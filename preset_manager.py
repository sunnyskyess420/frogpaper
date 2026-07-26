"""
preset_manager.py
-----------------
Manage preset bundles that include input fields, generated themes, and prompts.
"""

import json
import os
import uuid
from pathlib import Path
from datetime import datetime

from utils import atomic_write_json, get_app_dir

BASE_DIR = get_app_dir()


def _get_db():
    """Lazily import and initialise the database module, returning it."""
    import database as db
    if not getattr(db, 'DB_AVAILABLE', True):
        return None
    if db._SessionFactory is None:
        db.init_db()
    return db


def _validate_path(file_path: str | Path, allowed_dir: Path = None) -> Path:
    """Validate that a file path is within the allowed directory to prevent path traversal attacks."""
    file_path = Path(file_path).resolve()
    allowed_dir = allowed_dir or BASE_DIR
    allowed_dir = allowed_dir.resolve()
    
    # Check if the resolved path is within the allowed directory
    try:
        file_path.relative_to(allowed_dir)
        return file_path
    except ValueError:
        # Path is outside allowed directory
        raise ValueError(f"Path {file_path} is outside allowed directory {allowed_dir}")


def _row_to_dict(row) -> dict:
    """Convert a Preset ORM row into the public dict format."""
    return {
        "id": row.id,
        "name": row.name,
        "created_at": row.created_at,
        "inputs": json.loads(row.inputs_json) if row.inputs_json else {},
        "themes": json.loads(row.themes_json) if row.themes_json else [],
        "prompts": json.loads(row.prompts_json) if row.prompts_json else [],
        "favorite_prompts": json.loads(row.favorite_prompts_json) if row.favorite_prompts_json else [],
    }


def load_presets() -> list:
    """Load all presets from the database."""
    db = _get_db()
    if db is not None:
        session = db.get_db_session()
        try:
            rows = session.query(db.Preset).all()
            return [_row_to_dict(r) for r in rows]
        except Exception:
            return []
        finally:
            session.close()
    else:
        presets_path = BASE_DIR / "presets.json"
        if presets_path.exists():
            try:
                with open(presets_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data if isinstance(data, list) else []
            except Exception:
                return []
        return []


def save_presets(presets: list) -> None:
    """Replace all presets in the database with the given list (delete-all then reinsert)."""
    db = _get_db()
    if db is not None:
        session = db.get_db_session()
        try:
            session.query(db.Preset).delete()
            for p in presets:
                session.add(db.Preset(
                    id=p.get("id", f"preset_{uuid.uuid4().hex[:8]}"),
                    name=p.get("name", ""),
                    created_at=p.get("created_at", ""),
                    inputs_json=json.dumps(p.get("inputs", {}), ensure_ascii=False),
                    themes_json=json.dumps(p.get("themes", []), ensure_ascii=False),
                    prompts_json=json.dumps(p.get("prompts", []), ensure_ascii=False),
                    favorite_prompts_json=json.dumps(p.get("favorite_prompts", []), ensure_ascii=False),
                ))
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()
    else:
        presets_path = BASE_DIR / "presets.json"
        atomic_write_json(presets_path, presets)


def create_bundle_preset(
    name: str,
    subject: str,
    style: str,
    lighting: str,
    mood: str,
    style_mode: str,
    themes: list = None,
    prompts: list = None,
    favorite_prompts: list = None,
) -> dict:
    """Create a comprehensive preset bundle."""
    return {
        "id": f"preset_{uuid.uuid4().hex[:8]}",
        "name": name,
        "created_at": datetime.now().isoformat(),
        "inputs": {
            "subject": subject,
            "style": style,
            "lighting": lighting,
            "mood": mood,
            "style_mode": style_mode,
        },
        "themes": themes or [],
        "prompts": prompts or [],
        "favorite_prompts": favorite_prompts or [],
    }


def save_bundle_preset(
    name: str,
    subject: str,
    style: str,
    lighting: str,
    mood: str,
    style_mode: str,
    themes: list = None,
    prompts: list = None,
    favorite_prompts: list = None,
) -> str:
    """Save a new bundle preset. Returns the preset ID."""
    db = _get_db()
    bundle = create_bundle_preset(
        name=name,
        subject=subject,
        style=style,
        lighting=lighting,
        mood=mood,
        style_mode=style_mode,
        themes=themes,
        prompts=prompts,
        favorite_prompts=favorite_prompts,
    )
    if db is not None:
        session = db.get_db_session()
        try:
            session.add(db.Preset(
                id=bundle["id"],
                name=bundle["name"],
                created_at=bundle["created_at"],
                inputs_json=json.dumps(bundle["inputs"], ensure_ascii=False),
                themes_json=json.dumps(bundle["themes"], ensure_ascii=False),
                prompts_json=json.dumps(bundle["prompts"], ensure_ascii=False),
                favorite_prompts_json=json.dumps(bundle["favorite_prompts"], ensure_ascii=False),
            ))
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()
    else:
        presets_path = BASE_DIR / "presets.json"
        presets = []
        if presets_path.exists():
            try:
                with open(presets_path, "r", encoding="utf-8") as f:
                    presets = json.load(f)
                if not isinstance(presets, list):
                    presets = []
            except Exception:
                presets = []
        presets.append(bundle)
        atomic_write_json(presets_path, presets)
    return bundle["id"]


def get_preset_by_id(preset_id: str) -> dict:
    """Retrieve a specific preset by ID."""
    db = _get_db()
    if db is not None:
        session = db.get_db_session()
        try:
            row = session.query(db.Preset).filter(db.Preset.id == preset_id).first()
            return _row_to_dict(row) if row else None
        except Exception:
            return None
        finally:
            session.close()
    else:
        presets_path = BASE_DIR / "presets.json"
        if presets_path.exists():
            try:
                with open(presets_path, "r", encoding="utf-8") as f:
                    presets = json.load(f)
                if isinstance(presets, list):
                    for p in presets:
                        if p.get("id") == preset_id:
                            return p
            except Exception:
                pass
        return None


def get_preset_by_name(name: str) -> dict:
    """Retrieve a preset by name."""
    db = _get_db()
    if db is not None:
        session = db.get_db_session()
        try:
            row = session.query(db.Preset).filter(db.Preset.name == name).first()
            return _row_to_dict(row) if row else None
        except Exception:
            return None
        finally:
            session.close()
    else:
        presets_path = BASE_DIR / "presets.json"
        if presets_path.exists():
            try:
                with open(presets_path, "r", encoding="utf-8") as f:
                    presets = json.load(f)
                if isinstance(presets, list):
                    for p in presets:
                        if p.get("name") == name:
                            return p
            except Exception:
                pass
        return None


def delete_preset(preset_id: str) -> bool:
    """Delete a preset by ID."""
    db = _get_db()
    if db is not None:
        session = db.get_db_session()
        try:
            row = session.query(db.Preset).filter(db.Preset.id == preset_id).first()
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True
        except Exception:
            session.rollback()
            return False
        finally:
            session.close()
    else:
        presets_path = BASE_DIR / "presets.json"
        if presets_path.exists():
            try:
                with open(presets_path, "r", encoding="utf-8") as f:
                    presets = json.load(f)
                if isinstance(presets, list):
                    new_presets = [p for p in presets if p.get("id") != preset_id]
                    if len(new_presets) != len(presets):
                        atomic_write_json(presets_path, new_presets)
                        return True
            except Exception:
                pass
        return False


def update_preset(preset_id: str, updates: dict) -> bool:
    """Update a preset with new data."""
    db = _get_db()
    if db is not None:
        session = db.get_db_session()
        try:
            row = session.query(db.Preset).filter(db.Preset.id == preset_id).first()
            if row is None:
                return False

            if "name" in updates:
                row.name = updates["name"]
            if "created_at" in updates:
                row.created_at = updates["created_at"]
            if "inputs" in updates:
                row.inputs_json = json.dumps(updates["inputs"], ensure_ascii=False)
            if "themes" in updates:
                row.themes_json = json.dumps(updates["themes"], ensure_ascii=False)
            if "prompts" in updates:
                row.prompts_json = json.dumps(updates["prompts"], ensure_ascii=False)
            if "favorite_prompts" in updates:
                row.favorite_prompts_json = json.dumps(updates["favorite_prompts"], ensure_ascii=False)

            session.commit()
            return True
        except Exception:
            session.rollback()
            return False
        finally:
            session.close()
    else:
        presets_path = BASE_DIR / "presets.json"
        if presets_path.exists():
            try:
                with open(presets_path, "r", encoding="utf-8") as f:
                    presets = json.load(f)
                if isinstance(presets, list):
                    for p in presets:
                        if p.get("id") == preset_id:
                            p.update(updates)
                            atomic_write_json(presets_path, presets)
                            return True
            except Exception:
                pass
        return False


def export_preset(preset_id: str, export_path: str | Path) -> bool:
    """Export a single preset as a JSON file."""
    preset = get_preset_by_id(preset_id)
    if not preset:
        return False
    try:
        export_path = _validate_path(export_path)
        export_path.parent.mkdir(parents=True, exist_ok=True)
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(preset, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def import_preset(import_path: str | Path) -> str | None:
    """Import a preset from a JSON file. Returns the preset ID if successful."""
    try:
        import_path = _validate_path(import_path)
        with open(import_path, "r", encoding="utf-8") as f:
            preset = json.load(f)
        if not isinstance(preset, dict):
            return None
        # Generate a new ID to avoid conflicts
        preset["id"] = f"preset_{uuid.uuid4().hex[:8]}"
        preset["created_at"] = datetime.now().isoformat()

        db = _get_db()
        if db is not None:
            session = db.get_db_session()
            try:
                session.add(db.Preset(
                    id=preset["id"],
                    name=preset.get("name", ""),
                    created_at=preset["created_at"],
                    inputs_json=json.dumps(preset.get("inputs", {}), ensure_ascii=False),
                    themes_json=json.dumps(preset.get("themes", []), ensure_ascii=False),
                    prompts_json=json.dumps(preset.get("prompts", []), ensure_ascii=False),
                    favorite_prompts_json=json.dumps(preset.get("favorite_prompts", []), ensure_ascii=False),
                ))
                session.commit()
            except Exception:
                session.rollback()
                return None
            finally:
                session.close()
        else:
            presets_path = BASE_DIR / "presets.json"
            presets = []
            if presets_path.exists():
                try:
                    with open(presets_path, "r", encoding="utf-8") as f:
                        presets = json.load(f)
                    if not isinstance(presets, list):
                        presets = []
                except Exception:
                    presets = []
            presets.append(preset)
            atomic_write_json(presets_path, presets)
        return preset["id"]
    except Exception:
        return None


def export_all_presets(export_path: str | Path) -> bool:
    """Export all presets as a single JSON file."""
    try:
        presets = load_presets()
        export_path = _validate_path(export_path)
        export_path.parent.mkdir(parents=True, exist_ok=True)
        base_real = os.path.realpath(BASE_DIR)
        target_real = os.path.realpath(export_path)
        if os.path.commonpath([base_real, target_real]) != base_real:
            raise Exception("Invalid file path")
        with open(target_real, "w", encoding="utf-8") as f:
            json.dump(presets, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False
