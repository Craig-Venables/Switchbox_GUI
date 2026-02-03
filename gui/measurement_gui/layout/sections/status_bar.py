"""
Bottom Status Bar
=================

Creates the bottom status bar with connection status, device count, and message.
"""

from __future__ import annotations

import tkinter as tk
from typing import Any

from ..constants import COLOR_BG_INFO, COLOR_SECONDARY, COLOR_SUCCESS, FONT_MAIN


def build_bottom_status_bar(builder: Any, parent: tk.Misc) -> None:
    """
    Create the bottom status bar.

    Args:
        builder: Layout builder with gui, widgets.
        parent: Parent widget.
    """
    gui = builder.gui

    frame = tk.Frame(parent, bg=COLOR_BG_INFO, height=30, relief="sunken", borderwidth=1)
    frame.grid(row=2, column=0, sticky="ew", padx=0, pady=0)
    frame.grid_propagate(False)

    left_section = tk.Frame(frame, bg=COLOR_BG_INFO)
    left_section.pack(side="left", fill="y", padx=10)

    gui.status_bar_connection = tk.Label(
        left_section,
        text="SMU: Disconnected",
        font=FONT_MAIN,
        bg=COLOR_BG_INFO,
        fg=COLOR_SECONDARY,
    )
    gui.status_bar_connection.pack(side="left", padx=(0, 15))

    middle_section = tk.Frame(frame, bg=COLOR_BG_INFO)
    middle_section.pack(side="left", fill="y")

    device_count = len(getattr(gui, "device_list", []))
    gui.status_bar_devices = tk.Label(
        middle_section,
        text=f"Devices: {device_count}",
        font=FONT_MAIN,
        bg=COLOR_BG_INFO,
        fg=COLOR_SECONDARY,
    )
    gui.status_bar_devices.pack(side="left", padx=15)

    right_section = tk.Frame(frame, bg=COLOR_BG_INFO)
    right_section.pack(side="right", fill="y", padx=10)

    gui.status_bar_message = tk.Label(
        right_section,
        text="Ready",
        font=FONT_MAIN,
        bg=COLOR_BG_INFO,
        fg=COLOR_SUCCESS,
    )
    gui.status_bar_message.pack(side="right")

    builder.widgets["bottom_status_bar"] = frame
