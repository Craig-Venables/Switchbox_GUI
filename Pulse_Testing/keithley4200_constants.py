"""
Keithley 4200-SCS profile identifiers (PMU vs SMU vs custom setup).

Used by the pulse GUI, optical runner, and oscilloscope GUI so string checks stay in one place.
See Pulse_Testing/README.md — "Keithley 4200 profiles".
"""

from typing import FrozenSet

# Fast interleaved / PMU timing: GUI uses µs for these systems.
KEITHLEY4200_PMU_TIMING_SYSTEMS: FrozenSet[str] = frozenset(
    {"keithley4200_pmu", "keithley4200a"}
)

# Optical + read on 4200 uses SMU bias-timed read (Python + laser sync).
# Use keithley4200_smu in the GUI; legacy keithley4200a matches PMU capabilities only.
KEITHLEY4200_SMU_OPTICAL_SYSTEMS: FrozenSet[str] = frozenset({"keithley4200_smu"})

# Any registered 4200 adapter (including legacy alias and custom connect-only profile).
KEITHLEY4200_SYSTEM_IDS: FrozenSet[str] = frozenset(
    {"keithley4200_pmu", "keithley4200_smu", "keithley4200_custom", "keithley4200a"}
)
