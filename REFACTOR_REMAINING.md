# Refactoring – Remaining Work

This document tracks outstanding refactoring tasks for the Switchbox GUI project. See `TODO.md` for general feature requests and known issues.

---

## Completed

- **Phase 1 Layout Builder**: Removed duplicate sequential controls; extracted custom_measurement_section, conditional_config_helpers; removed legacy methods (_build_connection_section, _build_mode_selection, _build_top_banner, _build_signal_messaging, build_all_panels)
- **Phase 2 Measurement GUI**: Extracted custom_sweeps.py, messaging_handlers.py, conditional_testing.py
- **Documentation**: Module docstrings, README updates, `TODO.md` consolidation
- **Archive**: Legacy code moved to `archive/`
- **Deprecation shims**: `IV_Analysis`, `Sample_Analysis` → `analysis`
- **Naming fixes**: `Measurments` → `Measurements`, `Sample_Infomation` → `Sample_Information`
- **Layout tabs**: All 8 tabs extracted to `gui/measurement_gui/layout/tab_*.py`
- **Layout sections**: Collapsible panels extracted to `gui/measurement_gui/layout/sections/`
- **Advanced tests sections**: Manual endurance/retention and conditional testing moved to `layout/sections/advanced_tests.py`
- **Connection section**: Setup tab (SMU, PSU, Temp) moved to `layout/sections/connection.py`
- **Notes helpers**: Load/save notes, previous devices, keyboard shortcuts, polling → `layout/notes_helpers.py`
- **Optical section**: LED/Laser configuration → `layout/sections/optical.py`
- **Bottom status bar**: Connection/devices/ready → `layout/sections/status_bar.py`
- **Sample GUI config**: `sample_config`, mappings, save paths moved to `gui/sample_gui/config.py`
- **Sample GUI UI**: All UI builders moved to `gui/sample_gui/ui/` (device map, device selection,
  terminal log, status bar, device manager, quick scan, top control bar)
- **Helpers refactor**: Core moved to top-level `analysis/` and `plotting/`; optional tools to `tools/`;
  assets to `resources/sample_information/`; deprecated `IV_Analysis` and `Sample_Analysis` removed.
  Main app and tools now import from `analysis`, `plotting`, and `tools.device_visualizer`.

---

## Remaining

### 1. Layout Builder – Further Decomposition

**File:** `gui/measurement_gui/layout_builder.py` (~4,000+ lines)

| Section | Lines (approx) | Notes |
|---------|----------------|-------|
| ~~`_build_connection_section_modern`~~ | ~~~600~~ | **Extracted** to `layout/sections/connection.py` |
| ~~`_build_optical_section`~~ | ~~~200~~ | **Extracted** to `layout/sections/optical.py` |
| `_build_manual_endurance_retention` | ~120 | Advanced Tests tab |
| `_build_conditional_testing_section` | ~360 | Advanced Tests tab |
| `_build_sequential_controls` | ~120 | Legacy (if still used) |
| `_build_custom_measurement_section` | ~100 | Fallback when CustomMeasurementsBuilder fails |
| ~~Notes helpers~~ | ~~~600~~ | **Extracted** to `layout/notes_helpers.py` |

**Suggestion:** Extract remaining to `layout/sections/notes_helpers.py`, or similar.

---

### 2. Measurement GUI Main

**File:** `gui/measurement_gui/main.py` (~7,600 lines)

- Large monolithic class handling layout, callbacks, measurement logic, plotting, and persistence.
- **Completed extractions:**
  - `custom_sweeps.py`, `messaging_handlers.py`, `conditional_testing.py`
  - `plot_handlers.py` – full extraction: plot_measurement_in_background, generate_sequence_summary, refresh_stats_list, update_stats_display, update_stats_plots, plot_all_device_graphs, plot_all_sample_graphs, run_full_sample_analysis
  - `analysis_handlers.py` – format_analysis_value, run_analysis_sync, get_latest_analysis_for_device
- **Remaining:** Further analysis handlers (save_analysis_results, save_research_analysis, append_classification_log, run_retroactive_analysis, reclassify_all_devices) if desired

---

### 3. Sample GUI Main

**File:** `gui/sample_gui/main.py` (~2,700 lines)

- Config in `config.py`. All UI layout in `ui/`.
- Remaining: business logic, event handlers, measurement/routing logic. Main is now focused
  on wiring and behavior rather than widget construction.

---

### 4. Pulse Testing GUI

**File:** `gui/pulse_testing_gui/main.py`

- Smaller than measurement/sample GUIs.
- Decompose only if it grows or becomes hard to maintain.

---

### 5. Motor Control GUI

**File:** `gui/motor_control_gui/main.py`

- Same approach as pulse testing GUI – extract if it becomes unwieldy.

---

### 6. Unified Measurement API (Phase 4)

- Define a shared abstraction for IV sweeps, pulse tests, sequential runs, etc.
- Reduces duplication between measurement modes.
- **Requires:** Design pass before implementation.

---

### 7. Plotting – One-stop shop (in progress)

- **Done:** `plotting/style.py` (central dpi/figsize/fonts), `plotting/CATALOG.md`, `plotting/sample_plots.py` (plots 1–8 for Run Full Sample Analysis), `plotting/endurance_plots.py` (DC endurance). Single entry point: `from plotting import UnifiedPlotter, SamplePlots, style, endurance_plots`. See `plotting/README.md` and `plotting/CATALOG.md`.
- **Remaining:** Move sample plots 9–26 from `analysis/aggregators/sample_analyzer.py` into `plotting/sample_plots.py`; move section-level plots into `plotting/section_plots.py`; move device combined sweeps into `plotting/device_combined_plots.py`.

### 8. Optional / Low Priority

- **Legacy layout methods**: Remove `_build_connection_section`, `_build_mode_selection`, `_build_top_banner`, `_build_signal_messaging` if they are no longer used.
- **TSP standalone**: `tools/tsp_testing_gui_standalone_v1/` uses its own `Measurments` package – consider aligning with main package or clearly documenting as standalone.
- **Import hygiene**: Review for circular imports and use `TYPE_CHECKING` where appropriate.

---

## Suggested Order

1. ~~Extract connection section~~ ✓
2. ~~Extract notes helpers~~ ✓
3. ~~Decompose sample_gui~~ ✓
4. Decompose measurement_gui main (callbacks, plots, runners).
5. Design and implement unified measurement API.
6. Revisit pulse/motor GUIs and legacy layout methods as needed.
