from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageDraw, ImageFont

DSO_COLOR_HEX = "#69BE7A"
STAR_COLOR_HEX = "#D4B953"
CONSTELLATION_COLOR_HEX = "#A391BF"
DSO_COLOR = (105, 190, 122)
STAR_COLOR = (212, 185, 83)
CONSTELLATION_COLOR = (163, 145, 191)
FONT_WEIGHTS = (500, 650, 800)
_HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}\Z")


def normalize_hex_color(value: Any, fallback: str) -> str:
    return value.upper() if isinstance(value, str) and _HEX_COLOR.fullmatch(value) else fallback.upper()


def normalize_font_weight(value: Any, fallback: int = 500) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return fallback
    return parsed if parsed in FONT_WEIGHTS else fallback


def _number(value: Any, fallback: float, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return fallback
    return max(low, min(high, number)) if math.isfinite(number) else fallback


def _rgb(value: Any, fallback: str) -> tuple[int, int, int]:
    color = normalize_hex_color(value, fallback)
    return tuple(int(color[index:index + 2], 16) for index in (1, 3, 5))


def _font(size: int, weight: int = 500) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        "C:/Windows/Fonts/msyhbd.ttc" if weight >= 650 else "C:/Windows/Fonts/msyh.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if weight >= 650 else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    )
    for candidate in candidates:
        if Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size=size)
            except OSError:
                continue
    return ImageFont.load_default(size=size)


def _intersects(a: tuple, b: tuple, padding: float = 3) -> bool:
    return not (a[2] + padding < b[0] or b[2] + padding < a[0] or a[3] + padding < b[1] or b[3] + padding < a[1])


def _place_label(draw, text, x, y, radius, font, occupied, canvas_size, stroke_width=0):
    width, height = canvas_size
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width, anchor="lt")
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    gap = max(3, font.size * .35)
    candidates = (
        (x + radius + gap, y - th / 2), (x - radius - gap - tw, y - th / 2),
        (x - tw / 2, y + radius + gap), (x - tw / 2, y - radius - gap - th),
        (x + radius + gap, y - radius - gap - th), (x - radius - gap - tw, y + radius + gap),
    )
    for left, top in candidates:
        left, top = round(left), round(top)
        box = (left - stroke_width, top - stroke_width, left + tw + stroke_width, top + th + stroke_width)
        if box[0] < 2 or box[1] < 2 or box[2] > width - 2 or box[3] > height - 2:
            continue
        if any(_intersects(box, previous) for previous in occupied):
            continue
        occupied.append(box)
        return left, top
    return None


def _marker(draw, x, y, radius, color, line_width, style, high_contrast):
    bounds = (x - radius, y - radius, x + radius, y + radius)
    strokes = [((5, 7, 9, color[3]), line_width + max(1, line_width))] if high_contrast else []
    strokes.append((color, line_width))
    for fill, weight in strokes:
        if style == "corners":
            arm = radius * .45
            for sx, sy in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
                cx, cy = x + sx * radius, y + sy * radius
                draw.line([(cx - sx * arm, cy), (cx, cy), (cx, cy - sy * arm)], fill=fill, width=weight)
        else:
            draw.ellipse(bounds, outline=fill, width=weight)


def render_annotation_layer(
    size: tuple[int, int],
    deep_sky: Iterable[dict[str, Any]],
    bright_stars: Iterable[dict[str, Any]] = (),
    constellation_segments: Iterable[dict[str, Any]] = (),
    *,
    show_deep_sky: bool = True,
    show_bright_stars: bool = True,
    show_constellations: bool = False,
    constellation_strength: float = 55.0,
    label_limit: int | None = None,
    label_density: str = "sparse",
    deep_sky_color: str = DSO_COLOR_HEX,
    bright_star_color: str = STAR_COLOR_HEX,
    constellation_color: str = CONSTELLATION_COLOR_HEX,
    font_weight: int = 500,
    high_contrast: bool = False,
    coordinate_size: tuple[int, int] | None = None,
    annotation_opacity: float = .85,
    annotation_line_width: float = 1.25,
    annotation_font_size: float = 18.0,
    marker_style: str = "circle",
    include_catalog_only: bool = False,
) -> Image.Image:
    """Draw only annotation pixels, retaining a transparent target core.

    Sizes use a 1920-pixel-wide reference so preview/export proportions agree.
    Native 16/32-bit data can be composited without reducing untouched pixels.
    """
    width, height = size
    source_width, source_height = coordinate_size or size
    sx, sy = width / source_width, height / source_height
    unit = width / 1920
    opacity = _number(annotation_opacity, .85, 0, 1)
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    if opacity == 0:
        return layer
    draw = ImageDraw.Draw(layer)
    alpha = round(255 * opacity)
    line_width = max(1, round(_number(annotation_line_width, 1.25, .5, 3) * unit))
    font_size = max(8, round(_number(annotation_font_size, 18, 8, 28) * unit))
    font_weight = normalize_font_weight(font_weight)
    font = _font(font_size, font_weight)
    stroke = max(1, round(unit)) if high_contrast else 0
    weight_stroke = max(1, round(unit * .5)) if font_weight == 800 else 0
    marker_style = marker_style if marker_style in {"circle", "corners"} else "circle"
    colors = {
        "dso": (*_rgb(deep_sky_color, DSO_COLOR_HEX), alpha),
        "star": (*_rgb(bright_star_color, STAR_COLOR_HEX), alpha),
        "constellation": (*_rgb(constellation_color, CONSTELLATION_COLOR_HEX), round(alpha * _number(constellation_strength, 55, 0, 100) / 100)),
    }
    limit = int(_number(label_limit, {"sparse": 35, "balanced": 90, "dense": 180}.get(label_density, 35), 0, 500))
    deep = [item for item in deep_sky if include_catalog_only or item.get("expectedVisible", False)] if show_deep_sky else []
    stars = [item for item in bright_stars if include_catalog_only or item.get("defaultVisible", item.get("recommendedLabel", True))] if show_bright_stars else []
    deep.sort(key=lambda item: -float(item.get("priority") or 0))
    stars.sort(key=lambda item: float(item.get("magnitude", 99)))
    deep = deep[:limit]
    stars = stars[:max(0, limit - len(deep))]
    targets = []
    for kind, items in (("dso", deep), ("star", stars)):
        for item in items:
            x, y = float(item["x"]) * sx, float(item["y"]) * sy
            if not math.isfinite(x + y):
                continue
            if kind == "dso":
                radius = max(8 * unit, float(item.get("radiusPx") or 0) * sx + 5 * unit, line_width * 3 + 2)
                core = min(radius * .65, max(3, 10 * unit))
            else:
                magnitude = float(item.get("magnitude", 6))
                radius = max((7 + max(0, 4 - magnitude) * 1.2) * unit, line_width * 3 + 3)
                core = max(2, radius - line_width * 2 - max(1, 2 * unit))
            targets.append((kind, item, x, y, radius, core))
    # Avoid labels over target cores, including neighbouring objects.
    occupied = [(x - core - 2, y - core - 2, x + core + 2, y + core + 2) for _, _, x, y, _, core in targets]
    segments = list(constellation_segments) if show_constellations else []
    groups: dict[str, list[tuple[float, float]]] = {}
    for segment in segments:
        x1, y1, x2, y2 = (float(segment[key]) * factor for key, factor in (("x1", sx), ("y1", sy), ("x2", sx), ("y2", sy)))
        if not all(math.isfinite(v) for v in (x1, y1, x2, y2)):
            continue
        draw.line((x1, y1, x2, y2), fill=colors["constellation"], width=line_width)
        name = str(segment.get("constellationNameZh") or segment.get("constellationName") or segment.get("constellation") or "")
        if name:
            groups.setdefault(name, []).extend([(x1, y1), (x2, y2)])
    for kind, item, x, y, radius, core in targets:
        label = str(item.get("label") or item.get("name") or item.get("id") or "")
        location = _place_label(draw, label, x, y, radius, font, occupied, size, stroke + weight_stroke)
        _marker(draw, x, y, radius, colors[kind], line_width, marker_style, high_contrast)
        if location:
            draw.text(location, label, font=font, anchor="lt", fill=colors[kind], stroke_width=stroke + weight_stroke,
                      stroke_fill=(5, 7, 9, alpha) if high_contrast else colors[kind])
    for name, points in groups.items():
        x, y = sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points)
        location = _place_label(draw, name, x, y, 12 * unit, font, occupied, size, stroke)
        if location:
            draw.text(location, name, font=font, anchor="lt", fill=colors["constellation"], stroke_width=stroke,
                      stroke_fill=(5, 7, 9, colors["constellation"][3]))
    # Erase overlay alpha only; this also clears crossing labels/lines.
    for _, _, x, y, _, core in targets:
        draw.ellipse((x - core, y - core, x + core, y + core), fill=(0, 0, 0, 0))
    # Only chain endpoints are stars; don't gap intermediate WCS samples.
    endpoints: dict[tuple, int] = {}
    for segment in segments:
        source_id = segment.get("sourceSegment", segment.get("id"))
        for xx, yy in ((segment["x1"], segment["y1"]), (segment["x2"], segment["y2"])):
            key = (source_id, round(float(xx) * sx, 2), round(float(yy) * sy, 2))
            endpoints[key] = endpoints.get(key, 0) + 1
    gap = max(3, 7 * unit)
    for (_, x, y), incidence in endpoints.items():
        if incidence == 1:
            draw.ellipse((x - gap, y - gap, x + gap, y + gap), fill=(0, 0, 0, 0))
    return layer


def render_annotation(image, deep_sky, bright_stars=(), constellation_segments=(), *, max_width=None, coordinate_size=None, transparent=False, **options):
    base_size = image.size
    size = base_size if not max_width or base_size[0] <= max_width else (max_width, round(base_size[1] * max_width / base_size[0]))
    layer = render_annotation_layer(size, deep_sky, bright_stars, constellation_segments,
                                    coordinate_size=coordinate_size or base_size, **options)
    if transparent:
        return layer
    base = image.convert("RGB")
    if base.size != size:
        resized = base.resize(size, Image.Resampling.LANCZOS)
        base.close()
        base = resized
    try:
        base.paste(layer, (0, 0), layer)
        return base
    finally:
        layer.close()


def save_jpeg(image: Image.Image, path: Path, quality: int = 92) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="JPEG", quality=quality, subsampling=0, optimize=True)
