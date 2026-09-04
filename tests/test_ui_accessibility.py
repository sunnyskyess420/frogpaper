"""Keyboard accessibility + focus visibility tests (improvement report §2).

Covers the "UI leftovers" accessibility slice:
  - ui_effects.enable_keyboard_activation: Label-based custom buttons
    become Tab-reachable, get a visible focus ring, and activate on
    Enter / Space.
  - RoundedButton: same contract, plus invoke() and no-command safety.
  - focus_ring_color: the ring always contrasts with the resting
    background on dark AND light themes.
  - ensure_visible_focus_indicators: every classic (tk) button-like
    widget in the tree gets visible focus colors; ttk widgets and plain
    labels are left alone.
  - pinned_dropdowns.compute_popup_width: popup fits the longest item
    (high-DPI fix), clamped, robust to bad items — pure function, no
    display needed.
  - Dropdown popup rows: stars and item labels are keyboard operable;
    Enter on an item selects it and closes the popup; Enter on a star
    toggles the pin.
  - make_text_tab_friendly: Text widgets never trap Tab — editable Text
    (negative-prompt Preview) moves focus on Tab / Shift-Tab instead of
    inserting a tab character; read-only Text (prompt preview, tutorial
    steps, setup guides) is removed from the Tab ring entirely.

Runs headless-safe: Tk tests skip automatically without a display (on
Linux CI run under xvfb; on Windows they run natively). No user files
are touched: the pinned-dropdown manager is pointed at an in-memory dict.
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
    import ui_effects as ue
    _UE = True
except Exception:  # pragma: no cover - PIL missing in odd environments
    _UE = False

try:
    import pinned_dropdowns as pd
    _PD = True
except Exception:  # pragma: no cover
    _PD = False


class TkTestBase(unittest.TestCase):
    """Headless-safe Tk root lifecycle (same pattern as test_ui_integration)."""

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

    def _focus(self, widget):
        """Force keyboard focus onto widget so key events dispatch.

        focus_set() only *requests* focus from the window manager; under
        Xvfb (no WM) the request is never granted and key events go
        nowhere. focus_force() bypasses the WM and works everywhere.
        """
        self.root.deiconify()
        self.root.update()
        widget.focus_force()
        self.root.update()


# ═══════════════════════════════════════════════════════════════════════════
#  Pure logic: popup width + focus ring color
# ═══════════════════════════════════════════════════════════════════════════

@unittest.skipUnless(_PD, "pinned_dropdowns unavailable")
class TestComputePopupWidth(unittest.TestCase):
    """The popup must fit its longest item (old code: fixed 260px)."""

    def test_short_items_use_min_width(self):
        measure = lambda s: len(s) * 7
        self.assertEqual(pd.compute_popup_width(measure, ["frog", "cat"]), 260)

    def test_long_item_widens_popup_to_max(self):
        measure = lambda s: len(s) * 7
        width = pd.compute_popup_width(measure, ["a" * 80])
        self.assertEqual(width, 420)  # clamped to max_width

    def test_medium_item_sized_to_fit(self):
        measure = lambda s: len(s) * 7
        # 40 chars * 7 = 280 + 78 chrome = 358 (between min and max)
        self.assertEqual(pd.compute_popup_width(measure, ["a" * 40]), 358)

    def test_empty_or_missing_items(self):
        measure = lambda s: len(s) * 7
        self.assertEqual(pd.compute_popup_width(measure, []), 260)
        self.assertEqual(pd.compute_popup_width(measure, None), 260)

    def test_custom_bounds(self):
        measure = lambda s: len(s) * 7
        self.assertEqual(
            pd.compute_popup_width(measure, ["a" * 30], min_width=100,
                                   max_width=200, chrome=10), 200)
        self.assertEqual(
            pd.compute_popup_width(measure, ["a" * 5], min_width=100,
                                   max_width=200, chrome=10), 100)

    def test_robust_against_bad_items_and_measures(self):
        calls = []
        def measure(s):
            if s == "boom":
                raise ValueError("cannot measure")
            calls.append(s)
            return len(s) * 7
        width = pd.compute_popup_width(measure, ["ok", "boom", None])
        self.assertEqual(width, 260)  # only "ok" measured -> tiny -> min
        self.assertIn("ok", calls)    # items measured lowercased
        self.assertNotIn("boom", calls)

    def test_measure_receives_lowercased_item(self):
        seen = []
        pd.compute_popup_width(lambda s: (seen.append(s), 10)[1], ["FROG"])
        self.assertEqual(seen, ["frog"])


class TestFocusRingColor(unittest.TestCase):
    """The focus ring must be visible on dark AND light resting colors."""

    def test_dark_background_gets_lighter_ring(self):
        ring = ue.focus_ring_color("#263322")
        self.assertNotEqual(ring, "#263322")
        def chan(h):
            h = h.lstrip("#")
            return int(h[0:2], 16) + int(h[2:4], 16) + int(h[4:6], 16)
        self.assertGreater(chan(ring), chan("#263322"))

    def test_light_background_gets_darker_ring(self):
        ring = ue.focus_ring_color("#f0f0f0")
        self.assertNotEqual(ring, "#f0f0f0")
        def chan(h):
            h = h.lstrip("#")
            return int(h[0:2], 16) + int(h[2:4], 16) + int(h[4:6], 16)
        self.assertLess(chan(ring), chan("#f0f0f0"))

    def test_ring_differs_from_background_for_mid_greys(self):
        for bg in ("#808080", "#5aad78", "#1f2937"):
            self.assertNotEqual(ue.focus_ring_color(bg), bg)


# ═══════════════════════════════════════════════════════════════════════════
#  enable_keyboard_activation + RoundedButton (need a display)
# ═══════════════════════════════════════════════════════════════════════════

@unittest.skipUnless(_TK and _UE, "tkinter / ui_effects unavailable")
class TestEnableKeyboardActivation(TkTestBase):
    """Bare Label-based buttons become first-class keyboard citizens."""

    def test_focus_config_applied(self):
        label = tk.Label(self.root, text="btn", bg="#1f2937")
        ue.enable_keyboard_activation(label, lambda: None, "#1f2937")
        self.assertEqual(int(label.cget("takefocus")), 1)
        self.assertEqual(int(label.cget("highlightthickness")), 2)
        self.assertNotEqual(label.cget("highlightcolor"),
                            label.cget("highlightbackground"))

    def test_custom_ring_color_honored(self):
        label = tk.Label(self.root, text="btn", bg="#1f2937")
        ue.enable_keyboard_activation(label, lambda: None, "#1f2937",
                                      ring_color="#ff8800")
        self.assertEqual(label.cget("highlightcolor"), "#ff8800")

    def test_return_activates_command(self):
        calls = []
        label = tk.Label(self.root, text="btn", bg="#1f2937")
        ue.enable_keyboard_activation(label, lambda: calls.append(1), "#1f2937")
        label.pack()
        self._focus(label)
        label.event_generate("<Return>")
        self.root.update()
        self.assertEqual(calls, [1])

    def test_space_activates_command(self):
        calls = []
        label = tk.Label(self.root, text="btn", bg="#1f2937")
        ue.enable_keyboard_activation(label, lambda: calls.append(1), "#1f2937")
        label.pack()
        self._focus(label)
        label.event_generate("<space>")
        self.root.update()
        self.assertEqual(calls, [1])

    def test_failing_command_does_not_propagate(self):
        def bad():
            raise RuntimeError("handler bug")
        label = tk.Label(self.root, text="btn", bg="#1f2937")
        ue.enable_keyboard_activation(label, bad, "#1f2937")
        label.pack()
        self._focus(label)
        label.event_generate("<Return>")  # must not raise
        self.root.update()


@unittest.skipUnless(_TK and _UE, "tkinter / ui_effects unavailable")
class TestRoundedButtonKeyboard(TkTestBase):
    """The Generate-Image style button is now keyboard operable."""

    def _make(self, command=None):
        return ue.RoundedButton(self.root, text="Generate Image",
                                width=120, height=34,
                                fill_color="#2a6644", command=command)

    def test_focus_ring_configured(self):
        btn = self._make()
        label = btn._label
        self.assertEqual(int(label.cget("takefocus")), 1)
        self.assertEqual(int(label.cget("highlightthickness")), 2)
        self.assertNotEqual(label.cget("highlightcolor"),
                            label.cget("highlightbackground"))

    def test_return_fires_command(self):
        calls = []
        btn = self._make(command=lambda: calls.append(1))
        btn.pack()
        self._focus(btn._label)
        btn._label.event_generate("<Return>")
        self.root.update()
        self.assertEqual(calls, [1])

    def test_space_fires_command(self):
        calls = []
        btn = self._make(command=lambda: calls.append(1))
        btn.pack()
        self._focus(btn._label)
        btn._label.event_generate("<space>")
        self.root.update()
        self.assertEqual(calls, [1])

    def test_invoke_programmatic(self):
        calls = []
        btn = self._make(command=lambda: calls.append(1))
        btn.invoke()
        self.assertEqual(calls, [1])

    def test_no_command_is_safe(self):
        btn = self._make(command=None)
        btn.invoke()          # must not raise
        btn._label.event_generate("<Return>")
        self.root.update()


@unittest.skipUnless(_TK and _UE, "tkinter / ui_effects unavailable")
class TestFocusIndicatorWalk(TkTestBase):
    """Classic tk buttons get visible focus colors; ttk/labels untouched."""

    def test_classic_buttons_get_ring_colors(self):
        border, ring = "#333333", "#5aad78"
        frame = tk.Frame(self.root)
        btn = tk.Button(frame, text="b", highlightthickness=0)
        check = tk.Checkbutton(frame, text="c", highlightthickness=0)
        radio = tk.Radiobutton(frame, text="r", highlightthickness=0)
        btn.pack(); check.pack(); radio.pack(); frame.pack()
        ue.ensure_visible_focus_indicators(self.root, border, ring)
        for w in (btn, check, radio):
            self.assertGreaterEqual(int(w.cget("highlightthickness")), 1)
            self.assertEqual(w.cget("highlightbackground"), border)
            self.assertEqual(w.cget("highlightcolor"), ring)

    def test_labels_and_tttk_untouched(self):
        border, ring = "#333333", "#5aad78"
        from tkinter import ttk
        frame = tk.Frame(self.root)
        plain = tk.Label(frame, text="plain", highlightthickness=0)
        tbtn = ttk.Button(frame, text="ttk")
        plain.pack(); tbtn.pack(); frame.pack()
        ue.ensure_visible_focus_indicators(self.root, border, ring)
        self.assertEqual(int(plain.cget("highlightthickness")), 0)
        self.assertTrue(tbtn.winfo_exists())  # skipped without error

    def test_deep_nesting_reached(self):
        border, ring = "#333333", "#5aad78"
        outer = tk.Frame(self.root)
        mid = tk.Frame(outer)
        deep = tk.Button(mid, text="deep", highlightthickness=0)
        mid.pack(); outer.pack()
        ue.ensure_visible_focus_indicators(self.root, border, ring)
        self.assertEqual(deep.cget("highlightcolor"), ring)


# ═══════════════════════════════════════════════════════════════════════════
#  Dropdown popup rows: stars + items keyboard operable (need a display)
# ═══════════════════════════════════════════════════════════════════════════

@unittest.skipUnless(_TK and _PD, "tkinter / pinned_dropdowns unavailable")
class TestPopupKeyboardOperable(TkTestBase):

    def setUp(self):
        super().setUp()
        self._original_mgr = pd._mgr
        self.cfg_data = {}
        pd.init_pinned_manager(lambda: dict(self.cfg_data),
                               lambda c: self.cfg_data.update(c))
        self.addCleanup(setattr, pd, "_mgr", self._original_mgr)

    def _make_combo(self, values):
        combo = pd.PinnedCombobox(self.root, category="subject",
                                  values=values, state="normal")
        combo.pack()
        self.root.update_idletasks()
        self.root.update()
        return combo

    def _open_popup(self, combo):
        result = combo._on_click(types.SimpleNamespace(x=2, y=2))
        self.assertEqual(result, "break")
        self.assertIsNotNone(combo._popup_window)
        self.root.update()
        return combo._popup_window

    def _popup_labels(self, popup):
        found = []

        def walk(w):
            for child in w.winfo_children():
                if isinstance(child, tk.Label):
                    found.append(child)
                walk(child)

        walk(popup)
        return found

    def _find_row(self, popup, item_text):
        """Return (star_label, item_label) for the row showing item_text.

        Popup rows are (star, item) label pairs inside row frames; items
        render lowercased and may be sorted, so never assume list order.
        """
        def walk(w):
            for child in w.winfo_children():
                if isinstance(child, tk.Frame):
                    labels = [c for c in child.winfo_children()
                              if isinstance(c, tk.Label)]
                    stars = [c for c in labels
                             if c.cget("text") in ("★", "☆")]
                    items = [c for c in labels
                             if c.cget("text") not in ("★", "☆")]
                    if stars and items and items[0].cget("text") == item_text:
                        return (stars[0], items[0])
                found = walk(child)
                if found:
                    return found
            return None
        return walk(popup)

    def test_rows_are_keyboard_reachable(self):
        combo = self._make_combo(["frog", "cat", "dragon"])
        popup = self._open_popup(combo)
        labels = [w for w in self._popup_labels(popup)
                  if w.cget("text") in ("★", "☆", "frog", "cat", "dragon")]
        self.assertTrue(labels, "popup rows not found")
        for w in labels:
            self.assertEqual(int(w.cget("takefocus")), 1)
            self.assertEqual(int(w.cget("highlightthickness")), 2)
        combo._close_popup()

    def test_enter_on_item_selects_and_closes(self):
        combo = self._make_combo(["frog", "cat", "dragon"])
        popup = self._open_popup(combo)
        row = self._find_row(popup, "cat")
        self.assertIsNotNone(row, "'cat' row not found in popup")
        _, cat_label = row
        self._focus(cat_label)
        cat_label.event_generate("<Return>")
        self.root.update()
        self.assertEqual(combo.get(), "cat")
        self.assertIsNone(combo._popup_window)  # popup closed after selection

    def test_enter_on_star_toggles_pin(self):
        combo = self._make_combo(["frog", "cat"])
        popup = self._open_popup(combo)
        row = self._find_row(popup, "frog")
        self.assertIsNotNone(row, "'frog' row not found in popup")
        star, _ = row
        self.assertEqual(star.cget("text"), "☆")
        self._focus(star)
        star.event_generate("<Return>")
        self.root.update()
        pinned = self.cfg_data.get("pinned_options", {}).get("subject", [])
        self.assertIn("frog", pinned)
        combo._close_popup()

    def test_popup_canvas_fits_longest_item(self):
        combo = self._make_combo(["a" * 60])
        popup = self._open_popup(combo)
        canvases = []

        def walk(w):
            for child in w.winfo_children():
                if isinstance(child, tk.Canvas):
                    canvases.append(child)
                walk(child)

        walk(popup)
        self.assertTrue(canvases)
        # 60 chars measured well above 260px min -> widened, clamped to 420
        self.assertGreater(int(canvases[0].cget("width")), 260)
        self.assertLessEqual(int(canvases[0].cget("width")), 420)
        combo._close_popup()


# ═══════════════════════════════════════════════════════════════════════════
#  Text widgets must not trap Tab (need a display)
# ═══════════════════════════════════════════════════════════════════════════

@unittest.skipUnless(_TK and _UE, "tkinter / ui_effects unavailable")
class TestTextTabTraversal(TkTestBase):
    """make_text_tab_friendly: Tab escapes Text widgets like every Entry.

    Reproduces the reported bug: tabbing through the prompt builder gets
    permanently stuck once focus reaches the negative-prompt Preview box
    (an editable tk.Text whose class binding consumes Tab).
    """

    def _make_form(self, text_state="normal"):
        """Entry A -> Text -> Entry B, in creation/traversal order."""
        entry_a = ttk.Entry(self.root)
        text = tk.Text(self.root, height=3, wrap="word", state=text_state)
        entry_b = ttk.Entry(self.root)
        entry_a.pack(); text.pack(); entry_b.pack()
        ue.make_text_tab_friendly(text)
        return entry_a, text, entry_b

    def _press(self, widget, keysym):
        self._focus(widget)
        widget.event_generate(keysym)
        self.root.update()

    def test_editable_text_gets_tab_bindings(self):
        _, text, _ = self._make_form()
        self.assertTrue(text.bind("<Tab>"), "<Tab> binding missing")
        self.assertTrue(text.bind("<Shift-Tab>"), "<Shift-Tab> binding missing")

    def test_tab_moves_focus_to_next_widget(self):
        entry_a, text, entry_b = self._make_form()
        received = []
        entry_b.focus_set = lambda: received.append(entry_b)  # spy: Xvfb has no WM
        self._press(text, "<Tab>")
        self.assertEqual(received, [entry_b])

    def test_shift_tab_moves_focus_to_previous_widget(self):
        entry_a, text, entry_b = self._make_form()
        received = []
        entry_a.focus_set = lambda: received.append(entry_a)  # spy: Xvfb has no WM
        self._press(text, "<Shift-Tab>")
        self.assertEqual(received, [entry_a])

    def test_tab_does_not_insert_tab_character(self):
        _, text, _ = self._make_form()
        text.insert("1.0", "sharp detail")
        entry_b = text.tk_focusNext()
        entry_b.focus_set = lambda: None  # spy: Xvfb has no WM
        self._press(text, "<Tab>")
        self.assertEqual(text.get("1.0", "end"), "sharp detail\n")

    def test_editing_still_works_after_helper(self):
        _, text, _ = self._make_form()
        self._focus(text)
        text.event_generate("<KeyPress-x>")
        self.root.update()
        self.assertIn("x", text.get("1.0", "end"))

    def test_disabled_text_removed_from_tab_ring(self):
        _, text, _ = self._make_form(text_state="disabled")
        self.assertEqual(str(text.cget("takefocus")), "0")
        self.assertFalse(text.bind("<Tab>"))  # no binding needed: skipped

    def test_editable_text_takefocus_untouched(self):
        _, text, _ = self._make_form()
        self.assertEqual(str(text.cget("takefocus")), "")  # stays default

    def test_helper_is_idempotent(self):
        entry_a, text, entry_b = self._make_form()
        ue.make_text_tab_friendly(text)  # second call must not double-bind
        received = []
        entry_b.focus_set = lambda: received.append(entry_b)  # spy: Xvfb has no WM
        self._press(text, "<Tab>")
        self.assertEqual(received, [entry_b])  # exactly one focus move

    def test_shift_tab_delivery_exits_on_this_platform(self):
        """Shift-Tab arrives differently per platform: X11 uses the
        ISO_Left_Tab keysym, Windows has no such keysym (bind raises
        TclError) and delivers Shift-Tab as keysym 'Tab' + Shift, which
        matches the <Shift-Tab> pattern. The helper binds both patterns,
        so this test presses the platform-neutral <Shift-Tab> event and
        additionally checks the ISO_Left_Tab binding where Tk knows it.
        (Generating a synthetic <ISO_Left_Tab> event is impossible on
        Windows, which is why the old form of this test failed there.)"""
        entry_a, text, entry_b = self._make_form()
        received = []
        entry_a.focus_set = lambda: received.append(entry_a)  # spy: Xvfb has no WM
        self._press(text, "<Shift-Tab>")
        self.assertEqual(received, [entry_a])

        probe = tk.Entry(self.root)
        try:
            probe.bind("<ISO_Left_Tab>", lambda e: None)
        except tk.TclError:
            return  # keysym unknown on this platform (Windows); covered above
        finally:
            probe.destroy()
        self.assertTrue(text.bind("<ISO_Left_Tab>"), "ISO_Left_Tab binding missing")


if __name__ == "__main__":
    unittest.main(verbosity=2)
