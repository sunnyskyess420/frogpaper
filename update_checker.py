"""
update_checker.py
-----------------
Checks GitHub Releases for the latest FrogPaper version.
Shows a themed notification popup when a newer version is available.

Used by app.py — called once on startup in a background thread.
No extra dependencies — uses only urllib (stdlib).
"""

import json
import logging
import threading
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

GITHUB_REPO = "sunnyskyess420/frogpaper"
RELEASES_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
DOWNLOADS_URL = "https://sunnyskyess420.github.io/frogpaper-website/#downloads"


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

    Returned dict keys: tag_name, name, html_url, body (cleaned), download_url
    """
    data = fetch_latest_release()
    if data is None:
        return None

    latest_tag = data.get("tag_name", "")
    if not latest_tag or not is_newer(latest_tag, current_version):
        logger.debug("App is up-to-date (%s >= %s)", current_version, latest_tag)
        return None

    # Find the .exe installer asset
    download_url = DOWNLOADS_URL  # fallback to website
    for asset in data.get("assets", []):
        name = asset.get("name", "")
        if name.endswith(".exe") and "Setup" in name:
            download_url = asset.get("browser_download_url", download_url)
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
    }


def show_update_notification(app, release_info: dict):
    """Display a themed update notification using the app's dialog system.

    Must be called on the main thread (scheduled via root.after).
    """
    try:
        tag = release_info["tag_name"]
        name = release_info["name"]
        body = release_info["body"]
        url = release_info["download_url"]

        title = f"Update Available"
        msg = f"A new version of FrogPaper is available!\n\n{name}\n\nWould you like to download it now?"

        result = app._dialog.ask(title, msg)

        if result:
            # Open download page in default browser
            import webbrowser
            webbrowser.open(url)

    except Exception as exc:
        logger.warning("Failed to show update notification: %s", exc)


def check_on_startup(app, current_version: str, delay_seconds: int = 5):
    """Run the update check in a background thread after a short delay.

    This keeps startup fast — the check runs quietly and only shows
    a popup if a newer version is found.

    Args:
        app: The FrogPaperApp instance (for dialog + root.after).
        current_version: The APP_VERSION string (e.g. "1.1.0").
        delay_seconds: How long to wait before checking (default 5s).
    """

    def _worker():
        import time
        time.sleep(delay_seconds)  # Let the app finish loading first
        release = check_for_update(current_version)
        if release is not None:
            # Schedule the UI popup on the main thread
            try:
                app.root.after(0, show_update_notification, app, release)
            except Exception:
                pass

    t = threading.Thread(target=_worker, daemon=True, name="UpdateChecker")
    t.start()
