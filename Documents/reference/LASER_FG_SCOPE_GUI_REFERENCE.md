# Laser FG Scope GUI — Reference

> **Tool location:** `Laser_FG_Scope_GUI.py` (project root)  
> **Module:** `gui/laser_fg_scope_gui/`  
> **Launch:** `python Laser_FG_Scope_GUI.py`

This document is the operational reference for the standalone Laser + Function Generator + Oscilloscope
experiment GUI. It covers the experiment concept, physical connections, software architecture, SCPI
command sequences, ARB waveform encoding, and parameter guidance.

For installation and quick-start, see `gui/laser_fg_scope_gui/README.md`.  
For hardware speed limits, see `Documents/reference/LASER_FG_SCOPE_HARDWARE_LIMITS.md`.

---

## Instrument Roles

| Instrument | Model | Interface | Role |
|---|---|---|---|
| Function Generator | Siglent SDG1032X | USB (VISA) | **Timing master** — fires laser TTL, triggers scope via SYNC OUT |
| Laser | Oxxius LBX-405-300-CSB-PPA | RS-232 / USB serial | Light source in DM1 TTL-gate mode |
| Oscilloscope | Tektronix TBS1000C | USB (VISA) | Waveform capture — hardware-triggered from FG SYNC OUT |
| SMU | Keithley 4200-SCS | GPIB | Passive DC bias source — **no timing role** |

The SDG1032X is the sole timing master. Its `SYNC OUT` BNC connects directly to the scope `EXT TRIG`
input so that trigger latency is hardware-locked (sub-nanosecond jitter), independent of Python/OS timing.

---

## Physical Connections

```
Siglent SDG1032X
  CH1 output  ──[ SMA cable, 50 Ω ]──► Oxxius LBX-405  MOD IN (SMA)
  SYNC OUT    ──[ BNC cable, 50 Ω ]──► TBS1000C  EXT TRIG (BNC)
  USB-B       ──────────────────────► PC USB

Tektronix TBS1000C
  CH1 (or CH2) ──[ 10× probe ]──► DUT output terminal
  USB-B        ──────────────────► PC USB

Keithley 4200-SCS SMU1
  FORCE / HI   ─┐
  FORCE / LO   ─┤──► DUT bias terminals (triax or BNC)
  GPIB         ──────────────────► PC GPIB card

Oxxius LBX-405
  MOD IN ◄──── from SDG1032X CH1 (see above)
  RS-232 / USB ─────────────────► PC COM port
  Beam output ──────────────────► DUT sample (free-space)

Ground / Common:
  All BNC shields connected at a single star ground point.
```

---

## Software Architecture

```
Laser_FG_Scope_GUI.py            ← standalone launcher (root)
gui/laser_fg_scope_gui/
├── __init__.py                  ← exports LaserFGScopeGUI
├── main.py                      ← LaserFGScopeGUI (tk.Toplevel)
│     handles: instrument connect/disconnect, run/stop, settings save
├── logic.py                     ← LaserFGScopeLogic
│     _Keithley4200Bias           ← minimal KXCI bias wrapper
│     connect_*(), run_measurement(), _run_sequence(), _read_waveform()
├── layout.py                    ← LayoutBuilder (two-column layout)
├── config.py                    ← colours, fonts, defaults
├── config_manager.py            ← JSON settings load/save
└── ui/
    ├── connection.py            ← 4 × instrument connection rows
    ├── laser_panel.py           ← power, Arm DM1, status
    ├── fg_panel.py              ← Simple Pulse tab + ARB Pattern tab
    ├── scope_panel.py           ← timebase, trigger, V/div
    ├── bias_panel.py            ← 4200 SMU voltage + compliance
    ├── help_panel.py            ← collapsible in-GUI documentation
    └── plot_panel.py            ← matplotlib waveform display + save
```

Reused drivers:
- `Equipment/managers/function_generator.py` → `FunctionGeneratorManager`
- `Equipment/Function_Generator/Siglent_SDG1032X.py` → raw SCPI driver
- `Equipment/Laser_Controller/oxxius.py` → `OxxiusLaser`
- `Equipment/managers/oscilloscope.py` → `OscilloscopeManager`
- `Equipment/Oscilloscopes/TektronixTBS1000C.py` → scope SCPI + waveform read

---

## Measurement Sequence (logic.py `_run_sequence`)

```
1. 4200 SMU: DV <ch>,0,<bias_v>,<compliance>  → CN <ch>   (set + enable bias)
2. Laser   : PM <power_mw>  →  DM 1  →  emission on        (arm TTL gate)
3. FG      :
   Simple Pulse:  set_pulse_shape + enable_burst(TRSR=BUS)
   ARB Pattern:   upload_arb_waveform (WVDT binary) + enable_burst(TRSR=BUS)
   CH1 output ON
4. Scope   : *RST, set CH scale, HOR:SCA, TRIG EXT, ACQ:STOPA SEQ
             ACQ:STATE RUN  ← arm for single acquisition
5. sleep(15 ms)             ← ensure scope is armed
6. FG      : C1:TRIG        ← software-trigger the burst
             CH1 pulse fires → laser pulses
             SYNC OUT fires  → scope EXT TRIG → acquisition starts
             (all hardware-synchronised — no Python timing involved)
7. Poll scope TRIG:STATE? until SAVE / TRIGGER, then sleep(capture_wait_s)
8. Scope   : DAT:SOU CH<n>  →  DAT:ENC ASCII  →  WFMO?  →  CURV?
             scale raw ADC codes via preamble YMULT/YOFF/YZERO
             build time array from XINCR
9. Return time[], voltage[] arrays → plot_panel.update_plot()
```

---

## ARB Waveform Encoding (SDG1000X)

### Why WVDT, not ARWV

The `ARWV` command on the SDG1000X only **selects** a built-in or already-stored
waveform by name or index. It does **not** upload user data.

User waveform upload requires the `WVDT` command with binary data:

```
C1:WVDT WVNM,<name>,TYPE,5,LENGTH,<N>B,FREQ,<f>,AMPL,<v>,OFST,<v/2>,PHASE,0,WAVEDATA,<binary>
```

### Binary encoding

Each waveform sample is a **14-bit signed integer** stored as a **little-endian 16-bit signed int**:

| Normalised value | 14-bit int | Output voltage |
|---|---|---|
| +1.0 | +8191 (0x1FFE) | OFST + AMPL/2  (HIGH) |
| 0.0  | 0              | OFST           (mid)  |
| −1.0 | −8192 (0xE000) | OFST − AMPL/2  (LOW)  |

Python packing: `struct.pack('<{N}h', *dac_values)`

The full byte sequence is sent with `inst.write_raw(header_bytes + binary_data + b'\n')`
with `write_termination = ''` to prevent write_termination corruption of binary data.

### After upload

```
C1:ARWV NAME,<name>       ← select uploaded waveform
C1:BSWV WVTP,ARB          ← set channel to ARB mode
```

### ARB limits

| Parameter | Limit |
|---|---|
| Max points | 16,384 |
| Max sample rate | 30 MSa/s |
| Min resolution | 33 ns/point at 30 MSa/s |
| Max duration | ~546 µs at 30 MSa/s, ~16 ms at 1 MSa/s |

---

## 4200 SMU Bias — KXCI Commands

The GUI uses bare KXCI (not UL/EX mode) for simple SMU bias:

| Command | Effect |
|---|---|
| `DV <ch>,0,<voltage>,<compliance>` | Set channel voltage with auto-range and compliance |
| `CN <ch>` | Connect (enable) SMU output |
| `CL <ch>` | Disconnect (disable) SMU output |

The 4200 does **not** measure anything in this workflow. If I-V measurement is needed,
consider integrating the existing `oscilloscope_pulse_gui` pattern.

---

## Settings Persistence

Settings are saved to `gui/laser_fg_scope_gui/laser_fg_scope_config.json` on:
- Window close
- File → Save settings

On startup the saved settings are restored. First-run defaults are in `config.py`.

---

## Known Limitations

| Limitation | Notes |
|---|---|
| Single-shot only | One scope acquisition per Run. No streaming / averaging. |
| No 4200 readback | SMU is bias-only. Current readback would need additional logic. |
| Scope RST on auto-config | `*RST` resets all scope settings — turn off auto-configure to avoid. |
| ARB max 16,384 points | For patterns longer than ~546 µs, reduce sample rate. |
| Windows only tested | The `os.startfile` for README uses Windows API. |

---

## Troubleshooting

**Scope shows no trigger / flat line**
- Confirm SYNC OUT → EXT TRIG cable is connected and the BNC shield is grounded.
- Increase trigger level: SYNC OUT amplitude is ~3.3 V, set trigger to 1.5–2.0 V.
- Check `ACQ:STATE?` returns `RUN` before the FG fires.

**Laser does not emit**
- Verify DM1 is armed (Arm DM1 button pressed, green indicator).
- Check CH1 HIGH voltage ≥ 2.5 V (Oxxius DM1 TTL threshold).
- Verify SMA cable connects SDG1032X CH1 to laser MOD IN.

**ARB upload fails / waveform looks wrong**
- Ensure `write_termination = ''` during `write_raw` (handled automatically).
- Total points must be ≤ 16,384; reduce sample rate or shorten segments.
- Check instrument error queue: `C1:SYST:ERR?`

**4200 GPIB connection fails**
- Verify GPIB address: default `GPIB0::17::INSTR`.
- Ensure NI-VISA or equivalent is installed and GPIB card is recognised.
- Try `python -c "import pyvisa; rm = pyvisa.ResourceManager(); print(rm.list_resources())"`.
