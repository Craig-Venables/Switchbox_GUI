"""
Sweep Combinations Editor Tab Builder
======================================

Builds the "Sweep Combinations Editor" tab for managing test_configurations.json.
Extracted from layout_builder for maintainability.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from .constants import COLOR_BG


def build_custom_sweeps_graphing_tab(builder: Any, notebook: ttk.Notebook) -> None:
    """
    Create Sweep Combinations Editor tab for managing test_configurations.json.

    Args:
        builder: The layout builder instance (provides gui, callbacks, widgets).
        notebook: The ttk.Notebook to add the tab to.
    """
    gui = builder.gui

    tab = tk.Frame(notebook, bg=COLOR_BG)
    notebook.add(tab, text="  Sweep Combinations Editor  ")

    tab.columnconfigure(0, weight=1)
    tab.rowconfigure(0, weight=1)

    main_panel = builder._create_scrollable_panel(tab)
    main_panel._container.grid(row=0, column=0, sticky="nsew", padx=20, pady=10)

    # Title
    title_frame = tk.Frame(main_panel, bg=COLOR_BG)
    title_frame.pack(fill='x', pady=(0, 15))

    tk.Label(title_frame, text="Sweep Combinations Editor", font=("Segoe UI", 14, "bold"), bg=COLOR_BG).pack()
    tk.Label(
        title_frame,
        text="Manage sweep combinations in test_configurations.json",
        font=("Segoe UI", 9),
        bg=COLOR_BG,
        fg="#666666"
    ).pack(pady=(5, 0))

    # Section 1: Select Custom Sweep Method
    method_frame = tk.LabelFrame(
        main_panel,
        text="1. Select Custom Sweep Method",
        font=("Segoe UI", 10, "bold"),
        bg=COLOR_BG,
        padx=10,
        pady=10
    )
    method_frame.pack(fill='x', pady=10)

    tk.Label(method_frame, text="Method (by code name or identifier):", font=("Segoe UI", 9), bg=COLOR_BG).pack(
        anchor='w', pady=(0, 5)
    )

    gui.custom_sweep_method_var = tk.StringVar()
    gui.custom_sweep_method_combo = ttk.Combobox(
        method_frame,
        textvariable=gui.custom_sweep_method_var,
        font=("Segoe UI", 9),
        state="readonly",
        width=30
    )
    gui.custom_sweep_method_combo.pack(fill='x', pady=(0, 10))
    gui.custom_sweep_method_combo.bind("<<ComboboxSelected>>", lambda e: gui.on_custom_sweep_method_selected())

    tk.Button(
        method_frame,
        text="Load Methods",
        command=gui.load_custom_sweep_methods,
        font=("Segoe UI", 9),
        bg="#2196F3",
        fg="white",
        padx=10,
        pady=5,
        cursor="hand2"
    ).pack(pady=5)

    # Section 2: Select Sweep Combinations
    combo_frame = tk.LabelFrame(
        main_panel,
        text="2. Select Sweep Combinations",
        font=("Segoe UI", 10, "bold"),
        bg=COLOR_BG,
        padx=10,
        pady=10
    )
    combo_frame.pack(fill='x', pady=10)

    tk.Label(combo_frame, text="Available combinations:", font=("Segoe UI", 9), bg=COLOR_BG).pack(
        anchor='w', pady=(0, 5)
    )

    listbox_frame = tk.Frame(combo_frame, bg=COLOR_BG)
    listbox_frame.pack(fill='both', expand=True, pady=(0, 10))

    gui.custom_sweep_combinations_listbox = tk.Listbox(
        listbox_frame,
        font=("Segoe UI", 9),
        selectmode=tk.MULTIPLE,
        height=8
    )
    scrollbar_combos = tk.Scrollbar(
        listbox_frame, orient="vertical", command=gui.custom_sweep_combinations_listbox.yview
    )
    gui.custom_sweep_combinations_listbox.config(yscrollcommand=scrollbar_combos.set)
    gui.custom_sweep_combinations_listbox.pack(side="left", fill="both", expand=True)
    scrollbar_combos.pack(side="right", fill="y")

    tk.Button(
        combo_frame,
        text="Load Combinations",
        command=gui.load_custom_sweep_combinations,
        font=("Segoe UI", 9),
        bg="#2196F3",
        fg="white",
        padx=10,
        pady=5,
        cursor="hand2"
    ).pack(pady=5)

    # Section 2.5: Manage Sweep Combinations
    manage_frame = tk.LabelFrame(
        main_panel,
        text="2.5. Manage Sweep Combinations",
        font=("Segoe UI", 10, "bold"),
        bg=COLOR_BG,
        padx=10,
        pady=10
    )
    manage_frame.pack(fill='x', pady=10)

    tk.Label(manage_frame, text="Add New Combination:", font=("Segoe UI", 9, "bold"), bg=COLOR_BG).pack(
        anchor='w', pady=(0, 5)
    )

    sweep_input_frame = tk.Frame(manage_frame, bg=COLOR_BG)
    sweep_input_frame.pack(fill='x', pady=(0, 5))
    tk.Label(sweep_input_frame, text="Sweep Numbers:", font=("Segoe UI", 9), bg=COLOR_BG).pack(side='left', padx=(0, 5))
    gui.new_combination_sweeps_var = tk.StringVar()
    tk.Entry(
        sweep_input_frame,
        textvariable=gui.new_combination_sweeps_var,
        font=("Segoe UI", 9),
        width=20
    ).pack(side='left', padx=(0, 5))
    tk.Label(
        sweep_input_frame,
        text="(e.g., 1,2 or 1,2,3)",
        font=("Segoe UI", 8),
        bg=COLOR_BG,
        fg="#666666"
    ).pack(side='left')

    title_input_frame = tk.Frame(manage_frame, bg=COLOR_BG)
    title_input_frame.pack(fill='x', pady=(0, 5))
    tk.Label(title_input_frame, text="Title:", font=("Segoe UI", 9), bg=COLOR_BG).pack(side='left', padx=(0, 5))
    gui.new_combination_title_var = tk.StringVar()
    tk.Entry(
        title_input_frame,
        textvariable=gui.new_combination_title_var,
        font=("Segoe UI", 9),
        width=30
    ).pack(side='left', fill='x', expand=True)

    manage_btn_frame = tk.Frame(manage_frame, bg=COLOR_BG)
    manage_btn_frame.pack(fill='x', pady=5)

    tk.Button(
        manage_btn_frame,
        text="Add Combination",
        command=gui.add_sweep_combination,
        font=("Segoe UI", 9),
        bg="#4CAF50",
        fg="white",
        padx=10,
        pady=5,
        cursor="hand2"
    ).pack(side='left', padx=(0, 5))
    tk.Button(
        manage_btn_frame,
        text="Edit Selected",
        command=gui.edit_sweep_combination,
        font=("Segoe UI", 9),
        bg="#FF9800",
        fg="white",
        padx=10,
        pady=5,
        cursor="hand2"
    ).pack(side='left', padx=(0, 5))
    tk.Button(
        manage_btn_frame,
        text="Delete Selected",
        command=gui.delete_sweep_combination,
        font=("Segoe UI", 9),
        bg="#F44336",
        fg="white",
        padx=10,
        pady=5,
        cursor="hand2"
    ).pack(side='left')

    tk.Button(
        manage_frame,
        text="Save to JSON",
        command=gui.save_sweep_combinations_to_json,
        font=("Segoe UI", 9, "bold"),
        bg="#2196F3",
        fg="white",
        padx=15,
        pady=5,
        cursor="hand2"
    ).pack(pady=(10, 0))

    gui.custom_sweep_status_label = tk.Label(
        main_panel,
        text="",
        font=("Segoe UI", 9),
        bg=COLOR_BG,
        fg="#666666",
        wraplength=600
    )
    gui.custom_sweep_status_label.pack(pady=20)

    builder.widgets["custom_sweeps_graphing_tab"] = tab
