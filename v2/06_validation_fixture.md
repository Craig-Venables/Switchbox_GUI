# 06 — 10 kOhm validation fixture

A known 10 kOhm resistor gives every AI-built module a simple correct answer:
R = V / I = 10 kOhm. Any deviation points to a bug in the waveform, the
measurement window, the range, or the `GP` slots, not to device physics.
Safety rules: [00_safety.md](00_safety.md).

## The resistor

- 10 kOhm, 0.1% to 1% metal film, at least 0.25 W. At the 1 V limit it
  dissipates 0.1 mW, so heating is negligible.
- Measure it once with a calibrated multimeter and record the value in
  `v2/config.toml` as `r_nominal`. Pass criteria use this value.
- Mount it in a small shielded box with the right connectors (triax for SMU,
  SMA for the RPM outputs). Keep leads short; long unshielded leads add
  capacitance that shows up in fast PMU edges.
- Label the box "V2 FIXTURE" so it is never confused with a sample.

## Wiring

### SMU

```text
SMU1 Force ──── 10 kΩ ──── GNDU (or SMU2 Force held at 0 V)
```

### PMU (dual channel, matching the existing modules)

```text
PMU1 CH1 (RPM1 output, force) ──── 10 kΩ ──── PMU1 CH2 (RPM2 output, measure, held at 0 V)
```

This matches the dual-channel setup in
[`C_Code_with_python_scripts/README.md`](../Equipment/SMU_AND_PMU/4200A/C_Code_with_python_scripts/README.md):
CH1 applies the voltage, CH2 measures the current.

If the probe station has both SMU and RPM paths, use the RPM's internal
switching (`rpm_config`) rather than moving cables between SMU and PMU tests,
and record which path each test uses.

## Fixture interlock

Before hardware runs (details in [00_safety.md](00_safety.md)):

- `EX A_Check_Connection smu_check_connection(...)` with bias 0.1 V, current
  limit 100 µA, buffer size 8.
- Expected current 10 µA. Require R within ±5% of `r_nominal`.
- Fail locks hardware tools until a human clears it.

## Pass criteria for `validate_resistor`

### SMU modules

| Check | Pass |
|---|---|
| Resistance at each point with \|V\| ≥ 0.1 V | Within ±2% of `r_nominal` |
| Linearity | Linear fit of I against V has R² ≥ 0.999 and intercept below 1% of max current |
| Polarity | Sign of I matches sign of V |
| Compliance | No point at the current limit |
| Array lengths | `GP` arrays have the expected length; no trailing zeros inside the expected range |

### PMU modules

| Check | Pass |
|---|---|
| Resistance per read | Within ±5% of `r_nominal`, using the **measured** probe voltage, not the requested `measV` |
| Range use | `analyze_pmu_i_range_usage(i_range, currents, read_voltage=...)` reports no saturation and no under-range |
| Firmware cap | No value equal to the cap `1e4 / IRange` (that means current was too small to measure) |
| Timestamps | `PulseTimes` strictly increasing; spacing matches the requested timing within 5% |
| Array lengths | `setV`, `setI`, `PulseTimes` match the module's expected probe count |
| Return code | `EX` returned 0; any negative code is explained with `_PMU_EX_ERROR_HINTS` |

### Choosing PMU settings for 10 kOhm

| Read voltage | Current | Good I-range | Use of range |
|---|---|---|---|
| 0.3 V | 30 µA | 100 µA | 30% |
| 0.5 V | 50 µA | 100 µA | 50% |
| 1.0 V | 100 µA | 1 mA | 10% |

Do not use 1 V on the 100 µA range: 100 µA is exactly full scale and will
saturate.

## Report format

`validate_resistor` returns:

```json
{
  "pass": false,
  "module": "V2_Readtrain/v2_readtrain",
  "r_nominal": 10003.1,
  "r_measured": {"median": 10512.0, "min": 10488.0, "max": 10540.0},
  "failed_checks": ["resistance_within_tolerance"],
  "notes": ["Median 5.1% high; check measurement window and CH2 range"],
  "data_file": "audit/2026-11-23/run_0042.json"
}
```

The raw `GP` arrays are saved so a human can review them.

## Limits of this fixture

A resistor checks timing, ranges, data handling and arithmetic. It cannot
check switching behaviour (SET/RESET thresholds, retention). Those need a
real device, which stays outside the AI's reach under these rules. A human
moves to real devices only after the module has passed here, with the
Switchbox_GUI's normal safeguards.
