# Measurement GUI — Architecture

## Role

`MeasurementGUI` coordinates instrument connections, measurement execution, plotting, and launching child tools. UI construction is delegated to `MeasurementGUILayoutBuilder` and tab modules.

## Module layout

```
gui/measurement_gui/
├── main.py              # Orchestrator: lifecycle, callbacks, measurement threads
├── layout_builder.py    # Top bar, notebook shell, section delegates
├── layout/
│   ├── tab_registry.py  # Single source of truth for tab order
│   ├── help_dialog.py   # Measurement GUI help window
│   ├── tab_*.py         # One builder per notebook tab
│   └── sections/        # Collapsible panels used inside tabs
├── child_gui_launchers.py # Launch implementations for top-bar child GUIs
├── child_gui_registry.py # In-process child GUI top-bar launchers
├── save_path_controller.py # Data folder paths and custom save config
├── sample_gui_sync.py     # SampleGUI change notifications and plot overlay
├── connection_controller.py # SMU/PSU/temp connect and auto-connect
├── system_config_controller.py # system_configs.json load/save, optical setup
├── lifecycle_controller.py # atexit instrument shutdown
├── custom_measurement_runner.py # Custom sweep plan execution thread body
├── smu_adapter.py         # IV controller wrapper for child tools
├── gui_state.py         # Grouped runtime/plot state dataclasses
├── tool_registry.py     # Hardware utility tool launcher
├── tool_adapters/       # Display, LED testing adapters
├── plot_panels.py       # Matplotlib widget construction
├── plot_updaters.py     # Background plot refresh threads
├── plot_handlers.py     # Batch analysis orchestration
├── analysis_handlers.py # Classification / analysis hooks
├── conditional_testing.py
├── custom_sweeps.py
└── messaging_handlers.py
```

## Tab registry

All tabs are registered in [`layout/tab_registry.py`](layout/tab_registry.py). To add a tab:

1. Create `layout/tab_your_feature.py` with `build_your_feature_tab(builder, notebook)`.
2. Append a `TabSpec` to `TAB_REGISTRY`.
3. No changes needed in `layout_builder._build_tabbed_content`.

## Callback contract

`MeasurementGUILayoutBuilder` receives a `callbacks` dict from `main.py`. Tab builders must use `builder.callbacks.get("name")` — never import `MeasurementGUI` methods directly.

| Callback | Owner |
|----------|-------|
| `connect_keithley`, `connect_psu`, `connect_temp` | `connection_controller` |
| `load_system`, `save_system`, `on_system_change` | `system_config_controller` |
| `measure_one_device`, sequential runners | `main.py` |
| Custom measurement thread | `custom_measurement_runner` |
| `open_motor_control`, `check_connection` | `main.py` |
| `open_pulse_testing`, `open_device_visualizer` | `main.py` → `child_gui_launchers` |
| Save path / custom folder | `save_path_controller` |
| SampleGUI notifications | `sample_gui_sync` |
| `open_oscilloscope_pulse`, `open_laser_fg_scope` | `main.py` |
| Plot/analysis actions | `plot_handlers.py` via thin `main` wrappers |

## Tool integration

**Child GUIs** (Motor Control, Pulse Testing, etc.) are registered in `child_gui_registry.DEFAULT_CHILD_GUIS`. Top-bar buttons are built from that registry; add a `ChildGuiSpec` and a matching entry in the layout `callbacks` dict.

**Hardware tools** (Display, LED testing) live in `tool_registry.DEFAULT_TOOLS`. The top bar **Hardware Tools** menu launches them in subprocesses. See [`GUI_EXTENSION_GUIDE.md`](../../Documents/guides/GUI_EXTENSION_GUIDE.md).

## State ownership

| State | Location |
|-------|----------|
| Instrument handles (`keithley`, `psu`, `itc`) | `MeasurementGUI` |
| Run flags (`measuring`, `abort`, `pause_requested`) | `runtime_state` via `@property` on `MeasurementGUI` |
| Plot buffers (`v_arr_disp`, `pulse_history`, etc.) | `plot_state` via `@property` on `MeasurementGUI` |
| Plot buffers | `plot_state` dataclass + `plot_panels` |
| Tk variables (sweep params) | Created by layout builders on `gui` |

## Cleanup

`cleanup()` stops plot threads, shuts down SMU, resets temperature, and closes optical connections. Registered via `atexit` and `WM_DELETE_WINDOW`.
