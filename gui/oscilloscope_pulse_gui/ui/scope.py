"""Oscilloscope setup section for Oscilloscope Pulse GUI."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import config as gui_config
from .widgets import create_collapsible_frame


def build_scope_content(gui, frame):
    """Build oscilloscope settings content."""
    instructions = (
        "Set up your oscilloscope MANUALLY:\n"
        "• Timebase: to capture full pulse (e.g., 500 ms/div for 1s pulse)\n"
        "• V/div: appropriate for signal level (e.g., 200 mV/div)\n"
        "• Trigger: set to capture pulse start\n"
        "• Channel: use CH1 (or set below)"
    )
    instr_label = tk.Label(
        frame,
        text=instructions,
        justify="left",
        bg=gui_config.COLORS["warning_bg"],
        font=(gui_config.FONT_FAMILY, 8),
        fg=gui_config.COLORS["warning_fg"],
        relief=tk.SOLID,
        bd=1,
        padx=5,
        pady=5,
    )
    instr_label.pack(fill="x", pady=(0, 10))

    gui._add_param(
        frame,
        "Scope Channel:",
        "scope_channel",
        "CH1",
        options=["CH1", "CH2", "CH3", "CH4"],
        ToolTipText="Which channel to read from",
    )


def create_scope_frame(gui, parent):
    """Build collapsible oscilloscope settings frame."""
    create_collapsible_frame(
        gui,
        parent,
        "1️⃣ Oscilloscope Setup (Manual)",
        lambda f: build_scope_content(gui, f),
        default_expanded=True,
    )
