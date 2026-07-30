"""
database.py
-----------
SQLite backend for FrogPaper using SQLAlchemy.

Replaces scattered JSON file storage with a single database:
  - gallery_tags.json  -> image_tags table
  - sessions.json      -> sessions table
  - presets.json       -> presets table
  - prompts_history.json -> history table
  - prompt_library.json -> prompt_library table
  - user_thesaurus.json -> user_thesaurus table
  - keyword_expansion.json -> expansion_log table
  - config.json (last_*) -> app_settings table

On first run, existing JSON files are migrated into SQLite.
After migration, JSON files are renamed to *.json.bak (not deleted).

Thread safety: SQLAlchemy sessions are NOT thread-safe across threads.
Each thread should call get_db_session() to get its own session.
The db_lock protects the global engine during initialization.

Graceful fallback: If sqlalchemy is not installed, this module loads
successfully but all operations are no-ops.  Callers should check
``DB_AVAILABLE`` before using any DB functions.
"""

import json
import logging
import os
import shutil
import threading
from datetime import datetime
from pathlib import Path

from utils import get_app_dir

logger = logging.getLogger(__name__)

# ── Try importing sqlalchemy ──────────────────────────────────────────────
try:
    from sqlalchemy import (
        Column, Integer, Text, Float, Boolean, DateTime, ForeignKey,
        create_engine, text, func,
    )
    from sqlalchemy.orm import (
        declarative_base, sessionmaker, Session as ORMSession, scoped_session,
    )
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    logger.warning(
        "sqlalchemy is not installed. "
        "The app will fall back to JSON file storage. "
        "Install it with: pip install sqlalchemy"
    )

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR = get_app_dir()
DB_PATH = BASE_DIR / "frogpaper.db"
MIGRATION_MARKER = BASE_DIR / ".db_migrated"

# Module-level lock for DB init (not for every query — SQLite WAL handles concurrency)
_db_init_lock = threading.Lock()
_engine = None
_SessionFactory = None

# ── ORM Base (only defined when sqlalchemy is available) ────────────────────
Base = None
if DB_AVAILABLE:
    Base = declarative_base()


# ═══════════════════════════════════════════════════════════════════════════
#  TABLE DEFINITIONS (only when sqlalchemy is available)
# ═══════════════════════════════════════════════════════════════════════════

if Base is not None:

    class ImageTag(Base):
        """One tag assigned to one image. image_path is the primary key segment."""
        __tablename__ = "image_tags"

        id = Column(Integer, primary_key=True, autoincrement=True)
        image_path = Column(Text, nullable=False, index=True)
        tag = Column(Text, nullable=False, index=True)
        tagged_at = Column(Text, nullable=True)  # ISO timestamp

    class PromptParam(Base):
        """Stored prompt parameters for a generated image."""
        __tablename__ = "prompt_params"

        id = Column(Integer, primary_key=True, autoincrement=True)
        image_path = Column(Text, nullable=False, unique=True, index=True)
        params_json = Column(Text, nullable=True)  # JSON blob of all prompt params
        updated_at = Column(Text, nullable=True)  # ISO timestamp

    class Session(Base):
        """Named session capturing full Prompt Builder state."""
        __tablename__ = "sessions"

        id = Column(Integer, primary_key=True, autoincrement=True)
        name = Column(Text, nullable=False, unique=True, index=True)
        subject = Column(Text, nullable=True)
        style = Column(Text, nullable=True)
        lighting = Column(Text, nullable=True)
        mood = Column(Text, nullable=True)
        color = Column(Text, nullable=True)
        atmosphere = Column(Text, nullable=True)
        mode = Column(Text, nullable=True)
        subject_lock = Column(Boolean, default=True)
        negative_prompt = Column(Text, nullable=True)
        neg_preset_selections = Column(Text, nullable=True)  # JSON blob of preset selections
        neg_custom_terms = Column(Text, nullable=True)  # Custom negative terms
        pb_view = Column(Text, nullable=True)
        selected_template = Column(Text, nullable=True)
        template_variable_values = Column(Text, nullable=True)

    class Preset(Base):
        """Saved preset bundle (inputs + themes + prompts)."""
        __tablename__ = "presets"

        id = Column(Text, primary_key=True)  # e.g. "preset_a1b2c3d4"
        name = Column(Text, nullable=False)
        created_at = Column(Text, nullable=True)
        inputs_json = Column(Text, nullable=True)
        themes_json = Column(Text, nullable=True)
        prompts_json = Column(Text, nullable=True)
        favorite_prompts_json = Column(Text, nullable=True)

    class HistoryEntry(Base):
        """One prompt generation history entry."""
        __tablename__ = "history"

        id = Column(Integer, primary_key=True, autoincrement=True)
        timestamp = Column(Text, nullable=True, index=True)
        saved_at = Column(Text, nullable=True)
        subject = Column(Text, nullable=True)
        style = Column(Text, nullable=True)
        lighting = Column(Text, nullable=True)
        mood = Column(Text, nullable=True)
        prompt = Column(Text, nullable=True)
        image_path = Column(Text, nullable=True)
        theme_sentence = Column(Text, nullable=True)

    class PromptLibraryEntry(Base):
        """Saved prompt in the user's library."""
        __tablename__ = "prompt_library"

        id = Column(Text, primary_key=True)
        name = Column(Text, nullable=False)
        subject = Column(Text, nullable=True)
        style = Column(Text, nullable=True)
        lighting = Column(Text, nullable=True)
        mood = Column(Text, nullable=True)
        prompt = Column(Text, nullable=True)
        theme_sentence = Column(Text, nullable=True)
        created_at = Column(Text, nullable=True)
        usage_count = Column(Integer, default=0)
        tags_json = Column(Text, nullable=True)

    class UserThesaurus(Base):
        """User-defined keyword synonym mapping."""
        __tablename__ = "user_thesaurus"

        id = Column(Integer, primary_key=True, autoincrement=True)
        from_word = Column(Text, nullable=False, unique=True)
        to_word = Column(Text, nullable=False)

    class ExpansionLogEntry(Base):
        """Logged keyword expansion for analytics/debugging."""
        __tablename__ = "expansion_log"

        id = Column(Integer, primary_key=True, autoincrement=True)
        original = Column(Text, nullable=True)
        expanded = Column(Text, nullable=True)
        method = Column(Text, nullable=True)
        confidence = Column(Float, default=0.0)
        timestamp = Column(Text, nullable=True)

    class AppSetting(Base):
        """Generic key-value store for app settings."""
        __tablename__ = "app_settings"

        key = Column(Text, primary_key=True)
        value = Column(Text, nullable=True)


# ═══════════════════════════════════════════════════════════════════════════
#  DATABASE INITIALIZATION
# ═══════════════════════════════════════════════════════════════════════════

def init_db():
    """Initialize the database. Creates tables and migrates existing JSON data."""
    global _engine, _SessionFactory

    if not DB_AVAILABLE:
        logger.info("sqlalchemy not available, skipping database init.")
        return

    with _db_init_lock:
        if _engine is not None:
            return  # Already initialized

        db_url = f"sqlite:///{DB_PATH}"
        _engine = create_engine(db_url, echo=False,
                                connect_args={"check_same_thread": False})

        with _engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA busy_timeout=5000"))
            conn.commit()

        Base.metadata.create_all(_engine)

        _SessionFactory = scoped_session(sessionmaker(bind=_engine))

        if not MIGRATION_MARKER.exists():
            _migrate_json_to_db()
            MIGRATION_MARKER.touch()
            logger.info("Database migration from JSON completed.")
        else:
            # Handle schema updates for existing databases
            _add_missing_columns()

    logger.info("Database initialized at %s", DB_PATH)


def get_db_session() -> ORMSession:
    """Get a new database session. Each call returns a session from the pool."""
    if not DB_AVAILABLE:
        raise RuntimeError("sqlalchemy is not installed; cannot open DB session")
    if _SessionFactory is None:
        init_db()
    return _SessionFactory()


def shutdown_db():
    """Close database connections on app shutdown."""
    global _engine, _SessionFactory
    if _SessionFactory is not None:
        _SessionFactory.remove()
        _SessionFactory = None
    if _engine is not None:
        _engine.dispose()
        _engine = None
    logger.info("Database shut down.")


# ═══════════════════════════════════════════════════════════════════════════
#  JSON → SQLITE MIGRATION
# ═══════════════════════════════════════════════════════════════════════════

def _migrate_json_to_db():
    """Import data from existing JSON files into SQLite tables."""
    session = get_db_session()
    try:
        _migrate_gallery_tags(session)
        _migrate_sessions(session)
        _migrate_presets(session)
        _migrate_history(session)
        _migrate_prompt_library(session)
        _migrate_user_thesaurus(session)
        _migrate_expansion_log(session)
        _migrate_app_settings(session)
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error("JSON migration failed: %s", e)
        raise
    finally:
        session.close()

    _backup_json_files()


def _add_missing_columns():
    """Add new columns to existing database tables for schema updates."""
    try:
        # Check if sessions table has the new columns using raw SQL
        with _engine.connect() as conn:
            result = conn.execute(text("PRAGMA table_info(sessions)")).fetchall()
            existing_columns = [row[1] for row in result]
            
            if 'neg_preset_selections' not in existing_columns:
                conn.execute(text("ALTER TABLE sessions ADD COLUMN neg_preset_selections TEXT"))
                conn.commit()
                logger.info("Added neg_preset_selections column to sessions table")
            
            if 'neg_custom_terms' not in existing_columns:
                conn.execute(text("ALTER TABLE sessions ADD COLUMN neg_custom_terms TEXT"))
                conn.commit()
                logger.info("Added neg_custom_terms column to sessions table")
        
    except Exception as e:
        logger.warning("Failed to add missing columns: %s", e)


def _safe_load_json(path: Path) -> dict | list | None:
    """Safely load a JSON file, returning None on any error."""
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Could not load %s for migration: %s", path.name, e)
        return None


def _migrate_gallery_tags(session: ORMSession):
    """Migrate gallery_tags.json -> image_tags + prompt_params tables."""
    data = _safe_load_json(BASE_DIR / "gallery_tags.json")
    if not data or not isinstance(data, dict):
        return

    tags_data = data.get("tags", {})
    now = datetime.now().isoformat()

    if session.query(ImageTag).first() is not None:
        logger.info("image_tags table already has data, skipping gallery_tags.json migration.")
        return

    for image_path_str, entry in tags_data.items():
        tags = entry.get("tags", [])
        tagged_at = entry.get("tagged_at", now)
        for tag in tags:
            session.add(ImageTag(image_path=image_path_str, tag=tag, tagged_at=tagged_at))

        prompt_params = entry.get("prompt_params")
        if prompt_params:
            session.add(PromptParam(
                image_path=image_path_str,
                params_json=json.dumps(prompt_params, ensure_ascii=False),
                updated_at=tagged_at,
            ))

    logger.info("Migrated %d images from gallery_tags.json", len(tags_data))


def _migrate_sessions(session: ORMSession):
    """Migrate sessions.json -> sessions table."""
    data = _safe_load_json(BASE_DIR / "sessions.json")
    if not data or not isinstance(data, dict):
        return

    if session.query(Session).first() is not None:
        logger.info("sessions table already has data, skipping.")
        return

    for name, state in data.items():
        session.add(Session(
            name=name,
            subject=state.get("subject", ""),
            style=state.get("style", ""),
            lighting=state.get("lighting", ""),
            mood=state.get("mood", ""),
            color=state.get("color", ""),
            atmosphere=state.get("atmosphere", ""),
            mode=state.get("mode", ""),
            subject_lock=state.get("subject_lock", True),
            negative_prompt=state.get("negative_prompt", ""),
            neg_preset_selections=json.dumps(state.get("neg_preset_selections", {}), ensure_ascii=False) if state.get("neg_preset_selections") else None,
            neg_custom_terms=state.get("neg_custom_terms", ""),
            pb_view=state.get("pb_view", ""),
            selected_template=state.get("selected_template", ""),
            template_variable_values=json.dumps(
                state.get("template_variable_values", {}), ensure_ascii=False
            ) if state.get("template_variable_values") else None,
        ))

    logger.info("Migrated %d sessions from sessions.json", len(data))


def _migrate_presets(session: ORMSession):
    """Migrate presets.json -> presets table."""
    data = _safe_load_json(BASE_DIR / "presets.json")
    if not data or not isinstance(data, list):
        return

    if session.query(Preset).first() is not None:
        logger.info("presets table already has data, skipping.")
        return

    for p in data:
        session.add(Preset(
            id=p.get("id", f"preset_{os.urandom(4).hex()}"),
            name=p.get("name", ""),
            created_at=p.get("created_at", ""),
            inputs_json=json.dumps(p.get("inputs", {}), ensure_ascii=False),
            themes_json=json.dumps(p.get("themes", []), ensure_ascii=False),
            prompts_json=json.dumps(p.get("prompts", []), ensure_ascii=False),
            favorite_prompts_json=json.dumps(p.get("favorite_prompts", []), ensure_ascii=False),
        ))

    logger.info("Migrated %d presets from presets.json", len(data))


def _migrate_history(session: ORMSession):
    """Migrate prompts_history.json -> history table."""
    data = _safe_load_json(BASE_DIR / "logs" / "prompts_history.json")
    if not data or not isinstance(data, list):
        return

    if session.query(HistoryEntry).first() is not None:
        logger.info("history table already has data, skipping.")
        return

    for entry in data:
        session.add(HistoryEntry(
            timestamp=entry.get("timestamp") or entry.get("saved_at", ""),
            saved_at=entry.get("saved_at", ""),
            subject=entry.get("subject", ""),
            style=entry.get("style", ""),
            lighting=entry.get("lighting", ""),
            mood=entry.get("mood", ""),
            prompt=entry.get("prompt", ""),
            image_path=entry.get("image_path", ""),
            theme_sentence=entry.get("theme_sentence", ""),
        ))

    logger.info("Migrated %d history entries from prompts_history.json", len(data))


def _migrate_prompt_library(session: ORMSession):
    """Migrate prompt_library.json -> prompt_library table."""
    data = _safe_load_json(BASE_DIR / "prompt_library.json")
    if not data or not isinstance(data, dict):
        return

    if session.query(PromptLibraryEntry).first() is not None:
        logger.info("prompt_library table already has data, skipping.")
        return

    for entry in data.get("library", []):
        session.add(PromptLibraryEntry(
            id=entry.get("id", f"lib_{os.urandom(4).hex()}"),
            name=entry.get("name", ""),
            subject=entry.get("subject", ""),
            style=entry.get("style", ""),
            lighting=entry.get("lighting", ""),
            mood=entry.get("mood", ""),
            prompt=entry.get("prompt", ""),
            theme_sentence=entry.get("theme_sentence", ""),
            created_at=entry.get("created_at", ""),
            usage_count=entry.get("usage_count", 0),
            tags_json=json.dumps(entry.get("tags", []), ensure_ascii=False),
        ))

    count = len(data.get("library", []))
    logger.info("Migrated %d prompt library entries", count)


def _migrate_user_thesaurus(session: ORMSession):
    """Migrate user_thesaurus.json -> user_thesaurus table."""
    data = _safe_load_json(BASE_DIR / "user_thesaurus.json")
    if not data or not isinstance(data, dict):
        return

    if session.query(UserThesaurus).first() is not None:
        logger.info("user_thesaurus table already has data, skipping.")
        return

    for from_word, to_word in data.items():
        session.add(UserThesaurus(from_word=from_word, to_word=to_word))

    logger.info("Migrated %d thesaurus entries", len(data))


def _migrate_expansion_log(session: ORMSession):
    """Migrate keyword_expansion.json -> expansion_log table."""
    data = _safe_load_json(BASE_DIR / "logs" / "keyword_expansion.json")
    if not data or not isinstance(data, list):
        return

    if session.query(ExpansionLogEntry).first() is not None:
        logger.info("expansion_log table already has data, skipping.")
        return

    for entry in data:
        session.add(ExpansionLogEntry(
            original=entry.get("original", ""),
            expanded=entry.get("expanded", ""),
            method=entry.get("method", ""),
            confidence=entry.get("confidence", 0.0),
            timestamp=entry.get("timestamp", ""),
        ))

    logger.info("Migrated %d expansion log entries", len(data))


def _migrate_app_settings(session: ORMSession):
    """Migrate last_* settings from config.json -> app_settings table."""
    data = _safe_load_json(BASE_DIR / "config.json")
    if not data or not isinstance(data, dict):
        return

    if session.query(AppSetting).first() is not None:
        logger.info("app_settings table already has data, skipping.")
        return

    migrated_keys = []
    for key, value in data.items():
        if key.startswith("last_"):
            session.add(AppSetting(key=key, value=str(value) if value is not None else None))
            migrated_keys.append(key)

    logger.info("Migrated %d app settings from config.json", len(migrated_keys))


def _backup_json_files():
    """Rename migrated JSON files to *.json.bak to preserve them as backups."""
    json_files = [
        BASE_DIR / "gallery_tags.json",
        BASE_DIR / "sessions.json",
        BASE_DIR / "presets.json",
        BASE_DIR / "logs" / "prompts_history.json",
        BASE_DIR / "prompt_library.json",
        BASE_DIR / "user_thesaurus.json",
        BASE_DIR / "logs" / "keyword_expansion.json",
    ]

    for json_file in json_files:
        if json_file.exists():
            backup = json_file.with_suffix(".json.bak")
            if not backup.exists():
                try:
                    shutil.copy2(str(json_file), str(backup))
                    logger.info("Backed up %s -> %s", json_file.name, backup.name)
                except Exception as e:
                    logger.warning("Could not back up %s: %s", json_file.name, e)
