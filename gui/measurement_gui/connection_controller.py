"""Instrument connection helpers for MeasurementGUI."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from tkinter import messagebox

if TYPE_CHECKING:
    from gui.measurement_gui.main import MeasurementGUI


class ConnectionController:
    """SMU, PSU, and temperature controller connect/reconnect logic."""

    def __init__(self, gui: "MeasurementGUI") -> None:
        self.gui = gui

    def connect_keithley(self) -> None:
        gui = self.gui
        address = gui.keithley_address_var.get()
        smu_type = getattr(gui, "SMU_type", "Keithley 2401")
        try:
            instrument = gui.connections.connect_keithley(smu_type, address)
            gui.keithley = instrument
            gui.connected = gui.connections.is_connected("keithley")
            gui._update_conditional_testing_button_state()
            gui._apply_smu_current_range()
            if hasattr(gui.keithley, "beep"):
                gui.keithley.beep(4000, 0.2)
                time.sleep(0.2)
                gui.keithley.beep(5000, 0.5)
        except RuntimeError as exc:
            gui.connected = False
            gui._update_conditional_testing_button_state()
            error_str = str(exc)
            print(f"❌ ERROR: Unable to connect to SMU ({smu_type} @ {address})")
            print(f"   {error_str}")
            if "IVControllerManager dependency not available" in error_str:
                detailed_msg = (
                    f"Could not connect to IV Controller Manager.\n\n"
                    f"The required dependencies are not available.\n\n"
                    f"Please check:\n"
                    f"• That Equipment/managers/iv_controller.py exists\n"
                    f"• That all required dependencies are installed\n"
                    f"• Try restarting Python/your IDE\n\n"
                    f"Original error:\n{exc}"
                )
            else:
                detailed_msg = f"Could not connect to device ({smu_type} @ {address}):\n\n{exc}"
            messagebox.showerror("Connection Error", detailed_msg)
        except Exception as exc:
            gui.connected = False
            print(f"❌ ERROR: Unable to connect to SMU ({smu_type} @ {address}): {exc}")
            messagebox.showerror(
                "Connection Error",
                f"Could not connect to device ({smu_type} @ {address}):\n\n{exc}",
            )

    def connect_keithley_psu(self) -> None:
        gui = self.gui
        try:
            gui.psu = gui.connections.connect_psu(gui.psu_visa_address)
            gui.psu_connected = gui.connections.is_connected("psu")
            if gui.keithley and hasattr(gui.keithley, "beep"):
                gui.keithley.beep(5000, 0.2)
                time.sleep(0.2)
                gui.keithley.beep(6000, 0.2)
            if gui.psu:
                gui.psu.reset()
        except Exception as exc:
            gui.psu_connected = False
            print("unable to connect to psu please check")
            messagebox.showerror("Error", f"Could not connect to device: {exc}")

    def connect_temp_controller(self) -> None:
        gui = self.gui
        address = gui.temp_controller_address
        try:
            gui.itc = gui.connections.connect_oxford_itc4(address)
            gui.itc_connected = gui.connections.is_connected("itc")
            print("connected too Temp controller")
            if gui.keithley and hasattr(gui.keithley, "beep"):
                gui.keithley.beep(7000, 0.2)
                time.sleep(0.2)
                gui.keithley.beep(8000, 0.2)
        except Exception as exc:
            gui.itc_connected = False
            print("unable to connect to Temp please check")
            messagebox.showerror("Error", f"Could not connect to temp device: {exc}")

    def init_temperature_controller(self) -> None:
        gui = self.gui
        gui.temp_controller = gui.connections.create_temperature_controller(auto_detect=True)
        info = gui.connections.get_temperature_info()
        if info:
            gui.log_terminal(f"Temperature Controller: {info['type']} at {info['address']}")
            gui.log_terminal(f"Current temperature: {info['temperature']:.1f}°C")
        else:
            gui.log_terminal("No temperature controller detected - using 25°C default")

    def reconnect_temperature_controller(self) -> None:
        gui = self.gui
        controller_type = getattr(gui, "controller_type", "Auto-Detect")
        if hasattr(gui, "controller_type_var"):
            try:
                controller_type = gui.controller_type_var.get()
            except Exception:
                controller_type = getattr(gui, "controller_type", "Auto-Detect")
        address = getattr(gui, "controller_address", gui.temp_controller_address)
        if hasattr(gui, "controller_address_var"):
            try:
                address = gui.controller_address_var.get()
            except Exception:
                address = getattr(gui, "controller_address", gui.temp_controller_address)
        gui.controller_type = controller_type or "Auto-Detect"
        gui.controller_address = address

        try:
            if gui.temp_controller:
                gui.temp_controller.close()
        except Exception:
            pass

        if controller_type == "Auto-Detect":
            gui.temp_controller = gui.connections.create_temperature_controller(auto_detect=True)
        elif controller_type == "None":
            gui.temp_controller = None
            self.update_controller_status()
            return
        else:
            if address == "Auto":
                default_addresses = {
                    "Lakeshore 335": "12",
                    "Oxford ITC4": "ASRL12::INSTR",
                }
                address = default_addresses.get(controller_type, "12")
            gui.temp_controller = gui.connections.create_temperature_controller(
                auto_detect=False,
                controller_type=controller_type,
                address=address,
            )

        self.update_controller_status()

    def reconnect_keithley_controller(self) -> None:
        """Legacy typo alias — reconnects temperature controller."""
        self.reconnect_temperature_controller()

    def update_controller_status(self) -> None:
        gui = self.gui
        info = gui.connections.get_temperature_info()
        label = getattr(gui, "controller_status_label", None)
        entry = getattr(gui, "target_temp_entry", None)
        btn = getattr(gui, "target_temp_button", None)
        if label:
            if info:
                label.config(text=f"● Connected: {info['type']}", fg="green")
            else:
                label.config(text="● Disconnected", fg="red")
        state = "normal" if info else "disabled"
        if entry:
            entry.configure(state=state)
        if btn:
            btn.configure(state=state)

    def auto_connect_current_system(self) -> bool:
        gui = self.gui
        keithley_address = ""
        if hasattr(gui, "keithley_address_var"):
            try:
                keithley_address = gui.keithley_address_var.get().strip()
            except Exception:
                keithley_address = ""
        if not keithley_address:
            keithley_address = getattr(gui, "keithley_address", "").strip()

        smu_type = getattr(gui, "SMU_type", "")
        if not smu_type and hasattr(gui, "smu_type_var"):
            try:
                smu_type = gui.smu_type_var.get()
            except Exception:
                smu_type = ""
        smu_type = smu_type or "Keithley 2401"

        status_label = getattr(gui, "connection_status_label", None)
        success_color = (
            getattr(gui.layout_builder, "COLOR_SUCCESS", "green")
            if hasattr(gui, "layout_builder")
            else "green"
        )
        error_color = (
            getattr(gui.layout_builder, "COLOR_ERROR", "red")
            if hasattr(gui, "layout_builder")
            else "red"
        )
        warning_color = (
            getattr(gui.layout_builder, "COLOR_WARNING", "orange")
            if hasattr(gui, "layout_builder")
            else "orange"
        )

        if not keithley_address:
            print("⚠️  No SMU address configured; skipping auto-connect.")
            if status_label:
                status_label.config(text="● Address Required", fg=warning_color)
            return False

        if status_label:
            status_label.config(text="● Connecting...", fg=warning_color)

        print(f"Connecting to {smu_type} @ {keithley_address}...")
        self.connect_keithley()

        connected = getattr(gui, "connected", False)
        if connected:
            idn = ""
            try:
                if hasattr(gui.keithley, "get_idn"):
                    idn = gui.keithley.get_idn()
            except Exception as exc:
                print(f"⚠️  Warning: Unable to query IDN: {exc}")

            model_number = smu_type
            if idn:
                parts = idn.split(",")
                for part in parts:
                    part = part.strip()
                    if "MODEL" in part.upper():
                        model_match = part.upper().replace("MODEL", "").strip()
                        if model_match:
                            model_number = model_match
                            break
                    elif any(char.isdigit() for char in part) and len(part) <= 10:
                        if any(x in part.upper() for x in ["2400", "2450", "2600", "4200", "2636"]):
                            model_number = part
                            break

            status_text = model_number
            print(f"✓ Connected: {idn or f'{smu_type} @ {keithley_address}'}")
            if status_label:
                status_label.config(text=f"● Connected: {status_text}", fg=success_color)
            return True

        print(f"❌ Connection failed for {smu_type} @ {keithley_address}")
        if status_label:
            status_label.config(text="● Connection Failed", fg=error_color)
        return False
