# SMU Bias Timed Read

Apply a constant voltage for a set duration and sample current at a fixed interval. Used for **optical+read tests** on the 4200A (laser pulsing from Python while the instrument collects current via the C module).

## Files

| File | Description |
| --- | --- |
| `SMU_BiasTimedRead.c` | USRLIB C module: forcev(V), loop (Sleep + measi), forcev(0). Output array Imeas retrieved via **GP 5**. |
| `SMU_BiasTimedRead_Start.c` | **Sync phase 1**: applies Vforce and Ilimit, then **returns immediately** so the host knows "4200 ready". Load with Collect for laser sync. |
| `SMU_BiasTimedRead_Collect.c` | **Sync phase 2**: sampling loop (assumes bias already on from Start), then forcev(0). Output Imeas via **GP 3**. |
| `run_smu_bias_timed_read.py` | Python runner: single EX (legacy) or **run_bias_timed_read_synced()** (Start → set Event → Collect) for aligned laser/4200 clocks. |

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

4. **GUI**: In Pulse Testing GUI, connect the 4200A, then run **Optical Read (Pulsed Light)** or **Optical Pulse Train + Read**. If **Start** and **Collect** C modules are loaded, the GUI uses **synced** mode: it waits for the 4200 to signal "ready" (bias applied), then sets t0 and starts the laser so clocks are aligned. Otherwise it falls back to a fixed delay (1 s).

## Synced mode (laser + 4200 clock alignment)

To avoid uncertainty about when the 4200 actually starts sampling, use the **two-phase** C modules:

1. **Compile and load** on the 4200 (same USRLIB): both Start and Collect live in the same module `A_SMU_BiasTimedRead_Start`:
   - `SMU_BiasTimedRead_Start.c` and `SMU_BiasTimedRead_Collect.c` → library `A_SMU_BiasTimedRead_Start`
   - Functions: `SMU_BiasTimedRead_Start(Vforce, Ilimit)` and `SMU_BiasTimedRead_Collect(Duration_s, SampleInterval_s, Imeas, NumPoints)`

2. **Flow**: Python enters UL → runs **Start** (bias on) → 4200 returns → Python sets a "ready" event and records t0 → Python starts the laser (and any other equipment) → Python runs **Collect** in the same thread (sample loop, then ramp down). Laser timing is now relative to t0, which is the moment the 4200 signalled ready.

## Parameters (C module)

- **Vforce** – bias voltage (V)
- **Duration_s** – time to hold bias (s)
- **SampleInterval_s** – time between current samples (s); minimum 1 ms in C
- **Ilimit** – current compliance (A)
- **Imeas** – output array (GP 5)
- **NumPoints** – number of samples

Return codes: `0` = OK, `-1` = invalid params, `-5` = forcev failed, `-6` = measi failed, `-7` = limiti failed.
