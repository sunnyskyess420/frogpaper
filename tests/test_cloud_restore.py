"""Tests for the cloud_restore planning/execution engine.

Headless and network-free: every test uses a temporary directory as both the
backup source and a throwaway FrogPaper app dir.
"""

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cloud_restore as cr


def _write_image(path, payload=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload if payload is not None else b"\x89PNG\r\n\x1a\n" + path.name.encode())
    return path


class _RestoreTestBase(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.app = root / "app"
        self.app.mkdir()
        self.backup = root / "backup"
        self.backup.mkdir()

    def _plan(self, **kwargs):
        source = cr.LocalFolderSource(self.backup)
        return source, cr.build_plan(source.list_files(), self.app, **kwargs)

    def _run(self, source, plan, **kwargs):
        return cr.RestoreExecutor(source, plan).run(**kwargs)


class TestLocalFolderSource(_RestoreTestBase):

    def test_maps_known_subfolders_and_ignores_other_files(self):
        _write_image(self.backup / "Generated" / "a.png")
        _write_image(self.backup / "Manual" / "b.jpg")
        _write_image(self.backup / "Favorites" / "c.webp")
        (self.backup / "notes.txt").write_text("not an image")

        records = cr.LocalFolderSource(self.backup).list_files()

        by_name = {record.name: record for record in records}
        self.assertEqual(set(by_name), {"a.png", "b.jpg", "c.webp"})
        self.assertEqual(by_name["a.png"].subfolder, "generated")
        self.assertEqual(by_name["b.jpg"].subfolder, "manual")
        self.assertEqual(by_name["c.webp"].subfolder, "favorites")
        self.assertEqual(by_name["a.png"].provider, "local_folder")
        self.assertEqual(
            by_name["a.png"].rel_path, "wallpapers/generated/a.png")

    def test_flat_folder_is_treated_as_manual(self):
        _write_image(self.backup / "lonely.png")
        records = cr.LocalFolderSource(self.backup).list_files()
        self.assertEqual([r.subfolder for r in records], ["manual"])

    def test_missing_folder_raises(self):
        source = cr.LocalFolderSource(self.backup / "nope")
        with self.assertRaises(cr.RestoreError):
            source.list_files()


class TestPlanner(_RestoreTestBase):

    def test_dry_run_does_not_touch_the_disk(self):
        _write_image(self.backup / "Generated" / "a.png")
        _source, plan = self._plan()

        self.assertFalse((self.app / "wallpapers").exists())
        self.assertEqual(plan.counts()[cr.RestoreStatus.MISSING.value], 1)

    def test_missing_file_gets_cloud_subfolder_target(self):
        _write_image(self.backup / "Styled" / "s.png")
        _source, plan = self._plan()
        item = plan.items[0]
        self.assertEqual(item.status, cr.RestoreStatus.MISSING)
        self.assertEqual(
            item.target, self.app / "wallpapers" / "styled" / "s.png")

    def test_identical_file_is_skipped(self):
        _write_image(self.backup / "Manual" / "same.png")
        target = self.app / "wallpapers" / "manual" / "same.png"
        target.parent.mkdir(parents=True)
        target.write_bytes((self.backup / "Manual" / "same.png").read_bytes())

        source, plan = self._plan()
        self.assertEqual(plan.items[0].status, cr.RestoreStatus.IDENTICAL)

        result = self._run(source, plan)
        self.assertEqual(result.written, [])
        self.assertEqual(len(result.skipped), 1)

    def test_same_image_under_another_folder_is_not_restored_twice(self):
        # A backup that stored one picture under both Manual and Generated
        # must not produce a second gallery copy on restore.
        _write_image(self.backup / "Manual" / "dup.png", b"identical-bytes")
        existing = self.app / "wallpapers" / "generated" / "original.png"
        existing.parent.mkdir(parents=True)
        existing.write_bytes(b"identical-bytes")

        source, plan = self._plan()
        item = plan.items[0]
        self.assertEqual(item.status, cr.RestoreStatus.IDENTICAL)
        self.assertEqual(item.target, existing)

        result = self._run(source, plan)
        self.assertEqual(result.written, [])
        self.assertFalse(
            (self.app / "wallpapers" / "manual" / "dup.png").exists())

    def test_favorites_copy_is_still_restored(self):
        # Favorites is a separate view: an identical image there is wanted.
        _write_image(self.backup / "Favorites" / "fav.png", b"identical-bytes")
        existing = self.app / "wallpapers" / "generated" / "original.png"
        existing.parent.mkdir(parents=True)
        existing.write_bytes(b"identical-bytes")

        _source, plan = self._plan()
        item = plan.items[0]
        self.assertEqual(item.status, cr.RestoreStatus.MISSING)
        self.assertEqual(
            item.target, self.app / "wallpapers" / "favorites" / "fav.png")

    def test_conflict_keeps_both_by_default(self):
        _write_image(self.backup / "Manual" / "x.png", b"remote-bytes")
        target = self.app / "wallpapers" / "manual" / "x.png"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"local-bytes")

        source, plan = self._plan()
        item = plan.items[0]
        self.assertEqual(item.status, cr.RestoreStatus.CONFLICT)
        self.assertFalse(item.will_overwrite)
        self.assertNotEqual(item.target, target)

        self._run(source, plan)

        self.assertEqual(target.read_bytes(), b"local-bytes")
        self.assertEqual(item.target.read_bytes(), b"remote-bytes")
        self.assertIn("(restored ", item.target.name)
        self.assertEqual(len(list(target.parent.iterdir())), 2)

    def test_conflict_policy_skip_writes_nothing(self):
        _write_image(self.backup / "Manual" / "x.png", b"remote-bytes")
        target = self.app / "wallpapers" / "manual" / "x.png"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"local-bytes")

        source, plan = self._plan(conflict_policy="skip")
        self.assertIsNone(plan.items[0].target)
        self.assertEqual(plan.pending(), [])

        result = self._run(source, plan)
        self.assertEqual(result.written, [])
        self.assertEqual(target.read_bytes(), b"local-bytes")

    def test_overwrite_only_when_explicitly_requested(self):
        _write_image(self.backup / "Manual" / "x.png", b"remote-bytes")
        target = self.app / "wallpapers" / "manual" / "x.png"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"local-bytes")

        source, plan = self._plan(overwrite=True)
        self.assertTrue(plan.items[0].will_overwrite)

        self._run(source, plan)
        self.assertEqual(target.read_bytes(), b"remote-bytes")
        self.assertEqual(len(list(target.parent.iterdir())), 1)

    def test_invalid_names_are_never_written(self):
        records = [
            cr.RemoteFile("local_folder", "id1", "..", "generated", 3, 0.0, "a" * 64),
            cr.RemoteFile("local_folder", "id2", "a/b.png", "generated", 3, 0.0, "a" * 64),
            cr.RemoteFile("local_folder", "id3", "CON.png", "generated", 3, 0.0, "a" * 64),
            cr.RemoteFile("local_folder", "id4", "notes.txt", "generated", 3, 0.0, "a" * 64),
        ]
        plan = cr.build_plan(records, self.app)
        self.assertEqual(
            [item.status for item in plan.items],
            [cr.RestoreStatus.INVALID] * 4,
        )
        self.assertEqual(plan.pending(), [])
        self.assertFalse((self.app / "wallpapers").exists())

    def test_insufficient_free_space_blocks_writes(self):
        _write_image(self.backup / "Generated" / "big.png", b"x" * 4096)
        _source, plan = self._plan(free_bytes=10)

        self.assertEqual(plan.items[0].status, cr.RestoreStatus.NO_SPACE)
        self.assertEqual(plan.pending(), [])

    def test_unknown_conflict_policy_is_rejected(self):
        with self.assertRaises(ValueError):
            cr.build_plan([], self.app, conflict_policy="clobber")


class TestExecutor(_RestoreTestBase):

    def test_restores_files_in_correct_places(self):
        _write_image(self.backup / "Generated" / "one.png", b"one")
        _write_image(self.backup / "Favorites" / "two.png", b"two")

        source, plan = self._plan()
        result = self._run(source, plan)

        self.assertTrue(result.ok)
        self.assertEqual(len(result.written), 2)
        self.assertEqual(
            (self.app / "wallpapers" / "generated" / "one.png").read_bytes(), b"one")
        self.assertEqual(
            (self.app / "wallpapers" / "favorites" / "two.png").read_bytes(), b"two")

    def test_truncated_source_leaves_no_file_and_no_partial(self):
        _write_image(self.backup / "Manual" / "t.png", b"0123456789")

        class TruncatingSource(cr.LocalFolderSource):
            def fetch(self, remote, dest):
                data = Path(remote.file_id).read_bytes()
                dest.write_bytes(data[:3])

        source = TruncatingSource(self.backup)
        plan = cr.build_plan(source.list_files(), self.app)
        result = self._run(source, plan)

        self.assertEqual(len(result.failures), 1)
        self.assertEqual(result.written, [])
        folder = self.app / "wallpapers" / "manual"
        self.assertEqual(list(folder.iterdir()), [])

    def test_same_size_wrong_content_is_rejected(self):
        _write_image(self.backup / "Manual" / "h.png", b"ABCD")

        class MutatingSource(cr.LocalFolderSource):
            def fetch(self, remote, dest):
                data = bytearray(Path(remote.file_id).read_bytes())
                data[0] ^= 0xFF
                dest.write_bytes(bytes(data))

        source = MutatingSource(self.backup)
        plan = cr.build_plan(source.list_files(), self.app)
        result = self._run(source, plan)

        self.assertEqual(len(result.failures), 1)
        self.assertIn("SHA-256", result.failures[0][1])
        self.assertFalse(
            (self.app / "wallpapers" / "manual" / "h.png").exists())

    def test_cancel_writes_nothing_and_leaves_no_partials(self):
        for index in range(3):
            _write_image(self.backup / "Manual" / f"c{index}.png", b"data")

        source, plan = self._plan()
        cancel = threading.Event()
        cancel.set()
        result = self._run(source, plan, cancel=cancel)

        self.assertTrue(result.cancelled)
        self.assertEqual(result.written, [])
        folders = self.app / "wallpapers"
        leftovers = list(folders.rglob("*.part")) if folders.exists() else []
        self.assertEqual(leftovers, [])

    def test_second_run_is_idempotent(self):
        _write_image(self.backup / "Generated" / "i.png", b"same")
        _write_image(self.backup / "Manual" / "j.png", b"other")

        source, plan = self._plan()
        first = self._run(source, plan)
        self.assertEqual(len(first.written), 2)

        again = cr.build_plan(source.list_files(), self.app)
        second = self._run(source, again)

        self.assertEqual(second.written, [])
        self.assertEqual(
            again.counts()[cr.RestoreStatus.IDENTICAL.value], 2)
        self.assertEqual(
            len(list((self.app / "wallpapers").rglob("*.png"))), 2)

    def test_progress_callback_reports_each_file(self):
        _write_image(self.backup / "Manual" / "p.png", b"p1")
        _write_image(self.backup / "Manual" / "q.png", b"p2")

        source, plan = self._plan()
        seen = []
        self._run(source, plan, progress=lambda i, total, item: seen.append((i, total)))

        self.assertEqual(seen, [(1, 2), (2, 2)])

    def test_restore_log_is_written(self):
        _write_image(self.backup / "Manual" / "log.png", b"payload")
        source, plan = self._plan()
        result = self._run(source, plan)

        self.assertIsNotNone(result.log_path)
        self.assertTrue(result.log_path.exists())
        payload = json.loads(result.log_path.read_text(encoding="utf-8"))
        self.assertEqual(len(payload["written"]), 1)
        self.assertEqual(payload["failures"], [])


class TestUnreadableFiles(_RestoreTestBase):
    """Files the provider lists but refuses to serve (403 appNotAuthorizedToFile).

    Live restore of a real Drive backup hit this on 387 of 632 images: the
    bytes are unreachable, retrying is pointless, and reporting it as a plain
    failure reads like a flaky network. It must be its own outcome.
    """

    def _source_with_forbidden_file(self):
        _write_image(self.backup / "Generated" / "ok.png", b"ok")
        _write_image(self.backup / "Generated" / "no.png", b"no")

        class PartlyForbidden(cr.LocalFolderSource):
            def fetch(self, remote, dest):
                if remote.name == "no.png":
                    raise cr.RemoteAccessError(
                        "Google Drive will not serve this file to FrogPaper.")
                super().fetch(remote, dest)

        return PartlyForbidden(self.backup)

    def test_permission_denied_is_not_counted_as_a_failure(self):
        source = self._source_with_forbidden_file()
        plan = cr.build_plan(source.list_files(), self.app)
        result = self._run(source, plan)

        self.assertEqual(len(result.written), 1)
        self.assertEqual(result.failures, [])
        self.assertEqual(len(result.unreadable), 1)
        self.assertEqual(result.unreadable[0][0].remote.name, "no.png")
        self.assertFalse(result.ok)
        self.assertIn("not readable by this app", result.summary())
        self.assertFalse(
            (self.app / "wallpapers" / "generated" / "no.png").exists())

    def test_unreadable_files_reach_the_restore_log(self):
        source = self._source_with_forbidden_file()
        plan = cr.build_plan(source.list_files(), self.app)
        result = self._run(source, plan)

        payload = json.loads(result.log_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["failures"], [])
        self.assertEqual(len(payload["unreadable"]), 1)
        self.assertEqual(payload["unreadable"][0]["rel_path"],
                         "wallpapers/generated/no.png")
        self.assertIn("not readable by this app", payload["summary"])

    def test_access_denied_classifier(self):
        for message in (
            "HttpError 403 ... reason: appNotAuthorizedToFile",
            "The user has not granted the app 123 read access to the file",
            "ApiError: insufficient_permissions",
            "403 accessDenied",
        ):
            self.assertTrue(cr.is_access_denied_error(RuntimeError(message)),
                            msg=message)
        for message in ("Connection timed out", "429 rate limit exceeded",
                        "HttpError 500 backendError"):
            self.assertFalse(cr.is_access_denied_error(RuntimeError(message)),
                             msg=message)


class TestNameValidation(unittest.TestCase):

    def test_rejects_traversal_and_reserved_names(self):
        for name in ("..", "../x.png", "a/b.png", "CON.png", "lpt1.jpg", ".hidden.png"):
            ok, _reason = cr.is_safe_image_name(name)
            self.assertFalse(ok, msg=name)

    def test_accepts_normal_names(self):
        for name in ("2026-10-19_14-03-22_frog.png", "My Image (2).webp", "x.JPG"):
            ok, reason = cr.is_safe_image_name(name)
            self.assertTrue(ok, msg=f"{name}: {reason}")


if __name__ == "__main__":
    unittest.main()
