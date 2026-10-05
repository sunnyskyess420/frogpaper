"""Gallery mouse-wheel scrolling regression tests.

Regression guard: the global wheel handler (app._on_mousewheel) once
referenced an undefined variable and raised NameError before reaching any
scrolling logic, so hovering the gallery and turning the wheel did nothing.
These tests build a real FrogPaperApp and fire synthetic <MouseWheel>
events over the gallery canvas, asserting the canvas actually scrolls.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import tkinter as tk
except Exception:  # pragma: no cover - tkinter is stdlib on Windows
    tk = None


class TestGalleryWheelScroll(unittest.TestCase):

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

        # A viewable window is required for reliable widget geometry.
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
        # Cancel the pending debounce job with a raw Tcl call: tkinter's
        # after_cancel() would also delete the registered callback command,
        # and when Tkinter reuses command names across widgets (big widget
        # trees), a later canvas.destroy() can raise
        # "can't delete Tcl command".
        try:
            job = getattr(cls.app, "_gallery_scroll_job", None)
            if job is not None and cls.root is not None:
                cls.root.tk.call("after", "cancel", job)
        except Exception:
            pass
        if cls.root is not None:
            try:
                cls.root.destroy()
            except Exception:
                # Mid-tree teardown failures leave widgets behind; the
                # window itself can still be forced down at the Tcl level.
                try:
                    cls.root.tk.call("destroy", ".")
                except Exception:
                    pass
            # Test isolation: if destroy() failed midway, tkinter's
            # process-wide default root still points at this dead root and
            # every later test creating a PhotoImage without an explicit
            # master would attach it to the wrong interpreter
            # ("image pyimageNNN does not exist").
            if tk is not None and getattr(tk, "_default_root", None) is cls.root:
                tk._default_root = None
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

    def _canvas(self):
        canvas = getattr(self.app, "gallery_canvas", None)
        self.assertIsNotNone(canvas, "gallery_canvas missing")
        return canvas

    def _ensure_scrollable(self, canvas):
        """Make the canvas scrollable even when the gallery has no images.

        A fresh/empty gallery has an empty scrollregion; give it a virtual
        one so the wheel-event plumbing itself is what gets exercised.
        """
        top, bottom = canvas.yview()
        if float(bottom) - float(top) >= 0.999:
            canvas.configure(scrollregion=(0, 0, 800, 6000))
            self.root.update_idletasks()
        canvas.yview_moveto(0.0)
        self.root.update_idletasks()

    def _wheel(self, canvas, x=100, y=100, delta=-120):
        canvas.event_generate("<MouseWheel>", delta=delta, x=x, y=y, when="now")
        self.root.update()

    def test_wheel_over_gallery_scrolls_canvas(self):
        canvas = self._canvas()
        self._ensure_scrollable(canvas)
        before = canvas.yview()
        self._wheel(canvas)
        after = canvas.yview()
        self.assertNotEqual(before, after,
                            "wheel over the gallery did not scroll it")

    def test_wheel_direction_follows_delta(self):
        canvas = self._canvas()
        self._ensure_scrollable(canvas)
        self._wheel(canvas, delta=-120)  # wheel down -> towards the end
        first = float(canvas.yview()[0])
        self._wheel(canvas, delta=-120)
        second = float(canvas.yview()[0])
        self.assertGreater(second, first, "wheel down did not advance")
        self._wheel(canvas, delta=120)  # wheel up -> back towards the start
        third = float(canvas.yview()[0])
        self.assertLess(third, second, "wheel up did not go back")


if __name__ == "__main__":
    unittest.main()
