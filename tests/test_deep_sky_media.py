from __future__ import annotations

import hashlib
import json
import unittest
import urllib.parse
from pathlib import Path

from PIL import Image

from backend.catalog import load_openngc
from backend.deep_sky_media import (
    IMAGE_DIR,
    MANIFEST_PATH,
    load_nasa_deep_sky,
    media_for,
    resolve_media_file,
)


class DeepSkyMediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_pack_covers_common_targets(self) -> None:
        objects = self.payload["objects"]
        self.assertGreaterEqual(len(objects), 36)
        for catalog_id in (
            "NGC0224", "NGC0221", "NGC0205", "NGC0598", "NGC1952",
            "NGC1976", "NGC0281", "NGC7635", "Mel022", "NGC6205",
            "IC1805", "IC1848", "NGC0869", "NGC0884",
        ):
            self.assertIn(catalog_id, objects)

    def test_every_mapping_matches_catalog_and_verified_local_image(self) -> None:
        catalog_ids = {item.name for item in load_openngc()}
        for catalog_id, item in self.payload["objects"].items():
            with self.subTest(catalog_id=catalog_id):
                self.assertIn(catalog_id, catalog_ids)
                image_path = IMAGE_DIR / item["thumbnailFile"]
                self.assertTrue(image_path.is_file())
                self.assertEqual(
                    hashlib.sha256(image_path.read_bytes()).hexdigest(),
                    item["thumbnailSha256"],
                )
                with Image.open(image_path) as image:
                    self.assertEqual(image.format, "WEBP")
                    self.assertEqual(image.size, (item["thumbnailWidth"], item["thumbnailHeight"]))

    def test_sources_are_official_nasa_hosts(self) -> None:
        for catalog_id, item in self.payload["objects"].items():
            for key in ("sourceUrl", "assetUrl"):
                with self.subTest(catalog_id=catalog_id, key=key):
                    url = urllib.parse.urlparse(item[key])
                    hostname = (url.hostname or "").lower()
                    self.assertEqual(url.scheme, "https")
                    self.assertTrue(hostname == "nasa.gov" or hostname.endswith(".nasa.gov"))

    def test_runtime_lookup_exposes_local_thumbnail_and_intro(self) -> None:
        load_nasa_deep_sky.cache_clear()
        item = media_for("NGC0224")
        self.assertEqual(item["mediaProvider"], "NASA")
        self.assertEqual(item["titleEn"], "Andromeda Galaxy")
        self.assertIn("本星系群", item["description"])
        self.assertTrue(item["thumbnail"].startswith("/api/deep-sky-media/"))
        self.assertTrue(item["sourceUrl"].startswith("https://"))

    def test_media_path_rejects_traversal(self) -> None:
        self.assertIsNone(resolve_media_file("../nasa_deep_sky.json"))
        self.assertIsNone(resolve_media_file("%2e%2e%2fnasa_deep_sky.json"))


if __name__ == "__main__":
    unittest.main()
