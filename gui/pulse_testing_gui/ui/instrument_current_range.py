"""
Instrument current-range UI helpers (PMU IRange vs SMU measurement range).
"""

from __future__ import annotations

import tkinter as tk
from typing import Any, Optional

from Pulse_Testing.keithley4200_constants import (
    KEITHLEY4200_PMU_TIMING_SYSTEMS,
    KEITHLEY4200_SMU_OPTICAL_SYSTEMS,
)

DEFAULT_PMU_I_RANGE_A = 1e-4

PMU_PARAMS_HINT = (
    "4200 PMU: widths/rises in us (0.1 = 100 ns). Fast writes OK; use wider Read Width for "
    "stable R. Set PMU Current Range (A) below — details in Help > 4200 PMU tab."
)


def is_pmu_profile(system_name: Optional[str]) -> bool:
    return bool(system_name) and system_name in KEITHLEY4200_PMU_TIMING_SYSTEMS


def uses_smu_current_range_setting(system_name: Optional[str]) -> bool:
    """Profiles where settings apply SMU hardware range (not PMU EX IRange)."""
    if not system_name or is_pmu_profile(system_name):
        return False
    if system_name in KEITHLEY4200_SMU_OPTICAL_SYSTEMS:
        return True
    return system_name in ("keithley2450", "keithley2450_sim", "keithley2400")


def should_show_current_range_setting(system_name: Optional[str]) -> bool:
    """Connection/settings current range is for SMU/2450 only; PMU uses test parameters."""
    return uses_smu_current_range_setting(system_name)


def register_current_range_row(
    gui: Any,
    frame,
    label_widget=None,
    hint_widget=None,
) -> None:
    """Track a current-range row for show/hide and label updates."""
    rows = getattr(gui, "_current_range_rows", None)
    if rows is None:
        rows = []
        gui._current_range_rows = rows
    rows.append({"frame": frame, "label": label_widget, "hint": hint_widget})


def update_instrument_current_range_ui(gui: Any, system_name: Optional[str] = None) -> None:
    """Show PMU or SMU current-range control; hide when not applicable."""
    system = system_name or getattr(gui, "current_system_name", None)
    if system is None and hasattr(gui, "system_var"):
        try:
            system = gui.system_var.get()
        except Exception:
            system = None

    show = should_show_current_range_setting(system)
    pmu = is_pmu_profile(system)

    for row in getattr(gui, "_current_range_rows", []):
        frame = row.get("frame")
        if frame is None:
            continue
        if show:
            frame.pack(fill=tk.X, pady=(3, 1))
            label = row.get("label")
            hint = row.get("hint")
            if label is not None:
                label.config(
                    text="PMU current range (A):" if pmu else "SMU current range (A):"
                )
            if hint is not None:
                if pmu:
                    hint.config(
                        text="(EX IRange - see Help > 4200 PMU tab)"
                    )
                else:
                    hint.config(text="[0 = auto]")
        else:
            frame.pack_forget()

    hint_label = getattr(gui, "pmu_params_hint", None)
    if hint_label is not None:
        if pmu:
            hint_label.config(text=PMU_PARAMS_HINT)
            hint_label.pack(fill=tk.X, padx=3, pady=(0, 4))
        else:
            hint_label.config(text="")
            hint_label.pack_forget()

    var = getattr(gui, "instrument_current_range_var", None) or getattr(
        gui, "smu_current_range_var", None
    )
    if pmu and var is not None:
        try:
            if float(var.get()) <= 0:
                var.set(DEFAULT_PMU_I_RANGE_A)
        except Exception:
            var.set(DEFAULT_PMU_I_RANGE_A)
