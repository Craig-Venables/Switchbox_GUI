"""
Classic Pulse Testing GUI layout (original tabbed interface).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from gui.pulse_testing_gui import config
from gui.pulse_testing_gui.ui.tabs_optical import build_optical_tab


def build_classic_ui(gui) -> None:
    """Build the original multi-tab pulse testing layout."""
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
    left_width = max(350, int(total_w * 0.40))
    left_container = tk.Frame(paned, width=left_width)
    left_container.pack_propagate(False)

    left_canvas = tk.Canvas(left_container, highlightthickness=0)
    left_scrollbar = ttk.Scrollbar(left_container, orient="vertical", command=left_canvas.yview)
    left_panel = tk.Frame(left_canvas)

    left_canvas_window = left_canvas.create_window((0, 0), window=left_panel, anchor="nw")
    left_canvas.configure(yscrollcommand=left_scrollbar.set)

    def update_scroll_region(event=None):
        left_canvas.configure(scrollregion=left_canvas.bbox("all"))
        canvas_width = left_canvas.winfo_width()
        if canvas_width > 1:
            left_canvas.itemconfig(left_canvas_window, width=canvas_width)

    left_panel.bind("<Configure>", update_scroll_region)
    left_canvas.bind(
        "<Configure>",
        lambda e: left_canvas.itemconfig(left_canvas_window, width=e.width),
    )

    left_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    left_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def _on_mousewheel(event):
        left_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    left_canvas.bind("<MouseWheel>", _on_mousewheel)
    left_panel.bind(
        "<MouseWheel>",
        lambda e: left_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"),
    )

    right_panel = tk.Frame(paned)
    paned.add(left_container, minsize=350, width=left_width)
    paned.add(right_panel, minsize=400)

    top_bar = tk.Frame(left_panel, bg="#e6f3ff", pady=5, padx=10)
    top_bar.pack(fill=tk.X, pady=(0, 5))
    top_bar.columnconfigure(0, weight=1)

    tk.Label(
        top_bar,
        text="TSP Pulse Testing",
        font=("Segoe UI", 11, "bold"),
        bg="#e6f3ff",
        fg="#1565c0",
    ).grid(row=0, column=0, sticky="w")

    tk.Button(
        top_bar,
        text="Help / Guide",
        command=gui._show_help,
        bg="#1565c0",
        fg="white",
        font=("Segoe UI", 9, "bold"),
        padx=10,
        pady=2,
    ).grid(row=0, column=1, sticky="e", padx=(10, 0))

    gui.create_connection_section(left_panel)
    if not gui.system_wrapper.is_connected():
        gui.current_system_name = gui.system_var.get()

    gui.create_laser_section(left_panel)

    gui.notebook = ttk.Notebook(left_panel)
    gui.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    gui.manual_tab = tk.Frame(gui.notebook)
    gui.automated_tab = tk.Frame(gui.notebook)
    gui.optical_tab = tk.Frame(gui.notebook)
    gui.notebook.add(gui.manual_tab, text="  Manual Testing  ")
    gui.notebook.add(gui.automated_tab, text="  Automated Testing  ")
    gui.notebook.add(gui.optical_tab, text="  Optical  ")

    gui.create_manual_testing_tab(gui.manual_tab)
    gui.create_automated_testing_tab(gui.automated_tab)
    build_optical_tab(gui.optical_tab, gui)

    gui.create_pulse_diagram_section(right_panel)
    gui.create_plot_section(right_panel)
    gui.create_bottom_control_bar(right_panel)

    gui._update_test_list_capabilities()
