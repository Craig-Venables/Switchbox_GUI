"""
Scrollable help window for Pulse Testing GUI (general + 4200 PMU guide).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import List, Optional, Tuple

from gui.pulse_testing_gui import config
from gui.pulse_testing_gui.pmu_help_content import (
    GENERAL_HELP_SECTIONS,
    PMU_HELP_SECTIONS,
    HelpSection,
)

HelpTab = Tuple[str, List[HelpSection]]


def _build_scrollable_tab(parent: tk.Widget, sections: List[HelpSection], title: str) -> None:
    """Fill a frame with titled help sections."""
    canvas = tk.Canvas(parent, bg="#f0f0f0", highlightthickness=0)
    scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
    inner = tk.Frame(canvas, bg="#f0f0f0")

    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    canvas.bind("<MouseWheel>", _on_mousewheel)
    inner.bind("<MouseWheel>", _on_mousewheel)

    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    pad = {"padx": 16, "pady": 6, "anchor": "w"}
    tk.Label(
        inner,
        text=title,
        font=("Segoe UI", 15, "bold"),
        bg="#f0f0f0",
        fg="#1565c0",
    ).pack(**pad)

    for heading, body in sections:
        tk.Label(
            inner,
            text=heading,
            font=("Segoe UI", 11, "bold"),
            bg="#f0f0f0",
        ).pack(**pad)
        tk.Label(
            inner,
            text=body,
            justify=tk.LEFT,
            bg="#f0f0f0",
            wraplength=720,
        ).pack(**pad)


def open_help_guide(parent: tk.Tk, *, initial_tab: str = "general") -> None:
    """Open modal help window with General and 4200 PMU tabs."""
    win = tk.Toplevel(parent)
    win.title("Pulse Testing Help")
    win.geometry(config.HELP_WINDOW_GEOMETRY)
    win.configure(bg="#f0f0f0")
    try:
        win.transient(parent)
    except Exception:
        pass

    notebook = ttk.Notebook(win)
    notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    tabs: List[HelpTab] = [
        ("General", GENERAL_HELP_SECTIONS),
        ("4200 PMU", PMU_HELP_SECTIONS),
    ]

    tab_ids: List[str] = []
    for tab_name, sections in tabs:
        frame = tk.Frame(notebook, bg="#f0f0f0")
        notebook.add(frame, text=f"  {tab_name}  ")
        tab_ids.append(tab_name.lower().replace(" ", "_"))
        display_title = "Pulse Testing Guide" if tab_name == "General" else "4200 PMU — Pulses & Current Range"
        _build_scrollable_tab(frame, sections, display_title)

    if initial_tab == "pmu" or initial_tab == "4200_pmu":
        notebook.select(1)
    else:
        notebook.select(0)

    btn_row = tk.Frame(win, bg="#f0f0f0")
    btn_row.pack(fill=tk.X, padx=8, pady=(0, 8))
    tk.Button(
        btn_row,
        text="Close",
        command=win.destroy,
        width=12,
    ).pack(side=tk.RIGHT)
