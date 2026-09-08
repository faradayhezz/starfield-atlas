from __future__ import annotations

import gzip
import io
import json
import unittest
from types import SimpleNamespace

from backend.server import JSON_GZIP_THRESHOLD, SkyHandler, _accepts_gzip


def response(payload: dict, accept_encoding: str | None):
    headers = {}
    stream = io.BytesIO()
    handler = SimpleNamespace(
        headers={} if accept_encoding is None else {"Accept-Encoding": accept_encoding},
        send_response=lambda _status: None,
        send_header=lambda name, value: headers.__setitem__(name, value),
        end_headers=lambda: None,
        wfile=stream,
    )
    SkyHandler._json(handler, payload)
    return headers, stream.getvalue()


class JsonCompressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.large = {"status": "完成", "brightStars": [
            {"id": f"tycho-{index}", "label": f"恒星 {index}",
             "raDeg": index / 100, "decDeg": index / 1000,
             "catalog": "ATHYG v3.2", "evidence": "catalog_position",
             "pixelDetected": False, "description": "公开目录坐标，仅表示位置，不代表像素检测。" * 4}
            for index in range(1000)
        ]}

    def test_large_json_roundtrips_every_object_and_chinese_text(self) -> None:
        headers, data = response(self.large, "br, gzip;q=0.6")
        decoded = gzip.decompress(data)
        self.assertGreater(len(decoded), JSON_GZIP_THRESHOLD)
        self.assertEqual(json.loads(decoded), self.large)
        self.assertIn("恒星 999".encode(), decoded)
        self.assertEqual(headers["Content-Encoding"], "gzip")
        self.assertEqual(headers["Content-Length"], str(len(data)))
        self.assertEqual(headers["Vary"], "Accept-Encoding")
        self.assertLess(len(data), len(decoded))

    def test_explicit_gzip_refusal_preserves_uncompressed_complete_payload(self) -> None:
        for accepted in (None, "br", "gzip;q=0", "GZIP; q=0.000, *;q=1", "gzip;q=invalid"):
            with self.subTest(header=accepted):
                headers, data = response(self.large, accepted)
                self.assertNotIn("Content-Encoding", headers)
                self.assertEqual(json.loads(data), self.large)
                self.assertEqual(headers["Content-Length"], str(len(data)))
                self.assertEqual(headers["Vary"], "Accept-Encoding")

    def test_small_payload_is_compact_and_not_compressed(self) -> None:
        headers, data = response({"status": "正常", "count": 3}, "gzip")
        self.assertEqual(data, '{"status":"正常","count":3}'.encode())
        self.assertNotIn("Content-Encoding", headers)
        self.assertEqual(headers["Content-Length"], str(len(data)))

    def test_encoding_negotiation_accepts_case_quality_and_wildcard(self) -> None:
        for accepted in ("gzip", "GZip;Q=0.1", "deflate, gzip", "*;q=.5"):
            self.assertTrue(_accepts_gzip(accepted), accepted)
        for refused in ("", "identity", "gzip;q=NaN", "gzip;q=-1", "gzip;q=2", "*;q=0"):
            self.assertFalse(_accepts_gzip(refused), refused)


if __name__ == "__main__":
    unittest.main()
