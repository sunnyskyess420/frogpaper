"""A seasonal edition must suggest, never impose.

The Christmas Edition used to rewrite `app_theme` to "christmas" once, so a
returning user's app would repaint itself red and green on first launch - the
kind of thing that reads as "Christmas shoved at me". The theme now ships in the
picker and nothing is applied on the user's behalf.
"""

import pathlib
import sys
import unittest
from unittest import mock

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import app


class TestEditionDefaults(unittest.TestCase):
    def setUp(self):
        # _apply_edition_defaults writes through save_config; never let a test
        # touch the real config.json.
        self._patch = mock.patch.object(app, "save_config", lambda cfg: None)
        self._patch.start()
        self.addCleanup(self._patch.stop)

    def apply(self, config):
        return app._apply_edition_defaults(dict(config))

    def test_never_switches_an_existing_theme(self):
        result = self.apply({"app_theme": "lightocean"})
        self.assertEqual(result["app_theme"], "lightocean")

    def test_does_not_invent_a_theme(self):
        result = self.apply({})
        self.assertNotIn("app_theme", result,
                         "the festive theme must only be applied when the user picks it")

    def test_keeps_a_saved_colour(self):
        result = self.apply({"remember_settings": True, "last_color": "satin ivory"})
        self.assertEqual(result["last_color"], "satin ivory")

    def test_fills_a_blank_colour_when_remembering(self):
        result = self.apply({"remember_settings": True, "last_color": ""})
        self.assertIn("red", result["last_color"])

    def test_leaves_colour_alone_when_not_remembering(self):
        result = self.apply({"remember_settings": False, "last_color": ""})
        self.assertEqual(result["last_color"], "")

    def test_fills_a_blank_startup_subject_only(self):
        blank = self.apply({"startup_subject": ""})
        self.assertEqual(blank["startup_subject"], app.DEFAULT_STARTUP_SUBJECT)

        chosen = self.apply({"startup_subject": "fox"})
        self.assertEqual(chosen["startup_subject"], "fox")

    def test_runs_once_per_edition(self):
        first = self.apply({"startup_subject": ""})
        flag = app.APP_EDITION.lower().replace(" ", "_") + "_applied"
        self.assertTrue(first[flag])

        second = self.apply({flag: True, "startup_subject": ""})
        self.assertEqual(second.get("startup_subject"), "",
                         "a second launch must not re-apply edition defaults")

    def test_no_op_without_an_edition(self):
        with mock.patch.object(app, "APP_EDITION", ""):
            result = self.apply({"startup_subject": ""})
        self.assertEqual(result, {"startup_subject": ""})


class TestFreshInstallTheme(unittest.TestCase):
    def test_default_theme_is_not_the_festive_one(self):
        self.assertNotEqual(app.DEFAULT_APP_THEME, "christmas")

    def test_default_theme_exists_in_the_picker(self):
        from app_themes import THEMES, THEME_DISPLAY_NAMES
        self.assertIn(app.DEFAULT_APP_THEME, THEMES)
        self.assertIn(app.DEFAULT_APP_THEME, THEME_DISPLAY_NAMES)

    def test_festive_theme_is_still_offered(self):
        from app_themes import THEMES, THEME_DISPLAY_NAMES
        for key in ("christmas", "christmas_light"):
            with self.subTest(theme=key):
                self.assertIn(key, THEMES)
                self.assertIn(key, THEME_DISPLAY_NAMES)


if __name__ == "__main__":
    unittest.main(verbosity=2)
