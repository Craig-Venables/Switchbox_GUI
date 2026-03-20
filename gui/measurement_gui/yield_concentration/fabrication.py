"""
Fabrication Metadata Lookup
============================

Reads 'solutions and devices.xlsx' to retrieve per-substrate fabrication
parameters: Np Concentration, Qd Spacing, Polymer, Volume Fraction, etc.

This is a port of `save_info_from_solution_devices_excell()` from the
Analysis_of_data project, adapted to work standalone within Switchbox_GUI
and without any file-saving side effects.

All devices on the same substrate share one fabrication row — the lookup key
is the *sample name* (which maps to "Device Full Name" in the Excel).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Optional

import pandas as pd


def get_fabrication_info(
    sample_name: str,
    excel_path: str,
    log_fn: Callable[[str], None] = print,
) -> Optional[Dict[str, Any]]:
    """Look up fabrication metadata for *sample_name* in solutions and devices.xlsx.

    Parameters
    ----------
    sample_name:
        Exact string that appears in the "Device Full Name" column of the
        "Memristor Devices" sheet (e.g. "D17-Stock-Gold-PMMA(0.25%)-Gold-s1").
    excel_path:
        Absolute path to the 'solutions and devices.xlsx' workbook.
    log_fn:
        Logging callback.

    Returns
    -------
    dict or None
        Dict of fabrication parameters, or None if the device is not found.
    """
    if not excel_path or not Path(excel_path).exists():
        log_fn(f"[FABRICATION] Excel not found: {excel_path!r}")
        return None

    try:
        with pd.ExcelFile(excel_path, engine="openpyxl") as xls:
            df_devices = pd.read_excel(xls, sheet_name="Memristor Devices")
            df_overview = pd.read_excel(xls, sheet_name="Devices Overview")

        row = df_devices[df_devices["Device Full Name"] == sample_name]
        if row.empty:
            log_fn(f"[FABRICATION] '{sample_name}' not found in 'Memristor Devices'.")
            return None

        r = row.iloc[0]
        info: Dict[str, Any] = {
            "Device Full Name": r.get("Device Full Name"),
            "B-Electrode (nm)": r.get("B-Electrode (nm)"),
            "B-Material": r.get("B-Material"),
            "Solution 1 ID": r.get("Solution 1 ID"),
            "Solution 2 ID": r.get("Solution 2 ID"),
            "Solution 3 ID": r.get("Solution 3 ID"),
            "Solution 4 ID": r.get("Solution 4 ID"),
            "T-Electrode (nm)": r.get("T-Electrode (nm)"),
            "T-Material": r.get("T-Material"),
            "Np Type": r.get("Np Type"),
            "Np Concentraion": r.get("Np Concentraion"),  # original typo preserved
            "Polymer": r.get("Polymer"),
            "Annealing": r.get("Annealing"),
            "Controll?": r.get("Controll?"),
        }

        # Devices Overview sheet
        row_ov = df_overview[df_overview["Device Full Name"] == sample_name]
        if not row_ov.empty:
            ov = row_ov.iloc[0]
            info.update({
                "Volume Fraction": ov.get("Volume fraction"),
                "Volume Fraction %": ov.get("Volume fraction %"),
                "Weight Fraction": ov.get("Weight Fraction"),
                "Qd Spacing (nm)": ov.get("Qd Spacing (nm)"),
                "Separation Distance": ov.get("Seperation Distance"),
                "Concentration of Qd (mg/ml)": ov.get("Concentration of Qd (mg/ml)"),
            })
        else:
            log_fn(f"[FABRICATION] '{sample_name}' not found in 'Devices Overview'.")

        # Np Concentration normalisation — treat "Stock" / blank as 0
        raw_conc = info.get("Np Concentraion")
        if isinstance(raw_conc, str) and raw_conc.strip().lower() in ("stock", ""):
            info["Np Concentration"] = 0.0
        else:
            try:
                info["Np Concentration"] = float(raw_conc) if raw_conc is not None else None
            except (TypeError, ValueError):
                info["Np Concentration"] = None

        # Solutions lookup
        _enrich_solutions(info, excel_path, log_fn)

        return info

    except Exception as exc:
        log_fn(f"[FABRICATION] Error reading Excel: {exc}")
        return None


def _enrich_solutions(
    info: Dict[str, Any],
    excel_path: str,
    log_fn: Callable,
) -> None:
    """Add solution-level detail for each Solution ID found in *info*."""
    try:
        with pd.ExcelFile(excel_path, engine="openpyxl") as xls:
            df_sol = pd.read_excel(xls, sheet_name="Prepared Solutions")
    except Exception as exc:
        log_fn(f"[FABRICATION] Could not read 'Prepared Solutions': {exc}")
        return

    for key in ("Solution 1 ID", "Solution 2 ID", "Solution 3 ID", "Solution 4 ID"):
        sol_id = info.get(key)
        if not sol_id or pd.isna(sol_id):
            continue
        matches = df_sol[df_sol["Solution Id"] == sol_id]
        if matches.empty:
            continue
        s = matches.iloc[0]
        prefix = key  # e.g. "Solution 1 ID"
        info[f"Np solution mg/ml {prefix}"] = s.get("Np solution (mg/ml)")
        info[f"Polymer 1 {prefix}"] = s.get("Polymer 1")
        info[f"Polymer 2 {prefix}"] = s.get("Polymer 2")
        info[f"Polymer % {prefix}"] = s.get("Polymer %")
        info[f"Calculated mg/ml {prefix}"] = s.get("Calculated mg/ml")
        info[f"Np Material {prefix}"] = s.get("Np Material")
        info[f"Np Size (nm) {prefix}"] = s.get("Np Size (nm)")
        info[f"Stock Np Solution Concentration {prefix}"] = s.get("Stock Np Solution Concentration (mg/ml)")
