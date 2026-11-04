"""Ctrl+N: random wallpaper when idle, the built prompt right after an edit."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app_generation_mixin import choose_generation_source


class TestChooseGenerationSource(unittest.TestCase):
    def test_nothing_on_screen_yet_rolls_random(self):
        self.assertEqual(choose_generation_source(False, False), "random")
        self.assertEqual(choose_generation_source(False, True), "random")

    def test_edited_prompt_is_honoured(self):
        self.assertEqual(choose_generation_source(True, True), "prompt")

    def test_untouched_prompt_rolls_random(self):
        self.assertEqual(choose_generation_source(True, False), "random")


if __name__ == "__main__":
    unittest.main()
