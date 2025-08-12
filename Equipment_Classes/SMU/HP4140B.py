import time
import numpy as np
import pyvisa


class HP4140BController:
    """Moved from Equipment_Classes/HP4140B.py. See original for full docstring."""

    def __init__(
        self,
        gpib_address: str = "GPIB0::17::INSTR",
        timeout_s: float = 5.0,
        append_semicolon: bool = False,
    ) -> None:
        self._append_semicolon = append_semicolon
        self.rm = None
        self.inst = None

        try:
            self.rm = pyvisa.ResourceManager()
            self.inst = self.rm.open_resource(gpib_address)
            self.inst.timeout = int(timeout_s * 1000)
            self.inst.write_termination = ""
            self.inst.read_termination = "\n"
            time.sleep(0.05)
            print("HP4140B: GPIB session opened")
        except Exception as exc:
            print(f"HP4140B: Failed to open GPIB session: {exc}")
            self.inst = None

    def _format_cmd(self, cmd: str) -> str:
        return f"{cmd};" if self._append_semicolon else cmd

    def write(self, cmd: str) -> None:
        if not self.inst:
            raise RuntimeError("HP4140B not connected")
        self.inst.write(self._format_cmd(cmd))

    def query(self, cmd: str) -> str:
        if not self.inst:
            raise RuntimeError("HP4140B not connected")
        return self.inst.query(self._format_cmd(cmd)).strip()

    def enable_output(self, channel: int = 1) -> None:
        self.write(f"CN {channel}")

    def disable_output(self, channel: int = 1) -> None:
        self.write(f"CL {channel}")

    def configure_voltage_source(self, channel: int = 1, range_code: int = 0, voltage_v: float = 0.0, compliance_a: float = 1e-3) -> None:
        self.write(f"DV {channel},{range_code},{voltage_v},{compliance_a}")

    def configure_current_source(self, channel: int = 1, range_code: int = 0, current_a: float = 0.0, compliance_v: float = 10.0) -> None:
        self.write(f"DI {channel},{range_code},{current_a},{compliance_v}")

    def trigger_voltage_measure(self, channel: int = 1, mode: int = 0) -> None:
        self.write(f"TV {channel},{mode}")

    def trigger_current_measure(self, channel: int = 1, mode: int = 0) -> None:
        self.write(f"TI {channel},{mode}")

    def read_data(self, channel: int = 1):
        raw = self.query(f"DO {channel}")
        parts = [p.strip() for p in raw.split(',')]
        status = parts[0] if len(parts) >= 1 else ""
        voltage_v = float(parts[1]) if len(parts) >= 2 else float("nan")
        current_a = float(parts[2]) if len(parts) >= 3 else float("nan")
        return status, voltage_v, current_a

    def set_voltage(self, voltage: float, Icc: float = 1e-3, channel: int = 1, range_code: int = 0) -> None:
        self.enable_output(channel)
        self.configure_voltage_source(channel=channel, range_code=range_code, voltage_v=voltage, compliance_a=Icc)

    def set_current(self, current: float, Vcc: float = 10.0, channel: int = 1, range_code: int = 0) -> None:
        self.enable_output(channel)
        self.configure_current_source(channel=channel, range_code=range_code, current_a=current, compliance_v=Vcc)

    def measure_voltage(self, channel: int = 1) -> float:
        self.trigger_voltage_measure(channel=channel, mode=0)
        _, v, _ = self.read_data(channel)
        return v

    def measure_current(self, channel: int = 1) -> float:
        self.trigger_current_measure(channel=channel, mode=0)
        _, _, i = self.read_data(channel)
        return i

    def measure_both(self, channel: int = 1):
        self.trigger_voltage_measure(channel=channel, mode=0)
        self.trigger_current_measure(channel=channel, mode=0)
        _, v, i = self.read_data(channel)
        return v, i

    def voltage_ramp(self, target_voltage_v: float, steps: int = 30, pause_s: float = 0.02, compliance_a: float = 1e-3, channel: int = 1, range_code: int = 0) -> None:
        if not self.inst:
            print("HP4140B: No device connected")
            return
        try:
            current_voltage = self.measure_voltage(channel)
            if not np.isfinite(current_voltage):
                current_voltage = 0.0
        except Exception:
            current_voltage = 0.0
        delta = (target_voltage_v - current_voltage) / max(1, steps)
        for step_index in range(steps):
            v = current_voltage + (step_index + 1) * delta
            self.set_voltage(v, compliance_a=compliance_a, channel=channel, range_code=range_code)
            time.sleep(pause_s)

    def shutdown(self, channel: int = 1) -> None:
        if not self.inst:
            return
        try:
            self.voltage_ramp(0.0, steps=10, pause_s=0.05, channel=channel)
            time.sleep(0.2)
            self.disable_output(channel)
            print("HP4140B: Output disabled, voltage ramped to 0 V")
        except Exception as exc:
            print(f"HP4140B: Shutdown warning: {exc}")

    def close(self) -> None:
        if self.inst:
            try:
                self.shutdown()
            except Exception:
                pass
            try:
                self.inst.close()
            except Exception:
                pass
        if self.rm:
            try:
                self.rm.close()
            except Exception:
                pass
        print("HP4140B: Session closed")

    def get_idn(self) -> str:
        return "HP4140B"

    def beep(self, frequency: float = 1000, duration: float = 0.2) -> None:
        try:
            self.write("BEEP")
        except Exception:
            pass


