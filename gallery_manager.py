"""
gallery_manager.py
------------------
Manage gallery organization, tagging, and folder structure.
"""

import json
import shutil
from pathlib import Path
from datetime import datetime

from utils import get_app_dir

BASE_DIR = get_app_dir()
TAGS_FILE = BASE_DIR / "gallery_tags.json"
WALLPAPERS_DIR = BASE_DIR / "wallpapers"
GENERATED_DIR = WALLPAPERS_DIR / "generated"

GENERATED_DIR.mkdir(parents=True, exist_ok=True)


def load_tags() -> dict:
    """Load image tags from disk."""
    if not TAGS_FILE.exists():
        return {"tags": {}}
    try:
        with open(TAGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {"tags": {}}
    except Exception:
        return {"tags": {}}


def save_tags(data: dict) -> None:
    """Save image tags to disk."""
    with open(TAGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def add_tags_to_image(image_path: str | Path, tags: list[str]) -> None:
    """Add tags to an image."""
    image_path = str(Path(image_path).resolve())
    data = load_tags()
    if image_path not in data.get("tags", {}):
        data["tags"][image_path] = {}
    data["tags"][image_path]["tags"] = list(set(data["tags"][image_path].get("tags", []) + tags))
    data["tags"][image_path]["tagged_at"] = datetime.now().isoformat()
    save_tags(data)


def add_tags_to_paths(paths: list[str | Path], tags: list[str]) -> None:
    """Add tags to multiple paths in a single load/save cycle (atomic propagation)."""
    if not paths or not tags:
        return
    now = datetime.now().isoformat()
    data = load_tags()
    for p in paths:
        key = str(Path(p).resolve())
        if key not in data.get("tags", {}):
            data["tags"][key] = {}
        data["tags"][key]["tags"] = list(set(data["tags"][key].get("tags", []) + tags))
        data["tags"][key]["tagged_at"] = now
    save_tags(data)


def get_tags_for_image(image_path: str | Path) -> list[str]:
    """Get tags for a specific image."""
    image_path = str(Path(image_path).resolve())
    data = load_tags()
    return data.get("tags", {}).get(image_path, {}).get("tags", [])


def remove_tag_from_image(image_path: str | Path, tag: str) -> None:
    """Remove a specific tag from an image."""
    image_path = str(Path(image_path).resolve())
    data = load_tags()
    if image_path in data.get("tags", {}):
        tags = data["tags"][image_path].get("tags", [])
        if tag in tags:
            tags.remove(tag)
            data["tags"][image_path]["tags"] = tags
            save_tags(data)


def get_all_tags() -> list[str]:
    """Get all unique tags across the gallery."""
    data = load_tags()
    all_tags = set()
    for entry in data.get("tags", {}).values():
        all_tags.update(entry.get("tags", []))
    return sorted(list(all_tags))


def get_images_by_tag(tag: str) -> list[Path]:
    """Get all images with a specific tag."""
    data = load_tags()
    images = []
    for image_path, entry in data.get("tags", {}).items():
        if tag in entry.get("tags", []):
            p = Path(image_path)
            if p.exists():
                images.append(p)
    return images


def get_images_by_tags(tags: list[str], match_any=True) -> list[Path]:
    """Get images matching tags. If match_any=True, any tag matches; else all must match."""
    data = load_tags()
    images = []
    for image_path, entry in data.get("tags", {}).items():
        image_tags = entry.get("tags", [])
        if image_tags:
            if match_any and any(t in image_tags for t in tags):
                p = Path(image_path)
                if p.exists():
                    images.append(p)
            elif not match_any and all(t in image_tags for t in tags):
                p = Path(image_path)
                if p.exists():
                    images.append(p)
    return images


def organize_image_into_folder(image_path: str | Path, folder_name: str) -> Path:
    """Move/organize an image into a subfolder within generated/."""
    image_path = Path(image_path)
    if not image_path.exists():
        return None

    folder_path = GENERATED_DIR / folder_name
    folder_path.mkdir(parents=True, exist_ok=True)
    new_path = folder_path / image_path.name

    if image_path.parent != folder_path:
        shutil.move(str(image_path), str(new_path))

    return new_path


def rename_image(image_path: str | Path, new_name: str) -> Path:
    """Rename an image file."""
    image_path = Path(image_path)
    if not image_path.exists():
        return None

    new_path = image_path.parent / new_name
    image_path.rename(new_path)

    # Update tags file to reflect new path
    data = load_tags()
    old_path_str = str(image_path.resolve())
    new_path_str = str(new_path.resolve())
    if old_path_str in data.get("tags", {}):
        data["tags"][new_path_str] = data["tags"].pop(old_path_str)
        save_tags(data)

    return new_path


def get_folder_structure() -> dict:
    """Get the folder structure of the generated directory."""
    structure = {"root": [], "folders": {}}
    if not GENERATED_DIR.exists():
        return structure

    for item in GENERATED_DIR.iterdir():
        if item.is_file() and item.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
            structure["root"].append(item)
        elif item.is_dir():
            images = [f for f in item.iterdir() if f.is_file() and f.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}]
            structure["folders"][item.name] = images

    return structure


def delete_image_and_tags(image_path: str | Path) -> None:
    """Delete an image and its tags."""
    image_path = Path(image_path)
    if image_path.exists():
        image_path.unlink()

    # Remove from tags file
    data = load_tags()
    image_path_str = str(image_path.resolve())
    if image_path_str in data.get("tags", {}):
        del data["tags"][image_path_str]
        save_tags(data)
