# Custom Sweeps JSON Configuration Guide

## Overview
The Custom_Sweeps.json file now supports comprehensive automated testing with all measurement types, source modes, temperature control, and optical parameters through a unified configuration structure.

## Unified Schema

### Top-Level Structure
```json
{
  "test_name": {
    "code_name": "short_name",
    "sweeps": {
      "1": { sweep_parameters },
      "2": { sweep_parameters }
    }
  }
}
```

### Sweep Parameters

#### Universal Parameters (all measurement types)
- **measurement_type**: `"IV"` | `"Endurance"` | `"Retention"` | `"PulsedIV"` | `"FastPulses"` | `"Hold"` (default: `"IV"`)
- **source_mode**: `"voltage"` | `"current"` (default: `"voltage"`)
- **temperature_C**: `float` (target temperature in Celsius, optional)
- **temp_stabilization_s**: `float` (wait time after temperature change, optional)
- **icc**: `float` (compliance per sweep, optional - defaults to GUI value)
- **delay_after_sweep_s**: `float` (delay after this sweep completes, optional)
- **notes**: `string` (metadata/comments, optional)
- **LED_ON**: `0` | `1`
- **power**: `float` (LED power level)
- **sequence**: `string` (LED on/off pattern, e.g. `"01010"`)

#### IV-Specific Parameters
- **start_v**: `float` (start voltage/current)
- **stop_v**: `float` (stop voltage/current)
- **step_v**: `float` (step size)
- **sweeps**: `int` (number of sweeps)
- **step_delay**: `float` (delay between steps, seconds)
- **Sweep_type**: `"FS"` | `"PS"` | `"NS"` | `"HS"` | `"Triangle"`
- **pause**: `float` (pause at extrema, seconds)

#### Endurance-Specific Parameters
- **set_v**: `float` (set voltage)
- **reset_v**: `float` (reset voltage)
- **pulse_ms**: `float` (pulse width in milliseconds)
- **cycles**: `int` (number of cycles)
- **read_v**: `float` (read voltage)

#### Retention-Specific Parameters
- **set_v**: `float` (set voltage)
- **set_ms**: `float` (set pulse width in milliseconds)
- **read_v**: `float` (read voltage)
- **times_s**: `[float]` (array of delay times in seconds)

#### PulsedIV-Specific Parameters
- **start_v**: `float` (start amplitude)
- **stop_v**: `float` (stop amplitude)
- **step_v**: `float` (step size)
- **num_steps**: `int` (number of steps, optional)
- **pulse_ms**: `float` (pulse width in milliseconds)
- **vbase**: `float` (base voltage)
- **inter_delay**: `float` (inter-step delay)

#### FastPulses-Specific Parameters
- **pulse_v**: `float` (pulse voltage)
- **pulse_ms**: `float` (pulse width in milliseconds)
- **num**: `int` (number of pulses)
- **inter_delay**: `float` (inter-pulse delay)
- **vbase**: `float` (base voltage)

#### Hold-Specific Parameters
- **hold_v**: `float` (hold voltage)
- **duration_s**: `float` (hold duration in seconds)
- **sample_dt_s**: `float` (sampling interval in seconds)

## Example Configurations

### Basic IV Measurement
```json
{
  "Basic_IV": {
    "code_name": "basic_iv",
    "sweeps": {
      "1": {
        "measurement_type": "IV",
        "source_mode": "voltage",
        "start_v": 0,
        "stop_v": 1,
        "step_v": 0.05,
        "sweeps": 3,
        "step_delay": 0.05,
        "Sweep_type": "FS",
        "LED_ON": 0
      }
    }
  }
}
```

### Current Source Mode
```json
{
  "Current_Source_Test": {
    "code_name": "current_test",
    "sweeps": {
      "1": {
        "measurement_type": "IV",
        "source_mode": "current",
        "start_v": 0,
        "stop_v": 1e-6,
        "step_v": 1e-8,
        "sweeps": 1,
        "step_delay": 0.05,
        "Sweep_type": "PS",
        "icc": 10.0,
        "notes": "Current source test with high compliance"
      }
    }
  }
}
```

### Temperature Control
```json
{
  "Temperature_Sweep": {
    "code_name": "temp_sweep",
    "sweeps": {
      "1": {
        "measurement_type": "IV",
        "source_mode": "voltage",
        "temperature_C": 25,
        "temp_stabilization_s": 30,
        "start_v": 0,
        "stop_v": 1,
        "step_v": 0.1,
        "sweeps": 1,
        "step_delay": 0.05,
        "Sweep_type": "FS",
        "LED_ON": 0,
        "notes": "Room temperature baseline"
      },
      "2": {
        "measurement_type": "IV",
        "source_mode": "voltage",
        "temperature_C": 75,
        "temp_stabilization_s": 60,
        "start_v": 0,
        "stop_v": 1,
        "step_v": 0.1,
        "sweeps": 1,
        "step_delay": 0.05,
        "Sweep_type": "FS",
        "LED_ON": 0,
        "delay_after_sweep_s": 10,
        "notes": "High temperature measurement"
      }
    }
  }
}
```

### Endurance Testing
```json
{
  "Endurance_Test": {
    "code_name": "endurance",
    "sweeps": {
      "1": {
        "measurement_type": "Endurance",
        "source_mode": "voltage",
        "temperature_C": 25,
        "set_v": 1.5,
        "reset_v": -1.5,
        "pulse_ms": 10,
        "cycles": 100,
        "read_v": 0.2,
        "LED_ON": 1,
        "power": 1.0,
        "sequence": "01010",
        "icc": 1e-3,
        "notes": "Endurance cycling with LED pattern"
      }
    }
  }
}
```

### Retention Testing
```json
{
  "Retention_Test": {
    "code_name": "retention",
    "sweeps": {
      "1": {
        "measurement_type": "Retention",
        "source_mode": "voltage",
        "temperature_C": 75,
        "set_v": 1.5,
        "set_ms": 10,
        "read_v": 0.2,
        "times_s": [1, 3, 10, 30, 100, 300, 1000],
        "LED_ON": 0,
        "icc": 1e-3,
        "delay_after_sweep_s": 5,
        "notes": "Retention test at high temperature"
      }
    }
  }
}
```

### Complex Multi-Measurement Test
```json
{
  "Comprehensive_Test": {
    "code_name": "comprehensive",
    "sweeps": {
      "1": {
        "measurement_type": "IV",
        "source_mode": "voltage",
        "temperature_C": 25,
        "start_v": 0,
        "stop_v": 1,
        "step_v": 0.05,
        "sweeps": 3,
        "step_delay": 0.01,
        "Sweep_type": "FS",
        "LED_ON": 0,
        "notes": "Baseline IV measurement"
      },
      "2": {
        "measurement_type": "Endurance",
        "source_mode": "voltage",
        "set_v": 1.5,
        "reset_v": -1.5,
        "pulse_ms": 10,
        "cycles": 50,
        "read_v": 0.2,
        "LED_ON": 1,
        "power": 1.0,
        "sequence": "01010",
        "notes": "Forming endurance cycles"
      },
      "3": {
        "measurement_type": "Retention",
        "source_mode": "voltage",
        "set_v": 1.5,
        "set_ms": 10,
        "read_v": 0.2,
        "times_s": [1, 10, 100, 1000],
        "LED_ON": 0,
        "delay_after_sweep_s": 5,
        "notes": "Retention after forming"
      },
      "4": {
        "measurement_type": "IV",
        "source_mode": "voltage",
        "start_v": 0,
        "stop_v": 1,
        "step_v": 0.05,
        "sweeps": 3,
        "step_delay": 0.01,
        "Sweep_type": "FS",
        "LED_ON": 0,
        "notes": "Post-forming IV measurement"
      }
    }
  }
}
```

## Backward Compatibility

The system maintains full backward compatibility with existing JSON configurations:

1. **Old "mode" field**: Automatically mapped to `measurement_type`
2. **Old "excitation" field**: Automatically mapped to `measurement_type`
3. **Missing fields**: Default values applied (e.g., `source_mode` defaults to `"voltage"`)
4. **Temperature control**: Only activated when `temperature_C` is explicitly specified

### Migration Examples

**Old Format:**
```json
{
  "1": {
    "mode": "Endurance",
    "set_v": 1.5,
    "reset_v": -1.5,
    "cycles": 100
  }
}
```

**New Format (equivalent):**
```json
{
  "1": {
    "measurement_type": "Endurance",
    "source_mode": "voltage",
    "set_v": 1.5,
    "reset_v": -1.5,
    "cycles": 100,
    "icc": 1e-3,
    "notes": "Endurance test"
  }
}
```

## Key Features

### 1. Unified Measurement Types
- Single `measurement_type` field controls all measurement modes
- Automatic routing to appropriate measurement service
- Support for all existing and new measurement types

### 2. Source Mode Flexibility
- Voltage source mode (default)
- Current source mode for specialized measurements
- Automatic compliance handling per mode

### 3. Temperature Control
- Optional temperature setting per sweep
- Stabilization time configuration
- Automatic fallback if temperature controller unavailable

### 4. Enhanced Timing Control
- Per-sweep compliance limits
- Configurable inter-sweep delays
- Fine-grained timing control for all measurement types

### 5. Metadata Support
- Notes field for documentation
- Enhanced logging and debugging
- Better test traceability

### 6. Validation
- Built-in parameter validation
- Clear error messages for invalid configurations
- Automatic backward compatibility checking

## Usage Tips

1. **Start Simple**: Begin with basic IV measurements and gradually add features
2. **Use Notes**: Always include descriptive notes for complex test sequences
3. **Temperature Control**: Only specify `temperature_C` when needed to avoid unnecessary temperature changes
4. **Compliance Limits**: Use per-sweep `icc` values for specialized measurements
5. **Timing**: Use `delay_after_sweep_s` for device recovery or thermal settling
6. **Validation**: Test configurations with the validator before running long measurements

## Error Handling

The system provides comprehensive error handling:
- Invalid measurement types are caught and reported
- Missing required parameters trigger clear error messages
- Temperature control failures don't stop measurements
- Backward compatibility warnings are logged but don't prevent execution

## Performance Considerations

- Temperature changes add significant time - use sparingly
- Inter-sweep delays should be minimized for fast testing
- Current source mode works best with Keithley 4200A
- Hardware sweeps are automatically selected for optimal performance
