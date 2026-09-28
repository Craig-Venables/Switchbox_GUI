"""Intensity histogram overlay for clipping checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import cv2
import numpy as np

from analysis.preprocessing import normalize_frame_shape


@dataclass
class IntensityStats:
    max_value: int
    saturation_pct: float
    histogram: np.ndarray


def gray_from_frame(frame: np.ndarray) -> np.ndarray:
    gray = normalize_frame_shape(np.asarray(frame))
    if gray.dtype == np.uint8:
        return gray
    if gray.dtype == np.uint16:
        return (gray >> 8).astype(np.uint8)
    scaled = gray.astype(np.float32)
    mx = float(scaled.max())
    if mx <= 255.0:
        return np.clip(scaled, 0, 255).astype(np.uint8)
    return np.clip(scaled / mx * 255.0, 0, 255).astype(np.uint8)


def compute_intensity_stats(gray: np.ndarray, clip_threshold: int = 254) -> IntensityStats:
    g = gray_from_frame(gray) if gray.ndim >= 2 else gray
    flat = g.ravel()
    hist = np.bincount(flat, minlength=256)
    saturated = int(np.sum(flat >= clip_threshold))
    sat_pct = 100.0 * saturated / float(flat.size) if flat.size else 0.0
    return IntensityStats(max_value=int(flat.max()) if flat.size else 0, saturation_pct=sat_pct, histogram=hist)


def draw_intensity_histogram(
    frame: np.ndarray,
    gray: np.ndarray,
    *,
    width: int = 150,
    height: int = 72,
    margin: int = 8,
    corner: str = "top_right",
) -> np.ndarray:
    """Draw a small histogram in the corner of ``frame``."""
    out = frame
    stats = compute_intensity_stats(gray)
    fh, fw = out.shape[:2]

    if corner == "top_right":
        x0 = fw - width - margin
        y0 = margin
    else:
        x0 = margin
        y0 = margin

    x1 = x0 + width
    y1 = y0 + height
    panel = out[y0:y1, x0:x1].astype(np.float32)
    panel *= 0.35
    panel += 15
    out[y0:y1, x0:x1] = panel.astype(np.uint8)
    cv2.rectangle(out, (x0, y0), (x1, y1), (80, 80, 80), 1)

    plot_x0 = x0 + 4
    plot_y1 = y1 - 4
    plot_w = width - 8
    plot_h = height - 22
    max_count = int(stats.histogram.max()) or 1

    for i in range(256):
        bar_h = int(stats.histogram[i] * plot_h / max_count)
        if bar_h <= 0:
            continue
        bx = plot_x0 + int(i * plot_w / 256)
        color = (60, 60, 255) if i >= 254 else (190, 190, 190)
        cv2.line(out, (bx, plot_y1), (bx, plot_y1 - bar_h), color, 1)

    clip_x = plot_x0 + int(255 * plot_w / 256)
    cv2.line(out, (clip_x, y0 + 16), (clip_x, plot_y1), (40, 40, 200), 1)

    if stats.max_value >= 254 or stats.saturation_pct > 0.05:
        text_color = (80, 80, 255)
    elif stats.max_value >= 220:
        text_color = (80, 220, 255)
    else:
        text_color = (180, 255, 180)

    label = f"max {stats.max_value}  clip {stats.saturation_pct:.1f}%"
    cv2.putText(out, label, (x0 + 4, y0 + 13), cv2.FONT_HERSHEY_SIMPLEX, 0.38, text_color, 1, cv2.LINE_AA)
    cv2.putText(out, "intensity", (x0 + 4, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (140, 140, 140), 1, cv2.LINE_AA)
    return out
