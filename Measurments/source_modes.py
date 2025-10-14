"""
Source Mode Abstraction

Provides a unified framework for different source modes:
- Voltage Source (source V, measure I) - traditional IV measurements
- Current Source (source I, measure V) - reverse measurements
- Future: Power Source, Resistance Source, etc.

This eliminates mode-specific if-statements and enables easy addition of new modes.

Author: AI Refactoring - October 2025
"""

from enum import Enum
from typing import Tuple, Callable, Optional


class SourceMode(Enum):
    """
    Enumeration of supported source modes.
    
    Each mode defines:
    - What quantity is sourced (set)
    - What quantity is measured (read)
    """
    VOLTAGE = "voltage"  # Source voltage, measure current
    CURRENT = "current"  # Source current, measure voltage
    # Future modes can be added here:
    # POWER = "power"      # Source power, measure current
    # RESISTANCE = "resistance"  # Source resistance (via feedback)


def apply_source(
    instrument, 
    mode: SourceMode, 
    value: float, 
    compliance: float
) -> None:
    """
    Apply a source value to the instrument based on mode.
    
    Args:
        instrument: Instrument object with set_voltage/set_current methods
        mode: Source mode (VOLTAGE or CURRENT)
        value: Source value (V for voltage mode, A for current mode)
        compliance: Compliance limit (A for voltage mode, V for current mode)
    
    Examples:
        >>> # Voltage source mode
        >>> apply_source(keithley, SourceMode.VOLTAGE, 1.0, 1e-3)
        >>> # Sets 1.0V with 1mA compliance
        
        >>> # Current source mode
        >>> apply_source(keithley, SourceMode.CURRENT, 1e-6, 10.0)
        >>> # Sets 1µA with 10V compliance
    
    Raises:
        ValueError: If mode is not supported
    """
    if mode == SourceMode.VOLTAGE:
        # Source voltage, compliance on current
        instrument.set_voltage(float(value), float(compliance))
        
    elif mode == SourceMode.CURRENT:
        # Source current, compliance on voltage
        instrument.set_current(float(value), float(compliance))
        
    else:
        raise ValueError(f"Unsupported source mode: {mode}")


def measure_result(instrument, mode: SourceMode) -> float:
    """
    Measure the appropriate quantity based on source mode.
    
    Args:
        instrument: Instrument object with measure_voltage/measure_current methods
        mode: Source mode (determines what to measure)
    
    Returns:
        float: Measured value (A for voltage mode, V for current mode)
    
    Examples:
        >>> # Voltage source mode - measure current
        >>> current = measure_result(keithley, SourceMode.VOLTAGE)
        
        >>> # Current source mode - measure voltage  
        >>> voltage = measure_result(keithley, SourceMode.CURRENT)
    
    Raises:
        ValueError: If mode is not supported
    """
    if mode == SourceMode.VOLTAGE:
        # Measuring current when sourcing voltage
        return instrument.measure_current()
        
    elif mode == SourceMode.CURRENT:
        # Measuring voltage when sourcing current
        return instrument.measure_voltage()
        
    else:
        raise ValueError(f"Unsupported source mode: {mode}")


def get_axis_labels(mode: SourceMode) -> Tuple[str, str]:
    """
    Get appropriate axis labels for plotting based on source mode.
    
    Args:
        mode: Source mode
    
    Returns:
        Tuple[str, str]: (x_label, y_label) for plotting
            - x_label: Label for sourced quantity
            - y_label: Label for measured quantity
    
    Examples:
        >>> x_label, y_label = get_axis_labels(SourceMode.VOLTAGE)
        >>> print(f"{x_label} vs {y_label}")
        Voltage (V) vs Current (A)
        
        >>> x_label, y_label = get_axis_labels(SourceMode.CURRENT)
        >>> print(f"{x_label} vs {y_label}")
        Current (A) vs Voltage (V)
    """
    if mode == SourceMode.VOLTAGE:
        return ("Voltage (V)", "Current (A)")
        
    elif mode == SourceMode.CURRENT:
        return ("Current (A)", "Voltage (V)")
        
    else:
        return ("Source", "Measure")


def get_data_column_names(mode: SourceMode) -> Tuple[str, str]:
    """
    Get column names for data files based on source mode.
    
    Args:
        mode: Source mode
    
    Returns:
        Tuple[str, str]: (source_column_name, measure_column_name)
    
    Examples:
        >>> src, meas = get_data_column_names(SourceMode.VOLTAGE)
        >>> print(f"{src}, {meas}")
        Voltage, Current
    """
    if mode == SourceMode.VOLTAGE:
        return ("Voltage", "Current")
        
    elif mode == SourceMode.CURRENT:
        return ("Current", "Voltage")
        
    else:
        return ("Source", "Measure")


def get_units(mode: SourceMode) -> Tuple[str, str]:
    """
    Get units for source and measure quantities.
    
    Args:
        mode: Source mode
    
    Returns:
        Tuple[str, str]: (source_unit, measure_unit)
    
    Examples:
        >>> src_unit, meas_unit = get_units(SourceMode.VOLTAGE)
        >>> print(f"Sourcing in {src_unit}, measuring in {meas_unit}")
        Sourcing in V, measuring in A
    """
    if mode == SourceMode.VOLTAGE:
        return ("V", "A")
        
    elif mode == SourceMode.CURRENT:
        return ("A", "V")
        
    else:
        return ("", "")


def format_source_value(mode: SourceMode, value: float) -> str:
    """
    Format source value with appropriate units for display.
    
    Args:
        mode: Source mode
        value: Source value
    
    Returns:
        str: Formatted string with units
    
    Examples:
        >>> format_source_value(SourceMode.VOLTAGE, 1.5)
        '1.50 V'
        >>> format_source_value(SourceMode.CURRENT, 1e-6)
        '1.00e-06 A'
    """
    src_unit, _ = get_units(mode)
    
    # Use scientific notation for very small/large values
    if abs(value) < 0.01 or abs(value) > 1000:
        return f"{value:.2e} {src_unit}"
    else:
        return f"{value:.2f} {src_unit}"


def format_measure_value(mode: SourceMode, value: float) -> str:
    """
    Format measured value with appropriate units for display.
    
    Args:
        mode: Source mode
        value: Measured value
    
    Returns:
        str: Formatted string with units
    """
    _, meas_unit = get_units(mode)
    
    if abs(value) < 0.01 or abs(value) > 1000:
        return f"{value:.2e} {meas_unit}"
    else:
        return f"{value:.2f} {meas_unit}"


class SourceModeConfig:
    """
    Configuration object for a specific source mode setup.
    
    This is a convenience class that bundles mode, value, and compliance together.
    
    Examples:
        >>> # Voltage source configuration
        >>> config = SourceModeConfig(SourceMode.VOLTAGE, 1.0, 1e-3)
        >>> config.apply(keithley)
        >>> measurement = config.measure(keithley)
        
        >>> # Current source configuration
        >>> config = SourceModeConfig(SourceMode.CURRENT, 1e-6, 10.0)
        >>> config.apply(keithley)
        >>> measurement = config.measure(keithley)
    """
    
    def __init__(
        self, 
        mode: SourceMode, 
        value: float, 
        compliance: float
    ):
        """
        Initialize source mode configuration.
        
        Args:
            mode: Source mode
            value: Source value
            compliance: Compliance limit
        """
        self.mode = mode
        self.value = value
        self.compliance = compliance
    
    def apply(self, instrument) -> None:
        """Apply this configuration to an instrument."""
        apply_source(instrument, self.mode, self.value, self.compliance)
    
    def measure(self, instrument) -> float:
        """Measure the appropriate quantity from the instrument."""
        return measure_result(instrument, self.mode)
    
    def get_labels(self) -> Tuple[str, str]:
        """Get axis labels for plotting."""
        return get_axis_labels(self.mode)
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        src_str = format_source_value(self.mode, self.value)
        comp_str = format_measure_value(
            SourceMode.CURRENT if self.mode == SourceMode.VOLTAGE else SourceMode.VOLTAGE,
            self.compliance
        )
        return f"SourceModeConfig(mode={self.mode.value}, source={src_str}, compliance={comp_str})"


# Module-level test
if __name__ == "__main__":
    print("Testing source_modes module...")
    
    # Mock instrument
    class MockInstrument:
        def __init__(self):
            self.voltage = 0.0
            self.current = 0.0
        
        def set_voltage(self, v, icc):
            self.voltage = v
            print(f"  Set voltage: {v} V (compliance: {icc} A)")
        
        def set_current(self, i, vcc):
            self.current = i
            print(f"  Set current: {i} A (compliance: {vcc} V)")
        
        def measure_voltage(self):
            print(f"  Measured voltage: {self.voltage} V")
            return self.voltage
        
        def measure_current(self):
            print(f"  Measured current: {self.current} A")
            return self.current
    
    instrument = MockInstrument()
    
    # Test voltage mode
    print("\n1. Testing VOLTAGE mode:")
    apply_source(instrument, SourceMode.VOLTAGE, 1.5, 1e-3)
    instrument.current = 5e-4  # Simulate measurement
    result = measure_result(instrument, SourceMode.VOLTAGE)
    print(f"  Result: {result}")
    labels = get_axis_labels(SourceMode.VOLTAGE)
    print(f"  Plot labels: {labels}")
    
    # Test current mode
    print("\n2. Testing CURRENT mode:")
    apply_source(instrument, SourceMode.CURRENT, 1e-6, 10.0)
    instrument.voltage = 2.5  # Simulate measurement
    result = measure_result(instrument, SourceMode.CURRENT)
    print(f"  Result: {result}")
    labels = get_axis_labels(SourceMode.CURRENT)
    print(f"  Plot labels: {labels}")
    
    # Test config object
    print("\n3. Testing SourceModeConfig:")
    config = SourceModeConfig(SourceMode.VOLTAGE, 2.0, 5e-3)
    print(f"  {config}")
    config.apply(instrument)
    
    print("\nAll tests passed!")

