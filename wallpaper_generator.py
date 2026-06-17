import json
import os
import re
import time
from pathlib import Path
from datetime import datetime
from typing import Callable, Optional

from utils import get_app_dir

BASE_DIR = get_app_dir()
CONFIG_FILE = BASE_DIR / "config.json"
GENERATED_DIR = BASE_DIR / "wallpapers" / "generated"
GENERATED_DIR.mkdir(parents=True, exist_ok=True)

class ImageGenerationError(Exception):
    pass

def load_token() -> str:
    token = os.getenv("HUGGINGFACE_TOKEN", "").strip()
    if not token:
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            token = (cfg.get("huggingface_token") or "").strip()
        except Exception:
            pass
    if not token:
        raise ValueError("Missing Hugging Face token. Set the HUGGINGFACE_TOKEN environment variable first.")
    return token

def slugify_filename(text: str, max_words: int = 6, max_len: int = 60) -> str:
    text = (text or "wallpaper").lower()
    text = re.sub(r"[^a-z0-9\s-]", " ", text)
    words = [w for w in text.split() if w]
    words = words[:max_words] if words else ["wallpaper"]
    slug = "-".join(words)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:max_len].strip("-") or "wallpaper"

def sanitize_filename_part(text: str) -> str:
    """Sanitize subject or style: lowercase, spaces to _, remove non-alphanumeric."""
    text = (text or "").lower().strip()
    # Replace spaces with underscores
    text = re.sub(r"\s+", "_", text)
    # Remove everything except alphanumeric and underscores
    text = re.sub(r"[^a-z0-9_]", "", text)
    return text or "unknown"

def get_unique_filename(subject: str, style: str, output_dir: Path) -> str:
    """Compute SUBJECT_STYLE_YYYYMMDD_NUMBER filename."""
    sub = sanitize_filename_part(subject)
    sty = sanitize_filename_part(style)
    date_str = datetime.now().strftime("%Y%m%d")

    base_pattern = f"{sub}_{sty}_{date_str}_"

    # Find the highest existing numeric suffix to avoid collisions after deletions/renames
    suffix_re = re.compile(r"_(\d+)\.png$")
    max_n = 0
    for f in output_dir.glob(f"{base_pattern}*.png"):
        m = suffix_re.search(f.name)
        if m:
            max_n = max(max_n, int(m.group(1)))

    number = max_n + 1

    # Safety net: skip any number that somehow already exists
    while (output_dir / f"{base_pattern}{number}.png").exists():
        number += 1

    return f"{base_pattern}{number}"

def generate_image(
    prompt: str, 
    subject: str | None = None,
    style: str | None = None,
    filename: str | None = None, 
    status_callback: Optional[Callable[[str], None]] = None
) -> Path:
    def update_status(msg: str):
        if status_callback:
            status_callback(msg)

    try:
        from huggingface_hub import InferenceClient
    except ImportError:
        raise ImageGenerationError("Missing library. Run: pip install huggingface_hub Pillow")

    # Determine filename using the new structured format or fallback
    if subject and style:
        # Use the new SUBJECT_STYLE_YYYYMMDD_NUMBER format
        final_filename = get_unique_filename(subject, style, GENERATED_DIR)
    elif filename:
        # Use provided filename (existing flow)
        final_filename = filename
    else:
        # Default fallback
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        final_filename = f"wallpaper-{timestamp}"

    output_path = GENERATED_DIR / f"{final_filename}.png"

    try:
        token = load_token()
    except ValueError as e:
        raise ImageGenerationError(str(e))

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
        model_id = (config.get("model_id") or "black-forest-labs/FLUX.1-schnell").strip() or "black-forest-labs/FLUX.1-schnell"
        dims = config.get("dimensions", "1024x576").strip().split("x")
        try:
            width = int(dims[0].strip()) if len(dims) == 2 else 1024
            height = int(dims[1].strip()) if len(dims) == 2 else 576
        except (ValueError, IndexError):
            width, height = 1024, 576
    except Exception:
        model_id = "black-forest-labs/FLUX.1-schnell"
        width, height = 1024, 576

    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            update_status(f"Requesting generation (Attempt {attempt}/{max_attempts})...")
            # Set a generous timeout for 4K generation
            client = InferenceClient(provider="hf-inference", api_key=token, timeout=120)
            image = client.text_to_image(prompt, model=model_id, width=width, height=height)
            update_status("Saving generated image...")
            image.save(str(output_path))
            return output_path
        except Exception as e:
            err = str(e)
            err_lower = err.lower()
            
            # Specific handling for common API errors
            if "402" in err or "payment required" in err_lower:
                raise ImageGenerationError("Hugging Face credits exhausted or payment required.")
            if "401" in err or "unauthorized" in err_lower:
                raise ImageGenerationError("Token rejected. Check HUGGINGFACE_TOKEN.")
            
            # Retryable errors
            is_retryable = False
            wait_time = 10
            
            if "429" in err or "too many requests" in err_lower:
                is_retryable = True
                wait_time = 30
                update_status("Rate limited (429). Waiting 30s to retry...")
            elif "loading" in err_lower or "503" in err:
                is_retryable = True
                wait_time = 20
                update_status("Model is loading (503). Waiting 20s to retry...")
            elif "server disconnected" in err_lower or "connection" in err_lower or "read timeout" in err_lower:
                is_retryable = True
                wait_time = 15
                update_status(f"Network error: {err[:40]}... Retrying in 15s...")
            
            if is_retryable and attempt < max_attempts:
                time.sleep(wait_time)
                continue
            
            if attempt < max_attempts:
                update_status(f"Error occurred. Retrying in 10s... ({err[:50]})")
                time.sleep(10)
            else:
                # Final attempt failed
                if "3840" in str(width) or "2160" in str(height):
                    raise ImageGenerationError(f"Image generation failed: {err[:150]}. Note: 4K generation may be unstable on the free API.")
                raise ImageGenerationError(f"Image generation failed: {err[:200]}")

    raise ImageGenerationError("All attempts failed.")
