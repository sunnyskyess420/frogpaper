import tkinter as tk
import logging
import sys
import threading
import random

try:
    import pystray
except ImportError:
    pystray = None

from PIL import Image

from utils import get_app_dir, get_bundle_dir


logger = logging.getLogger(__name__)


class TrayManager:
    """System tray icon and menu management."""

    def __init__(self, app):
        self.app = app
    def _build_tray_image(self) -> "Image.Image":
            """Drawn fallback frog icon — rendered at 256 px then downscaled for crispness."""
            app = self.app
            from PIL import Image, ImageDraw, ImageFilter
            import math

            S = 256  # render size; downscaled to 64 at the end

            img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            # ── Background circle: deep forest gradient via two-pass ellipse ──
            for i in range(S // 2, 0, -1):
                t = i / (S // 2)
                r = int(10 + 20 * t)
                g = int(22 + 38 * t)
                b = int(10 + 18 * t)
                draw.ellipse([S // 2 - i, S // 2 - i, S // 2 + i, S // 2 + i],
                             fill=(r, g, b, 255))

            # outer ring
            draw.ellipse([4, 4, S - 4, S - 4], outline="#4ade80", width=6)
            draw.ellipse([10, 10, S - 10, S - 10], outline="#166534", width=2)

            # ── Wallpaper monitor (bottom portion) ───────────────────────────
            mx, my, mw, mh = 44, 148, 168, 90
            # screen body
            draw.rounded_rectangle([mx, my, mx + mw, my + mh], radius=10,
                                   fill="#0f172a", outline="#334155", width=3)
            # screen gradient (purple→teal wallpaper)
            for i in range(mh - 14):
                t = i / max(mh - 14, 1)
                r = int(88 - 40 * t)
                g = int(28 + 60 * t)
                b = int(120 + 60 * t)
                draw.rectangle([mx + 8, my + 7 + i, mx + mw - 8, my + 8 + i],
                               fill=(r, g, b, 230))
            # tiny star on wallpaper
            for sx, sy in [(mx + 40, my + 30), (mx + 110, my + 20), (mx + 80, my + 50)]:
                draw.regular_polygon((sx, sy, 4), 4, rotation=45, fill="#fde68a")
            # monitor stand
            draw.rectangle([mx + mw // 2 - 8, my + mh, mx + mw // 2 + 8, my + mh + 14],
                           fill="#334155")
            draw.rectangle([mx + mw // 2 - 22, my + mh + 12, mx + mw // 2 + 22, my + mh + 18],
                           fill="#475569")

            # ── Frog body ────────────────────────────────────────────────────
            # main body (rounded, sitting on monitor area)
            body_col   = "#22c55e"
            body_dark  = "#15803d"
            body_light = "#4ade80"

            # belly
            draw.ellipse([72, 80, 184, 172], fill=body_col, outline=body_dark, width=3)
            # lighter belly patch
            draw.ellipse([90, 104, 166, 168], fill="#86efac")

            # left eye dome
            draw.ellipse([54, 44, 102, 92], fill=body_col, outline=body_dark, width=3)
            # right eye dome
            draw.ellipse([154, 44, 202, 92], fill=body_col, outline=body_dark, width=3)

            # left eyeball
            draw.ellipse([60, 50, 96, 86], fill="white")
            draw.ellipse([68, 58, 90, 80], fill="#111827")
            draw.ellipse([82, 60, 90, 68], fill="white")  # catchlight

            # right eyeball
            draw.ellipse([160, 50, 196, 86], fill="white")
            draw.ellipse([168, 58, 190, 80], fill="#111827")
            draw.ellipse([182, 60, 190, 68], fill="white")

            # nostrils
            draw.ellipse([110, 108, 118, 116], fill=body_dark)
            draw.ellipse([138, 108, 146, 116], fill=body_dark)

            # smile
            draw.arc([94, 118, 162, 158], start=15, end=165, fill=body_dark, width=4)

            # ── Subtle AI sparkle top-right ───────────────────────────────────
            for sx, sy, sr in [(196, 36, 6), (214, 52, 4), (208, 24, 3)]:
                draw.regular_polygon((sx, sy, sr), 4, rotation=45, fill="#fbbf24")

            # ── Downscale to 64 for crispness ────────────────────────────────
            img = img.resize((64, 64), Image.Resampling.LANCZOS)
            return img


    def _get_app_icon_image(self) -> "Image.Image":
            """Return a PIL Image for the app icon.

            Tries FrogPaperLogo.png first; falls back to the drawn frog.
            This is the single canonical icon used for both the tray and the
            window/taskbar iconphoto.
            """
            app = self.app
            try:
                from PIL import Image
                # Check app dir first (next to EXE or beside script),
                # then bundle dir (inside PyInstaller temp extraction).
                icon_p = get_app_dir() / "FrogPaperLogo.png"
                if not icon_p.exists():
                    icon_p = get_bundle_dir() / "FrogPaperLogo.png"
                if icon_p.exists():
                    img = Image.open(icon_p).convert("RGBA")
                    return img
            except Exception:
                pass
            return app._build_tray_image()


    def _restore_window(self):

            # deiconify handles both iconic and withdrawn states
            app = self.app
            app.root.deiconify()

            app.root.state("normal")

            app.root.lift()

            app.root.focus_force()

            # Do NOT stop the tray here — stopping and restarting pystray
            # creates duplicate hidden windows on Windows, causing extra
            # taskbar entries.  The tray stays alive and is only stopped on
            # actual app quit (_tray_exit).
            # app._stop_tray()  # <-- removed


    def _start_tray(self):
            """Start the system tray icon. Returns True if successful."""
            app = self.app
            if not app.PYSTRAY_AVAILABLE:
                logger.warning("pystray not available, skipping tray icon")
                return False

            if hasattr(app, '_tray_icon') and app._tray_icon:
                return True  # Tray already running
            
            try:
                logger.info("Starting tray icon...")
                menu = pystray.Menu(
                    pystray.MenuItem("Open FrogPaper", app._tray_restore, default=True),
                    pystray.MenuItem("Open Folder", app._tray_open_folder),
                    pystray.MenuItem("Settings", app._tray_open_settings),
                    pystray.Menu.SEPARATOR,
                    pystray.MenuItem("⏩ Next Wallpaper", app._tray_next_wallpaper),
                    pystray.MenuItem("⏪ Previous Wallpaper", app._tray_prev_wallpaper),
                    pystray.MenuItem("🎲 Random Wallpaper", app._tray_random_wallpaper),
                    pystray.Menu.SEPARATOR,
                    pystray.MenuItem(
                        lambda item: "Start Slideshow" if not getattr(app.slideshow, "running", False) else (
                            "Resume Slideshow" if getattr(app.slideshow, "paused", False) else "Pause Slideshow"
                        ),
                        app._tray_toggle_slideshow,
                    ),
                    pystray.MenuItem(
                        "Stop Slideshow",
                        app._tray_stop_slideshow,
                        visible=lambda item: getattr(app.slideshow, "running", False),
                    ),
                    pystray.Menu.SEPARATOR,
                    pystray.MenuItem("About FrogPaper", app._tray_show_about),
                    pystray.MenuItem("Quit FrogPaper", app._tray_exit),
                )
                
                # Create tray icon using shared canonical icon
                icon_image = app._get_app_icon_image()
                logger.info(f"Icon image loaded: {icon_image is not None}")
                app._tray_icon = pystray.Icon(
                    "FrogPaper",
                    icon=icon_image,
                    menu=menu
                )
                
                # Run in a background thread to avoid blocking Tkinter
                # Must be non-daemon to keep tray icon alive when main window closes
                import threading

                # On Windows, pystray creates a hidden message window that
                # can appear as an extra taskbar entry.  We patch the
                # _win32 backend to apply WS_EX_TOOLWINDOW so it stays
                # out of the taskbar.
                def _run_tray_hidden():
                    if sys.platform == "win32":
                        import ctypes
                        from ctypes import wintypes
                        user32 = ctypes.windll.user32
                        GWL_EXSTYLE = -20
                        WS_EX_TOOLWINDOW = 0x00000080
                        EnumWindows = user32.EnumWindows
                        EnumWindowsProc = ctypes.WINFUNCTYPE(
                            wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
                        GetWindowTextW = user32.GetWindowTextW
                        GetWindowTextLengthW = user32.GetWindowTextLengthW
                        SetWindowLongW = user32.SetWindowLongW

                        def _hide_from_taskbar(hwnd, _lparam):
                            length = GetWindowTextLengthW(hwnd) + 1
                            buf = ctypes.create_unicode_buffer(length)
                            GetWindowTextW(hwnd, buf, length)
                            # pystray names its hidden window "pystray_..."
                            if "pystray" in buf.value.lower():
                                ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                                user32.SetWindowLongW(
                                    hwnd, GWL_EXSTYLE,
                                    ex_style | WS_EX_TOOLWINDOW)
                            return True

                        # Wait briefly for the window to be created, then hide it
                        import time
                        time.sleep(0.3)
                        EnumWindows(EnumWindowsProc(_hide_from_taskbar), 0)

                    app._tray_icon.run()

                tray_thread = threading.Thread(target=_run_tray_hidden, daemon=True)
                tray_thread.start()
                logger.info("Tray icon started successfully")
                return True
            except Exception as e:
                logger.error(f"Error starting tray: {e}")
                import traceback
                traceback.print_exc()
                return False


    def _stop_tray(self):
            """Stop the system tray icon."""
            app = self.app
            if not app.PYSTRAY_AVAILABLE:
                return
            
            try:
                icon = getattr(app, '_tray_icon', None)
                if icon is not None:
                    app._tray_icon = None
                    stop_done = threading.Event()
                    def _do_stop():
                        try:
                            icon.stop()
                        except Exception:
                            pass
                        finally:
                            stop_done.set()
                    t = threading.Thread(target=_do_stop, daemon=True)
                    t.start()
                    stop_done.wait(timeout=3)
            except Exception as e:
                logger.error(f"Error stopping tray: {e}")


    def _toggle_minimize_to_tray(self, icon=None, item=None):
            """Toggle minimize to tray setting from tray menu."""
            app = self.app
            app.minimize_to_tray_var.set(not app.minimize_to_tray_var.get())
            app._on_minimize_to_tray_changed()


    def _tray_exit(self, icon=None, item=None):

            app = self.app
            app._stop_tray()

            try:
                app.root.after(0, app._quit_app)
            except (RuntimeError, tk.TclError):
                # Main loop already exited — force quit
                try:
                    app.root.destroy()
                except Exception:
                    pass
                import os
                os._exit(0)


    def _tray_generate_prompt(self, icon=None, item=None):
            """Restore window and generate an image."""
            app = self.app
            app.root.after(0, app._restore_window)
            app.root.after(100, app.generate_image)


    def _tray_next_wallpaper(self, icon=None, item=None):

            app = self.app
            app.root.after(0, app.advance_slideshow)


    def _tray_open_folder(self, icon=None, item=None):
            """Open the wallpapers folder in system file explorer (same as gallery header 'Open Folder' button)."""
            app = self.app
            app.root.after(0, app._open_wallpapers_folder)


    def _tray_open_settings(self, icon=None, item=None):
            """Restore window and open Settings dialog."""
            app = self.app
            app.root.after(0, lambda: self._restore_window_and_open_settings())

    def _restore_window_and_open_settings(self):
            """Restore the window and then open Settings dialog."""
            self._restore_window()
            self.app._open_settings_window()

    def _tray_show_about(self, icon=None, item=None):
            """Restore window and show About dialog."""
            app = self.app
            app.root.after(0, lambda: self._restore_window_and_show_about())

    def _restore_window_and_show_about(self):
            """Restore the window and then show About dialog."""
            self._restore_window()
            self.app._show_about_popup()


    def _tray_pause_slideshow(self, icon=None, item=None):

            app = self.app
            app.root.after(0, app.slideshow_pause_click)


    def _tray_prev_wallpaper(self, icon=None, item=None):

            app = self.app
            app.root.after(0, app.slideshow_prev_now)


    def _tray_random_wallpaper(self, icon=None, item=None):
            """Set a random wallpaper from the gallery without starting the slideshow."""
            app = self.app
            def _do():
                try:
                    candidates = app.slideshow.candidates(
                        source=app.slideshow._active_source(),
                        order="random",
                        skip_duplicates=False,
                    )
                    if not candidates:
                        app.status_var.set("Random wallpaper: no images found.")
                        return
                    import random as _random
                    chosen = _random.choice(candidates)
                    ok = set_wallpaper(chosen)
                    app.status_var.set(f"Random wallpaper: {chosen.name}" if ok else "Random wallpaper: set failed.")
                    if ok:
                        app.slideshow.reset_timer()
                except Exception as e:
                    app.status_var.set(f"Random wallpaper error: {e}")
            app.root.after(0, _do)


    def _tray_restore(self, icon=None, item=None):

            app = self.app
            app.root.after(0, app._restore_window)


    def _tray_stop_slideshow(self, icon=None, item=None):
            app = self.app
            app.root.after(0, app.slideshow.stop)


    def _tray_toggle_slideshow(self, icon=None, item=None):
            """Start, pause, or resume slideshow depending on current state."""
            app = self.app
            def _do():
                if not app.slideshow.running:
                    app.slideshow.start()
                elif app.slideshow.paused:
                    app.slideshow.resume()
                else:
                    app.slideshow.pause()
            app.root.after(0, _do)
