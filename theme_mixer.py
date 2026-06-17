"""
theme_mixer.py
--------------
Subject-locking wallpaper theme mixer for FrogPaper.
Keeps literal user subjects like cat, frog from being replaced by random pool subjects.
"""

import json
import random
import re
from pathlib import Path
import time

from utils import get_app_dir, get_bundle_dir

# Import keyword expansion system
try:
    from keyword_expander import get_keyword_expander
    KEYWORD_EXPANSION_AVAILABLE = True
except ImportError:
    KEYWORD_EXPANSION_AVAILABLE = False

# Import prompt validator for strengthening
try:
    from prompt_validator import strengthen_color, strengthen_mood, strengthen_mood_for_subject as _mood_subj
    VALIDATOR_AVAILABLE = True
except ImportError:
    VALIDATOR_AVAILABLE = False
    def _mood_subj(mood: str) -> str:  # noqa: F811
        return mood.split()[0] if mood else mood

# Pre-compile regex for tokenization (perf: avoid recompiling on every tokenize_keywords call)
_TOKENIZE_SPLIT_PATTERN = re.compile(r"[\s,;/|_-]+")

BASE_DIR = get_app_dir()
BUNDLE_DIR = get_bundle_dir()
KEYWORDS_FILE = BUNDLE_DIR / "keywords.json"
FALLBACK_FILE = BUNDLE_DIR / "keywords.txt"

CATEGORY_HINTS = {
    "subjects": [
        "frog", "cat", "cats", "kitten", "kittens", "robot", "skull", "dragon", "wizard", "hacker", "logo",
        "emblem", "mascot", "samurai", "ninja", "doll", "voodoo",
        "forest", "woods", "tree", "trees", "jungle", "mountain", "lake", "river",
        "castle", "temple", "city", "street", "room", "desk", "astronaut", "space", "airship",
        "island", "car", "mecha", "spirit", "survivor", "mushroom"
    ],
    "styles": [
        "cyberpunk", "psychedelic", "synthwave", "vapor", "noir", "futuristic",
        "glossy", "gamer", "poster", "cinematic", "retro", "cute", "realistic",
        "fantasy", "dark fantasy", "painterly", "surreal", "anime", "ghibli", 
        "oil", "watercolor", "3d", "render", "poly", "sketch", "pop art", "isometric"
    ],
    "tech_elements": [
        "terminal", "monitor", "screen", "code", "hud", "rgb", "circuit", "rog",
        "gaming", "carbon", "display", "ui", "computer", "workstation", "editing", "photoshop"
    ],
    "mood": [
        "cozy", "trippy", "moody", "dreamy", "mysterious", "electric", "playful",
        "hypnotic", "chill", "badass", "luxurious", "zen", "bold", "dark", "epic",
        "nostalgic", "melancholic", "triumphant", "peaceful", "ethereal", "chaotic"
    ],
    "colors": [
        "purple", "green", "magenta", "black", "emerald", "blue", "pink",
        "red", "silver", "lavender", "teal", "crimson", "scarlet", "gold",
        "pastel", "monochrome", "rainbow", "sepia"
    ],
    "lighting": [
        "neon", "underglow", "volumetric", "monitor glow", "blacklight", "backlight",
        "bloom", "reflections", "rim light", "sunset", "moonlight", "misty light",
        "golden hour", "glare", "bioluminescence"
    ],
    "atmosphere": [
        "fog", "mist", "particles", "glitch", "vapor", "embers", "haze",
        "rain", "snow", "forest fog", "dust", "stardust"
    ],
    "composition": [
        "centered", "symmetrical", "wide", "cinematic", "portrait", "landscape",
        "wallpaper", "desktop", "negative space"
    ],
}

SUBJECT_ALIASES = {
    "forest": "crimson forest landscape",
    "woods": "dense forest landscape",
    "tree": "dramatic woodland scene",
    "trees": "towering forest canopy",
    "jungle": "lush jungle environment",
    "mountain": "cinematic mountain vista",
    "lake": "reflective lake landscape",
    "river": "misty river scene",
    "castle": "dark fantasy castle",
    "temple": "mysterious temple ruins",
    "city": "neon cityscape",
    "street": "rainy neon street",
    "room": "cozy interior scene",
    "desk": "creative desk setup",
    "tree frog": "detailed tree frog on branch",
    "poison dart frog": "vibrant poison dart frog on leaf",
    "peeker frog": "curious peeker frog peeking from behind",
    "glowing frog": "bioluminescent glowing frog",
    "desert frog": "hardy desert frog in sand dunes",
    "red-eyed frog": "striking red-eyed tree frog",
    "frog": "frog",
    "cat": "cat",
    "cats": "cats",
    "kitten": "kitten",
    "kittens": "kittens",
    "voodoo": "voodoo doll",
    "doll": "voodoo doll",
    # Enhanced theme aliases for better anchoring
    "witch": "mystical witch character",
    "wizard": "powerful wizard character",
    "martian colony": "mars colony settlement",
    "underwater city": "submerged aquatic city",
    "forest spirit": "ethereal forest spirit",
    "humanoid": "humanoid character",
    "character": "character portrait",
}

COMPOUND_SUBJECTS = {
    ("frog", "lily"): "vibrant frog sitting on a vibrant green lily pad in a peaceful pond",
    ("frog", "pond"): "frog in a peaceful pond setting",
    ("frog", "rainforest"): "tree frog in rainforest canopy",
    ("frog", "desert"): "desert frog in sand dunes",
    ("frog", "swamp"): "frog in bioluminescent swamp",
    ("tree", "frog"): "detailed tree frog on branch",
    ("poison", "frog"): "vibrant poison dart frog on leaf",
    ("black", "cat"): "black cat",
    ("silver", "cat"): "silver cat",
    ("voodoo", "doll"): "handmade voodoo doll",
}

STYLE_ALIASES = {
    "bold": "cinematic",
    "red": "cinematic",
    "forest": "dark fantasy",
    "woods": "dark fantasy",
    "frog": "high-detail mascot art",
    "cat": "high-detail animal portrait",
    "cyber": "cyberpunk",
    "stoner": "retro stoner poster",
    "cozy": "cozy vapor lounge",
    "realistic": "realistic",
    "cute": "cute cinematic render",
}

MOOD_ALIASES = {
    "bold": "bold",
    "red": "moody",
    "forest": "mysterious",
    "cozy": "cozy",
    "cyber": "electric",
    "frog": "playful",
    "cat": "playful",
    "dark": "moody",
    "luxury": "luxurious",
    "luxurious": "luxurious",
}

COLOR_ALIASES = {
    "red": "crimson red",
    "crimson": "crimson red",
    "scarlet": "crimson red",
    "purple": "neon purple",
    "green": "emerald",
    "emerald": "emerald green",
    "emerald greens": "emerald green",
    "jade": "jade green",
    "verdant": "verdant green",
    "lush": "lush green",
    "forest": "forest green",
    "teal": "teal green",
    "blue": "electric blue",
    "pink": "hot pink",
    "black": "midnight black",
    "silver": "silver chrome",
    "gold": "golden glow",
}

LIGHTING_ALIASES = {
    "forest": "misty light shafts",
    "red": "cinematic bloom",
    "cyber": "neon rim light",
    "cozy": "soft lounge lighting",
    "dark": "smoky backlight",
    "glossy": "glossy reflections",
    "cat": "soft portrait lighting",
}

ATMOSPHERE_ALIASES = {
    "forest": "forest fog",
    "woods": "forest fog",
    "red": "embers in air",
    "cyber": "holographic mist",
    "cozy": "soft dreamy haze",
    "cat": "soft atmospheric depth",
    "fog": "low valley fog with swirling mist",
    "valley": "epic foggy valley",
}

COMPOSITION_ALIASES = {
    "forest": "wide cinematic desktop wallpaper framing",
    "woods": "wide cinematic desktop wallpaper framing",
    "landscape": "wide cinematic desktop wallpaper framing",
    "city": "wide cinematic desktop wallpaper framing",
    "frog": "centered hero with clean side space for desktop icons",
    "cat": "close-up portrait with clean side space for desktop icons",
    "cozy": "cozy room scene with foreground subject and back wall tech",
}

SCENIC_WORDS = {
    "forest", "woods", "tree", "trees", "jungle", "mountain", "lake", "river",
    "castle", "temple", "city", "street", "landscape"
}
TECH_TRIGGER_WORDS = {
    "cyber", "rog", "terminal", "monitor", "screen", "code", "hud", "rgb",
    "gaming", "computer", "workstation", "editing", "photoshop"
}
SUBJECT_PRIORITY_WORDS = {"frog", "tree frog", "poison dart frog", "peeker frog", "glowing frog", "desert frog", "red-eyed frog", "cat", "cats", "kitten", "kittens", "skull", "dragon", "wizard", "robot", "voodoo", "doll"}
STOPWORDS = {"a", "an", "the", "and", "with", "in", "on", "for", "of"}


_KEYWORDS_CACHE = None
_KEYWORD_EXPANDER = None  # Lazy-init once (perf: avoids repeated expander instantiation)


def load_keywords() -> dict:
    global _KEYWORDS_CACHE
    if _KEYWORDS_CACHE is not None:
        return _KEYWORDS_CACHE

    app_dir = get_app_dir()
    candidates = [
        KEYWORDS_FILE,
        FALLBACK_FILE,
        app_dir / "keywords.json",
        app_dir / "keywords.txt",
    ]
    for path in candidates:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            _KEYWORDS_CACHE = {k: v for k, v in data.items() if not k.startswith("_")}
            return _KEYWORDS_CACHE
    raise FileNotFoundError("Could not find keywords.json or keywords.txt")


def get_lazy_keyword_expander():
    """Get or create the keyword expander singleton (lazy-init for perf)."""
    global _KEYWORD_EXPANDER
    if _KEYWORD_EXPANDER is None and KEYWORD_EXPANSION_AVAILABLE:
        try:
            _KEYWORD_EXPANDER = get_keyword_expander()
        except Exception as e:
            print(f"Warning: Could not initialize keyword expander: {e}")
    return _KEYWORD_EXPANDER


MULTI_WORD_PHRASES = [
    # lighting
    "golden hour", "misty light", "monitor glow", "rim light", "bioluminescence",
    "soft lounge lighting", "studio reflections", "cinematic bloom", "soft portrait lighting",
    # atmosphere
    "forest fog", "holographic mist", "soft dreamy haze", "soft atmospheric depth",
    # subjects
    "cyber ninja", "floating island", "racing car", "giant mecha", "dark fantasy",
    "pop art", "oil painting",
    # styles
    "dark fantasy", "pop art", "oil painting", "watercolor", "3d render",
]

def tokenize_keywords(user_keywords) -> list[str]:
    if not user_keywords:
        return []
    if isinstance(user_keywords, str):
        raw = user_keywords
    else:
        raw = " ".join(str(x) for x in user_keywords)
    raw_lower = raw.lower()

    # Extract multi-word phrases first, replace them with a placeholder token
    found_phrases = []
    for phrase in sorted(MULTI_WORD_PHRASES, key=len, reverse=True):
        if phrase in raw_lower:
            found_phrases.append(phrase)
            raw_lower = raw_lower.replace(phrase, "")

    # Tokenize remaining single words using pre-compiled regex
    parts = _TOKENIZE_SPLIT_PATTERN.split(raw_lower)
    tokens = [p.strip() for p in parts if p.strip()]

    return found_phrases + tokens


def classify_keyword(word: str) -> str:
    w = word.lower().strip()
    if w in COLOR_ALIASES or w in CATEGORY_HINTS["colors"]:
        return "colors"
    if w in MOOD_ALIASES or w in CATEGORY_HINTS["mood"]:
        return "mood"
    if w in STYLE_ALIASES or any(hint in w or w in hint for hint in CATEGORY_HINTS["styles"]):
        return "styles"
    if w in LIGHTING_ALIASES or any(hint in w or w in hint for hint in CATEGORY_HINTS["lighting"]):
        return "lighting"
    if w in ATMOSPHERE_ALIASES or any(hint in w or w in hint for hint in CATEGORY_HINTS["atmosphere"]):
        return "atmosphere"
    if w in COMPOSITION_ALIASES or any(hint in w or w in hint for hint in CATEGORY_HINTS["composition"]):
        return "composition"
    if w in TECH_TRIGGER_WORDS or any(hint in w or w in hint for hint in CATEGORY_HINTS["tech_elements"]):
        return "tech_elements"
    # Multi-word phrase fallback — check if the phrase contains a known subject hint
    for hint in CATEGORY_HINTS["subjects"]:
        if hint in w:
            return "subjects"
    return "subjects"


def sort_user_keywords(user_keywords) -> dict:
    buckets = {cat: [] for cat in CATEGORY_HINTS}
    tokens = tokenize_keywords(user_keywords)
    for word in tokens:
        buckets[classify_keyword(word)].append(word)
    return buckets


def choose_from_alias_or_pool(tokens: list[str], alias_map: dict, pool: list[str], fallback: str = "") -> str:
    alias_hits = [alias_map[t] for t in tokens if t in alias_map]
    if alias_hits:
        return random.choice(alias_hits)
    if tokens:
        return random.choice(tokens)
    if pool:
        return random.choice(pool)
    return fallback


def detect_compound_subject(tokens: list[str]) -> str:
    token_set = set(tokens)
    for pair, subject in COMPOUND_SUBJECTS.items():
        if all(part in token_set for part in pair):
            return subject
    return ""


def lock_subject(tokens: list[str]) -> str:
    priority = [t for t in tokens if t in SUBJECT_PRIORITY_WORDS]
    if not priority:
        return ""
    if len(priority) >= 2 and tuple(priority[:2]) in COMPOUND_SUBJECTS:
        return COMPOUND_SUBJECTS[tuple(priority[:2])]
    if len(priority) == 1:
        return SUBJECT_ALIASES.get(priority[0], priority[0])
    resolved = []
    for t in priority[:3]:
        resolved.append(SUBJECT_ALIASES.get(t, t))
    return " and ".join(dict.fromkeys(resolved))


def should_include_tech(tokens: list[str]) -> bool:
    return any(t in TECH_TRIGGER_WORDS for t in tokens)


def get_theme_scene_mapping(subject: str) -> dict:
    """Get theme-specific scene mapping for stronger anchoring."""
    subject_lower = subject.lower()
    
    # Character/creature themes
    if any(char in subject_lower for char in ["witch", "wizard", "humanoid", "character"]):
        return {
            "focus": "character",
            "scene_elements": ["mystical setting", "character pose", "magical atmosphere"],
            "avoid": ["glass", "bottle", "table", "props", "studio"]
        }
    
    # Environmental themes
    elif "martian colony" in subject_lower:
        return {
            "focus": "environmental",
            "scene_elements": ["Mars terrain", "regolith", "habitat domes", "dusty horizon", "red planet atmosphere"],
            "avoid": ["glass", "bottle", "studio", "product", "table"]
        }
    
    elif "underwater city" in subject_lower:
        return {
            "focus": "environmental", 
            "scene_elements": ["submerged architecture", "bubbles", "caustic light", "aquatic atmosphere", "deep ocean setting"],
            "avoid": ["glass", "bottle", "studio", "product"]
        }
    
    elif "forest spirit" in subject_lower or any(forest in subject_lower for forest in ["forest", "woods", "tree"]):
        return {
            "focus": "environmental",
            "scene_elements": ["woodland", "roots", "mist", "moss", "ancient trees", "natural atmosphere"],
            "avoid": ["glass", "bottle", "studio", "product", "modern"]
        }
    
    # Default mapping
    return {
        "focus": "general",
        "scene_elements": ["atmospheric setting", "detailed environment"],
        "avoid": ["glass", "bottle", "studio props"]
    }


def _article(word: str) -> str:
    """Return 'an' if word starts with a vowel sound, else 'a'."""
    return "an" if word and word[0].lower() in "aeiou" else "a"


def _color_phrase(color: str) -> str:
    """Return color already-complete or append ' palette' only for bare single words."""
    if not color:
        return color
    cl = color.lower()
    if "palette" in cl or "tones" in cl or "hues" in cl:
        return color
    return f"{color} palette"


_ENV_SUBJECT_TOKENS = {
    "underwater city", "ancient temple", "ancient ruins", "spaceship cockpit",
    "steampunk laboratory", "martian colony", "retro arcade", "castle on a cliff",
    "wizard tower", "neon street market", "forest shrine", "floating island",
    "crystal cave", "ethereal meadow", "sacred grove", "mystic ruins",
    "bioluminescent swamp", "misty pond", "rainforest canopy", "lily pad marsh",
    "desert dune", "snowy tundra", "urban sewer", "volcanic lava", "swamp",
    "landscape", "cityscape", "mountain", "lake",
}


def build_sentence(subject: str, style: str, mood: str, color: str, lighting: str, atmosphere: str, tech: str, scenic_mode: bool, setting: str = "") -> str:
    # Get theme-specific mapping
    theme_mapping = get_theme_scene_mapping(subject)

    # If the subject is itself a location/environment, treat it as scenic.
    # Also drop the extra setting to avoid two locations colliding
    # (e.g. "underwater city in a forest shrine" makes no sense).
    subject_lower = subject.lower().strip()
    if any(env in subject_lower for env in _ENV_SUBJECT_TOKENS):
        scenic_mode = True
        setting = ""        # subject IS the setting; don't add a second one
        atmosphere = ""     # suppress atmosphere too — one environment is enough

    # If frog + atmosphere (no tech), prefer scenic mode
    frog_detected = "frog" in subject_lower
    has_atmosphere = bool(atmosphere and atmosphere.strip())
    has_tech = bool(tech and tech.strip())

    if frog_detected and has_atmosphere and not has_tech:
        scenic_mode = True

    # Filter out prop-heavy elements based on theme mapping
    avoid_terms = theme_mapping["avoid"]
    
    def filter_element(element: str) -> bool:
        if not element:
            return False
        element_lower = element.lower()
        return not any(avoid in element_lower for avoid in avoid_terms)
    
    # Filter inputs
    atmosphere = atmosphere if filter_element(atmosphere) else ""
    tech = tech if filter_element(tech) else ""
    setting = setting if filter_element(setting) else ""
    
    # Scenic/landscape mode — no character focal point
    if scenic_mode and not any(x in subject for x in ["cat", "frog", "doll"]):
        parts = [f"{_article(_mood_subj(mood))} {_mood_subj(mood)} {subject}"]
        if setting:
            parts.append(f"in a {setting}")
        parts.append(f"rendered in a {style} style")
        if atmosphere:
            parts.append(f"with {atmosphere} filling the scene")
        if color:
            parts.append(f"in a {_color_phrase(color)}")
        if lighting:
            parts.append(f"under {lighting}")
        return ", ".join(parts)

    # Theme-aware scene building
    if theme_mapping["focus"] == "character":
        # Character-focused: emphasize character and setting
        scene_layers = []
        scene_layers.append(f"{_article(_mood_subj(mood))} {_mood_subj(mood)} {subject} depicted in a {style} art style")
        
        # Environment layer - setting takes priority, then atmosphere/tech
        env_details = [x for x in [setting, atmosphere, tech] if x and filter_element(x)]
        if env_details:
            if setting and env_details[0] == setting:
                scene_layers.append(f"in a {setting}")
                remaining = [x for x in env_details[1:] if x != setting]
                if remaining:
                    scene_layers.append("with " + ", ".join(remaining))
            else:
                scene_layers.append("set in " + ", ".join(env_details))
        
        # Color + lighting layer
        if color and lighting:
            cl = color.lower()
            if "palette" in cl or "tones" in cl or "hues" in cl:
                scene_layers.append(f"bathed in {lighting} with {color}")
            else:
                scene_layers.append(f"bathed in {lighting} with {color} tones")
        elif lighting:
            scene_layers.append(f"illuminated by {lighting}")
        elif color:
            scene_layers.append(f"with {_color_phrase(color)}")
            
        return ", ".join(scene_layers)
    
    elif theme_mapping["focus"] == "environmental":
        # Environmental-focused: emphasize environment and composition
        scene_layers = []
        scene_layers.append(f"{_article(_mood_subj(mood))} {_mood_subj(mood)} {subject} in {style} style")
        
        # Environment layer: prioritize setting, then atmosphere, then theme_elements
        if setting:
            scene_layers.append(f"in a {setting}")
        elif has_atmosphere:
            # User selected explicit atmosphere - use it as the primary environment
            scene_layers.append(f"in {atmosphere}")
        else:
            # No explicit atmosphere - use theme-specific scene elements
            theme_elements = theme_mapping["scene_elements"][:3]  # Max 3 elements
            if theme_elements:
                scene_layers.append("featuring " + ", ".join(theme_elements))
        
        # Color + lighting
        if lighting:
            scene_layers.append(f"under {lighting}")
        if color:
            scene_layers.append(f"with {_color_phrase(color)}")

        return ", ".join(scene_layers)

    # General fallback - cleaner, prop-light
    scene_layers = []
    scene_layers.append(f"{_article(_mood_subj(mood))} {_mood_subj(mood)} {subject} in {style} style")
    
    # Setting takes priority in environment description
    if setting:
        scene_layers.append(f"in a {setting}")
    
    # Only include non-prop elements
    clean_elements = [x for x in [atmosphere, tech] if x and filter_element(x)]
    if clean_elements:
        scene_layers.append("with " + ", ".join(clean_elements))
    
    if lighting:
        scene_layers.append(f"under {lighting}")
    if color:
        cl = color.lower()
        if "palette" in cl or "tones" in cl or "hues" in cl:
            scene_layers.append(f"with {color}")
        else:
            scene_layers.append(f"with {color} tones")
    
    return ", ".join(scene_layers)


def generate_themes(count: int = 5, user_keywords=None, subject_lock: bool = True, custom_subject: str = "",
                    explicit_subject: str = "", explicit_setting: str = "", explicit_style: str = "", explicit_lighting: str = "",
                    explicit_mood: str = "", explicit_color: str = "", explicit_atmosphere: str = "") -> list[dict]:
    # Expand user keywords using the keyword expansion system (lazy-init)
    expanded_keywords = []
    if user_keywords:
        expander = get_lazy_keyword_expander()
        if expander:
            for keyword in user_keywords:
                try:
                    expanded_keyword = expander.expand_keyword(keyword)
                    expanded_keywords.append(expanded_keyword)
                except Exception:
                    expanded_keywords.append(keyword)
        else:
            expanded_keywords = user_keywords or []
    else:
        expanded_keywords = []
    
    kw = load_keywords()
    user_buckets = sort_user_keywords(expanded_keywords)
    tokens = tokenize_keywords(expanded_keywords)

    # Bias toward scenic mode when frog + environment detected.
    # Do NOT activate frog/env scenic bias when an explicit non-frog subject is set —
    # the user's subject is the focal point, not the scene.
    frog_detected = any("frog" in t for t in tokens)
    env_detected = any(t in SCENIC_WORDS for t in tokens)
    explicit_is_frog = "frog" in explicit_subject.lower() if explicit_subject else False
    explicit_is_set = bool(explicit_subject)
    if explicit_is_set and not explicit_is_frog:
        # Subject is a protected literal — do not impose env/frog scenic override
        scenic_mode = False
    else:
        scenic_mode = env_detected or (frog_detected and random.random() < 0.6)
    include_tech = should_include_tech(tokens)

    literal_subject = custom_subject if custom_subject and subject_lock else ""

    themes = []
    for i in range(count):
        # Use explicit UI selections when available — these are the source of truth
        # Only fall back to keyword/alias/pool logic when a field is blank.
        if explicit_subject:
            subject = explicit_subject
        elif literal_subject:
            subject = literal_subject
        else:
            compound_subject = detect_compound_subject(tokens)
            locked_subject = lock_subject(tokens)
            if compound_subject:
                subject = compound_subject
            elif locked_subject:
                subject = locked_subject
            else:
                # Bias toward frog subjects when frog detected in keywords (80% chance)
                if any("frog" in t for t in tokens) and random.random() < 0.8:
                    frog_subjects = [s for s in kw.get("subjects", []) if "frog" in s.lower()]
                    if frog_subjects:
                        subject = random.choice(frog_subjects)
                    else:
                        subject = choose_from_alias_or_pool(
                            user_buckets.get("subjects", []), SUBJECT_ALIASES, kw.get("subjects", []), "cinematic wallpaper subject"
                        )
                # General bias toward frog subjects even without explicit frog keywords (85% chance)
                elif random.random() < 0.85:
                    frog_subjects = [s for s in kw.get("subjects", []) if "frog" in s.lower()]
                    if frog_subjects:
                        subject = random.choice(frog_subjects)
                    else:
                        subject = choose_from_alias_or_pool(
                            user_buckets.get("subjects", []), SUBJECT_ALIASES, kw.get("subjects", []), "cinematic wallpaper subject"
                        )
                elif user_buckets.get("subjects"):
                    subject = choose_from_alias_or_pool(
                        user_buckets.get("subjects", []), SUBJECT_ALIASES, kw.get("subjects", []), "cinematic wallpaper subject"
                    )
                else:
                    subject = choose_from_alias_or_pool([], SUBJECT_ALIASES, kw.get("subjects", []), "cinematic wallpaper subject")

        if explicit_style:
            style = explicit_style
        else:
            style = choose_from_alias_or_pool(
                user_buckets.get("styles", []), STYLE_ALIASES, kw.get("styles", kw.get("style", [])), "cinematic wallpaper art"
            )

        if explicit_mood:
            mood = explicit_mood
            # Strengthen mood phrasing for better image generation
            if VALIDATOR_AVAILABLE:
                mood = strengthen_mood(mood)
        else:
            # Frog-biased mood only applies when the literal subject is a frog type
            if not explicit_is_set and any("frog" in t for t in tokens) and random.random() < 0.7:
                frog_moods = ["mystical", "serene", "whimsical"]
                mood = random.choice(frog_moods)
            else:
                mood = choose_from_alias_or_pool(
                    user_buckets.get("mood", []), MOOD_ALIASES, kw.get("mood", []), "moody"
                )

        # Color handling: use explicit color if provided, otherwise choose from pool
        if explicit_color:
            # Apply color alias first
            color = COLOR_ALIASES.get(explicit_color.lower(), explicit_color)
            # Strengthen color phrasing for better image generation
            if VALIDATOR_AVAILABLE:
                color = strengthen_color(color)
        else:
            color = choose_from_alias_or_pool(
                user_buckets.get("colors", []), COLOR_ALIASES, kw.get("colors", []), "rich dramatic color"
            )

        # Lighting: vary per theme if not explicitly set
        if explicit_lighting:
            lighting = explicit_lighting
        else:
            lighting = choose_from_alias_or_pool(
                user_buckets.get("lighting", []), LIGHTING_ALIASES, kw.get("lighting", []), "cinematic lighting"
            )
            # Add variation: 30% chance to use alternative lighting
            if i > 0 and random.random() < 0.3:
                alt_lightings = ["golden hour", "moonlight", "dramatic chiaroscuro", "backlit silhouette", "volumetric"]
                lighting = random.choice(alt_lightings)

        # Atmosphere: use explicit user selection if provided, otherwise generate
        if explicit_atmosphere:
            atmosphere = explicit_atmosphere
        elif not explicit_is_set and any("frog" in t for t in tokens) and random.random() < 0.7:
            # Frog-biased atmospheres only when no explicit (non-frog) subject is set
            env_atmospheres = ["misty pond", "rainforest canopy", "lily pad marsh", "desert dune", "snowy tundra", "urban sewer", "cosmic nebula", "ancient ruins", "volcanic lava", "low valley fog", "bioluminescent swamp"]
            atmosphere = random.choice(env_atmospheres)
        else:
            atmosphere = choose_from_alias_or_pool(
                user_buckets.get("atmosphere", []), ATMOSPHERE_ALIASES, kw.get("atmosphere", []), "soft atmospheric depth"
            )
        
        # Setting: use explicit user selection if provided
        setting = explicit_setting if explicit_setting else ""
        
        # Add composition variation per theme
        composition = choose_from_alias_or_pool(
            user_buckets.get("composition", []), COMPOSITION_ALIASES, kw.get("composition", []), "wide cinematic desktop wallpaper framing"
        )
        # Vary composition for subsequent themes
        if i > 0 and random.random() < 0.4:
            alt_compositions = ["close-up portrait", "dramatic wide shot", "heroic centered composition", "dynamic angle", "environmental wide shot"]
            composition = random.choice(alt_compositions)
        
        # Add color phrasing variation if not explicit
        varied_color = color
        if not explicit_color and i > 0 and random.random() < 0.3:
            color_variations = {
                "emerald": ["emerald green", "verdant emerald", "deep emerald"],
                "neon purple": ["vibrant purple", "electric purple", "neon violet"],
                "crimson red": ["deep crimson", "vivid crimson", "rich red"],
            }
            for base, variations in color_variations.items():
                if base in color.lower():
                    varied_color = random.choice(variations)
                    break

        tech = ""

        if include_tech and not scenic_mode:
            tech = random.choice(kw.get("tech_elements", [])) if kw.get("tech_elements") else ""

        themes.append({
            "theme_id": i + 1,
            "sentence": build_sentence(subject, style, mood, varied_color, lighting, atmosphere, tech, scenic_mode, setting),
            "components": {
                "subject": subject,
                "setting": setting,
                "style": style,
                "tech": tech,
                "mood": mood,
                "color": varied_color,
                "lighting": lighting,
                "atmosphere": atmosphere,
                "composition": composition,
                "scenic_mode": scenic_mode,
            },
        })
    return themes


def print_themes(themes: list[dict]) -> None:
    print("\n" + "=" * 60)
    print("  GENERATED THEMES")
    print("=" * 60)
    for t in themes:
        print(f"\n  Theme #{t['theme_id']}")
        print(f"  {t['sentence']}")
        print(f"  Composition: {t['components']['composition']}")
    print("\n" + "=" * 60)
