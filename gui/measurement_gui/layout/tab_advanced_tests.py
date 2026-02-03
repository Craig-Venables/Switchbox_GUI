"""
Advanced Tests Tab Builder
==========================

Builds the "Advanced Tests" tab for endurance, retention, and conditional testing.
Extracted from layout_builder for maintainability.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from .constants import COLOR_BG


def build_advanced_tests_tab(builder: Any, notebook: ttk.Notebook) -> None:
    """
    Create the Advanced Tests tab (Endurance, Retention, etc.).

    Args:
        builder: The layout builder instance (provides gui, widgets, _create_scrollable_panel,
                 _build_manual_endurance_retention, _build_conditional_testing_section).
        notebook: The ttk.Notebook to add the tab to.
    """
    tab = tk.Frame(notebook, bg=COLOR_BG)
    notebook.add(tab, text="  Advanced Tests  ")

    content = builder._create_scrollable_panel(tab)
    content._container.pack(fill='both', expand=True, padx=20, pady=20)

    builder._build_manual_endurance_retention(content)
    builder._build_conditional_testing_section(content)

    builder.widgets["advanced_tests_tab"] = tab
