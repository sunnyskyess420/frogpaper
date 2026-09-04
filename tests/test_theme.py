"""Unit tests for theme.py — FrogPaper's shared visual constants.

Verifies:
  - color math (adjust/lighten/darken, clamping, invalid input safety)
  - WCAG contrast logic (ensure_contrast, including the '#' re-prefix fix)
  - the shared constants exist and are the SINGLE source
    (settings_tab / settings_components / pinned_dropdowns all reference
    the same objects — no more duplicated definitions)

Run from the project root:
    python -m unittest discover -s tests -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import theme
from theme import (
    STATUS_COLORS,
    PIN_MARKER_ON,
    PIN_MARKER_OFF,
    COLOR_STAR_ON,
    FONT_FAMILY,
    FALLBACK_POPUP_COLORS,
    adjust_color,
    lighten,
    darken,
    ensure_contrast,
    Tooltip,
)


class TestAdjustColor(unittest.TestCase):
    """The one lighten/darken implementation (used by 3 modules)."""

    def test_lighten(self):
        self.assertEqual(adjust_color("#000000", 16), "#101010")

    def test_darken(self):
        self.assertEqual(adjust_color("#2a2a3e", -14), "#1c1c30")

    def test_clamps_at_white(self):
        self.assertEqual(adjust_color("#f0f0f0", 255), "#ffffff")

    def test_clamps_at_black(self):
        self.assertEqual(adjust_color("#101010", -255), "#000000")

    def test_lighten_wrapper_takes_abs(self):
        self.assertEqual(lighten("#000000", 30), "#1e1e1e")
        self.assertEqual(lighten("#000000", -30), "#1e1e1e")

    def test_darken_wrapper_takes_abs(self):
        self.assertEqual(darken("#ffffff", 30), "#e1e1e1")
        self.assertEqual(darken("#ffffff", -30), "#e1e1e1")

    def test_invalid_input_returns_original(self):
        self.assertEqual(adjust_color("not-a-color", 10), "not-a-color")
        self.assertEqual(adjust_color("#12345", 10), "#12345")
        self.assertEqual(adjust_color("", 10), "")

    def test_none_input_returns_none(self):
        self.assertIsNone(adjust_color(None, 10))

    def test_three_digit_hex_not_supported_returns_original(self):
        self.assertEqual(adjust_color("#f00", 10), "#f00")


class TestEnsureContrast(unittest.TestCase):
    """WCAG contrast guard for popup colors."""

    def test_high_contrast_fg_returned_re_prefixed(self):
        # Regression test: fg without '#' must come back WITH the '#',
        # otherwise Tk raises "unknown color name".
        self.assertEqual(ensure_contrast("#1e1e1e", "f0fff0", "#ffffff"), "#f0fff0")

    def test_low_contrast_uses_fallback(self):
        # #888888 on #777777 is ~1.3:1; white on #777777 is ~4.5:1
        self.assertEqual(ensure_contrast("#777777", "#888888", "#ffffff"), "#ffffff")

    def test_both_low_forces_white_on_dark_bg(self):
        self.assertEqual(ensure_contrast("#777777", "#888888", "#999999"), "#ffffff")

    def test_both_low_forces_black_on_light_bg(self):
        self.assertEqual(ensure_contrast("#eeeeee", "#dddddd", "#cccccc"), "#1a1a1a")

    def test_broken_input_returns_fallback(self):
        self.assertEqual(ensure_contrast("zzz", "#ffffff", "#f5f5f5"), "#f5f5f5")


class TestSharedConstants(unittest.TestCase):
    """The constants every module now shares."""

    def test_status_colors_complete(self):
        self.assertEqual(
            set(STATUS_COLORS),
            {"connected", "not_connected", "error", "success", "warning", "info"},
        )

    def test_pin_markers_are_the_one_standard(self):
        self.assertEqual(PIN_MARKER_ON, "★")
        self.assertEqual(PIN_MARKER_OFF, "☆")

    def test_star_color_is_gold(self):
        self.assertEqual(COLOR_STAR_ON, "#FFD700")

    def test_font_family(self):
        self.assertEqual(FONT_FAMILY, "Segoe UI")

    def test_fallback_popup_palette_complete(self):
        self.assertEqual(
            set(FALLBACK_POPUP_COLORS),
            {"bg", "fg", "hover", "selected_bg", "selected_fg",
             "header_fg", "separator", "star_off", "star_on"},
        )


class TestSingleSource(unittest.TestCase):
    """Duplicated definitions must be gone — everyone points at theme.py."""

    def test_settings_tab_reexports_theme_colors(self):
        import settings_tab
        self.assertIs(settings_tab.STATUS_COLORS, theme.STATUS_COLORS)

    def test_cloud_provider_card_uses_shared_colors(self):
        import settings_components
        self.assertIs(
            settings_components.CloudProviderCard.STATUS_COLORS,
            theme.STATUS_COLORS,
        )

    def test_pinned_dropdowns_delegates_contrast_to_theme(self):
        from pinned_dropdowns import PinnedCombobox
        bg, fg, fb = "#1e1e1e", "f0fff0", "#ffffff"
        self.assertEqual(
            PinnedCombobox._ensure_contrast(bg, fg, fb),
            theme.ensure_contrast(bg, fg, fb),
        )

    def test_pinned_dropdowns_delegates_color_math_to_theme(self):
        from pinned_dropdowns import PinnedCombobox
        widget = PinnedCombobox.__new__(PinnedCombobox)  # no Tk needed
        self.assertEqual(widget._adjust_color("#101010", 32), adjust_color("#101010", 32))


class TestTooltipClass(unittest.TestCase):
    def test_tooltip_is_a_class(self):
        self.assertTrue(isinstance(Tooltip, type))


if __name__ == "__main__":
    unittest.main(verbosity=2)
