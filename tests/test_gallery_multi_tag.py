"""Multi-select tagging regression tests.

Covers: (1) Ctrl+click multi-selection feeding tag_gallery_image;
(2) cross-view selection sync - picking an image in another view must
retarget "Tag Image" to that image (not a stale gallery selection);
(3) plain click resetting the multi-selection; (4) the dynamic
"Tag N Images" button label.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import tkinter as tk
except Exception:  # pragma: no cover
    tk = None


class TestGalleryMultiTag(unittest.TestCase):

    app = None
    root = None

    @classmethod
    def setUpClass(cls):
        if tk is None:
            raise unittest.SkipTest("tkinter unavailable")
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            raise unittest.SkipTest(f"No usable Tk display: {exc}")

        import utils as utils_mod

        cls._config_tmp = tempfile.TemporaryDirectory()
        cfg = Path(cls._config_tmp.name) / "config.json"
        cfg.write_text(json.dumps({"first_run_completed": True}), encoding="utf-8")
        cls._orig_config_file = utils_mod.CONFIG_FILE
        utils_mod.CONFIG_FILE = cfg

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
        for _ in range(6):
            cls.root.update()

        # Never open the real modal tag dialog inside tests.
        import gallery_tab as gt

        cls._gt = gt
        cls._orig_show_tag_dialog = gt.GalleryTab._show_tag_dialog
        gt.GalleryTab._show_tag_dialog = lambda self, title: ["regression-tag"]

    @classmethod
    def tearDownClass(cls):
        try:
            cls._gt.GalleryTab._show_tag_dialog = cls._orig_show_tag_dialog
        except Exception:
            pass
        if cls.root is not None:
            try:
                cls.root.destroy()
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

    def _cards(self):
        return list(getattr(self.app, "gallery_cards", {}).keys())

    def _dry_run_tag(self):
        """Run tag_gallery_image with a recorder instead of real writes."""
        rec = []
        self.app._propagate_tags_to_related = lambda p, t: rec.append(str(p))
        try:
            self.app.tag_gallery_image()
        finally:
            try:
                del self.app.__dict__["_propagate_tags_to_related"]
            except Exception:
                pass
        return rec

    def test_ctrl_click_multi_select_tags_all_selected(self):
        cards = self._cards()
        if len(cards) < 3:
            raise unittest.SkipTest("fewer than 3 gallery cards in this environment")
        paths = cards[:3]
        self.app._on_thumbnail_click(Path(paths[0]), False)
        self.app._on_thumbnail_click(Path(paths[1]), True)
        self.app._on_thumbnail_click(Path(paths[2]), True)
        self.assertEqual(set(self.app.selected_gallery_paths), set(paths))
        self.assertEqual(self.app.btn_tag_image.cget("text"), "Tag 3 Images")
        targets = self._dry_run_tag()
        self.assertEqual(sorted(targets), sorted(paths))

    def test_single_pick_in_other_view_retargets(self):
        cards = self._cards()
        if len(cards) < 2:
            raise unittest.SkipTest("fewer than 2 gallery cards in this environment")
        self.app._on_thumbnail_click(Path(cards[0]), False)
        self.app._on_thumbnail_click(Path(cards[1]), True)
        target = Path(cards[0])
        self.app._select_manual_image(target)  # exercises the cross-view sync
        self.assertEqual(set(self.app.selected_gallery_paths), {str(target)})
        targets = self._dry_run_tag()
        self.assertEqual(targets, [str(target)])

    def test_plain_click_resets_multi_selection(self):
        cards = self._cards()
        if len(cards) < 3:
            raise unittest.SkipTest("fewer than 3 gallery cards in this environment")
        self.app._on_thumbnail_click(Path(cards[0]), False)
        self.app._on_thumbnail_click(Path(cards[1]), True)
        self.app._on_thumbnail_click(Path(cards[2]), False)
        self.assertEqual(set(self.app.selected_gallery_paths), {cards[2]})
        self.assertEqual(self.app.btn_tag_image.cget("text"), "Tag Image")


if __name__ == "__main__":
    unittest.main()
