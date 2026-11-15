"""The light Christmas theme must stay readable.

A light theme is only worth shipping if every foreground clears WCAG AA on the
surface it is actually painted on, and if it carries the same keys as its dark
sibling (apply_theme reads them directly).
"""

import pathlib
import re
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import app_themes as themes

KEY = "christmas_light"
HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


class TestSnowLightTheme(unittest.TestCase):
    def setUp(self):
        self.pal = themes.THEMES[KEY]

    def test_registered_for_the_picker(self):
        self.assertIn(KEY, themes.THEME_DISPLAY_NAMES)
        self.assertEqual(themes.THEME_INTERNAL_NAMES[themes.THEME_DISPLAY_NAMES[KEY]], KEY)

    def test_has_every_key_the_dark_theme_has(self):
        missing = set(themes.THEMES["christmas"]) - set(self.pal)
        self.assertEqual(missing, set(), f"apply_theme would KeyError on {sorted(missing)}")

    def test_colours_are_valid_hex(self):
        for name, value in self.pal.items():
            if isinstance(value, str) and value.startswith("#"):
                with self.subTest(key=name):
                    self.assertRegex(value, HEX)
            elif name == "actions":
                for colour in value:
                    self.assertRegex(colour, HEX)

    def test_background_is_actually_light(self):
        self.assertGreater(themes._rel_luminance(self.pal["bg"]), 0.5)

    def test_every_pair_clears_wcag_aa(self):
        pairs = {
            "text on bg": (self.pal["text"], self.pal["bg"]),
            "text on panel": (self.pal["text"], self.pal["panel"]),
            "text on panel2": (self.pal["text"], self.pal["panel2"]),
            "text on surface": (self.pal["text"], self.pal["surface"]),
            "text on entry": (self.pal["entryfg"], self.pal["entrybg"]),
            "muted on bg": (self.pal["muted"], self.pal["bg"]),
            "muted on panel": (self.pal["muted"], self.pal["panel"]),
            "accent on bg": (self.pal["accent"], self.pal["bg"]),
            "accent on panel": (self.pal["accent"], self.pal["panel"]),
            "button text": (self.pal["button_fg"], self.pal["panel2"]),
            "hover text": (self.pal["button_hover_fg"], self.pal["button_hover"]),
            "primary text": (self.pal["primary_button_fg"], self.pal["accent"]),
            "secondary text": (self.pal.get("secondary_button_fg", self.pal["button_fg"]),
                               self.pal.get("secondary_button_bg", self.pal["panel2"])),
            "selected text": (self.pal["selected_fg"], self.pal["selected_bg"]),
            "tag on panel2": (self.pal["tag_fg"], self.pal["panel2"]),
            "error on bg": (self.pal["error_color"], self.pal["bg"]),
            "warning on bg": (self.pal["warning_color"], self.pal["bg"]),
            "success on bg": (self.pal["success_color"], self.pal["bg"]),
        }
        for label, (fg, bg) in pairs.items():
            with self.subTest(pair=label):
                ratio = themes._contrast_ratio(fg, bg)
                self.assertGreaterEqual(round(ratio, 2), 4.5, f"{label}: {ratio:.2f}")

    def test_no_glow_or_haze_on_a_light_background(self):
        self.assertEqual(self.pal.get("glow_intensity", 0), 0)
        self.assertEqual(self.pal.get("mist_alpha", 0), 0)

    def test_popup_sound_matches_the_dark_theme(self):
        self.assertEqual(themes.THEME_POPUP_SOUNDS.get(KEY),
                         themes.THEME_POPUP_SOUNDS.get("christmas"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
