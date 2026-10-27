# slideshow.py - Extracted slideshow manager for FrogPaper
from pathlib import Path
from datetime import datetime
import random
import logging
import time
try:
    from set_wallpaper import set_wallpaper, collect_wallpapers
except ImportError:
    set_wallpaper = None
    collect_wallpapers = lambda: []

from utils import get_app_dir

logger = logging.getLogger(__name__)

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
        self._deadline = None  # Monotonic timestamp when next change should occur
        self._epoch = 0  # Incremented on each timer reschedule to ignore stale callbacks

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

    def tick(self, expected_epoch):
        """Timer callback with epoch check to ignore stale callbacks."""
        # Ignore callbacks from cancelled/rescheduled timers
        if expected_epoch != self._epoch:
            logger.info(f"slideshow_stale_callback_ignored: expected_epoch={expected_epoch}, current_epoch={self._epoch}")
            return

        self.after_id = None
        if not self.running or self.paused:
            logger.info("slideshow_tick: skipped (not running or paused)")
            return
        if not hasattr(self, 'slideshow_source_var'):
            logger.info("slideshow_tick: skipped (config not loaded)")
            return  # Config not loaded yet

        try:
            source = self._active_source()
            minutes = self._interval_minutes()
            self._active_interval_minutes = minutes
            logger.info(f"slideshow_fire: interval={minutes}min, source={source}")
            self.do_change(
                source,
                minutes * 60,
                self.slideshow_order_var.get(),
                bool(self.slideshow_skip_duplicates_var.get()),
            )
            self._schedule_next(minutes * 60 * 1000, source='tick')
        except Exception as e:
            # Tk widget or variable was destroyed during shutdown - stop silently
            logger.error(f"slideshow_tick error: {e}")
            self.running = False

    def _schedule_next(self, delay_ms, source='unknown'):
        """Schedule next tick, always cancelling any existing job first."""
        if self.after_id is not None:
            try:
                self.root.after_cancel(self.after_id)
                logger.debug(f"slideshow_reschedule: cancelled after_id={self.after_id}, source={source}")
            except Exception as e:
                logger.warning(f"slideshow_reschedule: failed to cancel after_id={self.after_id}: {e}")
            self.after_id = None

        if self.running and not self.paused:
            self._epoch += 1
            epoch = self._epoch
            self._deadline = time.monotonic() + (delay_ms / 1000)
            self.after_id = self.root.after(delay_ms, lambda: self.tick(epoch))
            logger.info(f"slideshow_reschedule: delay={delay_ms}ms, epoch={epoch}, source={source}, after_id={self.after_id}")
        else:
            logger.debug(f"slideshow_reschedule: skipped (running={self.running}, paused={self.paused})")

    def schedule_next(self, ms):
        """Legacy method - redirects to _schedule_next for compatibility."""
        self._schedule_next(ms, source='legacy')

    def start(self, initial=False):
        """Start the slideshow.

        Cancels any existing timer and schedules the full interval from now.
        Does NOT change the wallpaper immediately - use manual advance for that.
        ``initial=True`` is used at app startup.
        """
        logger.info(f"slideshow_start: initial={initial}")
        self.stop()  # Cancel any existing timer first
        self.running = True
        self.paused = False
        if not initial:
            self.status_var.set('Slideshow enabled.')
        minutes = self._interval_minutes()
        self._active_interval_minutes = minutes
        # Always schedule the full interval, never 1000ms
        delay_ms = minutes * 60 * 1000
        self._schedule_next(delay_ms, source='start')
        logger.info(f"slideshow_start: scheduled {minutes}min interval")

    def stop(self):
        """Stop slideshow."""
        logger.info("slideshow_stop")
        self.running = False
        self.paused = False
        self._active_interval_minutes = None
        self._deadline = None
        if self.after_id is not None:
            try:
                self.root.after_cancel(self.after_id)
                logger.debug(f"slideshow_stop: cancelled after_id={self.after_id}")
            except Exception as e:
                logger.warning(f"slideshow_stop: failed to cancel after_id={self.after_id}: {e}")
        self.after_id = None
        self.status_var.set('Slideshow disabled.')

    def pause(self):
        """Pause slideshow without resetting running state, preserving remaining time."""
        if not self.running:
            logger.info("slideshow_pause: skipped (not running)")
            return
        logger.info("slideshow_pause")
        self.paused = True
        # Save remaining time before cancelling
        if self._deadline is not None:
            self._remaining_ms = max(0, int((self._deadline - time.monotonic()) * 1000))
            logger.info(f"slideshow_pause: saved remaining_ms={self._remaining_ms}")
        else:
            self._remaining_ms = 0
        if self.after_id is not None:
            try:
                self.root.after_cancel(self.after_id)
                logger.debug(f"slideshow_pause: cancelled after_id={self.after_id}")
            except Exception as e:
                logger.warning(f"slideshow_pause: failed to cancel after_id={self.after_id}: {e}")
        self.after_id = None
        self.status_var.set('Slideshow paused.')

    def resume(self):
        """Resume a paused slideshow with preserved remaining time."""
        if not self.running or not self.paused:
            logger.info("slideshow_resume: skipped (not running or not paused)")
            return
        logger.info(f"slideshow_resume: remaining_ms={getattr(self, '_remaining_ms', 0)}")
        self.paused = False
        remaining_ms = getattr(self, '_remaining_ms', 0)
        if remaining_ms == 0:
            # No remaining time, fire once immediately then schedule full interval
            minutes = self._interval_minutes()
            source = self._active_source()
            logger.info(f"slideshow_resume: firing immediately (no remaining time)")
            try:
                self.do_change(
                    source,
                    minutes * 60,
                    self.slideshow_order_var.get(),
                    bool(self.slideshow_skip_duplicates_var.get()),
                )
            except Exception as e:
                logger.error(f"slideshow_resume immediate change error: {e}")
            delay_ms = minutes * 60 * 1000
        else:
            delay_ms = remaining_ms
        self._schedule_next(delay_ms, source='resume')
        self.status_var.set('Slideshow resumed.')

    def prev_wallpaper(self):
        """Set the wallpaper to the previous item in history."""
        logger.info("slideshow_manual_advance: prev_wallpaper")
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
        # Do NOT update last_run - keeps the existing deadline intact

        try:
            if not set_wallpaper:
                self.status_var.set('Slideshow: set_wallpaper unavailable')
                return False
            ok = set_wallpaper(prev_path)
            if ok:
                self.status_var.set(f'Slideshow: ◄ {prev_path.name}')
            else:
                self.status_var.set('Slideshow: Set failed.')
            logger.info("slideshow_manual_advance: prev_wallpaper completed (timer not reset)")
            return ok
        except Exception as e:
            self.status_var.set(f'Slideshow failed: {e}')
            logger.error(f"slideshow_manual_advance error: {e}")
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
        """Restart the interval countdown from now (call after any manual wallpaper change).

        NOTE: This method is now DEPRECATED for manual advances. Manual advances should
        NOT reset the timer. Use check_interval_changed() instead for intentional rescheduling.
        """
        logger.warning("reset_timer called - this is deprecated for manual advances")
        if not self.running or self.paused:
            return
        minutes = self._interval_minutes()
        self._active_interval_minutes = minutes
        self.last_run = datetime.now()
        self._schedule_next(minutes * 60 * 1000, source='reset_timer')

    def check_interval_changed(self):
        """Apply a newly selected interval to an already-running slideshow.

        Only reschedules when the interval value actually changed.
        A plain Save or opening Settings must not touch the timer.
        """
        if not self.running or self.paused:
            return
        minutes = self._interval_minutes()
        if self._active_interval_minutes == minutes:
            return  # No change, do nothing
        logger.info(f"slideshow_reschedule: interval changed from {self._active_interval_minutes} to {minutes}min")
        self._active_interval_minutes = minutes
        self.last_run = datetime.now()
        self._schedule_next(minutes * 60 * 1000, source='interval_changed')

    def next_now(self):
        """Manual next - changes wallpaper once without resetting the timer."""
        logger.info("slideshow_manual_advance: next_now")
        if not self.do_change(source=self._active_source()):
            self.status_var.set('No eligible wallpapers.')
        # Do NOT reset the timer - keep the existing deadline
        logger.info("slideshow_manual_advance: next_now completed (timer not reset)")

    def advance_once(self):
        """Single advance without rescheduling next tick.

        Used by tray/keyboard shortcuts. Changes wallpaper once and leaves
        the pending timer/deadline unchanged. Does not update last_run.
        """
        logger.info("slideshow_manual_advance: advance_once")
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
        # Do NOT update last_run - keeps the existing deadline intact

        try:
            if not set_wallpaper:
                self.status_var.set('Slideshow: set_wallpaper unavailable')
                return False
            ok = set_wallpaper(chosen)
            self.status_var.set(f'Slideshow: {chosen.name}' if ok else 'Slideshow: Set failed.')
            logger.info("slideshow_manual_advance: advance_once completed (timer not reset)")
            return ok
        except Exception as e:
            self.status_var.set(f'Slideshow failed: {e}')
            logger.error(f"slideshow_manual_advance error: {e}")
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