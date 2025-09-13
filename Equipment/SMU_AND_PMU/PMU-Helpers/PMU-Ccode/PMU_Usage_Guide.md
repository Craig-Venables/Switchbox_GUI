## 4200A PMU Usage Guide (Wiring, Triggers, and High‑R Measurements)

### Hardware mapping
- PMU card: `PMU1` (one card) provides two channels: `CH1`, `CH2`.
- RPMs: `RPM1` → `PMU1-CH1` (Force HI/LO, Sense HI/LO), `RPM2` → `PMU1-CH2`.
- Rear panel: `TRIG IN` / `TRIG OUT` are TTL logic lines (not DUT connections).

### Typical wiring (Figure 11 topology)
- Two‑terminal DUT sits between `RPM1 (CH1)` and `RPM2 (CH2)`.
- Force and Sense are strapped per RPM (Kelvin). For best accuracy, strap at the DUT pads if possible.

### One vs two channels
- One channel (recommended for simple 2‑T R): CH1 force/sense/measure; CH2 held at 0 V as a quiet return.
- Two channels (useful cases):
  - Quiet return: keep CH2 at 0 V to avoid re‑ranging artifacts.
  - Auxiliary stimulus: bias/measure on CH1, perturb on CH2 (electrical pulse or TTL pattern).
  - Differential drive: split ± levels on CH1/CH2 to reduce common‑mode.
  - Diagnostics: read CH2 voltage to check lead drops/leakage.
- Cross‑channel sensing (force CH1, sense CH2) is not a calibrated path; avoid for metrology.

### Trigger I/O behavior
- TRIG OUT: TTL pulse per PMU pulse when enabled. Some units emit a short strobe train at arm/start.
- TRIG IN source modes:
  - 0: software (no external edge required)
  - 1/2: external initial‑only (one edge starts sequence)
  - 3/4: external per‑pulse (one edge per PMU pulse)
  - 5: internal trig bus
- Clean ways to use:
  - Fire external device per pulse: enable TRIG OUT and use its TTL edges.
  - Single external start: disable TRIG OUT, set source 1/2, send one external 0–5 V pulse.
- If TRIG OUT is looped into TRIG IN, the PMU self‑triggers per pulse (per‑pulse mode).

### Fast pulse limits (ns vs µs)
- The PMU can generate fast edges, but the measurement chain (ADC integration, LPT timing, cabling) sets a practical minimum useful pulse width (often ~1–5 µs in remote/measure modes). Sub‑µs pulses are typically clipped or not meaningfully measurable.
- Verify with a scope on RPM HI or TRIG OUT; expect rounding/clamping below the hardware/firmware minimums.

### High‑resistance (memristive) best practices
- Settling: width ≥ 5–10·τ, where τ ≈ R·C (fixture/device). For 100 kΩ with 50–200 pF, width ≈ 50–500 µs.
- Measure late: set measurement window to the last 10–20% of the pulse (e.g., 80–95%).
- Ranges: choose current range with headroom (e.g., 10 µA expected → 20 µA range). Keep voltage range just above setpoint.
- Minimization: Kelvin sense at DUT pads, short leads, clean/dry fixture, guard where possible.

### Patterns we support in code
- Constant bias + auxiliary pulse (perturb‑and‑observe):
  - CH1: bias/probe; CH2: pulse; fetch only CH1 waveform (observe response + relaxation).
  - Helper: `measure_bias_with_aux_pulse(bias_v, aux_pulse_v, width_s, period_s, ...)`.
- Single‑channel set‑and‑measure:
  - Helper: `measure_at_voltage(amplitude_v, width_s, period_s, meas_start_pct, meas_stop_pct, ...)`.
- High‑R reliability (median over shots):
  - Helper: `measure_resistance(amplitude_v, expected_res_ohm, shots, ...)`.
  - Sweep: `measure_resistance_sweep(voltages, expected_res_ohm, shots)`.

### Example snippets
```python
# One‑channel measurement with late window
df = pmu.measure_at_voltage(
  amplitude_v=1.0,
  width_s=100e-6, period_s=300e-6,
  meas_start_pct=0.85, meas_stop_pct=0.98,
  source_channel=1, force_fixed_ranges=True,
  v_meas_range=2.0, i_meas_range=20e-6,
  num_pulses=1
)

# High‑R (100 kΩ) summary
summary, raw = pmu.measure_resistance(amplitude_v=1.0, expected_res_ohm=100_000.0, shots=7)

# Bias + aux pulse (probe CH1, pulse CH2)
df = pmu.measure_bias_with_aux_pulse(
  bias_v=0.2, aux_pulse_v=5.0, width_s=10e-6, period_s=50e-6,
  bias_channel=1, aux_channel=2, v_meas_range=2.0, i_meas_range=200e-6,
  start_pct=0.0, stop_pct=1.0
)
```

### Laser triggering (summary)
- Prefer TRIG OUT → laser trigger input (TTL) while both channels stay on the DUT.
- If a specific gate pulse is required, disconnect CH2 from the DUT and use CH2 → laser trigger; otherwise keep CH2 on the DUT and use TRIG OUT.

### Quick do/don’t
- Do: measure late, fix ranges, keep CH2 quiet when not used, strap sense at DUT pads.
- Don’t: cross‑sense between channels for metrology, or terminate in 50 Ω on high‑R DUTs (will swamp the DUT).

---

## Measurement recipes (what to use and when)

### 1) Simple one‑channel measurement (2‑terminal R)
When your DUT dynamics are slow/moderate; use a single channel to source and measure.

Use when:
- Measuring a resistor/slow memristor state; no auxiliary perturbation needed.

How:
```python
df = pmu.measure_at_voltage(
  amplitude_v=1.0, width_s=100e-6, period_s=300e-6,
  meas_start_pct=0.85, meas_stop_pct=0.98,
  source_channel=1, hold_other_at_zero=True,
  force_fixed_ranges=True, v_meas_range=2.0, i_meas_range=20e-6,
  num_pulses=1
)
```

Notes:
- Keep CH2 at 0 V (quiet return). Fix ranges; avoid re‑range mid‑pulse.

### 2) High‑R reliability (late window + multiple shots)
When R·C is large; prioritize accuracy over speed.

Use when:
- 10 kΩ–MΩ devices; fixture C ≈ 50–200 pF; need stable, repeatable R.

How:
```python
summary, raw = pmu.measure_resistance(
  amplitude_v=1.0, expected_res_ohm=100_000.0,
  shots=7, width_s=300e-6, period_s=1e-3
)
print(summary)
```

Notes:
- Uses late sampling window under the hood and a robust median across shots.

### 3) Perturb‑and‑observe: bias on CH1, pulse on CH2
Observe device response and relaxation while one channel applies an auxiliary pulse.

Use when:
- You want to bias (or 0 V) and see the effect of a short electrical pulse.

How:
```python
df = pmu.measure_bias_with_aux_pulse(
  bias_v=0.2,           # CH1 probe bias (0.0 if you want unbiased)
  aux_pulse_v=5.0,      # CH2 pulse amplitude
  width_s=10e-6, period_s=50e-6,
  bias_channel=1, aux_channel=2,
  v_meas_range=2.0, i_meas_range=200e-6,
  start_pct=0.0, stop_pct=1.0
)
```

Notes:
- We fetch CH1 only; CH2 is only the perturbation. Keep CH1 ranges fixed and with headroom.

### 4) Dual‑node observation (both channels read)
Sometimes you need both node voltages to compute DUT voltage V_DUT = V_CH1 − V_CH2.

Use when:
- Diagnosing lead drops/ground bounce; studying both node transients.

How (pattern):
1) Run the desired pulse sequence (e.g., with `measure_at_voltage` or bias+aux).
2) Then call `pulse_fetch` for CH1 and CH2 separately and time‑align arrays in your analysis.

We can add a convenience `fetch_both=True` option on request to return a merged DataFrame.

### 5) Triggered sequences
Per‑pulse TTL for external gear, or one external edge to start a burst.

Use when:
- Firing external instruments in sync, or arming PMU from an external trigger.

How:
```python
# Per‑pulse TTL to TRIG OUT (laser, camera, etc.)
pmu.set_trigger_output(True)
pmu.set_trigger_source(0)  # software start
df = pmu.measure_at_voltage(amplitude_v=1.0, width_s=10e-6, period_s=100e-6, num_pulses=10)

# External initial‑only to start sequence
df = pmu.measure_at_voltage(amplitude_v=1.0, width_s=10e-6, period_s=100e-6,
                            num_pulses=10, trig_source=1, trig_polarity=1, trig_output=False)
```

Notes:
- Avoid looping TRIG OUT into TRIG IN unless you intend self‑triggering per pulse.

### Choosing ranges (cheat sheet)
- Expected current I ≈ V/R. Pick `i_meas_range` ≈ 5–10× I for headroom (not at limit, not 1000×).
- Voltage range just above setpoint (e.g., 1 V → 2 V range).
- Fix ranges during shots (use `force_fixed_ranges=True`) to avoid mid‑transient re‑range.

