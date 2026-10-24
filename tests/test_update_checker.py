"""Tests for the one-click auto-update helpers in update_checker.py.

Covers:
  - version parsing/comparison (parse_version / is_newer)
  - installer URL detection (is_installer_url)
  - GitHub release asset selection in check_for_update (direct installer
    download_url + size, website fallback, skipped-version suppression)
  - download_installer streaming: success, progress reporting, cancellation,
    corrupt/short payload rejection, URL errors, filename derivation

ISOLATION: every module-level file path is redirected into a per-test temp
directory and urllib is stubbed, so no network access happens and the real
config.json / installer files are never touched. No Tk window is created.
"""

import io
import sys
import tempfile
import threading
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import update_checker as uc


class _FakeResponse(io.BytesIO):
    """Minimal stand-in for the object returned by urllib.request.urlopen()."""

    def __init__(self, payload: bytes, content_length=None):
        super().__init__(payload)
        self.headers = {}
        if content_length is not None:
            self.headers["Content-Length"] = str(content_length)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def _installer_payload(size: int = uc.MIN_INSTALLER_BYTES + 64) -> bytes:
    return b"P" * size


# ═══════════════════════════════════════════════════════════════════════════
#  Version + URL helpers
# ═══════════════════════════════════════════════════════════════════════════

class TestVersionHelpers(unittest.TestCase):

    def test_parse_version_strips_v_prefix(self):
        self.assertEqual(uc.parse_version("v1.2.3"), (1, 2, 3))
        self.assertEqual(uc.parse_version("1.6.1"), (1, 6, 1))

    def test_parse_version_pads_short_versions(self):
        self.assertEqual(uc.parse_version("1.6"), (1, 6, 0))
        self.assertEqual(uc.parse_version("2"), (2, 0, 0))

    def test_parse_version_non_numeric_becomes_zero(self):
        self.assertEqual(uc.parse_version("vX.Y.Z"), (0, 0, 0))

    def test_is_newer(self):
        self.assertTrue(uc.is_newer("1.6.2", "1.6.1"))
        self.assertTrue(uc.is_newer("v2.0.0", "1.9.9"))
        self.assertFalse(uc.is_newer("1.6.1", "1.6.1"))
        self.assertFalse(uc.is_newer("1.6", "1.6.1"))
        self.assertFalse(uc.is_newer("", "1.6.1"))


class TestIsInstallerUrl(unittest.TestCase):

    def test_accepts_direct_exe(self):
        self.assertTrue(uc.is_installer_url("https://github.com/x/y/FrogPaper-Setup-2.0.exe"))

    def test_accepts_exe_with_query_string(self):
        self.assertTrue(uc.is_installer_url("https://objects.example.com/FrogPaper-Setup.exe?token=abc"))

    def test_accepts_exe_with_fragment(self):
        self.assertTrue(uc.is_installer_url("https://example.com/a.exe#download"))

    def test_accepts_http(self):
        self.assertTrue(uc.is_installer_url("http://example.com/a.exe"))

    def test_rejects_website_page(self):
        self.assertFalse(uc.is_installer_url("https://sunnyskyess420.github.io/frogpaper-website/#downloads"))

    def test_rejects_release_html_page(self):
        self.assertFalse(uc.is_installer_url("https://github.com/x/y/releases/tag/v1.6.2"))

    def test_rejects_non_http_scheme(self):
        self.assertFalse(uc.is_installer_url("ftp://example.com/a.exe"))

    def test_rejects_empty(self):
        self.assertFalse(uc.is_installer_url(""))


class TestFormatSize(unittest.TestCase):

    def test_formats_bytes_kb_mb(self):
        self.assertEqual(uc._format_size(512), "512 B")
        self.assertEqual(uc._format_size(2048), "2.0 KB")
        self.assertEqual(uc._format_size(5 * 1024 * 1024), "5.0 MB")

    def test_handles_bad_input(self):
        self.assertEqual(uc._format_size(None), "?")


# ═══════════════════════════════════════════════════════════════════════════
#  check_for_update asset selection
# ═══════════════════════════════════════════════════════════════════════════

def _release(tag="v9.9.9", assets=None, body="", name=None):
    return {
        "tag_name": tag,
        "name": name or tag,
        "body": body,
        "html_url": f"https://github.com/x/y/releases/tag/{tag}",
        "assets": assets or [],
    }


class TestCheckForUpdateAssetSelection(unittest.TestCase):

    def _check(self, release):
        with patch.object(uc, "fetch_latest_release", return_value=release), \
                patch.object(uc, "get_skipped_version", return_value=""):
            return uc.check_for_update("1.6.1")

    def test_picks_setup_exe_asset_and_size(self):
        url = "https://github.com/x/y/releases/download/v9.9.9/FrogPaper-Setup-9.9.9.exe"
        result = self._check(_release(assets=[
            {"name": "FrogPaper-portable.exe", "browser_download_url": "https://x/portable.exe", "size": 10},
            {"name": "source.zip", "browser_download_url": "https://x/source.zip", "size": 20},
            {"name": "FrogPaper-Setup-9.9.9.exe", "browser_download_url": url, "size": 42424242},
        ]))
        self.assertEqual(result["download_url"], url)
        self.assertEqual(result["download_size"], 42424242)

    def test_falls_back_to_website_when_no_setup_asset(self):
        result = self._check(_release(assets=[
            {"name": "FrogPaper-portable.exe", "browser_download_url": "https://x/portable.exe", "size": 10},
        ]))
        self.assertEqual(result["download_url"], uc.DOWNLOADS_URL)
        self.assertEqual(result["download_size"], 0)

    def test_falls_back_to_website_when_no_assets_key(self):
        result = self._check(_release())
        self.assertEqual(result["download_url"], uc.DOWNLOADS_URL)

    def test_returns_none_when_not_newer(self):
        with patch.object(uc, "fetch_latest_release", return_value=_release(tag="v1.6.1")):
            self.assertIsNone(uc.check_for_update("1.6.1"))

    def test_returns_none_when_fetch_fails(self):
        with patch.object(uc, "fetch_latest_release", return_value=None):
            self.assertIsNone(uc.check_for_update("1.6.1"))

    def test_returns_none_when_latest_is_skipped(self):
        with patch.object(uc, "fetch_latest_release", return_value=_release(tag="v9.9.9")), \
                patch.object(uc, "get_skipped_version", return_value="v9.9.9"):
            self.assertIsNone(uc.check_for_update("1.6.1"))

    def test_body_is_cleaned_and_truncated(self):
        body = "# Changelog\n\n**New**: one\n- two\n- three\n- four\n- five\n- six\n\nignored"
        result = self._check(_release(body=body))
        self.assertLessEqual(len(result["body"].split("\n")), 5)
        self.assertNotIn("**", result["body"])
        self.assertNotIn("#", result["body"])


# ═══════════════════════════════════════════════════════════════════════════
#  download_installer
# ═══════════════════════════════════════════════════════════════════════════

class TestDownloadInstaller(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _download(self, url, payload, **kwargs):
        resp = _FakeResponse(payload, content_length=len(payload))
        with patch.object(uc.urllib.request, "urlopen", return_value=resp):
            return uc.download_installer(url, self.tmp, **kwargs)

    def test_downloads_file_and_reports_progress(self):
        payload = _installer_payload()
        calls = []
        result = self._download(
            "https://example.com/FrogPaper-Setup-2.0.exe", payload,
            progress_cb=lambda done, total: calls.append((done, total)),
        )
        self.assertEqual(result, self.tmp / "FrogPaper-Setup-2.0.exe")
        self.assertEqual(result.stat().st_size, len(payload))
        self.assertTrue(calls)
        self.assertEqual(calls[-1], (len(payload), len(payload)))
        # progress is monotonically non-decreasing
        self.assertEqual([c[0] for c in calls], sorted(c[0] for c in calls))

    def test_reports_zero_total_when_header_missing(self):
        payload = _installer_payload()
        calls = []
        resp = _FakeResponse(payload)  # no Content-Length
        with patch.object(uc.urllib.request, "urlopen", return_value=resp):
            uc.download_installer(
                "https://example.com/FrogPaper-Setup-2.0.exe", self.tmp,
                progress_cb=lambda done, total: calls.append((done, total)),
            )
        self.assertEqual(calls[-1][1], 0)

    def test_strips_query_string_from_filename(self):
        result = self._download(
            "https://objects.example.com/FrogPaper-Setup.exe?sig=abc123", _installer_payload())
        self.assertEqual(result.name, "FrogPaper-Setup.exe")

    def test_rejects_non_exe_url_without_network(self):
        with patch.object(uc.urllib.request, "urlopen") as mock_open:
            with self.assertRaises(ValueError):
                uc.download_installer("https://example.com/page.html", self.tmp)
        mock_open.assert_not_called()

    def test_cancelled_download_removes_partial_file(self):
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(uc.DownloadCancelled):
            self._download(
                "https://example.com/FrogPaper-Setup-2.0.exe", _installer_payload(),
                cancel_event=cancel,
            )
        self.assertEqual(list(self.tmp.iterdir()), [])

    def test_short_payload_is_rejected_and_removed(self):
        with self.assertRaises(OSError):
            self._download(
                "https://example.com/FrogPaper-Setup-2.0.exe", b"<html>404</html>")
        self.assertEqual(list(self.tmp.iterdir()), [])

    def test_url_error_is_wrapped_as_oserror(self):
        with patch.object(uc.urllib.request, "urlopen",
                          side_effect=urllib.error.URLError("no network")):
            with self.assertRaises(OSError):
                uc.download_installer("https://example.com/FrogPaper-Setup-2.0.exe", self.tmp)
        self.assertEqual(list(self.tmp.iterdir()), [])

    def test_creates_missing_destination_dir(self):
        nested = self.tmp / "nested" / "deeper"
        resp = _FakeResponse(_installer_payload(), content_length=uc.MIN_INSTALLER_BYTES + 64)
        with patch.object(uc.urllib.request, "urlopen", return_value=resp):
            result = uc.download_installer(
                "https://example.com/FrogPaper-Setup.exe", nested)
        self.assertTrue(result.exists())
        self.assertEqual(result.parent, nested)


# ═══════════════════════════════════════════════════════════════════════════
#  spawn_installer_after_exit (detached launch handoff)
# ═══════════════════════════════════════════════════════════════════════════

class TestSpawnInstallerAfterExit(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_missing_installer_returns_false(self):
        with patch.object(uc.subprocess, "Popen") as mock_popen:
            self.assertFalse(uc.spawn_installer_after_exit(self.tmp / "nope.exe"))
        mock_popen.assert_not_called()

    def test_windows_helper_waits_for_pid_then_launches_installer(self):
        installer = self.tmp / "FrogPaper-Setup-2.0.exe"
        installer.write_bytes(b"MZ")
        bat = Path(tempfile.gettempdir()) / "frogpaper_update_launch.bat"
        self.addCleanup(lambda: bat.unlink(missing_ok=True))

        with patch.object(uc.sys, "platform", "win32"), \
                patch.object(uc.subprocess, "Popen") as mock_popen:
            ok = uc.spawn_installer_after_exit(installer)

        self.assertTrue(ok)
        mock_popen.assert_called_once()
        argv = mock_popen.call_args.args[0]
        self.assertEqual(argv[:2], ["cmd", "/c"])

        script = bat.read_text(encoding="utf-8")
        self.assertIn(f'PID eq {uc.os.getpid()}', script)   # waits for this process
        self.assertIn(str(installer), script)               # then runs the installer
        self.assertIn("start", script)
        self.assertIn("goto wait", script)


# ═══════════════════════════════════════════════════════════════════════════
#  show_update_notification / start_update_install orchestration
# ═══════════════════════════════════════════════════════════════════════════

class _DialogStub:
    def __init__(self, choice="Not Now"):
        self.choice = choice
        self.shown = []
        self.infos = []
        self.warnings = []
        self.errors = []

    def _show(self, kind, title, message, buttons=("OK",), primary=None):
        self.shown.append((kind, title, message, buttons, primary))
        return self.choice

    def info(self, title, message):
        self.infos.append((title, message))

    def warning(self, title, message):
        self.warnings.append((title, message))

    def error(self, title, message):
        self.errors.append((title, message))


class _AppStub:
    def __init__(self, choice="Not Now"):
        self._dialog = _DialogStub(choice)


def _release_info(url="https://x/FrogPaper-Setup-2.0.exe", size=1000, tag="v2.0.0"):
    return {
        "tag_name": tag,
        "name": f"FrogPaper {tag}",
        "html_url": f"https://github.com/x/y/releases/tag/{tag}",
        "body": "notes",
        "download_url": url,
        "download_size": size,
    }


class TestShowUpdateNotification(unittest.TestCase):

    def test_install_update_starts_auto_install(self):
        app = _AppStub(choice="Install Update")
        release = _release_info()
        with patch.object(uc, "start_update_install") as mock_start:
            uc.show_update_notification(app, release)
        mock_start.assert_called_once_with(app, release)
        # The popup exposed an explicit, primary "Install Update" button.
        _kind, _title, _msg, buttons, primary = app._dialog.shown[0]
        self.assertIn("Install Update", buttons)
        self.assertEqual(primary, "Install Update")

    def test_skip_records_version_and_informs_user(self):
        app = _AppStub(choice="Skip This Version")
        with patch.object(uc, "skip_version") as mock_skip, \
                patch.object(uc, "start_update_install") as mock_start:
            uc.show_update_notification(app, _release_info(tag="v2.0.0"))
        mock_skip.assert_called_once_with("v2.0.0")
        mock_start.assert_not_called()
        self.assertTrue(app._dialog.infos)

    def test_not_now_does_nothing(self):
        app = _AppStub(choice="Not Now")
        with patch.object(uc, "skip_version") as mock_skip, \
                patch.object(uc, "start_update_install") as mock_start:
            uc.show_update_notification(app, _release_info())
        mock_start.assert_not_called()
        mock_skip.assert_not_called()


class TestStartUpdateInstall(unittest.TestCase):

    def test_source_run_opens_browser_instead_of_installing(self):
        app = _AppStub()
        with patch.object(uc, "open_in_browser") as mock_open, \
                patch.object(uc, "download_installer") as mock_dl:
            uc.start_update_install(app, _release_info())  # frozen is False here
        mock_open.assert_called_once()
        mock_dl.assert_not_called()

    def test_missing_installer_asset_opens_browser(self):
        app = _AppStub()
        release = _release_info(url=uc.DOWNLOADS_URL)
        with patch.object(uc.sys, "frozen", True, create=True), \
                patch.object(uc, "open_in_browser") as mock_open, \
                patch.object(uc, "download_installer") as mock_dl:
            uc.start_update_install(app, release)
        mock_open.assert_called_once_with(release["html_url"])
        mock_dl.assert_not_called()

    def test_frozen_run_opens_release_page_without_downloading(self):
        app = _AppStub()
        release = _release_info()
        with patch.object(uc.sys, "frozen", True, create=True), \
                patch.object(uc, "open_in_browser") as mock_open, \
                patch.object(uc, "download_installer") as mock_dl, \
                patch.object(uc, "run_background") as mock_bg:
            uc.start_update_install(app, release)
        mock_open.assert_called_once_with(release["html_url"])
        mock_dl.assert_not_called()
        mock_bg.assert_not_called()
    

    def test_download_failed_warns_and_opens_browser(self):
        app = _AppStub()
        release = _release_info()
        with patch.object(uc, "open_in_browser") as mock_open:
            uc._download_failed(app, release, "no network")
        self.assertTrue(app._dialog.warnings)
        mock_open.assert_called_once_with(release["html_url"])


# ═══════════════════════════════════════════════════════════════════════════
#  ThemedDialog primary-button mapping (used by the update popup)
# ═══════════════════════════════════════════════════════════════════════════

try:
    from app import resolve_dialog_buttons
    _APP_IMPORTABLE = True
except Exception:  # pragma: no cover - e.g. tkinter missing in odd environments
    _APP_IMPORTABLE = False


@unittest.skipUnless(_APP_IMPORTABLE, "app not importable")
class TestDialogButtonMapping(unittest.TestCase):

    def test_default_keeps_historical_behaviour(self):
        """Without a primary, the last button is styled and the first is Enter."""
        primary_label, return_label = resolve_dialog_buttons(("Yes", "Skip", "No"))
        self.assertEqual(primary_label, "No")
        self.assertEqual(return_label, "Yes")

    def test_explicit_primary_drives_style_and_enter(self):
        primary_label, return_label = resolve_dialog_buttons(
            ("Install Update", "Skip This Version", "Not Now"),
            primary="Install Update",
        )
        self.assertEqual(primary_label, "Install Update")
        self.assertEqual(return_label, "Install Update")

    def test_unknown_primary_falls_back_to_historical_behaviour(self):
        primary_label, return_label = resolve_dialog_buttons(("OK",), primary="Bogus")
        self.assertEqual(primary_label, "OK")
        self.assertEqual(return_label, "OK")


if __name__ == "__main__":
    unittest.main()
