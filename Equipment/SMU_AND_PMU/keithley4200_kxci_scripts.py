"""
keithley4200_kxci_scripts - Backward Compatibility Wrapper

This file provides backward compatibility by importing from the new
keithley4200 package location.

All functionality is now provided by Equipment.SMU_AND_PMU.keithley4200.kxci_scripts.

New code should use:
    from Equipment.SMU_AND_PMU.keithley4200 import kxci_scripts as keithley4200_kxci_scripts
    # Or directly:
    from Equipment.SMU_AND_PMU.keithley4200.kxci_scripts import Keithley4200A_KXCI_Scripts
"""

from __future__ import annotations

# Import everything from the new location
from Equipment.SMU_AND_PMU.keithley4200.kxci_scripts import *

__all__ = ['Keithley4200A_KXCI_Scripts']
