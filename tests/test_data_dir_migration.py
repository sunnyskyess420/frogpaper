"""Regression tests for the 1.7.6 user-data directory move.

Frozen builds used to keep user data beside the EXE, where a rebuild or a
folder replacement destroyed the user's images and API keys.  These tests
pin the new behaviour: data lives in %LOCALAPPDATA%\\FrogPaper, and the
one-time migration copies — never moves, never overwrites — whatever an
older build left beside the EXE.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import app_data_dir
import utils


class DataDirMigrationTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.legacy = root / "dist"          # where the EXE + old data lived
        self.localappdata = root / "Local"   # stands in for %LOCALAPPDATA%
        self.legacy.mkdir()
        self.localappdata.mkdir()

        self._saved = (
            getattr(sys, "frozen", None),
            sys.executable,
            os.environ.get("LOCALAPPDATA"),
            app_data_dir._migration_checked,
        )
        sys.frozen = True
        sys.executable = str(self.legacy / "FrogPaper.exe")
        os.environ["LOCALAPPDATA"] = str(self.localappdata)
        app_data_dir._migration_checked = False

    def tearDown(self):
        frozen, executable, localappdata, checked = self._saved
        try:
            del sys.frozen
        except AttributeError:
            pass
        if frozen is not None:
            sys.frozen = frozen
        sys.executable = executable
        if localappdata is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = localappdata
        app_data_dir._migration_checked = checked
        self._tmp.cleanup()

    def _write(self, path: Path, text: str = "x") -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_frozen_data_dir_is_under_localappdata(self):
        app_dir = utils.get_app_dir()
        self.assertEqual(app_dir, self.localappdata / "FrogPaper")
        self.assertTrue(app_dir.is_dir())

    def test_migration_copies_config_wallpapers_and_database(self):
        self._write(self.legacy / "config.json", json.dumps({"huggingface_token": "keep-me"}))
        self._write(self.legacy / "frogpaper.db", "db")
        self._write(self.legacy / "frogpaper.db-wal", "wal")
        self._write(self.legacy / "gallery_tags.json", "[]")
        self._write(self.legacy / "wallpapers" / "generated" / "a.png", "png")
        self._write(self.legacy / "wallpapers" / "manual" / "sub" / "b.png", "png")
        self._write(self.legacy / "logs" / "favorites.json", "[]")

        app_dir = utils.get_app_dir()

        self.assertEqual(
            json.loads((app_dir / "config.json").read_text(encoding="utf-8")),
            {"huggingface_token": "keep-me"},
        )
        self.assertEqual((app_dir / "frogpaper.db").read_text(encoding="utf-8"), "db")
        self.assertEqual((app_dir / "frogpaper.db-wal").read_text(encoding="utf-8"), "wal")
        self.assertEqual((app_dir / "gallery_tags.json").read_text(encoding="utf-8"), "[]")
        self.assertEqual(
            (app_dir / "wallpapers" / "generated" / "a.png").read_text(encoding="utf-8"), "png")
        self.assertEqual(
            (app_dir / "wallpapers" / "manual" / "sub" / "b.png").read_text(encoding="utf-8"), "png")
        self.assertEqual(
            (app_dir / "logs" / "favorites.json").read_text(encoding="utf-8"), "[]")

    def test_migration_leaves_originals_in_place(self):
        self._write(self.legacy / "config.json", "{}")
        self._write(self.legacy / "wallpapers" / "generated" / "a.png", "png")

        utils.get_app_dir()

        self.assertTrue((self.legacy / "config.json").is_file())
        self.assertTrue((self.legacy / "wallpapers" / "generated" / "a.png").is_file())

    def test_migration_does_not_overwrite_existing_data(self):
        self._write(self.localappdata / "FrogPaper" / "config.json", '{"new": true}')
        self._write(self.legacy / "config.json", '{"old": true}')

        app_dir = utils.get_app_dir()

        self.assertEqual((app_dir / "config.json").read_text(encoding="utf-8"), '{"new": true}')

    def test_migration_skips_bundled_template(self):
        self._write(self.legacy / "config.template.json", "{}")
        self._write(self.legacy / "sounds" / "click.wav", "wav")

        app_dir = utils.get_app_dir()

        self.assertFalse((app_dir / "config.template.json").exists())
        self.assertFalse((app_dir / "sounds").exists())

    def test_migration_runs_only_once(self):
        self._write(self.legacy / "config.json", '{"first": 1}')
        app_dir = utils.get_app_dir()

        self._write(self.legacy / "config.json", '{"second": 2}')
        app_data_dir._migration_checked = False  # simulate the next launch
        utils.get_app_dir()

        self.assertEqual((app_dir / "config.json").read_text(encoding="utf-8"), '{"first": 1}')

    def test_source_runs_still_use_the_project_folder(self):
        del sys.frozen
        self.assertEqual(utils.get_app_dir(), Path(utils.__file__).parent)


if __name__ == "__main__":
    unittest.main()