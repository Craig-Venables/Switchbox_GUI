"""
Quick Scan UI Builder
=====================

Creates the Quick Scan Results tab with scan parameters, overlay controls, and canvas.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Dict, Optional

from PIL import ImageTk


def create_quick_scan_ui(sample_gui: Any) -> None:
    """
    Set up widgets for the Quick Scan tab with overlay controls.

    Args:
        sample_gui: The SampleGUI instance. Must have quick_scan_frame, telegram_bots,
                    telegram_bot_name_var, telegram_enabled, and methods: _update_threshold_from_var,
                    start_quick_scan, stop_quick_scan, save_quick_scan_results, load_quick_scan_results,
                    _redraw_quick_scan_overlay, apply_threshold_to_undefined, export_device_status_excel,
                    _update_telegram_bot, _lerp_current, _current_to_color.
    """
    control_frame = ttk.Frame(sample_gui.quick_scan_frame, padding=(10, 10))
    control_frame.grid(row=0, column=0, sticky="ew")
    control_frame.columnconfigure(9, weight=1)

    ttk.Label(control_frame, text="Voltage (V):").grid(row=0, column=0, padx=(0, 5))
    sample_gui.quick_scan_voltage_var = tk.DoubleVar(value=0.2)
    sample_gui.quick_scan_voltage_spin = ttk.Spinbox(
        control_frame,
        from_=0.0,
        to=5.0,
        increment=0.05,
        textvariable=sample_gui.quick_scan_voltage_var,
        width=8,
    )
    sample_gui.quick_scan_voltage_spin.grid(row=0, column=1, padx=(0, 10))

    ttk.Label(control_frame, text="Settle (s):").grid(row=0, column=2, padx=(0, 5))
    sample_gui.quick_scan_settle_var = tk.DoubleVar(value=0.2)
    sample_gui.quick_scan_settle_spin = ttk.Spinbox(
        control_frame,
        from_=0.0,
        to=5.0,
        increment=0.05,
        textvariable=sample_gui.quick_scan_settle_var,
        width=8,
    )
    sample_gui.quick_scan_settle_spin.grid(row=0, column=3, padx=(0, 10))

    ttk.Label(control_frame, text="Threshold (A):").grid(row=0, column=4, padx=(0, 5))
    sample_gui.quick_scan_threshold_var = tk.StringVar(value="1.0e-7")
    threshold_spin = ttk.Spinbox(
        control_frame,
        from_=1e-12,
        to=1e-3,
        increment=1e-8,
        textvariable=sample_gui.quick_scan_threshold_var,
        width=12,
    )
    threshold_spin.grid(row=0, column=5, padx=(0, 10))
    threshold_spin.bind("<Return>", lambda e: sample_gui._update_threshold_from_var())
    threshold_spin.bind("<FocusOut>", lambda e: sample_gui._update_threshold_from_var())

    sample_gui.quick_scan_run_button = ttk.Button(control_frame, text="Run Scan", command=sample_gui.start_quick_scan)
    sample_gui.quick_scan_run_button.grid(row=0, column=6, padx=5)

    sample_gui.quick_scan_stop_button = ttk.Button(
        control_frame, text="Stop", command=sample_gui.stop_quick_scan, state=tk.DISABLED
    )
    sample_gui.quick_scan_stop_button.grid(row=0, column=7, padx=5)

    sample_gui.quick_scan_save_button = ttk.Button(
        control_frame, text="Save", command=sample_gui.save_quick_scan_results, state=tk.DISABLED
    )
    sample_gui.quick_scan_save_button.grid(row=0, column=8, padx=5)

    sample_gui.quick_scan_load_button = ttk.Button(
        control_frame, text="Load", command=sample_gui.load_quick_scan_results
    )
    sample_gui.quick_scan_load_button.grid(row=0, column=9, padx=5, sticky="w")

    sample_gui.quick_scan_status = ttk.Label(control_frame, text="Status: Idle")
    sample_gui.quick_scan_status.grid(row=0, column=10, padx=(10, 0), sticky="w")

    overlay_frame = ttk.Frame(sample_gui.quick_scan_frame, padding=(10, 5, 10, 5))
    overlay_frame.grid(row=1, column=0, sticky="ew")

    ttk.Label(overlay_frame, text="Overlays:").pack(side="left", padx=5)

    ttk.Checkbutton(
        overlay_frame,
        text="Show Quick Scan Results",
        variable=sample_gui.show_quick_scan_overlay,
        command=sample_gui._redraw_quick_scan_overlay,
    ).pack(side="left", padx=5)

    ttk.Checkbutton(
        overlay_frame,
        text="Show Device Status",
        variable=sample_gui.show_status_overlay,
        command=sample_gui._redraw_quick_scan_overlay,
    ).pack(side="left", padx=5)

    ttk.Button(
        overlay_frame,
        text="Apply Threshold to Undefined",
        command=sample_gui.apply_threshold_to_undefined,
        width=25,
    ).pack(side="left", padx=10)

    ttk.Button(
        overlay_frame,
        text="Export Status to Excel",
        command=sample_gui.export_device_status_excel,
        width=20,
    ).pack(side="left", padx=5)

    canvas_frame = ttk.Frame(sample_gui.quick_scan_frame, padding=(10, 0, 10, 10))
    canvas_frame.grid(row=2, column=0, sticky="nsew")
    canvas_frame.columnconfigure(0, weight=1)
    canvas_frame.rowconfigure(0, weight=1)

    sample_gui.quick_scan_canvas = tk.Canvas(
        canvas_frame,
        width=600,
        height=500,
        bg="white",
        highlightbackground="black",
    )
    sample_gui.quick_scan_canvas.grid(row=0, column=0, sticky="nsew")

    legend_frame = ttk.Frame(canvas_frame)
    legend_frame.grid(row=0, column=1, padx=(10, 0), sticky="ns")
    ttk.Label(legend_frame, text="Current Legend").grid(row=0, column=0, pady=(0, 5))
    legend_canvas = tk.Canvas(legend_frame, width=30, height=200, highlightthickness=0)
    legend_canvas.grid(row=1, column=0, sticky="ns")
    for i in range(200):
        color_ratio = i / 199
        current = sample_gui._lerp_current(color_ratio)
        color = sample_gui._current_to_color(current)
        legend_canvas.create_line(0, 199 - i, 30, 199 - i, fill=color)
    ttk.Label(legend_frame, text="≤1e-10 A").grid(row=2, column=0, pady=(5, 0))
    ttk.Label(legend_frame, text="≥1e-6 A").grid(row=3, column=0, pady=(0, 5))

    telegram_frame = ttk.LabelFrame(legend_frame, text="Telegram", padding=5)
    telegram_frame.grid(row=4, column=0, pady=(10, 0), sticky="ew")

    ttk.Label(telegram_frame, text="Bot:").grid(row=0, column=0, sticky="w", pady=2)
    bot_names = list(sample_gui.telegram_bots.keys())
    telegram_bot_combo = ttk.Combobox(
        telegram_frame,
        textvariable=sample_gui.telegram_bot_name_var,
        values=bot_names,
        width=18,
        state="readonly",
    )
    telegram_bot_combo.grid(row=1, column=0, sticky="ew", pady=2)
    if bot_names:
        sample_gui.telegram_bot_name_var.set(bot_names[0])
    telegram_bot_combo.bind("<<ComboboxSelected>>", lambda e: sample_gui._update_telegram_bot())

    ttk.Checkbutton(
        telegram_frame,
        text="Enable Notifications",
        variable=sample_gui.telegram_enabled,
        command=sample_gui._update_telegram_bot,
    ).grid(row=2, column=0, sticky="w", pady=(5, 0))

    telegram_frame.columnconfigure(0, weight=1)

    log_frame = ttk.Frame(sample_gui.quick_scan_frame, padding=(10, 0, 10, 10))
    log_frame.grid(row=3, column=0, sticky="nsew")
    log_frame.columnconfigure(0, weight=1)
    log_frame.rowconfigure(0, weight=1)

    sample_gui.quick_scan_log = tk.Text(log_frame, height=8, state=tk.DISABLED)
    sample_gui.quick_scan_log.grid(row=0, column=0, sticky="nsew")

    quick_scan_scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=sample_gui.quick_scan_log.yview)
    quick_scan_scrollbar.grid(row=0, column=1, sticky="ns")
    sample_gui.quick_scan_log.configure(yscrollcommand=quick_scan_scrollbar.set)

    sample_gui.quick_scan_canvas_image: Optional[ImageTk.PhotoImage] = None
    sample_gui.quick_scan_overlay_items: Dict[str, int] = {}
    sample_gui.quick_scan_results: Dict[str, float] = {}
