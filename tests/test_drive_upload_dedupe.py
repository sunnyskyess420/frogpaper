"""The duplicate-upload failsafe for Google Drive.

Re-running a sync must never create a second copy of a wallpaper. Two things
prevent it:

* ``SyncManager._detect_changes`` skips files whose hash is already recorded,
  and
* ``GoogleDriveProvider.upload_file`` looks for a file with the same name in
  the target subfolder and skips (same size) or updates in place (size
  changed) instead of creating another one.

The second half is what protects a re-upload after the metadata index was lost
or replaced, so it is what these tests cover. No network and no Google client
library required: ``MediaFileUpload`` is stubbed when the real one is absent.
"""

import sys
import tempfile
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:  # the real client, when the environment has it installed
    from googleapiclient.http import MediaFileUpload  # noqa: F401
except ImportError:  # keep the test runnable on a lean install
    googleapiclient = types.ModuleType("googleapiclient")
    http = types.ModuleType("googleapiclient.http")

    class _MediaFileUpload:
        def __init__(self, path, **kwargs):
            self.path = path

    http.MediaFileUpload = _MediaFileUpload
    googleapiclient.http = http
    sys.modules.setdefault("googleapiclient", googleapiclient)
    sys.modules.setdefault("googleapiclient.http", http)

import cloud_providers as cp


class _Request:
    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error

    def execute(self):
        if self.error is not None:
            raise self.error
        return self.payload


class FakeDriveFiles:
    """Just enough of ``service.files()`` for the upload path."""

    def __init__(self, existing=()):
        self.existing = list(existing)
        self.created = []
        self.updated = []

    def list(self, q="", fields=None, spaces=None, pageSize=None, **kwargs):
        if "mimeType='application/vnd.google-apps.folder'" in q:
            return _Request({"files": [{"id": "subfolder-id", "name": "Generated"}]})
        return _Request({"files": list(self.existing)})

    def create(self, body=None, media_body=None, fields=None):
        self.created.append(body)
        return _Request({"id": "created-id"})

    def update(self, fileId=None, media_body=None, fields=None):
        self.updated.append(fileId)
        return _Request({"id": fileId})


class FakeDriveService:
    def __init__(self, files):
        self._files = files

    def files(self):
        return self._files


class TestGoogleUploadDoesNotDuplicate(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "frog.png"
        self.path.write_bytes(b"x" * 2048)

        self.provider = cp.GoogleDriveProvider()
        self.provider.authenticated = True
        self.provider._folder_id_cache = "root-id"  # skip the root lookup
        self.files = FakeDriveFiles()
        self.provider.service = FakeDriveService(self.files)

    def _existing(self, size):
        return {"id": "existing-id", "name": self.path.name, "size": str(size)}

    def test_same_name_and_size_skips_the_upload(self):
        self.files.existing = [self._existing(2048)]

        result = self.provider.upload_file(self.path, subfolder="Generated")

        self.assertEqual(result, "existing-id")
        self.assertEqual(self.files.created, [])
        self.assertEqual(self.files.updated, [])

    def test_changed_size_updates_in_place(self):
        self.files.existing = [self._existing(1024)]

        result = self.provider.upload_file(self.path, subfolder="Generated")

        self.assertEqual(result, "existing-id")
        self.assertEqual(self.files.updated, ["existing-id"])
        self.assertEqual(self.files.created, [])

    def test_absent_file_is_created_once(self):
        result = self.provider.upload_file(self.path, subfolder="Generated")

        self.assertEqual(result, "created-id")
        self.assertEqual(len(self.files.created), 1)
        self.assertEqual(self.files.created[0]["parents"], ["subfolder-id"])

    def test_lookup_is_scoped_to_the_target_subfolder(self):
        """A same-named file elsewhere in the drive must not be mistaken for it."""
        calls = []
        original = self.files.list

        def recording_list(q="", **kwargs):
            calls.append(q)
            return original(q=q, **kwargs)

        self.files.list = recording_list
        self.provider.upload_file(self.path, subfolder="Generated")

        name_queries = [q for q in calls if self.path.name in q]
        self.assertTrue(name_queries, calls)
        self.assertIn("'subfolder-id' in parents", name_queries[0])


if __name__ == "__main__":
    unittest.main()
