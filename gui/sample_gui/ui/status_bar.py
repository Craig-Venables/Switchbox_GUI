"""
Status Bar UI Builder
=====================

Creates the bottom status bar with multiplexer and device count.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any


def create_status_bar(sample_gui: Any) -> None:
    """
    Create the bottom status bar.

    Args:
        sample_gui: The SampleGUI instance. Must have root.
    """
    status_bar = ttk.Frame(sample_gui.root, relief=tk.SUNKEN, borderwidth=1)
    status_bar.grid(row=2, column=0, sticky="ew", padx=5, pady=(0, 5))

    sample_gui.mpx_status_label = tk.Label(
        status_bar,
        text="Multiplexer: Not Connected",
        font=("Segoe UI", 9),
        anchor="w",
    )
    sample_gui.mpx_status_label.pack(side="left", padx=10)

    sample_gui.device_count_label = tk.Label(
        status_bar,
        text="Devices: 0 selected / 0 total",
        font=("Segoe UI", 9),
        anchor="w",
    )
    sample_gui.device_count_label.pack(side="left", padx=10)

    ttk.Frame(status_bar).pack(side="left", expand=True)

    sample_gui.theme_label = tk.Label(
        status_bar,
        text="☀ Light Mode",
        font=("Segoe UI", 9),
        fg="#888888",
        cursor="hand2",
    )
    sample_gui.theme_label.pack(side="right", padx=10)
