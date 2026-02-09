"""
Motor Control GUI - Controls Panel
===================================

Scrollable left panel with all control sections.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from gui.motor_control_gui import config
from gui.motor_control_gui.ui import (
    fg_controls,
    goto_controls,
    jog_controls,
    laser_controls,
    motor_settings,
    presets,
    scan_controls,
)


def create_controls_panel(gui: Any) -> None:
    """Build left control panel with scrollable sections."""
    c = config.COLORS
    controls_container = tk.Frame(gui.root, bg=c["bg_dark"], width=380)
    controls_container.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
    controls_container.grid_propagate(False)
    controls_container.rowconfigure(1, weight=1)
    controls_container.columnconfigure(0, weight=1)

    expand_collapse_frame = tk.Frame(controls_container, bg=c["bg_dark"])
    expand_collapse_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(0, 5))

    tk.Button(
        expand_collapse_frame,
        text="▼ Expand All",
        command=gui._expand_all_sections,
        bg=c["accent_blue"],
        fg="white",
        font=("Arial", 9),
        relief=tk.FLAT,
        padx=10,
        pady=3,
    ).pack(side=tk.LEFT, padx=2)

    tk.Button(
        expand_collapse_frame,
        text="▶ Collapse All",
        command=gui._collapse_all_sections,
        bg=c["accent_blue"],
        fg="white",
        font=("Arial", 9),
        relief=tk.FLAT,
        padx=10,
        pady=3,
    ).pack(side=tk.LEFT, padx=2)

    canvas = tk.Canvas(
        controls_container,
        bg=c["bg_dark"],
        highlightthickness=0,
    )
    scrollbar = ttk.Scrollbar(controls_container, orient="vertical", command=canvas.yview)
    scrollable_frame = tk.Frame(canvas, bg=c["bg_dark"])

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.grid(row=1, column=0, sticky="nsew")
    scrollbar.grid(row=1, column=1, sticky="ns")

    gui.collapsible_sections = []

    # Only Jog starts expanded; all other sections start collapsed
    jog_controls.create_jog_controls(gui, scrollable_frame, start_expanded=True)
    goto_controls.create_goto_controls(gui, scrollable_frame, start_expanded=False)
    motor_settings.create_motor_settings(gui, scrollable_frame, start_expanded=False)
    presets.create_presets(gui, scrollable_frame, start_expanded=False)
    scan_controls.create_scan_controls(gui, scrollable_frame, start_expanded=False)
    fg_controls.create_fg_controls(gui, scrollable_frame, start_expanded=False)
    laser_controls.create_laser_controls(gui, scrollable_frame, start_expanded=False)
