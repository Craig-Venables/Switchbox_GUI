"""Digital zoom / crop for display and analysis centering."""

from __future__ import annotations

from typing import Tuple

import cv2
import numpy as np


def zoom_view_size(full_shape: Tuple[int, int], zoom: float) -> Tuple[int, int]:
    fh, fw = full_shape
    if zoom <= 1.0:
        return fw, fh
    view_w = max(16, int(round(fw / zoom)))
    view_h = max(16, int(round(fh / zoom)))
    return view_w, view_h


def crop_zoom(
    frame: np.ndarray,
    center_x: float,
    center_y: float,
    zoom: float,
) -> Tuple[np.ndarray, Tuple[int, int]]:
    """Crop a region around center and upscale to original size.

    ``zoom=1`` returns the full frame. ``zoom=4`` shows a 1/4-width window
    centered on ``center`` (magnified 4×).
    """
    if zoom <= 1.0:
        return frame.copy(), (0, 0)

    h, w = frame.shape[:2]
    view_w, view_h = zoom_view_size((h, w), zoom)

    x0 = int(round(center_x - view_w / 2.0))
    y0 = int(round(center_y - view_h / 2.0))
    x0 = max(0, min(x0, w - view_w))
    y0 = max(0, min(y0, h - view_h))

    crop = frame[y0 : y0 + view_h, x0 : x0 + view_w]
    if crop.size == 0:
        return frame.copy(), (0, 0)
    zoomed = cv2.resize(crop, (w, h), interpolation=cv2.INTER_NEAREST if zoom >= 8 else cv2.INTER_LINEAR)
    return zoomed, (x0, y0)


def map_full_to_display(
    full_x: float,
    full_y: float,
    zoom: float,
    crop_offset: Tuple[int, int],
    full_shape: Tuple[int, int],
) -> Tuple[float, float]:
    if zoom <= 1.0:
        return full_x, full_y
    fh, fw = full_shape
    x0, y0 = crop_offset
    view_w, view_h = zoom_view_size(full_shape, zoom)
    display_x = (full_x - x0) * fw / view_w
    display_y = (full_y - y0) * fh / view_h
    return display_x, display_y


def map_display_to_full(
    display_x: float,
    display_y: float,
    zoom: float,
    crop_offset: Tuple[int, int],
    full_shape: Tuple[int, int],
) -> Tuple[float, float]:
    """Map a click on the zoomed display back to full-frame coordinates."""
    if zoom <= 1.0:
        return display_x, display_y
    fh, fw = full_shape
    x0, y0 = crop_offset
    view_w, view_h = zoom_view_size(full_shape, zoom)
    full_x = x0 + display_x * view_w / fw
    full_y = y0 + display_y * view_h / fh
    return full_x, full_y


def full_length_to_display(length_px: float, zoom: float, full_shape: Tuple[int, int]) -> float:
    """Scale a distance in full-frame pixels to display pixels."""
    if zoom <= 1.0:
        return length_px
    fh, fw = full_shape
    view_w, _ = zoom_view_size(full_shape, zoom)
    return length_px * fw / view_w
