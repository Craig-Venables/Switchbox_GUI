"""
Sample Analysis Tab Builder
===========================

Builds the "Sample Analysis" tab for comprehensive analysis plots and reports.
Extracted from layout_builder for maintainability.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from .constants import COLOR_BG


def build_graphing_tab(builder: Any, notebook: ttk.Notebook) -> None:
    """
    Create Graphing tab for sample analysis and plotting.

    Args:
        builder: The layout builder instance (provides gui, widgets, _create_scrollable_panel).
        notebook: The ttk.Notebook to add the tab to.
    """
    gui = builder.gui

    tab = tk.Frame(notebook, bg=COLOR_BG)
    notebook.add(tab, text="  Sample Analysis  ")

    tab.columnconfigure(0, weight=1)
    tab.rowconfigure(0, weight=1)

    main_panel = builder._create_scrollable_panel(tab)
    main_panel._container.grid(row=0, column=0, sticky="nsew", padx=20, pady=10)

    # Title Section
    title_frame = tk.Frame(main_panel, bg=COLOR_BG)
    title_frame.pack(fill='x', pady=(0, 20))
    tk.Label(title_frame, text="Sample Analysis and Plotting", font=("Segoe UI", 16, "bold"), bg=COLOR_BG).pack()
    tk.Label(
        title_frame,
        text="Generate comprehensive analysis plots and reports for the entire sample",
        font=("Segoe UI", 10),
        bg=COLOR_BG,
        fg="#666666"
    ).pack(pady=(5, 0))

    # 1. Data Selection Section
    selection_frame = tk.LabelFrame(
        main_panel,
        text="1. Data Selection",
        font=("Segoe UI", 11, "bold"),
        bg=COLOR_BG,
        padx=15,
        pady=15
    )
    selection_frame.pack(fill='x', pady=(0, 20))
    selection_frame.columnconfigure(1, weight=1)

    tk.Label(selection_frame, text="Sample Folder:", font=("Segoe UI", 10), bg=COLOR_BG).grid(
        row=0, column=0, padx=(0, 10), pady=10, sticky="w"
    )
    gui.analysis_folder_var = tk.StringVar()
    gui.analysis_folder_var.set("(Use current sample)")
    tk.Entry(
        selection_frame,
        textvariable=gui.analysis_folder_var,
        font=("Segoe UI", 9),
        state="readonly"
    ).grid(row=0, column=1, padx=(0, 10), pady=10, sticky="ew")

    folder_btn_frame = tk.Frame(selection_frame, bg=COLOR_BG)
    folder_btn_frame.grid(row=0, column=2, pady=10, sticky="e")
    tk.Button(
        folder_btn_frame,
        text="Browse...",
        command=lambda: gui.browse_sample_folder_for_analysis(),
        font=("Segoe UI", 9),
        bg="#2196F3",
        fg="white",
        padx=15,
        pady=5,
        cursor="hand2"
    ).pack(side="left", padx=(0, 5))
    tk.Button(
        folder_btn_frame,
        text="Reset",
        command=lambda: gui.clear_sample_folder_selection(),
        font=("Segoe UI", 9),
        bg="#757575",
        fg="white",
        padx=10,
        pady=5,
        cursor="hand2"
    ).pack(side="left")

    # Row 2: Code Name Filter
    tk.Label(selection_frame, text="Code Name (Optional):", font=("Segoe UI", 10), bg=COLOR_BG).grid(
        row=1, column=0, padx=(0, 10), pady=10, sticky="w"
    )
    filter_layout_frame = tk.Frame(selection_frame, bg=COLOR_BG)
    filter_layout_frame.grid(row=1, column=1, columnspan=2, sticky="w", pady=10)
    gui.analysis_code_name_var = tk.StringVar(value="")
    ttk.Combobox(
        filter_layout_frame,
        textvariable=gui.analysis_code_name_var,
        values=[""] + list(gui.code_names.values()) if hasattr(gui, 'code_names') else [""],
        state="readonly",
        width=25,
        font=("Segoe UI", 9)
    ).pack(side="left")
    tk.Label(
        filter_layout_frame,
        text="(Leave empty to analyze all measurements)",
        font=("Segoe UI", 9, "italic"),
        bg=COLOR_BG,
        fg="#666666"
    ).pack(side="left", padx=(10, 0))

    # 2. Actions Section
    actions_frame = tk.LabelFrame(
        main_panel,
        text="2. Actions",
        font=("Segoe UI", 11, "bold"),
        bg=COLOR_BG,
        padx=15,
        pady=15
    )
    actions_frame.pack(fill='x', pady=(0, 20))

    tk.Button(
        actions_frame,
        text="▶ Run Full Sample Analysis",
        command=gui.run_full_sample_analysis,
        font=("Segoe UI", 12, "bold"),
        bg="#4CAF50",
        fg="white",
        padx=30,
        pady=12,
        cursor="hand2",
        relief=tk.RAISED,
        bd=1
    ).pack(fill='x', pady=(0, 20))

    tk.Button(
        actions_frame,
        text="🔄 Reclassify All Devices",
        command=gui.reclassify_all_devices,
        font=("Segoe UI", 11, "bold"),
        bg="#2196F3",
        fg="white",
        padx=30,
        pady=10,
        cursor="hand2",
        relief=tk.RAISED,
        bd=1
    ).pack(fill='x', pady=(0, 20))

    tk.Label(
        actions_frame,
        text="* Reclassify updates all device classifications using current weights from classification_weights.json",
        font=("Segoe UI", 9),
        bg=COLOR_BG,
        fg="#666666"
    ).pack(pady=(0, 20))

    plot_btns_frame = tk.Frame(actions_frame, bg=COLOR_BG)
    plot_btns_frame.pack(fill='x')
    plot_btns_frame.columnconfigure(0, weight=1)
    plot_btns_frame.columnconfigure(1, weight=1)

    tk.Button(
        plot_btns_frame,
        text="Plot Current Device Graphs",
        command=gui.plot_all_device_graphs,
        font=("Segoe UI", 10),
        bg="#FF9800",
        fg="white",
        padx=20,
        pady=8,
        cursor="hand2"
    ).grid(row=0, column=0, sticky="ew", padx=(0, 10))

    tk.Button(
        plot_btns_frame,
        text="Plot All Sample Graphs",
        command=gui.plot_all_sample_graphs,
        font=("Segoe UI", 10),
        bg="#9C27B0",
        fg="white",
        padx=20,
        pady=8,
        cursor="hand2"
    ).grid(row=0, column=1, sticky="ew", padx=(10, 0))

    tk.Label(
        actions_frame,
        text="* Plotting buttons generate dashboard, conduction, and SCLC graphs for immediate visualization",
        font=("Segoe UI", 9),
        bg=COLOR_BG,
        fg="#666666"
    ).pack(pady=(15, 0))

    # Status Section
    status_frame = tk.Frame(main_panel, bg=COLOR_BG)
    status_frame.pack(fill='x', pady=(0, 20))
    tk.Label(status_frame, text="Status:", font=("Segoe UI", 10, "bold"), bg=COLOR_BG).pack(anchor="w")
    gui.analysis_status_label = tk.Label(
        status_frame,
        text="Ready",
        font=("Segoe UI", 10),
        bg="#F5F5F5",
        fg="#333333",
        relief=tk.SUNKEN,
        bd=1,
        padx=10,
        pady=8,
        anchor="w"
    )
    gui.analysis_status_label.pack(fill='x', pady=(5, 0))

    # Information Section
    info_frame = tk.LabelFrame(
        main_panel,
        text="Information",
        font=("Segoe UI", 10, "bold"),
        bg=COLOR_BG,
        padx=15,
        pady=10
    )
    info_frame.pack(fill='x', pady=10)
    info_text = """
This module performs:
• Retroactive analysis of raw measurement files
• Loading of device tracking data
• Generation of 12 advanced plot types per device
• Export of Origin-ready data files (CSV)
• Creation of comprehensive sample report

Output location: {sample_dir}/sample_analysis/
  - plots/ : All PNG figures
  - origin_data/ : CSV files for Origin import
    """
    tk.Label(
        info_frame,
        text=info_text.strip(),
        font=("Consolas", 9),
        bg=COLOR_BG,
        justify=tk.LEFT,
        anchor="w"
    ).pack(fill='x')

    builder.widgets["graphing_tab"] = tab
    gui.graphing_tab = tab
