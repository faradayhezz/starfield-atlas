from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
PACK_ROOT = ROOT / "backend" / "data" / "legacy-survey-dr11"
TILE_ROOT = PACK_ROOT / "tiles"
MANIFEST_PATH = PACK_ROOT / "manifest.json"

LAYER = "ls-dr11"
VERSION = 1
TILE_SIZE = 256
TILE_TEMPLATE = (
    "https://a.legacysurvey.org/viewer/ls-dr11/1/{z}/{x}/{y}.jpg"
)
USER_AGENT = "StarfieldAtlas/1.0 (offline DR11 overview tile pack)"
MAX_TILE_BYTES = 2 * 1024 * 1024


def _tile_path(z: int, x: int, y: int) -> Path:
    return TILE_ROOT / str(z) / str(x) / f"{y}.jpg"


def _valid_jpeg(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < 100:
        return False
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            return image.format == "JPEG" and image.size == (TILE_SIZE, TILE_SIZE)
    except (OSError, ValueError):
        return False


def _download_tile(tile: tuple[int, int, int], *, retries: int = 3) -> dict[str, object]:
    z, x, y = tile
    destination = _tile_path(z, x, y)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not _valid_jpeg(destination):
        url = TILE_TEMPLATE.format(z=z, x=x, y=y)
        last_error: Exception | None = None
        for attempt in range(retries):
            try:
                request = urllib.request.Request(
                    url,
                    headers={"User-Agent": USER_AGENT, "Accept": "image/jpeg"},
                )
                with urllib.request.urlopen(request, timeout=30) as response:
                    content_type = response.headers.get_content_type()
                    payload = response.read(MAX_TILE_BYTES + 1)
                if content_type != "image/jpeg" or len(payload) > MAX_TILE_BYTES:
                    raise ValueError(f"unexpected tile response: {content_type}, {len(payload)} bytes")
                if not payload.startswith(b"\xff\xd8"):
                    raise ValueError("tile is not a JPEG")
                temporary = destination.with_suffix(f".jpg.{os.getpid()}.part")
                temporary.write_bytes(payload)
                if not _valid_jpeg(temporary):
                    temporary.unlink(missing_ok=True)
                    raise ValueError("downloaded tile failed image validation")
                temporary.replace(destination)
                break
            except (OSError, ValueError) as exc:
                last_error = exc
                if attempt + 1 < retries:
                    time.sleep(0.4 * (attempt + 1))
        else:
            raise RuntimeError(f"failed tile z={z} x={x} y={y}: {last_error}")

    payload = destination.read_bytes()
    return {
        "z": z,
        "x": x,
        "y": y,
        "path": destination.relative_to(PACK_ROOT).as_posix(),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def _tiles(min_zoom: int, max_zoom: int) -> list[tuple[int, int, int]]:
    return [
        (z, x, y)
        for z in range(min_zoom, max_zoom + 1)
        for x in range(2**z)
        for y in range(2**z)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download the public Legacy Surveys DR11 low-zoom tile pyramid."
    )
    parser.add_argument("--min-zoom", type=int, default=0)
    parser.add_argument("--max-zoom", type=int, default=5)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    if not 0 <= args.min_zoom <= args.max_zoom <= 8:
        parser.error("zoom range must satisfy 0 <= min <= max <= 8")
    workers = min(12, max(1, args.workers))

    TILE_ROOT.mkdir(parents=True, exist_ok=True)
    requested = _tiles(args.min_zoom, args.max_zoom)
    rows: list[dict[str, object]] = []
    print(f"Legacy Surveys DR11: downloading/verifying {len(requested)} tiles")
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_download_tile, tile): tile for tile in requested}
        for completed, future in enumerate(as_completed(futures), 1):
            rows.append(future.result())
            if completed % 100 == 0 or completed == len(requested):
                print(f"  {completed}/{len(requested)}")

    rows.sort(key=lambda item: (int(item["z"]), int(item["x"]), int(item["y"])))
    manifest = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset": "DESI Legacy Imaging Surveys Data Release 11",
        "layer": LAYER,
        "tileVersion": VERSION,
        "tileSize": TILE_SIZE,
        "minZoom": args.min_zoom,
        "maxZoom": args.max_zoom,
        "projection": "Web Mercator; map longitude = 180 degrees - right ascension, latitude = declination",
        "runtimeNetworkRequired": False,
        "officialReleaseUrl": "https://newscenter.lbl.gov/2026/08/10/scientists-release-biggest-2d-map-of-the-universe/",
        "dataReleaseUrl": "https://www.legacysurvey.org/dr11/description/",
        "viewerUrl": "https://www.legacysurvey.org/viewer?layer=ls-dr11",
        "tileTemplate": TILE_TEMPLATE,
        "license": "CC BY 4.0",
        "licenseUrl": "https://creativecommons.org/licenses/by/4.0/",
        "attribution": "Legacy Surveys / D. Lang (Perimeter Institute)",
        "tileCount": len(rows),
        "totalBytes": sum(int(item["bytes"]) for item in rows),
        "tiles": rows,
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Wrote {MANIFEST_PATH.relative_to(ROOT)}: "
        f"{manifest['tileCount']} tiles, {manifest['totalBytes'] / 1024 / 1024:.1f} MiB"
    )


if __name__ == "__main__":
    main()
