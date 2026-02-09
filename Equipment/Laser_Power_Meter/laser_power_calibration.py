"""
Load laser power calibration (apparent vs actual) for use when configuring power on sample.

Calibration files are produced by measure_laser_power.py and saved as
laser_power_calibration_YYYYMMDD_HHMMSS.json in this folder.

Example:
  from Equipment.Laser_Power_Meter.laser_power_calibration import (
      load_calibration,
      get_setpoint_for_actual_mw,
      get_actual_mw,
  )
  cal = load_calibration()
  set_mw = get_setpoint_for_actual_mw(cal, 1.0)   # setpoint to get 1.0 mW actual
  actual = get_actual_mw(cal, 2.0)                 # actual power when set to 2.0 mW
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

OUTPUT_DIR = Path(__file__).resolve().parent
FILENAME_PREFIX = "laser_power_calibration"


def load_calibration(path: Path | str | None = None) -> dict[str, Any]:
    """
    Load calibration from JSON.

    Args:
        path: Path to .json file. If None, uses the most recent
              laser_power_calibration_*.json in this folder.

    Returns:
        Dict with "calibration" (list of {"set_mw", "measured_mw"}), "timestamp_iso", etc.

    Raises:
        FileNotFoundError: No file found or path missing.
    """
    if path is not None:
        p = Path(path)
        if not p.is_absolute():
            p = OUTPUT_DIR / p
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    # Latest by filename (timestamp sort)
    pattern = f"{FILENAME_PREFIX}_*.json"
    files = sorted(OUTPUT_DIR.glob(pattern), reverse=True)
    if not files:
        raise FileNotFoundError(
            f"No calibration file found in {OUTPUT_DIR}. Run measure_laser_power.py first."
        )
    with open(files[0], encoding="utf-8") as f:
        return json.load(f)


def _interp(x: float, xs: list[float], ys: list[float]) -> float:
    """Linear interpolation. Clamp to range if x outside xs."""
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    for i in range(len(xs) - 1):
        if xs[i] <= x <= xs[i + 1]:
            t = (x - xs[i]) / (xs[i + 1] - xs[i]) if xs[i + 1] != xs[i] else 0
            return ys[i] + t * (ys[i + 1] - ys[i])
    return ys[-1]


def get_actual_mw(cal: dict[str, Any], set_mw: float) -> float:
    """
    Return expected actual power (mW) at the sample for a given laser setpoint.

    Uses linear interpolation of the calibration curve (set_mw -> measured_mw).

    Args:
        cal: Loaded calibration dict (from load_calibration()).
        set_mw: Laser setpoint in mW (apparent power).

    Returns:
        Estimated actual power in mW.
    """
    points = cal.get("calibration", [])
    if not points:
        return set_mw
    xs = [p["set_mw"] for p in points]
    ys = [p["measured_mw"] for p in points]
    return _interp(set_mw, xs, ys)


def get_setpoint_for_actual_mw(cal: dict[str, Any], target_actual_mw: float) -> float:
    """
    Return laser setpoint (mW) needed to achieve a desired actual power at the sample.

    Uses linear interpolation of the inverse curve (measured_mw -> set_mw).

    Args:
        cal: Loaded calibration dict (from load_calibration()).
        target_actual_mw: Desired actual power in mW.

    Returns:
        Laser setpoint in mW to use (apparent power).
    """
    points = cal.get("calibration", [])
    if not points:
        return target_actual_mw
    # Inverse: measured -> set
    xs = [p["measured_mw"] for p in points]
    ys = [p["set_mw"] for p in points]
    return _interp(target_actual_mw, xs, ys)


def get_calibration_table(cal: dict[str, Any]) -> list[dict[str, float]]:
    """Return the calibration list as-is (list of {set_mw, measured_mw})."""
    return list(cal.get("calibration", []))


def format_true_power_display(true_mw: float) -> str:
    """
    Format calibrated power for UI: show both mW and µW so low powers (e.g. at 1 mW setpoint)
    don't appear as "0 mW" when there is still light.
    """
    uw = true_mw * 1000
    if true_mw >= 0.01:
        return f"{true_mw:.3f} mW ({uw:.0f} µW)"
    if true_mw >= 0.001:
        return f"{true_mw:.3f} mW ({uw:.1f} µW)"
    return f"{true_mw:.4f} mW ({uw:.1f} µW)"
