import json
import uuid
from datetime import datetime

from utils import get_app_dir

_BASE_DIR = get_app_dir()
_LIBRARY_FILE = _BASE_DIR / "prompt_library.json"


def _load_library_json() -> dict:
    if not _LIBRARY_FILE.exists():
        return {"library": []}
    try:
        with open(_LIBRARY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {"library": []}
    except Exception:
        return {"library": []}


def _save_library_json(data: dict) -> None:
    try:
        _LIBRARY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_LIBRARY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def _get_db():
    """Lazy-import the database module, ensuring it is initialised. Returns None if sqlalchemy unavailable."""
    try:
        import database as db
        if not db.DB_AVAILABLE:
            return None
        if db._SessionFactory is None:
            db.init_db()
        return db
    except ImportError:
        return None


def _row_to_dict(row) -> dict:
    """Convert a PromptLibraryEntry ORM row to a plain dict (backward-compat format)."""
    return {
        "id": row.id,
        "name": row.name,
        "subject": row.subject or "",
        "style": row.style or "",
        "lighting": row.lighting or "",
        "mood": row.mood or "",
        "prompt": row.prompt or "",
        "theme_sentence": row.theme_sentence or "",
        "created_at": row.created_at or "",
        "usage_count": row.usage_count or 0,
        "tags": json.loads(row.tags_json) if row.tags_json else [],
    }


def load_library() -> dict:
    """Load the prompt library from the database."""
    db = _get_db()
    if db is not None:
        session = db.get_db_session()
        try:
            rows = session.query(db.PromptLibraryEntry).all()
            return {"library": [_row_to_dict(r) for r in rows]}
        except Exception:
            return {"library": []}
        finally:
            session.close()
    else:
        return _load_library_json()


def save_library(data: dict) -> None:
    """Save the prompt library to the database (upsert semantics)."""
    db = _get_db()
    if db is not None:
        session = db.get_db_session()
        try:
            existing_ids = {
                row.id
                for row in session.query(db.PromptLibraryEntry.id).all()
            }
            for entry in data.get("library", []):
                entry_id = entry.get("id", "")
                tags = entry.get("tags", [])
                if entry_id in existing_ids:
                    row = session.query(db.PromptLibraryEntry).get(entry_id)
                    if row is not None:
                        row.name = entry.get("name", row.name)
                        row.subject = entry.get("subject", row.subject)
                        row.style = entry.get("style", row.style)
                        row.lighting = entry.get("lighting", row.lighting)
                        row.mood = entry.get("mood", row.mood)
                        row.prompt = entry.get("prompt", row.prompt)
                        row.theme_sentence = entry.get("theme_sentence", row.theme_sentence)
                        row.created_at = entry.get("created_at", row.created_at)
                        row.usage_count = entry.get("usage_count", row.usage_count)
                        row.tags_json = json.dumps(tags, ensure_ascii=False)
                        existing_ids.discard(entry_id)
                else:
                    session.add(db.PromptLibraryEntry(
                        id=entry_id,
                        name=entry.get("name", ""),
                        subject=entry.get("subject", ""),
                        style=entry.get("style", ""),
                        lighting=entry.get("lighting", ""),
                        mood=entry.get("mood", ""),
                        prompt=entry.get("prompt", ""),
                        theme_sentence=entry.get("theme_sentence", ""),
                        created_at=entry.get("created_at", ""),
                        usage_count=entry.get("usage_count", 0),
                        tags_json=json.dumps(tags, ensure_ascii=False),
                    ))
            # Delete rows that were not in the incoming data
            if existing_ids:
                session.query(db.PromptLibraryEntry).filter(
                    db.PromptLibraryEntry.id.in_(existing_ids)
                ).delete(synchronize_session="fetch")
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    else:
        _save_library_json(data)


def add_prompt_to_library(
    name: str,
    subject: str,
    style: str,
    lighting: str,
    mood: str,
    prompt: str,
    theme_sentence: str = "",
    tags: list = None,
) -> str:
    """Add a new prompt to the library. Returns the new ID."""
    db = _get_db()
    prompt_id = f"lib_{uuid.uuid4().hex[:8]}"
    if db is not None:
        session = db.get_db_session()
        try:
            session.add(db.PromptLibraryEntry(
                id=prompt_id,
                name=name,
                subject=subject,
                style=style,
                lighting=lighting,
                mood=mood,
                prompt=prompt,
                theme_sentence=theme_sentence,
                created_at=datetime.now().isoformat(),
                usage_count=0,
                tags_json=json.dumps(tags or [], ensure_ascii=False),
            ))
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    else:
        data = _load_library_json()
        entry = {
            "id": prompt_id,
            "name": name,
            "subject": subject,
            "style": style,
            "lighting": lighting,
            "mood": mood,
            "prompt": prompt,
            "theme_sentence": theme_sentence,
            "created_at": datetime.now().isoformat(),
            "usage_count": 0,
            "tags": tags or [],
        }
        data["library"].append(entry)
        _save_library_json(data)
    return prompt_id


def get_library_prompts() -> list:
    """Get all prompts in the library."""
    lib = load_library()
    return lib.get("library", [])


def search_library(query: str) -> list:
    """Search library by name, subject, style, or tags (case-insensitive)."""
    lib = load_library()
    results = []
    query_lower = query.lower()
    for entry in lib.get("library", []):
        if (
            query_lower in entry.get("name", "").lower()
            or query_lower in entry.get("subject", "").lower()
            or query_lower in entry.get("style", "").lower()
            or any(query_lower in tag.lower() for tag in entry.get("tags", []))
        ):
            results.append(entry)
    return results


def get_prompt_by_id(prompt_id: str) -> dict:
    """Retrieve a specific prompt by ID."""
    db = _get_db()
    if db is not None:
        session = db.get_db_session()
        try:
            row = session.query(db.PromptLibraryEntry).get(prompt_id)
            if row is None:
                return None
            return _row_to_dict(row)
        except Exception:
            return None
        finally:
            session.close()
    else:
        data = _load_library_json()
        for entry in data.get("library", []):
            if entry.get("id") == prompt_id:
                return entry
        return None


def update_prompt_usage(prompt_id: str) -> None:
    """Increment the usage count for a prompt."""
    db = _get_db()
    if db is not None:
        session = db.get_db_session()
        try:
            row = session.query(db.PromptLibraryEntry).get(prompt_id)
            if row is not None:
                row.usage_count = (row.usage_count or 0) + 1
                session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    else:
        data = _load_library_json()
        for entry in data.get("library", []):
            if entry.get("id") == prompt_id:
                entry["usage_count"] = (entry.get("usage_count") or 0) + 1
                break
        _save_library_json(data)


def delete_prompt_from_library(prompt_id: str) -> bool:
    """Delete a prompt from the library."""
    db = _get_db()
    if db is not None:
        session = db.get_db_session()
        try:
            row = session.query(db.PromptLibraryEntry).get(prompt_id)
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    else:
        data = _load_library_json()
        original_len = len(data.get("library", []))
        data["library"] = [
            entry for entry in data.get("library", [])
            if entry.get("id") != prompt_id
        ]
        _save_library_json(data)
        return len(data["library"]) < original_len


def update_prompt_tags(prompt_id: str, tags: list) -> None:
    """Update tags for a prompt."""
    db = _get_db()
    if db is not None:
        session = db.get_db_session()
        try:
            row = session.query(db.PromptLibraryEntry).get(prompt_id)
            if row is not None:
                row.tags_json = json.dumps(tags, ensure_ascii=False)
                session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    else:
        data = _load_library_json()
        for entry in data.get("library", []):
            if entry.get("id") == prompt_id:
                entry["tags"] = tags
                break
        _save_library_json(data)


def get_prompt_categories() -> dict:
    """Get unique subjects, styles, moods in the library for filtering."""
    db = _get_db()
    if db is not None:
        session = db.get_db_session()
        try:
            rows = session.query(db.PromptLibraryEntry).all()
            categories = {"subjects": set(), "styles": set(), "moods": set(), "tags": set()}
            for row in rows:
                if row.subject:
                    categories["subjects"].add(row.subject)
                if row.style:
                    categories["styles"].add(row.style)
                if row.mood:
                    categories["moods"].add(row.mood)
                row_tags = json.loads(row.tags_json) if row.tags_json else []
                for tag in row_tags:
                    categories["tags"].add(tag)
            return {k: sorted(list(v)) for k, v in categories.items()}
        except Exception:
            return {"subjects": [], "styles": [], "moods": [], "tags": []}
        finally:
            session.close()
    else:
        data = _load_library_json()
        categories = {"subjects": set(), "styles": set(), "moods": set(), "tags": set()}
        for entry in data.get("library", []):
            if entry.get("subject"):
                categories["subjects"].add(entry["subject"])
            if entry.get("style"):
                categories["styles"].add(entry["style"])
            if entry.get("mood"):
                categories["moods"].add(entry["mood"])
            for tag in entry.get("tags", []):
                categories["tags"].add(tag)
        return {k: sorted(list(v)) for k, v in categories.items()}
