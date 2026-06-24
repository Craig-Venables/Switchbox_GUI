"""
Parameters section – presets, time unit, scrollable parameter inputs.
Builds the Test Parameters LabelFrame; gui must have load_preset, delete_preset, save_preset,
_on_unit_changed, load_presets_from_file, populate_parameters.
"""

import tkinter as tk
from tkinter import ttk

from Pulse_Testing.keithley4200_constants import KEITHLEY4200_PMU_TIMING_SYSTEMS


def refresh_params_canvas(gui) -> None:
    """Resize the scrollable params canvas so entry columns stay visible."""
    canvas = getattr(gui, "_params_canvas", None)
    window_id = getattr(gui, "_params_canvas_window", None)
    if canvas is None or window_id is None:
        return
    canvas.update_idletasks()
    canvas_width = canvas.winfo_width()
    if canvas_width > 1:
        canvas.itemconfig(window_id, width=canvas_width)
    canvas.configure(scrollregion=canvas.bbox("all"))


def toggle_parameters_section(gui):
    """Toggle collapse/expand of parameters section."""
    if gui.params_collapsed.get():
        gui.params_content_frame.pack(fill=tk.BOTH, expand=True)
        gui.params_collapse_btn.config(text="▼")
        gui.params_collapsed.set(False)
        refresh_params_canvas(gui)
    else:
        gui.params_content_frame.pack_forget()
        gui.params_collapse_btn.config(text="▶")
        gui.params_collapsed.set(True)


def init_parameters_section(parent, gui, *, compact: bool = False) -> None:
    """Build parameters widgets without packing (allows test selection to appear above)."""
    frame = tk.LabelFrame(parent, text="Test Parameters", padx=3, pady=3)
    gui.params_section_frame = frame

    header_frame = tk.Frame(frame)
    header_frame.pack(fill=tk.X, pady=(0, 3))

    gui.params_collapsed = tk.BooleanVar(value=False)
    gui.params_collapse_btn = tk.Button(
        header_frame,
        text="▼",
        width=3,
        command=lambda: toggle_parameters_section(gui),
        font=("TkDefaultFont", 8),
        relief=tk.FLAT,
    )
    gui.params_collapse_btn.pack(side=tk.LEFT, padx=(0, 5))
    tk.Label(header_frame, text="Configure Test", font=("TkDefaultFont", 8, "bold")).pack(side=tk.LEFT, anchor="w")

    gui.params_content_frame = tk.Frame(frame)
    gui.params_content_frame.pack(fill=tk.BOTH, expand=True)

    preset_frame = tk.Frame(gui.params_content_frame)
    preset_frame.pack(fill=tk.X, padx=3, pady=(0, 3))
    tk.Label(preset_frame, text="Presets:", font=("TkDefaultFont", 8, "bold")).pack(side=tk.LEFT, padx=(0, 5))

    gui.preset_var = tk.StringVar()
    gui.preset_dropdown = ttk.Combobox(preset_frame, textvariable=gui.preset_var, state="readonly", width=20)
    gui.preset_dropdown.pack(side=tk.LEFT, padx=2)
    gui.preset_dropdown.bind("<<ComboboxSelected>>", lambda e: gui.load_preset())

    tk.Button(preset_frame, text="💾 Save", command=gui.save_preset, font=("TkDefaultFont", 8), width=6).pack(
        side=tk.LEFT, padx=2
    )
    tk.Button(preset_frame, text="🗑️ Del", command=gui.delete_preset, font=("TkDefaultFont", 8), width=6).pack(
        side=tk.LEFT, padx=2
    )

    if not compact:
        pass  # current range: connection bar (classic) or settings (compact)

    default_unit = "µs" if getattr(gui, "current_system_name", None) in KEITHLEY4200_PMU_TIMING_SYSTEMS else "ms"
    if not hasattr(gui, "time_unit_var"):
        gui.time_unit_var = tk.StringVar(value=default_unit)
        gui.previous_unit = default_unit
    unit_combo = ttk.Combobox(
        preset_frame,
        textvariable=gui.time_unit_var,
        values=["ns", "µs", "ms", "s"],
        state="readonly",
        width=6,
        justify="center",
    )
    unit_combo.pack(side=tk.RIGHT, padx=(5, 0))
    unit_combo.bind("<<ComboboxSelected>>", lambda e: gui._on_unit_changed())

    canvas_holder = tk.Frame(gui.params_content_frame)
    canvas_holder.pack(fill=tk.BOTH, expand=True)

    canvas_height = 340 if compact else 300
    canvas = tk.Canvas(canvas_holder, height=canvas_height, highlightthickness=0)
    scrollbar = ttk.Scrollbar(canvas_holder, orient="vertical", command=canvas.yview)
    gui.params_frame = tk.Frame(canvas)

    def update_canvas_window_width(event=None):
        canvas_width = canvas.winfo_width()
        if canvas_width > 1:
            canvas.itemconfig(canvas_window, width=canvas_width)

    def _on_params_configure(_event=None):
        canvas.configure(scrollregion=canvas.bbox("all"))

    gui.params_frame.bind("<Configure>", _on_params_configure)
    canvas_window = canvas.create_window((0, 0), window=gui.params_frame, anchor="nw")
    canvas.bind("<Configure>", update_canvas_window_width)
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    canvas.bind("<MouseWheel>", _on_mousewheel)
    gui.params_frame.bind("<MouseWheel>", _on_mousewheel)

    gui._params_canvas = canvas
    gui._params_canvas_window = canvas_window
    gui.refresh_params_canvas = lambda: refresh_params_canvas(gui)
    gui.param_vars = {}
    gui.presets = gui.load_presets_from_file()


def pack_parameters_section(gui, *, compact: bool = False) -> None:
    """Pack the parameters LabelFrame (call after test selection for visual order)."""
    if not hasattr(gui, "params_section_frame"):
        return
    padx = 5
    pady = (3, 5)
    if compact:
        padx = 5
    gui.params_section_frame.pack(fill=tk.BOTH, expand=True, padx=padx, pady=pady)
    gui.params_section_frame.update_idletasks()
    refresh_params_canvas(gui)


def build_parameters_section(parent, gui, *, compact: bool = False):
    """Build and pack Test Parameters in one step (legacy convenience)."""
    init_parameters_section(parent, gui, compact=compact)
    pack_parameters_section(gui, compact=compact)
