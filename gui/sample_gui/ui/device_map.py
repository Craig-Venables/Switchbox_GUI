"""
Device Map UI Builder
=====================

Creates the canvas section with device map image and navigation controls.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any


def create_canvas_section(sample_gui: Any) -> None:
    """
    Create the canvas section with navigation controls.

    Args:
        sample_gui: The SampleGUI instance. Must have device_selection_frame and
                    methods: canvas_click, canvas_ctrl_click, canvas_right_click,
                    prev_device, next_device, change_relays, clear_canvas.
    """
    canvas_container = ttk.Frame(sample_gui.device_selection_frame)
    canvas_container.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
    canvas_container.grid_rowconfigure(0, weight=1)
    canvas_container.grid_rowconfigure(1, weight=0)
    canvas_container.grid_columnconfigure(0, weight=1)

    canvas_frame = ttk.LabelFrame(canvas_container, text="Device Map", padding=5)
    canvas_frame.grid(row=0, column=0, sticky="nsew")

    sample_gui.canvas = tk.Canvas(
        canvas_frame,
        width=600,
        height=500,
        bg="white",
        highlightbackground="black",
        highlightthickness=1,
    )
    sample_gui.canvas.pack(fill="both", expand=True)
    sample_gui.canvas.bind("<Button-1>", sample_gui.canvas_click)
    sample_gui.canvas.bind("<Control-Button-1>", sample_gui.canvas_ctrl_click)
    sample_gui.canvas.bind("<Button-3>", sample_gui.canvas_right_click)

    nav_bar = ttk.Frame(canvas_container)
    nav_bar.grid(row=1, column=0, sticky="ew", pady=5)

    sample_gui.prev_button = ttk.Button(nav_bar, text="◄ Previous", command=sample_gui.prev_device, width=12)
    sample_gui.prev_button.pack(side="left", padx=5)

    sample_gui.info_box = tk.Label(
        nav_bar,
        text="Current Device: None",
        relief=tk.SUNKEN,
        font=("Segoe UI", 10),
        bg="#f0f0f0",
        padx=10,
        pady=5,
    )
    sample_gui.info_box.pack(side="left", expand=True, fill="x", padx=5)

    sample_gui.next_button = ttk.Button(nav_bar, text="Next ►", command=sample_gui.next_device, width=12)
    sample_gui.next_button.pack(side="left", padx=5)

    sample_gui.change_button = ttk.Button(
        nav_bar,
        text="Route to Device",
        command=sample_gui.change_relays,
        width=15,
    )
    sample_gui.change_button.pack(side="left", padx=5)

    sample_gui.clear_button = ttk.Button(nav_bar, text="Clear", command=sample_gui.clear_canvas, width=10)
    sample_gui.clear_button.pack(side="left", padx=5)
