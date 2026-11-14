"""Keithley 4200-SCS — SMU (slow pulse, bias-timed read, cyclical IV) profile. See keithley4200_core.py."""

from .keithley4200_core import Keithley4200KXCICommon


class Keithley4200SMUSystem(Keithley4200KXCICommon):
    """SMU-based tests and optical coordination (bias-timed read)."""

    def get_system_name(self) -> str:
        return "keithley4200_smu"


class Keithley4200SMUSimSystem(Keithley4200SMUSystem):
    """In-process 4200 SMU: electrical pulse tests and bias-timed optical reads."""

    DEFAULT_ADDRESS = "SIM::4200"

    def get_system_name(self) -> str:
        return "keithley4200_smu_sim"

    def connect(self, address: str, **kwargs) -> bool:
        addr = (address or "").strip()
        if not addr.upper().startswith("SIM"):
            addr = self.DEFAULT_ADDRESS
        kwargs.setdefault("live_hiccups", True)
        kwargs.setdefault("wall_sleep", True)
        return super().connect(addr, **kwargs)
