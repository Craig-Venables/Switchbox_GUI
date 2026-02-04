"""Status bar for Oscilloscope Pulse GUI."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


def create_status_bar(gui, parent):
    """Build status bar."""
    frame = ttk.Frame(parent, padding=3)
    frame.pack(fill="x", pady=2)

    gui.vars["status"] = tk.StringVar(value="Ready")
    status_label = ttk.Label(frame, textvariable=gui.vars["status"], style="Status.TLabel")
    status_label.pack(side="left")
