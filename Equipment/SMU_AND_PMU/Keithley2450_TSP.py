"""
Keithley2450_TSP - Backward Compatibility Wrapper

This file provides backward compatibility by importing from the new
keithley2450 package location.

All functionality is now provided by Equipment.SMU_AND_PMU.keithley2450.tsp_controller.

New code should use:
    from Equipment.SMU_AND_PMU.keithley2450 import Keithley2450_TSP
"""

from __future__ import annotations

from Equipment.SMU_AND_PMU.keithley2450.tsp_controller import Keithley2450_TSP

__all__ = ['Keithley2450_TSP']
