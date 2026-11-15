"""Every built-in style must stay usable: right shape, not blank, not black.

These filters are hand-tuned OpenCV pipelines; a bad threshold used to turn
edge_enhance black and posterize yellow without any test noticing.
"""
import pathlib
import sys
import unittest

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import style_transfer as st

engine = st.get_style_transfer()


def _sample():
    """A colourful gradient with structure, 200x120, BGR."""
    h, w = 120, 200
    x = np.linspace(0, 255, w, dtype=np.float32)
    y = np.linspace(0, 255, h, dtype=np.float32)[:, None]
    b = np.broadcast_to(x, (h, w)).astype(np.uint8)
    g = np.broadcast_to(y, (h, w)).astype(np.uint8)
    r = ((x[None, :] + y) / 2).clip(0, 255).astype(np.uint8)
    img = np.dstack([b, g, r]).copy()
    img[20:40, 30:90] = (30, 30, 30)      # dark block
    img[70:90, 120:180] = (240, 240, 240)  # bright block
    return img


class TestEveryStyleRenders(unittest.TestCase):
    def test_shapes_and_content(self):
        src = _sample()
        for key in engine.available_styles:
            if key == "original":
                continue
            with self.subTest(style=key):
                out = engine._apply_filter(src.copy(), key)
                out = np.asarray(out)
                if out.ndim == 2:
                    out = np.dstack([out] * 3)
                self.assertEqual(out.shape[:2], src.shape[:2], "size changed")
                self.assertEqual(out.dtype, np.uint8, "wrong dtype")
                self.assertGreater(float(out.std()), 3.0,
                                   f"{key} produced a near-flat image")


if __name__ == "__main__":
    unittest.main()
