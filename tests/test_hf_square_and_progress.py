"""Hugging Face generates square, and the progress bars use the theme colour.

Two separate fixes:
  * its free queue drops wide requests, so HF always asks for a square image;
  * the progress bars were painted Windows blue by sv_ttk's re-theme, so they
    now use a FrogPaper style name sv_ttk does not touch.
"""

import pathlib
import sys
import unittest
from unittest import mock

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import wallpaper_generator as wg
from settings_providers import SettingsProvidersMixin


class TestHuggingFaceSquareSize(unittest.TestCase):
    def test_landscape_becomes_its_short_side(self):
        self.assertEqual(wg.huggingface_square_size(1920, 1080), 1072)

    def test_portrait_becomes_its_short_side(self):
        self.assertEqual(wg.huggingface_square_size(1080, 1920), 1072)

    def test_square_is_unchanged(self):
        self.assertEqual(wg.huggingface_square_size(1024, 1024), 1024)

    def test_always_divisible_by_16(self):
        for pair in ((1920, 1080), (2560, 1440), (1080, 1080), (1024, 768)):
            with self.subTest(size=pair):
                self.assertEqual(wg.huggingface_square_size(*pair) % 16, 0)

    def test_broken_input_falls_back_to_a_square(self):
        self.assertEqual(wg.huggingface_square_size(None, None), 1024)


class _Var:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class _Entry:
    def pack_forget(self):
        pass


class _StubApp:
    def __init__(self, provider):
        self.provider_var = _Var(provider)
        self.model_choice_var = _Var("")
        self.model_choice_combo = {}
        self.custom_model_entry = _Entry()
        self.dimension_preset_var = _Var("16:9 (1080p)")
        self.DIMENSION_PRESETS = {"16:9 (1080p)": "1920x1080", "Portrait": "1080x1920",
                                  "Square": "1024x1024"}
        self.PROVIDER_MODELS = {"Hugging Face Inference": {"options": ["Stable Diffusion 3 Medium (Free tier)"]},
                                "Pollinations.ai (Free - No Key)": {"options": ["flux"]}}


class TestProviderSwitchesToSquare(unittest.TestCase):
    def handler(self, provider, start="16:9 (1080p)", remember=None):
        mixin = SettingsProvidersMixin.__new__(SettingsProvidersMixin)
        mixin.app = _StubApp(provider)
        mixin.app.dimension_preset_var.set(start)
        if remember is not None:
            mixin.app._dimensions_before_huggingface = remember
        mixin._palette = {}
        with mock.patch.object(mixin, "_update_provider_description", lambda: None), \
             mock.patch.object(mixin, "_rebuild_provider_setup", lambda *a, **k: None):
            mixin._on_provider_changed()
        return mixin.app

    def test_hugging_face_selects_the_square_preset(self):
        app = self.handler("Hugging Face Inference")
        self.assertEqual(app.dimension_preset_var.get(), "Square")

    def test_other_providers_keep_the_users_choice(self):
        app = self.handler("Pollinations.ai (Free - No Key)")
        self.assertEqual(app.dimension_preset_var.get(), "16:9 (1080p)")

    def test_leaving_hugging_face_restores_the_previous_preset(self):
        app = self.handler("Pollinations.ai (Free - No Key)",
                           start="Square", remember="Portrait")
        self.assertEqual(app.dimension_preset_var.get(), "Portrait")
        self.assertIsNone(getattr(app, "_dimensions_before_huggingface", None))

    def test_leaving_hugging_face_without_a_memory_falls_back_to_16_9(self):
        app = self.handler("Pollinations.ai (Free - No Key)", start="Square")
        self.assertEqual(app.dimension_preset_var.get(), "16:9 (1080p)")

    def test_a_deliberate_non_square_choice_is_left_alone(self):
        app = self.handler("Pollinations.ai (Free - No Key)", start="Portrait", remember="Square")
        self.assertEqual(app.dimension_preset_var.get(), "Portrait")

    def test_switching_to_hugging_face_twice_keeps_the_first_memory(self):
        app = self.handler("Hugging Face Inference", start="16:9 (1080p)")
        self.assertEqual(app._dimensions_before_huggingface, "16:9 (1080p)")
        mixin = SettingsProvidersMixin.__new__(SettingsProvidersMixin)
        mixin.app = app
        mixin._palette = {}
        with mock.patch.object(mixin, "_update_provider_description", lambda: None), \
             mock.patch.object(mixin, "_rebuild_provider_setup", lambda *a, **k: None):
            mixin._on_provider_changed()
        self.assertEqual(app.dimension_preset_var.get(), "Square")


class TestProgressBarStyle(unittest.TestCase):
    """The bars must not use the style sv_ttk repaints."""

    def test_widgets_use_the_frogpaper_style(self):
        for name in ("app.py", "prompt_tab.py"):
            source = (REPO_ROOT / name).read_text(encoding="utf-8")
            self.assertIn('style="Frog.Horizontal.TProgressbar"', source, name)

    def test_style_is_configured_with_the_theme_accent(self):
        source = (REPO_ROOT / "app_theme_engine.py").read_text(encoding="utf-8")
        self.assertIn('"Frog.Horizontal.TProgressbar"', source)
        self.assertIn("troughcolor=pal[\"panel2\"]", source)
        self.assertIn("background=accent", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
