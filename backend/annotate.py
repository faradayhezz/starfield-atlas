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


def _segment_hits_box(x1, y1, x2, y2, box, padding=0):
    """Clip a leader against a label rectangle, including diagonal crossings."""
    enter, leave = 0., 1.
    for origin, delta, lower, upper in ((x1, x2 - x1, box[0] - padding, box[2] + padding),
                                        (y1, y2 - y1, box[1] - padding, box[3] + padding)):
        if abs(delta) < 1e-12:
            if origin < lower or origin > upper:
                return False
            continue
        first, last = sorted(((lower - origin) / delta, (upper - origin) / delta))
        enter, leave = max(enter, first), min(leave, last)
        if enter > leave:
            return False
    return True


def _place_label(draw, text, x, y, radius, font, occupied, canvas_size, stroke_width=0, candidate_check=None):
    width, height = canvas_size
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width, anchor="lt")
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    unit = width / 1920
    gap = max(3 * unit, font.size * .35)
    candidates = []
    for offset in (0, 2, 4, 7):
        reach = radius + gap + offset * font.size * 1.15
        candidates.extend(((x + reach, y - th / 2), (x - reach - tw, y - th / 2),
                           (x - tw / 2, y + reach), (x - tw / 2, y - reach - th),
                           (x + reach, y - reach - th), (x - reach - tw, y + reach),
                           (x + reach, y + reach), (x - reach - tw, y - reach - th)))
    for left, top in candidates:
        left, top = round(left), round(top)
        box = (left - stroke_width, top - stroke_width, left + tw + stroke_width, top + th + stroke_width)
        if box[0] < 2 or box[1] < 2 or box[2] > width - 2 or box[3] > height - 2:
            continue
        if any(_intersects(box, previous, padding=2 * unit) for previous in occupied):
            continue
        if candidate_check is not None and not candidate_check(box):
            continue
        occupied.append(box)
        return left, top
    return None


def _marker(draw, x, y, radius, color, line_width, style, high_contrast):
    bounds = (x - radius, y - radius, x + radius, y + radius)
    # High contrast belongs to text only. A black ring underlay conceals both
    # the photograph and neighbouring ring arcs in compact galaxy groups.
    strokes = [(color, line_width)]
    for fill, weight in strokes:
        if style == "corners":
            arm = radius * .45
            for sx, sy in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
                cx, cy = x + sx * radius, y + sy * radius
                draw.line([(cx - sx * arm, cy), (cx, cy), (cx, cy - sy * arm)], fill=fill, width=weight)
        else:
            draw.ellipse(bounds, outline=fill, width=weight)


def _spatial_pick(items: list[dict[str, Any]], cap: int, size: tuple[int, int]) -> list[dict[str, Any]]:
    """Priority-ranked cell representatives, then fill unused slots in rank order."""
    if cap <= 0:
        return []
    if len(items) <= cap:
        return items
    width, height = size
    columns = max(1, math.ceil(math.sqrt(cap * width / height)))
    rows = max(1, math.ceil(cap / columns))
    selected: set[int] = set()
    cells: set[tuple[int, int]] = set()
    for index, item in enumerate(items):
        cell = (min(columns - 1, max(0, int(float(item["x"]) / width * columns))),
                min(rows - 1, max(0, int(float(item["y"]) / height * rows))))
        if cell not in cells:
            selected.add(index)
            cells.add(cell)
        if len(selected) >= cap:
            break
    for index in range(len(items)):
        if len(selected) >= cap:
            break
        selected.add(index)
    return [item for index, item in enumerate(items) if index in selected]


def select_annotation_objects(deep_sky, bright_stars, size, *, show_deep_sky=True,
                              show_bright_stars=True, include_catalog_only=False,
                              label_limit=None, label_density="sparse", star_label_density="balanced"):
    """Separate budgets prevent deep-sky labels from hiding the stellar layer."""
    dso_limit = int(_number(label_limit, {"sparse": 35, "balanced": 90, "dense": 180}.get(label_density, 35), 0, 500))
    star_limit = {"sparse": 20, "balanced": 60, "dense": 180}.get(star_label_density, 60)
    deep = [item for item in deep_sky if include_catalog_only or item.get("expectedVisible", False)] if show_deep_sky else []
    # The frame inventory already obeys the chosen magnitude limit. The old
    # defaultVisible flag described a ten-label budget, not pixel detection.
    stars = list(bright_stars) if show_bright_stars else []
    deep.sort(key=lambda item: (-float(item.get("priority") or 0),
                               float(item.get("magnitude") if item.get("magnitude") is not None else 99),
                               str(item.get("id", ""))))
    stars.sort(key=lambda item: (float(item.get("magnitude") if item.get("magnitude") is not None else 99), str(item.get("id", ""))))
    return _spatial_pick(deep, dso_limit, size), _spatial_pick(stars, star_limit, size)


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
    star_label_density: str = "balanced",
    faint_marker_scale: float = .6,
) -> Image.Image:
    """Draw thin, hollow annotation rings without inter-object erasure.

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
    reference_line_width = _number(annotation_line_width, 1.25, .5, 3)
    line_width = max(1, round(reference_line_width * unit))
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
    deep, stars = select_annotation_objects(deep_sky, bright_stars, (source_width, source_height),
        show_deep_sky=show_deep_sky, show_bright_stars=show_bright_stars,
        include_catalog_only=include_catalog_only, label_limit=label_limit,
        label_density=label_density, star_label_density=star_label_density)
    faint_marker_scale = _number(faint_marker_scale, .6, .3, 1)
    targets = []
    for kind, items in (("dso", deep), ("star", stars)):
        for item in items:
            x, y = float(item["x"]) * sx, float(item["y"]) * sy
            if not math.isfinite(x + y):
                continue
            if kind == "dso":
                radius = max(2.5, 8 * unit, float(item.get("radiusPx") or 0) * sx + 5 * unit, reference_line_width * unit * 3 + 2 * unit)
                core = min(radius * .65, 10 * unit)
            else:
                magnitude = float(item.get("magnitude", 6))
                # Below this raster radius a one-pixel outline becomes a filled
                # dot. Keep an actual empty interior even for tiny input images.
                radius = max(2.5, (7 + max(0, 4 - magnitude) * 1.2) * unit, reference_line_width * unit * 3 + 3 * unit)
                core = max(2 * unit, radius - reference_line_width * unit * 2 - 2 * unit)
            magnitude = item.get("magnitude")
            faint = (kind == "star" and magnitude is not None and float(magnitude) >= 7) or (
                kind == "dso" and radius <= 24 * unit and
                (magnitude is None or float(magnitude) >= 10 or not item.get("expectedVisible", False)))
            requested_width = max(.35, reference_line_width * (faint_marker_scale if faint else 1)) * unit
            weight = max(1, round(requested_width))
            ink = (*colors[kind][:3], round(alpha * min(1, requested_width / weight)))
            targets.append((kind, item, x, y, radius, core, weight, ink))
    # Labels must clear the entire marker, not only the central protected disk.
    occupied = [(x - radius - 2 * unit, y - radius - 2 * unit, x + radius + 2 * unit, y + radius + 2 * unit)
                for _, _, x, y, radius, _, _, _ in targets]
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
    # Only constellation strokes receive core cut-outs. Markers and labels are
    # drawn afterwards and therefore cannot erase one another's outlines.
    for kind, _, x, y, _, core, _, _ in targets:
        if kind == "star":
            draw.ellipse((x - core, y - core, x + core, y + core), fill=(0, 0, 0, 0))
    endpoints: dict[tuple, int] = {}
    for segment in segments:
        source_id = segment.get("sourceSegment", segment.get("id"))
        for xx, yy in ((segment["x1"], segment["y1"]), (segment["x2"], segment["y2"])):
            key = (source_id, round(float(xx) * sx, 2), round(float(yy) * sy, 2))
            endpoints[key] = endpoints.get(key, 0) + 1
    gap = 7 * unit
    for (_, x, y), incidence in endpoints.items():
        if incidence == 1:
            draw.ellipse((x - gap, y - gap, x + gap, y + gap), fill=(0, 0, 0, 0))

    labels = []
    for kind, item, x, y, radius, core, weight, ink in targets:
        label = str(item.get("label") or item.get("name") or item.get("id") or "")
        leader = []
        def accept_label(box):
            leader.clear()
            end_x = min(max(x, box[0]), box[2])
            end_y = min(max(y, box[1]), box[3])
            distance = math.hypot(end_x - x, end_y - y)
            if distance <= radius + font_size * 1.25:
                return True
            start_x = x + (end_x - x) * (radius + 2 * unit) / distance
            start_y = y + (end_y - y) * (radius + 2 * unit) / distance
            dx, dy = end_x - start_x, end_y - start_y
            for _, other, ox, oy, other_radius, _, other_width, _ in targets:
                if other is item:
                    continue
                t = max(0., min(1., ((ox - start_x) * dx + (oy - start_y) * dy) / (dx * dx + dy * dy or 1)))
                if math.hypot(ox - start_x - t * dx, oy - start_y - t * dy) < other_radius + other_width / 2 + 2 * unit:
                    return False
            # New leaders must not cross text already placed for other targets.
            # The initial entries are marker obstacles; the tail contains all
            # previous text boxes and leader corridors.
            if any(_segment_hits_box(start_x, start_y, end_x, end_y, previous, 2 * unit)
                   for previous in occupied[len(targets):]):
                return False
            leader.extend((start_x, start_y, end_x, end_y))
            return True
        location = _place_label(draw, label, x, y, radius + weight / 2, font, occupied, size,
                                stroke + weight_stroke, candidate_check=accept_label)
        if location:
            if leader:
                draw.line(leader, fill=(*colors[kind][:3], round(alpha * .7)), width=max(1, round(.55 * unit)))
                lx1, ly1, lx2, ly2 = leader
                occupied.append((min(lx1, lx2), min(ly1, ly2), max(lx1, lx2), max(ly1, ly2)))
            labels.append((location, label, colors[kind]))
        _marker(draw, x, y, radius, ink, weight, marker_style, False)

    for location, label, color in labels:
        draw.text(location, label, font=font, anchor="lt", fill=color, stroke_width=stroke + weight_stroke,
                  stroke_fill=(5, 7, 9, alpha) if high_contrast else color)
    for name, points in groups.items():
        x, y = sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points)
        location = _place_label(draw, name, x, y, 12 * unit, font, occupied, size, stroke)
        if location:
            draw.text(location, name, font=font, anchor="lt", fill=colors["constellation"], stroke_width=stroke,
                      stroke_fill=(5, 7, 9, colors["constellation"][3]))
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
