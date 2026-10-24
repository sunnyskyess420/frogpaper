"""Locate FrogPaper's user-data directory, and migrate older layouts into it.

Why this module exists
----------------------
Frozen builds used to keep every writable file beside the EXE: ``config.json``
(with the user's API keys), ``wallpapers/``, ``logs/`` and ``frogpaper.db``.
That data vanished whenever the program folder was rebuilt, replaced or
uninstalled — a 1.7.6 rebuild deleted a developer's entire gallery and keys.

Frozen builds now use ``%LOCALAPPDATA%\\FrogPaper``.  On the first frozen
launch, anything an older build left beside the EXE is **copied** (never
moved) into the new location, skipping files that already exist there, so a
partial or repeated migration cannot lose or revert data.  The old folder is
left untouched as a fallback.

Running from source is unchanged: data stays in the project folder.
"""

import logging
import os
import shutil
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Written into the new data dir once a migration pass completes cleanly.
MIGRATION_MARKER = ".data_dir_migrated"

# User-data folders copied from the old "beside the EXE" location.
_MIGRATED_DIRS = (
    "wallpapers",
    "logs",
    "templates",
    "recipes",
    "favorites",
    "favorites_migrated",
)

# Database files (SQLite sidecars included) that hold tags and favourites.
_MIGRATED_DB_FILES = (
    "frogpaper.db",
    "frogpaper.db-wal",
    "frogpaper.db-shm",
    ".db_migrated",
)

# Bundled starter files that must never be copied over the user's own data.
_SKIP_JSON = {"config.template.json"}

_migration_checked = False


def legacy_data_dir() -> Path:
    """Where pre-1.7.6 frozen builds kept user data: beside the EXE."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def per_user_data_dir() -> Path:
    """Per-user writable data directory that survives reinstall/upgrade."""
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        return Path(base) / "FrogPaper"
    # No per-user folder known (non-Windows) — keep the old layout.
    return legacy_data_dir()


def resolve_app_dir() -> Path:
    """Return the directory for user-writable data, migrating old data once."""
    if getattr(sys, "frozen", False):
        target = per_user_data_dir()
        try:
            target.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            # Never fail startup over this: fall back to the old layout.
            logger.warning("Could not create %s (%s) - using the EXE folder", target, e)
            return legacy_data_dir()
        migrate_legacy_data(target)
        return target
    return Path(__file__).parent


def _copy_file_if_missing(src: Path, dst: Path) -> int:
    """Copy *src* to *dst* only when *dst* does not exist yet."""
    if not src.is_file() or dst.exists():
        return 0
    shutil.copy2(src, dst)
    return 1


def _copy_tree_if_missing(src_root: Path, dst_root: Path) -> int:
    """Recursively copy files from *src_root* that are missing in *dst_root*."""
    copied = 0
    for src in src_root.rglob("*"):
        try:
            if not src.is_file():
                continue
            dst = dst_root / src.relative_to(src_root)
            if dst.exists():
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied += 1
        except OSError as e:
            logger.warning("Could not migrate %s: %s", src, e)
    return copied


def migrate_legacy_data(target: Path) -> int:
    """Copy data left beside the EXE into *target*, once. Returns file count.

    Never overwrites an existing file in *target* and never deletes anything
    from the legacy folder.  The marker is written only after a clean pass, so
    a failed run simply retries on the next launch.
    """
    global _migration_checked
    if _migration_checked:
        return 0
    _migration_checked = True

    try:
        legacy = legacy_data_dir()
        if legacy == target or (target / MIGRATION_MARKER).exists():
            return 0
        target.mkdir(parents=True, exist_ok=True)

        copied = 0
        for name in _MIGRATED_DB_FILES:
            copied += _copy_file_if_missing(legacy / name, target / name)
        for src in legacy.glob("*.json"):
            if src.name not in _SKIP_JSON:
                copied += _copy_file_if_missing(src, target / src.name)
        for dirname in _MIGRATED_DIRS:
            src_dir = legacy / dirname
            if src_dir.is_dir():
                copied += _copy_tree_if_missing(src_dir, target / dirname)

        (target / MIGRATION_MARKER).write_text(str(legacy), encoding="utf-8")
        if copied:
            logger.info("Migrated %d user-data file(s) from %s to %s",
                        copied, legacy, target)
        return copied
    except Exception as e:  # noqa: BLE001 - startup must never crash here
        logger.warning("Could not migrate user data beside the EXE: %s", e)
        return 0