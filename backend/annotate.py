from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageDraw, ImageFont


DSO_COLOR = (24, 223, 105)
STAR_COLOR = (244, 206, 58)
CONSTELLATION_COLOR = (184, 106, 230)
DSO_COLOR_HEX = "#18DF69"
STAR_COLOR_HEX = "#F4CE3A"
CONSTELLATION_COLOR_HEX = "#B86AE6"
FONT_WEIGHTS = (500, 650, 800)
_HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}\Z")


def normalize_hex_color(value: Any, fallback: str) -> str:
    """Return a canonical, strictly validated CSS-style RGB hex colour."""

    if isinstance(value, str) and _HEX_COLOR.fullmatch(value):
        return value.upper()
    return fallback.upper()


def normalize_font_weight(value: Any, fallback: int = 500) -> int:
    """Restrict font weights to the variants supported by the renderer."""

    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed in FONT_WEIGHTS else fallback


def _rgb(value: Any, fallback: str) -> tuple[int, int, int]:
    color = normalize_hex_color(value, fallback)
    return tuple(int(color[index : index + 2], 16) for index in (1, 3, 5))


def _font(size: int, weight: int = 500) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    regular_candidates = (
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    )
    bold_candidates = (
        "C:/Windows/Fonts/msyhbd.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    )
    candidates = bold_candidates + regular_candidates if weight >= 650 else regular_candidates
    for candidate in candidates:
        if Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _intersects(a: tuple[int, int, int, int], b: tuple[int, int, int, int], padding: int = 5) -> bool:
    return not (
        a[2] + padding < b[0]
        or b[2] + padding < a[0]
        or a[3] + padding < b[1]
        or b[3] + padding < a[1]
    )


def _place_label(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: float,
    y: float,
    radius: float,
    font: ImageFont.ImageFont,
    occupied: list[tuple[int, int, int, int]],
    canvas_size: tuple[int, int],
    stroke_width: int = 1,
) -> tuple[int, int] | None:
    width, height = canvas_size
    text_bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    gap = max(6, round(radius * 0.12))
    candidates = (
        (round(x + radius + gap), round(y - text_height / 2)),
        (round(x - radius - gap - text_width), round(y - text_height / 2)),
        (round(x - text_width / 2), round(y + radius + gap)),
        (round(x - text_width / 2), round(y - radius - gap - text_height)),
    )
    for left, top in candidates:
        bbox = (left, top, left + text_width, top + text_height)
        if left < 4 or top < 4 or bbox[2] > width - 4 or bbox[3] > height - 4:
            continue
        if not any(_intersects(bbox, previous) for previous in occupied):
            occupied.append(bbox)
            return left, top
    return None


def _draw_text(
    draw: ImageDraw.ImageDraw,
    location: tuple[int, int],
    text: str,
    *,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
    base_stroke_width: int,
    stroke_fill: tuple[int, int, int],
    font_weight: int,
    high_contrast: bool,
) -> None:
    """Draw legible text while keeping the historical default style unchanged."""

    weight_stroke = {500: 0, 650: 1, 800: 2}[font_weight]
    contrast_stroke = base_stroke_width + (2 if high_contrast else 0)
    if high_contrast:
        shadow_offset = max(2, round(getattr(font, "size", 16) / 12))
        draw.text(
            (location[0] + shadow_offset, location[1] + shadow_offset),
            text,
            font=font,
            fill=(5, 5, 8),
            stroke_width=contrast_stroke + weight_stroke,
            stroke_fill=(5, 5, 8),
        )
    draw.text(
        location,
        text,
        font=font,
        fill=fill,
        stroke_width=contrast_stroke + weight_stroke,
        stroke_fill=stroke_fill,
    )
    if weight_stroke:
        # A colour-matched inner stroke makes 650/800 visibly heavier even on
        # systems where only a regular CJK font is installed.
        draw.text(
            location,
            text,
            font=font,
            fill=fill,
            stroke_width=weight_stroke,
            stroke_fill=fill,
        )


def render_annotation(
    image: Image.Image,
    deep_sky: Iterable[dict[str, Any]],
    bright_stars: Iterable[dict[str, Any]] = (),
    constellation_segments: Iterable[dict[str, Any]] = (),
    *,
    max_width: int | None = None,
    show_deep_sky: bool = True,
    show_bright_stars: bool = True,
    show_constellations: bool = True,
    constellation_strength: float = 70.0,
    label_limit: int = 120,
    deep_sky_color: str = DSO_COLOR_HEX,
    bright_star_color: str = STAR_COLOR_HEX,
    constellation_color: str = CONSTELLATION_COLOR_HEX,
    font_weight: int = 650,
    high_contrast: bool = True,
    coordinate_size: tuple[int, int] | None = None,
) -> Image.Image:
    base = image.convert("RGB")
    base_width, base_height = base.size
    coordinate_width = coordinate_size[0] if coordinate_size else base_width
    if max_width and base_width > max_width:
        output_width = max_width
        output_height = round(base_height * max_width / base_width)
        base = base.resize((output_width, output_height), Image.Resampling.LANCZOS)
    width, height = base.size
    scale = width / coordinate_width
    draw = ImageDraw.Draw(base)
    line_width = max(2, round(width / 1500))
    font_size = max(15, min(58, round(width / 102)))
    font_weight = normalize_font_weight(font_weight, 650)
    dso_color = _rgb(deep_sky_color, DSO_COLOR_HEX)
    star_color = _rgb(bright_star_color, STAR_COLOR_HEX)
    constellation_base_color = _rgb(constellation_color, CONSTELLATION_COLOR_HEX)
    font = _font(font_size, font_weight)
    weight_stroke = {500: 0, 650: 1, 800: 2}[font_weight]
    label_stroke_width = 1 + weight_stroke + (2 if high_contrast else 0)
    occupied: list[tuple[int, int, int, int]] = []

    if show_constellations:
        strength = min(100.0, max(0.0, float(constellation_strength)))
        rendered_constellation_color = tuple(
            round(channel * (0.35 + 0.65 * strength / 100))
            for channel in constellation_base_color
        )
        constellation_groups: dict[str, list[tuple[float, float, float, float]]] = {}
        for segment in constellation_segments:
            coordinates = (
                float(segment["x1"]) * scale,
                float(segment["y1"]) * scale,
                float(segment["x2"]) * scale,
                float(segment["y2"]) * scale,
            )
            rendered_line_width = max(1, round((line_width - 0.5) * (0.65 + strength / 100)))
            if high_contrast:
                draw.line(coordinates, fill=(8, 8, 12), width=rendered_line_width + 4)
            draw.line(coordinates, fill=rendered_constellation_color, width=rendered_line_width)
            label = str(
                segment.get("constellationNameZh")
                or segment.get("constellationName")
                or segment.get("constellation")
                or ""
            )
            if label:
                constellation_groups.setdefault(label, []).append(coordinates)

        constellation_font = _font(max(font_size + 3, round(font_size * 1.22)), font_weight)
        for label, lines in constellation_groups.items():
            total_length = sum(math.hypot(x2 - x1, y2 - y1) for x1, y1, x2, y2 in lines)
            if total_length < width * 0.045:
                continue
            points = [(x, y) for x1, y1, x2, y2 in lines for x, y in ((x1, y1), (x2, y2))]
            center_x = sum(point[0] for point in points) / len(points)
            center_y = sum(point[1] for point in points) / len(points)
            constellation_stroke = 2 + weight_stroke + (2 if high_contrast else 0)
            bbox = draw.textbbox(
                (0, 0), label, font=constellation_font, stroke_width=constellation_stroke
            )
            label_width = bbox[2] - bbox[0]
            label_height = bbox[3] - bbox[1]
            left = round(min(max(8, center_x - label_width / 2), width - label_width - 8))
            top = round(min(max(8, center_y - label_height / 2), height - label_height - 8))
            label_box = (left, top, left + label_width, top + label_height)
            if any(_intersects(label_box, previous, padding=10) for previous in occupied):
                continue
            occupied.append(label_box)
            _draw_text(
                draw,
                (left, top),
                label,
                font=constellation_font,
                fill=rendered_constellation_color,
                base_stroke_width=2,
                stroke_fill=(18, 18, 22),
                font_weight=font_weight,
                high_contrast=high_contrast,
            )

    if show_bright_stars:
        for star in bright_stars:
            x = float(star["x"]) * scale
            y = float(star["y"]) * scale
            radius = max(4, width / 720)
            star_bounds = (x - radius, y - radius, x + radius, y + radius)
            if high_contrast:
                draw.ellipse(star_bounds, outline=(8, 8, 12), width=line_width + 4)
            draw.ellipse(star_bounds, outline=star_color, width=line_width)
            location = _place_label(
                draw,
                str(star["label"]),
                x,
                y,
                radius,
                font,
                occupied,
                base.size,
                label_stroke_width,
            )
            if location:
                _draw_text(
                    draw,
                    location,
                    str(star["label"]),
                    font=font,
                    fill=star_color,
                    base_stroke_width=1,
                    stroke_fill=(24, 24, 24),
                    font_weight=font_weight,
                    high_contrast=high_contrast,
                )

    if show_deep_sky:
        candidates = [item for item in deep_sky if item.get("expectedVisible")]
        candidates.sort(key=lambda item: -float(item.get("priority") or 0))
        for item in candidates[:label_limit]:
            x = float(item["x"]) * scale
            y = float(item["y"]) * scale
            radius = max(7, min(width / 11, float(item.get("radiusPx") or 8) * scale))
            dso_bounds = (x - radius, y - radius, x + radius, y + radius)
            if high_contrast:
                draw.ellipse(dso_bounds, outline=(8, 8, 12), width=line_width + 4)
            draw.ellipse(dso_bounds, outline=dso_color, width=line_width)
            label = str(item["label"])
            location = _place_label(
                draw,
                label,
                x,
                y,
                radius,
                font,
                occupied,
                base.size,
                label_stroke_width,
            )
            if location:
                _draw_text(
                    draw,
                    location,
                    label,
                    font=font,
                    fill=dso_color,
                    base_stroke_width=1,
                    stroke_fill=(22, 22, 22),
                    font_weight=font_weight,
                    high_contrast=high_contrast,
                )
    return base


def save_jpeg(image: Image.Image, path: Path, quality: int = 92) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="JPEG", quality=quality, subsampling=0, optimize=True)
