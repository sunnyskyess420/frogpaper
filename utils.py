import json
import os
import sys
from pathlib import Path


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
                print(f"[seed_bundled_files] Could not copy {name}: {e}")


def load_json_list(path: Path) -> list:
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_json_list(path: Path, data: list) -> None:
    try:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[save_json_list] Failed to write {path}: {e}")


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
        clean_data.pop("huggingface_token", None)
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(clean_data, f, indent=2)
    except Exception as e:
        print(f"[save_config] Failed to write config: {e}")


def get_huggingface_token() -> str:
    return os.environ.get("HUGGINGFACE_TOKEN", "").strip()


def has_huggingface_token() -> bool:
    return bool(get_huggingface_token())