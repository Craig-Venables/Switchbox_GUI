"""Spectrum / run metrics for Solartron origin_data (including deep EIS fits)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd

from .fitting import deep_eis_analysis
from .loader import (
    ORIGIN_CAP,
    ORIGIN_FREQ,
    ORIGIN_IMAG,
    ORIGIN_MAG,
    ORIGIN_PHASE,
    ORIGIN_REAL,
    SMART_CAP,
    SMART_FREQ,
    SMART_MAG,
    SMART_PHASE,
    load_origin_csv,
    parse_bias_from_name,
    tag_run_from_name,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_Z_TOOL = _REPO_ROOT / "tools" / "impedance_analyzer"

ANCHOR_HZ = (1.0, 10.0, 100.0, 1e3, 1e4)


def _ensure_z_tool() -> None:
    p = str(_Z_TOOL)
    if p not in sys.path:
        sys.path.insert(0, p)


def _interp_at(f: np.ndarray, y: np.ndarray, f0: float) -> float:
    mask = np.isfinite(f) & np.isfinite(y)
    if mask.sum() < 2:
        return float("nan")
    ff, yy = f[mask], y[mask]
    order = np.argsort(ff)
    ff, yy = ff[order], yy[order]
    if f0 < ff[0] or f0 > ff[-1]:
        return float(yy[np.argmin(np.abs(ff - f0))])
    return float(np.interp(f0, ff, yy))


def _anchor_key(f0: float) -> str:
    if f0 >= 1000:
        return f"{int(f0 / 1000)}k"
    if f0 == int(f0):
        return str(int(f0))
    return str(f0)


def spectrum_metrics(df: pd.DataFrame, meta: Dict[str, Any], run_name: str = "") -> Dict[str, Any]:
    """Nyquist params + anchors + deep circuit fits for one spectrum."""
    _ensure_z_tool()
    from impedance_plots import extract_nyquist_parameters  # type: ignore

    out: Dict[str, Any] = {
        "run": run_name,
        "filename": meta.get("filename"),
        "source": meta.get("source"),
        "used_corrected": bool(meta.get("used_corrected")),
        "bias_V": meta.get("bias_V"),
        "run_tag": tag_run_from_name(run_name) if run_name else "other",
    }

    try:
        nyq = extract_nyquist_parameters(df)
        out["series_resistance_ohms"] = nyq.get("series_resistance_ohms")
        out["parallel_resistance_ohms"] = nyq.get("parallel_resistance_ohms")
        out["peak_frequency_hz"] = nyq.get("peak_frequency_hz")
        out["relaxation_time_s"] = nyq.get("relaxation_time_s")
    except Exception as e:
        out["nyquist_error"] = str(e)
        out["series_resistance_ohms"] = float("nan")
        out["parallel_resistance_ohms"] = float("nan")
        out["peak_frequency_hz"] = float("nan")
        out["relaxation_time_s"] = float("nan")

    fcol = SMART_FREQ if SMART_FREQ in df.columns else ORIGIN_FREQ
    mcol = SMART_MAG if SMART_MAG in df.columns else ORIGIN_MAG
    pcol = SMART_PHASE if SMART_PHASE in df.columns else ORIGIN_PHASE
    ccol = SMART_CAP if SMART_CAP in df.columns else (ORIGIN_CAP if ORIGIN_CAP in df.columns else None)

    f = mag = phase = None
    if fcol in df.columns and mcol in df.columns:
        f = pd.to_numeric(df[fcol], errors="coerce").to_numpy(dtype=float)
        mag = np.abs(pd.to_numeric(df[mcol], errors="coerce").to_numpy(dtype=float))
        for f0 in ANCHOR_HZ:
            out[f"Zmag_{_anchor_key(f0)}Hz"] = _interp_at(f, mag, f0)
        if ccol and ccol in df.columns:
            cap = pd.to_numeric(df[ccol], errors="coerce").to_numpy(dtype=float)
            for f0 in ANCHOR_HZ:
                out[f"C_{_anchor_key(f0)}Hz"] = _interp_at(f, cap, f0)
        if pcol in df.columns:
            phase = pd.to_numeric(df[pcol], errors="coerce").to_numpy(dtype=float)

    # Prefer mag+phase (physics Im). Origin Z_Imag is typically -Im(Z).
    origin_imag_negated = False
    if f is not None and mag is not None and phase is not None:
        pr = np.deg2rad(phase)
        z_re = mag * np.cos(pr)
        z_im = mag * np.sin(pr)
    elif ORIGIN_REAL in df.columns and ORIGIN_IMAG in df.columns and f is not None:
        z_re = pd.to_numeric(df[ORIGIN_REAL], errors="coerce").to_numpy(dtype=float)
        z_im = pd.to_numeric(df[ORIGIN_IMAG], errors="coerce").to_numpy(dtype=float)
        origin_imag_negated = True  # Origin Nyquist convention
    else:
        z_re = z_im = None

    if f is not None and z_re is not None and z_im is not None:
        try:
            deep = deep_eis_analysis(
                f,
                z_re,
                z_im,
                mag=mag,
                phase_deg=phase,
                origin_imag_is_negated=origin_imag_negated and mag is None,
            )
            for k, v in deep.items():
                if k == "circuit_fit":
                    out["circuit_fit_models"] = {
                        name: {kk: vv for kk, vv in m.items() if kk != "params"}
                        for name, m in (v.get("models") or {}).items()
                    }
                    continue
                if k == "anomalies":
                    out["anomalies"] = v
                    out["anomalies_str"] = ",".join(v) if v else ""
                    continue
                out[k] = v
        except Exception as e:
            out["deep_eis_error"] = str(e)
            out["anomalies"] = ["deep_eis_failed"]
            out["anomalies_str"] = "deep_eis_failed"

    out["_df"] = df
    return out


def analyze_origin_file(path: Path | str, run_name: str = "") -> Dict[str, Any]:
    df, meta = load_origin_csv(path)
    if meta.get("bias_V") is None:
        meta["bias_V"] = parse_bias_from_name(Path(path).stem)
    return spectrum_metrics(df, meta, run_name=run_name)


def flatten_spectrum_row(metrics: Dict[str, Any]) -> Dict[str, Any]:
    row: Dict[str, Any] = {}
    for k, v in metrics.items():
        if k.startswith("_"):
            continue
        if k in ("circuit_fit_models", "anomalies"):
            if k == "anomalies" and isinstance(v, list):
                row["anomalies_str"] = ",".join(v)
            continue
        if isinstance(v, dict):
            continue
        if isinstance(v, (np.floating, np.integer)):
            row[k] = v.item()
        else:
            row[k] = v
    return row
