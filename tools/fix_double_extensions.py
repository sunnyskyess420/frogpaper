"""Repair files that were saved as name.png.png.

The generator used to append ".png" to a filename that already ended in it, so
images generated with an empty Style box landed as e.g.
    frog_20260617_194111.png.png

Renaming the files alone would break the gallery: tags, stored prompt
parameters, history rows, image events and the favourites log all key off the
full path. This tool moves the file and rewrites every stored path that points
at it.

    python tools/fix_double_extensions.py            # dry run, prints the plan
    python tools/fix_double_extensions.py --apply    # rename + rewrite

Close FrogPaper first: it caches tags in memory and keeps the database open.
A timestamped copy of the database and favourites log is written next to the
originals before anything is changed.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app_paths import (  # noqa: E402
    BASE_DIR, FAVORITES_LOG, MANUAL_DIR, STYLED_DIR, FAVORITES_DIR,
)

GENERATED_DIR = BASE_DIR / "wallpapers" / "generated"
DEFAULT_DB = BASE_DIR / "frogpaper.db"
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
#: Columns that store an image path.
PATH_COLUMNS = {
    "image_tags": "image_path",
    "prompt_params": "image_path",
    "image_events": "image_path",
    "history": "image_path",
}
FAVORITE_KEYS = ("original_image_path", "image_path", "copied_image_path")


def scan_directories(roots) -> list[tuple[Path, Path]]:
    """Files whose name ends in a doubled image extension: (old, new)."""
    pairs: list[tuple[Path, Path]] = []
    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            lower = path.name.lower()
            for ext in IMAGE_EXTS:
                if lower.endswith(ext + ext):
                    pairs.append((path, path.with_name(path.name[: -len(ext)])))
                    break
    return sorted(pairs, key=lambda pair: str(pair[0]))


def _resolved(path: Path) -> Path:
    try:
        return Path(path).resolve()
    except (OSError, RuntimeError):
        return Path(path)


def rewrite_stored_path(stored: str, rename_map: dict[Path, Path]) -> str | None:
    """New stored value for *stored*, or None when it does not point at a renamed file."""
    if not stored:
        return None
    original = Path(stored)
    new_path = rename_map.get(_resolved(original))
    if new_path is None:
        return None
    if original.is_absolute():
        return str(new_path)
    try:
        return str(new_path.relative_to(Path.cwd()))
    except ValueError:
        return str(new_path)


def backup_database(db_path: Path) -> Path:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    backup = db_path.with_name(f"{db_path.name}.bak-{stamp}")
    shutil.copy2(db_path, backup)
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(db_path) + suffix)
        if sidecar.exists():
            shutil.copy2(sidecar, backup.with_name(backup.name + suffix))
    return backup


def backup_json(path: Path) -> Path | None:
    if not path.exists():
        return None
    stamp = time.strftime("%Y%m%d_%H%M%S")
    backup = path.with_name(f"{path.name}.bak-{stamp}")
    shutil.copy2(path, backup)
    return backup


def rename_files(pairs, apply: bool) -> tuple[list[tuple[Path, Path]], list[str]]:
    """Rename each file unless the target name is taken."""
    done: list[tuple[Path, Path]] = []
    skipped: list[str] = []
    for old, new in pairs:
        if new.exists() and new != old:
            skipped.append(f"{old.name} -> target already exists ({new.name})")
            continue
        if apply:
            old.rename(new)
        done.append((old, new))
    return done, skipped


def rewrite_database(db_path: Path, rename_map: dict[Path, Path], apply: bool) -> dict:
    """Update every stored path in the database. Returns per-table counts."""
    counts: dict[str, int] = {}
    if not db_path.exists():
        return counts
    con = sqlite3.connect(str(db_path), timeout=5)
    try:
        tables = {row[0] for row in con.execute(
            "select name from sqlite_master where type='table'").fetchall()}
        for table, column in PATH_COLUMNS.items():
            if table not in tables:
                continue
            changed = 0
            rows = con.execute(f"select id, {column} from {table}").fetchall()
            for row_id, stored in rows:
                new_value = rewrite_stored_path(stored, rename_map)
                if new_value is None or new_value == stored:
                    continue
                changed += 1
                if apply:
                    con.execute(f"update {table} set {column} = ? where id = ?",
                                (new_value, row_id))
            counts[table] = changed
        if apply:
            con.commit()
    except sqlite3.OperationalError as exc:
        con.rollback()
        raise SystemExit(f"database is locked ({exc}) - close FrogPaper and run again")
    finally:
        con.close()
    return counts


def rewrite_favorites(json_path: Path, rename_map: dict[Path, Path], apply: bool) -> int:
    if not json_path.exists():
        return 0
    try:
        entries = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    if not isinstance(entries, list):
        return 0
    changed = 0
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        for key in FAVORITE_KEYS:
            stored = entry.get(key)
            if not isinstance(stored, str):
                continue
            new_value = rewrite_stored_path(stored, rename_map)
            if new_value and new_value != stored:
                entry[key] = new_value
                changed += 1
    if apply and changed:
        json_path.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")
    return changed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="actually rename and rewrite")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--favorites", type=Path, default=FAVORITES_LOG)
    args = parser.parse_args(argv)

    roots = [MANUAL_DIR, GENERATED_DIR, STYLED_DIR, FAVORITES_DIR]
    pairs = scan_directories(roots)
    print(f"double-extension files found: {len(pairs)}")
    for old, new in pairs[:10]:
        print(f"  {old.name}  ->  {new.name}")
    if len(pairs) > 10:
        print(f"  ... {len(pairs) - 10} more")
    if not pairs:
        return 0

    done, skipped = rename_files(pairs, apply=False)
    for note in skipped:
        print(f"  skipped: {note}")

    rename_map = {_resolved(old): new for old, new in done}

    if args.apply:
        db_backup = backup_database(args.db) if args.db.exists() else None
        fav_backup = backup_json(args.favorites)
        if db_backup:
            print(f"database backup: {db_backup.name}")
        if fav_backup:
            print(f"favourites backup: {fav_backup.name}")

    done, skipped = rename_files(pairs, apply=args.apply)
    counts = rewrite_database(args.db, rename_map, apply=args.apply)
    fav_changed = rewrite_favorites(args.favorites, rename_map, apply=args.apply)

    verb = "renamed" if args.apply else "would rename"
    print(f"\n{verb}: {len(done)} file(s); skipped {len(skipped)}")
    total = sum(counts.values())
    label = "updated" if args.apply else "would update"
    print(f"{label} database rows: {total}  " + ", ".join(
        f"{table} {count}" for table, count in counts.items()))
    print(f"{label} favourites entries: {fav_changed}")

    if not args.apply:
        print("\nnothing changed - re-run with --apply to do it")
        print("note: also restart FrogPaper afterwards so its caches reload.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
