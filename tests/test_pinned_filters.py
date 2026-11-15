"""Type-to-filter and the "recently used" row.

The manager tests are pure logic. The rendering tests build real widgets but
never open the popup window itself (no grab, no focus games), calling
_render_popup_items on a plain frame the way _show_popup does.
"""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pinned_dropdowns
from pinned_dropdowns import (
    FILTER_MIN_ITEMS,
    RECENT_LIMIT,
    PinnedDropdownManager,
)

COLORS = {
    "bg": "#101010",
    "fg": "#f0f0f0",
    "hover": "#202020",
    "selected_bg": "#303030",
    "selected_fg": "#ffffff",
    "header_fg": "#a0a0a0",
    "separator": "#404040",
    "star_off": "#606060",
    "star_on": "#ffcc00",
}


class FakeConfig:
    def __init__(self, initial=None):
        self.data = dict(initial) if initial else {}
        self.save_calls = 0
        self.fail_save = False

    def load(self):
        return dict(self.data)

    def save(self, cfg):
        if self.fail_save:
            raise IOError("simulated disk failure")
        self.data = dict(cfg)
        self.save_calls += 1


class TestRecentManager(unittest.TestCase):
    def setUp(self):
        self.cfg = FakeConfig()
        self.mgr = PinnedDropdownManager(self.cfg.load, self.cfg.save)

    def test_starts_empty(self):
        self.assertEqual(self.mgr.get_recent("subject"), [])

    def test_push_puts_newest_first(self):
        self.mgr.push_recent("subject", "frog")
        self.mgr.push_recent("subject", "owl")
        self.assertEqual(self.mgr.get_recent("subject"), ["owl", "frog"])

    def test_repeat_moves_to_front_without_duplicating(self):
        for value in ("frog", "owl", "frog"):
            self.mgr.push_recent("subject", value)
        self.assertEqual(self.mgr.get_recent("subject"), ["frog", "owl"])

    def test_capped_at_limit(self):
        for i in range(RECENT_LIMIT + 4):
            self.mgr.push_recent("subject", f"creature {i}")
        recent = self.mgr.get_recent("subject")
        self.assertEqual(len(recent), RECENT_LIMIT)
        self.assertEqual(recent[0], f"creature {RECENT_LIMIT + 3}")

    def test_categories_are_independent(self):
        self.mgr.push_recent("subject", "frog")
        self.mgr.push_recent("mood", "epic")
        self.assertEqual(self.mgr.get_recent("subject"), ["frog"])
        self.assertEqual(self.mgr.get_recent("mood"), ["epic"])

    def test_persisted_and_reloaded(self):
        self.mgr.push_recent("subject", "frog")
        self.mgr.push_recent("subject", "owl")
        self.assertIn("recent_options", self.cfg.data)

        reloaded = PinnedDropdownManager(self.cfg.load, self.cfg.save)
        self.assertEqual(reloaded.get_recent("subject"), ["owl", "frog"])

    def test_blank_and_non_string_values_ignored(self):
        self.mgr.push_recent("subject", "")
        self.mgr.push_recent("subject", "   ")
        self.mgr.push_recent("subject", None)
        self.assertEqual(self.mgr.get_recent("subject"), [])

    def test_corrupt_config_does_not_raise(self):
        cfg = FakeConfig({"recent_options": ["not", "a", "dict"]})
        mgr = PinnedDropdownManager(cfg.load, cfg.save)
        self.assertEqual(mgr.get_recent("subject"), [])

    def test_save_failure_is_survivable(self):
        self.cfg.fail_save = True
        self.mgr.push_recent("subject", "frog")  # must not raise
        self.assertEqual(self.mgr.get_recent("subject"), ["frog"])

    def test_pins_and_recents_do_not_clobber_each_other(self):
        self.mgr.toggle_pin("subject", "frog")
        self.mgr.push_recent("subject", "owl")
        self.assertEqual(self.mgr.get_pinned("subject"), ["frog"])
        self.assertEqual(self.mgr.get_recent("subject"), ["owl"])
        self.assertTrue(self.cfg.data.get("pinned_options"))
        self.assertTrue(self.cfg.data.get("recent_options"))


def _make_root():
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        return root
    except Exception as exc:  # no Tk in this interpreter
        raise unittest.SkipTest(f"tkinter unavailable: {exc}")


class TestPopupRendering(unittest.TestCase):
    VALUES = [
        "", "frog", "tree frog", "bullfrog", "owl", "wolf", "panther", "tiger",
        "bear", "fox", "raven", "stag", "eagle", "kraken", "phoenix", "dragon",
    ]

    def setUp(self):
        import tkinter as tk

        self.root = _make_root()
        self.cfg = FakeConfig()
        self.mgr = pinned_dropdowns.init_pinned_manager(self.cfg.load, self.cfg.save)
        self.pc = pinned_dropdowns.PinnedCombobox(
            self.root, category="subject", values=list(self.VALUES), state="normal")
        self.pc.pack()
        self.body = tk.Frame(self.root, bg=COLORS["bg"])
        self.body.pack()
        self.pc._popup_filter_var = tk.StringVar()
        self.pc._popup_body = self.body

    def tearDown(self):
        try:
            self.pc._close_popup()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass
        pinned_dropdowns._mgr = None

    def render(self):
        self.pc._render_popup_items(self.body, COLORS)

    def labels(self) -> list[str]:
        text = []
        for child in self.body.winfo_children():
            try:
                value = child.cget("text")
            except Exception:
                value = ""
            if value:
                text.append(str(value))
        return text

    def test_filter_narrows_visible_values(self):
        self.pc._popup_filter_var.set("frog")
        self.assertEqual(self.pc._visible_values(), ["frog", "tree frog", "bullfrog"])

    def test_filter_is_case_insensitive_and_trims(self):
        self.pc._popup_filter_var.set("  OWL  ")
        self.assertEqual(self.pc._visible_values(), ["owl"])

    def test_empty_filter_shows_everything(self):
        self.pc._popup_filter_var.set("")
        self.assertEqual(self.pc._visible_values(), [v for v in self.VALUES if v])

    def test_render_shows_recent_section(self):
        self.mgr.push_recent("subject", "owl")
        self.mgr.push_recent("subject", "wolf")
        self.render()
        headers = " ".join(self.labels())
        self.assertIn("RECENTLY USED", headers)
        self.assertIn("Available Options", headers)

    def test_recent_items_are_not_repeated_in_available(self):
        self.mgr.push_recent("subject", "owl")
        self.render()
        headers = [t for t in self.labels() if "Available Options" in t]
        self.assertEqual(headers, [f"Available Options ({len(self.VALUES) - 2})"])

    def test_recent_row_shrinks_with_filter(self):
        self.mgr.push_recent("subject", "owl")
        self.mgr.push_recent("subject", "frog")
        self.pc._popup_filter_var.set("frog")
        self.render()
        headers = " ".join(self.labels())
        self.assertIn("RECENTLY USED (1)", headers)
        self.assertIn("Available Options (2)", headers)

    def test_no_match_message(self):
        self.pc._popup_filter_var.set("zzz")
        self.render()
        self.assertEqual(self.pc._visible_values(), [])
        self.assertIn('No match for "zzz"', " ".join(self.labels()))

    def test_pinned_still_listed_first(self):
        self.mgr.toggle_pin("subject", "raven")
        self.render()
        self.assertIn("★ FAVORITES (1)", " ".join(self.labels()))

    def test_choosing_a_value_remembers_it(self):
        self.pc._remember_choice("kraken")
        self.assertEqual(self.mgr.get_recent("subject"), ["kraken"])

    def test_enter_picks_the_first_visible_match(self):
        self.pc._popup_filter_var.set("phoe")
        self.pc._select_first_match()
        self.assertEqual(self.pc.get(), "phoenix")
        self.assertEqual(self.mgr.get_recent("subject"), ["phoenix"])

    def test_filter_box_only_for_long_lists(self):
        self.assertGreater(len([v for v in self.VALUES if v]), FILTER_MIN_ITEMS - 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
