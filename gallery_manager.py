"""
gallery_manager.py
------------------
Manage gallery organization, tagging, and folder structure.

Now backed by SQLite (image_tags + prompt_params tables) via database.py.
Falls back to JSON file I/O when SQLAlchemy is unavailable.
All public function signatures are unchanged — callers don't need modification.
"""

import json
import logging
import shutil
import threading
from pathlib import Path
from datetime import datetime

from utils import atomic_write_json, get_app_dir

logger = logging.getLogger(__name__)

BASE_DIR = get_app_dir()
WALLPAPERS_DIR = BASE_DIR / "wallpapers"
GENERATED_DIR = WALLPAPERS_DIR / "generated"

GENERATED_DIR.mkdir(parents=True, exist_ok=True)

# Module-level lock for thread safety (DB handles its own locking, but we keep
# this for multi-step read-modify-write patterns that need atomicity)
_tags_lock = threading.Lock()

# Lazy import of database to avoid circular import issues at module level
_db = None


def _get_db():
    """Lazy-initialize and return database module. Returns None if sqlalchemy is unavailable."""
    global _db
    if _db is None:
        try:
            import database
            if not database.DB_AVAILABLE:
                return None
            _db = database
            if _db._SessionFactory is None:
                _db.init_db()
        except ImportError:
            return None
    return _db


# ═══════════════════════════════════════════════════════════════════════════
#  LEGACY JSON COMPAT (kept for any code that still calls these)
# ═══════════════════════════════════════════════════════════════════════════

TAGS_FILE = BASE_DIR / "gallery_tags.json"


def _load_tags_json() -> dict:
    """Load tags data from the JSON fallback file.

    Never raises: a missing, corrupt, or wrong-shaped file yields an
    empty tag store so callers always get a usable dict back.
    """
    if TAGS_FILE.exists():
        try:
            with open(TAGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("tags"), dict):
                return data
            logger.warning("gallery_tags.json has unexpected shape - ignoring it")
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Could not read gallery_tags.json (%s) - starting with empty tags", e)
    return {"tags": {}}


def _save_tags_json(data: dict) -> None:
    """Save tags data to the JSON fallback file atomically."""
    atomic_write_json(TAGS_FILE, data)


def load_tags() -> dict:
    """Load image tags from DB and return in legacy JSON format.

    Returns the same shape as the old gallery_tags.json:
      {"tags": {"image_path": {"tags": [...], "tagged_at": "...", "prompt_params": {...}}}}
    """
    db = _get_db()
    if db is not None:
        try:
            session = db.get_db_session()
            try:
                from database import ImageTag, PromptParam

                # Query all image paths that have tags
                image_rows = session.query(
                    ImageTag.image_path,
                    ImageTag.tagged_at,
                ).distinct().all()

                result = {"tags": {}}
                for img_path, tagged_at in image_rows:
                    tags = [
                        row.tag for row in session.query(ImageTag.tag)
                        .filter(ImageTag.image_path == img_path)
                        .all()
                    ]
                    result["tags"][img_path] = {"tags": tags, "tagged_at": tagged_at or ""}

                    # Include prompt params if present
                    pp = session.query(PromptParam).filter(PromptParam.image_path == img_path).first()
                    if pp and pp.params_json:
                        try:
                            result["tags"][img_path]["prompt_params"] = json.loads(pp.params_json)
                        except Exception:
                            pass

                return result
            finally:
                session.close()
        except Exception as e:
            # Graceful degradation: a locked/corrupt DB must never take the
            # gallery tab down - fall back to the JSON compat file.
            logger.warning("DB read failed in load_tags; falling back to JSON: %s", e)
    return _load_tags_json()


def save_tags(data: dict) -> None:
    """Save tags from legacy format dict into DB. Used internally by legacy compat code."""
    _invalidate_tags_cache()
    db = _get_db()
    if db is not None:
        session = db.get_db_session()
        try:
            from database import ImageTag, PromptParam

            for image_path_str, entry in data.get("tags", {}).items():
                tags = entry.get("tags", [])
                tagged_at = entry.get("tagged_at", datetime.now().isoformat())

                # Delete existing tags for this image and re-insert
                session.query(ImageTag).filter(ImageTag.image_path == image_path_str).delete()
                for tag in tags:
                    session.add(ImageTag(image_path=image_path_str, tag=tag, tagged_at=tagged_at))

                # Update prompt params if present
                prompt_params = entry.get("prompt_params")
                if prompt_params:
                    existing = session.query(PromptParam).filter(
                        PromptParam.image_path == image_path_str
                    ).first()
                    if existing:
                        existing.params_json = json.dumps(prompt_params, ensure_ascii=False)
                        existing.updated_at = tagged_at
                    else:
                        session.add(PromptParam(
                            image_path=image_path_str,
                            params_json=json.dumps(prompt_params, ensure_ascii=False),
                            updated_at=tagged_at,
                        ))

            session.commit()
        except Exception:
            session.rollback()
            logger.exception("DB write failed in gallery_manager — rolled back, re-raising for caller")
            raise
        finally:
            session.close()
    else:
        _save_tags_json(data)


# ═══════════════════════════════════════════════════════════════════════════
#  TAG OPERATIONS (DB-backed)
# ═══════════════════════════════════════════════════════════════════════════

def add_tags_to_image(image_path: str | Path, tags: list[str]) -> None:
    """Add tags to an image."""
    _invalidate_tags_cache()
    image_path = str(Path(image_path).resolve())
    now = datetime.now().isoformat()

    db = _get_db()
    if db is not None:
        session = db.get_db_session()
        try:
            from database import ImageTag

            for tag in tags:
                # Avoid duplicates
                exists = session.query(ImageTag).filter(
                    ImageTag.image_path == image_path,
                    ImageTag.tag == tag,
                ).first()
                if not exists:
                    session.add(ImageTag(image_path=image_path, tag=tag, tagged_at=now))

            # Update tagged_at on existing tags for this image too
            session.query(ImageTag).filter(
                ImageTag.image_path == image_path,
            ).update({"tagged_at": now})

            session.commit()
        except Exception:
            session.rollback()
            logger.exception("DB write failed in gallery_manager — rolled back, re-raising for caller")
            raise
        finally:
            session.close()
    else:
        with _tags_lock:
            data = _load_tags_json()
            entry = data["tags"].setdefault(image_path, {"tags": [], "tagged_at": "", "prompt_params": {}})
            for tag in tags:
                if tag not in entry["tags"]:
                    entry["tags"].append(tag)
            entry["tagged_at"] = now
            _save_tags_json(data)


def add_tags_to_paths(paths: list[str | Path], tags: list[str]) -> None:
    """Add tags to multiple paths in a single transaction."""
    _invalidate_tags_cache()
    if not paths or not tags:
        return

    now = datetime.now().isoformat()
    db = _get_db()
    if db is not None:
        session = db.get_db_session()
        try:
            from database import ImageTag

            for p in paths:
                key = str(Path(p).resolve())
                for tag in tags:
                    exists = session.query(ImageTag).filter(
                        ImageTag.image_path == key,
                        ImageTag.tag == tag,
                    ).first()
                    if not exists:
                        session.add(ImageTag(image_path=key, tag=tag, tagged_at=now))

            session.commit()
        except Exception:
            session.rollback()
            logger.exception("DB write failed in gallery_manager — rolled back, re-raising for caller")
            raise
        finally:
            session.close()
    else:
        with _tags_lock:
            data = _load_tags_json()
            for p in paths:
                key = str(Path(p).resolve())
                entry = data["tags"].setdefault(key, {"tags": [], "tagged_at": "", "prompt_params": {}})
                for tag in tags:
                    if tag not in entry["tags"]:
                        entry["tags"].append(tag)
                entry["tagged_at"] = now
            _save_tags_json(data)


# ── Tags read memo (perf: N+1 session-per-image on every view load) ──────
# A single gallery view load calls get_tags_for_image once per image for
# tag filtering and one or more times per card (direct + fallback chain),
# and each call opened a fresh DB session. The memo below survives until
# the next tag WRITE — every writing function in this module calls
# _invalidate_tags_cache() first, so the cache can never outlive the
# data it reflects. (One-time startup migration in database.py runs
# before the UI exists and needs no invalidation hook.)
_TAGS_CACHE: dict = {}
_TAGS_CACHE_LIMIT = 2000


def _invalidate_tags_cache() -> None:
    """Drop all memoized tag reads. Called by every tag-writing function
    BEFORE its write work, so even a failed write leaves no stale memo."""
    _TAGS_CACHE.clear()


def get_tags_for_image(image_path: str | Path) -> list[str]:
    """Get tags for a specific image (memoized until the next tag write).

    The memo key is the canonical (resolved) path so different spellings of
    the same file share one entry, but the underlying read receives the
    ORIGINAL string: on Windows, ``Path('/img/a.png').resolve()`` grows a
    drive letter (``C:\\img\\a.png``), so looking the JSON store up by the
    canonical form alone would miss entries saved under the literal path
    the caller used.
    """
    original = str(image_path)
    key = str(Path(original).resolve())
    cached = _TAGS_CACHE.get(key)
    if cached is not None:
        return list(cached)
    tags = _read_tags_for_image(original)
    if len(_TAGS_CACHE) >= _TAGS_CACHE_LIMIT:
        _TAGS_CACHE.clear()
    _TAGS_CACHE[key] = tags
    return list(tags)


def _read_tags_for_image(image_path: str) -> list[str]:
    """Un-memoized tags read: DB first, JSON fallback (Task 5 hardening).

    Looks the image up first by the exact string the caller passed, then by
    its resolved form — write-side code stores resolved paths, but legacy
    JSON files / foreign callers may hold the unresolved spelling (and on
    Windows resolving a root-relative path changes it entirely).
    """
    canonical = str(Path(image_path).resolve())
    candidates = [image_path] if canonical == image_path else [image_path, canonical]
    db = _get_db()
    if db is not None:
        try:
            session = db.get_db_session()
            try:
                from database import ImageTag
                rows = []
                for candidate in candidates:
                    rows = session.query(ImageTag.tag).filter(
                        ImageTag.image_path == candidate
                    ).all()
                    if rows:
                        break
                return [row.tag for row in rows]
            finally:
                session.close()
        except Exception as e:
            logger.warning("DB read failed in get_tags_for_image; falling back to JSON: %s", e)
    data = _load_tags_json()
    tags_map = data["tags"]
    for candidate in candidates:
        entry = tags_map.get(candidate)
        if entry is not None:
            return list(entry.get("tags", []))
    return []


def remove_tag_from_image(image_path: str | Path, tag: str) -> None:
    """Remove a specific tag from an image."""
    _invalidate_tags_cache()
    image_path = str(Path(image_path).resolve())
    db = _get_db()
    if db is not None:
        session = db.get_db_session()
        try:
            from database import ImageTag
            session.query(ImageTag).filter(
                ImageTag.image_path == image_path,
                ImageTag.tag == tag,
            ).delete()
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("DB write failed in gallery_manager — rolled back, re-raising for caller")
            raise
        finally:
            session.close()
    else:
        with _tags_lock:
            data = _load_tags_json()
            entry = data["tags"].get(image_path)
            if entry and tag in entry["tags"]:
                entry["tags"].remove(tag)
            _save_tags_json(data)


def cleanup_orphaned_tags() -> int:
    """Remove tag rows that reference images no longer on disk.

    Also removes tags that have zero remaining image associations.
    Returns the number of tag rows cleaned up.
    """
    _invalidate_tags_cache()
    db = _get_db()
    if db is not None:
        session = db.get_db_session()
        try:
            from database import ImageTag

            # Find all distinct image_paths referenced in the tag table
            rows = session.query(ImageTag.image_path).distinct().all()
            removed = 0
            for (path_str,) in rows:
                if not Path(path_str).exists():
                    # Image no longer on disk — delete all its tag rows
                    count = session.query(ImageTag).filter(
                        ImageTag.image_path == path_str
                    ).delete()
                    removed += count

            session.commit()
            return removed
        except Exception:
            session.rollback()
            logger.exception("DB write failed in gallery_manager — rolled back, re-raising for caller")
            raise
        finally:
            session.close()
    else:
        with _tags_lock:
            data = _load_tags_json()
            paths_to_remove = [
                p for p in data["tags"] if not Path(p).exists()
            ]
            removed = sum(1 for p in paths_to_remove)
            for p in paths_to_remove:
                del data["tags"][p]
            if paths_to_remove:
                _save_tags_json(data)
            return removed


def get_all_tags() -> list[str]:
    """Get all unique tags across the gallery."""
    db = _get_db()
    if db is not None:
        try:
            session = db.get_db_session()
            try:
                from database import ImageTag
                rows = session.query(ImageTag.tag).distinct().all()
                return sorted([row.tag for row in rows])
            finally:
                session.close()
        except Exception as e:
            logger.warning("DB read failed in get_all_tags; falling back to JSON: %s", e)
    data = _load_tags_json()
    all_tags = set()
    for entry in data["tags"].values():
        all_tags.update(entry.get("tags", []))
    return sorted(all_tags)


def get_images_by_tag(tag: str) -> list[Path]:
    """Get all images with a specific tag."""
    db = _get_db()
    if db is not None:
        try:
            session = db.get_db_session()
            try:
                from database import ImageTag
                rows = session.query(ImageTag.image_path).filter(
                    ImageTag.tag == tag
                ).distinct().all()
                images = []
                for (path_str,) in rows:
                    p = Path(path_str)
                    if p.exists():
                        images.append(p)
                return images
            finally:
                session.close()
        except Exception as e:
            logger.warning("DB read failed in get_images_by_tag; falling back to JSON: %s", e)
    data = _load_tags_json()
    images = []
    for path_str, entry in data["tags"].items():
        if tag in entry.get("tags", []):
            p = Path(path_str)
            if p.exists():
                images.append(p)
    return images


def get_images_by_tags(tags: list[str], match_any=True) -> list[Path]:
    """Get images matching tags. If match_any=True, any tag matches; else all must match."""
    db = _get_db()
    if db is not None:
        try:
            session = db.get_db_session()
            try:
                from database import ImageTag

                if match_any:
                    rows = session.query(ImageTag.image_path).filter(
                        ImageTag.tag.in_(tags)
                    ).distinct().all()
                else:
                    # All tags must match: use GROUP BY + HAVING COUNT
                    from sqlalchemy import func
                    rows = session.query(ImageTag.image_path).filter(
                        ImageTag.tag.in_(tags)
                    ).group_by(ImageTag.image_path).having(
                        func.count(func.distinct(ImageTag.tag)) == len(tags)
                    ).all()

                images = []
                for (path_str,) in rows:
                    p = Path(path_str)
                    if p.exists():
                        images.append(p)
                return images
            finally:
                session.close()
        except Exception as e:
            logger.warning("DB read failed in get_images_by_tags; falling back to JSON: %s", e)
    data = _load_tags_json()
    images = []
    for path_str, entry in data["tags"].items():
        img_tags = set(entry.get("tags", []))
        if match_any:
            if img_tags & set(tags):
                p = Path(path_str)
                if p.exists():
                    images.append(p)
        else:
            if set(tags).issubset(img_tags):
                p = Path(path_str)
                if p.exists():
                    images.append(p)
    return images


# ═══════════════════════════════════════════════════════════════════════════
#  FILE OPERATIONS (filesystem + DB metadata)
# ═══════════════════════════════════════════════════════════════════════════

def organize_image_into_folder(image_path: str | Path, folder_name: str) -> Path:
    """Move/organize an image into a subfolder within generated/."""
    image_path = Path(image_path)
    if not image_path.exists():
        return None

    folder_path = GENERATED_DIR / folder_name
    new_path = folder_path / image_path.name
    try:
        folder_path.mkdir(parents=True, exist_ok=True)
        if image_path.parent != folder_path:
            shutil.move(str(image_path), str(new_path))
    except OSError:
        logger.exception("Failed to organize image %s into folder %r", image_path, folder_name)
        raise

    return new_path


def rename_image(image_path: str | Path, new_name: str) -> Path:
    """Rename an image file and update DB metadata."""
    _invalidate_tags_cache()
    image_path = Path(image_path)
    if not image_path.exists():
        return None

    new_path = image_path.parent / new_name
    try:
        image_path.rename(new_path)
    except OSError:
        logger.exception("Failed to rename %s to %r (target exists or file locked?)", image_path, new_name)
        raise

    old_path_str = str(image_path.resolve())
    new_path_str = str(new_path.resolve())
    db = _get_db()
    if db is not None:
        session = db.get_db_session()
        try:
            from database import ImageTag, PromptParam

            session.query(ImageTag).filter(
                ImageTag.image_path == old_path_str
            ).update({"image_path": new_path_str})

            session.query(PromptParam).filter(
                PromptParam.image_path == old_path_str
            ).update({"image_path": new_path_str})

            session.commit()
        except Exception:
            session.rollback()
            logger.exception("DB write failed in gallery_manager — rolled back, re-raising for caller")
            raise
        finally:
            session.close()
    else:
        with _tags_lock:
            data = _load_tags_json()
            if old_path_str in data["tags"]:
                data["tags"][new_path_str] = data["tags"].pop(old_path_str)
            _save_tags_json(data)

    return new_path


def get_folder_structure() -> dict:
    """Get the folder structure of the generated directory."""
    structure = {"root": [], "folders": {}}
    if not GENERATED_DIR.exists():
        return structure

    try:
        items = list(GENERATED_DIR.iterdir())
    except OSError as e:
        logger.warning("Could not scan gallery folders: %s", e)
        return structure

    for item in items:
        try:
            if item.is_file() and item.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
                structure["root"].append(item)
            elif item.is_dir():
                images = [f for f in item.iterdir() if f.is_file() and f.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}]
                structure["folders"][item.name] = images
        except OSError as e:
            # One unreadable subfolder shouldn't blank the whole gallery view
            logger.warning("Skipping unreadable gallery folder %s: %s", item, e)

    return structure


def delete_image_and_tags(image_path: str | Path) -> None:
    """Delete an image and its tags from DB.

    Also removes any tags that no longer have any associated images
    (orphaned tags) so the tag dropdown always reflects the current state.
    """
    _invalidate_tags_cache()
    image_path = Path(image_path)
    if image_path.exists():
        try:
            image_path.unlink()
        except OSError:
            logger.exception("Failed to delete image file %s (locked by another program?)", image_path)
            raise

    image_path_str = str(image_path.resolve())
    db = _get_db()
    if db is not None:
        session = db.get_db_session()
        try:
            from database import ImageTag, PromptParam

            # Collect tags that this image had before deleting them
            image_tags = [
                row.tag for row in
                session.query(ImageTag.tag).filter(ImageTag.image_path == image_path_str).all()
            ]

            session.query(ImageTag).filter(ImageTag.image_path == image_path_str).delete()
            session.query(PromptParam).filter(PromptParam.image_path == image_path_str).delete()

            # Remove orphaned tags (tags with zero remaining images)
            from sqlalchemy import func
            for tag in image_tags:
                remaining = session.query(func.count(ImageTag.id)).filter(
                    ImageTag.tag == tag
                ).scalar()
                if remaining == 0:
                    session.query(ImageTag).filter(ImageTag.tag == tag).delete()

            session.commit()
        except Exception:
            session.rollback()
            logger.exception("DB write failed in gallery_manager — rolled back, re-raising for caller")
            raise
        finally:
            session.close()
    else:
        with _tags_lock:
            data = _load_tags_json()
            data["tags"].pop(image_path_str, None)
            # Remove orphaned tags from JSON fallback too
            if data["tags"]:
                all_remaining_tags = set()
                for entry in data["tags"].values():
                    all_remaining_tags.update(entry.get("tags", []))
            else:
                all_remaining_tags = set()
            # No further action needed for JSON — tags are per-image,
            # so removing the image entry already removes its tag entries.
            _save_tags_json(data)


def save_prompt_parameters(image_path: str | Path, prompt_params: dict) -> None:
    """Save full prompt parameters for an image."""
    image_path = str(Path(image_path).resolve())
    now = datetime.now().isoformat()

    db = _get_db()
    if db is not None:
        session = db.get_db_session()
        try:
            from database import PromptParam

            existing = session.query(PromptParam).filter(
                PromptParam.image_path == image_path
            ).first()
            if existing:
                existing.params_json = json.dumps(prompt_params, ensure_ascii=False)
                existing.updated_at = now
            else:
                session.add(PromptParam(
                    image_path=image_path,
                    params_json=json.dumps(prompt_params, ensure_ascii=False),
                    updated_at=now,
                ))
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("DB write failed in gallery_manager — rolled back, re-raising for caller")
            raise
        finally:
            session.close()
    else:
        with _tags_lock:
            data = _load_tags_json()
            entry = data["tags"].setdefault(image_path, {"tags": [], "tagged_at": "", "prompt_params": {}})
            entry["prompt_params"] = prompt_params
            entry["tagged_at"] = now
            _save_tags_json(data)


def get_prompt_parameters(image_path: str | Path) -> dict:
    """Get saved prompt parameters for an image.

    Reads try the caller's exact string first, then the resolved form —
    see _read_tags_for_image for why (Windows drive-letter resolution).
    """
    original = str(image_path)
    canonical = str(Path(original).resolve())
    candidates = [original] if canonical == original else [original, canonical]
    db = _get_db()
    if db is not None:
        try:
            session = db.get_db_session()
            try:
                from database import PromptParam
                row = None
                for candidate in candidates:
                    row = session.query(PromptParam).filter(
                        PromptParam.image_path == candidate
                    ).first()
                    if row is not None:
                        break
                if row and row.params_json:
                    try:
                        return json.loads(row.params_json)
                    except Exception:
                        return {}
                return {}
            finally:
                session.close()
        except Exception as e:
            logger.warning("DB read failed in get_prompt_parameters; falling back to JSON: %s", e)
    data = _load_tags_json()
    tags_map = data.get("tags", {})
    for candidate in candidates:
        entry = tags_map.get(candidate)
        if entry is not None:
            return entry.get("prompt_params", {}) or {}
    return {}


def get_portrait_images() -> list[Path]:
    """Collect all portrait (9:16 aspect ratio) images from all folders.
    
    Returns:
        List of Path objects for portrait images found in generated, manual, 
        styled, and favorites folders.
    """
    try:
        from PIL import Image
        from set_wallpaper import collect_wallpapers, MANUAL_DIR, GENERATED_DIR, STYLED_DIR, FAVORITES_DIR
        
        # Collect images from all folders
        all_folders = [GENERATED_DIR, MANUAL_DIR, STYLED_DIR, FAVORITES_DIR]
        all_images = collect_wallpapers(all_folders) or []
        
        # Portrait ratio: 9:16 with tolerance
        target_ratio = 9/16
        tolerance = 0.1
        portrait_images = []
        
        for img_path in all_images:
            try:
                with Image.open(img_path) as img:
                    w, h = img.size
                    if h == 0:
                        continue
                    img_ratio = w / h
                    if abs(img_ratio - target_ratio) <= tolerance:
                        portrait_images.append(img_path)
            except Exception:
                # Skip images that can't be opened
                continue
        
        return portrait_images
    except ImportError:
        # PIL not available, return empty list
        return []
    except Exception:
        # Any other error, return empty list
        return []
