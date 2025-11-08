# Documentation Index

This directory contains documentation for the modular utilities and configuration guides.

## Quick Navigation

### For Users
- **[USER_GUIDE.md](USER_GUIDE.md)** - Complete guide on how to use all utilities
- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - One-page cheat sheet
- **[JSON_CONFIG_GUIDE.md](JSON_CONFIG_GUIDE.md)** - JSON configuration for automated testing

### Available Utilities

#### Data Utilities (`Measurments/data_utils.py`)
- `safe_measure_current()` - Normalize current measurements
- `safe_measure_voltage()` - Normalize voltage measurements
- Handles all instrument output formats automatically

#### Optical Control (`Measurments/optical_controller.py`)
- `OpticalController` - Unified interface for laser/LED control
- Works with any light source automatically

#### Source Modes (`Measurments/source_modes.py`)
- `SourceMode.VOLTAGE` / `SourceMode.CURRENT` - Source modes
- `apply_source()` - Apply voltage or current
- `measure_result()` - Measure corresponding value
- Enables current source mode (source I, measure V)

#### Sweep Patterns (`Measurments/sweep_patterns.py`)
- `build_sweep_values()` - Generate any sweep pattern
- `SweepType.POSITIVE/NEGATIVE/FULL/TRIANGLE` - Sweep types

#### Multiplexer (`Equipment/multiplexer_manager.py`)
- `MultiplexerManager` - Unified multiplexer interface
- Supports Pyswitchbox, Electronic_Mpx, and more

#### Data Formatting (`Measurments/data_formats.py`)
- `DataFormatter` - Consistent file formatting
- `FileNamer` - Standardized filename generation

#### Measurement Orchestrators
- `Measurments/single_measurement_runner.py` – Standard DC IV sweep orchestrator
- `Measurments/pulsed_measurement_runner.py` – SMU/PMU pulsed and fast-pulse/hold flows
- `Measurments/special_measurement_runner.py` – ISPP, pulse-width sweep, threshold search, transient capture
- `Measurments/telegram_coordinator.py` – Telegram post-measurement automation
- `Measurments/background_workers.py` – Manual endurance/retention worker threads

## Testing

Run the automated test suite with:
```bash
pytest tests
```

The tests cover summary plot generation (`MeasurementDataSaver`) and directory utilities (e.g. `find_largest_number_in_folder`).  They run headlessly using `matplotlib`’s Agg backend, so no GUI is required.

Individual modules can still be smoke-tested with `python -m` if needed.

## Getting Started

1. **New to this?** → Start with [USER_GUIDE.md](USER_GUIDE.md)
2. **Need quick reference?** → See [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
3. **Configuring automated tests?** → See [JSON_CONFIG_GUIDE.md](JSON_CONFIG_GUIDE.md)

## Future Plans

- **[Documents/GUI_REFACTORING_PLAN.md](Documents/GUI_REFACTORING_PLAN.md)** - Detailed plan for future GUI refactoring (reference only)
