"""
Messaging / Telegram Handlers
=============================

Load and update Telegram messaging configuration.
Uses secure config loader (local file + env overrides). See gui.messaging_config.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import tkinter as tk

from gui.messaging_config import load_messaging_config


def load_messaging_data(gui: Any) -> None:
    """Populate Telegram messaging metadata (names, token/chat IDs) from secure config."""
    gui.messaging_profiles = load_messaging_config()
    gui.names = sorted(gui.messaging_profiles.keys())
    default_name = gui.names[0] if gui.names else ""
    profile = gui.messaging_profiles.get(default_name, {})

    gui.token_var = tk.StringVar(value=profile.get("token", ""))
    gui.chatid_var = tk.StringVar(value=profile.get("chatid", ""))
    gui.get_messaged_var = tk.IntVar(value=0)
    gui._selected_messaging_user = default_name


def update_messaging_info(gui: Any, _event: Optional[Any] = None) -> None:
    """Update token/chat ID when the operator selects a different profile."""
    selection = ""
    try:
        selected = getattr(gui, "selected_user", None)
        if isinstance(selected, tk.StringVar):
            selection = selected.get()
        elif isinstance(selected, str):
            selection = selected
    except Exception:
        selection = ""

    if not selection:
        selection = getattr(gui, "_selected_messaging_user", "") or ""

    profile = gui.messaging_profiles.get(selection)
    if not profile:
        return

    gui._selected_messaging_user = selection
    token = profile.get("token", "")
    chatid = profile.get("chatid", "")

    if hasattr(gui, "token_var") and hasattr(gui.token_var, "set"):
        gui.token_var.set(token)
    else:
        gui.token_var = token

    if hasattr(gui, "chatid_var") and hasattr(gui.chatid_var, "set"):
        gui.chatid_var.set(chatid)
    else:
        gui.chatid_var = chatid

    if hasattr(gui, "telegram"):
        gui.telegram.reset_credentials()
