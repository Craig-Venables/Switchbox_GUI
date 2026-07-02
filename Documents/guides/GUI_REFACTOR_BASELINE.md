# GUI Refactor Baseline

Snapshot of expected behavior before and after cleanup. Use this as the regression checklist.

## Application Flow

```
main.py
  └─ SampleGUI (gui/sample_gui/)
        └─ MeasurementGUI (gui/measurement_gui/)  [Toplevel]
              ├─ Tabbed notebook (8 tabs)
              ├─ MeasurementService + InstrumentConnectionManager
              └─ Child tools (pulse testing, connection check, motor, etc.)
```

## Sample GUI — Expected Behavior

| Area | Expected behavior |
|------|-------------------|
| Startup | Window title "Device Selection & Quick Scan", geometry 1100x850 |
| Tabs (order) | Device Selection → Device Manager → Quick Scan Results |
| Multiplexer | Manual / Pyswitchbox / Electronic_Mpx; status label updates |
| Device map | Click selects device; Ctrl+click toggles checkbox selection |
| Selection | Checkboxes sync with map highlights; status bar shows count |
| Open measurement | Requires device name + selection (dialogs if missing); launches `MeasurementGUI` |
| Quick scan | Requires multiplexer; colors map by current; saves JSON/CSV |
| Device status | Manual working/broken/undefined; persists to JSON + Excel |
| Child GUIs | `register_child_gui` / `unregister_child_gui` propagate changes |

## Measurement GUI — Tab Order

| # | Tab | Purpose |
|---|-----|---------|
| 1 | Measurements | Main controls + live IV plots |
| 2 | Advanced Tests | Endurance, retention, forming, optical |
| 3 | Setup | Instrument connections, system config |
| 4 | Custom Measurements | JSON-defined measurement editor |
| 5 | Notes | Run notes and metadata |
| 6 | Stats | Device tracking statistics |
| 7 | Graphing | Sample analysis and batch plots |
| 8 | Custom Sweeps | Sweep combination graphing |

## Measurement GUI — Top Bar Actions

| Button | Action |
|--------|--------|
| System dropdown | Load system config, auto-connect instruments |
| Motor Control | Open motor control window |
| Check Connection | Open connection check GUI |
| Pulse Testing | Open TSP testing GUI |
| Device Visualizer | Launch Qt visualizer |
| Oscilloscope Pulse | Open oscilloscope pulse GUI |
| Laser FG Scope | Open laser FG scope GUI |
| Hardware Tools | Open registered utility tools (Display, LED testing) |
| Help / Guide | In-app help window |

## Coding Guardrails

1. **Tab builders** (`layout/tab_*.py`, `layout/sections/*.py`) must not call hardware directly.
2. **Hardware access** goes through `MeasurementService`, `InstrumentConnectionManager`, or equipment managers.
3. **New features** register via callbacks dict, `child_gui_registry`, or `GuiToolRegistry` — not ad-hoc imports in tab code.
4. **Sample GUI controllers** own domain logic; `main.py` wires UI events to controllers.
5. **Measurement helpers** (`save_path_controller`, `sample_gui_sync`, `child_gui_launchers`) keep `main.py` thin.

## Module inventory (post-refactor)

### Sample GUI controllers

`status_store`, `selection_controller`, `routing_controller`, `quick_scan_controller`, `device_status_controller`, `device_manager_controller`, `telegram_controller`, `terminal_log_controller`

### Measurement GUI helpers

`child_gui_registry`, `child_gui_launchers`, `tool_registry`, `gui_state`, `save_path_controller`, `sample_gui_sync`, `connection_controller`, `system_config_controller`, `lifecycle_controller`, `custom_measurement_runner`, `smu_adapter`, `layout/help_dialog`

## Smoke Test Checklist

### Automated (no hardware)

```powershell
python -m pytest tests/test_sample_gui_quick_scan.py tests/test_plot_updaters.py -q
python -m gui.smoke_test
```

### Manual — Sample GUI

- [ ] `python main.py` opens without traceback
- [ ] All three tabs render
- [ ] Sample type dropdown loads device map
- [ ] Device click updates current device label
- [ ] Select/deselect all updates checkbox state
- [ ] Terminal log receives messages

### Manual — Measurement GUI

- [ ] Open from Sample GUI with at least one device selected
- [ ] All 8 tabs render without error
- [ ] System dropdown populates from `Json_Files/system_configs.json`
- [ ] Setup tab shows connection section
- [ ] Measurements tab shows plots (empty axes OK)
- [ ] Close window cleans up without hang

### Manual — Standalone Tools

- [ ] `python tools/Display/main.py` opens
- [ ] `python tools/LED_testing/main.py` opens

### Regression — Data Compatibility

- [ ] `Json_Files/Custom_Sweeps.json` loads in Custom Measurements tab
- [ ] `Json_Files/system_configs.json` loads on system change
- [ ] Quick scan JSON/CSV round-trip (see `tests/test_sample_gui_quick_scan.py`)
