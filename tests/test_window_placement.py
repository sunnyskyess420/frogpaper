"""Tests for main-window placement (centered on the visible work area).

NOTE: the window must be deiconified (mapped) — Tk 9 does not apply a
geometry request to an unmapped window, and winfo_rootx includes the
window-manager frame offset, so these tests assert against the
`wm geometry` string (the source of truth) instead of winfo coords.
"""

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import utils


class TestWindowPlacement(unittest.TestCase):

    def setUp(self):
        try:
            import tkinter as tk
        except ImportError:  # pragma: no cover
            self.skipTest("tkinter unavailable")
        self.root = tk.Tk()
        self.root.deiconify()
        self.root.update_idletasks()
        self.root.update()

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def _parse_geometry(self):
        m = re.match(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)", self.root.geometry())
        self.assertIsNotNone(m, f"unexpected geometry: {self.root.geometry()}")
        return tuple(int(g) for g in m.groups())  # W, H, X, Y

    def test_geometry_parsed_and_fits_requested_size(self):
        # 640x480 fits even the smallest runner desktop (GitHub's Windows
        # runner is 1024x768 with a taskbar; requesting a size near the
        # screen edge let the shell clamp the mapped window and break the
        # return-value comparison).
        w, h = utils.place_on_work_area(self.root, 640, 480)
        self.root.update()
        W, H, X, Y = self._parse_geometry()
        self.assertEqual((W, H), (w, h))
        self.assertLessEqual(W, 640)
        self.assertLessEqual(H, 480)
        wa_x, wa_y, _, _ = utils.get_work_area(self.root)
        self.assertGreaterEqual(X, wa_x - 1)
        self.assertGreaterEqual(Y, wa_y - 1)

    def test_oversized_window_clamped_to_work_area(self):
        wa_x, wa_y, wa_w, wa_h = utils.get_work_area(self.root)
        utils.place_on_work_area(self.root, 99999, 99999)
        self.root.update()
        W, H, X, Y = self._parse_geometry()
        self.assertLessEqual(W, wa_w)
        self.assertLessEqual(H, wa_h)

    def test_window_is_centered_and_above_taskbar(self):
        utils.place_on_work_area(self.root, 800, 600)
        self.root.update()
        wa_x, wa_y, wa_w, wa_h = utils.get_work_area(self.root)
        W, H, X, Y = self._parse_geometry()
        expected_x = wa_x + (wa_w - W) // 2
        expected_y = wa_y + (wa_h - H) // 2
        self.assertLessEqual(abs(X - expected_x), 1, "not horizontally centered")
        self.assertLessEqual(abs(Y - expected_y), 1, "not vertically centered")
        # the whole window must sit inside the work area (above the taskbar)
        self.assertGreaterEqual(Y, wa_y)
        self.assertLessEqual(Y + H, wa_y + wa_h)


if __name__ == "__main__":
    unittest.main(verbosity=2)
