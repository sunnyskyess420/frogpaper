"""Tests for the config schema / validation / migration layer in utils.py.

Covers (improvement report §5):
  - schema validation: wrong-typed values are dropped safely
  - graceful handling: corrupt JSON -> empty config + corrupt-file backup
  - migration: schema version stamping, key rename registry
  - non-destructiveness: unknown keys and valid values always preserved
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import utils


class ConfigTestBase(unittest.TestCase):
    """Each test gets its own temp config.json (never the real one)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._original = utils.CONFIG_FILE
        utils.CONFIG_FILE = Path(self._tmp.name) / "config.json"
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(setattr, utils, "CONFIG_FILE", self._original)

    def write(self, data):
        utils.CONFIG_FILE.write_text(json.dumps(data), encoding="utf-8")


class TestLoadDefaults(ConfigTestBase):

    def test_missing_file_returns_empty(self):
        self.assertEqual(utils.load_config(), {})


class TestSchemaValidation(ConfigTestBase):

    def test_valid_config_round_trips(self):
        self.write({"app_theme": "darkforest", "slideshow_interval": 30})
        cfg = utils.load_config()
        self.assertEqual(cfg["app_theme"], "darkforest")
        self.assertEqual(cfg["slideshow_interval"], 30)

    def test_wrong_typed_values_are_dropped(self):
        self.write({
            "app_theme": "darkforest",        # valid, must survive
            "slideshow_interval": "30",       # str, expected int -> dropped
            "remember_settings": "yes",       # str, expected bool -> dropped
            "completed_tutorials": "nope",    # str, expected list -> dropped
            "pinned_options": [1, 2],         # list, expected dict -> dropped
        })
        cfg = utils.load_config()
        self.assertEqual(cfg["app_theme"], "darkforest")
        self.assertNotIn("slideshow_interval", cfg)
        self.assertNotIn("remember_settings", cfg)
        self.assertNotIn("completed_tutorials", cfg)
        self.assertNotIn("pinned_options", cfg)

    def test_integral_float_coerced_to_int(self):
        self.write({"slideshow_interval": 45.0})
        cfg = utils.load_config()
        self.assertEqual(cfg["slideshow_interval"], 45)
        self.assertIsInstance(cfg["slideshow_interval"], int)

    def test_non_integral_float_dropped(self):
        self.write({"slideshow_interval": 45.5})
        cfg = utils.load_config()
        self.assertNotIn("slideshow_interval", cfg)

    def test_bool_is_not_accepted_as_int(self):
        # bool is a subclass of int in Python — strict type() must reject it
        self.write({"slideshow_interval": True})
        cfg = utils.load_config()
        self.assertNotIn("slideshow_interval", cfg)

    def test_unknown_keys_are_preserved(self):
        self.write({"custom_future_setting": {"a": 1}, "note": "hello"})
        cfg = utils.load_config()
        self.assertEqual(cfg["custom_future_setting"], {"a": 1})
        self.assertEqual(cfg["note"], "hello")


class TestMigration(ConfigTestBase):

    def test_version_stamped_on_load(self):
        self.write({"app_theme": "darkforest"})  # old config, no version key
        cfg = utils.load_config()
        self.assertEqual(cfg["config_version"], utils.CONFIG_SCHEMA_VERSION)

    def test_migration_applies_key_renames(self):
        # Temporarily register a rename to exercise the migration mechanism
        original = dict(utils._CONFIG_KEY_RENAMES)
        utils._CONFIG_KEY_RENAMES["old_provider"] = "provider"
        try:
            self.write({"old_provider": "pollinations"})
            cfg = utils.load_config()
            self.assertEqual(cfg["provider"], "pollinations")
            self.assertNotIn("old_provider", cfg)
        finally:
            utils._CONFIG_KEY_RENAMES.clear()
            utils._CONFIG_KEY_RENAMES.update(original)

    def test_old_version_is_bumped(self):
        self.write({"config_version": 0, "app_theme": "darkforest"})
        cfg = utils.load_config()
        self.assertEqual(cfg["config_version"], utils.CONFIG_SCHEMA_VERSION)
        self.assertEqual(cfg["app_theme"], "darkforest")


class TestSaveStamping(ConfigTestBase):

    def test_save_stamps_schema_version(self):
        utils.save_config({"app_theme": "darkforest"})
        saved = json.loads(utils.CONFIG_FILE.read_text(encoding="utf-8"))
        self.assertEqual(saved["config_version"], utils.CONFIG_SCHEMA_VERSION)
        self.assertEqual(saved["app_theme"], "darkforest")

    def test_save_overwrites_stale_version(self):
        utils.save_config({"config_version": 99})
        saved = json.loads(utils.CONFIG_FILE.read_text(encoding="utf-8"))
        self.assertEqual(saved["config_version"], utils.CONFIG_SCHEMA_VERSION)


class TestCorruptConfig(ConfigTestBase):

    def test_corrupt_json_returns_empty_and_backs_up(self):
        broken = "{ this is not valid json !!!"
        utils.CONFIG_FILE.write_text(broken, encoding="utf-8")
        cfg = utils.load_config()
        self.assertEqual(cfg, {})
        backup = utils.CONFIG_FILE.with_name("config.json.corrupt")
        self.assertTrue(backup.exists(), "corrupt config was not backed up")
        self.assertIn("not valid json", backup.read_text(encoding="utf-8"))

    def test_non_dict_json_returns_empty(self):
        utils.CONFIG_FILE.write_text("[1, 2, 3]", encoding="utf-8")
        self.assertEqual(utils.load_config(), {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
