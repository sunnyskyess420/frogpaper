"""
Style Transfer Module for FrogPaper

Provides local artistic style filters for post-processing generated images.
No API calls required - all processing happens locally using OpenCV and PIL.
"""

from __future__ import annotations

# The two probes are deliberately separate. A broken OpenCV install must not
# disable text overlay: that path only needs PIL, and used to fail with a
# misleading "image may be corrupted" dialog because ``Image`` was set to None
# by cv2's ImportError.
try:
    import numpy as np
except ImportError:
    np = None

try:
    import cv2
    CV2_AVAILABLE = cv2 is not None and np is not None
except ImportError:
    cv2 = None
    CV2_AVAILABLE = False

try:
    from PIL import Image, ImageFilter, ImageEnhance, ImageOps  # noqa: F401
    PIL_AVAILABLE = True
except ImportError:
    Image = None
    PIL_AVAILABLE = False

# Artistic filters need both; plain text overlay only needs PIL.
STYLE_TRANSFER_AVAILABLE = CV2_AVAILABLE and PIL_AVAILABLE

from pathlib import Path
from typing import Optional
import logging

from utils import get_app_dir
import sys

BASE_DIR = get_app_dir()
STYLED_DIR = BASE_DIR / "wallpapers" / "styled"

# Debug: log the directory being used
logging.debug("[style_transfer] BASE_DIR: %s", BASE_DIR)
logging.debug("[style_transfer] STYLED_DIR: %s", STYLED_DIR)
logging.debug("[style_transfer] sys.frozen: %s", getattr(sys, 'frozen', False))
logging.debug("[style_transfer] sys.executable: %s", sys.executable)

# Ensure directory exists
try:
    STYLED_DIR.mkdir(parents=True, exist_ok=True)
    logging.debug("[style_transfer] STYLED_DIR created/verified: %s", STYLED_DIR.exists())
except Exception as e:
    logging.warning("Could not create STYLED_DIR: %s", e)


def _kuwahara(img, radius=4):
    """Kuwahara filter: per-pixel pick the flattest of four windows.

    This is the technique that actually produces a painted look - flat colour
    regions with edges preserved - rather than the blur-then-sharpen approach
    the painterly styles used before.
    """
    k = radius + 1
    f = img.astype(np.float32)
    sq = f * f
    means, variances = [], []
    for oy in (-radius, 0):
        for ox in (-radius, 0):
            shifted = np.roll(f, (oy, ox), axis=(0, 1))
            shifted_sq = np.roll(sq, (oy, ox), axis=(0, 1))
            m = cv2.blur(shifted, (k, k))
            v = cv2.blur(shifted_sq, (k, k)) - m * m
            means.append(m)
            variances.append(v.sum(axis=2))
    idx = np.argmin(np.stack(variances, axis=0), axis=0)
    out = np.zeros_like(f)
    for i, m in enumerate(means):
        mask = idx == i
        out[mask] = m[mask]
    return np.clip(out, 0, 255).astype(np.uint8)


def _gray(img):
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def _work_scale(img, max_w=1100):
    """Downscale heavy filters; returns (image, needs_restore)."""
    h, w = img.shape[:2]
    if w <= max_w:
        return img, None
    s = max_w / float(w)
    return cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA), img.shape


def _restore(img, shape):
    if shape is None:
        return img
    return cv2.resize(img, (shape[1], shape[0]), interpolation=cv2.INTER_LINEAR)


def _kmeans(img, k):
    z = img.reshape((-1, 3)).astype(np.float32)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 12, 1.0)
    _, labels, centers = cv2.kmeans(z, k, None, crit, 3, cv2.KMEANS_PP_CENTERS)
    return centers.astype(np.uint8)[labels.flatten()].reshape(img.shape)


def _thicken(mask, n=1):
    return cv2.dilate(mask, np.ones((2 * n + 1, 2 * n + 1), np.uint8))


def _vignette(img, strength=0.6):
    h, w = img.shape[:2]
    kx = cv2.getGaussianKernel(w, max(1.0, w * 0.55))
    ky = cv2.getGaussianKernel(h, max(1.0, h * 0.55))
    mask = ky @ kx.T
    mask = mask / mask.max()
    mask = 1.0 - strength * (1.0 - mask)
    return (img.astype(np.float32) * mask[:, :, None]).clip(0, 255).astype(np.uint8)


class StyleTransfer:
    """Local artistic style transfer using OpenCV and PIL filters."""
    
    def __init__(self):
        self.available_styles = {
            "original": "Original (no filter)",
            "oil_painting": "Oil Painting (thick brushstrokes, blended colors)",
            "watercolor": "Watercolor (soft edges, color blooms)",
            "sketch": "Sketch (line art, pen-like strokes)",
            "line_art": "Line Art (high contrast, minimal color)",
            "comic_book": "Comic Book (bold lines, limited palette)",
            "manga": "Manga (clean lines, high contrast)",
            "sepia": "Sepia (warm brown tones, vintage)",
            "bw": "B&W (grayscale, no color)",
            "vintage": "Vintage (aged, faded look)",
            "posterize": "Posterize (reduced color palette)",
            "emboss": "Emboss (3D relief effect)",
            "edge_enhance": "Edge Enhance (sharpened edges)",
            "cyberpunk_neon": "Cyberpunk Neon (neon glow, dark shadows)",
            "vaporwave": "Vaporwave (retro synth, purple/pink palette)",
            "pixel_art": "Pixel Art (retro 8-bit style)",
            "sketch_pencil": "Sketch Pencil (charcoal-like texture)",
            "gouache": "Gouache (opaque watercolor, matte finish)",
            "art_deco": "Art Deco (geometric patterns, gold accents)",
            "surreal_dali": "Surreal Dali (dreamlike, melting forms)",
            "3d_render": "3D Render (digital 3D style, glossy)",
            "anime_key": "Anime Key (cel shading, vibrant colors)",
            "noir_bw": "Noir B&W (high contrast, dramatic shadows)",
            "vintage_sepia": "Vintage Sepia (aged photo, warm tones)",
            "pop_art": "Pop Art (bold colors, comic style)",
            "impressionist": "Impressionist (soft brushstrokes, light effects)",
        }
    
    def apply_style(self, image_path: Path, style: str) -> Optional[Path]:
        """
        Apply artistic style to an image.
        
        Args:
            image_path: Path to the original image
            style: Style name to apply
            
        Returns:
            Path to the styled image, or None if failed
        """
        if style == "original":
            return image_path
        
        if style not in self.available_styles:
            logging.warning("Unknown style requested: %s", style)
            return None
        
        try:
            # Load image
            img = cv2.imread(str(image_path))
            if img is None:
                logging.warning("Could not load image: %s", image_path)
                return None
            
            # Apply the selected style
            styled_img = self._apply_filter(img, style)
            
            # Generate output filename
            base_name = image_path.stem
            extension = image_path.suffix
            styled_filename = f"{base_name}_{style}{extension}"
            styled_path = STYLED_DIR / styled_filename
            
            # Save the styled image
            cv2.imwrite(str(styled_path), styled_img)
            
            return styled_path
            
        except Exception as e:
            logging.error("Error applying style %s: %s", style, e)
            return None
    
    def _apply_filter(self, img: np.ndarray, style: str) -> np.ndarray:
        """Apply the specific filter to the image."""
        if style == "oil_painting":
            return self._oil_painting(img)
        elif style == "watercolor":
            return self._watercolor(img)
        elif style == "sketch":
            return self._sketch(img)
        elif style == "line_art":
            return self._line_art(img)
        elif style == "comic_book":
            return self._comic_book(img)
        elif style == "manga":
            return self._manga(img)
        elif style == "sepia":
            return self._sepia(img)
        elif style == "bw":
            return self._black_and_white(img)
        elif style == "vintage":
            return self._vintage(img)
        elif style == "posterize":
            return self._posterize(img)
        elif style == "emboss":
            return self._emboss(img)
        elif style == "edge_enhance":
            return self._edge_enhance(img)
        elif style == "cyberpunk_neon":
            return self._cyberpunk_neon(img)
        elif style == "vaporwave":
            return self._vaporwave(img)
        elif style == "pixel_art":
            return self._pixel_art(img)
        elif style == "sketch_pencil":
            return self._sketch_pencil(img)
        elif style == "gouache":
            return self._gouache(img)
        elif style == "art_deco":
            return self._art_deco(img)
        elif style == "surreal_dali":
            return self._surreal_dali(img)
        elif style == "3d_render":
            return self._3d_render(img)
        elif style == "anime_key":
            return self._anime_key(img)
        elif style == "noir_bw":
            return self._noir_bw(img)
        elif style == "vintage_sepia":
            return self._vintage_sepia(img)
        elif style == "pop_art":
            return self._pop_art(img)
        elif style == "impressionist":
            return self._impressionist(img)
        else:
            return img
    
    def _oil_painting(self, img: np.ndarray) -> np.ndarray:
        """Kuwahara flats with dark creases - reads as oil on canvas."""
        small, shape = _work_scale(img, 1100)
        out = _kuwahara(small, 5)
        hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV)
        hsv[..., 1] = np.clip(hsv[..., 1].astype(np.int16) * 1.2, 0, 255).astype(np.uint8)
        out = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        creases = _thicken(cv2.Canny(_gray(out), 25, 70), 1)
        out[creases > 0] = (out[creases > 0] * 0.7).astype(np.uint8)
        return _restore(out, shape)

    def _watercolor(self, img: np.ndarray) -> np.ndarray:
        """Soft Kuwahara washes, pooled pigment, lifted paper."""
        small, shape = _work_scale(img, 1100)
        out = _kuwahara(small, 3)
        hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV)
        hsv[..., 1] = np.clip(hsv[..., 1].astype(np.int16) * 0.8, 0, 255).astype(np.uint8)
        hsv[..., 2] = np.clip(hsv[..., 2].astype(np.int16) + 20, 0, 255).astype(np.uint8)
        out = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        pools = cv2.GaussianBlur(cv2.Canny(_gray(out), 40, 100), (7, 7), 0)
        out[pools > 30] = (out[pools > 30] * 0.55).astype(np.uint8)
        return _restore(out, shape)

    def _sketch(self, img: np.ndarray) -> np.ndarray:
        """Apply sketch effect using edge detection."""
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Apply Gaussian blur
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Detect edges using Canny
        edges = cv2.Canny(blurred, 50, 150)
        
        # Invert edges
        edges_inv = cv2.bitwise_not(edges)
        
        # Convert back to BGR
        result = cv2.cvtColor(edges_inv, cv2.COLOR_GRAY2BGR)
        
        return result
    
    def _line_art(self, img: np.ndarray) -> np.ndarray:
        """Sparse ink outlines: edges only, small speckle dropped."""
        gray = cv2.GaussianBlur(_gray(img), (5, 5), 0)
        edges = cv2.Canny(gray, 80, 200)
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8))
        # drop components smaller than ~40 px so texture noise disappears
        n, labels, stats, _ = cv2.connectedComponentsWithStats(edges, 8)
        keep = np.zeros_like(edges)
        for i in range(1, n):
            if stats[i, cv2.CC_STAT_AREA] >= 40:
                keep[labels == i] = 255
        return cv2.cvtColor(255 - keep, cv2.COLOR_GRAY2BGR)

    def _comic_book(self, img: np.ndarray) -> np.ndarray:
        """Flat 6-colour print look with clean black keylines."""
        small, shape = _work_scale(img, 900)
        out = _kmeans(small, 6)
        hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV)
        hsv[..., 1] = np.clip(hsv[..., 1].astype(np.int16) * 1.35, 0, 255).astype(np.uint8)
        out = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        edges = _thicken(cv2.Canny(_gray(out), 90, 180), 1)
        out[edges > 0] = 0
        return _restore(out, shape)

    def _manga(self, img: np.ndarray) -> np.ndarray:
        """Clean ink lines over a 3-tone screentone."""
        gray = _gray(img)
        lines = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                      cv2.THRESH_BINARY, 25, 12)
        lines = cv2.medianBlur(lines, 3)
        tones = (np.round(gray.astype(np.float32) / 85.0) * 85).clip(0, 255).astype(np.uint8)
        out = np.where(lines == 0, 25, tones).astype(np.uint8)
        return cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)

    def _sepia(self, img: np.ndarray) -> np.ndarray:
        """Apply sepia tone effect."""
        # Convert to float
        img_float = img.astype(np.float32)
        
        # Apply sepia matrix
        kernel = np.array([[0.272, 0.534, 0.131],
                          [0.349, 0.686, 0.168],
                          [0.393, 0.769, 0.189]])
        
        sepia_img = cv2.transform(img_float, kernel)
        
        # Clip values to valid range
        sepia_img = np.clip(sepia_img, 0, 255)
        
        return sepia_img.astype(np.uint8)
    
    def _black_and_white(self, img: np.ndarray) -> np.ndarray:
        """Apply black and white effect."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    
    def _vintage(self, img: np.ndarray) -> np.ndarray:
        """Apply vintage/aged effect."""
        # Reduce saturation
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        hsv[:, :, 1] = hsv[:, :, 1] * 0.7  # Reduce saturation
        hsv[:, :, 2] = hsv[:, :, 2] * 0.9  # Slightly darken
        result = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        
        # Add slight sepia tone
        result = self._sepia(result)
        
        # Add vignette effect
        rows, cols = result.shape[:2]
        kernel_x = cv2.getGaussianKernel(cols, cols/2)
        kernel_y = cv2.getGaussianKernel(rows, rows/2)
        kernel = kernel_y * kernel_x.T
        mask = 255 * kernel / np.linalg.norm(kernel)
        mask = mask.astype(np.uint8)
        
        # Apply vignette
        result = cv2.cvtColor(result, cv2.COLOR_BGR2BGRA)
        mask_bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGRA)
        result = cv2.addWeighted(result, 0.7, mask_bgr, 0.3, 0)
        result = cv2.cvtColor(result, cv2.COLOR_BGRA2BGR)
        
        return result
    
    def _posterize(self, img: np.ndarray) -> np.ndarray:
        """Reduce to 6 real colours (k-means, not bit-masking)."""
        small, shape = _work_scale(img, 900)
        return _restore(_kmeans(small, 6), shape)

    def _emboss(self, img: np.ndarray) -> np.ndarray:
        """Apply emboss effect (3D relief)."""
        # Create emboss kernel
        kernel = np.array([[-2, -1, 0],
                          [-1, 1, 1],
                          [0, 1, 2]])
        
        # Apply kernel
        embossed = cv2.filter2D(img, -1, kernel)
        
        # Add gray offset
        embossed = cv2.add(embossed, 128)
        
        return embossed
    
    def _edge_enhance(self, img: np.ndarray) -> np.ndarray:
        """Unsharp mask - crisp, not black."""
        blur = cv2.GaussianBlur(img, (0, 0), 2.0)
        out = cv2.addWeighted(img, 1.9, blur, -0.9, 0)
        return np.clip(out, 0, 255).astype(np.uint8)

    def _cyberpunk_neon(self, img: np.ndarray) -> np.ndarray:
        """Dark plate, magenta/cyan edge glow."""
        base = cv2.convertScaleAbs(img, alpha=0.5, beta=-12)
        hsv = cv2.cvtColor(base, cv2.COLOR_BGR2HSV)
        hsv[..., 1] = np.clip(hsv[..., 1].astype(np.int16) * 1.7, 0, 255).astype(np.uint8)
        base = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        edges = cv2.Canny(_gray(img), 60, 140)
        glow = cv2.GaussianBlur(edges, (0, 0), 8)
        neon = np.zeros_like(img)
        neon[..., 0] = glow                     # blue
        neon[..., 1] = (glow.astype(np.float32) * 0.35).astype(np.uint8)   # green
        neon[..., 2] = (glow.astype(np.float32) * 0.85).astype(np.uint8)   # red -> magenta
        return np.clip(cv2.addWeighted(base, 1.0, neon, 1.3, 0), 0, 255).astype(np.uint8)

    def _vaporwave(self, img: np.ndarray) -> np.ndarray:
        """Apply vaporwave retro synth effect."""
        try:
            # Apply purple/pink tint using HSV color space
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            h, s, v = cv2.split(hsv)
            
            # Shift hue toward purple/magenta range (around 150-170 in OpenCV HSV)
            h = h.astype(np.float32)
            h = (h + 30) % 180  # Shift hue by 30 degrees
            h = h.astype(np.uint8)
            
            # Boost saturation for vaporwave effect
            s = cv2.multiply(s, 1.3)
            
            # Merge back
            hsv_tinted = cv2.merge([h, s, v])
            result = cv2.cvtColor(hsv_tinted, cv2.COLOR_HSV2BGR)
            
            # Add scanlines effect
            lines = np.zeros_like(result)
            for i in range(0, result.shape[0], 4):
                lines[i, :, :] = 30
            result = cv2.addWeighted(result, 0.9, lines, 0.1, 0)
            
            return result
        except Exception:
            # Fallback: simple purple tint
            try:
                purple_tint = np.array([148, 0, 211], dtype=np.float32)
                result = img.astype(np.float32)
                result = result * 0.7 + purple_tint * 0.3
                return np.clip(result, 0, 255).astype(np.uint8)
            except Exception:
                return img

    def _pixel_art(self, img: np.ndarray) -> np.ndarray:
        """Apply retro 8-bit pixel art effect."""
        try:
            # Reduce colors using k-means clustering
            data = img.reshape((-1, 3)).astype(np.float32)
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
            _, labels, centers = cv2.kmeans(data, 16, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
            centers = np.uint8(centers)
            
            # Map each pixel to its center color
            pixelated = centers[labels.flatten()]
            pixelated = pixelated.reshape(img.shape)
            
            # Downscale and upscale for pixelated look
            h, w = img.shape[:2]
            small_h, small_w = max(1, h // 8), max(1, w // 8)
            small = cv2.resize(pixelated, (small_w, small_h), interpolation=cv2.INTER_NEAREST)
            result = cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)
            
            return result
        except Exception:
            # Fallback: simple downsampling/upsampling without k-means
            try:
                h, w = img.shape[:2]
                small_h, small_w = max(1, h // 10), max(1, w // 10)
                small = cv2.resize(img, (small_w, small_h), interpolation=cv2.INTER_NEAREST)
                result = cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)
                return result
            except Exception:
                return img

    def _sketch_pencil(self, img: np.ndarray) -> np.ndarray:
        """Classic pencil dodge - soft graphite, no hard edges."""
        gray = _gray(img)
        inv = 255 - gray
        blur = cv2.GaussianBlur(inv, (21, 21), 0)
        dodge = cv2.divide(gray, 255 - blur, scale=256)
        return cv2.cvtColor(dodge, cv2.COLOR_GRAY2BGR)

    def _gouache(self, img: np.ndarray) -> np.ndarray:
        """Small Kuwahara dabs, chalky matte, faint canvas grain."""
        small, shape = _work_scale(img, 1100)
        out = _kuwahara(small, 3)
        mean = out.reshape(-1, 3).mean(axis=0)
        out = (out.astype(np.float32) * 0.7 + mean * 0.3).clip(0, 255).astype(np.uint8)
        out = cv2.convertScaleAbs(out, alpha=0.85, beta=26)
        grain = np.random.normal(0, 3.5, out.shape).astype(np.int16)
        return _restore(np.clip(out.astype(np.int16) + grain, 0, 255).astype(np.uint8), shape)

    def _art_deco(self, img: np.ndarray) -> np.ndarray:
        """Gold-on-ink duotone with a geometric frame."""
        gray = cv2.equalizeHist(_gray(img))
        t = (gray.astype(np.float32) / 255.0)[..., None]
        ink = np.array([40, 22, 14], np.float32)      # BGR
        gold = np.array([90, 190, 235], np.float32)
        out = (ink * (1.0 - t) + gold * t).astype(np.uint8)
        h, w = out.shape[:2]
        m = max(8, int(min(h, w) * 0.02))
        cv2.rectangle(out, (m, m), (w - m, h - m), (90, 190, 235), 2)
        cv2.rectangle(out, (2 * m, 2 * m), (w - 2 * m, h - 2 * m), (60, 140, 190), 1)
        return out

    def _surreal_dali(self, img: np.ndarray) -> np.ndarray:
        """Dream grade with a strong horizontal melt and colour fringing."""
        h, w = img.shape[:2]
        xs = np.arange(w, dtype=np.float32)
        ys = np.arange(h, dtype=np.float32)[:, None]
        shift = np.sin(xs / max(1.0, w / 4.0)) * (h * 0.05)
        map_x = (np.tile(xs, (h, 1)) + shift).astype(np.float32)
        map_y = (np.tile(ys, (1, w)) + shift * 0.75).astype(np.float32)
        out = cv2.remap(img, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        # colour fringing: nudge the channels apart like a bad lens
        out[..., 0] = np.roll(out[..., 0], 2, axis=1)
        out[..., 2] = np.roll(out[..., 2], -2, axis=1)
        hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV)
        hsv[..., 1] = np.clip(hsv[..., 1].astype(np.int16) * 1.3, 0, 255).astype(np.uint8)
        hsv[..., 0] = ((hsv[..., 0].astype(np.int16) + 5) % 180).astype(np.uint8)
        out = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        return _vignette(cv2.convertScaleAbs(out, alpha=1.1, beta=-12), 0.55)

    def _3d_render(self, img: np.ndarray) -> np.ndarray:
        """CG look: Kuwahara surfaces, glossy specular bloom, punchy grade."""
        small, shape = _work_scale(img, 1100)
        base = _kuwahara(small, 3)
        base = cv2.convertScaleAbs(base, alpha=1.12, beta=4)
        lum = _gray(base).astype(np.float32) / 255.0
        spec = np.clip((lum - 0.62) / 0.38, 0, 1) ** 1.4
        glow = cv2.GaussianBlur((spec[..., None] * base).astype(np.uint8), (0, 0), 14)
        out = cv2.addWeighted(base, 1.0, glow, 1.0, 0)
        return _restore(np.clip(out, 0, 255).astype(np.uint8), shape)

    def _anime_key(self, img: np.ndarray) -> np.ndarray:
        """Apply anime cel shading effect."""
        # Enhance edges and colors for anime style
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        
        # Enhance saturation
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)
        s = cv2.multiply(s, 1.3)
        enhanced_hsv = cv2.merge([h, s, v])
        enhanced = cv2.cvtColor(enhanced_hsv, cv2.COLOR_HSV2BGR)
        
        # Combine with edges
        result = cv2.addWeighted(enhanced, 0.8, cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR), 0.2, 0)
        
        return result

    def _noir_bw(self, img: np.ndarray) -> np.ndarray:
        """High-contrast black and white with a vignette."""
        gray = cv2.createCLAHE(clipLimit=3.5, tileGridSize=(8, 8)).apply(_gray(img))
        gray = cv2.convertScaleAbs(gray, alpha=1.15, beta=-12)
        return _vignette(cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR), 0.65)

    def _vintage_sepia(self, img: np.ndarray) -> np.ndarray:
        """Apply aged photo sepia effect."""
        # Convert to float
        img_float = img.astype(np.float32)
        
        # Apply sepia matrix
        kernel = np.array([[0.272, 0.534, 0.131],
                          [0.349, 0.686, 0.168],
                          [0.393, 0.769, 0.189]])
        
        sepia = cv2.transform(img_float, kernel)
        
        # Clip values to valid range
        sepia = np.clip(sepia, 0, 255)
        sepia = sepia.astype(np.uint8)
        
        # Add aging effect
        aged = cv2.addWeighted(sepia, 0.8, img, 0.2, 0)
        
        return aged

    def _pop_art(self, img: np.ndarray) -> np.ndarray:
        """Four loud colours with thin black keylines."""
        small, shape = _work_scale(img, 800)
        out = _kmeans(small, 4)
        hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV)
        hsv[..., 1] = np.clip(hsv[..., 1].astype(np.int16) * 1.6, 0, 255).astype(np.uint8)
        out = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        edges = _thicken(cv2.Canny(_gray(out), 80, 160), 1)
        out[edges > 0] = 0
        return _restore(out, shape)

    def _impressionist(self, img: np.ndarray) -> np.ndarray:
        """Fine Kuwahara dabs plus broken, dappled light."""
        small, shape = _work_scale(img, 1100)
        out = _kuwahara(small, 2)
        h, w = out.shape[:2]
        dapple = cv2.GaussianBlur(np.random.normal(0, 14, (h, w)).astype(np.float32), (0, 0), 3)
        out = np.clip(out.astype(np.float32) + dapple[:, :, None], 0, 255).astype(np.uint8)
        out = cv2.convertScaleAbs(out, alpha=1.08, beta=16)
        return _restore(out, shape)

    def get_style_list(self) -> list:
        """Get list of available styles."""
        return list(self.available_styles.keys())
    
    def get_style_name(self, style: str) -> str:
        """Get human-readable style name."""
        return self.available_styles.get(style, style)
    
    # Maps base font filenames to their bold/italic/bold-italic variants.
    # Covers Windows, macOS, and common Linux font packages.
    FONT_VARIANTS = {
        # Arial family
        "arial.ttf":             {"bold": "arialbd.ttf", "italic": "ariali.ttf", "bold_italic": "arialbi.ttf"},
        "arialmt.ttf":           {"bold": "arialbd.ttf", "italic": "ariali.ttf", "bold_italic": "arialbi.ttf"},
        # Calibri family
        "calibri.ttf":           {"bold": "calibrib.ttf", "italic": "calibrii.ttf", "bold_italic": "calibriz.ttf"},
        # Cambria family
        "cambria.ttc":           {"bold": "cambriab.ttf", "italic": "cambriai.ttf", "bold_italic": "cambriaz.ttf"},
        # Comic Sans
        "comic.ttf":             {"bold": "comicbd.ttf", "italic": "comici.ttf", "bold_italic": "comicz.ttf"},
        "comicsansms.ttf":       {"bold": "comicbd.ttf", "italic": "comici.ttf", "bold_italic": "comicz.ttf"},
        # Consolas
        "consola.ttf":           {"bold": "consolab.ttf", "italic": "consolai.ttf", "bold_italic": "consolaz.ttf"},
        "consolas.ttf":          {"bold": "consolab.ttf", "italic": "consolai.ttf", "bold_italic": "consolaz.ttf"},
        # Courier New
        "cour.ttf":              {"bold": "courbd.ttf", "italic": "couri.ttf", "bold_italic": "courbi.ttf"},
        "cournew.ttf":           {"bold": "courbd.ttf", "italic": "couri.ttf", "bold_italic": "courbi.ttf"},
        "couri.ttf":             {"bold": "courbi.ttf"},
        "courbd.ttf":            {"italic": "courbi.ttf"},
        # Georgia
        "georgia.ttf":           {"bold": "georgiab.ttf", "italic": "georgiai.ttf", "bold_italic": "georgiaz.ttf"},
        # Impact (no variants)
        # Times New Roman
        "times.ttf":             {"bold": "timesbd.ttf", "italic": "timesi.ttf", "bold_italic": "timesbi.ttf"},
        "timesnewroman.ttf":     {"bold": "timesbd.ttf", "italic": "timesi.ttf", "bold_italic": "timesbi.ttf"},
        "timesnr.ttf":           {"bold": "timesbd.ttf", "italic": "timesi.ttf", "bold_italic": "timesbi.ttf"},
        # Verdana
        "verdana.ttf":           {"bold": "verdanab.ttf", "italic": "verdanai.ttf", "bold_italic": "verdanaz.ttf"},
        # Trebuchet
        "trebuc.ttf":            {"bold": "trebucbd.ttf", "italic": "trebucit.ttf", "bold_italic": "trebucbi.ttf"},
        # Tahoma
        "tahoma.ttf":            {"bold": "tahomabd.ttf", "italic": "tahomai.ttf"},
        # Linux / cross-platform
        "dejavusans.ttf":        {"bold": "DejaVuSans-Bold.ttf", "italic": "DejaVuSans-Oblique.ttf", "bold_italic": "DejaVuSans-BoldOblique.ttf"},
        "dejavusans-bold.ttf":   {"italic": "DejaVuSans-BoldOblique.ttf"},
        "dejavusans-oblique.ttf":{"bold": "DejaVuSans-BoldOblique.ttf"},
        "liberationsans.ttf":    {"bold": "LiberationSans-Bold.ttf", "italic": "LiberationSans-Italic.ttf", "bold_italic": "LiberationSans-BoldItalic.ttf"},
        "liberationsans-bold.ttf":{"italic": "LiberationSans-BoldItalic.ttf"},
        "freesans.ttf":          {"bold": "FreeSansBold.ttf", "italic": "FreeSansOblique.ttf", "bold_italic": "FreeSansBoldOblique.ttf"},
        "freeserif.ttf":         {"bold": "FreeSerifBold.ttf", "italic": "FreeSerifItalic.ttf", "bold_italic": "FreeSerifBoldItalic.ttf"},
        "freemono.ttf":          {"bold": "FreeMonoBold.ttf", "italic": "FreeMonoOblique.ttf", "bold_italic": "FreeMonoBoldOblique.ttf"},
    }

    def _resolve_font_variant(self, font_path: str, font_size: int,
                              bold: bool = False, italic: bool = False):
        """Resolve the correct font file for bold/italic, with synthetic fallback."""
        from PIL import ImageFont

        if not font_path:
            return None, False, False  # font, needs_synthetic_bold, needs_synthetic_italic

        p = Path(font_path)
        stem_lower = p.stem.lower()
        parent = p.parent
        ext = p.suffix

        # Not bold or italic → just load the base font
        if not bold and not italic:
            try:
                return ImageFont.truetype(str(p), font_size), False, False
            except Exception:
                return None, False, False

        # Determine which variant we need
        if bold and italic:
            variant_key = "bold_italic"
        elif bold:
            variant_key = "bold"
        elif italic:
            variant_key = "italic"
        else:
            variant_key = None

        # Strategy 1: Look up the filename in FONT_VARIANTS
        filename_lower = p.name.lower()
        variant_file = self.FONT_VARIANTS.get(filename_lower, {}).get(variant_key) if variant_key else None
        if variant_file:
            candidate = parent / variant_file
            if candidate.exists():
                try:
                    return ImageFont.truetype(str(candidate), font_size), False, False
                except Exception:
                    pass

        # Strategy 2: Try common naming patterns in the same directory
        # e.g. replace "Regular"/"-Regular" stem fragment with "Bold" etc.
        if variant_key:
            suffixes_map = {
                "bold": ["Bold", "SemiBold", "DemiBold", "Heavy", "ExtraBold"],
                "italic": ["Italic", "Oblique", "It"],
                "bold_italic": ["BoldItalic", "Bold_Italic", "BdIt", "BoldOblique"],
            }
            for suffix in suffixes_map.get(variant_key, []):
                candidate = parent / f"{suffix}{ext}"
                if candidate.exists():
                    try:
                        return ImageFont.truetype(str(candidate), font_size), False, False
                    except Exception:
                        continue
            # Try replacing style fragment in stem
            for old in ["regular", "bold", "italic", "medium", "light", "thin"]:
                if old in stem_lower:
                    new_stem = stem_lower.replace(old, suffixes_map[variant_key][0].lower())
                    candidate = parent / f"{new_stem}{ext}"
                    if candidate.exists():
                        try:
                            return ImageFont.truetype(str(candidate), font_size), False, False
                        except Exception:
                            continue

        # Strategy 3: Fall back to base font + flag synthetic rendering
        try:
            return ImageFont.truetype(str(p), font_size), bold, italic
        except Exception:
            return None, bold, italic

    @staticmethod
    def _color_to_rgb(color_str: str) -> tuple:
        """Convert a color name or hex string to an (R, G, B) tuple."""
        from PIL import ImageColor
        try:
            return ImageColor.getrgb(color_str)
        except Exception:
            return (255, 255, 255)

    @staticmethod
    def _draw_text_with_style(draw, pos, text, font, fill,
                              needs_synthetic_bold: bool = False,
                              needs_synthetic_italic: bool = False,
                              italic_layer: "Image.Image" = None):
        """Draw text, applying synthetic bold (multi-stroke) and/or italic (affine shear).

        If needs_synthetic_italic is True, *italic_layer* must be a blank RGBA image
        the same size as the target, with its own draw object managed by the caller.
        The caller is responsible for compositing the sheared layer afterward.
        """
        x, y = pos
        if needs_synthetic_bold:
            # Draw text at 4 sub-pixel offsets to thicken strokes
            for dx in (-0.5, 0, 0.5):
                for dy in (-0.5, 0, 0.5):
                    if dx == 0 and dy == 0:
                        draw.text((x + dx, y + dy), text, font=font, fill=fill)
                    else:
                        draw.text((x + dx, y + dy), text, font=font, fill=fill)
        else:
            draw.text((x, y), text, font=font, fill=fill)

    def add_text_overlay(self, image_path: Path, text: str,
                        position: str = "bottom-right",
                        font_size: int = 36,
                        text_color: str = "white",
                        outline_color: str = "black",
                        outline_width: int = 2,
                        font_path: str = None,
                        bold: bool = False,
                        italic: bool = False,
                        underline: bool = False,
                        opacity: int = 100,
                        shadow: bool = False,
                        custom_x: float = None,
                        custom_y: float = None) -> Optional[Path]:
        """
        Add text overlay to an image.
        
        Args:
            image_path: Path to the original image
            text: Text to overlay
            position: Position preset ("top-left", "top-right", etc.) Ignored if custom_x/custom_y are set.
            font_size: Font size in pixels
            text_color: Text color (name or hex)
            outline_color: Outline/stroke color (name or hex)
            outline_width: Outline stroke width
            font_path: Path to a .ttf font file (None = auto-detect default)
            bold: Use bold variant of the font if available
            italic: Use italic variant of the font if available
            underline: Draw underline beneath text
            opacity: Text opacity 0-100 (100 = fully opaque)
            shadow: Add drop shadow behind text
            custom_x: Custom X position as fraction of image width (0.0-1.0)
            custom_y: Custom Y position as fraction of image height (0.0-1.0)
            
        Returns:
            Path to the image with text overlay, or None if failed
        """
        if not text or not text.strip():
            return image_path
        
        try:
            # Load image with PIL and copy the data to avoid file handle issues
            with Image.open(image_path) as img:
                # Convert to RGBA for transparency support
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                # Copy the image data so we can close the file
                img_copy = img.copy()
            
            # Work with the copy, file is now closed
            img = img_copy
            
            # Create a drawing context
            from PIL import ImageDraw, ImageFont
            draw = ImageDraw.Draw(img)
            
            # Load font — resolve bold/italic variants using FONT_VARIANTS map
            font = None
            needs_synthetic_bold = False
            needs_synthetic_italic = False

            if font_path:
                font, needs_synthetic_bold, needs_synthetic_italic = \
                    self._resolve_font_variant(font_path, font_size, bold, italic)

            if font is None:
                # Try to use a common system font
                if bold and italic:
                    fallback_names = ["arialbi.ttf", "DejaVuSans-BoldOblique.ttf",
                                      "LiberationSans-BoldItalic.ttf",
                                      "FreeSansBoldOblique.ttf", "FreeSansBold.ttf"]
                elif bold:
                    fallback_names = ["arialbd.ttf", "DejaVuSans-Bold.ttf",
                                      "LiberationSans-Bold.ttf",
                                      "FreeSansBold.ttf", "FreeSans.ttf"]
                elif italic:
                    fallback_names = ["ariali.ttf", "DejaVuSans-Oblique.ttf",
                                      "LiberationSans-Italic.ttf",
                                      "FreeSansOblique.ttf", "FreeSans.ttf"]
                else:
                    fallback_names = ["arial.ttf", "Arial.ttf",
                                      "DejaVuSans.ttf",
                                      "LiberationSans.ttf",
                                      "FreeSans.ttf"]
                for fn in fallback_names:
                    try:
                        font = ImageFont.truetype(fn, font_size)
                        break
                    except Exception:
                        continue
            if font is None:
                font = ImageFont.load_default()
            
            # Get text bounding box
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            # Calculate position
            img_width, img_height = img.size
            padding = 20

            # Custom position overrides preset
            if custom_x is not None and custom_y is not None:
                x = int(custom_x * img_width - text_width / 2)
                y = int(custom_y * img_height - text_height / 2)
                # Clamp to image bounds
                x = max(0, min(x, img_width - text_width))
                y = max(0, min(y, img_height - text_height))
            elif position == "top-left":
                x = padding
                y = padding
            elif position == "top-right":
                x = img_width - text_width - padding
                y = padding
            elif position == "middle-top":
                x = (img_width - text_width) // 2
                y = padding
            elif position == "middle-bottom":
                x = (img_width - text_width) // 2
                y = img_height - text_height - padding
            elif position == "bottom-left":
                x = padding
                y = img_height - text_height - padding
            elif position == "bottom-right":
                x = img_width - text_width - padding
                y = img_height - text_height - padding
            elif position == "center":
                x = (img_width - text_width) // 2
                y = (img_height - text_height) // 2
            else:
                x = img_width - text_width - padding
                y = img_height - text_height - padding

            # Helper to draw text (with optional synthetic bold)
            def _draw(draw_ctx, pos, fill):
                if needs_synthetic_bold:
                    for dx in (-0.6, 0, 0.6):
                        for dy in (-0.6, 0, 0.6):
                            draw_ctx.text((pos[0] + dx, pos[1] + dy), text, font=font, fill=fill)
                else:
                    draw_ctx.text(pos, text, font=font, fill=fill)

            # If synthetic italic, draw onto a separate layer and shear it
            import math
            if needs_synthetic_italic:
                text_layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
                tl_draw = ImageDraw.Draw(text_layer)
                _txt_rgb = self._color_to_rgb(text_color)
                _ol_rgb = self._color_to_rgb(outline_color)
                # Shadow on italic layer
                if shadow:
                    so = max(2, font_size // 12)
                    _draw(tl_draw, (x + so, y + so), (0, 0, 0, 255))
                # Outline on italic layer
                if outline_width > 0:
                    for ax in range(-outline_width, outline_width + 1):
                        for ay in range(-outline_width, outline_width + 1):
                            if ax != 0 or ay != 0:
                                tl_draw.text((x + ax, y + ay), text, font=font, fill=(*_ol_rgb, 255))
                # Main text on italic layer
                _draw(tl_draw, (x, y), (*_txt_rgb, 255))
                # Underline on italic layer
                if underline:
                    ul_offset = max(2, int(font_size * 0.08))
                    ul_thickness = max(1, int(font_size * 0.05))
                    try:
                        _m = font.getmetrics()
                        ul_y = y + _m[0] + ul_offset
                    except Exception:
                        ul_y = y + text_height + ul_offset
                    tl_draw.line([(x, ul_y), (x + text_width, ul_y)],
                                  fill=(*_txt_rgb, 255), width=ul_thickness)
                # Shear the layer for italic effect
                shear_angle = -12  # degrees
                text_layer = text_layer.transform(
                    img.size, Image.AFFINE,
                    (1, math.tan(math.radians(shear_angle)), 0, 0, 1, 0),
                    resample=Image.BICUBIC
                )
                # Apply opacity if needed
                if opacity < 100:
                    alpha = int(255 * opacity / 100)
                    r, g, b, a = text_layer.split()
                    a = a.point(lambda px: int(px * alpha / 255))
                    text_layer = Image.merge('RGBA', (r, g, b, a))
                img = Image.alpha_composite(img, text_layer)
            elif opacity < 100:
                # Opacity path (no synthetic italic)
                alpha = int(255 * opacity / 100)
                text_layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
                text_draw = ImageDraw.Draw(text_layer)
                if shadow:
                    so = max(2, font_size // 12)
                    _draw(text_draw, (x + so, y + so), (0, 0, 0, alpha))
                if outline_width > 0:
                    _ol_rgb = self._color_to_rgb(outline_color)
                    for ax in range(-outline_width, outline_width + 1):
                        for ay in range(-outline_width, outline_width + 1):
                            if ax != 0 or ay != 0:
                                text_draw.text((x + ax, y + ay), text, font=font, fill=(*_ol_rgb, alpha))
                _txt_rgb = self._color_to_rgb(text_color)
                _draw(text_draw, (x, y), (*_txt_rgb, alpha))
                if underline:
                    ul_offset = max(2, int(font_size * 0.08))
                    ul_thickness = max(1, int(font_size * 0.05))
                    try:
                        _m = font.getmetrics()
                        ul_y = y + _m[0] + ul_offset
                    except Exception:
                        ul_y = y + text_height + ul_offset
                    text_draw.line([(x, ul_y), (x + text_width, ul_y)],
                                    fill=(*_txt_rgb, alpha), width=ul_thickness)
                img = Image.alpha_composite(img, text_layer)
            else:
                # Direct draw path (full opacity, no synthetic italic)
                if shadow:
                    so = max(2, font_size // 12)
                    _draw(draw, (x + so, y + so), "black")
                if outline_width > 0:
                    for ax in range(-outline_width, outline_width + 1):
                        for ay in range(-outline_width, outline_width + 1):
                            if ax != 0 or ay != 0:
                                draw.text((x + ax, y + ay), text, font=font, fill=outline_color)
                _draw(draw, (x, y), text_color)
                if underline:
                    ul_offset = max(2, int(font_size * 0.08))
                    ul_thickness = max(1, int(font_size * 0.05))
                    try:
                        metrics = font.getmetrics()
                        ascent = metrics[0]
                        ul_y = y + ascent + ul_offset
                    except Exception:
                        ul_y = y + text_height + ul_offset
                    draw.line([(x, ul_y), (x + text_width, ul_y)],
                              fill=text_color, width=ul_thickness)
            
            # Convert back to RGB if original wasn't RGBA
            if image_path.suffix.lower() in ['.jpg', '.jpeg']:
                img = img.convert('RGB')
            
            # Generate output filename
            base_name = image_path.stem
            extension = image_path.suffix
            # Sanitize text for filename
            safe_text = "".join(c for c in text if c.isalnum() or c in ('-', '_')).strip()
            if not safe_text:
                safe_text = "text"
            styled_filename = f"{base_name}_text_{safe_text}{extension}"
            styled_path = STYLED_DIR / styled_filename
            
            # If file already exists, add a counter to avoid conflicts
            counter = 1
            while styled_path.exists():
                styled_filename = f"{base_name}_text_{safe_text}_{counter}{extension}"
                styled_path = STYLED_DIR / styled_filename
                counter += 1
            
            # Save to a temp file first to avoid file locking issues
            import tempfile
            temp_dir = Path(tempfile.gettempdir())
            temp_path = temp_dir / f"temp_{styled_filename}"
            
            logging.debug("[style_transfer] Saving to temp file: %s", temp_path)
            img.save(temp_path)
            logging.debug("[style_transfer] Temp file saved successfully")
            
            # Now move to final location
            import shutil
            logging.debug("[style_transfer] Moving to final location: %s", styled_path)
            shutil.move(str(temp_path), str(styled_path))
            logging.debug("[style_transfer] File moved successfully")
            
            return styled_path
            
        except Exception as e:
            logging.error("Error adding text overlay: %s", e)
            import traceback
            traceback.print_exc()
            return None


# Global instance
_style_transfer = None

def get_style_transfer() -> StyleTransfer:
    """Get the global style transfer instance."""
    global _style_transfer
    if _style_transfer is None:
        _style_transfer = StyleTransfer()
    return _style_transfer

def apply_style_to_image(image_path: Path, style: str) -> Optional[Path]:
    """Convenience function to apply style to an image."""
    transfer = get_style_transfer()
    return transfer.apply_style(image_path, style)


def test_all_styles(sample_image_path: Optional[Path] = None) -> dict:
    """
    Test all available styles on a sample image to identify broken filters.
    
    Args:
        sample_image_path: Path to a test image. If None, creates a simple test image.
        
    Returns:
        Dictionary mapping style names to (success: bool, error: str or None)
    """
    import numpy as np
    
    transfer = get_style_transfer()
    results = {}
    
    # Create a simple test image if none provided
    if sample_image_path is None or not sample_image_path.exists():
        test_img = np.zeros((100, 100, 3), dtype=np.uint8)
        test_img[:] = [128, 128, 128]  # Gray image
        test_path = STYLED_DIR / "test_sample.png"
        cv2.imwrite(str(test_path), test_img)
        sample_image_path = test_path
    
    # Test each style (skip "original")
    for style_key in transfer.available_styles.keys():
        if style_key == "original":
            continue
            
        try:
            result = transfer.apply_style(sample_image_path, style_key)
            if result is not None and result.exists():
                results[style_key] = (True, None)
                # Clean up test output
                try:
                    result.unlink()
                except Exception:
                    pass
            else:
                results[style_key] = (False, "Returned None or path does not exist")
        except Exception as e:
            results[style_key] = (False, str(e))
    
    # Clean up sample image if we created it
    if sample_image_path.name == "test_sample.png":
        try:
            sample_image_path.unlink()
        except Exception:
            pass
    
    return results
