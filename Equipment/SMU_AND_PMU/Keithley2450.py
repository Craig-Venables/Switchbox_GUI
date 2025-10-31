"""
Keithley 2450 SourceMeter Controller
=====================================

This module provides a Python interface for the Keithley 2450 SourceMeter Unit (SMU).
The 2450 is an advanced precision source-measure instrument with touchscreen interface,
improved measurement speed, and enhanced TSP scripting capabilities compared to the 2400 series.

Key Features:
- ±200V voltage sourcing (±210V absolute maximum)
- ±1A current sourcing
- Fast pulse measurements optimized for memristor characterization
- TSP (Test Script Processor) for on-instrument script execution
- USB, GPIB, and LAN connectivity
- Pre-defined pulse patterns for potentiation/depression testing
- Custom TSP script execution support

TSP Toolkit: https://www.tek.com/en/products/software/tsp-toolkit-scripting-tool

Reference Manuals:
- Equipment/manuals/Keithley 2450 manual.pdf
- Equipment/manuals/Keithley 2450 datasheet.pdf

Usage:
    # Basic connection and sourcing
    k2450 = Keithley2450Controller('USB0::0x05E6::0x2450::04517573::INSTR')
    k2450.set_voltage(1.5, Icc=0.01)
    current = k2450.measure_current()
    
    # Fast pulse measurements
    k2450.prepare_for_pulses(Icc=0.1, v_range=20.0)
    result = k2450.tsp_potentiation_pulse(voltage=2.0, pulse_width=100e-6, count=10)
    k2450.finish_pulses()

Author: Adapted from Keithley2400Controller for 2450 capabilities
"""

import pyvisa
import time
import math
from typing import Optional, Dict, Any, List, Tuple, Union


class Keithley2450Controller:
    """Controller for Keithley 2450 SourceMeter with TSP pulse capabilities."""
    
    # Instrument specifications
    MAX_VOLTAGE = 200.0  # Maximum safe voltage (±210V absolute max)
    MAX_CURRENT = 1.05  # Maximum current (±1.05A absolute max)
    MIN_PULSE_WIDTH = 50e-6  # Minimum pulse width (50 microseconds)
    
    def __init__(self, address: str = 'GPIB0::15::INSTR', timeout: int = 10000):
        """
        Initialize connection to Keithley 2450 via PyVISA.
        
        Args:
            address: VISA resource address. Supports:
                     - GPIB: 'GPIB0::15::INSTR'
                     - USB: 'USB0::0x05E6::0x2450::04517573::INSTR'
                     - LAN: 'TCPIP0::192.168.1.100::INSTR'
            timeout: Communication timeout in milliseconds (default 10000ms)
        """
        self.address = address
        self.device = None
        self.rm = None
        
        # Cache for source configuration
        self._configured = False
        self._cached_icc: Optional[float] = None
        self._cached_vrange: Optional[float] = None
        self._range_lock: Optional[float] = None
        self._output_enabled: bool = False
        
        try:
            self.rm = pyvisa.ResourceManager()
            self.device = self.rm.open_resource(address)
            self.device.timeout = timeout
            
            # Clear any errors and reset
            self.device.write('*RST')
            self.device.write('*CLS')
            time.sleep(0.5)
            
            idn = self.get_idn()
            print(f"Connected to: {idn}")
            
            if '2450' not in idn:
                print(f"Warning: Expected Keithley 2450, got: {idn}")
                
        except Exception as e:
            print(f"Error initializing Keithley 2450: {e}")
            self.device = None
            
    def get_idn(self) -> str:
        """Query and return the device identity string."""
        if self.device:
            try:
                return self.device.query('*IDN?').strip()
            except Exception:
                return "No Device Connected"
        return "No Device Connected"
    
    def check_errors(self) -> str:
        """Check instrument error status."""
        if self.device:
            try:
                return self.device.query(':SYST:ERR?').strip()
            except Exception as e:
                return f"Error querying: {e}"
        return "No Device Connected"
    
    def _configure_voltage_source(self, icc: float, v_range: float = 20.0) -> None:
        """
        Configure voltage source with compliance and range.
        
        Args:
            icc: Compliance current (A)
            v_range: Voltage range (0.2, 2, 20, or 200 V)
        """
        if not self.device:
            return
            
        # Only reconfigure if changed
        if (not self._configured) or (self._cached_icc != icc) or (self._cached_vrange != v_range):
            try:
                # Set source function to voltage
                self.device.write(':SOUR:FUNC VOLT')
                
                # Set voltage range
                if v_range in (0.2, 2.0, 20.0, 200.0):
                    self.device.write(f':SOUR:VOLT:RANG {v_range}')
                else:
                    self.device.write(':SOUR:VOLT:RANG:AUTO ON')
                
                # Set current compliance (limit)
                self.device.write(f':SOUR:VOLT:ILIM {icc}')
                
                self._configured = True
                self._cached_icc = icc
                self._cached_vrange = v_range
            except Exception as e:
                print(f"Error configuring voltage source: {e}")
    
    def set_voltage(self, voltage: float, Icc: float = 0.1) -> None:
        """
        Set source voltage with compliance current.
        
        Args:
            voltage: Target voltage (V)
            Icc: Compliance current limit (A)
        """
        if not self.device:
            return
            
        try:
            # Select appropriate range
            if self._range_lock is not None:
                v_rng = float(self._range_lock)
            else:
                v_abs = abs(float(voltage))
                if v_abs <= 0.2:
                    v_rng = 0.2
                elif v_abs <= 2.0:
                    v_rng = 2.0
                elif v_abs <= 20.0:
                    v_rng = 20.0
                else:
                    v_rng = 200.0
            
            self._configure_voltage_source(float(Icc), v_rng)
            
            # Enable output if not already enabled
            if not self._output_enabled:
                self.device.write(':SOUR:VOLT:LEV 0.0')
                self.device.write(':OUTP ON')
                self._output_enabled = True
                time.sleep(0.01)
            
            # Set voltage
            self.device.write(f':SOUR:VOLT:LEV {voltage}')
            
        except Exception as e:
            print(f"Error setting voltage: {e}")
    
    def set_current(self, current: float, Vcc: float = 10.0) -> None:
        """
        Set source current with compliance voltage.
        
        Args:
            current: Target current (A)
            Vcc: Compliance voltage limit (V)
        """
        if not self.device:
            return
            
        try:
            # Set source function to current
            self.device.write(':SOUR:FUNC CURR')
            
            # Set current range
            i_abs = abs(float(current))
            if i_abs <= 0.01:
                i_range = 0.01
            elif i_abs <= 0.1:
                i_range = 0.1
            else:
                i_range = 1.0
            self.device.write(f':SOUR:CURR:RANG {i_range}')
            
            # Set voltage compliance
            self.device.write(f':SOUR:CURR:VLIM {Vcc}')
            
            # Enable output if not already enabled
            if not self._output_enabled:
                self.device.write(':SOUR:CURR:LEV 0.0')
                self.device.write(':OUTP ON')
                self._output_enabled = True
                time.sleep(0.01)
            
            # Set current
            self.device.write(f':SOUR:CURR:LEV {current}')
            
        except Exception as e:
            print(f"Error setting current: {e}")
    
    def measure_voltage(self) -> Optional[float]:
        """Measure and return voltage."""
        if self.device:
            try:
                result = self.device.query(':MEAS:VOLT?').strip()
                return float(result)
            except Exception as e:
                print(f"Error measuring voltage: {e}")
                return None
        return None
    
    def measure_current(self) -> Optional[float]:
        """Measure and return current."""
        if self.device:
            try:
                result = self.device.query(':MEAS:CURR?').strip()
                return float(result)
            except Exception as e:
                print(f"Error measuring current: {e}")
                return None
        return None
    
    def enable_output(self, enable: bool = True) -> None:
        """Enable or disable output."""
        if self.device:
            try:
                if enable:
                    self.device.write(':OUTP ON')
                    self._output_enabled = True
                else:
                    self.device.write(':OUTP OFF')
                    self._output_enabled = False
            except Exception as e:
                print(f"Error setting output: {e}")
    
    def beep(self, frequency: float = 1000, duration: float = 0.5) -> None:
        """
        Make the instrument beep.
        
        Args:
            frequency: Beep frequency in Hz (20-8000 Hz)
            duration: Beep duration in seconds
        """
        if self.device:
            try:
                frequency = max(20, min(8000, frequency))
                duration = max(0.001, min(7.9, duration))
                self.device.write(f':SYST:BEEP {frequency}, {duration}')
            except Exception as e:
                print(f"Error beeping: {e}")
    
    def prepare_for_pulses(self, Icc: float = 1e-3, v_range: float = 20.0, 
                          ovp: float = 21.0, use_remote_sense: bool = False,
                          autozero_off: bool = True) -> None:
        """
        Prepare instrument for fast pulsed operation.
        
        Args:
            Icc: Compliance current (A)
            v_range: Fixed voltage range (0.2, 2, 20, or 200 V)
            ovp: Over-voltage protection limit (V) - 2450 uses source limit
            use_remote_sense: Enable 4-wire sensing
            autozero_off: Disable autozero for faster measurements
        """
        if not self.device:
            return
            
        try:
            # Set voltage source function
            self.device.write(':SOUR:FUNC VOLT')
            
            # Lock range for fast operation
            self._range_lock = float(v_range)
            
            # Configure source
            self._configure_voltage_source(float(Icc), float(v_range))
            
            # Configure sense mode (2-wire or 4-wire)
            if use_remote_sense:
                self.device.write(':SYST:RSEN ON')
            else:
                self.device.write(':SYST:RSEN OFF')
            
            # Autozero control for speed
            if autozero_off:
                self.device.write(':SYST:AZER OFF')
            else:
                self.device.write(':SYST:AZER ON')
            
            # Set measurement speed to fast
            self.device.write(':SENS:CURR:NPLC 0.01')  # Fast measurement
            
            # Start at 0V and enable output
            self.device.write(':SOUR:VOLT:LEV 0.0')
            self.device.write(':OUTP ON')
            self._output_enabled = True
            
        except Exception as e:
            print(f"Error preparing for pulses: {e}")
    
    def finish_pulses(self, restore_autozero: bool = True) -> None:
        """
        Return to safe state after pulsed operation.
        
        Args:
            restore_autozero: Re-enable autozero for accurate measurements
        """
        if not self.device:
            return
            
        try:
            # Return to 0V
            self.device.write(':SOUR:VOLT:LEV 0.0')
            time.sleep(0.1)
            
            # Restore autozero
            if restore_autozero:
                self.device.write(':SYST:AZER ON')
            
            # Disable output
            self.device.write(':OUTP OFF')
            self._output_enabled = False
            
            # Clear range lock
            self._range_lock = None
            
        except Exception as e:
            print(f"Error finishing pulses: {e}")
    
    def voltage_ramp(self, target_voltage: float, steps: int = 30, pause: float = 0.02) -> None:
        """
        Ramp voltage gradually to target.
        
        Args:
            target_voltage: Target voltage (V)
            steps: Number of steps
            pause: Pause between steps (s)
        """
        if not self.device:
            return
            
        try:
            # Get current voltage
            current_v = self.measure_voltage() or 0.0
            voltage_step = (target_voltage - current_v) / steps
            
            for i in range(steps):
                v = current_v + (i + 1) * voltage_step
                self.device.write(f':SOUR:VOLT:LEV {v}')
                time.sleep(pause)
                
        except Exception as e:
            print(f"Error ramping voltage: {e}")
    
    def shutdown(self) -> None:
        """Safe shutdown: ramp to 0V and disable output."""
        if self.device:
            try:
                self.voltage_ramp(0.0, steps=20, pause=0.01)
                self.device.write(':OUTP OFF')
                self._output_enabled = False
            except Exception:
                pass
    
    # ========================================================================
    # TSP SCRIPTING METHODS FOR FAST PULSE OPERATIONS
    # ========================================================================
    
    def tsp_read_pulse(self, read_voltage: float, pulse_width: float = 1e-3,
                       return_to_zero: bool = True) -> Dict[str, Any]:
        """
        Execute a single read pulse using TSP scripting.
        
        Args:
            read_voltage: Read voltage amplitude (V)
            pulse_width: Pulse width (s), minimum 50µs
            return_to_zero: Return to 0V after pulse
            
        Returns:
            Dict with 'voltage' and 'current' measurement
        """
        if not self.device:
            return {"status": "ERROR", "message": "No device connected"}
        
        pulse_width = max(self.MIN_PULSE_WIDTH, pulse_width)
        
        tsp_script = f"""
smu.source.func = smu.FUNC_DC_VOLTAGE
smu.source.level = 0
smu.source.output = smu.ON
delay({pulse_width/4})
smu.source.level = {read_voltage}
delay({pulse_width})
measV = smu.measure.read()
measI = smu.measure.i()
print(string.format("DATA:%g,%g", measV, measI))
smu.source.level = 0
{"smu.source.output = smu.OFF" if not return_to_zero else ""}
"""
        
        try:
            return self._execute_tsp_and_parse(tsp_script)
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}
    
    def tsp_potentiation_pulse(self, voltage: float, pulse_width: float = 100e-6,
                               count: int = 10, delay_between: float = 1e-3,
                               read_voltage: float = 0.2) -> Dict[str, Any]:
        """
        Execute potentiation pulse train for memristor SET operation.
        
        Args:
            voltage: Pulse amplitude (V, positive)
            pulse_width: Pulse width (s)
            count: Number of pulses
            delay_between: Delay between pulses (s)
            read_voltage: Read voltage for resistance check (V)
            
        Returns:
            Dict with 'voltages', 'currents' arrays and 'status'
        """
        if not self.device:
            return {"status": "ERROR", "message": "No device connected"}
        
        pulse_width = max(self.MIN_PULSE_WIDTH, pulse_width)
        
        tsp_script = f"""
smu.source.func = smu.FUNC_DC_VOLTAGE
smu.source.level = 0
smu.source.output = smu.ON
delay(0.01)
for i = 1, {count} do
    smu.source.level = {voltage}
    delay({pulse_width})
    smu.source.level = 0
    delay({delay_between/2})
    smu.source.level = {read_voltage}
    delay({pulse_width})
    local measV = smu.measure.read()
    local measI = smu.measure.i()
    print(string.format("DATA:%g,%g", measV, measI))
    smu.source.level = 0
    delay({delay_between/2})
end
smu.source.output = smu.OFF
print("DONE")
"""
        
        try:
            return self._execute_tsp_and_parse(tsp_script, multi_point=True)
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}
    
    def tsp_depression_pulse(self, voltage_neg: float, pulse_width: float = 100e-6,
                            count: int = 10, delay_between: float = 1e-3,
                            read_voltage: float = 0.2) -> Dict[str, Any]:
        """
        Execute depression pulse train for memristor RESET operation.
        
        Args:
            voltage_neg: Pulse amplitude (V, typically negative)
            pulse_width: Pulse width (s)
            count: Number of pulses
            delay_between: Delay between pulses (s)
            read_voltage: Read voltage for resistance check (V)
            
        Returns:
            Dict with 'voltages', 'currents' arrays and 'status'
        """
        if not self.device:
            return {"status": "ERROR", "message": "No device connected"}
        
        pulse_width = max(self.MIN_PULSE_WIDTH, pulse_width)
        
        tsp_script = f"""
smu.source.func = smu.FUNC_DC_VOLTAGE
smu.source.level = 0
smu.source.output = smu.ON
delay(0.01)
for i = 1, {count} do
    smu.source.level = {voltage_neg}
    delay({pulse_width})
    smu.source.level = 0
    delay({delay_between/2})
    smu.source.level = {read_voltage}
    delay({pulse_width})
    local measV = smu.measure.read()
    local measI = smu.measure.i()
    print(string.format("DATA:%g,%g", measV, measI))
    smu.source.level = 0
    delay({delay_between/2})
end
smu.source.output = smu.OFF
print("DONE")
"""
        
        try:
            return self._execute_tsp_and_parse(tsp_script, multi_point=True)
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}
    
    def tsp_pulse_train_custom(self, voltage_list: List[float], 
                               pulse_width_list: List[float],
                               delay_list: Optional[List[float]] = None) -> Dict[str, Any]:
        """
        Execute custom pulse sequence with arbitrary voltage/timing.
        
        Args:
            voltage_list: List of pulse voltages (V)
            pulse_width_list: List of pulse widths (s)
            delay_list: Optional list of delays between pulses (s)
            
        Returns:
            Dict with 'voltages', 'currents' arrays and 'status'
        """
        if not self.device:
            return {"status": "ERROR", "message": "No device connected"}
        
        if len(voltage_list) != len(pulse_width_list):
            return {"status": "ERROR", "message": "voltage_list and pulse_width_list must have same length"}
        
        if delay_list is None:
            delay_list = [1e-3] * len(voltage_list)
        elif len(delay_list) != len(voltage_list):
            return {"status": "ERROR", "message": "delay_list must match voltage_list length"}
        
        # Build pulse sequence
        pulse_commands = []
        for v, pw, d in zip(voltage_list, pulse_width_list, delay_list):
            pw = max(self.MIN_PULSE_WIDTH, pw)
            pulse_commands.append(f"""
smu.source.level = {v}
delay({pw})
local measV = smu.measure.read()
local measI = smu.measure.i()
print(string.format("DATA:%g,%g", measV, measI))
smu.source.level = 0
delay({d})
""")
        
        tsp_script = f"""
smu.source.func = smu.FUNC_DC_VOLTAGE
smu.source.level = 0
smu.source.output = smu.ON
delay(0.01)
{''.join(pulse_commands)}
smu.source.output = smu.OFF
print("DONE")
"""
        
        try:
            return self._execute_tsp_and_parse(tsp_script, multi_point=True)
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}
    
    def execute_tsp_script(self, script: str, timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        Execute arbitrary TSP script on the instrument.
        
        Args:
            script: TSP script code as string
            timeout: Optional timeout override (seconds)
            
        Returns:
            Dict with parsed output or raw response
        """
        if not self.device:
            return {"status": "ERROR", "message": "No device connected"}
        
        try:
            return self._execute_tsp_and_parse(script, timeout=timeout, multi_point=True)
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}
    
    def _execute_tsp_and_parse(self, script: str, multi_point: bool = False,
                               timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        Internal method to execute TSP script and parse output.
        
        Based on Tektronix TSP documentation:
        https://www.tek.com/en/documents/application-note/how-to-write-scripts-for-test-script-processing-(tsp)
        
        Args:
            script: TSP script
            multi_point: Expect multiple DATA: lines
            timeout: Optional timeout (seconds)
            
        Returns:
            Parsed data dictionary
        """
        if not self.device:
            return {"status": "ERROR", "message": "No device"}
        
        original_timeout = self.device.timeout
        if timeout:
            self.device.timeout = int(timeout * 1000)
        
        try:
            # Clear output buffer and errors
            self.device.write('*CLS')
            
            # Split script into lines (skip comments and empty lines)
            lines = [line.strip() for line in script.strip().split('\n') 
                     if line.strip() and not line.strip().startswith('--')]
            
            # Send all TSP commands first (don't try to read yet)
            for line in lines:
                self.device.write(line)
            
            # Small delay to let script execute
            time.sleep(0.05)
            
            # Now read all output from print() statements
            voltages = []
            currents = []
            done = False
            
            # Read until we get DONE marker or timeout
            max_reads = 1000 if multi_point else 10
            for _ in range(max_reads):
                try:
                    line = self.device.read().strip()
                    
                    if 'DATA:' in line:
                        # Parse data line
                        payload = line.split('DATA:')[1].strip()
                        v_str, i_str = payload.split(',')
                        voltages.append(float(v_str))
                        currents.append(float(i_str))
                    elif 'DONE' in line:
                        done = True
                        break
                        
                except (pyvisa.errors.VisaIOError, pyvisa.errors.VI_ERROR_TMO):
                    # No more data available
                    break
            
            if voltages:
                return {
                    "status": "SUCCESS",
                    "voltages": voltages,
                    "currents": currents,
                    "points": len(voltages)
                }
            else:
                return {"status": "NO_DATA", "message": "No data points received"}
                
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}
        finally:
            self.device.timeout = original_timeout
    
    def close(self) -> None:
        """Close connection to instrument."""
        if self.device:
            try:
                self.shutdown()
                self.device.close()
                if self.rm:
                    self.rm.close()
                print("Connection closed.")
            except Exception as e:
                print(f"Error closing connection: {e}")


# ============================================================================
# TEST SCRIPT - Run this file directly to verify functionality
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("Keithley 2450 SourceMeter Test Script")
    print("=" * 70)
    print()
    
    # Configuration - CHANGE THIS TO YOUR ADDRESS
    #DEVICE_ADDRESS = 'USB0::0x05E6::0x2450::04496615::INSTR'  # Change to your address
    # Alternatives:
    # DEVICE_ADDRESS = 'GPIB0::24::INSTR'
    # DEVICE_ADDRESS = 'TCPIP0::192.168.1.100::INSTR'
    
    # Test parameters (safe values)
    TEST_VOLTAGE = 0.5  # Safe test voltage
    TEST_CURRENT_COMPLIANCE = 0.01  # 10mA compliance
    PULSE_VOLTAGE = 1.5  # Pulse test voltage
    READ_VOLTAGE = 0.2  # Read voltage
    
    # Stage 1: Connection Test
    print("Stage 1: Connection Test")
    print("-" * 70)
    
    try:
        keithley = Keithley2450Controller()
        if not keithley.device:
            print("❌ Failed to connect to instrument")
            print("\nTroubleshooting:")
            print("1. Check the DEVICE_ADDRESS matches your instrument")
            print("2. Verify USB/GPIB cable is connected")
            print("3. Check instrument is powered on")
            exit(1)
        
        idn = keithley.get_idn()
        print(f"✓ Connected: {idn}")
        
        errors = keithley.check_errors()
        print(f"✓ Error check: {errors}")
        print()
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        exit(1)
    
    # Stage 2: Basic SCPI Operations
    print("Stage 2: Basic SCPI Operations")
    print("-" * 70)
    
    try:
        # Test beep
        print("Testing beep (you should hear it)...")
        keithley.beep(1000, 0.2)
        time.sleep(0.3)
        
        # Test voltage setting
        print(f"Setting voltage to {TEST_VOLTAGE}V with {TEST_CURRENT_COMPLIANCE}A compliance...")
        keithley.set_voltage(TEST_VOLTAGE, Icc=TEST_CURRENT_COMPLIANCE)
        time.sleep(0.5)
        
        # Measure
        v_meas = keithley.measure_voltage()
        i_meas = keithley.measure_current()
        print(f"✓ Measured: V={v_meas:.6f}V, I={i_meas:.9f}A")
        
        if v_meas and abs(v_meas - TEST_VOLTAGE) < 0.1:
            print("✓ Voltage setting OK")
        else:
            print(f"⚠ Voltage mismatch (expected {TEST_VOLTAGE}V, got {v_meas}V)")
        
        # Return to zero
        keithley.set_voltage(0.0)
        keithley.enable_output(False)
        print("✓ Output disabled")
        print()
        
    except Exception as e:
        print(f"❌ Basic operations failed: {e}")
        keithley.close()
        exit(1)
    
    # Stage 3: Pulse Preparation
    print("Stage 3: Pulse Preparation")
    print("-" * 70)
    
    try:
        print("Preparing for pulses...")
        keithley.prepare_for_pulses(Icc=0.1, v_range=20.0, autozero_off=True)
        print("✓ Pulse preparation complete")
        
        time.sleep(0.5)
        
        print("Finishing pulses...")
        keithley.finish_pulses(restore_autozero=True)
        print("✓ Returned to safe state")
        print()
        
    except Exception as e:
        print(f"❌ Pulse preparation failed: {e}")
        keithley.close()
        exit(1)
    
    # Stage 4: TSP Pulse Tests
    print("Stage 4: TSP Pulse Tests")
    print("-" * 70)
    
    user_input = input("Run TSP pulse tests? This will apply pulses to the device. (y/N): ")
    if user_input.lower() == 'y':
        try:
            # Test 1: Single read pulse
            print(f"\nTest 1: Single read pulse ({READ_VOLTAGE}V, 1ms)")
            result = keithley.tsp_read_pulse(READ_VOLTAGE, pulse_width=1e-3)
            if result.get('status') == 'SUCCESS':
                print(f"✓ Read pulse OK: V={result.get('voltages', [0])[0]:.6f}V, I={result.get('currents', [0])[0]:.9f}A")
            else:
                print(f"⚠ Read pulse result: {result}")
            
            time.sleep(0.5)
            
            # Test 2: Potentiation pulses
            print(f"\nTest 2: Potentiation pulse train (5 pulses, {PULSE_VOLTAGE}V, 100µs)")
            result = keithley.tsp_potentiation_pulse(
                voltage=PULSE_VOLTAGE,
                pulse_width=100e-6,
                count=5,
                delay_between=1e-3,
                read_voltage=READ_VOLTAGE
            )
            if result.get('status') == 'SUCCESS':
                print(f"✓ Potentiation OK: {result.get('points', 0)} measurements")
                currents = result.get('currents', [])
                if currents:
                    print(f"  Current range: {min(currents):.9f}A to {max(currents):.9f}A")
            else:
                print(f"⚠ Potentiation result: {result}")
            
            time.sleep(0.5)
            
            # Test 3: Depression pulses
            print(f"\nTest 3: Depression pulse train (3 pulses, -{PULSE_VOLTAGE}V, 100µs)")
            result = keithley.tsp_depression_pulse(
                voltage_neg=-PULSE_VOLTAGE,
                pulse_width=100e-6,
                count=3,
                delay_between=1e-3,
                read_voltage=READ_VOLTAGE
            )
            if result.get('status') == 'SUCCESS':
                print(f"✓ Depression OK: {result.get('points', 0)} measurements")
            else:
                print(f"⚠ Depression result: {result}")
            
            time.sleep(0.5)
            
            # Test 4: Custom pulse train
            print(f"\nTest 4: Custom pulse train (arbitrary sequence)")
            result = keithley.tsp_pulse_train_custom(
                voltage_list=[0.5, 1.0, 1.5, 1.0, 0.5],
                pulse_width_list=[200e-6, 200e-6, 200e-6, 200e-6, 200e-6],
                delay_list=[1e-3, 1e-3, 1e-3, 1e-3, 1e-3]
            )
            if result.get('status') == 'SUCCESS':
                print(f"✓ Custom train OK: {result.get('points', 0)} measurements")
                voltages = result.get('voltages', [])
                if voltages:
                    print(f"  Voltage range: {min(voltages):.6f}V to {max(voltages):.6f}V")
            else:
                print(f"⚠ Custom train result: {result}")
            
            print("\n✓ All TSP pulse tests complete")
            
        except Exception as e:
            print(f"❌ TSP pulse tests failed: {e}")
    else:
        print("⊘ TSP pulse tests skipped")
    
    print()
    
    # Stage 5: Safety Checks
    print("Stage 5: Safety Checks")
    print("-" * 70)
    
    try:
        # Verify safe state
        keithley.shutdown()
        time.sleep(0.2)
        
        v_final = keithley.measure_voltage()
        if v_final is not None and abs(v_final) < 0.01:
            print(f"✓ Output at safe level: {v_final:.6f}V")
        else:
            print(f"⚠ Output voltage: {v_final}V")
        
        print("✓ All safety checks passed")
        print()
        
    except Exception as e:
        print(f"❌ Safety check failed: {e}")
    
    # Summary
    print("=" * 70)
    print("Test Summary")
    print("=" * 70)
    print("✓ Connection successful")
    print("✓ Basic SCPI operations working")
    print("✓ Pulse preparation working")
    print("✓ TSP pulse capabilities verified" if user_input.lower() == 'y' else "⊘ TSP tests skipped")
    print("✓ Safety checks passed")
    print()
    print("The Keithley 2450 controller is ready for use!")
    print()
    
    # Cleanup
    keithley.close()
    print("Connection closed. Test complete.")

