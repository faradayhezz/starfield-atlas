from __future__ import annotations

import unittest
import csv
import hashlib
import json

import numpy as np

from backend.catalog import (
    DATA_DIR, _star_identifier, bright_stars_in_frame, catalog_summary,
    deep_sky_in_frame, load_bright_stars, load_dark_nebulae,
    load_deep_sky_catalog, load_openngc, load_stars,
)
from backend.plate_solver import PlateSolution


def _test_solution() -> PlateSolution:
    return PlateSolution(
        center_ra_deg=0, center_dec_deg=0, roll_deg=0,
        horizontal_fov_deg=60, vertical_fov_deg=40, crop_fov_deg=25,
        distortion=0, rmse_arcsec=0, matches=10, false_positive_probability=0,
        solve_ms=1, image_width=1200, image_height=800,
        focal_pixels=600 / np.tan(np.deg2rad(30)), principal_x=600,
        principal_y=400, radial_reference_width=500,
        rotation_matrix=[[1, 0, 0], [0, 1, 0], [0, 0, 1]],
    )


class CatalogTests(unittest.TestCase):
    def test_catalog_has_real_coordinates(self) -> None:
        objects = load_openngc()
        self.assertGreaterEqual(len(objects), 4)
        self.assertTrue(all(0 <= item.ra_deg < 360 for item in objects))
        self.assertTrue(all(-90 <= item.dec_deg <= 90 for item in objects))

    def test_m31_is_present(self) -> None:
        objects = load_openngc()
        self.assertTrue(any(item.messier and int(item.messier) == 31 for item in objects))

    def test_ic434_background_is_not_mislabeled_as_the_flame_nebula(self) -> None:
        objects = {item.name: item for item in load_openngc()}
        self.assertEqual(objects["IC0434"].common_name_zh, "马头星云背景发射区")
        self.assertEqual(objects["NGC2024"].common_name_zh, "火焰星云")
        self.assertEqual(objects["B033"].common_name_zh, "马头星云")
        # Corrections affect display only; scientific-source snapshot stays exact.
        manifest = json.loads((DATA_DIR / "catalog_manifest.json").read_text(encoding="utf-8"))
        with (DATA_DIR / "openngc.csv").open("rb") as handle:
            self.assertEqual(hashlib.file_digest(handle, "sha256").hexdigest(), manifest["catalogs"]["openngc"]["sha256"])

    def test_full_hyg_is_real_unique_and_excludes_sun(self) -> None:
        stars = load_stars()
        self.assertEqual(len(stars), 119625)
        self.assertEqual(len({_star_identifier(star, index) for index, star in enumerate(stars)}), len(stars))
        self.assertFalse(any(star.get("hyg") == "0" for star in stars))
        self.assertEqual(sum(star["mag"] > 7 for star in stars), 104027)
        self.assertTrue(all(0 <= star["ra_deg"] < 360 and -90 <= star["dec_deg"] <= 90 for star in stars))
        # A concrete non-mainstream target: Barnard's high-proper-motion star.
        barnard = next(star for star in stars if star.get("hip") == "87937")
        self.assertGreater(barnard["mag"], 9)
        self.assertAlmostEqual(barnard["ra_deg"], 269.45, delta=0.1)

    def test_expanded_catalog_preserves_all_existing_chinese_names(self) -> None:
        full_by_hip = {star["hip"]: star for star in load_stars() if star.get("hip")}
        named = [star for star in load_bright_stars() if star.get("common_name_zh")]
        self.assertEqual(len(named), 2253)
        for star in named:
            self.assertEqual(full_by_hip[star["hip"]]["common_name_zh"], star["common_name_zh"])

    def test_faint_frame_inventory_has_no_bright_label_cap(self) -> None:
        solution = _test_solution()
        bright = bright_stars_in_frame(solution, magnitude_limit=7)
        faint = bright_stars_in_frame(solution, magnitude_limit=12)
        self.assertGreater(len(faint), len(bright))
        self.assertGreater(len(faint), 18)
        self.assertTrue(any(item["magnitude"] > 10 for item in faint))
        self.assertTrue({item["id"] for item in bright}.issubset({item["id"] for item in faint}))
        self.assertTrue(all(item["magnitude"] <= 12 for item in faint))
        self.assertTrue(all(item["evidence"] == "catalog_position" and item["pixelDetected"] is False for item in faint))
        self.assertLessEqual(sum(item["defaultVisible"] for item in faint), 15)
        self.assertTrue(all(0 <= item["x"] < 1200 and 0 <= item["y"] < 800 for item in faint))
        # The cap crosses RA=0. Both sides of the seam must survive the vector query.
        self.assertTrue(any(item["raDeg"] < 10 for item in faint))
        self.assertTrue(any(item["raDeg"] > 350 for item in faint))
        self.assertFalse(any(90 < item["raDeg"] < 270 for item in faint))

    def test_dark_catalog_uses_converted_j2000_and_honest_size_units(self) -> None:
        dark = load_dark_nebulae()
        self.assertEqual(len(dark), 1791)
        self.assertEqual(len({item.name for item in dark}), 1791)
        self.assertEqual(sum(item.name.startswith("LDN-SEQ-") for item in dark), 4)
        ldn1 = next(item for item in dark if item.name == "LDN0001")
        self.assertAlmostEqual(ldn1.ra_deg, 247.2144, places=4)
        self.assertAlmostEqual(ldn1.dec_deg, -16.1094, places=4)
        self.assertEqual(ldn1.area_sqdeg, 0.054)
        self.assertIsNone(ldn1.magnitude)
        self.assertEqual(ldn1.opacity, 3)
        self.assertEqual(ldn1.size_kind, "equivalent_area_circle")
        self.assertTrue(all(item.magnitude is None for item in dark))

    def test_faint_dso_depth_selects_faint_positions_without_claiming_detection(self) -> None:
        solution = _test_solution()
        base = deep_sky_in_frame(solution, threshold=60)
        deep = deep_sky_in_frame(solution, threshold=100)
        self.assertEqual({item["id"] for item in base}, {item["id"] for item in deep})
        self.assertTrue(any(item["expectedVisible"] and item["magnitude"] and item["magnitude"] > 12 for item in deep))
        self.assertGreater(sum(item["expectedVisible"] for item in deep), sum(item["expectedVisible"] for item in base))
        limited = deep_sky_in_frame(solution, threshold=100, magnitude_limit=8)
        self.assertFalse(any(item["expectedVisible"] and item["magnitude"] is not None and item["magnitude"] > 8 for item in limited))
        self.assertTrue(all(item["evidence"] == "catalog_position" and item["pixelDetected"] is False for item in deep))

    def test_catalog_deduplication_and_summary(self) -> None:
        combined = load_deep_sky_catalog()
        self.assertEqual(len({item.name for item in combined}), len(combined))
        self.assertFalse(any(item.object_type in {"NonEx", "Dup"} for item in combined))
        summary = catalog_summary()
        self.assertEqual(summary["deepSky"], len(combined))
        self.assertEqual(summary["stars"], len(load_stars()))
        self.assertEqual(summary["darkNebulae"], 1793)
        self.assertEqual(summary["pixelDetection"], False)

    def test_dark_cloud_inventory_does_not_overload_default_labels(self) -> None:
        solution = _test_solution()
        # Rotate the camera into the densely catalogued Cygnus region.
        ra, dec = np.deg2rad([310, 45])
        solution.rotation_matrix = [
            [np.cos(dec)*np.cos(ra), np.cos(dec)*np.sin(ra), np.sin(dec)],
            [-np.sin(ra), np.cos(ra), 0],
            [-np.sin(dec)*np.cos(ra), -np.sin(dec)*np.sin(ra), np.cos(dec)],
        ]
        initial = deep_sky_in_frame(solution, threshold=75)
        dark = [item for item in initial if item["id"].startswith("LDN")]
        self.assertGreater(len(dark), 20)
        self.assertFalse(any(item["defaultVisible"] for item in dark))
        deep = deep_sky_in_frame(solution, threshold=100)
        self.assertTrue(all(item["defaultVisible"] for item in deep if item["id"].startswith("LDN")))

    def test_distributed_faint_catalogue_artifacts_match_manifest(self) -> None:
        manifest = json.loads((DATA_DIR / "catalog_manifest.json").read_text(encoding="utf-8"))
        for name in ("faint_stars", "lynds_dark_nebulae"):
            entry = manifest["catalogs"][name]
            path = DATA_DIR / entry["file"]
            with path.open("rb") as handle:
                digest = hashlib.file_digest(handle, "sha256").hexdigest()
            self.assertEqual(digest, entry["sha256"])
            with path.open(encoding="utf-8", newline="") as handle:
                self.assertEqual(sum(1 for _ in csv.DictReader(handle)), entry["rows"])


if __name__ == "__main__":
    unittest.main()
