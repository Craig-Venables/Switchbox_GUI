"""System configuration load/save and optical setup for MeasurementGUI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, List

from tkinter import messagebox, simpledialog

from Equipment.optical_excitation import create_optical_from_system_config

if TYPE_CHECKING:
    from gui.measurement_gui.main import MeasurementGUI

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class SystemConfigController:
    """Load/save system_configs.json and sync Setup tab fields."""

    def __init__(self, gui: "MeasurementGUI") -> None:
        self.gui = gui

    def set_default_system(self) -> None:
        """Set default system to 'Please Select System' without auto-connecting"""
        gui = self.gui
        systems = gui.systems
        default = "Please Select System"
        # Set to "Please Select System" without triggering auto-connect
        gui.system_var.set(default)
        # Don't call _handle_system_selection to avoid auto-connection


    def load_systems(self) -> List[str]:
        """Load system configurations from JSON file"""
        gui = self.gui
        config_file = str(_PROJECT_ROOT / "Json_Files" / "system_configs.json")

        try:
            with open(config_file, 'r') as f:
                gui.system_configs = json.load(f)
            systems_list = list(gui.system_configs.keys())
            # Prepend "Please Select System" to the list
            return ["Please Select System"] + systems_list
        except (FileNotFoundError, json.JSONDecodeError):
            return ["Please Select System", "No systems available"]


    def get_smu_current_range_a(self) -> float:
        """Return configured SMU current measurement range in A (0 = auto)."""
        gui = self.gui
        raw_value = 0.0
        try:
            if hasattr(gui, "smu_current_range_var"):
                raw_value = float(gui.smu_current_range_var.get())
            else:
                raw_value = float(getattr(gui, "smu_current_range_a", 0.0))
        except Exception:
            raw_value = 0.0
        if raw_value < 0:
            return 0.0
        return raw_value


    def apply_smu_current_range(self) -> None:
        """
        Apply current measurement range to active SMU if supported.
        0 means auto range.
        """
        gui = self.gui
        current_range_a = self.get_smu_current_range_a()
        gui.smu_current_range_a = current_range_a
        try:
            if getattr(gui, "keithley", None) is not None and hasattr(gui.keithley, "set_current_measurement_range"):
                gui.keithley.set_current_measurement_range(current_range_a)
        except Exception as e:
            print(f"Warning: Could not apply SMU current range ({current_range_a} A): {e}")


    def load_system(self) -> None:
        """Load the selected system configuration and populate all fields"""
        gui = self.gui
        selected_system = getattr(gui, 'system_var', None)
        if not selected_system:
            return

        system_name = selected_system.get() if hasattr(selected_system, 'get') else str(selected_system)
        if not system_name or system_name == "No systems available" or system_name == "Please Select System":
            return

        if not hasattr(gui, 'system_configs') or system_name not in gui.system_configs:
            # Reload systems
            self.load_systems()
            if system_name not in gui.system_configs:
                messagebox.showwarning("System Not Found", f"System '{system_name}' not found in configuration file.")
                return

        config = gui.system_configs[system_name]

        # Update SMU section
        smu_type = config.get("SMU Type", "")
        smu_address = config.get("SMU_address", "")
        smu_current_range_a = float(config.get("SMU_current_range_a", 0.0) or 0.0)
        if hasattr(gui, 'smu_type_var'):
            gui.smu_type_var.set(smu_type)
        if hasattr(gui, 'keithley_address_var'):
            gui.keithley_address_var.set(smu_address)
        if hasattr(gui, "smu_current_range_var"):
            gui.smu_current_range_var.set(smu_current_range_a)
        # Ensure address is in combobox values if using combobox
        if hasattr(gui, 'iv_address_combo') and smu_address:
            current_values = list(gui.iv_address_combo['values'])
            if smu_address not in current_values:
                gui.iv_address_combo['values'] = tuple([smu_address] + list(current_values))
        gui.SMU_type = smu_type
        gui.keithley_address = smu_address
        gui.iv_address = smu_address
        gui.smu_current_range_a = smu_current_range_a

        # Update PSU section
        psu_type = config.get("psu_type", "None")
        psu_address = config.get("psu_address", "")
        if hasattr(gui, 'psu_type_var'):
            gui.psu_type_var.set(psu_type if psu_type else "None")
        if hasattr(gui, 'psu_address_var'):
            gui.psu_address_var.set(psu_address)
        # Ensure address is in combobox values if using combobox
        if hasattr(gui, 'psu_address_combo') and psu_address:
            current_values = list(gui.psu_address_combo['values'])
            if psu_address not in current_values:
                gui.psu_address_combo['values'] = tuple([psu_address] + list(current_values))
        gui.psu_visa_address = psu_address

        # Update Temp section
        temp_type = config.get("temp_controller")
        if not temp_type or temp_type.strip() == "":
            temp_type = "None"
        temp_address = config.get("temp_address", "")
        if temp_type == "None":
            temp_address = ""
        if hasattr(gui, 'temp_type_var'):
            gui.temp_type_var.set(temp_type)
        if hasattr(gui, 'temp_address_var'):
            gui.temp_address_var.set(temp_address)
        # Ensure address is in combobox values if using combobox
        if hasattr(gui, 'temp_address_combo') and temp_address:
            current_values = list(gui.temp_address_combo['values'])
            if temp_address not in current_values:
                gui.temp_address_combo['values'] = tuple([temp_address] + list(current_values))
        gui.temp_controller_type = temp_type if temp_type != "None" else ""
        gui.temp_controller_address = temp_address
        gui.controller_type = temp_type
        gui.controller_address = temp_address

        # Update optical section
        optical_config = config.get("optical")
        if optical_config and hasattr(gui, 'optical_type_var'):
            opt_type = optical_config.get("type", "None")
            gui.optical_type_var.set(opt_type)

            # Expand optical section if configured
            if opt_type != "None" and hasattr(gui, 'optical_config_frame'):
                if hasattr(gui, 'optical_expanded_var') and not gui.optical_expanded_var.get():
                    if hasattr(gui, 'optical_toggle_button'):
                        gui.layout_builder._toggle_optical_section(self, gui.optical_config_frame, gui.optical_toggle_button)

            if opt_type == "LED":
                if hasattr(gui, 'optical_led_units_var'):
                    gui.optical_led_units_var.set(optical_config.get("units", "mA"))
                if hasattr(gui, 'optical_led_channels_var'):
                    channels = optical_config.get("channels", {})
                    channels_str = ",".join([f"{k}:{v}" for k, v in channels.items()])
                    gui.optical_led_channels_var.set(channels_str)
                limits = optical_config.get("limits", {})
                if hasattr(gui, 'optical_led_min_var'):
                    gui.optical_led_min_var.set(str(limits.get("min", "0.0")))
                if hasattr(gui, 'optical_led_max_var'):
                    gui.optical_led_max_var.set(str(limits.get("max", "30.0")))
                defaults = optical_config.get("defaults", {})
                if hasattr(gui, 'optical_led_default_channel_var'):
                    gui.optical_led_default_channel_var.set(defaults.get("channel", "380nm"))
                # Update UI
                if hasattr(gui, 'optical_config_frame'):
                    gui.layout_builder._update_optical_ui(self, gui.optical_config_frame)

            elif opt_type == "Laser":
                if hasattr(gui, 'optical_laser_driver_var'):
                    gui.optical_laser_driver_var.set(optical_config.get("driver", "Oxxius"))
                if hasattr(gui, 'optical_laser_address_var'):
                    gui.optical_laser_address_var.set(optical_config.get("address", "COM4"))
                if hasattr(gui, 'optical_laser_baud_var'):
                    gui.optical_laser_baud_var.set(str(optical_config.get("baud", "19200")))
                if hasattr(gui, 'optical_laser_units_var'):
                    gui.optical_laser_units_var.set(optical_config.get("units", "mW"))
                if hasattr(gui, 'optical_laser_wavelength_var'):
                    gui.optical_laser_wavelength_var.set(str(optical_config.get("wavelength_nm", "405")))
                limits = optical_config.get("limits", {})
                if hasattr(gui, 'optical_laser_min_var'):
                    gui.optical_laser_min_var.set(str(limits.get("min", "0.0")))
                if hasattr(gui, 'optical_laser_max_var'):
                    gui.optical_laser_max_var.set(str(limits.get("max", "10.0")))
                defaults = optical_config.get("defaults", {})
                if hasattr(gui, 'optical_laser_default_var'):
                    gui.optical_laser_default_var.set(str(defaults.get("level", 1.0)))
                # Update UI
                if hasattr(gui, 'optical_config_frame'):
                    gui.layout_builder._update_optical_ui(self, gui.optical_config_frame)
        elif hasattr(gui, 'optical_type_var'):
            gui.optical_type_var.set("None")

        # Try to create optical object; reuse existing laser connection to avoid "port in use"
        opt_cfg = config.get("optical") or {}
        opt_type = (opt_cfg.get("type") or "").strip().lower()
        existing = getattr(gui, "optical", None)
        if opt_type == "laser" and existing is not None:
            try:
                caps = getattr(existing, "capabilities", {}) or {}
                if caps.get("type") == "Laser":
                    default_mw = 1.0
                    if hasattr(gui, "optical_laser_default_var"):
                        try:
                            default_mw = float(gui.optical_laser_default_var.get())
                        except (ValueError, AttributeError):
                            pass
                    existing.set_level(default_mw, "mW")
                    _opt_status = getattr(gui, "optical_laser_status_var", None)
                    if _opt_status is not None:
                        _opt_status.set("Connected")
                    # Skip create_optical - we already have the laser
                    return
            except Exception:
                pass
        try:
            gui.optical = create_optical_from_system_config(config)
            if gui.optical is not None and hasattr(gui.optical, "set_level"):
                default_mw = 1.0
                if hasattr(gui, "optical_laser_default_var"):
                    try:
                        default_mw = float(gui.optical_laser_default_var.get())
                    except (ValueError, AttributeError):
                        pass
                gui.optical.set_level(default_mw, "mW")
            _opt_status = getattr(gui, "optical_laser_status_var", None)
            if _opt_status is not None:
                _opt_status.set("Connected" if gui.optical is not None else "Not connected")
        except Exception:
            gui.optical = None
            _opt_status = getattr(gui, "optical_laser_status_var", None)
            if _opt_status is not None:
                _opt_status.set("Not connected")


    def connect_optical_laser(self) -> None:
        """Connect to laser from current Setup tab optical settings. Sets default power to 1 mW (or Default (mW) value)."""
        gui = self.gui
        if getattr(gui, "optical_type_var", None) is None or gui.optical_type_var.get() != "Laser":
            messagebox.showwarning("Laser", "Select Optical type 'Laser' and configure Address/Baud first.")
            return
        config = self.build_optical_config_from_ui()
        if config is None:
            return
        try:
            if getattr(gui, "optical", None) is not None:
                try:
                    gui.optical.close()
                except Exception:
                    pass
                gui.optical = None
            gui.optical = create_optical_from_system_config(config)
            if gui.optical is None:
                messagebox.showerror("Laser", "Could not connect to laser. Check Address (e.g. COM4), Baud, and that the port is not in use by another app.")
            else:
                default_mw = 1.0
                if hasattr(gui, "optical_laser_default_var"):
                    try:
                        default_mw = float(gui.optical_laser_default_var.get())
                    except (ValueError, AttributeError):
                        pass
                gui.optical.set_level(default_mw, "mW")
                messagebox.showinfo("Laser", f"Connected. Default power set to {default_mw} mW.")
        except Exception as e:
            gui.optical = None
            messagebox.showerror("Laser", f"Connection failed: {e}")
        status_var = getattr(gui, "optical_laser_status_var", None)
        if status_var is not None:
            status_var.set("Connected" if gui.optical is not None else "Not connected")
        if hasattr(gui, "_refresh_led_laser_controls"):
            gui._refresh_led_laser_controls()


    def disconnect_optical_laser(self) -> None:
        """Disconnect laser and restore to manual control."""
        gui = self.gui
        if getattr(gui, "optical", None) is None:
            status_var = getattr(gui, "optical_laser_status_var", None)
            if status_var is not None:
                status_var.set("Not connected")
            return
        try:
            gui.optical.close()
        except Exception:
            pass
        gui.optical = None
        status_var = getattr(gui, "optical_laser_status_var", None)
        if status_var is not None:
            status_var.set("Not connected")
        if hasattr(gui, "_refresh_led_laser_controls"):
            gui._refresh_led_laser_controls()


    def build_optical_config_from_ui(self):
        """Build full system config dict with optical section from current UI (for connect_optical_laser)."""
        gui = self.gui
        opt_type = getattr(gui, "optical_type_var", None)
        if opt_type is None or opt_type.get() != "Laser":
            return None
        config = {"optical": {"type": "Laser"}}
        opt = config["optical"]
        opt["driver"] = getattr(gui, "optical_laser_driver_var", None) and gui.optical_laser_driver_var.get() or "Oxxius"
        opt["address"] = getattr(gui, "optical_laser_address_var", None) and gui.optical_laser_address_var.get() or "COM4"
        try:
            opt["baud"] = int(getattr(gui, "optical_laser_baud_var", None) and gui.optical_laser_baud_var.get() or 19200)
        except ValueError:
            opt["baud"] = 19200
        opt["units"] = getattr(gui, "optical_laser_units_var", None) and gui.optical_laser_units_var.get() or "mW"
        try:
            opt["wavelength_nm"] = int(getattr(gui, "optical_laser_wavelength_var", None) and gui.optical_laser_wavelength_var.get() or 405)
        except ValueError:
            opt["wavelength_nm"] = 405
        limits = {}
        try:
            limits["min"] = float(getattr(gui, "optical_laser_min_var", None) and gui.optical_laser_min_var.get() or 0.0)
        except ValueError:
            limits["min"] = 0.0
        try:
            limits["max"] = float(getattr(gui, "optical_laser_max_var", None) and gui.optical_laser_max_var.get() or 10.0)
        except ValueError:
            limits["max"] = 10.0
        opt["limits"] = limits
        defaults = {}
        try:
            defaults["level"] = float(getattr(gui, "optical_laser_default_var", None) and gui.optical_laser_default_var.get() or 1.0)
        except ValueError:
            defaults["level"] = 1.0
        opt["defaults"] = defaults
        return config


    def save_system(self) -> None:
        """Save current configuration as a new system"""
        gui = self.gui
        # Get system name from user
        system_name = simpledialog.askstring("Save System", "Enter system name:")
        if not system_name:
            return

        # Build configuration dictionary
        config = {}

        # SMU configuration
        if hasattr(gui, 'smu_type_var'):
            config["SMU Type"] = gui.smu_type_var.get()
        elif hasattr(gui, 'SMU_type'):
            config["SMU Type"] = gui.SMU_type
        else:
            config["SMU Type"] = "Keithley 2401"

        if hasattr(gui, 'keithley_address_var'):
            config["SMU_address"] = gui.keithley_address_var.get()
        elif hasattr(gui, 'keithley_address'):
            config["SMU_address"] = gui.keithley_address
        else:
            config["SMU_address"] = ""
        config["SMU_current_range_a"] = self.get_smu_current_range_a()

        # PSU configuration
        if hasattr(gui, 'psu_type_var'):
            psu_type = gui.psu_type_var.get()
            if psu_type and psu_type != "None":
                config["psu_type"] = psu_type
                if hasattr(gui, 'psu_address_var'):
                    config["psu_address"] = gui.psu_address_var.get()
                elif hasattr(gui, 'psu_visa_address'):
                    config["psu_address"] = gui.psu_visa_address
                else:
                    config["psu_address"] = ""

        # Temperature controller configuration
        if hasattr(gui, 'temp_type_var'):
            temp_type = gui.temp_type_var.get()
            if temp_type and temp_type != "None" and temp_type != "Auto-Detect":
                config["temp_controller"] = temp_type
                if hasattr(gui, 'temp_address_var'):
                    config["temp_address"] = gui.temp_address_var.get()
                elif hasattr(gui, 'temp_controller_address'):
                    config["temp_address"] = gui.temp_controller_address
                else:
                    config["temp_address"] = ""

        # Optical configuration
        if hasattr(gui, 'optical_type_var'):
            opt_type = gui.optical_type_var.get()
            if opt_type and opt_type != "None":
                optical_config = {"type": opt_type}

                if opt_type == "LED":
                    if hasattr(gui, 'optical_led_units_var'):
                        optical_config["units"] = gui.optical_led_units_var.get()
                    else:
                        optical_config["units"] = "mA"

                    # Parse channels string
                    if hasattr(gui, 'optical_led_channels_var'):
                        channels_str = gui.optical_led_channels_var.get()
                        channels = {}
                        for pair in channels_str.split(','):
                            if ':' in pair:
                                key, val = pair.strip().split(':', 1)
                                try:
                                    channels[key] = int(val)
                                except ValueError:
                                    pass
                        optical_config["channels"] = channels

                    # Limits
                    limits = {}
                    if hasattr(gui, 'optical_led_min_var'):
                        try:
                            limits["min"] = float(gui.optical_led_min_var.get())
                        except ValueError:
                            limits["min"] = 0.0
                    if hasattr(gui, 'optical_led_max_var'):
                        try:
                            limits["max"] = float(gui.optical_led_max_var.get())
                        except ValueError:
                            limits["max"] = 30.0
                    optical_config["limits"] = limits

                    # Defaults
                    defaults = {}
                    if hasattr(gui, 'optical_led_default_channel_var'):
                        defaults["channel"] = gui.optical_led_default_channel_var.get()
                    optical_config["defaults"] = defaults

                elif opt_type == "Laser":
                    if hasattr(gui, 'optical_laser_driver_var'):
                        optical_config["driver"] = gui.optical_laser_driver_var.get()
                    else:
                        optical_config["driver"] = "Oxxius"

                    if hasattr(gui, 'optical_laser_address_var'):
                        optical_config["address"] = gui.optical_laser_address_var.get()
                    else:
                        optical_config["address"] = "COM4"

                    if hasattr(gui, 'optical_laser_baud_var'):
                        try:
                            optical_config["baud"] = int(gui.optical_laser_baud_var.get())
                        except ValueError:
                            optical_config["baud"] = 19200
                    else:
                        optical_config["baud"] = 19200

                    if hasattr(gui, 'optical_laser_units_var'):
                        optical_config["units"] = gui.optical_laser_units_var.get()
                    else:
                        optical_config["units"] = "mW"

                    if hasattr(gui, 'optical_laser_wavelength_var'):
                        try:
                            optical_config["wavelength_nm"] = int(gui.optical_laser_wavelength_var.get())
                        except ValueError:
                            optical_config["wavelength_nm"] = 405
                    else:
                        optical_config["wavelength_nm"] = 405

                    # Limits
                    limits = {}
                    if hasattr(gui, 'optical_laser_min_var'):
                        try:
                            limits["min"] = float(gui.optical_laser_min_var.get())
                        except ValueError:
                            limits["min"] = 0.0
                    if hasattr(gui, 'optical_laser_max_var'):
                        try:
                            limits["max"] = float(gui.optical_laser_max_var.get())
                        except ValueError:
                            limits["max"] = 10.0
                    optical_config["limits"] = limits
                    # Defaults: default power 1 mW (or value from Default (mW) field)
                    defaults = {}
                    if hasattr(gui, 'optical_laser_default_var'):
                        try:
                            defaults["level"] = float(gui.optical_laser_default_var.get())
                        except ValueError:
                            defaults["level"] = 1.0
                    else:
                        defaults["level"] = 1.0
                    optical_config["defaults"] = defaults

                config["optical"] = optical_config

        # Load existing configs
        config_file = str(_PROJECT_ROOT / "Json_Files" / "system_configs.json")
        try:
            with open(config_file, 'r') as f:
                all_configs = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            all_configs = {}

        # Add/update system
        all_configs[system_name] = config

        # Save to file
        try:
            with open(config_file, 'w') as f:
                json.dump(all_configs, f, indent=4)

            # Update local configs
            gui.system_configs = all_configs

            # Update system combo
            if hasattr(gui, 'system_combo'):
                systems = list(all_configs.keys())
                gui.system_combo['values'] = systems
                gui.system_var.set(system_name)

            messagebox.showinfo("System Saved", f"System '{system_name}' saved successfully.")
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save system: {e}")


    def on_system_change(self, selected_system: str) -> None:
        """Update addresses when system selection changes (legacy method)"""
        gui = self.gui
        if selected_system == "Please Select System" or not selected_system:
            # Don't update addresses if no system selected
            return

        if selected_system in gui.system_configs:
            config = gui.system_configs[selected_system]

            # Update IV section
            iv_address = config.get("SMU_address", "")
            smu_current_range_a = float(config.get("SMU_current_range_a", 0.0) or 0.0)
            gui.iv_address = iv_address
            gui.keithley_address = iv_address
            gui.smu_current_range_a = smu_current_range_a

            # Update the StringVar (this should sync with combobox if bound)
            if hasattr(gui, 'keithley_address_var'):
                gui.keithley_address_var.set(iv_address)
            if hasattr(gui, "smu_current_range_var"):
                gui.smu_current_range_var.set(smu_current_range_a)

            # Also explicitly update combobox if it exists (in case it's not bound properly)
            if hasattr(gui, 'iv_address_combo'):
                # Ensure address is in combobox values first
                current_values = list(gui.iv_address_combo['values'])
                if iv_address and iv_address not in current_values:
                    gui.iv_address_combo['values'] = tuple([iv_address] + list(current_values))
                # Then set the value
                gui.iv_address_combo.set(iv_address)

            self.update_component_state("iv", iv_address)

            # Update PSU section
            psu_address = config.get("psu_address", "")
            if hasattr(gui, 'psu_address_var'):
                gui.psu_address_var.set(psu_address)
            gui.psu_visa_address = psu_address
            self.update_component_state("psu", psu_address)

            # Update Temp section
            temp_type = config.get("temp_controller")
            if not temp_type or temp_type.strip() == "":
                temp_type = "None"
            temp_address = config.get("temp_address", "")
            if temp_type == "None":
                temp_address = ""
            if hasattr(gui, 'temp_type_var'):
                gui.temp_type_var.set(temp_type)
            if hasattr(gui, 'temp_address_var'):
                gui.temp_address_var.set(temp_address)
            gui.temp_controller_address = temp_address
            self.update_component_state("temp", temp_address)

            # updater controller type
            gui.temp_controller_type = temp_type if temp_type != "None" else ""
            gui.controller_type = temp_type
            gui.controller_address = temp_address

            # smu type
            gui.SMU_type = config.get("SMU Type", "")
            print(gui.SMU_type)

            # Optical: reuse existing laser connection when config has Laser (avoids "port in use")
            opt_cfg = config.get("optical") or {}
            opt_type = (opt_cfg.get("type") or "").strip().lower()
            existing = getattr(gui, "optical", None)
            if opt_type == "laser" and existing is not None:
                try:
                    caps = getattr(existing, "capabilities", {}) or {}
                    if caps.get("type") == "Laser":
                        default_mw = 1.0
                        if hasattr(gui, "optical_laser_default_var"):
                            try:
                                default_mw = float(gui.optical_laser_default_var.get())
                            except (ValueError, AttributeError):
                                pass
                        existing.set_level(default_mw, "mW")
                        _s = getattr(gui, "optical_laser_status_var", None)
                        if _s is not None:
                            _s.set("Connected")
                        # Skip create_optical - already connected
                    else:
                        existing = None
                except Exception:
                    existing = None
            if opt_type != "laser" or existing is None:
                try:
                    gui.optical = create_optical_from_system_config(config)
                    if gui.optical is not None and hasattr(gui.optical, "set_level"):
                        default_mw = 1.0
                        if hasattr(gui, "optical_laser_default_var"):
                            try:
                                default_mw = float(gui.optical_laser_default_var.get())
                            except (ValueError, AttributeError):
                                pass
                        gui.optical.set_level(default_mw, "mW")
                    _s = getattr(gui, "optical_laser_status_var", None)
                    if _s is not None:
                        _s.set("Connected" if gui.optical is not None else "Not connected")
                except Exception:
                    gui.optical = None
                    _s = getattr(gui, "optical_laser_status_var", None)
                    if _s is not None:
                        _s.set("Not connected")


    def handle_system_selection(self, selected_system: str) -> None:
        """Callback for legacy system dropdown - only connects if a valid system is selected."""
        gui = self.gui
        # Don't auto-connect if "Please Select System" is selected
        if selected_system == "Please Select System" or not selected_system:
            self.on_system_change(selected_system)
            return

        self.on_system_change(selected_system)
        # Don't auto-connect - user must click Connect button manually
        # gui.auto_connect_current_system()  # Removed auto-connect



    def update_component_state(self, component_type: str, address: str) -> None:
        """Enable/disable and style components based on address availability"""
        gui = self.gui
        has_address = bool(address and address.strip())

        # Build components list - labels may not exist in modern layout
        if component_type == "iv":
            label = getattr(gui, "iv_label", None)
            entry = getattr(gui, "iv_address_entry", None)
            button = getattr(gui, "iv_connect_button", None)
        elif component_type == "psu":
            label = getattr(gui, "psu_label", None)
            entry = getattr(gui, "psu_address_entry", None)
            button = getattr(gui, "psu_connect_button", None)
        elif component_type == "temp":
            label = getattr(gui, "temp_label", None)
            entry = getattr(gui, "temp_address_entry", None)
            button = getattr(gui, "temp_connect_button", None)
        else:
            return

        # Skip if required components don't exist
        if entry is None or button is None:
            return

        # Update label color if it exists
        if label is not None:
            if has_address:
                label.configure(fg="black")
            else:
                label.configure(fg="grey")

        # Update entry state
        # Check if it's a ttk widget (ttk widgets don't support bg/fg options)
        # Ttk widgets have class names starting with "T" (e.g., "TEntry", "TCombobox")
        # Regular tk widgets have class names without "T" prefix (e.g., "Entry", "Button")
        widget_class = entry.winfo_class()
        is_ttk_widget = widget_class.startswith("T")

        try:
            if has_address:
                if is_ttk_widget:
                    entry.configure(state="normal")
                else:
                    entry.configure(state="normal", bg="white", fg="black")
            else:
                if is_ttk_widget:
                    entry.configure(state="disabled")
                else:
                    entry.configure(state="disabled", bg="lightgrey", fg="grey")
        except Exception:
            # Fallback: if bg/fg options aren't supported, just update state
            entry.configure(state="normal" if has_address else "disabled")

        # Update button state
        if has_address:
            button.configure(state="normal")
        else:
            button.configure(state="disabled")
