from __future__ import annotations

import io
import unittest

from PIL import Image

from backend.metadata import ImageMetadata, estimated_horizontal_fov, read_metadata


class MetadataTests(unittest.TestCase):
    def test_28mm_full_frame_horizontal_fov(self) -> None:
        metadata = ImageMetadata(width=9504, height=6336, focal_length_35mm=28)
        fov = estimated_horizontal_fov(metadata)
        self.assertIsNotNone(fov)
        self.assertAlmostEqual(fov or 0, 65.47, places=2)

    def test_missing_focal_length_is_not_guessed(self) -> None:
        metadata = ImageMetadata(width=1000, height=1000)
        self.assertIsNone(estimated_horizontal_fov(metadata))

    def test_orientation_dimensions_are_derived_without_pixel_transpose(self) -> None:
        payload = io.BytesIO()
        exif = Image.Exif()
        exif[274] = 6
        Image.new("RGB", (12, 7), "black").save(payload, "JPEG", exif=exif)
        payload.seek(0)
        with Image.open(payload) as image:
            metadata = read_metadata(image)
            self.assertEqual((metadata.width, metadata.height), (7, 12))
            self.assertEqual(metadata.orientation, 6)
            # Reading EXIF alone must not force a full JPEG pixel decode.
            self.assertIsNone(getattr(image, "_im", None))


if __name__ == "__main__":
    unittest.main()
