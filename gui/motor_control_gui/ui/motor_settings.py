"""
Motor Control GUI - Motor Settings Section
==========================================
"""

from __future__ import annotations

import tkinter as tk
from typing import Any

from gui.motor_control_gui import config
from gui.motor_control_gui.ui.widgets import CollapsibleFrame


def create_motor_settings(gui: Any, parent: tk.Frame, start_expanded: bool = True) -> None:
    """Build motor velocity/acceleration settings."""
    c = config.COLORS
    collapsible = CollapsibleFrame(
        parent, "⚙️ Motor Settings", bg_color=c["bg_dark"], fg_color=c["fg_primary"], start_expanded=start_expanded
    )
    collapsible.pack(fill=tk.X, pady=3)
    gui.collapsible_sections.append(collapsible)

    settings_frame = collapsible.get_content_frame()
    settings_frame.configure(bg=c["bg_medium"])

    tk.Label(
        settings_frame,
        text="Max Velocity (mm/s):",
        fg=c["fg_primary"],
        bg=c["bg_medium"],
    ).grid(row=0, column=0, sticky="w", pady=2)
    tk.Entry(
        settings_frame,
        textvariable=gui.var_velocity,
        bg=c["bg_light"],
        fg=c["fg_primary"],
        insertbackground=c["fg_primary"],
    ).grid(row=0, column=1, sticky="ew", pady=2)

    tk.Label(
        settings_frame,
        text="Acceleration (mm/s²):",
        fg=c["fg_primary"],
        bg=c["bg_medium"],
    ).grid(row=1, column=0, sticky="w", pady=2)
    tk.Entry(
        settings_frame,
        textvariable=gui.var_acceleration,
        bg=c["bg_light"],
        fg=c["fg_primary"],
        insertbackground=c["fg_primary"],
    ).grid(row=1, column=1, sticky="ew", pady=2)

    tk.Button(
        settings_frame,
        text="Apply Settings",
        command=gui._apply_motor_settings,
        bg=c["accent_blue"],
        fg="white",
        font=("Arial", 9),
    ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(5, 0))

    settings_frame.columnconfigure(1, weight=1)
