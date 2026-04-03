# Oscilloscope Pulse GUI — Architecture Reference

> **Documentation accuracy:** This module is actively developed; threading delays, scope models, and SMU integration change. Treat this document as **orientation** only and read `gui/oscilloscope_pulse_gui/main.py`, `logic.py`, and `layout.py` for authoritative behavior.

---

## 1. General overview

### 1.1 Purpose

The **Oscilloscope Pulse GUI** (`gui/oscilloscope_pulse_gui/`) is a **`tk.Toplevel`** application that coordinates:

- **SMU** — apply a **voltage pulse** (or bias/hold sequence) to the device under test  
- **Oscilloscope** — capture **waveform data** after the pulse (triggered or timed read)  
- **Post-processing** — convert captured **voltage** across a **shunt** (or other method) into **current**, plot **V/I vs time**, save CSV/plots  

It supports **simulation mode** (no hardware) for UI testing and includes helpers for **Tektronix TBS1000C**-style scopes via **`Equipment.managers.oscilloscope.OscilloscopeManager`**.

### 1.2 Entry points

- **From Measurement GUI:** `MeasurementGUI.open_oscilloscope_pulse` builds a **`context`** dict (device label, sample name, save directory, VISA port lists, **`provider=self`**) and passes an **SMU adapter** instance to **`OscilloscopePulseGUI(master, smu_instance=adapter, context=context)`**.  
- **Standalone:** Running **`main.py` as `__main__`** adjusts `sys.path` and may create **`tk.Tk()`** if no master—see the conditional block at the top of `main.py` (dual import style for package vs script).

**Class:** **`OscilloscopePulseGUI`** — controller that owns **`ConfigManager`**, optional **`SystemWrapper`**, **`PulseMeasurementLogic`**, and **`OscilloscopePulseLayout`**.

### 1.3 Package layout

```
gui/oscilloscope_pulse_gui/
├── main.py              # OscilloscopePulseGUI — wiring, context, callbacks, system JSON
├── layout.py            # OscilloscopePulseLayout — top bar, left controls, right plots
├── logic.py             # PulseMeasurementLogic — threads, SMU+scope sequence, simulation
├── config.py            # COLORS, THEME, fonts (static GUI styling)
├── config_manager.py    # load/save pulse_gui_config.json next to this package
├── pulse_gui_config.json # persisted pulse/scope defaults (merged with defaults in code)
├── ui/
│   ├── header.py        # create_top_bar, help dialog
│   ├── controls_panel.py
│   ├── connection.py    # SMU/scope connection UI
│   ├── pulse.py         # pulse parameter frame
│   ├── measurement.py   # measurement options
│   ├── scope.py         # scope settings
│   ├── plots.py         # matplotlib figures
│   ├── action_buttons.py
│   ├── save_options.py
│   ├── calculator.py  # shunt / scaling helpers
│   ├── status_bar.py
│   └── widgets.py     # ToolTip, collapsible helpers
├── test_scripts/        # bench utilities (grab waveform, probe attenuation, etc.)
└── *.md                 # FIXES, walkthrough, checklists (developer notes)
```

There is **no** `gui/oscilloscope_pulse_gui/__init__.py` in the tree snapshot used for this doc; imports are typically **`from gui.oscilloscope_pulse_gui.main import OscilloscopePulseGUI`** (as Measurement GUI does).

---

## 2. Architecture: MVC-style split

| Layer | Module | Responsibility |
|-------|--------|----------------|
| **View** | `layout.py` + `ui/*` | Builds widgets; stores `vars` / `widgets`; calls **callbacks** dict passed from controller |
| **Controller** | `main.py` | `OscilloscopePulseGUI` — fills context, handles `_start_measurement`, `_stop_measurement`, save dialogs, SMU connect, system list from `system_configs.json` |
| **Model / worker** | `logic.py` | `PulseMeasurementLogic` — **`start_measurement`**, **`send_pulse_only`**, **`grab_scope_only`**, background **`_measurement_worker`**, stop event, `OscilloscopeManager` |

**Config:** **`ConfigManager`** reads/writes **`pulse_gui_config.json`** beside `config_manager.py`, merging with **`default_config`** (pulse voltage, duration, compliance, bias, scope address/type, channel, trigger, timebase, shunt resistance, simulation flag, etc.).

---

## 3. `OscilloscopePulseGUI` (`main.py`) — highlights

- **`__init__(master, smu_instance=None, context=None)`**  
  - Loads config via **`ConfigManager`**.  
  - **`self.system_wrapper`** — `SystemWrapper()` when import succeeds (4200/2450 routing parity with pulse testing stack).  
  - **`self.logic = PulseMeasurementLogic(smu_instance)`** — may be updated when SMU reconnects.  
  - **`context`** may include: `device_label`, `sample_name`, `save_directory`, `smu_ports`, `scope_ports`, **`provider`** (Measurement GUI reference for live attributes).  
- **Scrollable outer frame** — `Canvas` + scrollbars wrapping **`content_frame`**.  
- **`OscilloscopePulseLayout`** receives **callbacks**: `start`, `start_no_config`, `grab_scope`, `pulse_only`, `stop`, `save`, `browse_save`, `refresh_scopes`, `on_system_change`, `quick_test`, `read_scope_settings`, `connect_smu`, `on_alignment_applied`.  
- **`_load_systems_from_json`** — reads **`Json_Files/system_configs.json`** like Measurement GUI (named lab configs).  
- **`_resolve_default_save_root`** — same OneDrive/Documents **`Data_folder`** preference order as other GUIs.  
- **`WM_DELETE_WINDOW`** → **`_on_close`** for cleanup.

---

## 4. `PulseMeasurementLogic` (`logic.py`) — highlights

- Holds **`self.smu`** and **`OscilloscopeManager`** (if import ok).  
- **`start_measurement(params, on_progress, on_data, on_error, on_finished)`** — spawns daemon **thread** running **`_measurement_worker`**.  
- Uses module-level timing constants (e.g. **`SMU_POST_COMMAND_WAIT_S`**, scope pre-trigger wait)—**tune in code**; comments in file may not match numeric values (verify file).  
- **`KEITHLEY4200_SYSTEM_IDS`** — branches for 4200 family vs other SMUs where timing/command paths differ.  
- **Simulation mode** — when enabled in config, synthesizes waveforms without VISA.  
- Additional entry points: **`send_pulse_only`**, scope-only grab, etc., for partial workflows.

---

## 5. `OscilloscopePulseLayout` (`layout.py`) — highlights

- Applies ttk styles from **`gui_config`** (`THEME`, `COLORS`, fonts).  
- **`_build_layout`:** `create_top_bar` → horizontal split: **`create_controls_panel`** (left), **`create_plots`** (right).  
- Contains optional **collapsible** sections (e.g. quick test) via internal toggles.

---

## 6. Persistence and defaults

| Artifact | Role |
|----------|------|
| `pulse_gui_config.json` | User’s last pulse/scope/simulation settings |
| `Json_Files/system_configs.json` | Named instrument systems (shared with Measurement GUI) |

---

## 7. Dependencies

- **tkinter**, **matplotlib**, **numpy**  
- **`Equipment.managers.oscilloscope`** — optional  
- **`Pulse_Testing.system_wrapper`** / **`keithley4200_constants`** — optional parity with pulse-testing stack  
- **`Measurements.connection_manager`** — optional for standalone dropdown population  

---

## 8. Relationships

```
MeasurementGUI.open_oscilloscope_pulse()
        │
        ▼
OscilloscopePulseGUI(master, smu_instance=adapter, context={..., provider})
        │
        ├─► OscilloscopePulseLayout (ui)
        ├─► PulseMeasurementLogic → OscilloscopeManager + SMU
        ├─► ConfigManager → pulse_gui_config.json
        └─► SystemWrapper (optional) + system_configs.json
```

---

## 9. Further reading (in-repo)

- **`gui/oscilloscope_pulse_gui/SIMPLE_USAGE_GUIDE.md`** — operator-style steps  
- **`gui/oscilloscope_pulse_gui/FIXES_AND_USAGE.md`**, **`V_SMU_FIXES_AND_USAGE.md`** — known issues / versions  
- **`gui/oscilloscope_pulse_gui/REFACTOR_SUMMARY.md`** — structural history  

---

*Other GUI references in `Documents/reference/`: `MEASUREMENT_AND_SAMPLE_GUI_REFERENCE.md`, `PULSE_TESTING_GUI_REFERENCE.md`, `MOTOR_CONTROL_GUI_REFERENCE.md`, `CONNECTION_CHECK_GUI_REFERENCE.md`.*
