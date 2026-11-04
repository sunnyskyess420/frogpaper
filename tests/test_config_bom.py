"""A UTF-8 BOM in config.json must not brick the app.

Notepad and PowerShell 5.1 both write UTF-8 with a BOM by default, so this is
a realistic hand-edit.  Before the fix, every load raised, the app ran on
defaults, and the write guard refused to save anything.
"""
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import utils


class TestConfigBOM(unittest.TestCase):
    def _sandbox(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        old = utils.CONFIG_FILE
        self.addCleanup(setattr, utils, "CONFIG_FILE", old)
        utils.CONFIG_FILE = pathlib.Path(tmp.name) / "config.json"
        return utils.CONFIG_FILE

    def test_bom_config_loads(self):
        cfg = self._sandbox()
        cfg.write_text(json.dumps({"provider": "Replicate", "huggingface_token": "hf_x"}),
                       encoding="utf-8-sig")
        data = utils.load_config()
        self.assertEqual(data.get("provider"), "Replicate")
        self.assertEqual(data.get("huggingface_token"), "hf_x")
        self.assertFalse(cfg.with_name("config.json.corrupt").exists())

    def test_saved_config_has_no_bom(self):
        cfg = self._sandbox()
        utils.save_config({"provider": "Pollinations.ai (Free - No Key)"})
        self.assertNotEqual(cfg.read_bytes()[:3], b"\xef\xbb\xbf")
        self.assertEqual(json.loads(cfg.read_text(encoding="utf-8"))["provider"],
                         "Pollinations.ai (Free - No Key)")

    def test_bom_round_trip_keeps_settings_writable(self):
        cfg = self._sandbox()
        cfg.write_text(json.dumps({"app_theme": "darkforest"}), encoding="utf-8-sig")
        data = utils.load_config()
        data["app_theme"] = "neoncyber_light"
        utils.save_config(data)
        self.assertEqual(json.loads(cfg.read_text(encoding="utf-8"))["app_theme"],
                         "neoncyber_light")


if __name__ == "__main__":
    unittest.main()
