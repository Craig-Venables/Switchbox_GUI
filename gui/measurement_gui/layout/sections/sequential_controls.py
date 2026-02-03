"""
Sequential Controls Section
===========================

Collapsible sequential measurement controls.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from ..constants import COLOR_BG, FONT_MAIN
from ._collapsible import build_collapsible_section


def build_sequential_controls(builder: Any, parent: tk.Misc) -> None:
    """Build the Sequential Measurements collapsible section."""
    gui = builder.gui

    def build_content(content_frame: tk.Frame) -> None:
        tk.Label(content_frame, text="Mode:", font=FONT_MAIN, bg=COLOR_BG).grid(row=0, column=0, sticky="w", pady=2)
        existing_mode = getattr(gui, "Sequential_measurement_var", "Iv Sweep")
        if hasattr(existing_mode, "get"):
            existing_mode = existing_mode.get()
        gui.Sequential_measurement_var = tk.StringVar(value=existing_mode or "Iv Sweep")
        ttk.Combobox(
            content_frame,
            textvariable=gui.Sequential_measurement_var,
            values=["Iv Sweep", "Single Avg Measure"],
            state="readonly",
            font=FONT_MAIN,
            width=18,
        ).grid(row=0, column=1, sticky="ew", pady=2)

        tk.Label(content_frame, text="# Passes:", font=FONT_MAIN, bg=COLOR_BG).grid(row=1, column=0, sticky="w", pady=2)
        gui.sequential_number_of_sweeps = tk.IntVar(value=getattr(gui, "sequential_number_of_sweeps", 100))
        tk.Entry(content_frame, textvariable=gui.sequential_number_of_sweeps, font=FONT_MAIN, width=18).grid(
            row=1, column=1, sticky="w", pady=2
        )

        tk.Label(content_frame, text="Voltage Limit (V):", font=FONT_MAIN, bg=COLOR_BG).grid(row=2, column=0, sticky="w", pady=2)
        gui.sq_voltage = tk.DoubleVar(value=1.0)
        tk.Entry(content_frame, textvariable=gui.sq_voltage, font=FONT_MAIN, width=18).grid(row=2, column=1, sticky="w", pady=2)

        tk.Label(content_frame, text="Delay (s):", font=FONT_MAIN, bg=COLOR_BG).grid(row=3, column=0, sticky="w", pady=2)
        gui.sq_time_delay = tk.DoubleVar(value=1.0)
        tk.Entry(content_frame, textvariable=gui.sq_time_delay, font=FONT_MAIN, width=18).grid(row=3, column=1, sticky="w", pady=2)

        tk.Label(content_frame, text="Duration/Device (s):", font=FONT_MAIN, bg=COLOR_BG).grid(row=4, column=0, sticky="w", pady=2)
        gui.measurement_duration_var = tk.DoubleVar(value=1.0)
        tk.Entry(content_frame, textvariable=gui.measurement_duration_var, font=FONT_MAIN, width=18).grid(
            row=4, column=1, sticky="w", pady=2
        )

        gui.live_plot_enabled = tk.BooleanVar(value=True)
        tk.Checkbutton(
            content_frame,
            text="Enable live plotting",
            variable=gui.live_plot_enabled,
            bg=COLOR_BG,
            font=FONT_MAIN,
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=5)

        btn_frame = tk.Frame(content_frame, bg=COLOR_BG)
        btn_frame.grid(row=6, column=0, columnspan=2, sticky="ew", pady=5)
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        tk.Button(
            btn_frame,
            text="Start Sequential",
            font=("Segoe UI", 10, "bold"),
            bg="#4CAF50",
            fg="white",
            activebackground="#388e3c",
            activeforeground="white",
            relief="raised",
            cursor="hand2",
            pady=8,
            command=builder.callbacks.get("start_sequential_measurement"),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 3))

        tk.Button(
            btn_frame,
            text="Stop",
            font=("Segoe UI", 10, "bold"),
            bg="#f44336",
            fg="white",
            activebackground="#d32f2f",
            activeforeground="white",
            relief="raised",
            cursor="hand2",
            pady=8,
            command=builder.callbacks.get("stop_sequential_measurement"),
        ).grid(row=0, column=1, sticky="ew", padx=(3, 0))

        content_frame.columnconfigure(1, weight=1)

    container = build_collapsible_section(
        parent,
        "🔁 Sequential Measurements",
        build_content,
        start_expanded=False,
        content_bg=COLOR_BG,
    )
    builder.widgets["sequential_controls_collapsible"] = container
