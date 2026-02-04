"""
Motor Control GUI - Position Presets Section
============================================
"""

from __future__ import annotations

import tkinter as tk
from typing import Any

from gui.motor_control_gui import config
from gui.motor_control_gui.ui.widgets import CollapsibleFrame


def create_presets(gui: Any, parent: tk.Frame) -> None:
    """Build position presets section."""
    c = config.COLORS
    collapsible = CollapsibleFrame(
        parent, "⭐ Position Presets", bg_color=c["bg_dark"], fg_color=c["fg_primary"]
    )
    collapsible.pack(fill=tk.X, pady=3)
    gui.collapsible_sections.append(collapsible)

    presets_frame = collapsible.get_content_frame()
    presets_frame.configure(bg=c["bg_medium"])

    gui.presets_listbox = tk.Listbox(
        presets_frame,
        height=4,
        bg=c["bg_light"],
        fg=c["fg_primary"],
        selectbackground=c["accent_blue"],
        font=("Consolas", 9),
    )
    gui.presets_listbox.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 5))
    gui._update_presets_list()

    tk.Button(
        presets_frame,
        text="💾 Save Current",
        command=gui._save_preset,
        bg=c["accent_green"],
        fg="black",
        font=("Arial", 8),
    ).grid(row=1, column=0, sticky="ew", padx=(0, 2))

    tk.Button(
        presets_frame,
        text="📌 Go To Selected",
        command=gui._goto_preset,
        bg=c["accent_blue"],
        fg="white",
        font=("Arial", 8),
    ).grid(row=1, column=1, sticky="ew", padx=(2, 0))

    tk.Button(
        presets_frame,
        text="🗑️ Delete Selected",
        command=gui._delete_preset,
        bg=c["accent_red"],
        fg="white",
        font=("Arial", 8),
    ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(2, 0))

    presets_frame.columnconfigure(0, weight=1)
    presets_frame.columnconfigure(1, weight=1)
