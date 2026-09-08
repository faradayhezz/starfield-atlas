"""Build a compact, offline AT-HYG/Tycho-2 stellar extension.

The upstream v3.2 CSV stream is split across two gzip files; only the first
part contains the header. The immutable source downloads remain in .runtime.
Run: .build-venv/Scripts/python.exe scripts/download_tycho_catalog.py
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
import urllib.request

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "backend" / "data"
CACHE = ROOT / ".runtime" / "catalog-downloads"
OUTPUT = DATA / "athyg_v32"
COMMIT = "650346e2bc57f664eb411bc5f44ffd94b8006af2"
SOURCE_HASHES = (
    "c71d6863d1bbab46511bf680209e424ece9435790e46025f12477a105edd1c2f",
    "bd8fe86f089c7fd3104761458cd2b0c9955ea97259440585164e4b24ed9d2fd8",
)
DTYPE = np.dtype([
    ("athyg", "<u4"), ("tyc", "<u8"), ("ra_q", "<u4"), ("dec_q", "<i4"),
    ("mag_mmag", "<i2"), ("hip", "<u4"), ("hd", "<u4"),
    ("pmra", "<f4"), ("pmdec", "<f4"), ("band", "u1"),
])


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def source_file(part: int) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    name = f"athyg_v32-{part}.csv.gz"
    target = CACHE / name
    if not target.is_file():
        url = f"https://raw.githubusercontent.com/astronexus/ATHYG-Database/{COMMIT}/data/{name}"
        temporary = target.with_suffix(".part")
        with urllib.request.urlopen(url, timeout=90) as source, temporary.open("wb") as output:
            while block := source.read(1024 * 1024):
                output.write(block)
        temporary.replace(target)
    if sha256(target) != SOURCE_HASHES[part - 1]:
        raise ValueError(f"Source checksum mismatch: {name}")
    return target


def optional_float(value: str) -> float:
    return float(value) if value.strip() else float("nan")


def build() -> None:
    sources = [source_file(part) for part in (1, 2)]
    with (DATA / "faint_stars.csv").open(encoding="utf-8", newline="") as handle:
        hyg_rows = list(csv.DictReader(handle))
    hyg_ids = {row["hyg"] for row in hyg_rows}
    hip_ids = {row["hip"] for row in hyg_rows if row["hip"]}
    # Numeric build arrays avoid retaining millions of Python dictionaries.
    rows = np.empty(2_600_000, dtype=DTYPE)
    cells = np.empty(len(rows), dtype=np.uint16)
    counts: Counter = Counter()
    count = 0
    header = None
    for source in sources:
        with gzip.open(source, "rt", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, fieldnames=header)
            if header is None:
                header = reader.fieldnames
            for row in reader:
                counts["upstream_rows"] += 1
                if row["hyg"] == "0":
                    counts["sun_excluded"] += 1
                    continue
                # The author explicitly cross-matched HYG identifiers. Never
                # collapse nearby stars or Tycho binary components by distance.
                if row["hyg"] in hyg_ids:
                    counts["exact_hyg_duplicates_excluded"] += 1
                    continue
                ra, dec, mag = float(row["ra"]) * 15, float(row["dec"]), float(row["mag"])
                if not all(math.isfinite(value) for value in (ra, dec, mag)):
                    raise ValueError(f"Nonfinite AT-HYG entry {row['id']}")
                if not (0 <= ra < 360 and -90 <= dec <= 90):
                    raise ValueError(f"Invalid AT-HYG coordinates {row['id']}")
                tyc1, tyc2, tyc3 = (int(value) for value in row["tyc"].split("-"))
                if not (0 < tyc1 < 10000 and 0 < tyc2 < 100000 and 0 < tyc3 < 10):
                    raise ValueError(f"Invalid Tycho identifier {row['tyc']}")
                if row["pos_src"] not in {"T", "TYC", "HIP", "HIP_X", "GJ"}:
                    raise ValueError(f"Unknown coordinate source: {row['pos_src']}")
                band = 1 if row["mag_src"] in {"T", "TYC"} else 0
                # AT-HYG publishes magnitudes to at most millimagnitude
                # precision. Check before quantizing, so no silent truncation.
                magnitude_mmag = round(mag * 1000)
                if abs(magnitude_mmag / 1000 - mag) > 0.0000001:
                    raise ValueError(f"Unexpected magnitude precision: {row['id']}")
                rows[count] = (
                    int(row["id"]), (tyc1 * 100000 + tyc2) * 10 + tyc3,
                    round(ra * 1e7), round(dec * 1e7), magnitude_mmag,
                    int(row["hip"] or 0), int(row["hd"] or 0),
                    optional_float(row["pm_ra"]), optional_float(row["pm_dec"]), band,
                )
                cells[count] = min(17, int((dec + 90) // 10)) * 24 + min(23, int(ra // 15))
                counts[f"position_source_{row['pos_src']}"] += 1
                counts[f"magnitude_band_{'VT' if band else 'V'}"] += 1
                if row["hip"] in hip_ids:
                    counts["hip_association_without_hyg_match"] += 1
                count += 1
        print(f"Processed {source.name}: {count:,} supplemental stars", flush=True)
    rows, cells = rows[:count], cells[:count]
    if count < 2_400_000 or count > 2_500_000:
        raise ValueError(f"Unexpected source coverage: {count}")
    if len(np.unique(rows["athyg"])) != count or len(np.unique(rows["tyc"])) != count:
        raise ValueError("Duplicate source identifiers")
    order = np.argsort(cells, kind="stable")
    rows, cells = rows[order], cells[order]
    OUTPUT.mkdir(parents=True, exist_ok=True)
    shard_records = []
    for cell in range(432):
        start, stop = np.searchsorted(cells, [cell, cell + 1])
        subset = rows[start:stop]
        path = OUTPUT / f"cell_{cell:03d}.npz"
        np.savez_compressed(path, **{name: subset[name] for name in DTYPE.names})
        shard_records.append({
            "file": path.name, "cell": cell, "rows": len(subset),
            "center_ra_deg": (cell % 24) * 15 + 7.5,
            "center_dec_deg": (cell // 24) * 10 - 85,
            # Triangle inequality along a meridian and a parallel provides a
            # conservative bound everywhere, including cells next to a pole.
            "cap_radius_deg": 12.5,
            "sha256": sha256(path), "bytes": path.stat().st_size,
        })
    manifest = {
        "schema_version": 1, "dataset": "AT-HYG v3.2 / Tycho-2 extension",
        "creator": "David Nash / Astronexus", "license": "CC-BY-SA-4.0",
        "upstream_commit": COMMIT,
        "source_url": f"https://github.com/astronexus/ATHYG-Database/tree/{COMMIT}",
        "sources": [{"url": f"https://raw.githubusercontent.com/astronexus/ATHYG-Database/{COMMIT}/data/{p.name}", "sha256": sha256(p)} for p in sources],
        "rows": count, "base_hyg_rows": len(hyg_rows), "combined_stars": count + len(hyg_rows),
        "faint_stars_gt_7": int(np.count_nonzero(rows["mag_mmag"] > 7000)),
        "stars_gt_12": int(np.count_nonzero(rows["mag_mmag"] > 12000)),
        "magnitude_min": float(rows["mag_mmag"].min()) / 1000,
        "magnitude_max": float(rows["mag_mmag"].max()) / 1000,
        "magnitude_completeness": "Tycho-2 approximately 90% complete to V=11.5; not complete to the faintest magnitude. HYG uses V and Tycho uses VT.",
        "completeness_reference": "https://heasarc.gsfc.nasa.gov/w3browse/all/tycho2.html",
        "coordinate_frame": "ICRS, J2000.0",
        "coordinate_quantization_deg": 1e-7,
        "magnitude_quantization": 0.001,
        "selection": "All valid AT-HYG records except the Sun and author-supplied exact HYG duplicates; no sky, brightness, or proximity cut.",
        "deduplication": "Keep all HYG v4.1 base entries, exclude extension rows whose explicit HYG ID already exists, retain distinct TYC component IDs even if a HIP association is shared.",
        "source_counts": dict(counts),
        "total_compressed_bytes": sum(shard["bytes"] for shard in shard_records),
        "max_shard_rows": max(shard["rows"] for shard in shard_records),
        "shards": shard_records,
    }
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({key: value for key, value in manifest.items() if key != "shards"}, indent=2), flush=True)


if __name__ == "__main__":
    build()
