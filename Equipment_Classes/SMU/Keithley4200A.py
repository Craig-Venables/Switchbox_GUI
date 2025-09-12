


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

from Equipment_Classes.SMU.ProxyClass import Proxy


class Keithley4200AController:
    """Unified controller for 4200A SMU (DC) and basic PMU access using LPT.

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
            if token.startswith("SMU"):
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
        # SMU has no explicit output enable in LPT; emulate via sourcing 0 when disabling
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
        
        # try:
        #     self.lpt.dev_abort()
        # except Exception:
        #     pass

        #self.reset_lpt_server(self.lpt)

        # Initialize tester
        self.lpt.initialize()
        self.lpt.tstsel(1)
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
            pass

        atexit.register(self.cleanup)
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda s, f: (self.cleanup(), sys.exit(0)))

    def cleanup(self):
        try: pmu.output(False)
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
            print("a")
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
            print("b")

        # Software trigger by default
        # try:
        #     self.lpt.pulse_trig_source(self.card_id, 0)
        # except Exception:
        #     pass

        self._configured = True
        print("PMU configured")

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
                           timeout_s: float = 10.0,
                           acquire_time_stamp: int = 1,
                           trig_source: int | None = None,
                           trig_output: bool | None = None,
                           trig_polarity: int | None = None) -> pd.DataFrame:
        """Apply a single pulse and return V, I, t, and R (ohm) for the source channel.

        - Uses both channels: the non-source channel can be held at 0 V to match
          the typical wiring (manual figure 11 with both channels connected).
        - Returns a pandas DataFrame with columns: t (s), V (V), I (A), R (Ohm).
        """
        # checks if PMU is configured
        self._ensure_config()

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
                self.lpt.pulse_ranges(self.card_id, ch,v_src_range=v_src_range,i_range_type=0)

        print("passed_ranges")

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

        print("passed_trigger_settings")

        # Update timing on both channels
        for ch in self.channels:
            self.lpt.pulse_source_timing(self.card_id, ch, period_s, 1e-7, width_s, 1e-7, 1e-7)
            self.lpt.pulse_meas_timing(self.card_id, ch, float(meas_start_pct), float(meas_stop_pct), int(num_pulses))

        print("passed_timing_settings")

        # Program setpoints: source channel to requested amplitude, other at 0 V if requested
        other_channel = 2 if int(source_channel) == 1 else 1
        self.lpt.pulse_sweep_linear(self.card_id, int(source_channel),
                                    self.param.PULSE_AMPLITUDE_SP,
                                    float(amplitude_v), float(amplitude_v), float(base_v))
        if hold_other_at_zero:
            self.lpt.pulse_sweep_linear(self.card_id, other_channel,
                                        self.param.PULSE_AMPLITUDE_SP,
                                        0.0, 0.0, 0.0)

        print("passed_setpoints")
        #self.lpt.pulse_burst_count(self.card_id, ch, int(1))  #define num of pulses 
        #self.lpt.pulse_output(self.card_id, ch, 1)   
        #self.lpt.pulse_trig(self.card_id,0 ) # 2 burst trigger
        print("passed_trig")
        

        # Enable outputs on both channels
        for ch in self.channels:
            # delays trigger output by 50us
            self.lpt.pulse_delay(self.card_id, ch, 50e-6)
            self.lpt.pulse_output(self.card_id, ch, 1)

        print("passed_outputs")
        #trigger for 5 pulses
        
        #maybe add if stastment to check fior trigger or no trigger?
        
        

        # fails onthe pulse_trig, due too a fucntion not valid in the present pulse mode! 
        
        
        # Execute and wait
        #PULSE_MODE_ADVANCED
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

        print("passed_exec")

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

        print("passed_fetch")

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

        print("passed_statuses")

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

        print("Finished returning Df")

        return df

    def create_and_upload_arb(self,
                              chan: int,
                              levels: list[float],
                              time_per_point: float,
                              fname: str | None = None) -> str:
        """Upload an arbitrary waveform to the pulse card.

        - chan: channel to associate the arb with (1 or 2)
        - levels: list of voltage levels (floats)
        - time_per_point: sample interval in seconds for each level
        - fname: optional name for the uploaded waveform; autogenerated if None

        Returns the waveform name used on the server.
        """
        if not isinstance(levels, (list, tuple)) or len(levels) == 0:
            raise ValueError("levels must be a non-empty list of floats")
        if float(time_per_point) <= 0:
            raise ValueError("time_per_point must be > 0")

            

        fname = fname or f"py_arb_{int(time.time()*1e6)}"
        try:
            # ensure card is in ARB/PG2 mode before uploading arb array
            try:
                self.lpt.pg2_init(self.card_id, 2)
            except Exception:
                pass
            # arb_array(instr_id, chan, time_per_pt, length, level_arr, fname)
            self.lpt.arb_array(self.card_id, int(chan), float(time_per_point), int(len(levels)), list(levels), fname)
        except Exception:
            # try to re-init the card once then rethrow the exception
            try:
                self.lpt.pulse_init(self.card_id)
                self.lpt.arb_array(self.card_id, int(chan), float(time_per_point), int(len(levels)), list(levels), fname)
            except Exception as exc:
                raise
        return fname

    def run_arb_waveform(self,
                         chan: int,
                         fname: str,
                         mode: str = "full",
                         trig_source: int = 0,
                         trig_output: bool = True,
                         burst_count: int = 1,
                         v_meas_range: float = 2.0,
                         i_meas_range: float = 1e-3,
                         timeout_s: float = 10.0) -> pd.DataFrame:
        """Run a previously uploaded arb waveform and return measured V/I/t.

        mode: 'full' -> full arb (mode_id=2), 'segment' -> segment arb (mode_id=1)
        """
        if not fname:
            raise ValueError("fname is required to run an arb waveform")

        mode_id = 2 if mode == "full" else 1

        # Put card into requested PG/ARB mode
        try:
            self.lpt.pg2_init(self.card_id, int(mode_id))
        except Exception:
            pass

        # Load the named arb into the card (if present)
        try:
            # arb_file(instr_id, chan, fname)
            self.lpt.arb_file(self.card_id, int(chan), fname)
        except Exception:
            # ignore if server already has it or doesn't support loading by name
            pass

        # For full ARB the server often expects the channel to be associated with the uploaded arb
        # Try an explicit full-ARB registration step if available
        try:
            # Some servers accept pulse_sweep_linear with a special sweep type to bind the arb; try using PULSE_AMPLITUDE_SP with start==stop==0
            self.lpt.pulse_sweep_linear(self.card_id, int(chan), self.param.PULSE_AMPLITUDE_SP, 0.0, 0.0, 0.0)
        except Exception:
            pass

        # Configure measurement for waveform
        try:
            self.lpt.pulse_meas_wfm(self.card_id, int(chan), acquire_type=1, acquire_meas_v=1, acquire_meas_i=1, acquire_time_stamp=1, llecomp=0)
        except Exception:
            try:
                # fallback to spot-mean config
                self.lpt.pulse_meas_sm(self.card_id, int(chan), acquire_type=0, acquire_meas_v_ampl=1, acquire_meas_v_base=0, acquire_meas_i_ampl=1, acquire_meas_i_base=0, acquire_time_stamp=1, llecomp=0)
            except Exception:
                pass

        # Set ranges and limits
        try:
            self.lpt.pulse_ranges(self.card_id, int(chan), v_src_range=max(abs(v_meas_range), 2.0), v_range_type=1, v_range=float(v_meas_range), i_range_type=1, i_range=float(i_meas_range))
        except Exception:
            pass
        try:
            self.lpt.pulse_limits(self.card_id, int(chan), v_limit=float(max(v_meas_range, 10.0)), i_limit=float(i_meas_range), power_limit=1.0)
        except Exception:
            pass

        # Set burst count and trigger I/O
        try:
            self.lpt.pulse_burst_count(self.card_id, int(chan), int(burst_count))
        except Exception:
            pass
        # Ensure the channel is added to the test by defining a sweep on it
        try:
            self.lpt.pulse_sweep_linear(self.card_id, int(chan), self.param.PULSE_AMPLITUDE_SP, 0.0, 0.0, 0.0)
        except Exception:
            pass
        try:
            self.lpt.pulse_trig_source(self.card_id, int(trig_source))
        except Exception:
            pass
        try:
            self.lpt.pulse_trig_output(self.card_id, 1 if trig_output else 0)
        except Exception:
            pass

        # Enable outputs
        try:
            self.lpt.pulse_output(self.card_id, int(chan), 1)
        except Exception:
            pass

        # Execute in advanced/arb-capable mode (fallback to simple if not available)
        exec_mode = getattr(self.param, "PULSE_MODE_ADVANCED", getattr(self.param, "PULSE_MODE_SIMPLE", 1))
        try:
            self.lpt.pulse_exec(exec_mode)
        except Exception:
            try:
                self.lpt.pulse_init(self.card_id)
                self.lpt.pulse_exec(exec_mode)
            except Exception as exc:
                raise

        # Wait for completion
        t0 = time.time()
        while True:
            status, _ = self.lpt.pulse_exec_status()
            if status != self.param.PMU_TEST_STATUS_RUNNING:
                break
            if time.time() - t0 > float(timeout_s):
                try:
                    self.lpt.dev_abort()
                except Exception:
                    pass
                raise TimeoutError("ARB execution timed out")
            time.sleep(0.02)

        # Fetch data
        buf_size = 0
        try:
            buf_size = self.lpt.pulse_chan_status(self.card_id, int(chan))
        except Exception:
            pass
        try:
            v, i, ts, st = self.lpt.pulse_fetch(self.card_id, int(chan), 0, max(0, buf_size - 1))
        except Exception:
            v, i, ts, st = [], [], [], []

        df = pd.DataFrame({"t (s)": ts, "V (V)": v, "I (A)": i})
        if st:
            df["Status"] = st
        return df

    # ---- Segment ARB helpers (PG2 segment mode) ----
    def build_segments_from_volts_times(self,
                                        volts: list[float],
                                        times: list[float]) -> tuple[list[float], list[float], list[float], list[int], list[int]]:
        """Convert sample/hold-style volts,times arrays into segment parameters.

        Returns (startvals, stopvals, timevals, triggervals, output_relays)
        suitable for seg_arb_define. Uses simple 0 trigger and 0 relay values.
        """
        if not volts or not times or len(times) != len(volts):
            raise ValueError("volts and times must be non-empty and same length")
        n = len(volts)
        startvals = []
        stopvals = []
        timevals = []
        triggervals = []
        output_relays = []
        # each entry is a flat segment at volts[i] for times[i]
        for i in range(n):
            v = float(volts[i])
            t = float(times[i])
            if t <= 0:
                continue
            startvals.append(v)
            stopvals.append(v)
            timevals.append(t)
            triggervals.append(0)
            output_relays.append(0)
        return startvals, stopvals, timevals, triggervals, output_relays

    def run_segment_arb(self,
                        chan: int,
                        startvals: list[float],
                        stopvals: list[float],
                        timevals: list[float],
                        triggervals: list[int] | None = None,
                        output_relays: list[int] | None = None,
                        trig_source: int = 0,
                        trig_output: bool = True,
                        v_meas_range: float = 2.0,
                        i_meas_range: float = 1e-3,
                        timeout_s: float = 10.0) -> pd.DataFrame:
        """Define a segment-ARB sequence on chan and execute it (PG2 segment mode).

        Expects per-segment arrays of equal length.
        """
        chan = int(chan)
        nsegments = len(startvals)
        if not (nsegments and len(stopvals) == nsegments and len(timevals) == nsegments):
            raise ValueError("startvals, stopvals, timevals must have same non-zero length")
        trigs = [int(x) for x in (triggervals if triggervals else [0] * nsegments)]
        relays = [int(x) for x in (output_relays if output_relays else [0] * nsegments)]

        # Segment ARB mode
        try:
            self.lpt.pg2_init(self.card_id, 1)  # 1: segment arb
        except Exception:
            pass
        try:
            self.lpt.pulse_init(self.card_id)
        except Exception:
            pass

        # Define segments and waveform
        define_ok = False
        try:
            # Preferred path (if server impl is correct)
            self.lpt.seg_arb_define(self.card_id, chan, int(nsegments), list(startvals), list(stopvals), list(timevals), trigs, relays)
            define_ok = True
        except Exception:
            # Fallback: use seg_arb_sequence API to register segments under a single sequence
            try:
                seq_num = 1
                meas_type = [1.0] * nsegments      # 1 = Spot measurement per segment
                meas_start = [0.2] * nsegments     # 20% window
                meas_stop = [0.8] * nsegments      # 80% window
                self.lpt.seg_arb_sequence(
                    self.card_id,
                    chan,
                    int(seq_num),
                    int(nsegments),
                    list(startvals),
                    list(stopvals),
                    list(timevals),
                    trigs,
                    relays,
                    meas_type,
                    meas_start,
                    meas_stop,
                )
                # Build waveform from that single sequence
                self.lpt.seg_arb_waveform(self.card_id, chan, 1, [seq_num], [1.0])
                define_ok = True
            except Exception:
                define_ok = False
        if define_ok:
            try:
                # If we used seg_arb_define we may still want a simple waveform; attempt but ignore failures
                seq_ids = list(range(nsegments))
                loop_counts = [1.0] * nsegments
                self.lpt.seg_arb_waveform(self.card_id, chan, int(len(seq_ids)), seq_ids, loop_counts)
            except Exception:
                pass

        # Configure measurement
        try:
            self.lpt.pulse_meas_wfm(self.card_id, chan, acquire_type=1, acquire_meas_v=1, acquire_meas_i=1, acquire_time_stamp=1, llecomp=0)
        except Exception:
            pass
        # Ranges/limits
        try:
            self.lpt.pulse_ranges(self.card_id, chan, v_src_range=max(abs(v_meas_range), 2.0), v_range_type=1, v_range=float(v_meas_range), i_range_type=1, i_range=float(i_meas_range))
        except Exception:
            pass
        try:
            self.lpt.pulse_limits(self.card_id, chan, v_limit=float(max(v_meas_range, 10.0)), i_limit=float(i_meas_range), power_limit=1.0)
        except Exception:
            pass

        # Trigger and outputs
        try:
            self.lpt.pulse_trig_source(self.card_id, int(trig_source))
        except Exception:
            pass
        try:
            self.lpt.pulse_trig_output(self.card_id, 1 if trig_output else 0)
        except Exception:
            pass
        try:
            self.lpt.pulse_output(self.card_id, chan, 1)
        except Exception:
            pass

        # Execute advanced mode
        exec_mode = getattr(self.param, "PULSE_MODE_ADVANCED", getattr(self.param, "PULSE_MODE_SIMPLE", 1))
        try:
            self.lpt.pulse_exec(exec_mode)
        except Exception:
            try:
                self.lpt.pulse_init(self.card_id)
                self.lpt.pulse_exec(exec_mode)
            except Exception as exc:
                raise

        # Wait and fetch
        t0 = time.time()
        while True:
            status, _ = self.lpt.pulse_exec_status()
            if status != self.param.PMU_TEST_STATUS_RUNNING:
                break
            if time.time() - t0 > float(timeout_s):
                try:
                    self.lpt.dev_abort()
                except Exception:
                    pass
                raise TimeoutError("Segment ARB execution timed out")
            time.sleep(0.02)

        buf = self.lpt.pulse_chan_status(self.card_id, chan)
        v, i, ts, st = self.lpt.pulse_fetch(self.card_id, chan, 0, max(0, buf - 1))
        df = pd.DataFrame({"t (s)": ts, "V (V)": v, "I (A)": i})
        if st:
            df["Status"] = st
        return df

    def output(self, enable: bool) -> None:
        for ch in self.channels:
            try:
                self.lpt.pulse_output(self.card_id, ch, 1 if enable else 0)
            except Exception:
                pass

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
                                   hold_other_at_zero: bool = True) -> pd.DataFrame:
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

        # Enable TRIG OUT and send a quick manual pre-trigger pulse (toggle)
        try:
            self.lpt.pulse_trig_polarity(self.card_id, 1)
            print("trig_polarity out")
        except Exception:
            pass
        try:
            # Enable TRIG OUT
            self.lpt.pulse_trig_output(self.card_id, 1)
            print("trig_out out")
        except Exception:
            pass
        # Do not manually toggle TRIG OUT here; rely on PMU arm/start marker

        # Enable outputs
        for ch in self.channels:
            try:
                self.lpt.pulse_delay(self.card_id, ch, 50e-6)
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


    # ---- Memristor-oriented convenience APIs ----
    def memr_read(self,
                  read_v: float = 0.2,
                  expected_res_ohm: float = 100_000.0,
                  shots: int = 5,
                  width_s: float = 200e-6,
                  period_s: float = 500e-6,
                  source_channel: int = 1) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Low-stress read of device resistance at a small bias voltage.

        Returns (summary_df, raw_df).
        """
        return self.measure_resistance(
            amplitude_v=float(read_v),
            expected_res_ohm=float(expected_res_ohm),
            shots=int(shots),
            width_s=float(width_s),
            period_s=float(period_s),
            source_channel=int(source_channel),
        )

    def memr_iv(self,
                voltages: list[float],
                expected_res_ohm: float,
                shots: int = 3,
                width_s: float = 200e-6,
                period_s: float = 500e-6,
                source_channel: int = 1) -> pd.DataFrame:
        """Quasi-static IV: sweep small set of voltages with late-window sampling and shots.

        Returns a summary DataFrame with Vset and robust R per step.
        """
        return self.measure_resistance_sweep(
            voltages=list(voltages or []),
            expected_res_ohm=float(expected_res_ohm),
            shots=int(shots),
            width_s=float(width_s),
            period_s=float(period_s),
            source_channel=int(source_channel),
        )

    def memr_perturb_relax(self,
                            bias_v: float,
                            pulse_v: float,
                            width_s: float,
                            period_s: float,
                            delay_s: float = 1e-7,
                            num_pulses: int = 1,
                            bias_channel: int = 1,
                            aux_channel: int = 2,
                            v_meas_range: float = 2.0,
                            i_meas_range: float = 200e-6,
                            capture_start_pct: float = 0.0,
                            capture_stop_pct: float = 1.0,
                            fetch_both: bool = False) -> pd.DataFrame | tuple[pd.DataFrame, pd.DataFrame]:
        """Bias + auxiliary pulse: observe bias channel waveform (V/I/t) including relaxation."""
        return self.measure_bias_with_aux_pulse(
            bias_v=float(bias_v),
            aux_pulse_v=float(pulse_v),
            width_s=float(width_s),
            period_s=float(period_s),
            delay_s=float(delay_s),
            num_pulses=int(num_pulses),
            bias_channel=int(bias_channel),
            aux_channel=int(aux_channel),
            v_meas_range=float(v_meas_range),
            i_meas_range=float(i_meas_range),
            start_pct=float(capture_start_pct),
            stop_pct=float(capture_stop_pct),
            fetch_both=bool(fetch_both),
        )



# ----------------------------
# Memristor measurement wrapper
# ----------------------------
class MemristorMeasurements:
    """User-friendly wrapper exposing common memristor tests.

    All methods return a dict containing:
      - "summary": DataFrame with key metrics to use
      - "raw_ch1": DataFrame of CH1 waveform data (if available)
      - "raw_ch2": DataFrame of CH2 waveform data (if available)
    """

    def __init__(self, pmu: Keithley4200A_PMUDualChannel):
        self.pmu = pmu

    def pulse_iv_sweep(self,
                       levels: list[float],
                       width_s: float,
                       period_s: float,
                       source_channel: int = 1,
                       v_meas_range: float = 2.0,
                       i_meas_range: float = 20e-6,
                       meas_start_pct: float = 0.85,
                       meas_stop_pct: float = 0.98) -> dict:
        rows = []
        raw_all = []
        for vset in list(levels or []):
            df = self.pmu.measure_at_voltage(amplitude_v=float(vset), base_v=0.0,
                                             width_s=float(width_s), period_s=float(period_s),
                                             meas_start_pct=float(meas_start_pct), meas_stop_pct=float(meas_stop_pct),
                                             source_channel=int(source_channel), hold_other_at_zero=True,
                                             force_fixed_ranges=True,
                                             v_meas_range=float(v_meas_range), i_meas_range=float(i_meas_range),
                                             num_pulses=1, timeout_s=10.0)
            df["Level (V)"] = float(vset)
            raw_all.append(df)
            vmed = float(np.nanmedian(df["V (V)"])) if not df.empty else float("nan")
            imed = float(np.nanmedian(df["I (A)"])) if not df.empty else float("nan")
            rmed = float(vmed / imed) if abs(imed) > 1e-15 else float("nan")
            rows.append({"Level (V)": float(vset), "Vmed (V)": vmed, "Imed (A)": imed, "Rmed (Ohm)": rmed})
        return {"summary": pd.DataFrame(rows), "raw_ch1": pd.concat(raw_all, ignore_index=True) if raw_all else pd.DataFrame()}

    def pulse_width_sweep(self,
                          voltage_v: float,
                          widths_s: list[float],
                          period_factor: float = 3.0,
                          source_channel: int = 1,
                          v_meas_range: float = 2.0,
                          i_meas_range: float = 20e-6,
                          meas_start_pct: float = 0.85,
                          meas_stop_pct: float = 0.98) -> dict:
        rows = []
        raw_all = []
        for w in list(widths_s or []):
            period = max(float(w) * float(period_factor), 20e-6)
            df = self.pmu.measure_at_voltage(amplitude_v=float(voltage_v), base_v=0.0,
                                             width_s=float(w), period_s=period,
                                             meas_start_pct=float(meas_start_pct), meas_stop_pct=float(meas_stop_pct),
                                             source_channel=int(source_channel), hold_other_at_zero=True,
                                             force_fixed_ranges=True,
                                             v_meas_range=float(v_meas_range), i_meas_range=float(i_meas_range),
                                             num_pulses=1, timeout_s=10.0)
            df["Width (s)"] = float(w)
            raw_all.append(df)
            vmed = float(np.nanmedian(df["V (V)"])) if not df.empty else float("nan")
            imed = float(np.nanmedian(df["I (A)"])) if not df.empty else float("nan")
            rmed = float(vmed / imed) if abs(imed) > 1e-15 else float("nan")
            rows.append({"Width (s)": float(w), "Vmed (V)": vmed, "Imed (A)": imed, "Rmed (Ohm)": rmed})
        return {"summary": pd.DataFrame(rows), "raw_ch1": pd.concat(raw_all, ignore_index=True) if raw_all else pd.DataFrame()}

    def fast_read(self,
                  read_v: float = 0.2,
                  duration_pulses: int = 50,
                  width_s: float = 50e-6,
                  period_s: float = 100e-6,
                  source_channel: int = 1,
                  v_meas_range: float = 2.0,
                  i_meas_range: float = 200e-6) -> dict:
        # Capture as fast as PMU allows with repeated pulses
        df = self.pmu.measure_at_voltage(amplitude_v=float(read_v), base_v=0.0,
                                         width_s=float(width_s), period_s=float(period_s),
                                         meas_start_pct=0.0, meas_stop_pct=1.0,
                                         source_channel=int(source_channel), hold_other_at_zero=True,
                                         force_fixed_ranges=True,
                                         v_meas_range=float(v_meas_range), i_meas_range=float(i_meas_range),
                                         num_pulses=int(duration_pulses), timeout_s=30.0)
        return {"summary": pd.DataFrame(), "raw_ch1": df}

    def perturb_measure(self,
                         bias_v: float,
                         pulse_v: float,
                         width_s: float,
                         period_s: float,
                         delay_s: float = 5e-6,
                         num_pulses: int = 3,
                         v_meas_range: float = 2.0,
                         i_meas_range: float = 200e-6,
                         fetch_both: bool = True) -> dict:
        res = self.pmu.memr_perturb_relax(bias_v=float(bias_v), pulse_v=float(pulse_v),
                                          width_s=float(width_s), period_s=float(period_s), delay_s=float(delay_s),
                                          num_pulses=int(num_pulses),
                                          bias_channel=1, aux_channel=2,
                                          v_meas_range=float(v_meas_range), i_meas_range=float(i_meas_range),
                                          capture_start_pct=0.0, capture_stop_pct=1.0,
                                          fetch_both=bool(fetch_both))
        if fetch_both:
            bias_df, aux_df = res
            return {"summary": pd.DataFrame(), "raw_ch1": bias_df, "raw_ch2": aux_df}
        return {"summary": pd.DataFrame(), "raw_ch1": res}

    def run_modes_from_json(self,
                             config_path: str,
                             bias_v: float = 0.0,
                             bias_channel: int = 1,
                             aux_channel: int = 2) -> dict:
        """Run tests defined in a JSON like PMU_modes.json against the DUT using two channels.

        For pattern-like modes, CH2 pulses while CH1 probes at bias_v.
        Returns a dict mapping mode names to their result dicts.
        """
        import json, math
        with open(config_path, "r") as f:
            cfg = json.load(f)

        results: dict[str, dict] = {}

        # Helper: single run
        def run_bias_pulse(ampl_v: float, width: float, period: float, num_p: int) -> dict:
            res = self.pmu.memr_perturb_relax(bias_v=float(bias_v), pulse_v=float(ampl_v),
                                              width_s=float(width), period_s=float(period),
                                              delay_s=min(5e-6, max(1e-7, 0.1*width)),
                                              num_pulses=int(num_p),
                                              bias_channel=int(bias_channel), aux_channel=int(aux_channel),
                                              v_meas_range=2.0, i_meas_range=200e-6,
                                              capture_start_pct=0.0, capture_stop_pct=1.0,
                                              fetch_both=True)
            ch1, ch2 = res
            return {"summary": pd.DataFrame(), "raw_ch1": ch1, "raw_ch2": ch2}

        # Pulse Train
        if "Pulse Train" in cfg:
            c = cfg["Pulse Train"]
            results["Pulse Train"] = run_bias_pulse(c.get("amplitude_v", 0.5), c.get("width_s", 1e-5),
                                                     c.get("period_s", 2e-5), c.get("num_pulses", 10))

        # Pulse Pattern (string of 1/0)
        if "Pulse Pattern" in cfg:
            c = cfg["Pulse Pattern"]
            amp = float(c.get("amplitude_v", 0.5))
            width = float(c.get("width_s", 1e-5))
            period = float(c.get("period_s", 2e-5))
            pattern = str(c.get("pattern", "1011"))
            raw1_list, raw2_list = [], []
            for bit in pattern:
                a = amp if bit == "1" else 0.0
                r = run_bias_pulse(a, width, period, 1)
                raw1_list.append(r["raw_ch1"]) ; raw2_list.append(r["raw_ch2"]) 
            results["Pulse Pattern"] = {"summary": pd.DataFrame(),
                                         "raw_ch1": pd.concat(raw1_list, ignore_index=True) if raw1_list else pd.DataFrame(),
                                         "raw_ch2": pd.concat(raw2_list, ignore_index=True) if raw2_list else pd.DataFrame()}

        # Amplitude Sweep
        if "Amplitude Sweep" in cfg:
            c = cfg["Amplitude Sweep"]
            start = float(c.get("base_v", 0.0))
            stop = float(c.get("stop_v", 1.0))
            step = float(c.get("step_v", 0.1))
            width = float(c.get("width_s", 1e-5))
            period = float(c.get("period_s", 2e-5))
            levels = list(np.arange(start, stop + step/2.0, step))
            rows, raw1_list, raw2_list = [], [], []
            for vset in levels:
                r = run_bias_pulse(vset, width, period, 1)
                raw1_list.append(r["raw_ch1"]) ; raw2_list.append(r["raw_ch2"]) 
                df = r["raw_ch1"]
                vmed = float(np.nanmedian(df["V (V)"])) if not df.empty else float("nan")
                imed = float(np.nanmedian(df["I (A)"])) if not df.empty else float("nan")
                rmed = float(vmed/imed) if abs(imed) > 1e-15 else float("nan")
                rows.append({"Level (V)": float(vset), "Vmed (V)": vmed, "Imed (A)": imed, "Rmed (Ohm)": rmed})
            results["Amplitude Sweep"] = {"summary": pd.DataFrame(rows),
                                           "raw_ch1": pd.concat(raw1_list, ignore_index=True) if raw1_list else pd.DataFrame(),
                                           "raw_ch2": pd.concat(raw2_list, ignore_index=True) if raw2_list else pd.DataFrame()}

        # Width Sweep
        if "Width Sweep" in cfg:
            c = cfg["Width Sweep"]
            amp = float(c.get("amplitude_v", 0.5))
            width = float(c.get("width_s", 1e-5))
            period = float(c.get("period_s", 2e-5))
            num_p = int(c.get("num_pulses", 5))
            results["Width Sweep"] = run_bias_pulse(amp, width, period, num_p)

        # Transient (single pulse)
        if "Transient" in cfg:
            c = cfg["Transient"]
            results["Transient"] = run_bias_pulse(c.get("amplitude_v", 0.5), c.get("width_s", 1e-5),
                                                   c.get("period_s", 2e-5), 1)

        # Endurance (many pulses)
        if "Endurance" in cfg:
            c = cfg["Endurance"]
            results["Endurance"] = run_bias_pulse(c.get("amplitude_v", 0.5), c.get("width_s", 1e-5),
                                                   c.get("period_s", 2e-5), c.get("num_pulses", 100))

        # DC Measure (approximate with repeated short pulses)
        if "DC Measure" in cfg:
            c = cfg["DC Measure"]
            dv = float(c.get("dc_voltage", 0.2))
            capture_s = float(c.get("capture_s", 0.02))
            dt_s = float(c.get("dt_s", 1e-3))
            n = max(1, int(round(capture_s / max(dt_s, 1e-6))))
            fr = self.fast_read(read_v=dv, duration_pulses=n, width_s=dt_s, period_s=dt_s,
                                source_channel=bias_channel, v_meas_range=2.0, i_meas_range=200e-6)
            results["DC Measure"] = fr

        return results

if __name__ == "__main__":
    # pmu = Keithley4200A_PMUDualChannel("192.168.0.10:8888|PMU1")

    # pmu = Keithley4200A_PMUDualChannel("192.168.0.10:8888|PMU1")
    # df = pmu.test_pulse_with_pretrigger(amplitude_v=0.2, width_s=50e-6, period_s=200e-6, num_pulses=5, source_channel=1)
    # print(df.head())
    # pmu.close()

    # Example A: upload and run a simple full-ARB (if supported by firmware)
    pmu = Keithley4200A_PMUDualChannel("192.168.0.10:8888|PMU1")

    try:
        levels = [0.0, 0.05, 0.1, 0.15, 0.2, 0.15, 0.1, 0.05, 0.0]
        fname = pmu.create_and_upload_arb(chan=1, levels=levels, time_per_point=1e-5)
        df_arb = pmu.run_arb_waveform(chan=1, fname=fname, mode='full', trig_source=0, trig_output=True, burst_count=1)
        print("Full ARB rows:", len(df_arb))
        print(df_arb.head())
    except Exception as e:
        print("Full ARB path failed:", e)

    # Example B: build and run a segment ARB approximating a small pulse train
    #try:
    volts = [0.0, 0.2, 0.2, 0.0, 0.2, 0.2, 0.0]  # flat segments
    times = [2e-6, 1e-6, 1e-6, 2e-6, 1e-6, 1e-6, 2e-6]
    s, p, t, trig, rel = pmu.build_segments_from_volts_times(volts, times)
    df_seg = pmu.run_segment_arb(chan=1, startvals=s, stopvals=p, timevals=t, triggervals=trig, output_relays=rel,
                                    trig_source=0, trig_output=True, v_meas_range=2.0, i_meas_range=1e-3)
    print("Segment ARB rows:", len(df_seg))
    print(df_seg.head())
    # except Exception as e:
    #     print("Segment ARB path failed:", e)

    pmu.close()
