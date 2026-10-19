"""Tests for cloud_catalog.CloudRestoreSource and the checksum helpers.

No network and no real provider: a FakeBackend supplies the same three
primitives the Drive/OneDrive/Dropbox backends implement (resolve_root,
list_children, download), so the tree walk, normalization and the
plan/execute path are exercised end to end.
"""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import backup_manifest as bm
import cloud_catalog as catalog
import cloud_restore as cr


def _item(kind, item_id, name, size=0, algo=None, value=None, modified=0.0):
    return catalog._item(kind, item_id, name, size=size, modified=modified,
                         algo=algo, value=value)


def _folder(item_id, name):
    return _item("folder", item_id, name)


def _file(item_id, name, data, algo="md5"):
    value = None
    if algo == "md5":
        value = hashlib.md5(data).hexdigest()
    elif algo == "sha256":
        value = hashlib.sha256(data).hexdigest()
    return _item("file", item_id, name, size=len(data), algo=algo, value=value)


_UNSET = object()


class FakeBackend:
    name = "fake_cloud"

    def __init__(self, tree, blobs=None, fail=(), resolve=_UNSET,
                 name="fake_cloud"):
        self.tree = tree
        self.blobs = blobs or {}
        self.fail = set(fail)
        self.downloads = []
        self.name = name
        self._resolve = "root" if resolve is _UNSET else resolve

    def resolve_root(self):
        return self._resolve

    def list_children(self, ref):
        return self.tree.get(ref, [])

    def download(self, file_ref, dest):
        if file_ref in self.fail:
            raise cr.RestoreError(f"network died for {file_ref}")
        Path(dest).write_bytes(self.blobs[file_ref])
        self.downloads.append(file_ref)


class _Base(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.app = Path(tmp.name) / "app"
        self.app.mkdir()

    def _tree(self):
        a = b"frog-bytes" * 10
        b = b"swamp-bytes" * 7
        tree = {
            "root": [
                _folder("f-gen", "Generated"),
                _folder("f-fav", "Favorites"),
                _folder("f-junk", "Screenshots"),
            ],
            "f-gen": [_file("id-a", "a.png", a)],
            "f-fav": [_file("id-b", "b.png", b)],
            "f-junk": [_file("id-x", "shot.png", b"x")],
        }
        return tree, {"id-a": a, "id-b": b, "id-x": b"x"}


class TestCatalogListing(_Base):

    def test_maps_subfolders_and_keeps_native_checksum(self):
        tree, blobs = self._tree()
        source = catalog.CloudRestoreSource(FakeBackend(tree, blobs))
        records = source.list_files()

        by_name = {record.name: record for record in records}
        self.assertEqual(set(by_name), {"a.png", "b.png"})
        self.assertEqual(by_name["a.png"].subfolder, "generated")
        self.assertEqual(by_name["b.png"].subfolder, "favorites")
        self.assertEqual(by_name["a.png"].provider, "fake_cloud")
        self.assertEqual(by_name["a.png"].digest,
                         ("md5", hashlib.md5(blobs["id-a"]).hexdigest()))
        self.assertEqual(by_name["a.png"].rel_path,
                         "wallpapers/generated/a.png")

    def test_unknown_folders_and_non_images_are_ignored(self):
        tree, blobs = self._tree()
        tree["f-gen"].append(_file("id-txt", "notes.txt", b"hello"))
        records = catalog.CloudRestoreSource(FakeBackend(tree, blobs)).list_files()
        self.assertNotIn("shot.png", [r.name for r in records])
        self.assertNotIn("notes.txt", [r.name for r in records])

    def test_files_at_the_backup_root_are_legacy_manual(self):
        tree = {"root": [_file("id-root", "old.png", b"legacy")]}
        source = catalog.CloudRestoreSource(FakeBackend(tree))
        records = source.list_files()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].subfolder, "manual")

    def test_missing_backup_folder_raises(self):
        source = catalog.CloudRestoreSource(
            FakeBackend({}, resolve=None))
        with self.assertRaises(catalog.CloudCatalogError):
            source.list_files()

    def test_large_folder_is_listed_completely(self):
        tree = {"root": [_folder("f-gen", "Generated")], "f-gen": []}
        blobs = {}
        for index in range(250):
            name = f"img{index:03d}.png"
            data = f"data{index}".encode()
            tree["f-gen"].append(_file(f"id-{index}", name, data))
            blobs[f"id-{index}"] = data
        records = catalog.CloudRestoreSource(FakeBackend(tree, blobs)).list_files()
        self.assertEqual(len(records), 250)

    def test_unknown_provider_is_rejected(self):
        with self.assertRaises(catalog.CloudCatalogError):
            catalog.make_cloud_source("floppy_disk", object())


class TestCloudRestore(_Base):

    def test_md5_identical_file_is_skipped(self):
        tree, blobs = self._tree()
        target = self.app / "wallpapers" / "generated" / "a.png"
        target.parent.mkdir(parents=True)
        target.write_bytes(blobs["id-a"])

        source = catalog.CloudRestoreSource(FakeBackend(tree, blobs))
        plan = cr.build_plan(source.list_files(), self.app)

        statuses = {item.remote.name: item.status for item in plan.items}
        self.assertEqual(statuses["a.png"], cr.RestoreStatus.IDENTICAL)
        self.assertEqual(statuses["b.png"], cr.RestoreStatus.MISSING)

    def test_missing_file_is_downloaded_and_verified(self):
        tree, blobs = self._tree()
        backend = FakeBackend(tree, blobs)
        source = catalog.CloudRestoreSource(backend)

        plan = cr.build_plan(source.list_files(), self.app)
        result = cr.RestoreExecutor(source, plan).run()

        self.assertTrue(result.ok)
        self.assertEqual(len(result.written), 2)
        self.assertEqual(
            (self.app / "wallpapers" / "generated" / "a.png").read_bytes(),
            blobs["id-a"])
        self.assertIn("id-a", backend.downloads)

    def test_corrupt_download_fails_verification(self):
        tree, blobs = self._tree()
        backend = FakeBackend(tree, blobs)
        backend.blobs = dict(blobs)
        # Same length so the size check passes and the MD5 check is what fires.
        backend.blobs["id-a"] = b"Z" * len(blobs["id-a"])

        source = catalog.CloudRestoreSource(backend)
        plan = cr.build_plan(source.list_files(), self.app)
        result = cr.RestoreExecutor(source, plan).run()

        self.assertEqual(len(result.failures), 1)
        self.assertIn("MD5", result.failures[0][1])
        self.assertFalse(
            (self.app / "wallpapers" / "generated" / "a.png").exists())

    def test_download_error_is_recorded_not_fatal(self):
        tree, blobs = self._tree()
        backend = FakeBackend(tree, blobs, fail={"id-a"})
        source = catalog.CloudRestoreSource(backend)

        plan = cr.build_plan(source.list_files(), self.app)
        result = cr.RestoreExecutor(source, plan).run()

        self.assertEqual(len(result.failures), 1)
        self.assertEqual(len(result.written), 1)  # b.png still restored

    def test_file_without_provider_checksum_is_not_treated_as_identical(self):
        data = b"no-hash-here"
        tree = {
            "root": [_folder("f-gen", "Generated")],
            "f-gen": [_item("file", "id-n", "n.png", size=len(data))],
        }
        target = self.app / "wallpapers" / "generated" / "n.png"
        target.parent.mkdir(parents=True)
        target.write_bytes(data)

        source = catalog.CloudRestoreSource(FakeBackend(tree, {"id-n": data}))
        plan = cr.build_plan(source.list_files(), self.app)
        self.assertEqual(plan.items[0].status, cr.RestoreStatus.CONFLICT)


class TestCloudRestoreSet(_Base):

    def _source(self, provider_name, item_id, data):
        tree = {
            "root": [_folder("f-gen", "Generated")],
            "f-gen": [_file(item_id, "same.png", data)],
        }
        backend = FakeBackend(tree, {item_id: data}, name=provider_name)
        return catalog.CloudRestoreSource(backend), backend

    def test_identical_records_across_providers_are_merged(self):
        data = b"same-bytes"
        drive, _ = self._source("google_drive", "id-1", data)
        dropbox, _ = self._source("dropbox", "id-2", data)

        sources = catalog.CloudRestoreSet([drive, dropbox])
        records = sources.list_files()

        self.assertEqual(len(records), 1)
        self.assertIn("google_drive", sources.label)
        self.assertIn("dropbox", sources.label)

    def test_different_content_is_kept_per_provider(self):
        drive, _ = self._source("google_drive", "id-1", b"one")
        dropbox, _ = self._source("dropbox", "id-2", b"two")

        records = catalog.CloudRestoreSet([drive, dropbox]).list_files()
        self.assertEqual(len(records), 2)

    def test_fetch_routes_to_the_owning_provider(self):
        data = b"routing"
        drive, drive_backend = self._source("google_drive", "id-1", data)
        dropbox, dropbox_backend = self._source("dropbox", "id-2", data + b"!")

        sources = catalog.CloudRestoreSet([drive, dropbox])
        plan = cr.build_plan(sources.list_files(), self.app)
        result = cr.RestoreExecutor(sources, plan).run()

        self.assertTrue(result.ok)
        self.assertEqual(len(drive_backend.downloads), 1)
        self.assertEqual(len(dropbox_backend.downloads), 1)
        self.assertEqual(
            (self.app / "wallpapers" / "generated" / "same.png").read_bytes(),
            data)

    def test_empty_set_raises(self):
        with self.assertRaises(catalog.CloudCatalogError):
            catalog.CloudRestoreSet([]).list_files()


class TestCloudManifest(_Base):

    def _source(self, provider_name="google_drive", image_count=2, raw=None,
                include_manifest=True):
        manifest = {
            "schema": 1,
            "images": [
                {
                    "rel_path": "wallpapers/generated/a.png",
                    "subfolder": "generated",
                    "tags": ["frog"],
                    "prompt_params": {"subject": "frog"},
                },
            ][:image_count],
        }
        data = raw if raw is not None else json.dumps(manifest).encode()
        tree = {
            "root": [_folder("f-gen", "Generated")],
            "f-gen": [_file("id-a", "a.png", b"aaa")],
        }
        if include_manifest:
            tree["root"].append(
                _item("file", "m-1", "backup-manifest.json", size=len(data)))
        backend = FakeBackend(tree, {"id-a": b"aaa", "m-1": data},
                              name=provider_name)
        return catalog.CloudRestoreSource(backend)

    def test_manifest_is_fetched_and_parsed(self):
        manifest = self._source().fetch_manifest()
        self.assertIsNotNone(manifest)
        self.assertEqual(manifest["images"][0]["tags"], ["frog"])

    def test_backup_without_manifest_returns_none(self):
        self.assertIsNone(self._source(include_manifest=False).fetch_manifest())

    def test_unreadable_manifest_returns_none(self):
        source = self._source(raw=b"{broken")
        self.assertIsNone(source.fetch_manifest())

    def test_set_prefers_the_richer_manifest(self):
        sparse = self._source("google_drive", image_count=1)
        richer = self._source("dropbox")
        richer_manifest = richer.fetch_manifest()
        richer_manifest["images"].append({
            "rel_path": "wallpapers/generated/b.png", "tags": ["swamp"]})
        # Re-encode so the backend serves the larger document.
        richer.backend.blobs["m-1"] = json.dumps(richer_manifest).encode()

        merged = catalog.CloudRestoreSet([sparse, richer]).fetch_manifest()
        self.assertEqual(len(merged["images"]), 2)

    def test_restored_cloud_files_receive_manifest_tags(self):
        source = self._source()
        records = source.list_files()
        plan = cr.build_plan(records, self.app)
        result = cr.RestoreExecutor(source, plan).run()
        self.assertTrue(result.ok)

        calls = []
        counts = bm.apply_manifest(
            source.fetch_manifest(), result.written, self.app,
            add_tags=lambda path, tags: calls.append((Path(path), tags)),
            save_params=lambda path, params: calls.append(("params", params)),
            get_params=lambda path: {},
        )

        self.assertEqual(counts["tagged"], 1)
        self.assertEqual(calls[0][0],
                         self.app / "wallpapers" / "generated" / "a.png")
        self.assertEqual(calls[0][1], ["frog"])


class TestChecksums(_Base):

    def test_sha256_matches_helper(self):
        path = self.app / "x.bin"
        path.write_bytes(b"payload")
        self.assertEqual(cr.compute_digest(path, "sha256"), cr.sha256_file(path))

    def test_md5_and_sha1(self):
        path = self.app / "x.bin"
        data = b"payload"
        path.write_bytes(data)
        self.assertEqual(cr.compute_digest(path, "md5"), hashlib.md5(data).hexdigest())
        self.assertEqual(cr.compute_digest(path, "sha1"), hashlib.sha1(data).hexdigest())

    def test_dropbox_hash_for_single_block(self):
        path = self.app / "x.bin"
        data = b"dropbox-content"
        path.write_bytes(data)
        expected = hashlib.sha256(hashlib.sha256(data).digest()).hexdigest()
        self.assertEqual(cr.compute_digest(path, "dropbox"), expected)

    def test_unknown_algorithm_is_rejected(self):
        path = self.app / "x.bin"
        path.write_bytes(b"x")
        with self.assertRaises(cr.RestoreError):
            cr.compute_digest(path, "crc32")


if __name__ == "__main__":
    unittest.main()
