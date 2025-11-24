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
    from Equipment.SMU_AND_PMU import Keithley4200A_KXCI
    
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
    
    def __init__(self, gpib_address: str = "GPIB0::17::INSTR", timeout: float = 30.0, debug: bool = False):
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
        self._debug = bool(debug)
        
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
    
    def set_debug(self, enabled: bool) -> None:
        """Enable or disable verbose KXCI logging."""
        self._debug = bool(enabled)
    
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
            # Don't wait for response - just send and move on
            print(f"[KXCI] Sending: DE (exit UL mode)")
            self.inst.write("DE")
            time.sleep(0.03)  # Wait 30ms (consistent with other commands)
            
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
        if self._debug:
            print(f"\n[KXCI] Parsing GP response...")
            print(f"[KXCI] Original response: {repr(response)}")
        
        # Remove "PARAM VALUE = " prefix if present
        original_response = response
        response = response.strip()
        
        if self._debug:
            print(f"[KXCI] After strip: {repr(response)}")
        
        if "PARAM VALUE" in response.upper():
            # Format: "PARAM VALUE = value1;value2;..."
            if self._debug:
                print(f"[KXCI] Found 'PARAM VALUE' in response")
            parts = response.split("=", 1)
            if len(parts) > 1:
                response = parts[1].strip()
                if self._debug:
                    print(f"[KXCI] Extracted value part: {repr(response)}")
            elif self._debug:
                print(f"[KXCI] 'PARAM VALUE' found but no '=' separator")
        elif self._debug:
            print(f"[KXCI] No 'PARAM VALUE' prefix found, using full response")
        
        # Check for semicolon separator
        if ';' in response:
            if self._debug:
                print(f"[KXCI] Using semicolon separator")
            separator = ';'
        elif ',' in response:
            if self._debug:
                print(f"[KXCI] Using comma separator")
            separator = ','
        else:
            if self._debug:
                print(f"[KXCI] Single value (no separator found)")
            separator = None
        
        # Split by separator and parse as floats
        values = []
        if separator:
            split_values = response.split(separator)
            if self._debug:
                print(f"[KXCI] Split into {len(split_values)} parts")
            for i, val_str in enumerate(split_values):
                val_str = val_str.strip()
                if self._debug:
                    print(f"[KXCI] Part {i}: {repr(val_str)}")
                if val_str:
                    try:
                        parsed = float(val_str)
                        values.append(parsed)
                        if self._debug:
                            print(f"[KXCI]   -> Parsed as: {parsed}")
                    except ValueError as e:
                        print(f"⚠️ Could not parse value {repr(val_str)}: {e}")
                else:
                    if self._debug:
                        print(f"[KXCI]   -> Empty, skipping")
        else:
            # Single value
            if response:
                try:
                    parsed = float(response)
                    values.append(parsed)
                    if self._debug:
                        print(f"[KXCI] Parsed single value: {parsed}")
                except ValueError as e:
                    print(f"⚠️ Could not parse single value {repr(response)}: {e}")
        
        if self._debug:
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
            
            if self._debug:
                print(f"\n[KXCI] Sending: {cmd}")
            self.inst.write(cmd)
            time.sleep(0.03)  # Wait 30ms between commands (from LabVIEW)
            
            # Read response
            response = self.inst.read()
            
            # Print ALL raw response information
            if self._debug:
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
            if self._debug:
                print(f"[KXCI] Parsed {len(values)} values: {values[:10] if len(values) > 10 else values}")
            
            return values
            
        except Exception as e:
            print(f"⚠️ GP query failed for param {param_position}: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _execute_ex_command(self, command: str, wait_seconds: float = 2.0) -> Tuple[Optional[int], Optional[str]]:
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
            if self._debug:
                print(f"\n[KXCI] Sending EX command:")
                print(f"[KXCI] Command: {command}")
                print(f"[KXCI] Command length: {len(command)} characters")
            self.inst.write(command)
            time.sleep(0.03)  # Wait 30ms between commands (from LabVIEW)
            
            # Wait for measurement to complete (2000ms from LabVIEW)
            wait_seconds = max(0.01, wait_seconds)
            if self._debug:
                print(f"⏳ Waiting for measurement to complete ({wait_seconds:.3f}s)...")
            time.sleep(wait_seconds)
            
            # Try to read return value
            # Format: "RETURN VALUE = <int>"
            # Return value 1 means measurement completed successfully
            if self._debug:
                print(f"\n[KXCI] Attempting to read return value...")
            try:
                response = self.inst.read()
                
                # Print ALL raw response information
                if self._debug:
                    print(f"[KXCI] Received: {repr(response)}")
                    print(f"[KXCI] Response (raw): {response}")
                    print(f"[KXCI] Response length: {len(response)} characters")
                    print(f"[KXCI] Response type: {type(response).__name__}")
                    if response:
                        print(f"[KXCI] Response bytes: {response.encode('utf-8') if isinstance(response, str) else response}")
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
                        if return_value == 1 and self._debug:
                            print(f"✓ Return value: {return_value} (measurement completed successfully)")
                        elif return_value == -1 and self._debug:
                            print(f"⚠️ Return value: {return_value} (measurement completed with error/warning)")
                        elif self._debug:
                            print(f"⚠️ Return value: {return_value} (unexpected value, expected 1 or -1)")
                elif self._debug:
                    print(f"[KXCI] Response does not contain 'RETURN VALUE', full response above")
                
                return return_value, None
                
            except pyvisa.errors.VisaIOError as e:
                if self._debug:
                    print(f"[KXCI] First read attempt failed: {e}")
                # After 2000ms wait, try reading the return value
                try:
                    if self._debug:
                        print(f"[KXCI] Retrying read...")
                    response = self.inst.read()
                    if self._debug:
                        print(f"[KXCI] Received on retry: {repr(response)}")
                        print(f"[KXCI] Response (raw): {response}")
                        print(f"[KXCI] Response length: {len(response)} characters")
                    
                    if "RETURN VALUE" in response:
                        match = re.search(r'RETURN VALUE\s*=\s*(-?\d+)', response, re.IGNORECASE)
                        if match:
                            return_value = int(match.group(1))
                            if return_value == 1 and self._debug:
                                print(f"✓ Return value: {return_value} (measurement completed successfully)")
                            elif return_value == -1 and self._debug:
                                print(f"⚠️ Return value: {return_value} (measurement completed with error/warning)")
                            elif self._debug:
                                print(f"⚠️ Return value: {return_value} (unexpected value, expected 1 or -1)")
                            return return_value, None
                    elif self._debug:
                        print(f"[KXCI] Retry response does not contain 'RETURN VALUE', full response above")
                except Exception as e2:
                    if self._debug:
                        print(f"[KXCI] Retry read also failed: {e2}")
                
                # If we can't read return value, assume it might be available later via GP
                if self._debug:
                    print("⚠️ Could not read return value immediately, will check via GP commands")
                return None, None
                
        except Exception as e:
            error_msg = f"EX command failed: {e}"
            print(f"❌ {error_msg}")
            return None, error_msg
    
    # PMU_PulseTrain function commented out - using PMU_retention as main function
    # def pmu_pulse_train(
    #     self,
    #     riseTime: float,
    #     resetV: float,
    #     resetWidth: float,
    #     resetDelay: float,
    #     measV: float,
    #     measWidth: float,
    #     measDelay: float,
    #     setWidth: float,
    #     setFallTime: float,
    #     setDelay: float,
    #     setStartV: float,
    #     setStopV: float,
    #     steps: int,
    #     IRange: float,
    #     max_points: int,
    #     setR_size: int,
    #     resetR_size: int,
    #     setV_size: int,
    #     setI_size: int,
    #     iteration: int,
    #     out1_size: int,
    #     out1_name: str = "VF",
    #     out2_size: int = 7,
    #     out2_name: str = "T",
    #     PulseTimes_size: int = 12,
    #     PulseTrainSequence: str = "10101",
    #     NumbPulses: int = 4,
    #     ClariusDebug: int = 0
    # ) -> Dict[str, Any]:
    #     """
    #     Execute PMU_PulseTrain measurement.
    #     
    #     This method replicates the LabVIEW PMU_PulseTrain() call.
    #     
    #     Args:
    #         riseTime: Rise/fall time for RESET pulse (s)
    #         resetV: Voltage for reset pulse (V)
    #         resetWidth: Width of RESET pulse flat portion (s)
    #         resetDelay: Delay around RESET pulse (s)
    #         measV: Voltage for measurement (V)
    #         measWidth: Width of measure pulse flat portion (s)
    #         measDelay: Delay around measure pulse (s)
    #         setWidth: Width of SET pulse flat portion (s)
    #         setFallTime: Fall/rise time for SET pulse (s)
    #         setDelay: Delay around SET pulse (s)
    #         setStartV: Starting voltage for SET sweep (V)
    #         setStopV: Stopping voltage for SET sweep (V)
    #         steps: Number of points in sweep
    #         IRange: Current range for measurements (A)
    #         max_points: Maximum number of measurement points
    #         setR_size: Size of setR output array
    #         resetR_size: Size of resetR output array
    #         setV_size: Size of setV output array
    #         setI_size: Size of setI output array
    #         iteration: Iteration number for debug wave profiles
    #         out1_size: Size of out1 debug array
    #         out1_name: Name of out1 debug parameter (e.g., "VF")
    #         out2_size: Size of out2 debug array
    #         out2_name: Name of out2 debug parameter (e.g., "T")
    #         PulseTimes_size: Size of PulseTimes output array
    #         PulseTrainSequence: Pulse sequence string (e.g., "10101")
    #         NumbPulses: Number of pulses
    #         ClariusDebug: Debug flag (0 or 1)
    #         
    #     Returns:
    #         Dictionary with measurement results:
    #         - 'return_value': Function return code
    #         - 'setR': SET resistance array
    #         - 'resetR': RESET resistance array
    #         - 'setV': SET voltage array
    #         - 'setI': SET current array
    #         - 'out1': Debug output array 1
    #         - 'out2': Debug output array 2
    #         - 'PulseTimes': Pulse times array
    #         - 'param18': Parameter 18 value (from GP 18 1)
    #         - 'success': Whether execution succeeded
    #     """
    #     # Ensure connection
    #     if not self.inst:
    #         if not self.connect():
    #             return {
    #                 'success': False,
    #                 'error': 'Failed to connect'
    #             }
    #     
    #     # Reset state: Exit UL mode if we're still in it (from previous run)
    #     # This ensures clean state for each measurement
    #     if self._ul_mode_active:
    #         print("[KXCI] Still in UL mode from previous run, exiting first...")
    #         self._exit_ul_mode()
    #         time.sleep(0.03)  # Brief pause after exit
    #     
    #     # Enter UL mode fresh
    #     if not self._enter_ul_mode():
    #         return {
    #             'success': False,
    #             'error': 'Failed to enter UL mode'
    #         }
    #     
    #     # Use the exact command string provided (hardcoded)
    #     # This matches the working LabVIEW command exactly
    #     ex_command = "EX Labview_Controlled_Programs_Kemp3 PMU_PulseTrain(1.00E-7,1,1.00E-6,5.00E-8,3.00E-1,2.00E-6,2.00E-6,1.00E-6,1.00E-7,1.00E-6,3.00E-1,3.00E-1,1,1.00E-4,10000,,12,,12,,12,,12,1,,12,VF,,12,T,,7,11111,5,0)"
    #     
    #     print(f"\n[KXCI] Sending exact command:")
    #     print(f"[KXCI] {ex_command}")
    #     
    #     print(f"\n{'='*60}")
    #     print("Executing PMU_PulseTrain")
    #     print(f"{'='*60}")
    #     
    #     # Execute EX command
    #     return_value, error = self._execute_ex_command(ex_command)
    #     
    #     # Only fail immediately if there's a real error (not just missing return value)
    #     # If error is None, the measurement likely succeeded even if we couldn't read return value
    #     if error and "failed" in error.lower():
    #         return {
    #             'success': False,
    #             'error': error,
    #             'return_value': return_value
    #         }
    #     
    #     # Check return value - 1 or -1 indicates measurement completed
    #     # 1 = success, -1 = error/completion with issue
    #     # None = couldn't read, but measurement may have succeeded
    #     if return_value is not None:
    #         if return_value == 1:
    #             print(f"✓ Return value: {return_value} (measurement completed successfully)")
    #         elif return_value == -1:
    #             print(f"⚠️ Return value: {return_value} (measurement completed with error/warning)")
    #         elif return_value not in [1, -1]:
    #             print(f"⚠️ Warning: Return value is {return_value} (expected 1 or -1)")
    #     else:
    #         print(f"⚠️ Could not read return value, but continuing (measurement may have succeeded)")
    #     
    #     # Retrieve results using GP commands (as per LabVIEW workflow)
    #     print(f"\n📊 Retrieving results...")
    #     time.sleep(0.03)  # Wait 30ms between commands
    #     
    #     results = {
    #         'return_value': return_value,
    #         'measurement_complete': return_value in [1, -1] if return_value is not None else None,
    #         'measurement_success': return_value == 1 if return_value is not None else None,
    #         'param18': None,
    #         'setV': [],
    #         'setI': [],
    #         'out1': [],
    #         'setR': [],
    #         'resetR': [],
    #         'PulseTimes': []
    #     }
    #     
    #     # GP 18 1 - First parameter query (from LabVIEW output)
    #     print("Querying GP 18 1...")
    #     param18_values = self._query_gp(18, 1)
    #     if param18_values:
    #         results['param18'] = param18_values[0] if len(param18_values) > 0 else None
    #     time.sleep(0.03)  # Wait 30ms between commands
    #     
    #     # GP 20 7 - SET V values (from LabVIEW: "GP 20 7" returns SET V VALUES)
    #     print("Querying GP 20 7 (SET V values)...")
    #     results['setV'] = self._query_gp(20, 7)
    #     print(f"  Retrieved {len(results['setV'])} SET V values")
    #     time.sleep(0.03)  # Wait 30ms between commands
    #     
    #     # GP 22 7 - SET I values (from LabVIEW: "GP 22 7" returns I VALUES)
    #     print("Querying GP 22 7 (SET I values)...")
    #     results['setI'] = self._query_gp(22, 7)
    #     print(f"  Retrieved {len(results['setI'])} SET I values")
    #     time.sleep(0.03)  # Wait 30ms between commands
    #     
    #     # GP 31 7 - OUT1 values (from LabVIEW: "GP 31 7" returns unknown values)
    #     print("Querying GP 31 7 (OUT1 values)...")
    #     results['out1'] = self._query_gp(31, 7)
    #     print(f"  Retrieved {len(results['out1'])} OUT1 values")
    #     
    #     # Optional: Query other parameters if needed
    #     # GP for setR, resetR, etc. would need correct parameter positions
    #     
    #     # Determine success based on whether we got data back
    #     # If we got data, measurement likely succeeded even if return_value wasn't read
    #     has_data = (len(results['setV']) > 0 or len(results['setI']) > 0 or 
    #                len(results['out1']) > 0 or results['param18'] is not None)
    #     
    #     if return_value in [1, -1]:
    #         results['success'] = True
    #     elif return_value is None and has_data:
    #         # Couldn't read return value but got data - assume success
    #         results['success'] = True
    #         print(f"✓ Measurement appears successful (data retrieved, return value not read)")
    #     elif return_value is None and not has_data:
    #         # No return value and no data - might have failed
    #         results['success'] = False
    #         results['error'] = 'No return value received and no data retrieved'
    #     else:
    #         # Unexpected return value
    #         results['success'] = has_data  # Success if we got data
    #     
    #     if results['success']:
    #         print(f"\n✓ PMU_PulseTrain completed successfully")
    #     else:
    #         print(f"\n⚠️ PMU_PulseTrain may have failed (check return_value and data)")
    #     print(f"{'='*60}\n")
    #     
    #     # Exit UL mode after measurement to reset state for next run
    #     # This prevents issues with running multiple measurements in sequence
    #     print(f"[KXCI] Exiting UL mode to reset state...")
    #     self._exit_ul_mode()
    #     
    #     return results
    
    def pmu_retention(
        self,
        riseTime: float = 1e-7,
        resetV: float = 1.0,
        resetWidth: float = 1e-6,
        resetDelay: float = 5e-7,
        measV: float = 0.3,
        measWidth: float = 1e-6,
        measDelay: float = 2e-6,
        setWidth: float = 1e-6,
        setFallTime: float = 1e-7,
        setDelay: float = 1e-6,
        setStartV: float = 0.3,
        setStopV: float = 0.3,
        steps: int = 0,
        IRange: float = 1e-4,
        max_points: int = 10000,
        setR_size: int = 12,
        resetR_size: int = 12,
        setV_size: int = 12,
        setI_size: int = 12,
        iteration: int = 1,
        out1_size: int = 12,
        out1_name: str = "VF",
        out2_size: int = 200,
        out2_name: str = "T",
        PulseTimesSize: int = 12,
        ClariusDebug: int = 0
    ) -> Dict[str, Any]:
        """
        Execute PMU_retention measurement.
        
        This method replicates the LabVIEW PMU_retention() call.
        The retention measurement performs multiple probe measurements over time
        to track resistance changes after a SET/RESET pulse.
        
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
            steps: Number of points in sweep (typically 0 for retention)
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
            PulseTimesSize: Size of PulseTimes output array
            ClariusDebug: Debug flag (0 or 1)
            
        Returns:
            Dictionary with measurement results:
            - 'return_value': Function return code
            - 'setR': SET resistance array
            - 'resetR': RESET resistance array
            - 'setV': SET voltage array (contains probe voltages)
            - 'setI': SET current array (contains probe currents)
            - 'out1': Debug output array 1
            - 'out2': Debug output array 2
            - 'PulseTimes': Pulse times array
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
        # Library is "Labview_Controlled_PLabview_Controlled_Programs_Kemp Kemp3)
        
        num_pulses = 20  # number of user-requested measurement probes after the initial baseline read
        total_probe_count = num_pulses + 2  # baseline probe + requested probes + trailing probe

        ex_command = (
            "EX ACraig2 ACraig1_PMU_retention(1.00E-7,1.00E+0,1.00E-6,5.00E-7,3.00E-1,1.00E-6,2.00E-6,"
            "1.00E-6,1.00E-7,1.00E-6,3.00E-1,3.00E-1,0,1.00E-4,10000,,{0},,{0},,{0},,{0},1,,{0},VF,,200,T,,{0},{1},1)"
        ).format(total_probe_count, num_pulses)
        z = total_probe_count
        print(f"\n[KXCI] Sending exact command:")
        print(f"[KXCI] {ex_command}")
        
        print(f"\n{'='*60}")
        print("Executing PMU_retention")
        print(f"{'='*60}")
        
        # Execute EX command
        return_value, error = self._execute_ex_command(ex_command)
        
        # Only fail immediately if there's a real error (not just missing return value)
        # If error is None, the measurement likely succeeded even if we couldn't read return value
        if error and "failed" in error.lower():
            return {
                'success': False,
            
                'error': error,
                'return_value': return_value
            }
        
        # Check return value - 1 or -1 indicates measurement completed
        # 1 = success, -1 = error/completion with issue
        # None = couldn't read, but measurement may have succeeded
        if return_value is not None:
            if return_value == 1:
                print(f"✓ Return value: {return_value} (measurement completed successfully)")
            elif return_value == -1:
                print(f"⚠️ Return value: {return_value} (measurement completed with error/warning)")
            elif return_value not in [1, -1]:
                print(f"⚠️ Warning: Return value is {return_value} (expected 1 or -1)")
        else:
            print(f"⚠️ Could not read return value, but continuing (measurement may have succeeded)")
        
        # Retrieve results using GP commands (as per LabVIEW workflow)
        print(f"\n📊 Retrieving results...")
        time.sleep(0.03)  # Wait 30ms between commands
        
        results = {
            'return_value': return_value,
            'measurement_complete': return_value in [1, -1] if return_value is not None else None,
            'measurement_success': return_value == 1 if return_value is not None else None,
            'setR': [],
            'resetR': [],
            'setV': [],
            'setI': [],
            'PulseTimes': [],
            'out1': [],
            'out2': []
        }
        
        # Query results - based on PMU_retention, we need to get:
        # setR, resetR, setV, setI, PulseTimes, out1, out2
        # The parameter positions may differ from PMU_PulseTrain
        
        # Try to query similar parameters as PMU_PulseTrain
        # GP 18 1 - First parameter query
        print("Querying GP 18 1...")
        param18_values = self._query_gp(18, 0)
        if param18_values:
            results['param18'] = param18_values[0] if len(param18_values) > 0 else None
        time.sleep(0.03)  # Wait 30ms between commands
        
        # GP 20 12 - SET V values (probe voltages)
        print("Querying GP 20 12 (SET V values / probe voltages)...")
        results['setV'] = self._query_gp(20, z)
        print(f"  Retrieved {len(results['setV'])} SET V values")
        time.sleep(0.03)  # Wait 30ms between commands
        
        # GP 22 12 - SET I values (probe currents)
        print("Querying GP 22 12 (SET I values / probe currents)...")
        results['setI'] = self._query_gp(22, z)
        print(f"  Retrieved {len(results['setI'])} SET I values")
        time.sleep(0.03)  # Wait 30ms between commands
        
        # GP 30 12 - PulseTimes array
        print("Querying GP 30 12 (PulseTimes)...")
        results['PulseTimes'] = self._query_gp(30, z)
        print(f"  Retrieved {len(results['PulseTimes'])} PulseTimes values")
        time.sleep(0.03)  # Wait 30ms between commands
        
        # GP 31 12 - OUT1 values
        print("Querying GP 31 12 (OUT1 values)...")
        results['out1'] = self._query_gp(31, z)
        print(f"  Retrieved {len(results['out1'])} OUT1 values")
        time.sleep(0.03)  # Wait 30ms between commands
        
        # Determine success based on whether we got data back
        # If we got data, measurement likely succeeded even if return_value wasn't read
        has_data = (len(results['setV']) > 0 or len(results['setI']) > 0 or 
                   len(results['out1']) > 0 or len(results['PulseTimes']) > 0 or
                   results.get('param18') is not None)
        
        if return_value in [1, -1]:
            results['success'] = True
        elif return_value is None and has_data:
            # Couldn't read return value but got data - assume success
            results['success'] = True
            print(f"✓ Measurement appears successful (data retrieved, return value not read)")
        elif return_value is None and not has_data:
            # No return value and no data - might have failed
            results['success'] = False
            results['error'] = 'No return value received and no data retrieved'
        else:
            # Unexpected return value
            results['success'] = has_data  # Success if we got data
        
        if results['success']:
            print(f"\n✓ PMU_retention completed successfully")
        else:
            print(f"\n⚠️ PMU_retention may have failed (check return_value and data)")
        print(f"{'='*60}\n")
        
        # Exit UL mode after measurement to reset state for next run
        # This prevents issues with running multiple measurements in sequence
        print(f"[KXCI] Exiting UL mode to reset state...")
        self._exit_ul_mode()
        
        return results
    
    def pmu_retention_test(
        self,
        riseTime: float = 1e-7,
        writeVoltage: float = 2.5,
        writeWidth: float = 100e-6,
        readVoltage: float = 0.5,
        readWidth: float = 10e-6,
        readInterval: float = 1.0,
        numReads: int = 30,
        readCount: int = 3,
        initialDelay: float = 1e-6,
        IRange: float = 1e-4,
        max_points: int = 10000,
        resistance_size: int = 200,
        time_size: int = 200,
        iteration: int = 1,
        out1_size: int = 200,
        out1_name: str = "VF",
        out2_size: int = 200,
        out2_name: str = "T",
        ClariusDebug: int = 0
    ) -> Dict[str, Any]:
        """
        Execute PMU_RetentionTest measurement.
        
        This performs a full retention test with multiple read measurements over time
        in a single waveform execution.
        
        Args:
            riseTime: Rise/fall time for pulses (s)
            writeVoltage: Voltage for write pulse to set state (V)
            writeWidth: Width of write pulse (s)
            readVoltage: Voltage for read pulses (V)
            readWidth: Width of read pulses (s)
            readInterval: Time between consecutive read measurements (s)
            numReads: Total number of read measurements
            readCount: Number of read pulses per measurement (for averaging)
            initialDelay: Initial settling time before write pulse (s)
            IRange: Current range for measurements (A)
            max_points: Maximum number of measurement points
            resistance_size: Size of resistance output array
            time_size: Size of time output array
            iteration: Iteration number for debug wave profiles
            out1_size: Size of out1 debug array
            out1_name: Name of out1 debug parameter (e.g., "VF")
            out2_size: Size of out2 debug array
            out2_name: Name of out2 debug parameter (e.g., "T")
            ClariusDebug: Debug flag (0 or 1)
            
        Returns:
            Dictionary with measurement results:
            - 'return_value': Function return code
            - 'resistance': Resistance array (Ohm)
            - 'time_s': Time array (seconds from start)
            - 'out1': Debug output array 1
            - 'out2': Debug output array 2
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
        if self._ul_mode_active:
            print("[KXCI] Still in UL mode from previous run, exiting first...")
            self._exit_ul_mode()
            time.sleep(0.03)
        
        # Enter UL mode fresh
        if not self._enter_ul_mode():
            return {
                'success': False,
                'error': 'Failed to enter UL mode'
            }
        
        # Build EX command with all parameters
        # Library: "Python_Controlled_PMU_Craig"
        # Function: "PMU_RetentionTest"
        params = [
            riseTime,
            writeVoltage,
            writeWidth,
            readVoltage,
            readWidth,
            readInterval,
            numReads,
            readCount,
            initialDelay,
            IRange,
            max_points,
            "",  # resistance (output array - empty)
            resistance_size,
            "",  # time_s (output array - empty)
            time_size,
            iteration,
            "",  # out1 (output array - empty)
            out1_size,
            out1_name,
            "",  # out2 (output array - empty)
            out2_size,
            out2_name,
            ClariusDebug
        ]
        
        ex_command = self._build_ex_command("Python_Controlled_PMU_Craig", "PMU_RetentionTest", params)
        
        print(f"\n[KXCI] Sending command:")
        print(f"[KXCI] {ex_command}")
        
        print(f"\n{'='*60}")
        print("Executing PMU_RetentionTest")
        print(f"{'='*60}")
        
        # Execute EX command
        return_value, error = self._execute_ex_command(ex_command)
        
        if error and "failed" in error.lower():
            return {
                'success': False,
                'error': error,
                'return_value': return_value
            }
        
        # Check return value
        if return_value is not None:
            if return_value == 1:
                print(f"✓ Return value: {return_value} (measurement completed successfully)")
            elif return_value == -1:
                print(f"⚠️ Return value: {return_value} (measurement completed with error/warning)")
        else:
            print(f"⚠️ Could not read return value, but continuing")
        
        # Retrieve results using GP commands
        print(f"\n📊 Retrieving results...")
        time.sleep(0.03)
        
        results = {
            'return_value': return_value,
            'resistance': [],
            'time_s': [],
            'out1': [],
            'out2': []
        }
        
        # Query output arrays
        # Parameter positions based on PMU_RetentionTest function signature (1-based):
        # 1. riseTime, 2. writeVoltage, 3. writeWidth, 4. readVoltage, 5. readWidth,
        # 6. readInterval, 7. numReads, 8. readCount, 9. initialDelay, 10. IRange,
        # 11. max_points, 12. resistance (OUTPUT), 13. resistance_size,
        # 14. time_s (OUTPUT), 15. time_size, 16. iteration,
        # 17. out1 (OUTPUT), 18. out1_size, 19. out1_name,
        # 20. out2 (OUTPUT), 21. out2_size, 22. out2_name, 23. ClariusDebug
        # Note: GP positions may differ - these are based on function signature order
        
        print("Querying GP 12 (resistance array)...")
        results['resistance'] = self._query_gp(12, resistance_size)
        print(f"  Retrieved {len(results['resistance'])} resistance values")
        time.sleep(0.03)
        
        print("Querying GP 14 (time_s array)...")
        results['time_s'] = self._query_gp(14, time_size)
        print(f"  Retrieved {len(results['time_s'])} time values")
        time.sleep(0.03)
        
        print("Querying GP 17 (out1 array)...")
        results['out1'] = self._query_gp(17, out1_size)
        print(f"  Retrieved {len(results['out1'])} out1 values")
        time.sleep(0.03)
        
        print("Querying GP 20 (out2 array)...")
        results['out2'] = self._query_gp(20, out2_size)
        print(f"  Retrieved {len(results['out2'])} out2 values")
        time.sleep(0.03)
        
        # Determine success
        has_data = (len(results['resistance']) > 0 or len(results['time_s']) > 0 or
                   len(results['out1']) > 0 or len(results['out2']) > 0)
        
        if return_value in [1, -1]:
            results['success'] = True
        elif return_value is None and has_data:
            results['success'] = True
            print(f"✓ Measurement appears successful (data retrieved)")
        elif return_value is None and not has_data:
            results['success'] = False
            results['error'] = 'No return value received and no data retrieved'
        else:
            results['success'] = has_data
        
        if results['success']:
            print(f"\n✓ PMU_RetentionTest completed successfully")
        else:
            print(f"\n⚠️ PMU_RetentionTest may have failed")
        print(f"{'='*60}\n")
        
        # Exit UL mode
        print(f"[KXCI] Exiting UL mode to reset state...")
        self._exit_ul_mode()
        
        return results
    
    def pmu_retention_simple(
        self,
        riseTime: float = 1e-7,
        writeVoltage: float = 2.5,
        writeWidth: float = 100e-6,
        readVoltage: float = 0.5,
        readWidth: float = 10e-6,
        readCount: int = 3,
        v_range: float = 10.0,
        IRange: float = 1e-4,
        doWrite: int = 1,
        ClariusDebug: int = 0
    ) -> Dict[str, Any]:
        """
        Execute PMU_RetentionSimple measurement.
        
        This performs a single retention measurement (one write + one or more reads).
        Designed to be called repeatedly from Python with delays between calls.
        
        Args:
            riseTime: Rise/fall time for pulses (s)
            writeVoltage: Voltage for write pulse to set state (V)
            writeWidth: Width of write pulse (s)
            readVoltage: Voltage for read pulses (V)
            readWidth: Width of read pulses (s)
            readCount: Number of read pulses to average
            v_range: Voltage range for measurements (V)
            IRange: Current range for measurements (A)
            doWrite: If 1, apply write pulse first. If 0, only read
            ClariusDebug: Debug flag (0 or 1)
            
        Returns:
            Dictionary with measurement results:
            - 'return_value': Function return code
            - 'resistance': Average resistance (Ohm)
            - 'current': Average current (A)
            - 'voltage': Average voltage (V)
            - 'success': Whether execution succeeded
        """
        # Ensure connection
        if not self.inst:
            if not self.connect():
                return {
                    'success': False,
                    'error': 'Failed to connect'
                }
        
        # Reset state: Exit UL mode if we're still in it
        if self._ul_mode_active:
            print("[KXCI] Still in UL mode from previous run, exiting first...")
            self._exit_ul_mode()
            time.sleep(0.03)
        
        # Enter UL mode fresh
        if not self._enter_ul_mode():
            return {
                'success': False,
                'error': 'Failed to enter UL mode'
            }
        
        # Build EX command
        # Library: "Python_Controlled_PMU_Craig"
        # Function: "PMU_RetentionSimple"
        params = [
            riseTime,
            writeVoltage,
            writeWidth,
            readVoltage,
            readWidth,
            readCount,
            v_range,
            IRange,
            "",  # resistance (output - single value, will query via GP)
            "",  # current (output - single value)
            "",  # voltage (output - single value)
            doWrite,
            ClariusDebug
        ]
        
        ex_command = self._build_ex_command("Python_Controlled_PMU_Craig", "PMU_RetentionSimple", params)
        
        print(f"\n[KXCI] Sending command:")
        print(f"[KXCI] {ex_command}")
        
        print(f"\n{'='*60}")
        print("Executing PMU_RetentionSimple")
        print(f"{'='*60}")
        
        # Execute EX command
        return_value, error = self._execute_ex_command(ex_command)
        
        if error and "failed" in error.lower():
            return {
                'success': False,
                'error': error,
                'return_value': return_value
            }
        
        # Check return value
        if return_value is not None:
            if return_value == 1:
                print(f"✓ Return value: {return_value} (measurement completed successfully)")
            elif return_value == -1:
                print(f"⚠️ Return value: {return_value} (measurement completed with error/warning)")
        else:
            print(f"⚠️ Could not read return value, but continuing")
        
        # Retrieve results using GP commands
        print(f"\n📊 Retrieving results...")
        time.sleep(0.03)
        
        results = {
            'return_value': return_value,
            'resistance': None,
            'current': None,
            'voltage': None
        }
        
        # Query output values (single values, not arrays)
        # Parameter positions based on PMU_RetentionSimple parameter list:
        # 9: resistance (double *, Output)
        # 10: current (double *, Output)
        # 11: voltage (double *, Output)
        
        print("Querying GP 9 (resistance)...")
        resistance_vals = self._query_gp(9, 1)
        if resistance_vals:
            results['resistance'] = resistance_vals[0]
        time.sleep(0.03)
        
        print("Querying GP 10 (current)...")
        current_vals = self._query_gp(10, 1)
        if current_vals:
            results['current'] = current_vals[0]
        time.sleep(0.03)
        
        print("Querying GP 11 (voltage)...")
        voltage_vals = self._query_gp(11, 1)
        if voltage_vals:
            results['voltage'] = voltage_vals[0]
        time.sleep(0.03)
        
        # Determine success
        has_data = (results['resistance'] is not None or 
                   results['current'] is not None or 
                   results['voltage'] is not None)
        
        if return_value in [1, -1]:
            results['success'] = True
        elif return_value is None and has_data:
            results['success'] = True
            print(f"✓ Measurement appears successful (data retrieved)")
        elif return_value is None and not has_data:
            results['success'] = False
            results['error'] = 'No return value received and no data retrieved'
        else:
            results['success'] = has_data
        
        if results['success']:
            print(f"\n✓ PMU_RetentionSimple completed successfully")
        else:
            print(f"\n⚠️ PMU_RetentionSimple may have failed")
        print(f"{'='*60}\n")
        
        # Exit UL mode
        print(f"[KXCI] Exiting UL mode to reset state...")
        self._exit_ul_mode()
        
        return results
    
    def long_term_retention_test(
        self,
        riseTime: float = 1e-7,
        writeVoltage: float = 2.5,
        writeWidth: float = 100e-6,
        readVoltage: float = 0.5,
        readWidth: float = 10e-6,
        readCount: int = 3,
        v_range: float = 10.0,
        IRange: float = 1e-4,
        time_limit_minutes: float = 60.0,
        measurement_interval_seconds: float = 60.0,
        initial_write: bool = True,
        ClariusDebug: int = 0
    ) -> Dict[str, Any]:
        """
        Execute long-term retention test (time-based, similar to chris_man_retention).
        
        This repeatedly calls pmu_retention_simple over time until time_limit_minutes is reached.
        Designed for extended retention testing (hours/days).
        
        Args:
            riseTime: Rise/fall time for pulses (s)
            writeVoltage: Voltage for write pulse to set state (V)
            writeWidth: Width of write pulse (s)
            readVoltage: Voltage for read pulses (V)
            readWidth: Width of read pulses (s)
            readCount: Number of read pulses to average per measurement
            v_range: Voltage range for measurements (V)
            IRange: Current range for measurements (A)
            time_limit_minutes: Total test duration in minutes
            measurement_interval_seconds: Time between measurements (seconds)
            initial_write: If True, do a write pulse at the start. If False, only read
            ClariusDebug: Debug flag (0 or 1)
            
        Returns:
            Dictionary with measurement results:
            - 'return_value': Final function return code
            - 'resistance_history': List of resistance values over time
            - 'current_history': List of current values over time
            - 'voltage_history': List of voltage values over time
            - 'time_history': List of elapsed times (seconds from start)
            - 'measurement_count': Number of measurements taken
            - 'success': Whether execution succeeded
        """
        import time as time_module
        from datetime import datetime
        
        # Ensure connection
        if not self.inst:
            if not self.connect():
                return {
                    'success': False,
                    'error': 'Failed to connect'
                }
        
        print(f"\n{'='*60}")
        print("Starting Long-Term Retention Test")
        print(f"{'='*60}")
        print(f"Duration: {time_limit_minutes} minutes")
        print(f"Measurement interval: {measurement_interval_seconds} seconds")
        print(f"Estimated measurements: {int(time_limit_minutes * 60 / measurement_interval_seconds)}")
        print(f"{'='*60}\n")
        
        # Initialize results
        results = {
            'return_value': None,
            'resistance_history': [],
            'current_history': [],
            'voltage_history': [],
            'time_history': [],
            'measurement_count': 0,
            'success': False
        }
        
        start_time = time_module.time()
        end_time = start_time + (time_limit_minutes * 60)
        next_measurement_time = start_time
        
        # Initial write if requested
        if initial_write:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Performing initial write pulse...")
            write_result = self.pmu_retention_simple(
                riseTime=riseTime,
                writeVoltage=writeVoltage,
                writeWidth=writeWidth,
                readVoltage=readVoltage,
                readWidth=readWidth,
                readCount=readCount,
                v_range=v_range,
                IRange=IRange,
                doWrite=1,
                ClariusDebug=ClariusDebug
            )
            if not write_result.get('success'):
                print(f"⚠️ Initial write may have failed, but continuing...")
            time_module.sleep(1.0)  # Brief pause after write
        
        # Main measurement loop
        measurement_num = 0
        try:
            while time_module.time() < end_time:
                current_time = time_module.time()
                elapsed_time = current_time - start_time
                
                # Wait until it's time for the next measurement
                if current_time < next_measurement_time:
                    sleep_time = next_measurement_time - current_time
                    if sleep_time > 0:
                        time_module.sleep(min(sleep_time, 1.0))  # Sleep in small chunks to allow interruption
                    continue
                
                measurement_num += 1
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Measurement #{measurement_num} (Elapsed: {elapsed_time/60:.1f} min)")
                
                # Perform measurement (read-only after initial write)
                measure_result = self.pmu_retention_simple(
                    riseTime=riseTime,
                    writeVoltage=writeVoltage,
                    writeWidth=writeWidth,
                    readVoltage=readVoltage,
                    readWidth=readWidth,
                    readCount=readCount,
                    v_range=v_range,
                    IRange=IRange,
                    doWrite=0,  # Read-only after initial write
                    ClariusDebug=ClariusDebug
                )
                
                if measure_result.get('success'):
                    results['resistance_history'].append(measure_result.get('resistance'))
                    results['current_history'].append(measure_result.get('current'))
                    results['voltage_history'].append(measure_result.get('voltage'))
                    results['time_history'].append(elapsed_time)
                    results['measurement_count'] = measurement_num
                    
                    print(f"  Resistance: {measure_result.get('resistance', 'N/A'):.6e} Ω")
                    print(f"  Current: {measure_result.get('current', 'N/A'):.6e} A")
                    print(f"  Voltage: {measure_result.get('voltage', 'N/A'):.6f} V")
                else:
                    print(f"  ⚠️ Measurement failed: {measure_result.get('error', 'Unknown error')}")
                    # Still record the time, but with None values
                    results['resistance_history'].append(None)
                    results['current_history'].append(None)
                    results['voltage_history'].append(None)
                    results['time_history'].append(elapsed_time)
                    results['measurement_count'] = measurement_num
                
                # Schedule next measurement
                next_measurement_time = current_time + measurement_interval_seconds
                
                # Check if we have time for another measurement
                if next_measurement_time >= end_time:
                    break
        
        except KeyboardInterrupt:
            print(f"\n\n⚠️ Test interrupted by user after {measurement_num} measurements")
            results['return_value'] = -1
            results['success'] = True  # Partial success
        except Exception as e:
            print(f"\n\n❌ Error during test: {e}")
            results['error'] = str(e)
            results['return_value'] = -1
            results['success'] = False
        else:
            # Normal completion
            total_time = time_module.time() - start_time
            print(f"\n{'='*60}")
            print(f"Test completed successfully")
            print(f"Total time: {total_time/60:.1f} minutes")
            print(f"Total measurements: {measurement_num}")
            print(f"{'='*60}\n")
            results['return_value'] = 1
            results['success'] = True
        
        return results
    
    def nvm_reram_sweep(
        self,
        riseTime: float = 1e-4,
        widthTime: float = 1e-6,
        delayTime: float = 1e-4,
        complianceCH: int = 2,
        resetV: float = -2.5,
        setV: float = 2.5,
        Irange: float = 1e-2,
        resetIcomp: float = 0.0,
        setIcomp: float = 1e-3,
        resTestV: float = 0.5,
        takeRmeas: int = 1,
        useSmu: int = 0,
        numIter: float = 1.0,
        Vforce_size: int = 1000,
        Imeas_size: int = 1000,
        Time_size: int = 1000
    ) -> Dict[str, Any]:
        """
        Execute NVM library reramSweep function - double sweep (reset + set pulse) for IV characterization.
        
        This function performs a double sweep with a flat section at the peak of each sweep.
        Returns full waveforms for voltage, current, and time.
        
        Args:
            riseTime: Time for voltage to ramp to final value (s). Must be > 5% of widthTime.
            widthTime: Time to wait at peak voltage (s)
            delayTime: Delay before/after each pulse (s). Time between reset and set = 2*delayTime.
            complianceCH: PMU channel for compliance (1 or 2)
            resetV: Reset pulse voltage (V). Negative for ReRAM.
            setV: Set pulse voltage (V). Positive for ReRAM.
            Irange: Current measurement range (A)
            resetIcomp: Current compliance during reset pulse (A). 0 = max of Irange.
            setIcomp: Current compliance during set pulse (A). 0 = max of Irange.
            resTestV: Voltage for resistance measurement (V). Should be << set/reset voltages.
            takeRmeas: 1 = measure resistance, 0 = don't measure
            useSmu: 1 = use SMU, 0 = use PMU
            numIter: Number of iterations (pulse cycles)
            Vforce_size: Size of output voltage array
            Imeas_size: Size of output current array
            Time_size: Size of output time array
            
        Returns:
            Dictionary with:
            - 'return_value': Function return code (1 = success, negative = error)
            - 'Vforce': Array of forced voltages
            - 'Imeas': Array of measured currents
            - 'Time': Array of measurement times
            - 'pts': Number of points returned
            - 'resetResistance': Resistance after reset pulse
            - 'setResistance': Resistance after set pulse
            - 'initResistance': Initial resistance before pulses
            - 'success': Whether execution succeeded
        """
        # Ensure connection
        if not self.inst:
            if not self.connect():
                return {
                    'success': False,
                    'error': 'Failed to connect'
                }
        
        # Reset state
        if self._ul_mode_active:
            print("[KXCI] Still in UL mode from previous run, exiting first...")
            self._exit_ul_mode()
            time.sleep(0.03)
        
        # Enter UL mode
        if not self._enter_ul_mode():
            return {
                'success': False,
                'error': 'Failed to enter UL mode'
            }
        
        # Build EX command
        # Parameters: riseTime, widthTime, delayTime, complianceCH, resetV, setV, Irange,
        #            resetIcomp, setIcomp, resTestV, takeRmeas, useSmu, numIter,
        #            Vforce (output), Vforce_size, Imeas (output), Imeas_size,
        #            Time (output), Time_size, pts (output), resetResistance (output),
        #            setResistance (output), initResistance (output)
        params = [
            riseTime, widthTime, delayTime, complianceCH,
            resetV, setV, Irange, resetIcomp, setIcomp, resTestV,
            takeRmeas, useSmu, numIter,
            "",  # Vforce (output array - empty)
            Vforce_size,
            "",  # Imeas (output array - empty)
            Imeas_size,
            "",  # Time (output array - empty)
            Time_size,
            "",  # pts (output scalar - empty)
            "",  # resetResistance (output scalar - empty)
            "",  # setResistance (output scalar - empty)
            ""   # initResistance (output scalar - empty)
        ]
        
        # Debug: Verify parameter count
        print(f"\n[DEBUG] Parameter count: {len(params)} (should be 23)")
        print(f"[DEBUG] Parameters: {[type(p).__name__ for p in params]}")
        
        ex_command = self._build_ex_command("nvm", "reramSweep", params)
        
        # Count actual parameters in command (by commas + 1)
        param_count_in_command = ex_command.count(',') + 1
        print(f"\n[DEBUG] Command has {param_count_in_command} parameters (by comma count)")
        
        print(f"\n[KXCI] Sending command:")
        print(f"[KXCI] {ex_command}")
        
        print(f"\n{'='*60}")
        print("Executing NVM reramSweep (IV Characterization)")
        print(f"{'='*60}")
        
        # Execute EX command
        return_value, error = self._execute_ex_command(ex_command)
        
        if error and "failed" in error.lower():
            self._exit_ul_mode()
            return {
                'success': False,
                'error': error,
                'return_value': return_value
            }
        
        # Check return value
        if return_value is not None:
            if return_value == 1:
                print(f"✓ Return value: {return_value} (measurement completed successfully)")
            elif return_value < 0:
                print(f"⚠️ Return value: {return_value} (error code)")
            else:
                print(f"⚠️ Return value: {return_value} (unexpected)")
        else:
            print(f"⚠️ Could not read return value, but continuing")
        
        # Retrieve results using GP commands
        print(f"\n📊 Retrieving results...")
        time.sleep(0.03)
        
        results = {
            'return_value': return_value,
            'Vforce': [],
            'Imeas': [],
            'Time': [],
            'pts': None,
            'resetResistance': None,
            'setResistance': None,
            'initResistance': None
        }
        
        # Query output arrays
        # Parameter positions: 14=Vforce, 16=Imeas, 18=Time, 20=pts, 21=resetResistance, 22=setResistance, 23=initResistance
        print("Querying GP 14 (Vforce array)...")
        results['Vforce'] = self._query_gp(14, Vforce_size) or []
        time.sleep(0.03)
        
        print("Querying GP 16 (Imeas array)...")
        results['Imeas'] = self._query_gp(16, Imeas_size) or []
        time.sleep(0.03)
        
        print("Querying GP 18 (Time array)...")
        results['Time'] = self._query_gp(18, Time_size) or []
        time.sleep(0.03)
        
        print("Querying GP 20 (pts)...")
        pts_vals = self._query_gp(20, 1)
        if pts_vals:
            results['pts'] = int(pts_vals[0])
        time.sleep(0.03)
        
        print("Querying GP 21 (resetResistance)...")
        resetR_vals = self._query_gp(21, 1)
        if resetR_vals:
            results['resetResistance'] = resetR_vals[0]
        time.sleep(0.03)
        
        print("Querying GP 22 (setResistance)...")
        setR_vals = self._query_gp(22, 1)
        if setR_vals:
            results['setResistance'] = setR_vals[0]
        time.sleep(0.03)
        
        print("Querying GP 23 (initResistance)...")
        initR_vals = self._query_gp(23, 1)
        if initR_vals:
            results['initResistance'] = initR_vals[0]
        time.sleep(0.03)
        
        # Determine success
        has_data = (len(results['Vforce']) > 0 or len(results['Imeas']) > 0 or 
                   results['pts'] is not None)
        
        if return_value == 1:
            results['success'] = True
        elif return_value is None and has_data:
            results['success'] = True
            print(f"✓ Measurement appears successful (data retrieved)")
        else:
            results['success'] = has_data
        
        if results['success']:
            print(f"\n✓ reramSweep completed successfully")
            print(f"  Points: {results['pts']}")
            print(f"  Vforce points: {len(results['Vforce'])}")
            print(f"  Imeas points: {len(results['Imeas'])}")
            print(f"  Reset Resistance: {results['resetResistance']}")
            print(f"  Set Resistance: {results['setResistance']}")
            print(f"  Initial Resistance: {results['initResistance']}")
        else:
            print(f"\n⚠️ reramSweep may have failed")
        print(f"{'='*60}\n")
        
        # Exit UL mode
        print(f"[KXCI] Exiting UL mode...")
        self._exit_ul_mode()
        
        return results
    
    def nvm_pund_test(
        self,
        Vp: float = 3.3,
        tp: float = 1e-6,
        td: float = 1e-6,
        trf: float = 1e-6,
        Irange1: float = 1e-2,
        Irange2: float = 1e-2,
        V_size: int = 10000,
        I_size: int = 10000,
        t_size: int = 10000
    ) -> Dict[str, Any]:
        """
        Execute NVM library pundTest function - PUND test for FRAM (4-pulse sequence).
        
        Performs a 17-segment voltage pulse waveform: two positive pulses (P, Pa) from 0V to +Vp,
        followed by two negative pulses (N, Na, D, Da) to -Vp. Calculates polarization,
        switching charge, etc.
        
        Args:
            Vp: Voltage pulse level for all 4 pulses (V). First two are +Vp, last two are -Vp.
            tp: Pulse width of each voltage pulse (s)
            td: Delay time between pulses (s)
            trf: Rise and fall time of each pulse (s)
            Irange1: Current range for RPM1/sourcing (A)
            Irange2: Current range for RPM2/measuring (A)
            V_size: Size of output voltage array
            I_size: Size of output current array
            t_size: Size of output time array
            
        Returns:
            Dictionary with:
            - 'return_value': Function return code
            - 'V': Voltage waveform array
            - 'I': Current waveform array
            - 't': Time array
            - 'pts': Number of points
            - 'P', 'Pa', 'U', 'Ua', 'N', 'Na', 'D', 'Da': Polarization values
            - 'Psw', 'Qsw': Switching polarization and charge
            - 'success': Whether execution succeeded
        """
        # Ensure connection
        if not self.inst:
            if not self.connect():
                return {
                    'success': False,
                    'error': 'Failed to connect'
                }
        
        # Reset state
        if self._ul_mode_active:
            print("[KXCI] Still in UL mode from previous run, exiting first...")
            self._exit_ul_mode()
            time.sleep(0.03)
        
        # Enter UL mode
        if not self._enter_ul_mode():
            return {
                'success': False,
                'error': 'Failed to enter UL mode'
            }
        
        # Build EX command
        # Parameters: Vp, tp, td, trf, Irange1, Irange2,
        #            V (output), V_size, I (output), I_size, t (output), t_size,
        #            P (output), Pa (output), U (output), Ua (output),
        #            N (output), Na (output), D (output), Da (output),
        #            Psw (output), Qsw (output), pts (output)
        params = [
            Vp, tp, td, trf, Irange1, Irange2,
            "",  # V (output array - empty)
            V_size,
            "",  # I (output array - empty)
            I_size,
            "",  # t (output array - empty)
            t_size,
            "",  # P (output scalar - empty)
            "",  # Pa (output scalar - empty)
            "",  # U (output scalar - empty)
            "",  # Ua (output scalar - empty)
            "",  # N (output scalar - empty)
            "",  # Na (output scalar - empty)
            "",  # D (output scalar - empty)
            "",  # Da (output scalar - empty)
            "",  # Psw (output scalar - empty)
            "",  # Qsw (output scalar - empty)
            ""   # pts (output scalar - empty)
        ]
        
        ex_command = self._build_ex_command("nvm", "pundTest", params)
        
        print(f"\n[KXCI] Sending command:")
        print(f"[KXCI] {ex_command}")
        
        print(f"\n{'='*60}")
        print("Executing NVM pundTest (PUND 4-Pulse Sequence)")
        print(f"{'='*60}")
        
        # Execute EX command
        return_value, error = self._execute_ex_command(ex_command)
        
        if error and "failed" in error.lower():
            self._exit_ul_mode()
            return {
                'success': False,
                'error': error,
                'return_value': return_value
            }
        
        # Check return value
        if return_value is not None:
            if return_value == 1:
                print(f"✓ Return value: {return_value} (measurement completed successfully)")
            elif return_value < 0:
                print(f"⚠️ Return value: {return_value} (error code)")
        else:
            print(f"⚠️ Could not read return value, but continuing")
        
        # Retrieve results
        print(f"\n📊 Retrieving results...")
        time.sleep(0.03)
        
        results = {
            'return_value': return_value,
            'V': [], 'I': [], 't': [],
            'pts': None,
            'P': None, 'Pa': None, 'U': None, 'Ua': None,
            'N': None, 'Na': None, 'D': None, 'Da': None,
            'Psw': None, 'Qsw': None
        }
        
        # Query output arrays and values
        # Parameter positions: 7=V, 9=I, 11=t, 13=P, 14=Pa, 15=U, 16=Ua, 17=N, 18=Na, 19=D, 20=Da, 21=Psw, 22=Qsw, 23=pts
        print("Querying GP 7 (V array)...")
        results['V'] = self._query_gp(7, V_size) or []
        time.sleep(0.03)
        
        print("Querying GP 9 (I array)...")
        results['I'] = self._query_gp(9, I_size) or []
        time.sleep(0.03)
        
        print("Querying GP 11 (t array)...")
        results['t'] = self._query_gp(11, t_size) or []
        time.sleep(0.03)
        
        # Query scalar outputs
        for param_num, key in [(13, 'P'), (14, 'Pa'), (15, 'U'), (16, 'Ua'),
                               (17, 'N'), (18, 'Na'), (19, 'D'), (20, 'Da'),
                               (21, 'Psw'), (22, 'Qsw'), (23, 'pts')]:
            print(f"Querying GP {param_num} ({key})...")
            vals = self._query_gp(param_num, 1)
            if vals:
                if key == 'pts':
                    results[key] = int(vals[0])
                else:
                    results[key] = vals[0]
            time.sleep(0.03)
        
        # Determine success
        has_data = (len(results['V']) > 0 or len(results['I']) > 0 or results['pts'] is not None)
        
        if return_value == 1:
            results['success'] = True
        elif return_value is None and has_data:
            results['success'] = True
            print(f"✓ Measurement appears successful (data retrieved)")
        else:
            results['success'] = has_data
        
        if results['success']:
            print(f"\n✓ pundTest completed successfully")
            print(f"  Points: {results['pts']}")
            print(f"  P={results['P']}, Pa={results['Pa']}")
            print(f"  U={results['U']}, Ua={results['Ua']}")
            print(f"  N={results['N']}, Na={results['Na']}")
            print(f"  D={results['D']}, Da={results['Da']}")
            print(f"  Psw={results['Psw']}, Qsw={results['Qsw']}")
        else:
            print(f"\n⚠️ pundTest may have failed")
        print(f"{'='*60}\n")
        
        # Exit UL mode
        print(f"[KXCI] Exiting UL mode...")
        self._exit_ul_mode()
        
        return results
    
    def nvm_reram_stress(
        self,
        riseTime: float = 1e-4,
        widthTime: float = 1e-4,
        compCH: int = 2,
        biasV: float = -2.5,
        Irange: float = 1e-2,
        Icomp: float = 0.0,
        resTestV: float = 0.5,
        useSmu: int = 0,
        Vforce_size: int = 3000,
        Imeas_size: int = 3000,
        Time_size: int = 3000
    ) -> Dict[str, Any]:
        """
        Execute NVM library reramStress function - single long stress pulse test.
        
        Performs a single long stress pulse and measures resistance before and after.
        
        Args:
            riseTime: Time for voltage to ramp (s)
            widthTime: Time at peak voltage (s). Can be very long (up to 480s).
            compCH: Compliance channel (1 or 2)
            biasV: Bias voltage for stress pulse (V)
            Irange: Current measurement range (A)
            Icomp: Current compliance (A). 0 = max of Irange.
            resTestV: Voltage for resistance measurement (V)
            useSmu: 1 = use SMU, 0 = use PMU
            Vforce_size: Size of output voltage array
            Imeas_size: Size of output current array
            Time_size: Size of output time array
            
        Returns:
            Dictionary with:
            - 'return_value': Function return code
            - 'Vforce': Voltage waveform array
            - 'Imeas': Current waveform array
            - 'Time': Time array
            - 'pts': Number of points
            - 'beforeRes': Resistance before stress pulse
            - 'afterRes': Resistance after stress pulse
            - 'success': Whether execution succeeded
        """
        # Ensure connection
        if not self.inst:
            if not self.connect():
                return {
                    'success': False,
                    'error': 'Failed to connect'
                }
        
        # Reset state
        if self._ul_mode_active:
            print("[KXCI] Still in UL mode from previous run, exiting first...")
            self._exit_ul_mode()
            time.sleep(0.03)
        
        # Enter UL mode
        if not self._enter_ul_mode():
            return {
                'success': False,
                'error': 'Failed to enter UL mode'
            }
        
        # Build EX command
        # Parameters: riseTime, widthTime, compCH, biasV, Irange, Icomp, resTestV, useSmu,
        #            Vforce (output), Vforce_size, Imeas (output), Imeas_size,
        #            Time (output), Time_size, pts (output), beforeRes (output), afterRes (output)
        params = [
            riseTime, widthTime, compCH, biasV, Irange, Icomp, resTestV, useSmu,
            "",  # Vforce (output array - empty)
            Vforce_size,
            "",  # Imeas (output array - empty)
            Imeas_size,
            "",  # Time (output array - empty)
            Time_size,
            "",  # pts (output scalar - empty)
            "",  # beforeRes (output scalar - empty)
            ""   # afterRes (output scalar - empty)
        ]
        
        ex_command = self._build_ex_command("nvm", "reramStress", params)
        
        print(f"\n[KXCI] Sending command:")
        print(f"[KXCI] {ex_command}")
        
        print(f"\n{'='*60}")
        print("Executing NVM reramStress (Stress Pulse Test)")
        print(f"{'='*60}")
        
        # Execute EX command
        return_value, error = self._execute_ex_command(ex_command)
        
        if error and "failed" in error.lower():
            self._exit_ul_mode()
            return {
                'success': False,
                'error': error,
                'return_value': return_value
            }
        
        # Check return value
        if return_value is not None:
            if return_value == 1:
                print(f"✓ Return value: {return_value} (measurement completed successfully)")
            elif return_value < 0:
                print(f"⚠️ Return value: {return_value} (error code)")
        else:
            print(f"⚠️ Could not read return value, but continuing")
        
        # Retrieve results
        print(f"\n📊 Retrieving results...")
        time.sleep(0.03)
        
        results = {
            'return_value': return_value,
            'Vforce': [],
            'Imeas': [],
            'Time': [],
            'pts': None,
            'beforeRes': None,
            'afterRes': None
        }
        
        # Query output arrays
        # Parameter positions: 9=Vforce, 11=Imeas, 13=Time, 15=pts, 16=beforeRes, 17=afterRes
        
        # First get pts to know how many values to query
        print("Querying GP 15 (pts)...")
        pts_vals = self._query_gp(15, 1)
        if pts_vals:
            results['pts'] = int(pts_vals[0])
        else:
            results['pts'] = None
        time.sleep(0.03)
        
        # Query arrays using actual number of points (or requested size if pts not available)
        num_points = results['pts'] if results['pts'] else Vforce_size
        
        print(f"Querying GP 9 (Vforce array, {num_points} points)...")
        results['Vforce'] = self._query_gp(9, num_points) or []
        time.sleep(0.03)
        
        print(f"Querying GP 11 (Imeas array, {num_points} points)...")
        results['Imeas'] = self._query_gp(11, num_points) or []
        time.sleep(0.03)
        
        print(f"Querying GP 13 (Time array, {num_points} points)...")
        results['Time'] = self._query_gp(13, num_points) or []
        time.sleep(0.03)
        
        print("Querying GP 16 (beforeRes)...")
        beforeR_vals = self._query_gp(16, 1)
        if beforeR_vals:
            results['beforeRes'] = beforeR_vals[0]
        time.sleep(0.03)
        
        print("Querying GP 17 (afterRes)...")
        afterR_vals = self._query_gp(17, 1)
        if afterR_vals:
            results['afterRes'] = afterR_vals[0]
        time.sleep(0.03)
        
        # Determine success
        has_data = (len(results['Vforce']) > 0 or len(results['Imeas']) > 0 or 
                   results['pts'] is not None)
        
        if return_value == 1:
            results['success'] = True
        elif return_value is None and has_data:
            results['success'] = True
            print(f"✓ Measurement appears successful (data retrieved)")
        else:
            results['success'] = has_data
        
        if results['success']:
            print(f"\n✓ reramStress completed successfully")
            print(f"  Points: {results['pts']}")
            print(f"  Resistance before: {results['beforeRes']} Ω")
            print(f"  Resistance after: {results['afterRes']} Ω")
            if results['beforeRes'] and results['afterRes']:
                delta = results['afterRes'] - results['beforeRes']
                delta_pct = (delta / results['beforeRes'] * 100) if results['beforeRes'] != 0 else 0
                print(f"  Resistance change: {delta:.2e} Ω ({delta_pct:+.2f}%)")
        else:
            print(f"\n⚠️ reramStress may have failed")
        print(f"{'='*60}\n")
        
        # Exit UL mode
        print(f"[KXCI] Exiting UL mode...")
        self._exit_ul_mode()
        
        return results
    
    def retention_pulse_ilimit_nk(
        self,
        InstrName: str = "PMU1",
        ForceCh: int = 1,
        ForceVRange: float = 5.0,
        ForceIRange: float = 1e-2,
        iFLimit: float = 0.0,
        iMLimit: float = 0.0,
        MeasureCh: int = 2,
        MeasureVRange: float = 5.0,
        MeasureIRange: float = 1e-2,
        max_pts: int = 10000,
        MeasureBias: float = 0.0,
        Volts: List[float] = None,
        Times: List[float] = None,
        vf_size: int = 100,
        if_size: int = 100,
        vm_size: int = 100,
        im_size: int = 100,
        t_size: int = 100
    ) -> Dict[str, Any]:
        """
        Execute retention_pulse_ilimitNK measurement.
        
        This function performs a pulse measurement with current limiting on both
        force and measure channels, returning voltage and current data from both channels.
        
        Args:
            InstrName: Instrument name (e.g., "PMU1")
            ForceCh: Force channel (1 or 2)
            ForceVRange: Voltage range for force channel (5, 10, or 40 V)
            ForceIRange: Current range for force channel (A)
            iFLimit: Current limit for force channel (A). 0.0 = disabled
            iMLimit: Current limit for measure channel (A). 0.0 = disabled
            MeasureCh: Measure channel (1 or 2)
            MeasureVRange: Voltage range for measure channel (5, 10, or 40 V)
            MeasureIRange: Current range for measure channel (A)
            max_pts: Maximum number of points to collect
            MeasureBias: Bias voltage for measure channel (V)
            Volts: Input voltage array for segment profile (V)
            Times: Input time array for segment profile (s). Size should be volts_size - 1
            vf_size: Size of output VF array
            if_size: Size of output IF array
            vm_size: Size of output VM array
            im_size: Size of output IM array
            t_size: Size of output T array
            
        Returns:
            Dictionary with:
            - 'return_value': Function return code (0 = success, negative = error)
            - 'VF': Voltage array from ForceCh (V)
            - 'IF': Current array from ForceCh (A)
            - 'VM': Voltage array from MeasureCh (V)
            - 'IM': Current array from MeasureCh (A)
            - 'T': Time array (s)
            - 'npts': Actual number of collected data points
            - 'success': Whether execution succeeded
        """
        # Ensure connection
        if not self.inst:
            if not self.connect():
                return {
                    'success': False,
                    'error': 'Failed to connect'
                }
        
        # Default input arrays if not provided
        if Volts is None:
            Volts = [0.0, 1.0, 0.0]  # Default: 0V -> 1V -> 0V
        if Times is None:
            Times = [1e-6, 1e-6]  # Default: 1us each segment
        
        volts_size = len(Volts)
        times_size = len(Times)
        
        # Reset state
        if self._ul_mode_active:
            print("[KXCI] Still in UL mode from previous run, exiting first...")
            self._exit_ul_mode()
            time.sleep(0.03)
        
        # Enter UL mode
        if not self._enter_ul_mode():
            return {
                'success': False,
                'error': 'Failed to enter UL mode'
            }
        
        # Build EX command
        # Parameters: InstrName, ForceCh, ForceVRange, ForceIRange, iFLimit, iMLimit,
        #            MeasureCh, MeasureVRange, MeasureIRange, max_pts, MeasureBias,
        #            Volts (input array), volts_size, Times (input array), times_size,
        #            VF (output), vf_size, IF (output), if_size,
        #            VM (output), vm_size, IM (output), im_size,
        #            T (output), t_size, npts (output)
        
        # Format input arrays as comma-separated values
        # Note: TSP arrays may need special formatting - testing may be required
        volts_str = ",".join(self._format_parameter(v) for v in Volts)
        times_str = ",".join(self._format_parameter(t) for t in Times)
        
        # Build parameter list
        # For arrays in TSP, we pass them as comma-separated values (may need adjustment)
        params = [
            InstrName,
            ForceCh,
            ForceVRange,
            ForceIRange,
            iFLimit,
            iMLimit,
            MeasureCh,
            MeasureVRange,
            MeasureIRange,
            max_pts,
            MeasureBias,
            f"{{{volts_str}}}",  # Array format: {value1,value2,value3} - may need adjustment
            volts_size,
            f"{{{times_str}}}",  # Array format
            times_size,
            "",  # VF (output array - empty)
            vf_size,
            "",  # IF (output array - empty)
            if_size,
            "",  # VM (output array - empty)
            vm_size,
            "",  # IM (output array - empty)
            im_size,
            "",  # T (output array - empty)
            t_size,
            ""   # npts (output scalar - empty)
        ]
        
        ex_command = self._build_ex_command("Python_Controlled_PMU_Craig", "retention_pulse_ilimitNK", params)
        
        print(f"\n[KXCI] Sending command:")
        print(f"[KXCI] {ex_command}")
        
        print(f"\n{'='*60}")
        print("Executing retention_pulse_ilimitNK")
        print(f"{'='*60}")
        
        # Execute EX command
        return_value, error = self._execute_ex_command(ex_command)
        
        if error and "failed" in error.lower():
            self._exit_ul_mode()
            return {
                'success': False,
                'error': error,
                'return_value': return_value
            }
        
        # Check return value (0 = success for this function)
        if return_value is not None:
            if return_value == 0:
                print(f"✓ Return value: {return_value} (measurement completed successfully)")
            elif return_value < 0:
                print(f"⚠️ Return value: {return_value} (error code - see function documentation)")
            else:
                print(f"⚠️ Return value: {return_value} (unexpected)")
        else:
            print(f"⚠️ Could not read return value, but continuing")
        
        # Retrieve results using GP commands
        print(f"\n📊 Retrieving results...")
        time.sleep(0.03)
        
        results = {
            'return_value': return_value,
            'VF': [],
            'IF': [],
            'VM': [],
            'IM': [],
            'T': [],
            'npts': None
        }
        
        # Query output arrays
        # Parameter positions based on function signature (1-based):
        # 16: VF (output), 18: IF (output), 20: VM (output), 
        # 22: IM (output), 24: T (output), 26: npts (output)
        
        print("Querying GP 16 (VF array)...")
        results['VF'] = self._query_gp(16, vf_size) or []
        print(f"  Retrieved {len(results['VF'])} VF values")
        time.sleep(0.03)
        
        print("Querying GP 18 (IF array)...")
        results['IF'] = self._query_gp(18, if_size) or []
        print(f"  Retrieved {len(results['IF'])} IF values")
        time.sleep(0.03)
        
        print("Querying GP 20 (VM array)...")
        results['VM'] = self._query_gp(20, vm_size) or []
        print(f"  Retrieved {len(results['VM'])} VM values")
        time.sleep(0.03)
        
        print("Querying GP 22 (IM array)...")
        results['IM'] = self._query_gp(22, im_size) or []
        print(f"  Retrieved {len(results['IM'])} IM values")
        time.sleep(0.03)
        
        print("Querying GP 24 (T array)...")
        results['T'] = self._query_gp(24, t_size) or []
        print(f"  Retrieved {len(results['T'])} T values")
        time.sleep(0.03)
        
        print("Querying GP 26 (npts)...")
        npts_vals = self._query_gp(26, 1)
        if npts_vals:
            results['npts'] = int(npts_vals[0])
        time.sleep(0.03)
        
        # Determine success
        has_data = (len(results['VF']) > 0 or len(results['IF']) > 0 or 
                   len(results['VM']) > 0 or len(results['IM']) > 0 or
                   len(results['T']) > 0 or results['npts'] is not None)
        
        if return_value == 0:
            results['success'] = True
        elif return_value is None and has_data:
            results['success'] = True
            print(f"✓ Measurement appears successful (data retrieved)")
        elif return_value is None and not has_data:
            results['success'] = False
            results['error'] = 'No return value received and no data retrieved'
        else:
            results['success'] = has_data
        
        if results['success']:
            print(f"\n✓ retention_pulse_ilimitNK completed successfully")
            print(f"  Points: {results['npts']}")
            print(f"  VF points: {len(results['VF'])}")
            print(f"  IF points: {len(results['IF'])}")
            print(f"  VM points: {len(results['VM'])}")
            print(f"  IM points: {len(results['IM'])}")
            print(f"  T points: {len(results['T'])}")
        else:
            print(f"\n⚠️ retention_pulse_ilimitNK may have failed")
            if return_value is not None and return_value < 0:
                error_codes = {
                    -1: "volts_size error (should be > 3)",
                    -2: "vf_size/if_size/t_size error",
                    -3: "vm_size/im_size/t_size error",
                    -4: "Cannot get InstrName",
                    -5: "Error getting InstId",
                    -6: "Error in pg2_init",
                    -7: "Error in pulse_load for ForceCh",
                    -8: "Error in pulse_ranges for ForceCh",
                    -9: "Error in pulse_burst_count for ForceCh",
                    -10: "Error in pulse_output for ForceCh",
                    -11: "Error in pulse_load for MeasureCh",
                    -12: "Error in pulse_ranges for MeasureCh",
                    -13: "Error in pulse_burst_count for MeasureCh",
                    -14: "Error in pulse_output for MeasureCh",
                    -15: "Error in pulse_sample_rate",
                    -16: "Error in seg_arb_sequence for ForceCh",
                    -17: "Error in seg_arb_sequence for MeasureCh",
                    -18: "Error in seg_arb_waveform for ForceCh",
                    -19: "Error in seg_arb_waveform for MeasureCh",
                    -20: "Error in pulse_fetch for ForceCh",
                    -21: "Error in pulse_fetch for MeasureCh",
                    -22: "Max_pts too large",
                    -33: "Invalid rate",
                    -44: "RPMs are in bypass",
                    -141: "Error setting iFLimit",
                    -142: "Error setting iMLimit"
                }
                error_msg = error_codes.get(return_value, f"Unknown error code {return_value}")
                results['error'] = error_msg
                print(f"  Error: {error_msg}")
        print(f"{'='*60}\n")
        
        # Exit UL mode
        print(f"[KXCI] Exiting UL mode...")
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
    ║   PMU_retention measurement.                                ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    gpib_address = input("Enter GPIB address (default: GPIB0::17::INSTR): ").strip()
    if not gpib_address:
        gpib_address = "GPIB0::17::INSTR"
    
    try:
        with Keithley4200A_KXCI(gpib_address=gpib_address) as keithley:
            # Example PMU_retention call - uses default parameters (matching the hardcoded command)
            result = keithley.pmu_retention()
            
            if result['success']:
                print("\n📊 RESULTS:")
                print(f"  Return value: {result['return_value']}")
                print(f"  Parameter 18: {result.get('param18', 'N/A')}")
                print(f"  SET V values (probe voltages) ({len(result['setV'])} points): {result['setV']}")
                print(f"  SET I values (probe currents) ({len(result['setI'])} points): {result['setI']}")
                print(f"  PulseTimes ({len(result['PulseTimes'])} points): {result['PulseTimes']}")
                print(f"  OUT1 values ({len(result['out1'])} points): {result['out1']}")
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

