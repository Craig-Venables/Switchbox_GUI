"""
Comprehensive analysis orchestrator - one-stop shop for all analysis types.

This module provides:
1. Auto-detection of all code_names from measurement files
2. Analysis for each code_name found in test_configurations.json
3. Device-level combined sweep plots (using sweep_combinations)
4. Section-level and sample-level analysis
5. Automatic execution after custom measurements
"""

import os
import json
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict

# Get project root
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
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
        
    def _load_test_configurations(self) -> Dict:
        """Load test configurations from JSON."""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"[COMPREHENSIVE] Error loading test_configurations.json: {e}")
            return {}
    
    def _extract_code_name_from_filename(self, filename: str) -> Optional[str]:
        """Extract code_name from filename (position 6 after splitting by '-')."""
        try:
            filename = filename.replace('.txt', '')
            parts = filename.split('-')
            if len(parts) > 6:
                return parts[6]
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
    
    def plot_device_combined_sweeps(self, section: str, device_num: str, code_name: str) -> None:
        """
        Plot combined sweeps for a single device using sweep_combinations from config.
        
        This matches the old module's analyze_single_device() behavior.
        """
        device_path = self.sample_dir / section / device_num
        if not device_path.exists():
            return
        
        images_dir = device_path / 'images'
        images_dir.mkdir(exist_ok=True)
        
        # Get sweep combinations for this code_name
        if code_name not in self.test_configs:
            return
        
        config = self.test_configs[code_name]
        combinations = config.get('sweep_combinations', [])
        
        if not combinations:
            return
        
        # Process each combination
        for combo in combinations:
            sweeps = combo.get('sweeps', [])
            title = combo.get('title', f"Combination {sweeps}")
            
            if not sweeps:
                continue
            
            # Create figure with linear and log subplots
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
            
            # Plot each sweep in the combination
            for sweep_num in sweeps:
                sweep_files = list(device_path.glob(f'{sweep_num}-*.txt'))
                sweep_files = [f for f in sweep_files if f.name != 'log.txt']
                
                if sweep_files:
                    try:
                        # Read data file
                        data = np.loadtxt(sweep_files[0], skiprows=1 if self._has_header(sweep_files[0]) else 0)
                        if data.shape[1] >= 2:
                            voltage = data[:, 0]
                            current = data[:, 1]
                            
                            # Parse filename for metadata
                            file_info = self._parse_filename(sweep_files[0].name)
                            label = f"Sweep {sweep_num}"
                            if file_info and len(sweeps) >= 3:
                                label += f" (V={file_info.get('voltage', '?')}, SD={file_info.get('step_delay', '?')})"
                            
                            # Plot on both axes
                            ax1.plot(voltage, current, label=label, linewidth=1.5)
                            ax2.semilogy(voltage, np.abs(current), label=label, linewidth=1.5)
                    except Exception as e:
                        print(f"[COMPREHENSIVE] Error reading {sweep_files[0]}: {e}")
                        continue
            
            # Format plots
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
            
            plt.tight_layout()
            
            # Save
            safe_title = title.replace(" ", "_").replace("/", "-")
            output_file = images_dir / f'{code_name}_{sweeps}_{safe_title}.png'
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"[COMPREHENSIVE] Saved: {output_file}")
    
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
        print(f"[COMPREHENSIVE] Starting comprehensive analysis for {self.sample_name}...")
        
        # Discover all code_names
        valid_code_names = self.get_valid_code_names()
        
        # Run device-level combined plots for each code_name
        print(f"[COMPREHENSIVE] Generating device-level combined plots...")
        for section_dir in self.sample_dir.iterdir():
            if not section_dir.is_dir() or section_dir.name in ['device_tracking', 'device_research', 'sample_analysis']:
                continue
            
            if len(section_dir.name) == 1 and section_dir.name.isalpha():
                section = section_dir.name
                for device_dir in section_dir.iterdir():
                    if device_dir.is_dir() and device_dir.name.isdigit():
                        device_num = device_dir.name
                        
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
        
        # Run sample-level analysis for each code_name
        print(f"[COMPREHENSIVE] Running sample-level analysis for each code_name...")
        from .sample_analyzer import SampleAnalysisOrchestrator
        
        for code_name in valid_code_names:
            print(f"[COMPREHENSIVE] Analyzing code_name: {code_name}")
            try:
                analyzer = SampleAnalysisOrchestrator(str(self.sample_dir), code_name=code_name)
                device_count = analyzer.load_all_devices()
                if device_count > 0:
                    analyzer.generate_all_plots()
                    analyzer.export_origin_data()
                    print(f"[COMPREHENSIVE] Completed analysis for {code_name}: {device_count} devices")
            except Exception as e:
                print(f"[COMPREHENSIVE] Error analyzing {code_name}: {e}")
                import traceback
                traceback.print_exc()
        
        # Run overall sample analysis (no code_name filter)
        print(f"[COMPREHENSIVE] Running overall sample analysis (all measurements)...")
        try:
            analyzer = SampleAnalysisOrchestrator(str(self.sample_dir), code_name=None)
            device_count = analyzer.load_all_devices()
            if device_count > 0:
                analyzer.generate_all_plots()
                analyzer.export_origin_data()
                print(f"[COMPREHENSIVE] Completed overall analysis: {device_count} devices")
        except Exception as e:
            print(f"[COMPREHENSIVE] Error in overall analysis: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"[COMPREHENSIVE] Comprehensive analysis complete!")

