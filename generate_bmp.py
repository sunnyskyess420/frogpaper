from PIL import Image

BACKGROUND = (255, 255, 255)  # white, matches wizard background

def make_bmp(src_path, out_path, canvas_size, fill_canvas=False):
    src = Image.open(src_path).convert("RGBA")
    if fill_canvas:
        # small image: logo fills the square canvas
        rgb = Image.new("RGB", src.size, BACKGROUND)
        rgb.paste(src, mask=src.split()[3])
        rgb = rgb.resize(canvas_size, Image.LANCZOS)
    else:
        # large image: fit inside canvas, preserve aspect ratio, center on white
        canvas = Image.new("RGB", canvas_size, BACKGROUND)
        sw, sh = src.size
        cw, ch = canvas_size
        scale = min(cw / sw, ch / sh)
        new_w = max(1, int(round(sw * scale)))
        new_h = max(1, int(round(sh * scale)))
        resized = src.resize((new_w, new_h), Image.LANCZOS)
        bg = Image.new("RGB", resized.size, BACKGROUND)
        bg.paste(resized, mask=resized.split()[3]) if resized.mode == "RGBA" else bg.paste(resized)
        x = (cw - new_w) // 2
        y = (ch - new_h) // 2
        canvas.paste(bg, (x, y))
        rgb = canvas
    rgb.save(out_path, format="BMP", bits=24, compression=0)
    print(f"Wrote {out_path}: {rgb.size}, 24-bit BMP")

# Large wizard image — 497x359, fit inside canvas
make_bmp("FrogPaperLogo.png", "FrogPaperLogo.bmp", (497, 359), fill_canvas=False)

# Small wizard image — 77x77, fill canvas
make_bmp("FrogPaperLogo.png", "FrogPaperSmall.bmp", (77, 77), fill_canvas=True)