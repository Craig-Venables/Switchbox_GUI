# Arduino Device Current Testing System

Complete Arduino Uno solution for applying 0.2V to multiple devices, measuring current, and monitoring temperature/humidity with SHT45 sensor.

## Quick Answers

**Can I apply 0.2V using Arduino pins directly?**  
No. Arduino outputs 5V or 0V. Use a voltage divider (simplest), PWM+filter, or DAC.

**Simplest solution?**  
**Voltage Divider** - just 2 resistors! See "Voltage Options" below.

## What's Included

### Main Applications
- `device_current_test.ino` - Full system with Serial output (305 lines)
- `device_current_test_with_sd.ino` - Standalone with SD card logging (132 lines)

### Test/Verification Sketches
- `sht45_test.ino` - Test SHT45 sensor (93 lines)
- `current_sense_test.ino` - Calibrate current sensing (88 lines)
- `simple_voltage_divider_test.ino` - Test voltage divider (84 lines)
- `pwm_voltage_test.ino` - Test PWM approach (113 lines)

## Quick Start

### 1. Install Libraries
Arduino IDE → Tools → Manage Libraries → Install:
- **SensirionI2CSht4x** (by Sensirion AG)

### 2. Connect Hardware

**SHT45 Sensor:**
```
VCC → 5V
GND → GND
SDA → A4
SCL → A5
```

### 3. Choose Voltage Method

#### ⭐ Voltage Divider (SIMPLEST - Recommended!)
```
Arduino Pin → [24kΩ] → OUTPUT (0.2V) → Device
                         ↓
                      [1kΩ to GND]

Code:
digitalWrite(pin, HIGH);  // Apply 0.2V
digitalWrite(pin, LOW);   // Turn off
```

**Pros:** Just 2 resistors, exact 0.2V, no calibration  
**Test:** `simple_voltage_divider_test.ino`

#### PWM + Low-Pass Filter (Adjustable)
```
Arduino PWM Pin → [10kΩ] → OUTPUT → [10µF to GND] → Device

Code:
analogWrite(pin, 10);  // PWM value 10 ≈ 0.2V
```

**Pros:** Adjustable voltage  
**Cons:** Needs filter circuit  
**Test:** `pwm_voltage_test.ino`

#### External DAC (Precise)
MCP4725 module via I2C - most precise but needs additional module.

**Test:** See main sketches

### 4. Current Measurement

**Option A: INA219 Module (Easiest)**
```
INA219: V+ → Device+, V- → Device-, I2C to Arduino
```

**Option B: Shunt Resistor**
```
Device GND → [0.1Ω] → Arduino GND
Measure voltage across resistor
```

### 5. Test & Run

**Step 1:** Test SHT45 - Upload `sht45_test.ino`  
**Step 2:** Test current sensing - Upload `current_sense_test.ino`  
**Step 3:** Run full system - Upload `device_current_test.ino`  
**Step 4:** Monitor Serial at 115200 baud

## Configuration

Edit in main sketch:
```cpp
#define NUM_DEVICES 6              // Number of devices
#define TARGET_VOLTAGE 0.2         // Applied voltage
float CURRENT_SENSE_SCALE = 0.001; // Calibration factor
```

## Output Format

**CSV:**
```
Timestamp,Device,Temp(C),Humidity(%),Voltage(V),Current(A)
00:05:23,0,23.45,45.67,0.200,0.000123
```

**Console:**
```
Environment: 23.45°C, 45.67%
Device 0: V=0.200V, I=0.000123A
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| SHT45 not detected | Check I2C wiring, add 4.7kΩ pull-ups |
| Current always zero | Calibrate CURRENT_SENSE_SCALE |
| Voltage not 0.2V | Verify voltage divider calculation |
| SD card fails | Format as FAT32, check wiring |

## Calibration

1. Connect known current source
2. Measure with multimeter
3. Calculate: `CURRENT_SENSE_SCALE = Actual_Current / Measured_Voltage`

## Files Reference

| File | Purpose | When to Use |
|------|---------|-------------|
| `device_current_test.ino` | Main app (Serial) | PC monitoring |
| `device_current_test_with_sd.ino` | Main app (SD) | Standalone |
| `sht45_test.ino` | Sensor test | Setup/debug |
| `current_sense_test.ino` | Current test | Calibration |
| `simple_voltage_divider_test.ino` | Voltage test | Circuit test |
| `pwm_voltage_test.ino` | PWM test | PWM approach |

## Complete Workflow

1. **Setup:** Install libraries, wire SHT45
2. **Test:** Upload test sketches to verify each component
3. **Build Circuit:** Choose voltage method, add current sensing
4. **Calibrate:** Adjust CURRENT_SENSE_SCALE
5. **Run:** Upload main sketch, collect data
6. **Analyze:** CSV data for IV characteristics

## Advanced Options

**Standalone Operation:**
- Use `device_current_test_with_sd.ino`
- Requires SD card module
- Power Arduino externally

**Python Integration:**
Use existing scripts in parent directory:
- `arduino_temp_usb.py` - USB monitoring
- `arduino_temp_tray.py` - Windows tray app
- `arduino_temp_ip.py` - Ethernet connection

## Safety Notes

- Verify devices can handle 0.2V
- Add current limiting if needed
- Proper grounding
- ESD protection for sensors

## Voltage Divider Calculator

For different voltages from 5V:
```
0.2V: R1 = 24kΩ, R2 = 1kΩ
0.5V: R1 = 9kΩ, R2 = 1kΩ
1.0V: R1 = 4kΩ, R2 = 1kΩ

Formula: R1/R2 = (Vin/Vout) - 1
```

## Key Understanding

**PWM doesn't give smooth DC:**  
`analogWrite()` creates a square wave switching between 0V-5V. Average is 0.2V, but devices see the switching. Use a low-pass filter to smooth it, or use a voltage divider for steady 0.2V.

**Best for fixed 0.2V:**  
Voltage divider with 24kΩ and 1kΩ resistors - simplest and most accurate.

---

**Total Files:** 6 sketches + documentation  
**Hardware:** Arduino Uno + SHT45 + 2 resistors (voltage divider) + current sensor














