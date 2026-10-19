"""Tests for backup_manifest: build, load, and re-key tags onto restored files."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import backup_manifest as bm


def _write(path, data=b"image-bytes"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


class _Base(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.app = self.root / "old-install"
        self.app.mkdir()

    def _collection(self, app=None):
        app = app or self.app
        a = _write(app / "wallpapers" / "generated" / "a.png", b"aaa")
        b = _write(app / "wallpapers" / "manual" / "b.png", b"bbb")
        c = _write(app / "wallpapers" / "favorites" / "c.png", b"ccc")
        _write(app / "wallpapers" / "generated" / "notes.txt", b"nope")
        return a, b, c


class TestBuild(_Base):

    def test_images_are_listed_with_relative_paths(self):
        self._collection()
        manifest = bm.build_manifest(self.app, tags={}, config={})

        self.assertEqual(manifest["schema"], bm.SCHEMA_VERSION)
        self.assertEqual(manifest["image_count"], 3)
        rels = {image["rel_path"] for image in manifest["images"]}
        self.assertEqual(rels, {
            "wallpapers/generated/a.png",
            "wallpapers/manual/b.png",
            "wallpapers/favorites/c.png",
        })
        self.assertNotIn("wallpapers/generated/notes.txt", rels)

    def test_tags_and_prompt_params_are_attached(self):
        a, _b, _c = self._collection()
        tags = {"tags": {str(a.resolve()): {
            "tags": ["frog", "neon"],
            "prompt_params": {"subject": "frog"},
        }}}
        manifest = bm.build_manifest(self.app, tags=tags, config={})
        entry = next(i for i in manifest["images"] if i["name"] == "a.png")

        self.assertEqual(entry["tags"], ["frog", "neon"])
        self.assertEqual(entry["prompt_params"], {"subject": "frog"})
        self.assertFalse(entry["favorite"])

    def test_favorites_are_flagged(self):
        self._collection()
        manifest = bm.build_manifest(self.app, tags={}, config={})
        fav = next(i for i in manifest["images"] if i["name"] == "c.png")
        self.assertTrue(fav["favorite"])

    def test_safe_config_excludes_every_secret(self):
        config = {
            "app_theme": "darkforest",
            "slideshow_interval": 60,
            "oauth_tokens": {"google_drive": "ya29.secret"},
            "google_client_secret": "GOCSPX-nope",
            "dropbox_app_key": "abc123",
            "hf_token": "hf_nope",
        }
        safe = bm.safe_config(config)
        self.assertEqual(safe["app_theme"], "darkforest")
        self.assertEqual(safe["slideshow_interval"], 60)
        self.assertEqual(set(safe), {"app_theme", "slideshow_interval"})
        dumped = json.dumps(safe).lower()
        for marker in ("token", "secret", "gocspx", "hf_"):
            self.assertNotIn(marker, dumped)

    def test_provided_hashes_are_reused_without_rehashing(self):
        self._collection()
        manifest = bm.build_manifest(
            self.app, tags={}, config={},
            hashes={"wallpapers/generated/a.png": "deadbeef" * 8})

        by_name = {image["name"]: image for image in manifest["images"]}
        self.assertEqual(by_name["a.png"]["sha256"], "deadbeef" * 8)
        self.assertEqual(len(by_name["b.png"]["sha256"]), 64)

    def test_write_manifest_round_trips(self):
        self._collection()
        path, manifest = bm.write_manifest(self.app, tags={}, config={})

        self.assertTrue(path.exists())
        loaded = bm.load_manifest(path)
        self.assertEqual(loaded["image_count"], manifest["image_count"])
        self.assertEqual(loaded["images"][0]["rel_path"][:10], "wallpapers")


class TestLoad(_Base):

    def test_missing_and_malformed_files_return_none(self):
        self.assertIsNone(bm.load_manifest(self.root / "nope.json"))
        bad = self.root / "bad.json"
        bad.write_text("{not json")
        self.assertIsNone(bm.load_manifest(bad))

    def test_manifest_without_images_is_rejected(self):
        path = self.root / "empty.json"
        path.write_text(json.dumps({"schema": 1}))
        self.assertIsNone(bm.load_manifest(path))

    def test_newer_schema_is_accepted(self):
        path = self.root / "future.json"
        path.write_text(json.dumps({
            "schema": bm.SCHEMA_VERSION + 5,
            "images": [],
            "some_future_field": True,
        }))
        loaded = bm.load_manifest(path)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["images"], [])

    def test_manifest_for_source_reads_folder(self):
        _write(self.app / "wallpapers" / "generated" / "a.png")
        bm.write_manifest(self.app, tags={}, config={})
        self.assertIsNotNone(bm.manifest_for_source(self.app))
        self.assertIsNone(bm.manifest_for_source(self.root / "elsewhere"))


class TestApply(_Base):

    def _manifest(self):
        a, b, c = self._collection()
        tags = {"tags": {
            str(a.resolve()): {"tags": ["frog"],
                               "prompt_params": {"subject": "frog"}},
            str(b.resolve()): {"tags": ["swamp"]},
        }}
        # Written to disk too, so the folder-based import path is covered.
        _path, manifest = bm.write_manifest(self.app, tags=tags, config={})
        return manifest

    def test_tags_are_rekeyed_to_the_new_install(self):
        manifest = self._manifest()
        new_app = self.root / "new-install"
        target = _write(new_app / "wallpapers" / "generated" / "a.png",
                        b"aaa")
        calls = []

        counts = bm.apply_manifest(
            manifest, [target], new_app,
            add_tags=lambda path, tags: calls.append((Path(path), tags)),
            save_params=lambda path, params: calls.append(("params", params)),
            get_params=lambda path: {},
        )

        self.assertEqual(counts["tagged"], 1)
        self.assertEqual(counts["prompt_params"], 1)
        self.assertIn((target, ["frog"]), calls)
        self.assertIn(("params", {"subject": "frog"}), calls)

    def test_files_not_restored_are_skipped(self):
        manifest = self._manifest()
        new_app = self.root / "new-install"
        target = _write(new_app / "wallpapers" / "generated" / "a.png", b"aaa")
        calls = []

        counts = bm.apply_manifest(
            manifest, [target], new_app,
            add_tags=lambda path, tags: calls.append(path),
            save_params=lambda path, params: None,
            get_params=lambda path: {},
        )

        self.assertEqual(counts["skipped"], 2)
        self.assertEqual(calls, [target])

    def test_existing_prompt_params_win(self):
        manifest = self._manifest()
        new_app = self.root / "new-install"
        target = _write(new_app / "wallpapers" / "generated" / "a.png", b"aaa")
        saved = []

        bm.apply_manifest(
            manifest, [target], new_app,
            add_tags=lambda path, tags: None,
            save_params=lambda path, params: saved.append(params),
            get_params=lambda path: {"subject": "local-choice"},
        )

        self.assertEqual(saved, [])

    def test_paths_outside_the_app_dir_are_refused(self):
        manifest = self._manifest()
        outside = _write(self.root / "elsewhere" / "a.png", b"aaa")
        calls = []

        counts = bm.apply_manifest(
            manifest, [outside], self.app,
            add_tags=lambda path, tags: calls.append(path),
            save_params=lambda path, params: None,
            get_params=lambda path: {},
        )

        self.assertEqual(calls, [])
        self.assertEqual(counts["tagged"], 0)

    def test_apply_manifest_from_folder(self):
        manifest = self._manifest()  # writes into self.app
        new_app = self.root / "new-install"
        target = _write(new_app / "wallpapers" / "generated" / "a.png", b"aaa")
        calls = []

        counts = bm.apply_manifest_from_folder(
            self.app, [target], new_app,
            add_tags=lambda path, tags: calls.append(tags),
            save_params=lambda path, params: None,
            get_params=lambda path: {},
        )

        self.assertIsNotNone(counts)
        self.assertIn(["frog"], calls)
        self.assertTrue((self.app / bm.MANIFEST_NAME).exists())
        self.assertIsNone(bm.apply_manifest_from_folder(
            self.root / "nowhere", [target], new_app))


if __name__ == "__main__":
    unittest.main()
