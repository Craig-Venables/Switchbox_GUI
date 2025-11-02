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

# All available test function names (must match method names in base_system.py)
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
    },
    'keithley4200a': {
        # All False initially - set to True when implementation is ready
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
            'pulse_read_repeat': '4200A implementation not yet ready - LabVIEW/KXCI integration pending',
            'endurance_test': '4200A implementation not yet ready - LabVIEW/KXCI integration pending',
            # Add more specific explanations as needed
        }
    }
    
    system_explanations = explanations.get(system_name, {})
    return system_explanations.get(
        test_function,
        f'Test not yet implemented for {system_name}'
    )

