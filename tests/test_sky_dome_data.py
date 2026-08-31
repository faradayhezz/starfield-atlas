from __future__ import annotations

import unittest
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image

from backend import hips_proxy
from backend.hips_proxy import public_hips_manifest, resolve_hips_resource
from backend.sky_catalog import public_sky_catalog


def _tiny_jpeg() -> bytes:
    output = BytesIO()
    Image.new("RGB", (2, 2), (8, 18, 32)).save(output, format="JPEG")
    return output.getvalue()


class SkyDomeDataTests(unittest.TestCase):
    def test_catalog_contains_every_label_layer(self) -> None:
        catalog = public_sky_catalog()
        self.assertGreaterEqual(catalog["counts"]["deepSky"], 300)
        self.assertGreaterEqual(catalog["counts"]["brightStars"], 400)
        self.assertEqual(catalog["counts"]["constellations"], 88)
        self.assertGreaterEqual(catalog["counts"]["constellationSegments"], 700)
        self.assertTrue(any(item["catalogLabel"] == "M31" for item in catalog["deepSky"]))

    def test_manifest_exposes_two_all_sky_surveys_and_partial_legacy(self) -> None:
        manifest = public_hips_manifest()
        surveys = {item["id"]: item for item in manifest["surveys"]}
        self.assertEqual(surveys["dss2-color"]["coverageFraction"], 1.0)
        self.assertEqual(surveys["2mass-color"]["coverageFraction"], 1.0)
        self.assertLess(surveys["legacy-dr10"]["coverageFraction"], 1.0)

    def test_bundled_overview_is_resolved_without_network(self) -> None:
        resolved = resolve_hips_resource("2mass-color", "Norder3/Allsky.jpg")
        self.assertIsNotNone(resolved)
        path, content_type, source = resolved or (None, "", "")
        self.assertTrue(path and path.is_file())
        self.assertEqual(content_type, "image/jpeg")
        self.assertEqual(source, "bundled")

    def test_proxy_rejects_traversal_unknown_surveys_and_impossible_orders(self) -> None:
        self.assertIsNone(resolve_hips_resource("2mass-color", "../properties"))
        self.assertIsNone(resolve_hips_resource("unknown", "properties"))
        self.assertIsNone(resolve_hips_resource("dss2-color", "Norder10/Dir0/Npix0.jpg"))
        self.assertIsNone(resolve_hips_resource("dss2-color", "Norder1/Dir999/Npix0.jpg"))
        self.assertIsNone(resolve_hips_resource("dss2-color", "Norder1/Dir0/Npix48.jpg"))
        self.assertIsNone(resolve_hips_resource("dss2-color", f"Norder1/Dir{'9' * 500}/Npix0.jpg"))

    def test_proxy_does_not_cache_html_returned_for_an_image(self) -> None:
        class FakeResponse:
            headers = {"Content-Length": "31"}

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _size: int) -> bytes:
                if hasattr(self, "_done"):
                    return b""
                self._done = True
                return b"<html>temporary upstream error</html>"

        with TemporaryDirectory() as folder:
            root = Path(folder)
            with (
                patch.object(hips_proxy, "BUNDLED_DIR", root / "bundled"),
                patch.object(hips_proxy, "CACHE_DIR", root / "cache"),
                patch.object(hips_proxy.urllib.request, "urlopen", return_value=FakeResponse()),
            ):
                self.assertIsNone(resolve_hips_resource("dss2-color", "Norder1/Dir0/Npix0.jpg"))
                self.assertEqual(list((root / "cache").rglob("*.part")), [])
                self.assertEqual(list((root / "cache").rglob("*.jpg")), [])

    def test_proxy_caches_a_valid_jpeg_tile(self) -> None:
        payload = _tiny_jpeg()

        class FakeResponse:
            headers = {"Content-Length": str(len(payload))}

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _size: int) -> bytes:
                if hasattr(self, "_done"):
                    return b""
                self._done = True
                return payload

        with TemporaryDirectory() as folder:
            root = Path(folder)
            with (
                patch.object(hips_proxy, "BUNDLED_DIR", root / "bundled"),
                patch.object(hips_proxy, "CACHE_DIR", root / "cache"),
                patch.object(hips_proxy.urllib.request, "urlopen", return_value=FakeResponse()),
            ):
                resolved = resolve_hips_resource("dss2-color", "Norder1/Dir0/Npix3.jpg")
                self.assertIsNotNone(resolved)
                path, content_type, source = resolved or (None, "", "")
                self.assertTrue(path and path.is_file())
                self.assertEqual(content_type, "image/jpeg")
                self.assertEqual(source, "downloaded")

    def test_proxy_replaces_a_stale_html_tile_in_cache(self) -> None:
        payload = _tiny_jpeg()

        class FakeResponse:
            headers = {"Content-Length": str(len(payload))}

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _size: int) -> bytes:
                if hasattr(self, "_done"):
                    return b""
                self._done = True
                return payload

        with TemporaryDirectory() as folder:
            root = Path(folder)
            stale = root / "cache" / "dss2-color" / "Norder1" / "Dir0" / "Npix3.jpg"
            stale.parent.mkdir(parents=True)
            stale.write_text("<html>stale error</html>", encoding="utf-8")
            with (
                patch.object(hips_proxy, "BUNDLED_DIR", root / "bundled"),
                patch.object(hips_proxy, "CACHE_DIR", root / "cache"),
                patch.object(hips_proxy.urllib.request, "urlopen", return_value=FakeResponse()),
            ):
                resolved = resolve_hips_resource("dss2-color", "Norder1/Dir0/Npix3.jpg")
                self.assertIsNotNone(resolved)
                self.assertTrue(stale.read_bytes().startswith(b"\xff\xd8\xff"))
                self.assertEqual((resolved or (None, None, None))[2], "downloaded")

    def test_proxy_rejects_a_truncated_jpeg_response(self) -> None:
        class FakeResponse:
            headers = {"Content-Length": "100"}

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _size: int) -> bytes:
                if hasattr(self, "_done"):
                    return b""
                self._done = True
                return b"\xff\xd8\xffOK"

        with TemporaryDirectory() as folder:
            root = Path(folder)
            with (
                patch.object(hips_proxy, "BUNDLED_DIR", root / "bundled"),
                patch.object(hips_proxy, "CACHE_DIR", root / "cache"),
                patch.object(hips_proxy.urllib.request, "urlopen", return_value=FakeResponse()),
            ):
                self.assertIsNone(resolve_hips_resource("dss2-color", "Norder1/Dir0/Npix4.jpg"))
                self.assertEqual(list((root / "cache").rglob("*.part")), [])
                self.assertEqual(list((root / "cache").rglob("*.jpg")), [])

    def test_proxy_rejects_a_truncated_jpeg_without_content_length(self) -> None:
        payload = _tiny_jpeg()[:-2]

        class FakeResponse:
            headers: dict[str, str] = {}

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _size: int) -> bytes:
                if hasattr(self, "_done"):
                    return b""
                self._done = True
                return payload

        with TemporaryDirectory() as folder:
            root = Path(folder)
            with (
                patch.object(hips_proxy, "BUNDLED_DIR", root / "bundled"),
                patch.object(hips_proxy, "CACHE_DIR", root / "cache"),
                patch.object(hips_proxy.urllib.request, "urlopen", return_value=FakeResponse()),
            ):
                self.assertIsNone(resolve_hips_resource("dss2-color", "Norder1/Dir0/Npix5.jpg"))
                self.assertEqual(list((root / "cache").rglob("*.part")), [])
                self.assertEqual(list((root / "cache").rglob("*.jpg")), [])


if __name__ == "__main__":
    unittest.main()
