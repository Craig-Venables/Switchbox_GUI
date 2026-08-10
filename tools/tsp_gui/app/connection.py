"""USB TSP connection for Keithley 2450 (hardware or sim)."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from .config import (
    DEFAULT_TERMINALS,
    DEFAULT_TIMEOUT_MS,
    DEFAULT_USB_ADDRESS,
    SIM_ADDRESS,
    USB_MODEL_HINT,
    USB_VENDOR_HINT,
)
from .sim_scripts import SimpleSimScripts
from .tsp_imports import load_tsp_stack


def list_usb_resources(include_sim: bool = True) -> List[str]:
    """List VISA USB resources, preferring Keithley 2450 IDs."""
    devices: List[str] = []
    try:
        import pyvisa

        rm = pyvisa.ResourceManager()
        for res in rm.list_resources():
            if not str(res).upper().startswith("USB"):
                continue
            devices.append(str(res))
    except Exception:
        pass

    preferred = [
        d for d in devices
        if USB_VENDOR_HINT.lower() in d.lower() or USB_MODEL_HINT.lower() in d.lower()
    ]
    others = [d for d in devices if d not in preferred]
    ordered = preferred + others

    if include_sim and SIM_ADDRESS not in ordered:
        ordered.append(SIM_ADDRESS)
    if not ordered:
        ordered = [DEFAULT_USB_ADDRESS, SIM_ADDRESS] if include_sim else [DEFAULT_USB_ADDRESS]
    return ordered


def is_usb_or_sim_address(address: str) -> bool:
    a = (address or "").strip().upper()
    return a.startswith("USB") or a.startswith("SIM::")


class Keithley2450TSPSystem:
    """Minimal 2450 adapter: TSP scripts + optical bias/measure API."""

    def __init__(self, sim: bool = False) -> None:
        self._sim = sim
        self.tsp_controller = None
        self.test_scripts = None
        self._connected = False

    def connect(self, address: str, terminals: str = "front", timeout: int = 10000, **kwargs) -> bool:
        Keithley2450_TSP, Keithley2450_TSP_Scripts, Keithley2450_TSP_Sim = load_tsp_stack()
        if self._sim or str(address).upper().startswith("SIM::"):
            self.tsp_controller = Keithley2450_TSP_Sim(address, timeout=timeout, terminals=terminals)
            # Local sim scripts avoid MeasurementService / pymeasure dependency
            self.test_scripts = SimpleSimScripts(self.tsp_controller)
        else:
            self.tsp_controller = Keithley2450_TSP(address, timeout=timeout, terminals=terminals)
            self.test_scripts = Keithley2450_TSP_Scripts(self.tsp_controller)
        self._connected = True
        return True

    def disconnect(self) -> None:
        if self.tsp_controller is not None:
            try:
                self.tsp_controller.close()
            except Exception:
                pass
        self.tsp_controller = None
        self.test_scripts = None
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected and self.tsp_controller is not None and self.test_scripts is not None

    def get_idn(self) -> str:
        if self.tsp_controller:
            return self.tsp_controller.get_idn()
        return "Not Connected"

    def get_system_name(self) -> str:
        return "keithley2450_sim" if self._sim else "keithley2450"

    def __getattr__(self, name: str):
        # Delegate unknown attributes/methods to test_scripts (pulse tests)
        if name.startswith("_"):
            raise AttributeError(name)
        scripts = self.test_scripts
        if scripts is None:
            raise RuntimeError("Not connected to device")
        attr = getattr(scripts, name, None)
        if attr is None:
            raise AttributeError(f"No test method '{name}'")
        return attr

    # Optical API
    def source_voltage_for_optical(self, voltage: float, current_limit: float) -> None:
        if not self.tsp_controller:
            raise RuntimeError("Not connected to device")
        self.tsp_controller.set_voltage(voltage, current_limit)
        try:
            self.tsp_controller.device.write("smu.measure.func = smu.FUNC_DC_CURRENT")
            self.tsp_controller.device.write("smu.measure.nplc = 0.01")
            self.tsp_controller.device.write("smu.measure.autozero.enable = smu.OFF")
            time.sleep(0.02)
        except Exception:
            pass

    def measure_current_once(self) -> Tuple[float, float]:
        if not self.tsp_controller:
            raise RuntimeError("Not connected to device")
        t = time.perf_counter()
        i = self.tsp_controller.measure_current()
        return (t, i if i is not None else 0.0)

    def source_output_off(self) -> None:
        if self.tsp_controller:
            try:
                self.tsp_controller.enable_output(False)
            except Exception:
                pass


class SMUConnection:
    """Owns a Keithley2450TSPSystem for TSP pulse + optical APIs."""

    def __init__(self) -> None:
        self.system: Optional[Keithley2450TSPSystem] = None
        self.address: Optional[str] = None
        self.terminals: str = DEFAULT_TERMINALS
        self._connected = False

    @property
    def connected(self) -> bool:
        return bool(self._connected and self.system is not None and self.system.is_connected())

    def connect(
        self,
        address: str,
        terminals: str = DEFAULT_TERMINALS,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
    ) -> Tuple[bool, str]:
        address = (address or "").strip()
        if not address:
            return False, "No VISA address provided."
        if not is_usb_or_sim_address(address):
            return False, "This GUI is USB-only. Use a USB0::... VISA address (or SIM::KEITHLEY2450)."

        self.disconnect()
        terminals = (terminals or "front").lower()
        if terminals not in ("front", "rear"):
            terminals = "front"

        try:
            is_sim = address.upper().startswith("SIM::")
            system = Keithley2450TSPSystem(sim=is_sim)
            system.connect(address, terminals=terminals, timeout=timeout_ms)
            idn = system.get_idn()
            self.system = system
            self.address = address
            self.terminals = terminals
            self._connected = True
            return True, f"Connected: {idn}"
        except Exception as e:
            self.system = None
            self._connected = False
            return False, f"Connect failed: {e}"

    def disconnect(self) -> None:
        if self.system is not None:
            try:
                self.system.disconnect()
            except Exception:
                pass
        self.system = None
        self._connected = False

    def get_idn(self) -> str:
        if not self.connected:
            return "Not connected"
        try:
            return self.system.get_idn()
        except Exception as e:
            return f"IDN error: {e}"
