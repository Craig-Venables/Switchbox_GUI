"""
Section-level data analyzer for memristor device measurements.

Restored from Switchbox_Data_Analysis_and_Graphing/data_analyzer.py to provide:
1. Stacked sweep plots (first/second/third sweeps)
2. Statistical comparisons
3. Section-level summaries
"""

import numpy as np
import matplotlib
# Force Agg backend to prevent GUI resource allocation
matplotlib.use('Agg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from pathlib import Path
import json
import seaborn as sns
from functools import lru_cache
from typing import Tuple, Optional, Dict, List
import os

# Import single file analyzer
try:
    from Helpers.IV_Analysis.single_file_metrics import analyze_single_file as AnalyzeSingleFile
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
            main_sweep = self.test_analyzer.get_main_sweep(test_type) if test_type else None
            working_device = self.check_working_device(device, main_sweep) if main_sweep else False
            self.device_list_with_type_and_status[device] = (test_type, working_device, main_sweep)

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

    def check_working_device(self, device_path, main_sweep):
        sweep_files = list(device_path.glob(f'{main_sweep}-*.txt'))
        sweep_files = [f for f in sweep_files if f.name != 'log.txt']
        if sweep_files:
            voltage, current, _ = self.read_data_file(sweep_files[0])
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
                    main_sweep = self.test_analyzer.get_main_sweep(test_type)
                    if main_sweep:
                        main_sweep_files = list(device.glob(f'{main_sweep}-*.txt'))
                        main_sweep_files = [f for f in main_sweep_files if f.name != 'log.txt']
                        
                        if main_sweep_files:
                            working_device = self.check_working_device(device, main_sweep)
                            if working_device:
                                voltage, current, _ = self.read_data_file(main_sweep_files[0])
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
