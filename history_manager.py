"""
History Manager for FrogPaper

Provides history cleanup, pruning policies, backup, and export functionality.
Now backed by SQLite (history table) via database.py.
"""

import json
import csv
import logging
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import shutil

from utils import get_app_dir

logger = logging.getLogger(__name__)

BASE_DIR = get_app_dir()
LOGS_DIR = BASE_DIR / "logs"
BACKUP_DIR = LOGS_DIR / "history_backups"
EXPORT_DIR = LOGS_DIR / "history_exports"
BACKUP_DIR.mkdir(exist_ok=True)
EXPORT_DIR.mkdir(exist_ok=True)

# Lazy DB import
_db = None

def _get_db():
    global _db
    if _db is None:
        try:
            import database
            if not database.DB_AVAILABLE:
                return None
            _db = database
            if _db._SessionFactory is None:
                _db.init_db()
        except ImportError:
            return None
    return _db


class HistoryManager:
    """Manages prompt history with cleanup and export capabilities."""

    def __init__(self):
        self.history_data = []
        self._load_history()

    def _load_history(self):
        """Load history from DB, falling back to JSON if DB is unavailable."""
        try:
            db = _get_db()
            if db is not None:
                from database import HistoryEntry
                session = db.get_db_session()
                try:
                    rows = session.query(HistoryEntry).order_by(HistoryEntry.id.desc()).all()
                    self.history_data = [
                        {
                            "timestamp": row.timestamp or row.saved_at or "",
                            "saved_at": row.saved_at or "",
                            "subject": row.subject or "",
                            "style": row.style or "",
                            "lighting": row.lighting or "",
                            "mood": row.mood or "",
                            "prompt": row.prompt or "",
                            "image_path": row.image_path or "",
                            "theme_sentence": row.theme_sentence or "",
                        }
                        for row in rows
                    ]
                finally:
                    session.close()
            else:
                # JSON fallback
                history_file = LOGS_DIR / "prompts_history.json"
                if history_file.exists():
                    with open(history_file, "r", encoding="utf-8") as f:
                        self.history_data = json.load(f)
                else:
                    self.history_data = []
        except Exception as e:
            logger.error("Error loading history: %s", e)
            self.history_data = []

    def reload_from_disk(self) -> None:
        """Reload history from DB (call after external writes)."""
        self._load_history()

    @staticmethod
    def _entry_datetime(entry: Dict) -> datetime:
        raw = entry.get("timestamp") or entry.get("saved_at") or ""
        if not raw:
            return datetime.now()
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            return datetime.now()

    def _save_history(self):
        """Persist history to DB, falling back to JSON if DB is unavailable.

        This is called after in-memory modifications to sync back to DB.
        """
        try:
            db = _get_db()
            if db is not None:
                from database import HistoryEntry
                session = db.get_db_session()
                try:
                    # Delete all and re-insert (simple approach for this use case)
                    session.query(HistoryEntry).delete()
                    for entry in self.history_data:
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
                    session.commit()
                except Exception:
                    session.rollback()
                    raise
                finally:
                    session.close()
            else:
                # JSON fallback
                history_file = LOGS_DIR / "prompts_history.json"
                history_file.parent.mkdir(parents=True, exist_ok=True)
                with open(history_file, "w", encoding="utf-8") as f:
                    json.dump(self.history_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("Error saving history: %s", e)

    def get_history(self) -> List[Dict]:
        """Get all history entries."""
        return self.history_data

    def add_entry(self, entry: Dict):
        """Add a new history entry."""
        entry['timestamp'] = datetime.now().isoformat()
        self.history_data.insert(0, entry)

        # Also persist directly for efficiency
        try:
            db = _get_db()
            if db is not None:
                from database import HistoryEntry
                session = db.get_db_session()
                try:
                    session.add(HistoryEntry(
                        timestamp=entry.get("timestamp", ""),
                        saved_at=entry.get("saved_at", ""),
                        subject=entry.get("subject", ""),
                        style=entry.get("style", ""),
                        lighting=entry.get("lighting", ""),
                        mood=entry.get("mood", ""),
                        prompt=entry.get("prompt", ""),
                        image_path=entry.get("image_path", ""),
                        theme_sentence=entry.get("theme_sentence", ""),
                    ))
                    session.commit()
                except Exception:
                    session.rollback()
                finally:
                    session.close()
            else:
                # JSON fallback — just save whole list
                self._save_history()
        except Exception as e:
            logger.error("Error adding history entry to DB: %s", e)

    def prune_by_count(self, keep_count: int) -> int:
        """Prune history to keep only the last N entries."""
        if len(self.history_data) <= keep_count:
            return 0

        # Backup entries to be pruned
        pruned_entries = self.history_data[keep_count:]
        self._backup_entries(pruned_entries)

        # Prune in memory
        pruned_count = len(pruned_entries)
        self.history_data = self.history_data[:keep_count]
        self._save_history()

        return pruned_count

    def prune_by_days(self, keep_days: int) -> int:
        """Prune history to keep only entries from the last N days."""
        cutoff_date = datetime.now() - timedelta(days=keep_days)

        keep_entries = []
        prune_entries = []

        for entry in self.history_data:
            entry_date = self._entry_datetime(entry)
            if entry_date >= cutoff_date:
                keep_entries.append(entry)
            else:
                prune_entries.append(entry)

        if not prune_entries:
            return 0

        self._backup_entries(prune_entries)

        pruned_count = len(prune_entries)
        self.history_data = keep_entries
        self._save_history()

        return pruned_count

    def preview_prune_by_count(self, keep_count: int) -> List[Dict]:
        """Entries that would be removed by prune_by_count (oldest first)."""
        if len(self.history_data) <= keep_count:
            return []
        return list(self.history_data[keep_count:])

    def preview_prune_by_days(self, keep_days: int) -> List[Dict]:
        """Entries older than keep_days that would be removed by prune_by_days."""
        cutoff_date = datetime.now() - timedelta(days=keep_days)
        out = []
        for entry in self.history_data:
            if self._entry_datetime(entry) < cutoff_date:
                out.append(entry)
        return out

    def _backup_entries(self, entries: List[Dict]):
        """Backup entries to a timestamped backup file."""
        if not entries:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = BACKUP_DIR / f"history_backup_{timestamp}.json"

        try:
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(entries, f, indent=2)
        except Exception as e:
            logger.error("Error creating backup: %s", e)

    def restore_from_backup(self, backup_file: Path) -> bool:
        """Restore entries from a backup file."""
        try:
            base_real = os.path.realpath(BACKUP_DIR)
            target_real = os.path.realpath(backup_file)
            if os.path.commonpath([base_real, target_real]) != base_real:
                raise Exception('Invalid file path')
            with open(target_real, 'r', encoding='utf-8') as f:
                backup_entries = json.load(f)

            # Add restored entries to history
            self.history_data.extend(backup_entries)

            # Remove duplicates based on timestamp
            seen_timestamps = set()
            unique_history = []
            for entry in reversed(self.history_data):
                if entry.get('timestamp') not in seen_timestamps:
                    seen_timestamps.add(entry.get('timestamp'))
                    unique_history.append(entry)

            self.history_data = list(reversed(unique_history))
            self._save_history()

            return True
        except Exception as e:
            logger.error("Error restoring from backup: %s", e)
            return False

    def get_backup_files(self) -> List[Path]:
        """Get list of backup files."""
        return sorted(BACKUP_DIR.glob("history_backup_*.json"), reverse=True)

    def export_to_csv(self, entries: Optional[List[Dict]] = None) -> Optional[Path]:
        """Export history entries to CSV file."""
        if entries is None:
            entries = self.history_data

        if not entries:
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_file = EXPORT_DIR / f"prompts_export_{timestamp}.csv"

        try:
            with open(export_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)

                writer.writerow(['Timestamp', 'Subject', 'Style', 'Lighting', 'Mood', 'Full Prompt', 'Image Path'])

                for entry in entries:
                    writer.writerow([
                        entry.get('timestamp', ''),
                        entry.get('subject', ''),
                        entry.get('style', ''),
                        entry.get('lighting', ''),
                        entry.get('mood', ''),
                        entry.get('prompt', ''),
                        entry.get('image_path', '')
                    ])

            return export_file
        except Exception as e:
            logger.error("Error exporting to CSV: %s", e)
            return None

    def search_history(self, query: str) -> List[Dict]:
        """Search history by keyword."""
        query = query.lower()
        results = []

        for entry in self.history_data:
            searchable_text = ' '.join([
                entry.get('subject', ''),
                entry.get('style', ''),
                entry.get('lighting', ''),
                entry.get('mood', ''),
                entry.get('prompt', ''),
                entry.get('timestamp', ''),
                entry.get('saved_at', ''),
                entry.get('theme_sentence', ''),
            ]).lower()

            if query in searchable_text:
                results.append(entry)

        return results

    def filter_by_date_range(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Filter history by date range."""
        results = []

        for entry in self.history_data:
            entry_date = self._entry_datetime(entry)
            if start_date <= entry_date <= end_date:
                results.append(entry)

        return results

    def filter_by_favorites(self, favorites_data: List[Dict]) -> List[Dict]:
        """Filter history to show only favorited entries."""
        favorite_prompts = {fav.get('prompt', '') for fav in favorites_data}
        return [entry for entry in self.history_data if entry.get('prompt', '') in favorite_prompts]

    def filter_by_has_image(self) -> List[Dict]:
        """Filter history to show only entries with generated images."""
        return [entry for entry in self.history_data if entry.get('image_path')]

    def get_statistics(self) -> Dict:
        """Get history statistics."""
        total_entries = len(self.history_data)

        with_images = sum(1 for entry in self.history_data if entry.get('image_path'))

        entries_by_date = {}
        for entry in self.history_data:
            date = entry.get('timestamp', '')[:10]  # YYYY-MM-DD
            entries_by_date[date] = entries_by_date.get(date, 0) + 1

        return {
            'total_entries': total_entries,
            'with_images': with_images,
            'without_images': total_entries - with_images,
            'entries_by_date': entries_by_date,
            'oldest_entry': self.history_data[-1].get('timestamp') if self.history_data else None,
            'newest_entry': self.history_data[0].get('timestamp') if self.history_data else None
        }


# Global instance
_history_manager = None

def get_history_manager() -> HistoryManager:
    """Get the global history manager instance."""
    global _history_manager
    if _history_manager is None:
        _history_manager = HistoryManager()
    return _history_manager
