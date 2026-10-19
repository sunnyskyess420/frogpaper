"""Tests for recording remote ids and deleting remote copies of deleted files.

No network: providers are fakes. The module's BASE_DIR and metadata path are
redirected to a temp directory so nothing touches the developer's real app dir.
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sync_manager as sm


class FakeProvider:
    authenticated = True

    def __init__(self, size=None, upload_result="remote-id", reason=None):
        self.size = size
        self.upload_result = upload_result
        self.last_upload_reason = reason
        self.delete_calls = []
        self.upload_calls = []

    def upload_file(self, file_path, subfolder=""):
        self.upload_calls.append((Path(file_path), subfolder))
        return self.upload_result

    def get_file_size(self, file_ref):
        return self.size

    def delete_file(self, file_ref):
        self.delete_calls.append(file_ref)
        return True


class TestRemoteDeletion(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

        self._saved_base = sm.BASE_DIR
        self._saved_meta = sm.SYNC_METADATA_FILE
        sm.BASE_DIR = self.root
        sm.SYNC_METADATA_FILE = self.root / "sync_metadata.json"
        self.addCleanup(self._restore_paths)

        self.manager = sm.SyncManager(app=None)
        self.rel = Path("wallpapers") / "generated" / "gone.png"
        self.path = self.root / self.rel
        self.key = str(self.rel)

    def _restore_paths(self):
        sm.BASE_DIR = self._saved_base
        sm.SYNC_METADATA_FILE = self._saved_meta

    def _record(self, **extra):
        self.manager.sync_metadata["files"][self.key] = {
            "hash": "h", "modified": "2026-10-18T00:00:00",
            "size": 5, "remote": {"google_drive": "g-1"}, **extra,
        }

    def test_upload_records_every_remote_id(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_bytes(b"12345")
        drive = FakeProvider(upload_result="g-1")
        dropbox = FakeProvider(upload_result="id:abc")
        self.manager.providers = {"google_drive": drive, "dropbox": dropbox}

        uploaded = self.manager._upload_file(self.path)
        self.manager._update_single_file_metadata(self.path, uploaded)

        entry = self.manager.sync_metadata["files"][self.key]
        self.assertEqual(entry["remote"],
                         {"google_drive": "g-1", "dropbox": "id:abc"})
        self.assertEqual(entry["size"], 5)

    def test_upload_returns_empty_dict_when_all_fail(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_bytes(b"12345")
        self.manager.providers = {"google_drive": FakeProvider(upload_result=None)}
        self.assertEqual(self.manager._upload_file(self.path), {})

    def test_delete_removes_remote_copy_when_size_matches(self):
        provider = FakeProvider(size=5)
        self.manager.providers = {"google_drive": provider}
        self._record()

        self.manager._delete_remote_file(self.path)

        self.assertEqual(provider.delete_calls, ["g-1"])

    def test_delete_is_skipped_when_remote_changed(self):
        provider = FakeProvider(size=999)
        self.manager.providers = {"google_drive": provider}
        self._record()

        self.manager._delete_remote_file(self.path)

        self.assertEqual(provider.delete_calls, [])

    def test_delete_is_skipped_without_recorded_ids(self):
        provider = FakeProvider(size=5)
        self.manager.providers = {"google_drive": provider}
        self.manager.sync_metadata["files"][self.key] = {
            "hash": "h", "size": 5,
        }

        self.manager._delete_remote_file(self.path)

        self.assertEqual(provider.delete_calls, [])

    def test_delete_skips_unauthenticated_provider(self):
        provider = FakeProvider(size=5)
        provider.authenticated = False
        self.manager.providers = {"google_drive": provider}
        self._record()

        self.manager._delete_remote_file(self.path)

        self.assertEqual(provider.delete_calls, [])

    def test_delete_ignores_paths_outside_the_app_dir(self):
        provider = FakeProvider(size=5)
        self.manager.providers = {"google_drive": provider}
        outside = Path(tempfile.gettempdir()) / "somewhere-else.png"

        self.manager._delete_remote_file(outside)  # must not raise

        self.assertEqual(provider.delete_calls, [])

    def test_metadata_update_merges_remote_ids_per_provider(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_bytes(b"12345")
        self._record(remote={"google_drive": "g-1", "dropbox": "old-id"})

        self.manager._update_single_file_metadata(
            self.path, {"google_drive": "g-2"})

        entry = self.manager.sync_metadata["files"][self.key]
        self.assertEqual(entry["remote"],
                         {"google_drive": "g-2", "dropbox": "old-id"})


class TestUploadFailureAccounting(unittest.TestCase):
    """A failed upload must never be reported as a synced change.

    The modified-files loop used to increment ``modified`` regardless of what
    ``_upload_file`` returned, so a cloud copy that refused the write still
    looked backed up. Real Drive accounts hit exactly this for files created by
    a different OAuth client (403 appNotAuthorizedToFile).
    """

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

        self._saved_base = sm.BASE_DIR
        self._saved_meta = sm.SYNC_METADATA_FILE
        sm.BASE_DIR = self.root
        sm.SYNC_METADATA_FILE = self.root / "sync_metadata.json"
        self.addCleanup(self._restore_paths)

        self.path = self.root / "wallpapers" / "generated" / "frog.png"
        self.path.parent.mkdir(parents=True)
        self.path.write_bytes(b"12345")

    def _restore_paths(self):
        sm.BASE_DIR = self._saved_base
        sm.SYNC_METADATA_FILE = self._saved_meta

    def _manager(self, provider):
        manager = sm.SyncManager(app=None)
        manager.providers = {"google_drive": provider}
        manager._detect_changes = lambda: ([], [self.path], [])
        manager._update_sync_metadata = lambda: None
        manager._save_sync_metadata = lambda: None
        manager._upload_backup_manifest = lambda results: None
        manager._is_favorite = lambda path: False
        return manager

    def test_failed_modification_counts_as_error_not_change(self):
        results = self._manager(
            FakeProvider(upload_result=None, reason="error")).perform_sync()

        self.assertEqual(results["modified"], 0)
        self.assertEqual(results["errors"], 1)
        self.assertEqual(results["unwritable"], 0)

    def test_permission_refusal_gets_its_own_tally(self):
        results = self._manager(
            FakeProvider(upload_result=None, reason="no_access")).perform_sync()

        self.assertEqual(results["modified"], 0)
        self.assertEqual(results["errors"], 1)
        self.assertEqual(results["unwritable"], 1)

    def test_successful_upload_still_counts_as_modified(self):
        results = self._manager(FakeProvider()).perform_sync()

        self.assertEqual(results["modified"], 1)
        self.assertEqual(results["errors"], 0)
        self.assertEqual(results["unwritable"], 0)


if __name__ == "__main__":
    unittest.main()
