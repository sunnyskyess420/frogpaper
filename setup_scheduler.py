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
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
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

    print(f"\n  Wrapper script  : {RUNNER_BAT}")
    print(f"  Task name       : {TASK_NAME}")
    print(f"  Command         : {task_command}\n")

    cmd = [
        "schtasks", "/create",
        "/tn", TASK_NAME,
        "/tr", task_command,
        "/sc", "ONLOGON",
        "/rl", "HIGHEST",
        "/f",
        "/delay", "0001:00",
    ]

    print("  Adding to Windows Task Scheduler...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print("  SUCCESS! Task created or updated.")
        print("\n  FrogPaper will now:")
        print("    - Run automatically every time you log into Windows")
        print("    - Wait 1 minute for your internet to connect")
        print("    - Change into the FrogPaper folder first")
        print("    - Launch daily_runner.py silently through pythonw.exe")
        print("    - Generate and set a fresh wallpaper")
        print("\n  To test right now without restarting:")
        print(f"    schtasks /run /tn {TASK_NAME}")
        print("\n  To remove the task later:")
        print(f"    schtasks /delete /tn {TASK_NAME} /f")
        return True

    error_text = (result.stderr or result.stdout or "Unknown scheduler error").strip()
    print(f"  FAILED: {error_text}")
    print("\n  Try running Command Prompt as Administrator, then run:")
    print("    python setup_scheduler.py")
    return False


if __name__ == "__main__":
    print("\n  FrogPaper - Task Scheduler Setup")
    print("  " + "-" * 40)
    try:
        ok = create_task()
        sys.exit(0 if ok else 1)
    except Exception as e:
        print(f"\n  ERROR: {e}")
        sys.exit(1)
