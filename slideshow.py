# slideshow.py - Extracted slideshow manager for FrogPaper
from pathlib import Path
from datetime import datetime
import random
import tkinter as tk
from tkinter import messagebox
from set_wallpaper import set_wallpaper, collect_wallpapers  # Assumes WINDOWS=True

BASEDIR = Path(__file__).parent
LOGSDIR = BASEDIR / 'logs'
FAVORITESDIR = BASEDIR / 'wallpapers' / 'favorites'
STYLEDDIR = BASEDIR / 'wallpapers' / 'styled'
SLIDESHOWSOURCES = ['generated', 'manual', 'all', 'favorites', 'styled']

class SlideshowManager:
    def __init__(self, app_root, status_var):
        self.root = app_root
        self.status_var = status_var
        self.running = False
        self.paused = False
        self.after_id = None
        self.history = []  # Paths used, for skip-duplicates
        self.last_run = None
        self.last_path = None
        self.all_known_images = []  # Set in load_gallery()

    def load_gallery(self, all_images):
        """Call this when gallery refreshes."""
        self.all_known_images = all_images

    def candidates(self, source='all', order='random', skip_duplicates=True):
        """Get eligible wallpapers."""
        candidates = []
        
        if source == 'favorites':
            # Use favorites/ folder as source of truth
            if FAVORITESDIR.exists():
                for p in FAVORITESDIR.iterdir():
                    if p.is_file() and p.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}:
                        candidates.append(p)
        elif source == 'styled':
            # Use styled/ folder as source of truth
            if STYLEDDIR.exists():
                for p in STYLEDDIR.iterdir():
                    if p.is_file() and p.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}:
                        candidates.append(p)
        else:
            # Existing logic for generated, manual, all
            for p in self.all_known_images:
                # More robust check: is it in the 'generated' subfolder?
                is_generated = 'generated' in str(p.parent).lower()
                
                if source == 'generated' and is_generated:
                    candidates.append(p)
                elif source == 'manual' and not is_generated:
                    candidates.append(p)
                elif source == 'all':
                    candidates.append(p)
        
        if order == 'random':
            random.shuffle(candidates)
        elif order == 'newest':
            candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        elif order == 'oldest':
            candidates.sort(key=lambda p: p.stat().st_mtime)
        
        if skip_duplicates:
            # Filter out recent history (extract basename for comparison)
            seen = {Path(h).name.lower() for h in self.history[-50:]}  # Last 50 filenames
            candidates = [p for p in candidates if p.name.lower() not in seen]
        
        return candidates

    def do_change(self, source='all', interval=60, order='random', skip_duplicates=True):
        """Perform one wallpaper change."""
        candidates = self.candidates(source, order, skip_duplicates)
        if not candidates:
            self.status_var.set('Slideshow: No wallpapers found.')
            return False
        
        chosen = random.choice(candidates) if order == 'random' else candidates[0]
        
        self.history.append(str(chosen.resolve()))
        if len(self.history) > 500:
            self.history = self.history[-250:]
        self.last_path = chosen
        self.last_run = datetime.now()
        
        try:
            ok = set_wallpaper(chosen)
            self.status_var.set(f'Slideshow: {chosen.name}' if ok else 'Slideshow: Set failed.')
            return ok
        except Exception as e:
            self.status_var.set(f'Slideshow failed: {e}')
            return False

    def tick(self):
        """Timer callback."""
        self.after_id = None
        if not self.running or self.paused:
            return
        if not hasattr(self, 'slideshow_source_var'):
            return  # Config not loaded yet
        try:
            source = self._active_source()

            try:
                val = self.slideshow_interval_var.get().strip()
                minutes = max(1, int(float(val)) if val else 60)
            except (ValueError, TypeError):
                minutes = 60

            self.do_change(source, minutes * 60, self.slideshow_order_var.get(), bool(self.slideshow_skip_duplicates_var.get()))
            self.schedule_next(minutes * 60 * 1000)  # ms
        except Exception:
            # Tk widget or variable was destroyed during shutdown — stop silently
            self.running = False

    def schedule_next(self, ms):
        """Schedule next tick."""
        if self.running:
            self.after_id = self.root.after(ms, self.tick)

    def start(self, initial=False):
        """Start slideshow."""
        self.stop()
        self.running = True
        if not initial:
            self.status_var.set('Slideshow enabled.')
        self.schedule_next(1000)  # Start soon

    def stop(self):
        """Stop slideshow."""
        self.running = False
        self.paused = False
        if self.after_id is not None:
            try:
                self.root.after_cancel(self.after_id)
            except:
                pass
        self.after_id = None
        self.status_var.set('Slideshow disabled.')

    def pause(self):
        """Pause slideshow without resetting running state."""
        if not self.running:
            return
        self.paused = True
        if self.after_id is not None:
            try:
                self.root.after_cancel(self.after_id)
            except:
                pass
        self.after_id = None
        self.status_var.set('Slideshow paused.')

    def resume(self):
        """Resume a paused slideshow."""
        if not self.running or not self.paused:
            return
        self.paused = False
        self.schedule_next(1000)
        self.status_var.set('Slideshow resumed.')

    def prev_wallpaper(self):
        """Set the wallpaper to the previous item in history."""
        # history[-1] is the current wallpaper; we want [-2]
        if len(self.history) < 2:
            self.status_var.set('Slideshow: No previous wallpaper.')
            return False
        prev_path = Path(self.history[-2])
        if not prev_path.exists():
            self.status_var.set('Slideshow: Previous file not found.')
            return False
        # Remove the current entry so next tick picks a fresh one
        self.history.pop()
        self.last_path = prev_path
        self.last_run = datetime.now()
        try:
            ok = set_wallpaper(prev_path)
            self.status_var.set(f'Slideshow: ◄ {prev_path.name}' if ok else 'Slideshow: Set failed.')
            if ok:
                self.reset_timer()
            return ok
        except Exception as e:
            self.status_var.set(f'Slideshow failed: {e}')
            return False

    def _active_source(self):
        """Resolve the current slideshow source value from the UI variable."""
        label_to_value = {
            'Generated': 'generated',
            'Manual': 'manual',
            'All Images': 'all',
            'Favorites': 'favorites',
        }
        display = getattr(self, 'slideshow_source_var', None)
        label = display.get().strip() if display else 'All Images'
        return label_to_value.get(label, label.lower()) or 'all'

    def reset_timer(self):
        """Restart the interval countdown from now (call after any manual wallpaper change)."""
        if not self.running or self.paused:
            return
        if self.after_id is not None:
            try:
                self.root.after_cancel(self.after_id)
            except Exception:
                pass
            self.after_id = None
        try:
            val = getattr(self, 'slideshow_interval_var', None)
            minutes = max(1, int(float(val.get().strip()) if val else 60))
        except (ValueError, TypeError):
            minutes = 60
        self.last_run = datetime.now()
        self.schedule_next(minutes * 60 * 1000)

    def next_now(self):
        """Manual next."""
        if not self.do_change(source=self._active_source()):
            self.status_var.set('No eligible wallpapers.')
        self.reset_timer()

    def advance_once(self):
        """Single advance without rescheduling next tick."""
        candidates = self.candidates(source=self._active_source())
        if not candidates:
            self.status_var.set('Slideshow: No wallpapers found.')
            return False
        
        order = getattr(self, 'slideshow_order_var', None)
        chosen = random.choice(candidates) if (order is None or order.get() == 'random') else candidates[0]
        
        self.history.append(str(chosen.resolve()))
        if len(self.history) > 500:
            self.history = self.history[-250:]
        self.last_path = chosen
        self.last_run = datetime.now()
        
        try:
            ok = set_wallpaper(chosen)
            self.status_var.set(f'Slideshow: {chosen.name}' if ok else 'Slideshow: Set failed.')
            return ok
        except Exception as e:
            self.status_var.set(f'Slideshow failed: {e}')
            return False

    def status_text(self):
        """For UI label."""
        candidates_len = len(self.candidates(source=self._active_source()))
        source_display = getattr(self, 'slideshow_source_var', type('obj', (), {'get': lambda self: 'All Images'})()).get()
        if self.running and self.paused:
            return f'Paused ({candidates_len}) {source_display}'
        if self.running:
            try:
                interval_minutes = float(getattr(self, 'slideshow_interval_var', type('obj', (), {'get': lambda self: '60'})()).get())
            except:
                interval_minutes = 60.0
            
            if self.last_run:
                elapsed = (datetime.now() - self.last_run).total_seconds()
                remaining_seconds = max(0, int(interval_minutes * 60) - int(elapsed))
                next_text = f'next in {remaining_seconds // 60}m:{remaining_seconds % 60:02d}s'
            else:
                next_text = 'starting...'
            
            return f'Running ({candidates_len}) {source_display} {next_text}'
        return f'Idle ({candidates_len}) {source_display}'