# Switchbox Measurement System

Switchbox_GUI is an ongoing Python project for internal lab use. It automates electrical testing of thin-film devices so measurement is faster and more repeatable.

One interface coordinates source-measure units, a 100-device relay switch matrix, lasers, motorised stages, oscilloscopes, and temperature controllers. It then turns raw measurements into classified results and graphs for quick analysis. The design is shaped by first-hand work fabricating and measuring the devices it tests.

## Quick Start

**New machine?** Follow [SETUP.md](SETUP.md) (Python 3.10+, virtual environment, dependencies, config).

```bash
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

The application opens the Sample GUI. Select a device there, then launch the measurement interface.

## Read this first

```
main.py
  → gui/sample_gui/         device map and sample selection
  → gui/measurement_gui/    measurement interface
  → Equipment/managers/     instrument drivers behind one API
  → Measurements/           sweeps, pulses, and saving
  → analysis/               classification of results
  → plotting/               graphs
```

On a first look, skip `archive/` and any folder marked UNUSED, Ignore, or work-in-progress. Those are historical or unfinished experiments.

Optical pulse experiments (Laser + function generator + oscilloscope) are written and waiting on bench validation. Detail is in the [system overview](Documents/reference/SYSTEM_OVERVIEW.md).

## What lives where

| Path | Role |
|------|------|
| `main.py` | Application entry point |
| `gui/` | Tkinter interfaces |
| `Equipment/` | Instrument drivers and managers |
| `Measurements/` | Measurement logic |
| `analysis/` | IV classification |
| `plotting/` | Graphs |
| `Pulse_Testing/` | Multi-instrument pulse routing |
| `Json_Files/` | Runtime configuration |
| `Notifications/` | Telegram messaging |
| `tools/` | Separate utilities (see below) |
| `archive/` | Historical code |

New measurement code belongs in `Measurements/`. The `Measurments/` folder is a spelling shim that re-exports that package. `Helpers/` is an empty redirect.

Root scripts `Laser_FG_Scope_GUI.py`, `TSP_Testing_GUI.py`, and `Pulse_Testing_GUI_compact.py` open individual interfaces without the sample selector.

## Standalone tools

Everything under [`tools/`](tools/) is separate from the main application. Each tool is written so it could live in its own repository. They stay in this repo so they are easy to run next to the lab software.

Index and run commands: [tools/README.md](tools/README.md).

## Further reading

- [System overview](Documents/reference/SYSTEM_OVERVIEW.md) — instruments, measurement types, and GUI detail
- [Documentation index](Documents/README.md)
- [User guide](Documents/guides/USER_GUIDE.md)
- [Layout and conventions](CONTRIBUTING.md)
- [IV classification](docs/classification/README.md)

## License

MIT — see [LICENSE](LICENSE).
