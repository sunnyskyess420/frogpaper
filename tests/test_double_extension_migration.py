"""Renaming double-extension files must carry the stored paths with it.

Renaming alone breaks the gallery: tags, params, events and favourites all key
off the full path. These tests pin the mapping logic and the rewrite pass
against a throwaway database and favourites file.
"""

import json
import pathlib
import sqlite3
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

import fix_double_extensions as fix  # noqa: E402


class TestScanAndRename(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name)
        (self.root / "sub").mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def test_finds_doubled_extensions_only(self):
        (self.root / "frog_1.png.png").write_bytes(b"x")
        (self.root / "sub" / "frog_2.PNG.PNG").write_bytes(b"x")
        (self.root / "normal.png").write_bytes(b"x")
        (self.root / "notes.txt").write_text("x", encoding="utf-8")
        pairs = fix.scan_directories([self.root])
        self.assertEqual(sorted(old.name for old, _ in pairs),
                         ["frog_1.png.png", "frog_2.PNG.PNG"])

    def test_dry_run_does_not_touch_disk(self):
        old = self.root / "a.png.png"
        old.write_bytes(b"x")
        pairs = fix.scan_directories([self.root])
        fix.rename_files(pairs, apply=False)
        self.assertTrue(old.exists())
        self.assertFalse((self.root / "a.png").exists())

    def test_apply_renames(self):
        old = self.root / "a.png.png"
        old.write_bytes(b"x")
        done, skipped = fix.rename_files(fix.scan_directories([self.root]), apply=True)
        self.assertEqual(len(done), 1)
        self.assertEqual(skipped, [])
        self.assertFalse(old.exists())
        self.assertTrue((self.root / "a.png").exists())

    def test_collision_is_skipped_not_overwritten(self):
        (self.root / "a.png").write_bytes(b"existing")
        (self.root / "a.png.png").write_bytes(b"other")
        done, skipped = fix.rename_files(fix.scan_directories([self.root]), apply=True)
        self.assertEqual(done, [])
        self.assertEqual(len(skipped), 1)
        self.assertEqual((self.root / "a.png").read_bytes(), b"existing")


class TestPathRewrite(unittest.TestCase):
    def test_absolute_paths_are_rewritten(self):
        old = pathlib.Path("/tmp/wallpapers/frog.png.png")
        new = pathlib.Path("/tmp/wallpapers/frog.png")
        self.assertEqual(fix.rewrite_stored_path(str(old), {fix._resolved(old): new}), str(new))

    def test_unrelated_path_left_alone(self):
        old = pathlib.Path("/tmp/wallpapers/frog.png.png")
        self.assertIsNone(fix.rewrite_stored_path("/tmp/wallpapers/owl.png", {fix._resolved(old): old}))

    def test_blank_input(self):
        self.assertIsNone(fix.rewrite_stored_path("", {}))


class TestDatabaseRewrite(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name)
        self.db = self.root / "test.db"
        con = sqlite3.connect(self.db)
        con.execute("create table image_tags (id integer primary key, image_path text)")
        con.execute("create table prompt_params (id integer primary key, image_path text)")
        con.execute("create table history (id integer primary key, image_path text)")
        self.old_file = self.root / "frog.png.png"
        self.old_file.write_bytes(b"x")
        self.new_file = self.root / "frog.png"
        con.execute("insert into image_tags (image_path) values (?)", (str(self.old_file),))
        con.execute("insert into prompt_params (image_path) values (?)", (str(self.old_file),))
        con.execute("insert into history (image_path) values (?)", (str(self.old_file),))
        con.execute("insert into image_tags (image_path) values (?)", (str(self.root / "owl.png"),))
        con.commit()
        con.close()
        self.map = {fix._resolved(self.old_file): self.new_file}

    def tearDown(self):
        self._tmp.cleanup()

    def test_counts_and_values(self):
        counts = fix.rewrite_database(self.db, self.map, apply=True)
        self.assertEqual(counts["image_tags"], 1)
        self.assertEqual(counts["prompt_params"], 1)
        self.assertEqual(counts["history"], 1)

        con = sqlite3.connect(self.db)
        paths = [r[0] for r in con.execute("select image_path from image_tags order by id")]
        con.close()
        self.assertEqual(paths[0], str(self.new_file))
        self.assertEqual(paths[1], str(self.root / "owl.png"))

    def test_dry_run_writes_nothing(self):
        fix.rewrite_database(self.db, self.map, apply=False)
        con = sqlite3.connect(self.db)
        stored = con.execute("select image_path from image_tags order by id").fetchone()[0]
        con.close()
        self.assertEqual(stored, str(self.old_file))


class TestFavoritesRewrite(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name)
        self.json = self.root / "favorites.json"
        self.old = self.root / "frog.png.png"
        self.new = self.root / "frog.png"
        self.json.write_text(json.dumps([{
            "original_image_path": str(self.old),
            "image_path": str(self.old),
            "copied_image_path": None,
            "theme_sentence": "untouched",
        }]), encoding="utf-8")
        self.map = {fix._resolved(self.old): self.new}

    def tearDown(self):
        self._tmp.cleanup()

    def test_rewrites_every_path_key(self):
        changed = fix.rewrite_favorites(self.json, self.map, apply=True)
        self.assertEqual(changed, 2)
        entry = json.loads(self.json.read_text(encoding="utf-8"))[0]
        self.assertEqual(entry["original_image_path"], str(self.new))
        self.assertEqual(entry["image_path"], str(self.new))
        self.assertEqual(entry["theme_sentence"], "untouched")

    def test_missing_file_is_not_an_error(self):
        self.assertEqual(fix.rewrite_favorites(self.root / "nope.json", self.map, apply=True), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
