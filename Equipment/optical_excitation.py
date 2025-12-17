from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple, Union


class OpticalExcitation:
    """Abstract optical excitation controller.

    All concrete implementations must implement the methods below.
    Units are adapter-specific; callers should pass the unit explicitly.
    """

    def initialize(self) -> None:
        raise NotImplementedError

    def select_channel(self, name_or_wavelength: Union[str, int]) -> None:
        raise NotImplementedError

    def set_enabled(self, on: bool) -> None:
        raise NotImplementedError

    def set_level(self, value: float, unit: str) -> None:
        raise NotImplementedError

    def emergency_stop(self) -> None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError

    @property
    def capabilities(self) -> Dict[str, Any]:
        """Return capability metadata and current selection/state.

        Keys:
          - type: "LED" | "Laser" | "Simulation"
          - units: default unit (e.g. "mA" or "mW")
          - supports_wavelength: bool
          - supports_absolute_power: bool
          - limits: {min, max, ramp_rate}
          - selection: current channel/wavelength
        """
        return {}


class LEDExcitation(OpticalExcitation):
    """LED optical excitation backed by a bench PSU via PowerSupplyManager.

    Expects units in mA or V depending on configuration. Default: mA on a given
    PSU channel mapped from a human-readable channel name (e.g., "380nm").
    """

    def __init__(self, *, psu_manager: Any, channels: Dict[str, int], units: str = "mA",
                 limits: Optional[Dict[str, float]] = None, default_channel: Optional[str] = None) -> None:
        self._psu = psu_manager
        self._channels = dict(channels or {})
        self._units = units or "mA"
        self._limits = dict(limits or {})
        self._selection: Optional[str] = default_channel if default_channel in self._channels else None

    def initialize(self) -> None:
        # Ensure channel is disabled at init for safety
        try:
            if self._selection is not None:
                ch = self._channels[self._selection]
                self._psu.disable(ch)
        except Exception:
            pass

    def select_channel(self, name_or_wavelength: Union[str, int]) -> None:
        name = str(name_or_wavelength)
        if name not in self._channels:
            raise ValueError(f"Unknown LED channel: {name}")
        self._selection = name

    def set_enabled(self, on: bool) -> None:
        if self._selection is None:
            raise RuntimeError("LED channel not selected")
        ch = self._channels[self._selection]
        try:
            if on:
                self._psu.enable(ch)
            else:
                self._psu.disable(ch)
        except Exception:
            pass

    def set_level(self, value: float, unit: str) -> None:
        if self._selection is None:
            raise RuntimeError("LED channel not selected")
        ch = self._channels[self._selection]
        # Clamp to limits if provided
        try:
            min_v = float(self._limits.get("min", -1e9))
            max_v = float(self._limits.get("max", 1e9))
            value = max(min_v, min(max_v, float(value)))
        except Exception:
            pass

        unit = (unit or self._units).lower()
        try:
            if unit == "ma":
                self._psu.set_current(ch, float(value) / 1000.0)
            elif unit == "a":
                self._psu.set_current(ch, float(value))
            elif unit == "v":
                self._psu.set_voltage(ch, float(value))
            else:
                # Default assume mA
                self._psu.set_current(ch, float(value) / 1000.0)
        except Exception:
            pass

    def emergency_stop(self) -> None:
        try:
            # Best-effort disable for all configured channels
            for ch in self._channels.values():
                try:
                    self._psu.disable(ch)
                except Exception:
                    pass
        except Exception:
            pass

    def close(self) -> None:
        try:
            self.emergency_stop()
            if hasattr(self._psu, "close"):
                self._psu.close()
        except Exception:
            pass

    @property
    def capabilities(self) -> Dict[str, Any]:
        return {
            "type": "LED",
            "units": self._units,
            "supports_wavelength": False,
            "supports_absolute_power": False,
            "limits": self._limits,
            "selection": self._selection,
            "available_channels": list(self._channels.keys()),
        }


class LaserExcitation(OpticalExcitation):
    """Laser optical excitation backed by a vendor controller (e.g., Oxxius)."""

    def __init__(self, *, laser: Any, units: str = "mW",
                 wavelength_nm: Optional[int] = None, limits: Optional[Dict[str, float]] = None) -> None:
        self._laser = laser
        self._units = units or "mW"
        self._wavelength_nm = wavelength_nm
        self._limits = dict(limits or {})

    def initialize(self) -> None:
        try:
            # Ensure emission is off first
            self._laser.emission_off()
        except Exception:
            pass
        # Some lasers require a delay before first enable
        time.sleep(0.2)

    def select_channel(self, name_or_wavelength: Union[str, int]) -> None:
        # Fixed wavelength for now; accept but do nothing
        try:
            self._wavelength_nm = int(name_or_wavelength)
        except Exception:
            pass

    def set_enabled(self, on: bool) -> None:
        """Enable/disable laser emission following proper sequence.
        
        When turning ON:
        1. Set to power control mode (APC 1)
        2. Set to digital control (AM 0, DM 0)
        3. Turn emission ON
        (Power should be set before enabling via set_level)
        
        When turning OFF:
        1. Turn emission OFF
        2. Enable analog modulation (AM 1) for manual control
        3. Set power to 100 mW for manual control
        """
        try:
            if on:
                # Turn ON sequence
                self._laser.send_command("APC 1")
                time.sleep(0.1)
                self._laser.send_command("AM 0")
                time.sleep(0.1)
                self._laser.send_command("DM 0")
                time.sleep(0.1)
                self._laser.emission_on()
            else:
                # Turn OFF sequence - restore to manual control
                self._laser.emission_off()
                time.sleep(0.1)
                self._laser.send_command("AM 1")
                time.sleep(0.1)
                self._laser.set_power(100.0)
                time.sleep(0.1)
        except Exception:
            pass

    def set_level(self, value: float, unit: str) -> None:
        """Set laser power level.
        
        Should be called before set_enabled(True) for best results.
        If laser is already on, power will be updated immediately.
        """
        # Clamp to limits
        try:
            min_v = float(self._limits.get("min", -1e9))
            max_v = float(self._limits.get("max", 1e9))
            value = max(min_v, min(max_v, float(value)))
        except Exception:
            pass
        
        # Ensure we're in power control mode before setting power
        try:
            self._laser.send_command("APC 1")
            time.sleep(0.05)
        except Exception:
            pass
        
        unit = (unit or self._units).lower()
        try:
            if unit == "mw":
                self._laser.set_power(float(value))
            elif unit == "ma" or unit == "a":
                # fall back to current mode if supported
                self._laser.set_current(float(value) if unit == "a" else float(value) / 1000.0)
            else:
                self._laser.set_power(float(value))
        except Exception:
            pass

    def emergency_stop(self) -> None:
        try:
            self._laser.emission_off()
        except Exception:
            pass

    def close(self) -> None:
        """Close laser connection and restore to manual control mode."""
        try:
            # Restore to manual control mode before closing
            try:
                self._laser.emission_on()  # Ensure emission is ON
                time.sleep(0.1)
                self._laser.send_command("APC 1")
                time.sleep(0.1)
                self._laser.send_command("AM 1")  # Enable analog modulation
                time.sleep(0.1)
                self._laser.send_command("DM 0")
                time.sleep(0.1)
                self._laser.set_power(100.0)  # Set to 100 mW for manual control
                time.sleep(0.1)
            except Exception:
                pass
            # Use laser's close method which also restores to manual control
            if hasattr(self._laser, "close"):
                self._laser.close(restore_to_manual_control=True)
        except Exception:
            pass

    @property
    def capabilities(self) -> Dict[str, Any]:
        return {
            "type": "Laser",
            "units": self._units,
            "supports_wavelength": False,
            "supports_absolute_power": True,
            "limits": self._limits,
            "selection": self._wavelength_nm,
        }


class SimulationExcitation(OpticalExcitation):
    def __init__(self, *, units: str = "mW") -> None:
        self._units = units
        self._on = False
        self._selection: Optional[Union[str, int]] = None

    def initialize(self) -> None:
        self._on = False

    def select_channel(self, name_or_wavelength: Union[str, int]) -> None:
        self._selection = name_or_wavelength

    def set_enabled(self, on: bool) -> None:
        self._on = bool(on)

    def set_level(self, value: float, unit: str) -> None:
        _ = (value, unit)

    def emergency_stop(self) -> None:
        self._on = False

    def close(self) -> None:
        self._on = False

    @property
    def capabilities(self) -> Dict[str, Any]:
        return {
            "type": "Simulation",
            "units": self._units,
            "supports_wavelength": True,
            "supports_absolute_power": True,
            "limits": {"min": 0.0, "max": 1000.0},
            "selection": self._selection,
        }


def create_optical_from_system_config(system_cfg: Dict[str, Any]) -> Optional[OpticalExcitation]:
    """Factory: build an OpticalExcitation from a system config block.

    Expected structure:
      system_cfg["optical"] = {
        "type": "LED" | "Laser",
        "units": "mA" | "mW" | "V",
        # LED
        "channels": {"380nm": 1, ...},
        "limits": {"min": 0.0, "max": 30.0},
        # Laser
        "driver": "Oxxius",
        "address": "COM3",
        "wavelength_nm": 405,
        "limits": {"min": 0.0, "max": 10.0}
      }
    """
    opt = system_cfg.get("optical") if isinstance(system_cfg, dict) else None
    if not isinstance(opt, dict):
        return None

    otype = str(opt.get("type", "")).strip().lower()
    units = str(opt.get("units", "")).strip() or ("mA" if otype == "led" else "mW")
    limits = opt.get("limits") or {}

    if otype == "led":
        # Build PSU manager from config
        try:
            from Equipment.managers.power_supply import PowerSupplyManager  # local import to avoid cycles
        except Exception as _:
            return None
        psu_type = system_cfg.get("psu_type", "Keithley 2220")
        psu_addr = system_cfg.get("psu_address")
        if not psu_addr:
            return None
        psu = PowerSupplyManager(psu_type, psu_addr)
        channels = opt.get("channels") or {}
        default_channel = (opt.get("defaults") or {}).get("channel")
        led = LEDExcitation(psu_manager=psu, channels=channels, units=units, limits=limits,
                            default_channel=default_channel)
        try:
            led.initialize()
        except Exception:
            pass
        return led

    if otype == "laser":
        driver = str(opt.get("driver", "Oxxius")).strip()
        if driver.lower() == "oxxius":
            try:
                from Equipment.Laser_Controller.oxxius import OxxiusLaser  # type: ignore
            except Exception as e:
                print(f"[OPTICAL] ERROR: Could not import OxxiusLaser: {e}")
                return None
            port = opt.get("address", "COM4")  # Default to COM4 (common for this system)
            baud = int(opt.get("baud", 19200))  # Default to 19200 (common for this system)
            print(f"[OPTICAL] Creating laser connection: port={port}, baud={baud}")
            
            # Try to create connection, with retry logic for port conflicts
            laser = None
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    laser = OxxiusLaser(port=port, baud=baud)
                    print(f"[OPTICAL] Laser connection created successfully")
                    break  # Success, exit retry loop
                except Exception as e:
                    error_msg = str(e)
                    if ("Access is denied" in error_msg or "PermissionError" in error_msg) and attempt < max_retries - 1:
                        # Port is in use, wait a bit and retry
                        print(f"[OPTICAL] WARNING: Port {port} appears to be in use (attempt {attempt + 1}/{max_retries}). Waiting...")
                        import time
                        time.sleep(1.0)  # Wait 1 second for port to be released
                        continue
                    else:
                        # Final attempt failed or different error
                        if "Access is denied" in error_msg or "PermissionError" in error_msg:
                            print(f"[OPTICAL] ERROR: Port {port} is already in use by another process.")
                            print(f"[OPTICAL] This may happen if:")
                            print(f"[OPTICAL]   - The laser is already connected in another window (e.g., Motor Control GUI)")
                            print(f"[OPTICAL]   - A previous connection wasn't properly closed")
                            print(f"[OPTICAL] Solution: Close other laser connections or wait a moment and reload the system.")
                        else:
                            print(f"[OPTICAL] ERROR: Failed to connect to laser at {port}: {e}")
                        import traceback
                        traceback.print_exc()
                        return None
            
            if laser is None:
                return None
            
            # Test connection by querying ID
            try:
                idn = laser.idn()
                print(f"[OPTICAL] Laser ID: {idn}")
            except Exception as e:
                print(f"[OPTICAL] WARNING: Could not query laser ID: {e}")
            lx = LaserExcitation(laser=laser, units=units, wavelength_nm=opt.get("wavelength_nm"), limits=limits)
            try:
                lx.initialize()
                print(f"[OPTICAL] Laser initialized successfully")
            except Exception as e:
                print(f"[OPTICAL] WARNING: Laser initialization had issues: {e}")
            return lx
        # Unknown laser driver for now
        print(f"[OPTICAL] WARNING: Unknown laser driver: {driver}")
        return None

    if otype == "simulation":
        return SimulationExcitation(units=units or "mW")

    return None





