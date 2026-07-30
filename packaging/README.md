# PyInstaller packaging

PyInstaller spec files and build scripts for the main application, Pulse Testing GUI, and **v6 full release**.

> **Note:** PyInstaller output still lands in repo-root `dist/` and `build/` (gitignored). This folder only holds recipes and launchers.

## v6 full release (recommended)

```powershell
python packaging/build_release_v6.py          # check env + plan
python packaging/build_release_v6.py --build  # all exes + dist/Switchbox_GUI_v6/
```

See **[BUILD_RELEASE_V6.md](BUILD_RELEASE_V6.md)** for the complete target list, folder layout, and handover checklist.

## Main application only

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
- `tools/data_analysis_pulse_2450/build_exe.py`

Console script runner (for bundled `.py` tools in frozen main app):

- `packaging/build_script_runner.spec` — built automatically by `build_release_v6.py`

## Documentation

- **[BUILD_RELEASE_V6.md](BUILD_RELEASE_V6.md)** — **v6 full release** (all exes + assembly)
- [Documents/build/BUILD_INSTRUCTIONS.md](../Documents/build/BUILD_INSTRUCTIONS.md)
- [Documents/build/BUILD_MODULES.md](../Documents/build/BUILD_MODULES.md)
