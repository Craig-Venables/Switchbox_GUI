"""
Measurements Tab Builder
========================

Builds the main Measurements tab with control panels and graph display area.
Extracted from layout_builder for maintainability.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from .constants import COLOR_BG


def build_measurements_tab(builder: Any, notebook: ttk.Notebook) -> None:
    """
    Create the main Measurements tab with:
    - LEFT: Control panels (collapsible)
    - RIGHT: Large graph display area

    Args:
        builder: The layout builder instance (provides gui, widgets,
                 _create_scrollable_panel, and various _build_* methods).
        notebook: The ttk.Notebook to add the tab to.
    """
    gui = builder.gui

    tab = tk.Frame(notebook, bg=COLOR_BG)
    notebook.add(tab, text="  Measurements  ")

    tab.columnconfigure(0, weight=0, minsize=400)
    tab.columnconfigure(1, weight=1)
    tab.rowconfigure(0, weight=1)

    left_panel = builder._create_scrollable_panel(tab)
    left_panel._container.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)

    builder._build_mode_selection_modern(left_panel)
    builder._build_sweep_parameters_collapsible(left_panel)
    builder._build_pulse_parameters_collapsible(left_panel)
    builder._build_sequential_controls_collapsible(left_panel)
    builder._build_custom_measurement_quick_select(left_panel)
    builder._build_conditional_testing_quick_select(left_panel)
    builder._build_telegram_bot_collapsible(left_panel)

    right_panel = tk.Frame(tab, bg=COLOR_BG)
    right_panel.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
    right_panel.columnconfigure(0, weight=1)
    right_panel.rowconfigure(0, weight=1)
    gui.measurements_graph_panel = right_panel

    builder.widgets["measurements_tab"] = tab
    builder.widgets["measurements_left_panel"] = left_panel
    builder.widgets["measurements_right_panel"] = right_panel
