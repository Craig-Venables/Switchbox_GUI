"""
Motor Control GUI - Laser Control Section
=========================================
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from gui.motor_control_gui import config
from gui.motor_control_gui.ui.widgets import CollapsibleFrame

try:
    from Equipment.managers.laser import LaserManager
except ModuleNotFoundError:
    LaserManager = None  # type: ignore[misc, assignment]


def create_laser_controls(gui: Any, parent: tk.Frame, start_expanded: bool = True) -> None:
    """Build laser controller controls."""
    c = config.COLORS
    collapsible = CollapsibleFrame(
        parent, "🔴 Laser Control", bg_color=c["bg_dark"], fg_color=c["fg_primary"], start_expanded=start_expanded
    )
    collapsible.pack(fill=tk.X, pady=3)
    gui.collapsible_sections.append(collapsible)

    laser_frame = collapsible.get_content_frame()
    laser_frame.configure(bg=c["bg_medium"])

    tk.Label(
        laser_frame,
        text="Configuration:",
        fg=c["fg_primary"],
        bg=c["bg_medium"],
    ).grid(row=0, column=0, columnspan=2, sticky="w", pady=2)

    laser_config_options = ["Custom..."] + [
        f"{cfg['port']} @ {cfg['baud']} baud" for cfg in gui.laser_configs
    ]

    gui.laser_config_combo = ttk.Combobox(
        laser_frame,
        values=laser_config_options,
        state="readonly",
        width=30,
    )
    gui.laser_config_combo.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 5))
    current_port = gui.var_laser_port.get()
    current_baud = gui.var_laser_baud.get()
    matching_config = f"{current_port} @ {current_baud} baud"
    if matching_config in laser_config_options:
        gui.laser_config_combo.set(matching_config)
    else:
        gui.laser_config_combo.set("Custom...")
    gui.laser_config_combo.bind("<<ComboboxSelected>>", gui._on_laser_config_selected)

    tk.Label(
        laser_frame,
        text="COM Port:",
        fg=c["fg_primary"],
        bg=c["bg_medium"],
    ).grid(row=2, column=0, sticky="w", pady=2)
    port_entry = tk.Entry(
        laser_frame,
        textvariable=gui.var_laser_port,
        bg=c["bg_light"],
        fg=c["fg_primary"],
        insertbackground=c["fg_primary"],
    )
    port_entry.grid(row=2, column=1, sticky="ew", pady=2)

    tk.Label(
        laser_frame,
        text="Baud Rate:",
        fg=c["fg_primary"],
        bg=c["bg_medium"],
    ).grid(row=3, column=0, sticky="w", pady=2)
    baud_entry = tk.Entry(
        laser_frame,
        textvariable=gui.var_laser_baud,
        bg=c["bg_light"],
        fg=c["fg_primary"],
        insertbackground=c["fg_primary"],
    )
    baud_entry.grid(row=3, column=1, sticky="ew", pady=2)

    btn_frame = tk.Frame(laser_frame, bg=c["bg_medium"])
    btn_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(5, 5))
    btn_frame.columnconfigure(0, weight=1)
    btn_frame.columnconfigure(1, weight=1)

    connect_btn = tk.Button(
        btn_frame,
        text="Connect",
        command=gui._on_laser_connect,
        bg=c["accent_green"],
        fg="black",
        font=("Arial", 8),
    )
    connect_btn.grid(row=0, column=0, sticky="ew", padx=(0, 2))

    disconnect_btn = tk.Button(
        btn_frame,
        text="Disconnect",
        command=gui._on_laser_disconnect,
        bg=c["accent_red"],
        fg="white",
        font=("Arial", 8),
    )
    disconnect_btn.grid(row=0, column=1, sticky="ew", padx=(2, 0))

    tk.Label(
        laser_frame,
        textvariable=gui.var_laser_status,
        fg=c["accent_yellow"],
        bg=c["bg_medium"],
        font=("Arial", 9),
    ).grid(row=5, column=0, columnspan=2, sticky="w", pady=2)

    emission_check = tk.Checkbutton(
        laser_frame,
        text="Emission Enabled",
        variable=gui.var_laser_enabled,
        command=gui._on_laser_toggle,
        fg=c["fg_primary"],
        bg=c["bg_medium"],
        selectcolor=c["bg_light"],
        activebackground=c["bg_medium"],
        activeforeground=c["fg_primary"],
    )
    emission_check.grid(row=6, column=0, columnspan=2, sticky="w", pady=2)

    tk.Label(
        laser_frame,
        text="Power (mW):",
        fg=c["fg_primary"],
        bg=c["bg_medium"],
    ).grid(row=7, column=0, sticky="w", pady=2)

    power_frame = tk.Frame(laser_frame, bg=c["bg_medium"])
    power_frame.grid(row=7, column=1, sticky="ew", pady=2)
    power_frame.columnconfigure(1, weight=1)

    decrease_btn = tk.Button(
        power_frame,
        text="−",
        command=gui._decrease_laser_power,
        bg=c["accent_blue"],
        fg="white",
        font=("Arial", 10, "bold"),
        width=3,
    )
    decrease_btn.grid(row=0, column=0, padx=(0, 2))

    power_entry = tk.Entry(
        power_frame,
        textvariable=gui.var_laser_power,
        bg=c["bg_light"],
        fg=c["fg_primary"],
        insertbackground=c["fg_primary"],
    )
    power_entry.grid(row=0, column=1, sticky="ew", padx=2)

    increase_btn = tk.Button(
        power_frame,
        text="+",
        command=gui._increase_laser_power,
        bg=c["accent_blue"],
        fg="white",
        font=("Arial", 10, "bold"),
        width=3,
    )
    increase_btn.grid(row=0, column=2, padx=(2, 0))

    apply_btn = tk.Button(
        laser_frame,
        text="Apply Power",
        command=gui._on_apply_laser_power,
        bg=c["accent_blue"],
        fg="white",
        font=("Arial", 9),
    )
    apply_btn.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(5, 0))

    laser_frame.columnconfigure(1, weight=1)

    if LaserManager is None:
        gui.var_laser_status.set("Laser: Driver unavailable (install pyserial)")
        for widget in (
            gui.laser_config_combo,
            port_entry,
            baud_entry,
            connect_btn,
            disconnect_btn,
            emission_check,
            power_entry,
            decrease_btn,
            increase_btn,
            apply_btn,
        ):
            widget.configure(state=tk.DISABLED)
