---
name: Oscilloscope Pulse Capture GUI
overview: ""
todos:
  - id: 2cbd14d0-cea1-4cec-9d61-8f3419cc8b0c
    content: "Structure: Create `gui/oscilloscope_pulse_gui/` package."
    status: pending
  - id: 6abdef3a-604a-4879-b737-a4a17719e920
    content: "Logic: Implement `PulseMeasurementLogic` class (handling threading & hardware)."
    status: pending
  - id: 1d0544f6-d763-4ecf-9b14-a0372508d002
    content: "UI: Create `MainWindow` class with modern layout (collapsible frames)."
    status: pending
  - id: e4ea8a89-b8d0-4cbf-8dfd-8b2d6f746f64
    content: "Config: Implement `ConfigManager` to save/restore JSON settings."
    status: pending
  - id: 2991b772-9f02-4e6e-a85e-b2a9cf622b49
    content: "Integration: Add button to `measurement_gui`."
    status: pending
  - id: 3748bec0-37cf-4d21-be1b-834b4485c933
    content: "Integration: Add callback method in `measurement_gui/main.py`."
    status: pending
  - id: 9d7bbe13-51a0-4e00-b349-126f5aa05a16
    content: "Testing: Verify with Simulation Mode, then with real hardware."
    status: pending
---

# Oscilloscope Pulse Capture GUI

## Overview

Create a GUI tool that sends voltage pulses from the SMU to a memristor device and captures the current response using an oscilloscope. The tool will use a shunt resistor method (primary) for fast, accurate current measurements, with SMU current measurement as a secondary option.

## Architecture

### Main Components

1.  **Standalone GUI** (`gui/oscilloscope_pulse_gui/main.py`)
    *   Tkinter-based window following the modern `measurement_gui` style (collapsible sections, styled widgets).
    *   **Threading**: All hardware operations (pulse, measure, acquire) will run in a separate thread to prevent UI freezing.
    *   **Simulation Mode**: Built-in mock drivers for offline development and testing.
    *   **Configuration Persistence**: Automatically save and load last used settings via `config.json`.

2.  **Integration into measurement_gui**
    *   Add button in `gui/measurement_gui/layout_builder.py` (top control bar).
    *   Add callback method in `gui/measurement_gui/main.py`.
    *   Pass existing SMU connection to the new GUI.

## Implementation Details

### Files to Create

*   `gui/oscilloscope_pulse_gui/main.py` - Main GUI window class.
*   `gui/oscilloscope_pulse_gui/logic.py` - Separation of logic for pulse execution and data processing.
*   `gui/oscilloscope_pulse_gui/config_manager.py` - Helper for saving/loading JSON settings.
*   `gui/oscilloscope_pulse_gui/README.md` - Documentation.

### Files to Modify

*   `gui/measurement_gui/layout_builder.py` - Add "Oscilloscope Pulse" button.
*   `gui/measurement_gui/main.py` - Add `open_oscilloscope_pulse()` method and callback.

### Key Features

#### 1. Pulse Configuration
*   **Voltage**: Input field (V) with safety limit validation (e.g., ±10V).
*   **Duration**: Pulse width (s), supporting ms/us ranges.
*   **Compliance**: Current compliance for SMU (A).
*   **Timing**:
    *   Pre-pulse delay (wait time before pulse).
    *   Post-pulse hold time.
    *   *Improvement*: Use `time.perf_counter()` for more accurate timing in the worker thread.

#### 2. Oscilloscope Configuration
*   **Connection**:
    *   Auto-detect (via `OscilloscopeManager`).
    *   Manual address entry.
    *   *New*: **Simulation Mode** toggle (mocks hardware responses).
*   **Channel**: Select CH1 or CH2.
*   **Trigger**: Source, Level, Slope, Mode.
*   **Timebase**: Scale (s/div), Position (s).
*   **Vertical**: Scale (V/div), Offset (V), Coupling (AC/DC/GND).

#### 3. Measurement Methods
*   **Primary: Shunt Resistor**
    *   Configurable Resistor Value ($R_{shunt}$).
    *   Calculation: $I(t) = V_{scope}(t) / R_{shunt}$.
*   **Secondary: SMU Current**
    *   Fallback method using SMU's internal measurement (slower).

#### 4. Data Processing & Saving
*   **Acquisition**: Fetch raw waveform data (Time, Voltage).
*   **Processing**: Calculate Current array, Peak Current, Total Charge (integral).
*   **Saving**:
    *   Formats: JSON (metadata) + CSV (data) or compressed .npz.
    *   Metadata: timestamp, pulse params, scope settings, $R_{shunt}$, full SMU settings.
    *   *New*: **Auto-save** option to automatically save after every successful pulse.

#### 5. GUI Layout (Modern Tkinter)
*   **Left Panel (Controls)**:
    *   Collapsible logic (like `layout_builder.py`).
    *   Sections: "Connection", "Pulse Settings", "Scope Settings", "Measurement".
*   **Right Panel (Visualization)**:
    *   Matplotlib Figure with 2 subplots:
        1.  Voltage vs Time (Scope trace).
        2.  Current vs Time (Calculated).
    *   Toolbar for zooming/panning.
*   **Bottom Bar**:
    *   Status messages ("Ready", "Pulsing...", "Saving...").
    *   Progress bar for sequences (future proofing).
    *   control buttons: **RUN**, **STOP**, **SAVE**.

### Integration Points

#### SMU Access
*   Receive `smu_instance` from `measurement_gui`.
*   If standalone, attempt to connect to SMU using `Equipment.Managers`.

#### Oscilloscope Access
*   Use `Equipment/managers/oscilloscope.py`.
*   Wrap calls in `try/except` blocks to handle connection drops.

### Technical Considerations

#### Threading Model
*   **Main Thread**: UI Event Loop (Tkinter).
*   **Worker Thread**: Executes the measurement sequence.
    *   Prevents "Application Not Responding" state.
    *   Uses a Queue or Callback to send data back to Main Thread for plotting.

#### Error Handling
*   Input Validation: Check for non-numeric inputs, out-of-range values.
*   Hardware Errors: Catch `VisaIOError` and display friendly popups.
*   Safety: Ensure SMU output is turned OFF if an error occurs during the pulse.

#### Simulation Mode
*   If enabled, skip hardware calls.
*   Generate synthetic waveform data (e.g., a square wave with added noise) to allow GUI testing without equipment.

## Future Enhancements
*   **Pulse Train**: Define a sequence of pulses with varying amplitudes/widths.
*   **Sweep**: Automatically sweep pulse voltage and record response (RRAM switching probability).