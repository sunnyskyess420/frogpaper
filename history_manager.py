"""
History Manager for FrogPaper

Provides history cleanup, pruning policies, backup, and export functionality.
"""

import json
import csv
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import shutil

from utils import get_app_dir

BASE_DIR = get_app_dir()
LOGS_DIR = BASE_DIR / "logs"
HISTORY_FILE = LOGS_DIR / "prompts_history.json"
BACKUP_DIR = LOGS_DIR / "history_backups"
EXPORT_DIR = LOGS_DIR / "history_exports"
BACKUP_DIR.mkdir(exist_ok=True)
EXPORT_DIR.mkdir(exist_ok=True)


class HistoryManager:
    """Manages prompt history with cleanup and export capabilities."""
    
    def __init__(self):
        self.history_data = []
        self._load_history()
    
    def _load_history(self):
        """Load history from JSON file."""
        try:
            if HISTORY_FILE.exists():
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                    self.history_data = json.load(f)
            else:
                self.history_data = []
        except Exception as e:
            print(f"Error loading history: {e}")
            self.history_data = []

    def reload_from_disk(self) -> None:
        """Reload history from disk (call after external writes to the JSON file)."""
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
        """Save history to JSON file."""
        try:
            with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.history_data, f, indent=2)
        except Exception as e:
            print(f"Error saving history: {e}")
    
    def get_history(self) -> List[Dict]:
        """Get all history entries."""
        return self.history_data
    
    def add_entry(self, entry: Dict):
        """Add a new history entry."""
        entry['timestamp'] = datetime.now().isoformat()
        self.history_data.insert(0, entry)  # Add to beginning
        self._save_history()
    
    def prune_by_count(self, keep_count: int) -> int:
        """
        Prune history to keep only the last N entries.
        
        Args:
            keep_count: Number of entries to keep
            
        Returns:
            Number of entries pruned
        """
        if len(self.history_data) <= keep_count:
            return 0
        
        # Backup entries to be pruned
        pruned_entries = self.history_data[keep_count:]
        self._backup_entries(pruned_entries)
        
        # Prune
        pruned_count = len(pruned_entries)
        self.history_data = self.history_data[:keep_count]
        self._save_history()
        
        return pruned_count
    
    def prune_by_days(self, keep_days: int) -> int:
        """
        Prune history to keep only entries from the last N days.
        
        Args:
            keep_days: Number of days to keep
            
        Returns:
            Number of entries pruned
        """
        cutoff_date = datetime.now() - timedelta(days=keep_days)
        
        # Separate entries to keep and prune
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
        
        # Backup entries to be pruned
        self._backup_entries(prune_entries)
        
        # Prune
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
            print(f"Error creating backup: {e}")
    
    def restore_from_backup(self, backup_file: Path) -> bool:
        """
        Restore entries from a backup file.
        
        Args:
            backup_file: Path to backup file
            
        Returns:
            True if successful
        """
        try:
            with open(backup_file, 'r', encoding='utf-8') as f:
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
            print(f"Error restoring from backup: {e}")
            return False
    
    def get_backup_files(self) -> List[Path]:
        """Get list of backup files."""
        return sorted(BACKUP_DIR.glob("history_backup_*.json"), reverse=True)
    
    def export_to_csv(self, entries: Optional[List[Dict]] = None) -> Optional[Path]:
        """
        Export history entries to CSV file.
        
        Args:
            entries: Entries to export (None = all entries)
            
        Returns:
            Path to exported CSV file or None if failed
        """
        if entries is None:
            entries = self.history_data
        
        if not entries:
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_file = EXPORT_DIR / f"prompts_export_{timestamp}.csv"
        
        try:
            with open(export_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Write header
                writer.writerow(['Timestamp', 'Subject', 'Style', 'Lighting', 'Mood', 'Full Prompt', 'Image Path'])
                
                # Write entries
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
            print(f"Error exporting to CSV: {e}")
            return None
    
    def search_history(self, query: str) -> List[Dict]:
        """
        Search history by keyword.
        
        Args:
            query: Search query
            
        Returns:
            Matching entries
        """
        query = query.lower()
        results = []
        
        for entry in self.history_data:
            # Search in all text fields
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
        """
        Filter history by date range.
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            Entries within date range
        """
        results = []
        
        for entry in self.history_data:
            entry_date = self._entry_datetime(entry)
            if start_date <= entry_date <= end_date:
                results.append(entry)
        
        return results
    
    def filter_by_favorites(self, favorites_data: List[Dict]) -> List[Dict]:
        """
        Filter history to show only favorited entries.
        
        Args:
            favorites_data: List of favorite entries
            
        Returns:
            Entries that are in favorites
        """
        favorite_prompts = {fav.get('prompt', '') for fav in favorites_data}
        return [entry for entry in self.history_data if entry.get('prompt', '') in favorite_prompts]
    
    def filter_by_has_image(self) -> List[Dict]:
        """
        Filter history to show only entries with generated images.
        
        Returns:
            Entries with image paths
        """
        return [entry for entry in self.history_data if entry.get('image_path')]
    
    def get_statistics(self) -> Dict:
        """Get history statistics."""
        total_entries = len(self.history_data)
        
        # Count entries with images
        with_images = sum(1 for entry in self.history_data if entry.get('image_path'))
        
        # Count entries by date
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
