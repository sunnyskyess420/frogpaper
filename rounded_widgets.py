"""
rounded_widgets.py — Generate themed rounded-corner widget images with Pillow.

sv_ttk bakes widget backgrounds as PNG sprite images with fixed grey colours.
This module generates replacement images using the FrogPaper theme palette
so that every widget displays with rounded corners AND correct theme colours.

We create custom ttk elements (prefixed "Frog.") and custom ttk layouts so
they never conflict with the underlying clam theme's built-in elements.

Usage (called from app.py apply_theme):
    from rounded_widgets import apply_rounded_elements
    apply_rounded_elements(style, pal, root)
"""

from __future__ import annotations

import io
import logging
import tkinter as tk

from PIL import Image, ImageDraw

from theme import adjust_color as _theme_adjust_color

from theme import COLOR_MID_GRAY, COLOR_WHITE  # shared color constants (migrated inline hex)

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────
IMG_SIZE = 40          # Base sprite size (pixels); enough for 9-patch stretch
CORNER_R = 6           # Corner radius in pixels
BORDER_W = 2           # Border width for entry / combobox fields


# ── Drawing helpers ─────────────────────────────────────────────────────

def _safe_rect(draw: ImageDraw.ImageDraw, xy, **kw):
    """Draw a rectangle only if coordinates are valid (y1>=y0, x1>=x0)."""
    x0, y0, x1, y1 = xy[0], xy[1], xy[2], xy[3]
    if x1 >= x0 and y1 >= y0:
        draw.rectangle(list(xy), **kw)


def _rounded_rect(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    radius: int,
    fill: str | None = None,
    outline: str | None = None,
    width: int = 1,
) -> None:
    """Draw a rounded rectangle using PIL arcs + lines + filled corners."""
    x0, y0, x1, y1 = xy
    # Ensure minimum dimensions — need at least 2px in each direction
    if x1 - x0 < 2 or y1 - y0 < 2:
        # Too tiny for any rounded logic — just draw a plain rect if possible
        if x1 >= x0 and y1 >= y0:
            if outline:
                draw.rectangle([x0, y0, x1, y1], outline=outline, width=width)
            if fill:
                draw.rectangle([x0, y0, x1, y1], fill=fill)
        return
    r = min(radius, (x1 - x0) // 2, (y1 - y0) // 2)
    if r < 1:
        if outline:
            draw.rectangle([x0, y0, x1, y1], outline=outline, width=width)
        if fill:
            draw.rectangle([x0, y0, x1, y1], fill=fill)
        return
    d = 2 * r
    if outline:
        draw.arc([x0, y0, x0 + d, y0 + d], 180, 270, fill=outline, width=width)
        draw.arc([x1 - d, y0, x1, y0 + d], 270, 360, fill=outline, width=width)
        draw.arc([x1 - d, y1 - d, x1, y1], 0, 90, fill=outline, width=width)
        draw.arc([x0, y1 - d, x0 + d, y1], 90, 180, fill=outline, width=width)
        draw.line([x0 + r, y0, x1 - r, y0], fill=outline, width=width)
        draw.line([x0 + r, y1, x1 - r, y1], fill=outline, width=width)
        draw.line([x0, y0 + r, x0, y1 - r], fill=outline, width=width)
        draw.line([x1, y0 + r, x1, y1 - r], fill=outline, width=width)
    if fill:
        # Horizontal band
        _safe_rect(draw, [x0 + r, y0 + 1, x1 - r, y1 - 1], fill=fill)
        # Vertical band
        _safe_rect(draw, [x0 + 1, y0 + r, x1 - 1, y1 - r], fill=fill)
        # Four corner pieslices
        draw.pieslice([x0, y0, x0 + d, y0 + d], 180, 270, fill=fill)
        draw.pieslice([x1 - d, y0, x1, y0 + d], 270, 360, fill=fill)
        draw.pieslice([x1 - d, y1 - d, x1, y1], 0, 90, fill=fill)
        draw.pieslice([x0, y1 - d, x0 + d, y1], 90, 180, fill=fill)


def _rr(fill: str, outline: str | None = None, radius: int = CORNER_R,
        outline_w: int = 1, w: int = IMG_SIZE, h: int = IMG_SIZE) -> Image.Image:
    """Quick rounded-rect image factory. Enforces minimum 4x4 pixels."""
    w = max(w, 4)
    h = max(h, 4)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    _rounded_rect(draw, (0, 0, w - 1, h - 1), radius, fill=fill,
                  outline=outline, width=outline_w)
    return img


def _lighten(hex_color: str, amount: int = 30) -> str:
    """Lighten a color — single implementation lives in theme.py."""
    return _theme_adjust_color(hex_color, abs(amount))


def _darken(hex_color: str, amount: int = 30) -> str:
    """Darken a color — single implementation lives in theme.py."""
    return _theme_adjust_color(hex_color, -abs(amount))


def _img_to_tk(img: Image.Image, master: tk.Tk) -> tk.PhotoImage:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return tk.PhotoImage(data=buf.read(), master=master)


def _make_checkbox(fill: str, checked_fill: str, mark_color: str,
                   size: int = 20, radius: int = 3) -> dict[str, Image.Image]:
    imgs = {}
    for name, f, mark in [("off", fill, None), ("on", checked_fill, mark_color),
                          ("dis", _darken(fill, 40), _darken(mark_color, 60))]:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        _rounded_rect(draw, (1, 1, size - 2, size - 2), radius,
                      fill=f, outline=_lighten(fill, 20), width=1)
        if mark:
            draw.line([(6, 11), (9, 14), (15, 6)], fill=mark, width=2)
        imgs[name] = img
    return imgs


def _make_radio(fill: str, checked_fill: str, dot_color: str,
                size: int = 20) -> dict[str, Image.Image]:
    imgs = {}
    for name, f, dot in [("off", fill, None), ("on", checked_fill, dot_color),
                         ("dis", _darken(fill, 40), _darken(dot_color, 60))]:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([1, 1, size - 2, size - 2], fill=f,
                     outline=_lighten(fill, 20), width=1)
        if dot:
            draw.ellipse([5, 5, size - 6, size - 6], fill=dot)
        imgs[name] = img
    return imgs


def _make_arrow(color: str, size: int = 12) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    mid = size // 2
    draw.polygon([(2, 3), (size - 3, 3), (mid, size - 3)], fill=color)
    return img


def _make_thumb(color: str, size: int = 16) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([0, 0, size - 1, size - 1], fill=color)
    return img


# ══════════════════════════════════════════════════════════════════════════
#  Main entry point
# ══════════════════════════════════════════════════════════════════════════

def apply_rounded_elements(style, pal: dict, root: tk.Tk) -> None:
    """
    Generate rounded-corner images from the theme palette and register them
    as custom ttk widget elements with 'Frog.' prefix + matching layouts.

    Must be called AFTER style.theme_use("clam") and style.configure().
    """

    try:
        from PIL import Image, ImageDraw  # noqa: F811
    except ImportError:
        logger.warning("Pillow not available — rounded corners disabled")
        return

    # Palette shortcuts
    bg         = pal.get("bg", "#1e1e1e")
    panel2     = pal.get("panel2", "#2a2a2a")
    panel      = pal.get("panel", "#252525")
    accent     = pal.get("accent", pal.get("progress", "#4a8c62"))
    text_fg    = pal.get("text", COLOR_WHITE)
    button_bg  = pal.get("panel2", "#333333")
    button_fg  = pal.get("button_fg", COLOR_WHITE)
    entrybg    = pal.get("entrybg", bg)
    border     = pal.get("border_color", pal.get("panel2", "#3a3a3a"))
    muted      = pal.get("muted", COLOR_MID_GRAY)
    hover      = pal.get("button_hover", _lighten(button_bg, 25))
    tabsel     = pal.get("tabsel", _lighten(accent, 15))
    disabled_bg = _darken(bg, 20)

    # ── Make entry/combobox fields visually distinct (obviously editable) ──
    # Use a noticeably lighter background than the page bg so the user
    # can see at a glance "this area accepts input".
    entry_field_bg = _lighten(bg, 18)
    if entrybg and entrybg != bg:
        entry_field_bg = entrybg   # respect theme if explicitly set

    # Image cache — prevent GC of tk.PhotoImage objects
    if hasattr(style, "_frog_images"):
        style._frog_images.clear()
    else:
        style._frog_images = []
    cache = style._frog_images

    def register_image(img):
        """Register a PIL Image as a tk.PhotoImage and cache it."""
        tk_img = _img_to_tk(img, root)
        cache.append(tk_img)
        return tk_img

    # ── Per-widget sections, each in its own try/except ────────────────
    # This way one broken widget doesn't prevent all others from loading.

    # ════════════════════════════════════════════════════════════════
    #  ENTRY — slightly lighter bg + clear border = obviously editable
    # ════════════════════════════════════════════════════════════════
    try:
        e_rest  = register_image(_rr(entry_field_bg, outline=border, outline_w=BORDER_W))
        e_hov   = register_image(_rr(entry_field_bg, outline=_lighten(border, 40), outline_w=BORDER_W + 1))
        e_foc   = register_image(_rr(entry_field_bg, outline=accent, outline_w=BORDER_W + 1))
        e_dis   = register_image(_rr(disabled_bg, outline=_darken(border, 20), outline_w=BORDER_W))

        style.element_create("Frog.Entry.field", "image",
            e_rest, ("hover", e_hov), ("focus", e_foc), ("disabled", e_dis),
            border=BORDER_W + 2, sticky="nsew")
        style.layout("TEntry", [
            ("Frog.Entry.field", {"sticky": "nsew", "children": [
                ("Entry.padding", {"sticky": "nsew", "children": [
                    ("Entry.textarea", {"sticky": "nsew"}),
                ]}),
            ]}),
        ])
        logger.debug("  ENTRY rounded OK")
    except Exception as exc:
        logger.warning("  ENTRY rounded failed: %s", exc)

    # ════════════════════════════════════════════════════════════════
    #  COMBOBOX
    # ════════════════════════════════════════════════════════════════
    try:
        c_rest  = register_image(_rr(entry_field_bg, outline=border, outline_w=BORDER_W))
        c_hov   = register_image(_rr(entry_field_bg, outline=_lighten(border, 40), outline_w=BORDER_W + 1))
        c_foc   = register_image(_rr(entry_field_bg, outline=accent, outline_w=BORDER_W + 1))
        c_dis   = register_image(_rr(disabled_bg, outline=_darken(border, 20), outline_w=BORDER_W))
        c_ro    = register_image(_rr(button_bg, outline=border, outline_w=BORDER_W))
        c_ro_h  = register_image(_rr(hover, outline=border, outline_w=BORDER_W))
        c_ro_f  = register_image(_rr(hover, outline=accent, outline_w=BORDER_W + 1))

        style.element_create("Frog.Combobox.field", "image",
            c_rest, ("hover", c_hov), ("focus", c_foc), ("disabled", c_dis),
            ("readonly", c_ro), ("readonly hover", c_ro_h), ("readonly focus", c_ro_f),
            border=BORDER_W + 2, sticky="nsew")
        arrow_img = register_image(_make_arrow(muted))
        style.element_create("Frog.Combobox.arrow", "image", arrow_img, sticky="e")
        style.layout("TCombobox", [
            ("Frog.Combobox.field", {"sticky": "nsew", "children": [
                ("Frog.Combobox.arrow", {"side": "right", "sticky": "ns"}),
                ("Combobox.padding", {"sticky": "nsew", "children": [
                    ("Combobox.textarea", {"sticky": "nsew"}),
                ]}),
            ]}),
        ])
        logger.debug("  COMBOBOX rounded OK")
    except Exception as exc:
        logger.warning("  COMBOBOX rounded failed: %s", exc)

    # ════════════════════════════════════════════════════════════════
    #  SPINBOX
    # ════════════════════════════════════════════════════════════════
    try:
        style.element_create("Frog.Spinbox.field", "image",
            e_rest, ("hover", e_hov), ("focus", e_foc), ("disabled", e_dis),
            border=BORDER_W + 2, sticky="nsew")
        style.layout("TSpinbox", [
            ("Frog.Spinbox.field", {"side": "top", "sticky": "we", "children": [
                ("Spinbox.uparrow", {"side": "right", "sticky": "ns"}),
                ("Spinbox.downarrow", {"side": "right", "sticky": "ns"}),
                ("Spinbox.padding", {"sticky": "nswe", "children": [
                    ("Spinbox.textarea", {"sticky": "nsew"}),
                ]}),
            ]}),
        ])
        logger.debug("  SPINBOX rounded OK")
    except Exception as exc:
        logger.warning("  SPINBOX rounded failed: %s", exc)

    # ════════════════════════════════════════════════════════════════
    #  BUTTON
    # ════════════════════════════════════════════════════════════════
    try:
        b_rest = register_image(_rr(button_bg, radius=CORNER_R + 1))
        b_hov  = register_image(_rr(hover, radius=CORNER_R + 1))
        b_prs  = register_image(_rr(_darken(button_bg, 20), radius=CORNER_R + 1))
        b_dis  = register_image(_rr(disabled_bg, radius=CORNER_R + 1))
        b_foc  = register_image(_rr(button_bg, outline=accent, radius=CORNER_R + 1, outline_w=1))
        b_fh   = register_image(_rr(hover, outline=accent, radius=CORNER_R + 1, outline_w=1))

        style.element_create("Frog.Button.button", "image",
            b_rest, ("hover", b_hov), ("pressed", b_prs),
            ("disabled", b_dis), ("focus", b_foc), ("focus hover", b_fh),
            border=CORNER_R + 1, sticky="nsew")
        style.layout("TButton", [
            ("Frog.Button.button", {"sticky": "nsew", "children": [
                ("Button.padding", {"sticky": "nsew", "children": [
                    ("Button.label", {"sticky": "nsew"}),
                ]}),
            ]}),
        ])
        logger.debug("  BUTTON rounded OK")
    except Exception as exc:
        logger.warning("  BUTTON rounded failed: %s", exc)

    # ════════════════════════════════════════════════════════════════
    #  ACCENT.TBUTTON
    # ════════════════════════════════════════════════════════════════
    try:
        a_rest = register_image(_rr(accent, radius=CORNER_R + 1))
        a_hov  = register_image(_rr(_lighten(accent, 25), radius=CORNER_R + 1))
        a_prs  = register_image(_rr(_darken(accent, 20), radius=CORNER_R + 1))
        a_dis  = register_image(_rr(_darken(disabled_bg, 10), radius=CORNER_R + 1))

        style.element_create("Frog.AccentButton.button", "image",
            a_rest, ("hover", a_hov), ("pressed", a_prs), ("disabled", a_dis),
            border=CORNER_R + 1, sticky="nsew")
        style.layout("Accent.TButton", [
            ("Frog.AccentButton.button", {"sticky": "nsew", "children": [
                ("AccentButton.padding", {"sticky": "nsew", "children": [
                    ("AccentButton.label", {"sticky": "nsew"}),
                ]}),
            ]}),
        ])
        logger.debug("  ACCENT.TBUTTON rounded OK")
    except Exception as exc:
        logger.warning("  ACCENT.TBUTTON rounded failed: %s", exc)

    # ════════════════════════════════════════════════════════════════
    #  ACTIVE.TBUTTON
    # ════════════════════════════════════════════════════════════════
    try:
        pcol = pal.get("progress", accent)
        act_rest = register_image(_rr(pcol, radius=CORNER_R + 1))
        act_hov  = register_image(_rr(_lighten(pcol, 25), radius=CORNER_R + 1))

        style.element_create("Frog.Active.TButton.button", "image",
            act_rest, ("hover", act_hov),
            ("pressed", register_image(_rr(_darken(pcol, 20), radius=CORNER_R + 1))),
            ("disabled", register_image(_rr(disabled_bg, radius=CORNER_R + 1))),
            border=CORNER_R + 1, sticky="nsew")
        style.layout("Active.TButton", [
            ("Frog.Active.TButton.button", {"sticky": "nsew", "children": [
                ("Active.TButton.padding", {"sticky": "nsew", "children": [
                    ("Active.TButton.label", {"sticky": "nsew"}),
                ]}),
            ]}),
        ])
        logger.debug("  ACTIVE.TBUTTON rounded OK")
    except Exception as exc:
        logger.warning("  ACTIVE.TBUTTON rounded failed: %s", exc)

    # ════════════════════════════════════════════════════════════════
    #  TOOLBUTTON
    # ════════════════════════════════════════════════════════════════
    try:
        style.element_create("Frog.Toolbutton.button", "image",
            b_rest, ("hover", b_hov), ("pressed", b_prs),
            ("disabled", b_dis), ("focus", b_foc),
            border=CORNER_R + 1, sticky="nsew")
        style.layout("Toolbutton", [
            ("Frog.Toolbutton.button", {"sticky": "nsew", "children": [
                ("Toolbutton.padding", {"sticky": "nsew", "children": [
                    ("Toolbutton.label", {"sticky": "nsew"}),
                ]}),
            ]}),
        ])
        logger.debug("  TOOLBUTTON rounded OK")
    except Exception as exc:
        logger.warning("  TOOLBUTTON rounded failed: %s", exc)

    # ════════════════════════════════════════════════════════════════
    #  CHECKBUTTON
    # ════════════════════════════════════════════════════════════════
    try:
        cb = _make_checkbox(panel2, accent, button_fg)
        # Create wrapper elements FIRST
        style.element_create("Frog.Checkbutton.button", "from", "clam")
        style.element_create("Frog.Checkbutton.padding", "from", "clam")
        style.element_create("Frog.Checkbutton.label", "from", "clam")
        style.element_create("Frog.Checkbutton.indicator", "image",
            register_image(cb["off"]), ("selected", register_image(cb["on"])),
            ("disabled", register_image(cb["dis"])),
            ("selected disabled", register_image(cb["dis"])),
            ("hover", register_image(_make_checkbox(_lighten(panel2, 15), accent, button_fg)["off"])),
            ("selected hover", register_image(cb["on"])),
            ("focus", register_image(cb["off"])),
            ("selected focus", register_image(cb["on"])),
            border=CORNER_R, sticky="w")
        style.layout("TCheckbutton", [
            ("Frog.Checkbutton.button", {"sticky": "nsew", "children": [
                ("Frog.Checkbutton.padding", {"sticky": "nsew", "children": [
                    ("Frog.Checkbutton.indicator", {"side": "left", "sticky": ""}),
                    ("Frog.Checkbutton.label", {"side": "right", "sticky": "nsew"}),
                ]}),
            ]}),
        ])
        logger.debug("  CHECKBUTTON rounded OK")
    except Exception as exc:
        logger.warning("  CHECKBUTTON rounded failed: %s", exc)

    # ════════════════════════════════════════════════════════════════
    #  RADIOBUTTON
    # ════════════════════════════════════════════════════════════════
    try:
        rb = _make_radio(panel2, accent, button_fg)
        style.element_create("Frog.Radiobutton.button", "from", "clam")
        style.element_create("Frog.Radiobutton.padding", "from", "clam")
        style.element_create("Frog.Radiobutton.label", "from", "clam")
        style.element_create("Frog.Radiobutton.indicator", "image",
            register_image(rb["off"]), ("selected", register_image(rb["on"])),
            ("disabled", register_image(rb["dis"])),
            ("selected disabled", register_image(rb["dis"])),
            ("hover", register_image(_make_radio(_lighten(panel2, 15), accent, button_fg)["off"])),
            ("selected hover", register_image(rb["on"])),
            border=CORNER_R, sticky="w")
        style.layout("TRadiobutton", [
            ("Frog.Radiobutton.button", {"sticky": "nsew", "children": [
                ("Frog.Radiobutton.padding", {"sticky": "nsew", "children": [
                    ("Frog.Radiobutton.indicator", {"side": "left", "sticky": ""}),
                    ("Frog.Radiobutton.label", {"side": "right", "sticky": "nsew"}),
                ]}),
            ]}),
        ])
        logger.debug("  RADIOBUTTON rounded OK")
    except Exception as exc:
        logger.warning("  RADIOBUTTON rounded failed: %s", exc)

    # ════════════════════════════════════════════════════════════════
    #  SEPARATOR
    # ════════════════════════════════════════════════════════════════
    try:
        # Use a plain 1px line via ImageDraw — no rounded rect needed
        sep_img = Image.new("RGBA", (200, 2), (0, 0, 0, 0))
        sep_draw = ImageDraw.Draw(sep_img)
        sep_draw.line([(0, 0), (199, 0)], fill=border, width=1)
        sep = register_image(sep_img)
        style.element_create("Frog.Separator.separator", "image", sep, sticky="nsew")
        style.layout("TSeparator", [
            ("Frog.Separator.separator", {"sticky": "nsew"}),
        ])
        logger.debug("  SEPARATOR rounded OK")
    except Exception as exc:
        logger.warning("  SEPARATOR rounded failed: %s", exc)

    # ════════════════════════════════════════════════════════════════
    #  SCALE (slider + trough)
    # ════════════════════════════════════════════════════════════════
    try:
        style.element_create("Frog.Scale.slider", "image",
            register_image(_make_thumb(accent)),
            ("hover", register_image(_make_thumb(_lighten(accent, 30)))),
            ("pressed", register_image(_make_thumb(_darken(accent, 20)))),
            ("disabled", register_image(_make_thumb(disabled_bg))),
            sticky="")
        trough_h = register_image(_rr(_darken(bg, 10), outline=border, radius=4, outline_w=1, w=200, h=12))
        trough_v = register_image(_rr(_darken(bg, 10), outline=border, radius=4, outline_w=1, w=12, h=200))
        style.element_create("Frog.Horizontal.Scale.trough", "image",
            trough_h, border=4, sticky="ew")
        style.element_create("Frog.Vertical.Scale.trough", "image",
            trough_v, border=4, sticky="ns")
        style.element_create("Frog.Horizontal.Scale.padding", "from", "clam")
        style.element_create("Frog.Vertical.Scale.padding", "from", "clam")
        style.layout("Horizontal.TScale", [
            ("Frog.Horizontal.Scale.trough", {"sticky": "ew", "children": [
                ("Frog.Horizontal.Scale.padding", {"sticky": "nsew", "children": [
                    ("Frog.Scale.slider", {"sticky": "nsew"}),
                ]}),
            ]}),
        ])
        style.layout("Vertical.TScale", [
            ("Frog.Vertical.Scale.trough", {"sticky": "ns", "children": [
                ("Frog.Vertical.Scale.padding", {"sticky": "nsew", "children": [
                    ("Frog.Scale.slider", {"sticky": "nsew"}),
                ]}),
            ]}),
        ])
        logger.debug("  SCALE rounded OK")
    except Exception as exc:
        logger.warning("  SCALE rounded failed: %s", exc)

    # ════════════════════════════════════════════════════════════════
    #  LABELFRAME
    # ════════════════════════════════════════════════════════════════
    try:
        lf = register_image(_rr(bg, outline=border, radius=CORNER_R, outline_w=1))
        style.element_create("Frog.Labelframe.border", "image",
            lf, border=CORNER_R + 2, sticky="nsew")
        style.element_create("Frog.Labelframe.padding", "from", "clam")
        style.element_create("Frog.Labelframe.content", "from", "clam")
        style.layout("TLabelframe", [
            ("Frog.Labelframe.border", {"sticky": "nsew", "children": [
                ("Frog.Labelframe.padding", {"sticky": "nsew", "padding": 0, "children": [
                    ("Frog.Labelframe.content", {"sticky": "nsew", "expand": True}),
                ]}),
            ]}),
        ])
        logger.debug("  LABELFRAME rounded OK")
    except Exception as exc:
        logger.warning("  LABELFRAME rounded failed: %s", exc)

    # ════════════════════════════════════════════════════════════════
    #  NOTEBOOK
    # ════════════════════════════════════════════════════════════════
    try:
        nb_bdr = register_image(_rr(bg, outline=border, radius=CORNER_R, outline_w=1))
        style.element_create("Frog.Notebook.border", "image",
            nb_bdr, border=CORNER_R + 2, sticky="nsew")
        style.element_create("Frog.Notebook.tab", "image",
            register_image(_rr(pal.get("tabbg", panel), radius=CORNER_R)),
            ("selected", register_image(_rr(pal.get("tabsel", accent), radius=CORNER_R))),
            ("active", register_image(_rr(_lighten(pal.get("tabbg", panel), 15), radius=CORNER_R))),
            border=CORNER_R + 1, sticky="nsew", height=28)
        style.element_create("Frog.Notebook.client", "from", "clam")
        style.layout("TNotebook", [
            ("Frog.Notebook.border", {"children": [
                ("Frog.Notebook.client", {"sticky": "nsew"}),
            ]}),
        ])
        logger.debug("  NOTEBOOK rounded OK")
    except Exception as exc:
        logger.warning("  NOTEBOOK rounded failed: %s", exc)

    # ════════════════════════════════════════════════════════════════
    #  PROGRESSBAR
    # ════════════════════════════════════════════════════════════════
    try:
        pb_tr = register_image(_rr(_darken(bg, 10), outline=border, radius=4, outline_w=1))
        pb_br = register_image(_rr(accent, radius=4))
        style.element_create("Frog.Horizontal.Progressbar.trough", "image",
            pb_tr, border=4, sticky="ew")
        style.element_create("Frog.Horizontal.Progressbar.pbar", "image",
            pb_br, border=4, sticky="ew")
        style.element_create("Frog.Vertical.Progressbar.trough", "image",
            pb_tr, border=4, sticky="ns")
        style.element_create("Frog.Vertical.Progressbar.pbar", "image",
            pb_br, border=4, sticky="ns")
        logger.debug("  PROGRESSBAR rounded OK")
    except Exception as exc:
        logger.warning("  PROGRESSBAR rounded failed: %s", exc)

    # ════════════════════════════════════════════════════════════════
    #  SCROLLBAR
    # ════════════════════════════════════════════════════════════════
    try:
        sb_tr = register_image(_rr(panel2, radius=3))
        sb_th = register_image(_rr(pal.get("scrollbar_fg", accent), radius=3))
        style.element_create("Frog.Horizontal.Scrollbar.trough", "image",
            sb_tr, border=3, sticky="ew")
        style.element_create("Frog.Horizontal.Scrollbar.thumb", "image",
            sb_th, border=3, sticky="ew")
        style.element_create("Frog.Vertical.Scrollbar.trough", "image",
            sb_tr, border=3, sticky="ns")
        style.element_create("Frog.Vertical.Scrollbar.thumb", "image",
            sb_th, border=3, sticky="ns")
        style.layout("Horizontal.TScrollbar", [
            ("Frog.Horizontal.Scrollbar.trough", {"sticky": "ew", "children": [
                ("Horizontal.Scrollbar.leftarrow", {"side": "left"}),
                ("Horizontal.Scrollbar.rightarrow", {"side": "right"}),
                ("Frog.Horizontal.Scrollbar.thumb", {"expand": 1}),
            ]}),
        ])
        style.layout("Vertical.TScrollbar", [
            ("Frog.Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
                ("Vertical.Scrollbar.uparrow", {"side": "top"}),
                ("Vertical.Scrollbar.downarrow", {"side": "bottom"}),
                ("Frog.Vertical.Scrollbar.thumb", {"expand": 1}),
            ]}),
        ])
        logger.debug("  SCROLLBAR rounded OK")
    except Exception as exc:
        logger.warning("  SCROLLBAR rounded failed: %s", exc)

    # ════════════════════════════════════════════════════════════════
    #  CARD.TFrame
    # ════════════════════════════════════════════════════════════════
    try:
        card = register_image(_rr(panel, outline=border, radius=CORNER_R + 2, outline_w=1))
        style.element_create("Frog.Card.field", "image",
            card, border=CORNER_R + 4, sticky="nsew")
        style.element_create("Frog.Card.padding", "from", "clam")
        style.layout("Card.TFrame", [
            ("Frog.Card.field", {"children": [
                ("Frog.Card.padding", {"expand": 1}),
            ]}),
        ])
        logger.debug("  CARD.TFrame rounded OK")
    except Exception as exc:
        logger.warning("  CARD.TFrame rounded failed: %s", exc)

    logger.info("Rounded-corner widget images applied successfully")