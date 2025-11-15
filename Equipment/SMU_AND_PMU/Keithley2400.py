"""
Keithley2400 - Backward Compatibility Wrapper

This file provides backward compatibility by importing from the new
keithley2400 package location.

All functionality is now provided by Equipment.SMU_AND_PMU.keithley2400.controller.

New code should use:
    from Equipment.SMU_AND_PMU.keithley2400 import Keithley2400Controller
"""

from __future__ import annotations

from Equipment.SMU_AND_PMU.keithley2400.controller import Keithley2400Controller

__all__ = ['Keithley2400Controller']
