"""Save options section for Oscilloscope Pulse GUI."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import config as gui_config
from .widgets import ToolTip, create_collapsible_frame


def build_save_options_content(gui, frame):
    """Build save options content."""
    gui.vars["auto_save"] = tk.BooleanVar(value=gui.config.get("auto_save", True))
    auto_save_check = ttk.Checkbutton(
        frame,
        text="Auto-save after 'Read & Analyze'",
        variable=gui.vars["auto_save"],
    )
    auto_save_check.pack(side="left", padx=5)
    ToolTip(
        auto_save_check,
        "Automatically save data to save directory after reading scope (filename: Pulse_Sample_Device_timestamp.txt)",
    )

    save_dir_frame = ttk.Frame(frame)
    save_dir_frame.pack(fill="x", pady=(5, 0))
    ttk.Label(save_dir_frame, text="Save to:", font=(gui_config.FONT_FAMILY, 8)).pack(side="left")
    gui.vars["save_dir_display"] = tk.StringVar(value=gui.context.get("save_directory", "Not set"))
    save_dir_label = tk.Label(
        save_dir_frame,
        textvariable=gui.vars["save_dir_display"],
        bg=gui_config.COLORS["bg"],
        fg=gui_config.COLORS["fg_secondary"],
        font=(gui_config.FONT_FAMILY, 8),
        relief=tk.SUNKEN,
        bd=1,
        padx=5,
        pady=2,
    )
    save_dir_label.pack(side="left", fill="x", expand=True, padx=(5, 0))


def create_save_options_frame(gui, parent):
    """Build collapsible save options frame."""
    create_collapsible_frame(
        gui,
        parent,
        "💾 Save Options",
        lambda f: build_save_options_content(gui, f),
        default_expanded=False,
    )
