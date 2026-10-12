"""Regression tests: wheel over the open Tag dropdown must never scroll the gallery.

Root cause context (fixed 2026-10-07): the ttk combobox popdown listbox is
created entirely in Tcl, so its mouse-wheel events arrive with
``event.widget`` as a plain path string (no Python widget object).
app._on_mousewheel tried ``ev_widget.winfo_toplevel()``, the AttributeError
was silently swallowed, and the handler fell through to the main-window
path - scrolling the gallery canvas underneath the open dropdown (the
"tag dropdown scrolls the gallery" bug). The handler now resolves string
widgets through Tcl and stops popdown events from touching the gallery.
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import tkinter as tk
except Exception:  # pragma: no cover - tkinter is stdlib on Windows
    tk = None


class TestTagDropdownWheel(unittest.TestCase):

    app = None
    root = None
    combo = None
    lb_path = None
    pd_path = None

    @classmethod
    def setUpClass(cls):
        if tk is None:
            raise unittest.SkipTest("tkinter unavailable")
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            raise unittest.SkipTest(f"No usable Tk display: {exc}")

        import tempfile

        import utils as utils_mod

        cls._config_tmp = tempfile.TemporaryDirectory()
        cfg = Path(cls._config_tmp.name) / "config.json"
        cfg.write_text(json.dumps({"first_run_completed": True}), encoding="utf-8")
        cls._orig_config_file = utils_mod.CONFIG_FILE
        utils_mod.CONFIG_FILE = cfg

        root.geometry("1280x800+30+30")
        root.update_idletasks()
        root.update()
        try:
            from app import FrogPaperApp

            cls.app = FrogPaperApp(root)
        except Exception:
            root.destroy()
            raise
        cls.root = root
        root.update_idletasks()
        for _ in range(6):
            root.update()

        cls.combo = cls.app.gallery_tag_combo
        cls.combo.configure(
            values=["All tags", "Untagged"] + [f"regtag_{i:02d}" for i in range(1, 41)]
        )
        cls.combo.set("regtag_03")

        cls.pd_path = None
        cls.lb_path = None
        cls._ensure_posted()

    @classmethod
    def _ensure_posted(cls):
        if cls.combo is None:
            return
        try:
            posted = False
            if cls.pd_path:
                try:
                    posted = bool(int(cls.root.tk.call("winfo", "viewable", cls.pd_path)))
                except Exception:
                    posted = False
            if not posted:
                cls.combo.tk.call("ttk::combobox::Post", cls.combo._w)
                for _ in range(3):
                    cls.root.update()
                cls.pd_path = str(cls.combo.tk.call("ttk::combobox::PopdownWindow", cls.combo._w))
                cls.lb_path = cls._find_listbox(cls.pd_path)
        except Exception:
            cls.lb_path = None

    @classmethod
    def _ensure_unposted(cls):
        try:
            cls.combo.tk.call("ttk::combobox::Unpost", cls.combo._w)
            for _ in range(2):
                cls.root.update()
        except Exception:
            pass

    @classmethod
    def _find_listbox(cls, p):
        try:
            if cls.root.tk.call("winfo", "class", p) == "Listbox":
                return p
            for c in cls.root.tk.splitlist(cls.root.tk.call("winfo", "children", p)):
                r = cls._find_listbox(c)
                if r:
                    return r
        except Exception:
            pass
        return None

    @classmethod
    def tearDownClass(cls):
        try:
            job = getattr(cls.app, "_gallery_scroll_job", None)
            if job is not None and cls.root is not None:
                cls.root.tk.call("after", "cancel", job)
        except Exception:
            pass
        cls._ensure_unposted()
        if cls.root is not None:
            try:
                cls.root.destroy()
            except Exception:
                try:
                    cls.root.tk.call("destroy", ".")
                except Exception:
                    pass
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

    def _router(self, widget, x_root, y_root, delta=-120):
        # Call the real central wheel router with a synthetic event.

        class _Ev:
            pass

        ev = _Ev()
        ev.widget = widget
        ev.delta = delta
        ev.x_root = x_root
        ev.y_root = y_root
        return self.app._on_mousewheel(ev)

    def _listbox_center(self):
        rx = int(self.root.tk.call("winfo", "rootx", self.lb_path))
        ry = int(self.root.tk.call("winfo", "rooty", self.lb_path))
        rw = int(self.root.tk.call("winfo", "width", self.lb_path))
        rh = int(self.root.tk.call("winfo", "height", self.lb_path))
        return rx + rw // 2, ry + rh // 2

    def test_open_dropdown_listbox_scrolls_itself_not_gallery(self):
        # End-to-end: a real generated wheel on the popdown listbox.
        self._ensure_posted()
        if not self.lb_path:
            raise unittest.SkipTest("popdown listbox unavailable in this environment")
        gc = self.app.gallery_canvas
        gc.yview_moveto(0.0)
        for _ in range(3):
            self.root.update()
        g_before = gc.yview()
        l_before = self.root.tk.call(self.lb_path, "yview")
        rw = int(self.root.tk.call("winfo", "width", self.lb_path))
        rh = int(self.root.tk.call("winfo", "height", self.lb_path))
        self.root.tk.call("event", "generate", self.lb_path, "<MouseWheel>",
                          "-delta", -120, "-x", rw // 2, "-y", rh // 2)
        for _ in range(3):
            self.root.update()
        self.assertEqual(gc.yview(), g_before,
                         "gallery scrolled while wheeling over the open dropdown")
        span = float(l_before[1]) - float(l_before[0])
        if span < 0.999:
            self.assertNotEqual(self.root.tk.call(self.lb_path, "yview"), l_before,
                                "dropdown list must scroll itself")

    def test_string_widget_in_main_window_still_routes(self):
        # A main-window widget delivered as a string path must still scroll.
        self._ensure_unposted()
        gc = self.app.gallery_canvas
        top, bottom = gc.yview()
        if float(bottom) - float(top) >= 0.999:
            gc.configure(scrollregion=(0, 0, 800, 6000))
            self.root.update_idletasks()
        gc.yview_moveto(0.0)
        for _ in range(3):
            self.root.update()
        before = gc.yview()
        cx = gc.winfo_rootx() + gc.winfo_width() // 2
        cy = gc.winfo_rooty() + gc.winfo_height() // 2
        result = self._router(gc._w, cx, cy)
        for _ in range(3):
            self.root.update()
        self.assertEqual(result, "break")
        self.assertNotEqual(gc.yview(), before,
                            "wheel over the gallery itself must still scroll it")

    def test_wheel_over_open_dropdown_never_scrolls_gallery(self):
        # Direct router call: string popdown widget must not move the gallery.
        self._ensure_posted()
        if not self.lb_path:
            raise unittest.SkipTest("popdown listbox unavailable in this environment")
        gc = self.app.gallery_canvas
        gc.yview_moveto(0.0)
        for _ in range(3):
            self.root.update()
        before = gc.yview()
        px, py = self._listbox_center()
        result = self._router(self.lb_path, px, py)
        for _ in range(3):
            self.root.update()
        self.assertEqual(result, "break",
                         "router must stop wheel events coming from the popdown")
        self.assertEqual(gc.yview(), before,
                         "gallery must not move when wheeling over the dropdown")


if __name__ == "__main__":
    unittest.main()
