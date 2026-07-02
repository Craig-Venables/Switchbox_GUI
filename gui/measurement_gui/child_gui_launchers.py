"""Launch in-process child GUIs from the Measurement GUI top bar."""

from __future__ import annotations

import time
from typing import Any, Optional

from tkinter import messagebox

from gui.connection_check_gui import CheckConnection
from gui.motor_control_gui import MotorControlWindow
from gui.oscilloscope_pulse_gui.main import OscilloscopePulseGUI
from gui.pulse_testing_gui import TSPTestingGUI


def resolve_sample_name(gui: Any) -> Optional[str]:
    """Best-effort sample name from Measurement GUI or parent Sample GUI."""
    if hasattr(gui, "sample_name_var"):
        try:
            name = gui.sample_name_var.get().strip()
            if name:
                return name
        except Exception:
            pass
    sample_gui = getattr(gui, "sample_gui", None)
    if sample_gui:
        for attr in ("current_device_name", "current_sample_name", "sample_name"):
            fallback = getattr(sample_gui, attr, None)
            if fallback:
                return str(fallback).strip()
    return None


def open_pulse_testing_gui(gui: Any) -> None:
    sample_name = resolve_sample_name(gui)
    device_label = getattr(gui, "device_section_and_number", None)
    custom_path = None
    use_custom_var = getattr(gui, "use_custom_save_var", None)
    if use_custom_var and use_custom_var.get():
        custom_loc = getattr(gui, "custom_save_location", None)
        if custom_loc:
            custom_path = str(custom_loc)

    address = getattr(gui, "keithley_address", None)
    if not address and hasattr(gui, "keithley_address_var"):
        try:
            address = gui.keithley_address_var.get().strip()
        except Exception:
            address = None

    try:
        TSPTestingGUI(
            gui.master,
            device_address=address or "GPIB0::17::INSTR",
            provider=gui,
            sample_name=sample_name,
            device_label=device_label,
            custom_save_base=custom_path,
        )
    except Exception as exc:
        messagebox.showerror("Pulse Testing", f"Could not open Pulse Testing GUI:\n{exc}")


def open_laser_fg_scope_gui(gui: Any) -> None:
    try:
        from gui.laser_fg_scope_gui import LaserFGScopeGUI

        LaserFGScopeGUI(gui.master, provider=gui)
    except Exception as exc:
        messagebox.showerror("Laser FG Scope GUI", f"Could not open Laser FG Scope GUI:\n{exc}")


def open_device_visualizer(gui: Any) -> None:
    sample_name = resolve_sample_name(gui)
    sample_path = None
    if sample_name:
        try:
            sample_path = gui._get_sample_save_directory(sample_name)
        except Exception:
            sample_path = None
    try:
        from tools.device_visualizer.device_visualizer_app import launch_visualizer

        launch_visualizer(sample_path=sample_path)
    except Exception as exc:
        import traceback

        traceback.print_exc()
        messagebox.showerror("Device Visualizer", f"Could not open Device Visualizer:\n{exc}")


def open_oscilloscope_pulse(gui: Any) -> None:
    try:
        from gui.measurement_gui.smu_adapter import SMUAdapter

        adapter = SMUAdapter(gui.keithley) if gui.keithley else None
        sample_name = resolve_sample_name(gui) or "Unknown"
        device_label = (
            getattr(gui, "device_section_and_number", None)
            or getattr(gui, "current_device", "Stand-alone")
        )
        systems = getattr(gui, "systems", [])
        if isinstance(systems, dict):
            known_systems = list(systems.keys())
        elif isinstance(systems, list):
            known_systems = systems
        else:
            known_systems = []
        context = {
            "device_label": device_label,
            "sample_name": sample_name,
            "save_directory": gui.default_save_root,
            "smu_ports": [gui.keithley_address],
            "known_systems": known_systems,
            "system": gui.controller_type,
            "provider": gui,
        }
        OscilloscopePulseGUI(gui.master, smu_instance=adapter, context=context)
    except Exception as exc:
        messagebox.showerror("Error", f"Failed to open Oscilloscope Pulse GUI:\n{exc}")


def open_motor_control(gui: Any) -> None:
    try:
        existing = getattr(gui, "motor_control_window", None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            return
    except Exception:
        pass
    try:
        gui.motor_control_window = MotorControlWindow()
    except Exception as exc:
        messagebox.showerror("Motor Control", f"Unable to open motor control GUI:\n{exc}")


def check_connection(gui: Any) -> None:
    gui.connect_keithley()
    time.sleep(0.1)
    gui.Check_connection_gui = CheckConnection(gui.master, gui.keithley)
