"""Real-app startup smoke test (regression guard for roadmap #7 Phase B2).

WHY THIS FILE EXISTS
--------------------
After the Phase B2 refactor moved apply_theme into app_theme_engine.py,
the module globals SV_TTK_AVAILABLE / sv_ttk / UI_EFFECTS_AVAILABLE /
ThemeTransition were left behind in app_runtime.py.  All 296 unit tests
stayed green because none of them instantiated the real FrogPaperApp --
the NameError only surfaced at first real launch on Windows:

    File "app_theme_engine.py", line 530, in apply_theme
        if SV_TTK_AVAILABLE:
    NameError: name 'SV_TTK_AVAILABLE' is not defined

This file closes that gap: it builds the FULL FrogPaperApp exactly like
app.main() does, re-themes EVERY palette, and drives the theme-change
handler end-to-end.  A future refactor that breaks the startup path now
fails here instead of on the user's desktop.

Run from the project root:
    python -m unittest discover -s tests -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# app.py binds ctypes.windll.user32 at import time (Windows-only API).
# Stub it on other platforms so the real app can be imported here.
import ctypes

if not hasattr(ctypes, "windll"):

    class _FakeWinDLL:
        def __getattr__(self, name):
            def _missing(*_a, **_k):
                raise OSError(
                    f"ctypes.windll.{name} unavailable on this platform"
                )

            return _missing

    ctypes.windll = _FakeWinDLL()  # type: ignore[attr-defined]


class TestAppStartupSmoke(unittest.TestCase):
    """Build the real FrogPaperApp and verify the theme engine works."""

    app = None
    root = None

    @classmethod
    def setUpClass(cls):
        import tkinter as tk

        try:
            root = tk.Tk()
            root.withdraw()
        except Exception as exc:  # no display (headless CI without Xvfb)
            raise unittest.SkipTest(f"No usable Tk display: {exc}")

        try:
            from app import FrogPaperApp

            cls.app = FrogPaperApp(root)
        except Exception:
            root.destroy()
            raise
        cls.root = root

    @classmethod
    def tearDownClass(cls):
        if cls.root is not None:
            try:
                cls.root.destroy()
            except Exception:
                pass

    def test_app_built_with_valid_theme(self):
        self.assertIsNotNone(self.app)
        from app_themes import THEMES

        self.assertIn(self.app.current_theme_name, THEMES)

    def test_theme_engine_module_globals_resolvable(self):
        """Direct regression: the B2 split left apply_theme's globals behind."""
        import app_theme_engine as eng

        for name in ("SV_TTK_AVAILABLE", "UI_EFFECTS_AVAILABLE",
                     "ThemeTransition"):
            self.assertTrue(
                hasattr(eng, name),
                f"app_theme_engine.{name} missing - apply_theme would "
                f"raise NameError at runtime",
            )
        # sv_ttk is bound iff the runtime probe found the package
        self.assertEqual(
            hasattr(eng, "sv_ttk"),
            eng.SV_TTK_AVAILABLE,
            "sv_ttk must be bound exactly when SV_TTK_AVAILABLE is True",
        )

    def test_apply_theme_every_palette(self):
        from app_themes import THEMES

        for name in THEMES:
            self.app.apply_theme(name)
            self.assertEqual(self.app.current_theme_name, name)

    def test_on_theme_changed_end_to_end(self):
        """Drive the combobox callback for real, minus the animation wait.

        on_theme_changed applies the theme from ThemeTransition's
        completion callback (root.after).  Pumping the Tk event loop to
        wait for it would also fire the app's deferred init tasks
        (keyword warmup, gallery populate, modal popups) -- not testable
        headless.  So the transition is swapped for an instant-apply
        double; the real animation is ui_effects' own concern and is
        untouched by the modularization.
        """
        from unittest.mock import patch

        from app_themes import THEME_INTERNAL_NAMES

        class _InstantTransition:
            def __init__(self, root):
                pass

            def start(self, old_palette, new_palette, target_widgets,
                      callback=None):
                if callback is not None:
                    callback()

        with patch("app_theme_engine.ThemeTransition", _InstantTransition):
            for display in list(THEME_INTERNAL_NAMES.keys())[:3]:
                self.app.theme_var.set(display)
                self.app.on_theme_changed()
                internal = THEME_INTERNAL_NAMES.get(display, "darkforest")
                self.assertEqual(self.app.current_theme_name, internal)

    def test_mro_mixin_design_intact(self):
        """Guard the Phase B2 mixin architecture from accidental changes."""
        from app import FrogPaperApp

        mro = [c.__name__ for c in FrogPaperApp.__mro__]
        self.assertEqual(
            mro,
            [
                "FrogPaperApp",
                "FrogPaperAppThemeMixin",
                "FrogPaperAppGenerationMixin",
                "FrogPaperAppSystemMixin",
                "FrogPaperAppCloudMixin",
                "FrogPaperAppDelegatesMixin",
                "object",
            ],
        )


if __name__ == "__main__":
    unittest.main()
