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
from Equipment.SMU_AND_PMU.ProxyClass import RemoteException


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
        try:
            for ch in self.channels:
                try:
                    self.lpt.pulse_output(self.card_id, int(ch), 0)
                except Exception:
                    pass
        except Exception:
            pass
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
        try:
            self.lpt.pulse_trig_source(self.card_id, 0)
        except Exception:
            pass

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

    
    # ------------------------------
    # Segment-Arbitrary Pulse Engine
    # ------------------------------
    def _compute_rate(self, total_time_s: float, max_pts: int) -> tuple[int, int]:
        """Mirror of ret_getRate from C: choose sample rate to keep points <= max_pts.

        Returns (used_rate_hz, estimated_points).
        """
        default_rate = 200_000_000  # 200 MHz
        max_divider = 1000
        min_rate = default_rate // max_divider

        if max_pts > 30000:
            max_pts = 30000

        used_rate = -1
        used_pts = 0

        n = 1
        while n < max_divider * 2:
            rate = int(default_rate / n)
            pts = int(total_time_s * rate + 2)
            if pts < max_pts:
                used_rate = rate
                used_pts = pts
                break
            n += 1

        if used_rate < min_rate:
            return (-1, 0)
        return (used_rate, used_pts)

    def _define_segments_arrays(self,
                                volts: list[float],
                                times: list[float],
                                bias_v: float) -> tuple[list[float], list[float], list[float], list[float], list[float], list[float], list[int], list[int], list[int], float]:
        """Construct arrays for seg_arb_sequence from boundary volt points and segment times.

        Returns:
          (fstartv, fstopv, mstartv, mstopv, measstart, measstop, trig, ssrctrl, meastypes, total_time)
        """
        if len(volts) != len(times) + 1:
            raise ValueError("volts_size must be times_size + 1")
        numpts = len(times)
        fstartv = [0.0] * numpts
        fstopv = [0.0] * numpts
        mstartv = [0.0] * numpts
        mstopv = [0.0] * numpts
        measstart = [0.0] * numpts
        measstop = [1.0] * numpts
        segtime = [0.0] * numpts
        trig = [0] * numpts
        # SSR control: 1 enables measurement and route settings per segment
        ssrctrl = [1] * numpts
        meastypes = [1.0] * numpts  # 1.0 = spot/segment meas window in LPT wrapper

        ttime = 0.0
        for i in range(numpts):
            fstartv[i] = float(volts[i])
            fstopv[i] = float(volts[i + 1])
            segtime[i] = float(times[i])
            ttime += segtime[i]
            # LPT seg_arb_sequence expects normalized window [0..1]; use 20%-80% like example
            measstart[i] = 0.2
            measstop[i] = 0.8
            meastypes[i] = 1.0
            mstartv[i] = float(bias_v)
            mstopv[i] = float(bias_v)
            trig[i] = 1 if i == 0 else 0

        return (fstartv, fstopv, mstartv, mstopv, measstart, measstop, trig, ssrctrl, meastypes, ttime)

    def pulse_train_pulse_ilimit(self,
                                 volts: list[float],
                                 times: list[float],
                                 force_ch: int = 1,
                                 measure_ch: int = 2,
                                 force_v_range: float = 10.0,
                                 force_i_range: float = 0.01,
                                 iF_limit: float = 0.0,
                                 iM_limit: float = 0.0,
                                 measure_v_range: float = 10.0,
                                 measure_i_range: float = 0.01,
                                 max_pts: int = 10000,
                                 measure_bias: float = 0.0,
                                 sample_rate_hz: int | None = None) -> dict:
        """Python port of PulseTrain_pulse_ilimitNK.

        - Accepts boundary `volts` of size N and per-segment `times` of size N-1.
        - Programs seg-arb sequences on force and measure channels and executes once.
        - Returns dict with raw arrays: VF, IF, VM, IM, T (numpy arrays) and status.
        """
        # Validate sizes
        vsize = len(volts)
        tsize = len(times)
        if vsize < 4 or vsize != tsize + 1:
            raise ValueError("volts_size must be times_size + 1 and >= 4")

        # Build segment arrays and total time
        (fstartv, fstopv, mstartv, mstopv, measstart, measstop,
         trig, ssrctrl, meastypes, total_time) = self._define_segments_arrays(volts, times, measure_bias)

        # Compute sample rate
        if sample_rate_hz is None:
            used_rate, allocate_pts = self._compute_rate(total_time, int(max_pts))
            if used_rate <= 0:
                raise RuntimeError("Failed to compute a valid sample rate for seg-arb")
        else:
            used_rate = int(sample_rate_hz)

        # Initialize and configure PMU for seg-arb
        try:
            # Pathway to RPM PULSE on both channels
            self.lpt.rpm_config(self.card_id, int(force_ch), self.param.KI_RPM_PATHWAY, self.param.KI_RPM_PULSE)
            if int(measure_ch) != int(force_ch) and int(measure_ch) > 0:
                self.lpt.rpm_config(self.card_id, int(measure_ch), self.param.KI_RPM_PATHWAY, self.param.KI_RPM_PULSE)
        except Exception:
            pass

        # Optional advanced/seg-arb init if available
        try:
            # Segment-ARB mode is 1 per LPT examples
            self.lpt.pg2_init(self.card_id, 1)
        except Exception:
            pass

        # Compliance/limits via pulse_ranges and loads
        # Force channel
        try:
            self.lpt.pulse_load(self.card_id, int(force_ch), 1e6)
        except Exception:
            pass
        self.lpt.pulse_ranges(self.card_id, int(force_ch),
                              float(force_v_range), self.param.PULSE_MEAS_FIXED,
                              float(force_v_range), self.param.PULSE_MEAS_FIXED,
                              float(force_i_range))
        try:
            self.lpt.pulse_burst_count(self.card_id, int(force_ch), 1)
        except Exception:
            pass
        self.lpt.pulse_output(self.card_id, int(force_ch), 1)

        # Measure channel
        if int(measure_ch) != int(force_ch) and int(measure_ch) > 0:
            try:
                self.lpt.pulse_load(self.card_id, int(measure_ch), 50.0)
            except Exception:
                pass
            self.lpt.pulse_ranges(self.card_id, int(measure_ch),
                                  float(measure_v_range), self.param.PULSE_MEAS_FIXED,
                                  float(measure_v_range), self.param.PULSE_MEAS_FIXED,
                                  float(measure_i_range))
            try:
                self.lpt.pulse_burst_count(self.card_id, int(measure_ch), 1)
            except Exception:
                pass
            self.lpt.pulse_output(self.card_id, int(measure_ch), 1)

        # Program sample rate
        try:
            self.lpt.pulse_sample_rate(self.card_id, int(used_rate))
        except Exception:
            pass

        # Define sequences
        numpts = tsize
        self.lpt.seg_arb_sequence(self.card_id, int(force_ch), 1,
                                  int(numpts),
                                  list(fstartv), list(fstopv),
                                  list(times),
                                  [int(x) for x in trig],
                                  [int(x) for x in ssrctrl],
                                  [float(x) for x in meastypes],
                                  [float(x) for x in measstart],
                                  [float(x) for x in measstop])

        if int(measure_ch) != int(force_ch) and int(measure_ch) > 0:
            self.lpt.seg_arb_sequence(self.card_id, int(measure_ch), 1,
                                      int(numpts),
                                      list(mstartv), list(mstopv),
                                      list(times),
                                      [int(x) for x in trig],
                                      [int(x) for x in ssrctrl],
                                      [float(x) for x in meastypes],
                                      [float(x) for x in measstart],
                                      [float(x) for x in measstop])

        # Select sequence index 1, run once
        try:
            self.lpt.seg_arb_waveform(self.card_id, int(force_ch), 1, [1], [1])
            if int(measure_ch) != int(force_ch) and int(measure_ch) > 0:
                self.lpt.seg_arb_waveform(self.card_id, int(measure_ch), 1, [1], [1])
        except Exception:
            pass

        # Execute and wait
        try:
            self.lpt.pulse_exec(0)
        except Exception:
            # fallback to simple mode value if needed
            try:
                self.lpt.pulse_exec(self.param.PULSE_MODE_SIMPLE)
            except Exception:
                self.lpt.pulse_exec(0)

        t0 = time.time()
        timeout_s = max(2.0, total_time * 10)
        while True:
            status, elapsed = self.lpt.pulse_exec_status()
            if status != self.param.PMU_TEST_STATUS_RUNNING:
                break
            if (time.time() - t0) > timeout_s:
                self.lpt.dev_abort()
                raise TimeoutError("PMU seg-arb execution timed out")
            time.sleep(0.02)

        # Fetch results
        def _fetch(ch: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
            try:
                buf_size = int(self.lpt.pulse_chan_status(self.card_id, int(ch)))
                v, i, t, s = self.lpt.pulse_fetch(self.card_id, int(ch), 0, max(0, buf_size - 1))
                return (np.asarray(v, dtype=float),
                        np.asarray(i, dtype=float),
                        np.asarray(t, dtype=float),
                        np.asarray(s, dtype=int))
            except Exception:
                return (np.array([], float), np.array([], float), np.array([], float), np.array([], int))

        VF, IF, T, ST_F = _fetch(int(force_ch))
        VM, IM, Tm, ST_M = _fetch(int(measure_ch)) if (int(measure_ch) != int(force_ch) and int(measure_ch) > 0) else (np.array([], float), np.array([], float), np.array([], float), np.array([], int))

        # Use force time if measure empty
        if T.size == 0 and Tm.size > 0:
            T = Tm

        return {
            "VF": VF,
            "IF": IF,
            "VM": VM,
            "IM": IM,
            "T": T,
            "StatusF": ST_F,
            "StatusM": ST_M,
            "rate_hz": used_rate,
            "total_time_s": total_time,
        }

    def run_pulse_train(self,
                        volts: list[float],
                        times: list[float],
                        **kwargs) -> dict:
        """Convenience wrapper to execute a seg-arb pulse train defined by `volts`/`times`."""
        return self.pulse_train_pulse_ilimit(volts=volts, times=times, **kwargs)

    # ---------------------------------------------
    # High-level PulseTrain builder + analysis (C port)
    # ---------------------------------------------
    def build_pulse_train(self,
                          rise_time: float,
                          reset_v: float,
                          reset_width: float,
                          reset_delay: float,
                          meas_v: float,
                          meas_width: float,
                          meas_delay: float,
                          set_fall_time: float,
                          set_delay: float,
                          pulse_sequence: str,
                          num_pulses: int,
                          ratio: float = 0.4) -> tuple[list[float], list[float], list[tuple[float, float]], tuple[float, float]]:
        """Port of PMU_PulseTrain segment construction.

        Returns (volts, times, meas_windows, off_window)
        - volts: list of boundary voltages (size N)
        - times: list of segment durations (size N-1)
        - meas_windows: list of (tmin, tmax) pairs for each probe measurement window,
                        length num_pulses+2 (start, after each pulse, final)
        - off_window: (tmin, tmax) for baseline/off current near beginning
        """
        if len(pulse_sequence) != num_pulses:
            raise ValueError("pulse_sequence length must equal num_pulses")

        volts: list[float] = []
        times: list[float] = []

        ttime = 0.0

        # Baseline before first measurement
        times.append(float(reset_delay)); volts.append(0.0); ttime += times[-1]
        times.append(float(rise_time)); volts.append(0.0); ttime += times[-1]

        # First measurement pulse at meas_v
        meas_windows: list[tuple[float, float]] = []
        meas_min = ttime + ratio * float(meas_width)
        meas_max = ttime + 0.9 * float(meas_width)
        meas_windows.append((meas_min, meas_max))
        times.append(float(meas_width)); volts.append(float(meas_v)); ttime += times[-1]
        times.append(float(rise_time)); volts.append(float(meas_v)); ttime += times[-1]
        times.append(float(meas_delay)); volts.append(float(meas_v)); ttime += times[-1]
        times.append(float(rise_time)); volts.append(float(meas_v)); ttime += times[-1]
        times.append(float(rise_time)); volts.append(float(meas_v)); ttime += times[-1]

        # Off current window near beginning
        off_min = (times[0] - float(reset_delay)) + ratio * float(reset_delay)
        # But since we already advanced, compute using absolute ttime values per C intent:
        # After starting, off window is inside the first reset_delay segment:
        off_min = 0.0 + ratio * float(reset_delay)
        off_max = 0.0 + 0.9 * float(reset_delay)
        off_window = (off_min, off_max)

        # Repeated pulses according to sequence
        sequence_index = 0
        for _ in range(int(num_pulses)):
            # small rise segment at meas_v
            times.append(float(rise_time)); volts.append(float(meas_v)); ttime += times[-1]
            # main pulse width at reset_v if '1' else at meas_v
            times.append(float(reset_width)); volts.append(float(reset_v if pulse_sequence[sequence_index] == '1' else meas_v)); ttime += times[-1]
            # fall segment
            times.append(float(set_fall_time)); volts.append(float(reset_v if pulse_sequence[sequence_index] == '1' else meas_v)); ttime += times[-1]
            # next measurement window
            meas_min = ttime + ratio * float(meas_width)
            meas_max = ttime + 0.9 * float(meas_width)
            meas_windows.append((meas_min, meas_max))
            # measurement segment (meas_width + reset_delay) at meas_v
            times.append(float(meas_width + reset_delay)); volts.append(float(meas_v)); ttime += times[-1]
            sequence_index += 1

        # Final measurement pulse
        times.append(float(rise_time)); volts.append(float(meas_v)); ttime += times[-1]
        meas_min = ttime + ratio * float(meas_width)
        meas_max = ttime + 0.9 * float(meas_width)
        meas_windows.append((meas_min, meas_max))
        times.append(float(meas_width)); volts.append(float(meas_v)); ttime += times[-1]
        times.append(float(set_fall_time)); volts.append(float(meas_v)); ttime += times[-1]
        times.append(float(meas_delay)); volts.append(0.0); ttime += times[-1]
        # two short zero segments (per C code)
        times.append(500e-9); volts.append(0.0); ttime += times[-1]
        times.append(500e-9); volts.append(0.0); ttime += times[-1]

        # Convert from interleaved scheme (C builds boundary volts alongside times)
        # Our lists currently aligned as: for each append to times we also appended corresponding volts for end of that segment.
        # We need boundary style: volts_boundary of size len(times)+1
        volts_boundary: list[float] = []
        if len(volts) != len(times):
            raise RuntimeError("Internal build mismatch volts/times sizes")
        # Rebuild boundary so that each segment i goes from volts_boundary[i] to volts_boundary[i+1]
        # Interpret volts[] entries as the segment end value; start value is previous end.
        for i, v_end in enumerate(volts):
            if i == 0:
                # assume starting at same as first end
                volts_boundary.append(float(v_end))
            volts_boundary.append(float(v_end))

        return (volts_boundary, times, meas_windows, off_window)

    def execute_pulse_train_with_analysis(self,
                                          rise_time: float,
                                          reset_v: float,
                                          reset_width: float,
                                          reset_delay: float,
                                          meas_v: float,
                                          meas_width: float,
                                          meas_delay: float,
                                          set_fall_time: float,
                                          set_delay: float,
                                          pulse_sequence: str,
                                          num_pulses: int,
                                          i_range: float,
                                          max_points: int = 10000,
                                          force_ch: int = 1,
                                          measure_ch: int = 2) -> dict:
        """Build the pulse train, execute, and compute probe resistances like C code.

        Returns dict with:
          - setV, setI for each probe window (numpy arrays length num_pulses+2)
          - resetR: probe resistances per window (Ohm)
          - PulseTimes: mid-times of probe windows
          - raw: output from pulse_train_pulse_ilimit
        """
        volts, times, meas_windows, off_window = self.build_pulse_train(
            rise_time, reset_v, reset_width, reset_delay, meas_v, meas_width,
            meas_delay, set_fall_time, set_delay, pulse_sequence, num_pulses)

        force_v_range = max(abs(reset_v), abs(meas_v))
        measure_v_range = max(abs(reset_v), abs(meas_v))

        raw = self.pulse_train_pulse_ilimit(
            volts=volts,
            times=times,
            force_ch=force_ch,
            measure_ch=measure_ch,
            force_v_range=float(force_v_range),
            force_i_range=float(i_range),
            measure_v_range=float(measure_v_range),
            measure_i_range=float(i_range),
            max_pts=int(max_points),
            measure_bias=0.0,
        )

        VF = raw["VF"]; IF = raw["IF"]; VM = raw["VM"]; IM = raw["IM"]; T = raw["T"]
        # Prefer measure channel time if available
        TT = T
        if IM.size and VF.size and IM.size == IF.size:
            # likely aligned; keep T
            pass

        def avg_in_window(arr_t: np.ndarray, arr_y: np.ndarray, tmin: float, tmax: float) -> float:
            if arr_t.size == 0 or arr_y.size == 0:
                return float("nan")
            m = (arr_t >= tmin) & (arr_t <= tmax)
            if not np.any(m):
                return float("nan")
            return float(np.nanmean(arr_y[m]))

        # Baseline OFF current
        i_off = avg_in_window(TT, IM if IM.size else IF, off_window[0], off_window[1])

        nprobe = len(meas_windows)
        setV = np.zeros(nprobe, dtype=float)
        setI = np.zeros(nprobe, dtype=float)
        resetR = np.zeros(nprobe, dtype=float)
        pulse_times = np.zeros(nprobe, dtype=float)

        for idx, (tmin, tmax) in enumerate(meas_windows):
            v_val = avg_in_window(TT, VF, tmin, tmax)
            i_val = avg_in_window(TT, IM if IM.size else IF, tmin, tmax)
            setV[idx] = v_val
            setI[idx] = i_val
            # Convert to resistance with baseline subtraction
            if np.isfinite(i_val) and np.isfinite(i_off):
                cur = i_val - i_off
                if cur == 0.0:
                    r_val = np.nan
                else:
                    r_val = abs(float(meas_v) / cur)
                # clip like C
                r_max = 1e4 / float(i_range)
                if np.isfinite(r_val):
                    resetR[idx] = min(r_val, r_max)
                else:
                    resetR[idx] = np.nan
            else:
                resetR[idx] = np.nan
            pulse_times[idx] = 0.5 * (tmin + tmax)

        return {
            "setV": setV,
            "setI": setI,
            "resetR": resetR,
            "PulseTimes": pulse_times,
            "raw": raw,
        }

if __name__ == "__main__":
    
    pmu = Keithley4200A_PMUDualChannel("192.168.0.10:8888|PMU1")

    # # Build / run like the C PMU_PulseTrain
    # result = pmu.execute_pulse_train_with_analysis(
    #     rise_time=30e-9,
    #     reset_v=4.0,
    #     reset_width=1e-6,
    #     reset_delay=1e-6,
    #     meas_v=0.5,
    #     meas_width=2e-6,
    #     meas_delay=1e-6,
    #     set_fall_time=30e-9,
    #     set_delay=1e-6,              # included for parity; not separately used
    #     pulse_sequence="10101",       # length must equal num_pulses
    #     num_pulses=5,
    #     i_range=1e-2,
    #     max_points=10000,
    #     force_ch=1,
    #     measure_ch=2,
    # )

    # print(result["resetR"], result["PulseTimes"])
    res = pmu.run_pulse_train(
    volts=[0.0, 0.0, 0.5, 0.5, 0.5],  # boundary voltages (N)
    times=[1e-6, 3e-8, 2e-6, 1e-6],   # segment durations (N-1)
    force_ch=1,
    measure_ch=2,
    force_v_range=10.0,
    force_i_range=1e-2,
    measure_v_range=10.0,
    measure_i_range=1e-2,
    max_pts=10000,
    measure_bias=0.0,
    )

    print(res)