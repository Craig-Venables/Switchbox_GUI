"""
Device Selection Panel UI Builder
=================================

Creates the device selection panel with checkboxes and status indicators.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Dict


def create_device_selection_panel(sample_gui: Any) -> None:
    """
    Create the device selection panel with checkboxes and status indicators.

    Args:
        sample_gui: The SampleGUI instance. Must have device_selection_frame and
                    methods: select_all_devices, deselect_all_devices, invert_selection,
                    mark_selected_devices.
    """
    selection_container = ttk.LabelFrame(
        sample_gui.device_selection_frame,
        text="Device Selection",
        padding=5,
    )
    selection_container.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
    selection_container.grid_rowconfigure(1, weight=1)
    selection_container.grid_columnconfigure(0, weight=1)

    button_frame = ttk.Frame(selection_container)
    button_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))

    ttk.Button(button_frame, text="Select All", command=sample_gui.select_all_devices, width=10).pack(side="left", padx=2)
    ttk.Button(button_frame, text="Clear", command=sample_gui.deselect_all_devices, width=10).pack(side="left", padx=2)
    ttk.Button(button_frame, text="Invert", command=sample_gui.invert_selection, width=10).pack(side="left", padx=2)

    button_frame2 = ttk.Frame(selection_container)
    button_frame2.grid(row=2, column=0, sticky="ew", pady=5)

    ttk.Label(button_frame2, text="Mark Selected:").pack(side="left", padx=5)
    ttk.Button(
        button_frame2, text="✓ Working", command=lambda: sample_gui.mark_selected_devices("working"), width=10
    ).pack(side="left", padx=2)
    ttk.Button(
        button_frame2, text="✗ Broken", command=lambda: sample_gui.mark_selected_devices("broken"), width=10
    ).pack(side="left", padx=2)
    ttk.Button(
        button_frame2, text="? Reset", command=lambda: sample_gui.mark_selected_devices("undefined"), width=10
    ).pack(side="left", padx=2)

    scroll_frame = ttk.Frame(selection_container)
    scroll_frame.grid(row=1, column=0, sticky="nsew")

    canvas = tk.Canvas(scroll_frame, width=250, highlightthickness=0)
    scrollbar = ttk.Scrollbar(scroll_frame, orient="vertical", command=canvas.yview)
    sample_gui.scrollable_frame = ttk.Frame(canvas)

    sample_gui.scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
    )

    canvas.create_window((0, 0), window=sample_gui.scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    sample_gui.device_checkboxes: Dict[str, tk.Checkbutton] = {}
    sample_gui.checkbox_vars: Dict[str, tk.BooleanVar] = {}
    sample_gui.device_status_labels: Dict[str, tk.Label] = {}

    sample_gui.selection_status = tk.Label(
        selection_container,
        text="Selected: 0/0",
        font=("Segoe UI", 9, "bold"),
        fg="#4CAF50",
    )
    sample_gui.selection_status.grid(row=3, column=0, pady=5)
