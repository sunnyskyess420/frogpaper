import ctypes
import random
import sys
from pathlib import Path

from utils import get_app_dir

SPI_SETDESKWALLPAPER = 0x0014
SPIF_FLAGS = 3
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

BASE_DIR = get_app_dir()
MANUAL_DIR = BASE_DIR / "wallpapers" / "manual"
GENERATED_DIR = BASE_DIR / "wallpapers" / "generated"
STYLED_DIR = BASE_DIR / "wallpapers" / "styled"
FAVORITES_DIR = BASE_DIR / "wallpapers" / "favorites"

MANUAL_DIR.mkdir(parents=True, exist_ok=True)
GENERATED_DIR.mkdir(parents=True, exist_ok=True)
STYLED_DIR.mkdir(parents=True, exist_ok=True)
FAVORITES_DIR.mkdir(parents=True, exist_ok=True)


def set_wallpaper(image_path: str | Path) -> bool:
    image_path = Path(image_path).resolve()

    if not image_path.exists():
        print(f"  [X] File not found: {image_path}")
        return False

    if image_path.suffix.lower() not in IMAGE_EXTENSIONS:
        print(f"  [X] Unsupported format: {image_path.suffix}")
        print(f"     Supported: {', '.join(IMAGE_EXTENSIONS)}")
        return False

    result = ctypes.windll.user32.SystemParametersInfoW(
        SPI_SETDESKWALLPAPER,
        0,
        str(image_path),
        SPIF_FLAGS,
    )

    if result:
        print(f"  [OK] Wallpaper set: {image_path.name}")
        return True

    print(f"  [X] Windows API call failed (error code: {ctypes.get_last_error()})")
    return False


def collect_wallpapers(folders: list[Path] = None) -> list[Path]:
    if folders is None:
        folders = [MANUAL_DIR, GENERATED_DIR, STYLED_DIR, FAVORITES_DIR]

    found = []
    for folder in folders:
        if not folder.exists():
            continue
        for ext in IMAGE_EXTENSIONS:
            found.extend(folder.rglob(f"*{ext}"))
            found.extend(folder.rglob(f"*{ext.upper()}"))

    return list(set(found))


def set_random_wallpaper(folders: list[Path] = None) -> bool:
    images = collect_wallpapers(folders)

    if not images:
        print("  [!] No wallpapers found in wallpapers/manual or wallpapers/generated.")
        print("     Save some images there first, then run this again.")
        return False

    chosen = random.choice(images)
    print(f"\n  [*] Randomly picked: {chosen.name}")
    return set_wallpaper(chosen)


def list_wallpapers() -> None:
    images = collect_wallpapers()

    if not images:
        print("  [!] No wallpapers saved yet.")
        return

    print(f"\n  Found {len(images)} wallpaper(s):\n")
    for img in sorted(images):
        print(f"    [{img.parent.name}]  {img.name}")


if __name__ == "__main__":
    if len(sys.argv) == 2:
        set_wallpaper(sys.argv[1])
    else:
        set_random_wallpaper()