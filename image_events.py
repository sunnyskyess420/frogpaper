"""Event log for generated images.

Phase 1 of the dropdown improvement plan: every pick, every favourite, every
wallpaper set and every delete is recorded, so list decisions can be made from
evidence instead of guesswork.

Shape of the data (table ``image_events``)
------------------------------------------
``generated`` and ``deleted`` write one row per option field, which keeps the
choice queryable after the image itself is gone.  ``favorite_added``,
``favorite_removed`` and ``wallpaper_set`` write a single row with an empty
field.  That makes one query answer everything::

    SELECT field, value, source,
           SUM(event='generated')       AS uses,
           SUM(event='favorite_added')  AS favorites,
           SUM(event='deleted')         AS deletes,
           SUM(event='wallpaper_set')   AS wallpaper_sets
    FROM image_events
    GROUP BY field, value, source

``tools/option_report.py`` runs exactly that.

Like the rest of the storage layer this degrades quietly: without sqlalchemy,
or without a writable database, every function is a no-op and the app keeps
working.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

#: Option fields that become one row each.
FIELD_KEYS = ("subject", "setting", "style", "lighting", "mood", "atmosphere", "color", "mode")

#: Where an image came from. Kept as plain strings so a future source can be
#: added without a migration.
SOURCE_MANUAL = "manual"
SOURCE_DAILY = "daily_runner"
SOURCE_RANDOM = "random_theme"
SOURCE_STARTUP = "startup_auto"
SOURCES = (SOURCE_MANUAL, SOURCE_DAILY, SOURCE_RANDOM, SOURCE_STARTUP)

EVENT_GENERATED = "generated"
EVENT_DELETED = "deleted"
EVENT_FAVORITE_ADDED = "favorite_added"
EVENT_FAVORITE_REMOVED = "favorite_removed"
EVENT_WALLPAPER_SET = "wallpaper_set"


def _db():
    """Return the database module when it is usable, else None."""
    try:
        import database
    except Exception:  # pragma: no cover - import guard
        return None
    if getattr(database, "DB_AVAILABLE", False) and getattr(database, "Base", None) is not None:
        return database
    return None


def _iso_now() -> str:
    return datetime.now().isoformat()


def normalized_path(image_path) -> str:
    """Key used for every event row.

    ``Path.resolve`` keeps working for a file that has just been deleted, which
    is why delete events can still be tied to their generation events.
    """
    try:
        return str(Path(image_path).resolve())
    except (OSError, RuntimeError, ValueError):
        return str(image_path)


def _params_of(params: dict | None) -> dict:
    if not params:
        return {}
    return params if isinstance(params, dict) else {}


def _write(rows: list[dict]) -> None:
    if not rows:
        return
    db = _db()
    if db is None:
        return
    try:
        from database import ImageEvent

        session = db.get_db_session()
        try:
            session.bulk_insert_mappings(ImageEvent, rows)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    except Exception as exc:  # never let analytics break generation
        logger.debug("image_events write failed: %s", exc)


def _source_for_image(path: str) -> str | None:
    """Source recorded for this image's generation, if any."""
    db = _db()
    if db is None:
        return None
    try:
        from database import ImageEvent

        session = db.get_db_session()
        try:
            row = (session.query(ImageEvent.source)
                   .filter(ImageEvent.image_path == path, ImageEvent.event == EVENT_GENERATED)
                   .order_by(ImageEvent.id.desc())
                   .first())
            return row[0] if row and row[0] else None
        finally:
            session.close()
    except Exception:
        return None


def log_generation(image_path, params: dict | None = None, source: str = SOURCE_MANUAL) -> None:
    """Record that an image was produced with these option picks.

    Re-logging the same path replaces the previous ``generated`` rows, so a
    re-saved parameter blob does not inflate the counts.
    """
    path = normalized_path(image_path)
    values = _params_of(params)
    db = _db()
    if db is not None:
        try:
            from database import ImageEvent

            session = db.get_db_session()
            try:
                session.query(ImageEvent).filter(
                    ImageEvent.image_path == path,
                    ImageEvent.event == EVENT_GENERATED,
                ).delete()
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()
        except Exception as exc:
            logger.debug("image_events cleanup failed: %s", exc)

    stamp = _iso_now()
    rows = []
    for field in FIELD_KEYS:
        value = (values.get(field) or "")
        rows.append({
            "image_path": path,
            "event": EVENT_GENERATED,
            "field": field,
            "value": value.strip() if isinstance(value, str) else str(value),
            "source": source,
            "created_at": stamp,
        })
    _write(rows)


def log_event(image_path, event: str, params: dict | None = None,
              source: str | None = None, per_field: bool = False) -> None:
    """Record a non-generation event.

    ``per_field=True`` writes one row per option field (used for deletes, where
    the parameter row is about to disappear); otherwise a single row with an
    empty field is written.
    """
    path = normalized_path(image_path)
    stamp = _iso_now()
    values = _params_of(params)

    if per_field and not source and not values.get("source"):
        # Attribute the delete to the same source as its generation, so a later
        # report does not count one image under two different sources.
        source = _source_for_image(path)

    if per_field:
        rows = [{
            "image_path": path,
            "event": event,
            "field": field,
            "value": (values.get(field) or "").strip() if isinstance(values.get(field), str) else str(values.get(field) or ""),
            "source": source or values.get("source") or SOURCE_MANUAL,
            "created_at": stamp,
        } for field in FIELD_KEYS]
    else:
        rows = [{
            "image_path": path,
            "event": event,
            "field": "",
            "value": "",
            "source": source or "",
            "created_at": stamp,
        }]
    _write(rows)


def log_delete(image_path, params: dict | None = None) -> None:
    """Keep the evidence when an image is removed.

    Must be called *before* the ``prompt_params`` row is deleted.
    """
    log_event(image_path, EVENT_DELETED, params=params, per_field=True)


def log_favorite(image_path, added: bool) -> None:
    log_event(image_path, EVENT_FAVORITE_ADDED if added else EVENT_FAVORITE_REMOVED)


def log_wallpaper(image_path, source: str = "") -> None:
    log_event(image_path, EVENT_WALLPAPER_SET, source=source or None)


def counts(db_path: Path | str | None = None, since: str | None = None,
           field: str | None = None) -> list[dict]:
    """Per option value: uses, favourites, deletes, wallpaper sets, by source.

    Reads the database directly so it works from a tool or a test without a
    running app.  Favourite and wallpaper events are image-level rows, so they
    are joined back onto the field rows of the same image; deletes are already
    per field.  Images whose only evidence is a delete are merged in, otherwise
    pruning would never see the negative signal.
    """
    try:
        import sqlite3
    except ImportError:  # pragma: no cover
        return []

    from app_data_dir import resolve_app_dir

    target = Path(db_path) if db_path else Path(resolve_app_dir()) / "frogpaper.db"
    if not target.exists():
        return []

    filters: list[str] = []
    params: list = []
    if since:
        filters.append("g.created_at >= ?")
        params.append(since)
    if field:
        filters.append("g.field = ?")
        params.append(field)
    where = (" AND " + " AND ".join(filters)) if filters else ""

    usage_query = f"""
        SELECT g.field AS field, g.value AS value, g.source AS source,
               COUNT(*) AS uses,
               COALESCE(SUM(f.favorites), 0) AS favorites,
               COALESCE(SUM(f.unfavorites), 0) AS unfavorites,
               COALESCE(SUM(d.deletes), 0) AS deletes,
               COALESCE(SUM(f.wallpaper_sets), 0) AS wallpaper_sets
        FROM image_events g
        LEFT JOIN (
            SELECT image_path,
                   SUM(event = 'favorite_added')   AS favorites,
                   SUM(event = 'favorite_removed') AS unfavorites,
                   SUM(event = 'wallpaper_set')    AS wallpaper_sets
            FROM image_events
            WHERE event IN ('favorite_added', 'favorite_removed', 'wallpaper_set')
            GROUP BY image_path
        ) f ON f.image_path = g.image_path
        LEFT JOIN (
            SELECT image_path, field, COUNT(*) AS deletes
            FROM image_events WHERE event = 'deleted'
            GROUP BY image_path, field
        ) d ON d.image_path = g.image_path AND d.field = g.field
        WHERE g.event = 'generated' AND g.field <> ''{where}
        GROUP BY g.field, g.value, g.source
        ORDER BY g.field, uses DESC
    """

    del_filters = []
    del_params: list = []
    if since:
        del_filters.append("created_at >= ?")
        del_params.append(since)
    if field:
        del_filters.append("field = ?")
        del_params.append(field)
    del_where = (" AND " + " AND ".join(del_filters)) if del_filters else ""
    delete_query = f"""
        SELECT field, value, source, COUNT(*) AS deletes
        FROM image_events
        WHERE event = 'deleted' AND field <> ''{del_where}
        GROUP BY field, value, source
    """

    con = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    try:
        con.row_factory = sqlite3.Row
        rows = [dict(row) for row in con.execute(usage_query, params).fetchall()]
        merged = {(r["field"], r["value"], r["source"]): r for r in rows}
        # Delete-only images (pruned before the event log existed, or a
        # generation that was never recorded) are merged by value, not by
        # source, so one image can never be counted under two sources.
        by_value = {(r["field"], r["value"]): r for r in rows}
        for row in con.execute(delete_query, del_params).fetchall():
            key = (row["field"], row["value"], row["source"])
            existing = merged.get(key) or by_value.get((row["field"], row["value"]))
            if existing:
                existing["deletes"] = max(existing.get("deletes") or 0, row["deletes"])
            else:
                merged[key] = {
                    "field": row["field"], "value": row["value"], "source": row["source"],
                    "uses": 0, "favorites": 0, "unfavorites": 0,
                    "deletes": row["deletes"], "wallpaper_sets": 0,
                }
        return list(merged.values())
    except sqlite3.Error:
        return []
    finally:
        con.close()


def summary(db_path: Path | str | None = None) -> dict:
    """Row counts per event, for a quick sanity check."""
    try:
        import sqlite3

        from app_data_dir import resolve_app_dir
    except ImportError:  # pragma: no cover
        return {}
    target = Path(db_path) if db_path else Path(resolve_app_dir()) / "frogpaper.db"
    if not target.exists():
        return {}
    con = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    try:
        return {row[0]: row[1] for row in con.execute(
            "SELECT event, COUNT(*) FROM image_events GROUP BY event").fetchall()}
    except sqlite3.Error:
        return {}
    finally:
        con.close()

