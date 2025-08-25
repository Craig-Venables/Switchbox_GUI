from pymeasure.instruments.keithley import Keithley2400
import time
from typing import Optional, Dict, Any, List, Tuple

"""https://pymeasure.readthedocs.io/en/latest/api/instruments/keithley/keithley2400.html#pymeasure.instruments.keithley.Keithley2400.compliance_current"""


class Keithley2400Controller:
    def __init__(self, gpib_address='GPIB0::24::INSTR', timeout=5):
        """Initialize connection to Keithley 2400 via PyMeasure."""
        try:
            self.device = Keithley2400(gpib_address)
            self.device.adapter.connection.timeout = timeout * 1000  # Convert to milliseconds
            self.device.reset()  # Reset the instrument
            print(f"Connected to: {self.get_idn()}")

            print(self.get_idn())
        except Exception as e:
            print("Error initializing Keithley 2400:", e)
            self.device = None

    def get_idn(self):
        """Query and return the device identity string."""
        return self.device.id if self.device else "No Device Connected"

    def check_errors(self):
        """Check instrument error status."""
        return self.device.ask('SYST:ERR?') if self.device else "No Device Connected"

    def set_voltage(self, voltage, Icc=0.1):
        """Set output voltage and enable source mode."""
        if self.device:

            self.device.apply_voltage(voltage_range=20, compliance_current=Icc)  # Set compliance current
            self.device.source_voltage = voltage

    def set_current(self, current, Vcc=10):
        """Set output current and enable source mode."""
        if self.device:
            self.device.apply_current(current_range=10e-3, compliance_voltage=Vcc)  # Set compliance voltage
            self.device.source_current = current

    def measure_voltage(self):
        """Measure and return voltage."""
        return self.device.voltage if self.device else None

    def measure_current(self):
        """Measure and return current."""
        return self.device.current if self.device else None

    def enable_output(self, enable=True):
        """Enable or disable output."""
        if self.device:
            self.device.enable_source() if enable else self.device.disable_source()

    def beep(self, frequency=1000, duration=0.5):
        """Make the instrument beep."""
        if self.device:
            self.device.write(f'SYST:BEEP {frequency}, {duration}')

    def voltage_ramp(self, target_voltage, steps=30, pause=0.02):
        """Ramp voltage gradually to avoid sudden spikes."""
        if not self.device:
            print("No Device Connected.")
            return
        current_voltage = self.device.source_voltage
        voltage_step = (target_voltage - current_voltage) / steps

        for i in range(steps):
            self.device.source_voltage = current_voltage + (i + 1) * voltage_step
            time.sleep(pause)

    def shutdown(self):
        """Ramp current to 0 mA and disable output."""
        if self.device:
            self.device.source_current = 0
            self.device.disable_source()

    def close(self):
        """Close connection to the instrument."""
        if self.device:
            self.device.shutdown()
            print("Connection closed.")

    
    def run_tsp_sweep(self,
                    start_v: float = 0.0,
                    stop_v: float = 2.5,
                    step_v: float = 0.05,
                    icc_start: float = 1e-4,
                    icc_factor: float = 10.0,
                    icc_max: Optional[float] = None,
                    delay_s: float = 0.005,
                    burn_abort_A: Optional[float] = None
                    ) -> Dict[str, Any]:
        """
        Run an embedded TSP voltage sweep on the Keithley 2401.

        Safety & behavior:
            - The sweep runs on the instrument, so detection of fast current spikes happens
            instrument-side and will immediately switch the output off (protecting the device).
            - The script will increase the compliance when measured current is > 90% of current limiti,
            scaled by `icc_factor`, but never above `icc_max` (if provided).
            - If measured current >= burn_abort_A the script will abort (switch output OFF and print an ABORT marker).
            - The instrument prints lines "DATA:V,I" for each step; Python parses these into lists.
            - Returns a dict: {"status": "FORMED"/"NO_FORM"/"DAMAGE"/"ERROR", "voltages": [...], "currents": [...], "trace_file": optional, "message": optional}.

        Parameters:
            start_v, stop_v, step_v: sweep geometry (V)
            icc_start: initial compliance (A)
            icc_factor: factor to multiply compliance when near current limit
            icc_max: maximum allowed compliance (A); if None, a large upper bound is used
            delay_s: instrument-side settle delay after setting voltage (s)
            burn_abort_A: absolute current threshold to abort IMMEDIATELY (A); if None set to (icc_start * 10)

        Notes:
            - This routine expects self.device to be a pymeasure Keithley instance having:
                self.device.write(...) and self.device.adapter.connection.read() (pyvisa read)
            If those are missing it attempts a couple of fallbacks.
            - Make sure your instrument connection timeout is sufficiently long (we set a per-sweep timeout below)."""

        # --- sanity defaults and guards ---
        if icc_max is None:
            icc_max = icc_start * 1e3 if icc_start > 0 else 1.0  # very permissive fallback
        if burn_abort_A is None:
            burn_abort_A = max(icc_start * 10.0, icc_start + 1e-6)

        # Prepare container for results
        voltages = []
        currents = []
        device_id = getattr(self, "device", None) and getattr(self.device, "id", "keithley") or "keithley"

        # Build the TSP script (Keithley 2401 style). The script:
        # - configures SMU for voltage sourcing
        # - loops from start_v to stop_v in step_v increments
        # - measures I and V on each step, prints "DATA:V,I"
        # - if measured I >= burn_abort_A -> prints ABORT marker and turns output off immediately
        # - if measured I > 0.9 * limiti -> raises limiti but clamps to icc_max and prints COMPLIANCE_RAISED
        tsp_script = f"""
        -- TSP script generated by run_tsp_sweep
        smu.reset()
        smu.source.func = smu.FUNC_DC_VOLTAGE
        smu.measure.func = smu.FUNC_DC_CURRENT
        smu.source.autorangev = smu.ON
        smu.source.limiti = {icc_start}
        smu.source.output = smu.ON

        local startv = {start_v}
        local stopv  = {stop_v}
        local stepv  = {step_v}
        local icc_factor = {icc_factor}
        local icc_max = {icc_max}
        local burn_abort = {burn_abort_A}

        local v = startv
        print('TSP_STARTED')
        while v <= stopv do
        smu.source.levelv = v
        delay({delay_s})
        local measV = smu.measure.read(smu.FUNC_DC_VOLTAGE)
        local measI = smu.measure.read(smu.FUNC_DC_CURRENT)
        -- Print a data line. Python will parse lines starting with 'DATA:'
        print(string.format('DATA:%0.9g,%0.12g', measV, measI))

        -- Immediate abort if current exceeds burn_abort
        if math.abs(measI) >= burn_abort then
            print('ABORT:CURRENT_EXCEEDED')
            smu.source.output = smu.OFF
            break
        end

        -- Adaptive compliance: if close to current limit, raise it (but not above icc_max)
        if math.abs(measI) > 0.9 * smu.source.limiti then
            local newlim = smu.source.limiti * icc_factor
            if newlim > icc_max then
                newlim = icc_max
            end
            smu.source.limiti = newlim
            print(string.format('COMPLIANCE_RAISED:%0.12g', smu.source.limiti))
        end

        v = v + stepv
        end

        -- Ensure output off at the end
        smu.source.output = smu.OFF
        print('SWEEP_DONE')
        """

        # --- send script to instrument and read back output ---
        try:
            # Ensure underlying device object exists
            if not hasattr(self, "device") or self.device is None:
                return {"status": "ERROR", "message": "No instrument object available on controller."}

            # Write the script to the instrument
            # Some PyMeasure wrappers let you write multiline TSP directly
            try:
                # primary: use pymeasure's low-level write (should accept multi-line commands)
                self.device.write(tsp_script)
            except Exception:
                # fallback: try adapter connection write
                try:
                    self.device.adapter.connection.write(tsp_script)
                except Exception as e:
                    return {"status": "ERROR", "message": f"Failed to write TSP script: {e}"}

            # Now read back lines until SWEEP_DONE or ABORT
            voltages = []
            currents = []
            start_time = time.time()
            # compute a conservative timeout: proportional to number of steps * delay plus margin
            nsteps = int(max(1, math.floor((stop_v - start_v) / max(1e-12, step_v)) + 1))
            timeout = max(10.0, nsteps * (delay_s * 2.5) + 5.0)

            # We'll attempt reads using several fallbacks for different wrapper capabilities
            read_func = None
            if hasattr(self.device, "adapter") and hasattr(self.device.adapter, "connection"):
                read_func = lambda: self.device.adapter.connection.read().strip()
            elif hasattr(self.device, "read"):
                read_func = lambda: self.device.read().strip()
            elif hasattr(self.device, "ask"):
                # ask requires a command; we can't use it in the same way, but include as a last fallback
                read_func = lambda: self.device.ask("").strip()
            else:
                return {"status": "ERROR", "message": "No read method available on instrument wrapper."}

            # consume lines until marker or timeout
            got_abort = False
            while True:
                # timeout guard
                if time.time() - start_time > timeout:
                    raise TimeoutError("Timeout waiting for TSP output.")

                try:
                    line = read_func()
                except Exception as e:
                    # often read() will block until something is printed; small sleep and retry
                    time.sleep(0.005)
                    continue

                if not line:
                    # empty line - continue
                    time.sleep(0.001)
                    continue

                # We may receive multiple concatenated lines depending on wrapper; split and iterate
                for raw in line.splitlines():
                    raw = raw.strip()
                    if not raw:
                        continue
                    # handle markers
                    if raw.startswith("DATA:"):
                        payload = raw.split(":", 1)[1].strip()
                        try:
                            v_str, i_str = payload.split(",")
                            vv = float(v_str)
                            ii = float(i_str)
                            voltages.append(vv)
                            currents.append(ii)
                        except Exception:
                            # malformed data - skip
                            continue
                    elif raw.startswith("COMPLIANCE_RAISED:"):
                        # optional: parse and log the raised compliance value
                        # comp_val = float(raw.split(":",1)[1])
                        # (we just ignore or log it if you want)
                        continue
                    elif raw.startswith("ABORT:"):
                        got_abort = True
                        # stop reading further; the script also turned output off
                        break
                    elif raw == "SWEEP_DONE":
                        # normal end
                        break
                    # other prints (TSP_STARTED etc) - ignore or log
                if got_abort or raw == "SWEEP_DONE":
                    break

            # post-process and safety check
            if got_abort:
                # last recorded point may be the cause (or none if failed earlier)
                last_v = voltages[-1] if voltages else None
                last_i = currents[-1] if currents else None
                # optionally save trace file
                trace_file = None
                try:
                    if voltages and currents:
                        trace_file = f"tsp_trace_{timestamp()}.csv"
                        with open(trace_file, "w") as f:
                            f.write("V_V,I_A\n")
                            for vv, ii in zip(voltages, currents):
                                f.write(f"{vv},{ii}\n")
                except Exception:
                    trace_file = None
                return {"status": "DAMAGE", "message": "Instrument-side abort: current exceeded burn threshold",
                        "V_last": last_v, "I_last": last_i, "voltages": voltages, "currents": currents, "trace_file": trace_file}

            # if we reached here without abort, check for a jump in currents (simple heuristic)
            prev_i = max(1e-12, abs(currents[0])) if currents else 1e-12
            for vv, ii in zip(voltages[1:], currents[1:]):
                if abs(ii) >= (self.jump_factor if hasattr(self, 'jump_factor') else 100.0) * prev_i:
                    # formation event detected
                    trace_file = None
                    try:
                        if voltages and currents:
                            trace_file = f"tsp_trace_{timestamp()}.csv"
                            with open(trace_file, "w") as f:
                                f.write("V_V,I_A\n")
                                for vvv, iii in zip(voltages, currents):
                                    f.write(f"{vvv},{iii}\n")
                    except Exception:
                        trace_file = None
                    return {"status": "FORMED", "V_form": vv, "voltages": voltages, "currents": currents, "trace_file": trace_file}
                prev_i = abs(ii)

            # otherwise no form detected
            return {"status": "NO_FORM", "voltages": voltages, "currents": currents}

        except Exception as e:
            # Ensure output is off if anything goes wrong (best-effort)
            try:
                self.device.write("smu.source.output = smu.OFF")
            except Exception:
                pass
            return {"status": "ERROR", "message": str(e), "voltages": voltages, "currents": currents}


if __name__ == "__main__":
    keithley = Keithley2400Controller()  # Connect to the device
    print("Device ID:", keithley.device.id)  # Check connection

    # Test beep function using PyMeasure interface
    keithley.beep(100, 0.5)
    keithley.beep(1000, 0.5)
    keithley.beep(10000, 0.5)
    keithley.beep(100000, 0.5)

    keithley.close()

