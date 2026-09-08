from __future__ import annotations

import hashlib
import io
import json
import threading
import time
import unittest
import urllib.parse
import urllib.request
from urllib.error import HTTPError
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image, ImageDraw

from backend import nasa_survey_media as survey
from backend.deep_sky_media import fetch_object_media, media_for, resolve_media_file
from backend.server import create_server


def jpeg(size=(384, 384)) -> bytes:
    image = Image.new("RGB", size, (11, 13, 20))
    ImageDraw.Draw(image).ellipse((160, 175, 200, 200), fill=(200, 190, 180))
    output = io.BytesIO()
    image.save(output, "JPEG")
    image.close()
    return output.getvalue()


class NasaSurveyMediaTests(unittest.TestCase):
    def test_unknown_identifiers_cannot_become_network_queries(self) -> None:
        with patch.object(survey, "_request_image") as request:
            for identifier in ("https://example.com/photo.jpg", "../../secrets", "M99999", "", "star-83274"):
                with self.subTest(identifier=identifier), self.assertRaises(survey.UnknownCatalogObjectError):
                    fetch_object_media(identifier)
            request.assert_not_called()

    def test_curated_nasa_photo_has_priority_and_resolves_catalog_alias(self) -> None:
        with patch.object(survey, "fetch_survey_media") as fallback:
            item = fetch_object_media("m13")
            self.assertEqual(item["mediaKind"], "official")
            self.assertEqual(item["mediaProvider"], "NASA")
            self.assertTrue(item["thumbnail"].startswith("/api/deep-sky-media/"))
            fallback.assert_not_called()

    def test_each_query_uses_its_own_exact_public_catalog_coordinates(self) -> None:
        first, neighbor = survey.catalog_object("ngc6269"), survey.catalog_object("NGC6271")
        first_query = urllib.parse.parse_qs(urllib.parse.urlparse(survey.query_url(first)).query)
        self.assertEqual(first_query["Position"], [f"{first.ra_deg:.7f},{first.dec_deg:.7f}"])
        self.assertEqual(first_query["Survey"], ["DSS2 Red"])
        self.assertEqual(first_query["Coordinates"], ["J2000"])
        self.assertNotEqual(survey.query_url(first), survey.query_url(neighbor))
        self.assertNotIn("filename", first_query)
        self.assertNotIn("photo", first_query)

    def test_invalid_image_or_dimensions_are_not_cached(self) -> None:
        for payload in (b"<html>NASA unavailable</html>", jpeg((64, 64))):
            with self.subTest(size=len(payload)), TemporaryDirectory() as temporary:
                with patch.object(survey, "_request_image", return_value=payload):
                    with self.assertRaises(survey.MediaUnavailableError):
                        survey.download_survey_record("NGC6269", Path(temporary))
                self.assertFalse(list(Path(temporary).glob("images/*.webp")))

    def test_cache_is_immutable_and_cannot_substitute_another_object(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(survey, "_request_image", return_value=jpeg()):
                record = survey.download_survey_record("NGC6269", root)
            item = survey.catalog_object("NGC6269")
            public = survey._public_record(record, item, root)
            self.assertEqual(public["mediaKind"], "survey")
            self.assertIn("DSS2", public["mediaProvider"])
            self.assertIn("巡天", public["note"])
            path = root / "images" / record["thumbnailFile"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), record["thumbnailSha256"])
            self.assertIsNone(survey._public_record(record, survey.catalog_object("NGC6271"), root))
            corrupted = {**record, "sourceUrl": survey.query_url(survey.catalog_object("NGC6271"))}
            self.assertIsNone(survey._public_record(corrupted, item, root))

    def test_runtime_requests_are_deduplicated_and_limited_to_three_downloads(self) -> None:
        lock = threading.Lock()
        state = {"active": 0, "peak": 0, "calls": 0}

        def slow_request(_url):
            with lock:
                state["calls"] += 1
                state["active"] += 1
                state["peak"] = max(state["peak"], state["active"])
            try:
                time.sleep(.04)
                return jpeg()
            finally:
                with lock:
                    state["active"] -= 1

        ids = ["NGC6269", "NGC6269", "NGC6271", "NGC6270", "NGC6263", "NGC6261"]
        with TemporaryDirectory() as temporary, patch.object(survey, "DATA_DIR", Path(temporary) / "empty-bundle"), \
                patch.object(survey, "CACHE_DIR", Path(temporary) / "cache"), \
                patch.object(survey, "_bundled_records", return_value={}), \
                patch.object(survey, "_request_image", side_effect=slow_request):
            with ThreadPoolExecutor(max_workers=6) as clients:
                outputs = list(clients.map(survey.fetch_survey_media, ids))
            self.assertEqual(state["calls"], len(set(ids)))
            self.assertLessEqual(state["peak"], 3)
            self.assertEqual(outputs[0], outputs[1])
            # A subsequent read works from disk, with no external request.
            with patch.object(survey, "_request_image", side_effect=AssertionError("cache miss")):
                self.assertEqual(survey.fetch_survey_media("NGC6269"), outputs[0])

    def test_bundled_real_thumbnails_match_catalog_coordinates_and_hashes(self) -> None:
        payload = json.loads((survey.DATA_DIR / "manifest.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(payload["objectCount"], 60)
        self.assertEqual(payload["objectCount"], len(payload["objects"]))
        for identifier in ("NGC6207", "NGC6255", "NGC6166", "NGC6269", "NGC6271"):
            self.assertIn(identifier, payload["objects"])
        for identifier, record in payload["objects"].items():
            with self.subTest(catalog_id=identifier):
                item = survey.catalog_object(identifier)
                self.assertEqual((record["raDeg"], record["decDeg"]), (item.ra_deg, item.dec_deg))
                self.assertEqual(record["sourceUrl"], survey.query_url(item))
                path = survey.DATA_DIR / "images" / record["thumbnailFile"]
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), record["thumbnailSha256"])
                with Image.open(path) as image:
                    self.assertEqual(image.size, (384, 384))
                    self.assertEqual(image.format, "WEBP")
        survey._bundled_records.cache_clear()
        self.assertEqual(media_for("NGC6207")["mediaKind"], "survey")
        filename = payload["objects"]["NGC6207"]["thumbnailFile"]
        self.assertTrue(resolve_media_file(filename).is_file())
        self.assertIsNone(resolve_media_file("../" + filename))

    def test_http_route_serves_valid_images_and_reports_missing_or_unavailable(self) -> None:
        server = create_server("127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            for identifier, kind in (("m13", "official"), ("ngc6269", "survey"), ("NGC6274%20NED01", "survey")):
                with self.subTest(identifier=identifier):
                    with urllib.request.urlopen(f"{base}/api/objects/{identifier}/media", timeout=5) as response:
                        record = json.load(response)
                    self.assertEqual(record["mediaKind"], kind)
                    with urllib.request.urlopen(base + record["thumbnail"], timeout=5) as response:
                        self.assertEqual(response.headers.get_content_type(), "image/webp")
                        with Image.open(io.BytesIO(response.read())) as image:
                            self.assertEqual(image.format, "WEBP")
            with self.assertRaises(HTTPError) as unknown:
                urllib.request.urlopen(base + "/api/objects/not-a-catalog-object/media", timeout=5)
            self.assertEqual(unknown.exception.code, 404)
            with patch("backend.deep_sky_media.fetch_object_media", side_effect=survey.MediaUnavailableError("temporarily unavailable")):
                with self.assertRaises(HTTPError) as unavailable:
                    urllib.request.urlopen(base + "/api/objects/NGC6269/media", timeout=5)
                self.assertEqual(unavailable.exception.code, 503)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
