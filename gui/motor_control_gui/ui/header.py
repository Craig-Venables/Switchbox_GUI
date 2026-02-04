"""
Motor Control GUI - Header Section
==================================
"""

from __future__ import annotations

import tkinter as tk
from typing import Any

from gui.motor_control_gui import config


def create_header(gui: Any) -> None:
    """Build header with title and connection controls."""
    c = config.COLORS
    header = tk.Frame(gui.root, bg=c["bg_dark"], pady=10, padx=10)
    header.grid(row=0, column=0, columnspan=2, sticky="ew")
    header.columnconfigure(1, weight=1)

    title_label = tk.Label(
        header,
        text="⚡ Motor Control & Laser Positioning",
        font=("Arial", 16, "bold"),
        fg=c["accent_blue"],
        bg=c["bg_dark"],
    )
    title_label.grid(row=0, column=0, sticky="w", padx=(0, 20))

    btn_frame = tk.Frame(header, bg=c["bg_dark"])
    btn_frame.grid(row=0, column=1, sticky="e")

    gui.btn_connect = tk.Button(
        btn_frame,
        text="🔌 Connect Motors",
        command=gui._on_connect,
        bg=c["accent_green"],
        fg="black",
        font=("Arial", 10, "bold"),
        padx=15,
        pady=5,
        relief=tk.FLAT,
    )
    gui.btn_connect.pack(side=tk.LEFT, padx=5)

    gui.btn_disconnect = tk.Button(
        btn_frame,
        text="⏹ Disconnect",
        command=gui._on_disconnect,
        bg=c["accent_red"],
        fg="white",
        font=("Arial", 10, "bold"),
        padx=15,
        pady=5,
        relief=tk.FLAT,
    )
    gui.btn_disconnect.pack(side=tk.LEFT, padx=5)

    help_btn = tk.Button(
        btn_frame,
        text="Help / Guide",
        command=gui._show_help,
        bg=c["accent_blue"],
        fg="white",
        font=("Arial", 10, "bold"),
        padx=15,
        pady=5,
        relief=tk.FLAT,
    )
    help_btn.pack(side=tk.LEFT, padx=5)

    pos_label = tk.Label(
        header,
        textvariable=gui.var_position,
        font=("Consolas", 11),
        fg=c["accent_yellow"],
        bg=c["bg_dark"],
    )
    pos_label.grid(row=0, column=2, sticky="e", padx=(20, 0))
