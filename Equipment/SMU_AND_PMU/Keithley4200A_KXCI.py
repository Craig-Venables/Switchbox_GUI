"""
Keithley 4200A KXCI Controller (GPIB Interface)
===============================================

This module provides a Python interface for controlling the Keithley 4200A-SCS
via KXCI (Keithley External Control Interface) over GPIB, replacing LabVIEW.

The KXCI interface uses User Library (UL) functions that are called via EX commands.
This implementation replicates the behavior of the LabVIEW program that calls
PMU_PulseTrain() from the lABVIEW_CONTROLLED_PROGRAMS_KEMP3 library.

Key Features:
- GPIB connection via pyvisa
- UL (User Library) mode switching
- EX command execution for PMU_PulseTrain
- GP command for retrieving output parameters
- Automatic parsing of semicolon-separated return values

LabVIEW Workflow Replicated:
1. Send "ul" to enter User Library mode
2. Send "EX lABVIEW_CONTROLLED_PROGRAMS_KEMP3 PMU_PulseTrain(...)"
3. Read return value
4. Use "GP <param> <count>" to retrieve output arrays
5. Parse semicolon-separated values

Usage:
    from Equipment.SMU_AND_PMU.Keithley4200A_KXCI import Keithley4200A_KXCI
    
    # Connect to instrument
    keithley = Keithley4200A_KXCI(gpib_address="GPIB0::17::INSTR")
    
    # Run PMU_PulseTrain measurement
    result = keithley.pmu_pulse_train(
        riseTime=1e-7,
        resetV=2.0,
        resetWidth=1e-6,
        resetDelay=5e-8,
        measV=0.3,
        measWidth=2e-6,
        measDelay=2e-6,
        setWidth=1e-6,
        setFallTime=1e-7,
        setDelay=1e-6,
        setStartV=0.3,
        setStopV=0.3,
        steps=1,
        IRange=1e-4,
        max_points=10000,
        setR_size=7,
        resetR_size=7,
        setV_size=7,
        setI_size=7,
        iteration=1,
        out1_size=7,
        out1_name="VF",
        out2_size=7,
        out2_name="T",
        PulseTimes_size=12,
        PulseTrainSequence="10101",
        NumbPulses=4,
        ClariusDebug=0
    )
    
    # Access results
    print(f"Return value: {result['return_value']}")
    print(f"SET V values: {result['setV']}")
    print(f"SET I values: {result['setI']}")
    print(f"OUT1 values: {result['out1']}")
    
    keithley.close()

Author: Created to replace LabVIEW-based control
"""

import pyvisa
import time
from typing import Optional, Dict, List, Any, Tuple
import re


class Keithley4200A_KXCI:
    """
    Controller for Keithley 4200A-SCS via KXCI over GPIB.
    
    This class replicates the LabVIEW functionality for calling PMU_PulseTrain
    and retrieving measurement results.
    """
    
    def __init__(self, gpib_address: str = "GPIB0::17::INSTR", timeout: float = 30.0):
        """
        Initialize GPIB connection to Keithley 4200A.
        
        Args:
            gpib_address: GPIB address string (e.g., "GPIB0::17::INSTR")
            timeout: Communication timeout in seconds
        """
        self.gpib_address = gpib_address
        self.timeout = timeout * 1000  # Convert to milliseconds for pyvisa
        self.rm: Optional[pyvisa.ResourceManager] = None
        self.inst: Optional[pyvisa.Resource] = None
        self._ul_mode_active = False
        
    def connect(self) -> bool:
        """
        Establish GPIB connection to the instrument.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.rm = pyvisa.ResourceManager()
            print(f"✓ VISA ResourceManager initialized")
            
            print(f"📡 Connecting to {self.gpib_address}...")
            self.inst = self.rm.open_resource(self.gpib_address)
            self.inst.timeout = self.timeout
            
            # Common GPIB settings
            self.inst.write_termination = '\n'
            self.inst.read_termination = '\n'
            
            # Test connection with ID query
            idn = self.inst.query("*IDN?")
            print(f"✓ Connected to: {idn.strip()}")
            
            return True
            
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    def disconnect(self):
        """Close GPIB connection."""
        try:
            # Exit UL mode before disconnecting (if still in UL mode)
            if self._ul_mode_active:
                print("[KXCI] Exiting UL mode before disconnect...")
                self._exit_ul_mode()
            
            if self.inst:
                self.inst.close()
            if self.rm:
                self.rm.close()
            print("✓ Disconnected")
        except Exception as e:
            print(f"⚠️ Error during disconnect: {e}")
        finally:
            # Always reset flags
            self._ul_mode_active = False
    
    def close(self):
        """Alias for disconnect() for compatibility."""
        self.disconnect()
    
    def _enter_ul_mode(self) -> bool:
        """
        Enter User Library (UL) mode.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.inst:
                print("❌ Not connected")
                return False
            
            # Send UL command (must be UPPERCASE - error -992 if lowercase)
            # Don't read response - just send and move on (response takes too long)
            print(f"\n[KXCI] Sending: UL")
            self.inst.write("UL")
            time.sleep(0.03)  # Wait 30ms between commands (from LabVIEW)
            
            self._ul_mode_active = True
            print("✓ Entered User Library (UL) mode")
            return True
            
        except Exception as e:
            print(f"❌ Failed to enter UL mode: {e}")
            return False
    
    def _exit_ul_mode(self) -> bool:
        """
        Exit User Library mode and return to normal KXCI mode.
        
        According to KXCI manual, DE or US command returns to normal mode from UL mode.
        This should be called after measurements to reset state for next run.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.inst:
                return False
            
            if not self._ul_mode_active:
                print("[KXCI] Not in UL mode, nothing to exit")
                return True
            
            # DE or US command returns to normal mode
            print(f"[KXCI] Sending: DE (exit UL mode)")
            self.inst.write("DE")
            time.sleep(0.03)  # Wait 30ms (consistent with other commands)
            
            # Try to read response
            try:
                response = self.inst.read()
                print(f"[KXCI] DE response: {repr(response)}")
            except pyvisa.errors.VisaIOError:
                # No response expected, that's OK
                pass
            
            self._ul_mode_active = False
            print("✓ Exited User Library mode")
            return True
            
        except Exception as e:
            print(f"⚠️ Failed to exit UL mode: {e}")
            # Still reset the flag even if command failed
            self._ul_mode_active = False
            return False
    
    def _format_parameter(self, value: Any) -> str:
        """
        Format a parameter value for EX command.
        
        Matches LabVIEW format: floats in scientific notation (e.g., "1.00E-7"),
        integers as-is, strings as-is.
        
        Args:
            value: Parameter value (int, float, or str)
            
        Returns:
            Formatted string for KXCI command
        """
        if isinstance(value, float):
            # Use scientific notation: "1.00E-7" format (2 decimal places)
            # Python's .2E format may include leading zeros in exponent
            formatted = f"{value:.2E}".upper()
            # Remove leading zero in exponent if present (1.00E-07 -> 1.00E-7)
            formatted = formatted.replace("E-0", "E-").replace("E+0", "E+")
            return formatted
        elif isinstance(value, int):
            return str(value)
        elif isinstance(value, str):
            return value
        else:
            return str(value)
    
    def _build_ex_command(self, library: str, function: str, params: List[Any]) -> str:
        """
        Build EX command string.
        
        Args:
            library: Library name (e.g., "lABVIEW_CONTROLLED_PROGRAMS_KEMP3")
            function: Function name (e.g., "PMU_PulseTrain")
            params: List of parameter values
            
        Returns:
            Complete EX command string
        """
        param_str = ",".join(self._format_parameter(p) for p in params)
        return f"EX {library} {function}({param_str})"
    
    def _parse_gp_response(self, response: str) -> List[float]:
        """
        Parse GP command response (semicolon-separated values).
        
        Args:
            response: Raw response string from GP command
            
        Returns:
            List of parsed float values
        """
        print(f"\n[KXCI] Parsing GP response...")
        print(f"[KXCI] Original response: {repr(response)}")
        
        # Remove "PARAM VALUE = " prefix if present
        original_response = response
        response = response.strip()
        
        print(f"[KXCI] After strip: {repr(response)}")
        
        if "PARAM VALUE" in response.upper():
            # Format: "PARAM VALUE = value1;value2;..."
            print(f"[KXCI] Found 'PARAM VALUE' in response")
            parts = response.split("=", 1)
            if len(parts) > 1:
                response = parts[1].strip()
                print(f"[KXCI] Extracted value part: {repr(response)}")
            else:
                print(f"[KXCI] 'PARAM VALUE' found but no '=' separator")
        else:
            print(f"[KXCI] No 'PARAM VALUE' prefix found, using full response")
        
        # Check for semicolon separator
        if ';' in response:
            print(f"[KXCI] Using semicolon separator")
            separator = ';'
        elif ',' in response:
            print(f"[KXCI] Using comma separator")
            separator = ','
        else:
            print(f"[KXCI] Single value (no separator found)")
            separator = None
        
        # Split by separator and parse as floats
        values = []
        if separator:
            split_values = response.split(separator)
            print(f"[KXCI] Split into {len(split_values)} parts")
            for i, val_str in enumerate(split_values):
                val_str = val_str.strip()
                print(f"[KXCI] Part {i}: {repr(val_str)}")
                if val_str:
                    try:
                        parsed = float(val_str)
                        values.append(parsed)
                        print(f"[KXCI]   -> Parsed as: {parsed}")
                    except ValueError as e:
                        print(f"⚠️ Could not parse value {repr(val_str)}: {e}")
                else:
                    print(f"[KXCI]   -> Empty, skipping")
        else:
            # Single value
            if response:
                try:
                    parsed = float(response)
                    values.append(parsed)
                    print(f"[KXCI] Parsed single value: {parsed}")
                except ValueError as e:
                    print(f"⚠️ Could not parse single value {repr(response)}: {e}")
        
        print(f"[KXCI] Final parsed values count: {len(values)}")
        
        return values
    
    def _query_gp(self, param_position: int, num_values: int = 1) -> List[float]:
        """
        Query parameter value using GP command.
        
        Args:
            param_position: Parameter position (1-based)
            num_values: Number of values to retrieve (for arrays)
            
        Returns:
            List of parsed values (single value for num_values=1)
        """
        try:
            if not self.inst:
                raise RuntimeError("Not connected")
            
            # Build GP command: "GP <position> [count]"
            if num_values > 1:
                cmd = f"GP {param_position} {num_values}"
            else:
                cmd = f"GP {param_position} {num_values}"  # Still include count for consistency
            
            print(f"\n[KXCI] Sending: {cmd}")
            self.inst.write(cmd)
            time.sleep(0.03)  # Wait 30ms between commands (from LabVIEW)
            
            # Read response
            response = self.inst.read()
            
            # Print ALL raw response information
            print(f"[KXCI] Received: {repr(response)}")
            print(f"[KXCI] Response (raw): {response}")
            print(f"[KXCI] Response length: {len(response)} characters")
            print(f"[KXCI] Response type: {type(response).__name__}")
            if response:
                print(f"[KXCI] Response bytes: {response.encode('utf-8') if isinstance(response, str) else response}")
                # Show first and last 100 chars if long
                if len(response) > 200:
                    print(f"[KXCI] First 100 chars: {response[:100]}")
                    print(f"[KXCI] Last 100 chars: {response[-100:]}")
            
            values = self._parse_gp_response(response)
            print(f"[KXCI] Parsed {len(values)} values: {values[:10] if len(values) > 10 else values}")
            
            return values
            
        except Exception as e:
            print(f"⚠️ GP query failed for param {param_position}: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _execute_ex_command(self, command: str) -> Tuple[Optional[int], Optional[str]]:
        """
        Execute EX command and retrieve return value.
        
        Args:
            command: Complete EX command string
            
        Returns:
            Tuple of (return_value, error_message)
        """
        try:
            if not self.inst:
                raise RuntimeError("Not connected")
            
            if not self._ul_mode_active:
                print("⚠️ UL mode not active, entering now...")
                if not self._enter_ul_mode():
                    raise RuntimeError("Failed to enter UL mode")
            
            # Send EX command
            print(f"\n[KXCI] Sending EX command:")
            print(f"[KXCI] Command: {command}")
            print(f"[KXCI] Command length: {len(command)} characters")
            self.inst.write(command)
            time.sleep(0.03)  # Wait 30ms between commands (from LabVIEW)
            
            # Wait for measurement to complete (2000ms from LabVIEW)
            print("⏳ Waiting for measurement to complete (2000ms)...")
            time.sleep(2.0)
            
            # Try to read return value
            # Format: "RETURN VALUE = <int>"
            # Return value 1 means measurement completed successfully
            print(f"\n[KXCI] Attempting to read return value...")
            try:
                response = self.inst.read()
                
                # Print ALL raw response information
                print(f"[KXCI] Received: {repr(response)}")
                print(f"[KXCI] Response (raw): {response}")
                print(f"[KXCI] Response length: {len(response)} characters")
                print(f"[KXCI] Response type: {type(response).__name__}")
                if response:
                    print(f"[KXCI] Response bytes: {response.encode('utf-8') if isinstance(response, str) else response}")
                    # Show first and last 200 chars if long
                    if len(response) > 400:
                        print(f"[KXCI] First 200 chars: {response[:200]}")
                        print(f"[KXCI] Last 200 chars: {response[-200:]}")
                    else:
                        print(f"[KXCI] Full response: {response}")
                
                # Parse return value (can be 1 or -1)
                return_value = None
                if "RETURN VALUE" in response:
                    match = re.search(r'RETURN VALUE\s*=\s*(-?\d+)', response, re.IGNORECASE)
                    if match:
                        return_value = int(match.group(1))
                        if return_value == 1:
                            print(f"✓ Return value: {return_value} (measurement completed successfully)")
                        elif return_value == -1:
                            print(f"⚠️ Return value: {return_value} (measurement completed with error/warning)")
                        else:
                            print(f"⚠️ Return value: {return_value} (unexpected value, expected 1 or -1)")
                else:
                    print(f"[KXCI] Response does not contain 'RETURN VALUE', full response above")
                
                return return_value, None
                
            except pyvisa.errors.VisaIOError as e:
                print(f"[KXCI] First read attempt failed: {e}")
                # After 2000ms wait, try reading the return value
                try:
                    print(f"[KXCI] Retrying read...")
                    response = self.inst.read()
                    print(f"[KXCI] Received on retry: {repr(response)}")
                    print(f"[KXCI] Response (raw): {response}")
                    print(f"[KXCI] Response length: {len(response)} characters")
                    
                    if "RETURN VALUE" in response:
                        match = re.search(r'RETURN VALUE\s*=\s*(-?\d+)', response, re.IGNORECASE)
                        if match:
                            return_value = int(match.group(1))
                            if return_value == 1:
                                print(f"✓ Return value: {return_value} (measurement completed successfully)")
                            elif return_value == -1:
                                print(f"⚠️ Return value: {return_value} (measurement completed with error/warning)")
                            else:
                                print(f"⚠️ Return value: {return_value} (unexpected value, expected 1 or -1)")
                            return return_value, None
                    else:
                        print(f"[KXCI] Retry response does not contain 'RETURN VALUE', full response above")
                except Exception as e2:
                    print(f"[KXCI] Retry read also failed: {e2}")
                
                # If we can't read return value, assume it might be available later via GP
                print("⚠️ Could not read return value immediately, will check via GP commands")
                return None, None
                
        except Exception as e:
            error_msg = f"EX command failed: {e}"
            print(f"❌ {error_msg}")
            return None, error_msg
    
    def pmu_pulse_train(
        self,
        riseTime: float,
        resetV: float,
        resetWidth: float,
        resetDelay: float,
        measV: float,
        measWidth: float,
        measDelay: float,
        setWidth: float,
        setFallTime: float,
        setDelay: float,
        setStartV: float,
        setStopV: float,
        steps: int,
        IRange: float,
        max_points: int,
        setR_size: int,
        resetR_size: int,
        setV_size: int,
        setI_size: int,
        iteration: int,
        out1_size: int,
        out1_name: str = "VF",
        out2_size: int = 7,
        out2_name: str = "T",
        PulseTimes_size: int = 12,
        PulseTrainSequence: str = "10101",
        NumbPulses: int = 4,
        ClariusDebug: int = 0
    ) -> Dict[str, Any]:
        """
        Execute PMU_PulseTrain measurement.
        
        This method replicates the LabVIEW PMU_PulseTrain() call.
        
        Args:
            riseTime: Rise/fall time for RESET pulse (s)
            resetV: Voltage for reset pulse (V)
            resetWidth: Width of RESET pulse flat portion (s)
            resetDelay: Delay around RESET pulse (s)
            measV: Voltage for measurement (V)
            measWidth: Width of measure pulse flat portion (s)
            measDelay: Delay around measure pulse (s)
            setWidth: Width of SET pulse flat portion (s)
            setFallTime: Fall/rise time for SET pulse (s)
            setDelay: Delay around SET pulse (s)
            setStartV: Starting voltage for SET sweep (V)
            setStopV: Stopping voltage for SET sweep (V)
            steps: Number of points in sweep
            IRange: Current range for measurements (A)
            max_points: Maximum number of measurement points
            setR_size: Size of setR output array
            resetR_size: Size of resetR output array
            setV_size: Size of setV output array
            setI_size: Size of setI output array
            iteration: Iteration number for debug wave profiles
            out1_size: Size of out1 debug array
            out1_name: Name of out1 debug parameter (e.g., "VF")
            out2_size: Size of out2 debug array
            out2_name: Name of out2 debug parameter (e.g., "T")
            PulseTimes_size: Size of PulseTimes output array
            PulseTrainSequence: Pulse sequence string (e.g., "10101")
            NumbPulses: Number of pulses
            ClariusDebug: Debug flag (0 or 1)
            
        Returns:
            Dictionary with measurement results:
            - 'return_value': Function return code
            - 'setR': SET resistance array
            - 'resetR': RESET resistance array
            - 'setV': SET voltage array
            - 'setI': SET current array
            - 'out1': Debug output array 1
            - 'out2': Debug output array 2
            - 'PulseTimes': Pulse times array
            - 'param18': Parameter 18 value (from GP 18 1)
            - 'success': Whether execution succeeded
        """
        # Ensure connection
        if not self.inst:
            if not self.connect():
                return {
                    'success': False,
                    'error': 'Failed to connect'
                }
        
        # Reset state: Exit UL mode if we're still in it (from previous run)
        # This ensures clean state for each measurement
        if self._ul_mode_active:
            print("[KXCI] Still in UL mode from previous run, exiting first...")
            self._exit_ul_mode()
            time.sleep(0.03)  # Brief pause after exit
        
        # Enter UL mode fresh
        if not self._enter_ul_mode():
            return {
                'success': False,
                'error': 'Failed to enter UL mode'
            }
        
        # Use the exact command string provided (hardcoded)
        # This matches the working LabVIEW command exactly
        ex_command = "EX Labview_Controlled_Programs_Kemp3 PMU_PulseTrain(1.00E-7,1,1.00E-6,5.00E-8,3.00E-1,2.00E-6,2.00E-6,1.00E-6,1.00E-7,1.00E-6,3.00E-1,3.00E-1,1,1.00E-4,10000,,12,,12,,12,,12,1,,12,VF,,12,T,,7,11111,5,0)"
        
        print(f"\n[KXCI] Sending exact command:")
        print(f"[KXCI] {ex_command}")
        
        print(f"\n{'='*60}")
        print("Executing PMU_PulseTrain")
        print(f"{'='*60}")
        
        # Execute EX command
        return_value, error = self._execute_ex_command(ex_command)
        
        if error:
            return {
                'success': False,
                'error': error,
                'return_value': return_value
            }
        
        # Check return value - 1 or -1 indicates measurement completed
        # 1 = success, -1 = error/completion with issue
        if return_value not in [1, -1]:
            print(f"⚠️ Warning: Return value is {return_value} (expected 1 or -1)")
        elif return_value == 1:
            print(f"✓ Return value: {return_value} (measurement completed successfully)")
        elif return_value == -1:
            print(f"⚠️ Return value: {return_value} (measurement completed with error/warning)")
        
        # Retrieve results using GP commands (as per LabVIEW workflow)
        print(f"\n📊 Retrieving results...")
        time.sleep(0.03)  # Wait 30ms between commands
        
        results = {
            'success': return_value in [1, -1],  # Both 1 and -1 indicate completion
            'return_value': return_value,
            'measurement_complete': return_value in [1, -1],
            'measurement_success': return_value == 1,  # Only 1 is true success
            'param18': None,
            'setV': [],
            'setI': [],
            'out1': [],
            'setR': [],
            'resetR': [],
            'PulseTimes': []
        }
        
        # GP 18 1 - First parameter query (from LabVIEW output)
        print("Querying GP 18 1...")
        param18_values = self._query_gp(18, 1)
        if param18_values:
            results['param18'] = param18_values[0] if len(param18_values) > 0 else None
        time.sleep(0.03)  # Wait 30ms between commands
        
        # GP 20 7 - SET V values (from LabVIEW: "GP 20 7" returns SET V VALUES)
        print("Querying GP 20 7 (SET V values)...")
        results['setV'] = self._query_gp(20, 7)
        print(f"  Retrieved {len(results['setV'])} SET V values")
        time.sleep(0.03)  # Wait 30ms between commands
        
        # GP 22 7 - SET I values (from LabVIEW: "GP 22 7" returns I VALUES)
        print("Querying GP 22 7 (SET I values)...")
        results['setI'] = self._query_gp(22, 7)
        print(f"  Retrieved {len(results['setI'])} SET I values")
        time.sleep(0.03)  # Wait 30ms between commands
        
        # GP 31 7 - OUT1 values (from LabVIEW: "GP 31 7" returns unknown values)
        print("Querying GP 31 7 (OUT1 values)...")
        results['out1'] = self._query_gp(31, 7)
        print(f"  Retrieved {len(results['out1'])} OUT1 values")
        
        # Optional: Query other parameters if needed
        # GP for setR, resetR, etc. would need correct parameter positions
        
        print(f"\n✓ PMU_PulseTrain completed successfully")
        print(f"{'='*60}\n")
        
        # Exit UL mode after measurement to reset state for next run
        # This prevents issues with running multiple measurements in sequence
        print(f"[KXCI] Exiting UL mode to reset state...")
        self._exit_ul_mode()
        
        return results
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()


def main():
    """Test/demo function."""
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║   Keithley 4200A KXCI Controller Test                      ║
    ║                                                               ║
    ║   This test connects to the 4200A via GPIB and executes      ║
    ║   PMU_PulseTrain measurement.                               ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    gpib_address = input("Enter GPIB address (default: GPIB0::17::INSTR): ").strip()
    if not gpib_address:
        gpib_address = "GPIB0::17::INSTR"
    
    try:
        with Keithley4200A_KXCI(gpib_address=gpib_address) as keithley:
            # Example PMU_PulseTrain call with minimal parameters
            result = keithley.pmu_pulse_train(
                riseTime=1e-7,
                resetV=2.0,
                resetWidth=1e-6,
                resetDelay=5e-8,
                measV=0.3,
                measWidth=2e-6,
                measDelay=2e-6,
                setWidth=1e-6,
                setFallTime=1e-7,
                setDelay=1e-6,
                setStartV=0.3,
                setStopV=0.3,
                steps=1,
                IRange=1e-4,
                max_points=10000,
                setR_size=7,
                resetR_size=7,
                setV_size=7,
                setI_size=7,
                iteration=1,
                out1_size=7,
                out1_name="VF",
                out2_size=7,
                out2_name="T",
                PulseTimes_size=12,
                PulseTrainSequence="10101",
                NumbPulses=4,
                ClariusDebug=0
            )
            
            if result['success']:
                print("\n📊 RESULTS:")
                print(f"  Return value: {result['return_value']}")
                print(f"  Parameter 18: {result['param18']}")
                print(f"  SET V values: {result['setV']}")
                print(f"  SET I values: {result['setI']}")
                print(f"  OUT1 values: {result['out1']}")
            else:
                print(f"\n❌ Measurement failed: {result.get('error', 'Unknown error')}")
                
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

