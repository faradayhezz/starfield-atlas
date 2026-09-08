from __future__ import annotations

import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageChops, ImageDraw

from backend.annotate import render_annotation, render_annotation_layer


def _dso(x: float, y: float, radius: float = 20, magnitude: float = 14, **extra) -> dict:
    return {"x": x, "y": y, "radiusPx": radius, "magnitude": magnitude,
            "expectedVisible": True, "priority": 50, **extra}


class AnnotationGeometryTests(unittest.TestCase):
    """Pixel-level regressions for overlapping catalog markers, not sky detection."""

    def test_neighboring_markers_do_not_erase_each_others_arcs(self) -> None:
        targets = [_dso(500, 350), _dso(530, 350)]
        options = {"annotation_opacity": 1, "annotation_line_width": 2,
                   "show_bright_stars": False, "high_contrast": False}
        for style in ("circle", "corners"):
            with self.subTest(style=style):
                alone = [render_annotation_layer((1920, 800), [target], marker_style=style, **options)
                         for target in targets]
                combined = render_annotation_layer((1920, 800), targets, marker_style=style, **options)
                try:
                    expected = np.maximum(np.asarray(alone[0])[300:400, 450:580, 3],
                                          np.asarray(alone[1])[300:400, 450:580, 3])
                    actual = np.asarray(combined)[300:400, 450:580, 3]
                    # A nearby target's transparent core cannot punch a hole in
                    # pixels already occupied by the other object's outline.
                    self.assertFalse(np.any((expected > 64) & (actual == 0)))
                finally:
                    for layer in [*alone, combined]:
                        layer.close()

    def test_contrast_mode_has_no_black_halo_on_marker_outline(self) -> None:
        layer = render_annotation_layer((1920, 800), [_dso(500, 350, label="NGC 6269")],
                                        high_contrast=True, annotation_opacity=1,
                                        annotation_line_width=3)
        try:
            marker = np.asarray(layer)[320:381, 470:531]
            opaque = marker[:, :, 3] > 0
            black = np.all(marker[:, :, :3] == (5, 7, 9), axis=2)
            self.assertTrue(np.any(opaque))
            self.assertFalse(np.any(opaque & black), "Text contrast must not add opaque ring underlays")
        finally:
            layer.close()

    def test_clear_ring_interior_retains_source_pixels(self) -> None:
        rng = np.random.default_rng(1269)
        source = Image.fromarray(rng.integers(0, 256, (700, 1920, 3), dtype=np.uint8))
        for style in ("circle", "corners"):
            with self.subTest(style=style):
                rendered = render_annotation(source, [_dso(500, 350, radius=30)],
                                             marker_style=style, high_contrast=True,
                                             annotation_line_width=3)
                try:
                    bounds = (481, 331, 519, 369)
                    self.assertIsNone(ImageChops.difference(source.crop(bounds), rendered.crop(bounds)).getbbox())
                finally:
                    rendered.close()
        source.close()

    def test_label_placement_avoids_full_neighboring_marker_bounds(self) -> None:
        draw_text = ImageDraw.ImageDraw.text
        labels = []

        def capture_text(draw, position, text, *args, **kwargs):
            if text:
                labels.append(draw.textbbox(position, text, font=kwargs.get("font"),
                                            anchor=kwargs.get("anchor"),
                                            stroke_width=kwargs.get("stroke_width", 0)))
            return draw_text(draw, position, text, *args, **kwargs)

        targets = [_dso(300, 300, label="A", priority=100), _dso(370, 300, radius=35)]
        with patch.object(ImageDraw.ImageDraw, "text", capture_text):
            layer = render_annotation_layer((1920, 800), targets)
            layer.close()
        self.assertEqual(len(labels), 1)
        # Neighboring ring radius = source radius 35 + 5 pixels clearance.
        left, top, right, bottom = labels[0]
        self.assertTrue(right < 330 or left > 410 or bottom < 260 or top > 340,
                        f"The label intersects the neighboring 80px marker: {labels[0]}")

    def test_faint_marker_setting_reduces_stroke_without_dimming_color(self) -> None:
        options = dict(size=(3840, 900), deep_sky=[_dso(700, 350, magnitude=15)],
                       annotation_line_width=3, annotation_opacity=1)
        wide = render_annotation_layer(**options, faint_marker_scale=1)
        thin = render_annotation_layer(**options, faint_marker_scale=.6)
        try:
            wide_pixels, thin_pixels = np.asarray(wide), np.asarray(thin)
            self.assertLess(float(thin_pixels[:, :, 3].sum()), float(wide_pixels[:, :, 3].sum()) * .85)
            self.assertEqual(tuple(wide_pixels[wide_pixels[:, :, 3].argmax() // wide.width,
                                               wide_pixels[:, :, 3].argmax() % wide.width, :3]),
                             tuple(thin_pixels[thin_pixels[:, :, 3].argmax() // thin.width,
                                               thin_pixels[:, :, 3].argmax() % thin.width, :3]))
        finally:
            wide.close()
            thin.close()

    def test_dense_scene_leaders_never_cross_another_rendered_label(self) -> None:
        # A deterministic compact galaxy-group layout: marker positions are
        # synthetic, while the test inspects the renderer's emitted geometry.
        rng = np.random.default_rng(6269)
        targets = [_dso(float(x), float(y), radius=5, label=f"NGC {1000 + index}",
                        priority=100 - index)
                   for index, (x, y) in enumerate(rng.uniform((850, 430), (1050, 650), (28, 2)))]
        text_boxes, leader_lines = [], []
        draw_text, draw_line = ImageDraw.ImageDraw.text, ImageDraw.ImageDraw.line

        def capture_text(draw, position, text, *args, **kwargs):
            if text:
                text_boxes.append((text, draw.textbbox(position, text, font=kwargs.get("font"),
                                                      anchor=kwargs.get("anchor"),
                                                      stroke_width=kwargs.get("stroke_width", 0))))
            return draw_text(draw, position, text, *args, **kwargs)

        def capture_line(draw, coordinates, *args, **kwargs):
            leader_lines.append(tuple(coordinates))
            return draw_line(draw, coordinates, *args, **kwargs)

        with patch.object(ImageDraw.ImageDraw, "text", capture_text), \
                patch.object(ImageDraw.ImageDraw, "line", capture_line):
            layer = render_annotation_layer((1920, 1080), targets, marker_style="circle",
                                            show_constellations=False, show_bright_stars=False,
                                            label_density="dense", high_contrast=True)
            layer.close()
        self.assertGreater(len(leader_lines), 1, "The dense scene must exercise relocated labels")
        self.assertGreater(len(text_boxes), 10)
        for x1, y1, x2, y2 in leader_lines:
            # Sample more finely than a pixel; touching its own label edge is
            # valid, passing through any rendered text-box interior is not.
            samples = max(2, int(np.hypot(x2 - x1, y2 - y1) * 4) + 1)
            t = np.linspace(0, 1, samples)
            x, y = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
            for label, (left, top, right, bottom) in text_boxes:
                inside = (x > left + .25) & (x < right - .25) & (y > top + .25) & (y < bottom - .25)
                self.assertFalse(inside.any(), f"A leader crosses rendered label {label}")

    def test_star_marker_budget_is_independent_of_dso_labels_and_old_flags(self) -> None:
        stars = [{"x": 80 + index % 20 * 85, "y": 100 + index // 20 * 90,
                  "magnitude": 8 + index / 1000, "defaultVisible": False,
                  "recommendedLabel": False, "expectedVisible": False,
                  "evidence": "catalog_position", "pixelDetected": False}
                 for index in range(200)]
        for density, expected in (("sparse", 20), ("balanced", 60), ("dense", 180)):
            with self.subTest(star_density=density):
                layer = render_annotation_layer((1920, 1280), [_dso(1800, 1150)], stars,
                                                label_limit=1, star_label_density=density)
                try:
                    rendered_count = sum(layer.crop((s["x"] - 20, s["y"] - 20,
                                                     s["x"] + 21, s["y"] + 21)).getbbox() is not None
                                         for s in stars)
                    self.assertEqual(rendered_count, expected)
                finally:
                    layer.close()
        self.assertTrue(all(s["pixelDetected"] is False and s["evidence"] == "catalog_position" for s in stars))


if __name__ == "__main__":
    unittest.main()
