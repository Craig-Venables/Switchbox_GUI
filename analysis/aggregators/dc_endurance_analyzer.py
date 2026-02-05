"""
DC Endurance Analyzer
=====================

Purpose:
--------
Analyzes DC endurance data by extracting current values at specific voltages
across multiple cycles. Based on Pandas_test/memristors/analysis.py DC endurance
analysis functionality.

What This Module Does:
----------------------
1. Extracts current values at specific voltages (0.1V, 0.15V, 0.2V) across cycles
2. Handles both positive and negative voltage sweeps
3. Identifies ON/OFF states from forward/reverse sweeps
4. Generates plots showing current vs cycle for each voltage
5. Exports CSV data for further analysis

Key Classes:
------------
- DCEnduranceAnalyzer: Main analyzer class

Key Methods:
------------
- extract_current_at_voltages(): Extract current values at target voltages
- plot_current_vs_cycle(): Generate individual plots per voltage
- plot_endurance_summary(): Generate comprehensive multi-panel summary
- export_to_csv(): Export data to CSV files

Usage:
------
    from analysis.aggregators.dc_endurance_analyzer import DCEnduranceAnalyzer
    
    analyzer = DCEnduranceAnalyzer(
        split_voltage_data=[v1, v2, ...],  # List of voltage arrays, one per cycle
        split_current_data=[c1, c2, ...],  # List of current arrays, one per cycle
        file_name="device_sweep",
        device_path="path/to/sample/section/device_num"  # Device directory path
    )
    analyzer.analyze_and_plot()

Output:
-------
Saved to: {device_path}/Graphs/dc endurance/
- Data/{file_name}_endurance_{voltage}V.csv
- {file_name}_endurance_{voltage}V.png (individual plots)
- {file_name}_endurance_summary.png (summary plot with all voltages)

Called By:
----------
- comprehensive_analyzer.py → ComprehensiveAnalyzer (when endurance data detected)

Dependencies:
-------------
- numpy, pandas, matplotlib
- Data format: Lists of voltage/current arrays (one per cycle)
"""

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Sequence


class DCEnduranceAnalyzer:
    """
    Analyzer for DC endurance measurements.
    
    Extracts current values at specific voltages across cycles and generates
    plots showing degradation over time.
    """
    
    def __init__(
        self,
        split_voltage_data: List[Sequence[float]],
        split_current_data: List[Sequence[float]],
        file_name: str,
        device_path: str,
        voltages: Optional[List[float]] = None,
    ):
        """
        Initialize DC endurance analyzer.
        
        Args:
            split_voltage_data: List of voltage arrays, one per cycle
            split_current_data: List of current arrays, one per cycle
            file_name: Base filename for output files
            device_path: Path to device directory (e.g., {sample_dir}/{section}/{device_num})
            voltages: List of voltages to extract (default: [0.1, 0.15, 0.2])
        """
        self.split_v_data = [np.asarray(v, dtype=float) for v in split_voltage_data]
        self.split_c_data = [np.asarray(c, dtype=float) for c in split_current_data]
        self.file_name = file_name
        self.voltages = voltages if voltages is not None else [0.1, 0.15, 0.2]
        self.num_sweeps = len(split_voltage_data)
        
        # Set up save directories - save to device's Graphs/dc endurance/ folder
        device_path_obj = Path(device_path)
        self.endurance_dir = device_path_obj / "Graphs" / "dc endurance"
        self.data_dir = self.endurance_dir / "Data"
        self.endurance_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Storage for extracted data
        self.extracted_data: Dict[float, pd.DataFrame] = {}
    
    def find_nearest_indices(self, array: np.ndarray, value: float, tolerance: float = 1e-3) -> np.ndarray:
        """
        Find indices in array where values are close to target value.
        
        Args:
            array: Array to search
            value: Target value
            tolerance: Tolerance for matching
            
        Returns:
            Array of matching indices
        """
        return np.where(np.isclose(array, value, atol=tolerance))[0]
    
    def extract_current_at_voltages(self) -> Dict[float, pd.DataFrame]:
        """
        Extract current values at specific voltages across all cycles.
        
        Returns:
            Dictionary mapping voltage to DataFrame with cycle data
        """
        # Initialize results dictionary
        all_voltages = self.voltages + [-v for v in self.voltages]
        results = {v: [] for v in all_voltages}
        
        # Iterate over each cycle
        for cycle in range(1, self.num_sweeps + 1):
            v_data = self.split_v_data[cycle - 1]
            c_data = self.split_c_data[cycle - 1]
            
            # Extract current at each positive voltage
            for v in self.voltages:
                indices = self.find_nearest_indices(v_data, v)
                if len(indices) >= 2:
                    # Expect at least two matches (forward and reverse sweep)
                    # Take first two matches
                    current_values = [float(c_data[indices[0]]), float(c_data[indices[1]])]
                else:
                    current_values = [np.nan, np.nan]
                results[v].append(current_values)
            
            # Extract current at each negative voltage
            for v in self.voltages:
                neg_v = -v
                indices = self.find_nearest_indices(v_data, neg_v)
                if len(indices) >= 2:
                    current_values = [float(c_data[indices[0]]), float(c_data[indices[1]])]
                else:
                    current_values = [np.nan, np.nan]
                results[neg_v].append(current_values)
        
        # Convert results to DataFrames
        dfs = {}
        for v in self.voltages:
            # Combine positive and negative voltage data
            pos_data = pd.DataFrame(
                results[v],
                columns=[f'Current_Forward_(OFF)_{v}V', f'Current_Reverse_(ON)_{v}V']
            )
            neg_data = pd.DataFrame(
                results[-v],
                columns=[f'Current_Forward_(ON)_{-v}V', f'Current_Reverse_(OFF)_{-v}V']
            )
            combined_df = pd.concat([pos_data, neg_data], axis=1)
            combined_df.index += 1  # Cycle numbers start from 1
            dfs[v] = combined_df
        
        self.extracted_data = dfs
        return dfs
    
    def plot_current_vs_cycle(self, voltage: float, df: pd.DataFrame) -> None:
        """Plot current vs cycle for a specific voltage (delegates to plotting.endurance)."""
        from plotting.endurance import plot_current_vs_cycle as _plot
        _plot(voltage, df, self.endurance_dir, self.file_name)
    
    def plot_endurance_summary(self) -> None:
        """Create comprehensive summary plot (delegates to plotting.endurance)."""
        if not self.extracted_data:
            return
        from plotting.endurance import plot_endurance_summary as _plot
        _plot(self.voltages, self.extracted_data, self.endurance_dir, self.file_name)
    
    def export_to_csv(self) -> None:
        """
        Export extracted current values to CSV files.
        """
        for v in self.voltages:
            df = self.extracted_data[v]
            csv_file = self.data_dir / f'{self.file_name}_endurance_{v}V.csv'
            df.to_csv(csv_file, index_label='Cycle')
    
    def analyze_and_plot(self) -> Dict[float, pd.DataFrame]:
        """
        Run complete DC endurance analysis: extract, plot, and export.
        
        Returns:
            Dictionary of DataFrames with extracted data
        """
        # Extract current values
        dfs = self.extract_current_at_voltages()
        
        # Plot individual plots for each voltage
        for v in self.voltages:
            self.plot_current_vs_cycle(v, dfs[v])
        
        # Plot summary
        self.plot_endurance_summary()
        
        # Export CSV
        self.export_to_csv()
        
        return dfs
