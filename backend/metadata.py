from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from PIL import ExifTags, Image


@dataclass(slots=True)
class ImageMetadata:
    width: int
    height: int
    format: str | None = None
    mode: str | None = None
    camera_make: str | None = None
    camera_model: str | None = None
    lens_model: str | None = None
    focal_length_mm: float | None = None
    focal_length_35mm: float | None = None
    exposure_seconds: float | None = None
    aperture: float | None = None
    iso: int | None = None
    captured_at: str | None = None
    timezone_offset: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    orientation: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def exposure_label(self) -> str:
        values: list[str] = []
        if self.focal_length_mm:
            values.append(f"{self.focal_length_mm:g} mm")
        if self.exposure_seconds:
            values.append(f"{self.exposure_seconds:g} s")
        if self.aperture:
            values.append(f"f/{self.aperture:g}")
        if self.iso:
            values.append(f"ISO {self.iso}")
        return " · ".join(values) if values else "未发现可用拍摄参数"


def _float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _gps_decimal(values: Any, reference: str | None) -> float | None:
    if not values or len(values) != 3:
        return None
    parts = [_float(value) for value in values]
    if any(value is None for value in parts):
        return None
    degrees, minutes, seconds = parts
    result = degrees + minutes / 60 + seconds / 3600
    if reference in {"S", "W"}:
        result *= -1
    return result


def read_metadata(image: Image.Image) -> ImageMetadata:
    """Read normalized image metadata without trusting it for sky orientation."""

    exif = image.getexif()
    top = {ExifTags.TAGS.get(key, key): value for key, value in exif.items()}
    try:
        exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
    except (KeyError, TypeError, AttributeError):
        exif_ifd = {}
    nested = {ExifTags.TAGS.get(key, key): value for key, value in exif_ifd.items()}
    values = {**top, **nested}

    try:
        gps_ifd = exif.get_ifd(ExifTags.IFD.GPSInfo)
    except (KeyError, TypeError, AttributeError):
        gps_ifd = {}
    gps = {ExifTags.GPSTAGS.get(key, key): value for key, value in gps_ifd.items()}

    capture = values.get("DateTimeOriginal") or values.get("DateTimeDigitized") or values.get("DateTime")
    capture_iso: str | None = None
    if capture:
        try:
            capture_iso = datetime.strptime(str(capture), "%Y:%m:%d %H:%M:%S").isoformat()
        except ValueError:
            capture_iso = str(capture)

    orientation = _int(top.get("Orientation"))
    width, height = image.size
    # Reading metadata must not decode and duplicate a 40–60 MP pixel buffer.
    # EXIF orientations 5–8 swap the displayed axes; the pipeline applies the
    # actual pixel transpose once, in place, after metadata has been collected.
    if orientation in {5, 6, 7, 8}:
        width, height = height, width
    return ImageMetadata(
        width=width,
        height=height,
        format=image.format,
        mode=image.mode,
        camera_make=_clean(values.get("Make")),
        camera_model=_clean(values.get("Model")),
        lens_model=_clean(values.get("LensModel")),
        focal_length_mm=_float(values.get("FocalLength")),
        focal_length_35mm=_float(values.get("FocalLengthIn35mmFilm")),
        exposure_seconds=_float(values.get("ExposureTime")),
        aperture=_float(values.get("FNumber")),
        iso=_int(values.get("PhotographicSensitivity") or values.get("ISOSpeedRatings") or values.get("RecommendedExposureIndex")),
        captured_at=capture_iso,
        timezone_offset=_clean(values.get("OffsetTimeOriginal") or values.get("OffsetTime")),
        latitude=_gps_decimal(gps.get("GPSLatitude"), gps.get("GPSLatitudeRef")),
        longitude=_gps_decimal(gps.get("GPSLongitude"), gps.get("GPSLongitudeRef")),
        orientation=orientation,
    )


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().strip("\x00")
    return text or None


def estimated_horizontal_fov(metadata: ImageMetadata) -> float | None:
    """Estimate horizontal FOV in degrees from 35-mm-equivalent focal length."""

    focal = metadata.focal_length_35mm
    if not focal or focal <= 0:
        return None
    # 35-mm-equivalent focal lengths conventionally use a 36 mm wide frame.
    import math

    return math.degrees(2 * math.atan(36.0 / (2 * focal)))
