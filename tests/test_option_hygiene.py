"""The option lists are product data; these tests stop them rotting again.

Covers the defects listed in FrogPaper-dropdown-improvement-plan.md section 3
and the guarantees the colour prune has to keep: what is offered stays clean,
and what was retired stays parseable.
"""

import pathlib
import random
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import app_prompt_data as data


class TestListHygiene(unittest.TestCase):
    def setUp(self):
        self.table = data.THEME_VARIABLE_OPTIONS

    def test_one_blank_entry_per_list(self):
        for name, options in self.table.items():
            with self.subTest(field=name):
                self.assertEqual(options.count(""), 1, f"{name} must have exactly one blank entry")
                self.assertEqual(options[0], "", f"{name} blank entry must come first")

    def test_no_duplicates_case_insensitive(self):
        for name, options in self.table.items():
            with self.subTest(field=name):
                lowered = [o.lower() for o in options]
                self.assertEqual(len(lowered), len(set(lowered)), f"duplicate in {name}")

    def test_no_cross_list_overlap(self):
        names = list(self.table)
        for i, first in enumerate(names):
            for second in names[i + 1:]:
                with self.subTest(first=first, second=second):
                    shared = {o.lower() for o in self.table[first]} & {o.lower() for o in self.table[second]}
                    shared.discard("")
                    self.assertEqual(shared, set())

    def test_entries_are_trimmed_and_lowercase_leading(self):
        for name, options in self.table.items():
            for option in options:
                with self.subTest(field=name, option=option):
                    self.assertEqual(option, option.strip())
                    self.assertNotIn("  ", option)
                    self.assertFalse(option[:1].isupper(), "leading capital breaks the house style")

    def test_shipped_typo_never_returns(self):
        for name, options in self.table.items():
            with self.subTest(field=name):
                self.assertNotIn("unset haze", [o.lower() for o in options])

    def test_genre_words_stay_out_of_mood(self):
        genres = {
            "cyberpunk edge", "cottagecore", "dark academia", "solarpunk optimism",
            "vaporwave nostalgia", "lo-fi calm", "gothic elegance",
        }
        self.assertEqual(genres & {o.lower() for o in data.MOOD_OPTIONS}, set())

    def test_mood_stays_visibly_renderable(self):
        weak = {"numb", "resigned", "raw", "vulnerable", "contemplative"}
        self.assertEqual(weak & {o.lower() for o in data.MOOD_OPTIONS}, set())

    def test_near_duplicate_pair_is_gone(self):
        moods = {o.lower() for o in data.MOOD_OPTIONS}
        self.assertFalse({"dark", "sinister"} <= moods, "dark/sinister split the same mood")

    def test_weather_lives_in_atmosphere(self):
        self.assertIn("arctic aurora", data.ATMOSPHERE_OPTIONS)
        self.assertNotIn("arctic aurora", data.LIGHTING_OPTIONS)
        for weather in data.WEATHER_ATMOSPHERES:
            self.assertIn(weather, data.ATMOSPHERE_OPTIONS)


class TestLegacyAliases(unittest.TestCase):
    def test_old_title_case_settings_resolve(self):
        self.assertEqual(data.canonical_option("setting", "Aztec pyramid at dawn"),
                         "aztec pyramid at dawn")
        self.assertEqual(data.canonical_option("setting", "Victorian greenhouse"),
                         "victorian greenhouse")

    def test_old_lighting_spellings_resolve(self):
        self.assertEqual(data.canonical_option("lighting", "LED strip underglow"),
                         "led strip underglow")
        self.assertEqual(data.canonical_option("lighting", "TV screen flicker"),
                         "tv screen flicker")

    def test_settings_only_differ_by_case(self):
        for old, new in data.OPTION_ALIASES["setting"].items():
            self.assertEqual(old.lower(), new)
            self.assertIn(new, data.SETTING_OPTIONS)

    def test_free_text_is_untouched(self):
        self.assertEqual(data.canonical_option("setting", "my kitchen"), "my kitchen")
        self.assertEqual(data.canonical_option("setting", ""), "")

    def test_random_theme_not_used_as_alias(self):
        # Anything the user typed that matches an option only by case is fixed;
        # anything else survives as free text.
        self.assertEqual(data.canonical_option("mood", "EPIC"), "epic")
        self.assertEqual(data.canonical_option("mood", "jubilant"), "jubilant")


class TestColourValidity(unittest.TestCase):
    def test_meaningless_combinations_are_blocked(self):
        for family, variation in (
            ("white", "deep"),
            ("white", "dark"),
            ("black", "light"),
            ("black", "pastel"),
            ("void", "pale"),
            ("brown", "neon"),
            ("beige", "neon"),
        ):
            with self.subTest(family=family, variation=variation):
                self.assertFalse(data.is_valid_color_combo(family, variation))

    def test_useful_combinations_survive(self):
        for family, variation in (
            ("amber", "high contrast"),
            ("crimson", "translucent"),
            ("ivory", "matte"),
            ("black", "deep"),
            ("teal", "vintage"),
            ("white", "bright"),
        ):
            with self.subTest(family=family, variation=variation):
                self.assertTrue(data.is_valid_color_combo(family, variation))

    def test_blank_halves_are_always_valid(self):
        self.assertTrue(data.is_valid_color_combo("white", ""))
        self.assertTrue(data.is_valid_color_combo("", "deep"))

    def test_offered_variations_follow_the_family(self):
        white = data.color_variation_options("white")
        self.assertIn("", white)
        self.assertNotIn("deep", white)
        self.assertIn("bright", white)
        self.assertEqual(white[0], "")

    def test_validity_is_what_the_dropdown_offers(self):
        for family in [f for f in data.COLOR_FAMILIES if f]:
            for variation in data.color_variation_options(family):
                self.assertTrue(data.is_valid_color_combo(family, variation))

    def test_random_pick_is_always_valid(self):
        rng = random.Random(20261115)
        for _ in range(500):
            family, variation = data.pick_color_pair(rng)
            self.assertIn(family, data.COLOR_FAMILIES)
            self.assertIn(variation, data.color_variation_options(family))

    def test_retired_words_stay_parseable(self):
        # A preset saved before the prune must still resolve to a palette.
        for word in ("washed out", "forest green", "high contrast", "dreamy", "holographic"):
            self.assertIn(word, [w.lower() for w in data.COLOR_FAMILIES_PARSE + data.COLOR_VARIATIONS_PARSE])

    def test_parse_vocabulary_is_a_superset_of_the_offered_one(self):
        for family in data.COLOR_FAMILIES:
            self.assertIn(family, data.COLOR_FAMILIES_PARSE)
        for variation in data.COLOR_VARIATIONS:
            self.assertIn(variation, data.COLOR_VARIATIONS_PARSE)


class TestAuditTool(unittest.TestCase):
    """The audit script that ships with the repo agrees the lists are clean."""

    def test_no_hard_defects(self):
        tools_dir = pathlib.Path(__file__).resolve().parent.parent / "tools"
        sys.path.insert(0, str(tools_dir))
        try:
            import option_audit
        finally:
            sys.path.remove(str(tools_dir))
        report = option_audit.collect(pathlib.Path("does-not-exist.db"))
        self.assertEqual(option_audit.hard_defects(report), [])


class TestListSizes(unittest.TestCase):
    """Guard rails, not the plan's targets - those are tracked in docs/option-baseline.md."""

    def test_sane_sizes(self):
        expected = {
            "subject": (60, 95),
            "setting": (60, 95),
            "style": (25, 45),
            "lighting": (35, 55),
            "mood": (35, 55),
            "atmosphere": (30, 50),
        }
        for name, (low, high) in expected.items():
            size = len([o for o in data.THEME_VARIABLE_OPTIONS[name] if o])
            with self.subTest(field=name):
                self.assertGreaterEqual(size, low)
                self.assertLessEqual(size, high)

    def test_mode_values_are_frozen(self):
        self.assertEqual(
            data.STYLE_MODES,
            ["anime", "cinematic", "dark-fantasy", "minimalist", "painterly",
             "pixel-art", "product-photo", "realistic", "stylized", "surreal"],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
