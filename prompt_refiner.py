"""
prompt_refiner.py
-----------------
Advanced prompt refinement and editing capabilities.
"""

import re
from typing import Dict, List


class PromptRefiner:
    """Handles prompt parsing, editing, and refinement."""
    
    @staticmethod
    def parse_prompt(prompt: str) -> Dict[str, str]:
        """
        Parse a structured builder prompt back into labelled sections.

        Strategy — section-aware clause parser:
          Builder prompts are assembled by build_prompt() as period-separated clauses
          in a fixed order.  Several sections have unambiguous prefix anchors:

            S1  "Single main subject: ..."  or  "Single clear subject, ..."
            S6  "16:9 desktop wallpaper framing; ..."  or  "Wide cinematic 16:9, ..."
            S7  "Rendered as: ..."
            S8  starts with a quality_lead phrase and ends with "8K resolution"
            S9  "No text, no watermark, ..."

          The free-text sections (S2 scene, S3 lighting, S4 mood, S5 palette) sit in
          the gap between S1 and S6.  They are assigned in order: the first free clause
          goes to scene, the second to lighting, the third to mood, the fourth to
          palette.  This matches the fixed build_prompt() section order exactly.

          Freeform / legacy prompts that don't match any anchor fall through entirely
          into sections["main"] so nothing is lost.
        """
        sections = {
            "subject":     "",
            "scene":       "",
            "lighting":    "",
            "mood":        "",
            "palette":     "",
            "composition": "",
            "style":       "",
            "quality":     "",
            "negative":    "",
            "main":        "",   # fallback for freeform prompts
            "raw":         prompt,
        }

        if not prompt or not prompt.strip():
            return sections

        # ------------------------------------------------------------------
        # Anchor patterns — compiled once, matched against individual clauses
        # ------------------------------------------------------------------
        _RE_SUBJECT     = re.compile(r'^Single (?:main |clear )?subject', re.IGNORECASE)
        _RE_SUBJECT_ALT = re.compile(r'^Single clear subject', re.IGNORECASE)
        _RE_COMPOSITION = re.compile(r'^(?:16:9 desktop wallpaper framing|Wide cinematic 16:9)', re.IGNORECASE)
        _RE_STYLE       = re.compile(r'^Rendered as:', re.IGNORECASE)
        _RE_QUALITY     = re.compile(r'8K resolution', re.IGNORECASE)
        _RE_EXCLUSIONS  = re.compile(r'^No text,\s*no watermark', re.IGNORECASE)
        # Subject continuation clauses (part of S1 that build_prompt spreads across sentences)
        _RE_SUBJ_CONT   = re.compile(
            r'^(?:\w[\w\s]+ is (?:fully visible|the dominant focal point)|Nothing obscures)',
            re.IGNORECASE
        )

        # ------------------------------------------------------------------
        # Split the full prompt into period-separated clauses, preserving text
        # ------------------------------------------------------------------
        raw_clauses = [c.strip() for c in prompt.split(". ") if c.strip()]

        # Remove trailing period from the last clause if present
        if raw_clauses and raw_clauses[-1].endswith("."):
            raw_clauses[-1] = raw_clauses[-1][:-1].strip()

        is_structured = any(
            _RE_SUBJECT.match(c) or _RE_STYLE.match(c) or _RE_EXCLUSIONS.match(c)
            for c in raw_clauses
        )

        if not is_structured:
            # Freeform / legacy prompt — put everything in main unchanged
            sections["main"] = prompt.strip()
            return sections

        # ------------------------------------------------------------------
        # Walk clauses and assign to sections by anchor matching
        # ------------------------------------------------------------------
        # Tracks which zone we are in between the fixed anchors
        # Zones: "pre_subject" → "subject" → "free" → "post_composition"
        zone = "pre_subject"
        free_clauses: List[str] = []   # S2–S5 collected here for ordered assignment

        subject_parts: List[str] = []

        for clause in raw_clauses:
            # --- Hard anchors (take priority regardless of zone) ---

            if _RE_STYLE.match(clause):
                value = re.sub(r'^Rendered as:\s*', '', clause, flags=re.IGNORECASE).strip()
                sections["style"] = value
                zone = "post_style"
                continue

            if _RE_EXCLUSIONS.match(clause):
                sections["quality"] = (sections["quality"] + ". " + clause).strip(". ")
                zone = "exclusions"
                continue

            if _RE_QUALITY.search(clause):
                sections["quality"] = (sections["quality"] + ". " + clause).strip(". ")
                zone = "quality"
                continue

            if _RE_COMPOSITION.match(clause):
                sections["composition"] = clause
                zone = "post_composition"
                continue

            # --- Subject block (S1 spans multiple sentences in build_prompt) ---
            if _RE_SUBJECT.match(clause) or _RE_SUBJECT_ALT.match(clause):
                subject_parts.append(clause)
                zone = "subject"
                continue

            if zone == "subject":
                if _RE_SUBJ_CONT.match(clause):
                    subject_parts.append(clause)
                    continue
                else:
                    # First clause that doesn't continue the subject → switch to free zone
                    zone = "free"
                    # Fall through to free zone handling below

            # --- Free zone: S2 scene, S3 lighting, S4 mood, S5 palette (in order) ---
            if zone in ("free", "pre_subject"):
                free_clauses.append(clause)
                continue

            # Anything after style/quality/exclusions that doesn't match → quality overflow
            if zone in ("post_style", "quality", "exclusions", "post_composition"):
                sections["quality"] = (sections["quality"] + ". " + clause).strip(". ")

        # ------------------------------------------------------------------
        # Reconstruct subject from its (possibly multi-sentence) parts
        # ------------------------------------------------------------------
        if subject_parts:
            # Extract the named subject from the opening anchor sentence only
            m = re.match(
                r'Single (?:main |clear )?subject[:\s]+([^.]+)',
                subject_parts[0], re.IGNORECASE
            )
            sections["subject"] = m.group(1).strip() if m else subject_parts[0].strip()

        # ------------------------------------------------------------------
        # Classify and assign free clauses (S2–S5)
        #
        # Strategy: try content-based classification first so that missing
        # middle sections don't cause positional misalignment.
        # Each clause is tested against keyword sets for lighting, mood, and
        # palette. Clauses that don't match any of those are treated as scene.
        # Within each category the first match wins; subsequent matches for the
        # same category are appended to scene as overflow (safe — no data lost).
        # ------------------------------------------------------------------
        _LIGHTING_KW = {
            "neon", "golden hour", "moonlight", "cinematic", "dramatic",
            "soft light", "volumetric", "backlit", "candlelight", "natural light",
            "studio lighting", "rim light", "ambient", "diffused", "hdr",
            "sunset light", "overcast", "directional", "silhouette", "glow",
            "bioluminescent", "aurora", "firelight", "rays", "shadow",
        }
        _MOOD_KW = {
            "epic", "chill", "mysterious", "cozy", "nostalgic", "dark",
            "dreamlike", "melancholic", "eerie", "majestic", "serene",
            "tense", "euphoric", "lonely", "whimsical", "atmosphere",
            "ominous", "peaceful", "ethereal", "surreal", "haunting",
        }
        _PALETTE_KW = {
            "colour", "color", "palette", "hue", "tones", "teal", "emerald",
            "crimson", "violet", "amber", "cyan", "magenta", "gold", "silver",
            "warm", "cool", "muted", "vivid", "pastel", "neon", "monochrome",
            "highlights", "gradient", "earthy", "jewel",
        }

        def _clause_type(clause: str) -> str:
            lower = clause.lower()
            words = set(re.split(r'[\s,]+', lower))
            # Palette: check word-level tokens (colours are single words)
            if words & _PALETTE_KW:
                return "palette"
            # Lighting: phrase-level check (multi-word terms like "golden hour")
            if any(kw in lower for kw in _LIGHTING_KW):
                return "lighting"
            # Mood: phrase-level check
            if any(kw in lower for kw in _MOOD_KW):
                return "mood"
            return "scene"

        for clause in free_clauses:
            kind = _clause_type(clause)
            if kind == "scene" or not sections["scene"]:
                if not sections["scene"]:
                    sections["scene"] = clause
                elif kind == "scene":
                    sections["scene"] += ", " + clause
                else:
                    # Classified as lighting/mood/palette but scene is empty —
                    # still fill scene first (first free clause is always scene)
                    sections["scene"] = clause
            elif kind == "lighting" and not sections["lighting"]:
                sections["lighting"] = clause
            elif kind == "mood" and not sections["mood"]:
                sections["mood"] = clause
            elif kind == "palette" and not sections["palette"]:
                sections["palette"] = clause
            else:
                # Already filled or unclassifiable — append to scene as overflow
                sections["scene"] += ", " + clause

        return sections
    
    @staticmethod
    def reassemble_prompt(sections: Dict[str, str]) -> str:
        """Reassemble a prompt from parsed sections in canonical builder order."""
        # Fixed order mirrors build_prompt section sequence
        ordered_keys = [
            "subject", "scene", "lighting", "mood",
            "palette", "composition", "style", "quality", "main",
        ]
        parts = [sections[k] for k in ordered_keys if sections.get(k)]
        prompt = ". ".join(p.strip().rstrip(".") for p in parts if p.strip())
        if prompt and not prompt.endswith("."):
            prompt += "."
        if sections.get("negative"):
            prompt += f" Negative: {sections['negative']}."
        return prompt
    
    @staticmethod
    def get_enhancement_suggestions(prompt: str) -> List[Dict[str, str]]:
        """Get suggestions for prompt enhancement."""
        suggestions = []
        
        # Check for missing elements
        sections = PromptRefiner.parse_prompt(prompt)
        
        if not sections.get("style"):
            suggestions.append({
                "type": "missing_style",
                "title": "Add Style",
                "description": "Prompt lacks a visual style",
                "suggestions": ["oil painting", "3D render", "cyberpunk art", "watercolor", "digital art"]
            })
        
        if not sections.get("lighting"):
            suggestions.append({
                "type": "missing_lighting",
                "title": "Add Lighting",
                "description": "Consider adding lighting details",
                "suggestions": ["neon glow", "golden hour", "dramatic shadows", "soft diffused light", "cinematic lighting"]
            })
        
        if not sections.get("mood"):
            suggestions.append({
                "type": "missing_mood",
                "title": "Add Mood",
                "description": "Prompt could benefit from mood/atmosphere",
                "suggestions": ["epic", "mysterious", "dreamy", "ethereal", "majestic"]
            })
        
        # Check for generic terms
        generic_terms = {
            "thing": "object, element, form",
            "stuff": "details, elements, textures",
            "nice": "beautiful, stunning, breathtaking",
            "good": "excellent, outstanding, masterful",
            "bad": "flawed, distorted, malformed"
        }
        
        for generic, replacement in generic_terms.items():
            if f" {generic} " in f" {prompt.lower()} ":
                suggestions.append({
                    "type": "generic_term",
                    "title": f"Replace '{generic}'",
                    "description": f"'{generic}' is too generic",
                    "suggestions": replacement.split(", ")
                })
        
        # Check prompt length
        word_count = len(prompt.split())
        if word_count < 10:
            suggestions.append({
                "type": "short_prompt",
                "title": "Expand Prompt",
                "description": "Prompt is quite short - consider adding more details",
                "suggestions": ["adjectives", "descriptive phrases", "environmental details"]
            })
        elif word_count > 100:
            suggestions.append({
                "type": "long_prompt",
                "title": "Simplify Prompt",
                "description": "Prompt is quite long - try to focus on key elements",
                "suggestions": ["Keep main subject", "Remove redundancy", "Combine similar ideas"]
            })
        
        # Check for prop-heavy/generic prompts
        prop_terms = ["glass", "bottle", "bottles", "stemware", "table", "prop", "props", "object", "objects", "item", "items"]
        generic_scene_terms = ["scene", "setting", "environment", "background", "studio", "product"]
        
        lower = prompt.lower()
        prop_count = sum(1 for term in prop_terms if term in lower)
        generic_count = sum(1 for term in generic_scene_terms if term in lower)
        
        # Flag prop-heavy prompts
        if prop_count >= 2:
            suggestions.append({
                "type": "prop_heavy",
                "title": "Too Generic - Prop Heavy",
                "description": "Prompt contains too many generic object/prop terms that may cause drift",
                "suggestions": [
                    "Replace 'glass/bottle' with theme-specific elements",
                    "Focus on character or environment instead of props", 
                    "Add stronger theme anchoring (e.g., 'witch in mystical forest' instead of 'witch with bottles')"
                ]
            })
        
        # Flag generic scene prompts
        if generic_count >= 2 and not any(theme in lower for theme in ["witch", "wizard", "martian", "underwater", "forest", "colony"]):
            suggestions.append({
                "type": "generic_scene",
                "title": "Needs Stronger Scene Anchor",
                "description": "Prompt uses generic scene terms - add specific theme elements",
                "suggestions": [
                    "Replace 'scene/setting' with specific location (forest, Mars, underwater)",
                    "Add environment details (mist, regolith, bubbles, roots)",
                    "Focus on theme-specific atmosphere and composition"
                ]
            })
        
        # Suggest anatomy lock for humanoid prompts missing hand constraints
        humanoid_tokens = ["person", "human", "man", "woman", "girl", "boy", "character", "witch", "wizard", "humanoid", "portrait"]
        has_humanoid = any(tok in lower for tok in humanoid_tokens)
        mentions_hands = any(k in lower for k in ["hand", "hands", "finger", "fingers", "two hands", "exactly two"])
        if has_humanoid and not mentions_hands:
            suggestions.append({
                "type": "add_hand_anatomy_lock",
                "title": "Add Hand Anatomy Lock",
                "description": "Prompt appears humanoid — consider adding a short anatomy lock to avoid extra or malformed hands/fingers.",
                "suggestions": [
                    "Add: 'Anatomy lock: two hands only, five fingers per hand, no extra hands or fused fingers.'",
                ]
            })
        
        return suggestions
    
    @staticmethod
    def apply_quick_edit(prompt: str, edit_type: str, value: str = "") -> str:
        """Apply a quick edit to a prompt."""
        sections = PromptRefiner.parse_prompt(prompt)
        
        if edit_type == "add_detail":
            sections["main"] += f", {value}" if sections["main"] else value
        elif edit_type == "set_style":
            sections["style"] = value
        elif edit_type == "set_lighting":
            sections["lighting"] = value
        elif edit_type == "set_mood":
            sections["mood"] = value
        elif edit_type == "add_quality":
            sections["quality"] = value
        elif edit_type == "remove_style":
            sections["style"] = ""
        elif edit_type == "remove_lighting":
            sections["lighting"] = ""
        elif edit_type == "remove_mood":
            sections["mood"] = ""
        elif edit_type == "clear_all":
            sections = {k: "" for k in sections}
            sections["raw"] = prompt
        
        return PromptRefiner.reassemble_prompt(sections)
    
    @staticmethod
    def extract_keywords(prompt: str) -> List[str]:
        """Extract main keywords from prompt."""
        # Remove negative prompt
        prompt = re.sub(r'Negative prompt:.*', '', prompt, flags=re.IGNORECASE)
        
        # Split on common delimiters and clean
        words = re.split(r'[,\s]+', prompt.lower())
        
        # Filter meaningful words (length > 3, not common)
        common_words = {'and', 'the', 'with', 'in', 'of', 'on', 'at', 'to', 'a', 'an', 'by', 'is', 'are'}
        keywords = [w.strip() for w in words if len(w.strip()) > 2 and w.strip() not in common_words]
        
        # Remove duplicates while preserving order
        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw not in seen:
                unique_keywords.append(kw)
                seen.add(kw)
        
        return unique_keywords[:15]  # Return top 15
    
    @staticmethod
    def get_prompt_stats(prompt: str, negative_prompt: str = "") -> Dict[str, any]:
        """Get statistics about a prompt (and optional separate negative prompt)."""
        sections  = PromptRefiner.parse_prompt(prompt)
        keywords  = PromptRefiner.extract_keywords(prompt)
        word_count = len(prompt.split())

        # Support both inline negative (legacy) and separate negative_prompt field
        has_negative = bool(negative_prompt.strip() or sections.get("negative"))

        return {
            "word_count":        word_count,
            "keyword_count":     len(keywords),
            "has_subject":       bool(sections.get("subject")),
            "has_style":         bool(sections.get("style")),
            "has_lighting":      bool(sections.get("lighting")),
            "has_mood":          bool(sections.get("mood")),
            "has_negative":      has_negative,
            "completeness_score": calculate_completeness(sections, keywords),
        }


def calculate_completeness(sections: Dict[str, str], keywords: List[str]) -> int:
    """
    Calculate prompt completeness score (0–100).
    Mirrors the fixed section order used by build_prompt.
    """
    score = 0

    # Subject lock present (named subject or freeform main)
    if sections.get("subject") or sections.get("main"):
        score += 25

    # Style descriptor
    if sections.get("style"):
        score += 15

    # Lighting
    if sections.get("lighting"):
        score += 15

    # Mood
    if sections.get("mood"):
        score += 10

    # Negative prompt (baked-in or custom)
    if sections.get("negative"):
        score += 15

    # Keyword variety (max 20 pts)
    score += min(len(keywords) * 2, 20)

    return min(score, 100)
