"""Performance pass tests (improvement report §6).

Covers the performance slice:
  - gallery_manager tag read memo: get_tags_for_image reads once per path
    until the next tag WRITE (kills the N+1 session-per-image cost on
    every gallery view load); every writing function invalidates the memo.
  - GalleryTab._img_dims: image dimensions are cached across view loads
    (resolution sorts + card info lines used to open every image every
    time); unreadable files yield (0, 0) without raising.
  - GalleryTab._info_line_for: the '1920x1080 - 2.1 MB' card line is built
    from the cached dimensions.
  - GalleryTab deferred grid thumbnails: Favorites/Styled/Manual cards get
    a text placeholder first and the SAME label is reconfigured in place
    when the background decode arrives — the UI thread never opens an
    image; stale generations and destroyed labels are ignored safely.
  - GalleryTab resize handlers (favorites/manual/styled) are debounced
    like the main gallery instead of re-gridding on every Configure event.
  - KeywordExpander.add_user_mapping / remove_user_mapping invalidate the
    per-word expansion cache, so editing a mapping applies immediately
    (previously stale expansions survived until app restart).

Runs headless-safe: Tk tests skip automatically without a display (on
Linux CI run under xvfb; on Windows they run natively). Every file path
is redirected into a per-test temp directory; _get_db is patched to None
so the real frogpaper.db and gallery_tags.json are never touched.
"""

import inspect
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import tkinter as tk
    _TK = True
except ImportError:  # pragma: no cover
    _TK = False

try:
    from unittest.mock import patch
    import gallery_manager as gm
    _GM = True
except Exception:  # pragma: no cover
    _GM = False

try:
    import gallery_tab as gt
    _GT = True
except Exception:  # pragma: no cover
    _GT = False

try:
    import keyword_expander as ke
    _KE = True
except Exception:  # pragma: no cover
    _KE = False

try:
    from PIL import Image
    _PIL = True
except ImportError:  # pragma: no cover
    _PIL = False


def _make_png(path, width, height, color=(40, 120, 60)):
    """Write a tiny real PNG so PIL header reads have something to read."""
    Image.new("RGB", (width, height), color).save(path, format="PNG")
    return path


# ═══════════════════════════════════════════════════════════════════════════
#  Tag read memo (gallery_manager) — no display needed
# ═══════════════════════════════════════════════════════════════════════════

@unittest.skipUnless(_GM, "gallery_manager unavailable")
class TestTagsMemo(unittest.TestCase):
    """get_tags_for_image memoizes reads; every writer drops the memo."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self._patch(gm, "TAGS_FILE", self.tmp / "gallery_tags.json")
        self._patch(gm, "_get_db", lambda: None)  # never touch a real DB
        gm._TAGS_CACHE.clear()
        self.addCleanup(gm._TAGS_CACHE.clear)

    def _patch(self, target, name, value):
        patcher = patch.object(target, name, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _write_tags_file(self, data):
        (self.tmp / "gallery_tags.json").write_text(
            json.dumps(data), encoding="utf-8")

    def test_repeated_reads_hit_the_memo_once(self):
        self._write_tags_file(
            {"tags": {"/img/a.png": {"tags": ["frog"], "tagged_at": ""}}})
        calls = []
        original = gm._read_tags_for_image

        def counting(path):
            calls.append(path)
            return original(path)

        self._patch(gm, "_read_tags_for_image", counting)
        first = gm.get_tags_for_image("/img/a.png")
        second = gm.get_tags_for_image("/img/a.png")
        self.assertEqual(first, ["frog"])
        self.assertEqual(second, ["frog"])
        self.assertEqual(len(calls), 1, "second read must come from the memo")

    def test_memo_returns_copies_not_internal_lists(self):
        self._write_tags_file(
            {"tags": {"/img/a.png": {"tags": ["frog"], "tagged_at": ""}}})
        got = gm.get_tags_for_image("/img/a.png")
        got.append("mutation")
        self.assertEqual(gm.get_tags_for_image("/img/a.png"), ["frog"])

    def test_write_refreshes_memo_end_to_end(self):
        self._write_tags_file({"tags": {}})
        path = str(self.tmp / "b.png")
        self.assertEqual(gm.get_tags_for_image(path), [])
        gm.add_tags_to_paths([path], ["frog"])
        # The [] read above was memoized; the write must have dropped it.
        self.assertEqual(gm.get_tags_for_image(path), ["frog"])

    def test_add_tags_to_paths_invalidates_even_on_early_return(self):
        gm._TAGS_CACHE["/img/stale.png"] = ["old"]
        gm.add_tags_to_paths([], ["never-applied"])
        self.assertEqual(gm._TAGS_CACHE, {})

    def test_rename_invalidates_without_touching_files(self):
        gm._TAGS_CACHE["/img/stale.png"] = ["old"]
        self.assertIsNone(gm.rename_image("/img/does-not-exist.png", "x.png"))
        self.assertEqual(gm._TAGS_CACHE, {})

    def test_every_writer_calls_invalidate(self):
        """Tripwire: a future writer that forgets invalidation fails here."""
        writers = [
            "save_tags", "add_tags_to_image", "add_tags_to_paths",
            "remove_tag_from_image", "cleanup_orphaned_tags",
            "rename_image", "delete_image_and_tags",
        ]
        for name in writers:
            src = inspect.getsource(getattr(gm, name))
            self.assertIn("_invalidate_tags_cache()", src,
                          f"{name}() forgot to invalidate the tags memo")


# ═══════════════════════════════════════════════════════════════════════════
#  Image-dimension cache — no display needed
# ═══════════════════════════════════════════════════════════════════════════

@unittest.skipUnless(_GT and _PIL, "gallery_tab / PIL unavailable")
class TestImageDimsCache(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.tab = gt.GalleryTab.__new__(gt.GalleryTab)
        self.app = SimpleNamespace()
        self.tab.app = self.app

    def test_dimensions_read_once_then_cached(self):
        png = _make_png(self.tmp / "a.png", 64, 32)
        self.assertEqual(self.tab._img_dims(png), (64, 32))
        png.unlink()  # a cache hit must not re-open the (now gone) file
        self.assertEqual(self.tab._img_dims(png), (64, 32))

    def test_unreadable_file_yields_zero_zero(self):
        bad = self.tmp / "bad.png"
        bad.write_text("not an image", encoding="utf-8")
        self.assertEqual(self.tab._img_dims(bad), (0, 0))
        self.assertEqual(self.tab._img_dims(self.tmp / "missing.png"), (0, 0))

    def test_info_line_combines_dims_and_size(self):
        png = _make_png(self.tmp / "a.png", 32, 16)
        info = self.tab._info_line_for(png)
        self.assertIn("32\u00d716", info)
        self.assertIn("KB", info)

    def test_info_line_for_missing_file_is_empty(self):
        self.assertEqual(self.tab._info_line_for(self.tmp / "nope.png"), "")


# ═══════════════════════════════════════════════════════════════════════════
#  Expansion cache invalidation — no display needed
# ═══════════════════════════════════════════════════════════════════════════

@unittest.skipUnless(_KE, "keyword_expander unavailable")
class TestExpansionCacheInvalidation(unittest.TestCase):
    """Editing a user mapping must apply immediately, not after restart."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        (self.tmp / "logs").mkdir()
        self.addCleanup(self._tmp.cleanup)
        self._patch(ke, "BASE_DIR", self.tmp)
        self._patch(ke, "KEYWORDS_FILE", self.tmp / "keywords.json")
        self._patch(ke, "LOGS_DIR", self.tmp / "logs")
        self._patch(ke, "_get_db", lambda: None)  # never touch a real DB

    def _patch(self, target, name, value):
        patcher = patch.object(target, name, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _expander(self):
        (self.tmp / "keywords.json").write_text(
            json.dumps({"animals": ["frog", "cat"]}), encoding="utf-8")
        expander = ke.KeywordExpander()
        expander.initialize()
        return expander

    def test_added_mapping_overrides_cached_expansion(self):
        exp = self._expander()
        # "frog" is a known keyword -> cached as unchanged
        self.assertEqual(exp.expand_text("frog"), "frog")
        exp.add_user_mapping("frog", "enchanted frog")
        self.assertEqual(exp.expand_text("frog"), "enchanted frog",
                         "stale cache entry shadowed the new mapping")

    def test_removed_mapping_reverts_expansion(self):
        exp = self._expander()
        exp.add_user_mapping("cat", "cursed cat")
        self.assertEqual(exp.expand_text("cat"), "cursed cat")
        exp.remove_user_mapping("cat")
        # "cat" is a known keyword again -> back to unchanged
        self.assertEqual(exp.expand_text("cat"), "cat")


# ═══════════════════════════════════════════════════════════════════════════
#  Deferred grid thumbnails — need a display
# ═══════════════════════════════════════════════════════════════════════════

@unittest.skipUnless(_TK and _GT and _PIL, "tkinter / gallery_tab / PIL unavailable")
class TestDeferredGridThumbs(unittest.TestCase):
    """Favorites/Styled/Manual thumbs decode off the UI thread, in place."""

    def setUp(self):
        if not _TK:
            self.skipTest("tkinter unavailable")
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("no display available (headless environment)")
        self.root.withdraw()
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

        # gallery_tab calls schedule_ui_update/run_background as module
        # globals — patch them to SYNCHRONOUS versions so tests are
        # deterministic (worker runs inline, UI callbacks run immediately).
        self._patch(gt, "schedule_ui_update",
                    lambda cb, *a, **k: cb(*a, **k))
        self._patch(gt, "run_background",
                    lambda target, *a, **k: target(*a, **k))

        self.tab = gt.GalleryTab.__new__(gt.GalleryTab)
        self.app = SimpleNamespace(root=self.root, thumb_cache={},
                                   favorite_thumb_refs=[],
                                   small_font=("Segoe UI", 9))
        self.tab.app = self.app
        self.tab._fade_jobs = {}   # normally initialized in __init__
        self.pal = {"panel": "#20242c", "muted": "#8892a0"}

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def _patch(self, target, name, value):
        original = getattr(target, name)
        setattr(target, name, value)
        self.addCleanup(setattr, target, name, original)

    def test_cache_miss_shows_placeholder_and_queues_decode(self):
        png = _make_png(self.tmp / "a.png", 60, 40)
        label = self.tab._attach_card_thumb(self.root, self.pal, png)
        self.assertEqual(label.cget("text"), "\u2026")  # placeholder first
        self.assertEqual(str(self.app.thumb_cache.get(str(png))), "None")

        self.tab._start_grid_thumb_worker()  # synchronous patched worker
        self.assertEqual(label.cget("text"), "")  # swapped in place
        self.assertTrue(label.cget("image"))      # now has a photo
        self.assertIn(str(png), self.app.thumb_cache)

    def test_click_bindings_live_before_and_after_image_arrives(self):
        png = _make_png(self.tmp / "a.png", 60, 40)
        clicks = []
        label = self.tab._attach_card_thumb(
            self.root, self.pal, png,
            on_click=lambda e: clicks.append("pre"))
        # Button events only deliver to VIEWABLE windows — show the root
        self.root.deiconify()
        self.root.update()
        label.event_generate("<Button-1>")
        self.root.update()
        self.assertEqual(clicks, ["pre"])
        self.tab._start_grid_thumb_worker()
        label.event_generate("<Button-1>")
        self.root.update()
        self.assertEqual(clicks, ["pre", "pre"],
                         "bindings must survive the in-place swap")

    def test_cache_hit_shows_image_immediately(self):
        png = _make_png(self.tmp / "a.png", 60, 40)
        self.app.thumb_cache[str(png)] = tk.PhotoImage(width=1, height=1)
        label = self.tab._attach_card_thumb(self.root, self.pal, png)
        self.assertEqual(label.cget("text"), "")
        self.assertTrue(label.cget("image"))

    def test_stale_generation_is_dropped_on_arrival(self):
        png = _make_png(self.tmp / "a.png", 60, 40)
        label = self.tab._attach_card_thumb(self.root, self.pal, png)
        stale_seq = getattr(self.tab, "_grid_load_seq", 0)
        self.tab._bump_grid_load_seq()       # a NEW view load happened
        self.tab._apply_grid_thumbs([(label, None)], stale_seq)
        self.assertEqual(label.cget("text"), "\u2026")  # untouched

    def test_destroyed_label_is_ignored_safely(self):
        png = _make_png(self.tmp / "a.png", 60, 40)
        label = self.tab._attach_card_thumb(self.root, self.pal, png)
        seq = getattr(self.tab, "_grid_load_seq", 0)
        label.destroy()
        self.tab._apply_grid_thumbs([(label, None)], seq)  # must not raise

    def test_unreadable_image_marks_error_in_place(self):
        bad = self.tmp / "bad.png"
        bad.write_text("not an image", encoding="utf-8")
        label = self.tab._attach_card_thumb(self.root, self.pal, bad)
        self.tab._start_grid_thumb_worker()
        self.assertIn("image error", label.cget("text"))

    def test_populate_bump_drops_pending_queue(self):
        png = _make_png(self.tmp / "a.png", 60, 40)
        label = self.tab._attach_card_thumb(self.root, self.pal, png)
        self.assertTrue(self.tab._grid_thumb_queue)
        self.tab._bump_grid_load_seq()  # view reloaded while job pending
        self.assertEqual(self.tab._grid_thumb_queue, [])
        self.assertIsNone(self.tab._grid_thumb_job)


# ═══════════════════════════════════════════════════════════════════════════
#  Resize debouncing — need a display
# ═══════════════════════════════════════════════════════════════════════════

@unittest.skipUnless(_TK and _GT, "tkinter / gallery_tab unavailable")
class TestResizeDebounce(unittest.TestCase):
    """fav/manual/styled resizes collapse into one re-grid like the gallery."""

    def setUp(self):
        if not _TK:
            self.skipTest("tkinter unavailable")
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("no display available (headless environment)")
        self.root.withdraw()
        self.tab = gt.GalleryTab.__new__(gt.GalleryTab)

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def _pump_until(self, condition, timeout=2.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            self.root.update()
            if condition():
                return True
            time.sleep(0.01)
        return condition()

    def _debounce_case(self, attr, handler, canvas_attr, item_tag):
        app = SimpleNamespace(root=self.root)
        canvas = tk.Canvas(self.root, width=800, height=200)
        canvas.create_window((0, 0), tags=(item_tag,))
        setattr(app, canvas_attr, canvas)
        rebuilt = []
        setattr(app, "_rebuild_fav_grid" if "fav" in attr
                else "_rebuild_manual_grid" if "manual" in attr
                else "_rebuild_styled_grid",
                lambda cols: rebuilt.append(cols))
        self.tab.app = app
        event = SimpleNamespace(width=800)

        handler(event)
        handler(event)  # second event lands inside the debounce window
        self.assertIsNotNone(getattr(app, attr))

        ok = self._pump_until(lambda: getattr(app, attr) is None)
        self.assertTrue(ok, "debounced job never ran")
        self.assertEqual(rebuilt, [3],
                         "expected exactly ONE collapsed re-grid (cols=3)")

    def test_fav_resize_debounced(self):
        self._debounce_case("_fav_resize_job", self.tab.on_fav_resize,
                            "gallery_fav_canvas", "fav_inner_frame")

    def test_manual_resize_debounced(self):
        self._debounce_case("_manual_resize_job", self.tab.on_manual_resize,
                            "gallery_manual_canvas", "manual_inner_frame")

    def test_styled_resize_debounced(self):
        self._debounce_case("_styled_resize_job", self.tab.on_styled_resize,
                            "gallery_styled_canvas", "styled_inner_frame")


if __name__ == "__main__":
    unittest.main(verbosity=2)
