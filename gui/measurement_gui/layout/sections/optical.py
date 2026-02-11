"""
Optical Section
===============

Collapsible optical excitation (LED/Laser) configuration for the Setup tab.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from ..constants import COLOR_BG, FONT_MAIN


def build_optical_section(parent: tk.Misc, gui: Any) -> None:
    """Build collapsible optical excitation configuration section."""
    optical_container = tk.Frame(parent, bg=COLOR_BG)
    optical_container.pack(fill="x", pady=(0, 10))

    toggle_frame = tk.Frame(optical_container, bg=COLOR_BG)
    toggle_frame.pack(fill="x")

    gui.optical_expanded_var = tk.BooleanVar(value=False)

    optical_frame = tk.LabelFrame(optical_container, text="", font=FONT_MAIN, bg=COLOR_BG, padx=10, pady=10)
    optical_frame.pack_forget()

    toggle_btn = tk.Button(
        toggle_frame,
        text="▶",
        font=("Arial", 10),
        bg=COLOR_BG,
        fg="black",
        relief="flat",
        command=lambda: toggle_optical_section(gui, optical_frame, toggle_btn),
    )
    toggle_btn.pack(side="left", padx=(0, 5))

    tk.Label(toggle_frame, text="Optical Excitation (LED/Laser) - Optional", font=FONT_MAIN, bg=COLOR_BG).pack(side="left")

    tk.Label(optical_frame, text="Type:", font=FONT_MAIN, bg=COLOR_BG).grid(row=0, column=0, sticky="w", pady=5)
    optical_types = ["None", "LED", "Laser"]
    gui.optical_type_var = tk.StringVar(value="None")
    gui.optical_type_combo = ttk.Combobox(
        optical_frame, textvariable=gui.optical_type_var, values=optical_types, font=FONT_MAIN, width=20, state="readonly"
    )
    gui.optical_type_combo.grid(row=0, column=1, sticky="ew", pady=5, padx=(10, 10))
    gui.optical_type_combo.bind("<<ComboboxSelected>>", lambda e: update_optical_ui(gui, optical_frame))

    gui.optical_led_frame = tk.Frame(optical_frame, bg=COLOR_BG)
    gui.optical_led_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=5)

    gui.optical_laser_frame = tk.Frame(optical_frame, bg=COLOR_BG)
    gui.optical_laser_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=5)

    optical_frame.columnconfigure(1, weight=1)
    gui.optical_config_frame = optical_frame
    gui.optical_toggle_button = toggle_btn


def _connect_optical_laser(gui: Any) -> None:
    """Connect to laser using current UI config (called from Connect button)."""
    if hasattr(gui, "connect_optical_laser"):
        gui.connect_optical_laser()


def _disconnect_optical_laser(gui: Any) -> None:
    """Disconnect laser (called from Disconnect button)."""
    if hasattr(gui, "disconnect_optical_laser"):
        gui.disconnect_optical_laser()


def toggle_optical_section(gui: Any, frame: tk.Frame, button: tk.Button) -> None:
    """Toggle visibility of optical configuration section."""
    if gui.optical_expanded_var.get():
        frame.pack_forget()
        button.config(text="▶")
        gui.optical_expanded_var.set(False)
    else:
        frame.pack(fill="x", pady=(0, 10))
        button.config(text="▼")
        gui.optical_expanded_var.set(True)


def update_optical_ui(gui: Any, parent: tk.Frame) -> None:
    """Update optical UI based on selected type (LED/Laser)."""
    opt_type = gui.optical_type_var.get()
    for widget in gui.optical_led_frame.winfo_children():
        widget.destroy()
    for widget in gui.optical_laser_frame.winfo_children():
        widget.destroy()

    if opt_type == "LED":
        tk.Label(gui.optical_led_frame, text="Units:", font=FONT_MAIN, bg=COLOR_BG).grid(row=0, column=0, sticky="w", pady=5)
        led_units = ["mA", "V"]
        gui.optical_led_units_var = tk.StringVar(value="mA")
        ttk.Combobox(
            gui.optical_led_frame, textvariable=gui.optical_led_units_var, values=led_units,
            font=FONT_MAIN, width=15, state="readonly"
        ).grid(row=0, column=1, sticky="ew", pady=5, padx=(10, 10))

        tk.Label(
            gui.optical_led_frame, text="Channels (e.g., 380nm:1,420nm:2):", font=FONT_MAIN, bg=COLOR_BG
        ).grid(row=1, column=0, sticky="w", pady=5)
        gui.optical_led_channels_var = tk.StringVar(value="380nm:1,420nm:2")
        ttk.Entry(gui.optical_led_frame, textvariable=gui.optical_led_channels_var, font=FONT_MAIN, width=30).grid(
            row=1, column=1, sticky="ew", pady=5, padx=(10, 10)
        )

        tk.Label(gui.optical_led_frame, text="Min:", font=FONT_MAIN, bg=COLOR_BG).grid(row=2, column=0, sticky="w", pady=5)
        gui.optical_led_min_var = tk.StringVar(value="0.0")
        ttk.Entry(gui.optical_led_frame, textvariable=gui.optical_led_min_var, font=FONT_MAIN, width=15).grid(
            row=2, column=1, sticky="ew", pady=5, padx=(10, 10)
        )
        tk.Label(gui.optical_led_frame, text="Max:", font=FONT_MAIN, bg=COLOR_BG).grid(row=2, column=2, sticky="w", pady=5, padx=(10, 0))
        gui.optical_led_max_var = tk.StringVar(value="30.0")
        ttk.Entry(gui.optical_led_frame, textvariable=gui.optical_led_max_var, font=FONT_MAIN, width=15).grid(
            row=2, column=3, sticky="ew", pady=5, padx=(10, 10)
        )

        tk.Label(gui.optical_led_frame, text="Default Channel:", font=FONT_MAIN, bg=COLOR_BG).grid(row=3, column=0, sticky="w", pady=5)
        gui.optical_led_default_channel_var = tk.StringVar(value="380nm")
        ttk.Entry(gui.optical_led_frame, textvariable=gui.optical_led_default_channel_var, font=FONT_MAIN, width=15).grid(
            row=3, column=1, sticky="ew", pady=5, padx=(10, 10)
        )
        gui.optical_led_frame.columnconfigure(1, weight=1)

    elif opt_type == "Laser":
        tk.Label(gui.optical_laser_frame, text="Driver:", font=FONT_MAIN, bg=COLOR_BG).grid(row=0, column=0, sticky="w", pady=5)
        laser_drivers = ["Oxxius"]
        gui.optical_laser_driver_var = tk.StringVar(value="Oxxius")
        ttk.Combobox(
            gui.optical_laser_frame, textvariable=gui.optical_laser_driver_var, values=laser_drivers,
            font=FONT_MAIN, width=20, state="readonly"
        ).grid(row=0, column=1, sticky="ew", pady=5, padx=(10, 10))

        tk.Label(gui.optical_laser_frame, text="Address:", font=FONT_MAIN, bg=COLOR_BG).grid(row=1, column=0, sticky="w", pady=5)
        gui.optical_laser_address_var = tk.StringVar(value="COM4")
        ttk.Entry(gui.optical_laser_frame, textvariable=gui.optical_laser_address_var, font=FONT_MAIN, width=30).grid(
            row=1, column=1, sticky="ew", pady=5, padx=(10, 10)
        )

        tk.Label(gui.optical_laser_frame, text="Baud:", font=FONT_MAIN, bg=COLOR_BG).grid(row=2, column=0, sticky="w", pady=5)
        gui.optical_laser_baud_var = tk.StringVar(value="19200")
        ttk.Entry(gui.optical_laser_frame, textvariable=gui.optical_laser_baud_var, font=FONT_MAIN, width=15).grid(
            row=2, column=1, sticky="ew", pady=5, padx=(10, 10)
        )

        tk.Label(gui.optical_laser_frame, text="Units:", font=FONT_MAIN, bg=COLOR_BG).grid(row=3, column=0, sticky="w", pady=5)
        laser_units = ["mW"]
        gui.optical_laser_units_var = tk.StringVar(value="mW")
        ttk.Combobox(
            gui.optical_laser_frame, textvariable=gui.optical_laser_units_var, values=laser_units,
            font=FONT_MAIN, width=15, state="readonly"
        ).grid(row=3, column=1, sticky="ew", pady=5, padx=(10, 10))

        tk.Label(gui.optical_laser_frame, text="Wavelength (nm):", font=FONT_MAIN, bg=COLOR_BG).grid(row=4, column=0, sticky="w", pady=5)
        gui.optical_laser_wavelength_var = tk.StringVar(value="405")
        ttk.Entry(gui.optical_laser_frame, textvariable=gui.optical_laser_wavelength_var, font=FONT_MAIN, width=15).grid(
            row=4, column=1, sticky="ew", pady=5, padx=(10, 10)
        )

        tk.Label(gui.optical_laser_frame, text="Min (mW):", font=FONT_MAIN, bg=COLOR_BG).grid(row=5, column=0, sticky="w", pady=5)
        gui.optical_laser_min_var = tk.StringVar(value="0.0")
        ttk.Entry(gui.optical_laser_frame, textvariable=gui.optical_laser_min_var, font=FONT_MAIN, width=15).grid(
            row=5, column=1, sticky="ew", pady=5, padx=(10, 10)
        )
        tk.Label(gui.optical_laser_frame, text="Max (mW):", font=FONT_MAIN, bg=COLOR_BG).grid(row=5, column=2, sticky="w", pady=5, padx=(10, 0))
        gui.optical_laser_max_var = tk.StringVar(value="10.0")
        ttk.Entry(gui.optical_laser_frame, textvariable=gui.optical_laser_max_var, font=FONT_MAIN, width=15).grid(
            row=5, column=3, sticky="ew", pady=5, padx=(10, 10)
        )

        tk.Label(gui.optical_laser_frame, text="Default (mW):", font=FONT_MAIN, bg=COLOR_BG).grid(row=6, column=0, sticky="w", pady=5)
        gui.optical_laser_default_var = tk.StringVar(value="1.0")
        ttk.Entry(gui.optical_laser_frame, textvariable=gui.optical_laser_default_var, font=FONT_MAIN, width=15).grid(
            row=6, column=1, sticky="ew", pady=5, padx=(10, 10)
        )

        # Connect / Disconnect and status
        btn_row = tk.Frame(gui.optical_laser_frame, bg=COLOR_BG)
        btn_row.grid(row=7, column=0, columnspan=4, sticky="w", pady=(10, 5))
        ttk.Button(btn_row, text="Connect", command=lambda: _connect_optical_laser(gui)).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_row, text="Disconnect", command=lambda: _disconnect_optical_laser(gui)).pack(side=tk.LEFT, padx=(0, 5))
        gui.optical_laser_status_var = tk.StringVar(value="Not connected")
        if getattr(gui, "optical", None) is not None:
            try:
                caps = getattr(gui.optical, "capabilities", {}) or {}
                if caps.get("type") == "Laser":
                    gui.optical_laser_status_var.set("Connected")
            except Exception:
                pass
        ttk.Label(btn_row, textvariable=gui.optical_laser_status_var, font=FONT_MAIN).pack(side=tk.LEFT, padx=(10, 0))

        gui.optical_laser_frame.columnconfigure(1, weight=1)
