# PMU TTL Laser + SMU Continuous Read

Standalone lab tool: drive a laser via **PMU CH1 TTL** while reading sample resistance on a **4200 SMU**, over **KXCI/GPIB** (no LPT).

## Run

```bash
python tools/pmu_laser_smu_read/run_gui.py
```

In the GUI: **Wiring diagram / RPM help…** opens a diagram + checklist. **Test GPIB** checks the bus (only one app may own GPIB).

## Saving data

Default root:

`C:\Users\ppxcv1\OneDrive - The University of Nottingham\Documents\Data_folder\pmu_laser_smu_read`

Set **Sample** in the top bar. Each save goes to:

`<Save root>/<Sample>/<N>-single_YYYYMMDD_HHMMSS.csv`  
(or `…-live_…` for the Live tab)

`N` increments inside that sample folder (`1-…`, `2-…`, …).

Each CSV has two logical tables:

1. **laser_fires** (`#`-commented rows) — fire index + pulse parameters  
2. **data** — `t_s,I_A,V_V,R_Ohm,laser_fire` where `laser_fire` is `0`, or `1`/`2`/… on the nearest sample to each fire (SMU is not reading during the µs pulse)

A matching `_meta.json` is written beside the CSV.

## GPIB / KXCI

- Typical address: `GPIB0::17::INSTR`
- Enable KXCI on the 4200
- **Only one client** at a time (Clarius remote, Pulse Testing, this tool, etc.). If Test GPIB fails, something else is probably holding the bus.

## Wiring

```
PMU  →  RPM  →  laser TTL     (pulsing only, 0 / 5 V)
SMU  →  device pads           (cables straight out of the SMU — no RPM)
PMU CH2 → leave unconnected
```

RPM is **only** on the laser pulse path. The SMU does not go through an RPM for this test.

## Pulse modes

| Mode | Behaviour |
|------|-----------|
| **Single** | One TTL high pulse |
| **Train** | N pulses at fixed period |
| **Cool-down** | Pulse 0 fires at the same **Width** as a single pulse (the on-time already confirmed to reach the laser). From there, both **Width** and the OFF-time between pulses taper together toward the end of the train, over **Cool-down over**, following the chosen decay shape (linear / exponential / quadratic) — progressively smaller, more widely spaced pulses. N and the width/period range are derived automatically from Width/rise/fall/span, so they scale with Width (a small Width barely tapers; a big Width gets a long, gradual taper) instead of a fixed ns-scale floor unrelated to Width. If **Cool-down over** is too short to fit even two full-Width pulses, the taper's starting width shrinks automatically so a meaningful multi-pulse ramp still fits. |

## Two tabs

| Tab | Use for |
|-----|---------|
| **Single-shot Run** | One bounded measurement: pre-laser baseline + fixed-duration post-laser read, single `EX` call, saved as one CSV. |
| **Live / Manual Fire** | Continuous SMU read with a **"Fire Pulse Now"** button — alternate/repeat pulses on demand while watching R(t) update live. See below. |

### Live / Manual Fire tab

KXCI/GPIB is strictly one-command-at-a-time and synchronous, so there is no
way to interrupt an in-flight measurement to fire the laser mid-call.
Instead, this tab reads the SMU in short repeated **chunks** (each its own
`EX` call to `pmu_laser_smu_stream`, over one persistent GPIB session).
Click **Fire Pulse Now** anytime — the laser fires at the very start of the
*next* chunk, so the fire latency is bounded by that chunk's duration
(shown live as "Fire Now latency ≈ up to Xs"). Smaller **Sample dt** /
**Chunk size** values give lower latency at the cost of more GPIB
round-trips; 0.05 s dt / 0.3 s chunks is a reasonable starting point.

The pulse that fires uses whatever is currently set in the **Pulse mode**
/ **PMU CH1 TTL** panels (mirrored in the Live tab itself, and shared with
the Single-shot tab) — the Live tab shows a one-line summary of what will
fire before you press the button, and you can change mode/shape between
fires to alternate pulse types within one streaming session. Each fire
event is shown as a green shaded region + dashed line + a small mode label
(`single` / `train`, `Nx` / `cooldown`, `Nx`) on the live plot, so you can
tell pulse types apart at a glance even after switching mid-session.

**Save live CSV** exports the full session (timestamps, current, voltage,
resistance, plus a `fire_index` column linking each row to the fire event —
if any — it falls under). The exact pulse parameters (mode, Vhigh, width,
rise/fall, period, num_pulses, delay-before, ...) used for **every**
individual fire are written both as `#`-prefixed comment lines at the top
of the CSV (`pandas.read_csv(..., comment='#')` skips them) and in full in
the companion `_meta.json`'s `fire_events` list. The Single-shot tab's
**Save CSV** does the same for its one pulse (`pulse_parameters` in the
CSV header comments / meta JSON).

#### Preset experiment: pulse-width sweep

A dedicated section in the Live tab automates "fire an increasing-width
pulse every N seconds" without manual clicking: set **Start width**,
**Width step**, **Max width** (µs) and **Fire every (s)**, then
**Start width sweep**. It starts streaming if not already running, sets
**Width** to the start value, and fires automatically on a timer —
incrementing Width each time — updating the live plot in real time. It
stops automatically once **Max width** is reached (or if streaming stops/
errors), or can be stopped early with **Stop sweep**. The pulse type
(single/train/cool-down) used is whatever is currently selected — only
**Width** is swept.

## Clarius — one library, two modules the tool calls

Create **`A_pmu_laser_smu_read`** and add `pmu_laser_smu_run.c` **and**
`pmu_laser_smu_stream.c` from:

`Equipment/SMU_AND_PMU/4200A/C_Code_with_python_scripts/pmu_ttl_laser_ch1/`

- `pmu_laser_smu_run` — used by the **Single-shot Run** tab (bias + baseline
  + PMU TTL + timed read + ramp-down, all in one `EX` call).
- `pmu_laser_smu_stream` — used by the **Live / Manual Fire** tab (one
  chunk per `EX` call: re-assert bias, optionally fire, sample a chunk;
  called repeatedly in a loop over one persistent session).

The other three files in that folder (`pmu_ttl_laser_ch1.c`,
`pmu_laser_smu_start.c`, `pmu_laser_smu_collect.c`) can also be added for
reference/standalone debugging, but **the Python tool only issues `EX`
calls to `pmu_laser_smu_run` and `pmu_laser_smu_stream`** — see
"Architecture" below for why.

(Do not use the old `SMU_BiasTimedRead_*` names — they clash with `proto.h`.)

Build and load. You do **not** need a separate BiasTimedRead library.

### Recompile after drive-strength fix (Jul 2026)

`pmu_laser_smu_run` / `pmu_laser_smu_stream` / `pmu_ttl_laser_ch1` now call
`pulse_load(..., 1e6)` and `pulse_ranges(..., irange=0.2)` (PMU 200 mA)
instead of the old RPM-max `0.01` (10 mA). That change is **C-only** — no
Python EX signature change — but Clarius must rebuild:

1. Open library **`A_pmu_laser_smu_read`** in Clarius / KULT
2. Replace/re-add the updated `.c` files from
   `Equipment/.../pmu_ttl_laser_ch1/`
3. **Build** then **Load** the library onto the 4200
4. Re-run a single pulse and measure Vpeak at the laser TTL with the laser
   connected (see Wiring Help in the GUI)

### Recompile after cool-down redesign (Jul 2026)

Cool-down mode used to shrink pulses 1..N-1 toward a fixed `cdStartWidth`
default of ~200 ns regardless of the main **Width** field, so pulse
count/width barely changed no matter what Width was set to. Cool-down now
anchors the taper's *start* to **Width** itself (pulse 0 == Width exactly,
by default) and its *end* to the PMU's true hardware-minimum pulse width
(40 ns) — so pulse count, width, AND spacing all scale directly with
Width, and (if the requested span is too short for even two full-Width
pulses) the starting width auto-shrinks to fit rather than being forced to
one oversized pulse. `cdStartWidth`/`cdEndWidth` are ACTIVE again (no
longer ignored) — Clarius must rebuild:

1. Open library **`A_pmu_laser_smu_read`** in Clarius / KULT
2. Replace/re-add the updated `.c` files from
   `Equipment/.../pmu_ttl_laser_ch1/`
3. **Build** then **Load** the library onto the 4200
4. Re-run a cool-down and confirm pulse width visibly shrinks over the
   train (not just the OFF-time), tracking whatever Width was set to

Full notes: that folder’s `README.md`.

## Architecture: why one EX call, not three

Earlier versions split this into three separate `EX` calls:
`pmu_laser_smu_start` → `pmu_ttl_laser_ch1` → `pmu_laser_smu_collect`. On
real hardware, this failed on the very first `measi()` in Collect with
**LPT status `-160`**: *"Measurement cannot be performed because the
source is not operational."*

Root cause: each top-level `EX`/`UL` invocation from KXCI is its own
execution context. The SMU's `forcev()` from the `Start` call did not
remain "operational" once that `EX` call returned and a separate `EX` call
(the PMU pulse, then Collect) began — the source got torn down between
calls.

**Fix:** `pmu_laser_smu_run.c` inlines SMU-bias-on → build+fire the PMU CH1
TTL Segment ARB waveform → SMU sample loop → SMU ramp-down, all in **one**
continuous C function executed by **one** `EX` command, so the SMU source
is never released mid-sequence.

```text
EX A_pmu_laser_smu_read pmu_laser_smu_run(Vforce,Ilimit,mode,vhigh,vlow,rise,fall,width,period,startPeriod,endPeriod,numPulses,delayBefore,vrange,PMU_ID,ClariusDebug,Duration_s,SampleInterval_s,NumPrePoints,cdStartWidth,cdEndWidth,,NumPoints,,NumPointsTimestamps)
```

## Timing

One GPIB session: `DE` → `UL` → `pmu_laser_smu_run` EX (bias + pre-laser
baseline read + PMU TTL fire + post-laser sample loop + ramp down, all
inline) → `GP` → `DE`.

SMU sample interval ≥ **1 ms**. `NumPoints` is the **total** sample count;
`NumPrePoints` of those are taken **before** the laser fires (baseline —
set via the GUI's **Pre-laser baseline (s)** field, 0 = skip), the rest
after.

**Plot / CSV time axis (Python, not instrument GP Timestamps):**

- **Single-shot:** `t` is built as `i * SampleInterval_s` with **t = 0 at
  laser fire** (pre-laser samples negative). Same reference as
  `laser_on_intervals` from the waveform preview. Instrument `Timestamps`
  from GP are not used for the axis (they are only synthetic `i*dt` in C
  anyway).
- **Live streaming:** `t` is **`time.perf_counter()` session time**. Each
  chunk is end-aligned to when its data arrives; samples inside the chunk
  are spaced by `SampleInterval_s`. Fire markers use the same base. This
  fixes the old live plot where time crawled slowly because the GUI only
  advanced by `n * dt` per chunk while wall time included GPIB wait
  padding and transfer overhead.

## `pmu_laser_smu_stream` (Live / Manual Fire tab)

Same one-call-must-be-self-contained rule applies, but here Python calls it
repeatedly (a "chunk" per call) instead of once, because GPIB has no way to
interrupt an in-flight `EX` call to fire the laser on demand:

```text
EX A_pmu_laser_smu_read pmu_laser_smu_stream(Vforce,Ilimit,mode,vhigh,vlow,rise,fall,width,period,startPeriod,endPeriod,numPulses,delayBefore,vrange,PMU_ID,ClariusDebug,SampleInterval_s,FireNow,StopNow,cdStartWidth,cdEndWidth,,NumPoints,,NumPointsTimestamps)
```

Each call: re-assert bias (`forcev`, required every call) → if `FireNow=1`,
build+fire the PMU CH1 TTL waveform → sample `NumPoints` more points. The
SMU is deliberately **not** ramped to 0 V at the end of a normal chunk (so
there's no periodic force-down/force-up glitch between chunks) — only
`StopNow=1` ramps it down, sent once when the user clicks "Stop streaming".
Python builds the live time axis from `time.perf_counter()` (see Timing
above); instrument chunk-local `Timestamps` are not used for the plot.

## Troubleshooting: EX return codes

The 4200 replies to `EX` with a bare return code (e.g. `-2`), which the tool
parses directly (`runner.py`'s `_send_ex`) — no `RETURN VALUE = ...` prefix
is expected.

`pmu_laser_smu_run` codes:
| Code | Meaning |
|---|---|
| 0 | OK |
| -1 | invalid parameters (SMU collect params OR PMU pulse params) |
| -2 | PMU_ID not in KCON configuration — **check KCON**, or set the GUI's **PMU_ID (KCON name)** field to match |
| -3 | `getinstid()` failed for `PMU_ID` |
| -4 | memory allocation failed |
| -5 | too many Segment ARB segments — reduce `num_pulses` |
| -160 | (LPT) "source is not operational" — this was the split-EX-call bug; should no longer occur now that everything is one EX call. If it recurs, it's a real wiring/compliance issue. |
| other | RAW LPT status code from `limiti`/`forcev`/`measi`/`rpm_config`/`pg2_init`/`pulse_ranges`/`pulse_output`/`seg_arb_sequence`/`seg_arb_waveform`/`pulse_exec` — look it up in the Keithley LPT Library reference |

### History (confirmed on real hardware, 2026-07-22)

1. `PMU_ID` was being quoted (`"PMU1"`) in the EX command, unlike the repo's
   other working PMU callers (`ACraig10_PMU_Waveform_SegArb` via
   `kxci_scripts.py`), which pass it unquoted. Fixed → PMU pulse started
   firing correctly (`pmu_ttl_laser_ch1` returned `0`).
2. With PMU firing, SMU `Collect` then failed with LPT `-6`→ later
   confirmed as raw LPT `-160` ("source not operational") once the C
   modules were changed to surface real status codes instead of fixed
   sentinels. Root cause: SMU state doesn't persist across separate
   top-level `EX` calls. Fixed by merging Start+PMU+Collect into the single
   `pmu_laser_smu_run` module described above.
