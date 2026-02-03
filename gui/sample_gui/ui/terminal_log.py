"""
Terminal Log UI Builder
=======================

Creates the activity log section with filtering and export.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, List, Tuple


def create_terminal_log(sample_gui: Any) -> None:
    """
    Create the terminal log section with color coding and filtering.

    Args:
        sample_gui: The SampleGUI instance. Must have device_selection_frame, terminal_filter,
                    and methods: _apply_terminal_filter, clear_terminal, export_terminal_log.
    """
    terminal_container = ttk.LabelFrame(
        sample_gui.device_selection_frame,
        text="Activity Log",
        padding=5,
    )
    terminal_container.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
    terminal_container.grid_rowconfigure(0, weight=1)
    terminal_container.grid_columnconfigure(0, weight=1)

    control_frame = ttk.Frame(terminal_container)
    control_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))

    ttk.Label(control_frame, text="Filter:").pack(side="left", padx=5)

    filter_combo = ttk.Combobox(
        control_frame,
        textvariable=sample_gui.terminal_filter,
        values=["All", "Info", "Success", "Warning", "Error"],
        width=10,
        state="readonly",
    )
    filter_combo.pack(side="left", padx=5)
    filter_combo.bind("<<ComboboxSelected>>", lambda e: sample_gui._apply_terminal_filter())

    ttk.Button(control_frame, text="Clear Log", command=sample_gui.clear_terminal, width=10).pack(side="left", padx=5)
    ttk.Button(control_frame, text="Export Log", command=sample_gui.export_terminal_log, width=10).pack(side="left", padx=5)

    text_frame = ttk.Frame(terminal_container)
    text_frame.grid(row=1, column=0, sticky="nsew")
    text_frame.grid_rowconfigure(0, weight=1)
    text_frame.grid_columnconfigure(0, weight=1)

    sample_gui.terminal_output = tk.Text(
        text_frame,
        height=6,
        width=100,
        state=tk.DISABLED,
        bg="#1e1e1e",
        fg="#d4d4d4",
        font=("Consolas", 9),
        wrap=tk.WORD,
    )
    sample_gui.terminal_output.grid(row=0, column=0, sticky="nsew")

    terminal_scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=sample_gui.terminal_output.yview)
    terminal_scrollbar.grid(row=0, column=1, sticky="ns")
    sample_gui.terminal_output.configure(yscrollcommand=terminal_scrollbar.set)

    sample_gui.terminal_output.tag_config("INFO", foreground="#569CD6")
    sample_gui.terminal_output.tag_config("SUCCESS", foreground="#4CAF50")
    sample_gui.terminal_output.tag_config("WARNING", foreground="#FFA500")
    sample_gui.terminal_output.tag_config("ERROR", foreground="#F44336")
    sample_gui.terminal_output.tag_config("TIMESTAMP", foreground="#888888")

    sample_gui.terminal_messages: List[Tuple[str, str, str]] = []
