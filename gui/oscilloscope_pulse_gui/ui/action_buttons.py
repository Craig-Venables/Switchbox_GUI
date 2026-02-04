"""Measurement workflow action buttons for Oscilloscope Pulse GUI."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import config as gui_config


def create_action_buttons(gui, parent):
    """Build action buttons frame - simplified workflow."""
    frame = ttk.LabelFrame(parent, text="📋 Measurement Workflow", padding=5)
    frame.pack(fill="x", pady=2)

    instructions = "1️⃣ Set scope | 2️⃣ Send Pulse | 3️⃣ Verify | 4️⃣ Read & Analyze"
    instr_label = tk.Label(
        frame,
        text=instructions,
        justify="left",
        bg=gui_config.COLORS["bg"],
        font=(gui_config.FONT_FAMILY, 8),
        fg=gui_config.COLORS["header"],
    )
    instr_label.pack(fill="x", pady=(0, 4))

    btn_frame = ttk.Frame(frame)
    btn_frame.pack(fill="x", pady=2)

    gui.widgets["pulse_only_btn"] = ttk.Button(
        btn_frame,
        text="2️⃣ Send Pulse",
        command=gui.callbacks.get("pulse_only", lambda: None),
        style="Action.TButton",
    )
    gui.widgets["pulse_only_btn"].pack(side="left", padx=2, fill="x", expand=True)

    gui.widgets["grab_scope_btn"] = ttk.Button(
        btn_frame,
        text="4️⃣ Read & Analyze",
        command=gui.callbacks.get("grab_scope", lambda: None),
        style="Action.TButton",
    )
    gui.widgets["grab_scope_btn"].pack(side="left", padx=2, fill="x", expand=True)

    btn_frame2 = ttk.Frame(frame)
    btn_frame2.pack(fill="x", pady=(5, 0))

    save_btn = ttk.Button(
        btn_frame2,
        text="💾 Save Data",
        command=gui.callbacks.get("save", lambda: None),
    )
    save_btn.pack(side="left", padx=2, fill="x", expand=True)

    gui.widgets["stop_btn"] = ttk.Button(
        btn_frame2,
        text="⏹ Stop",
        command=gui.callbacks.get("stop", lambda: None),
        style="Stop.TButton",
        state="disabled",
    )
    gui.widgets["stop_btn"].pack(side="left", padx=2, fill="x", expand=True)

