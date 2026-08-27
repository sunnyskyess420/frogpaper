import json
import os
import sys
import tempfile
import logging
import tkinter as tk
from pathlib import Path

logger = logging.getLogger(__name__)


def center_window(parent: tk.Tk | tk.Toplevel, child: tk.Toplevel) -> None:
    """Center *child* window on top of *parent* window.

    Call this after the child has been given its initial geometry (so it
    knows its requested size) but before the mainloop blocks.  It works
    whether the child uses ``geometry("WxH")`` or ``geometry("WxH+X+Y")``.
    """
    child.update_idletasks()
    pw = parent.winfo_width()
    ph = parent.winfo_height()
    px = parent.winfo_rootx()
    py = parent.winfo_rooty()
    cw = child.winfo_width()
    ch = child.winfo_height()
    x = px + (pw - cw) // 2
    y = py + (ph - ch) // 2
    child.geometry(f"+{x}+{y}")


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

# Bundled template that is shipped inside the EXE. On first launch it is copied
# to `config.json` beside the EXE if no config exists yet. We never bundle
# `config.json` itself, because the developer's local copy may contain real
# HuggingFace / Google / Dropbox / OneDrive credentials that must NOT be
# baked into the binary.
_BUNDLED_CONFIG_TEMPLATE = "config.template.json"


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

    # Seed a clean config.json from the bundled template if the user doesn't
    # already have one. This keeps the EXE self-bootstrapping on first run
    # without ever bundling the developer's real secrets.
    template_src = bundle / _BUNDLED_CONFIG_TEMPLATE
    config_dst = app / "config.json"
    if template_src.exists() and not config_dst.exists():
        try:
            shutil.copy2(template_src, config_dst)
            logger.info("Seeded fresh config.json from bundled template")
        except Exception as e:
            logger.warning("Could not seed config.json from template: %s", e)


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


def get_oauth_token(provider: str) -> str:
    """Get OAuth token for a cloud provider.
    
    Priority: keyring (OS credential manager) → config.json (plaintext fallback)
    
    Args:
        provider: Provider name (e.g., "google_drive", "onedrive", "dropbox")
        
    Returns:
        OAuth token string, or empty string if not found.
    """
    # Priority 1: OS credential manager via keyring
    try:
        import keyring
        token = (keyring.get_password("FrogPaper", f"oauth_{provider}") or "").strip()
        if token:
            return token
    except ImportError:
        pass  # keyring not installed — fall through to config
    except Exception:
        pass  # keyring backend error — fall through to config
    
    # Priority 2: config.json (plaintext fallback - for migration/debugging only)
    try:
        config = load_config()
        oauth_tokens = config.get("oauth_tokens", {})
        token = (oauth_tokens.get(provider) or "").strip()
        return token
    except Exception:
        return ""


def save_oauth_token(provider: str, token: str) -> None:
    """Save OAuth token for a cloud provider to OS credential manager.
    
    Args:
        provider: Provider name (e.g., "google_drive", "onedrive", "dropbox")
        token: OAuth token string to store
    """
    try:
        import keyring
        keyring.set_password("FrogPaper", f"oauth_{provider}", token)
        logger.info(f"OAuth token saved to keyring for {provider}")
    except ImportError:
        logger.warning("keyring not installed, falling back to config.json")
        # Fallback to config.json (less secure)
        config = load_config()
        if "oauth_tokens" not in config:
            config["oauth_tokens"] = {}
        config["oauth_tokens"][provider] = token
        save_config(config)
    except Exception as e:
        logger.warning(f"keyring failed ({e}), falling back to config.json")
        # Fallback to config.json (less secure)
        config = load_config()
        if "oauth_tokens" not in config:
            config["oauth_tokens"] = {}
        config["oauth_tokens"][provider] = token
        save_config(config)


def delete_oauth_token(provider: str) -> None:
    """Delete OAuth token for a cloud provider from OS credential manager.
    
    Args:
        provider: Provider name (e.g., "google_drive", "onedrive", "dropbox")
    """
    # Try keyring first
    try:
        import keyring
        keyring.delete_password("FrogPaper", f"oauth_{provider}")
        logger.info(f"OAuth token deleted from keyring for {provider}")
        return
    except ImportError:
        pass  # Fall through to config.json
    except Exception as e:
        logger.debug(f"Keyring deletion failed: {e}")
    
    # Fallback: remove from config.json
    try:
        config = load_config()
        if "oauth_tokens" in config and provider in config["oauth_tokens"]:
            del config["oauth_tokens"][provider]
            save_config(config)
            logger.info(f"OAuth token deleted from config for {provider}")
    except Exception as e:
        logger.debug(f"Config deletion failed: {e}")


def has_oauth_token(provider: str) -> bool:
    """Check if OAuth token exists for a cloud provider.
    
    Args:
        provider: Provider name (e.g., "google_drive", "onedrive", "dropbox")
        
    Returns:
        True if token exists, False otherwise.
    """
    return bool(get_oauth_token(provider))


def create_export_folder(name: str = "FrogPaper_Portrait_Export") -> Path:
    """Create a temporary export folder with timestamp.
    
    Args:
        name: Base name for the export folder.
        
    Returns:
        Path to the created export folder.
    """
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_folder = BASE_DIR / f"{name}_{timestamp}"
    export_folder.mkdir(parents=True, exist_ok=True)
    return export_folder


def copy_images_to_folder(image_paths: list[Path], destination: Path) -> tuple[int, int]:
    """Copy images to destination folder.
    
    Args:
        image_paths: List of image file paths to copy.
        destination: Destination folder path.
        
    Returns:
        Tuple of (success_count, failure_count).
    """
    import shutil
    
    # Create destination folder if it doesn't exist
    destination.mkdir(parents=True, exist_ok=True)
    
    success_count = 0
    failure_count = 0
    
    for img_path in image_paths:
        try:
            dest_path = destination / img_path.name
            # Handle duplicate filenames
            if dest_path.exists():
                stem = img_path.stem
                suffix = img_path.suffix
                counter = 1
                while dest_path.exists():
                    dest_path = destination / f"{stem}_{counter}{suffix}"
                    counter += 1
            
            shutil.copy2(img_path, dest_path)
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to copy {img_path}: {e}")
            failure_count += 1
    
    return success_count, failure_count


def open_folder_in_explorer(folder_path: Path) -> bool:
    """Open a folder in Windows Explorer.
    
    Args:
        folder_path: Path to the folder to open.
        
    Returns:
        True if successful, False otherwise.
    """
    import subprocess
    import os
    
    try:
        if os.name == 'nt':  # Windows
            os.startfile(str(folder_path))
            return True
        else:
            # Fallback for other platforms
            subprocess.run(['xdg-open', str(folder_path)], check=True)
            return True
    except Exception as e:
        logger.error(f"Failed to open folder {folder_path}: {e}")
        return False


def invoke_windows_share(file_paths: list[Path]) -> bool:
    """Invoke Windows Share UI for multiple files.
    
    This is a complex operation that may not work reliably across all Windows versions.
    As a fallback, we recommend using open_folder_in_explorer instead.
    
    Args:
        file_paths: List of file paths to share.
        
    Returns:
        True if successful, False otherwise.
    """
    import subprocess
    import os
    
    if not file_paths:
        return False
    
    try:
        # Convert paths to absolute Windows paths
        abs_paths = [str(p.resolve()) for p in file_paths]
        
        # Attempt to invoke Windows Share UI using PowerShell
        # This method uses the Windows Runtime API
        ps_script = f'''
        Add-Type -AssemblyName WindowsRuntime
        $dataTransfer = [Windows.ApplicationModel.DataTransfer.DataTransferManager]::GetForCurrentView()
        '''
        
        # For now, return False as this needs more complex implementation
        # Fallback to folder export is recommended
        logger.warning("Direct Windows Share API not implemented, use folder export instead")
        return False
        
    except Exception as e:
        logger.error(f"Failed to invoke Windows Share: {e}")
        return False