"""Unit tests for laser beam width analysis."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from analysis.calibration import CalibrationState
from analysis.gaussian_fit import E2_FACTOR, FWHM_FACTOR, analyze_beam


def _make_gaussian_blob(width: int, height: int, sigma_x: float, sigma_y: float, cx: float, cy: float) -> np.ndarray:
    yy, xx = np.mgrid[0:height, 0:width]
    img = np.exp(-0.5 * (((xx - cx) / sigma_x) ** 2 + ((yy - cy) / sigma_y) ** 2))
    return img.astype(np.float32)


class TestGaussianFit(unittest.TestCase):
    def test_e2_factor_is_1e2_diameter(self) -> None:
        self.assertAlmostEqual(E2_FACTOR, 4.0)
        self.assertAlmostEqual(FWHM_FACTOR, 2.0 * math.sqrt(2.0 * math.log(2.0)))

    def test_fwhm_and_e2_recovery(self) -> None:
        sigma_x, sigma_y = 12.0, 8.0
        w, h = 200, 200
        cx, cy = 100.0, 100.0
        roi = _make_gaussian_blob(w, h, sigma_x, sigma_y, cx, cy)
        fit = analyze_beam(roi, cx, cy, saturation_pct=0.0, snr=100.0)
        self.assertTrue(fit.ok, fit.message)
        self.assertAlmostEqual(fit.fwhm_x_px, FWHM_FACTOR * sigma_x, delta=1.5)
        self.assertAlmostEqual(fit.fwhm_y_px, FWHM_FACTOR * sigma_y, delta=1.5)
        self.assertAlmostEqual(fit.e2_x_px, E2_FACTOR * sigma_x, delta=1.5)
        self.assertAlmostEqual(fit.e2_y_px, E2_FACTOR * sigma_y, delta=1.5)

    def test_major_minor_axes(self) -> None:
        roi = _make_gaussian_blob(180, 180, 15.0, 6.0, 90.0, 90.0)
        fit = analyze_beam(roi, 90.0, 90.0, 0.0, 50.0)
        self.assertGreater(fit.major_fwhm_px, fit.minor_fwhm_px)


class TestCalibration(unittest.TestCase):
    def test_two_point_scale(self) -> None:
        cal = CalibrationState(
            reference_distance_um=100.0,
            point_a=(0.0, 0.0),
            point_b=(200.0, 0.0),
        )
        self.assertTrue(cal.apply_two_point())
        self.assertAlmostEqual(cal.um_per_pixel, 0.5)
        self.assertAlmostEqual(cal.pixel_distance(), 200.0)

    def test_invalid_points(self) -> None:
        cal = CalibrationState(reference_distance_um=100.0, point_a=(1.0, 1.0), point_b=(1.0, 1.0))
        self.assertFalse(cal.apply_two_point())


if __name__ == "__main__":
    unittest.main()
