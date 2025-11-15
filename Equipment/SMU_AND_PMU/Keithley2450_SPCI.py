"""
Keithley2450_SPCI - Backward Compatibility Wrapper

This file provides backward compatibility by importing from the new
keithley2450 package location.

All functionality is now provided by Equipment.SMU_AND_PMU.keithley2450.spci_controller.

New code should use:
    from Equipment.SMU_AND_PMU.keithley2450 import Keithley2450_SPCI
"""

from __future__ import annotations

from Equipment.SMU_AND_PMU.keithley2450.spci_controller import Keithley2450_SPCI

__all__ = ['Keithley2450_SPCI']
