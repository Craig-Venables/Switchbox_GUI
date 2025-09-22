## Optical Excitation Integration – Remaining Work

Goal: finalize a safe, configurable optical layer (LED/Laser) that is robust in production and easy to test. We’ve implemented the core interface, adapters, factory, config schema, and GUI/service wiring.

### Must-do (next passes)
- Emergency OFF control in GUI: add a button that calls `optical.emergency_stop()` with PSU fallback; visible at all times.
- Status indicator: show current optical mode and selection (e.g., "Optical: LED via PSU" or "Laser: Oxxius @ 405 nm").
- Hide/disable PSU UI when optical type is Laser; don’t prompt PSU connect for laser-only systems.
- Ensure all measurement branches always turn optical OFF on completion/abort.

### Safety & robustness
- Add soft ramping and limit enforcement for `set_level` based on `limits` in config (rate and min/max clamps).
- Watchdog: ensure best-effort OFF on exceptions/abort (wrap lifecycles).
- Device safety interlocks: guard against enabling Laser without recent `initialize()` and interlock checks.

### Config & validation
- Validate `Json_Files/system_configs.json` optical blocks using `pydantic` or `jsonschema`. Provide clear error messages.
- Optional: auto-detect Oxxius serial ports and sanity-check connectivity on system selection.

### Testing & simulation
- Add `SimulationExcitation` to a dev test system; unit tests for lifecycle (init→enable→level→off), sequencing, and cleanup.
- Smoke tests on real LED and Laser systems; verify units (mA vs mW) and clamp behavior.

### UX & logging
- Include optical metadata in saved files (we now append `-LASER<level><unit>` to filenames when Laser used). Also add a header line with optical mode and settings.
- Add structured logging around optical actions (enable/disable/level), with rotating file handler.

### Future enhancements
- Optical state machine with timeouts and explicit states (OFF→INIT→ARMED→ON→OFF).
- Calibration support: LED current↔mW profiles per channel; store in `calibration.json` and apply when user sets mW.
- Capability detection: guard unsupported ops (e.g., wavelength changes on fixed lasers) with clear messages.





