# pmu_endurance_interleaved

Fast PMU endurance: **Initial Read → (SET → Read → RESET → Read) × N** in one seg-arb burst.

## Deploy to 4200A (add to existing library)

Your working library **already** contains:

- `pmu_pulse_read_interleaved.c`
- `retention_pulse_ilimit_dual_channel.c`

**Only add one new file:**

- `pmu_endurance_interleaved.c`

Do **not** add another copy of `retention_pulse_ilimit_dual_channel.c` — that causes linker errors (`collect2.exe: id returned 1 exit status`) from duplicate symbols.

`pmu_endurance_interleaved.c` uses **static** local helpers (VFret, ret_find_value, etc.) so it does not conflict with `pmu_pulse_read_interleaved.c` in the same library. It still links to `retention_pulse_ilimit_dual_channel.c` for `ret_getRate` and waveform execution.

### Build steps

1. Clarius → User Library → open `A_pulse_read_grouped_multi` (or your existing pulse library).
2. Add **only** `pmu_endurance_interleaved.c` from this folder.
3. Ensure `pmu_pulse_read_interleaved.c` and `retention_pulse_ilimit_dual_channel.c` remain in the project.
4. Build / load library.

If build still fails, check the Clarius build log for `multiple definition of` — that means a file was added twice.

## Parameter mapping (EX command)

| Python / GUI | C parameter | Role |
|--------------|-------------|------|
| `set_voltage` | `PulseV` | SET pulse amplitude |
| `reset_voltage` | `setStopV` | RESET pulse amplitude |
| `num_cycles` | `NumPulses` | Endurance cycles per EX |
| `read_voltage` | `measV` | Read level |
| `pulse_width` | `PulseWidth` | SET/RESET flat top |
| GP 20 / 22 / 31 | `setV` / `setI` / `PulseTimes` | Same as pulse-read module |

**Probes per burst:** `1 + 2 × NumPulses`

## Smoke test (after deploy)

```powershell
python Equipment/SMU_AND_PMU/4200A/scripts/pmu_endurance_smoke_test.py --cycles 2 --dry-run
python Equipment/SMU_AND_PMU/4200A/scripts/pmu_endurance_smoke_test.py --cycles 2
```
