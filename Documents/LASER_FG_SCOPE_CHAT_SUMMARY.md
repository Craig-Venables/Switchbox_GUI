# Laser FG Scope GUI — Design Chat Summary

**Date:** April 2026  
**Chat ref:** [Laser FG Scope GUI design & implementation](2b11e63d-3102-4414-85e8-955e7d7257de)

---

## What This Is

A new standalone measurement tool for firing precision laser pulses at a device under test (DUT)
and capturing the resulting electrical response on an oscilloscope. A Keithley 4200 SMU holds
a steady DC bias on the device throughout.

**The tool lives at:** `Laser_FG_Scope_GUI.py` (project root)  
**Launched from measurement_gui:** More Tests → **Laser FG Scope** button  
**All source:** `gui/laser_fg_scope_gui/`

---

## Why This Setup Exists

The original plan was to use the 4200 PMU to pulse the laser via its analog input, and use the
function generator for DC bias. During discussion it became clear that:

1. **4200 PMU timing is unsuitable for nanosecond laser pulses.** Its TTL signals are unreliable
   (fires once at start, once later), and the minimum analog pulse width achievable limits high-speed
   work.
2. **A function generator makes a poor DC bias source** — it drifts and has no current compliance.

### Role reversal adopted

| Instrument | Old role | New role |
|---|---|---|
| Siglent SDG1032X FG | DC bias source | **Timing master** — fires laser via TTL, triggers scope via SYNC OUT |
| Keithley 4200 SMU | Laser driver | **Passive DC bias only** — no timing, no measurement |
| Oxxius LBX-405 | Analog-modulated | **DM1 digital modulation mode** — TTL-gated, ≤2 ns rise |
| TBS1000C Scope | Result capture | Same — now hardware-triggered from FG SYNC OUT |

---

## How the 4200 Bias Works

**We use KXCI interactive-mode commands directly — no C module, no User Library (EX/UL) mode.**

```python
# In logic.py  _Keithley4200Bias class:
inst.write(f"DV {channel},0,{voltage:.6f},{compliance:.6e}")  # force voltage
inst.write(f"CN {channel}")    # connect (enable output)
# ... measurement runs ...
inst.write(f"CL {channel}")    # clear / disconnect at end
```

| KXCI command | Effect |
|---|---|
| `DV ch,0,voltage,compliance` | Force a DC voltage on SMU channel. Range=0 means auto. |
| `CN ch` | Connect (enable) the output |
| `CL ch` | Clear / disconnect the output |

**Why not the C code?**

The existing C modules (`smu_ivsweep`, `SMU_BiasTimedRead`, `smu_check_connection`) require UL
mode and either sweep through voltages or run a timed sampling loop. For this GUI we just need
to hold a steady voltage while the FG + scope does the fast pulse work. The interactive KXCI
commands are simpler, don't require entering UL mode, and release immediately — perfect for a
"set and forget" bias.

If you later need current logging alongside the laser pulse, `SMU_BiasTimedRead` can be used:
see `Equipment/SMU_AND_PMU/4200A/C_Code_with_python_scripts/SMU_BiasTimedRead/`.

---

## ARB Waveform Upload Fix

A critical bug was found in `Equipment/Function_Generator/Siglent_SDG1032X.py`:

| | Before (broken) | After (fixed) |
|---|---|---|
| Command | `ARWV NAME,x,DATA,…` | `WVDT WVNM,x,TYPE,5,LENGTH,NB,…,WAVEDATA,<binary>` |
| Data format | ASCII comma-separated floats | Binary little-endian 16-bit signed integers |
| Transfer method | `write()` with text terminator | `write_raw()` with `write_termination=''` |

The `ARWV` command only *selects* built-in waveforms — it cannot upload user data. The correct
upload command is `WVDT`. This fix is now in place.

New method: `upload_arb_waveform(channel, samples_normalized, waveform_name, freq_hz, amplitude_v, offset_v)`  
Helper: `build_ttl_pulse_samples([(level, duration_s), ...], sample_rate_hz)` → normalised list

---

## Timing Chain (why it works)

```
PC software (Python)
  └─ sends C1:TRIG to SDG1032X
       └─ CH1 output fires pulse
            └─ Laser DM1 input → laser fires  (≤ 2 ns rise)
       └─ SYNC OUT fires simultaneously (hardware)
            └─ TBS1000C EXT TRIG → acquisition starts
                 └─ captures DUT response on CH1
```

Everything after `C1:TRIG` is **hardware synchronised** — no Python OS timing involved.
The only soft timing is the 15 ms sleep before `C1:TRIG` to ensure the scope is armed.

---

## Files Created / Modified

### New files
| File | Purpose |
|---|---|
| `Laser_FG_Scope_GUI.py` | Standalone launcher |
| `gui/laser_fg_scope_gui/__init__.py` | Package init |
| `gui/laser_fg_scope_gui/main.py` | Main `tk.Toplevel` window |
| `gui/laser_fg_scope_gui/logic.py` | Measurement thread + `_Keithley4200Bias` |
| `gui/laser_fg_scope_gui/layout.py` | 3-tab layout (Controls / Connections / Help) |
| `gui/laser_fg_scope_gui/config.py` | Colour palette, defaults |
| `gui/laser_fg_scope_gui/config_manager.py` | JSON settings persistence; reads scope defaults from oscilloscope_pulse_gui |
| `gui/laser_fg_scope_gui/ui/connection.py` | Instrument address + connect buttons |
| `gui/laser_fg_scope_gui/ui/laser_panel.py` | Power spinbox, Arm DM1 / Disarm |
| `gui/laser_fg_scope_gui/ui/fg_panel.py` | Simple Pulse tab + ARB Pattern tab |
| `gui/laser_fg_scope_gui/ui/scope_panel.py` | Timebase, trigger, V/div |
| `gui/laser_fg_scope_gui/ui/bias_panel.py` | 4200 voltage + compliance |
| `gui/laser_fg_scope_gui/ui/help_panel.py` | Wiring diagram image + documentation tabs |
| `gui/laser_fg_scope_gui/ui/plot_panel.py` | Matplotlib waveform + Save CSV/PNG |
| `gui/laser_fg_scope_gui/wiring_diagram.png` | Instrument wiring reference image |
| `gui/laser_fg_scope_gui/README.md` | Physical connections, safety, quick start |
| `Documents/reference/LASER_FG_SCOPE_GUI_REFERENCE.md` | Full operational reference |
| `Documents/reference/LASER_FG_SCOPE_HARDWARE_LIMITS.md` | Hardware speed limits |

### Modified files
| File | Change |
|---|---|
| `Equipment/Function_Generator/Siglent_SDG1032X.py` | Fixed ARB upload (WVDT binary) |
| `Equipment/managers/function_generator.py` | Exposed `upload_arb_waveform()` + `build_ttl_pulse_samples()` |
| `gui/measurement_gui/main.py` | Added "Laser FG Scope" button in More Tests section |

---

## GUI Layout

The window uses a **split-pane layout**:

```
┌─────────────────────┬──────────────────────────────────┐
│  [Controls]  [Connections]  [Help]  ◄ tab strip        │
│                     │                                   │
│  Controls tab:      │  Waveform plot                    │
│  ├ Laser panel      │  (matplotlib, zoomable)           │
│  ├ FG panel         │                                   │
│  │  ├ Simple Pulse  │                                   │
│  │  └ ARB Pattern   │                                   │
│  ├ Scope settings   │                                   │
│  ├ 4200 bias        │                                   │
│  └ Run / Stop       │                                   │
│                     │                                   │
│  Connections tab:   │  Save CSV + PNG                   │
│  └ 4 addr entries   │                                   │
│                     │                                   │
│  Help tab:          │                                   │
│  └ wiring diagram   │                                   │
│  └ text docs        │                                   │
└─────────────────────┴──────────────────────────────────┘
  Status bar
```

---

## Known Limitations / Future Work

- **Single-shot only.** No streaming or averaging.
- **4200 reads nothing.** Bias-only. Current readback needs `SMU_BiasTimedRead` integration.
- **Scope RST on auto-configure** resets all scope settings. Disable if you've set up manually.
- **ARB max 16,384 points.** For patterns longer than ~546 µs, reduce sample rate.
- **Integration into pulse_testing_gui** is deferred — this is a standalone tool for now.
