"""The mood pick must reach the subject cleanly.

Every mood expands to a comma chain ("epic" -> "grand, epic, monumental") for
the scene clause. That chain used to be handed to the subject anchor as well,
and the anchor keeps only the first word - so picking "epic" produced
"Grand, frog" instead of "Epic frog".
"""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import app_prompt_data as data
import prompt_builder as pb
import theme_mixer as tm


def build(mood: str, subject: str = "frog") -> tuple[dict, str]:
    pick = {
        "subject": subject, "setting": "mountain peak", "style": "oil painting",
        "lighting": "golden hour", "mood": mood, "atmosphere": "mist",
        "color": "moody sand", "mode": "painterly",
    }
    themes = tm.generate_themes(
        count=1, user_keywords=[], subject_lock=True,
        custom_subject=subject, explicit_subject=subject,
        explicit_setting=pick["setting"], explicit_style=pick["style"],
        explicit_lighting=pick["lighting"], explicit_mood=mood,
        explicit_color=pick["color"], explicit_atmosphere=pick["atmosphere"])
    prompt = pb.build_all_prompts(themes, style_mode="painterly", ui_values=pick)[0]["prompt"]
    return themes[0], prompt


class TestMoodAnchor(unittest.TestCase):
    MOODS = [m for m in data.MOOD_OPTIONS if m]

    def test_theme_keeps_the_raw_mood_for_the_anchor(self):
        for mood in self.MOODS:
            with self.subTest(mood=mood):
                theme, _ = build(mood)
                self.assertEqual(theme["components"]["mood"], mood)

    def test_anchor_uses_one_adjective_and_no_comma(self):
        for mood in self.MOODS:
            with self.subTest(mood=mood):
                _, prompt = build(mood)
                opening = prompt.split(".")[0]
                self.assertTrue(opening.startswith("Single main subject:"), opening)
                self.assertNotIn(",", opening)
                self.assertIn(mood.split()[0].lower(), opening.lower())
                self.assertIn("frog", opening.lower())

    def test_scene_clause_keeps_the_rich_phrasing(self):
        from prompt_validator import strengthen_mood

        theme, prompt = build("epic")
        self.assertIn(strengthen_mood("epic").lower(), theme["sentence"].lower())
        self.assertIn("Epic frog", prompt)

    def test_multi_word_mood_uses_first_word(self):
        _, prompt = build("cosmic awe")
        self.assertTrue(prompt.startswith("Single main subject: Cosmic frog"), prompt[:60])

    def test_blank_mood_still_names_the_subject(self):
        pick = {"subject": "frog", "setting": "mountain peak", "style": "oil painting",
                "lighting": "golden hour", "mood": "", "atmosphere": "mist",
                "color": "moody sand", "mode": "painterly"}
        themes = tm.generate_themes(count=1, user_keywords=[], subject_lock=True,
                                    custom_subject="frog", explicit_subject="frog",
                                    explicit_setting="mountain peak", explicit_style="oil painting",
                                    explicit_lighting="golden hour", explicit_mood="",
                                    explicit_color="moody sand", explicit_atmosphere="mist")
        prompt = pb.build_all_prompts(themes, style_mode="painterly", ui_values=pick)[0]["prompt"]
        # A blank mood falls back to the pool, but the phrase must stay clean.
        opening = prompt.split(".")[0]
        self.assertTrue(opening.startswith("Single main subject:"), opening)
        self.assertNotIn(",", opening)
        self.assertTrue(opening.lower().endswith("frog"), opening)


if __name__ == "__main__":
    unittest.main(verbosity=2)
