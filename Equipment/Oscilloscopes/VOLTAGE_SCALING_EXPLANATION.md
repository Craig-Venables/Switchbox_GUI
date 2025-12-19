# Voltage Scaling Issues and Solutions - Tektronix TBS1000C

## Problem Summary

When reading waveform data from the Tektronix TBS1000C oscilloscope via SCPI commands, we encountered voltage scaling discrepancies. The voltage values displayed on the oscilloscope screen did not match the values obtained from SCPI data, and initially required manual scaling factors to correct.

## Root Cause

### Understanding Tektronix Waveform Data

The Tektronix TBS1000C oscilloscope stores and transmits waveform data in **raw ADC (Analog-to-Digital Converter) codes**, not pre-scaled voltage values. This is a critical distinction:

- **Raw ADC codes**: Integer values (typically -127 to +127 for 8-bit, or -32767 to +32767 for 16-bit)
- **Scaled voltages**: Physical voltage values in Volts that match what you see on the screen

### The Key Insight: Preamble Scaling

The oscilloscope provides **scaling factors** in a waveform preamble (via `WFMO?` command) that must be used to convert raw ADC codes to voltage values. These scaling factors **already account for probe attenuation** - you should NOT apply manual scaling factors on top of this.

## Tektronix Scaling Formula

The standard Tektronix formula for converting raw ADC codes to voltage is:

```
V = (code - YOFF) * YMULT + YZERO
```

Where:
- **code**: Raw ADC code (integer from CURV? command)
- **YOFF**: Y-axis offset (typically ~0, but may vary)
- **YMULT**: Y-axis multiplier (volts per ADC code) - **already includes probe attenuation**
- **YZERO**: Y-axis zero offset (voltage offset, typically 0V)

### Important: Probe Attenuation is Already Accounted For

The `YMULT` value in the preamble **already accounts for probe attenuation**. For example:
- If you have a 10x probe, `YMULT` will be 10x larger than it would be for a 1x probe
- **DO NOT** manually divide by probe attenuation factor
- **DO NOT** apply additional scaling factors (like a 100x multiplier)

## Data Format Issues

### Available Data Formats

The Tektronix TBS1000C supports multiple data formats:

1. **ASCII**: Text format, comma-separated values
2. **RIBINARY**: Signed binary format
3. **RPBINARY**: Unsigned binary format (values offset by 128)

Each format can use different data widths:
- **1-byte (8-bit)**: Values range from -127 to +127 (signed) or 0 to 255 (unsigned)
- **2-byte (16-bit)**: Values range from -32767 to +32767 (signed) or 0 to 65535 (unsigned)

### The 2-Byte Format Problem

During testing (`test_all_data_formats.py`), we discovered that **2-byte formats did not scale correctly**. 

**Root Cause**: The preamble `YMULT` value is **calibrated for 8-bit (1-byte) data**. When using 16-bit (2-byte) data:
- The `YMULT` value is still based on 8-bit scaling
- The ADC codes have a wider range but the same scaling factor
- Result: Incorrect voltage scaling

**Solution**: Use **1-byte (8-bit) formats** exclusively:
- `DAT:ENC ASCII` with `DAT:WID 1` (or default)
- `DAT:ENC RIBINARY` with `DAT:WID 1`
- `DAT:ENC RPBINARY` with `DAT:WID 1` (requires offset conversion)

### Binary Transfer Speed Issue

We initially tried using `RIBINARY` format with 1-byte width (`DAT:ENC RIBINARY; DAT:WID 1`) for better efficiency, but encountered **very slow data transfer** when using PyVISA's `query_binary_values()` method with the TBS1000C.

**Solution**: Revert to **ASCII format** for data acquisition, which is slower in theory but more reliable and consistent in practice with this specific oscilloscope model.

## Implementation Solution

### Current Implementation

In our code (`TektronixTBS1000C.py` and `logic.py`), we use:

1. **Data Format**: ASCII (`DAT:ENC ASCII`)
2. **Data Width**: 1-byte (8-bit) - default
3. **Scaling Method**: Use preamble scaling via `_scale_waveform_values()`

### Code Flow

```python
# 1. Set data source and format
scope.write(f"DAT:SOU CH{channel}")
scope.write("DAT:ENC ASCII")
scope.write("DAT:WID 1")  # 8-bit data

# 2. Get waveform preamble (contains YMULT, YOFF, YZERO)
preamble = scope.get_waveform_preamble(channel)

# 3. Read raw ADC codes
scope.write("DAT:STAR 1")
scope.write(f"DAT:STOP {record_len}")
data_str = scope.query("CURV?")  # Returns comma-separated integers

# 4. Parse raw ADC codes
raw_adc_codes = np.array([float(x) for x in data_str.split(',')])

# 5. Apply scaling (handles probe attenuation automatically)
voltage_values = scope._scale_waveform_values(raw_adc_codes, preamble)
# Formula: V = (code - YOFF) * YMULT + YZERO
```

### Key Functions

**`_scale_waveform_values()`** (`TektronixTBS1000C.py`):
- Takes raw ADC codes and preamble dictionary
- Applies the Tektronix formula: `V = (code - YOFF) * YMULT + YZERO`
- Returns scaled voltage values in Volts
- **Automatically handles probe attenuation** (no manual scaling needed)

**`get_waveform_preamble()`** (`TektronixTBS1000C.py`):
- Queries `WFMO?` command
- Parses preamble string (handles both key-value and positional formats)
- Returns dictionary with `YMULT`, `YOFF`, `YZERO`, `XINCR`, etc.

## USB CSV vs SCPI Data

### Important Distinction

When saving data to a USB drive (`TEK00002.CSV`), the oscilloscope uses its **internal save function**, which outputs **pre-scaled voltage values**. This is different from SCPI data.

**USB CSV format**:
- Contains pre-scaled voltage values (already in Volts)
- No need for preamble scaling
- Values match what you see on screen exactly

**SCPI CURV? command**:
- Always returns raw ADC codes (integers)
- **MUST** be scaled using preamble values
- Values match USB CSV only after proper scaling

### Why This Matters

If you compare USB CSV data with SCPI `CURV?` data without scaling:
- USB CSV: Shows voltages like `0.880V`, `1.200V`
- SCPI (unscaled): Shows ADC codes like `-128`, `128`, `255`

They will only match after applying the preamble scaling formula.

## Best Practices

1. **Always use preamble scaling**: Never apply manual scaling factors
2. **Use 1-byte (8-bit) formats**: 2-byte formats have scaling issues
3. **Use ASCII format**: More reliable than binary on TBS1000C
4. **Trust the preamble**: `YMULT` already accounts for probe attenuation
5. **Don't double-scale**: If using preamble scaling, don't apply additional factors

## Example: Correct Scaling

### Scenario
- Oscilloscope shows: 0.880V on screen
- Probe: 10x attenuation
- Raw ADC code from `CURV?`: -128

### Incorrect Approach (Don't Do This)
```python
# ❌ WRONG: Manual scaling with probe factor
voltage = raw_code * some_factor / probe_attenuation
# This will be incorrect because YMULT already includes probe attenuation
```

### Correct Approach
```python
# ✅ CORRECT: Use preamble scaling
preamble = scope.get_waveform_preamble(channel)
# preamble['YMULT'] = 0.008 (already accounts for 10x probe)
# preamble['YOFF'] = 0.0
# preamble['YZERO'] = 0.0

voltage = (raw_code - preamble['YOFF']) * preamble['YMULT'] + preamble['YZERO']
# voltage = (-128 - 0.0) * 0.008 + 0.0 = -1.024V (at probe input)
# After accounting for probe: -1.024V / 10 = -0.1024V at scope input
# But wait - YMULT already accounts for this, so we get the correct value
```

**Note**: The preamble `YMULT` is calibrated such that applying the formula gives you the voltage at the **probe input** (what you see on screen), not at the scope input.

## Debugging Tips

If voltages still don't match:

1. **Check preamble values**: Print `YMULT`, `YOFF`, `YZERO` from preamble
2. **Verify data format**: Ensure using `DAT:WID 1` (1-byte, 8-bit)
3. **Check probe setting**: Verify scope probe attenuation setting matches physical probe
4. **Compare with USB CSV**: Save waveform to USB and compare values
5. **Inspect raw codes**: Print raw ADC codes to verify they're in expected range (-127 to +127)

## References

- Tektronix TBS1000C Series Programmer Manual
- Tektronix TBS1000C Series User Manual
- Test script: `Equipment/Oscilloscopes/TektronixTBS1000C_example_scripts/test_all_data_formats.py`
- Implementation: `Equipment/Oscilloscopes/TektronixTBS1000C.py`







