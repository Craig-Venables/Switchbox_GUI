# Keithley 4200A IV Sweep Flow - Where Commands End Up

## Overview
When you select "Keithley 4200A" in the measurement GUI and execute an IV sweep, here's the complete flow:

## Flow Diagram

```
GUI (measurement_gui/main.py)
    ↓
    Selects "Keithley 4200A" from dropdown
    ↓
IVControllerManager (Equipment/managers/iv_controller.py)
    ↓
    Creates: Keithley4200A_KXCI instance
    Wraps it in: _Keithley4200A_KXCI_Wrapper
    ↓
Measurement Service (Measurments/measurement_services_smu.py)
    ↓
    Calls: keithley.do_iv_sweep(config, ...)
    ↓
IVControllerManager.do_iv_sweep()
    ↓
    Routes to: _do_iv_sweep_4200a() [Line 1764-2028]
    ↓
Keithley4200A_KXCI (Equipment/SMU_AND_PMU/keithley4200/kxci_controller.py)
    ↓
    Executes: kxci._execute_ex_command() [Line 1939 in iv_controller.py]
    ↓
    C Module: smu_ivsweep (runs on 4200A hardware)
    ↓
    Retrieves data: kxci._query_gp() [Lines 1975-1979]
```

## Key Files

### 1. **GUI Selection**
**File:** `gui/measurement_gui/layout_builder.py`
- **Line 1190:** Defines available SMU types including 'Keithley 4200A'
- **File:** `gui/measurement_gui/main.py`
- **Line 1995-1996:** Checks if SMU type is 'Keithley 4200A' for cyclical sweep option

### 2. **Controller Initialization**
**File:** `Equipment/managers/iv_controller.py`
- **Lines 526-530:** Registers 'Keithley 4200A' with `Keithley4200A_KXCI` class
- **Lines 577-583:** Creates `Keithley4200A_KXCI` instance when initialized
  - Requires GPIB address (e.g., "GPIB0::17::INSTR")
  - Wraps it in `_Keithley4200A_KXCI_Wrapper` (Line 603)

### 3. **IV Sweep Execution - Main Entry Point**
**File:** `Equipment/managers/iv_controller.py`
- **Line 856-906:** `do_iv_sweep()` method
  - Routes to `_do_iv_sweep_4200a()` if `smu_type == 'Keithley 4200A'` (Line 897-899)

### 4. **IV Sweep Implementation - Where It Actually Happens**
**File:** `Equipment/managers/iv_controller.py`
- **Lines 1764-2028:** `_do_iv_sweep_4200a()` method
  - **Line 1783-1790:** Gets the KXCI wrapper and kxci instance
  - **Line 1891:** Gets `build_ex_command` function from wrapper
  - **Line 1924-1933:** Builds EX command string for C module
  - **Line 1939:** **EXECUTES THE COMMAND** via `kxci._execute_ex_command()`
  - **Lines 1975-1979:** Retrieves voltage and current data via `kxci._query_gp()`

### 5. **KXCI Controller - Low-Level Communication**
**File:** `Equipment/SMU_AND_PMU/keithley4200/kxci_controller.py`
- **Class:** `Keithley4200A_KXCI`
- **Methods:**
  - `_execute_ex_command()`: Sends EX command to 4200A, enters UL mode, executes C module
  - `_query_gp()`: Queries GP parameters to retrieve measurement data
  - `_enter_ul_mode()` / `_exit_ul_mode()`: Manages User Library mode

### 6. **LPT Controller (Alternative - Not Currently Used)**
**File:** `Equipment/SMU_AND_PMU/keithley4200/controller.py`
- **Class:** `Keithley4200AController`
- Uses LPT (Local Procedure Table) protocol via TCP/IP proxy
- **NOT currently used** by the measurement GUI
- Would need to be registered in `IVControllerManager._get_supported()` to use

## Where the IV Sweep Command Actually Executes

The IV sweep command execution happens in **TWO places**:

### 1. Command Building (Python)
**File:** `Equipment/managers/iv_controller.py`
- **Line 1924-1933:** Builds the EX command string
- **Line 1939:** Calls `kxci._execute_ex_command(command, wait_seconds=2.0)`

### 2. Command Execution (4200A Hardware)
**File:** `Equipment/SMU_AND_PMU/keithley4200/kxci_controller.py`
- **Method:** `_execute_ex_command()`
- Sends command to 4200A via GPIB
- Enters UL (User Library) mode
- Executes C module: `smu_ivsweep` (runs on 4200A hardware)
- Returns when measurement completes

### 3. Data Retrieval
**File:** `Equipment/managers/iv_controller.py`
- **Lines 1975-1979:** After execution, queries GP parameters:
  - `GP 6` = Vforce (voltage array)
  - `GP 4` = Imeas (current array)

## Current Implementation Details

### EX Command Format
The EX command built at line 1924 looks like:
```
EX lABVIEW_CONTROLLED_PROGRAMS_KEMP3 smu_ivsweep <vpos> <vneg> <num_cycles> <num_points> <settle_time> <ilimit> <integration_time> <clarius_debug>
```

### C Module Requirements
- The C module `smu_ivsweep` must be installed on the 4200A
- Requires exactly 4 points per cycle (0 → +V → -V → 0)
- Total points = 4 × num_cycles

### Fallback Behavior
If the sweep needs fine-grained control (LED sequences, pausing, many points), it falls back to point-by-point mode (Line 1834-1836), which uses the 2400 method.

## To Fix/Modify the 4200A Measurement System

### If you want to use the LPT controller instead:
1. Modify `Equipment/managers/iv_controller.py`:
   - Import `Keithley4200AController` instead of `Keithley4200A_KXCI`
   - Update the registration at line 526-530
   - Change initialization logic at lines 577-603

### If you want to fix the KXCI implementation:
1. Check `Equipment/SMU_AND_PMU/keithley4200/kxci_controller.py`:
   - Verify `_execute_ex_command()` method
   - Check `_query_gp()` method for data retrieval
   - Ensure UL mode switching works correctly

2. Check `Equipment/managers/iv_controller.py`:
   - Review `_do_iv_sweep_4200a()` method (lines 1764-2028)
   - Verify EX command building logic
   - Check error handling

### Common Issues to Check:
- GPIB connection: Is the address correct in system_configs.json?
- C module: Is `smu_ivsweep` installed on the 4200A?
- UL mode: Does the 4200A support User Library mode?
- Data retrieval: Are GP parameters being queried correctly?

## Summary

**The IV sweep command ends up in:**
1. **`Equipment/managers/iv_controller.py`** - `_do_iv_sweep_4200a()` method (Line 1764)
2. **`Equipment/SMU_AND_PMU/keithley4200/kxci_controller.py`** - `_execute_ex_command()` method
3. **4200A Hardware** - C module `smu_ivsweep` executes the actual measurement

The main entry point for debugging is **`_do_iv_sweep_4200a()`** in `Equipment/managers/iv_controller.py` starting at line 1764.
