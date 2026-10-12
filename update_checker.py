"""
update_checker.py
-----------------
Checks GitHub Releases for the latest FrogPaper version.
Shows a themed notification popup when a newer version is available.

Used by app.py — called once on startup in a background thread.
No extra dependencies — uses only urllib (stdlib).

Persistence:
    If the user clicks "Skip This Version", the latest tag is recorded in
    config.json under `skipped_update_version`. The popup will NOT appear
    again for that exact version. When an even newer version is released,
    the popup reappears (because the skipped tag no longer matches).
"""

import json
import logging
import os
import subprocess
import sys
import tempfile
import threading
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Callable

# Import thread-safe UI update functions
try:
    from thread_manager import run_background, schedule_ui_update
    THREAD_MANAGER_AVAILABLE = True
except ImportError:
    THREAD_MANAGER_AVAILABLE = False
    # Fallback to direct threading if thread_manager not available
    def schedule_ui_update(callback, *args, **kwargs):
        """Fallback for thread-safe UI updates."""
        if hasattr(callback, '__self__') and hasattr(callback.__self__, 'root'):
            callback.__self__.root.after(0, lambda: callback(*args, **kwargs))
        else:
            # Direct call as fallback (not thread-safe, but prevents crashes)
            callback(*args, **kwargs)
    
    def run_background(target, *args, daemon=True, **kwargs):
        """Fallback for background thread execution."""
        thread = threading.Thread(target=target, args=args, kwargs=kwargs, daemon=daemon)
        thread.start()
        return thread

logger = logging.getLogger(__name__)

GITHUB_REPO = "sunnyskyess420/frogpaper"
RELEASES_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
DOWNLOADS_URL = "https://sunnyskyess420.github.io/frogpaper-website/#downloads"

# Field in config.json used to persist the user's "skip this version" choice.
SKIPPED_VERSION_KEY = "skipped_update_version"

# Release asset filename must contain this hint (and end with .exe) to be
# treated as the installer for the one-click update flow.
INSTALLER_ASSET_HINT = "Setup"

# Stream the installer download in ~256 KiB chunks so progress can be reported
# and a runaway download can be cancelled without freezing the UI.
DOWNLOAD_CHUNK_SIZE = 256 * 1024

# Refuse to treat a download as a valid installer below this size — a few KB
# almost certainly means an HTML error page was saved instead of the EXE.
MIN_INSTALLER_BYTES = 1024 * 1024


def _config_path() -> Path:
    """Locate config.json next to the EXE (or beside the source tree)."""
    try:
        from utils import CONFIG_FILE
        return CONFIG_FILE
    except Exception:
        # Fallback if utils hasn't been imported yet — shouldn't happen in
        # normal operation, but we never want the update check to crash.
        return Path(__file__).resolve().parent / "config.json"


def get_skipped_version() -> str:
    """Return the version tag the user has explicitly skipped, or ""."""
    try:
        with _config_path().open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return str(data.get(SKIPPED_VERSION_KEY, "") or "").strip()
    except Exception:
        pass
    return ""


def skip_version(version_tag: str) -> None:
    """Persist the given version tag as 'skipped' so the popup is suppressed
    for that exact version on subsequent launches."""
    try:
        from utils import load_config, save_config
        config = load_config()
        config[SKIPPED_VERSION_KEY] = version_tag
        save_config(config)
        logger.info("Update popup suppressed for version %s", version_tag)
    except Exception as exc:
        # Fall back to a direct file write if utils helpers are unavailable.
        try:
            path = _config_path()
            with path.open("r", encoding="utf-8") as f:
                config = json.load(f) if path.exists() else {}
            if not isinstance(config, dict):
                config = {}
            config[SKIPPED_VERSION_KEY] = version_tag
            with path.open("w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
        except Exception as exc2:
            logger.warning("Failed to persist skipped version: %s / %s", exc, exc2)


def parse_version(version_str: str) -> tuple:
    """Parse '1.2.3' into (1, 2, 3). Handles 'v' prefix."""
    s = version_str.lstrip("vV")
    parts = []
    for part in s.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def is_newer(latest: str, current: str) -> bool:
    """Return True if *latest* is strictly newer than *current*."""
    return parse_version(latest) > parse_version(current)


def fetch_latest_release() -> Optional[dict]:
    """Call GitHub Releases API and return the JSON response, or None on failure."""
    req = urllib.request.Request(
        RELEASES_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "FrogPaper-UpdateChecker",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, KeyError) as exc:
        logger.debug("Update check failed: %s", exc)
        return None


def _clean_markdown(text: str) -> str:
    """Strip markdown formatting from GitHub release body for clean display."""
    import re
    # Remove bold/italic markers
    text = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', text)
    # Remove heading markers
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)
    # Remove bullet markers but keep the text
    text = re.sub(r'^\s*[-*]\s*', '- ', text, flags=re.MULTILINE)
    # Remove links but keep the text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # Collapse multiple blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def check_for_update(current_version: str) -> Optional[dict]:
    """Return release info dict if an update is available, else None.

    Suppressed (returns None) when:
      - the GitHub API call fails
      - the latest tag is not strictly newer than the current version
      - the user has explicitly skipped the latest tag
    """
    data = fetch_latest_release()
    if data is None:
        return None

    latest_tag = data.get("tag_name", "")
    if not latest_tag or not is_newer(latest_tag, current_version):
        logger.debug("App is up-to-date (%s >= %s)", current_version, latest_tag)
        return None

    # Honor a previously-recorded "Skip this version" choice.
    if get_skipped_version() == latest_tag:
        logger.debug("Update to %s skipped by user — suppressing popup", latest_tag)
        return None

    # Find the .exe installer asset
    download_url = DOWNLOADS_URL  # fallback to website
    download_size = 0
    for asset in data.get("assets", []):
        name = asset.get("name", "")
        if name.lower().endswith(".exe") and INSTALLER_ASSET_HINT in name:
            download_url = asset.get("browser_download_url", download_url)
            try:
                download_size = int(asset.get("size") or 0)
            except (TypeError, ValueError):
                download_size = 0
            break

    # Clean and truncate body for the popup
    body = (data.get("body") or "").strip()
    body = _clean_markdown(body)

    # Keep only the first few lines so the dialog doesn't overflow
    lines = body.split("\n")
    kept = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if kept:
                break  # stop at first blank line after content
            continue
        kept.append(stripped)
        if len(kept) >= 5:  # max 5 bullet points / lines
            break
    body = "\n".join(kept)

    return {
        "tag_name": latest_tag,
        "name": data.get("name", latest_tag),
        "html_url": data.get("html_url", ""),
        "body": body,
        "download_url": download_url,
        "download_size": download_size,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  One-click update: download the installer straight from GitHub and run it
# ═══════════════════════════════════════════════════════════════════════════

class DownloadCancelled(Exception):
    """Raised when the user cancels an in-progress installer download."""


def is_installer_url(url: str) -> bool:
    """Return True when *url* points directly at a downloadable .exe."""
    if not url or not url.lower().startswith(("http://", "https://")):
        return False
    # Strip any query string/fragment before checking the extension.
    path = url.split("#", 1)[0].split("?", 1)[0]
    return path.lower().endswith(".exe")


def default_download_dir() -> Path:
    """Folder where the downloaded installer is staged before launching."""
    return Path(tempfile.gettempdir()) / "FrogPaper-Update"


def _format_size(num_bytes: float) -> str:
    """Human-readable size (e.g. '3.4 MB') for progress feedback."""
    try:
        size = float(num_bytes)
    except (TypeError, ValueError):
        return "?"
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def download_installer(
    url: str,
    dest_dir: Path,
    progress_cb: Optional[Callable[[int, int], None]] = None,
    cancel_event: Optional[threading.Event] = None,
    timeout: int = 30,
    chunk_size: int = DOWNLOAD_CHUNK_SIZE,
) -> Path:
    """Stream the installer at *url* into *dest_dir* and return its path.

    Args:
        url: direct browser_download_url from the GitHub release asset.
        dest_dir: folder to write the installer into (created if missing).
        progress_cb: called as progress_cb(bytes_done, total_bytes); total is
            0 when the server does not report a Content-Length.
        cancel_event: when set, the download aborts and the partial file is
            removed.

    Raises:
        DownloadCancelled: the user cancelled.
        OSError / urllib.error.URLError: the download failed.
    """
    if not is_installer_url(url):
        raise ValueError(f"Not a direct installer download URL: {url!r}")

    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = url.split("#", 1)[0].split("?", 1)[0].rsplit("/", 1)[-1] or "FrogPaper-Setup.exe"
    if not name.lower().endswith(".exe"):
        name = "FrogPaper-Setup.exe"
    dest = dest_dir / name

    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/octet-stream",
            "User-Agent": "FrogPaper-Updater",
        },
    )

    def _abort(partial: Path) -> None:
        try:
            partial.unlink(missing_ok=True)
        except Exception:
            pass

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            try:
                total = int(resp.headers.get("Content-Length") or 0)
            except (TypeError, ValueError):
                total = 0
            done = 0
            with dest.open("wb") as fh:
                while True:
                    if cancel_event is not None and cancel_event.is_set():
                        raise DownloadCancelled("Download cancelled by user")
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    fh.write(chunk)
                    done += len(chunk)
                    if progress_cb is not None:
                        try:
                            progress_cb(done, total)
                        except Exception:
                            pass
    except DownloadCancelled:
        _abort(dest)
        raise
    except (urllib.error.URLError, OSError, ValueError) as exc:
        _abort(dest)
        raise OSError(f"Download failed: {exc}") from exc

    if dest.stat().st_size < MIN_INSTALLER_BYTES:
        _abort(dest)
        raise OSError("Downloaded file is far too small to be the installer")

    logger.info("Downloaded installer to %s (%s)", dest, _format_size(dest.stat().st_size))
    return dest


def _palette(app) -> dict:
    """Best-effort theme palette lookup, with a safe fallback."""
    try:
        return app._dialog._pal()
    except Exception:
        return {
            "bg": "#1b231d",
            "panel2": "#2a3329",
            "text": "#e6efe2",
            "accent": "#4fbf7a",
            "border_color": "#3a463a",
            "button_hover": "#38452f",
        }


class UpdateProgressWindow:
    """Small themed, cancellable progress window shown while the installer
    downloads. Must be constructed on the main UI thread; progress_cb may be
    called from a worker thread (updates are marshalled back to the UI)."""

    def __init__(self, app, tag: str, expected_size: int = 0):
        import tkinter as tk
        from tkinter import ttk

        self._app = app
        self._closed = False
        self.cancel_event = threading.Event()
        self._total = int(expected_size or 0)
        pal = _palette(app)

        top = tk.Toplevel(app.root)
        self._top = top
        top.title("Updating FrogPaper")
        top.configure(bg=pal["bg"])
        top.resizable(False, False)
        try:
            top.transient(app.root)
        except Exception:
            pass

        w, h = 440, 190
        try:
            px = app.root.winfo_rootx()
            py = app.root.winfo_rooty()
            pw = app.root.winfo_width()
            ph = app.root.winfo_height()
            x = px + max(0, (pw - w) // 2)
            y = py + max(0, (ph - h) // 2)
        except Exception:
            x = y = 200
        top.geometry(f"{w}x{h}+{x}+{y}")

        tk.Label(
            top, text=f"Downloading FrogPaper {tag}", bg=pal["bg"],
            fg=pal["text"], font=("Segoe UI", 11, "bold"),
        ).pack(pady=(18, 4))
        tk.Label(
            top, text="Fetching the update straight from GitHub…",
            bg=pal["bg"], fg=pal["text"], font=("Segoe UI", 9),
        ).pack()

        style_name = "FrogUpdate.Horizontal.TProgressbar"
        try:
            ttk.Style(top).configure(
                style_name,
                troughcolor=pal.get("panel2", "#2a3329"),
                background=pal.get("accent", "#4fbf7a"),
                bordercolor=pal.get("border_color", "#3a463a"),
            )
            bar_style = style_name
        except Exception:
            bar_style = None

        self._bar = ttk.Progressbar(
            top, orient="horizontal", length=360, maximum=100,
            mode="determinate" if self._total > 0 else "indeterminate",
            style=bar_style,
        )
        self._bar.pack(pady=(16, 6))
        if self._total <= 0:
            try:
                self._bar.start(12)
            except Exception:
                pass

        self._pct = tk.Label(
            top, text="Starting…" if self._total > 0 else "Connecting…",
            bg=pal["bg"], fg=pal["text"], font=("Segoe UI", 9),
        )
        self._pct.pack()

        tk.Button(
            top, text="Cancel", command=self._on_cancel,
            bg=pal.get("panel2", "#2a3329"), fg=pal["text"],
            activebackground=pal.get("button_hover", pal.get("panel2", "#2a3329")),
            activeforeground=pal["text"], relief="flat", padx=14, pady=4,
            cursor="hand2", font=("Segoe UI", 9),
        ).pack(pady=(12, 10))

        top.protocol("WM_DELETE_WINDOW", self._on_cancel)

    # -- progress plumbing -------------------------------------------------

    def update(self, downloaded: int, total: int = 0) -> None:
        """Thread-safe progress callback (called from the download worker)."""
        if self._closed:
            return
        try:
            schedule_ui_update(self._apply, int(downloaded), int(total or 0))
        except Exception:
            pass

    def _apply(self, downloaded: int, total: int) -> None:
        if self._closed:
            return
        effective_total = total or self._total
        try:
            if effective_total > 0:
                pct = max(0.0, min(100.0, downloaded / effective_total * 100.0))
                if str(self._bar.cget("mode")) != "determinate":
                    self._bar.stop()
                    self._bar.configure(mode="determinate")
                self._bar["value"] = pct
                self._pct.configure(
                    text=f"{pct:.0f}%  ({_format_size(downloaded)} of {_format_size(effective_total)})"
                )
            else:
                self._pct.configure(text=f"{_format_size(downloaded)} downloaded")
        except Exception:
            pass

    # -- lifecycle ---------------------------------------------------------

    def _on_cancel(self) -> None:
        self.cancel_event.set()
        self.close()

    def close(self) -> None:
        """Close the window (safe from any thread)."""
        if self._closed:
            return
        self._closed = True
        try:
            schedule_ui_update(self._destroy)
        except Exception:
            self._destroy()

    def _destroy(self) -> None:
        try:
            self._bar.stop()
        except Exception:
            pass
        try:
            self._top.destroy()
        except Exception:
            pass


DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200


def spawn_installer_after_exit(installer_path: Path, max_wait_seconds: int = 180) -> bool:
    """Launch the downloaded installer *after* FrogPaper exits.

    A detached helper batch waits until this process is gone (so the installer
    can overwrite the currently-running EXE without a "file in use" prompt),
    then starts the installer and deletes itself. Returns True when the helper
    was started. On non-Windows platforms the file is simply opened.
    """
    installer_path = Path(installer_path)
    if not installer_path.exists():
        return False

    if sys.platform != "win32":
        try:
            opener = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.Popen([opener, str(installer_path)])
            return True
        except Exception as exc:
            logger.warning("Could not open installer: %s", exc)
            return False

    pid = os.getpid()
    loops = max(1, int(max_wait_seconds) * 2)  # ~0.5 s per iteration
    script = (
        "@echo off\r\n"
        "setlocal enabledelayedexpansion\r\n"
        "set /a n=0\r\n"
        ":wait\r\n"
        f'tasklist /FI "PID eq {pid}" 2>nul | find "{pid}" >nul\r\n'
        "if errorlevel 1 goto launch\r\n"
        "set /a n+=1\r\n"
        f"if !n! GEQ {loops} goto launch\r\n"
        "ping -n 2 127.0.0.1 >nul\r\n"
        "goto wait\r\n"
        ":launch\r\n"
        f'start "" "{installer_path}"\r\n'
        'del "%~f0"\r\n'
    )
    bat_path = Path(tempfile.gettempdir()) / "frogpaper_update_launch.bat"
    try:
        bat_path.write_text(script, encoding="utf-8")
        subprocess.Popen(
            ["cmd", "/c", str(bat_path)],
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        logger.info("Installer will launch once FrogPaper exits: %s", installer_path)
        return True
    except Exception as exc:
        logger.warning("Could not schedule installer launch: %s", exc)
        return False


def open_in_browser(url: str) -> None:
    """Open *url* in the default browser (best-effort)."""
    try:
        import webbrowser
        webbrowser.open(url)
    except Exception as exc:
        logger.warning("Could not open browser for %s: %s", url, exc)


def _install_and_quit(app, installer_path: Path, tag: str) -> None:
    """Launch the installer (after we exit) and shut FrogPaper down."""
    if not spawn_installer_after_exit(installer_path):
        try:
            app._dialog.error(
                "Could Not Start Installer",
                f"FrogPaper downloaded the update but couldn't launch it.\n\n"
                f"Please run this file manually:\n{installer_path}",
            )
        except Exception:
            pass
        return
    try:
        app._quit_app()
    except Exception:
        try:
            app.root.destroy()
        except Exception:
            pass
        try:
            os._exit(0)
        except Exception:
            pass


def _confirm_install(app, installer_path: Path, tag: str) -> None:
    """Ask before closing the app to run the freshly downloaded installer."""
    msg = (
        f"FrogPaper {tag} is ready to install.\n\n"
        "FrogPaper will close and the installer will open.\n"
        "Your wallpapers, settings and API keys are kept."
    )
    try:
        choice = app._dialog._show(
            "ask", "Ready to Install", msg,
            buttons=("Install Now", "Later"), primary="Install Now",
        )
    except Exception:
        choice = "Install Now"

    if choice == "Install Now":
        _install_and_quit(app, installer_path, tag)
    else:
        try:
            app._dialog.info(
                "Installer Saved",
                f"The update was saved to:\n{installer_path}\n\n"
                "You can run it any time to finish installing.",
            )
        except Exception:
            pass


def _download_failed(app, release_info: dict, error: str) -> None:
    """Automatic download failed — point the user at the download page."""
    try:
        app._dialog.warning(
            "Automatic Update Failed",
            "FrogPaper couldn't download the update automatically.\n\n"
            f"{error}\n\n"
            "Opening the download page in your browser instead.",
        )
    except Exception:
        pass
    open_in_browser(release_info.get("html_url") or release_info.get("download_url", DOWNLOADS_URL))


def start_update_install(app, release_info: dict) -> None:
    """Download the installer for *release_info* in the background, then run it.

    Falls back to opening the download page when the release has no direct
    installer asset or when FrogPaper is running from source (an EXE install
    wouldn't update this copy).
    """
    url = release_info.get("download_url", "")
    tag = release_info.get("tag_name", "latest")

    if not getattr(sys, "frozen", False):
        # Running from source — installing the EXE wouldn't update this tree.
        logger.info("Source run detected; opening download page instead of auto-install")
        open_in_browser(release_info.get("html_url") or url or DOWNLOADS_URL)
        return

    if not is_installer_url(url):
        logger.info("No direct installer asset found; opening download page")
        open_in_browser(release_info.get("html_url") or url or DOWNLOADS_URL)
        return

    expected = int(release_info.get("download_size") or 0)
    try:
        progress = UpdateProgressWindow(app, tag, expected_size=expected)
    except Exception as exc:
        logger.warning("Could not show progress window: %s", exc)
        open_in_browser(release_info.get("html_url") or url)
        return

    def _worker():
        try:
            installer = download_installer(
                url,
                default_download_dir(),
                progress_cb=progress.update,
                cancel_event=progress.cancel_event,
            )
        except DownloadCancelled:
            logger.info("Installer download cancelled by user")
            progress.close()
            return
        except Exception as exc:
            logger.warning("Installer download failed: %s", exc)
            progress.close()
            try:
                schedule_ui_update(_download_failed, app, release_info, str(exc))
            except Exception:
                pass
            return

        progress.close()
        try:
            schedule_ui_update(_confirm_install, app, installer, tag)
        except Exception:
            pass

    run_background(_worker, name="UpdateDownload")


def show_update_notification(app, release_info: dict):
    """Display a themed update notification using the app's dialog system.

    Offers three actions:
      - "Install Update"      → download the installer from GitHub and run it
      - "Skip This Version"   → suppress popup for this exact version
      - "Not Now"             → dismiss for this launch only

    Must be called on the main thread (scheduled via root.after).
    """
    try:
        tag = release_info["tag_name"]
        name = release_info["name"]

        title = "Update Available"
        msg = (
            f"A new version of FrogPaper is available!\n\n"
            f"{name}\n\n"
            "Click 'Install Update' and FrogPaper will download and set it up "
            "for you automatically."
        )

        # Use the dialog's underlying _show() so we can supply three buttons.
        # _show returns the label of the button that was clicked.
        buttons = ("Install Update", "Skip This Version", "Not Now")
        choice = app._dialog._show(
            "ask", title, msg, buttons=buttons, primary="Install Update",
        )

        if choice == "Install Update":
            start_update_install(app, release_info)
        elif choice == "Skip This Version":
            skip_version(tag)
            try:
                app._dialog.info(
                    "Update Skipped",
                    f"You won't be notified about version {tag} again.\n\n"
                    f"A new popup will appear when an even newer version is released.",
                )
            except Exception:
                pass

    except Exception as exc:
        logger.warning("Failed to show update notification: %s", exc)


def check_on_startup(app, current_version: str, delay_seconds: int = 5):
    """Run the update check in a background thread after a short delay.

    This keeps startup fast — the check runs quietly and only shows
    a popup if a newer version is found (and hasn't been skipped).

    Args:
        app: The FrogPaperApp instance (for dialog + root.after).
        current_version: The APP_VERSION string (e.g. "1.2.0").
        delay_seconds: How long to wait before checking (default 5s).
    """

    def _worker():
        import time
        time.sleep(delay_seconds)  # Let the app finish loading first
        release = check_for_update(current_version)
        if release is not None:
            # Schedule the UI popup on the main thread
            try:
                schedule_ui_update(show_update_notification, app, release)
            except Exception:
                pass

    run_background(_worker, name="UpdateChecker")
