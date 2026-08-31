from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from backend.metadata import read_metadata
from backend.pipeline import _display_rgb
from backend.plate_solver import solve_plate


FIXTURES = Path(__file__).resolve().parent / "fixtures"


class RealSkyRegressionTests(unittest.TestCase):
    def test_16_bit_frame_is_not_clamped_white_for_preview(self) -> None:
        with Image.open(FIXTURES / "esa_tetra3_alt40_az-135_20190729.tiff") as image:
            preview = _display_rgb(image)
        values = np.asarray(preview)
        self.assertEqual(preview.mode, "RGB")
        self.assertGreater(len(np.unique(values[..., 0])), 32)

    def test_esa_camera_frames_blind_solve_to_reference_coordinates(self) -> None:
        expected = {
            "esa_tetra3_alt40_az-135_20190729.tiff": (230.667360, 11.034223, 11.426214),
            "esa_tetra3_alt60_az-135_20190729.tiff": (240.464077, 28.940573, 11.421557),
        }
        for filename, (ra, dec, fov) in expected.items():
            with self.subTest(filename=filename), Image.open(FIXTURES / filename) as image:
                solution = solve_plate(image, read_metadata(image))
                self.assertAlmostEqual(solution.center_ra_deg, ra, delta=0.02)
                self.assertAlmostEqual(solution.center_dec_deg, dec, delta=0.02)
                self.assertAlmostEqual(solution.horizontal_fov_deg, fov, delta=0.03)
                self.assertGreaterEqual(solution.matches, 8)


if __name__ == "__main__":
    unittest.main()
