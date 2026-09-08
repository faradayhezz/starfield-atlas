"""Native pixel I/O. Preview conversion never replaces the export source."""
from __future__ import annotations

import struct
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import imagecodecs
import numpy as np
import rawpy
import tifffile
from PIL import Image

from .metadata import ImageMetadata, read_file_metadata

RAW_SUFFIXES = {
    ".arw", ".cr2", ".cr3", ".nef", ".nrw", ".dng", ".raf", ".orf", ".rw2",
    ".pef", ".srw", ".raw", ".sr2", ".srf", ".3fr", ".fff", ".iiq", ".rwl",
    ".mos", ".mrw", ".kdc", ".dcr", ".erf", ".mef", ".mdc", ".x3f",
}
RASTER_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
ALLOWED_SUFFIXES = RASTER_SUFFIXES | RAW_SUFFIXES
MAX_IMAGE_PIXELS = 180_000_000


def _check_size(width: int, height: int) -> None:
    if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
        raise ValueError("照片像素超出支持范围（最多 1.8 亿像素）")


def orient_pixels(pixels: np.ndarray, orientation: int | None) -> np.ndarray:
    """EXIF transform as a view, without quantization or another frame buffer."""
    return {
        2: lambda: pixels[:, ::-1], 3: lambda: pixels[::-1, ::-1],
        4: lambda: pixels[::-1], 5: lambda: pixels.swapaxes(0, 1),
        6: lambda: np.rot90(pixels, -1), 7: lambda: pixels.swapaxes(0, 1)[::-1, ::-1],
        8: lambda: np.rot90(pixels, 1),
    }.get(orientation, lambda: pixels)()


@dataclass
class NativeImage:
    pixels: np.ndarray
    metadata: ImageMetadata
    output_format: str
    extension: str
    info: dict[str, Any] = field(default_factory=dict)

    @property
    def size(self) -> tuple[int, int]:
        return self.pixels.shape[1], self.pixels.shape[0]

    def export_info(self) -> dict[str, Any]:
        note = "保留原始像素尺寸和位深；标注后文件字节大小会改变。"
        if self.metadata.is_raw:
            note = "RAW 原件保持不变；标注输出为全分辨率 16 位 TIFF，不能写回相机传感器 RAW 格式。"
        elif self.output_format == "JPEG":
            note = "保留原始像素尺寸和 JPEG 格式；添加标注需要重新编码，文件字节大小会改变。"
        if self.info.get("miniswhite_normalized"):
            note += "白为零的灰度 TIFF 已按同位深转换为等效 RGB 亮度。"
        return {
            "format": self.output_format, "extension": self.extension,
            "bitDepth": self.pixels.dtype.itemsize * 8,
            "width": self.size[0], "height": self.size[1],
            "originalFormat": self.metadata.format,
            "isRaw": self.metadata.is_raw, "note": note,
        }

    def close(self) -> None:
        self.pixels = np.empty((0, 0), dtype=np.uint8)


def load_native(path: Path, check_cancelled: Callable[[], None] = lambda: None) -> NativeImage:
    check_cancelled()
    metadata = read_file_metadata(path)
    suffix = path.suffix.lower()
    info: dict[str, Any] = {}
    if suffix in RAW_SUFFIXES:
        try:
            with rawpy.imread(str(path)) as raw:
                _check_size(raw.sizes.width, raw.sizes.height)
                check_cancelled()
                pixels = raw.postprocess(
                    output_bps=16, half_size=False, use_camera_wb=True,
                    no_auto_bright=True, output_color=rawpy.ColorSpace.sRGB,
                )
        except rawpy.LibRawError as exc:
            raise ValueError(f"LibRaw 无法解析该 RAW 文件或相机型号：{exc}") from exc
        metadata.is_raw = True
        metadata.format = suffix[1:].upper()
        # LibRaw applies the camera orientation by default, exactly once.
        output_format, extension = "TIFF", ".tiff"
    elif suffix in {".tif", ".tiff"}:
        with tifffile.TiffFile(path) as tif:
            page = tif.pages[0]
            _check_size(page.imagewidth, page.imagelength)
            if len(tif.pages) != 1:
                raise ValueError("当前支持单帧 TIFF；请先选择多页 TIFF 中要标注的一帧")
            if page.photometric not in {0, 1, 2}:
                raise ValueError("当前 TIFF 支持灰度或 RGB 图像，请先转换调色板或 CMYK TIFF")
            if (page.dtype.kind not in "uif" or page.dtype.itemsize not in {1, 2, 4, 8}
                    or (page.dtype.kind in "ui" and page.dtype.itemsize > 4)):
                raise ValueError("不支持该 TIFF 像素数据类型")
            pixels = page.asarray()
            if page.planarconfig == 2:
                pixels = np.moveaxis(pixels, 0, -1)
            orientation_tag = page.tags.get("Orientation")
            if orientation_tag:
                metadata.orientation = int(orientation_tag.value)
            icc = page.tags.get("InterColorProfile")
            if icc:
                info["icc_profile"] = icc.value
            if page.photometric == 0:
                # Colored TIFF output uses RGB, whose zero means black. Keep
                # the visual brightness when normalizing an inverted grayscale
                # photometric interpretation, without reducing its precision.
                white = np.iinfo(pixels.dtype).max if pixels.dtype.kind in "ui" else 1.
                pixels = np.subtract(white, pixels, dtype=pixels.dtype)
                info["miniswhite_normalized"] = True
            for tag, key in (("XResolution", "xresolution"), ("YResolution", "yresolution"), ("ResolutionUnit", "resolutionunit")):
                value = page.tags.get(tag)
                if value:
                    info[key] = value.value
        pixels = orient_pixels(pixels, metadata.orientation)
        output_format, extension = "TIFF", suffix
    else:
        with Image.open(path) as image:
            _check_size(*image.size)
            info = {key: image.info[key] for key in ("icc_profile", "exif", "dpi") if key in image.info}
            actual_format = image.format
            if actual_format == "PNG":
                # Pillow truncates RGB 16-bit PNG to 8 bits; libpng does not.
                pixels = imagecodecs.png_decode(path.read_bytes())
                info["png_color_chunks"] = _png_color_chunks(path)
                output_format, extension = "PNG", ".png"
            elif actual_format == "JPEG":
                image.load()
                pixels = np.asarray(image.convert("RGB") if image.mode not in {"RGB", "L"} else image).copy()
                output_format = "JPEG"
                extension = suffix if suffix in {".jpg", ".jpeg"} else ".jpg"
            else:
                raise ValueError("文件内容与支持的 JPG、PNG、TIFF 或相机 RAW 格式不符")
        pixels = orient_pixels(pixels, metadata.orientation)
    check_cancelled()
    if pixels.ndim not in {2, 3} or (pixels.ndim == 3 and pixels.shape[2] not in {1, 2, 3, 4}):
        raise ValueError("照片必须是单帧灰度、RGB 或 RGBA 图像")
    metadata.width, metadata.height = pixels.shape[1], pixels.shape[0]
    metadata.bit_depth = pixels.dtype.itemsize * 8
    metadata.mode = ("RGB" if pixels.ndim == 3 and pixels.shape[2] >= 3 else "L") + f" {metadata.bit_depth}-bit"
    return NativeImage(pixels, metadata, output_format, extension, info)


def display_rgb(native: NativeImage, *, max_size: tuple[int, int] | None = None) -> Image.Image:
    """Bound all float working arrays to strips; export always uses native.pixels."""
    pixels = native.pixels
    height, width = pixels.shape[:2]
    stride = max(1, int(np.ceil((height * width / 1_000_000) ** .5)))
    sample = pixels[::stride, ::stride]
    if sample.ndim == 3 and sample.shape[2] in {2, 4}:
        sample = sample[..., :-1]
    if pixels.dtype == np.uint8:
        low, high = 0., 255.
    elif pixels.dtype == np.uint16 and (native.metadata.is_raw or native.output_format == "PNG"):
        low, high = 0., 65535.
    else:
        finite = sample[np.isfinite(sample)]
        low, high = np.percentile(finite, [.5, 99.98]) if finite.size else (0., 1.)
        if high <= low:
            high = low + 1.
    rgb = Image.new("RGB", (width, height))
    rows = max(1, min(height, (16 * 1024 * 1024) // max(1, width * 4 * 4)))
    for top in range(0, height, rows):
        strip = pixels[top:top + rows]
        alpha = None
        if strip.ndim == 3 and strip.shape[2] in {2, 4}:
            maximum_alpha = float(np.iinfo(strip.dtype).max) if strip.dtype.kind in "ui" else 1.
            alpha = strip[..., -1].astype(np.float32) / maximum_alpha
            strip = strip[..., :-1]
        scaled = strip.astype(np.float32)
        scaled -= low
        scaled *= 255. / (high - low)
        np.nan_to_num(scaled, copy=False, nan=0., posinf=255., neginf=0.)
        np.clip(scaled, 0., 255., out=scaled)
        if alpha is not None:
            scaled *= np.clip(alpha, 0., 1.)[..., None]
        values = scaled.astype(np.uint8)
        if values.ndim == 3 and values.shape[2] == 1:
            values = values[..., 0]
        tile = Image.fromarray(values)
        rgb.paste(tile, (0, top))
        tile.close()
    if max_size:
        rgb.thumbnail(max_size, Image.Resampling.LANCZOS, reducing_gap=3.)
    return rgb


def composite_native(native: NativeImage, layer: Image.Image, check_cancelled: Callable[[], None] = lambda: None) -> np.ndarray:
    """Blend only annotated pixels. Untouched lossless samples retain exact bits."""
    if layer.mode != "RGBA" or layer.size != native.size:
        raise ValueError("标注图层必须为原始尺寸的 RGBA 图层")
    source = native.pixels
    # Colored annotations on a grayscale image require RGB channels, but retain
    # the source sample type and values in all three channels outside the marks.
    if source.ndim == 2 or source.shape[2] == 1:
        output = np.repeat(source.reshape(*source.shape[:2], 1), 3, axis=2)
    elif source.shape[2] == 2:
        output = np.empty((*source.shape[:2], 4), dtype=source.dtype)
        output[..., :3] = source[..., :1]
        output[..., 3] = source[..., 1]
    else:
        output = source
        if not output.flags.writeable:
            output = output.copy()
    dtype = output.dtype
    if dtype.kind == "u":
        black, white = 0., float(np.iinfo(dtype).max)
    else:
        step = max(1, int(np.ceil((source.shape[0] * source.shape[1] / 1_000_000) ** .5)))
        sample = source[::step, ::step]
        finite = sample[np.isfinite(sample)]
        black, white = np.percentile(finite, [.5, 99.98]) if finite.size else (0., 1.)
        if white <= black:
            white = black + 1.
    width, height = native.size
    rows = max(1, min(height, (16 * 1024 * 1024) // max(1, width * 4 * 8)))
    for top in range(0, height, rows):
        check_cancelled()
        tile = layer.crop((0, top, width, min(height, top + rows)))
        overlay = np.asarray(tile)
        mask = overlay[..., 3] > 0
        if mask.any():
            opacity = overlay[..., 3][mask].astype(np.float64)[:, None] / 255.
            rgb = overlay[..., :3][mask].astype(np.float64) / 255.
            target = black + rgb * (white - black)
            strip = output[top:top + rows]
            original = strip[..., :3][mask].astype(np.float64)
            np.nan_to_num(original, copy=False, nan=black, posinf=white, neginf=black)
            output_alpha = None
            if strip.shape[2] == 4:
                alpha_white = float(np.iinfo(dtype).max) if dtype.kind in "ui" else 1.
                source_alpha = strip[..., 3][mask].astype(np.float64)[:, None] / alpha_white
                output_alpha = opacity + source_alpha * (1. - opacity)
                mixed = (original * source_alpha * (1. - opacity) + target * opacity) / output_alpha
            else:
                mixed = original * (1. - opacity) + target * opacity
            if dtype.kind in "ui":
                np.rint(mixed, out=mixed)
                limits = np.iinfo(dtype)
                np.clip(mixed, limits.min, limits.max, out=mixed)
            strip[..., :3][mask] = mixed.astype(dtype)
            if output_alpha is not None:
                strip[..., 3][mask] = (output_alpha[:, 0] * alpha_white).astype(dtype)
        tile.close()
    return output


def save_native(native: NativeImage, pixels: np.ndarray, path: Path) -> None:
    """Encode the original container and precision, without touching input bytes."""
    if native.output_format == "TIFF":
        kwargs: dict[str, Any] = {}
        if native.info.get("icc_profile"):
            kwargs["iccprofile"] = native.info["icc_profile"]
        if native.info.get("xresolution") and native.info.get("yresolution"):
            kwargs["resolution"] = (native.info["xresolution"], native.info["yresolution"])
            kwargs["resolutionunit"] = native.info.get("resolutionunit", 2)
        # Data is RGB after adding colored labels, including grayscale sources.
        tifffile.imwrite(path, pixels, photometric="rgb", metadata=None,
                         compression="deflate", rowsperstrip=128,
                         bigtiff=pixels.nbytes > 3_800_000_000, **kwargs)
    elif native.output_format == "PNG":
        encoded = imagecodecs.png_encode(np.ascontiguousarray(pixels), level=5)
        # ICC/gamma and physical pixel scale are independent of the added marks.
        chunks = native.info.get("png_color_chunks", b"")
        with path.open("wb") as stream:
            stream.write(encoded[:33])
            stream.write(chunks)
            stream.write(encoded[33:])
    else:
        image = Image.fromarray(pixels)
        exif_bytes = native.info.get("exif")
        kwargs = {key: native.info[key] for key in ("icc_profile", "dpi") if key in native.info}
        if exif_bytes:
            exif = Image.Exif()
            exif.load(exif_bytes)
            exif[274] = 1
            if 40962 in exif:
                exif[40962] = native.size[0]
            if 40963 in exif:
                exif[40963] = native.size[1]
            kwargs["exif"] = exif.tobytes()
        try:
            image.save(path, "JPEG", quality=97, subsampling=0, **kwargs)
        finally:
            image.close()


def _png_color_chunks(path: Path) -> bytes:
    chunks: list[bytes] = []
    with path.open("rb") as stream:
        if stream.read(8) != b"\x89PNG\r\n\x1a\n":
            return b""
        while header := stream.read(8):
            if len(header) != 8:
                break
            length, kind = struct.unpack(">I4s", header)
            if kind in {b"iCCP", b"sRGB", b"gAMA", b"cHRM", b"pHYs"} and length <= 4 * 1024 * 1024:
                chunks.append(header + stream.read(length + 4))
            else:
                stream.seek(length + 4, 1)
            if kind == b"IEND":
                break
    return b"".join(chunks)
