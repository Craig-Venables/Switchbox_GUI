"""
Filter data above a frequency cutoff and export Origin-ready CSV.

Origin CSV columns: Frequency_Hz, Z_Magnitude_Ohms, Phase_deg, Capacitance_F,
Z_Real_Ohms, Z_Imag_Ohms (for easy Bode, C vs f, and Nyquist in Origin).
"""

from pathlib import Path
from typing import Optional, Union

import numpy as np
import pandas as pd


def _build_origin_columns(
    df: pd.DataFrame,
    fc: Optional[str],
    mc: Optional[str],
    pc: Optional[str],
    cc: Optional[str],
) -> pd.DataFrame:
    """Build Origin columns from one DataFrame. Returns DataFrame with standard column names."""
    n = len(df)
    out = pd.DataFrame()
    if fc and fc in df.columns:
        out["Frequency_Hz"] = pd.to_numeric(df[fc], errors="coerce")
    else:
        out["Frequency_Hz"] = np.full(n, np.nan)
    if mc and mc in df.columns:
        mag = np.asarray(pd.to_numeric(df[mc], errors="coerce").values, dtype=float)
        out["Z_Magnitude_Ohms"] = np.abs(mag)
    else:
        mag = np.full(n, np.nan)
        out["Z_Magnitude_Ohms"] = np.full(n, np.nan)
    if pc and pc in df.columns:
        phase_deg = pd.to_numeric(df[pc], errors="coerce").values
        out["Phase_deg"] = phase_deg
        phase_rad = np.deg2rad(phase_deg)
        out["Z_Real_Ohms"] = np.abs(mag) * np.cos(phase_rad)
        out["Z_Imag_Ohms"] = -np.abs(mag) * np.sin(phase_rad)
    else:
        out["Phase_deg"] = np.full(n, np.nan)
        out["Z_Real_Ohms"] = np.abs(mag)
        out["Z_Imag_Ohms"] = np.zeros(n)
    if cc and cc in df.columns:
        out["Capacitance_F"] = pd.to_numeric(df[cc], errors="coerce")
    else:
        out["Capacitance_F"] = np.full(n, np.nan)
    return out

# Standard column names (must match impedance_plots / smart_loader)
FREQ = "Frequency (Hz)"
MAG = "Impedance Magnitude (Ohms)"
PHASE = "Impedance Phase Degrees (')"
CAP = "Capacitance Magnitude (F)"


def _col(df: pd.DataFrame, name: str) -> Optional[str]:
    """Return actual column name in df that matches name (strip)."""
    for c in df.columns:
        if str(c).strip() == name:
            return c
    return None


def filter_by_max_frequency(
    df: pd.DataFrame,
    max_freq: float = 1e6,
    freq_col: str = FREQ,
) -> pd.DataFrame:
    """Return a view with only rows where frequency <= max_freq (removes noise above 1e6 Hz)."""
    fc = _col(df, freq_col) or freq_col
    if fc not in df.columns:
        return df
    return df.loc[df[fc] <= max_freq].copy()


def export_origin_csv(
    df: pd.DataFrame,
    path: Union[str, Path],
    freq_col: str = FREQ,
    mag_col: str = MAG,
    phase_col: str = PHASE,
    cap_col: str = CAP,
) -> Path:
    """
    Write an Origin-friendly CSV with columns for Bode, C vs f, and Nyquist.

    Columns: Frequency_Hz, Z_Magnitude_Ohms, Phase_deg, Capacitance_F,
             Z_Real_Ohms, Z_Imag_Ohms (Nyquist: plot Z_Real vs Z_Imag).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fc = _col(df, freq_col) or freq_col
    mc = _col(df, mag_col) or mag_col
    pc = _col(df, phase_col) or phase_col
    cc = _col(df, cap_col) or cap_col
    out = _build_origin_columns(df, fc, mc, pc, cc)
    out = out[["Frequency_Hz", "Z_Magnitude_Ohms", "Phase_deg", "Capacitance_F", "Z_Real_Ohms", "Z_Imag_Ohms"]]
    out.to_csv(path, index=False, na_rep="")
    return path


def export_origin_csv_with_corrected(
    df_uncorrected: pd.DataFrame,
    path: Union[str, Path],
    df_corrected: Optional[pd.DataFrame] = None,
    freq_col: str = FREQ,
    mag_col: str = MAG,
    phase_col: str = PHASE,
    cap_col: str = CAP,
) -> Path:
    """
    Write Origin CSV with uncorrected columns plus corrected columns when df_corrected is provided.

    When df_corrected is None, same as export_origin_csv.
    When provided: adds Z_Magnitude_Ohms_corrected, Phase_deg_corrected, Capacitance_F_corrected,
    Z_Real_Ohms_corrected, Z_Imag_Ohms_corrected.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fc = _col(df_uncorrected, freq_col) or freq_col
    mc = _col(df_uncorrected, mag_col) or mag_col
    pc = _col(df_uncorrected, phase_col) or phase_col
    cc = _col(df_uncorrected, cap_col) or cap_col
    out = _build_origin_columns(df_uncorrected, fc, mc, pc, cc)
    if df_corrected is not None and len(df_corrected) == len(df_uncorrected):
        corr = _build_origin_columns(df_corrected, fc, mc, pc, cc)
        out["Z_Magnitude_Ohms_corrected"] = corr["Z_Magnitude_Ohms"]
        out["Phase_deg_corrected"] = corr["Phase_deg"]
        out["Capacitance_F_corrected"] = corr["Capacitance_F"]
        out["Z_Real_Ohms_corrected"] = corr["Z_Real_Ohms"]
        out["Z_Imag_Ohms_corrected"] = corr["Z_Imag_Ohms"]
    cols = list(out.columns)
    out = out[cols]
    out.to_csv(path, index=False, na_rep="")
    return path
