import time
from typing import Optional, Dict, Any, Union

import pyvisa


class SiglentSDG1032X:
    """
    Controller for Siglent SDG1032X waveform generators using PyVISA (USBTMC/LAN/GPIB).

    Highlights:
      - Connect, reset, IDN, error query
      - Per-channel output on/off, load impedance
      - Basic waveform (SINE/SQUARE/RAMP/PULSE/DC/NOISE/ARB), freq, amp, offset, phase, duty
      - DC output convenience (for bias control)
      - Burst mode + trigger source (INT/EXT/BUS) and software trigger
      - Generic SCPI write/query helpers for full coverage
    """

    def __init__(self, resource: Optional[str] = None, timeout_ms: int = 5000):
        """
        resource: VISA resource string (e.g., 'USB0::0xF4EC::0x1103::SDG1XCAQ3R3184::INSTR' or 'TCPIP0::192.168.1.100::INSTR')
        timeout_ms: VISA IO timeout in milliseconds
        """
        self.rm: Optional[pyvisa.ResourceManager] = None
        self.inst: Optional[pyvisa.resources.MessageBasedResource] = None
        self.resource = resource
        self.timeout_ms = timeout_ms

    # ------------- Connection management -------------

    def connect(self, resource: Optional[str] = None) -> bool:
        try:
            if resource:
                self.resource = resource
            if not self.resource:
                raise ValueError("No VISA resource specified.")
            self.rm = pyvisa.ResourceManager()
            self.inst = self.rm.open_resource(self.resource)
            self.inst.timeout = self.timeout_ms
            # Make sure we can talk to it
            _ = self.idn()
            return True
        except Exception as e:
            print(f"Error connecting to instrument: {e}")
            self.inst = None
            if self.rm:
                try:
                    self.rm.close()
                except Exception:
                    pass
                self.rm = None
            return False

    def disconnect(self):
        if self.inst is not None:
            try:
                self.inst.close()
            except Exception:
                pass
        if self.rm is not None:
            try:
                self.rm.close()
            except Exception:
                pass
        self.inst = None
        self.rm = None

    def is_connected(self) -> bool:
        return self.inst is not None

    # ------------- Core SCPI helpers -------------

    def write(self, cmd: str):
        if not self.inst:
            raise RuntimeError("Instrument not connected.")
        # print(f">>> {cmd}")  # uncomment for debugging
        self.inst.write(cmd)

    def query(self, cmd: str) -> str:
        if not self.inst:
            raise RuntimeError("Instrument not connected.")
        # print(f">>> {cmd}?")
        resp = self.inst.query(cmd)
        return resp.strip()

    def send_command(self, base: str, params: Dict[str, Union[str, float, int]]):
        """
        Compose commands like: C1:BSWV WVTP,SINE,FRQ,1KHZ,AMP,1VPP,OFST,0V
        """
        parts = []
        for k, v in params.items():
            if isinstance(v, str):
                parts.append(f"{k},{v}")
            else:
                parts.append(f"{k},{v}")
        cmd = f"{base} " + ",".join(parts)
        self.write(cmd)

    # ------------- Basic instrument controls -------------

    def idn(self) -> str:
        try:
            return self.query("*IDN?")
        except Exception as e:
            return f"IDN error: {e}"

    def reset(self):
        self.write("*RST")

    def clear_status(self):
        self.write("*CLS")

    def error_query(self) -> str:
        # Returns "0,No error" when clear
        return self.query("SYST:ERR?")

    def beeper(self, on: bool = True):
        self.write(f"SYST:BEEP {'ON' if on else 'OFF'}")

    # ------------- Channel helpers -------------

    @staticmethod
    def _ch_prefix(channel: int) -> str:
        if channel not in (1, 2):
            raise ValueError("channel must be 1 or 2")
        return f"C{channel}:"

    def output(self, channel: int, on: bool = True):
        pref = self._ch_prefix(channel)
        self.write(f"{pref}OUTP {'ON' if on else 'OFF'}")

    def set_output_load(self, channel: int, load: Union[str, float] = "50OHM"):
        """
        load: '50OHM', 'HIGHZ', or numeric impedance in ohms (e.g., 50, 75, 600)
        """
        pref = self._ch_prefix(channel)
        if isinstance(load, str):
            self.write(f"{pref}OUTP LOAD,{load}")
        else:
            self.write(f"{pref}OUTP LOAD,{load}")

    # ------------- Basic waveform -------------

    def set_basic_waveform(
        self,
        channel: int,
        wvtype: str = "SINE",
        frequency: Union[str, float] = "1KHZ",
        amplitude: Union[str, float] = "1VPP",
        offset: Union[str, float] = "0V",
        phase_deg: Union[str, float] = 0,
        duty_cycle: Optional[Union[str, float]] = None,
    ):
        """
        wvtype: SINE|SQUARE|RAMP|PULSE|NOISE|DC|ARB
        frequency: e.g., 1000, '1KHZ', '10MHZ'
        amplitude: e.g., 1, '1VPP', '0.5VRMS', '0DBM'
        offset: e.g., 0, '0V', '1.5V'
        phase_deg: e.g., 0, '90'
        duty_cycle: for SQUARE/PULSE/RAMP as supported, e.g., 50 or '50'
        """
        pref = self._ch_prefix(channel)

        params: Dict[str, Any] = {
            "WVTP": str(wvtype).upper(),
            "FRQ": frequency,
            "AMP": amplitude,
            "OFST": offset,
            "PHSE": phase_deg,
        }
        if duty_cycle is not None:
            params["DUTY"] = duty_cycle

        self.send_command(f"{pref}BSWV", params)

    def set_dc_level(self, channel: int, level: Union[str, float] = "0V"):
        """
        Convenience: set DC mode and define the level via OFST.
        """
        pref = self._ch_prefix(channel)
        self.send_command(f"{pref}BSWV", {"WVTP": "DC", "OFST": level})

    def set_offset(self, channel: int, offset: Union[str, float]):
        pref = self._ch_prefix(channel)
        self.send_command(f"{pref}BSWV", {"OFST": offset})

    # ------------- Burst and trigger -------------

    def set_burst_params(self, channel: int, params: Dict[str, Union[str, float, int]]):
        """
        Generic burst parameter setter. Examples of params keys you can use (depending on firmware):
          - STATE: ON|OFF
          - TRMD: NCYC|GATE|INF
          - NCYC or CNT: number of cycles (e.g., 1..1e6)
          - TRSR: INT|EXT|BUS (BUS/MAN = software/GPIB trigger)
          - PERI or INTFRQ: internal trigger period/frequency when TRSR=INT
          - DLAY: trigger delay
          - PHSE: phase in deg
          - GATEPOL: POS|NEG
        """
        pref = self._ch_prefix(channel)
        self.send_command(f"{pref}BTWV", params)

    def enable_burst(
        self,
        channel: int,
        mode: str = "NCYC",
        cycles: int = 1,
        trigger_source: str = "BUS",
        internal_period: Optional[Union[str, float]] = None,
    ):
        """
        Convenience wrapper for common burst setup:
         - mode: 'NCYC' (finite cycles), 'GATE', or 'INF'
         - trigger_source: 'INT' (internal rate), 'EXT' (rear BNC), 'BUS'/'MAN' (software trigger)
         - internal_period: e.g., '10MS' or float seconds if TRSR='INT'
        """
        params: Dict[str, Union[str, float, int]] = {
            "STATE": "ON",
            "TRMD": mode.upper(),
            "TRSR": "BUS" if trigger_source.upper() in ("BUS", "MAN", "SW") else trigger_source.upper(),
        }
        if mode.upper() == "NCYC":
            # Some firmwares use NCYC, some accept CNT. We'll try NCYC.
            params["NCYC"] = int(cycles)
        if trigger_source.upper() == "INT" and internal_period is not None:
            # Some firmwares accept PERI (period) or INTFRQ (internal trigger frequency).
            # Here we set PERI; adjust to INTFRQ if your unit expects it.
            params["PERI"] = internal_period
        self.set_burst_params(channel, params)

    def disable_burst(self, channel: int):
        self.set_burst_params(channel, {"STATE": "OFF"})

    def trigger_now(self, channel: int):
        """
        Issue a software trigger to the specified channel.
        Requires burst TRSR=BUS/MAN on that channel.
        """
        pref = self._ch_prefix(channel)
        self.write(f"{pref}TRIG")

    # ------------- Utility -------------

    def opc(self, timeout_s: float = 5.0) -> bool:
        """
        *OPC? blocks until operations complete or times out.
        """
        t0 = time.time()
        while True:
            try:
                resp = self.query("*OPC?")
                return resp.strip() == "1"
            except Exception:
                pass
            if (time.time() - t0) > timeout_s:
                return False
            time.sleep(0.05)

    def upload_csv_waveform(self, channel: int, csv_filename: str, waveform_name: str = "USER"):
        """
        Upload a CSV file containing waveform data to the function generator.
        The CSV should contain one voltage value per line.
        """
        try:
            # Read the CSV file
            with open(csv_filename, 'r') as f:
                data = f.read().strip()

            # Convert to the format expected by Siglent
            # Siglent expects comma-separated values
            values = [line.strip() for line in data.split('\n') if line.strip()]
            if not values:
                raise ValueError("CSV file is empty or contains no valid data")

            # Upload the data
            data_str = ",".join(values)
            self.write(f"C{channel}:ARWV NAME,{waveform_name},DATA,{data_str}")

            return True
        except Exception as e:
            print(f"Error uploading CSV waveform: {e}")
            return False


def safe_float_or_str(val: Union[str, float, int]) -> Union[str, float]:
    return val if isinstance(val, str) else float(val)


if __name__ == "__main__":
    """
    Basic test:
      - Connect
      - Reset, clear
      - Set CH1 to SINE 1 kHz, 1 Vpp, 0 V offset
      - Turn on output
      - Change to SQUARE 1 kHz, 1 Vpp, 50% duty
      - Configure burst for 5 cycles per trigger on BUS (software)
      - Issue a software trigger
      - Disable burst, turn off, disconnect
    """
    # Update with your VISA resource:
    VISA_RESOURCE = "USB0::0xF4EC::0x1103::SDG1XCAQ3R3184::INSTR"

    gen = SiglentSDG1032X(resource=VISA_RESOURCE)

    if not gen.connect():
        raise SystemExit("Failed to connect to the generator.")

    try:
        print("Connected to:", gen.idn())
        gen.clear_status()
        gen.reset()
        gen.opc()

        # Set CH1 basic sine
        gen.set_basic_waveform(
            channel=1,
            wvtype="SINE",
            frequency="1KHZ",
            amplitude="1VPP",
            offset="0V",
            phase_deg=0,
        )
        gen.output(1, True)

        time.sleep(0.5)

        # Change to square with duty
        gen.set_basic_waveform(
            channel=1,
            wvtype="SQUARE",
            frequency="1KHZ",
            amplitude="1VPP",
            offset="0V",
            duty_cycle=50,
        )

        # Example: add DC offset for laser bias (be careful with your hardware!)
        # gen.set_offset(1, "1.5V")

        # Configure burst: 5 cycles per trigger, BUS/software-triggered
        gen.enable_burst(channel=1, mode="NCYC", cycles=5, trigger_source="BUS")
        time.sleep(0.2)

        # Fire a software trigger
        print("Issuing software trigger...")
        gen.trigger_now(1)

        time.sleep(1.0)

        # Clean up: disable burst, output off
        gen.disable_burst(1)
        gen.output(1, False)

        # Check for instrument errors
        err = gen.error_query()
        if not err.startswith("0"):
            print("Instrument reported error:", err)
        else:
            print("No instrument errors reported.")
    finally:
        gen.disconnect()
        print("Disconnected.")