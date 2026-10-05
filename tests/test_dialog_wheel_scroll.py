"""Dialog / child-window wheel scrolling regression tests.

Regression guard: the global wheel handler used to bail out whenever ANY
Toplevel (e.g. the Settings window) was open, and the dialogs' hover-based
canvas registration goes stale as soon as the pointer is over a child
widget - so scrolling inside the settings window did nothing. The handler
now routes wheel events by the window they occur in and walks up from the
wheeled widget to the page's scrollable canvas.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import tkinter as tk
except Exception:  # pragma: no cover - tkinter is stdlib on Windows
    tk = None


class TestDialogWheelScroll(unittest.TestCase):

    app = None
    root = None

    @classmethod
    def setUpClass(cls):
        if tk is None:
            raise unittest.SkipTest("tkinter unavailable")
        try:
            root = tk.Tk()
        except tk.TclError as exc:  # headless environment without a display
            raise unittest.SkipTest(f"No usable Tk display: {exc}")

        # Don't let app construction / save_config touch the real config.json.
        import tempfile

        import utils as utils_mod

        cls._config_tmp = tempfile.TemporaryDirectory()
        cls._orig_config_file = utils_mod.CONFIG_FILE
        utils_mod.CONFIG_FILE = Path(cls._config_tmp.name) / "config.json"

        root.geometry("1280x800+40+40")
        root.update_idletasks()
        root.update()

        try:
            from app import FrogPaperApp

            cls.app = FrogPaperApp(root)
        except Exception:
            root.destroy()
            raise
        cls.root = root
        cls.root.update_idletasks()
        cls.root.update()

    @classmethod
    def tearDownClass(cls):
        if cls.root is not None:
            try:
                cls.root.destroy()
            except Exception:
                pass
        # Restore the real config path / clean up the throwaway file.
        try:
            import utils as utils_mod

            utils_mod.CONFIG_FILE = cls._orig_config_file
        except Exception:
            pass
        try:
            cls._config_tmp.cleanup()
        except Exception:
            pass
        if tk is not None and getattr(tk, "_default_root", None) is cls.root:
            tk._default_root = None

    def _find_child_widget(self, parent):
        """Return a mapped label deep inside *parent* to wheel over."""
        stack = [parent]
        while stack:
            w = stack.pop()
            try:
                children = w.winfo_children()
            except Exception:
                continue
            for c in children:
                if isinstance(c, tk.Label) and c.winfo_ismapped():
                    return c
                stack.append(c)
        return None

    def test_settings_window_scrolls_on_wheel_over_child(self):
        self.app._open_settings_window()
        for _ in range(10):
            self.root.update()
        win = getattr(self.app, "_settings_win", None)
        self.assertIsNotNone(win, "settings window did not open")
        canvas = getattr(self.app, "settings_canvas", None)
        self.assertIsNotNone(canvas, "settings canvas missing")
        tab = getattr(self.app, "_settings_tab", None)
        if tab is not None:
            tab._switch_category("cloud")  # a page that is usually taller than the viewport
        for _ in range(8):
            self.root.update()

        span = float(canvas.yview()[1]) - float(canvas.yview()[0])
        if span >= 0.999:
            # Nothing taller than the viewport in this environment - force a
            # scrollable region so the wheel routing is still exercised.
            canvas.configure(scrollregion=(0, 0, 800, 6000))
            self.root.update_idletasks()

        target = self._find_child_widget(canvas) or canvas
        gallery = getattr(self.app, "gallery_canvas", None)
        g0 = gallery.yview() if gallery is not None else None
        before = canvas.yview()
        target.event_generate("<MouseWheel>", delta=-120, x=8, y=8, when="now")
        self.root.update()
        self.assertNotEqual(
            before, canvas.yview(),
            "wheel over settings content did not scroll the settings page",
        )
        if g0 is not None:
            self.assertEqual(
                g0, gallery.yview(),
                "wheel inside the settings window must not scroll the gallery",
            )
        try:
            win.destroy()
        except Exception:
            pass
        self.app._settings_win = None


if __name__ == "__main__":
    unittest.main()
