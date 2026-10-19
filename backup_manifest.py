"""backup_manifest.py
-------------------
The portable metadata half of a FrogPaper backup.

Images alone restore as an untagged pile. Tags and prompt parameters live in
SQLite keyed by *absolute* path, so they cannot be copied across machines --
they have to travel as paths relative to the app directory and be re-keyed on
import. That is what ``backup-manifest.json`` is for:

    {
      "schema": 1,
      "created": "...",
      "images": [
        {"rel_path": "wallpapers/generated/a.png", "subfolder": "generated",
         "size": 123, "sha256": "...", "tags": ["frog"], "prompt_params": {...}}
      ],
      "config_safe": {"app_theme": "darkforest", ...}
    }

Safety rules enforced here:

* **No secrets.** Only an explicit allow-list of config keys is exported; any
  key containing token/key/secret/credential is rejected even if added to the
  allow-list by mistake.
* **No path escapes.** Import only writes tags for files that actually live
  inside the target app directory and were restored by this run.
* **Additive.** Existing tags are merged, never replaced; existing prompt
  parameters are left alone.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

from cloud_restore import IMAGE_EXTENSIONS, SUBFOLDER_NAMES, sha256_file

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
MANIFEST_NAME = "backup-manifest.json"

# Everything the user can safely carry to a new machine. Credentials, tokens
# and provider client IDs are deliberately absent.
SAFE_CONFIG_KEYS = (
    "app_theme",
    "dimensions",
    "model_id",
    "provider",
    "wallpaper_format",
    "slideshow_enabled",
    "slideshow_interval",
    "slideshow_source",
    "slideshow_order",
    "slideshow_skip_duplicates",
    "minimize_to_tray",
    "remember_settings",
)

_SECRET_MARKERS = ("token", "secret", "key", "password", "credential")


def _norm(value):
    """Compare paths/relative paths case- and separator-insensitively."""
    return str(value).replace("\\", "/").lower()


def _is_secret_key(key):
    lowered = key.lower()
    return any(marker in lowered for marker in _SECRET_MARKERS)


def safe_config(config):
    """Return the allow-listed, non-secret subset of ``config``."""
    if not isinstance(config, dict):
        return {}
    result = {}
    for key in SAFE_CONFIG_KEYS:
        if key not in config or _is_secret_key(key):
            continue
        value = config[key]
        if isinstance(value, (str, int, float, bool)):
            result[key] = value
    return result


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

def build_manifest(app_dir, tags=None, config=None, hashes=None):
    """Build a manifest dict for the collection under ``app_dir``.

    ``tags`` takes the ``gallery_manager.load_tags()`` shape, keyed by absolute
    path; pass it explicitly to avoid a database read (and in tests).
    ``hashes`` maps ``rel_path -> sha256`` and lets a caller that already
    hashed the collection (``SyncManager``) skip a second full read.
    """
    hash_map = {_norm(key): value for key, value in (hashes or {}).items()}
    app_dir = Path(app_dir)
    if tags is None:
        try:
            import gallery_manager

            tags = gallery_manager.load_tags()
        except Exception as exc:  # tags are optional, images are not
            logger.warning("Manifest built without tags: %s", exc)
            tags = {}
    if config is None:
        try:
            from utils import load_config

            config = load_config()
        except Exception:
            config = {}

    tag_map = {}
    for raw_path, info in (tags.get("tags") or {}).items():
        tag_map[_norm(Path(raw_path).resolve())] = info

    images = []
    for subfolder in SUBFOLDER_NAMES:
        directory = app_dir / "wallpapers" / subfolder
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            try:
                info = tag_map.get(_norm(path.resolve()), {})
                rel_path = f"wallpapers/{subfolder}/{path.name}"
                images.append({
                    "rel_path": rel_path,
                    "subfolder": subfolder,
                    "name": path.name,
                    "size": path.stat().st_size,
                    "sha256": hash_map.get(_norm(rel_path)) or sha256_file(path),
                    "modified": path.stat().st_mtime,
                    "favorite": subfolder == "favorites",
                    "tags": sorted(info.get("tags") or []),
                    "prompt_params": info.get("prompt_params") or {},
                })
            except OSError as exc:
                logger.warning("Skipping %s in manifest: %s", path, exc)

    return {
        "schema": SCHEMA_VERSION,
        "app_version": _app_version(),
        "created": datetime.now().isoformat(timespec="seconds"),
        "image_count": len(images),
        "images": images,
        "config_safe": safe_config(config),
    }


def _app_version():
    try:
        from update_checker import CURRENT_VERSION

        return str(CURRENT_VERSION)
    except Exception:
        return "unknown"


def write_manifest(app_dir, **kwargs):
    """Build and atomically write ``<app_dir>/backup-manifest.json``."""
    app_dir = Path(app_dir)
    manifest = build_manifest(app_dir, **kwargs)
    path = app_dir / MANIFEST_NAME
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
    os.replace(tmp, path)
    logger.info("Wrote backup manifest (%d images) to %s",
                len(manifest["images"]), path)
    return path, manifest


# ---------------------------------------------------------------------------
# load
# ---------------------------------------------------------------------------

def load_manifest(path):
    """Load and validate a manifest, or return ``None`` if unusable.

    Unknown fields are ignored and a *newer* schema is accepted best-effort, so
    a backup made by a future version still restores what it can.
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        logger.warning("Could not read backup manifest %s: %s", path, exc)
        return None

    if not isinstance(data, dict) or not isinstance(data.get("images"), list):
        logger.warning("Backup manifest %s has an unexpected shape", path)
        return None

    schema = data.get("schema")
    if not isinstance(schema, int) or schema < 1:
        logger.warning("Backup manifest %s has no usable schema version", path)
        return None
    if schema > SCHEMA_VERSION:
        logger.info("Backup manifest schema %s is newer than %s; "
                    "importing known fields only", schema, SCHEMA_VERSION)
    return data


def manifest_for_source(source_root):
    """Return the manifest inside a backup folder, if there is one."""
    if not source_root:
        return None
    candidate = Path(source_root) / MANIFEST_NAME
    return load_manifest(candidate) if candidate.is_file() else None


# ---------------------------------------------------------------------------
# import
# ---------------------------------------------------------------------------

def apply_manifest(manifest, restored_paths, app_dir, add_tags=None,
                   save_params=None, get_params=None):
    """Merge manifest tags/prompt params onto the files this run restored.

    ``restored_paths`` are absolute paths actually written by the restore, so a
    skipped or conflicting file can never inherit another file's tags. Existing
    tags are unioned; existing prompt params win.
    """
    if not manifest:
        return {"tagged": 0, "prompt_params": 0, "skipped": 0}

    app_dir = Path(app_dir)
    if add_tags is None:
        import gallery_manager

        add_tags = gallery_manager.add_tags_to_image
    if save_params is None or get_params is None:
        import gallery_manager

        save_params = save_params or gallery_manager.save_prompt_parameters
        get_params = get_params or gallery_manager.get_prompt_parameters

    by_rel = {}
    for path in restored_paths:
        path = Path(path)
        try:
            rel = _norm(path.resolve().relative_to(app_dir.resolve()))
        except (ValueError, OSError):
            logger.warning("Refusing to import metadata for %s", path)
            continue
        by_rel[rel] = path

    counts = {"tagged": 0, "prompt_params": 0, "skipped": 0}
    for image in manifest.get("images") or []:
        if not isinstance(image, dict):
            continue
        rel = _norm(image.get("rel_path") or "")
        target = by_rel.get(rel)
        if target is None:
            counts["skipped"] += 1
            continue

        tags = [tag for tag in (image.get("tags") or []) if isinstance(tag, str)]
        if tags:
            try:
                add_tags(target, tags)
                counts["tagged"] += 1
            except Exception as exc:
                logger.warning("Could not tag %s: %s", target, exc)

        params = image.get("prompt_params") or {}
        if isinstance(params, dict) and params:
            try:
                if not get_params(target):
                    save_params(target, params)
                    counts["prompt_params"] += 1
            except Exception as exc:
                logger.warning("Could not import prompt params for %s: %s",
                               target, exc)

    logger.info("Manifest import: %s", counts)
    return counts


def apply_manifest_file(manifest_path, restored_paths, app_dir, **kwargs):
    """Convenience wrapper: load a manifest file and apply it."""
    manifest = load_manifest(manifest_path)
    if manifest is None:
        return {"tagged": 0, "prompt_params": 0, "skipped": 0}
    return apply_manifest(manifest, restored_paths, app_dir, **kwargs)


def apply_manifest_from_folder(source_root, restored_paths, app_dir, **kwargs):
    """Apply the manifest sitting in a backup folder, if present."""
    manifest = manifest_for_source(source_root)
    if manifest is None:
        return None
    return apply_manifest(manifest, restored_paths, app_dir, **kwargs)
