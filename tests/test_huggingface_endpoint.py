"""Hugging Face must call a host that still exists.

The legacy `api-inference.huggingface.co` host was retired and no longer
resolves in DNS, so every request failed before the token was even read - which
is why valid tokens "did not work". Serverless inference now goes through
router.huggingface.co.
"""

import json
import pathlib
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import wallpaper_generator as wg


class TestEndpoint(unittest.TestCase):
    def test_uses_the_router_host(self):
        url = wg.huggingface_endpoint("black-forest-labs/FLUX.1-schnell")
        self.assertTrue(url.startswith("https://router.huggingface.co/hf-inference/models/"))
        self.assertTrue(url.endswith("black-forest-labs/FLUX.1-schnell"))

    def test_defaults_when_model_is_blank(self):
        self.assertIn("stable-diffusion-3-medium", wg.huggingface_endpoint(""))
        self.assertIn("stable-diffusion-3-medium", wg.huggingface_endpoint(None))

    def test_strips_whitespace(self):
        url = wg.huggingface_endpoint("  black-forest-labs/FLUX.1-schnell  ")
        self.assertTrue(url.endswith("FLUX.1-schnell"))

    def test_source_never_calls_the_dead_host(self):
        source = (REPO_ROOT / "wallpaper_generator.py").read_text(encoding="utf-8")
        # The retired host may be named in a comment/docstring, but no URL may
        # point at it: it no longer resolves in DNS.
        self.assertNotIn("https://api-inference.huggingface.co", source,
                         "the legacy host no longer resolves; use the router")


class TestSizeRounding(unittest.TestCase):
    """Hugging Face rejects sizes that are not multiples of 16."""

    def test_1080_becomes_1072(self):
        self.assertEqual(wg._round_to_multiple(1080), 1072)

    def test_already_aligned_is_unchanged(self):
        for value in (1920, 1024, 512, 256, 1072):
            with self.subTest(value=value):
                self.assertEqual(wg._round_to_multiple(value), value)

    def test_portrait_rounds_the_long_side_too(self):
        self.assertEqual(wg._round_to_multiple(1080), 1072)

    def test_clamped_to_a_sane_minimum(self):
        self.assertEqual(wg._round_to_multiple(10), 256)
        self.assertEqual(wg._round_to_multiple(0), 256)
        self.assertEqual(wg._round_to_multiple(None), 256)

    def test_every_result_is_divisible_by_16(self):
        for value in range(257, 2100, 7):
            with self.subTest(value=value):
                self.assertEqual(wg._round_to_multiple(value) % 16, 0)

    def test_request_payload_carries_rounded_sizes(self):
        captured = {}

        class FakeResponse:
            status = 200

            def __init__(self):
                self._payload = b"\xff\xd8\xff" + b"0" * 4000
                self._sent = False

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self, *a):
                if self._sent:
                    return b""
                self._sent = True
                return self._payload

        def fake_urlopen(req, *a, **k):
            captured["body"] = json.loads(req.data.decode())
            return FakeResponse()

        out = pathlib.Path(tempfile.mkdtemp()) / "sized.png"
        with mock.patch.object(wg, "load_token", lambda: "hf_test"), \
             mock.patch.object(wg.urllib.request, "urlopen", fake_urlopen):
            wg._generate_huggingface("prompt", wg.DEFAULT_HF_MODEL, 1920, 1080, out)

        params = captured["body"]["parameters"]
        self.assertEqual(params["width"], 1920)
        self.assertEqual(params["height"], 1072)


class TestDroppedConnection(unittest.TestCase):
    """Hugging Face sometimes hangs up mid-request on the free queue."""

    def test_remote_disconnect_is_recognised(self):
        import http.client
        self.assertTrue(wg._looks_like_dropped_connection(
            http.client.RemoteDisconnected("Remote end closed connection without response")))

    def test_reset_and_timeout_are_recognised(self):
        self.assertTrue(wg._looks_like_dropped_connection(ConnectionResetError("reset")))
        self.assertTrue(wg._looks_like_dropped_connection(TimeoutError("timed out")))

    def test_ordinary_errors_are_not(self):
        self.assertFalse(wg._looks_like_dropped_connection(ValueError("bad prompt")))

    def test_message_blames_the_queue_and_suggests_a_smaller_size(self):
        import http.client

        error = http.client.RemoteDisconnected("Remote end closed connection without response")
        calls = {"n": 0}

        class Boom:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self, *a):
                return b""

        def fake_urlopen(*a, **k):
            calls["n"] += 1
            raise error

        out = pathlib.Path(tempfile.mkdtemp()) / "dropped.png"
        with mock.patch.object(wg, "load_token", lambda: "hf_test"), \
             mock.patch.object(wg.urllib.request, "urlopen", fake_urlopen), \
             mock.patch.object(wg, "_sleep_cancellable", lambda *a, **k: None):
            with self.assertRaises(wg.ImageGenerationError) as ctx:
                wg._generate_huggingface("prompt", wg.DEFAULT_HF_MODEL, 1024, 1024, out)

        message = str(ctx.exception)
        self.assertIn("closed the connection", message)
        self.assertIn("1024x1024", message)
        self.assertEqual(calls["n"], 3, "a dropped connection must be retried")


class TestRetiredModels(unittest.TestCase):
    """Only ids no provider serves any more are remapped."""

    def test_sdxl_maps_to_the_served_model(self):
        self.assertEqual(wg.huggingface_model("stabilityai/stable-diffusion-xl-base-1.0"),
                         wg.DEFAULT_HF_MODEL)

    def test_blank_falls_back_to_the_served_model(self):
        self.assertEqual(wg.huggingface_model(""), wg.DEFAULT_HF_MODEL)
        self.assertEqual(wg.huggingface_model(None), wg.DEFAULT_HF_MODEL)

    def test_flux_is_retired_to_the_served_model(self):
        for flux in ("black-forest-labs/FLUX.1-schnell", "black-forest-labs/FLUX.1-dev"):
            with self.subTest(model=flux):
                self.assertEqual(wg.huggingface_model(flux), wg.DEFAULT_HF_MODEL)

    def test_the_served_model_is_on_the_free_list(self):
        self.assertIn(wg.DEFAULT_HF_MODEL, wg.HF_FREE_MODELS)


class TestRouterRouting(unittest.TestCase):
    """Paid models must go through the OpenAI-compatible router."""

    def test_router_url_is_the_credit_endpoint(self):
        self.assertEqual(wg.HF_OPENAI_URL,
                         "https://router.huggingface.co/v1/images/generations")

    def test_free_model_stays_on_hf_inference(self):
        self.assertIn(wg.DEFAULT_HF_MODEL, wg.HF_FREE_MODELS)
        self.assertIn("hf-inference/models", wg.huggingface_endpoint(wg.DEFAULT_HF_MODEL))

    def test_flux_request_is_remapped_before_routing(self):
        # A saved FLUX config must never reach the router: it serves no image
        # models, so the request has to be remapped to the free model first.
        self.assertEqual(
            wg.huggingface_model("black-forest-labs/FLUX.1-schnell"),
            wg.DEFAULT_HF_MODEL)


class TestErrorMessages(unittest.TestCase):
    def generate(self, code, body=b'{"error":"nope"}'):
        error = urllib.error.HTTPError(
            wg.huggingface_endpoint("black-forest-labs/FLUX.1-dev"), code, "err",
            {}, mock.Mock(read=lambda *a, **k: body))
        with mock.patch.object(wg, "load_token", lambda: "hf_test"), \
             mock.patch.object(wg.urllib.request, "urlopen", side_effect=error), \
             mock.patch.object(wg, "_sleep_cancellable", lambda *a, **k: None):
            with self.assertRaises(wg.ImageGenerationError) as ctx:
                wg._generate_huggingface("prompt", "black-forest-labs/FLUX.1-dev",
                                         256, 256, pathlib.Path("unused.png"))
        return str(ctx.exception)

    def test_rejected_token_says_so(self):
        self.assertIn("rejected the token", self.generate(401))

    def test_forbidden_is_treated_as_a_token_problem(self):
        self.assertIn("rejected the token", self.generate(403))

    def test_missing_model_points_at_the_settings(self):
        message = self.generate(404)
        self.assertIn("Settings", message)
        self.assertIn("not served", message)

    def test_other_codes_include_the_response_body(self):
        message = self.generate(500, b'{"error":"boom"}')
        self.assertIn("500", message)
        self.assertIn("boom", message)

    def test_missing_inference_permission_is_explained(self):
        message = self.generate(
            403, b'{"error":"This authentication method does not have sufficient '
                 b'permissions to call Inference Providers"}')
        self.assertIn("Make calls to Inference Providers", message)
        self.assertNotIn("plan", message.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
