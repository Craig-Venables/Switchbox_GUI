# Switchbox_GUI

## About
- Real-time graphing (multiple plots, live updates)
- Temperature measurement/manager ready (ITC/Lakeshore)
- LED control via PSU
- Bot messaging (Telegram) for remote prompts/updates
- Auto-saving data with device/sample folders and incrementing filenames
- Beep on instrument connect
- Sequential measurement across devices

## Current Multiplexers
- PySwitchbox: 100-device array (Raven’s creation), Arduino-controlled relay box
- Multiplexer: simple 1–10 selector (positive inner, negative outer) for basic routing

## Systems
### Smu (Keithleys)
- Keithley 2400 (SMU)
- Keithley 2401 (SMU)
- Keithley 2450 (TSP mode; fast pulse generation; front/rear terminal selection)
- Keithley 4200A_smu (SMU)
- Keithley 4200A_pmu (PMU; waveform capture; in-progress integration)
- HP4140B (classic picoammeter/SMU)

### Temp Controllers
- TemperatureControllerManager abstraction (supports Lakeshore 335, Oxford ITC4)

### Power Supplies (LED control)
- Keithley 2220 (used for LED driving)

### Function Generators
- Siglent (triggered pulses)
- Moku Go (in the works)

### Cameras
- Thorlabs Camera System (USB and Ethernet streaming)
  - **USB Mode**: Local camera viewing for direct monitoring
  - **Server Mode**: Stream video from one laptop to another over Ethernet
  - **Client Mode**: Receive and display video stream from remote server
  - **Motor Control Integration**: Frame callbacks available for automated positioning
  - Test script: `Equipment/Camera/view_camera.py` provides GUI viewer
  - Manager: `Equipment/camera_manager.py` for unified camera interface

### Motor Control
- Thorlabs Kinesis Linear Stages (X/Y axes)
  - Controller: `Equipment/Motor_Controll/Kenisis_motor_control.py`
  - GUI: `Motor_Controll_GUI.py`
  - Camera integration ready for visual positioning feedback

## Measurement Types

- DC Triangle IV: Classic FS/PS/NS triangle sweep. Configurable by Sweep Mode (fixed step, fixed sweep rate, fixed voltage time), Sweep Type (FS/PS/NS), Step/Delay or rate/time.

- SMU Pulsed IV: One pulse per amplitude across a range; device returns to Vbase and a read is taken. Use when you want reduced self-heating compared with DC IV.

- SMU Fast Pulses: Pulse train at fixed amplitude and width; measure at Vbase after each pulse. Good for endurance-like stress.

- SMU Fast Hold: Hold a DC bias and sample current vs time (I–t). Useful for stress/recovery or quick retention checks.

- ISPP: Incremental Step Pulse Programming. Increase pulse amplitude stepwise until hitting a target current/resistance. Produces amplitude vs response curves.

- Pulse Width Sweep: Fixed amplitude, sweep pulse width; read at Vbase; width vs response.

- Threshold Search: Find Vset/Vreset using binary/gradient search with minimal pulses.

## Visuals (concept sketches)

- DC Triangle IV
```
V: /\\/\\
I: response vs V
```

- SMU Pulsed IV (Amplitude Sweep)
```
A: [A1 A2 A3 ...]
Pulse: |‾‾|   |‾‾|   |‾‾|
Read:   r1     r2     r3   at Vbase
Plot: A vs I_read
```

- SMU Fast Pulses
```
Pulse train: |‾| |‾| |‾| |‾| ... (fixed A, width)
Reads: after each at Vbase
```

- SMU Fast Hold
```
V(t) = Vhold (flat)
I(t) sampled regularly
```

- ISPP (Amplitude Ramp to Target)
```
Amps:  0.2  0.3  0.4  0.5 ...
Iread: i1   i2   i3*           (* ≥ target)
Plot: Amplitude vs I_read
```

- Pulse Width Sweep (Fixed Amplitude)
```
Widths (ms):  1   2   5   10 ...
I_read:       i1  i2  i3  i4
Plot: width vs I_read
```

- Threshold Search (Binary Search on V)
```
Range: [Vlow --------------------- Vhigh]
Test mid -> I(mid) ? target -> shrink range toward threshold
Repeat until |Vhigh - Vlow| small
```

## Safety & Limits

- SMU-specific minimum pulse width enforced via SMULimits. Defaults are set per model (e.g., 2400/2401 ≥ 1 ms).
- Planned: optional guard to abort on excessive current jump between samples.

## Timing and "Fast" Pulses

SMU-driven pulses are limited by instrument command latency and OS scheduling; they are appropriate for millisecond-scale pulses, not microseconds.

- SMU limits: `SMULimits.min_pulse_width_ms` enforces device-specific minima (e.g., 2400/2401 ≥ 1 ms). Sub-ms accuracy requires a PMU.
- Implementation details:
  - `MeasurementService.run_pulse_measurement` sets the pulse voltage, then busy-waits the pulse duration using ~1 ms sleeps, returns to Vbase, waits ~2 ms for settling, then reads.
  - Inter-pulse delay is user-configurable; "Max speed" can set it to 0, bounded by device limits.
- Python/OS timing: `time.sleep(0.001)` is not hard real-time; actual resolution and jitter depend on the OS scheduler (on Windows typically ~1 ms best case). Expect a few ms of timing uncertainty on SMU pulses.
- Recommendation: For sub-ms or waveform-accurate pulses, use the PMU flows (see PMU_Testing_GUI and PMU_* methods in `measurement_service.py`).

## Specific Measurements
### Volatile
- Transient Decay: single pulse then sample I(t) at Vread (extract τ / power-law).
  Sketch: `|‾‾|____` then hold Vread → I(t) decays.
- PPF: two identical pulses separated by Δt; PPF index vs Δt.
  Sketch: `|‾‾|__Δt__|‾‾|` → measure I1 and I2 @ Vread; PPF=(I2−I1)/|I1|.
- STDP: pre/post pulses with Δt (±); Δw vs Δt curve.
- SRDP: trains at different frequencies; steady-state/current gain vs rate.
- Potentiation/Depression: alternating +/− short pulses; immediate and post-delay reads; volatility ratio.
- Frequency Response: sweep pulse frequency (fixed width/amplitude); response vs frequency.
- Dynamic Threshold (volatile): minimal pulse amplitude/width that elicits transient change (binary/gradient).
- Bias-dependent Volatility: repeat transients at multiple Vread; map decay constants vs bias.
- Temperature-dependent Volatility: repeat at several temperatures; Arrhenius for decay time (future).
- Noise/RTN: low-bias I(t) segments for PSD/variance.

### Nonvolatile
- (reserved for future: long retention, endurance, MLC program/verify, half-select disturb, etc.)

## Custom Sweeps

- Each sweep can set a `measurement type` within the GUI. For custom JSON, an `excitation` key enables pulse modes (examples provided in `Json_Files/Custom_Sweeps.json`).

## Signal Messaging
- Optional Telegram bot integration to drive interactive flows (start/continue tests, send plots/images).

## TSP Testing System (Keithley 2450)

- **Controller**: `Equipment/SMU_AND_PMU/Keithley2450_TSP.py` (TSP command interface)
- **Test Scripts**: `Equipment/SMU_AND_PMU/keithley2450_tsp_scripts.py` (pre-configured test patterns)
- **GUI**: `TSP_Testing_GUI.py` (fast pulse testing with real-time visualization)

### Features

- **Front/Rear Terminal Selection**: Toggle between front panel and rear BNC terminals via radio buttons in the connection section. Default selection is automatically saved and restored on next startup.

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

## PMU System (current capabilities)

- Controller: `Equipment/SMU_AND_PMU/Keithley4200A.py` (`Keithley4200A_PMUDualChannel` low-level helper)
- Service: `Measurments/measurement_services_pmu.py` (`MeasurementServicesPMU` high-level API)
- GUI: `PMU_Testing_GUI.py` (connect PMU + function generator, preview waveforms, run measurement, view results)

- Reference: see `Equipment/SMU_AND_PMU/PMU_Step_Sweep_Reference.md` for PMU step vs sweep and sweep types.

### Available measurement
- Single Laser Pulse with read
  - PMU sources a pulse train; TRIG OUT drives the function generator (FG) which emits a laser pulse.
  - Enforced checks: FG pulse_width_s ≥ PMU active time; safety dialogs require laser OFF (before arming) and ON (before run).
  - Parameters:
    - PMU: amplitude_v, width_s, period_s (or auto via width_s), num_pulses, ranges, measurement window.
    - FG: period_s, high_level_v, cycles, trigger_source=EXT; pulse_width_s auto set to match PMU active time.
  - API entrypoint: `MeasurementServicesPMU.Single_Laser_Pulse_with_read(pmu_params, fg_params)`

#### Parameter summary

PMU parameters

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

FG parameters

| Name | Description |
|------|-------------|
| channel | Output channel index (e.g., 1) |
| period_s | Generator period (s) |
| pulse_width_s | Generator pulse width (s); auto-set to PMU active time |
| high_level_v | Generator high level (V) |
| cycles | Burst cycles (e.g., 1 for single) |
| trigger_source | Should be `EXT` to use PMU TRIG OUT |

### Preview and results
- PMU preview figure (in GUI):
  - Top: expected PMU voltage vs time
  - Bottom: expected FG output vs time
- Latest Data Preview (GUI):
  - Plots acquired data (time vs V and I) separate from the preview.
  - CH1 displayed today; CH2 plotting is planned.

### Utilities and helpers
- Runtime estimator: `estimate_runtime_from_params(pmu_params, fg_params)` returns a breakdown including `pmu_active_s` and `total_estimate_s`.
- Low-level PMU methods (via `Keithley4200A_PMUDualChannel`):
  - `prepare_measure_at_voltage(...)`, `start()`, `wait(...)`, `fetch(...)`
  - Trigger helpers: `set_trigger_output(...)`, `set_trigger_polarity(...)`

### Minimal example (script)
```python
from Equipment.SMU_AND_PMU.Keithley4200A import Keithley4200A_PMUDualChannel
from Equipment.function_generator_manager import FunctionGeneratorManager
from Measurments.measurement_services_pmu import MeasurementServicesPMU

pmu = Keithley4200A_PMUDualChannel("192.168.0.10:8888|PMU1")
fg = FunctionGeneratorManager(fg_type="Siglent SDG1032X", address="USB0::...::INSTR", auto_connect=True)
ms = MeasurementServicesPMU(pmu=pmu, function_generator=fg)

pmu_params = {"amplitude_v": 0.25, "width_s": 50e-6, "period_s": 200e-6, "num_pulses": 100}
fg_params  = {"channel": 1, "period_s": 1.0, "high_level_v": 1.5, "cycles": 1, "trigger_source": "EXT"}
df = ms.Single_Laser_Pulse_with_read(pmu_params, fg_params, timeout_s=15.0)
```

## Equipment Managers

All equipment follows a unified manager pattern for easy configuration and initialization:

- **SMU/PMU**: `Equipment/SMU_AND_PMU/` (Keithley controllers)
- **Temperature Controllers**: `Equipment/temperature_controller_manager.py` (Lakeshore, Oxford)
- **Function Generators**: `Equipment/function_generator_manager.py` (Siglent, Moku)
- **Cameras**: `Equipment/camera_manager.py` (Thorlabs USB/Ethernet)
- **Laser Controllers**: `Equipment/laser_manager.py` (Oxxius)
- **Power Supplies**: `Equipment/power_supply_manager.py` (Keithley 2220)
- **Ammeters**: `Equipment/ammeter_manager.py` (Agilent)
- **Multiplexers**: `Equipment/multiplexer_manager.py` (PySwitchbox, Electronic)
- **Oscilloscopes**: `Equipment/oscilloscope_manager.py` (Tektronix, GW Instek)
- **Motor Control**: `Equipment/Motor_Controll/Kenisis_motor_control.py` (Thorlabs Kinesis)

All managers support `from_config()` for configuration-based initialization.

## Code Map (where to look)

- Volatile Tests (GUI: More Tests → Volatile)
  - Transient Decay: single pulse then I(t) at Vread; saves time-series.
    Sketch:
    ```
    |‾‾|____  then hold Vread → I(t) decays
    ```
  - PPF (Paired-Pulse Facilitation): two pulses with Δt; PPF index vs Δt.
    ```
    |‾‾|__Δt__|‾‾| → measure I1 and I2 @ Vread; PPF=(I2−I1)/|I1|
    ```
  - STDP: pre/post with Δt (±); Δw vs Δt.
    ```
    pre at t0, post at t0+Δt (or reversed), measure Δw = (I_after−I0)/|I0|
    ```
  - SRDP: frequency trains; steady-state vs rate (Hz).
    ```
    train at f=1,5,10… → measure I_ss
    ```
  - Potentiation/Depression: alternate +/− pulses; immediate/post reads; volatility ratio.
  - Frequency Response: average read after pulses at each frequency.
  - Bias-dependent Decay: run multiple transients at different Vread; concatenated time series.
  - Noise/RTN: low-bias I(t) capture for noise analysis.

- Core service (measurement logic): `measurement_service.py`
  - DC Triangle IV: `run_iv_sweep(...)`
  - SMU Pulsed IV: `run_pulse_measurement(...)` (single/sequence), `run_pulsed_iv_sweep(...)` (amplitude sweep)
  - SMU Fast Hold: `run_dc_capture(...)`
  - ISPP: `run_ispp(...)`
  - Pulse Width Sweep: `run_pulse_width_sweep(...)`
  - Threshold Search: `run_threshold_search(...)`

- GUI wiring and controls: `Measurement_GUI.py`
  - More Tests popup (Volatile): `advanced_tests_gui.py`
  - Measurement Type dropdown and dynamic panels: `create_sweep_parameters(...)`
  - Execution branching and saving: `start_measurement(...)` (branches on Measurement Type)

## Camera System

The camera system provides local USB viewing and Ethernet streaming capabilities for remote monitoring and motor control integration.

### Modes

**USB Mode** - Local camera viewing:
```python
from Equipment.camera_manager import CameraManager

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

## Notes

- PMU-based measurements are available separately (see PMU_Testing_GUI) for accurate waveform capture.
- TSP Testing GUI requires Keithley 2450 to be in TSP mode (not SCPI). Switch via: MENU → System → Settings → Command Set → TSP
- Terminal selection (front/rear) is saved automatically and persists across sessions
- All TSP functions now use correct setting order (measure function/range first) to prevent instrument errors
- Camera system uses OpenCV; ensure camera drivers are installed for USB mode
- For Ethernet streaming, ensure both laptops are on the same network and firewall allows the port (default: 8485)



