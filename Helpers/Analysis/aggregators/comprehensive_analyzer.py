"""
Comprehensive Analysis Orchestrator
===================================

Purpose:
--------
One-stop orchestrator for comprehensive sample analysis. This module coordinates
all levels of analysis (device, section, and sample) into a single unified workflow.
Called by the "Run Full Sample Analysis" button in the Measurement GUI.

What This Module Does:
----------------------
1. Discovers all code_names (test types) from measurement files in the sample
2. Filters to valid code_names that exist in test_configurations.json
3. Generates device-level combined sweep plots (using sweep_combinations from config)
4. Runs section-level analysis (stacked sweeps & statistics for each section)
5. Runs sample-level analysis for each code_name (12 plot types per code_name)
6. Runs overall sample analysis (all measurements combined, no code_name filter)

Key Classes:
------------
- ComprehensiveAnalyzer: Main orchestrator class

Key Methods:
------------
- run_comprehensive_analysis(): Main entry point - runs complete analysis workflow
- discover_all_code_names(): Scans files to find all test types
- get_valid_code_names(): Filters to code_names in test_configurations.json
- plot_device_combined_sweeps(): Creates device-level combined plots

Usage:
------
    from Helpers.Analysis import ComprehensiveAnalyzer
    
    analyzer = ComprehensiveAnalyzer(sample_directory="path/to/sample")
    analyzer.set_log_callback(lambda msg: print(msg))  # Optional progress logging
    analyzer.run_comprehensive_analysis()

Output:
-------
All output saved to: {sample_dir}/sample_analysis/
- Device plots: {sample_dir}/{section}/{device_num}/images/
- Section plots: {sample_dir}/{section}/plots_combined/
- Sample plots: {sample_dir}/sample_analysis/plots/{code_name}/ (code_name-specific)
- Overall plots: {sample_dir}/sample_analysis/plots/ (no code_name filter)
- Size comparison plots: {sample_dir}/sample_analysis/plots/size_comparison/
- Origin data: {sample_dir}/sample_analysis/plots/data_origin_formatted/
- Analysis data: {sample_dir}/sample_analysis/analysis/ (device_tracking, device_research, device_summaries)

Called By:
----------
- gui/measurement_gui/main.py → run_full_sample_analysis() (via "Run Full Sample Analysis" button)

Dependencies:
-------------
- section_analyzer.py: SectionAnalyzer for section-level analysis
- sample_analyzer.py: SampleAnalysisOrchestrator for sample-level analysis
- Json_Files/test_configurations.json: Test type configurations
"""

import os
import json
import numpy as np
import matplotlib
# Force Agg backend
matplotlib.use('Agg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
import matplotlib.pyplot as plt
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Callable
from collections import defaultdict

# Get project root (go up 3 levels: aggregators -> Analysis -> Helpers -> project root)
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_CONFIG_PATH = _PROJECT_ROOT / "Json_Files" / "test_configurations.json"


class ComprehensiveAnalyzer:
    """One-stop comprehensive analysis for all measurement types."""
    
    def __init__(self, sample_directory: str):
        """
        Args:
            sample_directory: Path to sample folder
        """
        self.sample_dir = Path(sample_directory)
        self.sample_name = self.sample_dir.name
        self.config_path = _CONFIG_PATH
        
        # Load test configurations
        self.test_configs = self._load_test_configurations()
        
        # Discovered code_names
        self.discovered_code_names: Set[str] = set()
        
        # Logging callback for progress updates
        self.log_callback: Optional[callable] = None
    
    def set_log_callback(self, callback: callable) -> None:
        """Set callback function for logging progress updates."""
        self.log_callback = callback
    
    def _log(self, message: str) -> None:
        """Log message using callback if available, otherwise print."""
        if self.log_callback:
            self.log_callback(message)
        else:
            print(message)
        
    def _load_test_configurations(self) -> Dict:
        """Load test configurations from JSON."""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"[COMPREHENSIVE] Error loading test_configurations.json: {e}")
            return {}
    
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
        """Extract code_name from filename (position 6 after splitting by '-')."""
        try:
            filename = filename.replace('.txt', '')
            parts = filename.split('-')
            if len(parts) > 6:
                code_name = parts[6]
                # Filter out numeric-only code names (misclassified)
                if self._is_valid_code_name(code_name):
                    return code_name
        except Exception:
            pass
        return None
    
    def discover_all_code_names(self) -> Set[str]:
        """Scan all measurement files to discover all code_names."""
        code_names = set()
        
        # Scan device directories (letter/number structure)
        for section_dir in self.sample_dir.iterdir():
            if not section_dir.is_dir() or section_dir.name in ['device_tracking', 'device_research', 'device_summaries', 'sample_analysis']:
                continue
            
            # Check if it's a section (single letter)
            if len(section_dir.name) == 1 and section_dir.name.isalpha():
                for device_dir in section_dir.iterdir():
                    if device_dir.is_dir() and device_dir.name.isdigit():
                        # Scan .txt files in device directory
                        for file in device_dir.glob('*.txt'):
                            if file.name != 'log.txt':
                                code_name = self._extract_code_name_from_filename(file.name)
                                if code_name:
                                    code_names.add(code_name)
        
        self.discovered_code_names = code_names
        print(f"[COMPREHENSIVE] Discovered code_names: {sorted(code_names)}")
        return code_names
    
    def get_valid_code_names(self) -> List[str]:
        """Get code_names that exist in both discovered files and test_configurations.json."""
        discovered = self.discover_all_code_names()
        valid = [cn for cn in discovered if cn in self.test_configs]
        print(f"[COMPREHENSIVE] Valid code_names (in config): {valid}")
        return valid
    
    def _find_min_sweep_for_code_name(self, device_path: Path, code_name: str) -> Optional[int]:
        """
        Find the minimum sweep number for a given code_name in a device folder.
        This treats the lowest number as the first measurement for that code_name.
        
        Args:
            device_path: Path to device directory
            code_name: Code name to search for
            
        Returns:
            int or None: Minimum sweep number for this code_name, or None if not found
        """
        if not device_path.exists():
            return None
        
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
    
    def plot_device_combined_sweeps(self, section: str, device_num: str, code_name: str) -> None:
        """
        Plot combined sweeps for a single device using sweep_combinations from config.
        
        This matches the old module's analyze_single_device() behavior.
        Finds the minimum sweep number for the code_name and treats it as the first measurement.
        
        Special handling for endurance and retention measurements:
        - Endurance: plots resistance vs cycle/iteration
        - Retention: plots resistance vs time
        - IV sweeps: plots voltage vs current (default)
        """
        device_path = self.sample_dir / section / device_num
        if not device_path.exists():
            return
        
        images_dir = device_path / 'images'
        images_dir.mkdir(exist_ok=True)
        
        # Find minimum sweep number for this code_name (treat as first measurement)
        min_sweep = self._find_min_sweep_for_code_name(device_path, code_name)
        if min_sweep is None:
            return  # No files found for this code_name
        
        # Get sweep combinations for this code_name
        if code_name not in self.test_configs:
            return
        
        config = self.test_configs[code_name]
        combinations = config.get('sweep_combinations', [])
        
        if not combinations:
            return
        
        # Detect measurement type from code_name
        is_endurance = 'end' in code_name.lower()
        is_retention = 'ret' in code_name.lower()
        
        # Process each combination
        for combo in combinations:
            sweeps = combo.get('sweeps', [])
            title = combo.get('title', f"Combination {sweeps}")
            
            if not sweeps:
                continue
            
            # Create figure - different layout for endurance/retention vs IV
            if is_endurance or is_retention:
                # Single plot for endurance/retention
                fig = Figure(figsize=(12, 6))
                FigureCanvasAgg(fig)
                ax1 = fig.add_subplot(111)
            else:
                # Dual plot (linear + log) for IV sweeps
                fig = Figure(figsize=(16, 6))
                FigureCanvasAgg(fig)
                ax1 = fig.add_subplot(121)
                ax2 = fig.add_subplot(122)
            
            # Plot each sweep in the combination
            # sweeps from config are relative (1=first, 2=second, etc.)
            # Add to min_sweep to get actual sweep numbers
            for relative_sweep in sweeps:
                actual_sweep_num = min_sweep + (relative_sweep - 1)  # Convert relative to absolute
                sweep_files = list(device_path.glob(f'{actual_sweep_num}-*.txt'))
                sweep_files = [f for f in sweep_files if f.name != 'log.txt']
                
                # Filter to only files with matching code_name
                matching_files = []
                for f in sweep_files:
                    try:
                        parts = f.name.replace('.txt', '').split('-')
                        if len(parts) > 6 and parts[6] == code_name:
                            matching_files.append(f)
                    except (ValueError, IndexError):
                        continue
                
                if matching_files:
                    try:
                        # Read data file
                        data = np.loadtxt(matching_files[0], skiprows=1 if self._has_header(matching_files[0]) else 0)
                        
                        if data.shape[1] < 2:
                            continue
                        
                        # Parse filename for metadata
                        file_info = self._parse_filename(matching_files[0].name)
                        
                        # Determine label
                        if is_endurance:
                            label = f"Endurance {relative_sweep}"
                            # Try to extract pulse time from filename if available
                            if file_info:
                                label += f" (Sweep {actual_sweep_num})"
                        elif is_retention:
                            label = f"Retention {relative_sweep}"
                            if file_info:
                                label += f" (Sweep {actual_sweep_num})"
                        else:
                            label = f"Sweep {actual_sweep_num}"
                            if file_info and len(sweeps) >= 3:
                                label += f" (V={file_info.get('voltage', '?')}, SD={file_info.get('step_delay', '?')})"
                        
                        # Plot based on measurement type
                        if is_endurance:
                            # Endurance: plot resistance vs cycle/iteration
                            # Data format: typically has iteration/cycle, resistance columns
                            if data.shape[1] >= 2:
                                # Try to detect column structure
                                # Common formats: [iteration, resistance] or [time, voltage, current, resistance]
                                if data.shape[1] >= 4:
                                    # Assume: time, voltage, current, resistance
                                    x_data = data[:, 0]  # time or iteration
                                    y_data = data[:, 3]  # resistance
                                elif data.shape[1] >= 2:
                                    # Assume: iteration/cycle, resistance
                                    x_data = np.arange(len(data))  # cycle number
                                    y_data = data[:, 1]  # resistance (or calculate from V/I)
                                    # If second column looks like current, calculate resistance
                                    if np.max(np.abs(y_data)) > 1e-3:  # Looks like current
                                        voltage = data[:, 0]
                                        current = data[:, 1]
                                        y_data = np.abs(voltage / (current + 1e-12))  # Calculate resistance
                                
                                ax1.plot(x_data, y_data, label=label, linewidth=1.5, marker='o', markersize=3)
                                
                        elif is_retention:
                            # Retention: plot resistance vs time
                            if data.shape[1] >= 2:
                                # Common formats: [time, resistance] or [time, voltage, current, resistance]
                                if data.shape[1] >= 4:
                                    # Assume: time, voltage, current, resistance
                                    x_data = data[:, 0]  # time
                                    y_data = data[:, 3]  # resistance
                                elif data.shape[1] >= 2:
                                    # Assume: time, resistance or time, voltage, current
                                    x_data = data[:, 0]  # time
                                    if data.shape[1] >= 3:
                                        # time, voltage, current - calculate resistance
                                        voltage = data[:, 1]
                                        current = data[:, 2]
                                        y_data = np.abs(voltage / (current + 1e-12))
                                    else:
                                        y_data = data[:, 1]  # resistance
                                
                                ax1.plot(x_data, y_data, label=label, linewidth=1.5, marker='o', markersize=3)
                                
                        else:
                            # IV Sweep: plot voltage vs current
                            voltage = data[:, 0]
                            current = data[:, 1]
                            
                            # Plot on both axes
                            ax1.plot(voltage, current, label=label, linewidth=1.5)
                            if not is_endurance and not is_retention:
                                ax2.semilogy(voltage, np.abs(current), label=label, linewidth=1.5)
                            
                            # NOTE: SCLC plots are available but commented out per user request
                            # Uncomment when ready to use
                            # from Helpers.plotting_core import UnifiedPlotter
                            # 
                            # # Check if device is memristive (would need analysis data)
                            # # device_is_memristive = ...  # Determine from analysis
                            # 
                            # # if device_is_memristive:
                            # #     plotter = UnifiedPlotter(save_dir=images_dir)
                            # #     plotter.plot_sclc_fit(
                            # #         voltage=voltage,
                            # #         current=current,
                            # #         device_name=f"{section}{device_num}",
                            # #         save_name=f"{code_name}_sclc_fit.png"
                            # #     )
                                
                    except Exception as e:
                        print(f"[COMPREHENSIVE] Error reading {matching_files[0]}: {e}")
                        continue
            
            # Format plots based on measurement type
            if is_endurance:
                ax1.set_xlabel('Cycle/Iteration', fontsize=12, fontweight='bold')
                ax1.set_ylabel('Resistance (Ω)', fontsize=12, fontweight='bold')
                ax1.set_title(f"{self.sample_name} {section}{device_num} {code_name} - {title}", 
                             fontsize=13, fontweight='bold')
                ax1.grid(True, alpha=0.3)
                ax1.legend()
                ax1.set_yscale('log')  # Log scale for resistance
                
            elif is_retention:
                ax1.set_xlabel('Time (s)', fontsize=12, fontweight='bold')
                ax1.set_ylabel('Resistance (Ω)', fontsize=12, fontweight='bold')
                ax1.set_title(f"{self.sample_name} {section}{device_num} {code_name} - {title}", 
                             fontsize=13, fontweight='bold')
                ax1.grid(True, alpha=0.3)
                ax1.legend()
                ax1.set_yscale('log')  # Log scale for resistance
                
            else:
                # IV Sweep formatting
                ax1.set_xlabel('Voltage (V)', fontsize=12, fontweight='bold')
                ax1.set_ylabel('Current (A)', fontsize=12, fontweight='bold')
                ax1.set_title(f"{self.sample_name} {section}{device_num} {code_name} - {title}", 
                             fontsize=13, fontweight='bold')
                ax1.grid(True, alpha=0.3)
                ax1.legend()
                
                ax2.set_xlabel('Voltage (V)', fontsize=12, fontweight='bold')
                ax2.set_ylabel('|Current| (A)', fontsize=12, fontweight='bold')
                ax2.set_title(f"{self.sample_name} {section}{device_num} {code_name} - {title} (Log)", 
                             fontsize=13, fontweight='bold')
                ax2.grid(True, alpha=0.3)
                ax2.legend()
            
            fig.tight_layout()
            
            # Save
            safe_title = title.replace(" ", "_").replace("/", "-")
            output_file = images_dir / f'{code_name}_{sweeps}_{safe_title}.png'
            try:
                fig.savefig(output_file, dpi=300, bbox_inches='tight')
            except Exception:
                pass
            
            print(f"[COMPREHENSIVE] Saved: {output_file}")
    
    def _analyze_dc_endurance_if_present(self, section: str, device_num: str, code_name: str) -> None:
        """
        Check if device has DC endurance data (≥10 sweeps) and analyze if found.
        
        Args:
            section: Section letter (e.g., 'A')
            device_num: Device number (e.g., '1')
            code_name: Code name for the measurement type
        """
        try:
            device_path = self.sample_dir / section / device_num
            if not device_path.exists():
                return
            
            # Count sweeps for this code_name
            sweep_count = 0
            matching_files = []
            
            for file in device_path.glob('*.txt'):
                if file.name == 'log.txt':
                    continue
                try:
                    parts = file.name.replace('.txt', '').split('-')
                    if len(parts) > 6 and parts[6] == code_name:
                        matching_files.append(file)
                        # Try to extract sweep number from filename
                        try:
                            sweep_num = int(parts[0])
                            sweep_count = max(sweep_count, sweep_num)
                        except (ValueError, IndexError):
                            pass
                except (ValueError, IndexError):
                    continue
            
            # Also check if a single file contains multiple loops (≥10)
            # This handles the case where all sweeps are in one file
            single_file_loops = 0
            if len(matching_files) == 1:
                # Check if single file has multiple loops
                try:
                    data = np.loadtxt(matching_files[0], skiprows=1 if self._has_header(matching_files[0]) else 0)
                    if data.shape[1] >= 2:
                        voltage = data[:, 0]
                        # Simple loop detection: count zero crossings
                        zero_crossings = 0
                        for i in range(1, len(voltage)):
                            if voltage[i-1] * voltage[i] < 0:  # Sign change
                                zero_crossings += 1
                        # Bipolar sweep typically has 4 zero crossings per loop
                        if zero_crossings >= 4:
                            single_file_loops = max(1, zero_crossings // 4)
                except Exception:
                    pass
            
            # Check if we have ≥10 sweeps (either multiple files or single file with loops)
            total_sweeps = max(sweep_count, single_file_loops)
            
            if total_sweeps >= 10:
                self._log(f"Detected DC endurance data for {section}{device_num} ({code_name}): {total_sweeps} sweeps")
                self._run_dc_endurance_analysis(section, device_num, code_name, matching_files, total_sweeps)
        
        except Exception as e:
            self._log(f"Error checking DC endurance for {section}{device_num}: {e}")
            import traceback
            traceback.print_exc()
    
    def _run_dc_endurance_analysis(
        self,
        section: str,
        device_num: str,
        code_name: str,
        matching_files: List[Path],
        num_sweeps: int
    ) -> None:
        """
        Run DC endurance analysis on device data.
        
        Args:
            section: Section letter
            device_num: Device number
            code_name: Code name
            matching_files: List of matching measurement files
            num_sweeps: Number of sweeps detected
        """
        try:
            from .dc_endurance_analyzer import DCEnduranceAnalyzer
            
            # Collect all voltage/current data
            split_v_data = []
            split_c_data = []
            
            # If multiple files, read each one
            if len(matching_files) > 1:
                # Sort files by sweep number
                def get_sweep_num(f: Path) -> int:
                    try:
                        return int(f.name.split('-')[0])
                    except (ValueError, IndexError):
                        return 0
                
                sorted_files = sorted(matching_files, key=get_sweep_num)
                
                for file in sorted_files[:num_sweeps]:  # Limit to detected number
                    try:
                        data = np.loadtxt(file, skiprows=1 if self._has_header(file) else 0)
                        if data.shape[1] >= 2:
                            split_v_data.append(data[:, 0])
                            split_c_data.append(data[:, 1])
                    except Exception as e:
                        self._log(f"Error reading {file.name} for DC endurance: {e}")
                        continue
            
            # If single file with multiple loops, split it
            elif len(matching_files) == 1 and num_sweeps >= 10:
                try:
                    data = np.loadtxt(matching_files[0], skiprows=1 if self._has_header(matching_files[0]) else 0)
                    if data.shape[1] >= 2:
                        voltage = data[:, 0]
                        current = data[:, 1]
                        
                        # Use loop detection to split
                        # Simple approach: detect zero crossings to estimate loops
                        # More sophisticated splitting can be added later
                        zero_crossings = sum(1 for i in range(1, len(voltage)) if voltage[i-1] * voltage[i] < 0)
                        estimated_loops = max(1, zero_crossings // 4) if zero_crossings >= 4 else 1
                        
                        if estimated_loops >= 10:
                            # Split evenly for now (can be improved with proper loop detection)
                            points_per_loop = len(voltage) // estimated_loops
                            for i in range(estimated_loops):
                                start_idx = i * points_per_loop
                                end_idx = (i + 1) * points_per_loop if i < estimated_loops - 1 else len(voltage)
                                split_v_data.append(voltage[start_idx:end_idx])
                                split_c_data.append(current[start_idx:end_idx])
                        else:
                            # Fallback: split evenly based on num_sweeps
                            points_per_sweep = len(voltage) // num_sweeps
                            for i in range(num_sweeps):
                                start_idx = i * points_per_sweep
                                end_idx = (i + 1) * points_per_sweep if i < num_sweeps - 1 else len(voltage)
                                split_v_data.append(voltage[start_idx:end_idx])
                                split_c_data.append(current[start_idx:end_idx])
                except Exception as e:
                    self._log(f"Error splitting loops for DC endurance: {e}")
                    return
            
            # Run DC endurance analysis if we have data
            if len(split_v_data) >= 10 and len(split_v_data) == len(split_c_data):
                # Use device path for file naming (no code_name in filename to avoid overwrites)
                file_name = f"{section}{device_num}_endurance"
                
                # Get device path
                device_path = self.sample_dir / section / device_num
                
                analyzer = DCEnduranceAnalyzer(
                    split_voltage_data=split_v_data,
                    split_current_data=split_c_data,
                    file_name=file_name,
                    device_path=str(device_path)
                )
                
                analyzer.analyze_and_plot()
                self._log(f"✓ DC endurance analysis complete for {section}{device_num} (saved to {device_path}/Graphs/)")
            else:
                self._log(f"⚠ Insufficient data for DC endurance: {len(split_v_data)} sweeps found")
        
        except Exception as e:
            self._log(f"Error running DC endurance analysis for {section}{device_num}: {e}")
            import traceback
            traceback.print_exc()
    
    def _has_header(self, file_path: Path) -> bool:
        """Check if file has header."""
        try:
            with open(file_path, 'r') as f:
                first_line = f.readline().strip()
                # Check if first line looks like header (contains text, not just numbers)
                return not first_line.replace('.', '').replace('-', '').replace('E', '').replace('+', '').isdigit()
        except:
            return False
    
    def _parse_filename(self, filename: str) -> Optional[Dict]:
        """Parse filename to extract metadata."""
        try:
            filename = filename.replace('.txt', '')
            parts = filename.split('-')
            if len(parts) >= 5:
                return {
                    'sweep_num': int(parts[0]),
                    'sweep_type': parts[1],
                    'voltage': float(parts[2].replace('v', '')),
                    'step_voltage': float(parts[3].replace('sv', '')),
                    'step_delay': float(parts[4].replace('sd', ''))
                }
        except Exception:
            pass
        return None
    
    def run_comprehensive_analysis(self) -> None:
        """
        Run comprehensive analysis: discover all code_names and analyze each one.
        
        This is the "one-stop shop" that does everything:
        1. Discovers all code_names from files
        2. For each valid code_name, runs device-level combined plots
        3. Runs sample-level analysis for each code_name
        4. Runs overall sample analysis (no filter)
        """
        self._log(f"Starting comprehensive analysis for {self.sample_name}...")
        
        # Discover all code_names
        self._log("Discovering code names from measurement files...")
        valid_code_names = self.get_valid_code_names()
        self._log(f"Found {len(valid_code_names)} code name(s): {', '.join(sorted(valid_code_names))}")
        
        # Count total devices for progress tracking
        total_devices = 0
        device_list = []
        for section_dir in self.sample_dir.iterdir():
            if not section_dir.is_dir() or section_dir.name in ['device_tracking', 'device_research', 'sample_analysis']:
                continue
            if len(section_dir.name) == 1 and section_dir.name.isalpha():
                section = section_dir.name
                for device_dir in section_dir.iterdir():
                    if device_dir.is_dir() and device_dir.name.isdigit():
                        device_num = device_dir.name
                        device_path = self.sample_dir / section / device_num
                        txt_files = [f for f in device_path.glob('*.txt') if f.name != 'log.txt']
                        if txt_files:
                            total_devices += 1
                            device_list.append((section, device_num))
        
        self._log(f"Found {total_devices} device(s) with measurement files")
        
        # Run device-level combined plots for each code_name
        self._log("Generating device-level combined sweep plots...")
        plotted_count = 0
        for section, device_num in device_list:
            device_dir = self.sample_dir / section / device_num
            
            # Find code_name for this device
            device_code_name = None
            for file in device_dir.glob('*.txt'):
                if file.name != 'log.txt':
                    code_name = self._extract_code_name_from_filename(file.name)
                    if code_name and code_name in valid_code_names:
                        device_code_name = code_name
                        break
            
            if device_code_name:
                self.plot_device_combined_sweeps(section, device_num, device_code_name)
                
                # Check for DC endurance data (≥10 sweeps) and analyze if found
                self._analyze_dc_endurance_if_present(section, device_num, device_code_name)
                
                plotted_count += 1
                remaining = total_devices - plotted_count
                self._log(f"Plotted device {section}{device_num} ({device_code_name}) - {plotted_count}/{total_devices} done, {remaining} remaining")

        # Run section-level analysis (restored feature)
        self._log("Running section-level analysis (stacked sweeps & stats)...")
        from .section_analyzer import SectionAnalyzer
        
        unique_sections = sorted(list(set(s for s, _ in device_list)))
        for section in unique_sections:
            try:
                self._log(f"Analyzing Section {section}...")
                sec_analyzer = SectionAnalyzer(str(self.sample_dir), section, self.sample_name)
                sec_analyzer.analyze_section_sweeps()
            except Exception as e:
                self._log(f"Error analyzing Section {section}: {e}")
        
        # Run sample-level analysis for each code_name
        self._log(f"Running sample-level analysis for {len(valid_code_names)} code name(s)...")
        from .sample_analyzer import SampleAnalysisOrchestrator
        
        for idx, code_name in enumerate(valid_code_names, 1):
            self._log(f"[{idx}/{len(valid_code_names)}] Analyzing code_name: {code_name}")
            try:
                analyzer = SampleAnalysisOrchestrator(str(self.sample_dir), code_name=code_name)
                analyzer.set_log_callback(self.log_callback)  # Pass logging callback
                device_count = analyzer.load_all_devices()
                if device_count > 0:
                    self._log(f"Generating 12 plot types for {code_name} ({device_count} devices)...")
                    analyzer.generate_all_plots()
                    self._log(f"Exporting Origin data for {code_name}...")
                    analyzer.export_origin_data()
                    self._log(f"✓ Completed {code_name}: {device_count} devices, 12 plots generated")
                else:
                    self._log(f"⚠ No devices found for {code_name}")
            except Exception as e:
                self._log(f"✗ Error analyzing {code_name}: {str(e)}")
                import traceback
                traceback.print_exc()
        
        # Run overall sample analysis (no code_name filter)
        self._log("Running overall sample analysis (all measurements combined)...")
        try:
            analyzer = SampleAnalysisOrchestrator(str(self.sample_dir), code_name=None)
            analyzer.set_log_callback(self.log_callback)  # Pass logging callback
            device_count = analyzer.load_all_devices()
            if device_count > 0:
                self._log(f"Generating 12 plot types for overall analysis ({device_count} devices)...")
                analyzer.generate_all_plots()
                self._log("Exporting Origin data for overall analysis...")
                analyzer.export_origin_data()
                self._log(f"✓ Completed overall analysis: {device_count} devices, 12 plots generated")
            else:
                self._log("⚠ No devices found for overall analysis")
        except Exception as e:
            self._log(f"✗ Error in overall analysis: {str(e)}")
            import traceback
            traceback.print_exc()
        
        self._log("✓ Comprehensive analysis complete!")












