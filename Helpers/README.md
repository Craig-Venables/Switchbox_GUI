# Helpers (deprecated)

**This folder is retired.** All code has moved to canonical locations. Do not add new files here.

## Where things went

| Former `Helpers/` path | Use instead |
|------------------------|-------------|
| `Analysis/`, `IV_Analysis/`, `Sample_Analysis/` | [`analysis/`](../analysis/) |
| `plotting_core/` | [`plotting/`](../plotting/) |
| `Data_Analysis/` | [`tools/device_visualizer/`](../tools/device_visualizer/) |
| `Data_Analysis_Pulse_2450/` | [`tools/data_analysis_pulse_2450/`](../tools/data_analysis_pulse_2450/) |
| `Classification_Validation/` | [`tools/classification_validation/`](../tools/classification_validation/) |
| `TSP_Testing_GUI_Standalone_V1/` | [`tools/tsp_testing_gui_standalone_v1/`](../tools/tsp_testing_gui_standalone_v1/) |
| `Camera_Stream_Standalone/` | [`tools/camera_stream_standalone/`](../tools/camera_stream_standalone/) |
| `HP4140B_GUI/` | [`tools/hp4140b_gui/`](../tools/hp4140b_gui/) |
| `Connection_Check_Standalone/` | [`tools/connection_check_standalone/`](../tools/connection_check_standalone/) |
| `ITO_Analysis/` | [`tools/ito_analysis/`](../tools/ito_analysis/) |
| `Maps_Create/` | [`tools/maps_create/`](../tools/maps_create/) |
| `Equipment_Address_Location/` | [`tools/equipment_address_location/`](../tools/equipment_address_location/) |
| `Gordon_temp.py` | [`tools/gordon_temperature/`](../tools/gordon_temperature/) |
| `Sample_Infomation/` | [`resources/sample_information/`](../resources/sample_information/) |

## Documentation

- **All tools index:** [`tools/README.md`](../tools/README.md)
- **Path migration (old → new):** [`Documents/development/PATH_MIGRATION.md`](../Documents/development/PATH_MIGRATION.md)
- **Add a sample type:** [`Documents/guides/README_ADD_SAMPLE_TYPE.md`](../Documents/guides/README_ADD_SAMPLE_TYPE.md)
- **Analysis layout:** [`analysis/ANALYSIS_STRUCTURE.md`](../analysis/ANALYSIS_STRUCTURE.md)

The main application imports from `gui/`, `Measurements/`, `analysis/`, and `plotting/` — not from `Helpers/`.
