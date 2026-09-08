"""Build compact, real offline catalogues from fixed HYG and CDS sources.

Run from the repository root with Python. Downloads are cached under .runtime;
the resulting CSVs and their provenance manifest are the distributable assets.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "backend" / "data"
CACHE = ROOT / ".runtime" / "catalog-downloads"
HYG_COMMIT = "c7f7f883fe678cc7680169a50ccd7dcc49b060ce"
HYG_URL = f"https://raw.githubusercontent.com/astronexus/HYG-Database/{HYG_COMMIT}/hyg/CURRENT/hygdata_v41.csv"
HYG_SHA256 = "d9f69fd86bbf90a4e4d52b4c5c53eacfa6dfc0bfdef85bfd94f095e0bebe4ebd"
LDN_ARTIFACT_SHA256 = "e368587a0d1cec533d8b3232f021fc4679318c209837e78d77932d2ae3602468"
LDN_URL = (
    "https://vizier.cds.unistra.fr/viz-bin/asu-tsv?-source=VII/7A/ldn"
    "&-out=LDN,Seq,Area,Opacity,Barn,_RAJ2000,_DEJ2000"
    "&-out.max=unlimited&-out.form=mini&-oc.form=d"
)


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def download(name: str, url: str, expected_hash: str | None = None) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / name
    if not path.is_file():
        with urllib.request.urlopen(url, timeout=120) as source, path.open("wb") as output:
            while chunk := source.read(1024 * 1024):
                output.write(chunk)
    if expected_hash and sha256(path) != expected_hash:
        raise ValueError(f"Unexpected checksum for {name}; do not import an unverified snapshot")
    return path


def build_stars(source: Path) -> dict:
    with (DATA / "bright_stars.csv").open(encoding="utf-8-sig", newline="") as handle:
        names = {row["hip"]: row for row in csv.DictReader(handle)}
    rows = []
    with source.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            # HYG row 0 is the Sun, not an extrasolar point-source catalogue entry.
            if row["id"] == "0":
                continue
            try:
                ra, dec, mag = float(row["ra"]) * 15, float(row["dec"]), float(row["mag"])
            except (ValueError, TypeError):
                continue
            if not all(math.isfinite(value) for value in (ra, dec, mag)) or not -90 <= dec <= 90:
                continue
            enrichment = names.get(row.get("hip", ""), {})
            rows.append({
                "hyg": row["id"], "hip": row["hip"], "hd": row["hd"], "hr": row["hr"],
                "gl": row["gl"], "ra_deg": f"{ra % 360:.8f}", "dec_deg": f"{dec:.8f}",
                "mag": row["mag"], "name": enrichment.get("name") or row["proper"],
                "common_name_zh": enrichment.get("common_name_zh", ""),
                "pmra_masyr": row["pmra"], "pmdec_masyr": row["pmdec"],
            })
    if len(rows) < 110000 or len({row["hyg"] for row in rows}) != len(rows):
        raise ValueError("Incomplete or duplicate HYG catalogue")
    rows.sort(key=lambda row: int(row["hyg"]))
    target = DATA / "faint_stars.csv"
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    magnitudes = [float(row["mag"]) for row in rows]
    return {
        "file": target.name, "dataset": "HYG Database v4.1, full stellar catalogue (Sun excluded)",
        "source_url": HYG_URL, "upstream_commit": HYG_COMMIT,
        "source_sha256": sha256(source), "sha256": sha256(target),
        "rows": len(rows), "projectable_rows": len(rows), "epoch_equinox": "J2000.0",
        "epoch_proper_motion": 2000.0, "license": "CC-BY-SA-4.0",
        "magnitude_min": min(magnitudes), "magnitude_max": max(magnitudes),
        "stars_fainter_than_mag_7": sum(mag > 7 for mag in magnitudes),
        "stars_at_or_brighter_than_mag_12": sum(mag <= 12 for mag in magnitudes),
        "common_name_zh_filled": sum(bool(row["common_name_zh"]) for row in rows),
        "notes": "Apparent V magnitudes; catalogue is not complete to its faintest magnitude. Chinese names joined by exact HIP from the existing attributed bright-star catalogue. Coordinates retained at HYG epoch/equinox J2000; proper motions retained as metadata, not propagated without observation epoch.",
    }


def build_dark_nebulae(source: Path) -> dict:
    lines = [line for line in source.read_text(encoding="utf-8").splitlines() if line and not line.startswith("#")]
    # ASU TSV has a header, units, and dash separator before the data rows.
    entries = csv.DictReader(io.StringIO("\n".join([lines[0], *lines[3:]])), delimiter="\t")
    rows = []
    for entry in entries:
        row = {key: value.strip() for key, value in entry.items()}
        seq = int(row["Seq"])
        ldn = row["LDN"]
        ra, dec, area = float(row["_RAJ2000"]), float(row["_DEJ2000"]), float(row["Area"])
        if not all(math.isfinite(value) for value in (ra, dec, area)) or not 0 <= ra < 360 or not -90 <= dec <= 90:
            raise ValueError(f"Invalid LDN coordinates for sequence {seq}")
        rows.append({
            "name": f"LDN{int(ldn):04d}" if ldn else f"LDN-SEQ-{seq}",
            "type": "DrkN", "ra_deg": f"{ra:.4f}", "dec_deg": f"{dec:.4f}",
            "area_sqdeg": row["Area"], "opacity": row["Opacity"], "sequence": str(seq),
            "related_barnard": row["Barn"],
        })
    if len(rows) != 1791 or len({row["name"] for row in rows}) != len(rows):
        raise ValueError("LDN catalogue must contain exactly 1,791 unique rows")
    rows.sort(key=lambda row: int(row["sequence"]))
    # ASU response comments contain a fresh timestamp. Pin the normalized data
    # instead, so repeat downloads remain reproducible while changed data fails.
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    payload = output.getvalue().encode("utf-8")
    if hashlib.sha256(payload).hexdigest() != LDN_ARTIFACT_SHA256:
        raise ValueError("The LDN source data changed; review the new snapshot before updating its pin")
    target = DATA / "lynds_dark_nebulae.csv"
    target.write_bytes(payload)
    return {
        "file": target.name, "dataset": "Lynds' Catalogue of Dark Nebulae (LDN), CDS VII/7A",
        "source_url": LDN_URL, "source_sha256": sha256(source), "sha256": sha256(target),
        "rows": len(rows), "projectable_rows": len(rows),
        "catalog_version": "22-Feb-1996 updated catalogue; queried 2026-09-08",
        "epoch_equinox": "FK5/J2000.0 (VizieR-converted from FK4/B1950)",
        "license": "Original scientific catalogue data; see LYNDS-DARK-NEBULAE-NOTICE.md for citation and source terms",
        "citation": "Lynds B. T. (1962), Astrophysical Journal Supplement 7, 1; 1962ApJS....7....1L; CDS VII/7A",
        "notes": "1,787 published LDN identifiers plus 4 unnumbered clouds with stable CDS sequence IDs. Area and opacity are not magnitudes. Area-derived equivalent circular radius is only an approximate size, not a measured boundary. Barnard associations can be subclouds, so they are related identifiers, not deduplication aliases.",
    }


def main() -> None:
    stars = build_stars(download("hygdata_v41.csv", HYG_URL, HYG_SHA256))
    dark = build_dark_nebulae(download("ldn.tsv", LDN_URL))
    manifest_path = DATA / "catalog_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["generated_at"] = "2026-09-08"
    manifest["catalogs"]["faint_stars"] = stars
    manifest["catalogs"]["lynds_dark_nebulae"] = dark
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"faint_stars": stars, "lynds_dark_nebulae": dark}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
