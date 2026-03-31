"""
Pulse Testing Module
====================

Multi-system pulse testing architecture supporting:
- Keithley 2450 (TSP mode)
- Keithley 4200-SCS (KXCI): `keithley4200_pmu`, `keithley4200_smu`, `keithley4200_custom`, legacy `keithley4200a`

Provides unified interface for pulse testing across different measurement systems.
"""

__version__ = "1.0.0"

# Import visualization module
from .pulse_pattern_visualizer import (
    PulsePatternVisualizer,
    visualize_laser_and_read_pattern,
    PulsePatternTimeline,
    SignalSegment
)

__all__ = [
    'PulsePatternVisualizer',
    'visualize_laser_and_read_pattern',
    'PulsePatternTimeline',
    'SignalSegment',
]

