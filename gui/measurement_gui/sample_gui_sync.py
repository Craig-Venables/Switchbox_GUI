"""Sync MeasurementGUI state when SampleGUI changes (overlay, sample name)."""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING, Any

from tkinter import simpledialog

if TYPE_CHECKING:
    from gui.measurement_gui.main import MeasurementGUI


class SampleGuiSyncController:
    """Handle SampleGUI → MeasurementGUI notifications and plot overlay."""

    def __init__(self, gui: "MeasurementGUI") -> None:
        self.gui = gui

    def check_for_sample_name(self) -> None:
        gui = self.gui
        if gui.sample_name_var.get().strip():
            return

        result_holder: list[Any] = [None]

        def ask_on_main_thread() -> None:
            new_name = simpledialog.askstring(
                "Sample Name Required",
                "Enter sample name (or cancel for 'undefined'):",
                parent=gui.master,
            )
            if new_name:
                cleaned_name = new_name.strip()
                for char in '<>:"|?*\\/[]':
                    cleaned_name = cleaned_name.replace(char, "_")
                gui.sample_name_var.set(cleaned_name if cleaned_name else "undefined")
            else:
                gui.sample_name_var.set("undefined")
            result_holder[0] = True

        try:
            if threading.current_thread() == threading.main_thread():
                ask_on_main_thread()
            else:
                gui.master.after(0, ask_on_main_thread)
                elapsed = 0
                while result_holder[0] is None and elapsed < 60:
                    time.sleep(0.1)
                    elapsed += 0.1
                if result_holder[0] is None:
                    gui.sample_name_var.set("undefined")
        except Exception as exc:
            print(f"Error in sample name dialog: {exc}")
            gui.sample_name_var.set("undefined")

    def update_overlay_from_current_state(self) -> None:
        gui = self.gui
        if not hasattr(gui, "plot_panels") or not hasattr(gui.plot_panels, "update_overlay"):
            return

        sample_name = "—"
        if hasattr(gui, "sample_name_var"):
            try:
                name = gui.sample_name_var.get().strip()
                if name:
                    sample_name = name
            except Exception:
                pass
        if sample_name in ("—", ""):
            if hasattr(gui.sample_gui, "current_device_name") and gui.sample_gui.current_device_name:
                sample_name = gui.sample_gui.current_device_name
        if sample_name in ("—", ""):
            if hasattr(gui.sample_gui, "sample_type_var"):
                try:
                    sample_type = gui.sample_gui.sample_type_var.get()
                    if sample_type:
                        sample_name = sample_type
                except Exception:
                    pass

        device_label = "—"
        try:
            if hasattr(gui, "device_section_and_number") and gui.device_section_and_number:
                device_label = gui.device_section_and_number
            elif hasattr(gui.sample_gui, "device_var"):
                try:
                    device = gui.sample_gui.device_var.get()
                    if device:
                        device_label = device
                except Exception:
                    pass
            if device_label == "—" and hasattr(gui, "current_index") and hasattr(
                gui.sample_gui, "device_list",
            ):
                if 0 <= gui.current_index < len(gui.sample_gui.device_list):
                    device_key = gui.sample_gui.device_list[gui.current_index]
                    if hasattr(gui.sample_gui, "get_device_label"):
                        device_label = gui.sample_gui.get_device_label(device_key)
                    else:
                        device_label = str(device_key)
        except Exception:
            pass

        current_voltage = getattr(gui, "current_voltage", "0V")
        if current_voltage == "0V" and hasattr(gui, "v_arr_disp") and gui.v_arr_disp:
            try:
                current_voltage = f"{float(gui.v_arr_disp[-1]):.3f}V"
            except Exception:
                pass

        current_loop = getattr(gui, "current_loop", "#1")
        if current_loop == "#1":
            loop_val = getattr(gui, "sweep_num", None) or getattr(gui, "measurment_number", None)
            if loop_val is not None:
                current_loop = f"#{loop_val}"

        gui.plot_panels.update_overlay(
            sample_name=sample_name,
            device=device_label,
            voltage=current_voltage,
            loop=current_loop,
        )

    def on_sample_gui_change(self, change_type: str, **kwargs: Any) -> None:
        gui = self.gui
        try:
            if change_type == "device_name":
                device_name = kwargs.get("device_name")
                if hasattr(gui, "sample_name_var"):
                    if device_name:
                        gui.sample_name_var.set(device_name)
                    elif hasattr(gui.sample_gui, "sample_type_var"):
                        try:
                            sample_type = gui.sample_gui.sample_type_var.get()
                            if sample_type:
                                gui.sample_name_var.set(sample_type)
                        except Exception:
                            pass
                self.update_overlay_from_current_state()

            elif change_type == "sample_type":
                sample_type = kwargs.get("sample_type")
                if hasattr(gui, "sample_name_var"):
                    current_name = gui.sample_name_var.get().strip()
                    if not current_name or (
                        hasattr(gui.sample_gui, "sample_type_var")
                        and current_name == getattr(gui.sample_gui, "sample_type_var", None)
                    ):
                        if sample_type:
                            gui.sample_name_var.set(sample_type)
                self.update_overlay_from_current_state()

            elif change_type == "section":
                device = kwargs.get("device")
                if device and hasattr(gui.sample_gui, "device_list"):
                    try:
                        device_key = gui.sample_gui.get_device_key_from_label(device)
                        if device_key and device_key in gui.sample_gui.device_list:
                            new_index = gui.sample_gui.device_list.index(device_key)
                            if new_index != gui.current_index:
                                gui.current_index = new_index
                                if hasattr(gui, "device_list") and gui.current_index < len(gui.device_list):
                                    gui.current_device = gui.device_list[gui.current_index]
                                    gui.device_section_and_number = gui.convert_to_name(gui.current_index)
                                    gui.display_index_section_number = (
                                        f"{gui.device_section_and_number} ({gui.current_device})"
                                    )
                    except Exception:
                        pass
                self.update_overlay_from_current_state()

            elif change_type == "device_selection":
                selected_devices = kwargs.get("selected_devices", [])
                if selected_devices:
                    gui.device_list = selected_devices.copy()
                    if gui.current_index >= len(gui.device_list):
                        gui.current_index = 0 if gui.device_list else 0
                    if gui.device_list and gui.current_index < len(gui.device_list):
                        gui.current_device = gui.device_list[gui.current_index]
                        gui.device_section_and_number = gui.convert_to_name(gui.current_index)
                        gui.display_index_section_number = (
                            f"{gui.device_section_and_number} ({gui.current_device})"
                        )
                self.update_overlay_from_current_state()
        except Exception as exc:
            print(f"Error handling sample_gui change notification ({change_type}): {exc}")
