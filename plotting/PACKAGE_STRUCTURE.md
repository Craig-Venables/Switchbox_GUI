# Package Structure

```
plotting/
├── __init__.py              # Package exports (UnifiedPlotter, SamplePlots, style, etc.)
├── __version__.py           # Version information
├── core/                    # Shared infrastructure
│   ├── __init__.py
│   ├── base.py              # PlotManager - core saving utility
│   ├── style.py             # DPI, figsize, font presets
│   └── formatters.py        # plain_log_formatter and shared axis helpers
├── device/                  # Device-level IV, conduction, SCLC, combined sweeps
│   ├── __init__.py
│   ├── iv_grid.py           # IVGridPlotter - 2x2 IV dashboard
│   ├── conduction.py        # ConductionPlotter - mechanism analysis
│   ├── sclc_fit.py          # SCLCFitPlotter - SCLC slope fitting
│   ├── hdf5_style.py        # HDF5StylePlotter - statistical plots
│   ├── unified_plotter.py   # UnifiedPlotter - main entry point
│   └── device_combined_plots.py  # plot_device_combined_sweeps
├── sample/                  # Sample-level analysis (Run Full Sample Analysis)
│   ├── __init__.py
│   └── sample_plots.py      # SamplePlots class
├── section/                 # Section-level plots
│   ├── __init__.py
│   └── section_plots.py     # plot_sweeps_by_type, plot_statistical_comparisons, etc.
├── endurance/               # DC endurance plots
│   ├── __init__.py
│   └── endurance_plots.py  # plot_current_vs_cycle, plot_endurance_summary
├── section_plots.py         # Re-export for backward compatibility
├── device_combined_plots.py # Re-export for backward compatibility
├── endurance_plots.py       # Re-export for backward compatibility
├── sample_plots.py          # Re-export for backward compatibility
├── setup.py                 # Package installation script
├── requirements.txt         # Python dependencies
├── README.md                # Main documentation
├── CATALOG.md               # Plot catalog – where each graph lives
├── INSTALL.md               # Installation guide
├── MANIFEST.in              # Package manifest
├── .gitignore               # Git ignore rules
└── examples/
    ├── basic_usage.py       # Simple usage example
    ├── conditional_plotting.py
    └── load_from_file.py    # File loading example
```

## Core Components

### UnifiedPlotter (Main Entry Point)
- Lives in `device/unified_plotter.py`
- Single class for all device-level plotting needs
- `plot_all()` - Generate all plots at once
- Individual methods for each plot type (IV, conduction, SCLC, endurance, retention, forming)
- Fully configurable via constructor

### Individual Plotters (device/)
- **IVGridPlotter**: 2x2 IV dashboard (linear, log, averaged, time)
- **ConductionPlotter**: Conduction mechanism analysis (SCLC, Schottky, PF)
- **SCLCFitPlotter**: SCLC slope fitting with windowed search
- **HDF5StylePlotter**: Statistical plots for multi-device data

### SamplePlots (sample/)
- Lives in `sample/sample_plots.py`
- Sample-level analysis: heatmaps, scatter, dashboards, forming, comparisons

### Utilities (core/)
- **PlotManager** (base.py): Handles file saving and directory management
- **style**: DPI, figsize presets, font sizes
- **formatters**: plain_log_formatter for log-scale axes

## Usage Pattern

```python
from plotting import UnifiedPlotter

# Initialize once
plotter = UnifiedPlotter(save_dir="output/plots")

# Use anywhere
plotter.plot_all(voltage, current, device_name="Device_1")
```

## Backward Compatibility

Existing imports continue to work:
- `from plotting import UnifiedPlotter, SamplePlots, style, endurance_plots`
- `from plotting.section_plots import plot_sweeps_by_type, ...`
- `from plotting.device_combined_plots import plot_device_combined_sweeps`
- `from plotting.sample_plots import SamplePlots`
- `from plotting.endurance_plots import plot_current_vs_cycle, plot_endurance_summary`

## Dependencies

- matplotlib >= 3.3.0
- numpy >= 1.19.0
- pandas >= 1.2.0
- seaborn >= 0.11.0 (optional, for advanced plots)

## Portability

This package is designed to be:
- **Self-contained**: No external project dependencies
- **Portable**: Copy folder or install as package
- **Modular**: core / device / sample / section / endurance for easier navigation and extension
- **Well-documented**: Clear examples and CATALOG.md for finding any plot
