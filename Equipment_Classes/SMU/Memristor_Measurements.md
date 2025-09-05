## Memristor Measurements API

This layer wraps `Keithley4200A_PMUDualChannel` with friendly methods for common memristor tests. All methods return a dict with:
- `summary`: DataFrame with key results you should use
- `raw_ch1`: CH1 waveform/rows (if applicable)
- `raw_ch2`: CH2 waveform/rows (if applicable)

### Class: `MemristorMeasurements(pmu)`
`pmu` is an instance of `Keithley4200A_PMUDualChannel`.

---

### pulse_iv_sweep(levels, width_s, period_s, source_channel=1, v_meas_range=2.0, i_meas_range=20e-6, meas_start_pct=0.85, meas_stop_pct=0.98) -> dict
- Purpose: Quasi‑static IV at a small set of voltages. Uses late-window sampling and a robust median per step.
- Use the `summary` DataFrame (columns: `Level (V)`, `Vmed (V)`, `Imed (A)`, `Rmed (Ohm)`).
- `raw_ch1` contains all CH1 samples.

Example:
```python
wrap = MemristorMeasurements(pmu)
piv = wrap.pulse_iv_sweep([0.0, 0.1, 0.2, 0.5, 1.0], width_s=200e-6, period_s=500e-6)
print(piv["summary"])
```

---

### pulse_width_sweep(voltage_v, widths_s, period_factor=3.0, ...) -> dict
- Purpose: Same voltage, sweep pulse width to study settling/relaxation impact.
- `summary` has `Width (s)`, `Vmed (V)`, `Imed (A)`, `Rmed (Ohm)`.

Example:
```python
pws = wrap.pulse_width_sweep(voltage_v=0.5, widths_s=[50e-6, 100e-6, 200e-6, 500e-6])
print(pws["summary"])
```

---

### fast_read(read_v=0.2, duration_pulses=50, width_s=50e-6, period_s=100e-6, ...) -> dict
- Purpose: Read as fast as the PMU settings allow at a small bias. Captures multiple pulses in one run.
- `raw_ch1` contains the continuous CH1 stream across the specified pulses.
- Use a small `i_meas_range` with headroom for best SNR (e.g., 200 µA for ~tens of µA currents).

Example:
```python
fr = wrap.fast_read(read_v=0.2, duration_pulses=50, width_s=50e-6, period_s=100e-6)
print(fr["raw_ch1"].head())
```

---

### perturb_measure(bias_v, pulse_v, width_s, period_s, delay_s=5e-6, num_pulses=3, v_meas_range=2.0, i_meas_range=200e-6, fetch_both=True) -> dict
- Purpose: Bias/probe on CH1 and pulse on CH2; capture CH1 (and optionally CH2) waveforms. Ideal for perturb‑and‑relax studies.
- `raw_ch1` is the primary dataset to analyze device behavior.
- `raw_ch2` shows the applied pulse.
- You can compute `V_DUT ≈ V_CH1 − V_CH2` from the two datasets.

Example:
```python
pr = wrap.perturb_measure(bias_v=0.2, pulse_v=5.0, width_s=10e-6, period_s=50e-6,
                          delay_s=5e-6, num_pulses=3, fetch_both=True)
print(pr["raw_ch1"].head())
print(pr["raw_ch2"].head())
```

---

### Notes and guidance
- Always choose `i_meas_range` ≈ 5–10× expected current for headroom; avoid clipping.
- For high‑R devices, use longer widths (≥5–10× R·C) and measure late in the pulse.
- Keep ranges fixed during the shot to prevent re‑ranging artifacts.
- Use CH2 as a quiet return at 0 V unless you are actively pulsing with it.

