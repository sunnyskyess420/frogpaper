import tkinter as tk

import os

import shutil

import tkinter.font as tkfont
import logging

import ctypes
import ctypes.wintypes

logger = logging.getLogger(__name__)

import threading

import concurrent.futures

import queue

import time

import random

from tkinter import ttk, messagebox, simpledialog

from pathlib import Path

from datetime import datetime









try:

    import pystray

    PYSTRAY_AVAILABLE = True

except ImportError:

    PYSTRAY_AVAILABLE = False

try:
    import sv_ttk
    SV_TTK_AVAILABLE = True
except ImportError:
    SV_TTK_AVAILABLE = False

try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False



from theme_mixer import generate_themes

from prompt_builder import build_all_prompts

from slideshow import SlideshowManager

from keyword_expander import warmup_keyword_expander





from gallery_manager import (

    add_tags_to_image,

    add_tags_to_paths,

    get_tags_for_image,

    remove_tag_from_image,

    get_all_tags,

    get_images_by_tag,

    organize_image_into_folder,

    rename_image,

    get_folder_structure,

    delete_image_and_tags,

    save_prompt_parameters,

    get_prompt_parameters,

)

from preset_manager import (

    load_presets,

    save_bundle_preset,

    get_preset_by_id,

    get_preset_by_name,

    delete_preset,

    export_preset,

    import_preset,

    export_all_presets,

)

from utils import (

    load_json_list,

    save_json_list,

    load_config,

    save_config,

    get_huggingface_token,

    has_huggingface_token,

    get_app_dir,

    seed_bundled_files,

)

seed_bundled_files()

from setup_scheduler import create_task

from session_manager import SessionManager
from tray_manager import TrayManager
from settings_tab import SettingsTab
from prompt_tab import PromptTab
from gallery_tab import GalleryTab

DEFAULT_NEGATIVE_PROMPT = (
    "blurry, low quality, low resolution, pixelated, grainy, noisy, "
    "jpeg artifacts, cropped, bad anatomy, deformed, disfigured"
)



try:

    from set_wallpaper import set_wallpaper, collect_wallpapers

    WINDOWS = True
    
    
    
    
    

except (ImportError, AttributeError):

    WINDOWS = False

    def collect_wallpapers():

        return []

    def set_wallpaper(_path):

        return False



BASE_DIR = get_app_dir()

LOGS_DIR = BASE_DIR / "logs"

PROMPTS_LOG = LOGS_DIR / "prompts_history.json"

FAVORITES_LOG = LOGS_DIR / "favorites.json"

FAVORITES_DIR = BASE_DIR / "wallpapers" / "favorites"
STYLED_DIR = BASE_DIR / "wallpapers" / "styled"
MANUAL_DIR = BASE_DIR / "wallpapers" / "manual"

PRESETS_FILE = LOGS_DIR / "presets.json"

SESSIONS_FILE = LOGS_DIR / "sessions.json"

LOGS_DIR.mkdir(exist_ok=True)

FAVORITES_DIR.mkdir(parents=True, exist_ok=True)
STYLED_DIR.mkdir(parents=True, exist_ok=True)
MANUAL_DIR.mkdir(parents=True, exist_ok=True)

# Migrate old top-level favorites/ folder — runs ONCE then renames source so it never repeats
old_favorites_dir = BASE_DIR / "favorites"
if old_favorites_dir.exists() and old_favorites_dir.is_dir():
    import shutil
    try:
        for file in old_favorites_dir.iterdir():
            if file.is_file() and file.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}:
                dest = FAVORITES_DIR / file.name
                if not dest.exists():  # never overwrite — skip if already present
                    shutil.copy2(file, dest)
        # Rename so this block never runs again
        old_favorites_dir.rename(BASE_DIR / "favorites_migrated")
    except Exception:
        pass  # Ignore migration errors


# ──── Style modes and slideshow sources ──────────────────────────────────

PROMPT_MODE_OPTIONS = [
    ("Stylized", "stylized"),
    ("Realistic", "realistic"),
    ("Cinematic", "cinematic"),
    ("Anime", "anime"),
    ("Dark Fantasy", "dark-fantasy"),
    ("Painterly", "painterly"),
    ("Pixel Art", "pixel-art"),
    ("Minimalist", "minimalist"),
    ("Product Photo", "product-photo"),
    ("Surreal", "surreal"),
]
PROMPT_MODE_LABELS = [label for label, _ in PROMPT_MODE_OPTIONS]
PROMPT_MODE_LABEL_TO_VALUE = {label: value for label, value in PROMPT_MODE_OPTIONS}
PROMPT_MODE_VALUE_TO_LABEL = {value: label for label, value in PROMPT_MODE_OPTIONS}
DEFAULT_PROMPT_MODE_VALUE = PROMPT_MODE_OPTIONS[0][1]
DEFAULT_PROMPT_MODE_LABEL = PROMPT_MODE_OPTIONS[0][0]
STYLE_MODES = [value for _, value in PROMPT_MODE_OPTIONS]

# ──── Color picker constants (shared by UI builder and random_theme) ─────────
# The UI combo includes a leading "" (blank = no selection).
# random_theme excludes "" so a color is always chosen when randomising.
COLOR_FAMILIES = sorted([
    "",
    "gold", "silver", "white", "black",
    "blue", "navy", "cobalt", "sapphire", "indigo", "violet",
    "purple", "lavender", "lilac", "mauve", "periwinkle",
    "red", "crimson", "scarlet", "burgundy", "maroon",
    "pink", "rose", "magenta", "fuchsia", "salmon", "coral",
    "green", "emerald", "jade", "forest green", "lime",
    "mint", "olive", "sage", "teal", "cyan",
    "orange", "amber", "apricot", "bronze",
    "yellow", "golden", "lemon", "mustard",
    "earth", "brown", "tan", "beige", "sand", "ivory",
    "slate", "charcoal", "ash", "stone",
    "rainbow", "holographic", "chrome", "obsidian",
    "midnight", "void", "plasma", "toxic",
])
COLOR_VARIATIONS = sorted([
    "",
    "rich", "deep", "dark", "light", "bright", "vivid",
    "vibrant", "bold", "pale", "faded", "muted", "soft",
    "high contrast", "low contrast",
    "cool", "warm", "icy", "fiery",
    "metallic", "iridescent", "translucent", "fluorescent",
    "glossy", "matte", "satin", "pearlescent", "crystalline",
    "holographic", "opalescent", "frosted", "burnished",
    "pastel", "electric", "neon", "dusty", "sepia", "monochrome",
    "washed out", "oversaturated", "desaturated", "vintage",
    "earthy", "moody", "dreamy", "smoky", "hazy",
])

SLIDESHOW_SOURCES = ["generated", "manual", "all", "favorites", "styled"]

SLIDESHOW_SOURCE_LABELS = {
    "generated": "Generated",
    "manual": "Manual",
    "all": "All Images",
    "favorites": "Favorites",
    "styled": "Styled"
}

SLIDESHOW_SOURCE_DISPLAY = [SLIDESHOW_SOURCE_LABELS[s] for s in SLIDESHOW_SOURCES]

# Reverse mapping for config loading
SLIDESHOW_LABEL_TO_VALUE = {v: k for k, v in SLIDESHOW_SOURCE_LABELS.items()}


# ──── Fullscreen detection (Windows API) ──────────────────────────────────

_user32 = ctypes.windll.user32


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


def _is_foreground_window_fullscreen():
    """Return True if the foreground window covers the entire primary monitor."""
    try:
        hwnd = _user32.GetForegroundWindow()
        if not hwnd:
            return False
        rect = _RECT()
        _user32.GetWindowRect(hwnd, ctypes.byref(rect))
        screen_w = _user32.GetSystemMetrics(0)
        screen_h = _user32.GetSystemMetrics(1)
        win_w = rect.right - rect.left
        win_h = rect.bottom - rect.top
        return (win_w >= screen_w - 4 and win_h >= screen_h - 4)
    except Exception:
        return False


# ──── Provider and model configuration ──────────────────────────────────

PROVIDER_OPTIONS = [
    "Pollinations.ai (Free - No Key)",
    "Cloudflare Workers AI (Free Tier)",
    "Hugging Face Inference",
]

# Maps each provider to its model list (display names) and display→id mapping
PROVIDER_MODELS = {
    "Pollinations.ai (Free - No Key)": {
        "options": [
            "FLUX (Default)",
            "FLUX Realism",
            "FLUX Anime",
            "FLUX 3D",
            "FLUX CablyAI",
            "Turbo (Fast)",
        ],
        "display_to_id": {
            "FLUX (Default)": "flux",
            "FLUX Realism": "flux-realism",
            "FLUX Anime": "flux-anime",
            "FLUX 3D": "flux-3d",
            "FLUX CablyAI": "flux-cablyai",
            "Turbo (Fast)": "turbo",
        },
    },
    "Cloudflare Workers AI (Free Tier)": {
        "options": [
            "FLUX.1-schnell (Fast - Free)",
        ],
        "display_to_id": {
            "FLUX.1-schnell (Fast - Free)": "@cf/black-forest-labs/flux-1-schnell",
        },
    },
    "Hugging Face Inference": {
        "options": [
            "FLUX.1-schnell (Fast - Free)",
            "FLUX.1-dev (Higher Quality - Free Credits)",
            "Custom...",
        ],
        "display_to_id": {
            "FLUX.1-schnell (Fast - Free)": "black-forest-labs/FLUX.1-schnell",
            "FLUX.1-dev (Higher Quality - Free Credits)": "black-forest-labs/FLUX.1-dev",
        },
    },
}

# Backward-compatible flat model list (defaults to HuggingFace)
MODEL_OPTIONS = PROVIDER_MODELS["Hugging Face Inference"]["options"]
MODEL_DISPLAY_TO_ID = PROVIDER_MODELS["Hugging Face Inference"]["display_to_id"]

# Reverse mapping for loading
MODEL_ID_TO_DISPLAY = {v: k for k, v in MODEL_DISPLAY_TO_ID.items()}

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

# Fixed card height used for lazy gallery rendering (thumb 135 + name + tags + padding)
_GALLERY_CARD_H = 195



DIMENSION_PRESETS = {
    "16:9 (1080p)": "1920x1080",
    "Portrait": "1080x1920",
    "Square": "1024x1024",
}



# Shared variable options for Theme Builder and Template Builder
# ── Setting (locations, structures, environments) ─────────────────────────
_BASE_SETTING_OPTIONS = sorted([
    "",
    "swamp",
    "misty pond",
    "rainforest canopy",
    "lily pad marsh",
    "bioluminescent swamp",
    "desert dune",
    "snowy tundra",
    "volcanic lava field",
    "sacred grove",
    "crystal cave",
    "ethereal meadow",
    "bamboo forest",
    "cherry blossom grove",
    "frozen tundra lake",
    "towering redwood forest",
    "hidden waterfall canyon",
    "alpine meadow at sunrise",
    "sea cave with glowing tide pools",
    "mangrove swamp at dusk",
    "sunflower field under storm clouds",
    "giant mushroom forest",
    "salt flat desert at golden hour",
    "lava tube cave",
    "kelp forest underwater",
    "arctic ice shelf",
    "autumn forest path",
    "savanna at sunset",
    "fog-covered mountain ridge",
    "mountain peak",
    "cliff edge",
    "grand canyon",
    "eagle nest on cliff",
    "alpine lake at sunrise",
    "sky above clouds",
    "forest canopy from above",
    "ancient ruins",
    "ancient temple",
    "mystic ruins",
    "wizard tower",
    "forest shrine",
    "floating island",
    "castle on a cliff",
    "enchanted library",
    "dragon's lair",
    "haunted graveyard",
    "fae ring in misty woods",
    "sunken elven city",
    "portal between worlds",
    "giant's throne room",
    "sky fortress above clouds",
    "cursed mirror maze",
    "underground dwarf forge",
    "demon gate at world's edge",
    "celestial observatory",
    "alchemist's tower at midnight",
    "ruins of a sky city",
    "ancient battlefield overgrown",
    "underwater city",
    "spaceship cockpit",
    "steampunk laboratory",
    "martian colony",
    "retro arcade",
    "space station corridor",
    "cyberpunk rooftop",
    "neon street market",
    "alien jungle planet",
    "derelict space hulk",
    "deep space nebula field",
    "orbital ring city",
    "bunker command center",
    "holographic data center",
    "underwater research station",
    "terraforming rig on an ice moon",
    "post-apocalyptic highway",
    "megacity skyline at night",
    "robot assembly bay",
    "time machine chamber",
    "lunar mining outpost",
    "generation ship interior",
    "cozy coffee shop at night",
    "rooftop garden at dusk",
    "foggy back alley",
    "subway station at 3am",
    "jazz club with neon signs",
    "abandoned warehouse",
    "art museum at night",
    "midnight diner",
    "penthouse with city view",
    "underground speakeasy",
    "overgrown shopping mall",
    "gothic cathedral interior",
    "lighthouse on stormy coast",
    "library with spiral staircase",
    "Victorian greenhouse",
    "abandoned amusement park",
    "street market in heavy rain",
    "feudal Japanese village",
    "ancient Roman forum",
    "Viking longhouse by sea",
    "Egyptian pyramid interior",
    "medieval market square",
    "Aztec pyramid at dawn",
    "Silk Road desert caravan",
    "Renaissance workshop",
    "pirate cove at dusk",
    "Ottoman palace courtyard",
    "Greek cliff-side temple",
    "ancient Chinese palace garden",
    "inverted city above clouds",
    "infinite mirrored corridor",
    "dreamscape of floating clocks",
    "world inside a snow globe",
    "chessboard landscape at twilight",
    "coral reef in outer space",
    "library that goes on forever",
    "staircase to nowhere",
    "giant hourglass desert",
    "city made entirely of glass",
    "landscape made of circuit boards",
    "ocean suspended in mid-air",
])

LEGACY_SETTING_OPTIONS = [
    "swamp",
    "ancient ruins",
    "ancient temple",
    "underwater city",
    "wizard tower",
    "neon street market",
    "forest shrine",
    "floating island",
    "spaceship cockpit",
    "steampunk laboratory",
    "martian colony",
    "retro arcade",
    "castle on a cliff",
]

# ── Subject (creatures, characters, hero objects) ───────────────────────────
_BASE_SUBJECT_OPTIONS = [
    "",
    # — Frogs & Amphibians —
    "frog",
    "tree frog",
    "poison dart frog",
    "cyber frog",
    "robot frog",
    "frog samurai",
    "glowing frog",
    "toad",
    "bullfrog",
    "tree toad",
    "horned toad",
    "fire-bellied toad",
    "golden toad",
    "giant toad",
    "cute toad",
    "fantasy toad",
    # — Animals & Creatures —
    "cat",
    "wolf",
    "fox",
    "owl",
    "raven",
    "eagle",
    "tiger",
    "panther",
    "bear",
    "stag",
    "giant spider",
    "peacock",
    "baroque peacock",
    "robot wolf",
    "mechanical horse",
    "neon butterfly",
    "glowing deer",
    "iron golem",
    "crystal serpent",
    "shadow panther",
    # — Human & Humanoid Characters —
    "astronaut",
    "cyber ninja",
    "samurai",
    "witch",
    "alchemist",
    "phantom thief",
    "mech pilot",
    "hero warrior",
    "desert nomad",
    "shadowy sentinel",
    "celestial guardian",
    "star wanderer",
    "time traveler",
    "plague doctor",
    "dark knight",
    "elven archer",
    "voodoo shaman",
    "cyberpunk hacker",
    "space marine",
    "street fighter",
    "rogue assassin",
    "battle mage",
    "pirate captain",
    "bounty hunter",
    "masked vigilante",
    "gothic empress",
    "fire dancer",
    "ice queen",
    "storm caller",
    "void walker",
    "neon geisha",
    "titan warrior",
    "undead king",
    "sun deity",
    "moon goddess",
    # — Machines & Vehicles —
    "racing car",
    "giant mecha",
    "steampunk airship",
    "military tank",
    "motorcycle",
    "fighter jet",
    "space shuttle",
    "submarine",
    "cargo freighter in space",
    "ancient war machine",
    # — Mythical & Fantasy —
    "dragon",
    "forest spirit",
    "bioengineered creature",
    "phoenix",
    "kraken",
    "unicorn",
    "griffon",
    "leviathan",
    "chimera",
    "banshee",
    "demon lord",
    "ancient god",
    "void titan",
    "elder treant",
    "sea serpent",
    "angel of war",
    "forgotten deity",
    # — Abstract & Objects —
    "floating ancient relic",
    "crumbling clocktower",
    "glowing crystal monolith",
    "giant skull throne",
    "living library",
    "mechanical clockwork heart",
    "interdimensional portal",
]

LEGACY_SUBJECT_OPTIONS = [
    "frog",
    "cat",
    "cyber ninja",
    "astronaut",
    "racing car",
    "giant mecha",
    "dragon",
    "samurai",
    "witch",
    "forest spirit",
    "robot wolf",
    "baroque peacock",
    "desert nomad",
    "shadowy sentinel",
    "bioengineered creature",
    "mech pilot",
]

_BASE_STYLE_OPTIONS = sorted([
    "",
    "oil painting",
    "watercolor",
    "cyberpunk neon",
    "vaporwave",
    "pixel art",
    "sketch pencil",
    "gouache",
    "art deco",
    "surreal dali",
    "3D render",
    "anime key",
    "noir b&w",
    "vintage sepia",
    "pop art",
    "impressionist",
    "colored pencil",
    "ink wash",
    "isometric",
    "stained glass",
    "art nouveau",
    "mid-century poster",
    "claymation",
    "stop-motion",
    "hyperrealism",
    "ukiyo-e",
    "concept art",
    "glitch art",
    "bio-luminescent",
    "arctic aurora",
    "sunset savanna",
    "hazy dawn",
    "storm lightning",
    "lantern light",
    "god rays",
    "dramatic chiaroscuro",
    "backlit silhouette",
    "volumetric",
    "studio rim light",
    "candlelight",
    "overcast daylight",
    "unset haze",
])

LEGACY_STYLE_OPTIONS = [
    "cyberpunk",
    "anime key visual",
    "oil painting",
    "watercolor storybook",
    "3D render",
    "synthwave poster",
    "gouache illustration",
    "colored pencil",
    "ink and wash",
    "pixel art 16-bit",
    "isometric vector",
    "stained glass",
    "art nouveau",
    "art deco",
    "noir comic",
    "risograph print",
    "mid-century poster",
    "claymation",
    "stop-motion puppet",
    "surrealism",
    "hyperrealism",
    "ukiyo-e",
    "concept art",
]

_BASE_LIGHTING_OPTIONS = sorted([
    "",
    "golden hour",
    "blue hour",
    "hazy dawn",
    "overcast daylight",
    "dappled forest",
    "midday harsh sun",
    "soft morning fog",
    "sunset savanna",
    "twilight dusk",
    "deep night starlight",
    "diffused cloudy sky",
    "dramatic storm light",
    "desert midday glare",
    "arctic aurora",
    "volcanic firelight",
    "neon",
    "studio rim light",
    "candlelight",
    "lantern light",
    "blacklight",
    "fluorescent buzz",
    "spotlight single beam",
    "neon sign glow",
    "TV screen flicker",
    "fire torchlight",
    "LED strip underglow",
    "bare bulb warmth",
    "cinema projector beam",
    "moonlight",
    "cinematic bloom",
    "god rays",
    "dramatic chiaroscuro",
    "backlit silhouette",
    "volumetric",
    "misty light",
    "soft diffused light",
    "unset haze",
    "high contrast shadow play",
    "fog diffused beam",
    "lens flare",
    "split lighting",
    "rembrandt lighting",
    "butterfly lighting",
    "practical light sources",
    "motivated key light",
    "bioluminescent",
    "arcane glow",
    "plasma energy glow",
    "holographic shimmer",
    "lava glow from below",
    "electric tesla arcs",
    "radioactive green glow",
    "ethereal spirit light",
    "portal energy burst",
    "crystal prism scatter",
    "frozen ice refraction",
    "blood moon red cast",
    "deep sea pressure glow",
])

LEGACY_LIGHTING_OPTIONS = [
    "neon",
    "golden hour",
    "blue hour",
    "moonlight",
    "cinematic bloom",
    "blacklight",
    "misty light",
    "soft diffused light",
    "dramatic chiaroscuro",
    "backlit silhouette",
    "volumetric god rays",
    "studio rim light",
    "candlelight",
    "bioluminescent glow",
    "overcast daylight",
    "sunset haze",
    "storm lightning",
    "lantern light",
    "hazy dawn",
]

_BASE_MOOD_OPTIONS = sorted([
    "",
    "adventurous",
    "whimsical",
    "serene",
    "hopeful",
    "euphoric",
    "triumphant",
    "majestic",
    "playful",
    "romantic",
    "cozy",
    "chill",
    "uplifting",
    "joyful",
    "peaceful",
    "radiant",
    "warm",
    "gentle",
    "dreamy",
    "blissful",
    "dark",
    "epic",
    "ominous",
    "chaotic",
    "mysterious",
    "menacing",
    "foreboding",
    "sinister",
    "apocalyptic",
    "wrathful",
    "brutal",
    "haunting",
    "unsettling",
    "tense",
    "eerie",
    "savage",
    "nostalgic",
    "melancholic",
    "dreamlike",
    "trippy",
    "lonely",
    "mythic",
    "bittersweet",
    "wistful",
    "contemplative",
    "solemn",
    "reverent",
    "vulnerable",
    "raw",
    "numb",
    "resigned",
    "electric",
    "frantic",
    "relentless",
    "hypnotic",
    "pulsing",
    "intense",
    "explosive",
    "wild",
    "feverish",
    "unstoppable",
    "luxurious",
    "zen",
    "bold",
    "ethereal",
    "surreal",
    "cyberpunk edge",
    "lo-fi calm",
    "cottagecore",
    "dark academia",
    "solarpunk optimism",
    "vaporwave nostalgia",
    "gothic elegance",
    "cosmic awe",
])

LEGACY_MOOD_OPTIONS = [
    "epic",
    "chill",
    "mysterious",
    "cozy",
    "nostalgic",
    "trippy",
    "dark",
    "melancholic",
    "dreamlike",
    "majestic",
    "ominous",
    "playful",
    "serene",
    "mythic",
    "eerie",
    "romantic",
    "chaotic",
    "hopeful",
    "lonely",
]

_BASE_ATMOSPHERE_OPTIONS = sorted([
    "",
    "soft atmospheric depth",
    "forest fog",
    "low valley fog",
    "soft dreamy haze",
    "mist",
    "rolling mist",
    "swirling fog",
    "dense fog",
    "morning haze",
    "jungle humidity",
    "mossy wetlands",
    "drifting spores",
    "rain",
    "snow",
    "dust",
    "stardust",
    "embers in air",
    "ash in the air",
    "floating pollen",
    "falling leaves",
    "arcane haze",
    "enchanted mist",
    "haunted fog",
    "sacred smoke",
    "ethereal glow",
    "holographic mist",
    "void haze",
    "glitch particles",
    "luminous vapor",
    "shimmering particles",
    "sandstorm haze",
    "smoke and ash",
    "storm front",
    "eerie mist",
    "sacred glow",
    "storm haze",
    "candlelit warmth",
    "dream haze",
])

LEGACY_ATMOSPHERE_OPTIONS = [
    "forest fog",
    "soft atmospheric depth",
    "soft dreamy haze",
    "holographic mist",
    "embers in air",
    "rain",
    "snow",
    "dust",
    "stardust",
    "low valley fog",
]

def _merge_options(base, extra, sort_key=None):
    """Merge option lists, removing duplicates and sorting alphabetically.
    
    For subject lists, pass sort_key='subject' to keep 'frog' at the top after empty string.
    """
    merged = list(base)
    for option in extra:
        if option not in merged:
            merged.append(option)
    
    # Separate empty string (if present) from sorted items
    has_empty = "" in merged
    non_empty = [opt for opt in merged if opt != ""]
    
    if sort_key == 'subject':
        # Sort alphabetically, but keep 'frog' at the top after empty string
        non_empty_sorted = sorted(non_empty, key=lambda x: (x.lower() != 'frog', x.lower()))
    else:
        # Standard alphabetical sort
        non_empty_sorted = sorted(non_empty, key=str.lower)
    
    # Reconstruct with empty string first if it was present
    if has_empty:
        return [""] + non_empty_sorted
    return non_empty_sorted


THEME_VARIABLE_OPTIONS = {
    "subject": _merge_options(_BASE_SUBJECT_OPTIONS, LEGACY_SUBJECT_OPTIONS, sort_key='subject'),
    "setting": _merge_options(_BASE_SETTING_OPTIONS, LEGACY_SETTING_OPTIONS),
    "style": _merge_options(_BASE_STYLE_OPTIONS, LEGACY_STYLE_OPTIONS),
    "lighting": _merge_options(_BASE_LIGHTING_OPTIONS, LEGACY_LIGHTING_OPTIONS),
    "mood": _merge_options(_BASE_MOOD_OPTIONS, LEGACY_MOOD_OPTIONS),
    "atmosphere": _merge_options(_BASE_ATMOSPHERE_OPTIONS, LEGACY_ATMOSPHERE_OPTIONS),
}

THEMES = {

    # ── Dark Moss / Lily Pad (default) ────────────────────────────────
    "darkforest": {
        "bg":          "#161d14",
        "panel":       "#1e2a1b",
        "panel2":      "#263322",
        "surface":     "#2c3d28",
        "text":        "#d6eacf",
        "muted":       "#7a9b72",
        "entrybg":     "#1a2418",
        "entryfg":     "#cde4c6",
        "tabbg":       "#222e1f",
        "tabsel":      "#3a5c34",
        "accent":      "#5aad78",
        "progress":    "#4a8c62",
        "actions":     ["#2a6644","#358055","#429966","#52b077","#65c48a","#7dd49e"],
        "button_fg":   "#e6f5e0",
        "button_hover":"#4a8c62",
        "scrollbar_bg":"#1e2a1b",
        "scrollbar_fg":"#4a8c62",
        "selected_bg": "#3a5c34",
        "selected_fg": "#f0fff0",
        "border_color":"#334d2f",
        "separator":   "#263322",
        "success_color":"#65c48a",
        "error_color": "#c0392b",
        "warning_color":"#e6a020",
        "tag_fg":      "#7dd49e",
        "heading_font_size": 11, "label_font_weight": "bold",
    },

    # ── Light Mist / Lily ─────────────────────────────────────────────
    "lightforest": {
        "bg":          "#f0f7ec",
        "panel":       "#e0edda",
        "panel2":      "#cfe2c8",
        "surface":     "#f8fcf6",
        "text":        "#1a3318",
        "muted":       "#4d7a47",
        "entrybg":     "#f8fef5",
        "entryfg":     "#1a3318",
        "tabbg":       "#cfe2c8",
        "tabsel":      "#84bb7e",
        "accent":      "#3d8c50",
        "progress":    "#4a9960",
        "actions":     ["#2e7d32","#388e3c","#43a047","#4caf50","#66bb6a","#81c784"],
        "button_fg":   "#0e2210",
        "button_hover":"#2e7d32",
        "button_hover_fg": "#ffffff",
        "scrollbar_bg":"#e0edda",
        "scrollbar_fg":"#4a9960",
        "selected_bg": "#84bb7e",
        "selected_fg": "#0e2210",
        "border_color":"#b0d0a8",
        "separator":   "#cfe2c8",
        "success_color":"#388e3c",
        "error_color": "#c62828",
        "warning_color":"#ef6c00",
        "tag_fg":      "#2e7d32",
        "heading_font_size": 11, "label_font_weight": "bold",
    },

    # ── Frog Neon / Toxic Swamp ──────────────────────────────────
    "darkocean": {
        "bg":          "#060d06",
        "panel":       "#0b160b",
        "panel2":      "#111f11",
        "surface":     "#162816",
        "text":        "#b8f0b0",
        "muted":       "#4db84d",
        "entrybg":     "#090f09",
        "entryfg":     "#a8e8a0",
        "tabbg":       "#0e1a0e",
        "tabsel":      "#1a4a1a",
        "accent":      "#39ff14",
        "progress":    "#28cc10",
        "actions":     ["#0a3d0a","#0f5010","#146614","#1a8018","#22aa20","#2ecc2c"],
        "button_fg":   "#b8f0b0",
        "button_hover":"#28cc10",
        "scrollbar_bg":"#0b160b",
        "scrollbar_fg":"#28cc10",
        "selected_bg": "#1a4a1a",
        "selected_fg": "#d0ffd0",
        "border_color":"#1a3a1a",
        "separator":   "#111f11",
        "success_color":"#39ff14",
        "error_color": "#ff3030",
        "warning_color":"#ffe000",
        "tag_fg":      "#39ff14",
        "heading_font_size": 11, "label_font_weight": "bold",
    },

    # ── Clear Sky ─────────────────────────────────────────────────────
    "lightocean": {
        "bg":          "#eaf4fc",
        "panel":       "#d4eaf8",
        "panel2":      "#bcdcf0",
        "surface":     "#f4faff",
        "text":        "#0c2840",
        "muted":       "#366889",
        "entrybg":     "#f0f9ff",
        "entryfg":     "#0c2840",
        "tabbg":       "#bcdcf0",
        "tabsel":      "#62aacc",
        "accent":      "#1a7eb8",
        "progress":    "#1e88c8",
        "actions":     ["#01579b","#0277bd","#0288d1","#039be5","#29b6f6","#4fc3f7"],
        "button_fg":   "#0c2840",
        "button_hover":"#0277bd",
        "button_hover_fg": "#ffffff",
        "scrollbar_bg":"#d4eaf8",
        "scrollbar_fg":"#1e88c8",
        "selected_bg": "#62aacc",
        "selected_fg": "#ffffff",
        "border_color":"#8cc8e8",
        "separator":   "#bcdcf0",
        "success_color":"#0288d1",
        "error_color": "#c62828",
        "warning_color":"#ef6c00",
        "tag_fg":      "#0277bd",
        "heading_font_size": 11, "label_font_weight": "bold",
    },

    # ── Ember Dark ────────────────────────────────────────────────────
    "darksunset": {
        "bg":          "#1c1108",
        "panel":       "#281808",
        "panel2":      "#362010",
        "surface":     "#3e2814",
        "text":        "#eedcc4",
        "muted":       "#9c6e48",
        "entrybg":     "#201208",
        "entryfg":     "#e4c8a0",
        "tabbg":       "#301a0c",
        "tabsel":      "#6a3610",
        "accent":      "#e07840",
        "progress":    "#c05e28",
        "actions":     ["#bf360c","#d84315","#e64a19","#f4511e","#ff7043","#ff8a65"],
        "button_fg":   "#fff0e0",
        "button_hover":"#c05e28",
        "scrollbar_bg":"#281808",
        "scrollbar_fg":"#c05e28",
        "selected_bg": "#6a3610",
        "selected_fg": "#ffffff",
        "border_color":"#522c0c",
        "separator":   "#362010",
        "success_color":"#ff8a65",
        "error_color": "#b71c1c",
        "warning_color":"#ffd54f",
        "tag_fg":      "#ff8a65",
        "heading_font_size": 11, "label_font_weight": "bold",
    },

    # ── Warm Linen ────────────────────────────────────────────────────
    "lightsunset": {
        "bg":          "#fef8f0",
        "panel":       "#faecd8",
        "panel2":      "#f4dcbc",
        "surface":     "#fffcf8",
        "text":        "#38180a",
        "muted":       "#845830",
        "entrybg":     "#fffaf4",
        "entryfg":     "#38180a",
        "tabbg":       "#f4dcbc",
        "tabsel":      "#f0a060",
        "accent":      "#d86820",
        "progress":    "#d86820",
        "actions":     ["#e65100","#ef6c00","#f57c00","#fb8c00","#ffa726","#ffb74d"],
        "button_fg":   "#38180a",
        "button_hover":"#c05a18",
        "button_hover_fg": "#ffffff",
        "scrollbar_bg":"#faecd8",
        "scrollbar_fg":"#d86820",
        "selected_bg": "#f0a060",
        "selected_fg": "#38180a",
        "border_color":"#f0cca0",
        "separator":   "#f4dcbc",
        "success_color":"#f57c00",
        "error_color": "#c62828",
        "warning_color":"#fdd835",
        "tag_fg":      "#e65100",
        "heading_font_size": 11, "label_font_weight": "bold",
    },

    # ── Pitch Dark ────────────────────────────────────────────────────
    "darkcontrast": {
        "bg":          "#080808",
        "panel":       "#111111",
        "panel2":      "#1c1c1c",
        "surface":     "#242424",
        "text":        "#f0f0f0",
        "muted":       "#aaaaaa",
        "entrybg":     "#0c0c0c",
        "entryfg":     "#f0f0f0",
        "tabbg":       "#1a1a1a",
        "tabsel":      "#404040",
        "accent":      "#90d090",
        "progress":    "#888888",
        "actions":     ["#333333","#444444","#555555","#666666","#777777","#888888"],
        "button_fg":   "#ffffff",
        "button_hover":"#505050",
        "scrollbar_bg":"#111111",
        "scrollbar_fg":"#888888",
        "selected_bg": "#404040",
        "selected_fg": "#ffffff",
        "border_color":"#303030",
        "separator":   "#1c1c1c",
        "success_color":"#aaaaaa",
        "error_color": "#ff4444",
        "warning_color":"#ffcc00",
        "tag_fg":      "#cccccc",
        "heading_font_size": 11, "label_font_weight": "bold",
    },

    # ── Clean White ───────────────────────────────────────────────────
    "lightcontrast": {
        "bg":          "#f8f8f8",
        "panel":       "#eeeeee",
        "panel2":      "#e0e0e0",
        "surface":     "#ffffff",
        "text":        "#111111",
        "muted":       "#555555",
        "entrybg":     "#fdfdfd",
        "entryfg":     "#111111",
        "tabbg":       "#e0e0e0",
        "tabsel":      "#999999",
        "accent":      "#3a8a50",
        "progress":    "#555555",
        "actions":     ["#222222","#333333","#444444","#555555","#666666","#777777"],
        "button_fg":   "#111111",
        "button_hover":"#444444",
        "button_hover_fg": "#ffffff",
        "scrollbar_bg":"#eeeeee",
        "scrollbar_fg":"#555555",
        "selected_bg": "#999999",
        "selected_fg": "#ffffff",
        "border_color":"#cccccc",
        "separator":   "#e0e0e0",
        "success_color":"#333333",
        "error_color": "#cc0000",
        "warning_color":"#cc7700",
        "tag_fg":      "#333333",
        "heading_font_size": 11, "label_font_weight": "bold",
    },

    # ── Neon Cyber ────────────────────────────────────────────────────
    "neoncyber": {
        "bg":          "#08000f",
        "panel":       "#100018",
        "panel2":      "#180028",
        "surface":     "#200035",
        "text":        "#eedeff",
        "muted":       "#8844aa",
        "entrybg":     "#0c0015",
        "entryfg":     "#e0ccff",
        "tabbg":       "#160025",
        "tabsel":      "#6600bb",
        "accent":      "#c040ff",
        "progress":    "#aa00ee",
        "actions":     ["#6600cc","#7700ee","#8800ff","#aa22ff","#cc44ff","#dd66ff"],
        "button_fg":   "#f8d8ff",
        "button_hover":"#9900dd",
        "scrollbar_bg":"#100018",
        "scrollbar_fg":"#aa00ee",
        "selected_bg": "#6600bb",
        "selected_fg": "#ffffff",
        "border_color":"#3a0066",
        "separator":   "#180028",
        "success_color":"#00ffcc",
        "error_color": "#ff0055",
        "warning_color":"#ffee00",
        "tag_fg":      "#dd66ff",
        "heading_font_size": 12, "label_font_weight": "bold",
    },

    # ── Warm Paper ────────────────────────────────────────────────────
    "warmpaper": {
        "bg":          "#f4ede0",
        "panel":       "#ece0cc",
        "panel2":      "#ddd0b8",
        "surface":     "#faf6ee",
        "text":        "#2c1e0e",
        "muted":       "#7a6040",
        "entrybg":     "#faf6ee",
        "entryfg":     "#2c1e0e",
        "tabbg":       "#ddd0b8",
        "tabsel":      "#c0a878",
        "accent":      "#a07040",
        "progress":    "#9c7040",
        "actions":     ["#6d4c41","#795548","#8d6e63","#a1887f","#bcaaa4","#d7ccc8"],
        "button_fg":   "#2c1e0e",
        "button_hover":"#6d4c41",
        "button_hover_fg": "#ffffff",
        "scrollbar_bg":"#ece0cc",
        "scrollbar_fg":"#9c7040",
        "selected_bg": "#c0a878",
        "selected_fg": "#2c1e0e",
        "border_color":"#ccc0a0",
        "separator":   "#ddd0b8",
        "success_color":"#558b2f",
        "error_color": "#b71c1c",
        "warning_color":"#e65100",
        "tag_fg":      "#6d4c41",
        "heading_font_size": 11, "label_font_weight": "normal",
    },

    # ── Studio Neutral ────────────────────────────────────────────────
    "studioneutral": {
        "bg":          "#222222",
        "panel":       "#2c2c2c",
        "panel2":      "#363636",
        "surface":     "#3c3c3c",
        "text":        "#eaeaea",
        "muted":       "#848484",
        "entrybg":     "#282828",
        "entryfg":     "#e0e0e0",
        "tabbg":       "#333333",
        "tabsel":      "#4e4e4e",
        "accent":      "#7abea0",
        "progress":    "#686868",
        "actions":     ["#404040","#4a4a4a","#555555","#606060","#6a6a6a","#757575"],
        "button_fg":   "#f0f0f0",
        "button_hover":"#5a5a5a",
        "scrollbar_bg":"#2c2c2c",
        "scrollbar_fg":"#686868",
        "selected_bg": "#4e4e4e",
        "selected_fg": "#ffffff",
        "border_color":"#444444",
        "separator":   "#363636",
        "success_color":"#80cbc4",
        "error_color": "#ef9a9a",
        "warning_color":"#ffe082",
        "tag_fg":      "#aaaaaa",
        "heading_font_size": 11, "label_font_weight": "normal",
    },

    # ── Dark Glass ────────────────────────────────────────────────────
    "darkglass": {
        "bg":          "#0e1620",
        "panel":       "#162030",
        "panel2":      "#1e2c3e",
        "surface":     "#243446",
        "text":        "#d8eaf8",
        "muted":       "#6080a0",
        "entrybg":     "#121a26",
        "entryfg":     "#c4dcf0",
        "tabbg":       "#1a2636",
        "tabsel":      "#284060",
        "accent":      "#4899cc",
        "progress":    "#386898",
        "actions":     ["#1e3a5f","#24496e","#2c5880","#346898","#4080b0","#5898c8"],
        "button_fg":   "#e4f2ff",
        "button_hover":"#386898",
        "scrollbar_bg":"#162030",
        "scrollbar_fg":"#386898",
        "selected_bg": "#284060",
        "selected_fg": "#ffffff",
        "border_color":"#223344",
        "separator":   "#1e2c3e",
        "success_color":"#5898c8",
        "error_color": "#e05060",
        "warning_color":"#f0b030",
        "tag_fg":      "#80b8e0",
        "heading_font_size": 11, "label_font_weight": "normal",
    },

    # ── Frog Swamp — maximum frog energy ──────────────────────────────────
    "frogswamp": {
        "bg":           "#0a1a08",   # deep swamp black-green
        "panel":        "#0f2610",   # dark lily-pad green
        "panel2":       "#163319",   # slightly lighter swamp
        "surface":      "#1c4020",   # muddy pond surface
        "text":         "#c8f59a",   # poison dart frog chartreuse
        "muted":        "#6abf4b",   # mid frog green
        "entrybg":      "#0c1e0d",   # near-black swamp water
        "entryfg":      "#b8e87a",   # bright leaf green
        "tabbg":        "#122915",   # tab bar swamp
        "tabsel":       "#2d7a1f",   # selected tab — vivid frog belly
        "accent":       "#5dda2a",   # poison dart lime
        "progress":     "#4ab822",   # frog-tongue green
        "actions":      ["#1a5c10","#237a16","#2e9920","#3db82a","#52d035","#6ae845"],
        "button_fg":    "#e8ffd0",   # pale lily pad
        "button_hover": "#3db82a",
        "scrollbar_bg": "#0f2610",
        "scrollbar_fg": "#4ab822",
        "selected_bg":  "#2d7a1f",
        "selected_fg":  "#e8ffd0",
        "border_color": "#1e4d18",   # swamp reed border
        "separator":    "#163319",
        "success_color":"#6ae845",
        "error_color":  "#d94f1e",   # red-eyed treefrog red
        "warning_color":"#f0d020",   # golden poison frog yellow
        "tag_fg":       "#a8f060",   # bright frog-spot green
        "heading_font_size": 11, "label_font_weight": "bold",
    },

}



# ── Layout / spacing constants ─────────────────────────────────────────

UI = {

    "small_pad":       5,   # tight inline spacing (icon-to-label, radio buttons)

    "med_pad":        10,   # standard row/column padding

    "large_pad":      16,   # between control groups

    "section_spacing": 20,  # between LabelFrame sections inside a tab

    "card_pad":         6,  # gallery/favorites card outer margin

    "card_inner":       4,  # gallery/favorites card inner padding

    "button_padx":      4,  # horizontal spacing between action buttons

    "tab_padding":    (16, 9),  # ttk.Notebook tab padding (same as style)

    "heading_font":  ("Segoe UI", 11, "bold"),

    "body_font":     ("Segoe UI", 10),

    "small_font":    ("Segoe UI", 9),

    "mono_font":     ("Consolas", 10),

}



THEME_DISPLAY_NAMES = {

    "darkforest":     "Dark Forest Green",

    "lightforest":    "Light Forest Green",

    "darkocean":      "Frog Neon (dark)",

    "lightocean":     "Ocean Blue (light)",

    "darksunset":     "Sunset Orange (dark)",

    "lightsunset":    "Sunset Orange (light)",

    "darkcontrast":   "High Contrast (dark)",

    "lightcontrast":  "High Contrast (light)",

    "neoncyber":      "Neon Cyber",

    "warmpaper":      "Warm Paper",

    "studioneutral":  "Studio Neutral",

    "darkglass":      "Dark Glass",

    "frogswamp":      "🐸 Frog Swamp",

}



THEME_INTERNAL_NAMES = {v: k for k, v in THEME_DISPLAY_NAMES.items()}



# ── Negative Prompt Builder helpers ──────────────────────────────────

class _TextVarBridge:
    """Shim so that code calling .get()/.delete(0,END)/.insert(0,val) on
    ``negative_prompt_entry`` works with the new Text widget + StringVar.
    """
    def __init__(self, text_widget: tk.Text, string_var: tk.StringVar):
        self._text = text_widget
        self._var = string_var

    def get(self):
        return self._var.get()

    def delete(self, start, end):
        self._text.delete("1.0", tk.END)

    def insert(self, index, value):
        self._text.delete("1.0", tk.END)
        self._text.insert("1.0", value)
        self._var.set(value)


class _FakePresetListbox:
    """Drop-in replacement for the old tk.Listbox so that
    ``apply_negative_prompt_to_prompts`` in prompt_tab.py can still call
    ``.curselection()`` and ``.get(idx)`` without changes.
    """
    def __init__(self, preset_vars: dict, preset_info: list):
        self._vars = preset_vars        # key -> BooleanVar
        self._info = preset_info        # [(key, dname, desc, negs, term_count), ...]

    def curselection(self):
        """Return tuple of indices for checked presets."""
        return tuple(
            i for i, (key, *_) in enumerate(self._info)
            if self._vars[key].get()
        )

    def get(self, idx):
        """Return display name at *idx*."""
        return self._info[idx][1]


class ThemedDialog:
    """Themed replacements for tkinter.messagebox dialogs.

    Usage (inside FrogPaperApp):
        self._dialog.info("Title", "Message")
        self._dialog.warning("Title", "Message")
        self._dialog.error("Title", "Message")
        result = self._dialog.ask("Title", "Question")  # returns True/False
    """

    _ICONS = {
        "info":    "info",
        "warning": "warning",
        "error":   "error",
        "ask":     "ask",
    }

    def __init__(self, app):
        self._app = app
        # Resolve popup sound path once
        self._sound_path = Path(__file__).parent / "sounds" / "frog-croak.mp3"

    def _play_popup_sound(self):
        """Play ribbit sound non-blocking on every popup. Each call gets a unique alias so overlapping popups don't cut each other short."""
        import uuid
        alias = f"popup_snd_{uuid.uuid4().hex[:8]}"
        def _play():
            try:
                import sys
                sp = str(self._sound_path)
                if not self._sound_path.exists():
                    return
                if sys.platform == "win32":
                    import ctypes
                    winmm = ctypes.windll.winmm
                    winmm.mciSendStringW(f'open "{sp}" alias {alias}', None, 0, None)
                    winmm.mciSendStringW(f'play {alias} wait', None, 0, None)
                    winmm.mciSendStringW(f'close {alias}', None, 0, None)
                else:
                    import subprocess
                    player = ("afplay" if sys.platform == "darwin"
                              else "mpv")
                    subprocess.run(
                        [player, "--no-video", sp],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
        try:
            threading.Thread(target=_play, daemon=True).start()
        except Exception:
            pass

    def _pal(self):
        theme = getattr(self._app, "current_theme_name", "darkforest")
        return THEMES.get(theme, THEMES["darkforest"])

    def _show(self, kind: str, title: str, message: str, buttons=("OK",)) -> str:
        self._play_popup_sound()
        pal = self._pal()
        accent = pal.get("accent", pal["progress"])

        dlg = tk.Toplevel(self._app.root)
        dlg.title(title)
        dlg.configure(bg=pal["bg"])
        dlg.resizable(True, True)
        dlg.grab_set()

        # Center over parent
        dlg.update_idletasks()
        pw = self._app.root.winfo_width()
        ph = self._app.root.winfo_height()
        px = self._app.root.winfo_rootx()
        py = self._app.root.winfo_rooty()
        
        # Calculate width based on message length, with min/max bounds
        msg_lines = message.split("\n")
        max_line_length = max(len(line) for line in msg_lines) if msg_lines else 0
        w = min(max(380, max_line_length * 8 + 100), 800)  # Scale with content, cap at 800
        h = 160 + len(msg_lines) * 16
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        dlg.geometry(f"{w}x{h}+{x}+{y}")

        result = tk.StringVar(value=buttons[-1])

        # Icon + message
        top = tk.Frame(dlg, bg=pal["bg"], padx=18, pady=14)
        top.pack(fill="both", expand=True)
        try:
            from icons import get_dialog_icon
            _icon_img = get_dialog_icon(kind, size=28, color=accent)
            icon_lbl = tk.Label(top, image=_icon_img, bg=pal["bg"])
        except Exception:
            icon_lbl = tk.Label(top, text=self._ICONS.get(kind, "info"),
                                font=("Segoe UI", 18, "bold"),
                                bg=pal["bg"], fg=accent)
        icon_lbl.pack(side="left", padx=(0, 12))
        msg_lbl = tk.Label(top, text=message, wraplength=w - 90,
                           justify="left", bg=pal["bg"], fg=pal["text"],
                           font=("Segoe UI", 10))
        msg_lbl.pack(side="left", fill="both", expand=True)

        # Separator
        sep = tk.Frame(dlg, bg=pal.get("border_color", pal["panel2"]), height=1)
        sep.pack(fill="x")

        # Buttons
        btn_row = tk.Frame(dlg, bg=pal["bg"], padx=14, pady=10)
        btn_row.pack(fill="x")

        def make_cmd(val):
            def _cmd():
                result.set(val)
                dlg.grab_release()
                dlg.destroy()
            return _cmd

        for i, label in enumerate(reversed(buttons)):
            is_primary = (i == 0)
            bg = accent if is_primary else pal["panel2"]
            fg = pal["button_fg"]
            btn = tk.Button(
                btn_row, text=label, bg=bg, fg=fg,
                activebackground=pal["button_hover"], activeforeground=fg,
                relief="flat", padx=16, pady=5, cursor="hand2",
                font=("Segoe UI", 9, "bold" if is_primary else "normal"),
                command=make_cmd(label),
            )
            btn.pack(side="right", padx=(6, 0))

        dlg.bind("<Return>", lambda e: make_cmd(buttons[0])())
        dlg.bind("<Escape>", lambda e: make_cmd(buttons[-1])())
        dlg.protocol("WM_DELETE_WINDOW", make_cmd(buttons[-1]))

        self._app.root.wait_window(dlg)
        return result.get()

    def info(self, title: str, message: str):
        self._show("info", title, message, buttons=("OK",))

    def warning(self, title: str, message: str):
        self._show("warning", title, message, buttons=("OK",))

    def error(self, title: str, message: str):
        self._show("error", title, message, buttons=("OK",))

    def ask(self, title: str, message: str) -> bool:
        return self._show("ask", title, message, buttons=("Yes", "No")) == "Yes"



class FrogPaperApp:

    def __init__(self, root):

        self.root = root

        self.template_variable_widgets = {}

        # Initialize SQLite database (migrates existing JSON on first run)
        try:
            import database
            database.init_db()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Database init failed, will use fallback: %s", e)

        self.root.title("FrogPaper")

        self.root.state("zoomed")  # Start maximized (full screen)
        self.root.minsize(1100, 700)

        # Fonts must exist before build_ui() because multiple tabs use them
        # during widget construction, including the Templates tab.
        default_font = tkfont.nametofont("TkDefaultFont")
        text_font = tkfont.nametofont("TkTextFont")
        fixed_font = tkfont.nametofont("TkFixedFont")

        self.basefont = default_font.copy()
        self.basefont.configure(size=10)

        self.smallfont = default_font.copy()
        self.smallfont.configure(size=9)

        self.tinyfont = default_font.copy()
        self.tinyfont.configure(size=8)

        self.boldfont = default_font.copy()
        self.boldfont.configure(size=10, weight="bold")

        self.uiheadingfont = default_font.copy()
        self.uiheadingfont.configure(size=11, weight="bold")

        self.small_font = self.smallfont  # alias for gallery_tab compatibility

        self.titlefont = default_font.copy()
        self.titlefont.configure(size=14, weight="bold")

        self.monospacefont = fixed_font.copy()
        self.monospacefont.configure(size=9)

        self.textfont = text_font.copy()
        self.textfont.configure(size=10)

        self.themes = []
        self.prompts = []
        self.current_prompt_data = None  # Single active preview prompt
        self.favorites = []
        self.presets = []
        self.last_image_path = None
        self.last_image_tk = None
        self.preview_source_label = None
        self.is_generating = False
        self.slideshow_interval_var = tk.StringVar(value='60')
        self.slideshow_source_var = tk.StringVar(value='All Images')
        self.slideshow_order_var = tk.StringVar(value='random')
        self.slideshow_enabled_var = tk.BooleanVar(value=False)
        self.slideshow_skip_duplicates_var = tk.BooleanVar(value=True)
        self.slideshow_pause_on_fullscreen_var = tk.BooleanVar(value=False)
        self._fullscreen_was_detected = False
        self._fullscreen_check_job = None
        self.gallery_images = []
        self.gallery_paths = []
        self.selected_gallery_path = None  # Primary selection for preview/wallpaper
        self.selected_gallery_paths = set()  # Multi-selection for batch operations
        self.favorite_thumb_refs = []
        self.prompt_source = "theme_builder"  # Track whether prompt came from theme_builder or recipe
        self.prompt_builder_quick_refs = None
        self.favorite_selected_item = None

        # Style transfer (OpenCV) is loaded on first use — avoids slow startup import.
        self.style_transfer = None
        self.style_transfer_available = False
        self._style_transfer_lazy_failed = False

        # Performance Fixes: Threading & Cancellation
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        self.cancel_event = threading.Event()
        self.thumb_cache = {}  # Cache for PhotoImage objects
        self.gen_future = None

        self.current_theme_name = "darkforest"
        self._tray_icon = None
        self._tray_thread = None
        self.gallery_cards = {}
        self.favorite_cards = {}
        self.remember_settings_var = tk.BooleanVar(value=False)
        self.custom_width_var = tk.StringVar(value="1024")
        self.custom_height_var = tk.StringVar(value="576")
        config = load_config()
        self.auto_generate_on_startup_var = tk.BooleanVar(
            value=config.get("auto_generate_on_startup", False))
        self.startup_subject_var = tk.StringVar(
            value=config.get("startup_subject", "frog"))

        # Initialize status variables early for slideshow
        self.statusvar = tk.StringVar(value="Ready.")
        self.status_var = self.statusvar

        # Slideshow tracking
        self.slideshow = SlideshowManager(self.root, self.status_var)

        # Gallery State (Initialize before build_ui)
        self.gallery_sort_mode = "date"  # "date" or "name"
        self.gallery_sort_desc = True
        self.gallery_organize_mode = tk.BooleanVar(value=False)
        self._gallery_custom_order = None  # List[Path] — persists manual order across reloads
        self._fav_custom_order = None       # List[str] image-paths — persists favorites manual order
        self._fav_drag_source = None        # int card-position index being dragged
        self._fav_display_items = []        # the exact list last rendered by _populate_visual_grid
        self._gallery_resize_job = None       # pending after() id for debounced resize handler
        self._gallery_layout_job = None      # pending after_idle id for deferred column layout
        self._gallery_scroll_job = None      # pending after() id for debounced scroll render
        self._gallery_cols = 3               # current column count, updated by layout passes
        self._gallery_placeholders = {}      # idx -> placeholder Frame for off-screen slots
        self.is_fullscreen = False

        # Themed dialog helper (replaces messagebox)
        self._dialog = ThemedDialog(self)

        # Toast notification system
        self._toast_frame = None
        self._toast_queue = []
        self._toast_timer = None

        # Minimize to tray setting
        self.minimize_to_tray_enabled = load_config().get("minimize_to_tray", True)

        # Run on startup setting (read actual registry state as source of truth)
        self.run_on_startup_enabled = self._get_startup_registry()

        _t0 = time.perf_counter()

        # Expose module-level constants as instance attributes for extracted modules
        self.THEMES = THEMES
        self.UI = UI
        self.THEME_DISPLAY_NAMES = THEME_DISPLAY_NAMES
        self.THEME_INTERNAL_NAMES = THEME_INTERNAL_NAMES
        self.COLOR_FAMILIES = COLOR_FAMILIES
        self.COLOR_VARIATIONS = COLOR_VARIATIONS
        self.THEME_VARIABLE_OPTIONS = THEME_VARIABLE_OPTIONS
        self.STYLE_MODES = STYLE_MODES
        self.MODEL_OPTIONS = MODEL_OPTIONS
        self.MODEL_ID_TO_DISPLAY = MODEL_ID_TO_DISPLAY
        self.MODEL_DISPLAY_TO_ID = MODEL_DISPLAY_TO_ID
        self.PROVIDER_OPTIONS = PROVIDER_OPTIONS
        self.PROVIDER_MODELS = PROVIDER_MODELS
        self.DIMENSION_PRESETS = DIMENSION_PRESETS
        self.SLIDESHOW_LABEL_TO_VALUE = SLIDESHOW_LABEL_TO_VALUE
        self.SLIDESHOW_SOURCE_DISPLAY = SLIDESHOW_SOURCE_DISPLAY
        self.SLIDESHOW_SOURCE_LABELS = SLIDESHOW_SOURCE_LABELS
        self.DEFAULT_NEGATIVE_PROMPT = DEFAULT_NEGATIVE_PROMPT
        self.DEFAULT_PROMPT_MODE_LABEL = DEFAULT_PROMPT_MODE_LABEL
        self.DEFAULT_PROMPT_MODE_VALUE = DEFAULT_PROMPT_MODE_VALUE
        self.PROMPT_MODE_LABELS = PROMPT_MODE_LABELS
        self.IMAGE_EXTS = IMAGE_EXTS
        self._GALLERY_CARD_H = _GALLERY_CARD_H
        self.BASE_DIR = BASE_DIR
        self.LOGS_DIR = LOGS_DIR
        self.PROMPTS_LOG = PROMPTS_LOG
        self.FAVORITES_LOG = FAVORITES_LOG
        self.FAVORITES_DIR = FAVORITES_DIR
        self.STYLED_DIR = STYLED_DIR
        self.MANUAL_DIR = MANUAL_DIR
        self.PRESETS_FILE = PRESETS_FILE
        self.SESSIONS_FILE = SESSIONS_FILE
        self.WINDOWS = WINDOWS
        self.PYSTRAY_AVAILABLE = PYSTRAY_AVAILABLE
        self.SV_TTK_AVAILABLE = SV_TTK_AVAILABLE
        self.KEYBOARD_AVAILABLE = KEYBOARD_AVAILABLE

        # Initialize extracted module managers
        self._session_mgr = SessionManager(self)
        self._settings_tab = SettingsTab(self)
        self._prompt_tab = PromptTab(self)
        self._gallery_tab = GalleryTab(self)
        self._tray_mgr = TrayManager(self)

        # Set window / taskbar icon using the shared icon loader
        # (must come AFTER _tray_mgr is created)
        try:
            from PIL import ImageTk
            self.icon_img = ImageTk.PhotoImage(self._get_app_icon_image())
            self.root.iconphoto(True, self.icon_img)
        except Exception:
            pass

        self.build_ui()
        logger.info(f"build_ui: {time.perf_counter()-_t0:.2f}s")

        _t1 = time.perf_counter()
        self.load_favorites()
        logger.info(f"load_favorites: {time.perf_counter()-_t1:.2f}s")

        _t2 = time.perf_counter()
        self.load_presets()
        self.load_slideshow_settings()
        self.load_remembered_settings()
        logger.info(f"config/presets/settings: {time.perf_counter()-_t2:.2f}s")

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.bind("<Unmap>", self._on_minimize)
        self.root.bind("<F11>", self.toggle_fullscreen)

        # Keyboard shortcuts for common actions
        self.root.bind("<Control-g>", lambda e: self._switch_to_tab("gallery"))
        self.root.bind("<Control-s>", lambda e: self._open_settings_window())
        self.root.bind("<Control-p>", lambda e: self._switch_to_tab("prompt_builder"))
        self.root.bind("<Control-n>", lambda e: self.generate_image())
        self.root.bind("<Escape>", lambda e: self._handle_escape())

        # Global Hotkey (Ctrl+Alt+N for next wallpaper)
        if KEYBOARD_AVAILABLE:
            try:
                keyboard.add_hotkey('ctrl+alt+n', self.advance_slideshow)
            except:
                pass

        _t3 = time.perf_counter()
        self.apply_theme(load_config().get("app_theme", "darkforest"))
        logger.info(f"apply_theme: {time.perf_counter()-_t3:.2f}s")
        logger.info(f"total sync init: {time.perf_counter()-_t0:.2f}s")

        self.status_var.set("Loading gallery…")
        self.root.after(1, self._deferred_startup_load)

        # Start tray icon on initialization so it's available when window closes
        if PYSTRAY_AVAILABLE:
            self._start_tray()

        # Show window normally on startup
        self.root.deiconify()
        self.root.state("normal")



    def _ensure_style_transfer(self):

        """Load OpenCV/style_transfer only when needed (first Apply Style open)."""

        if self.style_transfer is not None:

            return True

        if self._style_transfer_lazy_failed:

            return False

        try:

            from style_transfer import get_style_transfer



            self.style_transfer = get_style_transfer()

            self.style_transfer_available = True

            return True

        except Exception:

            self._style_transfer_lazy_failed = True

            self.style_transfer_available = False

            self.style_transfer = None

            return False





    def _deferred_startup_load(self):
        """Run all heavy disk I/O on a background thread; deliver results to main thread."""

        def _bg_work():
            _t = time.perf_counter()
            # 0. Skip keyword warmup to prevent system freezes
            # The keyword expander will lazy-load on first use instead
            logger.info(f"keyword warmup skipped (lazy-load enabled): {time.perf_counter()-_t:.2f}s")

            # 1. migrate saved image paths (rglob scan — was blocking main thread)
            try:
                updated_h, updated_f = self.migrate_saved_image_paths()
            except Exception:
                updated_h = updated_f = 0
            logger.info(f"migrate_saved_image_paths: {time.perf_counter()-_t:.2f}s")

            # 2. collect + sort gallery file list (rglob over 4 folders)
            _t2 = time.perf_counter()
            try:
                raw_images = collect_wallpapers() or []
                current_sort = getattr(self, '_startup_sort', 'Date Newest')
                if current_sort in ("Date Newest", "Date Oldest"):
                    images_with_stats = [(img, img.stat().st_mtime) for img in raw_images]
                    images_with_stats.sort(key=lambda x: x[1], reverse=(current_sort == "Date Newest"))
                    raw_images = [x[0] for x in images_with_stats]
                elif current_sort == "Name A-Z":
                    raw_images.sort(key=lambda x: x.name.lower())
                elif current_sort == "Name Z-A":
                    raw_images.sort(key=lambda x: x.name.lower(), reverse=True)
                elif current_sort == "Size Largest":
                    try:
                        images_with_size = [(img, os.path.getsize(img)) for img in raw_images]
                        images_with_size.sort(key=lambda x: x[1], reverse=True)
                        raw_images = [x[0] for x in images_with_size]
                    except OSError:
                        raw_images.sort(key=lambda x: x.name.lower())
            except Exception:
                raw_images = []
            logger.info(f"collect+sort wallpapers ({len(raw_images)} files): {time.perf_counter()-_t2:.2f}s")

            # Deliver results back on the main thread
            self.root.after(0, lambda: _main_thread_finish(raw_images, updated_f))

        def _main_thread_finish(raw_images, updated_f):
            _t = time.perf_counter()
            if updated_f:
                self.load_favorites()
            # Apply custom order if set
            if self._gallery_custom_order is not None:
                order_strs = [str(p) for p in self._gallery_custom_order]
                ordered = {str(p): p for p in raw_images}
                raw_images2 = [ordered[s] for s in order_strs if s in ordered]
                raw_images2 += [p for p in ordered.values() if str(p) not in order_strs]
                raw_images[:] = raw_images2
            self.gallery_images = raw_images
            self.slideshow.load_gallery(self.gallery_images)
            # Trigger the UI-only part of load_gallery (clear old cards + build placeholders)
            self.load_gallery()
            logger.info(f"gallery UI populate: {time.perf_counter()-_t:.2f}s")
            # Skip theme generation warmup to prevent system freezes
            # Theme generation will lazy-load on first use instead
            self.status_var.set("Ready.")

        # Cache the current sort choice before leaving the main thread
        self._startup_sort = getattr(self, 'sort_combo_var', None)
        self._startup_sort = self._startup_sort.get() if self._startup_sort else 'Date Newest'

        threading.Thread(target=_bg_work, daemon=True).start()

    def _warmup_theme_generation(self):
        """Pre-warm theme generation on background thread (cold-start perf fix)."""
        def warmup_thread():
            try:
                warmup_start = time.perf_counter()
                warmup_keyword_expander()
                keywords = ["frog"]
                start = time.perf_counter()
                themes = generate_themes(count=1, user_keywords=keywords)
                elapsed = time.perf_counter() - start
                warmup_total = time.perf_counter() - warmup_start
                logger.debug(f"Theme generation warmup complete: {warmup_total:.2f}s (theme gen: {elapsed:.2f}s)")
                self.root.after(0, lambda: self.status_var.set("Ready — prompt engine warm."))
            except Exception as e:
                logger.debug(f"Warmup error: {e}")
                self.root.after(0, lambda: self.status_var.set("Ready."))
        thread = threading.Thread(target=warmup_thread, daemon=True)
        thread.start()



    def get_cursor_color(self):

        """Get a cursor color that contrasts with the current theme background."""

        try:

            pal = THEMES.get(self.current_theme_name, THEMES["darkforest"])

            bg_color = pal["bg"]

            

            # Determine if background is dark or light

            if bg_color in ["#0f1711", "#16231a", "#1c2d22", "#0a1929", "#132f4c", "#1e3a5f", "#1a0f0f", "#2d1b1b", "#3d2828", "#000000", "#1a1a1a", "#2d2d2d"]:

                # Dark background - use

                #  light cursor

                return "#ffffff"  # White cursor for dark themes

            else:

                # Light background - use dark cursor

                return "#000000"  # Black cursor for light themes

        except Exception:

            return "#000000"  # Fallback to black



    def _update_all_entry_cursors(self):

        """Update cursor colors for all entry widgets when theme changes."""

        try:

            cursor_color = self.get_cursor_color()

            

            # Update all known entry widgets

            entry_widgets = [

                getattr(self, 'subject_entry', None),

                getattr(self, 'style_entry', None),

                getattr(self, 'lighting_entry', None),

                getattr(self, 'mood_entry', None),

                getattr(self, 'color_entry', None),

                getattr(self, 'negative_prompt_entry', None),

                getattr(self, 'token_entry', None),

                getattr(self, 'custom_width_entry', None),

                getattr(self, 'custom_height_entry', None),

                getattr(self, 'custom_model_entry', None),

                getattr(self, 'from_word_entry', None),

                getattr(self, 'to_word_entry', None),

            ]

            

            for entry in entry_widgets:

                if entry and hasattr(entry, 'configure'):

                    try:

                        # Check if it's a regular Entry widget (not Combobox)

                        if 'Entry' in str(type(entry)):

                            entry.configure(insertcolor=cursor_color, insertwidth=3)

                        # Combobox widgets get cursor styling from theme

                    except Exception:

                        pass

        except Exception:

            pass



    def configure_entry_cursor(self, entry_widget):

        """Configure entry widget with enhanced cursor visibility."""

        try:

            cursor_color = self.get_cursor_color()

            

            # Check if it's a regular Entry widget (not Combobox)

            if hasattr(entry_widget, 'configure') and 'Entry' in str(type(entry_widget)):

                # Regular Entry widget supports insertcolor

                entry_widget.configure(insertcolor=cursor_color, insertwidth=3)

            elif hasattr(entry_widget, 'configure') and 'Combobox' in str(type(entry_widget)):

                # Combobox widgets have different cursor handling

                # The cursor will inherit from the theme styling

                pass

        except Exception:

            # Fallback - do nothing for unsupported widgets

            pass



    def on_theme_changed(self, event=None):

        display_name = self.theme_var.get()

        internal_name = THEME_INTERNAL_NAMES.get(display_name, "darkforest")

        self.apply_theme(internal_name)

        self.status_var.set(f"Theme switched to {display_name}")



    def _lighten_color(self, hex_color, percent):
        """Lighten a hex color by a percentage."""
        try:
            hex_color = hex_color.lstrip('#')
            r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            r = min(255, int(r + (255 - r) * percent / 100))
            g = min(255, int(g + (255 - g) * percent / 100))
            b = min(255, int(b + (255 - b) * percent / 100))
            return f"#{r:02x}{g:02x}{b:02x}"
        except:
            return hex_color

    def _darken_color(self, hex_color, percent):
        """Darken a hex color by a percentage."""
        try:
            hex_color = hex_color.lstrip('#')
            r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            r = max(0, int(r * (100 - percent) / 100))
            g = max(0, int(g * (100 - percent) / 100))
            b = max(0, int(b * (100 - percent) / 100))
            return f"#{r:02x}{g:02x}{b:02x}"
        except:
            return hex_color

    def _apply_sidebar_icons(self, accent):
        """Apply rendered icons to sidebar, header, and prompt tab buttons."""
        pass  # Icons disabled — text-only buttons

    def _retheme_child_widgets(self, parent, pal):
        """Recursively re-theme all tk.Frame/tk.Label children of a parent widget."""
        try:
            for child in parent.winfo_children():
                try:
                    if isinstance(child, tk.Frame):
                        child.configure(bg=pal["panel"])
                        # Recurse into frame children
                        self._retheme_child_widgets(child, pal)
                    elif isinstance(child, tk.Label):
                        # Determine foreground: use muted color for labels
                        # that appear to be info/meta text (short text, no selection)
                        try:
                            font_info = child.cget("font")
                            is_small = font_info and ("small" in str(font_info) or
                                                      str(font_info).endswith("8") or
                                                      "tiny" in str(font_info))
                        except Exception:
                            is_small = False
                        fg = pal["muted"] if is_small else pal["text"]
                        child.configure(bg=pal["panel"], fg=fg)
                    elif isinstance(child, tk.Canvas):
                        child.configure(bg=pal["panel"], highlightthickness=0)
                except tk.TclError:
                    pass  # Widget already destroyed
        except tk.TclError:
            pass  # Parent already destroyed

    def _retheme_gallery_widgets(self, pal):
        """Re-theme all gallery view card widgets after a theme change."""
        border = pal.get("border_color", pal["panel2"])

        # Main gallery cards + placeholders
        if hasattr(self, "gallery_inner") and self.gallery_inner.winfo_exists():
            self._retheme_child_widgets(self.gallery_inner, pal)
            # Update card highlight borders
            for key, (card, name_lbl, tags_lbl) in list(self.gallery_cards.items()):
                try:
                    if card.winfo_exists():
                        card.configure(highlightbackground=border)
                except tk.TclError:
                    pass
            # Update placeholder backgrounds
            for idx, ph in list(self._gallery_placeholders.items()):
                try:
                    if ph.winfo_exists():
                        ph.configure(bg=pal["panel2"])
                except tk.TclError:
                    pass

        # Favorites inner
        if hasattr(self, "gallery_fav_inner") and self.gallery_fav_inner.winfo_exists():
            self._retheme_child_widgets(self.gallery_fav_inner, pal)

        # Styled inner
        if hasattr(self, "gallery_styled_inner") and self.gallery_styled_inner.winfo_exists():
            self._retheme_child_widgets(self.gallery_styled_inner, pal)

        # Manual inner
        if hasattr(self, "gallery_manual_inner") and self.gallery_manual_inner.winfo_exists():
            self._retheme_child_widgets(self.gallery_manual_inner, pal)

    def apply_theme(self, theme_name):
        if theme_name not in THEMES:
            theme_name = "darkforest"

        self.current_theme_name = theme_name
        pal = THEMES.get(self.current_theme_name, THEMES["darkforest"])

        self.root.configure(bg=pal["bg"])
        style = ttk.Style(self.root)

        _LIGHT_THEMES = {"lightforest", "lightocean", "lightsunset", "lightcontrast", "warmpaper"}
        if SV_TTK_AVAILABLE:
            sv_mode = "light" if theme_name in _LIGHT_THEMES else "dark"
            sv_ttk.set_theme(sv_mode, self.root)
        else:
            try:
                style.theme_use("clam")
            except Exception:
                pass

        accent = pal.get("accent", pal["progress"])
        border = pal.get("border_color", pal["panel2"])
        surface = pal.get("surface", pal["panel2"])

        style.configure(".",
            background=pal["bg"],
            foreground=pal["text"],
            fieldbackground=pal["entrybg"],
            relief="flat",
            borderwidth=0,
        )
        style.configure("TFrame", background=pal["bg"])
        style.configure("Inner.TFrame", background=pal["bg"])
        style.configure("Surface.TFrame", background=surface)
        style.configure("Card.TFrame", background=pal["panel"], relief="flat", borderwidth=0)

        style.configure("TLabelframe",
            background=pal["bg"],
            foreground=pal["text"],
            relief="flat",
            borderwidth=0,
        )
        style.configure("TLabelframe.Label",
            background=pal["bg"],
            foreground=accent,
            font=("Segoe UI", 10, "bold"),
            padding=(2, 2),
        )

        style.configure("TLabel", background=pal["bg"], foreground=pal["text"])
        style.configure("Muted.TLabel", background=pal["bg"], foreground=pal["muted"])

        style.configure("TButton",
            background=pal["panel2"],
            foreground=pal["button_fg"],
            relief="flat",
            borderwidth=0,
            padding=(8, 5),
            focusthickness=1,
            focuscolor=accent,
        )
        style.map("TButton",
            background=[("active", pal["button_hover"]), ("pressed", pal["tabsel"])],
            foreground=[("active", pal.get("button_hover_fg", pal["button_fg"]))],
            relief=[("active", "flat"), ("pressed", "flat")],
        )

        style.configure("Accent.TButton",
            background=accent,
            foreground=pal["button_fg"],
            relief="flat",
            borderwidth=0,
            padding=(8, 5),
        )
        style.map("Accent.TButton",
            background=[("active", self._lighten_color(accent, 20)), ("pressed", self._darken_color(accent, 20))],
        )

        style.configure("Active.TButton",
            background=pal["progress"],
            foreground=pal["button_fg"],
            relief="flat",
            borderwidth=0,
            padding=(8, 5),
        )
        style.map("Active.TButton",
            background=[("active", self._lighten_color(pal["progress"], 20)), ("pressed", self._darken_color(pal["progress"], 20))],
        )

        style.configure("TEntry",
            fieldbackground=pal["entrybg"],
            foreground=pal["entryfg"],
            insertcolor=pal["text"],
            insertwidth=2,
            relief="flat",
            borderwidth=1,
            bordercolor=border,
            padding=(4, 3),
        )
        style.map("TEntry",
            fieldbackground=[("focus", surface)],
            bordercolor=[("focus", accent)],
        )

        style.configure("TCombobox",
            fieldbackground=pal["entrybg"],
            foreground=pal["entryfg"],
            selectbackground=pal["tabsel"],
            selectforeground=pal["text"],
            relief="flat",
            borderwidth=1,
            padding=(4, 3),
        )
        style.map("TCombobox",
            fieldbackground=[("readonly", pal["entrybg"])],
            foreground=[("readonly", pal["entryfg"])],
            selectbackground=[("readonly", pal["tabsel"])],
        )

        style.configure("TCheckbutton",
            background=pal["bg"],
            foreground=pal["text"],
            indicatorcolor=pal["entrybg"],
            indicatorrelief="flat",
        )
        style.map("TCheckbutton",
            background=[("active", pal["bg"])],
            indicatorcolor=[("selected", accent)],
        )

        style.configure("TRadiobutton",
            background=pal["bg"],
            foreground=pal["text"],
            indicatorcolor=pal["entrybg"],
        )
        style.map("TRadiobutton",
            background=[("active", pal["bg"])],
            indicatorcolor=[("selected", accent)],
        )

        style.configure("TNotebook",
            background=pal["bg"],
            borderwidth=0,
            relief="flat",
        )
        style.configure("TNotebook.Tab",
            background=pal["tabbg"],
            foreground=pal["muted"],
            padding=(16, 9),
            relief="flat",
            borderwidth=0,
        )
        style.map("TNotebook.Tab",
            background=[("selected", pal["panel"]), ("active", pal["panel2"])],
            foreground=[("selected", pal["text"]), ("active", pal["text"])],
        )

        style.configure("Horizontal.TProgressbar",
            background=accent,
            troughcolor=pal["panel2"],
            borderwidth=0,
            relief="flat",
            thickness=14,
        )
        style.configure("Vertical.TProgressbar",
            background=accent,
            troughcolor=pal["panel2"],
            borderwidth=0,
            relief="flat",
        )

        # ── TSpinbox (rounded, consistent with TEntry) ──
        style.configure("TSpinbox",
            fieldbackground=pal["entrybg"],
            foreground=pal["entryfg"],
            insertcolor=pal["text"],
            insertwidth=2,
            relief="flat",
            borderwidth=1,
            bordercolor=border,
            padding=(4, 3),
            arrowcolor=pal["muted"],
        )
        style.map("TSpinbox",
            fieldbackground=[("focus", surface)],
            bordercolor=[("focus", accent)],
            arrowcolor=[("active", accent)],
        )

        # ── TScale (sliders) ──
        style.configure("TScale",
            background=pal["bg"],
            troughcolor=pal["panel2"],
            borderwidth=0,
            sliderlength=18,
        )
        style.map("TScale",
            background=[("active", pal["bg"])],
        )

        # ── Enhanced TButton padding for icon+text compound buttons ──
        style.configure("Icon.TButton",
            background=pal["panel2"],
            foreground=pal["button_fg"],
            relief="flat",
            borderwidth=0,
            padding=(6, 5, 10, 5),  # extra right padding when icon is present
            focusthickness=1,
            focuscolor=accent,
        )
        style.map("Icon.TButton",
            background=[("active", pal["button_hover"]), ("pressed", pal["tabsel"])],
            foreground=[("active", pal.get("button_hover_fg", pal["button_fg"]))],
        )

        # ── Separator spacing ──
        style.configure("Spacy.TSeparator",
            background=border,
            padding=(0, 6),
        )

        # ── Treeview (if used anywhere) ──
        style.configure("Treeview",
            background=pal["entrybg"],
            foreground=pal["entryfg"],
            fieldbackground=pal["entrybg"],
            borderwidth=0,
            rowheight=26,
        )
        style.map("Treeview",
            background=[("selected", pal["tabsel"])],
            foreground=[("selected", pal["text"])],
        )
        style.configure("Treeview.Heading",
            background=pal["panel2"],
            foreground=pal["text"],
            font=("Segoe UI", 9, "bold"),
            padding=(8, 4),
        )

        style.configure("Vertical.TScrollbar",
            background=pal["scrollbar_fg"],
            troughcolor=pal["panel2"],
            borderwidth=0,
            relief="flat",
            arrowsize=12,
        )
        style.configure("Horizontal.TScrollbar",
            background=pal["scrollbar_fg"],
            troughcolor=pal["panel2"],
            borderwidth=0,
            relief="flat",
            arrowsize=12,
        )
        style.map("Vertical.TScrollbar",
            background=[("active", accent)],
        )
        style.map("Horizontal.TScrollbar",
            background=[("active", accent)],
        )

        style.configure("TSeparator", background=border)

        self._update_all_entry_cursors()

        if hasattr(self, "prompttext"):
            self.prompttext.configure(
                bg=pal["entrybg"],
                fg=pal["entryfg"],
                insertbackground=pal["text"],
                selectbackground=pal["tabsel"],
                selectforeground=pal["text"],
            )
        elif hasattr(self, "prompt_text"):
            self.prompt_text.configure(
                bg=pal["entrybg"],
                fg=pal["entryfg"],
                insertbackground=pal["text"],
                selectbackground=pal["tabsel"],
                selectforeground=pal["text"],
            )

        canvas_bg = pal["bg"]
        accent = pal.get("accent", pal["progress"])

        if hasattr(self, "gallery_canvas"):
            self.gallery_canvas.configure(bg=canvas_bg, highlightthickness=0)
        if hasattr(self, "gallery_inner"):
            self.gallery_inner.configure(style="Inner.TFrame")
        if hasattr(self, "settings_canvas"):
            self.settings_canvas.configure(bg=canvas_bg, highlightthickness=0)
        if hasattr(self, "settings_inner"):
            self.settings_inner.configure(style="Inner.TFrame")
        if hasattr(self, "prompt_builder_canvas"):
            self.prompt_builder_canvas.configure(bg=canvas_bg, highlightthickness=0)
        if hasattr(self, "templatecanvas"):
            self.templatecanvas.configure(bg=pal["bg"], highlightthickness=0)
        if hasattr(self, "gallery_fav_canvas"):
            self.gallery_fav_canvas.configure(bg=canvas_bg, highlightthickness=0)
        if hasattr(self, "gallery_fav_inner"):
            self.gallery_fav_inner.configure(style="Inner.TFrame")
        if hasattr(self, "gallery_styled_canvas"):
            self.gallery_styled_canvas.configure(bg=canvas_bg, highlightthickness=0)
        if hasattr(self, "gallery_styled_inner"):
            self.gallery_styled_inner.configure(style="Inner.TFrame")
        if hasattr(self, "gallery_manual_canvas"):
            self.gallery_manual_canvas.configure(bg=canvas_bg, highlightthickness=0)
        if hasattr(self, "gallery_manual_inner"):
            self.gallery_manual_inner.configure(style="Inner.TFrame")

        # Re-theme all gallery card widgets (cards, placeholders, labels)
        self._retheme_gallery_widgets(pal)

        # Clear icon cache so icons re-render in new accent colour
        try:
            from icons import clear_cache
            clear_cache()
        except Exception:
            pass

        # Apply toolbar icons (rendered via PIL) after theme colours are set
        if hasattr(self, '_gallery_tab'):
            try:
                self._gallery_tab._apply_toolbar_icons()
            except Exception:
                pass

        # Apply sidebar and action icons
        self._apply_sidebar_icons(accent)

        if hasattr(self, "image_label"):
            self.image_label.configure(bg=pal["panel"], fg=pal["muted"],
                                       highlightthickness=0)
        if hasattr(self, "preview_details_frame"):
            self.preview_details_frame.configure(style="Inner.TFrame")
        if hasattr(self, "progress_overlay_label"):
            self.progress_overlay_label.configure(bg=accent, fg=pal["button_fg"])

        if hasattr(self, "templatevarscrollcanvas"):
            self.templatevarscrollcanvas.configure(bg=pal["panel"], highlightthickness=0)
        if hasattr(self, "templatevarrows"):
            pass

        if hasattr(self, "templatevarrows"):
            for child in self.templatevarrows.winfo_children():
                try:
                    if isinstance(child, tk.Frame):
                        child.configure(bg=pal["panel"])
                    elif isinstance(child, tk.Label):
                        child.configure(bg=pal["panel"], fg=pal["text"])
                except Exception:
                    pass

                try:
                    for grandchild in child.winfo_children():
                        if isinstance(grandchild, tk.Frame):
                            grandchild.configure(bg=pal["panel"])
                        elif isinstance(grandchild, tk.Label):
                            grandchild.configure(bg=pal["panel"], fg=pal["text"])
                        elif isinstance(grandchild, tk.Entry):
                            grandchild.configure(
                                bg=pal["entrybg"],
                                fg=pal["entryfg"],
                                insertbackground=pal["text"],
                                relief="flat",
                            )
                        elif isinstance(grandchild, tk.Text):
                            grandchild.configure(
                                bg=pal["entrybg"],
                                fg=pal["entryfg"],
                                insertbackground=pal["text"],
                                relief="flat",
                            )
                except Exception:
                    pass

        if hasattr(self, "themelist"):
            self.themelist.configure(
                bg=pal["entrybg"],
                fg=pal["entryfg"],
                selectbackground=pal["tabsel"],
                selectforeground=pal["text"],
            )

        # Theme the new sidebar elements (tk.Frame / tk.Label widgets)
        if hasattr(self, "_sidebar_outer"):
            self._sidebar_outer.configure(bg=pal["panel"])
        if hasattr(self, "_sidebar_canvas"):
            self._sidebar_canvas.configure(bg=pal["panel"])
        if hasattr(self, "_sidebar"):
            self._sidebar.configure(bg=pal["panel"])
        for attr in ("title_label",
                      "_sidebar_mode_lbl",
                      "_sidebar_lighting_lbl", "_sidebar_color_lbl",
                      "_sidebar_subj_lbl", "_sidebar_setting_lbl",
                      "_sidebar_atm_lbl",
                      "_sidebar_neg_lbl"):
            w = getattr(self, attr, None)
            if w and isinstance(w, tk.Label):
                w.configure(bg=pal["panel"], fg=pal["text"])
        if hasattr(self, "_generate_btn"):
            self._generate_btn.configure(
                bg=accent, fg=pal["button_fg"],
                activebackground=pal["button_hover"],
                activeforeground=pal.get("button_hover_fg", pal["button_fg"]),
            )
        if hasattr(self, "_generate_prompt_btn"):
            self._generate_prompt_btn.configure(
                bg=accent, fg=pal["button_fg"],
                activebackground=pal["button_hover"],
                activeforeground=pal.get("button_hover_fg", pal["button_fg"]),
            )

        config = load_config()
        config["app_theme"] = theme_name
        save_config(config)



    def activate_generator_tab(self, event=None):
        """Select the Prompt Builder tab (Generator merged into it)."""
        try:
            self.notebook.select(self.prompt_builder_tab)
        except Exception:
            pass

    def activate_prompt_builder_tab(self, event=None):

        try:

            self.notebook.select(self.prompt_builder_tab)

        except Exception:

            pass



    def build_ui(self):

        style = ttk.Style(self.root)

        style.theme_use("clam")

        self.base_font = tkfont.nametofont("TkDefaultFont")
        self.base_font.configure(family="Segoe UI", size=9)
        self.bold_font = tkfont.Font(family="Segoe UI", size=9, weight="bold")
        self.small_font = tkfont.Font(family="Segoe UI", size=8)
        self.title_font = tkfont.Font(family="Segoe UI", size=18, weight="bold")
        self.sidebar_title_font = tkfont.Font(family="Segoe UI", size=14, weight="bold")
        self.mono_font = tkfont.Font(family="Consolas", size=9)
        self.emoji_font = tkfont.Font(family="Segoe UI Emoji", size=11)

        self.main = ttk.Frame(self.root, padding=0)
        self.main.pack(fill="both", expand=True)

        # ── Three-column layout ──────────────────────────────────────────────
        self.main.columnconfigure(0, weight=0, minsize=300)  # left sidebar
        self.main.columnconfigure(1, weight=3)                # center preview
        self.main.columnconfigure(2, weight=2, minsize=280)  # right gallery
        self.main.rowconfigure(0, weight=1)

        # ═══════════════════════ LEFT SIDEBAR ═══════════════════════════════
        sidebar_outer = tk.Frame(self.main)
        sidebar_outer.grid(row=0, column=0, sticky="nsew")
        sidebar_outer.rowconfigure(0, weight=1)
        sidebar_outer.columnconfigure(0, weight=1)
        self._sidebar_outer = sidebar_outer

        sidebar_canvas = tk.Canvas(sidebar_outer, highlightthickness=0, width=300)
        sidebar_scroll = ttk.Scrollbar(sidebar_outer, orient="vertical", command=sidebar_canvas.yview)
        sidebar_canvas.configure(yscrollcommand=sidebar_scroll.set)
        sidebar_canvas.grid(row=0, column=0, sticky="nsew")
        sidebar_scroll.grid(row=0, column=1, sticky="ns")
        self._sidebar_canvas = sidebar_canvas

        left = tk.Frame(sidebar_canvas, padx=14, pady=14)
        _sb_win = sidebar_canvas.create_window((0, 0), window=left, anchor="nw")
        left.bind("<Configure>", lambda e: sidebar_canvas.configure(scrollregion=sidebar_canvas.bbox("all")))
        sidebar_canvas.bind("<Configure>", lambda e: sidebar_canvas.itemconfigure(_sb_win, width=e.width))
        left.columnconfigure(0, weight=1)
        self._sidebar = left

        # Sidebar mousewheel scrolling
        def _sidebar_wheel(event):
            sidebar_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"
        sidebar_canvas.bind("<MouseWheel>", _sidebar_wheel)
        left.bind("<MouseWheel>", _sidebar_wheel)
        self._sidebar_wheel = _sidebar_wheel  # store for binding children later

        def _bind_sidebar_wheel_recursive(widget):
            """Bind mousewheel to all children of the sidebar so scrolling works everywhere."""
            try:
                widget.bind("<MouseWheel>", _sidebar_wheel)
                for child in widget.winfo_children():
                    _bind_sidebar_wheel_recursive(child)
            except Exception:
                pass
        self._bind_sidebar_wheel_recursive = _bind_sidebar_wheel_recursive

        # ── Primary actions: Generate Prompt + Generate Image ──
        gen_row = ttk.Frame(left)
        gen_row.pack(fill="x", pady=(0, 4))
        gen_row.columnconfigure(0, weight=1)
        gen_row.columnconfigure(1, weight=1)

        gen_prompt_btn = tk.Button(gen_row, text="Generate Prompt", cursor="hand2",
                                   relief="flat", bd=0, padx=10, pady=8,
                                   command=self.generate_prompt_only)
        gen_prompt_btn.configure(font=tkfont.Font(family="Segoe UI", size=10, weight="bold"))
        gen_prompt_btn.grid(row=0, column=0, sticky="ew", padx=(0, 3), ipady=3)
        self._generate_prompt_btn = gen_prompt_btn

        gen_img_btn = tk.Button(gen_row, text="Generate Image", cursor="hand2",
                                relief="flat", bd=0, padx=10, pady=8,
                                command=self.generate)
        gen_img_btn.configure(font=tkfont.Font(family="Segoe UI", size=10, weight="bold"))
        gen_img_btn.grid(row=0, column=1, sticky="ew", padx=(3, 0), ipady=3)
        self._generate_btn = gen_img_btn

        # ── Utility bar: Random · Cancel / Settings ──
        util_bar = ttk.Frame(left)
        util_bar.pack(fill="x", pady=(4, 6))
        util_bar.columnconfigure(0, weight=1)
        util_bar.columnconfigure(1, weight=1)
        self._btn_random = ttk.Button(util_bar, text=" Random",
                   command=self.random_theme)
        self._btn_random.grid(row=0, column=0, sticky="ew", padx=(0, 3))
        self._btn_cancel = ttk.Button(util_bar, text=" Cancel",
                   command=self.cancel_generation)
        self._btn_cancel.grid(row=0, column=1, sticky="ew")
        self._btn_settings = ttk.Button(util_bar, text=" Settings",
                   command=self._open_settings_window)
        self._btn_settings.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(3, 0))

        ttk.Separator(left, orient="horizontal").pack(fill="x", pady=(2, 10))

        # Subject
        subj_lbl = tk.Label(left, text="Subject", anchor="w")
        subj_lbl.configure(font=self.bold_font)
        subj_lbl.pack(fill="x", pady=(0, 2))
        self._sidebar_subj_lbl = subj_lbl
        self.subject_entry = ttk.Combobox(left, values=THEME_VARIABLE_OPTIONS["subject"])
        self.subject_entry.pack(fill="x", pady=(0, 10))
        self.subject_entry.insert(0, "frog")
        self.subject_entry.bind("<MouseWheel>", lambda e: "break")

        # Mode dropdown
        mode_lbl = tk.Label(left, text="Mode", anchor="w")
        mode_lbl.configure(font=self.bold_font)
        mode_lbl.pack(fill="x", pady=(0, 2))
        self._sidebar_mode_lbl = mode_lbl

        self.mode_var = tk.StringVar(value=DEFAULT_PROMPT_MODE_LABEL)
        mode_combo = ttk.Combobox(left, textvariable=self.mode_var,
                                  values=PROMPT_MODE_LABELS, state="readonly")
        mode_combo.pack(fill="x", pady=(0, 10))
        mode_combo.bind("<<ComboboxSelected>>", lambda e: self.update_mode_badge())
        mode_combo.bind("<MouseWheel>", lambda e: "break")
        self.mode_combo = mode_combo

        # Lighting dropdown
        lighting_lbl = tk.Label(left, text="Lighting", anchor="w")
        lighting_lbl.configure(font=self.bold_font)
        lighting_lbl.pack(fill="x", pady=(0, 2))
        self._sidebar_lighting_lbl = lighting_lbl

        self.lighting_entry = ttk.Combobox(left, values=THEME_VARIABLE_OPTIONS["lighting"])
        self.lighting_entry.pack(fill="x", pady=(0, 10))
        self.lighting_entry.insert(0, "neon")
        self.lighting_entry.bind("<MouseWheel>", lambda e: "break")

        # Color palette row
        color_lbl = tk.Label(left, text="Color Palette", anchor="w")
        color_lbl.configure(font=self.bold_font)
        color_lbl.pack(fill="x", pady=(0, 4))
        self._sidebar_color_lbl = color_lbl

        color_frame = ttk.Frame(left)
        color_frame.pack(fill="x", pady=(0, 14))
        # Use random defaults for color to avoid empty on startup
        color_families = [f for f in COLOR_FAMILIES if f]
        color_variations = COLOR_VARIATIONS
        default_family = random.choice(color_families) if color_families else ""
        default_variation = random.choice(color_variations) if color_variations else ""
        self.color_family_var = tk.StringVar(value=default_family)
        self.color_family_combo = ttk.Combobox(color_frame, textvariable=self.color_family_var,
                                               values=COLOR_FAMILIES, state="readonly", width=14)
        self.color_family_combo.pack(side="left", padx=(0, 6))
        self.color_family_combo.bind("<MouseWheel>", lambda e: "break")
        self.color_variation_var = tk.StringVar(value=default_variation)
        self.color_variation_combo = ttk.Combobox(color_frame, textvariable=self.color_variation_var,
                                                  values=COLOR_VARIATIONS, state="readonly", width=14)
        self.color_variation_combo.pack(side="left")
        self.color_variation_combo.bind("<MouseWheel>", lambda e: "break")

        # Setting (location/environment)
        setting_lbl = tk.Label(left, text="Setting", anchor="w")
        setting_lbl.configure(font=self.bold_font)
        setting_lbl.pack(fill="x", pady=(0, 2))
        self._sidebar_setting_lbl = setting_lbl
        self.setting_entry = ttk.Combobox(left, values=THEME_VARIABLE_OPTIONS["setting"])
        self.setting_entry.pack(fill="x", pady=(0, 10))
        first_setting = [opt for opt in THEME_VARIABLE_OPTIONS["setting"] if opt]
        if first_setting:
            self.setting_entry.insert(0, first_setting[0])
        self.setting_entry.bind("<MouseWheel>", lambda e: "break")

        # Atmosphere
        atm_lbl = tk.Label(left, text="Atmosphere", anchor="w")
        atm_lbl.configure(font=self.bold_font)
        atm_lbl.pack(fill="x", pady=(0, 2))
        self._sidebar_atm_lbl = atm_lbl
        first_atmosphere = [opt for opt in THEME_VARIABLE_OPTIONS.get("atmosphere", []) if opt]
        # Use a random default instead of first alphabetically to avoid always showing "arcane haze"
        default_atm = random.choice(first_atmosphere) if first_atmosphere else ""
        self.atmosphere_var = tk.StringVar(value=default_atm)
        self.atmosphere_combo = ttk.Combobox(left, textvariable=self.atmosphere_var,
                                             values=THEME_VARIABLE_OPTIONS.get("atmosphere", [""]),
                                             state="readonly")
        self.atmosphere_combo.pack(fill="x", pady=(0, 10))
        self.atmosphere_combo.bind("<MouseWheel>", lambda e: "break")

        # ── Negative Prompt Builder (unified) ──
        from negative_manager import load_negative_presets, get_preset_negatives
        neg_builder_lbl = tk.Label(left, text="Negative Prompt", anchor="w")
        neg_builder_lbl.configure(font=self.bold_font)
        neg_builder_lbl.pack(fill="x", pady=(0, 4))
        self._sidebar_neg_preset_lbl = neg_builder_lbl
        self._sidebar_neg_lbl = neg_builder_lbl

        _presets_data = load_negative_presets().get("presets", {})
        # Store ordered list of (key, name, description, negatives_text, term_count)
        self._neg_preset_info = []
        self._neg_preset_vars = {}  # key -> BooleanVar
        for key, val in _presets_data.items():
            if key == "none":
                continue
            dname = val.get("name", key)
            desc = val.get("description", "")
            negs = val.get("negatives", "")
            term_count = len([t for t in negs.split(",") if t.strip()])
            self._neg_preset_info.append((key, dname, desc, negs, term_count))
            self._neg_preset_vars[key] = tk.BooleanVar(value=False)
        # Keep _neg_preset_key_map for backward compat (display_name -> key)
        self._neg_preset_key_map = {info[1]: info[0] for info in self._neg_preset_info}

        # Preset checkbuttons — compact rows with term counts
        preset_frame = ttk.Frame(left)
        preset_frame.pack(fill="x", pady=(0, 4))
        self._neg_preset_frame = preset_frame
        for idx, (key, dname, desc, negs, term_count) in enumerate(self._neg_preset_info):
            row_frame = ttk.Frame(preset_frame)
            row_frame.pack(fill="x", pady=(0, 1))
            cb = ttk.Checkbutton(row_frame, text=dname, variable=self._neg_preset_vars[key],
                                  command=self._rebuild_neg_combined)
            cb.pack(side="left")
            count_lbl = tk.Label(row_frame, text=f"({term_count})", fg="gray", anchor="e")
            count_lbl.configure(font=self.small_font)
            count_lbl.pack(side="right", padx=(0, 2))

        # Preset description (updates on checkbox hover)
        self._neg_preset_desc_var = tk.StringVar(value="")
        self._neg_preset_desc_lbl = tk.Label(left, textvariable=self._neg_preset_desc_var,
                                              anchor="w", wraplength=240, fg="gray")
        self._neg_preset_desc_lbl.pack(fill="x", pady=(0, 2))
        # Bind hover on each checkbutton to show description
        for key, dname, desc, negs, term_count in self._neg_preset_info:
            for child in self._neg_preset_frame.winfo_children():
                for sub in child.winfo_children():
                    if isinstance(sub, ttk.Checkbutton) and sub.cget("text") == dname:
                        sub.bind("<Enter>", lambda e, d=desc: self._neg_preset_desc_var.set(d))
                        sub.bind("<Leave>", lambda e: self._neg_preset_desc_var.set(""))
                        break

        # Custom terms — single-line entry with label
        custom_lbl = tk.Label(left, text="Custom terms (comma-separated):", anchor="w")
        custom_lbl.configure(font=self.small_font)
        custom_lbl.pack(fill="x", pady=(0, 1))
        self._neg_custom_var = tk.StringVar(value="")
        self._neg_custom_entry = ttk.Entry(left, textvariable=self._neg_custom_var)
        self._neg_custom_entry.pack(fill="x", pady=(0, 4))
        self._neg_custom_entry.bind("<KeyRelease>", lambda e: self._rebuild_neg_combined())

        # Preview — live-merged presets + custom (edits mark it as manual)
        preview_lbl = tk.Label(left, text="Preview", anchor="w")
        preview_lbl.configure(font=self.small_font)
        preview_lbl.pack(fill="x", pady=(0, 1))
        self._neg_final_frame = ttk.Frame(left)
        self._neg_final_frame.pack(fill="x", pady=(0, 1))
        self._neg_final_text = tk.Text(self._neg_final_frame, height=3, wrap="word",
                                        font=self.mono_font, bd=1, relief="solid")
        self._neg_final_text.pack(fill="x")
        self._neg_final_text.bind("<KeyRelease>", self._on_neg_final_edited)

        # Small note about what this preview shows
        preview_note = tk.Label(left, anchor="w", wraplength=240, fg="gray",
                              text="Additional negatives may be added at generation time.")
        preview_note.configure(font=self.small_font)
        preview_note.pack(fill="x", pady=(0, 1))

        # Term count + reset row
        self._neg_term_count_var = tk.StringVar(value="0 terms")
        count_row = ttk.Frame(left)
        count_row.pack(fill="x", pady=(0, 6))
        tk.Label(count_row, textvariable=self._neg_term_count_var, anchor="w",
                 fg="gray").pack(side="left")
        self._neg_reset_btn = ttk.Button(count_row, text="Reset", width=6,
                                          command=self._reset_neg_combined)
        self._neg_reset_btn.pack(side="right")

        # negative_prompt_var still exists for backward compat — reflects the final combined text
        self.negative_prompt_var = tk.StringVar(value=DEFAULT_NEGATIVE_PROMPT)
        # negative_prompt_entry kept as alias for _neg_final_text (for _set_active_entry compat)
        self.negative_prompt_entry = _TextVarBridge(self._neg_final_text, self.negative_prompt_var)

        # Track whether user has manually edited the final text
        self._neg_manual_edit = False
        # Backward compat: keep _neg_preset_listbox interface (returns selected keys)
        self._neg_preset_listbox = _FakePresetListbox(self._neg_preset_vars, self._neg_preset_info)

        # Seed the initial combined prompt
        self._rebuild_neg_combined()

        # ── Secondary toggles (stored here; UI lives in Settings > Advanced) ──
        self.smart_neg_var = tk.BooleanVar(value=True)
        self.subject_lock_var = tk.BooleanVar(value=True)

        # Bind mousewheel to all sidebar children
        self._bind_sidebar_wheel_recursive(left)

        # ═══════════════════════ CENTER PANEL ═══════════════════════════════
        center = ttk.Frame(self.main, padding=(8, 8))
        center.grid(row=0, column=1, sticky="nsew")
        center.rowconfigure(1, weight=1)
        center.columnconfigure(0, weight=1)
        self._center_panel = center

        # Quick actions on center tab bar
        center_tabs = ttk.Frame(center)
        center_tabs.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        # Apply Style menubutton — same styles as gallery, applied to current preview
        self._center_style_btn = ttk.Menubutton(center_tabs, text=" Apply Style")
        self._center_style_menu = tk.Menu(self._center_style_btn, tearoff=0)
        for display_name, style_key in [
            ("Vivid Enhance", "edge_enhance"), ("Monochrome BW", "bw"),
            ("Vintage Warm", "vintage"), ("Color Pop", "posterize"),
            ("Oil Painting", "oil_painting"), ("Watercolor", "watercolor"),
            ("Cyberpunk Neon", "cyberpunk_neon"), ("Vaporwave", "vaporwave"),
            ("Pixel Art", "pixel_art"), ("Sketch Pencil", "sketch_pencil"),
            ("Gouache", "gouache"), ("Art Deco", "art_deco"),
            ("Surreal Dali", "surreal_dali"), ("3D Render", "3d_render"),
            ("Anime Key", "anime_key"), ("Noir BW", "noir_bw"),
            ("Vintage Sepia", "vintage_sepia"), ("Pop Art", "pop_art"),
            ("Impressionist", "impressionist"),
        ]:
            self._center_style_menu.add_command(label=display_name,
                command=lambda sk=style_key: self._gallery_apply_theme(sk))
        self._center_style_btn.config(menu=self._center_style_menu)
        self._center_style_btn.pack(side="right", padx=(6, 0))

        # Image preview area
        preview_card = ttk.Frame(center)
        preview_card.grid(row=1, column=0, sticky="nsew")
        preview_card.rowconfigure(0, weight=1)
        preview_card.columnconfigure(0, weight=1)

        self.preview_source_label = ttk.Label(preview_card, text="")
        self.image_label = tk.Label(preview_card, text="Selected or generated image\nwill appear here",
                                    anchor="center", justify="center", width=80, height=30)
        self.image_label.grid(row=0, column=0, sticky="nsew")
        self.image_label.bind("<Double-Button-1>", self.previewdoubleclick)
        self.image_label.bind("<Configure>", self._on_preview_resize)
        self.last_preview_path = None

        details = ttk.Frame(preview_card, style="Inner.TFrame")
        details.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.preview_details_frame = details
        self.preview_name_label = ttk.Label(details, text="", wraplength=600)
        self.preview_name_label.configure(font=self.bold_font)
        self.preview_name_label.pack(anchor="w")
        self.preview_dims_label = ttk.Label(details, text="")
        self.preview_dims_label.pack(anchor="w")
        self.preview_size_label = ttk.Label(details, text="")
        self.preview_size_label.pack(anchor="w")

        # Slideshow countdown progress bar (above prompt preview)
        progress_frame = ttk.Frame(center, height=24)
        progress_frame.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        progress_frame.grid_propagate(False)
        progress_frame.columnconfigure(0, weight=1)
        progress_frame.rowconfigure(0, weight=1)
        self.progress = ttk.Progressbar(progress_frame, mode="determinate", maximum=100)
        self.progress.grid(row=0, column=0, sticky="nsew")
        self.progress_overlay_label = tk.Label(progress_frame, text="", font=self.bold_font, anchor="center")
        self.progress_overlay_label.place(relx=0.5, rely=0.5, anchor="center")
        # Progress bar is always visible, shows countdown when slideshow is running

        # Image generation status label (below slideshow progress bar)
        # Simple visual indicator when image is being generated
        self.image_generation_status_label = ttk.Label(center, text="", font=self.bold_font, anchor="center", foreground="#00ff00")
        self.image_generation_status_label.grid(row=3, column=0, sticky="ew", pady=(4, 0))

        # Generation progress bar overlay (over image preview)
        self.generation_progress = ttk.Progressbar(preview_card, mode="indeterminate", maximum=100)
        self.generation_progress.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.5, relheight=0.1)
        self.generation_progress.place_forget()  # Hide initially

        # Prompt preview (below progress bars)
        preview_frame = ttk.LabelFrame(center, text="Prompt Preview", padding=(8, 4))
        preview_frame.grid(row=4, column=0, sticky="ew", pady=(6, 0))
        preview_frame.columnconfigure(0, weight=1)

        badge_frame = ttk.Frame(preview_frame)
        badge_frame.grid(row=0, column=0, sticky="ew", pady=(0, 2))
        badge_frame.columnconfigure(0, weight=1)

        self.mode_badge = ttk.Label(badge_frame,
                                    text=f"Subject lock: ON")
        self.mode_badge.grid(row=0, column=0, sticky="w")

        ttk.Button(badge_frame, text=" Copy Prompt", width=18,
                   command=self._copy_prompt_to_clipboard).grid(row=0, column=1, sticky="e", padx=(4, 0))

        _pt_scroll = ttk.Scrollbar(preview_frame, orient="vertical")
        self.prompt_text = tk.Text(
            preview_frame, wrap="word", font=self.mono_font, height=8,
            yscrollcommand=_pt_scroll.set,
        )
        _pt_scroll.config(command=self.prompt_text.yview)
        self.prompt_text.grid(row=1, column=0, sticky="nsew")
        _pt_scroll.grid(row=1, column=1, sticky="ns")
        self.prompt_text.config(state="disabled")
        self.prompt_text.bind("<MouseWheel>", lambda e: self._on_prompt_text_scroll(e))

        # ═══════════════════════ RIGHT PANEL (GALLERY) ══════════════════════
        right = ttk.Frame(self.main, padding=(8, 8))
        right.grid(row=0, column=2, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)
        self._right_panel = right

        # Header: "My Collection" + view icons
        gallery_header = ttk.Frame(right)
        gallery_header.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        ttk.Label(gallery_header, text="My Collection",
                  font=self.sidebar_title_font).pack(side="left")
        
        button_frame = ttk.Frame(gallery_header)
        button_frame.pack(side="right")
        
        ttk.Button(button_frame, text=" Open Folder", width=18,
                   command=self._open_wallpapers_folder).pack(side="left", padx=(0, 4))
        ttk.Button(button_frame, text=" Refresh Gallery", width=18,
                   command=self.load_gallery).pack(side="left")

        # Gallery content — delegate to existing builder
        gallery_content = ttk.Frame(right, padding=(0, 0))
        gallery_content.grid(row=1, column=0, sticky="nsew")
        self._build_gallery_tab(gallery_content)

        # ═══════════════════════ BOTTOM STATUS BAR ══════════════════════════
        bottom = ttk.Frame(self.main)
        bottom.grid(row=1, column=0, columnspan=3, sticky="ew", padx=8, pady=(4, 4))
        self.bottom_bar = bottom

        ttk.Label(bottom, textvariable=self.statusvar).pack(side="right")

        # ── Notebook stub (kept so existing code doesn't crash) ─────────────
        # Hidden notebook — never displayed, but self.notebook.select() calls
        # are wrapped in try/except throughout, so this is safe.
        self._notebook_stub = ttk.Frame(self.main)
        self.notebook = ttk.Notebook(self._notebook_stub)
        gallery_tab = ttk.Frame(self.notebook)
        self.gallery_tab = gallery_tab
        prompt_builder_tab = ttk.Frame(self.notebook)
        self.prompt_builder_tab = prompt_builder_tab
        self.generator_tab = prompt_builder_tab
        settings_tab = ttk.Frame(self._notebook_stub, padding=(20, 10))
        self.settings_tab = settings_tab
        self.notebook.add(prompt_builder_tab, text="Prompt Builder")
        self.notebook.add(gallery_tab, text="Gallery")

        # Build prompt builder into hidden tab so Quick Build refs exist
        self.build_prompt_builder_tab(prompt_builder_tab)

        # Build settings into hidden tab (opened via modal)
        self._build_settings_tab(settings_tab)

        # Sync slideshow state now that widgets exist
        self.sync_slideshow_state()

        self.root.bind_all("<MouseWheel>", self._on_mousewheel)



    def _build_gallery_tab(self, parent):
        return self._gallery_tab._build_gallery_tab(parent)




    # toggle_gallery_sort removed - dropdown handles all sorting



    def sort_gallery(self, event=None):
        return self._gallery_tab.sort_gallery(event)


    def _do_sort_gallery_reload(self):
        return self._gallery_tab._do_sort_gallery_reload()




    def _on_tag_var_changed(self, *args):
        return self._gallery_tab._on_tag_var_changed(*args)


    def _confirm_delete_tag(self):
        return self._gallery_tab._confirm_delete_tag()


    def _on_tag_selected(self):
        return self._gallery_tab._on_tag_selected()


    def apply_gallery_filter(self):
        return self._gallery_tab.apply_gallery_filter()



    def on_gallery_resize(self, event):
        return self._gallery_tab.on_gallery_resize(event)




    def refresh_grid_layout(self, cols):
        return self._gallery_tab.refresh_grid_layout(cols)




    # ------------------------------------------------------------------
    # Lazy / virtual gallery rendering
    # ------------------------------------------------------------------
    #
    # Strategy: every image index always occupies a grid slot in gallery_inner,
    # either as a real thumbnail card or as a fixed-size placeholder Frame.
    # This keeps gallery_inner's height correct so the canvas scrollregion and
    # scrollbar always match reality.
    #
    # _render_visible_cards() "promotes" placeholders → real cards for the
    # visible viewport (+1 row buffer) and "demotes" real cards → placeholders
    # outside that range.  thumb_cache means re-promotion is instant.
    # ------------------------------------------------------------------

    def _gallery_visible_range(self):
        return self._gallery_tab._gallery_visible_range()


    def _make_gallery_placeholder(self, idx, row, col):
        return self._gallery_tab._make_gallery_placeholder(idx, row, col)


    def _render_visible_cards(self):
        return self._gallery_tab._render_visible_cards()


    def _on_gallery_scroll(self, *_):
        return self._gallery_tab._on_gallery_scroll(*_)


    def _gallery_view_mode(self):
        return self._gallery_tab._gallery_view_mode()


    def get_active_tag(self):
        return self._gallery_tab.get_active_tag()


    def _gallery_set_wallpaper(self):
        return self._gallery_tab._gallery_set_wallpaper()


    def _gallery_save_to_favorites(self):
        return self._gallery_tab._gallery_save_to_favorites()


    def _gallery_apply_theme(self, style_key):
        return self._gallery_tab._gallery_apply_theme(style_key)


    def _gallery_add_text(self):
        return self._gallery_tab._gallery_add_text()


    def _gallery_tag_selected(self):
        return self._gallery_tab._gallery_tag_selected()


    def _gallery_delete(self):
        return self._gallery_tab._gallery_delete()


    def _delete_styled_image(self):
        return self._gallery_tab._delete_styled_image()

    def _copy_prompt_to_clipboard(self):
        return self._gallery_tab._copy_prompt_to_clipboard()


    def _open_wallpapers_folder(self):
        return self._gallery_tab._open_wallpapers_folder()


    def _on_gallery_view_changed(self):
        return self._gallery_tab._on_gallery_view_changed()


    def load_gallery(self):
        return self._gallery_tab.load_gallery()




    def create_gallery_card(self, img_path, row, col, index):
        return self._gallery_tab.create_gallery_card(img_path, row, col, index)




    def on_card_click(self, event, path, index):
        return self._gallery_tab.on_card_click(event, path, index)


    def show_gallery_context_menu(self, event, path):
        return self._gallery_tab.show_gallery_context_menu(event, path)


    def load_prompt_from_history(self, image_path):
        return self._gallery_tab.load_prompt_from_history(image_path)


    def copy_to_clipboard(self, text):
        return self._gallery_tab.copy_to_clipboard(text)




    def on_card_drag(self, event, index):
        return self._gallery_tab.on_card_drag(event, index)


    def on_card_drop(self, event, source_index):
        return self._gallery_tab.on_card_drop(event, source_index)




    def _widget_to_card_index(self, widget):
        return self._gallery_tab._widget_to_card_index(widget)


    def _highlight_organize_source(self, picked_index, hover_index):
        return self._gallery_tab._highlight_organize_source(picked_index, hover_index=hover_index)




    def apply_style_transfer_filter(self, style_key):
        return self._gallery_tab.apply_style_transfer_filter(style_key)




    def apply_artistic_filter(self, style_name):
        return self._gallery_tab.apply_artistic_filter(style_name)




    def on_fav_resize(self, event):
        return self._gallery_tab.on_fav_resize(event)




    def _rebuild_fav_grid(self, cols):
        return self._gallery_tab._rebuild_fav_grid(cols)




    def on_styled_resize(self, event):
        return self._gallery_tab.on_styled_resize(event)




    def _rebuild_styled_grid(self, cols):
        return self._gallery_tab._rebuild_styled_grid(cols)




    def on_manual_resize(self, event):
        return self._gallery_tab.on_manual_resize(event)




    def _rebuild_manual_grid(self, cols):
        return self._gallery_tab._rebuild_manual_grid(cols)





    def on_organize_toggle(self):
        return self._gallery_tab.on_organize_toggle()


    def _on_thumbnail_click(self, path, ctrl_pressed=False):
        return self._gallery_tab._on_thumbnail_click(path, ctrl_pressed)


    def _update_gallery_highlight(self, selected_path):
        return self._gallery_tab._update_gallery_highlight(selected_path)


    def _update_gallery_highlight_multi(self):
        return self._gallery_tab._update_gallery_highlight_multi()


    def set_gallery_image_as_wallpaper(self, path):
        return self._gallery_tab.set_gallery_image_as_wallpaper(path)




    def set_gallery_selection(self):
        return self._gallery_tab.set_gallery_selection()




    def save_gallery_to_favorites(self):
        return self._gallery_tab.save_gallery_to_favorites()




    def _resolve_related_paths(self, path):
        return self._gallery_tab._resolve_related_paths(path)


    def _propagate_tags_to_related(self, path, tags):
        return self._gallery_tab._propagate_tags_to_related(path, tags)


    def tag_gallery_image(self):
        return self._gallery_tab.tag_gallery_image()




    def organize_gallery_image(self):
        return self._gallery_tab.organize_gallery_image()




    def delete_selected(self):
        return self._gallery_tab.delete_selected()




    def _refresh_tag_ui(self, status_msg=None, keep_selection=True):
        return self._gallery_tab._refresh_tag_ui(status_msg, keep_selection)


    def _refresh_gallery_tag_filter(self):
        return self._gallery_tab._refresh_gallery_tag_filter()


        

    def clear_image(self):
        return self._gallery_tab.clear_image()


    def open_style_dialog(self):
        return self._gallery_tab.open_style_dialog()


    

    def apply_selected_style(self, dialog):
        return self._gallery_tab.apply_selected_style(dialog)


    

    def _apply_style_thread(self, style):
        return self._gallery_tab._apply_style_thread(style)


    

    def _style_applied_success(self, styled_path, style):
        return self._gallery_tab._style_applied_success(styled_path, style)




    def toggle_fullscreen(self, event=None):
        return self._gallery_tab.toggle_fullscreen(event)


    def _on_minimize_to_tray_changed(self):
        """Handle minimize-to-tray setting change."""
        new_value = self.minimize_to_tray_var.get()

        self.minimize_to_tray_enabled = new_value
        config = load_config()
        config["minimize_to_tray"] = new_value
        save_config(config)

        if hasattr(self, "_tray_icon") and self._tray_icon:
            try:
                self._tray_icon.update_menu()
            except Exception as e:
                logger.error(f"Error updating tray menu: {e}")

    def _on_minimize(self, event=None):
        """Handle window minimize event — keep taskbar button; start tray if enabled."""
        if self.minimize_to_tray_enabled and self.root.state() == "iconic":
            # Do NOT withdraw — that removes the taskbar button.
            # Stay iconic so the taskbar entry remains; only add the tray icon.
            self._start_tray()

    def advance_slideshow(self):
        """Advance slideshow with single step and debounce."""
        current_time = time.time()

        if not hasattr(self, "_last_advance_time"):
            self._last_advance_time = 0

        if current_time - self._last_advance_time < 1.0:
            return

        self._last_advance_time = current_time
        self.slideshow.advance_once()

    def _slideshow_prev(self):
        """Go to previous wallpaper in slideshow history."""
        self.slideshow.prev_wallpaper()

    def _slideshow_play(self):
        """Start the slideshow."""
        self.slideshow.start()

    def _slideshow_pause(self):
        """Pause the slideshow."""
        self.slideshow.pause()

    def _slideshow_next(self):
        """Advance to next wallpaper."""
        self.advance_slideshow()

    def _slideshow_stop(self):
        """Stop the slideshow."""
        self.slideshow.stop()

    def on_close(self):
        """Minimize to taskbar (and tray) when X is pressed; only quit on explicit Quit."""
        if hasattr(self, "save_current_settings_for_memory"):
            self.save_current_settings_for_memory()

        if self.minimize_to_tray_enabled:
            self.root.withdraw()   # hide window completely, show only tray icon
            self._start_tray()
        else:
            self._stop_fullscreen_watcher()
            self.slideshow.stop()
            self._stop_tray()
            self._shutdown_db()
            try:
                self.root.destroy()
            except Exception:
                pass
            import os
            os._exit(0)

    def _shutdown_db(self):
        """Close database connections before app exits."""
        try:
            import database
            database.shutdown_db()
        except Exception:
            pass

    def _style_applied_failed(self, style):
        return self._gallery_tab._style_applied_failed(style)


    def _style_applied_error(self, error):
        return self._gallery_tab._style_applied_error(error)

    def _build_demoted_theme_builder(self, parent):
        return self._prompt_tab._build_demoted_theme_builder(parent)


    def _build_theme_builder_panel(self, parent, assign_refs, title, refs):
        return self._prompt_tab._build_theme_builder_panel(parent, assign_refs=assign_refs, title=title, refs=refs)


    def build_prompt_builder_tab(self, parent):
        return self._prompt_tab.build_prompt_builder_tab(parent)


    def update_prompt_builder_mode(self):
        return self._prompt_tab.update_prompt_builder_mode()


    def _on_notebook_tab_changed(self, event=None):
        return self._prompt_tab._on_notebook_tab_changed(event)


    def _open_settings_window(self):
        return self._prompt_tab._open_settings_window()


    def _open_recipe_window(self):
        return self._prompt_tab._open_recipe_window()


    def _toggle_recipe_library(self):
        return self._prompt_tab._toggle_recipe_library()


    def _build_templates_tab(self, parent):
        return self._prompt_tab._build_templates_tab(parent)


    def ontemplateselected(self, event=None):
        return self._prompt_tab.ontemplateselected(event)


    def load_selected_recipe_into_quick_build(self):
        return self._prompt_tab.load_selected_recipe_into_quick_build()


    def load_selected_prompt_from_library(self):
        return self._prompt_tab.load_selected_prompt_from_library()


    def loadtemplate(self):
        return self._prompt_tab.loadtemplate()


    def _load_recipe(self, recipe):
        return self._prompt_tab._load_recipe(recipe)


    def _load_template_legacy(self, template):
        return self._prompt_tab._load_template_legacy(template)


    def generatefromtemplate(self):
        return self._prompt_tab.generatefromtemplate()


    def _generate_from_recipe(self, recipe):
        return self._prompt_tab._generate_from_recipe(recipe)


    def _generate_from_template_legacy(self, template):
        return self._prompt_tab._generate_from_template_legacy(template)


    def refreshtemplatelist(self):
        return self._prompt_tab.refreshtemplatelist()


    def _refresh_template_library(self):
        return self._prompt_tab._refresh_template_library()


    def _update_template_detail_label(self):
        return self._prompt_tab._update_template_detail_label()


    def resettemplatevariables(self):
        return self._prompt_tab.resettemplatevariables()


    def _generate_template_name_from_prompt(self, prompt):
        return self._prompt_tab._generate_template_name_from_prompt(prompt)


    def _generate_template_description(self):
        return self._prompt_tab._generate_template_description()


    def save_as_template(self):
        return self._prompt_tab.save_as_template()


    def _save_template_dialog(self, name, description, dialog):
        return self._prompt_tab._save_template_dialog(name, description, dialog)




    # ── Working Session save / load ──────────────────────────────────────────

    def _collect_session_state(self):
        return self._session_mgr._collect_session_state()


    def _restore_session_state(self, state):
        return self._session_mgr._restore_session_state(state)


    def save_session(self):
        return self._session_mgr.save_session()


    def load_session(self):
        return self._session_mgr.load_session()


    def _ensure_recipe_manager(self):
        return self._prompt_tab._ensure_recipe_manager()


    def save_as_quick_recipe(self):
        return self._prompt_tab.save_as_quick_recipe()


    def _save_quick_recipe_dialog(self, name, description, dialog, subject, style, lighting, mood, color, atmosphere, mode, subject_lock, negative_prompt):
        return self._prompt_tab._save_quick_recipe_dialog(name, description, dialog, subject, style, lighting, mood, color, atmosphere, mode, subject_lock, negative_prompt)


    def _generate_quick_recipe_name(self, subject, style, mood, atmosphere=None):
        return self._prompt_tab._generate_quick_recipe_name(subject, style, mood, atmosphere)


    def _generate_quick_recipe_description(self, subject, style, mood, lighting, atmosphere=None):
        return self._prompt_tab._generate_quick_recipe_description(subject, style, mood, lighting, atmosphere)


    def load_quick_recipe(self):
        return self._prompt_tab.load_quick_recipe()


    def _load_quick_recipe_to_theme_builder(self, recipe):
        return self._prompt_tab._load_quick_recipe_to_theme_builder(recipe)


    def delete_quick_recipe(self):
        return self._prompt_tab.delete_quick_recipe()


    def duplicate_template(self):
        return self._prompt_tab.duplicate_template()


    def import_templates(self):
        return self._prompt_tab.import_templates()

    
    def export_templates(self):
        return self._prompt_tab.export_templates()


    def edit_template(self):
        return self._prompt_tab.edit_template()


    def _open_template_edit_dialog(self, source, is_recipe):
        return self._prompt_tab._open_template_edit_dialog(source, is_recipe=is_recipe)


    def delete_template(self):
        return self._prompt_tab.delete_template()


    

    def export_template(self):
        return self._prompt_tab.export_template()


    def import_template(self):
        return self._prompt_tab.import_template()


    

    # _on_template_search and _clear_template_search removed —
    # template_search_var widget was never added to the UI.











    def previewdoubleclick(self, event=None):
        return self._prompt_tab.previewdoubleclick(event)





    def _build_settings_tab(self, parent):
        result = self._settings_tab._build_settings_tab(parent)
        # Inject fullscreen pause checkbox after settings UI is built
        self.root.after(500, lambda: self._add_fullscreen_setting(parent))
        return result




    def _on_model_choice_changed(self, event=None):
        return self._settings_tab._on_model_choice_changed(event)

    def _on_provider_changed(self, event=None):
        return self._settings_tab._on_provider_changed(event)

    def _update_provider_visibility(self):
        return self._settings_tab._update_provider_visibility()

    def _update_provider_description(self):
        return self._settings_tab._update_provider_description()




    def setup_scheduler_from_gui(self):
        return self._settings_tab.setup_scheduler_from_gui()




    def migrate_saved_image_paths(self):

        updated_favorites = 0

        # One disk scan for all guesses.

        known_images = self._all_known_images()

        for item in self.favorites:

            if not item.get("image_path"):

                guessed = self._guess_image_for_item(item, known_images=known_images)

                if guessed:

                    item["image_path"] = str(guessed)

                    updated_favorites += 1

        if updated_favorites:

            save_json_list(FAVORITES_LOG, self.favorites)

        return 0, updated_favorites



    def load_presets(self):
        self.presets = load_presets()
        # Presets UI removed - just load the data for potential future use



    def _preset_payload(self):

        return {

            "subject": self.get_active_subject(),

            "style": self.get_active_style(),

            "lighting": self.get_active_lighting(),

            "mood": self.get_active_mood(),

            "color": self.get_active_color(),

            "mode": self.get_active_mode(),

            "subject_lock": self.get_active_subject_lock(),

            "negative_prompt": self.get_active_negative_prompt(),

        }



    def save_current_preset(self):

        name = simpledialog.askstring("Save Preset Bundle", "Preset name:", parent=self.root)

        if not name or not name.strip():

            return

        name = name.strip()

        

        # Save as a full bundle including themes and prompts

        payload = self._preset_payload()

        save_bundle_preset(

            name=name,

            subject=payload["subject"],

            style=payload["style"],

            lighting=payload["lighting"],

            mood=payload["mood"],

            style_mode=payload["mode"],

            themes=self.themes if self.themes else [],

            prompts=self.prompts if self.prompts else [],

            favorite_prompts=[],  # Could be populated later

        )

        self.load_presets()
        self.status_var.set(f"✓ Bundle preset saved: {name}")


    def load_selected_preset(self):
        # Presets UI removed - this method is no longer used
        pass


    def delete_current_preset(self):
        # Presets UI removed - this method is no longer used
        pass


    def export_preset_bundle(self):
        """Export current preset to a shareable JSON file."""
        # Presets UI removed - this method is no longer used
        pass



    def import_preset_bundle(self):

        """Import a preset from a JSON file."""

        from tkinter import filedialog

        path = filedialog.askopenfilename(

            filetypes=[("JSON files", "*.json")],

            title="Import Preset Bundle",

        )

        if not path:

            return

        preset_id = import_preset(path)

        if preset_id:

            self.load_presets()

            preset = get_preset_by_id(preset_id)

            if preset:
                # Presets UI removed - no need to set preset_var
                pass
            self.status_var.set(f"✓ Preset imported: {Path(path).name}")
            self._dialog.info("Import Successful", f"Preset imported and loaded.")

        else:
            self._dialog.error("Import Failed", "Could not import preset file.")





    def _all_known_images(self):

        paths = []

        try:

            paths.extend(collect_wallpapers())

        except Exception:

            pass

        wallpapers_root = BASE_DIR / "wallpapers"

        if wallpapers_root.exists():

            for p in wallpapers_root.rglob("*"):

                if p.is_file() and p.suffix.lower() in IMAGE_EXTS:

                    paths.append(p)

        unique = []

        seen = set()

        for p in paths:

            rp = str(Path(p).resolve())

            if rp not in seen:

                seen.add(rp)

                unique.append(Path(p))

        unique.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)

        return unique



    def _guess_image_for_item(self, item, strict=False, known_images=None):

        for key in ("image_path", "path", "last_image_path"):

            val = item.get(key)

            if val:

                p = Path(val)

                if p.exists():

                    return p

        if strict:

            return None

        known = known_images if known_images is not None else self._all_known_images()

        sentence = (item.get("theme_sentence") or "").strip().lower()

        prompt = (item.get("prompt") or "").strip().lower()

        for p in known:

            name = p.stem.lower()

            if sentence and any(word for word in sentence.split()[:3] if word and word in name):

                return p

            if prompt and any(word for word in prompt.split()[:3] if word and word in name):

                return p

        return known[0] if known else None



    def _on_preview_resize(self, event=None):
        if self.last_preview_path:
            self._render_preview(self.last_preview_path)

    def _render_preview(self, path):
        try:
            from PIL import Image, ImageTk
            path = Path(path)
            img = Image.open(path)
            w = max(self.image_label.winfo_width(), 100)
            h = max(self.image_label.winfo_height(), 100)
            preview = img.copy()
            preview.thumbnail((w, h), Image.Resampling.LANCZOS)
            self.last_image_tk = ImageTk.PhotoImage(preview)
            self.image_label.config(image=self.last_image_tk, text="")
        except Exception:
            pass

    def show_preview_in_left_panel(self, path, source_text="Preview"):

        try:

            from PIL import Image, ImageTk

            path = Path(path)

            img = Image.open(path)

            orig_w, orig_h = img.size

            self.last_preview_path = path
            w = max(self.image_label.winfo_width(), 100)
            h = max(self.image_label.winfo_height(), 100)
            preview = img.copy()
            preview.thumbnail((w, h), Image.Resampling.LANCZOS)

            self.last_image_tk = ImageTk.PhotoImage(preview)

            self.image_label.config(image=self.last_image_tk, text="")

            self.preview_source_label.config(text=source_text)

            size_bytes = path.stat().st_size

            size_str = f"{size_bytes / 1_048_576:.1f} MB" if size_bytes >= 1_048_576 else f"{size_bytes / 1024:.1f} KB"

            self.preview_name_label.config(text=path.name)

            self.preview_dims_label.config(text=f"Resolution: {orig_w} × {orig_h} px")

            self.preview_size_label.config(text=f"File size: {size_str}")

        except Exception as e:

            self.image_label.config(text=f"Preview failed: {e}", image="")

            self.preview_source_label.config(text=source_text)

            self.preview_name_label.config(text="")

            self.preview_dims_label.config(text="")

            self.preview_size_label.config(text="")





    def _populate_visual_grid(self, ui, items, kind):
        return self._gallery_tab._populate_visual_grid(ui, items, kind)


    def _on_fav_card_click(self, event, path, data, ui, index):
        return self._gallery_tab._on_fav_card_click(event, path, data, ui, index)


    def _on_fav_card_drag(self, event, index):
        return self._gallery_tab._on_fav_card_drag(event, index)


    def _on_fav_card_drop(self, event, source_index):
        return self._gallery_tab._on_fav_card_drop(event, source_index)


    def _fav_widget_to_card_index(self, widget):
        return self._gallery_tab._fav_widget_to_card_index(widget)


    def _highlight_fav_organize(self, picked_index, hover_index):
        return self._gallery_tab._highlight_fav_organize(picked_index, hover_index=hover_index)


    def _update_fav_card_highlight(self, selected_item):
        return self._gallery_tab._update_fav_card_highlight(selected_item)


    def _refresh_fav_card_highlights(self):
        return self._gallery_tab._refresh_fav_card_highlights()


    def _select_visual_item(self, ui, path, data):
        return self._gallery_tab._select_visual_item(ui, path, data)


    def _double_click_visual_item(self, ui, path, data):
        return self._gallery_tab._double_click_visual_item(ui, path, data)


    def double_click_set_wallpaper(self, path):
        return self._gallery_tab.double_click_set_wallpaper(path)


    def random_theme(self):
        return self._gallery_tab.random_theme()




    def upscale_selected(self):
        return self._gallery_tab.upscale_selected()








    def delete_selected_favorite(self):
        return self._gallery_tab.delete_selected_favorite()




    def _on_mousewheel(self, event):
        """Handle mousewheel scrolling with context awareness."""
        try:
            # Check if focus is in an input widget - don't scroll page
            focus_widget = self.root.focus_get()
            if focus_widget:
                widget_class = focus_widget.winfo_class()
                # Skip scrolling if focus is in entry, combobox, or text widget
                if widget_class in ('TEntry', 'Entry', 'TCombobox', 'Combobox', 'Text'):
                    return
                # Also check if mouse is over the prompt_text widget
                if hasattr(self, 'prompt_text') and focus_widget == self.prompt_text:
                    return

            # Get mouse position
            mouse_x = self.root.winfo_pointerx() - self.root.winfo_rootx()
            mouse_y = self.root.winfo_pointery() - self.root.winfo_rooty()

            # Check if mouse is over Prompt Preview text widget
            if hasattr(self, 'prompt_text'):
                try:
                    widget_x = self.prompt_text.winfo_rootx() - self.root.winfo_rootx()
                    widget_y = self.prompt_text.winfo_rooty() - self.root.winfo_rooty()
                    widget_w = self.prompt_text.winfo_width()
                    widget_h = self.prompt_text.winfo_height()
                    if (widget_x <= mouse_x <= widget_x + widget_w and
                        widget_y <= mouse_y <= widget_y + widget_h):
                        # Mouse is over prompt text - scroll it locally
                        self.prompt_text.yview_scroll(int(-1 * (event.delta / 120)), "units")
                        return "break"
                except Exception:
                    pass

            # Gallery is always visible — scroll the active view canvas
            # First determine which canvas to scroll based on mouse position
            target_canvas = None
            view = getattr(self, "gallery_view_var", None)
            
            if view:
                current_view = view.get()
                # Check if mouse is over the active gallery canvas
                if current_view == "Favorites" and hasattr(self, 'gallery_fav_canvas'):
                    widget_x = self.gallery_fav_canvas.winfo_rootx() - self.root.winfo_rootx()
                    widget_y = self.gallery_fav_canvas.winfo_rooty() - self.root.winfo_rooty()
                    widget_w = self.gallery_fav_canvas.winfo_width()
                    widget_h = self.gallery_fav_canvas.winfo_height()
                    if (widget_x <= mouse_x <= widget_x + widget_w and
                        widget_y <= mouse_y <= widget_y + widget_h):
                        target_canvas = self.gallery_fav_canvas
                elif current_view == "Styled" and hasattr(self, 'gallery_styled_canvas'):
                    widget_x = self.gallery_styled_canvas.winfo_rootx() - self.root.winfo_rootx()
                    widget_y = self.gallery_styled_canvas.winfo_rooty() - self.root.winfo_rooty()
                    widget_w = self.gallery_styled_canvas.winfo_width()
                    widget_h = self.gallery_styled_canvas.winfo_height()
                    if (widget_x <= mouse_x <= widget_x + widget_w and
                        widget_y <= mouse_y <= widget_y + widget_h):
                        target_canvas = self.gallery_styled_canvas
                elif current_view == "Manual" and hasattr(self, 'gallery_manual_canvas'):
                    widget_x = self.gallery_manual_canvas.winfo_rootx() - self.root.winfo_rootx()
                    widget_y = self.gallery_manual_canvas.winfo_rooty() - self.root.winfo_rooty()
                    widget_w = self.gallery_manual_canvas.winfo_width()
                    widget_h = self.gallery_manual_canvas.winfo_height()
                    if (widget_x <= mouse_x <= widget_x + widget_w and
                        widget_y <= mouse_y <= widget_y + widget_h):
                        target_canvas = self.gallery_manual_canvas
                elif hasattr(self, 'gallery_canvas'):
                    # Default gallery view
                    widget_x = self.gallery_canvas.winfo_rootx() - self.root.winfo_rootx()
                    widget_y = self.gallery_canvas.winfo_rooty() - self.root.winfo_rooty()
                    widget_w = self.gallery_canvas.winfo_width()
                    widget_h = self.gallery_canvas.winfo_height()
                    if (widget_x <= mouse_x <= widget_x + widget_w and
                        widget_y <= mouse_y <= widget_y + widget_h):
                        target_canvas = self.gallery_canvas

            # Scroll the target canvas if found
            if target_canvas:
                target_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                if target_canvas == self.gallery_canvas:
                    self._on_gallery_scroll()
                return "break"

        except Exception:
            pass

    def _on_prompt_text_scroll(self, event):
        """Handle mousewheel scrolling specifically for Prompt Preview text widget."""
        try:
            self.prompt_text.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"  # Prevent event from bubbling up to parent
        except Exception:
            pass

    def _on_template_var_scroll(self, event):

        """Handle mousewheel scrolling on the template variables scrollable area."""

        try:

            self.template_var_scroll_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        except Exception:

            pass



    def _canonical_mode_value(self, value=None):
        raw = (value or "").strip()
        if not raw:
            # Read mode_var from PB Quick Build refs (primary source).
            # Read directly to avoid circular calls with get_active_mode_label.
            refs = self._get_pb_quick_refs()
            if refs and "mode_var" in refs:
                try:
                    raw = refs["mode_var"].get().strip()
                except Exception:
                    raw = ""
        if not raw:
            return DEFAULT_PROMPT_MODE_VALUE
        lower = raw.lower()
        if lower in STYLE_MODES:
            return lower
        if raw in STYLE_MODES:
            return raw
        for label, canonical in PROMPT_MODE_OPTIONS:
            if lower == label.lower():
                return canonical
        hyphenated = lower.replace(" ", "-")
        if hyphenated in STYLE_MODES:
            return hyphenated
        return DEFAULT_PROMPT_MODE_VALUE

    def current_mode(self):

        return self.get_active_mode()



    def _mode_label(self, mode_value=None):
        canonical = self._canonical_mode_value(mode_value)
        return PROMPT_MODE_VALUE_TO_LABEL.get(canonical, DEFAULT_PROMPT_MODE_LABEL)

    def _set_mode_display(self, mode_value):
        # Retained for any call sites not yet migrated; delegates to set_active_mode.
        self.set_active_mode(mode_value)



    def format_token_preview(self):
        return self._settings_tab.format_token_preview()




    def refresh_token_status(self):
        return self._settings_tab.refresh_token_status()




    def resolved_model_id(self):
        return self._settings_tab.resolved_model_id()




    def save_settings(self):
        result = self._settings_tab.save_settings()
        # Save fullscreen pause setting
        config = load_config()
        config['slideshow_pause_on_fullscreen'] = bool(self.slideshow_pause_on_fullscreen_var.get())
        save_config(config)
        return result




    def load_slideshow_settings(self):
        result = self._settings_tab.load_slideshow_settings()
        # Load fullscreen pause setting and start watcher if enabled
        config = load_config()
        self.slideshow_pause_on_fullscreen_var.set(bool(config.get('slideshow_pause_on_fullscreen', False)))
        if self.slideshow_pause_on_fullscreen_var.get():
            self._start_fullscreen_watcher()
        return result




    def sync_slideshow_state(self):
        return self._settings_tab.sync_slideshow_state()



    def on_slideshow_toggle(self):
        return self._settings_tab.on_slideshow_toggle()




    def slideshow_start_click(self):
        return self._settings_tab.slideshow_start_click()




    def slideshow_stop_click(self):
        return self._settings_tab.slideshow_stop_click()




    def slideshow_next_now(self):
        return self._settings_tab.slideshow_next_now()




    def slideshow_prev_now(self):
        return self._settings_tab.slideshow_prev_now()




    def slideshow_pause_click(self):
        return self._settings_tab.slideshow_pause_click()




    def slideshow_preview_sources(self):
        return self._settings_tab.slideshow_preview_sources()




    def update_slideshow_status(self):
        return self._settings_tab.update_slideshow_status()




    def _on_theme_changed(self, event=None):
        display_name = self.theme_var.get()
        theme_mapping = {
            "Dark (forest green)": "darkforest",
            "Light (forest green)": "light_forest",
            "Ocean Blue (dark)": "dark_ocean",
            "Ocean Blue (light)": "light_ocean",
            "Sunset Orange (dark)": "dark_sunset",
            "Sunset Orange (light)": "light_sunset",
            "High Contrast (dark)": "dark_contrast",
            "High Contrast (light)": "light_contrast",
        }
        theme_name = theme_mapping.get(display_name, "darkforest")
        self.apply_theme(theme_name)

    def _on_dimension_preset_changed(self, event=None):
        return self._settings_tab._on_dimension_preset_changed(event)


    def _set_dimensions_from_string(self, dimensions_str):
        return self._settings_tab._set_dimensions_from_string(dimensions_str)




    def get_current_dimensions(self):
        return self._settings_tab.get_current_dimensions()




    def _on_remember_settings_changed(self, event=None):
        return self._settings_tab._on_remember_settings_changed(event)




    def load_remembered_settings(self):
        return self._settings_tab.load_remembered_settings()




    def add_user_mapping(self):
        return self._settings_tab.add_user_mapping()




    def remove_user_mapping(self):
        return self._settings_tab.remove_user_mapping()




    def save_current_settings_for_memory(self):
        return self._session_mgr.save_current_settings_for_memory()




    def _on_token_changed(self, event=None):
        return self._settings_tab._on_token_changed(event)


    def toggle_token_visibility(self):
        return self._settings_tab.toggle_token_visibility()




    def subject_lock_enabled(self):
        return self._prompt_tab.subject_lock_enabled()




    def _is_prompt_builder_tab_selected(self):
        return self._prompt_tab._is_prompt_builder_tab_selected()


    def _is_prompt_builder_quick_active(self):
        return self._prompt_tab._is_prompt_builder_quick_active()


    def _get_pb_quick_refs(self):
        return self._prompt_tab._get_pb_quick_refs()


    def _get_active_quick_refs(self):
        return self._prompt_tab._get_active_quick_refs()


    def _get_active_widget(self, name):
        return self._prompt_tab._get_active_widget(name)


    def _get_active_text(self, name, default=''):
        return self._prompt_tab._get_active_text(name, default)


    def get_active_subject(self):
        return self._prompt_tab.get_active_subject()


    def get_active_style(self):
        return self._prompt_tab.get_active_style()


    def get_active_lighting(self):
        return self._prompt_tab.get_active_lighting()


    def get_active_mood(self):
        return self._prompt_tab.get_active_mood()


    def get_active_color(self):
        return self._prompt_tab.get_active_color()


    def get_active_setting(self):
        return self._prompt_tab.get_active_setting()


    def set_active_setting(self, value):
        return self._prompt_tab.set_active_setting(value)


    def get_active_atmosphere(self):
        return self._prompt_tab.get_active_atmosphere()


    def get_active_mode_label(self):
        return self._prompt_tab.get_active_mode_label()


    def get_active_mode(self):
        return self._canonical_mode_value(self.get_active_mode_label())

    def get_active_subject_lock(self):
        return self._prompt_tab.get_active_subject_lock()


    def get_active_negative_prompt(self):
        # The var always mirrors the final Text widget content
        return self.negative_prompt_var.get().strip() or DEFAULT_NEGATIVE_PROMPT

    # ── Negative Prompt Builder methods ──────────────────────────────────

    def _rebuild_neg_combined(self, *_args):
        """Rebuild the final combined negative prompt from selected presets + custom terms."""
        if self._neg_manual_edit:
            return  # user is manually editing; don't overwrite
        parts = []
        for key, dname, desc, negs, term_count in self._neg_preset_info:
            if self._neg_preset_vars[key].get():
                parts.append(negs)
        custom = self._neg_custom_var.get().strip()
        if custom:
            parts.append(custom)
        # Deduplicate
        seen = set()
        unique = []
        for raw in (", ".join(parts)).split(","):
            t = raw.strip()
            if t and t.lower() not in seen:
                unique.append(t)
                seen.add(t.lower())
        combined = ", ".join(unique)
        # Update Text widget and StringVar (suppress the <KeyRelease> handler)
        self._neg_final_text.config(state="normal")
        self._neg_final_text.delete("1.0", tk.END)
        self._neg_final_text.insert("1.0", combined)
        self.negative_prompt_var.set(combined)
        # Update term count
        count = len(unique)
        self._neg_term_count_var.set(f"{count} term{'s' if count != 1 else ''}")

    def _on_neg_final_edited(self, event=None):
        """User typed in the final Text widget — enter manual-edit mode."""
        self._neg_manual_edit = True
        text = self._neg_final_text.get("1.0", tk.END).strip()
        self.negative_prompt_var.set(text)
        count = len([t for t in text.split(",") if t.strip()])
        self._neg_term_count_var.set(f"{count} term{'s' if count != 1 else ''} (edited)")

    def _reset_neg_combined(self):
        """Exit manual-edit mode and rebuild from presets + custom."""
        self._neg_manual_edit = False
        self._rebuild_neg_combined()

    # ── Active-source setters ────────────────────────────────────────────────

    def _set_active_entry(self, name, value):
        return self._prompt_tab._set_active_entry(name, value)


    def _set_active_var(self, name, value):
        return self._prompt_tab._set_active_var(name, value)


    def set_active_subject(self, value):
        return self._prompt_tab.set_active_subject(value)


    def set_active_style(self, value):
        return self._prompt_tab.set_active_style(value)


    def set_active_lighting(self, value):
        return self._prompt_tab.set_active_lighting(value)


    def set_active_mood(self, value):
        return self._prompt_tab.set_active_mood(value)


    def set_active_color(self, value):
        return self._prompt_tab.set_active_color(value)


    def set_active_atmosphere(self, value):
        return self._prompt_tab.set_active_atmosphere(value)


    def set_active_mode(self, mode_value):
        return self._prompt_tab.set_active_mode(mode_value)


    def set_active_subject_lock(self, value):
        return self._prompt_tab.set_active_subject_lock(value)


    def set_active_negative_prompt(self, value):
        return self._prompt_tab.set_active_negative_prompt(value)


    # ────────────────────────────────────────────────────────────────────────

    def update_mode_badge(self, mode=None):
        return self._prompt_tab.update_mode_badge(mode)




    def get_negative_prompt(self):
        return self._prompt_tab.get_negative_prompt()




    def apply_negative_prompt_to_prompts(self):
        return self._prompt_tab.apply_negative_prompt_to_prompts()




    def generate(self, show_progress=True):

        if self.is_generating:

            self._dialog.info("Please wait", "Generation is already in progress.")

            return

        # Read from sidebar widgets (same as generate_prompt_only)
        logger.debug(f"generate: Reading from sidebar widgets")
        
        # Subject - check if it's a Combobox or Entry
        if hasattr(self, 'subject_entry'):
            if hasattr(self.subject_entry, 'get'):
                val = self.subject_entry.get()
                logger.debug(f"generate: subject_entry.get() = '{val}'")
                self.prompt_builder_values["subject"] = val
            elif hasattr(self.subject_entry, 'current'):
                idx = self.subject_entry.current()
                if idx >= 0:
                    val = self.subject_entry.get()
                    logger.debug(f"generate: subject_entry (combobox).get() = '{val}'")
                    self.prompt_builder_values["subject"] = val
        
        # Style - sidebar doesn't have style dropdown, read from Mode dropdown
        # The Mode dropdown is below the Style label and contains style values like "Painterly"
        if hasattr(self, 'mode_var') and hasattr(self.mode_var, 'get'):
            val = self.mode_var.get()
            logger.debug(f"generate: mode_var.get() = '{val}'")
            # Convert mode label to value if needed
            if val in PROMPT_MODE_LABEL_TO_VALUE:
                style_value = PROMPT_MODE_LABEL_TO_VALUE[val]
                logger.debug(f"generate: style from mode: '{style_value}'")
                self.prompt_builder_values["style"] = style_value
            else:
                self.prompt_builder_values["style"] = val
        # Fallback to Prompt Builder if sidebar mode is not available
        refs = self._get_pb_quick_refs()
        if refs and not self.prompt_builder_values.get("style"):
            style_entry = refs.get("style_entry")
            if style_entry and hasattr(style_entry, 'get'):
                val = style_entry.get()
                logger.debug(f"generate: style_entry (from PB).get() = '{val}'")
                self.prompt_builder_values["style"] = val
        
        # Lighting
        if hasattr(self, 'lighting_entry'):
            if hasattr(self.lighting_entry, 'get'):
                val = self.lighting_entry.get()
                logger.debug(f"generate: lighting_entry.get() = '{val}'")
                self.prompt_builder_values["lighting"] = val
            elif hasattr(self.lighting_entry, 'current'):
                idx = self.lighting_entry.current()
                if idx >= 0:
                    val = self.lighting_entry.get()
                    logger.debug(f"generate: lighting_entry (combobox).get() = '{val}'")
                    self.prompt_builder_values["lighting"] = val
        
        # Setting
        if hasattr(self, 'setting_entry'):
            if hasattr(self.setting_entry, 'get'):
                val = self.setting_entry.get()
                logger.debug(f"generate: setting_entry.get() = '{val}'")
                self.prompt_builder_values["setting"] = val
            elif hasattr(self.setting_entry, 'current'):
                idx = self.setting_entry.current()
                if idx >= 0:
                    val = self.setting_entry.get()
                    logger.debug(f"generate: setting_entry (combobox).get() = '{val}'")
                    self.prompt_builder_values["setting"] = val
        
        # Atmosphere
        if hasattr(self, 'atmosphere_combo'):
            if hasattr(self.atmosphere_combo, 'get'):
                val = self.atmosphere_combo.get()
                logger.debug(f"generate: atmosphere_combo.get() = '{val}'")
                self.prompt_builder_values["atmosphere"] = val
            elif hasattr(self.atmosphere_combo, 'current'):
                idx = self.atmosphere_combo.current()
                if idx >= 0:
                    val = self.atmosphere_combo.get()
                    logger.debug(f"generate: atmosphere_combo (combobox).get() = '{val}'")
                    self.prompt_builder_values["atmosphere"] = val
        
        # Color - combine family and variation
        if hasattr(self, 'color_family_var') and hasattr(self.color_family_var, 'get'):
            family = self.color_family_var.get()
            variation = ""
            if hasattr(self, 'color_variation_var') and hasattr(self.color_variation_var, 'get'):
                variation = self.color_variation_var.get()
            if family and variation:
                val = f"{variation} {family}"
            else:
                val = family or variation
            logger.debug(f"generate: color: family='{family}', variation='{variation}', combined='{val}'")
            self.prompt_builder_values["color"] = val

        subject = self.get_active_subject()

        setting = self.get_active_setting()

        style = self.get_active_style()

        lighting = self.get_active_lighting()

        mood = self.get_active_mood()

        color = self.get_active_color()

        atmosphere = self.get_active_atmosphere()

        mode = self.get_active_mode()

        subject_lock = self.get_active_subject_lock()

        logger.debug(f"generate: After getter functions:")
        logger.info(f"  subject='{subject}'")
        logger.info(f"  style='{style}'")
        logger.info(f"  lighting='{lighting}'")
        logger.info(f"  setting='{setting}'")
        logger.info(f"  atmosphere='{atmosphere}'")
        logger.info(f"  mood='{mood}'")
        logger.info(f"  color='{color}'")
        logger.info(f"  mode='{mode}'")
        logger.info(f"  subject_lock={subject_lock}")

        # Check if audit mode is enabled
        run_audit = False
        if hasattr(self, 'prompt_audit_var'):
            run_audit = self.prompt_audit_var.get()

        # Clear template selection when generating from Quick Build
        self.prompt_source = "theme_builder"
        self._should_generate_image = True  # Flag to trigger image generation
        if hasattr(self, 'template_var'):
            self.template_var.set("")

        self.is_generating = True
        self._show_generation_progress()

        self.cancel_event.clear()

        self.update_mode_badge(mode)

        self.status_var.set("Generating themes...")

        # Use ThreadPoolExecutor for non-blocking UI

        self.gen_future = self.executor.submit(

            self._generate_themes_thread,

            subject, setting, style, lighting, mood, color, atmosphere, mode, subject_lock, run_audit

        )

    def generate_prompt_only(self):
        """Generate prompt text from sidebar choices without generating the image."""
        logger.debug("generate_prompt_only called")
        if self.is_generating:
            self._dialog.info("Please wait", "Generation is already in progress.")
            return

        # Read from sidebar widgets (what the user is actually using)
        logger.debug(f"Reading from sidebar widgets")
        
        # Subject - check if it's a Combobox or Entry
        if hasattr(self, 'subject_entry'):
            if hasattr(self.subject_entry, 'get'):
                val = self.subject_entry.get()
                logger.debug(f"subject_entry.get() = '{val}'")
                self.prompt_builder_values["subject"] = val
            elif hasattr(self.subject_entry, 'current'):
                # It's a Combobox - get current selection
                idx = self.subject_entry.current()
                if idx >= 0:
                    val = self.subject_entry.get()
                    logger.debug(f"subject_entry (combobox).get() = '{val}'")
                    self.prompt_builder_values["subject"] = val
        
        # Style - sidebar doesn't have style dropdown, read from Mode dropdown
        # The Mode dropdown is below the Style label and contains style values like "Painterly"
        if hasattr(self, 'mode_var') and hasattr(self.mode_var, 'get'):
            val = self.mode_var.get()
            logger.debug(f"mode_var.get() = '{val}'")
            # Convert mode label to value if needed
            if val in PROMPT_MODE_LABEL_TO_VALUE:
                style_value = PROMPT_MODE_LABEL_TO_VALUE[val]
                logger.debug(f"style from mode: '{style_value}'")
                self.prompt_builder_values["style"] = style_value
            else:
                self.prompt_builder_values["style"] = val
        # Fallback to Prompt Builder if sidebar mode is not available
        refs = self._get_pb_quick_refs()
        if refs and not self.prompt_builder_values.get("style"):
            style_entry = refs.get("style_entry")
            if style_entry and hasattr(style_entry, 'get'):
                val = style_entry.get()
                logger.debug(f"style_entry (from PB).get() = '{val}'")
                self.prompt_builder_values["style"] = val
        
        # Lighting
        if hasattr(self, 'lighting_entry'):
            if hasattr(self.lighting_entry, 'get'):
                val = self.lighting_entry.get()
                logger.debug(f"lighting_entry.get() = '{val}'")
                self.prompt_builder_values["lighting"] = val
            elif hasattr(self.lighting_entry, 'current'):
                idx = self.lighting_entry.current()
                if idx >= 0:
                    val = self.lighting_entry.get()
                    logger.debug(f"lighting_entry (combobox).get() = '{val}'")
                    self.prompt_builder_values["lighting"] = val
        
        # Setting
        if hasattr(self, 'setting_entry'):
            if hasattr(self.setting_entry, 'get'):
                val = self.setting_entry.get()
                logger.debug(f"setting_entry.get() = '{val}'")
                self.prompt_builder_values["setting"] = val
            elif hasattr(self.setting_entry, 'current'):
                idx = self.setting_entry.current()
                if idx >= 0:
                    val = self.setting_entry.get()
                    logger.debug(f"setting_entry (combobox).get() = '{val}'")
                    self.prompt_builder_values["setting"] = val
        
        # Atmosphere
        if hasattr(self, 'atmosphere_combo'):
            if hasattr(self.atmosphere_combo, 'get'):
                val = self.atmosphere_combo.get()
                logger.debug(f"atmosphere_combo.get() = '{val}'")
                self.prompt_builder_values["atmosphere"] = val
            elif hasattr(self.atmosphere_combo, 'current'):
                idx = self.atmosphere_combo.current()
                if idx >= 0:
                    val = self.atmosphere_combo.get()
                    logger.debug(f"atmosphere_combo (combobox).get() = '{val}'")
                    self.prompt_builder_values["atmosphere"] = val
        
        # Color - combine family and variation
        if hasattr(self, 'color_family_var') and hasattr(self.color_family_var, 'get'):
            family = self.color_family_var.get()
            variation = ""
            if hasattr(self, 'color_variation_var') and hasattr(self.color_variation_var, 'get'):
                variation = self.color_variation_var.get()
            if family and variation:
                val = f"{variation} {family}"
            else:
                val = family or variation
            logger.debug(f"color: family='{family}', variation='{variation}', combined='{val}'")
            self.prompt_builder_values["color"] = val
        
        logger.debug(f"prompt_builder_values = {self.prompt_builder_values}")
        subject = self.get_active_subject()
        setting = self.get_active_setting()
        style = self.get_active_style()
        lighting = self.get_active_lighting()
        mood = self.get_active_mood()
        color = self.get_active_color()
        atmosphere = self.get_active_atmosphere()
        mode = self.get_active_mode()
        subject_lock = self.get_active_subject_lock()

        # Check if audit mode is enabled
        run_audit = False
        if hasattr(self, 'prompt_audit_var'):
            run_audit = self.prompt_audit_var.get()

        # Clear template selection when generating from Quick Build
        self.prompt_source = "theme_builder"
        self._should_generate_image = False  # Flag to NOT trigger image generation
        if hasattr(self, 'template_var'):
            self.template_var.set("")

        self.status_var.set("Generating prompt...")

        # Generate prompt only
        keywords = [w for w in f"{subject} {setting} {style} {lighting} {mood} {color} {atmosphere}".split() if w]

        ui_values = {
            "subject": subject,
            "style": style,
            "lighting": lighting,
            "mood": mood,
            "color": color,
            "mode": mode,
            "atmosphere": atmosphere,
            "setting": setting
        }

        try:
            themes = generate_themes(
                count=1,
                user_keywords=keywords,
                subject_lock=subject_lock,
                custom_subject=subject,
                explicit_subject=subject,
                explicit_setting=setting,
                explicit_style=style,
                explicit_lighting=lighting,
                explicit_mood=mood,
                explicit_color=color,
                explicit_atmosphere=atmosphere,
            )

            if themes:
                prompts = build_all_prompts(themes, style_mode=mode, ui_values=ui_values, run_audit=run_audit)
                if prompts:
                    prompt_data = prompts[0]
                    text = f"{prompt_data['theme_sentence']}\n\nPROMPT:\n\n{prompt_data['prompt']}\n\nNegative prompt: {prompt_data.get('negative', '(none)')}"
                    self.set_prompt_text(text)
                    self.status_var.set("Prompt generated successfully.")
                else:
                    self.status_var.set("Failed to generate prompt.")
            else:
                self.status_var.set("Failed to generate themes.")
        except Exception as e:
            self.status_var.set(f"Error generating prompt: {e}")
            self._dialog.error("Error", f"Failed to generate prompt:\n\n{e}")



    def _generate_themes_thread(self, subject, setting, style, lighting, mood, color, atmosphere, mode, subject_lock, run_audit=False):

        try:
            logger.debug(f"_generate_themes_thread called with:")
            logger.info(f"  subject='{subject}'")
            logger.info(f"  setting='{setting}'")
            logger.info(f"  style='{style}'")
            logger.info(f"  lighting='{lighting}'")
            logger.info(f"  mood='{mood}'")
            logger.info(f"  color='{color}'")
            logger.info(f"  atmosphere='{atmosphere}'")
            logger.info(f"  mode='{mode}'")
            logger.info(f"  subject_lock={subject_lock}")
            logger.info(f"  run_audit={run_audit}")

            if self.cancel_event.is_set(): return

            # Values are already passed as parameters from sidebar widget reading
            # Don't overwrite them by reading from Prompt Builder Entry widgets

            keywords = [w for w in f"{subject} {setting} {style} {lighting} {mood} {color} {atmosphere}".split() if w]
            logger.debug(f"keywords = {keywords}")

            # Build UI values dict for audit
            ui_values = {
                "subject": subject,
                "style": style,
                "lighting": lighting,
                "mood": mood,
                "color": color,
                "mode": mode,
                "atmosphere": atmosphere,
                "setting": setting
            }

            # Time theme generation for perf tracking
            gen_start = time.perf_counter()
            themes = generate_themes(

                count=1,

                user_keywords=keywords,

                subject_lock=subject_lock,

                custom_subject=subject,

                explicit_subject=subject,

                explicit_setting=setting,

                explicit_style=style,

                explicit_lighting=lighting,

                explicit_mood=mood,

                explicit_color=color,

                explicit_atmosphere=atmosphere,

            )
            gen_elapsed = time.perf_counter() - gen_start
            
            if self.cancel_event.is_set(): return

            prompts = build_all_prompts(themes, style_mode=mode, ui_values=ui_values, run_audit=run_audit) if themes else []

            # Log timing for diagnostics
            logger.debug(f"Theme generation completed: {gen_elapsed:.2f}s")

            self.root.after(0, self._finish_generate_themes, themes, prompts, mode, None, ui_values)

        except Exception as e:
            import traceback
            error_details = f"{str(e)}\n\nTraceback:\n{traceback.format_exc()}"
            logger.error(f"[ERROR] Theme generation failed: {error_details}")
            self.root.after(0, self._finish_generate_themes, None, None, mode, error_details, None)



    def _show_generation_progress(self):
        """Show the generation progress bar overlay."""
        if hasattr(self, 'generation_progress'):
            logger.debug("Showing generation progress bar")
            self.generation_progress.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.5, relheight=0.1)
            self.generation_progress.lift()  # Bring to front
            self.generation_progress.start(10)  # Start indeterminate animation
            self.root.update_idletasks()  # Force UI update

    def _hide_generation_progress(self):
        """Hide the generation progress bar overlay (not the sidebar image_progress)."""
        if hasattr(self, 'generation_progress'):
            logger.debug("Hiding generation progress bar")
            self.generation_progress.stop()
            self.generation_progress.place_forget()
            self.root.update_idletasks()  # Force UI update
        # Do NOT hide the sidebar image_progress here - it's controlled separately

    def _finish_generate_themes(self, themes, prompts, mode, error_msg, ui_values=None):

        # Check if image generation will be triggered
        # If prompts exist and we're in generate mode (not prompt-only), image generation will follow
        # In that case, keep progress bar visible. Otherwise, hide it now.
        will_generate_image = (prompts and prompts[0] and
                                hasattr(self, 'prompt_source') and
                                self.prompt_source == "theme_builder" and
                                getattr(self, '_should_generate_image', False))

        if not will_generate_image:
            self.is_generating = False
            self._hide_generation_progress()
            # Only reset image generation progress UI when NOT generating image
            if self.image_progress.winfo_ismapped():
                self.image_progress.grid_remove()
                self.image_progress["value"] = 0
            if self.image_progress_overlay_label.winfo_ismapped():
                self.image_progress_overlay_label.config(text="")
        else:
            # Will generate image - ensure sidebar progress bar is visible
            if hasattr(self, 'image_progress'):
                self.image_progress.grid()
                self.image_progress["value"] = 0
                self.root.update_idletasks()

        if error_msg:

            self._dialog.error("Error", f"Preview generation failed.\n\n{error_msg}")

            self.status_var.set("Preview generation failed.")

            return



        self.themes = themes
        self.prompts = prompts
        self._last_ui_values = ui_values  # cache for audit display in show_prompt

        # Ensure theme_sentence reflects the source (quick_build vs template)
        for prompt in self.prompts:
            if self.prompt_source == "theme_builder":
                theme = next((t for t in themes if t['theme_id'] == prompt['theme_id']), None)
                if theme:
                    prompt['theme_sentence'] = theme['sentence']

        self.apply_negative_prompt_to_prompts()

        if self.prompts:
            self.current_prompt_data = self.prompts[0]
            self.show_prompt()

            # Display audit results if audit mode was enabled
            if ui_values and self.prompts and "audit_results" in self.prompts[0]:
                self._display_audit_results(self.prompts[0]["audit_results"], ui_values)

            self.status_var.set(f"Generated preview in {mode} mode.")

            # Trigger image generation after themes/prompts are generated
            # Only trigger if _should_generate_image flag is True (set by generate(), not generate_prompt_only)
            if self.prompts and self.prompts[0] and getattr(self, '_should_generate_image', False):
                prompt = self.prompts[0]['prompt']
                import datetime
                filename = ui_values.get('subject', 'frog') + '_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S') + '.png'
                logger.debug(f"Triggering image generation with prompt: {prompt[:100]}...")
                self.gen_future = self.executor.submit(
                    self._generate_image_thread,
                    prompt,
                    filename,
                    False,  # auto_set_wallpaper
                    ui_values.get('subject', 'frog'),
                    ui_values.get('style', ''),
                    ui_values  # Pass full ui_values to save prompt parameters
                )
        else:
            self.current_prompt_data = None
            self.clear_prompt()
            self.clear_image()
            self.status_var.set("No preview generated.")



    def show_prompt(self, event=None):
        data = self.current_prompt_data
        if not data:
            return
        mode = data.get("style_mode", self.current_mode())
        self.update_mode_badge(mode)
        neg = data.get("negative_prompt", "")

        # Include audit results in the prompt display if available
        audit_section = ""
        if "audit_results" in data and data["audit_results"]:
            try:
                from prompt_validator import format_audit_summary
                _ui_vals = getattr(self, '_last_ui_values', None)
                _comps = (self.themes[0].get("components", {}) if getattr(self, 'themes', None) else None)
                audit_section = "\n\n" + format_audit_summary(
                    data["audit_results"],
                    ui_values=_ui_vals,
                    components=_comps,
                    final_prompt=data.get("prompt"),
                )
            except ImportError:
                pass

        text = f"{data['theme_sentence']}\n\nPROMPT:\n\n{data['prompt']}\n\nNegative prompt: {neg or '(none)'}{audit_section}"
        self.set_prompt_text(text)


    def _display_audit_results(self, audit_results, ui_values):
        """Display audit results in a message box and log warnings."""
        try:
            from prompt_validator import get_audit_warnings, format_audit_summary
            warnings = get_audit_warnings(audit_results)

            # Log to console
            logger.info("\n" + "=" * 80)
            logger.info("PROMPT VARIABLE AUDIT RESULTS")
            logger.info("=" * 80)
            _comps = (self.themes[0].get("components", {}) if getattr(self, 'themes', None) else None)
            logger.info(format_audit_summary(audit_results, ui_values=ui_values, components=_comps, final_prompt=(self.current_prompt_data or {}).get('prompt')))
            logger.info("=" * 80 + "\n")

            # Show warnings in message box if any
            if warnings:
                warning_text = "Prompt Variable Audit Warnings:\n\n" + "\n".join(warnings)
                self._dialog.warning("Prompt Variable Audit", warning_text)
            else:
                # Show success message in status
                self.status_var.set("Generated preview. Audit: All variables present in prompt.")

        except ImportError:
            pass



    def save_prompts(self):

            if not self.prompts:

                self._dialog.info("Nothing to save", "Generate a preview first.")

                return

            existing = load_json_list(PROMPTS_LOG)

            image_path = str(self.last_image_path) if self.last_image_path else ""

            enriched = []

            for item in self.prompts:

                clone = dict(item)
                clone.pop("audit_results", None)

                if image_path and not clone.get("image_path"):

                    clone["image_path"] = image_path

                clone.setdefault("saved_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

                enriched.append(clone)

            save_json_list(PROMPTS_LOG, existing + enriched)

            self.status_var.set(f"✓ Saved {len(enriched)} prompt(s) to log.")



    def selected_prompt(self):
        return self.current_prompt_data



    def generate_selected_image(self):

            if not has_huggingface_token():

                self._dialog.error("Missing token", "Set HUGGINGFACE_TOKEN in your environment first.")

                return

            data = self.selected_prompt()

            if not data:

                self._dialog.info("No preview", "Generate a preview first.")

                return

            self.run_image_generation(

                data.get("prompt", ""), 

                data.get("theme_sentence", "prompt"), 

                data.get("style_mode", self.current_mode()),

                subject=data.get("subject"),

                art_style=data.get("art_style"),
                ui_values=self.current_prompt_data

            )



    def generate_and_set(self):
            """Set the current image as wallpaper without regenerating."""
            path = self.last_image_path or self.selected_gallery_path
            if not path:
                self._dialog.info("No image", "No image is currently loaded. Generate or select an image first.")
                return
            self.double_click_set_wallpaper(path)





    def load_favorites(self):
        return self._gallery_tab.load_favorites()




    def load_styled(self):
        return self._gallery_tab.load_styled()




    def _create_styled_card(self, img_path, index, pal, border):
        return self._gallery_tab._create_styled_card(img_path, index, pal, border)




    def load_manual(self):
        return self._gallery_tab.load_manual()


    def load_gallery_by_ratio(self, ratio_mode, tag_filter=None):
        return self._gallery_tab.load_gallery_by_ratio(ratio_mode, tag_filter)


    def _build_ratio_gallery_ui(self, filtered_images, ratio_mode, tag_filter):
        return self._gallery_tab._build_ratio_gallery_ui(filtered_images, ratio_mode, tag_filter)




    def _create_manual_card(self, img_path, index, pal, border):
        return self._gallery_tab._create_manual_card(img_path, index, pal, border)




    def _select_manual_image(self, path):
        return self._gallery_tab._select_manual_image(path)


    def _update_manual_highlight(self, selected_path):
        return self._gallery_tab._update_manual_highlight(selected_path)




    def _select_styled_image(self, path):
        return self._gallery_tab._select_styled_image(path)


    def _update_styled_highlight(self, selected_path):
        return self._gallery_tab._update_styled_highlight(selected_path)




    def favorite_current_prompt(self):
        return self._gallery_tab.favorite_current_prompt()




    def set_selected_favorite_as_wallpaper(self):
        return self._gallery_tab.set_selected_favorite_as_wallpaper()


    def cancel_generation(self):

        """Cancel any running generation tasks."""

        if not self.is_generating:

            return

            

        self.cancel_event.set()

        if self.gen_future:

            self.gen_future.cancel()

            

        self.is_generating = False
        self._hide_generation_progress()

        # Clear the status label
        self.image_generation_status_label.config(text="")
        self.status_var.set("Generation cancelled.")

        self.image_label.config(text="Generation cancelled", image="")

        self.preview_source_label.config(text="Cancelled")

        self.root.update_idletasks()



    def _update_progress_ui(self, value, text=None):

        """Update both the progress bar and the percentage label."""

        # Percentage calculation: Clamp value to 0-100

        val = max(0, min(100, int(value)))

        # Set progress bar value

        self.image_progress["value"] = val

        # Update label text for "how much is left" feeling

        display_text = text if text else "Generating Image..."
        self.image_progress_overlay_label.config(text=display_text)



    def _update_generation_timer(self):

            if not getattr(self, "is_generating", False) or getattr(self, "generation_cancelled", False):

                return


    def _update_image_generation_timer(self):
        """Timer function no longer needed - using simple label instead."""
        pass

    def run_image_generation(self, prompt, theme_sentence, style_mode="stylized", auto_set_wallpaper=False, subject=None, art_style=None, ui_values=None):

            if self.is_generating:

                self._dialog.info("Please wait", "An image is already being generated.")

                return

            self.generation_cancelled = False

            from wallpaper_generator import slugify_filename

            filename = slugify_filename(f"{theme_sentence}-{style_mode}")

            self.base_status_msg = f"Generating image in {style_mode} mode..."

            self.status_var.set(self.base_status_msg)

            self.update_mode_badge(style_mode)

            self.is_generating = True
            self._show_generation_progress()

            # Show image progress bar in sidebar
            if hasattr(self, 'image_progress'):
                logger.debug("Showing image_progress in sidebar")
                self.image_progress.grid()
                self.image_progress["value"] = 0
                self.root.update_idletasks()
            else:
                logger.debug("image_progress not found")

            self.cancel_event.clear()

            # Show the status label
            self.image_generation_status_label.config(text="🔄 Generating image...")

            self.image_label.config(text="Creating your wallpaper...", image="")

            self.preview_source_label.config(text=f"Generating image: {filename}")

            

            self.gen_future = self.executor.submit(

                self._generate_image_thread, 

                prompt, filename, auto_set_wallpaper, subject, art_style, ui_values

            )



    def _generate_image_thread(self, prompt, filename, auto_set_wallpaper, subject, art_style, ui_values=None):

            def status_cb(msg):

                def update():

                    self.base_status_msg = msg

                self.root.after(0, update)

            # Progress bar is already shown in _finish_generate_themes, no need to show here

            try:

                if self.cancel_event.is_set(): return

                from wallpaper_generator import generate_image

                # Get live dimensions from the UI dropdown, not stale config
                live_dims = self.get_current_dimensions() if hasattr(self, 'get_current_dimensions') else None

                image_path = generate_image(prompt, subject=subject, style=art_style, filename=filename, status_callback=status_cb, dimensions=live_dims)

                if self.cancel_event.is_set():

                    self.root.after(0, self._on_generation_cancelled)

                    return

                # Save prompt parameters with the generated image
                if image_path and ui_values:
                    try:
                        save_prompt_parameters(image_path, ui_values)
                    except Exception as e:
                        logger.error(f"[ERROR] Failed to save prompt parameters: {e}")

                self.root.after(0, self._on_generation_complete, image_path, auto_set_wallpaper, None)

            except Exception as e:

                if self.cancel_event.is_set():

                    self.root.after(0, self._on_generation_cancelled)

                    return

                self.root.after(0, self._on_generation_complete, None, False, str(e))



    def _on_generation_cancelled(self):

            self.is_generating = False
            self._hide_generation_progress()

            # Hide image progress bar in sidebar
            if hasattr(self, 'image_progress'):
                self.image_progress.grid_remove()
                self.image_progress["value"] = 0
            if hasattr(self, 'image_progress_overlay_label'):
                self.image_progress_overlay_label.config(text="")

            self.generation_cancelled = False

            # Clear the status label
            self.image_generation_status_label.config(text="")
            self.status_var.set("Image generation cancelled.")

            self.image_label.config(text="Generation cancelled", image="")

            self.preview_source_label.config(text="Cancelled")



    def _on_generation_complete(self, image_path, auto_set_wallpaper, error_msg):

            self.is_generating = False
            self._hide_generation_progress()

            # Hide image progress bar in sidebar
            if hasattr(self, 'image_progress'):
                self.image_progress.grid_remove()
                self.image_progress["value"] = 0
            if hasattr(self, 'image_progress_overlay_label'):
                self.image_progress_overlay_label.config(text="")

            # Clear the status label
            self.image_generation_status_label.config(text="")
            if error_msg:

                self._dialog.error("Error", f"Image generation failed.\n\n{error_msg}")

                self.status_var.set("Image generation failed.")

                self.image_label.config(text="Generation failed", image="")

                return

            if not image_path:

                self._dialog.error("Generation failed", "Could not generate image. Check your HUGGINGFACE_TOKEN environment variable.")

                self.status_var.set("Image generation failed.")

                self.image_label.config(text="Generation failed", image="")

                return

            self.last_image_path = Path(image_path)

            for item in self.prompts:

                item["image_path"] = str(self.last_image_path)

            self.load_image_preview(image_path)

            self.status_var.set(f"Generated: {self.last_image_path.name}")

            self.load_gallery()

            self.load_favorites()

            if auto_set_wallpaper:

                self.set_last_image_as_wallpaper()



    def set_last_image_as_wallpaper(self):

            if not WINDOWS:

                self._dialog.info("Windows only", "Automatic wallpaper setting only works on Windows.")

                return

            if not self.last_image_path:

                self._dialog.info("No image yet", "Generate an image first.")

                return

            self.status_var.set("Setting wallpaper...")

            self.root.update_idletasks()

            try:

                success = set_wallpaper(self.last_image_path)

            except Exception as e:

                self._dialog.error("Error", f"Could not set wallpaper.\n\n{e}")

                self.status_var.set("Wallpaper set failed.")

                return

            if success:

                self.status_var.set(f"Wallpaper set: {self.last_image_path.name}")
                self.slideshow.reset_timer()

                self._dialog.info("Done!", "Wallpaper set successfully!")

            else:

                self.status_var.set("Wallpaper could not be set.")

                self._dialog.warning("Warning", "Image generated, but Windows did not set it as wallpaper.")



    def load_image_preview(self, image_path):

            self.show_preview_in_left_panel(image_path, f"Generated image: {Path(image_path).name}")





    def set_prompt_text(self, text):

        self.prompt_text.config(state="normal")

        self.prompt_text.delete("1.0", tk.END)

        self.prompt_text.insert("1.0", text)

        self.prompt_text.config(state="disabled")

    def get_prompt_text(self):
        """Return the current generator prompt text."""
        try:
            return self.prompt_text.get("1.0", tk.END).strip()
        except Exception:
            return ""

    def clear_prompt(self):

            self.set_prompt_text("")



    def _get_app_icon_image(self):
        return self._tray_mgr._get_app_icon_image()


    def _build_tray_image(self):
        return self._tray_mgr._build_tray_image()




    def _start_tray(self):
        return self._tray_mgr._start_tray()




    def _stop_tray(self):
            """Stop the system tray icon — bulletproof version.

            Directly stops the pystray icon (with timeout) and nulls the ref.
            Called from both on_close and _quit_app.
            """
            if not PYSTRAY_AVAILABLE:
                return
            try:
                icon = getattr(self, '_tray_icon', None)
                if icon is not None:
                    import os, threading
                    # icon.stop() posts a message to the tray thread's hidden
                    # window and waits for the thread to join.  Use a timeout so
                    # we never hang here.
                    def _stop_with_timeout():
                        try:
                            icon.stop()
                        except Exception:
                            pass

                    t = threading.Thread(target=_stop_with_timeout, daemon=True)
                    t.start()
                    t.join(timeout=3)
                    self._tray_icon = None
            except Exception:
                pass




    def _toggle_minimize_to_tray(self, icon=None, item=None):
        return self._tray_mgr._toggle_minimize_to_tray(icon, item)




    def _tray_restore(self, icon=None, item=None):
        return self._tray_mgr._tray_restore(icon, item)




    def _tray_prev_wallpaper(self, icon=None, item=None):
        return self._tray_mgr._tray_prev_wallpaper(icon, item)




    def _tray_next_wallpaper(self, icon=None, item=None):
        return self._tray_mgr._tray_next_wallpaper(icon, item)




    def _tray_pause_slideshow(self, icon=None, item=None):
        return self._tray_mgr._tray_pause_slideshow(icon, item)


    def _tray_toggle_slideshow(self, icon=None, item=None):
        return self._tray_mgr._tray_toggle_slideshow(icon, item)


    def _tray_stop_slideshow(self, icon=None, item=None):
        return self._tray_mgr._tray_stop_slideshow(icon, item)


    def _tray_open_gallery(self, icon=None, item=None):
        return self._tray_mgr._tray_open_gallery(icon, item)


    def _tray_generate_prompt(self, icon=None, item=None):
        return self._tray_mgr._tray_generate_prompt(icon, item)


    def _tray_open_settings(self, icon=None, item=None):
        return self._tray_mgr._tray_open_settings(icon, item)


    def _tray_random_wallpaper(self, icon=None, item=None):
        return self._tray_mgr._tray_random_wallpaper(icon, item)


    def _restore_window(self):
        return self._tray_mgr._restore_window()




    def _tray_exit(self, icon=None, item=None):
        return self._tray_mgr._tray_exit(icon, item)




    def _show_about_dialog(self, icon=None, item=None):
        """Show About dialog from tray menu."""
        self.root.after(0, self._show_about_popup)

    def _show_toast(self, message, duration=3000, message_type="info"):
        """Show a toast notification message."""
        if self._toast_frame is None:
            self._init_toast_system()

        toast = tk.Frame(self._toast_frame, bg="#333333", relief="flat", bd=0)
        toast.pack(side="bottom", fill="x", padx=20, pady=10)

        # Color based on message type
        colors = {
            "info": "#4a90e2",
            "success": "#2ecc71",
            "warning": "#f39c12",
            "error": "#e74c3c"
        }
        bg_color = colors.get(message_type, "#4a90e2")

        # Left accent bar
        accent = tk.Frame(toast, bg=bg_color, width=4)
        accent.pack(side="left", fill="y")

        # Message label
        label = tk.Label(
            toast,
            text=message,
            bg="#333333",
            fg="#ffffff",
            font=self.smallfont,
            padx=15,
            pady=8,
            anchor="w"
        )
        label.pack(side="left", fill="both", expand=True)

        # Close button
        close_btn = tk.Label(
            toast,
            text="✕",
            bg="#333333",
            fg="#888888",
            font=self.tinyfont,
            padx=8,
            pady=8,
            cursor="hand2"
        )
        close_btn.pack(side="right")
        close_btn.bind("<Button-1>", lambda e: self._dismiss_toast(toast))

        # Auto-dismiss after duration
        self.root.after(duration, lambda: self._dismiss_toast(toast))

    def _switch_to_tab(self, tab_name):
        """Switch to a specific tab by name."""
        try:
            if tab_name == "gallery":
                self.notebook.select(self.gallery_tab)
            elif tab_name == "prompt_builder":
                self.notebook.select(self.prompt_builder_tab)
            elif tab_name == "settings":
                self._open_settings_window()
            # Note: Favorites is integrated into Gallery tab
        except Exception:
            pass

    def _handle_escape(self):
        """Handle Escape key - close settings or show toast."""
        if hasattr(self, "_settings_win") and self._settings_win and self._settings_win.winfo_exists():
            self._settings_win.destroy()
        else:
            self._show_toast("Press Ctrl+G for Gallery, Ctrl+P for Prompt Builder, Ctrl+S for Settings", message_type="info")

    def _init_toast_system(self):
        """Initialize the toast notification container."""
        self._toast_frame = tk.Frame(self.root, bg="")
        self._toast_frame.place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-10)
        self._toast_frame.lift()

    def _dismiss_toast(self, toast):
        """Dismiss a toast notification with fade effect."""
        try:
            toast.destroy()
        except:
            pass

    def _show_about_popup(self):
        """Display the About popup window with full theme support."""
        # Restore window if minimized to ensure popup appears
        if self.root.state() == "iconic":
            self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

        about_window = tk.Toplevel(self.root)
        about_window.title("About FrogPaper")
        about_window.geometry("400x260")
        about_window.minsize(360, 220)
        about_window.resizable(True, False)
        about_window.transient(self.root)
        about_window.grab_set()

        # Center the window
        about_window.update_idletasks()
        x = (about_window.winfo_screenwidth() // 2) - (400 // 2)
        y = (about_window.winfo_screenheight() // 2) - (260 // 2)
        about_window.geometry(f"+{x}+{y}")

        # Apply full theme styling
        pal = THEMES.get(self.current_theme_name, THEMES["darkforest"])
        about_window.configure(bg=pal["panel"])

        # Main container with fixed bottom button bar
        main_frame = tk.Frame(about_window, bg=pal["panel"])
        main_frame.pack(fill="both", expand=True)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=0)

        # Content area (scrollable/shrinkable)
        content_frame = tk.Frame(main_frame, bg=pal["panel"])
        content_frame.grid(row=0, column=0, sticky="nsew", padx=24, pady=(20, 8))
        content_frame.columnconfigure(0, weight=1)

        # Title with accent color
        title_label = tk.Label(
            content_frame,
            text="🐸 FrogPaper",
            font=("Segoe UI", 20, "bold"),
            bg=pal["panel"],
            fg=pal.get("accent", pal["text"])
        )
        title_label.pack(pady=(0, 8))

        # Subtitle
        tk.Label(
            content_frame,
            text="AI Wallpaper Generator",
            font=("Segoe UI", 12),
            bg=pal["panel"],
            fg=pal["text"]
        ).pack()

        # Description
        tk.Label(
            content_frame,
            text="Generate, style, and manage wallpapers from one app.",
            font=("Segoe UI", 10),
            bg=pal["panel"],
            fg=pal.get("muted", "#888"),
            wraplength=320
        ).pack(pady=(10, 14))

        # Version
        tk.Label(
            content_frame,
            text="Version 1.0",
            font=("Segoe UI", 10, "italic"),
            bg=pal["panel"],
            fg=pal.get("muted", "#888")
        ).pack()

        # Fixed bottom button bar
        btn_bar = tk.Frame(main_frame, bg=pal["panel2"], height=54)
        btn_bar.grid(row=1, column=0, sticky="ew")
        btn_bar.grid_propagate(False)
        btn_bar.columnconfigure(0, weight=1)

        ok_btn = tk.Button(
            btn_bar,
            text="OK",
            command=about_window.destroy,
            width=14,
            font=("Segoe UI", 10),
            bg=pal.get("accent", pal["progress"]),
            fg=pal["text"],
            activebackground=pal.get("surface", pal["panel"]),
            activeforeground=pal["text"],
            relief="flat",
            cursor="hand2"
        )
        ok_btn.place(relx=0.5, rely=0.5, anchor="center")



    # ── Fullscreen slideshow pause ─────────────────────────────────────────

    def _on_pause_fullscreen_toggle(self):
        if self.slideshow_pause_on_fullscreen_var.get():
            self._start_fullscreen_watcher()
        else:
            self._stop_fullscreen_watcher()
            if self._fullscreen_was_detected and self.slideshow.running and self.slideshow.paused:
                self.slideshow.resume()
                self._fullscreen_was_detected = False
                self.status_var.set('Fullscreen mode ended — slideshow resumed.')

    def _start_fullscreen_watcher(self):
        self._stop_fullscreen_watcher()
        self._fullscreen_check_loop()

    def _stop_fullscreen_watcher(self):
        if self._fullscreen_check_job is not None:
            try:
                self.root.after_cancel(self._fullscreen_check_job)
            except Exception:
                pass
            self._fullscreen_check_job = None
        self._fullscreen_was_detected = False

    def _fullscreen_check_loop(self):
        if not self.slideshow_pause_on_fullscreen_var.get():
            self._fullscreen_check_job = None
            return
        try:
            is_fs = _is_foreground_window_fullscreen()
            if is_fs and not self._fullscreen_was_detected:
                self._fullscreen_was_detected = True
                if self.slideshow.running and not self.slideshow.paused:
                    self.slideshow.pause()
                    self.status_var.set('Fullscreen app detected — slideshow paused.')
            elif not is_fs and self._fullscreen_was_detected:
                self._fullscreen_was_detected = False
                if self.slideshow.running and self.slideshow.paused:
                    self.slideshow.resume()
                    self.status_var.set('Fullscreen mode ended — slideshow resumed.')
        except Exception:
            pass
        self._fullscreen_check_job = self.root.after(3000, self._fullscreen_check_loop)

    def _add_fullscreen_setting(self, parent):
        """Find the 'Skip duplicates' checkbox and add 'Pause on fullscreen' below it.
        Called after settings_tab builds its UI."""
        try:
            # Walk all children to find the Gallery & Slideshow frame
            for widget in parent.winfo_children():
                for child in widget.winfo_children():
                    for grandchild in child.winfo_children():
                        for gc2 in grandchild.winfo_children():
                            try:
                                txt = gc2.cget('text') if hasattr(gc2, 'cget') else ''
                                if 'Skip duplicates' in str(txt):
                                    # Found it — shift all rows below this one down by 2 FIRST
                                    row_info = gc2.grid_info()
                                    r = row_info.get('row', 0)
                                    p = gc2.master
                                    # Shift existing widgets down before inserting new ones
                                    for w in p.winfo_children():
                                        info = w.grid_info()
                                        if not info:
                                            continue
                                        wr = info.get('row', 0)
                                        if wr > r:
                                            w.grid(row=wr + 2)
                                    # Now insert into the cleared rows
                                    ttk.Checkbutton(p, text='Pause when a full-screen app is active',
                                                    variable=self.slideshow_pause_on_fullscreen_var,
                                                    command=self._on_pause_fullscreen_toggle).grid(
                                        row=r+1, column=0, columnspan=2, sticky='w', pady=(0, 2))
                                    ttk.Label(p, text='Auto-pauses slideshow while games, videos, or presentations are full-screen',
                                              font=self.small_font, foreground='#666666', wraplength=620).grid(
                                        row=r+2, column=0, columnspan=2, sticky='w', pady=(0, 6))
                                    return
                            except Exception:
                                pass
        except Exception:
            pass

    def _quit_app(self):

            """Fully quit the application (used by tray exit)."""

            self._stop_fullscreen_watcher()
            self.slideshow.stop()

            self._stop_tray()

            self._shutdown_db()

            try:
                self.root.destroy()
            except Exception:
                pass

            # Force-kill the process so non-daemon threads (tray) cannot keep it alive.
            # sys.exit() only raises SystemExit in the calling thread; the tray
            # thread (daemon=False) would keep the process running.
            import os
            os._exit(0)

    

    def _on_minimize_to_tray_changed(self):

        """Handle minimize-to-tray setting change."""

        new_value = self.minimize_to_tray_var.get()

        

        # Update setting

        self.minimize_to_tray_enabled = new_value

        config = load_config()

        config['minimize_to_tray'] = new_value

        save_config(config)

        

        # Update tray menu if it exists

        if hasattr(self, '_tray_icon') and self._tray_icon:

            try:

                # Force menu update to reflect new checked state

                self._tray_icon.update_menu()

            except Exception as e:

                logger.error(f"Error updating tray menu: {e}")



    def _get_startup_registry(self) -> bool:
        """Return True if FrogPaper is registered in the Windows startup registry key."""
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_READ
            )
            try:
                winreg.QueryValueEx(key, "FrogPaper")
                return True
            except FileNotFoundError:
                return False
            finally:
                winreg.CloseKey(key)
        except Exception:
            return False

    def _set_startup_registry(self, enable: bool):
        """Add or remove FrogPaper from the Windows startup registry key."""
        try:
            import winreg
            import sys
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE
            )
            if enable:
                exe_path = sys.executable if getattr(sys, 'frozen', False) else sys.executable
                if getattr(sys, 'frozen', False):
                    # Running as PyInstaller EXE
                    target = f'"{sys.executable}"'
                else:
                    # Running as script — launch via python
                    import __main__
                    script = getattr(__main__, '__file__', None) or 'app.py'
                    target = f'"{sys.executable}" "{script}"'
                winreg.SetValueEx(key, "FrogPaper", 0, winreg.REG_SZ, target)
            else:
                try:
                    winreg.DeleteValue(key, "FrogPaper")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            logger.error(f"[Startup] Registry error: {e}")

    def _on_run_on_startup_changed(self):
        """Handle run-on-startup toggle."""
        new_value = self.run_on_startup_var.get()
        self.run_on_startup_enabled = new_value
        self._set_startup_registry(new_value)
        state = "enabled" if new_value else "disabled"
        self.status_var.set(f"Run on startup {state}.")



    def _on_minimize(self, event=None):

        """Handle window minimize event — keep taskbar button; start tray if enabled."""

        # Only trigger if window is actually being minimized (state is "iconic").
        # Do NOT withdraw — that removes the taskbar button.
        # Stay iconic so the taskbar entry remains; only add the tray icon.
        if self.minimize_to_tray_enabled and self.root.state() == "iconic":

            self._start_tray()



    def advance_slideshow(self):

        """Advance slideshow with single step and debounce."""

        # Debounce: only allow one advance per second

        current_time = time.time()

        if not hasattr(self, '_last_advance_time'):

            self._last_advance_time = 0

        

        if current_time - self._last_advance_time < 1.0:  # 1 second debounce

            return  # Ignore rapid clicks

        

        self._last_advance_time = current_time

        self.slideshow.advance_once()  # Use advance_once instead of next_now for single step



def _acquire_single_instance_mutex():
    """Create a named Windows mutex to enforce a single running instance.
    Returns the mutex handle on success, or None if another instance is already running."""
    import ctypes
    mutex = ctypes.windll.kernel32.CreateMutexW(None, True, "FrogPaper_SingleInstance_Mutex")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        ctypes.windll.kernel32.CloseHandle(mutex)
        return None
    return mutex

def _release_mutex(mutex):
    """Release the mutex handle."""
    if mutex:
        import ctypes
        ctypes.windll.kernel32.CloseHandle(mutex)


def main():

        mutex = _acquire_single_instance_mutex()
        if mutex is None:
            import tkinter as _tk
            _r = _tk.Tk()
            _r.withdraw()
            from tkinter import messagebox as _mb
            _mb.showwarning(
                "FrogPaper Already Running",
                "FrogPaper is already open.\n\nCheck your taskbar or system tray."
            )
            _r.destroy()
            return

        try:
            root = tk.Tk()

            app = FrogPaperApp(root)

            app.update_mode_badge()

            app.refresh_token_status()

            # Auto-generate a fresh wallpaper on startup if enabled
            if app.auto_generate_on_startup_var.get():
                def _startup_generate():
                    # Use the configured startup subject from settings (defaults to "frog")
                    subject = app.startup_subject_var.get().strip() or "frog"
                    app.set_active_subject(subject)
                    # Randomize everything except subject
                    import random as _rng
                    import time
                    _rng.seed(int(time.time() * 1000))  # Ensure different random values each time
                    settings = [o for o in THEME_VARIABLE_OPTIONS["setting"] if o]
                    styles = [o for o in THEME_VARIABLE_OPTIONS["style"] if o]
                    lightings = [o for o in THEME_VARIABLE_OPTIONS["lighting"] if o]
                    moods = [o for o in THEME_VARIABLE_OPTIONS["mood"] if o]
                    atmospheres = [o for o in THEME_VARIABLE_OPTIONS.get("atmosphere", []) if o]
                    color_families = [f for f in COLOR_FAMILIES if f]
                    family = _rng.choice(color_families)
                    variation = _rng.choice(COLOR_VARIATIONS)
                    color_value = f"{variation} {family}".strip() if variation else family
                    random_setting = _rng.choice(settings)
                    random_style = _rng.choice(styles)
                    random_lighting = _rng.choice(lightings)
                    random_mood = _rng.choice(moods)
                    random_atmosphere = _rng.choice(atmospheres)
                    random_mode = _rng.choice(STYLE_MODES)

                    # Apply random values to both sidebar and PB Quick Build widgets
                    app.set_active_setting(random_setting)
                    app.set_active_style(random_style)
                    app.set_active_lighting(random_lighting)
                    app.set_active_mood(random_mood)
                    app.set_active_color(color_value)
                    app.set_active_atmosphere(random_atmosphere)
                    app.set_active_mode(random_mode)

                    # Also update sidebar widgets directly to ensure they have the random values
                    if hasattr(app, 'setting_entry'):
                        app.setting_entry.delete(0, tk.END)
                        app.setting_entry.insert(0, random_setting)
                    if hasattr(app, 'style_entry'):
                        app.style_entry.delete(0, tk.END)
                        app.style_entry.insert(0, random_style)
                    if hasattr(app, 'lighting_entry'):
                        app.lighting_entry.delete(0, tk.END)
                        app.lighting_entry.insert(0, random_lighting)
                    if hasattr(app, 'mood_entry'):
                        app.mood_entry.delete(0, tk.END)
                        app.mood_entry.insert(0, random_mood)
                    # Update color family and color variation sidebar widgets
                    if hasattr(app, 'color_family_var'):
                        app.color_family_var.set(family)
                    if hasattr(app, 'color_variation_var'):
                        app.color_variation_var.set(variation)
                    # Update atmosphere sidebar widget
                    if hasattr(app, 'atmosphere_var'):
                        app.atmosphere_var.set(random_atmosphere)
                    # Update mode sidebar widget directly
                    if hasattr(app, 'mode_var'):
                        app.mode_var.set(random_mode)

                    app.update_mode_badge()

                    # Force UI update before generation
                    app.root.update()

                    app.generate(show_progress=False)  # This generates themes/prompts AND the image
                root.after(2000, _startup_generate)

            root.mainloop()
        finally:
            _release_mutex(mutex)



if __name__ == "__main__":

        main()




