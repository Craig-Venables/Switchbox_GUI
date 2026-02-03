"""
Conditional Testing Quick Select Section
========================================

Collapsible quick selector for conditional testing.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Any

from ..constants import COLOR_BG, FONT_BUTTON, FONT_MAIN
from ._collapsible import build_collapsible_section


def build_conditional_testing_quick(builder: Any, parent: tk.Misc) -> None:
    """Build the Conditional Testing quick select collapsible section."""
    gui = builder.gui

    def build_content(content_frame: tk.Frame) -> None:
        tk.Label(
            content_frame,
            text="Conditional Testing Configuration:",
            font=FONT_MAIN,
            bg=COLOR_BG,
        ).pack(anchor="w", pady=(0, 5))

        gui.conditional_testing_status_var = tk.StringVar(value="No config loaded")
        tk.Label(
            content_frame,
            textvariable=gui.conditional_testing_status_var,
            font=FONT_MAIN,
            bg=COLOR_BG,
            fg="gray",
        ).pack(anchor="w", pady=(0, 10))

        btn_frame = tk.Frame(content_frame, bg=COLOR_BG)
        btn_frame.pack(fill="x")
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        tk.Button(
            btn_frame,
            text="Load Config",
            font=FONT_BUTTON,
            bg="#2196f3",
            fg="white",
            activebackground="#1976d2",
            activeforeground="white",
            relief="raised",
            cursor="hand2",
            pady=6,
            command=lambda: _load_conditional_config(builder, gui),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 3))

        run_conditional_btn = tk.Button(
            btn_frame,
            text="Run Conditional",
            font=("Segoe UI", 10, "bold"),
            bg="#4CAF50",
            fg="white",
            activebackground="#388e3c",
            activeforeground="white",
            relief="raised",
            cursor="hand2",
            pady=8,
            command=builder.callbacks.get("run_conditional_testing"),
        )
        run_conditional_btn.grid(row=0, column=1, sticky="ew", padx=(3, 0))
        gui.run_conditional_button_main = run_conditional_btn

        if hasattr(gui, "connected") and gui.connected:
            run_conditional_btn.config(state=tk.NORMAL)
        else:
            run_conditional_btn.config(state=tk.DISABLED)

    container = build_collapsible_section(
        parent,
        "⚡ Conditional Testing",
        build_content,
        start_expanded=False,
        header_bg="#fff3e0",
        header_fg="#e65100",
        content_bg=COLOR_BG,
    )
    builder.widgets["conditional_testing_quick"] = container


def _load_conditional_config(builder: Any, gui) -> None:
    """Load conditional testing configuration and update status."""
    if hasattr(gui, "_load_conditional_test_config"):
        config = gui._load_conditional_test_config()
        if config:
            quick_test = config.get("quick_test", {}).get("custom_sweep_name", "")
            basic_test = config.get("tests", {}).get("basic_memristive", {}).get("custom_sweep_name", "")
            high_quality_test = config.get("tests", {}).get("high_quality", {}).get("custom_sweep_name", "")
            final_test = config.get("final_test", {}).get("custom_sweep_name", "")

            if quick_test and basic_test:
                status_parts = [f"Quick: {quick_test[:15]}..."]
                if final_test:
                    status_parts.append(f"Final: {final_test[:15]}...")
                status_text = " | ".join(status_parts)
                if hasattr(gui, "conditional_testing_status_var"):
                    gui.conditional_testing_status_var.set(status_text)

                final_info = f"\nFinal Test: {final_test}" if final_test else "\nFinal Test: Not configured"
                messagebox.showinfo(
                    "Config Loaded",
                    f"Conditional testing configuration loaded:\n\nQuick Test: {quick_test}\nBasic Test: {basic_test}\nHigh Quality: {high_quality_test or 'Not set'}{final_info}",
                )
            else:
                messagebox.showwarning(
                    "Incomplete Config",
                    "Configuration is incomplete. Please configure in Advanced Tests tab.",
                )
