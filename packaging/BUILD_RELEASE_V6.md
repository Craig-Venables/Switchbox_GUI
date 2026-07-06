# Switchbox_GUI v6 release build

Full Windows release package: main app, companion tool exes, Pulse Testing GUIs, and optional vendor bundles.

## Quick commands

From the **repository root** with an activated venv (Python **3.10.11+** or **3.11+**):

```powershell
# 1. Install build dependencies (once per venv)
pip install -r requirements.txt pyinstaller

# 2. Validate environment and print the build plan (does NOT run PyInstaller)
python packaging/build_release_v6.py

# 3. When ready — build everything and assemble dist/Switchbox_GUI_v6/
python packaging/build_release_v6.py --build

# Optional: skip camera stream / TSP analysis if their extra deps are not installed
python packaging/build_release_v6.py --build --skip-optional

# Re-assemble only (after manual partial builds)
python packaging/build_release_v6.py --assemble-only
```

**Do not distribute only the `.exe` files** — ship the entire `dist/Switchbox_GUI_v6/` folder (onedir layouts include `_internal`).

## What gets built

| Target | Output | Role |
|--------|--------|------|
| Main app | `dist/Switchbox_GUI/` | Sample + Measurement GUIs, analysis, plotting |
| Script runner | `dist/Switchbox_ScriptRunner.exe` | Runs bundled `.py` tools (impedance, laser calibration plot) |
| Display tool | `tools/Display/dist/DisplayControl.exe` | Hardware Tools → Display Control |
| LED tool | `tools/LED_testing/dist/LEDTesting.exe` | Hardware Tools → LED Testing |
| Camera stream | `tools/camera_stream_standalone/dist/CameraStream.exe` | Optional USB camera viewer |
| TSP data analysis | `tools/data_analysis_pulse_2450/dist/TSP_Data_Analysis.exe` | Optional PyQt6 analysis (Pulse GUI button) |
| Pulse classic | `dist/Pulse_Testing_GUI/` | Standalone pulse testing (classic layout) |
| Pulse compact | `dist/Pulse_Testing_GUI_Compact/` | Standalone pulse testing (compact layout) |

## Assembled layout (`dist/Switchbox_GUI_v6/`)

```
Switchbox_GUI_v6/
  README_RELEASE.txt
  Switchbox_GUI/
    Switchbox_GUI.exe
    _internal/...
    Json_Files/
    Documents/
    tools_bin/
      Switchbox_ScriptRunner.exe
      DisplayControl.exe
      LEDTesting.exe
      CameraStream.exe          (if built)
      TSP_Data_Analysis.exe     (if built)
  Pulse_Testing_GUI/
  Pulse_Testing_GUI_Compact/
  Equipment/Moku/Moku CLI/      (if present locally at build time)
```

## Prerequisites

1. **Python 3.10.11+ or 3.11+** (3.10.0 breaks PyInstaller analysis).
2. `pip install -r requirements.txt pyinstaller`
3. Optional extras:
   - **TSP Data Analysis:** `pip install -r tools/data_analysis_pulse_2450/requirements.txt`
   - **Moku CLI:** install under `Equipment/Moku/Moku CLI/` before build (not in git — see `SETUP.md`)
4. Recommended: dedicated build venv (`.venv-build`) so site-packages stay minimal.

## Main spec changes (v6)

`packaging/build_exe.spec` now:

- Registers all `analysis.*` and `plotting.*` modules (lazy classification / plots).
- Bundles tool script trees used by `gui/frozen_launch.py`.
- Adds hardware / notification hidden imports (`pyvisa`, `telegram`, `cv2`, `nidaqmx`, …).
- Copies **Moku CLI** into the bundle when `Equipment/Moku/Moku CLI/` exists locally.

Frozen subprocess launches use `gui/frozen_launch.py` (standalone exes in `tools_bin/` or `Switchbox_ScriptRunner.exe`).

## Handover checklist

- [ ] `python packaging/build_release_v6.py` shows no blocking environment warnings
- [ ] `python packaging/build_release_v6.py --build` completes
- [ ] Run `Switchbox_GUI_v6/Switchbox_GUI/Switchbox_GUI.exe` on build PC
- [ ] Copy whole `Switchbox_GUI_v6/` to a PC **without** Python and repeat
- [ ] Hardware Tools → Display + LED open their bundled exes
- [ ] Impedance visualisation opens (script runner)
- [ ] Pulse Testing standalone exes launch
- [ ] Zip `Switchbox_GUI_v6/` for distribution

## Related docs

- [BUILD_INSTRUCTIONS.md](../Documents/build/BUILD_INSTRUCTIONS.md) — main app only
- [BUILD_MODULES.md](../Documents/build/BUILD_MODULES.md) — module inventory
- [packaging/README.md](README.md) — individual build scripts
