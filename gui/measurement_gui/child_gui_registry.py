"""
Registry for in-process child GUIs launched from the Measurement GUI top bar.

Add a new launcher by appending a ChildGuiSpec to DEFAULT_CHILD_GUIS and
registering the callback on MeasurementGUI / the layout callbacks dict.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import tkinter as tk


@dataclass(frozen=True)
class ChildGuiSpec:
    """One top-bar button that opens a child GUI or tool window."""

    tool_id: str
    label: str
    callback_key: str
    style: str = "default"  # "primary" (blue) or "default"


PRIMARY_STYLE = {
    "bg": "#2196f3",
    "fg": "white",
    "activebackground": "#1976d2",
    "activeforeground": "white",
    "relief": "raised",
    "cursor": "hand2",
    "padx": 12,
    "pady": 6,
}

DEFAULT_STYLE = {
    "bg": None,  # filled from builder COLOR_BG
    "relief": "raised",
    "padx": 10,
    "pady": 5,
}


DEFAULT_CHILD_GUIS: tuple[ChildGuiSpec, ...] = (
    ChildGuiSpec("motor", "Motor Control", "open_motor_control", "primary"),
    ChildGuiSpec("connection_check", "Check Connection", "check_connection", "primary"),
    ChildGuiSpec("pulse_testing", "Pulse Testing", "open_pulse_testing", "default"),
    ChildGuiSpec("device_visualizer", "Device Visualizer", "open_device_visualizer", "default"),
    ChildGuiSpec("oscilloscope_pulse", "Oscilloscope Pulse", "open_oscilloscope_pulse", "default"),
    ChildGuiSpec("laser_fg_scope", "Laser FG Scope", "open_laser_fg_scope", "default"),
)


class ChildGuiRegistry:
    """Build top-bar buttons and resolve launch callbacks."""

    def __init__(self, specs: Optional[tuple[ChildGuiSpec, ...]] = None) -> None:
        self._specs = specs or DEFAULT_CHILD_GUIS

    @property
    def specs(self) -> tuple[ChildGuiSpec, ...]:
        return self._specs

    def resolve_callback(
        self,
        spec: ChildGuiSpec,
        callbacks: Dict[str, Callable[..., Any]],
        gui: Any,
    ) -> Optional[Callable[..., Any]]:
        cb = callbacks.get(spec.callback_key)
        if callable(cb):
            return cb
        method = getattr(gui, spec.callback_key, None)
        if callable(method):
            return method
        return None

    def build_top_bar_buttons(
        self,
        parent: tk.Frame,
        gui: Any,
        callbacks: Dict[str, Callable[..., Any]],
        font: tuple,
        color_bg: str,
    ) -> Dict[str, tk.Button]:
        """Create one button per registered child GUI; return {tool_id: button}."""
        buttons: Dict[str, tk.Button] = {}
        attr_names = {
            "motor": "motor_control_button",
            "connection_check": "check_connection_button",
            "pulse_testing": "pulse_testing_button",
            "device_visualizer": "device_visualizer_button",
            "oscilloscope_pulse": "oscilloscope_pulse_button",
            "laser_fg_scope": "laser_fg_scope_button",
        }

        for spec in self._specs:
            command = self.resolve_callback(spec, callbacks, gui)
            if command is None:
                continue

            kwargs: Dict[str, Any] = {"font": font, "command": command}
            if spec.style == "primary":
                kwargs.update(PRIMARY_STYLE)
            else:
                kwargs.update(DEFAULT_STYLE)
                kwargs["bg"] = color_bg

            btn = tk.Button(parent, text=spec.label, **kwargs)
            btn.pack(side="left", padx=5)
            buttons[spec.tool_id] = btn

            attr = attr_names.get(spec.tool_id)
            if attr:
                setattr(gui, attr, btn)

        return buttons
