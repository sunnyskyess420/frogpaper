"""Slideshow control methods for the Settings tab (roadmap #7 Phase A).

Hosts the Start/Stop/Next/Prev/Pause handlers, source preview and the
live status updater for the wallpaper slideshow.  Mixed into
``SettingsTab``; all state lives on ``self.app.slideshow`` as before.
"""

import tkinter as tk
from datetime import datetime

from utils import load_config


class SettingsSlideshowMixin:
    """Slideshow control methods for SettingsTab."""

    def load_slideshow_settings(self):
        """Load slideshow settings from config and sync state.
        
        Safe to call before UI is built (e.g. during __init__).
        Creates tk variables if they don't exist yet.
        """
        app = self.app
        config = load_config()
        
        # Ensure tk variables exist (may be called before _build_slideshow_category)
        if not hasattr(app, 'slideshow_enabled_var'):
            app.slideshow_enabled_var = tk.BooleanVar(value=False)
        if not hasattr(app, 'slideshow_interval_var'):
            app.slideshow_interval_var = tk.StringVar(value='60')
        if not hasattr(app, 'slideshow_source_var'):
            app.slideshow_source_var = tk.StringVar(value='All Images')
        if not hasattr(app, 'slideshow_order_var'):
            app.slideshow_order_var = tk.StringVar(value='random')
        if not hasattr(app, 'slideshow_skip_duplicates_var'):
            app.slideshow_skip_duplicates_var = tk.BooleanVar(value=True)
        if not hasattr(app, 'slideshow_status_var'):
            app.slideshow_status_var = tk.StringVar(value='')
        
        app.slideshow_enabled_var.set(bool(config.get('slideshow_enabled', False)))
        interval_value = str(config.get('slideshow_interval', 60))
        app.slideshow_interval_var.set(interval_value)
        try:
            interval_int = int(float(interval_value))
            interval_int = max(1, min(60, interval_int))
            if hasattr(app, 'interval_display_var'):
                app.interval_display_var.set(str(interval_int))
            if hasattr(app, 'interval_slider'):
                app.interval_slider.set(interval_int)
        except (ValueError, AttributeError):
            if hasattr(app, 'interval_display_var'):
                app.interval_display_var.set('60')
            if hasattr(app, 'interval_slider'):
                app.interval_slider.set(60)
        source_value = config.get('slideshow_source', 'both')
        if source_value == 'both':
            source_value = 'all'
        app.slideshow_source_var.set(app.SLIDESHOW_SOURCE_LABELS.get(source_value, 'All Images'))
        app.slideshow_order_var.set(config.get('slideshow_order', 'random'))
        app.slideshow_skip_duplicates_var.set(bool(config.get('slideshow_skip_duplicates', True)))
        app.slideshow.load_gallery(app.gallery_images or [])
        self.sync_slideshow_state()
        self.on_slideshow_toggle()
        app.root.after(200, self.update_slideshow_status)

    def sync_slideshow_state(self):
        """Pass app UI variables to the SlideshowManager instance."""
        app = self.app
        if not hasattr(app, 'slideshow_source_var'):
            return
        app.slideshow.slideshow_enabled_var = app.slideshow_enabled_var
        app.slideshow.slideshow_interval_var = app.slideshow_interval_var
        app.slideshow.slideshow_source_var = app.slideshow_source_var
        app.slideshow.slideshow_order_var = app.slideshow_order_var
        app.slideshow.slideshow_skip_duplicates_var = app.slideshow_skip_duplicates_var

    def on_slideshow_toggle(self):
        """Start or stop slideshow based on enabled state."""
        app = self.app
        if not hasattr(app, 'slideshow_enabled_var'):
            return
        app.slideshow.start() if app.slideshow_enabled_var.get() else app.slideshow.stop()
        self.update_slideshow_status()

    def slideshow_start_click(self):
        """Start the slideshow."""
        app = self.app
        app.slideshow_enabled_var.set(True)
        app.slideshow.start()
        self.update_slideshow_status()
        app.status_var.set('Slideshow started.')

    def slideshow_stop_click(self):
        """Stop the slideshow."""
        app = self.app
        app.slideshow_enabled_var.set(False)
        app.slideshow.stop()
        self.update_slideshow_status()
        app.status_var.set('Slideshow stopped.')

    def slideshow_next_now(self):
        """Jump to next wallpaper in slideshow."""
        self.app.slideshow.next_now()

    def slideshow_prev_now(self):
        """Jump to previous wallpaper in slideshow."""
        self.app.slideshow.prev_wallpaper()

    def slideshow_pause_click(self):
        """Toggle pause/resume on slideshow."""
        app = self.app
        if app.slideshow.paused:
            app.slideshow.resume()
        else:
            app.slideshow.pause()
        self.update_slideshow_status()

    def slideshow_preview_sources(self):
        """Show dialog with eligible slideshow images."""
        app = self.app
        source_value = app.SLIDESHOW_LABEL_TO_VALUE.get(
            app.slideshow_source_var.get().strip(),
            app.slideshow_source_var.get().strip().lower()
        ) or 'all'
        candidates = app.slideshow.candidates(
            source=source_value,
            order=app.slideshow_order_var.get(),
            skip_duplicates=bool(app.slideshow_skip_duplicates_var.get())
        )
        lines = [f'Eligible images: {len(candidates)}']
        lines.append(f'Source: {app.slideshow_source_var.get()}')
        for i, p in enumerate(candidates[:30]):
            lines.append(f'{i+1}. {p.name}')
        if len(candidates) > 30:
            lines.append(f'... and {len(candidates) - 30} more')
        app._dialog.info('Slideshow Sources', '\n'.join(lines))

    def update_slideshow_status(self):
        """Update slideshow status display and progress bar."""
        app = self.app
        app.slideshow_status_var.set(app.slideshow.status_text())
        if hasattr(app, 'slideshow_pause_btn'):
            if app.slideshow.paused:
                app.slideshow_pause_btn.config(text=" Resume", style="Active.TButton")
            else:
                app.slideshow_pause_btn.config(text=" Pause", style="TButton")
        if app.slideshow.running and not app.slideshow.paused and app.slideshow.last_run:
            try:
                interval_mins = float(app.slideshow_interval_var.get())
                elapsed = (datetime.now() - app.slideshow.last_run).total_seconds()
                total = interval_mins * 60
                remaining = max(0, total - elapsed)
                mins, secs = divmod(int(remaining), 60)
                time_str = f"{mins:02d}:{secs:02d}"
                progress_pct = min(100, (elapsed / total) * 100)
                app.progress.config(mode="determinate", value=progress_pct)
                app.progress.grid()
                pal = app.THEMES.get(app.current_theme_name, app.THEMES["darkforest"])
                accent = pal.get("accent", pal["progress"])
                app.progress_overlay_label.config(text=f"Next Wallpaper in {time_str}")
                app.progress_overlay_label.place(relx=0.5, rely=0.5, anchor="center")
                app.progress_overlay_label.config(bg=accent, fg=pal["button_fg"])
            except Exception:
                pass
        else:
            app.progress["value"] = 0
            app.progress_overlay_label.config(text="")
        app.root.after(1000, self.update_slideshow_status)

