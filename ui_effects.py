"""
ui_effects.py
-------------
Visual enhancement utilities for FrogPaper.
Provides gradient backgrounds, rounded corners, drop shadows,
glassmorphism overlays, and smooth animated transitions for tkinter widgets.

All rendering uses PIL (Pillow) so effects work on any platform.
"""

import tkinter as tk
from PIL import Image, ImageDraw, ImageFilter, ImageTk
import logging

from theme import COLOR_BLACK, COLOR_WHITE  # shared color constants (migrated inline hex)

logger = logging.getLogger(__name__)


# ─── Color Utilities ──────────────────────────────────────────────────────

def hex_to_rgb(hex_color: str) -> tuple:
    """Convert hex color string to (R, G, B) tuple."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 6:
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return (128, 128, 128)


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert (R, G, B) to hex color string."""
    return f"#{int(r):02x}{int(g):02x}{int(b):02x}"


def lerp_color(c1: str, c2: str, t: float) -> str:
    """Linearly interpolate between two hex colors. t=0 gives c1, t=1 gives c2."""
    r1, g1, b1 = hex_to_rgb(c1)
    r2, g2, b2 = hex_to_rgb(c2)
    r = r1 + (r2 - r1) * t
    g = g1 + (g2 - g1) * t
    b = b1 + (b2 - b1) * t
    return rgb_to_hex(r, g, b)


def darken(hex_color: str, factor: float = 0.15) -> str:
    """Darken a hex color by a factor (0=black, 1=unchanged)."""
    r, g, b = hex_to_rgb(hex_color)
    return rgb_to_hex(r * factor, g * factor, b * factor)


def lighten(hex_color: str, factor: float = 0.3) -> str:
    """Lighten a hex color toward white by a factor (0=unchanged, 1=white)."""
    r, g, b = hex_to_rgb(hex_color)
    r = r + (255 - r) * factor
    g = g + (255 - g) * factor
    b = b + (255 - b) * factor
    return rgb_to_hex(r, g, b)


def alpha_blend(fg_hex: str, bg_hex: str, alpha: float) -> str:
    """Blend fg over bg with given alpha (0=bg only, 1=fg only)."""
    r1, g1, b1 = hex_to_rgb(fg_hex)
    r2, g2, b2 = hex_to_rgb(bg_hex)
    r = r1 * alpha + r2 * (1 - alpha)
    g = g1 * alpha + g2 * (1 - alpha)
    b = b1 * alpha + b2 * (1 - alpha)
    return rgb_to_hex(r, g, b)


# ─── Gradient Background ──────────────────────────────────────────────────

def create_gradient_image(width: int, height: int,
                           color_top: str, color_bottom: str,
                           direction: str = "vertical") -> Image.Image:
    """
    Create a gradient image.
    
    Args:
        width: Image width in pixels
        height: Image height in pixels
        color_top: Starting color (hex)
        color_bottom: Ending color (hex)
        direction: "vertical" (top-to-bottom) or "horizontal" (left-to-right)
    
    Returns:
        PIL Image with the gradient
    """
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)
    
    r1, g1, b1 = hex_to_rgb(color_top)
    r2, g2, b2 = hex_to_rgb(color_bottom)
    
    if direction == "vertical":
        for y in range(height):
            t = y / max(height - 1, 1)
            r = int(r1 + (r2 - r1) * t)
            g = int(g1 + (g2 - g1) * t)
            b = int(b1 + (b2 - b1) * t)
            draw.line([(0, y), (width, y)], fill=(r, g, b))
    else:
        for x in range(width):
            t = x / max(width - 1, 1)
            r = int(r1 + (r2 - r1) * t)
            g = int(g1 + (g2 - g1) * t)
            b = int(b1 + (b2 - b1) * t)
            draw.line([(x, 0), (x, height)], fill=(r, g, b))
    
    return img


def create_subtle_gradient(width: int, height: int,
                           base_color: str, strength: float = 0.08) -> Image.Image:
    """
    Create a subtle gradient from a base color — slightly lighter at top,
    slightly darker at bottom. Gives depth without being obvious.
    """
    top = lighten(base_color, strength)
    bottom = darken(base_color, strength * 0.6)
    return create_gradient_image(width, height, top, bottom, "vertical")


# ─── Rounded Rectangle ────────────────────────────────────────────────────

def rounded_rect(draw: ImageDraw.ImageDraw,
                  xy: tuple, radius: int, fill=None, outline=None, width=1):
    """
    Draw a rounded rectangle on a PIL ImageDraw context.
    Compatible with both old and new Pillow versions.
    """
    x0, y0, x1, y1 = xy
    # Clamp radius so it never exceeds half the short side
    short_side = min(x1 - x0, y1 - y0)
    radius = max(0, min(radius, short_side // 2))
    
    draw_opts = {"fill": fill}
    if outline is not None:
        draw_opts["outline"] = outline
    if width != 1:
        draw_opts["width"] = width
    
    # Try the modern Pillow API first (Pillow >= 8.2)
    try:
        draw.rounded_rectangle(xy, radius=radius, **draw_opts)
    except (AttributeError, TypeError):
        # Fallback: draw using arc + rectangle primitives
        d = radius * 2
        if fill:
            # Main body
            draw.rectangle([x0 + radius, y0, x1 - radius, y1], fill=fill)
            draw.rectangle([x0, y0 + radius, x1, y1 - radius], fill=fill)
            # Four corners
            draw.pieslice([x0, y0, x0 + d, y0 + d], 180, 270, fill=fill)
            draw.pieslice([x1 - d, y0, x1, y0 + d], 270, 360, fill=fill)
            draw.pieslice([x0, y1 - d, x0 + d, y1], 90, 180, fill=fill)
            draw.pieslice([x1 - d, y1 - d, x1, y1], 0, 90, fill=fill)
        if outline:
            draw.arc([x0, y0, x0 + d, y0 + d], 180, 270, fill=outline, width=width)
            draw.arc([x1 - d, y0, x1, y0 + d], 270, 360, fill=outline, width=width)
            draw.arc([x0, y1 - d, x0 + d, y1], 90, 180, fill=outline, width=width)
            draw.arc([x1 - d, y1 - d, x1, y1], 0, 90, fill=outline, width=width)
            draw.line([x0 + radius, y0, x1 - radius, y0], fill=outline, width=width)
            draw.line([x0 + radius, y1, x1 - radius, y1], fill=outline, width=width)
            draw.line([x0, y0 + radius, x0, y1 - radius], fill=outline, width=width)
            draw.line([x1, y0 + radius, x1, y1 - radius], fill=outline, width=width)


def create_rounded_rect_image(width: int, height: int,
                               fill_color: str, radius: int = 12,
                               outline_color: str = None,
                               outline_width: int = 1) -> Image.Image:
    """
    Create an image of a rounded rectangle with transparent background.
    """
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    r, g, b = hex_to_rgb(fill_color)
    rounded_rect(draw, [0, 0, width, height], radius=radius,
                 fill=(r, g, b, 255),
                 outline=tuple(hex_to_rgb(outline_color)) if outline_color else None,
                 width=outline_width)
    return img


def create_rounded_button_image(width: int, height: int,
                                 fill_color: str, radius: int = 8,
                                 hover: bool = False) -> Image.Image:
    """
    Create a rounded button image with subtle inner gradient for depth.
    """
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Base rounded rect
    r, g, b = hex_to_rgb(fill_color if not hover else lighten(fill_color, 0.12))
    rounded_rect(draw, [0, 0, width, height], radius=radius,
                 fill=(r, g, b, 255))
    
    # Subtle top highlight (glass-like sheen)
    highlight = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    h_draw = ImageDraw.Draw(highlight)
    hr, hg, hb = 255, 255, 255
    h_alpha = 25 if not hover else 35
    # Top half highlight
    rounded_rect(h_draw, [2, 2, width - 2, height // 2 + 2], radius=radius,
                 fill=(hr, hg, hb, h_alpha))
    img = Image.alpha_composite(img, highlight)
    
    return img


# ─── Drop Shadow ──────────────────────────────────────────────────────────

def create_shadow_image(width: int, height: int,
                        shadow_color: str = COLOR_BLACK,
                        offset_x: int = 0, offset_y: int = 4,
                        blur_radius: int = 12,
                        corner_radius: int = 12,
                        opacity: float = 0.35) -> Image.Image:
    """
    Create a soft drop-shadow image for a rounded rectangle.
    Place this BEHIND a widget (using canvas or overlapping frames) to simulate elevation.
    """
    # Make shadow bigger to accommodate offset and blur
    sw = width + abs(offset_x) + blur_radius * 2
    sh = height + abs(offset_y) + blur_radius * 2
    
    img = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw the shadow shape (offset from origin)
    sx = blur_radius + max(offset_x, 0)
    sy = blur_radius + max(offset_y, 0)
    r, g, b = hex_to_rgb(shadow_color)
    a = int(255 * opacity)
    rounded_rect(draw, [sx, sy, sx + width, sy + height],
                 radius=corner_radius, fill=(r, g, b, a))
    
    # Blur to create soft shadow
    img = img.filter(ImageFilter.GaussianBlur(blur_radius))
    
    # Crop to useful region
    crop_x = blur_radius + min(offset_x, 0)
    crop_y = blur_radius + min(offset_y, 0)
    img = img.crop([crop_x, crop_y, crop_x + width + abs(offset_x),
                    crop_y + height + abs(offset_y)])
    
    return img


def create_card_image(width: int, height: int,
                      bg_color: str, corner_radius: int = 12,
                      shadow_offset: int = 3,
                      shadow_blur: int = 10,
                      border_color: str = None) -> Image.Image:
    """
    Create a complete card image with shadow + rounded rect + optional border.
    The shadow is baked into the image so you get one composite.
    """
    total_w = width + shadow_blur
    total_h = height + shadow_blur + shadow_offset
    
    # Start with shadow
    shadow = create_shadow_image(
        width, height,
        shadow_color=COLOR_BLACK,
        offset_x=0, offset_y=shadow_offset,
        blur_radius=shadow_blur,
        corner_radius=corner_radius,
        opacity=0.25
    )
    
    # Composite card on top
    card = create_rounded_rect_image(
        width, height, bg_color, radius=corner_radius,
        outline_color=border_color, outline_width=1 if border_color else 0
    )
    
    result = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    result.paste(shadow, (0, 0), shadow)
    result.paste(card, (0, 0), card)
    
    return result


# ─── Glassmorphism ─────────────────────────────────────────────────────────

def create_glassmorphism_image(width: int, height: int,
                               bg_color: str = "#1a1a2e",
                               tint_color: str = COLOR_WHITE,
                               tint_alpha: float = 0.08,
                               border_color: str = COLOR_WHITE,
                               border_alpha: float = 0.15,
                               corner_radius: int = 16,
                               blur_sigma: int = 2) -> Image.Image:
    """
    Create a glassmorphism-style panel image.
    
    Characteristics:
    - Semi-transparent tinted background
    - Subtle white border (like frosted glass edge)
    - Rounded corners
    - Optional blur (visual only — tkinter can't blur real content behind)
    
    Usage: Place on a Canvas or use as a Label image. For true glassmorphism,
    set the underlying panel's bg to a gradient/image first, then overlay this.
    """
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Tinted fill
    r, g, b = hex_to_rgb(tint_color)
    bg_r, bg_g, bg_b = hex_to_rgb(bg_color)
    fill_r = int(bg_r * (1 - tint_alpha) + r * tint_alpha)
    fill_g = int(bg_g * (1 - tint_alpha) + g * tint_alpha)
    fill_b = int(bg_b * (1 - tint_alpha) + b * tint_alpha)
    fill_a = int(255 * (0.65 + tint_alpha * 0.35))  # semi-transparent
    
    rounded_rect(draw, [0, 0, width, height], radius=corner_radius,
                 fill=(fill_r, fill_g, fill_b, fill_a))
    
    # Frosted border (subtle white edge)
    br, bg_c, bb = hex_to_rgb(border_color)
    ba = int(255 * border_alpha)
    rounded_rect(draw, [1, 1, width - 1, height - 1], radius=corner_radius - 1,
                 outline=(br, bg_c, bb, ba), width=1)
    
    # Inner highlight (top edge glow — simulates light refraction)
    highlight = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    h_draw = ImageDraw.Draw(highlight)
    # Thin bright line at top
    highlight_alpha = int(40 * border_alpha * 3)
    rounded_rect(h_draw, [corner_radius, 1, width - corner_radius, 3],
                 radius=1, fill=(255, 255, 255, highlight_alpha))
    img = Image.alpha_composite(img, highlight)
    
    # Apply slight blur for the frosted look
    if blur_sigma > 0:
        img = img.filter(ImageFilter.GaussianBlur(blur_sigma))
    
    return img


def create_glass_dialog_image(width: int, height: int,
                              bg_color: str = "#0d0d1a",
                              corner_radius: int = 20) -> Image.Image:
    """
    Create a glassmorphism overlay image suitable for dialog backdrops.
    Darker, more dramatic than panel glass.
    """
    return create_glassmorphism_image(
        width, height,
        bg_color=bg_color,
        tint_color="#4488cc",
        tint_alpha=0.06,
        border_color="#88aadd",
        border_alpha=0.12,
        corner_radius=corner_radius,
        blur_sigma=1
    )


# ─── Gradient Button ─────────────────────────────────────────────────────

def create_gradient_button_image(width: int, height: int,
                                  color_start: str, color_end: str,
                                  radius: int = 8,
                                  direction: str = "vertical") -> Image.Image:
    """
    Create a button with a gradient fill and rounded corners.
    """
    # Draw gradient on a temp image, then mask with rounded rect
    grad = create_gradient_image(width, height, color_start, color_end, direction)
    grad = grad.convert("RGBA")
    
    # Create mask
    mask = Image.new("L", (width, height), 0)
    mask_draw = ImageDraw.Draw(mask)
    rounded_rect(mask_draw, [0, 0, width, height], radius=radius, fill=255)
    
    # Apply mask
    result = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    result.paste(grad, (0, 0), mask)
    
    # Add top highlight
    highlight = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    h_draw = ImageDraw.Draw(highlight)
    rounded_rect(h_draw, [3, 2, width - 3, height // 2], radius=radius - 1,
                 fill=(255, 255, 255, 30))
    result = Image.alpha_composite(result, highlight)
    
    return result


# ─── Animated Theme Transition ─────────────────────────────────────────────

class ThemeTransition:
    """
    Manages smooth animated color transitions when switching themes.
    
    Usage:
        transition = ThemeTransition(app)
        transition.start(old_palette, new_palette, callback=app.apply_theme)
    """
    
    STEPS = 12  # Number of interpolation steps
    INTERVAL_MS = 16  # ~60fps
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self._after_id = None
    
    def start(self, old_palette: dict, new_palette: dict,
              target_widgets: dict, callback=None):
        """
        Animate from old_palette to new_palette over STEPS frames.
        
        Args:
            old_palette: Dict of {widget_key: old_color_hex}
            new_palette: Dict of {widget_key: new_color_hex}
            target_widgets: Dict of {widget_key: widget_or_list_of_widgets}
            callback: Optional function to call when animation completes
        """
        self._cancel()
        self._old = old_palette
        self._new = new_palette
        self._targets = target_widgets
        self._callback = callback
        self._step = 0
        self._animate()
    
    def _animate(self):
        if self._step > self.STEPS:
            if self._callback:
                self._callback()
            return
        
        t = self._step / self.STEPS
        # Ease-in-out curve for smoother feel
        t = t * t * (3 - 2 * t)  # smoothstep
        
        for key, widgets in self._targets.items():
            if key not in self._old or key not in self._new:
                continue
            color = lerp_color(self._old[key], self._new[key], t)
            
            if isinstance(widgets, (list, tuple)):
                for w in widgets:
                    try:
                        if isinstance(w, tk.Widget):
                            w.configure(bg=color)
                        elif hasattr(w, "configure"):  # ttk
                            pass  # ttk needs style.configure, skip mid-animation
                    except tk.TclError:
                        pass
            else:
                try:
                    if isinstance(widgets, tk.Widget):
                        widgets.configure(bg=color)
                except tk.TclError:
                    pass
        
        self._step += 1
        self._after_id = self.root.after(self.INTERVAL_MS, self._animate)
    
    def _cancel(self):
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None


# ─── Panel Background Manager ─────────────────────────────────────────────

class GradientPanel:
    """
    Manages a gradient background for a tkinter Frame or Canvas.
    
    Usage:
        panel = GradientPanel(parent_frame, color_top="#2a2a3e", color_bottom="#1a1a2e")
        # Call panel.refresh() if the frame resizes
    """
    
    def __init__(self, parent, color_top: str, color_bottom: str,
                 strength: float = 0.08, corner_radius: int = 0,
                 direction: str = "vertical"):
        self.parent = parent
        self.color_top = color_top
        self.color_bottom = color_bottom
        self.strength = strength
        self.corner_radius = corner_radius
        self.direction = direction
        self._photo = None
        self._canvas = None
        self._label = None
        self._setup()
    
    def _setup(self):
        """Create the canvas/label that displays the gradient."""
        # Use a label with a canvas background approach
        self._canvas = tk.Canvas(self.parent, highlightthickness=0, bd=0)
        self._canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self._canvas.lower()  # Send behind all sibling widgets so content stays visible
        self._canvas.bind("<Configure>", self._on_resize)
    
    def _on_resize(self, event=None):
        self.refresh()
    
    def refresh(self):
        """Redraw the gradient at current size."""
        w = self.parent.winfo_width()
        h = self.parent.winfo_height()
        if w < 10 or h < 10:
            return  # Too small, skip
        
        top = lighten(self.color_top, self.strength)
        bottom = darken(self.color_bottom, self.strength * 0.6)
        
        img = create_gradient_image(w, h, top, bottom, self.direction)
        
        if self.corner_radius > 0:
            # Apply rounded corner mask
            mask = Image.new("L", (w, h), 0)
            mask_draw = ImageDraw.Draw(mask)
            rounded_rect(mask_draw, [0, 0, w, h], radius=self.corner_radius, fill=255)
            img_rgba = img.convert("RGBA")
            img_rgba.putalpha(mask)
            img = img_rgba
        
        self._photo = ImageTk.PhotoImage(img)
        self._canvas.delete("all")
        self._canvas.create_image(0, 0, anchor="nw", image=self._photo)
    
    def update_colors(self, color_top: str, color_bottom: str):
        """Update gradient colors and refresh."""
        self.color_top = color_top
        self.color_bottom = color_bottom
        self.refresh()
    
    def destroy(self):
        """Clean up."""
        if self._canvas:
            try:
                self._canvas.destroy()
            except Exception:
                pass


class ShadowFrame:
    """
    Wraps a frame with a drop shadow effect.
    Creates a canvas behind the frame that renders a soft shadow.
    
    Usage:
        shadow = ShadowFrame(parent, width=300, height=200, radius=12)
        frame = shadow.get_inner_frame()
        # Add widgets to frame
    """
    
    def __init__(self, parent, width=300, height=200,
                 shadow_color=COLOR_BLACK, offset_y=3, blur=10,
                 corner_radius=12, bg_color=None):
        self.parent = parent
        self.corner_radius = corner_radius
        self.bg_color = bg_color or "#2a2a3e"
        
        # Outer frame holds canvas + inner frame
        self.outer = tk.Frame(parent, bg=parent.cget("bg") if hasattr(parent, "cget") else "#1a1a2e")
        
        # Shadow canvas (behind the content)
        self.canvas = tk.Canvas(self.outer, highlightthickness=0, bd=0,
                                width=width + blur, height=height + blur + offset_y)
        self.canvas.pack(side="top", anchor="nw")
        
        # Inner frame (on top of shadow)
        self.inner = tk.Frame(self.canvas, bg=self.bg_color,
                              highlightthickness=0, bd=0)
        self.inner.place(x=0, y=0, width=width, height=height)
        
        self._draw_shadow(width, height, shadow_color, offset_y, blur)
    
    def _draw_shadow(self, w, h, color, offset_y, blur):
        shadow_img = create_shadow_image(w, h, shadow_color=color,
                                         offset_x=0, offset_y=offset_y,
                                         blur_radius=blur,
                                         corner_radius=self.corner_radius,
                                         opacity=0.3)
        self._photo = ImageTk.PhotoImage(shadow_img)
        self.canvas.create_image(0, 0, anchor="nw", image=self._photo)
    
    def get_inner_frame(self) -> tk.Frame:
        return self.inner
    
    def pack(self, **kwargs):
        self.outer.pack(**kwargs)
    
    def grid(self, **kwargs):
        self.outer.grid(**kwargs)
    
    def place(self, **kwargs):
        self.outer.place(**kwargs)
    
    def update_bg(self, bg_color: str):
        self.bg_color = bg_color
        self.inner.configure(bg=bg_color)


class GlassOverlay:
    """
    Creates a glassmorphism overlay on a Canvas or Toplevel window.
    
    Usage:
        glass = GlassOverlay(dialog_toplevel, width=500, height=400,
                             bg_color="#1a1a2e", corner_radius=20)
    """
    
    def __init__(self, parent, width=500, height=400,
                 bg_color="#0d0d1a", corner_radius=20):
        self.parent = parent
        self._photo = None
        self._canvas = None
        self.corner_radius = corner_radius
        
        self._canvas = tk.Canvas(parent, highlightthickness=0, bd=0,
                                 width=width, height=height)
        self._canvas.place(x=0, y=0, relwidth=1, relheight=1)
        
        img = create_glass_dialog_image(width, height, bg_color=bg_color,
                                        corner_radius=corner_radius)
        self._photo = ImageTk.PhotoImage(img)
        self._canvas.create_image(0, 0, anchor="nw", image=self._photo)
        self._canvas.bind("<Configure>", self._on_resize)
    
    def _on_resize(self, event=None):
        w = self._canvas.winfo_width()
        h = self._canvas.winfo_height()
        if w < 20 or h < 20:
            return
        bg = self.parent.cget("bg") if hasattr(self.parent, "cget") else "#0d0d1a"
        img = create_glass_dialog_image(w, h, bg_color=bg,
                                        corner_radius=self.corner_radius)
        self._photo = ImageTk.PhotoImage(img)
        self._canvas.delete("all")
        self._canvas.create_image(0, 0, anchor="nw", image=self._photo)
    
    def refresh(self):
        self._on_resize()
    
    def destroy(self):
        if self._canvas:
            try:
                self._canvas.destroy()
            except Exception:
                pass


# ─── Keyboard accessibility ─────────────────────────────────────────────

def focus_ring_color(base_bg: str) -> str:
    """Pick a focus-ring color that visibly contrasts with ``base_bg``.

    Tries the lightened and darkened variants of the resting background
    and returns whichever is farther away in RGB distance, so the ring
    is visible on both dark and light themes.
    """
    lighter = lighten(base_bg, 0.6)
    darker = darken(base_bg, 0.45)
    br, bc, bb = hex_to_rgb(base_bg)

    def _dist(color: str) -> int:
        r, g, b = hex_to_rgb(color)
        return abs(br - r) + abs(bc - g) + abs(bb - b)

    return lighter if _dist(lighter) >= _dist(darker) else darker


def _safe_invoke(command) -> None:
    if command is None:
        return
    try:
        command()
    except Exception:
        logger.exception("Keyboard activation handler failed")


def _kb_activate(command) -> str:
    _safe_invoke(command)
    return "break"


def enable_keyboard_activation(widget: tk.Label, command, base_bg: str,
                               ring_color: str | None = None) -> tk.Label:
    """Make a click-only, Label-based custom button keyboard operable.

    - ``takefocus=True`` so Tab / Shift+Tab reach it
    - a visible focus ring: ``highlightcolor`` while focused,
      ``highlightbackground`` (matched to the resting background, so it
      is invisible) while not
    - ``<Return>`` and ``<space>`` activate the command

    Used by RoundedButton and the pinned-dropdown star/row buttons; any
    future Label-based custom button should use it too.
    """
    widget.configure(
        takefocus=True,
        highlightthickness=2,
        highlightbackground=base_bg,
        highlightcolor=ring_color or focus_ring_color(base_bg),
    )
    widget.bind("<Return>", lambda event: _kb_activate(command))
    widget.bind("<space>", lambda event: _kb_activate(command))
    return widget


def ensure_visible_focus_indicators(widget, border_color: str,
                                    ring_color: str) -> None:
    """Walk the widget tree and give classic (tk) button-like widgets a
    visible keyboard-focus ring.

    - ttk widgets are skipped: the rounded-elements style layer already
      provides focus-state visuals for them.
    - Label-based custom buttons are skipped: they manage their own ring
      via :func:`enable_keyboard_activation`.

    Safe to call repeatedly (e.g. on every theme change): it only sets
    highlight colors/thickness, never layout, and never raises.
    """
    try:
        wclass = widget.winfo_class()
    except Exception:
        return
    if wclass in ("Button", "Checkbutton", "Radiobutton"):
        try:
            if int(widget.cget("highlightthickness")) < 1:
                widget.configure(highlightthickness=1)
            widget.configure(highlightbackground=border_color,
                             highlightcolor=ring_color)
        except Exception:
            pass  # widget destroyed mid-walk
    try:
        children = widget.winfo_children()
    except Exception:
        return
    for child in children:
        ensure_visible_focus_indicators(child, border_color, ring_color)


def make_text_tab_friendly(text) -> tk.Text:
    """Make a ``tk.Text`` widget behave like every other field under Tab.

    Tk's Text class binding *consumes* the Tab key — it inserts a literal
    tab character (editable widget) or silently does nothing (disabled
    widget) — so once keyboard focus lands in a Text widget, Tab can never
    leave it. The negative-prompt Preview box was exactly such a trap.

    This helper fixes both directions:

    - **Read-only Text** (``state='disabled'``): removed from the Tab ring
      entirely via ``takefocus=0``. It is not an interactive field, so it
      has no business being a Tab stop; mouse selection/copy and wheel
      scrolling are unaffected, and direct ``focus_set()`` still works.
    - **Editable Text**: ``<Tab>`` moves focus to the next widget and
      ``<Shift-Tab>`` / ``<ISO_Left_Tab>`` to the previous one — the same
      behavior as every Entry in the app. (Consequence: a literal tab
      character can no longer be typed into the field, which prompt text
      never needed.)

    Returns the widget for chaining, and never raises: widget-level
    failures are logged so callers do not need their own guards.
    """
    try:
        if str(text.cget("state")) == "disabled":
            try:
                text.configure(takefocus=0)
            except tk.TclError:
                pass
            return text

        def _move_focus(event, mover):
            try:
                target = mover(event.widget)
                if target is not None and target is not event.widget:
                    target.focus_set()
            except Exception:
                logger.exception("Text Tab traversal failed")
            return "break"  # stop the Text class binding (no tab insert)

        text.bind("<Tab>", lambda e: _move_focus(e, lambda w: w.tk_focusNext()))
        text.bind("<Shift-Tab>", lambda e: _move_focus(e, lambda w: w.tk_focusPrev()))
        try:
            # X11 delivers Shift-Tab as the ISO_Left_Tab keysym; Windows Tk
            # may not accept that keysym at bind time, so this is best-effort
            # (the <Shift-Tab> pattern above already covers Windows delivery).
            text.bind("<ISO_Left_Tab>", lambda e: _move_focus(e, lambda w: w.tk_focusPrev()))
        except tk.TclError:
            pass
        return text
    except Exception:
        logger.exception("make_text_tab_friendly failed")
        return text


class RoundedButton:
    """
    A custom button with rounded corners, gradient fill, and hover effects.
    
    Usage:
        btn = RoundedButton(parent, text="Generate", width=180, height=38,
                           fill_color="#4a9eff", radius=10,
                           command=on_click)
        btn.pack(pady=5)
    """
    
    def __init__(self, parent, text="", width=180, height=38,
                 fill_color="#4a9eff", text_color=COLOR_WHITE,
                 radius=10, font=("Segoe UI", 10, "bold"),
                 command=None, use_gradient=False,
                 gradient_end=None):
        self.parent = parent
        self.fill_color = fill_color
        self.text_color = text_color
        self._text = text
        self.width = width
        self.height = height
        self.radius = radius
        self.font = font
        self.command = command
        self.use_gradient = use_gradient
        self.gradient_end = gradient_end or lighten(fill_color, 0.2)
        self._photo_normal = None
        self._photo_hover = None
        self._photo_pressed = None
        
        self._label = tk.Label(parent, text=text, font=font,
                               fg=text_color, bg=fill_color,
                               cursor="hand2", bd=0,
                               highlightthickness=0,
                               activeforeground=text_color,
                               compound="center")
        self._label.bind("<Enter>", self._on_enter)
        self._label.bind("<Leave>", self._on_leave)
        self._label.bind("<ButtonPress-1>", self._on_press)
        self._label.bind("<ButtonRelease-1>", self._on_release)
        # Keyboard operable: Tab-reachable with a visible focus ring;
        # Enter / Space trigger the command (see enable_keyboard_activation).
        enable_keyboard_activation(
            self._label, self._keyboard_activate, self.fill_color)
        
        self._render_images(width, height)
    
    def _render_images(self, width, height):
        """Pre-render button states."""
        if self.use_gradient:
            self._photo_normal = ImageTk.PhotoImage(
                create_gradient_button_image(width, height,
                                             self.fill_color, self.gradient_end,
                                             self.radius))
            self._photo_hover = ImageTk.PhotoImage(
                create_gradient_button_image(width, height,
                                             lighten(self.fill_color, 0.1),
                                             lighten(self.gradient_end, 0.1),
                                             self.radius))
            self._photo_pressed = ImageTk.PhotoImage(
                create_gradient_button_image(width, height,
                                             darken(self.fill_color, 0.1),
                                             darken(self.gradient_end, 0.1),
                                             self.radius))
        else:
            self._photo_normal = ImageTk.PhotoImage(
                create_rounded_button_image(width, height,
                                            self.fill_color, self.radius,
                                            hover=False))
            self._photo_hover = ImageTk.PhotoImage(
                create_rounded_button_image(width, height,
                                            self.fill_color, self.radius,
                                            hover=True))
            self._photo_pressed = ImageTk.PhotoImage(
                create_rounded_button_image(width, height,
                                            darken(self.fill_color, 0.15),
                                            self.radius, hover=False))
        
        self._label.configure(image=self._photo_normal)
        self._label.image = self._photo_normal  # prevent GC
    
    def _on_enter(self, event=None):
        self._label.configure(image=self._photo_hover, text=self._label.cget('text'), fg=self.text_color, compound="center")
        self._label.image = self._photo_hover
    
    def _on_leave(self, event=None):
        self._label.configure(image=self._photo_normal, text=self._label.cget('text'), fg=self.text_color, compound="center")
        self._label.image = self._photo_normal
    
    def _on_press(self, event=None):
        self._label.configure(image=self._photo_pressed, text=self._label.cget('text'), fg=self.text_color, compound="center")
        self._label.image = self._photo_pressed
    
    def _on_release(self, event=None):
        self._on_enter()  # Go to hover state
        if self.command:
            self.command()

    def _keyboard_activate(self):
        """Enter/Space activation: flash pressed state, run command, restore."""
        self._on_press()
        try:
            if self.command:
                self.command()
        finally:
            self._on_enter()

    def invoke(self):
        """Programmatic activation (mirrors tk.Button.invoke)."""
        self._keyboard_activate()
    
    def configure(self, **kwargs):
        """Passthrough for standard label config options.

        Blocks image= (would wipe button background) and always
        re-asserts compound="center" so text stays visible.
        """
        kwargs.pop('image', None)  # never let callers wipe our bg image
        self._text = kwargs.get('text', getattr(self, '_text', self._label.cget('text')))
        if 'fg' in kwargs:
            self.text_color = kwargs['fg']
        self._label.configure(**kwargs, compound="center")
    
    def _set_text(self, text):
        self._text = text
        self._label.configure(text=text, compound="center")
    
    def _get_text(self):
        return self._label.cget('text')
    
    def pack(self, **kwargs):
        self._label.pack(**kwargs)
    
    def grid(self, **kwargs):
        self._label.grid(**kwargs)
    
    def place(self, **kwargs):
        self._label.place(**kwargs)
    
    def __getattr__(self, name):
        """Proxy attribute access to the underlying label."""
        return getattr(self._label, name)


# ─── Convenience: Apply effects to existing widgets ────────────────────────

def add_shadow_to_widget(widget: tk.Widget, shadow_color: str = COLOR_BLACK,
                         offset_x: int = 0, offset_y: int = 3,
                         blur_radius: int = 10,
                         corner_radius: int = 10,
                         opacity: float = 0.25):
    """
    Add a drop shadow behind an existing widget by placing a canvas behind it.
    Returns the shadow canvas for cleanup later.
    """
    parent = widget.master
    shadow_img = create_shadow_image(
        widget.winfo_reqwidth(), widget.winfo_reqheight(),
        shadow_color=shadow_color,
        offset_x=offset_x, offset_y=offset_y,
        blur_radius=blur_radius,
        corner_radius=corner_radius,
        opacity=opacity
    )
    
    shadow_canvas = tk.Canvas(parent, highlightthickness=0, bd=0,
                              width=shadow_img.width, height=shadow_img.height)
    photo = ImageTk.PhotoImage(shadow_img)
    shadow_canvas.create_image(0, 0, anchor="nw", image=photo)
    shadow_canvas.image = photo  # prevent GC
    
    # Place shadow behind widget
    widget.lift(shadow_canvas)
    
    return shadow_canvas


def apply_glass_to_dialog(toplevel: tk.Toplevel, width: int = None,
                          height: int = None, corner_radius: int = 20,
                          bg_color: str = "#0d0d1a"):
    """
    Apply glassmorphism effect to a Toplevel dialog window.
    Call after the dialog content is packed.
    """
    toplevel.update_idletasks()
    w = width or toplevel.winfo_width()
    h = height or toplevel.winfo_height()
    
    glass = GlassOverlay(toplevel, w, h, bg_color=bg_color,
                         corner_radius=corner_radius)
    glass._canvas.lower()  # Send behind all other widgets
    
    # Make dialog background transparent-ish (match the glass)
    r, g, b = hex_to_rgb(bg_color)
    toplevel.configure(bg=bg_color)
    
    return glass


def make_card_frame(parent, bg_color: str, corner_radius: int = 12,
                    shadow: bool = True, padding: int = 10) -> tk.Frame:
    """
    Create a card-style frame with rounded visual corners and optional shadow.
    Returns (frame, cleanup_list) where cleanup_list contains created canvases.
    """
    cleanup = []
    
    # Shadow layer
    if shadow:
        shadow_canvas = tk.Canvas(parent, highlightthickness=0, bd=0,
                                  bg=parent.cget("bg") if hasattr(parent, "cget") else "#1a1a2e")
        shadow_canvas.place(relx=0.5, rely=0.5, anchor="center")
        cleanup.append(shadow_canvas)
    
    # Card frame
    frame = tk.Frame(parent, bg=bg_color, highlightthickness=0, bd=0)
    frame.pack_propagate(False)
    
    if shadow:
        frame.lift(shadow_canvas)
    
    return frame, cleanup


def create_rounded_button_for_sidebar(parent, text: str, width: int, height: int,
                                       fill_color: str, text_color: str = COLOR_WHITE,
                                       font: tuple = None, command=None) -> RoundedButton:
    """
    Convenience factory for sidebar-style rounded buttons.
    """
    if font is None:
        font = ("Segoe UI", 10, "bold")
    return RoundedButton(
        parent, text=text, width=width, height=height,
        fill_color=fill_color, text_color=text_color,
        radius=10, font=font, command=command,
        use_gradient=True
    )
