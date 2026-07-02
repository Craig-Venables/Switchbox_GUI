# GUI Deployment Guide

Release and handover checklist for the Switchbox GUI.

## Prerequisites

- Python 3.10+ (3.11 recommended)
- Virtual environment with `pip install -r requirements.txt`
- See root [SETUP.md](../../SETUP.md) for full machine setup

## Run commands

| Command | Purpose |
|---------|---------|
| `python main.py` | Main application |
| `python -m gui.smoke_test` | Import / registry smoke test |
| `python -m pytest tests/ -q` | Automated tests |
| `python tools/Display/main.py` | Standalone display tool |
| `python tools/LED_testing/main.py` | Standalone LED tool |

## Pre-handover validation

### Automated

```powershell
.\.venv\Scripts\Activate.ps1
python -m gui.smoke_test
python -m pytest tests/test_sample_gui_quick_scan.py tests/test_plot_updaters.py -q
```

### Manual (no instruments)

- [ ] Sample GUI opens; three tabs visible
- [ ] Generic_Grid + Manual multiplexer loads placeholder map
- [ ] Measurement GUI opens from selected devices
- [ ] All 8 measurement tabs render
- [ ] Hardware Tools menu lists Display + LED Testing
- [ ] Windows close without hang

### Manual (with instruments)

- [ ] System config loads from `Json_Files/system_configs.json`
- [ ] SMU connects from Setup tab
- [ ] Single IV sweep runs and saves data
- [ ] Plot threads stop on window close

## Configuration files

| File | Purpose |
|------|---------|
| `Json_Files/system_configs.json` | Instrument addresses per bench |
| `Json_Files/Custom_Sweeps.json` | Custom measurement definitions |
| `Json_Files/mapping.json` | Device layout coordinates |
| `Json_Files/pin_mapping.json` | Multiplexer pin map |

| `Json_Files/save_location_config.json` | Custom save path preference (written by GUI) |
| `Json_Files/help_videos.json` | Help window video tutorial list |

## Documentation index

| Doc | Purpose |
|-----|---------|
| `Documents/guides/GUI_HANDBOOK.md` | Module map and design rules |
| `Documents/guides/GUI_EXTENSION_GUIDE.md` | How to add tabs, tools, controllers |
| `Documents/guides/GUI_REFACTOR_BASELINE.md` | Regression checklist |
| `tools/README.md` | Standalone tools index (run commands, categories) |
| `gui/sample_gui/ARCHITECTURE.md` | Sample GUI module layout |
| `gui/measurement_gui/ARCHITECTURE.md` | Measurement GUI module layout |

## Packaging standalone tools

Display and LED tools support PyInstaller builds:

```powershell
python tools/Display/build_exe.py
python tools/LED_testing/build_exe.py
```

## Support contacts / notes

Document bench-specific system names and COM ports in `Json_Files/system_configs.json` before handover. Keep Telegram tokens out of git — use `gui/messaging_config` / environment variables.

## Release readiness sign-off

| Item | Status |
|------|--------|
| Smoke test passes | |
| Core pytest suite passes | |
| GUI_HANDBOOK.md + ARCHITECTURE.md reviewed | |
| system_configs.json updated for target bench | |
| No uncommitted secrets in repo | |
