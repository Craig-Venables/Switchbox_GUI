"""Terminal log panel for SampleGUI."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import tkinter as tk
from tkinter import messagebox

from gui.sample_gui.config import resolve_default_save_root

if TYPE_CHECKING:
    from gui.sample_gui.main import SampleGUI


class TerminalLogController:
    """Timestamped terminal output with filter and export."""

    def __init__(self, gui: "SampleGUI") -> None:
        self.gui = gui

    def log(self, message: str, level: str = "INFO") -> None:
        gui = self.gui
        timestamp = datetime.now().strftime("%H:%M:%S")
        gui.terminal_messages.append((timestamp, level, message))

        if gui.terminal_filter.get() != "All" and level != gui.terminal_filter.get().upper():
            return

        gui.terminal_output.config(state=tk.NORMAL)
        gui.terminal_output.insert(tk.END, f"[{timestamp}] ", "TIMESTAMP")
        gui.terminal_output.insert(tk.END, f"{message}\n", level.upper())
        gui.terminal_output.config(state=tk.DISABLED)
        gui.terminal_output.see(tk.END)

    def apply_filter(self) -> None:
        gui = self.gui
        filter_value = gui.terminal_filter.get()
        gui.terminal_output.config(state=tk.NORMAL)
        gui.terminal_output.delete("1.0", tk.END)
        for timestamp, level, message in gui.terminal_messages:
            if filter_value == "All" or level == filter_value.upper():
                gui.terminal_output.insert(tk.END, f"[{timestamp}] ", "TIMESTAMP")
                gui.terminal_output.insert(tk.END, f"{message}\n", level.upper())
        gui.terminal_output.config(state=tk.DISABLED)
        gui.terminal_output.see(tk.END)

    def clear(self) -> None:
        gui = self.gui
        gui.terminal_output.config(state=tk.NORMAL)
        gui.terminal_output.delete("1.0", tk.END)
        gui.terminal_output.config(state=tk.DISABLED)
        gui.terminal_messages.clear()

    def export(self) -> None:
        gui = self.gui
        save_root = resolve_default_save_root()
        log_path = save_root / f"terminal_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        try:
            with log_path.open("w", encoding="utf-8") as f:
                for ts, level, msg in gui.terminal_messages:
                    f.write(f"[{ts}] [{level}] {msg}\n")
            messagebox.showinfo("Export Complete", f"Log exported to:\n{log_path}")
            self.log(f"Exported log to {log_path.name}", "SUCCESS")
        except Exception as exc:
            messagebox.showerror("Export Error", f"Failed to export log: {exc}")
