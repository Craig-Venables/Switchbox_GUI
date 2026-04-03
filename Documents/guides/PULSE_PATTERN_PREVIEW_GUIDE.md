# Pulse Pattern Preview Guide

## Visual Guide to Understanding Test Previews

### ❌ Electrical Pulse Train (Memristor Programming)
**Test**: "⚡ Electrical Pulse Train (Memristor Programming)"

**What you see**:
```
Voltage (V)
    2V  ▄▄    ▄▄         ▄▄         ▄▄
        ██    ██         ██         ██
    0V  ██▄▄▄▄██▄▄▄▄▄▄▄▄▄██▄▄▄▄▄▄▄▄▄██
        ↑  x  ↑  x      ↑  x      ↑  x
       Pulse Read   Pulse Read  Pulse Read
```

**Legend**:
- **Cyan filled blocks** = Electrical voltage pulses (SET/RESET)
- **Red X marks** = Read measurements
- **Height of blocks** = Pulse voltage (can vary: 2V, -2V, 0V)

**This shows**: SMU alternating between pulsing voltage and reading

---

### ✅ Optical: Laser Pattern + Continuous Read
**Test**: "🔬 Optical: Laser Pattern + Continuous Read"  
**Pattern**: "11010"

**What you see**:
```
Laser (ON/OFF)
    ON  ▇▇▇     ▇▇▇           ▇▇▇
        ███     ███           ███
   OFF  ███▁▁▁▁▁███▁▁▁▁▁▁▁▁▁▁▁███▁▁▁▁▁
        slot0   slot1   slot2  slot3  slot4
         1       1       0       1      0

SMU Voltage (V)
   0.2V ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        (Continuous read throughout)
```

**Legend**:
- **Blue line** (flat) = SMU reading continuously at 0.2V
- **Red blocks** = Laser fires (only where pattern = '1')
- **Gray dotted lines** = Skipped laser slots (where pattern = '0')
- **Gaps** = Time between laser pulse slots

**This shows**: SMU reads continuously while laser fires per pattern

---

## Side-by-Side Comparison

| Feature | Electrical Pulse Train | Optical Laser Pattern |
|---------|----------------------|----------------------|
| **SMU Behavior** | Pulses voltage ON/OFF | Continuous read (flat line) |
| **Blocks/Rectangles** | Electrical voltage pulses | Laser light pulses |
| **Block Height** | Voltage amplitude (V) | ON/OFF indicator |
| **X Marks** | Read measurements | Not shown (reads continuously) |
| **Pattern Control** | Which electrical pulses fire | Which laser pulses fire |
| **Use For** | Memristor programming | Optical experiments |

---

## How to Read the New Optical Pattern Preview

### Example: Pattern "11010"

```
Time (s) →
0.0      0.3      0.6      0.9      1.2      1.5
│        │        │        │        │        │
│ ▇▇▇    │ ▇▇▇    │        │ ▇▇▇    │        │  Laser
│ ███    │ ███    │   :    │ ███    │   :    │  (red)
│ ███▁▁▁▁│▁███▁▁▁▁│▁▁▁:▁▁▁▁│▁███▁▁▁▁│▁▁▁:▁▁▁▁│
│   1    │   1    │   0    │   1    │   0    │  Pattern
│        │        │        │        │        │
│━━━━━━━━│━━━━━━━━│━━━━━━━━│━━━━━━━━│━━━━━━━━│  SMU
│  0.2V  │  0.2V  │  0.2V  │  0.2V  │  0.2V  │  (blue)
```

**Reading the preview**:
1. **Blue line**: SMU voltage stays constant at 0.2V (continuous read)
2. **Red blocks**: Laser fires for 100ms
3. **Gaps**: 200ms between laser slots
4. **Dotted lines** (`:` in ASCII): Skipped laser slots (pattern = '0')

### Visual Indicators:
- ▇▇▇ (solid red) = Laser firing
- ━━━ (solid blue) = SMU continuous read
- `:` (dotted gray) = Skipped laser slot
- Numbers = Binary pattern (1=fire, 0=skip)

---

## Quick Reference

**If you see cyan blocks + X marks** → Electrical pulse train (memristor programming)  
**If you see flat blue line + red blocks** → Optical test (laser + continuous SMU read)  
**If red blocks have gaps with dotted lines** → Pattern control (some slots skipped)

---

## Testing the Preview

1. Select **"🔬 Optical: Laser Pattern + Continuous Read"**
2. Set parameters:
   - `read_voltage`: 0.2V
   - `num_laser_pulses`: 5
   - `laser_pattern`: "11010"
   - `optical_on_ms`: 100
   - `optical_off_ms`: 200
3. Look at pulse pattern preview

**You should see**:
- Flat blue line at 0.2V (SMU continuous read)
- 3 red rectangles (at slots 0, 1, 3)
- 2 dotted gray lines (at slots 2, 4) showing skipped pulses
- Title: "🔬 Optical Pattern: "11010" (3 fire, 2 skip)"
