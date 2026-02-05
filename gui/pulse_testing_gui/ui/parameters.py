"""
Parameters section – presets, time unit, scrollable parameter inputs.
Builds the Test Parameters LabelFrame; gui must have load_preset, delete_preset, save_preset,
_on_unit_changed, load_presets_from_file, populate_parameters.
"""

import tkinter as tk
from tkinter import ttk


def build_parameters_section(parent, gui):
    """Build Test Parameters (presets, unit, params_frame, param_vars, populate). Sets gui.preset_var, gui.params_frame, gui.param_vars, gui.presets, etc."""
    frame = tk.LabelFrame(parent, text="Test Parameters", padx=5, pady=5)
    frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    preset_frame = tk.Frame(frame)
    preset_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
    tk.Label(preset_frame, text="Presets:", font=("TkDefaultFont", 9, "bold")).pack(side=tk.LEFT, padx=(0, 5))

    gui.preset_var = tk.StringVar()
    gui.preset_dropdown = ttk.Combobox(preset_frame, textvariable=gui.preset_var, state="readonly", width=20)
    gui.preset_dropdown.pack(side=tk.LEFT, padx=2)
    gui.preset_dropdown.bind("<<ComboboxSelected>>", lambda e: gui.load_preset())

    tk.Button(preset_frame, text="💾 Save", command=gui.save_preset, font=("TkDefaultFont", 8), width=6).pack(side=tk.LEFT, padx=2)
    tk.Button(preset_frame, text="🗑️ Del", command=gui.delete_preset, font=("TkDefaultFont", 8), width=6).pack(side=tk.LEFT, padx=2)

    unit_options = ["ns", "µs", "ms", "s"]
    default_unit = "µs" if getattr(gui, "current_system_name", None) in ("keithley4200a",) else "ms"
    gui.time_unit_var = tk.StringVar(value=default_unit)
    gui.previous_unit = default_unit
    unit_combo = ttk.Combobox(preset_frame, textvariable=gui.time_unit_var, values=unit_options, state="readonly", width=6, justify="center")
    unit_combo.pack(side=tk.RIGHT, padx=(5, 0))
    unit_combo.bind("<<ComboboxSelected>>", lambda e: gui._on_unit_changed())

    canvas = tk.Canvas(frame, height=450)
    scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
    gui.params_frame = tk.Frame(canvas)

    def update_canvas_window_width(event=None):
        canvas_width = canvas.winfo_width()
        if canvas_width > 1:
            canvas.itemconfig(canvas_window, width=canvas_width)

    gui.params_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas_window = canvas.create_window((0, 0), window=gui.params_frame, anchor="nw")
    canvas.bind("<Configure>", update_canvas_window_width)
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    gui.param_vars = {}
    gui.presets = gui.load_presets_from_file()
    gui.populate_parameters()
