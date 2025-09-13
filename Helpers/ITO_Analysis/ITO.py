import os
import re
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# Root directory on OneDrive that contains the ITO sample folders (e.g., "5-ITO")
ONEDRIVE_ROOT = r"C:\Users\Craig-Desktop\OneDrive - The University of Nottingham\Documents\Phd\2) Data\1) Devices\1) Memristors\Quantum Dots\ITO"

# The specific sample folder to analyze
SAMPLE_FOLDER_NAME = "5-ITO"

# File name prefixes for the first three sweeps (ignore any trailing suffixes in actual files)
FIRST_THREE_SWEEP_PREFIXES = [
    "1-FS-0.5v-0.1sv-0.05sd-Py",
    "2-FS-3v-0.1sv-0.05sd-Py",
    "3-FS-5v-0.2sv-0.05sd-Py",
]


def list_section_directories(sample_directory: str) -> List[str]:
    """Return absolute paths of letter-named section directories within the sample directory.

    Ignores non-letter folders. Accepts single letters (A, B, D, ...). Case-insensitive.
    """
    section_directories: List[str] = []
    if not os.path.isdir(sample_directory):
        return section_directories
    for entry in os.listdir(sample_directory):
        abs_path = os.path.join(sample_directory, entry)
        if os.path.isdir(abs_path) and re.fullmatch(r"[A-Za-z]", entry or ""):
            section_directories.append(abs_path)
    return sorted(section_directories)


def find_candidate_directory_for_section(section_directory: str) -> str:
    """Return directory to search for sweep files within a section.

    Prefers the first numeric subfolder (e.g., "1") if present; otherwise use the section directory itself.
    """
    numeric_subfolders: List[str] = []
    for entry in os.listdir(section_directory):
        abs_path = os.path.join(section_directory, entry)
        if os.path.isdir(abs_path) and re.fullmatch(r"\d+", entry):
            numeric_subfolders.append(abs_path)
    if numeric_subfolders:
        return sorted(numeric_subfolders, key=lambda p: int(os.path.basename(p)))[0]
    return section_directory


def match_first_three_files(search_directory: str, prefixes: List[str]) -> Dict[str, Optional[str]]:
    """Locate the first matching .txt file for each prefix (case-insensitive) within a directory.

    Returns a mapping from prefix -> absolute file path (or None if missing).
    """
    files = [f for f in os.listdir(search_directory) if os.path.isfile(os.path.join(search_directory, f))]
    matched: Dict[str, Optional[str]] = {prefix: None for prefix in prefixes}
    for prefix in prefixes:
        for fname in files:
            if fname.lower().startswith(prefix.lower()) and fname.lower().endswith(".txt"):
                matched[prefix] = os.path.join(search_directory, fname)
                break
    return matched


def load_iv_data(file_path: str) -> pd.DataFrame:
    """Load IV data from a text file with header 'Voltage Current Time' separated by tabs.

    Returns DataFrame with columns: Voltage (V), Current (A), Time (s).
    """
    df = pd.read_csv(
        file_path,
        sep="\t",
        comment="#",
        header=0,
        names=["Voltage", "Current", "Time"],
        engine="python",
    )
    # Ensure numeric
    for col in ["Voltage", "Current", "Time"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["Voltage", "Current"]).reset_index(drop=True)
    return df


def compute_resistance_linear_fit(v: np.ndarray, i: np.ndarray) -> Optional[float]:
    """Return resistance from linear fit I = a*V + b -> R = 1/a. None if ill-conditioned."""
    if v.size < 2:
        return None
    if not np.isfinite(v).all() or not np.isfinite(i).all():
        return None
    if np.ptp(v) < 1e-12:  # nearly constant voltage
        return None
    try:
        a, b = np.polyfit(v, i, 1)
    except Exception:
        return None
    if not np.isfinite(a) or abs(a) < 1e-30:
        return None
    r = 1.0 / a
    return float(r) if np.isfinite(r) else None


def compute_resistance_in_range(df: pd.DataFrame, vmin: float, vmax: float) -> Optional[float]:
    """Compute resistance using linear fit within [vmin, vmax] (inclusive)."""
    if df.empty:
        return None
    mask = (df["Voltage"] >= min(vmin, vmax)) & (df["Voltage"] <= max(vmin, vmax))
    window = df.loc[mask]
    if len(window) < 3:
        return None
    v = window["Voltage"].values
    i = window["Current"].values
    return compute_resistance_linear_fit(v, i)


def compute_small_signal_resistance(df: pd.DataFrame) -> Optional[float]:
    """Compute small-signal resistance using a linear fit around 0 V with robust guards."""
    if df.empty:
        return None
    vmax = float(np.nanmax(np.abs(df["Voltage"].values))) if len(df) > 0 else 0.0
    if vmax <= 0:
        return None
    v_window = min(0.2, 0.1 * vmax)
    near_zero = df[np.abs(df["Voltage"]) <= v_window]
    if len(near_zero) < 3:
        # Fallback: take points closest to 0 V
        df_sorted = df.iloc[(np.abs(df["Voltage"]).argsort())]
        near_zero = df_sorted.head(min(11, len(df_sorted)))
    if len(near_zero) < 3:
        return None
    return compute_resistance_linear_fit(near_zero["Voltage"].values, near_zero["Current"].values)


def detect_switching_voltages(df: pd.DataFrame, ratio_threshold: float = 5.0, v_window: float = 0.5) -> List[float]:
    """Heuristic detection of possible switching: large adjacent current jumps within ±v_window V.

    Returns list of voltages (midpoint of the step) where |I[n+1]|/max(|I[n]|, eps) >= ratio_threshold.
    """
    if len(df) < 3:
        return []
    region = df[(df["Voltage"] >= -abs(v_window)) & (df["Voltage"] <= abs(v_window))]
    if len(region) < 3:
        return []
    volts = region["Voltage"].values
    curr = np.abs(region["Current"].values) + 1e-15
    ratios = curr[1:] / np.maximum(curr[:-1], 1e-15)
    idxs = np.where(ratios >= ratio_threshold)[0]
    events: List[float] = []
    for idx in idxs:
        vmid = 0.5 * (volts[idx] + volts[idx + 1])
        events.append(float(vmid))
    return events


def format_engineering(value: float) -> str:
    """Return engineering string, e.g., 1.23 kΩ, 4.56 MΩ."""
    if value is None or not np.isfinite(value):
        return "n/a"
    abs_val = abs(value)
    if abs_val >= 1e9:
        return f"{value/1e9:.3g} GΩ"
    if abs_val >= 1e6:
        return f"{value/1e6:.3g} MΩ"
    if abs_val >= 1e3:
        return f"{value/1e3:.3g} kΩ"
    return f"{value:.3g} Ω"


def write_origin_wide_csv(out_path: str, blocks: List[Tuple[str, int, pd.DataFrame, str, Optional[float], Optional[float]]], sample: str) -> None:
    """Write a single CSV with left-to-right [Voltage,Current,Time] triplets for each (Section,Sweep).

    blocks: list of (section_name, sweep_index, df, source_file_basename, R_pos_0-0.5, R_neg_-0.5-0)
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    # Determine maximum rows
    max_len = 0
    for _, _, df, _, _, _ in blocks:
        max_len = max(max_len, len(df))
    # Prepare header rows
    group_row = []
    name_row = []
    meta_row = []
    for section, sweep_index, _, file_name, r_pos, r_neg in blocks:
        label = f"{section}_s{sweep_index}"
        group_row.extend([label, label, label])
        name_row.extend(["Voltage", "Current", "Time"])
        rpos_str = f"Rpos={r_pos:.6g}" if (r_pos is not None and np.isfinite(r_pos)) else "Rpos=n/a"
        rneg_str = f"Rneg={r_neg:.6g}" if (r_neg is not None and np.isfinite(r_neg)) else "Rneg=n/a"
        meta_row.extend([rpos_str, rneg_str, f"file={file_name}"])
    # Write file
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(f"# sample: {sample}\n")
        fh.write(f"# blocks: {len(blocks)} (Section_Sweep triplets left-to-right)\n")
        fh.write(",".join(group_row) + "\n")
        fh.write(",".join(name_row) + "\n")
        fh.write(",".join(meta_row) + "\n")
        # Data rows
        for row_idx in range(max_len):
            row_values: List[str] = []
            for _, _, df, _, _, _ in blocks:
                if row_idx < len(df):
                    v = df["Voltage"].iat[row_idx]
                    i = df["Current"].iat[row_idx]
                    t = df.get("Time", pd.Series([np.nan]*len(df))).iat[row_idx]
                    v_str = f"{float(v):.12g}" if np.isfinite(v) else ""
                    i_str = f"{float(i):.12g}" if np.isfinite(i) else ""
                    t_str = f"{float(t):.12g}" if (t is not None and np.isfinite(t)) else ""
                else:
                    v_str = i_str = t_str = ""
                row_values.extend([v_str, i_str, t_str])
            fh.write(",".join(row_values) + "\n")


def main() -> None:
    # Filesystem locations
    repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    analysis_dir = os.path.join(repo_dir, "ITO_Analysis")
    sample_dir = os.path.join(ONEDRIVE_ROOT, SAMPLE_FOLDER_NAME)
    output_dir = os.path.join(analysis_dir, SAMPLE_FOLDER_NAME)
    os.makedirs(output_dir, exist_ok=True)

    # Collect data across sections
    section_dirs = list_section_directories(sample_dir)
    per_sweep_summary: List[Dict[str, object]] = []
    combined_rows: List[Dict[str, object]] = []

    # For overlay plot of first sweeps and for wide CSV blocks
    overlay_traces: List[Tuple[str, np.ndarray, np.ndarray]] = []  # (label, V, I)
    wide_blocks: List[Tuple[str, int, pd.DataFrame, str, Optional[float], Optional[float]]] = []

    for section_path in section_dirs:
        section_name = os.path.basename(section_path).upper()
        search_dir = find_candidate_directory_for_section(section_path)
        matched_files = match_first_three_files(search_dir, FIRST_THREE_SWEEP_PREFIXES)

        # Process first sweep (for resistance and overlay)
        first_sweep_path = matched_files[FIRST_THREE_SWEEP_PREFIXES[0]]
        if first_sweep_path and os.path.isfile(first_sweep_path):
            df_first = load_iv_data(first_sweep_path)
            r_small = compute_small_signal_resistance(df_first)
            r_pos_first = compute_resistance_in_range(df_first, 0.0, 0.5)
            label_r = r_pos_first if r_pos_first is not None else r_small
            overlay_traces.append((f"{section_name} ({format_engineering(label_r)})", df_first["Voltage"].values, df_first["Current"].values))

        # Build summary and wide CSV blocks
        for idx, prefix in enumerate(FIRST_THREE_SWEEP_PREFIXES, start=1):
            sweep_path = matched_files[prefix]
            if not sweep_path or not os.path.isfile(sweep_path):
                continue
            df = load_iv_data(sweep_path)

            # Resistances in specified ranges
            r_pos = compute_resistance_in_range(df, 0.0, 0.5)
            r_neg = compute_resistance_in_range(df, -0.5, 0.0)
            switch_v = detect_switching_voltages(df)
            ohmic_flag = "X" if len(switch_v) > 0 else ""

            wide_blocks.append((section_name, idx, df, os.path.basename(sweep_path), r_pos, r_neg))

            per_sweep_summary.append(
                {
                    "sample": SAMPLE_FOLDER_NAME,
                    "section": section_name,
                    "sweep_index": idx,
                    "file_name": os.path.basename(sweep_path),
                    "R_pos_0_to_0p5_ohm": r_pos,
                    "R_neg_m0p5_to_0_ohm": r_neg,
                    "R_pos_label": format_engineering(r_pos) if r_pos is not None else "n/a",
                    "R_neg_label": format_engineering(r_neg) if r_neg is not None else "n/a",
                    "ohmic": "" if ohmic_flag == "" else "X",
                    "switching_voltages_V": ";".join(f"{v:.3g}" for v in switch_v) if switch_v else "",
                }
            )

            # Combined long CSV (all rows for all sweeps)
            combined_rows.extend(
                {
                    "sample": SAMPLE_FOLDER_NAME,
                    "section": section_name,
                    "sweep_index": idx,
                    "sweep_prefix": prefix,
                    "file_name": os.path.basename(sweep_path),
                    "Voltage_V": float(v),
                    "Current_A": float(i),
                    "Time_s": float(t) if pd.notna(t) else None,
                }
                for v, i, t in zip(df["Voltage"].values, df["Current"].values, df.get("Time", pd.Series([np.nan]*len(df))).values)
            )

    # Save combined long CSV (tidy format)
    if combined_rows:
        combined_df = pd.DataFrame(combined_rows)
        combined_csv_path = os.path.join(output_dir, f"ITO_{SAMPLE_FOLDER_NAME}_first_three_sweeps.csv")
        combined_df.to_csv(combined_csv_path, index=False)

    # Save summary CSV (per sweep per section)
    if per_sweep_summary:
        summary_df = pd.DataFrame(per_sweep_summary)
        summary_csv_path = os.path.join(output_dir, f"ITO_{SAMPLE_FOLDER_NAME}_summary.csv")
        summary_df.to_csv(summary_csv_path, index=False)

    # Save single wide Origin-friendly CSV (left-to-right V,C,T for each Section/Sweep) including resistances per block
    if wide_blocks:
        wide_out = os.path.join(output_dir, f"ITO_{SAMPLE_FOLDER_NAME}_wide.csv")
        write_origin_wide_csv(wide_out, wide_blocks, sample=SAMPLE_FOLDER_NAME)

    # Plot 1: Overlay of first-sweep I-V curves labeled by section and R(0->0.5V)
    if overlay_traces:
        plt.figure(figsize=(8, 6))
        for label, v, i in overlay_traces:
            plt.plot(v, i, label=label, linewidth=1.5)
        plt.xlabel("Voltage (V)")
        plt.ylabel("Current (A)")
        plt.title(f"{SAMPLE_FOLDER_NAME}: First-sweep I-V by Section (label shows R 0->0.5 V)")
        plt.grid(True, which="both", linestyle=":", linewidth=0.6)
        plt.legend(loc="best", fontsize=8)
        overlay_path = os.path.join(output_dir, f"ITO_{SAMPLE_FOLDER_NAME}_first_sweep_overlay.png")
        plt.tight_layout()
        plt.savefig(overlay_path, dpi=200)
        plt.close()

    # Plot 2: Bar chart of R(0->0.5V) by section (from first sweep)
    if per_sweep_summary:
        first_sweep_rows = [row for row in per_sweep_summary if row.get("sweep_index") == 1]
        if first_sweep_rows:
            labels = [row["section"] for row in first_sweep_rows]
            resistances = [row["R_pos_0_to_0p5_ohm"] if row["R_pos_0_to_0p5_ohm"] is not None else np.nan for row in first_sweep_rows]
            if any(np.isfinite(r) for r in resistances):
                plt.figure(figsize=(8, 5))
                values = [(r / 1e3) if np.isfinite(r) else np.nan for r in resistances]
                plt.bar(labels, values, color="#4e79a7")
                plt.ylabel("Resistance (kΩ)")
                plt.title(f"{SAMPLE_FOLDER_NAME}: First-sweep R(0->0.5 V) by Section")
                plt.grid(axis="y", linestyle=":", linewidth=0.6)
                for x, r in zip(labels, resistances):
                    if np.isfinite(r):
                        plt.text(x, (r / 1e3) * 1.02, format_engineering(r), ha="center", va="bottom", fontsize=8, rotation=90)
                bar_path = os.path.join(output_dir, f"ITO_{SAMPLE_FOLDER_NAME}_resistance_bar.png")
                plt.tight_layout()
                plt.savefig(bar_path, dpi=200)
                plt.close()

    # Plot 3: Overlay of last sweep IV within -0.5 to 0 V (final resistance region)
    if per_sweep_summary and wide_blocks:
        last_blocks = [(sec, idx, df) for (sec, idx, df, _, _, _) in wide_blocks if idx == 3]
        if last_blocks:
            plt.figure(figsize=(8, 6))
            for sec, idx, df in last_blocks:
                region = df[(df["Voltage"] >= -0.5) & (df["Voltage"] <= 0.0)]
                if len(region) >= 2:
                    plt.plot(region["Voltage"].values, region["Current"].values, label=f"{sec}", linewidth=1.5)
            plt.xlabel("Voltage (V)")
            plt.ylabel("Current (A)")
            plt.title(f"{SAMPLE_FOLDER_NAME}: Last sweep IV in -0.5..0 V")
            plt.grid(True, which="both", linestyle=":", linewidth=0.6)
            plt.legend(loc="best", fontsize=8)
            out_path = os.path.join(output_dir, f"ITO_{SAMPLE_FOLDER_NAME}_last_neg_overlay.png")
            plt.tight_layout()
            plt.savefig(out_path, dpi=200)
            plt.close()

    # Plot 4: Grouped bar chart of first vs last resistances (Rpos first, Rneg last)
    if per_sweep_summary:
        first_by_sec: Dict[str, Optional[float]] = {}
        last_by_sec: Dict[str, Optional[float]] = {}
        for row in per_sweep_summary:
            if row.get("sweep_index") == 1:
                first_by_sec[row["section"]] = row.get("R_pos_0_to_0p5_ohm")
            if row.get("sweep_index") == 3:
                last_by_sec[row["section"]] = row.get("R_neg_m0p5_to_0_ohm")
        sections = sorted(set(first_by_sec.keys()).union(last_by_sec.keys()))
        if sections:
            first_vals = [first_by_sec.get(s) if first_by_sec.get(s) is not None else np.nan for s in sections]
            last_vals = [last_by_sec.get(s) if last_by_sec.get(s) is not None else np.nan for s in sections]
            if any(np.isfinite(first_vals)) or any(np.isfinite(last_vals)):
                x = np.arange(len(sections))
                width = 0.38
                plt.figure(figsize=(9, 5))
                plt.bar(x - width/2, [(v/1e3) if np.isfinite(v) else np.nan for v in first_vals], width, label="First (0->0.5 V)")
                plt.bar(x + width/2, [(v/1e3) if np.isfinite(v) else np.nan for v in last_vals], width, label="Last (-0.5->0 V)")
                plt.xticks(x, sections)
                plt.ylabel("Resistance (kΩ)")
                plt.title(f"{SAMPLE_FOLDER_NAME}: First vs Last Resistances")
                plt.grid(axis="y", linestyle=":", linewidth=0.6)
                plt.legend()
                out_path = os.path.join(output_dir, f"ITO_{SAMPLE_FOLDER_NAME}_first_vs_last_resistance.png")
                plt.tight_layout()
                plt.savefig(out_path, dpi=200)
                plt.close()

    # Plot 5: Semilog-Y plot of abs(Current) vs Voltage for last sweep
    if wide_blocks:
        last_blocks = [(sec, idx, df) for (sec, idx, df, _, _, _) in wide_blocks if idx == 3]
        if last_blocks:
            plt.figure(figsize=(8, 6))
            for sec, idx, df in last_blocks:
                v = df["Voltage"].values
                i_abs = np.abs(df["Current"].values) + 1e-20
                plt.semilogy(v, i_abs, label=sec)
            plt.xlabel("Voltage (V)")
            plt.ylabel("abs(Current) (A)")
            plt.title(f"{SAMPLE_FOLDER_NAME}: Last sweep semilog abs(I) vs V")
            plt.grid(True, which="both", linestyle=":", linewidth=0.6)
            plt.legend(loc="best", fontsize=8)
            out_path = os.path.join(output_dir, f"ITO_{SAMPLE_FOLDER_NAME}_last_semilogy.png")
            plt.tight_layout()
            plt.savefig(out_path, dpi=200)
            plt.close()

    # Stats and plots: start vs end resistance
    if per_sweep_summary:
        # Build per-section start (sweep 1, Rpos) and end (sweep 3, Rneg)
        start_map: Dict[str, Optional[float]] = {}
        end_map: Dict[str, Optional[float]] = {}
        for row in per_sweep_summary:
            sec = row["section"]
            if row.get("sweep_index") == 1:
                start_map[sec] = row.get("R_pos_0_to_0p5_ohm")
            if row.get("sweep_index") == 3:
                end_map[sec] = row.get("R_neg_m0p5_to_0_ohm")
        sections_se = sorted(set(start_map.keys()).intersection(end_map.keys()))
        stats_rows: List[Dict[str, object]] = []
        xs = []
        ys = []
        labels = []
        for sec in sections_se:
            r_start = start_map.get(sec)
            r_end = end_map.get(sec)
            stats_rows.append({
                "section": sec,
                "R_start_ohm": r_start,
                "R_end_ohm": r_end,
                "R_end_over_start": (r_end / r_start) if (r_start is not None and r_end is not None and np.isfinite(r_start) and r_start != 0) else np.nan,
                "log10_R_end_over_start": (np.log10((r_end / r_start))) if (r_start is not None and r_end is not None and np.isfinite(r_start) and r_start != 0 and r_end is not None and np.isfinite(r_end)) else np.nan,
            })
            if r_start is not None and r_end is not None and np.isfinite(r_start) and np.isfinite(r_end):
                xs.append(r_start)
                ys.append(r_end)
                labels.append(sec)
        # Save stats CSV
        if stats_rows:
            stats_df = pd.DataFrame(stats_rows)
            stats_path = os.path.join(output_dir, f"ITO_{SAMPLE_FOLDER_NAME}_start_end_stats.csv")
            stats_df.to_csv(stats_path, index=False)
        # Scatter: start vs end
        if len(xs) >= 1:
            plt.figure(figsize=(6.5, 6))
            plt.loglog(xs, ys, 'o', label='Sections')
            # y=x line
            try:
                minv = float(np.nanmin([np.nanmin(xs), np.nanmin(ys)]))
                maxv = float(np.nanmax([np.nanmax(xs), np.nanmax(ys)]))
                if np.isfinite(minv) and np.isfinite(maxv) and maxv > 0 and maxv > minv:
                    plt.loglog([minv, maxv], [minv, maxv], '--', color='gray', label='y=x')
            except Exception:
                pass
            for x, y, sec in zip(xs, ys, labels):
                plt.annotate(sec, (x, y), textcoords="offset points", xytext=(4, 2), fontsize=8)
            plt.xlabel("Start R (0->0.5 V) [Ohm]")
            plt.ylabel("End R (-0.5->0 V) [Ohm]")
            plt.title(f"{SAMPLE_FOLDER_NAME}: Start vs End Resistance")
            plt.grid(True, which='both', linestyle=':', linewidth=0.6)
            plt.legend()
            out_path = os.path.join(output_dir, f"ITO_{SAMPLE_FOLDER_NAME}_start_vs_end_scatter.png")
            plt.tight_layout()
            plt.savefig(out_path, dpi=200)
            plt.close()
        # Dumbbell chart: visual range per section (start vs end on log-x)
        if sections_se:
            plt.figure(figsize=(9, max(4, 0.45*len(sections_se))))
            y_positions = np.arange(len(sections_se))
            start_vals = [start_map.get(s) if start_map.get(s) is not None else np.nan for s in sections_se]
            end_vals = [end_map.get(s) if end_map.get(s) is not None else np.nan for s in sections_se]
            # Plot lines
            for y, s_val, e_val in zip(y_positions, start_vals, end_vals):
                if np.isfinite(s_val) and np.isfinite(e_val):
                    plt.plot([s_val, e_val], [y, y], '-', color='#9fbfdf', linewidth=2)
            # Plot markers
            plt.scatter(start_vals, y_positions, color='#4e79a7', label='Start (0->0.5 V)')
            plt.scatter(end_vals, y_positions, color='#f28e2b', label='End (-0.5->0 V)')
            plt.yticks(y_positions, sections_se)
            plt.xscale('log')
            plt.xlabel('Resistance (Ohm, log scale)')
            plt.title(f"{SAMPLE_FOLDER_NAME}: Start vs End Resistance (Dumbbell)")
            plt.grid(True, axis='x', which='both', linestyle=':', linewidth=0.6)
            plt.legend()
            out_path = os.path.join(output_dir, f"ITO_{SAMPLE_FOLDER_NAME}_start_end_dumbbell.png")
            plt.tight_layout()
            plt.savefig(out_path, dpi=200)
            plt.close()
        # Violin plot: distribution of start vs end
        start_series = [v for v in start_map.values() if v is not None and np.isfinite(v)]
        end_series = [v for v in end_map.values() if v is not None and np.isfinite(v)]
        if len(start_series) >= 2 or len(end_series) >= 2:
            # Work in log10 for better distribution visualization
            data = []
            labels_violin = []
            if len(start_series) >= 2:
                data.append(np.log10(np.array(start_series)))
                labels_violin.append('Start (0->0.5 V)')
            if len(end_series) >= 2:
                data.append(np.log10(np.array(end_series)))
                labels_violin.append('End (-0.5->0 V)')
            if data:
                plt.figure(figsize=(7, 5))
                parts = plt.violinplot(data, showmeans=True, showmedians=True)
                plt.xticks(np.arange(1, len(labels_violin)+1), labels_violin)
                plt.ylabel('log10(Resistance [Ohm])')
                plt.title(f"{SAMPLE_FOLDER_NAME}: Distribution of Resistances")
                plt.grid(axis='y', linestyle=':', linewidth=0.6)
                out_path = os.path.join(output_dir, f"ITO_{SAMPLE_FOLDER_NAME}_distribution.png")
                plt.tight_layout()
                plt.savefig(out_path, dpi=200)
                plt.close()

    # Simple console output for quick check (ASCII-safe)
    print(f"Analyzed sample: {SAMPLE_FOLDER_NAME}")
    print(f"Sections found: {[os.path.basename(p) for p in section_dirs]}")
    if per_sweep_summary:
        print("First-sweep resistances (0->0.5 V):")
        for row in [r for r in per_sweep_summary if r.get("sweep_index") == 1]:
            label_ascii = str(row['R_pos_label']).replace('Ω', 'Ohm')
            print(f"  {row['section']}: {label_ascii}  ({'X' if row['ohmic']=='X' else 'ohmic'})")


if __name__ == "__main__":
    main()









