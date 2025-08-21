


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
                self._pmu_channel = ch or 1
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

    Construct with the same address string format as Keithley4200AController but
    include a PMU channel selection, e.g. "192.168.0.10:8888|PMU1-CH1".
    """

    def __init__(self, address: str) -> None:
        base = Keithley4200AController(address if "|" in address else address + "|PMU1-CH1")
        if not base._is_pmu:
            raise ValueError("PMUController requires a PMU address like '...|PMU1-CH1'")

        self._base = base
        self.lpt = base.lpt
        self.param = base.param
        self._card_id = base._instr_id
        self._chan = base._pmu_channel or 1

        # Default pulse configuration (similar to examples)
        self.configure_pulse(
            v_src_range=10.0,
            v_meas_range_type=0,
            v_meas_range=10.0,
            i_meas_range_type=0,
            i_meas_range=0.2,
            v_limit=5.0,
            i_limit=1.0,
            power_limit=10.0,
            start_pct=0.5,
            stop_pct=0.7,
            num_pulses=1,
            period=2e-6,
            delay=2e-8,
            width=5e-7,
            rise=1e-7,
            fall=1e-7,
            load_ohm=1e6,
        )

    def configure_pulse(self,
                         v_src_range: float,
                         v_meas_range_type: int,
                         v_meas_range: float,
                         i_meas_range_type: int,
                         i_meas_range: float,
                         v_limit: float,
                         i_limit: float,
                         power_limit: float,
                         start_pct: float,
                         stop_pct: float,
                         num_pulses: int,
                         period: float,
                         delay: float,
                         width: float,
                         rise: float,
                         fall: float,
                         load_ohm: float) -> None:
        # Mode init
        self.lpt.pg2_init(self._card_id, 0)

        # Route RPM to pulse
        self.lpt.rpm_config(self._card_id, self._chan, self.param.KI_RPM_PATHWAY, self.param.KI_RPM_PULSE)

        # Spot-mean meas config (V and I amplitude; timestamp; LLEC on)
        self.lpt.pulse_meas_sm(self._card_id, self._chan, 0, 1, 0, 1, 0, 1, 1)

        # Ranges and limits
        self.lpt.pulse_ranges(self._card_id, self._chan, v_src_range, v_meas_range_type, v_meas_range,
                               i_meas_range_type, i_meas_range)
        self.lpt.pulse_limits(self._card_id, self._chan, v_limit, i_limit, power_limit)

        # Meas timing and source timing
        self.lpt.pulse_meas_timing(self._card_id, self._chan, start_pct, stop_pct, int(num_pulses))
        self.lpt.pulse_source_timing(self._card_id, self._chan, period, delay, width, rise, fall)

        # Load
        self.lpt.pulse_load(self._card_id, self._chan, load_ohm)

    def arm_single_pulse(self, amplitude_v: float, base_v: float = 0.0):
        # Single-point sweep (start=stop=value)
        self.lpt.pulse_sweep_linear(self._card_id, self._chan, self.param.PULSE_AMPLITUDE_SP,
                                    float(amplitude_v), float(amplitude_v), 0.0)
        # Ensure output relay on
        self.lpt.pulse_output(self._card_id, self._chan, 1)

    def exec_and_fetch(self) -> tuple[list[float], list[float], list[float], list[int]]:
        # Execute simple pulse
        self.lpt.pulse_exec(self.param.PULSE_MODE_SIMPLE)

        # Wait until finished (simple polling)
        timeout = 30.0
        t0 = time.time()
        while True:
            status, elapsed = self.lpt.pulse_exec_status()
            if status != self.param.PMU_TEST_STATUS_RUNNING:
                break
            if (time.time() - t0) > timeout:
                self.lpt.dev_abort()
                break
            time.sleep(0.05)

        # Determine buffer size and fetch
        buf_size = self.lpt.pulse_chan_status(self._card_id, self._chan)
        v, i, ts, statuses = self.lpt.pulse_fetch(self._card_id, self._chan, 0, buf_size - 1)
        return v, i, ts, statuses

    def output(self, enable: bool):
        self.lpt.pulse_output(self._card_id, self._chan, 1 if enable else 0)

    def close(self):
        try:
            self.output(False)
        except Exception:
            pass
        self._base.close()


    def get_identifier(self) -> str:
        """Return IDN."""
        self.port.write("*IDN?")
        return self.port.read()

    def get_options(self) -> str:
        """Return OPT."""
        self.port.write("*OPT?")
        return self.port.read()

    def set_resolution(self, resolution: int) -> str:
        """Set the resolution of the device."""
        if self.command_set == "US":
            self.port.write(f"RS {int(resolution)}")
        return self.read_tcpip_port()

    def set_current_range(self, channel: str, current_range: float, compliance: float) -> str:
        """Set the current range of the device."""
        if self.command_set == "US":
            self.port.write(f"RI {channel}, {current_range}, {compliance}")
        return self.read_tcpip_port()

    def set_current_range_limited(self, channel: str, current: float) -> str:
        """Set the current range of the device."""
        if self.command_set == "US":
            self.port.write(f"RG {channel}, {current}")
        return self.read_tcpip_port()

    def switch_off(self, channel: str) -> str:
        """Switch off the device."""
        if self.command_set == "US":
            self.port.write(f"DV{channel}")
        return self.read_tcpip_port()

    def clear_buffer(self) -> str:
        """Clear the buffer of the device."""
        self.port.write("BC")
        return self.read_tcpip_port()

    def set_to_4200(self) -> str:
        """Set the device to 4200 mode."""
        self.port.write("EM 1,0")  # set to 4200 mode for this session
        return self.read_tcpip_port()

    def enable_user_mode(self) -> str:
        """Enable user mode."""
        self.port.write("US")  # user mode
        return self.read_tcpip_port()

    def set_data_service(self) -> str:
        """Set data ready service."""
        if self.command_set == "US":
            self.port.write("DR0")  # data ready service request
        return self.read_tcpip_port()

    def set_integration_time(self, nplc: int) -> str:
        """Set the integration time of the device."""
        if self.command_set == "US":
            self.port.write("IT" + str(nplc))
        return self.read_tcpip_port()

    def set_current(self, channel: str, current_range: int, value: float, protection: float) -> str:
        """Set the current of the given channel."""
        if self.command_set == "US":
            self.port.write(f"DI{channel}, {current_range}, {value}, {protection}")
        return self.read_tcpip_port()

    def set_voltage(self, channel: str, voltage_range: int, value: float, protection: float) -> str:
        """Set the voltage of the given channel."""
        if self.command_set == "US":
            self.port.write(f"DV{channel}, {voltage_range}, {value}, {protection}")
        return self.read_tcpip_port()

    def get_voltage(self, channel: str) -> float:
        """Request voltage of given channel."""
        voltage = float("nan")
        overflow_value = 1e37
        if self.command_set == "US":
            self.port.write("TV" + str(channel))
            answer = self.port.read()
            voltage = float(answer[3:])
            if voltage > overflow_value:
                voltage = float("nan")
        return voltage

        # • N: Normal
        # • L: Interval too short
        # • V: Overflow reading (A/D converter saturated)
        # • X: Oscillation
        # • C: This channel in compliance
        # • T: Other channel in compliance

    def get_current(self, channel: str) -> float:
        """Request current of given channel."""
        current = float("nan")
        overflow_value = 1e37
        if self.command_set == "US":
            self.port.write("TI" + str(channel))
            answer = self.port.read()
            current = float(answer[3:])
            if current > overflow_value:
                current = float("nan")
        return current

    def set_pulse_impedance(self, channel: str, impedance: str) -> str:
        """Set the pulse impedance of the device."""
        impedance = float(impedance)
        minimum_impedance = 1.0
        maximum_impedance = 1e6
        if impedance < minimum_impedance:
            msg = f"Impedance of {impedance} too low. Must be between 1.0 and 1e6."
            raise ValueError(msg)
        if impedance > maximum_impedance:
            msg = f"Impedance of {impedance} too high. Must be between 1.0 and 1e6."
            raise ValueError(msg)

        self.port.write(f"PD {channel}, {impedance}")

        return self.read_tcpip_port()

    def set_pulse_trigger_mode(self, channel: str, mode: int, count: int) -> str:
        """Set pulse trigger mode.

        Mode:
            Burst mode: 0
            Continuous: 1 (default)
            Trigger burst: 2

        Count:
            Burst or trigger burst only: Pulse count in number of pulses: 1 to 232-1; set to 1 for
            continuous (default 1)
        """
        self.port.write(f"PG {channel}, {mode}, {count}")
        return self.read_tcpip_port()

    def set_pulse_stop(self, channel: str) -> str:
        """Stop pulse output for given channel."""
        self.port.write(f"PH {channel}")
        return self.read_tcpip_port()

    def set_pulse_output(self, channel: str, output: str) -> str:
        """Set pulse output of given channel."""
        self.port.write(f"PO {channel}, {output}")
        return self.read_tcpip_port()

    def set_pulse_reset(self, channel: str) -> str:
        """Reset pulse for given channel."""
        self.port.write(f"PS {channel}")
        return self.read_tcpip_port()

    def set_pulse_timing(self, channel: str, period: str, width: str, rise_time: str, fall_time: str) -> str:
        """Set pulse timing for given channel."""
        self.port.write(f"PT {channel}, {period}, {width}, {rise_time}, {fall_time}")
        return self.read_tcpip_port()

    def set_pulse_levels(self, channel: str, pulse_high: str, pulse_low: str, range: str, current_limit: str) -> str:
        """This command sets pulse high, pulse low, range, and current limit independently the given channel."""
        self.port.write(f"PV {channel}, {pulse_high}, {pulse_low}, {range}, {current_limit}")
        return self.read_tcpip_port()

    def set_pulse_output_parameters(self, channel: str, pulse_delay: str, trigger_polarity: str) -> str:
        """This command sets the trigger output parameters for pulse delay and trigger polarity."""
        self.port.write(f"TO {channel}, {pulse_delay}, {trigger_polarity}")
        return self.read_tcpip_port()

    def set_pulse_source(self, channel: str, trigger_source: str) -> str:
        """This command sets the trigger source that is used to trigger the pulse card to start its output."""
        self.port.write(f"TS {channel}, {trigger_source}")
        return self.read_tcpip_port()

    def kult_get_module_description(self, library: str, module: str) -> str:
        """Returns a description of the Library module.

        Attention: only works after EX command has been used before.
        """
        self.port.write(f"GD {library} {module}")
        return self.port.read()

    def kult_execute_module(self, library: str, module: str, *args) -> str:
        arguments = ", ".join([str(x) for x in args])
        self.port.write(f"EX {library} {module}({arguments})")

        if self.port_string.startswith("TCPIP"):
            answer = self.port.read()
            print("EX TCPIP read:", answer)

        return self.port.read()

    def kult_abort(self) -> None:
        """Abort KULT."""
        self.port.write("AB")

    def kult_get_parameter(self, name_or_index: str | int, num_values=None) -> None:
        """Retrieves information about the function arguments.

        Args:
            name_or_index: define parameter by name using string or by index using integer
            num_values: in case of an array, the number of values can be defined
        """
        if isinstance(name_or_index, str):
            command = f"GN {name_or_index}"
            if num_values:
                command += " %i" % int(num_values)
            self.port.write(command)

if __name__ == "__main__":
    # Basic connectivity and measure test
    import sys
    import time

    address = "192.168.0.10:8888"
    print(f"Connecting to 4200A at {address} ...")
    ctrl = Keithley4200AController(address)
    try:
        print(ctrl.get_idn())
        ctrl.set_voltage(0.5, Icc=1e-3)
        time.sleep(0.1)
        v = ctrl.measure_voltage()
        i = ctrl.measure_current()
        print(f"Measured V={v:.6g} V, I={i:.6g} A")
        ctrl.enable_output(False)
        ctrl.close()
        
    except Exception as e:
        print(f"Error: {e}")
    pass