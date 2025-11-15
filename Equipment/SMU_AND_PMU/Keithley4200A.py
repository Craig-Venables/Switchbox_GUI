"""
Keithley4200A - Backward Compatibility Wrapper

This file provides backward compatibility by importing from the new
keithley4200 package location.

All functionality is now provided by Equipment.SMU_AND_PMU.keithley4200.controller.

New code should use:
    from Equipment.SMU_AND_PMU.keithley4200 import Keithley4200AController, Keithley4200A_PMUDualChannel
"""

from __future__ import annotations

from Equipment.SMU_AND_PMU.keithley4200.controller import (
    Keithley4200AController,
    Keithley4200A_PMUDualChannel,
)

__all__ = ['Keithley4200AController', 'Keithley4200A_PMUDualChannel']
