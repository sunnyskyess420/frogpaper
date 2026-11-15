"""FrogPaper prompt / provider / option-table data (roadmap #7 Phase B).

Pure data extracted from app.py: the default negative prompt, prompt-mode
and style/slideshow tables, provider + model configuration, image
extensions, gallery card height, dimension presets and the base/legacy
option lists that feed THEME_VARIABLE_OPTIONS.

app.py re-imports every name defined here, so app.<NAME> attribute
access, bare-name references inside app.py, and test monkeypatching
(tests set app.<NAME> = ...) all keep working unchanged.
"""

DEFAULT_NEGATIVE_PROMPT = (
    "blurry, low quality, low resolution, pixelated, grainy, noisy, "
    "jpeg artifacts, cropped, bad anatomy, deformed, disfigured"
)

# ──── Style modes and slideshow sources ──────────────────────────────────

PROMPT_MODE_OPTIONS = [
    ("Anime", "anime"),
    ("Cinematic", "cinematic"),
    ("Dark Fantasy", "dark-fantasy"),
    ("Minimalist", "minimalist"),
    ("Painterly", "painterly"),
    ("Pixel Art", "pixel-art"),
    ("Product Photo", "product-photo"),
    ("Realistic", "realistic"),
    ("Stylized", "stylized"),
    ("Surreal", "surreal"),
]
PROMPT_MODE_LABELS = [label for label, _ in PROMPT_MODE_OPTIONS]
PROMPT_MODE_LABEL_TO_VALUE = {label: value for label, value in PROMPT_MODE_OPTIONS}
PROMPT_MODE_VALUE_TO_LABEL = {value: label for label, value in PROMPT_MODE_OPTIONS}
DEFAULT_PROMPT_MODE_VALUE = "stylized"
DEFAULT_PROMPT_MODE_LABEL = "Stylized"
STYLE_MODES = [value for _, value in PROMPT_MODE_OPTIONS]

# ──── Colour picker (curated) ─────────────────────────────────────────────

COLOR_FAMILIES = [
    "", "amber", "apricot", "ash", "beige", "black", "blue", "bronze", "brown", "burgundy",
    "charcoal", "chrome", "cobalt", "coral", "crimson", "cyan", "earth", "emerald", "fuchsia",
    "gold", "golden", "green", "holographic", "indigo", "ivory", "jade", "lavender", "lemon",
    "lilac", "magenta", "maroon", "mauve", "midnight", "mint", "mustard", "navy", "obsidian",
    "olive", "orange", "periwinkle", "pink", "plasma", "purple", "rainbow", "red", "rose", "sage",
    "salmon", "sand", "sapphire", "scarlet", "silver", "slate", "stone", "tan", "teal", "toxic",
    "violet", "void", "white", "yellow",
]

COLOR_VARIATIONS = [
    "", "bold", "bright", "cool", "crystalline", "dark", "deep", "desaturated", "dusty",
    "earthy", "faded", "frosted", "glossy", "hazy", "high contrast", "iridescent", "light",
    "matte", "metallic", "monochrome", "moody", "muted", "neon", "pale", "pastel", "rich",
    "satin", "sepia", "smoky", "soft", "translucent", "vintage", "vivid", "warm",
]

# Colour vocabulary that is no longer offered in the dropdown but must keep
# parsing, so saved presets, sessions and restored configs do not silently lose
# their palette (see FrogPaper-dropdown-improvement-plan.md sections 3.8 and 7).
LEGACY_COLOR_FAMILIES = ["forest green", "lime"]
LEGACY_COLOR_VARIATIONS = [
    "burnished", "dreamy", "electric", "fiery", "fluorescent", "holographic", "icy",
    "low contrast", "opalescent", "oversaturated", "pearlescent", "washed out",
]

COLOR_FAMILIES_PARSE = [*COLOR_FAMILIES, *LEGACY_COLOR_FAMILIES]
COLOR_VARIATIONS_PARSE = [
    *COLOR_VARIATIONS,
    *[v for v in LEGACY_COLOR_VARIATIONS if v not in COLOR_VARIATIONS],
]

# Combinations that read as nonsense to an image model.  Curated per family
# instead of pruning whole adjectives, so "high contrast amber" survives while
# "deep white" does not.
COLOR_COMBO_BLOCKLIST = {
    "white": {"deep", "dark", "light", "pale", "neon", "pastel"},
    "black": {"light", "pale", "pastel", "bright", "neon", "washed out"},
    "obsidian": {"light", "pale", "pastel", "bright"},
    "void": {"light", "pale", "pastel", "bright"},
    "charcoal": {"pastel"},
}

# Variations that contradict earthy families (neon brown, fluorescent beige...).
_EARTHY_FAMILIES = {
    "ash", "beige", "brown", "charcoal", "earth", "ivory", "sand", "stone", "tan", "sepia",
}
_NEON_LIKE_VARIATIONS = {"neon", "fluorescent"}


def is_valid_color_combo(family: str, variation: str) -> bool:
    """True when *variation family* is a palette worth sending to the model."""
    family = (family or "").strip().lower()
    variation = (variation or "").strip().lower()
    if not family or not variation:
        return True
    if variation in COLOR_COMBO_BLOCKLIST.get(family, ()):
        return False
    if variation in _NEON_LIKE_VARIATIONS and family in _EARTHY_FAMILIES:
        return False
    return True


def color_variation_options(family: str, variations=None) -> list[str]:
    """Offer only the variations that make sense for *family* (blank first)."""
    pool = COLOR_VARIATIONS if variations is None else variations
    return [v for v in pool if v == "" or is_valid_color_combo(family, v)]


def pick_color_pair(rng=None) -> tuple[str, str]:
    """Random but valid (family, variation) pair; variation may be blank."""
    import random as _random

    rng = rng or _random
    families = [f for f in COLOR_FAMILIES if f]
    family = rng.choice(families)
    return family, rng.choice(color_variation_options(family))


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


# ──── Provider and model configuration ──────────────────────────────────

PROVIDER_OPTIONS = [
    "Pollinations.ai (Free - No Key)",
    "Prodia (Pro Account)",
    "Cloudflare Workers AI (Free Tier)",
    "Replicate (Pay-Per-Image)",
    "Fal.ai (Fast Inference)",
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
        # The router lists no image models at all (checked against
        # /v1/models: 133 models, none with image output, no FLUX), so the only
        # thing that actually generates is hf-inference's SD3. Offering FLUX
        # here only produced a 404.
        "options": [
            "Stable Diffusion 3 Medium (Free tier)",
            "Custom...",
        ],
        "display_to_id": {
            "Stable Diffusion 3 Medium (Free tier)":
                "stabilityai/stable-diffusion-3-medium-diffusers",
        },
    },
    "Prodia (Pro Account)": {
        "options": [
            "FLUX.schnell (Fast - Free)",
            "FLUX.dev (Higher Quality)",
            "FLUX.1-fill (Inpainting)",
            "SDXL 1.0",
            "SDXL Lightning (Fast)",
            "Animagine XL 3.1 (Anime)",
            "DreamShaper 8",
        ],
        "display_to_id": {
            "FLUX.schnell (Fast - Free)": "flux.schnell",
            "FLUX.dev (Higher Quality)": "flux.dev",
            "FLUX.1-fill (Inpainting)": "flux-fill-dev",
            "SDXL 1.0": "sd-xl-base-1.0",
            "SDXL Lightning (Fast)": "sdxl-lightning",
            "Animagine XL 3.1 (Anime)": "animagine-xl-3.1",
            "DreamShaper 8": "dreamshaper_8",
        },
    },
    "Replicate (Pay-Per-Image)": {
        "options": [
            "FLUX.schnell (Fast - $0.003/img)",
            "FLUX.dev (Quality - $0.025/img)",
            "FLUX.pro (Best - $0.04/img)",
            "SDXL 1.0",
            "SDXL Lightning (Fast)",
        ],
        "display_to_id": {
            "FLUX.schnell (Fast - $0.003/img)": "black-forest-labs/flux-schnell",
            "FLUX.dev (Quality - $0.025/img)": "black-forest-labs/flux-dev",
            "FLUX.pro (Best - $0.04/img)": "black-forest-labs/flux-pro",
            "SDXL 1.0": "stability-ai/sdxl",
            "SDXL Lightning (Fast)": "bytedance/sdxl-lightning-4step",
        },
    },
    "Fal.ai (Fast Inference)": {
        "options": [
            "FLUX.schnell (Fast)",
            "FLUX.dev (Quality)",
            "FLUX.pro (Best)",
            "SDXL 1.0",
            "Playground v2.5",
        ],
        "display_to_id": {
            "FLUX.schnell (Fast)": "fal-ai/flux/schnell",
            "FLUX.dev (Quality)": "fal-ai/flux/dev",
            "FLUX.pro (Best)": "fal-ai/flux/pro",
            "SDXL 1.0": "fal-ai/stable-diffusion-xl",
            "Playground v2.5": "fal-ai/playground-v2.5",
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


# ── Subject ───────────────────────────────────────────────────────────────

SUBJECT_OPTIONS = [
    "", "alchemist", "ancient god", "ancient war machine", "angel of war", "astronaut", "banshee",
    "battle mage", "bear", "bioengineered creature", "bounty hunter", "bullfrog", "cat",
    "celestial guardian", "chimera", "crumbling clocktower", "crystal serpent", "cute toad",
    "cyber frog", "cyber ninja", "dark knight", "demon lord", "desert nomad", "dragon", "eagle",
    "elder treant", "elven archer", "fantasy toad", "fire dancer", "fire-bellied toad",
    "floating ancient relic", "forest spirit", "forgotten deity", "fox", "frog", "frog samurai",
    "giant mecha", "giant skull throne", "giant spider", "giant toad", "glowing crystal monolith",
    "glowing deer", "glowing frog", "golden toad", "gothic empress", "griffon", "haunted house",
    "horned toad", "ice queen", "interdimensional portal", "jack-o-lantern", "kraken", "leviathan",
    "living library", "mech pilot", "mechanical clockwork heart", "moon goddess", "neon butterfly",
    "owl", "panther", "peacock", "phoenix", "pirate captain", "plague doctor", "poison dart frog",
    "racing car", "raven", "robot frog", "samurai", "scarecrow", "sea serpent", "shadowy sentinel",
    "space shuttle", "stag", "star wanderer", "steampunk airship", "street fighter", "submarine",
    "sun deity", "tiger", "time traveler", "toad", "tree frog", "tree toad", "unicorn",
    "void titan", "void walker", "voodoo shaman", "witch", "wolf",
]


# ── Setting ───────────────────────────────────────────────────────────────

SETTING_OPTIONS = [
    "", "abandoned warehouse",
    "alchemist's tower at midnight", "alien jungle planet", "alpine lake at sunrise",
    "alpine meadow at sunrise", "ancient Chinese palace garden", "ancient Roman forum",
    "ancient ruins", "ancient temple", "art museum at night", "autumn forest path",
    "aztec pyramid at dawn",
    "bamboo forest", "bioluminescent swamp", "bunker command center", "castle on a cliff",
    "celestial observatory", "cherry blossom grove", "chessboard landscape at twilight",
    "city made entirely of glass", "cliff edge", "cozy coffee shop at night", "cyberpunk rooftop",
    "deep space nebula field", "derelict space hulk", "dragon's lair",
    "dreamscape of floating clocks", "egyptian pyramid interior", "enchanted library",
    "fae ring in misty woods",
    "feudal Japanese village", "floating island", "fog-covered mountain ridge", "foggy back alley",
    "forest shrine", "frozen tundra lake", "generation ship interior", "giant hourglass desert",
    "giant mushroom forest", "giant's throne room", "gothic cathedral interior",
    "greek cliff-side temple", "hidden waterfall canyon", "holographic data center",
    "infinite mirrored corridor",
    "inverted city above clouds", "jazz club with neon signs", "kelp forest underwater",
    "landscape made of circuit boards", "library that goes on forever",
    "library with spiral staircase", "lighthouse on stormy coast", "lily pad marsh",
    "lunar mining outpost", "mangrove swamp at dusk", "medieval market square",
    "megacity skyline at night", "midnight diner", "misty pond", "mountain peak", "mystic ruins",
    "neon street market", "ocean suspended in mid-air", "orbital ring city",
    "ottoman palace courtyard",
    "penthouse with city view", "portal between worlds", "rainforest canopy", "renaissance workshop",
    "robot assembly bay",
    "rooftop garden at dusk", "sacred grove", "salt flat desert at golden hour",
    "savanna at sunset", "sea cave with glowing tide pools", "silk road desert caravan",
    "sky fortress above clouds",
    "space station corridor", "spaceship cockpit", "staircase to nowhere", "subway station at 3am",
    "sunken elven city", "swamp", "towering redwood forest", "underground speakeasy",
    "underwater city", "underwater research station", "victorian greenhouse",
    "viking longhouse by sea", "wizard tower",
]


# ── Style ─────────────────────────────────────────────────────────────────

STYLE_OPTIONS = [
    "", "3D render", "anime key", "art deco", "art nouveau", "charcoal drawing", "claymation",
    "colored pencil", "concept art", "cottagecore", "cyberpunk neon", "dark academia",
    "glitch art", "gothic elegance", "gouache", "hyperrealism", "impressionist", "ink wash",
    "isometric", "lo-fi", "mid-century poster", "noir b&w", "oil painting", "pixel art", "pop art",
    "risograph print", "sketch pencil", "solarpunk", "stained glass", "stop-motion",
    "surreal dali", "synthwave poster", "ukiyo-e", "vaporwave", "vector flat", "vintage sepia",
    "watercolor",
]


# ── Lighting ──────────────────────────────────────────────────────────────

LIGHTING_OPTIONS = [
    "", "arcane glow", "backlit silhouette", "bare bulb warmth", "bioluminescent glow",
    "blood moon red cast",
    "blue hour", "butterfly lighting", "candlelight", "cinema projector beam", "cinematic bloom",
    "crystal prism scatter", "deep night starlight", "desert midday glare", "dramatic chiaroscuro",
    "dramatic storm light", "electric tesla arcs", "ethereal spirit light", "fire torchlight",
    "fluorescent buzz", "fog diffused beam", "god rays", "golden hour", "hazy dawn",
    "holographic shimmer", "lantern light", "lava glow from below", "led strip underglow",
    "lens flare",
    "midday harsh sun", "misty light", "moonlight", "motivated key light", "overcast daylight",
    "plasma energy glow", "portal energy burst", "practical light sources", "rembrandt lighting",
    "soft diffused light", "soft morning fog", "split lighting", "spotlight single beam",
    "storm lightning", "studio rim light", "sunset haze", "tv screen flicker", "twilight dusk",
    "volumetric",
]


# ── Mood ──────────────────────────────────────────────────────────────────

MOOD_OPTIONS = [
    "", "apocalyptic", "bittersweet", "blissful", "brutal", "chaotic",
    "cosmic awe", "cozy", "dark", "dreamy", "eerie", "electric", "epic", "ethereal", "euphoric",
    "explosive", "foreboding", "frantic", "gentle", "haunting", "hopeful", "hypnotic", "intense",
    "joyful", "lonely", "melancholic", "menacing", "mysterious", "mythic", "nostalgic", "ominous",
    "playful", "radiant", "relentless", "romantic", "savage", "serene", "tense",
    "trippy", "triumphant", "unsettling", "uplifting", "warm", "whimsical", "wild", "wistful",
    "zen",
]


# ── Atmosphere ────────────────────────────────────────────────────────────

ATMOSPHERE_OPTIONS = [
    "", "arcane haze", "ash in the air", "candlelit warmth", "dense fog", "dream haze",
    "drifting spores", "dust", "eerie mist", "embers in air", "enchanted mist", "ethereal glow",
    "falling leaves", "floating pollen", "forest fog", "glitch particles", "holographic mist",
    "jungle humidity", "low valley fog", "luminous vapor", "mist", "morning haze",
    "mossy wetlands", "rolling mist", "sacred glow", "sacred smoke", "sandstorm haze",
    "shimmering particles", "soft atmospheric depth", "soft dreamy haze", "stardust",
    "storm haze", "swirling fog", "void haze",
    # weather sub-group (kept last so the block reads as one category)
    "arctic aurora", "rain", "snow", "storm front",
]

# Members of ATMOSPHERE_OPTIONS that are weather rather than suspended particles.
WEATHER_ATMOSPHERES = ("arctic aurora", "rain", "snow", "storm front")


# ── Public tables (unchanged names) ───────────────────────────────────────

_BASE_SUBJECT_OPTIONS = SUBJECT_OPTIONS
_BASE_SETTING_OPTIONS = SETTING_OPTIONS
_BASE_STYLE_OPTIONS = STYLE_OPTIONS
_BASE_LIGHTING_OPTIONS = LIGHTING_OPTIONS
_BASE_MOOD_OPTIONS = MOOD_OPTIONS
_BASE_ATMOSPHERE_OPTIONS = ATMOSPHERE_OPTIONS

# Everything that used to be merged in is now either kept above or retired.
LEGACY_SUBJECT_OPTIONS = []
LEGACY_SETTING_OPTIONS = []
LEGACY_STYLE_OPTIONS = []
LEGACY_LIGHTING_OPTIONS = []
LEGACY_MOOD_OPTIONS = []
LEGACY_ATMOSPHERE_OPTIONS = []


def _merge_options(base, extra, sort_key=None):
    """Kept for import compatibility. Order is author-controlled now."""
    merged = list(base)
    for option in extra:
        if option not in merged:
            merged.append(option)
    return merged


THEME_VARIABLE_OPTIONS = {
    "subject": SUBJECT_OPTIONS,
    "setting": SETTING_OPTIONS,
    "style": STYLE_OPTIONS,
    "lighting": LIGHTING_OPTIONS,
    "mood": MOOD_OPTIONS,
    "atmosphere": ATMOSPHERE_OPTIONS,
}

# Spellings that used to ship in the lists.  Values saved in sessions, presets,
# templates or a restored config still arrive in the old casing, so they are
# mapped onto the canonical entry instead of silently failing to match.
_LEGACY_SPELLINGS = {
    "setting": [
        "Aztec pyramid at dawn",
        "Egyptian pyramid interior",
        "Greek cliff-side temple",
        "Ottoman palace courtyard",
        "Renaissance workshop",
        "Silk Road desert caravan",
        "Victorian greenhouse",
        "Viking longhouse by sea",
    ],
    "lighting": ["LED strip underglow", "TV screen flicker"],
}

OPTION_ALIASES = {
    category: {old: old.lower() for old in olds if old.lower() in options}
    for category, olds in _LEGACY_SPELLINGS.items()
    for options in (THEME_VARIABLE_OPTIONS[category],)
}


def canonical_option(category: str, value: str) -> str:
    """Map a stored option value onto its current spelling.

    Free text is allowed in every dropdown, so anything unknown is returned
    unchanged.
    """
    text = (value or "").strip()
    if not text:
        return text
    aliased = OPTION_ALIASES.get(category, {}).get(text)
    if aliased:
        return aliased
    lowered = text.lower()
    for option in THEME_VARIABLE_OPTIONS.get(category, ()):
        if option.lower() == lowered:
            return option
    return text
