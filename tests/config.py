from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Thresholds:
    # Baseline probe
    probe_voltage_v: float = 0.2
    probe_duration_s: float = 3.0
    probe_sample_hz: int = 100
    working_current_a: float = 1e-9

    # Forming
    forming_voltages_v: tuple[float, ...] = (1.0, 2.0, 3.0, 4.0)
    forming_step_v: float = 0.01
    forming_dwell_s: float = 0.002
    forming_compliance_a: float = 100e-6
    forming_spike_current_a: float = 1e-8
    forming_hysteresis_min: float = 1e-10  # loop area minimum to consider memristive
    forming_cooldown_s: float = 0.5

    # Hysteresis optimization (discrete profiles)
    hyst_profiles: tuple[tuple[float, float, float, float], ...] = (
        # (v_max, step_v, dwell_s, i_comp)
        (0.5, 0.01, 0.005, 20e-6),
        (1.0, 0.01, 0.005, 20e-6),
        (1.5, 0.01, 0.010, 50e-6),
        (2.0, 0.02, 0.010, 50e-6),
        (2.5, 0.02, 0.015, 80e-6),
    )
    hyst_budget: int = 5  # number of profiles to evaluate per device

    # Endurance
    endurance_cycles: int = 100
    set_voltage_v: float = 1.5
    reset_voltage_v: float = -1.5
    pulse_width_s: float = 0.01
    read_voltage_v: float = 0.2
    endurance_abort_on_ratio_below: float = 2.0
    endurance_abort_consec: int = 5

    # Retention
    retention_times_s: tuple[float, ...] = (1, 3, 10, 30, 100, 300)
    retention_read_voltage_v: float = 0.2

    # Safety
    max_voltage_v: float = 4.0
    max_compliance_a: float = 100e-6
    dcurrent_abort_a_per_s: float = 5e-4


