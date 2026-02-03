# Archive

This folder contains legacy and deprecated code that has been moved out of the main
codebase during refactoring. **No production code depends on these modules.**

## Contents

### Switchbox_Data_Analysis_and_Graphing

- **Origin:** `Helpers/Switchbox_Data_Analysis_and_Graphing - Copy/`
- **Archived:** Phase 1 refactoring
- **Description:** Older copy of data analysis and graphing utilities. Functionality
  has been superseded by:
  - `Helpers.Analysis` (core sweep analysis, aggregators)
  - `Helpers.IV_Analysis` (IV sweep analysis)
  - `Helpers.plotting_core` (plotting utilities)
- **Note:** This was a git submodule. Kept for reference only.

### old_code

- **Origin:** `Other/old_code/`
- **Archived:** Phase 1 refactoring
- **Description:** Legacy implementations that have been replaced:
  - `AdaptiveMeasurement.py` – superseded by current measurement runners
  - `Check_Connection.py` – replaced by `gui.connection_check_gui`
  - `Sample_GUI_old.py`, `Sample_GUI.py` – replaced by `gui.sample_gui`
  - `Measurement_GUI.py`, `Measurement_GUI.py.backup` – replaced by `gui.measurement_gui`
  - `sequential.py` – replaced by `Measurments.sequential_runner`
  - `old/Equipment/` – older equipment managers (now in `Equipment/managers/`)
  - `old/Measurments/` – older measurement services

## Restoration

If you need to reference or restore any archived code, the structure is preserved
here. Prefer updating the current codebase rather than restoring deprecated modules.
