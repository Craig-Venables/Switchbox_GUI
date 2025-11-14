"""
Test Capability Definitions
===========================

Defines which tests are supported by each measurement system.
Easy to update: change boolean values to enable/disable test support.

To add 4200A support for a test:
1. Implement the test method in keithley4200a.py
2. Change the corresponding boolean to True in SYSTEM_CAPABILITIES['keithley4200a']
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
    },
    'keithley4200a': {
        # Tests implemented in keithley4200_kxci_scripts.py
        # See 4200A_TEST_STATUS.md for detailed status
        'pulse_read_repeat': False,  # ❌ Requires NEW C module: pulse_read_repeat_dual_channel.c
        'pulse_then_read': False,  # Not available - use pulse_read_repeat instead
        'multi_pulse_then_read': True,  # ⚠️ Works but limited to 8 reads (needs C modification for N reads)
        'varying_width_pulses': False,  # Not available - use width_sweep_with_reads instead
        'width_sweep_with_reads': True,  # ⚠️ Works but needs Python-side loop over widths
        'width_sweep_with_all_measurements': False,  # ❌ Requires NEW C module with pulse measurement
        'potentiation_depression_cycle': False,  # Not available/not working
        'potentiation_only': True,
        'depression_only': True,
        'endurance_test': True,
        'retention_test': False,  # Not yet implemented
        'pulse_multi_read': True,  # ✅ Fully working
        'multi_read_only': True,  # ✅ Fully working
        'current_range_finder': False,  # ❌ Requires NEW C module (or Python-side loop)
        'relaxation_after_multi_pulse': True,  # ✅ Fully working
        'relaxation_after_multi_pulse_with_pulse_measurement': False,  # ❌ Requires NEW C module with pulse measurement
        # Additional tests available in 4200A
        'voltage_amplitude_sweep': True,
        'ispp_test': True,
        'switching_threshold_test': True,
        'multilevel_programming': True,
        'pulse_train_varying_amplitudes': True,
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
        'keithley4200a': {
            'pulse_read_repeat': 'Can use pmu_retention_dual_channel.c if we remove min-8 requirement. Need to modify C code validation (line 266) and Python validation (line 310 in run_pmu_retention.py). Pattern: Initial Read → (Pulse → Read → Delay) × N',
            'multi_pulse_then_read': 'Currently limited to 8 reads per cycle. C module needs modification to support N reads (1-1000)',
            'width_sweep_with_reads': 'Works but needs Python-side loop to call C module multiple times (once per width)',
            'width_sweep_with_all_measurements': 'Requires NEW C module with pulse peak current measurement capability',
            'relaxation_after_multi_pulse_with_pulse_measurement': 'Requires NEW C module: relaxation_with_pulse_measurement.c to measure pulse peaks',
            'current_range_finder': 'Requires NEW C module or Python-side loop over current ranges',
            # Add more specific explanations as needed
        }
    }
    
    system_explanations = explanations.get(system_name, {})
    return system_explanations.get(
        test_function,
        f'Test not yet implemented for {system_name}'
    )

