"""
Yield Analysis Orchestrator
==============================

Supports two modes, auto-detected from the selected folder:

  **Multi-sample mode** (folder contains multiple sample subdirs)
      - One row per sample in ``sample_df`` (yield fraction, concentration, etc.)
      - One row per device across all samples in ``device_df``
      - Sample-level plots (yield vs concentration, etc.) + device-level plots

  **Single-sample mode** (folder IS a sample dir)
      - Per-device DataFrame only
      - Device-level plots (resistance per device, etc.)

Auto-detect heuristic
---------------------
A directory is treated as a **sample dir** when it contains at least one
single-letter subfolder (A–Z) that itself contains numeric device subfolders.
Otherwise, if it contains at least one such sample subdir, it is a **root dir**.

Main entry points
-----------------
    run_yield_analysis(root_or_sample_dir, ...)     <- auto-detect
    run_multi_sample_analysis(sample_dirs, ...)     <- explicit multi
    run_single_sample_analysis(sample_dir, ...)     <- explicit single
"""

from __future__ import annotations

import os
from typing import Callable, List, Optional, Tuple

import pandas as pd

from gui.measurement_gui.yield_concentration.yield_source import (
    resolve_yield,
    compute_sample_yield,
)
from gui.measurement_gui.yield_concentration.fabrication import get_fabrication_info
from gui.measurement_gui.yield_concentration.first_sweep_resistance import (
    get_resistance_for_all_devices,
)
from gui.measurement_gui.yield_concentration import plots as _plots


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_yield_analysis(
    root_or_sample_dir: str,
    excel_path: Optional[str] = None,
    selected_samples: Optional[List[str]] = None,
    voltage_val: float = 0.1,
    manual_excel_dir: Optional[str] = None,
    log_fn: Callable[[str], None] = print,
) -> dict:
    """Auto-detect single vs multi-sample and run accordingly.

    Parameters
    ----------
    root_or_sample_dir:
        Either a root directory containing multiple sample subfolders, or a
        single sample directory.
    excel_path:
        Optional path to 'solutions and devices.xlsx'.
    selected_samples:
        For multi-sample mode: list of sample folder names (not full paths) to
        include.  ``None`` means include all discovered samples.
    voltage_val:
        Voltage window upper bound for resistance calculation.
    manual_excel_dir:
        Extra directory to search for manual classification Excel files.
    log_fn:
        Logging callback.
    """
    mode, sample_dirs = detect_mode(root_or_sample_dir)
    log_fn(f"[YIELD ANALYSIS] Detected mode: {mode} ({len(sample_dirs)} sample(s))")

    if mode == "single":
        return run_single_sample_analysis(
            sample_dir=root_or_sample_dir,
            sample_name=os.path.basename(root_or_sample_dir),
            excel_path=excel_path,
            voltage_val=voltage_val,
            manual_excel_dir=manual_excel_dir,
            log_fn=log_fn,
        )
    else:
        # Filter to selected samples if provided
        if selected_samples:
            sample_dirs = [d for d in sample_dirs if os.path.basename(d) in selected_samples]
        return run_multi_sample_analysis(
            sample_dirs=sample_dirs,
            root_dir=root_or_sample_dir,
            excel_path=excel_path,
            voltage_val=voltage_val,
            manual_excel_dir=manual_excel_dir,
            log_fn=log_fn,
        )


def detect_mode(path: str) -> Tuple[str, List[str]]:
    """Return (mode, sample_dirs) where mode is 'single' or 'multi'.

    ``sample_dirs`` is a list of full paths to discovered sample directories.
    For single mode it contains just the one path.
    """
    if _is_sample_dir(path):
        return "single", [path]
    sample_dirs = _discover_sample_dirs(path)
    if sample_dirs:
        return "multi", sample_dirs
    # fallback: treat as single even if no devices found
    return "single", [path]


def run_multi_sample_analysis(
    sample_dirs: List[str],
    root_dir: str,
    excel_path: Optional[str] = None,
    voltage_val: float = 0.1,
    manual_excel_dir: Optional[str] = None,
    log_fn: Callable[[str], None] = print,
) -> dict:
    """Run analysis across multiple samples.

    Builds:
    - ``sample_df``: one row per sample (sample_yield fraction, fabrication info)
    - ``device_df``: one row per device across all samples (binary yield, resistance)

    Both DataFrames are saved as CSVs and plots are generated for each.
    """
    log_fn(f"[YIELD ANALYSIS] Multi-sample mode: {len(sample_dirs)} sample(s)")
    sample_rows = []
    device_rows = []

    for sample_dir in sorted(sample_dirs):
        sample_name = os.path.basename(sample_dir)
        log_fn(f"[YIELD ANALYSIS] Processing sample: {sample_name}")

        device_ids = _discover_device_ids(sample_dir, sample_name, log_fn)
        if not device_ids:
            log_fn(f"[YIELD ANALYSIS]   No devices found in {sample_name} — skipping")
            continue

        # Yield
        per_device_yield = resolve_yield(
            sample_dir=sample_dir,
            sample_name=sample_name,
            device_ids=device_ids,
            log_fn=log_fn,
            manual_excel_dir=manual_excel_dir,
        )
        sample_yield_frac = compute_sample_yield(per_device_yield)

        # Fabrication
        fab_info = None
        if excel_path and os.path.exists(excel_path):
            fab_info = get_fabrication_info(sample_name, excel_path, log_fn)

        # First-sweep resistance
        resistance_results = get_resistance_for_all_devices(
            sample_dir=sample_dir,
            device_ids=device_ids,
            voltage_val=voltage_val,
            log_fn=log_fn,
        )

        # Sample-level row (yield fraction + shared fabrication)
        sample_rows.append(_make_sample_row(sample_name, sample_yield_frac, fab_info, per_device_yield))

        # Device-level rows (one per device)
        device_rows.extend(
            _make_device_rows(sample_name, device_ids, per_device_yield, fab_info, resistance_results)
        )

    sample_df = pd.DataFrame(sample_rows)
    device_df = pd.DataFrame(device_rows)

    _coerce_numeric(sample_df)
    _coerce_numeric(device_df)

    # Save outputs
    output_dir = os.path.join(root_dir, "yield_analysis")
    os.makedirs(output_dir, exist_ok=True)

    root_name = os.path.basename(root_dir)
    sample_csv = os.path.join(output_dir, f"{root_name}_sample_summary.csv")
    device_csv = os.path.join(output_dir, f"{root_name}_device_detail.csv")
    sample_df.to_csv(sample_csv, index=False)
    device_df.to_csv(device_csv, index=False)
    log_fn(f"[YIELD ANALYSIS] Sample CSV: {sample_csv}")
    log_fn(f"[YIELD ANALYSIS] Device CSV: {device_csv}")

    # Plots
    log_fn("[YIELD ANALYSIS] Generating sample-level plots…")
    sample_plots = _plots.generate_sample_level_plots(
        sample_df, output_dir, title_suffix=f" — {root_name}", log_fn=log_fn
    )
    log_fn("[YIELD ANALYSIS] Generating device-level plots…")
    device_plots = _plots.generate_device_level_plots(
        device_df, output_dir, title_suffix=f" — {root_name}", log_fn=log_fn
    )
    all_plots = sample_plots + device_plots
    log_fn(f"[YIELD ANALYSIS] {len(all_plots)} plot(s) saved to: {output_dir}")

    return {
        "mode": "multi",
        "sample_df": sample_df,
        "device_df": device_df,
        "output_dir": output_dir,
        "sample_yield": float(sample_df["sample_yield"].mean()) if not sample_df.empty and "sample_yield" in sample_df.columns else 0.0,
        "plots": all_plots,
        "sample_csv": sample_csv,
        "device_csv": device_csv,
    }


def run_single_sample_analysis(
    sample_dir: str,
    sample_name: str,
    excel_path: Optional[str] = None,
    voltage_val: float = 0.1,
    manual_excel_dir: Optional[str] = None,
    log_fn: Callable[[str], None] = print,
) -> dict:
    """Run analysis for a single sample — per-device DataFrame and plots."""
    log_fn(f"[YIELD ANALYSIS] Single-sample mode: {sample_name}")

    device_ids = _discover_device_ids(sample_dir, sample_name, log_fn)
    if not device_ids:
        log_fn("[YIELD ANALYSIS] No devices found — aborting.")
        return {"mode": "single", "device_df": pd.DataFrame(), "output_dir": None,
                "sample_yield": 0.0, "plots": [], "csv": None}

    log_fn(f"[YIELD ANALYSIS] Found {len(device_ids)} device(s)")

    per_device_yield = resolve_yield(
        sample_dir=sample_dir, sample_name=sample_name,
        device_ids=device_ids, log_fn=log_fn, manual_excel_dir=manual_excel_dir,
    )
    sample_yield_frac = compute_sample_yield(per_device_yield)
    log_fn(f"[YIELD ANALYSIS] Sample yield = {sample_yield_frac:.1%}")

    fab_info = None
    if excel_path and os.path.exists(excel_path):
        fab_info = get_fabrication_info(sample_name, excel_path, log_fn)

    resistance_results = get_resistance_for_all_devices(
        sample_dir=sample_dir, device_ids=device_ids, voltage_val=voltage_val, log_fn=log_fn,
    )

    device_df = pd.DataFrame(
        _make_device_rows(sample_name, device_ids, per_device_yield, fab_info, resistance_results)
    )
    _coerce_numeric(device_df)

    output_dir = os.path.join(sample_dir, "sample_analysis", "yield_analysis")
    os.makedirs(output_dir, exist_ok=True)

    csv_path = os.path.join(output_dir, f"{sample_name}_yield_analysis.csv")
    device_df.to_csv(csv_path, index=False)
    log_fn(f"[YIELD ANALYSIS] CSV saved: {csv_path}")

    # For a single sample we still generate device-level plots, and also a
    # mini sample-level summary so the user sees yield vs concentration if
    # they have at least one data point
    sample_df = pd.DataFrame([_make_sample_row(sample_name, sample_yield_frac, fab_info, per_device_yield)])
    _coerce_numeric(sample_df)

    log_fn("[YIELD ANALYSIS] Generating plots…")
    device_plots = _plots.generate_device_level_plots(
        device_df, output_dir, title_suffix=f" — {sample_name}", log_fn=log_fn
    )
    sample_plots = _plots.generate_sample_level_plots(
        sample_df, output_dir, title_suffix=f" — {sample_name}", log_fn=log_fn
    )
    all_plots = device_plots + sample_plots
    log_fn(f"[YIELD ANALYSIS] {len(all_plots)} plot(s) saved to: {output_dir}")

    return {
        "mode": "single",
        "device_df": device_df,
        "sample_df": sample_df,
        "output_dir": output_dir,
        "sample_yield": sample_yield_frac,
        "plots": all_plots,
        "csv": csv_path,
    }


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------

def _is_sample_dir(path: str) -> bool:
    """True when *path* looks like a single sample directory.

    Heuristic: contains at least one single-letter subfolder (A-Z) that
    itself contains at least one numeric device subfolder.
    """
    if not os.path.isdir(path):
        return False
    try:
        for entry in os.scandir(path):
            if entry.is_dir() and len(entry.name) == 1 and entry.name.isalpha():
                for sub in os.scandir(entry.path):
                    if sub.is_dir() and sub.name.isdigit():
                        return True
    except PermissionError:
        pass
    return False


def _discover_sample_dirs(root_dir: str) -> List[str]:
    """Return sorted list of full paths to sample subdirs inside *root_dir*."""
    result = []
    if not os.path.isdir(root_dir):
        return result
    try:
        for entry in sorted(os.scandir(root_dir), key=lambda e: e.name):
            if entry.is_dir() and _is_sample_dir(entry.path):
                result.append(entry.path)
    except PermissionError:
        pass
    return result


# ---------------------------------------------------------------------------
# Per-sample / per-device row builders
# ---------------------------------------------------------------------------

def _make_sample_row(
    sample_name: str,
    sample_yield_frac: float,
    fab_info: Optional[dict],
    per_device_yield: dict,
) -> dict:
    total = len(per_device_yield)
    memristive = sum(1 for v in per_device_yield.values() if v.get("yield", 0) == 1)
    yield_source = next(
        (v.get("source", "unknown") for v in per_device_yield.values()), "unknown"
    )
    row = {
        "sample_name": sample_name,
        "sample_yield": sample_yield_frac,
        "memristive_devices": memristive,
        "total_devices": total,
        "yield_source": yield_source,
        "Np Concentration": fab_info.get("Np Concentration") if fab_info else None,
        "Qd Spacing (nm)": fab_info.get("Qd Spacing (nm)") if fab_info else None,
        "Polymer": fab_info.get("Polymer") if fab_info else None,
        "Volume Fraction %": fab_info.get("Volume Fraction %") if fab_info else None,
    }
    return row


def _make_device_rows(
    sample_name: str,
    device_ids: list,
    per_device_yield: dict,
    fab_info: Optional[dict],
    resistance_results: dict,
) -> list:
    rows = []
    for device_id in device_ids:
        parts = device_id.rsplit("_", 2)
        section = parts[-2] if len(parts) >= 2 else ""
        dev_num = parts[-1] if len(parts) >= 1 else ""
        yield_data = per_device_yield.get(device_id, {})
        res_data = resistance_results.get(device_id, {})
        rows.append({
            "device_id": device_id,
            "sample_name": sample_name,
            "section": section,
            "device_number": dev_num,
            "yield": yield_data.get("yield", 0),
            "yield_source": yield_data.get("source", "unknown"),
            "classification_type": yield_data.get("classification_type", "unknown"),
            "Np Concentration": fab_info.get("Np Concentration") if fab_info else None,
            "Qd Spacing (nm)": fab_info.get("Qd Spacing (nm)") if fab_info else None,
            "Polymer": fab_info.get("Polymer") if fab_info else None,
            "Volume Fraction %": fab_info.get("Volume Fraction %") if fab_info else None,
            "avg_resistance_first_sweep": res_data.get("resistance"),
            "first_sweep_file": res_data.get("file"),
            "resistance_n_points": res_data.get("n_points"),
            "resistance_error": res_data.get("error"),
        })
    return rows


def _discover_device_ids(sample_dir: str, sample_name: str, log_fn: Callable) -> list:
    """Scan sample_dir for section/device subdirectories and device_tracking JSONs."""
    device_ids: list = []
    seen: set = set()

    for entry in sorted(os.scandir(sample_dir), key=lambda e: e.name):
        if not entry.is_dir() or len(entry.name) != 1 or not entry.name.isalpha():
            continue
        section = entry.name.upper()
        for dev_entry in sorted(os.scandir(entry.path), key=lambda e: e.name):
            if not dev_entry.is_dir():
                continue
            device_id = f"{sample_name}_{section}_{dev_entry.name}"
            if device_id not in seen:
                seen.add(device_id)
                device_ids.append(device_id)

    # Also include devices only in tracking
    for tracking_subdir in [
        os.path.join("sample_analysis", "analysis", "device_tracking"),
        os.path.join("sample_analysis", "device_tracking"),
        "device_tracking",
    ]:
        tracking_path = os.path.join(sample_dir, tracking_subdir)
        if not os.path.isdir(tracking_path):
            continue
        for fname in sorted(os.listdir(tracking_path)):
            if fname.endswith("_history.json"):
                device_id = fname[: -len("_history.json")]
                if device_id not in seen:
                    seen.add(device_id)
                    device_ids.append(device_id)
        break

    return device_ids


def _coerce_numeric(df: pd.DataFrame) -> None:
    for col in ("Np Concentration", "Qd Spacing (nm)", "Volume Fraction %",
                "avg_resistance_first_sweep", "sample_yield"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
