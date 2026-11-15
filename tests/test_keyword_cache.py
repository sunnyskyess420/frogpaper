"""Keyword-bank embeddings are cached to disk.

Encoding the whole bank with sentence-transformers on every launch is what made
the first Generate sit there. The cache is keyed by a fingerprint of the bank,
so editing keywords.json (or changing the model) invalidates it automatically.
"""

import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

try:
    import numpy as np
    HAVE_NUMPY = True
except ImportError:  # pragma: no cover - minimal interpreters
    HAVE_NUMPY = False

import keyword_expander as ke

WORDS = ["frog", "owl", "wolf", "mountain", "mist"]


@unittest.skipUnless(HAVE_NUMPY, "numpy not installed")
class TestSignature(unittest.TestCase):
    def test_stable_and_order_independent(self):
        a = ke.bank_signature(WORDS)
        b = ke.bank_signature(list(reversed(WORDS)))
        self.assertEqual(a, b)

    def test_changes_when_the_bank_changes(self):
        self.assertNotEqual(ke.bank_signature(WORDS), ke.bank_signature(WORDS + ["toad"]))

    def test_changes_when_the_model_changes(self):
        self.assertNotEqual(ke.bank_signature(WORDS, "model-a"),
                            ke.bank_signature(WORDS, "model-b"))


@unittest.skipUnless(HAVE_NUMPY, "numpy not installed")
class TestEmbeddingCache(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = pathlib.Path(self._tmp.name) / "keyword_embeddings.npz"
        self._patch = mock.patch.object(ke, "EMBEDDINGS_CACHE", self.path)
        self._patch.start()
        self.addCleanup(self._patch.stop)
        self.addCleanup(self._tmp.cleanup)
        self.matrix = np.random.default_rng(0).random((len(WORDS), 8), dtype="float32")

    def test_round_trip(self):
        ke.save_cached_embeddings(WORDS, self.matrix)
        self.assertTrue(self.path.exists())
        loaded = ke.load_cached_embeddings(WORDS)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.shape, self.matrix.shape)
        self.assertTrue(np.allclose(loaded, self.matrix))

    def test_missing_file_returns_none(self):
        self.assertIsNone(ke.load_cached_embeddings(WORDS))

    def test_edited_bank_invalidates(self):
        ke.save_cached_embeddings(WORDS, self.matrix)
        self.assertIsNone(ke.load_cached_embeddings(WORDS + ["toad"]))

    def test_corrupt_file_returns_none(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(b"not an npz")
        self.assertIsNone(ke.load_cached_embeddings(WORDS))

    def test_save_failure_is_not_fatal(self):
        with mock.patch.object(ke.np if hasattr(ke, "np") else np, "savez_compressed",
                               side_effect=OSError("disk full")):
            ke.save_cached_embeddings(WORDS, self.matrix)  # must not raise
        self.assertFalse(self.path.exists())

    def test_torch_tensor_is_accepted(self):
        class FakeTensor:
            def __init__(self, array):
                self._array = array

            def detach(self):
                return self

            def cpu(self):
                return self

            def numpy(self):
                return self._array

        ke.save_cached_embeddings(WORDS, FakeTensor(self.matrix))
        self.assertIsNotNone(ke.load_cached_embeddings(WORDS))


class TestExpansionCache(unittest.TestCase):
    """Per-word results persist, so a seen word never loads the model again."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(self._tmp.name)
        self.path = root / "expansions.json"
        self._patch_path = mock.patch.object(ke, "EXPANSIONS_CACHE", self.path)
        self._patch_dir = mock.patch.object(ke, "CACHE_DIR", root)
        self._patch_flag = mock.patch.object(ke, "_persistence_enabled", lambda: True)
        self._patch_flag2 = mock.patch.object(ke, "PERSIST_EXPANSIONS", True)
        self._patch_path.start()
        self._patch_dir.start()
        self._patch_flag.start()
        self._patch_flag2.start()
        self.addCleanup(self._patch_path.stop)
        self.addCleanup(self._patch_dir.stop)
        self.addCleanup(self._patch_flag.stop)
        self.addCleanup(self._patch_flag2.stop)
        self.addCleanup(self._tmp.cleanup)

        self.expander = ke.KeywordExpander()
        self.expander.all_keywords_set = set(WORDS)
        self.expander.user_thesaurus = {}

    def test_remember_writes_to_disk(self):
        self.expander._remember("toad", "frog")
        self.assertTrue(self.path.exists())
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(data["words"]["toad"], "frog")

    def test_reload_in_a_new_instance(self):
        self.expander._remember("toad", "frog")
        fresh = ke.KeywordExpander()
        fresh.all_keywords_set = set(WORDS)
        fresh.user_thesaurus = {}
        fresh._load_expansions()
        self.assertEqual(fresh._expansion_cache.get("toad"), "frog")

    def test_signature_changes_with_the_thesaurus(self):
        before = self.expander._expansion_signature()
        self.expander.user_thesaurus = {"bunny": "rabbit"}
        self.assertNotEqual(before, self.expander._expansion_signature())

    def test_stale_signature_is_ignored(self):
        self.expander._remember("toad", "frog")
        changed = ke.KeywordExpander()
        changed.all_keywords_set = set(WORDS)
        changed.user_thesaurus = {"bunny": "rabbit"}
        changed._load_expansions()
        self.assertEqual(changed._expansion_cache, {})

    def test_corrupt_file_is_ignored(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("{not json", encoding="utf-8")
        self.expander._load_expansions()
        self.assertEqual(self.expander._expansion_cache, {})

    def test_known_word_expands_without_loading_the_model(self):
        self.expander._expansion_cache["owl"] = "owl"
        self.assertEqual(self.expander.expand_keyword("owl"), "owl")
        self.assertIsNone(self.expander.sentence_model,
                          "a cached word must not load sentence-transformers")


if __name__ == "__main__":
    unittest.main(verbosity=2)
