"""
Redesigned settings page with sidebar navigation and card-based layout.
Provides a polished, premium settings experience.
"""

import tkinter as tk
import logging
import webbrowser
import re

from tkinter import ttk
from datetime import datetime
from utils import load_config, save_config, get_huggingface_token

# Pinned Dropdown Options feature (v1.3.0 - Favorite Items)
try:
    from pinned_dropdowns import (
        init_pinned_manager,
        get_manager,
        build_pinned_settings_ui,
    )
    PINNED_AVAILABLE = True
except ImportError:
    PINNED_AVAILABLE = False

from settings_components import (
    StatusBadge,
    SettingRow,
    SettingCard,
    ExpandableSection,
    HelpResourceCard,
    SidebarNav,
    CloudProviderCard
)

logger = logging.getLogger(__name__)

# Status color mappings exposed for app.py
STATUS_COLORS = {
    "connected": "#22c55e",
    "not_connected": "#6b7280",
    "error": "#ef4444",
    "success": "#22c55e",
    "warning": "#f59e0b",
    "info": "#3b82f6"
}

# Cloud provider UX configuration
CLOUD_PROVIDER_UX = {
    "google_drive": {
        "display_name": "Google Drive",
        "id_var_attr": "google_client_id_var",
        "secret_var_attr": "google_client_secret_var",
        "id_label": "Client ID",
        "secret_label": "Client Secret",
        "setup_url": "https://console.cloud.google.com/apis/credentials",
        "setup_steps": [
            "Go to https://console.cloud.google.com and create a project (or select existing).",
            'Enable the "Google Drive API" under APIs & Services > Library.',
            'Go to APIs & Services > OAuth consent screen and configure it (select "External" user type, fill in app name and your email, and save).',
            'While the app is in "Testing" mode, go to OAuth consent screen > Audience, click "Add Users", and add the Google account email you will sign in with. (This step is not needed once the app is published to Production.)',
            "Go to APIs & Services > Credentials > Create Credentials > OAuth client ID.",
            'Select "Desktop app" as the application type, give it a name, and click Create.',
            "Copy the Client ID and Client Secret into the fields above.",
        ],
        "icon_char": "G",
        "cloud_url": "https://drive.google.com/drive/my-drive",
    },
    "onedrive": {
        "display_name": "OneDrive",
        "id_var_attr": "onedrive_client_id_var",
        "secret_var_attr": "onedrive_client_secret_var",
        "id_label": "Client ID",
        "secret_label": "Client Secret",
        "setup_url": "https://developer.microsoft.com/en-us/microsoft-365/dev-program",
        "setup_steps": [
            "Go to https://developer.microsoft.com/en-us/microsoft-365/dev-program and join the FREE M365 Developer Program.",
            "This gives you an Azure directory (needed for personal MS accounts like hotmail.com / outlook.com).",
            "After joining, go to https://portal.azure.com > App registrations > New registration.",
            'Name it "FrogPaper", select "Accounts in any organizational directory and personal Microsoft accounts".',
            "Go to API permissions > Add a permission > Microsoft Graph > Delegated permissions. Search for and add \"Files.ReadWrite\".",
            'Select "Mobile and desktop applications" as the platform (NOT "Web"). No redirect URI is needed.',
            "Go to Certificates & secrets > New client secret. Copy the Value (NOT the Secret ID).",
            "Copy the Application (client) ID and the secret Value into the fields above.",
        ],
        "icon_char": "O",
        "cloud_url": "https://onedrive.live.com",
    },
    "dropbox": {
        "display_name": "Dropbox",
        "id_var_attr": "dropbox_app_key_var",
        "secret_var_attr": "dropbox_app_secret_var",
        "id_label": "App Key",
        "secret_label": "App Secret",
        "setup_url": "https://www.dropbox.com/developers/apps",
        "setup_steps": [
            "Go to https://www.dropbox.com/developers/apps and click \"Create app\".",
            'Choose "Scoped access" then "Full Dropbox" as the access type. Name it "FrogPaper".',
            "No redirect URI is needed — FrogPaper uses the copy-paste auth code flow.",
            "Go to the Permissions tab, enable files.content.write and files.content.read, then click Submit.",
            "Copy the App key and App secret (from the Settings tab) into the fields above.",
        ],
        "icon_char": "D",
        "cloud_url": "https://www.dropbox.com/home",
    },
}


def _darken(hex_color, amount):
    """Darken a hex color by amount (0-255). Amount can be negative to lighten."""
    try:
        hex_color = hex_color.lstrip("#")
        r = max(0, min(255, int(hex_color[0:2], 16) - amount))
        g = max(0, min(255, int(hex_color[2:4], 16) - amount))
        b = max(0, min(255, int(hex_color[4:6], 16) - amount))
        return f"#{r:02x}{g:02x}{b:02x}"
    except (ValueError, IndexError):
        return hex_color


def _compute_sidebar_bg(pal):
    """Compute a sidebar background that is distinct from the main bg.
    
    For dark themes: sidebar is slightly lighter than bg (not darker).
    For light themes: sidebar is slightly darker than bg.
    Ensures the sidebar is always visually distinct from the content area.
    """
    bg = pal.get("bg", "#111827")
    panel = pal.get("panel", "#1f2937")
    
    try:
        bg_hex = bg.lstrip("#")
        r, g, b = int(bg_hex[0:2], 16), int(bg_hex[2:4], 16), int(bg_hex[4:6], 16)
        # Perceived brightness
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        
        if luminance < 0.15:
            # Very dark theme: use panel color (which is lighter) as sidebar
            return panel
        elif luminance < 0.5:
            # Dark theme: blend bg toward panel
            return _blend_colors(bg, panel, 0.4)
        else:
            # Light theme: darken bg slightly toward panel
            return _darken(bg, 15)
    except (ValueError, IndexError):
        return _darken(bg, 15)


def _blend_colors(c1, c2, t):
    """Linearly blend two hex colors. t=0 gives c1, t=1 gives c2."""
    try:
        c1 = c1.lstrip("#")
        c2 = c2.lstrip("#")
        r = int(int(c1[0:2], 16) * (1 - t) + int(c2[0:2], 16) * t)
        g = int(int(c1[2:4], 16) * (1 - t) + int(c2[2:4], 16) * t)
        b = int(int(c1[4:6], 16) * (1 - t) + int(c2[4:6], 16) * t)
        return f"#{max(0,min(255,r)):02x}{max(0,min(255,g)):02x}{max(0,min(255,b)):02x}"
    except (ValueError, IndexError):
        return c1


class SettingsTab:
    """Redesigned settings tab with sidebar navigation and card-based layout."""

    def __init__(self, app):
        self.app = app
        self._current_category = "general"
        self._category_frames = {}
        self._dirty = False
        self.sidebar_nav = None
        # References to top-level tk frames so we can re-theme the popup
        self._settings_main_container = None
        self._settings_body_container = None
        self._settings_content_area = None
        self._settings_sep = None
        self._settings_save_bar = None
        # Live registry of SettingCard / SettingRow / ExpandableSection /
        # HelpResourceCard / CloudProviderCard instances built inside the
        # popup.  Each entry exposes an ``update_theme(pal)`` method so that
        # ``_retheme_settings_popup`` can repaint the cards after the user
        # switches themes while the settings popup is open.  Without this
        # the cards would stay frozen on the previous theme's colours
        # (often grey defaults) even after the neon cyber theme is applied.
        self._setting_components = []

    def _build_settings_tab(self, parent):
        """Build the complete settings page with sidebar navigation."""
        app = self.app
        self._category_frames = {}
        
        # Get theme palette (copy so we don't mutate the original)
        pal = dict(app.THEMES.get(getattr(app, "current_theme_name", "darkforest"), app.THEMES["darkforest"]))
        
        # Ensure keys expected by settings components exist
        pal["card_bg"] = _darken(pal.get("panel2", pal.get("panel", pal["bg"])), -8)
        pal["sidebar_bg"] = _compute_sidebar_bg(pal)
        
        # Main container
        main_container = tk.Frame(parent, bg=pal["bg"])
        main_container.pack(fill="both", expand=True)
        self._settings_main_container = main_container
        
        # Sticky save bar (packed bottom first so it stays pinned across full width)
        self._build_save_bar(main_container, pal)
        
        # Body container (fills remaining space above save bar)
        body_container = tk.Frame(main_container, bg=pal["bg"])
        body_container.pack(side="top", fill="both", expand=True)
        self._settings_body_container = body_container
        
        # Define navigation categories
        categories = [
            ("general", "General", "⚙"),
            ("generation", "Generation", "🎨"),
            ("appearance", "Appearance", "🖼"),
            ("startup", "Startup", "🚀"),
            ("slideshow", "Slideshow", "📺"),
            ("cloud", "Cloud & Backup", "☁"),
            ("advanced", "Advanced", "🔧"),
            ("help", "Help", "❓"),
        ]
        
        # Content area
        content_area = tk.Frame(body_container, bg=pal["bg"])
        self._settings_content_area = content_area
        
        # Scrollable content canvas
        canvas = tk.Canvas(content_area, highlightthickness=0, bg=pal["bg"])
        scroll = ttk.Scrollbar(content_area, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas, style="Inner.TFrame")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        _st_win = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(_st_win, width=e.width))
        canvas.configure(yscrollcommand=scroll.set)
        
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        
        # Mouse-wheel scrolling
        def _on_enter(event):
            app._hover_canvas = canvas
        def _on_leave(event):
            if app._hover_canvas is canvas:
                app._hover_canvas = None
        canvas.bind('<Enter>', _on_enter)
        canvas.bind('<Leave>', _on_leave)
        
        app.settings_canvas = canvas
        app.settings_inner = inner
        
        # Build all category frames inside inner
        self._build_general_category(inner, pal)
        self._build_generation_category(inner, pal)
        self._build_appearance_category(inner, pal)
        self._build_startup_category(inner, pal)
        self._build_slideshow_category(inner, pal)
        self._build_cloud_category(inner, pal)
        self._build_advanced_category(inner, pal)
        self._build_help_category(inner, pal)
        
        # Sidebar navigation callback
        def on_category_select(cat_id):
            self._switch_category(cat_id)
        
        sidebar = SidebarNav(body_container, categories, on_category_select, pal, width=220)
        self.sidebar_nav = sidebar
        
        # Visible separator line between sidebar and content
        sep = tk.Frame(body_container, bg=pal.get("border_color", "#374151"), width=1)
        sep.pack(side="left", fill="y")
        self._settings_sep = sep
        content_area.pack(side="left", fill="both", expand=True)
        
        # Show first category
        initial_category = self._current_category if self._current_category in self._category_frames else "general"
        self._switch_category(initial_category)
        if sidebar._selected_category != initial_category:
            sidebar.select_category(initial_category)

    def _switch_category(self, category_id):
        """Switch between category views."""
        # Hide all categories
        for cat_id, frame in list(self._category_frames.items()):
            try:
                if frame.winfo_exists():
                    frame.pack_forget()
            except tk.TclError:
                pass
        
        # Show selected category
        if category_id in self._category_frames:
            target_frame = self._category_frames[category_id]
            try:
                if target_frame.winfo_exists():
                    target_frame.pack(fill="both", expand=True, padx=16, pady=16)
            except tk.TclError:
                pass
        
        self._current_category = category_id
        
        # Reset scroll position to top
        if hasattr(self.app, 'settings_canvas') and self.app.settings_canvas:
            try:
                if self.app.settings_canvas.winfo_exists():
                    self.app.settings_canvas.yview_moveto(0)
            except tk.TclError:
                pass

    def _build_save_bar(self, parent, pal):
        """Build sticky save bar at bottom with dirty state indicator."""
        save_bar = tk.Frame(parent, bg=pal.get("card_bg", pal["bg"]), height=60)
        save_bar.pack(side="bottom", fill="x")
        self._settings_save_bar = save_bar
        self._save_bar_content = None  # will store the inner content frame
        self._save_bar_status_label = None

        # Separator - subtle gradient effect with double line
        tk.Frame(save_bar, bg=pal.get("border_color", "#374151"), height=1).pack(side="top", fill="x")
        sep_glow = tk.Frame(save_bar, bg=pal.get("accent", "#8b5cf6"), height=1)
        sep_glow.pack(side="top", fill="x")
        sep_glow.pack_forget()  # Only shown when dirty
        self._sep_glow = sep_glow

        # Content
        content = tk.Frame(save_bar, bg=pal.get("card_bg", pal["bg"]))
        content.pack(fill="x", padx=20, pady=12)
        self._save_bar_content = content

        # Status with dot indicator
        status_frame = tk.Frame(content, bg=pal.get("card_bg", pal["bg"]))
        status_frame.pack(side="left")
        self._save_bar_status_frame = status_frame

        self._status_dot = tk.Canvas(status_frame, width=8, height=8,
                                       bg=pal.get("card_bg", pal["bg"]),
                                       highlightthickness=0)
        self._status_dot.pack(side="left", padx=(0, 8))
        self._status_dot.create_oval(1, 1, 7, 7, fill="#22c55e", outline="", tags="dot")

        self.save_status_var = tk.StringVar(value="All changes saved")
        status_label = tk.Label(
            content,
            textvariable=self.save_status_var,
            font=("Segoe UI", 9),
            fg=pal.get("muted", "#9ca3af"),
            bg=pal.get("card_bg", pal["bg"])
        )
        status_label.pack(side="left")
        self._save_bar_status_label = status_label

        # Save button with hover binding
        save_btn = ttk.Button(content, text="Save Settings", command=self._on_save)
        save_btn.pack(side="right")

    def _on_save(self):
        """Handle save button click with visual confirmation."""
        self.app.save_settings()
        self._mark_saved()

    def _mark_dirty(self):
        """Mark settings as dirty (unsaved changes) with visual feedback."""
        self._dirty = True
        if not hasattr(self, 'save_status_var'):
            return
        self.save_status_var.set("Unsaved changes")
        # Show accent glow line
        try:
            self._sep_glow.pack(side="top", fill="x", before=self._sep_glow.master.winfo_children()[0])
        except Exception:
            pass
        # Change status dot to warning amber
        try:
            self._status_dot.delete("dot")
            self._status_dot.create_oval(1, 1, 7, 7, fill="#f59e0b", outline="", tags="dot")
        except Exception:
            pass

    def _mark_saved(self):
        """Mark settings as saved with visual feedback."""
        self._dirty = False
        if not hasattr(self, 'save_status_var'):
            return
        self.save_status_var.set("All changes saved")
        # Hide accent glow line
        try:
            self._sep_glow.pack_forget()
        except Exception:
            pass
        # Change status dot back to green
        try:
            self._status_dot.delete("dot")
            self._status_dot.create_oval(1, 1, 7, 7, fill="#22c55e", outline="", tags="dot")
        except Exception:
            pass

    def _retheme_settings_popup(self, pal):
        """Update the settings popup window's tk widgets to match *pal*.

        Called from ``App.apply_theme`` so that the sidebar, save bar, and
        container frames reflect the new theme instead of staying frozen on
        the colours they were created with.
        """
        bg = pal["bg"]
        card_bg = _darken(pal.get("panel2", pal.get("panel", bg)), -8)
        sidebar_bg = _compute_sidebar_bg(pal)
        border_color = pal.get("border_color", "#374151")
        accent = pal.get("accent", "#8b5cf6")
        muted = pal.get("muted", "#9ca3af")

        popup_pal = dict(pal)
        popup_pal["card_bg"] = card_bg
        popup_pal["sidebar_bg"] = sidebar_bg

        # ── Toplevel window background ──
        app = self.app
        if hasattr(app, "_settings_win") and app._settings_win:
            try:
                app._settings_win.configure(bg=bg)
            except (tk.TclError, AttributeError):
                pass

        # ── Main container ──
        w = self._settings_main_container
        if w:
            try:
                w.configure(bg=bg)
            except (tk.TclError, AttributeError):
                pass

        # ── Body container ──
        w = self._settings_body_container
        if w:
            try:
                w.configure(bg=bg)
            except (tk.TclError, AttributeError):
                pass

        # ── Content area (tk.Frame, not ttk) ──
        w = self._settings_content_area
        if w:
            try:
                w.configure(bg=bg)
            except (tk.TclError, AttributeError):
                pass

        # ── Separator line ──
        w = self._settings_sep
        if w:
            try:
                w.configure(bg=border_color)
            except (tk.TclError, AttributeError):
                pass

        # ── Sidebar navigation ──
        if self.sidebar_nav:
            try:
                self.sidebar_nav.update_theme(popup_pal)
            except Exception:
                pass

        # ── Save bar ──
        w = self._settings_save_bar
        if w:
            try:
                w.configure(bg=card_bg)
            except (tk.TclError, AttributeError):
                pass
            # Update the separator lines inside the save bar
            for child in w.winfo_children():
                try:
                    if isinstance(child, tk.Frame) and child.winfo_height() <= 2:
                        # This is one of the separator lines
                        if child == self._sep_glow:
                            child.configure(bg=accent)
                        else:
                            child.configure(bg=border_color)
                except (tk.TclError, AttributeError):
                    pass

        w = self._save_bar_content
        if w:
            try:
                w.configure(bg=card_bg)
            except (tk.TclError, AttributeError):
                pass

        w = getattr(self, '_save_bar_status_frame', None)
        if w:
            try:
                w.configure(bg=card_bg)
            except (tk.TclError, AttributeError):
                pass

        if hasattr(self, '_status_dot') and self._status_dot:
            try:
                self._status_dot.configure(bg=card_bg)
            except (tk.TclError, AttributeError):
                pass

        w = self._save_bar_status_label
        if w:
            try:
                w.configure(bg=card_bg, fg=muted)
            except (tk.TclError, AttributeError):
                pass

        # ── Walk the settings scroll-area tree ──
        #
        # The body of the settings popup is made of SettingCard /
        # SettingRow / ExpandableSection / HelpResourceCard /
        # CloudProviderCard instances.  Each of these captures its colours
        # at creation time and never updates them when the user switches
        # themes — so when the user opens Settings while a different theme
        # is active and then switches to e.g. "Neon Cyber — Dark", the
        # cards stay frozen on the previous theme's colours (often grey
        # defaults), producing the "grey instead of theme color" bug.
        #
        # Each component now tags its outer tk widget with
        # ``_fp_component = self`` so we can rediscover it here and call
        # its ``update_theme`` method.  When a widget is owned by a
        # component, we let the component repaint itself and DO NOT
        # recurse into its internals (the component knows about its own
        # accent bars, icons, borders, etc. and would conflict with a
        # generic repaint pass).  We only repaint "free-standing" widgets
        # that live directly inside the scroll area: category headers,
        # section labels, separator lines, and any other tk widgets the
        # settings builders added outside a card component.
        try:
            inner = getattr(self.app, "settings_inner", None)
            if inner is not None and inner.winfo_exists():
                # Colours used for free-standing widgets (those NOT
                # owned by a card component).
                page_bg = bg
                text_fg = pal.get("text", "#e5e7eb")
                entry_bg = pal.get("entrybg", bg)

                # Use a marker so we never recurse into the same
                # widget twice even if it gets re-packed during the
                # walk (some components re-pack their children when
                # update_theme runs).
                visited = set()

                def _repaint_free_standing(parent, current_bg):
                    """Walk the tree, repaint free-standing widgets, and
                    skip the internals of any tagged component (which
                    has its own update_theme that owns its internals)."""
                    try:
                        for child in parent.winfo_children():
                            try:
                                if not child.winfo_exists():
                                    continue
                                child_id = id(child)
                                if child_id in visited:
                                    continue
                                visited.add(child_id)

                                # 1) If this widget is the outer frame of
                                #    a SettingCard / SettingRow / etc,
                                #    let that component repaint itself
                                #    and DO NOT recurse into its body —
                                #    the component's update_theme already
                                #    handles its accent bar, borders,
                                #    icon, title, description, content
                                #    frame, and step labels.
                                comp = getattr(child, "_fp_component", None)
                                if comp is not None and hasattr(comp, "update_theme"):
                                    try:
                                        comp.update_theme(popup_pal)
                                    except Exception:
                                        pass
                                    continue  # do NOT recurse into the component

                                # 2) Free-standing widgets — repaint.
                                if isinstance(child, tk.Frame):
                                    # Detect 1-pixel separator lines
                                    try:
                                        h = int(child.cget("height"))
                                    except (tk.TclError, ValueError, TypeError):
                                        h = 0
                                    try:
                                        wd = int(child.cget("width"))
                                    except (tk.TclError, ValueError, TypeError):
                                        wd = 0
                                    try:
                                        ht = int(child.cget("highlightthickness"))
                                    except (tk.TclError, ValueError, TypeError):
                                        ht = 0

                                    if h == 1 and wd == 0:
                                        # Separator line
                                        child.configure(bg=border_color)
                                        _repaint_free_standing(child, border_color)
                                    elif ht > 0:
                                        # Standalone bordered card-like
                                        # frame (rare).  Use card_bg.
                                        child.configure(
                                            bg=card_bg,
                                            highlightbackground=border_color,
                                        )
                                        _repaint_free_standing(child, card_bg)
                                    else:
                                        # Plain container — inherit page bg
                                        try:
                                            child.configure(bg=current_bg)
                                        except tk.TclError:
                                            pass
                                        _repaint_free_standing(child, current_bg)
                                elif isinstance(child, tk.Label):
                                    try:
                                        font_info = child.cget("font")
                                        is_small = False
                                        if isinstance(font_info, tuple) and len(font_info) >= 2:
                                            try:
                                                is_small = abs(int(font_info[1])) <= 9
                                            except (ValueError, TypeError):
                                                pass
                                        cur_fg = child.cget("fg")
                                        # Preserve explicit accent / status
                                        # colours so we don't blow away
                                        # coloured icons or status badges.
                                        status_colors = {
                                            "#22c55e", "#ef4444", "#f59e0b",
                                            "#3b82f6", accent,
                                        }
                                        if cur_fg and cur_fg not in (
                                            muted, text_fg, "gray", "grey",
                                            "#888888", "#9ca3af",
                                        ) and cur_fg not in status_colors:
                                            new_fg = cur_fg
                                        else:
                                            new_fg = muted if is_small else text_fg
                                        child.configure(bg=current_bg, fg=new_fg)
                                    except tk.TclError:
                                        pass
                                elif isinstance(child, tk.Canvas):
                                    try:
                                        child.configure(bg=current_bg, highlightthickness=0)
                                    except tk.TclError:
                                        pass
                                elif isinstance(child, (tk.Checkbutton, tk.Radiobutton)):
                                    try:
                                        child.configure(
                                            bg=current_bg,
                                            fg=text_fg,
                                            selectcolor=entry_bg,
                                            activebackground=current_bg,
                                            activeforeground=text_fg,
                                        )
                                    except tk.TclError:
                                        pass
                                # Recurse into ttk containers as well so
                                # any nested tk children get repainted.
                                if isinstance(child, (ttk.Frame, ttk.LabelFrame)):
                                    _repaint_free_standing(child, current_bg)
                            except tk.TclError:
                                continue
                    except tk.TclError:
                        pass

                _repaint_free_standing(inner, page_bg)
        except Exception:
            pass

    # ================================================================
    # CATEGORY BUILDERS
    # ================================================================

    def _build_general_category(self, parent, pal):
        """Build General settings category."""
        app = self.app
        frame = tk.Frame(parent, bg=pal["bg"])
        self._category_frames["general"] = frame
        
        # Header
        header = tk.Label(frame, text="General", font=("Segoe UI", 18, "bold"),
                         fg=pal["text"], bg=pal["bg"], anchor="w")
        header.pack(fill="x", pady=20)
        
        # App Theme card
        theme_card = SettingCard(frame, "App Theme", 
                                "Choose your preferred color theme for FrogPaper.",
                                pal, pal.get("accent", "#8b5cf6"))
        
        config = load_config()
        app.theme_var = tk.StringVar(
            value=app.THEME_DISPLAY_NAMES.get(config.get("app_theme", "darkforest"), "Forest Green — Dark")
        )
        theme_combo = ttk.Combobox(
            theme_card.get_content(),
            textvariable=app.theme_var,
            values=list(app.THEME_DISPLAY_NAMES.values()),
            state="readonly",
            width=30
        )
        theme_combo.pack(fill="x", pady=8)
        theme_combo.bind("<<ComboboxSelected>>", lambda e: [app.on_theme_changed(), self._mark_dirty()])
        theme_combo.bind("<MouseWheel>", lambda e: "break")
        
        # Resolution card
        res_card = SettingCard(frame, "Wallpaper Resolution",
                               "Set the default resolution for generated wallpapers.",
                               pal, pal.get("accent", "#8b5cf6"))
        
        if not hasattr(app, 'dimension_preset_var'):
            app.dimension_preset_var = tk.StringVar(value="16:9 (1080p)")
        res_combo = ttk.Combobox(
            res_card.get_content(),
            textvariable=app.dimension_preset_var,
            values=list(app.DIMENSION_PRESETS.keys()),
            state="readonly",
            width=25
        )
        res_combo.pack(fill="x", pady=8)
        res_combo.bind("<<ComboboxSelected>>", lambda e: [self._on_dimension_preset_changed(), self._mark_dirty()])
        res_combo.bind("<MouseWheel>", lambda e: "break")

    def _build_generation_category(self, parent, pal):
        """Build Generation settings category."""
        app = self.app
        frame = tk.Frame(parent, bg=pal["bg"])
        self._category_frames["generation"] = frame
        
        header = tk.Label(frame, text="Generation", font=("Segoe UI", 18, "bold"),
                         fg=pal["text"], bg=pal["bg"], anchor="w")
        header.pack(fill="x", pady=20)
        
        # Provider card
        provider_card = SettingCard(frame, "AI Provider",
                                     "Select the AI service for generating wallpapers.",
                                     pal, pal.get("accent", "#8b5cf6"))
        
        saved_provider = load_config().get("provider", "Pollinations.ai (Free - No Key)")
        app.provider_var = tk.StringVar(value=saved_provider)
        provider_combo = ttk.Combobox(
            provider_card.get_content(),
            textvariable=app.provider_var,
            values=app.PROVIDER_OPTIONS,
            state="readonly",
            width=40
        )
        provider_combo.pack(fill="x", pady=8)
        provider_combo.bind("<<ComboboxSelected>>", lambda e: [self._on_provider_changed(), self._mark_dirty()])
        provider_combo.bind("<MouseWheel>", lambda e: "break")
        
        app.provider_desc_var = tk.StringVar(value="")
        desc_label = tk.Label(
            provider_card.get_content(),
            textvariable=app.provider_desc_var,
            font=("Segoe UI", 9),
            fg=pal["muted"],
            bg=pal["card_bg"],
            wraplength=600,
            justify="left"
        )
        desc_label.pack(fill="x", pady=8)
        self._update_provider_description()
        
        # API Token card (conditional)
        token_card = SettingCard(frame, "API Token",
                                 "Your Hugging Face token for paid models.",
                                 pal, pal.get("accent", "#8b5cf6"))
        app.token_card = token_card
        
        token_frame = tk.Frame(token_card.get_content(), bg=pal["card_bg"])
        token_frame.pack(fill="x", pady=8)
        
        app.token_var = tk.StringVar(value=get_huggingface_token())
        token_entry = ttk.Entry(token_frame, textvariable=app.token_var, width=40, show="*")
        token_entry.pack(side="left", fill="x", expand=True)
        app.token_entry = token_entry
        app.configure_entry_cursor(token_entry)
        token_entry.bind("<FocusOut>", lambda e: [self._on_token_changed(), self._mark_dirty()])
        
        token_btn_frame = tk.Frame(token_frame, bg=pal["card_bg"])
        token_btn_frame.pack(side="right", padx=8)
        
        app.token_toggle_btn = ttk.Button(token_btn_frame, text="Show", 
                                          command=lambda: [self.toggle_token_visibility(), self._mark_dirty()])
        app.token_toggle_btn.pack(side="left", padx=4)
        
        ttk.Button(token_btn_frame, text="Refresh", 
                  command=lambda: [self.refresh_token_status(), self._mark_dirty()]).pack(side="left")
        
        app.token_preview_var = tk.StringVar(value=self.format_token_preview())
        preview_label = tk.Label(
            token_card.get_content(),
            textvariable=app.token_preview_var,
            font=("Segoe UI", 9),
            fg=pal["muted"],
            bg=pal["card_bg"]
        )
        preview_label.pack(fill="x", pady=8)
        
        # Cloudflare card (conditional)
        cf_card = SettingCard(frame, "Cloudflare Workers AI",
                             "Free tier AI generation with Cloudflare account.",
                             pal, pal.get("accent", "#8b5cf6"))
        app.cloudflare_card = cf_card
        
        cf_frame = tk.Frame(cf_card.get_content(), bg=pal["card_bg"])
        cf_frame.pack(fill="x", pady=8)
        cf_frame.columnconfigure(1, weight=1)
        
        tk.Label(cf_frame, text="Token:", font=("Segoe UI", 10),
                fg=pal["text"], bg=pal["card_bg"]).grid(row=0, column=0, sticky="w", padx=8)
        saved_cf_token = load_config().get("cloudflare_token", "")
        app.cloudflare_token_var = tk.StringVar(value=saved_cf_token)
        cf_token_entry = ttk.Entry(cf_frame, textvariable=app.cloudflare_token_var, width=30, show="*")
        cf_token_entry.grid(row=0, column=1, sticky="ew")
        app.configure_entry_cursor(cf_token_entry)
        
        tk.Label(cf_frame, text="Account ID:", font=("Segoe UI", 10),
                fg=pal["text"], bg=pal["card_bg"]).grid(row=1, column=0, sticky="w", padx=8, pady=8)
        saved_cf_account_id = load_config().get("cloudflare_account_id", "")
        app.cloudflare_account_id_var = tk.StringVar(value=saved_cf_account_id)
        cf_id_entry = ttk.Entry(cf_frame, textvariable=app.cloudflare_account_id_var, width=30)
        cf_id_entry.grid(row=1, column=1, sticky="ew", pady=8)
        app.configure_entry_cursor(cf_id_entry)
        
        # Model card
        model_card = SettingCard(frame, "AI Model",
                                  "Select the specific AI model to use.",
                                  pal, pal.get("accent", "#8b5cf6"))
        
        saved_model_id = load_config().get("model_id", "flux")
        provider_info = app.PROVIDER_MODELS.get(saved_provider, app.PROVIDER_MODELS.get("Pollinations.ai (Free - No Key)", {}))
        provider_models = provider_info.get("options", [])
        provider_display_to_id = provider_info.get("display_to_id", {})
        provider_id_to_display = {v: k for k, v in provider_display_to_id.items()}
        initial_display = provider_id_to_display.get(saved_model_id, provider_models[0] if provider_models else "FLUX (Default)")
        
        app.model_choice_var = tk.StringVar(value=initial_display)
        model_combo = ttk.Combobox(
            model_card.get_content(),
            textvariable=app.model_choice_var,
            values=provider_models,
            state="readonly",
            width=40
        )
        model_combo.pack(fill="x", pady=8)
        app.model_choice_combo = model_combo
        model_combo.bind("<<ComboboxSelected>>", lambda e: [self._on_model_choice_changed(), self._mark_dirty()])
        model_combo.bind("<MouseWheel>", lambda e: "break")
        
        app.custom_model_var = tk.StringVar(value=saved_model_id if initial_display == "Custom..." else "")
        app.custom_model_entry = ttk.Entry(model_card.get_content(), textvariable=app.custom_model_var, width=58)
        app.configure_entry_cursor(app.custom_model_entry)
        if initial_display == "Custom...":
            app.custom_model_entry.pack(fill="x", pady=8)
        
        self._update_provider_visibility()

    def _build_appearance_category(self, parent, pal):
        """Build Appearance settings category."""
        app = self.app
        frame = tk.Frame(parent, bg=pal["bg"])
        self._category_frames["appearance"] = frame
        
        header = tk.Label(frame, text="Appearance", font=("Segoe UI", 18, "bold"),
                         fg=pal["text"], bg=pal["bg"], anchor="w")
        header.pack(fill="x", pady=20)
        
        # Wallpaper Output card
        output_card = SettingCard(frame, "Wallpaper Output",
                                  "Configure the format and quality of saved wallpapers.",
                                  pal, pal.get("accent", "#8b5cf6"))
        
        format_frame = tk.Frame(output_card.get_content(), bg=pal["card_bg"])
        format_frame.pack(fill="x", pady=8)
        
        if not hasattr(app, 'wallpaper_format_var'):
            app.wallpaper_format_var = tk.StringVar(value='PNG')
        if not hasattr(app, 'wallpaper_quality_var'):
            app.wallpaper_quality_var = tk.StringVar(value='High')
        
        tk.Label(format_frame, text="Format:", font=("Segoe UI", 10),
                fg=pal["text"], bg=pal["card_bg"]).pack(side="left")
        format_combo = ttk.Combobox(format_frame, textvariable=app.wallpaper_format_var,
                                    values=['PNG', 'JPEG', 'WebP'], state="readonly", width=12)
        format_combo.pack(side="left", padx=16)
        format_combo.bind("<<ComboboxSelected>>", lambda e: self._mark_dirty())
        format_combo.bind("<MouseWheel>", lambda e: "break")
        
        tk.Label(format_frame, text="Quality:", font=("Segoe UI", 10),
                fg=pal["text"], bg=pal["card_bg"]).pack(side="left")
        quality_combo = ttk.Combobox(format_frame, textvariable=app.wallpaper_quality_var,
                                     values=['Maximum', 'High', 'Medium', 'Low'], state="readonly", width=12)
        quality_combo.pack(side="left", padx=8)
        quality_combo.bind("<<ComboboxSelected>>", lambda e: self._mark_dirty())
        quality_combo.bind("<MouseWheel>", lambda e: "break")
        
        helper_label = tk.Label(
            output_card.get_content(),
            text="Lower quality = smaller file size, minimal visual difference at desktop size",
            font=("Segoe UI", 9),
            fg=pal["muted"],
            bg=pal["card_bg"],
            wraplength=600
        )
        helper_label.pack(fill="x", pady=8)

    def _build_startup_category(self, parent, pal):
        """Build Startup settings category."""
        app = self.app
        frame = tk.Frame(parent, bg=pal["bg"])
        self._category_frames["startup"] = frame
        
        header = tk.Label(frame, text="Startup", font=("Segoe UI", 18, "bold"),
                         fg=pal["text"], bg=pal["bg"], anchor="w")
        header.pack(fill="x", pady=20)
        
        # Run on Startup card
        startup_card = SettingCard(frame, "Run on Startup",
                                   "Configure how FrogPaper behaves when Windows starts.",
                                   pal, pal.get("accent", "#8b5cf6"))
        
        app.run_on_startup_var = tk.BooleanVar(value=app.run_on_startup_enabled)
        startup_check = tk.Checkbutton(
            startup_card.get_content(),
            text="Launch FrogPaper when Windows starts",
            variable=app.run_on_startup_var,
            font=("Segoe UI", 10),
            fg=pal["text"],
            bg=pal["card_bg"],
            selectcolor=pal.get("entrybg", pal["card_bg"]),
            activebackground=pal["card_bg"],
            activeforeground=pal["text"],
            command=lambda: [app._on_run_on_startup_changed(), self._mark_dirty()]
        )
        startup_check.pack(fill="x", pady=8, anchor="w")
        
        # Auto-generate card
        gen_card = SettingCard(frame, "Auto-Generate on Launch",
                               "Automatically generate a wallpaper when FrogPaper starts.",
                               pal, pal.get("accent", "#8b5cf6"))
        
        gen_check = tk.Checkbutton(
            gen_card.get_content(),
            text="Generate a fresh random wallpaper each launch",
            variable=app.auto_generate_on_startup_var,
            font=("Segoe UI", 10),
            fg=pal["text"],
            bg=pal["card_bg"],
            selectcolor=pal.get("entrybg", pal["card_bg"]),
            activebackground=pal["card_bg"],
            activeforeground=pal["text"],
            command=self._mark_dirty
        )
        gen_check.pack(fill="x", pady=8, anchor="w")
        
        # Startup subject
        subject_frame = tk.Frame(gen_card.get_content(), bg=pal["card_bg"])
        subject_frame.pack(fill="x", pady=8)
        
        tk.Label(subject_frame, text="Startup subject:", font=("Segoe UI", 10),
                fg=pal["text"], bg=pal["card_bg"]).pack(side="left")
        startup_subj_entry = ttk.Entry(subject_frame, textvariable=app.startup_subject_var, width=25)
        startup_subj_entry.pack(side="left", padx=8)
        app.configure_entry_cursor(startup_subj_entry)
        
        helper_label = tk.Label(
            gen_card.get_content(),
            text="Leave as 'frog' for classic frogs, or change to any subject you like",
            font=("Segoe UI", 9),
            fg=pal["muted"],
            bg=pal["card_bg"],
            wraplength=600
        )
        helper_label.pack(fill="x", pady=8)
        
        # Minimize to Tray card
        tray_card = SettingCard(frame, "System Tray",
                                "Control how FrogPaper behaves when minimized.",
                                pal, pal.get("accent", "#8b5cf6"))
        
        app.minimize_to_tray_var = tk.BooleanVar(value=app.minimize_to_tray_enabled)
        tray_check = tk.Checkbutton(
            tray_card.get_content(),
            text="Minimize to system tray instead of taskbar",
            variable=app.minimize_to_tray_var,
            font=("Segoe UI", 10),
            fg=pal["text"],
            bg=pal["card_bg"],
            selectcolor=pal.get("entrybg", pal["card_bg"]),
            activebackground=pal["card_bg"],
            activeforeground=pal["text"],
            command=lambda: [app._on_minimize_to_tray_changed(), self._mark_dirty()]
        )
        tray_check.pack(fill="x", pady=8, anchor="w")

    def _build_slideshow_category(self, parent, pal):
        """Build Slideshow settings category."""
        app = self.app
        frame = tk.Frame(parent, bg=pal["bg"])
        self._category_frames["slideshow"] = frame
        
        header = tk.Label(frame, text="Slideshow", font=("Segoe UI", 18, "bold"),
                         fg=pal["text"], bg=pal["bg"], anchor="w")
        header.pack(fill="x", pady=20)
        
        # Slideshow Control card
        control_card = SettingCard(frame, "Slideshow Control",
                                   "Enable and configure the in-app wallpaper slideshow.",
                                   pal, pal.get("accent", "#8b5cf6"))
        
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
        self.sync_slideshow_state()
        
        enable_check = tk.Checkbutton(
            control_card.get_content(),
            text="Enable in-app slideshow",
            variable=app.slideshow_enabled_var,
            font=("Segoe UI", 10),
            fg=pal["text"],
            bg=pal["card_bg"],
            selectcolor=pal.get("entrybg", pal["card_bg"]),
            activebackground=pal["card_bg"],
            activeforeground=pal["text"],
            command=lambda: [self.on_slideshow_toggle(), self._mark_dirty()]
        )
        enable_check.pack(fill="x", pady=8, anchor="w")
        
        # Interval slider
        interval_frame = tk.Frame(control_card.get_content(), bg=pal["card_bg"])
        interval_frame.pack(fill="x", pady=12)
        
        tk.Label(interval_frame, text="Interval:", font=("Segoe UI", 10),
                fg=pal["text"], bg=pal["card_bg"]).pack(side="left")
        
        if not hasattr(app, 'interval_display_var'):
            app.interval_display_var = tk.StringVar(value='60')
        interval_display = tk.Label(interval_frame, textvariable=app.interval_display_var,
                                   font=("Segoe UI", 10, "bold"), fg=pal.get("accent", "#8b5cf6"),
                                   bg=pal["card_bg"])
        interval_display.pack(side="right")
        
        def on_interval_change(value):
            val = int(float(value))
            app.slideshow_interval_var.set(str(val))
            app.interval_display_var.set(str(val))
            self._mark_dirty()
        
        app.interval_slider = ttk.Scale(control_card.get_content(), from_=1, to=60, 
                                       orient='horizontal', command=on_interval_change)
        try:
            initial_val = int(float(app.slideshow_interval_var.get()))
            app.interval_slider.set(max(1, min(60, initial_val)))
        except:
            app.interval_slider.set(60)
        app.interval_slider.pack(fill="x", pady=8)
        
        helper_label = tk.Label(
            control_card.get_content(),
            text="Adjust the slider to set how often wallpapers rotate (1-60 minutes)",
            font=("Segoe UI", 9),
            fg=pal["muted"],
            bg=pal["card_bg"]
        )
        helper_label.pack(fill="x", pady=4)
        
        # Source & Order card
        source_card = SettingCard(frame, "Source & Order",
                                  "Choose which wallpapers to show and in what order.",
                                  pal, pal.get("accent", "#8b5cf6"))
        
        source_frame = tk.Frame(source_card.get_content(), bg=pal["card_bg"])
        source_frame.pack(fill="x", pady=8)
        source_frame.columnconfigure(1, weight=1)
        
        tk.Label(source_frame, text="Source:", font=("Segoe UI", 10),
                fg=pal["text"], bg=pal["card_bg"]).grid(row=0, column=0, sticky="w", padx=8)
        source_combo = ttk.Combobox(source_frame, textvariable=app.slideshow_source_var,
                                    values=app.SLIDESHOW_SOURCE_DISPLAY, state='readonly', width=20)
        source_combo.grid(row=0, column=1, sticky="w")
        source_combo.bind("<<ComboboxSelected>>", self._mark_dirty)
        source_combo.bind("<MouseWheel>", lambda e: "break")
        
        tk.Label(source_frame, text="Order:", font=("Segoe UI", 10),
                fg=pal["text"], bg=pal["card_bg"]).grid(row=1, column=0, sticky="w", padx=8, pady=8)
        order_combo = ttk.Combobox(source_frame, textvariable=app.slideshow_order_var,
                                    values=['random', 'newest', 'oldest'], state='readonly', width=20)
        order_combo.grid(row=1, column=1, sticky="w", pady=8)
        order_combo.bind("<<ComboboxSelected>>", self._mark_dirty)
        order_combo.bind("<MouseWheel>", lambda e: "break")
        
        skip_check = tk.Checkbutton(
            source_card.get_content(),
            text="Skip duplicates (no repeat until all shown)",
            variable=app.slideshow_skip_duplicates_var,
            font=("Segoe UI", 10),
            fg=pal["text"],
            bg=pal["card_bg"],
            selectcolor=pal.get("entrybg", pal["card_bg"]),
            activebackground=pal["card_bg"],
            activeforeground=pal["text"],
            command=self._mark_dirty
        )
        skip_check.pack(fill="x", pady=12, anchor="w")

    def _build_cloud_category(self, parent, pal):
        """Build Cloud & Backup settings category."""
        app = self.app
        frame = tk.Frame(parent, bg=pal["bg"])
        self._category_frames["cloud"] = frame
        
        header = tk.Label(frame, text="Cloud & Backup", font=("Segoe UI", 18, "bold"),
                         fg=pal["text"], bg=pal["bg"], anchor="w")
        header.pack(fill="x", pady=20)
        
        # Cloud Providers section
        providers_header = tk.Label(frame, text="Cloud Providers", font=("Segoe UI", 14, "bold"),
                                   fg=pal["text"], bg=pal["bg"], anchor="w")
        providers_header.pack(fill="x", pady=12)
        
        providers_desc = tk.Label(frame, text="Connect cloud storage for backup and sync.",
                                 font=("Segoe UI", 10), fg=pal["muted"], bg=pal["bg"], anchor="w")
        providers_desc.pack(fill="x", pady=12)
        
        # Build cloud provider cards
        self._cloud_provider_cards = {}
        for prov_key, ux_info in CLOUD_PROVIDER_UX.items():
            card = CloudProviderCard(frame, prov_key, ux_info, pal, app)
            self._cloud_provider_cards[prov_key] = card
        
        # Sync Settings card
        sync_card = SettingCard(frame, "Sync Settings",
                               "Configure automatic backup and sync behavior.",
                               pal, pal.get("accent", "#8b5cf6"))
        
        app.auto_backup_var = tk.BooleanVar(value=load_config().get("auto_backup_enabled", False))
        
        backup_check = tk.Checkbutton(
            sync_card.get_content(),
            text="Enable automatic daily backups",
            variable=app.auto_backup_var,
            font=("Segoe UI", 10),
            fg=pal["text"],
            bg=pal["card_bg"],
            selectcolor=pal.get("entrybg", pal["card_bg"]),
            activebackground=pal["card_bg"],
            activeforeground=pal["text"],
            command=self._mark_dirty
        )
        backup_check.pack(fill="x", pady=8, anchor="w")
        
        # Backup time
        time_frame = tk.Frame(sync_card.get_content(), bg=pal["card_bg"])
        time_frame.pack(fill="x", pady=8)
        
        _cfg = load_config()
        saved_hour = _cfg.get("auto_backup_hour", 2)
        saved_minute = _cfg.get("auto_backup_minute", 0)
        app.auto_backup_hour_var = tk.StringVar(value=f"{saved_hour:02d}:{saved_minute:02d}")
        
        tk.Label(time_frame, text="Backup time:", font=("Segoe UI", 10),
                fg=pal["text"], bg=pal["card_bg"]).pack(side="left")
        time_entry = tk.Entry(time_frame, textvariable=app.auto_backup_hour_var, width=8,
                             font=("Segoe UI", 10), fg=pal["text"], bg=pal.get("entrybg", pal["card_bg"]),
                             insertbackground=pal["text"], relief="solid", bd=1)
        time_entry.pack(side="left", padx=8)
        app.configure_entry_cursor(time_entry)
        
        tk.Label(time_frame, text="(HH:MM, 24h)", font=("Segoe UI", 9),
                fg=pal["muted"], bg=pal["card_bg"]).pack(side="left")
        
        # Last backup status
        app.last_backup_var = tk.StringVar(value="Last backup: Never")
        backup_status = tk.Label(sync_card.get_content(), textvariable=app.last_backup_var,
                                font=("Segoe UI", 9), fg=pal["muted"], bg=pal["card_bg"])
        backup_status.pack(fill="x", pady=8, anchor="w")
        
        # Sync button
        sync_btn_frame = tk.Frame(sync_card.get_content(), bg=pal["card_bg"])
        sync_btn_frame.pack(fill="x", pady=8)
        
        ttk.Button(sync_btn_frame, text="Sync Now", command=app._manual_sync).pack(side="left")
        app.sync_status_var = tk.StringVar(value="Ready")
        tk.Label(sync_btn_frame, textvariable=app.sync_status_var, font=("Segoe UI", 9),
                fg=pal["muted"], bg=pal["card_bg"]).pack(side="left", padx=8)
        
        # Sync scope
        tk.Frame(sync_card.get_content(), bg=pal.get("border_color", "#374151"), 
                height=1).pack(fill="x", pady=16)
        
        tk.Label(sync_card.get_content(), text="Sync Scope:", font=("Segoe UI", 10, "bold"),
                fg=pal["text"], bg=pal["card_bg"]).pack(anchor="w")
        
        sync_frame = tk.Frame(sync_card.get_content(), bg=pal["card_bg"])
        sync_frame.pack(fill="x", pady=8)
        
        config = load_config()
        sync_scope = config.get("sync_scope", "everything")
        app.sync_scope_var = tk.StringVar(value=sync_scope)
        
        for scope_label, scope_val in [("All Wallpapers", "everything"), ("Favorites Only", "favorites")]:
            tk.Radiobutton(sync_frame, text=scope_label, variable=app.sync_scope_var,
                           value=scope_val, font=("Segoe UI", 10),
                           fg=pal["text"], bg=pal["card_bg"], 
                           selectcolor=pal.get("entrybg", pal["card_bg"]),
                           activebackground=pal["card_bg"], activeforeground=pal["text"],
                           command=self._mark_dirty).pack(side="left", padx=16)
        
        helper_label = tk.Label(sync_card.get_content(),
                               text="Choose what to sync to cloud storage",
                               font=("Segoe UI", 9), fg=pal["muted"], bg=pal["card_bg"])
        helper_label.pack(fill="x", pady=8)

    def _build_advanced_category(self, parent, pal):
        """Build Advanced settings category."""
        app = self.app
        frame = tk.Frame(parent, bg=pal["bg"])
        self._category_frames["advanced"] = frame
        
        header = tk.Label(frame, text="Advanced", font=("Segoe UI", 18, "bold"),
                         fg=pal["text"], bg=pal["bg"], anchor="w")
        header.pack(fill="x", pady=20)
        
        # Generation Behavior card
        gen_card = SettingCard(frame, "Generation Behavior",
                               "Fine-tune how prompts are constructed.",
                               pal, pal.get("accent", "#8b5cf6"))
        
        smart_neg_check = tk.Checkbutton(
            gen_card.get_content(),
            text="Smart Negatives",
            variable=app.smart_neg_var,
            font=("Segoe UI", 10),
            fg=pal["text"],
            bg=pal["card_bg"],
            selectcolor=pal.get("entrybg", pal["card_bg"]),
            activebackground=pal["card_bg"],
            activeforeground=pal["text"],
            command=self._mark_dirty
        )
        smart_neg_check.pack(fill="x", pady=8, anchor="w")
        
        neg_helper = tk.Label(gen_card.get_content(),
                             text="Scan the generated prompt for keywords (e.g. portrait, forest) and inject matching negative terms.",
                             font=("Segoe UI", 9), fg=pal["muted"], bg=pal["card_bg"], wraplength=600)
        neg_helper.pack(fill="x", pady=12, anchor="w")
        
        subj_lock_check = tk.Checkbutton(
            gen_card.get_content(),
            text="Keep subject exact",
            variable=app.subject_lock_var,
            font=("Segoe UI", 10),
            fg=pal["text"],
            bg=pal["card_bg"],
            selectcolor=pal.get("entrybg", pal["card_bg"]),
            activebackground=pal["card_bg"],
            activeforeground=pal["text"],
            command=self._mark_dirty
        )
        subj_lock_check.pack(fill="x", pady=4, anchor="w")
        
        subj_helper = tk.Label(gen_card.get_content(),
                               text="Use your typed subject as-is. When off, mood adjectives (e.g. serene, vibrant) may be prefixed.",
                               font=("Segoe UI", 9), fg=pal["muted"], bg=pal["card_bg"], wraplength=600)
        subj_helper.pack(fill="x", pady=4, anchor="w")
        
        # Keyword Expansion card
        kw_card = SettingCard(frame, "Keyword Expansion",
                             "Create custom word mappings for prompt enhancement.",
                             pal, pal.get("accent", "#8b5cf6"))
        
        kw_frame = tk.Frame(kw_card.get_content(), bg=pal["card_bg"])
        kw_frame.pack(fill="x", pady=8)
        
        tk.Label(kw_frame, text="When I type:", font=("Segoe UI", 10),
                fg=pal["text"], bg=pal["card_bg"]).pack(side="left", padx=8)
        app.from_word_var = tk.StringVar()
        app.from_word_entry = ttk.Entry(kw_frame, textvariable=app.from_word_var, width=14)
        app.from_word_entry.pack(side="left", padx=8)
        app.configure_entry_cursor(app.from_word_entry)
        
        tk.Label(kw_frame, text="→", font=("Segoe UI", 10),
                fg=pal["text"], bg=pal["card_bg"]).pack(side="left", padx=8)
        
        app.to_word_var = tk.StringVar()
        app.to_word_entry = ttk.Entry(kw_frame, textvariable=app.to_word_var, width=14)
        app.to_word_entry.pack(side="left", padx=8)
        app.configure_entry_cursor(app.to_word_entry)
        
        btn_frame = tk.Frame(kw_frame, bg=pal["card_bg"])
        btn_frame.pack(side="left")
        
        ttk.Button(btn_frame, text="Add", command=lambda: [self.add_user_mapping(), self._mark_dirty()]).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Remove", command=lambda: [self.remove_user_mapping(), self._mark_dirty()]).pack(side="left")
        
        kw_helper = tk.Label(kw_card.get_content(),
                            text="e.g. awesome → epic, gloomy → moody",
                            font=("Segoe UI", 9), fg=pal["muted"], bg=pal["card_bg"])
        kw_helper.pack(fill="x", pady=8)
        
        app.expansion_status_var = tk.StringVar(value="Keyword expansion: Ready")
        status_label = tk.Label(kw_card.get_content(), textvariable=app.expansion_status_var,
                                font=("Segoe UI", 9), fg=pal["muted"], bg=pal["card_bg"])
        status_label.pack(fill="x", pady=8)

        # Pinned Dropdown Options card (v1.3.0)
        if PINNED_AVAILABLE:
            pin_card = SettingCard(frame, "Favorite Dropdown Items",
                                   "Pin your favorite items to the top of dropdown lists.",
                                   pal, pal.get("accent", "#8b5cf6"))
            try:
                build_pinned_settings_ui(pin_card.get_content(), app)
            except Exception:
                pass

    def _build_help_category(self, parent, pal):
        """Build Help settings category."""
        app = self.app
        frame = tk.Frame(parent, bg=pal["bg"])
        self._category_frames["help"] = frame
        
        header = tk.Label(frame, text="Help", font=("Segoe UI", 18, "bold"),
                         fg=pal["text"], bg=pal["bg"], anchor="w")
        header.pack(fill="x", pady=20)
        
        # Getting Started section
        gs_header = tk.Label(frame, text="Getting Started", font=("Segoe UI", 14, "bold"),
                             fg=pal["text"], bg=pal["bg"], anchor="w")
        gs_header.pack(fill="x", pady=12)
        
        # Help resource cards
        HelpResourceCard(
            frame,
            "📖",
            "Quick Start Guide",
            "Learn the basics of FrogPaper in 5 minutes",
            "Start",
            lambda: app.tutorial_manager.start_tutorial("quick_start"),
            pal
        )
        
        HelpResourceCard(
            frame,
            "🎯",
            "Feature Tour",
            "Explore all major features of FrogPaper",
            "Start",
            lambda: app.tutorial_manager.start_tutorial("feature_tour"),
            pal
        )
        
        HelpResourceCard(
            frame,
            "✏",
            "Interactive Practice",
            "Guided wallpaper generation practice",
            "Start",
            lambda: app.tutorial_manager.start_tutorial("interactive_practice"),
            pal
        )
        
        HelpResourceCard(
            frame,
            "⚙",
            "Model Setup Guide",
            "Configure AI providers and models",
            "Start",
            lambda: app.tutorial_manager.start_tutorial("model_setup"),
            pal
        )

    # ================================================================
    # EVENT HANDLERS (delegated to existing app methods)
    # ================================================================

    def _on_dimension_preset_changed(self, event=None):
        app = self.app
        preset = app.dimension_preset_var.get()
        dimensions = app.DIMENSION_PRESETS.get(preset, "1920x1080")
        self._set_dimensions_from_string(dimensions)
        self.app.save_config()

    def _on_model_choice_changed(self, event=None):
        app = self.app
        if app.model_choice_var.get() == "Custom...":
            if not app.custom_model_entry.winfo_ismapped():
                app.custom_model_entry.pack(fill="x", pady=8)
        elif app.custom_model_entry.winfo_ismapped():
            app.custom_model_entry.pack_forget()

    def _on_provider_changed(self, event=None):
        """Handle provider dropdown change."""
        app = self.app
        provider = app.provider_var.get().strip()
        provider_info = app.PROVIDER_MODELS.get(provider, {})
        new_models = provider_info.get("options", [])
        app.model_choice_combo["values"] = new_models
        if new_models:
            app.model_choice_var.set(new_models[0])
        else:
            app.model_choice_var.set("")
        app.custom_model_entry.pack_forget()
        self._update_provider_visibility()
        self._update_provider_description()

    def _update_provider_visibility(self):
        """Show/hide token fields based on the selected provider."""
        app = self.app
        provider = app.provider_var.get().strip()
        if "Pollinations" in provider:
            app.token_card.get_content().grid_remove()
            app.cloudflare_card.get_content().grid_remove()
        elif "Cloudflare" in provider:
            app.token_card.get_content().grid_remove()
            app.cloudflare_card.get_content().grid()
        else:
            app.token_card.get_content().grid()
            app.cloudflare_card.get_content().grid_remove()

    def _update_provider_description(self):
        """Update the description label for the selected provider."""
        app = self.app
        provider = app.provider_var.get().strip()
        descriptions = {
            "Pollinations.ai (Free - No Key)": "100% free, no account needed. Multiple FLUX models available.",
            "Cloudflare Workers AI (Free Tier)": "Free: 10,000 neurons/day. Needs a free Cloudflare account token.",
            "Hugging Face Inference": "Uses your HF token. Free credits reset monthly ($0.10 for free users).",
        }
        app.provider_desc_var.set(descriptions.get(provider, ""))

    def _on_token_changed(self, event=None):
        """Auto-save token when the entry field loses focus."""
        app = self.app
        token = app.token_var.get().strip()
        config = load_config()
        if token:
            config["huggingface_token"] = token
        else:
            config.pop("huggingface_token", None)
        save_config(config)
        app.token_preview_var.set(self.format_token_preview())

    def _set_dimensions_from_string(self, dimensions_str):
        app = self.app
        if "x" in dimensions_str:
            width, height = dimensions_str.split("x", 1)
            app.custom_width_var.set(width.strip())
            app.custom_height_var.set(height.strip())
            for preset_name, preset_dims in app.DIMENSION_PRESETS.items():
                if preset_dims == dimensions_str:
                    app.dimension_preset_var.set(preset_name)
                    break

    # ================================================================
    # DELEGATED METHODS (called from app.py via self._settings_tab)
    # ================================================================

    def format_token_preview(self):
        """Format token for preview display."""
        token = get_huggingface_token()
        if not token:
            return "Environment token not found."
        if len(token) <= 8:
            return "Environment token loaded: " + ("*" * len(token))
        return f"Environment token loaded: {token[:4]}...{token[-4:]}"

    def refresh_token_status(self):
        """Refresh token from environment and update UI."""
        app = self.app
        token = get_huggingface_token()
        app.token_var.set(token)
        if hasattr(app, 'token_entry') and app.token_entry.winfo_exists():
            app.token_entry.config(show="*")
        if hasattr(app, 'token_toggle_btn') and app.token_toggle_btn.winfo_exists():
            app.token_toggle_btn.config(text="Show")
        app.token_preview_var.set(self.format_token_preview())
        app.status_var.set("Environment token loaded." if token else "No environment token found.")

    def toggle_token_visibility(self):
        """Toggle token entry between hidden and visible."""
        app = self.app
        if hasattr(app, 'token_entry') and app.token_entry.winfo_exists():
            if app.token_entry.cget("show") == "*":
                app.token_entry.config(show="")
                if hasattr(app, 'token_toggle_btn') and app.token_toggle_btn.winfo_exists():
                    app.token_toggle_btn.config(text="Hide")
            else:
                app.token_entry.config(show="*")
                if hasattr(app, 'token_toggle_btn') and app.token_toggle_btn.winfo_exists():
                    app.token_toggle_btn.config(text="Show")

    def resolved_model_id(self):
        """Resolve the selected model display name to an actual model ID."""
        app = self.app
        choice = app.model_choice_var.get().strip()
        if choice == "Custom...":
            return app.custom_model_var.get().strip()
        provider = app.provider_var.get().strip()
        provider_info = app.PROVIDER_MODELS.get(provider, {})
        display_to_id = provider_info.get("display_to_id", {})
        return display_to_id.get(choice, "flux")

    def save_settings(self):
        """Save all settings to config file."""
        app = self.app
        config = load_config()

        # Theme
        display_name = app.theme_var.get()
        config["app_theme"] = app.THEME_INTERNAL_NAMES.get(display_name, "darkforest")

        # Dimensions & model
        config["dimensions"] = self.get_current_dimensions()
        config["model_id"] = self.resolved_model_id() or "flux"
        config["provider"] = app.provider_var.get().strip()

        # Cloudflare
        cf_token = app.cloudflare_token_var.get().strip()
        if cf_token:
            config["cloudflare_token"] = cf_token
        cf_account_id = app.cloudflare_account_id_var.get().strip()
        if cf_account_id:
            config["cloudflare_account_id"] = cf_account_id

        # Slideshow
        config['slideshow_enabled'] = bool(app.slideshow_enabled_var.get())
        config['slideshow_interval'] = int(app.slideshow_interval_var.get() or 60)
        source_value = app.slideshow_source_var.get().strip()
        if source_value == 'both':
            source_value = 'all'
        config['slideshow_source'] = app.SLIDESHOW_LABEL_TO_VALUE.get(source_value, source_value.lower()) or 'all'
        config['slideshow_order'] = app.slideshow_order_var.get()
        config['slideshow_skip_duplicates'] = bool(app.slideshow_skip_duplicates_var.get())

        # Startup & tray
        config["remember_settings"] = bool(app.remember_settings_var.get())
        config["auto_generate_on_startup"] = bool(app.auto_generate_on_startup_var.get())
        config["startup_subject"] = app.startup_subject_var.get().strip() or "frog"
        config['minimize_to_tray'] = bool(app.minimize_to_tray_enabled)

        # Token
        token = app.token_var.get().strip()
        if token:
            config["huggingface_token"] = token

        # Remembered settings
        if app.remember_settings_var.get():
            config["last_style_mode"] = app.get_active_mode()
            config["last_subject"] = app.get_active_subject()
            config["last_setting"] = app.get_active_setting()
            config["last_style"] = app.get_active_style()
            config["last_lighting"] = app.get_active_lighting()
            config["last_mood"] = app.get_active_mood()
            config["last_color"] = app.get_active_color()
            config["last_atmosphere"] = app.get_active_atmosphere()
            config["last_subject_lock"] = app.get_active_subject_lock()

        # Negative prompt selections
        neg_preset_selections = {}
        if hasattr(app, '_neg_preset_vars'):
            for key, var in app._neg_preset_vars.items():
                if hasattr(var, 'get'):
                    try:
                        neg_preset_selections[key] = var.get()
                    except Exception:
                        neg_preset_selections[key] = False
        neg_custom_terms = ""
        if hasattr(app, '_neg_custom_var'):
            if hasattr(app._neg_custom_var, 'get'):
                try:
                    neg_custom_terms = app._neg_custom_var.get()
                except Exception:
                    neg_custom_terms = ""
        config["last_neg_preset_selections"] = neg_preset_selections
        config["last_neg_custom_terms"] = neg_custom_terms

        # Wallpaper format
        config['wallpaper_format'] = app.wallpaper_format_var.get()
        config['wallpaper_quality'] = app.wallpaper_quality_var.get()

        # Scheduler settings (v1.3.0)
        try:
            from setup_scheduler import save_scheduler_settings_to_config
            save_scheduler_settings_to_config(app)
        except Exception as e:
            logger.warning(f"Failed to save scheduler settings: {e}")

        save_config(config)
        app.status_var.set("Settings saved.")
        self.sync_slideshow_state()
        try:
            app._dialog.info("Settings", "Settings saved successfully.")
        except Exception:
            pass

    def setup_scheduler_from_gui(self):
        """Create a scheduled task for auto-wallpaper."""
        app = self.app
        try:
            from setup_scheduler import create_task
            ok = create_task()
            if ok:
                app._dialog.info("Task Scheduler", "Morning auto-wallpaper task created successfully.")
                app.status_var.set("Task Scheduler setup complete.")
            else:
                app._dialog.warning("Task Scheduler", "Task setup did not complete successfully.")
                app.status_var.set("Task Scheduler setup may have failed.")
        except Exception as e:
            app._dialog.error("Task Scheduler", f"Could not create scheduled task.\n\n{e}")
            app.status_var.set("Task Scheduler setup failed.")

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

    def _on_remember_settings_changed(self, event=None):
        """Handle remember-settings checkbox toggle."""
        pass

    def load_remembered_settings(self):
        """Load previously remembered settings from config."""
        app = self.app
        config = load_config()
        if hasattr(app, 'wallpaper_format_var'):
            app.wallpaper_format_var.set(config.get('wallpaper_format', 'PNG'))
        if hasattr(app, 'wallpaper_quality_var'):
            app.wallpaper_quality_var.set(config.get('wallpaper_quality', 'High'))
        neg_preset_selections = config.get("last_neg_preset_selections", {})
        neg_custom_terms = config.get("last_neg_custom_terms", "")
        if neg_preset_selections and hasattr(app, '_neg_preset_vars'):
            for key, selected in neg_preset_selections.items():
                if key in app._neg_preset_vars:
                    if hasattr(app._neg_preset_vars[key], 'set'):
                        try:
                            app._neg_preset_vars[key].set(selected)
                        except Exception:
                            pass
        if neg_custom_terms and hasattr(app, '_neg_custom_var'):
            if hasattr(app._neg_custom_var, 'set'):
                try:
                    app._neg_custom_var.set(neg_custom_terms)
                except Exception:
                    pass
        if hasattr(app, '_rebuild_neg_combined'):
            try:
                app._rebuild_neg_combined()
            except Exception:
                pass
        if config.get("remember_settings", False) and not config.get("auto_generate_on_startup", False):
            app.set_active_mode(config.get("last_style_mode", app.DEFAULT_PROMPT_MODE_VALUE))
            app.set_active_subject(config.get("last_subject", "frog"))
            app.set_active_setting(config.get("last_setting", ""))
            app.set_active_style(config.get("last_style", "oil painting"))
            app.set_active_lighting(config.get("last_lighting", "neon"))
            app.set_active_mood(config.get("last_mood", "epic"))
            app.set_active_color(config.get("last_color", ""))
            app.set_active_atmosphere(config.get("last_atmosphere", ""))
            app.set_active_subject_lock(config.get("last_subject_lock", True))
            app.status_var.set("Settings restored from last session")
        else:
            config["last_style"] = ""
            config["last_setting"] = ""
            config["last_lighting"] = ""
            config["last_mood"] = ""
            config["last_color"] = ""
            config["last_atmosphere"] = ""
            save_config(config)
            app.set_active_style("")
            app.set_active_setting("")
            app.set_active_lighting("")
            app.set_active_mood("")
            app.set_active_color("")
            app.set_active_atmosphere("")

    def add_user_mapping(self):
        """Add a custom user thesaurus mapping."""
        app = self.app
        from_word = app.from_word_var.get().strip()
        to_word = app.to_word_var.get().strip()
        if not from_word or not to_word:
            app._dialog.warning("Invalid Input", "Please enter both 'when I type' and 'treat as' values.")
            return
        try:
            from keyword_expander import get_keyword_expander
            expander = get_keyword_expander()
            expander.add_user_mapping(from_word, to_word)
            app.from_word_var.set("")
            app.to_word_var.set("")
            app.status_var.set(f"Added mapping: '{from_word}' -> '{to_word}'")
            app.expansion_status_var.set(f"Keyword expansion: Added '{from_word}' -> '{to_word}'")
        except Exception as e:
            app._dialog.error("Error", f"Could not add mapping: {e}")

    def remove_user_mapping(self):
        """Remove a custom user thesaurus mapping."""
        app = self.app
        from_word = app.from_word_var.get().strip()
        if not from_word:
            app._dialog.warning("Invalid Input", "Please enter the word to remove.")
            return
        try:
            from keyword_expander import get_keyword_expander
            expander = get_keyword_expander()
            expander.remove_user_mapping(from_word)
            app.from_word_var.set("")
            app.status_var.set(f"Removed mapping for: '{from_word}'")
            app.expansion_status_var.set(f"Keyword expansion: Removed '{from_word}'")
        except Exception as e:
            app._dialog.error("Error", f"Could not remove mapping: {e}")

    def get_current_dimensions(self):
        """Get current wallpaper dimensions string."""
        app = self.app
        return app.DIMENSION_PRESETS.get(app.dimension_preset_var.get(), "1920x1080")
