"""
Compact Pulse Testing GUI layout — simplified single-view workflow for 4200 PMU.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from gui.pulse_testing_gui import config
from gui.pulse_testing_gui.ui.connection_compact import build_connection_bar
from gui.pulse_testing_gui.ui.manual_test_sections import build_manual_test_sections
from gui.pulse_testing_gui.ui.laser_section import build_laser_section


def build_compact_ui(gui) -> None:
    """Build simplified pulse testing layout (no extra tabs, connection bar, test-first flow)."""
    gui.title("Pulse Testing (Compact)")
    gui._compact_laser_visible = False

    main_frame = tk.Frame(gui)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    paned = tk.PanedWindow(
        main_frame,
        orient=tk.HORIZONTAL,
        sashwidth=5,
        sashrelief=tk.RAISED,
        bg="#d0d0d0",
    )
    paned.pack(fill=tk.BOTH, expand=True)

    try:
        win_w, _ = config.WINDOW_GEOMETRY.lower().split("x")
        total_w = int(win_w)
    except (ValueError, AttributeError):
        total_w = 1400
    left_width = max(350, int(total_w * 0.38))
    left_container = tk.Frame(paned, width=left_width)
    left_container.pack_propagate(False)
    left_panel = tk.Frame(left_container)
    left_panel.pack(fill=tk.BOTH, expand=True)

    right_panel = tk.Frame(paned)
    paned.add(left_container, minsize=350, width=left_width)
    paned.add(right_panel, minsize=400)

    top_bar = tk.Frame(left_panel, bg="#e8f5e9", pady=4, padx=8)
    top_bar.pack(fill=tk.X, pady=(0, 4))
    top_bar.columnconfigure(0, weight=1)
    tk.Label(
        top_bar,
        text="Pulse Testing",
        font=("Segoe UI", 11, "bold"),
        bg="#e8f5e9",
        fg="#2e7d32",
    ).grid(row=0, column=0, sticky="w")
    tk.Label(
        top_bar,
        text="Compact",
        font=("Segoe UI", 8),
        bg="#e8f5e9",
        fg="#558b2f",
    ).grid(row=0, column=1, sticky="w", padx=(6, 0))
    tk.Button(
        top_bar,
        text="Help",
        command=gui._show_help,
        bg="#2e7d32",
        fg="white",
        font=("Segoe UI", 8, "bold"),
        padx=8,
        pady=1,
    ).grid(row=0, column=2, sticky="e")

    build_connection_bar(left_panel, gui)
    if not gui.system_wrapper.is_connected():
        gui.current_system_name = gui.system_var.get()

    manual_frame = tk.LabelFrame(left_panel, text="Manual Test", padx=3, pady=3)
    manual_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=3)

    build_manual_test_sections(
        manual_frame,
        gui,
        compact=True,
        show_smu_range=False,
        log_height=3,
        start_log_collapsed=True,
    )

    build_laser_section(left_panel, gui, start_hidden=True, show_smu_range=False)

    gui.create_pulse_diagram_section(right_panel)
    gui.create_plot_section(right_panel)
    gui.create_bottom_control_bar(right_panel)

    gui._update_test_list_capabilities()
    if hasattr(gui, "test_var") and gui.test_var.get():
        gui.on_test_selected(None)
