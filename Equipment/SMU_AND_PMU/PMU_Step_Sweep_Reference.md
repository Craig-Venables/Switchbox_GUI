# Keithley 4200A PMU: Step vs Sweep (LPT)

This note explains how the PMU LPT calls `pulse_sweep_linear` and `pulse_step_linear` work, and how to choose the right Step/Sweep type for experiments.

## Sweep vs. Step

- Sweep (`pulse_sweep_linear`): defines the channel and setpoint that actively changes during the test (the inner loop).
  - Example: sweep the pulse amplitude from 0 → 5 V in 1 V steps → pulses at 0,1,2,3,4,5 V on that channel.
- Step (`pulse_step_linear`): defines a second channel that holds a fixed value while the sweep runs, then steps to the next value between sweeps (the outer loop).
  - You cannot use step without at least one sweep. Think of “Step” as the bias condition applied per-sweep.

Example (2‑channel):
- CH1: sweep amplitude 0–4 V (9 points)
- CH2: step amplitude 1–2.5 V (4 points)
- Total points = 9 (sweep) × 4 (steps) = 36

In short: sweep scans within a step; step holds a bias and increments after the sweep finishes.

## Step/Sweep Types (what you can vary)

These enums tell the PMU what parameter to vary during a sweep/step:

- `PULSE_AMPLITUDE_SP` – vary pulse high level (amplitude)
- `PULSE_BASE_SP` – vary base (low) level
- `PULSE_DC_SP` – vary DC offset level
- `PULSE_PERIOD_SP` – vary pulse period (affects duty cycle)
- `PULSE_RISE_SP` / `PULSE_FALL_SP` – vary edge times
- `PULSE_WIDTH_SP` – vary pulse width (time at high level)
- `PULSE_DUAL_*` – dual (up-then-down) versions for hysteresis-style sweeps

Use a SweepType for `pulse_sweep_linear` (inner loop) and a StepType for `pulse_step_linear` (outer loop). You can combine different types across channels (e.g., sweep amplitude on CH1 while stepping base on CH2).

## Practical applications

- Memristor amplitude studies: `PULSE_AMPLITUDE_SP` sweep at fixed base.
- Bias dependence: add a step on another channel (e.g., step amplitude/base/offset) and sweep on the primary channel.
- Pulse width studies: `PULSE_WIDTH_SP` (endurance/retention vs width).
- Duty cycle studies: `PULSE_PERIOD_SP` (thermal/self‑heating via duty).
- Asymmetric pulsing: `PULSE_BASE_SP` to shift baseline.
- Edge‑rate sensitivity: `PULSE_RISE_SP` / `PULSE_FALL_SP`.
- Hysteresis/recovery: `PULSE_DUAL_*` to go up then back down in one run.

## TL;DR

- Use sweep for the variable you are studying (e.g., amplitude for memristors).
- Add a step if you need an outer‑loop bias (e.g., different gate biases).
- Choose the `*_SP` type that matches the parameter you want to vary (amplitude, width, period, baseline, edges, etc.).

## Notes

- Dual‑sweep (`PULSE_DUAL_*`) emits up and then down in one test; useful for capturing hysteresis.
- Only a sweep defines time‑varying setpoints during the acquisition; steps change between sweeps.
- See `Equipment/SMU_AND_PMU/Keithley4200A.py` for usage examples where `pulse_sweep_linear` and `pulse_step_linear` are called.
