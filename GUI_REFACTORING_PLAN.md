# GUI Refactoring Plan

## Current State Analysis

### Main GUI Files (Root Directory)
1. **Sample_GUI.py** (3200 lines)
   - Purpose: Device selection, multiplexer routing, sample management
   - Launches: MeasurementGUI
   - Status: Large, complex, mixes UI and business logic

2. **TSP_Testing_GUI.py** (3289 lines)
   - Purpose: Pulse testing for Keithley 2450/4200A
   - Can be: Standalone or launched from MeasurementGUI
   - Status: Very large, contains test definitions, UI, and logic

3. **Measurement_GUI.py** (~2000+ lines)
   - Purpose: IV sweeps, measurements, instrument control
   - Launches: TSPTestingGUI, CheckConnection, MotorControlWindow, AdvancedTestsGUI
   - Status: Uses layout_builder.py (good!), but still large

4. **Check_Connection_GUI.py** (382 lines)
   - Purpose: Connection verification tool
   - Status: Reasonable size, relatively focused

5. **advanced_tests_gui.py** (464 lines)
   - Purpose: Advanced/volatile memristor tests
   - Status: Reasonable size, focused

6. **Motor_Controll_GUI.py**
   - Purpose: Motor control for laser positioning
   - Status: Standalone, focused

7. **Automated_tester_GUI.py**
   - Purpose: Automated testing workflows
   - Status: Large, complex

### Existing GUI Module (`gui/`)
- `layout_builder.py` - Good separation! Builds MeasurementGUI layout
- `plot_panels.py` - Plotting components
- `plot_updaters.py` - Plot update logic
- `custom_measurements_builder.py` - Custom measurement UI

### Problems Identified
1. **Large monolithic files** - Hard to navigate and understand
2. **Unclear relationships** - How GUIs connect is not obvious
3. **Mixed concerns** - UI, business logic, and data handling mixed together
4. **Scattered files** - GUIs in root, some components in `gui/`
5. **Duplicate code** - Similar patterns repeated across files
6. **Hard to test** - Tight coupling makes unit testing difficult
7. **No clear entry points** - Unclear which GUI to use when

---

## Proposed Refactoring Strategy

### Phase 1: Organization & Documentation (Low Risk)
**Goal**: Make current structure more understandable without breaking changes

#### 1.1 Create Clear Directory Structure
```
gui/
├── __init__.py
├── core/                          # Core GUI framework
│   ├── __init__.py
│   ├── base_window.py            # Base class for all GUI windows
│   ├── base_dialog.py            # Base class for dialogs
│   └── window_manager.py         # Manages window lifecycle
│
├── main/                          # Main application windows
│   ├── __init__.py
│   ├── sample_gui.py            # Device selection (from Sample_GUI.py)
│   ├── measurement_gui.py       # Main measurement window (from Measurement_GUI.py)
│   └── pulse_testing_gui.py     # Pulse testing (from TSP_Testing_GUI.py)
│
├── dialogs/                       # Popup dialogs and tools
│   ├── __init__.py
│   ├── connection_check.py      # From Check_Connection_GUI.py
│   ├── advanced_tests.py         # From advanced_tests_gui.py
│   ├── motor_control.py          # From Motor_Controll_GUI.py
│   └── automated_tester.py      # From Automated_tester_GUI.py
│
├── components/                    # Reusable UI components
│   ├── __init__.py
│   ├── parameter_input.py       # Parameter entry widgets
│   ├── plot_canvas.py            # Matplotlib canvas wrapper
│   ├── status_bar.py             # Status bar component
│   ├── connection_panel.py      # Instrument connection UI
│   └── device_selector.py       # Device selection widget
│
├── builders/                      # UI builders (existing)
│   ├── __init__.py
│   ├── layout_builder.py         # Keep existing
│   ├── plot_panels.py            # Keep existing
│   ├── plot_updaters.py          # Keep existing
│   └── custom_measurements_builder.py  # Keep existing
│
└── utils/                         # GUI utilities
    ├── __init__.py
    ├── validators.py             # Input validation
    ├── formatters.py             # Data formatting for display
    └── helpers.py                # Common helper functions
```

#### 1.2 Create Architecture Documentation
- Document GUI hierarchy and relationships
- Create flow diagrams showing how GUIs interact
- Document entry points and use cases

#### 1.3 Add Clear Module Docstrings
- Each GUI file should have clear purpose statement
- Document dependencies and relationships
- List what it launches/creates

### Phase 2: Extract Reusable Components (Medium Risk)
**Goal**: Create reusable components to reduce duplication

#### 2.1 Extract Common Patterns
- **Parameter Input Widgets**: Extract from TSP_Testing_GUI and Measurement_GUI
- **Connection Panels**: Extract instrument connection UI
- **Plot Components**: Enhance existing plot_panels.py
- **Status/Log Displays**: Extract terminal/log display components

#### 2.2 Create Base Classes
- `BaseMeasurementWindow`: Common functionality for measurement GUIs
- `BaseDialog`: Common dialog patterns
- `BasePlotPanel`: Common plotting functionality

### Phase 3: Break Down Large Files (Higher Risk)
**Goal**: Split large files into manageable modules

#### 3.1 TSP_Testing_GUI.py Refactoring
```
gui/main/pulse_testing_gui.py      # Main window class (~500 lines)
gui/main/pulse_testing/
├── test_definitions.py            # TEST_FUNCTIONS dict (~300 lines)
├── test_runner.py                  # Test execution logic (~400 lines)
├── plot_manager.py                 # Plotting logic (~300 lines)
├── connection_handler.py           # Device connection (~200 lines)
└── save_handler.py                 # Data saving (~200 lines)
```

#### 3.2 Sample_GUI.py Refactoring
```
gui/main/sample_gui.py              # Main window class (~500 lines)
gui/main/sample_gui/
├── device_map_viewer.py            # Image map display (~400 lines)
├── device_selector.py               # Device selection logic (~300 lines)
├── multiplexer_controller.py       # Multiplexer routing (~300 lines)
├── status_tracker.py               # Device status tracking (~300 lines)
└── quick_scan.py                   # Quick scan functionality (~400 lines)
```

#### 3.3 Measurement_GUI.py Refactoring
```
gui/main/measurement_gui.py          # Main window class (~400 lines)
gui/main/measurement_gui/
├── instrument_manager.py            # Instrument connections (~300 lines)
├── measurement_runner.py            # Measurement execution (~400 lines)
├── sweep_config.py                  # Sweep configuration (~200 lines)
└── data_handler.py                  # Data saving/loading (~200 lines)
```

### Phase 4: Improve Relationships (Medium Risk)
**Goal**: Make GUI relationships explicit and clear

#### 4.1 Create Window Manager
- Central registry of open windows
- Prevents duplicate windows
- Manages window lifecycle

#### 4.2 Standardize Communication
- Use events/signals for GUI-to-GUI communication
- Clear provider/consumer patterns
- Document data flow

#### 4.3 Create Entry Point Documentation
```
ENTRY_POINTS.md:
- Sample_GUI: Main entry for device selection
  → Launches: MeasurementGUI
- MeasurementGUI: Main measurement interface
  → Launches: TSPTestingGUI, CheckConnection, etc.
- TSPTestingGUI: Can be standalone or launched from MeasurementGUI
```

---

## Recommended Implementation Order

### Step 1: Create Documentation (1-2 hours)
1. Document current GUI relationships
2. Create architecture diagram
3. Document entry points

### Step 2: Reorganize Directory Structure (2-3 hours)
1. Create new `gui/` subdirectories
2. Move files to new locations
3. Update imports (use aliases to maintain backward compatibility)
4. Test that everything still works

### Step 3: Extract Common Components (4-6 hours)
1. Create base classes
2. Extract parameter input widgets
3. Extract connection panels
4. Update existing GUIs to use new components

### Step 4: Break Down Large Files (8-12 hours)
1. Start with TSP_Testing_GUI.py (most complex)
2. Extract test definitions
3. Extract test runner
4. Extract plotting logic
5. Repeat for Sample_GUI.py
6. Repeat for Measurement_GUI.py

### Step 5: Improve Relationships (4-6 hours)
1. Create window manager
2. Standardize communication patterns
3. Update all GUIs to use new patterns

---

## Benefits of Refactoring

1. **Understandability**
   - Clear file organization
   - Obvious relationships between components
   - Easy to find relevant code

2. **Maintainability**
   - Smaller, focused files
   - Easier to modify without breaking other parts
   - Clear separation of concerns

3. **Reusability**
   - Common components can be reused
   - Less code duplication
   - Consistent UI patterns

4. **Testability**
   - Smaller units easier to test
   - Clear interfaces
   - Can test components in isolation

5. **Onboarding**
   - New developers can understand structure quickly
   - Clear entry points
   - Well-documented relationships

---

## Migration Strategy

### Backward Compatibility
- Keep old imports working with aliases initially
- Gradually migrate to new structure
- Update documentation as we go

### Testing Strategy
- Test after each phase
- Ensure all GUIs still launch correctly
- Verify functionality is preserved

### Rollout Plan
1. Phase 1: Documentation + directory structure (low risk)
2. Phase 2: Extract components (test thoroughly)
3. Phase 3: Break down files (one at a time)
4. Phase 4: Improve relationships (final polish)

---

## Questions to Consider

1. **Should we keep old files during migration?**
   - Yes, with deprecation warnings
   - Remove after full migration

2. **How to handle existing users?**
   - Maintain backward compatibility
   - Update main.py to use new structure
   - Provide migration guide

3. **What about the standalone TSP GUI?**
   - Keep it as a separate entry point
   - Share components with main GUI

---

## Next Steps

1. **Review this plan** - Get feedback on approach
2. **Prioritize phases** - Decide what to do first
3. **Start with Phase 1** - Low risk, high value
4. **Iterate** - Make improvements as we go

