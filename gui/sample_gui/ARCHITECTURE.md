# Sample GUI — Architecture

## Role

`SampleGUI` is the application entry window: device map, selection, multiplexer routing, quick scan, and launching `MeasurementGUI`.

## Module layout

```
gui/sample_gui/
├── main.py                  # Orchestrator: window lifecycle, UI wiring, thin delegates
├── config.py                # Sample maps, pin mapping, save-root resolution
├── status_store.py          # Device status + quick-scan path persistence
├── selection_controller.py  # Checkbox selection, canvas highlights
├── routing_controller.py    # Multiplexer init and relay routing
├── quick_scan_controller.py # Quick scan worker, overlays, save/load
├── device_manager_controller.py  # Device naming, load/save, tree list
├── device_status_controller.py  # Manual/auto status menus and export
├── telegram_controller.py       # Bot setup and scan notifications
├── terminal_log_controller.py   # Terminal panel log, filter, export
└── ui/                      # Tab and panel builders (no hardware calls)
```

## Tabs

| Tab | Builder | State owner |
|-----|---------|-------------|
| Device Selection | `ui/device_map.py`, `device_selection.py` | `SelectionController` + `main` |
| Device Manager | `ui/device_manager.py` | `DeviceManagerController` |
| Quick Scan Results | `ui/quick_scan.py` | `QuickScanController` |
| Terminal log | `ui/terminal_log.py` | `TerminalLogController` |

## Adding a feature

1. Put domain logic in a controller or `status_store.py`.
2. Add UI in `ui/` if needed.
3. Wire one callback in `main.py` — avoid growing `main.py` with business logic.

## Child GUI propagation

`register_child_gui` / `_notify_child_guis` push sample/section/device changes to open `MeasurementGUI` instances.
