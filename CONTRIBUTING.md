# Contributing & Handoff Guide

This document is for anyone taking over maintenance of the Switchbox Measurement System.

## Repository layout (canonical paths)

| Path | Role |
|------|------|
| `main.py` | Application entry point → Sample GUI |
| `gui/` | All Tkinter user interfaces |
| `Equipment/managers/` | Unified hardware abstraction layer |
| `Measurements/` | **Canonical** measurement logic (runners, data saving, sweeps) |
| `Measurments/` | **Deprecated shim** — re-exports `Measurements`; do not edit |
| `analysis/` | IV sweep analysis and classification |
| `plotting/` | Plotting utilities |
| `Pulse_Testing/` | Multi-instrument pulse routing |
| `Json_Files/` | Runtime configuration |
| `tools/` | Standalone utilities (canonical location for optional tools) |
| `packaging/` | PyInstaller specs and build scripts (`build_exe.py`, Pulse Testing GUI builds) |
| `Helpers/` | **Deprecated redirect** — see [Helpers/README.md](Helpers/README.md); all code moved to `tools/`, `analysis/`, or `plotting/` |
| `archive/` | Old code kept for reference only — not used by the main app |
| `tests/` | Pytest suite |
| `Documents/` | Operator and developer documentation |

## Getting started as a maintainer

1. Follow [SETUP.md](SETUP.md) on a clean machine.
2. Read [Documents/README.md](Documents/README.md) for the doc index.
3. Read [Documents/reference/MEASUREMENT_AND_SAMPLE_GUI_REFERENCE.md](Documents/reference/MEASUREMENT_AND_SAMPLE_GUI_REFERENCE.md) for app flow.
4. Check [TODO.md](TODO.md) and [Documents/development/REFACTOR_REMAINING.md](Documents/development/REFACTOR_REMAINING.md) for known work.

## Running tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests
```

Before lab releases, also use [Documents/guides/LAB_TEST_CHECKLIST.md](Documents/guides/LAB_TEST_CHECKLIST.md).

## Code conventions

- Match existing style in the file you edit (naming, imports, docstrings).
- **Do not** add new code under `Measurments/` or `Helpers/` — use `Measurements/`, `analysis/`, `plotting/`, or `tools/`.
- Keep instrument drivers in `Equipment/`; keep GUI code in `gui/`.
- JSON-driven behaviour belongs in `Json_Files/` with documentation updates in `Documents/guides/`.
- Avoid committing generated outputs (plots, CSVs, `.ibw`, `.exe`) — see `.gitignore`.

## Adding a new instrument

1. Add low-level driver under `Equipment/<category>/`.
2. Add or extend a manager in `Equipment/managers/`.
3. Wire into measurement services in `Measurements/` if needed.
4. Update `Json_Files/system_configs.json` and document in the relevant GUI README.

## Building a release executable

See [Documents/build/BUILD_INSTRUCTIONS.md](Documents/build/BUILD_INSTRUCTIONS.md) and keep [Documents/build/BUILD_MODULES.md](Documents/build/BUILD_MODULES.md) in sync with `packaging/build_exe.spec`.

## What not to touch without good reason

- `archive/` — historical reference only
- `Equipment/SMU_AND_PMU/4200A/C_Code_with_python_scripts/` — lab-validated C modules
- Large GUI files (`gui/measurement_gui/main.py`) — prefer extracting handlers into sibling modules (see refactor doc)

## Reporting issues

Track feature requests and bugs in [TODO.md](TODO.md) or your team's issue tracker. Include:

- Python version
- Instrument configuration (`system_configs.json` preset name)
- Steps to reproduce
- Relevant log output from the terminal panel

## License

MIT — see [LICENSE](LICENSE).
