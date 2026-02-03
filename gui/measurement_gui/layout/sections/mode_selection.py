"""
Mode Selection Section
======================

Sample & Save Settings collapsible panel for the Measurements tab.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from ..constants import COLOR_BG, FONT_BUTTON, FONT_MAIN
from ._collapsible import build_collapsible_section


def build_mode_selection(builder: Any, parent: tk.Misc) -> None:
    """Build the Sample & Save Settings collapsible section."""
    gui = builder.gui

    def build_content(content_frame: tk.Frame) -> None:
        checkbox_frame = tk.Frame(content_frame, bg=COLOR_BG)
        checkbox_frame.pack(fill="x", pady=(0, 12))

        gui.adaptive_var = tk.IntVar(value=1)
        cb_label_frame = tk.Frame(checkbox_frame, bg="#e8f5e9", relief="solid", borderwidth=1, padx=10, pady=6)
        cb_label_frame.pack(fill="x")

        ttk.Checkbutton(
            cb_label_frame,
            text="Measure One Device",
            variable=gui.adaptive_var,
            command=builder.callbacks.get("measure_one_device"),
        ).pack(side="left")
        tk.Label(
            cb_label_frame, text="(Single device mode)", font=("Segoe UI", 8), bg="#e8f5e9", fg="#2e7d32"
        ).pack(side="left", padx=(10, 0))

        tk.Label(content_frame, text="Sample Name:", font=FONT_MAIN, bg=COLOR_BG, fg="#424242").pack(
            anchor="w", pady=(0, 2)
        )
        gui.sample_name_var = tk.StringVar()
        if hasattr(gui, "sample_gui") and gui.sample_gui and hasattr(gui.sample_gui, "current_device_name"):
            device_name = getattr(gui.sample_gui, "current_device_name", None)
            if device_name:
                gui.sample_name_var.set(device_name)
        gui.sample_name_entry = ttk.Entry(content_frame, textvariable=gui.sample_name_var, font=FONT_MAIN)
        gui.sample_name_entry.pack(fill="x", pady=(0, 10))

        tk.Label(content_frame, text="Additional Info:", font=FONT_MAIN, bg=COLOR_BG, fg="#424242").pack(
            anchor="w", pady=(0, 2)
        )
        gui.additional_info_var = tk.StringVar()
        gui.additional_info_entry = ttk.Entry(content_frame, textvariable=gui.additional_info_var, font=FONT_MAIN)
        gui.additional_info_entry.pack(fill="x", pady=(0, 10))

        ttk.Separator(content_frame, orient="horizontal").pack(fill="x", pady=10)

        gui.use_custom_save_var = tk.BooleanVar(value=False)
        gui.custom_save_location_var = tk.StringVar(value="")
        gui.custom_save_location = None

        tk.Checkbutton(
            content_frame,
            text="Use custom save location",
            variable=gui.use_custom_save_var,
            command=builder.callbacks.get("on_custom_save_toggle"),
            bg=COLOR_BG,
            font=FONT_MAIN,
            fg="#424242",
        ).pack(anchor="w", pady=(0, 8))

        save_frame = tk.Frame(content_frame, bg=COLOR_BG)
        save_frame.pack(fill="x")
        save_frame.columnconfigure(0, weight=1)

        gui.save_path_entry = tk.Entry(
            save_frame,
            textvariable=gui.custom_save_location_var,
            state="disabled",
            font=FONT_MAIN,
            relief="solid",
            borderwidth=1,
        )
        gui.save_path_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        browse_btn = tk.Button(
            save_frame,
            text="Browse...",
            command=builder.callbacks.get("browse_save"),
            font=FONT_BUTTON,
            bg="#2196f3",
            fg="white",
            relief="raised",
            padx=12,
            pady=4,
            state="disabled",
        )
        browse_btn.grid(row=0, column=1)
        gui.save_browse_button = browse_btn

        if hasattr(gui, "_load_save_location_config"):
            gui._load_save_location_config()

    container = build_collapsible_section(
        parent,
        "Sample & Save Settings",
        build_content,
        start_expanded=False,
        content_bg=COLOR_BG,
    )
    builder.widgets["mode_selection"] = container
