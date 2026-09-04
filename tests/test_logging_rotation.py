"""Tests for FrogPaper's logging setup (improvement report §3).

Verifies that BOTH entry points attach a RotatingFileHandler with sane
size limits, so log files can never grow without bound:
  - app.py (the GUI)        -> logs/frogpaper.log
  - daily_runner.py (tasks) -> logs/daily_runner.log

Each check runs in a fresh subprocess so logging.basicConfig behaves the
same way it does at real startup (basicConfig is a no-op if the root
logger already has handlers, which would make in-process tests flaky).
"""

import os
import subprocess
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
PY = sys.executable
_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}

_CHECK = (
    "import logging; import {module}; "
    "hs = [h for h in logging.root.handlers "
    "      if type(h).__name__ == 'RotatingFileHandler']; "
    "assert hs, 'no RotatingFileHandler on root logger'; "
    "h = hs[0]; "
    "assert str(h.baseFilename).replace(chr(92), '/').endswith('logs/{logfile}'), h.baseFilename; "
    "assert h.maxBytes == 2 * 1024 * 1024, h.maxBytes; "
    "assert h.backupCount == 3, h.backupCount; "
    "print('OK')"
)


class TestLogRotation(unittest.TestCase):

    def _run_import_check(self, module, logfile):
        r = subprocess.run(
            [PY, "-c", _CHECK.format(module=module, logfile=logfile)],
            cwd=str(PROJECT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", env=_ENV, timeout=120,
        )
        self.assertEqual(r.returncode, 0,
                         f"check failed for {module}:\n{r.stdout}\n{r.stderr}")
        self.assertIn("OK", r.stdout)

    def test_daily_runner_uses_rotating_handler(self):
        self._run_import_check("daily_runner", "daily_runner.log")

    def test_gui_app_uses_rotating_handler(self):
        self._run_import_check("app", "frogpaper.log")

    def test_log_files_are_created(self):
        subprocess.run(
            [PY, "-c", "import app, daily_runner"],
            cwd=str(PROJECT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", env=_ENV, timeout=120,
        )
        logs = PROJECT / "logs"
        self.assertTrue((logs / "frogpaper.log").exists(),
                        "frogpaper.log was not created")
        self.assertTrue((logs / "daily_runner.log").exists(),
                        "daily_runner.log was not created")


if __name__ == "__main__":
    unittest.main(verbosity=2)
