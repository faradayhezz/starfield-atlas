from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from backend.legacy_sky_map import (
    ALL_SKY_PACK_ROOT,
    PACK_ROOT,
    all_sky_manifest,
    compose_filled_image,
    manifest,
    public_manifest,
    resolve_all_sky_tile,
    resolve_layer_tile,
    resolve_tile,
)


class LegacySkyMapTests(unittest.TestCase):
    def test_complete_offline_tile_pyramid_is_verified(self) -> None:
        payload = manifest()
        min_zoom = int(payload["minZoom"])
        max_zoom = int(payload["maxZoom"])
        expected = sum(4**zoom for zoom in range(min_zoom, max_zoom + 1))
        tiles = payload["tiles"]
        self.assertEqual(int(payload["tileCount"]), expected)
        self.assertEqual(len(tiles), expected)
        for row in tiles:
            path = (PACK_ROOT / str(row["path"])).resolve()
            path.relative_to(PACK_ROOT.resolve())
            self.assertTrue(path.is_file(), path)
            content = path.read_bytes()
            self.assertEqual(hashlib.sha256(content).hexdigest(), row["sha256"])
        for row in (tiles[0], tiles[len(tiles) // 2], tiles[-1]):
            with Image.open(PACK_ROOT / str(row["path"])) as image:
                self.assertEqual(image.format, "JPEG")
                self.assertEqual(image.size, (256, 256))

    def test_manifest_preserves_required_credit_and_official_sources(self) -> None:
        payload = public_manifest()
        self.assertEqual(
            payload["attribution"], "Legacy Surveys / D. Lang (Perimeter Institute)"
        )
        self.assertEqual(payload["license"], "CC BY 4.0")
        self.assertIn("lbl.gov", str(payload["officialReleaseUrl"]))
        for key in ("dataReleaseUrl", "viewerUrl"):
            self.assertIn("legacysurvey.org", str(payload[key]))

    def test_manifest_reader_refreshes_when_file_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "manifest.json"
            path.write_text('{"revision": 1}', encoding="utf-8")
            with patch("backend.legacy_sky_map.MANIFEST_PATH", path):
                self.assertEqual(manifest()["revision"], 1)
                path.write_text('{"revision": 22}', encoding="utf-8")
                self.assertEqual(manifest()["revision"], 22)

    def test_complete_2mass_all_sky_tile_pyramid_is_verified(self) -> None:
        payload = all_sky_manifest()
        min_zoom = int(payload["minZoom"])
        max_zoom = int(payload["maxZoom"])
        expected = sum(4**zoom for zoom in range(min_zoom, max_zoom + 1))
        tiles = payload["tiles"]
        self.assertEqual(expected, 1365)
        self.assertEqual(int(payload["tileCount"]), expected)
        self.assertEqual(len(tiles), expected)
        self.assertEqual(
            int(payload["totalBytes"]), sum(int(row["bytes"]) for row in tiles)
        )
        for row in tiles:
            path = (ALL_SKY_PACK_ROOT / str(row["path"])).resolve()
            path.relative_to(ALL_SKY_PACK_ROOT.resolve())
            self.assertTrue(path.is_file(), path)
            content = path.read_bytes()
            self.assertEqual(len(content), int(row["bytes"]))
            self.assertEqual(hashlib.sha256(content).hexdigest(), row["sha256"])
        for row in (tiles[0], tiles[len(tiles) // 2], tiles[-1]):
            with Image.open(ALL_SKY_PACK_ROOT / str(row["path"])) as image:
                self.assertEqual(image.format, "JPEG")
                self.assertEqual(image.size, (256, 256))

    def test_2mass_manifest_preserves_license_provenance_and_full_coverage(self) -> None:
        payload = all_sky_manifest()
        self.assertEqual(payload["dataset"], "Two Micron All Sky Survey (2MASS) Color J/H/Ks")
        self.assertEqual(payload["sourceHiPSId"], "CDS/P/2MASS/color")
        self.assertEqual(float(payload["coverageFraction"]), 1.0)
        self.assertEqual(float(payload["datasetCoverageFraction"]), 1.0)
        self.assertAlmostEqual(float(payload["renderCoverageFraction"]), 0.996272, places=5)
        self.assertAlmostEqual(float(payload["renderDeclinationLimit"]), 85.05112878)
        self.assertFalse(bool(payload["runtimeNetworkRequired"]))
        self.assertEqual(payload["license"], "ODbL-1.0")
        self.assertIn("opendatacommons.org", str(payload["licenseUrl"]))
        self.assertIn("alasky.cds.unistra.fr", str(payload["sourceHiPSUrl"]))
        self.assertIn("irsa.ipac.caltech.edu", str(payload["sourceMissionUrl"]))
        self.assertIn("2MASS", str(payload["attribution"]))
        self.assertIn("CDS", str(payload["acknowledgement"]))
        self.assertEqual(payload["localPackStatus"], "partial derivative")
        self.assertEqual(payload["sourceHiPSStatus"], "public master clonableOnce")
        self.assertEqual(payload["sourceHiPSDoi"], "10.26093/cds/aladin/bzc8-nw")
        self.assertEqual(payload["surveyBibcode"], "2006AJ....131.1163S")

        public = public_manifest()
        self.assertEqual(public["defaultLayer"], "filled")
        self.assertTrue(bool(public["allSkyPackAvailable"]))
        self.assertRegex(str(public["tileVersion"]), r"^[0-9a-f]{16}$")
        self.assertAlmostEqual(float(public["renderCoverageFraction"]), 0.996272, places=5)
        self.assertAlmostEqual(float(public["renderDeclinationLimit"]), 85.05112878)
        self.assertEqual(
            [row["id"] for row in public["layers"]],
            ["filled", "ls-dr11", "2mass-color"],
        )
        self.assertEqual(int(public["allSkyTileCount"]), 1365)
        self.assertEqual(public["allSkyLicense"], "ODbL-1.0")
        self.assertIn("alasky.cds.unistra.fr", str(public["allSkySourceUrl"]))
        self.assertIn("irsa.ipac.caltech.edu", str(public["allSkyMissionUrl"]))
        self.assertEqual(public["allSkyDoi"], "10.26093/cds/aladin/bzc8-nw")
        self.assertEqual(public["allSkyReferenceBibcode"], "2006AJ....131.1163S")
        for layer in public["layers"]:
            self.assertGreater(int(layer["tileCount"]), 0)
            self.assertGreater(int(layer["totalBytes"]), 0)
            for credit in layer["attributions"]:
                self.assertIn("sourceUrl", credit)
                self.assertIn("licenseLabel", credit)
                self.assertIn("licenseUrl", credit)

    def test_resolver_accepts_only_valid_tile_coordinates(self) -> None:
        self.assertIsNotNone(resolve_tile(1, 0, 0))
        self.assertIsNotNone(resolve_tile(0, 0, 0))
        self.assertIsNone(resolve_tile(-1, 0, 0))
        self.assertIsNone(resolve_tile(5, 32, 0))
        self.assertIsNone(resolve_tile(5, 0, -1))
        self.assertIsNone(resolve_tile(15, 0, 0))

    def test_layer_resolver_serves_all_three_layers_and_rejects_unknown_layer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            composite_cache = Path(temporary) / "filled"
            with patch(
                "backend.legacy_sky_map.COMPOSITE_CACHE_ROOT", composite_cache
            ):
                legacy = resolve_layer_tile("ls-dr11", 0, 0, 0)
                all_sky = resolve_layer_tile("2mass-color", 0, 0, 0)
                filled = resolve_layer_tile("filled", 0, 0, 0)
                self.assertIsNotNone(legacy)
                self.assertEqual(legacy[1], "bundled")
                self.assertIsNotNone(all_sky)
                self.assertEqual(all_sky[1], "2mass-bundled")
                self.assertIsNotNone(filled)
                self.assertIn(filled[1], {"dr11+2mass", "dr11+2mass-cache"})
                with Image.open(filled[0]) as image:
                    self.assertEqual(image.format, "JPEG")
                    self.assertEqual(image.size, (256, 256))

        self.assertIsNone(resolve_layer_tile("unknown", 0, 0, 0))
        self.assertIsNone(resolve_layer_tile("", 0, 0, 0))
        self.assertIsNone(resolve_layer_tile("filled", -1, 0, 0))

    def test_filled_compositor_replaces_an_entire_no_data_tile(self) -> None:
        foreground = Image.new("RGB", (256, 256), (32, 32, 32))
        background = Image.new("RGB", (256, 256), (13, 91, 177))
        rendered = compose_filled_image(foreground, background)
        self.assertEqual(rendered.getpixel((0, 0)), (13, 91, 177))
        self.assertEqual(rendered.getpixel((128, 128)), (13, 91, 177))
        self.assertEqual(rendered.getpixel((255, 255)), (13, 91, 177))

    def test_filled_compositor_preserves_an_entire_covered_tile(self) -> None:
        foreground = Image.new("RGB", (256, 256), (18, 41, 73))
        background = Image.new("RGB", (256, 256), (173, 122, 49))
        rendered = compose_filled_image(foreground, background)
        self.assertEqual(rendered.getpixel((0, 0)), (18, 41, 73))
        self.assertEqual(rendered.getpixel((128, 128)), (18, 41, 73))
        self.assertEqual(rendered.getpixel((255, 255)), (18, 41, 73))

    def test_filled_compositor_replaces_only_connected_no_data_hole(self) -> None:
        foreground = Image.new("RGB", (256, 256), (18, 41, 73))
        for y in range(80, 176):
            for x in range(64, 192):
                foreground.putpixel((x, y), (32, 32, 32))
        # An isolated dark-sky-colored pixel must not be mistaken for survey coverage loss.
        foreground.putpixel((12, 12), (32, 32, 32))
        background = Image.new("RGB", (256, 256), (173, 122, 49))

        rendered = compose_filled_image(foreground, background)

        self.assertEqual(rendered.getpixel((128, 128)), (173, 122, 49))
        self.assertEqual(rendered.getpixel((63, 128)), (18, 41, 73))
        self.assertEqual(rendered.getpixel((192, 128)), (18, 41, 73))
        self.assertEqual(rendered.getpixel((12, 12)), (32, 32, 32))

    def test_direct_2mass_stops_at_native_zoom_but_filled_can_sample_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cache_root = Path(temporary) / "filled"
            with patch("backend.legacy_sky_map.COMPOSITE_CACHE_ROOT", cache_root):
                self.assertIsNone(resolve_all_sky_tile(6, 0, 0))
                first = resolve_layer_tile("filled", 6, 0, 0)
                second = resolve_layer_tile("filled", 6, 0, 0)

                self.assertIsNotNone(first)
                self.assertEqual(first[1], "2mass-derived-fallback")
                self.assertEqual(first, second)
                self.assertTrue(first[0].is_relative_to(cache_root))
                self.assertTrue(first[0].is_file())
                with Image.open(first[0]) as image:
                    self.assertEqual(image.format, "JPEG")
                    self.assertEqual(image.size, (256, 256))

        self.assertIsNone(resolve_all_sky_tile(15, 0, 0))

    def test_public_manifest_falls_back_when_2mass_pack_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / "missing-manifest.json"
            with patch("backend.legacy_sky_map.ALL_SKY_MANIFEST_PATH", missing):
                payload = public_manifest()

        self.assertFalse(bool(payload["allSkyPackAvailable"]))
        self.assertEqual(payload["defaultLayer"], "ls-dr11")
        self.assertEqual([row["id"] for row in payload["layers"]], ["ls-dr11"])
        self.assertEqual(int(payload["allSkyTileCount"]), 0)


if __name__ == "__main__":
    unittest.main()
