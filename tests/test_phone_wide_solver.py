from __future__ import annotations

import math
import os
from pathlib import Path
import unittest

from PIL import Image

from backend.image_io import display_rgb, load_native
from backend.plate_solver import _blind_crop_specs, _refine_wide_phone_solution, solve_plate


class PhoneWideSolverTests(unittest.TestCase):
    def test_metadata_free_wide_probe_fits_real_pattern_database(self) -> None:
        size = (4032, 3024)
        specs = _blind_crop_specs(size)
        self.assertEqual(specs[0], ((0, 0, *size), None))
        box, hint = specs[1]
        self.assertIsNone(hint)
        fraction = (box[2] - box[0]) / size[0]
        crop_angle = math.degrees(2 * math.atan(fraction * math.tan(math.radians(70 / 2))))
        self.assertGreater(crop_angle, 10)
        self.assertLess(crop_angle, 30)
        self.assertEqual((box[0] + box[2]) / 2, size[0] / 2)
        self.assertEqual((box[1] + box[3]) / 2, size[1] / 2)

    def test_multiscale_crops_keep_optical_centre_for_odd_sizes(self) -> None:
        for size in [(4033, 3025), (4032, 3025), (120, 80), (20, 20)]:
            with self.subTest(size=size):
                boxes = [box for box, _ in _blind_crop_specs(size)]
                self.assertEqual(len(boxes), len(set(boxes)))
                for left, top, right, bottom in boxes:
                    self.assertGreaterEqual(left, 0)
                    self.assertGreaterEqual(top, 0)
                    self.assertLessEqual(right, size[0])
                    self.assertLessEqual(bottom, size[1])
                    self.assertEqual(left + right, size[0])
                    self.assertEqual(top + bottom, size[1])

    def test_blank_full_frame_cannot_validate_a_central_hypothesis(self) -> None:
        # A blank negative control must not create full-frame anchor evidence.
        with Image.new("RGB", (320, 240), "black") as blank:
            result = _refine_wide_phone_solution(blank, None, None)
        self.assertIsNone(result)

    @unittest.skipUnless(os.environ.get("STARFIELD_PHONE_FIXTURE"), "Private phone fixture is opt-in and not distributed")
    def test_real_phone_blind_solution_and_independent_global_anchors(self) -> None:
        native = load_native(Path(os.environ["STARFIELD_PHONE_FIXTURE"]))
        image = display_rgb(native)
        try:
            self.assertEqual(native.size, (4032, 3024))
            # The transferred file really has no camera/FOV EXIF. The reference
            # screenshot is used only below for a coarse independent check.
            self.assertIsNone(native.metadata.focal_length_35mm)
            self.assertIsNone(native.metadata.camera_model)
            solution = solve_plate(image, native.metadata, orientation_applied=True)
            self.assertGreaterEqual(solution.matches, 8)
            self.assertLess(solution.false_positive_probability, 1e-8)
            self.assertLess(solution.rmse_arcsec, 180)
            self.assertAlmostEqual(solution.center_ra_deg, 290.3471, delta=.25)
            self.assertAlmostEqual(solution.center_dec_deg, 29.3208, delta=.25)
            self.assertAlmostEqual(solution.horizontal_fov_deg, 70.2, delta=2)
            self.assertAlmostEqual(solution.roll_deg, 290.36, delta=.5)
            self.assertEqual(solution.method, "tetra3-wide-multiscale-verified")
            verification = solution.verification
            self.assertIsNotNone(verification)
            self.assertGreaterEqual(verification["heldOutStars"], 8)
            self.assertGreaterEqual(verification["heldOutOutsideCrop"], 8)
            self.assertGreaterEqual(verification["spanFractionX"], .65)
            self.assertGreaterEqual(verification["spanFractionY"], .65)
            self.assertLess(verification["heldOutRmseArcsec"], 180)
            self.assertEqual((solution.principal_x, solution.principal_y), (2016, 1512))
            self.assertEqual(solution.radial_reference_width, 4032)
        finally:
            image.close()
            native.close()


if __name__ == "__main__":
    unittest.main()
