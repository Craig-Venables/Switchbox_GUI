"""
Device selection state and checkbox/canvas sync for SampleGUI.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

import tkinter as tk
from tkinter import ttk

if TYPE_CHECKING:
    from gui.sample_gui.main import SampleGUI


class SelectionController:
    """Manages selected devices, checkboxes, and canvas highlights."""

    def __init__(self, gui: "SampleGUI") -> None:
        self.gui = gui

    def update_device_checkboxes(self) -> None:
        gui = self.gui
        for widget in gui.scrollable_frame.winfo_children():
            widget.destroy()

        gui.device_checkboxes.clear()
        gui.checkbox_vars.clear()
        gui.device_status_labels.clear()

        for i, device in enumerate(gui.device_list):
            label = gui.get_device_label(device)
            var = tk.BooleanVar(value=True)

            row_frame = ttk.Frame(gui.scrollable_frame)
            row_frame.grid(row=i, column=0, sticky="w", pady=1)

            cb = tk.Checkbutton(
                row_frame,
                text=label,
                variable=var,
                command=gui.update_selected_devices,
            )
            cb.pack(side="left")

            status_info = gui.device_status.get(device, {})
            manual_status = status_info.get("manual_status", "undefined")
            icon = gui.status_icons.get(manual_status, "?")

            status_label = tk.Label(
                row_frame,
                text=icon,
                font=("Segoe UI", 10, "bold"),
                fg=gui._get_status_color(manual_status),
                width=2,
            )
            status_label.pack(side="left", padx=(5, 0))

            cb.bind("<Button-3>", lambda e, d=device: gui.show_device_status_menu(e, d))
            status_label.bind("<Button-3>", lambda e, d=device: gui.show_device_status_menu(e, d))

            gui.device_checkboxes[device] = cb
            gui.checkbox_vars[device] = var
            gui.device_status_labels[device] = status_label
            gui.selected_devices.add(device)

        self.update_selected_devices()

    def select_all_devices(self) -> None:
        for var in self.gui.checkbox_vars.values():
            var.set(True)
        self.update_selected_devices()

    def deselect_all_devices(self) -> None:
        for var in self.gui.checkbox_vars.values():
            var.set(False)
        self.update_selected_devices()

    def invert_selection(self) -> None:
        for var in self.gui.checkbox_vars.values():
            var.set(not var.get())
        self.update_selected_devices()

    def update_selected_devices(self) -> None:
        gui = self.gui
        gui.selected_devices.clear()
        gui.selected_indices.clear()

        for device, var in gui.checkbox_vars.items():
            if var.get():
                gui.selected_devices.add(device)
                if device in gui.device_list:
                    gui.selected_indices.append(gui.device_list.index(device))

        gui.selected_indices.sort()

        total = len(gui.device_list)
        selected = len(gui.selected_devices)
        gui.selection_status.config(text=f"Selected: {selected}/{total}")

        self.update_canvas_selection_highlights()
        self._update_status_bar()

        friendly_selected = [gui.get_device_label(gui.device_list[idx]) for idx in gui.selected_indices]
        selection_text = ", ".join(friendly_selected[:5])
        if len(friendly_selected) > 5:
            selection_text += f" ... (+{len(friendly_selected) - 5} more)"
        if not selection_text:
            selection_text = "None"
        gui.log_terminal(f"Selected devices: {selection_text}", "INFO")

        selected_device_list = [gui.device_list[i] for i in gui.selected_indices]
        gui._notify_child_guis(
            "device_selection",
            selected_devices=selected_device_list,
            selected_indices=gui.selected_indices.copy(),
        )

    def _update_status_bar(self) -> None:
        gui = self.gui
        total = len(gui.device_list) if hasattr(gui, "device_list") else 0
        selected = len(gui.selected_devices)

        if hasattr(gui, "device_count_label"):
            gui.device_count_label.config(text=f"Devices: {selected} selected / {total} total")

        if hasattr(gui, "measure_button"):
            if selected > 0:
                gui.measure_button.config(
                    text=f"Measure {selected} Selected Device{'s' if selected != 1 else ''}",
                )
            else:
                gui.measure_button.config(text="Measure Selected Devices")

    def update_canvas_selection_highlights(self) -> None:
        gui = self.gui
        gui.canvas.delete("selection")

        if not hasattr(gui, "original_image") or gui.original_image is None:
            return

        orig_width, orig_height = gui.original_image.size
        scale_x = orig_width / 600
        scale_y = orig_height / 500

        for device, bounds in gui.device_mapping.items():
            if device in gui.selected_devices:
                x_min = bounds["x_min"] / scale_x
                x_max = bounds["x_max"] / scale_x
                y_min = bounds["y_min"] / scale_y
                y_max = bounds["y_max"] / scale_y
                gui.canvas.create_rectangle(
                    x_min, y_min, x_max, y_max,
                    outline="#4CAF50", width=2, tags="selection",
                )

    def canvas_ctrl_click(self, event: Any) -> None:
        gui = self.gui
        if not hasattr(gui, "original_image") or gui.original_image is None:
            return

        orig_width, orig_height = gui.original_image.size
        scale_x = orig_width / 600
        scale_y = orig_height / 500

        for device, bounds in gui.device_mapping.items():
            x_min = bounds["x_min"] / scale_x
            x_max = bounds["x_max"] / scale_x
            y_min = bounds["y_min"] / scale_y
            y_max = bounds["y_max"] / scale_y

            if x_min <= event.x <= x_max and y_min <= event.y <= y_max:
                if device in gui.checkbox_vars:
                    current_value = gui.checkbox_vars[device].get()
                    gui.checkbox_vars[device].set(not current_value)
                    self.update_selected_devices()
                break
