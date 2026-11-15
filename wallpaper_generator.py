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

class ImageGenerationCancelled(ImageGenerationError):
    """The user cancelled the generation; nothing was written."""


def _check_cancel(cancel_event) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise ImageGenerationCancelled("Generation cancelled by user.")


def _sleep_cancellable(seconds: float, cancel_event) -> None:
    """Sleep in short slices so Cancel is honoured within a quarter second."""
    import time as _time
    end = _time.time() + float(seconds)
    while True:
        _check_cancel(cancel_event)
        left = end - _time.time()
        if left <= 0:
            return
        _time.sleep(min(0.25, left))


def _read_body(response, cancel_event=None, chunk_size: int = 65536) -> bytes:
    """Read a response body in chunks so a cancel can stop the transfer."""
    chunks = []
    while True:
        _check_cancel(cancel_event)
        chunk = response.read(chunk_size)
        if not chunk:
            break
        chunks.append(chunk)
    return b"".join(chunks)


def load_token() -> str:
    token = os.getenv("HUGGINGFACE_TOKEN", "").strip()
    if not token:
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8-sig") as f:
                cfg = json.load(f)
            token = (cfg.get("huggingface_token") or "").strip()
        except Exception:
            pass
    if not token:
        raise ValueError("Missing Hugging Face token. Add one in Settings > AI Provider "
                         "(or set the HUGGINGFACE_TOKEN environment variable).")
    return token


HF_ROUTER_ROOT = "https://router.huggingface.co/hf-inference/models"
#: OpenAI-compatible Images API. This is the path that spends Inference
#: Provider credits, so paid models (FLUX) are served here rather than on the
#: free hf-inference list.
HF_OPENAI_URL = "https://router.huggingface.co/v1/images/generations"
DEFAULT_HF_MODEL = "stabilityai/stable-diffusion-3-medium-diffusers"
#: Models served by the free hf-inference list; everything else goes through
#: the paid router endpoint above.
HF_FREE_MODELS = {"stabilityai/stable-diffusion-3-medium-diffusers"}


# Models that are no longer offered by any provider map onto the one that is
# served, so a config saved with an old id keeps working. FLUX models are NOT
# in this list: they are still available, just through the paid router.
_RETIRED_HF_MODELS = {
    "stabilityai/stable-diffusion-xl-base-1.0": "stabilityai/stable-diffusion-3-medium-diffusers",
    "black-forest-labs/FLUX.1-schnell": "stabilityai/stable-diffusion-3-medium-diffusers",
    "black-forest-labs/FLUX.1-dev": "stabilityai/stable-diffusion-3-medium-diffusers",
}


def huggingface_model(model_id: str) -> str:
    """Effective model for a request: retired ids fall back to the served one."""
    model = (model_id or "").strip() or DEFAULT_HF_MODEL
    return _RETIRED_HF_MODELS.get(model, model)


def huggingface_endpoint(model_id: str) -> str:
    """URL for a Hugging Face image model.

    Hugging Face retired the legacy api-inference.huggingface.co host (it no
    longer resolves in DNS); serverless inference now goes through the router.
    """
    model = (model_id or "").strip() or "stabilityai/stable-diffusion-3-medium-diffusers"
    return f"{HF_ROUTER_ROOT}/{model}"

def _load_cloudflare_config() -> tuple:
    """Load Cloudflare API token and account ID from config.
    Returns (token, account_id)."""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8-sig") as f:
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

def save_image_bytes(output_path: Path, data: bytes, cancel_event=None) -> None:
    """Write image *data* to *output_path* atomically.

    A failed, truncated or cancelled download must never leave a 0-byte or
    HTML error body at the final ``.png`` path, where the gallery indexes it.
    The bytes are written to a ``.part`` sibling and only replace the target
    once they are complete and plausibly an image.
    """
    _check_cancel(cancel_event)
    if not data or len(data) < 1000:
        raise ImageGenerationError(
            f"Provider returned a {len(data)}-byte response, not an image.")
    output_path = Path(output_path)
    tmp = output_path.with_name(output_path.name + ".part")
    try:
        with open(tmp, "wb") as out_file:
            out_file.write(data)
            out_file.flush()
            os.fsync(out_file.fileno())
        os.replace(tmp, output_path)
    except Exception:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


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



def _load_config_value(key: str, default: str = "") -> str:
    """Load a single value from config.json."""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8-sig") as f:
            cfg = json.load(f)
        return (cfg.get(key) or "").strip()
    except Exception:
        return default

# ──── Pollinations.ai backend ─────────────────────────────────────────────

def _generate_pollinations(prompt: str, model_id: str, width: int, height: int,
                           output_path: Path, status_callback=None, cancel_event=None) -> Path:
    """Generate image via Pollinations.ai (free, no API key needed)."""
    def update_status(msg):
        if status_callback:
            status_callback(msg)
    _check_cancel(cancel_event)

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
                save_image_bytes(output_path, _read_body(response, cancel_event), cancel_event)

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
                    _sleep_cancellable(wait, cancel_event)
                    continue
                raise ImageGenerationError("Pollinations.ai rate limit reached. Wait a minute and try again.")
            elif e.code == 503:
                if attempt < max_attempts:
                    wait = 15
                    update_status(f"Pollinations.ai overloaded (503). Waiting {wait}s...")
                    _sleep_cancellable(wait, cancel_event)
                    continue
                raise ImageGenerationError("Pollinations.ai is temporarily unavailable.")
            elif e.code in (401, 403):
                raise ImageGenerationError(
                    f"Pollinations rejected the request (HTTP {e.code}). "
                    "The selected model may need a token or be unavailable right now.")
            elif e.code == 402:
                raise ImageGenerationError(
                    "Pollinations has no credits left for this model (HTTP 402). "
                    "Pick the free 'flux' model, wait for the quota to reset, or "
                    "switch provider in Settings > Generation.")
            elif e.code == 404:
                raise ImageGenerationError(
                    "Pollinations does not recognise that model (HTTP 404). "
                    "Choose another model in Settings > Generation.")
            else:
                raise ImageGenerationError(f"Pollinations.ai HTTP error: {e.code}")
        except urllib.error.URLError as e:
            err_str = str(e)
            if attempt < max_attempts:
                update_status(f"Network error. Waiting 15s... ({err_str[:50]})")
                _sleep_cancellable(15, cancel_event)
                continue
            if "getaddrinfo" in err_str or "resolve" in err_str.lower():
                raise ImageGenerationError(
                    "Could not reach Pollinations.ai — the server may be down or your internet connection is offline. "
                    "Try again in a few minutes, or switch to a different provider in Settings.")
            raise ImageGenerationError(
                f"Could not connect to Pollinations.ai: {err_str[:100]}. "
                "Check your internet connection and try again.")
        except ImageGenerationError:
            raise
        except Exception as e:
            if attempt < max_attempts:
                update_status(f"Error occurred. Retrying in 10s...")
                _sleep_cancellable(10, cancel_event)
                continue
            raise ImageGenerationError(f"Pollinations.ai failed: {str(e)[:200]}")

    raise ImageGenerationError("All Pollinations.ai attempts failed.")


# ──── Cloudflare Workers AI backend ───────────────────────────────────────

def _build_cloudflare_url(base_url: str, account_id: str, model: str) -> str:
    try:
        # Minimal path validation
        if "/../" in base_url or re.search(r"/%2e%2e/", base_url, re.IGNORECASE):
            raise ValueError("Invalid path")
        
        parsed = urllib.parse.urlparse(base_url)
        
        # Validate path parameters
        if not re.fullmatch(r"[A-Za-z0-9_-]+", account_id):
            raise ValueError("Invalid parameter")
        if not re.fullmatch(r"[@A-Za-z0-9_/-]+", model):
            raise ValueError("Invalid parameter")
        
        # Rebuild path from fixed literals + validated segments
        parsed = parsed._replace(path=f"/client/v4/accounts/{account_id}/ai/run/{model}")
        
        return urllib.parse.urlunparse(parsed)
    except Exception:
        raise ValueError("Invalid URL")

def _generate_cloudflare(prompt: str, model_id: str, width: int, height: int,
                          output_path: Path, status_callback=None, cancel_event=None) -> Path:
    """Generate image via Cloudflare Workers AI (free tier: 10,000 neurons/day)."""
    def update_status(msg):
        if status_callback:
            status_callback(msg)
    _check_cancel(cancel_event)

    token, account_id = _load_cloudflare_config()

    # Cloudflare Workers AI REST API requires account ID in the URL path
    model = model_id if model_id else "@cf/black-forest-labs/flux-1-schnell"
    api_url = _build_cloudflare_url("https://api.cloudflare.com", account_id, model)

    # Cloudflare FLUX.1-schnell only outputs 1024x1024
    # The universal resize in generate_image() handles this after generation
    payload_dict = {"prompt": prompt}
    payload = json.dumps(payload_dict).encode("utf-8")

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
                result_bytes = _read_body(response, cancel_event)

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
            save_image_bytes(output_path, img_bytes, cancel_event)

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
                    # Detect unsupported parameters (e.g. width/height not allowed for this model)
                    if "not allowed" in cf_msg.lower() or "additional" in cf_msg.lower() or "unevaluated" in cf_msg.lower():
                        raise ImageGenerationError(
                            "This Cloudflare model does not support custom dimensions. "
                            "Try a different model in Settings, or switch to HuggingFace / Pollinations.ai.")
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
                    _sleep_cancellable(20, cancel_event)
                    continue
                raise ImageGenerationError("Cloudflare rate limit reached.")
            elif e.code >= 500:
                if attempt < max_attempts:
                    update_status(f"Cloudflare is temporarily busy (HTTP {e.code}). Retrying in 15s...")
                    _sleep_cancellable(15, cancel_event)
                    continue
                raise ImageGenerationError(
                    f"Cloudflare's servers are temporarily overloaded (HTTP {e.code}). "
                    f"This is not a problem with your app or settings — Cloudflare's AI service "
                    f"is just having a moment. Try again in a few minutes, or switch to a different provider.")
            else:
                raise ImageGenerationError(
                    f"Cloudflare HTTP {e.code}: {err_body[:200]}")
        except urllib.error.URLError as e:
            err_str = str(e)
            if attempt < max_attempts:
                update_status(f"Cloudflare network error. Waiting 15s...")
                _sleep_cancellable(15, cancel_event)
                continue
            if "getaddrinfo" in err_str or "resolve" in err_str.lower():
                raise ImageGenerationError(
                    "Could not reach Cloudflare — the server may be down or your internet connection is offline. "
                    "Try again in a few minutes, or switch to a different provider in Settings.")
            raise ImageGenerationError(
                f"Could not connect to Cloudflare: {err_str[:100]}. "
                "Check your internet connection and try again.")
        except ImageGenerationError:
            raise
        except Exception as e:
            if attempt < max_attempts:
                update_status(f"Error occurred. Retrying in 10s...")
                _sleep_cancellable(10, cancel_event)
                continue
            raise ImageGenerationError(f"Cloudflare generation failed: {str(e)[:200]}")

    raise ImageGenerationError("All Cloudflare attempts failed.")


# ──── Hugging Face backend ───────────────────────────────────────────────

HF_PERMISSIONS_HINT = (
    "Your Hugging Face token can sign in but is not allowed to call Inference Providers. "
    "Create a token with the 'Make calls to Inference Providers' permission "
    "(or a classic Read token), then save it in Settings > AI Provider."
)


def _is_permission_error(body: str) -> bool:
    text = (body or "").lower()
    return any(marker in text for marker in
               ("sufficient permissions", "permission", "not authorized", "forbidden"))


def _round_to_multiple(value: int, step: int = 16, minimum: int = 256) -> int:
    """Round *value* down to a multiple of *step* (never below *minimum*).

    Hugging Face rejects sizes that are not multiples of 16 (1080 -> HTTP 400);
    the post-generation resize restores the requested dimensions afterwards.
    """
    try:
        number = int(value)
    except (TypeError, ValueError):
        return minimum
    rounded = (number // step) * step
    return max(minimum, rounded)


def _looks_like_dropped_connection(exc: Exception) -> bool:
    """True for the server hanging up mid-request (RemoteDisconnected etc.)."""
    if isinstance(exc, (ConnectionResetError, ConnectionAbortedError, TimeoutError)):
        return True
    text = f"{type(exc).__name__} {exc}".lower()
    return any(marker in text for marker in
               ("remote end closed", "remotedisconnected", "connection reset",
                "connection aborted", "timed out", "timeout"))


def huggingface_square_size(width, height) -> int:
    """Side length for a Hugging Face request: always square.

    Its free queue runs 30s+ on a wide image and often hangs up mid-transfer;
    a square request is faster and reliable, and it avoids squashing the
    result into a 16:9 wallpaper afterwards.
    """
    try:
        side = min(int(width), int(height))
    except (TypeError, ValueError):
        side = 1024
    return _round_to_multiple(side)


def _generate_huggingface_router(prompt: str, model: str, token: str, output_path: Path,
                                 update_status, cancel_event=None) -> Path:
    """Image via the OpenAI-compatible router - the path that spends credits.

    Free-tier models go through hf-inference instead; this one is what serves
    FLUX and friends to a paying account, and it answers in seconds rather than
    the minutes the free queue can take.
    """
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "n": 1,
        "response_format": "b64_json",
    }).encode("utf-8")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    attempts = 2
    started = time.monotonic()
    data = None
    for attempt in range(1, attempts + 1):
        update_status(f"Requesting {model.split('/')[-1]} (attempt {attempt}/{attempts})...")
        req = urllib.request.Request(HF_OPENAI_URL, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")[:200]
            except Exception:
                pass
            if e.code in (401, 403):
                if _is_permission_error(body):
                    raise ImageGenerationError(HF_PERMISSIONS_HINT)
                raise ImageGenerationError(
                    "Hugging Face rejected the token. Check it in Settings > AI Provider.")
            if e.code == 402:
                raise ImageGenerationError(
                    f"Hugging Face credits are exhausted for {model}. Top up at huggingface.co/settings/billing, "
                    "or pick Stable Diffusion 3 Medium (free tier) in Settings.")
            if e.code == 404:
                raise ImageGenerationError(
                    f"Hugging Face does not serve {model} any more - its router lists no "
                    f"image models at all. Pick Stable Diffusion 3 Medium in Settings, "
                    f"or use another provider.")
            if e.code == 429 or e.code >= 500:
                if attempt < attempts:
                    update_status(f"Hugging Face busy (HTTP {e.code}). Retrying once...")
                    _sleep_cancellable(5, cancel_event)
                    continue
            raise ImageGenerationError(f"HuggingFace HTTP {e.code}: {body}".strip())
        except urllib.error.URLError as e:
            if attempt < attempts:
                _sleep_cancellable(5, cancel_event)
                continue
            raise ImageGenerationError(f"Could not reach Hugging Face: {str(e)[:120]}")

    elapsed = time.monotonic() - started
    items = (data or {}).get("data") or []
    if not items:
        raise ImageGenerationError(
            f"Hugging Face returned no image data after {elapsed:.0f}s. Try again, or another model.")

    entry = items[0] if isinstance(items[0], dict) else {}
    update_status(f"Saving generated image ({elapsed:.0f}s)...")
    if entry.get("b64_json"):
        import base64
        image_bytes = base64.b64decode(entry["b64_json"])
    elif entry.get("url"):
        req = urllib.request.Request(entry["url"], headers={"User-Agent": "FrogPaper/1.9"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            image_bytes = _read_body(resp, cancel_event)
    else:
        raise ImageGenerationError("Hugging Face returned neither image data nor a URL.")

    save_image_bytes(output_path, image_bytes, cancel_event)
    return output_path


def _generate_huggingface(prompt: str, model_id: str, width: int, height: int,
                            output_path: Path, status_callback=None, cancel_event=None) -> Path:
    """Generate image via Hugging Face Inference API (raw HTTP, no PIL needed for decoding)."""
    def update_status(msg):
        if status_callback:
            status_callback(msg)
    _check_cancel(cancel_event)

    try:
        token = load_token()
    except ValueError as e:
        raise ImageGenerationError(str(e))

    requested = (model_id or "").strip()
    model = huggingface_model(requested)
    if requested and model != requested:
        update_status(f"{requested} is no longer served - using {model.split('/')[-1]}")

    # Paying accounts get the credit-backed router (fast, serves FLUX); the
    # free list only has one model and can queue for minutes.
    if model not in HF_FREE_MODELS:
        return _generate_huggingface_router(prompt, model, token, output_path,
                                            update_status, cancel_event)

    api_url = huggingface_endpoint(model)

    payload = json.dumps({
        "inputs": prompt,
        "parameters": {
            "width": _round_to_multiple(width),
            "height": _round_to_multiple(height),
        }
    }).encode("utf-8")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    max_attempts = 3
    started = time.monotonic()
    for attempt in range(1, max_attempts + 1):
        try:
            update_status(f"Requesting HuggingFace (Attempt {attempt}/{max_attempts})...")
            req = urllib.request.Request(api_url, data=payload, headers=headers, method="POST")

            # The free queue can take minutes on a large image; 120s cut off
            # requests that would have completed.
            with urllib.request.urlopen(req, timeout=300) as response:
                if response.status != 200:
                    err_body = response.read().decode("utf-8", errors="replace")[:200]
                    if response.status == 401:
                        raise ImageGenerationError(f"Token rejected for model: {model}. Check HUGGINGFACE_TOKEN.")
                    if response.status == 402:
                        raise ImageGenerationError(f"HuggingFace credits exhausted or payment required for model: {model}")
                    if response.status == 429:
                        raise ImageGenerationError("rate_limited")
                    if response.status == 503:
                        raise ImageGenerationError("model_loading")
                    raise ImageGenerationError(f"HuggingFace HTTP {response.status}: {err_body}")

                update_status("Saving generated image...")
                save_image_bytes(output_path, _read_body(response, cancel_event), cancel_event)

            # Verify it's a real image
            if output_path.stat().st_size < 1000:
                raise ImageGenerationError("HuggingFace returned too-small response. Try again.")

            return output_path

        except ImageGenerationError as e:
            err_lower = str(e).lower()
            if "rate_limited" in err_lower and attempt < max_attempts:
                update_status("Rate limited (429). Waiting 30s to retry...")
                _sleep_cancellable(30, cancel_event)
                continue
            if "model_loading" in err_lower and attempt < max_attempts:
                update_status("Model is loading (503). Waiting 20s to retry...")
                _sleep_cancellable(20, cancel_event)
                continue
            raise

        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")[:160]
            except Exception:
                pass
            if e.code in (401, 403):
                if _is_permission_error(body):
                    raise ImageGenerationError(HF_PERMISSIONS_HINT)
                raise ImageGenerationError(
                    f"Hugging Face rejected the token for {model}. Check it in Settings > AI Provider "
                    f"(fine-grained tokens need 'Make calls to Inference Providers'). {body}".strip())
            if e.code == 402:
                raise ImageGenerationError(
                    f"Hugging Face credits exhausted for {model}. Switch to FLUX.1-schnell in Settings.")
            if e.code == 404:
                raise ImageGenerationError(
                    f"{model} is not served by Hugging Face's free inference any more. "
                    f"Pick another model in Settings, or switch to Pollinations.ai (free, no key).")
            if e.code == 429 and attempt < max_attempts:
                update_status("Rate limited (429). Waiting 30s...")
                _sleep_cancellable(30, cancel_event)
                continue
            if e.code == 503 and attempt < max_attempts:
                update_status("Model loading (503). Waiting 20s...")
                _sleep_cancellable(20, cancel_event)
                continue
            raise ImageGenerationError(f"HuggingFace HTTP {e.code}: {body}".strip())

        except urllib.error.URLError as e:
            err_str = str(e)
            if attempt < max_attempts:
                update_status(f"Network error. Retrying in 15s...")
                _sleep_cancellable(15, cancel_event)
                continue
            if "getaddrinfo" in err_str or "resolve" in err_str.lower():
                raise ImageGenerationError(
                    "Cannot connect to HuggingFace right now. This is usually a HuggingFace server outage, "
                    "not a problem with your app or internet. Check status.huggingface.co for updates. "
                    "You can also switch to Pollinations.ai (free, no key needed) in Settings as a backup.")
            raise ImageGenerationError(
                f"Could not connect to HuggingFace: {err_str[:100]}. "
                "Check your internet connection and try again.")

        except Exception as e:
            dropped = _looks_like_dropped_connection(e)
            if attempt < max_attempts:
                update_status("Connection dropped. Retrying in 10s..." if dropped
                              else "Error occurred. Retrying in 10s...")
                _sleep_cancellable(10, cancel_event)
                continue
            elapsed = time.monotonic() - started
            if dropped:
                raise ImageGenerationError(
                    f"Hugging Face closed the connection after {elapsed:.0f}s without returning an image. "
                    f"Its free queue does this on large requests - try 1024x1024, retry later, "
                    f"or switch to Pollinations.ai (free, no key) in Settings.")
            raise ImageGenerationError(f"Image generation failed after {elapsed:.0f}s: {str(e)[:200]}")

    raise ImageGenerationError("All HuggingFace attempts failed.")




# ──── Prodia backend ───────────────────────────────────────────────────

def _generate_prodia(prompt: str, model_id: str, width: int, height: int,
                       output_path: Path, status_callback=None, cancel_event=None) -> Path:
    """Generate image via Prodia v2 API (inference.prodia.com)."""
    def update_status(msg):
        if status_callback:
            status_callback(msg)
    _check_cancel(cancel_event)

    prodia_key = _load_config_value("prodia_key")
    if not prodia_key:
        raise ImageGenerationError(
            "Prodia requires an API key. Get one free (1000 calls free) at app.prodia.com/api "
            "and set it in Settings.")

    # model_id format: "inference.flux-fast.schnell.txt2img.v2"
    model = model_id if model_id else "inference.flux-fast.schnell.txt2img.v2"

    api_url = "https://inference.prodia.com/v2/job"

    payload_dict = {
        "type": model,
        "config": {
            "prompt": prompt,
            "width": min(width, 1536),
            "height": min(height, 1536),
        }
    }
    payload = json.dumps(payload_dict).encode("utf-8")

    headers = {
        "Authorization": f"Bearer {prodia_key}",
        "Content-Type": "application/json",
    }

    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            update_status(f"Requesting Prodia (attempt {attempt}/{max_attempts})...")
            req = urllib.request.Request(api_url, data=payload, headers=headers, method="POST")

            with urllib.request.urlopen(req, timeout=180) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            # v2 is synchronous - result should contain the output directly
            # Extract image URL from result
            image_url = None

            # Try output.images[].url
            output = result.get("output", {})
            if isinstance(output, dict):
                images = output.get("images", [])
                if images and isinstance(images, list):
                    image_url = images[0].get("url", "") if isinstance(images[0], dict) else str(images[0])
                if not image_url:
                    image_url = output.get("url", "")
            elif isinstance(output, str):
                image_url = output

            # Try top-level imageUrl
            if not image_url:
                image_url = result.get("imageUrl", "")

            if not image_url:
                # Check for error
                error = result.get("error", "")
                status_val = result.get("status", "")
                if status_val == "failed":
                    raise ImageGenerationError(f"Prodia generation failed: {error or 'Unknown error'}")
                raise ImageGenerationError("Prodia returned no image. The model may not support text-to-image.")

            # Download the image
            update_status("Downloading image from Prodia...")
            dl_req = urllib.request.Request(image_url, headers={"User-Agent": "FrogPaper/1.0"})
            with urllib.request.urlopen(dl_req, timeout=120) as img_resp:
                img_data = img_resp.read()

            if len(img_data) < 1000:
                raise ImageGenerationError("Prodia returned too-small response. Try again.")

            update_status("Saving generated image...")
            save_image_bytes(output_path, img_data, cancel_event)

            return output_path

        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode("utf-8", errors="replace")[:200]
            except Exception:
                pass
            if e.code == 401:
                raise ImageGenerationError("Prodia API key rejected. Check your Prodia API Key in Settings.")
            elif e.code == 402:
                raise ImageGenerationError("Prodia: API access not enabled or credits exhausted. Check app.prodia.com.")
            elif e.code == 429:
                if attempt < max_attempts:
                    update_status("Prodia rate limited (429). Waiting 20s...")
                    _sleep_cancellable(20, cancel_event)
                    continue
                raise ImageGenerationError("Prodia rate limit reached. Wait a minute and try again.")
            elif e.code >= 500:
                if attempt < max_attempts:
                    update_status(f"Prodia is temporarily busy (HTTP {e.code}). Retrying in 15s...")
                    _sleep_cancellable(15, cancel_event)
                    continue
                raise ImageGenerationError(
                    f"Prodia's servers are temporarily overloaded (HTTP {e.code}). "
                    f"This is not a problem with your app or settings — Prodia is just having a moment. "
                    f"Try again in a few minutes, or switch to a different provider.")
            else:
                raise ImageGenerationError(f"Prodia HTTP {e.code}: {err_body}")
        except urllib.error.URLError as e:
            err_str = str(e)
            if attempt < max_attempts:
                update_status("Prodia network error. Waiting 15s...")
                _sleep_cancellable(15, cancel_event)
                continue
            if "getaddrinfo" in err_str or "resolve" in err_str.lower():
                raise ImageGenerationError(
                    "Could not reach Prodia — the server may be down or your internet is offline. "
                    "Try again in a few minutes, or switch to a different provider in Settings.")
            raise ImageGenerationError(
                f"Could not connect to Prodia: {err_str[:100]}. "
                "Check your internet connection and try again.")
        except ImageGenerationError:
            raise
        except Exception as e:
            if attempt < max_attempts:
                update_status("Error occurred. Retrying in 10s...")
                _sleep_cancellable(10, cancel_event)
                continue
            raise ImageGenerationError(f"Prodia generation failed: {str(e)[:200]}")

    raise ImageGenerationError("All Prodia attempts failed.")


# ──── Replicate backend ─────────────────────────────────────────────────

def _generate_replicate(prompt: str, model_id: str, width: int, height: int,
                          output_path: Path, status_callback=None, cancel_event=None) -> Path:
    """Generate image via Replicate (pay-per-image, very reliable)."""
    def update_status(msg):
        if status_callback:
            status_callback(msg)
    _check_cancel(cancel_event)

    token = _load_config_value("replicate_token")
    if not token:
        raise ImageGenerationError(
            "Replicate requires an API token. Get one free at replicate.com/account/api-tokens "
            "and set it in Settings.")

    # Model format: "owner/model" e.g. "black-forest-labs/flux-schnell"
    model = model_id if model_id else "black-forest-labs/flux-schnell"

    # Replicate API: use model-based endpoint (no version hash needed)
    api_url = f"https://api.replicate.com/v1/models/{model}/predictions"

    payload_dict = {
        "input": {
            "prompt": prompt,
            "width": min(width, 1440),
            "height": min(height, 1440),
            "num_outputs": 1,
        }
    }
    payload = json.dumps(payload_dict).encode("utf-8")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            update_status(f"Requesting Replicate (attempt {attempt}/{max_attempts})...")

            req = urllib.request.Request(api_url, data=payload, headers=headers, method="POST")

            # No "Prefer: wait" — POST returns immediately (~1s), then we poll.
            # This is faster than Prefer: wait which holds the connection open ~60s.
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            status = result.get("status", "")

            # Always poll — even if status looks done, grab the get URL
            get_url = result.get("urls", {}).get("get", "")
            if not get_url and result.get("id"):
                get_url = f"https://api.replicate.com/v1/predictions/{result['id']}"

            if get_url:
                poll_headers = {"Authorization": f"Bearer {token}"}
                poll_req = urllib.request.Request(get_url, headers=poll_headers)

                # If already completed from the POST response, skip polling
                if status not in ("succeeded", "completed"):
                    update_status("Replicate is generating...")
                    for i in range(90):  # ~90 seconds max at 1s intervals
                        _sleep_cancellable(1, cancel_event)
                        with urllib.request.urlopen(poll_req, timeout=15) as poll_resp:
                            result = json.loads(poll_resp.read().decode("utf-8"))
                        status = result.get("status", "")
                        if status in ("succeeded", "completed"):
                            break
                        if status in ("failed", "canceled"):
                            error_msg = result.get("error", "Unknown error")
                            raise ImageGenerationError(f"Replicate generation failed: {error_msg}")
                        if i % 5 == 0:
                            update_status(f"Replicate is generating... ({i + 1}s)")
                    else:
                        raise ImageGenerationError("Replicate generation timed out. Try again.")

            # Extract image URL from output
            output = result.get("output", [])
            if isinstance(output, list) and output:
                image_url = output[0]
            elif isinstance(output, str) and output:
                image_url = output
            else:
                raise ImageGenerationError("Replicate returned no image. Try again.")

            # Download the image
            update_status("Downloading image from Replicate...")
            dl_req = urllib.request.Request(image_url, headers={"User-Agent": "FrogPaper/1.0"})
            with urllib.request.urlopen(dl_req, timeout=120) as img_resp:
                img_data = img_resp.read()

            if len(img_data) < 1000:
                raise ImageGenerationError("Replicate returned too-small response. Try again.")

            update_status("Saving generated image...")
            save_image_bytes(output_path, img_data, cancel_event)

            return output_path

        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode("utf-8", errors="replace")[:200]
            except Exception:
                pass
            if e.code == 401:
                raise ImageGenerationError("Replicate token rejected. Check your Replicate API Token in Settings.")
            elif e.code == 402:
                raise ImageGenerationError("Replicate credits exhausted. Add billing at replicate.com/account/billing.")
            elif e.code == 422:
                # Try to extract error detail
                try:
                    err_json = json.loads(err_body)
                    detail = err_json.get("detail", err_body)
                    raise ImageGenerationError(f"Replicate: {detail}")
                except ImageGenerationError:
                    raise
                except Exception:
                    raise ImageGenerationError(f"Replicate request error: {err_body}")
            elif e.code == 429:
                if attempt < max_attempts:
                    update_status("Replicate rate limited (429). Waiting 20s...")
                    _sleep_cancellable(20, cancel_event)
                    continue
                raise ImageGenerationError("Replicate rate limit reached. Wait a minute and try again.")
            elif e.code >= 500:
                if attempt < max_attempts:
                    update_status(f"Replicate is temporarily busy (HTTP {e.code}). Retrying in 15s...")
                    _sleep_cancellable(15, cancel_event)
                    continue
                raise ImageGenerationError(
                    f"Replicate's servers are temporarily overloaded (HTTP {e.code}). "
                    f"This is not a problem with your app or settings — Replicate is just having a moment. "
                    f"Try again in a few minutes, or check status.replicate.com, or switch to a different provider.")
            else:
                raise ImageGenerationError(f"Replicate HTTP {e.code}: {err_body}")
        except urllib.error.URLError as e:
            err_str = str(e)
            if attempt < max_attempts:
                update_status("Replicate network error. Waiting 15s...")
                _sleep_cancellable(15, cancel_event)
                continue
            if "getaddrinfo" in err_str or "resolve" in err_str.lower():
                raise ImageGenerationError(
                    "Could not reach Replicate — the server may be down or your internet is offline. "
                    "Try again in a few minutes, or switch to a different provider in Settings.")
            raise ImageGenerationError(
                f"Could not connect to Replicate: {err_str[:100]}. "
                "Check your internet connection and try again.")
        except ImageGenerationError:
            raise
        except Exception as e:
            if attempt < max_attempts:
                update_status("Error occurred. Retrying in 10s...")
                _sleep_cancellable(10, cancel_event)
                continue
            raise ImageGenerationError(f"Replicate generation failed: {str(e)[:200]}")

    raise ImageGenerationError("All Replicate attempts failed.")


# ──── Fal.ai backend ────────────────────────────────────────────────────

def _generate_fal(prompt: str, model_id: str, width: int, height: int,
                    output_path: Path, status_callback=None, cancel_event=None) -> Path:
    """Generate image via Fal.ai (fast inference, pay-per-use)."""
    def update_status(msg):
        if status_callback:
            status_callback(msg)
    _check_cancel(cancel_event)

    token = _load_config_value("fal_key")
    if not token:
        raise ImageGenerationError(
            "Fal.ai requires an API key. Get one free at fal.ai/dashboard/keys "
            "and set it in Settings.")

    # Fal model format: "fal-ai/flux-schnell" etc.
    model = model_id if model_id else "fal-ai/flux/schnell"

    api_url = f"https://queue.fal.run/{model}"

    payload_dict = {
        "prompt": prompt,
        "image_size": {"width": min(width, 1456), "height": min(height, 1456)},
        "num_images": 1,
    }
    payload = json.dumps(payload_dict).encode("utf-8")

    headers = {
        "Authorization": f"Key {token}",
        "Content-Type": "application/json",
    }

    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            update_status(f"Requesting Fal.ai (attempt {attempt}/{max_attempts})...")

            req = urllib.request.Request(api_url, data=payload, headers=headers, method="POST")

            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            # Fal returns a request_id for queued jobs
            request_id = result.get("request_id", "")
            status_url = result.get("status_url", f"https://queue.fal.run/{model}/requests/{request_id}/status")

            if request_id and "completed" not in str(result.get("status", "")):
                update_status("Generating image on Fal.ai...")
                poll_req = urllib.request.Request(status_url, headers=headers)

                for i in range(60):  # ~120 seconds max
                    _sleep_cancellable(2, cancel_event)
                    with urllib.request.urlopen(poll_req, timeout=30) as poll_resp:
                        job = json.loads(poll_resp.read().decode("utf-8"))

                    fal_status = job.get("status", "")
                    if fal_status == "COMPLETED":
                        # Get the image URL from the response
                        result = job
                        break
                    elif fal_status == "FAILED":
                        error_msg = job.get("error", "Unknown error")
                        raise ImageGenerationError(f"Fal.ai generation failed: {error_msg}")
                    else:
                        if i % 5 == 0:
                            update_status(f"Fal.ai is generating... ({i * 2}s)")
                else:
                    raise ImageGenerationError("Fal.ai generation timed out. Try again.")

            # Extract image URL
            image_url = None
            # Try common response structures
            images = result.get("images", [])
            if images and isinstance(images, list):
                image_url = images[0].get("url", "") if isinstance(images[0], dict) else str(images[0])
            if not image_url:
                output = result.get("output", {})
                if isinstance(output, dict):
                    image_url = output.get("url", "")
                    if not image_url:
                        imgs = output.get("images", [])
                        if imgs and isinstance(imgs, list):
                            image_url = imgs[0].get("url", "") if isinstance(imgs[0], dict) else str(imgs[0])
            if not image_url:
                image_url = result.get("image", {}).get("url", "")

            if not image_url:
                raise ImageGenerationError("Fal.ai returned no image URL. Try again.")

            # Download the image
            update_status("Downloading image from Fal.ai...")
            dl_req = urllib.request.Request(image_url, headers={"User-Agent": "FrogPaper/1.0"})
            with urllib.request.urlopen(dl_req, timeout=120) as img_resp:
                img_data = img_resp.read()

            if len(img_data) < 1000:
                raise ImageGenerationError("Fal.ai returned too-small response. Try again.")

            update_status("Saving generated image...")
            save_image_bytes(output_path, img_data, cancel_event)

            return output_path

        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode("utf-8", errors="replace")[:200]
            except Exception:
                pass
            if e.code == 401:
                raise ImageGenerationError("Fal.ai key rejected. Check your Fal.ai API Key in Settings.")
            elif e.code == 402:
                raise ImageGenerationError("Fal.ai credits exhausted. Check your account at fal.ai.")
            elif e.code == 429:
                if attempt < max_attempts:
                    update_status("Fal.ai rate limited (429). Waiting 20s...")
                    _sleep_cancellable(20, cancel_event)
                    continue
                raise ImageGenerationError("Fal.ai rate limit reached. Wait a minute and try again.")
            elif e.code >= 500:
                if attempt < max_attempts:
                    update_status(f"Fal.ai is temporarily busy (HTTP {e.code}). Retrying in 15s...")
                    _sleep_cancellable(15, cancel_event)
                    continue
                raise ImageGenerationError(
                    f"Fal.ai's servers are temporarily overloaded (HTTP {e.code}). "
                    f"This is not a problem with your app or settings — Fal.ai is just having a moment. "
                    f"Try again in a few minutes, or switch to a different provider.")
            else:
                raise ImageGenerationError(f"Fal.ai HTTP {e.code}: {err_body}")
        except urllib.error.URLError as e:
            err_str = str(e)
            if attempt < max_attempts:
                update_status("Fal.ai network error. Waiting 15s...")
                _sleep_cancellable(15, cancel_event)
                continue
            if "getaddrinfo" in err_str or "resolve" in err_str.lower():
                raise ImageGenerationError(
                    "Could not reach Fal.ai — the server may be down or your internet is offline. "
                    "Try again in a few minutes, or switch to a different provider in Settings.")
            raise ImageGenerationError(
                f"Could not connect to Fal.ai: {err_str[:100]}. "
                "Check your internet connection and try again.")
        except ImageGenerationError:
            raise
        except Exception as e:
            if attempt < max_attempts:
                update_status("Error occurred. Retrying in 10s...")
                _sleep_cancellable(10, cancel_event)
                continue
            raise ImageGenerationError(f"Fal.ai generation failed: {str(e)[:200]}")

    raise ImageGenerationError("All Fal.ai attempts failed.")

# ──── Main generate_image dispatcher ──────────────────────────────────────

def strip_image_extension(name: str) -> str:
    """Drop a trailing image extension so 'x.png' does not become 'x.png.png'.

    Callers pass filenames that already end in .png; generate_image appends the
    extension itself, so the double-extension only showed up when the style was
    blank (the subject+style branch ignores the passed filename).
    """
    text = str(name or "")
    for ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
        if text.lower().endswith(ext):
            return text[: -len(ext)]
    return text


def generate_image(
    prompt: str,
    subject: str | None = None,
    style: str | None = None,
    filename: str | None = None,
    status_callback: Optional[Callable[[str], None]] = None,
    dimensions: str | None = None,
    cancel_event=None,
) -> Path:
    def update_status(msg: str):
        if status_callback:
            status_callback(msg)

    # Determine filename using the new structured format or fallback
    if subject and style:
        final_filename = get_unique_filename(subject, style, GENERATED_DIR)
    elif filename:
        final_filename = strip_image_extension(filename)
    else:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        final_filename = f"wallpaper-{timestamp}"

    output_path = GENERATED_DIR / f"{final_filename}.png"

    # Read provider and model from config
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8-sig") as f:
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

    # Hugging Face generates square, always: see huggingface_square_size().
    if "Hugging Face" in provider:
        side = huggingface_square_size(width, height)
        width = height = side

    # Route to the correct backend
    result_path = None
    if "Pollinations" in provider:
        result_path = _generate_pollinations(prompt, model_id, width, height,
                                               output_path, status_callback, cancel_event)
    elif "Cloudflare" in provider:
        result_path = _generate_cloudflare(prompt, model_id, width, height,
                                              output_path, status_callback, cancel_event)
    elif "Prodia" in provider:
        result_path = _generate_prodia(prompt, model_id, width, height,
                                          output_path, status_callback, cancel_event)
    elif "Replicate" in provider:
        result_path = _generate_replicate(prompt, model_id, width, height,
                                             output_path, status_callback, cancel_event)
    elif "Fal.ai" in provider or "Fal" in provider:
        result_path = _generate_fal(prompt, model_id, width, height,
                                       output_path, status_callback, cancel_event)
    else:
        # Hugging Face (or any unrecognized provider falls back to HF)
        result_path = _generate_huggingface(prompt, model_id, width, height,
                                              output_path, status_callback, cancel_event)

    # Universal post-generation resize safety net
    # Many providers (Cloudflare FLUX, Replicate FLUX, etc.) only output 1024x1024
    # and ignore width/height params. This ensures the final image matches the
    # user's chosen resolution regardless of what the backend returned.
    if result_path and result_path.exists():
        try:
            from PIL import Image as PILImage
            img = PILImage.open(result_path)
            actual_w, actual_h = img.size
            if actual_w != width or actual_h != height:
                update_status(f"Resizing from {actual_w}x{actual_h} to {width}x{height}...")
                img = img.resize((width, height), PILImage.LANCZOS)
                img.save(result_path)
        except ImportError:
            pass  # Pillow not available, return as-is
        except Exception:
            pass  # If resize fails, return the original image

    return result_path
