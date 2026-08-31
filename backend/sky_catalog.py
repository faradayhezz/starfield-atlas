from __future__ import annotations

import json
import math
from functools import lru_cache
from typing import Any

from .catalog import (
    DATA_DIR,
    TYPE_NAMES_ZH,
    _display_label,
    _messier_label,
    _priority,
    load_bright_stars,
    load_openngc,
)


def _constellation_catalog() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    path = DATA_DIR / "constellation_lines.json"
    if not path.is_file():
        return [], []
    payload = json.loads(path.read_text(encoding="utf-8"))
    segments = payload.get("segments", []) if isinstance(payload, dict) else []
    metadata = {
        str(item.get("id")): item
        for item in payload.get("constellations", [])
        if isinstance(payload, dict) and isinstance(item, dict) and item.get("id")
    }
    output_segments: list[dict[str, Any]] = []
    vectors: dict[str, list[tuple[float, float, float]]] = {}
    for item in segments:
        if not isinstance(item, dict):
            continue
        constellation = str(item.get("constellation") or "")
        start = item.get("start")
        end = item.get("end")
        if not constellation or not isinstance(start, list) or not isinstance(end, list):
            continue
        if len(start) < 2 or len(end) < 2:
            continue
        points = [[float(start[0]), float(start[1])], [float(end[0]), float(end[1])]]
        output_segments.append({"constellation": constellation, "points": points})
        for ra_deg, dec_deg in points:
            ra = math.radians(ra_deg)
            dec = math.radians(dec_deg)
            vectors.setdefault(constellation, []).append(
                (math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra), math.sin(dec))
            )

    labels: list[dict[str, Any]] = []
    for constellation, points in vectors.items():
        x = sum(point[0] for point in points)
        y = sum(point[1] for point in points)
        z = sum(point[2] for point in points)
        length = math.sqrt(x * x + y * y + z * z) or 1.0
        x, y, z = x / length, y / length, z / length
        meta = metadata.get(constellation, {})
        labels.append(
            {
                "id": constellation,
                "label": str(meta.get("name_zh") or meta.get("name") or constellation),
                "nameEn": str(meta.get("name") or constellation),
                "raDeg": math.degrees(math.atan2(y, x)) % 360.0,
                "decDeg": math.degrees(math.asin(max(-1.0, min(1.0, z)))),
                "rank": int(meta.get("rank") or 3),
            }
        )
    labels.sort(key=lambda item: (item["rank"], item["label"]))
    return output_segments, labels


@lru_cache(maxsize=1)
def public_sky_catalog() -> dict[str, Any]:
    deep_sky: list[dict[str, Any]] = []
    for item in load_openngc():
        regular_target = bool(item.messier or item.common_name_zh)
        resolved_bright = (
            item.magnitude is not None
            and item.magnitude <= 9.0
            and item.major_arcmin is not None
            and item.major_arcmin >= 6.0
        )
        large_target = (
            item.major_arcmin is not None
            and item.major_arcmin >= 20.0
            and (item.magnitude is None or item.magnitude <= 11.0)
        )
        if not (regular_target or resolved_bright or large_target):
            continue
        deep_sky.append(
            {
                "id": item.name,
                "label": _display_label(item),
                "catalogLabel": _messier_label(item.messier) or item.name,
                "commonNameZh": item.common_name_zh,
                "objectType": item.object_type,
                "objectTypeZh": TYPE_NAMES_ZH.get(item.object_type, "深空天体"),
                "raDeg": item.ra_deg,
                "decDeg": item.dec_deg,
                "magnitude": item.magnitude,
                "majorArcmin": item.major_arcmin,
                "minorArcmin": item.minor_arcmin,
                "priority": round(_priority(item), 3),
            }
        )
    deep_sky.sort(key=lambda item: (-float(item["priority"]), str(item["label"])))

    bright_stars: list[dict[str, Any]] = []
    for index, star in enumerate(load_bright_stars()):
        magnitude = float(star["mag"])
        common_name = str(star.get("common_name_zh") or "").strip()
        if magnitude > 3.2 and not (common_name and magnitude <= 4.0):
            continue
        name = common_name or str(star.get("name") or "").strip()
        if not name:
            hr = str(star.get("hr") or "").strip()
            hip = str(star.get("hip") or "").strip()
            name = f"HR {hr}" if hr else (f"HIP {hip}" if hip else "亮星")
        bright_stars.append(
            {
                "id": f"star-{star.get('hip') or star.get('hr') or index}",
                "label": name,
                "raDeg": float(star["ra_deg"]),
                "decDeg": float(star["dec_deg"]),
                "magnitude": magnitude,
                "priority": round(30.0 - magnitude, 3),
            }
        )
    bright_stars.sort(key=lambda item: (float(item["magnitude"]), str(item["label"])))

    constellation_segments, constellation_labels = _constellation_catalog()
    return {
        "schemaVersion": 1,
        "frame": "ICRS/J2000",
        "deepSky": deep_sky,
        "brightStars": bright_stars,
        "constellationSegments": constellation_segments,
        "constellations": constellation_labels,
        "counts": {
            "deepSky": len(deep_sky),
            "brightStars": len(bright_stars),
            "constellations": len(constellation_labels),
            "constellationSegments": len(constellation_segments),
        },
        "provenance": {
            "deepSky": "OpenNGC v20260501 (CC BY-SA 4.0)",
            "brightStars": "Hipparcos via CDS I/239",
            "constellations": "Stellarium sky culture data",
        },
    }
