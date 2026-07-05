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

    # IV classification overlay controls + summary
    class_bar = ttk.Frame(canvas_container)
    class_bar.grid(row=2, column=0, sticky="ew", pady=(0, 4))
    canvas_container.grid_rowconfigure(2, weight=0)

    if not hasattr(sample_gui, "show_classification_overlay"):
        sample_gui.show_classification_overlay = tk.BooleanVar(value=True)
    if not hasattr(sample_gui, "show_classification_scores"):
        sample_gui.show_classification_scores = tk.BooleanVar(value=True)

    ttk.Checkbutton(
        class_bar,
        text="IV colors",
        variable=sample_gui.show_classification_overlay,
        command=sample_gui._on_classification_overlay_toggle,
    ).pack(side="left", padx=(0, 8))

    ttk.Checkbutton(
        class_bar,
        text="Scores",
        variable=sample_gui.show_classification_scores,
        command=sample_gui._on_classification_overlay_toggle,
    ).pack(side="left", padx=(0, 12))

    sample_gui.classification_summary_label = tk.Label(
        class_bar,
        text="Measured 0/0 · Memristive 0 · Promising 0 · Pending 0",
        font=("Segoe UI", 9),
        fg="#555555",
        anchor="w",
    )
    sample_gui.classification_summary_label.pack(side="left", fill="x", expand=True)

    ttk.Button(
        class_bar,
        text="Refresh",
        command=lambda: sample_gui.classification_overlay.refresh(),
        width=8,
    ).pack(side="right", padx=4)

    # Compact color legend
    legend_frame = ttk.Frame(class_bar)
    legend_frame.pack(side="right", padx=(8, 4))
    _legend_items = (
        ("#A5D6A7", "Mem"),
        ("#BDBDBD", "1x"),
        ("#EF9A9A", "Open"),
        ("#90CAF9", "Ohm"),
        ("#FFCC80", "Rect"),
    )
    for color, tip in _legend_items:
        swatch = tk.Label(legend_frame, text="  ", bg=color, relief=tk.GROOVE, width=2)
        swatch.pack(side="left", padx=1)
        tk.Label(legend_frame, text=tip, font=("Segoe UI", 7), fg="#666").pack(side="left", padx=(0, 4))
