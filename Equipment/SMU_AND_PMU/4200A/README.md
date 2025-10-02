# PMU C Example Translations

Python versions of Keithley's official C examples.

## Files

- **`simple_10ns_pulse.py`** - Basic continuous pulse generation
- **`segarb_example.py`** - Segment ARB multi-level waveforms

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

