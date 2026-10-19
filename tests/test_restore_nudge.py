"""Tests for the empty-gallery restore nudge.

Headless: the mixin methods are exercised against a stub host object with a
recording widget, so no Tk window and no real config file are involved.
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app_cloud_mixin import FrogPaperAppCloudMixin


class FakeWidget:
    def __init__(self):
        self.grid_calls = []
        self.removed = 0

    def grid(self, **kwargs):
        self.grid_calls.append(kwargs)

    def grid_remove(self):
        self.removed += 1


class StubApp(FrogPaperAppCloudMixin):
    """Minimal host; inherits the mixin so sibling methods resolve."""

    def __init__(self):
        self._restore_nudge = FakeWidget()
        self.MANUAL_DIR = Path(".")
        self.statuses = []

    def _set_restore_status(self, text):
        self.statuses.append(text)


class _FakeResult:
    def __init__(self, written):
        self.written = written

    def summary(self):
        return "stub summary"


def _show(app, images=None, config=None):
    with mock.patch("utils.load_config", return_value=dict(config or {})):
        with mock.patch("set_wallpaper.collect_wallpapers",
                        return_value=list(images or [])):
            app._maybe_show_restore_nudge()


class TestRestoreNudge(unittest.TestCase):

    def test_nudge_appears_for_an_empty_collection(self):
        app = StubApp()
        _show(app)
        self.assertEqual(len(app._restore_nudge.grid_calls), 1)

    def test_nudge_stays_hidden_when_images_exist(self):
        app = StubApp()
        _show(app, images=[Path("a.png")])
        self.assertEqual(app._restore_nudge.grid_calls, [])

    def test_nudge_stays_hidden_after_dismissal(self):
        app = StubApp()
        _show(app, config={"restore_nudge_dismissed": True})
        self.assertEqual(app._restore_nudge.grid_calls, [])

    def test_dismissal_is_persisted(self):
        app = StubApp()
        saved = {}

        with mock.patch("utils.load_config", return_value={"app_theme": "x"}):
            with mock.patch("utils.save_config",
                            side_effect=lambda cfg: saved.update(cfg)):
                app._dismiss_restore_nudge()

        self.assertTrue(saved["restore_nudge_dismissed"])
        self.assertEqual(saved["app_theme"], "x")  # other keys preserved
        self.assertEqual(app._restore_nudge.removed, 1)

    def test_nudge_hides_after_a_successful_restore(self):
        app = StubApp()
        app.load_gallery = lambda: None

        app._on_restore_finished(_FakeResult([Path("restored.png")]))

        self.assertEqual(app._restore_nudge.removed, 1)

    def test_nudge_stays_when_a_restore_wrote_nothing(self):
        app = StubApp()
        app.load_gallery = lambda: None

        app._on_restore_finished(_FakeResult([]))

        self.assertEqual(app._restore_nudge.removed, 0)

    def test_missing_widget_is_tolerated(self):
        app = StubApp()
        app._restore_nudge = None
        _show(app)  # must not raise
        app._hide_restore_nudge()


if __name__ == "__main__":
    unittest.main()
