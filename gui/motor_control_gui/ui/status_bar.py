"""
Motor Control GUI - Status Bar Section
======================================
"""

from __future__ import annotations

import tkinter as tk
from typing import Any

from gui.motor_control_gui import config


def create_status_bar(gui: Any) -> None:
    """Build bottom status bar."""
    c = config.COLORS
    status_bar = tk.Frame(gui.root, bg=c["bg_light"], height=30)
    status_bar.grid(row=2, column=0, columnspan=2, sticky="ew")
    status_bar.grid_propagate(False)

    tk.Label(
        status_bar,
        textvariable=gui.var_status,
        fg=c["fg_primary"],
        bg=c["bg_light"],
        font=("Arial", 9),
        anchor="w",
    ).pack(side=tk.LEFT, padx=10)

    tk.Label(
        status_bar,
        text="X:",
        fg=c["accent_blue"],
        bg=c["bg_light"],
        font=("Arial", 9, "bold"),
    ).pack(side=tk.LEFT)

    tk.Label(
        status_bar,
        textvariable=gui.var_status_x,
        fg=c["fg_secondary"],
        bg=c["bg_light"],
        font=("Arial", 9),
    ).pack(side=tk.LEFT, padx=(2, 15))

    tk.Label(
        status_bar,
        text="Y:",
        fg=c["accent_green"],
        bg=c["bg_light"],
        font=("Arial", 9, "bold"),
    ).pack(side=tk.LEFT)

    tk.Label(
        status_bar,
        textvariable=gui.var_status_y,
        fg=c["fg_secondary"],
        bg=c["bg_light"],
        font=("Arial", 9),
    ).pack(side=tk.LEFT, padx=(2, 0))

    tk.Label(
        status_bar,
        text="⌨️ Shortcuts: Arrow keys=Jog | H=Home | G=Go-to | S=Save Preset | Ctrl+Q=Quit",
        fg=c["grid_light"],
        bg=c["bg_light"],
        font=("Arial", 8),
    ).pack(side=tk.RIGHT, padx=10)
