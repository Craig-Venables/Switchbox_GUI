import os
import re
from typing import Dict, List, Optional, Tuple, Set

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm

# Import root settings from ITO.py if available by path
from ITO import ONEDRIVE_ROOT, EXCLUDE_SAMPLES, CONDUCTIVITY_THRESHOLDS

# Output directory for global summary inside ONEDRIVE_ROOT
SUMMARY_DIR = os.path.join(ONEDRIVE_ROOT, "summary")

# Visualization configuration
# Toggle explanatory tooltips on plots
SHOW_PLOT_TOOLTIPS: bool = True
# Thresholds to highlight samples with massive resistance change
MASSIVE_ABS_R_CHANGE_OHM: float = 5.0   # absolute ΔR threshold in ohms
MASSIVE_FOLD_R_CHANGE: float = 2.0      # fold-change threshold (e.g., 2x, 0.5x)


def add_plot_tooltip(ax: plt.Axes, text: str) -> None:
    """Optionally add an explanatory tooltip-like textbox to a plot.

    The text box is placed in the upper-left of the axes and can be toggled
    using SHOW_PLOT_TOOLTIPS.
    """
    if not SHOW_PLOT_TOOLTIPS:
        return
    try:
        ax.text(
            0.01,
            0.99,
            text,
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=8,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.85, edgecolor="#999"),
        )
    except Exception:
        pass


def find_sample_analysis_dirs() -> List[Tuple[str, str]]:
    """Return list of tuples (sample_name, analysis_dir) for samples that have analysis CSVs."""
    results: List[Tuple[str, str]] = []
    try:
        for entry in sorted(os.listdir(ONEDRIVE_ROOT)):
            if entry in EXCLUDE_SAMPLES:
                continue
            sample_dir = os.path.join(ONEDRIVE_ROOT, entry)
            if not os.path.isdir(sample_dir):
                continue
            analysis_dir = os.path.join(sample_dir, "analysis")
            if os.path.isdir(analysis_dir):
                print(entry)
                # Require at least the summary csv
                cand = os.path.join(analysis_dir, f"ITO_{entry}_summary.csv")
                if os.path.isfile(cand):
                    results.append((entry, analysis_dir))
    except Exception:
        pass
    return results


def load_per_sample_summary(sample: str, analysis_dir: str) -> Optional[pd.DataFrame]:
    path = os.path.join(analysis_dir, f"ITO_{sample}_summary.csv")
    if os.path.isfile(path):
        try:
            df = pd.read_csv(path)
            df["__sample__"] = sample
            return df
        except Exception:
            return None
    return None


def main() -> None:
    os.makedirs(SUMMARY_DIR, exist_ok=True)
    pairs = find_sample_analysis_dirs()
    all_summaries: List[pd.DataFrame] = []

    for sample, analysis_dir in pairs:
        df = load_per_sample_summary(sample, analysis_dir)
        if df is not None and not df.empty:
            all_summaries.append(df)

    if not all_summaries:
        print("No per-sample summary CSVs found.")
        return

    merged = pd.concat(all_summaries, ignore_index=True)

    # Save merged summary CSV
    merged_csv = os.path.join(SUMMARY_DIR, "ITO_all_samples_summary.csv")
    merged.to_csv(merged_csv, index=False)

    # Aggregations: first sweep vs last sweep metrics by sample & section
    # Build per-sample summary tables
    def safe_mean(series: pd.Series) -> float:
        vals = pd.to_numeric(series, errors="coerce")
        return float(vals.mean()) if len(vals) else np.nan

    # Helper to compute average nominal and bound-derived errors
    def avg_with_bounds(df: pd.DataFrame, nom: str, lo: str, hi: str) -> Tuple[float, float, float]:
        v_nom = pd.to_numeric(df.get(nom, pd.Series(dtype=float)), errors="coerce")
        v_lo = pd.to_numeric(df.get(lo, pd.Series(dtype=float)), errors="coerce")
        v_hi = pd.to_numeric(df.get(hi, pd.Series(dtype=float)), errors="coerce")
        avg_nom = float(v_nom.mean()) if len(v_nom) else np.nan
        avg_lo = float(v_lo.mean()) if len(v_lo) else np.nan
        avg_hi = float(v_hi.mean()) if len(v_hi) else np.nan
        err_lo = max(0.0, avg_nom - avg_lo) if np.isfinite(avg_nom) and np.isfinite(avg_lo) else np.nan
        err_hi = max(0.0, avg_hi - avg_nom) if np.isfinite(avg_nom) and np.isfinite(avg_hi) else np.nan
        return avg_nom, err_lo, err_hi

    # Compute per sample overall statistics
    per_sample_stats = []
    for sample, group in merged.groupby("__sample__"):
        first = group[group["sweep_index"] == 1]
        last = group[group["sweep_index"] == 3]
        avg_sigma_start, es_lo_s, es_hi_s = avg_with_bounds(first, "sigma_nominal_Spm", "sigma_lo_Spm", "sigma_hi_Spm")
        avg_sigma_end, es_lo_e, es_hi_e = avg_with_bounds(last, "sigma_nominal_Spm", "sigma_lo_Spm", "sigma_hi_Spm")
        avg_rsheet_start, ers_lo_s, ers_hi_s = avg_with_bounds(first, "Rsheet_nominal_ohm_sq", "Rsheet_lo_ohm_sq", "Rsheet_hi_ohm_sq")
        avg_rsheet_end, ers_lo_e, ers_hi_e = avg_with_bounds(last, "Rsheet_nominal_ohm_sq", "Rsheet_lo_ohm_sq", "Rsheet_hi_ohm_sq")
        avg_rho_start, erho_lo_s, erho_hi_s = avg_with_bounds(first, "rho_nominal_ohm_m", "rho_lo_ohm_m", "rho_hi_ohm_m")
        avg_rho_end, erho_lo_e, erho_hi_e = avg_with_bounds(last, "rho_nominal_ohm_m", "rho_lo_ohm_m", "rho_hi_ohm_m")
        # End resistance stats (avg/min/max)
        r_end_series = pd.to_numeric(last.get("R_neg_m0p5_to_0_ohm", pd.Series(dtype=float)), errors="coerce")
        r_end_avg = float(r_end_series.mean()) if len(r_end_series) else np.nan
        r_end_min = float(r_end_series.min()) if len(r_end_series) else np.nan
        r_end_max = float(r_end_series.max()) if len(r_end_series) else np.nan

        stats = {
            "sample": sample,
            "sections": group["section"].nunique(),
            "avg_R_start_ohm": safe_mean(first["R_pos_0_to_0p5_ohm"]) if "R_pos_0_to_0p5_ohm" in first else np.nan,
            "avg_R_end_ohm": r_end_avg,
            "min_R_end_ohm": r_end_min,
            "max_R_end_ohm": r_end_max,
            "avg_G_start_S": safe_mean(first["G_pos_S"]) if "G_pos_S" in first else np.nan,
            "avg_G_end_S": safe_mean(last["G_neg_S"]) if "G_neg_S" in last else np.nan,
            # Conductivity
            "avg_sigma_start_Spm": avg_sigma_start,
            "avg_sigma_start_err_lo": es_lo_s,
            "avg_sigma_start_err_hi": es_hi_s,
            "avg_sigma_end_Spm": avg_sigma_end,
            "avg_sigma_end_err_lo": es_lo_e,
            "avg_sigma_end_err_hi": es_hi_e,
            # Sheet resistance
            "avg_Rsheet_start_ohm_sq": avg_rsheet_start,
            "avg_Rsheet_start_err_lo": ers_lo_s,
            "avg_Rsheet_start_err_hi": ers_hi_s,
            "avg_Rsheet_end_ohm_sq": avg_rsheet_end,
            "avg_Rsheet_end_err_lo": ers_lo_e,
            "avg_Rsheet_end_err_hi": ers_hi_e,
            # Resistivity
            "avg_rho_start_ohm_m": avg_rho_start,
            "avg_rho_start_err_lo": erho_lo_s,
            "avg_rho_start_err_hi": erho_hi_s,
            "avg_rho_end_ohm_m": avg_rho_end,
            "avg_rho_end_err_lo": erho_lo_e,
            "avg_rho_end_err_hi": erho_hi_e,
        }
        per_sample_stats.append(stats)

    per_sample_df = pd.DataFrame(per_sample_stats)
    per_sample_df.to_csv(os.path.join(SUMMARY_DIR, "ITO_per_sample_stats.csv"), index=False)

    # Compute resistance change metrics per sample (ΔR and fold-change)
    try:
        r_start = pd.to_numeric(per_sample_df.get("avg_R_start_ohm", pd.Series(dtype=float)), errors="coerce")
        r_end = pd.to_numeric(per_sample_df.get("avg_R_end_ohm", pd.Series(dtype=float)), errors="coerce")
        delta_r = r_end - r_start
        with np.errstate(divide='ignore', invalid='ignore'):
            ratio_r = np.where((r_start > 0) & np.isfinite(r_start) & np.isfinite(r_end), r_end / r_start, np.nan)
            log10_fold_r = np.log10(ratio_r)
        per_sample_df["delta_R_ohm"] = delta_r
        per_sample_df["abs_delta_R_ohm"] = np.abs(delta_r)
        per_sample_df["ratio_R_end_over_start"] = ratio_r
        per_sample_df["log10_fold_R"] = log10_fold_r
        # Massive change flag: either absolute ΔR or fold-change exceeds thresholds
        massive_mask = (
            (per_sample_df["abs_delta_R_ohm"] >= float(MASSIVE_ABS_R_CHANGE_OHM)) |
            (np.abs(per_sample_df["log10_fold_R"]) >= np.log10(float(MASSIVE_FOLD_R_CHANGE)))
        )
        per_sample_df["is_massive_change"] = massive_mask.astype(bool)
    except Exception:
        # If anything fails, ensure columns exist
        per_sample_df["delta_R_ohm"] = np.nan
        per_sample_df["abs_delta_R_ohm"] = np.nan
        per_sample_df["ratio_R_end_over_start"] = np.nan
        per_sample_df["log10_fold_R"] = np.nan
        per_sample_df["is_massive_change"] = False

    # Plot: Avg end conductivity with error bars
    plt.figure(figsize=(10, 5))
    ax = plt.gca()
    y = per_sample_df["avg_sigma_end_Spm"].values
    yerr = np.vstack([
        per_sample_df["avg_sigma_end_err_lo"].values,
        per_sample_df["avg_sigma_end_err_hi"].values,
    ])
    plt.bar(per_sample_df["sample"], y, yerr=yerr, capsize=3, color="#4e79a7", label="Avg σ end")
    for name, val in CONDUCTIVITY_THRESHOLDS.items():
        plt.axhline(val, linestyle='--', linewidth=1.0, color={'low':'#999', 'medium':'#666', 'high':'#333'}.get(name, '#888'), label=f"{name}={val:.0e} S/m")
    plt.ylabel("Average end conductivity σ (S/m)")
    plt.title("ITO: Average end conductivity by sample (with bounds)")
    plt.grid(axis='y', linestyle=':', linewidth=0.6)
    plt.legend()
    add_plot_tooltip(ax, "Bars show avg end conductivity with asymmetric bounds. Dashed lines are σ thresholds.")
    plt.tight_layout()
    plt.savefig(os.path.join(SUMMARY_DIR, "ITO_avg_sigma_end_by_sample.png"), dpi=200)
    plt.close()

    # Grouped bars: Avg start vs end conductivity with error bars
    x = np.arange(len(per_sample_df))
    w = 0.42
    plt.figure(figsize=(11, 5))
    ax = plt.gca()
    plt.bar(x - w/2, per_sample_df["avg_sigma_start_Spm"], w,
            yerr=np.vstack([per_sample_df["avg_sigma_start_err_lo"], per_sample_df["avg_sigma_start_err_hi"]]), capsize=3,
            label="Start σ", color="#76b7b2")
    plt.bar(x + w/2, per_sample_df["avg_sigma_end_Spm"], w,
            yerr=np.vstack([per_sample_df["avg_sigma_end_err_lo"], per_sample_df["avg_sigma_end_err_hi"]]), capsize=3,
            label="End σ", color="#e15759")
    for name, val in CONDUCTIVITY_THRESHOLDS.items():
        plt.axhline(val, linestyle='--', linewidth=1.0, color={'low':'#999', 'medium':'#666', 'high':'#333'}.get(name, '#888'))
    plt.xticks(x, per_sample_df["sample"].values)
    plt.ylabel("Conductivity σ (S/m)")
    plt.title("ITO: Avg conductivity start vs end (with bounds)")
    plt.grid(axis='y', linestyle=':', linewidth=0.6)
    plt.legend()
    add_plot_tooltip(ax, "Grouped bars compare start vs end conductivity per sample with bounds and thresholds.")
    plt.tight_layout()
    plt.savefig(os.path.join(SUMMARY_DIR, "ITO_avg_sigma_start_end_by_sample.png"), dpi=200)
    plt.close()

    # Grouped bars: Avg sheet resistance start vs end with error bars
    plt.figure(figsize=(11, 5))
    ax = plt.gca()
    plt.bar(x - w/2, per_sample_df["avg_Rsheet_start_ohm_sq"], w,
            yerr=np.vstack([per_sample_df["avg_Rsheet_start_err_lo"], per_sample_df["avg_Rsheet_start_err_hi"]]), capsize=3,
            label="Start Rs", color="#59a14f")
    plt.bar(x + w/2, per_sample_df["avg_Rsheet_end_ohm_sq"], w,
            yerr=np.vstack([per_sample_df["avg_Rsheet_end_err_lo"], per_sample_df["avg_Rsheet_end_err_hi"]]), capsize=3,
            label="End Rs", color="#edc948")
    plt.xticks(x, per_sample_df["sample"].values)
    plt.ylabel("Sheet resistance Rs (Ω/□)")
    plt.title("ITO: Avg sheet resistance start vs end (with bounds)")
    plt.grid(axis='y', linestyle=':', linewidth=0.6)
    plt.legend()
    add_plot_tooltip(ax, "Sheet resistance comparison for start vs end per sample with error bounds.")
    plt.tight_layout()
    plt.savefig(os.path.join(SUMMARY_DIR, "ITO_avg_rsheet_start_end_by_sample.png"), dpi=200)
    plt.close()

    # Grouped bars: Avg resistivity start vs end with error bars
    plt.figure(figsize=(11, 5))
    ax = plt.gca()
    plt.bar(x - w/2, per_sample_df["avg_rho_start_ohm_m"], w,
            yerr=np.vstack([per_sample_df["avg_rho_start_err_lo"], per_sample_df["avg_rho_start_err_hi"]]), capsize=3,
            label="Start ρ", color="#af7aa1")
    plt.bar(x + w/2, per_sample_df["avg_rho_end_ohm_m"], w,
            yerr=np.vstack([per_sample_df["avg_rho_end_err_lo"], per_sample_df["avg_rho_end_err_hi"]]), capsize=3,
            label="End ρ", color="#ff9da7")
    plt.xticks(x, per_sample_df["sample"].values)
    plt.ylabel("Resistivity ρ (Ω·m)")
    plt.title("ITO: Avg resistivity start vs end (with bounds)")
    plt.grid(axis='y', linestyle=':', linewidth=0.6)
    plt.legend()
    add_plot_tooltip(ax, "Resistivity comparison for start vs end per sample with error bounds.")
    plt.tight_layout()
    plt.savefig(os.path.join(SUMMARY_DIR, "ITO_avg_rho_start_end_by_sample.png"), dpi=200)
    plt.close()

    # Bar: Avg end conductance (no bounds available)
    plt.figure(figsize=(9, 5))
    ax = plt.gca()
    plt.bar(per_sample_df["sample"], per_sample_df["avg_G_end_S"], color="#59a14f")
    plt.ylabel("Average end conductance G (S)")
    plt.title("ITO: Average end conductance by sample")
    plt.grid(axis='y', linestyle=':', linewidth=0.6)
    add_plot_tooltip(ax, "Bars show avg end conductance; no uncertainty bounds available.")
    plt.tight_layout()
    plt.savefig(os.path.join(SUMMARY_DIR, "ITO_avg_G_end_by_sample.png"), dpi=200)
    plt.close()

    # Bar: Avg end resistance with min/max as error bars
    plt.figure(figsize=(10, 5))
    ax = plt.gca()
    y = per_sample_df["avg_R_end_ohm"].values
    y_min = per_sample_df["min_R_end_ohm"].values
    y_max = per_sample_df["max_R_end_ohm"].values
    # compute asymmetric errors; guard against negatives
    err_lo = np.maximum(0.0, y - y_min)
    err_hi = np.maximum(0.0, y_max - y)
    yerr = np.vstack([err_lo, err_hi])
    plt.bar(per_sample_df["sample"], y, yerr=yerr, capsize=3, color="#4e79a7")
    plt.ylabel("Average end resistance R (Ω)")
    plt.title("ITO: Average end resistance by sample (min/max bounds)")
    plt.grid(axis='y', linestyle=':', linewidth=0.6)
    add_plot_tooltip(ax, "Bars show avg end resistance; error bars span min to max across sections.")
    plt.tight_layout()
    plt.savefig(os.path.join(SUMMARY_DIR, "ITO_avg_R_end_by_sample.png"), dpi=200)
    plt.close()

    # Scatter: avg start vs avg end R per sample
    xs = per_sample_df["avg_R_start_ohm"].values
    ys = per_sample_df["avg_R_end_ohm"].values
    samples = per_sample_df["sample"].values
    plt.figure(figsize=(6.5, 6))
    ax = plt.gca()
    plt.loglog(xs, ys, 'o')
    try:
        minv = float(np.nanmin([np.nanmin(xs), np.nanmin(ys)]))
        maxv = float(np.nanmax([np.nanmax(xs), np.nanmax(ys)]))
        if np.isfinite(minv) and np.isfinite(maxv) and maxv > 0 and maxv > minv:
            plt.loglog([minv, maxv], [minv, maxv], '--', color='gray', label='y=x')
    except Exception:
        pass
    for x, y, s in zip(xs, ys, samples):
        if np.isfinite(x) and np.isfinite(y):
            plt.annotate(s, (x, y), textcoords="offset points", xytext=(4, 2), fontsize=8)
    plt.xlabel("Avg start R (Ohm)")
    plt.ylabel("Avg end R (Ohm)")
    plt.title("ITO: Avg start vs end resistance per sample")
    plt.grid(True, which='both', linestyle=':', linewidth=0.6)
    plt.legend()
    add_plot_tooltip(ax, "Log–log scatter of avg start vs end resistance; y=x line indicates no change.")
    plt.tight_layout()
    plt.savefig(os.path.join(SUMMARY_DIR, "ITO_avg_R_start_vs_end_scatter.png"), dpi=200)
    plt.close()

    # Slopegraph: start → end average resistance per sample (highlight massive changes)
    try:
        plt.figure(figsize=(8.5, 6))
        ax = plt.gca()
        x_positions = [0, 1]
        for _, row in per_sample_df.iterrows():
            r_s = row.get("avg_R_start_ohm", np.nan)
            r_e = row.get("avg_R_end_ohm", np.nan)
            if not (np.isfinite(r_s) and np.isfinite(r_e) and r_s > 0 and r_e > 0):
                continue
            color = "#e15759" if bool(row.get("is_massive_change", False)) else "#999999"
            lw = 2.2 if bool(row.get("is_massive_change", False)) else 1.3
            ax.plot(x_positions, [r_s, r_e], color=color, linewidth=lw, alpha=0.9)
            if bool(row.get("is_massive_change", False)):
                # Annotate massive ones near the end point
                ax.annotate(str(row.get("sample", "")), (1.01, r_e), xycoords=("data", "data"), textcoords="offset points", xytext=(2, 0), fontsize=8, color=color)
        ax.set_yscale('log')
        ax.set_xlim(-0.05, 1.15)
        ax.set_xticks(x_positions)
        ax.set_xticklabels(["Start", "End"])
        ax.set_ylabel("Average resistance R (Ω)")
        ax.set_title("ITO: Start→End resistance slopegraph (avg per sample)")
        ax.grid(True, which='both', linestyle=':', linewidth=0.6, axis='y')
        add_plot_tooltip(ax, "Lines connect avg R at start and end per sample (log-scale). Red highlights ‘massive’ changes.")
        plt.tight_layout()
        plt.savefig(os.path.join(SUMMARY_DIR, "ITO_R_slopegraph_start_to_end.png"), dpi=200)
        plt.close()
    except Exception:
        pass

    # Ranked lollipop: absolute ΔR per sample (highlight massive changes)
    try:
        df_sorted = per_sample_df.sort_values(["abs_delta_R_ohm", "sample"], ascending=[False, True]).reset_index(drop=True)
        n = len(df_sorted)
        if n > 0:
            height = max(6.0, min(0.28 * n + 2.0, 14.0))
            plt.figure(figsize=(9.5, height))
            ax = plt.gca()
            y = np.arange(n)
            x = df_sorted["delta_R_ohm"].values
            colors = np.where(df_sorted["is_massive_change"].values, "#e15759", "#4e79a7")
            # stems
            for yi, xi, ci in zip(y, x, colors):
                ax.hlines(yi, 0, xi, color=ci, linewidth=1.5, alpha=0.9)
            ax.plot(x, y, 'o', color="#333333", markersize=4)
            ax.axvline(0, color="#777", linestyle='--', linewidth=1.0)
            ax.set_yticks(y)
            ax.set_yticklabels(df_sorted["sample"].values, fontsize=8)
            ax.set_xlabel("ΔR = R_end − R_start (Ω)")
            ax.set_title("ITO: Ranked ΔR per sample (lollipop)")
            ax.grid(True, axis='x', linestyle=':', linewidth=0.6)
            add_plot_tooltip(ax, "Horizontal stems show change in avg resistance. Right = increase, left = decrease. Red = ‘massive’.")
            plt.tight_layout()
            plt.savefig(os.path.join(SUMMARY_DIR, "ITO_delta_R_by_sample_lollipop.png"), dpi=200)
            plt.close()
    except Exception:
        pass

    # Ranked lollipop: log10 fold-change in R (End/Start)
    try:
        df_sorted = per_sample_df.copy()
        # Replace inf/NaN to avoid sorting issues
        v = pd.to_numeric(df_sorted.get("log10_fold_R", pd.Series(dtype=float)), errors="coerce")
        df_sorted["log10_fold_R_clean"] = np.where(np.isfinite(v), v, np.nan)
        df_sorted = df_sorted.sort_values(["log10_fold_R_clean", "sample"], ascending=[False, True]).reset_index(drop=True)
        n = len(df_sorted)
        if n > 0:
            height = max(6.0, min(0.28 * n + 2.0, 14.0))
            plt.figure(figsize=(9.5, height))
            ax = plt.gca()
            y = np.arange(n)
            x = df_sorted["log10_fold_R_clean"].values
            colors = np.where(df_sorted["is_massive_change"].values, "#e15759", "#59a14f")
            for yi, xi, ci in zip(y, x, colors):
                if np.isfinite(xi):
                    ax.hlines(yi, 0, xi, color=ci, linewidth=1.5, alpha=0.9)
            ax.plot(np.where(np.isfinite(x), x, np.nan), y, 'o', color="#333333", markersize=4)
            ax.axvline(0, color="#777", linestyle='--', linewidth=1.0)
            ax.set_yticks(y)
            ax.set_yticklabels(df_sorted["sample"].values, fontsize=8)
            ax.set_xlabel("log10(R_end / R_start)")
            ax.set_title("ITO: Ranked log10 fold-change in R per sample")
            ax.grid(True, axis='x', linestyle=':', linewidth=0.6)
            add_plot_tooltip(ax, "Positive = higher end resistance, negative = lower. Magnitude shows fold-change (log10 scale). Red = ‘massive’.")
            plt.tight_layout()
            plt.savefig(os.path.join(SUMMARY_DIR, "ITO_logfold_R_by_sample_lollipop.png"), dpi=200)
            plt.close()
    except Exception:
        pass

    # Scatter: start R vs ΔR (highlight massive changes)
    try:
        plt.figure(figsize=(7.5, 6))
        ax = plt.gca()
        xs = per_sample_df["avg_R_start_ohm"].values
        ys = per_sample_df["delta_R_ohm"].values
        mask_massive = per_sample_df["is_massive_change"].values
        ax.scatter(xs[~mask_massive], ys[~mask_massive], c="#4e79a7", alpha=0.8, label="Normal")
        ax.scatter(xs[mask_massive], ys[mask_massive], c="#e15759", alpha=0.9, label="Massive")
        # Annotate massive samples
        for x, y, s, m in zip(xs, ys, per_sample_df["sample"].values, mask_massive):
            if m and np.isfinite(x) and np.isfinite(y):
                ax.annotate(str(s), (x, y), textcoords="offset points", xytext=(4, 2), fontsize=8, color="#e15759")
        ax.set_xscale('log')
        ax.axhline(0, color="#777", linestyle='--', linewidth=1.0)
        ax.set_xlabel("Avg start R (Ω)")
        ax.set_ylabel("ΔR = R_end − R_start (Ω)")
        ax.set_title("ITO: Start R vs ΔR (avg per sample)")
        ax.grid(True, which='both', linestyle=':', linewidth=0.6)
        ax.legend()
        add_plot_tooltip(ax, "Relationship between starting resistance and change. Points in red exceed ‘massive’ thresholds.")
        plt.tight_layout()
        plt.savefig(os.path.join(SUMMARY_DIR, "ITO_R_start_vs_delta_scatter.png"), dpi=200)
        plt.close()
    except Exception:
        pass
    # Per-section cross-sample plots: σ_end by sample for each section (sweep 3)
    try:
        last = merged[merged.get("sweep_index") == 3].copy()
        last["sigma_nominal_Spm"] = pd.to_numeric(last.get("sigma_nominal_Spm", pd.Series(dtype=float)), errors="coerce")
        sections = sorted([s for s in last["section"].dropna().unique() if isinstance(s, str)])
        samples_order = sorted(per_sample_df["sample"].unique())
        if sections and samples_order:
            cols = 4
            rows = int(np.ceil(len(sections) / cols))
            fig, axes = plt.subplots(rows, cols, figsize=(cols*4.2, rows*3.6))
            axes = np.atleast_2d(axes)
            for idx, sec in enumerate(sections):
                r = idx // cols
                c = idx % cols
                ax = axes[r, c]
                sub = last[last["section"] == sec].groupby("__sample__")["sigma_nominal_Spm"].mean()
                y = [sub.get(s, np.nan) for s in samples_order]
                ax.bar(samples_order, y, color="#4e79a7")
                for name, val in CONDUCTIVITY_THRESHOLDS.items():
                    ax.axhline(val, linestyle='--', linewidth=0.8, color={'low':'#999', 'medium':'#666', 'high':'#333'}.get(name, '#888'))
                ax.set_title(f"Section {sec}", fontsize=9)
                ax.tick_params(axis='x', labelrotation=90, labelsize=7)
                if idx == 0:
                    add_plot_tooltip(ax, "Per section: bars show mean end σ by sample with thresholds.")
            # hide any extra axes
            for idx in range(len(sections), rows*cols):
                r = idx // cols
                c = idx % cols
                axes[r, c].axis('off')
            plt.tight_layout()
            plt.savefig(os.path.join(SUMMARY_DIR, "ITO_sigma_end_by_sample_per_section.png"), dpi=180)
            plt.close(fig)
    except Exception:
        pass

    # Correlation plots at end (sweep 3): σ_end vs Rsheet_end, σ_end vs R_end
    try:
        last = merged[merged.get("sweep_index") == 3].copy()
        sig = pd.to_numeric(last.get("sigma_nominal_Spm", pd.Series(dtype=float)), errors="coerce")
        rs = pd.to_numeric(last.get("Rsheet_nominal_ohm_sq", pd.Series(dtype=float)), errors="coerce")
        r_end = pd.to_numeric(last.get("R_neg_m0p5_to_0_ohm", pd.Series(dtype=float)), errors="coerce")
        # σ vs Rsheet
        plt.figure(figsize=(6.5, 6))
        ax = plt.gca()
        plt.loglog(sig, rs, 'o', alpha=0.7)
        plt.xlabel("σ_end (S/m)")
        plt.ylabel("Rsheet_end (Ω/□)")
        plt.title("ITO: σ_end vs Rsheet_end (sweep 3)")
        plt.grid(True, which='both', linestyle=':', linewidth=0.6)
        add_plot_tooltip(ax, "Expected inverse relation: higher σ typically corresponds to lower Rs.")
        plt.tight_layout()
        plt.savefig(os.path.join(SUMMARY_DIR, "ITO_corr_sigma_vs_rsheet_end.png"), dpi=200)
        plt.close()
        # σ vs R_end
        plt.figure(figsize=(6.5, 6))
        ax = plt.gca()
        plt.loglog(sig, r_end, 'o', alpha=0.7)
        plt.xlabel("σ_end (S/m)")
        plt.ylabel("R_end (Ω)")
        plt.title("ITO: σ_end vs R_end (sweep 3)")
        plt.grid(True, which='both', linestyle=':', linewidth=0.6)
        add_plot_tooltip(ax, "How end conductivity relates to end resistance across sections.")
        plt.tight_layout()
        plt.savefig(os.path.join(SUMMARY_DIR, "ITO_corr_sigma_vs_r_end.png"), dpi=200)
        plt.close()
    except Exception:
        pass

    # Distributions across samples for end metrics: box/violin
    try:
        last = merged[merged.get("sweep_index") == 3].copy()
        metrics = {
            "R_end (Ω)": pd.to_numeric(last.get("R_neg_m0p5_to_0_ohm", pd.Series(dtype=float)), errors="coerce"),
            "G_end (S)": pd.to_numeric(last.get("G_neg_S", pd.Series(dtype=float)), errors="coerce"),
            "σ_end (S/m)": pd.to_numeric(last.get("sigma_nominal_Spm", pd.Series(dtype=float)), errors="coerce"),
            "Rs_end (Ω/□)": pd.to_numeric(last.get("Rsheet_nominal_ohm_sq", pd.Series(dtype=float)), errors="coerce"),
            "ρ_end (Ω·m)": pd.to_numeric(last.get("rho_nominal_ohm_m", pd.Series(dtype=float)), errors="coerce"),
        }
        # Boxplot figure
        labels = list(metrics.keys())
        data = [v.dropna().values for v in metrics.values()]
        plt.figure(figsize=(11, 5))
        ax = plt.gca()
        plt.boxplot(data, showfliers=True)
        plt.xticks(np.arange(1, len(labels)+1), labels, rotation=0)
        plt.yscale('log')
        plt.grid(True, axis='y', linestyle=':', linewidth=0.6)
        plt.title("ITO: End-metric distributions (box, log-scale)")
        add_plot_tooltip(ax, "Boxplots summarize end-metric distributions across all samples/sections (log-scale).")
        plt.tight_layout()
        plt.savefig(os.path.join(SUMMARY_DIR, "ITO_end_metric_boxplots.png"), dpi=200)
        plt.close()
        # Violin figure
        plt.figure(figsize=(11, 5))
        ax = plt.gca()
        plt.violinplot(data, showmeans=True, showextrema=True, showmedians=True)
        plt.xticks(np.arange(1, len(labels)+1), labels, rotation=0)
        plt.yscale('log')
        plt.grid(True, axis='y', linestyle=':', linewidth=0.6)
        plt.title("ITO: End-metric distributions (violin, log-scale)")
        add_plot_tooltip(ax, "Violins show full distribution shapes with mean/median markers (log-scale).")
        plt.tight_layout()
        plt.savefig(os.path.join(SUMMARY_DIR, "ITO_end_metric_violins.png"), dpi=200)
        plt.close()
    except Exception:
        pass

    # Trend by sample order (lexicographic) for avg end metrics
    try:
        order = per_sample_df.sort_values("sample")["sample"].values
        idx = np.arange(len(order))
        # Series
        y_sigma = per_sample_df.set_index("sample").loc[order, "avg_sigma_end_Spm"].values
        y_R = per_sample_df.set_index("sample").loc[order, "avg_R_end_ohm"].values
        y_Rs = per_sample_df.set_index("sample").loc[order, "avg_Rsheet_end_ohm_sq"].values
        y_rho = per_sample_df.set_index("sample").loc[order, "avg_rho_end_ohm_m"].values
        y_G = per_sample_df.set_index("sample").loc[order, "avg_G_end_S"].values
        fig, axes = plt.subplots(2, 3, figsize=(13, 7))
        axes = np.atleast_2d(axes)
        def plot_tr(ax, y, title, logy=False, color="#4e79a7"):
            ax.plot(idx, y, "-o", color=color, markersize=4)
            ax.set_xticks(idx)
            ax.set_xticklabels(order, rotation=90, fontsize=7)
            ax.set_title(title)
            if logy:
                ax.set_yscale('log')
            ax.grid(True, linestyle=':', linewidth=0.6)
        plot_tr(axes[0,0], y_sigma, "Avg σ_end", False, "#4e79a7")
        plot_tr(axes[0,1], y_G, "Avg G_end", False, "#59a14f")
        plot_tr(axes[0,2], y_R, "Avg R_end", True, "#f28e2b")
        plot_tr(axes[1,0], y_Rs, "Avg Rs_end", True, "#edc948")
        plot_tr(axes[1,1], y_rho, "Avg ρ_end", True, "#af7aa1")
        axes[1,2].axis('off')
        add_plot_tooltip(axes[0,0], "Trends across samples (lexicographic order) for end metrics; some use log y.")
        plt.tight_layout()
        plt.savefig(os.path.join(SUMMARY_DIR, "ITO_trends_by_sample_order.png"), dpi=200)
        plt.close(fig)
    except Exception:
        pass

    # ECDF and CCDF for end metrics
    try:
        last = merged[merged.get("sweep_index") == 3].copy()
        metrics = {
            "R_end (Ω)": pd.to_numeric(last.get("R_neg_m0p5_to_0_ohm", pd.Series(dtype=float)), errors="coerce"),
            "G_end (S)": pd.to_numeric(last.get("G_neg_S", pd.Series(dtype=float)), errors="coerce"),
            "σ_end (S/m)": pd.to_numeric(last.get("sigma_nominal_Spm", pd.Series(dtype=float)), errors="coerce"),
            "Rs_end (Ω/□)": pd.to_numeric(last.get("Rsheet_nominal_ohm_sq", pd.Series(dtype=float)), errors="coerce"),
            "ρ_end (Ω·m)": pd.to_numeric(last.get("rho_nominal_ohm_m", pd.Series(dtype=float)), errors="coerce"),
        }
        labels = list(metrics.keys())
        data = [v.dropna().values for v in metrics.values()]
        # ECDF
        cols = 3
        rows = int(np.ceil(len(labels)/cols))
        fig, axes = plt.subplots(rows, cols, figsize=(cols*4.2, rows*3.6))
        axes = np.atleast_2d(axes)
        for idx, (lab, arr) in enumerate(zip(labels, data)):
            r = idx // cols
            c = idx % cols
            ax = axes[r, c]
            if arr.size > 0:
                arr_sorted = np.sort(arr)
                y = np.arange(1, arr_sorted.size+1) / arr_sorted.size
                ax.plot(arr_sorted, y, '-')
                ax.set_xscale('log')
            ax.set_title(f"ECDF {lab}", fontsize=9)
            ax.grid(True, linestyle=':', linewidth=0.6)
            if idx == 0:
                add_plot_tooltip(ax, "Empirical CDF of end metrics on log x-axis; shows distribution percentiles.")
        for idx in range(len(labels), rows*cols):
            r = idx // cols
            c = idx % cols
            axes[r, c].axis('off')
        plt.tight_layout()
        plt.savefig(os.path.join(SUMMARY_DIR, "ITO_end_metrics_ECDF.png"), dpi=200)
        plt.close(fig)
        # CCDF
        fig, axes = plt.subplots(rows, cols, figsize=(cols*4.2, rows*3.6))
        axes = np.atleast_2d(axes)
        for idx, (lab, arr) in enumerate(zip(labels, data)):
            r = idx // cols
            c = idx % cols
            ax = axes[r, c]
            if arr.size > 0:
                arr_sorted = np.sort(arr)
                y = 1.0 - (np.arange(1, arr_sorted.size+1) / arr_sorted.size)
                ax.plot(arr_sorted, y, '-')
                ax.set_xscale('log')
                ax.set_yscale('log')
            ax.set_title(f"CCDF {lab}", fontsize=9)
            ax.grid(True, which='both', linestyle=':', linewidth=0.6)
            if idx == 0:
                add_plot_tooltip(ax, "Complementary CDF on log–log; emphasizes tail behavior of metrics.")
        for idx in range(len(labels), rows*cols):
            r = idx // cols
            c = idx % cols
            axes[r, c].axis('off')
        plt.tight_layout()
        plt.savefig(os.path.join(SUMMARY_DIR, "ITO_end_metrics_CCDF.png"), dpi=200)
        plt.close(fig)
    except Exception:
        pass

    # Correlation heatmaps (Pearson and Spearman) for end metrics
    try:
        last = merged[merged.get("sweep_index") == 3].copy()
        dfm = pd.DataFrame({
            "R_end (Ω)": pd.to_numeric(last.get("R_neg_m0p5_to_0_ohm", pd.Series(dtype=float)), errors="coerce"),
            "G_end (S)": pd.to_numeric(last.get("G_neg_S", pd.Series(dtype=float)), errors="coerce"),
            "σ_end (S/m)": pd.to_numeric(last.get("sigma_nominal_Spm", pd.Series(dtype=float)), errors="coerce"),
            "Rs_end (Ω/□)": pd.to_numeric(last.get("Rsheet_nominal_ohm_sq", pd.Series(dtype=float)), errors="coerce"),
            "ρ_end (Ω·m)": pd.to_numeric(last.get("rho_nominal_ohm_m", pd.Series(dtype=float)), errors="coerce"),
        })
        dfm = dfm.replace([np.inf, -np.inf], np.nan).dropna(how='all')
        def plot_corr(mat: np.ndarray, labels: List[str], title: str, out_name: str) -> None:
            plt.figure(figsize=(6.2, 5.6))
            ax = plt.gca()
            im = ax.imshow(mat, vmin=-1, vmax=1, cmap="coolwarm")
            ax.set_xticks(np.arange(len(labels)))
            ax.set_yticks(np.arange(len(labels)))
            ax.set_xticklabels(labels, rotation=45, ha='right')
            ax.set_yticklabels(labels)
            for i in range(len(labels)):
                for j in range(len(labels)):
                    val = mat[i, j]
                    ax.text(j, i, f"{val:.2f}", ha='center', va='center', color='black', fontsize=8)
            ax.set_title(title)
            plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label='corr')
            ax.grid(False)
            add_plot_tooltip(ax, "Correlation matrix among end metrics; values in [-1,1].")
            plt.tight_layout()
            plt.savefig(os.path.join(SUMMARY_DIR, out_name), dpi=200)
            plt.close()
        if not dfm.empty:
            pear = dfm.corr(method='pearson').values
            spear = dfm.corr(method='spearman').values
            labels = list(dfm.columns)
            plot_corr(pear, labels, "ITO: Pearson correlation (end metrics)", "ITO_corr_heatmap_pearson.png")
            plot_corr(spear, labels, "ITO: Spearman correlation (end metrics)", "ITO_corr_heatmap_spearman.png")
    except Exception:
        pass

    # Hexbin density plots for σ_end relations
    try:
        last = merged[merged.get("sweep_index") == 3].copy()
        sig = pd.to_numeric(last.get("sigma_nominal_Spm", pd.Series(dtype=float)), errors="coerce")
        rs = pd.to_numeric(last.get("Rsheet_nominal_ohm_sq", pd.Series(dtype=float)), errors="coerce")
        r_end = pd.to_numeric(last.get("R_neg_m0p5_to_0_ohm", pd.Series(dtype=float)), errors="coerce")
        # σ vs Rs
        plt.figure(figsize=(6.5, 6))
        ax = plt.gca()
        hb = ax.hexbin(sig, rs, gridsize=40, xscale='log', yscale='log', bins='log', cmap='viridis', mincnt=1)
        ax.set_xlabel("σ_end (S/m)")
        ax.set_ylabel("Rsheet_end (Ω/□)")
        ax.set_title("ITO: Density σ_end vs Rs_end (hexbin)")
        cb = plt.colorbar(hb, ax=ax)
        cb.set_label('log10(count)')
        add_plot_tooltip(ax, "Hexbin density (log–log) reduces overplotting; darker = more sections.")
        plt.tight_layout()
        plt.savefig(os.path.join(SUMMARY_DIR, "ITO_hexbin_sigma_vs_rsheet_end.png"), dpi=200)
        plt.close()
        # σ vs R_end
        plt.figure(figsize=(6.5, 6))
        ax = plt.gca()
        hb = ax.hexbin(sig, r_end, gridsize=40, xscale='log', yscale='log', bins='log', cmap='viridis', mincnt=1)
        ax.set_xlabel("σ_end (S/m)")
        ax.set_ylabel("R_end (Ω)")
        ax.set_title("ITO: Density σ_end vs R_end (hexbin)")
        cb = plt.colorbar(hb, ax=ax)
        cb.set_label('log10(count)')
        add_plot_tooltip(ax, "Hexbin density (log–log) for σ vs end resistance across sections.")
        plt.tight_layout()
        plt.savefig(os.path.join(SUMMARY_DIR, "ITO_hexbin_sigma_vs_r_end.png"), dpi=200)
        plt.close()
    except Exception:
        pass

    # Section pass/fail grid by σ thresholds
    try:
        last = merged[merged.get("sweep_index") == 3].copy()
        last["sigma_nominal_Spm"] = pd.to_numeric(last.get("sigma_nominal_Spm", pd.Series(dtype=float)), errors="coerce")
        sections = sorted([s for s in last["section"].dropna().unique() if isinstance(s, str)])
        samples = sorted([s for s in last["__sample__"].dropna().unique() if isinstance(s, str)])
        if sections and samples:
            thresh_items = sorted(CONDUCTIVITY_THRESHOLDS.items(), key=lambda kv: kv[1])
            thresholds = [v for _, v in thresh_items]
            # Compute band index per (sample, section)
            grid = np.zeros((len(samples), len(sections)), dtype=float)
            for i, samp in enumerate(samples):
                for j, sec in enumerate(sections):
                    val = last[(last["__sample__"] == samp) & (last["section"] == sec)]["sigma_nominal_Spm"].mean()
                    if not np.isfinite(val):
                        grid[i, j] = np.nan
                    else:
                        band = 0
                        for t in thresholds:
                            if val >= t:
                                band += 1
                        grid[i, j] = band  # 0..len(thresholds)
            plt.figure(figsize=(max(6.5, 0.25*len(sections)+3), max(6.0, 0.25*len(samples)+2)))
            ax = plt.gca()
            im = ax.imshow(grid, aspect='auto', interpolation='nearest', cmap='YlGn', vmin=0, vmax=len(thresholds))
            ax.set_xticks(np.arange(len(sections)))
            ax.set_yticks(np.arange(len(samples)))
            ax.set_xticklabels(sections, rotation=90, fontsize=7)
            ax.set_yticklabels(samples, fontsize=8)
            ax.set_xlabel("Section")
            ax.set_ylabel("Sample")
            ax.set_title("ITO: Section pass/fail grid by σ thresholds (end)")
            cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
            cbar.set_label("# thresholds met")
            add_plot_tooltip(ax, "Grid shows, per section/sample, how many σ thresholds are met at end.")
            plt.tight_layout()
            plt.savefig(os.path.join(SUMMARY_DIR, "ITO_section_passfail_grid_sigma_end.png"), dpi=200)
            plt.close()
    except Exception:
        pass

    # Compliance rate stacked bars per sample
    try:
        last = merged[merged.get("sweep_index") == 3].copy()
        last["sigma_nominal_Spm"] = pd.to_numeric(last.get("sigma_nominal_Spm", pd.Series(dtype=float)), errors="coerce")
        samples = sorted([s for s in last["__sample__"].dropna().unique() if isinstance(s, str)])
        thresh_items = sorted(CONDUCTIVITY_THRESHOLDS.items(), key=lambda kv: kv[1])
        thresholds = [v for _, v in thresh_items]
        bands = [name for name, _ in thresh_items] + ["above_high"]
        counts = {b: [] for b in bands}
        for samp in samples:
            vals = last[last["__sample__"] == samp]["sigma_nominal_Spm"].dropna().values
            if vals.size == 0:
                for b in bands:
                    counts[b].append(0)
                continue
            band_idx = np.zeros(vals.shape[0], dtype=int)
            for k, t in enumerate(thresholds):
                band_idx += (vals >= t).astype(int)
            # Convert to categories matching bands length
            total = float(vals.size)
            for k in range(len(bands)):
                counts[bands[k]].append(float(np.sum(band_idx == k)) / total)
        # Plot stacked bars
        plt.figure(figsize=(max(10.0, 0.35*len(samples)+4), 5.0))
        ax = plt.gca()
        x = np.arange(len(samples))
        bottom = np.zeros(len(samples))
        colors = ["#d62728", "#ff7f0e", "#2ca02c", "#1f77b4"][:len(bands)]
        for b, col in zip(bands, colors):
            vals = np.array(counts[b])
            ax.bar(x, vals, bottom=bottom, color=col, label=b)
            bottom += vals
        ax.set_xticks(x)
        ax.set_xticklabels(samples, rotation=90, fontsize=8)
        ax.set_ylabel("Fraction of sections")
        ax.set_title("ITO: Compliance rate by sample (σ thresholds at end)")
        ax.legend(loc='upper right', fontsize=8)
        ax.grid(True, axis='y', linestyle=':', linewidth=0.6)
        add_plot_tooltip(ax, "Stacked bars show fraction of sections meeting each σ threshold band per sample.")
        plt.tight_layout()
        plt.savefig(os.path.join(SUMMARY_DIR, "ITO_compliance_rate_by_sample.png"), dpi=200)
        plt.close()
    except Exception:
        pass

    # Section-level variability (CV) bars per sample for σ_end
    try:
        last = merged[merged.get("sweep_index") == 3].copy()
        last["sigma_nominal_Spm"] = pd.to_numeric(last.get("sigma_nominal_Spm", pd.Series(dtype=float)), errors="coerce")
        cv_list = []
        for samp, grp in last.groupby("__sample__"):
            vals = grp["sigma_nominal_Spm"].dropna().values
            if vals.size >= 2 and np.nanmean(vals) > 0:
                cv = float(np.nanstd(vals, ddof=1) / np.nanmean(vals))
            else:
                cv = np.nan
            cv_list.append((samp, cv))
        if cv_list:
            names = [s for s, _ in cv_list]
            cvs = np.array([v for _, v in cv_list])
            order = np.argsort(-np.nan_to_num(cvs, nan=-np.inf))
            names = [names[i] for i in order]
            cvs = cvs[order]
            plt.figure(figsize=(max(10.0, 0.3*len(names)+4), 5.0))
            ax = plt.gca()
            ax.bar(names, cvs, color="#4e79a7")
            ax.set_ylabel("CV of σ_end (std/mean)")
            ax.set_title("ITO: Section-level variability per sample (σ_end)")
            ax.grid(True, axis='y', linestyle=':', linewidth=0.6)
            ax.tick_params(axis='x', rotation=90, labelsize=8)
            add_plot_tooltip(ax, "Coefficient of variation across sections: higher = more variability.")
            plt.tight_layout()
            plt.savefig(os.path.join(SUMMARY_DIR, "ITO_sigma_end_variability_CV_by_sample.png"), dpi=200)
            plt.close()
    except Exception:
        pass

    # Per-section jitter plot for σ_end by sample
    try:
        last = merged[merged.get("sweep_index") == 3].copy()
        last["sigma_nominal_Spm"] = pd.to_numeric(last.get("sigma_nominal_Spm", pd.Series(dtype=float)), errors="coerce")
        samples = sorted([s for s in last["__sample__"].dropna().unique() if isinstance(s, str)])
        x = np.arange(len(samples))
        plt.figure(figsize=(max(10.0, 0.35*len(samples)+4), 6.0))
        ax = plt.gca()
        for i, s in enumerate(samples):
            vals = last[last["__sample__"] == s]["sigma_nominal_Spm"].dropna().values
            if vals.size == 0:
                continue
            jitter = (np.random.rand(vals.size) - 0.5) * 0.5
            ax.scatter(np.full(vals.size, x[i]) + jitter, vals, alpha=0.7, s=12, color="#4e79a7")
        ax.set_yscale('log')
        ax.set_xticks(x)
        ax.set_xticklabels(samples, rotation=90, fontsize=8)
        ax.set_ylabel("σ_end (S/m)")
        ax.set_title("ITO: Per-section σ_end by sample (jittered)")
        ax.grid(True, which='both', linestyle=':', linewidth=0.6)
        add_plot_tooltip(ax, "Jittered points show section-level σ_end per sample (log y).")
        plt.tight_layout()
        plt.savefig(os.path.join(SUMMARY_DIR, "ITO_sigma_end_per_section_jitter.png"), dpi=200)
        plt.close()
    except Exception:
        pass

    # Sweep trajectories for σ and Rs (1→3) with arrows on log–log axes
    try:
        sweeps = merged.copy()
        sweeps["sigma_nominal_Spm"] = pd.to_numeric(sweeps.get("sigma_nominal_Spm", pd.Series(dtype=float)), errors="coerce")
        sweeps["Rsheet_nominal_ohm_sq"] = pd.to_numeric(sweeps.get("Rsheet_nominal_ohm_sq", pd.Series(dtype=float)), errors="coerce")
        # Aggregate per sample, per sweep
        agg = sweeps.groupby(["__sample__", "sweep_index"])[["sigma_nominal_Spm", "Rsheet_nominal_ohm_sq"]].mean().reset_index()
        samples = sorted(agg["__sample__"].unique())
        plt.figure(figsize=(7.8, 6.2))
        ax = plt.gca()
        for s in samples:
            sub = agg[agg["__sample__"] == s]
            if {1, 3}.issubset(set(sub["sweep_index"])):
                p1 = sub[sub["sweep_index"] == 1][["sigma_nominal_Spm", "Rsheet_nominal_ohm_sq"]].values.squeeze()
                p3 = sub[sub["sweep_index"] == 3][["sigma_nominal_Spm", "Rsheet_nominal_ohm_sq"]].values.squeeze()
                if np.all(np.isfinite(p1)) and np.all(np.isfinite(p3)) and np.all(p1 > 0) and np.all(p3 > 0):
                    ax.plot([p1[0], p3[0]], [p1[1], p3[1]], '-', color="#4e79a7", alpha=0.7)
                    ax.annotate("", xy=(p3[0], p3[1]), xytext=(p1[0], p1[1]),
                                arrowprops=dict(arrowstyle="->", color="#4e79a7", lw=1.4, alpha=0.8))
        ax.set_xscale('log')
        ax.set_yscale('log')
        ax.set_xlabel("σ (S/m)")
        ax.set_ylabel("Rs (Ω/□)")
        ax.set_title("ITO: Sweep trajectories (1→3) in σ vs Rs")
        ax.grid(True, which='both', linestyle=':', linewidth=0.6)
        add_plot_tooltip(ax, "Arrows show average trajectory from sweep 1 to 3 in (σ, Rs) space.")
        plt.tight_layout()
        plt.savefig(os.path.join(SUMMARY_DIR, "ITO_sweep_trajectories_sigma_vs_rsheet.png"), dpi=200)
        plt.close()
    except Exception:
        pass

    # Multi-figure dashboard of summary plots
    try:
        import matplotlib.image as mpimg
        files = [
            "ITO_avg_sigma_end_by_sample.png",
            "ITO_avg_sigma_start_end_by_sample.png",
            "ITO_avg_rsheet_start_end_by_sample.png",
            "ITO_avg_rho_start_end_by_sample.png",
            "ITO_avg_G_end_by_sample.png",
            "ITO_avg_R_end_by_sample.png",
            "ITO_avg_R_start_vs_end_scatter.png",
            "ITO_R_slopegraph_start_to_end.png",
            "ITO_delta_R_by_sample_lollipop.png",
            "ITO_logfold_R_by_sample_lollipop.png",
            "ITO_R_start_vs_delta_scatter.png",
            "ITO_end_metrics_ECDF.png",
            "ITO_end_metrics_CCDF.png",
            "ITO_corr_heatmap_pearson.png",
            "ITO_corr_heatmap_spearman.png",
            "ITO_hexbin_sigma_vs_rsheet_end.png",
            "ITO_hexbin_sigma_vs_r_end.png",
            "ITO_section_passfail_grid_sigma_end.png",
            "ITO_compliance_rate_by_sample.png",
            "ITO_sigma_end_variability_CV_by_sample.png",
            "ITO_sigma_end_per_section_jitter.png",
            "ITO_sweep_trajectories_sigma_vs_rsheet.png",
            "ITO_sigma_end_by_sample_per_section.png",
            "ITO_corr_sigma_vs_rsheet_end.png",
            "ITO_corr_sigma_vs_r_end.png",
            "ITO_end_metric_boxplots.png",
            "ITO_end_metric_violins.png",
            "ITO_trends_by_sample_order.png",
        ]
        paths = [os.path.join(SUMMARY_DIR, f) for f in files if os.path.isfile(os.path.join(SUMMARY_DIR, f))]
        if paths:
            cols = 2
            rows = int(np.ceil(len(paths)/cols))
            fig, axes = plt.subplots(rows, cols, figsize=(cols*5.5, rows*4.5))
            axes = np.atleast_2d(axes)
            for idx, p in enumerate(paths):
                r = idx // cols
                c = idx % cols
                ax = axes[r, c]
                img = mpimg.imread(p)
                ax.imshow(img)
                ax.set_title(os.path.basename(p), fontsize=8)
                ax.axis('off')
            for idx in range(len(paths), rows*cols):
                r = idx // cols
                c = idx % cols
                axes[r, c].axis('off')
            plt.tight_layout()
            plt.savefig(os.path.join(SUMMARY_DIR, "ITO_all_samples_dashboard.png"), dpi=180)
            plt.close(fig)
    except Exception:
        pass

    # Excel workbook with merged and per-sample stats
    try:
        xlsx_path = os.path.join(SUMMARY_DIR, "ITO_all_samples_summary.xlsx")
        with pd.ExcelWriter(xlsx_path, engine="xlsxwriter") as writer:
            merged.to_excel(writer, sheet_name="merged", index=False)
            per_sample_df.to_excel(writer, sheet_name="per_sample_stats", index=False)
    except Exception:
        pass


if __name__ == "__main__":
    main()
