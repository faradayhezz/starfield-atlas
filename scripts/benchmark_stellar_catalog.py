"""Measure one complete cold-process image analysis without publishing inputs.

Pass an input photograph, a generic label, and a local output directory.
The JSON report contains no original path or EXIF/GPS data. Run each image
in a fresh process when comparing cold catalogue/solver startup costs.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def peak_working_set_bytes() -> int:
    if sys.platform != "win32":
        import resource
        maximum = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(maximum if sys.platform == "darwin" else maximum * 1024)

    class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    counters = PROCESS_MEMORY_COUNTERS()
    counters.cb = ctypes.sizeof(counters)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    return int(counters.PeakWorkingSetSize)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--label", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    from PIL import Image
    from backend import pipeline
    from backend.stellar_index import _load_cell

    star_query_seconds = 0.0
    original_query = pipeline.bright_stars_in_frame

    def timed_query(*query_args, **query_kwargs):
        nonlocal star_query_seconds
        start = perf_counter()
        value = original_query(*query_args, **query_kwargs)
        star_query_seconds += perf_counter() - start
        return value

    pipeline.bright_stars_in_frame = timed_query
    started = perf_counter()
    stages = []

    def progress(stage, percent, _message):
        stages.append({"stage": stage, "percent": percent, "elapsed_seconds": round(perf_counter() - started, 3)})
        print(f"{args.label}: {stage} ({percent}%)", flush=True)

    result = pipeline.analyze_image(
        args.input.resolve(), args.output.resolve(), filename=args.label + args.input.suffix.lower(),
        progress_callback=progress,
    )
    pipeline_seconds = perf_counter() - started
    peak_after_pipeline = peak_working_set_bytes()
    response_bytes = len(json.dumps(result, ensure_ascii=False).encode("utf-8"))
    stars = result["brightStars"]
    output_file = args.output / Path(result["downloadUrl"]).name
    with Image.open(output_file) as image:
        exported_size, exported_format = list(image.size), image.format
    metadata = result["metadata"]
    report = {
        "label": args.label, "source_size": [metadata["width"], metadata["height"]],
        "exported_size": exported_size, "exported_format": exported_format,
        "horizontal_fov_deg": result["wcs"]["horizontal_fov_deg"],
        "vertical_fov_deg": result["wcs"]["vertical_fov_deg"],
        "total_stars": len(stars),
        "hyg_stars": sum(star["catalog"] == "HYG v4.1" for star in stars),
        "tycho_extension_stars": sum(star["catalog"] == "AT-HYG v3.2 / Tycho-2" for star in stars),
        "deep_sky_objects": len(result["objects"]),
        "stellar_magnitude_limit": result["settings"]["starMagnitudeLimit"],
        "stellar_label_density": result["settings"]["starLabelDensity"],
        "star_query_seconds": round(star_query_seconds, 3),
        "full_pipeline_seconds": round(pipeline_seconds, 3),
        "peak_pipeline_working_set_bytes": peak_after_pipeline,
        "peak_including_response_serialization_bytes": peak_working_set_bytes(),
        "results_json_bytes": (args.output / "results.json").stat().st_size,
        "http_json_bytes_uncompressed": response_bytes,
        "cached_numeric_cells": _load_cell.cache_info().currsize,
        "stages": stages,
        "note": "Catalogue positions, not verified pixel detections. Fresh process; original-size export included. Network upload/download and browser time excluded.",
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "benchmark.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
