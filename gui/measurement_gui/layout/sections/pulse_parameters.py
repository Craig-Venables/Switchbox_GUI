"""
Pulse Parameters Section
========================

Collapsible pulse parameters with single pulse and forming controls.
"""

from __future__ import annotations

import tkinter as tk
from typing import Any

from ..constants import COLOR_BG, FONT_MAIN
from ._collapsible import build_collapsible_section


def build_pulse_parameters(builder: Any, parent: tk.Misc) -> None:
    """Build the Pulse Parameters collapsible section."""
    gui = builder.gui

    def build_content(content_frame: tk.Frame) -> None:
        content_frame.columnconfigure(1, weight=1)

        tk.Label(
            content_frame, text="Single Pulse", font=("Segoe UI", 10, "bold"), bg=COLOR_BG
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))

        tk.Label(content_frame, text="Voltage (V):", font=FONT_MAIN, bg=COLOR_BG).grid(row=1, column=0, sticky="w", pady=2)
        gui.pulse_single_voltage = tk.DoubleVar(value=5.0)
        tk.Entry(content_frame, textvariable=gui.pulse_single_voltage, font=FONT_MAIN, width=18).grid(
            row=1, column=1, sticky="w", pady=2
        )

        tk.Label(content_frame, text="Pulse Time (s):", font=FONT_MAIN, bg=COLOR_BG).grid(row=2, column=0, sticky="w", pady=2)
        gui.pulse_single_time = tk.DoubleVar(value=1.0)
        tk.Entry(content_frame, textvariable=gui.pulse_single_time, font=FONT_MAIN, width=18).grid(
            row=2, column=1, sticky="w", pady=2
        )

        tk.Label(content_frame, text="Read Voltage (V):", font=FONT_MAIN, bg=COLOR_BG).grid(row=3, column=0, sticky="w", pady=2)
        gui.pulse_single_read_voltage = tk.DoubleVar(value=0.1)
        tk.Entry(content_frame, textvariable=gui.pulse_single_read_voltage, font=FONT_MAIN, width=18).grid(
            row=3, column=1, sticky="w", pady=2
        )

        tk.Label(content_frame, text="Current Limit (A):", font=FONT_MAIN, bg=COLOR_BG).grid(row=4, column=0, sticky="w", pady=2)
        gui.pulse_single_icc = tk.DoubleVar(value=1e-3)
        tk.Entry(content_frame, textvariable=gui.pulse_single_icc, font=FONT_MAIN, width=18).grid(
            row=4, column=1, sticky="w", pady=2
        )

        btn_frame = tk.Frame(content_frame, bg=COLOR_BG)
        btn_frame.grid(row=5, column=0, columnspan=2, sticky="ew", pady=5)
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        tk.Button(
            btn_frame,
            text="Send Single Pulse",
            font=("Segoe UI", 9, "bold"),
            bg="#2196F3",
            fg="white",
            activebackground="#1976D2",
            activeforeground="white",
            relief="raised",
            cursor="hand2",
            pady=5,
            command=builder.callbacks.get("run_single_pulse"),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 3))

        tk.Button(
            btn_frame,
            text="Send Read Pulse",
            font=("Segoe UI", 9, "bold"),
            bg="#4CAF50",
            fg="white",
            activebackground="#388e3c",
            activeforeground="white",
            relief="raised",
            cursor="hand2",
            pady=5,
            command=builder.callbacks.get("run_read_pulse"),
        ).grid(row=0, column=1, sticky="ew", padx=(3, 0))

        gui.pulse_single_result = tk.StringVar(value="")
        tk.Label(
            content_frame, textvariable=gui.pulse_single_result, font=FONT_MAIN, bg=COLOR_BG, fg="#1976D2"
        ).grid(row=6, column=0, columnspan=2, sticky="w", pady=2)

        tk.Frame(content_frame, height=2, bg="#cccccc").grid(row=7, column=0, columnspan=2, sticky="ew", pady=10)

        tk.Label(
            content_frame, text="Memristor Forming", font=("Segoe UI", 10, "bold"), bg=COLOR_BG
        ).grid(row=8, column=0, columnspan=2, sticky="w", pady=(0, 5))

        tk.Label(content_frame, text="Start Voltage (V):", font=FONT_MAIN, bg=COLOR_BG).grid(row=9, column=0, sticky="w", pady=2)
        gui.forming_start_voltage = tk.DoubleVar(value=5.0)
        tk.Entry(content_frame, textvariable=gui.forming_start_voltage, font=FONT_MAIN, width=18).grid(row=9, column=1, sticky="w", pady=2)

        tk.Label(content_frame, text="Start Time (s):", font=FONT_MAIN, bg=COLOR_BG).grid(row=10, column=0, sticky="w", pady=2)
        gui.forming_start_time = tk.DoubleVar(value=1.0)
        tk.Entry(content_frame, textvariable=gui.forming_start_time, font=FONT_MAIN, width=18).grid(row=10, column=1, sticky="w", pady=2)

        tk.Label(content_frame, text="Pulses per Step:", font=FONT_MAIN, bg=COLOR_BG).grid(row=11, column=0, sticky="w", pady=2)
        gui.forming_pulses_per_step = tk.IntVar(value=10)
        tk.Entry(content_frame, textvariable=gui.forming_pulses_per_step, font=FONT_MAIN, width=18).grid(row=11, column=1, sticky="w", pady=2)

        tk.Label(content_frame, text="Time Increment (s):", font=FONT_MAIN, bg=COLOR_BG).grid(row=12, column=0, sticky="w", pady=2)
        gui.forming_time_increment = tk.DoubleVar(value=1.0)
        tk.Entry(content_frame, textvariable=gui.forming_time_increment, font=FONT_MAIN, width=18).grid(row=12, column=1, sticky="w", pady=2)

        tk.Label(content_frame, text="Max Time (s):", font=FONT_MAIN, bg=COLOR_BG).grid(row=13, column=0, sticky="w", pady=2)
        gui.forming_max_time = tk.DoubleVar(value=10.0)
        tk.Entry(content_frame, textvariable=gui.forming_max_time, font=FONT_MAIN, width=18).grid(row=13, column=1, sticky="w", pady=2)

        tk.Label(content_frame, text="Max Voltage (V):", font=FONT_MAIN, bg=COLOR_BG).grid(row=14, column=0, sticky="w", pady=2)
        gui.forming_max_voltage = tk.DoubleVar(value=10.0)
        tk.Entry(content_frame, textvariable=gui.forming_max_voltage, font=FONT_MAIN, width=18).grid(row=14, column=1, sticky="w", pady=2)

        tk.Label(content_frame, text="Current Limit (A):", font=FONT_MAIN, bg=COLOR_BG).grid(row=15, column=0, sticky="w", pady=2)
        gui.forming_current_limit = tk.DoubleVar(value=1e-3)
        tk.Entry(content_frame, textvariable=gui.forming_current_limit, font=FONT_MAIN, width=18).grid(row=15, column=1, sticky="w", pady=2)

        tk.Label(content_frame, text="Target Current (A):", font=FONT_MAIN, bg=COLOR_BG).grid(row=16, column=0, sticky="w", pady=2)
        gui.forming_target_current = tk.DoubleVar(value=1e-4)
        tk.Entry(content_frame, textvariable=gui.forming_target_current, font=FONT_MAIN, width=18).grid(row=16, column=1, sticky="w", pady=2)

        tk.Label(content_frame, text="Read Voltage (V):", font=FONT_MAIN, bg=COLOR_BG).grid(row=17, column=0, sticky="w", pady=2)
        gui.forming_read_voltage = tk.DoubleVar(value=0.1)
        tk.Entry(content_frame, textvariable=gui.forming_read_voltage, font=FONT_MAIN, width=18).grid(row=17, column=1, sticky="w", pady=2)

        forming_btn_frame = tk.Frame(content_frame, bg=COLOR_BG)
        forming_btn_frame.grid(row=18, column=0, columnspan=2, sticky="ew", pady=5)
        forming_btn_frame.columnconfigure(0, weight=1)
        forming_btn_frame.columnconfigure(1, weight=1)

        tk.Button(
            forming_btn_frame,
            text="Start Forming",
            font=("Segoe UI", 9, "bold"),
            bg="#4CAF50",
            fg="white",
            activebackground="#388e3c",
            activeforeground="white",
            relief="raised",
            cursor="hand2",
            pady=5,
            command=builder.callbacks.get("start_forming_measurement"),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 3))

        tk.Button(
            forming_btn_frame,
            text="Stop",
            font=("Segoe UI", 9, "bold"),
            bg="#f44336",
            fg="white",
            activebackground="#d32f2f",
            activeforeground="white",
            relief="raised",
            cursor="hand2",
            pady=5,
            command=builder.callbacks.get("stop_forming_measurement"),
        ).grid(row=0, column=1, sticky="ew", padx=(3, 0))

        gui.forming_status = tk.StringVar(value="")
        tk.Label(
            content_frame,
            textvariable=gui.forming_status,
            font=FONT_MAIN,
            bg=COLOR_BG,
            fg="#1976D2",
            wraplength=300,
        ).grid(row=19, column=0, columnspan=2, sticky="w", pady=5)

        content_frame.columnconfigure(1, weight=1)

    container = build_collapsible_section(
        parent,
        "⚡ Pulse Parameters",
        build_content,
        start_expanded=False,
        content_bg=COLOR_BG,
    )
    builder.widgets["pulse_parameters_collapsible"] = container
