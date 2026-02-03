# Package Structure

```
plotting_core/
├── __init__.py              # Package exports
├── __version__.py           # Version information
├── base.py                  # PlotManager - core saving utility
├── iv_grid.py              # IVGridPlotter - 2x2 IV dashboard
├── conduction.py            # ConductionPlotter - mechanism analysis
├── sclc_fit.py             # SCLCFitPlotter - SCLC slope fitting
├── hdf5_style.py           # HDF5StylePlotter - statistical plots
├── unified_plotter.py      # UnifiedPlotter - main entry point
├── setup.py                # Package installation script
├── requirements.txt        # Python dependencies
├── README.md               # Main documentation
├── INSTALL.md              # Installation guide
├── MANIFEST.in             # Package manifest
├── .gitignore              # Git ignore rules
└── examples/
    ├── basic_usage.py      # Simple usage example
    └── load_from_file.py   # File loading example
```

## Core Components

### UnifiedPlotter (Main Entry Point)
- Single class for all plotting needs
- `plot_all()` - Generate all plots at once
- Individual methods for each plot type
- Fully configurable via constructor

### Individual Plotters
- **IVGridPlotter**: 2x2 IV dashboard (linear, log, averaged, time)
- **ConductionPlotter**: Conduction mechanism analysis (SCLC, Schottky, PF)
- **SCLCFitPlotter**: SCLC slope fitting with windowed search
- **HDF5StylePlotter**: Statistical plots for multi-device data

### Utilities
- **PlotManager**: Handles file saving and directory management

## Usage Pattern

```python
from plotting_core import UnifiedPlotter

# Initialize once
plotter = UnifiedPlotter(save_dir="output/plots")

# Use anywhere
plotter.plot_all(voltage, current, device_name="Device_1")
```

## Dependencies

- matplotlib >= 3.3.0
- numpy >= 1.19.0
- pandas >= 1.2.0
- seaborn >= 0.11.0 (optional, for advanced plots)

## Portability

This package is designed to be:
- **Self-contained**: No external project dependencies
- **Portable**: Copy folder or install as package
- **Clean**: No hardcoded paths or project-specific code
- **Well-documented**: Clear examples and documentation

