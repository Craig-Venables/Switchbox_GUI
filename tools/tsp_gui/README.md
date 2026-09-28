# 2450 TSP Pulse GUI

Standalone Keithley **2450** pulse-testing app using **TSP only** over **USB**, with **Oxxius laser** support for optical tests.

Does **not** depend on the Measurement GUI or 4200 / SCPI paths.

## Run

From the repository root:

```bash
python tools/tsp_gui/main.py
```

Dependencies (also in the main repo `requirements.txt`): see `requirements.txt` in this folder (`pyvisa`, `pyserial`, `numpy`, `matplotlib`).

## Before connecting the 2450

1. Front panel: **MENU → System → Settings → Command Set → TSP**
2. Plug in USB; refresh the VISA list in the GUI
3. Choose Front or Rear terminals, then Connect

Offline UI check: select `SIM::KEITHLEY2450` (no hardware).

## Laser

1. Connect Oxxius on the COM port (default baud 19200 — change if needed)
2. Set power (mW), emission On/Off, single Pulse or Train from the top panel
3. Optical tests require **both** SMU and laser connected

## Tests

- **Pulse tests** tab: electrical TSP scripts (`pulse_read_repeat`, width sweeps, pot/dep, endurance, retention, …)
- **Optical tests** tab: `optical_*` hybrid runs (SMU DC bias + PC-timed laser)

Time parameters on the Pulse tab are entered in **ms** and converted to seconds for the TSP scripts. Optical duration fields are in **seconds** (and on/off in ms) as labeled.

## Data

Results are saved under `tools/tsp_gui/data/` (or a folder you pick) as JSON (+ CSV when series exist).

## Layout

```
tools/tsp_gui/
  main.py
  app/
    connection.py      # USB VISA + Keithley2450System
    laser.py           # OxxiusLaser
    runner.py          # electrical TSP scripts
    optical_runner.py  # optical_* 2450 path
    tests.py / plot.py / gui.py / config.py
```

Instrument drivers are imported from the live repo packages (`Equipment`, `Pulse_Testing`) — not vendored copies.
