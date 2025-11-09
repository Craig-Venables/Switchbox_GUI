# Measurement GUI Refactoring Plan

**Created:** October 14, 2025  
**Objective:** Break down massive 5,899-line `Measurement_GUI.py` into modular, maintainable components

---

## 🎯 Aim and End Goal

### Current Problem
`Measurement_GUI.py` is a **5,899-line monolithic file** containing:
- GUI layout construction (12 methods, ~1,200 lines)
- Plotting setup and updates (12 methods, ~1,100 lines)
- Measurement execution logic (8+ methods, ~2,500 lines)
- Data saving and formatting (5 methods, ~600 lines)
- Connection management (4 methods, ~200 lines)
- Telegram bot integration (5 methods, ~400 lines)

**Problems:**
- ❌ Hard to navigate and understand
- ❌ Difficult to test individual components
- ❌ High risk of merge conflicts
- ❌ Changes ripple across unrelated functionality
- ❌ Cannot reuse components in other GUIs

### End Goal
Transform into a **clean, modular architecture** with:
- ✅ Main file reduced to ~1,000 lines (orchestration only)
- ✅ 8 focused modules, each with single responsibility
- ✅ Components reusable across other GUIs (Motor Control, PMU Testing, etc.)
- ✅ Easy to test, modify, and extend
- ✅ Clear separation of concerns

**Target Structure:**
```
Measurement_GUI.py (1,000 lines) - Main orchestrator
├── GUI/
│   ├── layout_builder.py (1,200 lines) - Widget creation
│   ├── plot_panels.py (800 lines) - Matplotlib setup
│   └── plot_updaters.py (300 lines) - Background plotting threads
├── Measurments/
│   ├── measurement_executor.py (1,500 lines) - Measurement logic
│   ├── data_saver.py (600 lines) - File I/O and saving
│   ├── connection_manager.py (200 lines) - Instrument connections
│   ├── telegram_coordinator.py (400 lines) - Telegram interactions
│   └── background_workers.py (300 lines) - Thread management
```

---

## 📊 Current State Analysis

### File Statistics
- **Total lines:** 5,899
- **Classes:** 2 (SMUAdapter, MeasurementGUI)
- **Methods in MeasurementGUI:** ~60+
- **Duplicated patterns:** Using old if-statement style (to be replaced with new utilities)

### Method Categories

| Category | Count | Lines | Examples |
|----------|-------|-------|----------|
| GUI Layout (`create_*`) | 12 | ~1,200 | `create_connection_section`, `create_sweep_parameters` |
| Plot Setup (`graphs_*`) | 7 | ~800 | `graphs_main_iv`, `graphs_all` |
| Plot Updates (`plot_*`) | 6 | ~300 | `plot_voltage_current`, `plot_current_time` |
| Measurements | 8 | ~2,500 | `start_measurement`, `run_custom_measurement` |
| Data Saving (`save_*`) | 5 | ~600 | `save_averaged_data`, `_save_combined_summary_plot` |
| Connections | 4 | ~200 | `connect_keithley`, `connect_temp_controller` |
| Telegram | 5 | ~400 | `_post_measurement_options_worker` |
| Utilities | 10+ | ~400 | `convert_to_name`, `check_for_sample_name` |

### Refactor Progress as of November 2025

- ✅ Shared measurement utilities now live in `Measurments/data_utils.py`, `Measurments/source_modes.py`, `Measurments/sweep_patterns.py`, and `Measurments/optical_controller.py`. These replace dozens of ad-hoc helper snippets that used to live inside `Measurement_GUI.py`.
- ✅ SMU/PMU execution has been centralized in `Measurments/measurement_services_smu.py` (and the PMU companion). Pulsed IV routines already delegate here and are production-tested.
- ✅ File formatting helpers (`Measurments/data_formats.py`) standardize headers and naming. The GUI still saves files inline, but the formatting logic is ready to reuse.
- ✅ `gui/layout_builder.py` now owns the top banner, the manual ITC4 temperature set panel, and Telegram/signal messaging controls; `Measurement_GUI.py` just wires callbacks.
- ✅ `Motor_Controll_GUI` can be imported without `pylablib`/`pyvisa`; optional hardware features expose guarded fallbacks and a `--test` smoke mode.
- ✅ Manual endurance/retention workers now live in `Measurments/background_workers.py`; the GUI just delegates to shared helpers.
- ✅ Telegram messaging helpers were extracted to `Measurments/telegram_coordinator.py` with `MeasurementGUI` delegating all bot access.
- ✅ Introduced `Measurments/single_measurement_runner.py`; the default (DC) IV flow now runs through this orchestrator, leaving the GUI to handle only mode dispatch and UI wiring.
- ✅ SMU/PMU pulsed modes (`<1.5 V`, `>1.5 V`, fixed 20 V) plus fast pulse/hold routines moved into `Measurments/pulsed_measurement_runner.py`; `MeasurementGUI.start_measurement` now delegates via a dispatcher.
- ✅ ISPP, pulse-width sweep, threshold search, and transient decay branches now live in `Measurments/special_measurement_runner.py`, keeping the GUI as a thin router.
- ✅ Summary plot/log generation now funnels through `MeasurementDataSaver.save_summary_plots`; GUI runners use `_save_summary_artifacts` so Telegram and file exports stay consistent.
- ✅ Sequential measurement UI *and* logic now live in `gui/layout_builder.py` (panel injected into the middle column) plus `Measurments/sequential_runner.py`, preserving the original layout location while trimming the GUI controller.
- ✅ Real-time plot updater threads were extracted to `gui/plot_updaters.py`; `MeasurementGUI` now delegates start/stop hooks to the helper instead of managing threads directly.
- ✅ `MeasurementGUI` gained a reusable `bring_to_top()` helper so runner modules can surface the main window without tightly coupling to Tk internals.
- ✅ Added `tests/conftest.py` to place the repo root on `sys.path`, unblocking pytest runs without `python -m`.
- ⚠️ Synchronous measurement wrappers, data saving helpers, and Telegram orchestration logic remain embedded inside `Measurement_GUI.py`. These are the next targets for extraction.
- ⚠️ No `GUI/` subpackage exists yet. Creating it will make the separation explicit and keep PEP 8–style module names (lowercase with underscores).

---

## ✅ 2025-11-09 Smoke-Test Checklist (Initial Pass)

| Flow | Status | Notes |
|------|--------|-------|
| Standard IV (single_runner) | ⚠️ Partial | Runs through main path; uses simulated Keithley 2450. Requires hardware or full simulator for end-to-end validation. |
| Sequential measurements | ⚠️ Partial | UI renders in middle column; runner invoked but still depends on hardware for verification. |
| Custom measurement plans | ⚠️ Partial | Executes JSON-driven IV branch; relies on `MeasurementService.compute_voltage_range`. Needs hardware to complete sweep. |
| Pulsed / Special modes | ⚠️ Pending | Not yet exercised after refactor; schedule targeted pass once optional libs (`pyvisa`, gpib bindings) available. |
| Manual endurance/retention workers | ⚠️ Pending | Background threads extracted; require manual trigger during next hardware session. |
| Telegram messaging | ⚠️ Pending | `TelegramCoordinator` instantiated; needs token/chat setup to verify post-measurement worker. |
| Data/plot saving | ✅ | `tests/test_summary_artifacts.py` covers summary plots/log creation; manual run saved `Combined_summary.png` artifacts under simulated path. |
| Pytest regression suite | ✅ | `py -3 -m pytest tests` passes (3 tests). |

**Next smoke pass:** repeat once lab instruments or fully mocked drivers are connected; record failures and regressions here.

---

## 🏗️ Detailed Architecture Design

### Module 1: GUI Layout Builder

**File:** `GUI/layout_builder.py`

**Purpose:** Create all Tkinter widgets and frames without mixing in measurement behaviour.

**Responsibilities:**
- Build connection panel (SMU, PSU, temp controller)
- Build mode selection panel
- Build sweep parameter panel
- Build custom measurement panel
- Build status displays
- Build control buttons

**Why split this out?**
- Keeps all Tkinter widget construction in one place so layout tweaks don’t risk breaking measurement logic.
- Makes it easier for newer contributors to reason about the GUI: they can read a single module to understand which widgets exist and what callbacks they trigger.
- Encourages smaller, focused methods (e.g., one method per panel) that can be unit-tested with Tkinter’s `tk.Misc` stubs.

**Interface:**
```python
class MeasurementGUILayoutBuilder:
    """Constructs all GUI widgets for MeasurementGUI"""
    
    def __init__(self, parent: tk.Misc, callbacks: Dict[str, Callable]):
        self.parent = parent
        self.callbacks = callbacks
        self.widgets = {}  # Store widget references
        self.vars = {}     # Store Tk variables
    
    def build_all_panels(self, left_frame, middle_frame, top_frame):
        """Build all GUI panels"""
        self.build_connection_panel(left_frame)
        self.build_mode_selection(left_frame)
        self.build_status_box(left_frame)
        self.build_sweep_parameters(middle_frame)
        self.build_custom_measurement(middle_frame)
        self.build_sequential_controls(middle_frame)
        self.build_top_banner(top_frame)
    
    def build_connection_panel(self, parent):
        """Build connection section with dropdowns and buttons"""
        # All create_connection_section logic here
    
    def build_sweep_parameters(self, parent):
        """Build sweep parameter controls with dynamic UI"""
        # All create_sweep_parameters logic here
    
    # ... etc for all create_* methods
    
    def get_values(self) -> Dict[str, Any]:
        """Get current values from all widgets"""
        return {
            'start_voltage': self.vars['start_voltage'].get(),
            'stop_voltage': self.vars['voltage_high'].get(),
            # ... all parameters
        }
```

**Methods to Move:**
- `create_connection_section()`
- `create_mode_selection()`
- ✅ `create_status_box()` → layout builder handles status frame.
- ✅ `create_controller_selection()` → layout builder builds controller dropdown and status badge.
- `create_sweep_parameters()`
- ✅ `create_custom_measurement_section()` → layout builder builds custom measurement menu, run/pause controls, and sweep editor button.
- ✅ `create_manual_endurance_retention()` → layout builder now renders manual endurance/retention controls and LED toggle callbacks.
- `create_automated_tests_section()`
- ✅ `temp_measurments_itc4()` → converted to layout builder temperature panel.
- ✅ `signal_messaging()` → migrated to layout builder with callback wiring.
- ✅ `sequential_measurments()` → sequential controls now live in layout builder with start/stop callbacks.
- ✅ `top_banner()` → layout builder creates top banner/quick action buttons.

**Size:** ~1,200 lines

**Implementation notes:**
- Follow standard Python style (`snake_case` module names, clear docstrings at the top of the file explaining the module’s role).
- Keep widget member names descriptive (e.g., `self.sample_name_entry`) and store them in dictionaries when the main GUI needs to read values.

---

### Module 2: Plot Panels

**File:** `GUI/plot_panels.py`

**Purpose:** Create and manage all matplotlib figures, isolated from measurement code.

**Responsibilities:**
- Create matplotlib figures and axes
- Setup plot styling and labels
- Provide methods to update plots
- Clear and reset plots

**Why split this out?**
- Plot construction is currently interwoven with business logic. Moving it keeps plotting bugs from breaking instrument control.
- Dedicated plotting module lets us reuse the same panels in other GUIs (e.g., PMU testing) without copying code.
- Makes it straightforward to write tests that instantiate the panel with a dummy Tk root and assert axes exist.

**Interface:**
```python
class MeasurementPlotPanels:
    """Creates and manages all matplotlib plot panels"""
    
    def __init__(self, parent: tk.Misc, font_config: Dict[str, int]):
        self.parent = parent
        self.axis_font_size = font_config.get('axis', 8)
        self.title_font_size = font_config.get('title', 10)
        
        # Plot references
        self.figures = {}
        self.axes = {}
        self.canvases = {}
        self.lines = {}
    
    def create_all_plots(self, graph_frame):
        """Create all plot panels"""
        self.create_main_iv_plots(graph_frame)
        self.create_all_sweeps_plots(graph_frame)
        self.create_vi_logiv_plots(graph_frame)
        self.create_current_time_plot(graph_frame)
        self.create_resistance_time_plot(graph_frame)
        self.create_temp_time_plot(graph_frame)
        self.create_endurance_retention_plots(graph_frame)
    
    def create_main_iv_plots(self, parent):
        """Create live IV and log-IV plots"""
        # graphs_main_iv logic
    
    def update_plot(self, plot_name: str, x_data, y_data):
        """Update a specific plot with new data"""
        line = self.lines.get(plot_name)
        if line:
            line.set_data(x_data, y_data)
            ax = self.axes[plot_name]
            ax.relim()
            ax.autoscale_view()
            self.canvases[plot_name].draw()
    
    def clear_plot(self, plot_name: str):
        """Clear a specific plot"""
        ax = self.axes.get(plot_name)
        if ax:
            ax.clear()
            self.canvases[plot_name].draw()
    
    def graphs_show(self, v_arr, c_arr, key, stop_v):
        """Add sweep to 'All' plots"""
        # Current graphs_show logic
```

**Methods to Move:**
- `graphs_main_iv()`
- `graphs_all()`
- `graphs_vi_logiv()`
- `graphs_current_time_rt()`
- `graphs_resistance_time_rt()`
- `graphs_temp_time_rt()`
- `graphs_endurance_retention()`
- `graphs_show()`
- `clear_axis()`

**Size:** ~800 lines

**Implementation notes:**
- Store matplotlib objects in dictionaries keyed by intent (`rt_iv`, `all_iv`) so the rest of the code can update them without keeping multiple attributes in sync.
- Keep figure creation code close together and add short comments explaining axis scaling choices (log axes, legends, etc.).

---

### Module 3: Plot Updaters

**File:** `GUI/plot_updaters.py`

**Purpose:** Background threads that update plots in real-time.

**Responsibilities:**
- Run background plotting threads
- Poll data arrays and update matplotlib
- Handle thread synchronization
- Update status labels

**Why split this out?**
- Threading code is easy to break accidentally. Keeping it in one module limits the blast radius of synchronization changes.
- Decouples background polling from Tkinter widget creation, which simplifies troubleshooting race conditions for new contributors.
- Gives us a clean surface for future async/queue-based updates if we move away from threads.

**Interface:**
```python
class PlotUpdaters:
    """Manages background threads for real-time plot updates"""
    
    def __init__(self, plot_panels: MeasurementPlotPanels, data_refs: Dict[str, Any]):
        self.plots = plot_panels
        self.data = data_refs  # References to shared data arrays
        self.threads = []
        self.running = True
    
    def start_all_threads(self):
        """Start all background plotting threads"""
        self.threads.append(threading.Thread(target=self.update_iv_plots, daemon=True))
        self.threads.append(threading.Thread(target=self.update_current_time, daemon=True))
        self.threads.append(threading.Thread(target=self.update_resistance_time, daemon=True))
        self.threads.append(threading.Thread(target=self.update_vi_logiv, daemon=True))
        
        for t in self.threads:
            t.start()
    
    def update_iv_plots(self):
        """Background thread: update IV plots"""
        while self.running:
            if self.data.get('measuring', False):
                try:
                    v = list(self.data['v_arr_disp'])
                    c = list(self.data['c_arr_disp'])
                    self.plots.update_plot('rt_iv', v, c)
                    self.plots.update_plot('rt_logiv', v, np.abs(c))
                except Exception:
                    pass
            time.sleep(0.1)
    
    # ... similar for other plot types
    
    def stop_all_threads(self):
        """Stop all background threads"""
        self.running = False
```

**Methods to Move:**
- `plot_voltage_current()`
- `plot_current_time()`
- `plot_resistance_time()`
- `plot_Temp_time()`
- `plot_vi_logilogv()`
- `_status_update_tick()`

**Size:** ~300 lines

**Implementation notes:**
- Share data through explicit dictionaries (e.g., `data_refs["v_arr_disp"]`) so we know exactly which arrays are thread-shared.
- Document thread lifecycles (`start_all_threads`, `stop_all_threads`) with clear comments to help newcomers reason about shutdown order.

---

### Module 4: Measurement Executor

**File:** `Measurments/measurement_executor.py`

**Purpose:** Execute all measurement types while delegating low-level work to `MeasurementService`.

**Responsibilities:**
- Coordinate measurement sequences
- Apply source modes using new utilities
- Control optical sources using new utilities
- Handle stop flags and threading
- Call MeasurementService for actual measurements

**Why split this out?**
- We already have `MeasurementService` doing the heavy lifting. A thin executor module keeps GUI code focused on UI flow while bundling together configuration, stop flags, and callbacks.
- Makes it easier to add new measurement flavours (capacitance, custom sweeps) without touching Tkinter code.
- Encourages writing integration tests that exercise the executor against mocked instruments.

**Interface:**
```python
from Measurments.source_modes import SourceMode, apply_source, measure_result
from Measurments.optical_controller import OpticalController
from Measurments.data_utils import safe_measure_current, safe_measure_voltage
from Measurments.sweep_patterns import build_sweep_values, SweepType

class MeasurementExecutor:
    """Executes different measurement types using MeasurementService"""
    
    def __init__(self, 
                 measurement_service: MeasurementService,
                 instrument_manager: Any,
                 optical: Any = None,
                 psu: Any = None):
        self.service = measurement_service
        self.instruments = instrument_manager
        self.optical_ctrl = OpticalController(optical=optical, psu=psu)
        self.stop_flag = False
    
    def execute_dc_triangle_iv(self, config: Dict) -> Tuple[List, List, List]:
        """Execute DC triangle IV sweep"""
        # Uses new sweep_patterns.py for voltage generation
        voltages = build_sweep_values(
            config['start_v'],
            config['stop_v'],
            config['step_v'],
            SweepType(config['sweep_type'])
        )
        
        # Uses new optical_controller.py
        self.optical_ctrl.enable(config.get('led_power', 1.0))
        
        try:
            # Uses MeasurementService
            v, c, t = self.service.run_iv_sweep(...)
            return v, c, t
        finally:
            self.optical_ctrl.disable()
    
    def execute_pulsed_iv(self, config: Dict) -> Tuple[List, List, List]:
        """Execute pulsed IV measurement"""
        # Pulsed IV logic
    
    def execute_endurance(self, config: Dict) -> Tuple[List, List, List]:
        """Execute endurance cycling"""
        # Uses new utilities for cleaner code
    
    def execute_retention(self, config: Dict) -> Tuple[List, List, List]:
        """Execute retention measurement"""
        # Retention logic
    
    def execute_custom_sequence(self, sweeps_dict: Dict) -> Dict:
        """Execute custom measurement sequence from JSON"""
        # Custom measurement logic
```

**Methods to Move:**
- `start_measurement()` - Main entry point
- `run_custom_measurement()` - Custom sweeps
- `sequential_measure()` - Sequential measurements
- `measure_average_current()` - Averaging logic
- `retention_measure()` - Retention
- `start_manual_endurance()` + `_manual_endurance_worker()`
- `start_manual_retention()` + `_manual_retention_worker()`

**Size:** ~1,500 lines

**Key Improvement:** Will use the new utilities from Phase 1!
- `source_modes.py` for voltage/current modes
- `optical_controller.py` instead of if-statements
- `data_utils.py` for measurement normalization
- `sweep_patterns.py` for voltage list generation

**Implementation notes:**
- Keep executor methods short: gather GUI parameters, call into `MeasurementService`, push results through callbacks (plotting, saving, messaging). Comments should explain the flow in plain language.
- Store new shared state (e.g., stop flags, selected devices) in lightweight dataclasses or dictionaries, avoiding global lists where possible.

---

### Module 5: Data Saver

**File:** `Measurments/data_saver.py`

**Purpose:** Handle all data persistence and file management.

**Responsibilities:**
- Save measurement data to files
- Create summary plots
- Generate graphs and images
- Organize file structure

**Why split this out?**
- Saving files currently mixes path handling, NumPy formatting, and matplotlib export logic inside the GUI. Extracting it prevents accidental regressions when changing save locations.
- Centralizing saving enables reuse in scripts or other GUIs, and makes it straightforward to swap in new formats later (e.g., parquet).
- Keeps GUI classes focused on orchestration: they call `self.saver.save_iv_sweep(...)` and move on.

**Interface:**
```python
from Measurments.data_formats import DataFormatter, FileNamer, save_measurement_data
from pathlib import Path

class MeasurementDataSaver:
    """Handles all data saving and file management"""
    
    def __init__(self, base_dir: str = "Data_save_loc"):
        self.base_dir = Path(base_dir)
        self.formatter = DataFormatter()
        self.namer = FileNamer(self.base_dir)
    
    def save_iv_sweep(self, 
                     v_arr, c_arr, t_arr,
                     device: str,
                     sample_name: str,
                     sweep_config: Dict) -> Path:
        """Save IV sweep data using standardized format"""
        # Uses data_formats.py utilities!
        folder = self.namer.get_device_folder(sample_name, device)
        filename = self.namer.create_iv_filename(
            device=device,
            voltage=sweep_config['stop_v'],
            measurement_type=sweep_config['sweep_type']
        )
        
        data, header, fmt = self.formatter.format_iv_data(
            timestamps=np.array(t_arr),
            voltages=np.array(v_arr),
            currents=np.array(c_arr)
        )
        
        filepath = folder / filename
        save_measurement_data(filepath, data, header, fmt)
        return filepath
    
    def save_averaged_data(self, device_data, sample_name, **kwargs):
        """Save averaged measurement data"""
        # Uses new formatter for consistency
    
    def save_all_measurements_file(self, device_data, sample_name, **kwargs):
        """Create consolidated CSV for all devices"""
    
    def create_summary_plots(self, save_dir: str) -> Dict[str, Path]:
        """Create all summary plots (IV, log, combined)"""
        plots = {}
        plots['final_iv'] = self._save_final_sweep_plot(save_dir)
        plots['combined'] = self._save_combined_summary_plot(save_dir)
        return plots
```

**Methods to Move:**
- `save_averaged_data()`
- `save_all_measurements_file()`
- `_save_final_sweep_plot()`
- `_save_combined_summary_plot()`
- `_create_individual_device_graphs()`
- `_create_comparison_graph()`
- `create_log_file()`

**Size:** ~600 lines

**Implementation notes:**
- Lean heavily on the existing `DataFormatter` and `FileNamer` classes. This avoids duplicating header logic and keeps filenames consistent.
- Add comments near each save call that clarify what the output file contains (“per-device IV sweep”, “combined summary figure”), so newcomers know where to look when debugging saves.

---

### Module 6: Connection Manager

**File:** `Measurments/connection_manager.py`

**Purpose:** Manage all instrument connections.

**Responsibilities:**
- Connect to SMU/PMU instruments
- Connect to PSU (power supply)
- Connect to temperature controllers
- Connect to optical sources
- Handle connection errors
- Cleanup on exit

**Why split this out?**
- Connection logic talks to hardware and has lots of error handling; moving it out avoids cluttering the GUI class with try/except blocks.
- A dedicated manager makes mocking easier in tests and means we can share the same connection code with other GUIs.
- Clarifies ownership: the manager exposes `connect_*`, `is_connected`, and `cleanup`, while the GUI simply calls those methods.

**Interface:**
```python
class InstrumentConnectionManager:
    """Manages connections to all instruments"""
    
    def __init__(self, config: Dict[str, str]):
        self.config = config
        self.keithley = None
        self.psu = None
        self.temp_controller = None
        self.optical = None
        self.connected_flags = {
            'keithley': False,
            'psu': False,
            'temp': False,
            'optical': False
        }
    
    def connect_all(self, required_instruments: List[str]) -> Dict[str, bool]:
        """Connect to all required instruments"""
        results = {}
        
        if 'keithley' in required_instruments:
            results['keithley'] = self.connect_keithley()
        
        if 'psu' in required_instruments:
            results['psu'] = self.connect_psu()
        
        if 'temp' in required_instruments:
            results['temp'] = self.connect_temp_controller()
        
        return results
    
    def connect_keithley(self) -> bool:
        """Connect to SMU/PMU via IVControllerManager"""
        try:
            from Equipment.iv_controller_manager import IVControllerManager
            smu_type = self.config.get('SMU Type', 'Keithley 2401')
            address = self.config.get('SMU_address', 'GPIB0::24::INSTR')
            
            self.keithley = IVControllerManager(smu_type, address)
            self.connected_flags['keithley'] = self.keithley.is_connected()
            return self.connected_flags['keithley']
        except Exception as e:
            print(f"Error connecting to Keithley: {e}")
            return False
    
    def connect_psu(self) -> bool:
        """Connect to power supply"""
        # Logic from connect_keithley_psu
    
    def connect_temp_controller(self) -> bool:
        """Connect to temperature controller"""
        # Logic from connect_temp_controller and reconnect_temperature_controller
    
    def is_connected(self, instrument: str) -> bool:
        """Check if specific instrument is connected"""
        return self.connected_flags.get(instrument, False)
    
    def all_connected(self) -> bool:
        """Check if all instruments are connected"""
        return all(self.connected_flags.values())
    
    def cleanup(self):
        """Safe shutdown of all instruments"""
        # Logic from cleanup() method
```

**Methods to Move:**
- `connect_keithley()`
- `connect_keithley_psu()`
- `connect_temp_controller()`
- `reconnect_temperature_controller()`
- `init_temperature_controller()`
- `update_controller_status()`
- `cleanup()`

**Size:** ~200 lines

**Implementation notes:**
- Keep configuration lookups (addresses, model names) together at the top of the module, with comments referencing the relevant JSON config keys.
- Return booleans from `connect_*` methods and log concise status messages; this makes it simpler for new developers to trace startup issues.

---

### Module 7: Telegram Coordinator

**File:** `Measurments/telegram_coordinator.py`

**Purpose:** Handle all Telegram bot interactions.

**Responsibilities:**
- Send measurement status updates
- Send result images
- Interactive parameter selection via chat
- Handle user responses
- Coordinate next actions

**Why split this out?**
- Messaging code is orthogonal to measurement logic; isolating it keeps network errors from spilling into GUI code.
- Lets us disable or swap messaging channels by replacing the coordinator without touching the rest of the app.
- Helps new contributors understand the messaging flow by reading one concise module with obvious method names.

**Interface:**
```python
class TelegramMeasurementCoordinator:
    """Coordinates Telegram bot interactions for measurements"""
    
    def __init__(self, token: str, chat_id: str):
        self.bot = TelegramBot(token, chat_id) if token and chat_id else None
        self.enabled = self.bot is not None
    
    def send_measurement_start(self, sample: str, device: str, mode: str):
        """Send measurement start notification"""
        if self.bot:
            self.bot.send_message(
                f"Starting {mode} on {sample} device {device}"
            )
    
    def send_measurement_complete(self, 
                                  results: Dict,
                                  images: Dict[str, Path]):
        """Send completion message with images"""
        if not self.bot:
            return
        
        self.bot.send_message("Measurement finished")
        
        for name, path in images.items():
            if path and path.exists():
                self.bot.send_image(str(path), caption=name)
    
    def ask_next_action(self, 
                       options: Dict[str, str],
                       timeout_s: int = 900) -> Optional[str]:
        """Interactive menu via Telegram"""
        if not self.bot:
            return None
        
        return self.bot.ask_and_wait(
            "Would you like to continue measuring?",
            options,
            timeout_s=timeout_s
        )
    
    def interactive_parameter_input(self, 
                                   current_params: Dict,
                                   timeout_s: int = 900) -> Optional[Dict]:
        """Get measurement parameters via chat"""
        # Logic from _post_measurement_options_worker
```

**Methods to Move:**
- `_bot_enabled()`
- `_get_bot()`
- `_send_bot_message()`
- `_send_bot_image()`
- `_post_measurement_options_worker()`

**Size:** ~400 lines

**Implementation notes:**
- Guard all bot calls so the coordinator can operate in “disabled” mode when no credentials are provided. Comments should explain when each method is safe to call.
- Consider exposing small status callbacks (e.g., `on_user_selection`) so the GUI can subscribe without knowing Telegram internals.

---

### Module 8: Background Workers

**File:** `Measurments/background_workers.py`

**Purpose:** Manage background measurement threads.

**Responsibilities:**
- Start measurement threads
- Handle stop flags
- Thread synchronization
- Progress reporting

**Why split this out?**
- Thread wrappers for measurements are mixed into `MeasurementGUI` today, which makes the class difficult to read. A separate module keeps concurrency details in one place.
- Simplifies adding future async features (e.g., progress callbacks, queue-based messaging) without reopening the main GUI file.
- Allows targeted unit tests that verify stop flags and completion handlers fire correctly.

**Interface:**
```python
class MeasurementBackgroundWorkers:
    """Manages background measurement threads"""
    
    def __init__(self, executor: MeasurementExecutor):
        self.executor = executor
        self.threads = {}
        self.stop_flags = {}
    
    def start_custom_measurement_thread(self, 
                                       config: Dict,
                                       on_complete: Callable):
        """Start custom measurement in background"""
        self.stop_flags['custom'] = False
        
        def worker():
            try:
                results = self.executor.execute_custom_sequence(config)
                on_complete(results)
            except Exception as e:
                print(f"Measurement error: {e}")
        
        t = threading.Thread(target=worker, daemon=True)
        self.threads['custom'] = t
        t.start()
    
    def stop_measurement(self, thread_name: str):
        """Request stop for a measurement thread"""
        self.stop_flags[thread_name] = True
```

**Methods to Move:**
- Thread wrapper logic from `start_measurement()`
- Thread wrapper from `run_custom_measurement()`
- Thread wrapper from `sequential_measure()`
- Automated test thread logic

**Size:** ~300 lines

**Implementation notes:**
- Keep worker functions small and document the steps they perform (set stop flag, call executor, trigger callbacks). This guidance helps newer developers trace control flow.
- Use `threading.Thread(daemon=True)` consistently and provide a clear `stop_measurement` method to request shutdown.

---

## 🚀 Next Improvement Ideas (Post-Refactor)

- Finalize a `gui/` package layout with `__init__.py` so the layout/plot modules share a consistent namespace.
- Add instrument abstraction interfaces (mockable drivers) to unblock richer unit tests and simplify CI.
- Expand automated coverage with instrument mocks so runners can be validated without hardware. Target sequential, pulsed/special runners, and data saver integration.
- Explore migrating background threads to a centralized job queue or `asyncio` for easier shutdown and coordination.
- Introduce structured logging/telemetry so console, file, and Telegram outputs all reuse a common event schema.

---

## 📐 Simplified Main File

**File:** `Measurement_GUI.py` (reduced to ~1,000 lines)

**Purpose:** Orchestrate components and handle high-level flow

**What Remains:**
```python
class MeasurementGUI:
    """Main GUI orchestrator - delegates to specialized components"""
    
    def __init__(self, master, sample_type, section, device_list, sample_gui):
        # Initialize configuration
        self.config = self._load_config()
        
        # Initialize sub-components
        self.connections = InstrumentConnectionManager(self.config)
        self.executor = MeasurementExecutor(
            self.measurement_service,
            self.connections
        )
        self.saver = MeasurementDataSaver()
        self.telegram = TelegramMeasurementCoordinator(token, chat_id)
        self.workers = MeasurementBackgroundWorkers(self.executor)
        
        # Build GUI
        self.layout = MeasurementGUILayoutBuilder(
            parent=master,
            callbacks={
                'start_measurement': self.start_measurement,
                'connect_keithley': self.connections.connect_keithley,
                'toggle_led': self.toggle_led,
                # ... all button callbacks
            }
        )
        self.layout.build_all_panels(left_frame, middle_frame, top_frame)
        
        # Setup plots
        self.plots = MeasurementPlotPanels(graph_frame, font_config)
        self.plots.create_all_plots(graph_frame)
        
        # Start plot updaters
        shared_data = {
            'measuring': lambda: self.measuring,
            'v_arr_disp': self.v_arr_disp,
            'c_arr_disp': self.c_arr_disp,
            # ... all shared arrays
        }
        self.updaters = PlotUpdaters(self.plots, shared_data)
        self.updaters.start_all_threads()
        
        # Connect instruments
        self.connections.connect_keithley()
    
    # Only coordination methods remain:
    
    def start_measurement(self):
        """Coordinate measurement execution"""
        params = self.layout.get_values()
        excitation = params['excitation']
        
        # Delegate to executor
        if excitation == "DC Triangle IV":
            v, c, t = self.executor.execute_dc_triangle_iv(params)
        elif excitation == "SMU_AND_PMU Pulsed IV <1.5v":
            v, c, t = self.executor.execute_pulsed_iv(params)
        # ... etc
        
        # Save results
        self.saver.save_iv_sweep(v, c, t, device, sample, params)
        
        # Update plots
        self.plots.graphs_show(v, c, "sweep", params['stop_v'])
        
        # Telegram notification
        self.telegram.send_measurement_complete(results, images)
    
    def toggle_led(self):
        """Toggle optical source"""
        # Simple delegation to optical_ctrl
    
    # Small helper methods stay
    def bring_to_top(self)
    def check_for_sample_name(self)
    def update_variables(self)
```

---

## 🔄 Migration Strategy

The plan keeps risk low by moving self-contained responsibilities first, then teasing apart logic with heavier dependencies. Each phase ends with a manual smoke test (launch GUI, run a short IV sweep, confirm plots and saves).

### Phase 0: Foundations (✅ Complete)
- Shared utilities (`data_utils`, `source_modes`, `sweep_patterns`, `optical_controller`, `data_formats`) and `measurement_services_*` provide the building blocks for new modules.
- Action: No work required—just lean on these helpers during extractions.

### Phase 1: Safe Extractions (start here)
These steps peel away code that already behaves like stand-alone helpers.

1. **Create packages**
   - Add `GUI/__init__.py` and `Measurments/__init__.py` (empty is fine) so imports stay tidy.
2. **Extract `Measurments/data_saver.py`**
   - Move all `save_*` helpers.
   - Replace inline NumPy formatting with calls to `DataFormatter` and `FileNamer`.
   - Update `Measurement_GUI.py` to instantiate `MeasurementDataSaver` and delegate saves.
3. **Extract `GUI/plot_panels.py`**
   - Move every `graphs_*` and `clear_axis` method.
   - Store axes/canvases/lines in dictionaries; expose simple `update_plot` / `clear_plot`.
   - Swap GUI references (`self.ax_rt_iv`) with `self.plots.axes["rt_iv"]`.
4. **Extract `Measurments/connection_manager.py`**
   - Move `connect_*`, `reconnect_*`, `cleanup`.
   - Return booleans and surface instrument handles so the GUI can store them.

### Phase 2: Behavioural Separation
Here we remove logic that still talks to Tkinter or threads but benefits most from the new utilities.

1. **Extract `GUI/layout_builder.py`**
   - Move every `create_*` and UI helper.
   - Collect Tk variables in dictionaries and expose `get_values()` / `set_defaults()` methods.
2. **Extract `GUI/plot_updaters.py`**
   - Move all `plot_*` background loops plus `_status_update_tick`.
   - Accept the `MeasurementPlotPanels` instance and a dict of shared arrays/flags.
3. **Extract `Measurments/measurement_executor.py`**
   - Move `start_measurement`, `run_custom_measurement`, sequential helpers, manual endurance/retention workers.
   - Delegate measurement work to `MeasurementService`; remove duplicated sweep/optical logic in favour of utilities.

### Phase 3: Polish & Orchestration
After core behaviour is modular, finish by decoupling messaging and worker threads, then shrink the main class.

1. **Extract `Measurments/telegram_coordinator.py`**
   - Move `_bot_*` methods and `_post_measurement_options_worker`.
   - Provide high-level methods (`send_measurement_start`, `ask_next_action`).
2. **Extract `Measurments/background_workers.py`**
   - Gather all measurement thread wrappers in one place.
   - Accept callbacks for success/failure so the GUI only wires events.
3. **Simplify `Measurement_GUI.py`**
   - Remove migrated methods, wire up new modules in `__init__`.
   - Keep only orchestration helpers (callback wiring, small utility checks).
   - Re-run lint checks and smoke tests.

---

## 📝 Implementation Templates

### Template 1: GUI/plot_panels.py

```python
"""
Plot Panels for Measurement GUI

Creates and manages all matplotlib figures and axes for the measurement interface.

Author: Refactoring - October 2025
"""

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import tkinter as tk
from typing import Dict, Any, Tuple, Optional
import numpy as np


class MeasurementPlotPanels:
    """
    Creates and manages all matplotlib plot panels.
    
    This class handles:
    - Creating matplotlib figures and axes
    - Embedding them in Tkinter frames
    - Providing methods to update plots
    - Managing plot styling and labels
    
    Usage:
        plots = MeasurementPlotPanels(parent, {'axis': 8, 'title': 10})
        plots.create_all_plots(graph_frame)
        plots.update_plot('rt_iv', voltages, currents)
    """
    
    def __init__(self, parent: tk.Misc, font_config: Dict[str, int]):
        """
        Initialize plot panels manager.
        
        Args:
            parent: Tkinter parent widget
            font_config: Dictionary with 'axis' and 'title' font sizes
        """
        self.parent = parent
        self.axis_font_size = font_config.get('axis', 8)
        self.title_font_size = font_config.get('title', 10)
        
        # Storage for plot components
        self.figures: Dict[str, plt.Figure] = {}
        self.axes: Dict[str, plt.Axes] = {}
        self.canvases: Dict[str, FigureCanvasTkAgg] = {}
        self.lines: Dict[str, Any] = {}
    
    def create_all_plots(self, graph_frame: tk.Frame):
        """Create all plot panels in the graph frame"""
        self.create_main_iv_plots(graph_frame)
        self.create_all_sweeps_plots(graph_frame)
        self.create_vi_logiv_plots(graph_frame)
        self.create_current_time_plot(graph_frame)
        self.create_resistance_time_plot(graph_frame)
        self.create_endurance_retention_plots(graph_frame)
    
    def create_main_iv_plots(self, parent: tk.Frame):
        """Create live IV and log-IV plots (current measurement)"""
        frame = tk.LabelFrame(parent, text="Current Measurement", padx=5, pady=5)
        frame.grid(row=0, column=1, rowspan=2, padx=10, pady=5, sticky="nsew")
        
        # IV plot
        fig_iv, ax_iv = plt.subplots(figsize=(3, 3))
        ax_iv.set_title("IV", fontsize=self.title_font_size)
        ax_iv.set_xlabel("Voltage (V)", fontsize=self.axis_font_size)
        ax_iv.set_ylabel("Current", fontsize=self.axis_font_size)
        
        canvas_iv = FigureCanvasTkAgg(fig_iv, master=frame)
        canvas_iv.get_tk_widget().grid(row=0, column=0, columnspan=5, sticky="nsew")
        
        line_iv, = ax_iv.plot([], [], marker='.')
        
        # Store references
        self.figures['rt_iv'] = fig_iv
        self.axes['rt_iv'] = ax_iv
        self.canvases['rt_iv'] = canvas_iv
        self.lines['rt_iv'] = line_iv
        
        # Log IV plot
        fig_logiv, ax_logiv = plt.subplots(figsize=(3, 3))
        ax_logiv.set_title("Log IV", fontsize=self.title_font_size)
        ax_logiv.set_xlabel("Voltage (V)", fontsize=self.axis_font_size)
        ax_logiv.set_ylabel("Current", fontsize=self.axis_font_size)
        ax_logiv.set_yscale('log')
        
        canvas_logiv = FigureCanvasTkAgg(fig_logiv, master=frame)
        canvas_logiv.get_tk_widget().grid(row=0, column=5, columnspan=5, sticky="nsew")
        
        line_logiv, = ax_logiv.plot([], [], marker='.')
        
        self.figures['rt_logiv'] = fig_logiv
        self.axes['rt_logiv'] = ax_logiv
        self.canvases['rt_logiv'] = canvas_logiv
        self.lines['rt_logiv'] = line_logiv
    
    # Similar for other plot types...
    
    def update_plot(self, plot_name: str, x_data, y_data):
        """Update a plot with new data"""
        if plot_name not in self.lines:
            return
        
        line = self.lines[plot_name]
        line.set_data(x_data, y_data)
        
        ax = self.axes[plot_name]
        ax.relim()
        ax.autoscale_view()
        
        canvas = self.canvases[plot_name]
        canvas.draw()
    
    def clear_plot(self, plot_name: str):
        """Clear a specific plot"""
        if plot_name not in self.axes:
            return
        
        ax = self.axes[plot_name]
        ax.clear()
        self.canvases[plot_name].draw()
    
    def graphs_show(self, v_arr, c_arr, key, stop_v):
        """Add sweep to 'All' plots (accumulated view)"""
        self.axes['all_iv'].plot(
            v_arr, c_arr, 
            marker='o', markersize=2, 
            label=f"{key}_{stop_v}v", 
            alpha=0.8
        )
        self.axes['all_iv'].legend(loc="best", fontsize="5")
        
        self.axes['all_logiv'].plot(
            v_arr, np.abs(c_arr),
            marker='o', markersize=2,
            label=f"{key}_{stop_v}v",
            alpha=0.8
        )
        self.axes['all_logiv'].legend(loc="best", fontsize="5")
        
        self.canvases['all_iv'].draw()
        self.canvases['all_logiv'].draw()
```

---

### Template 2: Measurments/data_saver.py

```python
"""
Measurement Data Saver

Handles all data persistence, file management, and plot generation for measurements.

Uses the new data_formats.py utilities for consistent formatting.

Author: Refactoring - October 2025
"""

from pathlib import Path
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
import time
from datetime import datetime

from Measurments.data_formats import (
    DataFormatter, 
    FileNamer, 
    save_measurement_data
)


class MeasurementDataSaver:
    """
    Centralized data saving for all measurement types.
    
    Features:
    - Uses standardized data formatting (data_formats.py)
    - Consistent file naming
    - Automatic directory creation
    - Summary plot generation
    - Graph exports
    
    Usage:
        saver = MeasurementDataSaver()
        saver.save_iv_sweep(v, i, t, device="A1", sample="Test")
    """
    
    def __init__(self, base_dir: str = "Data_save_loc"):
        self.base_dir = Path(base_dir)
        self.formatter = DataFormatter()
        self.namer = FileNamer(self.base_dir)
    
    def save_iv_sweep(self,
                     v_arr: List[float],
                     c_arr: List[float],
                     t_arr: List[float],
                     device: str,
                     sample_name: str,
                     sweep_type: str = "FS",
                     stop_v: float = 1.0,
                     metadata: Optional[Dict] = None) -> Path:
        """
        Save IV sweep data with standardized formatting.
        
        Args:
            v_arr: Voltage array
            c_arr: Current array
            t_arr: Timestamp array
            device: Device identifier (e.g., "A1")
            sample_name: Sample name
            sweep_type: Sweep type (FS, PS, NS, Triangle)
            stop_v: Stop voltage
            metadata: Optional metadata dict (step_v, sweeps, etc.)
        
        Returns:
            Path: Path to saved file
        """
        # Get device folder
        folder = self.namer.get_device_folder(sample_name, device)
        folder.mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        filename = self.namer.create_iv_filename(
            device=device,
            voltage=stop_v,
            measurement_type=sweep_type
        )
        
        # Format data
        data, header, fmt = self.formatter.format_iv_data(
            timestamps=np.array(t_arr),
            voltages=np.array(v_arr),
            currents=np.array(c_arr)
        )
        
        # Save
        filepath = folder / filename
        save_measurement_data(filepath, data, header, fmt)
        
        print(f"Saved: {filepath}")
        return filepath
    
    # Move all other save_* methods here, refactored to use utilities
```

---

### Template 3: Measurments/connection_manager.py

```python
"""
Instrument Connection Manager

Centralized management of all instrument connections for measurement GUIs.

Author: Refactoring - October 2025
"""

from typing import Dict, Optional, Any
from Equipment.iv_controller_manager import IVControllerManager
from Equipment.temperature_controller_manager import TemperatureControllerManager
from Equipment.PowerSupplies.Keithley2220 import Keithley2220_Powersupply
from Equipment.optical_excitation import create_optical_from_system_config


class InstrumentConnectionManager:
    """
    Manages connections to all measurement instruments.
    
    Features:
    - Unified connection interface
    - Connection status tracking
    - Automatic cleanup on exit
    - Error handling
    
    Usage:
        mgr = InstrumentConnectionManager(config)
        mgr.connect_all(['keithley', 'psu', 'temp'])
        if mgr.is_connected('keithley'):
            mgr.keithley.set_voltage(1.0, 1e-3)
    """
    
    def __init__(self, config: Dict[str, str]):
        """
        Initialize connection manager.
        
        Args:
            config: System configuration dict with addresses
        """
        self.config = config
        
        # Instrument references
        self.keithley: Optional[Any] = None
        self.psu: Optional[Any] = None
        self.temp_controller: Optional[Any] = None
        self.optical: Optional[Any] = None
        
        # Connection status
        self.connected = {
            'keithley': False,
            'psu': False,
            'temp': False,
            'optical': False
        }
    
    def connect_all(self, instruments: List[str] = ['keithley']) -> Dict[str, bool]:
        """
        Connect to specified instruments.
        
        Args:
            instruments: List of instrument names to connect
        
        Returns:
            Dict mapping instrument name to connection status
        """
        results = {}
        
        for instr in instruments:
            if instr == 'keithley':
                results['keithley'] = self.connect_keithley()
            elif instr == 'psu':
                results['psu'] = self.connect_psu()
            elif instr == 'temp':
                results['temp'] = self.connect_temp_controller()
            elif instr == 'optical':
                results['optical'] = self.connect_optical()
        
        return results
    
    def connect_keithley(self) -> bool:
        """Connect to SMU/PMU via IVControllerManager"""
        try:
            smu_type = self.config.get('SMU Type', 'Keithley 2401')
            address = self.config.get('SMU_address', '')
            
            if not address:
                print("No SMU address configured")
                return False
            
            self.keithley = IVControllerManager(smu_type, address)
            self.connected['keithley'] = self.keithley.is_connected()
            
            if self.connected['keithley']:
                print(f"Connected to {smu_type} at {address}")
                # Optional beep
                if hasattr(self.keithley, 'beep'):
                    self.keithley.beep(4000, 0.2)
            
            return self.connected['keithley']
            
        except Exception as e:
            print(f"Error connecting to Keithley: {e}")
            self.connected['keithley'] = False
            return False
    
    # Similar for other instruments...
    
    def cleanup(self):
        """Safe shutdown of all connected instruments"""
        # Shutdown SMU
        if self.keithley:
            try:
                self.keithley.shutdown()
                print("Keithley shutdown complete")
            except Exception as e:
                print(f"Keithley shutdown error: {e}")
        
        # Disable PSU
        if self.psu:
            try:
                self.psu.disable_channel(1)
                self.psu.disable_channel(2)
                self.psu.close()
                print("PSU shutdown complete")
            except Exception as e:
                print(f"PSU shutdown error: {e}")
        
        # Set temp controller to 0°C
        if self.temp_controller:
            try:
                self.temp_controller.set_temperature_setpoint(0, in_celsius=True)
                self.temp_controller.close()
                print("Temp controller shutdown complete")
            except Exception as e:
                print(f"Temp controller shutdown error: {e}")
```

---

## ✅ Testing Strategy

### Unit Tests (Each Module)

```python
# Test plot_panels.py
def test_plot_creation():
    root = tk.Tk()
    frame = tk.Frame(root)
    plots = MeasurementPlotPanels(frame, {'axis': 8, 'title': 10})
    plots.create_all_plots(frame)
    assert 'rt_iv' in plots.axes
    assert 'rt_logiv' in plots.axes

# Test data_saver.py
def test_data_saving():
    saver = MeasurementDataSaver()
    v = [0, 0.5, 1.0]
    i = [0, 1e-3, 2e-3]
    t = [0, 1, 2]
    path = saver.save_iv_sweep(v, i, t, "A1", "TestSample")
    assert path.exists()

# Test connection_manager.py
def test_connections():
    config = {'SMU Type': 'Keithley 2401', 'SMU_address': 'GPIB0::24::INSTR'}
    mgr = InstrumentConnectionManager(config)
    # Mock connection for testing
    assert hasattr(mgr, 'connect_keithley')
```

### Integration Tests

```python
def test_full_measurement_flow():
    """Test complete measurement with all new modules"""
    # 1. Setup
    config = load_system_config("Lab Small")
    connections = InstrumentConnectionManager(config)
    connections.connect_keithley()
    
    # 2. Execute
    executor = MeasurementExecutor(service, connections)
    v, c, t = executor.execute_dc_triangle_iv({
        'start_v': 0,
        'stop_v': 1,
        'step_v': 0.1,
        'sweep_type': 'FS'
    })
    
    # 3. Save
    saver = MeasurementDataSaver()
    path = saver.save_iv_sweep(v, c, t, "A1", "IntegrationTest")
    
    # 4. Verify
    assert path.exists()
    assert len(v) > 0
    
    # 5. Cleanup
    connections.cleanup()
```

---

## 📋 Step-by-Step Execution Checklist

Use this checklist when implementing the refactoring:

### Preparation
- [ ] Read this plan completely
- [ ] Backup `Measurement_GUI.py` (copy to `Measurement_GUI_BACKUP.py`)
- [ ] Create `GUI/` folder
- [ ] Review new utilities from Phase 1 (data_utils.py, optical_controller.py, etc.)

### Phase 1: Safe Extractions

#### Step 1: Data Saver
- [ ] Create `Measurments/data_saver.py`
- [ ] Copy these methods:
  - [ ] `save_averaged_data()`
  - [ ] `save_all_measurements_file()`
  - [ ] `_save_final_sweep_plot()`
  - [ ] `_save_combined_summary_plot()`
  - [ ] `_create_individual_device_graphs()`
  - [ ] `_create_comparison_graph()`
  - [ ] `create_log_file()`
- [ ] **Refactor to use `data_formats.py` utilities** ⭐
- [ ] Add imports to main file: `from Measurments.data_saver import MeasurementDataSaver`
- [ ] In `__init__`: `self.saver = MeasurementDataSaver()`
- [ ] Replace all calls: `self.save_*()` → `self.saver.save_*()`
- [ ] Test: Run a measurement and verify files save correctly
- [ ] Delete old methods from main file

#### Step 2: Plot Panels
- [ ] Create `GUI/plot_panels.py`
- [ ] Copy these methods:
  - [ ] `graphs_main_iv()`
  - [ ] `graphs_all()`
  - [ ] `graphs_vi_logiv()`
  - [ ] `graphs_current_time_rt()`
  - [ ] `graphs_resistance_time_rt()`
  - [ ] `graphs_temp_time_rt()`
  - [ ] `graphs_endurance_retention()`
  - [ ] `graphs_show()`
  - [ ] `clear_axis()`
- [ ] Refactor to use dictionaries for storage
- [ ] Add to main file: `from GUI.plot_panels import MeasurementPlotPanels`
- [ ] In `__init__`: `self.plots = MeasurementPlotPanels(...)`
- [ ] Replace: `self.ax_rt_iv` → `self.plots.axes['rt_iv']`
- [ ] Replace: `self.graphs_show()` → `self.plots.graphs_show()`
- [ ] Test: Verify plots appear and update correctly
- [ ] Delete old methods from main file

#### Step 3: Connection Manager
- [ ] Create `Measurments/connection_manager.py`
- [ ] Copy these methods:
  - [ ] `connect_keithley()`
  - [ ] `connect_keithley_psu()`
  - [ ] `connect_temp_controller()`
  - [ ] `reconnect_temperature_controller()`
  - [ ] `init_temperature_controller()`
  - [ ] `update_controller_status()`
  - [ ] `cleanup()`
- [ ] Add to main file: `from Measurments.connection_manager import InstrumentConnectionManager`
- [ ] In `__init__`: `self.connections = InstrumentConnectionManager(config)`
- [ ] Replace: `self.keithley` → `self.connections.keithley`
- [ ] Replace: `self.connect_keithley()` → `self.connections.connect_keithley()`
- [ ] Test: Verify instruments connect correctly
- [ ] Delete old methods from main file

### Phase 2: Complex Extractions

#### Step 4: Plot Updaters
- [ ] Create `GUI/plot_updaters.py`
- [ ] Copy these methods:
  - [ ] `plot_voltage_current()`
  - [ ] `plot_current_time()`
  - [ ] `plot_resistance_time()`
  - [ ] `plot_Temp_time()`
  - [ ] `plot_vi_logilogv()`
  - [ ] `_status_update_tick()`
- [ ] Refactor to accept plot panels and data references
- [ ] Add to main file: `from GUI.plot_updaters import PlotUpdaters`
- [ ] In `__init__`: `self.updaters = PlotUpdaters(self.plots, shared_data)`
- [ ] Test: Verify real-time plotting still works
- [ ] Delete old thread methods from main file

#### Step 5: Layout Builder
- [ ] Create `GUI/layout_builder.py`
- [ ] Copy these methods:
  - [ ] `create_connection_section()`
  - [ ] `create_mode_selection()`
  - [ ] `create_status_box()`
  - [ ] `create_controller_selection()`
  - [ ] `create_sweep_parameters()`
  - [x] `create_custom_measurement_section()`
  - [x] `create_manual_endurance_retention()`
  - [ ] `create_automated_tests_section()`
  - [ ] `temp_measurments_itc4()`
  - [ ] `signal_messaging()`
  - [x] `sequential_measurments()`
  - [ ] `top_banner()`
- [ ] Refactor to store widgets and variables
- [ ] Provide `get_values()` method
- [ ] Add to main file: `from GUI.layout_builder import MeasurementGUILayoutBuilder`
- [ ] Test: Verify GUI appears correctly
- [ ] Delete old create_* methods from main file

#### Step 6: Measurement Executor
- [ ] Create `Measurments/measurement_executor.py`
- [ ] Copy these methods:
  - [ ] `start_measurement()`
  - [ ] `run_custom_measurement()`
  - [ ] `sequential_measure()`
  - [ ] `measure_average_current()`
  - [ ] `retention_measure()`
  - [ ] `start_manual_endurance()` + worker
  - [ ] `start_manual_retention()` + worker
- [ ] **Refactor to use new utilities:** ⭐
  - [ ] Replace tuple checks with `safe_measure_current()`
  - [ ] Replace optical if-blocks with `OpticalController`
  - [ ] Replace voltage list building with `build_sweep_values()`
  - [ ] Add support for `SourceMode.CURRENT` (NEW!)
- [ ] Add to main file: `from Measurments.measurement_executor import MeasurementExecutor`
- [ ] Test: Verify all measurement types work
- [ ] Delete old measurement methods from main file

### Phase 3: Polish

#### Step 7: Telegram Coordinator
- [ ] Create `Measurments/telegram_coordinator.py`
- [ ] Copy bot-related methods
- [ ] Test: Verify Telegram notifications work
- [ ] Delete old bot methods from main file

#### Step 8: Background Workers
- [ ] Create `Measurments/background_workers.py`
- [ ] Extract thread management logic
- [ ] Test: Verify async operations work
- [ ] Delete old thread wrappers from main file

### Final Verification
- [ ] Run full measurement end-to-end
- [ ] Verify all plots update
- [ ] Verify data saves correctly
- [ ] Verify Telegram works (if configured)
- [ ] Check line count: `Measurement_GUI.py` should be ~1,000 lines
- [ ] No linting errors
- [ ] Commit changes

---

## 🔧 Code Migration Examples

### Example 1: Migrating Data Saving

**Before (in Measurement_GUI.py):**
```python
def save_averaged_data(self, device_data, sample_name, start_index, interrupted=False):
    # 150 lines of complex saving logic with duplicated formatting
    if self.record_temp_var.get():
        data = np.column_stack((timestamps, temperatures, voltages, currents, std_errors,
                                resistance, conductance, conductance_normalized))
        header = "Time(s)\tTemperature(C)\tVoltage(V)\tCurrent(A)\t..."
        fmt = "%0.3E\t%0.3E\t%0.3E\t%0.3E\t..."
    else:
        data = np.column_stack((timestamps, voltages, currents, std_errors, ...))
        header = "Time(s)\tVoltage(V)\tCurrent(A)\t..."
        fmt = "%0.3E\t%0.3E\t%0.3E"
    
    np.savetxt(file_path, data, fmt=fmt, header=header, comments="# ")
```

**After (using new modules):**
```python
# In Measurments/data_saver.py
from Measurments.data_formats import DataFormatter, save_measurement_data

def save_averaged_data(self, device_data, sample_name, **kwargs):
    for device, data in device_data.items():
        # Clean, standardized formatting
        formatted_data, header, fmt = self.formatter.format_iv_data(
            timestamps=np.array(data['timestamps']),
            voltages=np.array(data['voltages']),
            currents=np.array(data['currents']),
            temperatures=np.array(data['temperatures']) if data['temperatures'] else None
        )
        
        filepath = self._get_filepath(device, sample_name)
        save_measurement_data(filepath, formatted_data, header, fmt)
```

---

### Example 2: Migrating Measurement Execution

**Before (in Measurement_GUI.py):**
```python
def start_measurement(self):
    # 700+ lines of branching logic
    
    # Scattered optical control
    if optical is not None:
        optical.set_enabled(True)
    elif psu is not None:
        psu.led_on_380(power)
    
    # Manual voltage list building
    if sweep_type == "FS":
        forward = list(np.arange(start, stop, step))
        reverse = list(np.arange(stop, start, -step))
        v_list = forward + reverse
    
    # Tuple normalization
    for v in v_list:
        keithley.set_voltage(v, icc)
        current_tuple = keithley.measure_current()
        current = current_tuple[1] if isinstance(current_tuple, (list, tuple)) else float(current_tuple)
```

**After (using new modules):**
```python
# In Measurments/measurement_executor.py
from Measurments.optical_controller import OpticalController
from Measurments.sweep_patterns import build_sweep_values, SweepType
from Measurments.data_utils import safe_measure_current
from Measurments.source_modes import SourceMode, apply_source

def execute_dc_triangle_iv(self, config):
    # Clean optical control
    self.optical_ctrl.enable(config['led_power'])
    
    # Clean voltage list generation
    voltages = build_sweep_values(
        config['start_v'],
        config['stop_v'],
        config['step_v'],
        SweepType.FULL
    )
    
    # Clean measurement with source mode support
    v_arr, c_arr = [], []
    for v in voltages:
        apply_source(self.keithley, SourceMode.VOLTAGE, v, config['icc'])
        c = safe_measure_current(self.keithley)
        v_arr.append(v)
        c_arr.append(c)
    
    self.optical_ctrl.disable()
    return v_arr, c_arr
```

**Benefits:**
- ✅ 50% fewer lines
- ✅ Uses proven utilities
- ✅ Supports current source mode (NEW!)
- ✅ Much more readable

---

## 🎨 Interface Definitions

### Communication Between Modules

**Main GUI → Layout Builder:**
```python
# Callbacks passed to layout builder
callbacks = {
    'start_measurement': self.start_measurement,
    'stop_measurement': self.set_measurement_flag_true,
    'connect_keithley': self.connections.connect_keithley,
    'toggle_led': self.toggle_led,
    # ... all button callbacks
}

layout = MeasurementGUILayoutBuilder(parent, callbacks)
```

**Main GUI → Plot Panels:**
```python
# Shared data for plotting
plot_data = {
    'v_arr_disp': self.v_arr_disp,
    'c_arr_disp': self.c_arr_disp,
    't_arr_disp': self.t_arr_disp,
    'measuring': lambda: self.measuring
}

plots = MeasurementPlotPanels(graph_frame, font_config)
updaters = PlotUpdaters(plots, plot_data)
```

**Main GUI → Executor:**
```python
# Executor needs instruments and service
executor = MeasurementExecutor(
    measurement_service=self.measurement_service,
    keithley=self.connections.keithley,
    psu=self.connections.psu,
    optical=self.connections.optical
)

# Execute measurement
results = executor.execute_dc_triangle_iv(params)
```

---

## 🚨 Common Pitfalls and Solutions

### Pitfall 1: Circular Dependencies
**Problem:** Main GUI imports executor, executor imports GUI for callbacks

**Solution:** Use dependency injection
```python
# WRONG
class MeasurementExecutor:
    def __init__(self, gui):
        self.gui = gui  # Circular!

# RIGHT
class MeasurementExecutor:
    def __init__(self, on_progress: Callable):
        self.on_progress = on_progress  # Clean callback
```

### Pitfall 2: Shared State
**Problem:** Multiple modules modifying same variables

**Solution:** Use explicit data containers
```python
# Create shared data container
class MeasurementState:
    def __init__(self):
        self.v_arr_disp = []
        self.c_arr_disp = []
        self.measuring = False

# Pass to all modules
state = MeasurementState()
executor = MeasurementExecutor(state)
updaters = PlotUpdaters(state)
```

### Pitfall 3: Tk Variable Access
**Problem:** Modules can't access GUI's Tk variables

**Solution:** Layout builder provides `get_values()` method
```python
# Layout builder stores all Tk vars internally
class LayoutBuilder:
    def get_values(self):
        return {
            'start_v': self.vars['start_voltage'].get(),
            'stop_v': self.vars['voltage_high'].get(),
            # ... all parameters
        }

# Main GUI queries when needed
params = self.layout.get_values()
results = self.executor.execute_measurement(params)
```

---

## 📈 Expected Improvements

### Code Quality

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Lines per file | 5,899 | ~1,000 | 83% reduction |
| Methods in main class | ~60 | ~15 | 75% reduction |
| Duplicate patterns | Many | Few | Uses Phase 1 utilities |
| Testability | Low | High | Isolated modules |
| Reusability | None | High | Components shareable |

### Development Velocity

| Task | Before | After |
|------|--------|-------|
| Find a method | Search 5,899 lines | Search ~800 lines (one file) |
| Add new measurement | Modify monolith | Add to executor |
| Fix plotting bug | Risk breaking measurements | Only touch plot_panels.py |
| Test a feature | Full integration test | Unit test module |
| Onboard developer | Read 5,899 lines | Read 8 focused files |

---

## 🔄 Backward Compatibility

### Ensure Existing Code Works

**Strategy:** Keep old methods temporarily with deprecation wrapper

```python
# In Measurement_GUI.py (during migration)
def save_averaged_data(self, *args, **kwargs):
    """DEPRECATED: Use self.saver.save_averaged_data()"""
    print("Warning: Calling deprecated save_averaged_data")
    return self.saver.save_averaged_data(*args, **kwargs)
```

**Remove after migration complete and verified.**

---

## 📚 Additional Refactoring Opportunities

### Use New Utilities from Phase 1

Throughout all modules, replace old patterns:

#### Replace Tuple Normalization (34 locations)
```python
# OLD
current_tuple = keithley.measure_current()
current = current_tuple[1] if isinstance(current_tuple, (list, tuple)) else float(current_tuple)

# NEW
from Measurments.data_utils import safe_measure_current
current = safe_measure_current(keithley)
```

#### Replace Optical Control (26 locations)
```python
# OLD
if optical is not None:
    optical.set_enabled(True)
elif psu is not None:
    psu.led_on_380(power)

# NEW
from Measurments.optical_controller import OpticalController
OpticalController(optical, psu).enable(power)
```

#### Replace Sweep Generation (7 locations)
```python
# OLD
if sweep_type == "FS":
    forward = list(np.arange(start, stop, step))
    reverse = list(np.arange(stop, start, -step))
    v_list = forward + reverse

# NEW
from Measurments.sweep_patterns import build_sweep_values, SweepType
v_list = build_sweep_values(start, stop, step, SweepType.FULL)
```

---

## 🎯 Success Criteria

### Module-Level

- [ ] Each module has single, clear responsibility
- [ ] Each module is independently testable
- [ ] Each module has comprehensive docstrings
- [ ] No circular dependencies
- [ ] Clean interfaces between modules

### System-Level

- [ ] All measurements produce identical results
- [ ] No regressions in functionality
- [ ] GUI appears and behaves identically
- [ ] Performance is equal or better
- [ ] Code is more maintainable

### Documentation

- [ ] Each module has usage examples
- [ ] Migration guide is clear
- [ ] Testing strategy is documented
- [ ] Interface contracts are defined

---

## 🔮 Future Enhancements Enabled

With this modular architecture, new features become trivial:

### 1. Current Source Mode GUI
```python
# Add radio buttons in layout_builder.py
tk.Radiobutton(frame, text="Source Voltage", value="voltage").pack()
tk.Radiobutton(frame, text="Source Current", value="current").pack()

# Use in measurement_executor.py
mode = SourceMode.CURRENT if params['mode'] == 'current' else SourceMode.VOLTAGE
apply_source(keithley, mode, value, compliance)
measurement = measure_result(keithley, mode)
```

### 2. Reuse Components in Other GUIs
```python
# In Motor_Control_GUI.py - reuse same components!
from GUI.layout_builder import MeasurementGUILayoutBuilder
from GUI.plot_panels import MeasurementPlotPanels
from Measurments.connection_manager import InstrumentConnectionManager

# Build consistent GUI with shared code
```

### 3. Add New Measurement Types
```python
# Just add to measurement_executor.py
def execute_capacitance_measurement(self, config):
    # New measurement type in one place
```

---

## 🏁 Post-Refactoring Action

### After Completing Measurement_GUI Refactoring

**ASK THE USER:**

> "✅ Measurement_GUI.py refactoring complete! 
> 
> You have several other GUI files that could benefit from similar modularization:
> 
> 1. **Motor_Control_GUI.py** - Unknown size, likely has similar patterns
> 2. **PMU_Testing_GUI.py** - Unknown size
> 3. **Automated_tester_GUI.py** - 1,009 lines
> 4. **Sample_GUI.py** - 820 lines
> 5. **Check_Connection_GUI.py** - Unknown size
> 6. **advanced_tests_gui.py** - Unknown size
> 
> **How would you like to proceed?**
> 
> Options:
> - A) Apply similar refactoring to all GUI files systematically
> - B) Focus on the largest/most problematic GUI next
> - C) Create reusable GUI component library first, then migrate all GUIs
> - D) Pause refactoring and test current changes first
> - E) Custom approach (please specify)
> 
> I can analyze each GUI file and create refactoring plans similar to this one."

---

## 📊 Estimated Effort

| Phase | Tasks | Estimated Time | Risk Level |
|-------|-------|----------------|------------|
| Phase 1 (Steps 1-3) | Extract safe modules | 4-6 hours | Low |
| Phase 2 (Steps 4-6) | Extract complex modules | 6-8 hours | Medium |
| Phase 3 (Steps 7-8) | Polish and cleanup | 2-4 hours | Low |
| Testing | Full verification | 2-3 hours | - |
| **Total** | **All steps** | **14-21 hours** | **Low-Medium** |

**Recommendation:** Do one step per day, test thoroughly before proceeding.

---

## 📖 Reference Documentation

### Files Created in Phase 1 (Already Done)
- ✅ `Measurments/data_utils.py` - Measurement normalization
- ✅ `Measurments/optical_controller.py` - Optical/LED control
- ✅ `Measurments/source_modes.py` - Voltage/current modes
- ✅ `Measurments/sweep_patterns.py` - Sweep generation
- ✅ `Measurments/data_formats.py` - Data formatting
- ✅ `Equipment/multiplexer_manager.py` - Multiplexer abstraction

### Files to Create in This Phase
- 🔲 `GUI/plot_panels.py`
- 🔲 `GUI/plot_updaters.py`
- 🔲 `GUI/layout_builder.py`
- 🔲 `Measurments/measurement_executor.py`
- 🔲 `Measurments/data_saver.py`
- 🔲 `Measurments/connection_manager.py`
- 🔲 `Measurments/telegram_coordinator.py`
- 🔲 `Measurments/background_workers.py`

---

## 🎓 AI Execution Instructions

**If executing this plan in a new chat without the original context:**

### Context Needed
1. Read `Changes_Ai_Fixes/REFACTORING_SUMMARY.md` (Phase 1 utilities)
2. Read current `Measurement_GUI.py` file
3. Verify Phase 1 utilities exist and work

### Execution Steps
1. Start with Phase 1, Step 1 (Data Saver)
2. Follow checklist exactly
3. Test after each module extraction
4. Don't proceed to next step if tests fail
5. Keep old methods until verification complete
6. Use provided code templates as starting points
7. Ensure new modules use Phase 1 utilities (data_utils.py, optical_controller.py, etc.)
8. After all steps complete, ask user about other GUI files (see "Post-Refactoring Action" section above)

### Testing Protocol
```python
# After each module extraction, run:
1. python -m <new_module_name>  # Built-in tests
2. Run GUI and test one measurement
3. Verify data saves correctly
4. Check plots update
5. Look for any exceptions in console
```

### Success Indicators
- GUI appears and functions identically
- All measurements produce same results as before
- Files save in same format and location
- No new errors or warnings
- Line count of `Measurement_GUI.py` decreases appropriately

---

## 📌 Quick Reference Commands

### Create Backup
```bash
cp Measurement_GUI.py Measurement_GUI_BACKUP.py
```

### Check Line Counts
```bash
# Windows PowerShell
(Get-Content Measurement_GUI.py).Count
(Get-Content GUI/plot_panels.py).Count
(Get-Content Measurments/data_saver.py).Count
```

### Run Tests
```bash
python -m GUI.plot_panels
python -m Measurments.data_saver
python -m Measurments.connection_manager
```

### Verify No Errors
```bash
python -m py_compile Measurement_GUI.py
python -m py_compile GUI/*.py
python -m py_compile Measurments/*.py
```

---

## 🎉 End Goal Visualization

### Before
```
Measurement_GUI.py (5,899 lines)
├── 12 GUI methods (1,200 lines)
├── 12 plotting methods (1,100 lines)
├── 8 measurement methods (2,500 lines)
├── 5 saving methods (600 lines)
├── 4 connection methods (200 lines)
├── 5 telegram methods (400 lines)
└── 10+ utilities (400 lines)

Result: Monolithic, hard to maintain ❌
```

### After
```
Measurement_GUI.py (1,000 lines - orchestration only)
├── GUI/
│   ├── layout_builder.py (1,200 lines)
│   ├── plot_panels.py (800 lines)
│   └── plot_updaters.py (300 lines)
├── Measurments/
│   ├── measurement_executor.py (1,500 lines)
│   ├── data_saver.py (600 lines)
│   ├── connection_manager.py (200 lines)
│   ├── telegram_coordinator.py (400 lines)
│   └── background_workers.py (300 lines)
└── Phase 1 Utilities/
    ├── data_utils.py ✅
    ├── optical_controller.py ✅
    ├── source_modes.py ✅
    ├── sweep_patterns.py ✅
    └── data_formats.py ✅

Result: Modular, maintainable, extensible ✅
```

---

## ✅ This Plan is Complete and Self-Contained

Everything needed to execute this refactoring is in this document:
- ✅ Clear aim and end goal
- ✅ Detailed architecture design
- ✅ Step-by-step instructions
- ✅ Code templates for each module
- ✅ Testing strategy
- ✅ Migration checklist
- ✅ Common pitfalls and solutions
- ✅ Success criteria
- ✅ AI execution instructions
- ✅ Post-completion action (ask about other GUI files)

**Ready to execute in a fresh chat without additional questions!**

---

**Created:** October 14, 2025  
**Status:** Ready for implementation  
**Estimated Effort:** 14-21 hours over 1-2 weeks  
**Risk:** Low-Medium (well-defined, testable steps)

