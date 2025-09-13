


"""-------------------------------------------------------------------------
Unified 4200A controller classes for IVControllerManager

These classes wrap the minimal API expected by `IVControllerManager` so the
GUI can control a 4200A-SCS over the LPT server:
  - set_voltage(voltage: float, Icc: float = ...)
  - set_current(current: float, Vcc: float = ...)
  - measure_voltage() -> float
  - measure_current() -> float
  - enable_output(enable: bool)
  - close()

Additionally, convenience sweep and PMU helpers are provided.
-------------------------------------------------------------------------"""

import sys
from pathlib import Path
import time
from types import NoneType
import numpy as np
import pandas as pd

import atexit, signal, sys



# Ensure project root on sys.path for absolute imports when run as script
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Equipment.SMU_AND_PMU.ProxyClass import Proxy


class Keithley4200AController:
    """Unified controller for 4200A SMU_AND_PMU (DC) and basic PMU access using LPT.

    Address formats supported (examples):
      - "192.168.0.10:8888"            -> SMU1 by default
      - "192.168.0.10"                 -> SMU1 by default, port 8888
      - "192.168.0.10:8888|SMU2"       -> select SMU2
      - "192.168.0.10:8888|PMU1-CH2"   -> select PMU1 channel 2 (PMU mode)

    If running on the 4200A device (pylptlib available), pass address "LPTlib"
    to use the local DLL instead of TCP/IP.
    """

    def __init__(self, address: str) -> None:
        self._ip: str = ""
        self._port: int = 8888
        self._card_name: str = "SMU1"
        self._pmu_channel: int | None = None
        self._is_pmu: bool = False

        self.lpt = None
        self.param = None
        self._instr_id: int | None = None
        self._last_source_mode: str = "voltage"  # or "current"
        self._output_enabled: bool = False

        self._parse_address(address)
        self._connect()

    def _parse_address(self, address: str) -> None:
        addr = (address or "").strip()
        if addr.lower() == "lptlib":
            # Local DLL mode disabled in this build
            raise ValueError("Local LPTlib mode not supported. Use 'IP[:port]|SMUx' or '|PMU1-CHy'.")

        # Optional instrument selector after '|'
        instr_sel = None
        if "|" in addr:
            addr, instr_sel = addr.split("|", 1)
            instr_sel = instr_sel.strip()

        # IP[:port]
        if ":" in addr:
            ip_str, port_str = addr.split(":", 1)
            self._ip = ip_str.strip()
            try:
                self._port = int(port_str)
            except Exception:
                self._port = 8888
        else:
            self._ip = addr
            self._port = 8888

        # Instrument selection
        if instr_sel:
            token = instr_sel.replace(" ", "").upper()
            if token.startswith("SMU_AND_PMU"):
                self._card_name = token  # e.g. SMU2
                self._pmu_channel = None
                self._is_pmu = False
            elif token.startswith("PMU"):
                # Accept PMU1-CH2 or PMU1:2
                self._card_name = token.split("-")[0].split(":")[0]
                ch = None
                if "CH" in token:
                    try:
                        ch = int(token.split("CH")[-1])
                    except Exception:
                        ch = 1
                elif ":" in token:
                    try:
                        ch = int(token.split(":")[-1])
                    except Exception:
                        ch = 1
                self._pmu_channel = (ch - 1) if ch else 0
                self._is_pmu = True
        else:
            self._card_name = "SMU1"
            self._pmu_channel = None
            self._is_pmu = False

    def _connect(self) -> None:
        try:
            # Remote TCP proxy
            self.lpt = Proxy(self._ip, self._port, "lpt")
            self.param = Proxy(self._ip, self._port, "param")

            # Initialize session
            self.lpt.initialize()
            # For safety, reset and select test station
            self.lpt.tstsel(1)
            self.lpt.devint()

            self._instr_id = self.lpt.getinstid(self._card_name)

            # Reasonable defaults
            # Return real measured values in compliance
            self.lpt.setmode(self._instr_id, self.param.KI_LIM_MODE, self.param.KI_VALUE)
            # Fast integration default
            self.lpt.setmode(self._instr_id, self.param.KI_INTGPLC, 0.01)
            if not self._is_pmu:
                # Auto-range current measure by default
                self.lpt.rangei(self._instr_id, 0)

        except Exception as exc:
            raise RuntimeError(f"Failed to connect 4200A at {self._ip}:{self._port} ({self._card_name}): {exc}")

    # --------------- Unified API ---------------
    def set_voltage(self, voltage: float, Icc: float = 1e-3):
        self._last_source_mode = "voltage"
        if self._instr_id is None:
            return
        # Compliance on current for voltage source
        self.lpt.limiti(self._instr_id, float(Icc))
        self.lpt.forcev(self._instr_id, float(voltage))
        self._output_enabled = True

    def set_current(self, current: float, Vcc: float = 10.0):
        self._last_source_mode = "current"
        if self._instr_id is None:
            return
        # Compliance on voltage for current source
        self.lpt.limitv(self._instr_id, float(Vcc))
        self.lpt.forcei(self._instr_id, float(current))
        self._output_enabled = True

    def measure_voltage(self) -> float:
        if self._instr_id is None:
            return float("nan")
        return float(self.lpt.intgv(self._instr_id))

    def measure_current(self) -> float:
        if self._instr_id is None:
            return float("nan")
        return float(self.lpt.intgi(self._instr_id))

    def enable_output(self, enable: bool = True):
        # SMU_AND_PMU has no explicit output enable in LPT; emulate via sourcing 0 when disabling
        if self._instr_id is None:
            return
        if not enable:
            if self._last_source_mode == "voltage":
                self.lpt.forcev(self._instr_id, 0.0)
            else:
                self.lpt.forcei(self._instr_id, 0.0)
        self._output_enabled = enable

    def get_idn(self) -> str:
        ip = self._ip or "local"
        return f"Keithley 4200A-SCS via LPT ({ip}:{self._port}) {self._card_name}"

    def close(self):
        try:
            if self._instr_id is not None:
                # Put outputs to a safe state and deselect station
                try:
                    self.lpt.forcev(self._instr_id, 0.0)
                except Exception:
                    pass
            self.lpt.devint()
            try:
                self.lpt.tstdsl()
            except Exception:
                pass
        except Exception:
            pass

    # --------------- Convenience helpers ---------------
    def voltage_sweep(self, start_v: float, stop_v: float, step_v: float, delay_s: float = 0.05,
                       v_limit: float = 10.0, i_limit: float = 1e-3) -> list[tuple[float, float]]:
        points = []
        voltages = np.concatenate([
            np.arange(start_v, stop_v + step_v, step_v),
            np.arange(stop_v - step_v, start_v - step_v, -step_v),
        ])
        self.set_limits(v_limit=v_limit, i_limit=i_limit)
        for v in voltages:
            self.set_voltage(float(v), Icc=i_limit)
            time.sleep(delay_s)
            i = self.measure_current()
            points.append((float(v), float(i)))
        self.enable_output(False)
        return points

    def current_sweep(self, start_i: float, stop_i: float, step_i: float, delay_s: float = 0.05,
                       v_limit: float = 10.0) -> list[tuple[float, float]]:
        points = []
        currents = np.concatenate([
            np.arange(start_i, stop_i + step_i, step_i),
            np.arange(stop_i - step_i, start_i - step_i, -step_i),
        ])
        for i in currents:
            self.set_current(float(i), Vcc=v_limit)
            time.sleep(delay_s)
            v = self.measure_voltage()
            points.append((float(i), float(v)))
        self.enable_output(False)
        return points

    def set_limits(self, v_limit: float | None = None, i_limit: float | None = None):
        if self._instr_id is None:
            return
        if v_limit is not None:
            self.lpt.limitv(self._instr_id, float(v_limit))
        if i_limit is not None:
            self.lpt.limiti(self._instr_id, float(i_limit))



# -------------------------------------------
# Minimal dual-channel PMU helper (both CHs)
# -------------------------------------------
class Keithley4200A_PMUDualChannel:
    """Minimal dual-channel PMU helper using the LPT server.

    Goal: apply a voltage pulse and read back current, returning V, I, t, and R.
    Configures and uses both PMU channels to match the standard wiring (both
    channels engaged; CH2 held at 0 V by default as return path).

    Example address formats:
      - "192.168.0.10:8888|PMU1"
      - "192.168.0.10|PMU1"
      - "192.168.0.10:8888"  (defaults to PMU1)
    """

    def __init__(self, address: str):
        # Parse address and PMU card (always use both channels 1 and 2)
        if "|" in address:
            addr, instr_sel = address.split("|", 1)
            instr_sel = instr_sel.strip().upper()
        else:
            addr, instr_sel = address, "PMU1"

        if ":" in addr:
            ip, port = addr.split(":", 1)
            self._ip = ip
            self._port = int(port)
        else:
            self._ip = addr
            self._port = 8888


        # Instrument name (card), channels fixed to [1, 2]
        self.card = instr_sel.split("-")[0] if instr_sel else "PMU1"
        self.channels = [1, 2]

        # Proxies
        self.lpt = Proxy(self._ip, self._port, "lpt")
        self.param = Proxy(self._ip, self._port, "param")

        # Initialize tester
        self.lpt.initialize()

        try:
            self.lpt.tstsel(1)
        except Exception as e:
            print(e)
            print
            print("If you see this error close the terminal and rerun the script on both the 4200 and python terminal")
            print("the 4200 may need restarting is persists")
            print("Im not sure why this is occuring")
            sys.exit() # force close 

        self.lpt.devint()
        self.lpt.dev_abort()

        self.card_id = self.lpt.getinstid(self.card)
        self._configured = False

        print("PMU attempting configuration")

        # Configures PMU with defualts!       
        try:
            self._ensure_config()
            #self._configured = True
        except Exception:
            self._configured = False
            print("Failed to configure PMU")
            print("if this keeps happening try restarting the 4200a")
            pass

        # at close down, cleans up and hopfully shuts down any operation still running 
        # Stops a lot of errors from occuring if something goes wrong. Ie less restarts. 
        atexit.register(self.cleanup)
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda s, f: (self.cleanup(), sys.exit(0)))

    def cleanup(self):
        """"Cleans up and shuts down any operation still running"""
        try: self.output(False)
        except Exception: pass
        try: self.lpt.dev_abort()
        except Exception: pass
        try: self.lpt.tstdsl()
        except Exception: pass
        try: self.lpt.devint()
        except Exception: pass


    def _configure_both_channels(self,
                                 v_src_range: float = 10.0,
                                 v_meas_range_type: int = 0,
                                 v_meas_range: float = 10.0,
                                 i_meas_range_type: int = 0,
                                 i_meas_range: float = 0.2,
                                 v_limit: float = 5.0,
                                 i_limit: float = 1.0,
                                 power_limit: float = 10.0,
                                 start_pct: float = 0.1,
                                 stop_pct: float = 0.9,
                                 num_pulses: int = 1,
                                 period: float = 20e-6,
                                 delay: float = 1e-7,
                                 width: float = 10e-6,
                                 rise: float = 1e-7,
                                 fall: float = 1e-7,
                                 load_ohm: float = 1e6,
                                 acquire_time_stamp: int = 1) -> None:
        """"configures both channels"with the ranges limits and timing!"""
        # Configure pathway, measurement, ranges, limits, timing, and load for both channels
        for ch in self.channels:
            self.lpt.rpm_config(self.card_id, ch, self.param.KI_RPM_PATHWAY, self.param.KI_RPM_PULSE)
            self.lpt.pulse_meas_sm(self.card_id, ch,
                                   acquire_type=0,
                                   acquire_meas_v_ampl=1,
                                   acquire_meas_v_base=0,
                                   acquire_meas_i_ampl=1,
                                   acquire_meas_i_base=0,
                                   acquire_time_stamp=int(acquire_time_stamp),
                                   llecomp=0)
            self.lpt.pulse_ranges(self.card_id, ch,
                                  v_src_range,
                                  v_meas_range_type, v_meas_range,
                                  i_meas_range_type, i_meas_range)
            self.lpt.pulse_limits(self.card_id, ch, v_limit, i_limit, power_limit)
            self.lpt.pulse_meas_timing(self.card_id, ch, start_pct, stop_pct, int(num_pulses))
            self.lpt.pulse_source_timing(self.card_id, ch, period, delay, width, rise, fall)
            self.lpt.pulse_load(self.card_id, ch, load_ohm)

        # Software trigger by default
        # try:
        #     self.lpt.pulse_trig_source(self.card_id, 0)
        # except Exception:
        #     pass

        self._configured = True
        print("PMU default configured")

    def _ensure_config(self) -> None:
        
        if not self._configured:
            self._configure_both_channels()

    def measure_at_voltage(self,
                           amplitude_v: float,
                           base_v: float = 0.0,
                           width_s: float = 10e-6,
                           period_s: float = 20e-6,
                           meas_start_pct: float = 0.1,
                           meas_stop_pct: float = 0.9,
                           source_channel: int = 1,
                           hold_other_at_zero: bool = True,
                           force_fixed_ranges: bool = False,
                           v_meas_range: float = 10.0,
                           i_meas_range: float = 100e-6,
                           num_pulses: int = 1,
                           timeout_s: float = 10,
                           acquire_time_stamp: int = 1,
                           Trig_delay = int(500e-4),
                           trig_source: int | None = None,
                           trig_output: bool | None = None,
                           trig_polarity: int | None = None) -> pd.DataFrame:
        """Apply x num pulse and return V, I, t, and R (ohm) for the source channel.

        - Uses both channels: the non-source channel can be held at 0 V to match
          the typical wiring (manual figure 11 with both channels connected).
        - Returns a pandas DataFrame with columns: t (s), V (V), I (A), R (Ohm).
        """
        # checks if PMU is configured if not configures it
        try:
            self._ensure_config()
        except Exception:
            print("Failed to configure PMU")
            print("if this keeps happening try restarting the 4200a")
            sys.exit() # force close 

        # Optionally force fixed ranges (helps avoid bogus overflow values on some setups)
        # Sometimes this may be necessary to avoid errors! Not sure why yet. 

        v_src_range=max(abs(amplitude_v), v_meas_range) #Pulse Range in Volts

        
        if force_fixed_ranges:
            for ch in self.channels:
                # v_range_type=1 (fixed), i_range_type=1 (fixed)
                #pulse_range(int instr_id, long chan, double range);
                self.lpt.pulse_ranges(self.card_id, ch,
                                      v_src_range=v_src_range,
                                      v_range_type=1, v_range=float(v_meas_range),
                                      i_range_type=1, i_range=float(i_meas_range))

                print(f"Fixed Range for CH{ch}: {v_src_range}, {v_meas_range}, {i_meas_range}")
        else:
            for ch in self.channels:
                # Auto Range (i_range_type=0)
                # pulse_ranges(int instr_id, int chan, double VSrcRange, int Vrange_type, 
                # doubleVrange, int Irange_type, double Irange);
                self.lpt.pulse_ranges(self.card_id, ch,v_src_range=v_src_range,i_range_type=0,v_range_type=0)

        print("Set Ranges successfully")

        # Apply trigger settings if provided
        # for now this is not beenm checked
        if trig_source is not None:
            try:
                self.set_trigger_source(int(trig_source))
            except Exception:
                pass
        if trig_polarity is not None:
            try:
                self.set_trigger_polarity(int(trig_polarity))
            except Exception:
                pass
        if trig_output is not None:
            try:
                self.set_trigger_output(bool(trig_output))
            except Exception:
                pass

        print("Passed trigger set up correctly")

        # Update timing on both channels
        for ch in self.channels:
            self.lpt.pulse_source_timing(self.card_id, ch, period_s, 1e-7, width_s, 1e-7, 1e-7)
            self.lpt.pulse_meas_timing(self.card_id, ch, float(meas_start_pct), float(meas_stop_pct), int(num_pulses))

        print("Passed timing settings correctly")

        # Program setpoints: source channel to requested amplitude, other at 0 V if requested
        other_channel = 2 if int(source_channel) == 1 else 1
        self.lpt.pulse_sweep_linear(self.card_id, int(source_channel),
                                    self.param.PULSE_AMPLITUDE_SP,
                                    float(amplitude_v), float(amplitude_v), float(base_v))
        if hold_other_at_zero:
            self.lpt.pulse_sweep_linear(self.card_id, other_channel,
                                        self.param.PULSE_AMPLITUDE_SP,
                                        0.0, 0.0, 0.0)
        # for ch in self.channels:
        #     print("passed_setpoints")
        #     self.lpt.pulse_burst_count(self.card_id, ch, int(1))  #define num of pulses 
        #     self.lpt.pulse_output(self.card_id, ch, 1)   
        #     self.lpt.pulse_trig(self.card_id,0 ) # 2 burst trigger
        #     print("passed_trig")
        

        # Enable outputs on both channels
        for ch in self.channels:
            # delays trigger output by the trigger delay
            self.lpt.pulse_delay(self.card_id, ch, Trig_delay)
            self.lpt.pulse_output(self.card_id, ch, 1)

        print("Passed outputs correctly")
        print("Measuring under way")
        #trigger for 5 pulses

        # Execute and wait
        self.lpt.pulse_exec(self.param.PULSE_MODE_SIMPLE)
        t0 = time.time()
        while True:
            status, _ = self.lpt.pulse_exec_status()
            if status != self.param.PMU_TEST_STATUS_RUNNING:
                break
            if time.time() - t0 > float(timeout_s):
                self.lpt.dev_abort()
                raise TimeoutError("PMU pulse execution timed out")
            time.sleep(0.02)

        print("Passed execution, now waiting on Data")

        # Fetch both channels for diagnostics
        ch_data: dict[int, dict[str, np.ndarray]] = {}
        for ch in self.channels:
            try:
                buf_size = self.lpt.pulse_chan_status(self.card_id, ch)
                vv, ii, tt, st = self.lpt.pulse_fetch(self.card_id, ch, 0, max(0, buf_size - 1))
                ch_data[ch] = {
                    "v": np.array(vv, dtype=float),
                    "i": np.array(ii, dtype=float),
                    "t": np.array(tt, dtype=float),
                    "s": np.array(st, dtype=int),
                }
            except Exception:
                ch_data[ch] = {
                    "v": np.array([], dtype=float),
                    "i": np.array([], dtype=float),
                    "t": np.array([], dtype=float),
                    "s": np.array([], dtype=int),
                }

        print("Fetched Data successfully")

        # Decode and summarize statuses (helps diagnose overflow/invalid samples)
        try:
            for ch in self.channels:
                s_arr = ch_data[ch]["s"]
                if s_arr.size:
                    decoded = [self.lpt.decode_pulse_status(int(s)) for s in s_arr.tolist()]
                    # Print a tiny summary for quick debugging
                    unique, counts = np.unique(np.array(decoded, dtype=object), return_counts=True)
                    summary = {str(u): int(c) for u, c in zip(unique.tolist(), counts.tolist())}
                    #print(f"[PMU] CH{ch} status summary: {summary}")
        except Exception:
            pass

        print("Decoded statuses successfully")

        # Select the source channel arrays
        src = int(source_channel)
        v_arr = ch_data[src]["v"]
        i_arr = ch_data[src]["i"]
        ts_arr = ch_data[src]["t"]
        s_arr = ch_data[src]["s"]

        # Mask clearly invalid/sentinel readings (some servers encode NaN as huge numbers like 1e22)
        if i_arr.size:
            invalid = ~np.isfinite(i_arr) | (np.abs(i_arr) > 1e10)
            i_arr = np.where(invalid, np.nan, i_arr)

        # Compute resistance safely
        eps = 1e-15
        with np.errstate(divide="ignore", invalid="ignore"):
            r_arr = np.where(np.abs(i_arr) > eps, v_arr / i_arr, np.nan)

        df = pd.DataFrame({
            "t (s)": ts_arr,
            "V (V)": v_arr,
            "I (A)": i_arr,
            "R (Ohm)": r_arr,
        })

        # Attach raw status (int) for further diagnosis if needed
        if s_arr.size:
            df["Status"] = s_arr

        print("Finished returning Df successfully")

        return df


    def output(self, enable: bool) -> None:
        for ch in self.channels:
            try:
                self.lpt.pulse_output(self.card_id, ch, 1 if enable else 0)
            except Exception:
                pass

    # ---- High-level prep/start/wait/fetch helpers (no triggers) ----
    def prepare_measure_at_voltage(self,
                                   amplitude_v: float,
                                   base_v: float = 0.0,
                                   width_s: float = 10e-6,
                                   period_s: float = 20e-6,
                                   meas_start_pct: float = 0.1,
                                   meas_stop_pct: float = 0.9,
                                   source_channel: int = 1,
                                   hold_other_at_zero: bool = True,
                                   force_fixed_ranges: bool = False,
                                   v_meas_range: float = 10.0,
                                   i_meas_range: float = 100e-6,
                                   num_pulses: int = 1,
                                   delay_s: float | None = None,
                                   outputs_on: bool = True) -> None:
        """Prepare a measure-at-voltage style test without starting execution.

        - Configures ranges/limits/timing and setpoints.
        - Optionally enables outputs so a follow-up start() executes immediately.
        - No trigger configuration is performed here.
        """
        self._ensure_config()

        v_src_range = max(abs(amplitude_v), v_meas_range)
        if force_fixed_ranges:
            for ch in self.channels:
                self.lpt.pulse_ranges(self.card_id, ch,
                                      v_src_range=v_src_range,
                                      v_range_type=1, v_range=float(v_meas_range),
                                      i_range_type=1, i_range=float(i_meas_range))
        else:
            for ch in self.channels:
                self.lpt.pulse_ranges(self.card_id, ch,
                                      v_src_range=v_src_range,
                                      v_range_type=0, v_range=None,
                                      i_range_type=0, i_range=None)

        for ch in self.channels:
            self.lpt.pulse_source_timing(self.card_id, ch,
                                         float(period_s), 1e-7, float(width_s), 1e-7, 1e-7)
            self.lpt.pulse_meas_timing(self.card_id, ch,
                                       float(meas_start_pct), float(meas_stop_pct), int(num_pulses))
            if delay_s is not None:
                self.lpt.pulse_delay(self.card_id, ch, float(delay_s))

        src = int(source_channel)
        other = 2 if src == 1 else 1
        self.lpt.pulse_sweep_linear(self.card_id, src, self.param.PULSE_AMPLITUDE_SP,
                                    float(amplitude_v), float(amplitude_v), float(base_v))
        if hold_other_at_zero:
            self.lpt.pulse_sweep_linear(self.card_id, other, self.param.PULSE_AMPLITUDE_SP,
                                        0.0, 0.0, 0.0)

        if outputs_on:
            for ch in self.channels:
                self.lpt.pulse_output(self.card_id, ch, 1)

    def start(self) -> None:
        """Start an already-prepared PMU test in simple mode.

        Falls back to pulse_init if exec fails once.
        """
        try:
            self.lpt.pulse_exec(self.param.PULSE_MODE_SIMPLE)
        except Exception:
            try:
                self.lpt.pulse_init(self.card_id)
                self.lpt.pulse_exec(self.param.PULSE_MODE_SIMPLE)
            except Exception:
                raise

    def status(self) -> tuple[int, float]:
        """Return (status_code, elapsed_time_s)."""
        return self.lpt.pulse_exec_status()

    def wait(self, timeout_s: float = 10.0, poll_s: float = 0.02) -> None:
        """Block until PMU completes or timeout; raises TimeoutError on timeout."""
        t0 = time.time()
        while True:
            status, _elapsed = self.lpt.pulse_exec_status()
            if status != self.param.PMU_TEST_STATUS_RUNNING:
                return
            if time.time() - t0 > float(timeout_s):
                self.lpt.dev_abort()
                raise TimeoutError("PMU pulse execution timed out")
            time.sleep(float(poll_s))

    def fetch(self, channel: int = 1) -> pd.DataFrame:
        """Fetch V/I/t (and Status if present) for a single channel."""
        ch = int(channel)
        try:
            buf_size = self.lpt.pulse_chan_status(self.card_id, ch)
            v, i, ts, st = self.lpt.pulse_fetch(self.card_id, ch, 0, max(0, buf_size - 1))
        except Exception:
            v, i, ts, st = [], [], [], []

        v_arr = np.array(v, dtype=float)
        i_arr = np.array(i, dtype=float)
        ts_arr = np.array(ts, dtype=float)
        s_arr = np.array(st, dtype=int) if st else np.array([], dtype=int)

        if i_arr.size:
            invalid = ~np.isfinite(i_arr) | (np.abs(i_arr) > 1e10)
            i_arr = np.where(invalid, np.nan, i_arr)

        eps = 1e-15
        with np.errstate(divide="ignore", invalid="ignore"):
            r_arr = np.where(np.abs(i_arr) > eps, v_arr / i_arr, np.nan)

        df = pd.DataFrame({
            "t (s)": ts_arr,
            "V (V)": v_arr,
            "I (A)": i_arr,
            "R (Ohm)": r_arr,
        })
        if s_arr.size:
            df["Status"] = s_arr
        return df

    def abort(self) -> None:
        """Abort current PMU activity."""
        try:
            self.lpt.dev_abort()
        except Exception:
            pass

    def set_pulse_delay(self, delay_s: float, channel: int | None = None) -> None:
        """Set trigger-to-output delay for one channel or both if channel is None."""
        if channel is None:
            targets = self.channels
        else:
            targets = [int(channel)]
        for ch in targets:
            self.lpt.pulse_delay(self.card_id, ch, float(delay_s))

    # ---- Trigger helpers (dual-channel scope) ----
    def set_trigger_source(self, source: int) -> None:
        """Set PMU trigger source for the card (applies to both channels).

        0: software
        1: ext rising (initial only)
        2: ext falling (initial only)
        3: ext rising (per pulse)
        4: ext falling (per pulse)
        5: internal trig bus
        """
        try:
            self.lpt.pulse_trig_source(self.card_id, int(source))
        except Exception:
            pass

    def set_trigger_polarity(self, polarity: int) -> None:
        try:
            self.lpt.pulse_trig_polarity(self.card_id, int(polarity))
        except Exception:
            pass

    def set_trigger_output(self, state: bool) -> None:
        try:
            self.lpt.pulse_trig_output(self.card_id, 1 if state else 0)
        except Exception:
            pass

    def close(self) -> None:
        try:
            self.output(False)
        except Exception:
            pass
        try:
            self.lpt.devint()
            self.lpt.tstdsl()
        except Exception:
            pass

    # ---- Reliability helpers ----
    def _select_auto_ranges(self, amplitude_v: float, expected_res_ohm: float) -> tuple[float, float, float, float]:
        est_i = abs(amplitude_v) / max(abs(expected_res_ohm), 1e-12)
        i_ranges = [2e-6, 20e-6, 200e-6, 2e-3, 20e-3, 0.2]
        v_ranges = [0.2, 2.0, 10.0]
        chosen_i = next((rng for rng in i_ranges if est_i <= rng * 0.8), i_ranges[-1])
        chosen_v = next((rng for rng in v_ranges if abs(amplitude_v) <= rng * 0.9), v_ranges[-1])
        v_src = max(abs(amplitude_v), chosen_v)
        i_limit = min(max(est_i * 5.0, 1e-6), 0.1)
        print(v_src, chosen_v, chosen_i, i_limit)
        return float(v_src), float(chosen_v), float(chosen_i), float(i_limit)

    def measure_resistance(self,
                           amplitude_v: float,
                           expected_res_ohm: float,
                           shots: int = 5,
                           width_s: float = 10e-6,
                           period_s: float = 20e-6,
                           source_channel: int = 1) -> tuple[pd.DataFrame, pd.DataFrame]:
        v_src, v_rng, i_rng, _i_limit = self._select_auto_ranges(amplitude_v, expected_res_ohm)
        print(v_src, v_rng, i_rng, _i_limit)
        shot_rows = []
        raw_dfs = []
        for _ in range(int(max(1, shots))):
            df = self.measure_at_voltage(
                amplitude_v=float(amplitude_v),
                base_v=0.0,
                width_s=float(width_s),
                period_s=float(period_s),
                meas_start_pct=0.2,
                meas_stop_pct=0.8,
                source_channel=int(source_channel),
                force_fixed_ranges=True,
                v_meas_range=float(v_rng),
                i_meas_range=float(i_rng),
                num_pulses=1,
                timeout_s=10.0,
                acquire_time_stamp=1,
            )
            raw_dfs.append(df)
            v_med = float(np.nanmedian(df["V (V)"])) if not df.empty else float("nan")
            i_med = float(np.nanmedian(df["I (A)"])) if not df.empty else float("nan")
            r_med = float(v_med / i_med) if (abs(i_med) > 1e-15) else float("nan")
            shot_rows.append({
                "Shot": len(shot_rows) + 1,
                "Vmed (V)": v_med,
                "Imed (A)": i_med,
                "Rmed (Ohm)": r_med,
            })
        shots_df = pd.DataFrame(shot_rows)
        summary = pd.DataFrame([{ 
            "Vset (V)": float(amplitude_v),
            "Rexp (Ohm)": float(expected_res_ohm),
            "Rmedian (Ohm)": float(np.nanmedian(shots_df["Rmed (Ohm)"])) if not shots_df.empty else float("nan"),
            "Rmean (Ohm)": float(np.nanmean(shots_df["Rmed (Ohm)"])) if not shots_df.empty else float("nan"),
            "Rstd (Ohm)": float(np.nanstd(shots_df["Rmed (Ohm)"])) if not shots_df.empty else float("nan"),
            "i_range (A)": float(i_rng),
            "v_range (V)": float(v_rng),
            "v_src_range (V)": float(v_src),
        }])
        return summary, pd.concat(raw_dfs, ignore_index=True) if raw_dfs else pd.DataFrame()

    def measure_resistance_sweep(self,
                                 voltages: list[float],
                                 expected_res_ohm: float,
                                 shots: int = 3,
                                 width_s: float = 1e-6,
                                 period_s: float = 20e-6,
                                 source_channel: int = 1) -> pd.DataFrame:
        rows = []
        for vset in list(voltages or []):
            summary, _ = self.measure_resistance(float(vset), expected_res_ohm, shots, width_s, period_s, source_channel)
            rows.append(summary.iloc[0])
        return pd.DataFrame(rows)

    # ---- Bias + auxiliary pulse experiment ----
    def measure_bias_with_aux_pulse(self,
                                    bias_v: float,
                                    aux_pulse_v: float,
                                    width_s: float,
                                    period_s: float,
                                    delay_s: float = 1e-7,
                                    num_pulses: int = 1,
                                    bias_channel: int = 1,
                                    aux_channel: int = 2,
                                    v_meas_range: float = 2.0,
                                    i_meas_range: float = 200e-6,
                                    start_pct: float = 0.0,
                                    stop_pct: float = 1.0,
                                    fetch_both: bool = False) -> pd.DataFrame | tuple[pd.DataFrame, pd.DataFrame]:
        bias_ch = int(bias_channel)
        aux_ch = int(aux_channel)

        # Configure both channels; set bias as constant by sweeping start=stop= bias
        for ch in self.channels:
            self.lpt.rpm_config(self.card_id, ch, self.param.KI_RPM_PATHWAY, self.param.KI_RPM_PULSE)
            self.lpt.pulse_meas_sm(self.card_id, ch,
                                   acquire_type=0,
                                   acquire_meas_v_ampl=1,
                                   acquire_meas_v_base=0,
                                   acquire_meas_i_ampl=1,
                                   acquire_meas_i_base=0,
                                   acquire_time_stamp=1,
                                   llecomp=0)
            self.lpt.pulse_ranges(self.card_id, ch,
                                  v_src_range=max(abs(bias_v), abs(aux_pulse_v), v_meas_range),
                                  v_range_type=1, v_range=float(v_meas_range),
                                  i_range_type=1, i_range=float(i_meas_range))
            self.lpt.pulse_limits(self.card_id, ch, v_limit=10.0, i_limit=0.02, power_limit=1.0)
            self.lpt.pulse_meas_timing(self.card_id, ch, float(start_pct), float(stop_pct), int(num_pulses))
            self.lpt.pulse_source_timing(self.card_id, ch, period_s, float(delay_s), width_s, 1e-7, 1e-7)

        # Program bias on bias channel and aux pulse on aux channel
        self.lpt.pulse_sweep_linear(self.card_id, bias_ch, self.param.PULSE_AMPLITUDE_SP,
                                    float(bias_v), float(bias_v), 0.0)
        self.lpt.pulse_sweep_linear(self.card_id, aux_ch, self.param.PULSE_AMPLITUDE_SP,
                                    float(aux_pulse_v), float(aux_pulse_v), 0.0)

        # Enable both outputs and execute once
        self.lpt.pulse_output(self.card_id, bias_ch, 1)
        self.lpt.pulse_output(self.card_id, aux_ch, 1)
        self.lpt.pulse_exec(self.param.PULSE_MODE_SIMPLE)

        t0 = time.time()
        while True:
            status, _ = self.lpt.pulse_exec_status()
            if status != self.param.PMU_TEST_STATUS_RUNNING:
                break
            if time.time() - t0 > 10.0:
                self.lpt.dev_abort()
                raise TimeoutError("PMU bias+aux execution timed out")
            time.sleep(0.02)

        # Fetch bias channel (and optionally aux channel) to observe full response
        buf_size_bias = self.lpt.pulse_chan_status(self.card_id, bias_ch)
        v_b, i_b, ts_b, st_b = self.lpt.pulse_fetch(self.card_id, bias_ch, 0, max(0, buf_size_bias - 1))
        df_bias = pd.DataFrame({"t (s)": ts_b, "V (V)": v_b, "I (A)": i_b, "Status": st_b})

        if not fetch_both:
            return df_bias

        buf_size_aux = self.lpt.pulse_chan_status(self.card_id, aux_ch)
        v_a, i_a, ts_a, st_a = self.lpt.pulse_fetch(self.card_id, aux_ch, 0, max(0, buf_size_aux - 1))
        df_aux = pd.DataFrame({"t (s)": ts_a, "V (V)": v_a, "I (A)": i_a, "Status": st_a})
        return df_bias, df_aux

    def test_pulse_with_pretrigger(self,
                                   amplitude_v: float = 0.2,
                                   width_s: float = 50e-6,
                                   period_s: float = 200e-6,
                                   num_pulses: int = 5,
                                   source_channel: int = 1,
                                   hold_other_at_zero: bool = True,
                                   pretrigger_width_s: float = 50e-6) -> pd.DataFrame:
        """Simple helper: toggle TRIG OUT once (pre-trigger), then emit a short burst and fetch results.

        Uses Simple pulse mode and conservative defaults. Returns the DataFrame of the source channel.
        """
        src = int(source_channel)
        other = 2 if src == 1 else 1

        # Configure pathway/measurement
        for ch in self.channels:
            try:
                self.lpt.rpm_config(self.card_id, ch, self.param.KI_RPM_PATHWAY, self.param.KI_RPM_PULSE)
            except Exception:
                pass
            try:
                self.lpt.pulse_meas_sm(self.card_id, ch,
                                       acquire_type=0,
                                       acquire_meas_v_ampl=1,
                                       acquire_meas_v_base=0,
                                       acquire_meas_i_ampl=1,
                                       acquire_meas_i_base=0,
                                       acquire_time_stamp=1,
                                       llecomp=0)
            except Exception:
                pass

        # Send a TTL-only pre-trigger on TRIG OUT, with DUT outputs explicitly OFF
        # to avoid any activity on the DUT. Then proceed to set ranges/limits etc.
        try:
            # Ensure software trigger source so TRIG OUT toggling does not arm external flow
            self.lpt.pulse_trig_source(self.card_id, 0)
        except Exception:
            pass
        # Force outputs OFF before toggling TRIG OUT (belt and suspenders)
        for ch in self.channels:
            try:
                self.lpt.pulse_output(self.card_id, ch, 0)
            except Exception:
                pass
        try:
            self.lpt.pulse_trig_polarity(self.card_id, 1)
        except Exception:
            pass
        try:
            # Generate a clean TTL pulse on the rear TRIG OUT SMA
            self.lpt.pulse_trig_output(self.card_id, 0)
            time.sleep(1e-4)
            self.lpt.pulse_trig_output(self.card_id, 1)
            time.sleep(float(pretrigger_width_s))
            self.lpt.pulse_trig_output(self.card_id, 0)
        except Exception:
            pass

        # Ranges/limits
        try:
            self.lpt.pulse_ranges(self.card_id, src, v_src_range=max(abs(amplitude_v), 2.0), v_range_type=1, v_range=2.0, i_range_type=1, i_range=1e-3)
        except Exception:
            pass
        try:
            self.lpt.pulse_limits(self.card_id, src, v_limit=2.5, i_limit=1e-3, power_limit=1.0)
        except Exception:
            pass

        # Timing and measurement window
        try:
            self.lpt.pulse_source_timing(self.card_id, src, float(period_s), 1e-7, float(width_s), 1e-7, 1e-7)
            self.lpt.pulse_meas_timing(self.card_id, src, 0.1, 0.9, int(1))
        except Exception:
            pass

        # Amplitude and burst
        try:
            self.lpt.pulse_sweep_linear(self.card_id, src, self.param.PULSE_AMPLITUDE_SP, float(amplitude_v), float(amplitude_v), 0.0)
            self.lpt.pulse_burst_count(self.card_id, src, int(num_pulses))
        except Exception:
            pass

        # Optionally hold other at zero
        if hold_other_at_zero:
            try:
                self.lpt.pulse_sweep_linear(self.card_id, other, self.param.PULSE_AMPLITUDE_SP, 0.0, 0.0, 0.0)
            except Exception:
                pass

        # TRIG OUT already pulsed above while outputs were OFF.

        # Enable outputs
        for ch in self.channels:
            try:
                self.lpt.pulse_delay(self.card_id, ch, 0)
            except Exception:
                pass
            try:
                self.lpt.pulse_output(self.card_id, ch, 1)
            except Exception:
                pass

        # Execute simple-mode burst and wait
        try:
            self.lpt.pulse_exec(self.param.PULSE_MODE_SIMPLE)
        except Exception:
            # try re-init if exec fails
            try:
                self.lpt.pulse_init(self.card_id)
                self.lpt.pulse_exec(self.param.PULSE_MODE_SIMPLE)
            except Exception as exc:
                raise

        # wait for completion
        import time
        t0 = time.time()
        while True:
            status, _ = self.lpt.pulse_exec_status()
            if status != self.param.PMU_TEST_STATUS_RUNNING:
                break
            time.sleep(0.02)

        # fetch results for source channel
        buf_size = self.lpt.pulse_chan_status(self.card_id, src)
        v, i, ts, st = self.lpt.pulse_fetch(self.card_id, src, 0, max(0, buf_size - 1))
        df = pd.DataFrame({"t (s)": ts, "V (V)": v, "I (A)": i, "Status": st})
        return df



 

if __name__ == "__main__":
    print("nothing set up here yet ")

    