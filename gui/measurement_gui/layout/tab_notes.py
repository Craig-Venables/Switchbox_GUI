"""
Notes Tab Builder
==================

Builds the Notes tab for device and sample notes with formatting and previous-device views.
Extracted from layout_builder for maintainability.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from .constants import COLOR_BG, COLOR_PRIMARY, COLOR_SECONDARY, FONT_BUTTON, FONT_HEADING, FONT_MAIN


def build_notes_tab(builder: Any, notebook: ttk.Notebook) -> None:
    """
    Create the Notes tab for device and sample notes.

    Args:
        builder: The layout builder instance (provides gui, widgets, and notes-related
                 methods like _save_all_notes, _insert_datetime, _load_notes, etc.).
        notebook: The ttk.Notebook to add the tab to.
    """
    gui = builder.gui

    tab = tk.Frame(notebook, bg=COLOR_BG)
    notebook.add(tab, text="  Notes  ")

    tab.columnconfigure(0, weight=2)
    tab.columnconfigure(1, weight=1)
    tab.rowconfigure(1, weight=1)

    control_frame = tk.Frame(tab, bg=COLOR_BG, padx=20, pady=10)
    control_frame.grid(row=0, column=0, columnspan=2, sticky="ew")
    control_frame.columnconfigure(0, weight=1)

    tk.Label(control_frame, text="Device Notes", font=FONT_HEADING, bg=COLOR_BG).grid(row=0, column=0, sticky="w")

    save_btn = tk.Button(
        control_frame,
        text="Save All Notes",
        font=FONT_BUTTON,
        bg=COLOR_PRIMARY,
        fg="white",
        command=lambda: builder._save_all_notes(gui),
        padx=15,
        pady=5,
    )
    save_btn.grid(row=0, column=1, sticky="e", padx=(20, 0))
    gui.notes_save_button = save_btn

    gui.notes_status_label = tk.Label(
        control_frame,
        text="",
        font=FONT_MAIN,
        bg=COLOR_BG,
        fg=COLOR_SECONDARY,
    )
    gui.notes_status_label.grid(row=0, column=2, sticky="e", padx=(10, 0))

    left_frame = tk.Frame(tab, bg=COLOR_BG)
    left_frame.grid(row=1, column=0, sticky="nsew", padx=(20, 10), pady=(0, 20))
    left_frame.columnconfigure(0, weight=1)
    left_frame.rowconfigure(1, weight=1)

    toolbar_frame = tk.Frame(left_frame, bg=COLOR_BG, pady=5)
    toolbar_frame.grid(row=0, column=0, columnspan=2, sticky="ew")

    tk.Button(
        toolbar_frame,
        text="📅 Date/Time",
        font=FONT_MAIN,
        bg="#e3f2fd",
        fg="#1976d2",
        command=lambda: builder._insert_datetime(gui),
        padx=8,
        pady=3,
    ).pack(side="left", padx=2)

    tk.Button(
        toolbar_frame,
        text="📊 Measurement Details",
        font=FONT_MAIN,
        bg="#e3f2fd",
        fg="#1976d2",
        command=lambda: builder._insert_measurement_details(gui),
        padx=8,
        pady=3,
    ).pack(side="left", padx=2)

    tk.Frame(toolbar_frame, bg="#ccc", width=1).pack(side="left", padx=5, fill="y", pady=2)

    tk.Button(
        toolbar_frame,
        text="B",
        font=("Arial", 12, "bold"),
        bg="#f5f5f5",
        fg="black",
        command=lambda: builder._toggle_bold(gui),
        padx=8,
        pady=3,
        width=3,
    ).pack(side="left", padx=2)

    tk.Button(
        toolbar_frame,
        text="I",
        font=("Arial", 12, "italic"),
        bg="#f5f5f5",
        fg="black",
        command=lambda: builder._toggle_italic(gui),
        padx=8,
        pady=3,
        width=3,
    ).pack(side="left", padx=2)

    gui.notes_text = tk.Text(
        left_frame,
        wrap=tk.WORD,
        font=("Consolas", 10),
        bg="white",
        fg="black",
        padx=10,
        pady=10,
        relief=tk.SOLID,
        borderwidth=1,
        undo=True,
        maxundo=50,
    )
    gui.notes_text.grid(row=1, column=0, sticky="nsew")

    notes_scrollbar = ttk.Scrollbar(left_frame, orient="vertical", command=gui.notes_text.yview)
    notes_scrollbar.grid(row=1, column=1, sticky="ns")
    gui.notes_text.configure(yscrollcommand=notes_scrollbar.set)

    tk.Label(
        left_frame,
        text="Auto-saves after 500ms of no typing. | Shortcuts: Ctrl+S (Save), Ctrl+D (Date/Time), Ctrl+Z (Undo), Ctrl+Y (Redo), Ctrl+B (Bold), Ctrl+I (Italic)",
        font=("Segoe UI", 8),
        bg=COLOR_BG,
        fg=COLOR_SECONDARY,
        anchor="w",
    ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(5, 0))

    right_frame = tk.Frame(tab, bg=COLOR_BG)
    right_frame.grid(row=1, column=1, sticky="nsew", padx=(10, 20), pady=(0, 20))
    right_frame.columnconfigure(0, weight=1)
    right_frame.rowconfigure(0, weight=1)
    right_frame.rowconfigure(1, weight=1)

    previous_devices = builder._get_previous_devices(gui)

    if len(previous_devices) > 0:
        prev1_frame = tk.LabelFrame(
            right_frame,
            text=f"Previous Device: {previous_devices[0]['name']}",
            font=FONT_MAIN,
            bg=COLOR_BG,
            padx=5,
            pady=5,
        )
        prev1_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 5))
        prev1_frame.columnconfigure(0, weight=1)
        prev1_frame.rowconfigure(0, weight=1)

        gui.prev_device1_text = tk.Text(
            prev1_frame,
            wrap=tk.WORD,
            font=("Consolas", 9),
            bg="white",
            fg="black",
            padx=8,
            pady=8,
            relief=tk.SOLID,
            borderwidth=1,
            height=15,
            undo=True,
            maxundo=50,
        )
        gui.prev_device1_text.grid(row=0, column=0, sticky="nsew")

        prev1_scrollbar = ttk.Scrollbar(prev1_frame, orient="vertical", command=gui.prev_device1_text.yview)
        prev1_scrollbar.grid(row=0, column=1, sticky="ns")
        gui.prev_device1_text.configure(yscrollcommand=prev1_scrollbar.set)

        builder._load_previous_device_notes(gui, previous_devices[0], gui.prev_device1_text)
        gui.prev_device1_text.bind(
            "<FocusOut>",
            lambda e: builder._save_previous_device_notes(gui, previous_devices[0], gui.prev_device1_text),
        )
        gui.prev_device1_text.bind("<KeyRelease>", lambda e: builder._mark_prev_device1_changed(gui))
    else:
        empty_frame1 = tk.LabelFrame(
            right_frame,
            text="Previous Device: None",
            font=FONT_MAIN,
            bg=COLOR_BG,
            padx=5,
            pady=5,
        )
        empty_frame1.grid(row=0, column=0, sticky="nsew", pady=(0, 5))
        tk.Label(
            empty_frame1, text="No previous device", font=FONT_MAIN, bg=COLOR_BG, fg=COLOR_SECONDARY
        ).pack(pady=20)
        gui.prev_device1_text = None

    sample_name = builder._get_sample_name(gui)
    sample_label = f"Sample Notes: {sample_name}" if sample_name else "Sample Notes"

    sample_frame = tk.LabelFrame(
        right_frame, text=sample_label, font=FONT_MAIN, bg=COLOR_BG, padx=5, pady=5
    )
    sample_frame.grid(row=1, column=0, sticky="nsew")
    sample_frame.columnconfigure(0, weight=1)
    sample_frame.rowconfigure(0, weight=1)

    gui.sample_notes_text = tk.Text(
        sample_frame,
        wrap=tk.WORD,
        font=("Consolas", 9),
        bg="#fffef0",
        fg="black",
        padx=8,
        pady=8,
        relief=tk.SOLID,
        borderwidth=1,
        height=15,
        undo=True,
        maxundo=50,
    )
    gui.sample_notes_text.grid(row=0, column=0, sticky="nsew")

    sample_scrollbar = ttk.Scrollbar(sample_frame, orient="vertical", command=gui.sample_notes_text.yview)
    sample_scrollbar.grid(row=0, column=1, sticky="ns")
    gui.sample_notes_text.configure(yscrollcommand=sample_scrollbar.set)
    gui.sample_notes_frame = sample_frame

    builder._load_sample_notes(gui)
    gui.sample_notes_text.bind("<FocusOut>", lambda e: builder._save_sample_notes(gui))
    gui.sample_notes_text.bind("<KeyRelease>", lambda e: builder._mark_sample_notes_changed(gui))

    builder._load_notes(gui)

    gui.notes_last_saved = gui.notes_text.get("1.0", tk.END)
    gui.notes_changed = False
    if gui.prev_device1_text:
        gui.prev_device1_last_saved = gui.prev_device1_text.get("1.0", tk.END)
        gui.prev_device1_changed = False
    gui.sample_notes_last_saved = gui.sample_notes_text.get("1.0", tk.END)
    gui.sample_notes_changed = False

    gui.notes_text.bind("<FocusOut>", lambda e: builder._auto_save_notes(gui))
    gui.notes_text.bind("<KeyRelease>", lambda e: builder._on_notes_key_release(gui))

    builder._setup_notes_keyboard_shortcuts(gui, tab)

    def on_tab_change(event):
        try:
            current_tab_text = event.widget.tab("current")["text"].strip()
            if current_tab_text == "Notes":
                builder._load_notes(gui)
                previous_devices = builder._get_previous_devices(gui)
                if (
                    len(previous_devices) > 0
                    and hasattr(gui, "prev_device1_text")
                    and gui.prev_device1_text
                ):
                    builder._load_previous_device_notes(gui, previous_devices[0], gui.prev_device1_text)
                    gui.prev_device1_last_saved = gui.prev_device1_text.get("1.0", tk.END)
                    prev1_frame = gui.prev_device1_text.master
                    if isinstance(prev1_frame, tk.LabelFrame):
                        prev1_frame.config(text=f"Previous Device: {previous_devices[0]['name']}")
                if hasattr(gui, "sample_notes_text"):
                    builder._load_sample_notes(gui)
                    gui.sample_notes_last_saved = gui.sample_notes_text.get("1.0", tk.END)
                    sample_name = builder._get_sample_name(gui)
                    sample_label = f"Sample Notes: {sample_name}" if sample_name else "Sample Notes"
                    if hasattr(gui, "sample_notes_frame"):
                        gui.sample_notes_frame.config(text=sample_label)
            else:
                if hasattr(gui, "notes_text"):
                    builder._save_notes(gui)
                if hasattr(gui, "prev_device1_text") and gui.prev_device1_text:
                    previous_devices = builder._get_previous_devices(gui)
                    if len(previous_devices) > 0:
                        builder._save_previous_device_notes(
                            gui, previous_devices[0], gui.prev_device1_text
                        )
                if hasattr(gui, "sample_notes_text"):
                    builder._save_sample_notes(gui)
        except Exception:
            pass

    notebook.bind("<<NotebookTabChanged>>", on_tab_change)

    builder._start_auto_save_timer(gui)
    builder._start_device_change_polling(gui)
    builder._start_sample_change_polling(gui)

    builder.widgets["notes_tab"] = tab
