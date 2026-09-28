"""Unit tests for laser power sweep helpers."""

from __future__ import annotations

import math
import sys
import tempfile
import unittest
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from sweep import (
    SweepPoint,
    SweepResult,
    compute_intensities,
    filter_setpoints,
    generate_ramp,
    parse_setpoint_list,
    save_sweep_results,
    spot_area_from_diameter_um,
)


class TestSetpoints(unittest.TestCase):
    def test_parse_list(self) -> None:
        self.assertEqual(parse_setpoint_list("1, 2, 5"), [1.0, 2.0, 5.0])

    def test_generate_ramp(self) -> None:
        self.assertEqual(generate_ramp(1.0, 1.0, 3.0), [1.0, 2.0, 3.0])

    def test_filter_max(self) -> None:
        ok, bad = filter_setpoints([10, 55, 40], maximum=50)
        self.assertEqual(ok, [10.0, 40.0])
        self.assertEqual(bad, [55.0])


class TestIntensity(unittest.TestCase):
    def test_spot_area(self) -> None:
        area = spot_area_from_diameter_um(20.0)
        self.assertAlmostEqual(area, math.pi * 10**2)

    def test_gaussian_peak_from_e2(self) -> None:
        i_fwhm, i_e2 = compute_intensities(1.0, fwhm_um=20.0, e2_um=26.0)
        assert i_fwhm is not None and i_e2 is not None
        w = 13.0
        self.assertAlmostEqual(i_e2, 2.0 / (math.pi * w**2))
        self.assertAlmostEqual(i_fwhm, 0.5 / (math.pi * 10.0**2))
        self.assertGreater(i_e2, i_fwhm)


class TestSave(unittest.TestCase):
    def test_save_digital(self) -> None:
        pt = SweepPoint(
            setpoint=1.0,
            setpoint_unit="mW",
            measured_mw=0.9,
            error_value=-0.1,
            error_pct=-10.0,
            status="OK",
            timestamp_iso="2026-01-01T00:00:00+00:00",
            intensity_from_fwhm_mw_per_um2=0.01,
            intensity_from_e2_mw_per_um2=0.005,
        )
        result = SweepResult(
            control_mode="digital_mw",
            points=[pt],
            timestamp_iso="2026-01-01T00:00:00+00:00",
            timestamp_filename="20260101_000000",
        )
        with tempfile.TemporaryDirectory() as tmp:
            csv_p, json_p, png_p = save_sweep_results(
                result, Path(tmp), fwhm_um=20.0, e2_um=26.0
            )
            self.assertTrue(csv_p.exists())
            self.assertTrue(json_p.exists())
            self.assertTrue(png_p.exists())
            self.assertIn("intensity_from_e2", csv_p.read_text(encoding="utf-8"))

    def test_save_ttl(self) -> None:
        pt = SweepPoint(
            setpoint=50.0,
            setpoint_unit="current_pct",
            measured_mw=5.0,
            error_value=0.0,
            error_pct=0.0,
            status="OK",
            timestamp_iso="2026-01-01T00:00:00+00:00",
        )
        result = SweepResult(
            control_mode="ttl_current_pct",
            points=[pt],
            timestamp_iso="2026-01-01T00:00:00+00:00",
            timestamp_filename="20260101_000001",
        )
        with tempfile.TemporaryDirectory() as tmp:
            csv_p, _, _ = save_sweep_results(result, Path(tmp))
            text = csv_p.read_text(encoding="utf-8")
            self.assertIn("set_current_pct", text)


if __name__ == "__main__":
    unittest.main()
