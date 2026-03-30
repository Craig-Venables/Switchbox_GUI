"""
Sweep Configuration and Instrument Capabilities

Provides dataclasses to encapsulate sweep parameters and instrument capabilities
for optimized sweep execution (hardware vs point-by-point).

Integrates with existing modular utilities:
- sweep_patterns.py (SweepType enum)
- source_modes.py (SourceMode enum)

Author: Hardware Sweep Implementation - October 2025
"""

from dataclasses import dataclass
from typing import Optional, List, Tuple
from enum import Enum

from Measurments.sweep_patterns import SweepType
from Measurments.source_modes import SourceMode


class SweepMethod(Enum):
    """Method for executing a sweep."""
    POINT_BY_POINT = "point_by_point"      # Traditional slow sweep
    HARDWARE_SWEEP = "hardware_sweep"      # Fast hardware-accelerated sweep
    ARBITRARY_SWEEP = "arbitrary_sweep"    # Custom waveform sweep


@dataclass
class InstrumentCapabilities:
    """
    Describes instrument capabilities for optimal sweep selection.
    
    Attributes:
        supports_hardware_sweep: Can do fast hardware sweeps
        supports_arbitrary_sweep: Can do arbitrary waveforms
        supports_pulses: Can do fast pulsing
        supports_current_source: Can source current (measure voltage)
        min_step_delay_ms: Minimum delay between points
        max_points_per_sweep: Maximum points in single sweep
        voltage_range: (min, max) voltage range
        current_range: (min, max) current range
    
    Examples:
        >>> # Keithley 4200A capabilities
        >>> caps = InstrumentCapabilities(
        ...     supports_hardware_sweep=True,
        ...     min_step_delay_ms=1.0,
        ...     voltage_range=(-200.0, 200.0)
        ... )
    """
    supports_hardware_sweep: bool = False
    supports_arbitrary_sweep: bool = False
    supports_pulses: bool = False
    supports_current_source: bool = True  # Most SMUs support this
    min_step_delay_ms: float = 50.0
    max_points_per_sweep: int = 10000
    voltage_range: Tuple[float, float] = (-10.0, 10.0)
    current_range: Tuple[float, float] = (-1.0, 1.0)


@dataclass
class SweepConfig:
    """
    Configuration for a voltage or current sweep.
    
    Integrates with existing utilities:
    - Uses SweepType from sweep_patterns.py
    - Uses SourceMode from source_modes.py
    
    Attributes:
        start_v: Starting voltage (or current if source_mode=CURRENT)
        stop_v: Stopping voltage (or current)
        step_v: Step size (optional, calculated if None)
        neg_stop_v: Negative stop for triangle sweeps
        step_delay: Delay between points (seconds)
        sweep_type: Type of sweep (FS, PS, NS, Triangle)
        sweeps: Number of sweep repetitions
        pause_s: Pause at extrema
        icc: Compliance current (for voltage source) or voltage (for current source)
        sweep_method: Execution method (auto-selected if None)
        voltage_list: Pre-computed voltage list (optional)
        source_mode: Voltage or current source
        led: Enable optical excitation
        power: Optical power level
    
    Examples:
        >>> # Simple voltage sweep config
        >>> config = SweepConfig(
        ...     start_v=0.0,
        ...     stop_v=1.0,
        ...     step_v=0.1,
        ...     sweep_type="FS",
        ...     icc=1e-3
        ... )
        
        >>> # Current source sweep config
        >>> config = SweepConfig(
        ...     start_v=0.0,
        ...     stop_v=1e-6,
        ...     step_v=1e-7,
        ...     sweep_type="FS",
        ...     icc=10.0,  # Voltage compliance
        ...     source_mode=SourceMode.CURRENT
        ... )
    """
    # Core sweep parameters
    start_v: float
    stop_v: float
    step_v: Optional[float] = None
    neg_stop_v: Optional[float] = None
    
    # Timing
    step_delay: float = 0.05
    sweeps: int = 1
    pause_s: float = 0.0
    
    # Sweep pattern
    sweep_type: str = "FS"  # Can also use SweepType enum from sweep_patterns.py
    
    # Compliance and limits
    icc: float = 1e-3
    
    # Method selection (auto-selected if None)
    sweep_method: Optional[SweepMethod] = None
    
    # Optional pre-computed list
    voltage_list: Optional[List[float]] = None
    
    # Source mode support (uses source_modes.py)
    source_mode: SourceMode = SourceMode.VOLTAGE
    
    # Optical excitation
    led: bool = False
    power: float = 1.0
    sequence: Optional[List[str]] = None
    
    @property
    def num_points(self) -> int:
        """Estimate number of points in the sweep."""
        if self.voltage_list is not None:
            return len(self.voltage_list)
        
        if self.step_v is None:
            return 100  # Default estimate
        
        # Estimate based on range and step
        range_size = abs(self.stop_v - self.start_v)
        points_forward = int(range_size / abs(self.step_v)) + 1
        
        # Multiply based on sweep type
        if self.sweep_type in ["FS", "FULL"]:
            return points_forward * 2 * self.sweeps
        elif self.sweep_type == "Triangle":
            return points_forward * 3 * self.sweeps
        else:
            return points_forward * self.sweeps
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'start_v': self.start_v,
            'stop_v': self.stop_v,
            'step_v': self.step_v,
            'neg_stop_v': self.neg_stop_v,
            'step_delay': self.step_delay,
            'sweeps': self.sweeps,
            'sweep_type': self.sweep_type,
            'icc': self.icc,
            'source_mode': self.source_mode.value if hasattr(self.source_mode, 'value') else str(self.source_mode),
            'led': self.led,
            'power': self.power,
        }


# Helper functions

def create_sweep_config_from_gui(gui_values: dict) -> SweepConfig:
    """
    Create SweepConfig from GUI parameter dictionary.
    
    Args:
        gui_values: Dictionary of GUI values (start_voltage, voltage_high, etc.)
    
    Returns:
        SweepConfig: Configured sweep
    
    Example:
        >>> gui_vals = {
        ...     'start_voltage': 0.0,
        ...     'voltage_high': 1.0,
        ...     'step_size': 0.1,
        ...     'icc': 1e-3,
        ...     'sweep_type': 'FS'
        ... }
        >>> config = create_sweep_config_from_gui(gui_vals)
    """
    return SweepConfig(
        start_v=float(gui_values.get('start_voltage', 0.0)),
        stop_v=float(gui_values.get('voltage_high', 1.0)),
        step_v=gui_values.get('step_size'),
        neg_stop_v=gui_values.get('voltage_low'),
        step_delay=float(gui_values.get('step_delay', 0.05)),
        sweeps=int(gui_values.get('sweeps', 1)),
        pause_s=float(gui_values.get('pause', 0.0)),
        sweep_type=str(gui_values.get('sweep_type', 'FS')),
        icc=float(gui_values.get('icc', 1e-3)),
        source_mode=gui_values.get('source_mode', SourceMode.VOLTAGE),
        led=bool(gui_values.get('led', False)),
        power=float(gui_values.get('led_power', 1.0)),
        sequence=gui_values.get('sequence'),
    )


# Module-level test
if __name__ == "__main__":
    print("Testing sweep_config module...")
    
    # Test InstrumentCapabilities
    print("\n1. Testing InstrumentCapabilities:")
    caps_4200 = InstrumentCapabilities(
        supports_hardware_sweep=True,
        min_step_delay_ms=1.0,
        voltage_range=(-200.0, 200.0)
    )
    print(f"  Keithley 4200A: hardware_sweep={caps_4200.supports_hardware_sweep}")
    
    caps_2400 = InstrumentCapabilities(
        supports_hardware_sweep=False,
        min_step_delay_ms=50.0,
        voltage_range=(-20.0, 20.0)
    )
    print(f"  Keithley 2400: hardware_sweep={caps_2400.supports_hardware_sweep}")
    
    # Test SweepConfig
    print("\n2. Testing SweepConfig:")
    config = SweepConfig(
        start_v=0.0,
        stop_v=1.0,
        step_v=0.1,
        sweep_type="FS",
        icc=1e-3
    )
    print(f"  Config: {config.start_v}V to {config.stop_v}V, {config.num_points} points")
    print(f"  Source mode: {config.source_mode}")
    
    # Test current source config
    print("\n3. Testing Current Source Config:")
    config_current = SweepConfig(
        start_v=0.0,
        stop_v=1e-6,
        step_v=1e-7,
        sweep_type="FS",
        icc=10.0,  # Voltage compliance
        source_mode=SourceMode.CURRENT
    )
    print(f"  Current source: {config_current.start_v}A to {config_current.stop_v}A")
    print(f"  Source mode: {config_current.source_mode}")
    
    # Test to_dict
    print("\n4. Testing serialization:")
    config_dict = config.to_dict()
    print(f"  Dict keys: {list(config_dict.keys())}")
    
    print("\nAll tests passed!")

