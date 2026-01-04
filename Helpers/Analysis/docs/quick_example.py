"""
Quick Example - Using After a Sweep
====================================

This shows the simplest way to analyze data right after a sweep completes.
"""

import numpy as np
from Helpers.IV_Analysis import quick_analyze


def example_after_sweep():
    """
    Example: Analyze data immediately after a sweep.
    
    This is the simplest way - just pass your voltage and current arrays.
    """
    # Simulate a sweep that returns voltage and current arrays
    # In real usage, this would come from your measurement system
    voltages = np.array([0, 1, 2, 1, 0, -1, -2, -1, 0])
    currents = np.array([0, 1e-6, 2e-6, 1.5e-6, 0, -1e-6, -2e-6, -1.5e-6, 0])
    
    # One line - get all analysis results
    results = quick_analyze(voltages, currents)
    
    # Access the results
    print(f"Device Type: {results['classification']['device_type']}")
    print(f"Confidence: {results['classification']['confidence']:.1%}")
    print(f"Switching Ratio: {results['resistance_metrics']['switching_ratio_mean']:.1f}")
    print(f"Ron: {results['resistance_metrics']['ron_mean']:.2e} Ω")
    print(f"Roff: {results['resistance_metrics']['roff_mean']:.2e} Ω")
    
    return results


def example_with_metadata():
    """
    Example: Include metadata about the measurement conditions.
    """
    voltages = np.array([0, 1, 2, 1, 0, -1, -2, -1, 0])
    currents = np.array([0, 1e-6, 2e-6, 1.5e-6, 0, -1e-6, -2e-6, -1.5e-6, 0])
    
    # Pass metadata about measurement conditions
    metadata = {
        'led_on': True,
        'led_type': 'UV',
        'led_wavelength': 365,
        'temperature': 25.0,
        'device_name': 'Device_1_Sweep_1'
    }
    
    results = quick_analyze(voltages, currents, metadata=metadata)
    
    print(f"Device: {results['device_info']['name']}")
    print(f"LED Status: {'ON' if results['device_info']['metadata'].get('led_on') else 'OFF'}")
    print(f"Temperature: {results['device_info']['metadata'].get('temperature', 'N/A')} °C")
    
    return results


def example_with_time_data():
    """
    Example: Include time data for pulse/retention measurements.
    """
    voltages = np.array([0, 1, 2, 1, 0])
    currents = np.array([0, 1e-6, 2e-6, 1.5e-6, 0])
    times = np.array([0, 0.1, 0.2, 0.3, 0.4])  # Time in seconds
    
    results = quick_analyze(voltages, currents, time=times)
    
    print(f"Measurement Type: {results['device_info']['measurement_type']}")
    
    return results


def example_integration_pattern():
    """
    Example: How you might integrate this into your sweep code.
    
    This shows the pattern - replace run_your_sweep() with your actual function.
    """
    def run_your_sweep():
        """Your actual sweep function - returns (voltages, currents)"""
        # This is just a placeholder - replace with your real sweep code
        return (
            np.array([0, 1, 2, 1, 0, -1, -2, -1, 0]),
            np.array([0, 1e-6, 2e-6, 1.5e-6, 0, -1e-6, -2e-6, -1.5e-6, 0])
        )
    
    # Pattern: Run sweep, then immediately analyze
    voltages, currents = run_your_sweep()
    
    # One line analysis
    results = quick_analyze(voltages, currents)
    
    # Use results
    if results['classification']['device_type'] == 'memristive':
        print("✓ Memristive device detected!")
        print(f"  Switching Ratio: {results['resistance_metrics']['switching_ratio_mean']:.1f}")
    
    return results


if __name__ == "__main__":
    print("=" * 60)
    print("Quick Analysis Examples")
    print("=" * 60)
    
    print("\n1. Basic Analysis:")
    example_after_sweep()
    
    print("\n2. With Metadata:")
    example_with_metadata()
    
    print("\n3. With Time Data:")
    example_with_time_data()
    
    print("\n4. Integration Pattern:")
    example_integration_pattern()

