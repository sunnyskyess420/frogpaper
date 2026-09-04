"""Theme engine methods for FrogPaperApp (roadmap #7 Phase B step 2).

Extracted verbatim from app.py: apply_theme (the 583-line theme
application engine), the per-area retheme helpers (child widgets,
settings cloud cards, gallery, negative-prompt labels, sv-ttk classic
widgets), theme-change handling, sidebar icon refresh and the custom
entry-cursor colour system.

All methods are mixed into FrogPaperApp (see app.py), so behaviour is
unchanged: state still lives on self / self.app and every caller
keeps working untouched.
"""

import logging

import tkinter as tk
from tkinter import ttk

from utils import load_config, save_config

from app_themes import THEMES, THEME_INTERNAL_NAMES, _readable_fg

# Runtime flags / optional modules probed in app_runtime.py (roadmap #7
# Phase B step 2).  apply_theme and the retheme helpers reference these
# as bare module globals, exactly as they did when they lived in app.py.
# NOTE: sv_ttk is only bound in app_runtime when the package imports, so
# mirror app.py's conditional re-import (NameError-proof on machines
# without sv_ttk, identical semantics to the pre-split code).
from app_runtime import (
    SV_TTK_AVAILABLE,
    UI_EFFECTS_AVAILABLE,
    ThemeTransition,
)

from theme import COLOR_BLACK, COLOR_GRAY_700, COLOR_MID_GRAY, COLOR_NEAR_BLACK, COLOR_WHITE  # shared color constants (migrated inline hex)
if SV_TTK_AVAILABLE:
    from app_runtime import sv_ttk

logger = logging.getLogger(__name__)


class FrogPaperAppThemeMixin:
    """Theme application/retheme methods for FrogPaperApp."""

    def get_cursor_color(self):

        """Get a cursor color that contrasts with the current theme background."""

        try:

            pal = THEMES.get(self.current_theme_name, THEMES["darkforest"])

            bg_color = pal["bg"]

            

            # Determine if background is dark or light

            if bg_color in ["#0f1711", "#16231a", "#1c2d22", "#0a1929", "#132f4c", "#1e3a5f", "#1a0f0f", "#2d1b1b", "#3d2828", COLOR_BLACK, "#1a1a1a", "#2d2d2d"]:

                # Dark background - use

                #  light cursor

                return COLOR_WHITE  # White cursor for dark themes

            else:

                # Light background - use dark cursor

                return COLOR_BLACK  # Black cursor for light themes

        except Exception:

            return COLOR_BLACK  # Fallback to black



    def _update_all_entry_cursors(self):

        """Update cursor colors for all entry widgets when theme changes."""

        try:

            cursor_color = self.get_cursor_color()

            

            # Update all known entry widgets

            entry_widgets = [

                getattr(self, 'subject_entry', None),

                getattr(self, 'style_entry', None),

                getattr(self, 'lighting_entry', None),

                getattr(self, 'mood_entry', None),

                getattr(self, 'color_entry', None),

                getattr(self, 'negative_prompt_entry', None),

                getattr(self, 'token_entry', None),

                getattr(self, 'custom_width_entry', None),

                getattr(self, 'custom_height_entry', None),

                getattr(self, 'custom_model_entry', None),

                getattr(self, 'from_word_entry', None),

                getattr(self, 'to_word_entry', None),

            ]

            

            for entry in entry_widgets:

                if entry and hasattr(entry, 'configure'):

                    try:

                        # Check if it's a regular Entry widget (not Combobox)

                        if 'Entry' in str(type(entry)):

                            entry.configure(insertcolor=cursor_color, insertwidth=3)

                        # Combobox widgets get cursor styling from theme

                    except Exception:

                        pass

        except Exception:

            pass



    def configure_entry_cursor(self, entry_widget):

        """Configure entry widget with enhanced cursor visibility."""

        try:

            cursor_color = self.get_cursor_color()

            

            # Check if it's a regular Entry widget (not Combobox)

            if hasattr(entry_widget, 'configure') and 'Entry' in str(type(entry_widget)):

                # Regular Entry widget supports insertcolor

                entry_widget.configure(insertcolor=cursor_color, insertwidth=3)

            elif hasattr(entry_widget, 'configure') and 'Combobox' in str(type(entry_widget)):

                # Combobox widgets have different cursor handling

                # The cursor will inherit from the theme styling

                pass

        except Exception:

            # Fallback - do nothing for unsupported widgets

            pass



    def on_theme_changed(self, event=None):

        display_name = self.theme_var.get()

        internal_name = THEME_INTERNAL_NAMES.get(display_name, "darkforest")

        # ── Animated theme transition ──
        if UI_EFFECTS_AVAILABLE and hasattr(self, 'current_theme_name'):
            old_pal = THEMES.get(self.current_theme_name, THEMES["darkforest"])
            new_pal = THEMES.get(internal_name, THEMES["darkforest"])
            bg_widgets = {"bg": [self._sidebar_outer] if hasattr(self, "_sidebar_outer") else []}
            try:
                if hasattr(self, '_center_panel'):
                    bg_widgets["panel"] = [self._center_panel]
                if hasattr(self, '_right_panel'):
                    bg_widgets["panel2"] = [self._right_panel]
            except Exception:
                pass
            old_colors = {k: old_pal.get(k, old_pal["bg"]) for k in bg_widgets}
            new_colors = {k: new_pal.get(k, new_pal["bg"]) for k in bg_widgets}
            transition = ThemeTransition(self.root)
            transition.start(old_colors, new_colors, bg_widgets,
                             callback=lambda: self.apply_theme(internal_name))
        else:
            self.apply_theme(internal_name)

        self.status_var.set(f"Theme switched to {display_name}")



    def _lighten_color(self, hex_color, percent):
        """Lighten a hex color by a percentage."""
        try:
            hex_color = hex_color.lstrip('#')
            r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            r = min(255, int(r + (255 - r) * percent / 100))
            g = min(255, int(g + (255 - g) * percent / 100))
            b = min(255, int(b + (255 - b) * percent / 100))
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return hex_color

    def _darken_color(self, hex_color, percent):
        """Darken a hex color by a percentage."""
        try:
            hex_color = hex_color.lstrip('#')
            r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            r = max(0, int(r * (100 - percent) / 100))
            g = max(0, int(g * (100 - percent) / 100))
            b = max(0, int(b * (100 - percent) / 100))
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return hex_color

    def _apply_sidebar_icons(self, accent):
        """Apply rendered icons to sidebar, header, and prompt tab buttons."""
        pass  # Icons disabled — text-only buttons

    def _retheme_child_widgets(self, parent, pal):
        """Recursively re-theme all tk.Frame/tk.Label children of a parent widget."""
        try:
            for child in parent.winfo_children():
                try:
                    if isinstance(child, tk.Frame):
                        child.configure(bg=pal["panel"])
                        # Recurse into frame children
                        self._retheme_child_widgets(child, pal)
                    elif isinstance(child, tk.Label):
                        # Determine foreground based on actual font size.
                        # Small fonts (≤9pt) get muted colour; larger get text colour.
                        is_small = False
                        try:
                            font_info = child.cget("font")
                            if isinstance(font_info, tuple) and len(font_info) >= 2:
                                is_small = abs(int(font_info[1])) <= 9
                            elif isinstance(font_info, str):
                                # Named font — query actual size via Tk
                                actual = self.root.tk.call(font_info, "actual", "-size")
                                is_small = abs(int(actual)) <= 9
                        except Exception:
                            pass
                        fg = pal["muted"] if is_small else pal["text"]
                        child.configure(bg=pal["panel"], fg=fg)
                    elif isinstance(child, tk.Button):
                        # Re-theme button background to match new panel colour
                        # so no visible square appears around icon-only buttons
                        # (e.g. the heart/star favorite buttons).
                        # The parent Frame was already re-themed above, so
                        # just read its current bg.
                        parent_bg = pal["panel"]
                        try:
                            pw = self.root.nametowidget(child.winfo_parent())
                            parent_bg = pw.cget("bg")
                        except Exception:
                            pass
                        child.configure(
                            bg=parent_bg,
                            activebackground=pal.get("panel2", parent_bg),
                        )
                        # Refresh heart/star icon images with new accent colour
                        if hasattr(child, "_img_path"):
                            try:
                                from icons import get_icon
                                accent = pal.get("accent", pal["progress"])
                                is_fav = False
                                try:
                                    if hasattr(self, "_gallery_tab"):
                                        is_fav = self._gallery_tab._is_image_favorited(child._img_path)
                                except Exception:
                                    pass
                                heart_name = "heart_filled" if is_fav else "heart_outline"
                                heart_icon = get_icon(heart_name, size=36, color=accent)
                                child.configure(image=heart_icon)
                                child.image = heart_icon
                                child._icon_ref = heart_icon
                            except Exception:
                                pass
                    elif isinstance(child, tk.Canvas):
                        child.configure(bg=pal["panel"], highlightthickness=0)
                except tk.TclError:
                    pass  # Widget already destroyed
        except tk.TclError:
            pass  # Parent already destroyed

    def _retheme_settings_cloud_widgets(self, pal):
        """Re-theme the Cloud Accounts section in the settings tab.

        The cloud cards and sync options use tk widgets with hardcoded bg/fg
        colours set at build time.  Unlike ttk widgets they do NOT auto-update
        when the ttk style changes, so we must walk the tree and repaint them.

        We use pal["bg"] (not pal["panel"]) because the cloud cards live
        directly on the settings scroll area which uses the theme background.

        NOTE: This walker is COMPONENT-AWARE — if a child widget is tagged
        with ``_fp_component`` (i.e. it is the outer frame of a
        SettingCard / SettingRow / ExpandableSection / HelpResourceCard /
        CloudProviderCard managed by ``settings_tab.py``), we skip it
        entirely so that ``SettingsTab._retheme_settings_popup`` (which
        calls each component's ``update_theme``) is the single source of
        truth for the component's colours.  Without this guard, this
        walker would repaint the card bodies to ``pal["bg"]`` and erase
        the card-vs-page visual distinction, producing the "grey instead
        of theme color" bug in the settings area.
        """
        bg = pal["bg"]
        muted = pal["muted"]
        text_fg = pal["text"]
        entry_bg = pal.get("entrybg", bg)
        sep_color = pal.get("separator", pal.get("border_color", "#333"))
        accent = pal.get("accent", pal["progress"])

        def _walk(parent):
            try:
                for child in parent.winfo_children():
                    try:
                        # Skip widgets owned by a settings component —
                        # the component's own update_theme handles it.
                        if getattr(child, "_fp_component", None) is not None:
                            continue

                        if isinstance(child, tk.Frame):
                            # Separator frames (height=1) get the separator colour
                            if child.cget("height") == 1 and child.cget("width") == 0:
                                child.configure(bg=sep_color)
                            else:
                                child.configure(bg=bg)
                            _walk(child)
                        elif isinstance(child, (ttk.LabelFrame, ttk.Frame)):
                            # ttk containers are styled by the ttk theme engine;
                            # just recurse into their tk children.
                            _walk(child)
                        elif isinstance(child, tk.Label):
                            child.configure(bg=bg)
                            # Keep accent-coloured labels (setup links, icons)
                            try:
                                cur_fg = child.cget("fg")
                                # Detect accent-styled labels by checking if their
                                # current fg is a non-muted colour (heuristic)
                                if cur_fg and cur_fg not in (muted, text_fg):
                                    child.configure(fg=accent)
                                else:
                                    # Small font → muted, otherwise text
                                    is_small = False
                                    try:
                                        font_info = child.cget("font")
                                        if isinstance(font_info, tuple) and len(font_info) >= 2:
                                            is_small = abs(int(font_info[1])) <= 9
                                    except Exception:
                                        pass
                                    child.configure(fg=muted if is_small else text_fg)
                            except Exception:
                                pass
                        elif isinstance(child, (tk.Checkbutton, tk.Radiobutton)):
                            child.configure(bg=bg, fg=text_fg,
                                           selectcolor=entry_bg,
                                           activebackground=bg,
                                           activeforeground=text_fg)
                        elif isinstance(child, tk.Canvas):
                            child.configure(bg=bg, highlightthickness=0)
                    except tk.TclError:
                        pass
            except tk.TclError:
                pass

        if hasattr(self, 'settings_inner'):
            try:
                _walk(self.settings_inner)
            except tk.TclError:
                pass

    def _retheme_gallery_widgets(self, pal):
        """Re-theme all gallery view card widgets after a theme change."""
        border = pal.get("border_color", pal["panel2"])

        # Main gallery cards + placeholders
        if hasattr(self, "gallery_inner") and self.gallery_inner.winfo_exists():
            self._retheme_child_widgets(self.gallery_inner, pal)
            # Update card highlight borders
            for key, card_data in list(self.gallery_cards.items()):
                # Handle variable-length card data (some have 2, 3, 4, or 6 elements)
                card = card_data[0] if isinstance(card_data, (tuple, list)) else card_data
                try:
                    if card.winfo_exists():
                        card.configure(highlightbackground=border)
                except tk.TclError:
                    pass
            # Update placeholder backgrounds
            for idx, ph in list(self._gallery_placeholders.items()):
                try:
                    if ph.winfo_exists():
                        ph.configure(bg=pal["panel2"])
                except tk.TclError:
                    pass

        # Favorites inner
        if hasattr(self, "gallery_fav_inner") and self.gallery_fav_inner.winfo_exists():
            self._retheme_child_widgets(self.gallery_fav_inner, pal)

        # Styled inner
        if hasattr(self, "gallery_styled_inner") and self.gallery_styled_inner.winfo_exists():
            self._retheme_child_widgets(self.gallery_styled_inner, pal)

        # Manual inner
        if hasattr(self, "gallery_manual_inner") and self.gallery_manual_inner.winfo_exists():
            self._retheme_child_widgets(self.gallery_manual_inner, pal)

    def _retheme_neg_prompt_labels(self, pal):
        """Re-theme the negative prompt area's tk.Label widgets.

        Several labels in the negative prompt builder are created with
        hardcoded fg='gray' and are never updated during apply_theme().
        This method updates them to use the current theme's muted colour.
        """
        muted = pal.get("muted", COLOR_MID_GRAY)
        bg = pal.get("panel", pal["bg"])
        text_fg = pal.get("text", COLOR_WHITE)

        # 1) Term-count labels next to each preset checkbutton
        if hasattr(self, "_neg_preset_frame"):
            for row_frame in self._neg_preset_frame.winfo_children():
                for child in row_frame.winfo_children():
                    if isinstance(child, tk.Label):
                        try:
                            child.configure(bg=bg, fg=muted)
                        except tk.TclError:
                            pass

        # 2) Preset description label (shows on hover)
        if hasattr(self, "_neg_preset_desc_lbl") and self._neg_preset_desc_lbl.winfo_exists():
            self._neg_preset_desc_lbl.configure(bg=bg, fg=muted)

        # 3) Preview note ("Additional negatives may be added...")
        # This label doesn't have a stored reference, so find it by text
        # 4) Term count display
        # We handle both by walking the sidebar's negative prompt section
        if hasattr(self, "_neg_final_frame") and self._neg_final_frame.winfo_exists():
            parent = self._neg_final_frame.master
            for child in parent.winfo_children():
                if isinstance(child, tk.Label) and child not in (
                    getattr(self, "_neg_preset_desc_lbl", None),
                ):
                    try:
                        child.configure(bg=bg, fg=muted)
                    except (tk.TclError, AttributeError):
                        pass

        # 5) Preview Text widget — tk.Text inherits from tk_setPalette,
        # but re-configure explicitly to ensure consistency
        if hasattr(self, "_neg_final_text") and self._neg_final_text.winfo_exists():
            try:
                self._neg_final_text.configure(
                    bg=pal.get("entrybg", pal["bg"]),
                    fg=pal.get("entryfg", pal["text"]),
                    insertbackground=pal["text"],
                )
            except tk.TclError:
                pass

        # 6) Custom Negatives list — placeholder, × remove buttons
        # These tk.Label widgets are created with hardcoded ``fg="gray"``
        # in ``_rebuild_custom_neg_ui``.  Without this pass they stay grey
        # after every theme change, which is the most visible part of
        # the "neon cyber colors appear grey" bug in the prompt builder.
        if hasattr(self, "_cn_frame") and self._cn_frame is not None and self._cn_frame.winfo_exists():
            try:
                for row in self._cn_frame.winfo_children():
                    try:
                        for child in row.winfo_children():
                            if isinstance(child, tk.Label):
                                txt = (child.cget("text") or "").strip()
                                if txt == "×":
                                    # × remove button — keep its hover
                                    # behaviour but use muted as the
                                    # resting colour so it matches the
                                    # theme instead of staying grey.
                                    child.configure(bg=bg, fg=muted)
                                    # Re-bind hover so <Leave> restores
                                    # the muted colour (not "gray").
                                    def _on_enter(lbl=child):
                                        try:
                                            lbl.configure(fg="#ff6666")
                                        except tk.TclError:
                                            pass
                                    def _on_leave(lbl=child):
                                        try:
                                            lbl.configure(fg=muted)
                                        except tk.TclError:
                                            pass
                                    child.unbind("<Enter>")
                                    child.unbind("<Leave>")
                                    child.bind("<Enter>", lambda e, f=_on_enter: f())
                                    child.bind("<Leave>", lambda e, f=_on_leave: f())
                                else:
                                    child.configure(bg=bg, fg=muted)
                    except tk.TclError:
                        continue
                # Walk direct tk.Label children too (the "No saved
                # terms yet" placeholder is packed directly in
                # _cn_frame when there are no terms).
                for child in self._cn_frame.winfo_children():
                    try:
                        if isinstance(child, tk.Label):
                            txt = (child.cget("text") or "").strip()
                            if txt and txt != "×":
                                child.configure(bg=bg, fg=muted)
                    except tk.TclError:
                        continue
            except tk.TclError:
                pass

    def apply_theme(self, theme_name):
        if theme_name not in THEMES:
            theme_name = "darkforest"

        self.current_theme_name = theme_name
        pal = THEMES.get(self.current_theme_name, THEMES["darkforest"])

        self.root.configure(bg=pal["bg"])
        style = ttk.Style(self.root)

        # Apply sv_ttk theme for rounded corners.
        # Use the matching sv_ttk base theme (light/dark) so that
        # configure_colors() and tk_setPalette set appropriate base
        # colours before we fine-tune with the FrogPaper palette.
        # Detect light theme by background luminance, not name, so themes
        # like "warmpaper" are correctly identified as light.
        if SV_TTK_AVAILABLE:
            try:
                def _is_light_bg(hex_color):
                    h = hex_color.lstrip('#')
                    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
                    return (0.299 * r + 0.587 * g + 0.114 * b) / 255 > 0.5
                is_light_theme = _is_light_bg(pal["bg"])
                sv_ttk.set_theme("light" if is_light_theme else "dark")
            except Exception:
                pass

        # ── Kill sv_ttk's async palette re-grey (ROOT CAUSE of grey areas) ──
        # sv_ttk binds configure_colors() to <<ThemeChanged>>, which fires
        # ASYNCHRONOUSLY after this method finishes.  configure_colors()
        # calls tk_setPalette() with sv_ttk's own neutral colours
        # (#1c1c1c bg / #fafafa fg for dark) — silently repainting every
        # classic tk widget in the sidebar / prompt builder back to sv_ttk
        # grey AFTER we apply the FrogPaper palette below.
        if SV_TTK_AVAILABLE:
            try:
                from sv_ttk_fix import disable_classic_palette_regrey
                disable_classic_palette_regrey(self.root)
            except Exception as e:
                logger.warning("Could not disable sv_ttk palette re-grey: %s", e)

        # ── Replace sv_ttk's base sprites with themed colours ──
        # sv_ttk bakes grey (dark) or light grey (light) PNG backgrounds
        # into all widget images.  This recolours every sprite to match
        # the active FrogPaper theme palette while keeping sv_ttk's
        # rounded corners and hover state layouts.
        if SV_TTK_AVAILABLE:
            try:
                from sv_ttk_fix import fix_sv_ttk_sprites
                fix_sv_ttk_sprites(self.root, pal)
            except Exception as e:
                logger.warning("sv_ttk sprite fix failed: %s", e)

        accent = pal.get("accent", pal["progress"])
        border = pal.get("border_color", pal["panel2"])
        surface = pal.get("surface", pal["panel2"])

        # ── Contrast-safe button foregrounds ──────────────────────────
        # Validate the theme's button_fg against each button's ACTUAL
        # painted surface.  neoncyber_light ships button_fg=#ffffff for
        # its accent buttons, which vanished on the light panel2 button
        # sprites (white-on-light, ratio 1.5).  Threshold is 2.0 — low
        # enough to keep every legible dark-theme palette untouched
        # (their pale-on-accent ratios are ≈2.4+) — only catastrophic
        # combos like white-on-lavender get repaired.
        accent_btn_fg = _readable_fg(pal["button_fg"], COLOR_NEAR_BLACK,
                                     COLOR_WHITE, accent, min_ratio=2.0)
        plain_btn_fg = _readable_fg(pal["button_fg"], COLOR_NEAR_BLACK,
                                    COLOR_WHITE, pal["panel2"], min_ratio=2.0)
        progress_btn_fg = _readable_fg(pal["button_fg"], COLOR_NEAR_BLACK,
                                       COLOR_WHITE, pal["progress"],
                                       min_ratio=2.0)
        # Pressed buttons use the tabsel surface; prefer the already-
        # validated plain button fg so light tabs stay readable.
        pressed_btn_fg = _readable_fg(plain_btn_fg, COLOR_NEAR_BLACK,
                                      COLOR_WHITE, pal["tabsel"],
                                      min_ratio=2.0)

        style.configure(".",
            background=pal["bg"],
            foreground=pal["text"],
            fieldbackground=pal["entrybg"],
            relief="flat",
            borderwidth=0,
        )
        style.configure("TFrame", background=pal["bg"])
        style.configure("Inner.TFrame", background=pal["bg"])
        style.configure("Surface.TFrame", background=surface)
        style.configure("Card.TFrame", background=pal["panel"], relief="flat", borderwidth=0)
        # Card styling with subtle border for depth
        style.configure("Card.TFrame", background=pal["panel"], relief="groove",
                         borderwidth=1, bordercolor=pal.get("border_color", pal["panel2"]))

        style.configure("TLabelframe",
            background=pal["bg"],
            foreground=pal["text"],
            relief="flat",
            borderwidth=0,
        )
        style.configure("TLabelframe.Label",
            background=pal["bg"],
            foreground=accent,
            font=("Segoe UI", 10, "bold"),
            padding=(2, 2),
        )


        # ── Global tk palette for non-ttk widgets (Canvas, Text, etc.) ──
        self.root.tk_setPalette(
            background=pal["bg"],
            foreground=pal["text"],
            highlightColor=accent,
            selectBackground=pal["selected_bg"],
            selectForeground=pal["selected_fg"],
            activeBackground=accent,
            activeForeground=pal["text"],
            troughColor=pal["panel2"],
            disabledforeground=pal["muted"],
        )

        style.configure("TLabel", background=pal["bg"], foreground=pal["text"])
        style.configure("Muted.TLabel", background=pal["bg"], foreground=pal["muted"])

        # Apply FrogSwamp special effects
        button_radius = pal.get("button_radius", 0)
        hover_color = pal.get("hover_transition", "") or pal["button_hover"]
        focus_color = pal.get("focus_color", "") or accent
        
        style.configure("TButton",
            background=pal["panel2"],
            foreground=plain_btn_fg,
            relief="flat",
            borderwidth=0,
            padding=(8, 5),
            focusthickness=1,
            focuscolor=focus_color,
            # Lily pad rounded corners (simulated with border)
            bordercolor=border if button_radius == 0 else pal.get("glow_color", accent),
        )
        hover_fg = _readable_fg(
            pal.get("button_hover_fg", plain_btn_fg),
            COLOR_NEAR_BLACK, COLOR_WHITE, hover_color, min_ratio=2.0)
        style.map("TButton",
            background=[("active", hover_color), ("hover", hover_color), ("pressed", pal["tabsel"])],
            foreground=[("active", hover_fg), ("hover", hover_fg), ("pressed", pressed_btn_fg)],
            relief=[("active", "flat"), ("hover", "flat"), ("pressed", "flat")],
            bordercolor=[("focus", focus_color)],
        )

        style.configure("Accent.TButton",
            background=accent,
            foreground=accent_btn_fg,
            relief="flat",
            borderwidth=0,
            padding=(8, 5),
        )
        style.map("Accent.TButton",
            background=[("active", self._lighten_color(accent, 20)), ("hover", self._lighten_color(accent, 20)), ("pressed", self._darken_color(accent, 20))],
            foreground=[("active", accent_btn_fg), ("hover", accent_btn_fg), ("pressed", accent_btn_fg)],
        )

        style.configure("Active.TButton",
            background=pal["progress"],
            foreground=progress_btn_fg,
            relief="flat",
            borderwidth=0,
            padding=(8, 5),
        )
        style.map("Active.TButton",
            background=[("active", self._lighten_color(pal["progress"], 20)), ("hover", self._lighten_color(pal["progress"], 20)), ("pressed", self._darken_color(pal["progress"], 20))],
            foreground=[("active", progress_btn_fg), ("hover", progress_btn_fg), ("pressed", progress_btn_fg)],
        )

        # Bioluminescent glow effect for FrogSwamp themes
        glow_color = pal.get("glow_color", accent)
        glow_intensity = pal.get("glow_intensity", 0)
        
        style.configure("TEntry",
            fieldbackground=pal["bg"],
            foreground=pal["text"],
            insertcolor=pal["text"],
            insertwidth=2,
            relief="flat",
            borderwidth=0,
            padding=(4, 3),
        )
        style.map("TEntry",
            fieldbackground=[("focus", pal["panel2"])],
        )

        # Frog-eye focus indicators and water ripple hover effects
        style.configure("TCombobox",
            fieldbackground=pal["bg"],
            foreground=pal["text"],
            selectbackground=pal["selected_bg"],
            selectforeground=pal["selected_fg"],
            relief="flat",
            borderwidth=0,
            padding=(4, 3),
            focuscolor=focus_color,
        )
        style.map("TCombobox",
            fieldbackground=[("focus", pal["panel2"]), ("readonly", pal["bg"])],
            foreground=[("readonly", pal["text"])],
            selectbackground=[("active", hover_color), ("readonly", pal["selected_bg"])],
        )

        style.configure("TCheckbutton",
            background=pal["bg"],
            foreground=pal["text"],
            indicatorcolor=pal["panel2"],
            indicatorrelief="flat",
            indicatormargin=(4, 2),
        )
        style.map("TCheckbutton",
            background=[("active", pal["bg"])],
            indicatorcolor=[("selected", accent)],
        )

        style.configure("TRadiobutton",
            background=pal["bg"],
            foreground=pal["text"],
            indicatorcolor=pal["panel2"],
            indicatormargin=(4, 2),
        )
        style.map("TRadiobutton",
            background=[("active", pal["bg"])],
            indicatorcolor=[("selected", accent)],
        )

        style.configure("TNotebook",
            background=pal["bg"],
            borderwidth=0,
            relief="flat",
        )
        style.configure("TNotebook.Tab",
            background=pal["tabbg"],
            foreground=pal["muted"],
            padding=(16, 9),
            relief="flat",
            borderwidth=0,
        )
        style.map("TNotebook.Tab",
            background=[("selected", pal["panel"]), ("active", pal["panel2"])],
            foreground=[("selected", pal["text"]), ("active", pal["text"])],
        )

        style.configure("Horizontal.TProgressbar",
            background=accent,
            troughcolor=pal["panel2"],
            borderwidth=0,
            relief="flat",
            thickness=14,
        )
        style.configure("Vertical.TProgressbar",
            background=accent,
            troughcolor=pal["panel2"],
            borderwidth=0,
            relief="flat",
        )

        # ── TSpinbox (rounded, consistent with TEntry) ──
        style.configure("TSpinbox",
            fieldbackground=pal["bg"],
            foreground=pal["text"],
            insertcolor=pal["text"],
            insertwidth=2,
            relief="flat",
            borderwidth=0,
            padding=(4, 3),
            arrowcolor=pal["muted"],
        )
        style.map("TSpinbox",
            fieldbackground=[("focus", pal["panel2"])],
            arrowcolor=[("active", accent)],
        )

        # ── TScale (sliders) ──
        style.configure("TScale",
            background=pal["bg"],
            troughcolor=pal["border_color"],
            borderwidth=0,
            sliderlength=18,
        )
        style.map("TScale",
            background=[("active", pal["bg"])],
        )

        # ── Enhanced TButton padding for icon+text compound buttons ──
        style.configure("Icon.TButton",
            background=pal["panel2"],
            foreground=plain_btn_fg,
            relief="flat",
            borderwidth=0,
            padding=(6, 5, 10, 5),  # extra right padding when icon is present
            focusthickness=1,
            focuscolor=accent,
        )
        style.map("Icon.TButton",
            background=[("active", pal["button_hover"]), ("hover", pal["button_hover"]), ("pressed", pal["tabsel"])],
            foreground=[("active", hover_fg), ("hover", hover_fg), ("pressed", pressed_btn_fg)],
        )

        # ── Separator spacing ──
        style.configure("Spacy.TSeparator",
            background=pal["border_color"],
            padding=(0, 6),
        )

        # ── Treeview (if used anywhere) ──
        style.configure("Treeview",
            background=pal["entrybg"],
            foreground=pal["entryfg"],
            fieldbackground=pal["entrybg"],
            borderwidth=0,
            rowheight=26,
        )
        style.map("Treeview",
            background=[("selected", pal["tabsel"])],
            foreground=[("selected", pal["text"])],
        )
        style.configure("Treeview.Heading",
            background=pal["panel2"],
            foreground=pal["text"],
            font=("Segoe UI", 9, "bold"),
            padding=(8, 4),
        )

        style.configure("Vertical.TScrollbar",
            background=pal["scrollbar_fg"],
            troughcolor=pal["panel2"],
            borderwidth=0,
            relief="flat",
            arrowsize=12,
        )
        style.configure("Horizontal.TScrollbar",
            background=pal["scrollbar_fg"],
            troughcolor=pal["panel2"],
            borderwidth=0,
            relief="flat",
            arrowsize=12,
        )
        style.map("Vertical.TScrollbar",
            background=[("active", accent)],
        )
        style.map("Horizontal.TScrollbar",
            background=[("active", accent)],
        )

        style.configure("TSeparator", background=pal["border_color"])

        self._update_all_entry_cursors()

        if hasattr(self, "prompttext"):
            self.prompttext.configure(
                bg=pal["entrybg"],
                fg=pal["entryfg"],
                insertbackground=pal["text"],
                selectbackground=pal["selected_bg"],
                selectforeground=pal["selected_fg"],
            )
        elif hasattr(self, "prompt_text"):
            self.prompt_text.configure(
                bg=pal["entrybg"],
                fg=pal["entryfg"],
                insertbackground=pal["text"],
                selectbackground=pal["selected_bg"],
                selectforeground=pal["selected_fg"],
            )

        canvas_bg = pal["bg"]
        accent = pal.get("accent", pal["progress"])

        if hasattr(self, "gallery_canvas"):
            self.gallery_canvas.configure(bg=canvas_bg, highlightthickness=0)
        if hasattr(self, "gallery_inner"):
            self.gallery_inner.configure(style="Inner.TFrame")
        if hasattr(self, "settings_canvas"):
            self.settings_canvas.configure(bg=canvas_bg, highlightthickness=0)
        if hasattr(self, "settings_inner"):
            self.settings_inner.configure(style="Inner.TFrame")
        # Re-theme cloud cards + sync options (tk widgets with hardcoded colours)
        self._retheme_settings_cloud_widgets(pal)
        if hasattr(self, "prompt_builder_canvas"):
            self.prompt_builder_canvas.configure(bg=canvas_bg, highlightthickness=0)
        if hasattr(self, "templatecanvas"):
            self.templatecanvas.configure(bg=pal["bg"], highlightthickness=0)
        if hasattr(self, "gallery_fav_canvas"):
            self.gallery_fav_canvas.configure(bg=canvas_bg, highlightthickness=0)
        if hasattr(self, "gallery_fav_inner"):
            self.gallery_fav_inner.configure(style="Inner.TFrame")
        if hasattr(self, "gallery_styled_canvas"):
            self.gallery_styled_canvas.configure(bg=canvas_bg, highlightthickness=0)
        if hasattr(self, "gallery_styled_inner"):
            self.gallery_styled_inner.configure(style="Inner.TFrame")
        if hasattr(self, "gallery_manual_canvas"):
            self.gallery_manual_canvas.configure(bg=canvas_bg, highlightthickness=0)
        if hasattr(self, "gallery_manual_inner"):
            self.gallery_manual_inner.configure(style="Inner.TFrame")

        # Re-theme all gallery card widgets (cards, placeholders, labels)
        self._retheme_gallery_widgets(pal)

        # ── Re-theme negative prompt area labels ──
        # These tk.Label widgets use hardcoded fg colors at creation time
        # and are NOT handled by _retheme_child_widgets (which only covers
        # gallery frames).
        self._retheme_neg_prompt_labels(pal)

        # Clear icon cache so icons re-render in new accent colour
        try:
            from icons import clear_cache
            clear_cache()
        except Exception:
            pass

        # Apply toolbar icons (rendered via PIL) after theme colours are set
        if hasattr(self, '_gallery_tab'):
            try:
                self._gallery_tab._apply_toolbar_icons()
            except Exception:
                pass

        # Apply sidebar and action icons
        self._apply_sidebar_icons(accent)

        if hasattr(self, "image_label"):
            self.image_label.configure(bg=pal["panel"], fg=pal["muted"],
                                       highlightthickness=0)
        if hasattr(self, "preview_details_frame"):
            self.preview_details_frame.configure(style="Inner.TFrame")
        if hasattr(self, "progress_overlay_label"):
            self.progress_overlay_label.configure(bg=accent, fg=accent_btn_fg)
        # The image preview's progress overlay label is created in
        # prompt_tab.py:1390 with no explicit colours, so without this
        # re-theme it stays on whatever tk_setPalette chose at creation
        # time — which on some platforms renders as a flat grey pill
        # instead of the themed accent colour.
        if hasattr(self, "image_progress_overlay_label") and self.image_progress_overlay_label.winfo_exists():
            try:
                self.image_progress_overlay_label.configure(
                    bg=accent, fg=accent_btn_fg,
                )
            except (tk.TclError, AttributeError):
                pass

        if hasattr(self, "templatevarscrollcanvas"):
            self.templatevarscrollcanvas.configure(bg=pal["panel"], highlightthickness=0)
        if hasattr(self, "templatevarrows"):
            pass

        if hasattr(self, "templatevarrows"):
            for child in self.templatevarrows.winfo_children():
                try:
                    if isinstance(child, tk.Frame):
                        child.configure(bg=pal["panel"])
                    elif isinstance(child, tk.Label):
                        child.configure(bg=pal["panel"], fg=pal["text"])
                except Exception:
                    pass

                try:
                    for grandchild in child.winfo_children():
                        if isinstance(grandchild, tk.Frame):
                            grandchild.configure(bg=pal["panel"])
                        elif isinstance(grandchild, tk.Label):
                            grandchild.configure(bg=pal["panel"], fg=pal["text"])
                        elif isinstance(grandchild, tk.Entry):
                            grandchild.configure(
                                bg=pal["entrybg"],
                                fg=pal["entryfg"],
                                insertbackground=pal["text"],
                                relief="flat",
                            )
                        elif isinstance(grandchild, tk.Text):
                            grandchild.configure(
                                bg=pal["entrybg"],
                                fg=pal["entryfg"],
                                insertbackground=pal["text"],
                                relief="flat",
                            )
                except Exception:
                    pass

        # ── UI Effects: Gradient backgrounds, shadows, glassmorphism ──
        if UI_EFFECTS_AVAILABLE:
            self._apply_ui_effects(pal, accent, border)

        if hasattr(self, "themelist"):
            self.themelist.configure(
                bg=pal["entrybg"],
                fg=pal["entryfg"],
                selectbackground=pal["selected_bg"],
                selectforeground=pal["selected_fg"],
            )

        # Theme the new sidebar elements (tk.Frame / tk.Label widgets)
        if hasattr(self, "_sidebar_outer"):
            self._sidebar_outer.configure(bg=pal["panel"], highlightthickness=0, bd=0)
        if hasattr(self, "_sidebar_canvas"):
            self._sidebar_canvas.configure(bg=pal["panel"], highlightthickness=0)
        if hasattr(self, "_sidebar"):
            self._sidebar.configure(bg=pal["panel"])
        if hasattr(self, "_sidebar_logo_label") and self._sidebar_logo_label:
            self._sidebar_logo_label.configure(bg=pal["panel"])
        for attr in ("title_label",
                      "_sidebar_mode_lbl",
                      "_sidebar_lighting_lbl", "_sidebar_color_lbl",
                      "_sidebar_subj_lbl", "_sidebar_setting_lbl",
                      "_sidebar_atm_lbl", "_sidebar_mood_lbl",
                      "_sidebar_neg_lbl", "_sidebar_cn_lbl"):
            w = getattr(self, attr, None)
            if w and isinstance(w, tk.Label):
                w.configure(bg=pal["panel"], fg=pal["text"])
        if hasattr(self, "_generate_btn"):
            if UI_EFFECTS_AVAILABLE and hasattr(self, '_rounded_gen_btn') and self._rounded_gen_btn:
                # RoundedButton — re-render via _apply_ui_effects
                pass
            else:
                self._generate_btn.configure(
                    bg=accent, fg=accent_btn_fg,
                    activebackground=pal["button_hover"],
                    activeforeground=hover_fg,
                )
        if hasattr(self, "_generate_prompt_btn"):
            if UI_EFFECTS_AVAILABLE and hasattr(self, '_rounded_prompt_btn') and self._rounded_prompt_btn:
                pass
            else:
                self._generate_prompt_btn.configure(
                    bg=accent, fg=accent_btn_fg,
                    activebackground=pal["button_hover"],
                    activeforeground=hover_fg,
                )

        # ── Re-theme the settings popup (if open) ──
        # The popup uses tk.Frame widgets with explicit bg= values that
        # are frozen at creation time and are NOT covered by the global
        # ttk style update above.
        if (hasattr(self, '_settings_win') and self._settings_win
                and self._settings_win.winfo_exists()):
            try:
                self._settings_tab._retheme_settings_popup(pal)
            except Exception:
                pass

        # ── De-grey any classic widgets still holding sv_ttk / system
        # neutral colours from earlier this session (exact-match
        # replacement — intentionally-coloured widgets are untouched).
        try:
            self._retheme_sv_ttk_classic_widgets(pal)
        except Exception as e:
            logger.debug("classic widget de-grey pass failed: %s", e)

        # ── Deferred safety pass ──
        # Any <<ThemeChanged>> handlers that still fire after this method
        # (or third-party palette flips) get corrected on the next idle
        # cycle: the classic-widget de-grey runs again and the ttk '.'
        # base style is re-asserted with the FrogPaper palette.
        try:
            self.root.after_idle(
                lambda p=dict(pal): self._reassert_theme_palette(p))
        except Exception:
            pass

        # ── Keyboard focus visibility pass ──
        # Every classic (tk) button-like widget gets a visible focus ring
        # so keyboard users can see where they are. Re-runs on every
        # theme change so ring colors stay palette-fresh. Label-based
        # custom buttons (RoundedButton, popup stars) manage their own
        # rings; ttk widgets get focus visuals from the style layer.
        try:
            from ui_effects import ensure_visible_focus_indicators
            ensure_visible_focus_indicators(
                self.root,
                pal.get("border_color", COLOR_GRAY_700),
                pal.get("accent", "#5aad78"),
            )
        except Exception as e:
            logger.debug("focus indicator pass failed: %s", e)

        config = load_config()
        config["app_theme"] = theme_name
        save_config(config)

    # ── sv_ttk de-greying helpers ────────────────────────────────────────

    def _sv_ttk_palette_colors(self):
        """Read sv_ttk's neutral palettes from both theme namespaces."""
        colors = {"bg": set(), "fg": set(), "selbg": set(),
                  "selfg": set(), "disfg": set()}
        for ns in ("ttk::theme::sv_dark", "ttk::theme::sv_light"):
            for key in ("bg", "fg", "selbg", "selfg", "disfg"):
                try:
                    v = self.root.tk.call("set", f"{ns}::colors(-{key})")
                    if isinstance(v, str) and v.startswith("#"):
                        colors[key].add(v.lower())
                except Exception:
                    pass
        return colors

    def _retheme_sv_ttk_classic_widgets(self, pal):
        """Replace leftover sv_ttk / system neutral colours on classic tk widgets.

        tk_setPalette can only recolor widgets that still hold the
        PREVIOUS palette value.  Widgets that were already re-greyed by
        sv_ttk's asynchronous configure_colors() (or created while sv_ttk
        owned the option database) keep their neutral colours forever —
        visible as grey patches in the sidebar and prompt builder.

        This walker fixes them with EXACT colour matching, so any widget
        that was intentionally styled (accent buttons, overlays, icons)
        is never touched.

        Subtree awareness: classic widgets inside the sidebar are painted
        pal["panel"] (the sidebar surface), everything else pal["bg"].
        """
        sv = self._sv_ttk_palette_colors()

        grey_bg = set(sv["bg"]) | {
            "#1c1c1c", "#292929", "#fafafa", "#f9f9f9", "#f0f0f0",
            "#e7e7e7", "#e0e0e0", "#d9d9d9", "#d4d0c8", "#cccccc",
            "systembuttonface", "system3dface", "systemwindow",
        }
        grey_fg = set(sv["fg"]) | {
            "#fafafa", "#1c1c1c", "systembuttontext", "systemwindowtext",
        }
        grey_selbg = set(sv["selbg"]) | {"#2f60d8", "systemhighlight"}
        grey_selfg = set(sv["selfg"]) | {"systemhighlighttext"}
        grey_disfg = set(sv["disfg"]) | {"#595959", "#a0a0a0",
                                         "systemdisabledtext"}

        base_bg = pal["bg"]
        panel = pal.get("panel", base_bg)
        accent = pal.get("accent", pal.get("progress", ""))
        text_fg = pal.get("text", COLOR_WHITE)
        muted = pal.get("muted", COLOR_MID_GRAY)

        # Intentional button colours — never recolor their fg
        keep_fg_bgs = {accent.lower(),
                       str(pal.get("button_hover", "")).lower(),
                       str(pal.get("progress", "")).lower()}

        # Subtree anchors that use the panel surface
        anchors = []
        for attr in ("_sidebar_outer",):
            w = getattr(self, attr, None)
            if w is not None:
                try:
                    anchors.append((str(w), panel))
                except Exception:
                    pass

        def _norm(c):
            if not isinstance(c, str) or not c:
                return None
            c = c.strip().lower()
            if c.startswith("#") and len(c) == 4:
                c = "#" + "".join(ch * 2 for ch in c[1:])
            return c

        def _bg_for_path(path):
            for prefix, col in anchors:
                if path == prefix or path.startswith(prefix + "."):
                    return col
            return base_bg

        def _walk(widget):
            try:
                children = widget.winfo_children()
            except Exception:
                return
            for child in children:
                try:
                    cls = child.winfo_class()
                    path = str(child)
                except Exception:
                    continue
                if not cls.startswith("T"):
                    try:
                        cfg = set(child.configure())
                        new_bg = _bg_for_path(path)
                        cur_bg = None
                        for opt in ("bg", "background"):
                            if opt in cfg:
                                cur_bg = _norm(child.cget(opt))
                                break
                        target_bg = new_bg

                        def _set(option, value):
                            try:
                                child.configure({option: value})
                            except (tk.TclError, Exception):
                                pass

                        # Background-family → themed surface
                        if cur_bg in grey_bg:
                            for opt in ("bg", "background"):
                                if opt in cfg:
                                    _set(opt, target_bg)
                            if "highlightbackground" in cfg:
                                _set("highlightbackground", target_bg)

                        # highlightcolor (focus ring) → accent
                        if "highlightcolor" in cfg:
                            cur_hl = _norm(child.cget("highlightcolor"))
                            if cur_hl in grey_selbg:
                                _set("highlightcolor", accent)

                        # Foreground-family → themed text
                        for opt in ("fg", "foreground", "activeforeground"):
                            if opt in cfg:
                                cur = _norm(child.cget(opt))
                                if cur in grey_fg:
                                    # Skip intentionally-contrasting buttons
                                    if cur_bg in keep_fg_bgs:
                                        continue
                                    _set(opt, text_fg)

                        # Active background → hover colour
                        if "activebackground" in cfg:
                            cur_ab = _norm(child.cget("activebackground"))
                            if cur_ab in grey_selbg:
                                _set("activebackground",
                                     pal.get("button_hover", accent))

                        # Selection colours
                        if "selectbackground" in cfg:
                            cur_sb = _norm(child.cget("selectbackground"))
                            if cur_sb in (grey_selbg | grey_bg):
                                _set("selectbackground",
                                     pal.get("selected_bg", accent))
                        if "selectforeground" in cfg:
                            cur_sf = _norm(child.cget("selectforeground"))
                            if cur_sf in grey_selfg:
                                _set("selectforeground",
                                     pal.get("selected_fg", text_fg))

                        # Disabled foreground → muted
                        if "disabledforeground" in cfg:
                            cur_df = _norm(child.cget("disabledforeground"))
                            if cur_df in grey_disfg:
                                _set("disabledforeground", muted)

                        # Insert cursor → text colour (black cursors are
                        # invisible on dark themes)
                        for opt in ("insertbackground",):
                            if opt in cfg:
                                cur_ib = _norm(child.cget(opt))
                                if cur_ib in (COLOR_BLACK, "black",
                                              "systemwindowtext",
                                              "systembuttontext"):
                                    _set(opt, text_fg)
                    except Exception:
                        pass
                _walk(child)

        _walk(self.root)

    def _reassert_theme_palette(self, pal):
        """Final idle-cycle safety pass after apply_theme().

        Re-asserts the FrogPaper palette on the ttk '.' base style and
        de-greys any classic widget that an asynchronously-fired
        <<ThemeChanged>> handler (or third-party code) may have flipped
        back to sv_ttk's neutral colours.
        """
        try:
            style = ttk.Style(self.root)
            style.configure(".",
                background=pal["bg"],
                foreground=pal["text"],
                fieldbackground=pal["entrybg"],
                relief="flat",
                borderwidth=0,
            )
            style.configure("TFrame", background=pal["bg"])
            style.configure("TLabel",
                background=pal["bg"], foreground=pal["text"])
        except Exception:
            pass
        try:
            self._retheme_sv_ttk_classic_widgets(pal)
        except Exception:
            pass

    def _apply_ui_effects(self, pal, accent, border):
        """Apply visual enhancements (rounded buttons, shadows, etc.)."""
        try:
            # Accent buttons keep white/dark text per WCAG contrast on accent
            accent_fg = _readable_fg(pal.get("button_fg", COLOR_WHITE),
                                     COLOR_NEAR_BLACK, COLOR_WHITE, accent)
            # ── Re-render sidebar buttons with theme accent color ──
            if hasattr(self, '_rounded_gen_btn') and self._rounded_gen_btn:
                self._rounded_gen_btn.fill_color = accent
                self._rounded_gen_btn.text_color = accent_fg
                self._rounded_gen_btn.gradient_end = self._lighten_color(
                    accent, 20)
                self._rounded_gen_btn._render_images(
                    self._rounded_gen_btn.width, self._rounded_gen_btn.height)
                self._rounded_gen_btn._on_leave()
            if hasattr(self, '_rounded_prompt_btn') and self._rounded_prompt_btn:
                self._rounded_prompt_btn.fill_color = accent
                self._rounded_prompt_btn.text_color = accent_fg
                self._rounded_prompt_btn.gradient_end = self._lighten_color(
                    accent, 20)
                self._rounded_prompt_btn._render_images(
                    self._rounded_prompt_btn.width, self._rounded_prompt_btn.height)
                self._rounded_prompt_btn._on_leave()

        except Exception as e:
            logger.debug(f"UI effects apply error: {e}")

