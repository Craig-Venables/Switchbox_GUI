<!-- d4714c67-0e0e-4500-95bb-a26c2844b8c5 03de3f1b-0b51-40b6-96ff-53a97c16a1ec -->
# Unified JSON Configuration System for Automated Testing

## Goal

Enable comprehensive automated testing via Custom_Sweeps.json by supporting all measurement types, source modes, temperature control, and optical parameters with a unified configuration structure.

## Current State Analysis

**JSON Structure (Custom_Sweeps.json):**

- Currently has separate parameters per sweep (start_v, stop_v, etc.)
- Has "mode": "Endurance"/"Retention" fields that are NOT being read by code
- Has "excitation": "SMU Pulsed IV" etc. that IS being read
- Missing: source_mode, temperature, unified measurement_type

**Code Reading JSON (Measurement_GUI.py):**

- Line 2958: Loads sweeps from JSON
- Line 3070: Reads "excitation" parameter (works)
- Line 3020-3052: Reads IV parameters, LED, sequence
- Missing: Reading "mode" field, source_mode, temperature

## Implementation Plan

### Step 1: Define Unified JSON Schema

Add new top-level fields to each sweep entry:

```json
{
  "sweep_name": {
    "code_name": "test_v1",
    "sweeps": {
      "1": {
        "measurement_type": "IV",           // NEW: IV, Endurance, Retention, PulsedIV, FastPulses, Hold
        "source_mode": "voltage",           // NEW: voltage/current (defaults to voltage)
        "temperature_C": 25,                // NEW: Target temperature (optional)
        "temp_stabilization_s": 30,         // NEW: Wait time after temp change (optional)
        "icc": 1e-3,                        // NEW: Compliance per sweep (optional, defaults to GUI value)
        "delay_after_sweep_s": 5,           // NEW: Delay after this sweep completes (optional)
        "notes": "Testing after forming",   // NEW: Metadata/comments (optional)
        "start_v": 0,
        "stop_v": 1,
        "step_v": 0.05,
        "sweeps": 3,
        "step_delay": 0.05,
        "Sweep_type": "FS",
        "LED_ON": 1,
        "power": 1.0,
        "sequence": "01010"
      }
    }
  }
}
```

### Step 2: Update Measurement Dispatcher

**File: Measurement_GUI.py (run_custom_measurement method, ~line 3070)**

Current:

```python
excitation_mode = str(params.get("excitation", "DC Triangle IV"))
```

Replace with unified dispatcher:

```python
# Read measurement_type (new unified field)
measurement_type = str(params.get("measurement_type", "IV"))

# Backward compatibility: check old "mode" and "excitation" fields
if "mode" in params:
    measurement_type = params["mode"]  # Endurance, Retention
elif "excitation" in params:
    # Map old excitation names to measurement_type
    excitation_map = {
        "DC Triangle IV": "IV",
        "SMU Pulsed IV": "PulsedIV",
        "SMU Fast Pulses": "FastPulses",
        "SMU Fast Hold": "Hold"
    }
    measurement_type = excitation_map.get(params["excitation"], "IV")
```

### Step 3: Add Source Mode, Compliance, and Metadata Support

**File: Measurement_GUI.py (~line 3034)**

Add after reading sweep parameters:

```python
# Read source mode (NEW)
source_mode_str = params.get("source_mode", "voltage")
from Measurments.source_modes import SourceMode
source_mode = SourceMode.CURRENT if source_mode_str == "current" else SourceMode.VOLTAGE

# Read compliance per sweep (NEW - optional, defaults to GUI value)
icc_val = params.get("icc", None)
if icc_val is None:
    icc_val = float(self.icc.get())  # Use GUI value
else:
    icc_val = float(icc_val)  # Use JSON value

# Read metadata/notes (NEW - optional)
sweep_notes = params.get("notes", None)
if sweep_notes:
    print(f"Sweep {key} notes: {sweep_notes}")
```

Pass to all measurement service calls:

```python
v_arr, c_arr, timestamps = self.measurement_service.run_iv_sweep(
    # ... existing parameters ...
    icc=icc_val,  # UPDATED: per-sweep compliance
    source_mode=source_mode,  # NEW
)
```

### Step 4: Add Temperature Control (OPTIONAL)

**File: Measurement_GUI.py (~line 3034)**

Add temperature handling - ONLY activates when temperature_C is explicitly present in JSON:

```python
# Read temperature (NEW - OPTIONAL, defaults to OFF)
# Temperature control is ONLY activated if temperature_C is explicitly set in JSON
if "temperature_C" in params:
    target_temp = params["temperature_C"]
    if hasattr(self, 'temp_controller') and self.temp_controller is not None:
        try:
            print(f"Setting temperature to {target_temp}°C")
            self.temp_controller.set_temperature(float(target_temp))
            
            # Optional: wait for stabilization (only if specified)
            stabilization_time = params.get("temp_stabilization_s", 0)
            if stabilization_time > 0:
                print(f"Waiting {stabilization_time}s for temperature stabilization...")
                time.sleep(float(stabilization_time))
        except Exception as e:
            print(f"Temperature setting failed: {e}")
            # Continue with measurement even if temp control fails
    else:
        print("Warning: temperature_C specified but no temp controller connected")
# If "temperature_C" not in params, temperature control is completely skipped
```

### Step 5: Implement Measurement Type Router

**File: Measurement_GUI.py (~line 3070)**

Create unified measurement dispatcher:

```python
# Route to appropriate measurement based on measurement_type
if measurement_type == "IV":
    v_arr, c_arr, timestamps = self.measurement_service.run_iv_sweep(
        keithley=self.keithley,
        start_v=start_v,
        stop_v=stop_v,
        step_v=step_v,
        sweeps=sweeps,
        step_delay=step_delay,
        sweep_type=sweep_type,
        icc=float(self.icc.get()),
        psu=getattr(self, 'psu', None),
        led=led,
        power=power,
        optical=getattr(self, 'optical', None),
        sequence=sequence,
        pause_s=pause,
        smu_type=getattr(self, 'SMU_type', 'Keithley 2401'),
        source_mode=source_mode,
        should_stop=lambda: getattr(self, 'stop_measurement_flag', False),
        on_point=lambda v, i, t: self._update_live_plot(v, i, t)
    )

elif measurement_type == "Endurance":
    set_v = params.get("set_v", 1.5)
    reset_v = params.get("reset_v", -1.5)
    pulse_ms = params.get("pulse_ms", 10)
    cycles = params.get("cycles", 100)
    read_v = params.get("read_v", 0.2)
    
    v_arr, c_arr, timestamps = self.measurement_service.run_endurance(
        keithley=self.keithley,
        set_voltage=set_v,
        reset_voltage=reset_v,
        pulse_width_s=pulse_ms/1000,
        num_cycles=cycles,
        read_voltage=read_v,
        icc=float(self.icc.get()),
        psu=getattr(self, 'psu', None),
        led=led,
        power=power,
        optical=getattr(self, 'optical', None),
        smu_type=getattr(self, 'SMU_type', 'Keithley 2401'),
        should_stop=lambda: getattr(self, 'stop_measurement_flag', False),
        on_point=lambda v, i, t: self._update_live_plot(v, i, t)
    )

elif measurement_type == "Retention":
    set_v = params.get("set_v", 1.5)
    set_ms = params.get("set_ms", 10)
    read_v = params.get("read_v", 0.2)
    times_s = params.get("times_s", [1, 10, 100, 1000])
    
    v_arr, c_arr, timestamps = self.measurement_service.run_retention(
        keithley=self.keithley,
        set_voltage=set_v,
        set_time_s=set_ms/1000,
        read_voltage=read_v,
        repeat_delay_s=0.1,
        number=len(times_s),
        icc=float(self.icc.get()),
        psu=getattr(self, 'psu', None),
        led=led,
        optical=getattr(self, 'optical', None),
        smu_type=getattr(self, 'SMU_type', 'Keithley 2401'),
        should_stop=lambda: getattr(self, 'stop_measurement_flag', False),
        on_point=lambda v, i, t: self._update_live_plot(v, i, t)
    )

elif measurement_type == "PulsedIV":
    # ... existing SMU Pulsed IV code ...
    
elif measurement_type == "FastPulses":
    # ... existing SMU Fast Pulses code ...
    
elif measurement_type == "Hold":
    # ... existing SMU Fast Hold code ...
    
else:
    print(f"Unknown measurement_type: {measurement_type}")
    continue
```

### Step 6: Update JSON Examples

**File: Json_Files/Custom_Sweeps.json**

Add example entries showing new features:

```json
{
  "Full_Feature_Test": {
    "code_name": "full_test",
    "sweeps": {
      "1": {
        "measurement_type": "IV",
        "source_mode": "voltage",
        "temperature_C": 25,
        "temp_stabilization_s": 30,
        "start_v": 0,
        "stop_v": 1,
        "step_v": 0.05,
        "sweeps": 3,
        "step_delay": 0.01,
        "Sweep_type": "FS",
        "LED_ON": 0
      },
      "2": {
        "measurement_type": "IV",
        "source_mode": "current",
        "temperature_C": 50,
        "start_v": 0,
        "stop_v": 1e-6,
        "step_v": 1e-8,
        "sweeps": 1,
        "step_delay": 0.05,
        "Sweep_type": "PS",
        "LED_ON": 1,
        "power": 1.0
      },
      "3": {
        "measurement_type": "Endurance",
        "source_mode": "voltage",
        "temperature_C": 25,
        "set_v": 1.5,
        "reset_v": -1.5,
        "pulse_ms": 10,
        "cycles": 100,
        "read_v": 0.2,
        "LED_ON": 1,
        "sequence": "01010"
      },
      "4": {
        "measurement_type": "Retention",
        "source_mode": "voltage",
        "temperature_C": 75,
        "set_v": 1.5,
        "set_ms": 10,
        "read_v": 0.2,
        "times_s": [1, 3, 10, 30, 100, 300, 1000],
        "LED_ON": 0
      }
    }
  }
}
```

### Step 7: Add Validation and Documentation

**File: Measurments/json_config_validator.py (NEW)**

Create validator for JSON schema:

```python
def validate_sweep_config(params: dict) -> tuple[bool, str]:
    """Validate sweep configuration parameters"""
    
    measurement_type = params.get("measurement_type", "IV")
    valid_types = ["IV", "Endurance", "Retention", "PulsedIV", "FastPulses", "Hold"]
    
    if measurement_type not in valid_types:
        return False, f"Invalid measurement_type: {measurement_type}"
    
    # Type-specific validation
    if measurement_type == "IV":
        required = ["start_v", "stop_v"]
        for field in required:
            if field not in params:
                return False, f"Missing required field for IV: {field}"
    
    elif measurement_type == "Endurance":
        required = ["set_v", "reset_v", "cycles"]
        for field in required:
            if field not in params:
                return False, f"Missing required field for Endurance: {field}"
    
    # ... more validation
    
    return True, "Valid"
```

**File: Changes_Ai_Fixes/JSON_CONFIG_GUIDE.md (NEW)**

Document the unified schema:

```markdown
# Custom Sweeps JSON Configuration Guide

## Overview
The Custom_Sweeps.json file supports comprehensive automated testing with all measurement types, source modes, temperature control, and optical parameters.

## Unified Schema

### Top-Level Structure
{
  "test_name": {
    "code_name": "short_name",
    "sweeps": {
      "1": { sweep_parameters },
      "2": { sweep_parameters }
    }
  }
}

### Sweep Parameters

#### Universal Parameters (all measurement types)
- measurement_type: "IV" | "Endurance" | "Retention" | "PulsedIV" | "FastPulses" | "Hold"
- source_mode: "voltage" | "current" (default: "voltage")
- temperature_C: float (target temperature in Celsius)
- temp_stabilization_s: float (wait time after temperature change)
- LED_ON: 0 | 1
- power: float (LED power level)
- sequence: string (LED on/off pattern, e.g. "01010")

#### IV-Specific Parameters
- start_v: float
- stop_v: float
- step_v: float
- sweeps: int
- step_delay: float (seconds)
- Sweep_type: "FS" | "PS" | "NS" | "Triangle"
- pause: float (pause at extrema, seconds)

... [rest of documentation]
```

### Step 8: Backward Compatibility

Ensure old JSON files still work:

1. If "measurement_type" missing, default to "IV"
2. If "excitation" present, map to measurement_type
3. If "mode" present, use it as measurement_type
4. If "source_mode" missing, default to "voltage"
5. If temperature fields missing, skip temperature control

## Testing Checklist

- [ ] Test IV measurement with voltage source mode
- [ ] Test IV measurement with current source mode
- [ ] Test Endurance measurement
- [ ] Test Retention measurement
- [ ] Test temperature control integration
- [ ] Test LED/optical parameters
- [ ] Test backward compatibility with existing JSON
- [ ] Test validation catches invalid configurations

## Files to Modify

1. `Measurement_GUI.py` - Main dispatcher logic (~200 lines)
2. `Json_Files/Custom_Sweeps.json` - Add examples
3. `Measurments/json_config_validator.py` - NEW file
4. `Changes_Ai_Fixes/JSON_CONFIG_GUIDE.md` - NEW documentation