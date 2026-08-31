from __future__ import annotations

import json
import re
import urllib.parse
from functools import lru_cache
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parent / "data"
MANIFEST_PATH = DATA_DIR / "nasa_deep_sky.json"
IMAGE_DIR = DATA_DIR / "nasa-deep-sky" / "images"
PUBLIC_PREFIX = "/api/deep-sky-media/"
SAFE_IMAGE_NAME = re.compile(r"[a-z0-9][a-z0-9._-]{4,120}\.webp", re.IGNORECASE)


def _official_nasa_url(value: Any) -> str | None:
    if not isinstance(value, str) or not value.startswith("https://"):
        return None
    try:
        hostname = (urllib.parse.urlparse(value).hostname or "").lower()
    except ValueError:
        return None
    if hostname == "nasa.gov" or hostname.endswith(".nasa.gov"):
        return value
    return None


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


@lru_cache(maxsize=1)
def load_nasa_deep_sky() -> dict[str, dict[str, Any]]:
    """Load the optional offline NASA information pack without blocking recognition."""

    try:
        payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict) or payload.get("schemaVersion") != 1:
        return {}
    usage_url = _official_nasa_url(payload.get("usageGuidelinesUrl"))
    source_objects = payload.get("objects")
    if not isinstance(source_objects, dict):
        return {}
    output: dict[str, dict[str, Any]] = {}
    for catalog_id, raw in source_objects.items():
        if not isinstance(catalog_id, str) or not isinstance(raw, dict):
            continue
        filename = _text(raw.get("thumbnailFile"))
        source_url = _official_nasa_url(raw.get("sourceUrl"))
        if (
            not filename
            or not SAFE_IMAGE_NAME.fullmatch(filename)
            or not (IMAGE_DIR / filename).is_file()
            or source_url is None
        ):
            continue
        output[catalog_id] = {
            "titleEn": _text(raw.get("titleEn")),
            "description": _text(raw.get("descriptionZh")),
            "distance": _text(raw.get("distance")),
            "objectClassDetail": _text(raw.get("objectClassZh")),
            "thumbnail": f"{PUBLIC_PREFIX}{urllib.parse.quote(filename)}",
            "thumbnailWidth": raw.get("thumbnailWidth"),
            "thumbnailHeight": raw.get("thumbnailHeight"),
            "sourceUrl": source_url,
            "imageCredit": _text(raw.get("credit")) or "NASA",
            "nasaId": _text(raw.get("nasaId")),
            "mediaProvider": "NASA",
            "mediaUsageUrl": usage_url,
        }
    return output


def media_for(catalog_id: str) -> dict[str, Any]:
    return {
        key: value
        for key, value in load_nasa_deep_sky().get(catalog_id, {}).items()
        if value is not None
    }


def resolve_media_file(filename: str) -> Path | None:
    """Resolve an immutable media filename without allowing directory traversal."""

    decoded = urllib.parse.unquote(filename)
    if Path(decoded).name != decoded or not SAFE_IMAGE_NAME.fullmatch(decoded):
        return None
    candidate = (IMAGE_DIR / decoded).resolve()
    try:
        candidate.relative_to(IMAGE_DIR.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else None
