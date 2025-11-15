# GUI Architecture Overview

## Current GUI Relationships

```
┌─────────────────────────────────────────────────────────────────┐
│                         main.py                                 │
│                    (Entry Point)                                │
└───────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │   Sample_GUI.py   │  ◄── Main Device Selection
                    │   (3200 lines)    │      & Multiplexer Control
                    └─────────┬─────────┘
                              │
                              │ Launches
                              ▼
                    ┌──────────────────┐
                    │ Measurement_GUI  │  ◄── Main Measurement Interface
                    │   (~2000 lines)  │      IV Sweeps, Measurements
                    └─────────┬────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│TSP_Testing_  │    │Check_        │    │Motor_        │
│GUI           │    │Connection_    │    │Control_      │
│(3289 lines)  │    │GUI           │    │GUI           │
│              │    │(382 lines)    │    │              │
└──────────────┘    └──────────────┘    └──────────────┘
        │
        │ Can also be standalone
        │
        ▼
┌──────────────┐
│Advanced_     │
│Tests_GUI     │
│(464 lines)   │
└──────────────┘
```

## GUI Purposes

### 1. Sample_GUI.py
**Purpose**: Device selection and sample management
- Browse device maps/images
- Select devices to test
- Control multiplexer routing
- Manage sample information
- Quick scan functionality

**Launches**: `MeasurementGUI`

**Key Features**:
- Visual device map
- Device status tracking
- Multiplexer control
- Sample configuration

---

### 2. Measurement_GUI.py
**Purpose**: Main measurement interface
- Configure IV sweeps
- Run measurements
- Control instruments (SMU, PSU, Temp)
- Real-time plotting
- Data saving

**Launches**:
- `TSPTestingGUI` - For pulse testing
- `CheckConnection` - Connection verification
- `MotorControlWindow` - Motor control
- `AdvancedTestsGUI` - Advanced tests
- `AutomatedTesterGUI` - Automated workflows

**Key Features**:
- Instrument connection management
- Measurement configuration
- Real-time plotting (uses `gui/plot_panels.py`)
- Custom sweep editor
- Sequential measurements

---

### 3. TSP_Testing_GUI.py
**Purpose**: Pulse testing for Keithley instruments
- Pulse-read-repeat tests
- Width sweeps
- Potentiation/depression cycles
- Endurance tests
- Real-time pulse visualization

**Can be**:
- Launched from `MeasurementGUI`
- Standalone (direct entry point)

**Key Features**:
- Multi-system support (2450, 4200A)
- Test parameter configuration
- Real-time plotting
- Data saving

---

### 4. Check_Connection_GUI.py
**Purpose**: Connection verification tool
- Apply small DC bias
- Monitor current in real-time
- Audio alerts for connection
- Quick connection check

**Launched from**: `MeasurementGUI`

**Key Features**:
- Real-time current plot
- Sound alerts
- Connection threshold detection

---

### 5. advanced_tests_gui.py
**Purpose**: Advanced/volatile memristor tests
- Transient decay
- Paired-pulse facilitation (PPF)
- STDP (spike-timing dependent plasticity)
- SRDP (rate-dependent plasticity)

**Launched from**: `MeasurementGUI`

**Key Features**:
- Specialized test configurations
- Neuromorphic test patterns

---

### 6. Motor_Controll_GUI.py
**Purpose**: Motor control for laser positioning
- XY stage control
- Position presets
- Scanning capabilities
- Function generator integration

**Can be**: Standalone or launched from `MeasurementGUI`

**Key Features**:
- Interactive canvas
- Position tracking
- Motor jog controls
- Preset management

---

### 7. Automated_tester_GUI.py
**Purpose**: Automated testing workflows
- Batch device testing
- Automated measurement sequences
- Result tracking

**Launched from**: `MeasurementGUI`

---

## Existing GUI Components (`gui/` directory)

### layout_builder.py
- Builds `MeasurementGUI` layout
- Modern tabbed interface
- Reusable layout components

### plot_panels.py
- Plotting components
- Matplotlib integration
- Real-time plot updates

### plot_updaters.py
- Plot update logic
- Data formatting for plots
- Plot refresh management

### custom_measurements_builder.py
- Custom measurement UI builder
- Parameter input widgets
- Measurement configuration

---

## Data Flow

```
User Action Flow:
1. Start main.py
   └─> Sample_GUI
       └─> Select devices
           └─> Launch Measurement_GUI
               ├─> Configure measurement
               ├─> Connect instruments
               └─> Run measurement
                   ├─> Optionally launch TSP_Testing_GUI for pulse tests
                   ├─> Optionally launch Check_Connection for verification
                   └─> Save results

Alternative Flow:
- Direct launch of TSP_Testing_GUI (standalone mode)
- Direct launch of Motor_Control_GUI
```

---

## Key Issues with Current Structure

1. **Large Files**: TSP_Testing_GUI (3289 lines), Sample_GUI (3200 lines)
   - Hard to navigate
   - Mixed concerns
   - Difficult to maintain

2. **Unclear Entry Points**
   - Multiple ways to launch same functionality
   - Unclear which GUI to use when

3. **Tight Coupling**
   - GUIs directly import each other
   - Hard to test in isolation
   - Changes ripple through system

4. **Code Duplication**
   - Similar UI patterns repeated
   - Parameter input code duplicated
   - Connection logic repeated

5. **Mixed Concerns**
   - UI code mixed with business logic
   - Data handling mixed with presentation
   - Hard to separate for testing

---

## Recommended Improvements

See `GUI_REFACTORING_PLAN.md` for detailed refactoring strategy.

**Quick Wins**:
1. Add clear docstrings to each GUI file
2. Document which GUI launches which
3. Create simple architecture diagram
4. Extract common UI components

**Medium Term**:
1. Reorganize into `gui/` subdirectories
2. Break down large files
3. Create base classes for common patterns
4. Standardize communication between GUIs

**Long Term**:
1. Full separation of concerns
2. Event-based communication
3. Comprehensive testing
4. Clear API boundaries


