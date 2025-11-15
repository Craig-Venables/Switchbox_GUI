"""
keithley2450_tsp_scripts - Backward Compatibility Wrapper

This file provides backward compatibility by importing from the new
keithley2450 package location.

All functionality is now provided by Equipment.SMU_AND_PMU.keithley2450.tsp_scripts.

New code should use:
    from Equipment.SMU_AND_PMU.keithley2450 import tsp_scripts as keithley2450_tsp_scripts
    # Or directly:
    from Equipment.SMU_AND_PMU.keithley2450.tsp_scripts import Keithley2450_TSP_Scripts
"""

from __future__ import annotations

# Import everything from the new location
from Equipment.SMU_AND_PMU.keithley2450.tsp_scripts import *

__all__ = ['Keithley2450_TSP_Scripts']
