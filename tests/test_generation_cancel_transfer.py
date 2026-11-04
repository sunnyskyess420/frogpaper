"""Cancel must abort an in-flight provider transfer, not just the UI."""
import pathlib
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import wallpaper_generator as wg


class SlowResponse:
    """Endless 200 OK body — without cancellation this never returns."""

    status = 200
    headers = {}

    def read(self, size=-1):
        time.sleep(0.02)
        return b"x" * 1024

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class TestProviderHonoursCancel(unittest.TestCase):
    def test_pollinations_aborts_a_slow_transfer(self):
        out = pathlib.Path(tempfile.mkdtemp()) / "big.png"
        ev = threading.Event()
        threading.Timer(0.3, ev.set).start()

        started = time.time()
        with patch("urllib.request.urlopen", return_value=SlowResponse()):
            with self.assertRaises(wg.ImageGenerationCancelled):
                wg._generate_pollinations("a prompt", "flux", 64, 64, out, None, ev)
        elapsed = time.time() - started

        self.assertLess(elapsed, 5, "cancel did not interrupt the download")
        self.assertFalse(out.exists(), "a cancelled transfer left a file")


if __name__ == "__main__":
    unittest.main()
