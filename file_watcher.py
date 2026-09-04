"""
file_watcher.py
---------------
File monitoring for automatic sync triggers using watchdog.
"""

import logging
import threading
from typing import Callable, Optional

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent, FileDeletedEvent  # noqa: F401  (availability probe)
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

from utils import get_app_dir

logger = logging.getLogger(__name__)

BASE_DIR = get_app_dir()
WALLPAPERS_DIR = BASE_DIR / "wallpapers"


class WallpaperEventHandler(FileSystemEventHandler):
    """Handler for wallpaper file system events."""
    
    def __init__(self, sync_callback: Callable):
        """
        Args:
            sync_callback: Function to call when sync should be triggered
        """
        super().__init__()
        self.sync_callback = sync_callback
        self._debounce_timer = None
        self._debounce_delay = 5.0  # seconds to wait before triggering sync
        
    def on_any_event(self, event):
        """Handle any file system event (created, modified, deleted, moved)."""
        if event.is_directory:
            return
            
        # Only process image files
        if not event.src_path.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
            return
            
        logger.debug(f"File event detected: {event.event_type} - {event.src_path}")
        
        # Debounce rapid file changes (e.g., batch operations)
        if self._debounce_timer:
            self._debounce_timer.cancel()
            
        # Schedule sync after debounce delay
        self._debounce_timer = threading.Timer(self._debounce_delay, self._trigger_sync)
        self._debounce_timer.start()
        
    def _trigger_sync(self):
        """Trigger the sync callback."""
        try:
            logger.info("Triggering sync due to file changes")
            self.sync_callback()
        except Exception as e:
            logger.error(f"Error triggering sync callback: {e}")


class FileWatcher:
    """Monitors wallpaper directories for changes and triggers sync."""
    
    def __init__(self, sync_callback: Optional[Callable] = None):
        """
        Args:
            sync_callback: Function to call when sync should be triggered
        """
        self.sync_callback = sync_callback
        self.observer = None
        self.watching = False
        self.watch_thread = None
        
    def start(self):
        """Start file watching in background thread."""
        if not WATCHDOG_AVAILABLE:
            logger.warning("watchdog not available, file watching disabled")
            return False
            
        if self.watching:
            logger.info("File watcher already running")
            return True
            
        try:
            self.observer = Observer()
            event_handler = WallpaperEventHandler(self.sync_callback)
            
            # Watch all wallpaper subdirectories
            watch_dirs = []
            if WALLPAPERS_DIR.exists():
                for subdir in WALLPAPERS_DIR.iterdir():
                    if subdir.is_dir():
                        self.observer.schedule(event_handler, str(subdir), recursive=True)
                        watch_dirs.append(subdir)
                        logger.info(f"Watching directory: {subdir}")
            
            if not watch_dirs:
                logger.warning("No wallpaper directories to watch")
                return False
                
            # Start observer in background thread
            self.observer.start()
            self.watching = True
            logger.info("File watcher started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start file watcher: {e}")
            return False
    
    def stop(self):
        """Stop file watching."""
        if not self.watching:
            return
            
        try:
            if self.observer:
                self.observer.stop()
                self.observer.join(timeout=5)
            self.watching = False
            logger.info("File watcher stopped")
        except Exception as e:
            logger.error(f"Error stopping file watcher: {e}")
    
    def is_running(self) -> bool:
        """Check if file watcher is currently running."""
        return self.watching and self.observer and self.observer.is_alive()
