# Plotting – one stop shop for all graphs

All graph generation for the app lives here. Change style in one place: [core/style.py](core/style.py). Find any plot: [CATALOG.md](CATALOG.md).

**Entry points:**
- **Device-level (IV, conduction, SCLC, endurance, retention, forming):** `from plotting import UnifiedPlotter`
- **Sample-level (Run Full Sample Analysis, plots 1–8):** `from plotting import SamplePlots` – build with `SamplePlots(devices_data, plots_dir, sample_name, ...)` then call `.plot_memristivity_heatmap()`, etc.
- **DC endurance:** `from plotting.endurance_plots import plot_current_vs_cycle, plot_endurance_summary`
- **Global style (dpi, figsize, fonts):** `from plotting import style` then `style.get_dpi()`, `style.get_figsize("heatmap")`, etc.

**Package layout:** [core/](core/) (style, base, formatters), [device/](device/) (unified_plotter, iv_grid, conduction, sclc_fit, hdf5_style, device_combined_plots), [sample/](sample/) (sample_plots), [section/](section/) (section_plots), [endurance/](endurance/) (endurance_plots). See CATALOG for the full list.

## Features

- **IV Dashboard**: 2x2 grid with linear IV, log IV, averaged IV with arrows, and current vs time
- **Conduction Analysis**: 2x2 grid for SCLC, Schottky, and Poole-Frenkel mechanism analysis
- **SCLC Fitting**: Automated slope detection and fitting for space-charge-limited current analysis
- **HDF5 Style Plots**: Statistical plots for multi-device analysis (concentration, yield, spacing, etc.)
- **Unified API**: Single entry point for all plotting functionality

## Installation

See `INSTALL.md` for detailed installation instructions.

### Quick Install

```bash
cd plotting
pip install -e .
pip install -r requirements.txt
```

### Copy Folder

Simply copy the `plotting` folder to your project and add to path:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path("path/to/plotting").parent))
from plotting import UnifiedPlotter
```

## Quick Start

### Basic Usage - Generate All Plots

```python
from plotting import UnifiedPlotter
import numpy as np

# Initialize plotter with output directory
plotter = UnifiedPlotter(save_dir="output/plots")

# Your data
voltage = np.array([...])  # Your voltage data
current = np.array([...])   # Your current data
time = np.array([...])      # Optional time data

# Generate all plots at once
results = plotter.plot_all(
    voltage=voltage,
    current=current,
    time=time,
    device_name="Device_1",
    title_prefix="Sample_A",
)

# Plots are automatically saved to output/plots/
# Files created:
# - Device_1_iv_dashboard.png
# - Device_1_conduction.png
# - Device_1_sclc_fit.png
```

### Conditional Plotting - Basic + Memristive Analysis

For batch processing, you can plot basic IV for all devices, but only generate expensive analysis for memristive devices:

```python
from plotting import UnifiedPlotter

plotter = UnifiedPlotter(save_dir="output/plots")

# Process all devices - always plot basic IV
for device in devices:
    voltage, current, time = load_device_data(device)
    
    # Always plot basic IV dashboard (fast)
    plotter.plot_basic(
        voltage=voltage,
        current=current,
        time=time,
        device_name=device.name,
    )
    
    # Only plot advanced analysis if device is memristive
    if is_memristive(voltage, current):
        plotter.plot_memristive_analysis(
            voltage=voltage,
            current=current,
            device_name=device.name,
        )
```

This approach:
- Generates basic IV dashboard for all devices (fast, always useful)
- Only generates conduction analysis and SCLC fitting for memristive devices (saves time/resources)

### Individual Plot Types

```python
from plotting import UnifiedPlotter

plotter = UnifiedPlotter(save_dir="plots")

# Just IV dashboard
plotter.plot_iv_dashboard(voltage, current, device_name="Device_1")

# Just conduction analysis
plotter.plot_conduction_analysis(voltage, current, device_name="Device_1")

# Just SCLC fit
plotter.plot_sclc_fit(voltage, current, device_name="Device_1")
```

### Advanced Configuration

```python
from plotting import UnifiedPlotter

plotter = UnifiedPlotter(
    save_dir="output/plots",
    # IV Dashboard settings
    iv_figsize=(14, 10),
    iv_arrows_points=15,
    # Conduction analysis settings
    target_slopes=(1.0, 2.0, 3.0),
    high_slope_min=4.0,
    enable_schottky_overlays=True,
    enable_pf_overlays=True,
    schottky_slope_bounds=(0.8, 1.2),
    pf_slope_bounds=(0.8, 1.2),
    # SCLC settings
    sclc_ref_slope=2.0,
)

results = plotter.plot_all(voltage, current, device_name="Device_1")
```

### Using Individual Plotters

```python
from plotting import IVGridPlotter, ConductionPlotter, SCLCFitPlotter

# IV Dashboard
iv_plotter = IVGridPlotter(save_dir="plots")
fig, axes = iv_plotter.plot_grid(
    voltage=voltage,
    current=current,
    time=time,
    title="My Device",
    save_name="device_iv.png",
)

# Conduction Analysis
cond_plotter = ConductionPlotter(
    save_dir="plots",
    target_slopes=(1, 2, 3),
    enable_schottky_overlays=True,
)
fig, axes = cond_plotter.plot_conduction_grid(
    voltage=voltage,
    current=current,
    title="Conduction Analysis",
    save_name="device_conduction.png",
)

# SCLC Fit
sclc_plotter = SCLCFitPlotter(save_dir="plots")
fig, ax = sclc_plotter.plot_sclc_fit(
    voltage=voltage,
    current=current,
    title="SCLC Fit",
    save_name="device_sclc.png",
)
```

### Interactive Mode (No Saving)

```python
from plotting import UnifiedPlotter

plotter = UnifiedPlotter(save_dir=None)  # Don't save, just display

results = plotter.plot_all(voltage, current, device_name="Device_1")

# Show all plots
plotter.show_all()  # or plt.show()
```

## API Reference

### UnifiedPlotter

Main entry point for all plotting functionality.

**Methods:**
- `plot_basic()`: Generate basic IV dashboard only (fast, recommended for all devices)
- `plot_memristive_analysis()`: Generate advanced analysis (conduction + SCLC) for memristive devices
- `plot_all()`: Generate all plots (convenience method)
- `plot_iv_dashboard()`: Generate IV dashboard only
- `plot_conduction_analysis()`: Generate conduction analysis only
- `plot_sclc_fit()`: Generate SCLC fit only
- `show_all()`: Display all open figures

### Individual Plotters

- `IVGridPlotter`: 2x2 IV dashboard
- `ConductionPlotter`: Conduction mechanism analysis
- `SCLCFitPlotter`: SCLC slope fitting
- `HDF5StylePlotter`: Statistical plots for multi-device data

## Requirements

- Python >= 3.7
- matplotlib >= 3.3.0
- numpy >= 1.19.0
- pandas >= 1.2.0
- seaborn >= 0.11.0 (optional, for advanced statistical plots)

## Examples

See the `examples/` directory for usage examples:
- `basic_usage.py`: Simple example with synthetic data
- `load_from_file.py`: Example loading data from a file
- `conditional_plotting.py`: Conditional plotting based on device type

## License

MIT License (or your preferred license)

## Contributing

This package is designed to be self-contained and easily portable. When making changes:

1. Keep all imports relative (use `.` imports)
2. Don't add external dependencies without good reason
3. Maintain backward compatibility with the unified API
4. Test with the example script before committing

