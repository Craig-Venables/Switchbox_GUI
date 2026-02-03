"""
Connection Section
==================

Setup tab: system configuration and instrument connections (SMU, PSU, Temp, Optical).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from ..constants import COLOR_BG, COLOR_PRIMARY, FONT_BUTTON, FONT_HEADING, FONT_MAIN


def build_connection_section_modern(builder: Any, parent: tk.Misc) -> None:
    """
    Build the modern connection section for the Setup tab.

    Args:
        builder: Layout builder with gui, callbacks, widgets, _scan_visa_resources,
                 _validate_and_identify_address, _refresh_address_combo, _test_connection,
                 _build_optical_section.
        parent: Parent widget.
    """
    gui = builder.gui

    frame = tk.LabelFrame(
        parent,
        text="System Configuration & Instrument Connections",
        font=FONT_HEADING,
        bg=COLOR_BG,
        relief="solid",
        borderwidth=1,
        padx=15,
        pady=15,
    )
    frame.pack(fill="x", padx=5, pady=5)

    system_frame = tk.LabelFrame(frame, text="System Configuration", font=FONT_MAIN, bg=COLOR_BG, padx=10, pady=10)
    system_frame.pack(fill="x", pady=(0, 15))

    tk.Label(system_frame, text="Load System:", font=FONT_MAIN, bg=COLOR_BG).grid(row=0, column=0, sticky="w", pady=5, padx=(0, 10))

    systems = gui.load_systems() if hasattr(gui, "load_systems") else []
    if not systems or systems == ["No systems available"]:
        systems = []

    if not hasattr(gui, "system_var") or gui.system_var is None:
        default_value = "Please Select System" if systems and systems[0] == "Please Select System" else (systems[0] if systems else "")
        gui.system_var = tk.StringVar(value=default_value)
    else:
        current_value = gui.system_var.get()
        if not current_value or current_value not in systems:
            if systems:
                default_value = "Please Select System" if systems[0] == "Please Select System" else systems[0]
                gui.system_var.set(default_value)

    if hasattr(gui, "system_dropdown") and gui.system_dropdown:
        gui.system_dropdown["values"] = systems

    gui.system_combo = ttk.Combobox(system_frame, textvariable=gui.system_var, values=systems, font=FONT_MAIN, width=25, state="readonly")
    gui.system_combo.grid(row=0, column=1, sticky="ew", pady=5, padx=(0, 10))

    def on_system_selected(event=None):
        if builder._updating_system:
            return
        selected_system = gui.system_var.get()
        if not selected_system or selected_system == "Please Select System":
            return
        load_cb = builder.callbacks.get("load_system")
        if load_cb:
            load_cb()
        change_cb = builder.callbacks.get("on_system_change")
        if change_cb:
            change_cb(selected_system)
        gui.master.after(100, builder._auto_connect_instruments)

    gui.system_combo.bind("<<ComboboxSelected>>", on_system_selected)

    def on_load_button_click():
        selected_system = gui.system_var.get()
        if not selected_system or selected_system == "Please Select System":
            return
        load_cb = builder.callbacks.get("load_system")
        if load_cb:
            load_cb()
        change_cb = builder.callbacks.get("on_system_change")
        if change_cb:
            change_cb(selected_system)
        gui.master.after(100, builder._auto_connect_instruments)

    tk.Button(system_frame, text="Load", font=FONT_BUTTON, bg=COLOR_PRIMARY, fg="white", command=on_load_button_click, padx=15).grid(
        row=0, column=2, pady=5, padx=(0, 10)
    )
    tk.Button(system_frame, text="Save As...", font=FONT_BUTTON, bg=COLOR_PRIMARY, fg="white", command=builder.callbacks.get("save_system", lambda: None), padx=15).grid(
        row=0, column=3, pady=5
    )

    system_frame.columnconfigure(1, weight=1)

    _build_smu_section(builder, frame, gui)
    _build_psu_section(builder, frame, gui)
    _build_temp_section(builder, frame, gui)
    from .optical import build_optical_section
    build_optical_section(frame, gui)

    builder.widgets["connection_section_modern"] = frame


def _build_smu_section(builder: Any, frame: tk.Frame, gui) -> None:
    """SMU/Keithley section."""
    smu_frame = tk.LabelFrame(frame, text="SMU / Keithley", font=FONT_MAIN, bg=COLOR_BG, padx=10, pady=10)
    smu_frame.pack(fill="x", pady=(0, 10))

    tk.Label(smu_frame, text="Type:", font=FONT_MAIN, bg=COLOR_BG).grid(row=0, column=0, sticky="w", pady=5)
    smu_types = ["Keithley 2401", "Keithley 2450", "Keithley 2450 (Simulation)", "Hp4140b", "Keithley 4200A"]
    gui.smu_type_var = tk.StringVar(value=getattr(gui, "SMU_type", smu_types[0]))
    gui.smu_type_combo = ttk.Combobox(smu_frame, textvariable=gui.smu_type_var, values=smu_types, font=FONT_MAIN, width=25, state="readonly")
    gui.smu_type_combo.grid(row=0, column=1, sticky="ew", pady=5, padx=(10, 10))

    tk.Label(smu_frame, text="Address:", font=FONT_MAIN, bg=COLOR_BG).grid(row=1, column=0, sticky="w", pady=5)
    gui.keithley_address_var = tk.StringVar(value=getattr(gui, "keithley_address", ""))

    address_frame = tk.Frame(smu_frame, bg=COLOR_BG)
    address_frame.grid(row=1, column=1, sticky="ew", pady=5, padx=(10, 5))

    gui.iv_address_combo = ttk.Combobox(address_frame, textvariable=gui.keithley_address_var, font=FONT_MAIN, width=28)
    gui.iv_address_combo.grid(row=0, column=0, sticky="ew")
    gui.iv_address_combo["values"] = builder._scan_visa_resources()
    gui.iv_address_combo.bind("<FocusOut>", lambda e: builder._validate_and_identify_address(gui, "smu"))
    gui.iv_address_combo.bind("<<ComboboxSelected>>", lambda e: builder._validate_and_identify_address(gui, "smu"))

    tk.Button(
        address_frame,
        text="🔄",
        font=("Arial", 10),
        bg=COLOR_BG,
        fg="black",
        relief="flat",
        command=lambda: builder._refresh_address_combo(gui.iv_address_combo),
        padx=5,
    ).grid(row=0, column=1, padx=(5, 0))

    address_frame.columnconfigure(0, weight=1)
    gui.iv_address_entry = gui.iv_address_combo

    gui.smu_status_indicator = tk.Label(smu_frame, text="●", font=("Arial", 16), bg=COLOR_BG, fg="gray")
    gui.smu_status_indicator.grid(row=1, column=2, padx=(5, 5), sticky="w")

    button_frame_smu = tk.Frame(smu_frame, bg=COLOR_BG)
    button_frame_smu.grid(row=1, column=3, pady=5, padx=(0, 0))

    gui.smu_device_info = tk.Label(smu_frame, text="", font=("Segoe UI", 8), bg=COLOR_BG, fg="#666666")
    gui.smu_device_info.grid(row=2, column=1, columnspan=2, sticky="w", padx=(10, 0), pady=(2, 0))

    tk.Button(button_frame_smu, text="Test", font=FONT_BUTTON, bg="#FF9800", fg="white", command=lambda: builder._test_connection(gui, "smu"), padx=10).pack(
        side="left", padx=(0, 5)
    )
    tk.Button(button_frame_smu, text="Connect", font=FONT_BUTTON, bg=COLOR_PRIMARY, fg="white", command=builder.callbacks.get("connect_keithley"), padx=15).pack(
        side="left"
    )

    smu_frame.columnconfigure(1, weight=1)


def _build_psu_section(builder: Any, frame: tk.Frame, gui) -> None:
    """Power supply section."""
    psu_frame = tk.LabelFrame(frame, text="Power Supply", font=FONT_MAIN, bg=COLOR_BG, padx=10, pady=10)
    psu_frame.pack(fill="x", pady=(0, 10))

    tk.Label(psu_frame, text="Type:", font=FONT_MAIN, bg=COLOR_BG).grid(row=0, column=0, sticky="w", pady=5)
    psu_types = ["Keithley 2220", "None"]
    gui.psu_type_var = tk.StringVar(value=getattr(gui, "psu_type", psu_types[0]))
    gui.psu_type_combo = ttk.Combobox(psu_frame, textvariable=gui.psu_type_var, values=psu_types, font=FONT_MAIN, width=25, state="readonly")
    gui.psu_type_combo.grid(row=0, column=1, sticky="ew", pady=5, padx=(10, 10))

    tk.Label(psu_frame, text="Address:", font=FONT_MAIN, bg=COLOR_BG).grid(row=1, column=0, sticky="w", pady=5)
    gui.psu_address_var = tk.StringVar(value=getattr(gui, "psu_visa_address", ""))

    address_frame_psu = tk.Frame(psu_frame, bg=COLOR_BG)
    address_frame_psu.grid(row=1, column=1, sticky="ew", pady=5, padx=(10, 5))

    gui.psu_address_combo = ttk.Combobox(address_frame_psu, textvariable=gui.psu_address_var, font=FONT_MAIN, width=28)
    gui.psu_address_combo.grid(row=0, column=0, sticky="ew")
    gui.psu_address_combo["values"] = builder._scan_visa_resources()
    gui.psu_address_combo.bind("<FocusOut>", lambda e: builder._validate_and_identify_address(gui, "psu"))
    gui.psu_address_combo.bind("<<ComboboxSelected>>", lambda e: builder._validate_and_identify_address(gui, "psu"))

    tk.Button(
        address_frame_psu,
        text="🔄",
        font=("Arial", 10),
        bg=COLOR_BG,
        fg="black",
        relief="flat",
        command=lambda: builder._refresh_address_combo(gui.psu_address_combo),
        padx=5,
    ).grid(row=0, column=1, padx=(5, 0))

    address_frame_psu.columnconfigure(0, weight=1)
    gui.psu_address_entry = gui.psu_address_combo

    gui.psu_status_indicator = tk.Label(psu_frame, text="●", font=("Arial", 16), bg=COLOR_BG, fg="gray")
    gui.psu_status_indicator.grid(row=1, column=2, padx=(5, 5), sticky="w")

    button_frame_psu = tk.Frame(psu_frame, bg=COLOR_BG)
    button_frame_psu.grid(row=1, column=3, pady=5, padx=(0, 0))

    gui.psu_device_info = tk.Label(psu_frame, text="", font=("Segoe UI", 8), bg=COLOR_BG, fg="#666666")
    gui.psu_device_info.grid(row=2, column=1, columnspan=2, sticky="w", padx=(10, 0), pady=(2, 0))

    tk.Button(button_frame_psu, text="Test", font=FONT_BUTTON, bg="#FF9800", fg="white", command=lambda: builder._test_connection(gui, "psu"), padx=10).pack(
        side="left", padx=(0, 5)
    )
    gui.psu_connect_button = tk.Button(
        button_frame_psu, text="Connect", font=FONT_BUTTON, bg=COLOR_PRIMARY, fg="white", command=builder.callbacks.get("connect_psu"), padx=15
    )
    gui.psu_connect_button.pack(side="left")

    psu_frame.columnconfigure(1, weight=1)


def _build_temp_section(builder: Any, frame: tk.Frame, gui) -> None:
    """Temperature controller section."""
    temp_frame = tk.LabelFrame(frame, text="Temperature Controller", font=FONT_MAIN, bg=COLOR_BG, padx=10, pady=10)
    temp_frame.pack(fill="x", pady=(0, 10))

    tk.Label(temp_frame, text="Type:", font=FONT_MAIN, bg=COLOR_BG).grid(row=0, column=0, sticky="w", pady=5)
    temp_types = ["Auto-Detect", "Lakeshore 335", "Oxford ITC4", "None"]
    default_temp_type = getattr(gui, "temp_controller_type", None)
    if not default_temp_type or default_temp_type not in temp_types:
        default_temp_type = "None"
    gui.temp_type_var = tk.StringVar(value=default_temp_type)
    gui.temp_type_combo = ttk.Combobox(temp_frame, textvariable=gui.temp_type_var, values=temp_types, font=FONT_MAIN, width=25, state="readonly")
    gui.temp_type_combo.grid(row=0, column=1, sticky="ew", pady=5, padx=(10, 10))

    tk.Label(temp_frame, text="Address:", font=FONT_MAIN, bg=COLOR_BG).grid(row=1, column=0, sticky="w", pady=5)
    gui.temp_address_var = tk.StringVar(value=getattr(gui, "temp_controller_address", ""))

    address_frame_temp = tk.Frame(temp_frame, bg=COLOR_BG)
    address_frame_temp.grid(row=1, column=1, sticky="ew", pady=5, padx=(10, 5))

    gui.temp_address_combo = ttk.Combobox(address_frame_temp, textvariable=gui.temp_address_var, font=FONT_MAIN, width=28)
    gui.temp_address_combo.grid(row=0, column=0, sticky="ew")
    gui.temp_address_combo["values"] = builder._scan_visa_resources(include_serial=True)
    gui.temp_address_combo.bind("<FocusOut>", lambda e: builder._validate_and_identify_address(gui, "temp"))
    gui.temp_address_combo.bind("<<ComboboxSelected>>", lambda e: builder._validate_and_identify_address(gui, "temp"))

    tk.Button(
        address_frame_temp,
        text="🔄",
        font=("Arial", 10),
        bg=COLOR_BG,
        fg="black",
        relief="flat",
        command=lambda: builder._refresh_address_combo(gui.temp_address_combo, include_serial=True),
        padx=5,
    ).grid(row=0, column=1, padx=(5, 0))

    address_frame_temp.columnconfigure(0, weight=1)
    gui.temp_address_entry = gui.temp_address_combo

    gui.temp_status_indicator = tk.Label(temp_frame, text="●", font=("Arial", 16), bg=COLOR_BG, fg="gray")
    gui.temp_status_indicator.grid(row=1, column=2, padx=(5, 5), sticky="w")

    button_frame_temp = tk.Frame(temp_frame, bg=COLOR_BG)
    button_frame_temp.grid(row=1, column=3, pady=5, padx=(0, 0))

    gui.temp_device_info = tk.Label(temp_frame, text="", font=("Segoe UI", 8), bg=COLOR_BG, fg="#666666")
    gui.temp_device_info.grid(row=2, column=1, columnspan=2, sticky="w", padx=(10, 0), pady=(2, 0))

    gui.temp_test_button = tk.Button(
        button_frame_temp, text="Test", font=FONT_BUTTON, bg="#FF9800", fg="white", command=lambda: builder._test_connection(gui, "temp"), padx=10
    )
    gui.temp_test_button.pack(side="left", padx=(0, 5))

    gui.temp_connect_button = tk.Button(
        button_frame_temp, text="Connect", font=FONT_BUTTON, bg=COLOR_PRIMARY, fg="white", command=builder.callbacks.get("connect_temp"), padx=15
    )
    gui.temp_connect_button.pack(side="left")

    temp_frame.columnconfigure(1, weight=1)
