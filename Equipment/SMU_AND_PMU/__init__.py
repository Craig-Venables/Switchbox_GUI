"""
SMU_AND_PMU Package - Backward Compatibility Exports

This package provides backward-compatible imports for all SMU/PMU controllers
and scripts. Files have been reorganized into subdirectories by instrument model,
but all old import paths still work.

New Recommended Imports:
    from Equipment.SMU_AND_PMU.keithley2400 import Keithley2400Controller
    from Equipment.SMU_AND_PMU.keithley2450 import Keithley2450Controller
    from Equipment.SMU_AND_PMU.keithley2450 import Keithley2450_TSP
    from Equipment.SMU_AND_PMU.keithley4200 import Keithley4200AController
    from Equipment.SMU_AND_PMU.hp4140b import HP4140BController

Old Imports (Still Work):
    from Equipment.SMU_AND_PMU.Keithley2400 import Keithley2400Controller
    from Equipment.SMU_AND_PMU.Keithley2450_TSP import Keithley2450_TSP
    etc.
"""

# Re-export all controllers for backward compatibility
from Equipment.SMU_AND_PMU.keithley2400.controller import Keithley2400Controller
from Equipment.SMU_AND_PMU.keithley2450.controller import Keithley2450Controller
from Equipment.SMU_AND_PMU.keithley2450.tsp_controller import Keithley2450_TSP
from Equipment.SMU_AND_PMU.keithley2450.tsp_sim_controller import Keithley2450_TSP_Sim
from Equipment.SMU_AND_PMU.keithley2450.spci_controller import Keithley2450_SPCI
from Equipment.SMU_AND_PMU.keithley4200.controller import (
    Keithley4200AController,
    Keithley4200A_PMUDualChannel,
)
from Equipment.SMU_AND_PMU.keithley4200.kxci_controller import Keithley4200A_KXCI
from Equipment.SMU_AND_PMU.hp4140b.controller import HP4140BController

# Re-export script collections
from Equipment.SMU_AND_PMU.keithley2450 import tsp_scripts as keithley2450_tsp_scripts
from Equipment.SMU_AND_PMU.keithley2450 import tsp_sim_scripts as keithley2450_tsp_sim_scripts
from Equipment.SMU_AND_PMU.keithley4200 import kxci_scripts as keithley4200_kxci_scripts

# Re-export script classes for convenience
try:
    from Equipment.SMU_AND_PMU.keithley2450.tsp_scripts import Keithley2450_TSP_Scripts
except ImportError:
    Keithley2450_TSP_Scripts = None

try:
    from Equipment.SMU_AND_PMU.keithley2450.tsp_sim_scripts import Keithley2450_TSP_Sim_Scripts
except ImportError:
    Keithley2450_TSP_Sim_Scripts = None

try:
    from Equipment.SMU_AND_PMU.keithley4200.kxci_scripts import Keithley4200A_KXCI_Scripts
except ImportError:
    Keithley4200A_KXCI_Scripts = None

__all__ = [
    # Controllers
    'Keithley2400Controller',
    'Keithley2450Controller',
    'Keithley2450_TSP',
    'Keithley2450_TSP_Sim',
    'Keithley2450_SPCI',
    'Keithley4200AController',
    'Keithley4200A_PMUDualChannel',
    'Keithley4200A_KXCI',
    'HP4140BController',
    # Script collections (modules)
    'keithley2450_tsp_scripts',
    'keithley2450_tsp_sim_scripts',
    'keithley4200_kxci_scripts',
    # Script classes
    'Keithley2450_TSP_Scripts',
    'Keithley2450_TSP_Sim_Scripts',
    'Keithley4200A_KXCI_Scripts',
]

