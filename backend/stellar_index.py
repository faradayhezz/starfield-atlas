"""Offline, spatially indexed AT-HYG/Tycho-2 stars supplementing HYG v4.1.

Only numeric columns from intersecting 15-by-10-degree cells are decoded.
No all-sky Python-object list, remote query, or pixel-detection claim is made.
"""
from __future__ import annotations

from functools import lru_cache
import json
import math
from pathlib import Path
from typing import Any, Iterator

import numpy as np

from .plate_solver import PlateSolution


INDEX_DIR = Path(__file__).resolve().parent / "data" / "athyg_v32"


@lru_cache(maxsize=1)
def stellar_index_manifest() -> dict[str, Any] | None:
    path = INDEX_DIR / "manifest.json"
    if not path.is_file():
        return None
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported offline stellar index version")
    return manifest


@lru_cache(maxsize=8)
def _load_cell(path: str) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        arrays = {name: archive[name] for name in archive.files}
    for array in arrays.values():
        array.flags.writeable = False
    return arrays


def _sky_vectors(ra: np.ndarray, dec: np.ndarray) -> np.ndarray:
    longitude, latitude = np.radians(ra), np.radians(dec)
    return np.column_stack((np.cos(latitude) * np.cos(longitude),
                            np.cos(latitude) * np.sin(longitude), np.sin(latitude)))


def candidate_cells(center_vector: np.ndarray, radius_deg: float) -> list[dict[str, Any]]:
    """Conservative spherical cap/cell intersection, including RA wrap/poles."""
    manifest = stellar_index_manifest()
    if manifest is None:
        return []
    shards = manifest["shards"]
    if not shards:
        return []
    centers = _sky_vectors(
        np.asarray([shard["center_ra_deg"] for shard in shards]),
        np.asarray([shard["center_dec_deg"] for shard in shards]),
    )
    center = np.array(center_vector, dtype=float, copy=True)
    center /= np.linalg.norm(center)
    radii = np.asarray([shard["cap_radius_deg"] for shard in shards])
    threshold = np.cos(np.radians(np.minimum(180.0, radius_deg + radii)))
    indices = np.flatnonzero(centers @ center >= threshold - 1e-12)
    return [shards[int(index)] for index in indices]


def _finite(value: Any) -> float | None:
    number = float(value)
    return number if math.isfinite(number) else None


def indexed_stars_in_frame(
    solution: PlateSolution, magnitude_limit: float, cap_radius_deg: float,
) -> Iterator[dict[str, Any]]:
    """Yield every eligible in-frame TYC star, never limit the inventory."""
    center = np.asarray(solution.rotation[0], dtype=float)
    cosine_limit = math.cos(math.radians(min(89.9, cap_radius_deg)))
    for shard in candidate_cells(center, cap_radius_deg):
        values = _load_cell(str(INDEX_DIR / shard["file"]))
        # Test the integer magnitude first to avoid converting unused columns.
        indices = np.flatnonzero(values["mag_mmag"] <= magnitude_limit * 1000 + 1e-8)
        if not len(indices):
            continue
        ra = values["ra_q"][indices].astype(np.float64) / 1e7
        dec = values["dec_q"][indices].astype(np.float64) / 1e7
        in_cap = _sky_vectors(ra, dec) @ center >= cosine_limit - 1e-12
        indices, ra, dec = indices[in_cap], ra[in_cap], dec[in_cap]
        if not len(indices):
            continue
        x, y, front = solution.world_to_pixel(ra, dec)
        inside = front & np.isfinite(x) & np.isfinite(y)
        inside &= (x >= 0) & (x < solution.image_width) & (y >= 0) & (y < solution.image_height)
        for projected in np.flatnonzero(inside):
            row = int(indices[projected])
            packed_tyc = int(values["tyc"][row])
            tyc_region, remainder = divmod(packed_tyc, 1_000_000)
            tyc_number, tyc_component = divmod(remainder, 10)
            tyc = f"{tyc_region}-{tyc_number}-{tyc_component}"
            magnitude = int(values["mag_mmag"][row]) / 1000
            hd, hip = int(values["hd"][row]), int(values["hip"][row])
            # TYC component identifiers stay unique even when an older catalogue
            # associates multiple components with one HIP or HD system.
            label = f"TYC {tyc}"
            yield {
                "id": f"star-tyc-{tyc}", "name": label, "label": label,
                "objectType": "Star", "objectTypeZh": "恒星" if magnitude > 6.5 else "亮星",
                "raDeg": float(ra[projected]), "decDeg": float(dec[projected]),
                "x": round(float(x[projected]), 2), "y": round(float(y[projected]), 2),
                "magnitude": magnitude,
                "magnitudeBand": "VT" if int(values["band"][row]) else "V",
                "priority": round(30 - magnitude, 3), "expectedVisible": False,
                "defaultVisible": False, "recommendedLabel": False,
                "evidence": "catalog_position", "pixelDetected": False,
                "catalog": "AT-HYG v3.2 / Tycho-2", "positionEpoch": "J2000.0",
                "properMotionRaMasYr": _finite(values["pmra"][row]),
                "properMotionDecMasYr": _finite(values["pmdec"][row]),
                "hip": str(hip) if hip else None, "hd": str(hd) if hd else None,
                "hyg": None, "tyc": tyc, "athyg": str(int(values["athyg"][row])),
            }
