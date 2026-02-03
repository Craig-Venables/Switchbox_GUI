# Switchbox Measurement System

Comprehensive measurement system for device characterization with support for IV sweeps, pulse testing, and real-time monitoring. Features modular GUI architecture, unified equipment management, and Telegram notifications, designed for use within the university of nottingham under neil kemp

## Quick Start

```bash
# Run the main application
python main.py
```

The application starts with the Sample GUI, where you can select devices and launch measurement interfaces.

## About

- **Real-time Graphing**: Multiple plots with live updates during measurements
- **Temperature Control**: Temperature measurement/manager ready (ITC/Lakeshore)
- **LED Control**: LED control via PSU
- **Telegram Notifications**: Bot messaging for remote prompts and updates
- **Auto-saving**: Data with device/sample folders and incrementing filenames
- **Sequential Measurements**: Automated measurement across multiple devices
- **Modular Architecture**: Clean, organized package structure

## Project Structure

```
Switchbox_GUI/
├── main.py                      # Main entry point
├── TODO.md                      # Tracked feature requests and known issues
├── gui/                         # All GUI modules (modular structure)
│   ├── sample_gui/              # Device selection and sample management
│   ├── measurement_gui/         # Main measurement interface
│   ├── pulse_testing_gui/       # Fast pulse testing (TSP/4200A)
│   ├── motor_control_gui/       # XY stage motor control
│   ├── connection_check_gui/    # Connection verification tool
│   └── README.md                # GUI package documentation
├── Equipment/                   # Hardware control modules
│   ├── managers/                # Unified equipment managers
│   │   ├── iv_controller.py     # IV controller manager
│   │   ├── camera.py            # Camera manager
│   │   ├── function_generator.py
│   │   └── ...
│   └── SMU_AND_PMU/             # SMU/PMU controllers
├── Measurements/                 # Measurement services
│   ├── measurement_services_smu.py
│   ├── measurement_services_pmu.py
│   ├── connection_manager.py
│   └── ...
├── Notifications/               # Notification services
│   ├── telegram_bot.py          # Telegram bot integration
│   └── README.md
├── Pulse_Testing/               # Pulse testing utilities
│   ├── system_wrapper.py        # Multi-system routing
│   └── systems/                 # System implementations
├── Json_Files/                  # Configuration files
│   ├── system_configs.json      # System configurations
│   ├── mapping.json             # Device mappings
│   └── ...
├── Helpers/                     # Helper scripts and tools
└── archive/                     # Archived legacy code (see archive/README.md)
```

## GUI System

All GUIs are organized in the `gui/` package for modularity and easy maintenance.

### Application Flow

```
main.py
  └─> SampleGUI (gui/sample_gui/)
        └─> MeasurementGUI (gui/measurement_gui/)
              ├─> TSPTestingGUI (gui/pulse_testing_gui/)
              ├─> CheckConnection (gui/connection_check_gui/)
              ├─> MotorControlWindow (gui/motor_control_gui/)
              ├─> AdvancedTestsGUI
              └─> AutomatedTesterGUI
```

### GUI Modules

#### 1. Sample GUI (`gui/sample_gui/`)
- **Purpose**: Main entry point for device selection
- **Features**: Visual device map, device status tracking, multiplexer control
- **See**: [gui/sample_gui/README.md](gui/sample_gui/README.md)

#### 2. Measurement GUI (`gui/measurement_gui/`)
- **Purpose**: Central measurement interface
- **Features**: Instrument connections, IV sweeps, real-time plotting, data saving
- **See**: [gui/measurement_gui/README.md](gui/measurement_gui/README.md)

#### 3. Pulse Testing GUI (`gui/pulse_testing_gui/`)
- **Purpose**: Fast pulse testing interface
- **Features**: Multi-system support (2450, 4200A), real-time visualization
- **See**: [gui/pulse_testing_gui/README.md](gui/pulse_testing_gui/README.md)

#### 4. Motor Control GUI (`gui/motor_control_gui/`)
- **Purpose**: XY stage motor control with laser positioning
- **Features**: Interactive canvas, position presets, raster scanning
- **See**: [gui/motor_control_gui/README.md](gui/motor_control_gui/README.md)

#### 5. Connection Check GUI (`gui/connection_check_gui/`)
- **Purpose**: Real-time connection verification
- **Features**: Current monitoring, audio alerts, threshold detection
- **See**: [gui/connection_check_gui/README.md](gui/connection_check_gui/README.md)

For detailed documentation, see [gui/README.md](gui/README.md)

## Equipment Managers

All equipment follows a unified manager pattern located in `Equipment/managers/`:

### Available Managers

- **IV Controller**: `Equipment/managers/iv_controller.py` - Keithley SMUs (2400, 2401, 2450, 4200A), HP4140B
- **Temperature Controllers**: `Equipment/managers/temperature.py` - Lakeshore 335, Oxford ITC4
- **Function Generators**: `Equipment/managers/function_generator.py` - Siglent SDG1032X, Moku Go
- **Cameras**: `Equipment/managers/camera.py` - Thorlabs USB/Ethernet
- **Laser Controllers**: `Equipment/managers/laser.py` - Oxxius
- **Power Supplies**: `Equipment/managers/power_supply.py` - Keithley 2220 (LED control)
- **Ammeters**: `Equipment/managers/ammeter.py` - Agilent
- **Multiplexers**: `Equipment/managers/multiplexer.py` - PySwitchbox, Electronic Mpx
- **Oscilloscopes**: `Equipment/managers/oscilloscope.py` - Tektronix, GW Instek

### Manager Usage

All managers support lazy imports and optional dependencies, so missing hardware dependencies won't crash the application.

```python
from Equipment.managers.iv_controller import IVControllerManager

# Create manager instance
iv_manager = IVControllerManager(
    smu_type="Keithley 2450",
    address="USB0::0x05E6::0x2450::04496615::INSTR"
)

# Use unified API
iv_manager.set_voltage(1.0, 1e-3)
current = iv_manager.measure_current()
```

All managers support `from_config()` for configuration-based initialization.

## Supported Systems

### SMU/PMU (Keithley)

- **Keithley 2400/2401** (SMU) - Classic SMU control
- **Keithley 2450** (TSP mode) - Fast pulse generation, front/rear terminal selection
- **Keithley 4200A** (SMU mode) - Standard SMU operations
- **Keithley 4200A** (PMU mode) - Waveform capture, laser pulse integration
- **HP4140B** - Classic picoammeter/SMU with GPIB interface

### Temperature Controllers

- **Lakeshore 335** - Via TemperatureControllerManager
- **Oxford ITC4** - Via TemperatureControllerManager or direct connection

### Power Supplies

- **Keithley 2220** - Used for LED driving

### Function Generators

- **Siglent SDG1032X** - Triggered pulses, DC levels
- **Moku Go** - In development

### Cameras

- **Thorlabs Camera System**
  - **USB Mode**: Local camera viewing for direct monitoring
  - **Server Mode**: Stream video from one laptop to another over Ethernet
  - **Client Mode**: Receive and display video stream from remote server
  - **Motor Control Integration**: Frame callbacks available for automated positioning
  - Test script: `Equipment/Camera/view_camera.py` provides GUI viewer
  - Manager: `Equipment/managers/camera.py` for unified camera interface

### Motor Control

- **Thorlabs Kinesis Linear Stages** (X/Y axes)
  - Controller: `Equipment/Motor_Controll/Kenisis_motor_control.py`
  - GUI: `gui/motor_control_gui/`
  - Camera integration ready for visual positioning feedback

### Multiplexers

- **PySwitchbox**: 100-device array (Arduino-controlled relay box)
- **Electronic Mpx**: Simple 1–10 selector (positive inner, negative outer) for basic routing

## Measurement Types

### DC Measurements

- **DC Triangle IV**: Classic FS/PS/NS triangle sweep. Configurable by Sweep Mode (fixed step, fixed sweep rate, fixed voltage time), Sweep Type (FS/PS/NS), Step/Delay or rate/time.

### SMU Pulsed Measurements

- **SMU Pulsed IV**: One pulse per amplitude across a range; device returns to Vbase and a read is taken. Use when you want reduced self-heating compared with DC IV.

- **SMU Fast Pulses**: Pulse train at fixed amplitude and width; measure at Vbase after each pulse. Good for endurance-like stress.

- **SMU Fast Hold**: Hold a DC bias and sample current vs time (I–t). Useful for stress/recovery or quick retention checks.

- **ISPP**: Incremental Step Pulse Programming. Increase pulse amplitude stepwise until hitting a target current/resistance. Produces amplitude vs response curves.

- **Pulse Width Sweep**: Fixed amplitude, sweep pulse width; read at Vbase; width vs response.

- **Threshold Search**: Find Vset/Vreset using binary/gradient search with minimal pulses.

### Measurement Visualizations

- **DC Triangle IV**
```
V: /\/\
I: response vs V
```

- **SMU Pulsed IV (Amplitude Sweep)**
```
A: [A1 A2 A3 ...]
Pulse: |‾‾|   |‾‾|   |‾‾|
Read:   r1     r2     r3   at Vbase
Plot: A vs I_read
```

- **SMU Fast Pulses**
```
Pulse train: |‾| |‾| |‾| |‾| ... (fixed A, width)
Reads: after each at Vbase
```

- **SMU Fast Hold**
```
V(t) = Vhold (flat)
I(t) sampled regularly
```

- **ISPP (Amplitude Ramp to Target)**
```
Amps:  0.2  0.3  0.4  0.5 ...
Iread: i1   i2   i3*           (* ≥ target)
Plot: Amplitude vs I_read
```

- **Pulse Width Sweep (Fixed Amplitude)**
```
Widths (ms):  1   2   5   10 ...
I_read:       i1  i2  i3  i4
Plot: width vs I_read
```

- **Threshold Search (Binary Search on V)**
```
Range: [Vlow --------------------- Vhigh]
Test mid -> I(mid) ? target -> shrink range toward threshold
Repeat until |Vhigh - Vlow| small
```

### Volatile Memristor Tests

Available via "Advanced Tests" in Measurement GUI:

- **Transient Decay**: Single pulse then sample I(t) at Vread (extract τ / power-law).
  - Sketch: `|‾‾|____` then hold Vread → I(t) decays.

- **PPF**: Two identical pulses separated by Δt; PPF index vs Δt.
  - Sketch: `|‾‾|__Δt__|‾‾|` → measure I1 and I2 @ Vread; PPF=(I2−I1)/|I1|.

- **STDP**: Pre/post pulses with Δt (±); Δw vs Δt curve.

- **SRDP**: Trains at different frequencies; steady-state/current gain vs rate.

- **Potentiation/Depression**: Alternating +/− short pulses; immediate and post-delay reads; volatility ratio.

- **Frequency Response**: Sweep pulse frequency (fixed width/amplitude); response vs frequency.

- **Dynamic Threshold (volatile)**: Minimal pulse amplitude/width that elicits transient change (binary/gradient).

- **Bias-dependent Volatility**: Repeat transients at multiple Vread; map decay constants vs bias.

- **Noise/RTN**: Low-bias I(t) segments for PSD/variance.

### Nonvolatile Tests

- Long retention, endurance, MLC program/verify, half-select disturb, etc. (in development)

### Custom Sweeps

The system supports custom measurement configurations via JSON files, enabling complex multi-sweep measurements, endurance testing, retention testing, and conditional testing workflows.

#### Custom_Sweeps.json

**Location**: `Json_Files/Custom_Sweeps.json`

This file defines custom measurement sequences that can be selected from the Measurement GUI's "Custom Measurements" dropdown. Each entry consists of:
- **Test Name**: The display name (e.g., `"Simple_test_1.5V"`)
- **code_name**: Unique identifier used for analysis and file naming (e.g., `"Simple_1.5V"`)
- **sweeps**: Dictionary of sweep definitions, each numbered sequentially

##### Structure

```json
{
  "Test_Name": {
    "code_name": "unique_code_name",
    "sweeps": {
      "1": { /* sweep 1 parameters */ },
      "2": { /* sweep 2 parameters */ }
    }
  }
}
```

##### Measurement Types

###### 1. DC IV Sweeps

Standard voltage sweeps for I-V characterization. Used for forming, characterization, and half-sweeps.

**Example: Simple IV Sweep**
```json
"Simple_test_1.5V": {
  "code_name": "Simple_1.5V",
  "sweeps": {
    "1": {
      "start_v": 0,
      "stop_v": 0.5,
      "sweeps": 3,
      "step_v": 0.05,
      "step_delay": 0.05
    },
    "2": {
      "start_v": 0,
      "stop_v": 0.8,
      "sweeps": 3,
      "step_v": 0.05,
      "step_delay": 0.05
    }
  }
}
```

**Parameters**:
- `start_v`: Starting voltage (V)
- `stop_v`: Ending voltage (V)
- `sweeps`: Number of loops (typically 3 for bipolar)
- `step_v`: Voltage step size (V)
- `step_delay`: Delay between steps (s)
- `Sweep_type` (optional): `"PS"` (Positive only), `"FS"` (Full sweep), `"NS"` (Negative only)

**Use Case**: Device forming, basic characterization, before/after comparisons

###### 2. Endurance Measurements

Pulse-based endurance testing for cycling stability. Automatically detects pulse patterns and plots resistance vs cycle number.

**Example: Single Endurance Test**
```json
"Endurance_1.5V_10ms_x_50": {
  "code_name": "end_short",
  "sweeps": {
    "1": {
      "mode": "Endurance",
      "set_v": 1.5,
      "reset_v": -1.5,
      "pulse_ms": 10,
      "cycles": 50,
      "read_v": 0.2,
      "LED_ON": 0
    }
  }
}
```

**Parameters**:
- `mode`: `"Endurance"` (required)
- `set_v`: SET pulse voltage (V)
- `reset_v`: RESET pulse voltage (V)
- `pulse_ms`: Pulse width (ms)
- `cycles`: Number of SET/RESET cycles
- `read_v`: Read voltage between pulses (V)
- `LED_ON`: LED state (0=OFF, 1=ON)

**Use Case**: Cycling stability, device lifetime estimation, degradation analysis

###### 3. Combined Endurance Tests

Multiple pulse times tested in sequence for comprehensive endurance analysis.

**Example: Combined Endurance Test**
```json
"Endurance_Combined_1.5V": {
  "code_name": "end_short",
  "sweeps": {
    "1": {"mode": "Endurance", "set_v": 1.5, "reset_v": -1.5, "pulse_ms": 10, "cycles": 50, "read_v": 0.2, "LED_ON": 0},
    "2": {"mode": "Endurance", "set_v": 1.5, "reset_v": -1.5, "pulse_ms": 100, "cycles": 50, "read_v": 0.2, "LED_ON": 0},
    "3": {"mode": "Endurance", "set_v": 1.5, "reset_v": -1.5, "pulse_ms": 500, "cycles": 50, "read_v": 0.2, "LED_ON": 0},
    "4": {"mode": "Endurance", "set_v": 1.5, "reset_v": -1.5, "pulse_ms": 1000, "cycles": 50, "read_v": 0.2, "LED_ON": 0},
    "5": {"mode": "Endurance", "set_v": 1.5, "reset_v": -1.5, "pulse_ms": 2000, "cycles": 50, "read_v": 0.2, "LED_ON": 0}
  }
}
```

**Use Case**: Comparing endurance performance across different pulse times in one measurement

###### 4. Retention Measurements

State retention testing to measure resistance stability over time after programming.

**Example: Single Retention Test**
```json
"Retention__1.5v_10ms": {
  "code_name": "ret_quick",
  "sweeps": {
    "1": {
      "mode": "Retention",
      "set_v": 1.5,
      "set_ms": 10,
      "read_v": 0.2,
      "times_s": [1, 3, 10, 30, 100, 300],
      "LED_ON": 0
    }
  }
}
```

**Parameters**:
- `mode`: `"Retention"` (required)
- `set_v`: Programming pulse voltage (V)
- `set_ms`: Programming pulse width (ms)
- `read_v`: Read voltage for retention checks (V)
- `times_s`: Array of time points to measure retention (seconds)
- `LED_ON`: LED state (0=OFF, 1=ON)

**Use Case**: State stability analysis, retention time estimation, non-volatility validation

###### 5. Combined Retention Tests

Multiple pulse times tested in sequence for comprehensive retention analysis.

**Example: Combined Retention Test**
```json
"Retention_Combined_1.5v": {
  "code_name": "ret_quick",
  "sweeps": {
    "1": {"mode": "Retention", "set_v": 1.5, "set_ms": 10, "read_v": 0.2, "times_s": [1,3,10,30,100,300], "LED_ON": 0},
    "2": {"mode": "Retention", "set_v": 1.5, "set_ms": 100, "read_v": 0.2, "times_s": [1,3,10,30,100,300], "LED_ON": 0},
    "3": {"mode": "Retention", "set_v": 1.5, "set_ms": 1000, "read_v": 0.2, "times_s": [1,3,10,30,100,300], "LED_ON": 0},
    "4": {"mode": "Retention", "set_v": 1.5, "set_ms": 2000, "read_v": 0.2, "times_s": [1,3,10,30,100,300], "LED_ON": 0}
  }
}
```

**Use Case**: Comparing retention performance across different programming pulse times

##### Using Custom Sweeps in the GUI

1. **Select Custom Measurement**: In the Measurement GUI, use the "Custom Measurement" dropdown to select your test
2. **Run Measurement**: Click "Run Custom" to execute the entire sequence
3. **File Naming**: Files are automatically named using the pattern: `{sweep_number}-{parameters}-Py-{code_name}.txt`
4. **Sequential Numbering**: Sweep numbers continue from the highest existing file in the folder to prevent overwrites

##### Code Name Best Practices

- Use consistent code names for similar tests (e.g., `"end_short"` for all endurance tests)
- Use unique code names for different test types (e.g., `"ret_quick"` for retention)
- Code names are used for:
  - File naming
  - Conditional testing workflows
  - Analysis filtering and grouping
  - Plot organization

#### test_configurations.json

**Location**: `Json_Files/test_configurations.json`

This file defines how measurements are analyzed and plotted. Each `code_name` from `Custom_Sweeps.json` can have an entry here that specifies:

- **sweep_combinations**: Array of sweep number combinations to plot together
- **main_sweep**: Primary sweep number for analysis (typically the forming/characterization sweep)

##### Structure

```json
{
  "code_name": {
    "sweep_combinations": [
      {
        "sweeps": [1, 2],
        "title": "Plot Title"
      }
    ],
    "main_sweep": 1
  }
}
```

##### Examples

###### 1. Simple IV Sweep Configuration

For `Simple_1.5V` test:
```json
"Simple_1.5V": {
  "sweep_combinations": [
    {
      "sweeps": [1, 9],
      "title": "Same voltage sweep before and after forming"
    },
    {
      "sweeps": [2, 8],
      "title": "Same voltage sweep before and after forming"
    },
    {
      "sweeps": [5],
      "title": "Main Sweep"
    },
    {
      "sweeps": [10, 11, 12, 13],
      "title": "Combination of Half Sweeps All"
    }
  ],
  "main_sweep": 5
}
```

**Analysis Behavior**:
- Individual plots for each sweep combination
- Before/after forming comparisons
- Half-sweep combinations for PS/NS analysis

###### 2. Combined Endurance Configuration

For `end_combined` test:
```json
"end_combined": {
  "sweep_combinations": [
    {
      "sweeps": [1],
      "title": "Endurance - 10ms pulse"
    },
    {
      "sweeps": [2],
      "title": "Endurance - 100ms pulse"
    },
    {
      "sweeps": [3],
      "title": "Endurance - 500ms pulse"
    },
    {
      "sweeps": [4],
      "title": "Endurance - 1s pulse"
    },
    {
      "sweeps": [5],
      "title": "Endurance - 2s pulse"
    },
    {
      "sweeps": [1, 2, 3, 4, 5],
      "title": "All Endurance Pulses Combined"
    }
  ],
  "main_sweep": 1
}
```

**Analysis Behavior**:
- Individual plots for each pulse time (resistance vs cycle)
- Combined plot with all pulse times overlaid for comparison
- Specialized endurance metrics and degradation tracking

###### 3. Combined Retention Configuration

For `ret_combined` test:
```json
"ret_combined": {
  "sweep_combinations": [
    {
      "sweeps": [1],
      "title": "Retention - 10ms pulse"
    },
    {
      "sweeps": [2],
      "title": "Retention - 100ms pulse"
    },
    {
      "sweeps": [3],
      "title": "Retention - 1s pulse"
    },
    {
      "sweeps": [4],
      "title": "Retention - 2s pulse"
    },
    {
      "sweeps": [1, 2, 3, 4],
      "title": "All Retention Pulses Combined"
    }
  ],
  "main_sweep": 1
}
```

**Analysis Behavior**:
- Individual plots for each pulse time (resistance vs time)
- Combined plot with all pulse times overlaid for comparison
- Retention time estimation and decay analysis

###### 4. Quick Test Configuration

For single-sweep tests:
```json
"end_short": {
  "sweep_combinations": [
    {
      "sweeps": [1],
      "title": "Endurance Single Test"
    }
  ],
  "main_sweep": 1
}
```

**Analysis Behavior**:
- Single plot for the one sweep
- Standard endurance or retention analysis depending on mode

##### How Analysis Uses test_configurations.json

When running the "Full Sample Analysis" in the Analysis tab:

1. **Code Name Detection**: The system finds all unique `code_name` values from measurement files
2. **Configuration Lookup**: For each code name, it looks up the corresponding entry in `test_configurations.json`
3. **Sweep Identification**: Uses `main_sweep` or finds the minimum sweep number for the code name to identify the "first" measurement
4. **Plot Generation**: Creates plots for each `sweep_combination` entry:
   - **Individual Plots**: Each sweep combination gets its own plot
   - **Combined Plots**: Multiple sweeps in one combination are overlaid
5. **Specialized Analysis**: 
   - Endurance: Plots resistance vs cycle with degradation tracking
   - Retention: Plots resistance vs time with retention time estimation
   - IV Sweeps: Standard I-V curves with hysteresis analysis

##### Best Practices for test_configurations.json

1. **Match code_names**: Ensure every `code_name` in `Custom_Sweeps.json` has an entry (or use a default)
2. **Meaningful Titles**: Use descriptive titles that explain what the plot shows
3. **Logical Groupings**: Group related sweeps together (e.g., before/after forming, different voltages)
4. **Combined Views**: Add combined entries to compare multiple conditions
5. **Main Sweep**: Set `main_sweep` to the most important/representative sweep for analysis

##### Complete Workflow Example

**Step 1: Define Custom Sweep** (`Custom_Sweeps.json`)
```json
"My_Endurance_Test": {
  "code_name": "my_end_test",
  "sweeps": {
    "1": {"mode": "Endurance", "set_v": 2.0, "reset_v": -2.0, "pulse_ms": 50, "cycles": 100, "read_v": 0.2, "LED_ON": 0}
  }
}
```

**Step 2: Define Analysis Configuration** (`test_configurations.json`)
```json
"my_end_test": {
  "sweep_combinations": [
    {
      "sweeps": [1],
      "title": "My Endurance Test"
    }
  ],
  "main_sweep": 1
}
```

**Step 3: Run Measurement**
- Select "My_Endurance_Test" from Custom Measurement dropdown
- Click "Run Custom"
- File saved as: `{sweep_number}-Endurance-{params}-Py-my_end_test.txt`

**Step 4: Run Analysis**
- Go to Analysis tab
- Select "Full Sample Analysis"
- System detects `code_name="my_end_test"`
- Uses `test_configurations.json` to generate endurance plot (resistance vs cycle)
- Analysis includes: degradation metrics, cycle-to-cycle consistency, switching ratio evolution

## TSP Testing System (Keithley 2450)

Fast, buffer-based pulse testing with real-time visualization for Keithley 2450 in TSP mode.

### Key Files

- **Controller**: `Equipment/SMU_AND_PMU/Keithley2450_TSP.py` (TSP command interface)
- **Test Scripts**: `Equipment/SMU_AND_PMU/keithley2450_tsp_scripts.py` (pre-configured test patterns)
- **GUI**: `gui/pulse_testing_gui/` (TSPTestingGUI class)

### Features

- **Front/Rear Terminal Selection**: Toggle between front panel and rear BNC terminals via radio buttons. Default selection is automatically saved and restored.

- **Fast On-Instrument Execution**: All test scripts run entirely on the instrument (no PC communication during tests), enabling sub-millisecond pulse generation with high timing accuracy.

- **Buffer-Based Measurements**: All measurements use instrument buffers for fast, accurate data collection with proper timestamp handling.

- **Correct Setting Order**: All functions follow Keithley manual specifications (measure function/range set first, then source settings) to prevent errors 5076/5077.

### Available Test Patterns

- **Pulse-Read-Repeat**: (Pulse → Read → Delay) × N cycles
- **Multi-Pulse-Then-Read**: (Pulse×N → Read×M) × Cycles
- **Varying Width Pulses**: Sweep different pulse widths
- **Potentiation/Depression**: Gradual SET/RESET cycles
- **Endurance Test**: (SET → Read → RESET → Read) × N cycles
- **Retention Test**: Pulse followed by timed reads
- **Relaxation Tests**: Multi-pulse with relaxation monitoring
- **Width Sweeps**: Systematic pulse width characterization
- **Current Range Finder**: Test multiple current ranges to find optimal measurement range

### Terminal Configuration

- **Front Panel**: Standard front binding posts (FORCE HI/LO, SENSE HI/LO)
- **Rear Panel**: BNC connectors for remote connections
  - **Force HI**: Source positive (BNC center)
  - **Force LO**: Source return (BNC center)
  - **Sense HI**: Voltage sense positive (BNC center)
  - **Sense LO**: Voltage sense negative (BNC center)
- Terminal selection persists until changed and is saved as default preference

## PMU System (Keithley 4200A)

Waveform-accurate measurements using Keithley 4200A PMU channels.

### Key Files

- **Controller**: `Equipment/SMU_AND_PMU/Keithley4200A.py` (`Keithley4200A_PMUDualChannel` low-level helper)
- **Service**: `Measurements/measurement_services_pmu.py` (`MeasurementServicesPMU` high-level API)
- **GUI**: `PMU_Testing_GUI.py` (connect PMU + function generator, preview waveforms, run measurement, view results)

### Available Measurements

- **Single Laser Pulse with Read**
  - PMU sources a pulse train; TRIG OUT drives the function generator (FG) which emits a laser pulse.
  - Enforced checks: FG pulse_width_s ≥ PMU active time; safety dialogs require laser OFF (before arming) and ON (before run).
  - Parameters:
    - PMU: amplitude_v, width_s, period_s (or auto via width_s), num_pulses, ranges, measurement window.
    - FG: period_s, high_level_v, cycles, trigger_source=EXT; pulse_width_s auto set to match PMU active time.
  - API entrypoint: `MeasurementServicesPMU.Single_Laser_Pulse_with_read(pmu_params, fg_params)`

#### PMU Parameters

| Name | Description |
|------|-------------|
| amplitude_v | Pulse amplitude (V) on source channel |
| width_s | Pulse width (s) |
| period_s | Pulse-to-pulse period (s) |
| num_pulses | Number of pulses in the burst |
| v_meas_range | Voltage measurement range (V) |
| i_meas_range | Current measurement range (A) |
| meas_start_pct | Start of capture window (fraction of width) |
| meas_stop_pct | End of capture window (fraction of width) |

#### FG Parameters

| Name | Description |
|------|-------------|
| channel | Output channel index (e.g., 1) |
| period_s | Generator period (s) |
| pulse_width_s | Generator pulse width (s); auto-set to PMU active time |
| high_level_v | Generator high level (V) |
| cycles | Burst cycles (e.g., 1 for single) |
| trigger_source | Should be `EXT` to use PMU TRIG OUT |

### Preview and Results

- **PMU Preview Figure** (in GUI):
  - Top: expected PMU voltage vs time
  - Bottom: expected FG output vs time
- **Latest Data Preview** (GUI):
  - Plots acquired data (time vs V and I) separate from the preview.
  - CH1 displayed; CH2 plotting is planned.

### Minimal Example

```python
from Equipment.SMU_AND_PMU.Keithley4200A import Keithley4200A_PMUDualChannel
from Equipment.managers.function_generator import FunctionGeneratorManager
from Measurements.measurement_services_pmu import MeasurementServicesPMU

pmu = Keithley4200A_PMUDualChannel("192.168.0.10:8888|PMU1")
fg = FunctionGeneratorManager(fg_type="Siglent SDG1032X", address="USB0::...::INSTR", auto_connect=True)
ms = MeasurementServicesPMU(pmu=pmu, function_generator=fg)

pmu_params = {"amplitude_v": 0.25, "width_s": 50e-6, "period_s": 200e-6, "num_pulses": 100}
fg_params  = {"channel": 1, "period_s": 1.0, "high_level_v": 1.5, "cycles": 1, "trigger_source": "EXT"}
df = ms.Single_Laser_Pulse_with_read(pmu_params, fg_params, timeout_s=15.0)
```

## Notifications

The system includes Telegram bot integration for remote notifications and interactive control.

### Telegram Bot

**Location**: `Notifications/telegram_bot.py`

**Features**:
- Send measurement notifications
- Send images/plots
- Interactive Q&A sessions
- Non-blocking, thread-safe implementation

**Usage**:
```python
from Notifications import TelegramBot

bot = TelegramBot(token="YOUR_BOT_TOKEN", chat_id="YOUR_CHAT_ID")
bot.send_message("Measurement complete!")
bot.send_image("plot.png", caption="IV Curve Results")

# Ask interactive questions
response = bot.ask_and_wait(
    question="Continue test?",
    choices={"1": "Yes", "2": "No", "3": "Skip"},
    timeout_s=60
)
```

**See**: [Notifications/README.md](Notifications/README.md) for detailed documentation.

## Safety & Limits

- **SMU-specific minimum pulse width** enforced via SMULimits. Defaults are set per model (e.g., 2400/2401 ≥ 1 ms).
- **Planned**: Optional guard to abort on excessive current jump between samples.

## Timing and "Fast" Pulses

SMU-driven pulses are limited by instrument command latency and OS scheduling; they are appropriate for millisecond-scale pulses, not microseconds.

- **SMU limits**: `SMULimits.min_pulse_width_ms` enforces device-specific minima (e.g., 2400/2401 ≥ 1 ms). Sub-ms accuracy requires a PMU.

- **Implementation details**:
  - `MeasurementService.run_pulse_measurement` sets the pulse voltage, then busy-waits the pulse duration using ~1 ms sleeps, returns to Vbase, waits ~2 ms for settling, then reads.
  - Inter-pulse delay is user-configurable; "Max speed" can set it to 0, bounded by device limits.

- **Python/OS timing**: `time.sleep(0.001)` is not hard real-time; actual resolution and jitter depend on the OS scheduler (on Windows typically ~1 ms best case). Expect a few ms of timing uncertainty on SMU pulses.

- **Recommendation**: For sub-ms or waveform-accurate pulses, use the PMU flows (see PMU_Testing_GUI and PMU_* methods in `measurement_services_pmu.py`).

## Code Map (Where to Look)

### Core Services

- **SMU Measurements**: `Measurements/measurement_services_smu.py`
  - DC Triangle IV: `run_iv_sweep(...)`
  - SMU Pulsed IV: `run_pulse_measurement(...)`, `run_pulsed_iv_sweep(...)`
  - SMU Fast Hold: `run_dc_capture(...)`
  - ISPP: `run_ispp(...)`
  - Pulse Width Sweep: `run_pulse_width_sweep(...)`
  - Threshold Search: `run_threshold_search(...)`

- **PMU Measurements**: `Measurements/measurement_services_pmu.py`
  - Single Laser Pulse: `Single_Laser_Pulse_with_read(...)`

- **Connection Management**: `Measurements/connection_manager.py`
  - Unified instrument connection management
  - Handles SMU, PSU, temperature controller connections

### GUI Components

- **Sample GUI**: `gui/sample_gui/main.py` - Device selection and sample management
- **Measurement GUI**: `gui/measurement_gui/main.py` - Main measurement interface
  - Layout: `gui/measurement_gui/layout_builder.py`
  - Plotting: `gui/measurement_gui/plot_panels.py`, `plot_updaters.py`
  - Custom Measurements: `gui/measurement_gui/custom_measurements_builder.py`
- **Pulse Testing GUI**: `gui/pulse_testing_gui/main.py` - Fast pulse testing
- **Motor Control GUI**: `gui/motor_control_gui/main.py` - XY stage control
- **Connection Check GUI**: `gui/connection_check_gui/main.py` - Connection verification

### Volatile Tests

Available in Measurement GUI via "More Tests → Volatile":

- **Transient Decay**: Single pulse then I(t) at Vread; saves time-series.
- **PPF (Paired-Pulse Facilitation)**: Two pulses with Δt; PPF index vs Δt.
- **STDP**: Pre/post with Δt (±); Δw vs Δt.
- **SRDP**: Frequency trains; steady-state vs rate (Hz).
- **Potentiation/Depression**: Alternate +/− pulses; immediate/post reads; volatility ratio.
- **Frequency Response**: Average read after pulses at each frequency.
- **Bias-dependent Decay**: Run multiple transients at different Vread; concatenated time series.
- **Noise/RTN**: Low-bias I(t) capture for noise analysis.

## Camera System

The camera system provides local USB viewing and Ethernet streaming capabilities for remote monitoring and motor control integration.

### Modes

**USB Mode** - Local camera viewing:
```python
from Equipment.managers.camera import CameraManager

camera = CameraManager.create_usb(camera_index=0, resolution=(1280, 720), fps=30)
frame = camera.get_frame()  # Get latest frame for processing
```

**Server Mode** - Stream video over Ethernet:
```python
# On streaming laptop
config = {
    'camera_type': 'Thorlabs',
    'mode': 'server',
    'camera_index': 0,
    'port': 8485
}
camera = CameraManager.from_config(config, auto_connect=True)
```

**Client Mode** - Receive video stream:
```python
# On receiving laptop
config = {
    'camera_type': 'Thorlabs',
    'mode': 'client',
    'server_ip': '192.168.1.100',  # Server laptop IP
    'port': 8485
}
camera = CameraManager.from_config(config, auto_connect=True)
frame = camera.get_frame()
```

### Features

- **Frame Callbacks**: Set callbacks on new frames for motor control integration
- **Thread-Safe**: Safe concurrent access to frames
- **Configurable**: Resolution, FPS, and quality settings
- **Test Viewer**: Run `python Equipment/Camera/view_camera.py` for GUI viewer

### Test Script

The camera viewer provides a simple GUI for testing:
```bash
# View camera feed (default camera index 0)
python Equipment/Camera/view_camera.py

# Specify camera index
python Equipment/Camera/view_camera.py 1
```

**Controls:**
- `'q'` - Quit
- `'s'` - Save screenshot
- `'r'` - Show resolution info
- `'f'` - Show FPS

### Motor Control Integration

The camera system is designed for integration with motor control:
- Frame callbacks can trigger motor movements based on visual feedback
- USB mode provides low-latency local viewing
- Ethernet streaming enables remote monitoring from control laptop
- All modes support `set_frame_callback()` for real-time processing

## Dependencies

### Core Dependencies
- Python 3.8+
- tkinter (Python standard library)
- matplotlib
- numpy
- PIL/Pillow

### Hardware Dependencies (Optional)
- python-telegram-bot (for Telegram notifications)
- pymeasure (for some Keithley instruments)
- pylablib (for Thorlabs motor control)
- pyvisa (for VISA instruments)
- opencv-python (for camera support)

See `requirements.txt` for complete list.

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd Switchbox_GUI

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Running the Application

```bash
# Start the main application
python main.py
```

### Programmatic Usage

```python
# Import GUI modules
from gui.sample_gui import SampleGUI
from gui.measurement_gui import MeasurementGUI
from gui.pulse_testing_gui import TSPTestingGUI

# Import equipment managers
from Equipment.managers.iv_controller import IVControllerManager
from Equipment.managers.camera import CameraManager

# Import measurement services
from Measurements.measurement_services_smu import MeasurementService

# Import notifications
from Notifications import TelegramBot
```

### Standalone GUI Testing

Individual GUIs can be run standalone for testing:

```python
# Pulse Testing GUI
python -m gui.pulse_testing_gui.main

# Motor Control GUI
python -m gui.motor_control_gui.main

# Connection Check GUI
python -m gui.connection_check_gui.main
```

## Configuration Files

Configuration files are located in `Json_Files/`:

- **`system_configs.json`**: Instrument addresses and system configurations
- **`mapping.json`**: Device layout mappings
- **`pin_mapping.json`**: Device pin mappings for multiplexer control
- **`Custom_Sweeps.json`**: Custom measurement sweep configurations (see Custom Sweeps section above for detailed examples)
- **`test_configurations.json`**: Analysis and plotting configurations for each code_name (see Custom Sweeps section above for detailed examples)
- **`classification_weights.json`**: Device classification scoring weights
- **`messaging_data.json`**: Example Telegram bot config (use **`messaging_data.local.json`** for real tokens; see `Json_Files/MESSAGING_README.md`)
- **`save_location_config.json`**: Data save location preferences

## Notes

- **PMU-based measurements** are available separately (see PMU_Testing_GUI) for accurate waveform capture.
- **TSP Testing GUI** requires Keithley 2450 to be in TSP mode (not SCPI). Switch via: MENU → System → Settings → Command Set → TSP
- **Terminal selection** (front/rear) is saved automatically and persists across sessions
- **All TSP functions** now use correct setting order (measure function/range first) to prevent instrument errors
- **Camera system** uses OpenCV; ensure camera drivers are installed for USB mode
- **For Ethernet streaming**, ensure both laptops are on the same network and firewall allows the port (default: 8485)
- **Equipment managers** use lazy imports - missing dependencies won't crash the application
- **Backward compatibility**: Root-level wrapper files maintain old import paths for compatibility

## Documentation

- **GUI Documentation**: [gui/README.md](gui/README.md)
- **Notifications Documentation**: [Notifications/README.md](Notifications/README.md)
- **User Guide**: [Documents/USER_GUIDE.md](Documents/USER_GUIDE.md)
- **Quick Reference**: [Documents/QUICK_REFERENCE.md](Documents/QUICK_REFERENCE.md)
- **JSON Configuration Guide**: [Documents/JSON_CONFIG_GUIDE.md](Documents/JSON_CONFIG_GUIDE.md)

## License

[Add your license information here]

## Contributing

[Add contributing guidelines here if applicable]
