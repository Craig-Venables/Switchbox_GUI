"""
Motor Control GUI - Jog Controls Section
========================================
"""

from __future__ import annotations

import tkinter as tk
from typing import Any

from gui.motor_control_gui import config
from gui.motor_control_gui.ui.widgets import CollapsibleFrame


def create_jog_controls(gui: Any, parent: tk.Frame) -> None:
    """Build jog controls section."""
    c = config.COLORS
    collapsible = CollapsibleFrame(
        parent, "🎮 Jog Controls", bg_color=c["bg_dark"], fg_color=c["fg_primary"]
    )
    collapsible.pack(fill=tk.X, pady=3)
    gui.collapsible_sections.append(collapsible)

    jog_frame = collapsible.get_content_frame()
    jog_frame.configure(bg=c["bg_medium"])

    tk.Label(
        jog_frame,
        text="Step Size (mm):",
        font=("Arial", 9),
        fg=c["fg_primary"],
        bg=c["bg_medium"],
    ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 5))

    step_entry = tk.Entry(
        jog_frame,
        textvariable=gui.var_step,
        font=("Arial", 10),
        bg=c["bg_light"],
        fg=c["fg_primary"],
        insertbackground=c["fg_primary"],
    )
    step_entry.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 10))
    step_entry.bind("<FocusOut>", gui._validate_step)
    step_entry.bind("<Return>", gui._validate_step)

    tk.Button(
        jog_frame,
        text="▲\nY+",
        command=lambda: gui._on_jog("y", +1),
        bg=c["accent_blue"],
        fg="white",
        font=("Arial", 10, "bold"),
        width=6,
        height=2,
    ).grid(row=2, column=1, padx=2, pady=2)

    tk.Button(
        jog_frame,
        text="◀\nX-",
        command=lambda: gui._on_jog("x", -1),
        bg=c["accent_blue"],
        fg="white",
        font=("Arial", 10, "bold"),
        width=6,
        height=2,
    ).grid(row=3, column=0, padx=2, pady=2)

    gui.btn_home = tk.Button(
        jog_frame,
        text="🏠\nHOME",
        command=gui._on_home,
        bg=c["accent_yellow"],
        fg="black",
        font=("Arial", 9, "bold"),
        width=6,
        height=2,
    )
    gui.btn_home.grid(row=3, column=1, padx=2, pady=2)

    tk.Button(
        jog_frame,
        text="▶\nX+",
        command=lambda: gui._on_jog("x", +1),
        bg=c["accent_blue"],
        fg="white",
        font=("Arial", 10, "bold"),
        width=6,
        height=2,
    ).grid(row=3, column=2, padx=2, pady=2)

    tk.Button(
        jog_frame,
        text="▼\nY-",
        command=lambda: gui._on_jog("y", -1),
        bg=c["accent_blue"],
        fg="white",
        font=("Arial", 10, "bold"),
        width=6,
        height=2,
    ).grid(row=4, column=1, padx=2, pady=2)

    for i in range(3):
        jog_frame.columnconfigure(i, weight=1)
