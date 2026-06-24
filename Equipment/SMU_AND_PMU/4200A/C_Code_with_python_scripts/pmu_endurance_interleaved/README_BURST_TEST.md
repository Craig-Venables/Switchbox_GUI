# pmu_endurance_burst_test (experimental)

Instrument-side burst batching proof-of-concept. **Does not replace** `pmu_endurance_interleaved`.

## Library: `A_pulse_read_grouped_multi`

Same User Library as your existing PMU pulse modules:

| Module already in library | Role |
|---------------------------|------|
| `pmu_pulse_read_interleaved` | Read → Write → Read |
| `pmu_endurance_interleaved` | Endurance (single-burst, unchanged) |
| **`pmu_endurance_burst_test`** | **Add this** — experimental 100+ cycle batching |

**Add to the library (do not replace existing `.c` files):**

1. `pmu_burst_common.h`
2. `pmu_endurance_burst_test.c`

Keep `pmu_pulse_read_interleaved.c`, `pmu_endurance_interleaved.c`, and **one** `retention_pulse_ilimit_dual_channel.c`.

## EX command

```text
EX A_pulse_read_grouped_multi pmu_endurance_burst_test(<42 parameters>)
```

Clarius requires the full `ARGUMENTS:` table in the `.c` file USRLIB header (same 42 parms as `pmu_endurance_interleaved`). `NumPulses` = **total** cycles (1–1000).

**Segment batching:** `retention_pulse_ilimit_dual_channel` accepts ~350 seg-arb segments per call (not the 2048 hardware max). For 100 cycles (~1806 segments), `pmu_endurance_burst_test` runs **6 internal sub-bursts** (e.g. 19+19+19+19+19+5 cycles) inside **one EX**. There is a short PMU re-arm gap between sub-bursts (waveform reload), not a Python sleep. Sub-burst 2+ keeps RPM/PMU armed to shorten that gap. Redeploy `pmu_burst_common.h` and `retention_pulse_ilimit_dual_channel.c` when updating batching behavior.

## Clarius build error "parsing parameter …"

If you see a garbled parameter name, the USRLIB `ARGUMENTS:` block was incomplete. Use the repo version of `pmu_endurance_burst_test.c` with all 42 lines — not placeholder text like "(same signature as …)".

## GUI

Pulse Testing GUI → **Endurance Burst Test** (4200 PMU profile only).

## Smoke test (CLI)

```powershell
python Equipment/SMU_AND_PMU/4200A/scripts/pmu_endurance_burst_test.py --cycles 100 --dry-run
python Equipment/SMU_AND_PMU/4200A/scripts/pmu_endurance_burst_test.py --cycles 100
```

## Behaviour

- `NumPulses` = **total** SET/RESET cycles (1–1000).
- **Continuous waveform:** up to **~113 cycles** fit in one seg-arb burst (2048 segment hardware limit). A 100-cycle test is **one uninterrupted pulse train** — same as classic endurance, not 5×20 with idle gaps.
- Above ~113 cycles: C splits internally; burst 2+ skips Initial Read and continues SET/RESET at 0 V (minimal gap, no full PMU re-init between chunks).
- Python: one EX, scaled wait, one GP readback.

If you still see pauses between ~19-cycle chunks, the instrument library is still on the old **350-segment** budget — redeploy `pmu_burst_common.h` and rebuild.

## After validation

If bench tests pass, merge this logic into `pmu_endurance_interleaved` and retire this experimental module.
