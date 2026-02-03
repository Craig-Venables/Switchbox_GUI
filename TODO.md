# TODO – Switchbox GUI Project

Tracked items for future development. See also issue tracker and `.cursor/plans/` for
larger refactoring plans.

---

## Feature Requests

### Laser & Device Positioning

- **Laser GUI:** Build specific laser GUI that homes the laser, then lets user select a
  device to move to. Need to ensure correct position verification.
- **Pulse with laser:** Change pulse with laser C program update on 4200.

### Plotting Improvements

- **Current value highlight:** Make the current value red when plotting so it's visible
  when tracing.
- **Quick view update:** The quick view orange above the graphs needs updating with the
  current device's voltage and loop number.

### Forming

- **Forming setup:** Allow choosing a current limit; send pulses until the device "forms"
  (form read form read etc). Post-form then runs measurements.

### Analysis Tab

- **Reclassify with new weights:** Add ability to run through all data and reclassify
  with new weights (memristive, capacitive, etc.).
- **Analysis overhaul:** Need to overhaul the analysis stuff – we keep running the
  "memristive" classification all the time.
- **Memristive news view:** Something to view the "memristive news" of the samples and
  quick look.

### Conditional Testing

- **Conditional testing:** Doesn't work properly – seemingly doesn't save the data, but
  does run the measurement.
- **Switchbox routing:** When the switchbox is used, devices C and F 1–5 need to not be
  routed to (no auto pins for this location).

---

## Notes

- **Temp GUI:** Placeholder for future temperature-specific UI.
- Items migrated from `main.py` during Phase 1 refactoring (see codebase refactoring plan).
