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
