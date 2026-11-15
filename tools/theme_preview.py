"""Render a mock FrogPaper window in a theme, for eyeballing a palette.

    python tools/theme_preview.py christmas_light preview.png

No network, no image credits - it paints Tk widgets with the theme's own
colours and grabs the window with Pillow.

Layout mirrors the real app: the sidebar holds the logo, the two generate
buttons and the option fields; the main area holds the preview card.
"""
from __future__ import annotations

import pathlib
import sys
import tkinter as tk

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app_themes import THEMES, THEME_DISPLAY_NAMES, resolve_sidebar_logo  # noqa: E402


def load_logo(theme_key: str, size: int = 132):
    """The theme's sidebar logo, scaled for the mock (None if PIL/asset missing)."""
    try:
        from PIL import Image, ImageTk
        path = resolve_sidebar_logo(theme_key, REPO_ROOT)
        if not path.exists():
            return None
        image = Image.open(path).convert("RGBA").resize((size, size), Image.LANCZOS)
        return ImageTk.PhotoImage(image)
    except Exception:
        return None


def build(root: tk.Tk, theme_key: str) -> tk.Frame:
    pal = THEMES[theme_key]
    bg, panel, panel2 = pal["bg"], pal["panel"], pal["panel2"]
    text, muted, accent = pal["text"], pal["muted"], pal["accent"]
    border, separator = pal["border_color"], pal["separator"]
    secondary_fill = pal.get("secondary_button_bg", panel2)
    secondary_fg = pal.get("secondary_button_fg", text)

    root.configure(bg=bg)
    wrap = tk.Frame(root, bg=bg)
    wrap.pack(fill="both", expand=True)

    # ── sidebar: logo, the two generate buttons, the option fields
    side = tk.Frame(wrap, bg=panel, width=272)
    side.pack(side="left", fill="y")
    side.pack_propagate(False)

    logo_image = load_logo(theme_key)
    if logo_image is not None:
        mark = tk.Label(side, image=logo_image, bg=panel, bd=0)
        mark.image = logo_image  # keep a reference so Tk does not collect it
        mark.pack(pady=(12, 4))
    else:
        tk.Label(side, text="FrogPaper", bg=panel, fg=text,
                 font=("Segoe UI", 13, "bold")).pack(pady=(18, 8))

    buttons = tk.Frame(side, bg=panel)
    buttons.pack(fill="x", padx=12, pady=(4, 10))
    buttons.columnconfigure(0, weight=1)
    buttons.columnconfigure(1, weight=1)
    tk.Label(buttons, text="Generate Prompt", bg=secondary_fill, fg=secondary_fg,
             font=("Segoe UI", 9, "bold"), pady=8).grid(row=0, column=0, sticky="ew", padx=(0, 3))
    tk.Label(buttons, text="Generate Image", bg=accent, fg=pal["primary_button_fg"],
             font=("Segoe UI", 9, "bold"), pady=8).grid(row=0, column=1, sticky="ew", padx=(3, 0))

    for label, value in (("Subject", "frog"), ("Setting", "snowy pine forest"),
                         ("Lighting", "blue hour"), ("Mood", "cozy")):
        tk.Label(side, text=label, bg=panel, fg=muted, anchor="w",
                 font=("Segoe UI", 8)).pack(fill="x", padx=14)
        box = tk.Frame(side, bg=pal["entrybg"], highlightbackground=border,
                       highlightthickness=1)
        box.pack(fill="x", padx=12, pady=(0, 7))
        tk.Label(box, text=value, bg=pal["entrybg"], fg=pal["entryfg"], anchor="w",
                 padx=8, pady=5, font=("Segoe UI", 10)).pack(fill="x")

    tk.Frame(side, bg=separator, height=1).pack(fill="x", padx=12, pady=8)
    tk.Label(side, text="🕘 Recently used", bg=panel, fg=muted, anchor="w",
             font=("Segoe UI", 8, "bold")).pack(fill="x", padx=14)
    for item in ("golden toad", "owl", "cyber frog"):
        tk.Label(side, text=item, bg=panel, fg=pal["tag_fg"], anchor="w",
                 padx=14, pady=2, font=("Segoe UI", 9)).pack(fill="x")

    # ── main area: preview card, progress, tags, status
    main = tk.Frame(wrap, bg=bg)
    main.pack(side="left", fill="both", expand=True)

    head = tk.Frame(main, bg=bg)
    head.pack(fill="x", padx=18, pady=(16, 8))
    tk.Label(head, text=THEME_DISPLAY_NAMES.get(theme_key, theme_key), bg=bg, fg=text,
             font=("Segoe UI", 15, "bold")).pack(side="left")
    tk.Label(head, text="idle", bg=bg, fg=muted,
             font=("Segoe UI", 9)).pack(side="right", pady=(6, 0))

    card = tk.Frame(main, bg=pal["surface"], highlightbackground=border, highlightthickness=1)
    card.pack(fill="both", expand=True, padx=18, pady=(0, 10))

    matte = tk.Frame(card, bg=pal["preview_matte"])
    matte.pack(fill="both", expand=True, padx=10, pady=10)
    tk.Label(matte, text="wallpaper preview", bg=pal["preview_matte"], fg=muted,
             font=("Segoe UI", 10)).pack(expand=True)

    bar = tk.Frame(main, bg=pal["scrollbar_bg"], height=8)
    bar.pack(fill="x", padx=18, pady=(0, 10))
    tk.Frame(bar, bg=pal["progress"], height=8).place(relwidth=0.45, relheight=1)

    chips = tk.Frame(main, bg=bg)
    chips.pack(fill="x", padx=18, pady=(0, 16))
    for word in ("cozy", "winter", "pine"):
        tk.Label(chips, text=word, bg=panel2, fg=pal["tag_fg"], padx=10, pady=4,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))
    tk.Label(chips, text="♥ 12   ★ 4   ⚠ low credits", bg=bg, fg=muted,
             font=("Segoe UI", 9)).pack(side="right")
    return wrap


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    theme_key = argv[0] if argv else "christmas_light"
    out = pathlib.Path(argv[1] if len(argv) > 1 else "theme_preview.png")
    if theme_key not in THEMES:
        print(f"unknown theme {theme_key!r}; pick one of: {', '.join(sorted(THEMES))}")
        return 2

    root = tk.Tk()
    root.title("FrogPaper theme preview")
    root.geometry("980x540+80+80")
    # Stay above other windows: a grab of a covered window captures whatever is
    # in front of it, which is not what we want to save.
    root.attributes("-topmost", True)
    root.lift()
    build(root, theme_key)
    root.update()
    root.after(600, root.quit)
    root.mainloop()

    try:
        from PIL import ImageGrab
        root.update_idletasks()
        x, y = root.winfo_rootx(), root.winfo_rooty()
        w, h = root.winfo_width(), root.winfo_height()
        image = ImageGrab.grab(bbox=(x, y, x + w, y + h))
        image.save(out)
        print(f"wrote {out}")
    except Exception as exc:
        print(f"could not grab the window: {exc}")
        return 1
    finally:
        root.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
