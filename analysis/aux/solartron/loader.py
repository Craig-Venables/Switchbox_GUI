"""Load Solartron origin_data CSVs (prefer corrected columns)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# Origin-style columns (impedance_analyzer export)
ORIGIN_FREQ = "Frequency_Hz"
ORIGIN_MAG = "Z_Magnitude_Ohms"
ORIGIN_PHASE = "Phase_deg"
ORIGIN_CAP = "Capacitance_F"
ORIGIN_REAL = "Z_Real_Ohms"
ORIGIN_IMAG = "Z_Imag_Ohms"

# SMaRT-style names used by extract_nyquist_parameters
SMART_FREQ = "Frequency (Hz)"
SMART_MAG = "Impedance Magnitude (Ohms)"
SMART_PHASE = "Impedance Phase Degrees (')"
SMART_CAP = "Capacitance Magnitude (F)"


def parse_bias_from_name(name: str) -> Optional[float]:
    """Parse VBp0.500 / VBm1.000 (minus) or similar from filename/stem."""
    m = re.search(r"VBm\s*([+]?\d+(?:\.\d+)?)", name, re.IGNORECASE)
    if m:
        return -float(m.group(1))
    m = re.search(r"VBp?\s*([+-]?\d+(?:\.\d+)?)", name, re.IGNORECASE)
    if m:
        return float(m.group(1))
    m = re.search(r"bias[_\s]*([+-]?\d+(?:\.\d+)?)", name, re.IGNORECASE)
    if m:
        return float(m.group(1))
    return None


def tag_run_from_name(run_name: str) -> str:
    n = run_name.lower()
    if "bias_series" in n or "bias series" in n:
        return "bias_series"
    if "hrs" in n:
        return "hrs"
    if "lrs" in n:
        return "lrs"
    if "laser" in n:
        return "laser"
    return "other"


def _pick_corrected(df: pd.DataFrame, base: str) -> Tuple[str, bool]:
    corrected = f"{base}_corrected"
    if corrected in df.columns:
        return corrected, True
    return base, False


def load_origin_csv(path: Path | str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Load an origin_data CSV into a DataFrame with SMaRT-style column names
    suitable for extract_nyquist_parameters / plot helpers.

    Returns (df_smart, meta) where meta includes used_corrected, bias_V, source.
    """
    path = Path(path)
    df = pd.read_csv(path)
    df.columns = [str(c).strip() for c in df.columns]

    meta: Dict[str, Any] = {
        "source": str(path),
        "filename": path.name,
        "used_corrected": False,
        "bias_V": parse_bias_from_name(path.stem),
    }

    # Already SMaRT-style?
    if SMART_MAG in df.columns and SMART_PHASE in df.columns:
        out = df.copy()
        meta["used_corrected"] = any(c.endswith("_corrected") for c in df.columns)
        return out, meta

    # Origin-style (with optional corrected)
    if ORIGIN_MAG in df.columns or f"{ORIGIN_MAG}_corrected" in df.columns:
        mag_col, corr_m = _pick_corrected(df, ORIGIN_MAG)
        phase_col, corr_p = _pick_corrected(df, ORIGIN_PHASE)
        cap_col, _ = _pick_corrected(df, ORIGIN_CAP)
        freq_col = ORIGIN_FREQ if ORIGIN_FREQ in df.columns else None
        if freq_col is None:
            for c in df.columns:
                if "freq" in c.lower():
                    freq_col = c
                    break

        meta["used_corrected"] = corr_m or corr_p
        out = pd.DataFrame()
        if freq_col:
            out[SMART_FREQ] = pd.to_numeric(df[freq_col], errors="coerce")
        out[SMART_MAG] = np.abs(pd.to_numeric(df[mag_col], errors="coerce"))
        out[SMART_PHASE] = pd.to_numeric(df[phase_col], errors="coerce")
        if cap_col in df.columns:
            out[SMART_CAP] = pd.to_numeric(df[cap_col], errors="coerce")
        # Keep Origin names too for anchors
        out[ORIGIN_FREQ] = out.get(SMART_FREQ)
        out[ORIGIN_MAG] = out[SMART_MAG]
        out[ORIGIN_PHASE] = out[SMART_PHASE]
        if SMART_CAP in out.columns:
            out[ORIGIN_CAP] = out[SMART_CAP]
        # Real/Imag if present
        real_col, _ = _pick_corrected(df, ORIGIN_REAL) if ORIGIN_REAL in df.columns or f"{ORIGIN_REAL}_corrected" in df.columns else (None, False)
        imag_col, _ = _pick_corrected(df, ORIGIN_IMAG) if ORIGIN_IMAG in df.columns or f"{ORIGIN_IMAG}_corrected" in df.columns else (None, False)
        if real_col and real_col in df.columns:
            out[ORIGIN_REAL] = pd.to_numeric(df[real_col], errors="coerce")
        if imag_col and imag_col in df.columns:
            out[ORIGIN_IMAG] = pd.to_numeric(df[imag_col], errors="coerce")
        return out, meta

    raise ValueError(f"Unrecognized origin CSV columns in {path.name}: {list(df.columns)}")


def list_origin_csvs(run_dir: Path | str) -> List[Path]:
    run_dir = Path(run_dir)
    origin = run_dir / "origin_data"
    if not origin.is_dir():
        return []
    return sorted(origin.glob("*.csv"))
