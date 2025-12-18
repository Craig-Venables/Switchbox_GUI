"""
Sample-level analysis orchestrator using existing device tracking and research data.

Generates comprehensive plots and statistics for entire samples (100+ devices),
featuring 12 advanced plot types and Origin-ready data export.
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


class SampleAnalysisOrchestrator:
    """Orchestrate full sample analysis with 12 advanced plot types."""
    
    def __init__(self, sample_directory: str, code_name: Optional[str] = None):
        """
        Args:
            sample_directory: Path to sample folder containing device_tracking/, 
                            device_research/, etc.
            code_name: Optional code name (test_type) to filter by. If provided, only
                      devices/measurements with this code_name will be included.
        """
        self.sample_dir = sample_directory
        self.sample_name = os.path.basename(sample_directory)
        self.code_name_filter = code_name  # Filter by code_name like old module
        
        # Data directories - all under sample_analysis/
        self.tracking_dir = os.path.join(sample_directory, "sample_analysis", "device_tracking")
        self.research_dir = os.path.join(sample_directory, "sample_analysis", "device_research")
        
        # Unified output directory structure - everything in sample_analysis/ with subfolders
        self.output_dir = os.path.join(sample_directory, "sample_analysis")
        if code_name:
            # Use subfolder for code_name-specific analysis
            self.plots_dir = os.path.join(self.output_dir, "plots", code_name)
            self.data_origin_formatted_dir = os.path.join(self.output_dir, "plots", "data_origin_formatted", code_name)
        else:
            # Overall analysis (no code_name filter)
            self.plots_dir = os.path.join(self.output_dir, "plots", "overall")
            self.data_origin_formatted_dir = os.path.join(self.output_dir, "plots", "data_origin_formatted", "overall")
        
        # Device summaries also go in unified folder
        self.summaries_dir = os.path.join(self.output_dir, "device_summaries")
        
        # Create output directories
        os.makedirs(self.plots_dir, exist_ok=True)
        os.makedirs(self.data_origin_formatted_dir, exist_ok=True)
        os.makedirs(self.summaries_dir, exist_ok=True)
        
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
                return parts[6]  # code_name is in position 6
        except (IndexError, AttributeError):
            pass
        return None
    
    def _find_code_name_for_device(self, device_id: str) -> Optional[str]:
        """
        Find code_name for a device by scanning device directory for measurement files.
        Matches old module's detect_test_type() behavior.
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
                    # Look for first sweep file (sweep 1)
                    for file in os.listdir(device_dir):
                        if file.startswith('1-') and file.endswith('.txt'):
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
        """Generate all 12 plot types."""
        self._log(f"Generating 12 plot types for {self.sample_name}...")
        
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
            "Forming Status Distribution"
        ]
        
        plot_num = 0
        
        # Plot 1: Memristivity Score Heatmap
        plot_num += 1
        self._log(f"Plot {plot_num}/12: {plot_names[0]}")
        self.plot_memristivity_heatmap()
        
        # Plot 2: Conduction Mechanism Distribution
        plot_num += 1
        self._log(f"Plot {plot_num}/12: {plot_names[1]}")
        self.plot_conduction_mechanisms()
        
        # Plot 3: Memory Window Quality Distribution
        plot_num += 1
        self._log(f"Plot {plot_num}/12: {plot_names[2]}")
        self.plot_memory_window_quality()
        
        # Plot 4: Hysteresis Shape Radar (memristive only)
        if self.memristive_devices:
            plot_num += 1
            self._log(f"Plot {plot_num}/12: {plot_names[3]}")
            self.plot_hysteresis_radar()
        
        # Plot 5: Enhanced Classification Scatter
        plot_num += 1
        self._log(f"Plot {plot_num}/12: {plot_names[4]}")
        self.plot_classification_scatter()
        
        # Plot 6: Forming Progress Tracking
        plot_num += 1
        self._log(f"Plot {plot_num}/12: {plot_names[5]}")
        self.plot_forming_progress()
        
        # Plot 7: Warning Flag Summary
        plot_num += 1
        self._log(f"Plot {plot_num}/12: {plot_names[6]}")
        self.plot_warning_summary()
        
        # Plot 8: Research Diagnostics Scatter Matrix
        if self.memristive_devices and len(self.research_data) > 0:
            plot_num += 1
            self._log(f"Plot {plot_num}/12: {plot_names[7]}")
            self.plot_research_diagnostics()
        
        # Plot 9: Power & Energy Efficiency
        if len(self.research_data) > 0:
            plot_num += 1
            self._log(f"Plot {plot_num}/12: {plot_names[8]}")
            self.plot_power_efficiency()
        
        # Plot 10: Device Leaderboard
        plot_num += 1
        self._log(f"Plot {plot_num}/12: {plot_names[9]}")
        self.plot_device_leaderboard()
        
        # Plot 11: Spatial Distribution Maps
        plot_num += 1
        self._log(f"Plot {plot_num}/12: {plot_names[10]}")
        self.plot_spatial_distributions()
        
        # Plot 12: Forming Status Distribution
        plot_num += 1
        self._log(f"Plot {plot_num}/12: {plot_names[11]}")
        self.plot_forming_status()
        
        self._log(f"✓ All {plot_num} plots saved to: {self.plots_dir}")
    
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

