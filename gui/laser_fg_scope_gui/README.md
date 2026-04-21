# Laser FG Scope GUI

> ## Important Status Note (Apr 2026)
> The current Siglent SDG1032X firmware used in this setup has shown unstable
> behavior for this workflow (burst state dropping to OFF, trigger-source write
> inconsistencies, and output-enable transients). As a temporary mitigation, the
> GUI simple-pulse path is configured as **single pulse with burst disabled**.
> If robust production use is needed, moving to a different function generator
> with deterministic one-shot triggering is strongly recommended.

A standalone measurement tool for firing precision laser pulses at a device under test (DUT)
and capturing the resulting electrical response on an oscilloscope. DC bias is applied to the
DUT by a Keithley 4200 SMU throughout the measurement.

---

## What This Experiment Does

A semiconductor (or other photosensitive) device is biased at a known DC voltage. A laser
fires a short, timed pulse of light at the device. The device's electrical response to that
light pulse — current spike, voltage transient, resistance change — is captured by an
oscilloscope. By varying the pulse width, laser power, or DC bias, you can characterise how
the device responds to light as a function of those parameters.

```
Laser pulse → Device → Electrical response → Oscilloscope
                 ↑
           4200 SMU (DC bias)
```

---

## How the Timing Works

The Siglent SDG1032X function generator is the **timing master** for the entire system.
No software is involved in the timing path between the laser pulse and the scope capture.

```
PC sends "fire" command (SCPI, ~1–5 ms software delay — irrelevant)
         │
         ▼
SDG1032X ──CH1 output──► Laser DM input (TTL gate, ≤2 ns laser response)
              │
              └── SYNC OUT BNC ──► Scope EXT TRIG BNC (hardware, ~1 ns)
                                          │
                                          ▼
                                   Scope captures DUT waveform
```

Once the SDG1032X fires, the scope is triggered by a direct BNC-to-BNC hardware connection.
The 4200 SMU plays no role in timing; it simply holds a fixed bias voltage.

---

## Physical Connections

### Required Cables

| From | To | Cable |
|---|---|---|
| SDG1032X **CH1 output** (front BNC) | Laser **DM input** (see below) | BNC to appropriate connector |
| SDG1032X **SYNC OUT** (rear BNC) | Oscilloscope **EXT TRIG** (rear BNC) | BNC-to-BNC |
| Oscilloscope **CH1** (front BNC) | DUT output (probe or BNC) | Probe or coax |
| 4200 SMU **Force/Sense** | DUT bias terminals | SMU probe cables |
| Laser **RS-232 / USB** | PC | Serial or USB cable |
| SDG1032X **USB** (rear) | PC | USB-B cable |
| Oscilloscope **USB** (rear) | PC | USB-B cable |
| 4200 **GPIB or USB** | PC | GPIB or USB cable |

### Laser Digital Modulation Input (DM Input)

The Oxxius LBX-405 modulation input location depends on your specific variant:

- **Integrated version (with controller box):** The DM input is typically a BNC connector
  on the rear panel of the controller, or a pin on the DB15 D-sub connector.
  Check the wiring diagram in your Oxxius LBX user manual (Chapter: "Electrical Interface").
- **OEM version:** May expose the modulation input on a DB9 or direct BNC on the laser head.

**Input specification:** TTL, 0–5 V, ≥ 150 MHz bandwidth. The SDG1032X CH1 output should be
set to 3.3 V or 5 V high level, 0 V low level, 50 Ω output load.

### Scope Trigger

The oscilloscope **EXT TRIG** input (rear BNC on TBS1000C) receives the SDG1032X SYNC OUT
signal directly. Set the trigger:
- Source: EXT
- Level: 1.5 V (TTL midpoint)
- Slope: Rising edge
- Mode: SINGLE (one capture per run)

### 4200 SMU

Connect the SMU Force and Sense outputs to the two bias terminals of the DUT using the
appropriate probes or cabling for your test fixture.

---

## Safety Notes

**Laser safety — Class 3B**

- The Oxxius LBX-405-300 is a **Class 3B laser** (405 nm, 300 mW). This can cause
  **immediate and permanent eye damage** if the beam enters the eye directly or via
  specular (mirror-like) reflection.
- Always wear appropriate laser safety eyewear rated for 405 nm before powering the laser.
- Ensure all beam paths are enclosed or directed away from personnel before arming the laser.
- The laser emits even when the DM input is LOW (0 V) if emission is enabled (`DL 1`).
  In DM1 mode, LOW = laser off, HIGH = laser fires — but confirm this with your model.
- Never power up the laser without first setting a safe power level (`PM <mW>`) in software.

**Electrical safety**

- The TBS1000C inputs are rated to 300 VRMS. Do not exceed this with DUT voltages or
  ground offsets.
- The 4200 SMU can source voltages up to ±200 V depending on configuration. Confirm
  the compliance setting before connecting to the DUT.
- Do not connect or disconnect BNC cables while the SDG1032X output is active.

---

## Software Prerequisites

```
pip install pyvisa pyvisa-py pyserial numpy matplotlib
```

You also need one of:
- **NI-VISA** (full, includes NI-MAX for instrument discovery): download from ni.com
- **pyvisa-py** (pure Python backend, no NI software required): installed above

The SDG1032X and TBS1000C connect over USB (USBTMC). The 4200 uses GPIB or USB-GPIB
adapter. The Oxxius laser uses RS-232 serial (or USB-serial adapter).

---

## Quick Start

1. **Connect all cables** as described in the Physical Connections section above.
2. **Put on laser safety eyewear.**
3. **Launch the GUI:**
   ```
   python Laser_FG_Scope_GUI.py
   ```
4. **Connection panel:** enter VISA addresses for FG, scope, and 4200; enter COM port
   for the laser. Click each **Connect** button and confirm green status.
5. **Laser panel:** enter the desired laser power in mW. Click **Arm DM1** — this sends
   `PM <value>`, `DM 1`, and `DL 1` to the laser over serial. The laser is now on,
   but the TTL gate from the SDG1032X is currently LOW, so no light is emitted.
6. **4200 Bias panel:** enter the bias voltage (V) and click **Output ON**.
7. **Function Generator panel (Simple Pulse tab):**
   - High voltage: 3.3 V (or 5 V)
   - Low voltage: 0 V
   - Pulse width: start with 100 ns
   - Burst count: 1 (single shot)
8. **Scope panel:** set timebase to ~50 ns/div for a 100 ns pulse. Leave
   auto-configure enabled to let the GUI set trigger and channel automatically.
9. **Click Run.** The GUI will:
   - Configure the FG and scope
   - Arm the scope (waiting for hardware trigger)
   - Fire the FG burst
   - Read the waveform back
   - Display the result on the plot
10. **Save** the waveform using the Save button (exports CSV and PNG).

---

## Finding VISA Addresses

In Python:
```python
import pyvisa
rm = pyvisa.ResourceManager()
print(rm.list_resources())
```

Or use NI-MAX (if NI-VISA installed) to scan for instruments.

Typical addresses:
- SDG1032X (USB): `USB0::0xF4EC::0x1103::SDG1XCAQ3R3184::INSTR`
- TBS1000C (USB): `USB0::0x0699::0x03C7::xxxxxxxx::INSTR`
- 4200 (GPIB): `GPIB0::17::INSTR` (check GPIB address on the 4200 front panel)

---

## Hardware Limits at a Glance

| Parameter | Limit | Limited by |
|---|---|---|
| Minimum pulse width | 32.6 ns | SDG1032X |
| Pulse width resolution | 100 ps | SDG1032X |
| Timing jitter | ~300 ps | SDG1032X |
| Laser rise/fall (DM mode) | ≤ 2 ns | Oxxius LBX-405 |
| Scope time resolution | 1 ns | TBS1000C at 1 GS/s |
| Scope bandwidth (100 MHz model) | ~3.5 ns rise time | TBS1102C |

See [`Documents/reference/LASER_FG_SCOPE_HARDWARE_LIMITS.md`](../../Documents/reference/LASER_FG_SCOPE_HARDWARE_LIMITS.md)
for full details.

---

## Known Limitations and Notes

### ARB Pattern Mode

The ARB (arbitrary waveform) tab allows complex multi-pulse patterns with variable spacing.
This mode requires the SDG1032X ARB upload to be verified working with the `WVDT` binary
command. If the ARB tab is disabled or shows a warning, the driver fix has not been
applied yet. Use Simple Pulse mode in the meantime.

**Why it's tricky:** The SDG1000X requires waveform data in binary little-endian 16-bit
format sent via the `WVDT` SCPI command — not ASCII text. The `ARWV` command (which looks
similar) only selects from built-in waveforms and cannot upload data.

### 4200 Bias Only

The 4200 applies a fixed DC voltage. It does not measure during or between pulses in this
tool. If you need current measurements, use a sense resistor in series with the DUT and
monitor it on a second oscilloscope channel, or use a current probe.

### Single-Shot Capture

Each Run fires one burst and captures one scope record. For repeated measurements, use the
burst count (N pulses per trigger) and set the scope timebase accordingly to see all pulses.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Scope does not trigger | SYNC OUT not connected to EXT TRIG | Check BNC cable; confirm SDG1032X SYNC is enabled (rear panel) |
| Laser does not fire | DM1 not armed, or emission not on | Click "Arm DM1" in laser panel; check laser status LED |
| Waveform is flat | DUT not connected, or wrong scope channel | Check probing; confirm channel number in scope panel |
| FG error on connect | Wrong VISA address | Run `pyvisa.ResourceManager().list_resources()` to find correct address |
| ARB upload fails | Driver bug (ARWV vs WVDT) | Use Simple Pulse mode; see ARB limitation above |
| Laser comes on at full power on connect | Safe power not set | Power level is set to 10 mW by default on connect; do not close/reopen the laser connection without re-arming |

---

*For full instrument hardware limits, see [`Documents/reference/LASER_FG_SCOPE_HARDWARE_LIMITS.md`](../../Documents/reference/LASER_FG_SCOPE_HARDWARE_LIMITS.md)*
