# Helpers

This folder is for **misc one-off helper scripts only**. It was refactored so that:

- **Core analysis** lives in the top-level `analysis/` package.
- **Core plotting** lives in the top-level `plotting/` package.
- **Optional tools** (device visualizer, classification validation, standalones) live under `tools/`.
- **Sample assets** (images, mappings) live under `resources/sample_information/`.

Do not put regularly-used or core application code here. Use `analysis/`, `plotting/`, or `tools/` as appropriate.
