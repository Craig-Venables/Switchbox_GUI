# Helpers (legacy)

**This folder contains legacy copies of tools and analysis code.** New work should use the canonical locations below.

| Legacy (`Helpers/`) | Use instead |
|---------------------|-------------|
| `Helpers/Analysis/`, `Helpers/IV_Analysis/` | [`analysis/`](../analysis/) |
| `Helpers/plotting_core/` | [`plotting/`](../plotting/) |
| `Helpers/Data_Analysis_Pulse_2450/` | [`tools/data_analysis_pulse_2450/`](../tools/data_analysis_pulse_2450/) |
| `Helpers/Classification_Validation/` | [`tools/classification_validation/`](../tools/classification_validation/) |
| `Helpers/TSP_Testing_GUI_Standalone_V1/` | [`tools/tsp_testing_gui_standalone_v1/`](../tools/tsp_testing_gui_standalone_v1/) |
| `Helpers/Camera_Stream_Standalone/` | [`tools/camera_stream_standalone/`](../tools/camera_stream_standalone/) |

The main application imports from `Measurements`, `analysis`, `plotting`, and `gui` — not from `Helpers/`.

These copies are kept temporarily for backward compatibility. They may be removed in a future cleanup once all references are migrated.

See also [CONTRIBUTING.md](../CONTRIBUTING.md) and [archive/README.md](../archive/README.md).
