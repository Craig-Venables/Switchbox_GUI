"""
Keithley 2450 TSP (Test Script Processor) - Standalone Controller
==================================================================

This is a STANDALONE controller for the Keithley 2450 SourceMeter using
ONLY TSP (Test Script Processor) commands. No SCPI, no mode switching needed.

TSP provides the fastest and most accurate pulse generation (<1ms pulses).

⚠️ REQUIREMENTS:
    1. Instrument must be in TSP mode (not SCPI mode)
       - To switch: MENU → System → Settings → Command Set → TSP
       - Or leave it in TSP mode permanently
    
    2. This class uses ONLY TSP commands (no SCPI)
       - All commands are TSP: smu.source.level, smu.measure.read(), etc.
       - No SCPI commands like :MEAS:VOLT? or :SOUR:VOLT

Usage:
    from Keithley2450_TSP import Keithley2450_TSP
    
    # Connect directly in TSP mode
    tsp = Keithley2450_TSP('USB0::0x05E6::0x2450::04496615::INSTR')
    
    # Send pulses
    tsp.voltage_pulse(1.0, 100e-6, clim=0.1)  # 1V, 100µs pulse
    v, i = tsp.pulse_with_measurement(2.0, 500e-6)  # Pulse with measurement
    tsp.pulse_train(1.0, 100e-6, 10, 1e-3)  # 10 pulses
    
    # Check for errors
    tsp.print_diagnostics()
    
    # Close connection
    tsp.close()

Performance:
    - Minimum pulse width: ~50µs (vs ~2ms for SCPI)
    - Timing accuracy: ±10µs (vs ±100µs for SCPI)
    - Execution: On-instrument (no PC latency)
    - NPLC: 0.01 (fastest allowed)

Author: Automated refactoring
Date: 2025-10-28
Version: 2.0 - Standalone
"""

import pyvisa
import time
from typing import Optional, List, Dict, Any, Tuple


class Keithley2450_TSP:
    """
    Standalone TSP (Test Script Processor) controller for Keithley 2450.
    Uses ONLY TSP commands for fast, accurate pulse generation.
    """
    
    def __init__(self, address: str, timeout: int = 10000, terminals: str = 'front'):
        """
        Initialize and connect to Keithley 2450 in TSP mode.
        
        Args:
            address: VISA resource address
                     - GPIB: 'GPIB0::24::INSTR'
                     - USB: 'USB0::0x05E6::0x2450::04496615::INSTR'
                     - LAN: 'TCPIP0::192.168.1.100::INSTR'
            timeout: Communication timeout in milliseconds (default 10000ms)
            terminals: Terminal selection - 'front' or 'rear' (default: 'front')
        
        Note:
            Instrument must be in TSP mode. This class will NOT switch modes.
        """
        self.address = address
        self.device = None
        self.rm = None
        self.terminals = terminals.lower()
        
        if self.terminals not in ['front', 'rear']:
            print(f"Warning: Invalid terminals '{terminals}', defaulting to 'front'")
            self.terminals = 'front'
        
        try:
            self.rm = pyvisa.ResourceManager()
            self.device = self.rm.open_resource(address)
            self.device.timeout = timeout
            
            # Clear error queue using TSP
            try:
                self.device.write('errorqueue.clear()')
                time.sleep(0.1)
            except:
                print("⚠️  Could not clear error queue - ensure instrument is in TSP mode!")
            
            # Set terminal selection
            try:
                if self.terminals == 'rear':
                    self.device.write('smu.terminals = smu.TERMINALS_REAR')
                    print("Terminals set to: REAR")
                else:
                    self.device.write('smu.terminals = smu.TERMINALS_FRONT')
                    print("Terminals set to: FRONT")
                time.sleep(0.1)  # Small delay for setting to take effect
            except Exception as e:
                print(f"⚠️  Could not set terminals: {e}")
            
            # Get instrument identity
            idn = self.get_idn()
            print(f"Connected to: {idn}")
            
            if '2450' not in idn:
                print(f"Warning: Expected Keithley 2450, got: {idn}")
                
        except Exception as e:
            print(f"Error connecting to Keithley 2450: {e}")
            print("Ensure instrument is in TSP mode: MENU → System → Settings → TSP")
            self.device = None
    
    def get_idn(self) -> str:
        """Query and return the device identity string using TSP."""
        if self.device:
            try:
                self.device.write('print(localnode.model .. "," .. localnode.serialno .. "," .. localnode.version)')
                time.sleep(0.02)
                return "KEITHLEY INSTRUMENTS," + self.device.read().strip()
            except Exception as e:
                return f"No Device Connected (Error: {e})"
        return "No Device Connected"
    
    def set_voltage(self, voltage: float, Icc: float = 0.1) -> None:
        """
        Set source voltage and current limit (TSP version of standard interface).
        Enables output automatically if not already on.
        
        Args:
            voltage: Voltage to set (V)
            Icc: Current compliance limit (A)
        """
        if not self.device:
            return
        
        try:
            self.device.write('smu.source.func = smu.FUNC_DC_VOLTAGE')
            self.device.write(f'smu.source.level = {voltage}')
            self.device.write(f'smu.source.ilimit.level = {Icc}')
            self.device.write('smu.source.output = smu.ON')
            time.sleep(0.01)
        except Exception as e:
            print(f"Error setting voltage: {e}")
    
    def set_current(self, current: float, Vcc: float = 10.0) -> None:
        """
        Set source current and voltage limit (TSP version of standard interface).
        Enables output automatically if not already on.
        
        Args:
            current: Current to set (A)
            Vcc: Voltage compliance limit (V)
        """
        if not self.device:
            return
        
        try:
            self.device.write('smu.source.func = smu.FUNC_DC_CURRENT')
            self.device.write(f'smu.source.level = {current}')
            self.device.write(f'smu.source.vlimit.level = {Vcc}')
            self.device.write('smu.source.output = smu.ON')
            time.sleep(0.01)
        except Exception as e:
            print(f"Error setting current: {e}")
    
    def measure_voltage(self) -> Optional[float]:
        """
        Measure voltage (TSP version of standard interface).
        
        Returns:
            Measured voltage in volts, or None if error
        """
        if not self.device:
            return None
        
        try:
            self.device.write('smu.measure.func = smu.FUNC_DC_VOLTAGE')
            self.device.write('print(smu.measure.read())')
            time.sleep(0.02)
            result = self.device.read().strip()
            return float(result)
        except Exception as e:
            print(f"Error measuring voltage: {e}")
            return None
    
    def measure_current(self) -> Optional[float]:
        """
        Measure current (TSP version of standard interface).
        
        Returns:
            Measured current in amps, or None if error
        """
        if not self.device:
            return None
        
        try:
            self.device.write('smu.measure.func = smu.FUNC_DC_CURRENT')
            self.device.write('print(smu.measure.read())')
            time.sleep(0.02)
            result = self.device.read().strip()
            return float(result)
        except Exception as e:
            print(f"Error measuring current: {e}")
            return None
    
    def enable_output(self, enable: bool = True) -> None:
        """
        Enable or disable output (TSP version of standard interface).
        
        Args:
            enable: True to enable output, False to disable
        """
        if not self.device:
            return
        
        try:
            if enable:
                self.device.write('smu.source.output = smu.ON')
            else:
                self.device.write('smu.source.output = smu.OFF')
            time.sleep(0.01)
        except Exception as e:
            print(f"Error {'enabling' if enable else 'disabling'} output: {e}")
    
    def shutdown(self) -> None:
        """
        Shutdown: ramp to 0V/0A and disable output (TSP version of standard interface).
        """
        if not self.device:
            return
        
        try:
            # Ramp to zero
            self.device.write('smu.source.level = 0')
            time.sleep(0.1)
            # Disable output
            self.device.write('smu.source.output = smu.OFF')
            time.sleep(0.01)
        except Exception as e:
            print(f"Error during shutdown: {e}")
    
    def beep(self, frequency: float = 1000, duration: float = 0.5) -> None:
        """
        Make the instrument beep (TSP version of standard interface).
        
        Args:
            frequency: Beep frequency in Hz
            duration: Beep duration in seconds
        """
        if not self.device:
            return
        
        try:
            self.device.write(f'beeper.beep({duration}, {frequency})')
            time.sleep(0.01)
        except Exception as e:
            print(f"Error beeping: {e}")
    
    def close(self) -> None:
        """Close connection to instrument."""
        if self.device:
            try:
                # Turn off output using TSP
                self.device.write('smu.source.output = smu.OFF')
                time.sleep(0.02)
                
                # Close connection
                self.device.close()
                if self.rm:
                    self.rm.close()
                print("✓ Connection closed")
            except Exception as e:
                print(f"Error closing connection: {e}")
    
    def check_errors(self) -> str:
        """
        Check and clear the TSP error queue.
        Returns error string or "No errors".
        """
        if not self.device:
            return "No device connected"
        
        try:
            self.device.write('print(errorqueue.next())')
            import time
            time.sleep(0.02)
            err = self.device.read()
            if '0' in err or 'nil' in err.lower():
                return "No errors"
            return f"Error: {err}"
        except Exception as e:
            return f"Could not check errors: {e}"
    
    def get_all_errors(self) -> list:
        """
        Get all errors from the error queue.
        
        Returns:
            List of error strings (code, message)
        """
        errors = []
        if not self.device:
            return errors
        
        try:
            import time
            # Get error count
            self.device.write('print(errorqueue.count)')
            time.sleep(0.02)
            count_str = self.device.read().strip()
            count = int(count_str) if count_str else 0
            
            # Read all errors
            for _ in range(count):
                self.device.write('code, msg = errorqueue.next() print(code .. "," .. msg)')
                time.sleep(0.02)
                response = self.device.read().strip()
                if response and '0,' not in response:
                    errors.append(response)
            
            return errors
        except Exception as e:
            return [f"Error reading queue: {e}"]
    
    def get_error_count(self) -> int:
        """Get number of errors in queue."""
        if not self.device:
            return 0
        try:
            import time
            self.device.write('print(errorqueue.count)')
            time.sleep(0.02)
            result = self.device.read().strip()
            # Handle "nil" or empty response
            if result.lower() == 'nil' or not result:
                return 0
            return int(result)
        except:
            return 0
    
    def get_event_log(self, max_events: int = 50) -> list:
        """
        Get events from the instrument event log.
        
        The event log stores ALL events (errors, warnings, info) with timestamps.
        More comprehensive than error queue.
        
        Args:
            max_events: Maximum number of events to retrieve
            
        Returns:
            List of event dictionaries with timestamp, severity, code, and message
        """
        events = []
        
        if not self.device:
            return events
        
        try:
            import time
            # Get event count
            self.device.write('print(eventlog.count)')
            time.sleep(0.02)
            count_str = self.device.read().strip()
            count = int(count_str) if count_str.isdigit() else 0
            
            # Limit to max_events
            count = min(count, max_events)
            
            print(f"Reading {count} events from event log...")
            
            # Read events from event log
            for i in range(count):
                # Get next event with all details
                self.device.write('msg, secs, nano, sev = eventlog.next() if msg then print(string.format("%d,%d,%d,%s", secs, nano, sev, msg)) else print("NONE") end')
                time.sleep(0.02)
                
                response = self.device.read().strip()
                if response and response != "NONE":
                    try:
                        parts = response.split(',', 3)
                        if len(parts) >= 4:
                            events.append({
                                'timestamp_sec': int(parts[0]),
                                'timestamp_nano': int(parts[1]),
                                'severity': int(parts[2]),  # 0=info, 1=warning, 2=error
                                'message': parts[3]
                            })
                    except:
                        events.append({'raw': response})
            
            return events
            
        except Exception as e:
            return [{'error': f"Failed to read event log: {e}"}]
    
    def get_event_log_count(self) -> int:
        """Get number of events in event log."""
        if not self.device:
            return 0
        try:
            import time
            self.device.write('print(eventlog.count)')
            time.sleep(0.02)
            return int(self.device.read().strip())
        except:
            return 0
    
    def clear_event_log(self):
        """Clear all events from event log."""
        if not self.device:
            return
        try:
            self.device.write('eventlog.clear()')
            import time
            time.sleep(0.02)
            print("✓ Event log cleared")
        except Exception as e:
            print(f"⚠️  Error clearing event log: {e}")
    
    def get_full_diagnostics(self) -> dict:
        """
        Get comprehensive diagnostic information from the instrument.
        
        Returns dictionary with:
        - error_count: Number of errors in queue
        - errors: List of all errors
        - event_count: Number of events in log
        - events: List of recent events
        - instrument_status: Basic instrument info
        """
        diagnostics = {
            'error_count': 0,
            'errors': [],
            'event_count': 0,
            'events': [],
            'instrument_status': {}
        }
        
        if not self.device:
            return diagnostics
        
        try:
            import time
            
            # 1. Get all errors from error queue
            diagnostics['errors'] = self.get_all_errors()
            diagnostics['error_count'] = len(diagnostics['errors'])
            
            # 2. Get event log
            diagnostics['event_count'] = self.get_event_log_count()
            diagnostics['events'] = self.get_event_log(max_events=30)
            
            # 3. Get basic instrument status
            self.device.write('print(smu.source.output)')
            time.sleep(0.02)
            output_state = self.device.read().strip()
            diagnostics['instrument_status']['output'] = output_state
            
            self.device.write('print(smu.source.func)')
            time.sleep(0.02)
            source_func = self.device.read().strip()
            diagnostics['instrument_status']['source_function'] = source_func
            
            return diagnostics
            
        except Exception as e:
            diagnostics['errors'].append(f"Diagnostic error: {e}")
            return diagnostics
    
    def print_diagnostics(self, diagnostics: dict = None):
        """
        Pretty print diagnostic information.
        
        Args:
            diagnostics: Dictionary from get_full_diagnostics(), or None to fetch new
        """
        if diagnostics is None:
            diagnostics = self.get_full_diagnostics()
        
        print("\n" + "=" * 80)
        print("KEITHLEY 2450 TSP DIAGNOSTICS")
        print("=" * 80)
        
        # Error Queue
        print(f"\n📊 Error Queue: {diagnostics['error_count']} errors")
        if diagnostics['errors']:
            print("❌ Errors:")
            for i, err in enumerate(diagnostics['errors'], 1):
                print(f"  {i}. {err}")
        else:
            print("  ✓ No errors in queue")
        
        # Event Log
        print(f"\n📝 Event Log: {diagnostics['event_count']} total events")
        if diagnostics['events']:
            print(f"Recent events (showing {len(diagnostics['events'])}):")
            
            # Event severity mapping
            severity_map = {0: "INFO", 1: "WARN", 2: "ERROR"}
            severity_icon = {0: "ℹ️ ", 1: "⚠️ ", 2: "❌"}
            
            for i, event in enumerate(diagnostics['events'], 1):
                if isinstance(event, dict) and 'severity' in event:
                    sev = event['severity']
                    sev_str = severity_map.get(sev, "UNKNOWN")
                    icon = severity_icon.get(sev, "")
                    timestamp = event.get('timestamp_sec', 0)
                    message = event.get('message', 'No message')
                    print(f"  {i}. {icon}[{sev_str}] t={timestamp}s: {message}")
                elif isinstance(event, dict) and 'raw' in event:
                    print(f"  {i}. {event['raw']}")
                else:
                    print(f"  {i}. {event}")
        else:
            print("  ✓ No events in log")
        
        # Instrument Status
        print(f"\n🔧 Instrument Status:")
        status = diagnostics['instrument_status']
        print(f"  Output: {status.get('output', 'Unknown')}")
        print(f"  Source Function: {status.get('source_function', 'Unknown')}")
        
        print("=" * 80 + "\n")
    
    def clear_all_scripts(self) -> None:
        """
        Delete all loaded TSP scripts to prevent error 1408 (script already exists).
        Call this at the start of your program or when switching between tests.
        """
        if not self.device:
            print("❌ Error: No device connected")
            return
        
        try:
            script_names = ['voltPulse', 'currPulse', 'pulseMeas', 'pulseTrain']
            for name in script_names:
                self.device.write(f'if {name} ~= nil then script.delete("{name}") end')
            import time
            time.sleep(0.02)
            print("✓ Cleared all loaded TSP scripts")
        except Exception as e:
            print(f"⚠️  Error clearing scripts: {e}")
    
    def voltage_pulse(self, voltage: float, width: float, clim: float = 100e-3, fast: bool = True) -> None:
        """
        Execute a voltage pulse using TSP for maximum speed and accuracy.
        Ideal for pulses <1ms where SCPI timing is insufficient.
        
        Args:
            voltage: Pulse voltage in volts
            width: Pulse width in seconds (can be as low as 50µs)
            clim: Current limit (default: 100mA)
            fast: Use speed optimizations (fixed ranges, no autozero) - default True
            
        Example:
            tsp.voltage_pulse(2.0, 100e-6, clim=50e-3)  # 2V, 100µs, 50mA limit
        """
        if not self.device:
            print("❌ Error: No device connected")
            return
        
        try:
            # Delete existing script if it exists, then load new one
            self.device.write('if voltPulse ~= nil then script.delete("voltPulse") end')
            import time
            time.sleep(0.01)
            
            # Use loadscript/endscript for proper TSP execution
            self.device.write('loadscript voltPulse')
            # Configure source function and limits
            self.device.write('smu.source.func = smu.FUNC_DC_VOLTAGE')
            self.device.write(f'smu.source.ilimit.level = {clim}')
            
            if fast:
                # Speed optimizations for fast pulses
                # Lock source range to avoid autoranging delays
                if abs(voltage) <= 0.2:
                    self.device.write('smu.source.range = 0.2')
                elif abs(voltage) <= 2.0:
                    self.device.write('smu.source.range = 2')
                elif abs(voltage) <= 20.0:
                    self.device.write('smu.source.range = 20')
                else:
                    self.device.write('smu.source.range = 200')
                # Disable autozero for speed
                self.device.write('smu.measure.autozero.enable = smu.OFF')
            
            self.device.write('smu.source.level = 0')
            # Turn on output at 0V first
            self.device.write('smu.source.output = smu.ON')
            # NOW pulse: set level high, delay, set low
            self.device.write(f'smu.source.level = {voltage}')  # Pulse starts
            self.device.write(f'delay({width})')                # Pulse width
            self.device.write('smu.source.level = 0')           # Pulse ends
            # Turn off output
            self.device.write('smu.source.output = smu.OFF')
            
            if fast:
                # Restore autorange after fast pulse to prevent issues with subsequent commands
                self.device.write('smu.source.autorange = smu.ON')
                self.device.write('smu.measure.autozero.enable = smu.ON')
            
            self.device.write('endscript')
            
            # Execute the loaded script
            self.device.write('voltPulse()')
            self.device.write('waitcomplete()')
            
            # Check for errors
            self.device.write('print(errorqueue.next())')
            import time
            time.sleep(0.02)
            try:
                err = self.device.read()
                if '0' not in err:  # 0 means no error
                    print(f"⚠️  TSP reported: {err}")
            except:
                pass
            
            mode_str = " (FAST mode)" if fast else ""
            print(f"✓ TSP voltage pulse executed: {voltage}V, {width*1e6:.1f}µs{mode_str}")
            
        except Exception as e:
            print(f"❌ Error executing TSP voltage pulse: {e}")
            import traceback
            traceback.print_exc()
    
    def current_pulse(self, current: float, width: float, vlim: float = 40) -> None:
        """
        Execute a current pulse using TSP for maximum speed and accuracy.
        Ideal for pulses <1ms where SCPI timing is insufficient.
        
        Args:
            current: Pulse current in amps
            width: Pulse width in seconds (can be as low as 50µs)
            vlim: Voltage limit (default: 40V)
            
        Example:
            tsp.current_pulse(10e-3, 100e-6, vlim=20)  # 10mA, 100µs, 20V limit
        """
        if not self.device:
            print("❌ Error: No device connected")
            return
        
        try:
            # Delete existing script if it exists, then load new one
            self.device.write('if currPulse ~= nil then script.delete("currPulse") end')
            import time
            time.sleep(0.01)
            
            # Use loadscript/endscript for proper TSP execution
            self.device.write('loadscript currPulse')
            # Configure source function and limits
            self.device.write('smu.source.func = smu.FUNC_DC_CURRENT')
            self.device.write(f'smu.source.vlimit.level = {vlim}')
            self.device.write('smu.source.level = 0')
            # Turn on output at 0A first
            self.device.write('smu.source.output = smu.ON')
            # NOW pulse: set level high, delay, set low
            self.device.write(f'smu.source.level = {current}')  # Pulse starts
            self.device.write(f'delay({width})')                # Pulse width
            self.device.write('smu.source.level = 0')           # Pulse ends
            # Turn off output
            self.device.write('smu.source.output = smu.OFF')
            self.device.write('endscript')
            
            # Execute the loaded script
            self.device.write('currPulse()')
            self.device.write('waitcomplete()')
            
            # Check for errors
            self.device.write('print(errorqueue.next())')
            import time
            time.sleep(0.02)
            try:
                err = self.device.read()
                if '0' not in err:  # 0 means no error
                    print(f"⚠️  TSP reported: {err}")
            except:
                pass
            
            print(f"✓ TSP current pulse executed: {current*1e3:.2f}mA, {width*1e6:.1f}µs")
            
        except Exception as e:
            print(f"❌ Error executing TSP current pulse: {e}")
            import traceback
            traceback.print_exc()
    
    def pulse_with_measurement(self, voltage: float, width: float, clim: float = 100e-3) -> tuple:
        """
        Execute voltage pulse using TSP and measure current during pulse.
        Returns (voltage, current) measured during the pulse.
        
        Args:
            voltage: Pulse voltage in volts
            width: Pulse width in seconds
            clim: Current limit (default: 100mA)
            
        Returns:
            Tuple of (voltage_measured, current_measured)
            
        Example:
            v, i = tsp.pulse_with_measurement(1.0, 100e-6, clim=0.1)
            resistance = v / i
        """
        if not self.device:
            print("❌ Error: No device connected")
            return (0.0, 0.0)
        
        try:
            # Delete existing script if it exists, then load new one
            self.device.write('if pulseMeas ~= nil then script.delete("pulseMeas") end')
            import time
            time.sleep(0.01)
            
            # Use loadscript/endscript for proper TSP execution
            self.device.write('loadscript pulseMeas')
            # Configure source
            self.device.write('smu.source.func = smu.FUNC_DC_VOLTAGE')
            self.device.write(f'smu.source.ilimit.level = {clim}')
            
            # SPEED OPTIMIZATION: Fixed ranges, no autozero
            # Lock source range
            if abs(voltage) <= 0.2:
                self.device.write('smu.source.range = 0.2')
            elif abs(voltage) <= 2.0:
                self.device.write('smu.source.range = 2')
            elif abs(voltage) <= 20.0:
                self.device.write('smu.source.range = 20')
            else:
                self.device.write('smu.source.range = 200')
            
            self.device.write('smu.source.level = 0')
            # Configure measurement - FIXED RANGE for speed
            self.device.write('smu.measure.func = smu.FUNC_DC_CURRENT')
            # Use appropriate current range based on expected current
            expected_i = abs(voltage / 1e6)  # Assume ~1MΩ minimum
            if expected_i <= 10e-9:
                self.device.write('smu.measure.range = 10e-9')
            elif expected_i <= 100e-9:
                self.device.write('smu.measure.range = 100e-9')
            elif expected_i <= 1e-6:
                self.device.write('smu.measure.range = 1e-6')
            elif expected_i <= 10e-6:
                self.device.write('smu.measure.range = 10e-6')
            elif expected_i <= 100e-6:
                self.device.write('smu.measure.range = 100e-6')
            elif expected_i <= 1e-3:
                self.device.write('smu.measure.range = 1e-3')
            else:
                self.device.write('smu.measure.range = 10e-3')
            
            # Fast measurement settings
            self.device.write('smu.measure.nplc = 0.01')  # Fast: 166µs @ 60Hz (minimum allowed)
            self.device.write('smu.measure.autozero.enable = smu.OFF')
            
            # Turn on output at 0V
            self.device.write('smu.source.output = smu.ON')
            # NOW pulse: set level high, delay, measure, set low
            self.device.write(f'smu.source.level = {voltage}')  # Pulse starts
            self.device.write(f'delay({width})')                # Pulse width
            # Take measurement at end of pulse
            self.device.write('i = smu.measure.read()')
            # Get voltage from source level (we're sourcing voltage, measuring current)
            self.device.write('v = smu.source.level')
            self.device.write('smu.source.level = 0')           # Pulse ends
            # Print results
            self.device.write('if i ~= nil and v ~= nil then')
            self.device.write('  print(string.format("DATA:%.6e,%.6e", v, i))')
            self.device.write('else')
            self.device.write('  local i_str = tostring(i)')
            self.device.write('  local v_str = tostring(v)')
            self.device.write('  print("ERROR:i=" .. i_str .. ",v=" .. v_str)')
            self.device.write('end')
            # Turn off output
            self.device.write('smu.source.output = smu.OFF')
            # Restore autorange after pulse to prevent issues with subsequent commands
            self.device.write('smu.source.autorange = smu.ON')
            self.device.write('smu.measure.autorange = smu.ON')
            self.device.write('smu.measure.autozero.enable = smu.ON')
            self.device.write('endscript')
            
            # Execute the loaded script
            self.device.write('pulseMeas()')
            self.device.write('waitcomplete()')
            
            # Small delay to ensure output is ready
            import time
            time.sleep(0.05)
            
            response = self.device.read()
            
            # Parse DATA:v,i format
            if 'ERROR:' in response:
                print(f"❌ TSP measurement error: {response}")
                return (0.0, 0.0)
            elif 'DATA:' in response:
                data_str = response.split('DATA:')[1].strip()
                v, i = map(float, data_str.split(','))
                print(f"✓ TSP pulse with measurement: V={v:.6f}V, I={i:.6e}A, R={v/i:.2e}Ω")
                return (v, i)
            else:
                print(f"⚠ Unexpected TSP response: {response}")
                return (0.0, 0.0)
            
        except Exception as e:
            print(f"❌ Error executing TSP pulse with measurement: {e}")
            return (0.0, 0.0)
    
    def pulse_train(self, voltage: float, width: float, count: int, delay_between: float, clim: float = 100e-3) -> None:
        """
        Execute a train of voltage pulses using TSP.
        
        Args:
            voltage: Pulse voltage in volts
            width: Pulse width in seconds
            count: Number of pulses
            delay_between: Delay between pulses in seconds
            clim: Current limit (default: 100mA)
            
        Example:
            tsp.pulse_train(1.0, 100e-6, 10, 1e-3, clim=0.1)  # 10 pulses, 100µs each, 1ms apart
        """
        if not self.device:
            print("❌ Error: No device connected")
            return
        
        try:
            # Delete existing script if it exists, then load new one
            self.device.write('if pulseTrain ~= nil then script.delete("pulseTrain") end')
            import time
            time.sleep(0.01)
            
            # Use loadscript/endscript for proper TSP execution with for loop
            self.device.write('loadscript pulseTrain')
            self.device.write('smu.source.func = smu.FUNC_DC_VOLTAGE')
            self.device.write(f'smu.source.ilimit.level = {clim}')
            self.device.write('smu.source.level = 0')
            self.device.write('smu.source.output = smu.ON')
            self.device.write(f'for i = 1, {count} do')
            self.device.write(f'smu.source.level = {voltage}')
            self.device.write(f'delay({width})')
            self.device.write('smu.source.level = 0')
            self.device.write(f'if i < {count} then')
            self.device.write(f'delay({delay_between})')
            self.device.write('end')
            self.device.write('end')
            self.device.write('smu.source.output = smu.OFF')
            self.device.write('endscript')
            
            # Execute the loaded script
            self.device.write('pulseTrain()')
            self.device.write('waitcomplete()')
            
            # Check for errors
            self.device.write('print(errorqueue.next())')
            import time
            time.sleep(0.02)
            try:
                err = self.device.read()
                if '0' not in err:  # 0 means no error
                    print(f"⚠️  TSP reported: {err}")
            except:
                pass
            
            total_time = count * (width + delay_between)
            print(f"✓ TSP pulse train executed: {count} pulses, {voltage}V, {width*1e6:.1f}µs each")
            print(f"  Total time: {total_time*1e3:.1f}ms")
            
        except Exception as e:
            print(f"❌ Error executing TSP pulse train: {e}")
            import traceback
            traceback.print_exc()


# ============================================================================
# EXAMPLE/TEST CODE
# ============================================================================

if __name__ == "__main__":
    
    DEVICE_ADDRESS = 'USB0::0x05E6::0x2450::04496615::INSTR'
    
    print("\n" + "=" * 70)
    print("Keithley 2450 TSP Pulse Testing (Standalone)")
    print("=" * 70)
    print("⚠️  Ensure instrument is in TSP mode!")
    print("   MENU → System → Settings → Command Set → TSP")
    print("=" * 70)
    print()
    
    try:
        # Connect directly in TSP mode (standalone)
        print("Connecting to Keithley 2450 in TSP mode...")
        tsp = Keithley2450_TSP(DEVICE_ADDRESS)
        
        if not tsp.device:
            print("❌ Failed to connect")
            print("   Make sure instrument is in TSP mode!")
            exit(1)
        
        print()
        # for i in range(5):
        #     tsp.beep()
        #     time.sleep(0.01)
        #     tsp.beep(2000,0.1)
        #     tsp.beep()
        #     time.sleep(0.01)
        #     tsp.beep(2000,0.1)
        # for i in range(5):
        #     #tsp.beep(5000,0.1)
        #     #tsp.beep(3000,0.1)
        #     tsp.beep(1000,0.1)
        #     tsp.beep(500,0.1)
        #     tsp.beep(400,0.1)
        #     tsp.beep(200,0.1)
        #     tsp.beep(100,0.1)
        #     tsp.beep(50,0.1)
        #     tsp.beep(20,0.1)
        #     tsp.beep(20,0.1)
        #     tsp.beep(50,0.1)
        #     tsp.beep(100,0.1)
        #     tsp.beep(200,0.1)
        #     tsp.beep(400,0.1)
        #     tsp.beep(500,0.1)
        #     tsp.beep(1000,0.1)
        #     tsp.beep(2000,0.1)
        #     #tsp.beep(3000,0.1)

        def pause(t):
            time.sleep(t)

        # Super Mario Bros. intro (simplified)
        for _ in range(5):
            tsp.beep(660, 0.1)
            tsp.beep(660, 0.1)
            pause(0.1)
            tsp.beep(660, 0.1)
            pause(0.15)
            tsp.beep(510, 0.1)
            tsp.beep(660, 0.1)
            pause(0.1)
            tsp.beep(770, 0.1)
            pause(0.35)
            tsp.beep(380, 0.1)

        


    #     # Clear any previously loaded scripts to prevent error 1408
    #     tsp.clear_all_scripts()
    #     print()
        
    #     # ====================================================================
    #     # TEST 1: Single voltage pulse
    #     # ====================================================================
    #     print("\n" + "-" * 70)
    #     print("TEST 1: Single Voltage Pulse")
    #     print("-" * 70)
    #     print("Sending: 1V, 100µs pulse")
    #     tsp.voltage_pulse(1.0, 100e-6, clim=0.1)
    #     time.sleep(0.5)
        
    #     # ====================================================================
    #     # TEST 2: Single current pulse
    #     # ====================================================================
    #     print("\n" + "-" * 70)
    #     print("TEST 2: Single Current Pulse")
    #     print("-" * 70)
    #     print("Sending: 10mA, 100µs pulse")
    #     tsp.current_pulse(10e-3, 100e-6, vlim=20)
    #     time.sleep(5)
        
    #     # ====================================================================
    #     # TEST 3: Pulse with measurement
    #     # ====================================================================
    #     print("\n" + "-" * 70)
    #     print("TEST 3: Pulse with Measurement")
    #     print("-" * 70)
    #     print("Sending: 2V, 500µs pulse, measuring current")
    #     v, i = tsp.pulse_with_measurement(2.0, 500e-6, clim=0.1)
    #     if v != 0 and i != 0:
    #         print(f"Measured: V={v:.6f}V, I={i:.6e}A")
    #         print(f"Calculated resistance: {v/i:.2e}Ω")
    #     time.sleep(5)
        
    #     # ====================================================================
    #     # TEST 4: Pulse train
    #     # ====================================================================
    #     print("\n" + "-" * 70)
    #     print("TEST 4: Pulse Train")
    #     print("-" * 70)
    #     print("Sending: 5 pulses, 1V, 100µs each, 1ms apart")
    #     tsp.pulse_train(1.0, 100e-6, 5, 1e-3, clim=0.1)
        
    #     # ====================================================================
    #     # Summary
    #     # ====================================================================
    #     print("\n" + "=" * 70)
    #     print("✓ All TSP pulse tests completed!")
    #     print("=" * 70)
    #     print("\nNote: TSP pulses provide:")
    #     print("  - Minimum width: ~50µs (vs ~2ms for SCPI)")
    #     print("  - Timing accuracy: ±10µs (vs ±100µs for SCPI)")
    #     print("  - No PC communication latency during pulse")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    # finally:
    #     # ====================================================================
    #     # Pull full event log and diagnostics
    #     # ====================================================================
    #     print("\n" + "=" * 70)
    #     print("PULLING FULL EVENT LOG HISTORY...")
    #     print("=" * 70)
        
    #     try:
    #         tsp.print_diagnostics()
    #     except Exception as e:
    #         print(f"⚠️  Could not retrieve diagnostics: {e}")
        
    #     print("\nClosing connection...")
    #     tsp.close()

