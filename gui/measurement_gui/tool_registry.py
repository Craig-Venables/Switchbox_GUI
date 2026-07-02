"""
Registry for launching standalone hardware utility tools from MeasurementGUI.

New tool integration:
  1. Create an adapter in tool_adapters/
  2. Register it in DEFAULT_TOOLS below
  3. Optional: add a top-bar button via GuiToolRegistry.build_menu()
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Protocol, runtime_checkable

import tkinter as tk
from tkinter import messagebox

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


@runtime_checkable
class GuiTool(Protocol):
    """Contract for tools launchable from the main measurement GUI."""

    tool_id: str
    label: str
    description: str

    def launch(self, parent: tk.Misc) -> None:
        """Open the tool (subprocess or embedded window)."""


@dataclass
class SubprocessTool:
    """Launch a Python module in a separate process."""

    tool_id: str
    label: str
    description: str
    module_path: str
    cwd: Optional[Path] = None

    def launch(self, parent: tk.Misc) -> None:
        cwd = self.cwd or _PROJECT_ROOT
        script = _PROJECT_ROOT / self.module_path
        if not script.exists():
            messagebox.showerror(
                self.label,
                f"Tool script not found:\n{script}",
                parent=parent,
            )
            return
        try:
            popen_kwargs: dict = {"cwd": str(cwd)}
            if sys.platform == "win32":
                popen_kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
            subprocess.Popen(
                [sys.executable, str(script)],
                **popen_kwargs,
            )
        except OSError as exc:
            messagebox.showerror(
                self.label,
                f"Failed to launch {self.label}:\n{exc}",
                parent=parent,
            )


class GuiToolRegistry:
    """Lookup and UI helpers for registered tools."""

    def __init__(self, tools: Optional[List[GuiTool]] = None) -> None:
        self._tools: List[GuiTool] = list(tools or DEFAULT_TOOLS)

    @property
    def tools(self) -> List[GuiTool]:
        return list(self._tools)

    def get(self, tool_id: str) -> Optional[GuiTool]:
        for tool in self._tools:
            if tool.tool_id == tool_id:
                return tool
        return None

    def launch(self, tool_id: str, parent: tk.Misc) -> None:
        tool = self.get(tool_id)
        if tool is None:
            messagebox.showwarning("Tools", f"Unknown tool: {tool_id}", parent=parent)
            return
        tool.launch(parent)

    def build_menu(self, parent: tk.Misc, menu_button: tk.Misc) -> tk.Menu:
        """Attach a dropdown menu to menu_button with all registered tools."""
        toplevel = parent.winfo_toplevel()
        menu = tk.Menu(toplevel, tearoff=0)
        for tool in self._tools:
            menu.add_command(
                label=tool.label,
                command=lambda t=tool, win=toplevel: t.launch(win),
            )
        menu_button.configure(menu=menu)
        return menu

    def show_tools_popup(self, anchor: tk.Misc) -> None:
        """Show the tools menu below anchor (reliable on Windows)."""
        toplevel = anchor.winfo_toplevel()
        menu = tk.Menu(toplevel, tearoff=0)
        for tool in self._tools:
            menu.add_command(
                label=tool.label,
                command=lambda t=tool, win=toplevel: t.launch(win),
            )
        x = anchor.winfo_rootx()
        y = anchor.winfo_rooty() + anchor.winfo_height()
        try:
            menu.tk_popup(x, y)
        except tk.TclError:
            menu.post(x, y)

    def add_hardware_tools_button(self, parent: tk.Frame, font: tuple) -> tk.Button:
        """Create a 'Hardware Tools' button that opens a popup menu."""
        registry = self

        btn = tk.Button(
            parent,
            text="Hardware Tools",
            font=font,
            relief="raised",
            padx=10,
            pady=5,
            cursor="hand2",
            command=lambda: registry.show_tools_popup(btn),
        )
        btn.pack(side="left", padx=5)
        return btn


def _display_tool() -> SubprocessTool:
    return SubprocessTool(
        tool_id="display",
        label="Display Control (ST7789)",
        description="Arduino TFT colour / flash / brightness control",
        module_path="tools/Display/main.py",
        cwd=_PROJECT_ROOT / "tools" / "Display",
    )


def _led_testing_tool() -> SubprocessTool:
    return SubprocessTool(
        tool_id="led_testing",
        label="LED Testing (Arduino)",
        description="Exclusive LED control and timed patterns",
        module_path="tools/LED_testing/main.py",
        cwd=_PROJECT_ROOT / "tools" / "LED_testing",
    )


DEFAULT_TOOLS: List[GuiTool] = [
    _display_tool(),
    _led_testing_tool(),
]
