


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
    """Dedicated helper for PMU operation on 4200A using LPT.

    Construct with address like '192.168.0.10:8888|PMU1-CH1'.
    """

    def __init__(self, address: str) -> None:
        """Connect to the PMU on the given address.

        Address examples:
          - "192.168.0.10:8888|PMU1-CH1"
          - "192.168.0.10|PMU1-CH2"
          - "192.168.0.10:8888" (defaults to PMU1-CH1)
        """
        base = Keithley4200AController(address if "|" in address else address + "|PMU1-CH1")
        if not base._is_pmu:
            raise ValueError("PMUController requires a PMU address like '...|PMU1-CH1'")

        self._base = base
        self.lpt = base.lpt
        self.param = base.param
        self._card_id = base._instr_id
        self._chan = base._pmu_channel or 1

        # Set conservative safe defaults within 4200A PMU limits
        self.configure_pulse(
            v_src_range=5.0,
            v_meas_range_type=0, v_meas_range=5.0,
            i_meas_range_type=0, i_meas_range=0.1,
            v_limit=5.0, i_limit=0.1, power_limit=1.0,
            start_pct=0.1, stop_pct=0.9, num_pulses=1,
            period=20e-6, delay=1e-7, width=10e-6, rise=1e-7, fall=1e-7,
            load_ohm=1e6,
        )

    # -----------------------
    # PMU-Specific Functions
    # -----------------------
    def configure_pulse(self, v_src_range, v_meas_range_type, v_meas_range,
                        i_meas_range_type, i_meas_range,
                        v_limit, i_limit, power_limit,
                        start_pct, stop_pct, num_pulses,
                        period, delay, width, rise, fall,
                        load_ohm):
        """Configure pulse parameters for this channel.

        This method keeps the configuration minimal and readable. Values are not
        validated here; use helper validate methods if needed before calling.
        """
        self.lpt.pg2_init(self._card_id, 0)
        self.lpt.rpm_config(self._card_id, self._chan,
                            self.param.KI_RPM_PATHWAY, self.param.KI_RPM_PULSE)
        self.lpt.pulse_meas_sm(self._card_id, self._chan, 0, 1, 0, 1, 0, 1, 1)
        self.lpt.pulse_ranges(self._card_id, self._chan, v_src_range,
                              v_meas_range_type, v_meas_range,
                              i_meas_range_type, i_meas_range)
        self.lpt.pulse_limits(self._card_id, self._chan, v_limit, i_limit, power_limit)
        self.lpt.pulse_meas_timing(self._card_id, self._chan,
                                   start_pct, stop_pct, int(num_pulses))
        self.lpt.pulse_source_timing(self._card_id, self._chan,
                                     period, delay, width, rise, fall)
        self.lpt.pulse_load(self._card_id, self._chan, load_ohm)

    # ---- Simple setters to adjust parts of config without resending all ----
    def set_pulse_source_timing(self, period: float, delay: float, width: float, rise: float, fall: float):
        self.lpt.pulse_source_timing(self._card_id, self._chan, period, delay, width, rise, fall)

    def set_pulse_meas_timing(self, start_pct: float, stop_pct: float, num_pulses: int):
        self.lpt.pulse_meas_timing(self._card_id, self._chan, start_pct, stop_pct, int(num_pulses))

    def set_pulse_limits(self, v_limit: float, i_limit: float, power_limit: float):
        self.lpt.pulse_limits(self._card_id, self._chan, v_limit, i_limit, power_limit)

    def set_ranges(self, v_src_range: float, v_meas_range_type: int, v_meas_range: float,
                   i_meas_range_type: int, i_meas_range: float):
        self.lpt.pulse_ranges(self._card_id, self._chan, v_src_range,
                              v_meas_range_type, v_meas_range,
                              i_meas_range_type, i_meas_range)

    def set_load(self, load_ohm: float):
        self.lpt.pulse_load(self._card_id, self._chan, load_ohm)

    def arm_single_pulse(self, amplitude_v: float, base_v: float = 0.0):
        """Prepare a single pulse with given amplitude.

        Use together with exec_and_fetch() to execute and read back data.
        """
        self.lpt.pulse_sweep_linear(self._card_id, self._chan,
                                    self.param.PULSE_AMPLITUDE_SP,
                                    float(amplitude_v), float(amplitude_v), float(base_v))
        self.lpt.pulse_output(self._card_id, self._chan, 1)

    def exec_and_fetch(self, as_dataframe: bool = True):
        """Execute the pulse sequence configured and fetch results."""
        self.lpt.pulse_exec(self.param.PULSE_MODE_SIMPLE)

        # Poll for completion
        timeout, t0 = 30.0, time.time()
        while True:
            status, _ = self.lpt.pulse_exec_status()
            if status != self.param.PMU_TEST_STATUS_RUNNING:
                break
            if time.time() - t0 > timeout:
                self.lpt.dev_abort()
                raise TimeoutError("PMU pulse execution timed out")
            time.sleep(0.05)

        # Fetch data
        buf_size = self.lpt.pulse_chan_status(self._card_id, self._chan)
        v, i, ts, statuses = self.lpt.pulse_fetch(self._card_id, self._chan, 0, max(0, buf_size - 1))

        if as_dataframe:
            df = pd.DataFrame({
                "t (s)": ts,
                "V (V)": v,
                "I (A)": i,
                "Status": statuses,
            })
            df["Channel"] = self._chan
            return df

        return v, i, ts, statuses

    # --------------- High-level wrappers ---------------
    def run_fixed_amplitude_pulses(self, amplitude_v: float, base_v: float, num_pulses: int,
                                   width_s: float, period_s: float,
                                   rise_s: float = 1e-7, fall_s: float = 1e-7,
                                   as_dataframe: bool = True):
        """Run a simple pulse train of identical pulses and fetch results."""
        self.set_pulse_source_timing(period_s, 1e-7, width_s, rise_s, fall_s)
        self.set_pulse_meas_timing(0.1, 0.9, num_pulses)
        self.lpt.pulse_sweep_linear(self._card_id, self._chan,
                                    self.param.PULSE_AMPLITUDE_SP,
                                    float(amplitude_v), float(amplitude_v), float(base_v))
        self.lpt.pulse_output(self._card_id, self._chan, 1)
        return self.exec_and_fetch(as_dataframe=as_dataframe)

    def run_amplitude_sweep(self, start_v: float, stop_v: float, step_v: float,
                            base_v: float, width_s: float, period_s: float,
                            num_pulses: int | None = None,
                            as_dataframe: bool = True):
        """Run a linear amplitude sweep and fetch results."""
        if num_pulses is None:
            try:
                num_pulses = int(abs(stop_v - start_v) / abs(step_v)) + 1
            except Exception:
                num_pulses = 1
        self.set_pulse_source_timing(period_s, 1e-7, width_s, 1e-7, 1e-7)
        self.set_pulse_meas_timing(0.1, 0.9, num_pulses)
        self.lpt.pulse_sweep_linear(self._card_id, self._chan,
                                    self.param.PULSE_AMPLITUDE_SP,
                                    float(start_v), float(stop_v), float(step_v))
        self.lpt.pulse_output(self._card_id, self._chan, 1)
        return self.exec_and_fetch(as_dataframe=as_dataframe)

    def run_bitstring(self, pattern: str, amplitude_v: float, base_v: float,
                      width_s: float, period_s: float,
                      rise_s: float = 1e-7, fall_s: float = 1e-7,
                      as_dataframe: bool = True):
        """Run a pulse pattern like "1011"; '1' applies amplitude_v, '0' applies base_v.

        Implementation executes one pulse at a time and concatenates results.
        """
        dfs = []
        for ch in str(pattern):
            level = amplitude_v if ch == '1' else base_v
            self.set_pulse_source_timing(period_s, 1e-7, width_s, rise_s, fall_s)
            self.set_pulse_meas_timing(0.1, 0.9, 1)
            self.arm_single_pulse(level, base_v)
            df = self.exec_and_fetch(as_dataframe=True)
            dfs.append(df if isinstance(df, pd.DataFrame) else pd.DataFrame({
                "t (s)": df[2], "V (V)": df[0], "I (A)": df[1], "Status": df[3]
            }))
        out = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
        return out if as_dataframe else (
            out.get("V (V)", []).to_list(),
            out.get("I (A)", []).to_list(),
            out.get("t (s)", []).to_list(),
        )

    def output(self, enable: bool):
        self.lpt.pulse_output(self._card_id, self._chan, 1 if enable else 0)

    def close(self):
        try:
            self.output(False)
        except Exception:
            pass
        self._base.close()

    # ---- Introspection helpers ----
    def is_connected(self) -> bool:
        try:
            return self._card_id is not None and self.lpt is not None
        except Exception:
            return False

if __name__ == "__main__":
    # Minimal self-test (requires reachable 4200A LPT server). Adjust IP as needed.
    addr = "192.168.0.10:8888"
    print("Keithley 4200A Controller Test")
    try:
        ctrl = Keithley4200AController(addr)
        print(ctrl.get_idn())
        ctrl.enable_output(False)
        pmu = Keithley4200A_PMUController(addr + "|PMU1-CH1")
        print("PMU connected:", pmu.is_connected())
        df = pmu.run_fixed_amplitude_pulses(amplitude_v=0.5, base_v=0.0, num_pulses=1,
                                            width_s=10e-6, period_s=20e-6)
        print("Fetched rows:", len(df) if isinstance(df, pd.DataFrame) else "n/a")
        pmu.close()
        ctrl.close()
    except Exception as exc:
        print("Self-test skipped/failed:", exc)
