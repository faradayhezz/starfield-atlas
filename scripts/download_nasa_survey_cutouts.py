"""Bundle NASA SkyView DSS2 thumbnails around M13 and the NGC 6269 group.

Only public catalog identifiers/coordinates are written. No user photographs,
plate solutions, EXIF metadata, or private file paths are part of this pack.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.deep_sky_media import load_nasa_deep_sky
from backend.nasa_survey_media import DATA_DIR, DOCS_URL, catalog_object, download_survey_record, query_url

DEFAULT_IDS = """
NGC6341 NGC6207 NGC6255 NGC6166 NGC6239 NGC6173 NGC6269 NGC6137
NGC6146 NGC6339 NGC6195 NGC6107 NGC6160 NGC6196 NGC6109 NGC6301
NGC6332 NGC6131 IC1245 NGC6150 NGC6158 NGC6159 NGC6177 NGC6185
NGC6142 NGC6350 NGC6329 NGC6126 NGC6343 NGC6104 NGC6311 IC1244
NGC6320 NGC6323 NGC6336 NGC6097 NGC6162 IC1208 NGC6117 NGC6180
NGC6263 NGC6194 NGC6129 NGC6261 NGC6145 NGC6184 IC4630 IC4612
NGC6108 NGC6103 NGC6212 NGC6116 NGC6114 NGC6122 NGC6312 NGC6112
NGC6163 NGC6265 NGC6264 NGC6282 NGC6270 NGC6271 NGC6272 NGC6274
""".split() + ["NGC6175 NED01", "NGC6175 NED02", "NGC6274 NED01", "NGC6274 NED02"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--object", action="append", dest="objects", help="Catalog ID; repeat to bundle selected objects")
    args = parser.parse_args()
    manifest_path = DATA_DIR / "manifest.json"
    try:
        existing = json.loads(manifest_path.read_text(encoding="utf-8")).get("objects", {})
    except (OSError, ValueError):
        existing = {}
    official = load_nasa_deep_sky()
    selected = sorted({catalog_object(identifier).name for identifier in (args.objects or DEFAULT_IDS)})
    objects = dict(existing)
    pending = []
    for identifier in selected:
        if identifier in official:
            continue
        record = objects.get(identifier, {})
        image = DATA_DIR / "images" / record.get("thumbnailFile", "missing")
        if (image.is_file() and record.get("sourceUrl") == query_url(catalog_object(identifier))
                and hashlib.sha256(image.read_bytes()).hexdigest() == record.get("thumbnailSha256")):
            continue
        pending.append(identifier)
    failures = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        work = {pool.submit(download_survey_record, identifier, DATA_DIR): identifier for identifier in pending}
        for index, future in enumerate(as_completed(work), 1):
            identifier = work[future]
            try:
                objects[identifier] = future.result()
                print(f"[{index}/{len(work)}] {identifier}: verified 384px NASA DSS2", flush=True)
            except Exception as exc:
                failures[identifier] = str(exc)
                print(f"[{index}/{len(work)}] {identifier}: {exc}", flush=True)
    manifest = {
        "schemaVersion": 1, "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "provider": "NASA GSFC SkyView", "survey": "DSS2 Red", "mediaKind": "survey",
        "docsUrl": DOCS_URL, "objectCount": len(objects), "objects": dict(sorted(objects.items())),
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sources = ["# NASA SkyView / DSS2 survey thumbnails", "",
               "These are real DSS2 Red survey cutouts delivered by NASA GSFC SkyView, centered on the exact public J2000 catalog coordinates. They are not Hubble portraits or photographs of nearby substitute objects.", "",
               "Credit: Digitized Sky Survey / STScI / Palomar Observatory / Anglo-Australian Observatory; NASA GSFC SkyView supplies the cutout service.", "",
               f"Service documentation: {DOCS_URL}", "",
               "The manifest records each object's public coordinates, reproducible query, image hash, dimensions and retrieval date. No user photographs or metadata are included. The original survey depth limits whether a faint object is distinguishable.", "",
               f"Bundled objects: {len(objects)}; JPEG survey responses converted to 384 × 384 WebP thumbnails.", ""]
    sources += [f"- [{identifier}]({record['sourceUrl']})" for identifier, record in sorted(objects.items())]
    (DATA_DIR / "SOURCES.md").write_text("\n".join(sources) + "\n", encoding="utf-8")
    print(json.dumps({"bundled": len(objects), "failed": failures}, ensure_ascii=True), flush=True)
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
