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

    # Three columns: left = main analysis, middle = batch plotting, right = Impedance Analyzer
    content_row = tk.Frame(main_panel, bg=COLOR_BG)
    content_row.pack(fill='both', expand=True)

    left_col = tk.Frame(content_row, bg=COLOR_BG)
    left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # Title Section
    title_frame = tk.Frame(left_col, bg=COLOR_BG)
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
        left_col,
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
        left_col,
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
    status_frame = tk.Frame(left_col, bg=COLOR_BG)
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
        left_col,
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

    # ---------------------------------------------------------------
    # Yield & Concentration Analysis Section
    # ---------------------------------------------------------------
    yield_frame = tk.LabelFrame(
        left_col,
        text="Yield & Concentration Analysis",
        font=("Segoe UI", 11, "bold"),
        bg=COLOR_BG,
        padx=15,
        pady=15,
    )
    yield_frame.pack(fill="x", pady=(0, 20))
    yield_frame.columnconfigure(1, weight=1)

    # --- Row 0: Data folder ---
    tk.Label(
        yield_frame, text="Data Folder:", font=("Segoe UI", 10), bg=COLOR_BG
    ).grid(row=0, column=0, padx=(0, 10), pady=6, sticky="w")

    gui.yield_root_folder_var = tk.StringVar(value="(Use current sample)")
    tk.Entry(
        yield_frame,
        textvariable=gui.yield_root_folder_var,
        font=("Segoe UI", 9),
        state="readonly",
        width=38,
    ).grid(row=0, column=1, padx=(0, 6), pady=6, sticky="ew")

    def _browse_yield_root() -> None:
        from tkinter import filedialog
        path = filedialog.askdirectory(title="Select root data folder or a single sample folder")
        if path:
            gui.yield_root_folder_var.set(path)
            _scan_yield_samples()

    def _clear_yield_root() -> None:
        gui.yield_root_folder_var.set("(Use current sample)")
        gui.yield_mode_label.config(text="Mode: auto-detect on run")
        _clear_sample_list()

    tk.Button(
        yield_frame, text="Browse…", command=_browse_yield_root,
        font=("Segoe UI", 9), bg="#2196F3", fg="white", padx=10, pady=4, cursor="hand2",
    ).grid(row=0, column=2, pady=6)
    tk.Button(
        yield_frame, text="Clear", command=_clear_yield_root,
        font=("Segoe UI", 9), bg="#757575", fg="white", padx=8, pady=4, cursor="hand2",
    ).grid(row=0, column=3, padx=(4, 0), pady=6)

    # --- Row 1: Mode indicator ---
    gui.yield_mode_label = tk.Label(
        yield_frame,
        text="Mode: auto-detect on run",
        font=("Segoe UI", 9, "italic"),
        bg=COLOR_BG,
        fg="#2196F3",
        anchor="w",
    )
    gui.yield_mode_label.grid(row=1, column=0, columnspan=4, sticky="w", pady=(2, 4))

    # --- Row 2: Sample checklist (shown in multi-sample mode) ---
    yield_list_outer = tk.Frame(yield_frame, bg=COLOR_BG)
    yield_list_outer.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(0, 6))
    yield_list_outer.columnconfigure(0, weight=1)

    # header + select-all/none buttons
    yield_list_hdr = tk.Frame(yield_list_outer, bg=COLOR_BG)
    yield_list_hdr.grid(row=0, column=0, sticky="ew")
    tk.Label(yield_list_hdr, text="Samples to include:", font=("Segoe UI", 9, "bold"),
             bg=COLOR_BG).pack(side=tk.LEFT)
    tk.Button(yield_list_hdr, text="All", font=("Segoe UI", 8), bg=COLOR_BG, padx=6, pady=2,
              command=lambda: _set_all_yield_samples(True)).pack(side=tk.RIGHT, padx=(4, 0))
    tk.Button(yield_list_hdr, text="None", font=("Segoe UI", 8), bg=COLOR_BG, padx=6, pady=2,
              command=lambda: _set_all_yield_samples(False)).pack(side=tk.RIGHT)

    # scrollable checkbox list
    list_container = tk.Frame(yield_list_outer, bg="white", relief=tk.SUNKEN, bd=1, height=130)
    list_container.grid(row=1, column=0, sticky="ew", pady=(2, 0))
    list_container.pack_propagate(False)

    list_canvas = tk.Canvas(list_container, bg="white", highlightthickness=0)
    list_scroll = tk.Scrollbar(list_container, orient=tk.VERTICAL, command=list_canvas.yview)
    list_canvas.configure(yscrollcommand=list_scroll.set)
    list_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    list_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    gui.yield_sample_checkbox_frame = tk.Frame(list_canvas, bg="white")
    list_canvas.create_window((0, 0), window=gui.yield_sample_checkbox_frame, anchor="nw")

    def _on_frame_resize(event):
        list_canvas.configure(scrollregion=list_canvas.bbox("all"))
    gui.yield_sample_checkbox_frame.bind("<Configure>", _on_frame_resize)

    gui.yield_sample_vars = []  # list of (sample_name, BooleanVar)

    # Show a hint when empty
    gui._yield_empty_label = tk.Label(
        gui.yield_sample_checkbox_frame,
        text="Browse to a folder above to discover samples, or leave\n"
             "blank to use the current sample automatically.",
        font=("Segoe UI", 9, "italic"), bg="white", fg="#888888", justify=tk.LEFT,
    )
    gui._yield_empty_label.pack(pady=10, padx=10)

    def _clear_sample_list() -> None:
        for w in gui.yield_sample_checkbox_frame.winfo_children():
            w.destroy()
        gui.yield_sample_vars.clear()
        gui._yield_empty_label = tk.Label(
            gui.yield_sample_checkbox_frame,
            text="Browse to a folder above to discover samples, or leave\n"
                 "blank to use the current sample automatically.",
            font=("Segoe UI", 9, "italic"), bg="white", fg="#888888", justify=tk.LEFT,
        )
        gui._yield_empty_label.pack(pady=10, padx=10)

    def _scan_yield_samples() -> None:
        """Populate the checkbox list after a folder is browsed."""
        from gui.measurement_gui.yield_concentration.aggregator import detect_mode
        folder = gui.yield_root_folder_var.get()
        if not folder or folder == "(Use current sample)":
            return
        mode, sample_dirs = detect_mode(folder)
        for w in gui.yield_sample_checkbox_frame.winfo_children():
            w.destroy()
        gui.yield_sample_vars.clear()
        if mode == "single":
            gui.yield_mode_label.config(
                text=f"Mode: single sample — {folder.split('/')[-1]}", fg="#FF9800"
            )
            return
        gui.yield_mode_label.config(
            text=f"Mode: multi-sample — {len(sample_dirs)} sample(s) found", fg="#4CAF50"
        )
        for sd in sample_dirs:
            name = sd.replace("\\", "/").split("/")[-1]
            var = tk.BooleanVar(value=True)
            gui.yield_sample_vars.append((name, var))
            tk.Checkbutton(
                gui.yield_sample_checkbox_frame, text=name, variable=var,
                font=("Segoe UI", 9), bg="white", anchor="w",
            ).pack(fill="x", padx=6, pady=1)

    def _set_all_yield_samples(state: bool) -> None:
        for _, var in gui.yield_sample_vars:
            var.set(state)

    # --- Row 3: Solutions and devices Excel ---
    tk.Label(
        yield_frame, text="Solutions & Devices Excel:", font=("Segoe UI", 10), bg=COLOR_BG
    ).grid(row=3, column=0, padx=(0, 10), pady=(8, 4), sticky="w")

    gui.yield_excel_path_var = tk.StringVar(value="")
    tk.Entry(
        yield_frame,
        textvariable=gui.yield_excel_path_var,
        font=("Segoe UI", 9),
        state="readonly",
        width=38,
    ).grid(row=3, column=1, padx=(0, 6), pady=(8, 4), sticky="ew")

    def _browse_yield_excel() -> None:
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Select solutions and devices Excel",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")],
        )
        if path:
            gui.yield_excel_path_var.set(path)

    tk.Button(
        yield_frame, text="Browse…", command=_browse_yield_excel,
        font=("Segoe UI", 9), bg="#2196F3", fg="white", padx=10, pady=4, cursor="hand2",
    ).grid(row=3, column=2, pady=(8, 4))
    tk.Button(
        yield_frame, text="Clear", command=lambda: gui.yield_excel_path_var.set(""),
        font=("Segoe UI", 9), bg="#757575", fg="white", padx=8, pady=4, cursor="hand2",
    ).grid(row=3, column=3, padx=(4, 0), pady=(8, 4))

    tk.Label(
        yield_frame,
        text="Optional — provides Np Concentration, Qd Spacing, Polymer for cross-sample plots.",
        font=("Segoe UI", 9, "italic"), bg=COLOR_BG, fg="#666666", wraplength=520, justify=tk.LEFT,
    ).grid(row=4, column=0, columnspan=4, sticky="w", pady=(0, 8))

    # --- Row 5: Run button ---
    tk.Button(
        yield_frame,
        text="Run Yield & Concentration Analysis",
        command=gui.run_yield_concentration_analysis,
        font=("Segoe UI", 11, "bold"),
        bg="#4CAF50", fg="white", padx=20, pady=10,
        cursor="hand2", relief=tk.RAISED, bd=1,
    ).grid(row=5, column=0, columnspan=4, sticky="ew", pady=(4, 8))

    # --- Row 6: Priority note ---
    tk.Label(
        yield_frame,
        text=(
            "Yield source priority:  (1) {sample_name}.xlsx manual classification   "
            "(2) Cached manifest   (3) Auto from device_tracking"
        ),
        font=("Consolas", 8), bg=COLOR_BG, fg="#555555", justify=tk.LEFT, anchor="w",
    ).grid(row=6, column=0, columnspan=4, sticky="w", pady=(0, 4))

    # Middle column: Batch sample plotting
    middle_col = tk.Frame(content_row, bg=COLOR_BG, width=400)
    middle_col.pack(side=tk.LEFT, fill=tk.BOTH, padx=(20, 0))
    middle_col.pack_propagate(False)

    batch_frame = tk.LabelFrame(
        middle_col,
        text="3. Batch sample plotting",
        font=("Segoe UI", 11, "bold"),
        bg=COLOR_BG,
        padx=15,
        pady=15,
    )
    batch_frame.pack(fill="x", pady=(0, 10))
    batch_frame.columnconfigure(0, weight=1)

    tk.Label(
        batch_frame,
        text="Run \"Plot All Sample Graphs\" for multiple samples from the data save folder. Select one or more, or use Select all.",
        font=("Segoe UI", 9),
        bg=COLOR_BG,
        fg="#666666",
        wraplength=360,
        justify=tk.LEFT,
    ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

    list_outer = tk.Frame(batch_frame, bg=COLOR_BG)
    list_outer.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(0, 10))
    list_outer.columnconfigure(0, weight=1)
    list_outer.rowconfigure(0, weight=1)

    batch_canvas = tk.Canvas(list_outer, bg=COLOR_BG, highlightthickness=0)
    batch_scrollbar = ttk.Scrollbar(list_outer, orient="vertical", command=batch_canvas.yview)
    gui.batch_sample_checkbox_frame = tk.Frame(batch_canvas, bg=COLOR_BG)
    batch_canvas_window = batch_canvas.create_window((0, 0), window=gui.batch_sample_checkbox_frame, anchor="nw")

    def _on_frame_configure(e=None):
        batch_canvas.configure(scrollregion=batch_canvas.bbox("all"))

    def _on_canvas_configure(e):
        batch_canvas.itemconfig(batch_canvas_window, width=e.width)

    gui.batch_sample_checkbox_frame.bind("<Configure>", _on_frame_configure)
    batch_canvas.bind("<Configure>", _on_canvas_configure)
    batch_canvas.configure(yscrollcommand=batch_scrollbar.set)

    batch_canvas.grid(row=0, column=0, sticky="nsew")
    batch_scrollbar.grid(row=0, column=1, sticky="ns")
    batch_canvas.config(height=200)
    try:
        def _on_mousewheel(event, canvas=batch_canvas):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        batch_canvas.bind("<Enter>", lambda e: batch_canvas.bind_all("<MouseWheel>", _on_mousewheel))
        batch_canvas.bind("<Leave>", lambda e: batch_canvas.unbind_all("<MouseWheel>"))
    except Exception:
        pass

    btn_row = tk.Frame(batch_frame, bg=COLOR_BG)
    btn_row.grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 5))
    tk.Button(
        btn_row,
        text="Refresh",
        command=gui.refresh_batch_sample_list,
        font=("Segoe UI", 9),
        bg="#757575",
        fg="white",
        padx=12,
        pady=5,
        cursor="hand2",
    ).pack(side="left", padx=(0, 8))
    tk.Button(
        btn_row,
        text="Select all",
        command=gui.select_all_batch_samples,
        font=("Segoe UI", 9),
        bg="#2196F3",
        fg="white",
        padx=12,
        pady=5,
        cursor="hand2",
    ).pack(side="left", padx=(0, 8))
    tk.Button(
        btn_row,
        text="Deselect all",
        command=gui.deselect_all_batch_samples,
        font=("Segoe UI", 9),
        bg="#2196F3",
        fg="white",
        padx=12,
        pady=5,
        cursor="hand2",
    ).pack(side="left", padx=(0, 8))
    tk.Button(
        btn_row,
        text="Plot All Sample Graphs (selected)",
        command=gui.plot_selected_batch_samples,
        font=("Segoe UI", 10),
        bg="#9C27B0",
        fg="white",
        padx=20,
        pady=6,
        cursor="hand2",
    ).pack(side="left")

    gui.batch_sample_vars = []
    gui.refresh_batch_sample_list()

    # Right column: Impedance Analyzer
    right_col = tk.Frame(content_row, bg=COLOR_BG, width=320)
    right_col.pack(side=tk.RIGHT, fill=tk.Y, padx=(20, 0))
    right_col.pack_propagate(False)

    impedance_frame = tk.LabelFrame(
        right_col,
        text="Impedance Analyzer",
        font=("Segoe UI", 11, "bold"),
        bg=COLOR_BG,
        padx=12,
        pady=12,
    )
    impedance_frame.pack(fill='x', pady=(0, 10))

    imp_text = (
        "Plot SMaRT impedance CSV or .dat files: |Z| vs f, Nyquist, phase, capacitance. "
        "Data above 1 MHz is filtered. Outputs go to graphs/ and origin_data/ in the selected folder."
    )
    tk.Label(
        impedance_frame,
        text=imp_text,
        font=("Segoe UI", 9),
        bg=COLOR_BG,
        fg="#444",
        wraplength=280,
        justify=tk.LEFT,
    ).pack(fill='x', pady=(0, 12))

    tk.Label(impedance_frame, text="Folder:", font=("Segoe UI", 9), bg=COLOR_BG).pack(anchor="w")
    gui.impedance_folder_var = tk.StringVar(value="")
    tk.Entry(
        impedance_frame,
        textvariable=gui.impedance_folder_var,
        font=("Segoe UI", 9),
        state="readonly",
    ).pack(fill='x', pady=(2, 8))

    imp_btn_frame = tk.Frame(impedance_frame, bg=COLOR_BG)
    imp_btn_frame.pack(fill='x')
    tk.Button(
        imp_btn_frame,
        text="Browse...",
        command=lambda: gui.browse_impedance_folder(),
        font=("Segoe UI", 9),
        bg="#2196F3",
        fg="white",
        padx=12,
        pady=4,
        cursor="hand2",
    ).pack(side="left", padx=(0, 6))
    tk.Button(
        imp_btn_frame,
        text="Run CSV visualisation",
        command=lambda: gui.run_impedance_visualisation(),
        font=("Segoe UI", 9),
        bg="#4CAF50",
        fg="white",
        padx=12,
        pady=4,
        cursor="hand2",
    ).pack(side="left", padx=(0, 6))
    tk.Button(
        imp_btn_frame,
        text="Compare Combinations",
        command=lambda: gui.run_impedance_combinations(),
        font=("Segoe UI", 9),
        bg="#FF9800",
        fg="white",
        padx=12,
        pady=4,
        cursor="hand2",
    ).pack(side="left")

    builder.widgets["graphing_tab"] = tab
    gui.graphing_tab = tab
