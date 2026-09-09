"""Fast, offline integrity and real decoder checks for NASA telescope inputs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from backend.image_io import load_native


class TelescopeFixtureTests(unittest.TestCase):
    def test_official_files_decode_at_documented_dimensions(self) -> None:
        folder = Path(__file__).resolve().parent / "network-fixtures"
        manifest = json.loads((folder / "TELESCOPE_SOURCES.json").read_text(encoding="utf-8"))
        for item in manifest["images"]:
            with self.subTest(image=item["id"]):
                path = folder / item["file"]
                self.assertEqual(path.stat().st_size, item["bytes"])
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"])
                native = load_native(path)
                try:
                    self.assertEqual(native.size, (item["width"], item["height"]))
                    self.assertGreater(float(native.pixels.std()), 10)
                finally:
                    native.close()


if __name__ == "__main__":
    unittest.main()
