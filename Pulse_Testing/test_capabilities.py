"""
Test Capability Definitions
===========================

Which tests each measurement system supports. Built from ``test_registry.py``:
a system supports a test function when any registry entry for that function lists
the system in ``systems``. Edit the registry, not this file.

See also: ``Pulse_Testing/ADDING_A_TEST.md``.

IMPORTANT NOTE FOR 4200A DATA COLLECTION:
------------------------------------------
GP parameters 20 (setV), 22 (setI), and 31 (PulseTimes) are verified for
pmu_pulse_read_interleaved, pmu_endurance_interleaved, and pmu_retention_dual_channel
(scope / smoke tests PASS where deployed).
"""

from typing import Dict, List, Optional

from .test_registry import ALL_SYSTEMS, all_functions, systems_for_function

# All test function names (must match method names on the system adapters)
ALL_TEST_FUNCTIONS: List[str] = all_functions()

# System capability matrix: SYSTEM_CAPABILITIES[system][function] -> bool
SYSTEM_CAPABILITIES: Dict[str, Dict[str, bool]] = {
    system: {func: system in systems_for_function(func) for func in ALL_TEST_FUNCTIONS}
    for system in sorted(ALL_SYSTEMS)
}


def is_test_supported(system_name: str, test_function: str) -> bool:
    """Check if a test is supported by a specific system.
    
    Args:
        system_name: System identifier (e.g., 'keithley2450', 'keithley4200_pmu')
        test_function: Test function name (e.g., 'pulse_read_repeat')
    
    Returns:
        True if test is supported, False otherwise
    """
    if system_name not in SYSTEM_CAPABILITIES:
        return False
    
    capabilities = SYSTEM_CAPABILITIES[system_name]
    return capabilities.get(test_function, False)


def get_supported_tests(system_name: str) -> List[str]:
    """Get list of all supported tests for a system.
    
    Args:
        system_name: System identifier
    
    Returns:
        List of test function names that are supported
    """
    if system_name not in SYSTEM_CAPABILITIES:
        return []
    
    capabilities = SYSTEM_CAPABILITIES[system_name]
    return [test for test, supported in capabilities.items() if supported]


def get_unsupported_tests(system_name: str) -> List[str]:
    """Get list of all unsupported tests for a system.
    
    Args:
        system_name: System identifier
    
    Returns:
        List of test function names that are not supported
    """
    if system_name not in SYSTEM_CAPABILITIES:
        return ALL_TEST_FUNCTIONS
    
    capabilities = SYSTEM_CAPABILITIES[system_name]
    return [test for test, supported in capabilities.items() if not supported]


def get_test_explanation(system_name: str, test_function: str) -> Optional[str]:
    """Get explanation for why a test is unsupported (if applicable).
    
    Args:
        system_name: System identifier
        test_function: Test function name
    
    Returns:
        Explanation string if test is unsupported, None if supported
    """
    if is_test_supported(system_name, test_function):
        return None
    
    # Custom explanations for unsupported tests (can be expanded)
    explanations = {
        'keithley2400': {
            # All tests are supported for 2400, but note GPIB speed limitations
            # Minimum pulse width is ~10ms due to GPIB communication overhead
        },
        'keithley4200a': {
            'varying_width_pulses': 'Not available - use width_sweep_with_reads instead (uses pmu_pulse_read_interleaved with Python-side loop)',
            'width_sweep_with_reads': 'Uses pmu_pulse_read_interleaved: requires Python-side loop calling C program multiple times with different width values (one call per width)',
            'width_sweep_with_all_measurements': 'Requires NEW C module with pulse peak current measurement capability (interleaved only measures during read windows)',
            'retention_test': 'PMU retention (pmu_retention_dual_channel). Preset: DUT 20 reads @ 1us program.',
            'current_range_finder': 'Requires Python-side loop over current ranges (interleaved program uses fixed i_range parameter)',
            'relaxation_after_multi_pulse_with_pulse_measurement': 'Requires NEW C module with pulse measurement capability (interleaved only measures during read windows, not during pulses)',
        },
        'keithley4200_pmu': {
            'varying_width_pulses': 'Not available - use width_sweep_with_reads instead (uses pmu_pulse_read_interleaved with Python-side loop)',
            'width_sweep_with_reads': 'Uses pmu_pulse_read_interleaved: requires Python-side loop calling C program multiple times with different width values (one call per width)',
            'width_sweep_with_all_measurements': 'Requires NEW C module with pulse peak current measurement capability (interleaved only measures during read windows)',
            'retention_test': 'PMU retention (pmu_retention_dual_channel). Preset: DUT 20 reads @ 1us program.',
            'current_range_finder': 'Requires Python-side loop over current ranges (interleaved program uses fixed i_range parameter)',
            'relaxation_after_multi_pulse_with_pulse_measurement': 'Requires NEW C module with pulse measurement capability (interleaved only measures during read windows, not during pulses)',
        },
        'keithley4200_smu': {
            'pulse_read_repeat': 'Fast PMU interleaved test. Select keithley4200_pmu in Connection.',
            'pulse_then_read': 'Fast PMU interleaved test. Select keithley4200_pmu in Connection.',
            'multi_pulse_then_read': 'Fast PMU interleaved test. Select keithley4200_pmu in Connection.',
            'width_sweep_with_reads': 'Fast PMU interleaved test. Select keithley4200_pmu in Connection.',
            'potentiation_depression_cycle': 'Fast PMU interleaved test. Select keithley4200_pmu in Connection.',
            'potentiation_only': 'Fast PMU interleaved test. Select keithley4200_pmu in Connection.',
            'depression_only': 'Fast PMU interleaved test. Select keithley4200_pmu in Connection.',
            'endurance_test': 'PMU endurance (pmu_endurance_interleaved). Preset: DUT 10cyc @ 1us.',
            'retention_test': 'PMU retention (pmu_retention_dual_channel). Preset: DUT 20 reads @ 1us program.',
            'pulse_multi_read': 'Fast PMU interleaved test. Select keithley4200_pmu in Connection.',
            'multi_read_only': 'Fast PMU interleaved test. Select keithley4200_pmu in Connection.',
            'relaxation_after_multi_pulse': 'Fast PMU interleaved test. Select keithley4200_pmu in Connection.',
            'voltage_amplitude_sweep': 'Fast PMU interleaved test. Select keithley4200_pmu in Connection.',
            'ispp_test': 'Fast PMU interleaved test. Select keithley4200_pmu in Connection.',
            'switching_threshold_test': 'Fast PMU interleaved test. Select keithley4200_pmu in Connection.',
            'multilevel_programming': 'Fast PMU interleaved test. Select keithley4200_pmu in Connection.',
            'pulse_train_varying_amplitudes': 'Fast PMU interleaved test. Select keithley4200_pmu in Connection.',
            'laser_and_read': 'Laser on PMU (CH2). Select keithley4200_pmu in Connection.',
        },
    }

    system_explanations = explanations.get(system_name, {})
    return system_explanations.get(
        test_function,
        f'Test not yet implemented for {system_name}'
    )

