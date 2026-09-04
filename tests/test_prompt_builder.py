"""Tests for the prompt engine in prompt_builder.py.

Covers (improvement report §5 — testing expansion):
  - text helpers: clean_text normalisation
  - subject anchor: mood+subject lock, generic fallback for empty subject
  - composition anchor: custom override, scenic vs. framing variants
  - mode config integrity: all modes carry the four required strings
  - build_prompt: fixed section order, per-mode negatives, mode remap
    (product-photo + creature -> realistic), creature/humanoid anatomy
    blocks, field priorities (components beat theme defaults), tech
    prop-drift guard, subject negatives, passthrough metadata
  - build_all_prompts list mapping

These are pure logic tests — no files are read or written, no Tk, no
network. build_prompt uses random.choice internally for variety, so every
assertion here checks substrings that are present in ALL variants, which
keeps the tests deterministic without seeding.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import prompt_builder as pb


def make_theme(**overrides):
    """A representative theme dict; tests override individual fields."""
    theme = {
        "theme_id": 7,
        "sentence": "misty pine forest at dawn",
        "palette": "cool blues",
        "mood": "calm",
        "environment": "serene woodland",
        "subject_negatives": "",
        "components": {},
    }
    theme.update(overrides)
    return theme


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

class TestCleanText(unittest.TestCase):
    def test_normalises_whitespace_and_strips(self):
        self.assertEqual(pb.clean_text("  a\n  b\t c  "), "a b c")

    def test_none_becomes_empty_string(self):
        self.assertEqual(pb.clean_text(None), "")

    def test_plain_text_unchanged(self):
        self.assertEqual(pb.clean_text("crisp morning light"), "crisp morning light")


# ---------------------------------------------------------------------------
# Subject / composition anchors
# ---------------------------------------------------------------------------

class TestSubjectAnchor(unittest.TestCase):
    def test_mood_modifies_subject(self):
        out = pb._subject_anchor("cat", "ominous")
        self.assertIn("Single main subject:", out)
        self.assertIn("Ominous cat", out)

    def test_multiline_mood_uses_first_word(self):
        out = pb._subject_anchor("cat", "darkly ominous")
        self.assertIn("Darkly cat", out)
        self.assertNotIn("ominous cat", out)

    def test_no_mood_uses_plain_subject(self):
        out = pb._subject_anchor("cat", "")
        self.assertIn("Single main subject: cat", out)

    def test_empty_subject_falls_back_to_generic_anchor(self):
        out = pb._subject_anchor("", "ominous")
        self.assertTrue(out.startswith("Single clear subject"))
        self.assertNotIn("Single main subject", out)


class TestCompositionAnchor(unittest.TestCase):
    def test_custom_composition_returned_verbatim(self):
        out = pb._composition_anchor("cat", False, "centered mandala framing")
        self.assertEqual(out, "centered mandala framing")

    def test_scenic_mode_uses_cinematic_wide(self):
        out = pb._composition_anchor("castle", True, "")
        self.assertTrue(out.startswith("Wide cinematic 16:9"))
        self.assertIn("castle", out)

    def test_living_subject_uses_wallpaper_framing(self):
        out = pb._composition_anchor("frog", False, "")
        self.assertTrue(out.startswith("16:9 desktop wallpaper framing; frog"))

    def test_empty_subject_uses_generic_label(self):
        out = pb._composition_anchor("", False, "")
        self.assertIn("the subject", out)


# ---------------------------------------------------------------------------
# Mode config integrity
# ---------------------------------------------------------------------------

class TestModeConfig(unittest.TestCase):
    REQUIRED_KEYS = ("style_base", "quality_lead", "quality_close", "negative")

    def test_all_modes_have_complete_nonempty_config(self):
        self.assertGreaterEqual(len(pb._MODE_CONFIG), 8)
        for mode, cfg in pb._MODE_CONFIG.items():
            for key in self.REQUIRED_KEYS:
                self.assertIn(key, cfg, f"{mode} missing {key}")
                self.assertIsInstance(cfg[key], str)
                self.assertTrue(cfg[key].strip(), f"{mode}.{key} is empty")

    def test_expected_modes_present(self):
        for mode in ("stylized", "realistic", "product-photo", "surreal",
                     "anime", "dark-fantasy", "painterly", "pixel-art",
                     "cinematic", "minimalist"):
            self.assertIn(mode, pb._MODE_CONFIG)


# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------

class TestBuildPromptCore(unittest.TestCase):
    def test_result_carries_expected_keys(self):
        result = pb.build_prompt(make_theme())
        for key in ("prompt", "negative_prompt", "style_mode", "subject",
                    "art_style", "theme_id", "theme_sentence"):
            self.assertIn(key, result)
        self.assertNotIn("audit_results", result)

    def test_prompt_ends_with_period(self):
        result = pb.build_prompt(make_theme())
        self.assertTrue(result["prompt"].endswith("."))

    def test_fixed_section_order(self):
        """subject anchor -> scene -> palette -> style -> quality."""
        result = pb.build_prompt(make_theme(subject="frog"))
        p = result["prompt"]
        self.assertIn("Single main subject: Calm frog", p)  # mood locks onto subject
        idx_subject = p.index("Single main subject")
        idx_scene = p.index("misty pine forest at dawn")
        idx_palette = p.index("cool blues")
        idx_style = p.index("Rendered as:")
        idx_quality = p.index("Ultra-high detail, 8K resolution")
        self.assertLess(idx_subject, idx_scene)
        self.assertLess(idx_scene, idx_palette)
        self.assertLess(idx_palette, idx_style)
        self.assertLess(idx_style, idx_quality)

    def test_metadata_passthrough(self):
        result = pb.build_prompt(make_theme())
        self.assertEqual(result["theme_id"], 7)
        self.assertEqual(result["theme_sentence"], "misty pine forest at dawn")
        self.assertEqual(result["style_mode"], "stylized")

    def test_empty_theme_still_builds(self):
        result = pb.build_prompt({})
        self.assertEqual(result["subject"], "")
        self.assertEqual(result["theme_id"], 1)
        self.assertTrue(result["prompt"].startswith("Single clear subject"))
        self.assertTrue(result["negative_prompt"].strip())


class TestBuildPromptModes(unittest.TestCase):
    def test_per_mode_negative_is_baked_in(self):
        anime = pb.build_prompt(make_theme(), style_mode="anime")
        self.assertIn("photorealistic", anime["negative_prompt"])
        stylized = pb.build_prompt(make_theme(), style_mode="stylized")
        self.assertIn("glass objects", stylized["negative_prompt"])

    def test_unknown_mode_falls_back_to_stylized_config(self):
        result = pb.build_prompt(make_theme(), style_mode="bogus-mode")
        self.assertTrue(result["negative_prompt"].startswith("glass objects"))

    def test_product_photo_remapped_for_creature(self):
        result = pb.build_prompt(make_theme(subject="dragon"),
                                 style_mode="product-photo")
        self.assertEqual(result["style_mode"], "realistic")

    def test_product_photo_kept_for_object(self):
        result = pb.build_prompt(make_theme(subject="vintage camera"),
                                 style_mode="product-photo")
        self.assertEqual(result["style_mode"], "product-photo")


class TestBuildPromptAnatomy(unittest.TestCase):
    def test_creature_gets_anatomy_lock_and_extra_negatives(self):
        result = pb.build_prompt(make_theme(subject="frog"))
        self.assertIn("Anatomy lock", result["prompt"])
        self.assertIn("four limbs", result["prompt"])
        self.assertIn("tail on frog", result["negative_prompt"])

    def test_humanoid_gets_stylized_anatomy_block(self):
        result = pb.build_prompt(make_theme(subject="wizard"))
        self.assertIn("Anatomy lock: two hands only", result["prompt"])

    def test_humanoid_realistic_gets_strict_anatomy_block(self):
        result = pb.build_prompt(make_theme(subject="person"),
                                 style_mode="realistic")
        self.assertIn("Strict anatomy: exactly two hands", result["prompt"])


class TestBuildPromptPriorities(unittest.TestCase):
    def test_user_color_beats_theme_palette(self):
        theme = make_theme(components={"color": "neon pink"})
        result = pb.build_prompt(theme)
        self.assertIn("neon pink", result["prompt"])
        self.assertNotIn("cool blues", result["prompt"])

    def test_user_atmosphere_beats_theme_environment(self):
        theme = make_theme(components={"atmosphere": "electric haze"})
        result = pb.build_prompt(theme)
        self.assertIn("electric haze", result["prompt"])
        self.assertNotIn("serene woodland", result["prompt"])

    def test_art_style_prefixes_mode_base(self):
        theme = make_theme(components={"style": "cyberpunk"})
        result = pb.build_prompt(theme)
        self.assertIn("Rendered as: cyberpunk, stylized digital illustration",
                      result["prompt"])

    def test_tech_with_glass_is_dropped(self):
        theme = make_theme(components={"tech": "glass orbs"})
        result = pb.build_prompt(theme)
        self.assertNotIn("glass orbs", result["prompt"])

    def test_tech_without_glass_joined_as_elements(self):
        theme = make_theme(components={"tech": "holographic"})
        result = pb.build_prompt(theme)
        self.assertIn("holographic elements", result["prompt"])

    def test_focal_subject_ignores_tech_entirely(self):
        theme = make_theme(subject="wizard", components={"tech": "steampunk gears"})
        result = pb.build_prompt(theme)
        self.assertNotIn("steampunk gears", result["prompt"])

    def test_scenic_mode_switches_composition(self):
        theme = make_theme(components={"scenic_mode": True})
        result = pb.build_prompt(theme)
        self.assertIn("Wide cinematic 16:9", result["prompt"])

    def test_custom_composition_used_verbatim(self):
        theme = make_theme(components={"composition": "centered mandala framing"})
        result = pb.build_prompt(theme)
        self.assertIn("centered mandala framing", result["prompt"])
        self.assertNotIn("16:9 desktop wallpaper framing", result["prompt"])

    def test_subject_negatives_appended(self):
        result = pb.build_prompt(make_theme(subject_negatives="no vehicles"))
        self.assertIn("no vehicles", result["negative_prompt"])


class TestBuildAllPrompts(unittest.TestCase):
    def test_maps_over_theme_list(self):
        themes = [make_theme(subject="frog"), make_theme(subject="castle")]
        results = pb.build_all_prompts(themes)
        self.assertEqual(len(results), 2)
        self.assertEqual([r["subject"] for r in results], ["frog", "castle"])

    def test_empty_list_gives_empty_list(self):
        self.assertEqual(pb.build_all_prompts([]), [])


# ---------------------------------------------------------------------------
# Creature anatomy lookup
# ---------------------------------------------------------------------------

class TestCreatureAnatomyLookup(unittest.TestCase):
    def test_known_creature_returns_pair(self):
        pos, neg = pb.get_creature_anatomy("baby dragon")
        self.assertTrue(pos and neg)
        self.assertIn("exactly two large wings", pos)
        self.assertIn("one wing", neg)

    def test_unknown_subject_returns_none_pair(self):
        pos, neg = pb.get_creature_anatomy("vintage camera")
        self.assertIsNone(pos)
        self.assertIsNone(neg)


# ---------------------------------------------------------------------------
# Audit integration guard
# ---------------------------------------------------------------------------

class TestAuditGuard(unittest.TestCase):
    def test_run_audit_without_ui_values_skips_audit(self):
        """run_audit=True alone must not add audit_results (needs ui_values)."""
        result = pb.build_prompt(make_theme(), run_audit=True)
        self.assertNotIn("audit_results", result)


if __name__ == "__main__":
    unittest.main()
