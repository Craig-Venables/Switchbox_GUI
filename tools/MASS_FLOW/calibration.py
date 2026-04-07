"""Calibration helpers for MASS_FLOW tools."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np


def fit_model(device_readings: Sequence[float], reference_readings: Sequence[float], order: int) -> Dict:
    if len(device_readings) != len(reference_readings):
        raise ValueError("device_readings and reference_readings must have same length.")
    if len(device_readings) < 2:
        raise ValueError("Need at least two points to fit calibration.")
    if order not in (1, 2):
        raise ValueError("Supported orders are 1 (linear) or 2 (quadratic).")
    if order == 2 and len(device_readings) < 3:
        raise ValueError("Quadratic fit requires at least three points.")

    x = np.asarray(device_readings, dtype=float)
    y = np.asarray(reference_readings, dtype=float)
    coeffs = np.polyfit(x, y, order)
    y_pred = np.polyval(coeffs, x)
    residual = y - y_pred
    rmse = float(np.sqrt(np.mean(residual**2)))
    max_abs_error = float(np.max(np.abs(residual)))

    return {
        "model": "polynomial",
        "order": order,
        "coefficients": [float(c) for c in coeffs.tolist()],
        "rmse_sccm": rmse,
        "max_abs_error_sccm": max_abs_error,
    }


def apply_correction(value: float, calibration: Dict) -> float:
    if not calibration:
        return float(value)
    fit = calibration.get("fit", {})
    coeffs = fit.get("coefficients", [])
    if not coeffs:
        return float(value)
    return float(np.polyval(np.asarray(coeffs, dtype=float), float(value)))


def build_calibration_record(
    gas: str,
    full_scale_sccm: float,
    points: Iterable[Tuple[float, float]],
    fit: Dict,
    notes: str = "",
) -> Dict:
    data_points: List[Dict] = []
    for dev, ref in points:
        data_points.append({"device_sccm": float(dev), "reference_sccm": float(ref)})

    return {
        "created_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "gas": gas,
        "full_scale_sccm": float(full_scale_sccm),
        "fit": fit,
        "points": data_points,
        "notes": notes.strip(),
    }


def save_calibration(calibration_path: Path, record: Dict) -> None:
    calibration_path.parent.mkdir(parents=True, exist_ok=True)
    with calibration_path.open("w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)


def load_calibration(calibration_path: Path) -> Dict:
    with calibration_path.open("r", encoding="utf-8") as f:
        return json.load(f)
