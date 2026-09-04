"""
daily_runner.py
---------------
Silent background runner for FrogPaper.

What it does:
  1. Loads all available keywords
  2. Generates one fresh theme
  3. Builds one prompt
  4. Generates one wallpaper image
  5. Sets it as the Windows wallpaper
  6. Logs everything to logs/daily_runner.log

Manual test:
    python daily_runner.py
"""

import json
import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from utils import get_app_dir, get_bundle_dir

BASE_DIR = get_app_dir()
BUNDLE_DIR = get_bundle_dir()
LOGS_DIR = BASE_DIR / "logs"
KEYWORDS_FILE = BUNDLE_DIR / "keywords.json"
PROMPTS_LOG = LOGS_DIR / "prompts_history.json"
LOGS_DIR.mkdir(exist_ok=True)

log_file = LOGS_DIR / "daily_runner.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    handlers=[
        # Rotating: 2 MB per file, 3 backups — the log can never grow
        # beyond ~8 MB no matter how long the scheduler keeps running.
        RotatingFileHandler(log_file, maxBytes=2 * 1024 * 1024,
                            backupCount=3, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("daily_runner")


def load_all_keywords() -> list:
    with open(KEYWORDS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    all_words = []
    for key, values in data.items():
        if not key.startswith("_") and isinstance(values, list):
            all_words.extend(str(v).strip() for v in values if str(v).strip())
    return all_words


def append_prompt_log(entry: dict) -> None:
    try:
        if PROMPTS_LOG.exists():
            with open(PROMPTS_LOG, "r", encoding="utf-8") as f:
                existing = json.load(f)
            if not isinstance(existing, list):
                existing = []
        else:
            existing = []
    except Exception:
        existing = []

    existing.append(entry)
    with open(PROMPTS_LOG, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)


def run():
    log.info("=" * 50)
    log.info("FrogPaper daily run starting")

    try:
        from theme_mixer import generate_themes
        from prompt_builder import build_all_prompts
        from wallpaper_generator import generate_image
        from set_wallpaper import set_wallpaper
    except ImportError as e:
        log.error(f"Could not import module: {e}")
        sys.exit(1)

    try:
        keywords = load_all_keywords()
        if not keywords:
            raise ValueError("keywords.json did not contain any usable keyword values")
        log.info(f"Loaded {len(keywords)} keywords")
    except Exception as e:
        log.error(f"Could not load keywords.json: {e}")
        sys.exit(1)

    try:
        themes = generate_themes(count=1, user_keywords=keywords)
        if not themes:
            raise ValueError("generate_themes returned no themes")
        theme = themes[0]
        log.info(f"Theme: {theme.get('sentence', 'Untitled theme')}")
    except Exception as e:
        log.error(f"Theme generation failed: {e}")
        sys.exit(1)

    try:
        prompts = build_all_prompts(themes, style_mode="stylized")
        if not prompts:
            raise ValueError("build_all_prompts returned no prompts")
        prompt_data = prompts[0]
        prompt = prompt_data.get("prompt", "").strip()
        if not prompt:
            raise ValueError("prompt text was empty")

        log_entry = {
            "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            **prompt_data,
        }
        append_prompt_log(log_entry)
        log.info(f"Prompt built ({len(prompt)} chars)")
    except Exception as e:
        log.error(f"Prompt building failed: {e}")
        sys.exit(1)

    try:
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        image_path = generate_image(prompt, filename=f"daily_{date_str}")
        image_path = Path(image_path)
        log.info(f"Image saved: {image_path.name}")
    except Exception as e:
        log.error(f"Image generation error: {e}")
        sys.exit(1)

    try:
        success = set_wallpaper(image_path)
        if success:
            log.info(f"Wallpaper set: {image_path.name}")
        else:
            log.error("set_wallpaper returned False")
            sys.exit(1)
    except Exception as e:
        log.error(f"Setting wallpaper failed: {e}")
        sys.exit(1)

    log.info("FrogPaper daily run complete")
    log.info("=" * 50)


if __name__ == "__main__":
    run()
