"""
Filter data above a frequency cutoff and export Origin-ready CSV.

Origin CSV columns: Frequency_Hz, Z_Magnitude_Ohms, Phase_deg, Capacitance_F,
Z_Real_Ohms, Z_Imag_Ohms (for easy Bode, C vs f, and Nyquist in Origin).
"""

from pathlib import Path
from typing import Optional, Union

import numpy as np
import pandas as pd

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

    n = len(df)
    out = pd.DataFrame()
    if fc in df.columns:
        out["Frequency_Hz"] = pd.to_numeric(df[fc], errors="coerce")
    else:
        out["Frequency_Hz"] = np.full(n, np.nan)
    if mc in df.columns:
        mag = np.asarray(pd.to_numeric(df[mc], errors="coerce").values, dtype=float)
        out["Z_Magnitude_Ohms"] = np.abs(mag)
    else:
        mag = np.full(n, np.nan)
        out["Z_Magnitude_Ohms"] = np.full(n, np.nan)

    if pc in df.columns:
        phase_deg = pd.to_numeric(df[pc], errors="coerce").values
        out["Phase_deg"] = phase_deg
        phase_rad = np.deg2rad(phase_deg)
        out["Z_Real_Ohms"] = np.abs(mag) * np.cos(phase_rad)
        out["Z_Imag_Ohms"] = -np.abs(mag) * np.sin(phase_rad)  # -Im(Z) for usual Nyquist
    else:
        out["Phase_deg"] = np.full(n, np.nan)
        out["Z_Real_Ohms"] = np.abs(mag)
        out["Z_Imag_Ohms"] = np.zeros(n)

    if cc in df.columns:
        out["Capacitance_F"] = pd.to_numeric(df[cc], errors="coerce")
    else:
        out["Capacitance_F"] = np.full(n, np.nan)

    # Reorder for clarity
    out = out[["Frequency_Hz", "Z_Magnitude_Ohms", "Phase_deg", "Capacitance_F", "Z_Real_Ohms", "Z_Imag_Ohms"]]
    out.to_csv(path, index=False, na_rep="")
    return path
