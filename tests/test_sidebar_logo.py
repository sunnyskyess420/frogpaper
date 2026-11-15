"""Sidebar logo resolution.

A theme variant inherits its family's badge: a theme called christmas_light has
no logo file of its own, but it must still show the Christmas one instead of the
plain frog.
"""

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app_themes import resolve_sidebar_logo


class TestResolveSidebarLogo(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def touch(self, name: str) -> pathlib.Path:
        path = self.root / name
        path.write_bytes(b"png")
        return path

    def test_exact_theme_logo_wins(self):
        exact = self.touch("sidebar_logo_christmas_light.png")
        self.touch("sidebar_logo_christmas.png")
        self.touch("sidebar_logo.png")
        self.assertEqual(resolve_sidebar_logo("christmas_light", self.root), exact)

    def test_variant_inherits_family_logo(self):
        family = self.touch("sidebar_logo_christmas.png")
        self.touch("sidebar_logo.png")
        self.assertEqual(resolve_sidebar_logo("christmas_light", self.root), family)

    def test_unknown_theme_falls_back_to_default(self):
        default = self.touch("sidebar_logo.png")
        self.assertEqual(resolve_sidebar_logo("darkforest", self.root), default)

    def test_extension_order_prefers_png(self):
        png = self.touch("sidebar_logo_christmas.png")
        self.touch("sidebar_logo_christmas.jpg")
        self.assertEqual(resolve_sidebar_logo("christmas", self.root), png)

    def test_jpg_accepted_when_no_png(self):
        jpg = self.touch("sidebar_logo_halloween.jpg")
        self.touch("sidebar_logo.png")
        self.assertEqual(resolve_sidebar_logo("halloween", self.root), jpg)

    def test_missing_default_returns_expected_path(self):
        expected = self.root / "sidebar_logo.png"
        self.assertEqual(resolve_sidebar_logo("darkforest", self.root), expected)
        self.assertFalse(expected.exists())

    def test_blank_theme_name_is_safe(self):
        default = self.touch("sidebar_logo.png")
        self.assertEqual(resolve_sidebar_logo("", self.root), default)
        self.assertEqual(resolve_sidebar_logo(None, self.root), default)


class TestShippedLogos(unittest.TestCase):
    """What the repo actually ships must resolve for the Christmas themes."""

    ROOT = pathlib.Path(__file__).resolve().parent.parent

    def test_dark_christmas_uses_its_own_badge(self):
        path = resolve_sidebar_logo("christmas", self.ROOT)
        self.assertEqual(path.name, "sidebar_logo_christmas.png")
        self.assertTrue(path.exists())

    def test_light_christmas_inherits_the_badge(self):
        path = resolve_sidebar_logo("christmas_light", self.ROOT)
        self.assertEqual(path.name, "sidebar_logo_christmas.png")
        self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
