"""
Sweep Parameters Section
========================

Collapsible sweep parameters frame. Content is populated by main.py create_sweep_parameters().
"""

from __future__ import annotations

import tkinter as tk
from typing import Any

from ._collapsible import build_collapsible_section


def build_sweep_parameters(builder: Any, parent: tk.Misc) -> None:
    """Build the Sweep Parameters collapsible section."""
    gui = builder.gui

    def build_content(content_frame: tk.Frame) -> None:
        content_frame.columnconfigure(1, weight=1)
        gui.sweep_parameters_frame = content_frame

    container = build_collapsible_section(
        parent,
        "⚡ Sweep Parameters",
        build_content,
        start_expanded=True,
        content_bg="#f0f0f0",
    )
    builder.widgets["sweep_parameters_collapsible"] = container
