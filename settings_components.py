"""
Reusable settings UI components for FrogPaper.
Provides polished, consistent building blocks for the settings page.
"""

import itertools
import re
import tkinter as tk
from tkinter import ttk
import webbrowser
import logging

logger = logging.getLogger(__name__)

# Matches explicit http(s):// URLs AND bare website domains written in
# prose (e.g. "dash.cloudflare.com", "huggingface.co", "pollinations.ai").
# Bare domains are opened with an https:// prefix. Stops at whitespace and
# quote/angle-bracket delimiters; trailing sentence punctuation that got
# glued to the address is trimmed at match-use time. TLD list is a safe
# allow-list (no .py/.spec/.json style false positives).
_LINK_RE = re.compile(
    r"(?:https?://[^\s\"'<>]+)"
    r"|(?:\b(?:[\w-]+\.)+(?:com|org|net|io|ai|co|dev|app|gg|me)\b(?:/[^\s\"'<>]*)?)",
    re.IGNORECASE,
)

# Monotonic tag counter so re-linking a widget whose content was replaced
# never inherits stale click bindings from a previous tag of the same name.
_LINK_SEQ = itertools.count()


def _default_open(event, url):
    """Open *url* in the default browser, swallowing errors."""
    try:
        webbrowser.open(url, new=2)
    except Exception:
        logger.exception("failed to open link %r", url)


def linkify_text_widget(text_widget, body=None, link_color="#60a5fa",
                        on_open=None):
    """Tag website links inside a ``tk.Text`` as clickable.

    Finds every http(s):// URL and bare domain (dash.cloudflare.com,
    huggingface.co, ...) in *body* (defaults to the widget's full content),
    paints it with *link_color* + underline + hand cursor, and binds
    <Button-1> to open it in the default browser.

    Args:
        text_widget: the ``tk.Text`` to tag (read-only state is fine).
        body: exact text the offsets refer to; ``None`` reads the widget.
        link_color: accent colour for the link ranges.
        on_open: ``callable(event, url)``; defaults to ``webbrowser.open``.

    Returns:
        list of ``(tag_name, openable_url)`` pairs, in document order.
    """
    if body is None:
        body = text_widget.get("1.0", "end")
    on_open = on_open or _default_open
    tags = []
    for m in _LINK_RE.finditer(body):
        url = m.group(0)
        end = m.end()
        # Don't swallow trailing sentence punctuation into the address.
        while url and url[-1] in ".,;:)":
            url = url[:-1]
            end -= 1
        if not url:
            continue
        open_url = url if url.lower().startswith("http") else "https://" + url
        tag = f"link{next(_LINK_SEQ)}"
        try:
            text_widget.tag_configure(tag, foreground=link_color, underline=True)
            text_widget.tag_add(tag, f"1.0+{m.start()}c", f"1.0+{end}c")
            text_widget.tag_bind(tag, "<Enter>",
                                 lambda e: text_widget.config(cursor="hand2"))
            text_widget.tag_bind(tag, "<Leave>",
                                 lambda e: text_widget.config(cursor="arrow"))
            text_widget.tag_bind(tag, "<Button-1>",
                                 lambda e, u=open_url: on_open(e, u))
        except tk.TclError:
            continue
        tags.append((tag, open_url))
    return tags


class SetupGuideText(tk.Frame):
    """Read-only, auto-sizing, link-enabled step list for cloud setup guides.

    Replaces the plain numbered ``tk.Label`` stack inside the cloud cards'
    "How to get your credentials" guide:

    * every http(s) URL in a step is rendered as an inline clickable link
      (accent colour + underline + hand cursor, opens in the default browser);
    * the embedded ``tk.Text`` wraps to the widget's *actual* pixel width,
      so step text is never clipped by the sidebar/padding like the old
      fixed ``wraplength=550`` labels were;
    * the Text height is auto-synced to its content, so the whole guide is
      visible with no internal scrolling.
    """

    def __init__(self, parent, steps, bg="#22252a", fg="#9ca3af", link=None,
                 font=("Segoe UI", 9)):
        super().__init__(parent, bg=bg)
        self._bg = bg
        self._fg = fg
        self._link = link or fg  # resolved caller-side to the accent colour

        self.text = tk.Text(
            self,
            wrap="word",
            relief="flat",
            bd=0,
            highlightthickness=0,
            bg=bg,
            fg=fg,
            font=font,
            cursor="arrow",
            state="disabled",
            padx=0,
            pady=0,
            spacing1=2,   # small breathing room above each display line block
            spacing3=2,
            height=4,     # provisional; _sync_height() fits it to content
        )
        self.text.pack(fill="both", expand=True)
        self.text.configure(selectbackground=self._link,
                            inactiveselectbackground=self._link)

        # ── Content: numbered steps separated by blank lines ──
        body = "\n\n".join(f"{i}. {step}" for i, step in enumerate(steps, 1))
        self.text.configure(state="normal")
        self.text.insert("1.0", body)

        # ── Tag every URL occurrence as an individual link ──
        self._tags = linkify_text_widget(
            self.text,
            body=body,
            link_color=self._link,
            on_open=self._open_link,
        )

        self.text.configure(state="disabled")

        # ── Auto-height so all steps stay fully visible ──
        self._last_h = None
        self.text.bind("<Configure>", lambda e: self.after_idle(self._sync_height))
        self.after_idle(self._sync_height)
        self.bind("<Configure>", lambda e: self.after_idle(self._sync_height))

    def _open_link(self, event, url):
        try:
            webbrowser.open(url, new=2)
        except Exception:
            logger.exception("failed to open setup link %r", url)

    def _sync_height(self):
        """Size the Text to exactly fit its wrapped content (no inner scroll)."""
        if not self.winfo_exists():
            return
        res = None
        try:
            res = self.text.count("1.0", "end", "displaylines")
        except Exception:
            pass
        if isinstance(res, (tuple, list)):
            n = int(res[0]) if res and res[0] else 1
        elif isinstance(res, int):
            n = max(res, 1)
        else:
            n = 1
        n += 1  # one spare line so the last spacing3 padding never clips
        if n != self._last_h:
            self._last_h = n
            try:
                self.text.configure(height=n)
            except tk.TclError:
                pass

    def apply_colors(self, bg=None, fg=None, link=None):
        """Re-paint widget for a theme switch (called from update_theme)."""
        if bg is not None:
            self._bg = bg
            self.configure(bg=bg)
        if fg is not None:
            self._fg = fg
        if link is not None:
            self._link = link
        try:
            kw = {}
            if bg is not None:
                kw["bg"] = bg
            if fg is not None:
                kw["fg"] = fg
            if kw:
                self.text.configure(**kw)
            for tag, _url in self._tags:
                self.text.tag_configure(tag, foreground=self._link, underline=True)
        except tk.TclError:
            pass


class StatusBadge:
    """Reusable status badge with color-coded states."""
    
    COLORS = {
        "connected": "#22c55e",
        "not_connected": "#6b7280",
        "error": "#ef4444",
        "success": "#22c55e",
        "warning": "#f59e0b",
        "info": "#3b82f6"
    }
    
    @staticmethod
    def create(parent, text, status="not_connected", size="small"):
        """
        Create a status badge widget.
        
        Args:
            parent: Parent widget
            text: Badge text
            status: Status key (connected, not_connected, error, etc.)
            size: "small" or "normal"
        """
        bg_color = StatusBadge.COLORS.get(status, "#6b7280")
        font_size = 8 if size == "small" else 9
        
        frame = tk.Frame(parent, bg=bg_color, padx=8, pady=2)
        
        label = tk.Label(
            frame,
            text=text,
            font=("Segoe UI", font_size),
            fg="white",
            bg=bg_color
        )
        label.pack()
        
        return frame


class SettingRow:
    """
    Standardized setting row with label, control, and optional helper text.
    Provides consistent spacing and alignment.
    """
    
    def __init__(self, parent, label_text, control_widget, helper_text=None, 
                 label_width=180, row_padding=12, palette=None):
        """
        Create a setting row.
        
        Args:
            parent: Parent widget
            label_text: Label text
            control_widget: The control widget (Entry, Combobox, etc.)
            helper_text: Optional helper text below the control
            label_width: Width of label column for alignment
            row_padding: Vertical padding
            palette: Color palette dict
        """
        self.parent = parent
        self.palette = palette or {}
        self._muted = self.palette.get("muted", "#9ca3af")
        self._text = self.palette.get("text", "#e5e7eb")
        self._card_bg = self.palette.get("card_bg", self.palette.get("bg", "#1f2937"))
        
        # Create row frame
        self.frame = tk.Frame(parent, bg=self._card_bg)
        self.frame.pack(fill="x", pady=row_padding)
        self.frame.columnconfigure(1, weight=1)
        # Tag this widget so the settings popup's recursive theme
        # walker can discover this SettingRow instance and call
        # ``update_theme`` on it when the user switches themes.
        self.frame._fp_component = self
        
        # Label
        self.label = tk.Label(
            self.frame,
            text=label_text,
            font=("Segoe UI", 10),
            fg=self._text,
            bg=self._card_bg,
            anchor="w",
            width=int(label_width / 8)  # Approximate character width
        )
        self.label.grid(row=0, column=0, sticky="w", padx=16)
        
        # Control
        control_widget.grid(row=0, column=1, sticky="w")
        
        # Helper text
        if helper_text:
            self.helper = tk.Label(
                self.frame,
                text=helper_text,
                font=("Segoe UI", 9),
                fg=self._muted,
                bg=self._card_bg,
                wraplength=500,
                justify="left",
                anchor="w"
            )
            self.helper.grid(row=1, column=0, columnspan=2, sticky="w", pady=4, padx=16)
    
    def get_frame(self):
        return self.frame

    def update_theme(self, palette):
        """Re-paint this row's tk widgets to match a new theme palette.

        Called by ``SettingsTab._retheme_settings_popup`` so that rows
        created in a previous theme do not stay frozen on the old colours
        when the user switches themes while the settings popup is open.
        """
        try:
            self.palette = palette or {}
            new_muted   = self.palette.get("muted",   self._muted)
            new_text    = self.palette.get("text",    self._text)
            new_card_bg = self.palette.get("card_bg", self.palette.get("bg", self._card_bg))

            self._muted   = new_muted
            self._text    = new_text
            self._card_bg = new_card_bg

            self.frame.configure(bg=new_card_bg)
            self.label.configure(bg=new_card_bg, fg=new_text)
            if getattr(self, "helper", None) is not None:
                try:
                    self.helper.configure(bg=new_card_bg, fg=new_muted)
                except (tk.TclError, AttributeError):
                    pass
        except (tk.TclError, AttributeError):
            pass


class SettingCard:
    """
    Card container for grouping related settings.
    Provides visual grouping with subtle background and border.
    Includes hover highlight for premium interactivity.
    """
    
    def __init__(self, parent, title=None, description=None, palette=None, 
                 accent_color=None, padding=16):
        """
        Create a settings card.
        
        Args:
            parent: Parent widget
            title: Optional card title
            description: Optional card description
            palette: Color palette dict
            accent_color: Optional accent color for left border
            padding: Internal padding
        """
        self.parent = parent
        self.palette = palette or {}
        self._bg = self.palette.get("bg", "#111827")
        self._card_bg = self.palette.get("card_bg", "#1f2937")
        self._card_bg_hover = self._lighten(self._card_bg, 8)
        self._text = self.palette.get("text", "#e5e7eb")
        self._muted = self.palette.get("muted", "#9ca3af")
        self._accent = accent_color or self.palette.get("accent", "#8b5cf6")
        self._border = self.palette.get("border_color", "#374151")
        self._border_hover = self._lighten(self._border, 15)
        
        # Outer frame with spacing
        self.outer = tk.Frame(parent, bg=self._bg)
        self.outer.pack(fill="x", pady=16)
        # Tag this widget so the settings popup's recursive theme
        # walker can discover this SettingCard instance and call
        # ``update_theme`` on it when the user switches themes.
        self.outer._fp_component = self
        
        # Accent bar (left border)
        self.accent_bar = tk.Frame(self.outer, bg=self._accent, width=3)
        self.accent_bar.pack(side="left", fill="y")
        
        # Card body
        self.card = tk.Frame(
            self.outer,
            bg=self._card_bg,
            padx=padding,
            pady=padding,
            highlightthickness=1,
            highlightbackground=self._border
        )
        self.card.pack(side="left", fill="both", expand=True)
        self.card.columnconfigure(0, weight=1)
        
        # Hover effects on card
        self.card.bind("<Enter>", self._on_card_enter)
        self.card.bind("<Leave>", self._on_card_leave)
        
        # Title
        if title:
            self.title_label = tk.Label(
                self.card,
                text=title,
                font=("Segoe UI", 11, "bold"),
                fg=self._text,
                bg=self._card_bg,
                anchor="w"
            )
            self.title_label.grid(row=0, column=0, sticky="w", pady=4)
            self.title_label.bind("<Enter>", self._on_card_enter)
            self.title_label.bind("<Leave>", self._on_card_leave)
            self._row = 1
        else:
            self.title_label = None
            self._row = 0
        
        # Description
        if description:
            self.desc_label = tk.Label(
                self.card,
                text=description,
                font=("Segoe UI", 9),
                fg=self._muted,
                bg=self._card_bg,
                wraplength=600,
                justify="left",
                anchor="w"
            )
            self.desc_label.grid(row=self._row, column=0, sticky="w", pady=12)
            self.desc_label.bind("<Enter>", self._on_card_enter)
            self.desc_label.bind("<Leave>", self._on_card_leave)
            self._row += 1
            self._child_widgets = [self.title_label, self.desc_label] if self.title_label else [self.desc_label]
        else:
            self.desc_label = None
            self._child_widgets = [self.title_label] if self.title_label else []
        
        # Content frame for adding widgets
        self.content = tk.Frame(self.card, bg=self._card_bg)
        self.content.grid(row=self._row, column=0, sticky="ew")
        self.content.columnconfigure(0, weight=1)
        self.content.bind("<Enter>", self._on_card_enter)
        self.content.bind("<Leave>", self._on_card_leave)
    
    def _on_card_enter(self, event=None):
        """Highlight card border on hover for premium feel."""
        try:
            self.card.config(highlightbackground=self._border_hover)
        except tk.TclError:
            pass
    
    def _on_card_leave(self, event=None):
        """Restore card border on leave."""
        try:
            self.card.config(highlightbackground=self._border)
        except tk.TclError:
            pass
    
    @staticmethod
    def _lighten(hex_color, amount):
        """Lighten a hex color by a given amount (0-255)."""
        try:
            hex_color = hex_color.lstrip("#")
            r = min(255, max(0, int(hex_color[0:2], 16) + amount))
            g = min(255, max(0, int(hex_color[2:4], 16) + amount))
            b = min(255, max(0, int(hex_color[4:6], 16) + amount))
            return f"#{r:02x}{g:02x}{b:02x}"
        except (ValueError, IndexError):
            return hex_color
    
    def add_widget(self, widget, **grid_kwargs):
        """Add a widget to the card content area."""
        default_kwargs = {"sticky": "ew", "pady": 8}
        default_kwargs.update(grid_kwargs)
        widget.grid(row=self.content.grid_size()[1], column=0, **default_kwargs)

    def update_theme(self, palette):
        """Re-paint this card's tk widgets to match a new theme palette.

        Called by ``SettingsTab._retheme_settings_popup`` so cards created
        in a previous theme do not stay frozen on the old colours when
        the user switches themes while the settings popup is open.
        """
        try:
            self.palette = palette or {}
            new_bg       = self.palette.get("bg",          self._bg)
            new_card_bg  = self.palette.get("card_bg",     self._card_bg)
            new_text     = self.palette.get("text",        self._text)
            new_muted    = self.palette.get("muted",       self._muted)
            new_accent   = self.palette.get("accent",      self._accent)
            new_border   = self.palette.get("border_color", self._border)

            self._bg            = new_bg
            self._card_bg       = new_card_bg
            self._card_bg_hover = self._lighten(new_card_bg, 8)
            self._text          = new_text
            self._muted         = new_muted
            self._accent        = new_accent
            self._border        = new_border
            self._border_hover  = self._lighten(new_border, 15)

            # Outer spacing frame
            try:
                self.outer.configure(bg=new_bg)
            except (tk.TclError, AttributeError):
                pass
            # Accent bar
            try:
                self.accent_bar.configure(bg=new_accent)
            except (tk.TclError, AttributeError):
                pass
            # Card body + border
            try:
                self.card.configure(
                    bg=new_card_bg,
                    highlightbackground=new_border,
                )
            except (tk.TclError, AttributeError):
                pass
            # Title + description labels
            if self.title_label is not None:
                try:
                    self.title_label.configure(bg=new_card_bg, fg=new_text)
                except (tk.TclError, AttributeError):
                    pass
            if self.desc_label is not None:
                try:
                    self.desc_label.configure(bg=new_card_bg, fg=new_muted)
                except (tk.TclError, AttributeError):
                    pass
            # Content frame
            try:
                self.content.configure(bg=new_card_bg)
            except (tk.TclError, AttributeError):
                pass
        except (tk.TclError, AttributeError):
            pass

    def get_content(self):
        """Get the content frame for direct manipulation."""
        return self.content


class ExpandableSection:
    """
    Collapsible section with toggle button.
    Useful for advanced settings or detailed guides.
    """
    
    def __init__(self, parent, title, expanded=False, palette=None, accent_color=None):
        """
        Create an expandable section.
        
        Args:
            parent: Parent widget
            title: Section title
            expanded: Initial state
            palette: Color palette dict
            accent_color: Accent color for toggle
        """
        self.parent = parent
        self.palette = palette or {}
        self._card_bg = self.palette.get("card_bg", self.palette.get("bg", "#1f2937"))
        self._text = self.palette.get("text", "#e5e7eb")
        self._muted = self.palette.get("muted", "#9ca3af")
        self._accent = accent_color or self.palette.get("accent", "#8b5cf6")
        
        self._expanded = expanded

        # Toggle button
        self.toggle_frame = tk.Frame(parent, bg=self._card_bg)
        self.toggle_frame.pack(fill="x", pady=8)
        # Tag this widget so the settings popup's recursive theme
        # walker can discover this ExpandableSection instance and
        # call ``update_theme`` on it when the user switches themes.
        self.toggle_frame._fp_component = self
        
        self.toggle_btn = tk.Label(
            self.toggle_frame,
            text=f"{'▼' if expanded else '▶'} {title}",
            font=("Segoe UI", 9),
            fg=self._accent,
            bg=self._card_bg,
            cursor="hand2",
            anchor="w"
        )
        self.toggle_btn.pack(fill="x")
        self.toggle_btn.bind("<Button-1>", self._on_toggle)
        self.toggle_btn.bind("<Enter>", self._on_enter)
        self.toggle_btn.bind("<Leave>", self._on_leave)
        
        # Content frame
        self.content = tk.Frame(parent, bg=self._card_bg)
        if expanded:
            self.content.pack(fill="x", pady=8)
        else:
            self.content.pack_forget()
    
    def _on_toggle(self, event=None):
        self._expanded = not self._expanded
        self.toggle_btn.config(text=f"{'▼' if self._expanded else '▶'} {self.toggle_btn.cget('text')[2:]}")
        
        if self._expanded:
            self.content.pack(fill="x", pady=8)
        else:
            self.content.pack_forget()
    
    def _on_enter(self, event):
        self.toggle_btn.config(fg="#60a5fa")
    
    def _on_leave(self, event):
        self.toggle_btn.config(fg=self._accent)
    
    def add_widget(self, widget, **pack_kwargs):
        """Add a widget to the expandable content."""
        default_kwargs = {"fill": "x", "pady": 4}
        default_kwargs.update(pack_kwargs)
        widget.pack(**default_kwargs)

    def update_theme(self, palette):
        """Re-paint this section's tk widgets to match a new theme palette.

        Called by ``SettingsTab._retheme_settings_popup`` so sections created
        in a previous theme do not stay frozen on the old colours when
        the user switches themes while the settings popup is open.
        """
        try:
            self.palette = palette or {}
            new_card_bg = self.palette.get("card_bg", self.palette.get("bg", self._card_bg))
            new_text    = self.palette.get("text",     self._text)
            new_muted   = self.palette.get("muted",    self._muted)
            new_accent  = self.palette.get("accent",   self._accent)

            self._card_bg = new_card_bg
            self._text    = new_text
            self._muted   = new_muted
            self._accent  = new_accent

            try:
                self.toggle_frame.configure(bg=new_card_bg)
            except (tk.TclError, AttributeError):
                pass
            try:
                self.toggle_btn.configure(bg=new_card_bg, fg=new_accent)
            except (tk.TclError, AttributeError):
                pass
            try:
                self.content.configure(bg=new_card_bg)
            except (tk.TclError, AttributeError):
                pass
        except (tk.TclError, AttributeError):
            pass

    def get_content(self):
        return self.content


class HelpResourceCard:
    """
    Card for help resources, tutorials, and guides.
    Includes icon, title, description, and action button.
    """
    
    def __init__(self, parent, icon, title, description, action_text, action_command,
                 palette=None):
        """
        Create a help resource card.
        
        Args:
            parent: Parent widget
            icon: Icon character or emoji
            title: Card title
            description: Card description
            action_text: Button text
            action_command: Button command
            palette: Color palette dict
        """
        self.parent = parent
        self.palette = palette or {}
        self._bg = self.palette.get("bg", "#111827")
        self._card_bg = self.palette.get("card_bg", "#1f2937")
        self._text = self.palette.get("text", "#e5e7eb")
        self._muted = self.palette.get("muted", "#9ca3af")
        self._accent = self.palette.get("accent", "#8b5cf6")
        self._border = self.palette.get("border_color", "#374151")
        
        # Card frame
        self.card = tk.Frame(
            parent,
            bg=self._card_bg,
            padx=16,
            pady=12,
            highlightthickness=1,
            highlightbackground=self._border
        )
        self.card.pack(fill="x", pady=8)
        self.card.columnconfigure(1, weight=1)
        # Tag this widget so the settings popup's recursive theme
        # walker can discover this HelpResourceCard instance and
        # call ``update_theme`` on it when the user switches themes.
        self.card._fp_component = self
        
        # Icon
        self.icon_label = tk.Label(
            self.card,
            text=icon,
            font=("Segoe UI", 16),
            fg=self._accent,
            bg=self._card_bg
        )
        self.icon_label.grid(row=0, column=0, rowspan=2, sticky="nw", padx=12)
        
        # Title
        self.title_label = tk.Label(
            self.card,
            text=title,
            font=("Segoe UI", 10, "bold"),
            fg=self._text,
            bg=self._card_bg,
            anchor="w"
        )
        self.title_label.grid(row=0, column=1, sticky="w", padx=8)
        
        # Action button
        self.action_btn = ttk.Button(
            self.card,
            text=action_text,
            command=action_command,
            width=12
        )
        self.action_btn.grid(row=0, column=2, sticky="e")
        
        # Description
        self.desc_label = tk.Label(
            self.card,
            text=description,
            font=("Segoe UI", 9),
            fg=self._muted,
            bg=self._card_bg,
            wraplength=500,
            justify="left",
            anchor="w"
        )
        self.desc_label.grid(row=1, column=1, columnspan=2, sticky="w", pady=4)
        
        # Hover effects on the whole card
        self._default_border = self._border
        self._hover_border = SettingCard._lighten(self._border, 20) if hasattr(SettingCard, '_lighten') else self._border
        for w in [self.card, self.icon_label, self.title_label, self.desc_label]:
            w.bind("<Enter>", self._on_hover_enter)
            w.bind("<Leave>", self._on_hover_leave)
    
    def _on_hover_enter(self, event=None):
        """Subtle border brighten on hover."""
        try:
            self.card.config(highlightbackground=self._hover_border)
            self.title_label.config(fg="#ffffff")
        except tk.TclError:
            pass
    
    def _on_hover_leave(self, event=None):
        """Restore original border on leave."""
        try:
            self.card.config(highlightbackground=self._default_border)
            self.title_label.config(fg=self._text)
        except tk.TclError:
            pass

    def update_theme(self, palette):
        """Re-paint this help resource card's tk widgets to match a new theme.

        Called by ``SettingsTab._retheme_settings_popup`` so cards created
        in a previous theme do not stay frozen on the old colours when
        the user switches themes while the settings popup is open.
        """
        try:
            self.palette = palette or {}
            new_bg       = self.palette.get("bg",          self._bg)
            new_card_bg  = self.palette.get("card_bg",     self._card_bg)
            new_text     = self.palette.get("text",        self._text)
            new_muted    = self.palette.get("muted",       self._muted)
            new_accent   = self.palette.get("accent",      self._accent)
            new_border   = self.palette.get("border_color", self._border)

            self._bg           = new_bg
            self._card_bg       = new_card_bg
            self._text          = new_text
            self._muted         = new_muted
            self._accent        = new_accent
            self._border        = new_border
            self._default_border = new_border
            self._hover_border  = SettingCard._lighten(new_border, 20) if hasattr(SettingCard, '_lighten') else new_border

            try:
                self.card.configure(
                    bg=new_card_bg,
                    highlightbackground=new_border,
                )
            except (tk.TclError, AttributeError):
                pass
            try:
                self.icon_label.configure(bg=new_card_bg, fg=new_accent)
            except (tk.TclError, AttributeError):
                pass
            try:
                self.title_label.configure(bg=new_card_bg, fg=new_text)
            except (tk.TclError, AttributeError):
                pass
            try:
                self.desc_label.configure(bg=new_card_bg, fg=new_muted)
            except (tk.TclError, AttributeError):
                pass
        except (tk.TclError, AttributeError):
            pass


class SidebarNav:
    """
    Left sidebar navigation for settings categories.
    Provides clear navigation with active state highlighting.
    """
    
    def __init__(self, parent, categories, on_select, palette=None, width=220):
        """
        Create sidebar navigation.
        
        Args:
            parent: Parent widget
            categories: List of (id, label, icon) tuples
            on_select: Callback when category selected
            palette: Color palette dict
            width: Sidebar width in pixels
        """
        self.parent = parent
        self.categories = categories
        self.on_select = on_select
        self.palette = palette or {}
        self._bg = self.palette.get("bg", "#111827")
        self._sidebar_bg = self.palette.get("sidebar_bg", "#0f131a")
        self._text = self.palette.get("text", "#e5e7eb")
        self._muted = self.palette.get("muted", "#9ca3af")
        self._accent = self.palette.get("accent", "#8b5cf6")
        self._border = self.palette.get("border_color", "#374151")
        
        self._selected_category = None
        self._buttons = {}
        
        # Sidebar frame
        self.sidebar = tk.Frame(parent, bg=self._sidebar_bg, width=width)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        
        # Header
        header_frame = tk.Frame(self.sidebar, bg=self._sidebar_bg)
        header_frame.pack(fill="x", pady=20)
        header = tk.Label(
            header_frame,
            text="Settings",
            font=("Segoe UI", 12, "bold"),
            fg=self._text,
            bg=self._sidebar_bg,
            anchor="w",
            padx=16
        )
        header.pack(fill="x")
        
        # Navigation buttons
        nav_frame = tk.Frame(self.sidebar, bg=self._sidebar_bg)
        nav_frame.pack(fill="x", padx=8)
        
        for cat_id, label, icon in categories:
            btn = self._create_nav_button(nav_frame, cat_id, label, icon)
            btn.pack(fill="x", pady=4)
            self._buttons[cat_id] = btn
        
        # Select first category by default
        if categories:
            self.select_category(categories[0][0])
    
    def _create_nav_button(self, parent, cat_id, label, icon):
        """Create a navigation button."""
        btn_frame = tk.Frame(parent, bg=self._sidebar_bg, cursor="hand2")
        
        # Active indicator (hidden / same as bg by default)
        indicator = tk.Frame(btn_frame, bg=self._sidebar_bg, width=3)
        indicator.pack(side="left", fill="y")
        
        # Button content
        content = tk.Frame(btn_frame, bg=self._sidebar_bg, cursor="hand2")
        content.pack(side="left", fill="x", expand=True, padx=12, pady=10)
        
        icon_label = tk.Label(
            content,
            text=icon,
            font=("Segoe UI", 11),
            fg=self._muted,
            bg=self._sidebar_bg,
            cursor="hand2"
        )
        icon_label.pack(side="left", padx=10)
        
        label_widget = tk.Label(
            content,
            text=label,
            font=("Segoe UI", 10),
            fg=self._text,
            bg=self._sidebar_bg,
            anchor="w",
            cursor="hand2"
        )
        label_widget.pack(side="left")
        
        # Store references
        btn_frame.indicator = indicator
        btn_frame.icon_label = icon_label
        btn_frame.label_widget = label_widget
        btn_frame.content = content
        btn_frame.cat_id = cat_id
        
        # Click handler
        def on_click(event=None):
            self.select_category(cat_id)
        
        # Hover effects
        def on_enter(event=None):
            if btn_frame.cat_id != self._selected_category:
                hover_bg = self._lighten(self._sidebar_bg, 6)
                try:
                    label_widget.config(fg=self._accent, bg=hover_bg)
                    icon_label.config(fg=self._accent, bg=hover_bg)
                    content.config(bg=hover_bg)
                except tk.TclError:
                    pass
        
        def on_leave(event=None):
            if btn_frame.cat_id != self._selected_category:
                try:
                    label_widget.config(fg=self._text, bg=self._sidebar_bg)
                    icon_label.config(fg=self._muted, bg=self._sidebar_bg)
                    content.config(bg=self._sidebar_bg)
                except tk.TclError:
                    pass
        
        for w in [btn_frame, content, icon_label, label_widget]:
            w.bind("<Button-1>", on_click)
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)
        
        return btn_frame
    
    def select_category(self, cat_id):
        """Select a category and update UI with smooth state transition."""
        # Reset previous selection
        if self._selected_category and self._selected_category in self._buttons:
            prev_btn = self._buttons[self._selected_category]
            try:
                prev_btn.indicator.config(bg=self._sidebar_bg)
                prev_btn.label_widget.config(fg=self._text, bg=self._sidebar_bg)
                prev_btn.icon_label.config(fg=self._muted, bg=self._sidebar_bg)
                prev_btn.content.config(bg=self._sidebar_bg)
                prev_btn.config(bg=self._sidebar_bg)
            except (tk.TclError, AttributeError):
                pass
        
        # Set new selection
        self._selected_category = cat_id
        if cat_id in self._buttons:
            new_btn = self._buttons[cat_id]
            active_bg = self._lighten(self._sidebar_bg, 8)
            try:
                new_btn.indicator.config(bg=self._accent)
                new_btn.label_widget.config(fg=self._accent, bg=active_bg)
                new_btn.icon_label.config(fg=self._accent, bg=active_bg)
                new_btn.content.config(bg=active_bg)
                new_btn.config(bg=self._sidebar_bg)
            except (tk.TclError, AttributeError):
                pass
        
        # Trigger callback
        if self.on_select:
            self.on_select(cat_id)
    
    @staticmethod
    def _lighten(hex_color, amount):
        """Lighten a hex color by a given amount (0-255)."""
        try:
            hex_color = hex_color.lstrip("#")
            r = min(255, max(0, int(hex_color[0:2], 16) + amount))
            g = min(255, max(0, int(hex_color[2:4], 16) + amount))
            b = min(255, max(0, int(hex_color[4:6], 16) + amount))
            return f"#{r:02x}{g:02x}{b:02x}"
        except (ValueError, IndexError):
            return hex_color
    
    def get_sidebar(self):
        return self.sidebar

    def update_theme(self, palette):
        """Update all sidebar colours to match a new theme palette.

        Called when the user changes the app theme while the settings popup
        is already open, so the sidebar does not stay frozen on the old
        theme's colours.
        """
        self.palette = palette or {}
        new_bg   = self.palette.get("sidebar_bg", "#0f131a")
        new_text = self.palette.get("text", "#e5e7eb")
        new_muted = self.palette.get("muted", "#9ca3af")
        new_accent = self.palette.get("accent", "#8b5cf6")
        new_border = self.palette.get("border_color", "#374151")

        self._sidebar_bg = new_bg
        self._text = new_text
        self._muted = new_muted
        self._accent = new_accent
        self._border = new_border

        # Update the main sidebar frame
        try:
            self.sidebar.configure(bg=new_bg)
        except (tk.TclError, AttributeError):
            return

        # Update header label
        for w in self.sidebar.winfo_children():
            try:
                w.configure(bg=new_bg)
                for child in w.winfo_children():
                    if isinstance(child, tk.Label):
                        child.configure(bg=new_bg, fg=new_text)
            except (tk.TclError, AttributeError):
                pass

        # Update all nav buttons
        for cat_id, btn_frame in self._buttons.items():
            try:
                btn_frame.configure(bg=new_bg)
                if hasattr(btn_frame, 'indicator'):
                    is_selected = (cat_id == self._selected_category)
                    ind_bg = new_accent if is_selected else new_bg
                    btn_frame.indicator.configure(bg=ind_bg)
                if hasattr(btn_frame, 'content'):
                    cont_bg = new_bg
                    if is_selected:
                        cont_bg = self._lighten(new_bg, 8)
                    btn_frame.content.configure(bg=cont_bg)
                if hasattr(btn_frame, 'icon_label'):
                    icon_fg = new_accent if is_selected else new_muted
                    icon_bg = self._lighten(new_bg, 8) if is_selected else new_bg
                    btn_frame.icon_label.configure(fg=icon_fg, bg=icon_bg)
                if hasattr(btn_frame, 'label_widget'):
                    lbl_fg = new_accent if is_selected else new_text
                    lbl_bg = self._lighten(new_bg, 8) if is_selected else new_bg
                    btn_frame.label_widget.configure(fg=lbl_fg, bg=lbl_bg)
            except (tk.TclError, AttributeError):
                pass


class CloudProviderCard:
    """
    Enhanced cloud provider card with progressive disclosure.
    Shows summary by default, expands for management.
    """
    
    STATUS_COLORS = {
        "connected": "#22c55e",
        "not_connected": "#6b7280",
        "error": "#ef4444"
    }
    
    def __init__(self, parent, provider_key, ux_info, palette, app):
        """
        Create a cloud provider card.
        
        Args:
            parent: Parent widget
            provider_key: Provider identifier (google_drive, onedrive, dropbox, etc.)
            ux_info: UX configuration dict
            palette: Color palette dict
            app: App instance for callbacks
        """
        self.parent = parent
        self.provider_key = provider_key
        self.ux_info = ux_info
        self.palette = palette
        self.app = app
        
        self._bg = palette.get("bg", "#111827")
        self._card_bg = palette.get("card_bg", "#1f2937")
        self._text = palette.get("text", "#e5e7eb")
        self._muted = palette.get("muted", "#9ca3af")
        self._accent = palette.get("accent", "#8b5cf6")
        self._border = palette.get("border_color", "#374151")
        
        self._expanded = False
        self._status = "not_connected"
        
        self._build_card()
    
    def _build_card(self):
        """Build the card UI."""
        # Outer frame
        self.outer = tk.Frame(self.parent, bg=self._bg)
        self.outer.pack(fill="x", pady=12)
        # Tag this widget so the settings popup's recursive theme
        # walker can discover this CloudProviderCard instance and
        # call ``update_theme`` on it when the user switches themes.
        self.outer._fp_component = self
        
        # Accent bar
        self.accent_bar = tk.Frame(self.outer, bg=self.STATUS_COLORS["not_connected"], width=3)
        self.accent_bar.pack(side="left", fill="y")
        
        # Card body
        self.card = tk.Frame(
            self.outer,
            bg=self._card_bg,
            padx=16,
            pady=12,
            highlightthickness=1,
            highlightbackground=self._border
        )
        self.card.pack(side="left", fill="both", expand=True)
        self.card.columnconfigure(1, weight=1)
        
        # Summary row (always visible)
        self._build_summary_row()
        
        # Expandable content (credentials, actions)
        self._build_expandable_content()
    
    def _build_summary_row(self):
        """Build the always-visible summary row."""
        # Icon
        icon = tk.Label(
            self.card,
            text=self.ux_info["icon_char"],
            font=("Segoe UI", 14, "bold"),
            fg=self._accent,
            bg=self._card_bg
        )
        icon.grid(row=0, column=0, sticky="w", padx=12)
        
        # Name
        name = tk.Label(
            self.card,
            text=self.ux_info["display_name"],
            font=("Segoe UI", 11, "bold"),
            fg=self._text,
            bg=self._card_bg,
            anchor="w"
        )
        name.grid(row=0, column=1, sticky="w")
        
        # Status badge
        self.status_badge = StatusBadge.create(
            self.card,
            "Not connected",
            "not_connected",
            "small"
        )
        self.status_badge.grid(row=0, column=2, sticky="e", padx=8)
        
        # Expand toggle
        self.toggle_label = tk.Label(
            self.card,
            text="▶",
            font=("Segoe UI", 10),
            fg=self._muted,
            bg=self._card_bg,
            cursor="hand2"
        )
        self.toggle_label.grid(row=0, column=3, sticky="e", padx=8)
        self.toggle_label.bind("<Button-1>", self._on_toggle)
        self.toggle_label.bind("<Enter>", lambda e: self.toggle_label.config(fg=self._accent))
        self.toggle_label.bind("<Leave>", lambda e: self.toggle_label.config(fg=self._muted))
    
    def _build_expandable_content(self):
        """Build the expandable content area."""
        self.content = tk.Frame(self.card, bg=self._card_bg)
        self.content.grid(row=1, column=0, columnspan=4, sticky="ew", pady=12)
        self.content.grid_remove()
        
        # Credential fields
        self.cred_frame = tk.Frame(self.content, bg=self._card_bg)
        self.cred_frame.pack(fill="x", pady=8)
        self.cred_frame.columnconfigure(1, weight=1)
        
        from utils import load_config
        cfg = load_config()
        
        # ID Variable & Entry
        id_attr = self.ux_info.get("id_var_attr", f"{self.provider_key}_id_var")
        id_val = cfg.get(f"{self.provider_key}_client_id", cfg.get(f"{self.provider_key}_app_key", cfg.get("google_client_id" if "google" in self.provider_key else "", "")))
        if not hasattr(self.app, id_attr):
            setattr(self.app, id_attr, tk.StringVar(value=id_val))
        id_var = getattr(self.app, id_attr)
        setattr(self.app, f"{self.provider_key}_id_var", id_var)
        
        tk.Label(self.cred_frame, text=f"{self.ux_info.get('id_label', 'Client ID')}:",
                 font=("Segoe UI", 10), fg=self._text, bg=self._card_bg).grid(row=0, column=0, sticky="w", padx=8, pady=4)
        id_entry = ttk.Entry(self.cred_frame, textvariable=id_var, width=35)
        id_entry.grid(row=0, column=1, sticky="ew", padx=8, pady=4)
        self.app.configure_entry_cursor(id_entry)
        
        # Secret Variable & Entry
        secret_attr = self.ux_info.get("secret_var_attr", f"{self.provider_key}_secret_var")
        secret_val = cfg.get(f"{self.provider_key}_client_secret", cfg.get(f"{self.provider_key}_app_secret", cfg.get("google_client_secret" if "google" in self.provider_key else "", "")))
        if not hasattr(self.app, secret_attr):
            setattr(self.app, secret_attr, tk.StringVar(value=secret_val))
        secret_var = getattr(self.app, secret_attr)
        setattr(self.app, f"{self.provider_key}_secret_var", secret_var)
        
        tk.Label(self.cred_frame, text=f"{self.ux_info.get('secret_label', 'Client Secret')}:",
                 font=("Segoe UI", 10), fg=self._text, bg=self._card_bg).grid(row=1, column=0, sticky="w", padx=8, pady=4)
        secret_entry = ttk.Entry(self.cred_frame, textvariable=secret_var, width=35, show="*")
        secret_entry.grid(row=1, column=1, sticky="ew", padx=8, pady=4)
        self.app.configure_entry_cursor(secret_entry)
        
        # Connected state frame
        self.connected_frame = tk.Frame(self.content, bg=self._card_bg)
        self.connected_lbl = tk.Label(
            self.connected_frame,
            text=f"✓ Connected to {self.ux_info['display_name']}",
            font=("Segoe UI", 10),
            fg="#22c55e",
            bg=self._card_bg
        )
        self.connected_lbl.pack(side="left", padx=8)
        self.disconnect_btn = ttk.Button(
            self.connected_frame,
            text="Disconnect",
            command=lambda: self.app._cloud_connect(self.provider_key)
        )
        self.disconnect_btn.pack(side="right", padx=8)
        
        # Error frame
        self.error_frame = tk.Frame(self.content, bg=self._card_bg)
        self.error_lbl = tk.Label(
            self.error_frame,
            text="",
            font=("Segoe UI", 9),
            fg="#ef4444",
            bg=self._card_bg,
            wraplength=550
        )
        self.error_lbl.pack(fill="x", padx=8, pady=4)
        
        # Action buttons frame
        self.action_frame = tk.Frame(self.content, bg=self._card_bg)
        self.action_frame.pack(fill="x", pady=8)
        
        self.connect_btn = ttk.Button(
            self.action_frame,
            text="Connect",
            command=lambda: self.app._cloud_connect(self.provider_key)
        )
        self.connect_btn.pack(side="left", padx=8)
        
        # Setup guide (collapsible, starts expanded so instructions are
        # immediately visible without an extra click)
        self.guide_section = ExpandableSection(
            self.content,
            "How to get your credentials",
            expanded=True,
            palette=self.palette,
            accent_color=self._accent
        )
        
        # Add setup steps (auto-wrapping, clickable links, auto-height)
        guide_content = self.guide_section.get_content()
        self.guide_text = SetupGuideText(
            guide_content,
            self.ux_info["setup_steps"],
            bg=self._card_bg,
            fg=self._muted,
            link=self._accent,
            font=("Segoe UI", 9),
        )
        # Tag so theme walkers can discover and re-paint this component.
        self.guide_text._fp_component = self.guide_text
        self.guide_text.pack(fill="x", pady=4)
        
        # Register in _cloud_card_refs for backward-compat
        if not hasattr(self.app, "_cloud_card_refs"):
            self.app._cloud_card_refs = {}
            
        dot_canvas = tk.Canvas(self.card, width=1, height=1, bg=self._card_bg, highlightthickness=0)
        dot_id = dot_canvas.create_oval(0, 0, 1, 1, fill=self.STATUS_COLORS["not_connected"])
        
        self.app._cloud_card_refs[self.provider_key] = {
            'accent_bar': self.accent_bar,
            'dot_canvas': dot_canvas,
            'dot_id': dot_id,
            'status_lbl': self.status_badge.winfo_children()[0] if self.status_badge.winfo_children() else self.status_badge,
            'cred_frame': self.cred_frame,
            'connected_frame': self.connected_frame,
            'error_frame': self.error_frame,
            'error_lbl': self.error_lbl,
            'setup_guide_toggle': self.guide_section.toggle_btn,
            'guide_frame': self.guide_section.get_content(),
        }
        
        # Sync initial status
        from utils import has_oauth_token
        is_conn = has_oauth_token(self.provider_key)
        self.update_status("connected" if is_conn else "not_connected")
        if is_conn:
            self.cred_frame.pack_forget()
            self.action_frame.pack_forget()
            self.connected_frame.pack(fill="x", pady=8)
            self.guide_section.toggle_frame.pack_forget()
            self.guide_section.get_content().pack_forget()
        else:
            self.connected_frame.pack_forget()
    
    def _on_toggle(self, event=None):
        """Toggle expand/collapse."""
        self._expanded = not self._expanded
        self.toggle_label.config(text="▼" if self._expanded else "▶")
        
        if self._expanded:
            self.content.grid()
        else:
            self.content.grid_remove()
    
    def update_status(self, status):
        """Update the connection status."""
        self._status = status
        try:
            self.accent_bar.config(bg=self.STATUS_COLORS.get(status, "#6b7280"))
        except tk.TclError:
            pass
        
        # Update status badge
        status_text = {
            "connected": "Connected",
            "not_connected": "Not connected",
            "error": "Error"
        }.get(status, "Unknown")
        
        try:
            self.status_badge.destroy()
            self.status_badge = StatusBadge.create(
                self.card,
                status_text,
                status,
                "small"
            )
            self.status_badge.grid(row=0, column=2, sticky="e", padx=8)
            if hasattr(self.app, '_cloud_card_refs') and self.provider_key in self.app._cloud_card_refs:
                self.app._cloud_card_refs[self.provider_key]['status_lbl'] = (
                    self.status_badge.winfo_children()[0] if self.status_badge.winfo_children() else self.status_badge
                )
        except (tk.TclError, AttributeError):
            pass

    def update_theme(self, palette):
        """Re-paint this cloud provider card's tk widgets to match a new theme.

        Called by ``SettingsTab._retheme_settings_popup`` so cards created
        in a previous theme do not stay frozen on the old colours when
        the user switches themes while the settings popup is open.
        """
        try:
            self.palette = palette or {}
            new_bg       = self.palette.get("bg",          self._bg)
            new_card_bg  = self.palette.get("card_bg",     self._card_bg)
            new_text     = self.palette.get("text",        self._text)
            new_muted    = self.palette.get("muted",       self._muted)
            new_accent   = self.palette.get("accent",      self._accent)
            new_border   = self.palette.get("border_color", self._border)

            self._bg       = new_bg
            self._card_bg  = new_card_bg
            self._text     = new_text
            self._muted    = new_muted
            self._accent   = new_accent
            self._border   = new_border

            try:
                self.outer.configure(bg=new_bg)
            except (tk.TclError, AttributeError):
                pass
            try:
                self.card.configure(
                    bg=new_card_bg,
                    highlightbackground=new_border,
                )
            except (tk.TclError, AttributeError):
                pass
            try:
                self.content.configure(bg=new_card_bg)
            except (tk.TclError, AttributeError):
                pass
            try:
                self.cred_frame.configure(bg=new_card_bg)
            except (tk.TclError, AttributeError):
                pass
            try:
                self.connected_frame.configure(bg=new_card_bg)
                self.connected_lbl.configure(bg=new_card_bg)
            except (tk.TclError, AttributeError):
                pass
            try:
                self.error_frame.configure(bg=new_card_bg)
                self.error_lbl.configure(bg=new_card_bg)
            except (tk.TclError, AttributeError):
                pass
            try:
                self.action_frame.configure(bg=new_card_bg)
            except (tk.TclError, AttributeError):
                pass
            try:
                self.toggle_label.configure(bg=new_card_bg, fg=new_muted)
            except (tk.TclError, AttributeError):
                pass
            try:
                # Recursively re-theme the Setup-guide section's toggle/content
                self.guide_section.update_theme(palette)
            except (tk.TclError, AttributeError):
                pass
            try:
                # Re-theme the guide step labels inside the setup guide content
                guide_content = self.guide_section.get_content()
                for child in guide_content.winfo_children():
                    if isinstance(child, tk.Label):
                        child.configure(bg=new_card_bg, fg=new_muted)
                    elif isinstance(child, SetupGuideText):
                        child.apply_colors(bg=new_card_bg, fg=new_muted,
                                           link=new_accent)
            except (tk.TclError, AttributeError):
                pass
            try:
                # Update dot canvas background (kept at card_bg by convention)
                refs = getattr(self.app, "_cloud_card_refs", {}).get(self.provider_key, {})
                dot_canvas = refs.get("dot_canvas")
                if dot_canvas is not None:
                    dot_canvas.configure(bg=new_card_bg)
            except (tk.TclError, AttributeError):
                pass
            try:
                # Re-walk the credential frame for inline tk.Label children
                for child in self.cred_frame.winfo_children():
                    if isinstance(child, tk.Label):
                        child.configure(bg=new_card_bg, fg=new_text)
            except (tk.TclError, AttributeError):
                pass
        except (tk.TclError, AttributeError):
            pass
