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

    Correction procedure:

    Step 1: Remove the series lead effect first using the short
      Z_s(f) = Z_short(f)
      Z'(f) = Z_device(f) - Z_s(f)

    Step 2: Remove the parallel stray capacitance using the open
      But first remove the same series effect from the open:
      Z_open,shunt(f) = Z_open(f) - Z_s(f)
      
      Convert that to the setup's parallel admittance:
      Y_p(f) = 1/Z_open,shunt(f)
      
      Convert your device-after-series-removal to admittance and subtract:
      Y'(f) = 1/Z'(f)
      Y_DUT(f) = Y'(f) - Y_p(f)
      
      Convert back to get the corrected device impedance:
      Z_DUT(f) = 1/Y_DUT(f)

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

    # Step 1: Build complex Z for device, open, and short
    zr_dev, zi_dev = _z_from_mag_phase(f_dev, mag_dev, phase_dev)

    # Open
    fo = np.asarray(open_df[_col(open_df, freq_col) or freq_col].values, dtype=float)
    mo = np.asarray(open_df[_col(open_df, mag_col) or mag_col].values, dtype=float)
    po = np.asarray(open_df[_col(open_df, phase_col) or phase_col].values, dtype=float)
    zro, zio = _z_from_mag_phase(fo, mo, po)

    # Short
    fs = np.asarray(short_df[_col(short_df, freq_col) or freq_col].values, dtype=float)
    ms = np.asarray(short_df[_col(short_df, mag_col) or mag_col].values, dtype=float)
    ps = np.asarray(short_df[_col(short_df, phase_col) or phase_col].values, dtype=float)
    zrs, zis = _z_from_mag_phase(fs, ms, ps)

    # Step 2: Interpolate short to device frequencies, compute Z_s(f) = Z_short(f)
    Z_short_re, Z_short_im = _interp_complex(f_dev, fs, zrs, zis)

    # Step 3: Remove series lead effect from device: Z'(f) = Z_device(f) - Z_s(f)
    Z_prime_re = zr_dev - Z_short_re
    Z_prime_im = zi_dev - Z_short_im

    # Step 4: Interpolate short to open frequencies, subtract from open
    # Z_open,shunt(f) = Z_open(f) - Z_s(f)
    Z_short_re_open, Z_short_im_open = _interp_complex(fo, fs, zrs, zis)
    Z_open_shunt_re = zro - Z_short_re_open
    Z_open_shunt_im = zio - Z_short_im_open

    # Step 5: Interpolate corrected open to device frequencies
    Z_open_shunt_re_dev, Z_open_shunt_im_dev = _interp_complex(f_dev, fo, Z_open_shunt_re, Z_open_shunt_im)

    # Step 6: Convert corrected open to admittance: Y_p(f) = 1/Z_open,shunt(f)
    denom_open = Z_open_shunt_re_dev**2 + Z_open_shunt_im_dev**2
    Y_p_re = Z_open_shunt_re_dev / np.where(denom_open > 1e-30, denom_open, np.nan)
    Y_p_im = -Z_open_shunt_im_dev / np.where(denom_open > 1e-30, denom_open, np.nan)
    # Handle NaN/zero
    bad_open = ~np.isfinite(Z_open_shunt_re_dev) | ~np.isfinite(Z_open_shunt_im_dev) | (denom_open < 1e-30)
    Y_p_re[bad_open] = np.nan
    Y_p_im[bad_open] = np.nan

    # Step 7: Convert device-after-series-removal to admittance: Y'(f) = 1/Z'(f)
    denom_prime = Z_prime_re**2 + Z_prime_im**2
    Y_prime_re = Z_prime_re / np.where(denom_prime > 1e-30, denom_prime, np.nan)
    Y_prime_im = -Z_prime_im / np.where(denom_prime > 1e-30, denom_prime, np.nan)
    # Handle NaN/zero
    bad_prime = ~np.isfinite(Z_prime_re) | ~np.isfinite(Z_prime_im) | (denom_prime < 1e-30)
    Y_prime_re[bad_prime] = np.nan
    Y_prime_im[bad_prime] = np.nan

    # Step 8: Remove parallel stray capacitance: Y_DUT(f) = Y'(f) - Y_p(f)
    Y_DUT_re = Y_prime_re - Y_p_re
    Y_DUT_im = Y_prime_im - Y_p_im

    # Step 9: Convert back to impedance: Z_DUT(f) = 1/Y_DUT(f)
    denom_dut = Y_DUT_re**2 + Y_DUT_im**2
    Z_DUT_re = Y_DUT_re / np.where(denom_dut > 1e-30, denom_dut, np.nan)
    Z_DUT_im = -Y_DUT_im / np.where(denom_dut > 1e-30, denom_dut, np.nan)
    # Handle NaN/zero
    bad_dut = ~np.isfinite(Y_DUT_re) | ~np.isfinite(Y_DUT_im) | (denom_dut < 1e-30)
    Z_DUT_re[bad_dut] = np.nan
    Z_DUT_im[bad_dut] = np.nan

    # Step 10: Extract magnitude and phase from Z_DUT
    mag_final = np.sqrt(Z_DUT_re**2 + Z_DUT_im**2)
    phase_final_rad = np.arctan2(Z_DUT_im, Z_DUT_re)
    phase_final_deg = np.rad2deg(phase_final_rad)

    # Step 11: Extract capacitance from Y_DUT: C = B/omega, where B = Im(Y_DUT)
    omega = 2.0 * np.pi * f_dev
    omega_safe = np.where(omega > 1e-30, omega, np.nan)
    cap_corrected = Y_DUT_im / omega_safe  # B/omega
    cap_corrected = np.where(np.isfinite(cap_corrected), cap_corrected, np.nan)

    out = device_df.copy()
    out[mc] = mag_final
    out[pc] = phase_final_deg
    if cc in out.columns:
        out[cc] = np.abs(cap_corrected)  # Capacitance magnitude
    return out
