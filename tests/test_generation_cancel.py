"""Cancellation must stop the transfer and never leave a file behind."""
import json
import pathlib
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import wallpaper_generator as wg


class FakeResponse:
    def __init__(self, payload, on_read=None):
        self._left = payload
        self._on_read = on_read
        self.reads = 0

    def read(self, size=-1):
        self.reads += 1
        if self._on_read:
            self._on_read(self.reads)
        if size is None or size < 0:
            out, self._left = self._left, b""
            return out
        out, self._left = self._left[:size], self._left[size:]
        return out


class TestReadBody(unittest.TestCase):
    def test_reads_everything_when_not_cancelled(self):
        payload = b"x" * 100_000
        self.assertEqual(wg._read_body(FakeResponse(payload)), payload)

    def test_raises_when_already_cancelled(self):
        ev = threading.Event()
        ev.set()
        with self.assertRaises(wg.ImageGenerationCancelled):
            wg._read_body(FakeResponse(b"x" * 10), ev)

    def test_raises_mid_stream(self):
        ev = threading.Event()
        body = FakeResponse(b"x" * 300_000, on_read=lambda n: ev.set() if n >= 2 else None)
        with self.assertRaises(wg.ImageGenerationCancelled):
            wg._read_body(body, ev)
        self.assertLess(body.reads, 10)  # stopped early, did not drain the body


class TestSaveImageBytesCancel(unittest.TestCase):
    def test_cancel_writes_nothing(self):
        d = pathlib.Path(tempfile.mkdtemp())
        ev = threading.Event()
        ev.set()
        with self.assertRaises(wg.ImageGenerationCancelled):
            wg.save_image_bytes(d / "a.png", b"y" * 5000, ev)
        self.assertEqual(list(d.iterdir()), [])


class TestGenerateImageHonoursCancel(unittest.TestCase):
    def test_cancelled_before_the_request_writes_nothing(self):
        d = pathlib.Path(tempfile.mkdtemp())
        cfg = d / "config.json"
        cfg.write_text(json.dumps({"provider": "Pollinations.ai (Free - No Key)"}),
                       encoding="utf-8")
        old_cfg, old_dir = wg.CONFIG_FILE, wg.GENERATED_DIR
        wg.CONFIG_FILE, wg.GENERATED_DIR = cfg, d
        try:
            ev = threading.Event()
            ev.set()
            with self.assertRaises(wg.ImageGenerationCancelled):
                wg.generate_image("a test prompt", subject="frog", style="stylized",
                                  cancel_event=ev)
            self.assertEqual([p for p in d.iterdir() if p.suffix == ".png"], [])
        finally:
            wg.CONFIG_FILE, wg.GENERATED_DIR = old_cfg, old_dir


if __name__ == "__main__":
    unittest.main()
