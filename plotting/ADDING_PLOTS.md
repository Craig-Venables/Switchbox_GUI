# Adding Plots – Developer Guide

This guide is for anyone adding or changing plots in the plotting package. Use it to see how each subpackage is used, how to add a new plot, and what data each part expects.

- **Find an existing plot:** [CATALOG.md](CATALOG.md)
- **Package layout:** [PACKAGE_STRUCTURE.md](PACKAGE_STRUCTURE.md)

---

## Core (`core/`)

**Purpose:** Shared infrastructure only. No plot types live here.

- **base.py** – `PlotManager`: save figures to a directory, optional auto-close.
- **style.py** – DPI, figsize presets, font sizes. Used by all subpackages.
- **formatters.py** – e.g. `plain_log_formatter` for log-scale axes (avoids matplotlib math text issues).

**How it’s used:** Device, sample, section, and endurance code import `from ..core import style` or `from ..core.base import PlotManager` or `from ..core.formatters import plain_log_formatter`.

**How to add (core only):**

- **New figsize preset:** In `style.py`, add a constant (e.g. `FIGSIZE_MYPLOT = (10, 6)`) and an entry in `get_figsize()` (e.g. `"myplot": FIGSIZE_MYPLOT`).
- **New formatter:** Add a function in `formatters.py` and use it in the plotter that needs it (e.g. in `device/iv_grid.py`).

There is no “add a new plot” in core—only style/formatter/utility changes.

---

## Device (`device/`)

**What lives here:** Device-level IV, conduction, SCLC, combined sweeps.

- **unified_plotter.py** – `UnifiedPlotter`: main entry for IV dashboard, conduction analysis, SCLC fit, endurance/retention/forming analysis.
- **iv_grid.py** – `IVGridPlotter`: 2×2 IV dashboard.
- **conduction.py** – `ConductionPlotter`: SCLC/Schottky/Poole–Frenkel panels.
- **sclc_fit.py** – `SCLCFitPlotter`: log-log slope fitting.
- **hdf5_style.py** – `HDF5StylePlotter`: concentration/yield/spacing-style statistical plots.
- **device_combined_plots.py** – `plot_device_combined_sweeps`: combined IV/endurance/retention per device from config.

**How they’re called:**

- From app/GUI: `from plotting import UnifiedPlotter` → `plotter = UnifiedPlotter(save_dir=...)` then:
  - `plotter.plot_iv_dashboard(voltage, current, device_name=..., save_name=...)`
  - `plotter.plot_conduction_analysis(voltage, current, ...)`
  - `plotter.plot_sclc_fit(voltage, current, ...)`
- Direct plotters: `from plotting import IVGridPlotter, ConductionPlotter, SCLCFitPlotter, HDF5StylePlotter` if you need them without the unified API.

**How to add a new device plot:**

1. Add a new plotter class in `device/` (or a new method on an existing class) that uses `PlotManager` and optionally `style` / `formatters`.
2. Optionally add a wrapper method on `UnifiedPlotter` that delegates to it.
3. Document the new plot in [CATALOG.md](CATALOG.md).

**Data contract:** IV-style plots expect `voltage` and `current` as 1D arrays (same length). Optional `time` for time-series panel. `UnifiedPlotter(save_dir=..., auto_close=...)` and sweep-related options as needed.

---

## Sample (`sample/`)

**What lives here:** [sample_plots.py](sample/sample_plots.py) – single class `SamplePlots` with many methods (heatmap, scatter, dashboards, forming, comparisons, etc.).

**How it’s called:** `from plotting import SamplePlots` → `plotter = SamplePlots(devices_data, plots_dir, sample_name, ...)` then e.g. `.plot_memristivity_heatmap()`, `.plot_classification_scatter()`, `.plot_conduction_mechanisms()`. Used by analysis (e.g. sample_analyzer).

**How to add a new sample plot:** Add a new method to `SamplePlots` that uses `self.devices_data`, `self.plots_dir`, `self.sample_name`, and optionally `self._load_iv`, `self.memristive_devices`, etc.; use `style.get_dpi()` / `style.get_figsize(...)`; save under `plots_dir` (or a subdir). Document in [CATALOG.md](CATALOG.md).

**Data contract:** `devices_data` is a list of dicts. Each dict typically has:

- `device_id` – e.g. `"S1_a_1"` (used for heatmap position: section_row + device col).
- `classification` – e.g. `memristivity_score`, `device_type`, `conduction_mechanism`.
- `resistance` – e.g. `ron_mean`, `roff_mean`, `switching_ratio`.
- `hysteresis` – e.g. `pinched`.
- `quality`, `all_measurements`, etc. for other plots.

Exact keys depend on the method; see existing methods in `sample_plots.py`.

---

## Section (`section/`)

**What lives here:** [section_plots.py](section/section_plots.py) – functions `plot_sweeps_by_type`, `plot_sweeps_by_voltage`, `plot_statistical_comparisons`, plus helpers `create_subplot`, `plot_data`, `plot_customization`.

**How they’re called:** From section_analyzer: `from plotting.section_plots import plot_sweeps_by_type, plot_sweeps_by_voltage, plot_statistical_comparisons, plot_customization`. You pass:

- `sweeps_by_type`: nested dict `test_type -> sweep_num -> list of (device_name, Path)`.
- `read_data_file`: callback `(Path) -> (voltage, current, extra)`.
- `customizer(test_type, ax1, ax2)` for axis titles/limits.

**How to add a new section plot:** Add a new function in `section_plots.py` that takes the same kind of inputs (paths, callbacks, section/sample names), uses `style.get_dpi()` / `style.get_figsize(...)`, and saves to the provided `plots_dir` or `stats_dir`. Document in [CATALOG.md](CATALOG.md).

**Data contract:** `read_data_file(Path)` returns `(voltage, current, extra)`. Section name and plot dirs are passed in.

---

## Endurance (`endurance/`)

**What lives here:** [endurance_plots.py](endurance/endurance_plots.py) – `plot_current_vs_cycle(voltage, df, save_path, file_name, dpi)`, `plot_endurance_summary(voltages, extracted_data, save_path, file_name, dpi)`.

**How they’re called:** From dc_endurance_analyzer: `from plotting.endurance_plots import plot_current_vs_cycle, plot_endurance_summary`.

**How to add a new endurance plot:** Add a new function that follows the same DataFrame/path conventions and uses `style.get_dpi()`. Document in [CATALOG.md](CATALOG.md).

**Data contract:** DataFrame index = cycle number. Column names per voltage `V`: `Current_Forward_(OFF)_{V}V`, `Current_Reverse_(ON)_{V}V`, `Current_Forward_(ON)_{-V}V`, `Current_Reverse_(OFF)_{-V}V`.

---

## Quick reference

| Subpackage | Entry point | Typical call |
|------------|-------------|--------------|
| **core** | `from plotting.core import style` / `from plotting.core.base import PlotManager` | `style.get_dpi()`, `style.get_figsize("heatmap")`; `PlotManager(save_dir=...).save(fig, name)` |
| **device** | `from plotting import UnifiedPlotter` | `UnifiedPlotter(save_dir=...).plot_iv_dashboard(voltage, current, ...)` |
| **sample** | `from plotting import SamplePlots` | `SamplePlots(devices_data, plots_dir, sample_name).plot_memristivity_heatmap()` |
| **section** | `from plotting.section_plots import plot_sweeps_by_type, ...` | `plot_sweeps_by_type(sweeps_by_type, section, sample_name, plots_dir, read_data_file, customizer)` |
| **endurance** | `from plotting.endurance_plots import plot_current_vs_cycle, plot_endurance_summary` | `plot_current_vs_cycle(voltage, df, save_path, file_name)` |
