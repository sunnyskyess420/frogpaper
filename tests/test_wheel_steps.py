"""Wheel handling: never truncate a high-resolution delta to zero."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from utils import wheel_steps, WHEEL_LINES_PER_NOTCH


class _Event:
    def __init__(self, delta):
        self.delta = delta


class TestWheelSteps(unittest.TestCase):
    def test_one_notch_scrolls_three_lines_by_default(self):
        self.assertEqual(wheel_steps(_Event(120)), -WHEEL_LINES_PER_NOTCH)
        self.assertEqual(wheel_steps(_Event(-120)), WHEEL_LINES_PER_NOTCH)

    def test_canvas_uses_one_unit_per_notch(self):
        self.assertEqual(wheel_steps(_Event(120), per_notch=1), -1)
        self.assertEqual(wheel_steps(_Event(-120), per_notch=1), 1)

    def test_precision_touchpad_delta_is_not_swallowed(self):
        # 30 used to give int(-30/120) == 0: the wheel did nothing.
        self.assertEqual(wheel_steps(_Event(30)), -1)
        self.assertEqual(wheel_steps(_Event(-30)), 1)
        self.assertEqual(wheel_steps(_Event(30), per_notch=1), -1)

    def test_zero_delta_is_a_no_op(self):
        self.assertEqual(wheel_steps(_Event(0)), 0)

    def test_large_delta_scales(self):
        self.assertEqual(wheel_steps(_Event(360)), -3 * WHEEL_LINES_PER_NOTCH)


if __name__ == "__main__":
    unittest.main()
