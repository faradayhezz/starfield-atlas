from __future__ import annotations

import http.client
import io
import json
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image
import numpy as np
import imagecodecs

from backend.analysis_tasks import AnalysisTaskRegistry
from backend import server as server_module


REQUEST_ID = "0123456789abcdef0123456789abcdef"
PROGRESS_KEYS = {
    "status",
    "stage",
    "percent",
    "message",
    "receivedBytes",
    "totalBytes",
    "updatedAt",
}


def _jpeg_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (16, 12), (5, 12, 24)).save(output, "JPEG")
    return output.getvalue()


class AnalysisTaskRegistryTests(unittest.TestCase):
    def test_progress_cancel_and_ttl(self) -> None:
        now = [10.0]
        registry = AnalysisTaskRegistry(ttl_seconds=30, monotonic=lambda: now[0])
        snapshot = registry.register(REQUEST_ID, total_bytes=100)
        self.assertEqual(set(snapshot), PROGRESS_KEYS)
        self.assertEqual(snapshot["status"], "uploading")

        registry.update(
            REQUEST_ID,
            status="processing",
            stage="solving",
            percent=25,
            message="正在解算",
            received_bytes=100,
        )
        interrupted = threading.Event()
        registry.set_cancel_hook(REQUEST_ID, interrupted.set)
        snapshot, accepted = registry.cancel(REQUEST_ID)
        self.assertTrue(accepted)
        self.assertTrue(interrupted.wait(0.2))
        self.assertEqual(snapshot["status"], "cancelling")

        # A late worker callback cannot revive a cancelling task.
        registry.update(REQUEST_ID, status="processing", stage="catalog", percent=55)
        self.assertEqual(registry.get(REQUEST_ID)["status"], "cancelling")
        registry.mark_cancelled(REQUEST_ID)
        self.assertEqual(registry.get(REQUEST_ID)["status"], "cancelled")

        now[0] += 31
        self.assertIsNone(registry.get(REQUEST_ID))


class AnalysisServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.runtime_patch = mock.patch.object(
            server_module, "RUNTIME_DIR", Path(self.temp_dir.name) / "jobs"
        )
        self.runtime_patch.start()
        self.registry = AnalysisTaskRegistry(ttl_seconds=60)
        self.server = server_module.create_server(
            "127.0.0.1",
            0,
            task_registry=self.registry,
            upload_idle_timeout=0.15,
        )
        self.port = int(self.server.server_address[1])
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=2)
        self.runtime_patch.stop()
        self.temp_dir.cleanup()

    def request(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, object]]:
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            payload = json.loads(response.read().decode("utf-8"))
            return response.status, payload
        finally:
            connection.close()

    def analyze_headers(self) -> dict[str, str]:
        return {
            "X-Request-Id": REQUEST_ID,
            "X-Filename": "sample.jpg",
            "Content-Type": "image/jpeg",
        }

    def test_success_records_upload_and_real_progress(self) -> None:
        image_bytes = _jpeg_bytes()
        state_at_analysis: dict[str, object] = {}

        def fake_analyze(
            input_path: Path,
            job_dir: Path,
            *,
            filename: str,
            settings: dict[str, object],
            progress_callback,
            is_cancelled,
        ) -> dict[str, object]:
            del input_path, job_dir, filename, settings
            state_at_analysis.update(self.registry.get(REQUEST_ID) or {})
            self.assertFalse(is_cancelled())
            progress_callback("solving", 25, "正在解算星图")
            progress_callback("catalog", 55, "正在匹配目录")
            return {"status": "complete", "metadata": {}, "wcs": {}, "objects": []}

        with mock.patch.object(server_module, "analyze_image", side_effect=fake_analyze):
            status, payload = self.request(
                "POST", "/api/analyze", body=image_bytes, headers=self.analyze_headers()
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload["requestId"], REQUEST_ID)
        self.assertEqual(state_at_analysis["receivedBytes"], len(image_bytes))
        self.assertEqual(state_at_analysis["totalBytes"], len(image_bytes))
        self.assertEqual(state_at_analysis["percent"], 15)

        status, progress = self.request("GET", f"/api/progress/{REQUEST_ID}")
        self.assertEqual(status, 200)
        self.assertEqual(set(progress), PROGRESS_KEYS)
        self.assertEqual(progress["status"], "complete")
        self.assertEqual(progress["stage"], "complete")
        self.assertEqual(progress["percent"], 100)

    def test_poll_and_delete_cancel_a_running_analysis(self) -> None:
        started = threading.Event()
        post_result: dict[str, object] = {}

        def fake_analyze(
            input_path: Path,
            job_dir: Path,
            *,
            filename: str,
            settings: dict[str, object],
            progress_callback,
            is_cancelled,
        ) -> dict[str, object]:
            del input_path, job_dir, filename, settings
            progress_callback("solving", 25, "正在解算星图")
            started.set()
            while not is_cancelled():
                time.sleep(0.005)
            raise RuntimeError("cancelled by test")

        def post_request() -> None:
            status, payload = self.request(
                "POST", "/api/analyze", body=_jpeg_bytes(), headers=self.analyze_headers()
            )
            post_result.update(status=status, payload=payload)

        with mock.patch.object(server_module, "analyze_image", side_effect=fake_analyze):
            worker = threading.Thread(target=post_request)
            worker.start()
            self.assertTrue(started.wait(2))

            status, progress = self.request("GET", f"/api/progress/{REQUEST_ID}")
            self.assertEqual(status, 200)
            self.assertEqual(progress["status"], "processing")
            self.assertEqual(progress["stage"], "solving")

            status, progress = self.request("DELETE", f"/api/progress/{REQUEST_ID}")
            self.assertEqual(status, 202)
            self.assertEqual(progress["status"], "cancelling")

            worker.join(timeout=2)
            self.assertFalse(worker.is_alive())

        self.assertEqual(post_result["status"], server_module.CLIENT_CLOSED_REQUEST)
        self.assertEqual(post_result["payload"]["status"], "cancelled")
        status, progress = self.request("GET", f"/api/progress/{REQUEST_ID}")
        self.assertEqual(status, 200)
        self.assertEqual(progress["status"], "cancelled")

    def test_upload_idle_timeout_returns_408_and_progress_state(self) -> None:
        request = (
            "POST /api/analyze HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{self.port}\r\n"
            f"X-Request-Id: {REQUEST_ID}\r\n"
            "X-Filename: sample.jpg\r\n"
            "Content-Type: image/jpeg\r\n"
            "Content-Length: 20\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).encode("ascii") + b"partial"

        with socket.create_connection(("127.0.0.1", self.port), timeout=2) as connection:
            connection.settimeout(2)
            connection.sendall(request)
            response = b""
            while True:
                chunk = connection.recv(4096)
                if not chunk:
                    break
                response += chunk

        self.assertIn(b" 408 ", response.split(b"\r\n", 1)[0])
        status, progress = self.request("GET", f"/api/progress/{REQUEST_ID}")
        self.assertEqual(status, 200)
        self.assertEqual(progress["status"], "timeout")
        self.assertEqual(progress["stage"], "upload")
        self.assertEqual(progress["receivedBytes"], len(b"partial"))

    def test_upload_can_resume_before_idle_deadline(self) -> None:
        self.server.upload_idle_timeout = 0.6
        image_bytes = _jpeg_bytes()
        request_headers = (
            "POST /api/analyze HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{self.port}\r\n"
            f"X-Request-Id: {REQUEST_ID}\r\n"
            "X-Filename: sample.jpg\r\n"
            "Content-Type: image/jpeg\r\n"
            f"Content-Length: {len(image_bytes)}\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).encode("ascii")

        def fake_analyze(*args, **kwargs) -> dict[str, object]:
            del args, kwargs
            return {"status": "complete", "metadata": {}, "wcs": {}, "objects": []}

        with mock.patch.object(server_module, "analyze_image", side_effect=fake_analyze):
            with socket.create_connection(("127.0.0.1", self.port), timeout=2) as connection:
                connection.settimeout(2)
                connection.sendall(request_headers + image_bytes[:40])
                # Cross at least one 250 ms read-poll timeout, but remain below
                # the configured idle deadline.
                time.sleep(0.32)
                connection.sendall(image_bytes[40:])
                response = b""
                while True:
                    chunk = connection.recv(4096)
                    if not chunk:
                        break
                    response += chunk

        self.assertIn(b" 200 ", response.split(b"\r\n", 1)[0])
        self.assertEqual(self.registry.get(REQUEST_ID)["receivedBytes"], len(image_bytes))

    def test_delete_interrupts_a_stalled_upload(self) -> None:
        self.server.upload_idle_timeout = 2
        request = (
            "POST /api/analyze HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{self.port}\r\n"
            f"X-Request-Id: {REQUEST_ID}\r\n"
            "X-Filename: sample.jpg\r\n"
            "Content-Type: image/jpeg\r\n"
            "Content-Length: 20\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).encode("ascii") + b"partial"

        with socket.create_connection(("127.0.0.1", self.port), timeout=2) as connection:
            connection.settimeout(2)
            connection.sendall(request)
            deadline = time.monotonic() + 1
            while self.registry.get(REQUEST_ID) is None and time.monotonic() < deadline:
                time.sleep(0.005)

            status, progress = self.request("DELETE", f"/api/progress/{REQUEST_ID}")
            self.assertEqual(status, 202)
            self.assertEqual(progress["status"], "cancelling")

            deadline = time.monotonic() + 1
            while (
                self.registry.get(REQUEST_ID)["status"] != "cancelled"
                and time.monotonic() < deadline
            ):
                time.sleep(0.005)

        self.assertEqual(self.registry.get(REQUEST_ID)["status"], "cancelled")

    def test_rejects_invalid_request_id(self) -> None:
        status, payload = self.request(
            "POST",
            "/api/analyze",
            body=_jpeg_bytes(),
            headers={"X-Request-Id": "ABC", "X-Filename": "sample.jpg"},
        )
        self.assertEqual(status, 400)
        self.assertIn("X-Request-Id", payload["error"])

    def test_native_export_uses_original_png_and_style_without_solving(self) -> None:
        job_id = "0123456789abcdef"
        job = server_module.RUNTIME_DIR / job_id
        job.mkdir()
        pixels = np.arange(48 * 64 * 3, dtype=np.uint16).reshape(48, 64, 3)
        (job / "input.png").write_bytes(imagecodecs.png_encode(pixels))
        (job / "results.json").write_text(json.dumps({
            "settings": {}, "objects": [], "constellationSegments": [],
            "brightStars": [{"id": "star", "label": "Star", "x": 32, "y": 24,
                             "magnitude": 3, "defaultVisible": True}],
        }), encoding="utf-8")
        with mock.patch("backend.pipeline.solve_plate") as solve:
            status, payload = self.request("POST", f"/api/export/{job_id}", body=json.dumps({
                "settings": {"brightStars": False, "deepSky": False, "constellations": False},
            }).encode(), headers={"X-Request-Id": REQUEST_ID, "Content-Type": "application/json"})
            solve.assert_not_called()
        self.assertEqual(status, 200)
        self.assertEqual(payload["export"]["bitDepth"], 16)
        self.assertEqual((payload["export"]["width"], payload["export"]["height"]), (64, 48))
        self.assertEqual(payload["export"]["format"], "PNG")
        output = job / Path(payload["downloadUrl"]).name
        np.testing.assert_array_equal(imagecodecs.png_decode(output.read_bytes()), pixels)
        self.assertEqual(self.registry.get(REQUEST_ID)["status"], "complete")
        status, marked = self.request("POST", f"/api/export/{job_id}", body=json.dumps({
            "settings": {"brightStars": True, "brightStarColor": "#ff0000", "annotationOpacity": 1},
        }).encode(), headers={"Content-Type": "application/json"})
        self.assertEqual(status, 200)
        marked_pixels = imagecodecs.png_decode((job / Path(marked["downloadUrl"]).name).read_bytes())
        self.assertFalse(np.array_equal(marked_pixels, pixels))
        np.testing.assert_array_equal(marked_pixels[24, 32], pixels[24, 32])
        self.assertNotEqual(payload["downloadUrl"], marked["downloadUrl"])
        np.testing.assert_array_equal(imagecodecs.png_decode((job / "input.png").read_bytes()), pixels)
        status, changed = self.request("POST", f"/api/export/{job_id}", body=json.dumps({
            "settings": {"catalogDepth": "bright"},
        }).encode(), headers={"Content-Type": "application/json"})
        self.assertEqual(status, 422)
        self.assertIn("重新解析", changed["error"])

    def test_export_rejects_invalid_job_and_invalid_json_settings(self) -> None:
        status, _ = self.request("POST", "/api/export/../", body=b"{}")
        self.assertEqual(status, 400)
        job = server_module.RUNTIME_DIR / "0123456789abcdef"
        job.mkdir()
        (job / "results.json").write_text("{}")
        status, _ = self.request("POST", "/api/export/0123456789abcdef", body=b'{"settings": []}')
        self.assertEqual(status, 422)

    def test_raw_upload_is_not_rejected_by_pillow_verification(self) -> None:
        def fake_analyze(*args, **kwargs):
            self.assertEqual(args[0].suffix, ".nef")
            return {"status": "complete", "metadata": {"is_raw": True}, "objects": []}
        with mock.patch.object(server_module, "analyze_image", side_effect=fake_analyze):
            status, payload = self.request("POST", "/api/analyze", body=b"decoder owns RAW validation",
                                           headers={"X-Request-Id": REQUEST_ID, "X-Filename": "camera.NEF"})
        self.assertEqual(status, 200)
        self.assertTrue(payload["metadata"]["is_raw"])

    def test_catalog_depth_query_reaches_pipeline(self) -> None:
        with mock.patch.object(server_module, "analyze_image", return_value={"status": "complete", "objects": []}) as analyze:
            status, _ = self.request("POST", "/api/analyze?catalogDepth=bright&starMagnitudeLimit=13.5",
                                     body=_jpeg_bytes(), headers=self.analyze_headers())
        self.assertEqual(status, 200)
        self.assertEqual(analyze.call_args.kwargs["settings"]["catalogDepth"], "bright")
        self.assertEqual(float(analyze.call_args.kwargs["settings"]["starMagnitudeLimit"]), 13.5)


if __name__ == "__main__":
    unittest.main()
