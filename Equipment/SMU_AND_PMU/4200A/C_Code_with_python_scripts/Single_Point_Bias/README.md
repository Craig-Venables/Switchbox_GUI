# Single Point Bias Monitor

This directory contains the tooling required to run a single-point bias check on a
Keithley 4200A and stream the results back to a PC.

## Files

| File | Description |
| --- | --- |
| `smu_check_connection.c` | UL (User Library) module for the 4200A. Applies a DC bias, samples current, and stores the results in output buffers. |
| `connection_check_runner.py` | Shared helper with `build_check_connection_command` and `execute_single_sample`; imported by both the CLI script and the IV controller wrapper. |
| `run_check_connection_stream.py` | CLI helper that repeatedly launches the UL module, reads the output buffers via `GP`, and prints or JSON-emits the latest sample(s). |
| `run_single_bias_read.py` | Standalone script for taking a one-off measurement (original helper). |

## Workflow

1. Transfer/compile `smu_check_connection.c` on the 4200A (Clarius or KXCI load).
2. From the PC, run `python run_check_connection_stream.py --bias-voltage 0.2`.  
   - By default this loops indefinitely: every cycle executes the UL module once,
     fetches the latest sample via `GP 8/6`, and prints `[01] V=... | I=...`.
   - Press Ctrl+C to stop. Use `--once` to take a single sample and exit.
   - Adjust `--sample-interval`, `--settle-time`, `--ilimit`, etc. as needed.
3. The console output provides a near real-time view while you probe/lower needles.
4. The IV controller wrapper (`IVControllerManager` → `_Keithley4200A_KXCI_Wrapper`) exposes
   a `connection_check_sample()` method that reuses the same helper, so the GUI can
   grab single-sample batches without spawning the CLI script.

## Notes

* The UL module already writes the latest samples into the `Ibuffer`/`Vbuffer`
  parameters. The Python helper simply takes advantage of that by issuing `GP`
  after each EX run.
* If you run the UL module directly from Clarius/KXCI, the `printf("DATA ...")`
  output will appear in the instrument message console as well. Only the session
  that launches the UL code receives those prints.
* For integration into a GUI or logger, import `CheckConnectionStreamer` and feed
  the samples into your own data structures instead of printing.

