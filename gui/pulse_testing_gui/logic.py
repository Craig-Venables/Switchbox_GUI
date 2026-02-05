"""
Pulse Testing GUI – business logic
==================================

Device discovery and test execution helpers. Keeps main.py focused on UI wiring.
"""

from typing import List, Optional


def get_available_devices(fallback_address: Optional[str] = None) -> List[str]:
    """
    Scan for available USB and GPIB devices (e.g. Keithley).

    Args:
        fallback_address: If no devices found, return this as single-item list.

    Returns:
        List of resource strings (e.g. USB0::..., GPIB0::...).
    """
    devices: List[str] = []
    try:
        import pyvisa
        rm = pyvisa.ResourceManager()
        resources = rm.list_resources()
        for res in resources:
            if res.startswith("USB") or res.startswith("GPIB"):
                devices.append(res)
        if not devices and fallback_address:
            devices = [fallback_address]
    except Exception as e:
        if fallback_address:
            devices = [fallback_address]
    return devices


def run_test_worker(system_wrapper, func_name: str, params: dict, progress_callback=None):
    """
    Run one test on the system wrapper (call from background thread).

    Args:
        system_wrapper: Pulse_Testing SystemWrapper instance (must be connected).
        func_name: Test function name (e.g. 'pulse_read_repeat').
        params: Dict of test parameters (may be mutated if progress_callback is set).
        progress_callback: Optional callable(partial_results) for incremental updates.

    Returns:
        (results_dict, None) on success, or (None, exception) on error.
    """
    if progress_callback and func_name in (
        "smu_endurance",
        "smu_retention",
        "smu_retention_with_pulse_measurement",
    ):
        params = dict(params, progress_callback=progress_callback)
    try:
        results = system_wrapper.run_test(test_function=func_name, params=params)
        return (results, None)
    except Exception as e:
        return (None, e)
