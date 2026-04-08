# Laser + Function Generator + Oscilloscope Experiment — Hardware Limits Reference

This document records the confirmed hardware limits and timing constraints for the combined
**Oxxius LBX-405 + Siglent SDG1032X + Tektronix TBS1000C + Keithley 4200** experiment setup.
It was produced during design discussion and should be consulted before setting pulse parameters.

---

## Instrument Roles in This Setup

| Instrument | Role | Timing role |
|---|---|---|
| Siglent SDG1032X | Fires laser via TTL/DM input; triggers scope via SYNC OUT | **Master clock** |
| Oxxius LBX-405-300-CSB-PPA | Light source; DM1 mode, power set over serial | Responds to FG |
| Tektronix TBS1000C | Captures DUT electrical response | Slave (triggered by FG SYNC OUT) |
| Keithley 4200 SMU | Applies DC bias to device under test | **No timing role** |

The Keithley 4200's TTL output is **not used** for triggering in this setup. It fires unpredictably
(once at measurement initiation, once at completion) and cannot be used as a precision trigger.
The 4200 SMU simply holds a fixed DC bias throughout each capture.

---

## 1. Oxxius LBX-405-300-CSB-PPA Laser

Source: Oxxius official datasheet (confirmed April 2026)

### Digital Modulation (DM1 mode) — used in this setup

| Parameter | Value |
|---|---|
| Rise / fall time (10–90%) | **≤ 2 ns** |
| Modulation bandwidth | **≥ 150 MHz** |
| Input signal type | TTL levels |
| Control | `DM 1` command over RS-232/USB, then TTL signal controls gate |
| Power level during DM | Set once via `PM <value>` (mW) over serial before arming TTL |

**The laser is not the timing bottleneck.** It responds faster than the SDG1032X can switch.

### Analog Modulation (AM1 mode) — not used in this setup, for reference

| Parameter | Value |
|---|---|
| Rise / fall time (10–90%, ACC mode) | **≤ 150 ns** |
| Bandwidth (3 dB, ACC mode) | **≥ 3 MHz** |
| Input voltage range | 0–5 V |
| Power scaling | 0–100% of `PM` setpoint |

Analog mode is limited by the APC control loop. Do not use it if pulse widths below ~1 µs are needed.

### Serial Control (DL 1 / DL 0) — not used for fast pulses

| Parameter | Value |
|---|---|
| Minimum reliable pulse width | **~20 ms** |
| Serial overhead per on+off cycle | ~10 ms (measured on COM4, 19200 baud) |
| Max switching rate | ~10–50 Hz |

Serial is only suitable for ms-scale pulses. For anything faster, use the TTL/DM1 input.

### Key Serial Commands

```
APC 1        — Enable automatic power control
AM 0         — Disable analog modulation
DM 1         — Enable digital modulation (TTL gate now controls emission)
PM <value>   — Set power in mW (e.g., PM 50 for 50 mW)
DL 1 / DL 0 — Emission on / off (serial, ms-scale only)
```

---

## 2. Siglent SDG1032X Function Generator

Source: Siglent SDG1000X Series datasheet (confirmed April 2026)

This is the **timing master** for the entire experiment. Its SYNC OUT BNC triggers the oscilloscope
via a direct BNC-to-BNC hardware connection, so there is no software latency in the trigger path.

### Pulse Mode (EasyPulse)

| Parameter | Value |
|---|---|
| Minimum pulse width | **32.6 ns** |
| Pulse width resolution | **100 ps** |
| Rise / fall time (minimum, 10–90%) | **16.8 ns** |
| Rise / fall time (maximum) | 22.4 s |
| Rise / fall time resolution | 100 ps |
| Cycle-to-cycle jitter (RMS) | **300 ps + 0.05 ppm of period** |
| Max pulse frequency | 12.5 MHz |

### Square Wave Mode (special circuit — alternative for very fast edges)

| Parameter | Value |
|---|---|
| Rise / fall time (10–90%) | **4.2 ns** |
| Max frequency | **30 MHz** |
| Jitter (RMS) | 300 ps + 0.05 ppm |

Use square mode if you need the fastest edges (4.2 ns vs 16.8 ns in pulse mode).
Use pulse mode if you need independent control of pulse width and duty cycle.

### General

| Parameter | Value |
|---|---|
| Channels | 2 |
| Max amplitude | ±10 V (20 Vpp) |
| Vertical resolution | 14-bit |
| Interfaces | USB USBTMC, LAN (VXI-11), optional GPIB |
| Burst modes | NCYC (N cycles), GATE, INF |
| Trigger sources | INT, EXT (rear BNC), BUS (software SCPI `C1:TRIG`) |

### SYNC Output

The rear-panel SYNC OUT BNC is hardware-locked to the waveform output with no software latency.
Connect this directly to the oscilloscope's EXT TRIG input to trigger scope captures.
For burst mode (`TRSR=BUS`), the software SCPI trigger command `C1:TRIG` fires the burst;
the SYNC BNC then immediately triggers the scope in hardware.

### Software Trigger Latency

The SCPI trigger command (`C1:TRIG`) sent over USB has approximately **1–5 ms latency**.
This affects only *when in absolute wall-clock time* the pulse fires — it does **not** affect
the relative timing between the laser pulse and scope capture, which is hardware-locked.

---

## 3. Tektronix TBS1000C Oscilloscope

Source: Tektronix TBS1000C Series datasheet (confirmed April 2026)

The TBS1000C comes in four bandwidth variants. Confirm which model is in use.

| Model | Bandwidth | Rise time (calc.) | Notes |
|---|---|---|---|
| TBS1052C | 50 MHz | ~7.0 ns | Can resolve pulses ≥ ~35 ns (marginal at 32 ns floor) |
| TBS1072C | 70 MHz | ~5.0 ns | Can resolve pulses ≥ ~25 ns |
| TBS1102C | 100 MHz | ~3.5 ns | **Recommended minimum** for this setup |
| TBS1202C | 200 MHz | ~1.75 ns | Best choice if available |

### Common Specifications (all models)

| Parameter | Value |
|---|---|
| Sample rate | **1 GS/s** on all channels simultaneously |
| Sample interval | 1 ns (at 1 GS/s) |
| Record length | **20,000 points** |
| Vertical resolution | 8 bits |
| Input impedance | 1 MΩ ∥ ~20 pF |
| Max input voltage | 300 VRMS (CAT II) |
| Waveform capture rate | Up to 5,000 waveforms/second |
| EXT TRIG input | Rear BNC, TTL compatible |

### Probe Bandwidth

| Probe | Bandwidth | Rise time |
|---|---|---|
| TPP0100 (ships with 50/70 MHz models) | 100 MHz | ~3.5 ns |
| TPP0200 (ships with 200 MHz model) | 200 MHz | ~2.3 ns |

**Important:** The probe bandwidth limits the system. Always use the probe that shipped with the
scope model, or a probe rated for the scope's bandwidth or higher.

### Practical Minimum Pulse Width to Capture Cleanly

As a rule of thumb, the signal rise time should be at least 3–5× the scope's rise time for accurate
amplitude measurement. For edge timing only, a 2× margin is acceptable.

- TBS1102C (100 MHz, 3.5 ns rise): clean amplitude measurement of pulses ≥ ~17 ns; edge timing ≥ ~7 ns.
- At the SDG1032X's **32.6 ns minimum pulse width**, the TBS1102C captures it well.
- At 50 MHz (TBS1052C), the 32.6 ns pulse will show visible edge rounding and ~15% amplitude error.

---

## 4. Keithley 4200-SCS

In this setup the 4200 acts exclusively as a DC bias source (SMU mode).

| Parameter | Value / Note |
|---|---|
| Role | Passive DC bias on DUT — no timing function |
| Bias stability | High (SMU-grade, mV accuracy) |
| TTL output | **Do not use** — fires at initiation and again at completion, timing is unpredictable |
| Minimum settling time | Allow ~100 ms after setting a new voltage before firing a pulse |

---

## 5. Full Timing Chain Summary

```
PC (Python, SCPI over USB)
  │
  │  ~1–5 ms software latency (irrelevant to relative timing)
  ▼
SDG1032X  ──CH1 output──►  Laser TTL / DM input
(master)        │               │
                │               │  ≤ 2 ns laser rise/fall
                │               ▼
                │           Laser light pulse
                │               │
                │               │  (propagation through optics to DUT)
                │               ▼
                │            Device Under Test  ◄── 4200 SMU (DC bias, passive)
                │               │
                │               │  DUT electrical response
                │               ▼
                └── SYNC OUT ──► Oscilloscope EXT TRIG
                    (BNC, ~1 ns)      │
                                      │  scope captures waveform
                                      ▼
                                  Waveform stored, read back over VISA
```

### Practical Limits at Each Stage

| Stage | Limit | Dominated by |
|---|---|---|
| Minimum pulse width | **32.6 ns** | SDG1032X (EasyPulse minimum) |
| Minimum rise/fall time at laser | **4.2 ns** (square) / **16.8 ns** (pulse mode) | SDG1032X |
| Laser response to TTL | ≤ 2 ns | Oxxius LBX-405 hardware |
| Trigger-to-capture jitter | **~300 ps** | SDG1032X jitter spec |
| Scope time resolution | **1 ns** | TBS1000C sample rate (1 GS/s) |
| Scope amplitude resolution | 8 bits | TBS1000C ADC |
| DC bias accuracy | SMU-grade (mV level) | Keithley 4200 |

---

## 6. Recommended Operating Parameters

Based on the above limits, the following are safe starting parameters for this experiment:

| Parameter | Recommended starting value | Absolute minimum |
|---|---|---|
| Laser power (PM setpoint) | 10–50 mW (confirm safe for DUT) | — |
| Pulse width | 100 ns (well above FG minimum) | 32.6 ns |
| Rise/fall time (FG) | Square mode (4.2 ns) or auto | 16.8 ns (pulse mode) |
| Pulse repetition rate | 1 kHz–1 MHz | — |
| 4200 SMU bias | Per DUT spec | — |
| Scope timebase | 50–200 ns/div for 100 ns pulses | — |
| Scope trigger | EXT TRIG from SDG1032X SYNC OUT | — |
| Trigger level | ~1.5 V (TTL midpoint) | — |

---

*Last updated: April 2026. Confirm instrument model numbers before use.*
