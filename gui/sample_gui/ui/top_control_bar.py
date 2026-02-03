"""
Top Control Bar UI Builder
==========================

Creates the top control bar with multiplexer, sample type, device dropdowns, and measure button.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from gui.sample_gui.config import multiplexer_types, sample_config


def create_top_control_bar(sample_gui: Any) -> None:
    """
    Create the top control bar with dropdowns and measure button.

    Args:
        sample_gui: The SampleGUI instance. Must have root and methods: update_multiplexer,
                    update_dropdowns, update_info_box, _show_help, open_measurement_window.
    """
    control_bar = ttk.Frame(sample_gui.root, relief=tk.RAISED, borderwidth=1)
    control_bar.grid(row=0, column=0, sticky="ew", padx=5, pady=5)

    ttk.Label(control_bar, text="Multiplexer:").pack(side="left", padx=(5, 2))
    sample_gui.Multiplexer_type_var = tk.StringVar()
    sample_gui.Multiplexer_dropdown = ttk.Combobox(
        control_bar,
        textvariable=sample_gui.Multiplexer_type_var,
        values=list(multiplexer_types.keys()),
        width=15,
        state="readonly",
    )
    sample_gui.Multiplexer_dropdown.pack(side="left", padx=(0, 10))
    sample_gui.Multiplexer_dropdown.bind("<<ComboboxSelected>>", sample_gui.update_multiplexer)

    ttk.Label(control_bar, text="Type:").pack(side="left", padx=(5, 2))
    sample_gui.sample_type_var = tk.StringVar()
    sample_gui.sample_dropdown = ttk.Combobox(
        control_bar,
        textvariable=sample_gui.sample_type_var,
        values=list(sample_config.keys()),
        width=15,
        state="readonly",
    )
    sample_gui.sample_dropdown.pack(side="left", padx=(0, 10))
    sample_gui.sample_dropdown.bind("<<ComboboxSelected>>", sample_gui.update_dropdowns)

    ttk.Label(control_bar, text="Device:").pack(side="left", padx=(5, 2))
    sample_gui.device_name_label = tk.Label(
        control_bar,
        text="No Device",
        font=("Segoe UI", 9, "bold"),
        fg="#888888",
        relief=tk.SUNKEN,
        padx=10,
        width=15,
        anchor="w",
    )
    sample_gui.device_name_label.pack(side="left", padx=(0, 10))

    ttk.Label(control_bar, text="Section:").pack(side="left", padx=(5, 2))
    sample_gui.section_var = tk.StringVar()
    sample_gui.section_dropdown = ttk.Combobox(
        control_bar,
        textvariable=sample_gui.section_var,
        width=4,
        state="readonly",
    )
    sample_gui.section_dropdown.pack(side="left", padx=(0, 10))
    sample_gui.section_dropdown.bind("<<ComboboxSelected>>", sample_gui.update_info_box)

    ttk.Label(control_bar, text="Device:").pack(side="left", padx=(5, 2))
    sample_gui.device_var = tk.StringVar()
    sample_gui.device_dropdown = ttk.Combobox(
        control_bar,
        textvariable=sample_gui.device_var,
        width=4,
        state="readonly",
    )
    sample_gui.device_dropdown.pack(side="left", padx=(0, 20))
    sample_gui.device_dropdown.bind("<<ComboboxSelected>>", sample_gui.update_info_box)

    ttk.Frame(control_bar).pack(side="left", expand=True)

    tk.Button(
        control_bar,
        text="Help / Guide",
        command=sample_gui._show_help,
        bg="#1565c0",
        fg="white",
        font=("Segoe UI", 9, "bold"),
        padx=12,
        pady=5,
        relief=tk.RAISED,
        cursor="hand2",
    ).pack(side="right", padx=5)

    sample_gui.measure_button = tk.Button(
        control_bar,
        text="Measure Selected Devices",
        command=sample_gui.open_measurement_window,
        bg="#4CAF50",
        fg="white",
        font=("Segoe UI", 10, "bold"),
        padx=20,
        pady=5,
        relief=tk.RAISED,
        borderwidth=2,
        cursor="hand2",
    )
    sample_gui.measure_button.pack(side="right", padx=10)
