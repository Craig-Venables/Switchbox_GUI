"""Frame preprocessing for beam width measurement."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np


@dataclass
class PreprocessResult:
    gray: np.ndarray
    processed: np.ndarray
    roi: np.ndarray
    roi_offset: Tuple[int, int]
    centroid_x: float
    centroid_y: float
    saturation_pct: float
    snr: float


def normalize_frame_shape(frame: np.ndarray) -> np.ndarray:
    """Convert camera arrays to HWC or 2D grayscale."""
    arr = np.asarray(frame)
    if arr.ndim == 3:
        # CHW (e.g. uc480 mono8 returns shape 1×H×W)
        if arr.shape[0] in (1, 3, 4) and arr.shape[0] < min(arr.shape[1], arr.shape[2]):
            if arr.shape[0] == 1:
                return arr[0]
            return np.transpose(arr, (1, 2, 0))
        if arr.shape[2] == 1:
            return arr[:, :, 0]
    return arr


def to_grayscale(frame: np.ndarray) -> np.ndarray:
    frame = normalize_frame_shape(frame)
    if frame.ndim == 2:
        return frame.astype(np.float32)
    if frame.shape[2] == 4:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
    if frame.shape[2] == 1:
        return frame[:, :, 0].astype(np.float32)
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)


def subtract_background(gray: np.ndarray, background: Optional[np.ndarray]) -> np.ndarray:
    if background is None:
        return gray.copy()
    bg = background.astype(np.float32)
    if bg.shape != gray.shape:
        bg = cv2.resize(bg, (gray.shape[1], gray.shape[0]), interpolation=cv2.INTER_LINEAR)
    diff = gray - bg
    diff[diff < 0] = 0.0
    return diff


def intensity_centroid(image: np.ndarray) -> Tuple[float, float]:
    total = float(np.sum(image))
    if total <= 0:
        h, w = image.shape
        return w / 2.0, h / 2.0
    yy, xx = np.mgrid[0 : image.shape[0], 0 : image.shape[1]]
    cx = float(np.sum(xx * image) / total)
    cy = float(np.sum(yy * image) / total)
    return cx, cy


def saturation_fraction(gray: np.ndarray, bit_depth: float = 255.0, threshold_frac: float = 0.98) -> float:
    saturated = np.sum(gray >= threshold_frac * bit_depth)
    return 100.0 * float(saturated) / float(gray.size)


def estimate_snr(image: np.ndarray, centroid_x: float, centroid_y: float, spot_radius_px: float = 20.0) -> float:
    h, w = image.shape
    cx = int(round(np.clip(centroid_x, 0, w - 1)))
    cy = int(round(np.clip(centroid_y, 0, h - 1)))
    y0 = max(0, cy - int(spot_radius_px))
    y1 = min(h, cy + int(spot_radius_px) + 1)
    x0 = max(0, cx - int(spot_radius_px))
    x1 = min(w, cx + int(spot_radius_px) + 1)
    signal_region = image[y0:y1, x0:x1]
    signal = float(np.max(signal_region)) if signal_region.size else 0.0

    margin = int(max(spot_radius_px * 2, 30))
    outer_mask = np.ones_like(image, dtype=bool)
    oy0 = max(0, cy - margin)
    oy1 = min(h, cy + margin + 1)
    ox0 = max(0, cx - margin)
    ox1 = min(w, cx + margin + 1)
    outer_mask[oy0:oy1, ox0:ox1] = False
    noise_vals = image[outer_mask]
    if noise_vals.size == 0:
        noise = float(np.std(image))
    else:
        noise = float(np.std(noise_vals))
    if noise <= 1e-6:
        return signal
    return signal / noise


def extract_roi(
    image: np.ndarray, centroid_x: float, centroid_y: float, half_size: int
) -> Tuple[np.ndarray, Tuple[int, int], float, float]:
    h, w = image.shape
    cx = int(round(centroid_x))
    cy = int(round(centroid_y))
    x0 = max(0, cx - half_size)
    x1 = min(w, cx + half_size + 1)
    y0 = max(0, cy - half_size)
    y1 = min(h, cy + half_size + 1)
    roi = image[y0:y1, x0:x1].copy()
    local_cx = centroid_x - x0
    local_cy = centroid_y - y0
    return roi, (x0, y0), local_cx, local_cy


def preprocess_frame(
    frame: np.ndarray,
    background: Optional[np.ndarray] = None,
    roi_half_size_px: int = 150,
    center_x: Optional[float] = None,
    center_y: Optional[float] = None,
) -> PreprocessResult:
    gray = to_grayscale(frame)
    processed = subtract_background(gray, background)
    saturation_pct = saturation_fraction(gray)
    if center_x is not None and center_y is not None:
        cx, cy = float(center_x), float(center_y)
    else:
        cx, cy = intensity_centroid(processed)
    snr = estimate_snr(processed, cx, cy, spot_radius_px=max(5.0, roi_half_size_px / 3.0))
    roi, (x0, y0), local_cx, local_cy = extract_roi(processed, cx, cy, roi_half_size_px)
    return PreprocessResult(
        gray=gray,
        processed=processed,
        roi=roi,
        roi_offset=(x0, y0),
        centroid_x=local_cx,
        centroid_y=local_cy,
        saturation_pct=saturation_pct,
        snr=snr,
    )
