"""
Motor Control GUI - Go To Position Section
==========================================
"""

from __future__ import annotations

import tkinter as tk
from typing import Any

from gui.motor_control_gui import config
from gui.motor_control_gui.ui.widgets import CollapsibleFrame


def create_goto_controls(gui: Any, parent: tk.Frame) -> None:
    """Build go-to-position controls."""
    c = config.COLORS
    collapsible = CollapsibleFrame(
        parent, "📍 Go To Position", bg_color=c["bg_dark"], fg_color=c["fg_primary"]
    )
    collapsible.pack(fill=tk.X, pady=3)
    gui.collapsible_sections.append(collapsible)

    goto_frame = collapsible.get_content_frame()
    goto_frame.configure(bg=c["bg_medium"])

    tk.Label(
        goto_frame,
        text="X (mm):",
        fg=c["fg_primary"],
        bg=c["bg_medium"],
    ).grid(row=0, column=0, sticky="w", pady=2)
    tk.Entry(
        goto_frame,
        textvariable=gui.var_goto_x,
        bg=c["bg_light"],
        fg=c["fg_primary"],
        insertbackground=c["fg_primary"],
    ).grid(row=0, column=1, sticky="ew", pady=2)

    tk.Label(
        goto_frame,
        text="Y (mm):",
        fg=c["fg_primary"],
        bg=c["bg_medium"],
    ).grid(row=1, column=0, sticky="w", pady=2)
    tk.Entry(
        goto_frame,
        textvariable=gui.var_goto_y,
        bg=c["bg_light"],
        fg=c["fg_primary"],
        insertbackground=c["fg_primary"],
    ).grid(row=1, column=1, sticky="ew", pady=2)

    tk.Button(
        goto_frame,
        text="➜ Move To Position",
        command=gui._on_goto,
        bg=c["accent_green"],
        fg="black",
        font=("Arial", 9, "bold"),
    ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(5, 0))

    goto_frame.columnconfigure(1, weight=1)
