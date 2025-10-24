# Keithley 2450 Controller - Changelog

## Initial Release

### Created Files

1. **`Keithley2450.py`** - Main controller implementation
   - Full PyVISA-based communication (USB/GPIB/LAN)
   - Basic SCPI commands for voltage/current sourcing and measurement
   - Advanced TSP pulse control for memristor characterization
   - Comprehensive test script included

2. **`README_Keithley2450.md`** - User documentation
   - Quick start guide
   - Example code for all features
   - Troubleshooting tips
   - Safety notes

3. **`CHANGELOG_Keithley2450.md`** - This file

### Modified Files

1. **`Equipment/iv_controller_manager.py`**
   - Added `Keithley2450Controller` import
   - Added 'Keithley 2450' to SUPPORTED instruments
   - Added instrument capabilities for 2450 (200V range, TSP support, fast pulses)

### Features Implemented

#### Basic Operations
- ✅ Connection via USB, GPIB, or LAN (auto-detect format)
- ✅ Voltage sourcing with compliance (±200V)
- ✅ Current sourcing with compliance (±1A)
- ✅ Voltage and current measurement
- ✅ Output enable/disable control
- ✅ Beeper control
- ✅ Voltage ramping for safe transitions
- ✅ Safe shutdown procedure

#### Advanced Features
- ✅ Pulse preparation (configure for fast measurements)
- ✅ Pulse finish (return to safe state)
- ✅ Range locking for consistent measurements
- ✅ Autozero control for speed optimization
- ✅ 4-wire sensing option

#### TSP Pulse Patterns
- ✅ **Single Read Pulse** - Fast single-point measurement
- ✅ **Potentiation Pulse Train** - SET operation with read-after-write
- ✅ **Depression Pulse Train** - RESET operation with read-after-write  
- ✅ **Custom Pulse Sequence** - Arbitrary voltage/timing patterns
- ✅ **Custom TSP Script Execution** - Full TSP programming flexibility

#### Testing
- ✅ Comprehensive 5-stage test script:
  1. Connection test with IDN query
  2. Basic SCPI operations (voltage, current, beep)
  3. Pulse preparation/finish
  4. TSP pulse pattern validation
  5. Safety checks

### Key Improvements Over Keithley 2400

| Feature | 2400 | 2450 |
|---------|------|------|
| Voltage Range | ±20V | ±200V |
| Communication | GPIB mainly | USB/GPIB/LAN |
| Touchscreen | No | Yes |
| TSP Speed | Standard | Optimized |
| Pulse Timing | ~1ms min | ~50µs min |
| Memory | Limited | Enhanced |
| Measurement Speed | Standard | Fast (0.01 NPLC) |

### Design Decisions

1. **PyVISA over PyMeasure**: 
   - Direct VISA control for maximum flexibility
   - PyMeasure's 2450 support may be incomplete
   - Better control over TSP scripting

2. **TSP Script Format**:
   - Using loadscript/endscript for multi-line scripts
   - Inline data parsing via print() statements
   - Consistent DATA:v,i format for measurements

3. **Method Compatibility**:
   - Maintained same method signatures as 2400 controller
   - Ensures drop-in replacement in existing code
   - Additional methods for 2450-specific features

4. **Safety First**:
   - All pulse methods return to 0V by default
   - prepare_for_pulses() requires explicit voltage range
   - shutdown() implements safe ramp-down
   - Comprehensive error handling

### Usage Notes

- Update `DEVICE_ADDRESS` in test script before running
- Start with low voltages when testing
- Use appropriate compliance limits to protect devices
- TSP scripts run on-instrument (fast, no Python delays)
- Pre-defined patterns handle memristor SET/RESET operations

### Known Limitations

- Minimum recommended pulse width: 50µs (hardware dependent)
- TSP script parsing expects specific print format
- Some advanced 2450 features not yet implemented (e.g., buffer operations)
- Firmware version compatibility not extensively tested

### Future Enhancements (Potential)

- [ ] Buffer reading for high-speed multi-point sweeps
- [ ] Advanced trigger configurations
- [ ] Digital I/O control
- [ ] Full arbitrary waveform generation
- [ ] Graphical display control
- [ ] Configuration save/recall

### Testing Status

✅ Syntax validated (no linter errors)  
⏳ Hardware testing required (connect to actual 2450)  
⏳ TSP script execution validation needed  
⏳ Long-term pulse stability testing pending  

### References

- Keithley 2450 Reference Manual: `Equipment/manuals/Keithley 2450 manual.pdf`
- Keithley 2450 Datasheet: `Equipment/manuals/Keithley 2450 datasheet.pdf`
- TSP Toolkit: https://www.tek.com/en/products/software/tsp-toolkit-scripting-tool

---

**Date**: 2025-10-24  
**Status**: Ready for hardware testing  
**Next Steps**: Run test script with actual Keithley 2450 hardware

