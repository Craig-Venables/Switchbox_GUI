"""
Custom Measurement Quick Select Section
=======================================

Collapsible quick selector for custom measurements.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from ..constants import COLOR_BG, FONT_BUTTON, FONT_MAIN
from ._collapsible import build_collapsible_section


def build_custom_measurement_quick(builder: Any, parent: tk.Misc) -> None:
    """Build the Custom Measurement quick select collapsible section."""
    gui = builder.gui

    def build_content(content_frame: tk.Frame) -> None:
        test_names = getattr(gui, "test_names", [])
        default_test = test_names[0] if test_names else "Test"
        gui.custom_measurement_var = tk.StringVar(value=default_test)

        tk.Label(content_frame, text="Select Test:", font=FONT_MAIN, bg=COLOR_BG).pack(anchor="w", pady=(0, 5))
        gui.custom_measurement_menu = ttk.Combobox(
            content_frame,
            textvariable=gui.custom_measurement_var,
            values=test_names,
            state="readonly" if test_names else "disabled",
            font=FONT_MAIN,
        )
        gui.custom_measurement_menu.pack(fill="x", pady=(0, 10))

        btn_frame = tk.Frame(content_frame, bg=COLOR_BG)
        btn_frame.pack(fill="x")
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        gui.run_custom_button = tk.Button(
            btn_frame,
            text="Run Custom",
            font=("Segoe UI", 10, "bold"),
            bg="#4CAF50",
            fg="white",
            activebackground="#388e3c",
            activeforeground="white",
            relief="raised",
            cursor="hand2",
            pady=8,
            command=builder.callbacks.get("start_custom_measurement_thread"),
        )
        gui.run_custom_button.grid(row=0, column=0, sticky="ew", padx=(0, 3))

        tk.Button(
            btn_frame,
            text="Edit Sweeps",
            font=FONT_BUTTON,
            bg="#2196f3",
            fg="white",
            activebackground="#1976d2",
            activeforeground="white",
            relief="raised",
            cursor="hand2",
            pady=6,
            command=builder.callbacks.get("open_sweep_editor"),
        ).grid(row=0, column=1, sticky="ew", padx=(3, 0))

        gui.pause_button_custom = tk.Button(
            content_frame,
            text="Pause",
            font=FONT_BUTTON,
            bg="#ff9800",
            fg="white",
            activebackground="#f57c00",
            activeforeground="white",
            relief="raised",
            cursor="hand2",
            pady=6,
            command=builder.callbacks.get("toggle_custom_pause"),
        )
        gui.pause_button_custom.pack(fill="x", pady=(5, 0))

    container = build_collapsible_section(
        parent,
        "🔬 Custom Measurement",
        build_content,
        start_expanded=False,
        content_bg=COLOR_BG,
    )
    builder.widgets["custom_measurement_quick"] = container
