"""Filesystem layout constants for FrogPaper (roadmap #7 Phase B step 2).

Extracted verbatim from app.py.  Importing this module performs the
same directory-creation side effects as the original inline block,
at the same point of app.py start-up.
"""

from utils import get_app_dir


BASE_DIR = get_app_dir()

LOGS_DIR = BASE_DIR / "logs"

PROMPTS_LOG = LOGS_DIR / "prompts_history.json"

FAVORITES_LOG = LOGS_DIR / "favorites.json"

FAVORITES_DIR = BASE_DIR / "wallpapers" / "favorites"
STYLED_DIR = BASE_DIR / "wallpapers" / "styled"
MANUAL_DIR = BASE_DIR / "wallpapers" / "manual"

PRESETS_FILE = LOGS_DIR / "presets.json"

SESSIONS_FILE = LOGS_DIR / "sessions.json"

LOGS_DIR.mkdir(exist_ok=True)

FAVORITES_DIR.mkdir(parents=True, exist_ok=True)
STYLED_DIR.mkdir(parents=True, exist_ok=True)
MANUAL_DIR.mkdir(parents=True, exist_ok=True)
