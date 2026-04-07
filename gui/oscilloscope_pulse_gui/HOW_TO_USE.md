# How To Use: Oscilloscope Pulse GUI

## 1) Connections Tab

1. Select your system.
2. Set SMU address and scope address.
3. Click `Connect SMU`.
4. Set up scope manually (timebase, V/div, trigger, channel).

## 2) Measurements Tab

1. Set pulse parameters:
   - Pulse Voltage
   - Pulse Duration
   - Bias Voltage
   - Pre/Post Bias Time (single shared value)
   - Current Compliance
2. Set `R_shunt` correctly (measured value).
3. Click `Send Pulse`.
4. Verify pulse on the scope.
5. Click `Read Raw Data`.
6. Click `Save Data` (or use auto-save).

## 3) What Gets Saved

- `Time(s)`
- `V_shunt_raw(V)`
- `Current(A)`
- `Resistance(Ohm)`

## Notes

- The workflow is intentionally simple (no pulse-alignment flow).
- Near-zero current points may produce `NaN` resistance values.
