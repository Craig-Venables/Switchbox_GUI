# GUI Extension Guide

How to add features without breaking the modular layout.

## Add a Measurement GUI tab

1. **Create builder** — `gui/measurement_gui/layout/tab_my_feature.py`:

```python
def build_my_feature_tab(builder, notebook):
    tab = tk.Frame(notebook, bg=COLOR_BG)
    notebook.add(tab, text="  My Feature  ")
    # ... widgets only; use builder.callbacks.get("my_action")
```

2. **Register tab** — append to `TAB_REGISTRY` in `layout/tab_registry.py`:

```python
TabSpec("my_feature", "  My Feature  ", build_my_feature_tab),
```

3. **Add callback** — in `MeasurementGUI.__init__`, extend the `callbacks` dict passed to `MeasurementGUILayoutBuilder`.

4. **Implement handler** — prefer a dedicated module (e.g. `my_feature_handlers.py`) with functions taking `gui` as first argument.

## Add a hardware utility tool

Example: integrate a new Arduino tool.

1. **Standalone tool** — ensure `tools/MyTool/main.py` runs independently.

2. **Register adapter** — in `gui/measurement_gui/tool_registry.py`:

```python
SubprocessTool(
    tool_id="my_tool",
    label="My Tool",
    description="Short description",
    module_path="tools/MyTool/main.py",
    cwd=_PROJECT_ROOT / "tools" / "MyTool",
)
```

3. Tool appears automatically under **Hardware Tools** in the Measurement GUI top bar.

4. Optional programmatic launch:

```python
self.tool_registry.launch("my_tool", self.master)
```

## Add a child GUI launcher (top bar)

For in-process windows (Pulse Testing, Motor Control, etc.):

1. Implement `open_my_gui()` on `MeasurementGUI` (or reuse an existing method).
2. Append to `DEFAULT_CHILD_GUIS` in `gui/measurement_gui/child_gui_registry.py`:

```python
ChildGuiSpec("my_gui", "My GUI", "open_my_gui", "default"),
```

3. Add `"open_my_gui": self.open_my_gui` to the layout `callbacks` dict in `main.py`.

The button appears automatically in the top bar (no `layout_builder` edits).

## Add Sample GUI behaviour

1. Add logic to the appropriate controller:

   | Area | Controller |
   |------|------------|
   | Selection / canvas | `selection_controller` |
   | Multiplexer | `routing_controller` |
   | Quick scan | `quick_scan_controller` |
   | Status persistence | `status_store` |
   | Device status UI | `device_status_controller` |
   | Device naming / load | `device_manager_controller` |
   | Telegram | `telegram_controller` |
   | Terminal log | `terminal_log_controller` |

2. Expose a one-line delegate method on `SampleGUI` if UI callbacks need it.
3. Add UI in `gui/sample_gui/ui/` — keep `main.py` thin.

## Add Measurement GUI behaviour (non-tab)

Prefer a dedicated module with functions or a small controller class taking `gui` as first argument:

| Area | Module |
|------|--------|
| Save paths | `save_path_controller.py` |
| SampleGUI sync / overlay | `sample_gui_sync.py` |
| Instrument connect | `connection_controller.py` |
| System config load/save | `system_config_controller.py` |
| Shutdown / cleanup | `lifecycle_controller.py` |
| Custom measurement plan | `custom_measurement_runner.py` |
| SMU adapter | `smu_adapter.py` |
| Child GUI launch | `child_gui_launchers.py` |
| New top-bar button | `child_gui_registry.py` + callback in `main.py` |

## Add a measurement mode

1. Extend `Measurements/` service layer first.
2. Wire a button in the relevant tab section (`layout/sections/`).
3. Add callback in `main.py` that calls the service — not the reverse.

## Testing checklist

- [ ] `python -m gui.smoke_test`
- [ ] New tab renders without traceback
- [ ] Callback fires (log or messagebox)
- [ ] Standalone tool still runs: `python tools/MyTool/main.py`
- [ ] No new imports from `archive/`
