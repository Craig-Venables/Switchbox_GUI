"""
Keithley 2450 SourceMeter Controller
=====================================

This module provides a Python interface for the Keithley 2450 SourceMeter Unit (SMU).
The 2450 is an advanced precision source-measure instrument with touchscreen interface,
improved measurement speed, and SCPI pulse capabilities.

Key Features:
- ±200V voltage sourcing (±210V absolute maximum)
- ±1A current sourcing
- SCPI-based pulse measurements using SimpleLoop trigger model
- USB, GPIB, and LAN connectivity
- Compatible with K2461 pulse workflow (pulse_loop.py pattern)
- 2-wire and 4-wire resistance measurement modes

Pulse Methods:
- SCPI pulses (this file): Good for pulses >1ms, uses SimpleLoop trigger
- TSP pulses (Keithley2450_TSP.py): Best for pulses <1ms, ~50µs minimum width

Reference Manuals:
- Equipment/manuals/Keithley 2450 manual.pdf
- Equipment/manuals/Keithley 2450 datasheet.pdf

Usage:
    # Basic connection and sourcing
    k2450 = Keithley2450Controller('USB0::0x05E6::0x2450::04517573::INSTR')
    k2450.set_voltage(1.5, Icc=0.01)
    current = k2450.measure_current()
    
    # SCPI pulse measurements (Option A - this file)
    k2450.prepare_pulsing_voltage(voltage=1.0, width=1e-3, clim=0.1)
    k2450.send_pulse()
    
    # TSP pulse measurements (separate file for <1ms pulses)
    from Keithley2450_TSP import TSP_Pulses
    tsp = TSP_Pulses(k2450)
    tsp.voltage_pulse(1.0, 100e-6, clim=0.1)  # 100µs pulse
    
    # Measure with buffer
    k2450.prepare_measure_n(current=10e-6, num=10, nplc=2)
    k2450.trigger()
    time_arr, voltage, current = k2450.read_buffer(10)

Author: Adapted from Keithley2400Controller with K2461 buffer methods
"""

import pyvisa
import time
import math
import numpy as np
from typing import Optional, Dict, Any, List, Tuple, Union


class Keithley2450Controller:
    """Controller for Keithley 2450 SourceMeter with buffer-based pulse capabilities."""
    
    # Instrument specifications
    MAX_VOLTAGE = 200.0  # Maximum safe voltage (±210V absolute max)
    MAX_CURRENT = 1.05  # Maximum current (±1.05A absolute max)
    MIN_PULSE_WIDTH = 50e-6  # Minimum pulse width (50 microseconds)
    
    def __init__(self, address: str = 'GPIB0::15::INSTR', timeout: int = 10000):
        """
        Initialize connection to Keithley 2450 via PyVISA.
        
        Args:
            address: VISA resource address. Supports:
                     - GPIB: 'GPIB0::24::INSTR'
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
        self._tsp_mode: bool = False  # Track if in TSP mode to prevent SCPI commands
        
        try:
            self.rm = pyvisa.ResourceManager()
            self.device = self.rm.open_resource(address)
            self.device.timeout = timeout
            
            # Try to detect mode and clear errors
            # Try SCPI first (most common)
            try:
                self.device.write('*RST')
                self.device.write('*CLS')
                time.sleep(0.5)
            except Exception as e:
                # Might already be in TSP mode, try TSP clear
                try:
                    self.device.write('errorqueue.clear()')
                    self.device.write('reset()')
                    time.sleep(0.5)
                    self._tsp_mode = True
                    print("Note: Instrument was in TSP mode")
                except:
                    print(f"Warning: Could not reset instrument: {e}")
            
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
                # Try SCPI first
                return self.device.query('*IDN?').strip()
            except Exception:
                # Try TSP if SCPI fails
                try:
                    self.device.write('print(localnode.model .. "," .. localnode.serialno .. "," .. localnode.version)')
                    time.sleep(0.02)
                    return "KEITHLEY," + self.device.read().strip()
                except:
                    return "No Device Connected"
        return "No Device Connected"
    
    def _check_scpi_mode(self, method_name: str = "") -> bool:
        """
        Check if instrument is in SCPI mode. Prevents SCPI commands in TSP mode.
        
        Returns:
            True if SCPI mode is active, False if TSP mode
        """
        if self._tsp_mode:
            print(f"⚠️  WARNING: Cannot call {method_name}() - instrument is in TSP mode!")
            print("   SCPI commands will cause error -285")
            print("   Switch back to SCPI mode or use TSP commands only")
            return False
        return True
    
    def check_errors(self) -> str:
        """Check instrument error status."""
        if self.device:
            try:
                if not self._check_scpi_mode("check_errors"):
                    return "Cannot check errors: In TSP mode"
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
                if self._tsp_mode:
                    # TSP mode: use TSP commands
                    self.device.write('print(smu.measure.read())')
                    time.sleep(0.02)
                    result = self.device.read().strip()
                    return float(result)
                else:
                    # SCPI mode
                    result = self.device.query(':MEAS:VOLT?').strip()
                return float(result)
            except Exception as e:
                # Don't print error if in wrong mode during cleanup
                if not self._tsp_mode or 'syntax error' not in str(e).lower():
                    print(f"Error measuring voltage: {e}")
                return None
        return None
    
    def measure_current(self) -> Optional[float]:
        """Measure and return current."""
        if self.device:
            try:
                if self._tsp_mode:
                    # TSP mode: use TSP commands
                    self.device.write('print(smu.measure.read())')
                    time.sleep(0.02)
                    result = self.device.read().strip()
                    return float(result)
                else:
                    # SCPI mode
                    result = self.device.query(':MEAS:CURR?').strip()
                    return float(result)
            except Exception as e:
                # Don't print error if in wrong mode during cleanup
                if not self._tsp_mode or 'syntax error' not in str(e).lower():
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
    # BUFFER-BASED PULSE OPERATIONS (SCPI)
    # ========================================================================
    
    def prepare_pulsing_voltage(self, voltage: float, width: float, clim: float = 100e-3) -> None:
        """
        Prepare voltage pulse using SimpleLoop trigger model with delay.
        For pulses <1ms, consider using TSP scripts (tsp_voltage_pulse) for better accuracy.
        Call send_pulse() to execute the pulse.
        
        Args:
            voltage: The desired peak voltage of the sample in volts
            width: The duration of the pulse in seconds
            clim: The current limit for the pulse (default: 100mA)
        """
        if not self.device:
            return
        
        try:
            # Store pulse parameters
            self._pulse_voltage = voltage
            self._pulse_width = width
            self._pulse_clim = clim
            self._pulse_type = 'voltage'
            
            # Reset and configure source
            self.device.write('*RST')
            self.device.write(':SOUR:FUNC VOLT')
            self.device.write(f':SOUR:VOLT:ILIM {clim}')
            self.device.write(':SOUR:VOLT:LEV 0')  # Start at 0V
            
            # Configure SimpleLoop trigger with delay for pulse width
            # Format: :TRIG:LOAD "SimpleLoop", count, delay
            self.device.write(f':TRIG:LOAD "SimpleLoop", 1, {width}')
            
            print(f"✓ Prepared voltage pulse: {voltage}V, {width*1e6:.1f}µs (SCPI)")
            
        except Exception as e:
            print(f"❌ Error preparing voltage pulse: {e}")
    
    def prepare_pulsing_current(self, current: float, width: float, vlim: float = 40) -> None:
        """
        Prepare current pulse using SimpleLoop trigger model with delay.
        For pulses <1ms, consider using TSP scripts (tsp_current_pulse) for better accuracy.
        Call send_pulse() to execute the pulse.
        
        Args:
            current: Desired peak current in AMPS (use 1e-3 for milliamps)
            width: Duration of pulse in seconds
            vlim: The voltage limit for the pulse (default: 40V)
        """
        if not self.device:
            return
        
        try:
            # Store pulse parameters
            self._pulse_current = current
            self._pulse_width = width
            self._pulse_vlim = vlim
            self._pulse_type = 'current'
            
            # Reset and configure source
            self.device.write('*RST')
            self.device.write(':SOUR:FUNC CURR')
            self.device.write(f':SOUR:CURR:VLIM {vlim}')
            self.device.write(':SOUR:CURR:LEV 0')  # Start at 0A
            
            # Configure SimpleLoop trigger with delay for pulse width
            # Format: :TRIG:LOAD "SimpleLoop", count, delay
            self.device.write(f':TRIG:LOAD "SimpleLoop", 1, {width}')
            
            print(f"✓ Prepared current pulse: {current*1e3:.2f}mA, {width*1e6:.1f}µs (SCPI)")
            
        except Exception as e:
            print(f"❌ Error preparing current pulse: {e}")
    
    def prepare_customsweep_currentpulse(self, sweep_list: List[float], width: float, nsweeps: int, 
                                        delay: float, vlim: float = 40, meason: int = 1, 
                                        range: float = 0.2) -> None:
        """
        Configure custom current pulse sweep with list of values.
        
        Args:
            sweep_list: List of current values to sweep through (A)
            width: Pulse width (s)
            nsweeps: Number of sweep repetitions
            delay: Delay between pulses (s)
            vlim: Voltage limit (V)
            meason: Measurement on time
            range: Voltage measurement range
        """
        if not self.device:
            return
        
        try:
            self.device.write('*rst')
            self.device.write('stat:cle')
            self.device.write('stat:ques:map 0, 2732, 2731')
            self.device.write('stat:ques:enable 1')
            self.device.write('stat:oper:map 0, 2732, 2731')
            self.device.write('stat:oper:enable 1')
            
            self.device.write('sour:func curr')
            self.device.write('sens:func "volt"')
            self.device.write(f'sour:curr:vlim {range}')
            self.device.write(f'sour:puls:curr:vlim {range}')
            self.device.write(f'sour:curr:range {10e-3}')
            self.device.write('sens:volt:rsen on')
            self.device.write('sens:volt:nplc 0.01')
            self.device.write('sens:volt:azer 0')
            self.device.write('sens:volt:rang:auto off')
            self.device.write(f'sens:volt:rang {range}')
            
            # Build current list
            self.device.write(f'source:puls:list:curr {sweep_list[0]}')
            for x in sweep_list[1:]:
                self.device.write(f'source:puls:list:curr:append {x}')
            self.device.write(
                f'source:puls:swe:curr:list {width}, {meason}, "defbuffer1", 1, {nsweeps}, {delay}, {delay}, 1')
        except Exception as e:
            print(f"Error preparing custom sweep: {e}")
    
    def set_ext_trig(self, pin: int = 3) -> None:
        """
        Configures the DIO pins to send an external positive edge pulse before the voltage pulse.
        
        Args:
            pin: DIO pin number connected to external trigger (default: 3)
        """
        if not self.device:
            return
        
        try:
            self.device.write(f'dig:line{pin}:mode trig, out')
            self.device.write(f'trig:dig{pin}:out:log pos')
            self.device.write(f'trig:dig{pin}:out:stim NOT1')
            self.device.write('trig:bloc:not 5, 1')
            self.device.write(f'TRIG:DIG{pin}:OUT:PULS 100e-6')
        except Exception as e:
            print(f"Error setting external trigger: {e}")
    
    def send_pulse(self) -> None:
        """
        Execute the pulse configured by prepare_pulsing_voltage or prepare_pulsing_current.
        Uses SimpleLoop trigger with hardware delay for timing.
        """
        if not self.device:
            return
        
        try:
            # Verify pulse was prepared
            if not hasattr(self, '_pulse_type'):
                print("❌ Error: No pulse prepared. Call prepare_pulsing_voltage() or prepare_pulsing_current() first.")
                return
            
            # Set source to pulse level
            if self._pulse_type == 'voltage':
                self.device.write(f':SOUR:VOLT:LEV {self._pulse_voltage}')
            else:
                self.device.write(f':SOUR:CURR:LEV {self._pulse_current}')
            
            # Turn on output and execute trigger (which includes the delay)
            self.device.write(':OUTP ON')
            self._output_enabled = True
            
            self.device.write(':INIT')  # Execute SimpleLoop (includes delay)
            self.device.write('*WAI')   # Wait for completion
            
            # Return to zero and turn off
            if self._pulse_type == 'voltage':
                self.device.write(':SOUR:VOLT:LEV 0')
            else:
                self.device.write(':SOUR:CURR:LEV 0')
            
            self.device.write(':OUTP OFF')
            self._output_enabled = False
            
            pulse_type = self._pulse_type
            width = self._pulse_width
            print(f"✓ {pulse_type.capitalize()} pulse executed ({width*1e6:.1f}µs)")
            
        except Exception as e:
            print(f"❌ Error sending pulse: {e}")
            import traceback
            traceback.print_exc()
    
    # ========================================================================
    # MEASUREMENT OPERATIONS
    # Note: For fast TSP pulses (<1ms), see Keithley2450_TSP.py
    # ========================================================================
    
    def prepare_measure_n(self, current: float, num: int, nplc: float = 2) -> None:
        """
        Prepares the instrument to measure specified number of points in 2-wire configuration. 
        Use trigger() to start and read_buffer() to collect data. Does not enable probe current.
        
        Args:
            current: Probing current amplitude in amps
            num: Number of points to measure
            nplc: Number of powerline cycles per point (default: 2)
        """
        if not self.device:
            return
        
        try:
            # Store parameters for later use
            self._measure_count = num
            self._measure_current = current
            
            print(f"  DEBUG: Configuring source: {current*1e6:.1f}µA")
            # Configure current source
            self.device.write(':SOUR:FUNC CURR')
            self.device.write(f':SOUR:CURR:LEV {current}')
            self.device.write(':SOUR:CURR:RANG:AUTO ON')
            
            print(f"  DEBUG: Configuring sense: VOLT, NPLC={nplc}")
            # Configure voltage measurement (2-wire for simplicity)
            self.device.write(':SENS:FUNC "VOLT"')
            self.device.write(f':SENS:VOLT:NPLC {nplc}')
            self.device.write(':SENS:VOLT:RANG:AUTO ON')
            
            print(f"  DEBUG: Setting trigger count: {num}")
            # Configure trigger count for multiple measurements
            self.device.write(f':TRIG:COUN {num}')
            
        except Exception as e:
            print(f"❌ Error preparing N-point measurement: {e}")
    
    def prepare_measure_one(self, current: float, nplc: float = 2, four_wire: bool = True) -> None:
        """
        Prepares the instrument to measure 2-wire or 4-wire resistance one at a time. 
        For use with trigger_before_fetch() + fetch_one() or with read_one(). 
        Does not enable probe current - use enable_output() after.
        
        Args:
            current: Source current (A)
            nplc: Number of powerline cycles
            four_wire: True for 4-wire sensing, False for 2-wire
        """
        if not self.device:
            return
        
        try:
            self.device.write('sens:func "volt"')
            self.device.write('sens:volt:rang:auto on')
            if four_wire:
                self.device.write('sens:volt:rsen on')
            else:
                self.device.write('sens:volt:rsen off')
            self.device.write(f'sens:volt:nplc {nplc}')
            self.device.write('sour:func curr')
            self.device.write(f'sour:curr {current}')
            self.device.write('sour:curr:range:auto on')
            self.device.write('sour:curr:vlim 2')
        except Exception as e:
            print(f"Error preparing single-point measurement: {e}")
    
    def enable_4_wire_probe(self, current: float, nplc: float = 2, vlim: float = 1) -> None:
        """
        Prepares the instrument for 4-wire resistance measurement and enables probe current.
        For use with trigger_before_fetch() + fetch_one() or with read_one().
        
        Args:
            current: Probing current (A)
            nplc: Number of powerline cycles
            vlim: Voltage limit (V)
        """
        if not self.device:
            return
        
        try:
            self.device.write('*rst')
            self.device.write('sour:func curr')
            self.device.write('sens:func "volt"')
            self.device.write('sens:volt:rang:auto on')
            self.device.write('sens:volt:rsen on')
            self.device.write(f'sens:volt:nplc {nplc}')
            self.device.write(f'sour:curr {current}')
            self.device.write('sour:curr:range:auto on')
            self.device.write(f'sour:curr:vlim {vlim}')
            self.device.write('outp on')
            self._output_enabled = True
        except Exception as e:
            print(f"Error enabling 4-wire probe: {e}")
    
    def enable_2_wire_probe(self, current: float, nplc: float = 2, vlim: float = 1) -> None:
        """
        Prepares the instrument for 2-wire resistance measurement and enables probe current.
        For use with trigger_before_fetch() + fetch_one() or with read_one().
        
        Args:
            current: Probing current in amps
            nplc: Number of powerline cycles (0.02, 0.2, 1, 10, 100, 200; 0.2 is "fast")
            vlim: Voltage limit (V)
        """
        if not self.device:
            return
        
        try:
            self.device.write('*rst')
            self.device.write('sour:func curr')
            self.device.write('sens:func "volt"')
            self.device.write('sens:volt:rang:auto on')
            self.device.write('sens:volt:rsen off')
            self.device.write(f'sens:volt:nplc {nplc}')
            self.device.write(f'sour:curr {current}')
            self.device.write('sour:curr:range:auto on')
            self.device.write(f'sour:curr:vlim {vlim}')
            self.device.write('outp on')
            self._output_enabled = True
        except Exception as e:
            print(f"Error enabling 2-wire probe: {e}")
    
    def trigger(self) -> None:
        """
        Starts applying current and initiates the measurement set up using prepare_measure_n(). 
        Use with read_buffer() then disable_probe_current().
        """
        if not self.device:
            return
        
        try:
            print("  DEBUG: Sending ':OUTP ON'")
            self.device.write(':OUTP ON')
            self._output_enabled = True
            
            print("  DEBUG: Sending ':INIT' (arm/initiate measurement)")
            self.device.write(':INIT')
            
            print("  DEBUG: Sending '*WAI' (wait for completion)")
            self.device.write('*WAI')
            
        except Exception as e:
            print(f"❌ Error triggering measurement: {e}")
            print(f"   Command that failed: {e}")
    
    def trigger_before_fetch(self) -> None:
        """
        Triggers a single measurement for reading later. Use for higher synchronicity between instruments.
        Use fetch_one() to get the data. See also: read_one()
        """
        if not self.device:
            return
        
        try:
            self.device.write('trac:trig "defbuffer1"')
            self.device.write('*wai')
        except Exception as e:
            print(f"Error triggering fetch: {e}")
    
    def read_buffer(self, num: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Reads measurements using :FETCh? (2450 command for retrieving buffered data).
        
        Args:
            num: Number of points to read
            
        Returns:
            Tuple of (time, voltage, current). Use v/c to get resistance.
        """
        if not self.device:
            return np.array([]), np.array([]), np.array([])
        
        try:
            voltages = []
            currents = []
            timestamps = []
            
            print(f"  DEBUG: Fetching {num} measurements with :FETCh? command...")
            
            # Fetch all the measurements that were triggered by :INITiate
            for i in range(num):
                result_str = self.device.query(':FETCh?')
                
                # Parse the result - format is typically: reading, source, timestamp, status
                # But might be just: reading, source
                values = [float(x) for x in result_str.split(',')]
                
                if len(values) >= 2:
                    voltages.append(values[0])  # Reading (voltage)
                    currents.append(values[1])  # Source (current)
                    timestamps.append(i * 0.02)  # Estimated timing
                elif len(values) == 1:
                    voltages.append(values[0])
                    # Use stored probe current
                    currents.append(self._measure_current if hasattr(self, '_measure_current') else 10e-6)
                    timestamps.append(i * 0.02)
                    
                if (i + 1) % 5 == 0:
                    print(f"    Fetched {i+1}/{num} points...")
            
            print(f"  DEBUG: Successfully fetched {len(voltages)} measurements")
            
            # Turn off output after reading
            print("  DEBUG: Sending ':OUTP OFF'")
            self.device.write(':OUTP OFF')
            self._output_enabled = False
            
            if voltages:
                return np.array(timestamps), np.array(voltages), np.array(currents)
            else:
                return np.array([]), np.array([]), np.array([])
                
        except Exception as e:
            print(f'❌ Error fetching measurements from K2450: {e}')
            print(f'   Command: :FETCh?')
            import traceback
            traceback.print_exc()
            return np.array([]), np.array([]), np.array([])
    
    def read_one(self) -> Tuple[float, float]:
        """
        Measures, reads and returns a single value from the instrument. 
        For use with enable_2_wire_probe() or enable_4_wire_probe(). 
        To measure and read separately, see trigger_before_fetch() and fetch_one().
            
        Returns:
            Tuple of (current, voltage). Use v/c for resistance.
        """
        if not self.device:
            return 0.0, 0.0
        
        try:
            data = np.array([self.device.query_ascii_values('read? "defbuffer1", sour, read')])
            cur = data[0][0]
            vol = data[0][1]
            return cur, vol
        except Exception as e:
            print(f"Error reading single point: {e}")
            return 0.0, 0.0
    
    def fetch_one(self) -> Tuple[float, float]:
        """
        Reads and returns a single value from the instrument. 
        For use with trigger_before_fetch() and either enable_2_wire_probe() or enable_4_wire_probe().
        
        Returns:
            Tuple of (voltage, current). Use v/c for resistance.
        """
        if not self.device:
            return 0.0, 0.0
        
        try:
            data = self.device.query_ascii_values('fetch? "defbuffer1", sour, read')
            return data[1], data[0]
        except Exception as e:
            print(f"Error fetching data: {e}")
            return 0.0, 0.0
    
    def enable_probe_current(self) -> None:
        """
        Enable output current. Same as hitting "output on" on the front panel.
        """
        if self.device:
            try:
                self.device.write('outp on')
                self._output_enabled = True
            except Exception as e:
                print(f"Error enabling probe current: {e}")
    
    def disable_probe_current(self) -> None:
        """
        Disable output current. Same as hitting "output off" on the front panel.
        """
        if self.device:
            try:
                self.device.write('outp off')
                self._output_enabled = False
            except Exception as e:
                print(f"Error disabling probe current: {e}")
    
    def get_trace(self, num: int, check_period: float = 10) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Retrieves measured values after an output sweep. Waits for completion by checking 
        instrument status, then retrieves data from buffer.
        
        Args:
            num: Number of points to retrieve
            check_period: Time between status checks in seconds
        
        Returns:
            Tuple of (time, voltage, current) as numpy arrays
        """
        if not self.device:
            return np.array([]), np.array([]), np.array([])
        
        try:
            start_time = time.time()
            running = True
            while running:
                time.sleep(check_period)
                status = int(self.device.query_ascii_values('*STB?')[0])
                state = format(status, '#08b')
                qsb = state[-4] == '1'
                msb = state[-1] == '1'
                if msb or qsb:
                    running = False
                print(f'time elapsed: {time.time() - start_time}')
            
            print('Measurement Finished, reading data')
            time.sleep(1)
            data = np.array(self.device.query_ascii_values(f'trac:data? 1, {num}, "defbuffer1", sour, read, rel'))
            t = data[2::3]
            v = data[1::3]
            c = data[0::3]
            self.device.write('*CLS')
            return t, v, c
        except Exception as e:
            print(f"Error getting trace: {e}")
            return np.array([]), np.array([]), np.array([])
    
    def close(self) -> None:
        """Close connection to instrument."""
        if self.device:
            try:
                # Only shutdown if not in TSP mode (shutdown uses SCPI commands)
                if not self._tsp_mode:
                    self.shutdown()
                else:
                    # TSP mode: just turn off output using TSP
                    try:
                        self.device.write('smu.source.output = smu.OFF')
                        time.sleep(0.02)
                    except:
                        pass
                
                self.device.close()
                if self.rm:
                    self.rm.close()
                print("Connection closed.")
            except Exception as e:
                print(f"Error closing connection: {e}")


# ============================================================================
# SIMPLE SINGLE PULSE EXAMPLE - Get basics working first
# ============================================================================

def example_single_pulse(keithley):
    """
    Simple Single Pulse and Measurement using Trigger Model (2450 style)
    
    Workflow:
    1. Send a voltage pulse
    2. Configure trigger-based measurement  
    3. Initiate trigger and read result
    
    Uses 2450's trigger model similar to K2461 in sourcemeters.py
    """
    print("\n" + "=" * 70)
    print("Simple Single Pulse Example (Trigger Mode)")
    print("=" * 70)
    
    # Simple parameters
    pulse_voltage = 1.0      # 1V pulse
    pulse_width = 1e-4      # 10ms pulse
    current_limit = 0.1      # 100mA compliance
    
    probe_current = 10e-6    # 10µA probe current
    num_readings = 5         # Take 5 readings after pulse
    
    print(f"\nConfiguration:")
    print(f"  Pulse: {pulse_voltage}V, {pulse_width*1e3:.1f}ms")
    print(f"  Probe: {probe_current*1e6:.1f}µA, {num_readings} readings")
    print()
    
    try:
        # ============================================================
        # STEP 1: Send pulse
        # ============================================================
        print("STEP 1: Sending pulse...")
        keithley.prepare_pulsing_voltage(pulse_voltage, pulse_width, clim=current_limit)
        keithley.send_pulse()
        print("  ✓ Pulse sent")
        
        time.sleep(0.2)  # Wait after pulse
        
        # ============================================================
        # STEP 2: Configure for trigger-based measurement
        # ============================================================
        print("\nSTEP 2: Configuring trigger-based measurement...")
        
        print(f"  DEBUG: Sending ':SOUR:FUNC CURR'")
        keithley.device.write(':SOUR:FUNC CURR')
        
        print(f"  DEBUG: Sending ':SOUR:CURR:LEV {probe_current}'")
        keithley.device.write(f':SOUR:CURR:LEV {probe_current}')
        
        print(f"  DEBUG: Sending ':SENS:FUNC \"VOLT\"'")
        keithley.device.write(':SENS:FUNC "VOLT"')
        
        print(f"  DEBUG: Sending ':SENS:VOLT:NPLC 2'")
        keithley.device.write(':SENS:VOLT:NPLC 2')
        
        print(f"  DEBUG: Loading simple loop trigger model...")
        print(f"  DEBUG: Sending ':TRIG:LOAD \"SimpleLoop\", {num_readings}, 0'")
        keithley.device.write(f':TRIG:LOAD "SimpleLoop", {num_readings}, 0')
        
        print("  ✓ Configured")
        
        # ============================================================
        # STEP 3: Initiate trigger and take measurements
        # ============================================================
        print("\nSTEP 3: Initiating trigger model...")
        print(f"  DEBUG: Sending ':OUTP ON'")
        keithley.device.write(':OUTP ON')
        
        time.sleep(0.05)  # Brief settling
        
        print(f"  DEBUG: Sending ':INIT'")
        keithley.device.write(':INIT')
        
        print(f"  DEBUG: Sending '*WAI' (wait for completion)")
        keithley.device.write('*WAI')
        
        print("  ✓ Measurements complete")
        
        # ============================================================
        # STEP 4: Read data from buffer
        # ============================================================
        print("\nSTEP 4: Reading data from buffer...")
        print(f"  DEBUG: Sending ':TRAC:DATA? 1, {num_readings}, \"defbuffer1\"'")
        
        try:
            result = keithley.device.query(f':TRAC:DATA? 1, {num_readings}, "defbuffer1"')
            print(f"  DEBUG: Received {len(result)} characters")
            print(f"  DEBUG: Raw data: {result[:100]}...")
            
            # Parse result - should be comma-separated values
            values = [float(x) for x in result.split(',')]
            print(f"  DEBUG: Parsed {len(values)} values")
            
            if len(values) >= num_readings:
                voltages = values[:num_readings]
                avg_voltage = sum(voltages) / len(voltages)
                resistance = avg_voltage / probe_current if probe_current != 0 else float('inf')
                
                print(f"\n  ✓ Measurement successful!")
                print(f"    Readings: {num_readings}")
                print(f"    Avg Voltage:  {avg_voltage:.6f} V")
                print(f"    Current:      {probe_current:.9f} A ({probe_current*1e6:.2f} µA)")
                print(f"    Resistance:   {resistance:.2e} Ω")
                print(f"    Voltage range: {min(voltages):.6f} - {max(voltages):.6f} V")
            else:
                print(f"  ⚠ Expected {num_readings} values, got {len(values)}")
        
        except Exception as e:
            print(f"  ❌ Error reading buffer: {e}")
            print(f"  Trying simple :READ? instead...")
            
            # Fallback to simple read
            result = keithley.device.query(':READ?')
            print(f"  DEBUG: Received: {result}")
            values = [float(x) for x in result.split(',')]
            if len(values) >= 1:
                print(f"    Voltage: {values[0]:.6f} V")
        
        # ============================================================
        # STEP 5: Turn off
        # ============================================================
        print("\nSTEP 5: Turning off output...")
        print(f"  DEBUG: Sending ':OUTP OFF'")
        keithley.device.write(':OUTP OFF')
        print("  ✓ Output disabled")
        
        print("\n" + "=" * 70)
        print("✓ Single pulse test complete!")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        try:
            keithley.device.write(':OUTP OFF')
        except:
            pass


def example_pulse_and_measure(keithley):
    """
    Pulse Loop Example (like pulse_loop.py)
    
    Workflow:
    1. Prepare and send pulse
    2. Prepare buffer measurement
    3. Trigger measurement
    4. Fetch data from buffer
    
    This mimics the pulse_loop.py pattern: pulse → measure → repeat
    """
    print("\n" + "=" * 70)
    print("Pulse Loop Example - Prepare, Pulse, Fetch Pattern")
    print("=" * 70)
    
    # Pulse parameters - TEST DIFFERENT SPEEDS
    pulse_voltage = 1.0      # 1V pulse
    pulse_widths = [1e-3, 500e-6, 100e-6, 50e-6]  # 1ms, 500µs, 100µs, 50µs
    current_limit = 0.1      # 100mA compliance
    number_of_pulses = len(pulse_widths)
    
    # Measurement parameters
    probe_current = 10e-6           # 10µA probe current
    nplc = 2                        # Integration time
    number_of_measurements = 10     # Points per pulse
    
    pulse_data = []
    
    print(f"\nConfiguration:")
    print(f"  Pulse: {pulse_voltage}V, varying widths")
    print(f"  Widths: {[f'{w*1e6:.0f}µs' for w in pulse_widths]}")
    print(f"  Probe: {probe_current*1e6:.1f}µA, {number_of_measurements} points, NPLC={nplc}")
    print()
    
    try:
        for n in range(number_of_pulses):
            pulse_width = pulse_widths[n]
            print(f"Pulse #{n+1}/{number_of_pulses} - Width: {pulse_width*1e6:.0f}µs")
            
            # ============================================================
            # STEP 1: Prepare and send pulse
            # ============================================================
            print(f"  [1] Preparing pulse: {pulse_voltage}V, {pulse_width*1e6:.0f}µs...")
            keithley.prepare_pulsing_voltage(pulse_voltage, pulse_width, clim=current_limit)
            
            print(f"  [2] Sending pulse...")
            keithley.send_pulse()
            
            # Wait for pulse to complete
            time.sleep(0.2)
            
            # ============================================================
            # STEP 2: Prepare buffer measurement
            # ============================================================
            print(f"  [3] Preparing measurement buffer ({number_of_measurements} points)...")
            keithley.prepare_measure_n(probe_current, number_of_measurements, nplc)
            
            # ============================================================
            # STEP 3: Trigger measurement
            # ============================================================
            print(f"  [4] Triggering measurement...")
            keithley.trigger()
            
            # Wait for measurement to complete
            time.sleep(0.1)
            
            # ============================================================
            # STEP 4: Fetch data from buffer
            # ============================================================
            print(f"  [5] Fetching data from buffer...")
            time_arr, v, c = keithley.read_buffer(number_of_measurements)
            
            # ============================================================
            # Process and display results
            # ============================================================
            if len(v) > 0 and len(c) > 0:
                # Calculate resistance
                valid_idx = c != 0
                if np.any(valid_idx):
                    resistances = v[valid_idx] / c[valid_idx]
                    avg_resistance = np.mean(resistances)
                    std_resistance = np.std(resistances)
                    
                    print(f"  ✓ Resistance: {avg_resistance:.2e} ± {std_resistance:.2e} Ω")
                    print(f"    (V_avg: {np.mean(v):.6f}V, I_avg: {np.mean(c):.9f}A)")
                    
                    # Store data
                    pulse_data.append({
                        'pulse_num': n+1,
                        'pulse_width': pulse_width,
                        'time': time_arr,
                        'voltage': v,
                        'current': c,
                        'resistance': avg_resistance
                    })
                else:
                    print(f"  ⚠ Warning: Zero current detected")
            else:
                print(f"  ❌ Error: No data received from buffer")
            
            print()  # Blank line between pulses
        
        # ================================================================
        # Summary
        # ================================================================
        print("=" * 70)
        print("Pulse Loop Complete")
        print("=" * 70)
        
        if pulse_data:
            resistances = [p['resistance'] for p in pulse_data]
            print(f"✓ Captured {len(pulse_data)} pulses")
            print(f"✓ Resistance range: {min(resistances):.2e} - {max(resistances):.2e} Ω")
            print(f"✓ Average: {np.mean(resistances):.2e} Ω")
            print(f"✓ Std dev: {np.std(resistances):.2e} Ω")
            
            # Show trend
            print(f"\nResistance after each pulse:")
            for p in pulse_data:
                width_us = p['pulse_width'] * 1e6
                print(f"  Pulse {p['pulse_num']} ({width_us:.0f}µs): {p['resistance']:.2e} Ω")
        else:
            print("❌ No data captured")
        
    except Exception as e:
        print(f"\n❌ Error in pulse loop: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("\nCleaning up...")
        keithley.disable_probe_current()
        print("✓ Output disabled")


if __name__ == "__main__":
    print("=" * 70)
    print("Keithley 2450 - Simple Single Pulse Test")
    print("=" * 70)
    print()
    print("Testing basic pulse and measurement workflow")
    print("  Step 1: Send pulse")
    print("  Step 2: Configure measurement")
    print("  Step 3: Take measurement")
    print("  Step 4: Turn off")
    print()
    
    # Configuration - CHANGE THIS TO YOUR ADDRESS
    DEVICE_ADDRESS = 'USB0::0x05E6::0x2450::04496615::INSTR'
    # Alternatives:
    # DEVICE_ADDRESS = 'GPIB0::24::INSTR'
    # DEVICE_ADDRESS = 'TCPIP0::192.168.1.100::INSTR'
    
    # Connection Test
    print("Connecting to instrument...")
    print(f"Address: {DEVICE_ADDRESS}")
    print()
    
    try:
        keithley = Keithley2450Controller(DEVICE_ADDRESS)
        if not keithley.device:
            print("❌ Failed to connect to instrument")
            print("\nTroubleshooting:")
            print("1. Check the DEVICE_ADDRESS matches your instrument")
            print("2. Verify USB/GPIB cable is connected")
            print("3. Check instrument is powered on")
            print("\nList available resources:")
            print("  import pyvisa")
            print("  rm = pyvisa.ResourceManager()")
            print("  print(rm.list_resources())")
            exit(1)
        
        idn = keithley.get_idn()
        print(f"✓ Connected to: {idn}")
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
    
    # Run the simple single pulse test
    example_single_pulse(keithley)
    
    # Cleanup
    print("\n" + "=" * 70)
    print("Cleanup")
    print("=" * 70)
    keithley.shutdown()
    keithley.close()
    print("✓ Connection closed safely")

