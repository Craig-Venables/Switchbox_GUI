# Source Mode Dropdown - Implementation Complete

**Date:** October 14, 2025

---

## What Was Added

A **Source Mode dropdown** in the Sweep Parameters section:
- **Voltage** (default) - Source voltage, measure current
- **Current** - Source current, measure voltage

---

## Location

```
Main GUI → Sweep Parameters → Source Mode (top row)
```

---

## How to Use

1. **Find dropdown** at top of Sweep Parameters
2. **Select mode:**
   - `voltage` = Source V, measure I (traditional)
   - `current` = Source I, measure V (reverse)
3. **Labels auto-update** to show correct units
4. **Enter values** and measure!

---

## Label Changes

**Voltage mode:**
- Start Voltage (V), Voltage High (V), Icc (A)

**Current mode:**
- Start Current (A), Current High (A), Vcc (V)

---

## Works With

- ✅ Hardware sweep (Keithley 4200A) - 0.1-1s (no live plotting)
- ✅ Point-by-point (ALL instruments) - with live plotting ⭐

---

## Code Changes

- **Measurement_GUI.py**: Added dropdown + label updates (lines 1800-1828)
- **Measurement_GUI.py**: Integrated source mode into both sweep methods (lines 4034-4081)
- **Measurments/measurement_services_smu.py**: Extended to support source mode

---

**That's it! Just select the mode and go.**

