


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

        if as_dataframe:
            return pd.DataFrame({
                "V (V)": v,
                "I (A)": i,
                "t (s)": ts,
                "Status": statuses,
            })

        return v, i, ts, statuses

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

# #----------------Proxy Class----------------

# logger = logging.getLogger("TCPClientProxy")

# import json
# import builtins
# import asyncio
# import logging

# class RemoteException(Exception):
#     """
#     A generic exception that is raised when the server-side code encountered an exception. As there is no universal
#     specification on how an exception (in particular custom exception) looks like and can be created, we have
#     to use a generic one and print the original traceback and exception type as the message.
#     """


# class RemoteVar:
#     def __init__(self, variable_reference_name):
#         self._variable_reference_name = variable_reference_name


# class Proxy:
#     _target_class: str

#     def __init__(self, address: str, port: int, target_class: str):
#         self.loop = asyncio.new_event_loop()
#         self._target_class = target_class
#         self.address = address
#         self.port = port
        
#     def __del__(self):
#         self.loop.close()

#     def _convert_argument_from_json(self, arg):
#         if isinstance(arg, list):
#             return [self._convert_argument_from_json(element) for element in arg]
#         arg_type = arg["type"]
#         arg_value = arg["value"]
#         if arg_type == "RemoteVar":
#             return RemoteVar(arg_value)
#         elif arg_type == "NoneType":
#             return None
#         return getattr(builtins, arg_type)(arg_value)

#     def _convert_argument_to_json(self, arg):
#         # tuples become lists in json anyway, so treat them the same here
#         if isinstance(arg, list) or isinstance(arg, tuple):
#             return [self._convert_argument_to_json(element) for element in arg]
#         arg_type = type(arg).__name__
#         # complex types are not transferred but saved locally and only a reference is sent back
#         if arg_type == "RemoteVar":
#             arg = arg._variable_reference_name
#         return {
#             "type": arg_type,
#             "value": arg
#         }

#     async def _async_send_to_server(self, command: str) -> str:
#         reader, writer = await asyncio.open_connection(
#             self.address, self.port)

#         writer.write(command.encode("utf-8") + b'\n')
#         await writer.drain()

#         data = await reader.readline()

#         writer.close()
#         return data.decode("utf-8")

#     def _send_to_server(self, command: str) -> str:
#         result = self.loop.run_until_complete(self._async_send_to_server(command))
#         return result

#     def unpack_result(self, response):
#         result = json.loads(response)
#         status = result.get("status", "invalid")
#         if status == "success":
#             return result
#         if status == "exception":
#             message = result["message"]
            
#              # only used if tblib was imported 
#             if tblib_imported:
#                 tb = Traceback.from_dict(result["traceback"]).as_traceback() 
#             else:
#                 tb = None

#             reraise(
#                 RemoteException,
#                 RemoteException(f"Server-side processing failed with {message}"),
#                 tb,
#                 )
                
#         raise Exception("Error decoding the response from the server")

#     def __getattr__(self, function):
#         def handle_call(*args, **kwargs):
#             args = args or []
#             kwargs = kwargs or {}
#             command_json = {
#                 "class": self._target_class,
#                 "function": function,
#                 "args": [self._convert_argument_to_json(arg) for arg in args],
#                 "kwargs": {k: self._convert_argument_to_json(v) for k, v in kwargs.items()}
#             }
#             command = json.dumps(command_json)
#             logger.debug(f"Request: {command}")
#             result = self._send_to_server(command)
#             logger.debug(f"Response: {result}")
#             result_json = self.unpack_result(result)
#             return self._convert_argument_from_json(result_json["return"])

#         if function[0] != "_":
#             # try to determine if it is an attribute and not a function
#             command_json = {
#                 "class": self._target_class,
#                 "attribute": function
#             }
#             command = json.dumps(command_json)
#             result = self._send_to_server(command)
#             result_json = self.unpack_result(result)
#             if result_json["return"]["type"] == "callable":
#                 return handle_call
#             logger.debug(f"Request: {command}")
#             logger.debug(f"Response: {result}")
#             return self._convert_argument_from_json(result_json["return"])
#         return None


if __name__ == "__main__":
    addr = "192.168.0.10:8888|PMU1-CH1"
    pmu = Keithley4200A_PMUController(addr)
    pmu.configure_pulse(
        v_src_range=10.0,
        v_meas_range_type=0, v_meas_range=10.0,
        i_meas_range_type=0, i_meas_range=0.2,
        v_limit=5.0, i_limit=1.0, power_limit=10.0,
        start_pct=0.2, stop_pct=0.8, num_pulses=4,
        period=20e-6, delay=1e-7, width=10e-6, rise=1e-7, fall=1e-7,
        load_ohm=1e6,
    )
    df = pmu.run_fixed_amplitude_pulses(amplitude_v=0.5, base_v=0.0,
                                        num_pulses=10, width_s=10e-6, period_s=20e-6)
    print(df)
    pmu.close()