"""Tests for the keyword expansion pipeline in keyword_expander.py.

Covers (improvement report §5 — testing expansion):
  - keywords.json loading: metadata filtering, lowercasing, corrupt/missing files
  - user thesaurus JSON fallback loading
  - expand_keyword pipeline order: user thesaurus -> known keyword ->
    semantic similarity (stubbed) -> thesaurus synonyms (stubbed) -> fallback
  - expansion cache behaviour
  - expand_text whole-word case-insensitive replacement
  - user mapping add/remove + JSON persistence round-trips
  - expansion history stats and periodic log file writes
  - dependency-guard behaviour when NLTK / sentence-transformers absent

ISOLATION — two guards, both mandatory:
  1. Every file path used by the module (BASE_DIR, KEYWORDS_FILE, LOGS_DIR)
     is redirected into a per-test temp directory. Your real keywords.json,
     user_thesaurus.json and logs are never read or written.
  2. _get_db is patched to return None. WITHOUT THIS, on a machine where
     sqlalchemy is installed, _load_user_thesaurus / _save_user_thesaurus /
     _save_expansion_log would hit your REAL frogpaper.db — and
     _save_user_thesaurus does a delete-all + re-insert. The patch forces
     the JSON fallback so tests can never touch the database.
  NLTK / sentence-transformers behaviour is stubbed per-test, so results
  are identical whether or not those libraries are installed.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import keyword_expander as ke


class KeywordExpanderTestBase(unittest.TestCase):
    """Temp-dir isolation + DB safety for every test."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        (self.tmp / "logs").mkdir()
        self._patch("BASE_DIR", self.tmp)
        self._patch("KEYWORDS_FILE", self.tmp / "keywords.json")
        self._patch("LOGS_DIR", self.tmp / "logs")
        # DB safety: force the JSON fallback everywhere (see module docstring)
        self._patch("_get_db", lambda: None)
        self.addCleanup(self._tmp.cleanup)

    def _patch(self, name, value):
        original = getattr(ke, name)
        setattr(ke, name, value)
        self.addCleanup(setattr, ke, name, original)

    def _write_keywords(self, data):
        (self.tmp / "keywords.json").write_text(
            json.dumps(data), encoding="utf-8")

    def _write_thesaurus(self, data):
        (self.tmp / "user_thesaurus.json").write_text(
            json.dumps(data), encoding="utf-8")

    def _expander(self, keywords=None, thesaurus=None):
        """Fresh KeywordExpander, initialized with optional seed data."""
        if keywords is not None:
            self._write_keywords(keywords)
        if thesaurus is not None:
            self._write_thesaurus(thesaurus)
        expander = ke.KeywordExpander()
        expander.initialize()
        return expander

    def _stub_deps(self, expander, semantic=None, synonyms=None):
        """Stub the optional-library branches with fixed results + call counter."""
        calls = {"semantic": 0, "synonyms": 0}

        expander._check_sentence_transformers = lambda: True
        expander._check_nltk = lambda: True

        def fake_semantic(word, top_k=3):
            calls["semantic"] += 1
            return list(semantic or [])

        def fake_synonyms(word):
            calls["synonyms"] += 1
            return list(synonyms or [])

        expander.find_semantic_similarities = fake_semantic
        expander.get_synonyms_from_thesaurus = fake_synonyms
        return calls


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

class TestLoadKeywords(KeywordExpanderTestBase):
    def test_filters_metadata_and_lowercases(self):
        expander = self._expander(keywords={
            "subject": ["Frog", "  Dragon "],
            "_comment": "generated file, ignore this key",
        })
        self.assertEqual(expander.keywords_data, {"subject": ["Frog", "  Dragon "]})
        self.assertEqual(expander.all_keywords_set, {"frog", "dragon"})

    def test_missing_file_gives_empty_state(self):
        expander = self._expander()
        self.assertEqual(expander.keywords_data, {})
        self.assertEqual(expander.all_keywords_set, set())

    def test_corrupt_json_degrades_gracefully(self):
        (self.tmp / "keywords.json").write_text("{not valid json!!", encoding="utf-8")
        expander = ke.KeywordExpander()
        expander.initialize()
        self.assertEqual(expander.keywords_data, {})
        self.assertEqual(expander.all_keywords_set, set())


class TestLoadUserThesaurus(KeywordExpanderTestBase):
    def test_json_fallback_loaded(self):
        expander = self._expander(thesaurus={"cat": "frog"})
        self.assertEqual(expander.user_thesaurus, {"cat": "frog"})

    def test_missing_thesaurus_gives_empty_dict(self):
        expander = self._expander()
        self.assertEqual(expander.user_thesaurus, {})

    def test_initialize_sets_flag_once(self):
        expander = self._expander(keywords={"subject": ["neon"]})
        self.assertTrue(expander._initialized)


# ---------------------------------------------------------------------------
# expand_keyword pipeline
# ---------------------------------------------------------------------------

class TestExpandKeywordPipeline(KeywordExpanderTestBase):
    def test_empty_string_returns_empty(self):
        expander = self._expander()
        self.assertEqual(expander.expand_keyword("   "), "")

    def test_user_thesaurus_has_top_priority(self):
        expander = self._expander(
            keywords={"subject": ["neon"]},
            thesaurus={"cat": "frog"},
        )
        self._stub_deps(expander, semantic=[("neon", 0.99)])
        self.assertEqual(expander.expand_keyword("CAT"), "frog")
        self.assertEqual(expander.expansion_history[0]["method"], "user_thesaurus")

    def test_known_keyword_passes_through_unchanged(self):
        expander = self._expander(keywords={"subject": ["neon"]})
        self._stub_deps(expander, semantic=[("frog", 0.99)])
        self.assertEqual(expander.expand_keyword("  NEON  "), "neon")
        # passthrough is not logged as an expansion
        self.assertEqual(expander.expansion_history, [])

    def test_semantic_match_above_threshold_wins(self):
        expander = self._expander(keywords={"subject": ["frog"]})
        self._stub_deps(expander, semantic=[("frog", 0.9)])
        self.assertEqual(expander.expand_keyword("ribbit"), "frog")
        self.assertEqual(expander.expansion_history[0]["method"],
                         "semantic_similarity")

    def test_semantic_match_below_threshold_ignored(self):
        expander = self._expander(keywords={"subject": ["frog"]})
        self._stub_deps(expander, semantic=[("frog", 0.5)])
        self.assertEqual(expander.expand_keyword("ribbit"), "ribbit")

    def test_thesaurus_synonym_matching_known_keyword(self):
        expander = self._expander(keywords={"subject": ["tree frog"]})
        self._stub_deps(expander, semantic=[], synonyms=["tree frog"])
        self.assertEqual(expander.expand_keyword("ribbit"), "tree frog")
        self.assertEqual(expander.expansion_history[0]["method"],
                         "thesaurus_match")

    def test_synonyms_not_matching_keywords_fall_back_to_original(self):
        expander = self._expander(keywords={"subject": ["neon"]})
        self._stub_deps(expander, semantic=[], synonyms=["croaking"])
        self.assertEqual(expander.expand_keyword("ribbit"), "ribbit")

    def test_no_deps_fallback_returns_cleaned_original(self):
        expander = self._expander(keywords={"subject": ["neon"]})
        self._stub_deps(expander)  # both stubs return []
        self.assertEqual(expander.expand_keyword("Ribbit"), "ribbit")

    def test_cache_prevents_repeat_lookups(self):
        expander = self._expander(keywords={"subject": ["frog"]})
        calls = self._stub_deps(expander, semantic=[("frog", 0.9)])
        first = expander.expand_keyword("ribbit")
        second = expander.expand_keyword("ribbit")
        self.assertEqual(first, second)
        self.assertEqual(calls["semantic"], 1)


# ---------------------------------------------------------------------------
# expand_text
# ---------------------------------------------------------------------------

class TestExpandText(KeywordExpanderTestBase):
    def test_replaces_whole_words_case_insensitively(self):
        expander = self._expander(thesaurus={"cat": "frog"})
        self._stub_deps(expander)
        # Genuine expansion rewrites the word (case-insensitively);
        # "A" and "catapult" are untouched, keeping their original casing.
        self.assertEqual(expander.expand_text("A CAT and a catapult"),
                         "A frog and a catapult")

    def test_unexpanded_words_keep_their_casing(self):
        """Regression: expand_text used to lowercase unrecognized words
        (step-5 fallback returns the cleaned form, which then differed
        from the original only by case and was rewritten). Since the fix,
        case-only differences are skipped and casing is preserved."""
        expander = self._expander(keywords={"subject": ["neon"]})
        self._stub_deps(expander)
        self.assertEqual(expander.expand_text("NEON Signs"), "NEON Signs")

    def test_known_keyword_casing_preserved_in_text(self):
        expander = self._expander(keywords={"subject": ["neon", "frog"]})
        self._stub_deps(expander)
        self.assertEqual(expander.expand_text("Neon frog"), "Neon frog")

    def test_real_expansion_still_rewrites_cased_input(self):
        expander = self._expander(thesaurus={"cat": "frog"})
        self._stub_deps(expander)
        self.assertEqual(expander.expand_text("Neon Cat"), "Neon frog")

    def test_preserves_punctuation(self):
        expander = self._expander(thesaurus={"cat": "frog"})
        self._stub_deps(expander)
        self.assertEqual(expander.expand_text("cat, dog!"), "frog, dog!")

    def test_unchanged_text_returned_intact(self):
        expander = self._expander(keywords={"subject": ["neon", "frog"]})
        self._stub_deps(expander)
        self.assertEqual(expander.expand_text("neon frog"), "neon frog")


# ---------------------------------------------------------------------------
# User mapping persistence (JSON fallback)
# ---------------------------------------------------------------------------

class TestUserMappingPersistence(KeywordExpanderTestBase):
    def test_add_mapping_lowercases_and_persists(self):
        expander = self._expander()
        expander.add_user_mapping("Cat", "Frog")
        self.assertEqual(expander.user_thesaurus, {"cat": "frog"})
        saved = json.loads((self.tmp / "user_thesaurus.json").read_text(
            encoding="utf-8"))
        self.assertEqual(saved, {"cat": "frog"})

    def test_mapping_survives_reinstantiation(self):
        expander = self._expander()
        expander.add_user_mapping("cat", "frog")
        fresh = ke.KeywordExpander()
        fresh.initialize()
        self.assertEqual(fresh.check_user_thesaurus("CAT"), "frog")

    def test_remove_mapping_updates_disk(self):
        expander = self._expander(thesaurus={"cat": "frog", "wolf": "dog"})
        expander.remove_user_mapping("CAT")
        self.assertEqual(expander.user_thesaurus, {"wolf": "dog"})
        saved = json.loads((self.tmp / "user_thesaurus.json").read_text(
            encoding="utf-8"))
        self.assertEqual(saved, {"wolf": "dog"})

    def test_remove_unknown_mapping_creates_no_file(self):
        expander = self._expander()
        expander.remove_user_mapping("ghost")
        self.assertFalse((self.tmp / "user_thesaurus.json").exists())


# ---------------------------------------------------------------------------
# Stats + expansion log
# ---------------------------------------------------------------------------

class TestStatsAndLog(KeywordExpanderTestBase):
    def test_empty_history_stats(self):
        stats = self._expander().get_expansion_stats()
        self.assertEqual(stats["total_expansions"], 0)
        self.assertEqual(stats["methods"], {})
        self.assertEqual(stats["success_rate"], 0)

    def test_stats_count_methods_and_success_rate(self):
        expander = self._expander(thesaurus={"cat": "frog"})
        self._stub_deps(expander, semantic=[("ribbit", 0.9)])
        expander.expand_keyword("CAT")     # changes the word -> successful
        expander.expand_keyword("ribbit")  # semantic hit == original -> logged, not successful
        stats = expander.get_expansion_stats()
        self.assertEqual(stats["total_expansions"], 2)
        self.assertEqual(stats["methods"],
                         {"user_thesaurus": 1, "semantic_similarity": 1})
        self.assertEqual(stats["success_rate"], 50.0)

    def test_expansion_log_file_written_every_10_entries(self):
        expander = self._expander()
        for _ in range(10):
            expander._log_expansion("a", "b", "test")
        log_file = self.tmp / "logs" / "keyword_expansion.json"
        self.assertTrue(log_file.exists())
        entries = json.loads(log_file.read_text(encoding="utf-8"))
        self.assertEqual(len(entries), 10)
        self.assertEqual(entries[0]["method"], "test")


# ---------------------------------------------------------------------------
# Dependency guards (deterministic on machines with or without the libs)
# ---------------------------------------------------------------------------

class TestDependencyGuards(KeywordExpanderTestBase):
    def test_unavailable_nltk_returns_no_synonyms(self):
        expander = self._expander()
        expander._check_nltk = lambda: False
        self.assertEqual(expander.get_synonyms_from_thesaurus("word"), [])

    def test_unavailable_sentence_transformers_returns_no_similarities(self):
        expander = self._expander()
        expander._check_sentence_transformers = lambda: False
        self.assertEqual(expander.find_semantic_similarities("word"), [])


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

class TestSingleton(KeywordExpanderTestBase):
    def test_get_keyword_expander_returns_same_instance(self):
        self.assertIs(ke.get_keyword_expander(), ke.get_keyword_expander())


if __name__ == "__main__":
    unittest.main()
