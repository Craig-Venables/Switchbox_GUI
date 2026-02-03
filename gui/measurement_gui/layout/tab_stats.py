"""
Stats Tab Builder
==================

Builds the "Stats" tab for device tracking and metrics visualization.
Extracted from layout_builder for maintainability.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from .constants import COLOR_BG, COLOR_PRIMARY


def build_stats_tab(builder: Any, notebook: ttk.Notebook) -> None:
    """
    Create Stats tab showing device tracking and metrics.

    Args:
        builder: The layout builder instance (provides gui, widgets, _create_scrollable_panel).
        notebook: The ttk.Notebook to add the tab to.
    """
    gui = builder.gui

    tab = tk.Frame(notebook, bg=COLOR_BG)
    notebook.add(tab, text="  Stats  ")

    tab.columnconfigure(0, weight=1)
    tab.rowconfigure(0, weight=0)
    tab.rowconfigure(1, weight=1)

    # TOP: Device selector
    selector_frame = tk.Frame(tab, bg=COLOR_BG)
    selector_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

    tk.Label(
        selector_frame,
        text="Device:",
        font=("Segoe UI", 10, "bold"),
        bg=COLOR_BG
    ).pack(side=tk.LEFT, padx=5)

    gui.stats_device_var = tk.StringVar()
    device_combo = ttk.Combobox(
        selector_frame,
        textvariable=gui.stats_device_var,
        width=50,
        state="readonly"
    )
    device_combo.pack(side=tk.LEFT, padx=5)
    device_combo.bind('<<ComboboxSelected>>', lambda e: gui.update_stats_display())
    gui.stats_device_combo = device_combo

    tk.Button(
        selector_frame,
        text="🔄 Refresh",
        command=gui.refresh_stats_list,
        bg=COLOR_PRIMARY,
        fg="white",
        font=("Segoe UI", 9, "bold"),
        relief=tk.FLAT,
        cursor="hand2"
    ).pack(side=tk.LEFT, padx=5)

    # CONTENT: Split view - Text on left, Plots on right
    content_frame = tk.Frame(tab, bg=COLOR_BG)
    content_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
    content_frame.columnconfigure(0, weight=1)
    content_frame.columnconfigure(1, weight=1)
    content_frame.rowconfigure(0, weight=1)

    # LEFT: Text statistics
    text_frame = tk.Frame(content_frame, bg="white", relief=tk.RIDGE, borderwidth=1)
    text_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
    text_frame.columnconfigure(0, weight=1)
    text_frame.rowconfigure(0, weight=1)

    text_scroll = tk.Scrollbar(text_frame)
    text_scroll.grid(row=0, column=1, sticky="ns")

    stats_text = tk.Text(
        text_frame,
        wrap=tk.WORD,
        yscrollcommand=text_scroll.set,
        font=("Consolas", 9),
        bg="white",
        relief=tk.FLAT
    )
    stats_text.grid(row=0, column=0, sticky="nsew")
    text_scroll.config(command=stats_text.yview)
    gui.stats_text_widget = stats_text

    # RIGHT: Trend plots
    plot_frame = tk.Frame(content_frame, bg="white", relief=tk.RIDGE, borderwidth=1)
    plot_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
    plot_frame.columnconfigure(0, weight=1)
    plot_frame.rowconfigure(0, weight=1)

    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure

    fig = Figure(figsize=(6, 8), dpi=100, facecolor='white')
    canvas = FigureCanvasTkAgg(fig, master=plot_frame)
    canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")

    gui.stats_plot_figure = fig
    gui.stats_plot_canvas = canvas

    builder.widgets["stats_tab"] = tab

    try:
        gui.refresh_stats_list()
    except Exception as e:
        print(f"[STATS] Initial load failed: {e}")
