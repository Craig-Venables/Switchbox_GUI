"""
Status section – log/status text area.
Builds the Status LabelFrame; gui must have log().
"""

import tkinter as tk


def build_status_section(parent, gui):
    """Build Status (log text). Sets gui.status_text."""
    frame = tk.LabelFrame(parent, text="Status", padx=5, pady=5)
    frame.pack(fill=tk.X, padx=5, pady=5)

    gui.status_text = tk.Text(frame, height=6, wrap=tk.WORD, bg="black", fg="lime", font=("Courier", 8))
    gui.status_text.pack(fill=tk.X)
    gui.log("TSP Testing GUI initialized")
