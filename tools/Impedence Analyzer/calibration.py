"""
Open/short calibration for impedance data.

Removes parallel (open) and series (short) parasitics using complex
admittance/impedance correction with frequency interpolation.
"""

import re
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import pandas as pd

# Standard column names (match impedance_plots / smart_loader)
FREQ = "Frequency (Hz)"
MAG = "Impedance Magnitude (Ohms)"
PHASE = "Impedance Phase Degrees (')"
CAP = "Capacitance Magnitude (F)"

OPEN_KEYWORDS = re.compile(r"open|open_circuit|open_loop|oc\b", re.I)
SHORT_KEYWORDS = re.compile(r"short|short_circuit|short_loop|sc\b|closed|closed_circuit", re.I)


def detect_open_short_paths(folder: Path) -> Tuple[Optional[Path], Optional[Path]]:
    """
    Scan folder for CSV files whose stem suggests open/short (or closed) calibration.
    Returns (open_csv_path or None, short_csv_path or None).
    Also detects "closed" as an alternative to "short".
    """
    folder = Path(folder)
    open_path = None
    short_path = None
    for p in sorted(folder.glob("*.csv")):
        if p.suffix.lower() != ".csv":
            continue
        stem = p.stem
        if OPEN_KEYWORDS.search(stem) and open_path is None:
            open_path = p
        if SHORT_KEYWORDS.search(stem) and short_path is None:
            short_path = p
    return open_path, short_path


def _col(df: pd.DataFrame, name: str) -> Optional[str]:
    for c in df.columns:
        if str(c).strip() == name:
            return c
    return None


def _z_from_mag_phase(
    freq: np.ndarray,
    mag: np.ndarray,
    phase_deg: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """Build complex Z = Z_real + j*Z_imag from magnitude and phase (radians)."""
    phase_rad = np.deg2rad(phase_deg)
    z_real = mag * np.cos(phase_rad)
    z_imag = mag * np.sin(phase_rad)
    return z_real, z_imag


def _interp_complex(
    f_target: np.ndarray,
    f_source: np.ndarray,
    z_real: np.ndarray,
    z_imag: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """Interpolate complex Z from source frequencies to target. Extrapolation yields NaN."""
    valid = np.isfinite(f_source) & np.isfinite(z_real) & np.isfinite(z_imag)
    if not np.any(valid):
        return np.full_like(f_target, np.nan), np.full_like(f_target, np.nan)
    f_s = np.asarray(f_source)[valid]
    re_s = np.asarray(z_real)[valid]
    im_s = np.asarray(z_imag)[valid]
    if np.any(np.diff(f_s) <= 0):
        # Sort by frequency
        idx = np.argsort(f_s)
        f_s = f_s[idx]
        re_s = re_s[idx]
        im_s = im_s[idx]
    re_out = np.interp(f_target, f_s, re_s)
    im_out = np.interp(f_target, f_s, im_s)
    # Mask outside source range
    out_of_range = (f_target < f_s.min()) | (f_target > f_s.max())
    re_out[out_of_range] = np.nan
    im_out[out_of_range] = np.nan
    return re_out, im_out


def apply_open_short_correction(
    device_df: pd.DataFrame,
    open_df: pd.DataFrame,
    short_df: pd.DataFrame,
    freq_col: str = FREQ,
    mag_col: str = MAG,
    phase_col: str = PHASE,
    cap_col: str = CAP,
) -> pd.DataFrame:
    """
    Apply open/short compensation to device data.

    Steps:
    1. Build Z = Z_real + j*Z_imag for open, short, device.
    2. Y = 1/Z for each.
    3. Y_corr1 = Y_device - Y_open (interpolate open to device frequencies).
    4. Z_corr1 = 1/Y_corr1; Z_final = Z_corr1 - Z_short (interpolate short).
    5. C_corrected = Im(Y_final) / omega, omega = 2*pi*f.

    Returns a DataFrame with the same structure as device_df but with
    corrected magnitude, phase, capacitance (and derived Z real/imag).
    """
    fc = _col(device_df, freq_col) or freq_col
    mc = _col(device_df, mag_col) or mag_col
    pc = _col(device_df, phase_col) or phase_col
    cc = _col(device_df, cap_col) or cap_col
    if fc not in device_df.columns or mc not in device_df.columns or pc not in device_df.columns:
        raise KeyError(f"Device DataFrame needs {freq_col}, {mag_col}, {phase_col}. Got: {list(device_df.columns)}")

    f_dev = np.asarray(device_df[fc].values, dtype=float)
    mag_dev = np.asarray(device_df[mc].values, dtype=float)
    phase_dev = np.asarray(device_df[pc].values, dtype=float)

    # Open
    fo = np.asarray(open_df[_col(open_df, freq_col) or freq_col].values, dtype=float)
    mo = np.asarray(open_df[_col(open_df, mag_col) or mag_col].values, dtype=float)
    po = np.asarray(open_df[_col(open_df, phase_col) or phase_col].values, dtype=float)
    zro, zio = _z_from_mag_phase(fo, mo, po)
    # Interpolate Y_open to device frequencies
    yr_o, yi_o = _interp_complex(f_dev, fo, zro, zio)
    Y_open_re = yr_o / (yr_o**2 + yi_o**2)
    Y_open_im = -yi_o / (yr_o**2 + yi_o**2)
    # Handle NaN/zero
    bad = ~np.isfinite(yr_o) | ~np.isfinite(yi_o) | ((yr_o**2 + yi_o**2) < 1e-30)
    Y_open_re[bad] = np.nan
    Y_open_im[bad] = np.nan

    # Short
    fs = np.asarray(short_df[_col(short_df, freq_col) or freq_col].values, dtype=float)
    ms = np.asarray(short_df[_col(short_df, mag_col) or mag_col].values, dtype=float)
    ps = np.asarray(short_df[_col(short_df, phase_col) or phase_col].values, dtype=float)
    zrs, zis = _z_from_mag_phase(fs, ms, ps)
    Z_short_re, Z_short_im = _interp_complex(f_dev, fs, zrs, zis)

    # Device Z and Y
    zr_dev, zi_dev = _z_from_mag_phase(f_dev, mag_dev, phase_dev)
    denom = zr_dev**2 + zi_dev**2
    Y_dev_re = zr_dev / np.where(denom > 1e-30, denom, np.nan)
    Y_dev_im = -zi_dev / np.where(denom > 1e-30, denom, np.nan)

    # Step 3: Y_corr1 = Y_device - Y_open
    Y_corr1_re = Y_dev_re - Y_open_re
    Y_corr1_im = Y_dev_im - Y_open_im

    # Step 4: Z_corr1 = 1/Y_corr1, Z_final = Z_corr1 - Z_short
    denom1 = Y_corr1_re**2 + Y_corr1_im**2
    Z_corr1_re = Y_corr1_re / np.where(denom1 > 1e-30, denom1, np.nan)
    Z_corr1_im = -Y_corr1_im / np.where(denom1 > 1e-30, denom1, np.nan)
    Z_final_re = Z_corr1_re - Z_short_re
    Z_final_im = Z_corr1_im - Z_short_im

    # Magnitude and phase from Z_final
    mag_final = np.sqrt(Z_final_re**2 + Z_final_im**2)
    phase_final_rad = np.arctan2(Z_final_im, Z_final_re)
    phase_final_deg = np.rad2deg(phase_final_rad)

    # Step 5: Y_final = 1/Z_final, C = B/omega, B = Im(Y_final)
    denom_f = Z_final_re**2 + Z_final_im**2
    Y_final_re = Z_final_re / np.where(denom_f > 1e-30, denom_f, np.nan)
    Y_final_im = -Z_final_im / np.where(denom_f > 1e-30, denom_f, np.nan)
    omega = 2.0 * np.pi * f_dev
    omega_safe = np.where(omega > 1e-30, omega, np.nan)
    cap_corrected = Y_final_im / omega_safe  # B/omega
    cap_corrected = np.where(np.isfinite(cap_corrected), cap_corrected, np.nan)

    out = device_df.copy()
    out[mc] = mag_final
    out[pc] = phase_final_deg
    if cc in out.columns:
        out[cc] = np.abs(cap_corrected)  # Capacitance magnitude
    return out
