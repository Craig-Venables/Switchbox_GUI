"""
Setup Tab Builder
==================

Builds the Setup tab for system configuration and instrument connections.
Extracted from layout_builder for maintainability.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from .constants import COLOR_BG


def build_setup_tab(builder: Any, notebook: ttk.Notebook) -> None:
    """
    Create the Setup tab (connections and configuration).

    Args:
        builder: The layout builder instance (provides gui, widgets,
                 _create_scrollable_panel, _build_connection_section_modern).
        notebook: The ttk.Notebook to add the tab to.
    """
    tab = tk.Frame(notebook, bg=COLOR_BG)
    notebook.add(tab, text="  Setup  ")

    content = builder._create_scrollable_panel(tab)
    content._container.pack(fill="both", expand=True, padx=20, pady=20)

    builder._build_connection_section_modern(content)

    builder.widgets["setup_tab"] = tab
