from __future__ import annotations

import math
import sys
import threading
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from time import perf_counter
from collections.abc import Callable
from typing import Any, Iterable

import numpy as np
from PIL import Image, ImageOps

from .app_paths import RESOURCE_ROOT
from .metadata import ImageMetadata, estimated_horizontal_fov


LOCAL_DEPS = RESOURCE_ROOT / ".deps"
if LOCAL_DEPS.exists() and str(LOCAL_DEPS) not in sys.path:
    sys.path.insert(0, str(LOCAL_DEPS))

# tetra3 0.1 still references the removed NumPy 1.x ``np.math`` alias.
# Supplying the standard-library module keeps the upstream solver working on
# NumPy 2 without modifying the installed third-party source.
if not hasattr(np, "math"):
    setattr(np, "math", math)

try:
    import tetra3
except ModuleNotFoundError as exc:  # pragma: no cover - surfaced by API startup
    raise RuntimeError(
        "缺少 tetra3。请运行 scripts/setup.ps1 安装本地星图解算依赖。"
    ) from exc


_solver_lock = threading.Lock()
_solve_run_lock = threading.Lock()
_solver_instance: Any | None = None


def _get_solver() -> Any:
    global _solver_instance
    with _solver_lock:
        if _solver_instance is None:
            _solver_instance = tetra3.Tetra3()
    return _solver_instance


@dataclass(slots=True)
class PlateSolution:
    center_ra_deg: float
    center_dec_deg: float
    roll_deg: float
    horizontal_fov_deg: float
    vertical_fov_deg: float
    crop_fov_deg: float
    distortion: float
    rmse_arcsec: float
    matches: int
    false_positive_probability: float
    solve_ms: float
    image_width: int
    image_height: int
    focal_pixels: float
    principal_x: float
    principal_y: float
    radial_reference_width: float
    rotation_matrix: list[list[float]]
    method: str = "tetra3-central-crop"
    verification: dict[str, Any] | None = None

    def to_public_dict(self) -> dict[str, Any]:
        result = asdict(self)
        corner_x = np.asarray(
            [0.0, self.image_width - 1.0, self.image_width - 1.0, 0.0]
        )
        corner_y = np.asarray(
            [0.0, 0.0, self.image_height - 1.0, self.image_height - 1.0]
        )
        corner_ra, corner_dec = self.pixel_to_world(corner_x, corner_y)
        result["frame_corners_radec"] = [
            {"ra_deg": round(float(ra), 7), "dec_deg": round(float(dec), 7)}
            for ra, dec in zip(corner_ra, corner_dec, strict=True)
        ]
        edge_samples = 32
        top_x = np.linspace(0, self.image_width - 1, edge_samples, endpoint=False)
        right_y = np.linspace(0, self.image_height - 1, edge_samples, endpoint=False)
        bottom_x = np.linspace(
            self.image_width - 1, 0, edge_samples, endpoint=False
        )
        left_y = np.linspace(
            self.image_height - 1, 0, edge_samples, endpoint=False
        )
        boundary_x = np.concatenate(
            (
                top_x,
                np.full(edge_samples, self.image_width - 1.0),
                bottom_x,
                np.zeros(edge_samples),
            )
        )
        boundary_y = np.concatenate(
            (
                np.zeros(edge_samples),
                right_y,
                np.full(edge_samples, self.image_height - 1.0),
                left_y,
            )
        )
        boundary_ra, boundary_dec = self.pixel_to_world(boundary_x, boundary_y)
        result["frame_boundary_radec"] = [
            {"ra_deg": round(float(ra), 7), "dec_deg": round(float(dec), 7)}
            for ra, dec in zip(boundary_ra, boundary_dec, strict=True)
        ]
        result["pixel_scale_arcsec"] = round(
            math.degrees(math.atan2(1.0, self.focal_pixels)) * 3600,
            4,
        )
        result.pop("rotation_matrix")
        result.pop("focal_pixels")
        result.pop("principal_x")
        result.pop("principal_y")
        result.pop("radial_reference_width")
        return result

    @property
    def rotation(self) -> np.ndarray:
        return np.asarray(self.rotation_matrix, dtype=np.float64)

    def world_to_pixel(
        self, ra_deg: Iterable[float] | np.ndarray, dec_deg: Iterable[float] | np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        sky = sky_vectors(ra_deg, dec_deg)
        camera = (self.rotation @ sky.T).T
        in_front = camera[:, 0] > 1e-8
        safe_x = np.where(in_front, camera[:, 0], np.nan)
        x_u = self.principal_x - self.focal_pixels * camera[:, 1] / safe_x
        y_u = self.principal_y - self.focal_pixels * camera[:, 2] / safe_x
        points = np.column_stack((y_u, x_u))
        points = _distort_points(
            points,
            (self.principal_y, self.principal_x),
            self.distortion,
            self.radial_reference_width,
        )
        return points[:, 1], points[:, 0], in_front

    def pixel_to_world(
        self, x: Iterable[float] | np.ndarray, y: Iterable[float] | np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        """Invert the calibrated camera projection for image points.

        These J2000 coordinates let the UI draw the actual four-sided sensor
        footprint instead of approximating it with a circle or roll-only box.
        """

        x_values = np.asarray(x, dtype=np.float64)
        y_values = np.asarray(y, dtype=np.float64)
        if x_values.shape != y_values.shape:
            raise ValueError("x and y must have matching shapes")
        points = np.column_stack((y_values.ravel(), x_values.ravel()))
        center = np.array([self.principal_y, self.principal_x], dtype=np.float64)
        relative = points - center
        if self.distortion and abs(self.distortion) >= 1e-8:
            radius_distorted = np.linalg.norm(relative, axis=1)
            normalized_sq = (2 * radius_distorted / self.radial_reference_width) ** 2
            radius_undistorted = (
                radius_distorted
                * (1 - self.distortion * normalized_sq)
                / (1 - self.distortion)
            )
            scale = np.divide(
                radius_undistorted,
                radius_distorted,
                out=np.ones_like(radius_undistorted),
                where=radius_distorted > 1e-12,
            )
            points = center + relative * scale[:, None]

        camera = np.ones((len(points), 3), dtype=np.float64)
        camera[:, 1] = (self.principal_x - points[:, 1]) / self.focal_pixels
        camera[:, 2] = (self.principal_y - points[:, 0]) / self.focal_pixels
        camera /= np.linalg.norm(camera, axis=1)[:, None]
        sky = (self.rotation.T @ camera.T).T
        ra = np.degrees(np.arctan2(sky[:, 1], sky[:, 0])) % 360.0
        dec = np.degrees(np.arcsin(np.clip(sky[:, 2], -1.0, 1.0)))
        return ra.reshape(x_values.shape), dec.reshape(y_values.shape)


def sky_vectors(
    ra_deg: Iterable[float] | np.ndarray, dec_deg: Iterable[float] | np.ndarray
) -> np.ndarray:
    ra = np.deg2rad(np.asarray(ra_deg, dtype=np.float64))
    dec = np.deg2rad(np.asarray(dec_deg, dtype=np.float64))
    cos_dec = np.cos(dec)
    return np.column_stack((cos_dec * np.cos(ra), cos_dec * np.sin(ra), np.sin(dec)))


def _undistort_points(
    points_yx: np.ndarray, size_hw: tuple[int, int], k: float
) -> np.ndarray:
    points = np.asarray(points_yx, dtype=np.float64).copy()
    if not k:
        return points
    height, width = size_hw
    center = np.array([height / 2, width / 2], dtype=np.float64)
    relative = points - center
    radius = np.linalg.norm(relative, axis=1)
    scale = (1 - k * (radius / width * 2) ** 2) / (1 - k)
    return center + relative * scale[:, None]


def _distort_points(
    points_yx: np.ndarray,
    center_yx: tuple[float, float],
    k: float,
    reference_width: float,
) -> np.ndarray:
    points = np.asarray(points_yx, dtype=np.float64).copy()
    if not k or abs(k) < 1e-8:
        return points
    center = np.asarray(center_yx, dtype=np.float64)
    relative = points - center
    r_u = np.linalg.norm(relative, axis=1)
    r_d = r_u.copy()
    denominator = 1 - k
    for _ in range(30):
        normalized_sq = (2 * r_d / reference_width) ** 2
        estimate = r_d * (1 - k * normalized_sq) / denominator
        derivative = (1 - 3 * k * normalized_sq) / denominator
        step = (estimate - r_u) / np.where(abs(derivative) > 1e-9, derivative, 1)
        r_d -= step
        if np.nanmax(np.abs(step), initial=0) < 1e-5:
            break
    scale = np.divide(r_d, r_u, out=np.ones_like(r_d), where=r_u > 1e-12)
    return center + relative * scale[:, None]


def _image_vectors(
    points_yx: np.ndarray, size_hw: tuple[int, int], fov_deg: float, k: float
) -> np.ndarray:
    height, width = size_hw
    points = _undistort_points(points_yx, size_hw, k)
    factor = math.tan(math.radians(fov_deg) / 2) / width * 2
    vectors = np.ones((len(points), 3), dtype=np.float64)
    vectors[:, 1] = (width / 2 - points[:, 1]) * factor
    vectors[:, 2] = (height / 2 - points[:, 0]) * factor
    vectors /= np.linalg.norm(vectors, axis=1)[:, None]
    return vectors


def _rotation_from_matches(image_vectors: np.ndarray, catalog_vectors: np.ndarray) -> np.ndarray:
    covariance = image_vectors.T @ catalog_vectors
    u, _, v = np.linalg.svd(covariance)
    rotation = u @ v
    if np.linalg.det(rotation) < 0:
        u[:, -1] *= -1
        rotation = u @ v
    return rotation


def _central_crop(
    image: Image.Image, full_fov_deg: float | None
) -> tuple[Image.Image, tuple[int, int, int, int], float | None]:
    box, crop_fov = _central_crop_spec(image.size, full_fov_deg)
    return image.crop(box), box, crop_fov


def _central_crop_spec(
    size: tuple[int, int], full_fov_deg: float | None
) -> tuple[tuple[int, int, int, int], float | None]:
    """Return a crop description without allocating its pixel buffer."""

    width, height = size
    if full_fov_deg and full_fov_deg > 29:
        target = 26.5
        fraction = math.tan(math.radians(target / 2)) / math.tan(math.radians(full_fov_deg / 2))
        crop_width = int(width * min(0.9, max(0.22, fraction)))
        crop_fov = math.degrees(
            2 * math.atan((crop_width / width) * math.tan(math.radians(full_fov_deg / 2)))
        )
        crop_height = min(crop_width, height)
    else:
        crop_width = width
        crop_height = height
        crop_fov = full_fov_deg
    left = (width - crop_width) // 2
    top = (height - crop_height) // 2
    box = (left, top, left + crop_width, top + crop_height)
    return box, crop_fov


def _proxy(image: Image.Image, max_side: int = 1800) -> tuple[Image.Image, float]:
    scale = min(1.0, max_side / max(image.size))
    if scale == 1:
        return image.copy(), 1.0
    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    return image.resize(size, Image.Resampling.LANCZOS), scale


def _blind_crop_specs(size: tuple[int, int]) -> list[tuple[tuple[int, int, int, int], None]]:
    """Describe centred multi-scale probes without assuming camera EXIF.

    A 32% rectilinear crop turns a roughly 70-degree phone field into about
    25 degrees, inside the existing real Hipparcos pattern database. No camera
    model or sky-coordinate hint is inferred from a filename or reference image.
    """
    width, height = size
    specs = [((0, 0, width, height), None)]
    seen: set[tuple[int, int, int, int]] = {specs[0][0]}
    for fraction in (.32, .42, .68):
        crop_width = min(width, height, round(width * fraction))
        crop_height = min(crop_width, height)
        # Matching parity keeps the optical centre exactly at the full-frame
        # centre instead of silently shifting an odd-sized crop by half a pixel.
        crop_width -= (width - crop_width) % 2
        crop_height -= (height - crop_height) % 2
        if min(crop_width, crop_height) < 32:
            continue
        left, top = (width - crop_width) // 2, (height - crop_height) // 2
        box = (left, top, left + crop_width, top + crop_height)
        if box not in seen:
            specs.append((box, None))
            seen.add(box)
    return specs


def _refine_wide_phone_solution(
    image: Image.Image, initial: PlateSolution, solver: Any,
    cancel_callback: Callable[[], None] | None = None,
) -> PlateSolution | None:
    """Validate a new small central probe with independent full-field anchors.

    This path is only used for the added no-EXIF 32% probe. Existing successful
    DSLR/hinted/full-frame paths keep their established projection unchanged.
    One quarter of catalogue candidates never enter the refinement fit.
    """
    from scipy.optimize import least_squares
    from scipy.spatial import cKDTree
    from scipy.spatial.transform import Rotation

    proxy, scale = _proxy(image)
    try:
        if cancel_callback:
            cancel_callback()
        observed = np.asarray(tetra3.get_centroids_from_image(
            proxy, sigma=3, filtsize=25, bg_sub_mode="local_mean",
            sigma_mode="global_median_abs", binary_open=False,
            min_area=1, max_area=200, max_returned=300,
        ), dtype=np.float64)
        if len(observed) < 24:
            return None
        table = solver.star_table
        ra, dec = np.degrees(table[:, 0]), np.degrees(table[:, 1])
        with np.errstate(invalid="ignore", divide="ignore", over="ignore"):
            x, y, front = initial.world_to_pixel(ra, dec)
        margin = image.width * .02
        possible = front & np.isfinite(x) & np.isfinite(y)
        possible &= (x > -margin) & (x < image.width + margin) & (y > -margin) & (y < image.height + margin)
        sky = sky_vectors(ra[possible], dec[possible])
        if len(sky) < 32:
            return None
        width, height = proxy.width, proxy.height
        center = np.array([height / 2, width / 2])
        tree = cKDTree(observed)
        rotation = initial.rotation
        # Exactly change the normalization width of the same division model:
        # r*(1-k*(2r/W)^2) / ((1-k)*f). Simply reusing crop k at full width
        # would give a different camera and displace edge annotations.
        k = initial.distortion * (image.width / initial.radial_reference_width) ** 2
        if not -.12 < k < .12:
            return None
        focal = initial.focal_pixels * scale * (1 - initial.distortion) / (1 - k)
        original_focal = focal
        held_out = np.arange(len(sky)) % 4 == 0

        def project(rot: np.ndarray, focal_px: float, distortion: float) -> np.ndarray:
            camera = sky @ rot.T
            projected = np.column_stack((center[0] - focal_px * camera[:, 2] / camera[:, 0],
                                         center[1] - focal_px * camera[:, 1] / camera[:, 0]))
            return _distort_points(projected, tuple(center), distortion, width)

        def associate(projected: np.ndarray, radius: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
            distances, nearest = tree.query(projected)
            _, reverse = cKDTree(projected).query(observed)
            # Mutual nearest neighbours prevent counting an unresolved double
            # or duplicate catalogue association as two independent anchors.
            keep = (distances < radius) & (reverse[nearest] == np.arange(len(sky)))
            return distances, nearest, keep

        for iteration in range(12):
            if cancel_callback:
                cancel_callback()
            distances, nearest, keep = associate(project(rotation, focal, k), 8 if iteration == 0 else 4)
            fit_mask = keep & ~held_out
            if int(fit_mask.sum()) < 18:
                return None
            fit_observed, fit_sky = observed[nearest[fit_mask]], sky[fit_mask]
            starting_rotation, starting_focal = rotation, focal
            relative = fit_observed - center
            normalized_radius_sq = (2 * np.linalg.norm(relative, axis=1) / width) ** 2

            def residual(parameters: np.ndarray) -> np.ndarray:
                rot = Rotation.from_rotvec(parameters[:3]).as_matrix() @ starting_rotation
                trial_focal = starting_focal * np.exp(parameters[3])
                trial_k = parameters[4]
                camera = fit_sky @ rot.T
                predicted = np.column_stack((-trial_focal * camera[:, 2] / camera[:, 0],
                                             -trial_focal * camera[:, 1] / camera[:, 0]))
                undistorted = relative * (1 - trial_k * normalized_radius_sq)[:, None] / (1 - trial_k)
                return (predicted - undistorted).ravel()

            fit = least_squares(
                residual, [0, 0, 0, 0, k],
                bounds=([-.03, -.03, -.03, -.08, -.12], [.03, .03, .03, .08, .12]),
                loss="soft_l1", f_scale=.7, max_nfev=80,
            )
            if not fit.success or not np.isfinite(fit.x).all():
                return None
            rotation = Rotation.from_rotvec(fit.x[:3]).as_matrix() @ starting_rotation
            focal = starting_focal * math.exp(float(fit.x[3]))
            new_k = float(fit.x[4])
            settled = np.linalg.norm(fit.x[:4]) < 1e-7 and abs(new_k - k) < 1e-7
            k = new_k
            if settled:
                break
        if not .75 < focal / original_focal < 1.35:
            return None
        distances, nearest, keep = associate(project(rotation, focal, k), 2)
        validation = keep & held_out
        beyond_crop = np.max(np.abs(observed[nearest] - center), axis=1) > initial.radial_reference_width * scale / 2
        if int(keep.sum()) < 32 or int(validation.sum()) < 8 or int((validation & beyond_crop).sum()) < 8:
            return None
        span = np.ptp(observed[nearest[keep]], axis=0) / np.array([height, width])
        if np.min(span) < .65:
            return None
        image_rays = _image_vectors(observed[nearest], (height, width), math.degrees(2 * math.atan(width / (2 * focal))), k)
        camera = sky @ rotation.T
        angles = np.degrees(np.arctan2(np.linalg.norm(np.cross(image_rays, camera), axis=1),
                                      np.sum(image_rays * camera, axis=1))) * 3600
        angular_rmse = float(np.sqrt(np.mean(angles[keep] ** 2)))
        validation_rmse = float(np.sqrt(np.mean(angles[validation] ** 2)))
        if angular_rmse > 180 or validation_rmse > 180:
            return None
        focal_original = focal / scale
        horizontal_fov = math.degrees(2 * math.atan(image.width / (2 * focal_original)))
        # Vertical endpoints use the same full-width radial normalization.
        vertical_radius = image.height / 2 * (1 - k * (image.height / image.width) ** 2) / (1 - k)
        vertical_fov = math.degrees(2 * math.atan(vertical_radius / focal_original))
        return replace(
            initial,
            center_ra_deg=math.degrees(math.atan2(rotation[0, 1], rotation[0, 0])) % 360,
            center_dec_deg=math.degrees(math.asin(float(np.clip(rotation[0, 2], -1, 1)))),
            roll_deg=math.degrees(math.atan2(rotation[1, 2], rotation[2, 2])) % 360,
            horizontal_fov_deg=horizontal_fov, vertical_fov_deg=vertical_fov,
            distortion=k, focal_pixels=focal_original, radial_reference_width=image.width,
            principal_x=image.width / 2, principal_y=image.height / 2,
            rotation_matrix=rotation.tolist(), rmse_arcsec=angular_rmse,
            method="tetra3-wide-multiscale-verified",
            verification={
                "mode": "full-frame-holdout", "matchedStars": int(keep.sum()),
                "heldOutStars": int(validation.sum()), "heldOutOutsideCrop": int((validation & beyond_crop).sum()),
                "rmsePixels": float(np.sqrt(np.mean(distances[keep] ** 2))) / scale,
                "heldOutRmsePixels": float(np.sqrt(np.mean(distances[validation] ** 2))) / scale,
                "heldOutRmseArcsec": validation_rmse,
                "spanFractionX": float(span[1]), "spanFractionY": float(span[0]),
                "patternStars": initial.matches,
                "patternProbability": initial.false_positive_probability,
            },
        )
    except (ValueError, FloatingPointError, np.linalg.LinAlgError):
        return None
    finally:
        proxy.close()


def solve_plate(
    image: Image.Image,
    metadata: ImageMetadata,
    *,
    orientation_applied: bool = False,
    cancel_callback: Callable[[], None] | None = None,
) -> PlateSolution:
    """Blind-solve an image locally and return a projection usable for catalog overlays."""

    started = perf_counter()
    # Preserve high-bit-depth grayscale input for centroid extraction.  A
    # direct ``I;16 -> RGB`` conversion in Pillow clamps every value above 255
    # and turns genuine astronomical TIFFs into a featureless white frame.
    oriented = image if orientation_applied else ImageOps.exif_transpose(image)
    owns_oriented = oriented is not image
    normalized = oriented
    owns_normalized = False
    try:
        if oriented.mode not in {"I;16", "I;16B", "I;16L", "I", "F", "L", "RGB"}:
            # tetra3 accepts one or three channels; remove alpha/palette/CMYK while
            # preserving true 16-bit single-channel data above.
            normalized = oriented.convert("RGB")
            owns_normalized = True
        full_width, full_height = normalized.size
        full_fov_hint = estimated_horizontal_fov(metadata)
        total_budget_seconds = 45.0 if full_fov_hint is None else 90.0
        crop_specs: list[tuple[tuple[int, int, int, int], float | None]] = []
        if full_fov_hint:
            crop_specs.append(_central_crop_spec(normalized.size, full_fov_hint))
        else:
            crop_specs.extend(_blind_crop_specs(normalized.size))

        extraction_profiles = (
            {},
            # A lower global threshold is particularly effective for dense,
            # high-ISO wide fields with short star trails (the user's 28 mm frame).
            dict(sigma=2.4, filtsize=21, bg_sub_mode="global_median", sigma_mode="global_median_abs", binary_open=False, min_area=2, max_area=800, max_returned=220),
            # More conservative local-background profiles remain as fallbacks for
            # uneven sky glow and hot-pixel-heavy frames.
            dict(sigma=4.0, filtsize=31, bg_sub_mode="local_mean", sigma_mode="global_root_square", binary_open=False, min_area=2, max_area=500, max_returned=140),
            dict(sigma=3.0, filtsize=25, bg_sub_mode="local_mean", sigma_mode="global_median_abs", binary_open=False, min_area=2, max_area=600, max_returned=180),
        )
        if cancel_callback:
            cancel_callback()
        solver = _get_solver()
        attempted: list[str] = []
        budget_exhausted = False
        # Try one fast extraction at each scale before spending the remaining
        # budget on noisy-image fallbacks at an unsuitable full-frame scale.
        attempts_by_scale = (
            [(box, hint, range(len(extraction_profiles))) for box, hint in crop_specs]
            if full_fov_hint else
            [(box, hint, range(1)) for box, hint in crop_specs]
            + [(box, hint, range(1, len(extraction_profiles))) for box, hint in crop_specs]
        )
        for box, crop_fov_hint, profile_indices in attempts_by_scale:
            if cancel_callback:
                cancel_callback()
            full_frame = box == (0, 0, full_width, full_height)
            cropped = normalized if full_frame else normalized.crop(box)
            try:
                proxy, scale = _proxy(cropped)
                try:
                    for profile_zero_index in profile_indices:
                        profile_index = profile_zero_index + 1
                        profile = extraction_profiles[profile_zero_index]
                        if cancel_callback:
                            cancel_callback()
                        remaining_ms = round(
                            (total_budget_seconds - (perf_counter() - started)) * 1000
                        )
                        if remaining_ms < 1000:
                            budget_exhausted = True
                            break
                        attempted.append(f"crop={cropped.width}px/profile={profile_index}")
                        try:
                            with _solve_run_lock:
                                result = solver.solve_from_image(
                                    proxy,
                                    fov_estimate=crop_fov_hint,
                                    fov_max_error=4.0 if crop_fov_hint else None,
                                    pattern_checking_stars=9,
                                    match_radius=0.018,
                                    match_threshold=1e-4,
                                    solve_timeout=min(4_000 if full_fov_hint is None and profile_zero_index == 0 else 12_000, remaining_ms),
                                    distortion=(-0.12, 0.12),
                                    return_matches=True,
                                    **profile,
                                )
                        except (ValueError, FloatingPointError, np.linalg.LinAlgError):
                            continue
                        if cancel_callback:
                            cancel_callback()
                        if not result or result.get("RA") is None or int(result.get("Matches") or 0) < 8:
                            continue
                        # A plausible coordinate alone is not enough for annotation.  Keep
                        # searching when a noisy pattern has a weak false-positive score or
                        # residuals large enough to move labels by several pixels.
                        probability = float(result.get("Prob") or 1.0)
                        rmse_arcsec = float(result.get("RMSE") or math.inf)
                        if probability > 1e-8 or rmse_arcsec > 180:
                            continue

                        distortion = float(result.get("distortion") or 0.0)
                        matched_centroids = np.asarray(result["matched_centroids"], dtype=np.float64)
                        matched_stars = np.asarray(result["matched_stars"], dtype=np.float64)
                        image_vectors = _image_vectors(
                            matched_centroids, (proxy.height, proxy.width), float(result["FOV"]), distortion
                        )
                        catalog_vectors = sky_vectors(matched_stars[:, 0], matched_stars[:, 1])
                        rotation = _rotation_from_matches(image_vectors, catalog_vectors)

                        crop_width_original = box[2] - box[0]
                        focal_proxy = proxy.width / (2 * math.tan(math.radians(float(result["FOV"])) / 2))
                        focal_original = focal_proxy / scale
                        horizontal_fov = math.degrees(2 * math.atan(full_width / (2 * focal_original)))
                        vertical_fov = math.degrees(2 * math.atan(full_height / (2 * focal_original)))
                        camera_center = rotation @ sky_vectors([float(result["RA"])], [float(result["Dec"])])[0]
                        if not np.isfinite(camera_center).all():
                            continue
                        candidate = PlateSolution(
                            center_ra_deg=float(result["RA"]),
                            center_dec_deg=float(result["Dec"]),
                            roll_deg=float(result["Roll"]),
                            horizontal_fov_deg=horizontal_fov,
                            vertical_fov_deg=vertical_fov,
                            crop_fov_deg=float(result["FOV"]),
                            distortion=distortion,
                            rmse_arcsec=float(result.get("RMSE") or 0),
                            matches=int(result["Matches"]),
                            false_positive_probability=float(result.get("Prob") or 0),
                            solve_ms=(perf_counter() - started) * 1000,
                            image_width=full_width,
                            image_height=full_height,
                            focal_pixels=focal_original,
                            principal_x=full_width / 2,
                            principal_y=full_height / 2,
                            radial_reference_width=crop_width_original,
                            rotation_matrix=rotation.tolist(),
                            method=(
                                "tetra3-full-frame"
                                if full_frame
                                else "tetra3-central-crop"
                            ),
                        )
                        new_wide_probe = full_fov_hint is None and crop_width_original <= full_width * .34 and horizontal_fov >= 45
                        if new_wide_probe:
                            refined = _refine_wide_phone_solution(normalized, candidate, solver, cancel_callback)
                            if refined is None:
                                continue
                            candidate = refined
                        candidate.solve_ms = (perf_counter() - started) * 1000
                        return candidate
                finally:
                    proxy.close()
            finally:
                if not full_frame:
                    cropped.close()
            if budget_exhausted:
                break

        attempts = ", ".join(attempted)
        timeout_note = (
            f"，并已到达 {total_budget_seconds:g} 秒本地搜索上限"
            if budget_exhausted
            else ""
        )
        raise RuntimeError(
            "未能从星点几何中得到可靠天球解。请确认照片中有清晰星点；可尝试原始文件、较少压缩或更短曝光。"
            "当前内置盲解星图覆盖约 10°–30° 视场，广于 30° 的照片会自动中央分块；小于 10° 的窄视场照片暂不支持。"
            f"（已尝试 {attempts}{timeout_note}）"
        )
    finally:
        if owns_normalized:
            normalized.close()
        if owns_oriented:
            oriented.close()
