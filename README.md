Install the following dependancies 

pip install opencv-python
pip install matplotlib

https://nodejs.org/en
https://liquidinstruments.com/software/utilities/

# Create a custom sweep 

To create custom sweeps use Custom_sweeps.jason build the sweeps you want and then within the code add it too the ddown list within the code

The following options are along with the defaults: 
"start_v": 0,
"stop_v": 0.1,
"sweeps": 3,
"step_v": 0.01,
"step_delay":0.05
"Sweep_type": "FS" 
"pause" : 0  #adds pause at the end of the sweep for the indicated time 
(FS = Full sweep (default),Ps=PositiveHalf-sweep +ve, Ns=NegativeHalf-sweep)

"LED": "OFF"      (colour of the led,options - blue,red,green,white,OFF)
"LED_TIME": "10" Time led is on before measurements taking place
"LED_SWEEPS": "2" (Number of sweep the led is on for)




# Common Problems

## Manual Endurance and Retention entries

You can define endurance and retention steps inside `Json_Files/Custom_Sweeps.json` using the following formats. These integrate with the GUI and can be combined with other steps.

Examples (already added):

```
"Manual_Endurance_Short": {
  "code_name": "end_short",
  "sweeps": {
    "1": {"mode": "Endurance", "set_v": 1.5, "reset_v": -1.5, "pulse_ms": 10, "cycles": 50, "read_v": 0.2, "LED_ON": 0}
  }
},
"Manual_Retention_Quick": {
  "code_name": "ret_quick",
  "sweeps": {
    "1": {"mode": "Retention", "set_v": 1.5, "set_ms": 10, "read_v": 0.2, "times_s": [1,3,10,30,100,300], "LED_ON": 0}
  }
}
```

- mode: `Endurance` or `Retention`
- Endurance keys: `set_v`, `reset_v`, `pulse_ms`, `cycles`, `read_v`, optional `LED_ON`, `power`
- Retention keys: `set_v`, `set_ms`, `read_v`, `times_s` (array), optional `LED_ON`, `power`

### What are Endurance and Retention tests?

- Endurance: Applies repeated SET/RESET voltage pulses and reads the device at a low read voltage between pulses. The ON/OFF current ratio is tracked over cycles to evaluate switching stability and fatigue. Key parameters:
  - `set_v` and `reset_v`: pulse amplitudes (V)
  - `pulse_ms`: pulse width in milliseconds
  - `cycles`: number of SET/RESET repetitions
  - `read_v`: read voltage used to sample the current after each pulse

- Retention: After driving the device into a known state (SET), the current is measured at a fixed read voltage over time to evaluate state stability and drift. Key parameters:
  - `set_v`, `set_ms`: SET conditions (voltage and duration)
  - `read_v`: read voltage for non‑destructive sampling
  - `times_s`: an array of times (in seconds) at which to take measurements

Why multiple times for retention (comma‑separated)?
- Retention behavior is time‑dependent. Measuring at multiple time points builds a decay curve (often analyzed on a log time scale) and allows fitting a retention exponent. Comma‑separated values let you define custom, non‑uniform sampling (e.g., `1,3,10,30,100,300`) to quickly cover short and long times without taking excessive measurements.

### Running from the GUI

- Manual controls: Use the “Manual Endurance / Retention” section in the left panel to set parameters and run tests interactively. A local LED toggle is provided for opto‑tests.
- Automated runs: Add endurance/retention entries (as above) to `Json_Files/Custom_Sweeps.json`. They can be mixed with IV sweeps in the same plan. Results are saved with the same file structure and naming conventions as IV data.
1. Mapping not correct?\
1.i. Check the scaling factor or use show box's python code\
1.ii. check x_max and x_min are the correct way around this causes issues if not!
2. 



