"""Frogs must not appear in prompts that never asked for one.

The Frog Dial ("frog_sneak": off) only governs the deliberate frog injection.
A separate leak put frogs in unrelated prompts: a composition entry in
keywords.json read "wide panoramic framing frog in natural environment", so one
run in thirteen with the dial off still produced a frog.
"""

import json
import pathlib
import random
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import app_prompt_data as data
import prompt_builder as pb
import theme_mixer as tm

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
AMPHIBIANS = ("frog", "toad")


def has_amphibian(text: str) -> bool:
    low = (text or "").lower()
    return any(word in low for word in AMPHIBIANS)


def build(subject: str, mode: str = "painterly"):
    pick = {
        "subject": subject, "setting": "mountain peak", "style": "oil painting",
        "lighting": "golden hour", "mood": "epic", "atmosphere": "mist",
        "color": "moody sand", "mode": mode,
    }
    themes = tm.generate_themes(
        count=1, user_keywords=[], subject_lock=True,
        custom_subject=subject, explicit_subject=subject,
        explicit_setting=pick["setting"], explicit_style=pick["style"],
        explicit_lighting=pick["lighting"], explicit_mood=pick["mood"],
        explicit_color=pick["color"], explicit_atmosphere=pick["atmosphere"])
    prompt = pb.build_all_prompts(themes, style_mode=mode, ui_values=pick)[0]
    return themes[0], prompt


class TestAmphibianHelper(unittest.TestCase):
    def test_detects_frogs_and_toads(self):
        for subject in ("frog", "tree frog", "golden toad", "cute toad", "bullfrog"):
            self.assertTrue(tm.is_amphibian_subject(subject), subject)

    def test_other_subjects_are_not_amphibians(self):
        for subject in ("wolf", "eagle", "witch", "dragon", "haunted house", ""):
            self.assertFalse(tm.is_amphibian_subject(subject), subject)

    def test_pool_is_filtered_for_non_frog_subjects(self):
        pool = ["wide panoramic framing frog in natural environment",
                "wide cinematic framing", "a toad on a log"]
        self.assertEqual(tm.strip_amphibian_pool(pool, "wolf"),
                         ["wide cinematic framing"])

    def test_pool_is_untouched_for_frog_subjects(self):
        pool = ["wide panoramic framing frog in natural environment", "wide cinematic framing"]
        self.assertEqual(tm.strip_amphibian_pool(pool, "tree frog"), pool)


class TestCompositionCannotInjectAFrog(unittest.TestCase):
    """Deterministic: force the old frog-laden pool and check it is filtered."""

    def setUp(self):
        self._orig_loader = tm.load_keywords
        fake = {"composition": ["wide panoramic framing frog in natural environment"],
                "subjects": ["frog", "tree frog", "wolf", "eagle"],
                "styles": ["oil painting"], "mood": ["epic"], "colors": ["moody sand"],
                "lighting": ["golden hour"], "atmosphere": ["mist"],
                "tech_elements": []}
        tm.load_keywords = lambda: fake

    def tearDown(self):
        tm.load_keywords = self._orig_loader

    def test_non_frog_subject_gets_no_frog_composition(self):
        for subject in ("wolf", "eagle", "witch"):
            with self.subTest(subject=subject):
                theme, prompt = build(subject)
                self.assertFalse(has_amphibian(theme["components"]["composition"]))
                self.assertFalse(has_amphibian(prompt["prompt"]))
                self.assertFalse(has_amphibian(prompt["negative_prompt"]))

    def test_frog_subject_still_allowed_its_composition(self):
        theme, _ = build("frog")
        self.assertIn("frog", theme["components"]["composition"])


class TestShippedData(unittest.TestCase):
    def setUp(self):
        self.keywords = json.loads((REPO_ROOT / "keywords.json").read_text(encoding="utf-8"))

    def test_no_amphibian_wording_outside_the_subject_pool(self):
        offenders = {}
        for key, values in self.keywords.items():
            if not isinstance(values, list) or key == "subjects":
                continue
            bad = [v for v in values if isinstance(v, str) and has_amphibian(v)]
            if bad:
                offenders[key] = bad
        self.assertEqual(offenders, {}, "frog wording outside 'subjects' leaks into any prompt")

    def test_the_auto_subject_pool_excludes_amphibians(self):
        pool = [s for s in self.keywords.get("subjects", []) if not tm.is_amphibian_subject(s)]
        self.assertTrue(pool)
        self.assertEqual([s for s in pool if has_amphibian(s)], [])


class TestDicePool(unittest.TestCase):
    """The random button must not hand out a frog when the dial is off."""

    SUBJECTS = ["frog", "tree frog", "golden toad", "wolf", "eagle", "witch"]

    def test_dial_off_removes_amphibians(self):
        pool = tm.random_subject_pool(self.SUBJECTS, frog_level=0.0)
        self.assertEqual(pool, ["wolf", "eagle", "witch"])

    def test_dial_on_keeps_them(self):
        pool = tm.random_subject_pool(self.SUBJECTS, frog_level=0.12)
        self.assertEqual(pool, self.SUBJECTS)

    def test_pool_never_empties(self):
        only_frogs = ["frog", "tree frog"]
        self.assertEqual(tm.random_subject_pool(only_frogs, frog_level=0.0), only_frogs)

    def test_real_list_loses_its_amphibians(self):
        pool = tm.random_subject_pool(data.SUBJECT_OPTIONS, frog_level=0.0)
        self.assertTrue(pool)
        self.assertEqual([s for s in pool if has_amphibian(s)], [])


class TestEndToEnd(unittest.TestCase):
    def test_non_frog_subjects_across_every_mode(self):
        subjects = ["wolf", "eagle", "astronaut", "witch", "dragon", "kraken", "owl", "fox"]
        random.seed(11)
        for subject in subjects:
            for mode in data.STYLE_MODES:
                with self.subTest(subject=subject, mode=mode):
                    _, prompt = build(subject, mode)
                    self.assertFalse(has_amphibian(prompt["prompt"]),
                                     f"{subject}/{mode} prompt mentions an amphibian")
                    self.assertFalse(has_amphibian(prompt["negative_prompt"]))

    def test_blank_subject_with_dial_off_never_picks_an_amphibian(self):
        self.assertEqual(tm.get_frog_sneak_probability(), 0.0,
                         "config.json must have frog_sneak = off for this test")
        random.seed(5)
        for _ in range(25):
            theme = tm.generate_themes(count=1, user_keywords=[], subject_lock=True)[0]
            self.assertFalse(tm.is_amphibian_subject(theme["components"]["subject"]),
                             theme["components"]["subject"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
