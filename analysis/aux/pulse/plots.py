"""Headless diagnostic plots for pulse analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .loader import (
    FAMILY_DEP_ONLY,
    FAMILY_ENDURANCE,
    FAMILY_IV_SWEEP,
    FAMILY_LASER_READ,
    FAMILY_MULTI_READ,
    FAMILY_POT_DEP,
    FAMILY_POT_ONLY,
    FAMILY_PULSE_TRAIN,
    FAMILY_RANGE_FINDER,
    FAMILY_READ_ONLY,
    FAMILY_READ_REPEAT,
    FAMILY_RELAXATION,
    FAMILY_RETENTION,
    FAMILY_SLOW_PULSE,
    FAMILY_WIDTH_SWEEP,
)


def _label_str(val: Any) -> str:
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="ignore")
    return str(val).strip()


def _plot_r_vs_t(ax, metrics: Dict[str, Any], log_r: bool = True) -> None:
    R = np.asarray(metrics["_r"], dtype=float)
    t = np.asarray(metrics.get("_t", np.arange(len(R))), dtype=float)
    ax.plot(t, R, ".-", markersize=3)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Resistance (Ohm)")
    if log_r:
        ax.set_yscale("log")
    if metrics.get("r_initial") is not None:
        ax.axhline(metrics["r_initial"], color="C1", ls="--", lw=1, label="R_initial")
        ax.legend()


def plot_pulse_dashboard(metrics: Dict[str, Any], out_path: Path | str) -> Optional[Path]:
    """Write a single dashboard PNG for one file's metrics. Returns path or None."""
    family = metrics.get("family")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    title = f"{metrics.get('test_name') or family} — {metrics.get('filename', '')}"

    try:
        if family == FAMILY_ENDURANCE and "_series" in metrics:
            s = metrics["_series"]
            cyc, r_set, r_reset = s["cycle"], s["r_set"], s["r_reset"]
            ax.plot(cyc, r_set, "o-", label="R_SET", markersize=3)
            ax.plot(cyc, r_reset, "s-", label="R_RESET", markersize=3)
            ax.set_xlabel("Cycle")
            ax.set_ylabel("Resistance (Ohm)")
            ax.legend()
            ax.set_yscale("log")
        elif family in (FAMILY_POT_DEP, FAMILY_POT_ONLY, FAMILY_DEP_ONLY) and "_r" in metrics:
            R = np.asarray(metrics["_r"], dtype=float)
            idx = metrics.get("_index", np.arange(len(R)))
            phases = metrics.get("_phases")
            if phases is not None and family == FAMILY_POT_DEP:
                colors = []
                for p in phases:
                    pl = _label_str(p).lower()
                    if "pot" in pl:
                        colors.append("C0")
                    elif "dep" in pl:
                        colors.append("C3")
                    else:
                        colors.append("0.5")
                ax.scatter(idx[: len(R)], R, c=colors[: len(R)], s=18)
            else:
                ax.plot(idx[: len(R)], R, ".-")
            ax.set_xlabel("Index")
            ax.set_ylabel("Resistance (Ohm)")
            ax.set_yscale("log")
        elif family == FAMILY_WIDTH_SWEEP and "_r" in metrics:
            R = np.asarray(metrics["_r"], dtype=float)
            widths = metrics.get("_widths")
            if widths is not None:
                w = np.asarray(widths, dtype=float)
                mask = np.isfinite(R) & np.isfinite(w) & (w > 0)
                ax.semilogx(w[mask], R[mask], "o-", markersize=4)
                ax.set_xlabel("Pulse width (s)")
            else:
                ax.plot(np.arange(len(R)), R, ".-")
                ax.set_xlabel("Index")
            ax.set_ylabel("Resistance (Ohm)")
            ax.set_yscale("log")
            tw = metrics.get("threshold_width_s")
            if tw is not None and np.isfinite(tw):
                ax.axvline(tw, color="C3", ls="--", lw=1, label=f"threshold≈{tw:.2e}s")
                ax.legend()
        elif family == FAMILY_IV_SWEEP and "_v" in metrics and "_i" in metrics:
            V = np.asarray(metrics["_v"], dtype=float)
            I = np.asarray(metrics["_i"], dtype=float)
            ax.plot(V, I, ".-", markersize=3)
            ax.set_xlabel("Voltage (V)")
            ax.set_ylabel("Current (A)")
        elif family == FAMILY_RANGE_FINDER and "_i" in metrics:
            I = np.asarray(metrics["_i"], dtype=float)
            t = np.asarray(metrics.get("_t", np.arange(len(I))), dtype=float)
            ax.semilogy(t, np.abs(I), ".-", markersize=3)
            ax.set_xlabel("Index")
            ax.set_ylabel("|Current| (A)")
            sug = metrics.get("suggested_i_range")
            if sug is not None and np.isfinite(sug):
                ax.axhline(sug, color="C3", ls="--", lw=1, label=f"suggested range {sug:.0e} A")
                ax.legend()
        elif family in (
            FAMILY_MULTI_READ,
            FAMILY_PULSE_TRAIN,
            FAMILY_READ_ONLY,
            FAMILY_READ_REPEAT,
            FAMILY_RELAXATION,
            FAMILY_RETENTION,
            FAMILY_LASER_READ,
            FAMILY_SLOW_PULSE,
        ) and "_r" in metrics:
            _plot_r_vs_t(ax, metrics)
        elif "_r" in metrics:
            _plot_r_vs_t(ax, metrics)
        else:
            ax.text(0.5, 0.5, "No plot for this family", ha="center", va="center", transform=ax.transAxes)

        ax.set_title(title, fontsize=10)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(out_path, dpi=140, bbox_inches="tight")
        return out_path
    except Exception:
        return None
    finally:
        plt.close(fig)
