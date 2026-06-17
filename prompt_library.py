"""
prompt_library.py
-----------------
Manage a library of saved prompts for quick reuse and iteration.
"""

import json
import uuid
from pathlib import Path
from datetime import datetime

from utils import get_app_dir

BASE_DIR = get_app_dir()
LIBRARY_FILE = BASE_DIR / "prompt_library.json"


def load_library() -> dict:
    """Load the prompt library from disk."""
    if not LIBRARY_FILE.exists():
        return {"library": []}
    try:
        with open(LIBRARY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) and "library" in data else {"library": []}
    except Exception:
        return {"library": []}


def save_library(data: dict) -> None:
    """Save the prompt library to disk."""
    with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


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
    lib = load_library()
    prompt_id = f"lib_{uuid.uuid4().hex[:8]}"
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
    lib["library"].append(entry)
    save_library(lib)
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
    lib = load_library()
    for entry in lib.get("library", []):
        if entry.get("id") == prompt_id:
            return entry
    return None


def update_prompt_usage(prompt_id: str) -> None:
    """Increment the usage count for a prompt."""
    lib = load_library()
    for entry in lib.get("library", []):
        if entry.get("id") == prompt_id:
            entry["usage_count"] = entry.get("usage_count", 0) + 1
            break
    save_library(lib)


def delete_prompt_from_library(prompt_id: str) -> bool:
    """Delete a prompt from the library."""
    lib = load_library()
    original_len = len(lib.get("library", []))
    lib["library"] = [e for e in lib.get("library", []) if e.get("id") != prompt_id]
    if len(lib["library"]) < original_len:
        save_library(lib)
        return True
    return False


def update_prompt_tags(prompt_id: str, tags: list) -> None:
    """Update tags for a prompt."""
    lib = load_library()
    for entry in lib.get("library", []):
        if entry.get("id") == prompt_id:
            entry["tags"] = tags
            break
    save_library(lib)


def get_prompt_categories() -> dict:
    """Get unique subjects, styles, moods in the library for filtering."""
    lib = load_library()
    categories = {"subjects": set(), "styles": set(), "moods": set(), "tags": set()}
    for entry in lib.get("library", []):
        if entry.get("subject"):
            categories["subjects"].add(entry["subject"])
        if entry.get("style"):
            categories["styles"].add(entry["style"])
        if entry.get("mood"):
            categories["moods"].add(entry["mood"])
        for tag in entry.get("tags", []):
            categories["tags"].add(tag)
    return {k: sorted(list(v)) for k, v in categories.items()}
