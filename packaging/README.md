# PyInstaller packaging

PyInstaller spec files and build scripts for the main application and Pulse Testing GUI.

> **Note:** PyInstaller output still lands in repo-root `dist/` and `build/` (gitignored). This folder only holds recipes and launchers.

## Main application

```powershell
python packaging/build_exe.py
```

- Spec: `packaging/build_exe.spec`
- Output: `dist/Switchbox_GUI/Switchbox_GUI.exe`

## Pulse Testing GUI

```powershell
python packaging/build_pulse_testing_gui.py           # classic
python packaging/build_pulse_testing_gui.py --compact
python packaging/build_pulse_testing_gui.py --all
```

- Specs: `build_pulse_testing_gui.spec`, `build_pulse_testing_gui_compact.spec`
- Outputs: `dist/Pulse_Testing_GUI/`, `dist/Pulse_Testing_GUI_Compact/`

## Standalone tool builds

Per-tool PyInstaller scripts stay with each tool:

- `tools/Display/build_exe.py`
- `tools/LED_testing/build_exe.py`
- `tools/camera_stream_standalone/build_exe.py`

## Documentation

- [Documents/build/BUILD_INSTRUCTIONS.md](../Documents/build/BUILD_INSTRUCTIONS.md)
- [Documents/build/BUILD_MODULES.md](../Documents/build/BUILD_MODULES.md)
