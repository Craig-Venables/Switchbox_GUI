"""Top bar and help dialog for Oscilloscope Pulse GUI."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import config as gui_config
from .widgets import ToolTip


def create_top_bar(gui, parent):
    """Top banner with System selection, Save path, and Identity info."""
    bar_frame = tk.Frame(
        parent,
        bg=gui_config.COLORS["accent"],
        pady=8,
        padx=10,
        relief="raised",
        bd=1,
    )
    bar_frame.pack(fill="x", side="top")

    id_text = (
        f"Device: {gui.context.get('device_label', 'Unknown')} | "
        f"Sample: {gui.context.get('sample_name', 'Unknown')}"
    )
    ttk.Label(bar_frame, text=id_text, style="Header.TLabel").pack(side="left", padx=(0, 20))

    tk.Label(bar_frame, text="System:", bg=gui_config.COLORS["accent"]).pack(side="left")
    gui.vars["system"] = tk.StringVar(value=gui.config.get("system", "keithley4200a"))
    sys_combo = ttk.Combobox(
        bar_frame,
        textvariable=gui.vars["system"],
        values=gui.context.get("known_systems", ["keithley4200a", "keithley2450", "keithley2400"]),
        width=15,
        state="readonly",
    )
    sys_combo.pack(side="left", padx=5)
    sys_combo.bind("<<ComboboxSelected>>", lambda e: gui.callbacks.get("on_system_change", lambda: None)())

    gui.vars["simulation_mode"] = tk.BooleanVar(value=gui.config.get("simulation_mode", False))
    sim_check = ttk.Checkbutton(
        bar_frame,
        text="🔧 Simulation Mode",
        variable=gui.vars["simulation_mode"],
    )
    sim_check.pack(side="left", padx=(10, 0))
    ToolTip(sim_check, "Test without oscilloscope - generates simulated data")

    tk.Button(
        bar_frame,
        text="Help / Guide",
        command=lambda: show_help_dialog(parent),
        bg=gui_config.COLORS["header"],
        fg="white",
        font=(gui_config.FONT_FAMILY, 9, "bold"),
    ).pack(side="right", padx=10)

    tk.Button(
        bar_frame,
        text="Save Location...",
        command=gui.callbacks["browse_save"],
        font=(gui_config.FONT_FAMILY, 8),
    ).pack(side="right", padx=5)
    gui.vars["save_dir"] = tk.StringVar(value=gui.context.get("save_directory", "Default"))
    tk.Label(
        bar_frame,
        textvariable=gui.vars["save_dir"],
        bg=gui_config.COLORS["accent"],
        fg=gui_config.COLORS["fg_secondary"],
        width=30,
        anchor="e",
    ).pack(side="right")


def show_help_dialog(parent):
    """Display help window with setup instructions."""
    help_win = tk.Toplevel(parent)
    help_win.title("Setup Guide & Instructions")
    help_win.geometry("800x700")
    help_win.configure(bg=gui_config.COLORS["bg"])

    canvas = tk.Canvas(help_win, bg=gui_config.COLORS["bg"])
    scrollbar = ttk.Scrollbar(help_win, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)

    scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    pad = {"padx": 20, "pady": 10, "anchor": "w"}

    tk.Label(
        scrollable_frame,
        text="Oscilloscope Pulse Capture Guide",
        font=(gui_config.FONT_FAMILY, 16, "bold"),
        bg=gui_config.COLORS["bg"],
        fg=gui_config.COLORS["header"],
    ).pack(**pad)

    tk.Label(
        scrollable_frame,
        text="1. Overview",
        font=(gui_config.FONT_FAMILY, 12, "bold"),
        bg=gui_config.COLORS["bg"],
    ).pack(**pad)
    tk.Label(
        scrollable_frame,
        text=(
            "This tool generates a voltage pulse using the SMU and captures the transient current "
            "response using an Oscilloscope.\nIt is designed for capturing fast transients that "
            "standard SMUs cannot resolve."
        ),
        justify="left",
        bg=gui_config.COLORS["bg"],
    ).pack(**pad)

    tk.Label(
        scrollable_frame,
        text="2. Setup & Wiring Modes",
        font=(gui_config.FONT_FAMILY, 12, "bold"),
        bg=gui_config.COLORS["bg"],
    ).pack(**pad)

    f_shunt = tk.LabelFrame(
        scrollable_frame,
        text="Method A: Shunt Resistor (Recommended for Fast Pulses)",
        bg=gui_config.COLORS["bg"],
        font=(gui_config.FONT_FAMILY, 10, "bold"),
    )
    f_shunt.pack(fill="x", **pad)
    shunt_txt = (
        "• Best for: Fast switching (<1ms), high bandwidth.\n"
        "• How it works: Measures voltage drop across a known resistor.\n\n"
        "WIRING:\n"
        "   [SMU Hi] ----> [Shunt Resistor] ----+---- [DUT] ----> [SMU Lo]\n"
        "                                       |\n"
        "   [Scope CH1] ------------------------+\n"
        "   [Scope GND] ------------------------+ (at Shunt-DUT junction? No, across Shunt!)\n\n"
        "   CORRECT WIRING (Shunt on Low Side is safer for Scope GND):\n"
        "   [SMU Hi] -----------------> [DUT] ----+---- [Shunt] ----> [SMU Lo]\n"
        "                                        |\n"
        "   [Scope CH1] -------------------------+\n"
        "   [Scope GND] --------------------------------------------+ (SMU Lo)\n\n"
        "   * Ensure Scope Ground is shared with SMU Lo/Ground."
    )
    tk.Label(f_shunt, text=shunt_txt, justify="left", bg=gui_config.COLORS["bg"], font=("Consolas", 9)).pack(
        padx=10, pady=5
    )

    f_smu = tk.LabelFrame(
        scrollable_frame,
        text="Method B: SMU Current (Slower)",
        bg=gui_config.COLORS["bg"],
        font=(gui_config.FONT_FAMILY, 10, "bold"),
    )
    f_smu.pack(fill="x", **pad)
    smu_txt = (
        "• Best for: Slow pulses (>10ms), DC accuracy.\n"
        "• How it works: Uses the SMU's internal measurement.\n"
        "• Wiring: Standard direct connection. Scope is NOT used for current, only Voltage monitoring if attached."
    )
    tk.Label(f_smu, text=smu_txt, justify="left", bg=gui_config.COLORS["bg"]).pack(padx=10, pady=5)

    tk.Label(
        scrollable_frame,
        text="3. Parameters Explained",
        font=(gui_config.FONT_FAMILY, 12, "bold"),
        bg=gui_config.COLORS["bg"],
    ).pack(**pad)
    params_txt = (
        "• Pulse Voltage: Amplitude of the pulse.\n"
        "• Duration: Width of the pulse.\n"
        "• Compliance: Current limit for the SMU (safety).\n"
        "• Pre-Pulse Delay: Time to wait at 0V before pulsing (to arm scope).\n"
        "• R_shunt: Value of shunt resistor used in Method A. Crucial for accurate Current calc (I = V_scope / R)."
    )
    tk.Label(scrollable_frame, text=params_txt, justify="left", bg=gui_config.COLORS["bg"]).pack(**pad)
