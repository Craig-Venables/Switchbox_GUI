# Measurement GUI and Sample GUI — Architecture Reference

> **Documentation accuracy:** These architecture notes are a snapshot of the repository at the time they were written. The project changes over time—modules move, APIs rename, and features are added or removed—so details may drift from the live code. Use this document for **orientation**, then confirm behavior in source when it matters.

This document describes the **active** implementation of the device-selection and measurement interfaces in the Switchbox project. It is written so another tool or developer can orient quickly: what runs first, what each layer owns, and how data and hardware flow through the system.

**Terminology:** When this file says **Measurement GUI**, it means the **live code under `gui/measurement_gui/`** (the package `main.py` imports). When it says **Sample GUI**, it means **`gui/sample_gui/`**. It does **not** refer to legacy single-file copies such as `Measurement_GUI.py` or `Sample_GUI.py` under `archive/old_code/` or `Other/old_code/` unless those paths are **explicitly** mentioned.

---

## 1. General overview

### 1.1 What the application does

The Switchbox GUI is a **Tkinter-based laboratory front end** for characterizing memristor / crossbar-style devices. Users:

1. Pick a **sample layout** and **devices** on a visual map (or a generated grid).
2. Optionally route those devices through a **multiplexer** (or work in manual probe mode).
3. Open the **Measurement GUI**, connect to configured **instruments** (SMU, PSU, temperature controller, optical hardware, etc.), and run **DC IV**, **pulsed**, **custom JSON-defined sweeps**, **sequential multi-device** runs, **manual endurance/retention**, and various **analysis / plotting** workflows.
4. Data is saved under a configurable root (see `gui/sample_gui/config.py` → `resolve_default_save_root()`), with filenames that encode sweep metadata and `code_name` values from `Json_Files/Custom_Sweeps.json`.

The **root entry point** is `main.py`, which only creates `tk.Tk()` and instantiates **`SampleGUI`** from `gui.sample_gui`.

### 1.2 Where the code lives (important naming note)

| Historical / informal name | Active code location |
|----------------------------|----------------------|
| `Sample_GUI.py` | **`gui/sample_gui/`** — primarily `main.py`, plus `config.py` and `ui/` builders |
| `Measurement_GUI.py` | **`gui/measurement_gui/`** — primarily `main.py`, plus `layout_builder.py`, `layout/`, `plot_panels.py`, `plot_updaters.py`, and several handler modules |

Monolithic copies of `Sample_GUI.py` and `Measurement_GUI.py` may still exist under **`archive/old_code/`** or **`Other/old_code/`**; **do not treat those as the source of truth** for current behavior. The modular `gui/` package is what `main.py` imports.

### 1.3 High-level application flow

```
main.py
  └─ SampleGUI (gui/sample_gui/main.py)
        ├─ Config & maps: gui/sample_gui/config.py, Json_Files/mapping.json, pin_mapping.json
        ├─ Multiplexers: Equipment.managers.multiplexer.MultiplexerManager (+ legacy controller paths)
        └─ User opens measurement
              └─ MeasurementGUI (gui/measurement_gui/main.py)  [tk.Toplevel]
                    ├─ Layout: MeasurementGUILayoutBuilder (layout_builder.py + layout/tab_*.py)
                    ├─ Plots: MeasurementPlotPanels + PlotUpdaters
                    ├─ Engine: Measurements.measurement_services_smu.MeasurementService
                    ├─ Connections: Measurements.connection_manager.InstrumentConnectionManager
                    ├─ Persistence: Measurements.data_saver.MeasurementDataSaver
                    └─ Optional child tools: pulse testing, connection check, motor control, oscilloscope pulse, PMU/advanced/automated testers if installed
```

`SampleGUI` keeps a reference to the open `MeasurementGUI` and can **register** it so that changes in the sample window (e.g. section/device) propagate via `on_sample_gui_change` when implemented on the child.

---

## 2. Sample GUI (`gui/sample_gui/`)

### 2.1 Role

**SampleGUI** is the **primary entry window**: sample type, section, device map, selection state, multiplexer mode, quick scan, device manager, terminal log, and the action that **constructs `MeasurementGUI`**.

Exported symbol: `SampleGUI` from `gui/sample_gui/__init__.py` → `gui.sample_gui.main`.

### 2.2 Main module: `main.py`

**Class: `SampleGUI`**

Core responsibilities:

- **Window layout**: Three-row grid — top control bar, notebook tabs, status bar (`__init__` around lines 120–245).
- **State**:
  - Multiplexer type: `Manual`, or hardware-backed modes (e.g. PySwitchbox / Electronic Mpx flags and `MultiplexerManager`).
  - `current_device_map` / sample type (e.g. `Cross_bar`, `Device_Array_10`, `15x15mm`, **`Generic_Grid`**).
  - `device_list`, `device_mapping`, label/key maps for display vs internal IDs.
  - **Selection**: `selected_devices`, `selected_indices`, navigation index `current_index`.
  - **Status tracking**: `device_status` per device (working / broken / undefined) with icons.
  - **Quick scan**: threading (`quick_scan_thread`, `quick_scan_abort`), thresholds, overlay toggles.
  - **Telegram**: optional bots loaded from config (`telegram_enabled`, `_load_telegram_bots`).
  - **Child GUIs**: `_child_guis` list; `register_child_gui` / `unregister_child_gui` / `_notify_child_guis`.

**Tabs (ttk.Notebook)**:

1. **Device Selection** — canvas map, device selection panel, terminal log.
2. **Device Manager** — device naming, metadata, workflows that require a “current device name”.
3. **Quick Scan Results** — quick scan controls and results visualization.

**UI construction** is delegated to `gui/sample_gui/ui/`:

| Module | Responsibility |
|--------|----------------|
| `top_control_bar.py` | Multiplexer type, sample type, global actions (e.g. open measurement, telegram). |
| `device_map.py` | Canvas, image load, highlights, click-to-select (`canvas_click`, scaling vs 600×500 view). |
| `device_selection.py` | List navigation, checkboxes, sync with map. |
| `terminal_log.py` | Scrollable log; filter var `terminal_filter`. |
| `status_bar.py` | Bottom status line. |
| `device_manager.py` | Device name and metadata UI. |
| `quick_scan.py` | Quick scan UI wiring. |

**Opening the Measurement GUI** — `open_measurement_window()` (approximately lines 2395–2457):

- If a measurement window is already open and valid, **`bring_to_top()`** instead of creating a new one.
- Enforces **device name** and **selected devices** via dialogs (`_show_no_device_name_dialog`, `_show_no_devices_dialog`) with paths to continue anyway (empty list or no name still possible per dialog branch).
- Calls **`change_relays()`** before constructing `MeasurementGUI`.
- Instantiates:

  ```text
  MeasurementGUI(self.root, sample_type, section, selected_device_list, self)
  ```

  Note: the codebase uses the attribute name `measuremnt_gui` (typo) in places.

**Multiplexer routing** — `change_relays()` (approximately lines 2535–2572):

- **Manual**: logs that the user should move probes; updates open `MeasurementGUI` index/variables if present.
- **Hardware**: uses `self.mpx_manager.route_to_device(...)` when initialized.
- Warns if the current device is not in `selected_devices` and asks to continue.

**Canvas hit-testing** — `canvas_click` maps click coordinates to `device_mapping` rectangles scaled from the original image size to the fixed display size.

**Automated tests from Sample GUI** — `start_automated_tests()` / `_run_automated_tests_worker` use **`Keithley2400Controller`** when available; logs are pumped to the terminal via a queue (`_pump_test_logs`). This is **separate** from the Measurement GUI’s own automated test hooks.

### 2.3 Configuration: `config.py`

- **`BASE_DIR`**: project root (with PyInstaller frozen-path handling).
- **`sample_config`**: per-sample sections and device ID lists (including **Generic_Grid** with 12 devices in a 3×4 logical grid).
- **`device_maps`**: loaded from **`Json_Files/mapping.json`**.
- **`get_or_build_device_map()`**: if a sample is not in `mapping.json` but is in `sample_config`, builds a **synthetic grid** (`build_generic_device_map`) and caches it in `device_maps`.
- **`pin_mapping`**: from **`Json_Files/pin_mapping.json`** (multiplexer pin mapping).
- **`resolve_default_save_root()`**: prefers OneDrive/commercial Documents paths, then University of Nottingham OneDrive path, then `~/Documents`, appends **`Data_folder`**.

### 2.4 Dependencies (Sample GUI)

- **`gui.measurement_gui.MeasurementGUI`** — primary child application.
- **`Equipment.Multiplexers...MultiplexerController`** — legacy multiplexer class (still imported).
- **`Equipment.managers.multiplexer.MultiplexerManager`** — preferred unified API.
- **Optional**: `Keithley2400Controller` for sample-side automated tests.

### 2.5 Generic_Grid (no physical mask image)

Documented in `gui/sample_gui/README.md`: choose **Manual** multiplexer and **Generic_Grid** sample type to get a **placeholder grid** without a custom `mapping.json` entry. **Quick Scan** expects real multiplexer hardware; manual mode is for hand probing.

---

## 3. Measurement GUI (`gui/measurement_gui/`)

### 3.1 Role

**MeasurementGUI** is a **`tk.Toplevel`** window: the **central hub** for instrument connection, sweep configuration, running measurements (via service + runner classes), live plots, saving data, Telegram prompts, optical controls, and launching auxiliary tools.

Exported symbol: `MeasurementGUI` from `gui/measurement_gui/__init__.py` → `gui.measurement_gui.main`.

### 3.2 Main module: `main.py`

**Supporting class: `SMUAdapter`**

- Thin wrapper around the **IV controller manager** (`Equipment` layer) exposing a minimal API: `set_voltage`, `set_current`, `measure_voltage`, `measure_current`, `enable_output`, `close`, optional `run_tsp_sweep`.
- Normalizes tuple returns to floats where needed.

**Class: `MeasurementGUI` — construction highlights**

**Parameters**: `master`, `sample_type`, `section`, `device_list`, `sample_gui` (reference back to SampleGUI).

**Lifecycle**:

- Creates **`self.master = tk.Toplevel(master)`**, title **IV Measurement System**, registers **`WM_DELETE_WINDOW`** to: unregister from sample GUI, call `_on_measurement_window_closed`, **`cleanup()`**, destroy window.
- Syncs **`current_index`** from `sample_gui`.
- Loads messaging/Telegram profile data via **`messaging_handlers.load_messaging_data`**.
- Instantiates:
  - **`TelegramCoordinator`**
  - **`SingleMeasurementRunner`**, **`PulsedMeasurementRunner`**, **`SpecialMeasurementRunner`**
  - **`MeasurementService()`** — core SMU-side measurement algorithms
  - **`MeasurementDataSaver`** with default base from **`_resolve_default_save_root()`** (aligned with sample GUI conceptually)
  - **`InstrumentConnectionManager`** — SMU/PSU/temperature connection lifecycle; logs via `log_terminal`
- Loads **`Json_Files/Custom_Sweeps.json`** into `custom_sweeps` / `test_names` / `code_names`.
- Builds UI via **`MeasurementGUILayoutBuilder`** with a large **callbacks** dict (connect, measure, sequential, custom sweep, motor, connection check, endurance/retention, forming, pulse actions, analysis toggle, conditional testing, etc.).
- **`layout_builder.build_modern_layout(self.master)`** — notebook tabs, top bar, status bar.
- **`MeasurementPlotPanels.create_all_plots_modern`** on `measurements_graph_panel`; **`attach_to(self)`** for backward-compatible attribute names on the GUI instance.
- **`PlotUpdaters`** — background threads for IV and I–t plots; optional temperature/endurance/retention threads when enabled.
- **`AnalysisStatsWindow`** — floating stats overlay when analysis features are enabled.
- **`atexit.register(self.cleanup)`** — stop plot threads, shutdown SMU, clean up analysis window, etc.

**Optional / legacy imports** (graceful fallback if missing):

- **4200A step IV** via `importlib` and `Equipment.SMU_AND_PMU.4200A...run_smu_vi_sweep`
- **`PMUTestingGUI`**, **`AdvancedTestsGUI`**, **`AutomatedTesterGUI`**, **`MeasurementPlotter`**
- **`automated_tests.framework`** (`MeasurementDriver`, `TestRunner`, `load_thresholds`)

**Other notable imports** in `main.py`:

- **`CheckConnection`**, **`MotorControlWindow`**, **`TSPTestingGUI`**, **`OscilloscopePulseGUI`**
- **`OpticalExcitation` / `create_optical_from_system_config`**, **`OpticalController`**
- Background workers for manual endurance/retention from **`Measurements.background_workers`**
- **`run_sequential_measurement`**, **`run_sequential_measurement`** from sequential/single/pulsed/special runners modules

The file is **very large**; most **UI-specific** code has been moved to **`layout_builder.py`** and **`layout/`**, and **plot/analysis/conditional/custom-sweep** logic to dedicated modules (below). `main.py` remains the **orchestrator** and still contains many measurement-thread entrypoints, optical helpers, system load/save, and classification/analysis orchestration methods.

### 3.3 Layout: `layout_builder.py` and `layout/`

**`MeasurementGUILayoutBuilder`** (dataclass):

- **`build_modern_layout`**: top bar (system combo, connection status, analysis controls, device context, utility buttons), tabbed notebook, bottom status bar.
- **Top bar** syncs system selection across duplicate comboboxes using a re-entrancy guard (`_updating_system`).
- **`_build_tabbed_content`** adds tabs by importing builders from **`layout/`**:

| Tab module | Tab purpose |
|------------|-------------|
| `tab_measurements.py` | **Main work tab**: left scrollable controls (mode, sweep params, pulse params, sequential, custom measurement quick select, conditional testing quick select, Telegram section); right **`measurements_graph_panel`** for plots. |
| `tab_advanced_tests.py` | Advanced / volatile test entry points (wiring to legacy `Advanced_tests_GUI` when present). |
| `tab_setup.py` | System/instrument setup, connections, addresses, save locations, optical laser connect/disconnect helpers, etc. |
| `tab_custom_measurements.py` | Editing / running custom measurement definitions tied to JSON. |
| `tab_notes.py` | Notes / metadata for the run or sample. |
| `tab_stats.py` | Device tracking / statistics UI. |
| `tab_graphing.py` | Sample analysis, folder browsing, batch plots, classification display. |
| `tab_custom_sweeps.py` | Custom sweeps graphing / combination management UI. |

**Collapsible sections** under `layout/sections/` include: `mode_selection`, `sweep_parameters`, `pulse_parameters`, `sequential_controls`, `custom_measurement_quick`, `conditional_testing_quick`, `telegram_bot`, `connection`, `optical`, `advanced_tests`, etc.

**Help / videos**: part of the builder can open documentation and **`Json_Files/help_videos.json`**-driven tutorials.

**VISA helpers**: `_scan_visa_resources`, `_refresh_address_combo`, `_validate_address_format` for instrument address UX.

### 3.4 Plotting: `plot_panels.py` and `plot_updaters.py`

**`MeasurementPlotPanels`**:

- Creates matplotlib **`Figure` / `FigureCanvasTkAgg`** widgets for real-time IV, log IV, endurance, retention, temperature vs time, etc. (legacy and **modern** vis toggles, overlays, graph terminal).
- Method **`create_all_plots_modern`** is used from `MeasurementGUI.__init__`.
- **`attach_to(gui)`** copies figure/axis/canvas references onto the GUI instance so older code paths keep working.

**`PlotUpdaters`**:

- Runs **daemon-style loops** (e.g. `_update_iv_plots`, `_update_current_time_plot`) on a fixed interval (`interval_s`, default 0.1 s).
- Optional threads for endurance, retention, temperature based on whether corresponding axes exist and flags are set.
- **`stop_all_threads`** used from **`cleanup()`**.

### 3.5 Extracted logic modules (still “part of” Measurement GUI behavior)

| Module | Role |
|--------|------|
| `plot_handlers.py` | Browse sample folders, batch plot samples/devices, stats list refresh, full sample analysis, yield/concentration, impedance visualization, classification UI updates — **large** orchestration file. |
| `analysis_handlers.py` | Formatting analysis values, synchronous IV analysis hooks, latest analysis lookup for a device. |
| `analysis_stats_window.py` | Floating window for live analysis stats when “Analysis” is enabled. |
| `conditional_testing.py` | **Conditional / tiered / quick** test flows using custom sweep definitions (`run_quick_test`, `execute_single_sweep_for_conditional_test`, `run_tiered_test`, `run_conditional_testing`, button state updates). |
| `custom_sweeps.py` | Load/save **`Custom_Sweeps.json`**, populate comboboxes, sweep **combinations** editor persistence, method selection handlers. |
| `messaging_handlers.py` | Load Telegram profiles via **`gui.messaging_config.load_messaging_config`**, update token/chat ID when profile changes. |
| `custom_measurements_builder.py` | Additional UI/builder pieces for custom measurements (see imports from layout where used). |

### 3.6 Yield / concentration submodule (`yield_concentration/`)

Package under `gui/measurement_gui/yield_concentration/` supports **yield and concentration** style plots and aggregation (`aggregator.py`, `fabrication.py`, `first_sweep_resistance.py`, `plots.py`, `yield_source.py`). Invoked from analysis/plot handler paths (e.g. `run_yield_concentration_analysis`).

### 3.7 What Measurement GUI launches (child tools)

From buttons / menu callbacks in the layout and `main.py`:

- **`TSPTestingGUI`** (`gui.pulse_testing_gui`) — fast Keithley 2450 TSP pulse tests.
- **`CheckConnection`** (`gui.connection_check_gui`) — live connection verification; receives `keithley` reference when available.
- **`MotorControlWindow`** (`gui.motor_control_gui`) — XY stage / laser positioning.
- **`OscilloscopePulseGUI`** — oscilloscope-oriented pulse workflow.
- **`PMUTestingGUI`** — if import succeeds (root-level module).
- **`AdvancedTestsGUI`** — volatile memristor protocols (PPF, STDP, etc.) if present.
- **`AutomatedTesterGUI`** — batch automated workflows if present.
- **Device visualizer** — `open_device_visualizer()` (implementation in `main.py`).

### 3.8 Runners and services (conceptual contract)

The GUI does **not** implement IV math inside Tk callbacks for the main paths; it delegates to:

- **`MeasurementService`** — DC triangle IV, pulsed IV, fast pulses, hold, ISPP, pulse-width sweep, threshold search, etc. (see repo `README.md` and `Measurements/measurement_services_smu.py`).
- **`SingleMeasurementRunner` / `PulsedMeasurementRunner` / `SpecialMeasurementRunner`** — glue between GUI state, `MeasurementService`, and plotting/saving.
- **`run_sequential_measurement`** — automated multi-device sweeps with coordination to Sample GUI indices / multiplexer.
- **`InstrumentConnectionManager`** — connects **SMU** (via system JSON), **PSU**, **temperature** controllers; exposes instances the GUI stores as `keithley`, `psu`, `temp_controller`, etc.

**Saving**: **`MeasurementDataSaver`** writes text/data files under the chosen hierarchy; filenames often include sweep index and **`code_name`** from custom sweep definitions for downstream **test_configurations.json** analysis.

### 3.9 Classification and post-measurement analysis (high level)

When **Analysis** is enabled (top bar checkbox):

- The GUI can trigger **synchronous or threaded** analysis after measurements (`_run_analysis_if_enabled`, related helpers).
- Results can be shown in **`AnalysisStatsWindow`**, drive **classification** displays, append **classification logs**, and optionally send **Telegram** notifications (`_send_classification_notification`).
- **`reclassify_all_devices`** and **retroactive analysis** paths (`_run_retroactive_analysis`) support batch reprocessing of saved sample folders.

Exact scoring uses helpers in **`analysis_handlers`** / **`plot_handlers`** and JSON such as **`Json_Files/classification_weights.json`** (see root README).

---

## 4. Configuration files (shared contract)

| File | Used by | Purpose |
|------|---------|---------|
| `Json_Files/system_configs.json` | Measurement GUI | Named instrument stacks (“System 1”, …), addresses, options. |
| `Json_Files/mapping.json` | Sample GUI (+ config) | Device bounding boxes on sample artwork per sample type. |
| `Json_Files/pin_mapping.json` | Sample GUI / multiplexer | Device ID → multiplexer pins. |
| `Json_Files/Custom_Sweeps.json` | Measurement GUI | Named multi-sweep tests, `code_name`, endurance/retention/IV params. |
| `Json_Files/test_configurations.json` | Analysis / graphing tab | Sweep combinations and titles per `code_name` for “Full Sample Analysis”. |
| `Json_Files/save_location_config.json` | GUI | Save path preferences (if enabled in UI). |
| `Json_Files/messaging_data*.json` | Telegram | Bot tokens/chat IDs via secure loader (`gui.messaging_config`). |

---

## 5. Testing

- **`tests/test_sample_gui_quick_scan.py`** — quick scan–related tests against Sample GUI behavior.

---

## 6. Quick orientation checklist for an AI / new developer

1. **Start**: `main.py` → `SampleGUI`.
2. **Device context**: `SampleGUI.device_list`, `current_index`, `selected_indices`, `mapping.json` / generic grid.
3. **Open measurement**: `SampleGUI.open_measurement_window()` → `MeasurementGUI(...)`.
4. **Instrument**: Measurement GUI **`load_system()` / `connect_keithley()`** paths + `InstrumentConnectionManager`.
5. **Run sweep**: `measure_one_device` and runner classes → **`MeasurementService`**.
6. **Plots**: `PlotUpdaters` read GUI buffers; panels in **`MeasurementPlotPanels`**.
7. **Custom sequences**: `Custom_Sweeps.json` + **`custom_sweeps.py`** + “Run Custom” / sequential UI.
8. **Analysis tab**: **`plot_handlers`** + `test_configurations.json`.

---

## 7. Related documentation in this repository

- Root **`README.md`** — systems, measurement types, JSON schema examples, equipment managers.
- **`gui/README.md`** — package map and import examples.
- **`gui/sample_gui/README.md`**, **`gui/measurement_gui/README.md`** — shorter module-focused docs.
- **`Documents/guides/USER_GUIDE.md`**, **`Documents/guides/QUICK_REFERENCE.md`**, **`Documents/guides/JSON_CONFIG_GUIDE.md`** — operator and config detail.

### GUI architecture reference series (`Documents/reference/`)

High-level, AI-oriented overviews (each file includes a **documentation accuracy** note):

- **[PULSE_TESTING_GUI_REFERENCE.md](PULSE_TESTING_GUI_REFERENCE.md)** — `gui/pulse_testing_gui/` (TSPTestingGUI).
- **[MOTOR_CONTROL_GUI_REFERENCE.md](MOTOR_CONTROL_GUI_REFERENCE.md)** — `gui/motor_control_gui/`.
- **[CONNECTION_CHECK_GUI_REFERENCE.md](CONNECTION_CHECK_GUI_REFERENCE.md)** — `gui/connection_check_gui/`.
- **[OSCILLOSCOPE_PULSE_GUI_REFERENCE.md](OSCILLOSCOPE_PULSE_GUI_REFERENCE.md)** — `gui/oscilloscope_pulse_gui/`.

---

*Document generated to reflect the modular `gui/` layout as used by `main.py`. If you need line-accurate behavior for a specific function, open the cited file in the repository; this guide is architectural, not a line-by-line spec.*
