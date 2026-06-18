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

from utils import get_app_dir

BASE_DIR = get_app_dir()
PRESETS_FILE = BASE_DIR / "presets.json"


def load_presets() -> list:
    """Load all presets from disk."""
    if not PRESETS_FILE.exists():
        return []
    try:
        with open(PRESETS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_presets(presets: list) -> None:
    """Save presets to disk."""
    with open(PRESETS_FILE, "w", encoding="utf-8") as f:
        json.dump(presets, f, indent=2, ensure_ascii=False)


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
    presets = load_presets()
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
    presets.append(bundle)
    save_presets(presets)
    return bundle["id"]


def get_preset_by_id(preset_id: str) -> dict:
    """Retrieve a specific preset by ID."""
    presets = load_presets()
    for p in presets:
        if p.get("id") == preset_id:
            return p
    return None


def get_preset_by_name(name: str) -> dict:
    """Retrieve a preset by name."""
    presets = load_presets()
    for p in presets:
        if p.get("name") == name:
            return p
    return None


def delete_preset(preset_id: str) -> bool:
    """Delete a preset by ID."""
    presets = load_presets()
    original_len = len(presets)
    presets = [p for p in presets if p.get("id") != preset_id]
    if len(presets) < original_len:
        save_presets(presets)
        return True
    return False


def update_preset(preset_id: str, updates: dict) -> bool:
    """Update a preset with new data."""
    presets = load_presets()
    for p in presets:
        if p.get("id") == preset_id:
            p.update(updates)
            save_presets(presets)
            return True
    return False


def export_preset(preset_id: str, export_path: str | Path) -> bool:
    """Export a single preset as a JSON file."""
    preset = get_preset_by_id(preset_id)
    if not preset:
        return False
    try:
        export_path = Path(export_path)
        export_path.parent.mkdir(parents=True, exist_ok=True)
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(preset, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def import_preset(import_path: str | Path) -> str | None:
    """Import a preset from a JSON file. Returns the preset ID if successful."""
    try:
        base_real = os.path.realpath(BASE_DIR)
        target_real = os.path.realpath(import_path)
        if os.path.commonpath([base_real, target_real]) != base_real:
            raise Exception("Invalid file path")
        with open(target_real, "r", encoding="utf-8") as f:
            preset = json.load(f)
        if not isinstance(preset, dict):
            return None
        # Generate a new ID to avoid conflicts
        preset["id"] = f"preset_{uuid.uuid4().hex[:8]}"
        preset["created_at"] = datetime.now().isoformat()
        presets = load_presets()
        presets.append(preset)
        save_presets(presets)
        return preset["id"]
    except Exception:
        return None


def export_all_presets(export_path: str | Path) -> bool:
    """Export all presets as a single JSON file."""
    try:
        presets = load_presets()
        export_path = Path(export_path)
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
