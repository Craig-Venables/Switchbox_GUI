# Motor Control GUI — Architecture Reference

> **Documentation accuracy:** These notes are a snapshot of the repository at the time they were written. Hardware integrations, default paths, and UI layout change over time. Use this for **orientation**; confirm behavior in the current source.

---

## 1. General overview

### 1.1 Purpose

The **Motor Control GUI** (`gui/motor_control_gui/`) is a **standalone Tk application** for **Thorlabs Kinesis XY stages** used to position a sample or laser spot. It combines:

- **Motor control** — connect, home, jog, go-to coordinates, presets, raster scan patterns  
- **Visual workspace** — square canvas mapping **world coordinates (mm)** to stage position with a laser marker  
- **Function generator** — optional Siglent-style VISA connection for **laser drive** (DC level / amplitude)  
- **Direct laser** — optional **Oxxius** laser via **`LaserManager`** (serial port)  
- **Camera** — optional OpenCV **USB** or **IP stream** overlay (threaded capture; see `CAMERA_DISPLAY_ISSUES.md` if troubleshooting)

### 1.2 Entry points

- **Standalone:** `python -m gui.motor_control_gui.main` or instantiate `MotorControlWindow()` and call **`run()`** (`root.mainloop()`).
- **From Measurement GUI:** `MeasurementGUI.open_motor_control()` constructs **`MotorControlWindow()`** with no arguments. The measurement GUI keeps a reference on **`self.motor_control_window`** and tries to **`lift()`** an existing window if present.

**Important integration detail:** `MotorControlWindow` creates its own **`tk.Tk()`** as **`self.root`**. It is **not** embedded as a `Toplevel` under the measurement window. Any “single instance” logic in the caller should key off **`window.root`** (or equivalent), not the Python wrapper object alone—verify `open_motor_control` in current `measurement_gui/main.py` if behavior seems wrong.

### 1.3 Package layout

```
gui/motor_control_gui/
├── __init__.py           # exports MotorControlWindow
├── main.py               # MotorControlWindow — state, handlers, camera thread, motor/FG/laser
├── config.py             # COLORS, PRESETS_FILE, FG_ADDRESSES, LASER_CONFIGS
├── ui/
│   ├── widgets.py        # CollapsibleFrame
│   ├── header.py         # connect row, position readout
│   ├── controls_panel.py # scrollable stack of sections
│   ├── jog_controls.py
│   ├── goto_controls.py
│   ├── motor_settings.py
│   ├── presets.py
│   ├── scan_controls.py
│   ├── fg_controls.py
│   ├── laser_controls.py
│   ├── canvas_camera.py  # canvas + camera UI
│   └── status_bar.py
├── README.md
├── CHANGELOG.md
└── CAMERA_DISPLAY_ISSUES.md
```

Hardware constants (velocity, acceleration, default VISA strings) come from **`Equipment/Motor_Controll/config.py`** (`hw_config` in code). Presets persist to **`motor_presets.json`** in the process working directory by default (`gui_config.PRESETS_FILE`).

---

## 2. Main class: `MotorControlWindow` (`main.py`)

### 2.1 Constructor parameters

| Parameter | Default (typical) | Role |
|-----------|-------------------|------|
| `function_generator` | `None` | Optional injected FG; else UI uses `FunctionGeneratorManager` |
| `default_amplitude_volts` | `0.4` | Initial FG amplitude string |
| `canvas_size_pixels` | `500` | Square canvas side |
| `world_range_units` | **`25.0`** | Half-range mapping (mm)—**README may say 50; code default is 25** |

### 2.2 Optional dependencies (import guards)

- **`KinesisController`** from `Equipment.Motor_Controll.Kenisis_motor_control` — if missing, `MOTOR_DRIVER_AVAILABLE` is false; motor actions should no-op or warn.  
- **`FunctionGeneratorManager`** — FG tab uses manager when not injecting `function_generator`.  
- **`LaserManager`** — Oxxius path.  
- **OpenCV / PIL / NumPy** — camera path (`CAMERA_AVAILABLE`).

### 2.3 UI build order

`__init__` creates **`self.root`**, then calls UI builders from **`gui.motor_control_gui.ui`**:

- `create_header`  
- `create_controls_panel` — collapsible sections (jog, go-to, presets, motor settings, scan, FG, laser)  
- `create_canvas_and_camera`  
- `create_status_bar`  

Keyboard bindings (arrow jog, H/G/S, Ctrl+Q) are wired in `main.py`.

### 2.4 Core behaviors

- **Connect / disconnect** — initializes or tears down `self.motor` (`KinesisController`).  
- **Homing** — establishes `(0,0)` reference; canvas Y often has **origin at bottom** (see module docstring).  
- **Jog** — step from `var_step`; updates `current_x` / `current_y` and marker.  
- **Presets** — load/save JSON dict name → `(x, y)`.  
- **Raster scan** — parameterized X/Y extent and line count; runs in a worker pattern (check implementation for threading).  
- **FG** — VISA address combo from `gui_config.FG_ADDRESSES` + `hw_config.LASER_USB`; connect, enable output, set amplitude.  
- **Laser** — serial port/baud presets from `LASER_CONFIGS`; power and emission toggles; **`close()`** restores analog modulation / safe state per `_on_laser_disconnect` path.  
- **Camera** — separate thread filling `current_camera_frame` with lock; UI schedules `_update_camera_display` on `root`.

### 2.5 Public API

- **`run()`** — `self.root.mainloop()`.  
- **`close()`** — stop camera, disconnect laser safely, `root.destroy()`.

---

## 3. Configuration files

| Location | Role |
|----------|------|
| `Equipment/Motor_Controll/config.py` | `MAX_VELOCITY`, `MAX_ACCELERATION`, default VISA/USB IDs |
| `gui/motor_control_gui/config.py` | Theme colors, `PRESETS_FILE`, FG address list, laser COM presets |
| `motor_presets.json` (cwd) | Saved XY presets |

---

## 4. Relationships

```
MeasurementGUI.open_motor_control()
        │
        ▼
MotorControlWindow()  →  own tk.Tk() root
        │
        ├─► Equipment.Motor_Controll.Kenisis_motor_control.MotorController
        ├─► Equipment.managers.function_generator.FunctionGeneratorManager (optional)
        ├─► Equipment.managers.laser.LaserManager (optional)
        └─► OpenCV / PIL (optional camera)
```

---

## 5. Related documentation

- **`gui/motor_control_gui/README.md`** — feature list and shortcuts  
- **`Documents/reference/MEASUREMENT_AND_SAMPLE_GUI_REFERENCE.md`** — launcher context  
- **`README.md` (root)** — motor + camera overview  

---

*Other GUI references in `Documents/reference/`: `PULSE_TESTING_GUI_REFERENCE.md`, `CONNECTION_CHECK_GUI_REFERENCE.md`, `OSCILLOSCOPE_PULSE_GUI_REFERENCE.md`.*
