"""Tests for the Halloween theme and per-theme popup sounds.

Covers the 2026-10-11 addition:
  - the Halloween theme is registered in THEMES + THEME_DISPLAY_NAMES,
  - its palette carries the full Visual Refresh token set (a missing
    token would silently fall back via pal.get() everywhere),
  - THEME_POPUP_SOUNDS maps Halloween to a bundled sounds/ file,
  - ThemedDialog resolves the ghost-attack sound for Halloween only —
    every other theme still plays the frog ribbit,
  - a missing themed file falls back to the ribbit instead of muting.

No Tk window is created: ThemedDialog's sound resolution only reads
current_theme_name off the app object.

Run from the project root:
    python -m unittest discover -s tests -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app_themes
from app_themes import THEMES, THEME_DISPLAY_NAMES, THEME_POPUP_SOUNDS

SOUNDS_DIR = Path(app_themes.__file__).resolve().parent / "sounds"

try:
    from app import ThemedDialog
    _APP_IMPORTABLE = True
except Exception:  # pragma: no cover - e.g. tkinter missing in odd environments
    _APP_IMPORTABLE = False


class _AppStub:
    """Minimal app stand-in: the dialog only reads current_theme_name."""

    def __init__(self, theme):
        self.current_theme_name = theme


class TestHalloweenThemeRegistered(unittest.TestCase):

    def test_theme_registered_in_both_maps(self):
        self.assertIn("halloween", THEMES)
        self.assertIn("halloween", THEME_DISPLAY_NAMES)
        self.assertIn("Halloween", THEME_DISPLAY_NAMES["halloween"])

    def test_palette_has_full_token_set(self):
        """Halloween must define every key the flagship theme defines."""
        missing = set(THEMES["darkforest"]) - set(THEMES["halloween"])
        self.assertFalse(
            missing, f"halloween palette missing tokens: {sorted(missing)}"
        )

    def test_effect_tokens_present(self):
        pal = THEMES["halloween"]
        self.assertTrue(pal.get("glow_color"))
        self.assertGreater(pal.get("glow_intensity", 0), 0)
        self.assertGreater(pal.get("button_radius", 0), 0)


class TestPopupSoundMapping(unittest.TestCase):

    def test_every_override_file_exists(self):
        for theme, filename in THEME_POPUP_SOUNDS.items():
            self.assertIn(theme, THEMES, f"override for unknown theme {theme}")
            self.assertTrue(
                (SOUNDS_DIR / filename).is_file(),
                f"{theme} popup sound missing: {filename}",
            )

    def test_default_ribbit_still_bundled(self):
        self.assertTrue((SOUNDS_DIR / "frog-croak.mp3").is_file())


@unittest.skipUnless(_APP_IMPORTABLE, "app not importable")
class TestDialogSoundResolution(unittest.TestCase):

    def test_halloween_resolves_to_ghost_attack(self):
        dlg = ThemedDialog(_AppStub("halloween"))
        self.assertEqual(
            dlg._popup_sound_path().name, "halloween-ghost-attack.mp3"
        )

    def test_other_themes_resolve_to_ribbit(self):
        for theme in ("darkforest", "frogswamp", "neoncyber_light",
                      "studioneutral"):
            dlg = ThemedDialog(_AppStub(theme))
            self.assertEqual(dlg._popup_sound_path().name, "frog-croak.mp3")

    def test_missing_themed_file_falls_back_to_ribbit(self):
        from unittest.mock import patch

        with patch("app.THEME_POPUP_SOUNDS",
                   {"halloween": "no-such-file.mp3"}):
            dlg = ThemedDialog(_AppStub("halloween"))
            self.assertEqual(dlg._popup_sound_path().name, "frog-croak.mp3")


if __name__ == "__main__":
    unittest.main()
