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
    from Helpers.Analysis import SampleAnalysisOrchestrator
    
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
        
        # Plot 1: Memristivity Score Heatmap
        plot_num += 1
        self._log(f"Plot {plot_num}/13: {plot_names[0]}")
        self.plot_memristivity_heatmap()
        
        # Plot 2: Conduction Mechanism Distribution
        plot_num += 1
        self._log(f"Plot {plot_num}/13: {plot_names[1]}")
        self.plot_conduction_mechanisms()
        
        # Plot 3: Memory Window Quality Distribution
        plot_num += 1
        self._log(f"Plot {plot_num}/13: {plot_names[2]}")
        self.plot_memory_window_quality()
        
        # Plot 4: Hysteresis Shape Radar (memristive only)
        if self.memristive_devices:
            plot_num += 1
            self._log(f"Plot {plot_num}/13: {plot_names[3]}")
            self.plot_hysteresis_radar()
        
        # Plot 5: Enhanced Classification Scatter
        plot_num += 1
        self._log(f"Plot {plot_num}/13: {plot_names[4]}")
        self.plot_classification_scatter()
        
        # Plot 6: Forming Progress Tracking
        plot_num += 1
        self._log(f"Plot {plot_num}/13: {plot_names[5]}")
        self.plot_forming_progress()
        
        # Plot 7: Warning Flag Summary
        plot_num += 1
        self._log(f"Plot {plot_num}/13: {plot_names[6]}")
        self.plot_warning_summary()
        
        # Plot 8: Research Diagnostics Scatter Matrix
        if self.memristive_devices and len(self.research_data) > 0:
            plot_num += 1
            self._log(f"Plot {plot_num}/13: {plot_names[7]}")
            self.plot_research_diagnostics()
        
        # Plot 9: Power & Energy Efficiency
        if len(self.research_data) > 0:
            plot_num += 1
            self._log(f"Plot {plot_num}/13: {plot_names[8]}")
            self.plot_power_efficiency()
        
        # Plot 10: Device Leaderboard
        plot_num += 1
        self._log(f"Plot {plot_num}/13: {plot_names[9]}")
        self.plot_device_leaderboard()
        
        # Plot 11: Spatial Distribution Maps
        plot_num += 1
        self._log(f"Plot {plot_num}/13: {plot_names[10]}")
        self.plot_spatial_distributions()
        
        # Plot 12: Forming Status Distribution
        plot_num += 1
        self._log(f"Plot {plot_num}/13: {plot_names[11]}")
        self.plot_forming_status()
        
        # Plot 13: Device Size Comparison
        plot_num += 1
        self._log(f"Plot {plot_num}/20: {plot_names[12]}")
        self.plot_device_size_comparison()
        
        # Plot 14: Metric Correlation Heatmap
        plot_num += 1
        self._log(f"Plot {plot_num}/20: Metric Correlation Heatmap")
        self.plot_metric_correlation_heatmap()
        
        # Plot 15: Section Performance Comparison
        plot_num += 1
        self._log(f"Plot {plot_num}/20: Section Performance Comparison")
        self.plot_section_performance_comparison()
        
        # Plot 16: Resistance Distribution Comparison
        plot_num += 1
        self._log(f"Plot {plot_num}/20: Resistance Distribution Comparison")
        self.plot_resistance_distribution_comparison()
        
        # Plot 17: Yield and Performance Dashboard
        plot_num += 1
        self._log(f"Plot {plot_num}/20: Yield and Performance Dashboard")
        self.plot_yield_dashboard()
        
        # Plot 18: Device Type vs Size Matrix
        plot_num += 1
        self._log(f"Plot {plot_num}/20: Device Type vs Size Matrix")
        self.plot_device_type_size_matrix()
        
        # Plot 19: Quality Score Breakdown
        plot_num += 1
        self._log(f"Plot {plot_num}/20: Quality Score Breakdown")
        self.plot_quality_score_breakdown()
        
        # Plot 20: Confidence vs Performance Scatter
        plot_num += 1
        self._log(f"Plot {plot_num}/25: Confidence vs Performance Scatter")
        self.plot_confidence_performance_scatter()
        
        # Plot 21: Voltage Range Analysis
        plot_num += 1
        self._log(f"Plot {plot_num}/25: Voltage Range Analysis")
        self.plot_voltage_range_analysis()
        
        # Plot 22: Performance Stability Analysis
        plot_num += 1
        self._log(f"Plot {plot_num}/25: Performance Stability Analysis")
        self.plot_performance_stability_analysis()
        
        # Plot 23: Warning Analysis Dashboard
        plot_num += 1
        self._log(f"Plot {plot_num}/25: Warning Analysis Dashboard")
        self.plot_warning_analysis_dashboard()
        
        # Plot 24: On/Off Ratio vs Switching Ratio
        plot_num += 1
        self._log(f"Plot {plot_num}/25: On/Off Ratio vs Switching Ratio")
        self.plot_ratio_comparison()
        
        # Plot 25: Section Spatial Gradient
        plot_num += 1
        self._log(f"Plot {plot_num}/25: Section Spatial Gradient")
        self.plot_section_spatial_gradient()
        
        self._log(f"✓ All {plot_num} main plots saved to: {self.plots_dir}")
        
        # Generate specialized size comparison plots (I-V overlays)
        if self.devices_data:
            self.generate_size_comparison_plots()
    
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
    
    # === PLOT 1: Memristivity Score Heatmap ===
    def plot_memristivity_heatmap(self) -> None:
        """Color-coded heatmap of memristivity scores across sample."""
        try:
            # Parse device IDs to extract position (e.g., "sample_A_5" -> row=A, col=5)
            positions = {}  # {(row, col): score}
            
            for dev in self.devices_data:
                device_id = dev['device_id']
                # Parse device_id format: sample_letter_number
                parts = device_id.split('_')
                if len(parts) >= 3:
                    try:
                        row = parts[-2]  # Letter
                        col = int(parts[-1])  # Number
                        score = dev['classification'].get('memristivity_score', 0)
                        positions[(row, col)] = score
                    except (ValueError, IndexError):
                        continue
            
            if not positions:
                print("[PLOT] No position data for heatmap")
                return
            
            # Create grid
            rows = sorted(set(r for r, c in positions.keys()))
            cols = sorted(set(c for r, c in positions.keys()))
            
            grid = np.zeros((len(rows), len(cols)))
            for i, row in enumerate(rows):
                for j, col in enumerate(cols):
                    grid[i, j] = positions.get((row, col), 0)
            
            # Plot
            fig, ax = plt.subplots(figsize=(max(12, len(cols)*0.8), max(8, len(rows)*0.6)))
            
            # Custom colormap: Red → Orange → Yellow → Green
            colors = ['#d62728', '#ff7f0e', '#ffd700', '#2ca02c']
            n_bins = 100
            cmap = LinearSegmentedColormap.from_list('memristivity', colors, N=n_bins)
            
            im = ax.imshow(grid, cmap=cmap, vmin=0, vmax=100, aspect='auto')
            
            # Labels
            ax.set_xticks(range(len(cols)))
            ax.set_xticklabels(cols)
            ax.set_yticks(range(len(rows)))
            ax.set_yticklabels(rows)
            
            ax.set_xlabel('Device Number', fontsize=12, fontweight='bold')
            ax.set_ylabel('Section', fontsize=12, fontweight='bold')
            ax.set_title(f'Memristivity Score Heatmap - {self.sample_name}', 
                        fontsize=14, fontweight='bold')
            
            # Colorbar
            cbar = plt.colorbar(im, ax=ax)
            cbar.set_label('Memristivity Score (0-100)', fontsize=12)
            
            # Add score text in cells
            for i in range(len(rows)):
                for j in range(len(cols)):
                    score = grid[i, j]
                    if score > 0:
                        text_color = 'white' if score < 50 else 'black'
                        ax.text(j, i, f'{score:.0f}', ha='center', va='center', 
                               color=text_color, fontsize=8, fontweight='bold')
            
            plt.tight_layout()
            
            # Save
            output_file = os.path.join(self.plots_dir, '01_memristivity_heatmap.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"[PLOT] Saved: 01_memristivity_heatmap.png")
            
            # Export Origin data
            self._export_memristivity_heatmap_data(positions)
            
        except Exception as e:
            print(f"[PLOT ERROR] Heatmap failed: {e}")
            import traceback
            traceback.print_exc()
    
    def _export_memristivity_heatmap_data(self, positions: Optional[Dict] = None) -> None:
        """Export heatmap data for Origin."""
        # Recalculate positions if not provided
        if positions is None:
            positions = {}
            for dev in self.devices_data:
                device_id = dev['device_id']
                parts = device_id.split('_')
                if len(parts) >= 3:
                    try:
                        row = parts[-2]
                        col = int(parts[-1])
                        score = dev['classification'].get('memristivity_score', 0)
                        positions[(row, col)] = score
                    except (ValueError, IndexError):
                        continue
        
        rows = []
        for (row, col), score in positions.items():
            rows.append({
                'Device_ID': f"{self.sample_name}_{row}_{col}",
                'Section': row,
                'Device_Number': col,
                'Memristivity_Score': score
            })
        
        df = pd.DataFrame(rows)
        output_file = os.path.join(self.data_origin_formatted_dir, 'memristivity_heatmap.csv')
        df.to_csv(output_file, index=False)
        print(f"[ORIGIN] Exported: memristivity_heatmap.csv")
    
    # === PLOT 2: Conduction Mechanism Distribution ===
    def plot_conduction_mechanisms(self) -> None:
        """Pie + bar chart of conduction mechanism distribution."""
        try:
            mechanisms = {}
            for dev in self.devices_data:
                mechanism = dev['classification'].get('conduction_mechanism', 'unknown')
                if mechanism is None:
                    mechanism = 'unknown'
                mechanisms[mechanism] = mechanisms.get(mechanism, 0) + 1
            
            if not mechanisms:
                print("[PLOT] No conduction mechanism data")
                return
            
            # Sort by count
            sorted_mechs = sorted(mechanisms.items(), key=lambda x: x[1], reverse=True)
            labels = [str(m[0]).replace('_', ' ').title() for m, _ in sorted_mechs]
            counts = [c for _, c in sorted_mechs]
            
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
            
            # Pie chart
            colors = plt.cm.Set3(np.linspace(0, 1, len(labels)))
            ax1.pie(counts, labels=labels, autopct='%1.1f%%', startangle=90, colors=colors)
            ax1.set_title('Conduction Mechanism Distribution\n(Pie Chart)', fontsize=12, fontweight='bold')
            
            # Bar chart
            bars = ax2.barh(labels, counts, color=colors)
            ax2.set_xlabel('Device Count', fontsize=11, fontweight='bold')
            ax2.set_title('Conduction Mechanism Distribution\n(Bar Chart)', fontsize=12, fontweight='bold')
            ax2.grid(axis='x', alpha=0.3)
            
            # Add count labels on bars
            for i, (bar, count) in enumerate(zip(bars, counts)):
                ax2.text(count + 0.5, i, str(count), va='center', fontweight='bold')
            
            plt.tight_layout()
            output_file = os.path.join(self.plots_dir, '02_conduction_mechanisms.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"[PLOT] Saved: 02_conduction_mechanisms.png")
            self._export_conduction_mechanism_data(mechanisms)
            
        except Exception as e:
            print(f"[PLOT ERROR] Conduction mechanisms failed: {e}")
            import traceback
            traceback.print_exc()
    
    def _export_conduction_mechanism_data(self, mechanisms: Optional[Dict] = None) -> None:
        """Export conduction mechanism data."""
        if mechanisms is None:
            mechanisms = {}
            for dev in self.devices_data:
                mechanism = dev['classification'].get('conduction_mechanism', 'unknown')
                mechanisms[mechanism] = mechanisms.get(mechanism, 0) + 1
        
        rows = [{'Mechanism': str(k).replace('_', ' ').title(), 'Count': v} 
                for k, v in sorted(mechanisms.items(), key=lambda x: x[1], reverse=True)]
        df = pd.DataFrame(rows)
        output_file = os.path.join(self.data_origin_formatted_dir, 'conduction_mechanisms.csv')
        df.to_csv(output_file, index=False)
        print(f"[ORIGIN] Exported: conduction_mechanisms.csv")
    
    # === PLOT 3: Memory Window Quality Distribution ===
    def plot_memory_window_quality(self) -> None:
        """Box plots for memory window quality metrics."""
        try:
            # Extract quality metrics
            ron_stability = []
            roff_stability = []
            overall_quality = []
            separation_ratio = []
            
            for dev in self.devices_data:
                quality = dev.get('quality', {})
                # Handle case where quality might be a float or None
                if not isinstance(quality, dict):
                    continue
                mw_quality = quality.get('memory_window_quality', {})
                
                if mw_quality and isinstance(mw_quality, dict):
                    ron_stability.append(mw_quality.get('ron_stability', np.nan))
                    roff_stability.append(mw_quality.get('roff_stability', np.nan))
                    overall_quality.append(mw_quality.get('overall_quality_score', np.nan))
                    separation_ratio.append(mw_quality.get('separation_ratio', np.nan))
            
            if not overall_quality:
                print("[PLOT] No memory window quality data")
                return
            
            fig, axes = plt.subplots(2, 2, figsize=(14, 10))
            
            # Ron Stability
            axes[0, 0].boxplot([x for x in ron_stability if not np.isnan(x)], vert=True)
            axes[0, 0].set_ylabel('Ron Stability (0-100)', fontsize=11, fontweight='bold')
            axes[0, 0].set_title('Ron Stability Distribution', fontsize=12, fontweight='bold')
            axes[0, 0].grid(axis='y', alpha=0.3)
            
            # Roff Stability
            axes[0, 1].boxplot([x for x in roff_stability if not np.isnan(x)], vert=True)
            axes[0, 1].set_ylabel('Roff Stability (0-100)', fontsize=11, fontweight='bold')
            axes[0, 1].set_title('Roff Stability Distribution', fontsize=12, fontweight='bold')
            axes[0, 1].grid(axis='y', alpha=0.3)
            
            # Overall Quality
            axes[1, 0].boxplot([x for x in overall_quality if not np.isnan(x)], vert=True)
            axes[1, 0].set_ylabel('Overall Quality Score (0-100)', fontsize=11, fontweight='bold')
            axes[1, 0].set_title('Memory Window Quality Score', fontsize=12, fontweight='bold')
            axes[1, 0].grid(axis='y', alpha=0.3)
            
            # Separation Ratio (log scale)
            valid_ratios = [x for x in separation_ratio if not np.isnan(x) and x > 0]
            if valid_ratios:
                axes[1, 1].boxplot(valid_ratios, vert=True)
                axes[1, 1].set_yscale('log')
                axes[1, 1].set_ylabel('Separation Ratio (log scale)', fontsize=11, fontweight='bold')
                axes[1, 1].set_title('Separation Ratio Distribution', fontsize=12, fontweight='bold')
                axes[1, 1].grid(axis='y', alpha=0.3)
            
            plt.suptitle(f'Memory Window Quality Distribution - {self.sample_name}', 
                        fontsize=14, fontweight='bold', y=0.995)
            plt.tight_layout()
            
            output_file = os.path.join(self.plots_dir, '03_memory_window_quality.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"[PLOT] Saved: 03_memory_window_quality.png")
            self._export_memory_window_data(ron_stability, roff_stability, overall_quality, separation_ratio)
            
        except Exception as e:
            print(f"[PLOT ERROR] Memory window quality failed: {e}")
            import traceback
            traceback.print_exc()
    
    def _export_memory_window_data(self, ron_stab=None, roff_stab=None, overall=None, separation=None) -> None:
        """Export memory window quality data."""
        if ron_stab is None:
            ron_stab, roff_stab, overall, separation = [], [], [], []
            for dev in self.devices_data:
                quality = dev.get('quality', {})
                if isinstance(quality, dict):
                    mw_quality = quality.get('memory_window_quality', {})
                    if isinstance(mw_quality, dict):
                        ron_stab.append(mw_quality.get('ron_stability', np.nan))
                        roff_stab.append(mw_quality.get('roff_stability', np.nan))
                        overall.append(mw_quality.get('overall_quality_score', np.nan))
                        separation.append(mw_quality.get('separation_ratio', np.nan))
        
        max_len = max(len(ron_stab), len(roff_stab), len(overall), len(separation)) if ron_stab else 0
        if max_len == 0:
            print("[ORIGIN] No memory window quality data to export")
            return
        
        data = {
            'Ron_Stability': ron_stab + [np.nan] * (max_len - len(ron_stab)),
            'Roff_Stability': roff_stab + [np.nan] * (max_len - len(roff_stab)),
            'Overall_Quality_Score': overall + [np.nan] * (max_len - len(overall)),
            'Separation_Ratio': separation + [np.nan] * (max_len - len(separation))
        }
        df = pd.DataFrame(data)
        output_file = os.path.join(self.data_origin_formatted_dir, 'memory_window_quality.csv')
        df.to_csv(output_file, index=False)
        print(f"[ORIGIN] Exported: memory_window_quality.csv")
    
    # === PLOT 4: Hysteresis Shape Radar (Memristive Only) ===
    def plot_hysteresis_radar(self) -> None:
        """Radar chart showing hysteresis shape features."""
        try:
            if not self.research_data:
                print("[PLOT] No research data for radar chart")
                return
            
            # Extract features from research data
            features_list = []
            device_ids = []
            
            for device_id, research in self.research_data.items():
                hyst_shape = research.get('classification', {}).get('hysteresis_shape', {})
                if hyst_shape:
                    features_list.append({
                        'figure_eight_quality': hyst_shape.get('figure_eight_quality', 0),
                        'smoothness': min(100, np.log10(hyst_shape.get('smoothness_metric', 1)) * 10) if hyst_shape.get('smoothness_metric', 0) > 0 else 0,
                        'lobe_asymmetry': hyst_shape.get('lobe_asymmetry', 0) * 100,
                        'width_variation': (1 - hyst_shape.get('width_variation', 1)) * 100 if hyst_shape.get('width_variation', 1) > 0 else 0
                    })
                    device_ids.append(device_id)
            
            if not features_list:
                print("[PLOT] No hysteresis shape data")
                return
            
            # Calculate average
            avg_features = {
                'figure_eight_quality': np.mean([f['figure_eight_quality'] for f in features_list]),
                'smoothness': np.mean([f['smoothness'] for f in features_list]),
                'lobe_asymmetry': np.mean([f['lobe_asymmetry'] for f in features_list]),
                'width_variation': np.mean([f['width_variation'] for f in features_list])
            }
            
            # Radar chart
            categories = ['Figure-8\nQuality', 'Smoothness', 'Lobe\nAsymmetry', 'Width\nVariation']
            values = [avg_features['figure_eight_quality'], avg_features['smoothness'], 
                     avg_features['lobe_asymmetry'], avg_features['width_variation']]
            
            angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
            values += values[:1]  # Close the loop
            angles += angles[:1]
            
            fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(projection='polar'))
            ax.plot(angles, values, 'o-', linewidth=2, label='Average')
            ax.fill(angles, values, alpha=0.25)
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(categories)
            ax.set_ylim(0, 100)
            ax.set_title(f'Hysteresis Shape Quality (Average)\n{self.sample_name}', 
                        fontsize=12, fontweight='bold', pad=20)
            ax.grid(True)
            ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
            
            plt.tight_layout()
            output_file = os.path.join(self.plots_dir, '04_hysteresis_radar.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"[PLOT] Saved: 04_hysteresis_radar.png")
            
        except Exception as e:
            print(f"[PLOT ERROR] Hysteresis radar failed: {e}")
            import traceback
            traceback.print_exc()
    
    # === PLOT 5: Enhanced Classification Scatter ===
    def plot_classification_scatter(self) -> None:
        """Scatter plot: Ron vs Roff with multi-dimensional encoding."""
        try:
            ron_values = []
            roff_values = []
            scores = []
            device_types = []
            pinched = []
            switching_ratios = []
            
            for dev in self.devices_data:
                ron = dev['resistance'].get('ron_mean', np.nan)
                roff = dev['resistance'].get('roff_mean', np.nan)
                score = dev['classification'].get('memristivity_score', 0)
                dtype = dev['classification'].get('device_type', 'unknown')
                is_pinched = dev['hysteresis'].get('pinched', False)
                ratio = dev['resistance'].get('switching_ratio', np.nan)
                
                if not np.isnan(ron) and not np.isnan(roff) and ron > 0 and roff > 0:
                    ron_values.append(ron)
                    roff_values.append(roff)
                    scores.append(score)
                    device_types.append(dtype)
                    pinched.append(is_pinched)
                    
                    # Safe ratio handling
                    safe_ratio = 1
                    if ratio is not None and isinstance(ratio, (int, float)) and not np.isnan(ratio):
                        safe_ratio = ratio
                    switching_ratios.append(safe_ratio)
            
            if not ron_values:
                print("[PLOT] No resistance data for scatter")
                return
            
            fig, ax = plt.subplots(figsize=(12, 10))
            
            # Color by memristivity score, size by switching ratio, shape by device type
            type_shapes = {'memristive': 'o', 'ohmic': 's', 'capacitive': '^', 'unknown': 'x'}
            type_colors = {'memristive': 'green', 'ohmic': 'red', 'capacitive': 'blue', 'unknown': 'gray'}
            
            for dtype in set(device_types):
                mask = [dt == dtype for dt in device_types]
                ron_subset = [r for r, m in zip(ron_values, mask) if m]
                roff_subset = [r for r, m in zip(roff_values, mask) if m]
                score_subset = [s for s, m in zip(scores, mask) if m]
                ratio_subset = [r for r, m in zip(switching_ratios, mask) if m]
                pinched_subset = [p for p, m in zip(pinched, mask) if m]
                
                # Size based on switching ratio (normalized)
                sizes = [min(200, max(20, np.log10(r) * 20)) if r > 1 else 20 for r in ratio_subset]
                
                scatter = ax.scatter(ron_subset, roff_subset, c=score_subset, s=sizes,
                                   marker=type_shapes.get(dtype, 'o'), 
                                   cmap='RdYlGn', vmin=0, vmax=100,
                                   alpha=0.6, edgecolors='black', linewidths=0.5,
                                   label=dtype.title())
            
            ax.set_xscale('log')
            ax.set_yscale('log')
            ax.set_xlabel('Ron (Ω)', fontsize=12, fontweight='bold')
            ax.set_ylabel('Roff (Ω)', fontsize=12, fontweight='bold')
            ax.set_title(f'Enhanced Classification: Ron vs Roff\n{self.sample_name}', 
                        fontsize=14, fontweight='bold')
            ax.legend(title='Device Type', fontsize=10)
            ax.grid(True, alpha=0.3)
            
            # Colorbar
            cbar = plt.colorbar(ax.collections[0], ax=ax)
            cbar.set_label('Memristivity Score', fontsize=11)
            
            plt.tight_layout()
            output_file = os.path.join(self.plots_dir, '05_classification_scatter.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"[PLOT] Saved: 05_classification_scatter.png")
            self._export_classification_scatter_data(ron_values, roff_values, scores, device_types, pinched, switching_ratios)
            
        except Exception as e:
            print(f"[PLOT ERROR] Classification scatter failed: {e}")
            import traceback
            traceback.print_exc()
    
    def _export_classification_scatter_data(self, ron=None, roff=None, scores=None, types=None, pinched=None, ratios=None) -> None:
        """Export classification scatter data."""
        if ron is None:
            ron, roff, scores, types, pinched, ratios = [], [], [], [], [], []
            for dev in self.devices_data:
                ron.append(dev['resistance'].get('ron_mean', np.nan))
                roff.append(dev['resistance'].get('roff_mean', np.nan))
                scores.append(dev['classification'].get('memristivity_score', 0))
                types.append(dev['classification'].get('device_type', 'unknown'))
                pinched.append(dev['hysteresis'].get('pinched_hysteresis', False))
                ratios.append(dev['resistance'].get('switching_ratio', 1))
        
        df = pd.DataFrame({
            'Ron_Mean': ron,
            'Roff_Mean': roff,
            'Switching_Ratio': ratios,
            'Memristivity_Score': scores,
            'Device_Type': types,
            'Pinched': pinched
        })
        output_file = os.path.join(self.data_origin_formatted_dir, 'classification_scatter.csv')
        df.to_csv(output_file, index=False)
        print(f"[ORIGIN] Exported: classification_scatter.csv")
    
    # === PLOT 6: Forming Progress Tracking ===
    def plot_forming_progress(self) -> None:
        """Multi-line plot showing memristivity score vs measurement number."""
        try:
            fig, ax = plt.subplots(figsize=(14, 8))
            
            devices_plotted = 0
            for dev in self.devices_data:
                measurements = dev.get('all_measurements', [])
                if len(measurements) < 2:  # Need at least 2 measurements
                    continue
                
                scores = [m.get('classification', {}).get('memristivity_score', 0) 
                         for m in measurements]
                measurement_nums = list(range(1, len(scores) + 1))
                
                # Determine status
                if len(scores) > 1:
                    improvement = scores[-1] - scores[0]
                    if improvement > 15:
                        color = 'green'  # Forming
                        label_suffix = ' (Forming)'
                    elif improvement < -10:
                        color = 'red'  # Degrading
                        label_suffix = ' (Degrading)'
                    else:
                        color = 'blue'  # Stable
                        label_suffix = ' (Stable)'
                else:
                    color = 'gray'
                    label_suffix = ''
                
                ax.plot(measurement_nums, scores, 'o-', color=color, alpha=0.6, 
                       linewidth=1.5, markersize=4, label=f"{dev['device_id']}{label_suffix}")
                devices_plotted += 1
            
            if devices_plotted == 0:
                print("[PLOT] No multi-measurement data for forming progress")
                return
            
            ax.set_xlabel('Measurement Number', fontsize=12, fontweight='bold')
            ax.set_ylabel('Memristivity Score', fontsize=12, fontweight='bold')
            ax.set_title(f'Forming Progress Tracking - {self.sample_name}', 
                        fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3)
            ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8, ncol=2)
            
            plt.tight_layout()
            output_file = os.path.join(self.plots_dir, '06_forming_progress.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"[PLOT] Saved: 06_forming_progress.png")
            
        except Exception as e:
            print(f"[PLOT ERROR] Forming progress failed: {e}")
            import traceback
            traceback.print_exc()
    
    # === PLOT 7: Warning Flag Summary ===
    def plot_warning_summary(self) -> None:
        """Horizontal bar chart of warning types."""
        try:
            warning_counts = {}
            warning_devices = {}
            
            for dev in self.devices_data:
                warnings = dev.get('warnings', [])
                for warning in warnings:
                    # Extract warning type (first part before colon or first sentence)
                    warning_type = warning.split(':')[0].split('.')[0].strip()
                    if not warning_type:
                        warning_type = warning[:50]  # First 50 chars
                    
                    warning_counts[warning_type] = warning_counts.get(warning_type, 0) + 1
                    if warning_type not in warning_devices:
                        warning_devices[warning_type] = []
                    warning_devices[warning_type].append(dev['device_id'])
            
            if not warning_counts:
                print("[PLOT] No warnings to plot")
                return
            
            # Sort by count
            sorted_warnings = sorted(warning_counts.items(), key=lambda x: x[1], reverse=True)
            labels = [w[0] for w in sorted_warnings]
            counts = [w[1] for w in sorted_warnings]
            
            fig, ax = plt.subplots(figsize=(12, max(6, len(labels) * 0.4)))
            
            bars = ax.barh(labels, counts, color='#ff6b6b')
            ax.set_xlabel('Count', fontsize=12, fontweight='bold')
            ax.set_title(f'Warning Flag Summary - {self.sample_name}', 
                        fontsize=14, fontweight='bold')
            ax.grid(axis='x', alpha=0.3)
            
            # Add count labels
            for i, (bar, count) in enumerate(zip(bars, counts)):
                ax.text(count + 0.5, i, str(count), va='center', fontweight='bold')
            
            plt.tight_layout()
            output_file = os.path.join(self.plots_dir, '07_warning_summary.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"[PLOT] Saved: 07_warning_summary.png")
            
        except Exception as e:
            print(f"[PLOT ERROR] Warning summary failed: {e}")
            import traceback
            traceback.print_exc()
    
    # === PLOT 8: Research Diagnostics Scatter Matrix ===
    def plot_research_diagnostics(self) -> None:
        """Pairplot with research-level metrics."""
        try:
            if not SEABORN_AVAILABLE:
                print("[PLOT] Skipping research diagnostics - seaborn not available")
                return
            
            if not self.research_data:
                print("[PLOT] No research data for diagnostics")
                return
            
            data_rows = []
            for device_id, research in self.research_data.items():
                diag = research.get('research_diagnostics', {})
                if diag:
                    data_rows.append({
                        'NDR_Index': diag.get('ndr_index', np.nan),
                        'Kink_Voltage': diag.get('kink_voltage', np.nan),
                        'Pinch_Offset': diag.get('pinch_offset', np.nan) if diag.get('pinch_offset') else np.nan,
                        'Noise_Floor': diag.get('noise_floor', np.nan) if diag.get('noise_floor') else np.nan,
                        'Device_ID': device_id
                    })
            
            if not data_rows:
                print("[PLOT] No diagnostic data")
                return
            
            df = pd.DataFrame(data_rows)
            numeric_cols = ['NDR_Index', 'Kink_Voltage', 'Pinch_Offset', 'Noise_Floor']
            df_numeric = df[numeric_cols].dropna()
            
            if len(df_numeric) < 2:
                print("[PLOT] Insufficient data for pairplot")
                return
            
            # Create pairplot
            g = sns.pairplot(df_numeric, diag_kind='kde', plot_kws={'alpha': 0.6, 's': 50})
            g.fig.suptitle(f'Research Diagnostics Scatter Matrix - {self.sample_name}', 
                          fontsize=14, fontweight='bold', y=1.02)
            
            output_file = os.path.join(self.plots_dir, '08_research_diagnostics.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"[PLOT] Saved: 08_research_diagnostics.png")
            
        except Exception as e:
            print(f"[PLOT ERROR] Research diagnostics failed: {e}")
            import traceback
            traceback.print_exc()
    
    # === PLOT 9: Power & Energy Efficiency ===
    def plot_power_efficiency(self) -> None:
        """Power consumption vs memristivity score."""
        try:
            if not self.research_data:
                print("[PLOT] No research data for power efficiency")
                return
            
            scores = []
            power_consumption = []
            energy_per_switch = []
            
            for device_id, research in self.research_data.items():
                perf = research.get('performance_metrics', {})
                classification = research.get('classification', {})
                
                score = classification.get('memristivity_score', 0)
                power = perf.get('power_consumption_mean', np.nan)
                energy = perf.get('energy_per_switch_mean', np.nan)
                
                if not np.isnan(power) and not np.isnan(energy):
                    scores.append(score)
                    power_consumption.append(power)
                    energy_per_switch.append(energy)
            
            if not scores:
                print("[PLOT] No power/energy data")
                return
            
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
            
            # Power vs Score
            scatter1 = ax1.scatter(scores, power_consumption, c=scores, cmap='RdYlGn', 
                                  vmin=0, vmax=100, s=100, alpha=0.6, edgecolors='black')
            ax1.set_xlabel('Memristivity Score', fontsize=11, fontweight='bold')
            ax1.set_ylabel('Power Consumption (W)', fontsize=11, fontweight='bold')
            ax1.set_title('Power Consumption vs Performance', fontsize=12, fontweight='bold')
            ax1.grid(True, alpha=0.3)
            plt.colorbar(scatter1, ax=ax1, label='Score')
            
            # Energy distribution
            ax2.boxplot(energy_per_switch, vert=True)
            ax2.set_ylabel('Energy per Switch (J)', fontsize=11, fontweight='bold')
            ax2.set_title('Energy per Switch Distribution', fontsize=12, fontweight='bold')
            ax2.grid(axis='y', alpha=0.3)
            
            plt.suptitle(f'Power & Energy Efficiency - {self.sample_name}', 
                        fontsize=14, fontweight='bold')
            plt.tight_layout()
            
            output_file = os.path.join(self.plots_dir, '09_power_efficiency.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"[PLOT] Saved: 09_power_efficiency.png")
            self._export_power_efficiency_data(scores, power_consumption, energy_per_switch)
            
        except Exception as e:
            print(f"[PLOT ERROR] Power efficiency failed: {e}")
            import traceback
            traceback.print_exc()
    
    def _export_power_efficiency_data(self, scores=None, power=None, energy=None) -> None:
        """Export power efficiency data."""
        if scores is None:
            scores, power, energy = [], [], []
            for device_id, research in self.research_data.items():
                scores.append(research.get('classification', {}).get('memristivity_score', 0))
                power.append(research.get('power_metrics', {}).get('avg_power_consumption_w', np.nan))
                energy.append(research.get('power_metrics', {}).get('energy_per_switch_j', np.nan))
        
        if not scores:
            print("[ORIGIN] No power efficiency data to export")
            return
        
        df = pd.DataFrame({
            'Memristivity_Score': scores,
            'Power_Consumption_W': power,
            'Energy_per_Switch_J': energy
        })
        output_file = os.path.join(self.data_origin_formatted_dir, 'power_efficiency.csv')
        df.to_csv(output_file, index=False)
        print(f"[ORIGIN] Exported: power_efficiency.csv")
    
    # === PLOT 10: Device Leaderboard ===
    def plot_device_leaderboard(self) -> None:
        """Horizontal bar chart of top devices ranked by composite score."""
        try:
            # Calculate composite score for each device
            device_scores = []
            
            for dev in self.devices_data:
                memristivity = dev['classification'].get('memristivity_score', 0)
                # Safely extract quality metrics
                quality_dict = dev.get('quality', {})
                if isinstance(quality_dict, dict):
                    mw_quality = quality_dict.get('memory_window_quality', {})
                    if isinstance(mw_quality, dict):
                        quality = mw_quality.get('overall_quality_score', 0)
                        stability = mw_quality.get('avg_stability', 0)
                    else:
                        quality = 0
                        stability = 0
                else:
                    quality = 0
                    stability = 0
                switching_ratio = dev['resistance'].get('switching_ratio', 1)
                
                # Composite score: memristivity (40%), quality (30%), switching ratio (20%), stability (10%)
                # Normalize switching ratio (log scale)
                ratio_val = 1
                if switching_ratio is not None and isinstance(switching_ratio, (int, float)):
                    ratio_val = switching_ratio
                    
                ratio_score = min(100, np.log10(ratio_val) * 10) if ratio_val > 1 else 0
                
                composite = (memristivity * 0.4 + quality * 0.3 + ratio_score * 0.2 + stability * 0.1)
                
                device_scores.append({
                    'device_id': dev['device_id'],
                    'composite_score': composite,
                    'memristivity': memristivity,
                    'quality': quality,
                    'switching_ratio': switching_ratio
                })
            
            # Sort by composite score
            device_scores.sort(key=lambda x: x['composite_score'], reverse=True)
            top_devices = device_scores[:20]  # Top 20
            
            if not top_devices:
                print("[PLOT] No devices for leaderboard")
                return
            
            fig, ax = plt.subplots(figsize=(12, max(8, len(top_devices) * 0.4)))
            
            device_ids = [d['device_id'] for d in top_devices]
            scores = [d['composite_score'] for d in top_devices]
            
            # Color by tier
            colors = []
            for score in scores:
                if score >= 80:
                    colors.append('#4CAF50')  # Green
                elif score >= 60:
                    colors.append('#FFA500')  # Orange
                elif score >= 40:
                    colors.append('#FF9800')  # Deep orange
                else:
                    colors.append('#F44336')  # Red
            
            bars = ax.barh(device_ids, scores, color=colors)
            ax.set_xlabel('Composite Score', fontsize=12, fontweight='bold')
            ax.set_title(f'Device Leaderboard (Top 20) - {self.sample_name}', 
                        fontsize=14, fontweight='bold')
            ax.grid(axis='x', alpha=0.3)
            
            # Add score labels
            for i, (bar, score) in enumerate(zip(bars, scores)):
                ax.text(score + 1, i, f'{score:.1f}', va='center', fontweight='bold')
            
            plt.tight_layout()
            output_file = os.path.join(self.plots_dir, '10_device_leaderboard.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"[PLOT] Saved: 10_device_leaderboard.png")
            self._export_leaderboard_data(device_scores)
            
        except Exception as e:
            print(f"[PLOT ERROR] Leaderboard failed: {e}")
            import traceback
            traceback.print_exc()
    
    def _export_leaderboard_data(self, device_scores=None) -> None:
        """Export leaderboard data."""
        if device_scores is None:
            device_scores = []
            for dev in self.devices_data:
                memristivity = dev['classification'].get('memristivity_score', 0)
                quality_dict = dev.get('quality', {})
                if isinstance(quality_dict, dict):
                    mw_quality = quality_dict.get('memory_window_quality', {})
                    if isinstance(mw_quality, dict):
                        quality = mw_quality.get('overall_quality_score', 0)
                        stability = mw_quality.get('avg_stability', 0)
                    else:
                        quality = 0
                        stability = 0
                else:
                    quality = 0
                    stability = 0
                switching_ratio = dev['resistance'].get('switching_ratio', 1)
                
                ratio_val = 1
                if switching_ratio is not None and isinstance(switching_ratio, (int, float)):
                    ratio_val = switching_ratio
                    
                ratio_score = min(100, np.log10(ratio_val) * 10) if ratio_val > 1 else 0
                composite = (memristivity * 0.4 + quality * 0.3 + ratio_score * 0.2 + stability * 0.1)
                device_scores.append({
                    'device_id': dev['device_id'],
                    'composite_score': composite,
                    'memristivity': memristivity,
                    'quality': quality,
                    'switching_ratio': switching_ratio
                })
            device_scores.sort(key=lambda x: x['composite_score'], reverse=True)
        
        df = pd.DataFrame(device_scores)
        output_file = os.path.join(self.data_origin_formatted_dir, 'device_leaderboard.csv')
        df.to_csv(output_file, index=False)
        print(f"[ORIGIN] Exported: device_leaderboard.csv")
    
    # === PLOT 11: Spatial Distribution Maps ===
    def plot_spatial_distributions(self) -> None:
        """3x heatmaps showing spatial distribution of metrics."""
        try:
            # Parse positions
            memristivity_map = {}
            quality_map = {}
            switching_map = {}
            
            for dev in self.devices_data:
                device_id = dev['device_id']
                parts = device_id.split('_')
                if len(parts) >= 3:
                    try:
                        row = parts[-2]
                        col = int(parts[-1])
                        
                        memristivity_map[(row, col)] = dev['classification'].get('memristivity_score', 0)
                        # Safely extract quality
                        quality_dict = dev.get('quality', {})
                        if isinstance(quality_dict, dict):
                            mw_quality = quality_dict.get('memory_window_quality', {})
                            if isinstance(mw_quality, dict):
                                quality_map[(row, col)] = mw_quality.get('overall_quality_score', 0)
                            else:
                                quality_map[(row, col)] = 0
                        else:
                            quality_map[(row, col)] = 0
                        switching_map[(row, col)] = dev['resistance'].get('switching_ratio', 1)
                    except (ValueError, IndexError):
                        continue
            
            if not memristivity_map:
                print("[PLOT] No spatial data")
                return
            
            rows = sorted(set(r for r, c in memristivity_map.keys()))
            cols = sorted(set(c for r, c in memristivity_map.keys()))
            
            # Create grids
            grid_mem = np.zeros((len(rows), len(cols)))
            grid_qual = np.zeros((len(rows), len(cols)))
            grid_switch = np.zeros((len(rows), len(cols)))
            
            for i, row in enumerate(rows):
                for j, col in enumerate(cols):
                    grid_mem[i, j] = memristivity_map.get((row, col), 0)
                    grid_qual[i, j] = quality_map.get((row, col), 0)
                    grid_switch[i, j] = switching_map.get((row, col), 0)
            
            fig, axes = plt.subplots(1, 3, figsize=(18, 6))
            
            # Memristivity
            im1 = axes[0].imshow(grid_mem, cmap='RdYlGn', vmin=0, vmax=100, aspect='auto')
            axes[0].set_title('Memristivity Score', fontsize=12, fontweight='bold')
            axes[0].set_xticks(range(len(cols)))
            axes[0].set_xticklabels(cols)
            axes[0].set_yticks(range(len(rows)))
            axes[0].set_yticklabels(rows)
            plt.colorbar(im1, ax=axes[0])
            
            # Quality
            im2 = axes[1].imshow(grid_qual, cmap='RdYlGn', vmin=0, vmax=100, aspect='auto')
            axes[1].set_title('Memory Window Quality', fontsize=12, fontweight='bold')
            axes[1].set_xticks(range(len(cols)))
            axes[1].set_xticklabels(cols)
            axes[1].set_yticks(range(len(rows)))
            axes[1].set_yticklabels(rows)
            plt.colorbar(im2, ax=axes[1])
            
            # Switching Ratio (log scale)
            grid_switch_log = np.log10(grid_switch + 1)
            im3 = axes[2].imshow(grid_switch_log, cmap='viridis', aspect='auto')
            axes[2].set_title('Switching Ratio (log)', fontsize=12, fontweight='bold')
            axes[2].set_xticks(range(len(cols)))
            axes[2].set_xticklabels(cols)
            axes[2].set_yticks(range(len(rows)))
            axes[2].set_yticklabels(rows)
            plt.colorbar(im3, ax=axes[2])
            
            plt.suptitle(f'Spatial Distribution Maps - {self.sample_name}', 
                        fontsize=14, fontweight='bold')
            plt.tight_layout()
            
            output_file = os.path.join(self.plots_dir, '11_spatial_distributions.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"[PLOT] Saved: 11_spatial_distributions.png")
            self._export_spatial_data(memristivity_map, quality_map, switching_map)
            
        except Exception as e:
            print(f"[PLOT ERROR] Spatial distributions failed: {e}")
            import traceback
            traceback.print_exc()
    
    def _export_spatial_data(self, mem_map=None, qual_map=None, switch_map=None) -> None:
        """Export spatial data."""
        if mem_map is None:
            mem_map, qual_map, switch_map = {}, {}, {}
            for dev in self.devices_data:
                device_id = dev['device_id']
                parts = device_id.split('_')
                if len(parts) >= 3:
                    try:
                        row = parts[-2]
                        col = int(parts[-1])
                        mem_map[(row, col)] = dev['classification'].get('memristivity_score', 0)
                        quality_dict = dev.get('quality', {})
                        if isinstance(quality_dict, dict):
                            mw_quality = quality_dict.get('memory_window_quality', {})
                            if isinstance(mw_quality, dict):
                                qual_map[(row, col)] = mw_quality.get('overall_quality_score', 0)
                            else:
                                qual_map[(row, col)] = 0
                        else:
                            qual_map[(row, col)] = 0
                        switch_map[(row, col)] = dev['resistance'].get('switching_ratio', 1)
                    except (ValueError, IndexError):
                        continue
        
        rows = []
        all_positions = set(mem_map.keys()) | set(qual_map.keys()) | set(switch_map.keys())
        for row, col in all_positions:
            rows.append({
                'Device_ID': f"{self.sample_name}_{row}_{col}",
                'Section': row,
                'Device_Number': col,
                'Memristivity_Score': mem_map.get((row, col), 0),
                'Memory_Window_Quality': qual_map.get((row, col), 0),
                'Switching_Ratio': switch_map.get((row, col), 1)
            })
        df = pd.DataFrame(rows)
        output_file = os.path.join(self.data_origin_formatted_dir, 'spatial_data.csv')
        df.to_csv(output_file, index=False)
        print(f"[ORIGIN] Exported: spatial_data.csv")
    
    # === PLOT 12: Forming Status Distribution ===
    def plot_forming_status(self) -> None:
        """Pie chart showing device forming status."""
        try:
            forming = 0
            formed = 0
            degrading = 0
            unstable = 0
            
            for dev in self.devices_data:
                measurements = dev.get('all_measurements', [])
                if len(measurements) < 2:
                    continue
                
                scores = [m.get('classification', {}).get('memristivity_score', 0) 
                         for m in measurements]
                # Filter None values
                scores = [s for s in scores if s is not None]
                
                if len(scores) > 1:
                    improvement = scores[-1] - scores[0]
                    variation = np.std(scores) if len(scores) > 1 else 0
                    
                    if improvement > 15:
                        forming += 1
                    elif improvement < -10:
                        degrading += 1
                    elif variation > 20:
                        unstable += 1
                    else:
                        formed += 1
            
            if forming + formed + degrading + unstable == 0:
                print("[PLOT] No multi-measurement data for forming status")
                return
            
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
            
            # Pie chart
            sizes = [forming, formed, degrading, unstable]
            labels = ['Forming', 'Formed', 'Degrading', 'Unstable']
            colors = ['#2196F3', '#4CAF50', '#F44336', '#FF9800']
            explode = (0.1, 0, 0.1, 0.1)
            
            ax1.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.1f%%',
                   shadow=True, startangle=90)
            ax1.set_title('Forming Status Distribution', fontsize=12, fontweight='bold')
            
            # Bar chart
            ax2.bar(labels, sizes, color=colors)
            ax2.set_ylabel('Device Count', fontsize=11, fontweight='bold')
            ax2.set_title('Forming Status Count', fontsize=12, fontweight='bold')
            ax2.grid(axis='y', alpha=0.3)
            
            for i, (label, size) in enumerate(zip(labels, sizes)):
                ax2.text(i, size + 0.5, str(size), ha='center', fontweight='bold')
            
            plt.suptitle(f'Forming Status Distribution - {self.sample_name}', 
                        fontsize=14, fontweight='bold')
            plt.tight_layout()
            
            output_file = os.path.join(self.plots_dir, '12_forming_status.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"[PLOT] Saved: 12_forming_status.png")
            self._export_forming_status_data(forming, formed, degrading, unstable)
            
        except Exception as e:
            print(f"[PLOT ERROR] Forming status failed: {e}")
            import traceback
            traceback.print_exc()
    
    def _export_forming_status_data(self, forming=None, formed=None, degrading=None, unstable=None) -> None:
        """Export forming status data."""
        if forming is None:
            forming = formed = degrading = unstable = 0
            for dev in self.devices_data:
                all_measurements = dev.get('all_measurements', [])
                if len(all_measurements) >= 3:
                    scores = [m.get('classification', {}).get('memristivity_score', 0) for m in all_measurements]
                    if len(scores) >= 3:
                        trend = scores[-1] - scores[0]
                        if trend > 15:
                            forming += 1
                        elif trend < -10:
                            degrading += 1
                        elif abs(scores[-1] - scores[-2]) > 5:
                            unstable += 1
                        else:
                            formed += 1
        
        df = pd.DataFrame({
            'Status': ['Forming', 'Formed', 'Degrading', 'Unstable'],
            'Count': [forming, formed, degrading, unstable]
        })
        output_file = os.path.join(self.data_origin_formatted_dir, 'forming_status.csv')
        df.to_csv(output_file, index=False)
        print(f"[ORIGIN] Exported: forming_status.csv")
    
    def _export_device_size_data(self) -> None:
        """Export device size comparison data."""
        try:
            rows = []
            for dev in self.devices_data:
                if dev.get('device_size'):  # Only include devices with size metadata
                    rows.append({
                        'Device_ID': dev['device_id'],
                        'Section': dev.get('section', ''),
                        'Device_Size': dev.get('device_size', ''),
                        'Area_um2': dev.get('area_um2', np.nan),
                        'Memristivity_Score': dev['classification'].get('memristivity_score', 0) or 0,
                        'Device_Type': dev['classification'].get('device_type', 'unknown'),
                        'Switching_Ratio': dev['resistance'].get('switching_ratio', np.nan),
                        'Memory_Window_Quality': self._safe_get_quality_score(dev),
                        'Ron_Mean': dev['resistance'].get('ron_mean', np.nan),
                        'Roff_Mean': dev['resistance'].get('roff_mean', np.nan),
                        'On_Off_Ratio': dev['resistance'].get('on_off_ratio', np.nan),
                        'Confidence': dev['classification'].get('confidence', 0),
                    })
            
            if rows:
                df = pd.DataFrame(rows)
                output_file = os.path.join(self.data_origin_formatted_dir, 'device_size_comparison.csv')
                df.to_csv(output_file, index=False)
                print(f"[ORIGIN] Exported: device_size_comparison.csv")
        except Exception as e:
            print(f"[ORIGIN ERROR] Device size data export failed: {e}")
    
    # === PLOT 13: Device Size Comparison ===
    def plot_device_size_comparison(self) -> None:
        """Compare memristivity and metrics across device sizes (100um, 200um, 400um)."""
        try:
            # Disable LaTeX/math text to prevent parsing errors
            plt.rcParams['text.usetex'] = False
            plt.rcParams['mathtext.default'] = 'regular'
            plt.rcParams['axes.formatter.use_mathtext'] = False
            
            # Group devices by size
            devices_by_size = {
                '100x100um': [d for d in self.devices_data if d.get('device_size') == '100x100um'],
                '200x200um': [d for d in self.devices_data if d.get('device_size') == '200x200um'],
                '400x400um': [d for d in self.devices_data if d.get('device_size') == '400x400um']
            }
            
            # Filter out empty groups - only include sizes with devices
            devices_by_size = {size: devices for size, devices in devices_by_size.items() if devices}
            
            if not devices_by_size:
                print("[PLOT] No devices with size metadata for size comparison")
                return
            
            # Determine which sizes are present (prioritize 100um and 200um)
            sizes_present = list(devices_by_size.keys())
            
            # Create figure with 2x2 subplot grid
            fig, axes = plt.subplots(2, 2, figsize=(14, 12))
            fig.suptitle(f'Device Size Comparison - {self.sample_name}', fontsize=16, fontweight='bold')
            
            # Prepare data for each size
            size_labels = []
            memristivity_scores = []
            switching_ratios = []
            device_types_by_size = {}
            mean_metrics = {'memristivity': [], 'quality': [], 'switching_ratio': []}
            
            for size in sizes_present:
                devices = devices_by_size[size]
                size_labels.append(size)
                
                # Extract memristivity scores
                scores = [d['classification'].get('memristivity_score', 0) or 0 for d in devices]
                memristivity_scores.append(scores)
                
                # Extract switching ratios
                ratios = [d['resistance'].get('switching_ratio', 1) or 1 for d in devices]
                switching_ratios.append(ratios)
                
                # Count device types
                type_counts = {}
                for d in devices:
                    dtype = d['classification'].get('device_type', 'unknown')
                    type_counts[dtype] = type_counts.get(dtype, 0) + 1
                device_types_by_size[size] = type_counts
                
                # Calculate mean metrics
                mean_metrics['memristivity'].append(np.mean(scores) if scores else 0)
                mean_metrics['quality'].append(np.mean([self._safe_get_quality_score(d) for d in devices]))
                mean_metrics['switching_ratio'].append(np.mean(ratios) if ratios else 1)
            
            # Plot 1: Memristivity Score Box Plot
            ax1 = axes[0, 0]
            if memristivity_scores:
                bp1 = ax1.boxplot(memristivity_scores, labels=size_labels, patch_artist=True)
                # Color boxes
                colors = ['#4CAF50', '#2196F3', '#FF9800']  # Green, Blue, Orange
                for patch, color in zip(bp1['boxes'], colors[:len(bp1['boxes'])]):
                    patch.set_facecolor(color)
                    patch.set_alpha(0.7)
                ax1.set_ylabel('Memristivity Score', fontweight='bold')
                ax1.set_title('Memristivity Score Distribution', fontweight='bold')
                ax1.grid(True, alpha=0.3, axis='y')
            
            # Plot 2: Switching Ratio Box Plot
            ax2 = axes[0, 1]
            if switching_ratios:
                bp2 = ax2.boxplot(switching_ratios, labels=size_labels, patch_artist=True)
                for patch, color in zip(bp2['boxes'], colors[:len(bp2['boxes'])]):
                    patch.set_facecolor(color)
                    patch.set_alpha(0.7)
                ax2.set_ylabel('Switching Ratio (Roff/Ron)', fontweight='bold')
                ax2.set_title('Switching Ratio Distribution', fontweight='bold')
                ax2.set_yscale('log')
                ax2.grid(True, alpha=0.3, axis='y')
            
            # Plot 3: Device Type Distribution (Stacked Bar)
            ax3 = axes[1, 0]
            type_names = sorted(set(t for counts in device_types_by_size.values() for t in counts.keys()))
            if type_names and device_types_by_size:
                x = np.arange(len(size_labels))
                width = 0.6
                bottom = np.zeros(len(size_labels))
                
                colors_dict = {'memristive': '#4CAF50', 'ohmic': '#9E9E9E', 'capacitive': '#2196F3',
                              'conductive': '#FF9800', 'memcapacitive': '#9C27B0', 'uncertain': '#F44336'}
                
                for tname in type_names:
                    counts = [device_types_by_size[size].get(tname, 0) for size in size_labels]
                    totals = [len(devices_by_size[size]) for size in size_labels]
                    percentages = [100 * c / t if t > 0 else 0 for c, t in zip(counts, totals)]
                    ax3.bar(x, percentages, width, label=tname.replace('_', ' ').title(),
                           bottom=bottom, color=colors_dict.get(tname, '#757575'))
                    bottom += percentages
                
                ax3.set_xlabel('Device Size', fontweight='bold')
                ax3.set_ylabel('Percentage (%)', fontweight='bold')
                ax3.set_title('Device Type Distribution by Size', fontweight='bold')
                ax3.set_xticks(x)
                ax3.set_xticklabels(size_labels)
                ax3.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
                ax3.grid(True, alpha=0.3, axis='y')
            
            # Plot 4: Mean Metrics Comparison
            ax4 = axes[1, 1]
            if mean_metrics['memristivity']:
                x = np.arange(len(size_labels))
                width = 0.25
                metrics = ['Memristivity', 'Quality', 'Switching Ratio']
                y_data = [
                    mean_metrics['memristivity'],
                    mean_metrics['quality'],
                    [r if r > 0 else 1 for r in mean_metrics['switching_ratio']]  # Normalize for display
                ]
                
                for i, (metric, y_vals) in enumerate(zip(metrics, y_data)):
                    # Normalize switching ratio for better visualization (divide by 10)
                    if metric == 'Switching Ratio':
                        y_vals = [v / 10.0 for v in y_vals]
                    offset = (i - 1) * width
                    bars = ax4.bar(x + offset, y_vals, width, label=metric, alpha=0.8)
                
                ax4.set_xlabel('Device Size', fontweight='bold')
                ax4.set_ylabel('Normalized Score', fontweight='bold')
                ax4.set_title('Mean Metrics Comparison', fontweight='bold')
                ax4.set_xticks(x)
                ax4.set_xticklabels(size_labels)
                ax4.legend()
                ax4.grid(True, alpha=0.3, axis='y')
            
            plt.tight_layout()
            output_file = os.path.join(self.plots_dir, '13_device_size_comparison.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"[PLOT] Saved: 13_device_size_comparison.png")
            
        except Exception as e:
            print(f"[PLOT ERROR] Device size comparison failed: {e}")
            import traceback
            traceback.print_exc()
    
    # === Helper: Find Minimum Sweep Number for Code Name ===
    def _find_min_sweep_for_code_name(self, device_dir: str, code_name: str) -> Optional[int]:
        """
        Find the minimum sweep number for a given code_name in a device folder.
        This treats the lowest number as the first measurement for that code_name.
        
        Args:
            device_dir: Path to device directory
            code_name: Code name to search for
            
        Returns:
            int or None: Minimum sweep number for this code_name, or None if not found
        """
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
    
    # === Helper: Load I-V Data from Device Files ===
    def _load_iv_data_for_device(self, device_id: str, sweep_num: Optional[int] = None, code_name: Optional[str] = None) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Load voltage and current data for a device by reading sweep file.
        
        Args:
            device_id: Device ID (format: sample_section_device_num)
            sweep_num: Sweep number to read (if None, finds minimum for code_name)
            code_name: Code name to filter by (if provided, finds minimum sweep for this code_name)
            
        Returns:
            (voltage_array, current_array) or (None, None) if not available
        """
        try:
            # Parse device_id: sample_name_section_device_num
            parts = device_id.split('_')
            if len(parts) < 3:
                return None, None
            
            section = parts[-2]  # Section letter
            device_num = parts[-1]  # Device number
            
            # Build device directory path
            device_dir = os.path.join(self.sample_dir, section, device_num)
            
            if not os.path.exists(device_dir):
                return None, None
            
            # If code_name provided, find minimum sweep number for that code_name
            if code_name and sweep_num is None:
                sweep_num = self._find_min_sweep_for_code_name(device_dir, code_name)
                if sweep_num is None:
                    return None, None
            elif sweep_num is None:
                sweep_num = 1  # Default to 1 if neither provided
            
            # Find sweep file (format: {sweep_num}-*.txt)
            import glob
            sweep_pattern = os.path.join(device_dir, f'{sweep_num}-*.txt')
            sweep_files = glob.glob(sweep_pattern)
            sweep_files = [f for f in sweep_files if os.path.basename(f) != 'log.txt']
            
            # If code_name provided, filter to only files with matching code_name
            if code_name:
                matching_files = []
                for f in sweep_files:
                    try:
                        filename = os.path.basename(f)
                        parts = filename.replace('.txt', '').split('-')
                        if len(parts) > 6 and parts[6] == code_name:
                            matching_files.append(f)
                    except (ValueError, IndexError):
                        continue
                sweep_files = matching_files
            
            if not sweep_files:
                return None, None
            
            # Read first matching file
            try:
                data = np.loadtxt(sweep_files[0], skiprows=1)
                if data.ndim == 1:
                    data = data.reshape(1, -1)
                if data.shape[1] >= 2:
                    voltage = data[:, 0]
                    current = data[:, 1]
                    return voltage, current
            except Exception:
                # Try without skiprows if file has no header
                try:
                    data = np.loadtxt(sweep_files[0], skiprows=0)
                    if data.ndim == 1:
                        data = data.reshape(1, -1)
                    if data.shape[1] >= 2:
                        voltage = data[:, 0]
                        current = data[:, 1]
                        return voltage, current
                except Exception:
                    pass
            
            return None, None
        except Exception as e:
            return None, None
    
    # === SIZE COMPARISON PLOTS (I-V Overlays) ===
    def generate_size_comparison_plots(self) -> None:
        """Generate all 3 specialized I-V overlay plots grouped by device size."""
        try:
            self._log("Generating size comparison I-V overlay plots...")
            self.plot_size_memristive_overlays()
            self.plot_size_top_per_section()
            self.plot_size_top_across_sample()
            self._log(f"✓ Size comparison plots saved to: {self.size_comparison_dir}")
        except Exception as e:
            self._log(f"Error generating size comparison plots: {e}")
            import traceback
            traceback.print_exc()
    
    def plot_size_memristive_overlays(self) -> None:
        """Overlay all memristive device I-V curves, grouped by size with locked axes."""
        try:
            # Disable LaTeX/math text to prevent parsing errors
            plt.rcParams['text.usetex'] = False
            plt.rcParams['mathtext.default'] = 'regular'
            plt.rcParams['axes.formatter.use_mathtext'] = False
            
            # Filter memristive devices
            memristive_devices = [d for d in self.devices_data 
                                 if d.get('classification', {}).get('device_type') == 'memristive']
            
            if not memristive_devices:
                print("[PLOT] No memristive devices for I-V overlay")
                return
            
            # Group by size
            devices_by_size = {
                '100x100um': [d for d in memristive_devices if d.get('device_size') == '100x100um'],
                '200x200um': [d for d in memristive_devices if d.get('device_size') == '200x200um'],
                '400x400um': [d for d in memristive_devices if d.get('device_size') == '400x400um']
            }
            
            # Filter out empty groups
            devices_by_size = {size: devices for size, devices in devices_by_size.items() if devices}
            
            if not devices_by_size:
                print("[PLOT] No memristive devices with size metadata")
                return
            
            sizes_present = sorted(devices_by_size.keys())
            num_sizes = len(sizes_present)
            
            # Create figure with dynamic layout (1 row × N cols)
            fig, axes = plt.subplots(1, num_sizes, figsize=(6*num_sizes, 6))
            if num_sizes == 1:
                axes = [axes]
            
            fig.suptitle(f'All Memristive I-V Curves by Size - {self.sample_name}', 
                        fontsize=14, fontweight='bold')
            
            # Determine global axis limits from all data
            all_voltages = []
            all_currents = []
            for devices in devices_by_size.values():
                for dev in devices:
                    v, i = self._load_iv_data_for_device(dev['device_id'])
                    if v is not None and i is not None:
                        all_voltages.extend(v)
                        all_currents.extend(i)
            
            if not all_voltages or not all_currents:
                print("[PLOT] No I-V data available for memristive devices")
                return
            
            v_min, v_max = min(all_voltages), max(all_voltages)
            i_min, i_max = min(all_currents), max(all_currents)
            i_max = max(abs(i_min), abs(i_max))  # Use symmetric range
            
            # Plot each size group
            for idx, size in enumerate(sizes_present):
                ax = axes[idx]
                devices = devices_by_size[size]
                
                plotted_count = 0
                for dev in devices:
                    v, i = self._load_iv_data_for_device(dev['device_id'])
                    if v is not None and i is not None:
                        ax.plot(v, i * 1e6, alpha=0.4, linewidth=0.8)  # Convert to μA
                        plotted_count += 1
                
                ax.set_xlabel('Voltage (V)', fontweight='bold')
                ax.set_ylabel('Current (μA)', fontweight='bold')
                ax.set_title(f'{size} (n={plotted_count})', fontweight='bold')
                ax.grid(True, alpha=0.3)
                ax.set_xlim(v_min, v_max)
                ax.set_ylim(-i_max * 1e6 * 1.1, i_max * 1e6 * 1.1)  # Symmetric with margin
            
            plt.tight_layout()
            output_file = os.path.join(self.size_comparison_dir, 'memristive_iv_overlays_by_size.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"[PLOT] Saved: size_comparison/memristive_iv_overlays_by_size.png")
            
        except Exception as e:
            print(f"[PLOT ERROR] Memristive I-V overlays failed: {e}")
            import traceback
            traceback.print_exc()
    
    def plot_size_top_per_section(self) -> None:
        """Show top 1 device from each section, grouped by size with locked axes."""
        try:
            # Disable LaTeX/math text to prevent parsing errors
            plt.rcParams['text.usetex'] = False
            plt.rcParams['mathtext.default'] = 'regular'
            plt.rcParams['axes.formatter.use_mathtext'] = False
            
            # Group devices by section and size
            devices_by_section_size = {}
            for dev in self.devices_data:
                section = dev.get('section')
                size = dev.get('device_size')
                if section and size:
                    key = (section, size)
                    if key not in devices_by_section_size:
                        devices_by_section_size[key] = []
                    devices_by_section_size[key].append(dev)
            
            if not devices_by_section_size:
                print("[PLOT] No devices with section and size metadata")
                return
            
            # Group by size and select top device per section
            devices_by_size = {}
            for (section, size), devices in devices_by_section_size.items():
                if size not in devices_by_size:
                    devices_by_size[size] = {}
                # Select top device by memristivity score
                devices_sorted = sorted(devices, 
                                      key=lambda d: d.get('classification', {}).get('memristivity_score', 0) or 0,
                                      reverse=True)
                devices_by_size[size][section] = devices_sorted[0] if devices_sorted else None
            
            # Filter out empty groups
            devices_by_size = {size: sections for size, sections in devices_by_size.items() 
                             if sections and any(d is not None for d in sections.values())}
            
            if not devices_by_size:
                print("[PLOT] No devices for top per section plot")
                return
            
            sizes_present = sorted(devices_by_size.keys())
            num_sizes = len(sizes_present)
            
            # Create figure with dynamic layout
            fig, axes = plt.subplots(1, num_sizes, figsize=(6*num_sizes, 6))
            if num_sizes == 1:
                axes = [axes]
            
            fig.suptitle(f'Top Device per Section by Size - {self.sample_name}', 
                        fontsize=14, fontweight='bold')
            
            # Determine global axis limits
            all_voltages = []
            all_currents = []
            for sections in devices_by_size.values():
                for dev in sections.values():
                    if dev:
                        v, i = self._load_iv_data_for_device(dev['device_id'])
                        if v is not None and i is not None:
                            all_voltages.extend(v)
                            all_currents.extend(i)
            
            if not all_voltages or not all_currents:
                print("[PLOT] No I-V data available")
                return
            
            v_min, v_max = min(all_voltages), max(all_voltages)
            i_max = max(abs(min(all_currents)), abs(max(all_currents)))
            
            # Plot each size group
            for idx, size in enumerate(sizes_present):
                ax = axes[idx]
                sections = devices_by_size[size]
                
                plotted_count = 0
                for section in sorted(sections.keys()):
                    dev = sections[section]
                    if dev:
                        v, i = self._load_iv_data_for_device(dev['device_id'])
                        if v is not None and i is not None:
                            ax.plot(v, i * 1e6, label=f'{section}', alpha=0.7, linewidth=1.5)
                            plotted_count += 1
                
                ax.set_xlabel('Voltage (V)', fontweight='bold')
                ax.set_ylabel('Current (μA)', fontweight='bold')
                ax.set_title(f'{size} (n={plotted_count})', fontweight='bold')
                ax.grid(True, alpha=0.3)
                ax.legend()
                ax.set_xlim(v_min, v_max)
                ax.set_ylim(-i_max * 1e6 * 1.1, i_max * 1e6 * 1.1)
            
            plt.tight_layout()
            output_file = os.path.join(self.size_comparison_dir, 'top_device_per_section_by_size.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"[PLOT] Saved: size_comparison/top_device_per_section_by_size.png")
            
        except Exception as e:
            print(f"[PLOT ERROR] Top per section plot failed: {e}")
            import traceback
            traceback.print_exc()
    
    def plot_size_top_across_sample(self) -> None:
        """Show top 5 devices overall, grouped by size with locked axes."""
        try:
            # Disable LaTeX/math text to prevent parsing errors
            plt.rcParams['text.usetex'] = False
            plt.rcParams['mathtext.default'] = 'regular'
            plt.rcParams['axes.formatter.use_mathtext'] = False
            
            # Rank all devices by memristivity score (or composite score)
            devices_with_scores = []
            for dev in self.devices_data:
                score = dev.get('classification', {}).get('memristivity_score', 0) or 0
                # Composite score: memristivity + quality
                quality = self._safe_get_quality_score(dev)
                if not np.isnan(quality):
                    composite = score * 0.7 + quality * 0.3
                else:
                    composite = score
                devices_with_scores.append((dev, composite))
            
            # Sort by composite score
            devices_with_scores.sort(key=lambda x: x[1], reverse=True)
            
            # Group top devices by size (up to 5 per size)
            devices_by_size = {}
            for dev, score in devices_with_scores:
                size = dev.get('device_size')
                if size:
                    if size not in devices_by_size:
                        devices_by_size[size] = []
                    if len(devices_by_size[size]) < 5:
                        devices_by_size[size].append(dev)
            
            # Filter out empty groups
            devices_by_size = {size: devices for size, devices in devices_by_size.items() if devices}
            
            if not devices_by_size:
                print("[PLOT] No devices with size metadata for top 5 plot")
                return
            
            sizes_present = sorted(devices_by_size.keys())
            num_sizes = len(sizes_present)
            
            # Create figure with dynamic layout
            fig, axes = plt.subplots(1, num_sizes, figsize=(6*num_sizes, 6))
            if num_sizes == 1:
                axes = [axes]
            
            fig.suptitle(f'Top 5 Devices by Size - {self.sample_name}', 
                        fontsize=14, fontweight='bold')
            
            # Determine global axis limits
            all_voltages = []
            all_currents = []
            for devices in devices_by_size.values():
                for dev in devices:
                    v, i = self._load_iv_data_for_device(dev['device_id'])
                    if v is not None and i is not None:
                        all_voltages.extend(v)
                        all_currents.extend(i)
            
            if not all_voltages or not all_currents:
                print("[PLOT] No I-V data available")
                return
            
            v_min, v_max = min(all_voltages), max(all_voltages)
            i_max = max(abs(min(all_currents)), abs(max(all_currents)))
            
            # Plot each size group
            for idx, size in enumerate(sizes_present):
                ax = axes[idx]
                devices = devices_by_size[size]
                
                plotted_count = 0
                for i, dev in enumerate(devices):
                    v, i_data = self._load_iv_data_for_device(dev['device_id'])
                    if v is not None and i_data is not None:
                        score = dev.get('classification', {}).get('memristivity_score', 0) or 0
                        ax.plot(v, i_data * 1e6, label=f'#{i+1} ({score:.0f})', 
                               alpha=0.7, linewidth=1.5)
                        plotted_count += 1
                
                ax.set_xlabel('Voltage (V)', fontweight='bold')
                ax.set_ylabel('Current (μA)', fontweight='bold')
                ax.set_title(f'{size} (n={plotted_count})', fontweight='bold')
                ax.grid(True, alpha=0.3)
                ax.legend()
                ax.set_xlim(v_min, v_max)
                ax.set_ylim(-i_max * 1e6 * 1.1, i_max * 1e6 * 1.1)
            
            plt.tight_layout()
            output_file = os.path.join(self.size_comparison_dir, 'top5_devices_by_size.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"[PLOT] Saved: size_comparison/top5_devices_by_size.png")
            
        except Exception as e:
            print(f"[PLOT ERROR] Top 5 devices plot failed: {e}")
            import traceback
            traceback.print_exc()
    
    # === PLOT 14: Metric Correlation Heatmap ===
    def plot_metric_correlation_heatmap(self) -> None:
        """Heatmap showing correlations between key device metrics."""
        try:
            # Extract numeric metrics
            metrics_data = []
            for dev in self.devices_data:
                row = {
                    'Memristivity_Score': dev['classification'].get('memristivity_score', np.nan),
                    'Confidence': dev['classification'].get('confidence', np.nan),
                    'Ron_Mean': dev['resistance'].get('ron_mean', np.nan),
                    'Roff_Mean': dev['resistance'].get('roff_mean', np.nan),
                    'Switching_Ratio': dev['resistance'].get('switching_ratio', np.nan),
                    'On_Off_Ratio': dev['resistance'].get('on_off_ratio', np.nan),
                    'Memory_Window_Quality': self._safe_get_quality_score(dev),
                    'Total_Measurements': dev.get('total_measurements', 0),
                    'Warning_Count': len(dev.get('warnings', []))
                }
                metrics_data.append(row)
            
            df = pd.DataFrame(metrics_data)
            # Drop rows with all NaN
            df = df.dropna(how='all')
            
            if len(df) < 3:
                print("[PLOT] Insufficient data for correlation heatmap")
                return
            
            # Calculate correlation matrix
            corr_matrix = df.corr()
            
            # Create heatmap
            fig, ax = plt.subplots(figsize=(12, 10))
            
            # Use custom colormap: blue (negative) -> white (zero) -> red (positive)
            im = ax.imshow(corr_matrix, cmap='RdBu_r', vmin=-1, vmax=1, aspect='auto')
            
            # Set ticks and labels
            ax.set_xticks(range(len(corr_matrix.columns)))
            ax.set_yticks(range(len(corr_matrix.columns)))
            ax.set_xticklabels(corr_matrix.columns, rotation=45, ha='right')
            ax.set_yticklabels(corr_matrix.columns)
            
            # Add correlation values as text
            for i in range(len(corr_matrix.columns)):
                for j in range(len(corr_matrix.columns)):
                    value = corr_matrix.iloc[i, j]
                    if not np.isnan(value):
                        text_color = 'white' if abs(value) > 0.5 else 'black'
                        ax.text(j, i, f'{value:.2f}', ha='center', va='center',
                               color=text_color, fontsize=9, fontweight='bold')
            
            ax.set_title(f'Metric Correlation Heatmap - {self.sample_name}', 
                        fontsize=14, fontweight='bold', pad=20)
            
            # Colorbar
            cbar = plt.colorbar(im, ax=ax)
            cbar.set_label('Correlation Coefficient', fontsize=12)
            
            plt.tight_layout()
            output_file = os.path.join(self.plots_dir, '14_metric_correlation_heatmap.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"[PLOT] Saved: 14_metric_correlation_heatmap.png")
            self._export_metric_correlation_data(corr_matrix)
            
        except Exception as e:
            print(f"[PLOT ERROR] Correlation heatmap failed: {e}")
            import traceback
            traceback.print_exc()
    
    def _export_metric_correlation_data(self, corr_matrix: Optional[pd.DataFrame] = None) -> None:
        """Export correlation matrix data."""
        if corr_matrix is None:
            metrics_data = []
            for dev in self.devices_data:
                row = {
                    'Memristivity_Score': dev['classification'].get('memristivity_score', np.nan),
                    'Confidence': dev['classification'].get('confidence', np.nan),
                    'Ron_Mean': dev['resistance'].get('ron_mean', np.nan),
                    'Roff_Mean': dev['resistance'].get('roff_mean', np.nan),
                    'Switching_Ratio': dev['resistance'].get('switching_ratio', np.nan),
                    'Memory_Window_Quality': self._safe_get_quality_score(dev),
                }
                metrics_data.append(row)
            df = pd.DataFrame(metrics_data).dropna(how='all')
            if len(df) >= 3:
                corr_matrix = df.corr()
            else:
                return
        
        output_file = os.path.join(self.data_origin_formatted_dir, 'metric_correlation.csv')
        corr_matrix.to_csv(output_file)
        print(f"[ORIGIN] Exported: metric_correlation.csv")
    
    # === PLOT 15: Section Performance Comparison ===
    def plot_section_performance_comparison(self) -> None:
        """Compare key metrics across sections using grouped bar charts."""
        try:
            # Group devices by section
            sections_data = {}
            for dev in self.devices_data:
                section = dev.get('section')
                if not section:
                    continue
                if section not in sections_data:
                    sections_data[section] = []
                sections_data[section].append(dev)
            
            if not sections_data:
                print("[PLOT] No section data for comparison")
                return
            
            sections = sorted(sections_data.keys())
            
            # Calculate metrics per section
            metrics = {
                'Memristivity_Score': [],
                'Memory_Window_Quality': [],
                'Switching_Ratio': [],
                'Memristive_Percentage': [],
                'Mean_Confidence': []
            }
            section_std = {
                'Memristivity_Score': [],
                'Memory_Window_Quality': [],
                'Switching_Ratio': []
            }
            
            for section in sections:
                devices = sections_data[section]
                scores = [d['classification'].get('memristivity_score', 0) or 0 for d in devices]
                qualities = [self._safe_get_quality_score(d) for d in devices]
                qualities = [q for q in qualities if not np.isnan(q)]
                ratios = [d['resistance'].get('switching_ratio', 1) or 1 for d in devices]
                ratios = [r for r in ratios if r > 0]
                confidences = [d['classification'].get('confidence', 0) or 0 for d in devices]
                memristive_count = sum(1 for d in devices if d['classification'].get('device_type') == 'memristive')
                
                metrics['Memristivity_Score'].append(np.mean(scores) if scores else 0)
                metrics['Memory_Window_Quality'].append(np.mean(qualities) if qualities else 0)
                metrics['Switching_Ratio'].append(np.mean(ratios) if ratios else 1)
                metrics['Memristive_Percentage'].append(100 * memristive_count / len(devices) if devices else 0)
                metrics['Mean_Confidence'].append(np.mean(confidences) if confidences else 0)
                
                section_std['Memristivity_Score'].append(np.std(scores) if len(scores) > 1 else 0)
                section_std['Memory_Window_Quality'].append(np.std(qualities) if len(qualities) > 1 else 0)
                section_std['Switching_Ratio'].append(np.std(ratios) if len(ratios) > 1 else 0)
            
            # Create subplots
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            fig.suptitle(f'Section Performance Comparison - {self.sample_name}', 
                        fontsize=16, fontweight='bold')
            
            x = np.arange(len(sections))
            width = 0.6
            
            # Plot 1: Memristivity Score
            ax1 = axes[0, 0]
            bars1 = ax1.bar(x, metrics['Memristivity_Score'], width, 
                           yerr=section_std['Memristivity_Score'], capsize=5,
                           color='#4CAF50', alpha=0.7, edgecolor='black')
            ax1.set_xlabel('Section', fontweight='bold')
            ax1.set_ylabel('Mean Memristivity Score', fontweight='bold')
            ax1.set_title('Memristivity Score by Section', fontweight='bold')
            ax1.set_xticks(x)
            ax1.set_xticklabels(sections)
            ax1.grid(axis='y', alpha=0.3)
            ax1.set_ylim(0, 100)
            
            # Plot 2: Memory Window Quality
            ax2 = axes[0, 1]
            bars2 = ax2.bar(x, metrics['Memory_Window_Quality'], width,
                           yerr=section_std['Memory_Window_Quality'], capsize=5,
                           color='#2196F3', alpha=0.7, edgecolor='black')
            ax2.set_xlabel('Section', fontweight='bold')
            ax2.set_ylabel('Mean Quality Score', fontweight='bold')
            ax2.set_title('Memory Window Quality by Section', fontweight='bold')
            ax2.set_xticks(x)
            ax2.set_xticklabels(sections)
            ax2.grid(axis='y', alpha=0.3)
            ax2.set_ylim(0, 100)
            
            # Plot 3: Memristive Percentage
            ax3 = axes[1, 0]
            bars3 = ax3.bar(x, metrics['Memristive_Percentage'], width,
                           color='#FF9800', alpha=0.7, edgecolor='black')
            ax3.set_xlabel('Section', fontweight='bold')
            ax3.set_ylabel('Memristive Devices (%)', fontweight='bold')
            ax3.set_title('Memristive Device Yield by Section', fontweight='bold')
            ax3.set_xticks(x)
            ax3.set_xticklabels(sections)
            ax3.grid(axis='y', alpha=0.3)
            ax3.set_ylim(0, 100)
            
            # Plot 4: Switching Ratio (log scale)
            ax4 = axes[1, 1]
            bars4 = ax4.bar(x, metrics['Switching_Ratio'], width,
                           yerr=section_std['Switching_Ratio'], capsize=5,
                           color='#9C27B0', alpha=0.7, edgecolor='black')
            ax4.set_xlabel('Section', fontweight='bold')
            ax4.set_ylabel('Mean Switching Ratio', fontweight='bold')
            ax4.set_title('Switching Ratio by Section', fontweight='bold')
            ax4.set_xticks(x)
            ax4.set_xticklabels(sections)
            ax4.set_yscale('log')
            ax4.grid(axis='y', alpha=0.3)
            
            plt.tight_layout()
            output_file = os.path.join(self.plots_dir, '15_section_performance_comparison.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"[PLOT] Saved: 15_section_performance_comparison.png")
            self._export_section_comparison_data(sections, metrics, section_std)
            
        except Exception as e:
            print(f"[PLOT ERROR] Section comparison failed: {e}")
            import traceback
            traceback.print_exc()
    
    def _export_section_comparison_data(self, sections=None, metrics=None, section_std=None) -> None:
        """Export section comparison data."""
        if sections is None:
            sections_data = {}
            for dev in self.devices_data:
                section = dev.get('section')
                if section:
                    if section not in sections_data:
                        sections_data[section] = []
                    sections_data[section].append(dev)
            sections = sorted(sections_data.keys())
            metrics = {'Memristivity_Score': [], 'Memory_Window_Quality': [], 
                      'Switching_Ratio': [], 'Memristive_Percentage': []}
            section_std = {'Memristivity_Score': [], 'Memory_Window_Quality': [], 'Switching_Ratio': []}
            for section in sections:
                devices = sections_data[section]
                scores = [d['classification'].get('memristivity_score', 0) or 0 for d in devices]
                qualities = [self._safe_get_quality_score(d) for d in devices]
                qualities = [q for q in qualities if not np.isnan(q)]
                ratios = [d['resistance'].get('switching_ratio', 1) or 1 for d in devices]
                memristive_count = sum(1 for d in devices if d['classification'].get('device_type') == 'memristive')
                metrics['Memristivity_Score'].append(np.mean(scores) if scores else 0)
                metrics['Memory_Window_Quality'].append(np.mean(qualities) if qualities else 0)
                metrics['Switching_Ratio'].append(np.mean(ratios) if ratios else 1)
                metrics['Memristive_Percentage'].append(100 * memristive_count / len(devices) if devices else 0)
                section_std['Memristivity_Score'].append(np.std(scores) if len(scores) > 1 else 0)
                section_std['Memory_Window_Quality'].append(np.std(qualities) if len(qualities) > 1 else 0)
                section_std['Switching_Ratio'].append(np.std(ratios) if len(ratios) > 1 else 0)
        
        rows = []
        for i, section in enumerate(sections):
            rows.append({
                'Section': section,
                'Mean_Memristivity_Score': metrics['Memristivity_Score'][i],
                'Std_Memristivity_Score': section_std['Memristivity_Score'][i],
                'Mean_Quality_Score': metrics['Memory_Window_Quality'][i],
                'Std_Quality_Score': section_std['Memory_Window_Quality'][i],
                'Mean_Switching_Ratio': metrics['Switching_Ratio'][i],
                'Std_Switching_Ratio': section_std['Switching_Ratio'][i],
                'Memristive_Percentage': metrics['Memristive_Percentage'][i]
            })
        
        df = pd.DataFrame(rows)
        output_file = os.path.join(self.data_origin_formatted_dir, 'section_comparison.csv')
        df.to_csv(output_file, index=False)
        print(f"[ORIGIN] Exported: section_comparison.csv")
    
    # === PLOT 16: Resistance Distribution Comparison ===
    def plot_resistance_distribution_comparison(self) -> None:
        """Compare Ron and Roff distributions across device types and sections."""
        try:
            # Extract resistance data
            ron_memristive = []
            roff_memristive = []
            ron_ohmic = []
            roff_ohmic = []
            ron_all = []
            roff_all = []
            
            for dev in self.devices_data:
                ron = dev['resistance'].get('ron_mean', np.nan)
                roff = dev['resistance'].get('roff_mean', np.nan)
                dtype = dev['classification'].get('device_type', 'unknown')
                
                if not np.isnan(ron) and not np.isnan(roff) and ron > 0 and roff > 0:
                    ron_all.append(ron)
                    roff_all.append(roff)
                    if dtype == 'memristive':
                        ron_memristive.append(ron)
                        roff_memristive.append(roff)
                    elif dtype == 'ohmic':
                        ron_ohmic.append(ron)
                        roff_ohmic.append(roff)
            
            if not ron_all:
                print("[PLOT] No resistance data for distribution comparison")
                return
            
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            fig.suptitle(f'Resistance Distribution Comparison - {self.sample_name}', 
                        fontsize=16, fontweight='bold')
            
            # Plot 1: Ron Distribution (all devices)
            ax1 = axes[0, 0]
            ax1.hist(np.log10(ron_all), bins=30, alpha=0.7, color='#2196F3', edgecolor='black')
            ax1.set_xlabel('log₁₀(Ron) [Ω]', fontweight='bold')
            ax1.set_ylabel('Device Count', fontweight='bold')
            ax1.set_title('Ron Distribution (All Devices)', fontweight='bold')
            ax1.axvline(np.log10(np.mean(ron_all)), color='red', linestyle='--', 
                       linewidth=2, label=f'Mean: {np.mean(ron_all):.2e} Ω')
            ax1.legend()
            ax1.grid(alpha=0.3)
            
            # Plot 2: Roff Distribution (all devices)
            ax2 = axes[0, 1]
            ax2.hist(np.log10(roff_all), bins=30, alpha=0.7, color='#FF9800', edgecolor='black')
            ax2.set_xlabel('log₁₀(Roff) [Ω]', fontweight='bold')
            ax2.set_ylabel('Device Count', fontweight='bold')
            ax2.set_title('Roff Distribution (All Devices)', fontweight='bold')
            ax2.axvline(np.log10(np.mean(roff_all)), color='red', linestyle='--', 
                       linewidth=2, label=f'Mean: {np.mean(roff_all):.2e} Ω')
            ax2.legend()
            ax2.grid(alpha=0.3)
            
            # Plot 3: Ron by Device Type (overlay)
            ax3 = axes[1, 0]
            if ron_memristive:
                ax3.hist(np.log10(ron_memristive), bins=20, alpha=0.6, color='green', 
                        label='Memristive', edgecolor='black')
            if ron_ohmic:
                ax3.hist(np.log10(ron_ohmic), bins=20, alpha=0.6, color='red', 
                        label='Ohmic', edgecolor='black')
            ax3.set_xlabel('log₁₀(Ron) [Ω]', fontweight='bold')
            ax3.set_ylabel('Device Count', fontweight='bold')
            ax3.set_title('Ron Distribution by Device Type', fontweight='bold')
            ax3.legend()
            ax3.grid(alpha=0.3)
            
            # Plot 4: Roff by Device Type (overlay)
            ax4 = axes[1, 1]
            if roff_memristive:
                ax4.hist(np.log10(roff_memristive), bins=20, alpha=0.6, color='green', 
                        label='Memristive', edgecolor='black')
            if roff_ohmic:
                ax4.hist(np.log10(roff_ohmic), bins=20, alpha=0.6, color='red', 
                        label='Ohmic', edgecolor='black')
            ax4.set_xlabel('log₁₀(Roff) [Ω]', fontweight='bold')
            ax4.set_ylabel('Device Count', fontweight='bold')
            ax4.set_title('Roff Distribution by Device Type', fontweight='bold')
            ax4.legend()
            ax4.grid(alpha=0.3)
            
            plt.tight_layout()
            output_file = os.path.join(self.plots_dir, '16_resistance_distribution_comparison.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"[PLOT] Saved: 16_resistance_distribution_comparison.png")
            self._export_resistance_distribution_data(ron_all, roff_all, ron_memristive, roff_memristive, ron_ohmic, roff_ohmic)
            
        except Exception as e:
            print(f"[PLOT ERROR] Resistance distribution failed: {e}")
            import traceback
            traceback.print_exc()
    
    def _export_resistance_distribution_data(self, ron_all=None, roff_all=None, 
                                            ron_mem=None, roff_mem=None, ron_ohm=None, roff_ohm=None) -> None:
        """Export resistance distribution data."""
        if ron_all is None:
            ron_all, roff_all, ron_mem, roff_mem, ron_ohm, roff_ohm = [], [], [], [], [], []
            for dev in self.devices_data:
                ron = dev['resistance'].get('ron_mean', np.nan)
                roff = dev['resistance'].get('roff_mean', np.nan)
                dtype = dev['classification'].get('device_type', 'unknown')
                if not np.isnan(ron) and not np.isnan(roff) and ron > 0 and roff > 0:
                    ron_all.append(ron)
                    roff_all.append(roff)
                    if dtype == 'memristive':
                        ron_mem.append(ron)
                        roff_mem.append(roff)
                    elif dtype == 'ohmic':
                        ron_ohm.append(ron)
                        roff_ohm.append(roff)
        
        data = {
            'All_Devices_Ron': ron_all + [np.nan] * max(0, len(roff_all) - len(ron_all)),
            'All_Devices_Roff': roff_all + [np.nan] * max(0, len(ron_all) - len(roff_all)),
            'Memristive_Ron': ron_mem + [np.nan] * max(0, max(len(roff_mem), len(ron_all)) - len(ron_mem)),
            'Memristive_Roff': roff_mem + [np.nan] * max(0, max(len(ron_mem), len(ron_all)) - len(roff_mem)),
        }
        max_len = max(len(v) for v in data.values())
        data = {k: v + [np.nan] * (max_len - len(v)) for k, v in data.items()}
        
        df = pd.DataFrame(data)
        output_file = os.path.join(self.data_origin_formatted_dir, 'resistance_distribution.csv')
        df.to_csv(output_file, index=False)
        print(f"[ORIGIN] Exported: resistance_distribution.csv")
    
    # === PLOT 17: Yield and Performance Dashboard ===
    def plot_yield_dashboard(self) -> None:
        """Single-page dashboard with key statistics and yield metrics."""
        try:
            total_devices = len(self.devices_data)
            memristive_count = len(self.memristive_devices)
            yield_percentage = 100 * memristive_count / total_devices if total_devices > 0 else 0
            
            # Calculate overall statistics
            scores = [d['classification'].get('memristivity_score', 0) or 0 for d in self.devices_data]
            avg_score = np.mean(scores) if scores else 0
            
            # Yield by section
            sections_data = {}
            for dev in self.devices_data:
                section = dev.get('section')
                if section:
                    if section not in sections_data:
                        sections_data[section] = {'total': 0, 'memristive': 0}
                    sections_data[section]['total'] += 1
                    if dev['classification'].get('device_type') == 'memristive':
                        sections_data[section]['memristive'] += 1
            
            sections = sorted(sections_data.keys())
            section_yields = [100 * sections_data[s]['memristive'] / sections_data[s]['total'] 
                            if sections_data[s]['total'] > 0 else 0 for s in sections]
            
            # Yield by size
            size_data = {}
            for dev in self.devices_data:
                size = dev.get('device_size')
                if size:
                    if size not in size_data:
                        size_data[size] = {'total': 0, 'memristive': 0}
                    size_data[size]['total'] += 1
                    if dev['classification'].get('device_type') == 'memristive':
                        size_data[size]['memristive'] += 1
            
            sizes = sorted(size_data.keys())
            size_yields = [100 * size_data[s]['memristive'] / size_data[s]['total'] 
                          if size_data[s]['total'] > 0 else 0 for s in sizes]
            
            # Device type breakdown
            type_counts = {}
            for dev in self.devices_data:
                dtype = dev['classification'].get('device_type', 'unknown')
                type_counts[dtype] = type_counts.get(dtype, 0) + 1
            
            # Create dashboard layout
            fig = plt.figure(figsize=(18, 12))
            gs = fig.add_gridspec(3, 4, hspace=0.3, wspace=0.3)
            fig.suptitle(f'Yield and Performance Dashboard - {self.sample_name}', 
                        fontsize=18, fontweight='bold', y=0.98)
            
            # Overall stats (text)
            ax1 = fig.add_subplot(gs[0, 0])
            ax1.axis('off')
            stats_text = f"""
            Total Devices: {total_devices}
            Memristive Devices: {memristive_count}
            Overall Yield: {yield_percentage:.1f}%
            Avg Memristivity Score: {avg_score:.1f}/100
            """
            ax1.text(0.1, 0.5, stats_text, fontsize=14, fontweight='bold',
                    verticalalignment='center', family='monospace')
            
            # Yield by section
            ax2 = fig.add_subplot(gs[0, 1:3])
            if sections:
                bars = ax2.bar(sections, section_yields, color='#4CAF50', alpha=0.7, edgecolor='black')
                ax2.set_ylabel('Yield (%)', fontweight='bold')
                ax2.set_title('Yield by Section', fontweight='bold')
                ax2.set_ylim(0, 100)
                ax2.grid(axis='y', alpha=0.3)
                for i, (bar, yld) in enumerate(zip(bars, section_yields)):
                    ax2.text(bar.get_x() + bar.get_width()/2, yld + 2, 
                            f'{yld:.1f}%', ha='center', fontweight='bold')
            
            # Device type pie chart
            ax3 = fig.add_subplot(gs[0, 3])
            if type_counts:
                labels = list(type_counts.keys())
                sizes_pie = list(type_counts.values())
                colors = plt.cm.Set3(np.linspace(0, 1, len(labels)))
                ax3.pie(sizes_pie, labels=labels, autopct='%1.1f%%', colors=colors, startangle=90)
                ax3.set_title('Device Type\nDistribution', fontweight='bold')
            
            # Score distribution
            ax4 = fig.add_subplot(gs[1, :2])
            if scores:
                ax4.hist(scores, bins=30, color='#2196F3', alpha=0.7, edgecolor='black')
                ax4.axvline(avg_score, color='red', linestyle='--', linewidth=2, 
                           label=f'Mean: {avg_score:.1f}')
                ax4.set_xlabel('Memristivity Score', fontweight='bold')
                ax4.set_ylabel('Device Count', fontweight='bold')
                ax4.set_title('Score Distribution', fontweight='bold')
                ax4.legend()
                ax4.grid(alpha=0.3)
            
            # Yield by size
            ax5 = fig.add_subplot(gs[1, 2:])
            if sizes:
                bars = ax5.bar(sizes, size_yields, color='#FF9800', alpha=0.7, edgecolor='black')
                ax5.set_ylabel('Yield (%)', fontweight='bold')
                ax5.set_title('Yield by Device Size', fontweight='bold')
                ax5.set_ylim(0, 100)
                ax5.grid(axis='y', alpha=0.3)
                for i, (bar, yld) in enumerate(zip(bars, size_yields)):
                    ax5.text(bar.get_x() + bar.get_width()/2, yld + 2, 
                            f'{yld:.1f}%', ha='center', fontweight='bold')
            
            # Top sections by average score
            ax6 = fig.add_subplot(gs[2, :2])
            if sections_data:
                section_avg_scores = {}
                for section in sections:
                    devices = [d for d in self.devices_data if d.get('section') == section]
                    section_scores = [d['classification'].get('memristivity_score', 0) or 0 for d in devices]
                    if section_scores:
                        section_avg_scores[section] = np.mean(section_scores)
                
                sorted_sections = sorted(section_avg_scores.items(), key=lambda x: x[1], reverse=True)[:5]
                if sorted_sections:
                    secs, scr = zip(*sorted_sections)
                    bars = ax6.barh(secs, scr, color='#9C27B0', alpha=0.7, edgecolor='black')
                    ax6.set_xlabel('Average Memristivity Score', fontweight='bold')
                    ax6.set_title('Top 5 Sections by Average Score', fontweight='bold')
                    ax6.set_xlim(0, 100)
                    ax6.grid(axis='x', alpha=0.3)
                    for i, (bar, score) in enumerate(zip(bars, scr)):
                        ax6.text(score + 1, i, f'{score:.1f}', va='center', fontweight='bold')
            
            # Quality vs Score scatter
            ax7 = fig.add_subplot(gs[2, 2:])
            scores_scatter = []
            qualities_scatter = []
            for dev in self.devices_data:
                score = dev['classification'].get('memristivity_score', 0) or 0
                quality = self._safe_get_quality_score(dev)
                if not np.isnan(quality):
                    scores_scatter.append(score)
                    qualities_scatter.append(quality)
            if scores_scatter:
                ax7.scatter(scores_scatter, qualities_scatter, alpha=0.6, s=50, edgecolors='black', linewidth=0.5)
                ax7.set_xlabel('Memristivity Score', fontweight='bold')
                ax7.set_ylabel('Quality Score', fontweight='bold')
                ax7.set_title('Score vs Quality', fontweight='bold')
                ax7.grid(alpha=0.3)
                ax7.set_xlim(0, 100)
                ax7.set_ylim(0, 100)
            
            plt.tight_layout()
            output_file = os.path.join(self.plots_dir, '17_yield_dashboard.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"[PLOT] Saved: 17_yield_dashboard.png")
            
        except Exception as e:
            print(f"[PLOT ERROR] Yield dashboard failed: {e}")
            import traceback
            traceback.print_exc()
    
    # === PLOT 18: Device Type vs Size Matrix ===
    def plot_device_type_size_matrix(self) -> None:
        """Show distribution of device types across different sizes."""
        try:
            # Group devices by size and type
            size_type_data = {}
            for dev in self.devices_data:
                size = dev.get('device_size')
                dtype = dev['classification'].get('device_type', 'unknown')
                if size:
                    if size not in size_type_data:
                        size_type_data[size] = {}
                    size_type_data[size][dtype] = size_type_data[size].get(dtype, 0) + 1
            
            if not size_type_data:
                print("[PLOT] No device size data for type vs size matrix")
                return
            
            sizes = sorted(size_type_data.keys())
            all_types = sorted(set(t for sizes_dict in size_type_data.values() for t in sizes_dict.keys()))
            
            # Create data matrix
            matrix = np.zeros((len(sizes), len(all_types)))
            for i, size in enumerate(sizes):
                total = sum(size_type_data[size].values())
                for j, dtype in enumerate(all_types):
                    count = size_type_data[size].get(dtype, 0)
                    matrix[i, j] = 100 * count / total if total > 0 else 0
            
            # Create plot
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
            fig.suptitle(f'Device Type vs Size Matrix - {self.sample_name}', 
                        fontsize=16, fontweight='bold')
            
            # Heatmap
            im = ax1.imshow(matrix, cmap='YlOrRd', aspect='auto', vmin=0, vmax=100)
            ax1.set_xticks(range(len(all_types)))
            ax1.set_yticks(range(len(sizes)))
            ax1.set_xticklabels([t.replace('_', ' ').title() for t in all_types], rotation=45, ha='right')
            ax1.set_yticklabels(sizes)
            ax1.set_xlabel('Device Type', fontweight='bold')
            ax1.set_ylabel('Device Size', fontweight='bold')
            ax1.set_title('Device Type Distribution (%)', fontweight='bold')
            
            # Add percentage text
            for i in range(len(sizes)):
                for j in range(len(all_types)):
                    value = matrix[i, j]
                    if value > 0:
                        text_color = 'white' if value > 50 else 'black'
                        ax1.text(j, i, f'{value:.0f}%', ha='center', va='center',
                               color=text_color, fontsize=10, fontweight='bold')
            
            cbar1 = plt.colorbar(im, ax=ax1)
            cbar1.set_label('Percentage (%)', fontsize=11)
            
            # Stacked bar chart
            x = np.arange(len(sizes))
            width = 0.6
            bottom = np.zeros(len(sizes))
            
            colors_dict = {'memristive': '#4CAF50', 'ohmic': '#9E9E9E', 'capacitive': '#2196F3',
                          'conductive': '#FF9800', 'memcapacitive': '#9C27B0', 'unknown': '#F44336'}
            colors_list = [colors_dict.get(t, '#757575') for t in all_types]
            
            for j, dtype in enumerate(all_types):
                values = [100 * size_type_data[size].get(dtype, 0) / sum(size_type_data[size].values())
                         if sum(size_type_data[size].values()) > 0 else 0 for size in sizes]
                ax2.bar(x, values, width, label=dtype.replace('_', ' ').title(),
                       bottom=bottom, color=colors_list[j], alpha=0.8, edgecolor='black')
                bottom += values
            
            ax2.set_xlabel('Device Size', fontweight='bold')
            ax2.set_ylabel('Percentage (%)', fontweight='bold')
            ax2.set_title('Device Type Distribution (Stacked)', fontweight='bold')
            ax2.set_xticks(x)
            ax2.set_xticklabels(sizes)
            ax2.set_ylim(0, 100)
            ax2.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
            ax2.grid(axis='y', alpha=0.3)
            
            plt.tight_layout()
            output_file = os.path.join(self.plots_dir, '18_device_type_size_matrix.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"[PLOT] Saved: 18_device_type_size_matrix.png")
            self._export_type_size_matrix_data(size_type_data, sizes, all_types)
            
        except Exception as e:
            print(f"[PLOT ERROR] Device type vs size matrix failed: {e}")
            import traceback
            traceback.print_exc()
    
    def _export_type_size_matrix_data(self, size_type_data=None, sizes=None, all_types=None) -> None:
        """Export device type vs size matrix data."""
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
            all_types = sorted(set(t for sizes_dict in size_type_data.values() for t in sizes_dict.keys()))
        
        rows = []
        for size in sizes:
            total = sum(size_type_data[size].values())
            row = {'Device_Size': size, 'Total_Devices': total}
            for dtype in all_types:
                count = size_type_data[size].get(dtype, 0)
                row[f'{dtype}_Count'] = count
                row[f'{dtype}_Percentage'] = 100 * count / total if total > 0 else 0
            rows.append(row)
        
        df = pd.DataFrame(rows)
        output_file = os.path.join(self.data_origin_formatted_dir, 'device_type_size_matrix.csv')
        df.to_csv(output_file, index=False)
        print(f"[ORIGIN] Exported: device_type_size_matrix.csv")
    
    # === PLOT 19: Quality Score Breakdown ===
    def plot_quality_score_breakdown(self) -> None:
        """Detailed breakdown of quality components."""
        try:
            # Extract quality components
            ron_stability = []
            roff_stability = []
            separation_ratio = []
            overall_quality = []
            device_ids = []
            sections = []
            
            for dev in self.devices_data:
                quality = dev.get('quality', {})
                if not isinstance(quality, dict):
                    continue
                mw_quality = quality.get('memory_window_quality', {})
                if isinstance(mw_quality, dict):
                    ron_stab = mw_quality.get('ron_stability', np.nan)
                    roff_stab = mw_quality.get('roff_stability', np.nan)
                    sep_ratio = mw_quality.get('separation_ratio', np.nan)
                    overall = mw_quality.get('overall_quality_score', np.nan)
                    
                    if not np.isnan(overall):
                        ron_stability.append(ron_stab if not np.isnan(ron_stab) else 0)
                        roff_stability.append(roff_stab if not np.isnan(roff_stab) else 0)
                        separation_ratio.append(sep_ratio if not np.isnan(sep_ratio) else 1)
                        overall_quality.append(overall)
                        device_ids.append(dev['device_id'])
                        sections.append(dev.get('section', 'Unknown'))
            
            if not overall_quality:
                print("[PLOT] No quality data for breakdown")
                return
            
            # Group by section if available
            sections_data = {}
            if any(s != 'Unknown' for s in sections):
                for i, section in enumerate(sections):
                    if section not in sections_data:
                        sections_data[section] = {'ron': [], 'roff': [], 'sep': [], 'overall': []}
                    sections_data[section]['ron'].append(ron_stability[i])
                    sections_data[section]['roff'].append(roff_stability[i])
                    sections_data[section]['sep'].append(separation_ratio[i])
                    sections_data[section]['overall'].append(overall_quality[i])
            
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            fig.suptitle(f'Quality Score Breakdown - {self.sample_name}', 
                        fontsize=16, fontweight='bold')
            
            # Plot 1: Component comparison (all devices)
            ax1 = axes[0, 0]
            components = ['Ron\nStability', 'Roff\nStability', 'Overall\nQuality']
            means = [np.mean(ron_stability), np.mean(roff_stability), np.mean(overall_quality)]
            stds = [np.std(ron_stability), np.std(roff_stability), np.std(overall_quality)]
            
            bars = ax1.bar(components, means, yerr=stds, capsize=5, 
                          color=['#FF6B6B', '#4ECDC4', '#95E1D3'], alpha=0.7, edgecolor='black')
            ax1.set_ylabel('Score', fontweight='bold')
            ax1.set_title('Average Quality Components', fontweight='bold')
            ax1.set_ylim(0, 100)
            ax1.grid(axis='y', alpha=0.3)
            for bar, mean, std in zip(bars, means, stds):
                ax1.text(bar.get_x() + bar.get_width()/2, mean + std + 2, 
                        f'{mean:.1f}', ha='center', fontweight='bold')
            
            # Plot 2: Separation Ratio Distribution
            ax2 = axes[0, 1]
            valid_ratios = [r for r in separation_ratio if r > 0]
            if valid_ratios:
                ax2.hist(np.log10(valid_ratios), bins=30, color='#FFA07A', alpha=0.7, edgecolor='black')
                ax2.axvline(np.log10(np.mean(valid_ratios)), color='red', linestyle='--', 
                           linewidth=2, label=f'Mean: {np.mean(valid_ratios):.2e}')
                ax2.set_xlabel('log₁₀(Separation Ratio)', fontweight='bold')
                ax2.set_ylabel('Device Count', fontweight='bold')
                ax2.set_title('Separation Ratio Distribution', fontweight='bold')
                ax2.legend()
                ax2.grid(alpha=0.3)
            
            # Plot 3: Quality by Section (if available)
            ax3 = axes[1, 0]
            if sections_data:
                section_names = sorted(sections_data.keys())
                section_means = [np.mean(sections_data[s]['overall']) for s in section_names]
                section_stds = [np.std(sections_data[s]['overall']) for s in section_names]
                
                x = np.arange(len(section_names))
                bars = ax3.bar(x, section_means, yerr=section_stds, capsize=5,
                              color='#9C27B0', alpha=0.7, edgecolor='black')
                ax3.set_xlabel('Section', fontweight='bold')
                ax3.set_ylabel('Mean Overall Quality Score', fontweight='bold')
                ax3.set_title('Quality Score by Section', fontweight='bold')
                ax3.set_xticks(x)
                ax3.set_xticklabels(section_names)
                ax3.set_ylim(0, 100)
                ax3.grid(axis='y', alpha=0.3)
            else:
                ax3.text(0.5, 0.5, 'No section data available', 
                        ha='center', va='center', transform=ax3.transAxes)
                ax3.set_title('Quality Score by Section', fontweight='bold')
            
            # Plot 4: Ron vs Roff Stability Scatter
            ax4 = axes[1, 1]
            scatter = ax4.scatter(ron_stability, roff_stability, c=overall_quality,
                                cmap='RdYlGn', vmin=0, vmax=100, s=100, alpha=0.6,
                                edgecolors='black', linewidth=0.5)
            ax4.set_xlabel('Ron Stability', fontweight='bold')
            ax4.set_ylabel('Roff Stability', fontweight='bold')
            ax4.set_title('Ron vs Roff Stability', fontweight='bold')
            ax4.set_xlim(0, 100)
            ax4.set_ylim(0, 100)
            ax4.grid(alpha=0.3)
            cbar = plt.colorbar(scatter, ax=ax4)
            cbar.set_label('Overall Quality Score', fontsize=11)
            
            plt.tight_layout()
            output_file = os.path.join(self.plots_dir, '19_quality_score_breakdown.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"[PLOT] Saved: 19_quality_score_breakdown.png")
            self._export_quality_breakdown_data(ron_stability, roff_stability, separation_ratio, overall_quality, sections)
            
        except Exception as e:
            print(f"[PLOT ERROR] Quality breakdown failed: {e}")
            import traceback
            traceback.print_exc()
    
    def _export_quality_breakdown_data(self, ron_stab=None, roff_stab=None, sep_ratio=None, 
                                       overall=None, sections=None) -> None:
        """Export quality breakdown data."""
        if ron_stab is None:
            ron_stab, roff_stab, sep_ratio, overall, sections = [], [], [], [], []
            for dev in self.devices_data:
                quality = dev.get('quality', {})
                if isinstance(quality, dict):
                    mw_quality = quality.get('memory_window_quality', {})
                    if isinstance(mw_quality, dict):
                        overall_val = mw_quality.get('overall_quality_score', np.nan)
                        if not np.isnan(overall_val):
                            ron_stab.append(mw_quality.get('ron_stability', 0))
                            roff_stab.append(mw_quality.get('roff_stability', 0))
                            sep_ratio.append(mw_quality.get('separation_ratio', 1))
                            overall.append(overall_val)
                            sections.append(dev.get('section', 'Unknown'))
        
        df = pd.DataFrame({
            'Ron_Stability': ron_stab,
            'Roff_Stability': roff_stab,
            'Separation_Ratio': sep_ratio,
            'Overall_Quality_Score': overall,
            'Section': sections
        })
        output_file = os.path.join(self.data_origin_formatted_dir, 'quality_breakdown.csv')
        df.to_csv(output_file, index=False)
        print(f"[ORIGIN] Exported: quality_breakdown.csv")
    
    # === PLOT 20: Confidence vs Performance Scatter ===
    def plot_confidence_performance_scatter(self) -> None:
        """Examine relationship between classification confidence and device performance."""
        try:
            confidences = []
            scores = []
            device_types = []
            switching_ratios = []
            
            for dev in self.devices_data:
                confidence = dev['classification'].get('confidence', np.nan)
                score = dev['classification'].get('memristivity_score', 0) or 0
                dtype = dev['classification'].get('device_type', 'unknown')
                ratio = dev['resistance'].get('switching_ratio', 1) or 1
                
                if not np.isnan(confidence):
                    confidences.append(confidence * 100)  # Convert to percentage
                    scores.append(score)
                    device_types.append(dtype)
                    switching_ratios.append(ratio)
            
            if not confidences:
                print("[PLOT] No confidence data for scatter plot")
                return
            
            fig, axes = plt.subplots(1, 2, figsize=(16, 8))
            fig.suptitle(f'Confidence vs Performance - {self.sample_name}', 
                        fontsize=16, fontweight='bold')
            
            # Plot 1: All devices with color by type
            ax1 = axes[0]
            type_colors = {'memristive': 'green', 'ohmic': 'red', 'capacitive': 'blue', 
                          'unknown': 'gray', 'conductive': 'orange'}
            
            for dtype in set(device_types):
                mask = [dt == dtype for dt in device_types]
                conf_subset = [c for c, m in zip(confidences, mask) if m]
                score_subset = [s for s, m in zip(scores, mask) if m]
                ratio_subset = [r for r, m in zip(switching_ratios, mask) if m]
                sizes = [min(200, max(20, np.log10(r) * 20)) if r > 1 else 20 for r in ratio_subset]
                
                ax1.scatter(conf_subset, score_subset, c=type_colors.get(dtype, 'gray'),
                           s=sizes, alpha=0.6, edgecolors='black', linewidth=0.5,
                           label=dtype.replace('_', ' ').title())
            
            # Add regression line (only if there's variation in x values)
            if len(confidences) > 1 and np.std(confidences) > 1e-10:
                with warnings.catch_warnings():
                    # Ignore rank warnings from polyfit (RankWarning removed in newer numpy)
                    warnings.simplefilter("ignore", RuntimeWarning)
                    warnings.simplefilter("ignore", UserWarning)
                    try:
                        z = np.polyfit(confidences, scores, 1)
                        p = np.poly1d(z)
                        x_line = np.linspace(min(confidences), max(confidences), 100)
                        ax1.plot(x_line, p(x_line), "r--", alpha=0.5, linewidth=2, label='Linear Fit')
                    except (np.linalg.LinAlgError, ValueError):
                        pass  # Skip regression if poorly conditioned
            
            # Highlight high confidence + high score region
            ax1.axhspan(70, 100, alpha=0.1, color='green', label='High Performance Zone')
            ax1.axvspan(70, 100, alpha=0.1, color='green')
            
            ax1.set_xlabel('Classification Confidence (%)', fontweight='bold')
            ax1.set_ylabel('Memristivity Score', fontweight='bold')
            ax1.set_title('Confidence vs Performance (All Devices)', fontweight='bold')
            ax1.set_xlim(0, 100)
            ax1.set_ylim(0, 100)
            ax1.grid(alpha=0.3)
            ax1.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
            
            # Plot 2: Memristive devices only
            ax2 = axes[1]
            memristive_conf = [c for c, dt in zip(confidences, device_types) if dt == 'memristive']
            memristive_scores = [s for s, dt in zip(scores, device_types) if dt == 'memristive']
            memristive_ratios = [r for r, dt in zip(switching_ratios, device_types) if dt == 'memristive']
            
            if memristive_conf:
                sizes = [min(200, max(20, np.log10(r) * 20)) if r > 1 else 20 for r in memristive_ratios]
                scatter = ax2.scatter(memristive_conf, memristive_scores, c=memristive_scores,
                                    cmap='RdYlGn', vmin=0, vmax=100, s=sizes, alpha=0.7,
                                    edgecolors='black', linewidth=0.5)
                
                # Regression line for memristive (only if there's variation)
                if len(memristive_conf) > 1 and np.std(memristive_conf) > 1e-10:
                    with warnings.catch_warnings():
                        # Ignore rank warnings from polyfit (RankWarning removed in newer numpy)
                        warnings.simplefilter("ignore", RuntimeWarning)
                        warnings.simplefilter("ignore", UserWarning)
                        try:
                            z = np.polyfit(memristive_conf, memristive_scores, 1)
                            p = np.poly1d(z)
                            x_line = np.linspace(min(memristive_conf), max(memristive_conf), 100)
                            ax2.plot(x_line, p(x_line), "b--", alpha=0.7, linewidth=2, label='Linear Fit')
                        except (np.linalg.LinAlgError, ValueError):
                            pass  # Skip regression if poorly conditioned
                
                ax2.set_xlabel('Classification Confidence (%)', fontweight='bold')
                ax2.set_ylabel('Memristivity Score', fontweight='bold')
                ax2.set_title(f'Confidence vs Performance (Memristive, n={len(memristive_conf)})', 
                            fontweight='bold')
                ax2.set_xlim(0, 100)
                ax2.set_ylim(0, 100)
                ax2.grid(alpha=0.3)
                ax2.legend()
                cbar = plt.colorbar(scatter, ax=ax2)
                cbar.set_label('Memristivity Score', fontsize=11)
            else:
                ax2.text(0.5, 0.5, 'No memristive devices', 
                        ha='center', va='center', transform=ax2.transAxes, fontsize=14)
                ax2.set_title('Confidence vs Performance (Memristive)', fontweight='bold')
            
            plt.tight_layout()
            output_file = os.path.join(self.plots_dir, '20_confidence_performance_scatter.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"[PLOT] Saved: 20_confidence_performance_scatter.png")
            self._export_confidence_performance_data(confidences, scores, device_types, switching_ratios)
            
        except Exception as e:
            print(f"[PLOT ERROR] Confidence vs performance scatter failed: {e}")
            import traceback
            traceback.print_exc()
    
    def _export_confidence_performance_data(self, confidences=None, scores=None, 
                                           types=None, ratios=None) -> None:
        """Export confidence vs performance data."""
        if confidences is None:
            confidences, scores, types, ratios = [], [], [], []
            for dev in self.devices_data:
                confidence = dev['classification'].get('confidence', np.nan)
                if not np.isnan(confidence):
                    confidences.append(confidence * 100)
                    scores.append(dev['classification'].get('memristivity_score', 0) or 0)
                    types.append(dev['classification'].get('device_type', 'unknown'))
                    ratios.append(dev['resistance'].get('switching_ratio', 1) or 1)
        
        df = pd.DataFrame({
            'Confidence_Percentage': confidences,
            'Memristivity_Score': scores,
            'Device_Type': types,
            'Switching_Ratio': ratios
        })
        output_file = os.path.join(self.data_origin_formatted_dir, 'confidence_performance.csv')
        df.to_csv(output_file, index=False)
        print(f"[ORIGIN] Exported: confidence_performance.csv")
    
    # === PLOT 21: Voltage Range Analysis ===
    def plot_voltage_range_analysis(self) -> None:
        """Analyze test voltage ranges and their relationship to performance."""
        try:
            max_voltages = []
            scores = []
            device_types = []
            sections = []
            
            for dev in self.devices_data:
                voltage_data = dev.get('voltage', {})
                max_v = voltage_data.get('max_voltage', np.nan)
                if not np.isnan(max_v) and max_v > 0:
                    max_voltages.append(abs(max_v))
                    scores.append(dev['classification'].get('memristivity_score', 0) or 0)
                    device_types.append(dev['classification'].get('device_type', 'unknown'))
                    sections.append(dev.get('section', 'Unknown'))
            
            if not max_voltages:
                print("[PLOT] No voltage data for voltage range analysis")
                return
            
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            fig.suptitle(f'Voltage Range Analysis - {self.sample_name}', 
                        fontsize=16, fontweight='bold')
            
            # Plot 1: Voltage Distribution
            ax1 = axes[0, 0]
            ax1.hist(max_voltages, bins=30, color='#2196F3', alpha=0.7, edgecolor='black')
            ax1.axvline(np.mean(max_voltages), color='red', linestyle='--', 
                       linewidth=2, label=f'Mean: {np.mean(max_voltages):.2f} V')
            ax1.set_xlabel('Max Voltage (V)', fontweight='bold')
            ax1.set_ylabel('Device Count', fontweight='bold')
            ax1.set_title('Voltage Distribution', fontweight='bold')
            ax1.legend()
            ax1.grid(alpha=0.3)
            
            # Plot 2: Voltage vs Score Scatter
            ax2 = axes[0, 1]
            type_colors = {'memristive': 'green', 'ohmic': 'red', 'capacitive': 'blue', 
                          'unknown': 'gray'}
            for dtype in set(device_types):
                mask = [dt == dtype for dt in device_types]
                v_subset = [v for v, m in zip(max_voltages, mask) if m]
                s_subset = [s for s, m in zip(scores, mask) if m]
                ax2.scatter(v_subset, s_subset, c=type_colors.get(dtype, 'gray'),
                           alpha=0.6, s=50, edgecolors='black', linewidth=0.5,
                           label=dtype.replace('_', ' ').title())
            ax2.set_xlabel('Max Voltage (V)', fontweight='bold')
            ax2.set_ylabel('Memristivity Score', fontweight='bold')
            ax2.set_title('Voltage vs Performance', fontweight='bold')
            ax2.grid(alpha=0.3)
            ax2.legend()
            
            # Plot 3: Voltage by Section (box plot)
            ax3 = axes[1, 0]
            if any(s != 'Unknown' for s in sections):
                section_voltages = {}
                for v, s in zip(max_voltages, sections):
                    if s != 'Unknown':
                        if s not in section_voltages:
                            section_voltages[s] = []
                        section_voltages[s].append(v)
                
                if section_voltages:
                    section_names = sorted(section_voltages.keys())
                    voltage_lists = [section_voltages[s] for s in section_names]
                    bp = ax3.boxplot(voltage_lists, labels=section_names, patch_artist=True)
                    for patch in bp['boxes']:
                        patch.set_facecolor('#FF9800')
                        patch.set_alpha(0.7)
                    ax3.set_xlabel('Section', fontweight='bold')
                    ax3.set_ylabel('Max Voltage (V)', fontweight='bold')
                    ax3.set_title('Voltage Range by Section', fontweight='bold')
                    ax3.grid(axis='y', alpha=0.3)
            else:
                ax3.text(0.5, 0.5, 'No section data available', 
                        ha='center', va='center', transform=ax3.transAxes)
                ax3.set_title('Voltage Range by Section', fontweight='bold')
            
            # Plot 4: Voltage bins performance
            ax4 = axes[1, 1]
            voltage_bins = [0, 0.5, 1.0, 1.5, 2.0, 5.0, 10.0]
            bin_labels = [f'{voltage_bins[i]:.1f}-{voltage_bins[i+1]:.1f}V' 
                         for i in range(len(voltage_bins)-1)]
            bin_means = []
            bin_counts = []
            
            for i in range(len(voltage_bins)-1):
                mask = [(v >= voltage_bins[i]) & (v < voltage_bins[i+1]) for v in max_voltages]
                bin_scores = [s for s, m in zip(scores, mask) if m]
                if bin_scores:
                    bin_means.append(np.mean(bin_scores))
                    bin_counts.append(len(bin_scores))
                else:
                    bin_means.append(0)
                    bin_counts.append(0)
            
            bars = ax4.bar(range(len(bin_labels)), bin_means, color='#4CAF50', 
                          alpha=0.7, edgecolor='black')
            ax4.set_xlabel('Voltage Range', fontweight='bold')
            ax4.set_ylabel('Mean Memristivity Score', fontweight='bold')
            ax4.set_title('Performance by Voltage Range', fontweight='bold')
            ax4.set_xticks(range(len(bin_labels)))
            ax4.set_xticklabels(bin_labels, rotation=45, ha='right')
            ax4.set_ylim(0, 100)
            ax4.grid(axis='y', alpha=0.3)
            for i, (bar, count) in enumerate(zip(bars, bin_counts)):
                if count > 0:
                    ax4.text(bar.get_x() + bar.get_width()/2, bin_means[i] + 2,
                            f'n={count}', ha='center', fontsize=9)
            
            plt.tight_layout()
            output_file = os.path.join(self.plots_dir, '21_voltage_range_analysis.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"[PLOT] Saved: 21_voltage_range_analysis.png")
            self._export_voltage_range_data(max_voltages, scores, device_types, sections)
            
        except Exception as e:
            print(f"[PLOT ERROR] Voltage range analysis failed: {e}")
            import traceback
            traceback.print_exc()
    
    def _export_voltage_range_data(self, max_voltages=None, scores=None, types=None, sections=None) -> None:
        """Export voltage range analysis data."""
        if max_voltages is None:
            max_voltages, scores, types, sections = [], [], [], []
            for dev in self.devices_data:
                max_v = dev.get('voltage', {}).get('max_voltage', np.nan)
                if not np.isnan(max_v) and max_v > 0:
                    max_voltages.append(abs(max_v))
                    scores.append(dev['classification'].get('memristivity_score', 0) or 0)
                    types.append(dev['classification'].get('device_type', 'unknown'))
                    sections.append(dev.get('section', 'Unknown'))
        
        df = pd.DataFrame({
            'Max_Voltage_V': max_voltages,
            'Memristivity_Score': scores,
            'Device_Type': types,
            'Section': sections
        })
        output_file = os.path.join(self.data_origin_formatted_dir, 'voltage_range_analysis.csv')
        df.to_csv(output_file, index=False)
        print(f"[ORIGIN] Exported: voltage_range_analysis.csv")
    
    # === PLOT 22: Performance Stability Analysis ===
    def plot_performance_stability_analysis(self) -> None:
        """Analyze stability of device performance over multiple measurements."""
        try:
            devices_with_multiple = []
            for dev in self.devices_data:
                measurements = dev.get('all_measurements', [])
                if len(measurements) >= 3:  # Need at least 3 measurements
                    scores = [m.get('classification', {}).get('memristivity_score', 0) or 0 
                             for m in measurements]
                    rons = [m.get('resistance', {}).get('ron_mean', np.nan) 
                           for m in measurements]
                    roffs = [m.get('resistance', {}).get('roff_mean', np.nan) 
                            for m in measurements]
                    # Filter out None, NaN, and non-positive values safely
                    def is_valid_positive(value):
                        try:
                            if value is None:
                                return False
                            val = float(value)
                            return not np.isnan(val) and val > 0
                        except (ValueError, TypeError):
                            return False
                    
                    rons = [r for r in rons if is_valid_positive(r)]
                    roffs = [r for r in roffs if is_valid_positive(r)]
                    
                    if len(scores) >= 3 and len(rons) >= 2 and len(roffs) >= 2:
                        # Calculate coefficient of variation (CV)
                        score_cv = np.std(scores) / np.mean(scores) if np.mean(scores) > 0 else 0
                        ron_cv = np.std(rons) / np.mean(rons) if np.mean(rons) > 0 else 0
                        roff_cv = np.std(roffs) / np.mean(roffs) if np.mean(roffs) > 0 else 0
                        
                        devices_with_multiple.append({
                            'device_id': dev['device_id'],
                            'avg_score': np.mean(scores),
                            'score_cv': score_cv,
                            'ron_cv': ron_cv,
                            'roff_cv': roff_cv,
                            'num_measurements': len(measurements),
                            'device_type': dev['classification'].get('device_type', 'unknown')
                        })
            
            if not devices_with_multiple:
                print("[PLOT] No devices with multiple measurements for stability analysis")
                return
            
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            fig.suptitle(f'Performance Stability Analysis - {self.sample_name}', 
                        fontsize=16, fontweight='bold')
            
            score_cvs = [d['score_cv'] for d in devices_with_multiple]
            avg_scores = [d['avg_score'] for d in devices_with_multiple]
            
            # Plot 1: Score CV Distribution
            ax1 = axes[0, 0]
            ax1.hist(score_cvs, bins=30, color='#2196F3', alpha=0.7, edgecolor='black')
            ax1.axvline(np.mean(score_cvs), color='red', linestyle='--', 
                       linewidth=2, label=f'Mean CV: {np.mean(score_cvs):.3f}')
            ax1.set_xlabel('Coefficient of Variation (Score)', fontweight='bold')
            ax1.set_ylabel('Device Count', fontweight='bold')
            ax1.set_title('Score Stability Distribution', fontweight='bold')
            ax1.legend()
            ax1.grid(alpha=0.3)
            
            # Plot 2: Stability vs Performance
            ax2 = axes[0, 1]
            scatter = ax2.scatter(score_cvs, avg_scores, c=avg_scores, cmap='RdYlGn',
                                vmin=0, vmax=100, s=100, alpha=0.6, edgecolors='black', linewidth=0.5)
            ax2.set_xlabel('Coefficient of Variation (Stability)', fontweight='bold')
            ax2.set_ylabel('Average Memristivity Score', fontweight='bold')
            ax2.set_title('Stability vs Performance', fontweight='bold')
            ax2.grid(alpha=0.3)
            cbar = plt.colorbar(scatter, ax=ax2)
            cbar.set_label('Average Score', fontsize=11)
            
            # Plot 3: Ron CV Distribution
            ax3 = axes[1, 0]
            ron_cvs = [d['ron_cv'] for d in devices_with_multiple if d['ron_cv'] > 0]
            if ron_cvs:
                ax3.hist(ron_cvs, bins=30, color='#FF9800', alpha=0.7, edgecolor='black')
                ax3.axvline(np.mean(ron_cvs), color='red', linestyle='--', 
                           linewidth=2, label=f'Mean CV: {np.mean(ron_cvs):.3f}')
                ax3.set_xlabel('Coefficient of Variation (Ron)', fontweight='bold')
                ax3.set_ylabel('Device Count', fontweight='bold')
                ax3.set_title('Ron Stability Distribution', fontweight='bold')
                ax3.legend()
                ax3.grid(alpha=0.3)
            else:
                ax3.text(0.5, 0.5, 'No Ron stability data', 
                        ha='center', va='center', transform=ax3.transAxes)
            
            # Plot 4: Roff CV Distribution
            ax4 = axes[1, 1]
            roff_cvs = [d['roff_cv'] for d in devices_with_multiple if d['roff_cv'] > 0]
            if roff_cvs:
                ax4.hist(roff_cvs, bins=30, color='#9C27B0', alpha=0.7, edgecolor='black')
                ax4.axvline(np.mean(roff_cvs), color='red', linestyle='--', 
                           linewidth=2, label=f'Mean CV: {np.mean(roff_cvs):.3f}')
                ax4.set_xlabel('Coefficient of Variation (Roff)', fontweight='bold')
                ax4.set_ylabel('Device Count', fontweight='bold')
                ax4.set_title('Roff Stability Distribution', fontweight='bold')
                ax4.legend()
                ax4.grid(alpha=0.3)
            else:
                ax4.text(0.5, 0.5, 'No Roff stability data', 
                        ha='center', va='center', transform=ax4.transAxes)
            
            plt.tight_layout()
            output_file = os.path.join(self.plots_dir, '22_performance_stability_analysis.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"[PLOT] Saved: 22_performance_stability_analysis.png")
            self._export_stability_analysis_data(devices_with_multiple)
            
        except Exception as e:
            print(f"[PLOT ERROR] Performance stability analysis failed: {e}")
            import traceback
            traceback.print_exc()
    
    def _export_stability_analysis_data(self, devices_data=None) -> None:
        """Export stability analysis data."""
        if devices_data is None:
            devices_data = []
            for dev in self.devices_data:
                measurements = dev.get('all_measurements', [])
                if len(measurements) >= 3:
                    scores = [m.get('classification', {}).get('memristivity_score', 0) or 0 
                             for m in measurements]
                    if len(scores) >= 3:
                        score_cv = np.std(scores) / np.mean(scores) if np.mean(scores) > 0 else 0
                        devices_data.append({
                            'device_id': dev['device_id'],
                            'avg_score': np.mean(scores),
                            'score_cv': score_cv,
                            'num_measurements': len(measurements)
                        })
        
            if devices_data:
                df = pd.DataFrame(devices_data)
                output_file = os.path.join(self.data_origin_formatted_dir, 'performance_stability.csv')
                df.to_csv(output_file, index=False)
                print(f"[ORIGIN] Exported: performance_stability.csv")
    
    # === PLOT 23: Warning Analysis Dashboard ===
    def plot_warning_analysis_dashboard(self) -> None:
        """Detailed analysis of warnings and their impact on performance."""
        try:
            warning_types = {}
            warning_devices = {}
            devices_with_warnings = []
            devices_without_warnings = []
            
            for dev in self.devices_data:
                warnings = dev.get('warnings', [])
                score = dev['classification'].get('memristivity_score', 0) or 0
                dtype = dev['classification'].get('device_type', 'unknown')
                
                if warnings:
                    devices_with_warnings.append({'score': score, 'type': dtype})
                    for warning in warnings:
                        warning_type = warning.split(':')[0].split('.')[0].strip()[:50]
                        if warning_type:
                            warning_types[warning_type] = warning_types.get(warning_type, 0) + 1
                            if warning_type not in warning_devices:
                                warning_devices[warning_type] = []
                            warning_devices[warning_type].append(score)
                else:
                    devices_without_warnings.append({'score': score, 'type': dtype})
            
            if not warning_types:
                print("[PLOT] No warnings found for analysis")
                return
            
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            fig.suptitle(f'Warning Analysis Dashboard - {self.sample_name}', 
                        fontsize=16, fontweight='bold')
            
            # Plot 1: Warning frequency
            ax1 = axes[0, 0]
            sorted_warnings = sorted(warning_types.items(), key=lambda x: x[1], reverse=True)[:10]
            labels = [w[0] for w in sorted_warnings]
            counts = [w[1] for w in sorted_warnings]
            
            bars = ax1.barh(range(len(labels)), counts, color='#F44336', alpha=0.7, edgecolor='black')
            ax1.set_yticks(range(len(labels)))
            ax1.set_yticklabels(labels)
            ax1.set_xlabel('Warning Count', fontweight='bold')
            ax1.set_title('Most Common Warnings', fontweight='bold')
            ax1.grid(axis='x', alpha=0.3)
            for i, (bar, count) in enumerate(zip(bars, counts)):
                ax1.text(count + 0.5, i, str(count), va='center', fontweight='bold')
            
            # Plot 2: Score distribution with/without warnings
            ax2 = axes[0, 1]
            scores_with = [d['score'] for d in devices_with_warnings]
            scores_without = [d['score'] for d in devices_without_warnings]
            
            if scores_with and scores_without:
                ax2.hist(scores_with, bins=20, alpha=0.6, label=f'With Warnings (n={len(scores_with)})',
                        color='#F44336', edgecolor='black')
                ax2.hist(scores_without, bins=20, alpha=0.6, label=f'No Warnings (n={len(scores_without)})',
                        color='#4CAF50', edgecolor='black')
                ax2.axvline(np.mean(scores_with), color='red', linestyle='--', linewidth=2)
                ax2.axvline(np.mean(scores_without), color='green', linestyle='--', linewidth=2)
                ax2.set_xlabel('Memristivity Score', fontweight='bold')
                ax2.set_ylabel('Device Count', fontweight='bold')
                ax2.set_title('Score Distribution: With vs Without Warnings', fontweight='bold')
                ax2.legend()
                ax2.grid(alpha=0.3)
            
            # Plot 3: Average score by warning type
            ax3 = axes[1, 0]
            warning_avg_scores = {}
            for warning_type, scores in warning_devices.items():
                if scores:
                    warning_avg_scores[warning_type] = np.mean(scores)
            
            sorted_avg = sorted(warning_avg_scores.items(), key=lambda x: x[1])[:10]
            if sorted_avg:
                labels_avg = [w[0] for w in sorted_avg]
                avg_scores = [w[1] for w in sorted_avg]
                bars = ax3.barh(range(len(labels_avg)), avg_scores, color='#FF9800', 
                               alpha=0.7, edgecolor='black')
                ax3.set_yticks(range(len(labels_avg)))
                ax3.set_yticklabels(labels_avg, fontsize=8)
                ax3.set_xlabel('Average Memristivity Score', fontweight='bold')
                ax3.set_title('Average Score by Warning Type', fontweight='bold')
                ax3.set_xlim(0, 100)
                ax3.grid(axis='x', alpha=0.3)
            
            # Plot 4: Warning count vs performance
            ax4 = axes[1, 1]
            warning_counts_list = []
            scores_list = []
            for dev in self.devices_data:
                warning_count = len(dev.get('warnings', []))
                score = dev['classification'].get('memristivity_score', 0) or 0
                warning_counts_list.append(warning_count)
                scores_list.append(score)
            
            scatter = ax4.scatter(warning_counts_list, scores_list, alpha=0.6, s=50,
                                c=scores_list, cmap='RdYlGn', vmin=0, vmax=100,
                                edgecolors='black', linewidth=0.5)
            ax4.set_xlabel('Number of Warnings', fontweight='bold')
            ax4.set_ylabel('Memristivity Score', fontweight='bold')
            ax4.set_title('Warning Count vs Performance', fontweight='bold')
            ax4.grid(alpha=0.3)
            cbar = plt.colorbar(scatter, ax=ax4)
            cbar.set_label('Memristivity Score', fontsize=11)
            
            plt.tight_layout()
            output_file = os.path.join(self.plots_dir, '23_warning_analysis_dashboard.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"[PLOT] Saved: 23_warning_analysis_dashboard.png")
            self._export_warning_analysis_data(warning_types, warning_devices, devices_with_warnings, devices_without_warnings)
            
        except Exception as e:
            print(f"[PLOT ERROR] Warning analysis dashboard failed: {e}")
            import traceback
            traceback.print_exc()
    
    def _export_warning_analysis_data(self, warning_types=None, warning_devices=None,
                                     devices_with=None, devices_without=None) -> None:
        """Export warning analysis data."""
        if warning_types is None:
            warning_types = {}
            warning_devices = {}
            devices_with = []
            devices_without = []
            for dev in self.devices_data:
                warnings = dev.get('warnings', [])
                score = dev['classification'].get('memristivity_score', 0) or 0
                if warnings:
                    devices_with.append(score)
                    for warning in warnings:
                        warning_type = warning.split(':')[0].split('.')[0].strip()[:50]
                        if warning_type:
                            warning_types[warning_type] = warning_types.get(warning_type, 0) + 1
                            if warning_type not in warning_devices:
                                warning_devices[warning_type] = []
                            warning_devices[warning_type].append(score)
                else:
                    devices_without.append(score)
        
        # Export warning summary
        rows = []
        for warning_type, count in sorted(warning_types.items(), key=lambda x: x[1], reverse=True):
            avg_score = np.mean(warning_devices.get(warning_type, [0]))
            rows.append({
                'Warning_Type': warning_type,
                'Count': count,
                'Average_Score': avg_score
            })
        
        df = pd.DataFrame(rows)
        output_file = os.path.join(self.data_origin_formatted_dir, 'warning_analysis.csv')
        df.to_csv(output_file, index=False)
        print(f"[ORIGIN] Exported: warning_analysis.csv")
    
    # === PLOT 24: On/Off Ratio vs Switching Ratio ===
    def plot_ratio_comparison(self) -> None:
        """Compare On/Off ratio vs Switching ratio metrics."""
        try:
            switching_ratios = []
            on_off_ratios = []
            scores = []
            device_types = []
            
            for dev in self.devices_data:
                switching = dev['resistance'].get('switching_ratio', np.nan)
                on_off = dev['resistance'].get('on_off_ratio', np.nan)
                score = dev['classification'].get('memristivity_score', 0) or 0
                dtype = dev['classification'].get('device_type', 'unknown')
                
                if not np.isnan(switching) and not np.isnan(on_off) and switching > 0 and on_off > 0:
                    switching_ratios.append(switching)
                    on_off_ratios.append(on_off)
                    scores.append(score)
                    device_types.append(dtype)
            
            if not switching_ratios:
                print("[PLOT] No ratio data for comparison")
                return
            
            fig, axes = plt.subplots(1, 2, figsize=(16, 8))
            fig.suptitle(f'On/Off Ratio vs Switching Ratio - {self.sample_name}', 
                        fontsize=16, fontweight='bold')
            
            # Plot 1: Scatter comparison
            ax1 = axes[0]
            type_colors = {'memristive': 'green', 'ohmic': 'red', 'capacitive': 'blue', 
                          'unknown': 'gray'}
            
            for dtype in set(device_types):
                mask = [dt == dtype for dt in device_types]
                switch_subset = [s for s, m in zip(switching_ratios, mask) if m]
                onoff_subset = [o for o, m in zip(on_off_ratios, mask) if m]
                ax1.scatter(switch_subset, onoff_subset, c=type_colors.get(dtype, 'gray'),
                           alpha=0.6, s=50, edgecolors='black', linewidth=0.5,
                           label=dtype.replace('_', ' ').title())
            
            # Add 1:1 line
            max_val = max(max(switching_ratios), max(on_off_ratios))
            ax1.plot([1, max_val], [1, max_val], 'k--', alpha=0.5, label='1:1 Line')
            
            ax1.set_xscale('log')
            ax1.set_yscale('log')
            ax1.set_xlabel('Switching Ratio (Roff/Ron)', fontweight='bold')
            ax1.set_ylabel('On/Off Ratio', fontweight='bold')
            ax1.set_title('Ratio Comparison', fontweight='bold')
            ax1.grid(alpha=0.3)
            ax1.legend()
            
            # Plot 2: Distribution comparison
            ax2 = axes[1]
            ax2.hist(np.log10(switching_ratios), bins=30, alpha=0.6, label='Switching Ratio',
                    color='#2196F3', edgecolor='black')
            ax2.hist(np.log10(on_off_ratios), bins=30, alpha=0.6, label='On/Off Ratio',
                    color='#FF9800', edgecolor='black')
            ax2.set_xlabel('log₁₀(Ratio)', fontweight='bold')
            ax2.set_ylabel('Device Count', fontweight='bold')
            ax2.set_title('Ratio Distribution Comparison', fontweight='bold')
            ax2.legend()
            ax2.grid(alpha=0.3)
            
            plt.tight_layout()
            output_file = os.path.join(self.plots_dir, '24_ratio_comparison.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"[PLOT] Saved: 24_ratio_comparison.png")
            self._export_ratio_comparison_data(switching_ratios, on_off_ratios, scores, device_types)
            
        except Exception as e:
            print(f"[PLOT ERROR] Ratio comparison failed: {e}")
            import traceback
            traceback.print_exc()
    
    def _export_ratio_comparison_data(self, switching=None, onoff=None, scores=None, types=None) -> None:
        """Export ratio comparison data."""
        if switching is None:
            switching, onoff, scores, types = [], [], [], []
            for dev in self.devices_data:
                switch = dev['resistance'].get('switching_ratio', np.nan)
                on_off = dev['resistance'].get('on_off_ratio', np.nan)
                if not np.isnan(switch) and not np.isnan(on_off) and switch > 0 and on_off > 0:
                    switching.append(switch)
                    onoff.append(on_off)
                    scores.append(dev['classification'].get('memristivity_score', 0) or 0)
                    types.append(dev['classification'].get('device_type', 'unknown'))
        
        df = pd.DataFrame({
            'Switching_Ratio': switching,
            'On_Off_Ratio': onoff,
            'Memristivity_Score': scores,
            'Device_Type': types
        })
        output_file = os.path.join(self.data_origin_formatted_dir, 'ratio_comparison.csv')
        df.to_csv(output_file, index=False)
        print(f"[ORIGIN] Exported: ratio_comparison.csv")
    
    # === PLOT 25: Section Spatial Gradient ===
    def plot_section_spatial_gradient(self) -> None:
        """Show spatial trends and gradients across sections."""
        try:
            # Extract section positions and metrics
            section_positions = {}
            for dev in self.devices_data:
                section = dev.get('section')
                if section:
                    if section not in section_positions:
                        section_positions[section] = {'scores': [], 'qualities': [], 'yield': 0, 'total': 0}
                    section_positions[section]['scores'].append(dev['classification'].get('memristivity_score', 0) or 0)
                    quality = self._safe_get_quality_score(dev)
                    if not np.isnan(quality):
                        section_positions[section]['qualities'].append(quality)
                    section_positions[section]['total'] += 1
                    if dev['classification'].get('device_type') == 'memristive':
                        section_positions[section]['yield'] += 1
            
            if not section_positions:
                print("[PLOT] No section data for spatial gradient")
                return
            
            sections = sorted(section_positions.keys())
            
            # Calculate section metrics
            section_metrics = {
                'avg_score': [np.mean(section_positions[s]['scores']) if section_positions[s]['scores'] else 0 
                             for s in sections],
                'avg_quality': [np.mean(section_positions[s]['qualities']) if section_positions[s]['qualities'] else 0 
                               for s in sections],
                'yield_pct': [100 * section_positions[s]['yield'] / section_positions[s]['total'] 
                             if section_positions[s]['total'] > 0 else 0 for s in sections]
            }
            
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            fig.suptitle(f'Section Spatial Gradient - {self.sample_name}', 
                        fontsize=16, fontweight='bold')
            
            x = np.arange(len(sections))
            
            # Plot 1: Score gradient
            ax1 = axes[0, 0]
            bars = ax1.bar(x, section_metrics['avg_score'], color='#4CAF50', 
                          alpha=0.7, edgecolor='black')
            ax1.plot(x, section_metrics['avg_score'], 'ro-', linewidth=2, markersize=8, label='Trend')
            ax1.set_xlabel('Section', fontweight='bold')
            ax1.set_ylabel('Average Memristivity Score', fontweight='bold')
            ax1.set_title('Score Gradient Across Sections', fontweight='bold')
            ax1.set_xticks(x)
            ax1.set_xticklabels(sections)
            ax1.set_ylim(0, 100)
            ax1.grid(axis='y', alpha=0.3)
            ax1.legend()
            
            # Plot 2: Yield gradient
            ax2 = axes[0, 1]
            bars = ax2.bar(x, section_metrics['yield_pct'], color='#FF9800', 
                          alpha=0.7, edgecolor='black')
            ax2.plot(x, section_metrics['yield_pct'], 'bo-', linewidth=2, markersize=8, label='Trend')
            ax2.set_xlabel('Section', fontweight='bold')
            ax2.set_ylabel('Memristive Yield (%)', fontweight='bold')
            ax2.set_title('Yield Gradient Across Sections', fontweight='bold')
            ax2.set_xticks(x)
            ax2.set_xticklabels(sections)
            ax2.set_ylim(0, 100)
            ax2.grid(axis='y', alpha=0.3)
            ax2.legend()
            
            # Plot 3: Quality gradient
            ax3 = axes[1, 0]
            bars = ax3.bar(x, section_metrics['avg_quality'], color='#2196F3', 
                          alpha=0.7, edgecolor='black')
            ax3.plot(x, section_metrics['avg_quality'], 'go-', linewidth=2, markersize=8, label='Trend')
            ax3.set_xlabel('Section', fontweight='bold')
            ax3.set_ylabel('Average Quality Score', fontweight='bold')
            ax3.set_title('Quality Gradient Across Sections', fontweight='bold')
            ax3.set_xticks(x)
            ax3.set_xticklabels(sections)
            ax3.set_ylim(0, 100)
            ax3.grid(axis='y', alpha=0.3)
            ax3.legend()
            
            # Plot 4: Combined gradient (normalized)
            ax4 = axes[1, 1]
            normalized_score = [s / 100.0 for s in section_metrics['avg_score']]
            normalized_yield = [y / 100.0 for y in section_metrics['yield_pct']]
            normalized_quality = [q / 100.0 for q in section_metrics['avg_quality']]
            
            ax4.plot(x, normalized_score, 'o-', linewidth=2, markersize=8, 
                    label='Score (normalized)', color='#4CAF50')
            ax4.plot(x, normalized_yield, 's-', linewidth=2, markersize=8, 
                    label='Yield (normalized)', color='#FF9800')
            ax4.plot(x, normalized_quality, '^-', linewidth=2, markersize=8, 
                    label='Quality (normalized)', color='#2196F3')
            ax4.set_xlabel('Section', fontweight='bold')
            ax4.set_ylabel('Normalized Value (0-1)', fontweight='bold')
            ax4.set_title('Combined Gradient (Normalized)', fontweight='bold')
            ax4.set_xticks(x)
            ax4.set_xticklabels(sections)
            ax4.set_ylim(0, 1)
            ax4.grid(alpha=0.3)
            ax4.legend()
            
            plt.tight_layout()
            output_file = os.path.join(self.plots_dir, '25_section_spatial_gradient.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"[PLOT] Saved: 25_section_spatial_gradient.png")
            self._export_spatial_gradient_data(sections, section_metrics)
            
        except Exception as e:
            print(f"[PLOT ERROR] Section spatial gradient failed: {e}")
            import traceback
            traceback.print_exc()
    
    def _export_spatial_gradient_data(self, sections=None, metrics=None) -> None:
        """Export spatial gradient data."""
        if sections is None:
            section_positions = {}
            for dev in self.devices_data:
                section = dev.get('section')
                if section:
                    if section not in section_positions:
                        section_positions[section] = {'scores': [], 'qualities': [], 'yield': 0, 'total': 0}
                    section_positions[section]['scores'].append(dev['classification'].get('memristivity_score', 0) or 0)
                    quality = self._safe_get_quality_score(dev)
                    if not np.isnan(quality):
                        section_positions[section]['qualities'].append(quality)
                    section_positions[section]['total'] += 1
                    if dev['classification'].get('device_type') == 'memristive':
                        section_positions[section]['yield'] += 1
            sections = sorted(section_positions.keys())
            metrics = {
                'avg_score': [np.mean(section_positions[s]['scores']) if section_positions[s]['scores'] else 0 
                             for s in sections],
                'avg_quality': [np.mean(section_positions[s]['qualities']) if section_positions[s]['qualities'] else 0 
                               for s in sections],
                'yield_pct': [100 * section_positions[s]['yield'] / section_positions[s]['total'] 
                             if section_positions[s]['total'] > 0 else 0 for s in sections]
            }
        
        df = pd.DataFrame({
            'Section': sections,
            'Average_Score': metrics['avg_score'],
            'Average_Quality': metrics['avg_quality'],
            'Yield_Percentage': metrics['yield_pct']
        })
        output_file = os.path.join(self.data_origin_formatted_dir, 'section_spatial_gradient.csv')
        df.to_csv(output_file, index=False)
        print(f"[ORIGIN] Exported: section_spatial_gradient.csv")
    
    # === HELPER METHODS ===
    def _safe_get_quality_score(self, dev: Dict) -> float:
        """Safely extract memory window quality score from device data."""
        try:
            quality = dev.get('quality', {})
            if not isinstance(quality, dict):
                return np.nan
            mw_quality = quality.get('memory_window_quality', {})
            if not isinstance(mw_quality, dict):
                return np.nan
            return mw_quality.get('overall_quality_score', np.nan)
        except Exception:
            return np.nan
    
    # === MAIN DEVICE SUMMARY EXPORT ===
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
                'Warning_Count': len(dev['warnings']),
                'Total_Measurements': dev['total_measurements']
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

All data files are in CSV format with headers, optimized for Origin import.
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Sample: {self.sample_name}

### Main Files:
- `device_summary.csv`: Complete device-level summary (all metrics)
- `memristivity_heatmap.csv`: Device positions and scores for heatmap
- `conduction_mechanisms.csv`: Mechanism distribution data
- `memory_window_quality.csv`: Quality metrics for all devices
- `classification_scatter.csv`: Ron/Roff data with classification
- `power_efficiency.csv`: Power and energy metrics (if available)
- `device_leaderboard.csv`: Ranked device performance
- `spatial_data.csv`: Spatial distribution data
- `forming_status.csv`: Device forming status counts

### Origin Import Steps:

1. Open Origin
2. File → Import → Single ASCII
3. Select CSV file
4. In Import Wizard:
   - Use first row as column headers: YES
   - Delimiter: Comma
   - Skip lines: 0
5. Click Finish

### Plot Recreation:

**Heatmap (memristivity_heatmap.csv):**
- Plot → 2D: Heatmap
- Z = Memristivity_Score
- X = Device_Number, Y = Section

**Scatter (classification_scatter.csv):**
- Plot → 2D: Scatter
- X = Ron_Mean (log scale)
- Y = Roff_Mean (log scale)
- Color by: Memristivity_Score
- Size by: Switching_Ratio

**Bar Chart (conduction_mechanisms.csv):**
- Plot → 2D: Column/Bar
- X = Mechanism, Y = Count

**Box Plot (memory_window_quality.csv):**
- Plot → 2D: Box Chart
- Select columns: Ron_Stability, Roff_Stability, Overall_Quality_Score

**Leaderboard (device_leaderboard.csv):**
- Plot → 2D: Bar
- X = Device_ID, Y = Composite_Score
- Sort by Composite_Score descending

## Notes:
- All resistance values are in Ohms
- Scores are 0-100 scale
- NaN values indicate data not available
- Power values in Watts, Energy in Joules
"""
        
        readme_file = os.path.join(self.data_origin_formatted_dir, 'README_ORIGIN_IMPORT.txt')
        with open(readme_file, 'w', encoding='utf-8') as f:
            f.write(readme.strip())
        print(f"[ORIGIN] Created: README_ORIGIN_IMPORT.txt")












