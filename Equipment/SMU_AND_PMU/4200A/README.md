# PMU C Example Translations


# See PMU repoitory for actual code for this 

Python versions of Keithley's official C examples.

## Files

- **`simple_10ns_pulse.py`** - Basic continuous pulse generation
- **`segarb_example.py`** - Segment ARB multi-level waveforms
- **`pmu_iv_sweep_example.py`** - Dual-channel pulse IV sweep (Gate/Drain)

---

## 1. Simple 10ns Pulse Example

Direct Python translation of `PMU_10ns_Pulse_Example.c`

### Usage

```python
from simple_10ns_pulse import PMU_10ns_Simple

# Connect
pmu = PMU_10ns_Simple(ip="192.168.0.10", port=8888, card="PMU1")

# Run continuous pulses
pmu.run_10ns_pulse(channel=1)

# ... pulses run continuously ...

# Stop
pmu.stop(1)
pmu.cleanup()
```

Or just run it:

```bash
cd Equipment/SMU_AND_PMU/4200A
python simple_10ns_pulse.py
```

Press Ctrl+C to stop. Connect scope to PMU1 Channel 1 to view output.

---

## 2. Segment ARB Example

Python translation of `PMU_SegArb_Example.c`

Segment ARB mode creates complex multi-segment waveforms with:
- Different voltage levels per segment
- Individual timing control
- Waveform measurement (V, I vs time)

### Usage

```python
from segarb_example import PMU_SegArb

pmu = PMU_SegArb(ip="192.168.0.10", port=8888, card="PMU1")

results = pmu.run_segarb_sweep(
    v_range_ch1=10.0,
    i_range_ch1=0.2,
    start_v_ch1=[0.0, 0.0, 0.5, 0.5, 0.0],  # Voltage sequence
    stop_v_ch1=[0.0, 0.5, 0.5, 0.0, 0.0],
    start_v_ch2=[...],  # Channel 2 voltages
    stop_v_ch2=[...],
    seg_time=[100e-9, 10e-6, ...],  # Timing for each segment
)

pmu.cleanup()
```

Or run the built-in 5-point sweep example:

```bash
python segarb_example.py
```

This runs the example from the C code:
- Ch1: 0.5V → 1V → 1.5V → 2V → 2.5V (sweep UP)
- Ch2: 2.5V → 2V → 1.5V → 1V → 0.5V (sweep DOWN)

Returns dict with `v_ch1`, `i_ch1`, `v_ch2`, `i_ch2`, `time_ch1`, `time_ch2` arrays.

---

## 3. PMU IV Sweep Example

Python translation of `PMU_IV_sweep_Example.c`

This performs a dual-channel pulse IV sweep, similar to transistor characterization:
- **Gate channel**: Fixed pulse amplitude
- **Drain channel**: Swept pulse amplitude
- Measures spot mean at both amplitude and base levels
- Optional SMU for biasing additional terminals
- Support for Load Line Effect Compensation (LLEC)
- Automatic sample rate adjustment

### Features

- Independent timing control for each channel (pulse width, rise/fall times, delay)
- Spot mean measurements at pulse top and base
- Automatic verification that measurement windows overlap
- Optional SMU bias voltage
- Threshold checking (voltage, current, power)
- Simple or Advanced mode operation

### Usage

```python
from pmu_iv_sweep_example import PMU_IV_Sweep

# Connect to PMU
pmu = PMU_IV_Sweep(ip="192.168.0.10", port=8888, pmu_id="PMU1")

# Run IV sweep
results = pmu.iv_sweep(
    # Gate (fixed amplitude)
    pulse_width_gate=200e-9,
    ampl_v_gate=2.0,
    base_v_gate=0.0,
    gate_ch=1,
    
    # Drain (swept amplitude)
    pulse_width_drain=300e-9,
    start_v_drain=0.0,
    stop_v_drain=5.0,
    step_v_drain=1.0,
    base_v_drain=0.0,
    drain_ch=2,
    
    # Timing (common)
    period=5e-6,
    meas_start_gate=0.65,  # Measure at 65-80% of pulse top
    meas_stop_gate=0.80,
    
    # Ranges
    v_range_gate=10.0,
    i_range_gate=0.01,
    v_range_drain=10.0,
    i_range_drain=0.2,
    
    # Optional SMU bias
    smu_id="SMU1",
    smu_v=0.0,
    
    verbose=True
)

# Results returned as pandas DataFrame
print(results)
# Columns: Drain_V_Ampl, Drain_I_Ampl, Drain_V_Base, Drain_I_Base,
#          Gate_V_Ampl, Gate_I_Ampl, Gate_V_Base, Gate_I_Base,
#          TimeStamp_Ampl_Gate, TimeStamp_Base_Gate,
#          TimeStamp_Ampl_Drain, TimeStamp_Base_Drain

pmu.cleanup()
```

Or run the built-in example:

```bash
python pmu_iv_sweep_example.py
```

**DEFAULT:** This runs a **two-terminal device** IV sweep:
- Channel 1: Held at 0V (ground return)
- Channel 2: Swept from -1V → +1V in 0.2V steps (11 points)
- Connect your device between Channel 1 (ground) and Channel 2 (signal)

Results saved to `pmu_iv_sweep_results.csv` with columns: V (V), I (A), R (Ohm), Time (s)

**For transistor (3-terminal) sweep**, call `example_transistor_iv()` instead.

### Troubleshooting

**Error: "Illegal value for parameter"**
- This usually means timing parameters are out of spec
- Try increasing `pulse_width` (min 60ns for 10V range, 140ns for 40V range)
- Ensure `rise_time` and `fall_time` are >= 20ns for 10V range, >= 100ns for 40V
- Verify `period` > `pulse_width` + `rise_time` + `fall_time` + `delay`
- Check that measurement window is within the pulse top

**Error: "Gate measurement window not within drain pulse top"**
- Adjust `meas_start_gate` and `meas_stop_gate` (typically 0.2 to 0.8)
- Ensure both channels have compatible timing (same or overlapping pulse tops)
- Try making drain pulse longer than gate pulse

**Noisy or invalid measurements**
- Increase `pulse_average` to average more pulses
- Use slower rise/fall times (e.g. 100ns instead of 20ns)
- Check load resistance settings (50Ω typical for fast signals, 1MΩ for DC-like)
- Verify current ranges are appropriate for expected currents

**Current reads as NaN or overflow**
- Current range may be too low - increase `i_range_gate/drain`
- Or enable `ltd_auto_curr_gate/drain=True` for auto-ranging
- Check that device isn't in compliance

**Measurements seem stuck or frozen**
- Test may have hit threshold limits - check voltage/current/power thresholds
- Try `pmu_mode=0` (Simple) instead of `pmu_mode=1` (Advanced)
- Verify connection to 4200A (ping IP address)

### Parameters

All 66 parameters from the C example are supported as keyword arguments to `iv_sweep()`:

**Timing:**
- `pulse_width_gate/drain`, `rise_time_gate/drain`, `fall_time_gate/drain`, `delay_gate/drain`
- `period`, `meas_start_gate`, `meas_stop_gate`, `pulse_average`

**Voltages:**
- `ampl_v_gate`, `base_v_gate`
- `start_v_drain`, `stop_v_drain`, `step_v_drain`, `base_v_drain`

**Ranges:**
- `v_range_gate/drain` (5, 10, or 40V)
- `i_range_gate/drain` (current range in amps)
- `ltd_auto_curr_gate/drain` (limited auto-range, boolean)

**Load & Compensation:**
- `res_gate/drain` (load resistance, 1 to 1e6 ohms)
- `load_line_gate/drain` (enable LLEC, boolean)

**Thresholds:**
- `threshold_curr_gate/drain`, `threshold_volt_gate/drain`, `threshold_pwr_gate/drain`

**Channels & Mode:**
- `gate_ch`, `drain_ch` (1 or 2)
- `pmu_mode` (0=Simple fast, 1=Advanced with LLEC/thresholds)

**Optional SMU:**
- `smu_id` ("SMU1", "SMU2", etc., or None)
- `smu_v`, `smu_irange`, `smu_icomp`

See docstring for full parameter details and valid ranges.

