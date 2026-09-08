"""Real NASA SkyView survey cutouts for catalog objects without curated photos.

Queries contain public catalog coordinates only. They never contain an uploaded
photograph, filename, camera metadata, or an arbitrary caller-provided URL.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import re
import threading
import urllib.parse
import urllib.request
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from .app_paths import USER_DATA_ROOT

DATA_DIR = Path(__file__).resolve().parent / "data" / "nasa-survey-cutouts"
CACHE_DIR = USER_DATA_ROOT / "nasa-survey-cutouts"
SERVICE_URL = "https://skyview.gsfc.nasa.gov/current/cgi/runquery.pl"
DOCS_URL = "https://skyview.gsfc.nasa.gov/current/docs/batchpage.html"
USAGE_URL = "https://skyview.gsfc.nasa.gov/current/help/faq.html"
SURVEY = "DSS2 Red"
PIXELS = 384
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
TIMEOUT_SECONDS = 18
SAFE_FILENAME = re.compile(r"skyview-[a-z0-9-]{1,45}-[0-9a-f]{16}\.webp\Z")
_POOL = ThreadPoolExecutor(max_workers=3, thread_name_prefix="nasa-cutout")
_LOCK = threading.Lock()
_IN_FLIGHT: dict[str, Future] = {}


class MediaUnavailableError(RuntimeError):
    pass


class UnknownCatalogObjectError(ValueError):
    pass


def _normalize_id(value: str) -> str:
    return re.sub(r"\s+", "", value).upper()


@lru_cache(maxsize=1)
def _catalog_objects() -> dict[str, Any]:
    # Lazy import avoids the catalog -> media_for -> survey module cycle.
    from .catalog import load_deep_sky_catalog
    objects = load_deep_sky_catalog()
    result = {_normalize_id(item.name): item for item in objects}
    for item in objects:
        if item.messier:
            result.setdefault(f"M{int(item.messier)}", item)
    return result


def catalog_object(catalog_id: str):
    if not isinstance(catalog_id, str) or not catalog_id or len(catalog_id) > 100:
        raise UnknownCatalogObjectError("未知的深空天体目录编号")
    item = _catalog_objects().get(_normalize_id(catalog_id))
    if item is None or not (math.isfinite(item.ra_deg) and math.isfinite(item.dec_deg)):
        raise UnknownCatalogObjectError("未知的深空天体目录编号")
    return item


def query_url(item) -> str:
    field = min(8.0, max(.08, float(item.major_arcmin or 0) / 60 * 2))
    return SERVICE_URL + "?" + urllib.parse.urlencode({
        "Position": f"{item.ra_deg:.7f},{item.dec_deg:.7f}",
        "Survey": SURVEY, "Coordinates": "J2000", "Projection": "Tan",
        "Pixels": PIXELS, "Size": f"{field:.6f}", "Return": "JPEG",
    })


def _metadata_filename(catalog_id: str) -> str:
    return hashlib.sha256(catalog_id.encode("utf-8")).hexdigest() + ".json"


@lru_cache(maxsize=1)
def _bundled_records() -> dict[str, Any]:
    try:
        payload = json.loads((DATA_DIR / "manifest.json").read_text(encoding="utf-8"))
        return payload.get("objects", {}) if payload.get("schemaVersion") == 1 else {}
    except (OSError, ValueError, AttributeError):
        return {}


def _public_record(record: dict[str, Any], item, directory: Path) -> dict[str, Any] | None:
    filename = record.get("thumbnailFile", "")
    if (record.get("catalogId") != item.name or record.get("sourceUrl") != query_url(item)
            or not isinstance(filename, str) or not SAFE_FILENAME.fullmatch(filename)):
        return None
    candidate = directory / "images" / filename
    if not candidate.is_file():
        return None
    return {
        "thumbnail": "/api/deep-sky-media/" + filename,
        "thumbnailWidth": record["thumbnailWidth"], "thumbnailHeight": record["thumbnailHeight"],
        "sourceUrl": record["sourceUrl"], "imageCredit": record["imageCredit"],
        "mediaProvider": "NASA SkyView / DSS2", "mediaUsageUrl": USAGE_URL,
        "mediaKind": "survey", "note": record["note"], "catalogId": item.name,
    }


def cached_survey_media(catalog_id: str) -> dict[str, Any]:
    try:
        item = catalog_object(catalog_id)
    except UnknownCatalogObjectError:
        return {}
    for directory, raw in ((DATA_DIR, _bundled_records().get(item.name)), (CACHE_DIR, None)):
        if directory == CACHE_DIR:
            try:
                raw = json.loads((directory / _metadata_filename(item.name)).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
        if isinstance(raw, dict):
            try:
                if result := _public_record(raw, item, directory):
                    return result
            except (KeyError, TypeError):
                continue
    return {}


def _request_image(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "StarfieldAtlas/1.3.0 (educational astronomy survey viewer)"})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        final = urllib.parse.urlparse(response.geturl())
        if final.scheme != "https" or final.hostname != "skyview.gsfc.nasa.gov":
            raise MediaUnavailableError("NASA 巡天服务返回了未验证的图片地址")
        payload = response.read(MAX_RESPONSE_BYTES + 1)
        if len(payload) > MAX_RESPONSE_BYTES:
            raise MediaUnavailableError("NASA 巡天图片超出大小限制")
        if not payload.startswith(b"\xff\xd8\xff"):
            raise MediaUnavailableError("NASA 巡天服务暂未返回有效图片")
        return payload


def download_survey_record(catalog_id: str, directory: Path | None = None) -> dict[str, Any]:
    directory = directory if directory is not None else CACHE_DIR
    item = catalog_object(catalog_id)
    url = query_url(item)
    try:
        payload = _request_image(url)
        with Image.open(io.BytesIO(payload)) as source:
            if source.size != (PIXELS, PIXELS) or source.format != "JPEG":
                raise MediaUnavailableError("NASA 巡天图片尺寸或格式不符合请求")
            source.load()
            image = source.convert("RGB")
        try:
            # Blank/no-data cutouts should not masquerade as object imagery.
            if all(low == high for low, high in image.getextrema()):
                raise MediaUnavailableError("NASA 巡天目录在该坐标没有可用图像")
            output = io.BytesIO()
            image.save(output, "WEBP", quality=88, method=5)
            encoded = output.getvalue()
        finally:
            image.close()
    except MediaUnavailableError:
        raise
    except (OSError, ValueError, UnidentifiedImageError) as exc:
        raise MediaUnavailableError("NASA 巡天图片暂时无法下载，请稍后重试") from exc
    digest = hashlib.sha256(encoded).hexdigest()
    slug = re.sub(r"[^a-z0-9]+", "-", item.name.lower()).strip("-")[:45]
    filename = f"skyview-{slug}-{digest[:16]}.webp"
    record = {
        "catalogId": item.name, "raDeg": item.ra_deg, "decDeg": item.dec_deg,
        "survey": SURVEY, "sourceUrl": url, "docsUrl": DOCS_URL,
        "thumbnailFile": filename, "thumbnailSha256": digest,
        "thumbnailWidth": PIXELS, "thumbnailHeight": PIXELS,
        "imageCredit": "Digitized Sky Survey / STScI / Palomar Observatory / AAO; delivered by NASA GSFC SkyView",
        "note": "NASA SkyView / DSS2 巡天图，以该天体的公开目录坐标为中心；不是哈勃特写，暗弱目标可能无法在此巡天深度下分辨。",
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (directory / "images").mkdir(parents=True, exist_ok=True)
    image_path = directory / "images" / filename
    image_path.write_bytes(encoded)
    metadata_path = directory / _metadata_filename(item.name)
    temporary_path = metadata_path.with_suffix(".json.part")
    temporary_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary_path.replace(metadata_path)
    return record


def fetch_survey_media(catalog_id: str) -> dict[str, Any]:
    item = catalog_object(catalog_id)
    if cached := cached_survey_media(item.name):
        return cached
    with _LOCK:
        for key, pending in list(_IN_FLIGHT.items()):
            if pending.done():
                _IN_FLIGHT.pop(key, None)
        future = _IN_FLIGHT.get(item.name)
        if future is None:
            if len(_IN_FLIGHT) >= 24:
                raise MediaUnavailableError("NASA 配图加载队列繁忙，请稍后重试")
            future = _POOL.submit(download_survey_record, item.name)
            _IN_FLIGHT[item.name] = future
    try:
        record = future.result(timeout=22)
        result = _public_record(record, item, CACHE_DIR)
        if not result:
            raise MediaUnavailableError("NASA 配图缓存无法读取")
        return result
    except TimeoutError as exc:
        raise MediaUnavailableError("NASA 配图请求超时，请稍后重试") from exc
    finally:
        if future.done():
            with _LOCK:
                if _IN_FLIGHT.get(item.name) is future:
                    _IN_FLIGHT.pop(item.name, None)


def resolve_survey_file(filename: str) -> Path | None:
    if not SAFE_FILENAME.fullmatch(filename):
        return None
    for directory in (DATA_DIR, CACHE_DIR):
        candidate = directory / "images" / filename
        if candidate.is_file():
            return candidate
    return None
