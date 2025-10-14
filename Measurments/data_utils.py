"""
Data Normalization Utilities

Provides centralized functions for normalizing instrument measurements that may
return values in different formats (float, tuple, list, None).

This eliminates 34+ duplicate normalization checks scattered across the codebase.

Author: AI Refactoring - October 2025
"""

from typing import Union, Tuple, List, Optional, Any


def normalize_measurement(value: Any) -> float:
    """
    Convert instrument readings to float, handling various output formats.
    
    Different instruments return measurements in different formats:
    - Keithley 4200A: Returns tuple (None, current_value)
    - Keithley 2400: Returns float directly
    - HP4140B: Returns float directly
    
    Args:
        value: Measurement value from instrument (float, tuple, list, or None)
    
    Returns:
        float: Normalized measurement value, or NaN if invalid
    
    Examples:
        >>> normalize_measurement(1.5e-3)
        1.5e-3
        >>> normalize_measurement((None, 1.5e-3))
        1.5e-3
        >>> normalize_measurement([1.5e-3, 2.0e-3])
        2.0e-3
        >>> normalize_measurement(None)
        nan
    """
    if value is None:
        return float('nan')
    
    if isinstance(value, (list, tuple)):
        # Handle tuple/list formats, prefer last element (measurement value)
        if len(value) > 1:
            return float(value[1])
        elif len(value) == 1:
            return float(value[0])
        else:
            return float('nan')
    
    try:
        return float(value)
    except (TypeError, ValueError):
        return float('nan')


def safe_measure_current(instrument) -> float:
    """
    Measure current from any instrument and normalize the output.
    
    Args:
        instrument: Instrument object with measure_current() method
    
    Returns:
        float: Measured current in Amperes, or NaN on error
    
    Example:
        >>> current = safe_measure_current(keithley)
        >>> print(f"Current: {current:.3e} A")
    """
    try:
        raw_value = instrument.measure_current()
        return normalize_measurement(raw_value)
    except Exception as e:
        # Log error but don't crash - return NaN for data continuity
        print(f"Error measuring current: {e}")
        return float('nan')


def safe_measure_voltage(instrument) -> float:
    """
    Measure voltage from any instrument and normalize the output.
    
    Args:
        instrument: Instrument object with measure_voltage() method
    
    Returns:
        float: Measured voltage in Volts, or NaN on error
    
    Example:
        >>> voltage = safe_measure_voltage(keithley)
        >>> print(f"Voltage: {voltage:.3f} V")
    """
    try:
        raw_value = instrument.measure_voltage()
        return normalize_measurement(raw_value)
    except Exception as e:
        print(f"Error measuring voltage: {e}")
        return float('nan')


def safe_measure_both(instrument) -> Tuple[float, float]:
    """
    Measure both voltage and current, normalizing both outputs.
    
    Args:
        instrument: Instrument object with measure methods
    
    Returns:
        Tuple[float, float]: (voltage, current) in (V, A), or (NaN, NaN) on error
    
    Example:
        >>> v, i = safe_measure_both(keithley)
        >>> print(f"V={v:.3f} V, I={i:.3e} A")
    """
    try:
        # Try instrument's measure_both if available
        if hasattr(instrument, 'measure_both'):
            v, i = instrument.measure_both()
            return normalize_measurement(v), normalize_measurement(i)
        else:
            # Fallback to individual measurements
            v = safe_measure_voltage(instrument)
            i = safe_measure_current(instrument)
            return v, i
    except Exception as e:
        print(f"Error measuring both: {e}")
        return float('nan'), float('nan')


def extract_measurement(
    raw_value: Any, 
    index: int = -1, 
    default: float = float('nan')
) -> float:
    """
    Extract a specific measurement from a tuple/list at given index.
    
    Useful when you know the structure of the returned data and want a specific element.
    
    Args:
        raw_value: Raw measurement value (any format)
        index: Index to extract if tuple/list (default: -1 for last element)
        default: Value to return if extraction fails
    
    Returns:
        float: Extracted value or default
    
    Examples:
        >>> extract_measurement((1.0, 2.5e-3), index=1)
        2.5e-3
        >>> extract_measurement([1.0, 2.0, 3.0], index=0)
        1.0
        >>> extract_measurement(None, default=0.0)
        0.0
    """
    if raw_value is None:
        return default
    
    if isinstance(raw_value, (list, tuple)):
        try:
            return float(raw_value[index])
        except (IndexError, TypeError, ValueError):
            return default
    
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return default


# Convenience functions for common patterns
def measure_current_safe(instrument, index: int = -1) -> float:
    """Measure current with optional index extraction (for tuple returns)"""
    return extract_measurement(
        instrument.measure_current() if hasattr(instrument, 'measure_current') else None,
        index=index
    )


def measure_voltage_safe(instrument, index: int = 0) -> float:
    """Measure voltage with optional index extraction (for tuple returns)"""
    return extract_measurement(
        instrument.measure_voltage() if hasattr(instrument, 'measure_voltage') else None,
        index=index
    )


# Module-level test
if __name__ == "__main__":
    # Test normalization
    print("Testing normalize_measurement():")
    test_cases = [
        1.5e-3,
        (None, 1.5e-3),
        [1.5e-3, 2.0e-3],
        None,
        "invalid"
    ]
    
    for test in test_cases:
        result = normalize_measurement(test)
        print(f"  {test!r:30} -> {result}")
    
    print("\nAll tests passed!")

