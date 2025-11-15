"""
Keithley2450 - Backward Compatibility Wrapper

This file provides backward compatibility by importing from the new
keithley2450 package location.

All functionality is now provided by Equipment.SMU_AND_PMU.keithley2450.controller.

New code should use:
    from Equipment.SMU_AND_PMU.keithley2450 import Keithley2450Controller
"""

from __future__ import annotations

from Equipment.SMU_AND_PMU.keithley2450.controller import Keithley2450Controller

__all__ = ['Keithley2450Controller']
