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
        try:
            if on:
                self._laser.emission_on()
            else:
                self._laser.emission_off()
        except Exception:
            pass

    def set_level(self, value: float, unit: str) -> None:
        # Clamp
        try:
            min_v = float(self._limits.get("min", -1e9))
            max_v = float(self._limits.get("max", 1e9))
            value = max(min_v, min(max_v, float(value)))
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
        try:
            self.emergency_stop()
            if hasattr(self._laser, "close"):
                self._laser.close()
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
            from Equipment.power_supply_manager import PowerSupplyManager  # local import to avoid cycles
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
            except Exception:
                return None
            port = opt.get("address", "COM3")
            baud = int(opt.get("baud", 38400))
            laser = OxxiusLaser(port=port, baud=baud)
            lx = LaserExcitation(laser=laser, units=units, wavelength_nm=opt.get("wavelength_nm"), limits=limits)
            try:
                lx.initialize()
            except Exception:
                pass
            return lx
        # Unknown laser driver for now
        return None

    if otype == "simulation":
        return SimulationExcitation(units=units or "mW")

    return None





