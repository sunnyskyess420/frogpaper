"""Regression guards for the startup popup loop and atomic image writes."""
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import utils
import wallpaper_generator as wg
from tutorial_manager import TutorialManager


class TestStartupPromptDoesNotRepeat(unittest.TestCase):
    def _config(self, data):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        old = utils.CONFIG_FILE
        self.addCleanup(lambda: setattr(utils, "CONFIG_FILE", old))
        utils.CONFIG_FILE = pathlib.Path(tmp.name) / "config.json"
        utils.CONFIG_FILE.write_text(json.dumps(data), encoding="utf-8")

    def test_prompt_shows_for_a_real_first_run(self):
        self._config({})
        self.assertTrue(TutorialManager.should_show_first_run_tutorial(object()))

    def test_prompt_hidden_once_flag_is_set(self):
        self._config({"first_run_completed": True})
        self.assertFalse(TutorialManager.should_show_first_run_tutorial(object()))

    def test_prompt_hidden_for_users_who_finished_a_tour(self):
        # Older builds only recorded completed_tutorials, never the flag.
        self._config({"completed_tutorials": ["Quick Start Guide"]})
        self.assertFalse(TutorialManager.should_show_first_run_tutorial(object()))


class TestSaveImageBytes(unittest.TestCase):
    def _dir(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return pathlib.Path(tmp.name)

    def test_error_body_is_rejected_and_leaves_nothing(self):
        d = self._dir()
        target = d / "x.png"
        with self.assertRaises(wg.ImageGenerationError):
            wg.save_image_bytes(target, b"<html>502 Bad Gateway</html>")
        self.assertFalse(target.exists())
        self.assertEqual(list(d.iterdir()), [])

    def test_valid_bytes_are_written_without_a_part_file(self):
        d = self._dir()
        target = d / "y.png"
        data = b"\x89PNG\r\n\x1a\n" + b"0" * 2000
        wg.save_image_bytes(target, data)
        self.assertEqual(target.read_bytes(), data)
        self.assertEqual(list(d.iterdir()), [target])

    def test_empty_payload_rejected(self):
        d = self._dir()
        with self.assertRaises(wg.ImageGenerationError):
            wg.save_image_bytes(d / "z.png", b"")


if __name__ == "__main__":
    unittest.main()
