# One Clarius library: `A_pmu_laser_smu_read`

## What to create on the 4200

| Item | Name |
|------|------|
| **Library** | `A_pmu_laser_smu_read` |
| **Module (used by the tool — Single-shot Run tab)** | `pmu_laser_smu_run` |
| **Module (used by the tool — Live / Manual Fire tab)** | `pmu_laser_smu_stream` |
| Module (kept, not called by the tool) | `pmu_ttl_laser_ch1` |
| Module (kept, not called by the tool) | `pmu_laser_smu_start` |
| Module (kept, not called by the tool) | `pmu_laser_smu_collect` |

Use these **unique** module names (not `SMU_BiasTimedRead_*`) so Clarius `proto.h`
does not clash with any older BiasTimedRead declaration on the system.

## Why `pmu_laser_smu_run` and not three separate EX calls

The tool used to call three separate `EX` commands: `pmu_laser_smu_start` →
`pmu_ttl_laser_ch1` → `pmu_laser_smu_collect`. On real hardware this failed
on the very first `measi()` in Collect with **LPT status `-160`**
("Measurement cannot be performed because the source is not operational").

Each top-level `EX`/`UL` invocation from KXCI is its own execution context —
the SMU's `forcev()` from `pmu_laser_smu_start` did **not** remain
"operational" once that `EX` call returned and a separate `EX` call began.
So the split-into-three-calls architecture was fundamentally broken for this
KXCI/UL usage pattern, regardless of parameter formatting.

**Fix:** `pmu_laser_smu_run.c` inlines all three steps (SMU bias on → build +
fire the PMU CH1 TTL Segment ARB waveform → SMU sample loop → SMU ramp down
to 0 V) into **one** continuous C function, called with **one** `EX`
command, so the SMU source is never torn down mid-sequence.

The three original modules (`pmu_ttl_laser_ch1`, `pmu_laser_smu_start`,
`pmu_laser_smu_collect`) are kept in the library (useful for standalone
debugging / dry-run comparison) but the Python tool now only calls
`pmu_laser_smu_run`.

Cool-down `mode` ints (same in run / stream / ttl modules):
`0` single, `1` train, `2` linear cool-down, `3` exponential, `4` quadratic.

Cool-down design (current, Aug 2026 — explicit sequence):
pulse 0 is a full-`width` **write**. Pulses after that come from
`cdSequence` (`delay:width;delay:width;...` in seconds). The first
delay is the OFF gap immediately after the write; each later delay is
the OFF before the next cool-down pulse. Python GUI lines are
`delay, pulse`; wire uses `:` / `;` (no commas — those split EX args).
Legacy cdStartWidth/cdEndWidth/startPeriod are unused for cool-down shape.

Empty / `"0"` sequence → write-only.

## Source files

```
Equipment/SMU_AND_PMU/4200A/C_Code_with_python_scripts/pmu_ttl_laser_ch1/
  pmu_laser_smu_run.c         ← USED BY THE TOOL (Single-shot tab): bias + baseline + PMU TTL + sample + ramp down, one EX call
  pmu_laser_smu_stream.c      ← USED BY THE TOOL (Live/Manual Fire tab): ONE CHUNK per EX call, called repeatedly in a loop
  pmu_ttl_laser_ch1.c         ← PMU CH1 TTL only (kept for reference/debugging)
  pmu_laser_smu_start.c       ← SMU bias on only (kept for reference/debugging)
  pmu_laser_smu_collect.c     ← SMU sample I(t) only (kept for reference/debugging)
  README.md
```

Absolute path:
```
C:\Users\ppxcv1\Documents\GitHub\Switchbox_GUI\Equipment\SMU_AND_PMU\4200A\C_Code_with_python_scripts\pmu_ttl_laser_ch1\
```

## Clarius steps

1. Create library **`A_pmu_laser_smu_read`** (or empty the old one and re-add)
2. **Remove** any modules named `SMU_BiasTimedRead_Start` / `SMU_BiasTimedRead_Collect` from this library
3. Add all five `.c` files above (at minimum, add `pmu_laser_smu_run.c` AND
   `pmu_laser_smu_stream.c` — the tool calls both of these, one per tab;
   the other three are optional extras)
4. Build / load

### TTL drive strength (why scope sees a pulse but laser stays off)

These modules previously used `pulse_ranges(..., 0.01)` — the **RPM 10 mA**
current range. A 1 MΩ scope probe still shows a pulse; many laser TTL/MOD
inputs draw enough current that Vpeak sags below VIH. LabView showing the
same scope shape and also failing the laser is consistent with this.

**Now:** `pulse_load(..., 1e6)` then `pulse_ranges(..., 0.2)` (PMU 10 V /
200 mA). Rebuild this library in Clarius after updating the `.c` files.

**Still sagging after rebuild?** Put a TTL buffer between RPM and laser.
If the laser MOD input is **50 Ω terminated**, even 200 mA cannot hold 5 V
through the PMU’s ~50 Ω source Z (loaded ≈ 2.5 V) — a buffer is required.

## KXCI (Python already matches)

```text
EX A_pmu_laser_smu_read pmu_laser_smu_run(Vforce,Ilimit,mode,vhigh,vlow,rise,fall,width,period,startPeriod,endPeriod,numPulses,delayBefore,vrange,PMU_ID,ClariusDebug,Duration_s,SampleInterval_s,NumPrePoints,cdStartWidth,cdEndWidth,,NumPoints,,NumPointsTimestamps)
```

25 parameters, in that order (`Imeas` and `Timestamps` are the two empty
`D_ARRAY_T` output-array slots; `cdStartWidth`/`cdEndWidth` only matter for
cool-down modes — leave at `0.0` to use the width-based defaults above).

## Pre-laser baseline reads (`NumPrePoints`)

`NumPoints` is the **total** number of samples in `Imeas`/`Timestamps`.
`NumPrePoints` (0 by default) tells the module how many of those samples to
take **before** firing the laser, as a baseline. Sequence:

1. SMU bias on
2. Sample `NumPrePoints` baseline points (laser still off) — negative timestamps
3. Fire the PMU CH1 TTL waveform
4. Sample the remaining `NumPoints - NumPrePoints` points — positive timestamps
5. Ramp SMU to 0 V

`t = 0` in `Timestamps` is always the instant the PMU fire step begins, so it
lines up directly with the `laser_on_intervals` computed by the Python
waveform preview (no extra time-shifting needed on the Python side).

## Return codes (`pmu_laser_smu_run`)

| Code | Meaning |
|---|---|
| 0 | OK |
| -1 | invalid parameters (SMU collect params OR PMU pulse params) |
| -2 | PMU_ID not in KCON configuration — check KCON |
| -3 | `getinstid()` failed for `PMU_ID` |
| -4 | memory allocation failed |
| -5 | too many Segment ARB segments — reduce `numPulses` |
| -160 | (LPT) "source is not operational" — should no longer occur now that bias/pulse/measure are all in one EX call; if it comes back, check wiring/compliance |
| other | RAW LPT status code from `limiti`/`forcev`/`measi`/`rpm_config`/`pg2_init`/`pulse_ranges`/`pulse_output`/`seg_arb_sequence`/`seg_arb_waveform`/`pulse_exec` — look it up in the Keithley LPT Library reference |

## `pmu_laser_smu_stream` — live/manual-fire chunked read

Used by the tool's **Live / Manual Fire** tab. KXCI/GPIB is one-command-at-
a-time and synchronous, so a single long `EX` call can't be "interrupted"
to fire the laser on a button press. Instead, Python calls this module
repeatedly (once per short "chunk") over one persistent GPIB session:

```text
EX A_pmu_laser_smu_read pmu_laser_smu_stream(Vforce,Ilimit,mode,vhigh,vlow,rise,fall,width,period,startPeriod,endPeriod,numPulses,delayBefore,vrange,PMU_ID,ClariusDebug,SampleInterval_s,FireNow,StopNow,cdStartWidth,cdEndWidth,,NumPoints,,NumPointsTimestamps)
```

25 parameters. Each call:

1. Re-assert SMU bias (`forcev`) — **required every call** (same reason as
   `pmu_laser_smu_run`: the source doesn't stay "operational" across
   separate top-level EX/UL invocations).
2. If `FireNow=1`: build + fire the PMU CH1 TTL waveform (same
   single/train/cool-down shapes), then continue into this chunk's sample
   loop so the transient is caught.
3. Sample `NumPoints` points at `SampleInterval_s`.
4. Return — **without** ramping the SMU to 0 V (so there's no
   force-down/force-up glitch between chunks). Only `StopNow=1` ramps
   down; send that once when the user clicks "Stop streaming".

`Timestamps` are **chunk-local** (`0 .. NumPoints * SampleInterval_s`); the
Python side (`PmuLaserSmuStreamSession`) keeps a running master-timeline
offset across chunks. "Fire Now" latency is bounded by the current chunk's
duration, since Python can't send the fire request until the in-flight
chunk's `EX` call returns.

### Return codes (`pmu_laser_smu_stream`)

Same meanings as `pmu_laser_smu_run` above (0 / -1 / -2 / -3 / -4 / -5 /
raw LPT codes), except `StopNow=1` always returns 0 (or a raw `forcev`
error if even the ramp-down fails) and skips all other validation.

## Build notes

- Do **not** put `#include <Windows.h>` in USRLIB INCLUDES for modules in this library.
- If you still see `proto.h` conflicting types: delete the library’s build/`proto.h`
  artefacts in Clarius/KULT and rebuild clean, after renaming as above.
