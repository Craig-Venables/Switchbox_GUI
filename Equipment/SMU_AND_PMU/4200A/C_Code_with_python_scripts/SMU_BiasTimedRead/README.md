# SMU Bias Timed Read

Apply a constant voltage for a set duration and sample current at a fixed interval. Used for **optical+read tests** on the 4200A (laser pulsing from Python while the instrument collects current via the C module).

## Files

| File | Description |
| --- | --- |
| `SMU_BiasTimedRead.c` | USRLIB C module: forcev(V), loop (Sleep + measi), forcev(0). Output array Imeas retrieved via **GP 5**. |
| `run_smu_bias_timed_read.py` | Python runner: KXCI connect → UL → EX → wait → GP 5 → DE. Returns timestamps, voltages, currents, resistances. |

## Prerequisites

- **4200A**: C module compiled and loaded into USRLIB (Clarius/4200 on the other PC).
- **PC**: Python 3 with `pyvisa` (and NI-VISA or similar for GPIB). Same repo so the runner is next to the C source.

## Testing (assume C is already compiled on the 4200 PC)

1. **Just run** – default is a short test (2 s bias, 20 points, ~4 s total). Double‑click or:
   ```bash
   python run_smu_bias_timed_read.py
   ```
   Use `--gpib-address GPIB0::17::INSTR` if your address is different.

2. **Dry run (no instrument)** – only print the EX command:
   ```bash
   python run_smu_bias_timed_read.py --dry-run
   ```

3. **Longer run** – e.g. 10 s, 0.02 s sample interval:
   ```bash
   python run_smu_bias_timed_read.py --duration 10 --sample-interval 0.02
   ```

4. **GUI**: In Pulse Testing GUI, connect the 4200A, then run **Optical Read (Pulsed Light)** or **Optical Pulse Train + Read**. The adapter calls this runner and coordinates the laser after a 1 s delay.

## Parameters (C module)

- **Vforce** – bias voltage (V)
- **Duration_s** – time to hold bias (s)
- **SampleInterval_s** – time between current samples (s); minimum 1 ms in C
- **Ilimit** – current compliance (A)
- **Imeas** – output array (GP 5)
- **NumPoints** – number of samples

Return codes: `0` = OK, `-1` = invalid params, `-5` = forcev failed, `-6` = measi failed, `-7` = limiti failed.
