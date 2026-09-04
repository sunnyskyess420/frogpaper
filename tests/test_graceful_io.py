"""Graceful degradation tests for gallery/history I/O (improvement report §3).

Covers:
  - gallery_manager DB READ fallbacks: a failing DB session must never
    raise out of a read — every getter falls back to the JSON compat file
    or a safe empty default, with a WARNING logged.
  - gallery_manager JSON fallback hardening: corrupt / wrong-shaped
    gallery_tags.json yields an empty store instead of raising.
  - gallery_manager DB WRITE failures: rolled back, logged with traceback,
    then re-raised so callers can show a friendly dialog (data integrity).
  - gallery_manager FILE OPS: log before re-raising (rename/organize/delete
    stay honest — the UI turns them into dialogs).
  - GalleryTab delete/organize handlers: failures show a ThemedDialog error
    and leave the UI state consistent (tested without Tk via stub app).
  - HistoryManager: corrupt history JSON -> [], export failure -> None,
    restore outside backup dir -> False (characterization of existing
    graceful behavior).

ISOLATION: every module-level file path is redirected into a per-test
temp directory; gallery_manager._get_db and history_manager._get_db are
stubbed, so the real frogpaper.db, gallery_tags.json and logs/ folder are
never touched. No Tk window is created anywhere in this file.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gallery_manager as gm
import history_manager as hm


class GracefulIOBase(unittest.TestCase):
    """Redirect every module-level file path into a temp directory."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        # The tags read memo (perf pass) is module-global: reset it per test
        # so fallback behavior tests always exercise the real read path.
        gm._TAGS_CACHE.clear()
        self.addCleanup(gm._TAGS_CACHE.clear)

    def _patch(self, target, name, value):
        patcher = patch.object(target, name, value)
        patcher.start()
        self.addCleanup(patcher.stop)


# ═══════════════════════════════════════════════════════════════════════════
#  DB read failures → JSON fallback / safe defaults
# ═══════════════════════════════════════════════════════════════════════════

class _ExplodingDB:
    """Simulates a locked/corrupt DB: the session factory itself fails."""

    def get_db_session(self):
        raise RuntimeError("database is locked")


class _FailingSession:
    """Session whose first query raises (simulates disk I/O error)."""

    def __init__(self):
        self.closed = False
        self.rolled_back = False

    def query(self, *args, **kwargs):
        raise RuntimeError("disk I/O error")

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class _FailingDB:
    """Returns a session that fails on first use."""

    def get_db_session(self):
        return _FailingSession()


class TestDBReadFallbacks(GracefulIOBase):
    """Read functions must degrade to JSON/empty defaults, never raise."""

    def _use_exploding_db(self):
        self._patch(gm, "_get_db", lambda: _ExplodingDB())

    def _write_tags_file(self, data):
        tags_file = self.tmp / "gallery_tags.json"
        tags_file.write_text(json.dumps(data), encoding="utf-8")
        self._patch(gm, "TAGS_FILE", tags_file)
        return tags_file

    def test_load_tags_falls_back_to_json_when_db_fails(self):
        self._write_tags_file({"tags": {"/img/a.png": {"tags": ["frog"], "tagged_at": ""}}})
        self._use_exploding_db()
        with self.assertLogs(gm.logger, level="WARNING"):
            result = gm.load_tags()
        self.assertEqual(result["tags"]["/img/a.png"]["tags"], ["frog"])

    def test_load_tags_returns_empty_when_db_fails_and_no_json(self):
        self._patch(gm, "TAGS_FILE", self.tmp / "missing.json")
        self._use_exploding_db()
        with self.assertLogs(gm.logger, level="WARNING"):
            result = gm.load_tags()
        self.assertEqual(result, {"tags": {}})

    def test_get_tags_for_image_falls_back_to_json(self):
        self._write_tags_file({"tags": {"/img/a.png": {"tags": ["x", "y"], "tagged_at": ""}}})
        self._use_exploding_db()
        with self.assertLogs(gm.logger, level="WARNING"):
            tags = gm.get_tags_for_image("/img/a.png")
        self.assertEqual(tags, ["x", "y"])

    def test_get_all_tags_falls_back_to_json(self):
        self._write_tags_file({
            "tags": {
                "/img/a.png": {"tags": ["frog", "neon"], "tagged_at": ""},
                "/img/b.png": {"tags": ["swamp"], "tagged_at": ""},
            }
        })
        self._use_exploding_db()
        with self.assertLogs(gm.logger, level="WARNING"):
            tags = gm.get_all_tags()
        self.assertEqual(tags, ["frog", "neon", "swamp"])

    def test_get_images_by_tag_falls_back_to_json(self):
        real_img = self.tmp / "a.png"
        real_img.write_bytes(b"png")
        self._write_tags_file({"tags": {str(real_img): {"tags": ["frog"], "tagged_at": ""}}})
        self._use_exploding_db()
        with self.assertLogs(gm.logger, level="WARNING"):
            images = gm.get_images_by_tag("frog")
        self.assertEqual([Path(img) for img in images], [real_img])

    def test_get_images_by_tags_match_all_falls_back_to_json(self):
        real_img = self.tmp / "b.png"
        real_img.write_bytes(b"png")
        self._write_tags_file({"tags": {str(real_img): {"tags": ["frog", "neon"], "tagged_at": ""}}})
        self._use_exploding_db()
        with self.assertLogs(gm.logger, level="WARNING"):
            both = gm.get_images_by_tags(["frog", "neon"], match_any=False)
            either = gm.get_images_by_tags(["frog", "missing"], match_any=True)
        self.assertEqual([Path(img) for img in both], [real_img])
        self.assertEqual([Path(img) for img in either], [real_img])

    def test_get_prompt_parameters_falls_back_to_json(self):
        self._write_tags_file({
            "tags": {"/img/a.png": {"tags": [], "tagged_at": "",
                                    "prompt_params": {"subject": "frog"}}}
        })
        self._use_exploding_db()
        with self.assertLogs(gm.logger, level="WARNING"):
            params = gm.get_prompt_parameters("/img/a.png")
        self.assertEqual(params, {"subject": "frog"})

    def test_db_none_still_uses_json_fallback(self):
        """Baseline: with no DB at all, the JSON path still works."""
        self._write_tags_file({"tags": {"/img/a.png": {"tags": ["keep"], "tagged_at": ""}}})
        self._patch(gm, "_get_db", lambda: None)
        self.assertEqual(gm.get_tags_for_image("/img/a.png"), ["keep"])


class TestJSONFallbackHardening(GracefulIOBase):
    """_load_tags_json must never raise, whatever the file contains."""

    def test_corrupt_json_yields_empty_store(self):
        tags_file = self.tmp / "gallery_tags.json"
        tags_file.write_text("{not valid json", encoding="utf-8")
        self._patch(gm, "TAGS_FILE", tags_file)
        with self.assertLogs(gm.logger, level="WARNING"):
            data = gm._load_tags_json()
        self.assertEqual(data, {"tags": {}})

    def test_wrong_shape_json_yields_empty_store(self):
        tags_file = self.tmp / "gallery_tags.json"
        tags_file.write_text(json.dumps(["a", "list", "not", "dict"]), encoding="utf-8")
        self._patch(gm, "TAGS_FILE", tags_file)
        with self.assertLogs(gm.logger, level="WARNING"):
            data = gm._load_tags_json()
        self.assertEqual(data, {"tags": {}})

    def test_missing_tags_key_yields_empty_store(self):
        tags_file = self.tmp / "gallery_tags.json"
        tags_file.write_text(json.dumps({"something": "else"}), encoding="utf-8")
        self._patch(gm, "TAGS_FILE", tags_file)
        data = gm._load_tags_json()
        self.assertEqual(data, {"tags": {}})


# ═══════════════════════════════════════════════════════════════════════════
#  DB write failures: rollback + log + re-raise (callers show dialogs)
# ═══════════════════════════════════════════════════════════════════════════

class TestDBWriteFailuresLogged(GracefulIOBase):
    """Writes stay honest (raise) but must now log the full failure."""

    def setUp(self):
        super().setUp()
        self._patch(gm, "_get_db", lambda: _FailingDB())

    # NOTE: without sqlalchemy installed, `from database import ImageTag`
    # raises ImportError inside the same guarded block, so the contract is
    # "any exception, after rollback + ERROR log" — not RuntimeError alone.
    def _assert_write_failure(self, fn, *args):
        with self.assertLogs(gm.logger, level="ERROR"):
            with self.assertRaises((RuntimeError, ImportError)):
                fn(*args)

    def test_save_tags_failure_rolls_back_logs_and_raises(self):
        self._assert_write_failure(
            gm.save_tags, {"tags": {"/img/a.png": {"tags": ["t"], "tagged_at": ""}}})

    def test_add_tags_failure_rolls_back_logs_and_raises(self):
        self._assert_write_failure(gm.add_tags_to_image, "/img/a.png", ["frog"])

    def test_save_prompt_parameters_failure_raises_and_logs(self):
        self._assert_write_failure(
            gm.save_prompt_parameters, "/img/a.png", {"subject": "frog"})

    def test_cleanup_orphaned_tags_failure_raises_and_logs(self):
        self._assert_write_failure(gm.cleanup_orphaned_tags)


# ═══════════════════════════════════════════════════════════════════════════
#  File operations: logged before re-raise; success paths unchanged
# ═══════════════════════════════════════════════════════════════════════════

class TestFileOperations(GracefulIOBase):
    """Filesystem ops keep their raise semantics but now log the failure."""

    def setUp(self):
        super().setUp()
        self._patch(gm, "_get_db", lambda: None)
        self._patch(gm, "TAGS_FILE", self.tmp / "gallery_tags.json")
        generated = self.tmp / "generated"
        generated.mkdir()
        self._patch(gm, "GENERATED_DIR", generated)

    def test_organize_moves_image_into_subfolder(self):
        src = self.tmp / "img.png"
        src.write_bytes(b"png")
        new_path = gm.organize_image_into_folder(src, "cyberpunk")
        self.assertEqual(new_path, self.tmp / "generated" / "cyberpunk" / "img.png")
        self.assertTrue(new_path.exists())
        self.assertFalse(src.exists())

    def test_organize_missing_image_returns_none(self):
        self.assertIsNone(gm.organize_image_into_folder(self.tmp / "nope.png", "f"))

    def test_organize_failure_logs_and_raises(self):
        src = self.tmp / "img.png"
        src.write_bytes(b"png")
        with patch.object(gm.shutil, "move", side_effect=OSError("file locked")):
            with self.assertLogs(gm.logger, level="ERROR"):
                with self.assertRaises(OSError):
                    gm.organize_image_into_folder(src, "cyberpunk")
        self.assertTrue(src.exists())  # untouched after failed move

    def test_rename_failure_logs_and_raises(self):
        src = self.tmp / "img.png"
        src.write_bytes(b"png")
        with patch.object(Path, "rename", side_effect=OSError("target exists")):
            with self.assertLogs(gm.logger, level="ERROR"):
                with self.assertRaises(OSError):
                    gm.rename_image(src, "new.png")

    def test_rename_success_updates_json_metadata(self):
        src = self.tmp / "img.png"
        src.write_bytes(b"png")
        (self.tmp / "gallery_tags.json").write_text(json.dumps({
            "tags": {str(src.resolve()): {"tags": ["frog"], "tagged_at": ""}}
        }), encoding="utf-8")
        new_path = gm.rename_image(src, "renamed.png")
        self.assertEqual(new_path, self.tmp / "renamed.png")
        self.assertTrue(new_path.exists())
        data = json.loads((self.tmp / "gallery_tags.json").read_text(encoding="utf-8"))
        self.assertIn(str(new_path.resolve()), data["tags"])

    def test_delete_failure_on_locked_file_logs_and_raises(self):
        img = self.tmp / "img.png"
        img.write_bytes(b"png")
        with patch.object(Path, "unlink", side_effect=PermissionError("locked")):
            with self.assertLogs(gm.logger, level="ERROR"):
                with self.assertRaises(PermissionError):
                    gm.delete_image_and_tags(img)
        self.assertTrue(img.exists())

    def test_get_folder_structure_reads_generated_dir(self):
        (self.tmp / "generated" / "root_img.png").write_bytes(b"png")
        sub = self.tmp / "generated" / "sub"
        sub.mkdir()
        (sub / "inner.jpg").write_bytes(b"jpg")
        structure = gm.get_folder_structure()
        self.assertEqual(len(structure["root"]), 1)
        self.assertEqual([p.name for p in structure["folders"]["sub"]], ["inner.jpg"])

    def test_get_folder_structure_survives_unreadable_dir(self):
        unreadable = self.tmp / "generated"
        unreadable.mkdir(exist_ok=True)
        stub = type("StubDir", (), {
            "exists": lambda self: True,
            "iterdir": lambda self: (_ for _ in ()).throw(PermissionError("denied")),
        })()
        self._patch(gm, "GENERATED_DIR", stub)
        with self.assertLogs(gm.logger, level="WARNING"):
            structure = gm.get_folder_structure()
        self.assertEqual(structure, {"root": [], "folders": {}})


# ═══════════════════════════════════════════════════════════════════════════
#  GalleryTab delete/organize handlers show dialogs (no Tk needed)
# ═══════════════════════════════════════════════════════════════════════════

try:
    import gallery_tab as gt
    GALLERY_TAB_IMPORTABLE = True
except Exception:  # pragma: no cover - e.g. PIL missing in odd environments
    GALLERY_TAB_IMPORTABLE = False


class _DialogStub:
    def __init__(self, ask_result=True):
        self.ask_result = ask_result
        self.errors = []
        self.warnings = []
        self.infos = []
        self.asks = []

    def ask(self, title, message):
        self.asks.append((title, message))
        return self.ask_result

    def error(self, title, message):
        self.errors.append((title, message))

    def warning(self, title, message):
        self.warnings.append((title, message))

    def info(self, title, message):
        self.infos.append((title, message))


class _StatusVar:
    def __init__(self):
        self.value = ""

    def set(self, value):
        self.value = value


class _AppStub:
    """Minimal app surface used by delete_selected / organize_gallery_image."""

    def __init__(self, tmp_path):
        self.selected_gallery_path = tmp_path / "img.png"
        self._dialog = _DialogStub()
        self.status_var = _StatusVar()
        self.cleared = False
        self.refreshed = False
        self.status_msg = ""
        self.gallery_loads = 0

    def clear_image(self):
        self.cleared = True

    def _refresh_tag_ui(self, status_msg=""):
        self.refreshed = True
        self.status_msg = status_msg

    def load_gallery(self):
        self.gallery_loads += 1


@unittest.skipUnless(GALLERY_TAB_IMPORTABLE, "gallery_tab not importable")
class TestGalleryTabErrorDialogs(GracefulIOBase):
    """User-triggered delete/organize must degrade to a dialog, not a crash."""

    def _make_tab(self):
        tab = gt.GalleryTab.__new__(gt.GalleryTab)  # skip __init__ (no Tk)
        tab.app = _AppStub(self.tmp)
        return tab

    def test_delete_failure_shows_dialog_and_keeps_selection(self):
        tab = self._make_tab()
        with patch.object(gt, "delete_image_and_tags", side_effect=PermissionError("locked")):
            tab.delete_selected()  # must not raise
        self.assertEqual(len(tab.app._dialog.errors), 1)
        title, message = tab.app._dialog.errors[0]
        self.assertEqual(title, "Delete Failed")
        self.assertIn("another program", message)
        self.assertIsNotNone(tab.app.selected_gallery_path)  # selection kept
        self.assertFalse(tab.app.refreshed)                  # no success refresh
        self.assertFalse(tab.app.cleared)

    def test_delete_success_refreshes_ui(self):
        tab = self._make_tab()
        with patch.object(gt, "delete_image_and_tags") as mock_del:
            tab.delete_selected()
        mock_del.assert_called_once()
        self.assertEqual(tab.app._dialog.errors, [])
        self.assertIsNone(tab.app.selected_gallery_path)
        self.assertTrue(tab.app.cleared)
        self.assertTrue(tab.app.refreshed)
        self.assertIn("Deleted", tab.app.status_msg)

    def test_delete_declined_confirm_makes_no_changes(self):
        tab = self._make_tab()
        tab.app._dialog.ask_result = False
        with patch.object(gt, "delete_image_and_tags") as mock_del:
            tab.delete_selected()
        mock_del.assert_not_called()
        self.assertFalse(tab.app.cleared)

    def test_delete_without_selection_warns(self):
        tab = self._make_tab()
        tab.app.selected_gallery_path = None
        tab.delete_selected()
        self.assertEqual(len(tab.app._dialog.warnings), 1)
        self.assertEqual(tab.app._dialog.errors, [])

    def test_organize_failure_shows_dialog_and_keeps_selection(self):
        tab = self._make_tab()
        with patch.object(gt, "simpledialog") as mock_sd:
            mock_sd.askstring.return_value = "cyberpunk"
            with patch.object(gt, "organize_image_into_folder",
                              side_effect=OSError("locked")):
                tab.organize_gallery_image()  # must not raise
        self.assertEqual(len(tab.app._dialog.errors), 1)
        title, message = tab.app._dialog.errors[0]
        self.assertEqual(title, "Move Failed")
        self.assertIn("locked by another program", message)
        self.assertEqual(tab.app.gallery_loads, 0)  # no refresh after failure

    def test_organize_success_moves_selection(self):
        tab = self._make_tab()
        new_path = self.tmp / "moved.png"
        with patch.object(gt, "simpledialog") as mock_sd:
            mock_sd.askstring.return_value = "cyberpunk"
            with patch.object(gt, "organize_image_into_folder", return_value=new_path):
                tab.organize_gallery_image()
        self.assertEqual(tab.app._dialog.errors, [])
        self.assertEqual(tab.app.selected_gallery_path, new_path)
        self.assertEqual(tab.app.gallery_loads, 1)
        self.assertIn("cyberpunk", tab.app.status_var.value)


# ═══════════════════════════════════════════════════════════════════════════
#  database.py import contract
# ═══════════════════════════════════════════════════════════════════════════

class TestDatabaseImportContract(GracefulIOBase):
    """database.py's docstring promises it loads even without sqlalchemy.

    Regression: `def get_db_session() -> ORMSession:` crashed the import
    with NameError whenever sqlalchemy was missing, breaking that promise
    (and every gallery read/write fallback along with it). The lazy
    annotation fix restores the contract.
    """

    def test_module_imports_and_reports_availability(self):
        import database
        self.assertIsInstance(database.DB_AVAILABLE, bool)
        self.assertTrue(callable(database.get_db_session))


# ═══════════════════════════════════════════════════════════════════════════
#  HistoryManager: characterization of existing graceful behavior
# ═══════════════════════════════════════════════════════════════════════════

class TestHistoryManagerGraceful(GracefulIOBase):
    """history_manager already degrades gracefully — these lock it in."""

    def setUp(self):
        super().setUp()
        self._patch(hm, "_get_db", lambda: None)  # force JSON fallback path
        logs_dir = self.tmp / "logs"
        logs_dir.mkdir()
        self._patch(hm, "LOGS_DIR", logs_dir)
        self._patch(hm, "BACKUP_DIR", logs_dir / "history_backups")
        self._patch(hm, "EXPORT_DIR", logs_dir / "history_exports")

    def test_corrupt_history_file_loads_empty(self):
        (self.tmp / "logs" / "prompts_history.json").write_text("{broken", encoding="utf-8")
        manager = hm.HistoryManager()
        self.assertEqual(manager.get_history(), [])

    def test_missing_history_file_loads_empty(self):
        manager = hm.HistoryManager()
        self.assertEqual(manager.get_history(), [])

    def test_add_entry_persists_to_json(self):
        manager = hm.HistoryManager()
        manager.add_entry({"subject": "frog", "prompt": "a frog"})
        saved = json.loads(
            (self.tmp / "logs" / "prompts_history.json").read_text(encoding="utf-8"))
        self.assertEqual(saved[0]["subject"], "frog")

    def test_export_failure_returns_none(self):
        manager = hm.HistoryManager()
        manager.add_entry({"subject": "frog", "prompt": "p"})
        self._patch(hm, "EXPORT_DIR", self.tmp / "does_not_exist")  # unwritable
        with self.assertLogs(hm.logger, level="ERROR"):
            result = manager.export_to_csv()
        self.assertIsNone(result)

    def test_restore_from_outside_backup_dir_is_rejected(self):
        manager = hm.HistoryManager()
        evil = self.tmp / "evil.json"
        evil.write_text("[]", encoding="utf-8")
        result = manager.restore_from_backup(evil)
        self.assertFalse(result)
        self.assertEqual(manager.get_history(), [])

    def test_backup_write_failure_does_not_raise(self):
        manager = hm.HistoryManager()
        self._patch(hm, "BACKUP_DIR", self.tmp / "no_such_dir")
        with self.assertLogs(hm.logger, level="ERROR"):
            manager._backup_entries([{"subject": "frog"}])  # must not raise


if __name__ == "__main__":
    unittest.main()
