# Switchbox_GUI

## About
- Real-time graphing (multiple plots, live updates)
- Temperature measurement/manager ready (ITC/Lakeshore)
- LED control via PSU
- Bot messaging (Telegram) for remote prompts/updates
- Auto-saving data with device/sample folders and incrementing filenames
- Beep on instrument connect
- Sequential measurement across devices

## Current Multiplexers
- PySwitchbox: 100-device array (Raven’s creation), Arduino-controlled relay box
- Multiplexer: simple 1–10 selector (positive inner, negative outer) for basic routing

## Systems
### Smu (Keithleys)
- Keithley 2400 (SMU)
- Keithley 2401 (SMU)
- Keithley 4200A_smu (SMU)
- Keithley 4200A_pmu (PMU; waveform capture; in-progress integration)
- HP4140B (classic picoammeter/SMU)

### Temp Controllers
- TemperatureControllerManager abstraction (supports Lakeshore 335, Oxford ITC4)

### Power Supplies (LED control)
- Keithley 2220 (used for LED driving)

### Function Generators
- Siglent (triggered pulses)
- Moku Go (in the works)

## Measurement Types

- DC Triangle IV: Classic FS/PS/NS triangle sweep. Configurable by Sweep Mode (fixed step, fixed sweep rate, fixed voltage time), Sweep Type (FS/PS/NS), Step/Delay or rate/time.

- SMU Pulsed IV: One pulse per amplitude across a range; device returns to Vbase and a read is taken. Use when you want reduced self-heating compared with DC IV.

- SMU Fast Pulses: Pulse train at fixed amplitude and width; measure at Vbase after each pulse. Good for endurance-like stress.

- SMU Fast Hold: Hold a DC bias and sample current vs time (I–t). Useful for stress/recovery or quick retention checks.

- ISPP: Incremental Step Pulse Programming. Increase pulse amplitude stepwise until hitting a target current/resistance. Produces amplitude vs response curves.

- Pulse Width Sweep: Fixed amplitude, sweep pulse width; read at Vbase; width vs response.

- Threshold Search: Find Vset/Vreset using binary/gradient search with minimal pulses.

## Visuals (concept sketches)

- DC Triangle IV
```
V: /\\/\\
I: response vs V
```

- SMU Pulsed IV (Amplitude Sweep)
```
A: [A1 A2 A3 ...]
Pulse: |‾‾|   |‾‾|   |‾‾|
Read:   r1     r2     r3   at Vbase
Plot: A vs I_read
```

- SMU Fast Pulses
```
Pulse train: |‾| |‾| |‾| |‾| ... (fixed A, width)
Reads: after each at Vbase
```

- SMU Fast Hold
```
V(t) = Vhold (flat)
I(t) sampled regularly
```

- ISPP (Amplitude Ramp to Target)
```
Amps:  0.2  0.3  0.4  0.5 ...
Iread: i1   i2   i3*           (* ≥ target)
Plot: Amplitude vs I_read
```

- Pulse Width Sweep (Fixed Amplitude)
```
Widths (ms):  1   2   5   10 ...
I_read:       i1  i2  i3  i4
Plot: width vs I_read
```

- Threshold Search (Binary Search on V)
```
Range: [Vlow --------------------- Vhigh]
Test mid -> I(mid) ? target -> shrink range toward threshold
Repeat until |Vhigh - Vlow| small
```

## Safety & Limits

- SMU-specific minimum pulse width enforced via SMULimits. Defaults are set per model (e.g., 2400/2401 ≥ 1 ms).
- Planned: optional guard to abort on excessive current jump between samples.

## Timing and "Fast" Pulses

SMU-driven pulses are limited by instrument command latency and OS scheduling; they are appropriate for millisecond-scale pulses, not microseconds.

- SMU limits: `SMULimits.min_pulse_width_ms` enforces device-specific minima (e.g., 2400/2401 ≥ 1 ms). Sub-ms accuracy requires a PMU.
- Implementation details:
  - `MeasurementService.run_pulse_measurement` sets the pulse voltage, then busy-waits the pulse duration using ~1 ms sleeps, returns to Vbase, waits ~2 ms for settling, then reads.
  - Inter-pulse delay is user-configurable; "Max speed" can set it to 0, bounded by device limits.
- Python/OS timing: `time.sleep(0.001)` is not hard real-time; actual resolution and jitter depend on the OS scheduler (on Windows typically ~1 ms best case). Expect a few ms of timing uncertainty on SMU pulses.
- Recommendation: For sub-ms or waveform-accurate pulses, use the PMU flows (see PMU_Testing_GUI and PMU_* methods in `measurement_service.py`).

## Specific Measurements
### Volatile
- Transient Decay: single pulse then sample I(t) at Vread (extract τ / power-law).
  Sketch: `|‾‾|____` then hold Vread → I(t) decays.
- PPF: two identical pulses separated by Δt; PPF index vs Δt.
  Sketch: `|‾‾|__Δt__|‾‾|` → measure I1 and I2 @ Vread; PPF=(I2−I1)/|I1|.
- STDP: pre/post pulses with Δt (±); Δw vs Δt curve.
- SRDP: trains at different frequencies; steady-state/current gain vs rate.
- Potentiation/Depression: alternating +/− short pulses; immediate and post-delay reads; volatility ratio.
- Frequency Response: sweep pulse frequency (fixed width/amplitude); response vs frequency.
- Dynamic Threshold (volatile): minimal pulse amplitude/width that elicits transient change (binary/gradient).
- Bias-dependent Volatility: repeat transients at multiple Vread; map decay constants vs bias.
- Temperature-dependent Volatility: repeat at several temperatures; Arrhenius for decay time (future).
- Noise/RTN: low-bias I(t) segments for PSD/variance.

### Nonvolatile
- (reserved for future: long retention, endurance, MLC program/verify, half-select disturb, etc.)

## Custom Sweeps

- Each sweep can set a `measurement type` within the GUI. For custom JSON, an `excitation` key enables pulse modes (examples provided in `Json_Files/Custom_Sweeps.json`).

## Signal Messaging
- Optional Telegram bot integration to drive interactive flows (start/continue tests, send plots/images).

## PMU Testing
- In the works. See `Equipment_Classes/SMU/Keithley4200A.py` (PMU helpers) and `PMU_Testing_GUI.py`.

## Code Map (where to look)

- Volatile Tests (GUI: More Tests → Volatile)
  - Transient Decay: single pulse then I(t) at Vread; saves time-series.
    Sketch:
    ```
    |‾‾|____  then hold Vread → I(t) decays
    ```
  - PPF (Paired-Pulse Facilitation): two pulses with Δt; PPF index vs Δt.
    ```
    |‾‾|__Δt__|‾‾| → measure I1 and I2 @ Vread; PPF=(I2−I1)/|I1|
    ```
  - STDP: pre/post with Δt (±); Δw vs Δt.
    ```
    pre at t0, post at t0+Δt (or reversed), measure Δw = (I_after−I0)/|I0|
    ```
  - SRDP: frequency trains; steady-state vs rate (Hz).
    ```
    train at f=1,5,10… → measure I_ss
    ```
  - Potentiation/Depression: alternate +/− pulses; immediate/post reads; volatility ratio.
  - Frequency Response: average read after pulses at each frequency.
  - Bias-dependent Decay: run multiple transients at different Vread; concatenated time series.
  - Noise/RTN: low-bias I(t) capture for noise analysis.

- Core service (measurement logic): `measurement_service.py`
  - DC Triangle IV: `run_iv_sweep(...)`
  - SMU Pulsed IV: `run_pulse_measurement(...)` (single/sequence), `run_pulsed_iv_sweep(...)` (amplitude sweep)
  - SMU Fast Hold: `run_dc_capture(...)`
  - ISPP: `run_ispp(...)`
  - Pulse Width Sweep: `run_pulse_width_sweep(...)`
  - Threshold Search: `run_threshold_search(...)`

- GUI wiring and controls: `Measurement_GUI.py`
  - More Tests popup (Volatile): `advanced_tests_gui.py`
  - Measurement Type dropdown and dynamic panels: `create_sweep_parameters(...)`
  - Execution branching and saving: `start_measurement(...)` (branches on Measurement Type)

## Notes

- PMU-based measurements are available separately (see PMU_Testing_GUI) for accurate waveform capture.



