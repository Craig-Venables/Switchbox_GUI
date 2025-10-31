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

## Testing

Test each module:
```bash
python -m Measurments.data_utils
python -m Measurments.optical_controller
python -m Measurments.source_modes
python -m Measurments.sweep_patterns
python -m Equipment.multiplexer_manager
python -m Measurments.data_formats
```

All should print "All tests passed!" ✓

## Getting Started

1. **New to this?** → Start with [USER_GUIDE.md](USER_GUIDE.md)
2. **Need quick reference?** → See [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
3. **Configuring automated tests?** → See [JSON_CONFIG_GUIDE.md](JSON_CONFIG_GUIDE.md)

## Future Plans

- **[Documents/GUI_REFACTORING_PLAN.md](Documents/GUI_REFACTORING_PLAN.md)** - Detailed plan for future GUI refactoring (reference only)
