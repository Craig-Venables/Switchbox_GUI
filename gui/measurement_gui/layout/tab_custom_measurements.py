"""
Custom Measurements Tab Builder
===============================

Builds the Custom Measurements tab with the sweep builder and visualizations.
Extracted from layout_builder for maintainability.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Any

from .constants import COLOR_BG

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def build_custom_measurements_tab(builder: Any, notebook: ttk.Notebook) -> None:
    """
    Create the Custom Measurements tab with builder and visualizations.

    Args:
        builder: The layout builder instance (provides gui, widgets,
                 _create_scrollable_panel, _build_custom_measurement_section).
        notebook: The ttk.Notebook to add the tab to.
    """
    gui = builder.gui

    tab = tk.Frame(notebook, bg=COLOR_BG)
    notebook.add(tab, text="  Custom Measurements  ")

    try:
        from gui.measurement_gui.custom_measurements_builder import CustomMeasurementsBuilder

        cm_builder = CustomMeasurementsBuilder(
            parent=tab,
            gui_instance=gui,
            json_path=str(_PROJECT_ROOT / "Json_Files" / "Custom_Sweeps.json"),
        )
        gui.custom_measurements_builder = cm_builder
    except Exception as e:
        print(f"Failed to load custom measurements builder: {e}")
        content = builder._create_scrollable_panel(tab)
        content._container.pack(fill="both", expand=True, padx=20, pady=20)
        builder._build_custom_measurement_section(content)

    builder.widgets["custom_measurements_tab"] = tab
