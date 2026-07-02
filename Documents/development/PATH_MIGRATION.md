# Path migration reference

Historical paths from before the `Helpers/` cleanup (July 2026). Use the **canonical** column for all new work and documentation.

## Code packages

| Old path | Canonical path |
|----------|----------------|
| `Helpers/Analysis/` | `analysis/` |
| `Helpers/IV_Analysis/` | `analysis/` (`core/`, `api/`) |
| `Helpers/Sample_Analysis/` | `analysis/aggregators/` |
| `Helpers/plotting_core/` | `plotting/` |
| `Measurments/` (typo) | `Measurements/` |

## Standalone tools

| Old path | Canonical path |
|----------|----------------|
| `Helpers/Data_Analysis_Pulse_2450/` | `tools/data_analysis_pulse_2450/` |
| `Helpers/Classification_Validation/` | `tools/classification_validation/` |
| `Helpers/TSP_Testing_GUI_Standalone_V1/` | `tools/tsp_testing_gui_standalone_v1/` |
| `Helpers/Camera_Stream_Standalone/` | `tools/camera_stream_standalone/` |
| `Helpers/HP4140B_GUI/` | `tools/hp4140b_gui/` |
| `Helpers/Connection_Check_Standalone/` | `tools/connection_check_standalone/` |
| `Helpers/Data_Analysis/` | `tools/device_visualizer/` |
| `Helpers/ITO_Analysis/` | `tools/ito_analysis/` |
| `Helpers/Maps_Create/` | `tools/maps_create/` |
| `Helpers/Equipment_Address_Location/` | `tools/equipment_address_location/` |
| `Helpers/Gordon_temp.py` | `tools/gordon_temperature/gordon_temp.py` |
| `Impedence Analyzer/` (typo) | `tools/impedance_analyzer/` |
| `afm curve analysis/` (spaces) | `tools/afm_curve_analysis/` |
| `afm 3d holes and protrusion/` | `tools/afm_3d_holes_protrusion/` |

## Assets

| Old path | Canonical path |
|----------|----------------|
| `Helpers/Sample_Infomation/` | `resources/sample_information/` |
| `Helpers/Sample_Information/` (docs typo) | `resources/sample_information/` |

## Import examples

```python
# Old (do not use)
from Helpers.Analysis import quick_analyze
from Helpers.plotting_core import UnifiedPlotter

# Current
from analysis import quick_analyze
from plotting import UnifiedPlotter
```

## Run examples

```powershell
# Old
python Helpers/Classification_Validation/run_validation_tool.py

# Current
python tools/classification_validation/launch_gui.py
```

## Related docs

- [Helpers/README.md](../../Helpers/README.md) — short redirect table
- [tools/README.md](../../tools/README.md) — full tools index
- [analysis/ANALYSIS_STRUCTURE.md](../../analysis/ANALYSIS_STRUCTURE.md) — analysis module map
