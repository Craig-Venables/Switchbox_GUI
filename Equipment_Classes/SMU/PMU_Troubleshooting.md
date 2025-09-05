## PMU Troubleshooting Notes

### Symptom
- PMU current readings return extremely large sentinel values (e.g., 1e22 A) for all samples.

### Cause
- The PMU measurement was effectively out-of-range/invalid for the default auto-range and timing. Some LPT/SweepMe server configurations encode invalid samples as huge numbers instead of NaN.

### Fix Implemented
- Added a dual-channel PMU helper that can optionally force fixed measurement ranges before a pulse. This avoids bogus sentinel values and yields valid readings.
- Implemented per-channel status decoding and printed summaries to quickly identify overflow/invalid states.
- Masked clearly invalid magnitudes (|I| > 1e10 or non-finite) to NaN before computing resistance.

### How to Use
```python
pmu = Keithley4200A_PMUDualChannel("<ip>:8888|PMU1")
df = pmu.measure_at_voltage(
    amplitude_v=0.5,
    base_v=0.0,
    width_s=10e-6,
    period_s=20e-6,
    source_channel=1,
    force_fixed_ranges=True,   # key change
    v_meas_range=2.0,
    i_meas_range=1e-3,
)
print(df.head())
pmu.close()
```

### Notes
- If statuses still indicate overflow, increase `i_meas_range` (e.g., 1e-2) or reduce amplitude/width.
- The non-source PMU channel is held at 0 V to match the dual-channel wiring described in the manual.

## Trigger I/O behavior and gotchas

### Overview
- TRIG OUT (rear BNC): TTL-like 0–5 V output. When enabled, the PMU asserts a marker pulse per PMU pulse. Some firmware may also emit a short pulse train at arm/start.
- TRIG IN (rear BNC): TTL-like 0–5 V input. The trigger source determines how it’s used:
  - 0: software (no external requirement)
  - 1/2: external initial-only (one edge starts the sequence)
  - 3/4: external per-pulse (one edge required per PMU pulse)
  - 5: internal trig bus

### Common observations
- “Why do I see 100+ tiny pulses at start?”
  - With TRIG OUT enabled, some units output a brief strobe/train when armed/executed. Disable TRIG OUT to remove it. Time-stamp acquisition on/off may not affect this on all systems.
- “Why do I get a trigger every measurement?”
  - By design. TRIG OUT emits a marker per PMU pulse when enabled.
- “It runs even when TRIG IN is disconnected.”
  - If the trigger source is 0 (software), execution starts immediately. For external-only behavior, set source to 1/2 (initial-only) or 3/4 (per-pulse).

### Recommended setups
- Single clean edge per PMU pulse (to fire external device):
  - Set trigger source to 0 (software) so PMU controls timing.
  - Enable TRIG OUT. Use its per‑pulse edges to drive the device.
  - Do NOT loop TRIG OUT to TRIG IN unless you intend self-triggering.

- Single external start edge (no per‑pulse triggers):
  - Disable TRIG OUT.
  - Set trigger source to 1 or 2 (external initial‑only).
  - Arm, then apply one 0–5 V pulse to TRIG IN to start the burst.

### Tips
- Scope with DC coupling, 1 MΩ. Use fast timebase (~1 µs/div) to see short edges.
- Always set trigger source/output before `pulse_exec`.

## High-resistance (memristive) measurement tips
- Increase pulse width to allow RC settling: τ ≈ R·C. Use width ≈ 5–10·τ.
- Measure late in the pulse (e.g., 80–98% window) to avoid transient.
- Prefer true Kelvin on one channel (CH1) instead of using CH2 as return.
- Keep fixture clean/dry; minimize leakage and stray C.
- Choose ranges by expected current (e.g., 10 µA → 20 µA range).


