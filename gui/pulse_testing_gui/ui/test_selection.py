"""
Test selection section – test type dropdown and description.
Builds the Test Selection LabelFrame; gui must have on_test_selected.
"""

import tkinter as tk
from tkinter import ttk

from Pulse_Testing.test_definitions import get_test_definitions_for_gui


def build_test_selection_section(parent, gui):
    """Build Test Selection (dropdown + description). Sets gui.test_var, gui.test_combo, gui.desc_text."""
    frame = tk.LabelFrame(parent, text="Test Selection", padx=5, pady=5)
    frame.pack(fill=tk.X, padx=5, pady=5)

    tk.Label(frame, text="Test Type:", font=("TkDefaultFont", 9, "bold")).pack(anchor="w")
    gui.test_var = tk.StringVar()
    gui.test_combo = ttk.Combobox(frame, textvariable=gui.test_var,
                                  values=list(get_test_definitions_for_gui(gui.system_var.get()).keys()),
                                  state="readonly", width=35)
    gui.test_combo.pack(fill=tk.X, pady=5)
    gui.test_combo.bind("<<ComboboxSelected>>", gui.on_test_selected)
    gui.test_combo.current(0)

    smu_row = tk.Frame(frame)
    smu_row.pack(fill=tk.X, pady=(4, 0))
    tk.Label(smu_row, text="SMU current range (A) [0=auto]:", font=("TkDefaultFont", 8)).pack(side=tk.LEFT)
    if not hasattr(gui, "smu_current_range_var") or gui.smu_current_range_var is None:
        gui.smu_current_range_var = tk.DoubleVar(value=0.0)
    tk.Entry(smu_row, textvariable=gui.smu_current_range_var, width=12, font=("TkDefaultFont", 8)).pack(
        side=tk.LEFT, padx=4
    )

    tk.Label(frame, text="Description:", font=("TkDefaultFont", 8, "bold")).pack(anchor="w", pady=(3, 0))
    gui.desc_text = tk.Text(frame, height=3, wrap=tk.WORD, bg="#f0f0f0", relief=tk.FLAT, font=("TkDefaultFont", 8))
    gui.desc_text.pack(fill=tk.X, pady=1)
    gui.desc_text.config(state=tk.DISABLED)

    gui.on_test_selected(None)
