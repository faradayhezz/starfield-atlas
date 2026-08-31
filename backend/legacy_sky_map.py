from __future__ import annotations

import json
import hashlib
import math
import os
import threading
import urllib.request
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from .app_paths import RESOURCE_ROOT, SKY_MAP_CACHE_DIR

PACK_ROOT = RESOURCE_ROOT / "backend" / "data" / "legacy-survey-dr11"
TILE_ROOT = PACK_ROOT / "tiles"
MANIFEST_PATH = PACK_ROOT / "manifest.json"
ALL_SKY_PACK_ROOT = RESOURCE_ROOT / "backend" / "data" / "2mass-allsky"
ALL_SKY_TILE_ROOT = ALL_SKY_PACK_ROOT / "tiles"
ALL_SKY_MANIFEST_PATH = ALL_SKY_PACK_ROOT / "manifest.json"
CACHE_ROOT = SKY_MAP_CACHE_DIR / "ls-dr11"
COMPOSITE_CACHE_ROOT = SKY_MAP_CACHE_DIR / "filled-2mass-v1"
OFFICIAL_TILE_TEMPLATE = (
    "https://a.legacysurvey.org/viewer/ls-dr11/1/{z}/{x}/{y}.jpg"
)
MAX_ZOOM = 14
MAX_TILE_BYTES = 2 * 1024 * 1024
ALLOWED_LAYERS = {"filled", "ls-dr11", "2mass-color"}
WEB_MERCATOR_DECLINATION_LIMIT = 85.05112878
WEB_MERCATOR_SKY_FRACTION = math.sin(
    math.radians(WEB_MERCATOR_DECLINATION_LIMIT)
)
_tile_locks: dict[tuple[str, int, int, int], list[Any]] = {}
_tile_locks_guard = threading.Lock()
_manifest_cache: dict[Path, tuple[int, int, dict[str, Any]]] = {}
_manifest_cache_guard = threading.Lock()
_all_sky_availability_cache: dict[tuple[str, int, int], bool] = {}
_all_sky_availability_guard = threading.Lock()


def _coordinates(z: int, x: int, y: int) -> tuple[int, int, int] | None:
    if not all(isinstance(value, int) for value in (z, x, y)):
        return None
    if not 0 <= z <= MAX_ZOOM:
        return None
    limit = 2**z
    if not 0 <= x < limit or not 0 <= y < limit:
        return None
    return z, x, y


def _tile_file(root: Path, z: int, x: int, y: int) -> Path:
    return root / str(z) / str(x) / f"{y}.jpg"


def _valid_tile(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < 100:
        return False
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            return image.format == "JPEG" and image.size == (256, 256)
    except (OSError, ValueError):
        return False


@contextmanager
def _tile_lock(layer: str, z: int, x: int, y: int):
    key = (layer, z, x, y)
    with _tile_locks_guard:
        entry = _tile_locks.get(key)
        if entry is None:
            entry = [threading.Lock(), 0]
            _tile_locks[key] = entry
        entry[1] += 1
    lock = entry[0]
    try:
        with lock:
            yield
    finally:
        with _tile_locks_guard:
            entry[1] -= 1
            if entry[1] == 0 and _tile_locks.get(key) is entry:
                _tile_locks.pop(key, None)


def _write_jpeg(image: Image.Image, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(
        f".jpg.{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex}.part"
    )
    try:
        image.convert("RGB").save(
            temporary,
            format="JPEG",
            quality=90,
            subsampling=0,
            optimize=True,
        )
        if not _valid_tile(temporary):
            raise OSError("generated sky-map tile failed validation")
        temporary.replace(destination)
    except (OSError, ValueError):
        temporary.unlink(missing_ok=True)
        raise


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        stat = path.stat()
    except OSError:
        with _manifest_cache_guard:
            _manifest_cache.pop(path, None)
        return {}
    cache_key = (stat.st_mtime_ns, stat.st_size)
    with _manifest_cache_guard:
        cached = _manifest_cache.get(path)
        if cached is not None and cached[:2] == cache_key:
            return cached[2]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    parsed = payload if isinstance(payload, dict) else {}
    with _manifest_cache_guard:
        _manifest_cache[path] = (stat.st_mtime_ns, stat.st_size, parsed)
    return parsed


def manifest() -> dict[str, Any]:
    return _read_manifest(MANIFEST_PATH)


def all_sky_manifest() -> dict[str, Any]:
    return _read_manifest(ALL_SKY_MANIFEST_PATH)


def all_sky_pack_available(*, refresh: bool = False) -> bool:
    """Verify the declared offline pyramid before advertising all-sky coverage."""
    candidate = all_sky_manifest()
    try:
        stat = ALL_SKY_MANIFEST_PATH.stat()
        cache_key = (
            str(ALL_SKY_MANIFEST_PATH.resolve()),
            stat.st_mtime_ns,
            stat.st_size,
        )
    except OSError:
        with _all_sky_availability_guard:
            _all_sky_availability_cache.clear()
        return False
    if not refresh:
        with _all_sky_availability_guard:
            cached = _all_sky_availability_cache.get(cache_key)
            if cached is not None:
                return cached

    def finish(result: bool) -> bool:
        with _all_sky_availability_guard:
            _all_sky_availability_cache.clear()
            _all_sky_availability_cache[cache_key] = result
        return result

    try:
        min_zoom = int(candidate["minZoom"])
        max_zoom = int(candidate["maxZoom"])
        rows = candidate["tiles"]
        declared_count = int(candidate["tileCount"])
        declared_bytes = int(candidate["totalBytes"])
    except (KeyError, TypeError, ValueError):
        return finish(False)
    if not isinstance(rows, list) or not 0 <= min_zoom <= max_zoom <= MAX_ZOOM:
        return finish(False)
    expected_count = sum(4**zoom for zoom in range(min_zoom, max_zoom + 1))
    if declared_count != expected_count or len(rows) != expected_count:
        return finish(False)
    total_bytes = 0
    root = ALL_SKY_PACK_ROOT.resolve()
    expected_paths = {
        Path("tiles") / str(zoom) / str(x) / f"{y}.jpg"
        for zoom in range(min_zoom, max_zoom + 1)
        for x in range(2**zoom)
        for y in range(2**zoom)
    }
    declared_paths: set[Path] = set()
    for row in rows:
        try:
            relative = Path(str(row["path"]))
            expected_bytes = int(row["bytes"])
            tile = (ALL_SKY_PACK_ROOT / relative).resolve()
            tile.relative_to(root)
            actual_bytes = tile.stat().st_size
        except (KeyError, TypeError, ValueError, OSError):
            return finish(False)
        if expected_bytes < 100 or actual_bytes != expected_bytes:
            return finish(False)
        declared_paths.add(relative)
        total_bytes += actual_bytes
    return finish(
        total_bytes == declared_bytes and declared_paths == expected_paths
    )


def _tile_version(legacy: dict[str, Any], all_sky: dict[str, Any]) -> str:
    version_payload = {
        "legacy": legacy,
        "allSky": all_sky,
        "compositor": 2,
    }
    encoded = json.dumps(
        version_payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def public_manifest() -> dict[str, Any]:
    legacy = manifest()
    declared_all_sky = all_sky_manifest()
    all_sky_available = all_sky_pack_available(refresh=True)
    all_sky = declared_all_sky if all_sky_available else {}
    legacy_max = int(legacy.get("maxZoom", 5))
    all_sky_max = int(all_sky.get("maxZoom", legacy_max))
    legacy_bytes = int(legacy.get("totalBytes", 0))
    all_sky_bytes = int(all_sky.get("totalBytes", 0))
    legacy_count = int(legacy.get("tileCount", 0))
    all_sky_count = int(all_sky.get("tileCount", 0))
    legacy_credit = legacy.get(
        "attribution", "Legacy Surveys / D. Lang (Perimeter Institute)"
    )
    all_sky_credit = all_sky.get(
        "attribution", "2MASS / UMass & IPAC-Caltech; colored HiPS by CDS"
    )
    legacy_license_url = legacy.get(
        "licenseUrl", "https://creativecommons.org/licenses/by/4.0/"
    )
    all_sky_license_url = all_sky.get(
        "licenseUrl", "https://opendatacommons.org/licenses/odbl/1-0/"
    )
    legacy_source_url = legacy.get("officialReleaseUrl") or legacy.get("viewerUrl")
    all_sky_source_url = all_sky.get("sourceRecordUrl") or all_sky.get(
        "sourceHiPSUrl"
    )
    legacy_attribution = {
        "label": str(legacy_credit),
        "sourceUrl": str(legacy_source_url) if legacy_source_url else None,
        "licenseLabel": str(legacy.get("license", "CC BY 4.0")),
        "licenseUrl": str(legacy_license_url),
        "url": str(legacy_license_url),
    }
    all_sky_attribution = {
        "label": str(all_sky_credit),
        "sourceUrl": str(all_sky_source_url) if all_sky_source_url else None,
        "licenseLabel": str(all_sky.get("license", "ODbL-1.0")),
        "licenseUrl": str(all_sky_license_url),
        "url": str(all_sky_license_url),
    }
    layers: list[dict[str, Any]] = []
    if all_sky_available:
        layers.append(
            {
                "id": "filled",
                "title": "自动补全",
                "shortTitle": "补全",
                "description": "DESI DR11 光学主图；无数据区域显示 2MASS 全天近红外观测",
                "offlineMaxZoom": min(legacy_max, all_sky_max),
                "onlineMaxZoom": MAX_ZOOM,
                "coverageFraction": 1.0,
                "datasetCoverageFraction": 1.0,
                "renderCoverageFraction": WEB_MERCATOR_SKY_FRACTION,
                "renderDeclinationLimit": WEB_MERCATOR_DECLINATION_LIMIT,
                "tileCount": legacy_count + all_sky_count,
                "totalBytes": legacy_bytes + all_sky_bytes,
                "attributions": [legacy_attribution, all_sky_attribution],
            }
        )
    layers.append(
        {
            "id": "ls-dr11",
            "title": "DR11 原图",
            "shortTitle": "DR11",
            "description": "DESI Legacy Imaging Surveys DR11 可见光覆盖原图",
            "offlineMaxZoom": legacy_max,
            "onlineMaxZoom": MAX_ZOOM,
            "coverageFraction": 0.75,
            "datasetCoverageFraction": 0.75,
            "renderCoverageFraction": 0.75 * WEB_MERCATOR_SKY_FRACTION,
            "renderDeclinationLimit": WEB_MERCATOR_DECLINATION_LIMIT,
            "tileCount": legacy_count,
            "totalBytes": legacy_bytes,
            "attributions": [legacy_attribution],
        }
    )
    if all_sky_available:
        layers.append(
            {
                "id": "2mass-color",
                "title": "2MASS 全天图",
                "shortTitle": "2MASS",
                "description": "2MASS J/H/Ks 三色近红外全天观测概览",
                "offlineMaxZoom": all_sky_max,
                "onlineMaxZoom": all_sky_max,
                "coverageFraction": float(all_sky.get("coverageFraction", 1.0)),
                "datasetCoverageFraction": float(
                    all_sky.get("datasetCoverageFraction", 1.0)
                ),
                "renderCoverageFraction": float(
                    all_sky.get(
                        "renderCoverageFraction", WEB_MERCATOR_SKY_FRACTION
                    )
                ),
                "renderDeclinationLimit": float(
                    all_sky.get(
                        "renderDeclinationLimit", WEB_MERCATOR_DECLINATION_LIMIT
                    )
                ),
                "tileCount": all_sky_count,
                "totalBytes": all_sky_bytes,
                "attributions": [all_sky_attribution],
            }
        )
    combined_bytes = legacy_bytes + all_sky_bytes
    combined_count = legacy_count + all_sky_count
    return {
        "schemaVersion": 2,
        "tileVersion": _tile_version(legacy, all_sky),
        "defaultLayer": "filled" if all_sky_available else "ls-dr11",
        "allSkyPackAvailable": all_sky_available,
        "layers": layers,
        "offlineTotalBytes": combined_bytes,
        "dataset": legacy.get("dataset", "DESI Legacy Imaging Surveys DR11"),
        "layer": legacy.get("layer", "ls-dr11"),
        "minZoom": min(
            int(legacy.get("minZoom", 0)),
            int(all_sky.get("minZoom", legacy.get("minZoom", 0))),
        ),
        "offlineMaxZoom": min(legacy_max, all_sky_max),
        "onlineMaxZoom": MAX_ZOOM,
        "tileSize": legacy.get("tileSize", all_sky.get("tileSize", 256)),
        "tileCount": combined_count,
        "totalBytes": combined_bytes,
        "projection": legacy.get("projection"),
        "renderDeclinationLimit": WEB_MERCATOR_DECLINATION_LIMIT,
        "renderCoverageFraction": WEB_MERCATOR_SKY_FRACTION,
        "attribution": legacy_credit,
        "license": legacy.get("license", "CC BY 4.0"),
        "licenseUrl": legacy_license_url,
        "officialReleaseUrl": legacy.get("officialReleaseUrl"),
        "dataReleaseUrl": legacy.get("dataReleaseUrl"),
        "viewerUrl": legacy.get("viewerUrl"),
        "allSkyDataset": all_sky.get("dataset"),
        "allSkyAttribution": all_sky_credit if all_sky_available else None,
        "allSkyLicense": all_sky.get("license") if all_sky_available else None,
        "allSkyLicenseUrl": all_sky_license_url if all_sky_available else None,
        "allSkySourceUrl": all_sky.get("sourceRecordUrl"),
        "allSkyMissionUrl": all_sky.get("sourceMissionUrl"),
        "allSkyDoi": all_sky.get("sourceHiPSDoi"),
        "allSkyReferenceBibcode": all_sky.get("surveyBibcode"),
        "allSkyTileCount": all_sky_count,
        "allSkyTotalBytes": all_sky_bytes,
    }


def resolve_tile(
    z: int, x: int, y: int, *, allow_online: bool = False
) -> tuple[Path, str] | None:
    """Resolve the original Legacy Surveys layer (kept for API compatibility)."""
    coordinates = _coordinates(z, x, y)
    if coordinates is None:
        return None
    bundled = _tile_file(TILE_ROOT, z, x, y)
    if _valid_tile(bundled):
        return bundled, "bundled"
    if not allow_online:
        return None
    cached = _tile_file(CACHE_ROOT, z, x, y)
    if _valid_tile(cached):
        return cached, "cache"
    with _tile_lock("ls-dr11", z, x, y):
        if _valid_tile(cached):
            return cached, "cache"
        cached.parent.mkdir(parents=True, exist_ok=True)
        url = OFFICIAL_TILE_TEMPLATE.format(z=z, x=x, y=y)
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "StarfieldAtlas/1.0 (interactive DR11 tile cache)",
                "Accept": "image/jpeg",
            },
        )
        temporary = cached.with_suffix(
            f".jpg.{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex}.part"
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                if response.headers.get_content_type() != "image/jpeg":
                    return None
                content = response.read(MAX_TILE_BYTES + 1)
            if len(content) > MAX_TILE_BYTES or not content.startswith(b"\xff\xd8"):
                return None
            temporary.write_bytes(content)
            if not _valid_tile(temporary):
                temporary.unlink(missing_ok=True)
                return None
            temporary.replace(cached)
            return cached, "official"
        except OSError:
            temporary.unlink(missing_ok=True)
            return None


def resolve_all_sky_tile(z: int, x: int, y: int) -> tuple[Path, str] | None:
    coordinates = _coordinates(z, x, y)
    payload = all_sky_manifest()
    if coordinates is None or not all_sky_pack_available():
        return None
    native_max = int(payload.get("maxZoom", 5))
    if z > native_max:
        return None
    bundled = _tile_file(ALL_SKY_TILE_ROOT, z, x, y)
    return (bundled, "2mass-bundled") if _valid_tile(bundled) else None


def _render_all_sky_image(
    z: int, x: int, y: int
) -> tuple[Image.Image, str] | None:
    """Render a 2MASS background without materializing a derived tile pyramid."""
    if _coordinates(z, x, y) is None:
        return None
    payload = all_sky_manifest()
    if not all_sky_pack_available():
        return None
    native_max = int(payload.get("maxZoom", 5))
    if z <= native_max:
        tile = _tile_file(ALL_SKY_TILE_ROOT, z, x, y)
        if not _valid_tile(tile):
            return None
        with Image.open(tile) as image:
            return image.convert("RGB").copy(), "2mass-bundled"

    scale = 2 ** (z - native_max)
    parent = _tile_file(ALL_SKY_TILE_ROOT, native_max, x // scale, y // scale)
    if not _valid_tile(parent):
        return None
    child_width = 256.0 / scale
    left = (x % scale) * child_width
    top = (y % scale) * child_width
    extent = (left, top, left + child_width, top + child_width)
    with Image.open(parent) as image:
        rendered = image.convert("RGB").transform(
            (256, 256),
            Image.Transform.EXTENT,
            extent,
            resample=Image.Resampling.BICUBIC,
        )
    return rendered, "2mass-derived-fallback"


def dr11_no_data_mask(foreground: np.ndarray) -> np.ndarray:
    """Find connected #202020 survey holes without erasing real dark sky."""
    rgb = foreground.astype(np.int16)
    distance = np.max(np.abs(rgb - 32), axis=2)
    chroma = np.max(rgb, axis=2) - np.min(rgb, axis=2)
    exact = distance <= 1
    padded = np.pad(exact.astype(np.uint8), 1)
    local_count = sum(
        padded[dy : dy + exact.shape[0], dx : dx + exact.shape[1]]
        for dy in range(3)
        for dx in range(3)
    )
    mask = exact & (local_count >= 5)
    candidate = (distance <= 12) & (chroma <= 7)
    for _ in range(5):
        padded_mask = np.pad(mask, 1)
        neighbors = np.zeros_like(mask)
        for dy in range(3):
            for dx in range(3):
                neighbors |= padded_mask[
                    dy : dy + mask.shape[0], dx : dx + mask.shape[1]
                ]
        expanded = mask | (candidate & neighbors)
        if np.array_equal(expanded, mask):
            break
        mask = expanded
    return mask


def compose_filled_image(foreground: Image.Image, background: Image.Image) -> Image.Image:
    legacy = np.asarray(foreground.convert("RGB"), dtype=np.uint8)
    fallback = np.asarray(background.convert("RGB"), dtype=np.uint8)
    if legacy.shape != (256, 256, 3) or fallback.shape != legacy.shape:
        raise ValueError("sky-map tiles must both be 256x256 RGB images")
    mask = dr11_no_data_mask(legacy)
    result = legacy.copy()
    result[mask] = fallback[mask]
    return Image.fromarray(result, mode="RGB")


def resolve_composite_tile(
    z: int, x: int, y: int, *, allow_online: bool = False
) -> tuple[Path, str] | None:
    if _coordinates(z, x, y) is None:
        return None
    foreground = resolve_tile(z, x, y, allow_online=allow_online)
    background = _render_all_sky_image(z, x, y)
    if foreground is None:
        native_background = resolve_all_sky_tile(z, x, y)
        if native_background is not None:
            return native_background
    if background is None:
        return foreground
    version = _tile_version(manifest(), all_sky_manifest())
    cached = _tile_file(COMPOSITE_CACHE_ROOT / version, z, x, y)
    if _valid_tile(cached):
        source = "dr11+2mass-cache" if foreground is not None else background[1]
        return cached, source
    try:
        with _tile_lock("filled", z, x, y):
            if _valid_tile(cached):
                source = (
                    "dr11+2mass-cache" if foreground is not None else background[1]
                )
                return cached, source
            if foreground is None:
                _write_jpeg(background[0], cached)
                return cached, background[1]
            with Image.open(foreground[0]) as legacy_image:
                composite = compose_filled_image(legacy_image, background[0])
                _write_jpeg(composite, cached)
            return cached, "dr11+2mass"
    except (OSError, ValueError):
        return foreground


def resolve_layer_tile(
    layer: str, z: int, x: int, y: int, *, allow_online: bool = False
) -> tuple[Path, str] | None:
    if layer not in ALLOWED_LAYERS:
        return None
    if layer == "ls-dr11":
        return resolve_tile(z, x, y, allow_online=allow_online)
    if layer == "2mass-color":
        return resolve_all_sky_tile(z, x, y)
    return resolve_composite_tile(z, x, y, allow_online=allow_online)
