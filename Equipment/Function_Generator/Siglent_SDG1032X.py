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

    def get_output_status(self, channel: int) -> bool:
        """Return True if channel output is ON, False if OFF.

        Parses responses like: "C1:OUTP ON,LOAD,50,PLRT,NOR".
        """
        pref = self._ch_prefix(channel)
        resp = self.query(f"{pref}OUTP?")
        txt = (resp or "").strip().upper()
        # Heuristic: prefer explicit OFF if present; otherwise ON if present
        if "OFF" in txt:
            return False
        if "ON" in txt:
            return True
        # Fallback: unknown -> False
        return False

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

    def set_pulse_shape(
        self,
        channel: int,
        frequency_hz: Union[str, float],
        high_level_v: Union[str, float],
        low_level_v: Union[str, float],
        pulse_width_s: Optional[Union[str, float]] = None,
        duty_pct: Optional[Union[str, float]] = None,
        rise_s: Optional[Union[str, float]] = None,
        fall_s: Optional[Union[str, float]] = None,
        delay_s: Optional[Union[str, float]] = None,
    ):
        """
        Configure a PULSE waveform using high/low levels and optional duty, rise/fall, and delay.
        Falls back gracefully if some parameters are unsupported by firmware.
        """
        pref = self._ch_prefix(channel)
        # Base pulse setup using HLEV/LLEV when available; otherwise fall back to AMP/OFST
        try:
            base_params: Dict[str, Any] = {
                "WVTP": "PULSE",
                "FRQ": frequency_hz,
                "HLEV": high_level_v,
                "LLEV": low_level_v,
            }
            if duty_pct is not None:
                base_params["DUTY"] = duty_pct
            if pulse_width_s is not None:
                base_params["PWID"] = self._fmt_time_value(pulse_width_s)
            self.send_command(f"{pref}BSWV", base_params)
        except Exception:
            # Fallback using amplitude/offset
            try:
                amp = float(high_level_v) - float(low_level_v)  # type: ignore[arg-type]
                ofst = (float(high_level_v) + float(low_level_v)) / 2.0  # type: ignore[arg-type]
            except Exception:
                amp = high_level_v
                ofst = 0
            self.set_basic_waveform(
                channel=channel,
                wvtype="PULSE",
                frequency=frequency_hz,
                amplitude=f"{amp}VPP",
                offset=f"{ofst}V",
                duty_cycle=duty_pct,
            )

        # Attempt to set edges and delay individually when supported
        for key, val in (("RISE", rise_s), ("FALL", fall_s), ("DLY", delay_s)):
            if val is None:
                continue
            try:
                self.send_command(f"{pref}BSWV", {key: self._fmt_time_value(val)})
            except Exception:
                pass

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
        burst_delay_s: Optional[Union[str, float]] = None,
    ):
        """
        Convenience wrapper for common burst setup:
         - mode: 'NCYC' (finite cycles), 'GATE', or 'INF'
         - trigger_source: 'INT' (internal rate), 'EXT' (rear BNC), 'BUS'/'MAN' (software trigger)
         - internal_period: e.g., '10MS' or float seconds if TRSR='INT'
        """
        # Always set basic burst state/mode/source
        base_params: Dict[str, Union[str, float, int]] = {
            "STATE": "ON",
            "TRMD": mode.upper(),
            "TRSR": "BUS" if trigger_source.upper() in ("BUS", "MAN", "SW") else trigger_source.upper(),
        }
        # Build a comprehensive BTWV parameter set and send once to improve reliability
        params: Dict[str, Union[str, float, int]] = {}
        if mode.upper() == "NCYC":
            # Use TIME as per manual; include alternates for compatibility
            params["TIME"] = int(cycles)
            params["NCYC"] = int(cycles)
            params["CNT"] = int(cycles)
        if trigger_source.upper() == "INT" and internal_period is not None:
            # provide both PERI (period) and INTFRQ (Hz)
            params["PERI"] = self._fmt_time_value(internal_period)
            if isinstance(internal_period, (int, float)) and internal_period:
                params["INTFRQ"] = 1.0 / float(internal_period)
        if burst_delay_s is not None:
            params["DLY"] = self._fmt_time_value(burst_delay_s)
        # Merge with base and send once
        all_params = {**base_params, **params}
        self.set_burst_params(channel, all_params)

    @staticmethod
    def _fmt_time_value(val: Union[str, float, int]) -> Union[str, float]:
        # Keep user strings (like '10MS')
        if isinstance(val, str):
            return val
        s = float(val)
        if s >= 1.0:
            return f"{s}S"
        ms = s * 1e3
        if ms >= 1.0:
            return f"{ms}MS"
        us = s * 1e6
        if us >= 1.0:
            return f"{us}US"
        ns = s * 1e9
        return f"{ns}NS"

    def disable_burst(self, channel: int):
        self.set_burst_params(channel, {"STATE": "OFF"})

    def trigger_now(self, channel: int):
        """
        Issue a software trigger to the specified channel.
        Requires burst TRSR=BUS/MAN on that channel.
        """
        pref = self._ch_prefix(channel)
        self.write(f"{pref}TRIG")

    # ------------- Query helpers -------------

    def read_basic_waveform(self, channel: int) -> str:
        pref = self._ch_prefix(channel)
        try:
            return self.query(f"{pref}BSWV?")
        except Exception as e:
            return f"ERR {e}"

    def read_burst(self, channel: int) -> str:
        pref = self._ch_prefix(channel)
        try:
            return self.query(f"{pref}BTWV?")
        except Exception as e:
            return f"ERR {e}"

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

    # ------------- Arbitrary waveform upload (WVDT binary — SDG1000X) -------------

    def upload_arb_waveform(
        self,
        channel: int,
        samples_normalized: list,
        waveform_name: str = "LSRPULSE",
        freq_hz: float = 1000.0,
        amplitude_v: float = 3.3,
        offset_v: float = 1.65,
    ) -> bool:
        """
        Upload an arbitrary waveform to the SDG1000X using the correct WVDT binary command.

        The SDG1000X requires binary little-endian 16-bit signed integer samples sent
        via the `WVDT` command — NOT the `ARWV` command (which only selects built-in waveforms).
        This method follows the official SDG1000X Programming Guide (section 3.22).

        Args:
            channel: Channel number (1 or 2).
            samples_normalized: List of floats in range [-1.0, +1.0]:
                +1.0 → output = offset_v + amplitude_v / 2  (high level)
                -1.0 → output = offset_v - amplitude_v / 2  (low level)
                Integers in the 14-bit range [-8192, +8191] are also accepted directly.
            waveform_name: Name stored on the instrument (≤8 alphanumeric chars).
            freq_hz: Playback frequency (Hz). Controls how fast the whole waveform plays.
                     For a single burst, set freq_hz = 1 / total_waveform_duration_s.
            amplitude_v: Peak-to-peak output amplitude (V).
                         High = offset_v + amplitude_v/2; Low = offset_v - amplitude_v/2.
            offset_v: DC offset (V). Center voltage of the output swing.

        Returns:
            True if upload succeeded, False on error.

        Notes:
            - Maximum 16,384 samples per waveform.
            - Minimum 2 samples.
            - Send uses write_raw() with write_termination='' to avoid corrupting binary data.
            - After upload, the waveform is selected with ARWV NAME,<name> and output type
              is set to ARB via BSWV WVTP,ARB.
        """
        import struct

        try:
            n = len(samples_normalized)
            if n < 2:
                raise ValueError("Waveform must have at least 2 samples.")
            if n > 16384:
                raise ValueError(f"Too many samples: {n} > 16,384 maximum for SDG1000X.")

            # Convert to 14-bit signed DAC values in [-8192, +8191]
            dac_values: list = []
            for v in samples_normalized:
                if isinstance(v, float):
                    dac = int(round(float(v) * 8191.0))
                else:
                    dac = int(v)
                dac = max(-8192, min(8191, dac))
                dac_values.append(dac)

            # Pack as little-endian 16-bit signed integers (2 bytes per sample)
            binary_data = struct.pack(f"<{n}h", *dac_values)

            # Build ASCII command header (WVDT with all required parameters)
            pref = self._ch_prefix(channel)
            header_str = (
                f"{pref}WVDT "
                f"WVNM,{waveform_name},"
                f"TYPE,5,"
                f"LENGTH,{n}B,"
                f"FREQ,{freq_hz:.6f},"
                f"AMPL,{amplitude_v:.6f},"
                f"OFST,{offset_v:.6f},"
                f"PHASE,0,"
                f"WAVEDATA,"
            )
            header_bytes = header_str.encode("ascii")

            # Send as raw bytes with no write termination to avoid corrupting binary payload
            old_write_term = self.inst.write_termination
            self.inst.write_termination = ""
            try:
                self.inst.write_raw(header_bytes + binary_data + b"\n")
            finally:
                self.inst.write_termination = old_write_term

            time.sleep(0.35)  # Allow instrument time to process binary transfer

            # Select the uploaded waveform and set output type
            self.write(f"{pref}ARWV NAME,{waveform_name}")
            self.write(f"{pref}BSWV WVTP,ARB")

            # Check instrument error queue
            err = self.error_query()
            if err and not str(err).startswith("0"):
                print(f"Instrument error after ARB upload: {err}")
                return False

            return True

        except Exception as exc:
            print(f"Error uploading ARB waveform via WVDT: {exc}")
            return False

    @staticmethod
    def build_ttl_pulse_samples(
        segments: list,
        sample_rate_hz: float = 10e6,
        high_normalized: float = 1.0,
        low_normalized: float = -1.0,
    ) -> list:
        """
        Build a normalized sample list from a (level, duration_s) segment table.

        Args:
            segments: List of (level, duration_s) tuples.
                      level can be 'H', 'HIGH', 1, True  → high_normalized
                      or        'L', 'LOW',  0, False → low_normalized
            sample_rate_hz: DAC sample rate in Sa/s (e.g. 10e6 = 10 MSa/s → 100 ns/point).
            high_normalized: Normalized value for HIGH segments (default +1.0).
            low_normalized: Normalized value for LOW segments (default -1.0).

        Returns:
            List of normalized floats suitable for upload_arb_waveform().

        Example:
            # 100 ns pulse, 900 ns gap, at 10 MSa/s (100 ns/point)
            samples = SiglentSDG1032X.build_ttl_pulse_samples(
                [('H', 100e-9), ('L', 900e-9)], sample_rate_hz=10e6
            )
        """
        HIGH_KEYS = {"h", "high", "1", "true"}
        result: list = []
        for level, duration_s in segments:
            n = max(1, round(float(duration_s) * float(sample_rate_hz)))
            val = high_normalized if str(level).lower() in HIGH_KEYS else low_normalized
            result.extend([val] * n)
        return result

    def upload_arb_data(self, channel: int, data: list, waveform_name: str = "LSRPULSE") -> bool:
        """
        Upload arbitrary waveform data given as a list of voltage values.

        Wraps upload_arb_waveform() with automatic amplitude/offset calculation.
        The data list should contain the target output voltages in volts
        (e.g. [3.3, 0.0, 3.3, 0.0] for a 3.3 V TTL pattern).

        Args:
            channel: Channel number (1 or 2).
            data: List of voltage values (floats). Must have 2–16,384 elements.
            waveform_name: Name to store on the instrument.

        Returns:
            True if upload succeeded, False on error.
        """
        try:
            if not data:
                raise ValueError("data list is empty")
            v_max = max(float(v) for v in data)
            v_min = min(float(v) for v in data)
            amplitude_v = max(v_max - v_min, 1e-6)  # avoid divide-by-zero
            offset_v = (v_max + v_min) / 2.0
            half = amplitude_v / 2.0
            normalized = [(float(v) - offset_v) / half for v in data]
            return self.upload_arb_waveform(
                channel=channel,
                samples_normalized=normalized,
                waveform_name=waveform_name,
                amplitude_v=amplitude_v,
                offset_v=offset_v,
            )
        except Exception as exc:
            print(f"Error in upload_arb_data: {exc}")
            return False

    def upload_csv_waveform(self, channel: int, csv_filename: str, waveform_name: str = "LSRPULSE") -> bool:
        """
        Upload an arbitrary waveform from a CSV file (one voltage value per line or comma-separated).

        Wraps upload_arb_data() with CSV parsing. Amplitude and offset are derived
        automatically from the data range.

        Args:
            channel: Channel number (1 or 2).
            csv_filename: Path to CSV file containing voltage values.
            waveform_name: Name to store on the instrument.

        Returns:
            True if upload succeeded, False on error.
        """
        try:
            with open(csv_filename, "r") as fh:
                raw = fh.read()
            values: list = []
            for token in raw.replace("\n", ",").split(","):
                token = token.strip()
                if token:
                    try:
                        values.append(float(token))
                    except ValueError:
                        pass
            if not values:
                raise ValueError("CSV file contains no numeric data")
            return self.upload_arb_data(channel=channel, data=values, waveform_name=waveform_name)
        except Exception as exc:
            print(f"Error uploading CSV waveform: {exc}")
            return False

    def set_arb_waveform(self, channel: int, waveform_name: str = "LSRPULSE", index: int = 0) -> None:
        """
        Select an already-uploaded arbitrary waveform by name and set output to ARB mode.

        This only selects; it does not upload data. To upload, call upload_arb_waveform().

        Args:
            channel: Channel number (1 or 2).
            waveform_name: Name of the waveform previously uploaded (ARWV NAME,<name>).
            index: Unused for user waveforms on SDG1000X (kept for API compatibility).
        """
        pref = self._ch_prefix(channel)
        self.write(f"{pref}ARWV NAME,{waveform_name}")
        self.write(f"{pref}BSWV WVTP,ARB")

    def list_arb_waveforms(self, channel: int) -> Optional[str]:
        """Query the current arbitrary waveform type/name for the channel."""
        try:
            pref = self._ch_prefix(channel)
            return self.query(f"{pref}ARWV?")
        except Exception as exc:
            print(f"Error querying ARB waveforms: {exc}")
            return None


def safe_float_or_str(val: Union[str, float, int]) -> Union[str, float]:
    return val if isinstance(val, str) else float(val)


# if __name__ == "__main__":
#     """
#     Basic test:
#       - Connect
#       - Reset, clear
#       - Set CH1 to SINE 1 kHz, 1 Vpp, 0 V offset
#       - Turn on output
#       - Change to SQUARE 1 kHz, 1 Vpp, 50% duty
#       - Configure burst for 5 cycles per trigger on BUS (software)
#       - Issue a software trigger
#       - Disable burst, turn off, disconnect
#     """
#     # Update with your VISA resource:
#     VISA_RESOURCE = "USB0::0xF4EC::0x1103::SDG1XCAQ3R3184::INSTR"

#     gen = SiglentSDG1032X(resource=VISA_RESOURCE)

#     if not gen.connect():
#         raise SystemExit("Failed to connect to the generator.")

#     try:
#         print("Connected to:", gen.idn())
#         gen.clear_status()
#         gen.reset()
#         gen.opc()

#         # Set CH1 basic sine
#         gen.set_basic_waveform(
#             channel=1,
#             wvtype="SINE",
#             frequency="1KHZ",
#             amplitude="1VPP",
#             offset="0V",
#             phase_deg=0,
#         )
#         gen.output(1, True)

#         time.sleep(0.5)

#         # Change to square with duty
#         gen.set_basic_waveform(
#             channel=1,
#             wvtype="SQUARE",
#             frequency="1KHZ",
#             amplitude="1VPP",
#             offset="0V",
#             duty_cycle=50,
#         )

#         # Example: add DC offset for laser bias (be careful with your hardware!)
#         # gen.set_offset(1, "1.5V")

#         # Configure burst: 5 cycles per trigger, BUS/software-triggered
#         gen.enable_burst(channel=1, mode="NCYC", cycles=5, trigger_source="BUS")
#         time.sleep(0.2)

#         # Fire a software trigger
#         print("Issuing software trigger...")
#         gen.trigger_now(1)

#         time.sleep(1.0)

#         # Clean up: disable burst, output off
#         gen.disable_burst(1)
#         gen.output(1, False)

#         # Check for instrument errors
#         err = gen.error_query()
#         if not err.startswith("0"):
#             print("Instrument reported error:", err)
#         else:
#             print("No instrument errors reported.")
#     finally:
#         gen.disconnect()
#         print("Disconnected.")

import numpy as np
def binary_to_pulses(binary_string: str, high: float = 2.0, low: float = 0.0,
                     samples_per_bit: int = 200) -> list:
    """
    Convert a binary string into a flat pulse waveform (no staircase).
    """
    data = []
    for bit in binary_string:
        val = high if bit == "1" else low
        data.extend([val] * samples_per_bit)
    return data


if __name__ == "__main__":
    VISA_RESOURCE = "USB0::0xF4EC::0x1103::SDG1XCAQ3R3184::INSTR"
    gen = SiglentSDG1032X(resource=VISA_RESOURCE)

    if not gen.connect():
        raise SystemExit("Failed to connect to generator.")

    try:
        print("Connected to:", gen.idn())
        gen.clear_status()
        gen.reset()
        gen.opc()

        # --- Step 1: make a binary waveform (4 bits)
        binary_pattern = "1000"   # Example pattern
        waveform = binary_to_pulses(binary_pattern, high=2.0, low=0.0, samples_per_bit=400)

        # --- Step 2: upload as ARB
        gen.upload_arb_data(channel=1, data=waveform, waveform_name="BINARY")

        # --- Step 3: select ARB waveform
        gen.set_arb_waveform(channel=1, waveform_name="BINARY", index=3)

        # --- Step 4: enable burst mode for 4 pulses
        gen.enable_burst(channel=1, mode="NCYC", cycles=1, trigger_source="BUS")

        # set amplitude
        #set offfset 1/2 ampplitude]
        # set bnurst mode 
        # # set cycles 4
        #set burst period >10s
        #set trigger external
        #set trig delay/trig out?
        

        # --- Step 5: output on
        gen.output(1, True)

        print("Triggering 4 pulses...")
        gen.trigger_now(1)

        # Wait for them to play
        time.sleep(1.0)

        gen.disable_burst(1)
        gen.output(1, False)

        # Check error status
        print("Instrument status:", gen.error_query())
    finally:
        gen.disconnect()
