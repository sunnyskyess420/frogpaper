"""cloud_restore.py
----------------
Restore engine for pulling a wallpaper collection back into FrogPaper.

This module is deliberately free of tkinter, SQLite and network imports: it
turns a listing of :class:`RemoteFile` records into a *plan* (a pure function of
the listing and the local disk), then executes that plan with crash-safe
writes. That keeps the whole thing testable headless, with no cloud account.

Phase 2 of CLOUD_RESTORE_PLAN.md. Only :class:`LocalFolderSource` is implemented
here; the cloud providers plug into the same ``RestoreSource`` contract in a
later phase (list_files + fetch), so planning and execution need no changes.

Safety contract
---------------
* Nothing local is deleted, and nothing is overwritten unless the caller passes
  ``overwrite=True`` or ``conflict_policy="overwrite"``.
* Files are written as ``<name>.part`` and only renamed into place after the
  size and SHA-256 checks pass.
* A failed or cancelled run leaves no ``.part`` files behind.
"""

import hashlib
import json
import logging
import os
import shutil
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

# Mirrors set_wallpaper.IMAGE_EXTENSIONS. Duplicated on purpose: importing
# set_wallpaper pulls in ctypes/windll and creates directories as a side effect,
# which this module must not do at import time.
IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".bmp", ".webp"})

# The cloud layout documented in CLOUD_RESTORE_PLAN.md.
SUBFOLDER_NAMES = ("generated", "manual", "favorites", "styled")

DEFAULT_SUBFOLDER = "manual"
CONFLICT_POLICIES = ("keep_both", "skip", "overwrite")
MAX_NAME_LENGTH = 200
_FREE_SPACE_HEADROOM = 1.10
_HASH_CHUNK = 1024 * 256

_RESERVED_WINDOWS_NAMES = frozenset(
    ["CON", "PRN", "AUX", "NUL"]
    + [f"COM{i}" for i in range(1, 10)]
    + [f"LPT{i}" for i in range(1, 10)]
)
_INVALID_NAME_CHARS = frozenset('<>:"/\\|?*')


class RestoreStatus(str, Enum):
    """Outcome class for one planned file."""

    MISSING = "missing"        # not on disk yet -> will be written
    IDENTICAL = "identical"    # already present with matching content -> skip
    CONFLICT = "conflict"      # present but different -> policy decides
    INVALID = "invalid"        # unsafe/unusable name -> never written
    NO_SPACE = "no_space"      # would be written, but disk is too full


class RestoreError(Exception):
    """Base class for restore failures."""


class RestoreVerificationError(RestoreError):
    """A downloaded file did not match the advertised size or hash."""


@dataclass(frozen=True)
class RemoteFile:
    """A single file discovered in a backup source.

    ``file_id`` is the provider identifier; for a local folder it is the
    absolute path. ``sha256`` may be ``None`` for sources (and legacy backups)
    that cannot supply a content hash -- such files are never treated as
    already-restored, only as conflicts.
    """

    provider: str
    file_id: str
    name: str
    subfolder: str = DEFAULT_SUBFOLDER
    size: int = 0
    modified: float = 0.0
    sha256: str = None
    # Cloud providers publish their own digests (Drive: md5, OneDrive: sha1,
    # Dropbox: content_hash). ``sha256`` is kept for local sources and for
    # callers built before this field existed.
    checksum_algo: str = None
    checksum: str = None

    @property
    def rel_path(self):
        sub = self.subfolder or DEFAULT_SUBFOLDER
        return f"wallpapers/{sub}/{self.name}"

    @property
    def digest(self):
        """Return ``(algorithm, value)``, or ``(None, None)`` when unknown.

        Verification and "already restored" detection both use this, so a
        provider that only publishes MD5 still gets content checks instead of
        falling back to size alone.
        """
        if self.checksum and self.checksum_algo:
            return self.checksum_algo, self.checksum
        if self.sha256:
            return "sha256", self.sha256
        return None, None


@dataclass
class RestoreItem:
    """One file in a :class:`RestorePlan`."""

    remote: RemoteFile
    status: RestoreStatus
    target: Path = None
    reason: str = ""
    will_overwrite: bool = False


@dataclass
class RestorePlan:
    """Result of the dry run. Inspecting it must never touch the disk."""

    app_dir: Path
    items: list = field(default_factory=list)
    free_bytes: int = 0
    needed_bytes: int = 0

    def counts(self):
        counts = {status.value: 0 for status in RestoreStatus}
        for item in self.items:
            counts[item.status.value] += 1
        return counts

    def pending(self):
        """Items that would actually write a file."""
        return [
            item for item in self.items
            if item.target is not None
            and item.status in (RestoreStatus.MISSING, RestoreStatus.CONFLICT)
        ]

    def summary(self):
        counts = self.counts()
        return (
            f"{counts['missing']} to restore, {counts['conflict']} conflicts, "
            f"{counts['identical']} already present, {counts['invalid']} invalid, "
            f"{counts['no_space']} blocked by free space"
        )

    def to_dict(self):
        return {
            "app_dir": str(self.app_dir),
            "summary": self.summary(),
            "counts": self.counts(),
            "needed_bytes": self.needed_bytes,
            "free_bytes": self.free_bytes,
            "items": [
                {
                    "rel_path": item.remote.rel_path,
                    "provider": item.remote.provider,
                    "status": item.status.value,
                    "target": str(item.target) if item.target else None,
                    "reason": item.reason,
                    "will_overwrite": item.will_overwrite,
                }
                for item in self.items
            ],
        }


@dataclass
class RestoreResult:
    """What actually happened during :meth:`RestoreExecutor.run`."""

    written: list = field(default_factory=list)
    skipped: list = field(default_factory=list)
    failures: list = field(default_factory=list)
    cancelled: bool = False
    log_path: Path = None

    @property
    def ok(self):
        return not self.failures and not self.cancelled

    def summary(self):
        text = f"{len(self.written)} restored, {len(self.skipped)} skipped"
        if self.failures:
            text += f", {len(self.failures)} failed"
        if self.cancelled:
            text += " (cancelled)"
        return text


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def sha256_file(path, chunk_size=_HASH_CHUNK):
    """Return the SHA-256 hex digest of ``path``."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dropbox_content_hash(path, block_size=4 * 1024 * 1024):
    """Dropbox's ``content_hash``: SHA-256 over the concatenated 4 MiB block
    digests. Files smaller than one block hash as ``sha256(sha256(data))``."""
    overall = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(block_size), b""):
            overall.update(hashlib.sha256(chunk).digest())
    return overall.hexdigest()


_ALGO_DISPLAY = {
    "sha256": "SHA-256",
    "sha1": "SHA-1",
    "md5": "MD5",
    "dropbox": "Dropbox content hash",
}


def compute_digest(path, algo="sha256", chunk_size=_HASH_CHUNK):
    """Compute a digest with the algorithm a backup source advertises."""
    algo = (algo or "sha256").lower()
    if algo == "dropbox":
        return dropbox_content_hash(path)
    if algo not in _ALGO_DISPLAY:
        raise RestoreError(f"unsupported checksum algorithm: {algo}")
    digest = hashlib.new(algo)
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def algorithm_label(algo):
    return _ALGO_DISPLAY.get((algo or "").lower(), (algo or "checksum").upper())


def is_safe_image_name(name):
    """Validate a file name coming from an untrusted backup source.

    Returns ``(ok, reason)``. Rejects path separators, traversal, control
    characters, Windows-reserved device names and over-long names, so a restore
    can never write outside ``wallpapers/<subfolder>/``.
    """
    if not isinstance(name, str) or not name:
        return False, "empty file name"
    if name != Path(name).name:
        return False, "path separators are not allowed"
    if name in (".", "..") or name.startswith("."):
        return False, "hidden or relative file name"
    if len(name) > MAX_NAME_LENGTH:
        return False, f"name longer than {MAX_NAME_LENGTH} characters"
    if any(char in _INVALID_NAME_CHARS or ord(char) < 32 for char in name):
        return False, "invalid character in file name"
    if name != name.rstrip(" ."):
        return False, "name ends with a space or dot"
    suffix = Path(name).suffix.lower()
    if suffix not in IMAGE_EXTENSIONS:
        return False, f"unsupported extension: {suffix or '(none)'}"
    stem = Path(name).stem
    if stem.upper() in _RESERVED_WINDOWS_NAMES:
        return False, "reserved Windows device name"
    return True, ""


def _unlink_quietly(path):
    try:
        os.unlink(path)
    except OSError:
        pass


def _unique_target(target, tag, used_keys):
    """Return a non-colliding path, ``<stem> (<tag>)[ (n)].<suffix>``."""
    stem, suffix = target.stem, target.suffix
    candidate = target.with_name(f"{stem} ({tag}){suffix}")
    counter = 2
    while str(candidate).lower() in used_keys or candidate.exists():
        candidate = target.with_name(f"{stem} ({tag}) ({counter}){suffix}")
        counter += 1
    return candidate


def _same_content(target, remote):
    """True only when we can positively prove the local file matches."""
    algo, value = remote.digest
    try:
        if remote.size and target.stat().st_size != remote.size:
            return False
        if not value:
            return False
        return compute_digest(target, algo) == value
    except (OSError, RestoreError):
        return False


# ---------------------------------------------------------------------------
# sources
# ---------------------------------------------------------------------------

class LocalFolderSource:
    """Restore from any folder on disk.

    Works with a Google Drive / OneDrive / Dropbox desktop-sync folder, an SD
    card or an old backup drive -- no OAuth, no network. This is the escape
    hatch when the app's OAuth client credentials are gone.

    Accepts both the FrogPaper cloud layout (``Generated/``, ``Manual/``,
    ``Favorites/``, ``Styled/``) and a flat folder of images, which is treated
    as ``manual``.
    """

    provider = "local_folder"

    def __init__(self, root):
        self.root = Path(root)

    def list_files(self):
        if not self.root.is_dir():
            raise RestoreError(f"restore folder not found: {self.root}")

        subfolder_map = {}
        for entry in self.root.iterdir():
            if entry.is_dir() and entry.name.lower() in SUBFOLDER_NAMES:
                subfolder_map[entry.name.lower()] = entry

        records = []
        if subfolder_map:
            for subfolder, directory in sorted(subfolder_map.items()):
                records.extend(self._scan(directory, subfolder))
        else:
            records.extend(self._scan(self.root, DEFAULT_SUBFOLDER))
        return records

    def _scan(self, directory, subfolder):
        records = []
        try:
            entries = sorted(directory.iterdir())
        except OSError as exc:
            logger.warning("Could not list %s: %s", directory, exc)
            return records
        for entry in entries:
            if not entry.is_file():
                continue
            if entry.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            try:
                stat = entry.stat()
                digest = sha256_file(entry)
            except OSError as exc:
                logger.warning("Skipping unreadable %s: %s", entry, exc)
                continue
            records.append(
                RemoteFile(
                    provider=self.provider,
                    file_id=str(entry),
                    name=entry.name,
                    subfolder=subfolder,
                    size=stat.st_size,
                    modified=stat.st_mtime,
                    sha256=digest,
                )
            )
        return records

    def fetch(self, remote, dest):
        shutil.copyfile(Path(remote.file_id), dest)


# ---------------------------------------------------------------------------
# planning
# ---------------------------------------------------------------------------

def build_plan(records, app_dir, conflict_policy="keep_both", overwrite=False,
               free_bytes=None):
    """Build a :class:`RestorePlan` without writing anything.

    ``conflict_policy`` is one of ``keep_both`` (default; restored copies get a
    ``(restored YYYY-MM-DD)`` suffix), ``skip`` (leave the local file alone) or
    ``overwrite``. ``overwrite=True`` is equivalent to the overwrite policy and
    exists as a separate switch for the UI checkbox.
    """
    if conflict_policy not in CONFLICT_POLICIES:
        raise ValueError(
            f"unknown conflict policy {conflict_policy!r}; "
            f"expected one of {CONFLICT_POLICIES}"
        )

    app_dir = Path(app_dir)
    wallpapers = app_dir / "wallpapers"
    tag = f"restored {datetime.now().strftime('%Y-%m-%d')}"
    allow_overwrite = overwrite or conflict_policy == "overwrite"

    used_keys = set()
    items = []

    for remote in sorted(records, key=lambda r: (r.subfolder, r.name)):
        ok, reason = is_safe_image_name(remote.name)
        if not ok:
            items.append(RestoreItem(remote, RestoreStatus.INVALID, None, reason))
            continue

        subfolder = remote.subfolder if remote.subfolder in SUBFOLDER_NAMES \
            else DEFAULT_SUBFOLDER
        target = wallpapers / subfolder / remote.name
        key = str(target).lower()

        if key in used_keys:
            # A second record claims a name already taken earlier in this plan.
            target = _unique_target(target, tag, used_keys)
            used_keys.add(str(target).lower())
            items.append(RestoreItem(
                remote, RestoreStatus.CONFLICT, target,
                "duplicate name in backup", will_overwrite=False,
            ))
            continue

        used_keys.add(key)

        if not target.exists():
            items.append(RestoreItem(remote, RestoreStatus.MISSING, target))
            continue

        if _same_content(target, remote):
            items.append(RestoreItem(remote, RestoreStatus.IDENTICAL, target))
            continue

        if allow_overwrite:
            items.append(RestoreItem(
                remote, RestoreStatus.CONFLICT, target,
                "local file will be replaced", will_overwrite=True,
            ))
        elif conflict_policy == "skip":
            items.append(RestoreItem(
                remote, RestoreStatus.CONFLICT, None,
                "local file differs; conflict policy is 'skip'",
            ))
        else:
            target = _unique_target(target, tag, used_keys)
            used_keys.add(str(target).lower())
            items.append(RestoreItem(
                remote, RestoreStatus.CONFLICT, target,
                "local file differs; kept both",
            ))

    writers = [
        item for item in items
        if item.target is not None
        and item.status in (RestoreStatus.MISSING, RestoreStatus.CONFLICT)
    ]
    needed = sum(item.remote.size for item in writers)

    if free_bytes is None:
        try:
            free_bytes = shutil.disk_usage(str(app_dir)).free
        except OSError:
            free_bytes = 0

    if needed and free_bytes < int(needed * _FREE_SPACE_HEADROOM):
        for item in writers:
            item.status = RestoreStatus.NO_SPACE
            item.reason = "not enough free disk space"

    return RestorePlan(
        app_dir=app_dir,
        items=items,
        free_bytes=free_bytes,
        needed_bytes=needed,
    )


# ---------------------------------------------------------------------------
# execution
# ---------------------------------------------------------------------------

class RestoreExecutor:
    """Execute a :class:`RestorePlan` with verified, atomic writes."""

    def __init__(self, source, plan, log_dir=None):
        self.source = source
        self.plan = plan
        self.log_dir = Path(log_dir) if log_dir else Path(plan.app_dir)

    def run(self, progress=None, cancel=None, write_log=True):
        """Download/copy every pending item.

        ``progress(index, total, item)`` is called after each item.
        ``cancel`` is a ``threading.Event``; when set the run stops before the
        next file, reports ``cancelled`` and leaves no partial files.
        """
        result = RestoreResult()
        pending = self.plan.pending()
        total = len(pending)
        # Everything the plan decided not to write (already present, invalid,
        # blocked by free space, skipped by policy).
        pending_ids = {id(item) for item in pending}
        result.skipped = [
            item for item in self.plan.items if id(item) not in pending_ids
        ]

        try:
            for index, item in enumerate(pending, 1):
                if cancel is not None and cancel.is_set():
                    result.cancelled = True
                    break
                try:
                    self._write_item(item, result)
                except Exception as exc:  # one bad file must not abort the run
                    logger.warning("Restore failed for %s: %s",
                                   item.remote.rel_path, exc)
                    result.failures.append((item, str(exc)))
                if progress is not None:
                    progress(index, total, item)
            if cancel is not None and cancel.is_set():
                result.cancelled = True
        finally:
            self._sweep_partials()

        if write_log:
            result.log_path = self._write_log(result)
        return result

    def _write_item(self, item, result):
        target = item.target
        target.parent.mkdir(parents=True, exist_ok=True)

        if target.exists() and not item.will_overwrite:
            # A file appeared after planning. Never clobber it.
            target = _unique_target(
                target, f"restored {datetime.now().strftime('%Y-%m-%d')}", set(),
            )
            item.target = target

        partial = target.with_name(target.name + ".part")
        logger.info("Restoring %s -> %s", item.remote.rel_path, target)
        try:
            self.source.fetch(item.remote, partial)
            self._verify(item.remote, partial)
            os.replace(partial, target)
        except BaseException:
            _unlink_quietly(partial)
            raise
        result.written.append(target)

    @staticmethod
    def _verify(remote, partial):
        try:
            size = partial.stat().st_size
        except OSError as exc:
            raise RestoreVerificationError(f"missing download: {exc}") from exc
        if remote.size and size != remote.size:
            raise RestoreVerificationError(
                f"size mismatch: expected {remote.size}, got {size}"
            )
        algo, value = remote.digest
        if value and compute_digest(partial, algo) != value:
            raise RestoreVerificationError(
                f"{algorithm_label(algo)} mismatch")

    def _sweep_partials(self):
        """Remove stray ``.part`` files this plan could have created."""
        for item in self.plan.items:
            if item.target is None:
                continue
            _unlink_quietly(item.target.with_name(item.target.name + ".part"))

    def _write_log(self, result):
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = self.log_dir / f"restore_log_{stamp}.json"
            payload = {
                "created": datetime.now().isoformat(timespec="seconds"),
                "summary": result.summary(),
                "cancelled": result.cancelled,
                "plan": self.plan.summary(),
                "written": [str(p) for p in result.written],
                "failures": [
                    {"rel_path": item.remote.rel_path, "error": error}
                    for item, error in result.failures
                ],
            }
            tmp = path.with_name(path.name + ".tmp")
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
            os.replace(tmp, path)
            return path
        except OSError as exc:
            logger.warning("Could not write restore log: %s", exc)
            return None


def restore_from_folder(source_dir, app_dir, conflict_policy="keep_both",
                        overwrite=False, progress=None, cancel=None):
    """Convenience one-shot: scan a folder, plan it, execute it."""
    source = LocalFolderSource(source_dir)
    plan = build_plan(
        source.list_files(), app_dir,
        conflict_policy=conflict_policy, overwrite=overwrite,
    )
    executor = RestoreExecutor(source, plan)
    return plan, executor.run(progress=progress, cancel=cancel)


def make_cancel_event():
    """Small helper so callers do not need to import threading."""
    return threading.Event()
