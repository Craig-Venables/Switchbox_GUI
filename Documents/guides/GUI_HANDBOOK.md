# GUI Handbook

Handover guide for the Switchbox Tkinter front end.

## Quick start

```powershell
python main.py                    # Sample GUI → Measurement GUI
python -m gui.smoke_test          # Import / registry checks
python -m pytest tests/test_sample_gui_quick_scan.py -q
```

## Where things live

| You want to… | Start here |
|--------------|------------|
| Change device map / sample types | `gui/sample_gui/config.py`, `Json_Files/mapping.json` |
| Change device selection UI | `gui/sample_gui/ui/` |
| Change measurement tabs | `gui/measurement_gui/layout/tab_registry.py` |
| Change sweep / connection UI | `gui/measurement_gui/layout/sections/` |
| Change measurement algorithms | `Measurements/measurement_services_smu.py` |
| Change instrument drivers | `Equipment/managers/` |
| SMU adapter for child tools | `gui/measurement_gui/smu_adapter.py` |
| Connect / auto-connect SMU | `gui/measurement_gui/connection_controller.py` |
| System config load/save | `gui/measurement_gui/system_config_controller.py` |
| Custom measurement plan | `gui/measurement_gui/custom_measurement_runner.py` |
| Add a top-bar child GUI button | `gui/measurement_gui/child_gui_registry.py` + `child_gui_launchers.py` |
| Add a subprocess hardware tool | `gui/measurement_gui/tool_registry.py` |
| Change save paths / custom folder | `gui/measurement_gui/save_path_controller.py` |
| Sync Sample → Measurement state | `gui/measurement_gui/sample_gui_sync.py` |

## Module map (refactored layout)

### Sample GUI controllers (`gui/sample_gui/`)

| Module | Responsibility |
|--------|----------------|
| `status_store.py` | Device status + quick-scan file persistence |
| `selection_controller.py` | Checkboxes, canvas highlights |
| `routing_controller.py` | Multiplexer init and relay routing |
| `quick_scan_controller.py` | Quick scan worker, overlays, save/load |
| `device_status_controller.py` | Manual/auto status menus, export |
| `device_manager_controller.py` | Device naming, load/save, tree list |
| `telegram_controller.py` | Telegram bots, scan notifications |
| `terminal_log_controller.py` | Terminal panel log, filter, export |
| `main.py` | Window lifecycle, UI wiring, thin delegates |
| `ui/` | Tab/panel builders (no hardware) |

### Measurement GUI modules (`gui/measurement_gui/`)

| Module | Responsibility |
|--------|----------------|
| `layout/tab_registry.py` | Tab order (8 tabs) |
| `layout/help_dialog.py` | Help / Guide window |
| `child_gui_registry.py` | Top-bar button specs |
| `child_gui_launchers.py` | `open_*` implementations |
| `tool_registry.py` | Subprocess tools (Display, LED) |
| `gui_state.py` | `runtime_state` + `plot_state` dataclasses |
| `save_path_controller.py` | Data folder paths, custom save config |
| `sample_gui_sync.py` | SampleGUI change notifications, plot overlay |
| `connection_controller.py` | SMU/PSU/temp connect and auto-connect |
| `system_config_controller.py` | system_configs.json, optical setup fields |
| `lifecycle_controller.py` | atexit instrument shutdown |
| `custom_measurement_runner.py` | Custom sweep plan thread body |
| `smu_adapter.py` | IV controller wrapper for child tools |
| `main.py` | Orchestrator: connections, measurement threads, callbacks |

## Application flow

```
main.py → SampleGUI → MeasurementGUI → (optional child tools / subprocess tools)
```

## First hour for a new developer

1. Read [`GUI_REFACTOR_BASELINE.md`](GUI_REFACTOR_BASELINE.md) — expected behaviour.
2. Run `python main.py` and open Measurement GUI with Manual + Generic_Grid (no hardware).
3. Skim [`gui/sample_gui/ARCHITECTURE.md`](../../gui/sample_gui/ARCHITECTURE.md).
4. Skim [`gui/measurement_gui/ARCHITECTURE.md`](../../gui/measurement_gui/ARCHITECTURE.md).
5. Pick one tab in `layout/tab_*.py` and trace its callbacks to `main.py` or a controller.

## Design rules

- **Tab builders are UI-only** — no VISA, serial, or SMU calls inside `layout/`.
- **Controllers own domain logic** in Sample GUI; `main.py` delegates.
- **Child GUIs** register in `child_gui_registry`; launch logic in `child_gui_launchers`.
- **Subprocess tools** use `GuiToolRegistry` — do not hard-code paths in layout code.
- **State flags** use `runtime_state` / `plot_state` via properties on `MeasurementGUI`.
- **Legacy code** under `archive/` is read-only reference — edit `gui/` package only.

## Related docs

- [GUI_EXTENSION_GUIDE.md](GUI_EXTENSION_GUIDE.md) — add tabs, tools, controllers
- [DEPLOYMENT_GUI.md](DEPLOYMENT_GUI.md) — setup and release checklist
- [GUI_REFACTOR_BASELINE.md](GUI_REFACTOR_BASELINE.md) — regression checklist
- [MEASUREMENT_AND_SAMPLE_GUI_REFERENCE.md](../reference/MEASUREMENT_AND_SAMPLE_GUI_REFERENCE.md) — detailed reference
