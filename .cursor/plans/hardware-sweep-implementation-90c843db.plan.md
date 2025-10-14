<!-- 90c843db-c55d-4ab0-aaf2-8a5ff090b454 57c7f225-3b1a-46f8-bbd1-7a52824241b3 -->
# Hardware Voltage Sweep Implementation Plan

## Current Architecture

```
Measurement_GUI (line 3982-4005)
    └─> MeasurementService.run_iv_sweep()
        └─> IVControllerManager (wraps instrument)
            └─> Keithley4200AController (LPT calls)
```

**Problem**: Current implementation uses slow point-by-point measurements:

- `set_voltage()` + `sleep(0.1)` + `measure_current()` + `sleep(step_delay)`
- ~150ms+ per point = 15+ seconds for 100 points

**Solution**: Use Keithley 4200A's hardware `sweepv()` command for autonomous sweeps

- Expected speedup: 10-150x faster (0.1-1 second for 100 points)

---

## PHASE 1: Architecture Refactoring (Polish First)

### 1.1 Create Sweep Configuration Module

**New File**: `Measurments/sweep_config.py`

Create dataclasses to encapsulate sweep parameters and instrument capabilities:

```python
from dataclasses import dataclass
from typing import Optional, List
from enum import Enum

class SweepMethod(Enum):
    POINT_BY_POINT = "point_by_point"
    HARDWARE_SWEEP = "hardware_sweep"
    ARBITRARY_SWEEP = "arbitrary_sweep"

@dataclass
class SweepConfig:
    """Encapsulates all sweep parameters."""
    start_v: float
    stop_v: float
    step_v: Optional[float] = None
    neg_stop_v: Optional[float] = None
    step_delay: float = 0.05
    sweep_type: str = "FS"
    sweeps: int = 1
    pause_s: float = 0.0
    icc: float = 1e-3
    sweep_method: Optional[SweepMethod] = None
    voltage_list: Optional[List[float]] = None
    # ... other params

@dataclass
class InstrumentCapabilities:
    """Describes instrument capabilities."""
    supports_hardware_sweep: bool = False
    supports_arbitrary_sweep: bool = False
    supports_pulses: bool = False
    min_step_delay_ms: float = 50.0
    max_points_per_sweep: int = 10000
    voltage_range: tuple[float, float] = (-10.0, 10.0)
    current_range: tuple[float, float] = (-1.0, 1.0)
```

### 1.2 Add Capabilities to IVControllerManager

**File**: `Equipment/iv_controller_manager.py`

Add method after line 142:

```python
from Measurments.sweep_config import InstrumentCapabilities

def get_capabilities(self) -> InstrumentCapabilities:
    """Return instrument capabilities."""
    if self.smu_type == 'Keithley 4200A':
        return InstrumentCapabilities(
            supports_hardware_sweep=True,
            supports_arbitrary_sweep=True,
            supports_pulses=True,
            min_step_delay_ms=1.0,
            max_points_per_sweep=10000,
            voltage_range=(-200.0, 200.0),
            current_range=(-1.0, 1.0)
        )
    elif self.smu_type in ['Keithley 2401', 'Keithley 2400']:
        return InstrumentCapabilities(
            supports_hardware_sweep=False,
            min_step_delay_ms=50.0,
            voltage_range=(-20.0, 20.0)
        )
    else:
        return InstrumentCapabilities()
```

### 1.3 Add New Sweep Method to MeasurementService

**File**: `Measurments/measurement_services_smu.py`

Add new method (keep old `run_iv_sweep()` unchanged):

```python
from Measurments.sweep_config import SweepConfig, SweepMethod

def run_iv_sweep_v2(
    self, *, keithley, config: SweepConfig, smu_type: str = "Keithley 2401",
    psu=None, led: bool = False, power: float = 1.0, optical=None,
    sequence=None, should_stop=None, on_point=None,
) -> Tuple[List[float], List[float], List[float]]:
    """New sweep using SweepConfig with auto-method selection."""
    
    capabilities = keithley.get_capabilities()
    
    if config.sweep_method is None:
        config.sweep_method = self._select_sweep_method(config, capabilities)
    
    if config.sweep_method == SweepMethod.HARDWARE_SWEEP:
        return self._run_hardware_sweep(keithley, config, smu_type, 
                                        psu, led, power, optical, 
                                        should_stop, on_point)
    else:
        return self._run_point_by_point_sweep(keithley, config, smu_type,
                                              psu, led, power, optical, 
                                              sequence, should_stop, on_point)

def _select_sweep_method(self, config: SweepConfig, 
                        capabilities: InstrumentCapabilities) -> SweepMethod:
    """Auto-select best sweep method."""
    if capabilities.supports_hardware_sweep:
        num_points = self._estimate_num_points(config)
        if num_points > 20 and config.step_delay < 0.05:
            return SweepMethod.HARDWARE_SWEEP
    return SweepMethod.POINT_BY_POINT

def _run_point_by_point_sweep(self, *, keithley, config: SweepConfig, **kwargs):
    """Wrapper calling existing run_iv_sweep."""
    return self.run_iv_sweep(
        keithley=keithley, icc=config.icc, sweeps=config.sweeps,
        step_delay=config.step_delay, start_v=config.start_v,
        stop_v=config.stop_v, neg_stop_v=config.neg_stop_v,
        step_v=config.step_v, sweep_type=config.sweep_type, **kwargs
    )

def _run_hardware_sweep(self, *, keithley, config: SweepConfig, **kwargs):
    """Placeholder for Phase 2."""
    print("Hardware sweep not yet implemented, using point-by-point")
    return self._run_point_by_point_sweep(keithley=keithley, config=config, **kwargs)
```

---

## PHASE 2: Hardware Sweep Implementation

### 2.1 Add Hardware Sweep to Keithley4200AController

**File**: `Equipment/SMU_AND_PMU/Keithley4200A.py`

Add after existing `voltage_sweep()` at line 206:

```python
def voltage_sweep_hardware(
    self, start_v: float, stop_v: float, num_points: int,
    delay_ms: float = 1.0, i_limit: float = 1e-3,
    bidirectional: bool = True
) -> tuple[list[float], list[float]]:
    """Fast hardware sweep using LPT sweepv command."""
    if self._instr_id is None:
        return ([], [])
    
    try:
        self.lpt.limiti(self._instr_id, float(i_limit))
        self.lpt.clrscn()
        
        v_reading = self.lpt.smeasv(self._instr_id, num_points)
        i_reading = self.lpt.smeasi(self._instr_id, num_points)
        
        self.lpt.sweepv(self._instr_id, float(start_v), float(stop_v),
                       num_points - 1, float(delay_ms / 1000.0))
        
        v_forward = [float(v_reading[i]) for i in range(num_points)]
        i_forward = [float(i_reading[i]) for i in range(num_points)]
        
        if bidirectional:
            v_reading_rev = self.lpt.smeasv(self._instr_id, num_points)
            i_reading_rev = self.lpt.smeasi(self._instr_id, num_points)
            
            self.lpt.sweepv(self._instr_id, float(stop_v), float(start_v),
                          num_points - 1, float(delay_ms / 1000.0))
            
            v_reverse = [float(v_reading_rev[i]) for i in range(num_points)]
            i_reverse = [float(i_reading_rev[i]) for i in range(num_points)]
            
            voltages = v_forward + v_reverse
            currents = i_forward + i_reverse
        else:
            voltages = v_forward
            currents = i_forward
        
        self.lpt.forcev(self._instr_id, 0.0)
        return (voltages, currents)
        
    except Exception as e:
        print(f"Hardware sweep failed: {e}")
        try:
            self.lpt.forcev(self._instr_id, 0.0)
        except:
            pass
        return ([], [])
```

### 2.2 Implement _run_hardware_sweep in MeasurementService

**File**: `Measurments/measurement_services_smu.py`

Replace placeholder with dump method (no live plotting):

```python
def _run_hardware_sweep(
    self, *, keithley, config: SweepConfig, smu_type: str,
    psu=None, led=False, power=1.0, optical=None,
    should_stop=None, on_point=None
) -> Tuple[List[float], List[float], List[float]]:
    """Execute hardware sweep without live plotting.
    
    Completes in ~1s vs 30s point-by-point.
    """
    import time
    
    if not hasattr(keithley.instrument, 'voltage_sweep_hardware'):
        return self._run_point_by_point_sweep(...)
    
    # Setup LED/optical
    try:
        if optical and led:
            optical.set_power(float(power))
            optical.set_enabled(True)
        elif psu and led:
            psu.led_on_380()
    except:
        pass
    
    # Build voltage list
    v_list = self._build_voltage_list(...)
    bidirectional = config.sweep_type in ["FS", "Triangle"]
    num_forward = len(v_list) // (2 * config.sweeps) if bidirectional else len(v_list) // config.sweeps
    
    keithley.enable_output(True)
    start_time = time.perf_counter()
    
    voltages_all = []
    currents_all = []
    
    for sweep_idx in range(config.sweeps):
        if should_stop and should_stop():
            break
        
        v_meas, i_meas = keithley.instrument.voltage_sweep_hardware(
            start_v=config.start_v, stop_v=config.stop_v,
            num_points=num_forward, delay_ms=config.step_delay * 1000,
            i_limit=config.icc, bidirectional=bidirectional
        )
        
        voltages_all.extend(v_meas)
        currents_all.extend(i_meas)
    
    # NO on_point callbacks - live plotting disabled
    
    # Cleanup
    try:
        if optical:
            optical.set_enabled(False)
        elif psu:
            psu.led_off_380()
        keithley.set_voltage(0, config.icc)
        keithley.enable_output(False)
    except:
        pass
    
    duration = time.perf_counter() - start_time
    timestamps = [duration for _ in range(len(voltages_all))]
    
    return (voltages_all, currents_all, timestamps)
```

---

## PHASE 3: GUI Integration with Status Indicators

### 3.1 Add Status Indicators

**File**: `Measurement_GUI.py`

Update around line 3970-4070:

```python
# Detect hardware sweep
using_hardware_sweep = (
    self.SMU_type == 'Keithley 4200A' and 
    num_points > 20 and step_delay < 0.05
)

if using_hardware_sweep:
    # Status message
    self.status_box.config(text="Hardware sweep in progress...")
    
    # Show indicator on plot
    self.ax_rt_iv.clear()
    self.ax_rt_iv.text(0.5, 0.5, 'Hardware Sweep Running...\nPlease Wait', 
                       ha='center', va='center', fontsize=14, color='blue')
    self.canvas_rt_iv.draw()
    self.master.update_idletasks()

# Execute measurement
v_arr, c_arr, timestamps = self.measurement_service.run_iv_sweep_v2(...)

# Update status
if using_hardware_sweep:
    self.status_box.config(
        text=f"Sweep complete ({len(v_arr)} points in {timestamps[-1]:.2f}s)"
    )
else:
    self.status_box.config(text="Measurement complete")

# Update plots
self.graphs_show(v_arr, c_arr, "1", stop_v)
```

---

## Testing Strategy

### Phase 1:

- Existing code works unchanged
- Test `run_iv_sweep_v2()` with POINT_BY_POINT
- Verify auto-selection logic

### Phase 2:

- Simple hardware sweep: 0-1V, 100 points
- Bidirectional sweep
- Multiple sweeps
- Timing comparison (expect 10-100x speedup)

### Phase 3:

- Status indicators appear correctly
- GUI responsive during sweep
- Plots update properly after sweep

---

## Implementation Checklist

### Phase 1 - Refactoring:

- [ ] Create `Measurments/sweep_config.py`
- [ ] Add `get_capabilities()` to IVControllerManager
- [ ] Add `run_iv_sweep_v2()` to MeasurementService
- [ ] Test existing code still works

### Phase 2 - Hardware Sweep:

- [ ] Add `voltage_sweep_hardware()` to Keithley4200AController
- [ ] Implement `_run_hardware_sweep()` in MeasurementService
- [ ] Test hardware sweep
- [ ] Measure performance improvement

### Phase 3 - GUI:

- [ ] Add status indicators
- [ ] Test user experience
- [ ] Verify plotting works correctly

### To-dos

- [ ] Test Phase 2: test hardware sweep with various configurations and measure speedup
- [ ] Test Phase 3: full end-to-end testing with GUI, plotting, and all features