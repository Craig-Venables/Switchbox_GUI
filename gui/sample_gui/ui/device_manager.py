"""
Device Manager UI Builder
=========================

Creates the Device Manager tab with current device and saved devices list.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from gui.sample_gui.config import sample_config


def create_device_manager_ui(sample_gui: Any) -> None:
    """
    Create the Device Manager tab UI.

    Args:
        sample_gui: The SampleGUI instance. Must have device_manager_tab and methods:
                    set_current_device, save_device_info, clear_current_device,
                    refresh_device_list, load_selected_device, update_device_info_display.
    """
    main_frame = ttk.Frame(sample_gui.device_manager_tab, padding=20)
    main_frame.grid(row=0, column=0, sticky="nsew")
    main_frame.grid_columnconfigure(0, weight=1)
    main_frame.grid_columnconfigure(1, weight=2)
    main_frame.grid_rowconfigure(1, weight=1)

    left_frame = ttk.LabelFrame(main_frame, text="Current Device", padding=15)
    left_frame.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 10))

    ttk.Label(left_frame, text="Device Name:").grid(row=0, column=0, sticky="w", pady=(0, 5))

    name_frame = ttk.Frame(left_frame)
    name_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))

    sample_gui.device_name_entry = ttk.Entry(name_frame, font=("Segoe UI", 12), width=20)
    sample_gui.device_name_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

    ttk.Button(name_frame, text="Set Device", command=sample_gui.set_current_device, width=12).pack(side="left")

    info_frame = ttk.LabelFrame(left_frame, text="Device Information", padding=10)
    info_frame.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
    left_frame.grid_rowconfigure(2, weight=1)

    sample_gui.device_info_text = tk.Text(
        info_frame,
        height=15,
        width=35,
        font=("Consolas", 9),
        wrap=tk.WORD,
        state=tk.DISABLED,
    )
    sample_gui.device_info_text.pack(fill="both", expand=True)

    button_frame = ttk.Frame(left_frame)
    button_frame.grid(row=3, column=0, sticky="ew", pady=(10, 0))

    ttk.Button(button_frame, text="Save Device Info", command=sample_gui.save_device_info, width=15).pack(
        side="left", padx=5
    )
    ttk.Button(button_frame, text="Clear Device", command=sample_gui.clear_current_device, width=15).pack(
        side="left", padx=5
    )

    right_frame = ttk.Frame(main_frame)
    right_frame.grid(row=0, column=1, rowspan=2, sticky="nsew")
    right_frame.grid_rowconfigure(1, weight=1)
    right_frame.grid_columnconfigure(0, weight=1)

    filter_frame = ttk.LabelFrame(right_frame, text="Quick Select Devices", padding=10)
    filter_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))

    ttk.Label(filter_frame, text="Filter by Sample Type:").pack(side="left", padx=5)

    sample_gui.device_filter_var = tk.StringVar(value="All")
    filter_combo = ttk.Combobox(
        filter_frame,
        textvariable=sample_gui.device_filter_var,
        values=["All"] + list(sample_config.keys()),
        width=15,
        state="readonly",
    )
    filter_combo.pack(side="left", padx=5)
    filter_combo.bind("<<ComboboxSelected>>", lambda e: sample_gui.refresh_device_list())

    ttk.Button(filter_frame, text="Refresh", command=sample_gui.refresh_device_list, width=10).pack(side="left", padx=5)

    list_frame = ttk.LabelFrame(right_frame, text="Saved Devices", padding=10)
    list_frame.grid(row=1, column=0, sticky="nsew")
    list_frame.grid_rowconfigure(0, weight=1)
    list_frame.grid_columnconfigure(0, weight=1)

    columns = ("name", "sample_type", "last_modified", "status")
    sample_gui.device_tree = ttk.Treeview(
        list_frame,
        columns=columns,
        show="tree headings",
        selectmode="browse",
    )

    sample_gui.device_tree.heading("#0", text="")
    sample_gui.device_tree.heading("name", text="Device Name")
    sample_gui.device_tree.heading("sample_type", text="Sample Type")
    sample_gui.device_tree.heading("last_modified", text="Last Modified")
    sample_gui.device_tree.heading("status", text="Status")

    sample_gui.device_tree.column("#0", width=0, stretch=False)
    sample_gui.device_tree.column("name", width=150)
    sample_gui.device_tree.column("sample_type", width=120)
    sample_gui.device_tree.column("last_modified", width=150)
    sample_gui.device_tree.column("status", width=100)

    sample_gui.device_tree.grid(row=0, column=0, sticky="nsew")

    tree_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=sample_gui.device_tree.yview)
    tree_scroll.grid(row=0, column=1, sticky="ns")
    sample_gui.device_tree.configure(yscrollcommand=tree_scroll.set)

    sample_gui.device_tree.bind("<Double-Button-1>", lambda e: sample_gui.load_selected_device())

    ttk.Button(
        right_frame,
        text="Load Selected Device",
        command=sample_gui.load_selected_device,
        width=20,
    ).grid(row=2, column=0, pady=(10, 0))

    sample_gui.refresh_device_list()
    sample_gui.update_device_info_display()
