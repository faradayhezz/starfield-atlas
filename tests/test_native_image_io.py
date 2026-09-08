from __future__ import annotations

import hashlib
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import imagecodecs
import numpy as np
import tifffile
from PIL import Image, ImageCms, ImageDraw

from backend.image_io import composite_native, display_rgb, load_native, save_native


class NativeImageTests(unittest.TestCase):
    def test_rgb16_png_keeps_precision_and_unmarked_samples(self) -> None:
        pixels = np.arange(48 * 64 * 3, dtype=np.uint16).reshape(48, 64, 3) * 7
        self._lossless_roundtrip(pixels, ".png")

    def test_rgb16_tiff_keeps_precision_and_unmarked_samples(self) -> None:
        pixels = np.arange(48 * 64 * 3, dtype=np.uint16).reshape(48, 64, 3) * 7
        self._lossless_roundtrip(pixels, ".tiff")

    def test_float32_tiff_keeps_hdr_values_nan_and_negative_samples(self) -> None:
        pixels = np.linspace(-.1, 3., 48 * 64 * 3, dtype=np.float32).reshape(48, 64, 3)
        pixels[0, 0] = np.nan
        pixels[0, 1] = np.inf
        self._lossless_roundtrip(pixels, ".tif")

    def test_uint32_tiff_is_not_silently_reduced_to_8_bits(self) -> None:
        pixels = np.arange(48 * 64 * 3, dtype=np.uint32).reshape(48, 64, 3) * 123456
        self._lossless_roundtrip(pixels, ".tiff")

    def test_gray16_tiff_keeps_precision_when_adding_color_channels(self) -> None:
        pixels = np.arange(48 * 64, dtype=np.uint16).reshape(48, 64) * 17
        self._lossless_roundtrip(pixels, ".tiff")

    def test_rgba16_png_keeps_unmarked_alpha(self) -> None:
        pixels = np.arange(48 * 64 * 4, dtype=np.uint16).reshape(48, 64, 4) * 5
        self._lossless_roundtrip(pixels, ".png")

    def test_rgba_blend_does_not_leak_hidden_original_color(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "transparent.png"
            pixels = np.zeros((8, 8, 4), dtype=np.uint16)
            pixels[..., 2] = 65000  # blue exists only in transparent storage
            path.write_bytes(imagecodecs.png_encode(pixels))
            native = load_native(path)
            layer = Image.new("RGBA", native.size)
            layer.putpixel((4, 4), (255, 0, 0, 128))
            blended = composite_native(native, layer)
            np.testing.assert_array_equal(blended[4, 4, :3], [65535, 0, 0])
            self.assertAlmostEqual(int(blended[4, 4, 3]), 65535 * 128 / 255, delta=1)
            np.testing.assert_array_equal(blended[0, 0], pixels[0, 0])
            layer.close()
            native.close()

    def _lossless_roundtrip(self, pixels: np.ndarray, suffix: str) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / ("source" + suffix), root / ("annotated" + suffix)
            if suffix == ".png":
                source.write_bytes(imagecodecs.png_encode(pixels))
            else:
                tifffile.imwrite(source, pixels, photometric="rgb" if pixels.ndim == 3 else "minisblack")
            original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            native = load_native(source)
            self.assertEqual(native.size, (64, 48))
            self.assertEqual(native.metadata.bit_depth, pixels.dtype.itemsize * 8)
            overlay = Image.new("RGBA", native.size)
            ImageDraw.Draw(overlay).ellipse((20, 12, 36, 28), outline=(120, 210, 170, 130), width=1)
            alpha = np.array(overlay)[..., 3]
            composite = composite_native(native, overlay)
            save_native(native, composite, target)
            output = imagecodecs.png_decode(target.read_bytes()) if suffix == ".png" else tifffile.imread(target)
            self.assertEqual(output.dtype, pixels.dtype)
            expected = np.repeat(pixels[..., None], 3, axis=2) if pixels.ndim == 2 else pixels
            np.testing.assert_array_equal(output[alpha == 0], expected[alpha == 0])
            self.assertTrue(np.any(output[alpha > 0] != expected[alpha > 0]))
            np.testing.assert_array_equal(output[20, 28], expected[20, 28])  # ring leaves object centre intact
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), original_hash)
            preview = display_rgb(native, max_size=(32, 32))
            self.assertEqual(preview.mode, "RGB")
            self.assertEqual(preview.size, (32, 24))
            preview.close()
            overlay.close()
            native.close()

    def test_oriented_jpeg_exports_original_format_and_displayed_dimensions(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "source.jpeg"
            exif = Image.Exif()
            exif[274] = 6
            exif[271] = "Test camera"
            Image.new("RGB", (64, 48), (70, 40, 20)).save(path, exif=exif)
            native = load_native(path)
            self.assertEqual(native.size, (48, 64))
            self.assertEqual(native.extension, ".jpeg")
            target = root / "result.jpeg"
            save_native(native, native.pixels, target)
            with Image.open(target) as image:
                self.assertEqual(image.format, "JPEG")
                self.assertEqual(image.size, (48, 64))
                self.assertEqual(image.getexif()[274], 1)
                self.assertEqual(image.getexif()[271], "Test camera")
            native.close()

    def test_oriented_uint16_tiff_transposes_exactly_once(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "oriented.tiff"
            pixels = np.arange(64 * 48 * 3, dtype=np.uint16).reshape(48, 64, 3)
            tifffile.imwrite(path, pixels, photometric="rgb", extratags=[(274, "H", 1, 6, False)])
            native = load_native(path)
            self.assertEqual(native.size, (48, 64))
            np.testing.assert_array_equal(native.pixels, np.rot90(pixels, -1))
            native.close()

    def test_camera_mpo_with_jpeg_filename_decodes_primary_and_exports_jpeg(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / "camera.jpg", root / "annotated.jpg"
            exif = Image.Exif()
            exif[274] = 6
            exif[271] = "Test camera"
            profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
            primary = Image.new("RGB", (64, 48), (110, 60, 30))
            auxiliary = Image.new("RGB", (16, 12), (5, 230, 20))
            primary.save(source, "MPO", save_all=True, append_images=[auxiliary], exif=exif, icc_profile=profile)
            primary.close()
            auxiliary.close()
            original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            with Image.open(source) as image:
                self.assertEqual(image.format, "MPO")
                self.assertEqual(image.n_frames, 2)
                expected = np.rot90(np.array(image), -1)
            native = load_native(source)
            self.assertEqual(native.size, (48, 64))
            self.assertEqual(native.metadata.format, "MPO")
            self.assertEqual(native.metadata.camera_make, "Test camera")
            self.assertEqual(native.output_format, "JPEG")
            self.assertEqual(native.extension, ".jpg")
            self.assertEqual(native.metadata.bit_depth, 8)
            self.assertEqual(native.info["multipart_frames"], 2)
            self.assertIn("主图", native.export_info()["note"])
            np.testing.assert_array_equal(native.pixels, expected)
            save_native(native, native.pixels, target)
            with Image.open(target) as image:
                self.assertEqual(image.format, "JPEG")
                self.assertEqual(image.size, (48, 64))
                self.assertEqual(getattr(image, "n_frames", 1), 1)
                self.assertEqual(image.getexif()[274], 1)
                self.assertEqual(image.getexif()[271], "Test camera")
                self.assertEqual(image.info["icc_profile"], profile)
                self.assertNotIn("mp", image.info)
                self.assertNotIn("mpoffset", image.info)
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), original_hash)
            native.close()
            mpo_source = root / "camera.mpo"
            mpo_source.write_bytes(source.read_bytes())
            native_mpo = load_native(mpo_source)
            self.assertEqual(native_mpo.extension, ".jpg")
            self.assertEqual(native_mpo.size, (48, 64))
            self.assertEqual(native_mpo.metadata.format, "MPO")
            np.testing.assert_array_equal(native_mpo.pixels, expected)
            native_mpo.close()

    def test_png_with_jpeg_filename_exports_actual_container_without_losing_16bit(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / "shared.jpg", root / "annotated.png"
            pixels = np.arange(48 * 64 * 3, dtype=np.uint16).reshape(48, 64, 3) * 7
            source.write_bytes(imagecodecs.png_encode(pixels))
            native = load_native(source)
            self.assertEqual(native.output_format, "PNG")
            self.assertEqual(native.extension, ".png")
            self.assertEqual(native.metadata.format, "PNG")
            save_native(native, native.pixels, target)
            np.testing.assert_array_equal(imagecodecs.png_decode(target.read_bytes()), pixels)
            native.close()

    def test_unsupported_content_reports_actual_format_instead_of_filename(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "shared.jpg"
            with Image.new("RGB", (16, 12)) as image:
                image.save(source, "BMP")
            with self.assertRaisesRegex(ValueError, "实际格式为 BMP"):
                load_native(source)

    def test_inverted_grayscale_tiff_preserves_visual_brightness(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "white-is-zero.tiff"
            pixels = np.arange(64 * 48, dtype=np.uint16).reshape(48, 64)
            tifffile.imwrite(path, pixels, photometric="miniswhite")
            native = load_native(path)
            np.testing.assert_array_equal(native.pixels, 65535 - pixels)
            self.assertIn("RGB", native.export_info()["note"])
            native.close()

    def test_png_color_profile_chunks_survive_native_export(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / "source.png", root / "result.png"
            profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
            Image.new("RGB", (20, 12)).save(source, icc_profile=profile, dpi=(300, 300))
            native = load_native(source)
            save_native(native, native.pixels, target)
            with Image.open(target) as image:
                self.assertEqual(image.info["icc_profile"], profile)
                self.assertAlmostEqual(image.info["dpi"][0], 300, places=1)
            native.close()

    def test_invalid_raw_is_rejected_by_libraw(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.nef"
            path.write_bytes(b"not camera raw data")
            with self.assertRaisesRegex(ValueError, "LibRaw"):
                load_native(path)

    def test_cancel_checked_before_raw_decode(self) -> None:
        def cancel() -> None:
            raise InterruptedError("cancelled")
        with self.assertRaises(InterruptedError):
            load_native(Path("does-not-exist.nef"), cancel)

    @unittest.skipUnless(os.environ.get("RUN_RAW_TESTS") == "1", "set RUN_RAW_TESTS=1 with public RAW fixture downloaded")
    def test_real_nikon_nef_is_full_resolution_16_bit_and_camera_exif(self) -> None:
        path = Path(__file__).resolve().parents[1] / ".runtime/raw-fixtures/iss030e122639.NEF"
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), "5922721d13f11795557d97fdeb0a60b900086c402bc82a848ff280d15b99ffd4")
        native = load_native(path)
        self.assertEqual(native.size, (4284, 2844))
        self.assertEqual(native.pixels.dtype, np.uint16)
        self.assertTrue(native.metadata.is_raw)
        self.assertEqual(native.metadata.camera_model, "NIKON D3S")
        self.assertEqual(native.metadata.iso, 3200)
        self.assertEqual(native.metadata.focal_length_mm, 28.)
        self.assertEqual(native.export_info()["format"], "TIFF")
        self.assertGreater(int(native.pixels.max()), 255)
        with TemporaryDirectory() as directory:
            target = Path(directory) / "camera-render.tiff"
            save_native(native, native.pixels, target)
            decoded = tifffile.imread(target)
            self.assertEqual(decoded.dtype, np.uint16)
            self.assertEqual(decoded.shape, (2844, 4284, 3))
            np.testing.assert_array_equal(decoded, native.pixels)
        native.close()


if __name__ == "__main__":
    unittest.main()
