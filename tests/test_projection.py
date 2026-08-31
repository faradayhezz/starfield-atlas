from __future__ import annotations

import unittest

import numpy as np

from backend.catalog import _clip_line_to_rect
from backend.plate_solver import PlateSolution


class ProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.solution = PlateSolution(
            center_ra_deg=0,
            center_dec_deg=0,
            roll_deg=0,
            horizontal_fov_deg=60,
            vertical_fov_deg=40,
            crop_fov_deg=25,
            distortion=0,
            rmse_arcsec=0,
            matches=10,
            false_positive_probability=0,
            solve_ms=1,
            image_width=1200,
            image_height=800,
            focal_pixels=600 / np.tan(np.deg2rad(30)),
            principal_x=600,
            principal_y=400,
            radial_reference_width=500,
            rotation_matrix=[[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        )

    def test_boresight_maps_to_image_center(self) -> None:
        x, y, front = self.solution.world_to_pixel([0], [0])
        self.assertTrue(front[0])
        self.assertAlmostEqual(x[0], 600, places=5)
        self.assertAlmostEqual(y[0], 400, places=5)

    def test_ra_increases_toward_left_for_identity_camera(self) -> None:
        x, _, _ = self.solution.world_to_pixel([1], [0])
        self.assertLess(x[0], 600)

    def test_pixel_world_projection_round_trips(self) -> None:
        expected_ra = np.asarray([0.0, 12.5, 347.0])
        expected_dec = np.asarray([0.0, 8.0, -7.5])
        x, y, front = self.solution.world_to_pixel(expected_ra, expected_dec)
        self.assertTrue(front.all())
        ra, dec = self.solution.pixel_to_world(x, y)
        ra_delta = (ra - expected_ra + 180) % 360 - 180
        np.testing.assert_allclose(ra_delta, 0, atol=1e-8)
        np.testing.assert_allclose(dec, expected_dec, atol=1e-8)

    def test_pixel_world_projection_round_trips_with_distortion(self) -> None:
        self.solution.distortion = -0.06
        expected_ra = np.asarray([0.0, 9.5, 348.5])
        expected_dec = np.asarray([0.0, 7.0, -6.5])
        x, y, front = self.solution.world_to_pixel(expected_ra, expected_dec)
        self.assertTrue(front.all())
        ra, dec = self.solution.pixel_to_world(x, y)
        ra_delta = (ra - expected_ra + 180) % 360 - 180
        np.testing.assert_allclose(ra_delta, 0, atol=1e-8)
        np.testing.assert_allclose(dec, expected_dec, atol=1e-8)

    def test_public_solution_contains_sensor_corner_coordinates(self) -> None:
        public = self.solution.to_public_dict()
        corners = public["frame_corners_radec"]
        self.assertEqual(len(corners), 4)
        self.assertTrue(all(0 <= corner["ra_deg"] < 360 for corner in corners))
        self.assertTrue(all(-90 <= corner["dec_deg"] <= 90 for corner in corners))
        boundary = public["frame_boundary_radec"]
        self.assertEqual(len(boundary), 128)
        self.assertTrue(all(0 <= point["ra_deg"] < 360 for point in boundary))
        self.assertTrue(all(-90 <= point["dec_deg"] <= 90 for point in boundary))

    def test_constellation_segment_is_clipped_to_canvas(self) -> None:
        clipped = _clip_line_to_rect(-100, 200, 1300, 600, 0, 0, 1199, 799)
        self.assertIsNotNone(clipped)
        assert clipped is not None
        self.assertAlmostEqual(clipped[0], 0)
        self.assertAlmostEqual(clipped[2], 1199)
        self.assertTrue(all(0 <= value <= 1199 for value in (clipped[0], clipped[2])))
        self.assertTrue(all(0 <= value <= 799 for value in (clipped[1], clipped[3])))

    def test_constellation_segment_outside_canvas_is_rejected(self) -> None:
        self.assertIsNone(_clip_line_to_rect(-100, -100, -20, -20, 0, 0, 1199, 799))


if __name__ == "__main__":
    unittest.main()
