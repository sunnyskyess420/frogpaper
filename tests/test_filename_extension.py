"""Generated filenames must carry exactly one extension.

The app passes "frog_20260101_120000.png" and the generator appends ".png"
itself, which produced files called frog_20260101_120000.png.png in the gallery
and in every cloud sync listing.
"""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from wallpaper_generator import strip_image_extension


class TestStripImageExtension(unittest.TestCase):
    def test_single_extension_is_removed(self):
        self.assertEqual(strip_image_extension("frog_20260617_194111.png"),
                         "frog_20260617_194111")

    def test_other_image_extensions(self):
        for name in ("a.jpg", "a.jpeg", "a.webp", "a.bmp", "A.PNG"):
            with self.subTest(name=name):
                self.assertFalse(strip_image_extension(name).lower().endswith(
                    (".png", ".jpg", ".jpeg", ".webp", ".bmp")))

    def test_name_without_extension_is_untouched(self):
        self.assertEqual(strip_image_extension("daily_20260617"), "daily_20260617")

    def test_double_extension_collapses_one_level(self):
        # A file that already shipped as x.png.png becomes x.png, not x.png.png.png
        self.assertEqual(strip_image_extension("frog.png.png"), "frog.png")

    def test_extension_in_the_middle_is_kept(self):
        self.assertEqual(strip_image_extension("frog.png.backup"), "frog.png.backup")

    def test_blank_input(self):
        self.assertEqual(strip_image_extension(""), "")
        self.assertEqual(strip_image_extension(None), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
