"""
icons.py — Central icon rendering system for FrogPaper.

All icons are drawn programmatically with PIL ImageDraw so there are
zero external asset dependencies.  Icons are theme-aware (colours are
passed in) and cached per (name, size, colour) tuple.

Usage in any widget:
    from icons import get_icon
    icon_img = get_icon("image", size=16, color="#4ade80")
    ttk.Button(parent, image=icon_img, text="Set as Wallpaper")

For a compound (icon + text) button:
    ttk.Button(parent, image=get_icon("star"), text=" Save to Favorites")
"""

from __future__ import annotations

import math
import threading
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageTk

# ── Cache ───────────────────────────────────────────────────────────
_cache: dict[Tuple[str, int, str], ImageTk.PhotoImage] = {}
_cache_lock = threading.Lock()

# Try to load a decent font for icon labels (fallback: default)
_ICON_FONT: Optional[ImageFont.FreeTypeFont] = None
for _fn in ["Segoe UI Symbol", "Segoe UI", "Arial", "DejaVu Sans", "Helvetica"]:
    try:
        _ICON_FONT = ImageFont.truetype(_fn, 12)
        break
    except Exception:
        continue


def _img(size: int, bg: Optional[str] = None) -> Tuple[Image.Image, ImageDraw.ImageDraw]:
    """Create a new RGBA image + draw context."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0) if bg is None else bg)
    return img, ImageDraw.Draw(img)


def _to_photo(img: Image.Image) -> ImageTk.PhotoImage:
    return ImageTk.PhotoImage(img)


def _hex(c: str) -> Tuple[int, int, int, int]:
    """Hex colour string -> RGBA tuple."""
    c = c.lstrip("#")
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), 255)


def _lighten(hex_color: str, pct: int = 40) -> str:
    """Lighten a hex colour by pct%."""
    r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
    f = pct / 100.0
    r = min(255, int(r + (255 - r) * f))
    g = min(255, int(g + (255 - g) * f))
    b = min(255, int(b + (255 - b) * f))
    return f"#{r:02x}{g:02x}{b:02x}"


def _darken(hex_color: str, pct: int = 30) -> str:
    """Darken a hex colour by pct%."""
    r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
    f = 1 - pct / 100.0
    return f"#{int(r*f):02x}{int(g*f):02x}{int(b*f):02x}"


# ── Icon drawing functions ──────────────────────────────────────────
# Each returns a PIL Image of the given size.


def _draw_image(s: int, c: str) -> Image.Image:
    """Landscape / photo icon — rectangle with mountain."""
    img, d = _img(s)
    p = s * 0.1  # padding
    w = s - 2 * p
    # Frame
    d.rounded_rectangle([p, p, s - p, s - p], radius=s * 0.08, outline=c, width=max(1, int(s * 0.06)))
    # Mountain
    mx = [p + w * 0.15, p + w * 0.5, p + w * 0.85]
    my = [s - p - w * 0.15, p + w * 0.3, s - p - w * 0.15]
    d.polygon([(mx[0], my[0]), (mx[1], my[1]), (mx[2], my[2])], fill=c)
    # Sun
    sr = w * 0.08
    cx, cy = p + w * 0.75, p + w * 0.25
    d.ellipse([cx - sr, cy - sr, cx + sr, cy + sr], fill=c)
    return img


def _draw_star(s: int, c: str) -> Image.Image:
    """Five-pointed star."""
    img, d = _img(s)
    cx, cy = s / 2, s / 2
    outer, inner = s * 0.42, s * 0.18
    pts = []
    for i in range(10):
        a = math.pi / 2 + i * math.pi / 5
        r = outer if i % 2 == 0 else inner
        pts.append((cx + r * math.cos(a), cy - r * math.sin(a)))
    d.polygon(pts, fill=c)
    return img


def _draw_palette(s: int, c: str) -> Image.Image:
    """Artist palette — circle with dots."""
    img, d = _img(s)
    cx, cy, r = s / 2, s / 2, s * 0.4
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=c, width=max(1, int(s * 0.06)))
    # Dots
    dr = s * 0.06
    for angle in [30, 90, 150, 210, 330]:
        a = math.radians(angle)
        dx, dy = cx + r * 0.6 * math.cos(a), cy + r * 0.6 * math.sin(a)
        d.ellipse([dx - dr, dy - dr, dx + dr, dy + dr], fill=c)
    return img


def _draw_text_edit(s: int, c: str) -> Image.Image:
    """Pencil / text-edit icon."""
    img, d = _img(s)
    p = s * 0.15
    # Pencil body (diagonal line)
    d.line([(p, s - p), (s - p, p)], fill=c, width=max(2, int(s * 0.12)))
    # Pencil tip
    tip = s * 0.1
    d.polygon([(s - p, p), (s - p - tip, p + tip * 1.5), (s - p + tip, p + tip * 1.5)], fill=c)
    # Lines (text)
    lw = max(1, int(s * 0.05))
    ly = s * 0.3
    for i in range(3):
        yy = p + i * s * 0.12
        d.line([(p, yy), (s * 0.45, yy)], fill=c, width=lw)
    return img


def _draw_delete(s: int, c: str) -> Image.Image:
    """Trash can icon."""
    img, d = _img(s)
    p = s * 0.2
    bw = s * 0.5
    bh = s * 0.45
    bx = (s - bw) / 2
    by = s * 0.3
    lw = max(1, int(s * 0.07))
    # Lid
    d.line([(bx - s * 0.05, by), (bx + bw + s * 0.05, by)], fill=c, width=lw)
    # Handle
    hx = s / 2
    d.line([(hx - s * 0.1, by - s * 0.05), (hx + s * 0.1, by - s * 0.05)], fill=c, width=lw)
    d.line([(hx, by - s * 0.05), (hx, by - s * 0.12)], fill=c, width=lw)
    # Body
    d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=s * 0.04, outline=c, width=lw)
    # Lines inside
    for i in range(3):
        lx = bx + bw * (0.25 + i * 0.25)
        d.line([(lx, by + bh * 0.2), (lx, by + bh * 0.8)], fill=c, width=max(1, int(s * 0.04)))
    return img


def _draw_random(s: int, c: str) -> Image.Image:
    """Dice icon."""
    img, d = _img(s)
    p = s * 0.15
    r = s * 0.07
    d.rounded_rectangle([p, p, s - p, s - p], radius=s * 0.12, outline=c, width=max(1, int(s * 0.06)))
    cx, cy = s / 2, s / 2
    sp = s * 0.18
    # Dice face pattern (5 dots)
    for dx, dy in [(-1, -1), (1, -1), (0, 0), (-1, 1), (1, 1)]:
        d.ellipse([cx + dx * sp - r, cy + dy * sp - r, cx + dx * sp + r, cy + dy * sp + r], fill=c)
    return img


def _draw_cancel(s: int, c: str) -> Image.Image:
    """X / close icon."""
    img, d = _img(s)
    p = s * 0.25
    lw = max(2, int(s * 0.1))
    d.line([(p, p), (s - p, s - p)], fill=c, width=lw)
    d.line([(s - p, p), (p, s - p)], fill=c, width=lw)
    return img


def _draw_save(s: int, c: str) -> Image.Image:
    """Save / download icon — floppy disk."""
    img, d = _img(s)
    p = s * 0.15
    lw = max(1, int(s * 0.06))
    # Outer
    d.rounded_rectangle([p, p, s - p, s - p], radius=s * 0.06, outline=c, width=lw)
    # Top notch
    nw = s * 0.35
    d.rectangle([s - p - nw, p, s - p, p + s * 0.3], fill=c)
    # Bottom rectangle
    bx = [p + s * 0.15, s - p - s * 0.15, s - p - s * 0.15, p + s * 0.5]
    d.rectangle([p + s * 0.15, s * 0.5, s - p - s * 0.15, s - p], outline=c, width=lw)
    return img


def _draw_folder(s: int, c: str) -> Image.Image:
    """Folder icon."""
    img, d = _img(s)
    p = s * 0.12
    lw = max(1, int(s * 0.06))
    # Tab
    d.polygon([(p, s * 0.35), (p, s * 0.2), (s * 0.4, s * 0.2), (s * 0.48, s * 0.35)], fill=c)
    # Body
    d.rounded_rectangle([p, s * 0.35, s - p, s - p], radius=s * 0.06, outline=c, width=lw)
    return img


def _draw_settings(s: int, c: str) -> Image.Image:
    """Gear / settings icon."""
    img, d = _img(s)
    cx, cy = s / 2, s / 2
    outer_r = s * 0.42
    inner_r = s * 0.18
    tooth_h = s * 0.12
    lw = max(1, int(s * 0.06))
    # Gear teeth (8 teeth)
    pts = []
    for i in range(16):
        a = i * math.pi / 8 - math.pi / 2
        r = outer_r + (tooth_h if i % 2 == 0 else 0)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    d.polygon(pts, outline=c, fill=None, width=lw)
    # Center hole
    d.ellipse([cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r], outline=c, width=lw)
    return img


def _draw_copy(s: int, c: str) -> Image.Image:
    """Copy / clipboard icon — overlapping rectangles."""
    img, d = _img(s)
    p = s * 0.15
    lw = max(1, int(s * 0.06))
    # Back rectangle
    d.rounded_rectangle([s * 0.3, p, s - p, s - p], radius=s * 0.04, outline=c, width=lw)
    # Front rectangle
    d.rounded_rectangle([p, s * 0.3, s * 0.7, s - p], radius=s * 0.04, outline=c, width=lw)
    return img


def _draw_refresh(s: int, c: str) -> Image.Image:
    """Refresh / circular arrows icon."""
    img, d = _img(s)
    cx, cy = s / 2, s / 2
    r = s * 0.32
    lw = max(2, int(s * 0.1))
    # Arc (270 degrees)
    bbox = [cx - r, cy - r, cx + r, cy + r]
    d.arc(bbox, start=30, end=300, fill=c, width=lw)
    # Arrowhead
    a = math.radians(30)
    ax, ay = cx + r * math.cos(a), cy - r * math.sin(a)
    al = s * 0.12
    d.polygon([
        (ax + al * math.cos(a + 0.5), ay - al * math.sin(a + 0.5)),
        (ax + al * math.cos(a - 1.2), ay - al * math.sin(a - 1.2)),
        (ax + al * 0.5 * math.cos(a - 0.3), ay - al * 0.5 * math.sin(a - 0.3)),
    ], fill=c)
    return img


def _draw_play(s: int, c: str) -> Image.Image:
    """Play triangle."""
    img, d = _img(s)
    p = s * 0.2
    d.polygon([(p, p), (p, s - p), (s - p, s / 2)], fill=c)
    return img


def _draw_pause(s: int, c: str) -> Image.Image:
    """Pause bars."""
    img, d = _img(s)
    bw = s * 0.18
    gap = s * 0.1
    x1 = s / 2 - bw - gap / 2
    x2 = s / 2 + gap / 2
    p = s * 0.2
    d.rounded_rectangle([x1, p, x1 + bw, s - p], radius=s * 0.03, fill=c)
    d.rounded_rectangle([x2, p, x2 + bw, s - p], radius=s * 0.03, fill=c)
    return img


def _draw_skip_next(s: int, c: str) -> Image.Image:
    """Skip forward icon."""
    img, d = _img(s)
    p = s * 0.15
    # Two triangles
    mid = s * 0.48
    d.polygon([(p, p), (p, s - p), (mid, s / 2)], fill=c)
    d.polygon([(mid, p), (mid, s - p), (s - p, s / 2)], fill=c)
    return img


def _draw_skip_prev(s: int, c: str) -> Image.Image:
    """Skip backward icon."""
    img, d = _img(s)
    p = s * 0.15
    mid = s * 0.52
    d.polygon([(s - p, p), (s - p, s - p), (mid, s / 2)], fill=c)
    d.polygon([(mid, p), (mid, s - p), (p, s / 2)], fill=c)
    return img


def _draw_info(s: int, c: str) -> Image.Image:
    """Info icon — 'i' in circle."""
    img, d = _img(s)
    cx, cy, r = s / 2, s / 2, s * 0.4
    lw = max(1, int(s * 0.06))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=c, width=lw)
    # Dot
    dr = s * 0.05
    d.ellipse([cx - dr, cy - r * 0.45 - dr, cx + dr, cy - r * 0.45 + dr], fill=c)
    # Line
    d.line([(cx, cy - r * 0.1), (cx, cy + r * 0.55)], fill=c, width=max(2, int(s * 0.08)))
    return img


def _draw_warning(s: int, c: str) -> Image.Image:
    """Warning icon — '!' in triangle."""
    img, d = _img(s)
    cx, cy = s / 2, s / 2
    r = s * 0.42
    lw = max(1, int(s * 0.06))
    pts = [(cx, cy - r), (cx - r * 0.9, cy + r * 0.6), (cx + r * 0.9, cy + r * 0.6)]
    d.polygon(pts, outline=c, fill=None, width=lw)
    # Exclamation dot
    dr = s * 0.05
    d.ellipse([cx - dr, cy + r * 0.15 - dr, cx + dr, cy + r * 0.15 + dr], fill=c)
    # Exclamation line
    d.line([(cx, cy - r * 0.2), (cx, cy + r * 0.05)], fill=c, width=max(2, int(s * 0.08)))
    return img


def _draw_error(s: int, c: str) -> Image.Image:
    """Error icon — X in circle."""
    img, d = _img(s)
    cx, cy, r = s / 2, s / 2, s * 0.4
    lw = max(1, int(s * 0.06))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=c, width=lw)
    p = s * 0.28
    xlw = max(2, int(s * 0.09))
    d.line([(cx - p, cy - p), (cx + p, cy + p)], fill=c, width=xlw)
    d.line([(cx + p, cy - p), (cx - p, cy + p)], fill=c, width=xlw)
    return img


def _draw_help(s: int, c: str) -> Image.Image:
    """Help icon — '?' in circle."""
    img, d = _img(s)
    cx, cy, r = s / 2, s / 2, s * 0.4
    lw = max(1, int(s * 0.06))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=c, width=lw)
    # Question mark (using text for the curved part)
    if _ICON_FONT:
        d.text((cx, cy - r * 0.3), "?", fill=c, font=_ICON_FONT, anchor="mm")
    else:
        d.line([(cx, cy - r * 0.3), (cx, cy + r * 0.1)], fill=c, width=max(2, int(s * 0.08)))
        d.ellipse([cx - s * 0.04, cy + r * 0.2 - s * 0.04, cx + s * 0.04, cy + r * 0.2 + s * 0.04], fill=c)
    return img


def _draw_import(s: int, c: str) -> Image.Image:
    """Import icon — arrow pointing down into box."""
    img, d = _img(s)
    cx = s / 2
    lw = max(2, int(s * 0.08))
    # Arrow shaft
    d.line([(cx, s * 0.15), (cx, s * 0.6)], fill=c, width=lw)
    # Arrow head
    d.polygon([(cx, s * 0.7), (cx - s * 0.15, s * 0.55), (cx + s * 0.15, s * 0.55)], fill=c)
    # Tray
    d.line([(s * 0.2, s * 0.75), (s * 0.8, s * 0.75)], fill=c, width=lw)
    d.line([(s * 0.2, s * 0.75), (s * 0.2, s * 0.85)], fill=c, width=lw)
    d.line([(s * 0.8, s * 0.75), (s * 0.8, s * 0.85)], fill=c, width=lw)
    return img


def _draw_export(s: int, c: str) -> Image.Image:
    """Export icon — arrow pointing up from box."""
    img, d = _img(s)
    cx = s / 2
    lw = max(2, int(s * 0.08))
    # Arrow head
    d.polygon([(cx, s * 0.15), (cx - s * 0.15, s * 0.3), (cx + s * 0.15, s * 0.3)], fill=c)
    # Arrow shaft
    d.line([(cx, s * 0.3), (cx, s * 0.6)], fill=c, width=lw)
    # Tray
    d.line([(s * 0.2, s * 0.75), (s * 0.8, s * 0.75)], fill=c, width=lw)
    d.line([(s * 0.2, s * 0.75), (s * 0.2, s * 0.85)], fill=c, width=lw)
    d.line([(s * 0.8, s * 0.75), (s * 0.8, s * 0.85)], fill=c, width=lw)
    return img


def _draw_wallpaper(s: int, c: str) -> Image.Image:
    """Monitor / wallpaper icon."""
    img, d = _img(s)
    p = s * 0.1
    lw = max(1, int(s * 0.06))
    # Screen
    d.rounded_rectangle([p, p, s - p, s * 0.7], radius=s * 0.06, outline=c, width=lw)
    # Stand
    cx = s / 2
    d.line([(cx, s * 0.7), (cx, s * 0.82)], fill=c, width=lw)
    d.line([(cx - s * 0.2, s * 0.82), (cx + s * 0.2, s * 0.82)], fill=c, width=lw)
    # Inner screen content (small landscape)
    ip = s * 0.18
    d.rounded_rectangle([ip, ip + s * 0.05, s - ip, s * 0.65], radius=s * 0.02, outline=_darken(c, 20), width=max(1, int(s * 0.03)))
    return img


def _draw_generate(s: int, c: str) -> Image.Image:
    """Magic wand / generate icon."""
    img, d = _img(s)
    p = s * 0.2
    # Wand (diagonal line)
    d.line([(p, s - p), (s * 0.65, s * 0.35)], fill=c, width=max(2, int(s * 0.1)))
    # Star at tip
    scx, scy = s * 0.72, s * 0.28
    sr = s * 0.12
    for i in range(4):
        a = i * math.pi / 4
        d.line([(scx, scy), (scx + sr * math.cos(a), scy - sr * math.sin(a))], fill=c, width=max(1, int(s * 0.05)))
    d.ellipse([scx - s * 0.03, scy - s * 0.03, scx + s * 0.03, scy + s * 0.03], fill=c)
    return img


def _draw_check(s: int, c: str) -> Image.Image:
    """Checkmark icon."""
    img, d = _img(s)
    p = s * 0.2
    lw = max(2, int(s * 0.12))
    d.line([(p, s / 2), (s * 0.4, s - p)], fill=c, width=lw)
    d.line([(s * 0.4, s - p), (s - p, p)], fill=c, width=lw)
    return img


def _draw_tag(s: int, c: str) -> Image.Image:
    """Tag icon."""
    img, d = _img(s)
    lw = max(1, int(s * 0.06))
    # Tag body
    pts = [(s * 0.15, s * 0.15), (s * 0.75, s * 0.15), (s * 0.85, s * 0.3),
           (s * 0.3, s * 0.85), (s * 0.15, s * 0.7)]
    d.polygon(pts, outline=c, fill=None, width=lw)
    # Hole
    hr = s * 0.05
    hx, hy = s * 0.25, s * 0.25
    d.ellipse([hx - hr, hy - hr, hx + hr, hy + hr], outline=c, width=lw)
    return img


def _draw_folder_move(s: int, c: str) -> Image.Image:
    """Folder with arrow (move/organize) icon."""
    img, d = _img(s)
    # Small folder
    p = s * 0.12
    lw = max(1, int(s * 0.05))
    d.polygon([(p, s * 0.35), (p, s * 0.2), (s * 0.35, s * 0.2), (s * 0.42, s * 0.35)], fill=c)
    d.rounded_rectangle([p, s * 0.35, s * 0.55, s - p], radius=s * 0.04, outline=c, width=lw)
    # Arrow
    d.line([(s * 0.65, s * 0.55), (s * 0.85, s * 0.55)], fill=c, width=max(1, int(s * 0.07)))
    d.polygon([(s * 0.85, s * 0.55), (s * 0.78, s * 0.45), (s * 0.78, s * 0.65)], fill=c)
    return img


def _draw_heart_outline(s: int, c: str) -> Image.Image:
    """Star outline icon (empty star) — uses theme colour *c*."""
    img, d = _img(s)
    lw = max(2, int(s * 0.08))
    cx, cy = s / 2, s / 2
    outer = s * 0.40
    inner = s * 0.17

    # Use the theme colour for the outline so the star blends with the palette
    outline_color = c

    # Draw star outline using lines
    pts = []
    for i in range(10):
        a = math.pi / 2 + i * math.pi / 5
        r = outer if i % 2 == 0 else inner
        pts.append((cx + r * math.cos(a), cy - r * math.sin(a)))

    # Draw outline by connecting points
    for i in range(len(pts)):
        d.line([pts[i], pts[(i + 1) % len(pts)]], fill=outline_color, width=lw)

    return img


def _draw_heart_filled(s: int, c: str) -> Image.Image:
    """Star filled icon (filled star) — uses theme colour *c*."""
    img, d = _img(s)
    cx, cy = s / 2, s / 2
    outer = s * 0.40
    inner = s * 0.17

    # Use the theme colour for fill (keeps it themed, not hard red)
    fill_color = c
    outline_color = c
    lw = max(2, int(s * 0.08))

    # Draw star points
    pts = []
    for i in range(10):
        a = math.pi / 2 + i * math.pi / 5
        r = outer if i % 2 == 0 else inner
        pts.append((cx + r * math.cos(a), cy - r * math.sin(a)))

    # Fill the star
    d.polygon(pts, fill=fill_color, outline=outline_color, width=lw)

    return img


# ── Registry ─────────────────────────────────────────────────────────
_DRAW_FUNCS = {
    "image": _draw_image,
    "star": _draw_star,
    "palette": _draw_palette,
    "text_edit": _draw_text_edit,
    "delete": _draw_delete,
    "random": _draw_random,
    "cancel": _draw_cancel,
    "save": _draw_save,
    "folder": _draw_folder,
    "settings": _draw_settings,
    "copy": _draw_copy,
    "refresh": _draw_refresh,
    "play": _draw_play,
    "pause": _draw_pause,
    "skip_next": _draw_skip_next,
    "skip_prev": _draw_skip_prev,
    "info": _draw_info,
    "warning": _draw_warning,
    "error": _draw_error,
    "help": _draw_help,
    "import": _draw_import,
    "export": _draw_export,
    "wallpaper": _draw_wallpaper,
    "generate": _draw_generate,
    "check": _draw_check,
    "tag": _draw_tag,
    "folder_move": _draw_folder_move,
    "heart_outline": _draw_heart_outline,
    "heart_filled": _draw_heart_filled,
}


# ── Public API ────────────────────────────────────────────────────────

def get_icon(name: str, size: int = 16, color: str = "#4ade80") -> ImageTk.PhotoImage:
    """Return a cached ``PhotoImage`` for *name* at *size* × *size* pixels.

    Parameters
    ----------
    name : str
        Icon identifier (see ``_DRAW_FUNCS`` keys).
    size : int
        Icon dimension in pixels.  Common values: 14, 16, 18, 20, 24.
    color : str
        Hex colour string for the icon strokes/fills.
    """
    key = (name, size, color)
    with _cache_lock:
        if key in _cache:
            return _cache[key]

    draw_func = _DRAW_FUNCS.get(name)
    if draw_func is None:
        raise ValueError(f"Unknown icon: {name!r}. Available: {sorted(_DRAW_FUNCS)}")

    pil_img = draw_func(size, color)
    photo = _to_photo(pil_img)

    with _cache_lock:
        # Re-check in case another thread created it while we were drawing
        if key not in _cache:
            _cache[key] = photo
        return _cache[key]


def clear_cache() -> None:
    """Wipe the icon cache (call on theme change if colours differ)."""
    with _cache_lock:
        _cache.clear()


def get_dialog_icon(kind: str, size: int = 24, color: str = "#4ade80") -> ImageTk.PhotoImage:
    """Return the dialog icon for *kind* ("info", "warning", "error", "ask")."""
    mapping = {"info": "info", "warning": "warning", "error": "error", "ask": "help"}
    return get_icon(mapping.get(kind, "info"), size=size, color=color)
