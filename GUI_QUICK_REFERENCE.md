# GUI Quick Reference Guide

## Which GUI Should I Use?

### 🎯 Starting Point: Sample_GUI
**File**: `Sample_GUI.py`  
**When to use**: Always start here! This is the main entry point.

**What it does**:
- Shows device map/image
- Lets you select which devices to test
- Controls multiplexer routing
- Tracks device status

**How to start**:
```bash
python main.py
```

**What happens next**: After selecting devices, click "Start Measurement" to launch MeasurementGUI.

---

### 📊 Main Measurement Interface: Measurement_GUI
**File**: `Measurement_GUI.py`  
**When to use**: After selecting devices in Sample_GUI, or when you need to run IV sweeps and measurements.

**What it does**:
- Configure IV sweeps
- Connect to instruments (SMU, PSU, temperature controllers)
- Run measurements on selected devices
- Real-time plotting
- Save measurement data

**How to access**: Launched automatically from Sample_GUI when you click "Start Measurement".

**From here you can launch**:
- Pulse Testing (TSP_Testing_GUI)
- Connection Check (Check_Connection_GUI)
- Advanced Tests (advanced_tests_gui)
- Motor Control (Motor_Controll_GUI)
- Automated Tester (Automated_tester_GUI)

---

### ⚡ Pulse Testing: TSP_Testing_GUI
**File**: `TSP_Testing_GUI.py`  
**When to use**: When you need to run pulse-based tests (pulse-read-repeat, width sweeps, endurance, etc.)

**What it does**:
- Pulse-read-repeat tests
- Width sweeps
- Potentiation/depression cycles
- Endurance testing
- Real-time pulse visualization

**How to access**:
1. From MeasurementGUI: Click "Pulse Testing" button
2. Standalone: Can be launched directly (see file docstring)

**Supports**: Keithley 2450 (TSP) and Keithley 4200A-SCS (KXCI)

---

### 🔌 Connection Check: Check_Connection_GUI
**File**: `Check_Connection_GUI.py`  
**When to use**: Before running measurements, to verify your probes are making good contact.

**What it does**:
- Applies small DC bias
- Monitors current in real-time
- Audio alerts when connection is detected
- Quick verification tool

**How to access**: From MeasurementGUI, click "Check Connection" button.

---

### 🧪 Advanced Tests: advanced_tests_gui
**File**: `advanced_tests_gui.py`  
**When to use**: For specialized volatile memristor tests (PPF, STDP, SRDP, transient decay).

**What it does**:
- Transient decay measurements
- Paired-pulse facilitation (PPF)
- Spike-timing dependent plasticity (STDP)
- Rate-dependent plasticity (SRDP)

**How to access**: From MeasurementGUI, click "Advanced Tests" button.

---

### 🎮 Motor Control: Motor_Controll_GUI
**File**: `Motor_Controll_GUI.py`  
**When to use**: When you need to control XY stage motors for laser positioning.

**What it does**:
- XY stage control
- Position presets
- Scanning capabilities
- Function generator integration

**How to access**: 
- From MeasurementGUI: Click "Motor Control" button
- Standalone: Can be launched directly

---

### 🤖 Automated Tester: Automated_tester_GUI
**File**: `Automated_tester_GUI.py`  
**When to use**: For automated batch testing of multiple devices.

**What it does**:
- Automated measurement sequences
- Batch device testing
- Result tracking

**How to access**: From MeasurementGUI, click "Automated Tester" button.

---

## Typical Workflow

```
1. Start Application
   └─> python main.py
       └─> Sample_GUI opens

2. Select Devices
   └─> Click devices on map
       └─> Click "Start Measurement"
           └─> MeasurementGUI opens

3. Connect Instruments
   └─> In MeasurementGUI, connect SMU/PSU/Temp controllers

4. Choose Your Test Type:
   
   Option A: IV Sweeps
   └─> Configure sweep parameters in MeasurementGUI
       └─> Click "Measure One Device" or "Sequential Measurement"
   
   Option B: Pulse Testing
   └─> Click "Pulse Testing" button
       └─> TSP_Testing_GUI opens
           └─> Select test type and configure parameters
   
   Option C: Advanced Tests
   └─> Click "Advanced Tests" button
       └─> advanced_tests_gui opens
           └─> Select test type (PPF, STDP, etc.)
   
   Option D: Check Connection First
   └─> Click "Check Connection" button
       └─> Check_Connection_GUI opens
           └─> Verify connection, then proceed with measurements

5. Save Results
   └─> Data is automatically saved with timestamps
       └─> Location configured in MeasurementGUI
```

---

## Quick Decision Tree

**Q: I want to test devices on a sample**
→ Start with `Sample_GUI` (main.py)

**Q: I want to run IV sweeps**
→ Use `Measurement_GUI` (launched from Sample_GUI)

**Q: I want to run pulse tests**
→ Use `TSP_Testing_GUI` (launched from MeasurementGUI or standalone)

**Q: I want to verify my connection is good**
→ Use `Check_Connection_GUI` (launched from MeasurementGUI)

**Q: I want to run specialized neuromorphic tests**
→ Use `advanced_tests_gui` (launched from MeasurementGUI)

**Q: I want to control motors**
→ Use `Motor_Controll_GUI` (launched from MeasurementGUI or standalone)

**Q: I want to automate testing**
→ Use `Automated_tester_GUI` (launched from MeasurementGUI)

---

## File Locations

All GUI files are in the root directory:
- `Sample_GUI.py` - Main entry point
- `Measurement_GUI.py` - Main measurement interface
- `TSP_Testing_GUI.py` - Pulse testing
- `Check_Connection_GUI.py` - Connection verification
- `advanced_tests_gui.py` - Advanced tests
- `Motor_Controll_GUI.py` - Motor control
- `Automated_tester_GUI.py` - Automated testing

GUI components (reusable parts) are in `gui/`:
- `gui/layout_builder.py` - Layout construction
- `gui/plot_panels.py` - Plotting components
- `gui/plot_updaters.py` - Plot update logic
- `gui/custom_measurements_builder.py` - Custom measurement UI

---

## Need More Details?

- See individual GUI file docstrings for detailed information
- See `GUI_ARCHITECTURE.md` for architecture overview
- See `GUI_REFACTORING_PLAN.md` for future improvements


