"""
prompt_builder.py
-----------------
Builds structured, high-quality prompts for AI image generation.

Design principles:
  - Fixed section order: subject → scene → lighting → mood → palette → composition → style → quality → negatives
  - Subject lock: subject named at start AND repeated in the composition anchor
  - Detail budget: max 3–5 scene details to avoid token dilution
  - Per-mode quality phrasing: stylized / realistic / product-photo / surreal differ intentionally
  - Per-mode negative suffix baked in at build time for tighter model compliance
"""

import re
import logging

# Import prompt validator for audit functionality
try:
    from prompt_validator import audit_prompt_variables, log_prompt_audit, get_audit_warnings, format_audit_summary
    VALIDATOR_AVAILABLE = True
except ImportError:
    VALIDATOR_AVAILABLE = False

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clean_text(value: str) -> str:
    """Normalise whitespace and strip leading/trailing spaces."""
    value = (value or "").strip()
    value = re.sub(r"\s+", " ", value)
    return value


def _subject_anchor(subject: str) -> str:
    """
    Subject lock — opening clause.
    States the subject clearly, sets focal-point expectations,
    enforces visibility and framing constraints.
    """
    subject = clean_text(subject)
    if not subject:
        return (
            "Single clear subject, fully visible and centered, "
            "not cropped, not obscured by other elements, "
            "subject must be clearly recognizable and identifiable"
        )
    cap = subject.capitalize()
    return (
        f"Single main subject: {subject}. "
        f"{cap} is fully visible, centered, and not cropped. "
        f"{cap} is the dominant focal point with sharp detail. "
        f"{cap} must be clearly recognizable and unmistakably identifiable as {subject}. "
        f"Nothing obscures or competes with {subject}"
    )


_CREATURE_CHARACTER_KEYWORDS = {
    "dragon", "phoenix", "griffin", "unicorn", "wolf", "cat", "frog", "spider",
    "horse", "eagle", "serpent", "shark", "creature", "beast", "monster",
    "person", "people", "human", "man", "woman", "girl", "boy",
    "character", "humanoid", "witch", "wizard", "mage", "sorcerer", "sorceress",
    "hero", "villain", "avatar", "warrior", "knight", "samurai", "ninja",
    "spirit", "specter", "wraith", "phantom", "ghost", "demon", "angel",
    "guardian", "sentinel", "deity", "god", "goddess", "nymph",
}


def _is_creature_or_character(subject: str) -> bool:
    sl = subject.lower()
    return any(kw in sl for kw in _CREATURE_CHARACTER_KEYWORDS)


def _composition_anchor(subject: str, scenic_mode: bool, custom_composition: str) -> str:
    """
    Composition clause — repeats subject to reinforce the lock.
    Uses custom composition if provided, otherwise picks a sensible default.
    Never uses product-photo framing language for living subjects.
    """
    subject = clean_text(subject)
    label = subject if subject else "the subject"

    if custom_composition:
        return custom_composition

    is_living = _is_creature_or_character(subject)

    if scenic_mode and "frog" in subject.lower():
        # Add variety to frog positioning - not always centered
        import random
        frog_positions = [
            f"Wide cinematic 16:9, {label} positioned dynamically in immersive environment",
            f"Wide cinematic 16:9, {label} off-center with environmental storytelling",
            f"Wide cinematic 16:9, {label} at varying angles within immersive environment",
            f"Wide cinematic 16:9, {label} naturally placed in environmental context",
            f"Wide cinematic 16:9, {label} with asymmetric composition in immersive environment"
        ]
        return random.choice(frog_positions)
    elif scenic_mode:
        return (
            f"Wide cinematic 16:9 panoramic framing; "
            f"{label} anchors the composition with clear breathing room on all sides"
        )
    elif is_living:
        return (
            f"16:9 desktop wallpaper framing; {label} centered, "
            f"facing camera or 3/4 angle, background fully separated from subject"
        )
    return (
        f"16:9 desktop wallpaper framing; {label} centred with clear breathing room, "
        f"background fully separated from subject"
    )


# ---------------------------------------------------------------------------
# Per-mode configuration
# ---------------------------------------------------------------------------

# quality_lead  — the opening quality descriptor for this mode (replaces the generic label)
# quality_close — closing technical constraint for this mode
# negative      — negative-prompt suffix baked in at build time

_HAND_NEGATIVES = (
    "extra fingers, missing fingers, fused fingers, melted fingers, too many fingers, "
    "three fingers, four fingers, six fingers, seven fingers, wrong number of fingers, "
    "claw hands, claw-like fingers, talon fingers, bent fingers, broken fingers, "
    "bad hands, malformed hands, extra hands, duplicate hands, merged hands, "
    "reversed hands, backwards hands, mirrored hands, inverted palms, wrong hand orientation, "
    "missing hand, severed hand, floating hand, disembodied hand, "
    "broken wrists, twisted wrists, extra arms, missing arms, extra limbs, "
    "extra legs, missing legs, extra feet, missing feet, extra toes, wrong number of toes, "
    "fused legs, fused feet, malformed feet, bad feet, deformed feet, "
    "extra limbs, wrong number of limbs, missing limbs, fused limbs, "
    "three arms, three legs, three hands, three feet, "
    "multiple arms, multiple legs, multiple hands, multiple feet, "
    "duplicate limbs, extra body parts, extra appendages"
)

_FACE_NEGATIVES = (
    "hood over face, face hidden by hood, covered face, obscured face, face not visible, "
    "mask covering face, veil over face, shadow hiding face, faceless, headless, no face, "
    "extra heads, two heads, multiple heads, duplicate heads, fused heads, "
    "extra face, two faces, multiple faces, duplicate faces, fused faces, "
    "split head, divided head, double head, triple head, extra necks, multiple necks"
)

# Common negative fragments shared across modes (DRY consolidation)
_COMMON = {
    "blurry_resolution": "blurry, soft focus, low resolution, grainy, noisy, pixelated",
    "anatomy_bad": "deformed, malformed, bad anatomy, misshapen, morphed, amorphous, "
                   "disfigured, distorted, warped, twisted, contorted, "
                   "unnatural body proportions, wrong proportions, "
                   "asymmetric limbs, uneven limbs, mismatched limbs, "
                   "mutated, genetic defects, birth defects",
    "art_style_cartoon": "cartoon, illustration, anime, painting, drawn, sketch",
    "art_style_3d": "3D render, plastic sheen, synthetic textures",
    "text_watermark": "",
    "glass_objects": "glass objects, glass pieces, stemware, bottles",
    "transparent_materials": "transparent objects, clear materials, glassware, crystal",
    "clutter": "busy background, background objects, clutter, distractions",
    "exposure_bad": "overexposed, underexposed, flat lighting",
}

_MODE_CONFIG = {
    "stylized": {
        "style_base": "stylized digital illustration, bold readable shapes, strong silhouettes",
        "quality_lead": "high visual contrast, vivid saturated colours, sharp clean edges, subject must remain clearly recognizable",
        "quality_close": "wallpaper-ready composition, no gradients that lose subject definition, style must not obscure subject identity",
        "negative": (
            f"{_COMMON['glass_objects']}, "
            "low detail, "
            f"{_COMMON['blurry_resolution']}, {_COMMON['anatomy_bad']}, "
            f"{_COMMON['text_watermark']}, "
            f"{_HAND_NEGATIVES}, {_FACE_NEGATIVES}, "
            f"{_COMMON['transparent_materials']}, "
            "abstract blob, undefined shape, amorphous form, unrecognizable subject, pattern without clear subject, style overwhelming subject"
        ),
    },
    "realistic": {
        "style_base": "photorealistic render, natural materials, real-world textures",
        "quality_lead": "sharp subject detail, cinematic shallow depth of field, clean background separation, subject must remain clearly recognizable",
        "quality_close": "professional photography quality, physically accurate lighting, no plastic sheen, style must not obscure subject identity",
        "negative": (
            f"{_COMMON['glass_objects']}, {_COMMON['art_style_cartoon']}, "
            f"{_COMMON['blurry_resolution']}, {_COMMON['anatomy_bad']}, "
            f"{_HAND_NEGATIVES}, {_FACE_NEGATIVES}, "
            f"{_COMMON['text_watermark']}, {_COMMON['clutter']}, "
            f"{_COMMON['exposure_bad']}, fake plastic look, "
            f"{_COMMON['transparent_materials']}, "
            "abstract blob, undefined shape, amorphous form, unrecognizable subject, pattern without clear subject"
        ),
    },
    "product-photo": {
        "style_base": "studio product photography, clean controlled lighting, precise sharp focus",
        "quality_lead": "subject razor-sharp edge-to-edge, neutral or gradient background, zero clutter",
        "quality_close": "commercial-grade image quality, colour-accurate, no shadows bleeding onto subject",
        "negative": (
            f"{_COMMON['glass_objects']}, "
            "people, faces, hands, figures, animals, "
            f"{_COMMON['clutter']}, "
            f"{_COMMON['text_watermark']}, "
            "blurry, soft focus, "
            f"{_COMMON['anatomy_bad']}, "
            f"{_HAND_NEGATIVES}, "
            f"{_COMMON['blurry_resolution']}, {_COMMON['exposure_bad']}, "
            "low quality, compression artifacts, fake plastic look, "
            f"{_COMMON['transparent_materials']}"
        ),
    },
    "surreal": {
        "style_base": "surreal dreamlike scene, impossible atmosphere, otherworldly scale",
        "quality_lead": "strange yet readable composition, subject unmistakably recognisable despite surreal context, subject must remain clearly identifiable",
        "quality_close": "high imaginative detail, vivid impossible colours, dreamlike but structurally coherent, style must not obscure subject identity",
        "negative": (
            f"{_COMMON['glass_objects']}, "
            "mundane, ordinary, plain, boring, photorealistic, "
            f"{_COMMON['blurry_resolution']}, deformed beyond recognition, "
            f"{_HAND_NEGATIVES}, {_FACE_NEGATIVES}, "
            f"{_COMMON['text_watermark']}, "
            "subject unrecognisable, amorphous blob, undefined shape, pattern without clear subject, style overwhelming subject, "
            f"{_COMMON['transparent_materials']}, "
            "cozy interiors, tech clutter, room scenes"
        ),
    },
    "anime": {
        "style_base": "high-quality anime key visual, cel-shaded illustration, clean line art, vibrant flat colours",
        "quality_lead": "sharp clean outlines, expressive character detail, dynamic pose, studio-quality anime finish, subject must remain clearly recognizable",
        "quality_close": "wallpaper-ready 16:9 anime composition, cohesive colour harmony, no rough linework, style must not obscure subject identity",
        "negative": (
            f"photorealistic, {_COMMON['art_style_3d']}, photograph, live action, "
            "blurry, soft lines, low detail, smudged, rough sketch, "
            "bad proportions, off-model, inconsistent style, "
            f"{_HAND_NEGATIVES}, {_FACE_NEGATIVES}, "
            f"{_COMMON['text_watermark']}, "
            "western cartoon style, thick outlines without fill, "
            f"{_COMMON['transparent_materials']}, "
            "abstract blob, undefined shape, amorphous form, unrecognizable subject, pattern without clear subject, style overwhelming subject"
        ),
    },
    "dark-fantasy": {
        "style_base": "dark fantasy concept art, dramatic shadows, moody atmospheric depth, gothic grandeur",
        "quality_lead": "rich shadow detail, high contrast chiaroscuro, brooding colour palette, epic scale, subject must remain clearly recognizable",
        "quality_close": "AAA game concept art quality, painterly textures, no flat shading, deep atmospheric perspective, style must not obscure subject identity",
        "negative": (
            "bright cheerful colours, pastel, cute, cartoony, anime, "
            f"{_COMMON['exposure_bad']}, washed out, low contrast, "
            f"{_COMMON['blurry_resolution']}, low detail, "
            f"{_HAND_NEGATIVES}, {_FACE_NEGATIVES}, "
            f"{_COMMON['text_watermark']}, "
            "modern setting, sci-fi tech, contemporary clothing, "
            f"{_COMMON['transparent_materials']}, "
            "abstract blob, undefined shape, amorphous form, unrecognizable subject, pattern without clear subject, style overwhelming subject"
        ),
    },
    "painterly": {
        "style_base": "expressive painterly illustration, visible brushwork, rich textured canvas, fine art quality",
        "quality_lead": "masterful brushstroke detail, warm luminous colour, impressionistic light and shadow, subject must remain clearly recognizable",
        "quality_close": "gallery-quality fine art composition, no flat digital look, organic texture throughout, style must not obscure subject identity",
        "negative": (
            "flat digital art, vector art, clean hard edges, cel shading, "
            f"photorealistic, {_COMMON['art_style_3d']}, "
            "blurry background without intentional bokeh, low detail, "
            f"{_HAND_NEGATIVES}, {_FACE_NEGATIVES}, "
            f"{_COMMON['text_watermark']}, "
            "over-smooth, airbrushed, "
            f"{_COMMON['transparent_materials']}, "
            "abstract blob, undefined shape, amorphous form, unrecognizable subject, pattern without clear subject, style overwhelming subject"
        ),
    },
    "pixel-art": {
        "style_base": "high-quality pixel art, crisp pixel grid, retro game aesthetic, limited colour palette",
        "quality_lead": "clean pixel-perfect edges, readable silhouette at all scales, intentional dithering, subject must remain clearly recognizable",
        "quality_close": "16-bit or 32-bit era quality, consistent pixel size, strong contrast between foreground and background, style must not obscure subject identity",
        "negative": (
            "blurry, anti-aliased, smooth gradients, photorealistic, 3D render, "
            "watercolour, oil painting, soft focus, "
            "inconsistent pixel size, mixed resolutions, "
            f"{_HAND_NEGATIVES}, "
            f"{_COMMON['text_watermark']}, "
            f"{_COMMON['blurry_resolution']}, low quality upscale, jpeg artifacts, "
            "abstract blob, undefined shape, amorphous form, unrecognizable subject, pattern without clear subject, style overwhelming subject"
        ),
    },
    "cinematic": {
        "style_base": "cinematic widescreen composition, anamorphic lens render, film-quality lighting and colour grade",
        "quality_lead": "movie-poster depth of field, dramatic lighting ratio, rich shadow and highlight detail, subject must remain clearly recognizable",
        "quality_close": "professional colour grading, sharp foreground with atmospheric background, no flat or amateur lighting, style must not obscure subject identity",
        "negative": (
            f"{_COMMON['art_style_cartoon']}, "
            "flat lighting, even exposure, no depth, "
            f"{_COMMON['blurry_resolution']}, "
            "blown highlights, crushed blacks, "
            f"{_HAND_NEGATIVES}, {_FACE_NEGATIVES}, "
            f"{_COMMON['text_watermark']}, "
            f"{_COMMON['transparent_materials']}, "
            "abstract blob, undefined shape, amorphous form, unrecognizable subject, pattern without clear subject, style overwhelming subject"
        ),
    },
    "minimalist": {
        "style_base": "clean minimalist design, negative space composition, bold simple shapes, limited colour palette",
        "quality_lead": "elegant simplicity, strong focal subject with maximum breathing room, no visual noise, subject must remain clearly recognizable",
        "quality_close": "poster-quality minimalist layout, crisp edges, cohesive 2-3 colour palette, desktop-icon-safe negative space, style must not obscure subject identity",
        "negative": (
            f"{_COMMON['clutter']}, many objects, complex textures, "
            "detailed patterns, noise, gradients, photorealistic, "
            "too many colours, rainbow palette, chaotic composition, "
            f"{_HAND_NEGATIVES}, {_FACE_NEGATIVES}, "
            f"{_COMMON['text_watermark']}, "
            f"{_COMMON['transparent_materials']}, "
            "abstract blob, undefined shape, amorphous form, unrecognizable subject, pattern without clear subject, style overwhelming subject"
        ),
    },
}

_DEFAULT_MODE = "stylized"


# ---------------------------------------------------------------------------
# Subject-aware creature anatomy
# ---------------------------------------------------------------------------

# Maps subject keyword -> (positive anatomy constraint, extra negative terms)
# Positive is appended to the quality block; negatives extend the mode negatives.
_CREATURE_ANATOMY = {
    "banshee": (
        "Anatomy lock: ghostly female humanoid figure, translucent spectral form, flowing tattered robes, "
        "pale translucent skin, hollow sunken eyes, long disheveled hair, screaming mouth open in wail, "
        "ethereal wraith-like appearance, no solid physical body, floating or standing posture, "
        "two arms, two legs, one head, human female silhouette clearly visible",
        "owl, bird, eagle, hawk, raven, crow, falcon, any bird species, beak, feathers, wings, talons, "
        "animal, creature, beast, solid physical body, opaque skin, normal human appearance, "
        "male figure, masculine features, hooded figure, masked face, covered face",
    ),
    "dragon": (
        "Anatomy lock: exactly two large wings both simultaneously visible and fully spread, "
        "both wings attached to the upper back, one wing clearly visible on each side of the body; "
        "the second wing is NOT hidden behind the body or obscured; "
        "one long tail clearly separate from the wings; "
        "four legs properly formed; "
        "IMPORTANT: dragon viewed from front or 3/4 angle, NOT side profile — "
        "both wings must be in frame at the same time",
        "side profile view, side view, profile shot, dragon viewed from the side, "
        "one wing, single wing, missing wing, only one wing visible, wing hidden behind body, "
        "tail mistaken for wing, wing that is actually a tail, "
        "three tails, multiple tails, extra tails, split tail, "
        "three wings, extra wings, half wing, partial wing, asymmetric wings, "
        "extra legs, missing legs, extra heads, two heads",
    ),
    "phoenix": (
        "Anatomy lock: exactly two wings, one tail, two legs; "
        "wings symmetrical and fully formed; single flowing tail",
        "extra wings, three wings, extra tails, split tail, extra legs, missing legs",
    ),
    "griffin": (
        "Anatomy lock: exactly two wings, four limbs, one tail, one head; "
        "wings symmetrical; front legs are eagle talons, rear legs are lion paws",
        "extra wings, extra tails, extra heads, missing limbs, extra limbs",
    ),
    "unicorn": (
        "Anatomy lock: four legs, one horn, one tail, two eyes; "
        "single straight horn on forehead; no wings unless explicitly described as alicorn",
        "extra horns, two horns, extra legs, missing legs, wings (unless alicorn), "
        "extra tails, split tail",
    ),
    "wolf": (
        "Anatomy lock: four legs, two ears, one tail, one head",
        "extra tails, multiple tails, extra legs, extra heads, extra ears",
    ),
    "cat": (
        "Anatomy lock: four legs, two ears, one tail, one head",
        "extra tails, multiple tails, extra legs, extra heads",
    ),
    "frog": (
        "Anatomy lock: clearly recognizable frog shape with four limbs, two large bulging eyes, one head, no tail; "
        "front legs shorter than rear legs; wide mouth; distinct frog body silhouette; "
        "frog must be unmistakably identifiable as a frog, not abstract patterns; "
        "varied poses: sitting, perching, leaping, swimming, or climbing; "
        "dynamic angles: side view, front view, 3/4 view, or overhead perspective",
        "extra limbs, tail on frog, extra eyes, extra heads, abstract blob, undefined shape, amorphous form, unrecognizable subject, pattern without clear subject",
    ),
    "spider": (
        "Anatomy lock: exactly eight legs, two body segments, one head",
        "six legs, ten legs, wrong number of legs, extra body segments",
    ),
    "horse": (
        "Anatomy lock: four legs, one tail, two ears, one head, one mane",
        "extra legs, extra tails, extra heads, missing legs",
    ),
    "eagle": (
        "Anatomy lock: realistic adult bald eagle proportions, broad fingered wings, proper feather layering, white head, dark brown body, hooked yellow beak, visible yellow talons, natural pose behavior. Allowed poses: soaring, perched on a branch, gliding, diving, landing, hunting. Photoreal wildlife anatomy and believable motion.",
        "floating posture, broken wing geometry, deformed feet, extra limbs, stiff necks, clipped tails, unrealistic fantasy-bird shapes, extra wings, extra legs, extra tails, extra heads, missing wings",
    ),
    "serpent": (
        "Anatomy lock: single continuous serpentine body, no limbs, one head; "
        "body tapers naturally to the tail tip",
        "legs on serpent, arms on serpent, extra heads, split body",
    ),
    "shark": (
        "Anatomy lock: one dorsal fin, two pectoral fins, one tail fin, one head",
        "extra fins, extra tails, extra heads, legs on shark",
    ),
}


def get_creature_anatomy(subject: str):
    """Return (positive_constraint, extra_negatives) for the detected creature type,
    or (None, None) if subject does not match any known creature."""
    sl = subject.lower()
    for keyword, (pos, neg) in _CREATURE_ANATOMY.items():
        if keyword in sl:
            return pos, neg
    return None, None



# ---------------------------------------------------------------------------
# Core builder
# ---------------------------------------------------------------------------

def build_prompt(theme: dict, style_mode: str = "stylized", ui_values: dict = None, run_audit: bool = False) -> dict:
    """
    Build a structured, high-quality prompt from a theme dict.

    Section order (fixed):
      1. Subject lock (opening anchor)
      2. Scene / environment (detail-budgeted, max 4 items)
      3. Lighting
      4. Mood
      5. Colour palette
      6. Composition anchor (repeats subject — subject lock #2)
      7. Style descriptor
      8. Quality constraints (mode-specific)
      9. Hard exclusions (no text, watermark, etc.)

    Args:
        theme: Theme dict with components
        style_mode: Style mode (stylized, realistic, product-photo, surreal)
        ui_values: Optional dict of raw UI field values for audit
        run_audit: If True, run prompt variable audit and include in result

    Returns:
        Dict with prompt, negative_prompt, style_mode, subject, art_style, theme_id, theme_sentence,
        and optionally audit_results if run_audit=True
    """
    components = theme.get("components", {})

    # --- Extract fields - prioritize components for explicit user inputs
    subject     = clean_text(theme.get("subject", "")      or components.get("subject", ""))
    sentence    = clean_text(theme.get("sentence", ""))
    lighting    = clean_text(components.get("lighting", "") or theme.get("lighting", ""))
    # Prioritize user's explicit color selection over theme palette
    palette     = clean_text(components.get("color", ""))
    # Only use theme palette as fallback if user didn't explicitly select a color
    if not palette:
        palette = clean_text(theme.get("palette", ""))
    composition = clean_text(components.get("composition", "") or theme.get("composition", ""))
    # EXPLICIT ATMOSPHERE: prioritize user-selected atmosphere from Quick Build
    # components.atmosphere is the explicit user choice; theme.environment is auto-generated fallback
    explicit_atmosphere = clean_text(components.get("atmosphere", ""))
    atmosphere = explicit_atmosphere if explicit_atmosphere else clean_text(theme.get("environment", ""))
    mood        = clean_text(components.get("mood", "")    or theme.get("mood", ""))
    art_style   = clean_text(components.get("style", ""))
    tech        = clean_text(components.get("tech", ""))
    scenic_mode = components.get("scenic_mode", False)
    # Extract subject-specific negatives from theme
    subject_negatives = clean_text(theme.get("subject_negatives", ""))

    # product-photo mode is for inanimate objects — silently remap to realistic
    # for any creature or character subject to avoid "studio product photography" framing.
    _living_check = clean_text(theme.get("subject", "") or components.get("subject", ""))
    if style_mode == "product-photo" and _is_creature_or_character(_living_check):
        style_mode = "realistic"

    cfg = _MODE_CONFIG.get(style_mode, _MODE_CONFIG[_DEFAULT_MODE])

    # Detect humanoid/focal-creature subjects that need character framing, not landscape framing
    HUMANOID_KEYWORDS = {
        "person", "people", "human", "humanity", "man", "woman", "girl", "boy",
        "character", "humanoid", "witch", "wizard", "mage", "sorcerer", "sorceress",
        "hero", "villain", "avatar", "portrait", "personified",
        "spirit", "specter", "spectre", "wraith", "phantom", "elemental",
        "ghost", "demon", "angel", "deity", "god", "goddess", "nymph",
        "creature", "being", "entity", "guardian", "sentinel",
    }
    subject_lower = subject.lower() if subject else ""
    is_humanoid = any(k in subject_lower for k in HUMANOID_KEYWORDS)

    # ------------------------------------------------------------------
    # 1. Subject lock — opening anchor
    # ------------------------------------------------------------------
    s1_subject = _subject_anchor(subject)

    # ------------------------------------------------------------------
    # 2. Scene / environment — use the theme sentence which now includes
    #    explicit atmosphere when user selected one in Quick Build
    # ------------------------------------------------------------------
    scene_pool = []
    
    # Theme-to-scene mapping for stronger anchoring
    subject_lower = subject.lower() if subject else ""
    
    # Focal-subject keywords: spirit/creature types get character framing, not env framing
    _FOCAL_SUBJECT_KEYWORDS = {
        "spirit", "specter", "spectre", "wraith", "phantom", "elemental",
        "ghost", "demon", "angel", "deity", "god", "goddess", "nymph",
        "creature", "being", "entity", "guardian", "sentinel",
        "witch", "wizard", "humanoid", "character", "person", "human",
    }
    is_focal_subject = any(kw in subject_lower.split() for kw in _FOCAL_SUBJECT_KEYWORDS)

    # Standalone pure-environment subjects (only when NOT a focal character compound)
    _PURE_ENV_SUBJECTS = {"martian colony", "underwater city", "landscape", "cityscape", "mountain", "lake"}
    is_pure_env = (
        not is_focal_subject
        and any(env in subject_lower for env in _PURE_ENV_SUBJECTS)
    )

    # Character/creature/spirit themes — subject is the focal point
    if is_focal_subject:
        if sentence:
            scene_pool.append(sentence)
        if atmosphere and atmosphere not in (sentence or ""):
            scene_pool.append(atmosphere)
        # Limit to 3 items for character focus
        scene_pool = scene_pool[:3]

    # Environmental themes — subject IS the environment
    elif is_pure_env:
        if sentence:
            scene_pool.append(sentence)
        if atmosphere and atmosphere not in (sentence or ""):
            scene_pool.append(atmosphere)
        if lighting and lighting not in (sentence or ""):
            scene_pool.append(lighting)
        # Limit to 3-4 items for environmental focus
        scene_pool = scene_pool[:4]

    # Special handling for frog environments
    elif "frog" in subject_lower:
        if sentence:
            scene_pool.append(sentence)
        if atmosphere and atmosphere not in (sentence or ""):
            scene_pool.append(atmosphere)
        scene_pool = scene_pool[:3]
    
    # General fallback - tighter scene pool
    else:
        if sentence:
            scene_pool.append(sentence)
        if atmosphere and atmosphere not in (sentence or ""):
            scene_pool.append(atmosphere)
        # Only add tech if it doesn't introduce prop drift
        if tech and "glass" not in tech.lower() and "bottle" not in tech.lower() and tech not in (sentence or ""):
            scene_pool.append(f"{tech} elements")
        
        scene_pool = scene_pool[:3]  # Tighter cap for general subjects
    
    s2_scene = ", ".join(scene_pool) if scene_pool else ""

    # ------------------------------------------------------------------
    # 3. Lighting
    # ------------------------------------------------------------------
    s3_lighting = lighting if lighting else ""

    # ------------------------------------------------------------------
    # 4. Mood — adjective chain only (no "atmosphere" suffix in the value);
    #    we add the framing word here so it appears in the right section,
    #    never as a prefix to the subject.
    # ------------------------------------------------------------------
    s4_mood = f"{mood} mood" if mood else ""

    # ------------------------------------------------------------------
    # 5. Colour palette
    # ------------------------------------------------------------------
    s5_palette = palette if palette else ""

    # ------------------------------------------------------------------
    # 6. Composition anchor — subject repeated for lock #2
    # ------------------------------------------------------------------
    s6_composition = _composition_anchor(subject, scenic_mode, composition)

    # ------------------------------------------------------------------
    # 7. Style descriptor
    #    art_style from theme prefixes the mode base (e.g. "cyberpunk" + base)
    # ------------------------------------------------------------------
    style_base = cfg["style_base"]
    full_style = f"{art_style}, {style_base}" if art_style else style_base
    s7_style = f"Rendered as: {full_style}"

    # ------------------------------------------------------------------
    # 8. Quality constraints — mode-specific, no generic catch-all
    # ------------------------------------------------------------------
    s8_quality = f"{cfg['quality_lead']}. {cfg['quality_close']}. Ultra-high detail, 8K resolution"

    # Humanoid anatomy safety block
    if is_humanoid:
        if style_mode in ("realistic", "product-photo"):
            anatomy_block = (
                "Strict anatomy: exactly two hands with five fingers each, correct orientation, palms facing naturally; "
                "no extra or duplicated hands or arms; no fused fingers, no malformed wrists, no reversed or backwards hands; "
                "face fully visible and unobstructed, no hood or mask covering the face; both hands anatomically correct"
            )
        else:
            anatomy_block = (
                "Anatomy lock: two hands only, five fingers per hand, correct hand orientation, no reversed hands, "
                "no extra hands or arms, no fused fingers; face clearly visible, not hidden by hood or mask"
            )
        s8_quality = s8_quality + ". " + anatomy_block

    # Creature anatomy safety block — subject-specific rules for non-humanoid creatures
    creature_pos, creature_neg = get_creature_anatomy(subject)
    if creature_pos and not is_humanoid:
        s8_quality = s8_quality + ". " + creature_pos

    # ------------------------------------------------------------------
    # 9. Hard exclusions (always present)
    # ------------------------------------------------------------------
    s9_exclusions = ""

    # ------------------------------------------------------------------
    # Assemble — skip empty sections, join with ". "
    # The atmosphere is now properly included in the theme sentence from build_sentence()
    # ------------------------------------------------------------------
    sections = [
        s1_subject,
        s2_scene,
        s3_lighting,
        s4_mood,
        s5_palette,
        s6_composition,
        s7_style,
        s8_quality,
        s9_exclusions,
    ]
    prompt_text = ". ".join(s for s in sections if s).strip()
    if not prompt_text.endswith("."):
        prompt_text += "."

    # ------------------------------------------------------------------
    # Negative prompt — baked in per-mode, always present
    # ------------------------------------------------------------------
    negative_text = cfg["negative"]

    # Append creature-specific negatives when subject is a known creature
    if creature_neg and not is_humanoid:
        negative_text = negative_text + ", " + creature_neg

    # Append subject-specific negatives from theme_mixer for drift prevention
    if subject_negatives:
        negative_text = negative_text + ", " + subject_negatives

    result = {
        "prompt":         prompt_text,
        "negative_prompt": negative_text,
        "style_mode":     style_mode,
        "subject":        subject,
        "art_style":      art_style,
        "theme_id":       theme.get("theme_id", 1),
        "theme_sentence": theme.get("sentence", ""),
    }

    # ------------------------------------------------------------------
    # Run prompt variable audit if requested
    # ------------------------------------------------------------------
    if run_audit and VALIDATOR_AVAILABLE and ui_values:
        audit_results = audit_prompt_variables(ui_values, components, prompt_text, style_mode)
        result["audit_results"] = audit_results
        log_prompt_audit(ui_values, components, prompt_text, style_mode, audit_results)

    return result


def build_all_prompts(themes: list, style_mode: str = "stylized", ui_values: dict = None, run_audit: bool = False) -> list:
    """Build prompts for all themes."""
    return [build_prompt(theme, style_mode=style_mode, ui_values=ui_values, run_audit=run_audit) for theme in themes]
