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
        # start() no longer sets last_run immediately - it's set on first fire

    def test_explicit_start_waits_full_interval(self):
        manager, root = _manager("720")
        manager.start(initial=False)
        # Both initial=True and initial=False now schedule full interval
        self.assertEqual(root.after_calls[-1][0], 720 * 60 * 1000)

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

        manager.tick(manager._epoch)

        self.assertEqual(root.after_calls[-1][0], 720 * 60 * 1000)
        self.assertEqual(manager._active_interval_minutes, 720)


class TestTemplateDefaults(unittest.TestCase):

    def test_template_does_not_enable_one_minute_rotation(self):
        template = Path(__file__).resolve().parent.parent / "config.template.json"
        data = json.loads(template.read_text(encoding="utf-8"))
        self.assertFalse(data["slideshow_enabled"])
        self.assertEqual(data["slideshow_interval"], 60)


class TestFormatRemaining(unittest.TestCase):

    def test_under_an_hour(self):
        self.assertEqual(slideshow.format_remaining(8 * 60 + 15), "08:15")
        self.assertEqual(slideshow.format_remaining(0), "00:00")

    def test_over_an_hour_includes_seconds(self):
        self.assertEqual(
            slideshow.format_remaining(23 * 3600 + 4 * 60 + 9),
            "23h 04m 09s",
        )

    def test_24_hours_stays_explicit(self):
        self.assertEqual(slideshow.format_remaining(24 * 3600), "24h 00m 00s")

    def test_days_include_seconds(self):
        self.assertEqual(
            slideshow.format_remaining(3 * 86400 + 2 * 3600 + 5 * 60 + 12),
            "3d 02h 05m 12s",
        )


class TestSlideshowTimerBehavior(unittest.TestCase):
    """Regression tests for the single-timer refactor."""

    def test_duplicate_start_cancels_first_job(self):
        manager, root = _manager("10")
        manager.start(initial=False)
        first_id = manager.after_id
        self.assertIsNotNone(first_id)

        manager.start(initial=False)
        second_id = manager.after_id
        self.assertNotEqual(first_id, second_id)
        self.assertEqual(len(root.cancelled), 1)
        self.assertEqual(root.cancelled[0], first_id)

    def test_unchanged_interval_does_not_reschedule(self):
        manager, root = _manager("10")
        manager.start(initial=True)
        calls_before = len(root.after_calls)

        manager.check_interval_changed()

        self.assertEqual(len(root.after_calls), calls_before)
        self.assertFalse(root.cancelled)

    def test_pause_resume_preserves_remaining_time(self):
        manager, root = _manager("10")
        manager.start(initial=True)
        # Simulate 6 minutes elapsed by modifying deadline
        manager._deadline = manager._deadline - (6 * 60)

        manager.pause()
        remaining_ms = manager._remaining_ms
        self.assertGreater(remaining_ms, 0)
        self.assertLess(remaining_ms, 10 * 60 * 1000)

        manager.resume()
        # Should schedule the remaining time, not 1000ms
        self.assertEqual(root.after_calls[-1][0], remaining_ms)

    def test_manual_advance_does_not_reset_timer(self):
        manager, root = _manager("10")
        manager.start(initial=True)
        manager.do_change = lambda *args, **kwargs: True
        initial_delay = root.after_calls[-1][0]

        manager.next_now()

        # Timer should not be rescheduled
        self.assertEqual(len(root.after_calls), 1)
        self.assertEqual(root.after_calls[-1][0], initial_delay)

    def test_advance_once_does_not_update_last_run(self):
        manager, root = _manager("10")
        manager.start(initial=True)
        manager.do_change = lambda *args, **kwargs: True
        initial_last_run = manager.last_run

        manager.advance_once()

        # last_run should NOT be updated
        self.assertEqual(manager.last_run, initial_last_run)

    def test_stale_callback_ignored(self):
        manager, root = _manager("10")
        manager.start(initial=True)
        manager.stop()  # Increments epoch
        old_epoch = manager._epoch - 1

        # Simulate a callback from the old epoch
        manager.tick(old_epoch)

        # Should return early without scheduling
        self.assertEqual(len(root.after_calls), 1)  # Only the initial schedule


if __name__ == "__main__":
    unittest.main()
