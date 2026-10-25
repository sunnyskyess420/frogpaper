# slideshow.py - Extracted slideshow manager for FrogPaper
from pathlib import Path
from datetime import datetime
import random
try:
    from set_wallpaper import set_wallpaper, collect_wallpapers
except ImportError:
    set_wallpaper = None
    collect_wallpapers = lambda: []

from utils import get_app_dir

BASEDIR = get_app_dir()
LOGSDIR = BASEDIR / 'logs'
FAVORITESDIR = BASEDIR / 'wallpapers' / 'favorites'
STYLEDDIR = BASEDIR / 'wallpapers' / 'styled'
SLIDESHOWSOURCES = ['generated', 'manual', 'all', 'favorites', 'styled']

# Wallpaper rotation intervals offered in Settings > Slideshow, in minutes:
# short stops for a quick test drive, then the long ones (up to 24 hours).
SLIDESHOW_INTERVAL_PRESETS = (1, 5, 10, 15, 30, 60, 120, 180, 240, 360, 480, 720, 1440)

# Ceiling applied to values read from a hand-edited config.json (one week).
MAX_INTERVAL_MINUTES = 7 * 24 * 60


def format_interval_label(minutes):
    """Friendly label for an interval given in minutes.

    45 -> '45 minutes', 60 -> '1 hour', 90 -> '1 hour 30 min', 1440 -> '24 hours'.
    """
    try:
        total = max(1, int(round(float(minutes))))
    except (TypeError, ValueError):
        total = 60
    hours, mins = divmod(total, 60)
    if hours and mins:
        return f"{hours} hour{'s' if hours != 1 else ''} {mins} min"
    if hours:
        return f"{hours} hour{'s' if hours != 1 else ''}"
    return f"{total} minute{'s' if total != 1 else ''}"


def format_remaining(seconds):
    """Compact countdown text that visibly ticks every second.

    Under an hour: '08:15'. Over an hour: '23h 04m 09s'.
    Past two days: '3d 02h 05m 12s'. A 24-hour interval shows
    '24h 00m 00s' so it still matches the picker's label.
    """
    secs = max(0, int(seconds))
    if secs < 3600:
        mins, rem = divmod(secs, 60)
        return f"{mins:02d}:{rem:02d}"
    hours, rem = divmod(secs, 3600)
    minutes, secs = divmod(rem, 60)
    if hours >= 48:
        days, hours = divmod(hours, 24)
        return f"{days}d {hours:02d}h {minutes:02d}m {secs:02d}s"
    return f"{hours}h {minutes:02d}m {secs:02d}s"


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
        self._active_interval_minutes = None

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
            filtered = [p for p in candidates if p.name.lower() not in seen]
            # If all candidates were filtered out (history exhausted), reset and start fresh
            if filtered:
                candidates = filtered
            else:
                # All images have been shown — clear history so they can repeat
                self.history.clear()
        
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

        # Windows desktop doesn't support true wallpaper crossfading
        # Direct wallpaper change without app window overlay
        try:
            if not set_wallpaper:
                self.status_var.set('Slideshow: set_wallpaper unavailable')
                return False
            ok = set_wallpaper(chosen)
            self.status_var.set(f'Slideshow: {chosen.name}' if ok else 'Slideshow: Set failed.')
            return ok
        except Exception as e:
            self.status_var.set(f'Slideshow failed: {e}')
            return False

    def _interval_minutes(self):
        """Read the interval (minutes) from the UI variable, clamped safely."""
        try:
            var = getattr(self, 'slideshow_interval_var', None)
            val = var.get().strip() if var is not None else ""
            minutes = max(1, int(float(val) if val else 60))
        except (ValueError, TypeError, AttributeError):
            minutes = 60
        return min(MAX_INTERVAL_MINUTES, minutes)

    def tick(self):
        """Timer callback."""
        self.after_id = None
        if not self.running or self.paused:
            return
        if not hasattr(self, 'slideshow_source_var'):
            return  # Config not loaded yet
        try:
            source = self._active_source()
            minutes = self._interval_minutes()
            self._active_interval_minutes = minutes
            self.do_change(
                source,
                minutes * 60,
                self.slideshow_order_var.get(),
                bool(self.slideshow_skip_duplicates_var.get()),
            )
            self.schedule_next(minutes * 60 * 1000)  # ms
        except Exception:
            # Tk widget or variable was destroyed during shutdown - stop silently
            self.running = False

    def schedule_next(self, ms):
        """Schedule next tick."""
        if self.running:
            self.after_id = self.root.after(ms, self.tick)

    def start(self, initial=False):
        """Start the slideshow.

        ``initial=True`` is used at app startup: the first change waits for
        the full configured interval instead of firing one second after the
        window opens. Explicit Start still advances promptly.
        """
        self.stop()
        self.running = True
        if not initial:
            self.status_var.set('Slideshow enabled.')
        minutes = self._interval_minutes()
        self._active_interval_minutes = minutes
        if initial:
            self.last_run = datetime.now()
            self.schedule_next(minutes * 60 * 1000)
        else:
            self.schedule_next(1000)  # Start soon

    def stop(self):
        """Stop slideshow."""
        self.running = False
        self.paused = False
        self._active_interval_minutes = None
        if self.after_id is not None:
            try:
                self.root.after_cancel(self.after_id)
            except Exception:
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
            except Exception:
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
            if not set_wallpaper:
                self.status_var.set('Slideshow: set_wallpaper unavailable')
                return False
            ok = set_wallpaper(prev_path)
            if ok:
                self.status_var.set(f'Slideshow: ◄ {prev_path.name}')
                self.reset_timer()
            else:
                self.status_var.set('Slideshow: Set failed.')
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
        minutes = self._interval_minutes()
        self._active_interval_minutes = minutes
        self.last_run = datetime.now()
        self.schedule_next(minutes * 60 * 1000)

    def check_interval_changed(self):
        """Apply a newly selected interval to an already-running slideshow.

        Settings are saved without restarting the timer, so without this the
        old `after` job keeps its original delay. Changing 60 minutes to 12
        hours would still fire at the 60-minute mark once, which looks like
        the new setting was ignored.
        """
        if not self.running or self.paused:
            return
        minutes = self._interval_minutes()
        if self._active_interval_minutes == minutes:
            return
        if self.after_id is not None:
            try:
                self.root.after_cancel(self.after_id)
            except Exception:
                pass
            self.after_id = None
        self._active_interval_minutes = minutes
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
            if not set_wallpaper:
                self.status_var.set('Slideshow: set_wallpaper unavailable')
                return False
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
            except Exception:
                interval_minutes = 60.0
            
            if self.last_run:
                elapsed = (datetime.now() - self.last_run).total_seconds()
                remaining_seconds = max(0, int(interval_minutes * 60) - int(elapsed))
                next_text = f'next in {format_remaining(remaining_seconds)}'
            else:
                next_text = 'starting...'
            
            return f'Running ({candidates_len}) {source_display} {next_text}'
        return f'Idle ({candidates_len}) {source_display}'