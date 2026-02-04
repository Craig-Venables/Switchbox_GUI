"""
Motor Control GUI - Raster Scan Section
=======================================
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from gui.motor_control_gui import config
from gui.motor_control_gui.ui.widgets import CollapsibleFrame


def create_scan_controls(gui: Any, parent: tk.Frame) -> None:
    """Build scanning/raster controls."""
    c = config.COLORS
    collapsible = CollapsibleFrame(
        parent, "🔍 Raster Scan", bg_color=c["bg_dark"], fg_color=c["fg_primary"]
    )
    collapsible.pack(fill=tk.X, pady=3)
    gui.collapsible_sections.append(collapsible)

    scan_frame = collapsible.get_content_frame()
    scan_frame.configure(bg=c["bg_medium"])

    tk.Label(
        scan_frame,
        text="X Distance (mm):",
        fg=c["fg_primary"],
        bg=c["bg_medium"],
    ).grid(row=0, column=0, sticky="w", pady=2)
    tk.Entry(
        scan_frame,
        textvariable=gui.var_scan_x,
        bg=c["bg_light"],
        fg=c["fg_primary"],
        insertbackground=c["fg_primary"],
    ).grid(row=0, column=1, sticky="ew", pady=2)

    tk.Label(
        scan_frame,
        text="Y Distance (mm):",
        fg=c["fg_primary"],
        bg=c["bg_medium"],
    ).grid(row=1, column=0, sticky="w", pady=2)
    tk.Entry(
        scan_frame,
        textvariable=gui.var_scan_y,
        bg=c["bg_light"],
        fg=c["fg_primary"],
        insertbackground=c["fg_primary"],
    ).grid(row=1, column=1, sticky="ew", pady=2)

    tk.Label(
        scan_frame,
        text="Raster Count:",
        fg=c["fg_primary"],
        bg=c["bg_medium"],
    ).grid(row=2, column=0, sticky="w", pady=2)
    tk.Entry(
        scan_frame,
        textvariable=gui.var_scan_count,
        bg=c["bg_light"],
        fg=c["fg_primary"],
        insertbackground=c["fg_primary"],
    ).grid(row=2, column=1, sticky="ew", pady=2)

    tk.Label(
        scan_frame,
        text="Direction:",
        fg=c["fg_primary"],
        bg=c["bg_medium"],
    ).grid(row=3, column=0, sticky="w", pady=2)
    ttk.Combobox(
        scan_frame,
        textvariable=gui.var_scan_direction,
        values=["Horizontal", "Vertical"],
        state="readonly",
    ).grid(row=3, column=1, sticky="ew", pady=2)

    tk.Button(
        scan_frame,
        text="▶️ Start Scan",
        command=gui._start_scan,
        bg=c["accent_green"],
        fg="black",
        font=("Arial", 9, "bold"),
    ).grid(row=4, column=0, columnspan=2, sticky="ew", pady=(5, 0))

    scan_frame.columnconfigure(1, weight=1)
