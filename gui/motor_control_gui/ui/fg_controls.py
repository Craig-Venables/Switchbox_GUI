"""
Motor Control GUI - Function Generator Section
==============================================
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from gui.motor_control_gui import config
from gui.motor_control_gui.ui.widgets import CollapsibleFrame

try:
    from Equipment.managers.function_generator import FunctionGeneratorManager
except ModuleNotFoundError:
    FunctionGeneratorManager = None  # type: ignore[misc, assignment]


def create_fg_controls(gui: Any, parent: tk.Frame) -> None:
    """Build function generator controls."""
    c = config.COLORS
    collapsible = CollapsibleFrame(
        parent, "⚡ Function Generator", bg_color=c["bg_dark"], fg_color=c["fg_primary"]
    )
    collapsible.pack(fill=tk.X, pady=3)
    collapsible.collapse()
    gui.collapsible_sections.append(collapsible)

    fg_frame = collapsible.get_content_frame()
    fg_frame.configure(bg=c["bg_medium"])

    tk.Label(
        fg_frame,
        text="VISA Address:",
        fg=c["fg_primary"],
        bg=c["bg_medium"],
    ).grid(row=0, column=0, columnspan=2, sticky="w", pady=2)

    addr_dropdown_frame = tk.Frame(fg_frame, bg=c["bg_medium"])
    addr_dropdown_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 5))
    addr_dropdown_frame.columnconfigure(0, weight=1)

    gui.fg_addr_combo = ttk.Combobox(
        addr_dropdown_frame,
        values=["Custom..."] + gui.fg_addresses,
        state="readonly",
        width=50,
    )
    gui.fg_addr_combo.grid(row=0, column=0, sticky="ew", padx=(0, 5))
    current_addr = gui.var_fg_addr.get()
    if current_addr in gui.fg_addresses:
        gui.fg_addr_combo.set(current_addr)
    else:
        gui.fg_addr_combo.set("Custom...")
    gui.fg_addr_combo.bind("<<ComboboxSelected>>", gui._on_fg_addr_selected)

    auto_btn = tk.Button(
        addr_dropdown_frame,
        text="🔍",
        command=gui._auto_detect_fg,
        bg=c["accent_blue"],
        fg="white",
        width=3,
    )
    auto_btn.grid(row=0, column=1, padx=(0, 5))

    addr_frame = tk.Frame(fg_frame, bg=c["bg_medium"])
    addr_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 5))
    addr_frame.columnconfigure(0, weight=1)

    addr_entry = tk.Entry(
        addr_frame,
        textvariable=gui.var_fg_addr,
        bg=c["bg_light"],
        fg=c["fg_primary"],
        insertbackground=c["fg_primary"],
    )
    addr_entry.grid(row=0, column=0, sticky="ew")

    btn_frame = tk.Frame(fg_frame, bg=c["bg_medium"])
    btn_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 5))
    btn_frame.columnconfigure(0, weight=1)
    btn_frame.columnconfigure(1, weight=1)

    connect_btn = tk.Button(
        btn_frame,
        text="Connect",
        command=gui._on_fg_connect,
        bg=c["accent_green"],
        fg="black",
        font=("Arial", 8),
    )
    connect_btn.grid(row=0, column=0, sticky="ew", padx=(0, 2))

    disconnect_btn = tk.Button(
        btn_frame,
        text="Disconnect",
        command=gui._on_fg_disconnect,
        bg=c["accent_red"],
        fg="white",
        font=("Arial", 8),
    )
    disconnect_btn.grid(row=0, column=1, sticky="ew", padx=(2, 0))

    tk.Label(
        fg_frame,
        textvariable=gui.var_fg_status,
        fg=c["accent_yellow"],
        bg=c["bg_medium"],
        font=("Arial", 9),
    ).grid(row=4, column=0, columnspan=2, sticky="w", pady=2)

    output_check = tk.Checkbutton(
        fg_frame,
        text="Output Enabled",
        variable=gui.var_fg_enabled,
        command=gui._on_fg_toggle,
        fg=c["fg_primary"],
        bg=c["bg_medium"],
        selectcolor=c["bg_light"],
        activebackground=c["bg_medium"],
        activeforeground=c["fg_primary"],
    )
    output_check.grid(row=5, column=0, columnspan=2, sticky="w", pady=2)

    tk.Label(
        fg_frame,
        text="DC Voltage (V):",
        fg=c["fg_primary"],
        bg=c["bg_medium"],
    ).grid(row=6, column=0, sticky="w", pady=2)
    amplitude_entry = tk.Entry(
        fg_frame,
        textvariable=gui.var_fg_amplitude,
        bg=c["bg_light"],
        fg=c["fg_primary"],
        insertbackground=c["fg_primary"],
    )
    amplitude_entry.grid(row=6, column=1, sticky="ew", pady=2)

    apply_btn = tk.Button(
        fg_frame,
        text="Apply Voltage",
        command=gui._on_apply_amplitude,
        bg=c["accent_blue"],
        fg="white",
        font=("Arial", 9),
    )
    apply_btn.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(5, 0))

    fg_frame.columnconfigure(1, weight=1)

    if FunctionGeneratorManager is None:
        gui.var_fg_status.set("FG: Driver unavailable (install pyvisa)")
        for widget in (
            gui.fg_addr_combo,
            addr_entry,
            auto_btn,
            connect_btn,
            disconnect_btn,
            output_check,
            amplitude_entry,
            apply_btn,
        ):
            widget.configure(state=tk.DISABLED)
