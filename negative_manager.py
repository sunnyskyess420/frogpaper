"""
negative_manager.py
-------------------
Manage negative prompts: presets, style defaults, smart negatives.
"""

import json
import re
from pathlib import Path

from utils import get_app_dir

BASE_DIR = get_app_dir()
PRESETS_FILE = BASE_DIR / "negative_presets.json"


def load_negative_presets() -> dict:
    """Load negative prompt presets from disk."""
    if not PRESETS_FILE.exists():
        return {"presets": {}, "smart_keywords": {}, "style_defaults": {}}
    try:
        with open(PRESETS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception:
        return {"presets": {}, "smart_keywords": {}, "style_defaults": {}}


def get_preset_names() -> list:
    """Get list of all preset names."""
    data = load_negative_presets()
    return [p.get("name", "") for p in data.get("presets", {}).values()]


def get_preset_negatives(preset_key: str) -> str:
    """Get negative prompt text for a preset."""
    data = load_negative_presets()
    preset = data.get("presets", {}).get(preset_key, {})
    return preset.get("negatives", "")


def get_style_defaults(style_mode: str) -> str:
    """Get default negatives for a style mode."""
    data = load_negative_presets()
    defaults = data.get("style_defaults", {})
    return defaults.get(style_mode, "")


def extract_smart_negatives(prompt_text: str) -> list:
    """Extract keywords from prompt and find associated smart negatives."""
    data = load_negative_presets()
    smart_keywords = data.get("smart_keywords", {})
    
    prompt_lower = prompt_text.lower()
    found_negatives = []
    
    for keyword, negatives_list in smart_keywords.items():
        # Check if keyword is in prompt (as whole word)
        if re.search(r'\b' + re.escape(keyword) + r'\b', prompt_lower):
            found_negatives.extend(negatives_list)
    
    # Return unique negatives, preserve order
    seen = set()
    result = []
    for neg in found_negatives:
        if neg not in seen:
            result.append(neg)
            seen.add(neg)
    return result


def build_final_negative_prompt(
    preset_key: str = "none",
    custom_negatives: str = "",
    style_mode: str = "stylized",
    append_style_defaults: bool = True,
    prompt_text: str = "",
    append_smart_negatives: bool = True,
) -> str:
    """Build the final negative prompt from all sources."""
    parts = []
    
    # 1. Preset
    if preset_key and preset_key != "none":
        preset_neg = get_preset_negatives(preset_key)
        if preset_neg:
            parts.append(preset_neg)
    
    # 2. Custom
    if custom_negatives.strip():
        parts.append(custom_negatives.strip())
    
    # 3. Style defaults
    if append_style_defaults and style_mode:
        style_defaults = get_style_defaults(style_mode)
        if style_defaults:
            parts.append(style_defaults)
    
    # 4. Smart negatives from prompt
    if append_smart_negatives and prompt_text.strip():
        smart = extract_smart_negatives(prompt_text)
        if smart:
            parts.append(", ".join(smart))
    
    # Combine and deduplicate
    final_text = ", ".join(parts)
    
    # Deduplicate while preserving order
    negatives = [n.strip() for n in final_text.split(",")]
    seen = set()
    unique_negatives = []
    for neg in negatives:
        neg_lower = neg.lower()
        if neg_lower and neg_lower not in seen:
            unique_negatives.append(neg)
            seen.add(neg_lower)
    
    return ", ".join(unique_negatives)


def get_preset_description(preset_key: str) -> str:
    """Get description of a preset."""
    data = load_negative_presets()
    preset = data.get("presets", {}).get(preset_key, {})
    return preset.get("description", "")
