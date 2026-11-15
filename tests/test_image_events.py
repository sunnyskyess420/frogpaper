"""Phase 1: the image event log has to be trustworthy.

Every generated image is recorded with its eight picks and a source, favourites
and wallpaper sets are counted, and a delete keeps the evidence instead of
throwing it away with the image.
"""

import pathlib
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import database  # noqa: E402
import image_events  # noqa: E402

PARAMS = {
    "subject": "frog",
    "setting": "mountain peak",
    "style": "oil painting",
    "lighting": "golden hour",
    "mood": "epic",
    "atmosphere": "mist",
    "color": "moody sand",
    "mode": "painterly",
}


@unittest.skipUnless(database.DB_AVAILABLE, "sqlalchemy not installed")
class TestImageEvents(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(self._tmp.name)
        self._orig = (database.DB_PATH, database.MIGRATION_MARKER)
        database.shutdown_db()
        database.DB_PATH = root / "test.db"
        database.MIGRATION_MARKER = root / ".migrated"
        database.MIGRATION_MARKER.write_text("", encoding="utf-8")  # skip JSON import
        database.init_db()
        self.db_path = database.DB_PATH
        self.image = root / "frog_painterly_1.png"
        self.image.write_bytes(b"\x89PNG\r\n\x1a\n")  # content is irrelevant

    def tearDown(self):
        database.shutdown_db()
        database.DB_PATH, database.MIGRATION_MARKER = self._orig
        self._tmp.cleanup()

    def rows(self, event=None):
        return [r for r in image_events.counts(self.db_path) if event is None or r["field"]]

    def test_generation_records_every_field(self):
        image_events.log_generation(self.image, PARAMS, source=image_events.SOURCE_MANUAL)
        rows = self.rows()
        self.assertEqual(len(rows), len(image_events.FIELD_KEYS))
        by_field = {r["field"]: r for r in rows}
        self.assertEqual(by_field["subject"]["value"], "frog")
        self.assertEqual(by_field["subject"]["uses"], 1)
        self.assertEqual(by_field["subject"]["source"], "manual")
        self.assertEqual(by_field["mood"]["value"], "epic")

    def test_regenerating_same_path_does_not_double_count(self):
        image_events.log_generation(self.image, PARAMS)
        image_events.log_generation(self.image, PARAMS)
        uses = {r["field"]: r["uses"] for r in self.rows()}
        self.assertEqual(uses["subject"], 1)

    def test_blank_fields_are_recorded_but_empty(self):
        params = dict(PARAMS, mood="")
        image_events.log_generation(self.image, params)
        by_field = {r["field"]: r for r in self.rows()}
        self.assertEqual(by_field["mood"]["value"], "")

    def test_favourites_and_wallpaper_are_counted(self):
        image_events.log_generation(self.image, PARAMS)
        image_events.log_favorite(self.image, added=True)
        image_events.log_favorite(self.image, added=False)
        image_events.log_favorite(self.image, added=True)
        image_events.log_wallpaper(self.image, source="manual")
        by_field = {r["field"]: r for r in self.rows()}
        self.assertEqual(by_field["subject"]["favorites"], 2)
        self.assertEqual(by_field["subject"]["unfavorites"], 1)
        self.assertEqual(by_field["subject"]["wallpaper_sets"], 1)

    def test_delete_keeps_the_evidence(self):
        image_events.log_generation(self.image, PARAMS)
        image_events.log_delete(self.image, PARAMS)
        by_field = {r["field"]: r for r in self.rows()}
        self.assertEqual(by_field["subject"]["uses"], 1)
        self.assertEqual(by_field["subject"]["deletes"], 1)
        self.assertEqual(by_field["setting"]["deletes"], 1)

    def test_counts_can_filter_by_field_and_source(self):
        image_events.log_generation(self.image, PARAMS, source=image_events.SOURCE_STARTUP)
        rows = image_events.counts(self.db_path, field="subject")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], "startup_auto")

    def test_events_are_isolated_per_image(self):
        other = pathlib.Path(self._tmp.name) / "other.png"
        image_events.log_generation(self.image, PARAMS)
        image_events.log_generation(other, dict(PARAMS, subject="owl"))
        by_field = {}
        for row in self.rows():
            by_field.setdefault(row["value"], 0)
            by_field[row["value"]] += row["uses"]
        self.assertEqual(by_field["frog"], 1)
        self.assertEqual(by_field["owl"], 1)

    def test_delete_flow_through_gallery_manager(self):
        """The delete path must snapshot params before the row disappears."""
        try:
            import gallery_manager
        except Exception as exc:  # tkinter missing in this interpreter
            self.skipTest(f"gallery_manager unavailable: {exc}")

        gallery_manager.save_prompt_parameters(self.image, PARAMS)
        gallery_manager.delete_image_and_tags(self.image)

        self.assertFalse(self.image.exists())
        self.assertEqual(gallery_manager.get_prompt_parameters(self.image), {})
        rows = {r["field"]: r for r in self.rows()}
        self.assertEqual(rows["subject"]["deletes"], 1)
        self.assertEqual(rows["subject"]["uses"], 0)  # no generation was logged


if __name__ == "__main__":
    unittest.main(verbosity=2)
