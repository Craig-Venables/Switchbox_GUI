"""
Grouped runtime state for MeasurementGUI.

Keeps orchestrator attributes organised without changing external API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MeasurementRuntimeState:
    """Flags and transient measurement-run state."""

    tests_running: bool = False
    abort_tests_flag: bool = False
    stop_measurement_flag: bool = False
    measuring: bool = False
    pause_requested: bool = False
    sweep_runtime_overrides: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlotDisplayState:
    """Buffers used by live plot updaters."""

    v_arr_disp: List[float] = field(default_factory=list)
    v_arr_disp_abs: List[float] = field(default_factory=list)
    v_arr_disp_abs_log: List[float] = field(default_factory=list)
    c_arr_disp: List[float] = field(default_factory=list)
    c_arr_disp_log: List[float] = field(default_factory=list)
    c_arr_disp_abs: List[float] = field(default_factory=list)
    c_arr_disp_abs_log: List[float] = field(default_factory=list)
    r_arr_disp: List[float] = field(default_factory=list)
    t_arr_disp: List[float] = field(default_factory=list)
    temp_time_disp: List[float] = field(default_factory=list)
    pulse_history: List[Dict[str, Any]] = field(default_factory=list)
    last_combined_summary_path: Optional[str] = None
