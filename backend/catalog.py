from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from .deep_sky_media import media_for
from .plate_solver import PlateSolution


DATA_DIR = Path(__file__).resolve().parent / "data"


TYPE_NAMES_ZH = {
    "G": "星系",
    "GPair": "星系对",
    "GTrpl": "星系三重系统",
    "GGroup": "星系群",
    "OCl": "疏散星团",
    "GCl": "球状星团",
    "Cl+N": "星团与星云",
    "Neb": "星云",
    "EmN": "发射星云",
    "RfN": "反射星云",
    "DrkN": "暗星云",
    "HII": "电离氢区",
    "PN": "行星状星云",
    "SNR": "超新星遗迹",
    "Nova": "新星",
    "Other": "深空天体",
}


@dataclass(frozen=True, slots=True)
class CatalogObject:
    name: str
    object_type: str
    ra_deg: float
    dec_deg: float
    major_arcmin: float | None = None
    minor_arcmin: float | None = None
    pa_deg: float | None = None
    magnitude: float | None = None
    messier: str | None = None
    common_name_zh: str | None = None


def _number(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "-"}:
        return None
    try:
        number = float(text)
        return number if math.isfinite(number) else None
    except ValueError:
        return None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _messier_label(value: str | None) -> str | None:
    if not value:
        return None
    text = value.upper().strip()
    if text.startswith("M"):
        text = text[1:]
    try:
        return f"M{int(text)}"
    except ValueError:
        return f"M{text}"


@lru_cache(maxsize=1)
def load_openngc() -> tuple[CatalogObject, ...]:
    path = DATA_DIR / "openngc.csv"
    if not path.exists():
        return _fallback_catalog()
    objects: list[CatalogObject] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            name = _text(row.get("name"))
            ra = _number(row.get("ra_deg"))
            dec = _number(row.get("dec_deg"))
            object_type = _text(row.get("type")) or "Other"
            if not name or ra is None or dec is None or object_type in {"NonEx", "Dup"}:
                continue
            objects.append(
                CatalogObject(
                    name=name,
                    object_type=object_type,
                    ra_deg=ra,
                    dec_deg=dec,
                    major_arcmin=_number(row.get("major_arcmin")),
                    minor_arcmin=_number(row.get("minor_arcmin")),
                    pa_deg=_number(row.get("pa_deg")),
                    magnitude=_number(row.get("mag")),
                    messier=_text(row.get("messier")),
                    common_name_zh=_text(row.get("common_name_zh")),
                )
            )
    return tuple(objects)


def _fallback_catalog() -> tuple[CatalogObject, ...]:
    # Allows the UI to start before the full OpenNGC data file is installed.
    return (
        CatalogObject("NGC0224", "G", 10.6847083, 41.26875, 178, 63, 35, 3.44, "31", "仙女座星系"),
        CatalogObject("NGC0221", "G", 10.6743, 40.8652, 8.7, 6.5, 170, 8.08, "32", None),
        CatalogObject("NGC0205", "G", 10.0919, 41.6853, 21.9, 11, 170, 8.92, "110", None),
        CatalogObject("NGC0752", "OCl", 29.1667, 37.785, 75, 75, None, 5.7, None, None),
    )


def _display_label(item: CatalogObject) -> str:
    identifier = _messier_label(item.messier) or item.name
    return f"{identifier} {item.common_name_zh}" if item.common_name_zh else identifier


def _priority(item: CatalogObject) -> float:
    value = 0.0
    if item.messier:
        value += 100
    if item.common_name_zh:
        value += 40
    if item.magnitude is not None:
        value += max(0, 25 - item.magnitude)
    if item.major_arcmin is not None:
        value += min(30, math.log1p(item.major_arcmin) * 5)
    return value


def deep_sky_in_frame(solution: PlateSolution, threshold: float = 75) -> list[dict[str, Any]]:
    catalog = load_openngc()
    if not catalog:
        return []
    ra = np.asarray([item.ra_deg for item in catalog])
    dec = np.asarray([item.dec_deg for item in catalog])
    camera_cosine = (solution.rotation @ _sky_vectors_local(ra, dec).T).T[:, 0]
    center_distance_deg = np.degrees(np.arccos(np.clip(camera_cosine, -1.0, 1.0)))
    diagonal_radius_deg = _frame_diagonal_radius_deg(solution)
    x, y, in_front = solution.world_to_pixel(ra, dec)
    result: list[dict[str, Any]] = []
    # Surface brightness, sky glow and focal length make catalogue magnitude a
    # very optimistic visibility predictor.  Keep every in-frame object in the
    # result list, but only draw a conservative subset by default.  At the UI's
    # default threshold (75) this corresponds to about magnitude 9.6; the user
    # can still raise the control to expose objects down to about magnitude 11.
    sensitivity = min(100.0, max(0.0, threshold))
    max_magnitude = 5.5 + sensitivity * 0.055
    for index, item in enumerate(catalog):
        angular_radius = (item.major_arcmin or 2.0) / 120
        if center_distance_deg[index] > diagonal_radius_deg + angular_radius + 1.5:
            continue
        if not in_front[index] or not np.isfinite(x[index]) or not np.isfinite(y[index]):
            continue
        radius_px = max(5.0, solution.focal_pixels * math.tan(math.radians(angular_radius)))
        if (
            x[index] < -radius_px
            or y[index] < -radius_px
            or x[index] > solution.image_width + radius_px
            or y[index] > solution.image_height + radius_px
        ):
            continue
        large_catalog_target = (
            item.major_arcmin is not None
            and item.major_arcmin >= 20
            and (item.magnitude is None or item.magnitude <= 9)
        )
        bright_resolved_target = (
            sensitivity >= 80
            and item.magnitude is not None
            and item.magnitude <= max_magnitude
            and item.major_arcmin is not None
            and item.major_arcmin >= max(5, 25 - sensitivity * 0.2)
        )
        expected_visible = (
            (sensitivity >= 15 and bool(item.messier))
            or (sensitivity >= 35 and bool(item.common_name_zh))
            or (sensitivity >= 55 and large_catalog_target)
            or bright_resolved_target
        )
        catalog_match = {
            "id": item.name,
            "name": item.name,
            "label": _display_label(item),
            "objectType": item.object_type,
            "objectTypeZh": TYPE_NAMES_ZH.get(item.object_type, "深空天体"),
            "raDeg": item.ra_deg,
            "decDeg": item.dec_deg,
            "x": round(float(x[index]), 2),
            "y": round(float(y[index]), 2),
            "magnitude": item.magnitude,
            "majorArcmin": item.major_arcmin,
            "minorArcmin": item.minor_arcmin,
            "positionAngleDeg": item.pa_deg,
            "messier": _messier_label(item.messier),
            "commonNameZh": item.common_name_zh,
            "radiusPx": round(radius_px, 2),
            "priority": round(_priority(item), 3),
            "expectedVisible": expected_visible,
            "evidence": "catalog_position",
        }
        catalog_match.update(media_for(item.name))
        result.append(catalog_match)
    result.sort(key=lambda item: (-float(item["priority"]), str(item["label"])))
    return result


@lru_cache(maxsize=1)
def load_bright_stars() -> tuple[dict[str, Any], ...]:
    path = DATA_DIR / "bright_stars.csv"
    if not path.exists():
        return ()
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            ra = _number(row.get("ra_deg"))
            dec = _number(row.get("dec_deg"))
            mag = _number(row.get("mag"))
            if ra is None or dec is None or mag is None:
                continue
            rows.append({**row, "ra_deg": ra, "dec_deg": dec, "mag": mag})
    return tuple(rows)


def bright_stars_in_frame(solution: PlateSolution, threshold: float = 60) -> list[dict[str, Any]]:
    stars = load_bright_stars()
    if not stars:
        return []
    ra = np.asarray([item["ra_deg"] for item in stars])
    dec = np.asarray([item["dec_deg"] for item in stars])
    camera_cosine = (solution.rotation @ _sky_vectors_local(ra, dec).T).T[:, 0]
    center_distance_deg = np.degrees(np.arccos(np.clip(camera_cosine, -1.0, 1.0)))
    diagonal_radius_deg = _frame_diagonal_radius_deg(solution)
    x, y, in_front = solution.world_to_pixel(ra, dec)
    sensitivity = min(100.0, max(0.0, threshold))
    max_mag = 1.8 + sensitivity * 0.048
    result: list[dict[str, Any]] = []
    for index, star in enumerate(stars):
        if center_distance_deg[index] > diagonal_radius_deg + 1.5:
            continue
        if not in_front[index] or star["mag"] > max_mag:
            continue
        if not (0 <= x[index] < solution.image_width and 0 <= y[index] < solution.image_height):
            continue
        identifier = _text(star.get("common_name_zh")) or _text(star.get("name"))
        if not identifier:
            hr = _text(star.get("hr"))
            hip = _text(star.get("hip"))
            identifier = f"HR {hr}" if hr else (f"HIP {hip}" if hip else "亮星")
        result.append(
            {
                "id": f"star-{star.get('hip') or star.get('hr') or index}",
                "name": identifier,
                "label": identifier,
                "objectType": "Star",
                "objectTypeZh": "亮星",
                "raDeg": star["ra_deg"],
                "decDeg": star["dec_deg"],
                "x": round(float(x[index]), 2),
                "y": round(float(y[index]), 2),
                "magnitude": star["mag"],
                "priority": round(30 - star["mag"], 3),
                "expectedVisible": True,
                "evidence": "catalog_position",
            }
        )
    result.sort(key=lambda item: (float(item["magnitude"]), str(item["label"])))
    # Bright-star labels are contextual anchors, not an attempt to print the
    # full stellar catalogue.  Cap them so a 28 mm frame remains readable while
    # the sensitivity control still exposes more anchors when requested.
    max_labels = 4 + round(sensitivity * 0.14)
    return result[:max_labels]


def constellation_segments_in_frame(solution: PlateSolution) -> list[dict[str, Any]]:
    path = DATA_DIR / "constellation_lines.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    segments = payload.get("segments", payload) if isinstance(payload, dict) else payload
    constellation_meta = {
        str(item.get("id")): item
        for item in payload.get("constellations", [])
        if isinstance(payload, dict) and isinstance(item, dict) and item.get("id")
    }
    output: list[dict[str, Any]] = []
    for index, segment in enumerate(segments):
        start = segment.get("start")
        end = segment.get("end")
        if not start or not end or len(start) < 2 or len(end) < 2:
            continue
        ra, dec = _great_circle_samples(start, end)
        vectors = _sky_vectors_local(ra, dec)
        camera = (solution.rotation @ vectors.T).T
        diagonal_radius_deg = math.degrees(
            math.atan2(
                math.hypot(solution.image_width / 2, solution.image_height / 2),
                solution.focal_pixels,
            )
        )
        # A small guard band lets clipping retain lines that enter through a
        # corner, while preventing the lens-distortion model from being
        # extrapolated to unrelated stars tens of degrees outside the frame.
        near_frame = camera[:, 0] >= math.cos(math.radians(diagonal_radius_deg + 3.0))
        if not near_frame.any():
            continue
        x, y, front = solution.world_to_pixel(ra, dec)
        constellation_id = str(segment.get("constellation") or segment.get("name") or "")
        meta = constellation_meta.get(constellation_id, {})
        for part in range(len(ra) - 1):
            if not (near_frame[part] or near_frame[part + 1]):
                continue
            if not (front[part] and front[part + 1]):
                continue
            if not np.isfinite([x[part], y[part], x[part + 1], y[part + 1]]).all():
                continue
            clipped = _clip_line_to_rect(
                float(x[part]),
                float(y[part]),
                float(x[part + 1]),
                float(y[part + 1]),
                0.0,
                0.0,
                float(solution.image_width - 1),
                float(solution.image_height - 1),
            )
            if clipped is None:
                continue
            x1, y1, x2, y2 = clipped
            if math.hypot(x2 - x1, y2 - y1) < 0.5:
                continue
            output.append(
                {
                    "id": f"constellation-{index}-{part}",
                    "sourceSegment": index,
                    "constellation": constellation_id,
                    "constellationName": meta.get("name") or constellation_id,
                    "constellationNameZh": meta.get("name_zh") or constellation_id,
                    "x1": round(x1, 2),
                    "y1": round(y1, 2),
                    "x2": round(x2, 2),
                    "y2": round(y2, 2),
                }
            )
    return output


def _sky_vectors_local(ra_deg: np.ndarray, dec_deg: np.ndarray) -> np.ndarray:
    ra = np.deg2rad(np.asarray(ra_deg, dtype=np.float64))
    dec = np.deg2rad(np.asarray(dec_deg, dtype=np.float64))
    cos_dec = np.cos(dec)
    return np.column_stack((cos_dec * np.cos(ra), cos_dec * np.sin(ra), np.sin(dec)))


def _frame_diagonal_radius_deg(solution: PlateSolution) -> float:
    return math.degrees(
        math.atan2(
            math.hypot(solution.image_width / 2, solution.image_height / 2),
            solution.focal_pixels,
        )
    )


def _great_circle_samples(
    start: list[float] | tuple[float, float],
    end: list[float] | tuple[float, float],
    max_step_deg: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Sample the short great-circle arc between two catalogue stars."""

    endpoints = _sky_vectors_local(
        np.asarray([start[0], end[0]], dtype=np.float64),
        np.asarray([start[1], end[1]], dtype=np.float64),
    )
    dot = float(np.clip(np.dot(endpoints[0], endpoints[1]), -1.0, 1.0))
    omega = math.acos(dot)
    steps = max(1, math.ceil(math.degrees(omega) / max_step_deg))
    t = np.linspace(0.0, 1.0, steps + 1)
    if omega < 1e-10:
        vectors = np.repeat(endpoints[:1], steps + 1, axis=0)
    else:
        denominator = math.sin(omega)
        vectors = (
            np.sin((1 - t) * omega)[:, None] / denominator * endpoints[0]
            + np.sin(t * omega)[:, None] / denominator * endpoints[1]
        )
    vectors /= np.linalg.norm(vectors, axis=1)[:, None]
    ra = np.degrees(np.arctan2(vectors[:, 1], vectors[:, 0])) % 360.0
    dec = np.degrees(np.arcsin(np.clip(vectors[:, 2], -1.0, 1.0)))
    return ra, dec


def _clip_line_to_rect(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    left: float,
    top: float,
    right: float,
    bottom: float,
) -> tuple[float, float, float, float] | None:
    """Clip a segment to a rectangle using the Liang-Barsky algorithm."""

    dx = x2 - x1
    dy = y2 - y1
    p = (-dx, dx, -dy, dy)
    q = (x1 - left, right - x1, y1 - top, bottom - y1)
    lower, upper = 0.0, 1.0
    for direction, distance in zip(p, q, strict=True):
        if abs(direction) < 1e-12:
            if distance < 0:
                return None
            continue
        ratio = distance / direction
        if direction < 0:
            if ratio > upper:
                return None
            lower = max(lower, ratio)
        else:
            if ratio < lower:
                return None
            upper = min(upper, ratio)
    return (
        x1 + lower * dx,
        y1 + lower * dy,
        x1 + upper * dx,
        y1 + upper * dy,
    )
