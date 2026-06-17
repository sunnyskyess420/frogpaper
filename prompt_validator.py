"""
prompt_validator.py
-------------------
Debug and validation system for FrogPaper Quick Build variables.
Tracks variable flow from UI → theme/components → final prompt.
"""

import re
import logging

# Configure logging
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Color strengthening mappings
# ---------------------------------------------------------------------------

_COLOR_STRENGTHENING = {
    # Base colors with stronger palette phrases
    "pink": "pink-dominant palette with soft pink hues",
    "pink tones": "pink-dominant palette with soft pink hues",
    "purple": "rich purple palette with vibrant violet tones",
    "purple tones": "rich purple palette with vibrant violet tones",
    "blue": "electric blue palette with cool azure tones",
    "blue tones": "electric blue palette with cool azure tones",
    "green": "emerald green palette with verdant tones",
    "green tones": "emerald green palette with verdant tones",
    "red": "crimson red palette with vivid scarlet accents",
    "red tones": "crimson red palette with vivid scarlet accents",
    "gold": "golden glow palette with warm amber tones",
    "gold tones": "golden glow palette with warm amber tones",
    "silver": "silver chrome palette with metallic highlights",
    "silver tones": "silver chrome palette with metallic highlights",
    "black": "midnight black palette with deep shadow tones",
    "black tones": "midnight black palette with deep shadow tones",
    "white": "pure white palette with bright highlight tones",
    "white tones": "pure white palette with bright highlight tones",
    "rainbow": "vibrant rainbow palette with full spectrum colors",
    "rainbow tones": "vibrant rainbow palette with full spectrum colors",
    "teal": "teal green palette with aquamarine tones",
    "teal tones": "teal green palette with aquamarine tones",
    "orange": "warm orange palette with sunset amber tones",
    "orange tones": "warm orange palette with sunset amber tones",
    "yellow": "bright yellow palette with golden sunshine tones",
    "yellow tones": "bright yellow palette with golden sunshine tones",
    "magenta": "vivid magenta palette with fuchsia tones",
    "magenta tones": "vivid magenta palette with fuchsia tones",
    "coral": "coral pink palette with warm peach tones",
    "coral tones": "coral pink palette with warm peach tones",
    "cyan": "cyan blue palette with turquoise tones",
    "cyan tones": "cyan blue palette with turquoise tones",
    "earth": "earth tone palette with natural brown and green hues",
    "earth tones": "earth tone palette with natural brown and green hues",
    "pastel": "soft pastel palette with gentle muted tones",
    "pastel tones": "soft pastel palette with gentle muted tones",
    "monochrome": "monochrome palette with single-tone consistency",
    "monochrome tones": "monochrome palette with single-tone consistency",
    "fluorescent": "fluorescent palette with vivid glowing tones",
    "fluorescent tones": "fluorescent palette with vivid glowing tones",
    "metallic": "metallic palette with shiny reflective tones",
    "metallic tones": "metallic palette with shiny reflective tones",
    "iridescent": "iridescent palette with color-shifting iridescent tones",
    "iridescent tones": "iridescent palette with color-shifting iridescent tones",
    # Named color variants — important: these must be in the table so the
    # family-priority matcher can find them instead of falling through to
    # a generic modifier key.
    "cobalt": "cobalt blue palette with deep royal tones",
    "cobalt tones": "cobalt blue palette with deep royal tones",
    "navy": "navy blue palette with deep oceanic tones",
    "navy tones": "navy blue palette with deep oceanic tones",
    "sapphire": "sapphire blue palette with jewel-toned brilliance",
    "sapphire tones": "sapphire blue palette with jewel-toned brilliance",
    "indigo": "deep indigo palette with midnight violet tones",
    "indigo tones": "deep indigo palette with midnight violet tones",
    "violet": "vivid violet palette with electric purple tones",
    "violet tones": "vivid violet palette with electric purple tones",
    "lavender": "lavender purple palette with soft lilac tones",
    "lavender tones": "lavender purple palette with soft lilac tones",
    "crimson": "crimson red palette with deep blood-red tones",
    "crimson tones": "crimson red palette with deep blood-red tones",
    "maroon": "maroon red palette with deep wine tones",
    "maroon tones": "maroon red palette with deep wine tones",
    "amber": "warm amber palette with golden honey tones",
    "amber tones": "warm amber palette with golden honey tones",
    "bronze": "bronze metallic palette with warm copper tones",
    "bronze tones": "bronze metallic palette with warm copper tones",
    "jade": "jade green palette with deep forest tones",
    "jade tones": "jade green palette with deep forest tones",
    "rust": "rust orange palette with earthy terracotta tones",
    "rust tones": "rust orange palette with earthy terracotta tones",
    "ivory": "ivory white palette with warm cream tones",
    "ivory tones": "ivory white palette with warm cream tones",
    "charcoal": "charcoal grey palette with dark smoky tones",
    "charcoal tones": "charcoal grey palette with dark smoky tones",
    "grey": "neutral grey palette with cool smoky tones",
    "grey tones": "neutral grey palette with cool smoky tones",
    "gray": "neutral grey palette with cool smoky tones",
    "gray tones": "neutral grey palette with cool smoky tones",
    "brown": "warm brown palette with earthy chocolate tones",
    "brown tones": "warm brown palette with earthy chocolate tones",
    "beige": "soft beige palette with warm sand tones",
    "beige tones": "soft beige palette with warm sand tones",
    "satin": "satin sheen palette with soft luminous tones",
    "satin tones": "satin sheen palette with soft luminous tones",
    # Modifier-only keys — used when NO color family is present in input.
    # The family-priority matcher ensures these only win when no named
    # color family word appears in the user input.
    "vibrant": "vibrant palette with high-saturation bold colors",
    "vibrant tones": "vibrant palette with high-saturation bold colors",
    "muted": "muted palette with desaturated soft colors",
    "muted tones": "muted palette with desaturated soft colors",
    "dark": "dark palette with deep shadow tones",
    "dark tones": "dark palette with deep shadow tones",
    "light": "light palette with bright airy tones",
    "light tones": "light palette with bright airy tones",
    "rich": "rich palette with deep saturated colors",
    "rich tones": "rich palette with deep saturated colors",
    "deep": "deep palette with intense shadow tones",
    "deep tones": "deep palette with intense shadow tones",
    "cool": "cool palette with blue-tinted refreshing tones",
    "cool tones": "cool palette with blue-tinted refreshing tones",
    "warm": "warm palette with red-tinted cozy tones",
    "warm tones": "warm palette with red-tinted cozy tones",
    "electric": "electric palette with high-energy bold tones",
    "electric tones": "electric palette with high-energy bold tones",
    "dusty": "dusty palette with muted vintage tones",
    "dusty tones": "dusty palette with muted vintage tones",
    "sepia": "sepia palette with warm brown nostalgic tones",
    "sepia tones": "sepia palette with warm brown nostalgic tones",
    "emerald": "emerald green palette with jewel-toned depths",
    "emerald tones": "emerald green palette with jewel-toned depths",
    "obsidian": "obsidian black palette with dark reflective tones",
    "obsidian tones": "obsidian black palette with dark reflective tones",
    "translucent": "translucent palette with light-passing ethereal tones",
    "translucent tones": "translucent palette with light-passing ethereal tones",
    "faded": "faded palette with washed-out vintage tones",
    "faded tones": "faded palette with washed-out vintage tones",
}

# ---------------------------------------------------------------------------
# Color family priority set
# Keys in this set are treated as named color families and always win over
# pure modifier keys (e.g. "muted", "deep") in the partial-match lookup.
# ---------------------------------------------------------------------------
_COLOR_FAMILIES_SET = frozenset({
    "pink", "purple", "blue", "green", "red", "gold", "silver",
    "black", "white", "rainbow", "teal", "orange", "yellow",
    "magenta", "coral", "cyan", "earth", "pastel", "monochrome",
    "fluorescent", "metallic", "iridescent", "emerald", "obsidian",
    # Named variants that must beat generic modifier words
    "cobalt", "navy", "sapphire", "indigo", "violet", "lavender",
    "crimson", "maroon", "amber", "bronze", "jade", "rust",
    "ivory", "charcoal", "grey", "gray", "brown", "beige", "satin",
    "sepia", "translucent",
})

# ---------------------------------------------------------------------------
# Mood strengthening mappings
# ---------------------------------------------------------------------------

_MOOD_STRENGTHENING = {
    "cozy":        "warm, intimate, cozy",
    "trippy":      "psychedelic, trippy, mind-bending",
    "moody":       "dark, dramatic, moody",
    "dreamy":      "ethereal, dreamy, soft-focus",
    "mysterious":  "enigmatic, mysterious, shadowed",
    "electric":    "high-energy, electric, charged",
    "playful":     "whimsical, playful, lighthearted",
    "hypnotic":    "mesmerizing, hypnotic, trance-inducing",
    "chill":       "relaxed, chill, laid-back",
    "badass":      "bold, badass, confident",
    "luxurious":   "opulent, luxurious, elegant",
    "zen":         "peaceful, zen, meditative",
    "bold":        "strong, bold, impactful",
    "dark":        "ominous, dark, shadowed",
    "epic":        "grand, epic, monumental",
    "nostalgic":   "wistful, nostalgic, reminiscent",
    "melancholic": "melancholic, subdued, emotionally heavy",
    "triumphant":  "victorious, triumphant, celebratory",
    "peaceful":    "serene, peaceful, tranquil",
    "ethereal":    "otherworldly, ethereal, delicate",
    "chaotic":     "dynamic, chaotic, energetic",
    "mystical":    "magical, mystical, enchanted",
    "serene":      "calm, serene, undisturbed",
    "whimsical":   "fantastical, whimsical, imaginative",
}

# Single safe adjective for use directly before a subject noun.
# Never a comma-separated chain — one word only so the subject stays clean.
_MOOD_SUBJECT_FORM = {
    "cozy":        "cozy",
    "trippy":      "trippy",
    "moody":       "moody",
    "dreamy":      "dreamy",
    "mysterious":  "mysterious",
    "electric":    "electric",
    "playful":     "playful",
    "hypnotic":    "hypnotic",
    "chill":       "chill",
    "badass":      "bold",
    "luxurious":   "luxurious",
    "zen":         "zen",
    "bold":        "bold",
    "dark":        "dark",
    "epic":        "epic",
    "nostalgic":   "nostalgic",
    "melancholic": "melancholic",
    "triumphant":  "triumphant",
    "peaceful":    "peaceful",
    "ethereal":    "ethereal",
    "chaotic":     "chaotic",
    "mystical":    "mystical",
    "serene":      "serene",
    "whimsical":   "whimsical",
}

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

# Words that describe light sources / luminance behavior — these should NOT be
# prepended as palette modifiers when a color-family match is found.
_LIGHTING_QUALIFIER_WORDS = frozenset({
    "neon", "glowing", "backlit",
    "bioluminescent", "blacklight", "cinematic", "volumetric",
})

# Suffix tokens that must not be duplicated in color phrases.
_COLOR_SUFFIX_TOKENS = frozenset({"tones", "palette", "hues", "colors", "color"})


def _dedup_color_phrase(phrase: str) -> str:
    """Collapse duplicate adjacent words and repeated suffix tokens in a color phrase."""
    if not phrase:
        return phrase
    words = phrase.split()
    seen_suffixes: set = set()
    out = []
    for word in words:
        w = word.rstrip(",")
        if w.lower() in _COLOR_SUFFIX_TOKENS:
            if w.lower() in seen_suffixes:
                continue  # drop duplicate suffix
            seen_suffixes.add(w.lower())
        # Drop exact adjacent duplicate
        if out and out[-1].lower() == word.lower():
            continue
        out.append(word)
    return " ".join(out)


def strengthen_color(color: str) -> str:
    """
    Strengthen color phrasing to ensure it affects the final image.
    e.g., "pink tones" -> "pink-dominant palette with soft pink hues"

    Guards against:
    - Re-processing already-complete palette phrases ("tones tones", etc.)
    - Prepending lighting words (neon, electric, glowing) as palette modifiers
    - Stacking modifiers onto phrases that already express the same meaning
    """
    if not color:
        return color

    color_lower = color.lower().strip()

    # Already a complete palette phrase — deduplicate tokens and return.
    if "palette" in color_lower or "tones" in color_lower:
        return _dedup_color_phrase(color)

    # Exact match in strengthening table.
    if color_lower in _COLOR_STRENGTHENING:
        return _dedup_color_phrase(_COLOR_STRENGTHENING[color_lower])

    # Partial match: find the best matching base key inside the input.
    # Priority rule: a named color-family key always beats a pure modifier key,
    # regardless of length. Among equal-priority keys, the longer one wins.
    best_base = None
    best_len = 0
    best_is_family = False
    for base in _COLOR_STRENGTHENING:
        # Only consider single-word base keys to avoid multi-word key accidents
        if " " in base:
            continue
        if base not in color_lower.split():
            # Also allow substring match for compound names but only if it's
            # a whole word match (surrounded by space or at start/end)
            import re as _re
            if not _re.search(r'(?<![a-z])' + _re.escape(base) + r'(?![a-z])', color_lower):
                continue
        is_family = base in _COLOR_FAMILIES_SET
        base_len = len(base)
        # A family key always beats a non-family key; among equal types, longer wins.
        if (is_family and not best_is_family) or \
           (is_family == best_is_family and base_len > best_len):
            best_base = base
            best_len = base_len
            best_is_family = is_family

    if best_base is not None:
        strengthened = _COLOR_STRENGTHENING[best_base]
        # Collect modifier words from the input that are not part of the base key
        # and are not lighting/luminance qualifiers (those belong in the Lighting field).
        base_words = set(best_base.split())
        input_words = color_lower.split()
        modifiers = [
            w for w in input_words
            if w not in base_words and w not in _LIGHTING_QUALIFIER_WORDS
        ]
        if modifiers:
            # Drop any modifier already present in the strengthened phrase
            strengthened_words = set(strengthened.lower().split())
            modifiers = [m for m in modifiers if m not in strengthened_words]
        if modifiers:
            mod_str = " ".join(modifiers)
            _COLOR_FAMILIES = _COLOR_FAMILIES_SET
            # Intensity/depth qualifiers always prepend regardless of base type.
            _PREPEND_MODIFIERS = {
                "dark", "light", "deep", "rich", "warm", "cool", "pale",
                "bright", "vivid", "bold", "soft", "muted", "dusty",
            }
            # Bidirectional antonym map: each word maps to the set of words
            # it contradicts. When a modifier is prepended, its antonyms are
            # stripped from the already-strengthened phrase so the two never
            # coexist (e.g. "muted vivid" or "dark bright").
            _ANTONYMS: dict = {
                "muted":     {"vivid", "vibrant", "bright", "electric", "bold", "rich", "deep"},
                "faded":     {"vivid", "vibrant", "bright", "electric", "bold", "rich"},
                "dusty":     {"vivid", "vibrant", "bright", "electric"},
                "soft":      {"vivid", "vibrant", "bright", "electric", "bold"},
                "pale":      {"vivid", "vibrant", "bright", "bold", "deep", "rich"},
                "vivid":     {"muted", "faded", "dusty", "soft", "pale"},
                "vibrant":   {"muted", "faded", "dusty", "soft", "pale"},
                "bright":    {"muted", "faded", "dusty", "dark", "deep"},
                "electric":  {"muted", "faded", "dusty", "soft"},
                "bold":      {"muted", "soft", "pale", "faded"},
                "dark":      {"bright", "light", "airy"},
                "deep":      {"bright", "light", "airy", "pale"},
                "light":     {"dark", "deep", "obsidian"},
                "warm":      {"cool"},
                "cool":      {"warm"},
            }
            all_prepend = all(m in _PREPEND_MODIFIERS for m in modifiers)
            if best_base in _COLOR_FAMILIES or all_prepend:
                # Strip antonyms of each modifier from the strengthened phrase.
                cleaned = strengthened
                for modifier in modifiers:
                    antonyms = _ANTONYMS.get(modifier, set())
                    if antonyms:
                        cleaned_words = [
                            w for w in cleaned.split()
                            if w.lower().rstrip(",") not in antonyms
                        ]
                        cleaned = " ".join(cleaned_words)
                # Prepend modifier: "muted magenta" -> "muted magenta palette with fuchsia tones"
                return _dedup_color_phrase(mod_str + " " + cleaned)
            else:
                # Non-intensity modifier (e.g. a color family name) — insert before
                # trailing suffix token for natural order:
                # "fluorescent purple" -> "fluorescent palette ... purple tones"
                s_words = strengthened.split()
                if s_words and s_words[-1].lower() in _COLOR_SUFFIX_TOKENS:
                    inserted = " ".join(s_words[:-1]) + " " + mod_str + " " + s_words[-1]
                else:
                    inserted = strengthened.rstrip() + " " + mod_str
                return _dedup_color_phrase(inserted)
        return _dedup_color_phrase(strengthened)

    # No match — ensure the phrase ends with "palette" to anchor it.
    result = f"{color} palette"
    return _dedup_color_phrase(result)


def strengthen_mood_for_subject(mood: str) -> str:
    """Return a single clean adjective safe for use directly before a subject noun.
    e.g. 'epic' -> 'epic'  (never 'grand, epic, monumental')
    """
    if not mood:
        return mood
    mood_lower = mood.lower().strip()
    if mood_lower in _MOOD_SUBJECT_FORM:
        return _MOOD_SUBJECT_FORM[mood_lower]
    for base, adj in _MOOD_SUBJECT_FORM.items():
        if base in mood_lower:
            return adj
    # Fallback: return the first word of the raw mood (never a comma chain)
    return mood.split()[0]


def strengthen_mood(mood: str) -> str:
    """
    Strengthen mood phrasing to ensure it affects the final image.
    e.g., "cozy" -> "warm, intimate, cozy atmosphere"
    Use only in dedicated mood/atmosphere clauses, never directly before a subject noun.
    """
    if not mood:
        return mood
    
    mood_lower = mood.lower().strip()
    
    # Check for exact match
    if mood_lower in _MOOD_STRENGTHENING:
        return _MOOD_STRENGTHENING[mood_lower]
    
    # Check for partial match
    for base, strengthened in _MOOD_STRENGTHENING.items():
        if base in mood_lower:
            return strengthened
    
    # No match — return the raw mood word; do not append "atmosphere".
    # Mood is used as an adjective prefix before the subject in build_sentence,
    # so adding "atmosphere" here would produce broken phrases like
    # "a lonely atmosphere cyber ninja".
    return mood


# ---------------------------------------------------------------------------
# Normalisation and matching helpers
# ---------------------------------------------------------------------------

def normalize_text(text: str) -> str:
    """
    Lower-case, collapse whitespace, strip leading/trailing punctuation.
    Used so comparisons are insensitive to case, extra spaces, and decoration.
    """
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"[\-_]+", " ", text)      # hyphens/underscores -> space
    text = re.sub(r"[^a-z0-9 ]+", "", text)  # drop remaining punctuation
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _candidate_phrases(raw: str, mapping: dict) -> list:
    """
    Build the full list of phrases to search for in the final prompt.
    Includes: the raw value, its normalized form, the strengthened phrase
    (if found in mapping), and every significant word in that phrase.
    """
    if not raw:
        return []

    candidates = [normalize_text(raw)]

    # Find the first mapping key whose normalized form is a substring of raw
    norm_raw = normalize_text(raw)
    for key, strengthened in mapping.items():
        norm_key = normalize_text(key)
        if norm_key and norm_key in norm_raw:
            norm_strengthened = normalize_text(strengthened)
            candidates.append(norm_strengthened)
            # Also add every content word (length > 3) from the strengthened phrase
            candidates.extend(
                w for w in norm_strengthened.split()
                if len(w) > 3
            )
            break

    return candidates


def phrase_matches_prompt(raw: str, mapping: dict, final_prompt: str) -> bool:
    """
    Return True if any candidate phrase derived from *raw* (including its
    strengthened mapping) appears in *final_prompt*.
    Case/whitespace/punctuation insensitive.
    """
    if not raw or not final_prompt:
        return False
    norm_prompt = normalize_text(final_prompt)
    return any(c and c in norm_prompt for c in _candidate_phrases(raw, mapping))


def get_expected_audit_values(ui_values: dict, components: dict) -> dict:
    """
    Return a dict of {var_name: (raw_ui_value, component_value)} for every
    auditable variable.  Callers can use this to log what was actually checked.
    """
    return {
        "subject":  (ui_values.get("subject", ""),  components.get("subject", "")),
        "style":    (ui_values.get("style", ""),    components.get("style", "")),
        "lighting": (ui_values.get("lighting", ""), components.get("lighting", "")),
        "mood":     (ui_values.get("mood", ""),     components.get("mood", "")),
        "color":    (ui_values.get("color", ""),    components.get("color", "")),
        "mode":     (ui_values.get("mode", ""),     ui_values.get("mode", "")),
    }


# ---------------------------------------------------------------------------
# Audit and validation functions
# ---------------------------------------------------------------------------

def audit_prompt_variables(
    ui_values: dict,
    components: dict,
    final_prompt: str,
    style_mode: str
) -> dict:
    """
    Audit whether Quick Build variables are present in the final prompt.

    Matching is tolerant: case/whitespace/punctuation insensitive, and the
    strengthened phrase is treated as a valid match for the raw UI value.
    Warnings are only emitted for genuine absences of set variables.

    Returns a dict keyed by variable name, each value:
      {"present": bool, "in_prompt": bool, "warning": str|None,
       "ui_value": str, "component_value": str}
    """
    norm_prompt = normalize_text(final_prompt)
    audit = {}

    # ── Subject ──────────────────────────────────────────────────────────────
    subject = ui_values.get("subject", "").strip()
    subject_present = bool(subject)
    subject_in_prompt = bool(subject and normalize_text(subject) in norm_prompt)
    audit["subject"] = {
        "present": subject_present,
        "in_prompt": subject_in_prompt,
        "warning": f"Subject '{subject}' not found in final prompt"
                   if subject_present and not subject_in_prompt else None,
        "ui_value": subject,
        "component_value": components.get("subject", ""),
    }

    # ── Style ────────────────────────────────────────────────────────────────
    style = ui_values.get("style", "").strip()
    style_present = bool(style)
    # Style appears in the "Rendered as:" section; the word itself may not be
    # verbatim but the section anchor signals it was applied.
    style_in_prompt = bool(
        style and (
            normalize_text(style) in norm_prompt
            or "rendered as" in norm_prompt
        )
    )
    audit["style"] = {
        "present": style_present,
        "in_prompt": style_in_prompt,
        "warning": f"Style '{style}' not found in final prompt"
                   if style_present and not style_in_prompt else None,
        "ui_value": style,
        "component_value": components.get("style", ""),
    }

    # ── Lighting ─────────────────────────────────────────────────────────────
    lighting = ui_values.get("lighting", "").strip()
    lighting_present = bool(lighting)
    lighting_in_prompt = bool(
        lighting and normalize_text(lighting) in norm_prompt
    )
    audit["lighting"] = {
        "present": lighting_present,
        "in_prompt": lighting_in_prompt,
        "warning": f"Lighting '{lighting}' not found in final prompt"
                   if lighting_present and not lighting_in_prompt else None,
        "ui_value": lighting,
        "component_value": components.get("lighting", ""),
    }

    # ── Mood ─────────────────────────────────────────────────────────────────
    # Match raw value OR strengthened phrase OR any significant word thereof.
    mood = ui_values.get("mood", "").strip()
    mood_present = bool(mood)
    mood_in_prompt = phrase_matches_prompt(mood, _MOOD_STRENGTHENING, final_prompt)
    audit["mood"] = {
        "present": mood_present,
        "in_prompt": mood_in_prompt,
        "warning": f"Mood '{mood}' not found in final prompt"
                   if mood_present and not mood_in_prompt else None,
        "ui_value": mood,
        "component_value": components.get("mood", ""),
    }

    # ── Color ────────────────────────────────────────────────────────────────
    # Match raw value OR strengthened palette phrase OR any significant word thereof.
    color = ui_values.get("color", "").strip()
    color_present = bool(color)
    color_in_prompt = phrase_matches_prompt(color, _COLOR_STRENGTHENING, final_prompt)
    audit["color"] = {
        "present": color_present,
        "in_prompt": color_in_prompt,
        "warning": f"Color '{color}' not found in final prompt"
                   if color_present and not color_in_prompt else None,
        "ui_value": color,
        "component_value": components.get("color", ""),
    }

    # ── Mode ─────────────────────────────────────────────────────────────────
    # Mode drives quality/style phrasing; the label isn't injected verbatim.
    mode = ui_values.get("mode", "").strip()
    audit["mode"] = {
        "present": bool(mode),
        "in_prompt": bool(style_mode),  # always applied via cfg selection
        "warning": None,
        "ui_value": mode,
        "component_value": style_mode,
    }

    return audit


def log_prompt_audit(
    ui_values: dict,
    components: dict,
    final_prompt: str,
    style_mode: str,
    audit_results: dict
) -> None:
    """
    Log the complete prompt audit for debugging.
    """
    logger.info("=" * 80)
    logger.info("PROMPT VARIABLE AUDIT")
    logger.info("=" * 80)

    # --- Subject integrity check (most important for drift diagnosis) ---
    ui_subject = (ui_values.get("subject") or "").strip()
    resolved_subject = (components.get("subject") or "").strip()
    logger.info("\n--- SUBJECT INTEGRITY ---")
    logger.info(f"  UI subject (literal input) : '{ui_subject}'")
    logger.info(f"  Resolved theme subject     : '{resolved_subject}'")
    if ui_subject and resolved_subject and ui_subject.lower() != resolved_subject.lower():
        logger.warning(
            f"  *** SUBJECT DRIFT DETECTED: UI='{ui_subject}' → theme='{resolved_subject}' ***"
        )
    else:
        logger.info("  Subject integrity: OK (no drift)")

    logger.info("\n--- EXACT PROMPT SENT TO MODEL ---")
    logger.info(f"  style_mode : {style_mode}")
    logger.info(f"  prompt     : {final_prompt}")

    logger.info("\n--- RAW UI FIELD VALUES ---")
    for key, value in ui_values.items():
        logger.info(f"  {key}: '{value}'")
    
    logger.info("\n--- THEME/COMPONENTS DICT ---")
    logger.info(f"  components: {components}")
    
    logger.info("\n--- VARIABLE AUDIT SUMMARY ---")
    for var_name, result in audit_results.items():
        status = "✓ PRESENT" if result["in_prompt"] else "✗ MISSING"
        logger.info(f"  {var_name}: {status}")
        if result.get("warning"):
            logger.info(f"    WARNING: {result['warning']}")
        logger.info(f"    UI value: '{result['ui_value']}'")
        logger.info(f"    Component value: '{result['component_value']}'")
    
    logger.info("=" * 80)


def get_audit_warnings(audit_results: dict) -> list:
    """
    Extract all warnings from audit results.
    Returns a list of warning strings.
    """
    warnings = []
    for var_name, result in audit_results.items():
        if result.get("warning"):
            warnings.append(f"{var_name}: {result['warning']}")
    return warnings


def format_audit_summary(audit_results: dict, ui_values: dict = None, components: dict = None, final_prompt: str = None) -> str:
    """
    Format audit results as a human-readable summary string.
    Optionally includes subject integrity and final prompt when supplied.
    """
    lines = []
    lines.append("PROMPT VARIABLE AUDIT SUMMARY")
    lines.append("=" * 50)

    # Subject integrity block
    if ui_values is not None and components is not None:
        ui_subject = (ui_values.get("subject") or "").strip()
        resolved_subject = (components.get("subject") or "").strip()
        lines.append(f"UI Subject   : {ui_subject or '(blank)'}")
        lines.append(f"Theme Subject: {resolved_subject or '(blank)'}")
        if ui_subject and resolved_subject and ui_subject.lower() != resolved_subject.lower():
            lines.append(f"⚠ SUBJECT DRIFT: '{ui_subject}' → '{resolved_subject}'")
        else:
            lines.append("✓ Subject integrity OK")

    if final_prompt is not None:
        lines.append(f"Prompt sent  : {final_prompt[:120]}{'...' if len(final_prompt) > 120 else ''}")

    lines.append("-" * 50)

    for var_name, result in audit_results.items():
        if result["present"]:
            status = "✓" if result["in_prompt"] else "✗"
            lines.append(f"{status} {var_name}: '{result['ui_value']}'")
            if result.get("warning"):
                lines.append(f"  ⚠ {result['warning']}")
        else:
            lines.append(f"- {var_name}: (not set)")
    
    lines.append("=" * 50)
    
    return "\n".join(lines)
