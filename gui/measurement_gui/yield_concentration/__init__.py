"""
Yield and Concentration Analysis
=================================

Derives per-device yield and sample-level yield fraction from:
  1. Per-sample manual Excel ({sample_name}.xlsx) — highest priority
  2. Cached JSON manifest from a previous auto-run
  3. Auto-classification from device_tracking history JSONs

Combines yield with fabrication metadata (Np Concentration, Qd Spacing,
Polymer, etc.) from the 'solutions and devices.xlsx' and computes
average resistance at 0.1 V from the first measurement file per device.

Public API
----------
    from gui.measurement_gui.yield_concentration import run_yield_analysis
"""

from gui.measurement_gui.yield_concentration.aggregator import (
    run_yield_analysis,
    run_multi_sample_analysis,
    run_single_sample_analysis,
    detect_mode,
)

__all__ = ["run_yield_analysis", "run_multi_sample_analysis", "run_single_sample_analysis", "detect_mode"]
