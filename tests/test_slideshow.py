"""Regression tests for the slideshow timer.

These cover the three ways a 12-hour setting could still produce an
unexpected wallpaper change:

  * every app launch fired a change one second later;
  * changing the interval while running left the old `after` job in place;
  * the shipped template enabled the slideshow at one minute.
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import slideshow


class _Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = str(value)


class _Root:
    def __init__(self):
        self.after_calls = []
        self.cancelled = []

    def after(self, ms, callback):
        self.after_calls.append((ms, callback))
        return len(self.after_calls)

    def after_cancel(self, after_id):
        self.cancelled.append(after_id)


class _Status:
    def __init__(self):
        self.text = ""

    def set(self, text):
        self.text = text


def _manager(interval="60"):
    root = _Root()
    manager = slideshow.SlideshowManager(root, _Status())
    manager.slideshow_interval_var = _Var(interval)
    manager.slideshow_source_var = _Var("All Images")
    manager.slideshow_order_var = _Var("random")
    manager.slideshow_skip_duplicates_var = _Var(True)
    return manager, root


class TestSlideshowStartupDelay(unittest.TestCase):

    def test_startup_waits_full_interval(self):
        manager, root = _manager("720")
        manager.start(initial=True)
        self.assertEqual(root.after_calls[-1][0], 720 * 60 * 1000)
        self.assertIsNotNone(manager.last_run)

    def test_explicit_start_is_prompt(self):
        manager, root = _manager("720")
        manager.start(initial=False)
        self.assertEqual(root.after_calls[-1][0], 1000)

    def test_stop_clears_active_interval(self):
        manager, _root = _manager("720")
        manager.start(initial=True)
        manager.stop()
        self.assertIsNone(manager._active_interval_minutes)


class TestSlideshowIntervalChange(unittest.TestCase):

    def test_changing_interval_reschedules_running_timer(self):
        manager, root = _manager("60")
        manager.start(initial=True)
        self.assertEqual(root.after_calls[-1][0], 60 * 60 * 1000)

        manager.slideshow_interval_var.set("720")
        manager.check_interval_changed()

        self.assertTrue(root.cancelled)
        self.assertEqual(root.after_calls[-1][0], 720 * 60 * 1000)
        self.assertEqual(manager._active_interval_minutes, 720)

    def test_unchanged_interval_does_not_reset_timer(self):
        manager, root = _manager("720")
        manager.start(initial=True)
        calls_before = len(root.after_calls)

        manager.check_interval_changed()

        self.assertEqual(len(root.after_calls), calls_before)
        self.assertFalse(root.cancelled)

    def test_tick_uses_current_interval_for_next_run(self):
        manager, root = _manager("720")
        manager.running = True
        manager.paused = False
        manager.do_change = lambda *args, **kwargs: True

        manager.tick()

        self.assertEqual(root.after_calls[-1][0], 720 * 60 * 1000)
        self.assertEqual(manager._active_interval_minutes, 720)


class TestTemplateDefaults(unittest.TestCase):

    def test_template_does_not_enable_one_minute_rotation(self):
        template = Path(__file__).resolve().parent.parent / "config.template.json"
        data = json.loads(template.read_text(encoding="utf-8"))
        self.assertFalse(data["slideshow_enabled"])
        self.assertEqual(data["slideshow_interval"], 60)


if __name__ == "__main__":
    unittest.main()
