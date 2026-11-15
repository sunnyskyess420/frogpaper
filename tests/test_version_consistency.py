"""Version numbers must agree everywhere.

They already drifted once: app.py said 1.8.0 while the release history and the
About box promised 1.8.1. This test keeps the four places in step — the
constant, the history tuple, the installer script and the release notes.
"""

import pathlib
import re
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import app


class TestVersionConsistency(unittest.TestCase):
    def setUp(self):
        self.version = app.APP_VERSION

    def test_version_looks_like_a_version(self):
        self.assertRegex(self.version, r"^\d+\.\d+\.\d+$")

    def test_release_history_starts_with_app_version(self):
        self.assertEqual(app.RELEASE_HISTORY[0][0], self.version)

    def test_history_is_newest_first(self):
        versions = [entry[0] for entry in app.RELEASE_HISTORY]
        keyed = [tuple(int(part) for part in v.split(".")) for v in versions]
        self.assertEqual(keyed, sorted(keyed, reverse=True), versions)

    def test_installer_script_matches(self):
        script = (REPO_ROOT / "build_installer.bat").read_text(encoding="utf-8")
        self.assertIn(f"AppVersion={self.version}", script)
        self.assertIn(f"FrogPaper-Setup-{self.version}", script)

    def test_release_notes_exist(self):
        notes = REPO_ROOT / f"RELEASE_NOTES_v{self.version}.md"
        self.assertTrue(notes.exists(), f"{notes.name} is missing")
        self.assertIn("FrogPaper", notes.read_text(encoding="utf-8"))

    def test_readme_changelog_has_the_entry(self):
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertRegex(readme, rf"### v{re.escape(self.version)} - ")
        self.assertIn(f"Desktop — v{self.version}", readme)

    def test_about_string_shows_the_version(self):
        self.assertIn(self.version, app.RELEASE_HIGHLIGHTS[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
