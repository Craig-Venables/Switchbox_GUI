"""Cross-spectrum Solartron analysis plots (bias overlay, HRS vs LRS)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .loader import SMART_FREQ, SMART_MAG, SMART_PHASE


def plot_bias_overlay(spectra: List[Dict[str, Any]], out_path: Path | str) -> Optional[Path]:
    """Overlay |Z| vs f for spectra that have bias_V."""
    usable = [s for s in spectra if s.get("_df") is not None and s.get("bias_V") is not None]
    if len(usable) < 2:
        return None
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    for s in sorted(usable, key=lambda x: (x.get("bias_V") is None, x.get("bias_V") or 0)):
        df = s["_df"]
        if SMART_FREQ not in df.columns or SMART_MAG not in df.columns:
            continue
        f = pd.to_numeric(df[SMART_FREQ], errors="coerce")
        z = np.abs(pd.to_numeric(df[SMART_MAG], errors="coerce"))
        ax.loglog(f, z, ".-", label=f"V={s['bias_V']}", markersize=3)

    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("|Z| (Ohm)")
    ax.set_title("Bias series |Z| overlay")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    try:
        fig.savefig(out_path, dpi=140, bbox_inches="tight")
        return out_path
    except Exception:
        return None
    finally:
        plt.close(fig)


def plot_hrs_lrs_compare(
    hrs_spectra: List[Dict[str, Any]],
    lrs_spectra: List[Dict[str, Any]],
    out_path: Path | str,
) -> Optional[Path]:
    if not hrs_spectra or not lrs_spectra:
        return None
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    def _plot_group(ax, group, label_prefix, color):
        for s in group:
            df = s.get("_df")
            if df is None or SMART_FREQ not in df.columns:
                continue
            f = pd.to_numeric(df[SMART_FREQ], errors="coerce")
            z = np.abs(pd.to_numeric(df[SMART_MAG], errors="coerce"))
            ax.loglog(f, z, ".-", color=color, alpha=0.7, markersize=2, label=f"{label_prefix} {s.get('filename','')[:20]}")

    _plot_group(axes[0], hrs_spectra, "HRS", "C3")
    _plot_group(axes[0], lrs_spectra, "LRS", "C0")
    axes[0].set_xlabel("Frequency (Hz)")
    axes[0].set_ylabel("|Z| (Ohm)")
    axes[0].set_title("|Z| HRS vs LRS")
    axes[0].grid(True, which="both", alpha=0.3)
    axes[0].legend(fontsize=7)

    # Nyquist-ish: use phase if available
    for s, color, lab in (
        (hrs_spectra[0], "C3", "HRS"),
        (lrs_spectra[0], "C0", "LRS"),
    ):
        df = s.get("_df")
        if df is None or SMART_MAG not in df.columns or SMART_PHASE not in df.columns:
            continue
        mag = np.abs(pd.to_numeric(df[SMART_MAG], errors="coerce").to_numpy(dtype=float))
        phase = np.deg2rad(pd.to_numeric(df[SMART_PHASE], errors="coerce").to_numpy(dtype=float))
        re_z = mag * np.cos(phase)
        im_z = mag * np.sin(phase)
        axes[1].plot(re_z, -im_z, ".-", color=color, markersize=2, label=lab)
    axes[1].set_xlabel("Re(Z) (Ohm)")
    axes[1].set_ylabel("-Im(Z) (Ohm)")
    axes[1].set_title("Nyquist (first HRS/LRS)")
    axes[1].grid(True, alpha=0.3)
    axes[1].legend(fontsize=8)

    fig.tight_layout()
    try:
        fig.savefig(out_path, dpi=140, bbox_inches="tight")
        return out_path
    except Exception:
        return None
    finally:
        plt.close(fig)


def plot_rs_vs_bias(spectra: List[Dict[str, Any]], out_path: Path | str) -> Optional[Path]:
    pts = [
        (s.get("bias_V"), s.get("series_resistance_ohms"))
        for s in spectra
        if s.get("bias_V") is not None and s.get("series_resistance_ohms") is not None
    ]
    pts = [(b, r) for b, r in pts if b == b and r == r]
    if len(pts) < 2:
        return None
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pts.sort(key=lambda x: x[0])
    bias, rs = zip(*pts)
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(bias, rs, "o-")
    ax.set_xlabel("Bias (V)")
    ax.set_ylabel("Rs (Ohm)")
    ax.set_title("Series resistance vs bias")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    try:
        fig.savefig(out_path, dpi=140, bbox_inches="tight")
        return out_path
    except Exception:
        return None
    finally:
        plt.close(fig)
