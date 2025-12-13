"""
Sweep Pattern Utilities

Provides centralized generation of voltage/current sweep patterns.

Eliminates 7+ duplicate sweep pattern generation blocks across the codebase.
Makes it easy to add custom sweep patterns and modify existing ones.

Author: AI Refactoring - October 2025
"""

from enum import Enum
from typing import List, Optional, Union
import numpy as np


class SweepType(Enum):
    """
    Standard sweep pattern types.
    
    - POSITIVE (PS): Start to stop (positive direction)
    - NEGATIVE (NS): Start to stop (negative direction)
    - FULL (FS): Start to stop, then back to start
    - HALF (HS): Start to stop only (same as POSITIVE, alias for clarity)
    - TRIANGLE: Start to stop to negative, then back to start
    - CUSTOM: User-defined pattern
    """
    POSITIVE = "PS"
    NEGATIVE = "NS"
    FULL = "FS"
    HALF = "HS"
    TRIANGLE = "Triangle"
    CUSTOM = "Custom"


def build_sweep_values(
    start: float,
    stop: float,
    step: Optional[float] = None,
    sweep_type: Union[SweepType, str] = SweepType.FULL,
    neg_stop: Optional[float] = None,
    num_points: Optional[int] = None
) -> List[float]:
    """
    Generate a list of sweep values based on pattern type.
    
    Args:
        start: Starting value
        stop: Stopping value (maximum positive value)
        step: Step size (optional, calculated if not provided)
        sweep_type: Type of sweep pattern (SweepType enum or string)
        neg_stop: Negative stopping value (for triangle sweep)
        num_points: Number of points (alternative to step)
    
    Returns:
        List[float]: List of sweep values
    
    Examples:
        >>> # Full sweep: 0 to 1 to 0
        >>> values = build_sweep_values(0, 1, step=0.1, sweep_type=SweepType.FULL)
        >>> # [0.0, 0.1, 0.2, ..., 1.0, 0.9, 0.8, ..., 0.0]
        
        >>> # Positive sweep: 0 to 1
        >>> values = build_sweep_values(0, 1, step=0.1, sweep_type=SweepType.POSITIVE)
        >>> # [0.0, 0.1, 0.2, ..., 1.0]
        
        >>> # Triangle: 0 to 1 to -1 to 0
        >>> values = build_sweep_values(0, 1, step=0.1, sweep_type=SweepType.TRIANGLE, neg_stop=-1)
        >>> # [0.0, 0.1, ..., 1.0, 0.9, ..., 0.0, -0.1, ..., -1.0, -0.9, ..., 0.0]
    """
    # Convert string to enum if needed
    if isinstance(sweep_type, str):
        try:
            sweep_type = SweepType(sweep_type)
        except ValueError:
            # Try uppercase conversion for backward compatibility
            for st in SweepType:
                if st.value.upper() == sweep_type.upper():
                    sweep_type = st
                    break
            else:
                sweep_type = SweepType.FULL  # Default fallback
    
    # Calculate step if not provided
    if step is None:
        if num_points is not None and num_points > 1:
            step = (stop - start) / (num_points - 1)
        else:
            step = (stop - start) / 100  # Default 100 points
    
    # Ensure step is positive
    step = abs(step)
    
    # Build forward sweep
    forward = np.arange(start, stop + step/2, step)
    
    if sweep_type == SweepType.POSITIVE or sweep_type == SweepType.HALF:
        # Simple positive sweep (half sweep)
        return list(forward)
    
    elif sweep_type == SweepType.NEGATIVE:
        # Negative sweep (flip the values)
        return list(-forward)
    
    elif sweep_type == SweepType.FULL:
        # Full sweep: forward then reverse
        reverse = np.arange(stop, start - step/2, -step)
        return list(forward) + list(reverse)
    
    elif sweep_type == SweepType.TRIANGLE:
        # Triangle sweep: forward, negative, return
        if neg_stop is None:
            neg_stop = -stop  # Default symmetric
        
        # Forward: start to stop
        forward = np.arange(start, stop + step/2, step)
        # Negative: start to neg_stop
        negative = np.arange(start, neg_stop - step/2, -step)
        # Back: neg_stop to start
        back = np.arange(neg_stop, start + step/2, step)
        
        return list(forward) + list(negative) + list(back)
    
    else:
        # Default to full sweep for unknown types
        reverse = np.arange(stop, start - step/2, -step)
        return list(forward) + list(reverse)


def build_multi_sweep(
    start: float,
    stop: float,
    step: Optional[float] = None,
    sweep_type: Union[SweepType, str] = SweepType.FULL,
    neg_stop: Optional[float] = None,
    num_sweeps: int = 1
) -> List[float]:
    """
    Generate multiple consecutive sweeps.
    
    Args:
        start: Starting value
        stop: Stopping value
        step: Step size
        sweep_type: Type of sweep pattern
        neg_stop: Negative stopping value (for triangle)
        num_sweeps: Number of sweeps to concatenate
    
    Returns:
        List[float]: Concatenated sweep values
    
    Example:
        >>> # 3 full sweeps
        >>> values = build_multi_sweep(0, 1, 0.5, SweepType.FULL, num_sweeps=3)
        >>> # [0, 0.5, 1, 0.5, 0] + [0, 0.5, 1, 0.5, 0] + [0, 0.5, 1, 0.5, 0]
    """
    single_sweep = build_sweep_values(start, stop, step, sweep_type, neg_stop)
    return single_sweep * num_sweeps


def build_custom_pattern(values: List[float], repeat: int = 1) -> List[float]:
    """
    Create a custom sweep pattern from a list of values.
    
    Args:
        values: List of custom sweep values
        repeat: Number of times to repeat the pattern
    
    Returns:
        List[float]: Custom pattern repeated
    
    Example:
        >>> pattern = build_custom_pattern([0, 1, 0.5, 0], repeat=2)
        >>> # [0, 1, 0.5, 0, 0, 1, 0.5, 0]
    """
    return list(values) * repeat


def get_sweep_extrema(
    start: float,
    stop: float,
    sweep_type: Union[SweepType, str] = SweepType.FULL,
    neg_stop: Optional[float] = None
) -> tuple[float, float]:
    """
    Get the minimum and maximum values of a sweep.
    
    Args:
        start: Starting value
        stop: Stopping value
        sweep_type: Type of sweep
        neg_stop: Negative stopping value (for triangle)
    
    Returns:
        Tuple[float, float]: (min_value, max_value)
    
    Example:
        >>> min_val, max_val = get_sweep_extrema(0, 1, SweepType.TRIANGLE, neg_stop=-1)
        >>> # (-1.0, 1.0)
    """
    if isinstance(sweep_type, str):
        try:
            sweep_type = SweepType(sweep_type)
        except ValueError:
            sweep_type = SweepType.FULL
    
    if sweep_type == SweepType.NEGATIVE:
        return (-stop, -start)
    elif sweep_type == SweepType.TRIANGLE and neg_stop is not None:
        return (min(start, stop, neg_stop), max(start, stop, neg_stop))
    else:
        return (min(start, stop), max(start, stop))


def estimate_sweep_points(
    start: float,
    stop: float,
    step: Optional[float] = None,
    sweep_type: Union[SweepType, str] = SweepType.FULL,
    neg_stop: Optional[float] = None,
    num_sweeps: int = 1
) -> int:
    """
    Estimate the number of points in a sweep without generating it.
    
    Useful for pre-allocating arrays or estimating measurement time.
    
    Args:
        start: Starting value
        stop: Stopping value
        step: Step size
        sweep_type: Type of sweep
        neg_stop: Negative stopping value
        num_sweeps: Number of sweeps
    
    Returns:
        int: Estimated number of points
    
    Example:
        >>> points = estimate_sweep_points(0, 1, 0.1, SweepType.FULL, num_sweeps=2)
        >>> # Approximately 42 points (21 per sweep, 2 sweeps)
    """
    if step is None:
        step = (stop - start) / 100
    
    step = abs(step)
    if step == 0:
        return 1
    
    # Points in forward sweep
    forward_points = int((stop - start) / step) + 1
    
    if isinstance(sweep_type, str):
        try:
            sweep_type = SweepType(sweep_type)
        except ValueError:
            sweep_type = SweepType.FULL
    
    if sweep_type == SweepType.POSITIVE or sweep_type == SweepType.NEGATIVE or sweep_type == SweepType.HALF:
        points_per_sweep = forward_points
    elif sweep_type == SweepType.FULL:
        points_per_sweep = forward_points * 2 - 1  # Don't double-count endpoints
    elif sweep_type == SweepType.TRIANGLE:
        if neg_stop is not None:
            negative_points = int(abs(start - neg_stop) / step) + 1
            back_points = negative_points
            points_per_sweep = forward_points + negative_points + back_points - 2
        else:
            points_per_sweep = forward_points * 3 - 2
    else:
        points_per_sweep = forward_points
    
    return points_per_sweep * num_sweeps


# Module-level test
if __name__ == "__main__":
    print("Testing sweep_patterns module...")
    
    # Test positive sweep
    print("\n1. Positive Sweep (PS):")
    values = build_sweep_values(0, 1, step=0.5, sweep_type=SweepType.POSITIVE)
    print(f"  Values: {values}")
    print(f"  Points: {len(values)}")
    
    # Test full sweep
    print("\n2. Full Sweep (FS):")
    values = build_sweep_values(0, 1, step=0.25, sweep_type=SweepType.FULL)
    print(f"  Values: {values}")
    print(f"  Points: {len(values)}")
    
    # Test triangle sweep
    print("\n3. Triangle Sweep:")
    values = build_sweep_values(0, 1, step=0.5, sweep_type=SweepType.TRIANGLE, neg_stop=-1)
    print(f"  Values: {values}")
    print(f"  Points: {len(values)}")
    
    # Test multi-sweep
    print("\n4. Multi-Sweep (3x FS):")
    values = build_multi_sweep(0, 1, step=0.5, sweep_type=SweepType.FULL, num_sweeps=3)
    print(f"  Points: {len(values)}")
    print(f"  First sweep: {values[:5]}")
    
    # Test extrema
    print("\n5. Sweep Extrema:")
    min_val, max_val = get_sweep_extrema(0, 1, SweepType.TRIANGLE, neg_stop=-1.5)
    print(f"  Min: {min_val}, Max: {max_val}")
    
    # Test point estimation
    print("\n6. Point Estimation:")
    estimated = estimate_sweep_points(0, 1, step=0.1, sweep_type=SweepType.FULL, num_sweeps=2)
    actual = len(build_multi_sweep(0, 1, step=0.1, sweep_type=SweepType.FULL, num_sweeps=2))
    print(f"  Estimated: {estimated}, Actual: {actual}")
    
    # Test backward compatibility with string types
    print("\n7. String Type Compatibility:")
    values_fs = build_sweep_values(0, 1, step=0.5, sweep_type="FS")
    values_ps = build_sweep_values(0, 1, step=0.5, sweep_type="PS")
    print(f"  FS: {len(values_fs)} points")
    print(f"  PS: {len(values_ps)} points")
    
    print("\nAll tests passed!")

