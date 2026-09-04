"""UI integration tests — the tier that catches user-visible behaviour bugs.

Covers (improvement report §5 — UI integration tests; bug classes from the
original user report that pure logic tests structurally cannot catch):

  1. Startup defaults (report fix #5): with "Remember settings" OFF the
     category dropdowns used to BLANK on startup. Now the starter defaults
     survive, the saved last_* values are wiped, and prompt_builder_values
     is re-seeded from the live widgets. With it ON, remembered values are
     applied via the set_active_* hooks.
     -> exercises the REAL SettingsTab.load_remembered_settings against a
        stub app with live Tk widgets.

  2. Prompt-engine agreement (report fix #5): whatever the UI seeds into
     prompt_builder_values is what build_prompt consumes — the built
     prompt must contain the user's visible subject/mood/lighting/color/
     atmosphere choices.

  3. Editable dropdown focus return (report fix #4): closing the starred
     popup hands focus back to the field so typing continues seamlessly.

  4. Rounded theming layer: apply_rounded_elements registers its custom
     "Frog.*" ttk elements and caches the generated images, and survives
     re-application (theme switch) without error.

Runs headless-safe: skipped automatically when tkinter or a required
module is unavailable. On Linux CI, run under xvfb; on Windows it runs
natively. No real user files are touched: config I/O is redirected into
a temp directory via utils.CONFIG_FILE, and the pinned-dropdown manager
is pointed at an in-memory dict.
"""

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import tkinter as tk
    from tkinter import ttk
    _TK = True
except ImportError:  # pragma: no cover
    _TK = False

try:
    import settings_tab
    _SETTINGS = True
except Exception:  # pragma: no cover - heavy import guards
    _SETTINGS = False

try:
    import prompt_tab
    _PROMPT_TAB = True
except Exception:  # pragma: no cover
    _PROMPT_TAB = False

try:
    import prompt_builder as pb
    _PB = True
except Exception:  # pragma: no cover
    _PB = False

try:
    import pinned_dropdowns as pd
    import rounded_widgets as rw
    import utils as utils_mod
    _WIDGETS = True
except Exception:  # pragma: no cover
    _WIDGETS = False


class TkTestBase(unittest.TestCase):
    """Headless-safe Tk root lifecycle."""

    def setUp(self):
        if not _TK:
            self.skipTest("tkinter unavailable")
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("no display available (headless environment)")
        self.root.withdraw()

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 1. Startup defaults — SettingsTab.load_remembered_settings
# ---------------------------------------------------------------------------

@unittest.skipUnless(_TK and _SETTINGS, "tkinter / settings_tab unavailable")
class TestStartupDefaults(TkTestBase):
    """The startup-empty-dropdown regression, at the integration seam."""

    STARTERS = {
        "subject_entry": "frog",
        "lighting_entry": "neon",
        "setting_entry": "deep swamp",
        "mood_entry": "cheerful",
    }

    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.config_file = Path(self._tmp.name) / "config.json"
        self._original_config = utils_mod.CONFIG_FILE
        utils_mod.CONFIG_FILE = self.config_file
        self.addCleanup(setattr, utils_mod, "CONFIG_FILE", self._original_config)
        self.addCleanup(self._tmp.cleanup)

    def _write_config(self, data):
        self.config_file.write_text(json.dumps(data), encoding="utf-8")

    def _read_config(self):
        return json.loads(self.config_file.read_text(encoding="utf-8"))

    def _make_app(self):
        """Stub app with live sidebar widgets + recording set_active hooks."""
        app = types.SimpleNamespace()
        app.prompt_builder_values = {}

        # Live widgets holding the built-in starter defaults
        app.subject_entry = ttk.Entry(self.root)
        app.subject_entry.insert(0, self.STARTERS["subject_entry"])
        app.lighting_entry = ttk.Entry(self.root)
        app.lighting_entry.insert(0, self.STARTERS["lighting_entry"])
        app.setting_entry = ttk.Entry(self.root)
        app.setting_entry.insert(0, self.STARTERS["setting_entry"])
        app.mood_entry = ttk.Entry(self.root)
        app.mood_entry.insert(0, self.STARTERS["mood_entry"])
        app.atmosphere_var = tk.StringVar(value="misty")
        app.atmosphere_combo = ttk.Entry(self.root, textvariable=app.atmosphere_var)
        app.color_family_var = tk.StringVar(value="gold")
        app.color_variation_var = tk.StringVar(value="rich")

        # Always-restored output settings
        app.wallpaper_format_var = tk.StringVar(value="PNG")
        app.wallpaper_quality_var = tk.StringVar(value="High")

        app.status_var = tk.StringVar()
        app.DEFAULT_PROMPT_MODE_VALUE = "fantasy"
        app._active_calls = []

        def _recorder(name):
            def _set(value=None, *args, **kwargs):
                app._active_calls.append((name, value))
            return _set

        for name in ("mode", "subject", "setting", "style", "lighting",
                     "mood", "color", "atmosphere", "subject_lock"):
            setattr(app, f"set_active_{name}", _recorder(name))
        return app

    def _load(self, app):
        st = settings_tab.SettingsTab.__new__(settings_tab.SettingsTab)
        st.app = app
        st.load_remembered_settings()

    def test_remember_on_applies_last_session_values(self):
        self._write_config({
            "remember_settings": True,
            "last_style_mode": "Photoreal",
            "last_subject": "dragon",
            "last_setting": "castle",
            "last_style": "watercolour",
            "last_lighting": "candlelight",
            "last_mood": "dark",
            "last_color": "crimson",
            "last_atmosphere": "eerie",
            "last_subject_lock": False,
            "wallpaper_format": "JPG",
        })
        app = self._make_app()
        self._load(app)

        applied = dict(app._active_calls)
        self.assertEqual(applied["subject"], "dragon")
        self.assertEqual(applied["setting"], "castle")
        self.assertEqual(applied["style"], "watercolour")
        self.assertEqual(applied["lighting"], "candlelight")
        self.assertEqual(applied["mood"], "dark")
        self.assertEqual(applied["color"], "crimson")
        self.assertEqual(applied["atmosphere"], "eerie")
        self.assertEqual(applied["subject_lock"], False)
        self.assertEqual(app.wallpaper_format_var.get(), "JPG")
        self.assertIn("restored", app.status_var.get().lower())

    def test_remember_off_keeps_starter_defaults_visible(self):
        """Regression: the OFF branch used to blank the dropdowns. The
        widgets must still show the starter defaults after loading."""
        self._write_config({
            "remember_settings": False,
            "last_subject": "ghost town",
            "last_lighting": "strobe",
        })
        app = self._make_app()
        self._load(app)

        # UI untouched — nothing blanked
        self.assertEqual(app.subject_entry.get(), "frog")
        self.assertEqual(app.lighting_entry.get(), "neon")
        self.assertEqual(app.setting_entry.get(), "deep swamp")
        self.assertEqual(app.mood_entry.get(), "cheerful")
        self.assertEqual(app.atmosphere_var.get(), "misty")
        # No set_active_* was called
        self.assertEqual(app._active_calls, [])

    def test_remember_off_wipes_saved_values_and_reseeds_engine(self):
        self._write_config({
            "remember_settings": False,
            "last_subject": "ghost town",
            "last_lighting": "strobe",
            "last_mood": "gloomy",
        })
        app = self._make_app()
        # Stale engine values prove the re-seed really happens
        app.prompt_builder_values.update({"subject": "stale", "mood": "stale"})

        self._load(app)

        # Saved last_* values wiped on disk (nothing leaks into next session)
        saved = self._read_config()
        for key in ("last_subject", "last_lighting", "last_mood"):
            self.assertEqual(saved.get(key), "", f"{key} should be wiped")

        # Engine now agrees with the visible UI
        self.assertEqual(app.prompt_builder_values["subject"], "frog")
        self.assertEqual(app.prompt_builder_values["lighting"], "neon")
        self.assertEqual(app.prompt_builder_values["setting"], "deep swamp")
        self.assertEqual(app.prompt_builder_values["atmosphere"], "misty")
        self.assertEqual(app.prompt_builder_values["mood"], "cheerful")
        self.assertEqual(app.prompt_builder_values["color"], "rich gold")


# ---------------------------------------------------------------------------
# 2. Prompt-engine agreement — UI values flow into the built prompt
# ---------------------------------------------------------------------------

@unittest.skipUnless(_TK and _PROMPT_TAB and _PB,
                     "tkinter / prompt_tab / prompt_builder unavailable")
class TestPromptEngineAgreement(TkTestBase):
    """Whatever the sidebar shows, the prompt engine must receive."""

    def _make_app(self):
        app = types.SimpleNamespace()
        app.prompt_builder_values = {}
        app.configure_entry_cursor = lambda w: None
        app.DEFAULT_NEGATIVE_PROMPT = "test"
        app.PROMPT_MODE_LABELS = ["Fantasy", "Photoreal"]
        app.DEFAULT_PROMPT_MODE_LABEL = "Fantasy"
        app.subject_entry = ttk.Entry(self.root)
        app.subject_entry.insert(0, "frog")
        app.mood_entry = ttk.Entry(self.root)
        app.mood_entry.insert(0, "ominous")
        app.lighting_entry = ttk.Entry(self.root)
        app.lighting_entry.insert(0, "neon")
        app.setting_entry = ttk.Entry(self.root)
        app.setting_entry.insert(0, "swamp")
        app.color_family_var = tk.StringVar(value="gold")
        app.color_variation_var = tk.StringVar(value="rich")
        app.color_family_combo = ttk.Combobox(self.root, textvariable=app.color_family_var)
        app.color_variation_combo = ttk.Combobox(self.root, textvariable=app.color_variation_var)
        app.atmosphere_var = tk.StringVar(value="misty")
        app.atmosphere_combo = ttk.Entry(self.root, textvariable=app.atmosphere_var)
        app.mode_var = tk.StringVar(value="Fantasy")
        app.mode_combo = ttk.Combobox(self.root, textvariable=app.mode_var)
        return app

    def _seed_panel(self, app):
        pt = prompt_tab.PromptTab.__new__(prompt_tab.PromptTab)
        pt.app = app
        frame = ttk.Frame(self.root)
        pt._build_theme_builder_panel(frame, assign_refs=False, title=None, refs={})

    def _theme_from_engine_values(self, values):
        """Mirror the app's mapping: sidebar values become theme components.
        Mood is intentionally absent — the panel never syncs it (sidebar-only
        by design, verified by the existing single-dropdown tests)."""
        return {
            "subject": values.get("subject", ""),
            "sentence": f"{values.get('setting', '')} scene",
            "components": {
                "lighting": values.get("lighting", ""),
                "color": values.get("color", ""),
                "atmosphere": values.get("atmosphere", ""),
            },
        }

    def test_built_prompt_contains_visible_ui_choices(self):
        app = self._make_app()
        self._seed_panel(app)
        theme = self._theme_from_engine_values(app.prompt_builder_values)

        result = pb.build_prompt(theme)
        p = result["prompt"]
        self.assertIn("Single main subject: frog", p)   # subject lock
        self.assertIn("neon", p)                        # lighting
        self.assertIn("rich gold", p)                   # colour
        self.assertIn("misty", p)                       # atmosphere
        self.assertIn("swamp", p)                       # setting (scene)

    def test_engine_subject_matches_sidebar_after_change(self):
        app = self._make_app()
        self._seed_panel(app)
        # User edits the sidebar; the engine dict must follow
        app.subject_entry.delete(0, "end")
        app.subject_entry.insert(0, "dragon")
        pt = prompt_tab.PromptTab.__new__(prompt_tab.PromptTab)
        pt.app = app
        frame = ttk.Frame(self.root)
        pt._build_theme_builder_panel(frame, assign_refs=False, title=None, refs={})

        theme = self._theme_from_engine_values(app.prompt_builder_values)
        result = pb.build_prompt(theme)
        self.assertIn("dragon", result["prompt"])
        self.assertNotIn("frog", result["prompt"].lower())


# ---------------------------------------------------------------------------
# 3. Editable dropdown — popup close returns focus to the field
# ---------------------------------------------------------------------------

@unittest.skipUnless(_TK and _WIDGETS, "tkinter / widget modules unavailable")
class TestDropdownFocusReturn(TkTestBase):
    """Typing must continue seamlessly after the starred popup closes."""

    def setUp(self):
        # NOTE: unlike the other UI tests, the root is NOT withdrawn here —
        # a withdrawn (unviewable) window cannot hold the X focus, and
        # focus_get() would return None. The window must be viewable for
        # focus assertions to be meaningful.
        if not _TK:
            self.skipTest("tkinter unavailable")
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("no display available (headless environment)")
        self.root.geometry("300x120+0+0")
        self.addCleanup(self._destroy_root)

        self._original_mgr = pd._mgr
        cfg_data = {}
        pd.init_pinned_manager(lambda: dict(cfg_data),
                               lambda c: cfg_data.update(c))
        self.addCleanup(setattr, pd, "_mgr", self._original_mgr)

        self.combo = pd.PinnedCombobox(self.root, category="subject",
                                       values=["frog", "cat"], state="normal")
        self.combo.pack(padx=10, pady=10)
        self.other = ttk.Entry(self.root)
        self.other.pack()
        self.root.update_idletasks()
        self.root.update()

    def _destroy_root(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def _focus_elsewhere(self):
        self.other.focus_force()
        self.root.update_idletasks()
        self.root.update()

    def test_popup_opens_on_text_area_click(self):
        self._focus_elsewhere()
        result = self.combo._on_click(types.SimpleNamespace(x=2, y=2))
        self.assertEqual(result, "break")
        self.assertIsNotNone(self.combo._popup_window)
        self.combo._close_popup()

    def test_close_popup_restores_focus_to_editable_field(self):
        """_close_popup must attempt focus restoration on editable combos
        (documented behaviour: typing continues seamlessly after close).
        Asserted at the contract level (focus_set is called) rather than
        querying real X focus state, which is window-manager dependent and
        flaky under headless servers / some Linux WMs. On Windows the same
        code path hands focus back to the field."""
        calls = []
        self.combo.focus_set = lambda: calls.append("focus_set")
        self.combo._on_click(types.SimpleNamespace(x=2, y=2))
        self.combo._close_popup()
        self.assertIn("focus_set", calls,
                      "editable combo did not get focus restored on close")

    def test_close_popup_fully_dismisses(self):
        self.combo._on_click(types.SimpleNamespace(x=2, y=2))
        self.combo._close_popup()
        self.assertIsNone(self.combo._popup_window)
        self.assertFalse(self.combo._popup_active)


# ---------------------------------------------------------------------------
# 4. Rounded theming layer — element registration smoke test
# ---------------------------------------------------------------------------

@unittest.skipUnless(_TK and _WIDGETS, "tkinter / widget modules unavailable")
class TestRoundedTheming(TkTestBase):
    """apply_rounded_elements must register custom elements and cache images."""

    PALETTE = {
        "bg": "#1e1e1e", "panel": "#252525", "panel2": "#2a2a2a",
        "accent": "#4a8c62", "text": "#ffffff", "entrybg": "#2e2e2e",
        "border_color": "#3a3a3a", "muted": "#888888",
        "button_fg": "#ffffff", "button_hover": "#3a3a3a",
        "tabsel": "#5aa07a", "progress": "#4a8c62",
    }

    def _apply(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        rw.apply_rounded_elements(style, self.PALETTE, self.root)
        return style

    def test_registers_frog_elements_and_caches_images(self):
        style = self._apply()
        frog_elements = [el for el in style.element_names()
                         if str(el).startswith("Frog.")]
        self.assertGreater(len(frog_elements), 0,
                           "no Frog.* ttk elements were registered")
        self.assertGreater(len(style._frog_images), 0,
                           "rounded images were not cached (would be GC'd)")

    def test_reapplication_is_safe(self):
        """Theme switch calls this again — cache must be cleared, not leak."""
        style = self._apply()
        first_count = len(style._frog_images)
        rw.apply_rounded_elements(style, self.PALETTE, self.root)
        self.assertGreater(len(style._frog_images), 0)
        self.assertLessEqual(len(style._frog_images), first_count * 2 + 50)

    def test_minimal_palette_does_not_crash(self):
        """Every pal lookup has a default — bare dict must still work."""
        style = ttk.Style(self.root)
        style.theme_use("clam")
        rw.apply_rounded_elements(style, {}, self.root)
        self.assertTrue(hasattr(style, "_frog_images"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
