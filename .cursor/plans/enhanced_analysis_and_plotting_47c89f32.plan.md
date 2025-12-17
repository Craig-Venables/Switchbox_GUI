---
name: Enhanced Analysis and Plotting
overview: Complete custom measurement analysis with conditional processing, plus comprehensive sample analysis featuring 12 advanced plot types and Origin-ready data export for publication-quality figures
todos:
  - id: conditional-analysis
    content: Modify _run_analysis_if_enabled() to add conditional logic for custom sequences
    status: completed
  - id: custom-measurement-updates
    content: Update run_custom_measurement() to track memristive flag and collect results
    status: completed
  - id: live-display
    content: Add _update_live_classification_display() method for real-time progress
    status: completed
  - id: notification-placeholder
    content: Add _send_classification_notification() placeholder method
    status: completed
  - id: summary-generator
    content: Implement _generate_sequence_summary() for comprehensive reports
    status: completed
  - id: sample-analyzer-core
    content: Create SampleAnalysisOrchestrator class with data loading
    status: completed
  - id: essential-plots
    content: Implement plots 1, 2, 3, 10 (memristivity heatmap, conduction, quality, leaderboard)
    status: completed
  - id: advanced-plots
    content: Implement plots 5, 6, 7, 11, 12 (scatter, forming, warnings, spatial, status)
    status: completed
  - id: specialized-plots
    content: Implement plots 4, 8, 9 (hysteresis radar, diagnostics, power)
    status: completed
  - id: origin-export
    content: Implement all Origin CSV export methods with README
    status: completed
  - id: graphing-tab-ui
    content: Add graphing tab to GUI layout
    status: completed
  - id: sample-analysis-trigger
    content: Add run_full_sample_analysis() method to main GUI
    status: completed
  - id: test-full-system
    content: "Test complete system: custom measurement → sample analysis → Origin export"
    status: pending
---

# Enhanced Analysis & Advanced Plotting System

## Overview

Integrate conditional custom measurement analysis with a comprehensive sample analysis system featuring 12 advanced plot types using Phase 1 & 2 enhanced metrics, plus Origin-ready data export.

---

## Part 1: Custom Measurement Analysis (from existing plan)

### 1.1 Conditional Analysis for Custom Sequences

**File**: [`gui/measurement_gui/main.py`](gui/measurement_gui/main.py)

Modify `_run_analysis_if_enabled()` (line ~706) to add conditional logic:

```python
def _run_analysis_if_enabled(
    self,
    voltage: List[float],
    current: List[float],
    timestamps: Optional[List[float]],
    save_dir: str,
    file_name: str,
    metadata: Optional[Dict[str, Any]] = None,
    is_custom_sequence: bool = False,  # NEW
    sweep_number: int = 1,              # NEW
    device_memristive_flag: bool = None # NEW
) -> Optional[Dict[str, Any]]:
    """Run analysis with conditional logic for custom sequences."""
    
    # Skip if not first sweep AND device is not memristive
    if is_custom_sequence and sweep_number > 1:
        if not device_memristive_flag:
            print(f"[ANALYSIS] Skipping sweep {sweep_number} - device not memristive")
            return None
    
    # ... existing analysis logic ...
    
    # After first sweep, return memristive flag
    if is_custom_sequence and sweep_number == 1:
        score = analysis_data.get('classification', {}).get('memristivity_score', 0)
        is_memristive = score > 60
        return {'analysis_data': analysis_data, 'is_memristive': is_memristive}
    
    return analysis_data
```

### 1.2 Update Custom Measurement Runner

**File**: [`gui/measurement_gui/main.py`](gui/measurement_gui/main.py)

In `run_custom_measurement()` (line ~4140), add tracking:

```python
# At start of method
device_is_memristive = None
sequence_analysis_results = []

# In sweep loop (line ~4733)
analysis_result = self._run_analysis_if_enabled(
    voltage=v_arr,
    current=c_arr,
    timestamps=t_arr,
    save_dir=save_dir,
    file_name=file_name,
    metadata=metadata,
    is_custom_sequence=True,
    sweep_number=key,
    device_memristive_flag=device_is_memristive
)

# Update flag after first sweep
if key == 1 and analysis_result:
    device_is_memristive = analysis_result.get('is_memristive', False)

# Collect results
if analysis_result:
    analysis_data = analysis_result.get('analysis_data') or analysis_result
    sequence_analysis_results.append({
        'sweep_number': key,
        'voltage': params.get('stop_v'),
        'analysis': analysis_data
    })
    
    # Update live display
    self._update_live_classification_display(
        sweep_num=key,
        total_sweeps=len(sweeps),
        classification_data=analysis_data.get('classification', {})
    )

# After all sweeps complete
if sequence_analysis_results:
    self._generate_sequence_summary(
        device_id=f"{sample_name}_{device_letter}_{device_number}",
        sequence_name=selected_measurement,
        sequence_results=sequence_analysis_results,
        save_dir=save_dir,
        total_sweeps=len(sweeps)
    )
```

### 1.3 Live Classification Display

Add methods to [`gui/measurement_gui/main.py`](gui/measurement_gui/main.py):

```python
def _update_live_classification_display(
    self, sweep_num: int, total_sweeps: int, 
    classification_data: Dict[str, Any]
) -> None:
    """Update GUI with live progress: 'Sweep 5/20: Memristive (Score: 75.2)'"""
    try:
        device_type = classification_data.get('device_type', 'unknown')
        score = classification_data.get('memristivity_score', 0)
        
        status_msg = f"Sweep {sweep_num}/{total_sweeps}: {device_type.title()} (Score: {score:.1f}/100)"
        
        if hasattr(self, 'status_label'):
            self.status_label.config(text=status_msg)
        
        self.master.update_idletasks()
        print(f"[LIVE] {status_msg}")
    except Exception as e:
        print(f"[LIVE] Error: {e}")

def _send_classification_notification(
    self, device_id: str, classification_data: Dict[str, Any]
) -> None:
    """
    PLACEHOLDER for future notifications (Telegram/Email/Webhook).
    
    TODO: Implement for:
    - Device becomes memristive
    - Score exceeds threshold
    - Degradation detected
    - Sequence complete
    """
    pass
```

### 1.4 Sequence Summary Report Generator

Add to [`gui/measurement_gui/main.py`](gui/measurement_gui/main.py):

```python
def _generate_sequence_summary(
    self,
    device_id: str,
    sequence_name: str,
    sequence_results: List[Dict[str, Any]],
    save_dir: str,
    total_sweeps: int
) -> None:
    """
    Generate comprehensive summary for custom measurement sequences.
    Creates text + JSON files in device_summaries/ folder.
    """
    import os, json, numpy as np
    from datetime import datetime
    
    # Create summaries directory
    sample_save_dir = self._get_sample_save_directory(self.sample_name_var.get())
    summary_dir = os.path.join(sample_save_dir, "device_summaries")
    os.makedirs(summary_dir, exist_ok=True)
    
    # Extract metrics
    scores = []
    voltages = []
    best_sweep = None
    worst_sweep = None
    
    for result in sequence_results:
        classification = result['analysis'].get('classification', {})
        score = classification.get('memristivity_score', 0)
        scores.append(score)
        voltages.append(result['voltage'])
        
        if best_sweep is None or score > best_sweep['score']:
            best_sweep = {'sweep': result['sweep_number'], 'score': score, 'voltage': result['voltage']}
        if worst_sweep is None or score < worst_sweep['score']:
            worst_sweep = {'sweep': result['sweep_number'], 'score': score, 'voltage': result['voltage']}
    
    # Overall score (weighted average favoring later sweeps)
    weights = np.linspace(0.5, 1.0, len(scores))
    overall_score = np.average(scores, weights=weights) if scores else 0
    
    # Detect forming
    score_improvement = scores[-1] - scores[0] if len(scores) > 1 else 0
    is_forming = score_improvement > 15
    
    # Build text report
    lines = ["=" * 80,
             "CUSTOM MEASUREMENT SEQUENCE SUMMARY",
             "=" * 80,
             f"Device: {device_id}",
             f"Sequence: {sequence_name}",
             f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
             f"Overall Score: {overall_score:.1f}/100",
             "",
             "KEY SWEEPS",
             "-" * 80,
             f"Best: Sweep #{best_sweep['sweep']} @ {best_sweep['voltage']:.1f}V (Score: {best_sweep['score']:.1f})",
             f"Worst: Sweep #{worst_sweep['sweep']} @ {worst_sweep['voltage']:.1f}V (Score: {worst_sweep['score']:.1f})",
             ""]
    
    # Save files
    text_file = os.path.join(summary_dir, f"{device_id}_{sequence_name}_summary.txt")
    json_file = os.path.join(summary_dir, f"{device_id}_{sequence_name}_summary.json")
    
    with open(text_file, 'w') as f:
        f.write('\n'.join(lines))
    
    json_summary = {
        'device_id': device_id,
        'overall_score': float(overall_score),
        'best_sweep': best_sweep,
        'worst_sweep': worst_sweep,
        'sweep_progression': [
            {'sweep_number': r['sweep_number'], 
             'voltage': r['voltage'],
             'score': r['analysis'].get('classification', {}).get('memristivity_score', 0)}
            for r in sequence_results
        ]
    }
    
    with open(json_file, 'w') as f:
        json.dump(json_summary, f, indent=2)
    
    print(f"[SUMMARY] Saved: {text_file}")
```

---

## Part 2: Full Sample Analysis System

### 2.1 Create Sample Analysis Module

**New File**: [`Helpers/Sample_Analysis/sample_analyzer.py`](Helpers/Sample_Analysis/sample_analyzer.py)

```python
"""
Sample-level analysis orchestrator using existing device tracking and research data.
Generates comprehensive plots and statistics for entire samples (100+ devices).
"""

import os
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Tuple, Optional
from datetime import datetime

class SampleAnalysisOrchestrator:
    """Orchestrate full sample analysis with 12 advanced plot types."""
    
    def __init__(self, sample_directory: str):
        """
        Args:
            sample_directory: Path to sample folder containing device_tracking/, 
                            device_research/, etc.
        """
        self.sample_dir = sample_directory
        self.sample_name = os.path.basename(sample_directory)
        
        # Data directories
        self.tracking_dir = os.path.join(sample_directory, "device_tracking")
        self.research_dir = os.path.join(sample_directory, "device_research")
        self.summaries_dir = os.path.join(sample_directory, "device_summaries")
        
        # Output directories
        self.output_dir = os.path.join(sample_directory, "sample_analysis")
        self.plots_dir = os.path.join(self.output_dir, "plots")
        self.origin_dir = os.path.join(self.output_dir, "origin_data")
        
        # Create output directories
        os.makedirs(self.plots_dir, exist_ok=True)
        os.makedirs(self.origin_dir, exist_ok=True)
        
        # Data containers
        self.devices_data = []
        self.memristive_devices = []
        
    def load_all_devices(self) -> int:
        """Load all device tracking data."""
        count = 0
        if not os.path.exists(self.tracking_dir):
            print(f"[SAMPLE] No tracking directory found: {self.tracking_dir}")
            return 0
        
        for file in os.listdir(self.tracking_dir):
            if file.endswith('_history.json'):
                try:
                    with open(os.path.join(self.tracking_dir, file), 'r') as f:
                        data = json.load(f)
                        device_id = data.get('device_id', file.replace('_history.json', ''))
                        
                        # Get latest measurement
                        if data.get('measurements'):
                            latest = data['measurements'][-1]
                            
                            device_info = {
                                'device_id': device_id,
                                'classification': latest.get('classification', {}),
                                'resistance': latest.get('resistance', {}),
                                'voltage': latest.get('voltage', {}),
                                'hysteresis': latest.get('hysteresis', {}),
                                'quality': latest.get('quality', {}),
                                'warnings': latest.get('warnings', []),
                                'total_measurements': data.get('total_measurements', 0)
                            }
                            
                            self.devices_data.append(device_info)
                            
                            # Track memristive devices
                            if device_info['classification'].get('device_type') == 'memristive':
                                self.memristive_devices.append(device_info)
                            
                            count += 1
                except Exception as e:
                    print(f"[SAMPLE] Error loading {file}: {e}")
        
        print(f"[SAMPLE] Loaded {count} devices ({len(self.memristive_devices)} memristive)")
        return count
    
    def generate_all_plots(self) -> None:
        """Generate all 12 plot types."""
        print(f"[SAMPLE] Generating plots for {self.sample_name}...")
        
        # Plot 1: Memristivity Score Heatmap
        self.plot_memristivity_heatmap()
        
        # Plot 2: Conduction Mechanism Distribution
        self.plot_conduction_mechanisms()
        
        # Plot 3: Memory Window Quality Distribution
        self.plot_memory_window_quality()
        
        # Plot 4: Hysteresis Shape Radar (memristive only)
        self.plot_hysteresis_radar()
        
        # Plot 5: Enhanced Classification Scatter
        self.plot_classification_scatter()
        
        # Plot 6: Forming Progress Tracking
        self.plot_forming_progress()
        
        # Plot 7: Warning Flag Summary
        self.plot_warning_summary()
        
        # Plot 8: Research Diagnostics Scatter Matrix
        self.plot_research_diagnostics()
        
        # Plot 9: Power & Energy Efficiency
        self.plot_power_efficiency()
        
        # Plot 10: Device Leaderboard
        self.plot_device_leaderboard()
        
        # Plot 11: Spatial Distribution Maps
        self.plot_spatial_distributions()
        
        # Plot 12: Forming Status Distribution
        self.plot_forming_status()
        
        print(f"[SAMPLE] All plots saved to: {self.plots_dir}")
    
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
        self._export_power_efficiency_data()
        self._export_leaderboard_data()
        self._export_spatial_data()
        
        # Create README for Origin import
        self._create_origin_readme()
        
        print(f"[SAMPLE] Origin data exported to: {self.origin_dir}")
    
    # === PLOT 1: Memristivity Score Heatmap ===
    def plot_memristivity_heatmap(self) -> None:
        """Color-coded heatmap of memristivity scores across sample."""
        # Parse device IDs to extract position (e.g., "sample_A_5" -> row=A, col=5)
        # Create 2D grid and plot as heatmap
        # Color scale: Red (0-40) → Orange (40-60) → Yellow (60-80) → Green (80-100)
        pass  # Implementation details...
    
    def _export_memristivity_heatmap_data(self) -> None:
        """Export as CSV with columns: Device_ID, Row, Column, Memristivity_Score"""
        pass
    
    # === PLOT 2: Conduction Mechanism Distribution ===
    def plot_conduction_mechanisms(self) -> None:
        """Pie + bar chart of conduction mechanism distribution."""
        pass
    
    # ... (Additional plot methods) ...
    
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
                'Memory_Window_Quality': dev['quality'].get('memory_window_quality', np.nan),
                'Has_Hysteresis': dev['hysteresis'].get('has_hysteresis', False),
                'Pinched': dev['hysteresis'].get('pinched', False),
                'Warning_Count': len(dev['warnings']),
                'Total_Measurements': dev['total_measurements']
            })
        
        df = pd.DataFrame(rows)
        output_file = os.path.join(self.origin_dir, 'device_summary.csv')
        df.to_csv(output_file, index=False)
        print(f"[ORIGIN] Exported: device_summary.csv")
    
    def _create_origin_readme(self) -> None:
        """Create README with import instructions for Origin."""
        readme = """
# Origin Data Import Guide

## Files Overview

All data files are in CSV format with headers, optimized for Origin import.

### Main Files:
- `device_summary.csv`: Complete device-level summary (all metrics)
- `memristivity_heatmap.csv`: Device positions and scores for heatmap
- `conduction_mechanisms.csv`: Mechanism distribution data
- `memory_window_quality.csv`: Quality metrics for all devices
- `classification_scatter.csv`: Ron/Roff data with classification
- `power_efficiency.csv`: Power and energy metrics
- `device_leaderboard.csv`: Ranked device performance
- `spatial_data.csv`: Spatial distribution data

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
- X = Column, Y = Row

**Scatter (classification_scatter.csv):**
- Plot → 2D: Scatter
- X = Ron_Mean (log scale)
- Y = Roff_Mean (log scale)
- Color by: Memristivity_Score
- Size by: Switching_Ratio

**Bar Chart (conduction_mechanisms.csv):**
- Plot → 2D: Column/Bar
- X = Mechanism, Y = Count

## Notes:
- All resistance values are in Ohms
- Scores are 0-100 scale
- NaN values indicate data not available
"""
        
        readme_file = os.path.join(self.origin_dir, 'README_ORIGIN_IMPORT.txt')
        with open(readme_file, 'w') as f:
            f.write(readme.strip())
        print(f"[ORIGIN] Created: README_ORIGIN_IMPORT.txt")
```

### 2.2 Implement All 12 Plot Methods

Each plot method in `sample_analyzer.py` should:

1. Generate matplotlib figure
2. Save to `plots/` directory
3. Call corresponding `_export_*_data()` method to save Origin CSV

**Plot Implementation Pattern**:

```python
def plot_memristivity_heatmap(self) -> None:
    """Plot 1: Memristivity Score Heatmap"""
    try:
        # Extract device positions and scores
        positions = {}  # {(row, col): score}
        
        for dev in self.devices_data:
            device_id = dev['device_id']
            # Parse "sample_A_5" -> row=A, col=5
            parts = device_id.split('_')
            if len(parts) >= 3:
                row = parts[-2]  # Letter
                col = int(parts[-1])  # Number
                score = dev['classification'].get('memristivity_score', 0)
                positions[(row, col)] = score
        
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
        fig, ax = plt.subplots(figsize=(12, 8))
        
        # Custom colormap: Red → Orange → Yellow → Green
        colors = ['#d62728', '#ff7f0e', '#ffd700', '#2ca02c']
        n_bins = 100
        cmap = plt.matplotlib.colors.LinearSegmentedColormap.from_list('memristivity', colors, N=n_bins)
        
        im = ax.imshow(grid, cmap=cmap, vmin=0, vmax=100, aspect='auto')
        
        # Labels
        ax.set_xticks(range(len(cols)))
        ax.set_xticklabels(cols)
        ax.set_yticks(range(len(rows)))
        ax.set_yticklabels(rows)
        
        ax.set_xlabel('Device Number', fontsize=12)
        ax.set_ylabel('Section', fontsize=12)
        ax.set_title(f'Memristivity Score Heatmap - {self.sample_name}', fontsize=14, fontweight='bold')
        
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

def _export_memristivity_heatmap_data(self, positions: Dict) -> None:
    """Export heatmap data for Origin."""
    rows = []
    for (row, col), score in positions.items():
        rows.append({
            'Device_ID': f"{self.sample_name}_{row}_{col}",
            'Section': row,
            'Device_Number': col,
            'Memristivity_Score': score
        })
    
    df = pd.DataFrame(rows)
    output_file = os.path.join(self.origin_dir, 'memristivity_heatmap.csv')
    df.to_csv(output_file, index=False)
    print(f"[ORIGIN] Exported: memristivity_heatmap.csv")
```

**Implement similar patterns for all 12 plots:**

- Plot 2: Conduction mechanisms (pie + bar)
- Plot 3: Memory window quality (box plots)
- Plot 4: Hysteresis radar charts
- Plot 5: Classification scatter (Ron vs Roff)
- Plot 6: Forming progress (time series)
- Plot 7: Warning summary (bar chart)
- Plot 8: Research diagnostics (pairplot)
- Plot 9: Power efficiency (scatter + distribution)
- Plot 10: Leaderboard (horizontal bar)
- Plot 11: Spatial distributions (multiple heatmaps)
- Plot 12: Forming status (pie chart)

### 2.3 GUI Integration - Graphing Tab

**File**: [`gui/measurement_gui/layout_builder.py`](gui/measurement_gui/layout_builder.py)

Add graphing tab in `_build_tabbed_content()`:

```python
def _create_graphing_tab(self, parent) -> ttk.Frame:
    """Create tab for sample analysis and plotting."""
    frame = ttk.Frame(parent)
    
    # Title
    title = tk.Label(frame, text="Sample Analysis & Plotting", 
                     font=('Arial', 14, 'bold'))
    title.pack(pady=10)
    
    # Description
    desc = tk.Label(frame, 
                    text="Generate comprehensive analysis plots for entire sample using existing data",
                    font=('Arial', 10), wraplength=600)
    desc.pack(pady=5)
    
    # Button frame
    btn_frame = ttk.Frame(frame)
    btn_frame.pack(pady=20)
    
    # Main analysis button
    analyze_btn = ttk.Button(
        btn_frame,
        text="Run Full Sample Analysis",
        command=gui.run_full_sample_analysis,
        width=30
    )
    analyze_btn.pack(pady=10)
    
    # Status label
    gui.analysis_status_label = tk.Label(frame, text="", font=('Arial', 10))
    gui.analysis_status_label.pack(pady=10)
    
    # Progress info
    info_text = """
This will:
• Load all device tracking data
• Generate 12 advanced plot types
• Export Origin-ready data files
• Create comprehensive sample report

No re-analysis performed - uses existing data only.
Suitable for 100+ device samples.
    """
    info_label = tk.Label(frame, text=info_text, font=('Arial', 9), 
                         justify='left', bg='#f0f0f0')
    info_label.pack(pady=10, padx=20, fill='x')
    
    return frame
```

Add to notebook in `_build_tabbed_content()`:

```python
# Existing tabs...
self.notebook.add(self._create_measurement_tab(self.notebook), text="Measurement")
self.notebook.add(self._create_stats_tab(self.notebook), text="Stats")
self.notebook.add(self._create_graphing_tab(self.notebook), text="Graphing")  # NEW
```

### 2.4 GUI Logic - Sample Analysis Trigger

**File**: [`gui/measurement_gui/main.py`](gui/measurement_gui/main.py)

Add method to trigger sample analysis:

```python
def run_full_sample_analysis(self) -> None:
    """Run comprehensive sample analysis with all plots."""
    try:
        sample_name = self.sample_name_var.get()
        if not sample_name:
            messagebox.showwarning("No Sample", "Please select a sample first")
            return
        
        # Get sample directory
        sample_dir = self._get_sample_save_directory(sample_name)
        
        if not os.path.exists(sample_dir):
            messagebox.showerror("Error", f"Sample directory not found: {sample_dir}")
            return
        
        # Update status
        if hasattr(self, 'analysis_status_label'):
            self.analysis_status_label.config(text="Loading device data...")
            self.master.update_idletasks()
        
        print(f"[SAMPLE ANALYSIS] Starting analysis for: {sample_name}")
        
        # Import analyzer
        from Helpers.Sample_Analysis.sample_analyzer import SampleAnalysisOrchestrator
        
        # Create orchestrator
        analyzer = SampleAnalysisOrchestrator(sample_dir)
        
        # Load devices
        device_count = analyzer.load_all_devices()
        
        if device_count == 0:
            messagebox.showwarning("No Data", "No device tracking data found for this sample")
            return
        
        # Update status
        if hasattr(self, 'analysis_status_label'):
            self.analysis_status_label.config(text=f"Generating plots for {device_count} devices...")
            self.master.update_idletasks()
        
        # Generate all plots
        analyzer.generate_all_plots()
        
        # Export Origin data
        if hasattr(self, 'analysis_status_label'):
            self.analysis_status_label.config(text="Exporting Origin data...")
            self.master.update_idletasks()
        
        analyzer.export_origin_data()
        
        # Success
        output_dir = analyzer.output_dir
        plots_dir = analyzer.plots_dir
        origin_dir = analyzer.origin_dir
        
        messagebox.showinfo(
            "Analysis Complete",
            f"Sample analysis complete!\n\n"
            f"Devices analyzed: {device_count}\n"
            f"Plots saved to: {plots_dir}\n"
            f"Origin data: {origin_dir}\n\n"
            f"Check the output folder for all results."
        )
        
        # Update status
        if hasattr(self, 'analysis_status_label'):
            self.analysis_status_label.config(text=f"✓ Complete - {device_count} devices analyzed")
        
        print(f"[SAMPLE ANALYSIS] Complete!")
        print(f"[SAMPLE ANALYSIS] Plots: {plots_dir}")
        print(f"[SAMPLE ANALYSIS] Origin data: {origin_dir}")
        
        # Optionally open output folder
        import subprocess
        subprocess.Popen(f'explorer "{plots_dir}"')
        
    except Exception as e:
        error_msg = f"Sample analysis failed: {e}"
        print(f"[SAMPLE ANALYSIS ERROR] {error_msg}")
        import traceback
        traceback.print_exc()
        
        messagebox.showerror("Analysis Error", error_msg)
        
        if hasattr(self, 'analysis_status_label'):
            self.analysis_status_label.config(text=f"✗ Error: {e}")
```

---

## Part 3: Origin Data Export Format

### 3.1 CSV Format Standards

All Origin data files follow these standards:

- **Format**: CSV (comma-delimited)
- **Headers**: First row contains column names
- **Encoding**: UTF-8
- **Numeric precision**: 6 significant figures
- **Missing data**: Empty cell or "NaN"
- **Boolean values**: "True"/"False" strings

### 3.2 File Structure

```
sample_analysis/
├── plots/                              # All matplotlib figures
│   ├── 01_memristivity_heatmap.png
│   ├── 02_conduction_mechanisms.png
│   ├── 03_memory_window_quality.png
│   ├── 04_hysteresis_radar.png
│   ├── 05_classification_scatter.png
│   ├── 06_forming_progress.png
│   ├── 07_warning_summary.png
│   ├── 08_research_diagnostics.png
│   ├── 09_power_efficiency.png
│   ├── 10_device_leaderboard.png
│   ├── 11_spatial_distributions.png
│   └── 12_forming_status.png
│
└── origin_data/                        # Origin-ready CSV files
    ├── README_ORIGIN_IMPORT.txt       # Import instructions
    ├── device_summary.csv             # Main dataset (all metrics)
    ├── memristivity_heatmap.csv       # Plot 1 data
    ├── conduction_mechanisms.csv      # Plot 2 data
    ├── memory_window_quality.csv      # Plot 3 data
    ├── hysteresis_shapes.csv          # Plot 4 data
    ├── classification_scatter.csv     # Plot 5 data
    ├── forming_progress.csv           # Plot 6 data
    ├── warning_summary.csv            # Plot 7 data
    ├── research_diagnostics.csv       # Plot 8 data
    ├── power_efficiency.csv           # Plot 9 data
    ├── device_leaderboard.csv         # Plot 10 data
    ├── spatial_memristivity.csv       # Plot 11a data
    ├── spatial_quality.csv            # Plot 11b data
    ├── spatial_switching.csv          # Plot 11c data
    └── forming_status.csv             # Plot 12 data
```

### 3.3 Example CSV Files

**device_summary.csv** (comprehensive):

```csv
Device_ID,Device_Type,Memristivity_Score,Confidence,Conduction_Mechanism,Ron_Mean,Roff_Mean,Switching_Ratio,Memory_Window_Quality,Has_Hysteresis,Pinched,Warning_Count
test_A_1,memristive,85.3,1.0,trap_sclc,1.2e-09,8.5e+06,7083333,75.0,True,True,0
test_A_2,ohmic,12.5,0.95,ohmic,5.0e+03,5.5e+03,1.1,0.0,False,False,2
test_B_1,memristive,72.1,1.0,sclc,3.4e-08,1.2e+07,352941,68.0,True,True,1
```

**memristivity_heatmap.csv**:

```csv
Device_ID,Section,Device_Number,Memristivity_Score
test_A_1,A,1,85.3
test_A_2,A,2,12.5
test_B_1,B,1,72.1
```

**classification_scatter.csv** (for Ron vs Roff):

```csv
Device_ID,Ron_Mean,Roff_Mean,Switching_Ratio,Memristivity_Score,Device_Type,Pinched
test_A_1,1.2e-09,8.5e+06,7083333,85.3,memristive,True
test_A_2,5.0e+03,5.5e+03,1.1,12.5,ohmic,False
```

---

## Part 4: Plot Details (All 12)

### Plot 1: Memristivity Score Heatmap

- **Type**: 2D color heatmap
- **Data**: Device position (row/col) vs score (0-100)
- **Colors**: Red (0-40) → Orange (40-60) → Yellow (60-80) → Green (80-100)
- **Features**: Score text overlaid on cells

### Plot 2: Conduction Mechanism Distribution

- **Type**: Pie chart + bar chart (side-by-side)
- **Data**: Count of each mechanism (ohmic, SCLC, trap_SCLC, etc.)
- **Features**: Percentage labels, sorted by frequency

### Plot 3: Memory Window Quality Distribution

- **Type**: Box plot (grouped)
- **Metrics**: Ron stability, Roff stability, separation ratio, overall quality
- **Features**: Outlier detection, mean markers

### Plot 4: Hysteresis Shape Radar (Memristive Only)

- **Type**: Radar/spider chart
- **Axes**: Figure-8 quality, smoothness, lobe asymmetry, width variation
- **Features**: Average + individual device overlay option

### Plot 5: Enhanced Classification Scatter

- **Type**: Scatter plot (Ron vs Roff, log-log scale)
- **Encoding**: Color = memristivity score, Size = switching ratio, Shape = device type
- **Features**: Reference lines for thresholds

### Plot 6: Forming Progress Tracking

- **Type**: Multi-line plot
- **Data**: Memristivity score vs measurement number for each device
- **Features**: Color-coded by final status (formed/forming/degrading)

### Plot 7: Warning Flag Summary

- **Type**: Horizontal bar chart
- **Data**: Count of each warning type across sample
- **Features**: Sorted by frequency, affected device list

### Plot 8: Research Diagnostics Scatter Matrix

- **Type**: Pairplot (seaborn style)
- **Variables**: NDR index, kink voltage, pinch offset, noise floor
- **Features**: Diagonal = distributions, off-diagonal = correlations

### Plot 9: Power & Energy Efficiency

- **Type**: Dual scatter plots
- **Plots**: 
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Power consumption vs memristivity score
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Energy per switch distribution (box plot by device type)
- **Features**: Efficiency frontier highlighting

### Plot 10: Device Leaderboard

- **Type**: Horizontal bar chart (ranked)
- **Score**: Composite from memristivity (40%), quality (30%), switching ratio (20%), stability (10%)
- **Features**: Top 20 devices, color-coded tiers

### Plot 11: Spatial Distribution Maps

- **Type**: 3x heatmaps (side-by-side)
- **Maps**: Memristivity score, memory window quality, switching ratio
- **Features**: Identify spatial patterns/clusters

### Plot 12: Forming Status Distribution

- **Type**: Pie chart + device list
- **Categories**: Forming (blue), Formed (green), Degrading (red), Unstable (orange)
- **Features**: Auto-classification from measurement history

---

## Implementation Priorities

### Phase 1: Core Functionality

1. ✅ Conditional custom measurement analysis
2. ✅ Live classification display
3. ✅ Sequence summary reports
4. ✅ Sample analysis orchestrator skeleton
5. ✅ Graphing tab UI

### Phase 2: Essential Plots (Must-Have)

6. Plot 1: Memristivity heatmap
7. Plot 2: Conduction mechanisms
8. Plot 3: Memory window quality
9. Plot 10: Device leaderboard
10. Origin data export for above

### Phase 3: Advanced Plots (Research-Level)

11. Plot 5: Classification scatter
12. Plot 6: Forming progress
13. Plot 7: Warning summary
14. Plot 11: Spatial distributions
15. Plot 12: Forming status

### Phase 4: Specialized Plots (Publication-Quality)

16. Plot 4: Hysteresis radar
17. Plot 8: Research diagnostics
18. Plot 9: Power efficiency
19. Complete Origin export for all plots

---

## Testing Plan

1. **Test conditional analysis**: Run custom measurement on 1 device
2. **Verify summaries**: Check device_summaries/ folder content
3. **Test sample analysis**: Run on sample with 5-10 devices
4. **Validate plots**: Check all 12 plots generate correctly
5. **Test Origin export**: Import CSV into Origin and recreate plots
6. **Full sample test**: Run on 100+ device sample overnight

---

## File Locations Summary

**Modified Files**:

- `gui/measurement_gui/main.py` (conditional analysis, live display, summaries, sample analysis trigger)
- `gui/measurement_gui/layout_builder.py` (graphing tab)

**New Files**:

- `Helpers/Sample_Analysis/sample_analyzer.py` (orchestrator with all 12 plot methods)
- `Helpers/Sample_Analysis/__init__.py`

**New Directories Created at Runtime**:

- `{sample_dir}/device_summaries/` (sequence summaries)
- `{sample_dir}/sample_analysis/` (main output)
- `{sample_dir}/sample_analysis/plots/` (all PNG figures)
- `{sample_dir}/sample_analysis/origin_data/` (all CSV files)

---

## Implementation Status (Updated)

### ✅ FULLY IMPLEMENTED

#### Part 1: Custom Measurement Analysis

1. **Conditional Analysis Logic** ✅

                                                - `_run_analysis_if_enabled()` modified with conditional logic (lines 775-996 in main.py)
                                                - Skips analysis for sweeps 2+ if device is not memristive
                                                - Returns memristive flag after first sweep

2. **Custom Measurement Tracking** ✅

                                                - `run_custom_measurement()` tracks `device_is_memristive` flag (line 5767)
                                                - Collects `sequence_analysis_results` across all sweeps (lines 6260-6307)
                                                - Updates memristive flag after first sweep analysis (lines 6254-6257)

3. **Live Classification Display** ✅

                                                - `_update_live_classification_display()` method implemented (lines 706-744)
                                                - Called during custom measurements (lines 6290-6294)
                                                - Shows: "Sweep X/Y: DeviceType (Score: Z.Z/100)"

4. **Notification Placeholder** ✅

                                                - `_send_classification_notification()` placeholder method exists (lines 746-751)
                                                - Ready for future integration (Telegram/Email/Webhook)

5. **Sequence Summary Generator** ✅

                                                - `_generate_sequence_summary()` fully implemented (lines 1464-1497)
                                                - Generates text and JSON summary files
                                                - Calculates overall score, best/worst sweeps, forming detection
                                                - Called after custom measurement completion (lines 6392-6399)

#### Part 2: Sample Analysis System

6. **Sample Analysis Orchestrator** ✅

                                                - `SampleAnalysisOrchestrator` class fully implemented (`Helpers/Sample_Analysis/sample_analyzer.py`)
                                                - `load_all_devices()` method loads tracking data
                                                - Supports code_name filtering for measurement-specific analysis

7. **All 12 Plot Types** ✅

                                                - Plot 1: Memristivity Score Heatmap (lines 288-370)
                                                - Plot 2: Conduction Mechanism Distribution (lines 403-449)
                                                - Plot 3: Memory Window Quality Distribution (lines 466-536)
                                                - Plot 4: Hysteresis Shape Radar (lines 568-632)
                                                - Plot 5: Enhanced Classification Scatter (lines 635-712)
                                                - Plot 6: Forming Progress Tracking (lines 739-795)
                                                - Plot 7: Warning Flag Summary (lines 798-849)
                                                - Plot 8: Research Diagnostics Scatter Matrix (lines 851-901)
                                                - Plot 9: Power & Energy Efficiency (lines 903-962)
                                                - Plot 10: Device Leaderboard (lines 987-1070)
                                                - Plot 11: Spatial Distribution Maps (lines 1108-1243)
                                                - Plot 12: Forming Status Distribution (lines 1245-1312)

8. **Origin Data Export** ✅

                                                - All export methods implemented:
                                                                                - `_export_device_summary_csv()` (lines 1356-1379)
                                                                                - `_export_memristivity_heatmap_data()` (lines 371-401)
                                                                                - `_export_conduction_mechanism_data()` (lines 450-464)
                                                                                - `_export_memory_window_data()` (lines 537-566)
                                                                                - `_export_classification_scatter_data()` (lines 714-737)
                                                                                - `_export_power_efficiency_data()` (lines 964-985)
                                                                                - `_export_leaderboard_data()` (lines 1072-1106)
                                                                                - `_export_spatial_data()` (lines 1203-1243)
                                                                                - `_export_forming_status_data()` (lines 1314-1339)
                                                - `_create_origin_readme()` generates import instructions (lines 1381+)

9. **GUI Integration** ✅

                                                - Graphing tab added to GUI (`gui/measurement_gui/layout_builder.py`, lines 2321+)
                                                - `run_full_sample_analysis()` method implemented (lines 2321-2420 in main.py)
                                                - Supports folder browsing for retroactive analysis
                                                - Status updates during analysis

### ⚠️ POTENTIALLY MISSING / NEEDS VERIFICATION

1. **Full System Testing** ⚠️

                                                - Status: `pending` in todos
                                                - Need to verify end-to-end: custom measurement → sample analysis → Origin export
                                                - Should test with real data to ensure all plots generate correctly

2. **Plot Data Requirements** ⚠️

                                                - Some plots require specific data:
                                                                                - Plot 4 (Hysteresis Radar): Requires research data with hysteresis_shape
                                                                                - Plot 6 (Forming Progress): Requires `all_measurements` in device data
                                                                                - Plot 8 (Research Diagnostics): Requires research data
                                                                                - Plot 9 (Power Efficiency): Requires research data
                                                - Need to verify these data structures are populated correctly

3. **Error Handling** ⚠️

                                                - Plots have try-except blocks, but need verification that errors are handled gracefully
                                                - Should test with incomplete/missing data scenarios

4. **Performance Testing** ⚠️

                                                - Need to verify performance with 100+ device samples
                                                - Plot generation time for large datasets

### 📝 NOTES

- **Implementation Quality**: All code appears to be fully implemented (not stubs)
- **Code Location**: All implementations match the plan's specified file locations
- **Integration**: Custom measurement analysis is integrated into the main measurement flow
- **Data Flow**: Sequence summaries → device_summaries/, Sample analysis → sample_analysis/

### 🔍 RECOMMENDED NEXT STEPS

1. **Run Full System Test**:

                                                - Execute custom measurement on a test device
                                                - Verify sequence summary generation
                                                - Run sample analysis on a small sample (5-10 devices)
                                                - Verify all 12 plots generate
                                                - Test Origin CSV import

2. **Data Validation**:

                                                - Verify `all_measurements` array is populated in device tracking
                                                - Verify research data structure matches plot expectations
                                                - Check that device_summaries/ folder structure is correct

3. **Documentation**:

                                                - Update user documentation with new features
                                                - Add examples of generated plots
                                                - Document Origin import process