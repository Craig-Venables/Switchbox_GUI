"""Keithley 4200-SCS — PMU (fast interleaved) profile. See keithley4200_core.py."""

from .keithley4200_core import Keithley4200KXCICommon


class Keithley4200PMUSystem(Keithley4200KXCICommon):
    """Fast pulse / PMU path; laser via PMU for laser_and_read."""

    def get_system_name(self) -> str:
        return "keithley4200_pmu"
