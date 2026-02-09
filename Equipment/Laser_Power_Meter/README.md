# Laser Power Meter (Thorlabs PM100D)

Controller for **Thorlabs PM100D** laser power meter. Default unit: **SN P0031757**.

## Requirements

- **pyvisa** (and NI-VISA or `pyvisa-py` backend)
- USB connection to the PM100D

## Usage

```python
from Equipment.Laser_Power_Meter import PM100D, find_pm100d_resource

# By default uses SN P0031757
with PM100D() as pm:
    print(pm.idn())
    pm.set_wavelength_nm(532)   # optional: set wavelength for correction
    power_w = pm.measure_power_w()
    power_mw = pm.measure_power_mw()
    print(f"Power: {power_mw:.3f} mW")

# Or specify resource or serial
resource = find_pm100d_resource("P0031757")
pm = PM100D(resource=resource)
pm.connect()
print(pm.measure_power_mw())
pm.close()
```

## API summary

| Method / function | Description |
|-------------------|-------------|
| `PM100D(resource=..., serial=..., timeout_ms=...)` | Constructor; default serial `P0031757`. |
| `connect(resource=...)` | Open VISA connection. |
| `close()` | Close connection. |
| `idn()` | Instrument identification. |
| `measure_power_w()` | Power in watts. |
| `measure_power_mw()` | Power in milliwatts. |
| `get_wavelength_nm()` | Wavelength setting (nm). |
| `set_wavelength_nm(nm)` | Set wavelength for correction. |
| `configure_power()` | Configure for power measurement. |
| `zero()` | Zero calibration (no light). |
| `find_pm100d_resource(serial=...)` | Find PM100D VISA resource on USB. |
