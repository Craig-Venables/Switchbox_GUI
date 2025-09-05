


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
import numpy as np
import pandas as pd



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



class Keithley4200A_PMUController:
    """Standalone PMU controller for the Keithley 4200A using the LPT server.

    Usage:
        pmu = Keithley4200A_PMUController("192.168.0.10:8888|PMU1-CH1")
        pmu.configure_pulse(...)
        df = pmu.run_fixed_amplitude_pulses(...)
    """

    def __init__(self, address: str):
        """Connect to a PMU channel.

        Address examples:
          - "192.168.0.10:8888|PMU1-CH1"
          - "192.168.0.10:8888|PMU1-CH2"
        """
        # Parse address
        if "|" in address:
            addr, instr_sel = address.split("|", 1)
            instr_sel = instr_sel.strip().upper()
        else:
            addr, instr_sel = address, "PMU1-CH1"

        if ":" in addr:
            ip, port = addr.split(":", 1)
            self._ip = ip
            self._port = int(port)
        else:
            self._ip = addr
            self._port = 8888

        # Parse instrument + channel
        if "CH" in instr_sel:
            card = instr_sel.split("-")[0]   # e.g. "PMU1"
            ch = int(instr_sel.split("CH")[-1])  # 1/2
        else:
            card, ch = instr_sel, 1

        self.card = card
        self.channel = ch  # keep channel as 1‑ or 2‑based (VALID for LPT API)

        # Proxies
        self.lpt = Proxy(self._ip, self._port, "lpt")
        self.param = Proxy(self._ip, self._port, "param")

        # Initialize tester
        self.lpt.initialize()
        self.lpt.tstsel(1)
        self.lpt.devint()
        self.lpt.dev_abort()

        self.card_id = self.lpt.getinstid(self.card)

        self._configured = False
        print(f"[PMU] Connected to {self.card} channel {self.channel}, ID={self.card_id}")

    # -----------------------
    # PMU-Specific Functions
    # -----------------------
    def configure_pulse(self, v_src_range, v_meas_range_type, v_meas_range,
                        i_meas_range_type, i_meas_range,
                        v_limit, i_limit, power_limit,
                        start_pct, stop_pct, num_pulses,
                        period, delay, width, rise, fall,
                        load_ohm):
        """Configure the pulse generator and measurement settings"""

        self.lpt.rpm_config(self.card_id, self.channel,
                            self.param.KI_RPM_PATHWAY,
                            self.param.KI_RPM_PULSE)

        self.lpt.pulse_meas_sm(self.card_id, self.channel,
                               acquire_type=0,
                               acquire_meas_v_ampl=1,
                               acquire_meas_v_base=0,
                               acquire_meas_i_ampl=1,
                               acquire_meas_i_base=0,
                               acquire_time_stamp=1,
                               llecomp=0)

        self.lpt.pulse_ranges(self.card_id, self.channel,
                              v_src_range,
                              v_meas_range_type, v_meas_range,
                              i_meas_range_type, i_meas_range)

        self.lpt.pulse_limits(self.card_id, self.channel,
                              v_limit, i_limit, power_limit)

        self.lpt.pulse_meas_timing(self.card_id, self.channel,
                                   start_pct, stop_pct, int(num_pulses))

        self.lpt.pulse_source_timing(self.card_id, self.channel,
                                     period, delay, width, rise, fall)

        self.lpt.pulse_load(self.card_id, self.channel, load_ohm)

        self._configured = True

    def set_pulse_source_timing(self, period: float, delay: float, width: float, rise: float, fall: float):
        self.lpt.pulse_source_timing(self.card_id, self.channel, period, delay, width, rise, fall)

    def set_pulse_meas_timing(self, start_pct: float, stop_pct: float, num_pulses: int):
        self.lpt.pulse_meas_timing(self.card_id, self.channel, start_pct, stop_pct, int(num_pulses))

    def set_pulse_limits(self, v_limit: float, i_limit: float, power_limit: float):
        self.lpt.pulse_limits(self.card_id, self.channel, v_limit, i_limit, power_limit)

    def set_ranges(self, v_src_range: float, v_meas_range_type: int, v_meas_range: float,
                   i_meas_range_type: int, i_meas_range: float):
        self.lpt.pulse_ranges(self.card_id, self.channel,
                              v_src_range, v_meas_range_type, v_meas_range,
                              i_meas_range_type, i_meas_range)

    def set_load(self, load_ohm: float):
        self.lpt.pulse_load(self.card_id, self.channel, load_ohm)

    def _ensure_configured_with_defaults(self):
        if getattr(self, "_configured", False):
            return
        # Conservative defaults; run methods will override timing per-call
        self.configure_pulse(
            v_src_range=10.0,
            v_meas_range_type=0, v_meas_range=10.0,
            i_meas_range_type=0, i_meas_range=0.2,
            v_limit=5.0, i_limit=1.0, power_limit=10.0,
            start_pct=0.1, stop_pct=0.9, num_pulses=1,
            period=20e-6, delay=1e-7, width=10e-6, rise=1e-7, fall=1e-7,
            load_ohm=1e6,
        )

    def arm_single_pulse(self, amplitude_v: float, base_v: float = 0.0):
        self.lpt.pulse_sweep_linear(self.card_id, self.channel,
                                    self.param.PULSE_AMPLITUDE_SP,
                                    float(amplitude_v), float(amplitude_v), float(base_v))
        self.lpt.pulse_output(self.card_id, self.channel, 1)

    def exec_and_fetch(self, as_dataframe: bool = True, timeout: float = 10.0):
        self.lpt.pulse_exec(self.param.PULSE_MODE_SIMPLE)

        t0 = time.time()
        while True:
            status, _ = self.lpt.pulse_exec_status()
            if status != self.param.PMU_TEST_STATUS_RUNNING:
                break
            if time.time() - t0 > timeout:
                self.lpt.dev_abort()
                raise TimeoutError("PMU pulse execution timed out")
            time.sleep(0.05)

        buf_size = self.lpt.pulse_chan_status(self.card_id, self.channel)
        v, i, ts, statuses = self.lpt.pulse_fetch(self.card_id, self.channel, 0, buf_size - 1)
        print(v, i, ts, statuses)
        

        if as_dataframe:
            return pd.DataFrame({
                "V (V)": v,
                "I (A)": i,
                "t (s)": ts,
                "Status": statuses,
            })

        return v, i, ts, statuses

    # -----------------------
    # Trigger configuration helpers
    # -----------------------
    def set_trigger_source(self, source: int) -> None:
        """Set PMU trigger source.

        Sources (per lpt):
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
        """Set trigger polarity (0 or 1)."""
        try:
            self.lpt.pulse_trig_polarity(self.card_id, int(polarity))
        except Exception:
            pass

    def set_trigger_output(self, state: bool) -> None:
        """Enable or disable the PMU trigger output line."""
        try:
            self.lpt.pulse_trig_output(self.card_id, 1 if state else 0)
        except Exception:
            pass

    def set_burst_count(self, count: int) -> None:
        """Set burst count for the pulse output (unsigned int)."""
        try:
            self.lpt.pulse_burst_count(self.card_id, self.channel, int(count))
        except Exception:
            pass

    # --------------- High-level wrappers ---------------
    def run_fixed_amplitude_pulses(self, amplitude_v: float, base_v: float, num_pulses: int,
                                   width_s: float, period_s: float,
                                   rise_s: float = 1e-7, fall_s: float = 1e-7,
                                   as_dataframe: bool = True):
        self._ensure_configured_with_defaults()
        self.set_pulse_source_timing(period_s, 1e-7, width_s, rise_s, fall_s)
        self.set_pulse_meas_timing(0.1, 0.9, num_pulses)
        self.lpt.pulse_sweep_linear(self.card_id, self.channel,
                                    self.param.PULSE_AMPLITUDE_SP,
                                    float(amplitude_v), float(amplitude_v), float(base_v))
        self.lpt.pulse_output(self.card_id, self.channel, 1)
        return self.exec_and_fetch(as_dataframe=as_dataframe)

    def run_amplitude_sweep(self, start_v: float, stop_v: float, step_v: float,
                            base_v: float, width_s: float, period_s: float,
                            num_pulses: int | None = None,
                            as_dataframe: bool = True):
        self._ensure_configured_with_defaults()
        if num_pulses is None:
            num_pulses = int(abs(stop_v - start_v) / abs(step_v)) + 1
        self.set_pulse_source_timing(period_s, 1e-7, width_s, 1e-7, 1e-7)
        self.set_pulse_meas_timing(0.1, 0.9, num_pulses)
        self.lpt.pulse_sweep_linear(self.card_id, self.channel,
                                    self.param.PULSE_AMPLITUDE_SP,
                                    float(start_v), float(stop_v), float(step_v))
        self.lpt.pulse_output(self.card_id, self.channel, 1)
        return self.exec_and_fetch(as_dataframe=as_dataframe)

    def run_bitstring(self, pattern: str, amplitude_v: float, base_v: float,
                      width_s: float, period_s: float,
                      rise_s: float = 1e-7, fall_s: float = 1e-7,
                      as_dataframe: bool = True):
        self._ensure_configured_with_defaults()
        dfs = []
        for ch in str(pattern):
            level = amplitude_v if ch == '1' else base_v
            self.set_pulse_source_timing(period_s, 1e-7, width_s, rise_s, fall_s)
            self.set_pulse_meas_timing(0.1, 0.9, 1)
            self.arm_single_pulse(level, base_v)
            df = self.exec_and_fetch(as_dataframe=True)
            dfs.append(df)
        return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

    def output(self, enable: bool):
        self.lpt.pulse_output(self.card_id, self.channel, 1 if enable else 0)

    def close(self):
        try:
            self.output(False)
        except Exception:
            pass
        try:
            self.lpt.devint()
            self.lpt.tstdsl()
        except Exception:
            pass

    def is_connected(self) -> bool:
        return self.card_id is not None and self.lpt is not None

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
        self.lpt.tstsel(1)
        self.lpt.devint()
        self.lpt.dev_abort()

        self.card_id = self.lpt.getinstid(self.card)
        self._configured = False

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

    def _ensure_config(self, acquire_time_stamp: int = 1) -> None:
        if not self._configured:
            self._configure_both_channels(acquire_time_stamp=acquire_time_stamp)

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
          the typical wiring (manual figure with both channels connected).
        - Returns a pandas DataFrame with columns: t (s), V (V), I (A), R (Ohm).
        """
        self._ensure_config(acquire_time_stamp=acquire_time_stamp)

        # Optionally force fixed ranges (helps avoid bogus overflow values on some setups)
        if force_fixed_ranges:
            for ch in self.channels:
                # v_range_type=1 (fixed), i_range_type=1 (fixed)
                self.lpt.pulse_ranges(self.card_id, ch,
                                      v_src_range=max(abs(amplitude_v), v_meas_range),
                                      v_range_type=1, v_range=float(v_meas_range),
                                      i_range_type=1, i_range=float(i_meas_range))

        # Apply trigger settings if provided
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
        #for ch in self.channels:
         #   self.lpt.pulse_ranges(self.card_id, ch,v_src_range=max(abs(amplitude_v), v_meas_range),i_range_type=0)

        # Update timing on both channels
        for ch in self.channels:
            self.lpt.pulse_source_timing(self.card_id, ch, period_s, 1e-7, width_s, 1e-7, 1e-7)
            self.lpt.pulse_meas_timing(self.card_id, ch, float(meas_start_pct), float(meas_stop_pct), int(num_pulses))

        # Program setpoints: source channel to requested amplitude, other at 0 V if requested
        other_channel = 2 if int(source_channel) == 1 else 1
        self.lpt.pulse_sweep_linear(self.card_id, int(source_channel),
                                    self.param.PULSE_AMPLITUDE_SP,
                                    float(amplitude_v), float(amplitude_v), float(base_v))
        if hold_other_at_zero:
            self.lpt.pulse_sweep_linear(self.card_id, other_channel,
                                        self.param.PULSE_AMPLITUDE_SP,
                                        0.0, 0.0, 0.0)

        # Enable outputs on both channels
        for ch in self.channels:
            self.lpt.pulse_output(self.card_id, ch, 1)

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
    pmu = Keithley4200A_PMUDualChannel("192.168.0.10:8888|PMU1")

    # --- Memristor examples ---

    # # 1) Low-stress read at 0.2 V (high-R friendly)
    # read_summary, read_raw = pmu.memr_read(read_v=0.2, expected_res_ohm=100_000.0, shots=5,
    #                                        width_s=200e-6, period_s=500e-6)
    # print("READ summary:")
    # print(read_summary)

    # # 2) Quasi-static IV on a few points
    # iv_summary = pmu.memr_iv(voltages=[0.1, 0.2, 0.5, 1.0], expected_res_ohm=100_000.0,
    #                           shots=3, width_s=200e-6, period_s=500e-6)
    # print("IV summary:")
    # print(iv_summary)

    wrap = MemristorMeasurements(pmu)

    # Pulse IV sweep
    piv = wrap.pulse_iv_sweep(levels=[0.0, 0.1, 0.2, 0.5, 1.0], width_s=200e-6, period_s=500e-6,
                               v_meas_range=2.0, i_meas_range=20e-6)
    print("Pulse IV summary:")
    print(piv["summary"])

    # Pulse width sweep at 0.5 V
    pws = wrap.pulse_width_sweep(voltage_v=0.5, widths_s=[50e-6, 100e-6, 200e-6, 500e-6],
                                 v_meas_range=2.0, i_meas_range=20e-6)
    print("Pulse width summary:")
    print(pws["summary"])

    # Fast read at 0.2 V (as fast as possible within settings)
    fr = wrap.fast_read(read_v=0.2, duration_pulses=50, width_s=50e-6, period_s=100e-6,
                        v_meas_range=2.0, i_meas_range=200e-6)
    print("Fast read sample rows:")
    print(fr["raw_ch1"].head())

    # Perturb/relax: bias CH1, pulse CH2, fetch both channels
    pr = wrap.perturb_measure(bias_v=0.2, pulse_v=5.0, width_s=10e-6, period_s=50e-6,
                              delay_s=5e-6, num_pulses=3,
                              v_meas_range=2.0, i_meas_range=200e-6, fetch_both=True)
    print("Perturb/Relax (CH1) first rows:")
    print(pr["raw_ch1"].head())
    print("Perturb/Relax (CH2) first rows:")
    print(pr["raw_ch2"].head())

    # Example: run JSON-defined modes (two-channel bias/pulse), using PMU_modes.json
    modes = wrap.run_modes_from_json(config_path=str(Path(__file__).resolve().parents[2] / "PMU_modes.json"),
                                     bias_v=0.2, bias_channel=1, aux_channel=2)
    for name, res in modes.items():
        print(f"Mode: {name}")
        if "summary" in res and not res["summary"].empty:
            print(res["summary"].head())
        else:
            print("(no summary; see raw data)")

    pmu.close()
