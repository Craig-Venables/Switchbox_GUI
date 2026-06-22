"""
PMU / SMU channel wiring hints for the Pulse Testing GUI.

All fast 4200 PMU interleaved C modules (pulse-read, endurance, retention,
potentiation/depression) use retention_pulse_ilimit_dual_channel with
ForceCh=1 and MeasureCh=2 — both PMU channels must be wired to the DUT.

Laser + Read uses a different 2-ch layout (CH1 DUT, CH2 laser driver).
"""

from typing import Optional

from Pulse_Testing.keithley4200_constants import (
    KEITHLEY4200_PMU_TIMING_SYSTEMS,
    KEITHLEY4200_SMU_OPTICAL_SYSTEMS,
)

# Uses pmu_pulse_read_interleaved / retention_pulse_ilimit_dual_channel (ForceCh=1, MeasureCh=2)
PMU_INTERLEAVED_DUT_2CH = frozenset(
    {
        "pulse_read_repeat",
        "pulse_then_read",
        "multi_pulse_then_read",
        "width_sweep_with_reads",
        "potentiation_depression_cycle",
        "potentiation_only",
        "depression_only",
        "endurance_test",
        "retention_test",
        "pulse_multi_read",
        "multi_read_only",
        "relaxation_after_multi_pulse",
        "pulse_train_varying_amplitudes",
        "voltage_amplitude_sweep",
        "ispp_test",
        "switching_threshold_test",
        "multilevel_programming",
    }
)

PMU_LASER_2CH = frozenset({"laser_and_read"})

SMU_4200_TESTS = frozenset(
    {
        "smu_slow_pulse_measure",
        "smu_endurance",
        "smu_retention",
        "smu_retention_with_pulse_measurement",
    }
)

OPTICAL_TESTS = frozenset(
    {
        "optical_read_pulsed_light",
        "optical_pulse_train_read",
        "optical_pulse_train_pattern_read",
        "optical_binary_sweep",
        "optical_pattern_repeat",
    }
)

SINGLE_CHANNEL_SYSTEMS = frozenset({"keithley2450", "keithley2450_sim", "keithley2400"})

_PMU_DUT_2CH_HINT = (
    "2-ch PMU (required): CH1 HI force → DUT+ ; CH2 LO measure → DUT− "
    "(ForceCh=1, MeasureCh=2). Primary current = CH2 (IM). "
    "Scope debug: tee CH1 + CH2."
)

_PMU_LASER_2CH_HINT = (
    "2-ch PMU (laser layout — not standard DUT wiring): CH1 → DUT (reads); "
    "CH2 → laser driver (≤2 V, not device return). Re-cable when switching "
    "to/from endurance / retention / pulse-read tests."
)

_SMU_4200_HINT = "1× SMU channel → DUT (select SMU in Clarius or your probe card wiring)."

_OPTICAL_4200_HINT = (
    "SMU → DUT for timed reads; laser via serial / function generator "
    "(not PMU CH2). Use keithley4200_smu profile."
)

_SINGLE_CH_HINT = "1-ch instrument: single force/sense pair → DUT."


def get_channel_wiring_hint(system_name: Optional[str], test_function: str) -> Optional[str]:
    """Return a short wiring line for the GUI, or None if not applicable."""
    if not system_name or not test_function:
        return None

    if system_name in KEITHLEY4200_PMU_TIMING_SYSTEMS:
        if test_function in PMU_INTERLEAVED_DUT_2CH:
            return _PMU_DUT_2CH_HINT
        if test_function in PMU_LASER_2CH:
            return _PMU_LASER_2CH_HINT
        return None

    if system_name in KEITHLEY4200_SMU_OPTICAL_SYSTEMS:
        if test_function in SMU_4200_TESTS:
            return _SMU_4200_HINT
        if test_function in OPTICAL_TESTS:
            return _OPTICAL_4200_HINT
        return None

    if system_name in SINGLE_CHANNEL_SYSTEMS:
        return _SINGLE_CH_HINT

    return None


def is_pmu_dual_dut_test(test_function: str) -> bool:
    """True when the test needs standard CH1 force / CH2 measure DUT wiring."""
    return test_function in PMU_INTERLEAVED_DUT_2CH
