# Standalone tools

Optional utilities that live outside the main `main.py` application. Each tool has its own folder under `tools/` with a **snake_case** name (no spaces).

> **Legacy note:** Older copies with spaces in the name (e.g. `afm curve analysis`, `Impedence Analyzer`) were removed. Use the underscore paths listed below.

## Quick index

| Folder | Purpose | Run from repo root |
|--------|---------|-------------------|
| [`Display/`](Display/) | Arduino ST7789 TFT colour / flash control | `python tools/Display/main.py` |
| [`LED_testing/`](LED_testing/) | Arduino exclusive LED patterns | `python tools/LED_testing/main.py` |
| [`MASS_FLOW/`](MASS_FLOW/) | Mass flow controller GUI (Arduino) | `python tools/MASS_FLOW/main.py` |
| [`hp4140b_gui/`](hp4140b_gui/) | HP 4140B pA meter / SMU GUI | `python tools/hp4140b_gui/run_gui.py` |
| [`camera_stream_standalone/`](camera_stream_standalone/) | USB camera stream viewer | `python tools/camera_stream_standalone/camera_stream_app.py` |
| [`connection_check_standalone/`](connection_check_standalone/) | Connection check without main app | `python tools/connection_check_standalone/Connection_Check_Standalone.py` |
| [`tsp_testing_gui_standalone_v1/`](tsp_testing_gui_standalone_v1/) | Legacy Keithley 2450 TSP GUI | `python tools/tsp_testing_gui_standalone_v1/main.py` |
| [`data_analysis_pulse_2450/`](data_analysis_pulse_2450/) | TSP / pulse data analysis GUI | `python tools/data_analysis_pulse_2450/main.py` |
| [`classification_validation/`](classification_validation/) | Classifier weight tuning & validation | `python tools/classification_validation/launch_gui.py` |
| [`device_visualizer/`](device_visualizer/) | Qt device yield / IV gallery viewer | `python tools/device_visualizer/device_visualizer_app.py` |
| [`filament_jump_finder/`](filament_jump_finder/) | Detect large current jumps in IV data | `python -m tools.filament_jump_finder` |
| [`impedance_analyzer/`](impedance_analyzer/) | SMaRT impedance CSV / `.dat` plots | `python tools/impedance_analyzer/visualise_csv.py` |
| [`ito_analysis/`](ito_analysis/) | ITO sample comparison plots | `python tools/ito_analysis/ITO.py` |
| [`afm_3d_holes_protrusion/`](afm_3d_holes_protrusion/) | AFM hole / protrusion batch analysis | `python tools/afm_3d_holes_protrusion/main.py` |
| [`afm_curve_analysis/`](afm_curve_analysis/) | AFM line-profile comparison | `python tools/afm_curve_analysis/main.py` |
| [`maps_create/`](maps_create/) | Device map creator GUI and JSON checkers | `python tools/maps_create/device_map_tool.py` |
| [`equipment_address_location/`](equipment_address_location/) | List VISA / serial ports | `python tools/equipment_address_location/find_visa.py` |
| [`gordon_temperature/`](gordon_temperature/) | Gordon–Taylor blend Tg plot | `python tools/gordon_temperature/gordon_temp.py` |
| [`optical_timing_calibration/`](optical_timing_calibration/) | Optical pulse timing from saved data | `python tools/optical_timing_calibration/analyze_optical_result.py <file>` |
| [`fg_test/`](fg_test/) | SDG1032X FG config smoke test | `python tools/fg_test/test_fg_config.py` |
| [`Lines_of_code/`](Lines_of_code/) | Repo line-count report | `python tools/Lines_of_code/count_lines_of_code.py` |

## Integrated with Measurement GUI

These tools are registered in `gui/measurement_gui/tool_registry.py` and appear under **Hardware Tools** in the Measurement GUI top bar:

| Tool | Folder | Docs |
|------|--------|------|
| Display Control (ST7789) | `tools/Display/` | [README](Display/README.md) |
| LED Testing (Arduino) | `tools/LED_testing/` | [README](LED_testing/README.md) |

To add a new hardware tool, see [Documents/guides/GUI_EXTENSION_GUIDE.md](../Documents/guides/GUI_EXTENSION_GUIDE.md).

## Setup & lab utilities

| Tool | When to use | Detailed docs |
|------|-------------|---------------|
| **maps_create** | Create or verify device coordinate maps | [README](maps_create/README.md), [START_HERE](maps_create/START_HERE.md) |
| **equipment_address_location** | Find VISA / COM addresses for config | [README](equipment_address_location/README.md) |
| **gordon_temperature** | PMMA blend Tg plot | [README](gordon_temperature/README.md) |

## Analysis & visualisation

| Tool | When to use | Detailed docs |
|------|-------------|---------------|
| **data_analysis_pulse_2450** | Plot and statistics on Keithley 2450 TSP exports | [README](data_analysis_pulse_2450/README.md), [USAGE_GUIDE](data_analysis_pulse_2450/USAGE_GUIDE.md) |
| **classification_validation** | Tune classifier weights against labelled test files | [README](classification_validation/README.md), [QUICK_START](classification_validation/QUICK_START.md) |
| **device_visualizer** | Browse device folders, yield heatmaps, plot gallery | [README](device_visualizer/README.md) |
| **filament_jump_finder** | Find filament-forming jumps in IV sweeps | Run with `python -m tools.filament_jump_finder --sample <path>` |
| **impedance_analyzer** | Open/short corrected impedance plots | [README](impedance_analyzer/README.md) |
| **ito_analysis** | Compare ITO deposition batches | [README_ITO_ANALYSIS](ito_analysis/README_ITO_ANALYSIS.md) |
| **optical_timing_calibration** | Derive timing from optical readout files | [README](optical_timing_calibration/README.md) |

## AFM processing

Both tools read Igor Binary Wave (`.ibw`) height maps. Raw data and generated outputs are **gitignored** — place `.ibw` files in each tool's `Data/` folder locally.

| Tool | Focus |
|------|-------|
| **afm_3d_holes_protrusion** | 3D blob detection, hole/protrusion metrics, batch comparison |
| **afm_curve_analysis** | 1D line-profile extraction and comparison |

See [afm_3d_holes_protrusion/README.md](afm_3d_holes_protrusion/README.md) and [afm_curve_analysis/README.md](afm_curve_analysis/README.md).

## Standalone lab GUIs

| Tool | Hardware |
|------|----------|
| **MASS_FLOW** | Arduino + mass flow controller |
| **hp4140b_gui** | HP 4140B |
| **camera_stream_standalone** | USB camera (PyInstaller build supported) |
| **connection_check_standalone** | Multiplexer / SMU wiring check |
| **tsp_testing_gui_standalone_v1** | Keithley 2450 TSP (self-contained copy of drivers) |

## Packaging (PyInstaller)

Display, LED Testing, and Camera Stream support one-file exe builds:

```powershell
python tools/Display/build_exe.py
python tools/LED_testing/build_exe.py
python tools/camera_stream_standalone/build_exe.py
```

Build artefacts land in each tool's `dist/` folder (gitignored). See [Documents/build/BUILD_MODULES.md](../Documents/build/BUILD_MODULES.md) for what is bundled in the main app exe vs standalone tools.

## Developer utilities

| Tool | Purpose |
|------|---------|
| **fg_test** | Verify Siglent SDG1032X accepts Laser FG Scope settings |
| **Lines_of_code** | Generate `lines_of_code_report.txt` for the repo |

## Folder conventions

- **Name:** `snake_case` only (e.g. `impedance_analyzer`, not `Impedence Analyzer`).
- **Entry point:** Prefer `main.py` or a clearly named launcher (`run_gui.py`, `launch_gui.py`).
- **Data / output:** Use local `Data/` and `Output/` subfolders; add patterns to root `.gitignore` if outputs are large or machine-specific.
- **Legacy copies:** Do not add new code under `Helpers/` — see [Helpers/README.md](../Helpers/README.md) and [PATH_MIGRATION.md](../Documents/development/PATH_MIGRATION.md).

## Related documentation

- [Documents/README.md](../Documents/README.md) — full documentation index
- [Documents/guides/GUI_EXTENSION_GUIDE.md](../Documents/guides/GUI_EXTENSION_GUIDE.md) — register tools in Measurement GUI
- [Documents/guides/DEPLOYMENT_GUI.md](../Documents/guides/DEPLOYMENT_GUI.md) — release checklist
- [CONTRIBUTING.md](../CONTRIBUTING.md) — repo layout rules
