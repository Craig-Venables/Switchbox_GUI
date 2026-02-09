"""
Status section – log/status text area.
Builds the Status LabelFrame; gui must have log().
"""

import tkinter as tk


def toggle_status_section(gui):
    """Toggle collapse/expand of status section."""
    if gui.status_collapsed.get():
        gui.status_text.pack(fill=tk.X)
        gui.status_collapse_btn.config(text="▼")
        gui.status_collapsed.set(False)
    else:
        gui.status_text.pack_forget()
        gui.status_collapse_btn.config(text="▶")
        gui.status_collapsed.set(True)


def build_status_section(parent, gui):
    """Build Status (log text). Sets gui.status_text."""
    frame = tk.LabelFrame(parent, text="Status", padx=3, pady=3)
    frame.pack(fill=tk.X, padx=5, pady=(3, 5))

    # Header with collapse button
    header_frame = tk.Frame(frame)
    header_frame.pack(fill=tk.X, pady=(0, 3))
    
    gui.status_collapsed = tk.BooleanVar(value=False)  # Start expanded
    gui.status_collapse_btn = tk.Button(header_frame, text="▼", width=3,
                                        command=lambda: toggle_status_section(gui),
                                        font=("TkDefaultFont", 8), relief=tk.FLAT)
    gui.status_collapse_btn.pack(side=tk.LEFT, padx=(0, 5))
    
    tk.Label(header_frame, text="Log", font=("TkDefaultFont", 8, "bold")).pack(side=tk.LEFT, anchor="w")

    gui.status_text = tk.Text(frame, height=4, wrap=tk.WORD, bg="black", fg="lime", font=("Courier", 8))
    gui.status_text.pack(fill=tk.X)
    gui.log("TSP Testing GUI initialized")
