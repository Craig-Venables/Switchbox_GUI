"""
Advanced Tests Sections
=======================

Manual Endurance/Retention and Conditional Memristive Testing for the Advanced Tests tab.
Extracted from layout_builder for maintainability.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from ..constants import COLOR_BG, COLOR_SUCCESS, FONT_BUTTON, FONT_HEADING, FONT_MAIN


def build_manual_endurance_retention(builder: Any, parent: tk.Misc) -> None:
    """Build the Manual Endurance / Retention section."""
    gui = builder.gui

    frame = tk.LabelFrame(parent, text="Manual Endurance / Retention", padx=5, pady=5)
    frame.pack(fill="x", padx=5, pady=5)

    end_frame = tk.Frame(frame, bg=COLOR_BG)
    end_frame.pack(side="left", padx=(0, 10))
    ret_frame = tk.Frame(frame, bg=COLOR_BG)
    ret_frame.pack(side="left")

    # Endurance
    tk.Label(end_frame, text="Endurance", font=FONT_MAIN, bg=COLOR_BG).grid(row=0, column=0, columnspan=2, sticky="w")
    for r, (attr, label, default, vtype) in enumerate([
        ("end_set_v", "SET V", 1.5, tk.DoubleVar),
        ("end_reset_v", "RESET V", -1.5, tk.DoubleVar),
        ("end_pulse_ms", "Pulse (ms)", 1000, tk.DoubleVar),
        ("end_cycles", "Cycles", 100, tk.IntVar),
        ("end_read_v", "Read V", 0.2, tk.DoubleVar),
        ("end_read_pulse_ms", "Read Pulse (ms)", 100.0, tk.DoubleVar),
        ("end_inter_cycle_delay_s", "Cycle Delay (s)", 0.0, tk.DoubleVar),
    ], start=1):
        _add_param(end_frame, gui, attr, label, default, vtype, r)

    start_endurance_cb = builder.callbacks.get("start_manual_endurance") or getattr(gui, "start_manual_endurance", None)
    tk.Button(
        end_frame,
        text="Start Endurance",
        command=start_endurance_cb,
        font=FONT_BUTTON,
        bg=COLOR_SUCCESS,
        fg="white",
        state=tk.NORMAL if start_endurance_cb else tk.DISABLED,
    ).grid(row=8, column=0, columnspan=2, pady=(4, 0), sticky="w")

    # Retention
    tk.Label(ret_frame, text="Retention", font=FONT_MAIN, bg=COLOR_BG).grid(row=0, column=0, columnspan=2, sticky="w")
    for r, (attr, label, default, vtype) in enumerate([
        ("ret_set_v", "SET V", 1.5, tk.DoubleVar),
        ("ret_set_ms", "SET Time (ms)", 10, tk.DoubleVar),
        ("ret_read_v", "Read V", 0.2, tk.DoubleVar),
        ("ret_read_pulse_ms", "Read Pulse (ms)", 100.0, tk.DoubleVar),
        ("ret_number_reads", "# Reads", 30, tk.IntVar),
        ("ret_every_s", "Delay (s)", 10.0, tk.DoubleVar),
    ], start=1):
        _add_param(ret_frame, gui, attr, label, default, vtype, r)

    gui.ret_estimate_var = tk.StringVar(value="Total: ~300 s")
    tk.Label(ret_frame, textvariable=gui.ret_estimate_var, fg="grey", bg=COLOR_BG).grid(
        row=7, column=0, columnspan=2, sticky="w"
    )

    start_retention_cb = builder.callbacks.get("start_manual_retention") or getattr(gui, "start_manual_retention", None)
    tk.Button(
        ret_frame,
        text="Start Retention",
        command=start_retention_cb,
        font=FONT_BUTTON,
        bg=COLOR_SUCCESS,
        fg="white",
        state=tk.NORMAL if start_retention_cb else tk.DISABLED,
    ).grid(row=8, column=0, columnspan=2, pady=(4, 0), sticky="w")

    builder.widgets["manual_endurance_retention"] = frame


def _add_param(parent: tk.Frame, gui: Any, attr: str, label: str, default, var_type, row: int) -> None:
    """Helper to add a label + entry for a parameter."""
    tk.Label(parent, text=label, font=("Segoe UI", 9), bg=COLOR_BG).grid(row=row, column=0, sticky="w")
    existing = getattr(gui, attr, default)
    if hasattr(existing, "get"):
        existing = existing.get()
    setattr(gui, attr, var_type(value=existing or default))
    tk.Entry(parent, textvariable=getattr(gui, attr), width=10, font=("Segoe UI", 9)).grid(row=row, column=1, sticky="w")


def build_conditional_testing_section(builder: Any, parent: tk.Misc) -> None:
    """Build the Conditional Memristive Testing section."""
    gui = builder.gui

    frame = tk.LabelFrame(
        parent,
        text="Conditional Memristive Testing",
        font=FONT_HEADING,
        bg=COLOR_BG,
        padx=10,
        pady=10,
    )
    frame.pack(fill="x", padx=5, pady=5)
    frame.columnconfigure(1, weight=1)

    thresholds_frame = tk.LabelFrame(frame, text="Thresholds", font=FONT_MAIN, bg=COLOR_BG, padx=5, pady=5)
    thresholds_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=5)

    tk.Label(thresholds_frame, text="Basic Memristive (≥):", bg=COLOR_BG, font=FONT_MAIN).grid(row=0, column=0, sticky="w", padx=5)
    gui.conditional_basic_threshold = tk.DoubleVar(value=60.0)
    tk.Spinbox(
        thresholds_frame, from_=0, to=100, increment=1,
        textvariable=gui.conditional_basic_threshold, width=10,
    ).grid(row=0, column=1, sticky="w", padx=5)

    tk.Label(thresholds_frame, text="High Quality (≥):", bg=COLOR_BG, font=FONT_MAIN).grid(row=1, column=0, sticky="w", padx=5)
    gui.conditional_high_quality_threshold = tk.DoubleVar(value=80.0)
    tk.Spinbox(
        thresholds_frame, from_=0, to=100, increment=1,
        textvariable=gui.conditional_high_quality_threshold, width=10,
    ).grid(row=1, column=1, sticky="w", padx=5)

    gui.conditional_re_evaluate = tk.BooleanVar(value=True)
    tk.Checkbutton(
        frame,
        text="Re-evaluate during test (check score after basic test)",
        variable=gui.conditional_re_evaluate,
        font=FONT_MAIN,
        bg=COLOR_BG,
    ).grid(row=1, column=0, columnspan=2, sticky="w", pady=5)

    gui.conditional_include_memcapacitive = tk.BooleanVar(value=True)
    tk.Checkbutton(
        frame,
        text="Include memcapacitive devices (uncheck to test only memristive)",
        variable=gui.conditional_include_memcapacitive,
        font=FONT_MAIN,
        bg=COLOR_BG,
    ).grid(row=2, column=0, columnspan=2, sticky="w", pady=5)

    test_config_frame = tk.LabelFrame(frame, text="Test Configuration", font=FONT_MAIN, bg=COLOR_BG, padx=5, pady=5)
    test_config_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=5)
    test_config_frame.columnconfigure(1, weight=1)

    sweep_values = list(gui.custom_sweeps.keys()) if hasattr(gui, "custom_sweeps") and gui.custom_sweeps else []

    tk.Label(test_config_frame, text="Quick Test:", bg=COLOR_BG, font=FONT_MAIN).grid(row=0, column=0, sticky="w", padx=5)
    gui.conditional_quick_test = tk.StringVar(value="")
    ttk.Combobox(test_config_frame, textvariable=gui.conditional_quick_test, values=sweep_values, width=28, state="readonly").grid(row=0, column=1, sticky="ew", padx=5)

    tk.Label(test_config_frame, text="Basic Test:", bg=COLOR_BG, font=FONT_MAIN).grid(row=1, column=0, sticky="w", padx=5)
    gui.conditional_basic_test = tk.StringVar(value="")
    ttk.Combobox(test_config_frame, textvariable=gui.conditional_basic_test, values=sweep_values, width=28, state="readonly").grid(row=1, column=1, sticky="ew", padx=5)

    tk.Label(test_config_frame, text="High Quality Test:", bg=COLOR_BG, font=FONT_MAIN).grid(row=2, column=0, sticky="w", padx=5)
    gui.conditional_high_quality_test = tk.StringVar(value="")
    ttk.Combobox(test_config_frame, textvariable=gui.conditional_high_quality_test, values=sweep_values, width=28, state="readonly").grid(row=2, column=1, sticky="ew", padx=5)

    final_test_frame = tk.LabelFrame(frame, text="Final Test (After All Devices)", font=FONT_MAIN, bg=COLOR_BG, padx=5, pady=5)
    final_test_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=5)
    final_test_frame.columnconfigure(1, weight=1)

    gui.conditional_final_test_enabled = tk.BooleanVar(value=False)
    tk.Checkbutton(
        final_test_frame,
        text="Enable Final Test",
        variable=gui.conditional_final_test_enabled,
        font=FONT_MAIN,
        bg=COLOR_BG,
        command=lambda: builder._update_final_test_controls(gui),
    ).grid(row=0, column=0, columnspan=2, sticky="w", pady=5)

    tk.Label(final_test_frame, text="Selection Mode:", bg=COLOR_BG, font=FONT_MAIN).grid(row=1, column=0, sticky="w", padx=5)
    gui.conditional_final_test_mode = tk.StringVar(value="top_x")
    mode_combo = ttk.Combobox(
        final_test_frame,
        textvariable=gui.conditional_final_test_mode,
        values=["top_x", "all_above_score"],
        state="readonly",
        width=15,
    )
    mode_combo.grid(row=1, column=1, sticky="w", padx=5)
    mode_combo.bind("<<ComboboxSelected>>", lambda e: builder._update_final_test_controls(gui))

    top_x_frame = tk.Frame(final_test_frame, bg=COLOR_BG)
    top_x_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=5)

    top_x_label = tk.Label(top_x_frame, text="Top X Count:", bg=COLOR_BG, font=FONT_MAIN)
    top_x_label.grid(row=0, column=0, sticky="w", padx=5)
    gui.conditional_final_test_top_x = tk.IntVar(value=3)
    top_x_spinbox = tk.Spinbox(top_x_frame, from_=1, to=100, increment=1, textvariable=gui.conditional_final_test_top_x, width=10)
    top_x_spinbox.grid(row=0, column=1, sticky="w", padx=5)

    min_score_label = tk.Label(top_x_frame, text="Min Score:", bg=COLOR_BG, font=FONT_MAIN)
    min_score_label.grid(row=1, column=0, sticky="w", padx=5)
    gui.conditional_final_test_min_score = tk.DoubleVar(value=80.0)
    min_score_spinbox = tk.Spinbox(top_x_frame, from_=0, to=100, increment=1, textvariable=gui.conditional_final_test_min_score, width=10)
    min_score_spinbox.grid(row=1, column=1, sticky="w", padx=5)

    tk.Label(final_test_frame, text="Final Test:", bg=COLOR_BG, font=FONT_MAIN).grid(row=3, column=0, sticky="w", padx=5)
    gui.conditional_final_test_name = tk.StringVar(value="")
    final_test_combo = ttk.Combobox(final_test_frame, textvariable=gui.conditional_final_test_name, values=sweep_values, width=28, state="readonly")
    final_test_combo.grid(row=3, column=1, sticky="ew", padx=5)

    gui.conditional_final_test_widgets = {
        "mode_combo": mode_combo,
        "top_x_frame": top_x_frame,
        "final_test_combo": final_test_combo,
        "top_x_label": top_x_label,
        "top_x_spinbox": top_x_spinbox,
        "min_score_label": min_score_label,
        "min_score_spinbox": min_score_spinbox,
    }

    button_frame = tk.Frame(frame, bg=COLOR_BG)
    button_frame.grid(row=5, column=0, columnspan=2, pady=10)

    tk.Button(
        button_frame,
        text="Load Config",
        command=lambda: builder._load_conditional_config(gui),
        font=FONT_BUTTON,
        bg=COLOR_SUCCESS,
        fg="white",
        padx=10,
        pady=5,
    ).pack(side="left", padx=5)

    tk.Button(
        button_frame,
        text="Save Config",
        command=lambda: builder._save_conditional_config(gui),
        font=FONT_BUTTON,
        bg=COLOR_SUCCESS,
        fg="white",
        padx=10,
        pady=5,
    ).pack(side="left", padx=5)

    run_callback = builder.callbacks.get("run_conditional_testing") or getattr(gui, "run_conditional_testing", None)
    gui.conditional_testing_run_button = tk.Button(
        button_frame,
        text="Run Conditional Testing",
        command=run_callback,
        font=FONT_BUTTON,
        bg=COLOR_SUCCESS,
        fg="white",
        padx=10,
        pady=5,
        state=tk.NORMAL if (hasattr(gui, "connected") and gui.connected) else tk.DISABLED,
    )
    gui.conditional_testing_run_button.pack(side="left", padx=5)

    builder._update_conditional_testing_controls(gui)
    builder._update_final_test_controls(gui)

    builder.widgets["conditional_testing_section"] = frame
