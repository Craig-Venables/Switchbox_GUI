"""Gaussian beam profile fitting and width metrics."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
from scipy.optimize import curve_fit

FWHM_FACTOR = 2.0 * math.sqrt(2.0 * math.log(2.0))  # ~2.355
# 1/e² diameter: I = I0 exp(-2 r²/w²) matches exp(-x²/(2σ²)) at w = 2σ, so diameter = 4σ.
# (2√2 σ is the 1/e diameter, not 1/e².)
E2_FACTOR = 4.0


@dataclass
class BeamFitResult:
    centroid_x: float
    centroid_y: float
    sigma_x: float
    sigma_y: float
    amplitude: float
    offset: float
    fwhm_x_px: float
    fwhm_y_px: float
    e2_x_px: float
    e2_y_px: float
    major_axis_px: float
    minor_axis_px: float
    major_fwhm_px: float
    minor_fwhm_px: float
    major_e2_px: float
    minor_e2_px: float
    r2_x: float
    r2_y: float
    r2_2d: float
    saturation_pct: float
    snr: float
    ok: bool
    message: str = ""

    def width_um(self, name: str, um_per_pixel: Optional[float]) -> Optional[float]:
        if um_per_pixel is None:
            return None
        value_px = getattr(self, name, None)
        if value_px is None:
            return None
        return float(value_px) * um_per_pixel


def _gaussian_1d(x: np.ndarray, amplitude: float, mu: float, sigma: float, offset: float) -> np.ndarray:
    sigma = max(abs(sigma), 1e-6)
    return amplitude * np.exp(-0.5 * ((x - mu) / sigma) ** 2) + offset


def _r2_score(y: np.ndarray, y_hat: np.ndarray) -> float:
    ss_res = float(np.sum((y - y_hat) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    if ss_tot <= 0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - ss_res / ss_tot))


def _fit_1d_profile(profile: np.ndarray) -> Tuple[float, float, float, float, float]:
    """Return amplitude, mu, sigma, offset, r2."""
    n = profile.size
    x = np.arange(n, dtype=float)
    y = profile.astype(float)
    peak = float(np.max(y))
    floor = float(np.min(y))
    amplitude = max(peak - floor, 1e-6)
    mu = float(np.argmax(y))
    sigma = max(n / 6.0, 1.0)
    offset = floor
    p0 = (amplitude, mu, sigma, offset)
    bounds = ([0.0, 0.0, 0.5, -np.inf], [np.inf, n - 1.0, n, np.inf])
    popt, _ = curve_fit(_gaussian_1d, x, y, p0=p0, bounds=bounds, maxfev=8000)
    amplitude, mu, sigma, offset = [float(v) for v in popt]
    y_hat = _gaussian_1d(x, amplitude, mu, sigma, offset)
    return amplitude, mu, max(sigma, 0.5), offset, _r2_score(y, y_hat)


def _axis_widths(sigma_x: float, sigma_y: float) -> Tuple[float, float, float, float, float, float]:
    fwhm_x = FWHM_FACTOR * sigma_x
    fwhm_y = FWHM_FACTOR * sigma_y
    e2_x = E2_FACTOR * sigma_x
    e2_y = E2_FACTOR * sigma_y
    major_sigma = max(sigma_x, sigma_y)
    minor_sigma = min(sigma_x, sigma_y)
    major_fwhm = FWHM_FACTOR * major_sigma
    minor_fwhm = FWHM_FACTOR * minor_sigma
    major_e2 = E2_FACTOR * major_sigma
    minor_e2 = E2_FACTOR * minor_sigma
    return fwhm_x, fwhm_y, e2_x, e2_y, major_fwhm, minor_fwhm, major_e2, minor_e2


def _fit_2d_r2(image: np.ndarray, amplitude: float, cx: float, cy: float, sigma_x: float, sigma_y: float, offset: float) -> float:
    yy, xx = np.mgrid[0 : image.shape[0], 0 : image.shape[1]]
    model = (
        amplitude * np.exp(-0.5 * (((xx - cx) / max(sigma_x, 1e-6)) ** 2 + ((yy - cy) / max(sigma_y, 1e-6)) ** 2))
        + offset
    )
    return _r2_score(image.ravel(), model.ravel())


def analyze_beam(
    image: np.ndarray,
    centroid_x: float,
    centroid_y: float,
    saturation_pct: float,
    snr: float,
) -> BeamFitResult:
    """Fit horizontal and vertical Gaussian profiles through the centroid."""
    if image.size == 0:
        return BeamFitResult(
            centroid_x=centroid_x,
            centroid_y=centroid_y,
            sigma_x=0.0,
            sigma_y=0.0,
            amplitude=0.0,
            offset=0.0,
            fwhm_x_px=0.0,
            fwhm_y_px=0.0,
            e2_x_px=0.0,
            e2_y_px=0.0,
            major_axis_px=0.0,
            minor_axis_px=0.0,
            major_fwhm_px=0.0,
            minor_fwhm_px=0.0,
            major_e2_px=0.0,
            minor_e2_px=0.0,
            r2_x=0.0,
            r2_y=0.0,
            r2_2d=0.0,
            saturation_pct=saturation_pct,
            snr=snr,
            ok=False,
            message="Empty ROI",
        )

    h, w = image.shape
    cx = int(round(np.clip(centroid_x, 0, w - 1)))
    cy = int(round(np.clip(centroid_y, 0, h - 1)))
    h_profile = image[cy, :]
    v_profile = image[:, cx]

    try:
        amp_x, mu_x, sigma_x, off_x, r2_x = _fit_1d_profile(h_profile)
        amp_y, mu_y, sigma_y, off_y, r2_y = _fit_1d_profile(v_profile)
    except Exception as exc:
        return BeamFitResult(
            centroid_x=centroid_x,
            centroid_y=centroid_y,
            sigma_x=0.0,
            sigma_y=0.0,
            amplitude=0.0,
            offset=0.0,
            fwhm_x_px=0.0,
            fwhm_y_px=0.0,
            e2_x_px=0.0,
            e2_y_px=0.0,
            major_axis_px=0.0,
            minor_axis_px=0.0,
            major_fwhm_px=0.0,
            minor_fwhm_px=0.0,
            major_e2_px=0.0,
            minor_e2_px=0.0,
            r2_x=0.0,
            r2_y=0.0,
            r2_2d=0.0,
            saturation_pct=saturation_pct,
            snr=snr,
            ok=False,
            message=f"Fit failed: {exc}",
        )

    fwhm_x, fwhm_y, e2_x, e2_y, major_fwhm, minor_fwhm, major_e2, minor_e2 = _axis_widths(sigma_x, sigma_y)
    amplitude = 0.5 * (amp_x + amp_y)
    offset = 0.5 * (off_x + off_y)
    fit_cx = float(mu_x)
    fit_cy = float(mu_y)
    r2_2d = _fit_2d_r2(image, amplitude, fit_cx, fit_cy, sigma_x, sigma_y, offset)

    ok = min(r2_x, r2_y) >= 0.85 and snr >= 5.0 and saturation_pct < 5.0
    message = "OK"
    if saturation_pct >= 5.0:
        message = "High saturation — reduce laser power or exposure"
        ok = False
    elif min(r2_x, r2_y) < 0.85:
        message = "Poor Gaussian fit — check focus or background"
        ok = False
    elif snr < 5.0:
        message = "Low SNR — increase signal or reduce background"
        ok = False

    return BeamFitResult(
        centroid_x=fit_cx,
        centroid_y=fit_cy,
        sigma_x=sigma_x,
        sigma_y=sigma_y,
        amplitude=amplitude,
        offset=offset,
        fwhm_x_px=fwhm_x,
        fwhm_y_px=fwhm_y,
        e2_x_px=e2_x,
        e2_y_px=e2_y,
        major_axis_px=FWHM_FACTOR * max(sigma_x, sigma_y),
        minor_axis_px=FWHM_FACTOR * min(sigma_x, sigma_y),
        major_fwhm_px=major_fwhm,
        minor_fwhm_px=minor_fwhm,
        major_e2_px=major_e2,
        minor_e2_px=minor_e2,
        r2_x=r2_x,
        r2_y=r2_y,
        r2_2d=r2_2d,
        saturation_pct=saturation_pct,
        snr=snr,
        ok=ok,
        message=message,
    )
