"""
Redesigned settings page with sidebar navigation and card-based layout.
Provides a polished, premium settings experience.
"""

import tkinter as tk
import logging

from tkinter import ttk

from theme import COLOR_ACCENT, COLOR_ERROR, COLOR_GRAY_200, COLOR_GRAY_400, COLOR_GRAY_700, COLOR_GRAY_800, COLOR_GRAY_900, COLOR_MID_GRAY, COLOR_SUCCESS, COLOR_WARNING  # shared color constants (migrated inline hex)

# Pinned Dropdown Options feature (since v1.4.1 - Favorite Items)
try:
    from pinned_dropdowns import (
        init_pinned_manager,  # noqa: F401  (availability probe)
        get_manager,  # noqa: F401  (availability probe)
        build_pinned_settings_ui,  # noqa: F401  (availability probe)
    )
    PINNED_AVAILABLE = True
except ImportError:
    PINNED_AVAILABLE = False

from settings_components import (
    SidebarNav
)

logger = logging.getLogger(__name__)

# STATUS_COLORS now lives in theme.py (single source of truth) and is
# re-exported here on purpose: app_cloud_mixin still does
# `from settings_tab import STATUS_COLORS`, and test_theme asserts the
# identity.  (ruff F401 is silenced via noqa - this is a facade import.)
from theme import STATUS_COLORS  # noqa: F401  (facade re-export)

# ------------------------------------------------------------------
# Modularized internals (roadmap #7 Phase A).  SettingsTab is now the
# shell (init, layout, save bar, retheme) plus four section mixins
# that live in their own modules.  All methods remain on the single
# SettingsTab class, so app.py / prompt_tab.py / tests are unaffected.
# The UX config dicts moved to settings_ux_data.py and are re-exported
# here for backward compatibility.
# ------------------------------------------------------------------
from settings_ux_data import AI_PROVIDER_UX, CLOUD_PROVIDER_UX  # noqa: F401
from settings_categories import SettingsCategoriesMixin
from settings_persistence import SettingsPersistenceMixin
from settings_providers import SettingsProvidersMixin
from settings_slideshow import SettingsSlideshowMixin




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
    bg = pal.get("bg", COLOR_GRAY_900)
    panel = pal.get("panel", COLOR_GRAY_800)
    
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
class SettingsTab(SettingsCategoriesMixin, SettingsProvidersMixin, SettingsSlideshowMixin, SettingsPersistenceMixin):
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
        self._palette = pal  # cache for dynamic rebuilds
        
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
        sep = tk.Frame(body_container, bg=pal.get("border_color", COLOR_GRAY_700), width=1)
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
        tk.Frame(save_bar, bg=pal.get("border_color", COLOR_GRAY_700), height=1).pack(side="top", fill="x")
        sep_glow = tk.Frame(save_bar, bg=pal.get("accent", COLOR_ACCENT), height=1)
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
        self._status_dot.create_oval(1, 1, 7, 7, fill=COLOR_SUCCESS, outline="", tags="dot")

        self.save_status_var = tk.StringVar(value="All changes saved")
        status_label = tk.Label(
            content,
            textvariable=self.save_status_var,
            font=("Segoe UI", 9),
            fg=pal.get("muted", COLOR_GRAY_400),
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
            self._status_dot.create_oval(1, 1, 7, 7, fill=COLOR_WARNING, outline="", tags="dot")
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
            self._status_dot.create_oval(1, 1, 7, 7, fill=COLOR_SUCCESS, outline="", tags="dot")
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
        border_color = pal.get("border_color", COLOR_GRAY_700)
        accent = pal.get("accent", COLOR_ACCENT)
        muted = pal.get("muted", COLOR_GRAY_400)

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
                text_fg = pal.get("text", COLOR_GRAY_200)
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
                                            COLOR_SUCCESS, COLOR_ERROR, COLOR_WARNING,
                                            "#3b82f6", accent,
                                        }
                                        if cur_fg and cur_fg not in (
                                            muted, text_fg, "gray", "grey",
                                            COLOR_MID_GRAY, COLOR_GRAY_400,
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
