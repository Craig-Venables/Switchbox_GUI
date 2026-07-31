# PMU TTL Laser + SMU Continuous Read

Standalone lab tool: drive a laser via **PMU CH1 TTL** while reading sample resistance on a **4200 SMU**, over **KXCI/GPIB** (no LPT).

## Run

```bash
python tools/pmu_laser_smu_read/run_gui.py
```

In the GUI: **Wiring diagram / RPM help…** opens a diagram + checklist. **Test GPIB** checks the bus (only one app may own GPIB).

## Saving data

Default root — the **same shared `Data_folder`** used by the main Sample GUI /
Measurement GUI, resolved via `resolve_default_save_root()`:

`C:\Users\ppxcv1\OneDrive - The University of Nottingham\Documents\Data_folder`

**Sample / Section / Device #** in the top bar identify exactly which device
you're testing, using the same convention as the Cross_bar sample type in the
main Sample GUI:

- **Sample** — an editable combobox. Type a brand-new name, or pick one from
  the dropdown to continue measuring on a sample already created anywhere
  (e.g. via the main Sample GUI) — the list is every folder under the shared
  `Data_folder`, most-recently-modified first. Click **↻** to rescan if a
  sample was created elsewhere while this tool is open.
- **Section** — a fixed dropdown, `A`–`L` (matches `Cross_bar`'s sections in
  `gui/sample_gui/config.py`).
- **Device #** — a fixed dropdown, `1`–`10` (matches `Cross_bar`'s device
  list).

There's no crossbar map or Device Manager dialog here — just enough to tag
and find your data; the last-used Sample/Section/Device # is remembered in
`pmu_laser_smu_config.json` between sessions.

Each save goes to:

`<Save root>/<Sample>/<Section>/<Device #>/PMU_Laser_SMU_Testing/<N>-single_YYYYMMDD_HHMMSS.csv`  
(or `…-live_…` / `…-routine_…` for the other tabs)

This nests the tool's files inside the same per-device folder tree the main
Sample/Measurement GUIs use (`<sample>/<section>/<device>/...`), in their own
`PMU_Laser_SMU_Testing` subfolder so they sit alongside — without mixing into
— other measurement types recorded for that device. `N` increments inside
that leaf folder (`1-…`, `2-…`, …). Existing data saved by older versions of
this tool under `Data_folder/pmu_laser_smu_read/<sample>/...` is left where
it is; only new saves use the nested layout above.

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

## Three tabs

Tab order (left to right): **Live / Manual Fire** opens first (the tab you'll
use most for day-to-day testing), then **Automated Routine**, then
**Single-shot Run**.

| Tab | Use for |
|-----|---------|
| **Live / Manual Fire** | Continuous SMU read with a **"Fire Pulse Now"** button — alternate/repeat pulses on demand while watching R(t) update live. See below. |
| **Automated Routine** | Unattended width × current-% sweep: fire a low-current pulse at increasing widths, then step diode current % up (serial) and repeat — see below. |
| **Single-shot Run** | One bounded measurement: pre-laser baseline + fixed-duration post-laser read, single `EX` call, saved as one CSV. |

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

**Known artifact — small periodic "sawtooth"/"triangle" ripple in I(t)/R(t):**
because each chunk is its own `EX` call, `pmu_laser_smu_stream.c` has to
re-assert the SMU bias (`limiti`/`setmode`/`forcev`) at the *start of every
chunk* — the LPT source doesn't stay "operational" across separate
EX/UL invocations (see its module help). On some samples (seen on GST
phase-change films) that re-assert triggers a small relaxation transient
that decays over the rest of the chunk, then resets at the next chunk
boundary — i.e. a repeating ripple synced exactly to chunk size, riding on
top of the real underlying drift. It's most visible with small chunks
(e.g. the 0.05 s dt / 0.3 s chunk default → 6-point sawtooth). If you see
this: the genuine trend is the slow envelope, not the ripple. Using a
larger **Chunk size** (fewer, more widely-spaced resets — trading off
slower Fire Now response) reduces how often it happens and, since the
relaxation gets more time to settle within each longer chunk, usually
reduces its size relative to the real signal too.

The pulse that fires uses whatever is currently set in the **Pulse mode**
/ **PMU CH1 TTL** panels (mirrored in the Live tab itself, and shared with
the Single-shot tab) — the Live tab shows a one-line summary of what will
fire before you press the button, and you can change mode/shape between
fires to alternate pulse types within one streaming session. Each fire
event is shown as a green shaded region + dashed line + a small mode label
(`single` / `train`, `Nx` / `cooldown`, `Nx`) on the live plot, so you can
tell pulse types apart at a glance even after switching mid-session.

Click **⏸ Pause** at any time to freeze streaming in place (no more SMU
reads or bias re-asserts — the bias stays exactly as last set) so you can
safely check the sample; click **▶ Resume** to continue exactly where you
left off. See the Automated Routine tab section below for how this
interacts with routine/sweep timers.

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

### Automated Routine tab

Automates the general threshold-finding procedure: **fire a low-current
pulse at a series of increasing widths, then raise the laser diode current
(%) and repeat**, from low upward, until you see a response on the live
R(t) plot. It reuses the exact same PMU/SMU streaming session as the Live
tab (only one GPIB session can exist at a time — streaming starts
automatically if it isn't already running), and adds real serial control
of the Oxxius laser (`Equipment/Laser_Controller/oxxius.py`) between
blocks.

**Laser (serial)** — Port/Baud + Connect/Disconnect (same driver used
elsewhere in the repo, e.g. `gui/pulse_testing_gui`). On **Connect** the
tool arms TTL-ready mode: power ceiling raised to the unit's rated max
(`PM 330`, see below) → analog modulation OFF (`AM 0`) →
digital modulation ON (`TTL 1`) → emission ON (`DL 1`). Emission must be
ON for the TTL input to gate light. Manual controls: **Emission On/Off**,
**Set current (%)** (sets `APC 0` + `CM <%>` without changing AM/TTL),
**Align ON / Align OFF → TTL** (CW beam for optical alignment: `TTL 0`,
current at the Align % field — default 5 % — emission ON; Align OFF
re-arms `TTL 1` with emission ON), and **Restore manual control**.
Default serial port is **COM8**. Disconnect / routine stop restores the usual
manual state: digital mod OFF (`TTL 0`), analog ON, constant power (`APC 1`),
emission ON (`close(restore_to_manual_control=True)`).

**Power ceiling (`PM`) vs. current (%) (`CM`):** `PM <mW>` is an absolute
power *ceiling* enforced by the firmware in **every** mode, including the
ACC/current-% mode this tool uses for routines. If `PM` is left at a lower
leftover value (e.g. the 100 mW used for manual front-panel/analog-wheel
control), `CM` (current %) gets silently clamped once the resulting power
would exceed that ceiling — so "100% current" would **not** mean "100% of
the laser's rated output". To fix this, `prepare_for_ttl_modulation()`
(called on Connect, on Align OFF, and when arming for the routine) now
also sets `PM` to the unit's true rated max power (**330 mW** by default —
see `TTL_FULL_POWER_MW` in `oxxius.py`; change it if your laser isn't a
330 mW model) before arming ACC/TTL, so the full `CM` range maps to
genuine, uncapped output.

Note: this LBX firmware returns `????` for unknown commands. Correct
tokens are `TTL` (not `DM`) for digital modulation and `CM` (not `I`)
for current percent.

**Routine** section:

- **Pulse widths** — either type a comma-separated list directly (e.g.
  `100ns, 1000ns, 10000ns`), or use **Start width / step multiplier /
  number of steps** + **Generate** to fill it in automatically (multiplier
  defaults to `10` for true decade steps — `100 ns -> 1000 ns -> 10000 ns
  -> ...` — but is customizable, e.g. `2` for octave steps).
- **Laser current (%)** — **Start / step / max** define an additive ramp
  of diode current percent (e.g. 10, 20, …, 100 %); a live preview line
  shows the exact levels that will be used.
- **Timing** — **Settle after current change (s)** (dwell after a serial
  current command + emission ON before the width sweep starts) and
  **Fire every (s)** (spacing between pulses within a width sweep).
- **Preview plan** shows the full step-by-step plan (every current change
  and fire, in order) and the estimated total duration before you commit.
- **Visualize routine** opens a schematic pulse-train chart of the current
  plan (before you even start it): each planned fire is drawn as a bar
  whose **height is the diode current %** and whose **width is the pulse
  width on a log scale** (all pulses stay visible whether they're ns or
  ms — it's a schematic, not a true timing diagram). Handy for a quick
  sanity check that the current/width ramp looks right.
- **Start routine** / **Stop routine** run/cancel the sweep; a status line
  shows live progress (e.g. `Step 4/20: Fire 1000 ns @ 30 % — next in
  2.0s`). Stopping is always manual — watch the plot and click **Stop
  routine** as soon as you see a response; there is no automatic
  stop-on-response detection yet. A **Stop streaming** button on this tab
  stays enabled once streaming starts (including after the routine
  finishes on its own), so you can always stop acquisition and save —
  even if you never click **Stop routine**.
- **⏸ Pause / ▶ Resume** freezes everything in place mid-run so you can
  check the sample (e.g. under a microscope) without losing the run:
  no more SMU reads, no bias re-asserts, and no automatic fires happen
  while paused — the SMU bias simply stays exactly as it last was.
  The routine and pulse-width sweep timers are frozen too (their step
  counters are preserved). Click **▶ Resume** to continue; the routine/
  sweep restarts its full **settle**/**fire-every**/**interval** wait
  from the moment you resume (rather than firing immediately), so the
  sample gets a fresh settle period after you've been poking at it. The
  same button is available on the **Live / Manual Fire** tab and pauses
  manual streaming too (enabled any time streaming is running).

The pulse type (single/train/cool-down) and PMU shape (Vhigh/rise/fall/
delay) are shared with the Live tab; only **Width** is routine-controlled
(shown read-only as "Current width"). Each fire event records the laser
current % that was active at the time (CSV / meta field still named
`laser_power_mw` for compatibility — value is **current percent**, not
mW), alongside the usual pulse parameters. **Save routine CSV** exports
the session the same way as **Save live CSV**
(`run_kind: "routine"` instead of `"live_manual_fire"`), and additionally
renders and saves a `<stem>_pulses.png` alongside the CSV/meta —
the same schematic pulse-train chart as **Visualize routine**, but built
from the pulses actually fired during the run (bar height = current %
that was armed, bar width = log-scaled actual pulse width). The image
path is also recorded in the `_meta.json` under `pulse_image`.

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
EX A_pmu_laser_smu_read pmu_laser_smu_run(Vforce,Ilimit,mode,vhigh,vlow,rise,fall,width,period,startPeriod,endPeriod,numPulses,delayBefore,vrange,PMU_ID,ClariusDebug,Duration_s,SampleInterval_s,NumPrePoints,cdStartWidth,cdEndWidth,Irange,,NumPoints,,NumPointsTimestamps)
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
EX A_pmu_laser_smu_read pmu_laser_smu_stream(Vforce,Ilimit,mode,vhigh,vlow,rise,fall,width,period,startPeriod,endPeriod,numPulses,delayBefore,vrange,PMU_ID,ClariusDebug,SampleInterval_s,FireNow,StopNow,cdStartWidth,cdEndWidth,Irange,,NumPoints,,NumPointsTimestamps)
```

Each call: re-assert bias (`forcev`, required every call) → if `FireNow=1`,
build+fire the PMU CH1 TTL waveform → sample `NumPoints` more points. The
SMU is deliberately **not** ramped to 0 V at the end of a normal chunk (so
there's no periodic force-down/force-up glitch between chunks) — only
`StopNow=1` ramps it down, sent once when the user clicks "Stop streaming".
Python builds the live time axis from `time.perf_counter()` (see Timing
above); instrument chunk-local `Timestamps` are not used for the plot.

### Current range (`Irange`)

Both `pmu_laser_smu_run` and `pmu_laser_smu_stream` now take an `Irange`
parameter (in addition to `Ilimit`, the compliance limit) — this is SMU1's
current **measurement** range, set via `rangei(SMU1, Irange)` right after
`limiti(SMU1, Ilimit)` (re-asserted every chunk in the stream module, same
as the bias). It's exposed in the GUI as **Current range (A)** next to
**Ilimit (A)** on every tab:

- **`0` or blank = Autorange** (the historical/default behaviour — the
  instrument picks a range per reading).
- **A fixed value (e.g. `1e-6`) = fixed range** — lower-noise, faster,
  more consistent readings once you have a rough idea what current to
  expect, at the cost of clipping if the real current exceeds that range.
  Invalid/unsupported values are silently snapped to the nearest hardware
  range by the LPT driver.

**Note:** this adds a new argument to both `.c` modules — if you already
have older-signature versions of `pmu_laser_smu_run`/`pmu_laser_smu_stream`
compiled/loaded in Clarius, you'll need to recompile and reload the
updated `.c` files from this repo (`Equipment/SMU_AND_PMU/4200A/
C_Code_with_python_scripts/pmu_ttl_laser_ch1/`) before using this field —
otherwise the `EX` call's argument count won't match and it will fail.

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
