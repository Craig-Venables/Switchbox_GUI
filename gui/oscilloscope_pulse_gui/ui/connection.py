"""Connection settings section for Oscilloscope Pulse GUI."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .widgets import create_collapsible_frame


def build_connection_content(gui, frame):
    """Build connection settings content."""
    smu_frame = ttk.Frame(frame)
    smu_frame.pack(fill="x", pady=2)
    ttk.Label(smu_frame, text="SMU Address:").pack(side="left")
    gui.vars["smu_address"] = tk.StringVar(value=gui.config.get("smu_address", "GPIB0::17::INSTR"))
    smu_combo = ttk.Combobox(
        smu_frame,
        textvariable=gui.vars["smu_address"],
        values=gui.context.get("smu_ports", ["GPIB0::17::INSTR"]),
        width=20,
    )
    smu_combo.pack(side="right")
    gui.widgets["smu_address"] = smu_combo
    gui.widgets["smu_combo"] = smu_combo

    scope_frame = ttk.Frame(frame)
    scope_frame.pack(fill="x", pady=2)
    ttk.Label(scope_frame, text="Scope Address:").pack(side="left")
    gui.vars["scope_address"] = tk.StringVar(value=gui.config.get("scope_address", ""))
    scope_combo = ttk.Combobox(
        scope_frame,
        textvariable=gui.vars["scope_address"],
        values=gui.context.get("scope_ports", []),
        width=20,
    )
    scope_combo.pack(side="right")
    refresh_btn = ttk.Button(
        scope_frame,
        text="Refresh",
        command=gui.callbacks.get("refresh_scopes", lambda: None),
        style="Small.TButton",
    )
    refresh_btn.pack(side="right", padx=5)
    gui.widgets["scope_combo"] = scope_combo

    conn_btn_frame = ttk.Frame(frame)
    conn_btn_frame.pack(fill="x", pady=(10, 0))

    gui.widgets["connect_smu_btn"] = ttk.Button(
        conn_btn_frame,
        text="🔌 Connect SMU",
        command=gui.callbacks.get("connect_smu", lambda: None),
        style="Action.TButton",
    )
    gui.widgets["connect_smu_btn"].pack(side="left", padx=5)

    gui.vars["smu_status"] = tk.StringVar(value="SMU: Not Connected")
    smu_status_label = ttk.Label(
        conn_btn_frame,
        textvariable=gui.vars["smu_status"],
        style="Status.TLabel",
        foreground="red",
    )
    smu_status_label.pack(side="left", padx=10)
    gui.widgets["smu_status_label"] = smu_status_label


def create_connection_frame(gui, parent):
    """Build collapsible connection settings frame."""
    create_collapsible_frame(gui, parent, "Connections", lambda f: build_connection_content(gui, f), default_expanded=True)
