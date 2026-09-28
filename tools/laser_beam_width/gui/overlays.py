"""Draw measurement overlays on camera frames."""

from __future__ import annotations

from typing import Optional, Tuple

import cv2
import numpy as np

from analysis.gaussian_fit import BeamFitResult
from analysis.view_zoom import full_length_to_display, map_full_to_display


def _pt(
    full_x: float,
    full_y: float,
    zoom: float,
    crop_offset: Tuple[int, int],
    full_shape: Tuple[int, int],
) -> Tuple[int, int]:
    dx, dy = map_full_to_display(full_x, full_y, zoom, crop_offset, full_shape)
    return int(round(dx)), int(round(dy))


def draw_overlays(
    frame: np.ndarray,
    fit: Optional[BeamFitResult],
    roi_offset: Tuple[int, int],
    roi_half_size: int,
    cal_point_a: Optional[Tuple[float, float]] = None,
    cal_point_b: Optional[Tuple[float, float]] = None,
    cal_pending: Optional[Tuple[float, float]] = None,
    spot_center: Optional[Tuple[float, float]] = None,
    zoom: float = 1.0,
    crop_offset: Tuple[int, int] = (0, 0),
    full_shape: Optional[Tuple[int, int]] = None,
) -> np.ndarray:
    out = frame.copy()
    shape = full_shape if full_shape is not None else frame.shape[:2]
    roi_x0, roi_y0 = roi_offset

    marker_size = 8
    line_th = 1
    scale = full_length_to_display(1.0, zoom, shape)

    if fit is not None and (fit.ok or fit.sigma_x > 0):
        full_cx = roi_x0 + fit.centroid_x
        full_cy = roi_y0 + fit.centroid_y
        cx, cy = _pt(full_cx, full_cy, zoom, crop_offset, shape)

        axes_x = max(1, int(round(0.5 * fit.fwhm_x_px * scale)))
        axes_y = max(1, int(round(0.5 * fit.fwhm_y_px * scale)))
        cv2.ellipse(out, (cx, cy), (axes_x, axes_y), 0, 0, 360, (0, 180, 0), line_th)
        cv2.drawMarker(
            out, (cx, cy), (0, 200, 200), markerType=cv2.MARKER_CROSS, markerSize=marker_size, thickness=line_th
        )

        rx0, ry0 = _pt(roi_x0, roi_y0, zoom, crop_offset, shape)
        rx1, ry1 = _pt(roi_x0 + 2 * roi_half_size, roi_y0 + 2 * roi_half_size, zoom, crop_offset, shape)
        cv2.rectangle(out, (min(rx0, rx1), min(ry0, ry1)), (max(rx0, rx1), max(ry0, ry1)), (180, 120, 0), line_th)

        if fit.ok:
            label = f"FWHM {fit.fwhm_x_px:.1f} x {fit.fwhm_y_px:.1f} px"
        else:
            label = fit.message
        cv2.putText(out, label, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1, cv2.LINE_AA)

    if cal_point_a is not None and cal_point_b is not None:
        p1 = _pt(cal_point_a[0], cal_point_a[1], zoom, crop_offset, shape)
        p2 = _pt(cal_point_b[0], cal_point_b[1], zoom, crop_offset, shape)
        cv2.line(out, p1, p2, (0, 180, 0), line_th)
        cv2.circle(out, p1, 3, (0, 180, 0), -1)
        cv2.circle(out, p2, 3, (0, 180, 0), -1)

    if cal_pending is not None:
        p = _pt(cal_pending[0], cal_pending[1], zoom, crop_offset, shape)
        cv2.circle(out, p, 4, (0, 160, 200), line_th)

    if spot_center is not None:
        sx, sy = _pt(spot_center[0], spot_center[1], zoom, crop_offset, shape)
        cv2.drawMarker(
            out, (sx, sy), (200, 0, 200), markerType=cv2.MARKER_CROSS, markerSize=marker_size, thickness=line_th
        )

    if zoom > 1.0:
        cv2.putText(
            out,
            f"zoom {zoom:.0f}x",
            (8, out.shape[0] - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (160, 160, 160),
            1,
            cv2.LINE_AA,
        )
    else:
        cv2.putText(
            out,
            "click spot to zoom in",
            (8, out.shape[0] - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (140, 140, 140),
            1,
            cv2.LINE_AA,
        )

    return out
