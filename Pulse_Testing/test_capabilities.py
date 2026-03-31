"""
Test Capability Definitions
===========================

Defines which tests are supported by each measurement system.
Easy to update: change boolean values to enable/disable test support.

To add Keithley 4200 support for a test:
1. Implement the method once on ``Keithley4200KXCICommon`` in ``systems/keithley4200_core.py`` (Equipment KXCI scripts as needed).
2. Set ``True`` in ``SYSTEM_CAPABILITIES['keithley4200_pmu']`` and/or ``['keithley4200_smu']`` (see README — Keithley 4200 profiles).

See also: ``Pulse_Testing/README.md`` (How to add a new test, Keithley 4200 profiles).

IMPORTANT NOTE FOR 4200A DATA COLLECTION:
------------------------------------------
There is a known issue with GP parameter numbers for data collection from 
pmu_pulse_read_interleaved.c and pmu_potentiation_depression.c. The current 
implementation uses GP parameters 20 (setV), 22 (setI), 25 (out1), and 31 (PulseTimes)
as shown in the example scripts, but these may need verification. If data collection
is not working correctly, check the GP parameter numbers in the C module output.
"""

from typing import Dict, List, Optional

# All available test function names (must match method names in base_system.py or system implementations)
ALL_TEST_FUNCTIONS = [
    'pulse_read_repeat',
    'pulse_then_read',
    'multi_pulse_then_read',
    'varying_width_pulses',
    'width_sweep_with_reads',
    'width_sweep_with_all_measurements',
    'potentiation_depression_cycle',
    'potentiation_only',
    'depression_only',
    'endurance_test',
    'retention_test',
    'pulse_multi_read',
    'multi_read_only',
    'current_range_finder',
    'relaxation_after_multi_pulse',
    'relaxation_after_multi_pulse_with_pulse_measurement',
    # Additional tests available in some systems
    'voltage_amplitude_sweep',
    'ispp_test',
    'switching_threshold_test',
    'multilevel_programming',
    'pulse_train_varying_amplitudes',
    'laser_and_read',
    'smu_slow_pulse_measure',  # SMU-based slow pulse (much slower than PMU)
    'smu_endurance',  # SMU-based endurance: (SET pulse → Read → RESET pulse → Read) × N cycles
    'smu_retention',  # SMU-based retention: Pulse → Read @ t1 → Read @ t2 → Read @ t3... (retention over time)
    'smu_retention_with_pulse_measurement',  # SMU-based retention with measurements during SET/RESET pulses
    'optical_read_pulsed_light',  # Optical: read at V while laser pulses periodically (2450/2400 only)
    'optical_pulse_train_read',   # Optical: read at V while one laser pulse train (2450/2400 only)
    'optical_pulse_train_pattern_read',  # Optical: read at V while laser fires pattern (11010 etc., 2450/2400 only)
]

# System capability matrix
# True = test is supported, False = test is not supported
SYSTEM_CAPABILITIES: Dict[str, Dict[str, bool]] = {
    'keithley2450': {
        'pulse_read_repeat': True,
        'pulse_then_read': True,
        'multi_pulse_then_read': True,
        'varying_width_pulses': True,
        'width_sweep_with_reads': True,
        'width_sweep_with_all_measurements': True,
        'potentiation_depression_cycle': True,
        'potentiation_only': True,
        'depression_only': True,
        'endurance_test': True,
        'retention_test': True,
        'pulse_multi_read': True,
        'multi_read_only': True,
        'current_range_finder': True,
        'relaxation_after_multi_pulse': True,
        'relaxation_after_multi_pulse_with_pulse_measurement': True,
        'voltage_amplitude_sweep': True,
        'ispp_test': True,
        'switching_threshold_test': True,
        'multilevel_programming': True,
        'pulse_train_varying_amplitudes': True,
        'optical_read_pulsed_light': True,
        'optical_pulse_train_read': True,
        'optical_pulse_train_pattern_read': True,
    },
    # --- Keithley 4200-SCS: PMU vs SMU profiles (shared implementation: keithley4200_core.py) ---
    'keithley4200_pmu': {
        # Fast interleaved PMU + laser_and_read (CH2 PMU for laser)
        'pulse_read_repeat': True,
        'pulse_then_read': True,
        'multi_pulse_then_read': True,
        'varying_width_pulses': False,
        'width_sweep_with_reads': True,
        'width_sweep_with_all_measurements': False,
        'potentiation_depression_cycle': True,
        'potentiation_only': True,
        'depression_only': True,
        'endurance_test': True,
        'retention_test': False,
        'pulse_multi_read': True,
        'multi_read_only': True,
        'current_range_finder': False,
        'relaxation_after_multi_pulse': True,
        'relaxation_after_multi_pulse_with_pulse_measurement': False,
        'voltage_amplitude_sweep': True,
        'ispp_test': True,
        'switching_threshold_test': True,
        'multilevel_programming': True,
        'pulse_train_varying_amplitudes': True,
        'laser_and_read': True,
        'smu_slow_pulse_measure': False,
        'smu_endurance': False,
        'smu_retention': False,
        'smu_retention_with_pulse_measurement': False,
        'optical_read_pulsed_light': False,
        'optical_pulse_train_read': False,
        'optical_pulse_train_pattern_read': False,
    },
    'keithley4200_smu': {
        # Slow SMU scripts + SMU_BiasTimedRead optical coordination
        'pulse_read_repeat': False,
        'pulse_then_read': False,
        'multi_pulse_then_read': False,
        'varying_width_pulses': False,
        'width_sweep_with_reads': False,
        'width_sweep_with_all_measurements': False,
        'potentiation_depression_cycle': False,
        'potentiation_only': False,
        'depression_only': False,
        'endurance_test': False,
        'retention_test': False,
        'pulse_multi_read': False,
        'multi_read_only': False,
        'current_range_finder': False,
        'relaxation_after_multi_pulse': False,
        'relaxation_after_multi_pulse_with_pulse_measurement': False,
        'voltage_amplitude_sweep': False,
        'ispp_test': False,
        'switching_threshold_test': False,
        'multilevel_programming': False,
        'pulse_train_varying_amplitudes': False,
        'laser_and_read': False,
        'smu_slow_pulse_measure': True,
        'smu_endurance': True,
        'smu_retention': True,
        'smu_retention_with_pulse_measurement': True,
        'optical_read_pulsed_light': True,
        'optical_pulse_train_read': True,
        'optical_pulse_train_pattern_read': True,
    },
    'keithley2400': {
        # Tests implemented using direct SCPI commands via Keithley2400Controller
        # All tests use voltage-based pulsing (0V → pulse → 0V) without toggling output on/off
        # NOTE: GPIB speed limitations mean minimum pulse width is ~10ms
        'pulse_read_repeat': True,  # ✅ SCPI-based: Initial Read → (Pulse → Read → Delay) × N
        'pulse_then_read': True,  # ✅ SCPI-based: (Pulse → Delay → Read) × N
        'multi_pulse_then_read': True,  # ✅ SCPI-based: (Pulse×N → Read) × Cycles
        'varying_width_pulses': True,  # ✅ SCPI-based: Test multiple pulse widths
        'width_sweep_with_reads': True,  # ✅ SCPI-based: For each width: (Read→Pulse→Read)×N, Reset
        'width_sweep_with_all_measurements': True,  # ✅ SCPI-based: Width sweep with pulse peak measurements
        'potentiation_depression_cycle': True,  # ✅ SCPI-based: Initial Read → Gradual SET → Gradual RESET
        'potentiation_only': True,  # ✅ SCPI-based: Initial Read → Repeated SET pulses with reads
        'depression_only': True,  # ✅ SCPI-based: Initial Read → Repeated RESET pulses with reads
        'endurance_test': True,  # ✅ SCPI-based: (SET → Read → RESET → Read) × N cycles
        'retention_test': True,  # ✅ SCPI-based: Pulse → Read @ t1 → Read @ t2 → Read @ t3...
        'pulse_multi_read': True,  # ✅ SCPI-based: N pulses then many reads
        'multi_read_only': True,  # ✅ SCPI-based: Just reads, no pulses
        'current_range_finder': True,  # ✅ SCPI-based: Find optimal current measurement range
        'relaxation_after_multi_pulse': True,  # ✅ SCPI-based: 1×Read → N×Pulse → N×Read (measure reads only)
        'relaxation_after_multi_pulse_with_pulse_measurement': True,  # ✅ SCPI-based: 1×Read → N×Pulse(measured) → N×Read
        'voltage_amplitude_sweep': True,  # ✅ SCPI-based: For each voltage: Initial Read → (Pulse → Read) × N → Reset
        'ispp_test': True,  # ✅ SCPI-based: Start at low voltage, increase by step each pulse
        'switching_threshold_test': True,  # ✅ SCPI-based: Try increasing voltages, find minimum that causes switching
        'multilevel_programming': True,  # ✅ SCPI-based: For each level: Reset → Program with pulses → Read
        'pulse_train_varying_amplitudes': True,  # ✅ SCPI-based: Initial Read → (Pulse1 → Read → Pulse2 → Read → ...) × N
        'optical_read_pulsed_light': True,
        'optical_pulse_train_read': True,
        'optical_pulse_train_pattern_read': True,
    },
}

# Setup-only profile: connect works; no pulse tests listed in GUI
SYSTEM_CAPABILITIES['keithley4200_custom'] = {k: False for k in ALL_TEST_FUNCTIONS}

# Legacy alias: same as keithley4200_pmu (saved configs / address auto-detect migration)
SYSTEM_CAPABILITIES['keithley4200a'] = dict(SYSTEM_CAPABILITIES['keithley4200_pmu'])


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
            'retention_test': 'Not yet implemented - would require time-based read measurements after initial pulse',
            'current_range_finder': 'Requires Python-side loop over current ranges (interleaved program uses fixed i_range parameter)',
            'relaxation_after_multi_pulse_with_pulse_measurement': 'Requires NEW C module with pulse measurement capability (interleaved only measures during read windows, not during pulses)',
        },
        'keithley4200_pmu': {
            'varying_width_pulses': 'Not available - use width_sweep_with_reads instead (uses pmu_pulse_read_interleaved with Python-side loop)',
            'width_sweep_with_reads': 'Uses pmu_pulse_read_interleaved: requires Python-side loop calling C program multiple times with different width values (one call per width)',
            'width_sweep_with_all_measurements': 'Requires NEW C module with pulse peak current measurement capability (interleaved only measures during read windows)',
            'retention_test': 'Not yet implemented - would require time-based read measurements after initial pulse',
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
            'endurance_test': 'Fast PMU interleaved test. Select keithley4200_pmu in Connection.',
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

