"""
Basic usage example for plotting package.

This example demonstrates the simplest way to use the unified plotter.

To run this example:
    1. Install the package: pip install -e .
    2. Or add the parent directory to your path
"""

import sys
from pathlib import Path

# Add code directory to path if not installed as package
code_dir = Path(__file__).parent.parent.parent
if str(code_dir) not in sys.path:
    sys.path.insert(0, str(code_dir))

import numpy as np
from plotting import UnifiedPlotter


def main():
    # Initialize plotter with output directory
    plotter = UnifiedPlotter(save_dir="output/plots")
    
    # Generate synthetic IV data (replace with your actual data)
    voltage = np.linspace(-1.5, 1.5, 200)
    current = 1e-6 * np.sin(voltage * np.pi) * np.exp(-voltage**2)
    time = np.arange(len(voltage)) * 0.01
    
    # Generate all plots with one call
    results = plotter.plot_all(
        voltage=voltage,
        current=current,
        time=time,
        device_name="Example_Device",
    )
    
    print("All plots generated and saved!")
    print(f"Check {plotter.save_dir} for generated files")


if __name__ == "__main__":
    main()

