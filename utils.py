import json
import os
import sys
import tempfile
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def get_app_dir() -> Path:
    """Return the directory for user-writable data (wallpapers, config, logs).
    When frozen by PyInstaller (--onefile), __file__ points into a temp extraction
    dir that is deleted on exit.  We use sys.executable's parent instead so that
    all user-facing folders sit next to the EXE."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def get_bundle_dir() -> Path:
    """Return the directory for read-only assets bundled inside the EXE.
    When frozen by PyInstaller, bundled files land in sys._MEIPASS (the temp
    extraction dir).  When running as plain Python they sit beside __file__."""
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent


BASE_DIR = get_app_dir()
CONFIG_FILE = BASE_DIR / "config.json"

_BUNDLED_DATA_FILES = [
    "keywords.json",
    "negative_presets.json",
    "presets.json",
    "recipes.json",
    "templates.json",
    "prompt_library.json",
]


def seed_bundled_files() -> None:
    """Copy default data files from the PyInstaller bundle to the app data dir
    (beside the EXE) if they don't already exist there.  This runs once on
    first launch so the app can read and write them as normal user files."""
    import shutil
    bundle = get_bundle_dir()
    app = get_app_dir()
    for name in _BUNDLED_DATA_FILES:
        src = bundle / name
        dst = app / name
        if src.exists() and not dst.exists():
            try:
                shutil.copy2(src, dst)
            except Exception as e:
                logger.warning("Could not copy bundled file %s: %s", name, e)


def load_json_list(path: Path) -> list:
    base_real = os.path.realpath(BASE_DIR)
    target_real = os.path.realpath(path)
    if os.path.commonpath([base_real, target_real]) != base_real:
        raise Exception("Invalid file path")
    if not path.exists():
        return []
    try:
        with open(target_real, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def atomic_write_json(path: Path, data, indent: int = 2, ensure_ascii: bool = False) -> None:
    """Write JSON atomically using temp file + os.replace to prevent corruption."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = None
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix='.tmp')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, str(path))
    except Exception:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        raise


def save_json_list(path: Path, data: list) -> None:
    try:
        atomic_write_json(path, data, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error("Failed to write %s: %s", path, e)


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_config(data: dict) -> None:
    try:
        clean_data = dict(data or {})
        atomic_write_json(CONFIG_FILE, clean_data, indent=2)
    except Exception as e:
        logger.error("Failed to write config: %s", e)


def get_huggingface_token() -> str:
    # Priority 1: environment variable
    token = os.environ.get("HUGGINGFACE_TOKEN", "").strip()
    if token:
        return token
    # Priority 2: OS credential manager via keyring
    try:
        import keyring
        token = (keyring.get_password("FrogPaper", "huggingface_token") or "").strip()
        if token:
            return token
    except ImportError:
        pass  # keyring not installed — fall through to config
    except Exception:
        pass  # keyring backend error — fall through to config
    # Priority 3: config.json (plaintext fallback)
    try:
        config = load_config()
        token = (config.get("huggingface_token") or "").strip()
        return token
    except Exception:
        return ""


def has_huggingface_token() -> bool:
    return bool(get_huggingface_token())