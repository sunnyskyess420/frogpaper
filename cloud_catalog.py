"""cloud_catalog.py
-----------------
Read-only view of the ``FrogPaper/`` backup tree in a cloud account, shaped so
``cloud_restore`` can plan and execute a restore without knowing which provider
supplied the files.

Split of responsibility:

* **Backends** (one per provider) do three narrow things: resolve the
  ``FrogPaper`` folder, list one folder's children following pagination, and
  download one file. The provider-specific API calls live there and nowhere
  else.
* **CloudRestoreSource** walks the tree, normalizes every item into a
  ``RemoteFile`` (native checksum included) and exposes the same
  ``list_files()`` / ``fetch()`` contract as ``LocalFolderSource``.

Restore is strictly read-only with respect to the cloud: nothing here creates,
moves or deletes remote files.
"""

import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path

import backup_manifest
import cloud_restore as cr
from cloud_restore import RemoteFile, SUBFOLDER_NAMES

logger = logging.getLogger(__name__)

GOOGLE_FOLDER_MIME = "application/vnd.google-apps.folder"
GRAPH_BASE = "https://graph.microsoft.com/v1.0"
DROPBOX_ROOT = "/FrogPaper"

# (connect timeout, read timeout) for the raw HTTP backends.
_TIMEOUT = (10, 300)


class CloudCatalogError(cr.RestoreError):
    """The backup folder could not be read from the cloud."""


# ---------------------------------------------------------------------------
# normalization
# ---------------------------------------------------------------------------

def _parse_iso(value):
    """Best-effort ISO-8601 -> POSIX timestamp; unparseable becomes 0.0."""
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _item(kind, item_id, name, size=0, modified=0.0, algo=None, value=None):
    return {
        "kind": kind,
        "id": str(item_id),
        "name": name or "",
        "size": int(size or 0),
        "modified": float(modified or 0.0),
        "checksum_algo": algo,
        "checksum": value,
    }


class CloudRestoreSource:
    """A backup tree served by a :class:`CloudBackend`."""

    def __init__(self, backend):
        self.backend = backend
        self.root = getattr(backend, "name", "cloud")

    # -- listing --------------------------------------------------------

    def list_files(self):
        """Return every image under ``FrogPaper/`` as a :class:`RemoteFile`.

        Recognized subfolders map to ``generated`` / ``manual`` /
        ``favorites`` / ``styled``. Images sitting directly in ``FrogPaper/``
        (older uploads) map to ``manual``. Unknown subfolders and non-image
        files are ignored.
        """
        root_ref = self.backend.resolve_root()
        if not root_ref:
            raise CloudCatalogError(
                "No FrogPaper backup folder was found in this cloud account."
            )

        records = []
        for child in self.backend.list_children(root_ref):
            if child.get("kind") == "folder":
                subfolder = child["name"].lower()
                if subfolder not in SUBFOLDER_NAMES:
                    logger.info("Skipping unrecognized backup folder: %s",
                                child["name"])
                    continue
                for item in self.backend.list_children(child["id"]):
                    if item.get("kind") != "file":
                        continue
                    record = self._to_remote(item, subfolder)
                    if record is not None:
                        records.append(record)
            elif child.get("kind") == "file":
                record = self._to_remote(child, "manual")
                if record is not None:
                    records.append(record)

        logger.info("Cloud catalog: %d images under %s", len(records), self.root)
        return records

    def _to_remote(self, item, subfolder):
        name = item.get("name", "")
        if Path(name).suffix.lower() not in cr.IMAGE_EXTENSIONS:
            return None
        return RemoteFile(
            provider=self.root,
            file_id=item["id"],
            name=name,
            subfolder=subfolder,
            size=item.get("size", 0),
            modified=item.get("modified", 0.0),
            checksum_algo=item.get("checksum_algo"),
            checksum=item.get("checksum"),
        )

    def fetch_manifest(self):
        """Download and parse ``backup-manifest.json`` from the backup root.

        Returns ``None`` when the backup predates the manifest, when the file
        is unreadable, or when the provider errors -- a missing manifest means
        an images-only restore, never a failed one.
        """
        root_ref = self.backend.resolve_root()
        if not root_ref:
            return None

        manifest_id = None
        try:
            for child in self.backend.list_children(root_ref):
                if (child.get("kind") == "file"
                        and child.get("name", "").lower()
                        == backup_manifest.MANIFEST_NAME):
                    manifest_id = child["id"]
                    break
        except CloudCatalogError as exc:
            logger.warning("Could not look for a manifest: %s", exc)
            return None

        if manifest_id is None:
            return None

        handle, temp_path = tempfile.mkstemp(suffix="-manifest.json")
        os.close(handle)
        try:
            self.backend.download(manifest_id, Path(temp_path))
            return backup_manifest.load_manifest(temp_path)
        except Exception as exc:
            logger.warning("Could not read the cloud manifest: %s", exc)
            return None
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass

    # -- download -------------------------------------------------------

    def fetch(self, remote, dest):
        """Download ``remote`` into ``dest`` (the executor supplies a .part)."""
        self.backend.download(remote.file_id, Path(dest))


# ---------------------------------------------------------------------------
# Google Drive
# ---------------------------------------------------------------------------

def _google_item(item):
    is_folder = item.get("mimeType") == GOOGLE_FOLDER_MIME
    md5 = item.get("md5Checksum")
    return _item(
        "folder" if is_folder else "file",
        item.get("id", ""),
        item.get("name", ""),
        size=item.get("size", 0),
        modified=_parse_iso(item.get("modifiedTime")),
        algo=None if is_folder or not md5 else "md5",
        value=None if is_folder else md5,
    )


class GoogleDriveBackend:
    """Drive backend over the ``googleapiclient`` service the app already has."""

    name = "google_drive"

    def __init__(self, provider):
        self.provider = provider

    def _service(self):
        service = getattr(self.provider, "service", None)
        if not getattr(self.provider, "authenticated", False) or service is None:
            raise CloudCatalogError("Google Drive is not connected.")
        return service

    def resolve_root(self):
        service = self._service()
        response = service.files().list(
            q="name='FrogPaper' and mimeType='application/vnd.google-apps.folder' "
              "and trashed=false",
            fields="files(id, name)",
            spaces="drive",
        ).execute()
        folders = response.get("files", [])
        return folders[0]["id"] if folders else None

    def list_children(self, folder_ref):
        service = self._service()
        items = []
        page_token = None
        while True:
            params = {
                "q": f"'{folder_ref}' in parents and trashed=false",
                "fields": ("nextPageToken, files(id, name, mimeType, size, "
                           "modifiedTime, md5Checksum)"),
                "pageSize": 1000,
            }
            if page_token:
                params["pageToken"] = page_token
            response = service.files().list(**params).execute()
            items.extend(_google_item(entry)
                         for entry in response.get("files", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                return items

    def download(self, file_ref, dest):
        if not self.provider.download_file(file_ref, dest):
            raise CloudCatalogError(f"Google Drive download failed: {file_ref}")


# ---------------------------------------------------------------------------
# OneDrive
# ---------------------------------------------------------------------------

def _graph_item(item):
    is_folder = "folder" in item
    hashes = (item.get("file") or {}).get("hashes") or {}
    value = hashes.get("sha1Hash")
    return _item(
        "folder" if is_folder else "file",
        item.get("id", ""),
        item.get("name", ""),
        size=item.get("size", 0),
        modified=_parse_iso(item.get("lastModifiedDateTime")),
        algo=None if is_folder or not value else "sha1",
        value=None if is_folder else value,
    )


class OneDriveBackend:
    """Graph backend over the bearer token the app already holds.

    ``http`` may be supplied to inject an HTTP client; it defaults to the
    ``requests`` module. The seam exists so the backend can be tested without
    requiring ``requests`` (it is absent from the lean CI test install).
    """

    name = "onedrive"

    def __init__(self, provider, http=None):
        self.provider = provider
        self._http = http

    def _http_client(self):
        if self._http is not None:
            return self._http
        import requests

        return requests

    def _headers(self):
        token = getattr(self.provider, "client", None)
        if not getattr(self.provider, "authenticated", False) or not token:
            raise CloudCatalogError("OneDrive is not connected.")
        return {"Authorization": f"Bearer {token}"}

    def _get_json(self, url):
        response = self._http_client().get(
            url, headers=self._headers(), timeout=_TIMEOUT)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def resolve_root(self):
        data = self._get_json(
            f"{GRAPH_BASE}/me/drive/root/children"
            "?$select=id,name,folder&$top=200") or {}
        for item in data.get("value", []):
            if item.get("name", "").lower() == "frogpaper" and "folder" in item:
                return item["id"]
        return None

    def list_children(self, folder_ref):
        url = (f"{GRAPH_BASE}/me/drive/items/{folder_ref}/children"
               "?$top=200&$select=id,name,size,file,folder,lastModifiedDateTime")
        items = []
        while url:
            data = self._get_json(url)
            if data is None:
                break
            items.extend(_graph_item(entry) for entry in data.get("value", []))
            url = data.get("@odata.nextLink")
        return items

    def download(self, file_ref, dest):
        url = f"{GRAPH_BASE}/me/drive/items/{file_ref}/content"
        response = self._http_client().get(
            url, headers=self._headers(), stream=True, timeout=_TIMEOUT)
        try:
            response.raise_for_status()
            with open(dest, "wb") as handle:
                for chunk in response.iter_content(chunk_size=256 * 1024):
                    if chunk:
                        handle.write(chunk)
        finally:
            response.close()


# ---------------------------------------------------------------------------
# Dropbox
# ---------------------------------------------------------------------------

class DropboxBackend:
    """Dropbox backend over the existing SDK client."""

    name = "dropbox"

    def __init__(self, provider):
        self.provider = provider

    def _client(self):
        client = getattr(self.provider, "client", None)
        if not getattr(self.provider, "authenticated", False) or client is None:
            raise CloudCatalogError("Dropbox is not connected.")
        return client

    def resolve_root(self):
        client = self._client()
        try:
            client.files_get_metadata(DROPBOX_ROOT)
        except Exception as exc:  # not-found is the normal "no backup" case
            logger.info("No Dropbox backup folder (%s): %s", DROPBOX_ROOT, exc)
            return None
        return DROPBOX_ROOT

    def _file_metadata_type(self):
        import dropbox

        return dropbox.files.FileMetadata

    def list_children(self, folder_ref):
        client = self._client()
        file_type = self._file_metadata_type()
        entries = []
        try:
            page = client.files_list_folder(folder_ref)
            entries.extend(page.entries)
            while page.has_more:
                page = client.files_list_folder_continue(page.cursor)
                entries.extend(page.entries)
        except Exception as exc:
            raise CloudCatalogError(
                f"Dropbox listing failed for {folder_ref}: {exc}") from exc

        items = []
        for entry in entries:
            if isinstance(entry, file_type):
                # files_download_to_file() takes a path, not the "id:..." id,
                # so the path is what we must carry in file_id.
                items.append(_item(
                    "file", entry.path_lower, entry.name,
                    size=entry.size,
                    modified=entry.server_modified.timestamp()
                    if entry.server_modified else 0.0,
                    algo="dropbox" if entry.content_hash else None,
                    value=entry.content_hash,
                ))
            elif getattr(entry, "name", None):
                items.append(_item("folder", entry.path_lower, entry.name))
        return items

    def download(self, file_ref, dest):
        client = self._client()
        try:
            client.files_download_to_file(str(dest), file_ref)
        except Exception as exc:
            raise CloudCatalogError(
                f"Dropbox download failed for {file_ref}: {exc}") from exc


# ---------------------------------------------------------------------------
# multi-provider merge
# ---------------------------------------------------------------------------

class CloudRestoreSet:
    """Treat several connected providers as one restore source.

    The same collection is often backed up to more than one provider. Records
    that share subfolder, name and checksum are merged, so re-running a restore
    never downloads the same bytes twice; genuinely different files are kept
    and the planner resolves them as normal conflicts.
    """

    def __init__(self, sources):
        self.sources = list(sources)
        self._by_provider = {
            getattr(source, "root", ""): source for source in self.sources
        }

    @property
    def label(self):
        names = sorted(name for name in self._by_provider if name)
        return ", ".join(names) if names else "cloud backup"

    def list_files(self):
        if not self.sources:
            raise CloudCatalogError("No cloud accounts are connected.")

        merged = []
        seen = set()
        errors = []
        for source in self.sources:
            try:
                records = source.list_files()
            except CloudCatalogError as exc:
                logger.warning("Skipping %s: %s", source.root, exc)
                errors.append(str(exc))
                continue
            for record in records:
                algo, value = record.digest
                key = (record.subfolder, record.name.lower(), algo, value)
                if value and key in seen:
                    continue
                seen.add(key)
                merged.append(record)

        if not merged and errors:
            raise CloudCatalogError("; ".join(errors))
        return merged

    def fetch_manifest(self):
        """Return the richest manifest any connected account provides."""
        best = None
        for source in self.sources:
            manifest = source.fetch_manifest()
            if not manifest:
                continue
            if best is None or (len(manifest.get("images") or [])
                                > len(best.get("images") or [])):
                best = manifest
        return best

    def fetch(self, remote, dest):
        source = self._by_provider.get(remote.provider)
        if source is None:
            raise CloudCatalogError(
                f"No connected account can supply {remote.rel_path}")
        source.fetch(remote, dest)


# ---------------------------------------------------------------------------
# factory
# ---------------------------------------------------------------------------

_BACKENDS = {
    "google_drive": GoogleDriveBackend,
    "onedrive": OneDriveBackend,
    "dropbox": DropboxBackend,
}


def make_cloud_source(provider_name, provider):
    """Wrap an authenticated provider in a restore source."""
    try:
        backend_class = _BACKENDS[provider_name]
    except KeyError:
        raise CloudCatalogError(f"Unknown cloud provider: {provider_name}")
    return CloudRestoreSource(backend_class(provider))


def make_cloud_sources(providers):
    """Build one merged source from ``{provider_name: provider}``."""
    sources = []
    for provider_name, provider in (providers or {}).items():
        try:
            sources.append(make_cloud_source(provider_name, provider))
        except CloudCatalogError as exc:
            logger.warning("Cannot restore from %s: %s", provider_name, exc)
    return CloudRestoreSet(sources)
