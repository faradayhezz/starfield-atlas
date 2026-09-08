from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import re
import select
import sys
import traceback
import urllib.parse
import uuid
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from time import monotonic
from typing import Any

from PIL import Image, UnidentifiedImageError

from .analysis_tasks import AnalysisTaskRegistry, TaskAlreadyExistsError
from .app_paths import JOBS_DIR, RESOURCE_ROOT
from .annotate import normalize_font_weight, normalize_hex_color
from .deep_sky_media import resolve_media_file
from .hips_proxy import public_hips_manifest, resolve_hips_resource
from .legacy_sky_map import public_manifest, resolve_layer_tile
from .pipeline import AnalysisCancelled, DEFAULT_SETTINGS, analyze_image
from .pipeline import reexport_image
from .image_io import ALLOWED_SUFFIXES, RAW_SUFFIXES
from .sky_catalog import public_sky_catalog


FRONTEND_DIST = RESOURCE_ROOT / "frontend" / "dist"
RUNTIME_DIR = JOBS_DIR
MAX_UPLOAD_BYTES = 200 * 1024 * 1024
UPLOAD_CHUNK_BYTES = 1024 * 1024
UPLOAD_IDLE_TIMEOUT_SECONDS = 15.0
CLIENT_CLOSED_REQUEST = 499
REQUEST_ID_PATTERN = re.compile(r"[0-9a-f]{32}")
TASK_REGISTRY = AnalysisTaskRegistry()


def _bool(value: str | None, fallback: bool) -> bool:
    if value is None:
        return fallback
    normalized = value.lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return fallback


def _float(value: str | None, fallback: float) -> float:
    if value is None:
        return fallback
    try:
        return min(100.0, max(0.0, float(value)))
    except ValueError:
        return fallback


def _hex_color(value: str | None, fallback: str) -> str:
    return normalize_hex_color(value, fallback)


def _font_weight(value: str | None, fallback: int) -> int:
    return normalize_font_weight(value, fallback)


def _safe_filename(value: str | None) -> str:
    decoded = urllib.parse.unquote(value or "sky-photo.jpg")
    name = Path(decoded).name
    name = re.sub(r"[^\w.\- ()\u4e00-\u9fff]", "_", name, flags=re.UNICODE)
    return name[:160] or "sky-photo.jpg"


class SkyThreadingHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[BaseHTTPRequestHandler],
        *,
        task_registry: AnalysisTaskRegistry,
        upload_idle_timeout: float,
    ) -> None:
        super().__init__(server_address, handler_class)
        self.task_registry = task_registry
        self.upload_idle_timeout = upload_idle_timeout


class SkyHandler(BaseHTTPRequestHandler):
    server_version = "SkyAtlasLocal/1.0"
    # An unbuffered request stream lets upload reads return whatever bytes are
    # currently available. This is required for accurate progress and for
    # checking cancellation without corrupting a BufferedReader after timeout.
    rbufsize = 0

    def log_message(self, format: str, *args: Any) -> None:
        if sys.stdout is not None:
            sys.stdout.write("[%s] %s\n" % (self.log_date_time_string(), format % args))

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Allow", "GET, POST, DELETE, OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/health":
            self._json({"status": "ok", "service": "星图寻迹"})
            return
        if parsed.path.startswith("/api/progress/"):
            self._serve_progress(parsed.path)
            return
        if parsed.path == "/api/sky-map/manifest":
            manifest = public_manifest()
            manifest["hips"] = public_hips_manifest()
            self._json(manifest)
            return
        if parsed.path == "/api/sky-map/catalog":
            self._json(public_sky_catalog())
            return
        if parsed.path.startswith("/api/sky-map/hips/"):
            self._serve_hips_resource(parsed.path)
            return
        if parsed.path.startswith("/api/sky-map/tiles/"):
            self._serve_sky_map_tile(parsed)
            return
        if parsed.path.startswith("/api/deep-sky-media/"):
            self._serve_deep_sky_media(parsed.path)
            return
        if parsed.path.startswith("/api/artifacts/"):
            self._serve_artifact(parsed.path, attachment=False)
            return
        if parsed.path.startswith("/api/download/"):
            self._serve_artifact(parsed.path, attachment=True)
            return
        self._serve_frontend(parsed.path)

    def do_DELETE(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        request_id = self._progress_request_id(parsed.path)
        if request_id is None:
            status = (
                HTTPStatus.BAD_REQUEST
                if parsed.path.startswith("/api/progress/")
                else HTTPStatus.NOT_FOUND
            )
            self._json({"status": "error", "error": "无效的进度请求编号"}, status)
            return
        snapshot, accepted = self._task_registry().cancel(request_id)
        if snapshot is None:
            self._json({"status": "error", "error": "进度记录不存在或已过期"}, HTTPStatus.NOT_FOUND)
            return
        self._json(snapshot, HTTPStatus.ACCEPTED if accepted else HTTPStatus.OK)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.startswith("/api/export/"):
            self._export_result(parsed.path)
            return
        if parsed.path != "/api/analyze":
            self._json({"status": "error", "error": "接口不存在"}, HTTPStatus.NOT_FOUND)
            return
        request_id = self.headers.get("X-Request-Id", "").strip()
        if REQUEST_ID_PATTERN.fullmatch(request_id) is None:
            self._json(
                {"status": "error", "error": "X-Request-Id 必须是 32 位小写十六进制字符串"},
                HTTPStatus.BAD_REQUEST,
            )
            return
        length_text = self.headers.get("Content-Length")
        if not length_text:
            self._json({"status": "error", "error": "请求缺少文件长度"}, HTTPStatus.LENGTH_REQUIRED)
            return
        try:
            length = int(length_text)
        except ValueError:
            self._json({"status": "error", "error": "无效的文件长度"}, HTTPStatus.BAD_REQUEST)
            return
        if length <= 0 or length > MAX_UPLOAD_BYTES:
            self._json(
                {"status": "error", "error": "照片必须小于 200 MB"},
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            )
            return

        filename = _safe_filename(self.headers.get("X-Filename"))
        suffix = Path(filename).suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            self._json(
                {"status": "error", "error": "支持 JPG、PNG、TIFF 及常见相机 RAW（ARW、CR2/CR3、NEF、DNG 等）"},
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
            )
            return

        query = urllib.parse.parse_qs(parsed.query)
        settings = {
            "deepSky": _bool(_one(query, "deepSky"), bool(DEFAULT_SETTINGS["deepSky"])),
            "brightStars": _bool(_one(query, "brightStars"), bool(DEFAULT_SETTINGS["brightStars"])),
            "constellations": _bool(_one(query, "constellations"), bool(DEFAULT_SETTINGS["constellations"])),
            "dsoThreshold": _float(_one(query, "dsoThreshold"), float(DEFAULT_SETTINGS["dsoThreshold"])),
            "starThreshold": _float(_one(query, "starThreshold"), float(DEFAULT_SETTINGS["starThreshold"])),
            "constellationStrength": _float(_one(query, "constellationStrength"), float(DEFAULT_SETTINGS["constellationStrength"])),
            "deepSkyColor": _hex_color(
                _one(query, "deepSkyColor"), str(DEFAULT_SETTINGS["deepSkyColor"])
            ),
            "brightStarColor": _hex_color(
                _one(query, "brightStarColor"), str(DEFAULT_SETTINGS["brightStarColor"])
            ),
            "constellationColor": _hex_color(
                _one(query, "constellationColor"), str(DEFAULT_SETTINGS["constellationColor"])
            ),
            "fontWeight": _font_weight(
                _one(query, "fontWeight"), int(DEFAULT_SETTINGS["fontWeight"])
            ),
            "highContrast": _bool(
                _one(query, "highContrast"), bool(DEFAULT_SETTINGS["highContrast"])
            ),
            "annotationOpacity": _one(query, "annotationOpacity") or DEFAULT_SETTINGS["annotationOpacity"],
            "annotationLineWidth": _one(query, "annotationLineWidth") or DEFAULT_SETTINGS["annotationLineWidth"],
            "annotationFontSize": _one(query, "annotationFontSize") or DEFAULT_SETTINGS["annotationFontSize"],
            "markerStyle": _one(query, "markerStyle") or DEFAULT_SETTINGS["markerStyle"],
            "labelDensity": _one(query, "labelDensity") or DEFAULT_SETTINGS["labelDensity"],
            "starMagnitudeLimit": _one(query, "starMagnitudeLimit") or DEFAULT_SETTINGS["starMagnitudeLimit"],
            "includeCatalogOnly": _bool(_one(query, "includeCatalogOnly"), False),
            "catalogDepth": _one(query, "catalogDepth") or DEFAULT_SETTINGS["catalogDepth"],
        }
        registry = self._task_registry()
        try:
            registry.register(request_id, total_bytes=length)
        except TaskAlreadyExistsError:
            self._json(
                {"status": "error", "error": "这个请求编号正在使用或尚未过期"},
                HTTPStatus.CONFLICT,
            )
            return

        job_id = uuid.uuid4().hex[:16]
        job_dir = RUNTIME_DIR / job_id
        try:
            job_dir.mkdir(parents=True, exist_ok=False)
        except OSError as exc:
            registry.update(
                request_id,
                status="error",
                stage="upload",
                message=f"无法创建任务目录：{exc}",
            )
            self._json(
                {"status": "error", "error": "无法创建本地任务目录"},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return
        input_path = job_dir / f"input{suffix}"

        sha256 = hashlib.sha256()
        remaining = length
        received = 0
        upload_timed_out = False
        upload_error: OSError | None = None
        upload_idle_timeout = self._upload_idle_timeout()
        last_upload_data = monotonic()
        try:
            with input_path.open("wb") as handle:
                while remaining:
                    if registry.is_cancelled(request_id):
                        break
                    idle_elapsed = monotonic() - last_upload_data
                    wait_seconds = min(0.25, max(0.0, upload_idle_timeout - idle_elapsed))
                    readable, _, _ = select.select([self.connection], [], [], wait_seconds)
                    if not readable:
                        if monotonic() - last_upload_data >= upload_idle_timeout:
                            upload_timed_out = True
                            break
                        continue
                    chunk = self.rfile.read(min(UPLOAD_CHUNK_BYTES, remaining))
                    if not chunk:
                        break
                    last_upload_data = monotonic()
                    handle.write(chunk)
                    sha256.update(chunk)
                    received += len(chunk)
                    remaining -= len(chunk)
                    registry.update(
                        request_id,
                        status="uploading",
                        stage="upload",
                        percent=min(15, round(received * 15 / length)),
                        message=f"正在接收照片（{received * 100 / length:.0f}%）",
                        received_bytes=received,
                    )
        except OSError as exc:
            upload_error = exc

        if registry.is_cancelled(request_id):
            self._respond_cancelled(request_id, "上传已取消")
            return
        if upload_timed_out:
            registry.update(
                request_id,
                status="timeout",
                stage="upload",
                message="照片上传超过 15 秒没有新数据",
                received_bytes=received,
            )
            self._json(
                {"status": "timeout", "error": "照片上传超时，请重试"},
                HTTPStatus.REQUEST_TIMEOUT,
            )
            return
        if upload_error is not None:
            registry.update(
                request_id,
                status="error",
                stage="upload",
                message=f"照片上传失败：{upload_error}",
                received_bytes=received,
            )
            self._json(
                {"status": "error", "error": "照片上传连接异常，请重试"},
                HTTPStatus.BAD_REQUEST,
            )
            return
        if remaining:
            registry.update(
                request_id,
                status="error",
                stage="upload",
                message="照片传输不完整",
                received_bytes=received,
            )
            self._json({"status": "error", "error": "照片传输不完整"}, HTTPStatus.BAD_REQUEST)
            return

        registry.update(
            request_id,
            status="processing",
            stage="validation",
            percent=15,
            message="正在校验照片",
            received_bytes=received,
        )

        def report_progress(stage: str, percent: int, message: str) -> None:
            registry.update(
                request_id,
                status="processing",
                stage=stage,
                percent=percent,
                message=message,
            )

        def is_cancelled() -> bool:
            return registry.is_cancelled(request_id)

        try:
            if is_cancelled():
                self._respond_cancelled(request_id)
                return
            # RAW and 16/32-bit TIFF must be validated by their native decoder;
            # Pillow cannot open many valid camera containers or RGB float TIFF.
            if suffix not in RAW_SUFFIXES and suffix not in {".tif", ".tiff"}:
                with Image.open(input_path) as image:
                    image.verify()
            result = analyze_image(
                input_path,
                job_dir,
                filename=filename,
                settings=settings,
                progress_callback=report_progress,
                is_cancelled=is_cancelled,
            )
            if is_cancelled():
                self._respond_cancelled(request_id)
                return
            result["sha256"] = sha256.hexdigest()
            result["requestId"] = request_id
            (job_dir / "results.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            registry.update(
                request_id,
                status="complete",
                stage="complete",
                percent=100,
                message="识别与标注已完成",
            )
            self._json(result)
        except (UnidentifiedImageError, OSError) as exc:
            if is_cancelled():
                self._respond_cancelled(request_id)
                return
            registry.update(
                request_id,
                status="error",
                stage="validation",
                message=f"无法读取这张照片：{exc}",
            )
            self._json(
                {"status": "error", "error": f"无法读取这张照片：{exc}"},
                HTTPStatus.UNPROCESSABLE_ENTITY,
            )
        except AnalysisCancelled:
            self._respond_cancelled(request_id)
        except Exception as exc:  # noqa: BLE001 - return a safe user message, log details locally
            if is_cancelled():
                self._respond_cancelled(request_id)
                return
            traceback.print_exc()
            registry.update(
                request_id,
                status="error",
                stage="error",
                message=str(exc),
            )
            self._json(
                {"status": "error", "error": str(exc)}, HTTPStatus.UNPROCESSABLE_ENTITY
            )

    def _export_result(self, path: str) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 3 or not re.fullmatch(r"[0-9a-f]{16}", parts[2]):
            self._json({"error": "无效的识别记录编号"}, HTTPStatus.BAD_REQUEST)
            return
        job_dir = RUNTIME_DIR / parts[2]
        if not (job_dir / "results.json").is_file():
            self._json({"error": "识别记录不存在，请先完成识别"}, HTTPStatus.NOT_FOUND)
            return
        request_id = self.headers.get("X-Request-Id", "").strip()
        if request_id and REQUEST_ID_PATTERN.fullmatch(request_id) is None:
            self._json({"error": "无效的导出请求编号"}, HTTPStatus.BAD_REQUEST)
            return
        registry = self._task_registry()
        registered = False
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 32768:
                raise ValueError("导出设置长度必须在 1–32768 字节之间")
            self.connection.settimeout(self._upload_idle_timeout())
            chunks: list[bytes] = []
            remaining = length
            while remaining:
                chunk = self.rfile.read(remaining)
                if not chunk:
                    raise ValueError("导出设置传输不完整")
                chunks.append(chunk)
                remaining -= len(chunk)
            payload = json.loads(b"".join(chunks))
            if not isinstance(payload, dict) or not isinstance(payload.get("settings", {}), dict):
                raise ValueError("导出设置必须是 JSON 对象")
            self.connection.settimeout(None)
            if request_id:
                registry.register(request_id, total_bytes=length)
                registered = True
                registry.update(request_id, status="processing", stage="validation", percent=15,
                                message="正在准备原始尺寸导出", received_bytes=length)
            def is_cancelled() -> bool:
                return bool(request_id and registry.is_cancelled(request_id))
            def progress(stage: str, percent: int, message: str) -> None:
                if request_id:
                    registry.update(request_id, status="processing", stage=stage,
                                    percent=percent, message=message)
            result = reexport_image(job_dir, payload.get("settings", {}),
                                    is_cancelled=is_cancelled, progress_callback=progress)
            if is_cancelled():
                self._respond_cancelled(request_id, "导出已取消")
                return
            if request_id:
                registry.update(request_id, status="complete", stage="complete", percent=100,
                                message="原始尺寸标注已导出")
                result["requestId"] = request_id
            self._json(result)
        except TaskAlreadyExistsError:
            self._json({"error": "这个导出请求编号正在使用"}, HTTPStatus.CONFLICT)
        except AnalysisCancelled:
            self._respond_cancelled(request_id, "导出已取消")
        except (ValueError, OSError) as exc:
            if registered:
                registry.update(request_id, status="error", stage="error", message=str(exc))
            self._json({"status": "error", "error": str(exc)}, HTTPStatus.UNPROCESSABLE_ENTITY)

    def _task_registry(self) -> AnalysisTaskRegistry:
        return getattr(self.server, "task_registry", TASK_REGISTRY)

    def _upload_idle_timeout(self) -> float:
        value = getattr(self.server, "upload_idle_timeout", UPLOAD_IDLE_TIMEOUT_SECONDS)
        try:
            return max(0.05, float(value))
        except (TypeError, ValueError):
            return UPLOAD_IDLE_TIMEOUT_SECONDS

    @staticmethod
    def _progress_request_id(path: str) -> str | None:
        parts = path.split("/")
        if len(parts) != 4 or parts[:3] != ["", "api", "progress"]:
            return None
        request_id = parts[3]
        return request_id if REQUEST_ID_PATTERN.fullmatch(request_id) else None

    def _serve_progress(self, path: str) -> None:
        request_id = self._progress_request_id(path)
        if request_id is None:
            self._json({"status": "error", "error": "无效的进度请求编号"}, HTTPStatus.BAD_REQUEST)
            return
        snapshot = self._task_registry().get(request_id)
        if snapshot is None:
            self._json({"status": "error", "error": "进度记录不存在或已过期"}, HTTPStatus.NOT_FOUND)
            return
        self._json(snapshot)

    def _respond_cancelled(self, request_id: str, message: str = "识别已取消") -> None:
        self._task_registry().mark_cancelled(request_id, message)
        self._json(
            {"status": "cancelled", "error": message},
            CLIENT_CLOSED_REQUEST,
        )

    def _serve_artifact(self, path: str, *, attachment: bool) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        _, _, job_id, filename = parts
        if not re.fullmatch(r"[0-9a-f]{16}", job_id) or Path(filename).name != filename:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        file_path = (RUNTIME_DIR / job_id / filename).resolve()
        try:
            file_path.relative_to(RUNTIME_DIR.resolve())
        except ValueError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(file_path.stat().st_size))
        self.send_header("Cache-Control", "private, max-age=3600")
        if attachment:
            self.send_header("Content-Disposition", f'attachment; filename="{file_path.name}"')
        self.end_headers()
        with file_path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                self.wfile.write(chunk)

    def _serve_deep_sky_media(self, path: str) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 3:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        file_path = resolve_media_file(parts[2])
        if file_path is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "image/webp")
        self.send_header("Content-Length", str(file_path.stat().st_size))
        self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.end_headers()
        with file_path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                self.wfile.write(chunk)

    def _serve_sky_map_tile(self, parsed: urllib.parse.ParseResult) -> None:
        parts = parsed.path.strip("/").split("/")
        if parts[:3] != ["api", "sky-map", "tiles"] or len(parts) not in {6, 7}:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        layer = "ls-dr11" if len(parts) == 6 else parts[3]
        offset = 3 if len(parts) == 6 else 4
        try:
            z = int(parts[offset])
            x = int(parts[offset + 1])
            y = int(Path(parts[offset + 2]).stem)
        except ValueError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if Path(parts[offset + 2]).suffix.lower() != ".jpg":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        query = urllib.parse.parse_qs(parsed.query)
        online = _bool(_one(query, "online"), False)
        resolved = resolve_layer_tile(layer, z, x, y, allow_online=online)
        if resolved is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        file_path, source = resolved
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(file_path.stat().st_size))
        temporary_fallback = (
            online
            and layer == "filled"
            and source in {"2mass-bundled", "2mass-derived-fallback"}
        )
        cache_control = (
            "public, max-age=300, must-revalidate"
            if temporary_fallback
            else "public, max-age=31536000, immutable"
        )
        self.send_header("Cache-Control", cache_control)
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("X-Sky-Map-Layer", layer)
        self.send_header("X-Sky-Map-Source", source)
        self.end_headers()
        with file_path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                self.wfile.write(chunk)

    def _serve_hips_resource(self, path: str) -> None:
        parts = path.strip("/").split("/")
        if parts[:3] != ["api", "sky-map", "hips"] or len(parts) < 5:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        survey_id = parts[3]
        relative_path = "/".join(parts[4:])
        resolved = resolve_hips_resource(survey_id, relative_path)
        if resolved is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        file_path, content_type, source = resolved
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(file_path.stat().st_size))
        self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("X-Sky-Map-Source", f"hips-{source}")
        self.end_headers()
        with file_path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                self.wfile.write(chunk)

    def _serve_frontend(self, path: str) -> None:
        requested = path.lstrip("/") or "index.html"
        candidate = (FRONTEND_DIST / requested).resolve()
        try:
            candidate.relative_to(FRONTEND_DIST.resolve())
        except ValueError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not candidate.is_file():
            candidate = FRONTEND_DIST / "index.html"
        if not candidate.is_file():
            self._json(
                {"status": "error", "error": "前端尚未构建，请先运行 scripts/setup.ps1"},
                HTTPStatus.SERVICE_UNAVAILABLE,
            )
            return
        content = candidate.read_bytes()
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        if candidate.suffix in {".js", ".css"}:
            content_type += "; charset=utf-8"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache" if candidate.name == "index.html" else "public, max-age=31536000, immutable")
        self.end_headers()
        self.wfile.write(content)

    def _json(self, payload: dict[str, Any], status: int | HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            # The progress record remains authoritative when a browser aborts
            # its original POST before the worker notices cancellation.
            return


def _one(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key)
    return values[0] if values else None


def create_server(
    host: str = "127.0.0.1",
    port: int = 0,
    *,
    task_registry: AnalysisTaskRegistry | None = None,
    upload_idle_timeout: float = UPLOAD_IDLE_TIMEOUT_SECONDS,
) -> ThreadingHTTPServer:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    return SkyThreadingHTTPServer(
        (host, port),
        SkyHandler,
        task_registry=task_registry or TASK_REGISTRY,
        upload_idle_timeout=upload_idle_timeout,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="星图寻迹本地识别服务")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open", action="store_true", help="启动后在默认浏览器打开应用")
    args = parser.parse_args()
    server = create_server(args.host, args.port)
    actual_port = int(server.server_address[1])
    url = f"http://{args.host}:{actual_port}"
    print(f"星图寻迹已启动：{url}")
    print("照片仅保存在当前项目的 .runtime 目录并在本机处理。按 Ctrl+C 停止。")
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n正在停止…")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
