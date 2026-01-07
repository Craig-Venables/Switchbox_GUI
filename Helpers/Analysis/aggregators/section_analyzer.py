"""
Section-Level Analyzer
======================

Purpose:
--------
Analyzes a section (single letter folder, e.g., "A", "B") of a sample/substrate
containing multiple devices. Provides section-level aggregation, visualization,
and statistical analysis.

What This Module Does:
----------------------
1. Analyzes all devices within a section (letter folder)
2. Categorizes sweeps by test type and voltage
3. Generates stacked sweep plots:
   - By test type (e.g., all "St_v1" sweeps combined)
   - By voltage (e.g., all "0.5v" sweeps combined)
4. Performs statistical comparisons between devices in the section
5. Generates comparison plots for key metrics (Ron, Roff, ratios, etc.)

Key Classes:
------------
- SectionAnalyzer: Main section analysis class
- TestTypeAnalyzer: Manages test type configurations from JSON

Key Methods:
------------
- analyze_section_sweeps(): Main entry point - runs complete section analysis
- categorize_sweeps(): Organizes sweeps by type and voltage
- plot_sweeps_by_type(): Creates stacked plots grouped by test type
- plot_sweeps_by_voltage(): Creates stacked plots grouped by voltage
- get_main_sweeps_stats(): Extracts statistics for main sweeps
- plot_statistical_comparisons(): Creates comparison plots for key metrics

Usage:
------
    from Helpers.Analysis import SectionAnalyzer
    
    analyzer = SectionAnalyzer(
        top_level_path="path/to/sample",
        section="A",  # Section letter
        sample_name="sample_name"
    )
    analyzer.analyze_section_sweeps()

Output:
-------
Saved to: {sample_dir}/{section}/plots_combined/
- {test_type}/sweep_{n}_combined.png: Stacked sweeps by type
- voltage_groups/voltage_{v}V_combined.png: Stacked sweeps by voltage
- statistics/main_sweeps_comparison.png: Comparison of main sweeps
- statistics/{metric}_comparison.png: Bar plots for key metrics

Called By:
----------
- comprehensive_analyzer.py → ComprehensiveAnalyzer.run_comprehensive_analysis()
  (runs section analysis for each section in the sample)

Dependencies:
-------------
- core/sweep_analyzer.py: SweepAnalyzer (imported as AnalyzeSingleFile) for individual file analysis
- Json_Files/test_configurations.json: Test type configurations
"""

import numpy as np
import matplotlib
# Force Agg backend to prevent GUI resource allocation
matplotlib.use('Agg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from pathlib import Path
import json
from functools import lru_cache
from typing import Tuple, Optional, Dict, List
import os

# Import single file analyzer
try:
    from ..core.sweep_analyzer import SweepAnalyzer as AnalyzeSingleFile
except ImportError:
    AnalyzeSingleFile = None

# Get project root
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_CONFIG_PATH = _PROJECT_ROOT / "Json_Files" / "test_configurations.json"


class TestTypeAnalyzer:
    """
    Analyzes and manages test type configurations from JSON files.
    """
    
    def __init__(self, config_path=None):
        if config_path is None:
            config_path = _DEFAULT_CONFIG_PATH
        self.config_path = Path(config_path)
        self.test_configs = {}
        self.load_test_configurations()

    def load_test_configurations(self):
        try:
            with open(self.config_path, 'r') as f:
                self.test_configs = json.load(f)
        except Exception as e:
            print(f"Error parsing configuration file: {e}. Using empty configurations.")
            self.test_configs = {}

    def get_sweep_combinations(self, test_type):
        if test_type in self.test_configs:
            combinations = self.test_configs[test_type].get('sweep_combinations', [])
            if combinations and isinstance(combinations[0], dict):
                return [combo['sweeps'] for combo in combinations]
            return combinations
        return []

    def get_sweep_titles(self, test_type):
        if test_type in self.test_configs:
            combinations = self.test_configs[test_type].get('sweep_combinations', [])
            if combinations and isinstance(combinations[0], dict):
                return [combo.get('title', f"Combination {i+1}") for i, combo in enumerate(combinations)]
            return [f"Combination {i + 1}" for i in range(len(combinations))]
        return []

    def get_main_sweep(self, test_type):
        if test_type in self.test_configs:
            return self.test_configs[test_type].get('main_sweep')
        return None

    def plot_customization(self, test_type, ax1, ax2):
        if test_type == 'St_v1':
            ax1.set_title('Standard V1 Test')
            ax2.set_title('Standard V1 Test (Log Scale)')
        elif test_type == 'Dy_v1':
            ax1.set_title('Dynamic V1 Test')
            ax2.set_title('Dynamic V1 Test (Log Scale)')
            ax1.set_ylim(-1e-3, 1e-3)


class SectionAnalyzer:
    """
    Analyzes a section of a sample/substrate for memristor device measurements.
    Restores original functionality for section summaries and stacked plots.
    """
    
    def __init__(self, top_level_path, section, sample_name, config_path=None):
        self.top_level_path = Path(top_level_path)
        self.test_analyzer = TestTypeAnalyzer(config_path)
        self.section_path = self.top_level_path / section # Assuming top_level_path is sample_dir
        self.sample_name = sample_name
        self.section = section

        # Verify path - if top_level_path is just the root data dir, we need to append sample_name
        # But commonly in the new code sample_dir is passed. Let's handle both.
        if not self.section_path.exists():
            # Try appending sample_name
            candidate = self.top_level_path / sample_name / section
            if candidate.exists():
                self.section_path = candidate
        
        # Initialize data structures
        self.sweeps_by_type = {}
        self.sweeps_by_voltage = {}
        self.device_list_with_type_and_status = {}

        # Get device folders (numbered 1-99)
        self.device_folders = [d for d in self.section_path.glob('[0-9]*') if d.is_dir() and d.name.isdigit()]
        
        # Detect test type and working status
        for device in self.device_folders:
            test_type = self.detect_test_type(device)
            # check_working_device now finds minimum sweep for code_name automatically
            working_device = self.check_working_device(device, test_type) if test_type else False
            # Store min_sweep for reference (or None if not found)
            min_sweep = self._find_min_sweep_for_code_name(device, test_type) if test_type else None
            self.device_list_with_type_and_status[device] = (test_type, working_device, min_sweep)

    @lru_cache(maxsize=128)
    def read_data_file(self, file_path) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray]]:
        try:
            data = np.loadtxt(file_path, skiprows=1)
            # Handle empty or single line files
            if data.ndim == 1:
                data = data.reshape(1, -1)
            if data.shape[1] < 2:
                return None, None, None
                
            v = data[:, 0]
            i = data[:, 1]
            t = data[:, 2] if data.shape[1] > 2 else None
            return v, i, t
        except Exception as e:
            # print(f"Error reading file {file_path}: {str(e)}")
            return None, None, None

    def detect_test_type(self, device_path):
        # Look for first sweep with valid filename format
        files = list(device_path.glob('*.txt'))
        for f in files:
            if f.name == 'log.txt': continue
            parts = f.name.replace('.txt', '').split('-')
            if len(parts) > 6:
                return parts[6]
        return None
    
    def _find_min_sweep_for_code_name(self, device_path, code_name):
        """
        Find the minimum sweep number for a given code_name in a device folder.
        This treats the lowest number as the first measurement for that code_name.
        
        Args:
            device_path: Path to device directory
            code_name: Code name to search for
            
        Returns:
            int or None: Minimum sweep number for this code_name, or None if not found
        """
        files = list(device_path.glob('*.txt'))
        min_sweep = None
        
        for f in files:
            if f.name == 'log.txt':
                continue
            try:
                parts = f.name.replace('.txt', '').split('-')
                if len(parts) > 6:
                    file_code_name = parts[6]
                    if file_code_name == code_name:
                        sweep_num = int(parts[0])
                        if min_sweep is None or sweep_num < min_sweep:
                            min_sweep = sweep_num
            except (ValueError, IndexError):
                continue
        
        return min_sweep

    def check_working_device(self, device_path, test_type_or_sweep):
        """
        Check if device is working by reading the first measurement for the code_name.
        
        Args:
            device_path: Path to device directory
            test_type_or_sweep: Code name (test_type) string, or legacy numeric sweep number
        """
        # If it's a code_name (string that's not a digit), use it directly
        # Otherwise, detect test_type from device (legacy behavior)
        if isinstance(test_type_or_sweep, str) and not test_type_or_sweep.isdigit():
            test_type = test_type_or_sweep
        else:
            test_type = self.detect_test_type(device_path)
        
        if not test_type:
            return False
        
        # Find minimum sweep number for this code_name (treat as first measurement)
        min_sweep = self._find_min_sweep_for_code_name(device_path, test_type)
        if min_sweep is None:
            return False
        
        # Use the minimum sweep as the first measurement for this code_name
        sweep_files = list(device_path.glob(f'{min_sweep}-*.txt'))
        sweep_files = [f for f in sweep_files if f.name != 'log.txt']
        
        # Filter to only files with matching code_name
        matching_files = []
        for f in sweep_files:
            try:
                parts = f.name.replace('.txt', '').split('-')
                if len(parts) > 6 and parts[6] == test_type:
                    matching_files.append(f)
            except (ValueError, IndexError):
                continue
        
        if matching_files:
            voltage, current, _ = self.read_data_file(matching_files[0])
            if current is not None and len(current) > 0:
                max_current = np.max(np.abs(current))
                if max_current >= 1E-9:
                    return True
        return False

    def create_subplot(self, title):
        fig = Figure(figsize=(15, 6))
        # Attach canvas explicitly for headless rendering
        FigureCanvasAgg(fig)
        ax1 = fig.add_subplot(121)
        ax2 = fig.add_subplot(122)
        fig.suptitle(title)
        ax2.set_yscale('log')
        return fig, ax1, ax2

    def plot_data(self, voltage, current, label, ax1, ax2):
        if voltage is not None and current is not None and len(voltage) > 0:
            ax1.plot(voltage, current, 'o-', label=label, markersize=2, linewidth=1, alpha=0.7)
            ax2.plot(voltage, np.abs(current), 'o-', label=label, markersize=2, linewidth=1, alpha=0.7)
            ax1.set_xlabel('Voltage (V)')
            ax1.set_ylabel('Current (A)')
            ax2.set_xlabel('Voltage (V)')
            ax2.set_ylabel('|Current| (A)')

    def analyze_section_sweeps(self):
        """
        Perform section analysis: categorize sweeps and generate plots.
        """
        print(f"[SECTION] Analyzing section {self.section}...")
        
        # Create output directories
        plots_dir = self.section_path / 'plots_combined'
        plots_dir.mkdir(exist_ok=True)
        stats_dir = plots_dir / 'statistics'
        stats_dir.mkdir(exist_ok=True)

        # 1. Categorize
        self.categorize_sweeps()

        # 2. Plot by type (stacked sweeps)
        self.plot_sweeps_by_type(plots_dir)

        # 3. Plot by voltage (stacked sweeps)
        self.plot_sweeps_by_voltage(plots_dir)

        # 4. Main sweep stats and comparison
        device_stats, main_sweep_data = self.get_main_sweeps_stats()
        
        # 5. Statistical Plots
        self.plot_statistical_comparisons(device_stats, main_sweep_data, stats_dir)
        
        print(f"[SECTION] Completed analysis for section {self.section}")
        return device_stats

    def categorize_sweeps(self):
        for device in self.device_folders:
            try:
                files = list(device.glob('*.txt'))
                test_type = self.detect_test_type(device)
                
                for file in files:
                    if file.name == 'log.txt': continue
                    try:
                        parts = file.name.replace('.txt', '').split('-')
                        if len(parts) < 3: continue
                        
                        sweep_num = int(parts[0])
                        
                        # Extract voltage
                        voltage_value = None
                        for p in parts:
                            if 'v' in p.lower() and any(c.isdigit() for c in p) and 'sv' not in p:
                                voltage_value = p.lower().replace('v', '')
                                break
                        
                        if test_type:
                            # Store by type
                            if test_type not in self.sweeps_by_type:
                                self.sweeps_by_type[test_type] = {}
                            if sweep_num not in self.sweeps_by_type[test_type]:
                                self.sweeps_by_type[test_type][sweep_num] = []
                            self.sweeps_by_type[test_type][sweep_num].append((device.name, file))
                            
                            # Store by voltage
                            if voltage_value:
                                if voltage_value not in self.sweeps_by_voltage:
                                    self.sweeps_by_voltage[voltage_value] = []
                                self.sweeps_by_voltage[voltage_value].append((device.name, file, test_type))
                                
                    except Exception:
                        continue
            except Exception:
                continue

    def plot_sweeps_by_type(self, plots_dir):
        for test_type, sweeps in self.sweeps_by_type.items():
            test_type_dir = plots_dir / test_type
            test_type_dir.mkdir(exist_ok=True)

            for sweep_num in sweeps.keys():
                fig, ax1, ax2 = self.create_subplot(
                    f"{self.sample_name} section {self.section} {test_type} sweep {sweep_num} combined")
                
                self.test_analyzer.plot_customization(test_type, ax1, ax2)

                for device_name, sweep_file in sweeps[sweep_num]:
                    voltage, current, _ = self.read_data_file(sweep_file)
                    if voltage is not None:
                        label = f"{self.section}{device_name} (Sweep {sweep_num})"
                        self.plot_data(voltage, current, label, ax1, ax2)

                if len(ax1.get_lines()) > 0:
                    ax1.legend(fontsize='x-small')
                if len(ax2.get_lines()) > 0:
                    ax2.legend(fontsize='x-small')
                
                try:
                    fig.savefig(test_type_dir / f'sweep_{sweep_num}_combined.png')
                except Exception:
                    pass
                # No plt.close() needed for Figure objects, just let them go out of scope

    def plot_sweeps_by_voltage(self, plots_dir):
        voltage_dir = plots_dir / 'voltage_groups'
        voltage_dir.mkdir(exist_ok=True)
        
        for voltage_value, sweeps in self.sweeps_by_voltage.items():
            fig, ax1, ax2 = self.create_subplot(
                f"{self.sample_name} section {self.section} {voltage_value}V combined")

            # Group by test type
            sweeps_by_test = {}
            for device_name, sweep_file, test_type in sweeps:
                if test_type not in sweeps_by_test:
                    sweeps_by_test[test_type] = []
                sweeps_by_test[test_type].append((device_name, sweep_file))

            for test_type, test_sweeps in sweeps_by_test.items():
                self.test_analyzer.plot_customization(test_type, ax1, ax2)
                for device_name, sweep_file in test_sweeps:
                    voltage, current, _ = self.read_data_file(sweep_file)
                    if voltage is not None:
                        try:
                            sweep_num = int(sweep_file.name.split('-')[0])
                            label = f"{self.section}{device_name} {test_type} (Sweep {sweep_num})"
                            self.plot_data(voltage, current, label, ax1, ax2)
                        except: pass

            if len(ax1.get_lines()) > 0:
                ax1.legend(fontsize='x-small')
            if len(ax2.get_lines()) > 0:
                ax2.legend(fontsize='x-small')
            
            try:
                fig.savefig(voltage_dir / f'voltage_{voltage_value}V_combined.png')
            except Exception:
                pass
            # No plt.close() needed

    def get_main_sweeps_stats(self):
        device_stats = {}
        main_sweep_data = {}

        for device in self.device_folders:
            try:
                device_num = int(device.name)
                test_type = self.detect_test_type(device)
                if test_type:
                    # Find minimum sweep number for this code_name (treat as first measurement)
                    min_sweep = self._find_min_sweep_for_code_name(device, test_type)
                    if min_sweep is not None:
                        # Find files with this sweep number and matching code_name
                        sweep_files = list(device.glob(f'{min_sweep}-*.txt'))
                        sweep_files = [f for f in sweep_files if f.name != 'log.txt']
                        
                        # Filter to only files with matching code_name
                        matching_files = []
                        for f in sweep_files:
                            try:
                                parts = f.name.replace('.txt', '').split('-')
                                if len(parts) > 6 and parts[6] == test_type:
                                    matching_files.append(f)
                            except (ValueError, IndexError):
                                continue
                        
                        if matching_files:
                            # check_working_device finds min_sweep itself based on test_type
                            working_device = self.check_working_device(device, test_type)
                            if working_device:
                                voltage, current, _ = self.read_data_file(matching_files[0])
                                if voltage is not None:
                                    main_sweep_data[device_num] = {
                                        'voltage': voltage,
                                        'current': current,
                                        'test_type': test_type
                                    }
                                    
                                    if AnalyzeSingleFile is not None:
                                        try:
                                            # Re-instantiate AnalyzeSingleFile properly
                                            # Assuming it takes voltage, current arrays
                                            sfm = AnalyzeSingleFile(voltage, current)
                                            # Check if it has get_summary_stats or similar
                                            if hasattr(sfm, 'get_summary_stats'):
                                                device_stats[device_num] = sfm.get_summary_stats()
                                            elif hasattr(sfm, 'analyze_iv_curve'):
                                                # Fallback if method name is different
                                                device_stats[device_num] = sfm.analyze_iv_curve(0) # 0 is placeholder
                                        except Exception:
                                            pass
            except Exception:
                continue
        return device_stats, main_sweep_data

    def plot_statistical_comparisons(self, device_stats, main_sweep_data, stats_dir):
        try:
            # 1. Main Sweep Comparison
            if main_sweep_data:
                fig = Figure(figsize=(12, 12))
                FigureCanvasAgg(fig)
                ax1 = fig.add_subplot(211)
                ax2 = fig.add_subplot(212)
                fig.suptitle(f'Main Sweep Comparison - Section {self.section}')
                
                for device_num, data in main_sweep_data.items():
                    label = f"Device {device_num} ({data['test_type']})"
                    ax1.plot(data['voltage'], data['current'], label=label)
                    ax2.semilogy(data['voltage'], np.abs(data['current']), label=label)
                
                ax1.set_ylabel('Current (A)')
                ax2.set_ylabel('|Current| (A)')
                ax1.grid(True)
                ax2.grid(True)
                if len(ax1.get_lines()) > 0: ax1.legend(fontsize='x-small')
                if len(ax2.get_lines()) > 0: ax2.legend(fontsize='x-small')
                
                fig.tight_layout()
                fig.savefig(stats_dir / 'main_sweeps_comparison.png')

            # 2. Key Metrics Comparisons (Bar Plots)
            metrics = [
                ('mean_ron', 'Mean Ron'),
                ('mean_roff', 'Mean Roff'),
                ('mean_on_off_ratio', 'Mean On/Off Ratio'),
                ('avg_normalized_area', 'Average Normalized Area'),
                ('mean_r_02V', 'Mean R at 0.2V'),
                ('mean_r_05V', 'Mean R at 0.5V'),
                ('total_area', 'Total Area'),
                ('max_current', 'Maximum Current'),
                ('max_voltage', 'Maximum Voltage'),
                ('num_loops', 'Number of Loops')
            ]
            
            for key, label in metrics:
                devices = []
                values = []
                for d_num, stats in device_stats.items():
                    if key in stats and stats[key] is not None:
                        devices.append(d_num)
                        values.append(stats[key])
                
                if devices:
                    fig = Figure(figsize=(10, 6))
                    FigureCanvasAgg(fig)
                    ax = fig.add_subplot(111)
                    
                    ax.bar(devices, values)
                    ax.set_title(f'{label} Comparison - Section {self.section}')
                    ax.set_xlabel('Device Number')
                    ax.set_ylabel(label)
                    if any(v > 0 for v in values) and ('ratio' in key.lower() or 'mean_r' in key.lower()):
                        ax.set_yscale('log')
                    fig.tight_layout()
                    fig.savefig(stats_dir / f'{key}_comparison.png')

        except Exception as e:
            print(f"Error plotting stats: {e}")
