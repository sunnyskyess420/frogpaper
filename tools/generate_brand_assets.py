"""Regenerate every FrogPaper logo asset from the master badge.

    python tools/generate_brand_assets.py
    python tools/generate_brand_assets.py --website "D:/path/to/site"   # extra site copy

The master is sidebar_logo.png (1024x1024, transparent outside the circle). One
run rewrites:

  app      FrogPaperLogo.png (tray + window/taskbar), frogpaper.ico (exe,
           shortcuts, installer), FrogPaperLogo.bmp + FrogPaperSmall.bmp
           (installer wizard art), splash.png
  website  favicon.png, favicon-16.png, assets/img/favicon.png,
           assets/img/logo-mark.png, logo.png

Filenames never change, so build scripts (FrogPaper.spec, build_installer.bat)
and the HTML keep working. Sizes are kept from the files they replace.
"""

from __future__ import annotations

import argparse
import io
import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parent.parent
MASTER = REPO_ROOT / "sidebar_logo.png"

# Splash screen palette, sampled from the old splash so the wordmark keeps its look.
SPLASH_BG = (21, 15, 29)
SPLASH_GOLD = (220, 184, 96)
# Light panel behind the installer art.
PANEL_BG = (246, 250, 245)

ICO_SIZES = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
FONT_CANDIDATES = ("segoeuib.ttf", "seguibl.ttf", "arialbd.ttf", "arial.ttf")


def load_master() -> Image.Image:
    """The badge, trimmed to its artwork with a little breathing room."""
    image = Image.open(MASTER).convert("RGBA")
    bbox = image.split()[-1].getbbox()
    if bbox:
        image = image.crop(bbox)
    side = max(image.size)
    pad = int(side * 0.04)
    canvas = Image.new("RGBA", (side + pad * 2, side + pad * 2), (0, 0, 0, 0))
    canvas.paste(image, ((canvas.width - image.width) // 2,
                         (canvas.height - image.height) // 2), image)
    return canvas


def square(master: Image.Image, size: int) -> Image.Image:
    return master.resize((size, size), Image.LANCZOS)


def icon_layer(master: Image.Image, size: int) -> Image.Image:
    """Icon art for one size.

    Below 64px the arced "FrogPaper" lettering collapses into noise, so the
    small taskbar/menu sizes are cropped to the frog itself and masked back into
    a circle, which keeps the badge silhouette readable at 16px.
    """
    if size < 64:
        side = master.width
        crop = int(side * 0.60)
        left = (side - crop) // 2
        top = int(side * 0.18)
        art = master.crop((left, top, left + crop, top + crop))
        mask = Image.new("L", art.size, 0)
        ImageDraw.Draw(mask).ellipse((0, 0, art.width - 1, art.height - 1), fill=255)
        masked = Image.new("RGBA", art.size, (0, 0, 0, 0))
        masked.paste(art, (0, 0), mask)
        art = masked
    else:
        art = master
    return art.resize((size, size), Image.LANCZOS)


def write_ico(path: Path, frames: list[Image.Image]) -> None:
    """Write a multi-size ICO from separate frames (PIL only takes one source)."""
    payloads = []
    for frame in frames:
        buffer = io.BytesIO()
        frame.save(buffer, format="PNG")
        payloads.append(buffer.getvalue())

    with open(path, "wb") as handle:
        handle.write(struct.pack("<HHH", 0, 1, len(frames)))
        offset = 6 + 16 * len(frames)
        for frame, payload in zip(frames, payloads):
            width = 0 if frame.width >= 256 else frame.width
            height = 0 if frame.height >= 256 else frame.height
            handle.write(struct.pack("<BBBBHHII", width, height, 0, 0, 1, 32,
                                     len(payload), offset))
            offset += len(payload)
        for payload in payloads:
            handle.write(payload)


def on_panel(master: Image.Image, size: tuple[int, int], badge: int) -> Image.Image:
    """Badge centred on a flat panel (installer wizard art has no alpha)."""
    panel = Image.new("RGB", size, PANEL_BG)
    art = square(master, badge)
    panel.paste(art, ((size[0] - badge) // 2, (size[1] - badge) // 2), art)
    return panel


def _font(size: int):
    for name in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_splash(master: Image.Image, size=(1376, 768)) -> Image.Image:
    splash = Image.new("RGB", size, SPLASH_BG)
    badge = 500
    art = square(master, badge)
    splash.paste(art, ((size[0] - badge) // 2, int(size[1] * 0.06)), art)

    draw = ImageDraw.Draw(splash)
    text = "FrogPaper"
    font = _font(104)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    draw.text(((size[0] - (right - left)) / 2 - left, int(size[1] * 0.78)),
              text, font=font, fill=SPLASH_GOLD)
    return splash


def write_app_assets(master: Image.Image, root: Path) -> list[str]:
    written = []
    square(master, 256).save(root / "FrogPaperLogo.png")
    written.append("FrogPaperLogo.png")

    frames = [icon_layer(master, size) for size, _ in ICO_SIZES]
    write_ico(root / "frogpaper.ico", frames)
    written.append("frogpaper.ico")

    on_panel(master, (497, 359), 300).save(root / "FrogPaperLogo.bmp")
    written.append("FrogPaperLogo.bmp")

    on_panel(master, (77, 77), 68).save(root / "FrogPaperSmall.bmp")
    written.append("FrogPaperSmall.bmp")

    make_splash(master).save(root / "splash.png")
    written.append("splash.png")
    return written


def write_website_assets(master: Image.Image, site: Path) -> list[str]:
    if not site.exists():
        return []
    written = []
    targets = [
        (site / "assets" / "img" / "favicon.png", 192),
        (site / "favicon.png", 32),
        (site / "favicon-16.png", 16),
        (site / "assets" / "img" / "logo-mark.png", 256),
        (site / "logo.png", 256),
    ]
    for path, size in targets:
        if not path.parent.exists():
            continue
        square(master, size).save(path)
        written.append(str(path.relative_to(site)).replace("\\", "/"))
    return written


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--website", action="append", default=None,
                        help="website folder to update (repeatable)")
    args = parser.parse_args(argv)

    if not MASTER.exists():
        print(f"missing master logo: {MASTER}")
        return 2

    master = load_master()
    print(f"master: {MASTER.name} -> trimmed {master.size[0]}px square")

    for name in write_app_assets(master, REPO_ROOT):
        print(f"  app     {name}")

    sites = args.website or [
        r"C:\Users\alive\OneDrive\Desktop\FP WEB\frogpaper-website-main",
        r"C:\Users\alive\OneDrive\Desktop\FP WEB\frogpaper-website-deploy",
    ]
    for site in sites:
        written = write_website_assets(master, Path(site))
        label = Path(site).name
        if not written:
            print(f"  site    {label}: not found, skipped")
            continue
        for name in written:
            print(f"  site    {label}/{name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
