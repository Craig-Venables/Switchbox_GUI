"""
Collapsible Section Helper
==========================

Creates a collapsible header + content frame with consistent styling.
"""

from __future__ import annotations

import tkinter as tk
from typing import Any, Callable, Optional


def build_collapsible_section(
    parent: tk.Misc,
    title: str,
    content_builder: Callable[[tk.Frame], None],
    *,
    start_expanded: bool = False,
    header_bg: str = "#e3f2fd",
    header_fg: str = "#1565c0",
    content_bg: str = "#f0f0f0",
    content_relief: str = "solid",
    content_borderwidth: int = 1,
    content_padx: int = 10,
    content_pady: int = 10,
) -> tk.Frame:
    """
    Create a collapsible section with header and content.

    Args:
        parent: Parent widget
        title: Header text (can include emoji, e.g. "⚡ Sweep Parameters")
        content_builder: Callable(parent_frame) that creates the content widgets
        start_expanded: Whether content is visible initially
        header_bg: Header background color
        header_fg: Header text color
        content_bg: Content background color
        content_relief: Content frame relief
        content_borderwidth: Content frame border width
        content_padx: Content padding x
        content_pady: Content padding y

    Returns:
        The container frame
    """
    container = tk.Frame(parent, bg=content_bg)
    container.pack(fill="x", padx=5, pady=5)

    header_frame = tk.Frame(container, bg=header_bg, relief="raised", borderwidth=1, cursor="hand2")
    header_frame.pack(fill="x")

    is_expanded = tk.BooleanVar(value=start_expanded)
    arrow = "▼" if start_expanded else "►"
    arrow_label = tk.Label(header_frame, text=arrow, bg=header_bg, font=("Segoe UI", 10, "bold"), fg="#1976d2")
    arrow_label.pack(side="left", padx=8)

    tk.Label(header_frame, text=title, font=("Segoe UI", 10, "bold"), bg=header_bg, fg=header_fg).pack(
        side="left", pady=8
    )

    content_frame = tk.Frame(
        container,
        bg=content_bg,
        relief=content_relief,
        borderwidth=content_borderwidth,
        padx=content_padx,
        pady=content_pady,
    )

    def toggle():
        if is_expanded.get():
            content_frame.pack_forget()
            arrow_label.config(text="►")
            is_expanded.set(False)
        else:
            content_frame.pack(fill="x")
            arrow_label.config(text="▼")
            is_expanded.set(True)

    header_frame.bind("<Button-1>", lambda e: toggle())
    arrow_label.bind("<Button-1>", lambda e: toggle())

    content_builder(content_frame)
    if start_expanded:
        content_frame.pack(fill="x")

    return container
