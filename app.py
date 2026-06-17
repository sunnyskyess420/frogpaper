import tkinter as tk

import os

import shutil

import tkinter.font as tkfont

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



DEFAULT_NEGATIVE_PROMPT = (
    "text, watermark, logo, signature, blurry, low quality, cropped, "
    "low resolution, pixelated, grainy, noisy, jpeg artifacts, "
    "bad anatomy, deformed, malformed, mutated, disfigured"
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
COLOR_FAMILIES = [
    "",
    # — Core —
    "gold", "silver", "white", "black",
    # — Blues & Purples —
    "blue", "navy", "cobalt", "sapphire", "indigo", "violet",
    "purple", "lavender", "lilac", "mauve", "periwinkle",
    # — Reds & Pinks —
    "red", "crimson", "scarlet", "burgundy", "maroon",
    "pink", "rose", "magenta", "fuchsia", "salmon", "coral",
    # — Greens —
    "green", "emerald", "jade", "forest green", "lime",
    "mint", "olive", "sage", "teal", "cyan",
    # — Oranges & Yellows —
    "orange", "amber", "apricot", "bronze",
    "yellow", "golden", "lemon", "mustard",
    # — Neutrals & Earth —
    "earth", "brown", "tan", "beige", "sand", "ivory",
    "slate", "charcoal", "ash", "stone",
    # — Special —
    "rainbow", "holographic", "chrome", "obsidian",
    "midnight", "void", "plasma", "toxic",
]
COLOR_VARIATIONS = [
    "",
    # — Intensity —
    "rich", "deep", "dark", "light", "bright", "vivid",
    "vibrant", "bold", "pale", "faded", "muted", "soft",
    # — Temperature —
    "cool", "warm", "icy", "fiery",
    # — Texture & Finish —
    "metallic", "iridescent", "translucent", "fluorescent",
    "glossy", "matte", "satin", "pearlescent", "crystalline",
    "holographic", "opalescent", "frosted", "burnished",
    # — Aesthetic —
    "pastel", "electric", "neon", "dusty", "sepia", "monochrome",
    "washed out", "oversaturated", "desaturated", "vintage",
    "earthy", "moody", "dreamy", "smoky", "hazy",
]

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


# ──── Model options and display to ID mapping ────────────────────────────

MODEL_OPTIONS = [

    "FLUX.1-schnell (Fastest & Free)",

    "FLUX.1-dev (High Quality - Pro Only)",

    "Stable Diffusion XL (Standard)",

    "Stable Diffusion 3.5 Large (Pro Only)",

    "Custom...",

]



MODEL_DISPLAY_TO_ID = {

    "FLUX.1-schnell (Fastest & Free)": "black-forest-labs/FLUX.1-schnell",

    "FLUX.1-dev (High Quality - Pro Only)": "black-forest-labs/FLUX.1-dev",

    "Stable Diffusion XL (Standard)": "stabilityai/stable-diffusion-xl-base-1.0",

    "Stable Diffusion 3.5 Large (Pro Only)": "stabilityai/stable-diffusion-3.5-large",

}



# Reverse mapping for loading

MODEL_ID_TO_DISPLAY = {v: k for k, v in MODEL_DISPLAY_TO_ID.items()}

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

# Fixed card height used for lazy gallery rendering (thumb 135 + name + tags + padding)
_GALLERY_CARD_H = 195



DIMENSION_PRESETS = {
    "16:9 (1080p)": "1920x1080",
    "4K (16:9)": "3840x2160",
    "Ultrawide": "3440x1440",
    "Portrait": "1080x1920",
    "Square": "1024x1024",
}



# Shared variable options for Theme Builder and Template Builder
# ── Setting (locations, structures, environments) ─────────────────────────
_BASE_SETTING_OPTIONS = [
    "",
    # — Nature & Wilderness —
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
    # — Fantasy & Magic —
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
    # — Sci-Fi & Futuristic —
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
    # — Urban & Interior —
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
    # — Historical & Cultural —
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
    # — Surreal & Abstract —
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
]

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
    "axolotl",
    # — Animals & Creatures —
    "cat",
    "wolf",
    "fox",
    "owl",
    "raven",
    "tiger",
    "panther",
    "bear",
    "stag",
    "octopus",
    "jellyfish swarm",
    "giant spider",
    "koi fish",
    "peacock",
    "baroque peacock",
    "robot wolf",
    "mechanical horse",
    "neon butterfly",
    "glowing deer",
    "ghost whale",
    "iron golem",
    "crystal serpent",
    "shadow panther",
    "bioluminescent deep sea creature",
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

_BASE_STYLE_OPTIONS = [
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
]

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

_BASE_LIGHTING_OPTIONS = [
    "",
    # — Natural Light —
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
    # — Artificial & Studio —
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
    # — Cinematic & Stylized —
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
    # — Magical & Sci-Fi —
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
]

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

_BASE_MOOD_OPTIONS = [
    "",
    # — Positive & Uplifting —
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
    # — Dark & Intense —
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
    # — Emotional & Reflective —
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
    # — Energetic & Electric —
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
    # — Aesthetic & Vibe —
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
]

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

_BASE_ATMOSPHERE_OPTIONS = [
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
]

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



class ThemedDialog:
    """Themed replacements for tkinter.messagebox dialogs.

    Usage (inside FrogPaperApp):
        self._dialog.info("Title", "Message")
        self._dialog.warning("Title", "Message")
        self._dialog.error("Title", "Message")
        result = self._dialog.ask("Title", "Question")  # returns True/False
    """

    _ICONS = {
        "info":    "ℹ️",
        "warning": "⚠️",
        "error":   "❌",
        "ask":     "❓",
    }

    def __init__(self, app):
        self._app = app

    def _pal(self):
        theme = getattr(self._app, "current_theme_name", "darkforest")
        return THEMES.get(theme, THEMES["darkforest"])

    def _show(self, kind: str, title: str, message: str, buttons=("OK",)) -> str:
        pal = self._pal()
        accent = pal.get("accent", pal["progress"])

        dlg = tk.Toplevel(self._app.root)
        dlg.title(title)
        dlg.configure(bg=pal["bg"])
        dlg.resizable(False, False)
        dlg.grab_set()

        # Center over parent
        dlg.update_idletasks()
        pw = self._app.root.winfo_width()
        ph = self._app.root.winfo_height()
        px = self._app.root.winfo_rootx()
        py = self._app.root.winfo_rooty()
        w, h = 380, 160 + message.count("\n") * 16
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        dlg.geometry(f"{w}x{h}+{x}+{y}")

        result = tk.StringVar(value=buttons[-1])

        # Icon + message
        top = tk.Frame(dlg, bg=pal["bg"], padx=18, pady=14)
        top.pack(fill="x")
        icon_lbl = tk.Label(top, text=self._ICONS.get(kind, "ℹ️"),
                            font=("Segoe UI Emoji", 22),
                            bg=pal["bg"], fg=pal["text"])
        icon_lbl.pack(side="left", padx=(0, 12))
        msg_lbl = tk.Label(top, text=message, wraplength=w - 90,
                           justify="left", bg=pal["bg"], fg=pal["text"],
                           font=("Segoe UI", 10))
        msg_lbl.pack(side="left", fill="x", expand=True)

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

        self.root.title("FrogPaper")

        # Set window / taskbar icon using the shared icon loader
        try:
            from PIL import ImageTk
            self.icon_img = ImageTk.PhotoImage(self._get_app_icon_image())
            self.root.iconphoto(True, self.icon_img)
        except Exception:
            pass

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

        # Minimize to tray setting
        self.minimize_to_tray_enabled = load_config().get("minimize_to_tray", True)

        # Run on startup setting (read actual registry state as source of truth)
        self.run_on_startup_enabled = self._get_startup_registry()

        _t0 = time.perf_counter()
        self.build_ui()
        print(f"[STARTUP] build_ui: {time.perf_counter()-_t0:.2f}s")

        _t1 = time.perf_counter()
        self.load_favorites()
        print(f"[STARTUP] load_favorites: {time.perf_counter()-_t1:.2f}s")

        _t2 = time.perf_counter()
        self.load_presets()
        self.load_slideshow_settings()
        self.load_remembered_settings()
        print(f"[STARTUP] config/presets/settings: {time.perf_counter()-_t2:.2f}s")

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.bind("<Unmap>", self._on_minimize)
        self.root.bind("<F11>", self.toggle_fullscreen)

        # Global Hotkey (Ctrl+Alt+N for next wallpaper)
        if KEYBOARD_AVAILABLE:
            try:
                keyboard.add_hotkey('ctrl+alt+n', self.advance_slideshow)
            except:
                pass

        _t3 = time.perf_counter()
        self.apply_theme(load_config().get("app_theme", "darkforest"))
        print(f"[STARTUP] apply_theme: {time.perf_counter()-_t3:.2f}s")
        print(f"[STARTUP] total sync init: {time.perf_counter()-_t0:.2f}s")

        self.status_var.set("Loading gallery…")
        self.root.after(1, self._deferred_startup_load)

        # Start minimized to tray by default on every launch - never show window initially
        if PYSTRAY_AVAILABLE:
            if self._start_tray():
                # Always withdraw window on startup - only show when user clicks tray icon
                self.root.withdraw()
            else:
                # If tray fails to start, ensure window is visible
                self.root.deiconify()
                self.root.state("normal")
        else:
            # If pystray is not installed, keep window visible
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
            # 0. Pre-warm prompt generation pipeline (eliminates first-prompt cold-start delay)
            try:
                from theme_mixer import load_keywords, get_lazy_keyword_expander
                load_keywords()
                get_lazy_keyword_expander()
            except Exception as e:
                print(f"[STARTUP] keyword warmup skipped: {e}")
            print(f"[STARTUP] keyword warmup: {time.perf_counter()-_t:.2f}s")

            # 1. migrate saved image paths (rglob scan — was blocking main thread)
            try:
                updated_h, updated_f = self.migrate_saved_image_paths()
            except Exception:
                updated_h = updated_f = 0
            print(f"[STARTUP] migrate_saved_image_paths: {time.perf_counter()-_t:.2f}s")

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
            print(f"[STARTUP] collect+sort wallpapers ({len(raw_images)} files): {time.perf_counter()-_t2:.2f}s")

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
            print(f"[STARTUP] gallery UI populate: {time.perf_counter()-_t:.2f}s")
            # Pre-warm theme generation after another 1.5s
            self.status_var.set("Warming up prompt engine — first prompt ready in a moment...")
            self.root.after(1500, self._warmup_theme_generation)

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
                print(f"[PERF] Theme generation warmup complete: {warmup_total:.2f}s (theme gen: {elapsed:.2f}s)")
                self.root.after(0, lambda: self.status_var.set("Ready — prompt engine warm."))
            except Exception as e:
                print(f"[PERF] Warmup error: {e}")
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
            background=[("active", pal["button_hover"]), ("pressed", pal["tabsel"])],
        )

        style.configure("Active.TButton",
            background=pal["progress"],
            foreground=pal["button_fg"],
            relief="flat",
            borderwidth=0,
            padding=(8, 5),
        )
        style.map("Active.TButton",
            background=[("active", pal["button_hover"]), ("pressed", pal["tabsel"])],
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
        for attr in ("title_label", "_sidebar_ar_lbl",
                      "_sidebar_style_lbl",
                      "_sidebar_lighting_lbl", "_sidebar_color_lbl",
                      "_sidebar_subj_lbl", "_sidebar_setting_lbl",
                      "_sidebar_vstyle_lbl", "_sidebar_atm_lbl",
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

        # App title
        self.title_label = tk.Label(left, text="FrogPaper", anchor="w", justify="left")
        self.title_label.configure(font=self.title_font)
        self.title_label.pack(fill="x", pady=(0, 14))

        # Aspect Ratio
        ar_lbl = tk.Label(left, text="Aspect Ratio", anchor="w")
        ar_lbl.configure(font=self.bold_font)
        ar_lbl.pack(fill="x", pady=(0, 4))
        self._sidebar_ar_lbl = ar_lbl

        ar_frame = ttk.Frame(left)
        ar_frame.pack(fill="x", pady=(0, 10))
        self.dimension_preset_var = tk.StringVar(value="16:9 (1080p)")
        for txt, val in [("16:9", "16:9 (1080p)"), ("21:9", "21:9 Ultrawide"), ("4:3", "4:3 Standard")]:
            ttk.Radiobutton(ar_frame, text=txt, variable=self.dimension_preset_var,
                            value=val).pack(side="left", padx=(0, 10))

        # Style dropdown
        style_lbl = tk.Label(left, text="Style", anchor="w")
        style_lbl.configure(font=self.bold_font)
        style_lbl.pack(fill="x", pady=(0, 2))
        self._sidebar_style_lbl = style_lbl

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
        self.color_family_var = tk.StringVar(value="")
        self.color_family_combo = ttk.Combobox(color_frame, textvariable=self.color_family_var,
                                               values=COLOR_FAMILIES, state="readonly", width=14)
        self.color_family_combo.pack(side="left", padx=(0, 6))
        self.color_family_combo.bind("<MouseWheel>", lambda e: "break")
        self.color_variation_var = tk.StringVar(value="")
        self.color_variation_combo = ttk.Combobox(color_frame, textvariable=self.color_variation_var,
                                                  values=COLOR_VARIATIONS, state="readonly", width=14)
        self.color_variation_combo.pack(side="left")
        self.color_variation_combo.bind("<MouseWheel>", lambda e: "break")

        # Subject
        subj_lbl = tk.Label(left, text="Subject", anchor="w")
        subj_lbl.configure(font=self.bold_font)
        subj_lbl.pack(fill="x", pady=(0, 2))
        self._sidebar_subj_lbl = subj_lbl
        self.subject_entry = ttk.Combobox(left, values=THEME_VARIABLE_OPTIONS["subject"])
        self.subject_entry.pack(fill="x", pady=(0, 10))
        self.subject_entry.insert(0, "frog")
        self.subject_entry.bind("<MouseWheel>", lambda e: "break")

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

        # Visual style
        vstyle_lbl = tk.Label(left, text="Visual Style", anchor="w")
        vstyle_lbl.configure(font=self.bold_font)
        vstyle_lbl.pack(fill="x", pady=(0, 2))
        self._sidebar_vstyle_lbl = vstyle_lbl
        self.style_entry = ttk.Combobox(left, values=THEME_VARIABLE_OPTIONS["style"])
        self.style_entry.pack(fill="x", pady=(0, 10))
        self.style_entry.insert(0, "cyberpunk")
        self.style_entry.bind("<MouseWheel>", lambda e: "break")

        # Atmosphere
        atm_lbl = tk.Label(left, text="Atmosphere", anchor="w")
        atm_lbl.configure(font=self.bold_font)
        atm_lbl.pack(fill="x", pady=(0, 2))
        self._sidebar_atm_lbl = atm_lbl
        first_atmosphere = [opt for opt in THEME_VARIABLE_OPTIONS.get("atmosphere", []) if opt]
        default_atm = first_atmosphere[0] if first_atmosphere else ""
        self.atmosphere_var = tk.StringVar(value=default_atm)
        self.atmosphere_combo = ttk.Combobox(left, textvariable=self.atmosphere_var,
                                             values=THEME_VARIABLE_OPTIONS.get("atmosphere", [""]),
                                             state="readonly")
        self.atmosphere_combo.pack(fill="x", pady=(0, 10))
        self.atmosphere_combo.bind("<MouseWheel>", lambda e: "break")

        # Negative prompt
        neg_lbl = tk.Label(left, text="Negative Prompt", anchor="w")
        neg_lbl.configure(font=self.bold_font)
        neg_lbl.pack(fill="x", pady=(0, 2))
        self._sidebar_neg_lbl = neg_lbl
        self.negative_prompt_var = tk.StringVar(value=DEFAULT_NEGATIVE_PROMPT)
        self.negative_prompt_entry = ttk.Entry(left, textvariable=self.negative_prompt_var)
        self.negative_prompt_entry.pack(fill="x", pady=(0, 10))

        # Subject lock checkbox
        self.subject_lock_var = tk.BooleanVar(value=True)
        self.subject_lock_check = ttk.Checkbutton(left, text="Keep Typed Subject Literal",
                                                   variable=self.subject_lock_var)
        self.subject_lock_check.pack(fill="x", pady=(0, 4))

        # Generate Prompt button — same styling as Generate Image
        gen_prompt_btn = tk.Button(left, text="Generate Prompt", cursor="hand2",
                                   relief="flat", bd=0, padx=20, pady=10,
                                   command=self.generate_prompt_only)
        gen_prompt_btn.configure(font=tkfont.Font(family="Segoe UI", size=12, weight="bold"))
        gen_prompt_btn.pack(fill="x", pady=(8, 4), ipady=4)
        self._generate_prompt_btn = gen_prompt_btn

        # Generate Image button — below Generate Prompt
        gen_img_btn = tk.Button(left, text="Generate Image", cursor="hand2",
                                relief="flat", bd=0, padx=20, pady=10,
                                command=self.generate)
        gen_img_btn.configure(font=tkfont.Font(family="Segoe UI", size=12, weight="bold"))
        gen_img_btn.pack(fill="x", pady=(4, 8), ipady=4)
        self._generate_btn = gen_img_btn

        # Quick action + utility buttons grid (2 columns, auto-width)
        btn_grid = ttk.Frame(left)
        btn_grid.pack(fill="x", pady=(0, 8))
        btn_grid.columnconfigure(0, weight=1)
        btn_grid.columnconfigure(1, weight=1)
        ttk.Button(btn_grid, text="🎰 Random",
                   command=self.random_theme).grid(row=0, column=0, sticky="ew", padx=(0, 3), pady=(0, 3))
        ttk.Button(btn_grid, text="❌ Cancel",
                   command=self.cancel_generation).grid(row=0, column=1, sticky="ew", pady=(0, 3))
        ttk.Button(btn_grid, text="⚙ Settings",
                   command=self._open_settings_window).grid(row=1, column=0, sticky="ew", padx=(0, 3), pady=(0, 3))
        ttk.Button(btn_grid, text="💾 Save Session",
                   command=self.save_session).grid(row=1, column=1, sticky="ew", pady=(0, 3))
        ttk.Button(btn_grid, text="📂 Load Session",
                   command=self.load_session).grid(row=2, column=0, columnspan=2, sticky="ew")

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
        self._center_style_btn = ttk.Menubutton(center_tabs, text="🎨 Apply Style")
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

        # Progress bar (above prompt preview)
        progress_frame = ttk.Frame(center, height=24)
        progress_frame.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        progress_frame.grid_propagate(False)
        progress_frame.columnconfigure(0, weight=1)
        progress_frame.rowconfigure(0, weight=1)
        self.progress = ttk.Progressbar(progress_frame, mode="determinate", maximum=100)
        self.progress.grid(row=0, column=0, sticky="nsew")
        self.progress.grid_remove()
        self.progress_overlay_label = tk.Label(progress_frame, text="", font=self.bold_font, anchor="center")
        self.progress_overlay_label.place(relx=0.5, rely=0.5, anchor="center")
        self.progress_overlay_label.place_forget()

        # Prompt preview (below progress)
        preview_frame = ttk.LabelFrame(center, text="Prompt Preview", padding=(8, 4))
        preview_frame.grid(row=3, column=0, sticky="ew", pady=(6, 0))
        preview_frame.columnconfigure(0, weight=1)

        badge_frame = ttk.Frame(preview_frame)
        badge_frame.grid(row=0, column=0, sticky="ew", pady=(0, 2))
        badge_frame.columnconfigure(0, weight=1)

        self.mode_badge = ttk.Label(badge_frame,
                                    text=f"Mode: {DEFAULT_PROMPT_MODE_LABEL} | Subject lock: ON")
        self.mode_badge.grid(row=0, column=0, sticky="w")

        ttk.Button(badge_frame, text="📋 Copy Prompt", width=18,
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
        
        ttk.Button(button_frame, text="📂 Open Folder", width=18,
                   command=self._open_wallpapers_folder).pack(side="left", padx=(0, 4))
        ttk.Button(button_frame, text="🔄 Refresh Gallery", width=18,
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

        # Gallery Controls — contains view selector, filters, sort, and action buttons
        filter_frame = ttk.LabelFrame(parent, text="Gallery Controls", padding=5)

        filter_frame.pack(fill='x', pady=(0, 8))

        # Row 0: Action buttons
        action_row = ttk.Frame(filter_frame)
        action_row.pack(fill='x', pady=(0, 4))
        self._gallery_action_row = action_row  # saved for view-switch repack

        _btn_wallpaper = ttk.Button(action_row, text="🖼️ Set as Wallpaper",
                   command=self._gallery_set_wallpaper)
        _btn_wallpaper.pack(side="left", padx=(0, 6))

        self._btn_save_to_fav = ttk.Button(action_row, text="⭐ Save to Favorites",
                   command=self._gallery_save_to_favorites)
        self._btn_save_to_fav.pack(side="left", padx=(0, 6))

        self.style_menu_btn = ttk.Menubutton(action_row, text="🎨 Apply Style")
        self.style_menu = tk.Menu(self.style_menu_btn, tearoff=0)
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
            self.style_menu.add_command(label=display_name,
                command=lambda sk=style_key: self._gallery_apply_theme(sk))
        self.style_menu_btn.config(menu=self.style_menu)
        # Not packed — Apply Style moved to center panel

        _btn_delete = ttk.Button(action_row, text="🗑️ Delete",
                   command=self._gallery_delete)
        _btn_delete.pack(side="left", padx=(0, 6))

        # Full ordered list — mirrors the view radio order: Gallery|Favorites|Styled|Manual
        # Gallery=Wallpaper, Favorites=Save to Fav, Styled=Apply Style, Manual=Delete
        self._gallery_action_row_order = [
            _btn_wallpaper, self._btn_save_to_fav, self.style_menu_btn,
            _btn_delete,
        ]

        # Row 1: View selector
        view_row = ttk.Frame(filter_frame)
        view_row.pack(fill='x', pady=(0, 4))
        ttk.Label(view_row, text="View:").pack(side='left', padx=(0, 6))
        self.gallery_view_var = tk.StringVar(value="Gallery")
        ttk.Radiobutton(view_row, text="Gallery", variable=self.gallery_view_var,
                        value="Gallery", command=self._on_gallery_view_changed).pack(side='left', padx=(0, 6))
        ttk.Radiobutton(view_row, text="Favorites", variable=self.gallery_view_var,
                        value="Favorites", command=self._on_gallery_view_changed).pack(side='left', padx=(0, 6))
        ttk.Radiobutton(view_row, text="Styled", variable=self.gallery_view_var,
                        value="Styled", command=self._on_gallery_view_changed).pack(side='left', padx=(0, 6))
        ttk.Radiobutton(view_row, text="Manual", variable=self.gallery_view_var,
                        value="Manual", command=self._on_gallery_view_changed).pack(side='left')

        # Row 1: Sort & Organize

        ctrl_row = ttk.Frame(filter_frame)

        ctrl_row.pack(fill='x', pady=2)

        ttk.Label(ctrl_row, text="Sort:").pack(side='left', padx=(0, 4))

        self.sort_combo_var = tk.StringVar(value="Date Newest")

        self.sort_combo = ttk.Combobox(ctrl_row, textvariable=self.sort_combo_var,
                                        values=["Date Newest", "Date Oldest", "Name A-Z", "Name Z-A", "Size Largest"],
                                        state="readonly", width=15)
        self.sort_combo.pack(side='left', padx=(0, 8))
        self.sort_combo.bind('<<ComboboxSelected>>', self.sort_gallery)
        self.sort_combo.bind("<MouseWheel>", lambda e: "break")
        self.sort_combo.bind("<Button-4>", lambda e: "break")
        self.sort_combo.bind("<Button-5>", lambda e: "break")

        

        

        # Thumbnails

        thumb_frame = ttk.Frame(parent)

        thumb_frame.pack(fill='both', expand=True)

        # --- Gallery canvas (shown in Gallery view) ---
        self.gallery_canvas = tk.Canvas(thumb_frame, highlightthickness=0)
        def _gallery_scrollbar_cmd(*args):
            self.gallery_canvas.yview(*args)
            self._on_gallery_scroll()
        self._gallery_scroll = ttk.Scrollbar(thumb_frame, orient='vertical', command=_gallery_scrollbar_cmd)
        self.gallery_inner = ttk.Frame(self.gallery_canvas, style="Inner.TFrame")
        self.gallery_canvas.bind('<Configure>', self.on_gallery_resize)
        self.gallery_canvas.create_window(0, 0, window=self.gallery_inner, anchor='nw', tags="inner_frame")
        self.gallery_canvas.configure(yscrollcommand=self._gallery_scroll.set)
        self.gallery_canvas.pack(side='left', fill='both', expand=True)
        self._gallery_scroll.pack(side='right', fill='y')

        # --- Favorites canvas (shown in Favorites view) ---
        self.gallery_fav_canvas = tk.Canvas(thumb_frame, highlightthickness=0)
        gallery_fav_scroll = ttk.Scrollbar(thumb_frame, orient='vertical', command=self.gallery_fav_canvas.yview)
        self.gallery_fav_inner = ttk.Frame(self.gallery_fav_canvas, style="Inner.TFrame")
        self.gallery_fav_inner.bind("<Configure>", lambda e: self.gallery_fav_canvas.configure(
            scrollregion=self.gallery_fav_canvas.bbox("all")))
        self.gallery_fav_canvas.create_window((0, 0), window=self.gallery_fav_inner, anchor='nw', tags="fav_inner_frame")
        self.gallery_fav_canvas.configure(yscrollcommand=gallery_fav_scroll.set)
        self.gallery_fav_canvas.bind('<Configure>', self.on_fav_resize)
        # Hidden by default; revealed by _on_gallery_view_changed
        self._gallery_fav_scroll = gallery_fav_scroll
        self.gallery_favorites_ui = {"canvas": self.gallery_fav_canvas, "inner": self.gallery_fav_inner, "mode": "favorites"}

        # --- Styled canvas (shown in Styled view) ---
        self.gallery_styled_canvas = tk.Canvas(thumb_frame, highlightthickness=0)
        gallery_styled_scroll = ttk.Scrollbar(thumb_frame, orient='vertical', command=self.gallery_styled_canvas.yview)
        self.gallery_styled_inner = ttk.Frame(self.gallery_styled_canvas, style="Inner.TFrame")
        self.gallery_styled_inner.bind("<Configure>", lambda e: self.gallery_styled_canvas.configure(
            scrollregion=self.gallery_styled_canvas.bbox("all")))
        self.gallery_styled_canvas.create_window((0, 0), window=self.gallery_styled_inner, anchor='nw', tags="styled_inner_frame")
        self.gallery_styled_canvas.configure(yscrollcommand=gallery_styled_scroll.set)
        self.gallery_styled_canvas.bind('<Configure>', self.on_styled_resize)
        # Hidden by default; revealed by _on_gallery_view_changed
        self._gallery_styled_scroll = gallery_styled_scroll
        self.gallery_styled_images = []  # List of styled image paths
        self.gallery_styled_cards = {}   # path -> card frame

        # --- Manual canvas (shown in Manual view) ---
        self.gallery_manual_canvas = tk.Canvas(thumb_frame, highlightthickness=0)
        gallery_manual_scroll = ttk.Scrollbar(thumb_frame, orient='vertical', command=self.gallery_manual_canvas.yview)
        self.gallery_manual_inner = ttk.Frame(self.gallery_manual_canvas, style="Inner.TFrame")
        self.gallery_manual_inner.bind("<Configure>", lambda e: self.gallery_manual_canvas.configure(
            scrollregion=self.gallery_manual_canvas.bbox("all")))
        self.gallery_manual_canvas.create_window((0, 0), window=self.gallery_manual_inner, anchor='nw', tags="manual_inner_frame")
        self.gallery_manual_canvas.configure(yscrollcommand=gallery_manual_scroll.set)
        self.gallery_manual_canvas.bind('<Configure>', self.on_manual_resize)
        # Hidden by default; revealed by _on_gallery_view_changed
        self._gallery_manual_scroll = gallery_manual_scroll
        self.gallery_manual_images = []  # List of manual image paths
        self.gallery_manual_cards = {}   # path -> card frame

        # Selection tracking

        self.selected_gallery_path = None

        self.gallery_cards = {}  # path -> card frame

        self.drag_source_index = None

        

        self.load_gallery()  # Initial load



    # toggle_gallery_sort removed - dropdown handles all sorting



    def sort_gallery(self, event=None):
        """Handle sort dropdown selection - deferred to avoid UI freeze."""
        # Cancel any pending sort refresh job to avoid queuing multiple reloads
        if hasattr(self, '_sort_refresh_job') and self._sort_refresh_job:
            self.root.after_cancel(self._sort_refresh_job)
        # Schedule a new refresh after the combobox event cycle finishes
        self._sort_refresh_job = self.root.after(50, self._do_sort_gallery_reload)
        # Shift focus to gallery canvas so mouse wheel scrolling works immediately
        # without requiring an extra click after dropdown closes
        try:
            self.gallery_canvas.focus_set()
        except Exception:
            pass

    def _do_sort_gallery_reload(self):
        """Perform the actual gallery reload after combobox closes."""
        current_sort = self.sort_combo_var.get()

        if current_sort in ["Date Newest", "Date Oldest"]:
            self.gallery_sort_mode = "date"
        elif current_sort in ["Name A-Z", "Name Z-A"]:
            self.gallery_sort_mode = "name"
        elif current_sort in ["Size Largest"]:
            self.gallery_sort_mode = "size"
        else:
            self.gallery_sort_mode = "date"  # Default fallback

        tag_filter = self.get_active_tag()
        view_mode = self._gallery_view_mode()
        if view_mode == "Favorites":
            self.load_favorites(tag_filter=tag_filter)
        elif view_mode == "Styled":
            self.load_styled(tag_filter=tag_filter)
        elif view_mode == "Manual":
            self.load_manual(tag_filter=tag_filter)
        else:  # Gallery
            self.load_gallery()



    def _on_tag_var_changed(self, *args):
        """Show/hide delete tag button based on tag selection."""
        current_tag = self.gallery_tag_var.get()
        if current_tag and current_tag != 'All tags':
            self.delete_tag_btn.pack(side='left', padx=(0, 4))
        else:
            self.delete_tag_btn.pack_forget()

    def _confirm_delete_tag(self):
        """Delete the selected tag after user confirmation."""
        current_tag = self.gallery_tag_var.get()
        if not current_tag or current_tag == 'All tags':
            return

        # First confirmation dialog
        if not self._dialog.ask('Delete Tag', f'Delete tag "{current_tag}" from all images?\n\nThis cannot be undone.'):
            return

        # Second confirmation for "All tags" safety check
        if current_tag == 'All tags':
            if not self._dialog.ask('Confirm Delete', f'Are you absolutely sure you want to delete the "All tags" tag?\n\nThis will remove it from all images in the gallery.'):
                return

        # Delete the tag from all images
        try:
            from gallery_manager import get_images_by_tag, remove_tag_from_image

            # Get all images with this tag
            tagged_images = get_images_by_tag(current_tag)

            # Remove the tag from each image
            for image_path in tagged_images:
                remove_tag_from_image(image_path, current_tag)

            # Refresh the tag dropdown
            self._refresh_gallery_tag_filter()

            self.status_var.set(f'Tag "{current_tag}" deleted from {len(tagged_images)} images.')
        except Exception as e:
            self.status_var.set(f'Error deleting tag: {e}')
            self._dialog.error('Error', f'Failed to delete tag: {e}')

    def _on_tag_selected(self):
        """Handle tag selection change - applies tag filter to current view."""
        current_tag = self.gallery_tag_var.get()
        tag_filter = current_tag if current_tag != 'All tags' else None

        view_mode = self._gallery_view_mode()
        if view_mode == "Gallery":
            self.load_gallery()
            filter_desc = f" with tag '{current_tag}'" if tag_filter else ""
            self.status_var.set(f'Gallery reloaded{filter_desc}.')
        elif view_mode == "Favorites":
            self.load_favorites(tag_filter=tag_filter)
            filter_desc = f" with tag '{current_tag}'" if tag_filter else ""
            self.status_var.set(f'Favorites reloaded{filter_desc}.')
        elif view_mode == "Styled":
            self.load_styled(tag_filter=tag_filter)
            filter_desc = f" with tag '{current_tag}'" if tag_filter else ""
            self.status_var.set(f'Styled reloaded{filter_desc}.')
        elif view_mode == "Manual":
            self.load_manual(tag_filter=tag_filter)
            filter_desc = f" with tag '{current_tag}'" if tag_filter else ""
            self.status_var.set(f'Manual reloaded{filter_desc}.')

        # Return focus to the active canvas so mousewheel scrolling works
        # immediately after tag selection without needing an extra click.
        try:
            canvas_map = {
                "Gallery": self.gallery_canvas,
                "Favorites": self.gallery_fav_canvas,
                "Styled": self.gallery_styled_canvas,
                "Manual": self.gallery_manual_canvas,
            }
            target = canvas_map.get(view_mode, self.gallery_canvas)
            target.focus_set()
        except Exception:
            pass

    def apply_gallery_filter(self):
        """Apply selected gallery filter - now delegates to view-aware handler."""
        self._on_tag_selected()


    def on_gallery_resize(self, event):

        """Handle window resize to adjust column count — debounced."""

        canvas_width = event.width

        if self._gallery_resize_job is not None:
            self.gallery_canvas.after_cancel(self._gallery_resize_job)

        def _do_resize():
            self._gallery_resize_job = None
            cols = min(3, max(1, canvas_width // 250))
            self._gallery_cols = cols
            self.refresh_grid_layout(cols)
            self.gallery_canvas.itemconfig("inner_frame", width=canvas_width)
            self._render_visible_cards()

        self._gallery_resize_job = self.gallery_canvas.after(80, _do_resize)



    def refresh_grid_layout(self, cols):

        """Re-grid all gallery cards and placeholders based on new column count."""

        self._gallery_cols = cols

        # Make each column expand equally to fill the canvas width
        for c in range(cols):
            self.gallery_inner.columnconfigure(c, weight=1)

        # Re-grid real cards by their true index in gallery_images
        path_to_idx = {str(p): i for i, p in enumerate(self.gallery_images)}
        for key, (card, _, __) in self.gallery_cards.items():
            idx = path_to_idx.get(key)
            if idx is not None:
                card.grid(row=idx // cols, column=idx % cols, padx=6, pady=6, sticky='nsew')

        # Re-grid placeholders by their stored index
        for idx, ph in self._gallery_placeholders.items():
            ph.grid(row=idx // cols, column=idx % cols, padx=6, pady=6, sticky='nsew')



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
        """Return (first_idx, last_idx) inclusive for the visible viewport + buffer.

        Reads the canvas yview fraction and maps it to image indices using the
        known placeholder/card height constant.
        """
        n = len(self.gallery_images)
        if n == 0:
            return 0, -1

        cols = max(1, self._gallery_cols)
        n_rows = (n + cols - 1) // cols
        total_h = n_rows * _GALLERY_CARD_H

        if total_h == 0:
            return 0, n - 1

        y0_frac, y1_frac = self.gallery_canvas.yview()

        buf = _GALLERY_CARD_H  # one-row look-ahead buffer
        top_px = max(0.0, y0_frac * total_h - buf)
        bot_px = min(float(total_h), y1_frac * total_h + buf)

        first_row = int(top_px // _GALLERY_CARD_H)
        last_row  = min(n_rows - 1, int(bot_px // _GALLERY_CARD_H))

        first_idx = first_row * cols
        last_idx  = min(n - 1, (last_row + 1) * cols - 1)

        return first_idx, last_idx

    def _make_gallery_placeholder(self, idx, row, col):
        """Create and grid a fixed-size placeholder Frame for one image slot."""
        pal = THEMES.get(self.current_theme_name, THEMES["darkforest"])
        ph = tk.Frame(
            self.gallery_inner,
            width=252, height=_GALLERY_CARD_H,
            bg=pal["panel2"],
        )
        ph.grid(row=row, column=col, padx=6, pady=6, sticky='nsew')
        ph.grid_propagate(False)  # hold fixed size even when empty
        self._gallery_placeholders[idx] = ph

    def _render_visible_cards(self):
        """Promote placeholders → real cards for the visible range; demote the rest.

        Safe to call repeatedly; idempotent for slots already in the right state.
        In organize mode all slots are promoted so drag indices stay contiguous.
        """
        n = len(self.gallery_images)
        if not n:
            return

        cols = max(1, self._gallery_cols)

        first_idx, last_idx = self._gallery_visible_range()

        visible_set = set(range(first_idx, last_idx + 1))

        # Build reverse lookup once for O(1) index resolution below
        path_to_idx = {str(p): i for i, p in enumerate(self.gallery_images)}

        # --- Demote real cards outside visible range back to placeholders ---
        to_demote = []
        for key in list(self.gallery_cards):
            idx = path_to_idx.get(key)
            if idx is None or idx not in visible_set:
                to_demote.append(key)

        for key in to_demote:
            entry = self.gallery_cards.pop(key, None)
            if entry:
                card = entry[0]
                idx = path_to_idx.get(key)
                card.destroy()
                if idx is not None:
                    row, col = idx // cols, idx % cols
                    self._make_gallery_placeholder(idx, row, col)

        # --- Promote placeholders in visible range to real cards ---
        for idx in range(first_idx, last_idx + 1):
            img_path = self.gallery_images[idx]
            key = str(img_path)
            if key in self.gallery_cards:
                continue  # already a real card

            # Destroy placeholder for this slot if one exists
            ph = self._gallery_placeholders.pop(idx, None)
            if ph is not None:
                ph.destroy()

            row, col = idx // cols, idx % cols
            self.create_gallery_card(img_path, row, col, idx)

        # scrollregion tracks gallery_inner's actual content (placeholders fill it)
        self.gallery_canvas.configure(
            scrollregion=self.gallery_canvas.bbox('all') or (0, 0, 1, 1)
        )

    def _on_gallery_scroll(self, *_):
        """Debounced scroll handler — defers _render_visible_cards by 60 ms."""
        if self._gallery_scroll_job is not None:
            try:
                self.gallery_canvas.after_cancel(self._gallery_scroll_job)
            except Exception:
                pass
        self._gallery_scroll_job = self.gallery_canvas.after(
            60, self._render_visible_cards
        )

    def _gallery_view_mode(self):
        """Return 'Favorites' or 'Gallery' based on current radio selection."""
        return self.gallery_view_var.get()

    def get_active_tag(self):
        """Return the currently selected tag filter, or None if 'All tags' / unset."""
        tag = getattr(self, 'gallery_tag_var', None)
        if tag is None:
            return None
        val = tag.get()
        return val if val and val != 'All tags' else None

    def _gallery_set_wallpaper(self):
        """Set as Wallpaper — routes to gallery, favorites, or styled selection."""
        if self._gallery_view_mode() == "Favorites":
            self.set_selected_favorite_as_wallpaper()
        else:
            # Gallery or Styled view — both use selected_gallery_path
            self.set_gallery_selection()

    def _gallery_save_to_favorites(self):
        """Save to Favorites — no-op with message if already a favorite."""
        if self._gallery_view_mode() == "Favorites":
            self.status_var.set("Already in Favorites.")
        else:
            self.save_gallery_to_favorites()

    def _gallery_apply_theme(self, style_key):
        """Apply Themes — uses resolved image path in Favorites view."""
        if self._gallery_view_mode() == "Favorites":
            if not self.favorite_selected_item:
                self._dialog.warning("No Selection", "Select a Favorite thumbnail first.")
                return
            path_str = self.favorite_selected_item.get("image_path") or \
                       self.favorite_selected_item.get("copied_image_path")
            if not path_str or not Path(path_str).exists():
                self._dialog.warning("No Image", "Selected favorite has no valid image file.")
                return
            self.selected_gallery_path = Path(path_str)
        self.apply_style_transfer_filter(style_key)

    def _gallery_tag_selected(self):
        """Tag Selected — uses resolved image path in Favorites view."""
        if self._gallery_view_mode() == "Favorites":
            if not self.favorite_selected_item:
                self._dialog.warning("No Selection", "Select a Favorite thumbnail first.")
                return
            path_str = self.favorite_selected_item.get("image_path") or \
                       self.favorite_selected_item.get("copied_image_path")
            if not path_str or not Path(path_str).exists():
                self._dialog.warning("No Image", "Selected favorite has no valid image file.")
                return
            self.selected_gallery_path = Path(path_str)
        self.tag_gallery_image()

    def _gallery_delete(self):
        """Delete — removes gallery image, favorite, or styled image depending on view."""
        mode = self._gallery_view_mode()
        if mode == "Favorites":
            self.delete_selected_favorite()
        elif mode == "Styled":
            self._delete_styled_image()
        elif mode == "Manual":
            self.delete_selected()
            self.load_manual()  # Refresh manual view after deletion
        else:
            self.delete_selected()

    def _delete_styled_image(self):
        """Delete selected styled image from the styled folder."""
        if not self.selected_gallery_path:
            self._dialog.warning("No Selection", "Select a styled image first.")
            return

        if not self.selected_gallery_path.exists():
            self._dialog.warning("File Not Found", "The selected image no longer exists.")
            return

        confirm = self._dialog.ask(
            "Confirm Delete",
            f"Delete styled image:\n{self.selected_gallery_path.name}\n\nThis cannot be undone."
        )
        if not confirm:
            return

        try:
            self.selected_gallery_path.unlink()
            self.status_var.set(f'🗑️ Deleted styled image: {self.selected_gallery_path.name}')
            self.selected_gallery_path = None
            self.load_styled()  # Refresh styled view
        except Exception as e:
            self._dialog.error("Delete Failed", f"Failed to delete:\n{e}")
    def _copy_prompt_to_clipboard(self):
        """Copy the current prompt text to the system clipboard."""
        prompt = self.prompt_text.get("1.0", "end-1c").strip()
        if prompt:
            self.root.clipboard_clear()
            self.root.clipboard_append(prompt)
            self.status_var.set("Prompt copied to clipboard!")
        else:
            self.status_var.set("No prompt to copy.")

    def _open_wallpapers_folder(self):
        """Open the wallpapers directory in the system file explorer."""
        try:
            folder_path = Path(__file__).parent / "wallpapers"
            if not folder_path.exists():
                folder_path.mkdir(parents=True, exist_ok=True)
            os.startfile(folder_path)
        except Exception as e:
            self.status_var.set(f"Could not open folder: {e}")

    def _on_gallery_view_changed(self):
        """Switch between Gallery, Favorites, Styled, and Manual views inside the Gallery tab."""
        mode = self.gallery_view_var.get()

        # Hide all view canvases first
        self.gallery_canvas.pack_forget()
        self._gallery_scroll.pack_forget()
        self.gallery_fav_canvas.pack_forget()
        self._gallery_fav_scroll.pack_forget()
        self.gallery_styled_canvas.pack_forget()
        self._gallery_styled_scroll.pack_forget()
        self.gallery_manual_canvas.pack_forget()
        self._gallery_manual_scroll.pack_forget()

        # Helper: repack action row showing only the given subset in order
        def _repack(visible):
            for w in self._gallery_action_row_order:
                w.pack_forget()
            for w in visible:
                w.pack(side="left", padx=(0, 6))

        _btn_wallpaper_ref = self._gallery_action_row_order[0]
        _btn_delete_ref    = self._gallery_action_row_order[3]

        if mode == "Favorites":
            self.gallery_fav_canvas.pack(side='left', fill='both', expand=True)
            self._gallery_fav_scroll.pack(side='right', fill='y')
            # Favorites: Wallpaper | Delete
            _repack([_btn_wallpaper_ref, _btn_delete_ref])
            self.load_favorites()
        elif mode == "Styled":
            self.gallery_styled_canvas.pack(side='left', fill='both', expand=True)
            self._gallery_styled_scroll.pack(side='right', fill='y')
            # Styled: Wallpaper | Save to Fav | Delete  (Apply Style hidden — already styled)
            _repack([_btn_wallpaper_ref, self._btn_save_to_fav, _btn_delete_ref])
            self.load_styled()
        elif mode == "Manual":
            self.gallery_manual_canvas.pack(side='left', fill='both', expand=True)
            self._gallery_manual_scroll.pack(side='right', fill='y')
            # Manual: Wallpaper | Save to Fav | Delete
            _repack([_btn_wallpaper_ref, self._btn_save_to_fav, _btn_delete_ref])
            self.load_manual()
        else:  # Gallery
            self.gallery_canvas.pack(side='left', fill='both', expand=True)
            self._gallery_scroll.pack(side='right', fill='y')
            # Gallery: Wallpaper | Save to Fav | Delete
            _repack([_btn_wallpaper_ref, self._btn_save_to_fav, _btn_delete_ref])
            # Force multiple UI updates to ensure canvas is properly visible and sized
            self.gallery_canvas.update()
            self.gallery_canvas.update_idletasks()
            self.root.update_idletasks()
            self.load_gallery()
            # Force another update after loading to ensure rendering
            self.gallery_canvas.update_idletasks()

    def load_gallery(self):

        """Load and display gallery images (excluding favorites and styled) with custom sorting."""

        try:

            # Only load from manual and generated folders, NOT favorites or styled
            from set_wallpaper import MANUAL_DIR, GENERATED_DIR
            raw_images = collect_wallpapers([MANUAL_DIR, GENERATED_DIR]) or []

            

            # Apply Sorting based on selected mode

            current_sort = self.sort_combo_var.get()

            

            if current_sort == "Date Newest":

                # Sort by date descending (newest first)

                images_with_stats = [(img, img.stat().st_mtime) for img in raw_images]

                images_with_stats.sort(key=lambda x: x[1], reverse=True)

                raw_images = [x[0] for x in images_with_stats]

            elif current_sort == "Date Oldest":

                # Sort by date ascending (oldest first)

                images_with_stats = [(img, img.stat().st_mtime) for img in raw_images]

                images_with_stats.sort(key=lambda x: x[1], reverse=False)

                raw_images = [x[0] for x in images_with_stats]

            elif current_sort == "Name A-Z":

                # Sort by name ascending

                raw_images.sort(key=lambda x: str(x.name).lower())

            elif current_sort == "Name Z-A":

                # Sort by name descending

                raw_images.sort(key=lambda x: str(x.name).lower(), reverse=True)

            elif current_sort == "Size Largest":

                # Sort by file size descending (largest first)

                try:

                    images_with_size = [(img, os.path.getsize(img)) for img in raw_images]

                    images_with_size.sort(key=lambda x: x[1], reverse=True)

                    raw_images = [x[0] for x in images_with_size]

                except OSError:

                    # Fallback to name sort if size fails

                    raw_images.sort(key=lambda x: str(x.name).lower())

            else:

                # Default to Date Newest

                images_with_stats = [(img, img.stat().st_mtime) for img in raw_images]

                images_with_stats.sort(key=lambda x: x[1], reverse=True)

                raw_images = [x[0] for x in images_with_stats]

            

            # If a custom order exists (from Organize Mode), apply it
            if self._gallery_custom_order is not None:
                order_strs = [str(p) for p in self._gallery_custom_order]
                ordered = {str(p): p for p in raw_images}
                raw_images = [ordered[s] for s in order_strs if s in ordered]
                # Append any new files not yet in the custom order
                raw_images += [p for p in ordered.values() if str(p) not in order_strs]

            self.gallery_images = raw_images

            self.slideshow.load_gallery(self.gallery_images)

        except Exception as e:

            self.status_var.set(f'Gallery load failed: {e}')

            self.gallery_images = []

        

        # Clear existing real cards
        for card, *_ in self.gallery_cards.values():
            card.destroy()
        self.gallery_cards.clear()

        # Clear existing placeholders
        for ph in self._gallery_placeholders.values():
            ph.destroy()
        self._gallery_placeholders.clear()

        # Cancel any stale layout or scroll jobs from a previous load
        for job_attr in ('_gallery_layout_job', '_gallery_scroll_job'):
            job = getattr(self, job_attr, None)
            if job is not None:
                try:
                    self.gallery_canvas.after_cancel(job)
                except Exception:
                    pass
                setattr(self, job_attr, None)

        # Compute column count from current canvas width (default 3 before first layout)
        w = self.gallery_canvas.winfo_width()
        cols = min(3, max(1, w // 250)) if w > 1 else 3
        self._gallery_cols = cols
        self.gallery_canvas.itemconfig("inner_frame", width=max(w, 1))
        for c in range(cols):
            self.gallery_inner.columnconfigure(c, weight=1)

        # Empty-state: no images found
        n = len(self.gallery_images)
        if n == 0:
            pal = THEMES.get(self.current_theme_name, THEMES["darkforest"])
            msg = tk.Label(
                self.gallery_inner,
                text="No images found in Gallery.",
                bg=pal["panel"], fg=pal["text"], font=self.small_font,
                pady=30,
            )
            msg.grid(row=0, column=0, columnspan=3, sticky="ew")
            self.gallery_canvas.update_idletasks()
            self.gallery_canvas.configure(
                scrollregion=self.gallery_canvas.bbox('all') or (0, 0, 1, 1)
            )
            self.status_var.set("No images found in Gallery.")
            return

        # Create a lightweight placeholder Frame for every image slot.
        # Placeholders hold gallery_inner at the correct total height so the
        # scrollbar is accurate before any thumbnails are loaded.
        for idx in range(n):
            self._make_gallery_placeholder(idx, idx // cols, idx % cols)

        # scrollregion is now driven by actual placeholder content
        self.gallery_canvas.update_idletasks()
        self.gallery_canvas.configure(
            scrollregion=self.gallery_canvas.bbox('all') or (0, 0, 1, 1)
        )

        # Promote the initial viewport to real cards
        self._render_visible_cards()

        self.status_var.set(f'Gallery loaded: {len(self.gallery_images)} images')



    def create_gallery_card(self, img_path, row, col, index):

        """Create clickable thumbnail card with drag-drop support."""

        pal = THEMES.get(self.current_theme_name, THEMES["darkforest"])
        border = pal.get("border_color", pal["panel2"])
        card = tk.Frame(self.gallery_inner, bg=pal["panel"],
                        highlightthickness=1, highlightbackground=border, bd=0)

        card.grid(row=row, column=col, padx=6, pady=6, sticky='nsew')

        card.columnconfigure(0, weight=1)

        

        # Thumbnail with Caching

        try:

            from PIL import Image, ImageTk

            path_str = str(img_path)

            if path_str in self.thumb_cache:

                thumb = self.thumb_cache[path_str]

            else:

                img = Image.open(img_path)

                img.thumbnail((240, 135), Image.Resampling.LANCZOS)

                thumb = ImageTk.PhotoImage(img)

                if len(self.thumb_cache) > 200:

                    self.thumb_cache.clear()

                self.thumb_cache[path_str] = thumb

            

            label = tk.Label(card, image=thumb, bg=pal["panel"])

            label.image = thumb  # Keep reference

            label.grid(row=0, column=0, pady=(4, 4), padx=4)

            

            # Selection & Drag Logic

            label.bind('<Button-1>', lambda e, p=img_path, idx=index: self.on_card_click(e, p, idx))

            label.bind('<Double-Button-1>', lambda e, p=img_path: self.set_gallery_image_as_wallpaper(p))

            card.bind('<Button-1>', lambda e, p=img_path, idx=index: self.on_card_click(e, p, idx))

        except Exception as e:

            print(f"Gallery thumbnail error for {img_path}: {e}")

            tk.Label(card, text=f'❌ {img_path.name}', bg='red', fg='white').grid(row=0, column=0)

        

        # Name + actions

        name_label = tk.Label(card, text=img_path.name,
                               wraplength=220, height=2, font=self.small_font, bg=pal["panel"], fg=pal["text"], anchor="w", justify="left",
                               padx=6, pady=2)

        name_label.grid(row=1, column=0, sticky='ew')

        # File size + resolution info
        try:
            stat = img_path.stat()
            size_bytes = stat.st_size
            if size_bytes >= 1_048_576:
                size_str = f"{size_bytes / 1_048_576:.1f} MB"
            else:
                size_str = f"{size_bytes / 1024:.0f} KB"
            from PIL import Image as _PILImage
            with _PILImage.open(img_path) as _im:
                w_px, h_px = _im.size
            info_text = f"{w_px}×{h_px}  •  {size_str}"
        except Exception:
            info_text = ""

        info_label = tk.Label(card, text=info_text, fg=pal["muted"], font=self.tinyfont,
                              bg=pal["panel"], anchor="w", justify="left", padx=6, pady=0)
        info_label.grid(row=2, column=0, sticky='ew')

        tags = get_tags_for_image(img_path) or []

        tags_label = tk.Label(card, text=', '.join(tags[:3]), fg=pal.get("tag_fg", pal["muted"]), font=self.small_font,
                              bg=pal["panel"], anchor="w", justify="left", padx=6, pady=4)

        tags_label.grid(row=3, column=0, sticky='ew')

        for sub in (name_label, info_label, tags_label):
            sub.bind('<Button-1>', lambda e, p=img_path, idx=index: self.on_card_click(e, p, idx))

        

        self.gallery_cards[str(img_path)] = (card, name_label, tags_label)



    def on_card_click(self, event, path, index):
        """Handle card click - delegate to _on_thumbnail_click with Ctrl check."""
        ctrl_pressed = (event.state & 0x4) != 0  # Check if Ctrl key is pressed
        self._on_thumbnail_click(path, ctrl_pressed)



    def on_card_drag(self, event, index):
        pass

    def on_card_drop(self, event, source_index):
        pass



    def _widget_to_card_index(self, widget):
        return None  # Organize Mode removed

    def _highlight_organize_source(self, picked_index, *, hover_index):
        pass  # Organize Mode removed



    def apply_style_transfer_filter(self, style_key):

        """Apply a selected artistic style using style_transfer.py and save as a new file."""

        if not self.selected_gallery_path:

            self._dialog.warning("No Selection", "Select an image from the gallery first.")

            return

        

        # Validate style key exists

        from style_transfer import get_style_transfer

        transfer = get_style_transfer()

        if style_key not in transfer.get_style_list():

            self._dialog.error("Unsupported Style", 

                               f"The style '{style_key}' is not available.\n\n"

                               f"Available styles:\n"

                               f"• {', '.join(transfer.get_style_list())}\n\n"

                               f"Please contact support if you need this style added.")

            return

        

        if style_key == "original":

            self._dialog.info("Style Transfer", "No style selected. Using original image.")

            return

        

        # Validate image path exists

        if not self.selected_gallery_path.exists():

            self._dialog.error("File Not Found", 

                               f"The selected image file could not be found:\n\n"

                               f"{self.selected_gallery_path}\n\n"

                               f"Please select a different image and try again.")

            return

        

        # Show progress

        self.status_var.set(f"Applying {style_key} style... (this may take 10-20 seconds)")

        

        # Apply style in a separate thread to avoid freezing UI

        import threading

        thread = threading.Thread(target=self._apply_style_thread, args=(style_key,))

        thread.daemon = True

        thread.start()



    def apply_artistic_filter(self, style_name):

        """Apply a selected artistic filter using PIL and save as a new file."""

        if not self.selected_gallery_path:

            self._dialog.warning("No Selection", "Select an image from the gallery first.")

            return

        

        try:

            from PIL import Image, ImageEnhance, ImageOps

            img = Image.open(self.selected_gallery_path)

            

            suffix = ""

            if style_name == "Vivid":

                # Enhance brightness and contrast

                img = ImageEnhance.Brightness(img).enhance(1.2)

                img = ImageEnhance.Contrast(img).enhance(1.2)

                suffix = "_vivid"

            elif style_name == "Monochrome":

                # Convert to grayscale

                img = ImageOps.grayscale(img)

                suffix = "_bw"

            elif style_name == "Vintage":

                # Warm tint and slightly lower contrast

                img = ImageEnhance.Color(img).enhance(0.8)

                img = ImageEnhance.Contrast(img).enhance(0.9)

                # Simple vintage tint (increase red/yellow slightly if RGB)

                if img.mode == 'RGB':

                    r, g, b = img.split()

                    r = r.point(lambda i: i * 1.1)

                    b = b.point(lambda i: i * 0.9)

                    img = Image.merge('RGB', (r, g, b))

                suffix = "_vintage"

            elif style_name == "Pop":

                # High saturation

                img = ImageEnhance.Color(img).enhance(1.6)

                suffix = "_pop"

            

            # Save new file

            new_name = f"{self.selected_gallery_path.stem}{suffix}.png"

            new_path = self.selected_gallery_path.parent / new_name

            img.save(new_path)

            

            self.status_var.set(f"🎨 {style_name} style saved: {new_name}")

            self.load_gallery()

        except Exception as e:

            self._dialog.error("Filter Error", f"Failed to apply {style_name}: {e}")



    def on_fav_resize(self, event):

        """Handle favorites canvas resize — match gallery 3-column behaviour."""

        canvas_width = event.width

        cols = min(3, max(1, canvas_width // 260))

        self._rebuild_fav_grid(cols)

        self.gallery_fav_canvas.configure(scrollregion=self.gallery_fav_canvas.bbox('all'))

        self.gallery_fav_canvas.itemconfig("fav_inner_frame", width=canvas_width)



    def _rebuild_fav_grid(self, cols):

        """Re-grid all favorites cards based on column count."""

        for c in range(cols):
            self.gallery_fav_inner.columnconfigure(c, weight=1)

        for i, card_frame in enumerate(self.gallery_fav_inner.winfo_children()):

            card_frame.grid(row=i // cols, column=i % cols, padx=5, pady=6, sticky='nsew')



    def on_styled_resize(self, event):

        """Handle styled canvas resize — match gallery 3-column behaviour."""

        canvas_width = event.width

        cols = min(3, max(1, canvas_width // 260))

        self._rebuild_styled_grid(cols)

        self.gallery_styled_canvas.configure(scrollregion=self.gallery_styled_canvas.bbox('all'))

        self.gallery_styled_canvas.itemconfig("styled_inner_frame", width=canvas_width)



    def _rebuild_styled_grid(self, cols):

        """Re-grid all styled cards based on column count."""

        for c in range(cols):
            self.gallery_styled_inner.columnconfigure(c, weight=1)

        for i, card_frame in enumerate(self.gallery_styled_inner.winfo_children()):
            card_frame.grid(row=i // cols, column=i % cols, padx=5, pady=6, sticky='nsew')



    def on_manual_resize(self, event):

        """Handle manual canvas resize — match gallery 3-column behaviour."""

        canvas_width = event.width

        cols = min(3, max(1, canvas_width // 260))

        self._rebuild_manual_grid(cols)

        self.gallery_manual_canvas.configure(scrollregion=self.gallery_manual_canvas.bbox('all'))

        self.gallery_manual_canvas.itemconfig("manual_inner_frame", width=canvas_width)



    def _rebuild_manual_grid(self, cols):

        """Re-grid all manual cards based on column count."""

        for c in range(cols):
            self.gallery_manual_inner.columnconfigure(c, weight=1)

        for i, card_frame in enumerate(self.gallery_manual_inner.winfo_children()):
            card_frame.grid(row=i // cols, column=i % cols, padx=5, pady=6, sticky='nsew')




    def on_organize_toggle(self):
        pass  # Organize Mode removed

    def _on_thumbnail_click(self, path, ctrl_pressed=False):
        """Handle thumbnail click with multi-select support (Ctrl-click)."""
        path_obj = Path(path)
        path_str = str(path_obj)
        
        if ctrl_pressed:
            # Ctrl-click: toggle selection in multi-select set
            if path_str in self.selected_gallery_paths:
                self.selected_gallery_paths.discard(path_str)
            else:
                self.selected_gallery_paths.add(path_str)
            # Primary selection stays as last clicked
            self.selected_gallery_path = path_obj
        else:
            # Normal click: clear multi-select, set single selection
            self.selected_gallery_paths.clear()
            self.selected_gallery_paths.add(path_str)
            self.selected_gallery_path = path_obj
            self.show_preview_in_left_panel(path, f'Gallery: {path.name}')
        
        selection_count = len(self.selected_gallery_paths)
        if selection_count > 1:
            self.status_var.set(f'Selected {selection_count} images')
        else:
            self.status_var.set(f'Selected: {path.name}')
        
        self._update_gallery_highlight_multi()

    def _update_gallery_highlight(self, selected_path):
        """Apply selection highlight to the selected gallery card (legacy single-select)."""
        self._update_gallery_highlight_multi()

    def _update_gallery_highlight_multi(self):
        """Apply selection highlight to all selected gallery cards (multi-select support)."""
        pal = THEMES.get(self.current_theme_name, THEMES["darkforest"])
        accent = pal.get("accent", pal["progress"])
        border = pal.get("border_color", pal["panel2"])
        surface = pal.get("surface", pal["panel2"])
        
        for path_str, (card, name_label, tags_label) in self.gallery_cards.items():
            is_multi_sel = path_str in self.selected_gallery_paths
            is_primary = self.selected_gallery_path and path_str == str(self.selected_gallery_path)
            
            if is_primary and len(self.selected_gallery_paths) > 1:
                # Primary selection in multi-select: accent border, surface bg
                bg = surface
                hi = accent
                thickness = 3
            elif is_multi_sel:
                # Multi-selected: surface bg, accent border
                bg = surface
                hi = accent
                thickness = 2
            else:
                # Not selected: panel bg, border color
                bg = pal["panel"]
                hi = border
                thickness = 1
            
            card.config(bg=bg, highlightbackground=hi, highlightthickness=thickness)
            for child in card.winfo_children():
                if isinstance(child, tk.Label):
                    child.config(bg=bg)

    def set_gallery_image_as_wallpaper(self, path):

        """Set gallery image as wallpaper on double-click."""

        if not WINDOWS:

            self._dialog.info('Windows only', 'Wallpaper setting is Windows-only.')

            return

        try:

            ok = set_wallpaper(Path(path))

            if ok:

                self.status_var.set(f'✅ Wallpaper set: {Path(path).name}')
                self.slideshow.reset_timer()

            else:

                self.status_var.set(f'❌ Set failed: {Path(path).name}')

        except Exception as e:

            self.status_var.set(f'❌ Error: {e}')

            self._dialog.error("Wallpaper Error", f"Failed to set wallpaper: {e}")



    def set_gallery_selection(self):

        """Set selected as wallpaper."""

        if not self.selected_gallery_path or not WINDOWS:

            self._dialog.info('Windows only', 'Wallpaper setting is Windows-only.')

            return

        try:

            ok = set_wallpaper(self.selected_gallery_path)

            self.status_var.set(f'✅ Wallpaper set: {self.selected_gallery_path.name}' if ok else '❌ Set failed.')
            if ok:
                self.slideshow.reset_timer()

        except Exception as e:

            self.status_var.set(f'❌ Error: {e}')



    def save_gallery_to_favorites(self):

        """Add selected to favorites by copying to wallpapers/favorites/ folder."""

        if not self.selected_gallery_path:

            self._dialog.warning('No Selection', 'Select an image first.')

            return

        existing = load_json_list(FAVORITES_LOG)

        path_str = str(self.selected_gallery_path)
        original_resolved = self.selected_gallery_path.resolve()
        
        # Check if already favorited by comparing resolved paths
        if any(item.get('copied_image_path') and Path(item.get('copied_image_path')).resolve() == original_resolved for item in existing):

            self.status_var.set(f'Image already in favorites.')

            return

        # Determine the final image path for the favorite
        final_image_path = None
        needs_copy = True
        
        # Check if the selected image is already inside wallpapers/favorites/
        if FAVORITES_DIR in self.selected_gallery_path.parents:
            # Image is already in favorites folder, use it directly
            final_image_path = self.selected_gallery_path
            needs_copy = False
        else:
            # Need to copy to favorites folder
            dest_filename = self.selected_gallery_path.name
            dest_path = FAVORITES_DIR / dest_filename
            
            # Handle filename collisions with fav2, fav3, etc. suffix
            counter = 2
            while dest_path.exists():
                # Check if it's the same file (same resolved path)
                if dest_path.resolve() == original_resolved:
                    # Same file, reuse it
                    final_image_path = dest_path
                    needs_copy = False
                    break
                
                # Different file, create unique name
                stem = self.selected_gallery_path.stem
                suffix = self.selected_gallery_path.suffix
                dest_filename = f"{stem}_fav{counter}{suffix}"
                dest_path = FAVORITES_DIR / dest_filename
                counter += 1
            
            if needs_copy:
                final_image_path = dest_path
                try:
                    import shutil
                    shutil.copy2(self.selected_gallery_path, dest_path)
                except Exception as e:
                    self._dialog.error('Error', f'Failed to copy image to favorites folder:\n{e}')
                    return

        # Create metadata entry with both paths
        entry = {
            'saved_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'original_image_path': path_str,
            'image_path': str(final_image_path),  # Final favorite copy path
            'copied_image_path': str(final_image_path) if needs_copy else None,
            'theme_sentence': f'Gallery favorite: {self.selected_gallery_path.name}'
        }

        existing.append(entry)
        save_json_list(FAVORITES_LOG, existing)

        self.load_favorites()
        self.status_var.set(f'⭐ Saved to favorites: {self.selected_gallery_path.name}')



    def _resolve_related_paths(self, path) -> list[str]:
        """Return all known physical paths that represent the same image.

        For a generated image this includes its favorite copy (if any).
        For a favorite copy this includes the original generated file.
        Always returns at least the input path when it exists.
        Paths are de-duplicated by resolved absolute path.
        """
        try:
            target = Path(path).resolve()
        except Exception:
            return [str(path)]

        seen = set()
        result = []

        def _add(p):
            try:
                rp = Path(p).resolve()
                key = str(rp)
                if key not in seen and rp.exists():
                    seen.add(key)
                    result.append(str(rp))
            except Exception:
                pass

        _add(target)

        target_str = str(target)
        target_name = target.name

        favorites = getattr(self, "favorites", []) or []
        if not favorites:
            try:
                favorites = load_json_list(FAVORITES_LOG)
            except Exception:
                favorites = []
        for item in favorites:
            orig = item.get("original_image_path") or ""
            img  = item.get("image_path") or ""
            cpy  = item.get("copied_image_path") or ""

            candidates = [c for c in (orig, img, cpy) if c]
            resolved_candidates = []
            for c in candidates:
                try:
                    resolved_candidates.append((c, str(Path(c).resolve())))
                except Exception:
                    pass

            # Check if any candidate matches the input path
            match = any(rc == target_str for _, rc in resolved_candidates)
            if not match:
                # Fallback: match by filename (handles renamed-copy edge case)
                match = any(Path(c).name == target_name for c, _ in resolved_candidates)

            if match:
                for _, rc in resolved_candidates:
                    _add(rc)

        return result

    def _propagate_tags_to_related(self, path, tags: list) -> list:
        """Apply tags to path and all its related sibling paths.

        Returns the full list of paths that were tagged.
        """
        all_paths = self._resolve_related_paths(path)
        if all_paths and tags:
            add_tags_to_paths(all_paths, tags)
        return all_paths

    def tag_gallery_image(self):
        """Add tags to selected image(s) with batch tagging support."""
        # Validate selection - use multi-select set if available, otherwise fall back to single
        target_paths = []
        if self.selected_gallery_paths:
            target_paths = [p for p in self.selected_gallery_paths if Path(p).exists()]
        elif self.selected_gallery_path and Path(self.selected_gallery_path).exists():
            target_paths = [str(self.selected_gallery_path)]
        
        if not target_paths:
            self._dialog.warning('No Selection', 'Select at least one image first.')
            return
        
        # Filter out non-existent paths
        existing_paths = [p for p in target_paths if Path(p).exists()]
        if not existing_paths:
            self._dialog.error('Error', 'Selected image(s) no longer exist.')
            self.selected_gallery_path = None
            self.selected_gallery_paths.clear()
            self._refresh_tag_ui(status_msg='Selection cleared - file(s) not found')
            return
        
        # Get tag input from user
        count_str = f'{len(existing_paths)} image(s)' if len(existing_paths) > 1 else 'image'
        tags_str = simpledialog.askstring('Add Tags', f'Tag {count_str} (comma-separated):', initialvalue='')
        if not tags_str:
            return  # User cancelled or empty input
        
        # Parse and clean tags
        tags = [t.strip() for t in tags_str.split(',') if t.strip()]
        if not tags:
            self._dialog.info('No Tags', 'No valid tags entered. Tags cannot be empty.')
            return
        
        # Deduplicate tags case-insensitively (preserve first occurrence's case)
        seen_lower = set()
        unique_tags = []
        for tag in tags:
            lower = tag.lower()
            if lower not in seen_lower:
                seen_lower.add(lower)
                unique_tags.append(tag)
        
        # Apply tags to all selected images
        total_new_tags = 0
        total_skipped = 0
        failed_paths = []
        
        for path_str in existing_paths:
            try:
                existing_tags = get_tags_for_image(path_str) or []
                existing_lower = {t.lower() for t in existing_tags}
                new_tags = [t for t in unique_tags if t.lower() not in existing_lower]

                if new_tags:
                    self._propagate_tags_to_related(path_str, new_tags)
                    total_new_tags += len(new_tags)
                total_skipped += len(unique_tags) - len(new_tags)
            except Exception as e:
                failed_paths.append((path_str, str(e)))
        
        # Build status message
        if len(existing_paths) == 1:
            if total_new_tags > 0:
                status_msg = f'🏷️ Tagged: {", ".join(unique_tags)}'
                if total_skipped > 0:
                    status_msg += f' ({total_skipped} duplicate skipped)'
            else:
                status_msg = 'All tags already exist on this image.'
        else:
            status_msg = f'🏷️ Tagged {len(existing_paths)} images with {total_new_tags} new tags'
            if total_skipped > 0:
                status_msg += f' ({total_skipped} duplicates skipped)'
            if failed_paths:
                status_msg += f' ({len(failed_paths)} failed)'
        
        self._refresh_tag_ui(status_msg=status_msg, keep_selection=True)
        
        if failed_paths:
            self.status_var.set(f'Error tagging some images: {failed_paths[0][1]}')



    def organize_gallery_image(self):

        """Move to subfolder."""

        if not self.selected_gallery_path:

            return

        folder = simpledialog.askstring('Folder', 'Subfolder name (e.g. "cyberpunk"):', initialvalue='')

        if folder:

            new_path = organize_image_into_folder(str(self.selected_gallery_path), folder)

            if new_path:

                self.selected_gallery_path = Path(new_path)

                self.load_gallery()  # Refresh gallery

                self.status_var.set(f'📁 Moved to /{folder}/')

            else:

                self.status_var.set('❌ Organize failed.')



    def delete_selected(self):
        """Delete selected image + tags, with proper tag UI refresh."""
        if not self.selected_gallery_path:
            self._dialog.warning('No Selection', 'Select an image first.')
            return
        
        if self._dialog.ask('Confirm', f'Delete {self.selected_gallery_path.name}?'):
            delete_image_and_tags(str(self.selected_gallery_path))
            self.selected_gallery_path = None
            self.clear_image()
            # Use centralized refresh to update dropdown and view
            self._refresh_tag_ui(status_msg='🗑️ Deleted.')



    def _refresh_tag_ui(self, status_msg=None, keep_selection=True):
        """Centralized tag UI refresh - call after ANY tag change.
        
        Rebuilds dropdown and reloads current view with proper filtering.
        Preserves current selection by default, or falls back to 'All tags'.
        """
        # Get current selection before rebuilding
        current_tag = self.gallery_tag_var.get()
        
        # Rebuild tag dropdown from current storage
        tags = ['All tags'] + get_all_tags()
        self.gallery_tag_combo['values'] = tags

        # Restore or reset selection — always call set() so the combobox
        # display refreshes even when the deleted tag was previously shown.
        new_selection = current_tag if (keep_selection and current_tag in tags) else 'All tags'
        self.gallery_tag_var.set(new_selection)
        # Force the readonly combobox to visually reflect the new value
        self.gallery_tag_combo.set(new_selection)
        
        # Determine effective filter after potential selection change
        effective_tag = self.gallery_tag_var.get()
        tag_filter = effective_tag if effective_tag != 'All tags' else None
        
        # Reload current view
        view_mode = self._gallery_view_mode()
        if view_mode == "Gallery":
            self.load_gallery()
        elif view_mode == "Favorites":
            self.load_favorites()
        elif view_mode == "Styled":
            self.load_styled()
        elif view_mode == "Manual":
            self.load_manual()
        
        # Show status message
        if status_msg:
            self.status_var.set(status_msg)
        elif tag_filter:
            self.status_var.set(f'{view_mode} filtered by tag: {effective_tag}')
        else:
            self.status_var.set(f'{view_mode} reloaded (no tag filter)')

    def _refresh_gallery_tag_filter(self):
        """Refresh tag list and reload current view with tag filtering applied.
        Delegates to _refresh_tag_ui for consistency."""
        self._refresh_tag_ui(status_msg=None, keep_selection=True)

        

    def clear_image(self):

        """Clear the preview image from the left panel."""

        self.last_image_tk = None

        self.image_label.config(image='', text='Selected or generated image will appear here')

        self.preview_source_label.config(text="Nothing selected yet")

        self.preview_name_label.config(text="")

        self.preview_dims_label.config(text="")

        self.preview_size_label.config(text="")

    def open_style_dialog(self):

        """Open the style transfer dialog for the selected image."""

        if not self.selected_gallery_path:

            self._dialog.warning("No Selection", "Please select an image from the gallery first.")

            return

        

        if not self._ensure_style_transfer():

            self._dialog.error("Style Transfer Not Available", "Style transfer requires OpenCV. Please install it with: pip install opencv-python")

            return

        

        # Create style dialog

        style_dialog = tk.Toplevel(self.root)

        style_dialog.title("Apply Artistic Style")

        style_dialog.geometry("560x780")

        style_dialog.minsize(520, 640)

        style_dialog.transient(self.root)

        style_dialog.grab_set()

        

        # Style selection (packed first → stays at top)

        style_frame = ttk.LabelFrame(style_dialog, text="Apply Artistic Style:", padding=10)

        style_frame.pack(fill="x", padx=10, pady=10)

        

        self.selected_style_var = tk.StringVar(value="original")

        

        # Create radio buttons for styles

        styles = [

            ("original", "Original (no filter)"),

            ("oil_painting", "Oil Painting (thick brushstrokes)"),

            ("watercolor", "Watercolor (soft edges)"),

            ("sketch", "Sketch (line art)"),

            ("line_art", "Line Art (high contrast)"),

            ("comic_book", "Comic Book (bold lines)"),

            ("manga", "Manga (clean lines)"),

            ("sepia", "Sepia (warm brown tones)"),

            ("bw", "B&W (grayscale)"),

            ("vintage", "Vintage (aged look)"),

            ("posterize", "Posterize (reduced colors)"),

            ("emboss", "Emboss (3D relief)"),

            ("edge_enhance", "Edge Enhance (sharpened)"),

        ]

        

        for i, (style_value, style_name) in enumerate(styles):

            row = i // 2

            col = (i % 2) * 2

            ttk.Radiobutton(style_frame, text=style_name, variable=self.selected_style_var, value=style_value).grid(row=row, column=col, sticky="w", padx=5, pady=2)

        

        # Buttons at bottom (packed before preview so preview fills space between top and bottom)

        button_frame = ttk.Frame(style_dialog)

        button_frame.pack(side="bottom", fill="x", padx=10, pady=(4, 12))

        ttk.Button(button_frame, text="Apply Style", command=lambda: self.apply_selected_style(style_dialog)).pack(side="right", padx=5)

        ttk.Button(button_frame, text="Cancel", command=style_dialog.destroy).pack(side="right", padx=5)



        # Preview fills remaining height between style list and buttons

        preview_frame = ttk.LabelFrame(style_dialog, text="Preview:", padding=10)

        preview_frame.pack(fill="both", expand=True, padx=10, pady=10)

        

        try:

            from PIL import Image, ImageTk

            img = Image.open(self.selected_gallery_path)

            img.thumbnail((480, 220))

            photo = ImageTk.PhotoImage(img)

            self.preview_label = tk.Label(preview_frame, image=photo)

            self.preview_label.image = photo

            self.preview_label.pack()

            ttk.Label(preview_frame, text="Original image selected", font=self.small_font).pack(pady=5)

        except Exception as e:

            ttk.Label(preview_frame, text=f"Could not load preview: {e}").pack()

    

    def apply_selected_style(self, dialog):

        """Apply the selected style to the image."""

        style = self.selected_style_var.get()

        

        if style == "original":

            self._dialog.info("Style Transfer", "No style selected. Using original image.")

            dialog.destroy()

            return

        

        # Show progress

        self.status_var.set(f"Applying {style} style... (this may take 10-20 seconds)")

        dialog.destroy()

        

        # Apply style in a separate thread to avoid freezing UI

        import threading

        thread = threading.Thread(target=self._apply_style_thread, args=(style,))

        thread.daemon = True

        thread.start()

    

    def _apply_style_thread(self, style):

        """Apply style in a separate thread."""

        try:

            # Update status for image loading

            self.root.after(0, lambda: self.status_var.set(f"Loading image for {style} style..."))

            

            from style_transfer import apply_style_to_image

            

            # Update status for processing

            self.root.after(0, lambda: self.status_var.set(f"Processing {style} style..."))

            

            styled_path = apply_style_to_image(self.selected_gallery_path, style)

            

            if styled_path:

                # Update status for success

                self.root.after(0, lambda: self.status_var.set(f"✅ {style} style applied successfully!"))

                # Update UI from main thread

                self.root.after(0, self._style_applied_success, styled_path, style)

            else:

                # Update status for failure

                self.root.after(0, lambda: self.status_var.set(f"❌ {style} style failed - no image created"))

                self.root.after(0, self._style_applied_failed, style)

                

        except Exception as e:

            # Update status for error - avoid threading issues

            try:

                self.root.after(0, lambda: self.status_var.set(f"❌ Style transfer error: {str(e)}"))

                self.root.after(0, self._style_applied_error, str(e))

            except:

                # Fallback if root is no longer valid

                print(f"Style transfer error (UI update failed): {str(e)}")

    

    def _style_applied_success(self, styled_path, style):

        """Update UI after successful style application."""

        self.status_var.set(f"✅ {style} style applied!")

        self.load_gallery()

        

        # Show the styled image in preview

        self.show_preview_in_left_panel(styled_path, f"Styled image: {style}")

        

        # Ask if user wants to set as wallpaper

        result = self._dialog.ask("Style Applied", f"Style '{style}' applied successfully!\n\nWould you like to set this styled image as wallpaper?")

        if result:

            self.selected_gallery_path = styled_path

            self.set_gallery_selection()



    def toggle_fullscreen(self, event=None):
        """Toggle fullscreen mode and hide/show the bottom bar."""
        self.is_fullscreen = not self.is_fullscreen
        self.root.attributes("-fullscreen", self.is_fullscreen)

        if self.is_fullscreen:
            self.bottom_bar.pack_forget()
        else:
            self.bottom_bar.pack(fill="x", pady=(10, 0))

        self.status_var.set(f"Fullscreen: {'ON' if self.is_fullscreen else 'OFF'}")

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
                print(f"Error updating tray menu: {e}")

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
            self.root.destroy()

    def _style_applied_failed(self, style):
        """Handle failed style application."""
        self.status_var.set(f"❌ Failed to apply style '{style}' - no image created")
        self._dialog.error(
            "Style Transfer Failed",
            f"Could not apply style '{style}'.\n\n"
            f"Possible causes:\n"
            f"• Image file is corrupted or unsupported\n"
            f"• OpenCV libraries missing\n"
            f"• Insufficient memory for processing\n\n"
            f"Please check the image file and try again."
        )

    def _style_applied_error(self, error):
        """Handle style application error."""
        self.status_var.set(f"❌ Style transfer error: {error}")
        self._dialog.error(
            "Style Transfer Error",
            f"An error occurred during style transfer:\n\n{error}\n\n"
            f"This could be due to:\n"
            f"• Missing OpenCV installation\n"
            f"• Corrupted image file\n"
            f"• Insufficient system resources\n\n"
            f"Please try installing OpenCV: pip install opencv-python"
        )
    def _build_demoted_theme_builder(self, parent):
        """Build compact left-panel navigation shell. Prompt Builder Quick Build is the real editor."""
        card = ttk.Labelframe(parent, text="Prompt Builder", padding=(10, 8))
        card.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        card.columnconfigure(0, weight=1)

        hint = ttk.Label(
            card,
            text="Build and edit prompts in the Prompt Builder tab.",
            wraplength=300,
            justify="left",
        )
        hint.grid(row=0, column=0, sticky="w", pady=(0, 8))

        ttk.Button(
            card,
            text="Open Prompt Builder →",
            command=self.activate_prompt_builder_tab,
        ).grid(row=1, column=0, sticky="w")

    def _build_theme_builder_panel(self, parent, *, assign_refs=True, title="Theme Builder", refs=None):
        """Build the Theme Builder controls on the provided parent."""
        if title is None:
            controls_card = ttk.Frame(parent)
            controls_card.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        else:
            controls_card = ttk.Labelframe(parent, text=title, padding=10)
            controls_card.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        controls_card.columnconfigure(1, weight=1)

        def _store(name, widget):
            if assign_refs:
                setattr(self, name, widget)
            if refs is not None:
                refs[name] = widget

        ttk.Label(controls_card, text="Subject:", width=10, anchor="w").grid(row=1, column=0, sticky="w", padx=(0, 2), pady=(0, 8))
        subject_entry = ttk.Combobox(controls_card, width=26, values=THEME_VARIABLE_OPTIONS["subject"])
        subject_entry.grid(row=1, column=1, sticky="ew", pady=(0, 8))
        subject_entry.insert(0, "frog")
        self.configure_entry_cursor(subject_entry)
        subject_entry.bind("<MouseWheel>", lambda e: "break")
        subject_entry.bind("<Button-4>", lambda e: "break")
        subject_entry.bind("<Button-5>", lambda e: "break")
        _store("subject_entry", subject_entry)

        # Setting field (location/structure) - default to first non-empty option
        ttk.Label(controls_card, text="Setting:", width=10, anchor="w").grid(row=2, column=0, sticky="w", padx=(0, 2), pady=(0, 8))
        setting_entry = ttk.Combobox(controls_card, width=26, values=THEME_VARIABLE_OPTIONS["setting"])
        setting_entry.grid(row=2, column=1, sticky="ew", pady=(0, 8))
        # Default to first non-empty setting option (swamp)
        first_setting = [opt for opt in THEME_VARIABLE_OPTIONS["setting"] if opt]
        if first_setting:
            setting_entry.insert(0, first_setting[0])
        self.configure_entry_cursor(setting_entry)
        setting_entry.bind("<MouseWheel>", lambda e: "break")
        setting_entry.bind("<Button-4>", lambda e: "break")
        setting_entry.bind("<Button-5>", lambda e: "break")
        _store("setting_entry", setting_entry)

        # Row 3: Style | Mode  (render treatment — both affect output type)
        row2 = ttk.Frame(controls_card)
        row2.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        row2.columnconfigure(1, weight=1)
        row2.columnconfigure(3, weight=1)
        ttk.Label(row2, text="Style:", width=10, anchor="w").grid(row=0, column=0, sticky="w", padx=(0, 2))
        style_entry = ttk.Combobox(row2, width=14, values=THEME_VARIABLE_OPTIONS["style"])
        style_entry.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        style_entry.insert(0, "cyberpunk")
        self.configure_entry_cursor(style_entry)
        style_entry.bind("<MouseWheel>", lambda e: "break")
        style_entry.bind("<Button-4>", lambda e: "break")
        style_entry.bind("<Button-5>", lambda e: "break")
        _store("style_entry", style_entry)
        ttk.Label(row2, text="Mode:", width=10, anchor="w").grid(row=0, column=2, sticky="w", padx=(0, 2))
        mode_var = tk.StringVar(value=DEFAULT_PROMPT_MODE_LABEL)
        mode_combo = ttk.Combobox(
            row2,
            textvariable=mode_var,
            values=PROMPT_MODE_LABELS,
            width=15,
            state="readonly",
        )
        mode_combo.grid(row=0, column=3, sticky="ew")
        mode_combo.bind("<<ComboboxSelected>>", lambda e: self.update_mode_badge())
        mode_combo.bind("<MouseWheel>", lambda e: "break")
        mode_combo.bind("<Button-4>", lambda e: "break")
        mode_combo.bind("<Button-5>", lambda e: "break")
        if assign_refs:
            self.mode_var = mode_var
            self.mode_combo = mode_combo
        if refs is not None:
            refs["mode_var"] = mode_var
            refs["mode_combo"] = mode_combo

        # Row 4: Lighting | Mood  (scene feel — both affect atmosphere and emotional tone)
        row3 = ttk.Frame(controls_card)
        row3.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        row3.columnconfigure(1, weight=1)
        row3.columnconfigure(3, weight=1)
        ttk.Label(row3, text="Lighting:", width=10, anchor="w").grid(row=0, column=0, sticky="w", padx=(0, 2))
        lighting_entry = ttk.Combobox(row3, width=14, values=THEME_VARIABLE_OPTIONS["lighting"])
        lighting_entry.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        lighting_entry.insert(0, "neon")
        self.configure_entry_cursor(lighting_entry)
        lighting_entry.bind("<MouseWheel>", lambda e: "break")
        lighting_entry.bind("<Button-4>", lambda e: "break")
        lighting_entry.bind("<Button-5>", lambda e: "break")
        _store("lighting_entry", lighting_entry)

        row4 = ttk.Frame(controls_card)
        row4.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        row4.columnconfigure(1, weight=1)
        row4.columnconfigure(3, weight=1)

        # Color family / variation options — sourced from module-level constants
        color_families = COLOR_FAMILIES
        color_variations = COLOR_VARIATIONS

        ttk.Label(row4, text="Color:", width=10, anchor="w").grid(row=0, column=0, sticky="w", padx=(0, 2))
        color_family_var = tk.StringVar(value="")
        color_family_combo = ttk.Combobox(row4, textvariable=color_family_var, width=14, values=color_families, state="readonly")
        color_family_combo.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        color_family_combo.bind("<MouseWheel>", lambda e: "break")
        color_family_combo.bind("<Button-4>", lambda e: "break")
        color_family_combo.bind("<Button-5>", lambda e: "break")

        ttk.Label(row4, text="Modifier:", width=10, anchor="w").grid(row=0, column=2, sticky="w", padx=(0, 2))
        color_variation_var = tk.StringVar(value="")
        color_variation_combo = ttk.Combobox(row4, textvariable=color_variation_var, width=14, values=color_variations, state="readonly")
        color_variation_combo.grid(row=0, column=3, sticky="ew")
        color_variation_combo.bind("<MouseWheel>", lambda e: "break")
        color_variation_combo.bind("<Button-4>", lambda e: "break")
        color_variation_combo.bind("<Button-5>", lambda e: "break")

        _store("color_family_var", color_family_var)
        _store("color_family_combo", color_family_combo)
        _store("color_variation_var", color_variation_var)
        _store("color_variation_combo", color_variation_combo)

        # Atmosphere row — full-width, same grid as Subject/Setting/Negative
        ttk.Label(controls_card, text="Atmosphere:", width=10, anchor="w").grid(row=6, column=0, sticky="w", padx=(0, 2), pady=(0, 8))
        first_atmosphere = [opt for opt in THEME_VARIABLE_OPTIONS.get("atmosphere", []) if opt]
        default_atm = first_atmosphere[0] if first_atmosphere else ""
        atmosphere_var = tk.StringVar(value=default_atm)
        atmosphere_combo = ttk.Combobox(controls_card, textvariable=atmosphere_var, width=26,
                                        values=THEME_VARIABLE_OPTIONS.get("atmosphere", [""]),
                                        state="readonly")
        atmosphere_combo.grid(row=6, column=1, sticky="ew", pady=(0, 8))
        atmosphere_combo.bind("<MouseWheel>", lambda e: "break")
        atmosphere_combo.bind("<Button-4>", lambda e: "break")
        atmosphere_combo.bind("<Button-5>", lambda e: "break")
        _store("atmosphere_var", atmosphere_var)
        _store("atmosphere_combo", atmosphere_combo)

        # Negative prompt (row number updated)
        ttk.Label(controls_card, text="Negative:", width=10, anchor="w").grid(row=7, column=0, sticky="nw", padx=(0, 2))
        negative_prompt_var = tk.StringVar(value=DEFAULT_NEGATIVE_PROMPT)
        negative_prompt_entry = ttk.Entry(controls_card, textvariable=negative_prompt_var, width=72)
        negative_prompt_entry.grid(row=7, column=1, sticky="ew", pady=(0, 8))
        self.configure_entry_cursor(negative_prompt_entry)
        negative_prompt_entry.bind("<MouseWheel>", lambda e: "break")
        negative_prompt_entry.bind("<Button-4>", lambda e: "break")
        negative_prompt_entry.bind("<Button-5>", lambda e: "break")
        if assign_refs:
            self.negative_prompt_var = negative_prompt_var
            self.negative_prompt_entry = negative_prompt_entry
        if refs is not None:
            refs["negative_prompt_var"] = negative_prompt_var
            refs["negative_prompt_entry"] = negative_prompt_entry

        return controls_card

    def build_prompt_builder_tab(self, parent):
        """Create the Prompt Builder tab."""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        # ── Scrollable canvas wrapper ─────────────────────────────────────────
        canvas = tk.Canvas(parent, highlightthickness=0)
        scroll = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas, style="Inner.TFrame")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        _pb_win = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(_pb_win, width=e.width))
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner.columnconfigure(0, weight=1)
        self.prompt_builder_canvas = canvas

        # ── Quick Build Prompts ──────────────────────────────────────────────────────
        qb_frame = ttk.LabelFrame(inner, text="Quick Build Prompts", padding=(10, 6))
        qb_frame.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        qb_frame.columnconfigure(0, weight=1)

        self.prompt_builder_quick_refs = {}
        self._build_theme_builder_panel(
            qb_frame,
            assign_refs=False,
            title=None,
            refs=self.prompt_builder_quick_refs,
        )

        ttk.Separator(qb_frame, orient="horizontal").grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(4, 6))
        qb_actions = ttk.Frame(qb_frame)
        qb_actions.grid(row=2, column=0, columnspan=2, sticky="w")
        ttk.Button(qb_actions, text="🎲 Generate Prompt",
                   command=self.generate).pack(side="left", padx=(0, 6))
        ttk.Button(qb_actions, text="🎰 Random Prompt",
                   command=self.random_theme).pack(side="left", padx=(0, 6))
        ttk.Button(qb_actions, text="Save Quick Prompt",
                   command=self.save_as_quick_recipe).pack(side="left", padx=(0, 6))

        self.prompt_builder_quick_container = qb_frame
        self.prompt_builder_mode_var = tk.StringVar(value="Quick Build Prompts")

        # ── Checkboxes: Subject Lock + Prompt Audit on one row ───────────────
        checks_frame = ttk.Frame(inner)
        checks_frame.grid(row=3, column=0, sticky="w", pady=(4, 4))
        # Use existing vars from sidebar if already created
        if not hasattr(self, 'subject_lock_var'):
            self.subject_lock_var = tk.BooleanVar(value=True)
        subject_lock_check = ttk.Checkbutton(checks_frame, text="Keep Typed Subject Literal",
                                              variable=self.subject_lock_var)
        subject_lock_check.pack(side="left", padx=(0, 18))
        self.prompt_builder_quick_refs["subject_lock_var"] = self.subject_lock_var
        self.prompt_builder_quick_refs["subject_lock_check"] = subject_lock_check
        self.subject_lock_check = subject_lock_check

        if not hasattr(self, 'prompt_audit_var'):
            self.prompt_audit_var = tk.BooleanVar(value=False)
        prompt_audit_check = ttk.Checkbutton(checks_frame, text="Show Prompt Variable Audit",
                                              variable=self.prompt_audit_var)
        prompt_audit_check.pack(side="left")
        self.prompt_builder_quick_refs["prompt_audit_var"] = self.prompt_audit_var
        self.prompt_builder_quick_refs["prompt_audit_check"] = prompt_audit_check
        self.prompt_audit_check = prompt_audit_check

        ttk.Separator(inner, orient="horizontal").grid(row=4, column=0, sticky="ew", pady=(6, 8))

        # ── Progress Bar (skip if already created in center panel) ────────────
        if not hasattr(self, 'progress'):
            progress_frame = ttk.Frame(inner, height=20)
            progress_frame.grid(row=6, column=0, sticky="ew", pady=(0, 6))
            progress_frame.grid_propagate(False)
            progress_frame.columnconfigure(0, weight=1)
            progress_frame.rowconfigure(0, weight=1)
            self.progress = ttk.Progressbar(progress_frame, mode="determinate", maximum=100)
            self.progress.grid(row=0, column=0, sticky="nsew")
            self.progress.grid_remove()
            self.progress_overlay_label = tk.Label(progress_frame, text="", font=self.small_font, anchor="center")
            self.progress_overlay_label.place(relx=0.5, rely=0.5, anchor="center")
            self.progress_overlay_label.place_forget()

        # ── Prompt Preview (skip if already created in center panel) ────────
        if not hasattr(self, 'prompt_text'):
            preview_frame = ttk.LabelFrame(inner, text="Prompt Preview", padding=(10, 6))
            preview_frame.grid(row=8, column=0, sticky="ew", pady=(0, 8))
            preview_frame.columnconfigure(0, weight=1)
            preview_frame.columnconfigure(1, weight=0)

            self.mode_badge = ttk.Label(preview_frame,
                                        text=f"Mode: {DEFAULT_PROMPT_MODE_LABEL} | Subject lock: ON")
            self.mode_badge.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))

            # Image/output actions — pinned at top for immediate visibility
            img_actions = ttk.Frame(preview_frame)
            img_actions.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 6))

            ttk.Button(img_actions, text="🖼️ Generate Image",
                       command=self.generate_selected_image).pack(side="left", padx=(0, 6))
            ttk.Button(img_actions, text="🚀 Set as Wallpaper",
                       command=self.generate_and_set).pack(side="left", padx=(0, 6))
            ttk.Button(img_actions, text="❌ Cancel",
                       command=self.cancel_generation).pack(side="left")

            ttk.Separator(preview_frame, orient="horizontal").grid(
                row=2, column=0, columnspan=2, sticky="ew", pady=(6, 6))

            _pt_scroll = ttk.Scrollbar(preview_frame, orient="vertical")
            self.prompt_text = tk.Text(
                preview_frame, wrap="word", font=self.mono_font, height=6,
                yscrollcommand=_pt_scroll.set,
            )
            _pt_scroll.config(command=self.prompt_text.yview)
            self.prompt_text.grid(row=3, column=0, sticky="nsew")
            _pt_scroll.grid(row=3, column=1, sticky="ns")
            self.prompt_text.config(state="disabled")
            self.prompt_text.bind("<MouseWheel>", lambda e: self._on_prompt_text_scroll(e))
            self.prompt_text.bind("<Button-4>", lambda e: self._on_prompt_text_scroll(e))
            self.prompt_text.bind("<Button-5>", lambda e: self._on_prompt_text_scroll(e))

        ttk.Separator(inner, orient="horizontal").grid(row=8, column=0, sticky="ew", pady=(6, 8))

        # ── Recipe Library (collapsible) ─────────────────────────────────────
        recipe_lib_container = ttk.Frame(inner)
        recipe_lib_container.grid(row=9, column=0, sticky="ew", pady=(0, 4))
        recipe_lib_container.columnconfigure(0, weight=1)

        # Recipe Library action buttons (Session only)
        recipe_actions = ttk.Frame(inner)
        recipe_actions.grid(row=10, column=0, sticky="ew", pady=(0, 8))
        
        session_frame = ttk.LabelFrame(recipe_actions, text="Session", padding=(4, 2))
        session_frame.pack(side="right")
        ttk.Button(session_frame, text="💾 Save", command=self.save_session).pack(side="left", padx=2)
        ttk.Button(session_frame, text="📂 Load", command=self.load_session).pack(side="left", padx=2)

        # Header with toggle
        recipe_header = ttk.Frame(recipe_lib_container)
        recipe_header.pack(fill="x", pady=(0, 4))
        ttk.Label(recipe_header, text="📚 Quick Prompt Library", font=self.bold_font).pack(side="left")
        self.recipe_lib_expanded = tk.BooleanVar(value=False)
        ttk.Checkbutton(recipe_header, text="Show", variable=self.recipe_lib_expanded,
                       command=self._toggle_recipe_library).pack(side="right")

        # Content frame (toggleable)
        self.recipe_lib_content = ttk.Frame(recipe_lib_container)
        # Initially hidden, built when expanded
        self._recipe_lib_built = False

        self.prompt_builder_template_container = recipe_lib_container

    def update_prompt_builder_mode(self):
        """No-op: Quick Build and Recipe Library are always visible together."""
        self.update_mode_badge()

    def _on_notebook_tab_changed(self, event=None):
        self.update_prompt_builder_mode()

    def _open_settings_window(self):
        """Open Settings in a modal Toplevel window, building content fresh."""
        if hasattr(self, "_settings_win") and self._settings_win and self._settings_win.winfo_exists():
            self._settings_win.lift()
            self._settings_win.focus_force()
            return

        win = tk.Toplevel(self.root)
        win.title("FrogPaper — Settings")
        win.geometry("700x600")
        win.transient(self.root)
        win.grab_set()
        self._settings_win = win

        # Build settings content directly inside this window
        container = ttk.Frame(win)
        container.pack(fill="both", expand=True)
        self._build_settings_tab(container)

        def _on_close():
            win.grab_release()
            win.destroy()
            self._settings_win = None

        win.protocol("WM_DELETE_WINDOW", _on_close)

    def _open_recipe_window(self):
        """Open Recipe Library in a modal Toplevel window."""
        if hasattr(self, "_recipe_win") and self._recipe_win and self._recipe_win.winfo_exists():
            self._recipe_win.lift()
            self._recipe_win.focus_force()
            return

        win = tk.Toplevel(self.root)
        win.title("FrogPaper — Recipe Library")
        win.geometry("750x550")
        win.transient(self.root)
        win.grab_set()
        self._recipe_win = win

        container = ttk.Frame(win, padding=10)
        container.pack(fill="both", expand=True)

        self._build_templates_tab(container)
        self.refreshtemplatelist()

        def _on_close():
            win.grab_release()
            win.destroy()
            self._recipe_win = None

        win.protocol("WM_DELETE_WINDOW", _on_close)

    def _toggle_recipe_library(self):
        """Toggle Recipe Library visibility."""
        if not self.recipe_lib_expanded.get():
            self.recipe_lib_content.pack_forget()
            return

        # Build content if not already built
        if not self._recipe_lib_built:
            self._build_templates_tab(self.recipe_lib_content)
            self._recipe_lib_built = True

        self.recipe_lib_content.pack(fill="x", expand=True, pady=(4, 0))
        self.refreshtemplatelist()

    def _build_templates_tab(self, parent):
        try:
            from template_system import get_template_manager, get_recipe_manager, Template, Recipe
            self.template_manager = get_template_manager()
            self.recipe_manager = get_recipe_manager()
            self.template_available = True
            self.TemplateClass = Template
            self.RecipeClass = Recipe
        except ImportError as e:
            self.template_available = False
            self.template_manager = None
            self.recipe_manager = None
            self.TemplateClass = None
            self.RecipeClass = None
            print("Template import failed:", e)

        self.templatemanager = self.template_manager
        self.recipemanager = self.recipe_manager
        self.templateavailable = self.template_available

        selectorframe = ttk.LabelFrame(parent, text="Select & Manage", padding=10)
        selectorframe.pack(fill="x", pady=(0, 10))

        row1 = ttk.Frame(selectorframe)
        row1.pack(fill="x", pady=(0, 6))

        ttk.Label(row1, text="Prompt:").pack(side="left", padx=(0, 6))
        self.template_var = tk.StringVar(value="")
        self.templatevar = self.template_var

        self.template_combo = ttk.Combobox(
            row1,
            textvariable=self.template_var,
            width=34,
            state="readonly",
        )
        self.templatecombo = self.template_combo
        self.template_combo.pack(side="left", padx=(0, 8))
        self.template_combo.bind("<<ComboboxSelected>>", self.ontemplateselected)

        ttk.Button(row1, text="🔄 Refresh",
                   command=self.refreshtemplatelist).pack(side="left", padx=(0, 0))

        row2 = ttk.Frame(selectorframe)
        row2.pack(fill="x", pady=(6, 0))

        ttk.Button(row2, text="📥 Import Prompts", command=self.import_templates).pack(side="left", padx=(0, 6))
        ttk.Button(row2, text="📤 Export Prompts", command=self.export_templates).pack(side="left", padx=(0, 6))
        ttk.Button(row2, text="🗑 Delete Selected", command=self.delete_template).pack(side="left", padx=(0, 6))

        self.template_detail_var = tk.StringVar(value="")
        ttk.Label(
            selectorframe,
            textvariable=self.template_detail_var,
            font=self.small_font,
            foreground="#555555",
        ).pack(anchor="w", pady=(6, 0))

        # Template variable UI removed - now auto-loads into Quick Build
        self.template_variable_widgets = {}

        self.refreshtemplatelist()

    def ontemplateselected(self, event=None):
        """Handle recipe selection — update detail label and auto-load into Quick Build."""
        template_name = self.template_var.get()
        if not template_name:
            return
        self._update_template_detail_label()
        self.load_selected_recipe_into_quick_build()

    def load_selected_recipe_into_quick_build(self):
        """Load the selected Recipe Library entry into the Quick Build form."""
        template_name = self.template_var.get()
        if not template_name:
            return
        recipe = None
        if self.recipe_manager:
            recipe = self.recipe_manager.get_recipe(template_name)
        if recipe is None and self.template_manager:
            legacy = self.template_manager.get_template(template_name)
            if legacy:
                from template_system import Recipe
                recipe = Recipe.from_template(legacy)
        if recipe is None:
            self._dialog.warning("Not Found", f"Could not find prompt: {template_name}")
            return
        self._load_quick_recipe_to_theme_builder(recipe)

    def load_selected_prompt_from_library(self):
        """Explicit Load button handler — validates selection then loads into Quick Build."""
        if not hasattr(self, "template_var") or not self.template_var.get():
            self._dialog.warning("No Selection", "Select a prompt from the library first.")
            return
        self.load_selected_recipe_into_quick_build()

    def loadtemplate(self):
        """Load selected template/recipe and show variable dropdowns."""
        template_name = self.template_var.get()

        if not template_name or not self.template_available:
            return

        # Try RecipeManager first (new unified system), fall back to TemplateManager
        if self.recipe_manager:
            recipe = self.recipe_manager.get_recipe(template_name)
            if recipe:
                self._load_recipe(recipe)
                return

        # Fall back to old TemplateManager for backward compatibility
        if self.template_manager:
            template = self.template_manager.get_template(template_name)
            if template:
                self._load_template_legacy(template)
                return

    def _load_recipe(self, recipe):
        """Load a Recipe object (new unified system)."""
        self.template_variable_widgets = {}
        # Recipe auto-loads into Quick Build instead of showing variable UI
        self._load_quick_recipe_to_theme_builder(recipe)
        self.status_var.set(f"Loaded prompt: {recipe.name}")

    def _load_template_legacy(self, template):
        """Load a Template object (legacy system) - auto-converts to Quick Build."""
        self.template_variable_widgets = {}
        # Convert legacy template to Recipe and load into Quick Build
        from template_system import Recipe
        recipe = Recipe.from_template(template)
        self._load_quick_recipe_to_theme_builder(recipe)
        self.status_var.set(f"Loaded template: {template.name}")

    def generatefromtemplate(self):
        """Generate themes from loaded template/recipe using current Quick Build fields."""
        template_name = self.template_var.get()

        if not template_name:
            self.status_var.set("No prompt selected. Choose one from Quick Prompt Library first.")
            return

        if not self.template_available:
            self.status_var.set("Prompt system is not available.")
            return

        # Set prompt_source to template when explicitly generating from template
        self.prompt_source = "template"

        # Try RecipeManager first (new unified system), fall back to TemplateManager
        try:
            if self.recipe_manager:
                recipe = self.recipe_manager.get_recipe(template_name)
                if recipe:
                    self._generate_from_recipe(recipe)
                    return

            # Fall back to old TemplateManager for backward compatibility
            if self.template_manager:
                template = self.template_manager.get_template(template_name)
                if template:
                    self._generate_from_template_legacy(template)
                    return

            self.status_var.set(f"Prompt not found: {template_name}")
        except Exception as e:
            self.status_var.set(f"Error generating from prompt: {e}")
            print(f"Error in generatefromtemplate: {e}")

    def _generate_from_recipe(self, recipe):
        """Generate themes from a Recipe object (new unified system) using Quick Build fields."""
        # Use Quick Build fields instead of template variables
        variable_values = {
            "subject": self.get_active_subject(),
            "style": self.get_active_style(),
            "lighting": self.get_active_lighting(),
            "mood": self.get_active_mood(),
            "color": self.get_active_color(),
        }

        expanded_prompt = recipe.expand(variable_values)
        mode = recipe.style_mode if recipe.style_mode else self.current_mode()
        theme_id = len(self.prompts) + 1

        # Create a theme entry
        theme_entry = {
            "theme_id": theme_id,
            "style_mode": mode,
            "theme_sentence": f"Recipe: {recipe.name}",
            "prompt": expanded_prompt,
            "negative_prompt": recipe.negative_prompt if recipe.negative_prompt else self.get_active_negative_prompt(),
            "subject": recipe.quick_fields.get("subject", "") if recipe.quick_fields else self.get_active_subject(),
            "art_style": recipe.quick_fields.get("style", "") if recipe.quick_fields else self.get_active_style(),
        }

        # Add to themes and prompts
        self.themes.append(theme_entry)
        self.prompts.append(theme_entry)

        # Apply negative prompt if configured
        self.apply_negative_prompt_to_prompts()

        self.current_prompt_data = theme_entry
        self.show_prompt()
        self.activate_generator_tab()
        self.status_var.set(f"Generated theme from prompt: {recipe.name}")

    def _generate_from_template_legacy(self, template):
        """Generate themes from a Template object (legacy system) using Quick Build fields."""
        # Use Quick Build fields instead of template variables
        variable_values = {
            "subject": self.get_active_subject(),
            "style": self.get_active_style(),
            "lighting": self.get_active_lighting(),
            "mood": self.get_active_mood(),
            "color": self.get_active_color(),
        }

        expanded_prompt = template.expand(variable_values)
        mode = self.current_mode()
        theme_id = len(self.prompts) + 1

        # Create a theme entry
        theme_entry = {
            "theme_id": theme_id,
            "style_mode": mode,
            "theme_sentence": f"Template: {template.name}",
            "prompt": expanded_prompt,
            "negative_prompt": self.get_active_negative_prompt(),
            "subject": self.get_active_subject(),
            "art_style": self.get_active_style(),
        }

        # Add to themes and prompts
        self.themes.append(theme_entry)
        self.prompts.append(theme_entry)

        # Apply negative prompt if configured
        self.apply_negative_prompt_to_prompts()

        self.current_prompt_data = theme_entry
        self.show_prompt()
        self.activate_generator_tab()
        self.status_var.set(f"Generated theme from template: {template.name}")

    def refreshtemplatelist(self):
        """Refresh the template/recipe library display."""
        if not self.template_available:
            return
        self._refresh_template_library()

    def _refresh_template_library(self):
        """Refresh template library display while preserving selection."""
        if not self.template_available:
            return

        current = self.template_var.get()
        
        # Only show quick-type recipes (Quick Build snapshots); skip legacy template-variable entries
        if self.recipe_manager:
            recipes = [r for r in self.recipe_manager.get_all_recipes() if getattr(r, "recipe_type", "quick") == "quick"]
            template_names = [r.name for r in recipes]
        else:
            template_names = []
        
        self.template_combo["values"] = template_names

        if current in template_names:
            self.template_var.set(current)
        else:
            self.template_var.set("")

        self._update_template_detail_label()

    def _update_template_detail_label(self):
        """Update the detail info label below the Template Library selector."""
        if not hasattr(self, "template_detail_var"):
            return

        name = self.template_var.get() if hasattr(self, "template_var") else ""
        if not name:
            self.template_detail_var.set("")
            return

        source = None
        if self.recipe_manager:
            source = self.recipe_manager.get_recipe(name)
        if source is None and self.template_manager:
            source = self.template_manager.get_template(name)

        if source is None:
            self.template_detail_var.set("")
            return

        # Build status badges
        builtin_badge = "Built-in" if source.is_builtin else "Custom"
        type_badge = getattr(source, "recipe_type", "template").title()
        badges = f"[{builtin_badge}]  {type_badge}"

        desc = (source.description or "").strip()
        if desc:
            # Truncate long descriptions
            if len(desc) > 80:
                desc = desc[:77] + "..."
            detail = f"{badges}  —  {desc}"
        else:
            detail = badges

        self.template_detail_var.set(detail)

    def resettemplatevariables(self):
        """Reset Quick Build fields to defaults."""
        # Reset Quick Build fields
        refs = self._get_pb_quick_refs()
        if refs:
            if "subject_entry" in refs:
                refs["subject_entry"].delete(0, tk.END)
                refs["subject_entry"].insert(0, "frog")
            if "style_entry" in refs:
                refs["style_entry"].delete(0, tk.END)
                refs["style_entry"].insert(0, "cyberpunk")
            if "lighting_entry" in refs:
                refs["lighting_entry"].delete(0, tk.END)
                refs["lighting_entry"].insert(0, "neon")
            if "mood_entry" in refs:
                refs["mood_entry"].delete(0, tk.END)
                refs["mood_entry"].insert(0, "epic")
            if "color_family_var" in refs:
                refs["color_family_var"].set("")
            if "color_variation_var" in refs:
                refs["color_variation_var"].set("")
        self.status_var.set("Quick Build fields reset to defaults")

    def _generate_template_name_from_prompt(self, prompt):
        """Auto-generate a template name from subject, variables, and style."""
        import re
        
        # Filler words to exclude
        filler_words = {
            "theme", "mode", "negative", "prompt", "quality", "wallpaper", 
            "generate", "image", "a", "an", "the", "of", "in", "on", "at", 
            "to", "and", "or", "with", "by", "for", "is", "as", "into", 
            "from", "very", "ultra", "highly"
        }
        
        # Collect name parts
        parts = []
        
        # 1. Use subject field if present
        subject = self.get_active_subject()
        if subject and subject.lower() not in filler_words:
            parts.append(subject.title())
        
        # 2. Extract and include variables from prompt
        variables = re.findall(r"\{(\w+)\}", prompt)
        for var in variables:
            if var.lower() not in filler_words:
                parts.append(f"{{{var}}}")
        
        # 3. Optionally include style if it adds clarity and we have room
        if len(parts) < 3:
            style = self.get_active_style()
            if style and style.lower() not in filler_words:
                # Only add if different from subject and not already implied
                if not parts or style.lower() != parts[0].lower():
                    parts.append(style.title())
        
        # 4. Fall back to cleaned prompt parsing if no parts yet
        if not parts:
            clean = re.sub(r"\{[^}]*\}", "", prompt)
            clean = re.sub(r"[^\w\s]", " ", clean)
            words = [w for w in clean.split() if w.lower() not in filler_words and len(w) > 2]
            parts = [w.title() for w in words[:3]]
        
        # 5. Limit to 2-4 meaningful parts
        if len(parts) > 4:
            parts = parts[:4]
        
        return " ".join(parts) if parts else "Custom Template"

    def _generate_template_description(self):
        """Generate a human-readable description from Quick Build fields."""
        parts = []
        
        # Get field values
        subject = self.get_active_subject()
        style = self.get_active_style()
        lighting = self.get_active_lighting()
        mood = self.get_active_mood()
        color = self.get_active_color()
        mode = self.get_active_mode_label()
        
        # Build description parts
        if mood and subject:
            parts.append(f"{mood} {subject}")
        elif subject:
            parts.append(subject)
        elif mood:
            parts.append(mood)
        
        if style:
            if parts:
                parts.append(f"in {style} style")
            else:
                parts.append(f"{style} style")
        
        if lighting:
            parts.append(f"with {lighting} lighting")
        
        if color:
            parts.append(f"{color} colors")
        
        if mode:
            parts.append(f"({mode} mode)")
        
        # Build final description
        if parts:
            description = " ".join(parts)
            # Capitalize first letter
            description = description[0].upper() + description[1:] if description else description
            # Add period if missing
            if description and not description.endswith('.'):
                description += "."
            return description
        else:
            return "Reusable wallpaper prompt template."

    def save_as_template(self):
        """Save current prompt as a new template."""
        current_prompt = self.get_prompt_text()
        if not current_prompt:
            self._dialog.warning("No Prompt", "Please generate or enter a prompt first.")
            return

        suggested_name = self._generate_template_name_from_prompt(current_prompt)
        suggested_desc = self._generate_template_description()

        dialog = tk.Toplevel(self.root)
        dialog.title("Save as New Prompt")
        dialog.geometry("480x320")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        header = ttk.Label(
            dialog,
            text="Save current prompt as a reusable prompt.",
            font=self.small_font,
            foreground="#666666",
        )
        header.pack(anchor="w", padx=14, pady=(12, 8))

        ttk.Label(dialog, text="Template Name  (subject & style):").pack(anchor="w", padx=14, pady=(0, 3))
        name_var = tk.StringVar(value=suggested_name)
        name_entry = ttk.Entry(dialog, textvariable=name_var, width=52)
        name_entry.pack(padx=14, pady=(0, 10), fill="x")
        self.configure_entry_cursor(name_entry)
        name_entry.icursor(tk.END)

        ttk.Label(dialog, text="Description  (shown in tooltip / dropdown):").pack(anchor="w", padx=14, pady=(0, 3))
        desc_var = tk.StringVar(value=suggested_desc)
        desc_entry = ttk.Entry(dialog, textvariable=desc_var, width=52)
        desc_entry.pack(padx=14, pady=(0, 10), fill="x")
        self.configure_entry_cursor(desc_entry)

        hint = ttk.Label(
            dialog,
            text="Tip: use {variable_name} in your prompt to create fill-in slots.",
            font=self.small_font,
            foreground="#888888",
        )
        hint.pack(anchor="w", padx=14, pady=(0, 12))

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=(0, 14))
        ttk.Button(
            button_frame,
            text="Save Prompt",
            command=lambda: self._save_template_dialog(name_var.get(), desc_var.get(), dialog),
        ).pack(side="left", padx=6)
        ttk.Button(
            button_frame,
            text="Cancel",
            command=dialog.destroy,
        ).pack(side="left", padx=6)

        name_entry.focus_set()
        name_entry.selection_range(0, tk.END)

    def _save_template_dialog(self, name, description, dialog):
        """Handle save template/recipe dialog submission."""
        current_prompt = self.get_prompt_text()
        name = (name or "").strip() or self._generate_template_name_from_prompt(current_prompt)
        description = (description or "").strip()

        try:
            import re

            variables = {}
            # Collect current variable values from template variable widgets
            last_values = {}
            for var_name in re.findall(r"\{(\w+)\}", current_prompt):
                if var_name not in variables:
                    variables[var_name] = []
                # Get current value from widget if it exists
                if hasattr(self, 'template_variable_widgets') and var_name in self.template_variable_widgets:
                    widget = self.template_variable_widgets[var_name]
                    if hasattr(widget, 'get'):
                        value = widget.get()
                        if value:
                            last_values[var_name] = value
                            # Also add to options if not already present
                            if value not in variables[var_name]:
                                variables[var_name].append(value)

            # Try to save as Recipe first (new unified system)
            if self.recipe_manager:
                recipe = self.RecipeClass(
                    name=name,
                    description=description,
                    recipe_type="template",  # Save as template mode for text-based recipes
                    template_text=current_prompt,
                    variables=variables,
                    is_builtin=False,
                    last_values=last_values,
                    style_mode=self.current_mode(),
                    negative_prompt=self.get_active_negative_prompt(),
                    quick_fields={
                        "subject": self.get_active_subject(),
                        "style": self.get_active_style(),
                        "lighting": self.get_active_lighting(),
                        "mood": self.get_active_mood(),
                        "color": self.get_active_color(),
                        "subject_lock": self.get_active_subject_lock()
                    }
                )

                if self.recipe_manager.add_recipe(recipe):
                    self.status_var.set(f"Prompt '{name}' saved successfully!")
                    self.refreshtemplatelist()
                    dialog.destroy()
                    self._dialog.info("Saved", f"Prompt saved as:\n\n\"{name}\"")
                else:
                    # Fall back to TemplateManager if RecipeManager fails (e.g., name conflict)
                    if self.template_manager:
                        template = self.TemplateClass(
                            name=name,
                            description=description,
                            template_text=current_prompt,
                            variables=variables,
                            is_builtin=False,
                            last_values=last_values
                        )
                        if self.template_manager.add_template(template):
                            self.status_var.set(f"Template '{name}' saved successfully!")
                            self.refreshtemplatelist()
                            dialog.destroy()
                            self._dialog.info("Saved", f"Template saved as:\n\n\"{name}\"")
                        else:
                            self._dialog.error(
                                "Name Taken",
                                f"A template named '{name}' already exists.\nPlease choose a different name.",
                            )
                    else:
                        self._dialog.error(
                            "Name Taken",
                            f"A prompt named '{name}' already exists.\nPlease choose a different name.",
                        )
            else:
                # Fall back to old TemplateManager if RecipeManager is not available
                if self.template_manager:
                    template = self.TemplateClass(
                        name=name,
                        description=description,
                        template_text=current_prompt,
                        variables=variables,
                        is_builtin=False,
                        last_values=last_values
                    )
                    if self.template_manager.add_template(template):
                        self.status_var.set(f"Template '{name}' saved successfully!")
                        self.refreshtemplatelist()
                        dialog.destroy()
                        self._dialog.info("Saved", f"Template saved as:\n\n\"{name}\"")
                    else:
                        self._dialog.error(
                            "Name Taken",
                            f"A template named '{name}' already exists.\nPlease choose a different name.",
                        )

        except Exception as e:
            self._dialog.error("Error", f"Could not save template: {e}")



    # ── Working Session save / load ──────────────────────────────────────────

    def _collect_session_state(self):
        """Return a dict capturing the current Prompt Builder working state."""
        template_var_values = {}
        template_widgets = getattr(self, "template_variable_widgets", {}) or {}
        for var_name, widget in template_widgets.items():
            if hasattr(widget, "get"):
                try:
                    template_var_values[var_name] = widget.get()
                except Exception:
                    pass

        return {
            "subject": self.get_active_subject(),
            "style": self.get_active_style(),
            "lighting": self.get_active_lighting(),
            "mood": self.get_active_mood(),
            "color": self.get_active_color(),
            "atmosphere": self.get_active_atmosphere(),
            "mode": self.get_active_mode(),
            "subject_lock": self.get_active_subject_lock(),
            "negative_prompt": self.get_active_negative_prompt(),
            "pb_view": getattr(self, "prompt_builder_mode_var", tk.StringVar()).get(),
            "selected_template": self.template_var.get() if hasattr(self, "template_var") else "",
            "template_variable_values": template_var_values,
        }

    def _restore_session_state(self, state):
        """Apply a previously saved session state dict to the current Prompt Builder."""
        self.set_active_subject(state.get("subject", ""))
        self.set_active_style(state.get("style", ""))
        self.set_active_lighting(state.get("lighting", ""))
        self.set_active_mood(state.get("mood", ""))
        self.set_active_color(state.get("color", ""))
        self.set_active_atmosphere(state.get("atmosphere", ""))
        mode = state.get("mode", "")
        if mode:
            self.set_active_mode(mode)
        self.set_active_subject_lock(state.get("subject_lock", True))
        neg = state.get("negative_prompt", "")
        if neg:
            self.set_active_negative_prompt(neg)

        # Restore Prompt Builder view mode
        pb_view = state.get("pb_view", "")
        if pb_view and hasattr(self, "prompt_builder_mode_var"):
            self.prompt_builder_mode_var.set(pb_view)
            self.update_prompt_builder_mode()

        # Restore selected template and its variable values
        selected_template = state.get("selected_template", "")
        if selected_template and hasattr(self, "template_var"):
            # Only restore if the template still exists in the list
            names = list(self.template_combo["values"]) if hasattr(self, "template_combo") else []
            if selected_template in names:
                self.template_var.set(selected_template)
                self._update_template_detail_label()
                self.loadtemplate()
                # Now overwrite widget values with saved variable values
                saved_vars = state.get("template_variable_values", {})
                template_widgets = getattr(self, "template_variable_widgets", {}) or {}
                for var_name, value in saved_vars.items():
                    if var_name in template_widgets:
                        widget = template_widgets[var_name]
                        if hasattr(widget, "set"):
                            try:
                                widget.set(value)
                            except Exception:
                                pass

    def save_session(self):
        """Prompt for a session name and save current Prompt Builder state to sessions.json."""
        import json
        from datetime import datetime

        dialog = tk.Toplevel(self.root)
        dialog.title("Save Session")
        dialog.geometry("380x160")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Session name:").pack(anchor="w", padx=14, pady=(14, 0))
        _subj = (self.get_active_subject() or "").strip().title() or "Session"
        default_name = datetime.now().strftime(f"{_subj} %Y-%m-%d %H:%M")
        name_var = tk.StringVar(value=default_name)
        name_entry = ttk.Entry(dialog, textvariable=name_var, width=46)
        name_entry.pack(padx=14, pady=(4, 12), fill="x")
        self.configure_entry_cursor(name_entry)
        name_entry.selection_range(0, tk.END)
        name_entry.focus_set()

        def do_save():
            name = name_var.get().strip()
            if not name:
                self._dialog.warning("Name Required", "Please enter a session name.")
                return
            try:
                sessions = {}
                if SESSIONS_FILE.exists():
                    with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
                        sessions = json.load(f)
                sessions[name] = self._collect_session_state()
                with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
                    json.dump(sessions, f, indent=2)
                self.status_var.set(f"Session saved: '{name}'")
                dialog.destroy()
            except Exception as e:
                self._dialog.error("Save Error", f"Could not save session:\n{e}")

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack()
        ttk.Button(btn_frame, text="Save", command=do_save).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side="left", padx=6)

    def load_session(self):
        """Show a list of saved sessions and restore the selected one."""
        import json

        if not SESSIONS_FILE.exists():
            self._dialog.info("No Sessions", "No saved sessions found.")
            return

        try:
            with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
                sessions = json.load(f)
        except Exception as e:
            self._dialog.error("Load Error", f"Could not read sessions file:\n{e}")
            return

        if not sessions:
            self._dialog.info("No Sessions", "No saved sessions found.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Load Session")
        dialog.geometry("420x320")
        dialog.resizable(True, True)
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Select a session to restore:").pack(anchor="w", padx=14, pady=(14, 4))

        list_frame = ttk.Frame(dialog)
        list_frame.pack(padx=14, fill="both", expand=True, pady=(0, 8))
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical")
        session_list = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, selectmode="single", height=10)
        scrollbar.config(command=session_list.yview)
        session_list.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        session_names = list(sessions.keys())
        for sname in session_names:
            session_list.insert(tk.END, sname)
        if session_names:
            session_list.selection_set(0)

        def do_load():
            sel = session_list.curselection()
            if not sel:
                return
            chosen = session_names[sel[0]]
            state = sessions[chosen]
            try:
                self._restore_session_state(state)
                self.status_var.set(f"Session loaded: '{chosen}'")
                dialog.destroy()
            except Exception as e:
                self._dialog.error("Restore Error", f"Could not restore session:\n{e}")

        def do_delete():
            sel = session_list.curselection()
            if not sel:
                return
            chosen = session_names[sel[0]]
            if not self._dialog.ask("Delete Session", f"Delete session '{chosen}'?"):
                return
            try:
                del sessions[chosen]
                with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
                    json.dump(sessions, f, indent=2)
                session_list.delete(sel[0])
                session_names.pop(sel[0])
            except Exception as e:
                self._dialog.error("Delete Error", f"Could not delete session:\n{e}")

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=(0, 12))
        ttk.Button(btn_frame, text="Load", command=do_load).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="Delete", command=do_delete).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side="left", padx=6)

        session_list.bind("<Double-Button-1>", lambda e: do_load())
        session_list.focus_set()

    def _ensure_recipe_manager(self):
        """Lazy-initialize recipe_manager if not already set (handles Prompt Builder tab usage before Templates tab)."""
        if not hasattr(self, 'recipe_manager') or self.recipe_manager is None:
            try:
                from template_system import get_recipe_manager
                self.recipe_manager = get_recipe_manager()
            except Exception:
                self.recipe_manager = None
        return self.recipe_manager

    def save_as_quick_recipe(self):
        """Save the current Prompt Builder Quick Build configuration as a Quick Recipe."""
        self._ensure_recipe_manager()
        if not self.recipe_manager:
            self._dialog.warning("Prompt System", "Prompt system is not available.")
            return

        # If a built-in prompt is currently selected, inform the user their
        # changes will be saved as a new custom prompt (built-ins are protected).
        current_name = getattr(self, "template_var", None)
        current_name = current_name.get() if current_name else ""
        if current_name:
            existing = self.recipe_manager.get_recipe(current_name)
            if existing and getattr(existing, "is_builtin", False):
                self._dialog.info(
                    "Saving as New Prompt",
                    f"'{current_name}' is a built-in prompt and cannot be overwritten.\n\n"
                    "Your changes will be saved as a new custom prompt."
                )

        # Get current active quick-build values
        subject = self.get_active_subject()
        style = self.get_active_style()
        lighting = self.get_active_lighting()
        mood = self.get_active_mood()
        color = self.get_active_color()
        atmosphere = self.get_active_atmosphere()
        mode = self.get_active_mode()
        subject_lock = self.get_active_subject_lock()
        negative_prompt = self.get_active_negative_prompt()

        # Generate suggested name and description
        suggested_name = self._generate_quick_recipe_name(subject, style, mood, atmosphere)
        suggested_desc = self._generate_quick_recipe_description(subject, style, mood, lighting, atmosphere)

        # Create dialog for prompt name
        dialog = tk.Toplevel(self.root)
        dialog.title("Save Quick Prompt")
        dialog.geometry("480x280")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        header = ttk.Label(
            dialog,
            text="Save the current Prompt Builder Quick Build configuration as a Quick Prompt.",
            font=self.small_font,
            foreground="#666666",
        )
        header.pack(anchor="w", padx=14, pady=(12, 8))

        ttk.Label(dialog, text="Prompt Name:").pack(anchor="w", padx=14, pady=(0, 3))
        name_var = tk.StringVar(value=suggested_name)
        name_entry = ttk.Entry(dialog, textvariable=name_var, width=52)
        name_entry.pack(padx=14, pady=(0, 10), fill="x")
        self.configure_entry_cursor(name_entry)
        name_entry.icursor(tk.END)

        ttk.Label(dialog, text="Description:").pack(anchor="w", padx=14, pady=(0, 3))
        desc_var = tk.StringVar(value=suggested_desc)
        desc_entry = ttk.Entry(dialog, textvariable=desc_var, width=52)
        desc_entry.pack(padx=14, pady=(0, 10), fill="x")
        self.configure_entry_cursor(desc_entry)

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=(0, 14))
        ttk.Button(
            button_frame,
            text="Save Prompt",
            command=lambda: self._save_quick_recipe_dialog(name_var.get(), desc_var.get(), dialog, subject, style, lighting, mood, color, atmosphere, mode, subject_lock, negative_prompt),
        ).pack(side="left", padx=6)
        ttk.Button(
            button_frame,
            text="Cancel",
            command=dialog.destroy,
        ).pack(side="left", padx=6)

        name_entry.focus_set()
        name_entry.selection_range(0, tk.END)

    def _save_quick_recipe_dialog(self, name, description, dialog, subject, style, lighting, mood, color, atmosphere, mode, subject_lock, negative_prompt):
        """Handle save quick recipe dialog submission."""
        name = (name or "").strip() or self._generate_quick_recipe_name(subject, style, mood, atmosphere)
        description = (description or "").strip() or self._generate_quick_recipe_description(subject, style, mood, lighting, atmosphere)

        # Auto-number if the name is already taken: Name → Name 2 → Name 3 …
        base_name = name
        n = 2
        while self.recipe_manager.get_recipe(name) is not None:
            name = f"{base_name} {n}"
            n += 1

        try:
            recipe = self.RecipeClass(
                name=name,
                description=description,
                recipe_type="quick",  # Quick mode uses structured fields
                template_text="",  # No template text for quick mode
                variables={},  # No variables for quick mode
                is_builtin=False,
                last_values={},
                style_mode=mode,
                negative_prompt=negative_prompt,
                quick_fields={
                    "subject": subject,
                    "style": style,
                    "lighting": lighting,
                    "mood": mood,
                    "color": color,
                    "atmosphere": atmosphere,
                    "subject_lock": subject_lock
                }
            )

            self.recipe_manager.add_recipe(recipe)
            self.status_var.set(f"Quick Prompt '{name}' saved successfully!")
            dialog.destroy()
            self._dialog.info("Saved", f"Quick Prompt saved as:\n\n\"{name}\"")

        except Exception as e:
            self._dialog.error("Error", f"Could not save quick prompt: {e}")

    def _generate_quick_recipe_name(self, subject, style, mood, atmosphere=None):
        """Generate a recipe name from Quick Build fields."""
        parts = []
        if subject:
            parts.append(subject)
        if style:
            parts.append(style)
        if mood:
            parts.append(mood)
        # Include atmosphere if present and space allows
        if atmosphere and len(parts) < 3:
            parts.append(atmosphere.replace(" ", "-"))
        
        if parts:
            return " ".join(parts[:3]).title()
        else:
            return "Quick Prompt"

    def _generate_quick_recipe_description(self, subject, style, mood, lighting, atmosphere=None):
        """Generate a description from Quick Build fields."""
        parts = []
        if mood:
            parts.append(mood)
        if subject:
            parts.append(subject)
        if style:
            parts.append(f"in {style} style")
        if lighting:
            parts.append(f"with {lighting} lighting")
        if atmosphere:
            parts.append(f"with {atmosphere} atmosphere")
        
        if parts:
            description = " ".join(parts)
            description = description[0].upper() + description[1:] if description else description
            if description and not description.endswith('.'):
                description += "."
            return description
        else:
            return "Quick prompt with structured fields."

    def load_quick_recipe(self):
        """Load a Quick Recipe into Prompt Builder Quick Build controls."""
        self._ensure_recipe_manager()
        if not self.recipe_manager:
            self._dialog.warning("Prompt System", "Prompt system is not available.")
            return

        # Get all quick recipes
        quick_recipes = [r for r in self.recipe_manager.get_all_recipes() if r.recipe_type == "quick"]
        
        if not quick_recipes:
            self._dialog.info("No Quick Prompts", "No Quick Prompts found.\n\nUse \"Save Quick Prompt\" in the Prompt Builder tab to save one.")
            return

        # Create dialog to select a quick prompt
        dialog = tk.Toplevel(self.root)
        dialog.title("Load Quick Prompt")
        dialog.geometry("500x400")
        dialog.resizable(True, True)
        dialog.transient(self.root)
        dialog.grab_set()

        header = ttk.Label(
            dialog,
            text="Select a Quick Prompt to load into Prompt Builder Quick Build.",
            font=self.small_font,
            foreground="#666666",
        )
        header.pack(anchor="w", padx=14, pady=(12, 8))

        # Create listbox for prompts
        list_frame = ttk.Frame(dialog)
        list_frame.pack(fill="both", expand=True, padx=14, pady=(0, 10))

        recipe_listbox = tk.Listbox(list_frame, height=10)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=recipe_listbox.yview)
        recipe_listbox.configure(yscrollcommand=scrollbar.set)
        
        recipe_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Populate listbox
        for recipe in quick_recipes:
            recipe_listbox.insert(tk.END, recipe.name)

        # Description label
        desc_label = ttk.Label(dialog, text="", wraplength=460, foreground="#666666")
        desc_label.pack(fill="x", padx=14, pady=(0, 10))

        def on_select(event):
            selection = recipe_listbox.curselection()
            if selection:
                index = selection[0]
                recipe = quick_recipes[index]
                desc_label.config(text=f"{recipe.description}\n\nMode: {recipe.style_mode}")

        recipe_listbox.bind("<<ListboxSelect>>", on_select)

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=(0, 14))

        def do_load():
            selection = recipe_listbox.curselection()
            if selection:
                index = selection[0]
                recipe = quick_recipes[index]
                self._load_quick_recipe_to_theme_builder(recipe)
                dialog.destroy()
            else:
                self._dialog.warning("No Selection", "Please select a Quick Prompt to load.")

        ttk.Button(button_frame, text="Load", command=do_load).pack(side="left", padx=6)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side="left", padx=6)

    def _load_quick_recipe_to_theme_builder(self, recipe):
        """Load a Quick Recipe's fields into the active quick-build controls."""
        try:
            quick_fields = recipe.quick_fields or {}

            self.set_active_subject(quick_fields.get("subject", ""))
            self.set_active_style(quick_fields.get("style", ""))
            self.set_active_lighting(quick_fields.get("lighting", ""))
            self.set_active_mood(quick_fields.get("mood", ""))
            self.set_active_color(quick_fields.get("color", ""))
            self.set_active_atmosphere(quick_fields.get("atmosphere", ""))
            self.set_active_mode(recipe.style_mode or DEFAULT_PROMPT_MODE_VALUE)
            self.set_active_subject_lock(quick_fields.get("subject_lock", True))
            if recipe.negative_prompt:
                self.set_active_negative_prompt(recipe.negative_prompt)

            self.status_var.set(f"Loaded Quick Prompt: {recipe.name}")
            self.update_mode_badge()

        except Exception as e:
            self._dialog.error("Error", f"Could not load quick prompt: {e}")

    def delete_quick_recipe(self):
        """Delete the selected quick recipe after confirmation. Built-in recipes are protected."""
        if not self.recipe_manager:
            self._dialog.warning("Prompt System", "Prompt system is not available.")
            return

        # Get list of quick recipes
        quick_recipes = [r for r in self.recipe_manager.get_all_recipes() if r.recipe_type == "quick"]
        if not quick_recipes:
            self._dialog.info("No Quick Prompts", "No quick prompts to delete.")
            return

        # Create dialog to select a recipe to delete
        dialog = tk.Toplevel(self.root)
        dialog.title("Delete Prompt")
        dialog.geometry("400x300")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Select a prompt to delete:", font=("TkDefaultFont", 10, "bold")).pack(pady=(12, 8), padx=12, anchor="w")

        # Listbox for recipe selection
        list_frame = ttk.Frame(dialog)
        list_frame.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        recipe_list = tk.Listbox(list_frame, selectmode="single", height=10)
        recipe_list.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(list_frame, command=recipe_list.yview)
        scrollbar.pack(side="right", fill="y")
        recipe_list.config(yscrollcommand=scrollbar.set)

        # Populate list
        recipe_map = {}
        for recipe in quick_recipes:
            recipe_list.insert("end", recipe.name)
            recipe_map[recipe.name] = recipe

        def do_delete():
            selection = recipe_list.curselection()
            if not selection:
                self._dialog.warning("No Selection", "Please select a prompt to delete.")
                return
            recipe_name = recipe_list.get(selection[0])
            recipe = recipe_map.get(recipe_name)
            if not recipe:
                return

            # Protect built-in recipes
            if getattr(recipe, 'built_in', False) or getattr(recipe, 'is_builtin', False):
                self._dialog.info("Protected Prompt", f"'{recipe_name}' is a built-in prompt and cannot be deleted.")
                return

            # Confirm deletion
            if not self._dialog.ask("Confirm Delete", f"Are you sure you want to delete '{recipe_name}'?"):
                return

            # Delete the recipe
            try:
                if self.recipe_manager.delete_recipe(recipe_name):
                    # Only refresh template library if the Templates tab has been initialized
                    if hasattr(self, 'template_available') and self.template_available:
                        self._refresh_template_library()
                    self.status_var.set(f"Deleted prompt: {recipe_name}")
                    dialog.destroy()
                else:
                    self._dialog.error("Error", f"Could not delete prompt: {recipe_name}")
            except Exception as e:
                self._dialog.error("Error", f"Failed to delete prompt: {e}")

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Button(btn_frame, text="Delete", command=do_delete).pack(side="right", padx=(6, 0))
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side="right")

        recipe_list.focus_set()
        recipe_list.bind("<Double-Button-1>", lambda e: do_delete())

    def duplicate_template(self):
        """Create a custom editable copy of the selected template or recipe."""
        template_name = self.template_var.get()
        if not template_name or not self.template_available:
            self._dialog.warning("No Selection", "Please select a prompt to copy.")
            return

        if not self.recipe_manager:
            self._dialog.warning("Prompt System", "Prompt system is not available.")
            return

        # Resolve source: RecipeManager first, then TemplateManager legacy
        source = self.recipe_manager.get_recipe(template_name)
        if source is None and self.template_manager:
            legacy = self.template_manager.get_template(template_name)
            if legacy:
                from template_system import Recipe
                source = Recipe.from_template(legacy)

        if source is None:
            self._dialog.warning("Not Found", f"Could not find template: {template_name}")
            return

        # Build a unique copy name: "Name (Copy)", "Name (Copy 2)", ...
        base_copy_name = f"{source.name} (Copy)"
        copy_name = base_copy_name
        counter = 2
        while self.recipe_manager.get_recipe(copy_name) is not None:
            copy_name = f"{base_copy_name[:-1]} {counter})"
            counter += 1

        from template_system import Recipe
        copy = Recipe(
            name=copy_name,
            description=source.description,
            recipe_type=source.recipe_type if source.recipe_type else "template",
            template_text=source.template_text,
            variables=dict(source.variables) if source.variables else {},
            last_values=dict(source.last_values) if source.last_values else {},
            is_builtin=False,
            style_mode=source.style_mode if hasattr(source, "style_mode") else "stylized",
            negative_prompt=source.negative_prompt if hasattr(source, "negative_prompt") else "",
            quick_fields=dict(source.quick_fields) if hasattr(source, "quick_fields") and source.quick_fields else {},
        )

        ok = self.recipe_manager.add_recipe(copy)
        if not ok:
            self._dialog.error("Name Conflict", f"A custom prompt named '{copy_name}' already exists.")
            return

        self.refreshtemplatelist()

        # Auto-select the new copy
        names = list(self.template_combo["values"])
        if copy_name in names:
            self.template_var.set(copy_name)
            self.loadtemplate()

        self.status_var.set(f"Editable copy created: '{copy_name}'")

    def import_templates(self):
        """Import one or more templates/recipes from a JSON file (single or list format)."""
        if not self.template_available:
            self._dialog.warning("Template System", "Template system is not available.")
            return
        
        from tkinter import filedialog
        import json
        from pathlib import Path
        
        file_path = filedialog.askopenfilename(
            title="Import Templates",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not file_path:
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Accept both a single dict and a list of dicts
            entries = data if isinstance(data, list) else [data]
            
            from template_system import Template, Recipe
            imported, skipped = 0, 0
            
            # Try RecipeManager first (new unified system), fall back to TemplateManager
            if self.recipe_manager:
                for entry in entries:
                    try:
                        # Support both old template format and new recipe format
                        if "recipe_type" in entry:
                            recipe = Recipe.from_dict(entry)
                            recipe.is_builtin = False
                            if self.recipe_manager.add_recipe(recipe):
                                imported += 1
                            else:
                                skipped += 1
                        else:
                            # Migrate old template format
                            template = Template.from_dict(entry)
                            recipe = Recipe.from_template(template)
                            recipe.is_builtin = False
                            if self.recipe_manager.add_recipe(recipe):
                                imported += 1
                            else:
                                skipped += 1
                    except Exception:
                        skipped += 1
            else:
                # Fall back to old TemplateManager for backward compatibility
                for entry in entries:
                    try:
                        tmpl = Template.from_dict(entry)
                        tmpl.is_builtin = False
                        if self.template_manager.add_template(tmpl):
                            imported += 1
                        else:
                            skipped += 1
                    except Exception:
                        skipped += 1
            
            self.refreshtemplatelist()
            msg = f"Imported {imported} template(s)."
            if skipped:
                msg += f" {skipped} skipped (name conflict or invalid)."
            self.status_var.set(msg)
            self._dialog.info("Import Complete", msg)
        except Exception as e:
            self._dialog.error("Import Error", f"Could not read file:\n{e}")
    
    def export_templates(self):
        """Export all custom templates/recipes to a single JSON file (list format)."""
        if not self.template_available:
            self._dialog.warning("Template System", "Template system is not available.")
            return
        
        from tkinter import filedialog
        import json, re
        
        from datetime import date
        default_name = f"frogpaper_recipes_{date.today().strftime('%Y%m%d')}"
        
        file_path = filedialog.asksaveasfilename(
            title="Export Prompts",
            initialfile=f"{default_name}.json",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not file_path:
            return
        
        try:
            # Try RecipeManager first (new unified system), fall back to TemplateManager
            if self.recipe_manager:
                custom = [r for r in self.recipe_manager.get_all_recipes() if not r.is_builtin]
                if not custom:
                    self._dialog.info("Nothing to Export", "You have no custom prompts to export.\n(Built-in prompts are not exported.)")
                    return
                data = [r.to_dict() for r in custom]
            else:
                # Fall back to old TemplateManager for backward compatibility
                custom = [t for t in self.template_manager.get_all_templates() if not t.is_builtin]
                if not custom:
                    self._dialog.info("Nothing to Export", "You have no custom templates to export.\n(Built-in templates are not exported.)")
                    return
                data = [t.to_dict() for t in custom]
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            self.status_var.set(f"Exported {len(custom)} custom template(s) to file.")
            self._dialog.info("Export Complete", f"Exported {len(custom)} template(s) to:\n{file_path}")
        except Exception as e:
            self._dialog.error("Export Error", f"Could not export templates:\n{e}")

    def edit_template(self):
        """Edit selected recipe by loading it into the Quick Build form."""
        template_name = self.template_var.get()
        if not template_name or not self.template_available:
            self._dialog.warning("No Selection", "Please select a prompt first.")
            return

        source = None
        if self.recipe_manager:
            source = self.recipe_manager.get_recipe(template_name)
        if source is None and self.template_manager:
            legacy = self.template_manager.get_template(template_name)
            if legacy:
                from template_system import Recipe
                source = Recipe.from_template(legacy)

        if source is None:
            return

        if source.is_builtin:
            self._dialog.info(
                "Built-in Prompt",
                "Built-in prompts cannot be edited directly.\n\n"
                "Save a new prompt with your changes using \"Save Quick Prompt\"."
            )
            return

        self._load_quick_recipe_to_theme_builder(source)
        self.activate_prompt_builder_tab()
        self.status_var.set(f"Loaded '{template_name}' into Quick Build for editing. Adjust values and save as a new prompt.")

    def _open_template_edit_dialog(self, source, *, is_recipe):
        """Open a modal edit dialog for a custom template or recipe."""
        import re as _re

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Edit: {source.name}")
        dialog.geometry("560x480")
        dialog.resizable(True, True)
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Name:").pack(anchor="w", padx=14, pady=(12, 0))
        name_var = tk.StringVar(value=source.name)
        name_entry = ttk.Entry(dialog, textvariable=name_var, width=60)
        name_entry.pack(padx=14, pady=(2, 8), fill="x")
        self.configure_entry_cursor(name_entry)

        ttk.Label(dialog, text="Description:").pack(anchor="w", padx=14)
        desc_var = tk.StringVar(value=source.description)
        desc_entry = ttk.Entry(dialog, textvariable=desc_var, width=60)
        desc_entry.pack(padx=14, pady=(2, 8), fill="x")
        self.configure_entry_cursor(desc_entry)

        ttk.Label(dialog, text="Template Text:").pack(anchor="w", padx=14)
        text_frame = ttk.Frame(dialog)
        text_frame.pack(padx=14, pady=(2, 8), fill="both", expand=True)
        text_scroll = ttk.Scrollbar(text_frame, orient="vertical")
        text_box = tk.Text(
            text_frame,
            wrap="word",
            height=10,
            yscrollcommand=text_scroll.set,
            font=("TkDefaultFont",),
        )
        text_scroll.config(command=text_box.yview)
        text_box.pack(side="left", fill="both", expand=True)
        text_scroll.pack(side="right", fill="y")
        text_box.insert("1.0", source.template_text or "")

        hint = ttk.Label(
            dialog,
            text="Use {variable_name} placeholders in the template text.",
            font=self.small_font,
            foreground="#666666",
        )
        hint.pack(anchor="w", padx=14, pady=(0, 8))

        def do_save():
            new_name = name_var.get().strip()
            new_desc = desc_var.get().strip()
            new_text = text_box.get("1.0", tk.END).strip()

            if not new_name:
                self._dialog.warning("Name Required", "Please enter a name.")
                return
            if not new_text:
                self._dialog.warning("Text Required", "Template text cannot be empty.")
                return

            # Re-extract variables from updated text; preserve existing options/last_values
            detected_vars = list(dict.fromkeys(_re.findall(r"\{(\w+)\}", new_text)))
            old_vars = source.variables if source.variables else {}
            old_last = source.last_values if source.last_values else {}
            new_vars = {v: old_vars.get(v, []) for v in detected_vars}
            new_last = {v: old_last[v] for v in detected_vars if v in old_last}

            try:
                if is_recipe and self.recipe_manager:
                    if new_name != source.name:
                        if self.recipe_manager.get_recipe(new_name):
                            self._dialog.error(
                                "Name Taken",
                                f"A recipe named '{new_name}' already exists.",
                            )
                            return
                        self.recipe_manager.delete_recipe(source.name)

                    from template_system import Recipe
                    updated = Recipe(
                        name=new_name,
                        description=new_desc,
                        recipe_type=source.recipe_type if source.recipe_type else "template",
                        template_text=new_text,
                        variables=new_vars,
                        last_values=new_last,
                        is_builtin=False,
                        style_mode=source.style_mode,
                        negative_prompt=source.negative_prompt,
                        quick_fields=dict(source.quick_fields) if source.quick_fields else {},
                    )
                    # Same name → update in place; new name → add (old already deleted above)
                    if new_name == source.name:
                        self.recipe_manager.update_recipe(updated)
                    else:
                        self.recipe_manager.add_recipe(updated)

                elif self.template_manager:
                    from template_system import Template
                    updated = Template(
                        name=new_name,
                        description=new_desc,
                        template_text=new_text,
                        variables=new_vars,
                        is_builtin=False,
                        last_values=new_last,
                    )
                    if new_name == source.name:
                        self.template_manager.update_template(updated)
                    else:
                        self.template_manager.delete_template(source.name)
                        self.template_manager.add_template(updated)

                self.refreshtemplatelist()
                self.template_var.set(new_name)
                self.loadtemplate()
                self.status_var.set(f"Prompt '{new_name}' saved.")
                dialog.destroy()

            except Exception as e:
                self._dialog.error("Save Error", f"Could not save template:\n{e}")

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=(0, 12))
        ttk.Button(btn_frame, text="Save", command=do_save).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side="left", padx=6)

        name_entry.focus_set()

    def delete_template(self):
        """Delete the selected template/recipe."""
        template_name = self.template_var.get()

        if not template_name or not self.template_available:
            self._dialog.warning("No Selection", "Please select a prompt first.")
            return

        # Try RecipeManager first (new unified system), fall back to TemplateManager
        if self.recipe_manager:
            recipe = self.recipe_manager.get_recipe(template_name)
            if recipe:
                if recipe.is_builtin:
                    self._dialog.warning("Built-in Prompt", "Cannot delete built-in prompts.")
                    return
                result = self._dialog.ask("Delete Prompt", f"Are you sure you want to delete '{template_name}'?")
                if result:
                    if self.recipe_manager.delete_recipe(template_name):
                        self.status_var.set(f"Prompt '{template_name}' deleted.")
                        self.refreshtemplatelist()
                    else:
                        self._dialog.error("Error", "Could not delete prompt.")
                return

        # Fall back to old TemplateManager for backward compatibility
        if self.template_manager:
            template = self.template_manager.get_template(template_name)
            if template:
                if template.is_builtin:
                    self._dialog.warning("Built-in Template", "Cannot delete built-in templates.")
                    return
                result = self._dialog.ask("Delete Template", f"Are you sure you want to delete '{template_name}'?")
                if result:
                    if self.template_manager.delete_template(template_name):
                        self.status_var.set(f"Template '{template_name}' deleted.")
                        self.refreshtemplatelist()
                    else:
                        self._dialog.error("Error", "Could not delete template.")
                return

    

    def export_template(self):
        """Export the selected template/recipe to a JSON file."""
        template_name = self.template_var.get()

        if not template_name or not self.template_available:
            self._dialog.warning("No Selection", "Please select a prompt first.")
            return

        from tkinter import filedialog
        export_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=f"{template_name}.json"
        )

        if export_path:
            # Try RecipeManager first (new unified system), fall back to TemplateManager
            if self.recipe_manager:
                recipe = self.recipe_manager.get_recipe(template_name)
                if recipe:
                    if self.recipe_manager.export_recipe(template_name, Path(export_path)):
                        self.status_var.set(f"Prompt '{template_name}' exported successfully.")
                        self._dialog.info("Export Successful", f"Prompt exported to {export_path}")
                    else:
                        self._dialog.error("Export Failed", "Could not export prompt.")
                    return

            # Fall back to old TemplateManager for backward compatibility
            if self.template_manager:
                if self.template_manager.export_template(template_name, Path(export_path)):
                    self.status_var.set(f"Template '{template_name}' exported successfully.")
                    self._dialog.info("Export Successful", f"Template exported to {export_path}")
                else:
                    self._dialog.error("Export Failed", "Could not export template.")

    def import_template(self):
        """Import a template/recipe from a JSON file."""
        from tkinter import filedialog

        import_path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )

        if import_path:
            # Try RecipeManager first (new unified system), fall back to TemplateManager
            if self.recipe_manager:
                if self.recipe_manager.import_recipe(Path(import_path)):
                    self.status_var.set("Prompt imported successfully.")
                    self.refreshtemplatelist()
                    self._dialog.info("Import Successful", "Prompt imported successfully.")
                else:
                    self._dialog.error("Import Failed", "Could not import prompt.")
                return

            # Fall back to old TemplateManager for backward compatibility
            if self.template_manager:
                if self.template_manager.import_template(Path(import_path)):
                    self.status_var.set("Template imported successfully.")
                    self.refreshtemplatelist()
                    self._dialog.info("Import Successful", "Template imported successfully.")
                else:
                    self._dialog.error("Import Failed", "Could not import template.")

    

    # _on_template_search and _clear_template_search removed —
    # template_search_var widget was never added to the UI.











    def previewdoubleclick(self, event=None):
        """Double-click the preview image to instantly set it as wallpaper."""
        path = self.last_image_path or self.selected_gallery_path
        if not path:
            self.status_var.set("No image loaded to set as wallpaper.")
            return
        self.double_click_set_wallpaper(path)




    def _build_settings_tab(self, parent):

        # ── Fixed header: Save Settings always visible ──────────────────────
        header = ttk.Frame(parent, padding=(10, 6))
        header.pack(side="top", fill="x")
        ttk.Button(header, text="💾 Save Settings", command=self.save_settings).pack(side="left")
        ttk.Separator(parent, orient="horizontal").pack(side="top", fill="x")

        # ── Scrollable body ─────────────────────────────────────────────────
        canvas = tk.Canvas(parent, highlightthickness=0)
        scroll = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas, style="Inner.TFrame")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        _st_win = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(_st_win, width=e.width))
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self.settings_canvas = canvas
        self.settings_inner = inner

        # Enable mousewheel scrolling for the entire settings panel
        def _settings_wheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"

        def _bind_wheel_recursive(widget):
            try:
                widget.bind("<MouseWheel>", _settings_wheel)
                for child in widget.winfo_children():
                    _bind_wheel_recursive(child)
            except Exception:
                pass

        # Bind after all widgets are built
        def _deferred_bind():
            _bind_wheel_recursive(canvas)
            _bind_wheel_recursive(inner)
        parent.after(200, _deferred_bind)

        PAD = {"pady": (0, 12)}   # uniform section gap
        LBL = {"font": UI["heading_font"]}  # section-label style

        # ── 1. APPEARANCE ────────────────────────────────────────────────────
        ap = ttk.LabelFrame(inner, text="Appearance", padding=10)
        ap.pack(fill="x", **PAD)
        ap.columnconfigure(1, weight=1)

        ttk.Label(ap, text="App Theme:", **LBL).grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.theme_var = tk.StringVar(value=THEME_DISPLAY_NAMES.get(load_config().get("app_theme", "darkforest"), "Dark Forest Green"))
        self.theme_combo = ttk.Combobox(ap, textvariable=self.theme_var, values=list(THEME_DISPLAY_NAMES.values()), state="readonly", width=25)
        self.theme_combo.grid(row=0, column=1, sticky="w", pady=(0, 4))
        self.theme_combo.bind("<<ComboboxSelected>>", self.on_theme_changed)

        ttk.Label(ap, text="Resolution:", **LBL).grid(row=1, column=0, sticky="w", pady=(6, 4))
        if not hasattr(self, 'dimension_preset_var'):
            self.dimension_preset_var = tk.StringVar(value="16:9 (1080p)")
        self.dimension_preset_combo = ttk.Combobox(ap, textvariable=self.dimension_preset_var, values=list(DIMENSION_PRESETS.keys()), state="readonly", width=20)
        self.dimension_preset_combo.grid(row=1, column=1, sticky="w", pady=(6, 4))

        # Note: Custom WxH option removed - use built-in presets only

        # ── 2. GENERATION ────────────────────────────────────────────────────
        gn = ttk.LabelFrame(inner, text="Generation", padding=10)
        gn.pack(fill="x", **PAD)
        gn.columnconfigure(1, weight=1)

        ttk.Label(gn, text="API Token:", **LBL).grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.token_var = tk.StringVar(value="")
        self.token_entry = ttk.Entry(gn, textvariable=self.token_var, width=40, show="*")
        self.token_entry.grid(row=0, column=1, sticky="ew", pady=(0, 4))
        self.configure_entry_cursor(self.token_entry)

        self.token_preview_var = tk.StringVar(value=self.format_token_preview())
        ttk.Label(gn, textvariable=self.token_preview_var, font=self.small_font).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(2, 4))

        tok_btns = ttk.Frame(gn)
        tok_btns.grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 8))
        self.token_toggle_btn = ttk.Button(tok_btns, text="Show Token", command=self.toggle_token_visibility)
        self.token_toggle_btn.pack(side="left", padx=(0, 8))
        ttk.Button(tok_btns, text="Refresh Token Status", command=self.refresh_token_status).pack(side="left")

        ttk.Separator(gn, orient="horizontal").grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        ttk.Label(gn, text="AI Model:", **LBL).grid(row=4, column=0, sticky="w", pady=(0, 4))
        saved_model_id = load_config().get("model_id", "black-forest-labs/FLUX.1-schnell")
        initial_display = MODEL_ID_TO_DISPLAY.get(
            saved_model_id,
            "Custom..." if saved_model_id not in MODEL_DISPLAY_TO_ID.values()
            else "FLUX.1-schnell (Fastest & Free)"
        )
        self.model_choice_var = tk.StringVar(value=initial_display)
        self.model_choice_combo = ttk.Combobox(gn, textvariable=self.model_choice_var, values=MODEL_OPTIONS, state="readonly", width=40)
        self.model_choice_combo.grid(row=4, column=1, sticky="w", pady=(0, 4))
        self.model_choice_combo.bind("<<ComboboxSelected>>", self._on_model_choice_changed)
        self.custom_model_var = tk.StringVar(value=saved_model_id if initial_display == "Custom..." else "")
        self.custom_model_entry = ttk.Entry(gn, textvariable=self.custom_model_var, width=58)
        self.configure_entry_cursor(self.custom_model_entry)
        if initial_display == "Custom...":
            self.custom_model_entry.grid(row=5, column=0, columnspan=2, sticky="w", pady=(0, 4))

        # ── 3. GALLERY & SLIDESHOW ───────────────────────────────────────────
        gs = ttk.LabelFrame(inner, text="Gallery & Slideshow", padding=10)
        gs.pack(fill="x", **PAD)
        gs.columnconfigure(1, weight=1)

        ttk.Label(gs, text="Wallpaper Slideshow:", **LBL).grid(row=0, column=0, sticky="w", pady=(0, 4))

        if not hasattr(self, 'slideshow_enabled_var'):
            self.slideshow_enabled_var = tk.BooleanVar(value=False)
        if not hasattr(self, 'slideshow_interval_var'):
            self.slideshow_interval_var = tk.StringVar(value='60')
        if not hasattr(self, 'slideshow_source_var'):
            self.slideshow_source_var = tk.StringVar(value='All Images')
        if not hasattr(self, 'slideshow_order_var'):
            self.slideshow_order_var = tk.StringVar(value='random')
        if not hasattr(self, 'slideshow_skip_duplicates_var'):
            self.slideshow_skip_duplicates_var = tk.BooleanVar(value=True)
        self.sync_slideshow_state()

        ttk.Checkbutton(gs, text="Enable in-app slideshow",
                        variable=self.slideshow_enabled_var,
                        command=self.on_slideshow_toggle).grid(row=1, column=1, sticky="w", pady=(0, 4))

        # Interval row with label and value display
        interval_label_frame = ttk.Frame(gs)
        interval_label_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(2, 0))
        interval_label_frame.columnconfigure(1, weight=1)
        
        ttk.Label(interval_label_frame, text="Interval (minutes)").grid(row=0, column=0, sticky="w")
        if not hasattr(self, 'interval_display_var'):
            self.interval_display_var = tk.StringVar(value='60')
        ttk.Label(interval_label_frame, textvariable=self.interval_display_var, font=("Segoe UI", 10, "bold"), foreground="#0078D4").grid(row=0, column=1, sticky="e")
        
        # Slider for interval selection (1-60 minutes)
        def on_interval_change(value):
            # Round to nearest integer for display and storage
            val = int(float(value))
            self.slideshow_interval_var.set(str(val))
            self.interval_display_var.set(str(val))
        
        self.interval_slider = ttk.Scale(gs, from_=1, to=60, orient='horizontal', command=on_interval_change)
        try:
            initial_val = int(float(self.slideshow_interval_var.get()))
            self.interval_slider.set(max(1, min(60, initial_val)))
        except:
            self.interval_slider.set(60)
        self.interval_slider.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        
        # Helper text
        ttk.Label(gs, text="Adjust the slider to set how often wallpapers rotate (1–60 minutes)",
                  font=self.small_font, foreground="#666666").grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(2, 0))

        ttk.Label(gs, text="Source").grid(row=5, column=0, sticky="w", pady=(2, 0))
        ttk.Combobox(gs, textvariable=self.slideshow_source_var, values=SLIDESHOW_SOURCE_DISPLAY, state='readonly', width=18).grid(row=5, column=1, sticky="w", pady=(2, 0))

        ttk.Label(gs, text="Order").grid(row=6, column=0, sticky="w", pady=(2, 0))
        ttk.Combobox(gs, textvariable=self.slideshow_order_var, values=['random', 'newest', 'oldest'], state='readonly', width=10).grid(row=6, column=1, sticky="w", pady=(2, 0))

        ttk.Checkbutton(gs, text="Skip duplicates (no repeat until all shown)",
                        variable=self.slideshow_skip_duplicates_var).grid(
            row=7, column=0, columnspan=2, sticky="w", pady=(4, 6))

        # ── Wallpaper Optimization ────────────────────────────────────────────
        ttk.Separator(gs, orient="horizontal").grid(row=8, column=0, columnspan=2, sticky="ew", pady=(8, 8))

        ttk.Label(gs, text="Wallpaper Output:", **LBL).grid(row=9, column=0, sticky="w", pady=(0, 4))

        if not hasattr(self, 'wallpaper_format_var'):
            self.wallpaper_format_var = tk.StringVar(value='PNG')
        if not hasattr(self, 'wallpaper_quality_var'):
            self.wallpaper_quality_var = tk.StringVar(value='High')

        format_frame = ttk.Frame(gs)
        format_frame.grid(row=9, column=1, sticky="w", pady=(0, 4))
        ttk.Combobox(format_frame, textvariable=self.wallpaper_format_var,
                     values=['PNG', 'JPEG', 'WebP'], state='readonly', width=10).pack(side='left', padx=(0, 8))
        ttk.Combobox(format_frame, textvariable=self.wallpaper_quality_var,
                     values=['Maximum', 'High', 'Medium', 'Low'], state='readonly', width=10).pack(side='left')

        ttk.Label(gs, text="Lower quality = smaller file size, minimal visual difference at desktop size",
                  font=self.small_font, foreground="#666666").grid(
            row=10, column=0, columnspan=2, sticky="w", pady=(2, 0))

        # ── 4. WINDOW BEHAVIOR ───────────────────────────────────────────────
        wb = ttk.LabelFrame(inner, text="Window Behavior", padding=10)
        wb.pack(fill="x", **PAD)

        self.minimize_to_tray_var = tk.BooleanVar(value=self.minimize_to_tray_enabled)
        ttk.Label(wb, text="Minimize to tray:", **LBL).grid(row=0, column=0, sticky="w", pady=(0, 2))
        ttk.Checkbutton(wb, text="Enabled",
                        variable=self.minimize_to_tray_var,
                        command=self._on_minimize_to_tray_changed).grid(row=0, column=1, sticky="w", pady=(0, 2))
        ttk.Label(wb, text="Closing or minimizing sends the app to the system tray",
                  font=self.small_font, foreground="#666666").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(2, 0))

        self.run_on_startup_var = tk.BooleanVar(value=self.run_on_startup_enabled)
        ttk.Label(wb, text="Run on startup:", **LBL).grid(row=2, column=0, sticky="w", pady=(8, 2))
        ttk.Checkbutton(wb, text="Enabled",
                        variable=self.run_on_startup_var,
                        command=self._on_run_on_startup_changed).grid(row=2, column=1, sticky="w", pady=(8, 2))
        ttk.Label(wb, text="Automatically launch FrogPaper when Windows starts",
                  font=self.small_font, foreground="#666666").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(0, 2))

        ttk.Label(wb, text="Auto-generate on startup:", **LBL).grid(row=4, column=0, sticky="w", pady=(8, 2))
        ttk.Checkbutton(wb, text="Generate a fresh random wallpaper each launch",
                        variable=self.auto_generate_on_startup_var).grid(
            row=4, column=1, sticky="w", pady=(8, 2))
        ttk.Label(wb, text="Startup subject:", **LBL).grid(row=5, column=0, sticky="w", pady=(4, 2))
        startup_subj_entry = ttk.Entry(wb, textvariable=self.startup_subject_var, width=20)
        startup_subj_entry.grid(row=5, column=1, sticky="w", pady=(4, 2))
        ttk.Label(wb, text="Leave as 'frog' for classic frogs, or change to any subject you like",
                  font=self.small_font, foreground="#666666").grid(
            row=6, column=0, columnspan=2, sticky="w", pady=(0, 2))

        # ── 5. ADVANCED ──────────────────────────────────────────────────────
        adv = ttk.LabelFrame(inner, text="Advanced", padding=10)
        adv.pack(fill="x", pady=(0, 20))
        adv.columnconfigure(0, weight=1)

        # Keyword Expansion section title
        kw_title = ttk.Label(adv, text="Keyword Expansion", font=("Segoe UI", 10, "bold"))
        kw_title.grid(row=0, column=0, sticky="w", pady=(0, 8))

        # Centered container for mapping controls
        kw_center_frame = ttk.Frame(adv)
        kw_center_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        kw_center_frame.columnconfigure(0, weight=1)

        # Inner frame for the actual controls (centered)
        kw_row = ttk.Frame(kw_center_frame)
        kw_row.grid(row=0, column=0)

        ttk.Label(kw_row, text="When I type:").pack(side="left", padx=(0, 6))
        self.from_word_var = tk.StringVar()
        self.from_word_entry = ttk.Entry(kw_row, textvariable=self.from_word_var, width=14)
        self.from_word_entry.pack(side="left", padx=(0, 8))
        self.configure_entry_cursor(self.from_word_entry)
        ttk.Label(kw_row, text="→").pack(side="left", padx=(0, 6))
        self.to_word_var = tk.StringVar()
        self.to_word_entry = ttk.Entry(kw_row, textvariable=self.to_word_var, width=14)
        self.to_word_entry.pack(side="left", padx=(0, 8))
        self.configure_entry_cursor(self.to_word_entry)
        ttk.Button(kw_row, text="Add",    command=self.add_user_mapping).pack(side="left", padx=(0, 6))
        ttk.Button(kw_row, text="Remove", command=self.remove_user_mapping).pack(side="left")

        # Example and status labels
        ttk.Label(adv, text="e.g.  awesome → epic     gloomy → moody",
                  font=self.small_font, foreground="#666666").grid(
            row=2, column=0, sticky="w", pady=(4, 4))

        self.expansion_status_var = tk.StringVar(value="Keyword expansion: Ready")
        ttk.Label(adv, textvariable=self.expansion_status_var,
                  font=self.small_font).grid(row=3, column=0, sticky="w")

        # Initialize slideshow status variable
        self.slideshow_status_var = tk.StringVar(value="Slideshow idle")



    def _on_model_choice_changed(self, event=None):

        if self.model_choice_var.get() == "Custom...":

            if not self.custom_model_entry.winfo_ismapped():

                self.custom_model_entry.pack(anchor="w", pady=(0, 8))

        elif self.custom_model_entry.winfo_ismapped():

            self.custom_model_entry.pack_forget()



    def setup_scheduler_from_gui(self):

        try:

            ok = create_task()

            if ok:

                self._dialog.info("Task Scheduler", "Morning auto-wallpaper task created successfully.")

                self.status_var.set("Task Scheduler setup complete.")

            else:

                self._dialog.warning("Task Scheduler", "Task setup did not complete successfully.")

                self.status_var.set("Task Scheduler setup may have failed.")

        except Exception as e:

            self._dialog.error("Task Scheduler", f"Could not create scheduled task.\n\n{e}")

            self.status_var.set("Task Scheduler setup failed.")



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

        for widget in ui["inner"].winfo_children():

            widget.destroy()



        self.favorite_cards.clear()

        self.favorite_thumb_refs.clear()

        self.favorite_selected_item = None

        cards = self.favorite_cards

        refs = self.favorite_thumb_refs

        pal = THEMES.get(self.current_theme_name, THEMES["darkforest"])



        rows = []

        for i, item in enumerate(items):

            item = dict(item)

            # Resolve using only the stored path — no cross-folder repair so
            # gallery images can never leak into the favorites grid.
            guessed = self._guess_image_for_item(item, strict=True)

            path = Path(guessed) if guessed else None

            if path:
                item["resolved_image_path"] = str(path)

            # Always include item — path=None will render a placeholder text card
            rows.append((i, item, path))



        if not rows:

            msg = "No favorites images found yet. Older saved items may not have image paths."

            ttk.Label(ui["inner"], text=msg).pack(pady=20)

            return



        # Store the exact rendered list so organize-mode reorder operates on correct indices
        self._fav_display_items = [item for _, item, _ in rows]

        FAV_COLS = 3

        row = col = 0

        for card_idx, (i, item, path) in enumerate(rows):

            border = pal.get("border_color", pal["panel2"])
            card = tk.Frame(ui["inner"], bd=0, padx=0, pady=0, bg=pal["panel"],
                            highlightthickness=1, highlightbackground=border)

            card.grid(row=row, column=col, padx=6, pady=6, sticky='nsew')
            card.columnconfigure(0, weight=1)

            ts = item.get("timestamp") or item.get("saved_at", "")

            subtitle = (ts[:19].replace("T", " ") if ts else "")

            meta = subtitle or (path.name[:18] if path else "")



            if path and path.exists():

                try:
                    from PIL import Image, ImageTk
                    img = Image.open(path)
                    img.thumbnail((240, 135), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    refs.append(photo)
                    thumb = tk.Label(card, image=photo, cursor="hand2", bg=pal["panel"])
                    thumb.image = photo
                    thumb.pack()
                    thumb.bind("<Button-1>", lambda e, p=path, d=item, u=ui, cidx=card_idx: self._on_fav_card_click(e, p, d, u, cidx))
                    thumb.bind("<Double-Button-1>", lambda e, p=path, d=item, u=ui: self._double_click_visual_item(u, p, d))
                    pass  # no organize drag binds
                except Exception:
                    tk.Label(card, text="(image error)", cursor="hand2", bg=pal["panel"], fg=pal["text"]).pack()

            else:

                snippet = (item.get("theme_sentence") or item.get("prompt") or "")[:100]

                tl = tk.Label(
                    card,
                    text=snippet + ("…" if len(snippet) == 100 else ""),
                    wraplength=220,
                    justify="left",
                    cursor="hand2",
                    font=self.small_font,
                    bg=pal["panel"],
                    fg=pal["text"],
                )

                tl.pack()

                tl.bind("<Button-1>", lambda e, d=item, u=ui: self._select_visual_item(u, None, d))

            # Meta label shown below thumbnail or text — used by highlight/organize logic
            name_label = tk.Label(
                card,
                text=meta,
                wraplength=220,
                height=2,
                font=self.small_font,
                bg=pal["panel"],
                fg=pal["text"],
                anchor="w",
                justify="left",
                padx=6,
                pady=2,
            )
            name_label.pack(fill="x")

            # File size + resolution info
            if path and path.exists():
                try:
                    size_bytes = path.stat().st_size
                    size_str = f"{size_bytes / 1_048_576:.1f} MB" if size_bytes >= 1_048_576 else f"{size_bytes / 1024:.0f} KB"
                    from PIL import Image as _PILImg
                    with _PILImg.open(path) as _im2:
                        w_px, h_px = _im2.size
                    info_text = f"{w_px}×{h_px}  •  {size_str}"
                except Exception:
                    info_text = ""
                info_lbl = tk.Label(card, text=info_text, fg=pal["muted"], font=self.tinyfont,
                                    bg=pal["panel"], anchor="w", justify="left", padx=6, pady=0)
                info_lbl.pack(fill="x")
                info_lbl.bind("<Button-1>", lambda e, p=path, d=item, u=ui, cidx=card_idx: self._on_fav_card_click(e, p, d, u, cidx))

            # Register card so organize-mode highlight and index lookup work
            cards[card_idx] = (card, name_label, item)

            # Advance grid position
            col += 1
            if col >= FAV_COLS:
                col = 0
                row += 1

    def _on_fav_card_click(self, event, path, data, ui, index):
        self._select_visual_item(ui, path, data)

    def _on_fav_card_drag(self, event, index):
        pass  # Organize Mode removed

    def _on_fav_card_drop(self, event, source_index):
        pass  # Organize Mode removed

    def _fav_widget_to_card_index(self, widget):
        return None  # Organize Mode removed

    def _highlight_fav_organize(self, picked_index, *, hover_index):
        pass  # Organize Mode removed

    def _update_fav_card_highlight(self, selected_item):
        pal = THEMES.get(self.current_theme_name, THEMES["darkforest"])
        accent = pal.get("accent", pal["progress"])
        border = pal.get("border_color", pal["panel2"])
        for card_id, (card, name_label, item) in self.favorite_cards.items():
            is_sel = item is selected_item
            bg = pal.get("surface", pal["panel2"]) if is_sel else pal["panel"]
            hi = accent if is_sel else border
            card.config(bg=bg, highlightbackground=hi, highlightthickness=2 if is_sel else 1)
            name_label.config(bg=bg, fg=pal["text"])
            for child in card.winfo_children():
                if isinstance(child, tk.Label) and child is not name_label:
                    child.config(bg=bg, fg=pal["text"])

    def _refresh_fav_card_highlights(self):
        pal = THEMES.get(self.current_theme_name, THEMES["darkforest"])
        accent = pal.get("accent", pal["progress"])
        border = pal.get("border_color", pal["panel2"])
        for card_id, (card, name_label, item) in self.favorite_cards.items():
            is_sel = item is self.favorite_selected_item
            bg = pal.get("surface", pal["panel2"]) if is_sel else pal["panel"]
            hi = accent if is_sel else border
            card.config(bg=bg, highlightbackground=hi, highlightthickness=2 if is_sel else 1)
            name_label.config(bg=bg, fg=pal["text"])

    def _select_visual_item(self, ui, path, data):
        mode = ui["mode"]
        self.set_prompt_text(data.get("prompt", ""))
        if path:
            self.show_preview_in_left_panel(path, f"{mode.capitalize()} selection: {path.name}")
        self.favorite_selected_item = data
        self._update_fav_card_highlight(data)

    def _double_click_visual_item(self, ui, path, data):
        self._select_visual_item(ui, path, data)
        if path:
            self.double_click_set_wallpaper(path)

    def double_click_set_wallpaper(self, path):
        if not WINDOWS:
            self._dialog.info("Windows only", "Setting wallpaper is only supported on Windows.")
            return
        try:
            ok = set_wallpaper(Path(path))
            if ok:
                self.status_var.set(f"Wallpaper set: {Path(path).name}")
                self.slideshow.reset_timer()
            else:
                self.status_var.set(f"Could not set wallpaper: {Path(path).name}")
        except Exception as e:
            self.status_var.set(f"Wallpaper error: {e}")
            self._dialog.error("Wallpaper Error", f"Failed to set wallpaper:\n{e}")

    def random_theme(self):
        """Randomize all quick-build variables including setting and atmosphere."""
        subjects = [option for option in THEME_VARIABLE_OPTIONS["subject"] if option]
        settings = [option for option in THEME_VARIABLE_OPTIONS["setting"] if option]
        styles = [option for option in THEME_VARIABLE_OPTIONS["style"] if option]
        lightings = [option for option in THEME_VARIABLE_OPTIONS["lighting"] if option]
        moods = [option for option in THEME_VARIABLE_OPTIONS["mood"] if option]
        atmospheres = [option for option in THEME_VARIABLE_OPTIONS["atmosphere"] if option]

        # Color options — sourced from module-level constants (exclude blank family so random always picks a color)
        color_families = [f for f in COLOR_FAMILIES if f]
        color_variations = COLOR_VARIATIONS
        # Build color string like "rich gold" or just "gold"
        family = random.choice(color_families)
        variation = random.choice(color_variations)
        color_value = f"{variation} {family}".strip() if variation else family

        self.set_active_subject(random.choice(subjects))
        self.set_active_setting(random.choice(settings))
        self.set_active_style(random.choice(styles))
        self.set_active_lighting(random.choice(lightings))
        self.set_active_mood(random.choice(moods))
        self.set_active_color(color_value)
        self.set_active_atmosphere(random.choice(atmospheres))
        self.set_active_mode(random.choice(STYLE_MODES))
        self.update_mode_badge()
        self.generate()



    def upscale_selected(self):

        if not self.selected_gallery_path:

            self._dialog.info("No Selection", "Please click an image in the gallery first.")

            return

        path = self.selected_gallery_path

        if "_upscaled" in path.stem:

            self._dialog.info("Already Upscaled", "This image has already been upscaled.")

            return

        try:

            from PIL import Image

            img = Image.open(path)

            orig_w, orig_h = img.size

            new_w, new_h = orig_w * 2, orig_h * 2

            upscaled = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            out_path = path.parent / f"{path.stem}_upscaled{path.suffix}"

            upscaled.save(str(out_path))

            self.status_var.set(f"Upscaled saved: {out_path.name}")

            self.load_gallery()

        except Exception as e:

            self._dialog.error("Upscale Failed", f"Could not upscale image.\n{e}")







    def delete_selected_favorite(self):

        if not self.favorite_selected_item:

            self._dialog.info("No selection", "Click a Favorite thumbnail first.")

            return

        target = self.favorite_selected_item

        if not self._dialog.ask("Delete Favorite", "Remove the selected item from Favorites?"):

            return

        # Delete the copied file from favorites/ folder if it exists
        copied_path = target.get("copied_image_path")
        if copied_path:
            try:
                copied_file = Path(copied_path)
                if copied_file.exists() and copied_file.is_file():
                    copied_file.unlink()
            except Exception:
                pass  # Ignore file deletion errors

        updated = [item for item in self.favorites if item is not target]

        if len(updated) == len(self.favorites):

            for i, item in enumerate(self.favorites):

                if item.get("saved_at") == target.get("saved_at") and item.get("prompt") == target.get("prompt"):

                    del self.favorites[i]

                    updated = self.favorites

                    break

        save_json_list(FAVORITES_LOG, updated)

        self.favorite_selected_item = None

        self.load_favorites()

        self.status_var.set("Favorite deleted.")



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

            # Check if mouse is over Prompt Preview text widget
            if hasattr(self, 'prompt_text'):
                try:
                    mouse_x = self.root.winfo_pointerx() - self.root.winfo_rootx()
                    mouse_y = self.root.winfo_pointery() - self.root.winfo_rooty()
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
            view = getattr(self, "gallery_view_var", None)
            if view and view.get() == "Favorites":
                self.gallery_fav_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            elif view and view.get() == "Styled":
                self.gallery_styled_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            elif view and view.get() == "Manual":
                self.gallery_manual_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            else:
                self.gallery_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                self._on_gallery_scroll()

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

        token = get_huggingface_token()

        if not token:

            return "Environment token not found."

        if len(token) <= 8:

            return "Environment token loaded: " + ("*" * len(token))

        return f"Environment token loaded: {token[:4]}...{token[-4:]}"



    def refresh_token_status(self):

        token = get_huggingface_token()

        self.token_var.set(token)

        self.token_entry.config(show="*")

        self.token_toggle_btn.config(text="Show Token")

        self.token_preview_var.set(self.format_token_preview())

        self.status_var.set("Environment token loaded." if token else "No environment token found.")



    def resolved_model_id(self):

        choice = self.model_choice_var.get().strip()

        if choice == "Custom...":

            return self.custom_model_var.get().strip()

        return MODEL_DISPLAY_TO_ID.get(choice, "black-forest-labs/FLUX.1-schnell")



    def save_settings(self):

        config = load_config()

        

        # Convert display theme name to internal name

        display_name = self.theme_var.get()

        config["app_theme"] = THEME_INTERNAL_NAMES.get(display_name, "darkforest")

        config["dimensions"] = self.get_current_dimensions()

        config["model_id"] = self.resolved_model_id() or MODEL_OPTIONS[0]

        config['slideshow_enabled'] = bool(self.slideshow_enabled_var.get())

        config['slideshow_interval'] = int(self.slideshow_interval_var.get() or 60)

        source_value = self.slideshow_source_var.get().strip()
        # Backward compatibility: map old "both" to "all"
        if source_value == 'both':
            source_value = 'all'
        config['slideshow_source'] = SLIDESHOW_LABEL_TO_VALUE.get(source_value, source_value.lower()) or 'all'

        

        # Save minimize to tray setting

        config['minimize_to_tray'] = bool(self.minimize_to_tray_enabled)

        config['slideshow_order'] = self.slideshow_order_var.get()

        config['slideshow_skip_duplicates'] = bool(self.slideshow_skip_duplicates_var.get())

        config["remember_settings"] = bool(self.remember_settings_var.get())
        config["auto_generate_on_startup"] = bool(self.auto_generate_on_startup_var.get())
        config["startup_subject"] = self.startup_subject_var.get().strip() or "frog"

        

        # Save current prompt/builder state if remember is enabled

        if self.remember_settings_var.get():

            config["last_style_mode"] = self.get_active_mode()

            config["last_subject"] = self.get_active_subject()

            config["last_setting"] = self.get_active_setting()

            config["last_style"] = self.get_active_style()

            config["last_lighting"] = self.get_active_lighting()

            config["last_mood"] = self.get_active_mood()

            config["last_color"] = self.get_active_color()

            config["last_atmosphere"] = self.get_active_atmosphere()

            config["last_subject_lock"] = self.get_active_subject_lock()

        # Always persist wallpaper output format and quality
        config['wallpaper_format'] = self.wallpaper_format_var.get()
        config['wallpaper_quality'] = self.wallpaper_quality_var.get()

        # Always persist core settings regardless of remember_settings
        save_config(config)

        self.status_var.set("Settings saved.")

        self.sync_slideshow_state()

        self._dialog.info("Settings", "Settings saved successfully.")



    def load_slideshow_settings(self):

        config = load_config()

        self.slideshow_enabled_var.set(bool(config.get('slideshow_enabled', False)))

        interval_value = str(config.get('slideshow_interval', 60))
        self.slideshow_interval_var.set(interval_value)
        # Update interval display and slider
        try:
            interval_int = int(float(interval_value))
            # Clamp to 1-60 range for slider
            interval_int = max(1, min(60, interval_int))
            if hasattr(self, 'interval_display_var'):
                self.interval_display_var.set(str(interval_int))
            if hasattr(self, 'interval_slider'):
                self.interval_slider.set(interval_int)
        except (ValueError, AttributeError):
            if hasattr(self, 'interval_display_var'):
                self.interval_display_var.set('60')
            if hasattr(self, 'interval_slider'):
                self.interval_slider.set(60)

        # Backward compatibility: map old "both" to "all"
        source_value = config.get('slideshow_source', 'both')
        if source_value == 'both':
            source_value = 'all'
        self.slideshow_source_var.set(SLIDESHOW_SOURCE_LABELS.get(source_value, 'All Images'))

        self.slideshow_order_var.set(config.get('slideshow_order', 'random'))

        self.slideshow_skip_duplicates_var.set(bool(config.get('slideshow_skip_duplicates', True)))

        

        self.slideshow.load_gallery(self.gallery_images or [])  # Wire gallery

        self.sync_slideshow_state()

        self.on_slideshow_toggle()  # Sync running state

        self.root.after(200, self.update_slideshow_status)



    def sync_slideshow_state(self):

        """Pass UI variables to the SlideshowManager instance."""

        if not hasattr(self, 'slideshow_source_var'):

            return # Too early

        self.slideshow.slideshow_enabled_var = self.slideshow_enabled_var

        self.slideshow.slideshow_interval_var = self.slideshow_interval_var

        self.slideshow.slideshow_source_var = self.slideshow_source_var

        self.slideshow.slideshow_order_var = self.slideshow_order_var

        self.slideshow.slideshow_skip_duplicates_var = self.slideshow_skip_duplicates_var



    def on_slideshow_toggle(self):

        self.slideshow.start() if self.slideshow_enabled_var.get() else self.slideshow.stop()

        self.update_slideshow_status()



    def slideshow_start_click(self):

        self.slideshow_enabled_var.set(True)

        self.slideshow.start()

        self.update_slideshow_status()

        self.status_var.set('Slideshow started.')



    def slideshow_stop_click(self):

        self.slideshow_enabled_var.set(False)

        self.slideshow.stop()

        self.update_slideshow_status()

        self.status_var.set('Slideshow stopped.')



    def slideshow_next_now(self):

        self.slideshow.next_now()



    def slideshow_prev_now(self):

        self.slideshow.prev_wallpaper()



    def slideshow_pause_click(self):

        if self.slideshow.paused:
            self.slideshow.resume()
        else:
            self.slideshow.pause()
        self.update_slideshow_status()



    def slideshow_preview_sources(self):

        source_value = SLIDESHOW_LABEL_TO_VALUE.get(self.slideshow_source_var.get().strip(), self.slideshow_source_var.get().strip().lower()) or 'all'
        candidates = self.slideshow.candidates(
            source=source_value,
            order=self.slideshow_order_var.get(),
            skip_duplicates=bool(self.slideshow_skip_duplicates_var.get())
        )

        lines = [f'Eligible images: {len(candidates)}']
        lines.append(f'Source: {self.slideshow_source_var.get()}')

        for i, p in enumerate(candidates[:30]):

            lines.append(f'{i+1}. {p.name}')

        if len(candidates) > 30:

            lines.append(f'... and {len(candidates) - 30} more')

        self._dialog.info('Slideshow Sources', '\n'.join(lines))



    def update_slideshow_status(self):

        self.slideshow_status_var.set(self.slideshow.status_text())
        if hasattr(self, 'slideshow_pause_btn'):
            if self.slideshow.paused:
                self.slideshow_pause_btn.config(text="▶ Resume", style="Active.TButton")
            else:
                self.slideshow_pause_btn.config(text="⏸ Pause", style="TButton")
        
        # Update visual countdown if running
        if self.slideshow.running and not self.slideshow.paused and self.slideshow.last_run:
            try:
                interval_mins = float(self.slideshow_interval_var.get())
                elapsed = (datetime.now() - self.slideshow.last_run).total_seconds()
                total = interval_mins * 60
                remaining = max(0, total - elapsed)
                
                # Format remaining time
                mins, secs = divmod(int(remaining), 60)
                time_str = f"{mins:02d}:{secs:02d}"
                
                progress_pct = min(100, (elapsed / total) * 100)
                self.progress.config(mode="determinate", value=progress_pct)
                self.progress.grid()
                
                # Show descriptive timer
                self.progress_overlay_label.config(text=f"Next Wallpaper in {time_str}")
                self.progress_overlay_label.place(relx=0.5, rely=0.5, anchor="center")
                
                # Theming the overlay label
                pal = THEMES.get(self.current_theme_name, THEMES["darkforest"])
                accent = pal.get("accent", pal["progress"])
                self.progress_overlay_label.config(bg=accent, fg=pal["button_fg"])
            except:
                pass
        else:
            self.progress.grid_remove()
            self.progress_overlay_label.place_forget()
            
        self.root.after(1000, self.update_slideshow_status)



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
        preset = self.dimension_preset_var.get()
        dimensions = DIMENSION_PRESETS.get(preset, "1920x1080")
        self._set_dimensions_from_string(dimensions)

    def _set_dimensions_from_string(self, dimensions_str):
        if "x" in dimensions_str:
            width, height = dimensions_str.split("x", 1)
            self.custom_width_var.set(width.strip())
            self.custom_height_var.set(height.strip())
            for preset_name, preset_dims in DIMENSION_PRESETS.items():
                if preset_dims == dimensions_str:
                    self.dimension_preset_var.set(preset_name)
                    break



    def get_current_dimensions(self):
        return DIMENSION_PRESETS.get(self.dimension_preset_var.get(), "1920x1080")



    def _on_remember_settings_changed(self, event=None):

        pass



    def load_remembered_settings(self):

        config = load_config()

        # Always restore wallpaper output format and quality (core settings)
        if hasattr(self, 'wallpaper_format_var'):
            self.wallpaper_format_var.set(config.get('wallpaper_format', 'PNG'))
        if hasattr(self, 'wallpaper_quality_var'):
            self.wallpaper_quality_var.set(config.get('wallpaper_quality', 'High'))

        # Only restore remembered settings if auto-generate on startup is disabled
        # When auto-generate is enabled, we want random variables each time
        if config.get("remember_settings", False) and not config.get("auto_generate_on_startup", False):

            self.set_active_mode(config.get("last_style_mode", DEFAULT_PROMPT_MODE_VALUE))

            self.set_active_subject(config.get("last_subject", "frog"))

            self.set_active_setting(config.get("last_setting", ""))

            self.set_active_style(config.get("last_style", "cyberpunk"))

            self.set_active_lighting(config.get("last_lighting", "neon"))

            self.set_active_mood(config.get("last_mood", "epic"))

            self.set_active_color(config.get("last_color", ""))

            self.set_active_atmosphere(config.get("last_atmosphere", ""))

            self.set_active_subject_lock(config.get("last_subject_lock", True))

            self.status_var.set("Settings restored from last session")
        else:
            # When auto-generate is enabled, clear any last settings to prevent them from being used
            # This ensures fresh randomization each startup
            config["last_style"] = ""
            config["last_setting"] = ""
            config["last_lighting"] = ""
            config["last_mood"] = ""
            config["last_color"] = ""
            config["last_atmosphere"] = ""
            save_config(config)
            # Also clear UI widget values to ensure they don't interfere with randomization
            self.set_active_style("")
            self.set_active_setting("")
            self.set_active_lighting("")
            self.set_active_mood("")
            self.set_active_color("")
            self.set_active_atmosphere("")



    def add_user_mapping(self):

        """Add a custom user thesaurus mapping."""

        from_word = self.from_word_var.get().strip()

        to_word = self.to_word_var.get().strip()



        if not from_word or not to_word:

            self._dialog.warning("Invalid Input", "Please enter both 'when I type' and 'treat as' values.")

            return



        try:

            from keyword_expander import get_keyword_expander

            expander = get_keyword_expander()

            expander.add_user_mapping(from_word, to_word)



            self.from_word_var.set("")

            self.to_word_var.set("")



            self.status_var.set(f"✓ Added mapping: '{from_word}' → '{to_word}'")

            self.expansion_status_var.set(f"Keyword expansion: Added '{from_word}' → '{to_word}'")



        except Exception as e:

            self._dialog.error("Error", f"Could not add mapping: {e}")



    def remove_user_mapping(self):

        """Remove a custom user thesaurus mapping."""

        from_word = self.from_word_var.get().strip()



        if not from_word:

            self._dialog.warning("Invalid Input", "Please enter the word to remove.")

            return



        try:

            from keyword_expander import get_keyword_expander

            expander = get_keyword_expander()

            expander.remove_user_mapping(from_word)



            self.from_word_var.set("")



            self.status_var.set(f"✓ Removed mapping for: '{from_word}'")

            self.expansion_status_var.set(f"Keyword expansion: Removed '{from_word}'")



        except Exception as e:

            self._dialog.error("Error", f"Could not remove mapping: {e}")



    def save_current_settings_for_memory(self):

        if self.remember_settings_var.get():

            config = load_config()

            config["last_style_mode"] = self.get_active_mode()

            config["last_subject"] = self.get_active_subject()

            config["last_style"] = self.get_active_style()

            config["last_lighting"] = self.get_active_lighting()

            config["last_mood"] = self.get_active_mood()

            config["last_color"] = self.get_active_color()

            save_config(config)



    def toggle_token_visibility(self):

        if self.token_entry.cget("show") == "*":

            self.token_entry.config(show="")

            self.token_toggle_btn.config(text="Hide Token")

        else:

            self.token_entry.config(show="*")

            self.token_toggle_btn.config(text="Show Token")



    def subject_lock_enabled(self):

        return self.get_active_subject_lock()



    def _is_prompt_builder_tab_selected(self):
        # In the 3-column layout, prompt builder controls are always visible
        return True

    def _is_prompt_builder_quick_active(self):
        if getattr(self, "prompt_builder_mode_var", None) is None:
            return False
        if self.prompt_builder_mode_var.get() != "Quick Build":
            return False
        if not getattr(self, "prompt_builder_quick_refs", None):
            return False
        return self._is_prompt_builder_tab_selected()

    def _get_pb_quick_refs(self):
        """Return PB Quick Build refs whenever they are populated (tab-agnostic).
        Used by setters and as the unconditional primary quick-build source."""
        refs = getattr(self, "prompt_builder_quick_refs", None)
        return refs if refs else None

    def _get_active_quick_refs(self):
        """Return PB Quick Build refs when the Prompt Builder tab is the active view.
        Falls back to PB refs unconditionally when no legacy widgets exist."""
        if self._is_prompt_builder_quick_active():
            return getattr(self, "prompt_builder_quick_refs", None)
        # No legacy widgets any more — always fall back to PB Quick Build refs.
        return self._get_pb_quick_refs()

    def _get_active_widget(self, name):
        # Sidebar widgets (self.xxx) are the primary ones now
        widget = getattr(self, name, None)
        if widget is not None:
            return widget
        # Fall back to hidden tab refs dict
        refs = self._get_active_quick_refs()
        if refs and name in refs:
            return refs[name]
        return None

    def _get_active_text(self, name, default=""):
        widget = self._get_active_widget(name)
        if not widget or not hasattr(widget, "get"):
            return default
        try:
            value = widget.get()
        except Exception:
            return default
        return value.strip() if isinstance(value, str) else value

    def get_active_subject(self):
        return self._get_active_text("subject_entry", "")

    def get_active_style(self):
        return self._get_active_text("style_entry", "")

    def get_active_lighting(self):
        return self._get_active_text("lighting_entry", "")

    def get_active_mood(self):
        return self._get_active_text("mood_entry", "")

    def get_active_color(self):
        """Get color by combining family and variation selections."""
        refs = self._get_pb_quick_refs()
        if refs:
            family = refs.get("color_family_var", tk.StringVar()).get() or ""
            variation = refs.get("color_variation_var", tk.StringVar()).get() or ""
            if family and variation:
                return f"{variation} {family}"
            return family or variation
        return ""

    def get_active_setting(self):
        """Get the selected setting from Quick Build controls."""
        return self._get_active_text("setting_entry", "")

    def set_active_setting(self, value):
        """Set setting in Quick Build controls."""
        self._set_active_entry("setting_entry", value or "")

    def get_active_atmosphere(self):
        """Get the selected atmosphere from Quick Build controls."""
        return self._get_active_text("atmosphere_var", "")

    def get_active_mode_label(self):
        label = self._get_active_text("mode_var", DEFAULT_PROMPT_MODE_LABEL)
        return label or DEFAULT_PROMPT_MODE_LABEL

    def get_active_mode(self):
        return self._canonical_mode_value(self.get_active_mode_label())

    def get_active_subject_lock(self):
        widget = self._get_active_widget("subject_lock_var")
        if widget and hasattr(widget, "get"):
            try:
                return bool(widget.get())
            except Exception:
                pass
        return True

    def get_active_negative_prompt(self):
        return self._get_active_text("negative_prompt_var", DEFAULT_NEGATIVE_PROMPT)

    # ── Active-source setters ────────────────────────────────────────────────

    def _set_active_entry(self, name, value):
        """Set a text entry/combobox widget on both sidebar and PB Quick Build source."""
        # Update sidebar widget if it exists
        sidebar_widget = getattr(self, name, None)
        if sidebar_widget and hasattr(sidebar_widget, "delete") and hasattr(sidebar_widget, "insert"):
            try:
                sidebar_widget.delete(0, tk.END)
                sidebar_widget.insert(0, value)
            except Exception:
                pass
        # Update PB Quick Build widget if it exists
        refs = self._get_pb_quick_refs()
        if refs and name in refs:
            widget = refs[name]
            if hasattr(widget, "delete") and hasattr(widget, "insert"):
                try:
                    widget.delete(0, tk.END)
                    widget.insert(0, value)
                except Exception:
                    pass

    def _set_active_var(self, name, value):
        """Set a StringVar / BooleanVar on the PB Quick Build source."""
        refs = self._get_pb_quick_refs()
        if refs and name in refs:
            var = refs[name]
            if hasattr(var, "set"):
                try:
                    var.set(value)
                except Exception:
                    pass

    def set_active_subject(self, value):
        self._set_active_entry("subject_entry", value)

    def set_active_style(self, value):
        self._set_active_entry("style_entry", value)

    def set_active_lighting(self, value):
        self._set_active_entry("lighting_entry", value)

    def set_active_mood(self, value):
        self._set_active_entry("mood_entry", value)

    def set_active_color(self, value):
        """Set color by parsing value into family and variation."""
        refs = self._get_pb_quick_refs()
        if not refs:
            return
        # Valid sets derived from module-level constants
        valid_families = set(COLOR_FAMILIES)
        valid_variations = set(COLOR_VARIATIONS)
        # Parse value like "rich gold" -> family="gold", variation="rich"
        value = (value or "").strip().lower()
        family = ""
        variation = ""
        if value:
            parts = value.split(maxsplit=1)
            if len(parts) == 2:
                var, fam = parts
                # Validate both parts
                if fam in valid_families and var in valid_variations:
                    family = fam
                    variation = var
                elif fam in valid_families:
                    family = fam
                    variation = ""
                elif var in valid_families:
                    family = var
                    variation = ""
            else:
                single = parts[0]
                # Single word: must be a valid family to be accepted
                if single in valid_families:
                    family = single
                    variation = ""
                # If single word is not a valid family, leave both empty (don't show partial tokens like "tones")

        try:
            refs["color_family_var"].set(family)
            refs["color_variation_var"].set(variation)
        except Exception:
            pass

    def set_active_atmosphere(self, value):
        """Set atmosphere in Quick Build controls."""
        self._set_active_var("atmosphere_var", value or "")

    def set_active_mode(self, mode_value):
        """Set mode display on the PB Quick Build source (canonical value or label)."""
        label = self._mode_label(mode_value)
        refs = self._get_pb_quick_refs()
        if refs and "mode_var" in refs:
            try:
                refs["mode_var"].set(label)
            except Exception:
                pass

    def set_active_subject_lock(self, value):
        self._set_active_var("subject_lock_var", bool(value))

    def set_active_negative_prompt(self, value):
        self._set_active_entry("negative_prompt_entry", value)
        self._set_active_var("negative_prompt_var", value)

    # ────────────────────────────────────────────────────────────────────────

    def update_mode_badge(self, mode=None):

        effective_mode = mode if mode is not None else self.get_active_mode()

        label = self._mode_label(effective_mode)

        self.mode_badge.config(
            text=f"Mode: {label} | Subject lock: {'ON' if self.get_active_subject_lock() else 'OFF'}"
        )



    def get_negative_prompt(self):

        return self.get_active_negative_prompt().strip()



    def apply_negative_prompt_to_prompts(self):

        custom = self.get_negative_prompt()

        for item in self.prompts:

            baked = item.get("negative_prompt", "")

            if custom:

                combined_parts = [p.strip() for p in (baked + ", " + custom).split(",") if p.strip()]

                seen = set()

                deduped = []

                for part in combined_parts:

                    key = part.lower()

                    if key not in seen:

                        deduped.append(part)

                        seen.add(key)

                item["negative_prompt"] = ", ".join(deduped)

            elif not baked:

                item["negative_prompt"] = ""



    def generate(self, show_progress=True):

        if self.is_generating:

            self._dialog.info("Please wait", "Generation is already in progress.")

            return

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
        if hasattr(self, 'template_var'):
            self.template_var.set("")

        self.is_generating = True

        self.cancel_event.clear()

        self.update_mode_badge(mode)

        self.status_var.set("Generating themes...")

        if show_progress:
            self.progress.configure(mode="indeterminate")
            self.progress.grid()
            self.progress.start()
            self.progress_overlay_label.config(text="Generating preview...")
            self.progress_overlay_label.place(relx=0.5, rely=0.5, anchor="center")

        # Use ThreadPoolExecutor for non-blocking UI

        self.gen_future = self.executor.submit(

            self._generate_themes_thread,

            subject, setting, style, lighting, mood, color, atmosphere, mode, subject_lock, run_audit

        )

    def generate_prompt_only(self):
        """Generate prompt text only without generating the image."""
        if self.is_generating:
            self._dialog.info("Please wait", "Generation is already in progress.")
            return

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
                    text = f"Mode: {mode}\n\n{prompt_data['theme_sentence']}\n\nPROMPT:\n\n{prompt_data['prompt']}\n\nNegative prompt: {prompt_data.get('negative', '(none)')}"
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

            if self.cancel_event.is_set(): return

            keywords = [w for w in f"{subject} {setting} {style} {lighting} {mood} {color} {atmosphere}".split() if w]

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
            print(f"[PERF] Theme generation completed: {gen_elapsed:.2f}s")

            self.root.after(0, self._finish_generate_themes, themes, prompts, mode, None, ui_values)

        except Exception as e:

            self.root.after(0, self._finish_generate_themes, None, None, mode, str(e), None)



    def _finish_generate_themes(self, themes, prompts, mode, error_msg, ui_values=None):

        self.is_generating = False

        # Only hide progress UI if it was shown
        if self.progress.winfo_ismapped():
            self.progress.stop()
            self.progress.configure(mode="determinate")
            self.progress.grid_remove()
        if self.progress_overlay_label.winfo_ismapped():
            self.progress_overlay_label.place_forget()

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
            if self.prompts and self.prompts[0]:
                prompt = self.prompts[0]['prompt']
                import datetime
                filename = ui_values.get('subject', 'frog') + '_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S') + '.png'
                self.gen_future = self.executor.submit(
                    self._generate_image_thread,
                    prompt,
                    filename,
                    False,  # auto_set_wallpaper
                    ui_values.get('subject', 'frog'),
                    ui_values.get('style', '')
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

        text = f"Mode: {mode}\n\n{data['theme_sentence']}\n\nPROMPT:\n\n{data['prompt']}\n\nNegative prompt: {neg or '(none)'}{audit_section}"
        self.set_prompt_text(text)


    def _display_audit_results(self, audit_results, ui_values):
        """Display audit results in a message box and log warnings."""
        try:
            from prompt_validator import get_audit_warnings, format_audit_summary
            warnings = get_audit_warnings(audit_results)

            # Log to console
            print("\n" + "=" * 80)
            print("PROMPT VARIABLE AUDIT RESULTS")
            print("=" * 80)
            _comps = (self.themes[0].get("components", {}) if getattr(self, 'themes', None) else None)
            print(format_audit_summary(audit_results, ui_values=ui_values, components=_comps, final_prompt=(self.current_prompt_data or {}).get('prompt')))
            print("=" * 80 + "\n")

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

                art_style=data.get("art_style")

            )



    def generate_and_set(self):
            """Set the current image as wallpaper without regenerating."""
            path = self.last_image_path or self.selected_gallery_path
            if not path:
                self._dialog.info("No image", "No image is currently loaded. Generate or select an image first.")
                return
            self.double_click_set_wallpaper(path)





    def load_favorites(self):
        """Load favorites."""
        raw_favorites = load_json_list(FAVORITES_LOG)

        # --- Authoritative source: files present in FAVORITES_DIR ---
        # Build a lookup from filename -> best-matching JSON record so
        # generate-from-favorite still has prompt/metadata available.
        meta_by_name = {}
        for item in raw_favorites:
            p = item.get("image_path") or item.get("copied_image_path") or ""
            if p:
                meta_by_name[Path(p).name] = item

        fav_files = sorted(
            (f for f in FAVORITES_DIR.iterdir()
             if f.is_file() and f.suffix.lower() in IMAGE_EXTS),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )

        self.favorites = []
        for fav_file in fav_files:
            meta = dict(meta_by_name.get(fav_file.name, {}))
            meta["image_path"] = str(fav_file)
            meta["copied_image_path"] = str(fav_file)
            self.favorites.append(meta)

        print(f"[Favorites] folder={len(fav_files)} json_records={len(raw_favorites)}")

        # Apply custom order if one exists from Organize Mode
        if self._fav_custom_order is not None:
            def _fav_key(x):
                return x.get("image_path") or x.get("copied_image_path") or ""
            by_path = {_fav_key(x): x for x in self.favorites}
            ordered = [by_path[p] for p in self._fav_custom_order if p in by_path]
            ordered += [x for x in self.favorites if _fav_key(x) not in set(self._fav_custom_order)]
            display_items = ordered
        else:
            # Apply the same sort as Gallery
            current_sort = self.sort_combo_var.get() if hasattr(self, 'sort_combo_var') else "Date Newest"
            sorted_favs = list(self.favorites)
            def _fav_path(x):
                return x.get("image_path") or x.get("copied_image_path") or ""
            if current_sort in ("Date Newest", "Date Oldest"):
                def _fav_mtime(x):
                    p = _fav_path(x)
                    try:
                        return Path(p).stat().st_mtime if p else 0
                    except Exception:
                        return 0
                sorted_favs.sort(key=_fav_mtime, reverse=(current_sort == "Date Newest"))
            elif current_sort in ("Name A-Z", "Name Z-A"):
                sorted_favs.sort(key=lambda x: Path(_fav_path(x)).name.lower(), reverse=(current_sort == "Name Z-A"))
            elif current_sort == "Size Largest":
                def _fav_size(x):
                    p = _fav_path(x)
                    try:
                        return os.path.getsize(p) if p else 0
                    except Exception:
                        return 0
                sorted_favs.sort(key=_fav_size, reverse=True)
            display_items = sorted_favs
        self._populate_visual_grid(self.gallery_favorites_ui, display_items, "favorites")



    def load_styled(self):
        """Load styled images."""
        try:
            # Collect styled images
            styled_files = [
                f for f in STYLED_DIR.iterdir()
                if f.is_file() and f.suffix.lower() in IMAGE_EXTS
            ]

            # Apply sorting
            current_sort = self.sort_combo_var.get() if hasattr(self, 'sort_combo_var') else "Date Newest"
            if current_sort == "Date Newest":
                styled_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            elif current_sort == "Date Oldest":
                styled_files.sort(key=lambda f: f.stat().st_mtime)
            elif current_sort == "Name A-Z":
                styled_files.sort(key=lambda f: f.name.lower())
            elif current_sort == "Name Z-A":
                styled_files.sort(key=lambda f: f.name.lower(), reverse=True)
            elif current_sort == "Size Largest":
                styled_files.sort(key=lambda f: f.stat().st_size, reverse=True)

            self.gallery_styled_images = styled_files

            # Clear existing styled cards
            for widget in self.gallery_styled_inner.winfo_children():
                widget.destroy()
            self.gallery_styled_cards.clear()

            # Build styled cards
            pal = THEMES.get(self.current_theme_name, THEMES["darkforest"])
            border = pal.get("border_color", pal["panel2"])

            for idx, img_path in enumerate(self.gallery_styled_images):
                self._create_styled_card(img_path, idx, pal, border)

            # Empty-state: tag active but no matches
            if not self.gallery_styled_images and tag_filter:
                pal = THEMES.get(self.current_theme_name, THEMES["darkforest"])
                tk.Label(
                    self.gallery_styled_inner,
                    text=f"No styled images tagged '{tag_filter}'.",
                    bg=pal["panel"], fg=pal["text"], font=self.small_font,
                    pady=30,
                ).grid(row=0, column=0, sticky="ew")

            self.gallery_styled_canvas.configure(
                scrollregion=self.gallery_styled_canvas.bbox("all") or (0, 0, 1, 1)
            )
            self.status_var.set(f'Styled loaded: {len(self.gallery_styled_images)} images')

        except Exception as e:
            self.status_var.set(f'Styled load failed: {e}')
            self.gallery_styled_images = []



    def _create_styled_card(self, img_path, index, pal, border):
        """Create a card for a styled image."""
        cols = min(3, max(1, self.gallery_styled_canvas.winfo_width() // 260))
        row, col = index // cols, index % cols

        card = tk.Frame(self.gallery_styled_inner, bg=pal["panel"],
                       highlightthickness=1, highlightbackground=border, bd=0)
        card.grid(row=row, column=col, padx=6, pady=6, sticky='nsew')
        card.columnconfigure(0, weight=1)

        # Thumbnail
        try:
            from PIL import Image, ImageTk
            path_str = str(img_path)

            if path_str in self.thumb_cache:
                thumb = self.thumb_cache[path_str]
            else:
                img = Image.open(img_path)
                img.thumbnail((240, 135), Image.Resampling.LANCZOS)
                thumb = ImageTk.PhotoImage(img)
                if len(self.thumb_cache) > 200:
                    self.thumb_cache.clear()
                self.thumb_cache[path_str] = thumb

            label = tk.Label(card, image=thumb, bg=pal["panel"])
            label.image = thumb
            label.pack(pady=(4, 4), padx=4)

            # Click to select, double-click to set wallpaper
            label.bind('<Button-1>', lambda e, p=img_path: self._select_styled_image(p))
            label.bind('<Double-Button-1>', lambda e, p=img_path: self.set_gallery_image_as_wallpaper(p))
            card.bind('<Button-1>', lambda e, p=img_path: self._select_styled_image(p))

        except Exception as e:
            print(f"Styled thumbnail error for {img_path}: {e}")
            tk.Label(card, text=f'❌ {img_path.name}', bg='red', fg='white').pack()

        # Name label
        name_label = tk.Label(card, text=img_path.name,
                             wraplength=220, height=2, font=self.small_font,
                             bg=pal["panel"], fg=pal["text"],
                             anchor="w", justify="left", padx=6, pady=2)
        name_label.pack(fill="x")
        name_label.bind('<Button-1>', lambda e, p=img_path: self._select_styled_image(p))

        # File size + resolution info
        try:
            size_bytes = img_path.stat().st_size
            size_str = f"{size_bytes / 1_048_576:.1f} MB" if size_bytes >= 1_048_576 else f"{size_bytes / 1024:.0f} KB"
            from PIL import Image as _PILImg
            with _PILImg.open(img_path) as _im:
                w_px, h_px = _im.size
            info_text = f"{w_px}\u00d7{h_px}  \u2022  {size_str}"
        except Exception:
            info_text = ""
        info_label = tk.Label(card, text=info_text, fg=pal["muted"], font=self.tinyfont,
                              bg=pal["panel"], anchor="w", justify="left", padx=6, pady=0)
        info_label.pack(fill="x")
        info_label.bind('<Button-1>', lambda e, p=img_path: self._select_styled_image(p))

        self.gallery_styled_cards[str(img_path)] = (card, name_label)



    def load_manual(self):
        """Load manual images."""
        try:
            # Collect manual images
            manual_files = [
                f for f in MANUAL_DIR.iterdir()
                if f.is_file() and f.suffix.lower() in IMAGE_EXTS
            ]

            # Apply sorting
            current_sort = self.sort_combo_var.get() if hasattr(self, 'sort_combo_var') else "Date Newest"
            if current_sort == "Date Newest":
                manual_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            elif current_sort == "Date Oldest":
                manual_files.sort(key=lambda f: f.stat().st_mtime)
            elif current_sort == "Name A-Z":
                manual_files.sort(key=lambda f: f.name.lower())
            elif current_sort == "Name Z-A":
                manual_files.sort(key=lambda f: f.name.lower(), reverse=True)
            elif current_sort == "Size Largest":
                manual_files.sort(key=lambda f: f.stat().st_size, reverse=True)

            self.gallery_manual_images = manual_files

            # Clear existing manual cards
            for widget in self.gallery_manual_inner.winfo_children():
                widget.destroy()
            self.gallery_manual_cards.clear()

            # Build manual cards
            pal = THEMES.get(self.current_theme_name, THEMES["darkforest"])
            border = pal.get("border_color", pal["panel2"])

            for idx, img_path in enumerate(self.gallery_manual_images):
                self._create_manual_card(img_path, idx, pal, border)

            # Empty-state: tag active but no matches
            if not self.gallery_manual_images and tag_filter:
                pal = THEMES.get(self.current_theme_name, THEMES["darkforest"])
                tk.Label(
                    self.gallery_manual_inner,
                    text=f"No manual images tagged '{tag_filter}'.",
                    bg=pal["panel"], fg=pal["text"], font=self.small_font,
                    pady=30,
                ).grid(row=0, column=0, sticky="ew")

            self.gallery_manual_canvas.configure(
                scrollregion=self.gallery_manual_canvas.bbox("all") or (0, 0, 1, 1)
            )
            self.status_var.set(f'Manual loaded: {len(self.gallery_manual_images)} images')

        except Exception as e:
            self.status_var.set(f'Manual load failed: {e}')
            self.gallery_manual_images = []



    def _create_manual_card(self, img_path, index, pal, border):
        """Create a card for a manual image."""
        cols = min(3, max(1, self.gallery_manual_canvas.winfo_width() // 260))
        row, col = index // cols, index % cols

        card = tk.Frame(self.gallery_manual_inner, bg=pal["panel"],
                       highlightthickness=1, highlightbackground=border, bd=0)
        card.grid(row=row, column=col, padx=6, pady=6, sticky='nsew')
        card.columnconfigure(0, weight=1)

        # Thumbnail
        try:
            from PIL import Image, ImageTk
            path_str = str(img_path)

            if path_str in self.thumb_cache:
                thumb = self.thumb_cache[path_str]
            else:
                img = Image.open(img_path)
                img.thumbnail((240, 135), Image.Resampling.LANCZOS)
                thumb = ImageTk.PhotoImage(img)
                if len(self.thumb_cache) > 200:
                    self.thumb_cache.clear()
                self.thumb_cache[path_str] = thumb

            label = tk.Label(card, image=thumb, bg=pal["panel"])
            label.image = thumb
            label.pack(pady=(4, 4), padx=4)

            # Click to select, double-click to set wallpaper
            label.bind('<Button-1>', lambda e, p=img_path: self._select_manual_image(p))
            label.bind('<Double-Button-1>', lambda e, p=img_path: self.set_gallery_image_as_wallpaper(p))
            card.bind('<Button-1>', lambda e, p=img_path: self._select_manual_image(p))

        except Exception as e:
            print(f"Manual thumbnail error for {img_path}: {e}")
            tk.Label(card, text=f'❌ {img_path.name}', bg='red', fg='white').pack()

        # Name label
        name_label = tk.Label(card, text=img_path.name,
                             wraplength=220, height=2, font=self.small_font,
                             bg=pal["panel"], fg=pal["text"],
                             anchor="w", justify="left", padx=6, pady=2)
        name_label.pack(fill="x")
        name_label.bind('<Button-1>', lambda e, p=img_path: self._select_manual_image(p))

        # File size + resolution info
        try:
            size_bytes = img_path.stat().st_size
            size_str = f"{size_bytes / 1_048_576:.1f} MB" if size_bytes >= 1_048_576 else f"{size_bytes / 1024:.0f} KB"
            from PIL import Image as _PILImg
            with _PILImg.open(img_path) as _im:
                w_px, h_px = _im.size
            info_text = f"{w_px}\u00d7{h_px}  \u2022  {size_str}"
        except Exception:
            info_text = ""
        info_label = tk.Label(card, text=info_text, fg=pal["muted"], font=self.tinyfont,
                              bg=pal["panel"], anchor="w", justify="left", padx=6, pady=0)
        info_label.pack(fill="x")
        info_label.bind('<Button-1>', lambda e, p=img_path: self._select_manual_image(p))

        self.gallery_manual_cards[str(img_path)] = (card, name_label)



    def _select_manual_image(self, path):
        """Handle manual image selection with highlighting."""
        self.selected_gallery_path = Path(path)
        self.selected_manual_path = Path(path)
        self.show_preview_in_left_panel(path, f'Manual: {path.name}')
        self.status_var.set(f'Selected manual: {path.name}')
        self._update_manual_highlight(self.selected_manual_path)

    def _update_manual_highlight(self, selected_path):
        """Apply selection highlight to the selected manual card."""
        pal = THEMES.get(self.current_theme_name, THEMES["darkforest"])
        sel_str = str(selected_path) if selected_path else None

        for path_str, (card, name_label) in self.gallery_manual_cards.items():
            is_sel = path_str == sel_str
            accent = pal.get("accent", pal["progress"])
            border = pal.get("border_color", pal["panel2"])
            bg = pal.get("surface", pal["panel2"]) if is_sel else pal["panel"]
            hi = accent if is_sel else border

            card.config(bg=bg, highlightbackground=hi, highlightthickness=1 if not is_sel else 2)
            name_label.config(bg=bg, fg=pal["text"])

            for child in card.winfo_children():
                if isinstance(child, tk.Label) and child is not name_label:
                    child.config(bg=bg)



    def _select_styled_image(self, path):
        """Handle styled image selection with highlighting."""
        self.selected_gallery_path = Path(path)
        self.selected_styled_path = Path(path)
        self.show_preview_in_left_panel(path, f'Styled: {path.name}')
        self.status_var.set(f'Selected styled: {path.name}')
        self._update_styled_highlight(self.selected_styled_path)

    def _update_styled_highlight(self, selected_path):
        """Apply selection highlight to the selected styled card."""
        pal = THEMES.get(self.current_theme_name, THEMES["darkforest"])
        sel_str = str(selected_path) if selected_path else None

        for path_str, (card, name_label) in self.gallery_styled_cards.items():
            is_sel = path_str == sel_str
            accent = pal.get("accent", pal["progress"])
            border = pal.get("border_color", pal["panel2"])
            bg = pal.get("surface", pal["panel2"]) if is_sel else pal["panel"]
            hi = accent if is_sel else border

            card.config(bg=bg, highlightbackground=hi, highlightthickness=1 if not is_sel else 2)
            name_label.config(bg=bg, fg=pal["text"])

            for child in card.winfo_children():
                if isinstance(child, tk.Label) and child is not name_label:
                    child.config(bg=bg)



    def favorite_current_prompt(self):

            data = self.selected_prompt()

            if not data:

                self._dialog.info("No preview", "Generate a preview first.")

                return

            # Check if we have an image to copy to favorites
            image_to_copy = None
            if self.last_image_path and Path(self.last_image_path).exists():
                image_to_copy = self.last_image_path

            existing = load_json_list(FAVORITES_LOG)
            
            if image_to_copy:
                original_resolved = Path(image_to_copy).resolve()
                # Check if already favorited by comparing resolved paths
                if any(item.get('copied_image_path') and Path(item.get('copied_image_path')).resolve() == original_resolved for item in existing):
                    self.status_var.set("Image already in favorites.")
                    return

            # Determine the final image path for the favorite
            final_image_path = None
            needs_copy = True
            
            if image_to_copy:
                # Check if the selected image is already inside wallpapers/favorites/
                if FAVORITES_DIR in Path(image_to_copy).parents:
                    # Image is already in favorites folder, use it directly
                    final_image_path = Path(image_to_copy)
                    needs_copy = False
                else:
                    # Need to copy to favorites folder
                    dest_filename = Path(image_to_copy).name
                    dest_path = FAVORITES_DIR / dest_filename
                    
                    # Handle filename collisions with fav2, fav3, etc. suffix
                    counter = 2
                    while dest_path.exists():
                        # Check if it's the same file (same resolved path)
                        if dest_path.resolve() == original_resolved:
                            # Same file, reuse it
                            final_image_path = dest_path
                            needs_copy = False
                            break
                        
                        # Different file, create unique name
                        stem = Path(image_to_copy).stem
                        suffix = Path(image_to_copy).suffix
                        dest_filename = f"{stem}_fav{counter}{suffix}"
                        dest_path = FAVORITES_DIR / dest_filename
                        counter += 1
                    
                    if needs_copy:
                        final_image_path = dest_path
                        try:
                            import shutil
                            shutil.copy2(image_to_copy, dest_path)
                        except Exception:
                            # If copy fails, skip copying but still save metadata
                            needs_copy = False

            # Create metadata entry with both paths
            entry = {
                'saved_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'original_image_path': str(image_to_copy) if image_to_copy else None,
                'image_path': str(final_image_path) if final_image_path else None,
                'copied_image_path': str(final_image_path) if needs_copy and final_image_path else None,
                'prompt': data.get('prompt', ''),
                'theme_sentence': data.get('theme_sentence', 'Prompt favorite'),
                'style_mode': data.get('style_mode', 'stylized'),
                'subject': data.get('subject'),
                'art_style': data.get('art_style')
            }

            existing.append(entry)
            save_json_list(FAVORITES_LOG, existing)

            self.status_var.set("Current prompt added to favorites.")
            self.load_favorites()



    def set_selected_favorite_as_wallpaper(self):
        """Set the selected favorite image as wallpaper directly."""
        if not WINDOWS:
            self._dialog.info("Windows only", "Setting wallpaper is only supported on Windows.")
            return

        if not self.favorite_selected_item:
            self._dialog.info("No selection", "Click a Favorite thumbnail first.")
            return

        data = self.favorite_selected_item
        # Use copied_image_path as primary, fall back to image_path for legacy entries
        image_path = data.get("copied_image_path") or data.get("image_path")

        if not image_path:
            self._dialog.info("No image", "This favorite has no associated image path.")
            return

        try:
            ok = set_wallpaper(Path(image_path))
            if ok:
                self.status_var.set(f"✅ Wallpaper set: {Path(image_path).name}")
            else:
                self.status_var.set(f"❌ Set failed: {Path(image_path).name}")
        except Exception as e:
            self.status_var.set(f"❌ Error: {e}")
            self._dialog.error("Error", f"Failed to set wallpaper:\n{e}")

    def cancel_generation(self):

        """Cancel any running generation tasks."""

        if not self.is_generating:

            return

            

        self.cancel_event.set()

        if self.gen_future:

            self.gen_future.cancel()

            

        self.is_generating = False

        self.progress.stop()
        self.progress.grid_remove()
        self.progress_overlay_label.place_forget()
        self.status_var.set("Generation cancelled.")

        self.image_label.config(text="Generation cancelled", image="")

        self.preview_source_label.config(text="Cancelled")

        self.root.update_idletasks()



    def _update_progress_ui(self, value, text=None):

        """Update both the progress bar and the percentage label."""

        # Percentage calculation: Clamp value to 0-100

        val = max(0, min(100, int(value)))

        # Set progress bar value

        self.progress["value"] = val

        # Update label text for "how much is left" feeling

        display_text = text if text else "Generating Image..."
        self.progress_overlay_label.config(text=display_text)



    def _update_generation_timer(self):

            if not getattr(self, "is_generating", False) or getattr(self, "generation_cancelled", False):

                return

            

            # Simulated progress calculation

            # We estimate the total time to be roughly 30 seconds for a typical generation

            elapsed = time.time() - getattr(self, "generation_start_time", time.time())

            

            # Map elapsed time to 0-95% (save last 5% for completion)

            # 0s -> 0%, 30s -> 95%, using a slow-down curve as it approaches 95

            if elapsed < 30:

                percent = (elapsed / 30.0) * 95

            else:

                # After 30s, increment very slowly towards 99%

                percent = 95 + min(4, (elapsed - 30) * 0.1)

                

            # Update bar and label together

            self._update_progress_ui(percent)

            

            msg = getattr(self, "base_status_msg", "Generating image...")

            self.status_var.set(f"{msg} ({int(elapsed)}s)")

            self.image_label.config(text=f"Generating image... please wait ({int(elapsed)}s)")

            

            # Run every 250ms for a smoother movement feel

            self.root.after(250, self._update_generation_timer)



    def run_image_generation(self, prompt, theme_sentence, style_mode="stylized", auto_set_wallpaper=False, subject=None, art_style=None):

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

            self.cancel_event.clear()

            self.generation_start_time = time.time()

            self._update_generation_timer()

            self.progress.grid()
            self.progress_overlay_label.place(relx=0.5, rely=0.5, anchor="center")

            

            # Initialize progress

            self._update_progress_ui(0)

            self.image_label.config(text="Generating image... please wait", image="")

            self.preview_source_label.config(text=f"Generating image: {filename}")

            

            self.gen_future = self.executor.submit(

                self._generate_image_thread, 

                prompt, filename, auto_set_wallpaper, subject, art_style

            )



    def _generate_image_thread(self, prompt, filename, auto_set_wallpaper, subject, art_style):

            def status_cb(msg):

                def update():

                    self.base_status_msg = msg

                self.root.after(0, update)



            try:

                if self.cancel_event.is_set(): return

                from wallpaper_generator import generate_image

                image_path = generate_image(prompt, subject=subject, style=art_style, filename=filename, status_callback=status_cb)

                if self.cancel_event.is_set():

                    self.root.after(0, self._on_generation_cancelled)

                    return

                self.root.after(0, self._on_generation_complete, image_path, auto_set_wallpaper, None)

            except Exception as e:

                if self.cancel_event.is_set():

                    self.root.after(0, self._on_generation_cancelled)

                    return

                self.root.after(0, self._on_generation_complete, None, False, str(e))



    def _on_generation_cancelled(self):

            self.is_generating = False

            self.generation_cancelled = False

            self.progress.stop()
            self.progress.grid_remove()
            self.progress_overlay_label.place_forget()
            self.status_var.set("Image generation cancelled.")

            self.image_label.config(text="Generation cancelled", image="")

            self.preview_source_label.config(text="Cancelled")



    def _on_generation_complete(self, image_path, auto_set_wallpaper, error_msg):

            self.is_generating = False

            self.progress.stop()
            self.progress.grid_remove()
            self.progress_overlay_label.place_forget()
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



    def _get_app_icon_image(self) -> "Image.Image":
            """Return a PIL Image for the app icon.

            Tries FrogPaperLogo.png first; falls back to the drawn frog.
            This is the single canonical icon used for both the tray and the
            window/taskbar iconphoto.
            """
            try:
                from PIL import Image
                icon_p = Path(__file__).parent / "FrogPaperLogo.png"
                if icon_p.exists():
                    img = Image.open(icon_p).convert("RGBA")
                    return img
            except Exception:
                pass
            return self._build_tray_image()

    def _build_tray_image(self) -> "Image.Image":
            """Drawn fallback frog icon — rendered at 256 px then downscaled for crispness."""
            from PIL import Image, ImageDraw, ImageFilter
            import math

            S = 256  # render size; downscaled to 64 at the end

            img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            # ── Background circle: deep forest gradient via two-pass ellipse ──
            for i in range(S // 2, 0, -1):
                t = i / (S // 2)
                r = int(10 + 20 * t)
                g = int(22 + 38 * t)
                b = int(10 + 18 * t)
                draw.ellipse([S // 2 - i, S // 2 - i, S // 2 + i, S // 2 + i],
                             fill=(r, g, b, 255))

            # outer ring
            draw.ellipse([4, 4, S - 4, S - 4], outline="#4ade80", width=6)
            draw.ellipse([10, 10, S - 10, S - 10], outline="#166534", width=2)

            # ── Wallpaper monitor (bottom portion) ───────────────────────────
            mx, my, mw, mh = 44, 148, 168, 90
            # screen body
            draw.rounded_rectangle([mx, my, mx + mw, my + mh], radius=10,
                                   fill="#0f172a", outline="#334155", width=3)
            # screen gradient (purple→teal wallpaper)
            for i in range(mh - 14):
                t = i / max(mh - 14, 1)
                r = int(88 - 40 * t)
                g = int(28 + 60 * t)
                b = int(120 + 60 * t)
                draw.rectangle([mx + 8, my + 7 + i, mx + mw - 8, my + 8 + i],
                               fill=(r, g, b, 230))
            # tiny star on wallpaper
            for sx, sy in [(mx + 40, my + 30), (mx + 110, my + 20), (mx + 80, my + 50)]:
                draw.regular_polygon((sx, sy, 4), 4, rotation=45, fill="#fde68a")
            # monitor stand
            draw.rectangle([mx + mw // 2 - 8, my + mh, mx + mw // 2 + 8, my + mh + 14],
                           fill="#334155")
            draw.rectangle([mx + mw // 2 - 22, my + mh + 12, mx + mw // 2 + 22, my + mh + 18],
                           fill="#475569")

            # ── Frog body ────────────────────────────────────────────────────
            # main body (rounded, sitting on monitor area)
            body_col   = "#22c55e"
            body_dark  = "#15803d"
            body_light = "#4ade80"

            # belly
            draw.ellipse([72, 80, 184, 172], fill=body_col, outline=body_dark, width=3)
            # lighter belly patch
            draw.ellipse([90, 104, 166, 168], fill="#86efac")

            # left eye dome
            draw.ellipse([54, 44, 102, 92], fill=body_col, outline=body_dark, width=3)
            # right eye dome
            draw.ellipse([154, 44, 202, 92], fill=body_col, outline=body_dark, width=3)

            # left eyeball
            draw.ellipse([60, 50, 96, 86], fill="white")
            draw.ellipse([68, 58, 90, 80], fill="#111827")
            draw.ellipse([82, 60, 90, 68], fill="white")  # catchlight

            # right eyeball
            draw.ellipse([160, 50, 196, 86], fill="white")
            draw.ellipse([168, 58, 190, 80], fill="#111827")
            draw.ellipse([182, 60, 190, 68], fill="white")

            # nostrils
            draw.ellipse([110, 108, 118, 116], fill=body_dark)
            draw.ellipse([138, 108, 146, 116], fill=body_dark)

            # smile
            draw.arc([94, 118, 162, 158], start=15, end=165, fill=body_dark, width=4)

            # ── Subtle AI sparkle top-right ───────────────────────────────────
            for sx, sy, sr in [(196, 36, 6), (214, 52, 4), (208, 24, 3)]:
                draw.regular_polygon((sx, sy, sr), 4, rotation=45, fill="#fbbf24")

            # ── Downscale to 64 for crispness ────────────────────────────────
            img = img.resize((64, 64), Image.Resampling.LANCZOS)
            return img



    def _start_tray(self):
            """Start the system tray icon. Returns True if successful."""
            if not PYSTRAY_AVAILABLE:
                return False
            
            if hasattr(self, '_tray_icon') and self._tray_icon:
                return True  # Tray already running
            
            try:
                menu = pystray.Menu(
                    pystray.MenuItem("Open FrogPaper", self._tray_restore, default=True),
                    pystray.MenuItem("Open Gallery", self._tray_open_gallery),
                    pystray.MenuItem("Open Prompt Builder", self._tray_generate_prompt),
                    pystray.Menu.SEPARATOR,
                    pystray.MenuItem("⏩ Next Wallpaper", self._tray_next_wallpaper),
                    pystray.MenuItem("⏪ Previous Wallpaper", self._tray_prev_wallpaper),
                    pystray.MenuItem("🎲 Random Wallpaper", self._tray_random_wallpaper),
                    pystray.Menu.SEPARATOR,
                    pystray.MenuItem(
                        lambda item: "Start Slideshow" if not getattr(self.slideshow, "running", False) else (
                            "Resume Slideshow" if getattr(self.slideshow, "paused", False) else "Pause Slideshow"
                        ),
                        self._tray_toggle_slideshow,
                    ),
                    pystray.MenuItem(
                        "Stop Slideshow",
                        self._tray_stop_slideshow,
                        visible=lambda item: getattr(self.slideshow, "running", False),
                    ),
                    pystray.Menu.SEPARATOR,
                    pystray.MenuItem("About FrogPaper", self._show_about_dialog),
                    pystray.MenuItem("Quit FrogPaper", self._tray_exit),
                )
                
                # Create tray icon using shared canonical icon
                self._tray_icon = pystray.Icon(
                    "FrogPaper",
                    icon=self._get_app_icon_image(),
                    menu=menu
                )
                
                # Run in a background thread to avoid blocking Tkinter
                import threading
                tray_thread = threading.Thread(target=self._tray_icon.run, daemon=False)
                tray_thread.start()
                return True
            except Exception as e:
                print(f"Error starting tray: {e}")
                return False



    def _stop_tray(self):
            """Stop the system tray icon."""
            if not PYSTRAY_AVAILABLE:
                return
            
            try:
                if hasattr(self, '_tray_icon') and self._tray_icon:
                    self._tray_icon.stop()
                    self._tray_icon = None
            except Exception as e:
                print(f"Error stopping tray: {e}")



    def _toggle_minimize_to_tray(self, icon=None, item=None):
            """Toggle minimize to tray setting from tray menu."""
            self.minimize_to_tray_var.set(not self.minimize_to_tray_var.get())
            self._on_minimize_to_tray_changed()



    def _tray_restore(self, icon=None, item=None):

            self.root.after(0, self._restore_window)



    def _tray_prev_wallpaper(self, icon=None, item=None):

            self.root.after(0, self.slideshow_prev_now)



    def _tray_next_wallpaper(self, icon=None, item=None):

            self.root.after(0, self.advance_slideshow)



    def _tray_pause_slideshow(self, icon=None, item=None):

            self.root.after(0, self.slideshow_pause_click)

    def _tray_toggle_slideshow(self, icon=None, item=None):
            """Start, pause, or resume slideshow depending on current state."""
            def _do():
                if not self.slideshow.running:
                    self.slideshow.start()
                elif self.slideshow.paused:
                    self.slideshow.resume()
                else:
                    self.slideshow.pause()
            self.root.after(0, _do)

    def _tray_stop_slideshow(self, icon=None, item=None):
            self.root.after(0, self.slideshow.stop)

    def _tray_open_gallery(self, icon=None, item=None):
            """Restore window — gallery is always visible in 3-column layout."""
            self.root.after(0, self._restore_window)

    def _tray_generate_prompt(self, icon=None, item=None):
            """Restore window — prompt builder is always visible in sidebar."""
            self.root.after(0, self._restore_window)

    def _tray_random_wallpaper(self, icon=None, item=None):
            """Set a random wallpaper from the gallery without starting the slideshow."""
            def _do():
                try:
                    candidates = self.slideshow.candidates(
                        source=self.slideshow._active_source(),
                        order="random",
                        skip_duplicates=False,
                    )
                    if not candidates:
                        self.status_var.set("Random wallpaper: no images found.")
                        return
                    import random as _random
                    chosen = _random.choice(candidates)
                    ok = set_wallpaper(chosen)
                    self.status_var.set(f"Random wallpaper: {chosen.name}" if ok else "Random wallpaper: set failed.")
                    if ok:
                        self.slideshow.reset_timer()
                except Exception as e:
                    self.status_var.set(f"Random wallpaper error: {e}")
            self.root.after(0, _do)

    def _restore_window(self):

            # deiconify handles both iconic and withdrawn states
            self.root.deiconify()

            self.root.state("normal")

            self.root.lift()

            self.root.focus_force()

            # Stop tray only if it was started; ordinary minimize leaves it running
            # if minimize_to_tray is enabled, so only stop on explicit restore.
            self._stop_tray()



    def _tray_exit(self, icon=None, item=None):

            self._stop_tray()

            self.root.after(0, self._quit_app)



    def _show_about_dialog(self, icon=None, item=None):
        """Show About dialog from tray menu."""
        self.root.after(0, self._show_about_popup)

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



    def _quit_app(self):

            """Fully quit the application (used by tray exit)."""

            self.slideshow.stop()

            self._stop_tray()

            self.root.destroy()

    

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

                print(f"Error updating tray menu: {e}")



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
            print(f"[Startup] Registry error: {e}")

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

                    app.generate(show_progress=False)  # Don't show progress UI during startup
                    # Wait for themes/prompts to complete, then generate actual image
                    def _startup_generate_image():
                        if app.prompts and app.prompts[0]:
                            prompt = app.prompts[0]['prompt']
                            import datetime
                            filename = subject + '_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S') + '.png'
                            app.gen_future = app.executor.submit(
                                app._generate_image_thread,
                                prompt,
                                filename,
                                True,  # auto_set_wallpaper
                                subject,
                                app.get_active_style()
                            )
                    app.root.after(3000, _startup_generate_image)  # Wait 3s for themes/prompts
                root.after(2000, _startup_generate)

            root.mainloop()
        finally:
            _release_mutex(mutex)



if __name__ == "__main__":

        main()




