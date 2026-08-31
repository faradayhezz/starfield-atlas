from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageOps

from .annotate import (
    CONSTELLATION_COLOR_HEX,
    DSO_COLOR_HEX,
    STAR_COLOR_HEX,
    normalize_font_weight,
    normalize_hex_color,
    render_annotation,
    save_jpeg,
)
from .catalog import bright_stars_in_frame, constellation_segments_in_frame, deep_sky_in_frame
from .metadata import read_metadata
from .plate_solver import solve_plate


DEFAULT_SETTINGS: dict[str, Any] = {
    "deepSky": True,
    "brightStars": True,
    "constellations": True,
    "dsoThreshold": 75.0,
    "starThreshold": 60.0,
    "constellationStrength": 70.0,
    "deepSkyColor": DSO_COLOR_HEX,
    "brightStarColor": STAR_COLOR_HEX,
    "constellationColor": CONSTELLATION_COLOR_HEX,
    "fontWeight": 650,
    "highContrast": True,
}

ProgressCallback = Callable[[str, int, str], None]
CancellationCheck = Callable[[], bool]


class AnalysisCancelled(Exception):
    """Raised when the caller no longer needs an in-flight analysis."""


def _setting_bool(value: Any, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return fallback


def normalize_settings(settings: dict[str, Any] | None = None) -> dict[str, Any]:
    """Merge request settings and strictly normalize user-controlled styles."""

    options = {**DEFAULT_SETTINGS, **(settings or {})}
    options["deepSkyColor"] = normalize_hex_color(
        options.get("deepSkyColor"), str(DEFAULT_SETTINGS["deepSkyColor"])
    )
    options["brightStarColor"] = normalize_hex_color(
        options.get("brightStarColor"), str(DEFAULT_SETTINGS["brightStarColor"])
    )
    options["constellationColor"] = normalize_hex_color(
        options.get("constellationColor"), str(DEFAULT_SETTINGS["constellationColor"])
    )
    options["fontWeight"] = normalize_font_weight(
        options.get("fontWeight"), int(DEFAULT_SETTINGS["fontWeight"])
    )
    options["highContrast"] = _setting_bool(
        options.get("highContrast"), bool(DEFAULT_SETTINGS["highContrast"])
    )
    return options


def _display_rgb(image: Image.Image) -> Image.Image:
    """Convert source pixels for preview without destroying 16-bit TIFFs."""

    if image.mode not in {"I;16", "I;16B", "I;16L", "I", "F"}:
        return image.convert("RGB")

    # Percentiles do not need every one of 60 million pixels.  Bound the
    # sampling image so high-bit-depth input cannot create several full-frame
    # float64 arrays merely to choose display levels.
    width, height = image.size
    max_sample_pixels = 2_000_000
    sample = image
    owns_sample = False
    if width * height > max_sample_pixels:
        scale = (max_sample_pixels / (width * height)) ** 0.5
        sample = image.resize(
            (max(1, round(width * scale)), max(1, round(height * scale))),
            Image.Resampling.BOX,
        )
        owns_sample = True
    try:
        sample_values = np.asarray(sample, dtype=np.float64)
        finite = sample_values[np.isfinite(sample_values)]
        if finite.size == 0:
            return Image.new("RGB", image.size)
        low, high = np.percentile(finite, [0.5, 99.98])
        del sample_values, finite
    finally:
        if owns_sample:
            sample.close()
    if high <= low:
        high = low + 1.0

    # Convert in bounded strips.  At 9504 px wide a 32 MiB float32 budget is
    # about 880 rows, rather than a 460 MiB full-frame float64 temporary.
    rows_per_strip = max(1, min(height, (32 * 1024 * 1024) // max(1, width * 4)))
    grayscale = Image.new("L", image.size)
    try:
        factor = 255.0 / (high - low)
        for top in range(0, height, rows_per_strip):
            bottom = min(height, top + rows_per_strip)
            tile = image.crop((0, top, width, bottom))
            try:
                values = np.asarray(tile, dtype=np.float32)
                scaled = (values - low) * factor
                np.nan_to_num(scaled, copy=False, nan=0.0, posinf=255.0, neginf=0.0)
                np.clip(scaled, 0.0, 255.0, out=scaled)
                np.rint(scaled, out=scaled)
                gray_tile = Image.fromarray(scaled.astype(np.uint8), mode="L")
                try:
                    grayscale.paste(gray_tile, (0, top))
                finally:
                    gray_tile.close()
            finally:
                tile.close()
        return grayscale.convert("RGB")
    finally:
        grayscale.close()


def _fit_size(
    size: tuple[int, int], bounds: tuple[int, int]
) -> tuple[int, int]:
    width, height = size
    max_width, max_height = bounds
    scale = min(1.0, max_width / width, max_height / height)
    return max(1, round(width * scale)), max(1, round(height * scale))


def _fit_width(size: tuple[int, int], max_width: int) -> tuple[int, int]:
    width, height = size
    if width <= max_width:
        return size
    return max_width, max(1, round(height * max_width / width))


def _resized_copy(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    if image.size == size:
        return image.copy()
    return image.resize(size, Image.Resampling.LANCZOS, reducing_gap=3.0)


def analyze_image(
    input_path: Path,
    job_dir: Path,
    *,
    filename: str,
    settings: dict[str, Any] | None = None,
    progress_callback: ProgressCallback | None = None,
    is_cancelled: CancellationCheck | None = None,
) -> dict[str, Any]:
    options = normalize_settings(settings)
    job_dir.mkdir(parents=True, exist_ok=True)

    def check_cancelled() -> None:
        if is_cancelled and is_cancelled():
            raise AnalysisCancelled("识别任务已取消")

    def report(stage: str, percent: int, message: str) -> None:
        check_cancelled()
        if progress_callback:
            progress_callback(stage, percent, message)
        check_cancelled()

    source: Image.Image | None = None
    display_image: Image.Image | None = None
    try:
        report("validation", 18, "正在校验照片并读取 EXIF 信息")
        source = Image.open(input_path)
        metadata = read_metadata(source)
        # Apply EXIF orientation once, in place.  The previous pipeline made a
        # full-size copy here and solve_plate made another one immediately.
        ImageOps.exif_transpose(source, in_place=True)
        source.load()
        check_cancelled()

        report("solving", 25, "正在匹配恒星图样并解算天球坐标")
        solution = solve_plate(
            source,
            metadata,
            orientation_applied=True,
            cancel_callback=check_cancelled,
        )

        report("catalog", 55, "正在匹配画面范围内的天体目录")
        deep_sky = deep_sky_in_frame(solution, float(options["dsoThreshold"]))
        check_cancelled()
        bright_stars = (
            bright_stars_in_frame(solution, float(options["starThreshold"]))
            if options["brightStars"]
            else []
        )
        check_cancelled()
        constellation_segments = (
            constellation_segments_in_frame(solution) if options["constellations"] else []
        )
        check_cancelled()

        # Reuse an already decoded RGB frame instead of converting it into a
        # second 60 MP buffer.  Other source modes still need one display copy.
        if source.mode == "RGB":
            display_image = source
            source = None
        else:
            display_image = _display_rgb(source)
            source.close()
            source = None
        full_size = display_image.size

        render_options = {
            "show_deep_sky": bool(options["deepSky"]),
            "show_bright_stars": bool(options["brightStars"]),
            "show_constellations": bool(options["constellations"]),
            "constellation_strength": float(options["constellationStrength"]),
            "deep_sky_color": str(options["deepSkyColor"]),
            "bright_star_color": str(options["brightStarColor"]),
            "constellation_color": str(options["constellationColor"]),
            "font_weight": int(options["fontWeight"]),
            "high_contrast": bool(options["highContrast"]),
        }

        report("preview", 65, "正在生成预览图与预览标注")
        annotated_preview_size = _fit_width(full_size, 2400)
        owns_preview_source = annotated_preview_size != full_size
        preview_source = (
            _resized_copy(display_image, annotated_preview_size)
            if owns_preview_source
            else display_image
        )
        try:
            original_preview_size = _fit_size(full_size, (2400, 1600))
            if original_preview_size == preview_source.size:
                save_jpeg(preview_source, job_dir / "original-preview.jpg", quality=90)
            else:
                original_preview = _resized_copy(display_image, original_preview_size)
                try:
                    save_jpeg(original_preview, job_dir / "original-preview.jpg", quality=90)
                finally:
                    original_preview.close()
            check_cancelled()

            preview = render_annotation(
                preview_source,
                deep_sky,
                bright_stars,
                constellation_segments,
                coordinate_size=full_size,
                **render_options,
            )
            try:
                save_jpeg(preview, job_dir / "annotated-preview.jpg", quality=92)
            finally:
                preview.close()
        finally:
            if owns_preview_source:
                preview_source.close()
        check_cancelled()

        report("full", 82, "正在渲染并保存高分辨率标注")
        full_annotation = render_annotation(
            display_image,
            deep_sky,
            bright_stars,
            constellation_segments,
            **render_options,
        )
        # The annotation is now self-contained, so release the unannotated full
        # frame before JPEG encoding allocates its own working buffers.
        display_image.close()
        display_image = None
        try:
            check_cancelled()
            save_jpeg(full_annotation, job_dir / "annotated-full.jpg", quality=93)
        finally:
            full_annotation.close()
        check_cancelled()

        expected_visible = sum(1 for item in deep_sky if item["expectedVisible"])
        constellations = sorted(
            {item["constellation"] for item in constellation_segments if item.get("constellation")}
        )
        warnings: list[str] = []
        if metadata.captured_at is None:
            warnings.append("文件未包含拍摄时间；本次定位完全由星点几何解算完成。")
        if metadata.latitude is None or metadata.longitude is None:
            warnings.append("文件未包含 GPS；识别深空目录不依赖拍摄地点。")
        if solution.rmse_arcsec > 60:
            warnings.append("画面存在短星轨或压缩噪声，标注采用星轨中心并保留目录位置属性。")
        warnings.append(
            "天体清单包含 OpenNGC 目录中与画面相交的全部条目；图上只标出按当前阈值预计可见的条目，以避免文字遮挡。"
        )

        job_id = job_dir.name
        result: dict[str, Any] = {
            "jobId": job_id,
            "status": "complete",
            "metadata": {
                **metadata.to_dict(),
                "filename": filename,
                "exposureLabel": metadata.exposure_label,
                "analyzed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            },
            "wcs": solution.to_public_dict(),
            "objects": deep_sky,
            "brightStars": bright_stars,
            "constellationSegments": constellation_segments,
            "counts": {
                "deepSky": len(deep_sky),
                "expectedVisible": expected_visible,
                "brightStars": len(bright_stars),
                "constellations": len(constellations),
            },
            "annotatedImageUrl": f"/api/artifacts/{job_id}/annotated-preview.jpg",
            "originalImageUrl": f"/api/artifacts/{job_id}/original-preview.jpg",
            "downloadUrl": f"/api/download/{job_id}/annotated-full.jpg",
            "resultsUrl": f"/api/download/{job_id}/results.json",
            "warnings": warnings,
            "settings": options,
        }
        check_cancelled()
        (job_dir / "results.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        report("complete", 98, "识别与高分辨率标注已完成")
        return result
    finally:
        if display_image is not None:
            display_image.close()
        if source is not None:
            source.close()
