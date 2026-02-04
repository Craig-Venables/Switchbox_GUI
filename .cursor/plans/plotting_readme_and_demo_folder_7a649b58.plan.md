---
name: Plotting README and demo folder
overview: Add a detailed developer README inside plotting (how to add plots per subpackage, how each is called, data contracts) and a reproducible demo folder that generates deterministic example data and example graphs for each subsection (core, device, sample, section, endurance), saving outputs into per-subsection folders for easy comparison when changing code or style.
todos: []
isProject: false
---

# Plotting detailed README and demo folder

## 1. Detailed README (developer guide)

Add a **developer-focused document** inside [plotting/](plotting/) that explains how to add and call plots in each subpackage. Options: **(A)** a new file e.g. [plotting/DEVELOPER.md](plotting/DEVELOPER.md) or [plotting/ADDING_PLOTS.md](plotting/ADDING_PLOTS.md), or **(B)** a long new section in the existing [plotting/README.md](plotting/README.md). Recommendation: **separate DEVELOPER.md** so the main README stays a “one stop shop” and the developer doc can be detailed without clutter.

**Proposed structure for the doc:**

- **Introduction**: Who this is for (anyone adding or changing plots), link to [CATALOG.md](plotting/CATALOG.md) (find a plot) and [PACKAGE_STRUCTURE.md](plotting/PACKAGE_STRUCTURE.md) (layout).
- **Core** (`core/`):  
  - Purpose: shared infrastructure only (no plot types). Contains [base.py](plotting/core/base.py) (PlotManager), [style.py](plotting/core/style.py) (DPI, figsize, fonts), [formatters.py](plotting/core/formatters.py) (e.g. `plain_log_formatter`).  
  - How it’s used: device/sample/section/endurance import `from ..core import style` or `from ..core.base import PlotManager`.  
  - **How to add**: e.g. new figsize preset in `style.py` (add constant + entry in `get_figsize()`); new formatter in `formatters.py` and use it in a plotter.  
  - No “add a new plot” here—only style/formatter/utility changes.
- **Device** (`device/`):  
  - What lives here: [unified_plotter.py](plotting/device/unified_plotter.py) (UnifiedPlotter), [iv_grid.py](plotting/device/iv_grid.py), [conduction.py](plotting/device/conduction.py), [sclc_fit.py](plotting/device/sclc_fit.py), [hdf5_style.py](plotting/device/hdf5_style.py), [device_combined_plots.py](plotting/device/device_combined_plots.py).  
  - **How they’re called**: From app/GUI: `from plotting import UnifiedPlotter` then `plotter = UnifiedPlotter(save_dir=...)` and `plotter.plot_iv_dashboard(voltage, current, ...)`, `plotter.plot_conduction_analysis(...)`, `plotter.plot_sclc_fit(...)`, etc. Direct plotters: `IVGridPlotter`, `ConductionPlotter`, `SCLCFitPlotter`, `HDF5StylePlotter` if needed.  
  - **How to add a new device plot**: (1) Add a new plotter class in `device/` (or a method on an existing one) that uses `PlotManager` and optionally `style`/`formatters`. (2) Optionally add a wrapper method on `UnifiedPlotter` that delegates to it. (3) Document in CATALOG.md.  
  - **Data contract**: IV-style plots expect `voltage` and `current` 1D arrays (same length); optional `time`. UnifiedPlotter can accept `save_dir`, `auto_close`, and sweep-related options.
- **Sample** (`sample/`):  
  - What: [sample_plots.py](plotting/sample/sample_plots.py) — single class `SamplePlots` with many methods (heatmap, scatter, dashboards, etc.).  
  - **How it’s called**: `from plotting import SamplePlots`; construct `SamplePlots(devices_data, plots_dir, sample_name, ...)` then call e.g. `.plot_memristivity_heatmap()`, `.plot_classification_scatter()`. Used by analysis (e.g. sample_analyzer).  
  - **How to add a new sample plot**: Add a new method to `SamplePlots` that uses `self.devices_data`, `self.plots_dir`, `self.sample_name`, and optionally `self._load_iv`, `self.memristive_devices`, etc.; use `style.get_dpi()` / `style.get_figsize(...)`; save to `plots_dir` (or subdir). Document in CATALOG.  
  - **Data contract**: `devices_data` is a list of dicts; each dict at least `device_id` (e.g. `"S1_a_1"`) and often `classification` (e.g. `memristivity_score`). Other keys depend on the plot (see existing methods).
- **Section** (`section/`):  
  - What: [section_plots.py](plotting/section/section_plots.py) — functions `plot_sweeps_by_type`, `plot_sweeps_by_voltage`, `plot_statistical_comparisons`, plus helpers `create_subplot`, `plot_data`, `plot_customization`.  
  - **How they’re called**: From section_analyzer: `from plotting.section_plots import plot_sweeps_by_type, plot_sweeps_by_voltage, plot_statistical_comparisons, plot_customization`. Call with `sweeps_by_type` (nested dict: test_type -> sweep_num -> list of (device_name, Path)), `read_data_file` callback returning (voltage, current, meta), `customizer(test_type, ax1, ax2)`.  
  - **How to add a new section plot**: Add a new function in `section_plots.py` that takes the same kind of inputs (paths, callbacks, section/sample names) and uses `style.get_dpi()` / `style.get_figsize(...)`; save to the provided `plots_dir` or `stats_dir`. Document in CATALOG.  
  - **Data contract**: `read_data_file(Path)` -> `(voltage, current, extra)`. Section names and plot dirs are passed in.
- **Endurance** (`endurance/`):  
  - What: [endurance_plots.py](plotting/endurance/endurance_plots.py) — `plot_current_vs_cycle(voltage, df, save_path, file_name, dpi)`, `plot_endurance_summary(voltages, extracted_data, save_path, file_name, dpi)`.  
  - **How they’re called**: From dc_endurance_analyzer: `from plotting.endurance_plots import plot_current_vs_cycle, plot_endurance_summary`.  
  - **How to add a new endurance plot**: Add a new function that takes the same DataFrame/path conventions and uses `style.get_dpi()`. Document in CATALOG.  
  - **Data contract**: DataFrame index = cycle; columns like `Current_Forward_(OFF)_{V}V`, `Current_Reverse_(ON)_{V}V`, `Current_Forward_(ON)_{-V}V`, `Current_Reverse_(OFF)_{-V}V` for each voltage.

End the doc with a short “Quick reference” table: subpackage → entry point → typical call pattern.

---

## 2. Demo folder (reproducible examples per subsection)

Add a **demo** folder inside plotting that:

- Uses **one deterministic dataset** (same every run) for fair comparison when you change style or code.
- Generates **example graphs for each subsection** and saves them into **per-subsection output folders**.
- Can be run as a single script or per-subsection scripts.

**Suggested layout:**

```
plotting/
  demo/
    README.md              # Purpose, how to run, output layout, optional: use your own data
    data/                   # Deterministic data (optional: user can add files here)
      README.md             # Describes expected formats if loading from file
    synthetic_data.py       # Single module: fixed seed, generate IV arrays, devices_data, endurance DataFrame, section-like structures
    run_all.py              # Runs all subsections, writes to output/{core,device,sample,section,endurance}
    output/                 # Generated figures (gitignore or commit for reference)
      core/
      device/
      sample/
      section/
      endurance/
```

**Deterministic data (synthetic_data.py):**

- Use a fixed `numpy.random.seed(...)` (e.g. 42) so runs are reproducible.
- **IV / device**: One or more bipolar sweep(s): voltage and current arrays (e.g. 0 → +V → 0 → -V → 0), plus optional time. Same length arrays every time.
- **Sample**: A minimal `devices_data` list: e.g. 4–6 devices with `device_id` like `"Demo_a_1"`, `"Demo_a_2"`, `"Demo_b_1"`, and `classification.memristivity_score` (and any other keys needed by the demo sample plots you call). Optionally minimal `research_data` / `memristive_devices` if the chosen methods need them.
- **Section**: Structures compatible with `plot_sweeps_by_type` and/or `plot_statistical_comparisons`: e.g. `sweeps_by_type` dict and a `read_data_file` that returns deterministic (voltage, current) from a key or in-memory buffer; or write 1–2 small temp CSV files and pass Paths.
- **Endurance**: A small DataFrame with index = cycle (e.g. 1..10), columns `Current_Forward_(OFF)_1V`, `Current_Reverse_(ON)_1V`, `Current_Forward_(ON)_-1V`, `Current_Reverse_(OFF)_-1V` (and optionally more voltages) with deterministic values.

All generation in one place so “same data every time” is guaranteed and you can optionally later support loading from `demo/data/` (e.g. CSV/JSON) with the same interface.

**What each subsection’s demo does:**


| Subsection    | Action                                                                                                                                                                                                                                                                                          | Output                                                      |
| ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| **core**      | Build one minimal figure that uses `style.get_figsize()`, `style.get_dpi()`, and `formatters.plain_log_formatter` on an axis (e.g. simple log plot). Save with PlotManager or fig.savefig to `demo/output/core/`.                                                                               | Shows that changing core style/formatters changes the look. |
| **device**    | Using synthetic IV (and time) from `synthetic_data.py`, create `UnifiedPlotter(save_dir=demo/output/device)` and call `plot_iv_dashboard`, `plot_conduction_analysis`, `plot_sclc_fit`. Optionally run `HDF5StylePlotter` with synthetic concentration/yield arrays and save there too.         | PNGs in `demo/output/device/`.                              |
| **sample**    | Build `SamplePlots(devices_data, plots_dir, sample_name, ...)` with synthetic `devices_data` (and any minimal callbacks if needed). Call a small set of methods that don’t require real files (e.g. `plot_memristivity_heatmap`, `plot_classification_scatter`). Save to `demo/output/sample/`. | PNGs in `demo/output/sample/`.                              |
| **section**   | Build `sweeps_by_type` (and optionally `device_stats` / `main_sweep_data` for statistical comparisons) from synthetic data; provide a `read_data_file` that returns deterministic (V, I). Call `plot_sweeps_by_type` and/or `plot_statistical_comparisons`. Save to `demo/output/section/`.     | PNGs in `demo/output/section/`.                             |
| **endurance** | Build synthetic DataFrame and voltages list; call `plot_current_vs_cycle` and `plot_endurance_summary`; save to `demo/output/endurance/`.                                                                                                                                                       | PNGs in `demo/output/endurance/`.                           |


**demo/README.md:**

- Purpose: reproducible example graphs for each subsection so you can see how changes to code or style affect output.
- How to run: from project root, e.g. `py plotting/demo/run_all.py` (or `python -m plotting.demo.run_all` if you add `__main__` and package the demo appropriately). Describe that output goes to `plotting/demo/output/{core,device,sample,section,endurance}`.
- Data: deterministic synthetic data from `synthetic_data.py`; same every run. Optional: “To use your own data, place files in `demo/data/` and see `demo/data/README.md` for expected formats” (if you add that later).
- Brief note that this is for development/regression comparison, not production.

**Implementation notes:**

- Ensure the project root is on `sys.path` when running `run_all.py` (e.g. run from repo root, or add a short path fix at the top of `run_all.py`).
- `device_combined_plots` expects real device directories and config; the demo can skip it or use a minimal mock (e.g. temp dir with one fake sweep file and minimal test_configs) if you want one example; otherwise leave it out of the demo to keep the first version simple.
- For sample plots that need `_load_iv` or file-based data, either provide a callback that returns synthetic (V, I) from `synthetic_data` or only call methods that work from `devices_data` alone (heatmap, classification scatter, etc.).

---

## 3. Optional: your own data

You said you can provide data or we generate it. The plan above uses **generated synthetic data** so it’s always the same and no files are required. If you later add your own data:

- Add a short **demo/data/README.md** describing accepted formats (e.g. IV: CSV with voltage, current [, time]; endurance: CSV with cycle and column names matching the expected pattern).
- In `synthetic_data.py` (or a small `data_loader.py`) add an optional path: if `demo/data/some_iv.csv` exists, load it and use it instead of synthetic IV for the device demo; otherwise use synthetic. That way “same data every time” can mean either “synthetic” or “your file once placed”.

No code changes in the plan for this; just document the option in the developer README and in demo/README.md.

---

## 4. Summary


| Deliverable                                    | Content                                                                                                                                              |
| ---------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| **plotting/DEVELOPER.md** (or ADDING_PLOTS.md) | Detailed guide: how each subpackage is used, how to add a new plot (and style/formatter) in each, data contracts; quick reference table.             |
| **plotting/demo/**                             | Folder with deterministic synthetic data, `run_all.py`, output per subsection, README.                                                               |
| **plotting/demo/synthetic_data.py**            | Single module (fixed seed) generating IV, devices_data, section structures, endurance DataFrame.                                                     |
| **plotting/demo/run_all.py**                   | Script that generates example graphs for core, device, sample, section, endurance and saves to `demo/output/{core,device,sample,section,endurance}`. |
| **plotting/demo/README.md**                    | Purpose, how to run, where output goes, that data is deterministic; optional note on using your own data.                                            |
| **plotting/demo/output/**                      | Subdirs core/, device/, sample/, section/, endurance/ for generated PNGs.                                                                            |


This gives you one place to read “how to add plots” and one place to run “example graphs for every subsection” with the same data every time for easy comparison.