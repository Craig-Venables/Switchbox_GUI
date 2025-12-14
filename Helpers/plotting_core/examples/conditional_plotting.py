"""
Example: Conditional plotting based on device characteristics.

This demonstrates how to plot basic IV for all devices,
but only generate advanced analysis for memristive devices.
"""

import sys
from pathlib import Path

# Add code directory to path if not installed as package
code_dir = Path(__file__).parent.parent.parent
if str(code_dir) not in sys.path:
    sys.path.insert(0, str(code_dir))

import numpy as np
from plotting_core import UnifiedPlotter


def is_memristive(voltage, current):
    """
    Example function to determine if device is memristive.
    
    Replace with your actual classification logic.
    """
    # Simple heuristic: check for hysteresis
    # (This is just an example - use your actual classification)
    if len(voltage) < 10:
        return False
    
    # Check for significant current variation
    current_range = np.max(np.abs(current)) - np.min(np.abs(current))
    if current_range < 1e-9:
        return False
    
    # Check for hysteresis (forward vs reverse sweep difference)
    max_v_idx = np.argmax(voltage)
    forward_current = np.abs(current[:max_v_idx+1])
    reverse_current = np.abs(current[max_v_idx:])
    
    if len(forward_current) > 0 and len(reverse_current) > 0:
        avg_forward = np.mean(forward_current)
        avg_reverse = np.mean(reverse_current)
        if avg_forward > 0 and avg_reverse > 0:
            ratio = max(avg_forward, avg_reverse) / min(avg_forward, avg_reverse)
            return ratio > 1.5  # Some hysteresis detected
    
    return False


def process_device(plotter, voltage, current, time, device_name, device_type=None):
    """
    Process a single device with conditional plotting.
    
    Two approaches shown:
    1. Using plot_conditional() - simplest one-liner
    2. Using plot_basic() + plot_memristive_analysis() - more control
    
    Args:
        plotter: UnifiedPlotter instance
        voltage: Voltage data
        current: Current data
        time: Optional time data
        device_name: Device identifier
        device_type: Optional device type ('memristive', 'ohmic', etc.)
                     If None, will be auto-detected
    """
    # Determine if memristive (if not provided)
    if device_type is None:
        memristive_flag = is_memristive(voltage, current)
        device_type = "memristive" if memristive_flag else "non-memristive"
    else:
        memristive_flag = (device_type == "memristive")
    
    # Approach 1: Use plot_conditional() - simplest way
    print(f"  Processing {device_name} (type: {device_type})...")
    results = plotter.plot_conditional(
        voltage=voltage,
        current=current,
        time=time,
        device_name=device_name,
        is_memristive=memristive_flag,
    )
    
    if memristive_flag:
        print(f"  Generated full analysis for memristive device {device_name}")
    else:
        print(f"  Generated basic IV only for {device_name}")
    
    return results

    # Approach 2: Manual control (commented out - use if you need more control)
    # print(f"  Plotting basic IV for {device_name}...")
    # basic_results = plotter.plot_basic(
    #     voltage=voltage,
    #     current=current,
    #     time=time,
    #     device_name=device_name,
    # )
    # 
    # if memristive_flag:
    #     print(f"  Device {device_name} is memristive - generating full analysis...")
    #     advanced_results = plotter.plot_memristive_analysis(
    #         voltage=voltage,
    #         current=current,
    #         device_name=device_name,
    #     )
    #     return {**basic_results, **advanced_results}
    # else:
    #     print(f"  Device {device_name} is {device_type} - skipping advanced analysis")
    #     return basic_results


def main():
    # Initialize plotter
    plotter = UnifiedPlotter(save_dir="output/plots")
    
    # Example: Process multiple devices
    devices = [
        {
            "name": "Device_1",
            "voltage": np.linspace(-1.5, 1.5, 200),
            "current": 1e-6 * np.sin(np.linspace(-1.5, 1.5, 200) * np.pi) * np.exp(-np.linspace(-1.5, 1.5, 200)**2),
            "time": None,
            "type": None,  # Will be auto-detected
        },
        {
            "name": "Device_2",
            "voltage": np.linspace(-1.5, 1.5, 200),
            "current": 1e-9 * np.linspace(-1.5, 1.5, 200),  # Linear (ohmic)
            "time": None,
            "type": "ohmic",  # Explicitly set
        },
    ]
    
    print("Processing devices with conditional plotting...")
    for device in devices:
        results = process_device(
            plotter=plotter,
            voltage=device["voltage"],
            current=device["current"],
            time=device["time"],
            device_name=device["name"],
            device_type=device["type"],
        )
        print(f"  Generated {len(results)} plot(s) for {device['name']}\n")
    
    print("Done! Check output/plots/ for generated files")
    print("\nNote: Only memristive devices have advanced analysis plots")


if __name__ == "__main__":
    main()

