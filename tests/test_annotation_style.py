from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image, ImageChops

from backend.annotate import DSO_COLOR, render_annotation, render_annotation_layer
from backend.pipeline import DEFAULT_SETTINGS, analyze_image, normalize_settings
from backend.server import _bool, _font_weight, _hex_color


class AnnotationStyleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.deep_sky = [
            {
                "x": 100,
                "y": 100,
                "radiusPx": 20,
                "label": "M31",
                "expectedVisible": True,
                "priority": 100,
            }
        ]
        self.bright_stars = [{"x": 250, "y": 100, "label": "亮星"}]
        self.segments = [
            {
                "x1": 20,
                "y1": 180,
                "x2": 380,
                "y2": 180,
                "constellation": "Test",
                "constellationName": "",
            }
        ]

    def test_server_style_parsers_accept_only_supported_values(self) -> None:
        self.assertEqual(_hex_color("#a1B2c3", "#28E863"), "#A1B2C3")
        self.assertEqual(_hex_color("a1B2c3", "#28E863"), "#28E863")
        self.assertEqual(_hex_color(" #A1B2C3", "#28E863"), "#28E863")
        self.assertEqual(_hex_color("#fff;drop table", "#28E863"), "#28E863")
        self.assertEqual(_font_weight("500", 500), 500)
        self.assertEqual(_font_weight("650", 500), 650)
        self.assertEqual(_font_weight("800", 500), 800)
        self.assertEqual(_font_weight("700", 500), 500)
        self.assertIs(_bool("true", False), True)
        self.assertIs(_bool("false", True), False)
        self.assertIs(_bool("not-a-bool", True), True)

    def test_pipeline_normalizes_direct_call_settings(self) -> None:
        settings = normalize_settings(
            {
                "deepSkyColor": "#123abc",
                "brightStarColor": "red",
                "constellationColor": "#ABCDEF00",
                "fontWeight": "800",
                "highContrast": "true",
            }
        )
        self.assertEqual(settings["deepSkyColor"], "#123ABC")
        self.assertEqual(settings["brightStarColor"], DEFAULT_SETTINGS["brightStarColor"])
        self.assertEqual(
            settings["constellationColor"], DEFAULT_SETTINGS["constellationColor"]
        )
        self.assertEqual(settings["fontWeight"], 800)
        self.assertIs(settings["highContrast"], True)

    def test_renderer_uses_all_three_custom_colors(self) -> None:
        rendered = render_annotation(
            Image.new("RGB", (400, 220), "black"),
            self.deep_sky,
            self.bright_stars,
            self.segments,
            constellation_strength=100,
            deep_sky_color="#FF00FF",
            bright_star_color="#00FFFF",
            constellation_color="#FF3300",
            annotation_opacity=1,
            show_constellations=True,
        )
        pixels = set(rendered.get_flattened_data())
        # Fractional thin strokes and antialiased glyphs retain the selected
        # hue, without requiring an opaque one-pixel coverage sample.
        self.assertTrue(any(r > 180 and g == 0 and r == b for r, g, b in pixels))
        self.assertTrue(any(g > 180 and r == 0 and g == b for r, g, b in pixels))
        self.assertEqual(rendered.getpixel((40, 180)), (255, 51, 0))

    def test_default_style_is_subdued_and_transparent_at_target_core(self) -> None:
        rendered = render_annotation(
            Image.new("RGB", (400, 220), "black"),
            self.deep_sky,
            show_bright_stars=False,
            show_constellations=False,
        )
        self.assertEqual(rendered.getpixel((100, 100)), (0, 0, 0))
        self.assertNotIn(DSO_COLOR, set(rendered.get_flattened_data()))
        self.assertIsNotNone(rendered.getbbox())

    def test_stellar_cores_are_unchanged_even_with_crossing_lines_and_emphasis(self) -> None:
        background = Image.new("RGB", (1920, 1280), (13, 29, 47))
        stars = [{"x": 600, "y": 500, "label": "HIP 123", "magnitude": 2}]
        segments = [{"x1": 200, "y1": 500, "x2": 1200, "y2": 500}]
        for style in ("circle", "corners"):
            for contrast in (False, True):
                with self.subTest(style=style, high_contrast=contrast):
                    layer = render_annotation_layer(background.size, [], stars, segments, show_constellations=True,
                                                    high_contrast=contrast, marker_style=style, annotation_opacity=1,
                                                    annotation_line_width=3, font_weight=800)
                    self.assertEqual(layer.getpixel((600, 500))[3], 0)
                    self.assertEqual(layer.getpixel((603, 500))[3], 0)
                    output = render_annotation(background, [], stars, segments, show_constellations=True,
                                               high_contrast=contrast, marker_style=style, annotation_opacity=1,
                                               annotation_line_width=3, font_weight=800)
                    self.assertEqual(output.getpixel((600, 500)), background.getpixel((600, 500)))

    def test_stellar_budget_can_draw_faint_stars_without_deep_sky_override(self) -> None:
        star = {"x": 200, "y": 100, "label": "HIP 999", "magnitude": 11, "defaultVisible": False}
        hidden = render_annotation_layer((400, 250), [], [star])
        shown = render_annotation_layer((400, 250), [], [star], include_catalog_only=True)
        self.assertIsNotNone(hidden.getbbox())
        self.assertIsNotNone(shown.getbbox())

    def test_zero_opacity_preserves_all_source_pixels(self) -> None:
        background = Image.new("RGB", (400, 220), (31, 62, 93))
        output = render_annotation(background, self.deep_sky, self.bright_stars, self.segments, annotation_opacity=0)
        self.assertIsNone(ImageChops.difference(background, output).getbbox())

    def test_heavy_high_contrast_style_changes_pixels(self) -> None:
        background = Image.new("RGB", (400, 220), (38, 42, 50))
        normal = render_annotation(
            background,
            self.deep_sky,
            self.bright_stars,
            self.segments,
            font_weight=500,
            high_contrast=False,
        )
        emphasized = render_annotation(
            background,
            self.deep_sky,
            self.bright_stars,
            self.segments,
            font_weight=800,
            high_contrast=True,
        )
        self.assertIsNotNone(ImageChops.difference(normal, emphasized).getbbox())

    def test_pipeline_passes_styles_to_preview_and_full_render(self) -> None:
        class FakeSolution:
            rmse_arcsec = 12.0

            @staticmethod
            def to_public_dict() -> dict[str, float]:
                return {"ra": 10.0, "dec": 20.0}

        custom = {
            "deepSkyColor": "#112233",
            "brightStarColor": "#445566",
            "constellationColor": "#778899",
            "fontWeight": 800,
            "highContrast": False,
        }
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_path = root / "input.png"
            Image.new("RGB", (64, 48), "black").save(input_path)
            job_dir = root / "0123456789abcdef"

            def fake_render(image: Image.Image, *args: object, **kwargs: object) -> Image.Image:
                return image.convert("RGB")

            with (
                patch("backend.pipeline.solve_plate", return_value=FakeSolution()),
                patch("backend.pipeline.deep_sky_in_frame", return_value=[]),
                patch("backend.pipeline.bright_stars_in_frame", return_value=[]),
                patch("backend.pipeline.constellation_segments_in_frame", return_value=[]),
                patch("backend.pipeline.render_annotation", side_effect=fake_render) as render,
                patch("backend.pipeline.render_annotation_layer", wraps=render_annotation_layer) as full_render,
            ):
                result = analyze_image(
                    input_path,
                    job_dir,
                    filename="input.png",
                    settings=custom,
                )

        self.assertEqual(render.call_count, 1)
        self.assertEqual(full_render.call_count, 1)
        for invocation in [*render.call_args_list, *full_render.call_args_list]:
            self.assertEqual(invocation.kwargs["deep_sky_color"], "#112233")
            self.assertEqual(invocation.kwargs["bright_star_color"], "#445566")
            self.assertEqual(invocation.kwargs["constellation_color"], "#778899")
            self.assertEqual(invocation.kwargs["font_weight"], 800)
            self.assertIs(invocation.kwargs["high_contrast"], False)
        self.assertEqual(result["settings"]["fontWeight"], 800)


if __name__ == "__main__":
    unittest.main()
