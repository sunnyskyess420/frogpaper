import json
import os
import re
import time
import urllib.request
import urllib.parse
import urllib.error
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

def _load_cloudflare_config() -> tuple:
    """Load Cloudflare API token and account ID from config.
    Returns (token, account_id)."""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        token = (cfg.get("cloudflare_token") or "").strip()
        account_id = (cfg.get("cloudflare_account_id") or "").strip()
    except Exception:
        token, account_id = "", ""
    if not token:
        raise ValueError("Missing Cloudflare API token. Set it in Settings.")
    if not account_id:
        raise ValueError("Missing Cloudflare Account ID. Set it in Settings.")
    return token, account_id

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


# ──── Pollinations.ai backend ─────────────────────────────────────────────

def _generate_pollinations(prompt: str, model_id: str, width: int, height: int,
                           output_path: Path, status_callback=None) -> Path:
    """Generate image via Pollinations.ai (free, no API key needed)."""
    def update_status(msg):
        if status_callback:
            status_callback(msg)

    # Pollinations uses a simple GET URL API
    # https://image.pollinations.ai/prompt/{encoded_prompt}?model={model}&width={w}&height={h}&nologo=true
    encoded_prompt = urllib.parse.quote(prompt)
    base_url = "https://image.pollinations.ai/prompt/"

    # Pollinations model names: flux, flux-realism, flux-anime, flux-3d, flux-cablyai, turbo
    model = model_id if model_id else "flux"

    params = urllib.parse.urlencode({
        "model": model,
        "width": str(width),
        "height": str(height),
        "nologo": "true",
        "nologo": "true",
        "enhance": "true",
    })

    url = f"{base_url}{encoded_prompt}?{params}"

    update_status("Connecting to Pollinations.ai...")

    # Pollinations can take a while for larger images, use generous timeout
    req = urllib.request.Request(url, headers={"User-Agent": "FrogPaper/1.0"})

    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            update_status(f"Downloading from Pollinations.ai (attempt {attempt}/{max_attempts})...")
            with urllib.request.urlopen(req, timeout=180) as response:
                if response.status != 200:
                    raise ImageGenerationError(
                        f"Pollinations.ai returned HTTP {response.status}")

                update_status("Saving generated image...")
                with open(output_path, "wb") as out_file:
                    out_file.write(response.read())

                # Verify the file is actually an image (not an error page)
                file_size = output_path.stat().st_size
                if file_size < 1000:
                    # Likely an error response, not a real image
                    raise ImageGenerationError(
                        f"Pollinations.ai returned too-small response ({file_size} bytes). Try again.")

                return output_path

        except urllib.error.HTTPError as e:
            if e.code == 429:
                if attempt < max_attempts:
                    wait = 20
                    update_status(f"Rate limited (429). Waiting {wait}s...")
                    time.sleep(wait)
                    continue
                raise ImageGenerationError("Pollinations.ai rate limit reached. Wait a minute and try again.")
            elif e.code == 503:
                if attempt < max_attempts:
                    wait = 15
                    update_status(f"Pollinations.ai overloaded (503). Waiting {wait}s...")
                    time.sleep(wait)
                    continue
                raise ImageGenerationError("Pollinations.ai is temporarily unavailable.")
            else:
                raise ImageGenerationError(f"Pollinations.ai HTTP error: {e.code}")
        except urllib.error.URLError as e:
            if attempt < max_attempts:
                update_status(f"Network error. Waiting 15s... ({str(e)[:50]})")
                time.sleep(15)
                continue
            raise ImageGenerationError(f"Pollinations.ai network error: {str(e)[:150]}")
        except ImageGenerationError:
            raise
        except Exception as e:
            if attempt < max_attempts:
                update_status(f"Error occurred. Retrying in 10s...")
                time.sleep(10)
                continue
            raise ImageGenerationError(f"Pollinations.ai failed: {str(e)[:200]}")

    raise ImageGenerationError("All Pollinations.ai attempts failed.")


# ──── Cloudflare Workers AI backend ───────────────────────────────────────

def _generate_cloudflare(prompt: str, model_id: str, width: int, height: int,
                          output_path: Path, status_callback=None) -> Path:
    """Generate image via Cloudflare Workers AI (free tier: 10,000 neurons/day)."""
    def update_status(msg):
        if status_callback:
            status_callback(msg)

    token, account_id = _load_cloudflare_config()

    # Cloudflare Workers AI REST API requires account ID in the URL path
    model = model_id if model_id else "@cf/black-forest-labs/flux-1-schnell"
    api_url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"

    payload = json.dumps({
        "prompt": prompt,
        "width": width,
        "height": height,
    }).encode("utf-8")

    req = urllib.request.Request(
        api_url,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            update_status(f"Requesting Cloudflare Workers AI (attempt {attempt}/{max_attempts})...")
            with urllib.request.urlopen(req, timeout=180) as response:
                result_bytes = response.read()

            # Cloudflare returns JSON with base64 image data
            result = json.loads(result_bytes.decode("utf-8"))

            # Check for API errors
            if not result.get("success", True):
                errors = result.get("errors", [])
                raise ImageGenerationError(
                    f"Cloudflare API error: {errors[0] if errors else 'Unknown error'}")

            # Extract image data
            image_data = result.get("result", {}).get("image", "")
            if not image_data:
                raise ImageGenerationError("Cloudflare returned no image data.")

            update_status("Saving generated image...")

            import base64
            img_bytes = base64.b64decode(image_data)
            with open(output_path, "wb") as out_file:
                out_file.write(img_bytes)

            return output_path

        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass

            if e.code == 400:
                # Parse CF error for user-friendly message
                try:
                    err_json = json.loads(err_body)
                    cf_errors = err_json.get("errors", [])
                    cf_code = cf_errors[0].get("code", 0) if cf_errors else 0
                    cf_msg = cf_errors[0].get("message", "") if cf_errors else ""
                    if cf_code == 7000:
                        raise ImageGenerationError(
                            "Cloudflare: Invalid API path. Check your Account ID in Settings "
                            "(dash.cloudflare.com → right sidebar shows your Account ID).")
                    raise ImageGenerationError(
                        f"Cloudflare API error: {cf_msg or err_body[:200]}")
                except ImageGenerationError:
                    raise
                except Exception:
                    raise ImageGenerationError(
                        f"Cloudflare request error: {err_body[:200]}")
            elif e.code == 401:
                raise ImageGenerationError(
                    "Cloudflare token rejected. Check your Cloudflare API Token in Settings.")
            elif e.code == 402:
                raise ImageGenerationError(
                    "Cloudflare free tier neurons exhausted. They reset daily at midnight UTC.")
            elif e.code == 429:
                if attempt < max_attempts:
                    update_status("Cloudflare rate limited (429). Waiting 20s...")
                    time.sleep(20)
                    continue
                raise ImageGenerationError("Cloudflare rate limit reached.")
            elif e.code >= 500:
                if attempt < max_attempts:
                    update_status(f"Cloudflare server error ({e.code}). Waiting 15s...")
                    time.sleep(15)
                    continue
                raise ImageGenerationError(f"Cloudflare server error: {e.code}")
            else:
                raise ImageGenerationError(
                    f"Cloudflare HTTP {e.code}: {err_body[:200]}")
        except urllib.error.URLError as e:
            if attempt < max_attempts:
                update_status(f"Cloudflare network error. Waiting 15s...")
                time.sleep(15)
                continue
            raise ImageGenerationError(f"Cloudflare network error: {str(e)[:150]}")
        except ImageGenerationError:
            raise
        except Exception as e:
            if attempt < max_attempts:
                update_status(f"Error occurred. Retrying in 10s...")
                time.sleep(10)
                continue
            raise ImageGenerationError(f"Cloudflare generation failed: {str(e)[:200]}")

    raise ImageGenerationError("All Cloudflare attempts failed.")


# ──── Hugging Face backend ───────────────────────────────────────────────

def _generate_huggingface(prompt: str, model_id: str, width: int, height: int,
                            output_path: Path, status_callback=None) -> Path:
    """Generate image via Hugging Face Inference API."""
    def update_status(msg):
        if status_callback:
            status_callback(msg)

    try:
        from huggingface_hub import InferenceClient
    except ImportError:
        raise ImageGenerationError("Missing library. Run: pip install huggingface_hub Pillow")

    try:
        token = load_token()
    except ValueError as e:
        raise ImageGenerationError(str(e))

    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            update_status(f"Requesting HuggingFace (Attempt {attempt}/{max_attempts})...")
            client = InferenceClient(provider="auto", api_key=token, timeout=120)
            image = client.text_to_image(prompt, model=model_id, width=width, height=height)
            update_status("Saving generated image...")
            image.save(str(output_path))
            return output_path
        except Exception as e:
            err = str(e)
            err_lower = err.lower()

            if "402" in err or "payment required" in err_lower:
                raise ImageGenerationError(f"Hugging Face credits exhausted or payment required for model: {model_id}")
            if "401" in err or "unauthorized" in err_lower:
                raise ImageGenerationError(f"Token rejected for model: {model_id}. Check HUGGINGFACE_TOKEN.")

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
                raise ImageGenerationError(f"Image generation failed: {err[:200]}")

    raise ImageGenerationError("All HuggingFace attempts failed.")


# ──── Main generate_image dispatcher ──────────────────────────────────────

def generate_image(
    prompt: str,
    subject: str | None = None,
    style: str | None = None,
    filename: str | None = None,
    status_callback: Optional[Callable[[str], None]] = None,
    dimensions: str | None = None,
) -> Path:
    def update_status(msg: str):
        if status_callback:
            status_callback(msg)

    # Determine filename using the new structured format or fallback
    if subject and style:
        final_filename = get_unique_filename(subject, style, GENERATED_DIR)
    elif filename:
        final_filename = filename
    else:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        final_filename = f"wallpaper-{timestamp}"

    output_path = GENERATED_DIR / f"{final_filename}.png"

    # Read provider and model from config
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception:
        config = {}

    provider = (config.get("provider") or "Pollinations.ai (Free - No Key)").strip()
    model_id = (config.get("model_id") or "flux").strip()
    # Use caller-provided dimensions (from live UI), else fall back to config
    dims_str = dimensions or config.get("dimensions", "1920x1080").strip()
    dims = dims_str.split("x")
    try:
        width = int(dims[0].strip()) if len(dims) == 2 else 1920
        height = int(dims[1].strip()) if len(dims) == 2 else 1080
    except (ValueError, IndexError):
        width, height = 1920, 1080

    # Route to the correct backend
    if "Pollinations" in provider:
        return _generate_pollinations(prompt, model_id, width, height,
                                       output_path, status_callback)
    elif "Cloudflare" in provider:
        return _generate_cloudflare(prompt, model_id, width, height,
                                      output_path, status_callback)
    else:
        # Hugging Face (or any unrecognized provider falls back to HF)
        return _generate_huggingface(prompt, model_id, width, height,
                                      output_path, status_callback)
