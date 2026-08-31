from __future__ import annotations

import unittest

from backend.catalog import load_openngc


class CatalogTests(unittest.TestCase):
    def test_catalog_has_real_coordinates(self) -> None:
        objects = load_openngc()
        self.assertGreaterEqual(len(objects), 4)
        self.assertTrue(all(0 <= item.ra_deg < 360 for item in objects))
        self.assertTrue(all(-90 <= item.dec_deg <= 90 for item in objects))

    def test_m31_is_present(self) -> None:
        objects = load_openngc()
        self.assertTrue(any(item.messier and int(item.messier) == 31 for item in objects))


if __name__ == "__main__":
    unittest.main()

