# Pulse Testing GUI — Architecture Reference

> **Documentation accuracy:** These notes are a snapshot of the repository at the time they were written. Refactors, new instruments, and UI changes can make any section stale. Treat this as **high-level orientation**; verify names, entry points, and behavior in the current source before relying on them.

---

## 1. General overview

### 1.1 What this module does

The **Pulse Testing GUI** (`gui/pulse_testing_gui/`) is a **`tk.Toplevel`** application for **fast, buffer-oriented pulse measurements** on Keithley hardware. It targets:

- **Keithley 2450** — TSP (Test Script Processor) scripts running on the instrument.
- **Keithley 4200-SCS family** — KXCI-based paths, with distinct GUI profiles (e.g. PMU vs SMU) that share a common core adapter.
- **Keithley 2400** — SCPI path via the same backend abstraction (see `Pulse_Testing/`).

The GUI **does not hard-code the full test matrix**. Instead it pulls **metadata** from `Pulse_Testing/test_definitions.py` and filters by **per-system support** in `Pulse_Testing/test_capabilities.py`. Execution is delegated to **`Pulse_Testing.system_wrapper.SystemWrapper`**, which routes `run_test(...)` to the correct system implementation under `Pulse_Testing/systems/`.

### 1.2 How it fits in the larger app

- **Launched from Measurement GUI**: `MeasurementGUI.open_pulse_testing_gui()` constructs `TSPTestingGUI` with the current SMU address, optional `provider=self` (for live context sync), sample name, device label, and custom save base when the Measurement GUI uses a custom save location.
- **Standalone**: `python -m gui.pulse_testing_gui.main` (or instantiating `TSPTestingGUI` on a `tk.Tk` / `Toplevel` parent) with a VISA address.

The class is still named **`TSPTestingGUI`** for historical reasons; the window title and behavior are **multi-system**, not 2450-only.

### 1.3 Package layout (active files)

```
gui/pulse_testing_gui/
├── __init__.py              # exports TSPTestingGUI
├── main.py                  # TSPTestingGUI: layout, callbacks, run/save flow
├── config.py                # paths, JSON filenames, window geometry
├── logic.py                 # VISA scan, run_test_worker (thread entry)
├── plot_handlers.py         # plot_by_type() + _plot_* for each plot_type
├── optical_runner.py        # laser + SMU optical test sequencing (4200-oriented)
├── ui/
│   ├── connection.py        # connection / system selection UI
│   ├── test_selection.py    # test list, on_test_selected
│   ├── diagram_section.py   # wraps pulse diagram section
│   ├── parameters.py        # dynamic parameter widgets per test
│   ├── status_section.py    # status / messages in manual tab
│   ├── plot_section.py      # matplotlib live plot embed
│   ├── pulse_diagram.py     # PulseDiagramHelper (pattern preview)
│   ├── laser_section.py     # Oxxius / laser controls (collapsible)
│   └── tabs_optical.py      # Optical tab builder
└── README.md                # concise module readme
```

Backend (not under `gui/` but required):

- **`Pulse_Testing/system_wrapper.py`** — connect, `run_test`, detection helpers.
- **`Pulse_Testing/test_definitions.py`** — `TEST_FUNCTIONS`, `get_test_definitions_for_gui(system_name)`.
- **`Pulse_Testing/test_capabilities.py`** — `SYSTEM_CAPABILITIES`, `is_test_supported`, explanations.
- **`Pulse_Testing/systems/*`** — thin adapters; 4200 logic concentrated in `keithley4200_core.py`.
- **`Equipment/SMU_AND_PMU/...`** — controllers and TSP/KXCI scripts (see `Pulse_Testing/README.md` table).

---

## 2. Main class: `TSPTestingGUI` (`main.py`)

### 2.1 Constructor arguments

| Argument | Role |
|----------|------|
| `master` | Parent Tk window |
| `device_address` | Default VISA address (string) |
| `provider` | Optional object (e.g. `MeasurementGUI`) used by `_poll_context()` to mirror sample name, device label, save path |
| `sample_name`, `device_label` | Strings for filenames and metadata; default `"UnknownSample"` / `"UnknownDevice"` |
| `custom_save_base` | Optional `Path` / str overriding save root; disables “simple save” mode when set from provider |

### 2.2 Core runtime objects

- **`self.system_wrapper`**: `SystemWrapper()` — connect/disconnect and `run_test(test_function=..., params=...)`.
- **`self.current_system_name`**: UI profile for test list and parameter units (may track combo when disconnected; aligns with wrapper when connected).
- **`self.tsp` / `self.test_scripts`**: Legacy 2450 handles; kept for compatibility where still referenced.
- **`self.smu_current_range_var`**: Shared `tk.DoubleVar` (0 = auto) mirrored in connection/parameters/automated tab.
- **Threading**: `test_thread`, `test_running`, `last_results` for the last completed run.
- **Laser**: Attributes for Oxxius control used by **`optical_runner.run_optical_test`** when running optical test functions.

### 2.3 UI structure (`create_ui`)

1. **Horizontal `PanedWindow`**: left **scrollable** control column (~40% width), right **diagram + plot** (~60%).
2. **Left column** (top to bottom):
   - Title bar + **Help / Guide**
   - **`create_connection_section`** — address, refresh, connect/disconnect, system type, 2450 front/rear terminal options where applicable
   - **`create_laser_section`** — laser block for optical workflows
   - **`ttk.Notebook`** with three tabs:
     - **Manual Testing** — parameters, test selection, status
     - **Automated Testing** — matrix-style **placeholder** UI; **START** button historically **disabled**; `_run_automated_test` shows “Not Implemented” (confirm in current `main.py` if this changes)
     - **Optical** — `build_optical_tab` (Oxxius + optical test wiring)
3. **Right column**:
   - **`create_pulse_diagram_section`** — schematic / timing preview via **`PulseDiagramHelper`**
   - **`create_plot_section`** — matplotlib `Figure` / axis / canvas for live and post-run plots
   - **`create_bottom_control_bar`** — **RUN**, **STOP**, **SAVE**, **ANALYSIS**, auto-save checkbox, etc.

After build, **`_update_test_list_capabilities()`** refreshes which tests appear for the selected system.

### 2.4 Typical run flow (manual tests)

1. User selects **system** (combo) and **connects** — wrapper connects underlying instrument.
2. User picks a **test** — `on_test_selected` rebuilds or updates parameter widgets from `test_definitions`.
3. **RUN** — starts a **worker thread** (see `logic.run_test_worker`) calling `system_wrapper.run_test` with the internal **function name** (e.g. `pulse_read_repeat`, not the display string).
4. **Progress** — for some tests (endurance, retention variants), `progress_callback` is injected in `run_test_worker` so the GUI can update incrementally.
5. On completion, results populate **`last_results`**; **`plot_handlers.plot_by_type`** draws according to `plot_type` from definitions.
6. **SAVE** / **auto-save** — uses **`Measurements.data_formats`** (`TSPDataFormatter`, `FileNamer`, `save_tsp_measurement`) and path logic from config / JSON / provider.

### 2.5 Optical tests

**`optical_runner.py`** implements a coordinated **laser + SMU** flow for functions in `OPTICAL_TEST_FUNCTIONS` (e.g. `optical_read_pulsed_light`, `optical_pulse_train_read`, `optical_pulse_train_pattern_read`). It:

- Requires **`gui.laser`** connected (Oxxius path from Optical tab / laser section).
- Uses **`MEASUREMENT_INIT_TIME_S`** wall-clock delay after starting the Keithley measurement before treating time zero for laser scheduling.
- Returns results including **`laser_on_intervals`** for plotting; **`plot_handlers`** draws confidence bands (nominal vs uncertain laser-on windows) for optical plot types.

Exact timing assumptions are documented in the module docstring; they are **best-effort**, not hard real-time.

### 2.6 Plotting (`plot_handlers.py`)

- **`plot_by_type(gui, plot_type)`** dispatches to `_plot_time_series`, `_plot_endurance`, `_plot_width_sweep`, `_plot_ispp`, `_plot_threshold`, etc.
- **`plot_type`** strings come from **`test_definitions`** (must stay in sync with handlers dict in `plot_handlers.py`).
- Optical-aware helpers (e.g. `_draw_laser_on_intervals`) annotate time-axis plots where `laser_on_intervals` is present.

---

## 3. Configuration (`config.py`)

| Constant | Purpose |
|----------|---------|
| `PROJECT_ROOT` | Repo root |
| `SAVE_LOCATION_CONFIG_FILE` | `Json_Files/save_location_config.json` |
| `TSP_GUI_CONFIG_FILE` | `Json_Files/tsp_gui_config.json` |
| `TSP_GUI_SAVE_CONFIG_FILE` | `Json_Files/tsp_gui_save_config.json` |
| `TSP_TEST_PRESETS_FILE` | `Json_Files/tsp_test_presets.json` |
| `WINDOW_GEOMETRY` | Default `"1400x900"` |
| `HELP_WINDOW_GEOMETRY`, `RANGE_FINDER_POPUP_GEOMETRY` | Dialog sizes |

---

## 4. Logic helpers (`logic.py`)

- **`get_available_devices(fallback_address)`** — PyVISA USB + GPIB scan; returns `[fallback]` if empty or on error.
- **`run_test_worker(system_wrapper, func_name, params, progress_callback=None)`** — thread-safe single test call; adds `progress_callback` into `params` for specific endurance/retention function names.

---

## 5. UI builders (`ui/`)

| Module | Responsibility |
|--------|------------------|
| `connection.py` | VISA combobox, connect/disconnect, system selection, terminal toggles, link to capability updates |
| `test_selection.py` | Filtered test combobox, descriptions, `on_test_selected` |
| `parameters.py` | Per-test parameter rows (sliders/spinboxes), unit scaling (incl. 4200 µs vs ms where applicable) |
| `diagram_section.py` | Host frame for pulse diagram |
| `pulse_diagram.py` | **`PulseDiagramHelper`**: preview drawings for pulse trains / reads |
| `status_section.py` | Progress labels / status text in manual tab |
| `plot_section.py` | Matplotlib embed, toolbar, axis setup |
| `laser_section.py` | Laser connect, power, digital control hooks |
| `tabs_optical.py` | Full Optical tab: laser connection, optical test selection, params |

`ui/__init__.py` re-exports **`build_*`** functions and **`PulseDiagramHelper`**.

---

## 6. Extending the system

Authoritative instructions live in **`Pulse_Testing/README.md`**. Summary:

1. Add **`test_capabilities`** rows for each `system_name` that supports the test.
2. Add **`test_definitions`** entry (display name, internal `function`, `params`, `plot_type`, optional `only_for_systems`).
3. Implement the method on the relevant **`BaseMeasurementSystem`** subclass (for 4200, usually once in **`keithley4200_core.py`**).
4. If the result shape is new, add a **`plot_type`** and a matching **`_plot_*`** in **`plot_handlers.py`**.

The Pulse Testing GUI **should not** duplicate capability logic in Tk code beyond filtering calls to `get_test_definitions_for_gui`.

---

## 7. Relationship diagram

```
MeasurementGUI.open_pulse_testing_gui()
        │
        ▼
TSPTestingGUI (gui/pulse_testing_gui/main.py)
        │
        ├─► ui/* (layout + widgets)
        ├─► logic.run_test_worker ──► SystemWrapper.run_test
        │                                    │
        │                                    ├─► Pulse_Testing/systems/keithley2450.py → Equipment TSP
        │                                    ├─► Pulse_Testing/systems/keithley4200_*.py → keithley4200_core → KXCI / C
        │                                    └─► Pulse_Testing/systems/keithley2400.py → SCPI
        ├─► optical_runner.run_optical_test (laser + SMU)
        ├─► plot_handlers.plot_by_type
        └─► Measurements.data_formats (save)
```

---

## 8. Related documentation

- **`gui/pulse_testing_gui/README.md`** — shorter module-focused readme (may differ slightly from this file over time).
- **`Pulse_Testing/README.md`** — backend architecture, adding tests/systems, 4200 profile differences.
- **Root `README.md`** — TSP testing overview, terminal selection, timing limitations.
- **`Documents/reference/MEASUREMENT_AND_SAMPLE_GUI_REFERENCE.md`** — how Sample + Measurement GUIs launch this tool.

---

*Sibling references in `Documents/reference/`: [MEASUREMENT_AND_SAMPLE_GUI_REFERENCE.md](MEASUREMENT_AND_SAMPLE_GUI_REFERENCE.md), [MOTOR_CONTROL_GUI_REFERENCE.md](MOTOR_CONTROL_GUI_REFERENCE.md), [CONNECTION_CHECK_GUI_REFERENCE.md](CONNECTION_CHECK_GUI_REFERENCE.md), [OSCILLOSCOPE_PULSE_GUI_REFERENCE.md](OSCILLOSCOPE_PULSE_GUI_REFERENCE.md).*
