# Documentation Index

This directory contains documentation for the modular utilities and configuration guides.

## Quick Navigation

### For Users
- **[USER_GUIDE.md](USER_GUIDE.md)** - Complete guide on how to use all utilities
- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - One-page cheat sheet
- **[JSON_CONFIG_GUIDE.md](JSON_CONFIG_GUIDE.md)** - JSON configuration for automated testing

### Available Utilities

#### Data Utilities (`Measurements/data_utils.py`)
- `safe_measure_current()` - Normalize current measurements
- `safe_measure_voltage()` - Normalize voltage measurements
- Handles all instrument output formats automatically

#### Optical Control (`Measurements/optical_controller.py`)
- `OpticalController` - Unified interface for laser/LED control
- Works with any light source automatically

#### Source Modes (`Measurements/source_modes.py`)
- `SourceMode.VOLTAGE` / `SourceMode.CURRENT` - Source modes
- `apply_source()` - Apply voltage or current
- `measure_result()` - Measure corresponding value
- Enables current source mode (source I, measure V)

#### Sweep Patterns (`Measurements/sweep_patterns.py`)
- `build_sweep_values()` - Generate any sweep pattern
- `SweepType.POSITIVE/NEGATIVE/FULL/TRIANGLE` - Sweep types

#### Multiplexer (`Equipment/multiplexer_manager.py`)
- `MultiplexerManager` - Unified multiplexer interface
- Supports Pyswitchbox, Electronic_Mpx, and more

#### Data Formatting (`Measurements/data_formats.py`)
- `DataFormatter` - Consistent file formatting
- `FileNamer` - Standardized filename generation

#### Measurement Orchestrators
- `Measurements/single_measurement_runner.py` – Standard DC IV sweep orchestrator
- `Measurements/pulsed_measurement_runner.py` – SMU/PMU pulsed and fast-pulse/hold flows
- `Measurements/special_measurement_runner.py` – ISPP, pulse-width sweep, threshold search, transient capture
- `Measurements/sequential_runner.py` – Batch IV/averaging loop controller for the sequential panel
- `Measurements/telegram_coordinator.py` – Telegram post-measurement automation
- `Measurements/background_workers.py` – Manual endurance/retention worker threads
- `Measurements/data_saver.py` – Centralized save/plot helpers used by all runners

#### GUI Helpers
- `gui/layout_builder.py` – Builds all Tk panels (manual endurance, custom sweeps, sequential controls now included in the middle column)
- `gui/plot_updaters.py` – Background worker threads that keep matplotlib panels in sync during live measurements
- `Measurement_GUI.bring_to_top()` – Lightweight focus helper runners use to surface the main window

## Testing

Run the automated test suite with:
```bash
python -m pytest tests
```

`tests/conftest.py` ensures the repo root is on `sys.path`, so `pytest tests` also works if you prefer. The suite covers summary plot generation (`MeasurementDataSaver`) and directory utilities (e.g. `find_largest_number_in_folder`).  Tests run headlessly using `matplotlib`’s Agg backend, so no GUI is required.

Individual modules can still be smoke-tested with `python -m` if needed.

### Optional Dependencies
- **Instruments:** `pyvisa`, `pyvisa-py`, `gpib-ctypes` (for legacy GPIB). Without them the GUI falls back to simulation modes.
- **Telegram Bot:** `python-telegram-bot` – required to enable messaging callbacks.
- **Plotting:** `matplotlib` (Agg backend configured automatically for tests).

## Getting Started

1. **New to this?** → Start with [USER_GUIDE.md](USER_GUIDE.md)
2. **Need quick reference?** → See [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
3. **Configuring automated tests?** → See [JSON_CONFIG_GUIDE.md](JSON_CONFIG_GUIDE.md)

## Future Plans

- **[Documents/GUI_REFACTORING_PLAN.md](Documents/GUI_REFACTORING_PLAN.md)** - Detailed plan for future GUI refactoring (reference only)
- **[Documents/LAB_TEST_CHECKLIST.md](Documents/LAB_TEST_CHECKLIST.md)** - On-site guide for validating the GUI with real hardware
- Clear remaining optional import warnings (`PMU_Testing_GUI`, `MeasurementDriver`, `TestRunner`, `MeasurementPlotter`) by lazy-loading or guarding them.
- Exercise pulsed/special/custom measurement flows with hardware attached; log findings in the smoke-test checklist.
- Extract plotting setup/update logic into dedicated modules (`gui/plot_panels.py`, `gui/plot_updaters.py`) to complete the architecture.
- Expand automated coverage with instrument-mock tests for runner orchestration and background workers.
- Verify Telegram and manual worker flows end-to-end once credentials/hardware are available.
