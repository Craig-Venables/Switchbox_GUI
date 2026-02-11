# Optical timing calibration scripts

Scripts to **home in** on laser sync and pulse width from saved optical pulse-test results.

## analyze_optical_result.py

Analyzes a saved Pulse Testing `.txt` file (tab-delimited, with `Timestamp(s)` and `Resistance(Ohm)` columns) and reports:

- **First pulse time** – when the first resistance drop occurs (photodiode response).
- **Suggested Laser sync offset (s)** – value to set in the GUI so the first pulse appears at a desired time (e.g. 1.0 s).
- **Observed pulse width(s)** – start, end, and width of each resistance drop (to check 500 ms vs 250 ms, etc.).

### Usage

From the **repo root**:

```bash
python tools/optical_timing_calibration/analyze_optical_result.py "path/to/2-Optical_Laser_Pattern_Continuous_Read-3.00mW-20260210_172239.txt"
```

With options:

```bash
# Desired first-pulse time 1.0 s (default)
python tools/optical_timing_calibration/analyze_optical_result.py result.txt --desired 1.0

# Stricter drop detection (15% of baseline)
python tools/optical_timing_calibration/analyze_optical_result.py result.txt --baseline-fraction 0.15

# More baseline samples
python tools/optical_timing_calibration/analyze_optical_result.py result.txt --min-baseline 20
```

### Workflow

1. Run an optical test with **Laser Start Delay = 0** and **Laser sync offset = 0**, then save the result.
2. Run this script on the saved `.txt` file.
3. Set **Laser sync offset (s)** in the GUI to the suggested value; re-run the test to confirm the first pulse is at the desired time.
4. Use the **Observed pulse width(s)** to check whether pulses are the requested duration (e.g. 500 ms or 1 s); if they are shorter, adjust hardware or the on-time parameter.

## Unit tests (repo root)

```bash
pytest tests/test_optical_timing.py -v
```

These tests check:

- `_optical_on_to_seconds` (ms vs seconds).
- `suggest_laser_sync_offset_s` on synthetic data.
- Pulse width estimation from synthetic resistance traces.
