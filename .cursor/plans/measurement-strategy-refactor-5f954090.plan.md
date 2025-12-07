<!-- 5f954090-6fa1-40d1-9f4d-d0444b5bf789 ce4a7640-df3e-4623-83fd-889e316f5367 -->
# Unified Measurement Strategy Refactor

## Overview

Create unified measurement methods in `IVControllerManager` for ALL measurement types (IV sweeps, pulses, retention, endurance, pulsed IV). Each method routes to instrument-specific implementations based on instrument type, respecting limits and providing live plotting.

## Unified API Methods (All in IVControllerManager)

### Main Entry Points

```python
# In IVControllerManager class

def do_iv_sweep(config, psu, optical, should_stop, on_point) -> (v_arr, i_arr, t_arr)
def do_pulse_measurement(pulse_voltage, pulse_width_ms, num_pulses, ...) -> (v_arr, i_arr, t_arr)
def do_retention_measurement(set_voltage, set_time_s, read_voltage, ...) -> (v_arr, i_arr, t_arr)
def do_endurance_measurement(set_voltage, reset_voltage, pulse_width_s, ...) -> (v_arr, i_arr, t_arr)
def do_pulsed_iv_sweep(config, pulse_width_ms, read_delay_ms, ...) -> (v_arr, i_arr, t_arr)
```

Each routes internally based on `self.smu_type` to instrument-specific implementations.

## Implementation Structure

### Phase 1: Core Infrastructure

1. Create `Measurments/measurement_context.py` - Context dataclass

### Phase 2: Unified Methods + Instrument-Specific Implementations

2. Implement all 5 unified routing methods in `IVControllerManager`
3. For each measurement type, implement instrument-specific versions:

   - `_do_iv_sweep_4200a()`, `_do_iv_sweep_2450()`, `_do_iv_sweep_2400()`, `_do_iv_sweep_generic()`
   - `_do_pulse_measurement_4200a()`, `_do_pulse_measurement_2450()`, etc.
   - `_do_retention_measurement_4200a()`, etc.
   - `_do_endurance_measurement_4200a()`, etc.
   - `_do_pulsed_iv_sweep_4200a()`, etc.

### Phase 3: Replace All Measurement Calls

4. Update `MeasurementService` - replace all methods to call unified API
5. Update all other measurement call sites

### Phase 4: Testing

6. Test all measurement types on all instruments
7. Verify live plotting, LED integration, limits enforcement

## Key Points

- ALL measurement types get unified API
- Each instrument has optimized implementation
- Live plotting for all where available
- Respect instrument limits
- Raise exceptions on failure
- Preserve all sweep types and functionality