"""Keithley 4200-SCS — SMU (slow pulse, bias-timed read, cyclical IV) profile. See keithley4200_core.py."""

from .keithley4200_core import Keithley4200KXCICommon


class Keithley4200SMUSystem(Keithley4200KXCICommon):
    """SMU-based tests and optical coordination (bias-timed read)."""

    def get_system_name(self) -> str:
        return "keithley4200_smu"
