"""
Keithley4200A_KXCI - Backward Compatibility Wrapper

This file provides backward compatibility by importing from the new
keithley4200 package location.

All functionality is now provided by Equipment.SMU_AND_PMU.keithley4200.kxci_controller.

New code should use:
    from Equipment.SMU_AND_PMU.keithley4200 import Keithley4200A_KXCI
"""

from __future__ import annotations

from Equipment.SMU_AND_PMU.keithley4200.kxci_controller import Keithley4200A_KXCI

__all__ = ['Keithley4200A_KXCI']
