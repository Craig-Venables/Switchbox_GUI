"""
Custom Measurement Section
=========================

Fallback Custom Measurements section when CustomMeasurementsBuilder fails.
Extracted from layout_builder for maintainability.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any


def build_custom_measurement_section(builder: Any, parent: tk.Misc) -> None:
    """Build the fallback Custom Measurements section (LabelFrame)."""
    gui = builder.gui
    frame = tk.LabelFrame(parent, text="Custom Measurements", padx=5, pady=5)
    frame.grid(row=3, column=0, padx=10, pady=5, sticky="ew")

    tk.Label(frame, text="Custom Measurement:").grid(row=0, column=0, sticky="w")
    test_names = getattr(gui, "test_names", [])
    default_test = test_names[0] if test_names else "Test"
    gui.custom_measurement_var = tk.StringVar(value=default_test)
    gui.custom_measurement_menu = ttk.Combobox(
        frame,
        textvariable=gui.custom_measurement_var,
        values=test_names,
        state="readonly" if test_names else "disabled",
    )
    gui.custom_measurement_menu.grid(row=0, column=1, padx=5)

    start_cb = builder.callbacks.get("start_custom_measurement_thread") or getattr(
        gui, "start_custom_measurement", None
    )
    gui.run_custom_button = tk.Button(
        frame,
        text="Run Custom",
        command=start_cb,
        state=tk.NORMAL if start_cb else tk.DISABLED,
    )
    gui.run_custom_button.grid(row=1, column=0, columnspan=2, pady=5)

    def toggle_pause() -> None:
        toggle_cb = builder.callbacks.get("toggle_custom_pause") or getattr(
            gui, "toggle_custom_pause", None
        )
        if not toggle_cb:
            return
        new_state = toggle_cb()
        try:
            gui.pause_button_custom.config(text="Resume" if new_state else "Pause")
        except Exception:
            pass

    gui.pause_button_custom = tk.Button(frame, text="Pause", width=10, command=toggle_pause)
    gui.pause_button_custom.grid(row=2, column=0, padx=5, pady=2, sticky="w")

    edit_cb = builder.callbacks.get("open_sweep_editor") or getattr(
        gui, "open_sweep_editor_popup", None
    )
    tk.Button(
        frame,
        text="Edit Sweeps",
        command=edit_cb,
        state=tk.NORMAL if edit_cb else tk.DISABLED,
    ).grid(row=2, column=1, padx=5, pady=2, sticky="w")

    frame.columnconfigure(1, weight=1)
    builder.widgets["custom_measurements"] = frame
