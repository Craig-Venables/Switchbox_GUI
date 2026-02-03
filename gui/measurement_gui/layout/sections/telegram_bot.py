"""
Telegram Bot Section
====================

Collapsible Telegram messaging controls.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from ..constants import COLOR_BG, FONT_MAIN
from ._collapsible import build_collapsible_section


def build_telegram_bot(builder: Any, parent: tk.Misc) -> None:
    """Build the Telegram Messaging collapsible section."""
    gui = builder.gui

    def build_content(content_frame: tk.Frame) -> None:
        current_value = getattr(gui, "get_messaged_var", 0)
        if hasattr(current_value, "get"):
            get_value = int(current_value.get())
        else:
            get_value = int(bool(current_value))
        gui.get_messaged_var = tk.IntVar(value=get_value)

        def on_telegram_checkbox_change():
            if hasattr(gui, "telegram"):
                gui.telegram.reset_credentials()

        ttk.Checkbutton(
            content_frame,
            text="Enable Telegram Bot",
            variable=gui.get_messaged_var,
            command=on_telegram_checkbox_change,
        ).pack(anchor="w", pady=(0, 10))

        tk.Label(content_frame, text="Operator:", font=FONT_MAIN, bg=COLOR_BG).pack(anchor="w", pady=(0, 5))

        names = list(getattr(gui, "names", []))
        default_name = "Choose name" if names else "No_Name"
        gui.selected_user = tk.StringVar(value=default_name)
        gui.messaging_user_menu = ttk.Combobox(
            content_frame,
            textvariable=gui.selected_user,
            values=names,
            state="readonly" if names else "disabled",
            font=FONT_MAIN,
        )
        gui.messaging_user_menu.pack(fill="x")

        update_cb = builder.callbacks.get("update_messaging_info") or getattr(gui, "update_messaging_info", None)
        if update_cb:
            gui.messaging_user_menu.bind("<<ComboboxSelected>>", update_cb)

    container = build_collapsible_section(
        parent,
        "📱 Telegram Messaging",
        build_content,
        start_expanded=False,
        content_bg=COLOR_BG,
    )
    builder.widgets["telegram_bot"] = container
