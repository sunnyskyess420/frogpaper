"""Colour parsing must survive multi-word families and variations.

"forest green" is a family and "high contrast" / "washed out" are variations.
The old split-on-first-space parser returned "" for those, so a random prompt
silently lost its palette (seen in a user log as color='').
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app_prompt_data import COLOR_FAMILIES, COLOR_VARIATIONS
from prompt_tab import parse_color_value


class TestParseColorValue(unittest.TestCase):
    def test_simple_pair(self):
        self.assertEqual(parse_color_value("smoky amber", COLOR_FAMILIES, COLOR_VARIATIONS),
                         ("amber", "smoky"))

    def test_bare_family(self):
        self.assertEqual(parse_color_value("amber", COLOR_FAMILIES, COLOR_VARIATIONS),
                         ("amber", ""))

    def test_multi_word_family_alone(self):
        self.assertEqual(parse_color_value("forest green", COLOR_FAMILIES, COLOR_VARIATIONS),
                         ("forest green", ""))

    def test_multi_word_variation(self):
        self.assertEqual(parse_color_value("high contrast amber", COLOR_FAMILIES, COLOR_VARIATIONS),
                         ("amber", "high contrast"))

    def test_multi_word_both(self):
        self.assertEqual(
            parse_color_value("washed out forest green", COLOR_FAMILIES, COLOR_VARIATIONS),
            ("forest green", "washed out"))

    def test_invalid_is_empty(self):
        self.assertEqual(parse_color_value("tones", COLOR_FAMILIES, COLOR_VARIATIONS), ("", ""))

    def test_every_random_combination_round_trips(self):
        """Exactly what random_theme() builds, for every family."""
        for family in COLOR_FAMILIES:
            for variation in ("", "high contrast", "low contrast", "washed out", "smoky"):
                value = f"{variation} {family}".strip()
                self.assertEqual(
                    parse_color_value(value, COLOR_FAMILIES, COLOR_VARIATIONS),
                    (family, variation),
                    f"failed to parse {value!r}")


if __name__ == "__main__":
    unittest.main()
