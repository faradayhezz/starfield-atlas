from __future__ import annotations

import json
import math
import shutil
import threading
import uuid
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
    render_annotation_layer,
    save_jpeg,
)
from .catalog import bright_stars_in_frame, catalog_summary, constellation_segments_in_frame, deep_sky_in_frame
from .image_io import ALLOWED_SUFFIXES, NativeImage, composite_native, display_rgb, load_native, save_native
from .plate_solver import solve_plate


DEFAULT_SETTINGS: dict[str, Any] = {
    "deepSky": True,
    "brightStars": True,
    "constellations": False,
    "dsoThreshold": 75.0,
    "starThreshold": 60.0,
    "constellationStrength": 55.0,
    "deepSkyColor": DSO_COLOR_HEX,
    "brightStarColor": STAR_COLOR_HEX,
    "constellationColor": CONSTELLATION_COLOR_HEX,
    "fontWeight": 500,
    "highContrast": False,
    "annotationOpacity": 0.85,
    "annotationLineWidth": 1.25,
    "annotationFontSize": 18.0,
    "markerStyle": "circle",
    "labelDensity": "sparse",
    "starMagnitudeLimit": 12.0,
    "includeCatalogOnly": False,
    "catalogDepth": "deep",
}

# A single native-frame operation at a time avoids concurrent 60 MP RAW buffers.
_native_work_lock = threading.Lock()

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
    for key in ("deepSky", "brightStars", "constellations", "includeCatalogOnly"):
        options[key] = _setting_bool(options.get(key), bool(DEFAULT_SETTINGS[key]))
    for key, minimum, maximum in (
        ("annotationOpacity", 0.05, 1.0), ("annotationLineWidth", 0.5, 3.0),
        ("annotationFontSize", 8.0, 24.0), ("starMagnitudeLimit", 1.0, 16.0),
        ("dsoThreshold", 0., 100.), ("starThreshold", 0., 100.),
        ("constellationStrength", 0., 100.),
    ):
        try:
            value = float(options[key])
            options[key] = min(maximum, max(minimum, value)) if math.isfinite(value) else DEFAULT_SETTINGS[key]
        except (ValueError, TypeError):
            options[key] = DEFAULT_SETTINGS[key]
    for key, allowed in (("markerStyle", {"circle", "corners"}),
                         ("labelDensity", {"sparse", "balanced", "dense"}),
                         ("catalogDepth", {"bright", "balanced", "deep"})):
        if options.get(key) not in allowed:
            options[key] = DEFAULT_SETTINGS[key]
    return options


def select_deep_sky_inventory(objects: list[dict[str, Any]], depth: str) -> list[dict[str, Any]]:
    """Filter DSO inventory only; unknown magnitudes never become guessed values.

    A named recommended favorite remains useful even without photometry.
    Unnamed unknown-magnitude dark clouds belong to the complete catalogue.
    Stellar magnitude selection is independent of this DSO control.
    """
    if depth == "deep":
        return objects
    limit = 10.0 if depth == "bright" else 15.0
    def included(item: dict[str, Any]) -> bool:
        named_favorite = bool(item.get("expectedVisible") and (item.get("messier") or item.get("commonNameZh")))
        magnitude = item.get("magnitude")
        known_bright = isinstance(magnitude, (int, float)) and math.isfinite(magnitude) and magnitude <= limit
        return bool(named_favorite or known_bright)
    return [item for item in objects if included(item)]


def _render_options(options: dict[str, Any]) -> dict[str, Any]:
    return {
        "show_deep_sky": options["deepSky"], "show_bright_stars": options["brightStars"],
        "show_constellations": options["constellations"],
        "constellation_strength": options["constellationStrength"],
        "deep_sky_color": options["deepSkyColor"], "bright_star_color": options["brightStarColor"],
        "constellation_color": options["constellationColor"], "font_weight": options["fontWeight"],
        "high_contrast": options["highContrast"], "annotation_opacity": options["annotationOpacity"],
        "annotation_line_width": options["annotationLineWidth"], "annotation_font_size": options["annotationFontSize"],
        "marker_style": options["markerStyle"], "label_density": options["labelDensity"],
        "include_catalog_only": options["includeCatalogOnly"],
    }


def _save_full(native: NativeImage, job_dir: Path, deep_sky: list, stars: list, segments: list,
               options: dict[str, Any], check_cancelled: Callable[[], None], *, stem: str = "annotated-full") -> str:
    layer = render_annotation_layer(native.size, deep_sky, stars, segments, **_render_options(options))
    try:
        check_cancelled()
        pixels = composite_native(native, layer, check_cancelled)
    finally:
        layer.close()
    check_cancelled()
    filename = stem + native.extension
    partial_path = job_dir / (filename + ".partial")
    try:
        save_native(native, pixels, partial_path)
        check_cancelled()
        partial_path.replace(job_dir / filename)
    finally:
        partial_path.unlink(missing_ok=True)
    return filename


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
    while not _native_work_lock.acquire(timeout=.2):
        if is_cancelled and is_cancelled():
            raise AnalysisCancelled("识别任务已取消")
    try:
        return _analyze_image(input_path, job_dir, filename=filename, settings=settings,
                              progress_callback=progress_callback, is_cancelled=is_cancelled)
    finally:
        _native_work_lock.release()


def _analyze_image(
    input_path: Path, job_dir: Path, *, filename: str,
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

    native: NativeImage | None = None
    display_image: Image.Image | None = None
    try:
        report("validation", 18, "正在校验照片并读取 EXIF 信息")
        native = load_native(input_path, check_cancelled)
        metadata = native.metadata
        source_name = "input" + input_path.suffix.lower()
        source_target = job_dir / source_name
        if input_path.resolve() != source_target.resolve():
            shutil.copy2(input_path, source_target)
        display_image = display_rgb(native)
        check_cancelled()

        report("solving", 25, "正在匹配恒星图样并解算天球坐标")
        solution = solve_plate(
            display_image,
            metadata,
            orientation_applied=True,
            cancel_callback=check_cancelled,
        )

        report("catalog", 55, "正在匹配画面范围内的天体目录")
        all_deep_sky = deep_sky_in_frame(solution, float(options["dsoThreshold"]))
        deep_sky = select_deep_sky_inventory(all_deep_sky, str(options["catalogDepth"]))
        check_cancelled()
        bright_stars = bright_stars_in_frame(solution, float(options["starThreshold"]), magnitude_limit=float(options["starMagnitudeLimit"]))
        check_cancelled()
        constellation_segments = constellation_segments_in_frame(solution)
        check_cancelled()

        full_size = display_image.size
        render_options = _render_options(options)

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

        report("full", 82, "正在按原始尺寸、格式和位深保存标注")
        display_image.close()
        display_image = None
        exported_name = _save_full(native, job_dir, deep_sky, bright_stars,
                                   constellation_segments, options, check_cancelled)
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
            "天体清单来自 HYG、OpenNGC 与 Lynds 暗星云目录的坐标投影；落在视场内不等于已从照片检测到该暗天体。默认只显示少量推荐标注，可在目录中查看更暗的条目。"
        )
        if options["catalogDepth"] != "deep":
            limit = 10 if options["catalogDepth"] == "bright" else 15
            warnings.append(f"深空目录当前保留星等 ≤ {limit} 的条目和推荐命名天体；更暗或未知星等条目可切换完整目录查看。恒星极限星等单独生效。")
        if metadata.is_raw:
            warnings.append(native.export_info()["note"])

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
            "catalogSummary": catalog_summary(),
            "catalogSelection": {
                "depth": options["catalogDepth"],
                "deepSkyInField": len(all_deep_sky),
                "deepSkyIncluded": len(deep_sky),
                "starMagnitudeLimit": options["starMagnitudeLimit"],
                "unknownMagnitudePolicy": "all" if options["catalogDepth"] == "deep" else "named_recommended_only",
            },
            "counts": {
                "deepSky": len(deep_sky),
                "expectedVisible": expected_visible,
                "brightStars": len(bright_stars),
                "constellations": len(constellations),
            },
            "annotatedImageUrl": f"/api/artifacts/{job_id}/annotated-preview.jpg",
            "originalImageUrl": f"/api/artifacts/{job_id}/original-preview.jpg",
            "downloadUrl": f"/api/download/{job_id}/{exported_name}",
            "originalDownloadUrl": f"/api/download/{job_id}/{source_name}",
            "export": native.export_info(),
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
        if native is not None:
            native.close()


def reexport_image(job_dir: Path, settings: dict[str, Any] | None = None,
                   is_cancelled: CancellationCheck | None = None,
                   progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    """Re-render saved coordinates over untouched input; never re-encode a preview."""
    def check_cancelled() -> None:
        if is_cancelled and is_cancelled():
            raise AnalysisCancelled("导出已取消")

    while not _native_work_lock.acquire(timeout=.2):
        check_cancelled()
    native: NativeImage | None = None
    try:
        check_cancelled()
        result = json.loads((job_dir / "results.json").read_text(encoding="utf-8"))
        source_candidates = [path for path in job_dir.glob("input.*") if path.suffix.lower() in ALLOWED_SUFFIXES]
        if len(source_candidates) != 1:
            raise ValueError("找不到唯一的原始照片，请重新上传后导出")
        analyzed_options = normalize_settings(result.get("settings", {}))
        options = normalize_settings({**analyzed_options, **(settings or {})})
        if any(options[key] != analyzed_options[key] for key in
               ("catalogDepth", "starMagnitudeLimit", "dsoThreshold", "starThreshold")):
            raise ValueError("目录参数已变化，请先重新解析，再按新目录导出")
        if progress_callback:
            progress_callback("validation", 18, "正在读取原始照片用于导出")
        native = load_native(source_candidates[0], check_cancelled)
        if progress_callback:
            progress_callback("full", 65, "正在按原始尺寸和位深重新渲染标注")
        # Catalogue coordinates are the analysis result. Style changes do not
        # silently run a different astrometric solution or invent new detections.
        deep_sky = select_deep_sky_inventory(result.get("objects", []), options["catalogDepth"])
        exported_name = _save_full(native, job_dir, deep_sky,
                                   result.get("brightStars", []), result.get("constellationSegments", []),
                                   options, check_cancelled, stem="annotated-" + uuid.uuid4().hex[:12])
        return {"downloadUrl": f"/api/download/{job_dir.name}/{exported_name}",
                "export": native.export_info(), "settings": options}
    finally:
        if native is not None:
            native.close()
        _native_work_lock.release()
