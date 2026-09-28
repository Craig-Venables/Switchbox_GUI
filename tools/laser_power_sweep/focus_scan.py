"""Load FWHM / 1/e² vs Z from laser_beam_width focus-scan folders."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


def parse_z_mm(folder_name: str) -> Optional[float]:
    match = re.search(r"([\d.]+)", folder_name.replace(",", "."))
    return float(match.group(1)) if match else None


@dataclass
class FocusScanPoint:
    z_mm: float
    folder: str
    mean_fwhm_um: float
    e2_mean_um: float
    fwhm_x_um: float
    fwhm_y_um: float
    e2_x_um: float
    e2_y_um: float
    major_fwhm_um: float
    minor_fwhm_um: float
    ok: bool
    rating: str
    um_per_pixel: Optional[float]

    @property
    def label(self) -> str:
        flag = "" if self.ok else " (weak fit)"
        return f"{self.z_mm:.2f} mm — FWHM {self.mean_fwhm_um:.1f} µm, 1/e² {self.e2_mean_um:.1f} µm{flag}"


def _rate_fit(fit: dict) -> str:
    if not fit:
        return "No data"
    r2_min = min(float(fit.get("r2_x", 0)), float(fit.get("r2_y", 0)))
    r2_2d = float(fit.get("r2_2d", 0))
    ok = bool(fit.get("ok", False))
    sat = float(fit.get("saturation_pct", 0))
    snr = float(fit.get("snr", 0))
    if ok and r2_min >= 0.95 and r2_2d >= 0.90:
        return "Excellent"
    if ok:
        return "Good"
    if r2_min >= 0.85 and sat < 5.0 and snr >= 5.0:
        return "Marginal"
    if r2_min >= 0.75:
        return "Weak"
    return "Poor"


def _um(fit: dict, cal: dict, name: str) -> Optional[float]:
    um_per_px = cal.get("um_per_pixel")
    if um_per_px is None:
        return None
    val = fit.get(name)
    return float(val) * float(um_per_px) if val is not None else None


def load_focus_scan(root: Path) -> List[FocusScanPoint]:
    """Load all Z positions from a focus-scan directory (subfolders per Z with beam_width_*.json)."""
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Not a directory: {root}")

    points: List[FocusScanPoint] = []
    for folder in sorted(root.iterdir()):
        if not folder.is_dir() or folder.name.lower() == "analysis":
            continue
        z_mm = parse_z_mm(folder.name)
        if z_mm is None:
            continue
        json_files = sorted(folder.glob("beam_width_*.json"))
        if not json_files:
            continue
        with open(json_files[-1], encoding="utf-8") as f:
            meta = json.load(f)
        fit = meta.get("fit") or {}
        cal = meta.get("calibration") or {}

        fwhm_x = _um(fit, cal, "fwhm_x_px")
        fwhm_y = _um(fit, cal, "fwhm_y_px")
        e2_x = _um(fit, cal, "e2_x_px")
        e2_y = _um(fit, cal, "e2_y_px")
        major_fwhm = _um(fit, cal, "major_fwhm_px")
        minor_fwhm = _um(fit, cal, "minor_fwhm_px")

        fwhm_vals = [v for v in (fwhm_x, fwhm_y) if v is not None]
        e2_vals = [v for v in (e2_x, e2_y) if v is not None]
        if not fwhm_vals or not e2_vals:
            continue

        points.append(
            FocusScanPoint(
                z_mm=z_mm,
                folder=folder.name,
                mean_fwhm_um=sum(fwhm_vals) / len(fwhm_vals),
                e2_mean_um=sum(e2_vals) / len(e2_vals),
                fwhm_x_um=float(fwhm_x or 0),
                fwhm_y_um=float(fwhm_y or 0),
                e2_x_um=float(e2_x or 0),
                e2_y_um=float(e2_y or 0),
                major_fwhm_um=float(major_fwhm or max(fwhm_vals)),
                minor_fwhm_um=float(minor_fwhm or min(fwhm_vals)),
                ok=bool(fit.get("ok", False)),
                rating=_rate_fit(fit),
                um_per_pixel=cal.get("um_per_pixel"),
            )
        )

    if not points:
        raise FileNotFoundError(f"No beam_width_*.json found under {root}")
    points.sort(key=lambda p: p.z_mm)
    return points


def point_at_z(points: List[FocusScanPoint], z_mm: float, *, tol: float = 0.01) -> Optional[FocusScanPoint]:
    for p in points:
        if abs(p.z_mm - z_mm) <= tol:
            return p
    return None
