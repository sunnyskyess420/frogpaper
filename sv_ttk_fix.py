"""
sv_ttk_fix.py — Replace sv_ttk's grey sprite images with themed versions.

sv_ttk creates PNG sprite images for widget backgrounds (buttons, entries,
cards, etc.) from a single spritesheet.  The sprites are baked with fixed
grey colours that cannot be overridden via style.configure().

This module discovers sv_ttk's images after it loads and overwrites each
sprite's pixel data with theme-appropriate colours while preserving the
original dimensions and transparency.

Usage (called from app.py after sv_ttk.set_theme()):
    from sv_ttk_fix import fix_sv_ttk_sprites
    fix_sv_ttk_sprites(root, pal)
"""

from __future__ import annotations

import io
import logging
import tkinter as tk

logger = logging.getLogger(__name__)

# ── Sprite definitions (from sv_ttk theme/sprites_dark.tcl) ──────────────
# Format: sprite_name x y width height
SPRITE_DEFS = [
    ("card", 0, 0, 50, 50),
    ("notebook-border", 50, 0, 40, 40),
    ("switch-dis", 50, 40, 40, 20),
    ("switch-focus-hover", 0, 50, 40, 20),
    ("switch-focus", 0, 70, 40, 20),
    ("switch-hover", 40, 60, 40, 20),
    ("switch-off-dis", 90, 0, 40, 20),
    ("switch-off-focus-hover", 90, 20, 40, 20),
    ("switch-off-focus", 90, 40, 40, 20),
    ("switch-off-hover", 80, 60, 40, 20),
    ("switch-off-pressed", 0, 90, 40, 20),
    ("switch-off-rest", 40, 80, 40, 20),
    ("switch-pressed", 80, 80, 40, 20),
    ("switch-rest", 0, 110, 40, 20),
    ("tab-hover", 130, 0, 32, 32),
    ("tab-rest", 130, 32, 32, 32),
    ("tab-selected", 120, 64, 32, 32),
    ("heading-hover", 40, 100, 22, 22),
    ("heading-pressed", 62, 100, 22, 22),
    ("heading-rest", 84, 100, 22, 22),
    ("slider-thumb-dis", 106, 100, 22, 22),
    ("slider-thumb-focus-hover", 128, 96, 22, 22),
    ("slider-thumb-focus", 0, 130, 22, 22),
    ("slider-thumb-hover", 22, 130, 22, 22),
    ("slider-thumb-pressed", 44, 122, 22, 22),
    ("slider-thumb-rest", 66, 122, 22, 22),
    ("slider-trough-hor", 88, 122, 22, 22),
    ("slider-trough-vert", 110, 122, 22, 22),
    ("button-accent-dis", 132, 118, 20, 20),
    ("button-accent-focus-hover", 0, 152, 20, 20),
    ("button-accent-focus", 20, 152, 20, 20),
    ("button-accent-hover", 40, 152, 20, 20),
    ("button-accent-pressed", 60, 144, 20, 20),
    ("button-accent-rest", 80, 144, 20, 20),
    ("button-dis", 100, 144, 20, 20),
    ("button-focus-hover", 120, 144, 20, 20),
    ("button-focus", 140, 138, 20, 20),
    ("button-hover", 162, 0, 20, 20),
    ("button-pressed", 162, 20, 20, 20),
    ("button-rest", 162, 40, 20, 20),
    ("check-dis", 162, 60, 20, 20),
    ("check-focus-hover", 150, 96, 20, 20),
    ("check-focus", 152, 116, 20, 20),
    ("check-hover", 160, 136, 20, 20),
    ("check-pressed", 0, 172, 20, 20),
    ("check-rest", 20, 172, 20, 20),
    ("check-tri-dis", 40, 172, 20, 20),
    ("check-tri-focus-hover", 160, 156, 20, 20),
    ("check-tri-focus", 140, 158, 20, 20),
    ("check-tri-hover", 60, 164, 20, 20),
    ("check-tri-pressed", 80, 164, 20, 20),
    ("check-tri-rest", 100, 164, 20, 20),
    ("check-unsel-dis", 120, 164, 20, 20),
    ("check-unsel-focus-hover", 182, 0, 20, 20),
    ("check-unsel-focus", 182, 20, 20, 20),
    ("check-unsel-hover", 182, 40, 20, 20),
    ("check-unsel-pressed", 182, 60, 20, 20),
    ("check-unsel-rest", 180, 80, 20, 20),
    ("progressbar-bar-hor", 180, 100, 20, 5),
    ("progressbar-bar-vert", 172, 80, 5, 20),
    ("progressbar-trough-hor", 152, 80, 20, 5),
    ("progressbar-trough-vert", 172, 100, 5, 20),
    ("radio-dis", 180, 105, 20, 20),
    ("radio-focus-hover", 180, 125, 20, 20),
    ("radio-focus", 180, 145, 20, 20),
    ("radio-hover", 180, 165, 20, 20),
    ("radio-pressed", 160, 176, 20, 20),
    ("radio-rest", 140, 178, 20, 20),
    ("radio-unsel-dis", 0, 192, 20, 20),
    ("radio-unsel-focus-hover", 20, 192, 20, 20),
    ("radio-unsel-focus", 40, 192, 20, 20),
    ("radio-unsel-hover", 180, 185, 20, 20),
    ("radio-unsel-pressed", 60, 184, 20, 20),
    ("radio-unsel-rest", 80, 184, 20, 20),
    ("scrollbar-thumb-hor", 160, 196, 20, 12),
    ("scrollbar-thumb-vert", 100, 184, 12, 20),
    ("scrollbar-trough-hor", 112, 198, 20, 12),
    ("scrollbar-trough-vert", 202, 0, 12, 20),
    ("textbox-dis", 0, 212, 20, 20),
    ("textbox-error", 20, 212, 20, 20),
    ("textbox-focus", 40, 212, 20, 20),
    ("textbox-hover", 60, 210, 20, 20),
    ("textbox-rest", 80, 210, 20, 20),
    ("down", 40, 50, 10, 5),
    ("empty", 152, 64, 10, 10),
    ("grip", 152, 85, 10, 10),
    ("right", 162, 85, 5, 10),
    ("sep", 202, 20, 10, 10),
    ("up", 40, 55, 10, 5),
    ("scrollbar-down", 132, 138, 8, 6),
    ("scrollbar-left", 44, 144, 6, 8),
    ("scrollbar-right", 50, 144, 6, 8),
    ("scrollbar-up", 172, 120, 8, 6),
]

# ── Color helpers ────────────────────────────────────────────────────────

def _hex_rgb(h: str):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

def _rgb_hex(r, g, b):
    return f"#{max(0,min(255,r)):02x}{max(0,min(255,g)):02x}{max(0,min(255,b)):02x}"

def _lighten(c: str, amt: int = 25) -> str:
    r, g, b = _hex_rgb(c)
    return _rgb_hex(r + amt, g + amt, b + amt)

def _darken(c: str, amt: int = 25) -> str:
    r, g, b = _hex_rgb(c)
    return _rgb_hex(r - amt, g - amt, b - amt)

def _alpha(hex_color: str, a: int) -> tuple:
    r, g, b = _hex_rgb(hex_color)
    return (r, g, b, a)

def _draw_rounded_rect(draw, w, h, radius, fill, outline=None):
    """Draw a rounded rectangle compatible with all Pillow versions.

    Hardened against tiny sprites: the radius is clamped so every
    rectangle/pieslice coordinate stays inside the image (Pillow raises
    ValueError when x1 < x0, which previously silently killed sprite
    replacement for the small scrollbar sprites).
    """
    if w <= 0 or h <= 0:
        return
    r = min(radius, (w - 1) // 2, (h - 1) // 2)
    if r < 1:
        draw.rectangle([0, 0, w - 1, h - 1], fill=fill, outline=outline)
        return
    if r < 2:
        draw.rectangle([0, 0, w - 1, h - 1], fill=fill, outline=outline)
        return
    # Four corner arcs
    d = 2 * r
    draw.pieslice([0, 0, d - 1, d - 1], 180, 270, fill=fill)
    draw.pieslice([w - d, 0, w - 1, d - 1], 270, 360, fill=fill)
    draw.pieslice([w - d, h - d, w - 1, h - 1], 0, 90, fill=fill)
    draw.pieslice([0, h - d, d - 1, h - 1], 90, 180, fill=fill)
    # Fill gaps
    draw.rectangle([r, 0, w - r - 1, h - 1], fill=fill)
    draw.rectangle([0, r, w - 1, h - r - 1], fill=fill)
    if outline:
        draw.arc([0, 0, d - 1, d - 1], 180, 270, fill=outline, width=1)
        draw.arc([w - d, 0, w - 1, d - 1], 270, 360, fill=outline, width=1)
        draw.arc([w - d, h - d, w - 1, h - 1], 0, 90, fill=outline, width=1)
        draw.arc([0, h - d, d - 1, h - 1], 90, 180, fill=outline, width=1)
        draw.line([r, 0, w - r - 1, 0], fill=outline)
        draw.line([r, h - 1, w - r - 1, h - 1], fill=outline)
        draw.line([0, r, 0, h - r - 1], fill=outline)
        draw.line([w - 1, r, w - 1, h - r - 1], fill=outline)


# ── Main entry point ────────────────────────────────────────────────────

def fix_sv_ttk_sprites(root: tk.Tk, pal: dict) -> None:
    """
    After sv_ttk.set_theme(), replace its grey sprites with themed ones.

    Strategy:
    1. Determine which sv_ttk theme is loaded (dark/light)
    2. Query sv_ttk's I() array to get the correct Tcl image name for
       each sprite (fixes the old broken size-based mapping)
    3. Generate themed replacements via Pillow
    4. Copy replacement data into the original Tcl images
    5. Re-register check/radio indicator elements for proper state changes
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        logger.warning("Pillow not available — sv_ttk sprites unchanged")
        return

    # ── Step 1: Find the correct sv_ttk Tcl namespace ──
    # sv_ttk stores images in ttk::theme::sv_dark::I(name) or
    # ttk::theme::sv_light::I(name).  Determine which is active.
    tcl_ns = None
    for ns_candidate in ("sv_dark", "sv_light"):
        try:
            exists = root.tk.call("info", "commands",
                                  f"ttk::theme::{ns_candidate}::load_images")
            # If the namespace variable I exists, we found it
            root.tk.call("set", f"ttk::theme::{ns_candidate}::I(card)")
            tcl_ns = f"ttk::theme::{ns_candidate}"
            break
        except Exception:
            continue

    if tcl_ns is None:
        logger.warning("Cannot find sv_ttk theme namespace — skipping sprite fix")
        return

    logger.info("Found sv_ttk namespace: %s", tcl_ns)

    # ── Step 2: Build sprite → Tcl image name mapping using sv_ttk's I() array ──
    sprite_to_tcl = {}
    for sname, sx, sy, sw, sh in SPRITE_DEFS:
        try:
            tcl_img_name = root.tk.call("set", f"{tcl_ns}::I({sname})")
            sprite_to_tcl[sname] = tcl_img_name
        except Exception:
            continue

    if len(sprite_to_tcl) < 10:
        logger.info("Only matched %d sprites via namespace lookup — skipping",
                    len(sprite_to_tcl))
        return

    logger.info("Matched %d/%d sv_ttk sprites via namespace lookup",
                len(sprite_to_tcl), len(SPRITE_DEFS))

    # ── Step 3: Determine theme colours from palette ──
    bg      = pal.get("bg", "#1e1e1e")
    panel2  = pal.get("panel2", "#2a2a2a")
    panel   = pal.get("panel", "#252525")
    accent  = pal.get("accent", pal.get("progress", "#4a8c62"))
    entrybg = pal.get("entrybg", bg)
    border  = pal.get("border_color", panel2)
    text_fg = pal.get("text", "#ffffff")
    muted   = pal.get("muted", "#888888")

    # ── Step 4: Generate themed replacements and copy into Tcl images ──
    replaced = 0
    for sprite_name, sw, sh in [(s[0], s[3], s[4]) for s in SPRITE_DEFS]:
        if sprite_name not in sprite_to_tcl:
            continue
        tcl_name = sprite_to_tcl[sprite_name]

        try:
            # Determine fill colour based on sprite name
            fill = _pick_color(sprite_name, bg, panel2, panel, accent,
                               entrybg, border, text_fg, muted)

            img = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            sn = sprite_name.lower()

            if any(k in sn for k in ("card", "notebook-border")):
                _draw_rounded_rect(draw, sw, sh, 8,
                    _alpha(fill, 255))

            elif any(k in sn for k in ("textbox", "entry")):
                _draw_rounded_rect(draw, sw, sh, 5,
                    _alpha(fill, 255),
                    outline=_alpha(border, 200))

            elif any(k in sn for k in ("button-accent",)):
                _draw_rounded_rect(draw, sw, sh, 5,
                    _alpha(fill, 255))

            elif any(k in sn for k in ("button-", "heading-")):
                _draw_rounded_rect(draw, sw, sh, 5,
                    _alpha(fill, 255))

            elif any(k in sn for k in ("check-", "check_")):
                if "unsel" in sn:
                    # Unchecked state — no checkmark, just rounded rect with border
                    _draw_rounded_rect(draw, sw, sh, 4,
                        _alpha(fill, 255),
                        outline=_alpha(border, 120))
                else:
                    # Checked / tri state — rounded rect with checkmark
                    _draw_rounded_rect(draw, sw, sh, 4,
                        _alpha(fill, 255))
                    if "dis" in sn:
                        draw.line([(6, 11), (9, 14), (14, 6)],
                                  fill=_alpha(muted, 255), width=2)
                    else:
                        draw.line([(6, 11), (9, 14), (14, 6)],
                                  fill=_alpha(text_fg, 255), width=2)

            elif any(k in sn for k in ("radio-", "radio_")):
                if "unsel" not in sn and "dis" not in sn:
                    # Selected radio — circle with dot
                    draw.ellipse([1, 1, sw - 2, sh - 2],
                                 fill=_alpha(fill, 255),
                                 outline=_alpha(border, 120))
                    draw.ellipse([5, 5, sw - 6, sh - 6],
                                 fill=_alpha(text_fg, 255))
                else:
                    draw.ellipse([1, 1, sw - 2, sh - 2],
                                 fill=_alpha(fill, 255),
                                 outline=_alpha(border, 120))

            elif any(k in sn for k in ("switch-", "switch_")):
                _draw_rounded_rect(draw, sw, sh, 8,
                    _alpha(fill, 255))
                # Draw the toggle dot
                if "off" not in sn and "dis" not in sn:
                    cx = sw - 14
                    draw.ellipse([cx, 3, cx + 10, sh - 3],
                                 fill=_alpha(text_fg, 255))
                else:
                    draw.ellipse([4, 3, 14, sh - 3],
                                 fill=_alpha(muted, 255))

            elif any(k in sn for k in ("tab-",)):
                # NOTE: ("tab-") — without the trailing comma — is a plain
                # string, so `for k in "tab-"` iterates the CHARACTERS
                # t/a/b/- and matched nearly every sprite name (every name
                # containing a hyphen!).  That bug swallowed the scrollbar
                # sprites (scrollbar-thumb/trough/up/down/left/right) and
                # "empty", routing them into the tab branch where the
                # 6px-radius rounded rect cannot fit a 12x20 sprite —
                # Pillow then raised ValueError and those sprites kept
                # sv_ttk's baked grey (the grey scrollbars).  The trailing
                # comma turns it back into a 1-element tuple.
                _draw_rounded_rect(draw, sw, sh, 6,
                    _alpha(fill, 255))

            elif any(k in sn for k in ("slider-thumb",)):
                draw.ellipse([0, 0, sw - 1, sh - 1],
                             fill=_alpha(fill, 255))

            elif any(k in sn for k in ("slider-trough",)):
                _draw_rounded_rect(draw, sw, sh, 4,
                    _alpha(fill, 255),
                    outline=_alpha(border, 100))

            elif any(k in sn for k in ("progressbar-bar",)):
                _draw_rounded_rect(draw, sw, sh, 2,
                    _alpha(fill, 255))

            elif any(k in sn for k in ("progressbar-trough",)):
                _draw_rounded_rect(draw, sw, sh, 2,
                    _alpha(fill, 255),
                    outline=_alpha(border, 100))

            elif any(k in sn for k in ("scrollbar-thumb",)):
                _draw_rounded_rect(draw, sw, sh, 3,
                    _alpha(fill, 200))

            elif any(k in sn for k in ("scrollbar-trough",)):
                _draw_rounded_rect(draw, sw, sh, 2,
                    _alpha(_darken(bg, 15), 100))

            elif any(k in sn for k in ("scrollbar-",)):
                # Arrow buttons — small triangles
                _draw_rounded_rect(draw, sw, sh, 2,
                    _alpha(fill, 150))
                mid = sw // 2
                if "up" in sn:
                    draw.polygon([(2, sh - 2), (sw - 2, sh - 2), (mid, 1)],
                                 fill=_alpha(muted, 255))
                elif "down" in sn:
                    draw.polygon([(2, 2), (sw - 2, 2), (mid, sh - 1)],
                                 fill=_alpha(muted, 255))
                elif "left" in sn:
                    draw.polygon([(sw - 2, 2), (sw - 2, sh - 2), (1, sh // 2)],
                                 fill=_alpha(muted, 255))
                elif "right" in sn:
                    draw.polygon([(2, 2), (2, sh - 2), (sw - 1, sh // 2)],
                                 fill=_alpha(muted, 255))

            elif sn == "down":
                mid = sw // 2
                draw.polygon([(1, 0), (sw - 2, 0), (mid, sh - 1)],
                             fill=_alpha(muted, 255))

            elif sn == "up":
                mid = sw // 2
                draw.polygon([(1, sh - 1), (sw - 2, sh - 1), (mid, 0)],
                             fill=_alpha(muted, 255))

            elif sn == "right":
                mid = sh // 2
                draw.polygon([(0, 1), (0, sh - 2), (sw - 1, mid)],
                             fill=_alpha(muted, 255))

            elif sn == "sep":
                draw.rectangle([0, 0, sw - 1, sh - 1],
                               fill=_alpha(border, 200))

            elif sn in ("empty", "grip"):
                pass  # Leave transparent

            else:
                # Fallback: use bg color
                _draw_rounded_rect(draw, sw, sh, 4,
                    _alpha(fill, 200))

            # Convert to tk.PhotoImage and copy into the Tcl image
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            temp = tk.PhotoImage(data=buf.read(), master=root)

            # Copy themed data into sv_ttk's image
            root.tk.call(tcl_name, "copy", str(temp))

            replaced += 1

        except Exception as exc:
            logger.warning("  Skip %s (%s): %s", sprite_name, tcl_name, exc,
                           exc_info=True)

    logger.info("Replaced %d/%d sv_ttk sprites with themed colours",
                replaced, len(sprite_to_tcl))

    # ── Step 5: Re-register check/radio indicator elements ──
    # The ttk image element system does not always detect pixel-level
    # changes to photo images created by sv_ttk.  Creating NEW
    # PhotoImage objects and re-registering the element forces the
    # theme engine to properly switch images on state changes.
    # This fixes the "checkbox goes blank on click" issue.
    _rebuild_indicator_elements(root, pal, sprite_to_tcl, bg, panel2,
                                panel, accent, entrybg, border, text_fg, muted)


def _pick_color(name, bg, panel2, panel, accent, entrybg, border, text_fg, muted):
    """Pick the appropriate fill colour for a sprite based on its name + state."""
    n = name.lower()

    # ── Accent buttons ──
    if "accent" in n:
        if "dis" in n:    return _darken(accent, 40)
        if "pressed" in n: return _darken(accent, 20)
        if "hover" in n:   return _lighten(accent, 25)
        if "focus" in n:   return _lighten(accent, 15)
        return accent

    # ── Regular buttons ──
    if "button" in n or "heading" in n:
        if "dis" in n:    return _darken(panel2, 30)
        if "pressed" in n: return _darken(panel2, 15)
        if "hover" in n:   return _lighten(panel2, 15)
        if "focus" in n:   return _lighten(panel2, 10)
        return panel2

    # ── Textbox / Entry ──
    if "textbox" in n or "entry" in n:
        if "dis" in n:    return _darken(bg, 30)
        if "error" in n:   return "#662222"
        if "focus" in n:   return _lighten(entrybg, 8)
        if "hover" in n:   return _lighten(entrybg, 5)
        return entrybg

    # ── Card / Frame / Notebook ──
    if any(k in n for k in ("card", "notebook-border")):
        return bg

    # ── Tabs ──
    if "tab" in n:
        if "selected" in n: return accent
        if "hover" in n:    return _lighten(panel2, 15)
        return panel2

    # ── Switch ──
    if "switch" in n:
        if "off" not in n and "dis" not in n:
            return accent
        return _darken(panel2, 10)

    # ── Checkboxes ──
    if "check" in n:
        # Checked states (check-rest, check-focus, etc.) get accent fill
        # Unchecked states (check-unsel-*) get panel2 fill
        # Indeterminate (check-tri-*) get accent fill
        if "unsel" in n:
            if "dis" in n:    return _darken(panel2, 30)
            if "pressed" in n: return _darken(panel2, 15)
            if "hover" in n:   return _lighten(panel2, 15)
            if "focus" in n:   return _lighten(panel2, 8)
            return panel2
        # Checked / tri / disabled-checked states
        if "dis" in n:    return _darken(accent, 40)
        if "pressed" in n: return _darken(accent, 20)
        if "hover" in n:   return _lighten(accent, 15)
        if "focus" in n:   return _lighten(accent, 10)
        return accent

    # ── Radio buttons ──
    if "radio" in n:
        # Selected states get accent fill; unsel states get panel2
        if "unsel" in n:
            if "dis" in n:    return _darken(panel2, 30)
            if "pressed" in n: return _darken(panel2, 15)
            if "hover" in n:   return _lighten(panel2, 15)
            if "focus" in n:   return _lighten(panel2, 8)
            return panel2
        # Selected states
        if "dis" in n:    return _darken(accent, 40)
        if "pressed" in n: return _darken(accent, 20)
        if "hover" in n:   return _lighten(accent, 15)
        if "focus" in n:   return _lighten(accent, 10)
        return accent

    # ── Slider thumb ──
    if "slider-thumb" in n:
        if "dis" in n:    return _darken(bg, 30)
        if "pressed" in n: return _darken(accent, 20)
        if "hover" in n:   return _lighten(accent, 25)
        if "focus" in n:   return _lighten(accent, 10)
        return accent

    # ── Slider trough ──
    if "slider-trough" in n:
        return _darken(bg, 10)

    # ── Progress bar ──
    if "progressbar-bar" in n:
        return accent

    if "progressbar-trough" in n:
        return _darken(bg, 15)

    # ── Scrollbar thumb ──
    if "scrollbar-thumb" in n:
        return _lighten(panel2, 20)

    # ── Scrollbar trough ──
    if "scrollbar-trough" in n:
        return _darken(bg, 10)

    # ── Scrollbar arrows ──
    if "scrollbar-" in n or n in ("down", "up", "right"):
        return panel2

    # ── Misc ──
    if n == "sep":
        return border

    return panel2


# ── Indicator element re-registration ───────────────────────────────────

# State maps copied from sv_ttk/theme/dark.tcl lines 152-171 and 244-257.
# Order matters: Tcl evaluates from first to last; first match wins.
_CHECK_STATE_MAP = [
    # (tcl_state_spec, sprite_name)
    (None,                         "check-unsel-rest"),       # default
    ("alternate disabled",        "check-tri-dis"),
    ("selected disabled",        "check-dis"),
    ("disabled",                 "check-unsel-dis"),
    ("pressed alternate",        "check-tri-hover"),
    ("active focus alternate",   "check-tri-focus-hover"),
    ("active alternate",         "check-tri-hover"),
    ("focus alternate",          "check-tri-focus"),
    ("alternate",                "check-tri-rest"),
    ("pressed selected",         "check-hover"),
    ("active focus selected",    "check-focus-hover"),
    ("active selected",          "check-hover"),
    ("focus selected",           "check-focus"),
    ("selected",                 "check-rest"),
    ("pressed !selected",        "check-unsel-pressed"),
    ("active focus",             "check-unsel-focus-hover"),
    ("active",                   "check-unsel-hover"),
    ("focus",                    "check-unsel-focus"),
]

_RADIO_STATE_MAP = [
    (None,                         "radio-unsel-rest"),
    ("selected disabled",        "radio-dis"),
    ("disabled",                 "radio-unsel-dis"),
    ("pressed selected",         "radio-pressed"),
    ("active focus selected",    "radio-focus-hover"),
    ("active selected",          "radio-hover"),
    ("focus selected",           "radio-focus"),
    ("selected",                 "radio-rest"),
    ("pressed !selected",        "radio-unsel-pressed"),
    ("active focus",             "radio-unsel-focus-hover"),
    ("active",                   "radio-unsel-hover"),
    ("focus",                    "radio-unsel-focus"),
]


def _rebuild_indicator_elements(root, pal, sprite_to_tcl,
                                 bg, panel2, panel, accent,
                                 entrybg, border, text_fg, muted):
    """Create new themed PhotoImages and re-register indicator elements.

    This solves the ttk image-element caching issue where pixel-level
    changes to existing photo images are not detected, causing checkboxes
    to appear blank on click until focus changes force a redraw.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return

    themed = {}
    check_radio = [s for s in SPRITE_DEFS
                    if (s[0].startswith("check") or s[0].startswith("radio"))
                    and s[0] in sprite_to_tcl]

    for sname, _sx, _sy, sw, sh in check_radio:
        fill = _pick_color(sname, bg, panel2, panel, accent,
                           entrybg, border, text_fg, muted)
        img = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        sn = sname.lower()

        if "check" in sn:
            if "unsel" in sn:
                _draw_rounded_rect(draw, sw, sh, 4,
                    _alpha(fill, 255), outline=_alpha(border, 120))
            else:
                _draw_rounded_rect(draw, sw, sh, 4, _alpha(fill, 255))
                ck_color = _alpha(muted, 255) if "dis" in sn else _alpha(text_fg, 255)
                draw.line([(6, 11), (9, 14), (14, 6)], fill=ck_color, width=2)
        elif "radio" in sn:
            if "unsel" not in sn and "dis" not in sn:
                draw.ellipse([1, 1, sw - 2, sh - 2],
                             fill=_alpha(fill, 255), outline=_alpha(border, 120))
                draw.ellipse([5, 5, sw - 6, sh - 6], fill=_alpha(text_fg, 255))
            else:
                draw.ellipse([1, 1, sw - 2, sh - 2],
                             fill=_alpha(fill, 255), outline=_alpha(border, 120))

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        themed[sname] = tk.PhotoImage(data=buf.read(), master=root)

    # Prevent garbage-collection: store on root
    if not hasattr(root, "_sv_ttk_indicator_imgs"):
        root._sv_ttk_indicator_imgs = []
    root._sv_ttk_indicator_imgs.extend(themed.values())

    def _reg_element(element_name, state_map):
        """Re-register a single indicator element with themed images.

        The image/state list must be passed as ONE Tcl list argument
        (exactly like sv_ttk's dark.tcl does):

            ttk::style element create Checkbutton.indicator image \
                [list $I(check-unsel-rest) {alternate disabled} $I(...)\n                     ...] -width 26 -sticky w

        Passing the pairs as flattened *args made Tcl parse each state
        word as a separate option, which failed with
        'bad option "alternate disabled"' and left the ORIGINAL sv_ttk
        indicator elements (with their baked-blue checked states) in
        place.
        """
        img_list = []
        for state_spec, sprite_name in state_map:
            img = themed.get(sprite_name)
            if img is None:
                continue
            if state_spec is None:
                # Default image FIRST, then pairs of {state spec} + image —
                # exactly the layout of sv_ttk's dark.tcl
                # [list $I(check-unsel-rest) {alternate disabled} $I(...) ...]
                img_list.append(str(img))
            else:
                img_list.append(state_spec)
                img_list.append(str(img))
        if not img_list:
            return
        try:
            already = set(str(x) for x in root.tk.splitlist(
                root.tk.call("ttk::style", "element", "names")))
        except Exception:
            already = set()
        if element_name in already:
            # Element exists (created by sv_ttk's dark.tcl) and references
            # the very Tcl photo images whose pixels we just recoloured via
            # copy() — Tk notifies image elements on pixel changes, so the
            # themed colours are already live for every state.  Skip.
            return
        try:
            root.tk.call("ttk::style", "element", "create",
                         element_name, "image",
                         img_list, "-width", "26", "-sticky", "w")
        except Exception as exc:
            logger.warning("Failed to re-register %s: %s", element_name, exc)

    _reg_element("Checkbutton.indicator", _CHECK_STATE_MAP)
    _reg_element("Radiobutton.indicator", _RADIO_STATE_MAP)
    logger.info("Re-registered Checkbutton & Radiobutton indicator elements")


# ── Classic-widget palette guard ─────────────────────────────────────────

def disable_classic_palette_regrey(root: tk.Tk) -> None:
    """Stop sv_ttk from re-grey-ing classic (tk) widgets on <<ThemeChanged>>.

    sv.tcl binds `configure_colors` to <<ThemeChanged>> on the toplevel
    class.  configure_colors() calls tk_setPalette() with sv_ttk's OWN
    neutral colours (#1c1c1c bg / #fafafa fg for dark, #fafafa/#1c1c1c for
    light).  Because ttk fires <<ThemeChanged>> ASYNCHRONOUSLY, that
    handler runs AFTER FrogPaper's apply_theme() has set the FrogPaper
    palette — silently repainting every classic tk widget whose colour
    matches the previous palette value back to sv_ttk grey.  This is the
    root cause of the grey patches in the left sidebar and the prompt
    builder (both are full of classic tk Frames/Canvas/Labels between
    ttk widgets).

    We remove only the configure_colors part of the binding, keeping any
    other scripts bound to the same event.  ttk styles are re-configured
    by apply_theme() anyway, so sv_ttk's ttk::style configure '.' grey
    base is overridden there; only this palette re-grey needs killing.
    """
    try:
        script = str(root.tk.call("bind", "Tk", "<<ThemeChanged>>"))
    except Exception:
        return
    if "configure_colors" not in script:
        return
    try:
        parts = root.tk.splitlist(script)
    except Exception:
        parts = [script]
    kept = [p for p in parts if "configure_colors" not in str(p)]
    new_script = " ".join(str(p) for p in kept)
    try:
        root.tk.call("bind", "Tk", "<<ThemeChanged>>", new_script)
        logger.info("Removed sv_ttk configure_colors from <<ThemeChanged>> "
                    "binding (classic widgets keep FrogPaper palette)")
    except Exception as exc:
        logger.warning("Could not rewrite <<ThemeChanged>> binding: %s", exc)
