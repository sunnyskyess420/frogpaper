"""Tests for keeping recorded cloud ids honest about the current backup folder.

The bug these cover: after the backup folder was replaced (renamed, reinstalled,
re-uploaded by another install) ``sync_metadata.json`` still pointed at the old
copies. The hashes matched, so every later sync skipped those files, and a
restore failed with 403 because the old copies were written by a different
OAuth client. The folder's actual contents must override the stale ids.

No network: the catalog listing is replaced with a dict.
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sync_manager as sm


class FakeProvider:
    authenticated = True

    def __init__(self, upload_result="new-id"):
        self.upload_result = upload_result
        self.last_upload_reason = None
        self.upload_calls = []

    def upload_file(self, file_path, subfolder=""):
        self.upload_calls.append((Path(file_path), subfolder))
        return self.upload_result

    def get_file_size(self, file_ref):
        return None

    def delete_file(self, file_ref):
        return True


class _SyncTestBase(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

        self._saved = {
            "BASE_DIR": sm.BASE_DIR,
            "SYNC_METADATA_FILE": sm.SYNC_METADATA_FILE,
            "GENERATED_DIR": sm.GENERATED_DIR,
            "MANUAL_DIR": sm.MANUAL_DIR,
            "FAVORITES_DIR": sm.FAVORITES_DIR,
            "STYLED_DIR": sm.STYLED_DIR,
            "_list_cloud_files": sm._list_cloud_files,
        }
        generated = self.root / "wallpapers" / "generated"
        manual = self.root / "wallpapers" / "manual"
        for folder in (generated, manual):
            folder.mkdir(parents=True)
        sm.BASE_DIR = self.root
        sm.SYNC_METADATA_FILE = self.root / "sync_metadata.json"
        sm.GENERATED_DIR = generated
        sm.MANUAL_DIR = manual
        sm.FAVORITES_DIR = self.root / "wallpapers" / "favorites"
        sm.STYLED_DIR = self.root / "wallpapers" / "styled"
        self.addCleanup(self._restore)

        self.listing = {}
        sm._list_cloud_files = lambda name, provider: self.listing.get(name, {})

        self.manager = sm.SyncManager(app=None)
        self.rel = Path("wallpapers") / "generated" / "frog.png"
        self.path = self.root / self.rel
        self.path.write_bytes(b"pixels")
        self.key = str(self.rel)

    def _restore(self):
        for name, value in self._saved.items():
            setattr(sm, name, value)

    def _record(self, remote=None):
        self.manager.sync_metadata["files"][self.key] = {
            "hash": self.manager._compute_file_hash(self.path),
            "modified": "2026-10-19T00:00:00",
            "size": self.path.stat().st_size,
            "remote": remote if remote is not None else {"google_drive": "old"},
        }

    def _added(self):
        return self.manager._detect_changes()[0]


class TestReconcileRemoteIds(_SyncTestBase):

    def test_id_missing_from_the_folder_is_dropped(self):
        self.manager.providers = {"google_drive": FakeProvider()}
        self.listing = {"google_drive": {}}
        self._record()

        self.assertEqual(self.manager._reconcile_remote_ids(), 1)
        self.assertEqual(self.manager.sync_metadata["files"][self.key]["remote"], {})

    def test_dropped_id_makes_the_file_upload_again(self):
        self.manager.providers = {"google_drive": FakeProvider()}
        self.listing = {"google_drive": {}}
        self._record()

        self.manager._reconcile_remote_ids()

        self.assertEqual(self._added(), [self.path])

    def test_id_for_a_different_copy_is_repointed(self):
        self.manager.providers = {"google_drive": FakeProvider()}
        self.listing = {"google_drive": {("generated", "frog.png"): "live-id"}}
        self._record()

        self.assertEqual(self.manager._reconcile_remote_ids(), 1)
        self.assertEqual(
            self.manager.sync_metadata["files"][self.key]["remote"],
            {"google_drive": "live-id"})
        self.assertEqual(self._added(), [])

    def test_matching_id_is_left_alone(self):
        self.manager.providers = {"google_drive": FakeProvider()}
        self.listing = {"google_drive": {("generated", "frog.png"): "live-id"}}
        self._record(remote={"google_drive": "live-id"})

        self.assertEqual(self.manager._reconcile_remote_ids(), 0)
        self.assertEqual(self._added(), [])

    def test_unlistable_provider_keeps_its_ids(self):
        def boom(name, provider):
            raise RuntimeError("network down")

        sm._list_cloud_files = boom
        self.manager.providers = {"google_drive": FakeProvider()}
        self._record()

        self.assertEqual(self.manager._reconcile_remote_ids(), 0)
        self.assertEqual(
            self.manager.sync_metadata["files"][self.key]["remote"],
            {"google_drive": "old"})
        self.assertEqual(self._added(), [])

    def test_id_for_an_unconnected_provider_is_not_trusted(self):
        self.manager.providers = {"google_drive": FakeProvider()}
        self.listing = {"google_drive": {}}
        self._record(remote={"dropbox": "id:abc"})

        self.manager._reconcile_remote_ids()
        # Nothing to reconcile: this run never uploaded to Dropbox, so the
        # entry must not look backed up for Drive either.
        self.assertEqual(self._added(), [self.path])

    def test_other_provider_ids_are_preserved(self):
        self.manager.providers = {"google_drive": FakeProvider()}
        self.listing = {"google_drive": {}}
        self._record(remote={"google_drive": "old", "dropbox": "id:abc"})

        self.manager._reconcile_remote_ids()

        self.assertEqual(
            self.manager.sync_metadata["files"][self.key]["remote"],
            {"dropbox": "id:abc"})

    def test_metadata_is_saved_when_an_id_changes(self):
        self.manager.providers = {"google_drive": FakeProvider()}
        self.listing = {"google_drive": {}}
        self._record()

        self.manager._reconcile_remote_ids()

        saved = sm.SYNC_METADATA_FILE.read_text(encoding="utf-8")
        self.assertIn(self.key.replace("\\", "\\\\"), saved)


class TestSyncReuploadsMissingCopies(_SyncTestBase):

    def test_perform_sync_uploads_files_whose_cloud_copy_vanished(self):
        provider = FakeProvider(upload_result="fresh-id")
        self.manager.providers = {"google_drive": provider}
        self.listing = {"google_drive": {}}
        self._record()

        results = self.manager.perform_sync()

        uploaded = [path for path, _subfolder in provider.upload_calls
                    if path.suffix == ".png"]
        self.assertEqual(uploaded, [self.path])
        self.assertEqual(results["added"], 1)
        self.assertEqual(
            self.manager.sync_metadata["files"][self.key]["remote"],
            {"google_drive": "fresh-id"})

    def test_running_sync_again_uploads_nothing(self):
        provider = FakeProvider(upload_result="fresh-id")
        self.manager.providers = {"google_drive": provider}
        self.listing = {"google_drive": {}}
        self._record()

        self.manager.perform_sync()
        after_first = len(provider.upload_calls)
        # The repaired copy now exists in the folder, so the second pass must
        # see nothing to do instead of uploading it again.
        self.listing = {"google_drive": {("generated", "frog.png"): "fresh-id"}}

        results = self.manager.perform_sync()

        self.assertEqual(len(provider.upload_calls), after_first)
        self.assertEqual(results["added"], 0)
        self.assertEqual(results["modified"], 0)


if __name__ == "__main__":
    unittest.main()
