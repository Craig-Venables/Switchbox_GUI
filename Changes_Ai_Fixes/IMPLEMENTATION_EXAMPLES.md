# Implementation Examples

Complete, working examples showing how to use the new modular utilities.

---

## Example 1: Generic IV Sweep (Voltage OR Current Source)

This example shows a truly generic sweep that works for both voltage and current source modes.

```python
from Measurments.source_modes import SourceMode, apply_source, measure_result, get_axis_labels
from Measurments.sweep_patterns import build_sweep_values, SweepType
from Measurments.optical_controller import OpticalController
from Measurments.data_utils import safe_measure_current, safe_measure_voltage
from Measurments.data_formats import DataFormatter, save_measurement_data
import time
from pathlib import Path

def run_generic_sweep(
    keithley,
    source_mode=SourceMode.VOLTAGE,  # or SourceMode.CURRENT
    start=0.0,
    stop=1.0,
    step=0.1,
    compliance=1e-3,
    sweep_type=SweepType.FULL,
    optical=None,
    psu=None,
    led_power=1.0,
    save_path=None
):
    """
    Universal sweep function that works for BOTH voltage and current modes!
    
    Examples:
        # Voltage sweep (traditional IV)
        v_arr, i_arr = run_generic_sweep(
            keithley, 
            source_mode=SourceMode.VOLTAGE,
            start=0, stop=1, compliance=1e-3
        )
        
        # Current sweep (reverse - source I, measure V)
        i_arr, v_arr = run_generic_sweep(
            keithley,
            source_mode=SourceMode.CURRENT,
            start=0, stop=1e-6, compliance=10.0
        )
    """
    
    # Build source values
    source_values = build_sweep_values(start, stop, step, sweep_type)
    
    # Setup optical control
    optical_ctrl = OpticalController(optical=optical, psu=psu)
    optical_ctrl.enable(led_power)
    
    # Enable instrument
    keithley.enable_output(True)
    
    # Measure
    source_arr = []
    measured_arr = []
    timestamps = []
    start_time = time.perf_counter()
    
    try:
        for source_val in source_values:
            # Apply source (voltage OR current)
            apply_source(keithley, source_mode, source_val, compliance)
            time.sleep(0.05)  # Settling time
            
            # Measure result (current OR voltage)
            measured_val = measure_result(keithley, source_mode)
            
            source_arr.append(source_val)
            measured_arr.append(measured_val)
            timestamps.append(time.perf_counter() - start_time)
    
    finally:
        # Cleanup
        apply_source(keithley, source_mode, 0, compliance)
        keithley.enable_output(False)
        optical_ctrl.disable()
    
    # Save data if requested
    if save_path:
        import numpy as np
        formatter = DataFormatter()
        
        # Format based on mode
        if source_mode == SourceMode.VOLTAGE:
            data, header, fmt = formatter.format_iv_data(
                np.array(timestamps),
                np.array(source_arr),
                np.array(measured_arr)
            )
        else:  # Current mode
            data, header, fmt = formatter.format_iv_data(
                np.array(timestamps),
                np.array(measured_arr),  # Voltage
                np.array(source_arr)     # Current
            )
        
        save_measurement_data(Path(save_path), data, header, fmt)
    
    return source_arr, measured_arr
```

---

## Example 2: Multi-Device Sweep with Multiplexer

This example shows automated measurement across multiple devices.

```python
from Equipment.multiplexer_manager import MultiplexerManager, MultiplexerContext
from Measurments.source_modes import SourceMode
from Measurments.sweep_patterns import build_sweep_values, SweepType
from Measurments.data_utils import safe_measure_current
from Measurments.data_formats import FileNamer, DataFormatter, save_measurement_data
import numpy as np

def measure_all_devices(
    keithley,
    device_list,
    multiplexer_type,
    pin_mapping=None,
    mpx_controller=None,
    sample_name="MySample"
):
    """
    Measure IV curves for all devices using multiplexer.
    
    Example:
        results = measure_all_devices(
            keithley,
            device_list=["A1", "A2", "A3"],
            multiplexer_type="Pyswitchbox",
            pin_mapping=pin_mapping,
            sample_name="Device_Batch_1"
        )
    """
    
    # Create multiplexer manager
    mpx = MultiplexerManager.create(
        multiplexer_type,
        pin_mapping=pin_mapping,
        controller=mpx_controller
    )
    
    # Setup file naming
    namer = FileNamer()
    formatter = DataFormatter()
    
    # Build sweep
    voltages = build_sweep_values(0, 1, 0.1, SweepType.FULL)
    
    results = {}
    
    for idx, device in enumerate(device_list):
        print(f"Measuring device {device}...")
        
        # Route to device (automatically disconnects after context)
        with MultiplexerContext(mpx, device, idx):
            # Measure
            v_arr, i_arr = [], []
            for v in voltages:
                keithley.set_voltage(v, 1e-3)
                i = safe_measure_current(keithley)
                v_arr.append(v)
                i_arr.append(i)
            
            # Save data
            folder = namer.get_device_folder(sample_name, device, "IV_sweeps")
            filename = namer.create_iv_filename(device, 1.0, "sweep")
            filepath = folder / filename
            
            data, header, fmt = formatter.format_iv_data(
                np.arange(len(v_arr)),
                np.array(v_arr),
                np.array(i_arr)
            )
            
            save_measurement_data(filepath, data, header, fmt)
            
            results[device] = {"voltages": v_arr, "currents": i_arr}
    
    return results
```

---

## Example 3: Optical Pulse Sequence

This example shows different light patterns during measurements.

```python
from Measurments.optical_controller import OpticalController
from Measurments.sweep_patterns import build_sweep_values, SweepType
from Measurments.data_utils import safe_measure_current

def measure_with_light_sequence(
    keithley,
    optical=None,
    psu=None,
    num_sweeps=4,
    light_sequence=['1', '0', '1', '0']  # ON, OFF, ON, OFF
):
    """
    Run multiple sweeps with different light conditions.
    
    Example:
        # Measure 4 sweeps: light ON, OFF, ON, OFF
        results = measure_with_light_sequence(
            keithley,
            optical=laser,
            num_sweeps=4,
            light_sequence=['1', '0', '1', '0']
        )
    """
    
    optical_ctrl = OpticalController(optical=optical, psu=psu)
    voltages = build_sweep_values(0, 1, 0.1, SweepType.FULL)
    
    all_results = []
    
    for sweep_idx in range(num_sweeps):
        # Set light state for this sweep
        optical_ctrl.apply_sequence_state(light_sequence, sweep_idx, power=1.5)
        
        # Measure
        v_arr, i_arr = [], []
        for v in voltages:
            keithley.set_voltage(v, 1e-3)
            i = safe_measure_current(keithley)
            v_arr.append(v)
            i_arr.append(i)
        
        light_state = "ON" if light_sequence[sweep_idx] == '1' else "OFF"
        all_results.append({
            "sweep": sweep_idx,
            "light": light_state,
            "voltages": v_arr,
            "currents": i_arr
        })
    
    # Cleanup
    optical_ctrl.disable()
    
    return all_results
```

---

## Example 4: Current Source Mode Measurement

New capability enabled by source mode abstraction!

```python
from Measurments.source_modes import (
    SourceMode, SourceModeConfig, 
    apply_source, measure_result,
    get_axis_labels, format_source_value
)
from Measurments.sweep_patterns import build_sweep_values, SweepType
import matplotlib.pyplot as plt

def run_current_source_sweep(keithley, start_i=0, stop_i=1e-6, step_i=1e-7):
    """
    Source current and measure voltage - new capability!
    
    This is useful for:
    - Characterizing low-impedance devices
    - Avoiding compliance issues
    - Direct resistance measurements
    
    Example:
        i_arr, v_arr = run_current_source_sweep(
            keithley,
            start_i=0,
            stop_i=1e-6,
            step_i=1e-7
        )
    """
    
    # Build current sweep
    current_values = build_sweep_values(
        start_i, stop_i, step_i, 
        SweepType.FULL
    )
    
    # Create source mode config for current source
    config = SourceModeConfig(
        mode=SourceMode.CURRENT,
        value=0,  # Will be updated in loop
        compliance=10.0  # 10V compliance
    )
    
    keithley.enable_output(True)
    
    i_arr = []
    v_arr = []
    
    try:
        for i_val in current_values:
            # Update and apply current
            config.value = i_val
            config.apply(keithley)
            
            # Measure voltage
            v_val = config.measure(keithley)
            
            i_arr.append(i_val)
            v_arr.append(v_val)
            
            print(f"Sourced: {format_source_value(config.mode, i_val)}, "
                  f"Measured: {v_val:.3f} V")
    
    finally:
        config.value = 0
        config.apply(keithley)
        keithley.enable_output(False)
    
    # Plot with correct labels
    x_label, y_label = get_axis_labels(SourceMode.CURRENT)
    plt.figure()
    plt.plot(i_arr, v_arr, 'b.-')
    plt.xlabel(x_label)
    plt.ylabel(y_label)
    plt.title("Current Source Sweep")
    plt.grid(True)
    plt.show()
    
    return i_arr, v_arr
```

---

## Example 5: Complete Measurement with All Features

This example combines everything!

```python
from Measurments.source_modes import SourceMode, apply_source, measure_result
from Measurments.sweep_patterns import build_sweep_values, SweepType
from Measurments.optical_controller import OpticalController
from Measurments.data_utils import safe_measure_current, safe_measure_voltage
from Measurments.data_formats import DataFormatter, FileNamer, save_measurement_data
from Equipment.multiplexer_manager import MultiplexerManager
import numpy as np
import time

def complete_device_characterization(
    keithley,
    device_list,
    source_mode=SourceMode.VOLTAGE,
    multiplexer_type="Pyswitchbox",
    pin_mapping=None,
    optical=None,
    psu=None,
    sample_name="Complete_Test"
):
    """
    Complete device characterization using ALL modular utilities.
    
    Features:
    - Source voltage OR current mode
    - Multiplexer routing
    - Optical control
    - Clean data normalization
    - Consistent file formatting
    
    Example:
        results = complete_device_characterization(
            keithley,
            device_list=["A1", "A2"],
            source_mode=SourceMode.VOLTAGE,
            multiplexer_type="Pyswitchbox",
            pin_mapping=pin_mapping,
            optical=laser,
            sample_name="Batch_2025_10_14"
        )
    """
    
    # Initialize managers
    mpx = MultiplexerManager.create(multiplexer_type, pin_mapping=pin_mapping)
    optical_ctrl = OpticalController(optical=optical, psu=psu)
    formatter = DataFormatter()
    namer = FileNamer()
    
    # Build sweep
    if source_mode == SourceMode.VOLTAGE:
        sweep_values = build_sweep_values(0, 1, 0.05, SweepType.FULL)
        compliance = 1e-3
    else:  # Current mode
        sweep_values = build_sweep_values(0, 1e-6, 1e-7, SweepType.FULL)
        compliance = 10.0
    
    results = {}
    
    # Enable light
    optical_ctrl.enable(power=1.5)
    
    for idx, device in enumerate(device_list):
        print(f"\nMeasuring {device} in {source_mode.value} mode...")
        
        # Route to device
        mpx.route_to_device(device, idx)
        time.sleep(0.5)  # Settling
        
        # Enable output
        keithley.enable_output(True)
        
        # Measure
        source_arr = []
        measured_arr = []
        timestamps = []
        start_time = time.perf_counter()
        
        for source_val in sweep_values:
            # Apply source
            apply_source(keithley, source_mode, source_val, compliance)
            time.sleep(0.05)
            
            # Measure
            measured_val = measure_result(keithley, source_mode)
            
            source_arr.append(source_val)
            measured_arr.append(measured_val)
            timestamps.append(time.perf_counter() - start_time)
        
        # Return to zero
        apply_source(keithley, source_mode, 0, compliance)
        keithley.enable_output(False)
        
        # Save data
        folder = namer.get_device_folder(sample_name, device, source_mode.value)
        filename = namer.create_iv_filename(device, 1.0, source_mode.value)
        
        if source_mode == SourceMode.VOLTAGE:
            data, header, fmt = formatter.format_iv_data(
                np.array(timestamps),
                np.array(source_arr),
                np.array(measured_arr)
            )
        else:  # Current mode
            data, header, fmt = formatter.format_iv_data(
                np.array(timestamps),
                np.array(measured_arr),  # Voltage
                np.array(source_arr)     # Current
            )
        
        save_measurement_data(folder / filename, data, header, fmt)
        
        results[device] = {
            "source": source_arr,
            "measured": measured_arr,
            "timestamps": timestamps
        }
        
        print(f"  Saved: {folder / filename}")
    
    # Cleanup
    optical_ctrl.disable()
    mpx.disconnect_all()
    
    return results
```

---

## Running the Examples

```python
# Example 1: Simple voltage sweep
from example1 import run_generic_sweep
v, i = run_generic_sweep(
    keithley,
    source_mode=SourceMode.VOLTAGE,
    start=0, stop=1, step=0.1
)

# Example 2: Current source sweep (NEW!)
from example4 import run_current_source_sweep
i, v = run_current_source_sweep(
    keithley,
    start_i=0,
    stop_i=1e-6,
    step_i=1e-7
)

# Example 5: Complete characterization
from example5 import complete_device_characterization
results = complete_device_characterization(
    keithley,
    device_list=["A1", "A2", "A3"],
    source_mode=SourceMode.VOLTAGE,  # or CURRENT
    multiplexer_type="Pyswitchbox",
    pin_mapping=pin_mapping,
    optical=laser
)
```

---

## Key Takeaways

1. **Modular utilities eliminate duplication** - No more scattered if-statements
2. **Easy to extend** - Add new modes, patterns, or devices in one place
3. **Consistent behavior** - Same formatting and handling everywhere
4. **Backward compatible** - Old code still works
5. **Future-proof** - New features (like current source mode) are trivial to add

---

## Next Steps

1. Test these examples with your hardware
2. Refactor one measurement function at a time
3. Verify results match old implementation
4. Gradually migrate all functions
5. Delete old duplicated code

