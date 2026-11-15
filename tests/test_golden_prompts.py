"""Golden-prompt snapshots.

Locks the prompt text for a representative matrix (one theme per mode, plus the
awkward cases: blank mood, weather atmosphere, a retired colour pair, a
typed-by-hand colour) so an edit to an option list cannot quietly change what
the model receives.

    python tests/test_golden_prompts.py --update    # regenerate after an intended change
    python tests/test_golden_prompts.py             # verify
"""

import json
import pathlib
import random
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import app_prompt_data as data  # noqa: E402
import prompt_builder  # noqa: E402

SNAPSHOT = pathlib.Path(__file__).resolve().parent / "golden_prompts.json"
SEED = 20261115

BASE = {
    "subject": "frog",
    "setting": "mountain peak",
    "lighting": "golden hour",
    "atmosphere": "mist",
    "mood": "epic",
    "color": "moody sand",
    "style": "oil painting",
}

EXTRA_CASES = {
    "blank-mood": (dict(BASE, mood=""), "painterly"),
    "weather-atmosphere": (dict(BASE, atmosphere="rain"), "realistic"),
    "retired-colour-pair": (dict(BASE, color="washed out forest green"), "stylized"),
    "impossible-colour-pair": (dict(BASE, color="deep white"), "minimalist"),
    "halloween-subject": (dict(BASE, subject="jack-o-lantern"), "dark-fantasy"),
}


def cases() -> dict[str, tuple[dict, str]]:
    matrix = {f"mode-{mode}": (dict(BASE), mode) for mode in data.STYLE_MODES}
    matrix.update(EXTRA_CASES)
    return matrix


def build(theme: dict, mode: str) -> dict:
    random.seed(SEED)
    result = prompt_builder.build_prompt(dict(theme), style_mode=mode, ui_values=dict(theme))
    return {
        "prompt": result.get("prompt", ""),
        "negative_prompt": result.get("negative_prompt", ""),
    }


def snapshot() -> dict:
    return {key: build(theme, mode) for key, (theme, mode) in cases().items()}


def write_snapshot() -> None:
    SNAPSHOT.write_text(json.dumps(snapshot(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


class TestGoldenPrompts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SNAPSHOT.exists():
            raise unittest.SkipTest(f"{SNAPSHOT.name} missing - run with --update")
        cls.expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        cls.actual = snapshot()

    def test_matrix_is_covered(self):
        self.assertEqual(set(self.expected), set(self.actual))

    def test_prompts_are_unchanged(self):
        for key, expected in self.expected.items():
            with self.subTest(case=key):
                actual = self.actual.get(key, {})
                self.assertEqual(actual.get("prompt"), expected.get("prompt"))
                self.assertEqual(actual.get("negative_prompt"), expected.get("negative_prompt"))

    def test_prompts_are_not_empty_and_have_no_placeholders(self):
        for key, payload in self.actual.items():
            with self.subTest(case=key):
                self.assertTrue(payload["prompt"].strip())
                self.assertTrue(payload["negative_prompt"].strip())
                self.assertNotIn("{", payload["prompt"])


if __name__ == "__main__":
    if "--update" in sys.argv:
        write_snapshot()
        print(f"wrote {SNAPSHOT.relative_to(REPO_ROOT)}")
    else:
        unittest.main(verbosity=2)
