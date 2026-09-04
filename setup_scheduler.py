"""
setup_scheduler.py
------------------
Creates or updates a Windows Task Scheduler job for FrogPaper.

This version schedules a batch wrapper instead of calling Python directly.
That wrapper changes into the FrogPaper folder first, which avoids the
common Task Scheduler 0x1 failure caused by the wrong working directory.

Manual use:
    python setup_scheduler.py
"""

import subprocess
import logging
import sys
from utils import get_app_dir

logger = logging.getLogger(__name__)

BASE_DIR = get_app_dir()
RUNNER_BAT = BASE_DIR / "run_daily_runner.bat"
TASK_NAME = "FrogPaperDailyWallpaper"


def create_wrapper_bat() -> None:
    python_path = sys.executable.replace("python.exe", "pythonw.exe")
    content = f'@echo off\ncd /d "%~dp0"\n"{python_path}" "%~dp0daily_runner.py"\n'
    RUNNER_BAT.write_text(content, encoding="utf-8")


def create_task() -> bool:
    if sys.platform != "win32":
        raise RuntimeError("This script only works on Windows.")

    create_wrapper_bat()
    if not RUNNER_BAT.exists():
        raise FileNotFoundError(f"Wrapper batch file not found: {RUNNER_BAT}")

    task_command = f'cmd /c "{RUNNER_BAT}"'

    logger.info(f"\n  Wrapper script  : {RUNNER_BAT}")
    logger.info(f"  Task name       : {TASK_NAME}")
    logger.info(f"  Command         : {task_command}\n")

    cmd = [
        "schtasks", "/create",
        "/tn", TASK_NAME,
        "/tr", task_command,
        "/sc", "ONLOGON",
        "/rl", "HIGHEST",
        "/f",
        "/delay", "0001:00",
    ]

    logger.info("  Adding to Windows Task Scheduler...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        logger.info("  SUCCESS! Task created or updated.")
        logger.info("\n  FrogPaper will now:")
        logger.info("    - Run automatically every time you log into Windows")
        logger.info("    - Wait 1 minute for your internet to connect")
        logger.info("    - Change into the FrogPaper folder first")
        logger.info("    - Launch daily_runner.py silently through pythonw.exe")
        logger.info("    - Generate and set a fresh wallpaper")
        logger.info("\n  To test right now without restarting:")
        logger.info(f"    schtasks /run /tn {TASK_NAME}")
        logger.info("\n  To remove the task later:")
        logger.info(f"    schtasks /delete /tn {TASK_NAME} /f")
        return True

    error_text = (result.stderr or result.stdout or "Unknown scheduler error").strip()
    logger.error(f"  FAILED: {error_text}")
    logger.info("\n  Try running Command Prompt as Administrator, then run:")
    logger.info("    python setup_scheduler.py")
    return False


if __name__ == "__main__":
    logger.info("\n  FrogPaper - Task Scheduler Setup")
    logger.info("  " + "-" * 40)
    try:
        ok = create_task()
        sys.exit(0 if ok else 1)
    except Exception as e:
        logger.error(f"\n  ERROR: {e}")
        sys.exit(1)
