from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
PACK_ROOT = ROOT / "backend" / "data" / "2mass-allsky"
TILE_ROOT = PACK_ROOT / "tiles"
MANIFEST_PATH = PACK_ROOT / "manifest.json"
DOWNLOAD_ROOT = ROOT / ".runtime" / "sky-map-downloads"
SOURCE_PATH = DOWNLOAD_ROOT / "2mass-color-car-8192x4096.jpg"
MAX_SOURCE_BYTES = 100 * 1024 * 1024
RENDER_DECLINATION_LIMIT = 85.05112878
RENDER_COVERAGE_FRACTION = math.sin(math.radians(RENDER_DECLINATION_LIMIT))

TILE_SIZE = 256
MAX_ZOOM = 5
SOURCE_WIDTH = TILE_SIZE * 2**MAX_ZOOM
SOURCE_HEIGHT = SOURCE_WIDTH // 2
HIPS_ID = "CDS/P/2MASS/color"
HIPS_RECORD_URL = (
    "https://alasky.cds.unistra.fr/MocServer/query?"
    "ID=CDS%2FP%2F2MASS%2Fcolor&fmt=html&get=record"
)
HIPS_SERVICE_URL = "https://alasky.cds.unistra.fr/2MASS/Color"
HIPS2FITS_URL = "https://alasky.cds.unistra.fr/hips-image-services/hips2fits"
IRSA_MISSION_URL = "https://irsa.ipac.caltech.edu/Missions/2mass.html"
ODBL_URL = "https://opendatacommons.org/licenses/odbl/1-0/"
HIPS_DOI = "10.26093/cds/aladin/bzc8-nw"
SURVEY_BIBCODE = "2006AJ....131.1163S"
USER_AGENT = "StarfieldAtlas/1.0 (2MASS offline all-sky overview pack)"


def _source_url() -> str:
    query = urllib.parse.urlencode(
        {
            "hips": HIPS_ID,
            "width": SOURCE_WIDTH,
            "height": SOURCE_HEIGHT,
            "projection": "CAR",
            "fov": 360,
            "ra": 180,
            "dec": 0,
            "coordsys": "icrs",
            "format": "jpg",
        }
    )
    return f"{HIPS2FITS_URL}?{query}"


def _valid_source(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < 100_000:
        return False
    try:
        with Image.open(path) as image:
            return image.format == "JPEG" and image.size == (SOURCE_WIDTH, SOURCE_HEIGHT)
    except OSError:
        return False


def _download_source(*, force: bool = False) -> dict[str, object]:
    DOWNLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    if force:
        SOURCE_PATH.unlink(missing_ok=True)
    if not _valid_source(SOURCE_PATH):
        request = urllib.request.Request(
            _source_url(),
            headers={"User-Agent": USER_AGENT, "Accept": "image/jpeg"},
        )
        temporary = SOURCE_PATH.with_suffix(f".jpg.{os.getpid()}.part")
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                if response.headers.get_content_type() != "image/jpeg":
                    raise RuntimeError(
                        f"HiPS2FITS returned {response.headers.get_content_type()!r}"
                    )
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > MAX_SOURCE_BYTES:
                    raise RuntimeError(
                        "2MASS all-sky source exceeds the 100 MiB download limit"
                    )
                downloaded = 0
                with temporary.open("wb") as handle:
                    while chunk := response.read(1024 * 1024):
                        downloaded += len(chunk)
                        if downloaded > MAX_SOURCE_BYTES:
                            raise RuntimeError(
                                "2MASS all-sky source exceeds the 100 MiB download limit"
                            )
                        handle.write(chunk)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        if not _valid_source(temporary):
            temporary.unlink(missing_ok=True)
            raise RuntimeError("downloaded 2MASS all-sky image failed validation")
        temporary.replace(SOURCE_PATH)
    content = SOURCE_PATH.read_bytes()
    return {
        "requestUrl": _source_url(),
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def _tile_path(z: int, x: int, y: int) -> Path:
    return TILE_ROOT / str(z) / str(x) / f"{y}.jpg"


def _save_jpeg(image: Image.Image, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(f".jpg.{os.getpid()}.part")
    image.convert("RGB").save(
        temporary,
        format="JPEG",
        quality=88,
        subsampling=0,
        optimize=True,
    )
    temporary.replace(destination)


def _mercator_declinations(pixel_rows: np.ndarray, world_size: int) -> np.ndarray:
    normalized = 1.0 - 2.0 * ((pixel_rows + 0.5) / world_size)
    return np.degrees(np.arctan(np.sinh(math.pi * normalized)))


def _render_max_zoom() -> None:
    with Image.open(SOURCE_PATH) as source:
        source_array = np.asarray(source.convert("RGB"), dtype=np.uint8)
    world_size = TILE_SIZE * 2**MAX_ZOOM
    if source_array.shape != (SOURCE_HEIGHT, SOURCE_WIDTH, 3):
        raise RuntimeError(f"unexpected source dimensions: {source_array.shape}")

    for tile_y in range(2**MAX_ZOOM):
        global_rows = tile_y * TILE_SIZE + np.arange(TILE_SIZE, dtype=np.float64)
        declinations = _mercator_declinations(global_rows, world_size)
        source_rows = (90.0 - declinations) * SOURCE_HEIGHT / 180.0 - 0.5
        source_rows = np.clip(source_rows, 0.0, SOURCE_HEIGHT - 1.0)
        upper = np.floor(source_rows).astype(np.int32)
        lower = np.minimum(upper + 1, SOURCE_HEIGHT - 1)
        mix = (source_rows - upper).astype(np.float32)[:, None, None]
        strip = np.rint(
            source_array[upper].astype(np.float32) * (1.0 - mix)
            + source_array[lower].astype(np.float32) * mix
        ).astype(np.uint8)
        for tile_x in range(2**MAX_ZOOM):
            left = tile_x * TILE_SIZE
            tile = Image.fromarray(strip[:, left : left + TILE_SIZE], mode="RGB")
            _save_jpeg(tile, _tile_path(MAX_ZOOM, tile_x, tile_y))
        print(f"  reprojected z{MAX_ZOOM} row {tile_y + 1}/{2**MAX_ZOOM}")


def _render_lower_zooms() -> None:
    for zoom in range(MAX_ZOOM - 1, -1, -1):
        for x in range(2**zoom):
            for y in range(2**zoom):
                mosaic = Image.new("RGB", (TILE_SIZE * 2, TILE_SIZE * 2))
                for child_x in range(2):
                    for child_y in range(2):
                        with Image.open(
                            _tile_path(zoom + 1, x * 2 + child_x, y * 2 + child_y)
                        ) as child:
                            mosaic.paste(
                                child.convert("RGB"),
                                (child_x * TILE_SIZE, child_y * TILE_SIZE),
                            )
                reduced = mosaic.resize(
                    (TILE_SIZE, TILE_SIZE), Image.Resampling.LANCZOS
                )
                _save_jpeg(reduced, _tile_path(zoom, x, y))
        print(f"  generated z{zoom}: {4**zoom} tiles")


def _tile_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for zoom in range(MAX_ZOOM + 1):
        for x in range(2**zoom):
            for y in range(2**zoom):
                path = _tile_path(zoom, x, y)
                content = path.read_bytes()
                with Image.open(path) as image:
                    if image.format != "JPEG" or image.size != (TILE_SIZE, TILE_SIZE):
                        raise RuntimeError(f"invalid generated tile: {path}")
                rows.append(
                    {
                        "z": zoom,
                        "x": x,
                        "y": y,
                        "path": path.relative_to(PACK_ROOT).as_posix(),
                        "bytes": len(content),
                        "sha256": hashlib.sha256(content).hexdigest(),
                    }
                )
    return rows


def _write_sources() -> None:
    (PACK_ROOT / "SOURCES.md").write_text(
        "# 2MASS 全天概览瓦片来源\n\n"
        "本目录是 `CDS/P/2MASS/color` 的低分辨率、部分镜像与 Web Mercator "
        "重投影，仅用于本应用的全天概览。它不是 DESI DR11 数据。\n\n"
        "- 原始巡天：Two Micron All Sky Survey (2MASS)，J/H/Ks 近红外。\n"
        "- 原始数据署名：University of Massachusetts & IPAC/Caltech；由 NASA "
        "与 NSF 资助。\n"
        "- 彩色 HiPS：Oberto A.、Boch T. (CDS - CNRS/Unistra)。\n"
        f"- HiPS 记录：{HIPS_RECORD_URL}\n"
        f"- 彩色 HiPS DOI：{HIPS_DOI}\n"
        f"- 2MASS 巡天论文 Bibcode：{SURVEY_BIBCODE}\n"
        f"- IRSA 任务页：{IRSA_MISSION_URL}\n"
        f"- 许可：Open Data Commons ODbL 1.0，{ODBL_URL}\n"
        "- 生成服务：CDS HiPS2FITS；使用该服务产生的结果时请致谢 CDS。\n\n"
        "标准致谢：This publication makes use of data products from the Two Micron "
        "All Sky Survey, which is a joint project of the University of Massachusetts "
        "and the Infrared Processing and Analysis Center/California Institute of "
        "Technology, funded by the National Aeronautics and Space Administration and "
        "the National Science Foundation.\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the offline 2MASS all-sky Web Mercator overview pack."
    )
    parser.add_argument("--force-download", action="store_true")
    parser.add_argument("--reuse-tiles", action="store_true")
    args = parser.parse_args()
    if args.force_download and args.reuse_tiles:
        parser.error("--force-download and --reuse-tiles cannot be used together")

    source = _download_source(force=args.force_download)
    TILE_ROOT.mkdir(parents=True, exist_ok=True)
    if not args.reuse_tiles:
        _render_max_zoom()
        _render_lower_zooms()
    rows = _tile_rows()
    _write_sources()
    manifest = {
        "schemaVersion": 2,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset": "Two Micron All Sky Survey (2MASS) Color J/H/Ks",
        "layer": "2mass-color",
        "role": "All-sky near-infrared fallback overview",
        "tileVersion": 1,
        "tileSize": TILE_SIZE,
        "minZoom": 0,
        "maxZoom": MAX_ZOOM,
        "coverageFraction": 1.0,
        "datasetCoverageFraction": 1.0,
        "renderCoverageFraction": RENDER_COVERAGE_FRACTION,
        "renderDeclinationLimit": RENDER_DECLINATION_LIMIT,
        "bands": ["J 1.23 µm", "H 1.66 µm", "Ks 2.16 µm"],
        "projection": (
            "Web Mercator; map longitude = 180 degrees - right ascension, "
            "latitude = declination; limited to +/-85.05112878 degrees"
        ),
        "runtimeNetworkRequired": False,
        "sourceHiPSId": HIPS_ID,
        "sourceHiPSUrl": HIPS_SERVICE_URL,
        "sourceRecordUrl": HIPS_RECORD_URL,
        "sourceHiPSDoi": HIPS_DOI,
        "surveyBibcode": SURVEY_BIBCODE,
        "sourceMissionUrl": IRSA_MISSION_URL,
        "generatedByUrl": HIPS2FITS_URL,
        "license": "ODbL-1.0",
        "licenseUrl": ODBL_URL,
        "attribution": "2MASS / UMass & IPAC-Caltech; colored HiPS by CDS",
        "acknowledgement": (
            "University of Massachusetts & IPAC/Caltech; funded by NASA and NSF; "
            "colored HiPS and HiPS2FITS by CDS (CNRS/Unistra)"
        ),
        "localPackStatus": "partial derivative",
        "sourceHiPSStatus": "public master clonableOnce",
        "sourceImage": source,
        "tileCount": len(rows),
        "totalBytes": sum(int(row["bytes"]) for row in rows),
        "tiles": rows,
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {MANIFEST_PATH.relative_to(ROOT)}: {manifest['tileCount']} tiles, "
        f"{manifest['totalBytes'] / 1024 / 1024:.1f} MiB"
    )


if __name__ == "__main__":
    main()
