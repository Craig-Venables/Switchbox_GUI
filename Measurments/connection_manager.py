"""
Instrument connection management helpers.
=======================================

This module centralises all hardware connection logic used by the GUI so the
main window no longer needs to juggle instrument lifecycles directly.  Keeping
these routines in one place:

- makes it easier to reuse connection code from alternative front-ends (Qt,
  CLI scripts, automated tests),
- allows us to stub or mock connections cleanly for unit tests,
- reduces coupling between GUI widgets and instrument APIs.

The manager exposes explicit methods for each piece of hardware.  Each method
returns the instrument on success and raises the original exception on failure;
callers decide how to surface errors (message boxes, status banners, logs).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Optional, Any
import sys
import warnings

try:
    from Equipment.managers.iv_controller import IVControllerManager
except ImportError as exc:  # pragma: no cover - optional hardware dependency
    IVControllerManager = Any  # type: ignore
    _IVC_ERROR = exc
    warnings.warn(
        f"⚠️  WARNING: IVControllerManager could not be imported.\n"
        f"   Error: {exc}\n"
        f"   The IV Controller Manager will not be available for connecting to SMU devices.\n"
        f"   Please check that Equipment/managers/iv_controller.py exists and all required dependencies are installed.",
        ImportWarning,
        stacklevel=2
    )
    print(f"⚠️  WARNING: IVControllerManager dependency not available: {exc}")
else:
    _IVC_ERROR = None

try:
    from Equipment.PowerSupplies.Keithley2220 import Keithley2220_Powersupply
except ImportError as exc:  # pragma: no cover
    Keithley2220_Powersupply = Any  # type: ignore
    _PSU_ERROR = exc
else:
    _PSU_ERROR = None

try:
    from Equipment.managers.temperature import TemperatureControllerManager
except ImportError as exc:  # pragma: no cover
    TemperatureControllerManager = Any  # type: ignore
    _TC_ERROR = exc
else:
    _TC_ERROR = None

try:
    from Equipment.TempControllers.OxfordITC4 import OxfordITC4
except ImportError as exc:  # pragma: no cover
    OxfordITC4 = Any  # type: ignore
    _ITC_ERROR = exc
else:
    _ITC_ERROR = None


StatusLogger = Callable[[str], None]


@dataclass
class InstrumentConnectionManager:
    """Manage connections to the SMU, PSU, and temperature controllers."""

    status_logger: StatusLogger = field(default=lambda msg: None)
    keithley: Optional[IVControllerManager] = None
    psu: Optional[Keithley2220_Powersupply] = None
    itc: Optional[OxfordITC4] = None
    temp_controller: Optional[TemperatureControllerManager] = None
    flags: Dict[str, bool] = field(default_factory=lambda: {
        "keithley": False,
        "psu": False,
        "itc": False,
        "temp_controller": False,
    })

    # ------------------------------------------------------------------
    # Keithley / SMU
    # ------------------------------------------------------------------
    def connect_keithley(self, smu_type: str, address: str) -> IVControllerManager:
        """Connect to a Keithley SMU using the IV controller manager."""
        if _IVC_ERROR is not None:  # pragma: no cover - hardware dependency missing
            error_msg = (
                f"❌ ERROR: Could not connect to IV Controller Manager - dependency not available.\n\n"
                f"   Original import error: {_IVC_ERROR}\n\n"
                f"   This usually means:\n"
                f"   - Equipment/managers/iv_controller.py could not be imported\n"
                f"   - A required dependency for IV controller is missing (e.g., pymeasure, visa, etc.)\n"
                f"   - The Equipment/managers/ directory structure is incorrect\n\n"
                f"   Please check:\n"
                f"   1. That Equipment/managers/iv_controller.py exists\n"
                f"   2. That all required dependencies are installed (pip install -r requirements.txt)\n"
                f"   3. That your Python path includes the project root directory\n"
                f"   4. Try restarting Python/your IDE to clear any cached imports\n\n"
                f"   SMU Type: {smu_type}\n"
                f"   Address: {address}"
            )
            print(error_msg)
            warnings.warn(error_msg, RuntimeWarning, stacklevel=2)
            raise RuntimeError(error_msg) from _IVC_ERROR
        instrument = IVControllerManager(smu_type, address)
        try:
            connected = bool(instrument.is_connected())
        except Exception:  # Some drivers lack the helper
            connected = True
        self.keithley = instrument
        self.flags["keithley"] = connected
        self.status_logger(f"Keithley connected: {smu_type} @ {address}")
        return instrument

    # ------------------------------------------------------------------
    # PSU
    # ------------------------------------------------------------------
    def connect_psu(self, visa_address: str) -> Keithley2220_Powersupply:
        """Connect to the Keithley PSU (visa address)."""
        if _PSU_ERROR is not None:  # pragma: no cover
            raise RuntimeError("PSU dependency not available") from _PSU_ERROR
        psu = Keithley2220_Powersupply(visa_address)
        self.psu = psu
        self.flags["psu"] = True
        self.status_logger(f"PSU connected: {visa_address}")
        return psu

    # ------------------------------------------------------------------
    # Oxford ITC4 (direct temperature controller)
    # ------------------------------------------------------------------
    def connect_oxford_itc4(self, address: str) -> OxfordITC4:
        """Connect to an Oxford ITC4 temperature controller."""
        if _ITC_ERROR is not None:  # pragma: no cover
            raise RuntimeError("Oxford ITC4 dependency not available") from _ITC_ERROR
        itc = OxfordITC4(port=address)
        self.itc = itc
        self.flags["itc"] = True
        self.status_logger(f"ITC4 connected: {address}")
        return itc

    # ------------------------------------------------------------------
    # Temperature controller manager abstraction
    # ------------------------------------------------------------------
    def create_temperature_controller(
        self,
        *,
        auto_detect: bool,
        controller_type: Optional[str] = None,
        address: Optional[str] = None,
    ) -> TemperatureControllerManager:
        """Create or recreate the temperature controller abstraction."""
        if _TC_ERROR is not None:  # pragma: no cover
            raise RuntimeError("TemperatureControllerManager dependency not available") from _TC_ERROR
        controller = TemperatureControllerManager(
            auto_detect=auto_detect,
            controller_type=controller_type,
            address=address,
        )
        self.temp_controller = controller
        self.flags["temp_controller"] = controller.is_connected()
        if self.flags["temp_controller"]:
            info = controller.get_controller_info()
            self.status_logger(
                f"Temp controller connected: {info.get('type', 'unknown')} @ {info.get('address', 'n/a')}"
            )
        else:
            self.status_logger("Temp controller not connected")
        return controller

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------
    def is_connected(self, name: str) -> bool:
        return bool(self.flags.get(name, False))

    def get_temperature_info(self) -> Optional[Dict[str, str]]:
        if self.temp_controller and self.temp_controller.is_connected():
            return self.temp_controller.get_controller_info()
        return None

    def cleanup(self) -> None:
        """Best-effort shutdown of all known instruments."""
        for inst in [self.keithley, self.psu, self.itc, self.temp_controller]:
            try:
                if hasattr(inst, "close"):
                    inst.close()
            except Exception:
                pass


def _self_test() -> Dict[str, bool]:
    """Simple diagnostic used by ``python -m Measurments.connection_manager``."""
    manager = InstrumentConnectionManager()
    return {name: manager.is_connected(name) for name in manager.flags}


if __name__ == "__main__":  # pragma: no cover - manual diagnostic
    import json

    print(json.dumps(_self_test(), indent=2))
