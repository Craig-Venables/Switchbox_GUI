# Oscilloscope Equipment

This directory contains oscilloscope control modules for the Switchbox_GUI project.

## Files

- **TektronixTBS1000C.py**: Driver for Tektronix TBS1000C series oscilloscopes
- **GWInstekGDS2062.py**: Driver for GW Instek GDS-2062 series oscilloscopes
- **README.md**: This file

## Usage

### Direct Usage

**Tektronix TBS1000C:**
```python
from Equipment.Oscilloscopes.TektronixTBS1000C import TektronixTBS1000C

# Connect to oscilloscope
scope = TektronixTBS1000C(resource='USB0::0x0699::0x0409::C000000::INSTR')
if scope.connect():
    print(f"Connected: {scope.idn()}")
    
    # Autoscale
    scope.autoscale()
    
    # Acquire waveform
    time_array, voltage_array = scope.acquire_waveform(1)
    
    # Clean up
    scope.disconnect()
```

**GW Instek GDS-2062:**
```python
from Equipment.Oscilloscopes.GWInstekGDS2062 import GWInstekGDS2062

# Connect to oscilloscope
scope = GWInstekGDS2062(resource='USB0::......::INSTR')
if scope.connect():
    print(f"Connected: {scope.idn()}")
    
    # Autoscale
    scope.autoscale()
    
    # Acquire waveform
    time_array, voltage_array = scope.acquire_waveform(1)
    
    # Clean up
    scope.disconnect()
```

### Using the Manager

```python
from Equipment.oscilloscope_manager import OscilloscopeManager

# Auto-detect oscilloscope
scope_mgr = OscilloscopeManager(auto_detect=True)

if scope_mgr.is_connected():
    # Run autoscale
    scope_mgr.autoscale()
    
    # Acquire waveform
    time_array, voltage_array = scope_mgr.acquire_waveform(channel=1)
    
    # Compute statistics from waveform (recommended for TBS1000C)
    stats = scope_mgr.compute_waveform_statistics(voltage_array)
    print(f"Peak-to-peak: {stats['vpp']:.3f} V")
    
    freq = scope_mgr.compute_frequency(time_array, voltage_array)
    print(f"Frequency: {freq:.2f} Hz")
    
    # Optionally try SCPI measurements (may not work on TBS1000C)
    try:
        scope_mgr.configure_measurement('AMPL', channel=1, measurement_number=1)
        amplitude = scope_mgr.read_measurement(1)
        print(f"SCPI Amplitude: {amplitude:.3f} V")
    except ValueError:
        print("Using computed statistics instead")
    
    # Clean up
    scope_mgr.close()
```

## Requirements

- pyvisa
- numpy
- VISA library (NI-VISA or TekVISA)

## Supported Features

- Connection management via USB
- Channel configuration (scale, offset, coupling)
- Timebase control
- Trigger configuration
- Waveform acquisition (ASCII and binary formats) ✓
- Automatic measurements (SCPI support varies by model)
- Screen capture
- Context manager support
- Waveform data analysis (compute statistics, frequency from data)

**Supported Models:**
- **Tektronix TBS1000C**: 2 channels, limited SCPI measurement support
- **GW Instek GDS-2062**: 4 channels, SCPI support

**Note**: The TBS1000C series has limited SCPI support compared to higher-end Tektronix models. 
Automatic measurements via SCPI commands may not work reliably on all TBS1000C models. 
Waveform acquisition and basic controls work well. Use waveform data analysis as fallback.

## Testing

Run the test suite:

```bash
python tests/test_oscilloscope.py
```

## Documentation

For more details, see the main project README and the inline documentation in each file.

