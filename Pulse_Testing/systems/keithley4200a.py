"""
Keithley 4200A — legacy alias (backward compatibility)
======================================================

Historically a single adapter; implementation lives in keithley4200_core.py.
`Keithley4200ASystem` keeps the old class name and reports system id `keithley4200a`
for saved configs and scripts.

Prefer: Keithley4200PMUSystem (keithley4200_pmu) or Keithley4200SMUSystem (keithley4200_smu).
"""

from .keithley4200_pmu import Keithley4200PMUSystem


class Keithley4200ASystem(Keithley4200PMUSystem):
    """Same implementation as PMU profile; get_system_name returns legacy id."""

    def get_system_name(self) -> str:
        return "keithley4200a"
