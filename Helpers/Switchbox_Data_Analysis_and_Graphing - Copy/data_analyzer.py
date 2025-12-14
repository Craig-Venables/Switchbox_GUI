"""
Section-level data analyzer for memristor device measurements.

This module provides classes for analyzing sections of a sample/substrate,
including sweep categorization, plotting, statistical analysis, and
device-level characterization. Designed to work with predesigned sweep
configurations and integrate into larger analysis systems.
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import json
import seaborn as sns
from functools import lru_cache
from typing import Tuple, Optional, Dict, List

# Import single file analyzer if available
AnalyzeSingleFile = None
try:
    from single_file_metrics import analyze_single_file as AnalyzeSingleFile
except ImportError:
    AnalyzeSingleFile = None


class TestTypeAnalyzer:
    """
    Analyzes and manages test type configurations from JSON files.
    
    Loads sweep combinations, main sweeps, and plot customizations for
    different test types (e.g., St_v1, St_v2, etc.) from a configuration file.
    """
    
    def __init__(self, config_path='test_configurations.json'):
        """
        Initialize the test type analyzer.
        
        Parameters:
        -----------
        config_path : str or Path, optional
            Path to the JSON configuration file. Defaults to 'test_configurations.json'
            in the current working directory.
        """
        self.config_path = Path(config_path)
        self.test_configs = {}
        self.load_test_configurations()

    def load_test_configurations(self):
        """
        Load test configurations from JSON file.
        
        The configuration file should contain test types as keys, each with:
        - 'sweep_combinations': List of sweep combinations (dicts with 'sweeps' and 'title')
        - 'main_sweep': Integer indicating the main sweep number for this test type
        """
        try:
            with open(self.config_path, 'r') as f:
                self.test_configs = json.load(f)
        except FileNotFoundError:
            print(f"Configuration file not found at {self.config_path}. Using empty configurations.")
            self.test_configs = {}
        except json.JSONDecodeError as e:
            print(f"Error parsing configuration file: {e}. Using empty configurations.")
            self.test_configs = {}

    def get_sweep_combinations(self, test_type):
        """
        Get sweep combinations for a specific test type.
        
        Parameters:
        -----------
        test_type : str
            Test type identifier (e.g., 'St_v1', 'St_v2')
            
        Returns:
        --------
        list
            List of sweep number lists. Each inner list contains sweep numbers
            that should be plotted together.
        """
        if test_type in self.test_configs:
            combinations = self.test_configs[test_type].get('sweep_combinations', [])
            # Support both new format (list of dicts) and old format (list of lists)
            if combinations and isinstance(combinations[0], dict):
                return [combo['sweeps'] for combo in combinations]
            return combinations
        return []

    def get_sweep_titles(self, test_type):
        """
        Get titles for sweep combinations of a specific test type.
        
        Parameters:
        -----------
        test_type : str
            Test type identifier
            
        Returns:
        --------
        list
            List of title strings corresponding to each sweep combination
        """
        if test_type in self.test_configs:
            combinations = self.test_configs[test_type].get('sweep_combinations', [])
            if combinations and isinstance(combinations[0], dict):
                return [combo.get('title', f"Combination {i+1}") for i, combo in enumerate(combinations)]
            # If using old format, generate generic titles
            return [f"Combination {i + 1}" for i in range(len(combinations))]
        return []

    def get_sweep_info(self, test_type):
        """
        Get complete sweep information (combinations and titles) for a test type.
        
        Parameters:
        -----------
        test_type : str
            Test type identifier
            
        Returns:
        --------
        list
            List of dictionaries with 'sweeps' and 'title' keys
        """
        if test_type in self.test_configs:
            combinations = self.test_configs[test_type].get('sweep_combinations', [])
            if combinations and isinstance(combinations[0], dict):
                return combinations
            # If using old format, create dictionary structure
            return [{'sweeps': combo, 'title': f"Combination {i + 1}"}
                    for i, combo in enumerate(combinations)]
        return []

    def get_main_sweep(self, test_type):
        """
        Get main sweep number for a specific test type.
        
        The main sweep is typically used for device characterization and statistics.
        
        Parameters:
        -----------
        test_type : str
            Test type identifier
            
        Returns:
        --------
        int or None
            Main sweep number, or None if test type not found
        """
        if test_type in self.test_configs:
            return self.test_configs[test_type].get('main_sweep')
        return None

    def plot_customization(self, test_type, ax1, ax2):
        """
        Apply test-specific plot customizations.
        
        Parameters:
        -----------
        test_type : str
            Test type identifier
        ax1 : matplotlib.axes.Axes
            Linear scale axes
        ax2 : matplotlib.axes.Axes
            Logarithmic scale axes
        """
        if test_type == 'St_v1':
            ax1.set_title('Standard V1 Test')
            ax2.set_title('Standard V1 Test (Log Scale)')
        elif test_type == 'Dy_v1':
            ax1.set_title('Dynamic V1 Test')
            ax2.set_title('Dynamic V1 Test (Log Scale)')
            ax1.set_ylim(-1e-3, 1e-3)


class DataAnalyzer:
    """
    Analyzes a section of a sample/substrate for memristor device measurements.
    
    This class handles:
    - Sweep categorization by type and voltage
    - Plotting sweeps in various groupings
    - Statistical analysis and device characterization
    - Generation of comprehensive reports and visualizations
    
    Designed to work with predesigned sweep configurations and integrate
    into larger analysis pipelines.
    """
    
    def __init__(self, top_level_path, section, sample_name, config_path='test_configurations.json'):
        """
        Initialize the section data analyzer.
        
        Parameters:
        -----------
        top_level_path : str or Path
            Root directory containing sample data
        section : str
            Section identifier (e.g., 'A', 'B', 'D')
        sample_name : str
            Name of the sample/substrate
        config_path : str or Path, optional
            Path to test configuration JSON file. Defaults to 'test_configurations.json'
        """
        self.top_level_path = Path(top_level_path)
        self.test_analyzer = TestTypeAnalyzer(config_path)
        self.section_path = self.top_level_path / sample_name / section
        self.sample_name = sample_name
        self.section = section

        # Initialize data structures
        self.working_device_list = []
        self.sweeps_by_type = {}
        self.sweeps_by_voltage = {}
        self.device_list_with_type_and_status = {}

        # Get device folders (numbered 1-9)
        self.device_folders = [d for d in self.section_path.glob('[1-9]*') if d.is_dir()]

        # Detect test type and working status for each device
        for device in self.device_folders:
            test_type = self.detect_test_type(device)
            main_sweep = self.test_analyzer.get_main_sweep(test_type) if test_type else None
            working_device = self.check_working_device(device, main_sweep) if main_sweep else False
            self.device_list_with_type_and_status[device] = (test_type, working_device, main_sweep)




    @lru_cache(maxsize=128)
    def read_data_file(self, file_path) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Read measurement data from a text file.
        
        Expected file format:
        - First line: header (skipped)
        - Subsequent lines: voltage, current, [time]
        
        Parameters:
        -----------
        file_path : str or Path
            Path to the data file
            
        Returns:
        --------
        tuple
            (voltage, current, time) arrays. time may be None if not present.
            Returns (None, None, None) on error.
        """
        try:
            data = np.loadtxt(file_path, skiprows=1)
            v = data[:, 0]
            i = data[:, 1]
            t = data[:, 2] if data.ndim == 2 and data.shape[1] > 2 else None
            return v, i, t
        except Exception as e:
            print(f"Error reading file {file_path}: {str(e)}")
            return None, None, None

    def parse_filename(self, filename):
        """
        Parse sweep file filename to extract metadata.
        
        Expected format: <sweep_num>-<sweep_type>-<voltage>v-<step_voltage>sv-<step_delay>sd-<...>-<test_type>-<num_sweeps>
        Example: "1-FS-0.5v-0.05sv-0.05sd-Py-St_v1-3"
        
        Parameters:
        -----------
        filename : str
            Filename to parse
            
        Returns:
        --------
        dict or None
            Dictionary with keys: sweep_num, sweep_type, voltage, step_voltage,
            step_delay, test_type, num_sweeps. Returns None on error.
        """
        try:
            # Remove the .txt extension first
            filename = filename.replace('.txt', '')
            # Split by '-' since that's now the main delimiter
            parts = filename.split('-')

            return {
                'sweep_num': int(parts[0]),
                'sweep_type': parts[1],
                'voltage': float(parts[2].replace('v', '')),
                'step_voltage': float(parts[3].replace('sv', '')),
                'step_delay': float(parts[4].replace('sd', '')),
                'test_type': parts[6],  # St_v1 is now in position 6
                'num_sweeps': int(parts[7])  # Last number is in position 7
            }
        except (IndexError, ValueError) as e:
            print(f"Error parsing filename {filename}: {str(e)}")
            return None

    def detect_test_type(self, device_path):
        """
        Detect test type from the first sweep file in a device directory.
        
        Parameters:
        -----------
        device_path : Path
            Path to the device directory
            
        Returns:
        --------
        str or None
            Test type identifier (e.g., 'St_v1'), or None if not found
        """
        first_sweep = list(device_path.glob('1-*.txt'))
        first_sweep = [f for f in first_sweep if f.name != 'log.txt']
        if not first_sweep:
            return None

        filename = first_sweep[0].name
        parts = filename.split('-')
        try:
            # Test type is in position 6 (0-based index)
            test_type = parts[6]
            return test_type
        except (IndexError, AttributeError):
            print(f"Could not extract test type from filename: {filename}")
            return None

    def create_subplot(self, title):
        """
        Create a figure with two subplots (linear and logarithmic scales).
        
        Parameters:
        -----------
        title : str
            Figure title
            
        Returns:
        --------
        tuple
            (figure, linear_axes, log_axes)
        """
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        fig.suptitle(title)
        ax2.set_yscale('log')
        return fig, ax1, ax2

    def plot_data(self, voltage, current, label, ax1, ax2):
        """
        Plot I-V data on both linear and logarithmic axes.
        
        Parameters:
        -----------
        voltage : array-like
            Voltage data
        current : array-like
            Current data
        label : str
            Label for the plot legend
        ax1 : matplotlib.axes.Axes
            Linear scale axes
        ax2 : matplotlib.axes.Axes
            Logarithmic scale axes
        """
        if voltage is not None and current is not None and len(voltage) > 0:
            ax1.plot(voltage, current, 'o-', label=label, markersize=2)
            ax2.plot(voltage, np.abs(current), 'o-', label=label, markersize=2)
            ax1.set_xlabel('Voltage (V)')
            ax1.set_ylabel('Current (A)')
            ax2.set_xlabel('Voltage (V)')
            ax2.set_ylabel('|Current| (A)')

            if len(ax1.get_lines()) > 0:
                ax1.legend()
            if len(ax2.get_lines()) > 0:
                ax2.legend()

    def analyze_section_sweeps(self, substrate, section, quality_metrics):
        """
        Perform comprehensive analysis of all sweeps in a section.
        
        This is the main analysis method that:
        1. Categorizes sweeps by type and voltage
        2. Generates plots grouped by type and voltage
        3. Extracts device statistics from main sweeps
        4. Creates statistical comparisons and visualizations
        5. Calculates section-level quality metrics
        
        Parameters:
        -----------
        substrate : str
            Sample/substrate name (should match self.sample_name)
        section : str
            Section identifier (should match self.section)
        quality_metrics : dict
            Dictionary to update with quality metrics (modified in-place)
            
        Returns:
        --------
        tuple
            (device_stats, metrics, quality_metrics)
            - device_stats: dict of device statistics keyed by device number
            - metrics: dict of section-level metrics
            - quality_metrics: updated quality metrics dictionary
        """
        section_path = self.top_level_path / substrate / section

        metrics = {
            'devices': [],
            'sweep1_current_range': [],
            'resistance_uniformity': [],
            'device_consistency': [],
            'working_devices': 0,
            'resistance_at_0_2V': [],
            'resistance_at_0_5V': []
        }

        # Create output directories
        plots_dir = section_path / 'plots_combined'
        plots_dir.mkdir(exist_ok=True)
        stats_dir = plots_dir / 'statistics'
        stats_dir.mkdir(exist_ok=True)

        # First pass: Categorize all sweeps by their type and voltage
        self.catogrize_sweeps_by_type_and_voltage()

        # Second pass: Plot sweeps by type
        self.plot_sweeps_by_type(plots_dir)

        # Third pass: Plot sweeps by voltage
        self.plot_Sweeps_by_voltage(plots_dir)

        # Fourth pass: get main sweep stats
        device_stats, main_sweep_data = self.get_main_sweeps_stats()

        # Export device_stats to CSV for traceability
        try:
            if device_stats:
                import pandas as _pd
                _df = _pd.DataFrame.from_dict(device_stats, orient='index')
                _df.index.name = 'device_number'
                _df.to_csv(stats_dir / 'device_stats.csv')
        except Exception:
            pass

        # plot statistical information
        self.plot_statistical_comparisons(device_stats, main_sweep_data, stats_dir)

        # Enhanced analytics and visuals per section
        try:
            self.generate_violin_and_box_plots(device_stats, stats_dir)
            self.generate_pairplot(device_stats, stats_dir)
            self.export_correlation_csv(device_stats, stats_dir)
            self.generate_device_leaderboard(device_stats, stats_dir)
            self.generate_section_summary_pdf(stats_dir)
        except Exception:
            pass

        # Analyze first sweep of each device and calculate section metrics
        metrics, quality_metrics = self.calculate_section_metrics(quality_metrics, metrics)

        # Augment quality metrics with memristive yield from device_stats if available
        try:
            if device_stats is not None:
                memristive_count = sum(1 for d, s in device_stats.items() if s.get('device_type') == 'memristive')
                total_devices = len(device_stats) if device_stats else 0
                yield_pct = (memristive_count / total_devices) * 100 if total_devices > 0 else 0
                key = f"{substrate}_{section}"
                if key in quality_metrics:
                    quality_metrics[key]['memristive_yield_pct'] = yield_pct
                    quality_metrics[key]['memristive_count'] = memristive_count
                    quality_metrics[key]['devices_counted'] = total_devices
        except Exception:
            pass


        return device_stats,metrics,quality_metrics

    def generate_violin_and_box_plots(self, device_stats, stats_dir):
        """
        Generate violin and box plots for key device metrics.
        
        Parameters:
        -----------
        device_stats : dict
            Dictionary of device statistics keyed by device number
        stats_dir : Path
            Directory where plots will be saved
        """
        import pandas as _pd
        if not device_stats:
            return
        df = _pd.DataFrame.from_dict(device_stats, orient='index')
        df_num = df.select_dtypes(include=['number']).dropna(axis=1, how='all')
        if df_num.empty:
            return
        candidates = ['mean_ron','mean_roff','mean_on_off_ratio','avg_normalized_area','mean_r_02V','mean_r_05V']
        cols = [c for c in candidates if c in df_num.columns]
        if not cols:
            return
        df_melt = df_num[cols].reset_index(names='device').melt(id_vars='device', var_name='metric', value_name='value')
        plt.figure(figsize=(12, 6))
        sns.violinplot(data=df_melt, x='metric', y='value', inner='box', scale='width')
        plt.xticks(rotation=45)
        plt.title(f'Violin plots across devices - Section {self.section}')
        plt.tight_layout()
        plt.savefig(stats_dir / 'violin_plots.png')
        plt.close()

        plt.figure(figsize=(12, 6))
        sns.boxplot(data=df_melt, x='metric', y='value')
        plt.xticks(rotation=45)
        plt.title(f'Box plots across devices - Section {self.section}')
        plt.tight_layout()
        plt.savefig(stats_dir / 'box_plots.png')
        plt.close()

    def generate_pairplot(self, device_stats, stats_dir):
        """
        Generate pairplot showing relationships between key metrics.
        
        Parameters:
        -----------
        device_stats : dict
            Dictionary of device statistics keyed by device number
        stats_dir : Path
            Directory where plot will be saved
        """
        import pandas as _pd
        if not device_stats:
            return
        df = _pd.DataFrame.from_dict(device_stats, orient='index')
        df_num = df.select_dtypes(include=['number']).dropna(axis=1, how='all')
        candidates = ['mean_ron','mean_roff','mean_on_off_ratio','avg_normalized_area','max_current','max_voltage']
        cols = [c for c in candidates if c in df_num.columns]
        if len(cols) < 2:
            return
        g = sns.pairplot(df_num[cols], corner=True, diag_kind='kde')
        g.fig.suptitle(f'Pairplot of key metrics - Section {self.section}', y=1.02)
        g.savefig(stats_dir / 'pairplot.png')
        plt.close('all')

    def export_correlation_csv(self, device_stats, stats_dir):
        """
        Export correlation matrix of device metrics to CSV.
        
        Parameters:
        -----------
        device_stats : dict
            Dictionary of device statistics keyed by device number
        stats_dir : Path
            Directory where CSV will be saved
        """
        import pandas as _pd
        if not device_stats:
            return
        df = _pd.DataFrame.from_dict(device_stats, orient='index')
        df_num = df.select_dtypes(include=['number']).dropna(axis=1, how='all')
        if df_num.empty:
            return
        corr = df_num.corr()
        corr.to_csv(stats_dir / 'correlation_matrix.csv')

    def generate_device_leaderboard(self, device_stats, stats_dir):
        """
        Generate device leaderboard ranked by performance score.
        
        Score is calculated from:
        - ON/OFF ratio (40% weight)
        - Ron (20% weight)
        - Retention score (20% weight)
        - Endurance score (20% weight)
        
        Parameters:
        -----------
        device_stats : dict
            Dictionary of device statistics keyed by device number
        stats_dir : Path
            Directory where CSV will be saved
        """
        import pandas as _pd
        if not device_stats:
            return
        df = _pd.DataFrame.from_dict(device_stats, orient='index')
        df['_score'] = 0.0
        if 'mean_on_off_ratio' in df:
            s = df['mean_on_off_ratio'].astype(float)
            df['_score'] += (s / (s.max() + 1e-12)) * 40
        if 'mean_ron' in df:
            s = df['mean_ron'].astype(float)
            inv = (s.max() - s) / (s.max() - s.min() + 1e-12)
            df['_score'] += inv * 20
        if 'retention_score' in df:
            df['_score'] += df['retention_score'].astype(float) * 20
        if 'endurance_score' in df:
            df['_score'] += df['endurance_score'].astype(float) * 20
        leaderboard = df.sort_values('_score', ascending=False).reset_index().rename(columns={'index':'device_number'})
        keep_cols = [c for c in ['device_number','_score','mean_on_off_ratio','mean_ron','retention_score','endurance_score','device_type'] if c in leaderboard.columns]
        leaderboard[keep_cols].to_csv(stats_dir / 'device_leaderboard.csv', index=False)

    def generate_section_summary_pdf(self, stats_dir):
        """
        Generate a PDF summary document bundling all section visualizations.
        
        Parameters:
        -----------
        stats_dir : Path
            Directory containing plots and where PDF will be saved
        """
        from matplotlib.backends.backend_pdf import PdfPages
        import matplotlib.image as mpimg
        report_path = stats_dir / 'section_summary.pdf'
        with PdfPages(report_path) as pdf:
            def add_image_if_exists(image_path, title=None):
                try:
                    if image_path.exists():
                        img = mpimg.imread(image_path)
                        fig, ax = plt.subplots(figsize=(11, 8.5))
                        ax.imshow(img)
                        ax.axis('off')
                        if title:
                            fig.suptitle(title)
                        pdf.savefig(fig)
                        plt.close(fig)
                except Exception:
                    plt.close('all')

            # Title page
            fig, ax = plt.subplots(figsize=(11, 8.5))
            ax.axis('off')
            fig.suptitle(f'Section {self.section} Summary', fontsize=18)
            pdf.savefig(fig)
            plt.close(fig)

            # Include key generated plots
            add_image_if_exists(stats_dir / 'main_sweeps_comparison.png', 'Main Sweeps Comparison')
            # Metric comparisons
            metric_plots = ['mean_ron','mean_roff','mean_on_off_ratio','avg_normalized_area','mean_r_02V','mean_r_05V','total_area','max_current','max_voltage','num_loops']
            for m in metric_plots:
                add_image_if_exists(stats_dir / f'{m}_comparison.png', f'{m} Comparison')
            # Correlation, violin/box, pairplot
            add_image_if_exists(stats_dir / 'correlation_matrix.png', 'Correlation Matrix')
            add_image_if_exists(stats_dir / 'violin_plots.png', 'Violin Plots')
            add_image_if_exists(stats_dir / 'box_plots.png', 'Box Plots')
            add_image_if_exists(stats_dir / 'pairplot.png', 'Pairplot')

    def analyze_single_device(self, sample_name, section, device_num):
        """
        Analyze and plot data for a single device.
        
        Generates plots for:
        - Sweep combinations (as defined in test configuration)
        - Individual sweeps not part of combinations
        
        Parameters:
        -----------
        sample_name : str
            Name of the sample/substrate
        section : str
            Section identifier
        device_num : int
            Device number (1-9)
        """
        device_path = self.top_level_path / sample_name / section / str(device_num)
        images_dir = device_path / 'images'
        images_dir.mkdir(exist_ok=True)

        # Detect test type
        test_type = self.detect_test_type(device_path)
        if not test_type:
            print(f"Could not determine test type for {device_path}")
            return

        # Get sweep combinations for this test type
        sweep_combinations = self.test_analyzer.get_sweep_combinations(test_type)
        sweep_titles = self.test_analyzer.get_sweep_titles(test_type)
        main_sweep = self.test_analyzer.get_main_sweep(test_type)

        # Process each combination
        for idx, combo in enumerate(sweep_combinations):
            # Get the corresponding title for this combination
            combo_title = sweep_titles[idx]

            fig, ax1, ax2 = self.create_subplot(
                f"{sample_name} {section}{device_num} {test_type} - {combo_title}")

            # Apply test-specific plot customizations
            self.test_analyzer.plot_customization(test_type, ax1, ax2)

            for sweep_num in combo:
                sweep_files = list(device_path.glob(f'{sweep_num}-*.txt'))
                sweep_files = [f for f in sweep_files if f.name != 'log.txt']
                if sweep_files:
                    voltage, current, _ = self.read_data_file(sweep_files[0])
                    if voltage is not None:
                        file_info = self.parse_filename(sweep_files[0].name)
                        if file_info:
                            label = f"Sweep {sweep_num}"
                            if len(combo) >= 3:
                                label += f" (V={file_info['voltage']}, SD={file_info['step_delay']})"
                            self.plot_data(voltage, current, label, ax1, ax2)

            ax1.legend()
            ax2.legend()
            # Use the combo_title in the filename (make it filesystem-friendly)
            safe_title = combo_title.replace(" ", "_").replace("/", "-")
            plt.savefig(images_dir / f'{combo} - {safe_title}_sweeps_.png')

            plt.close()

        # Plot individual sweeps

        all_files = list(device_path.glob('*.txt'))
        all_files = [f for f in all_files if f.name != 'log.txt']
        for file in all_files:
            sweep_num = int(file.name.split('-')[0])

            # plots together
            if sweep_num in [20, 21, 22, 23] or not any(sweep_num in combo for combo in sweep_combinations):
                fig, ax1, ax2 = self.create_subplot(
                    f"{sample_name} {section}{device_num} {test_type} sweep {sweep_num}")
                voltage, current, _ = self.read_data_file(file)
                if voltage is not None:
                    self.plot_data(voltage, current, f"Sweep {sweep_num}", ax1, ax2)
                ax1.legend()
                ax2.legend()
                plt.savefig(images_dir / f'sweep_{sweep_num}.png')
                plt.close()

    def check_working_device(self, device_path, main_sweep):
        """
        Check if a device is working based on current threshold.
        
        A device is considered working if the maximum absolute current in the
        main sweep exceeds 1E-9 A (noise threshold).
        
        Parameters:
        -----------
        device_path : Path
            Path to device directory
        main_sweep : int
            Main sweep number to check
            
        Returns:
        --------
        bool
            True if device is working (current > 1E-9 A), False otherwise
        """
        sweep_files = list(device_path.glob(f'{main_sweep}-*.txt'))
        sweep_files = [f for f in sweep_files if f.name != 'log.txt']

        if sweep_files:
            voltage, current, _ = self.read_data_file(sweep_files[0])
            if current is not None and len(current) > 0:
                # Check if maximum absolute current is below threshold
                max_current = max(abs(float(i)) for i in current)
                if max_current < 1E-9:
                    return False
                return True
        # Return False if no files found or current data is empty
        return False

    def catogrize_sweeps_by_type_and_voltage(self):
        """
        Categorize all sweeps in the section by test type and voltage.
        
        Populates self.sweeps_by_type and self.sweeps_by_voltage dictionaries
        for later plotting and analysis. Handles errors gracefully to allow
        processing to continue even if some files are malformed.
        """
        try:
            for device in self.device_folders:
                try:
                    files = list(device.glob('*.txt'))
                    # Detect test type
                    test_type = self.detect_test_type(device)

                    for file in files:
                        try:
                            if file.name == 'log.txt':
                                continue

                            # Parse filename
                            parts = file.name.split('-')
                            sweep_num = int(parts[0])

                            # Extract voltage from filename
                            # Assuming format like "1-FS-0.5v-0.05sv-0.05sd-Py-St_v1-3..."
                            voltage_part = next(
                                (part for part in parts if 'v' in part.lower() and any(c.isdigit() for c in part)),
                                None)
                            voltage_value = None
                            if voltage_part:
                                voltage_value = voltage_part.lower().replace('v', '')

                            if test_type:
                                # Store by test type
                                if test_type not in self.sweeps_by_type:
                                    self.sweeps_by_type[test_type] = {}
                                if sweep_num not in self.sweeps_by_type[test_type]:
                                    self.sweeps_by_type[test_type][sweep_num] = []
                                self.sweeps_by_type[test_type][sweep_num].append((device, file))

                                # Store by voltage
                                if voltage_value:
                                    if voltage_value not in self.sweeps_by_voltage:
                                        self.sweeps_by_voltage[voltage_value] = []
                                    self.sweeps_by_voltage[voltage_value].append((device, file, test_type))
                        except Exception as e:
                            print(f"Error processing file {file} in device {device}: {str(e)}")
                            continue  # Skip this file but continue with others
                except Exception as e:
                    print(f"Error processing device {device}: {str(e)}")
                    continue  # Skip this device but continue with others
        except Exception as e:
            print(f"Error in catogrize_sweeps_by_type_and_voltage: {str(e)}")
            import traceback
            traceback.print_exc()

            # Create error log
            log_path = self.section_path / "categorize_error_log.txt"
            with open(log_path, 'w') as f:
                f.write(f"Error occurred while categorizing sweeps for section {self.section}\n")
                f.write(f"Error: {str(e)}\n")
                f.write(f"Traceback: {traceback.format_exc()}")

    def plot_sweeps_by_type(self, plots_dir):
        """
        Plot sweeps grouped by test type.
        
        Creates plots for each test type and sweep number, showing all devices
        in the section overlaid on the same plot.
        
        Parameters:
        -----------
        plots_dir : Path
            Directory where plots will be saved
        """
        for test_type, sweeps in self.sweeps_by_type.items():
            # Create a directory for this test type
            test_type_dir = plots_dir / test_type
            test_type_dir.mkdir(exist_ok=True)

            # Plot each sweep number for this test type
            for sweep_num in sweeps.keys():
                fig, ax1, ax2 = self.create_subplot(
                    f"{self.sample_name} section {self.section} {test_type} sweep {sweep_num} combined")

                # Apply test-specific plot customizations
                self.test_analyzer.plot_customization(test_type, ax1, ax2)

                # Plot all devices for this sweep number and test type
                for device, sweep_file in sweeps[sweep_num]:
                    voltage, current, _ = self.read_data_file(sweep_file)
                    if voltage is not None:
                        label = f"{self.section}{device.name} (Sweep {sweep_num})"
                        self.plot_data(voltage, current, label, ax1, ax2)

                ax1.legend()
                ax2.legend()
                plt.savefig(test_type_dir / f'sweep_{sweep_num}_combined.png')
                plt.close()

    def plot_Sweeps_by_voltage(self, plots_dir):
        """
        Plot sweeps grouped by voltage value.
        
        Creates plots for each voltage value, showing all devices and test types
        overlaid on the same plot.
        
        Parameters:
        -----------
        plots_dir : Path
            Directory where plots will be saved
        """
        voltage_dir = plots_dir / 'voltage_groups'

        voltage_dir.mkdir(exist_ok=True)
        for voltage_value, sweeps in self.sweeps_by_voltage.items():
            fig, ax1, ax2 = self.create_subplot(
                f"{self.sample_name} section {self.section} {voltage_value}V combined")

            # Group sweeps by test type for legend organization
            sweeps_by_test = {}
            for device, sweep_file, test_type in sweeps:
                if test_type not in sweeps_by_test:
                    sweeps_by_test[test_type] = []
                sweeps_by_test[test_type].append((device, sweep_file))

            # Plot each test type with different colors/styles
            for test_type, test_sweeps in sweeps_by_test.items():
                # Apply test-specific plot customizations
                self.test_analyzer.plot_customization(test_type, ax1, ax2)

                for device, sweep_file in test_sweeps:
                    voltage, current, _ = self.read_data_file(sweep_file)
                    if voltage is not None:
                        sweep_num = int(sweep_file.name.split('-')[0])
                        label = f"{self.section}{device.name} {test_type} (Sweep {sweep_num})"
                        self.plot_data(voltage, current, label, ax1, ax2)

            ax1.legend()
            ax2.legend()
            plt.savefig(voltage_dir / f'voltage_{voltage_value}V_combined.png')
            plt.close()

    def get_main_sweeps_stats(self):
        """
        Extract statistics from main sweeps for all working devices.
        
        Returns:
        --------
        tuple
            (device_stats, main_sweep_data)
            - device_stats: dict of device statistics keyed by device number
            - main_sweep_data: dict of main sweep voltage/current data keyed by device number
        """
        # Collect stats and main sweeps
        device_stats = {}
        main_sweep_data = {}

        for device in self.device_folders:
            device_num = int(device.name)
            test_type = self.detect_test_type(device)
            if test_type:
                main_sweep = self.test_analyzer.get_main_sweep(test_type)
                main_sweep_files = list(device.glob(f'{main_sweep}-*.txt'))
                if main_sweep_files:
                    working_device = self.check_working_device(device, main_sweep)
                    if working_device:
                        # Store main sweep data
                        voltage, current, _ = self.read_data_file(main_sweep_files[0])
                        if voltage is not None:
                            main_sweep_data[device_num] = {
                                'voltage': voltage,
                                'current': current,
                                'test_type': test_type
                            }

                            # Get and store device stats using single file analyzer
                            try:
                                if AnalyzeSingleFile is not None:
                                    sfm = AnalyzeSingleFile(voltage, current)
                                    device_stats[device_num] = sfm.get_summary_stats()
                                else:
                                    device_stats[device_num] = {}
                            except Exception:
                                device_stats[device_num] = {}
        return device_stats, main_sweep_data

    def plot_statistical_comparisons(self, device_stats, main_sweep_data, stats_dir):
        """
        Generate statistical comparison plots for device metrics.
        
        Creates:
        - Bar plots for individual metrics across devices
        - Main sweeps comparison overlay plot
        - Correlation matrix heatmap
        
        Parameters:
        -----------
        device_stats : dict
            Dictionary of device statistics keyed by device number
        main_sweep_data : dict
            Dictionary of main sweep data keyed by device number
        stats_dir : Path
            Directory where plots will be saved
        """
        try:
            stat_metrics = [
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

            for stat_key, stat_label in stat_metrics:
                device_numbers = sorted(device_stats.keys())
                raw_values = [device_stats.get(d, {}).get(stat_key) for d in device_numbers]

                # Remove None and non-finite values
                filtered = [(d, v) for d, v in zip(device_numbers, raw_values) if v is not None and np.isfinite(v)]
                if not filtered:
                    # Still output an empty plot placeholder to keep pipeline predictable
                    plt.figure(figsize=(10, 6))
                    plt.title(f'{stat_label} Comparison - Section {self.section} (no data)')
                    plt.xlabel('Device Number')
                    plt.ylabel(stat_label)
                    plt.tight_layout()
                    plt.savefig(stats_dir / f'{stat_key}_comparison.png')
                    plt.close()
                    continue

                # Separate devices and values
                devices, values = zip(*filtered)

                # Determine if we can use log scale (values must be > 0)
                positive = [max(float(v), 0.0) for v in values]
                use_log = all(v > 0 for v in positive)

                plt.figure(figsize=(10, 6))
                plt.bar(devices, [max(v, 1e-18) for v in positive])
                plt.title(f'{stat_label} Comparison - Section {self.section}')
                plt.xlabel('Device Number')
                plt.ylabel(stat_label)
                if use_log:
                    plt.yscale('log')
                plt.grid(True, alpha=0.3)
                plt.tight_layout()
                plt.savefig(stats_dir / f'{stat_key}_comparison.png')
                plt.close()

            # Plot main sweeps comparison
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 12))
            fig.suptitle(f'Main Sweep Comparison - Section {self.section}')

            # Group by test type for consistent coloring
            test_types = set(data['test_type'] for data in main_sweep_data.values())
            colors = plt.cm.get_cmap('tab10')(np.linspace(0, 1, len(test_types)))
            color_dict = dict(zip(test_types, colors))


            for device_num, data in main_sweep_data.items():
                color = color_dict[data['test_type']]
                label = f"Device {device_num} ({data['test_type']})"

                # Linear plot
                ax1.plot(data['voltage'], data['current'], label=label, color=color)
                ax1.set_xlabel('Voltage (V)')
                ax1.set_ylabel('Current (A)')
                ax1.grid(True)
                ax1.legend()

                # Semi-log plot
                ax2.semilogy(data['voltage'], np.abs(data['current']), label=label, color=color)
                ax2.set_xlabel('Voltage (V)')
                ax2.set_ylabel('|Current| (A)')
                ax2.grid(True)
                ax2.legend()

            plt.tight_layout()
            plt.savefig(stats_dir / 'main_sweeps_comparison.png')
            plt.close()

            # Create correlation matrix of statistics (metrics vs metrics across devices)
            import pandas as _pd
            if device_stats:
                df = _pd.DataFrame.from_dict(device_stats, orient='index')
                # Keep only numeric columns
                df_num = df.select_dtypes(include=['number']).copy()
                # Drop all-NaN columns
                df_num = df_num.dropna(axis=1, how='all')
                if not df_num.empty and df_num.shape[1] >= 2:
                    corr = df_num.corr()
                    plt.figure(figsize=(12, 10))
                    sns.heatmap(corr, annot=True, cmap='coolwarm')
                    plt.title(f'Correlation Matrix of Statistics - Section {self.section}')
                    plt.tight_layout()
                    plt.savefig(stats_dir / 'correlation_matrix.png')
                    plt.close()
        except Exception as e:
            print(f"Error in plot_statistical_comparisons for section {self.section}: {str(e)}")
            import traceback
            traceback.print_exc()

            # Close any open figures to prevent memory leaks
            plt.close('all')

            # Create a simple error report file
            with open(stats_dir / 'plot_error_log.txt', 'w') as f:
                f.write(f"Error occurred while plotting statistical comparisons for section {self.section}\n")
                f.write(f"Error: {str(e)}\n")
                f.write(f"Traceback: {traceback.format_exc()}")


    def calculate_section_metrics(self, quality_metrics, metrics):
        """
        Calculate section-level quality metrics from device measurements.
        
        Analyzes the first sweep of each device to compute:
        - Current range statistics
        - Resistance at specific voltage points (0.2V, 0.5V)
        - Working device count
        - Overall quality score
        
        Parameters:
        -----------
        quality_metrics : dict
            Dictionary to update with quality metrics (modified in-place)
        metrics : dict
            Dictionary to populate with device-level metrics
            
        Returns:
        --------
        tuple
            (metrics, quality_metrics) - both dictionaries updated
        """
        # Analyze first sweep of each device
        for device_num in range(1, 11):
            device_path = self.section_path / str(device_num)
            if device_path.exists():
                sweep1_files = list(device_path.glob('1-*.txt'))
                sweep1_files = [f for f in sweep1_files if f.name != 'log.txt']

                if sweep1_files:
                    voltage, current, _ = self.read_data_file(sweep1_files[0])
                    if voltage is not None and current is not None:
                        # Calculate original metrics
                        current_range = np.max(np.abs(current)) - np.min(np.abs(current))
                        resistance = np.mean(np.abs(voltage / current))
                        resistance = float(resistance) if np.isfinite(resistance) else None

                        # Calculate resistance at specific voltage points
                        def get_resistance_at_voltage(target_voltage):
                            # Find the closest voltage point
                            idx = np.abs(voltage - target_voltage).argmin()
                            if abs(voltage[idx] - target_voltage) < 0.01:  # Within 10mV
                                return abs(voltage[idx] / current[idx])
                            return None

                        r_0_2V = get_resistance_at_voltage(0.2)
                        r_0_5V = get_resistance_at_voltage(0.5)

                        # Optional enrichment via single-file analyzer (classification flags)
                        memristive_flag = None
                        classification_conf = None
                        try:
                            if AnalyzeSingleFile is not None:
                                sfa = AnalyzeSingleFile(voltage, current, analysis_level='classification')
                                if hasattr(sfa, 'get_classification_report'):
                                    rep = sfa.get_classification_report()
                                    memristive_flag = rep.get('device_type') == 'memristive'
                                    classification_conf = rep.get('confidence')
                        except Exception:
                            pass

                        metrics['devices'].append(device_num)
                        metrics['sweep1_current_range'].append(current_range)
                        metrics['resistance_uniformity'].append(resistance)
                        if r_0_2V is not None and np.isfinite(r_0_2V):
                            metrics['resistance_at_0_2V'].append(r_0_2V)
                        if r_0_5V is not None and np.isfinite(r_0_5V):
                            metrics['resistance_at_0_5V'].append(r_0_5V)

                        # Record optional quality annotations
                        if memristive_flag is not None:
                            key = f"{self.sample_name}_{self.section}"
                            quality_metrics.setdefault(key, {})
                            quality_metrics[key].setdefault('memristive_flags', {})
                            quality_metrics[key]['memristive_flags'][device_num] = bool(memristive_flag)
                            if classification_conf is not None:
                                quality_metrics[key].setdefault('memristive_confidence', {})
                                quality_metrics[key]['memristive_confidence'][device_num] = float(classification_conf)

                        # Check if device is working
                        if device_path in self.device_list_with_type_and_status:
                            result = self.device_list_with_type_and_status[device_path]
                            if result[1]:  # If the device is working
                                metrics['working_devices'] += 1

        # Calculate section-wide metrics
        # Combine each device's metrics into section-level statistics (mean and std)
        if metrics['devices']:
            quality_metrics[f"{self.sample_name}_{self.section}"] = {
                'working_devices': metrics['working_devices'],
                'current_range_std': np.std(metrics['sweep1_current_range']),
                'resistance_std': np.std(metrics['resistance_uniformity']),
                'resistance_0_2V_mean': np.mean(metrics['resistance_at_0_2V']) if metrics[
                    'resistance_at_0_2V'] else None,
                'resistance_0_2V_std': np.std(metrics['resistance_at_0_2V']) if metrics['resistance_at_0_2V'] else None,
                'resistance_0_5V_mean': np.mean(metrics['resistance_at_0_5V']) if metrics[
                    'resistance_at_0_5V'] else None,
                'resistance_0_5V_std': np.std(metrics['resistance_at_0_5V']) if metrics['resistance_at_0_5V'] else None,
                'overall_score': self.calculate_overall_score(metrics)
            }
        return metrics, quality_metrics

    def calculate_overall_score(self, metrics):
        """
        Calculate an overall quality score (0-100) for the section.
        
        Currently based solely on working device ratio. Can be extended
        to include current uniformity and resistance uniformity.
        
        Parameters:
        -----------
        metrics : dict
            Dictionary containing device metrics
            
        Returns:
        --------
        float
            Quality score from 0 to 100
        """
        if not metrics['devices']:
            return 0

        # Calculate working device ratio
        working_ratio = metrics['working_devices'] / 10

        # Score is currently based only on working device ratio
        score = (working_ratio * 100)

        return score


def main():
    """
    Example main function demonstrating usage of DataAnalyzer.
    
    This function should be customized for your specific use case.
    For integration into other systems, instantiate DataAnalyzer directly
    and call analyze_section_sweeps() with appropriate parameters.
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Analyze memristor section data'
    )
    parser.add_argument(
        'top_level_path',
        type=str,
        help='Root directory containing sample data'
    )
    parser.add_argument(
        'sample_name',
        type=str,
        help='Name of the sample/substrate'
    )
    parser.add_argument(
        'section',
        type=str,
        help='Section identifier (e.g., A, B, D)'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='test_configurations.json',
        help='Path to test configuration JSON file'
    )
    
    args = parser.parse_args()
    
    analyzer = DataAnalyzer(args.top_level_path, args.section, args.sample_name, args.config)
    quality_metrics = {}
    analyzer.analyze_section_sweeps(args.sample_name, args.section, quality_metrics)


if __name__ == "__main__":
    main()
