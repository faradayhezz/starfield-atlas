from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np
from PIL import Image

from backend.metadata import read_metadata
from backend.pipeline import AnalysisCancelled, _display_rgb, analyze_image
from backend.plate_solver import solve_plate


class FakeSolution:
    rmse_arcsec = 12.0

    @staticmethod
    def to_public_dict() -> dict[str, float]:
        return {"ra": 10.0, "dec": 20.0}


class PipelineControlTests(unittest.TestCase):
    def test_pipeline_reports_real_stages_in_order(self) -> None:
        events: list[tuple[str, int, str]] = []
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_path = root / "input.png"
            Image.new("RGB", (128, 96), "black").save(input_path)
            job_dir = root / "0123456789abcdef"

            def progress(stage: str, percent: int, message: str) -> None:
                if stage == "complete":
                    self.assertTrue((job_dir / "results.json").is_file())
                events.append((stage, percent, message))

            with (
                patch("backend.pipeline.solve_plate", return_value=FakeSolution()) as solve,
                patch("backend.pipeline.deep_sky_in_frame", return_value=[]),
                patch("backend.pipeline.bright_stars_in_frame", return_value=[]),
                patch("backend.pipeline.constellation_segments_in_frame", return_value=[]),
            ):
                result = analyze_image(
                    input_path,
                    job_dir,
                    filename="input.png",
                    progress_callback=progress,
                )

            self.assertEqual(result["status"], "complete")
            self.assertTrue((job_dir / "annotated-preview.jpg").is_file())
            self.assertTrue((job_dir / "annotated-full.jpg").is_file())
            self.assertTrue((job_dir / "results.json").is_file())

        self.assertEqual(
            [(stage, percent) for stage, percent, _ in events],
            [
                ("validation", 18),
                ("solving", 25),
                ("catalog", 55),
                ("preview", 65),
                ("full", 82),
                ("complete", 98),
            ],
        )
        self.assertTrue(all(message for _, _, message in events))
        self.assertIs(solve.call_args.kwargs["orientation_applied"], True)
        self.assertTrue(callable(solve.call_args.kwargs["cancel_callback"]))

    def test_pipeline_raises_cancelled_before_heavy_preview_work(self) -> None:
        cancelled = False
        events: list[str] = []

        def progress(stage: str, _percent: int, _message: str) -> None:
            nonlocal cancelled
            events.append(stage)
            if stage == "preview":
                cancelled = True

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_path = root / "input.png"
            Image.new("RGB", (128, 96), "black").save(input_path)
            job_dir = root / "0123456789abcdef"

            with (
                patch("backend.pipeline.solve_plate", return_value=FakeSolution()),
                patch("backend.pipeline.deep_sky_in_frame", return_value=[]),
                patch("backend.pipeline.bright_stars_in_frame", return_value=[]),
                patch("backend.pipeline.constellation_segments_in_frame", return_value=[]),
                patch("backend.pipeline.render_annotation") as render,
            ):
                with self.assertRaises(AnalysisCancelled):
                    analyze_image(
                        input_path,
                        job_dir,
                        filename="input.png",
                        progress_callback=progress,
                        is_cancelled=lambda: cancelled,
                    )

            render.assert_not_called()
            self.assertFalse((job_dir / "results.json").exists())
        self.assertEqual(events, ["validation", "solving", "catalog", "preview"])

    def test_solver_can_cancel_pipeline_before_catalog_and_render(self) -> None:
        cancelled = False

        def fake_solve(
            _image: Image.Image, _metadata: object, **kwargs: object
        ) -> FakeSolution:
            nonlocal cancelled
            cancel_callback = kwargs["cancel_callback"]
            self.assertTrue(callable(cancel_callback))
            cancelled = True
            cancel_callback()
            self.fail("cancel callback should have raised AnalysisCancelled")

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_path = root / "input.png"
            Image.new("RGB", (128, 96), "black").save(input_path)
            job_dir = root / "0123456789abcdef"

            with (
                patch("backend.pipeline.solve_plate", side_effect=fake_solve),
                patch("backend.pipeline.deep_sky_in_frame") as catalog,
                patch("backend.pipeline.render_annotation") as render,
                patch("backend.pipeline.save_jpeg") as save,
            ):
                with self.assertRaises(AnalysisCancelled):
                    analyze_image(
                        input_path,
                        job_dir,
                        filename="input.png",
                        is_cancelled=lambda: cancelled,
                    )

            catalog.assert_not_called()
            render.assert_not_called()
            save.assert_not_called()
            self.assertFalse((job_dir / "results.json").exists())

    def test_preview_is_reduced_before_annotation(self) -> None:
        render_inputs: list[tuple[tuple[int, int], tuple[int, int] | None]] = []
        render_sources: list[Image.Image] = []
        render_outputs: list[Image.Image] = []

        def fake_render(
            image: Image.Image, *args: object, **kwargs: object
        ) -> Image.Image:
            if render_sources:
                with self.assertRaises(ValueError):
                    render_sources[0].getbbox()
                with self.assertRaises(ValueError):
                    render_outputs[0].getbbox()
            render_inputs.append((image.size, kwargs.get("coordinate_size")))
            render_sources.append(image)
            output = Image.new("RGB", image.size, "black")
            render_outputs.append(output)
            return output

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_path = root / "input.png"
            Image.new("RGB", (2500, 1000), "black").save(input_path)
            job_dir = root / "0123456789abcdef"

            with (
                patch("backend.pipeline.solve_plate", return_value=FakeSolution()),
                patch("backend.pipeline.deep_sky_in_frame", return_value=[]),
                patch("backend.pipeline.bright_stars_in_frame", return_value=[]),
                patch("backend.pipeline.constellation_segments_in_frame", return_value=[]),
                patch("backend.pipeline.render_annotation", side_effect=fake_render),
                patch("backend.pipeline.save_jpeg"),
            ):
                analyze_image(input_path, job_dir, filename="input.png")

        self.assertEqual(
            render_inputs,
            [
                ((2400, 960), (2500, 1000)),
                ((2500, 1000), None),
            ],
        )
        for image in (*render_sources, *render_outputs):
            with self.assertRaises(ValueError):
                image.getbbox()

    def test_large_high_bit_display_conversion_bounds_numpy_buffers(self) -> None:
        image = Image.new("I;16", (2500, 1000), 1024)
        original_asarray = np.asarray
        buffers: list[tuple[tuple[int, int], int]] = []

        def tracked_asarray(
            value: object, dtype: object = None, *args: object, **kwargs: object
        ) -> np.ndarray:
            if isinstance(value, Image.Image):
                item_size = np.dtype(dtype).itemsize if dtype is not None else 1
                buffers.append((value.size, value.width * value.height * item_size))
            return original_asarray(value, dtype=dtype, *args, **kwargs)

        try:
            with patch("backend.pipeline.np.asarray", side_effect=tracked_asarray):
                converted = _display_rgb(image)
            try:
                self.assertEqual(converted.mode, "RGB")
                self.assertEqual(converted.size, image.size)
            finally:
                converted.close()
        finally:
            image.close()

        self.assertNotEqual(buffers[0][0], (2500, 1000))
        self.assertTrue(all(byte_count <= 32 * 1024 * 1024 for _, byte_count in buffers))


class PlateSolverControlTests(unittest.TestCase):
    def test_preoriented_image_skips_duplicate_exif_transpose(self) -> None:
        class SolverStopped(Exception):
            pass

        class FakeSolver:
            @staticmethod
            def solve_from_image(*_args: object, **_kwargs: object) -> None:
                raise SolverStopped

        image = Image.new("RGB", (120, 80), "black")
        try:
            metadata = read_metadata(image)
            with (
                patch("backend.plate_solver._get_solver", return_value=FakeSolver()),
                patch("backend.plate_solver.ImageOps.exif_transpose") as transpose,
            ):
                with self.assertRaises(SolverStopped):
                    solve_plate(image, metadata, orientation_applied=True)
            transpose.assert_not_called()
        finally:
            image.close()

    def test_solver_checks_cancellation_between_attempts(self) -> None:
        class SolverCancelled(Exception):
            pass

        class FakeSolver:
            calls = 0

            def solve_from_image(self, *_args: object, **_kwargs: object) -> None:
                self.calls += 1
                return None

        solver = FakeSolver()
        checks = 0

        def cancel() -> None:
            nonlocal checks
            checks += 1
            if checks == 4:
                raise SolverCancelled

        image = Image.new("RGB", (120, 80), "black")
        try:
            metadata = read_metadata(image)
            with patch("backend.plate_solver._get_solver", return_value=solver):
                with self.assertRaises(SolverCancelled):
                    solve_plate(
                        image,
                        metadata,
                        orientation_applied=True,
                        cancel_callback=cancel,
                    )
        finally:
            image.close()

        self.assertEqual(solver.calls, 1)
        self.assertEqual(checks, 4)


if __name__ == "__main__":
    unittest.main()
