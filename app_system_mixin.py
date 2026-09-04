"""System integration methods for FrogPaperApp (roadmap #7 Phase B step 2).

Extracted verbatim from app.py: system-tray actions, the toast
notification system, the Escape handler and the application quit path.

NOTE: _show_toast references ImageTk, which is never bound in that
scope - the resulting NameError is silently caught by the surrounding
`except Exception: pass`.  That is pre-existing app.py behaviour and is
preserved exactly here; do NOT add an ImageTk import to this module.

All methods are mixed into FrogPaperApp (see app.py), so behaviour is
unchanged: state still lives on self / self.app and every caller keeps
working untouched.
"""

import logging

import tkinter as tk

from app_runtime import (
    PYSTRAY_AVAILABLE,
    UI_EFFECTS_AVAILABLE,
    create_shadow_image,
    lerp_color,
    run_background,
    schedule_ui_update,
)
from app_themes import THEMES

from theme import COLOR_BLACK, COLOR_MID_GRAY, COLOR_WHITE  # shared color constants (migrated inline hex)

logger = logging.getLogger(__name__)



class FrogPaperAppSystemMixin:
    """Mixed into FrogPaperApp (see app.py); methods are verbatim."""

    def _get_app_icon_image(self):
        return self._tray_mgr._get_app_icon_image()


    def _build_tray_image(self):
        return self._tray_mgr._build_tray_image()




    def _start_tray(self):
        return self._tray_mgr._start_tray()




    def _stop_tray(self):
            """Stop the system tray icon — bulletproof version.

            Directly stops the pystray icon (with timeout) and nulls the ref.
            Called from both on_close and _quit_app.
            """
            if not PYSTRAY_AVAILABLE:
                return
            try:
                icon = getattr(self, '_tray_icon', None)
                if icon is not None:
                    # icon.stop() posts a message to the tray thread's hidden
                    # window and waits for the thread to join.  Use a timeout so
                    # we never hang here.
                    def _stop_with_timeout():
                        try:
                            icon.stop()
                        except Exception:
                            pass

                    t = run_background(_stop_with_timeout)
                    t.join(timeout=3)
                    self._tray_icon = None
            except Exception:
                pass




    def _toggle_minimize_to_tray(self, icon=None, item=None):
        return self._tray_mgr._toggle_minimize_to_tray(icon, item)




    def _tray_restore(self, icon=None, item=None):
        return self._tray_mgr._tray_restore(icon, item)




    def _tray_prev_wallpaper(self, icon=None, item=None):
        return self._tray_mgr._tray_prev_wallpaper(icon, item)




    def _tray_next_wallpaper(self, icon=None, item=None):
        return self._tray_mgr._tray_next_wallpaper(icon, item)




    def _tray_pause_slideshow(self, icon=None, item=None):
        return self._tray_mgr._tray_pause_slideshow(icon, item)


    def _tray_toggle_slideshow(self, icon=None, item=None):
        return self._tray_mgr._tray_toggle_slideshow(icon, item)


    def _tray_stop_slideshow(self, icon=None, item=None):
        return self._tray_mgr._tray_stop_slideshow(icon, item)


    def _tray_open_gallery(self, icon=None, item=None):
        return self._tray_mgr._tray_open_gallery(icon, item)


    def _tray_open_folder(self, icon=None, item=None):
        return self._tray_mgr._tray_open_folder(icon, item)


    def _tray_generate_prompt(self, icon=None, item=None):
        return self._tray_mgr._tray_generate_prompt(icon, item)


    def _tray_open_settings(self, icon=None, item=None):
        return self._tray_mgr._tray_open_settings(icon, item)

    def _tray_show_about(self, icon=None, item=None):
        return self._tray_mgr._tray_show_about(icon, item)

    def _tray_show_tutorials(self, icon=None, item=None):
        """Show tutorial selection menu from tray (marshaled to the main thread)."""
        schedule_ui_update(self._tutorial_mgr._show_tutorial_menu)
    
    def _show_first_run_prompt(self):
        """Show a prompt to start the first-run tutorial."""
        if self._dialog.ask(
            "Welcome to FrogPaper! 🐸",
            "Would you like to take a quick 5-minute tour to learn the basics?"
        ):
            self._tutorial_mgr.start_tutorial("quick_start")
        else:
            self._tutorial_mgr.mark_first_run_completed()
    
    def _show_tutorial_menu(self):
        """Show the tutorial selection menu from the main app button."""
        self._tutorial_mgr._show_tutorial_menu()


    def _tray_random_wallpaper(self, icon=None, item=None):
        return self._tray_mgr._tray_random_wallpaper(icon, item)


    def _restore_window(self):
        return self._tray_mgr._restore_window()




    def _tray_exit(self, icon=None, item=None):
        return self._tray_mgr._tray_exit(icon, item)


    def _show_toast(self, message, duration=3000, message_type="info"):
        """Show a toast notification message with glassmorphism and shadow."""
        if self._toast_frame is None:
            self._init_toast_system()

        # Theme-aware colors
        pal = THEMES.get(self.current_theme_name, THEMES["darkforest"])
        toast_bg = pal.get("panel2", "#2a2a3e")
        toast_fg = pal.get("text", COLOR_WHITE)
        muted_fg = pal.get("muted", COLOR_MID_GRAY)

        # Color based on message type
        colors = {
            "info": pal.get("accent", "#4a90e2"),
            "success": pal.get("success_color", "#2ecc71"),
            "warning": pal.get("warning_color", "#f39c12"),
            "error": pal.get("error_color", "#e74c3c")
        }
        bg_color = colors.get(message_type, pal.get("accent", "#4a90e2"))

        # Shadow frame behind the toast
        toast_shadow = tk.Frame(self._toast_frame, bg="", relief="flat", bd=0)
        toast_shadow.pack(side="bottom", fill="x", padx=20, pady=(0, 4))

        # Glassmorphism-style toast
        toast = tk.Frame(toast_shadow, bg=toast_bg, relief="flat", bd=0,
                         highlightbackground=pal.get("border_color", "#333"), highlightthickness=1)
        toast.pack(side="bottom", fill="x", padx=0, pady=0)

        # Add shadow image if ui_effects is available
        if UI_EFFECTS_AVAILABLE:
            try:
                toast_shadow.update_idletasks()
                tw = max(toast_shadow.winfo_width(), 320)
                shadow_img = create_shadow_image(
                    tw, 50, shadow_color=COLOR_BLACK,
                    offset_x=0, offset_y=3, blur_radius=12,
                    corner_radius=10, opacity=0.4
                )
                shadow_photo = ImageTk.PhotoImage(shadow_img)
                shadow_canvas = tk.Canvas(toast_shadow, highlightthickness=0, bd=0,
                                         height=shadow_img.height)
                shadow_canvas.create_image(0, 0, anchor="nw", image=shadow_photo)
                shadow_canvas.image = shadow_photo
                shadow_canvas.pack(side="bottom", fill="x")
                toast.pack(in_=shadow_canvas, side="bottom", fill="x", padx=2, pady=0)
            except Exception:
                pass

        # Left accent bar
        accent = tk.Frame(toast, bg=bg_color, width=4)
        accent.pack(side="left", fill="y")

        # Message label
        label = tk.Label(
            toast,
            text=message,
            bg=toast_bg,
            fg=toast_fg,
            font=self.smallfont,
            padx=15,
            pady=8,
            anchor="w"
        )
        label.pack(side="left", fill="both", expand=True)

        # Close button
        close_btn = tk.Label(
            toast,
            text="✕",
            bg=toast_bg,
            fg=muted_fg,
            font=self.tinyfont,
            padx=8,
            pady=8,
            cursor="hand2"
        )
        close_btn.pack(side="right")
        close_btn.bind("<Button-1>", lambda e: self._dismiss_toast(toast))

        # Auto-dismiss after duration
        self.root.after(duration, lambda: self._dismiss_toast(toast))

    def _switch_to_tab(self, tab_name):
        """Switch to a specific tab by name."""
        try:
            if tab_name == "gallery":
                self.notebook.select(self.gallery_tab)
            elif tab_name == "settings":
                self._open_settings_window()
        except Exception:
            pass

    def _handle_escape(self):
        """Handle Escape key - close settings or show toast."""
        if hasattr(self, "_settings_win") and self._settings_win and self._settings_win.winfo_exists():
            self._settings_win.destroy()
        else:
            self._show_toast("Press Ctrl+G for Gallery, Ctrl+S for Settings, Ctrl+N to Generate", message_type="info")

    def _init_toast_system(self):
        """Initialize the toast notification container."""
        self._toast_frame = tk.Frame(self.root, bg="")
        self._toast_frame.place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-10)
        self._toast_frame.lift()

        # Set transparent bg so toasts float over content
        try:
            self._toast_frame.configure(bg="")
        except Exception:
            pass

    def _dismiss_toast(self, toast):
        """Dismiss a toast notification with smooth fade-out animation."""
        try:
            # Animate opacity fade-out over ~200ms (10 steps x 20ms)
            def _fade_step(widget, step=0, max_steps=10):
                if step >= max_steps or not widget.winfo_exists():
                    try:
                        widget.destroy()
                    except Exception:
                        pass
                    return
                try:
                    # Simulate fade by blending fg toward bg
                    alpha = 1.0 - (step / max_steps)
                    widget.configure(bg=self._blend_alpha(widget.cget("bg"), COLOR_BLACK, alpha * 0.3 + 0.7))
                except Exception:
                    pass
                self.root.after(20, lambda: _fade_step(widget, step + 1, max_steps))
            # Also try to destroy the shadow parent
            parent = toast.master
            _fade_step(toast)
            self.root.after(250, lambda: self._safe_destroy(parent))
        except Exception:
            pass

    def _blend_alpha(self, fg_hex, bg_hex, alpha):
        """Blend fg over bg with alpha. Fallback for toast fade."""
        if not UI_EFFECTS_AVAILABLE:
            return fg_hex
        try:
            return lerp_color(fg_hex, bg_hex, 1.0 - alpha)
        except Exception:
            return fg_hex

    def _safe_destroy(self, widget):
        """Safely destroy a widget, ignoring errors."""
        try:
            if widget and widget.winfo_exists():
                widget.destroy()
        except Exception:
            pass


    def _quit_app(self):

            """Fully quit the application (used by tray exit)."""

            self._stop_fullscreen_watcher()
            self.slideshow.stop()

            self._stop_tray()

            self._shutdown_db()
            
            # Shutdown thread manager
            from thread_manager import shutdown_thread_manager
            shutdown_thread_manager()

            try:
                self.root.destroy()
            except Exception:
                pass

            # Force-kill the process so non-daemon threads (tray) cannot keep it alive.
            # sys.exit() only raises SystemExit in the calling thread; the tray
            # thread (daemon=False) would keep the process running.
            import os
            os._exit(0)
