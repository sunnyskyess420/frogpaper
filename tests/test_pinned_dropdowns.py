"""Unit tests for FrogPaper's pinned-dropdown logic.

Covers the improvement-report targets:
  - pin toggling
  - pin persistence (save/load round-trip, failure resilience)
  - pin marker stripping (★, ☆, ⭐, 📌, *)
  - change-notification callbacks

These tests are pure logic tests: they never open a Tk window and never
touch your real config.json.

Run from the project root:
    python -m unittest discover -s tests -v

Or just double-click tests\\run_tests.bat
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

# Allow running from any working directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pinned_dropdowns import (
    PINNED_CATEGORIES,
    PinnedDropdownManager,
    get_manager,
    init_pinned_manager,
    strip_pin_marker,
)
import pinned_dropdowns


class FakeConfig:
    """In-memory config store mimicking load_config/save_config."""

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


class TestStripPinMarker(unittest.TestCase):
    """strip_pin_marker: remove pin symbols and whitespace."""

    def test_star_with_space(self):
        self.assertEqual(strip_pin_marker("★ frog"), "frog")

    def test_star_without_space(self):
        self.assertEqual(strip_pin_marker("★frog"), "frog")

    def test_outline_star(self):
        self.assertEqual(strip_pin_marker("☆cat"), "cat")

    def test_gold_star_emoji(self):
        self.assertEqual(strip_pin_marker("⭐ dragon"), "dragon")

    def test_pin_emoji(self):
        self.assertEqual(strip_pin_marker("📌 forest"), "forest")

    def test_asterisk(self):
        self.assertEqual(strip_pin_marker("*mood"), "mood")

    def test_plain_value_untouched(self):
        self.assertEqual(strip_pin_marker("cyberpunk city"), "cyberpunk city")

    def test_marker_not_at_start_untouched(self):
        # Only leading markers are stripped
        self.assertEqual(strip_pin_marker("frog ★"), "frog ★")

    def test_whitespace_trimmed(self):
        self.assertEqual(strip_pin_marker("   spaced   "), "spaced")

    def test_empty_string(self):
        self.assertEqual(strip_pin_marker(""), "")

    def test_none_becomes_empty_string(self):
        self.assertEqual(strip_pin_marker(None), "")

    def test_non_string_returns_as_is(self):
        self.assertEqual(strip_pin_marker(42), 42)

    def test_double_marker_is_single_pass(self):
        # Known behavior: stripping is single-pass, so a doubled marker
        # loses only one star. This test documents the current behavior
        # on purpose — change it consciously if the logic ever improves.
        self.assertEqual(strip_pin_marker("★★frog"), "★frog")


class TestManagerBasics(unittest.TestCase):
    """PinnedDropdownManager: toggling and lookups."""

    def setUp(self):
        self.cfg = FakeConfig()
        self.mgr = PinnedDropdownManager(self.cfg.load, self.cfg.save)

    def test_all_categories_initialized(self):
        for cat in PINNED_CATEGORIES:
            self.assertEqual(self.mgr.get_pinned(cat), [])

    def test_expected_category_set(self):
        self.assertEqual(
            set(PINNED_CATEGORIES),
            {"subject", "setting", "lighting", "mood",
             "atmosphere", "color_family", "color_variation"},
        )

    def test_toggle_pin_returns_true_then_false(self):
        self.assertTrue(self.mgr.toggle_pin("mood", "serene"))
        self.assertTrue(self.mgr.is_pinned("mood", "serene"))
        self.assertFalse(self.mgr.toggle_pin("mood", "serene"))
        self.assertFalse(self.mgr.is_pinned("mood", "serene"))

    def test_toggle_strips_whitespace(self):
        self.assertTrue(self.mgr.toggle_pin("mood", "  serene  "))
        self.assertTrue(self.mgr.is_pinned("mood", "serene"))
        self.assertEqual(self.mgr.get_pinned("mood"), ["serene"])

    def test_toggle_empty_value_is_noop(self):
        before = self.cfg.save_calls
        self.assertFalse(self.mgr.toggle_pin("mood", ""))
        self.assertFalse(self.mgr.toggle_pin("mood", "   "))
        self.assertFalse(self.mgr.toggle_pin("mood", None))
        self.assertEqual(self.cfg.save_calls, before)

    def test_toggle_none_value_is_noop(self):
        self.assertFalse(self.mgr.toggle_pin("mood", None))

    def test_unknown_category_created_on_toggle(self):
        self.assertTrue(self.mgr.toggle_pin("custom_category", "unicorn"))
        self.assertEqual(self.mgr.get_pinned("custom_category"), ["unicorn"])

    def test_is_pinned_unknown_category_false(self):
        self.assertFalse(self.mgr.is_pinned("no_such_cat", "x"))

    def test_is_pinned_handles_none(self):
        self.assertFalse(self.mgr.is_pinned("mood", None))

    def test_get_pinned_returns_copy(self):
        self.mgr.toggle_pin("mood", "a")
        pinned = self.mgr.get_pinned("mood")
        pinned.append("hacker-value")
        # Manager state must be unaffected by outside mutation
        self.assertEqual(self.mgr.get_pinned("mood"), ["a"])

    def test_toggle_saves_config(self):
        before = self.cfg.save_calls
        self.mgr.toggle_pin("mood", "serene")
        self.assertEqual(self.cfg.save_calls, before + 1)
        self.assertEqual(self.cfg.data["pinned_options"]["mood"], ["serene"])


class TestManagerPersistence(unittest.TestCase):
    """Pins survive config reloads; failures degrade gracefully."""

    def test_round_trip_through_temp_json_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = Path(tmp) / "config.json"

            def loader():
                if cfg_path.exists():
                    return json.loads(cfg_path.read_text(encoding="utf-8"))
                return {}

            def saver(cfg):
                cfg_path.write_text(
                    json.dumps(cfg, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

            # Session 1: pin two items
            mgr1 = PinnedDropdownManager(loader, saver)
            mgr1.toggle_pin("mood", "serene")
            mgr1.toggle_pin("lighting", "golden hour")

            # Session 2: a brand-new manager sees the same pins
            mgr2 = PinnedDropdownManager(loader, saver)
            self.assertTrue(mgr2.is_pinned("mood", "serene"))
            self.assertTrue(mgr2.is_pinned("lighting", "golden hour"))
            self.assertFalse(mgr2.is_pinned("mood", "stormy"))

    def test_loads_existing_pins_from_config(self):
        initial = {"pinned_options": {"mood": ["epic", "calm"]}}
        mgr = PinnedDropdownManager(FakeConfig(initial).load, FakeConfig().save)
        self.assertEqual(mgr.get_pinned("mood"), ["epic", "calm"])

    def test_load_failure_falls_back_to_empty(self):
        def broken_loader():
            raise RuntimeError("config file corrupted")

        mgr = PinnedDropdownManager(broken_loader, FakeConfig().save)
        for cat in PINNED_CATEGORIES:
            self.assertEqual(mgr.get_pinned(cat), [])
        # And it still works after the rough start
        self.assertTrue(mgr.toggle_pin("mood", "serene"))

    def test_save_failure_does_not_crash(self):
        cfg = FakeConfig()
        cfg.fail_save = True
        mgr = PinnedDropdownManager(cfg.load, cfg.save)
        # Toggle reports the in-memory flip even though persisting failed
        self.assertTrue(mgr.toggle_pin("mood", "serene"))
        self.assertTrue(mgr.is_pinned("mood", "serene"))

    def test_partial_pins_config_gets_missing_categories(self):
        initial = {"pinned_options": {"mood": ["calm"]}}  # others missing
        mgr = PinnedDropdownManager(FakeConfig(initial).load, FakeConfig().save)
        self.assertEqual(mgr.get_pinned("mood"), ["calm"])
        self.assertEqual(mgr.get_pinned("subject"), [])


class TestManagerCallbacks(unittest.TestCase):
    """Widgets registered for change notifications get informed."""

    def setUp(self):
        self.cfg = FakeConfig()
        self.mgr = PinnedDropdownManager(self.cfg.load, self.cfg.save)

    def test_callback_fired_on_toggle(self):
        calls = []
        self.mgr.register_callback(lambda: calls.append(1))
        self.mgr.toggle_pin("mood", "serene")
        self.assertEqual(len(calls), 1)
        self.mgr.toggle_pin("mood", "serene")
        self.assertEqual(len(calls), 2)

    def test_no_callback_on_noop_toggle(self):
        calls = []
        self.mgr.register_callback(lambda: calls.append(1))
        self.mgr.toggle_pin("mood", "")  # noop
        self.assertEqual(len(calls), 0)

    def test_broken_callback_does_not_block_others(self):
        calls = []

        def broken():
            raise ValueError("widget destroyed")

        self.mgr.register_callback(broken)
        self.mgr.register_callback(lambda: calls.append(1))
        self.mgr.toggle_pin("mood", "serene")
        self.assertEqual(len(calls), 1)


class TestGlobalManager(unittest.TestCase):
    """init_pinned_manager / get_manager module-level contract."""

    def setUp(self):
        self._original_mgr = pinned_dropdowns._mgr

    def tearDown(self):
        pinned_dropdowns._mgr = self._original_mgr

    def test_init_and_get_round_trip(self):
        cfg = FakeConfig()
        mgr = init_pinned_manager(cfg.load, cfg.save)
        self.assertIs(get_manager(), mgr)

    def test_strip_pin_marker_uses_manager_when_initialized(self):
        cfg = FakeConfig()
        mgr = init_pinned_manager(cfg.load, cfg.save)
        mgr.toggle_pin("mood", "serene")
        # Module-level function delegates to the manager's method
        self.assertEqual(strip_pin_marker("★ serene"), "serene")

    def test_strip_pin_marker_standalone_without_manager(self):
        pinned_dropdowns._mgr = None
        self.assertEqual(strip_pin_marker("★ frog"), "frog")


if __name__ == "__main__":
    unittest.main(verbosity=2)
