"""
Sample-Level Analysis Orchestrator
===================================

Purpose:
--------
Generates comprehensive analysis plots and statistics for entire samples (100+ devices)
using existing device tracking and research data. Provides publication-quality visualizations
and Origin-ready data exports.

What This Module Does:
----------------------
1. Loads device tracking data from sample_analysis/analysis/device_tracking/
2. Optionally filters by code_name (test type)
3. Generates 13 advanced plot types:
   1. Memristivity Score Heatmap (spatial distribution)
   2. Conduction Mechanism Distribution (pie + bar charts)
   3. Memory Window Quality Distribution (box plots)
   4. Hysteresis Shape Radar (polar plot, memristive only)
   5. Enhanced Classification Scatter (Ron vs Roff with multi-dimensional encoding)
   6. Forming Progress Tracking (multi-line plot over time)
   7. Warning Flag Summary (bar chart of warning types)
   8. Research Diagnostics Scatter Matrix (pairplot, requires seaborn)
   9. Power & Energy Efficiency (scatter + box plots)
   10. Device Leaderboard (top 20 devices by composite score)
   11. Spatial Distribution Maps (3 heatmaps: memristivity, quality, switching ratio)
   12. Forming Status Distribution (pie + bar charts)
   13. Device Size Comparison (box plots + bar charts comparing 100um, 200um, 400um)
   14. Metric Correlation Heatmap (correlations between key metrics)
   15. Section Performance Comparison (grouped bar charts comparing sections)
   16. Resistance Distribution Comparison (histograms of Ron/Roff distributions)
   17. Yield and Performance Dashboard (summary dashboard with key statistics)
   18. Device Type vs Size Matrix (distribution of device types across sizes)
   19. Quality Score Breakdown (detailed quality component analysis)
   20. Confidence vs Performance Scatter (relationship between confidence and performance)
   21. Voltage Range Analysis (test voltage ranges and performance relationships)
   22. Performance Stability Analysis (device stability over multiple measurements)
   23. Warning Analysis Dashboard (detailed warning impact analysis)
   24. On/Off Ratio vs Switching Ratio (comparison of ratio metrics)
   25. Section Spatial Gradient (spatial trends across sections)
4. Generates 3 specialized I-V overlay plots in plots/size_comparison/ folder (grouped by device size)
5. Exports all data in Origin-ready CSV format

Key Classes:
------------
- SampleAnalysisOrchestrator: Main sample analysis class

Key Methods:
------------
- load_all_devices(): Loads device tracking data (optionally filtered by code_name)
- generate_all_plots(): Generates all 25 plot types + 3 specialized size comparison plots
- export_origin_data(): Exports Origin-ready CSV files
- Individual plot methods: plot_memristivity_heatmap(), plot_conduction_mechanisms(), etc.

Usage:
------
    from analysis import SampleAnalysisOrchestrator
    
    # Analyze specific code_name
    analyzer = SampleAnalysisOrchestrator(
        sample_directory="path/to/sample",
        code_name="St_v1"  # Optional: filter by code_name
    )
    analyzer.set_log_callback(lambda msg: print(msg))  # Optional progress logging
    device_count = analyzer.load_all_devices()
    analyzer.generate_all_plots()
    analyzer.export_origin_data()
    
    # Analyze all measurements (no filter)
    analyzer = SampleAnalysisOrchestrator(sample_directory="path/to/sample", code_name=None)

Output:
-------
Saved to: {sample_dir}/sample_analysis/
- plots/{code_name}/: Plot images (01_memristivity_heatmap.png, etc.) for code_name-specific analysis
- plots/: Overall analysis plots (if code_name=None)
- plots/size_comparison/: Specialized I-V overlay plots grouped by device size
- plots/data_origin_formatted/{code_name}/: Origin-ready CSV files
- analysis/device_tracking/: Device tracking JSON files
- analysis/device_research/: Device research JSON files
- analysis/device_summaries/: Device summary files

Called By:
----------
- comprehensive_analyzer.py → ComprehensiveAnalyzer.run_comprehensive_analysis()
  (runs sample analysis for each code_name + overall analysis)

Dependencies:
-------------
- Reads from: sample_analysis/analysis/device_tracking/ and analysis/device_research/
- Requires: numpy, pandas, matplotlib, (optional: seaborn for plot 8)
- Data format: JSON files in analysis/device_tracking/ and analysis/device_research/ directories
"""

import os
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
try:
    import seaborn as sns
    SEABORN_AVAILABLE = True
except ImportError:
    SEABORN_AVAILABLE = False
    print("[SAMPLE] Warning: seaborn not available. Plot 8 (Research Diagnostics) will be skipped.")

from typing import Dict, List, Tuple, Optional, Callable
from datetime import datetime
import warnings

from plotting.sample_plots import SamplePlots

# Suppress matplotlib warnings
warnings.filterwarnings('ignore', category=UserWarning)

# Device size mapping: sections to device dimensions
DEVICE_SIZE_MAPPING = {
    'a': {'size': '200x200um', 'area_um2': 40000},
    'd': {'size': '200x200um', 'area_um2': 40000},
    'h': {'size': '200x200um', 'area_um2': 40000},
    'k': {'size': '200x200um', 'area_um2': 40000},
    'b': {'size': '100x100um', 'area_um2': 10000},
    'e': {'size': '100x100um', 'area_um2': 10000},
    'i': {'size': '100x100um', 'area_um2': 10000},
    'l': {'size': '100x100um', 'area_um2': 10000},
    'c': {'size': '400x400um', 'area_um2': 160000},
    'j': {'size': '400x400um', 'area_um2': 160000},
}


class SampleAnalysisOrchestrator:
    """Orchestrate full sample analysis with 13 advanced plot types + 3 specialized size comparison plots."""
    
    def __init__(self, sample_directory: str, code_name: Optional[str] = None):
        """
        Args:
            sample_directory: Path to sample folder containing analysis/ subfolder with
                            device_tracking/, device_research/, etc.
            code_name: Optional code name (test_type) to filter by. If provided, only
                      devices/measurements with this code_name will be included.
        """
        self.sample_dir = sample_directory
        self.sample_name = os.path.basename(sample_directory)
        self.code_name_filter = code_name  # Filter by code_name like old module
        
        # Data directories - all under sample_analysis/analysis/
        self.tracking_dir = os.path.join(sample_directory, "sample_analysis", "analysis", "device_tracking")
        self.research_dir = os.path.join(sample_directory, "sample_analysis", "analysis", "device_research")
        
        # Unified output directory structure - everything in sample_analysis/ with subfolders
        self.output_dir = os.path.join(sample_directory, "sample_analysis")
        if code_name:
            # Use subfolder for code_name-specific analysis
            self.plots_dir = os.path.join(self.output_dir, "plots", code_name)
            self.data_origin_formatted_dir = os.path.join(self.output_dir, "plots", "data_origin_formatted", code_name)
        else:
            # Overall analysis (no code_name filter) - plots go directly in plots/
            self.plots_dir = os.path.join(self.output_dir, "plots")
            self.data_origin_formatted_dir = os.path.join(self.output_dir, "plots", "data_origin_formatted", "overall")
        
        # Device summaries go in analysis/ folder
        self.summaries_dir = os.path.join(self.output_dir, "analysis", "device_summaries")
        
        # Create output directories
        os.makedirs(self.plots_dir, exist_ok=True)
        os.makedirs(self.data_origin_formatted_dir, exist_ok=True)
        os.makedirs(self.summaries_dir, exist_ok=True)
        
        # Size comparison plots directory (specialized I-V overlays) - always in plots/size_comparison/
        self.size_comparison_dir = os.path.join(self.output_dir, "plots", "size_comparison")
        os.makedirs(self.size_comparison_dir, exist_ok=True)
        
        # Data containers
        self.devices_data = []
        self.memristive_devices = []
        self.research_data = {}  # device_id -> list of research JSONs
        
        # Logging callback for progress updates
        self.log_callback: Optional[Callable] = None
    
    def set_log_callback(self, callback: Callable) -> None:
        """Set callback function for logging progress updates."""
        self.log_callback = callback
    
    def _log(self, message: str) -> None:
        """Log message using callback if available, otherwise print."""
        if self.log_callback:
            self.log_callback(message)
        else:
            print(message)
        
    def _is_valid_code_name(self, code_name: str) -> bool:
        """
        Check if code_name is valid (not purely numeric).
        Numeric-only strings are misclassified code names and should be excluded.
        """
        if not code_name:
            return False
        # Check if code_name is purely numeric (misclassified)
        if code_name.isdigit():
            return False
        return True
    
    def _extract_code_name_from_filename(self, filename: str) -> Optional[str]:
        """
        Extract code_name (test_type) from filename, matching old module behavior.
        
        Expected format: <sweep_num>-<sweep_type>-<voltage>v-<step_voltage>sv-<step_delay>sd-Py-<code_name>-...
        Example: "1-FS-0.5v-0.05sv-0.05sd-Py-St_v1-3.txt"
        
        Returns code_name from position 6 (0-based index) after splitting by '-'
        """
        try:
            filename = filename.replace('.txt', '')
            parts = filename.split('-')
            if len(parts) > 6:
                code_name = parts[6]  # code_name is in position 6
                # Filter out numeric-only code names (misclassified)
                if self._is_valid_code_name(code_name):
                    return code_name
        except (IndexError, AttributeError):
            pass
        return None
    
    def _find_code_name_for_device(self, device_id: str) -> Optional[str]:
        """
        Find code_name for a device by scanning device directory for measurement files.
        Matches old module's detect_test_type() behavior.
        Returns the first code_name found (any valid code_name in the device folder).
        """
        # Try to find device directory: sample_name/section/device_number/
        # Device ID format: sample_letter_number (e.g., "test_B_6")
        parts = device_id.split('_')
        if len(parts) >= 3:
            try:
                section = parts[-2]  # Letter
                device_num = parts[-1]  # Number
                device_dir = os.path.join(self.sample_dir, section, device_num)
                
                if os.path.exists(device_dir):
                    # Scan all files to find any valid code_name
                    for file in os.listdir(device_dir):
                        if file.endswith('.txt') and file != 'log.txt':
                            code_name = self._extract_code_name_from_filename(file)
                            if code_name:
                                return code_name
            except Exception:
                pass
        return None
    
    def load_all_devices(self) -> int:
        """Load all device tracking data, optionally filtered by code_name."""
        count = 0
        if not os.path.exists(self.tracking_dir):
            self._log(f"No tracking directory found: {self.tracking_dir}")
            return 0
        
        self._log("Loading device tracking data...")
        tracking_files = [f for f in os.listdir(self.tracking_dir) if f.endswith('_history.json')]
        total_files = len(tracking_files)
        
        for idx, file in enumerate(tracking_files, 1):
            if file.endswith('_history.json'):
                try:
                    file_path = os.path.join(self.tracking_dir, file)
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                        device_id = data.get('device_id', file.replace('_history.json', ''))
                        
                        # Filter by code_name if specified
                        if self.code_name_filter:
                            # Check if any measurement has this code_name
                            # First try to find code_name from device directory
                            device_code_name = self._find_code_name_for_device(device_id)
                            
                            # Also check measurements for code_name in metadata (if we add it later)
                            measurements = data.get('measurements', [])
                            measurement_code_name = None
                            for m in measurements:
                                # Check if measurement has code_name in metadata (future enhancement)
                                if m.get('code_name') == self.code_name_filter:
                                    measurement_code_name = self.code_name_filter
                                    break
                            
                            # Use device-level code_name if found, otherwise skip if filter doesn't match
                            if device_code_name != self.code_name_filter and measurement_code_name != self.code_name_filter:
                                continue
                        
                        # Get latest measurement (or filter by code_name if specified)
                        if data.get('measurements'):
                            # If filtering by code_name, try to find measurement with matching code_name
                            if self.code_name_filter:
                                matching_measurement = None
                                for m in reversed(data['measurements']):  # Check most recent first
                                    if m.get('code_name') == self.code_name_filter:
                                        matching_measurement = m
                                        break
                                if matching_measurement:
                                    latest = matching_measurement
                                else:
                                    # Fallback to latest if no code_name match found
                                    latest = data['measurements'][-1]
                            else:
                                latest = data['measurements'][-1]
                            
                            device_info = {
                                'device_id': device_id,
                                'classification': latest.get('classification', {}),
                                'resistance': latest.get('resistance', {}),
                                'voltage': latest.get('voltage', {}),
                                'hysteresis': latest.get('hysteresis', {}),
                                'quality': latest.get('quality', {}),
                                'warnings': latest.get('warnings', []),
                                'total_measurements': data.get('total_measurements', 0),
                                'all_measurements': data.get('measurements', [])  # For forming tracking
                            }
                            
                            # Add device size metadata based on section letter
                            parts = device_id.split('_')
                            if len(parts) >= 3:
                                section_letter = parts[-2].lower()  # Section letter
                                if section_letter in DEVICE_SIZE_MAPPING:
                                    size_info = DEVICE_SIZE_MAPPING[section_letter]
                                    device_info['section'] = parts[-2].upper()
                                    device_info['device_size'] = size_info['size']
                                    device_info['area_um2'] = size_info['area_um2']
                            
                            self.devices_data.append(device_info)
                            
                            # Track memristive devices
                            if device_info['classification'].get('device_type') == 'memristive':
                                self.memristive_devices.append(device_info)
                            
                            count += 1
                            
                            # Log progress every 10 devices or at the end
                            if count % 10 == 0 or idx == total_files:
                                remaining = total_files - idx
                                self._log(f"Loaded {count} device(s) - {idx}/{total_files} files processed, {remaining} remaining")
                except Exception as e:
                    self._log(f"Error loading {file}: {e}")
        
        # Load research data for memristive devices
        if self.memristive_devices:
            self._log(f"Loading research data for {len(self.memristive_devices)} memristive device(s)...")
        self._load_research_data()
        
        filter_msg = f" (filtered by: {self.code_name_filter})" if self.code_name_filter else ""
        self._log(f"✓ Loaded {count} device(s) ({len(self.memristive_devices)} memristive){filter_msg}")
        return count
    
    def _load_research_data(self) -> None:
        """Load research-level analysis data for memristive devices."""
        if not os.path.exists(self.research_dir):
            return
        
        for device_info in self.memristive_devices:
            device_id = device_info['device_id']
            device_research_dir = os.path.join(self.research_dir, device_id)
            
            if os.path.exists(device_research_dir):
                research_files = []
                for file in os.listdir(device_research_dir):
                    if file.endswith('_research.json'):
                        try:
                            with open(os.path.join(device_research_dir, file), 'r') as f:
                                research_files.append(json.load(f))
                        except Exception as e:
                            print(f"[SAMPLE] Error loading research file {file}: {e}")
                
                if research_files:
                    # Use latest research file
                    self.research_data[device_id] = research_files[-1]
    
    def generate_all_plots(self) -> None:
        """Generate all plot types (13 main plots + 3 specialized size comparison plots)."""
        self._log(f"Generating plots for {self.sample_name}...")
        
        plot_names = [
            "Memristivity Score Heatmap",
            "Conduction Mechanism Distribution",
            "Memory Window Quality Distribution",
            "Hysteresis Shape Radar",
            "Enhanced Classification Scatter",
            "Forming Progress Tracking",
            "Warning Flag Summary",
            "Research Diagnostics Scatter Matrix",
            "Power & Energy Efficiency",
            "Device Leaderboard",
            "Spatial Distribution Maps",
            "Forming Status Distribution",
            "Device Size Comparison"
        ]
        
        plot_num = 0
        plotter = SamplePlots(
            devices_data=self.devices_data,
            plots_dir=self.plots_dir,
            sample_name=self.sample_name,
            research_data=self.research_data,
            memristive_devices=self.memristive_devices,
            data_origin_formatted_dir=self.data_origin_formatted_dir,
            size_comparison_dir=self.size_comparison_dir,
            load_iv_callback=self._load_iv_data_for_device,
            tracking_dir=self.tracking_dir,
            code_name_filter=self.code_name_filter,
        )
        
        # Plot 1: Memristivity Score Heatmap (plotting.sample_plots)
        plot_num += 1
        self._log(f"Plot {plot_num}/13: {plot_names[0]}")
        plotter.plot_memristivity_heatmap()
        self._export_memristivity_heatmap_data()
        
        # Plot 2: Conduction Mechanism Distribution (plotting.sample_plots)
        plot_num += 1
        self._log(f"Plot {plot_num}/13: {plot_names[1]}")
        plotter.plot_conduction_mechanisms()
        self._export_conduction_mechanism_data()
        
        # Plot 3: Memory Window Quality Distribution (plotting.sample_plots)
        plot_num += 1
        self._log(f"Plot {plot_num}/13: {plot_names[2]}")
        plotter.plot_memory_window_quality()
        self._export_memory_window_data()
        
        # Plot 4: Hysteresis Shape Radar (memristive only, plotting.sample_plots)
        if self.memristive_devices:
            plot_num += 1
            self._log(f"Plot {plot_num}/13: {plot_names[3]}")
            plotter.plot_hysteresis_radar()
        
        # Plot 5: Enhanced Classification Scatter (plotting.sample_plots)
        plot_num += 1
        self._log(f"Plot {plot_num}/13: {plot_names[4]}")
        plotter.plot_classification_scatter()
        self._export_classification_scatter_data()
        
        # Plot 6: Forming Progress Tracking (plotting.sample_plots)
        plot_num += 1
        self._log(f"Plot {plot_num}/13: {plot_names[5]}")
        plotter.plot_forming_progress()
        
        # Plot 7: Warning Flag Summary (plotting.sample_plots)
        plot_num += 1
        self._log(f"Plot {plot_num}/13: {plot_names[6]}")
        plotter.plot_warning_summary()
        
        # Plot 8: Research Diagnostics Scatter Matrix (plotting.sample_plots)
        if self.memristive_devices and len(self.research_data) > 0:
            plot_num += 1
            self._log(f"Plot {plot_num}/13: {plot_names[7]}")
            plotter.plot_research_diagnostics()
        
        # Plot 9: Power & Energy Efficiency (plotting.sample_plots)
        if len(self.research_data) > 0:
            plot_num += 1
            self._log(f"Plot {plot_num}/13: {plot_names[8]}")
            plotter.plot_power_efficiency()
            self._export_power_efficiency_data()
        
        # Plot 10: Device Leaderboard
        plot_num += 1
        self._log(f"Plot {plot_num}/13: {plot_names[9]}")
        plotter.plot_device_leaderboard()
        self._export_leaderboard_data()
        
        # Plot 11: Spatial Distribution Maps
        plot_num += 1
        self._log(f"Plot {plot_num}/13: {plot_names[10]}")
        plotter.plot_spatial_distributions()
        self._export_spatial_data()
        
        # Plot 12: Forming Status Distribution
        plot_num += 1
        self._log(f"Plot {plot_num}/13: {plot_names[11]}")
        plotter.plot_forming_status()
        self._export_forming_status_data()
        
        # Plot 13: Device Size Comparison
        plot_num += 1
        self._log(f"Plot {plot_num}/20: {plot_names[12]}")
        plotter.plot_device_size_comparison()
        
        # Plot 14: Metric Correlation Heatmap
        plot_num += 1
        self._log(f"Plot {plot_num}/20: Metric Correlation Heatmap")
        plotter.plot_metric_correlation_heatmap()
        self._export_metric_correlation_data()
        
        # Plot 15: Section Performance Comparison
        plot_num += 1
        self._log(f"Plot {plot_num}/20: Section Performance Comparison")
        plotter.plot_section_performance_comparison()
        self._export_section_comparison_data()
        
        # Plot 16: Resistance Distribution Comparison
        plot_num += 1
        self._log(f"Plot {plot_num}/20: Resistance Distribution Comparison")
        plotter.plot_resistance_distribution_comparison()
        self._export_resistance_distribution_data()
        
        # Plot 17: Yield and Performance Dashboard
        plot_num += 1
        self._log(f"Plot {plot_num}/20: Yield and Performance Dashboard")
        plotter.plot_yield_dashboard()
        
        # Plot 18: Device Type vs Size Matrix
        plot_num += 1
        self._log(f"Plot {plot_num}/20: Device Type vs Size Matrix")
        plotter.plot_device_type_size_matrix()
        self._export_type_size_matrix_data()
        
        # Plot 19: Quality Score Breakdown
        plot_num += 1
        self._log(f"Plot {plot_num}/20: Quality Score Breakdown")
        plotter.plot_quality_score_breakdown()
        self._export_quality_breakdown_data()
        
        # Plot 20: Confidence vs Performance Scatter
        plot_num += 1
        self._log(f"Plot {plot_num}/25: Confidence vs Performance Scatter")
        plotter.plot_confidence_performance_scatter()
        self._export_confidence_performance_data()
        
        # Plot 21: Voltage Range Analysis
        plot_num += 1
        self._log(f"Plot {plot_num}/25: Voltage Range Analysis")
        plotter.plot_voltage_range_analysis()
        self._export_voltage_range_data()
        
        # Plot 22: Performance Stability Analysis
        plot_num += 1
        self._log(f"Plot {plot_num}/25: Performance Stability Analysis")
        plotter.plot_performance_stability_analysis()
        self._export_stability_analysis_data()
        
        # Plot 23: Warning Analysis Dashboard
        plot_num += 1
        self._log(f"Plot {plot_num}/25: Warning Analysis Dashboard")
        plotter.plot_warning_analysis_dashboard()
        self._export_warning_analysis_data()
        
        # Plot 24: On/Off Ratio vs Switching Ratio
        plot_num += 1
        self._log(f"Plot {plot_num}/25: On/Off Ratio vs Switching Ratio")
        plotter.plot_ratio_comparison()
        self._export_ratio_comparison_data()
        
        # Plot 25: Section Spatial Gradient
        plot_num += 1
        self._log(f"Plot {plot_num}/25: Section Spatial Gradient")
        plotter.plot_section_spatial_gradient()
        self._export_spatial_gradient_data()
        
        # Plot 26: On/Off Ratio Evolution
        plot_num += 1
        self._log(f"Plot {plot_num}/26: On/Off Ratio Evolution")
        plotter.plot_onoff_ratio_evolution()
        
        self._log(f"✓ All {plot_num} main plots saved to: {self.plots_dir}")
        
        # Generate specialized size comparison plots (I-V overlays)
        if self.devices_data:
            self._generate_size_comparison_plots(plotter)
    
    def export_origin_data(self) -> None:
        """Export all data in Origin-ready format (CSV/TXT)."""
        print(f"[SAMPLE] Exporting Origin data...")
        
        # Export main device summary
        self._export_device_summary_csv()
        
        # Export for each plot type
        self._export_memristivity_heatmap_data()
        self._export_conduction_mechanism_data()
        self._export_memory_window_data()
        self._export_classification_scatter_data()
        if len(self.research_data) > 0:
            self._export_power_efficiency_data()
        self._export_leaderboard_data()
        self._export_spatial_data()
        self._export_forming_status_data()
        self._export_metric_correlation_data()
        self._export_section_comparison_data()
        self._export_resistance_distribution_data()
        self._export_type_size_matrix_data()
        self._export_quality_breakdown_data()
        self._export_confidence_performance_data()
        self._export_voltage_range_data()
        self._export_stability_analysis_data()
        self._export_warning_analysis_data()
        self._export_ratio_comparison_data()
        self._export_spatial_gradient_data()
        
        # Create README for Origin import
        self._create_origin_readme()
        
        print(f"[SAMPLE] Origin data exported to: {self.data_origin_formatted_dir}")
    
    def generate_size_comparison_plots(self) -> None:
        """Generate all 3 specialized I-V overlay plots grouped by device size."""
        plotter = SamplePlots(
            devices_data=self.devices_data,
            plots_dir=self.plots_dir,
            sample_name=self.sample_name,
            research_data=self.research_data,
            memristive_devices=self.memristive_devices,
            data_origin_formatted_dir=self.data_origin_formatted_dir,
            size_comparison_dir=self.size_comparison_dir,
            load_iv_callback=self._load_iv_data_for_device,
            tracking_dir=self.tracking_dir,
            code_name_filter=self.code_name_filter,
        )
        self._generate_size_comparison_plots(plotter)
    
    def _generate_size_comparison_plots(self, plotter: SamplePlots) -> None:
        """Generate the 3 size-comparison I-V overlay plots using the given plotter."""
        try:
            self._log("Generating size comparison I-V overlay plots...")
            plotter.plot_size_memristive_overlays()
            plotter.plot_size_top_per_section()
            plotter.plot_size_top_across_sample()
            self._log(f"✓ Size comparison plots saved to: {self.size_comparison_dir}")
        except Exception as e:
            self._log(f"Error generating size comparison plots: {e}")
            import traceback
            traceback.print_exc()
    
    def _find_min_sweep_for_code_name(self, device_dir: str, code_name: str) -> Optional[int]:
        """Find the minimum sweep number for a given code_name in a device folder."""
        if not os.path.exists(device_dir):
            return None
        import glob
        files = glob.glob(os.path.join(device_dir, '*.txt'))
        min_sweep = None
        for f in files:
            filename = os.path.basename(f)
            if filename == 'log.txt':
                continue
            try:
                parts = filename.replace('.txt', '').split('-')
                if len(parts) > 6:
                    file_code_name = parts[6]
                    if file_code_name == code_name:
                        sweep_num = int(parts[0])
                        if min_sweep is None or sweep_num < min_sweep:
                            min_sweep = sweep_num
            except (ValueError, IndexError):
                continue
        return min_sweep
    
    def _load_iv_data_for_device(self, device_id: str, sweep_num: Optional[int] = None, code_name: Optional[str] = None) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Load voltage and current data for a device by reading sweep file."""
        try:
            parts = device_id.split('_')
            if len(parts) < 3:
                return None, None
            section = parts[-2]
            device_num = parts[-1]
            device_dir = os.path.join(self.sample_dir, section, device_num)
            if not os.path.exists(device_dir):
                return None, None
            if code_name and sweep_num is None:
                sweep_num = self._find_min_sweep_for_code_name(device_dir, code_name)
                if sweep_num is None:
                    return None, None
            elif sweep_num is None:
                sweep_num = 1
            import glob
            sweep_pattern = os.path.join(device_dir, f'{sweep_num}-*.txt')
            sweep_files = glob.glob(sweep_pattern)
            sweep_files = [f for f in sweep_files if os.path.basename(f) != 'log.txt']
            if code_name:
                matching_files = []
                for f in sweep_files:
                    try:
                        filename = os.path.basename(f)
                        parts_f = filename.replace('.txt', '').split('-')
                        if len(parts_f) > 6 and parts_f[6] == code_name:
                            matching_files.append(f)
                    except (ValueError, IndexError):
                        continue
                sweep_files = matching_files
            if not sweep_files:
                return None, None
            try:
                data = np.loadtxt(sweep_files[0], skiprows=1)
                if data.ndim == 1:
                    data = data.reshape(1, -1)
                if data.shape[1] >= 2:
                    return data[:, 0], data[:, 1]
            except Exception:
                try:
                    data = np.loadtxt(sweep_files[0], skiprows=0)
                    if data.ndim == 1:
                        data = data.reshape(1, -1)
                    if data.shape[1] >= 2:
                        return data[:, 0], data[:, 1]
                except Exception:
                    pass
            return None, None
        except Exception:
            return None, None
    
    def _safe_get_quality_score(self, dev: Dict) -> float:
        """Safely extract memory window quality score from device data."""
        try:
            quality = dev.get('quality', {})
            if not isinstance(quality, dict):
                return np.nan
            mw_quality = quality.get('memory_window_quality', {})
            if not isinstance(mw_quality, dict):
                return np.nan
            return float(mw_quality.get('overall_quality_score', np.nan))
        except Exception:
            return np.nan
    
    def _export_device_summary_csv(self) -> None:
        """Export comprehensive device summary as CSV."""
        rows = []
        for dev in self.devices_data:
            rows.append({
                'Device_ID': dev['device_id'],
                'Device_Type': dev['classification'].get('device_type', 'unknown'),
                'Memristivity_Score': dev['classification'].get('memristivity_score', 0),
                'Confidence': dev['classification'].get('confidence', 0),
                'Conduction_Mechanism': dev['classification'].get('conduction_mechanism', 'unknown'),
                'Ron_Mean': dev['resistance'].get('ron_mean', np.nan),
                'Roff_Mean': dev['resistance'].get('roff_mean', np.nan),
                'Switching_Ratio': dev['resistance'].get('switching_ratio', np.nan),
                'Memory_Window_Quality': self._safe_get_quality_score(dev),
                'Has_Hysteresis': dev['hysteresis'].get('has_hysteresis', False),
                'Pinched': dev['hysteresis'].get('pinched', False),
                'Warning_Count': len(dev.get('warnings', [])),
                'Total_Measurements': dev.get('total_measurements', 0)
            })
        df = pd.DataFrame(rows)
        output_file = os.path.join(self.data_origin_formatted_dir, 'device_summary.csv')
        df.to_csv(output_file, index=False)
        print(f"[ORIGIN] Exported: device_summary.csv")
    
    def _create_origin_readme(self) -> None:
        """Create README with import instructions for Origin."""
        readme = f"""
# Origin Data Import Guide

## Files Overview
All data files are in CSV format with headers. Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Sample: {self.sample_name}

### Origin Import Steps:
1. Open Origin → File → Import → Single ASCII
2. Select CSV file; use first row as column headers, Delimiter: Comma
"""
        readme_file = os.path.join(self.data_origin_formatted_dir, 'README_ORIGIN_IMPORT.txt')
        with open(readme_file, 'w', encoding='utf-8') as f:
            f.write(readme.strip())
        print(f"[ORIGIN] Created: README_ORIGIN_IMPORT.txt")
    
    def _export_memristivity_heatmap_data(self) -> None:
        rows = []
        for dev in self.devices_data:
            parts = dev['device_id'].split('_')
            if len(parts) >= 3:
                try:
                    row, col = parts[-2], int(parts[-1])
                    rows.append({'Section': row, 'Device_Number': col, 'Memristivity_Score': dev['classification'].get('memristivity_score', 0)})
                except (ValueError, IndexError):
                    pass
        if rows:
            pd.DataFrame(rows).to_csv(os.path.join(self.data_origin_formatted_dir, 'memristivity_heatmap.csv'), index=False)
            print(f"[ORIGIN] Exported: memristivity_heatmap.csv")
    
    def _export_conduction_mechanism_data(self) -> None:
        from collections import Counter
        counts = Counter(dev['classification'].get('conduction_mechanism', 'unknown') for dev in self.devices_data)
        if counts:
            df = pd.DataFrame([{'Mechanism': k, 'Count': v} for k, v in counts.items()])
            df.to_csv(os.path.join(self.data_origin_formatted_dir, 'conduction_mechanisms.csv'), index=False)
            print(f"[ORIGIN] Exported: conduction_mechanisms.csv")
    
    def _export_memory_window_data(self) -> None:
        rows = [{'Device_ID': d['device_id'], 'Ron_Stability': d.get('quality', {}).get('memory_window_quality', {}).get('ron_stability', np.nan), 'Roff_Stability': d.get('quality', {}).get('memory_window_quality', {}).get('roff_stability', np.nan), 'Overall_Quality_Score': self._safe_get_quality_score(d)} for d in self.devices_data]
        if rows:
            pd.DataFrame(rows).to_csv(os.path.join(self.data_origin_formatted_dir, 'memory_window_quality.csv'), index=False)
            print(f"[ORIGIN] Exported: memory_window_quality.csv")
    
    def _export_classification_scatter_data(self) -> None:
        rows = [{'Device_ID': d['device_id'], 'Ron_Mean': d['resistance'].get('ron_mean'), 'Roff_Mean': d['resistance'].get('roff_mean'), 'Memristivity_Score': d['classification'].get('memristivity_score'), 'Switching_Ratio': d['resistance'].get('switching_ratio')} for d in self.devices_data]
        if rows:
            pd.DataFrame(rows).to_csv(os.path.join(self.data_origin_formatted_dir, 'classification_scatter.csv'), index=False)
            print(f"[ORIGIN] Exported: classification_scatter.csv")
    
    def _export_power_efficiency_data(self) -> None:
        rows = []
        for device_id, research in self.research_data.items():
            perf = research.get('performance_metrics', {})
            classification = research.get('classification', {})
            if perf.get('power_consumption_mean') is not None or perf.get('energy_per_switch_mean') is not None:
                rows.append({'Device_ID': device_id, 'Power_Consumption_Mean': perf.get('power_consumption_mean'), 'Energy_Per_Switch_Mean': perf.get('energy_per_switch_mean'), 'Memristivity_Score': classification.get('memristivity_score')})
        if rows:
            pd.DataFrame(rows).to_csv(os.path.join(self.data_origin_formatted_dir, 'power_efficiency.csv'), index=False)
            print(f"[ORIGIN] Exported: power_efficiency.csv")
    
    def _export_leaderboard_data(self) -> None:
        device_scores = []
        for dev in self.devices_data:
            memristivity = dev.get('classification', {}).get('memristivity_score', 0) or 0
            quality = self._safe_get_quality_score(dev)
            quality = 0 if np.isnan(quality) else quality
            sr = dev['resistance'].get('switching_ratio', 1) or 1
            ratio_score = min(100, np.log10(float(sr)) * 10) if float(sr) > 1 else 0
            composite = memristivity * 0.4 + quality * 0.3 + ratio_score * 0.2
            device_scores.append({'device_id': dev['device_id'], 'composite_score': composite})
        device_scores.sort(key=lambda x: x['composite_score'], reverse=True)
        if device_scores:
            pd.DataFrame(device_scores).to_csv(os.path.join(self.data_origin_formatted_dir, 'device_leaderboard.csv'), index=False)
            print(f"[ORIGIN] Exported: device_leaderboard.csv")
    
    def _export_spatial_data(self) -> None:
        rows = []
        for dev in self.devices_data:
            parts = dev['device_id'].split('_')
            if len(parts) >= 3:
                try:
                    row, col = parts[-2], int(parts[-1])
                    rows.append({'Section': row, 'Device_Number': col, 'Memristivity_Score': dev['classification'].get('memristivity_score', 0), 'Quality': self._safe_get_quality_score(dev), 'Switching_Ratio': dev['resistance'].get('switching_ratio', 1)})
                except (ValueError, IndexError):
                    pass
        if rows:
            pd.DataFrame(rows).to_csv(os.path.join(self.data_origin_formatted_dir, 'spatial_data.csv'), index=False)
            print(f"[ORIGIN] Exported: spatial_data.csv")
    
    def _export_forming_status_data(self) -> None:
        forming = formed = degrading = unstable = 0
        for dev in self.devices_data:
            measurements = dev.get('all_measurements', [])
            if len(measurements) >= 2:
                scores = [m.get('classification', {}).get('memristivity_score', 0) for m in measurements]
                scores = [s for s in scores if s is not None]
                if len(scores) > 1:
                    improvement = scores[-1] - scores[0]
                    variation = np.std(scores)
                    if improvement > 15: forming += 1
                    elif improvement < -10: degrading += 1
                    elif variation > 20: unstable += 1
                    else: formed += 1
        if forming + formed + degrading + unstable > 0:
            df = pd.DataFrame([{'Status': 'Forming', 'Count': forming}, {'Status': 'Formed', 'Count': formed}, {'Status': 'Degrading', 'Count': degrading}, {'Status': 'Unstable', 'Count': unstable}])
            df.to_csv(os.path.join(self.data_origin_formatted_dir, 'forming_status.csv'), index=False)
            print(f"[ORIGIN] Exported: forming_status.csv")
    
    def _export_metric_correlation_data(self, corr_matrix: Optional[pd.DataFrame] = None) -> None:
        if corr_matrix is None:
            metrics_data = [{'Memristivity_Score': d['classification'].get('memristivity_score', np.nan), 'Confidence': d['classification'].get('confidence', np.nan), 'Ron_Mean': d['resistance'].get('ron_mean', np.nan), 'Roff_Mean': d['resistance'].get('roff_mean', np.nan), 'Switching_Ratio': d['resistance'].get('switching_ratio', np.nan), 'Memory_Window_Quality': self._safe_get_quality_score(d)} for d in self.devices_data]
            df = pd.DataFrame(metrics_data).dropna(how='all')
            if len(df) >= 3:
                corr_matrix = df.corr()
            else:
                return
        if corr_matrix is not None:
            corr_matrix.to_csv(os.path.join(self.data_origin_formatted_dir, 'metric_correlation.csv'))
            print(f"[ORIGIN] Exported: metric_correlation.csv")
    
    def _export_section_comparison_data(self) -> None:
        sections_data = {}
        for dev in self.devices_data:
            section = dev.get('section')
            if section:
                if section not in sections_data:
                    sections_data[section] = []
                sections_data[section].append(dev)
        if sections_data:
            rows = []
            for section in sorted(sections_data.keys()):
                devices = sections_data[section]
                scores = [d['classification'].get('memristivity_score', 0) or 0 for d in devices]
                qualities = [self._safe_get_quality_score(d) for d in devices]
                qualities = [q for q in qualities if not np.isnan(q)]
                rows.append({'Section': section, 'Mean_Memristivity': np.mean(scores) if scores else 0, 'Mean_Quality': np.mean(qualities) if qualities else 0, 'Count': len(devices)})
            pd.DataFrame(rows).to_csv(os.path.join(self.data_origin_formatted_dir, 'section_comparison.csv'), index=False)
            print(f"[ORIGIN] Exported: section_comparison.csv")
    
    def _export_resistance_distribution_data(self) -> None:
        rows = [{'Device_ID': d['device_id'], 'Ron_Mean': d['resistance'].get('ron_mean'), 'Roff_Mean': d['resistance'].get('roff_mean'), 'Device_Type': d['classification'].get('device_type')} for d in self.devices_data]
        if rows:
            pd.DataFrame(rows).to_csv(os.path.join(self.data_origin_formatted_dir, 'resistance_distribution.csv'), index=False)
            print(f"[ORIGIN] Exported: resistance_distribution.csv")
    
    def _export_type_size_matrix_data(self, size_type_data=None, sizes=None, all_types=None) -> None:
        if size_type_data is None:
            size_type_data = {}
            for dev in self.devices_data:
                size = dev.get('device_size')
                dtype = dev['classification'].get('device_type', 'unknown')
                if size:
                    if size not in size_type_data:
                        size_type_data[size] = {}
                    size_type_data[size][dtype] = size_type_data[size].get(dtype, 0) + 1
            sizes = sorted(size_type_data.keys())
            all_types = sorted(set(t for sd in size_type_data.values() for t in sd.keys() if t))
        rows = []
        for size in sizes:
            total = sum(size_type_data[size].values())
            row = {'Device_Size': size, 'Total_Devices': total}
            for dtype in all_types:
                count = size_type_data[size].get(dtype, 0)
                row[f'{dtype}_Count'] = count
                row[f'{dtype}_Percentage'] = 100 * count / total if total > 0 else 0
            rows.append(row)
        if rows:
            pd.DataFrame(rows).to_csv(os.path.join(self.data_origin_formatted_dir, 'device_type_size_matrix.csv'), index=False)
            print(f"[ORIGIN] Exported: device_type_size_matrix.csv")
    
    def _export_quality_breakdown_data(self, ron_stab=None, roff_stab=None, sep_ratio=None, overall=None, sections=None) -> None:
        if overall is None:
            ron_stab, roff_stab, sep_ratio, overall, sections = [], [], [], [], []
            for dev in self.devices_data:
                quality = dev.get('quality', {})
                if isinstance(quality, dict):
                    mw = quality.get('memory_window_quality', {})
                    if isinstance(mw, dict) and not np.isnan(mw.get('overall_quality_score', np.nan)):
                        ron_stab.append(mw.get('ron_stability', 0))
                        roff_stab.append(mw.get('roff_stability', 0))
                        sep_ratio.append(mw.get('separation_ratio', 1))
                        overall.append(mw.get('overall_quality_score'))
                        sections.append(dev.get('section', 'Unknown'))
        if overall:
            pd.DataFrame({'Ron_Stability': ron_stab, 'Roff_Stability': roff_stab, 'Separation_Ratio': sep_ratio, 'Overall_Quality_Score': overall, 'Section': sections}).to_csv(os.path.join(self.data_origin_formatted_dir, 'quality_breakdown.csv'), index=False)
            print(f"[ORIGIN] Exported: quality_breakdown.csv")
    
    def _export_confidence_performance_data(self, confidences=None, scores=None, types=None, ratios=None) -> None:
        if confidences is None:
            confidences = []; scores = []; types = []; ratios = []
            for dev in self.devices_data:
                c = dev['classification'].get('confidence', np.nan)
                if not np.isnan(c):
                    confidences.append(c * 100)
                    scores.append(dev['classification'].get('memristivity_score', 0) or 0)
                    types.append(dev['classification'].get('device_type', 'unknown'))
                    ratios.append(dev['resistance'].get('switching_ratio', 1) or 1)
        if confidences:
            pd.DataFrame({'Confidence_Percentage': confidences, 'Memristivity_Score': scores, 'Device_Type': types, 'Switching_Ratio': ratios}).to_csv(os.path.join(self.data_origin_formatted_dir, 'confidence_performance.csv'), index=False)
            print(f"[ORIGIN] Exported: confidence_performance.csv")
    
    def _export_voltage_range_data(self, max_voltages=None, scores=None, types=None, sections=None) -> None:
        if max_voltages is None:
            max_voltages, scores, types, sections = [], [], [], []
            for dev in self.devices_data:
                max_v = dev.get('voltage', {}).get('max_voltage', np.nan)
                if not np.isnan(max_v) and max_v > 0:
                    max_voltages.append(abs(max_v))
                    scores.append(dev['classification'].get('memristivity_score', 0) or 0)
                    types.append(dev['classification'].get('device_type', 'unknown'))
                    sections.append(dev.get('section', 'Unknown'))
        if max_voltages:
            pd.DataFrame({'Max_Voltage_V': max_voltages, 'Memristivity_Score': scores, 'Device_Type': types, 'Section': sections}).to_csv(os.path.join(self.data_origin_formatted_dir, 'voltage_range_analysis.csv'), index=False)
            print(f"[ORIGIN] Exported: voltage_range_analysis.csv")
    
    def _export_stability_analysis_data(self, devices_data=None) -> None:
        if devices_data is None:
            devices_data = []
            for dev in self.devices_data:
                measurements = dev.get('all_measurements', [])
                if len(measurements) >= 3:
                    scores = [m.get('classification', {}).get('memristivity_score', 0) or 0 for m in measurements]
                    if len(scores) >= 3 and np.mean(scores) > 0:
                        devices_data.append({'device_id': dev['device_id'], 'avg_score': np.mean(scores), 'score_cv': np.std(scores) / np.mean(scores), 'num_measurements': len(measurements)})
        if devices_data:
            pd.DataFrame(devices_data).to_csv(os.path.join(self.data_origin_formatted_dir, 'performance_stability.csv'), index=False)
            print(f"[ORIGIN] Exported: performance_stability.csv")
    
    def _export_warning_analysis_data(self, warning_types=None, warning_devices=None, devices_with=None, devices_without=None) -> None:
        if warning_types is None:
            warning_types = {}
            for dev in self.devices_data:
                for warning in dev.get('warnings', []):
                    wt = warning.split(':')[0].split('.')[0].strip()[:50]
                    if wt:
                        warning_types[wt] = warning_types.get(wt, 0) + 1
        if warning_types:
            rows = [{'Warning_Type': wt, 'Count': c} for wt, c in sorted(warning_types.items(), key=lambda x: x[1], reverse=True)]
            pd.DataFrame(rows).to_csv(os.path.join(self.data_origin_formatted_dir, 'warning_analysis.csv'), index=False)
            print(f"[ORIGIN] Exported: warning_analysis.csv")
    
    def _export_ratio_comparison_data(self, switching=None, onoff=None, scores=None, types=None) -> None:
        if switching is None:
            switching, onoff, scores, types = [], [], [], []
            for dev in self.devices_data:
                sw = dev['resistance'].get('switching_ratio', np.nan)
                oo = dev['resistance'].get('on_off_ratio', np.nan)
                if not np.isnan(sw) and not np.isnan(oo) and sw > 0 and oo > 0:
                    switching.append(sw); onoff.append(oo)
                    scores.append(dev['classification'].get('memristivity_score', 0) or 0)
                    types.append(dev['classification'].get('device_type', 'unknown'))
        if switching:
            pd.DataFrame({'Switching_Ratio': switching, 'On_Off_Ratio': onoff, 'Memristivity_Score': scores, 'Device_Type': types}).to_csv(os.path.join(self.data_origin_formatted_dir, 'ratio_comparison.csv'), index=False)
            print(f"[ORIGIN] Exported: ratio_comparison.csv")
    
    def _export_spatial_gradient_data(self, sections=None, metrics=None) -> None:
        if sections is None:
            section_positions = {}
            for dev in self.devices_data:
                section = dev.get('section')
                if section:
                    if section not in section_positions:
                        section_positions[section] = {'scores': [], 'qualities': [], 'yield': 0, 'total': 0}
                    section_positions[section]['scores'].append(dev['classification'].get('memristivity_score', 0) or 0)
                    q = self._safe_get_quality_score(dev)
                    if not np.isnan(q):
                        section_positions[section]['qualities'].append(q)
                    section_positions[section]['total'] += 1
                    if dev['classification'].get('device_type') == 'memristive':
                        section_positions[section]['yield'] += 1
            sections = sorted(section_positions.keys())
            metrics = {'avg_score': [np.mean(section_positions[s]['scores']) if section_positions[s]['scores'] else 0 for s in sections], 'avg_quality': [np.mean(section_positions[s]['qualities']) if section_positions[s]['qualities'] else 0 for s in sections], 'yield_pct': [100 * section_positions[s]['yield'] / section_positions[s]['total'] if section_positions[s]['total'] > 0 else 0 for s in sections]}
        if sections and metrics:
            pd.DataFrame({'Section': sections, 'Average_Score': metrics['avg_score'], 'Average_Quality': metrics['avg_quality'], 'Yield_Percentage': metrics['yield_pct']}).to_csv(os.path.join(self.data_origin_formatted_dir, 'section_spatial_gradient.csv'), index=False)
            print(f"[ORIGIN] Exported: section_spatial_gradient.csv")
    
    