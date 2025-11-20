"""Unit tests for the single-bias helper.

These tests validate the bias-point extraction logic used by
`run_single_bias_read.py`, ensuring every new module includes automated
verification per user preference.
"""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SINGLE_BIAS_DIR = PROJECT_ROOT / "Equipment" / "SMU_AND_PMU" / "4200A" / "C_Code_with_python_scripts" / "Single_Point_Bias"

if str(SINGLE_BIAS_DIR) not in sys.path:
    sys.path.append(str(SINGLE_BIAS_DIR))

from run_single_bias_read import extract_point_measurement  # type: ignore  # pylint: disable=import-error


def test_extract_point_measurement_finds_bias_point() -> None:
    voltage = [0.0, 0.2, -0.2, 0.0]
    current = [0.0, 1e-6, -1e-6, 0.0]

    forced, measured = extract_point_measurement(voltage, current, target_voltage=0.2, tolerance=1e-6)

    assert forced == voltage[1]
    assert measured == current[1]


def test_extract_point_measurement_raises_when_missing() -> None:
    voltage = [0.0, 0.19, -0.21, 0.0]
    current = [0.0, 9e-7, -1.1e-6, 0.0]

    try:
        extract_point_measurement(voltage, current, target_voltage=0.2, tolerance=1e-4)
        raise AssertionError("ValueError was not raised for missing point")
    except ValueError as exc:
        assert "No measurement matched" in str(exc)


