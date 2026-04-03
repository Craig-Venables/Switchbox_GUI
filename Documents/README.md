# Documentation index

Material for **operators**, **developers**, **AI assistants**, and **release builds** is grouped below. Paths are relative to this `Documents/` folder unless noted.

## Folder map

| Folder | Audience | Contents |
|--------|----------|----------|
| **[`guides/`](guides/)** | Lab users | User guide, quick reference, JSON config, lab checklist, sample-type notes, pulse pattern guide |
| **[`reference/`](reference/)** | Developers & AI | Architecture maps for Sample GUI, Measurement GUI, pulse / oscilloscope / connection / motor tools, Keithley 4200 flow |
| **[`build/`](build/)** | Release / CI | PyInstaller instructions, spec behaviour, **module inventory for exe builds** |
| **[`development/`](development/)** | Maintainers | Refactor backlog, feature summaries, internal write-ups |
| **[`ai/`](ai/)** | AI tooling | Short orientation: where code and docs live, what to update when imports change |

## Guides ([`guides/`](guides/))

- **[USER_GUIDE.md](guides/USER_GUIDE.md)** — full operator walkthrough  
- **[QUICK_REFERENCE.md](guides/QUICK_REFERENCE.md)** — one-page cheat sheet  
- **[JSON_CONFIG_GUIDE.md](guides/JSON_CONFIG_GUIDE.md)** — automated testing / JSON configuration  
- **[LAB_TEST_CHECKLIST.md](guides/LAB_TEST_CHECKLIST.md)** — hardware smoke-test checklist  
- **[README_ADD_SAMPLE_TYPE.md](guides/README_ADD_SAMPLE_TYPE.md)** — adding a sample type  
- **[PULSE_PATTERN_PREVIEW_GUIDE.md](guides/PULSE_PATTERN_PREVIEW_GUIDE.md)** — pulse pattern preview  

## Reference ([`reference/`](reference/))

- **[MEASUREMENT_AND_SAMPLE_GUI_REFERENCE.md](reference/MEASUREMENT_AND_SAMPLE_GUI_REFERENCE.md)** — main app flow: `main.py` → Sample → Measurement GUI (start here for architecture)  
- **[PULSE_TESTING_GUI_REFERENCE.md](reference/PULSE_TESTING_GUI_REFERENCE.md)**  
- **[OSCILLOSCOPE_PULSE_GUI_REFERENCE.md](reference/OSCILLOSCOPE_PULSE_GUI_REFERENCE.md)**  
- **[CONNECTION_CHECK_GUI_REFERENCE.md](reference/CONNECTION_CHECK_GUI_REFERENCE.md)**  
- **[MOTOR_CONTROL_GUI_REFERENCE.md](reference/MOTOR_CONTROL_GUI_REFERENCE.md)**  
- **[KEITHLEY_4200_IV_SWEEP_FLOW.md](reference/KEITHLEY_4200_IV_SWEEP_FLOW.md)**  

## Build ([`build/`](build/))

- **[BUILD_INSTRUCTIONS.md](build/BUILD_INSTRUCTIONS.md)** — how to produce `Switchbox_GUI.exe`  
- **[BUILD_EXPLANATION.md](build/BUILD_EXPLANATION.md)** — what the spec file does, what gets bundled next to the exe  
- **[BUILD_MODULES.md](build/BUILD_MODULES.md)** — **checklist of packages/paths**; keep in sync with root **`build_exe.spec`**  

## Development notes ([`development/`](development/))

- **[REFACTOR_REMAINING.md](development/REFACTOR_REMAINING.md)**  
- **[OPTICAL_TESTS_UPDATE_SUMMARY.md](development/OPTICAL_TESTS_UPDATE_SUMMARY.md)**  
- **[DEVICE_VISUALIZER_GALLERY_OVERLAY_SUMMARY.md](development/DEVICE_VISUALIZER_GALLERY_OVERLAY_SUMMARY.md)**  

## AI assistants ([`ai/`](ai/))

- **[README.md](ai/README.md)** — entry point for automated tools (Cursor, etc.)  

---

## Testing (code, not docs)

From repository root:

```bash
python -m pytest tests
```

`tests/conftest.py` puts the repo root on `sys.path`. The suite includes headless tests for `MeasurementDataSaver` and related utilities.

## Optional runtime dependencies

- **Instruments:** `pyvisa`, `pyvisa-py`, `gpib-ctypes` (legacy GPIB)  
- **Telegram:** `python-telegram-bot`  
- **Plotting / analysis:** `matplotlib`, `numpy`, `pandas`, **`scipy`** (required for full `analysis` package behaviour)  
