"""
Equipment Module
=================

Unified interface for instrument drivers and managers.

This module provides manager classes that unify different instrument drivers
behind common APIs, making it easy to switch between different equipment
types without changing calling code.

Structure:
----------
- managers: Unified manager interfaces (IV controller, temperature, power supply, etc.)
- smu_pmu: Source/Measure Unit drivers (Keithley 2400, 2450, 4200A, etc.)
- temperature_controllers: Temperature controller drivers
- power_supplies: Power supply drivers
- cameras: Camera drivers
- oscilloscopes: Oscilloscope drivers
- ammeters: Ammeter drivers
- function_generators: Function generator drivers
- lasers: Laser drivers
- multiplexers: Multiplexer drivers
- optical: Optical excitation interfaces
- arduino: Arduino integrations
- motor_control: Motor control interfaces

Usage:
------
    from Equipment import IVControllerManager
    from Equipment import TemperatureControllerManager
    
    # Initialize managers
    iv_manager = IVControllerManager("Keithley 2450", "USB0::...")
    temp_manager = TemperatureControllerManager(auto_detect=True)

Author: Measurement System Team
Created: 2024
Last Modified: 2025-01-XX
"""

__all__ = [
    # Managers
    "IVControllerManager",
    "TemperatureControllerManager",
    "PowerSupplyManager",
    "MultiplexerManager",
    "CameraManager",
    "OscilloscopeManager",
    "AmmeterControllerManager",
    "FunctionGeneratorManager",
    "LaserManager",
]

# Managers
# Import with graceful fallback - set to None if imports fail so application can continue
# This allows the application to start even if some managers are unavailable
# Each manager is imported separately so one failure doesn't block others
# Use relative imports to avoid circular import issues when Equipment is being initialized
try:
    from .managers.iv_controller import IVControllerManager
except ImportError as e:
    IVControllerManager = None  # type: ignore
    import warnings
    warnings.warn(f"IVControllerManager not available: {e}", ImportWarning)

try:
    from .managers.temperature import TemperatureControllerManager
except ImportError as e:
    TemperatureControllerManager = None  # type: ignore
    import warnings
    warnings.warn(f"TemperatureControllerManager not available: {e}", ImportWarning)

try:
    from .managers.power_supply import PowerSupplyManager
except ImportError as e:
    PowerSupplyManager = None  # type: ignore
    import warnings
    warnings.warn(f"PowerSupplyManager not available: {e}", ImportWarning)

try:
    from .managers.multiplexer import MultiplexerManager
except ImportError as e:
    MultiplexerManager = None  # type: ignore
    import warnings
    warnings.warn(f"MultiplexerManager not available: {e}", ImportWarning)

try:
    from .managers.camera import CameraManager
except ImportError as e:
    CameraManager = None  # type: ignore
    import warnings
    warnings.warn(f"CameraManager not available: {e}", ImportWarning)

try:
    from .managers.oscilloscope import OscilloscopeManager
except ImportError as e:
    OscilloscopeManager = None  # type: ignore
    import warnings
    warnings.warn(f"OscilloscopeManager not available: {e}", ImportWarning)

try:
    from .managers.ammeter import AmmeterControllerManager
except ImportError as e:
    AmmeterControllerManager = None  # type: ignore
    import warnings
    warnings.warn(f"AmmeterControllerManager not available: {e}", ImportWarning)

try:
    from .managers.function_generator import FunctionGeneratorManager
except ImportError as e:
    FunctionGeneratorManager = None  # type: ignore
    import warnings
    warnings.warn(f"FunctionGeneratorManager not available: {e}", ImportWarning)

try:
    from .managers.laser import LaserManager
except ImportError as e:
    LaserManager = None  # type: ignore
    import warnings
    warnings.warn(f"LaserManager not available: {e}", ImportWarning)
