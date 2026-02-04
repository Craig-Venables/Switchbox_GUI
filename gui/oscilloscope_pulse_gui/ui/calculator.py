"""Shunt resistor calculator section for Oscilloscope Pulse GUI."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import config as gui_config
from .widgets import create_collapsible_frame


def build_calculator_content(gui, frame):
    """Build shunt resistor calculator content."""
    input_row = ttk.Frame(frame)
    input_row.pack(fill="x", pady=2)

    ttk.Label(input_row, text="Test Voltage (V):").pack(side="left")
    gui.vars["calc_voltage"] = tk.StringVar(value="2.0")
    calc_v_entry = ttk.Entry(input_row, textvariable=gui.vars["calc_voltage"], width=8)
    calc_v_entry.pack(side="left", padx=5)

    ttk.Label(input_row, text="Expected Current (A):").pack(side="left", padx=(10, 0))
    gui.vars["calc_current"] = tk.StringVar(value="0.000001")
    calc_i_entry = ttk.Entry(input_row, textvariable=gui.vars["calc_current"], width=12)
    calc_i_entry.pack(side="left", padx=5)

    ttk.Label(input_row, text="Rule:").pack(side="left", padx=(10, 0))
    gui.vars["calc_rule"] = tk.StringVar(value="10")
    rule_combo = ttk.Combobox(
        input_row,
        textvariable=gui.vars["calc_rule"],
        values=["1", "10"],
        width=5,
        state="readonly",
    )
    rule_combo.pack(side="left", padx=5)
    ttk.Label(input_row, text="%").pack(side="left")

    tk.Button(
        input_row,
        text="Calculate",
        command=gui._calculate_shunt,
        bg="#4caf50",
        fg="white",
        font=(gui_config.FONT_FAMILY, 8, "bold"),
        relief=tk.FLAT,
        padx=10,
        pady=2,
    ).pack(side="left", padx=5)

    calc_v_entry.bind("<Return>", lambda e: gui._calculate_shunt())
    calc_i_entry.bind("<Return>", lambda e: gui._calculate_shunt())

    results_frame = ttk.Frame(frame)
    results_frame.pack(fill="x", pady=(5, 0))

    gui.vars["calc_result"] = tk.StringVar(value="Enter values and click Calculate")
    result_label = tk.Label(
        results_frame,
        textvariable=gui.vars["calc_result"],
        bg=gui_config.COLORS["bg"],
        fg=gui_config.COLORS["success_fg"],
        font=("Consolas", 8),
        justify="left",
        anchor="w",
        wraplength=400,
        relief=tk.SUNKEN,
        bd=1,
        padx=5,
        pady=5,
    )
    result_label.pack(fill="x")

    gui._build_quick_test_section(frame)


def create_calculator_frame(gui, parent):
    """Build collapsible shunt resistor calculator frame."""
    create_collapsible_frame(
        gui,
        parent,
        "📐 Shunt Resistor Calculator",
        lambda f: build_calculator_content(gui, f),
        default_expanded=False,
    )
