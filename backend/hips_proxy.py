from __future__ import annotations

import mimetypes
import os
import re
import threading
import urllib.error
import urllib.request
import weakref
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from .app_paths import HIPS_CACHE_DIR

BUNDLED_DIR = Path(__file__).resolve().parent / "data" / "hips"
CACHE_DIR = HIPS_CACHE_DIR
MAX_RESOURCE_BYTES = 64 * 1024 * 1024
MAX_IMAGE_PIXELS = 100_000_000


@dataclass(frozen=True, slots=True)
class HipsSurvey:
    id: str
    title: str
    upstream: str
    max_order: int
    tile_format: str
    coverage_fraction: float


SURVEYS: dict[str, HipsSurvey] = {
    "dss2-color": HipsSurvey(
        id="dss2-color",
        title="DSS2 全天彩色光学",
        upstream="https://alasky.cds.unistra.fr/DSS/DSSColor",
        max_order=9,
        tile_format="jpg",
        coverage_fraction=1.0,
    ),
    "legacy-dr10": HipsSurvey(
        id="legacy-dr10",
        title="DESI Legacy Surveys DR10 彩色光学",
        upstream=(
            "https://alasky.cds.unistra.fr/DESI-legacy-surveys/DR10/"
            "CDS_P_DESI-Legacy-Surveys_DR10_color"
        ),
        max_order=11,
        tile_format="png",
        coverage_fraction=0.67339,
    ),
    "2mass-color": HipsSurvey(
        id="2mass-color",
        title="2MASS J/H/Ks 全天近红外",
        upstream="https://alasky.cds.unistra.fr/2MASS/Color",
        max_order=9,
        tile_format="jpg",
        coverage_fraction=1.0,
    ),
}


_TILE_RESOURCE_RE = re.compile(
    r"^Norder([0-9]{1,2})/(?:Allsky\.(jpg|png|webp)|"
    r"Dir([0-9]{1,12})/Npix([0-9]{1,12})\.(jpg|png|webp|fits))$"
)
_locks_guard = threading.Lock()
_locks: weakref.WeakValueDictionary[str, threading.Lock] = weakref.WeakValueDictionary()


def public_hips_manifest() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "cacheMode": "bundled-allsky-and-on-demand-detail",
        "surveys": [
            {
                "id": survey.id,
                "title": survey.title,
                "url": f"/api/sky-map/hips/{survey.id}",
                "maxOrder": survey.max_order,
                "tileFormat": survey.tile_format,
                "coverageFraction": survey.coverage_fraction,
                "bundledOverview": (
                    (BUNDLED_DIR / survey.id / "properties").is_file()
                    and any((BUNDLED_DIR / survey.id / "Norder3").glob("Allsky.*"))
                ),
            }
            for survey in SURVEYS.values()
        ],
    }


def _resource_lock(key: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(key, threading.Lock())


def _valid_resource_path(survey: HipsSurvey, normalized: str) -> bool:
    if normalized in {"properties", "Moc.fits", "preview.jpg", "preview.png"}:
        return True
    match = _TILE_RESOURCE_RE.fullmatch(normalized)
    if not match:
        return False
    order = int(match.group(1))
    if order > survey.max_order:
        return False
    directory, pixel = match.group(3), match.group(4)
    if directory is None or pixel is None:  # Allsky image
        return True
    npix = int(pixel)
    expected_directory = (npix // 10_000) * 10_000
    return (
        pixel == str(npix)
        and directory == str(expected_directory)
        and npix < 12 * (4 ** order)
    )


def _content_type(path: Path) -> str:
    if path.name.lower() == "properties":
        return "text/plain; charset=utf-8"
    if path.suffix.lower() == ".fits":
        return "application/fits"
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def _has_valid_signature(content_path: Path, logical_path: Path) -> bool:
    """Reject successful HTML/error pages before they can poison the tile cache."""
    with content_path.open("rb") as handle:
        prefix = handle.read(80)
    suffix = logical_path.suffix.lower()
    if logical_path.name == "properties":
        text = prefix.decode("utf-8", errors="ignore").lower()
        return "hips_" in text or "obs_" in text or "dataproduct_" in text
    image_signature_ok = (
        (suffix in {".jpg", ".jpeg"} and prefix.startswith(b"\xff\xd8\xff"))
        or (suffix == ".png" and prefix.startswith(b"\x89PNG\r\n\x1a\n"))
        or (suffix == ".webp" and prefix.startswith(b"RIFF") and prefix[8:12] == b"WEBP")
    )
    if image_signature_ok:
        try:
            with Image.open(content_path) as image:
                width, height = image.size
                if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                    return False
                # Full decoding catches truncated JPEG/WebP payloads that can
                # pass both their magic bytes and Pillow's lightweight verify().
                image.load()
            return True
        except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError):
            return False
    if suffix == ".fits":
        return prefix.startswith(b"SIMPLE")
    return False


def _existing_resource(survey_id: str, relative_path: str) -> Path | None:
    for root in (BUNDLED_DIR, CACHE_DIR):
        candidate = (root / survey_id / relative_path).resolve()
        try:
            candidate.relative_to((root / survey_id).resolve())
        except ValueError:
            continue
        if candidate.is_file():
            size = candidate.stat().st_size
            if 0 < size <= MAX_RESOURCE_BYTES and _has_valid_signature(candidate, candidate):
                return candidate
    return None


def resolve_hips_resource(
    survey_id: str,
    relative_path: str,
) -> tuple[Path, str, str] | None:
    survey = SURVEYS.get(survey_id)
    normalized = relative_path.strip("/").replace("\\", "/")
    if survey is None or not normalized or not _valid_resource_path(survey, normalized):
        return None
    existing = _existing_resource(survey_id, normalized)
    if existing is not None:
        source = "bundled" if BUNDLED_DIR in existing.parents else "cache"
        return existing, _content_type(existing), source

    key = f"{survey_id}/{normalized}"
    with _resource_lock(key):
        existing = _existing_resource(survey_id, normalized)
        if existing is not None:
            source = "bundled" if BUNDLED_DIR in existing.parents else "cache"
            return existing, _content_type(existing), source

        target = CACHE_DIR / survey_id / normalized
        temporary = target.with_name(f".{target.name}.{os.getpid()}.part")
        request = urllib.request.Request(
            f"{survey.upstream}/{normalized}",
            headers={"User-Agent": "StarfieldAtlas/1.0 (+local HiPS cache)"},
        )
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with urllib.request.urlopen(request, timeout=30) as response, temporary.open("wb") as handle:
                content_length = response.headers.get("Content-Length")
                expected_length = int(content_length) if content_length else None
                if expected_length is not None and expected_length > MAX_RESOURCE_BYTES:
                    return None
                downloaded = 0
                while chunk := response.read(1024 * 1024):
                    downloaded += len(chunk)
                    if downloaded > MAX_RESOURCE_BYTES:
                        return None
                    handle.write(chunk)
            if expected_length is not None and downloaded != expected_length:
                return None
            if not _has_valid_signature(temporary, target):
                return None
            temporary.replace(target)
        except (OSError, ValueError, urllib.error.URLError):
            return None
        finally:
            # Also remove partial downloads rejected by the streaming size cap.
            temporary.unlink(missing_ok=True)
        return target, _content_type(target), "downloaded"
