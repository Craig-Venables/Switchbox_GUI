"""
Quick test script to verify all imports work correctly
Run: python test_imports.py
"""

import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    print("Testing imports...")
    
    print("  - Equipment.SMU_AND_PMU.Keithley2450_TSP...", end="")
    from Equipment.SMU_AND_PMU.Keithley2450_TSP import Keithley2450_TSP
    print(" ✓")
    
    print("  - Equipment.SMU_AND_PMU.keithley2450_tsp_scripts...", end="")
    from Equipment.SMU_AND_PMU.keithley2450_tsp_scripts import Keithley2450_TSP_Scripts
    print(" ✓")
    
    print("  - Measurments.data_formats...", end="")
    from Measurments.data_formats import TSPDataFormatter, FileNamer, save_tsp_measurement
    print(" ✓")
    
    print("  - TSP_Testing_GUI...", end="")
    from TSP_Testing_GUI import TSPTestingGUI
    print(" ✓")
    
    print("\n✓ All imports successful! The standalone version is ready to use.")
    print("  Run 'python main.py' to start the GUI.")
    
except ImportError as e:
    print(f"\n❌ Import error: {e}")
    sys.exit(1)

