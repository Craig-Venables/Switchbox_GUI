# Lab Smoke-Test Checklist

This guide walks through validating the refactored measurement GUI once you have
hardware access.  It assumes the refactor is already merged and the application
launches without errors on the development machine.

---

## 1. Pre-Requisites
- Install optional dependencies:
  - `pyvisa`, `pyvisa-py`
  - `gpib-ctypes` (for legacy GPIB)
  - Instrument-specific drivers/firmware utilities
- Confirm VISA aliases / GPIB addresses (NI-MAX or `pyvisa` list_resources).
- Have Telegram bot token/chat ID handy if messaging integration is required.

## 2. Instrument Bring-Up
- Connect Keithley SMU, PSU, temperature controller, optical sources.
- Power up hardware; verify they enumerate correctly via VISA.
- Launch the GUI; use the connection panel to attach each instrument.
- Watch console/log output for missing drivers or credential warnings.

## 3. Standard DC Measurement
- Select a single test device.
- Run the standard IV sweep (no special modes).
- Confirm:
  - Live plots update (IV, log IV, VI, etc.).
  - Data directory created with expected text files/plots.
  - Summary plot saved (`All_graphs_IV/LOG`, combined plot).

## 4. Sequential Measurements
- Configure `Iv Sweep` mode with a small loop count and delay.
- Start sequential run; verify loop counter and delay obeyed.
- Switch to `Single Avg Measure`; ensure averaged data saves and log files append.

## 5. Custom Plans
- Load a known JSON plan (e.g., `Debug_testing_sweep`).
- Run custom measurement; confirm:
  - Per-sweep data saved.
  - Plan respects pause/emergency stop flags.
  - Summary plots include custom run results.

## 6. Special & Pulsed Modes
- Exercise at least one path from each runner:
  - `special_runner`: ISPP, pulse-width sweep, threshold search, transient.
  - `pulsed_runner`: Pulsed IV (`<1.5V`), fast pulses, fast hold.
- Verify compliance limits, timing parameters, and data exports.

## 7. Manual Workers
- Start manual endurance with LED power set; confirm LED toggles and endurance plot updates.
- Run manual retention; verify retention plot updates and data saving.

## 8. Real-Time Plotting & Export
- Use the “Plot” menu:
  - Open live plotter window; ensure updates mirror main plots.
  - Export/save plot images without errors.
- Trigger `Show Last Sweeps`; confirm the All Sweeps window raises with the latest sweep.

## 9. Telegram Integration (optional)
- Enable messaging; update credentials if needed.
- Run a measurement:
  - Expect start/end messages, summary image upload.
  - Test interactive prompts (if enabled) and ensure GUI handles responses.

## 10. Error Handling
- Simulate hardware disconnect or invalid settings mid-run.
- Confirm GUI surfaces errors without crashing and resets stop flags correctly.

## 11. Wrap-Up
- Run `py -3 -m pytest tests` to ensure unit tests remain green post-session.
- Update `Documents/GUI_REFACTORING_PLAN.md` smoke-test table with outcomes.
- Record bugs/regressions discovered, including missing safeguards or desired improvements for the backlog.

---

Keep this checklist in the repo for future validation sessions.  Extend it with
hardware-specific nuances as new instruments or measurement types are added.


