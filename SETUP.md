# Setup Guide

Step-by-step instructions for installing Switchbox_GUI on a new Windows PC (also works on Linux/macOS with minor path differences).

## Requirements

| Item | Recommendation |
|------|----------------|
| **Python** | 3.10 or 3.11 (64-bit) |
| **OS** | Windows 10/11 (primary target); Linux/macOS supported for dev |
| **Hardware** | VISA-compatible instruments as needed for your bench setup |
| **Optional** | NI-VISA or Keysight VISA for GPIB/USB instruments |
| **Optional** | Telegram bot token for remote notifications |

## 1. Clone the repository

```bash
git clone <repository-url>
cd Switchbox_GUI
```

## 2. Create a virtual environment

**Windows (PowerShell):**

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

**Linux / macOS:**

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

For development and running tests:

```bash
pip install -r requirements-dev.txt
```

## 4. Verify the install

```bash
python -m pytest tests -q
python main.py
```

The Sample GUI should open. If instruments are not connected, the app still launches — use **Connection Check** from the menu when hardware is available.

## 5. Configuration

### Instrument and sweep settings

Edit JSON files under `Json_Files/`:

| File | Purpose |
|------|---------|
| `system_configs.json` | Bench/instrument presets |
| `mapping.json` | Device pin mappings |
| `Custom_Sweeps.json` | Saved sweep definitions |
| `test_configurations.json` | Automated test configs |

See [Documents/guides/JSON_CONFIG_GUIDE.md](Documents/guides/JSON_CONFIG_GUIDE.md) for details.

### Telegram notifications (optional)

1. Copy the example file:
   ```bash
   copy Json_Files\messaging_data.json.example Json_Files\messaging_data.local.json
   ```
2. Add your bot token and chat ID to `messaging_data.local.json` (this file is gitignored).
3. See [Json_Files/MESSAGING_README.md](Json_Files/MESSAGING_README.md).

### Data save location

Measurement data is saved under a configurable path (default behaviour is documented in the User Guide). The `/Data_save_loc` folder is gitignored for local overrides.

## 6. Optional external tools

These are **not** bundled in git — install or build separately if you need them:

| Tool | How to get it |
|------|----------------|
| **Moku CLI** | Install from [Liquid Instruments](https://liquidinstruments.com/) — do not commit `Equipment/Moku/Moku CLI/` to git |
| **Camera stream standalone** | Build with PyInstaller from `tools/camera_stream_standalone/` or run from source |
| **NI-DAQmx** | National Instruments driver if using NI hardware (`nidaqmx` Python package) |

## 7. Building a standalone executable (optional)

See [Documents/build/BUILD_INSTRUCTIONS.md](Documents/build/BUILD_INSTRUCTIONS.md):

```bash
pip install pyinstaller
python build_exe.py
```

Output: `dist/Switchbox_GUI/Switchbox_GUI.exe`

## 8. Standalone tool launchers

| Tool | Command |
|------|---------|
| Main app | `python main.py` |
| Laser FG Scope | `python Laser_FG_Scope_GUI.py` |
| Pulse testing GUI | `python -m gui.pulse_testing_gui.main` |
| Motor control | `python -m gui.motor_control_gui.main` |
| Connection check | `python -m gui.connection_check_gui.main` |
| TSP standalone (legacy) | `python tools/tsp_testing_gui_standalone_v1/TSP_Testing_GUI.py` |

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError` | Activate `.venv` and re-run `pip install -r requirements.txt` |
| VISA resource not found | Check NI-VISA installation and instrument USB/GPIB connection |
| Telegram not sending | Verify `messaging_data.local.json` exists and token is valid |
| Import errors after pull | Reinstall deps; check [CONTRIBUTING.md](CONTRIBUTING.md) for package layout |

## Next steps

- **Operators:** [Documents/guides/USER_GUIDE.md](Documents/guides/USER_GUIDE.md)
- **Developers:** [CONTRIBUTING.md](CONTRIBUTING.md) and [Documents/README.md](Documents/README.md)
- **Architecture:** [Documents/reference/MEASUREMENT_AND_SAMPLE_GUI_REFERENCE.md](Documents/reference/MEASUREMENT_AND_SAMPLE_GUI_REFERENCE.md)
