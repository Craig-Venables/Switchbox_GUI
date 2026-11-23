# 07 — PMU plan

PMU-specific rules for V2, on top of [00_safety.md](00_safety.md). Covers the
existing PMU1 setup with two RPMs in dual-channel mode.

## How the existing PMU modules work

From [`C_Code_with_python_scripts/README.md`](../Equipment/SMU_AND_PMU/4200A/C_Code_with_python_scripts/README.md)
and the module sources:

- Two layers of C: a module (for example `readtrain_dual_channel.c`) builds
  voltage/time arrays; a shared driver (for example
  `retention_pulse_ilimit_dual_channel.c`) configures channels and runs them.
- The driver switches both RPMs to the pulse path with
  `rpm_config(InstId, ch, KI_RPM_PATHWAY, KI_RPM_PULSE)`, sets ranges and
  limits, then runs `seg_arb_sequence` on the force channel (CH1) and the
  measure channel (CH2).
- Seg-arb rule: segment *i* ramps from `v[i]` to `v[i+1]` over `t[i]`. A flat
  top needs `v[i] == v[i+1]`. Every segment must be at least 20 ns.
- Reads are averaged over 40% to 90% of each read pulse
  (`PMU_READ_PROBE_RATIO_LO/HI` in `kxci_scripts.py`), using the measured
  probe voltage.
- The firmware caps reported resistance at `1e4 / IRange`
  (`PMU_MAX_RESISTANCE_PER_IRANGE`).

### Output slots used by existing modules

| Module | Library | setV | setI | PulseTimes | out1 |
|---|---|---|---|---|---|
| `readtrain_dual_channel` | `A_Read_Train` | 20 | 22 | 31 | n/a |
| `pmu_retention_dual_channel` | `A_Retention` | 20 | 22 | 30 | 31 |
| `pmu_potentiation_depression` | `A_Poteniation_Depression` | 20 | 22 | 31 | 25 |
| `pmu_pulse_read_interleaved` | `A_pulse_read_grouped_multi` | 20 | 22 | 31 | 25 |

Each `V2_*` copy must declare its slot map in its MCP module registry entry
([04_mcp_server.md](04_mcp_server.md)), so the AI never guesses slot numbers.

## PMU envelope (summary)

From [00_safety.md](00_safety.md):

- \|V\| ≤ 1 V on every level, including the reset and set levels that the
  existing modules default to 4 V.
- I-range in {10 µA, 100 µA, 1 mA}; current limit ≤ 1 mA.
- Every segment ≥ 1 µs.
- `max_points` ≤ 30 000.
- Estimated segments ≤ 350 per burst (practical ceiling
  `_PMU_OBSERVED_SINGLE_BURST_SEGMENTS`; hardware max 2048).
- Estimated burst duration ≤ 10 s.

## Burst estimates in the gate

The gate estimates segments and duration **before** sending:

- Retention: `estimate_retention_seg_arb_segments(initial, program, retention)`.
- Endurance: `estimate_endurance_seg_arb_segments(cycles)`.
- Interleaved: `estimate_interleaved_timeline(cfg)` for duration.
- New `V2_*` modules: the registry entry must provide its own estimate
  function, with a unit test comparing it to the C module's actual segment
  count from the simulator.

Negative return codes are explained with `format_pmu_ex_error` and
`_PMU_EX_ERROR_HINTS` (for example -122 segment too short, -211 too many
segments, -204 output arrays too small).

## Prerequisite: PMU simulator

`simulation_4200.py` has no PMU support today. Before any PMU hardware use:

1. Add a PMU `EX` handler to `Simulation4200` that recognises registered
   `V2_*` PMU module names and parses their arguments.
2. Model a **pure resistor** first: for each read, I = V_meas / R with a
   small configurable noise, and V_meas equal to the requested read voltage
   minus a small configurable source-resistance drop.
3. Produce the same `GP` slots, array lengths and `PulseTimes` as the C module
   should.
4. Apply the firmware cap and range quantisation so range mistakes show up in
   simulation.
5. Support the existing `Simulation4200Faults` options (timeout, truncated
   `GP`, error code, disconnect).
6. Add tests under `tests/` in the style of `tests/test_simulation_4200_pulse.py`.

A memristor model can come later; the resistor model is what validation needs.

## Porting order

Each step is a `V2_*` copy of an existing module. The originals are never
touched.

| Step | New library | Based on | Why this order |
|---|---|---|---|
| 1 | `V2_Readtrain` | `Readtrain/readtrain_dual_channel.c` + `read_train_ilimit.c` | Reads only; simplest timing |
| 2 | `V2_Retention` | `retention/pmu_retention_dual_channel.c` + `retention_pulse_ilimit_dual_channel.c` | Adds program pulses (kept at ≤ 1 V on the resistor) |
| 3 | `V2_PulseReadInterleaved` | `pmu_pulse_read_interleaved/` | Cycles and grouping; tests segment estimates |

For each step:

1. Copy, rename module functions to unique `v2_*` names.
2. Insert the safety-constant block ([05_build_pipeline.md](05_build_pipeline.md)).
3. Tighten USRLIB header min/max columns to the envelope.
4. Add the registry entry (argument limits, slot map, segment estimate).
5. Simulator pass, then build, interlock, first run with human approval,
   then `validate_resistor`.

## Known PMU pitfalls to check for

- Using 1 V on the 100 µA range with 10 kOhm: exactly full scale, saturates.
  Use 0.3 to 0.5 V on 100 µA, or 1 V on 1 mA.
- Output arrays sized smaller than the probe count (error -204/-205).
- Too many segments for one burst (error -211, or failure without a return
  code). Split into several bursts instead of raising limits.
- Reading `PulseTimes` from the wrong slot (30 versus 31 depends on module).
- Forgetting `DE` before `GP` queries (see the KXCI notes in the module
  README).
- Module names that clash with existing ones in Clarius `proto.h`.
