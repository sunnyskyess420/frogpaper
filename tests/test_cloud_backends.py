"""Backend-level tests for cloud_catalog's three providers.

These exercise the *real* backend code -- field mapping, pagination, folder
resolution, download plumbing -- against fake SDK objects and a patched
``requests``, so the parts that would otherwise only run against a live account
are at least logically verified.
"""

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cloud_catalog as catalog


# ---------------------------------------------------------------------------
# Google Drive doubles
# ---------------------------------------------------------------------------

class _Request:
    def __init__(self, payload):
        self._payload = payload

    def execute(self):
        return self._payload


class _FakeDriveFiles:
    def __init__(self, pages):
        self._pages = list(pages)
        self.calls = []

    def list(self, **params):
        self.calls.append(params)
        return _Request(self._pages.pop(0))


class _FakeDriveProvider:
    authenticated = True

    def __init__(self, pages, download_ok=True):
        self.files_api = _FakeDriveFiles(pages)
        self.service = types.SimpleNamespace(files=lambda: self.files_api)
        self.download_ok = download_ok
        self.downloaded = []

    def download_file(self, file_ref, dest):
        self.downloaded.append(file_ref)
        Path(dest).write_bytes(b"payload")
        return self.download_ok


class TestGoogleBackend(unittest.TestCase):

    def test_resolve_root_finds_the_folder(self):
        provider = _FakeDriveProvider([{
            "files": [{"id": "root-1", "name": "FrogPaper"}],
        }])
        backend = catalog.GoogleDriveBackend(provider)
        self.assertEqual(backend.resolve_root(), "root-1")
        self.assertIn("FrogPaper", provider.files_api.calls[0]["q"])

    def test_resolve_root_returns_none_when_absent(self):
        backend = catalog.GoogleDriveBackend(_FakeDriveProvider([{"files": []}]))
        self.assertIsNone(backend.resolve_root())

    def test_list_children_pages_and_maps_metadata(self):
        provider = _FakeDriveProvider([
            {"files": [{
                "id": "f1", "name": "a.png",
                "mimeType": "image/png", "size": "12",
                "modifiedTime": "2026-10-18T10:00:00Z",
                "md5Checksum": "abc",
            }], "nextPageToken": "p2"},
            {"files": [{
                "id": "dir", "name": "Generated",
                "mimeType": catalog.GOOGLE_FOLDER_MIME,
            }]},
        ])
        backend = catalog.GoogleDriveBackend(provider)
        items = backend.list_children("root-1")

        self.assertEqual(len(items), 2)
        file_item, folder_item = items
        self.assertEqual(file_item["kind"], "file")
        self.assertEqual(file_item["size"], 12)
        self.assertEqual(file_item["checksum_algo"], "md5")
        self.assertEqual(file_item["checksum"], "abc")
        self.assertGreater(file_item["modified"], 0)
        self.assertEqual(folder_item["kind"], "folder")
        self.assertEqual(provider.files_api.calls[1]["pageToken"], "p2")

    def test_download_raises_when_provider_reports_failure(self):
        provider = _FakeDriveProvider([], download_ok=False)
        backend = catalog.GoogleDriveBackend(provider)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(catalog.CloudCatalogError):
                backend.download("f1", Path(tmp) / "x.png")

    def test_unauthenticated_provider_is_rejected(self):
        provider = _FakeDriveProvider([])
        provider.authenticated = False
        with self.assertRaises(catalog.CloudCatalogError):
            catalog.GoogleDriveBackend(provider).resolve_root()


# ---------------------------------------------------------------------------
# OneDrive doubles
# ---------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, status_code=200, payload=None, content=b""):
        self.status_code = status_code
        self._payload = payload or {}
        self._content = content
        self.text = str(payload)
        self.closed = False

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size=1024):
        yield self._content

    def close(self):
        self.closed = True


class _FakeOneDriveProvider:
    authenticated = True
    client = "token"

    def __init__(self):
        self.downloaded = []


class TestOneDriveBackend(unittest.TestCase):

    def test_resolve_root_picks_the_folder(self):
        payload = {"value": [
            {"id": "other", "name": "Docs", "folder": {}},
            {"id": "root-9", "name": "FrogPaper", "folder": {}},
        ]}
        with mock.patch("requests.get",
                        return_value=_FakeResponse(payload=payload)):
            backend = catalog.OneDriveBackend(_FakeOneDriveProvider())
            self.assertEqual(backend.resolve_root(), "root-9")

    def test_list_children_follows_next_link(self):
        first = {"value": [{
            "id": "f1", "name": "a.png", "size": 10,
            "file": {"hashes": {"sha1Hash": "deadbeef"}},
            "lastModifiedDateTime": "2026-10-18T10:00:00Z",
        }], "@odata.nextLink": "https://graph/next"}
        second = {"value": [{"id": "d1", "name": "Generated", "folder": {}}]}

        responses = [_FakeResponse(payload=first), _FakeResponse(payload=second)]

        def fake_get(url, **kwargs):
            return responses.pop(0)

        with mock.patch("requests.get", side_effect=fake_get):
            items = catalog.OneDriveBackend(_FakeOneDriveProvider()).list_children("root-9")

        self.assertEqual([item["kind"] for item in items], ["file", "folder"])
        self.assertEqual(items[0]["checksum_algo"], "sha1")
        self.assertEqual(items[0]["checksum"], "deadbeef")
        self.assertEqual(items[0]["size"], 10)

    def test_download_streams_to_disk(self):
        provider = _FakeOneDriveProvider()
        with mock.patch("requests.get",
                        return_value=_FakeResponse(content=b"image-bytes")):
            with tempfile.TemporaryDirectory() as tmp:
                dest = Path(tmp) / "a.png"
                catalog.OneDriveBackend(provider).download("f1", dest)
                self.assertEqual(dest.read_bytes(), b"image-bytes")

    def test_download_raises_on_http_error(self):
        with mock.patch("requests.get",
                        return_value=_FakeResponse(status_code=500)):
            with tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(RuntimeError):
                    catalog.OneDriveBackend(_FakeOneDriveProvider()).download(
                        "f1", Path(tmp) / "a.png")


# ---------------------------------------------------------------------------
# Dropbox doubles
# ---------------------------------------------------------------------------

class _FakeFileMetadata:
    def __init__(self, item_id, name, size, content_hash, path_lower=None):
        self.id = item_id
        self.name = name
        self.size = size
        self.content_hash = content_hash
        self.path_lower = path_lower or f"/frogpaper/{name}"
        import datetime
        self.server_modified = datetime.datetime(2026, 10, 18, 10, 0, 0)


class _FakeFolderMetadata:
    def __init__(self, name, path_lower):
        self.name = name
        self.path_lower = path_lower


class _Page:
    def __init__(self, entries, has_more=False, cursor=""):
        self.entries = entries
        self.has_more = has_more
        self.cursor = cursor


class _FakeDropboxClient:
    def __init__(self, pages, metadata_error=False):
        self._pages = list(pages)
        self.metadata_error = metadata_error
        self.deleted = []

    def files_list_folder(self, path):
        return self._pages.pop(0)

    def files_list_folder_continue(self, cursor):
        return self._pages.pop(0)

    def files_get_metadata(self, ref):
        if self.metadata_error:
            raise RuntimeError("not found")
        return _FakeFolderMetadata("FrogPaper", "/frogpaper")

    def files_download_to_file(self, dest, ref):
        Path(dest).write_bytes(b"dropbox-bytes")


class _FakeDropboxProvider:
    authenticated = True

    def __init__(self, pages, metadata_error=False):
        self.client = _FakeDropboxClient(pages, metadata_error)


class _TestDropboxBackend(catalog.DropboxBackend):
    """Uses the fake metadata class so the dropbox SDK is not required."""

    def _file_metadata_type(self):
        return _FakeFileMetadata


class TestDropboxBackend(unittest.TestCase):

    def test_resolve_root_none_when_missing(self):
        provider = _FakeDropboxProvider([], metadata_error=True)
        self.assertIsNone(_TestDropboxBackend(provider).resolve_root())

    def test_list_children_paginates(self):
        page1 = _Page([_FakeFileMetadata("id:1", "a.png", 5, "hash-a")],
                      has_more=True, cursor="c1")
        page2 = _Page([_FakeFolderMetadata("Generated", "/frogpaper/generated")])
        backend = _TestDropboxBackend(_FakeDropboxProvider([page1, page2]))

        items = backend.list_children("/FrogPaper")

        self.assertEqual([item["kind"] for item in items], ["file", "folder"])
        self.assertEqual(items[0]["checksum_algo"], "dropbox")
        self.assertEqual(items[0]["id"], "/frogpaper/a.png")  # path, not id
        self.assertEqual(items[0]["size"], 5)
        self.assertGreater(items[0]["modified"], 0)

    def test_download_writes_file(self):
        backend = _TestDropboxBackend(_FakeDropboxProvider([]))
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "a.png"
            backend.download("/frogpaper/a.png", dest)
            self.assertEqual(dest.read_bytes(), b"dropbox-bytes")

    def test_download_failure_is_wrapped(self):
        class Failing(_FakeDropboxClient):
            def files_download_to_file(self, dest, ref):
                raise RuntimeError("network")

        provider = _FakeDropboxProvider([])
        provider.client = Failing([])
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(catalog.CloudCatalogError):
                _TestDropboxBackend(provider).download("/x/a.png", Path(tmp) / "a.png")


if __name__ == "__main__":
    unittest.main()
