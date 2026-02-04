"""Analysis/measurement parameters section for Oscilloscope Pulse GUI."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import config as gui_config
from .widgets import create_collapsible_frame


def build_measurement_content(gui, frame):
    """Build measurement settings content."""
    tk.Label(
        frame,
        text="⚠️ R_shunt must match your actual resistor for correct current calculation!",
        bg=gui_config.COLORS["bg"],
        fg=gui_config.COLORS["error_fg"],
        font=(gui_config.FONT_FAMILY, 8, "bold"),
    ).pack(fill="x", pady=(0, 5))

    gui._add_param(
        frame,
        "R_shunt (Ω):",
        "r_shunt",
        "100000",
        ToolTipText="Actual value of your shunt resistor - measure with DMM if unsure!",
    )


def create_measurement_frame(gui, parent):
    """Build collapsible measurement settings frame."""
    create_collapsible_frame(
        gui,
        parent,
        "Analysis Parameters (Critical!)",
        lambda f: build_measurement_content(gui, f),
        default_expanded=True,
    )
