"""
theme.py — Single source of truth for FrogPaper's shared visual constants.
===========================================================================

Colors, fonts, and color-math helpers that are used across multiple modules
live here, so they can never drift apart between files.

Previously duplicated, now consolidated (improvement report §2):
  - STATUS_COLORS        (was defined in settings_tab.py AND
                          settings_components.py)
  - popup fallback palette (was inline in pinned_dropdowns.py)
  - color lighten/darken math (was in pinned_dropdowns.py AND
                          rounded_widgets.py)

This module must stay dependency-light: it imports tkinter lazily and
tolerates its absence, so headless tooling and tests can import the
constants without a display.
"""

import logging

logger = logging.getLogger(__name__)

# ── Status colors ────────────────────────────────────────────────────────
# One definition. settings_tab.py re-exports this for app.py; the cloud
# provider cards read it via the class attribute.
STATUS_COLORS = {
    "connected": "#22c55e",
    "not_connected": "#6b7280",
    "error": "#ef4444",
    "success": "#22c55e",
    "warning": "#f59e0b",
    "info": "#3b82f6",
}

# ── Shared semantic palette ──────────────────────────────────────────────
COLOR_SUCCESS = "#22c55e"
COLOR_WARNING = "#f59e0b"
COLOR_ERROR = "#ef4444"
COLOR_INFO = "#3b82f6"
COLOR_MUTED = "#6b7280"

# ── Shared inline-color constants (Phase C hotspot migration) ────────────
# The hex values below used to be hardcoded as string literals across the
# UI modules (settings cards, gallery, tray, effects).  They now live here
# so a palette tweak is a one-line change.  Values are byte-identical to
# the literals they replaced - pure refactor, no visual change.
COLOR_ACCENT = "#8b5cf6"        # violet — default card accent (Tailwind violet-500)
COLOR_WHITE = "#ffffff"
COLOR_BLACK = "#000000"
COLOR_NEAR_BLACK = "#111111"
COLOR_MID_GRAY = "#888888"
COLOR_DIM_GRAY = "#666666"
COLOR_GRAY_200 = "#e5e7eb"      # Tailwind gray-200
COLOR_GRAY_400 = "#9ca3af"      # Tailwind gray-400
COLOR_GRAY_700 = "#374151"      # Tailwind gray-700
COLOR_GRAY_800 = "#1f2937"      # Tailwind gray-800
COLOR_GRAY_900 = "#111827"      # Tailwind gray-900
COLOR_GREEN_BRIGHT = "#4ade80"  # icon/status green (lighter than COLOR_SUCCESS)

# Favorites / pinning
COLOR_STAR_ON = "#FFD700"      # gold — pinned stars
PIN_MARKER_ON = "★"             # the ONE standard favorite marker
PIN_MARKER_OFF = "☆"            # unpinned / "click to add" hint

# ── Typography ───────────────────────────────────────────────────────────
FONT_FAMILY = "Segoe UI"


def font(size: int, style: str = "") -> tuple:
    """Build a Tkinter font tuple in the app-wide font family."""
    return (FONT_FAMILY, size) + ((style,) if style else ())


# ── Fallback dark palette ────────────────────────────────────────────────
# Used when live ttk theme colors cannot be detected (e.g. before the
# theme is fully applied). Previously inlined in pinned_dropdowns.py.
FALLBACK_POPUP_COLORS = {
    "bg": "#1e1e1e",
    "fg": "#ffffff",
    "hover": "#2d2d2d",
    "selected_bg": "#3a3a5c",
    "selected_fg": "#ffffff",
    "header_fg": "#888888",
    "separator": "#333333",
    "star_off": "#666666",
    "star_on": "#FFD700",
}

# Small floating tooltips
TOOLTIP_BG = "#252525"
TOOLTIP_FG = "#f5f5f5"
TOOLTIP_BORDER = "#4a4a5a"


# ── Color math ───────────────────────────────────────────────────────────
# One implementation of lighten/darken. Positive amounts lighten, negative
# amounts darken. Invalid input returns the original string unchanged.

def adjust_color(hex_color: str, amount: int) -> str:
    """Lighten (amount > 0) or darken (amount < 0) a '#rrggbb' color.

    Each channel is clamped to 0-255. Returns the input unchanged if it
    cannot be parsed, so callers never crash on odd color strings.
    """
    try:
        h = hex_color.lstrip("#")
        if len(h) != 6:
            return hex_color
        r = max(0, min(255, int(h[0:2], 16) + amount))
        g = max(0, min(255, int(h[2:4], 16) + amount))
        b = max(0, min(255, int(h[4:6], 16) + amount))
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return hex_color


def lighten(hex_color: str, amount: int = 30) -> str:
    """Lighten a color by `amount` (0-255 per channel)."""
    return adjust_color(hex_color, abs(amount))


def darken(hex_color: str, amount: int = 30) -> str:
    """Darken a color by `amount` (0-255 per channel)."""
    return adjust_color(hex_color, -abs(amount))


def ensure_contrast(bg_hex: str, fg_hex: str, fallback_fg: str) -> str:
    """Ensure `fg_hex` has at least a 3:1 WCAG contrast ratio on `bg_hex`.

    If the ratio is too low, tries `fallback_fg`; if that is also too low,
    forces white or black based on background luminance. The returned hex
    is always '#'-prefixed so Tk never sees a bare color name.

    NOTE: callers may pass fg/fallback WITHOUT the leading '#' — the
    return value is always re-prefixed, which fixes the historical
    "unknown color name" crash when popup colors lost their '#'.
    """
    try:
        bg_hex = bg_hex.lstrip("#")
        fg_hex = fg_hex.lstrip("#")

        def relative_luminance(hex_str):
            r, g, b = int(hex_str[0:2], 16) / 255, int(hex_str[2:4], 16) / 255, int(hex_str[4:6], 16) / 255
            r = r / 12.92 if r <= 0.04045 else ((r + 0.055) / 1.055) ** 2.4
            g = g / 12.92 if g <= 0.04045 else ((g + 0.055) / 1.055) ** 2.4
            b = b / 12.92 if b <= 0.04045 else ((b + 0.055) / 1.055) ** 2.4
            return 0.2126 * r + 0.7152 * g + 0.0722 * b

        l_bg = relative_luminance(bg_hex)
        l_fg = relative_luminance(fg_hex)

        lighter = max(l_bg, l_fg)
        darker = min(l_bg, l_fg)
        ratio = (lighter + 0.05) / (darker + 0.05)

        if ratio >= 3.0:
            # Re-prefix the '#' — luminance math stripped it above.
            return f"#{fg_hex}"

        # Use fallback if it has better contrast
        if fallback_fg and fallback_fg != fg_hex:
            l_fb = relative_luminance(fallback_fg.lstrip("#"))
            fb_lighter = max(l_bg, l_fb)
            fb_darker = min(l_bg, l_fb)
            fb_ratio = (fb_lighter + 0.05) / (fb_darker + 0.05)
            if fb_ratio >= 3.0:
                return fallback_fg if fallback_fg.startswith("#") \
                    else f"#{fallback_fg}"

        # Force white or black based on background luminance
        return "#ffffff" if l_bg < 0.4 else "#1a1a1a"
    except Exception:
        return fallback_fg or "#ffffff"


# ── Tooltips ─────────────────────────────────────────────────────────────
# tkinter is optional so headless tooling can still import the constants.

try:
    import tkinter as tk
    _TK_AVAILABLE = True
except ImportError:  # pragma: no cover - headless environments
    _TK_AVAILABLE = False


if _TK_AVAILABLE:

    class Tooltip:
        """Small hover tooltip for any widget.

        Usage:
            Tooltip(star_button, "Add to favorites")

        Safe to attach to widgets that already have <Enter>/<Leave>
        bindings (it adds its bindings with add="+"). The tooltip hides
        on mouse leave, on click, and when the widget is destroyed.
        """

        def __init__(self, widget, text: str, delay_ms: int = 500):
            self.widget = widget
            self.text = text
            self.delay_ms = delay_ms
            self._tip = None
            self._job = None
            widget.bind("<Enter>", self._schedule, add="+")
            widget.bind("<Leave>", self._hide, add="+")
            widget.bind("<ButtonPress>", self._hide, add="+")
            widget.bind("<Destroy>", self._on_destroy, add="+")

        def _schedule(self, event=None):
            self._cancel_job()
            try:
                self._job = self.widget.after(self.delay_ms, self._show)
            except Exception:
                self._job = None

        def _cancel_job(self):
            if self._job is not None:
                try:
                    self.widget.after_cancel(self._job)
                except Exception:
                    pass
                self._job = None

        def _show(self):
            self._job = None
            if self._tip is not None:
                return
            try:
                if not self.widget.winfo_exists():
                    return
                x = self.widget.winfo_rootx()
                y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
                self._tip = tk.Toplevel(self.widget)
                self._tip.wm_overrideredirect(True)
                self._tip.wm_attributes("-topmost", True)
                self._tip.wm_geometry(f"+{x}+{y}")
                label = tk.Label(
                    self._tip,
                    text=self.text,
                    justify="left",
                    background=TOOLTIP_BG,
                    foreground=TOOLTIP_FG,
                    font=(FONT_FAMILY, 9),
                    padx=8,
                    pady=4,
                    highlightthickness=1,
                    highlightbackground=TOOLTIP_BORDER,
                )
                label.pack()
            except Exception as e:
                logger.debug(f"Tooltip show failed: {e}")
                self._hide()

        def _hide(self, event=None):
            self._cancel_job()
            if self._tip is not None:
                try:
                    self._tip.destroy()
                except Exception:
                    pass
                self._tip = None

        def _on_destroy(self, event=None):
            # <Destroy> also fires for child widgets; only react to our own.
            try:
                if event is not None and event.widget is not self.widget:
                    return
            except Exception:
                pass
            self._hide()

else:  # pragma: no cover - headless environments

    class Tooltip:  # type: ignore[no-redef]
        """No-op placeholder when tkinter is unavailable."""

        def __init__(self, widget, text: str, delay_ms: int = 500):
            self.widget = widget
            self.text = text
