"""
HP4140B pA Meter/DC Voltage Source Controller

This module provides a Python interface for controlling the HP4140B pA Meter/DC Voltage Source
via GPIB (IEEE 488) communication. The HP4140B is a precision instrument used for measuring
very small currents (picoampere range) and sourcing DC voltages.

Key Features:
- Voltage source configuration and control
- Current source configuration and control
- Voltage and current measurement
- Output enable/disable control
- Voltage ramping for safe operation

GPIB Communication:
- The HP4140B uses standard GPIB commands (not SCPI)
- Commands require newline termination (\n)
- Typical GPIB address: 17 (default, configurable via DIP switches)
- Commands used: CN, CL, DV, DI, TV, TI, DO

Author: Generated for Switchbox_GUI project
"""

import time
import numpy as np
import pyvisa


class HP4140BController:
    """
    Controller for HP4140B pA Meter/DC Voltage Source via GPIB.
    
    The HP4140B is an older HP instrument that uses proprietary GPIB commands
    (not SCPI). Commands are terminated with newline characters.
    
    Command Reference:
    - CN <channel>: Connect (enable output) for specified channel
    - CL <channel>: Close (disable output) for specified channel
    - DV <ch>,<range>,<voltage>,<compliance>: Define Voltage source
    - DI <ch>,<range>,<current>,<compliance>: Define Current source
    - TV <channel>,<mode>: Trigger Voltage measurement
    - TI <channel>,<mode>: Trigger Current measurement
    - DO <channel>: Data Output (read measurement data)
    
    Args:
        gpib_address: GPIB address string (e.g., "GPIB0::17::INSTR")
        timeout_s: Communication timeout in seconds
        append_semicolon: If True, append semicolon to commands (usually not needed)
    """

    def __init__(
        self,
        gpib_address: str = "GPIB0::17::INSTR",
        timeout_s: float = 5.0,
        append_semicolon: bool = False,
    ) -> None:
        self._append_semicolon = append_semicolon
        self.rm = None
        self.inst = None
        self.gpib_address = gpib_address

        try:
            self.rm = pyvisa.ResourceManager()
            self.inst = self.rm.open_resource(gpib_address)
            self.inst.timeout = int(timeout_s * 1000)
            # HP4140B requires newline termination for commands (standard for HP instruments)
            self.inst.write_termination = "\n"
            # Responses are terminated with newline
            self.inst.read_termination = "\n"
            # Add small delay after connection to allow instrument to initialize
            time.sleep(0.1)
            print(f"HP4140B: GPIB session opened at {gpib_address}")
        except Exception as exc:
            print(f"HP4140B: Failed to open GPIB session: {exc}")
            self.inst = None
            raise

    def _format_cmd(self, cmd: str) -> str:
        """Format command with optional semicolon suffix."""
        return f"{cmd};" if self._append_semicolon else cmd

    def write(self, cmd: str) -> None:
        """
        Send a command to the instrument.
        
        Args:
            cmd: Command string to send
            
        Raises:
            RuntimeError: If instrument is not connected
        """
        if not self.inst:
            raise RuntimeError("HP4140B not connected")
        formatted_cmd = self._format_cmd(cmd)
        self.inst.write(formatted_cmd)
        # Small delay after write to allow instrument to process command
        time.sleep(0.01)

    def query(self, cmd: str) -> str:
        """
        Send a command and read the response.
        
        Args:
            cmd: Command string to send
            
        Returns:
            Response string from instrument (stripped of whitespace)
            
        Raises:
            RuntimeError: If instrument is not connected
        """
        if not self.inst:
            raise RuntimeError("HP4140B not connected")
        formatted_cmd = self._format_cmd(cmd)
        response = self.inst.query(formatted_cmd)
        return response.strip()

    def enable_output(self, enable: bool = True, channel: int = 1) -> None:
        """
        Enable or disable output for specified channel.
        
        This method is compatible with the IVControllerManager interface which
        calls enable_output(enable: bool). For HP4140B-specific usage, channel
        can also be specified.
        
        Args:
            enable: If True, enable output (CN command); if False, disable (CL command)
            channel: Channel number (typically 1 or 2). Defaults to 1.
        """
        if enable:
            self.write(f"CN {channel}")
        else:
            self.write(f"CL {channel}")

    def disable_output(self, channel: int = 1) -> None:
        """
        Disable output for specified channel (CL command).
        
        This is a convenience method for explicit disable. You can also use
        enable_output(enable=False, channel=channel).
        
        Args:
            channel: Channel number (typically 1 or 2)
        """
        self.write(f"CL {channel}")

    def configure_voltage_source(
        self, 
        channel: int = 1, 
        range_code: int = 0, 
        voltage_v: float = 0.0, 
        compliance_a: float = 1e-3
    ) -> None:
        """
        Configure voltage source (DV command).
        
        Args:
            channel: Channel number (typically 1 or 2)
            range_code: Voltage range code (refer to HP4140B manual)
            voltage_v: Voltage in volts
            compliance_a: Current compliance limit in amperes
        """
        # Format voltage and compliance with appropriate precision
        self.write(f"DV {channel},{range_code},{voltage_v:.6e},{compliance_a:.6e}")

    def configure_current_source(
        self, 
        channel: int = 1, 
        range_code: int = 0, 
        current_a: float = 0.0, 
        compliance_v: float = 10.0
    ) -> None:
        """
        Configure current source (DI command).
        
        Args:
            channel: Channel number (typically 1 or 2)
            range_code: Current range code (refer to HP4140B manual)
            current_a: Current in amperes
            compliance_v: Voltage compliance limit in volts
        """
        # Format current and compliance with appropriate precision
        self.write(f"DI {channel},{range_code},{current_a:.6e},{compliance_v:.6e}")

    def trigger_voltage_measure(self, channel: int = 1, mode: int = 0) -> None:
        """
        Trigger voltage measurement (TV command).
        
        Args:
            channel: Channel number (typically 1 or 2)
            mode: Measurement mode (refer to HP4140B manual, typically 0)
        """
        self.write(f"TV {channel},{mode}")

    def trigger_current_measure(self, channel: int = 1, mode: int = 0) -> None:
        """
        Trigger current measurement (TI command).
        
        Args:
            channel: Channel number (typically 1 or 2)
            mode: Measurement mode (refer to HP4140B manual, typically 0)
        """
        self.write(f"TI {channel},{mode}")

    def read_data(self, channel: int = 1):
        """
        Read measurement data from instrument (DO command).
        
        The DO command returns comma-separated values:
        - Status code
        - Voltage value
        - Current value
        
        Args:
            channel: Channel number (typically 1 or 2)
            
        Returns:
            Tuple of (status, voltage_v, current_a)
            - status: Status string
            - voltage_v: Voltage in volts (float)
            - current_a: Current in amperes (float)
        """
        raw = self.query(f"DO {channel}")
        # Parse comma-separated response
        parts = [p.strip() for p in raw.split(',')]
        status = parts[0] if len(parts) >= 1 else ""
        try:
            voltage_v = float(parts[1]) if len(parts) >= 2 else float("nan")
        except (ValueError, IndexError):
            voltage_v = float("nan")
        try:
            current_a = float(parts[2]) if len(parts) >= 3 else float("nan")
        except (ValueError, IndexError):
            current_a = float("nan")
        return status, voltage_v, current_a

    def set_voltage(self, voltage: float, Icc: float = 1e-3, channel: int = 1, range_code: int = 0) -> None:
        """
        Set voltage source with specified compliance.
        
        This method is compatible with the IVControllerManager interface.
        It enables output and configures the voltage source.
        
        Args:
            voltage: Voltage in volts
            Icc: Current compliance limit in amperes (default: 1e-3)
            channel: Channel number (typically 1 or 2). Defaults to 1.
            range_code: Voltage range code (refer to HP4140B manual). Defaults to 0.
        """
        self.enable_output(enable=True, channel=channel)
        self.configure_voltage_source(channel=channel, range_code=range_code, voltage_v=voltage, compliance_a=Icc)

    def set_current(self, current: float, Vcc: float = 10.0, channel: int = 1, range_code: int = 0) -> None:
        """
        Set current source with specified compliance.
        
        This method is compatible with the IVControllerManager interface.
        It enables output and configures the current source.
        
        Args:
            current: Current in amperes
            Vcc: Voltage compliance limit in volts (default: 10.0)
            channel: Channel number (typically 1 or 2). Defaults to 1.
            range_code: Current range code (refer to HP4140B manual). Defaults to 0.
        """
        self.enable_output(enable=True, channel=channel)
        self.configure_current_source(channel=channel, range_code=range_code, current_a=current, compliance_v=Vcc)

    def measure_voltage(self, channel: int = 1) -> float:
        """
        Measure voltage on specified channel.
        
        Args:
            channel: Channel number (typically 1 or 2)
            
        Returns:
            Voltage in volts (float)
        """
        self.trigger_voltage_measure(channel=channel, mode=0)
        _, v, _ = self.read_data(channel)
        return v

    def measure_current(self, channel: int = 1) -> float:
        """
        Measure current on specified channel.
        
        Args:
            channel: Channel number (typically 1 or 2)
            
        Returns:
            Current in amperes (float)
        """
        self.trigger_current_measure(channel=channel, mode=0)
        _, _, i = self.read_data(channel)
        return i

    def measure_both(self, channel: int = 1):
        """
        Measure both voltage and current on specified channel.
        
        Args:
            channel: Channel number (typically 1 or 2)
            
        Returns:
            Tuple of (voltage_v, current_a)
        """
        self.trigger_voltage_measure(channel=channel, mode=0)
        self.trigger_current_measure(channel=channel, mode=0)
        _, v, i = self.read_data(channel)
        return v, i

    def voltage_ramp(self, target_voltage_v: float, steps: int = 30, pause_s: float = 0.02, compliance_a: float = 1e-3, channel: int = 1, range_code: int = 0) -> None:
        """
        Ramp voltage from current value to target value.
        
        Args:
            target_voltage_v: Target voltage in volts
            steps: Number of steps for ramp (default: 30)
            pause_s: Pause between steps in seconds (default: 0.02)
            compliance_a: Current compliance limit in amperes (default: 1e-3)
            channel: Channel number (typically 1 or 2). Defaults to 1.
            range_code: Voltage range code (refer to HP4140B manual). Defaults to 0.
        """
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
        """
        Safely shutdown instrument by ramping to zero and disabling output.
        
        Args:
            channel: Channel number (typically 1 or 2). Defaults to 1.
        """
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
        """
        Close instrument connection and clean up resources.
        """
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
        """
        Get instrument identification.
        
        Note: HP4140B does not support *IDN? command, so this returns
        a fixed string. To verify communication, try sending a simple
        command like reading data.
        
        Returns:
            Instrument identification string
        """
        return "HP4140B"

    def beep(self, frequency: float = 1000, duration: float = 0.2) -> None:
        """
        Generate beep sound from instrument.
        
        Note: The HP4140B BEEP command does not accept parameters.
        The frequency and duration parameters are ignored.
        
        Args:
            frequency: Ignored (kept for compatibility)
            duration: Ignored (kept for compatibility)
        """
        try:
            self.write("BEEP")
        except Exception as exc:
            # Beep command may not be available on all instruments
            print(f"HP4140B: Beep command failed: {exc}")

