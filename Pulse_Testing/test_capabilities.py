"""
Test Capability Definitions
===========================

Defines which tests are supported by each measurement system.
Easy to update: change boolean values to enable/disable test support.

To add 4200A support for a test:
1. Implement the test method in keithley4200a.py
2. Change the corresponding boolean to True in SYSTEM_CAPABILITIES['keithley4200a']

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
    'keithley4200a': {
        # Tests implemented using pmu_pulse_read_interleaved.c and pmu_potentiation_depression.c
        # The interleaved program is highly versatile and can be configured for most test patterns
        # NOTE: There is a known issue with GP parameter numbers for data collection - 
        #       the method from examples is used but may need verification (GP 20, 22, 25, 31)
        'pulse_read_repeat': True,  # ✅ Uses pmu_pulse_read_interleaved: num_cycles=N, num_reads=1, num_pulses_per_group=1
        'pulse_then_read': True,  # ✅ Uses pmu_pulse_read_interleaved: same as pulse_read_repeat
        'multi_pulse_then_read': True,  # ✅ Uses pmu_pulse_read_interleaved: configurable num_pulses_per_group and num_reads
        'varying_width_pulses': False,  # Not available - use width_sweep_with_reads instead
        'width_sweep_with_reads': True,  # ⚠️ Uses pmu_pulse_read_interleaved: requires Python-side loop calling C program multiple times with different width values
        'width_sweep_with_all_measurements': False,  # ❌ Requires NEW C module with pulse measurement capability
        'potentiation_depression_cycle': True,  # ✅ Uses pmu_potentiation_depression.c for alternating potentiation/depression cycles
        'potentiation_only': True,  # ✅ Uses pmu_pulse_read_interleaved: positive pulses only
        'depression_only': True,  # ✅ Uses pmu_pulse_read_interleaved: negative pulses only
        'endurance_test': True,  # ✅ Uses pmu_pulse_read_interleaved: can configure alternating SET/RESET pattern
        'retention_test': False,  # Not yet implemented
        'pulse_multi_read': True,  # ✅ Uses pmu_pulse_read_interleaved: num_pulses_per_group=N, num_reads=M
        'multi_read_only': True,  # ✅ Uses pmu_pulse_read_interleaved: num_pulses_per_group=0, num_reads=N
        'current_range_finder': False,  # ❌ Requires Python-side loop over current ranges
        'relaxation_after_multi_pulse': True,  # ✅ Uses pmu_pulse_read_interleaved: 1 read → N pulses → M reads
        'relaxation_after_multi_pulse_with_pulse_measurement': False,  # ❌ Requires NEW C module with pulse measurement capability
        # Additional tests available in 4200A
        'voltage_amplitude_sweep': True,
        'ispp_test': True,
        'switching_threshold_test': True,
        'multilevel_programming': True,
        'pulse_train_varying_amplitudes': True,
        'laser_and_read': True,  # ✅ Uses Read_With_Laser_Pulse_SegArb.c: CH1 continuous reads, CH2 independent laser pulse
        'smu_slow_pulse_measure': True,  # ⚠️ Uses SMU (not PMU) - much slower but supports pulse widths up to 480 seconds
        'smu_endurance': True,  # ⚠️ Uses SMU (not PMU) - (SET pulse → Read → RESET pulse → Read) × N cycles, supports pulse widths up to 480 seconds
        'smu_retention': True,  # ⚠️ Uses SMU (not PMU) - Pulse → Read @ t1 → Read @ t2 → Read @ t3... (retention over time), supports pulse widths up to 480 seconds
        'smu_retention_with_pulse_measurement': True,  # ⚠️ Uses SMU (not PMU) - measures resistance DURING SET/RESET pulses, supports pulse widths up to 480 seconds
        'optical_read_pulsed_light': True,   # Uses SMU_BiasTimedRead + laser from Python (thread + optical_start_delay_s)
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


def is_test_supported(system_name: str, test_function: str) -> bool:
    """Check if a test is supported by a specific system.
    
    Args:
        system_name: System identifier (e.g., 'keithley2450', 'keithley4200a')
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
            # Add more specific explanations as needed
        }
    }
    
    system_explanations = explanations.get(system_name, {})
    return system_explanations.get(
        test_function,
        f'Test not yet implemented for {system_name}'
    )

