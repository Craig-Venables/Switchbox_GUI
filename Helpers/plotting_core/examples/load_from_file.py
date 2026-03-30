"""
Example: Loading data from a file and plotting.

This shows how to integrate plotting_core with your data loading code.

To run this example:
    1. Install the package: pip install -e .
    2. Or add the parent directory to your path
    3. Update the data_file path to point to your data
"""

import sys
from pathlib import Path

# Add code directory to path if not installed as package
code_dir = Path(__file__).parent.parent.parent
if str(code_dir) not in sys.path:
    sys.path.insert(0, str(code_dir))

import numpy as np
from plotting_core import UnifiedPlotter


def load_iv_data(file_path: Path):
    """
    Load IV data from a text file.
    
    Expected format:
        voltage current [time]
        -1.5    1e-6   0.0
        -1.4    2e-6   0.1
        ...
    """
    data = np.loadtxt(file_path, skiprows=1)
    voltage = data[:, 0]
    current = data[:, 1]
    time = data[:, 2] if data.shape[1] > 2 else None
    return voltage, current, time


def main():
    # Initialize plotter
    plotter = UnifiedPlotter(save_dir="output/plots")
    
    # Load your data file (adjust path as needed)
    data_file = Path("your_data_file.txt")
    
    if data_file.exists():
        voltage, current, time = load_iv_data(data_file)
        
        # Generate all plots
        plotter.plot_all(
            voltage=voltage,
            current=current,
            time=time,
            device_name=data_file.stem,
        )
        
        print(f"Plots saved for {data_file.name}")
    else:
        print(f"Data file not found: {data_file}")
        print("Please update the path in this script to point to your data file.")


if __name__ == "__main__":
    main()

