"""Smoke test: the Theme Builder panel must NOT create duplicate category inputs.

After the "single dropdown per category" fix, the panel must reference the
sidebar's starred widgets instead of creating its own Subject / Mode /
Lighting / Color / Setting / Atmosphere fields. Style and Negative inputs
remain panel-owned (the sidebar has no equivalent).
"""

import sys
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
    import prompt_tab
    _PROMPT_TAB = True
except Exception:  # pragma: no cover - heavy import guards
    _PROMPT_TAB = False


@unittest.skipUnless(_TK and _PROMPT_TAB, "tkinter / prompt_tab unavailable")
class TestPanelSingleSource(unittest.TestCase):
    """All category refs must point at the sidebar widgets (identity check)."""

    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def _make_stub_app(self):
        app = types.SimpleNamespace()
        app.prompt_builder_values = {}
        app.configure_entry_cursor = lambda w: None
        app.DEFAULT_NEGATIVE_PROMPT = "test"
        app.PROMPT_MODE_LABELS = ["Fantasy", "Photoreal"]
        app.DEFAULT_PROMPT_MODE_LABEL = "Fantasy"

        # Sidebar "starred" widgets (plain stand-ins with the same interface)
        app.subject_entry = ttk.Entry(self.root)
        app.subject_entry.insert(0, "frog")
        app.mood_entry = ttk.Combobox(self.root, values=["serene", "epic"], state="readonly")
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

    def test_category_refs_point_at_sidebar_widgets(self):
        app = self._make_stub_app()
        pt = prompt_tab.PromptTab.__new__(prompt_tab.PromptTab)
        pt.app = app
        refs = {}
        frame = ttk.Frame(self.root)
        pt._build_theme_builder_panel(frame, assign_refs=False, title=None, refs=refs)

        # Identity: refs must BE the sidebar widgets, not panel copies
        self.assertIs(refs["subject_entry"], app.subject_entry)
        # Mood never had a panel field — it stays sidebar-only by design
        self.assertNotIn("mood_entry", refs)
        self.assertIs(refs["lighting_entry"], app.lighting_entry)
        self.assertIs(refs["setting_entry"], app.setting_entry)
        self.assertIs(refs["atmosphere_combo"], app.atmosphere_combo)
        self.assertIs(refs["atmosphere_var"], app.atmosphere_var)
        self.assertIs(refs["color_family_var"], app.color_family_var)
        self.assertIs(refs["color_variation_var"], app.color_variation_var)
        self.assertIs(refs["mode_var"], app.mode_var)
        self.assertIs(refs["mode_combo"], app.mode_combo)

    def test_style_stays_panel_owned(self):
        app = self._make_stub_app()
        pt = prompt_tab.PromptTab.__new__(prompt_tab.PromptTab)
        pt.app = app
        refs = {}
        frame = ttk.Frame(self.root)
        pt._build_theme_builder_panel(frame, assign_refs=False, title=None, refs=refs)

        # Style has no sidebar equivalent — the panel owns it
        self.assertIn("style_entry", refs)
        self.assertIsNot(refs["style_entry"], getattr(app, "subject_entry", None))
        self.assertIn("negative_prompt_entry", refs)

    def test_values_seeded_from_sidebar(self):
        app = self._make_stub_app()
        pt = prompt_tab.PromptTab.__new__(prompt_tab.PromptTab)
        pt.app = app
        frame = ttk.Frame(self.root)
        pt._build_theme_builder_panel(frame, assign_refs=False, title=None, refs={})

        self.assertEqual(app.prompt_builder_values["subject"], "frog")
        self.assertEqual(app.prompt_builder_values["lighting"], "neon")
        self.assertEqual(app.prompt_builder_values["setting"], "swamp")
        self.assertEqual(app.prompt_builder_values["atmosphere"], "misty")
        self.assertEqual(app.prompt_builder_values["color"], "rich gold")

    def test_no_duplicate_category_labels_in_panel(self):
        app = self._make_stub_app()
        pt = prompt_tab.PromptTab.__new__(prompt_tab.PromptTab)
        pt.app = app
        frame = ttk.Frame(self.root)
        panel = pt._build_theme_builder_panel(frame, assign_refs=False, title=None, refs={})

        removed = {"Subject:", "Mode:", "Lighting:", "Color:", "Modifier:",
                   "Setting:", "Atmosphere:"}
        found = []

        def walk(w):
            for child in w.winfo_children():
                if isinstance(child, tk.Label):
                    try:
                        found.append(child.cget("text"))
                    except Exception:
                        pass
                walk(child)

        walk(panel)
        for label in found:
            for gone in removed:
                self.assertFalse(str(label).startswith(gone),
                                 f"duplicate field still in panel: {label}")

    def test_text_area_click_shows_starred_popup_not_native(self):
        """Regression: clicking the WORDS of an editable combobox used to
        fall through to the native (starless) ttk dropdown. Now every click
        opens the starred popup and suppresses the native list."""
        import types
        import pinned_dropdowns as pd

        original_mgr = pd._mgr
        try:
            cfg_data = {}
            pd.init_pinned_manager(lambda: dict(cfg_data),
                                   lambda c: cfg_data.update(c))
            combo = pd.PinnedCombobox(self.root, category="subject",
                                      values=["frog", "cat"], state="normal")
            combo.pack()
            self.root.update_idletasks()
            self.root.update()

            # Simulate a click on the TEXT AREA (left side, not the arrow)
            result = combo._on_click(types.SimpleNamespace(x=2, y=2))
            self.assertEqual(result, "break")
            self.assertIsNotNone(combo._popup_window)
            combo._close_popup()
            self.assertIsNone(combo._popup_window)
        finally:
            pd._mgr = original_mgr


if __name__ == "__main__":
    unittest.main(verbosity=2)
