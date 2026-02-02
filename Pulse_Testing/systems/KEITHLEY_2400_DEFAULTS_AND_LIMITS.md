# Keithley 2400/2401 Pulse Testing - Defaults and Limits

## Hardware Limits

| Parameter | Minimum | Maximum | Notes |
|-----------|---------|---------|-------|
| **Pulse Width** | 0.01s (10ms) | 10.0s | Minimum limited by GPIB communication speed |
| **Voltage** | -200V | +200V | Hardware specification |
| **Current Limit** | 1e-9A (1nA) | 1.0A | Hardware specification |

## Default Parameters

| Parameter | Default Value | Description | Adjustable |
|-----------|---------------|-------------|------------|
| **Read Settle Time** | 0.01s (10ms) | Time to wait after setting voltage before taking measurement | ❌ No - fixed internal value |
| **Pulse Width** | 0.01s (10ms) | Default pulse width | ✅ Yes - via `pulse_width` parameter |
| **Read Voltage** | 0.2V | Default read voltage | ✅ Yes - via `read_voltage` parameter |
| **Current Limit** | 100mA (0.1A) | Default compliance current | ✅ Yes - via `clim` parameter |
| **Delay Between Cycles** | 0.01s (10ms) | Default delay between pulse-read cycles | ✅ Yes - via `delay_between` parameter |

## Read Settle Time

**Current Setting:** 0.01 seconds (10ms)

**What it does:** After setting the read voltage, the system waits this amount of time before taking the measurement. This allows the device to settle to the new voltage level.

**Why it matters:**
- Too short: Measurements may be unstable or inaccurate due to incomplete settling
- Too long: Test duration increases unnecessarily
- For GPIB connections, 10ms is typically sufficient, but may need adjustment based on:
  - Device capacitance (higher capacitance = longer settle time needed)
  - Measurement range (some ranges may require longer settle)
  - Required measurement accuracy

**How to adjust:**
The read settle time is a fixed internal value (0.01s/10ms) in the `_read()` method. To change it, modify the `time.sleep()` call in the `_read()` method in `keithley2400_scpi_scripts.py`:

```python
def _read(self, voltage: float, icc: float = 0.1) -> tuple[float, float, float]:
    ...
    time.sleep(0.01)  # Change this value (e.g., 0.02 for 20ms)
    ...
```

## Recommended Settings by Use Case

| Use Case | Read Settle Time | Notes |
|----------|------------------|-------|
| **Fast devices (low capacitance)** | 0.005s - 0.01s | Default 10ms usually sufficient |
| **Standard devices** | 0.01s - 0.02s | Default 10ms is good starting point |
| **High capacitance devices** | 0.02s - 0.05s | May need longer for stable measurements |
| **High accuracy requirements** | 0.05s - 0.1s | Longer settle time improves accuracy |

## GPIB Communication Limitations

The Keithley 2400/2401 uses GPIB communication, which has inherent speed limitations:

- **Minimum pulse width:** ~10ms (0.01s) - shorter pulses may not be reliably executed
- **Measurement overhead:** Each measurement requires GPIB communication, adding ~1-5ms overhead
- **Total cycle time:** Pulse + Read + Delay typically takes 20-50ms minimum

## Example: Calculating Total Test Time

For `pulse_read_repeat` with:
- `num_cycles = 10`
- `pulse_width = 0.01s`
- `read_settle_time = 0.01s` (default)
- `delay_between = 0.01s`

**Per cycle time:**
- Pulse: 0.01s
- Read settle: 0.01s
- Measurement: ~0.001-0.005s (GPIB overhead)
- Delay: 0.01s
- **Total per cycle:** ~0.03-0.035s

**Total test time:**
- Initial read: ~0.02s
- 10 cycles: 10 × 0.035s = 0.35s
- **Total:** ~0.37s

## Notes

- The read settle time is a fixed internal value (0.01s/10ms) to maintain consistency with other systems (2450, 4200A)
- For very fast measurements, consider using a Keithley 2450 (TSP-based) or 4200A (PMU-based) which have faster communication and can handle shorter pulses
- If measurements are unstable, you can modify the `time.sleep()` value in the `_read()` method, but this will deviate from the standard interface
