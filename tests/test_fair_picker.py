"""The random button must use every option before repeating any.

Random sampling is uniform, but uniform is not what "give me something
different" means: with 89 subjects a frog/toad entry is 18% of the list, so
plain sampling shows a frog in most five-click sessions, and 12% of sessions
repeat an exact value. The fair picker deals a shuffled bag instead.
"""

import pathlib
import random
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import app_prompt_data as data
from random_pick import FairPicker, pick_colour_pair


class FakeConfig:
    def __init__(self, initial=None):
        self.data = dict(initial) if initial else {}
        self.save_calls = 0

    def load(self):
        return dict(self.data)

    def save(self, cfg):
        self.data = dict(cfg)
        self.save_calls += 1


POOL = ["a", "b", "c", "d", "e", "f", "g", "h"]


class TestFairPicker(unittest.TestCase):
    def test_first_cycle_uses_every_option_once(self):
        picker = FairPicker(rng=random.Random(1))
        drawn = [picker.pick("subject", POOL) for _ in POOL]
        self.assertEqual(sorted(drawn), sorted(POOL))

    def test_no_repeat_until_the_bag_empties(self):
        picker = FairPicker(rng=random.Random(2))
        drawn = [picker.pick("subject", POOL) for _ in range(len(POOL))]
        self.assertEqual(len(set(drawn)), len(POOL))

    def test_second_cycle_reshuffles(self):
        picker = FairPicker(rng=random.Random(3))
        first = [picker.pick("subject", POOL) for _ in POOL]
        second = [picker.pick("subject", POOL) for _ in POOL]
        self.assertEqual(sorted(second), sorted(POOL))
        self.assertNotEqual(first, second)

    def test_categories_have_independent_bags(self):
        picker = FairPicker(rng=random.Random(4))
        subjects = [picker.pick("subject", POOL) for _ in POOL]
        moods = [picker.pick("mood", POOL) for _ in POOL]
        self.assertEqual(sorted(subjects), sorted(POOL))
        self.assertEqual(sorted(moods), sorted(POOL))

    def test_blank_entries_are_skipped(self):
        picker = FairPicker(rng=random.Random(5))
        pool = ["", "  ", "frog", "owl"]
        drawn = [picker.pick("subject", pool) for _ in range(2)]
        self.assertEqual(sorted(drawn), ["frog", "owl"])

    def test_empty_pool_returns_blank(self):
        picker = FairPicker()
        self.assertEqual(picker.pick("subject", []), "")
        self.assertEqual(picker.pick("subject", ["", " "]), "")

    def test_position_persists_across_instances(self):
        cfg = FakeConfig()
        first = FairPicker(cfg.load, cfg.save, rng=random.Random(6))
        used = [first.pick("subject", POOL) for _ in range(3)]

        second = FairPicker(cfg.load, cfg.save, rng=random.Random(99))
        rest = [second.pick("subject", POOL) for _ in range(len(POOL) - 3)]

        self.assertEqual(sorted(used + rest), sorted(POOL), "restart must not restart the cycle")

    def test_edited_pool_starts_a_fresh_cycle(self):
        cfg = FakeConfig()
        picker = FairPicker(cfg.load, cfg.save, rng=random.Random(7))
        for _ in range(4):
            picker.pick("subject", POOL)
        changed = POOL + ["i"]
        remaining = picker.remaining("subject", changed)
        self.assertEqual(remaining, len(changed))
        self.assertIn(picker.pick("subject", changed), changed)

    def test_remaining_counts_down(self):
        picker = FairPicker(rng=random.Random(8))
        self.assertEqual(picker.remaining("subject", POOL), len(POOL))
        picker.pick("subject", POOL)
        self.assertEqual(picker.remaining("subject", POOL), len(POOL) - 1)

    def test_reset_restarts_the_cycle(self):
        picker = FairPicker(rng=random.Random(9))
        for _ in range(3):
            picker.pick("subject", POOL)
        picker.reset("subject")
        self.assertEqual(picker.remaining("subject", POOL), len(POOL))

    def test_survives_a_broken_config(self):
        def boom():
            raise RuntimeError("no config")

        picker = FairPicker(boom, boom)
        drawn = [picker.pick("subject", POOL) for _ in POOL]
        self.assertEqual(sorted(drawn), sorted(POOL))

    def test_corrupt_state_is_ignored(self):
        cfg = FakeConfig({"random_draw_state": ["not", "a", "dict"]})
        picker = FairPicker(cfg.load, cfg.save)
        self.assertEqual(picker.pick("subject", POOL) in POOL, True)


class TestRealLists(unittest.TestCase):
    def test_every_subject_appears_before_any_repeat(self):
        picker = FairPicker(rng=random.Random(10))
        subjects = [s for s in data.SUBJECT_OPTIONS if s]
        drawn = [picker.pick("subject", subjects) for _ in subjects]
        self.assertEqual(sorted(drawn), sorted(subjects))

    def test_every_mode_and_atmosphere_covered(self):
        picker = FairPicker(rng=random.Random(11))
        atmospheres = [a for a in data.ATMOSPHERE_OPTIONS if a]
        drawn = [picker.pick("atmosphere", atmospheres) for _ in atmospheres]
        self.assertEqual(sorted(drawn), sorted(atmospheres))

        modes = list(data.STYLE_MODES)
        mode_draws = [picker.pick("mode", modes) for _ in modes]
        self.assertEqual(sorted(mode_draws), sorted(modes))

    def test_colour_pairs_are_valid_and_families_are_covered(self):
        picker = FairPicker(rng=random.Random(12))
        families = [f for f in data.COLOR_FAMILIES if f]
        seen = []
        for _ in families:
            family, variation = pick_colour_pair(picker)
            self.assertIn(family, families)
            self.assertTrue(data.is_valid_color_combo(family, variation))
            seen.append(family)
        self.assertEqual(sorted(seen), sorted(families))

    def test_colour_variations_cycle_within_a_family(self):
        picker = FairPicker(rng=random.Random(13))
        options = [o for o in data.color_variation_options("amber") if o]
        drawn = [picker.pick("color_variation:amber", options) for _ in options]
        self.assertEqual(sorted(drawn), sorted(options))


if __name__ == "__main__":
    unittest.main(verbosity=2)
