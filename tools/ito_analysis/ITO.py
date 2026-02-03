import os
import re
from typing import Dict, List, Optional, Tuple, Set

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

print("ITO Analysis Running...")

# Root directory on OneDrive that contains the ITO sample folders (e.g., "5-ITO")
ONEDRIVE_ROOT = r"C:\Users\Craig-Desktop\OneDrive - The University of Nottingham\Documents\Phd\2) Data\1) Devices\1) Memristors\ITO"

# The specific sample folder to analyze
SAMPLE_FOLDER_NAME = "7_ITO"

# Geometry and material constants
# Thickness: 50 nm; Length uncertainty: 6700–6950 µm (use for error bounds)
THICKNESS_M: float = 50e-9
LENGTH_M_MIN: float = 6700e-6
LENGTH_M_MAX: float = 6950e-6

# Section widths (µm). A,D,G,H = 200 µm; B,E,L,I = 100 µm. Case-insensitive.
SECTION_WIDTH_UM: Dict[str, float] = {
    "A": 200.0, "D": 200.0, "G": 200.0, "H": 200.0,
    "B": 100.0, "E": 100.0, "L": 100.0, "I": 100.0,
}


# Conductivity thresholds (S/m) for guideline lines on plots
CONDUCTIVITY_THRESHOLDS: Dict[str, float] = {
    "low": 1e3,
    "medium": 1e4,
    "high": 1e5,
}

# Batch analysis options
PROCESS_ALL_SAMPLES: bool = True  # If True, analyze all subfolders in ONEDRIVE_ROOT except exclusions
EXCLUDE_SAMPLES: Set[str] = {"1","2","summary"}  # e.g., {"test", "archive"}

# File name prefixes for the first three sweeps (ignore any trailing suffixes in actual files)
FIRST_THREE_SWEEP_PREFIXES = [
    "1-FS-0.5v-0.1sv-0.05sd-Py",
    "2-FS-3v-0.1sv-0.05sd-Py",
    "3-FS-5v-0.2sv-0.05sd-Py",
]


def get_section_width_m(section_name: str) -> Optional[float]:
    key = (section_name or "").strip().upper()
    if key in SECTION_WIDTH_UM:
        return SECTION_WIDTH_UM[key] * 1e-6
    return None

def format_engineering_S(value: float) -> str:
    """Engineering string for conductance (S)."""
    if value is None or not np.isfinite(value):
        return "n/a"
    abs_val = abs(value)
    if abs_val >= 1:
        return f"{value:.3g} S"
    if abs_val >= 1e-3:
        return f"{value*1e3:.3g} mS"
    if abs_val >= 1e-6:
        return f"{value*1e6:.3g} µS"
    if abs_val >= 1e-9:
        return f"{value*1e9:.3g} nS"
    return f"{value:.3g} S"



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


def compute_geometry_metrics(section: str, resistance_ohm: Optional[float]) -> Dict[str, Optional[float]]:
    """Compute geometry-derived metrics given a section and resistance.

    Returns dict with keys:
    width_m, length_m_min, length_m_max, area_m2,
    sigma_nominal_Spm, sigma_lo_Spm, sigma_hi_Spm,
    rho_nominal_ohm_m, rho_lo_ohm_m, rho_hi_ohm_m,
    Rsheet_nominal_ohm_sq, Rsheet_lo_ohm_sq, Rsheet_hi_ohm_sq
    """
    width_m = get_section_width_m(section)
    if resistance_ohm is None or not np.isfinite(resistance_ohm) or resistance_ohm <= 0 or width_m is None:
        return {
            "width_m": width_m,
            "length_m_min": LENGTH_M_MIN,
            "length_m_max": LENGTH_M_MAX,
            "area_m2": None,
            "sigma_nominal_Spm": None,
            "sigma_lo_Spm": None,
            "sigma_hi_Spm": None,
            "rho_nominal_ohm_m": None,
            "rho_lo_ohm_m": None,
            "rho_hi_ohm_m": None,
            "Rsheet_nominal_ohm_sq": None,
            "Rsheet_lo_ohm_sq": None,
            "Rsheet_hi_ohm_sq": None,
        }
    area_m2 = width_m * THICKNESS_M
    L_mean = 0.5 * (LENGTH_M_MIN + LENGTH_M_MAX)
    # Conductivity sigma = L / (R * A)
    sigma_lo = LENGTH_M_MIN / (resistance_ohm * area_m2)
    sigma_hi = LENGTH_M_MAX / (resistance_ohm * area_m2)
    sigma_nom = L_mean / (resistance_ohm * area_m2)
    # Resistivity rho = 1/sigma
    rho_lo = 1.0 / sigma_hi if sigma_hi > 0 else None
    rho_hi = 1.0 / sigma_lo if sigma_lo > 0 else None
    rho_nom = 1.0 / sigma_nom if sigma_nom > 0 else None
    # Sheet resistance R_s = R * (w / L)
    Rs_lo = resistance_ohm * (width_m / LENGTH_M_MAX)
    Rs_hi = resistance_ohm * (width_m / LENGTH_M_MIN)
    Rs_nom = resistance_ohm * (width_m / L_mean)
    return {
        "width_m": width_m,
        "length_m_min": LENGTH_M_MIN,
        "length_m_max": LENGTH_M_MAX,
        "area_m2": area_m2,
        "sigma_nominal_Spm": sigma_nom,
        "sigma_lo_Spm": sigma_lo,
        "sigma_hi_Spm": sigma_hi,
        "rho_nominal_ohm_m": rho_nom,
        "rho_lo_ohm_m": rho_lo,
        "rho_hi_ohm_m": rho_hi,
        "Rsheet_nominal_ohm_sq": Rs_nom,
        "Rsheet_lo_ohm_sq": Rs_lo,
        "Rsheet_hi_ohm_sq": Rs_hi,
    }

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
        # Add conductance labels for quick view
        gpos = (1.0 / r_pos) if (r_pos is not None and np.isfinite(r_pos) and r_pos != 0) else None
        gneg = (1.0 / r_neg) if (r_neg is not None and np.isfinite(r_neg) and r_neg != 0) else None
        gpos_str = f"Gpos={gpos:.6g} S" if (gpos is not None and np.isfinite(gpos)) else "Gpos=n/a"
        gneg_str = f"Gneg={gneg:.6g} S" if (gneg is not None and np.isfinite(gneg)) else "Gneg=n/a"
        meta_row.extend([rpos_str, rneg_str, gpos_str + ";" + gneg_str])
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


def analyze_sample(sample_folder_name: str) -> None:
    # Filesystem locations
    repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    sample_dir = os.path.join(ONEDRIVE_ROOT, sample_folder_name)
    # Save all outputs inside the data folder: <ONEDRIVE_ROOT>/<sample>/analysis
    output_dir = os.path.join(sample_dir, "analysis")
    os.makedirs(output_dir, exist_ok=True)
    # Folder for per-sweep individual semilog plots
    individual_semilog_dir = os.path.join(output_dir, "log_iv_individual")
    os.makedirs(individual_semilog_dir, exist_ok=True)

    # Collect data across sections
    section_dirs = list_section_directories(sample_dir)
    per_sweep_summary: List[Dict[str, object]] = []
    combined_rows: List[Dict[str, object]] = []
    combined_df: Optional[pd.DataFrame] = None
    summary_df: Optional[pd.DataFrame] = None
    stats_df: Optional[pd.DataFrame] = None

    # For overlay plot of first sweeps and for wide CSV blocks
    overlay_traces: List[Tuple[str, np.ndarray, np.ndarray]] = []  # (label, V, I)
    wide_blocks: List[Tuple[str, int, pd.DataFrame, str, Optional[float], Optional[float]]] = []
    # Collect data for combined semilog plots per sweep index
    combined_semilog: Dict[int, List[Tuple[str, np.ndarray, np.ndarray]]] = {1: [], 2: [], 3: []}

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

            # Conductance (simple reciprocal, where defined)
            g_pos = (1.0 / r_pos) if (r_pos is not None and np.isfinite(r_pos) and r_pos != 0) else None
            g_neg = (1.0 / r_neg) if (r_neg is not None and np.isfinite(r_neg) and r_neg != 0) else None

            # Geometry-based metrics using R_pos for sweeps 1..3 and R_neg likewise (store both when available)
            geom_pos = compute_geometry_metrics(section_name, r_pos) if r_pos is not None else {}
            geom_neg = compute_geometry_metrics(section_name, r_neg) if r_neg is not None else {}

            wide_blocks.append((section_name, idx, df, os.path.basename(sweep_path), r_pos, r_neg))

            # Save individual semilog I-V plot (Voltage vs log(abs(Current)))
            try:
                v_vals = df["Voltage"].values
                i_abs_vals = np.abs(df["Current"].values) + 1e-20
                plt.figure(figsize=(8, 6))
                plt.semilogy(v_vals, i_abs_vals, linewidth=1.6, label=f"{section_name}")
                plt.xlabel("Voltage (V)")
                plt.ylabel("abs(Current) (A)")
                plt.title(f"{sample_folder_name}: Sweep {idx} - Section {section_name}")
                plt.grid(True, which="both", linestyle=":", linewidth=0.6)
                out_individual = os.path.join(individual_semilog_dir, f"{idx}-{section_name}.png")
                plt.tight_layout()
                plt.savefig(out_individual, dpi=200)
                plt.close()
            except Exception:
                plt.close()

            # Accumulate for combined plots per sweep
            try:
                combined_semilog[idx].append((section_name, v_vals, i_abs_vals))
            except Exception:
                pass

            per_sweep_summary.append(
                {
                    "sample": sample_folder_name,
                    "section": section_name,
                    "sweep_index": idx,
                    "file_name": os.path.basename(sweep_path),
                    "R_pos_0_to_0p5_ohm": r_pos,
                    "R_neg_m0p5_to_0_ohm": r_neg,
                    "R_pos_label": format_engineering(r_pos) if r_pos is not None else "n/a",
                    "R_neg_label": format_engineering(r_neg) if r_neg is not None else "n/a",
                    "G_pos_S": g_pos,
                    "G_neg_S": g_neg,
                    # Geometry
                    "width_m": geom_pos.get("width_m") or geom_neg.get("width_m"),
                    "thickness_m": THICKNESS_M,
                    "length_m_min": LENGTH_M_MIN,
                    "length_m_max": LENGTH_M_MAX,
                    # Conductivity/resistivity (using whichever side had a valid R)
                    "sigma_nominal_Spm": geom_pos.get("sigma_nominal_Spm") if geom_pos else geom_neg.get("sigma_nominal_Spm"),
                    "sigma_lo_Spm": geom_pos.get("sigma_lo_Spm") if geom_pos else geom_neg.get("sigma_lo_Spm"),
                    "sigma_hi_Spm": geom_pos.get("sigma_hi_Spm") if geom_pos else geom_neg.get("sigma_hi_Spm"),
                    "rho_nominal_ohm_m": geom_pos.get("rho_nominal_ohm_m") if geom_pos else geom_neg.get("rho_nominal_ohm_m"),
                    "rho_lo_ohm_m": geom_pos.get("rho_lo_ohm_m") if geom_pos else geom_neg.get("rho_lo_ohm_m"),
                    "rho_hi_ohm_m": geom_pos.get("rho_hi_ohm_m") if geom_pos else geom_neg.get("rho_hi_ohm_m"),
                    "Rsheet_nominal_ohm_sq": geom_pos.get("Rsheet_nominal_ohm_sq") if geom_pos else geom_neg.get("Rsheet_nominal_ohm_sq"),
                    "Rsheet_lo_ohm_sq": geom_pos.get("Rsheet_lo_ohm_sq") if geom_pos else geom_neg.get("Rsheet_lo_ohm_sq"),
                    "Rsheet_hi_ohm_sq": geom_pos.get("Rsheet_hi_ohm_sq") if geom_pos else geom_neg.get("Rsheet_hi_ohm_sq"),
                    "ohmic": "" if ohmic_flag == "" else "X",
                    "switching_voltages_V": ";".join(f"{v:.3g}" for v in switch_v) if switch_v else "",
                }
            )

            # Combined long CSV (all rows for all sweeps)
            combined_rows.extend(
                {
                    "sample": sample_folder_name,
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
        combined_csv_path = os.path.join(output_dir, f"ITO_{sample_folder_name}_first_three_sweeps.csv")
        combined_df.to_csv(combined_csv_path, index=False)

    # Save summary CSV (per sweep per section)
    if per_sweep_summary:
        summary_df = pd.DataFrame(per_sweep_summary)
        summary_csv_path = os.path.join(output_dir, f"ITO_{sample_folder_name}_summary.csv")
        summary_df.to_csv(summary_csv_path, index=False)

    # Save single wide Origin-friendly CSV (left-to-right V,C,T for each Section/Sweep) including resistances per block
    if wide_blocks:
        wide_out = os.path.join(output_dir, f"ITO_{sample_folder_name}_wide.csv")
        write_origin_wide_csv(wide_out, wide_blocks, sample=sample_folder_name)

    # Combined semilog plots per sweep: 1-all, 2-all, 3-all
    for sweep_idx in (1, 2, 3):
        traces = combined_semilog.get(sweep_idx, [])
        if traces:
            try:
                plt.figure(figsize=(8, 6))
                for sec_label, v_vals, i_abs_vals in traces:
                    plt.semilogy(v_vals, i_abs_vals, label=sec_label, linewidth=1.5)
                plt.xlabel("Voltage (V)")
                plt.ylabel("abs(Current) (A)")
                plt.title(f"{sample_folder_name}: Sweep {sweep_idx} - all sections (semilog)")
                plt.grid(True, which="both", linestyle=":", linewidth=0.6)
                plt.legend(loc="best", fontsize=8)
                out_all = os.path.join(output_dir, f"{sweep_idx}-all.png")
                plt.tight_layout()
                plt.savefig(out_all, dpi=200)
                plt.close()
            except Exception:
                plt.close()

    # Optional: Excel workbook export with multiple sheets
    try:
        xlsx_path = os.path.join(output_dir, f"ITO_{sample_folder_name}_summary.xlsx")
        with pd.ExcelWriter(xlsx_path, engine="xlsxwriter") as writer:
            if summary_df is not None:
                summary_df.to_excel(writer, sheet_name="summary", index=False)
            if combined_df is not None:
                combined_df.to_excel(writer, sheet_name="long", index=False)
            if stats_df is not None:
                stats_df.to_excel(writer, sheet_name="start_end_stats", index=False)
            # Embed table image if exists
            table_img = os.path.join(output_dir, f"ITO_{sample_folder_name}_summary_table.png")
            if os.path.isfile(table_img):
                # Create an empty sheet and insert image
                ws = writer.book.add_worksheet("summary_table")
                ws.insert_image("B2", table_img)
    except Exception:
        pass

    # Plot 1: Overlay of first-sweep I-V curves labeled by section and R(0->0.5V)
    if overlay_traces:
        plt.figure(figsize=(8, 6))
        for label, v, i in overlay_traces:
            plt.plot(v, i, label=label, linewidth=1.5)
        plt.xlabel("Voltage (V)")
        plt.ylabel("Current (A)")
        plt.title(f"{sample_folder_name}: First-sweep I-V by Section (label shows R 0->0.5 V)")
        plt.grid(True, which="both", linestyle=":", linewidth=0.6)
        plt.legend(loc="best", fontsize=8)
        overlay_path = os.path.join(output_dir, f"ITO_{sample_folder_name}_first_sweep_overlay.png")
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
                plt.title(f"{sample_folder_name}: First-sweep R(0->0.5 V) by Section")
                plt.grid(axis="y", linestyle=":", linewidth=0.6)
                for x, r in zip(labels, resistances):
                    if np.isfinite(r):
                        plt.text(x, (r / 1e3) * 1.02, format_engineering(r), ha="center", va="bottom", fontsize=8, rotation=90)
                bar_path = os.path.join(output_dir, f"ITO_{sample_folder_name}_resistance_bar.png")
                plt.tight_layout()
                plt.savefig(bar_path, dpi=200)
                plt.close()

            # Additional plot: Conductance for first vs final (G_pos vs G_neg background)
            g_pos_vals = [row.get("G_pos_S") if row.get("G_pos_S") is not None else np.nan for row in first_sweep_rows]
            # Match final conductance by section (from sweep 3 -> G_neg)
            final_rows = [row for row in per_sweep_summary if row.get("sweep_index") == 3]
            g_neg_map = {row["section"]: (row.get("G_neg_S") if row.get("G_neg_S") is not None else np.nan) for row in final_rows}
            g_neg_vals = [g_neg_map.get(sec, np.nan) for sec in labels]
            if any(np.isfinite(g) for g in g_pos_vals) or any(np.isfinite(g) for g in g_neg_vals):
                plt.figure(figsize=(9, 5))
                # background bars for final in lighter color
                g_neg_ms = [(g * 1e3) if np.isfinite(g) else np.nan for g in g_neg_vals]
                g_pos_ms = [(g * 1e3) if np.isfinite(g) else np.nan for g in g_pos_vals]
                x = np.arange(len(labels))
                bar_bg = plt.bar(x, g_neg_ms, color="#c7e9c0", label="Final G (mS)")
                bar_fg = plt.bar(x, g_pos_ms, color="#59a14f", alpha=0.9, width=0.55, label="First G (mS)")
                plt.xticks(x, labels)
                plt.ylabel("Conductance (mS)")
                plt.title(f"{sample_folder_name}: Conductance first vs final")
                plt.grid(axis="y", linestyle=":", linewidth=0.6)
                for xi, g in zip(x, g_pos_vals):
                    if np.isfinite(g):
                        plt.text(xi, (g * 1e3) * 1.02, format_engineering_S(g), ha="center", va="bottom", fontsize=8, rotation=90)
                out_path = os.path.join(output_dir, f"ITO_{sample_folder_name}_conductance_bar.png")
                plt.tight_layout()
                plt.legend()
                plt.savefig(out_path, dpi=200)
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
            plt.title(f"{sample_folder_name}: Last sweep IV in -0.5..0 V")
            plt.grid(True, which="both", linestyle=":", linewidth=0.6)
            plt.legend(loc="best", fontsize=8)
            out_path = os.path.join(output_dir, f"ITO_{sample_folder_name}_last_neg_overlay.png")
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
                plt.title(f"{sample_folder_name}: First vs Last Resistances")
                plt.grid(axis="y", linestyle=":", linewidth=0.6)
                plt.legend()
                out_path = os.path.join(output_dir, f"ITO_{sample_folder_name}_first_vs_last_resistance.png")
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
            plt.title(f"{sample_folder_name}: Last sweep semilog abs(I) vs V")
            plt.grid(True, which="both", linestyle=":", linewidth=0.6)
            plt.legend(loc="best", fontsize=8)
            out_path = os.path.join(output_dir, f"ITO_{sample_folder_name}_last_semilogy.png")
            plt.tight_layout()
            plt.savefig(out_path, dpi=200)
            plt.close()

    # Dashboard figure: a grid of subplots summarizing key plots
    try:
        import math
        dashboard_paths = []
        # List existing plot files to include (ensure table last)
        candidate_plots = [
            f"ITO_{sample_folder_name}_first_sweep_overlay.png",
            f"ITO_{sample_folder_name}_resistance_bar.png",
            f"ITO_{sample_folder_name}_conductance_bar.png",
            f"ITO_{sample_folder_name}_last_neg_overlay.png",
            f"ITO_{sample_folder_name}_first_vs_last_resistance.png",
            f"ITO_{sample_folder_name}_start_end_dumbbell.png",
            f"ITO_{sample_folder_name}_start_vs_end_scatter.png",
            f"ITO_{sample_folder_name}_last_semilogy.png",
            f"ITO_{sample_folder_name}_conductivity_start_end.png",
            f"ITO_{sample_folder_name}_sheet_resistance_start_end.png",
            f"ITO_{sample_folder_name}_resistivity_start_end.png",
        ]
        table_candidate = os.path.join(output_dir, f"ITO_{sample_folder_name}_summary_table.png")
        for fn in candidate_plots:
            p = os.path.join(output_dir, fn)
            if os.path.isfile(p):
                dashboard_paths.append(p)
        # Append the table last if it exists
        if os.path.isfile(table_candidate):
            dashboard_paths.append(table_candidate)
        if dashboard_paths:
            cols = 3
            rows = math.ceil(len(dashboard_paths) / cols)
            fig, axes = plt.subplots(rows, cols, figsize=(cols*5.0, rows*4.0))
            axes = np.atleast_2d(axes)
            import matplotlib.image as mpimg
            for idx, img_path in enumerate(dashboard_paths):
                r = idx // cols
                c = idx % cols
                ax = axes[r, c]
                img = mpimg.imread(img_path)
                ax.imshow(img)
                ax.set_title(os.path.basename(img_path).replace(f"ITO_{sample_folder_name}_", ""), fontsize=8)
                ax.axis('off')
            # Hide any leftover axes
            for idx in range(len(dashboard_paths), rows*cols):
                r = idx // cols
                c = idx % cols
                axes[r, c].axis('off')
            out_path = os.path.join(output_dir, f"ITO_{sample_folder_name}_dashboard.png")
            plt.tight_layout()
            plt.savefig(out_path, dpi=180)
            plt.close(fig)
    except Exception:
        pass

    # Stats and plots: start vs end resistance
    if per_sweep_summary:
        # Build per-section start (sweep 1, Rpos) and end (sweep 3, Rneg)
        start_map: Dict[str, Optional[float]] = {}
        end_map: Dict[str, Optional[float]] = {}
        start_sigma: Dict[str, Optional[float]] = {}
        end_sigma: Dict[str, Optional[float]] = {}
        start_sigma_lo: Dict[str, Optional[float]] = {}
        start_sigma_hi: Dict[str, Optional[float]] = {}
        end_sigma_lo: Dict[str, Optional[float]] = {}
        end_sigma_hi: Dict[str, Optional[float]] = {}
        for row in per_sweep_summary:
            sec = row["section"]
            if row.get("sweep_index") == 1:
                start_map[sec] = row.get("R_pos_0_to_0p5_ohm")
                start_sigma[sec] = row.get("sigma_nominal_Spm")
                start_sigma_lo[sec] = row.get("sigma_lo_Spm")
                start_sigma_hi[sec] = row.get("sigma_hi_Spm")
            if row.get("sweep_index") == 3:
                end_map[sec] = row.get("R_neg_m0p5_to_0_ohm")
                end_sigma[sec] = row.get("sigma_nominal_Spm")
                end_sigma_lo[sec] = row.get("sigma_lo_Spm")
                end_sigma_hi[sec] = row.get("sigma_hi_Spm")
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
            stats_path = os.path.join(output_dir, f"ITO_{sample_folder_name}_start_end_stats.csv")
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
            plt.title(f"{sample_folder_name}: Start vs End Resistance")
            plt.grid(True, which='both', linestyle=':', linewidth=0.6)
            plt.legend()
            out_path = os.path.join(output_dir, f"ITO_{sample_folder_name}_start_vs_end_scatter.png")
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
            plt.title(f"{sample_folder_name}: Start vs End Resistance (Dumbbell)")
            plt.grid(True, axis='x', which='both', linestyle=':', linewidth=0.6)
            plt.legend()
            out_path = os.path.join(output_dir, f"ITO_{sample_folder_name}_start_end_dumbbell.png")
            plt.tight_layout()
            plt.savefig(out_path, dpi=200)
            plt.close()
        # Replace distribution plot with a table of metrics per section
        table_sections = sorted(set(list(start_map.keys()) + list(end_map.keys())))
        if table_sections:
            # Build rows: section, R_start, R_end, G_end, sigma_end
            rows = []
            end_g_map = {row['section']: row.get('G_neg_S') for row in per_sweep_summary if row.get('sweep_index') == 3}
            end_sigma_map = {row['section']: row.get('sigma_nominal_Spm') for row in per_sweep_summary if row.get('sweep_index') == 3}
            end_sigma_lo_map = {row['section']: row.get('sigma_lo_Spm') for row in per_sweep_summary if row.get('sweep_index') == 3}
            end_sigma_hi_map = {row['section']: row.get('sigma_hi_Spm') for row in per_sweep_summary if row.get('sweep_index') == 3}
            for sec in table_sections:
                r_s = start_map.get(sec)
                r_e = end_map.get(sec)
                g_e = end_g_map.get(sec)
                s_e = end_sigma_map.get(sec)
                rows.append([
                    sec,
                    (f"{r_s:.3g}" if (r_s is not None and np.isfinite(r_s)) else "n/a"),
                    (f"{r_e:.3g}" if (r_e is not None and np.isfinite(r_e)) else "n/a"),
                    (format_engineering_S(g_e) if (g_e is not None and np.isfinite(g_e)) else "n/a"),
                    (f"{s_e:.3g}" if (s_e is not None and np.isfinite(s_e)) else "n/a"),
                ])
            # Compute averages and bounds
            r_s_vals = np.array([v for v in start_map.values() if v is not None and np.isfinite(v)])
            g_e_vals = np.array([v for v in end_g_map.values() if v is not None and np.isfinite(v)])
            s_e_vals = np.array([v for v in end_sigma_map.values() if v is not None and np.isfinite(v)])
            s_e_lo_vals = np.array([v for v in end_sigma_lo_map.values() if v is not None and np.isfinite(v)])
            s_e_hi_vals = np.array([v for v in end_sigma_hi_map.values() if v is not None and np.isfinite(v)])
            avg_r_s = np.nanmean(r_s_vals) if r_s_vals.size else np.nan
            avg_g_e = np.nanmean(g_e_vals) if g_e_vals.size else np.nan
            avg_s_e = np.nanmean(s_e_vals) if s_e_vals.size else np.nan
            lo_s_e = np.nanmean(s_e_lo_vals) if s_e_lo_vals.size else np.nan
            hi_s_e = np.nanmean(s_e_hi_vals) if s_e_hi_vals.size else np.nan

            fig, ax = plt.subplots(figsize=(9, max(3.5, 0.35*len(rows) + 1.6)))
            ax.axis('off')
            col_labels = ["Section", "R_start (Ω)", "R_end (Ω)", "G_end (S)", "σ_end (S/m)"]
            table = ax.table(cellText=rows, colLabels=col_labels, loc='center')
            table.auto_set_font_size(False)
            table.set_fontsize(8)
            table.scale(1, 1.2)
            title_lines = [f"{sample_folder_name}: Summary Table"]
            if np.isfinite(avg_r_s):
                title_lines.append(f"Avg R_start: {format_engineering(avg_r_s)}")
            if np.isfinite(avg_g_e):
                title_lines.append(f"Avg G_end: {format_engineering_S(avg_g_e)}")
            if np.isfinite(avg_s_e):
                avg_band = ""
                if np.isfinite(lo_s_e) and np.isfinite(hi_s_e):
                    avg_band = f" (avg bounds: {lo_s_e:.3g}..{hi_s_e:.3g})"
                title_lines.append(f"Avg σ_end: {avg_s_e:.3g} S/m{avg_band}")
            ax.set_title("\n".join(title_lines))
            out_path = os.path.join(output_dir, f"ITO_{sample_folder_name}_summary_table.png")
            plt.tight_layout()
            plt.savefig(out_path, dpi=200)
            plt.close()

        # Conductivity plots: start vs end with error bars
        sections_se = sorted(set([s for s, v in start_sigma.items() if v is not None]).intersection([s for s, v in end_sigma.items() if v is not None]))
        if sections_se:
            x = np.arange(len(sections_se))
            w = 0.38
            start_vals = [start_sigma[s] for s in sections_se]
            end_vals = [end_sigma[s] for s in sections_se]
            # Error bars from min/max around nominal
            start_err_lo = [max(0.0, (sv - (start_sigma_lo[s] if start_sigma_lo[s] is not None else sv))) for s, sv in zip(sections_se, start_vals)]
            start_err_hi = [max(0.0, ((start_sigma_hi[s] if start_sigma_hi[s] is not None else sv) - sv)) for s, sv in zip(sections_se, start_vals)]
            end_err_lo = [max(0.0, (ev - (end_sigma_lo[s] if end_sigma_lo[s] is not None else ev))) for s, ev in zip(sections_se, end_vals)]
            end_err_hi = [max(0.0, ((end_sigma_hi[s] if end_sigma_hi[s] is not None else ev) - ev)) for s, ev in zip(sections_se, end_vals)]
            plt.figure(figsize=(10, 5))
            plt.bar(x - w/2, start_vals, w, yerr=[start_err_lo, start_err_hi], label="Start σ", color="#76b7b2", capsize=3)
            plt.bar(x + w/2, end_vals, w, yerr=[end_err_lo, end_err_hi], label="End σ", color="#e15759", capsize=3)
            # Threshold lines
            for name, val in CONDUCTIVITY_THRESHOLDS.items():
                plt.axhline(val, linestyle='--', linewidth=1.0, color={'low':'#999', 'medium':'#666', 'high':'#333'}.get(name, '#888'), label=f"{name}={val:.0e} S/m")
            plt.xticks(x, sections_se)
            plt.ylabel("Conductivity σ (S/m)")
            plt.title(f"{sample_folder_name}: Conductivity start vs end with error bars")
            plt.grid(axis='y', linestyle=':', linewidth=0.6)
            plt.legend()
            out_path = os.path.join(output_dir, f"ITO_{sample_folder_name}_conductivity_start_end.png")
            plt.tight_layout()
            plt.savefig(out_path, dpi=200)
            plt.close()

        # Sheet resistance and resistivity plots (start vs end with error bars)
        if sections_se:
            # Build from per_sweep_summary again to ensure alignment of Rs and rho
            rs_start = {row['section']: row.get('Rsheet_nominal_ohm_sq') for row in per_sweep_summary if row.get('sweep_index') == 1}
            rs_end = {row['section']: row.get('Rsheet_nominal_ohm_sq') for row in per_sweep_summary if row.get('sweep_index') == 3}
            rs_lo_start = {row['section']: row.get('Rsheet_lo_ohm_sq') for row in per_sweep_summary if row.get('sweep_index') == 1}
            rs_hi_start = {row['section']: row.get('Rsheet_hi_ohm_sq') for row in per_sweep_summary if row.get('sweep_index') == 1}
            rs_lo_end = {row['section']: row.get('Rsheet_lo_ohm_sq') for row in per_sweep_summary if row.get('sweep_index') == 3}
            rs_hi_end = {row['section']: row.get('Rsheet_hi_ohm_sq') for row in per_sweep_summary if row.get('sweep_index') == 3}
            secs_rs = [s for s in sections_se if rs_start.get(s) is not None and rs_end.get(s) is not None]
            if secs_rs:
                x = np.arange(len(secs_rs))
                w = 0.38
                sv = [rs_start[s] for s in secs_rs]
                ev = [rs_end[s] for s in secs_rs]
                se_lo = [max(0.0, sv_i - (rs_lo_start[s] if rs_lo_start[s] is not None else sv_i)) for s, sv_i in zip(secs_rs, sv)]
                se_hi = [max(0.0, (rs_hi_start[s] if rs_hi_start[s] is not None else sv_i) - sv_i) for s, sv_i in zip(secs_rs, sv)]
                ee_lo = [max(0.0, ev_i - (rs_lo_end[s] if rs_lo_end[s] is not None else ev_i)) for s, ev_i in zip(secs_rs, ev)]
                ee_hi = [max(0.0, (rs_hi_end[s] if rs_hi_end[s] is not None else ev_i) - ev_i) for s, ev_i in zip(secs_rs, ev)]
                plt.figure(figsize=(10, 5))
                plt.bar(x - w/2, sv, w, yerr=[se_lo, se_hi], label="Start Rs", color="#59a14f", capsize=3)
                plt.bar(x + w/2, ev, w, yerr=[ee_lo, ee_hi], label="End Rs", color="#edc948", capsize=3)
                plt.xticks(x, secs_rs)
                plt.ylabel("Sheet resistance Rs (Ω/□)")
                plt.title(f"{sample_folder_name}: Sheet resistance start vs end")
                plt.grid(axis='y', linestyle=':', linewidth=0.6)
                plt.legend()
                out_path = os.path.join(output_dir, f"ITO_{sample_folder_name}_sheet_resistance_start_end.png")
                plt.tight_layout()
                plt.savefig(out_path, dpi=200)
                plt.close()

        if sections_se:
            rho_start = {row['section']: row.get('rho_nominal_ohm_m') for row in per_sweep_summary if row.get('sweep_index') == 1}
            rho_end = {row['section']: row.get('rho_nominal_ohm_m') for row in per_sweep_summary if row.get('sweep_index') == 3}
            rho_lo_start = {row['section']: row.get('rho_lo_ohm_m') for row in per_sweep_summary if row.get('sweep_index') == 1}
            rho_hi_start = {row['section']: row.get('rho_hi_ohm_m') for row in per_sweep_summary if row.get('sweep_index') == 1}
            rho_lo_end = {row['section']: row.get('rho_lo_ohm_m') for row in per_sweep_summary if row.get('sweep_index') == 3}
            rho_hi_end = {row['section']: row.get('rho_hi_ohm_m') for row in per_sweep_summary if row.get('sweep_index') == 3}
            secs_rho = [s for s in sections_se if rho_start.get(s) is not None and rho_end.get(s) is not None]
            if secs_rho:
                x = np.arange(len(secs_rho))
                w = 0.38
                sv = [rho_start[s] for s in secs_rho]
                ev = [rho_end[s] for s in secs_rho]
                se_lo = [max(0.0, sv_i - (rho_lo_start[s] if rho_lo_start[s] is not None else sv_i)) for s, sv_i in zip(secs_rho, sv)]
                se_hi = [max(0.0, (rho_hi_start[s] if rho_hi_start[s] is not None else sv_i) - sv_i) for s, sv_i in zip(secs_rho, sv)]
                ee_lo = [max(0.0, ev_i - (rho_lo_end[s] if rho_lo_end[s] is not None else ev_i)) for s, ev_i in zip(secs_rho, ev)]
                ee_hi = [max(0.0, (rho_hi_end[s] if rho_hi_end[s] is not None else ev_i) - ev_i) for s, ev_i in zip(secs_rho, ev)]
                plt.figure(figsize=(10, 5))
                plt.bar(x - w/2, sv, w, yerr=[se_lo, se_hi], label="Start ρ", color="#af7aa1", capsize=3)
                plt.bar(x + w/2, ev, w, yerr=[ee_lo, ee_hi], label="End ρ", color="#ff9da7", capsize=3)
                plt.xticks(x, secs_rho)
                plt.ylabel("Resistivity ρ (Ω·m)")
                plt.title(f"{sample_folder_name}: Resistivity start vs end")
                plt.grid(axis='y', linestyle=':', linewidth=0.6)
                plt.legend()
                out_path = os.path.join(output_dir, f"ITO_{sample_folder_name}_resistivity_start_end.png")
                plt.tight_layout()
                plt.savefig(out_path, dpi=200)
                plt.close()

    # Simple console output for quick check (ASCII-safe)
    print(f"Analyzed sample: {sample_folder_name}")
    print(f"Sections found: {[os.path.basename(p) for p in section_dirs]}")
    if per_sweep_summary:
        print("First-sweep resistances (0->0.5 V):")
        for row in [r for r in per_sweep_summary if r.get("sweep_index") == 1]:
            label_ascii = str(row['R_pos_label']).replace('Ω', 'Ohm')
            g_label = format_engineering_S(row.get('G_pos_S')) if row.get('G_pos_S') is not None else 'n/a'
            sigma_nom = row.get('sigma_nominal_Spm')
            sigma_str = f"{sigma_nom:.3g} S/m" if sigma_nom is not None and np.isfinite(sigma_nom) else 'n/a'
            print(f"  {row['section']}: R={label_ascii}, G={g_label}, sigma={sigma_str}  ({'X' if row['ohmic']=='X' else 'ohmic'})")


def main() -> None:
    if PROCESS_ALL_SAMPLES:
        # find subfolders in ONEDRIVE_ROOT that look like sample folders
        try:
            for entry in sorted(os.listdir(ONEDRIVE_ROOT)):
                full = os.path.join(ONEDRIVE_ROOT, entry)
                if os.path.isdir(full) and entry not in EXCLUDE_SAMPLES:
                    try:
                        analyze_sample(entry)
                    except Exception as e:
                        print(f"Error analyzing sample '{entry}': {e}")
        except Exception as e:
            print(f"Error listing ONEDRIVE_ROOT: {e}")
    else:
        analyze_sample(SAMPLE_FOLDER_NAME)

if __name__ == "__main__":
    main()









