# PMU-Ccode Directory Structure

This directory contains C source code for Keithley 4200A PMU (Pulse Measurement Unit) user library functions.

## Directory Organization

### `working_examples/`
Contains proven, working C functions that are currently in use:
- **PMU_PulseTrain.c** - Pulse train measurements with multiple pulses
- **PMU_retention.c** - Retention measurements with set/reset/measure cycles
- **PulseTrain_pulse_ilimitNK.c** - Helper function for pulse train execution with current limiting
- **retention_pulse_ilimitNK.c** - Helper function for retention pulse execution with current limiting

### `tests/`
Contains test/development C functions:
- **PMU_SimplePulse.c** - Simple test function: one main pulse followed by one read pulse
- **PMU_SinglePulseReads.c** - Single pulse with multiple reads (in development)

## Documentation Files
- **PMU_Usage_Guide.md** - Guide on how to use the PMU functions
- **PMU_Troubleshooting.md** - Troubleshooting guide
- **Memristor_Measurements.md** - Documentation for memristor measurement procedures

## Usage
These C functions are compiled into user library modules that can be called from LabVIEW or Python via the KXCI (Keithley External Control Interface) using the `EX` command.

Example:
```
EX LibraryName FunctionName(parameters...)
```

