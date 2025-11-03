"""
KXCI Diagnostic Script for Keithley 4200A
=========================================

This script explores the KXCI interface to discover:
1. UL (User Library) command syntax
2. Required initialization sequence
3. EX command format and response parsing
4. Array handling in KXCI responses
5. Error handling and status codes

Run this script while connected to the 4200A via GPIB to gather
information needed for implementing the 4200A system adapter.

CONTEXT FOR FUTURE AI ASSISTANT:
================================
This script is part of refactoring TSP_Testing_GUI.py to support multiple
SMU systems. The goal is to implement keithley4200a.py in Pulse_Testing/systems/
to work alongside keithley2450.py.

The 4200A uses KXCI (Keithley External Control Interface) over GPIB,
calling KULT (Keithley User Library) functions via EX commands.

Key files referenced:
- Equipment/SMU_AND_PMU/4200A/PMU-Helpers/PMU-Ccode/PMU_PulseTrain.c
- Equipment/SMU_AND_PMU/4200A/PMU-Helpers/PMU-Ccode/PulseTrain_pulse_ilimitNK.c
- Pulse_Testing/systems/keithley4200a.py (target implementation)

Example command format observed:
  EX Labview_Controlled_Programs_Kemp3 PMU_PulseTrain(1.00E-7,2,1.00E-6,...)
  EX Labview_Controlled_Programs_Kemp PMU_endurance(...)

CONFIRMED FROM KXCI MANUAL (via web search):
===========================================
1. UL Command: "UL" (no parameters) - switches to User Library mode
2. EX Command: "EX <LibraryName> <FunctionName>(<parameters>)"
3. GP Command: "GP <ParameterPosition> [NumValues]" - query parameter values
4. GN Command: "GN <ParameterName>" - query parameter by name
5. DE/US Commands: Return to normal KXCI mode from UL mode

Workflow:
  1. Connect via GPIB
  2. Send "UL" to switch to User Library mode
  3. Send "EX ..." to execute user library function
  4. Use "GP" or "GN" to retrieve output arrays/values
  5. (Optional) Send "DE" or "US" to return to normal mode
"""

import pyvisa
import time
import json
from datetime import datetime
from pathlib import Path

class KXCIDiagnostics:
    def __init__(self, gpib_address="GPIB0::17::INSTR", timeout=10.0):
        """
        Initialize GPIB connection to 4200A.
        
        Args:
            gpib_address: GPIB address string (e.g., "GPIB0::12::INSTR")
            timeout: Timeout in seconds
        """
        self.gpib_address = gpib_address
        self.timeout = timeout * 1000  # Convert to milliseconds
        self.rm = None
        self.inst = None
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'gpib_address': gpib_address,
            'tests': []
        }
        
    def connect(self):
        """Establish GPIB connection."""
        try:
            self.rm = pyvisa.ResourceManager()
            print(f"✓ VISA ResourceManager initialized")
            
            print(f"📡 Attempting connection to {self.gpib_address}...")
            self.inst = self.rm.open_resource(self.gpib_address)
            self.inst.timeout = self.timeout
            
            # Common GPIB settings
            self.inst.write_termination = '\n'
            self.inst.read_termination = '\n'
            
            print(f"✓ Connected to {self.gpib_address}")
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    def disconnect(self):
        """Close GPIB connection."""
        try:
            if self.inst:
                self.inst.close()
            if self.rm:
                self.rm.close()
            print("✓ Disconnected")
        except Exception as e:
            print(f"⚠️ Error during disconnect: {e}")
    
    def test_command(self, name, command, expect_response=True, parse_response=True):
        """
        Test a KXCI command and record results.
        
        Args:
            name: Test name/description
            command: Command string to send
            expect_response: Whether to read response
            parse_response: Whether to attempt parsing
        """
        test_result = {
            'name': name,
            'command': command,
            'timestamp': datetime.now().isoformat(),
            'success': False,
            'response': None,
            'error': None,
            'response_type': None,
            'parsed_response': None
        }
        
        try:
            print(f"\n{'='*60}")
            print(f"TEST: {name}")
            print(f"Command: {command}")
            print(f"{'='*60}")
            
            # Send command
            self.inst.write(command)
            print(f"✓ Command sent")
            
            if expect_response:
                # Wait a bit for response
                time.sleep(0.1)
                
                # Try to read response
                try:
                    response = self.inst.read()
                    test_result['response'] = response
                    test_result['response_type'] = type(response).__name__
                    print(f"✓ Response received: {repr(response[:200])}")  # First 200 chars
                    print(f"  Response type: {type(response).__name__}")
                    print(f"  Response length: {len(response)} characters")
                    
                    # Try to parse as JSON
                    if parse_response:
                        try:
                            parsed = json.loads(response)
                            test_result['parsed_response'] = parsed
                            print(f"  ✓ Response is valid JSON")
                        except json.JSONDecodeError:
                            # Try to parse as comma-separated values
                            if ',' in response:
                                values = [v.strip() for v in response.split(',')]
                                test_result['parsed_response'] = {
                                    'type': 'comma_separated',
                                    'values': values,
                                    'count': len(values)
                                }
                                print(f"  ✓ Response appears to be comma-separated ({len(values)} values)")
                            else:
                                print(f"  ⚠️ Response is not JSON or CSV")
                    
                except Exception as e:
                    test_result['error'] = f"Failed to read response: {e}"
                    print(f"⚠️ No response or error reading: {e}")
            else:
                print(f"✓ Command sent (no response expected)")
            
            test_result['success'] = True
            
        except Exception as e:
            test_result['error'] = str(e)
            print(f"❌ Error: {e}")
        
        self.results['tests'].append(test_result)
        return test_result
    
    def run_diagnostics(self):
        """Run all diagnostic tests."""
        print("\n" + "="*60)
        print("KXCI DIAGNOSTICS FOR KEITHLEY 4200A")
        print("="*60)
        print(f"GPIB Address: {self.gpib_address}")
        print(f"Timestamp: {self.results['timestamp']}")
        print("="*60)
        
        if not self.connect():
            print("\n❌ Cannot proceed without connection")
            return
        
        # ============================================================
        # TEST GROUP 1: Basic Connection & ID
        # ============================================================
        print("\n\n" + "#"*60)
        print("# GROUP 1: Basic Connection & Identification")
        print("#"*60)
        
        self.test_command("Query ID", "*IDN?")
        self.test_command("Query Error", "*ESR?")
        
        # ============================================================
        # TEST GROUP 2: UL (User Library) Mode Switching
        # ============================================================
        print("\n\n" + "#"*60)
        print("# GROUP 2: UL (User Library) Mode Commands")
        print("#"*60)
        print("# Testing various UL command formats to find correct syntax")
        
        ul_variants = [
            "UL",
            "UL ON",
            "UL 1",
            "UL MODE",
            "UL MODE ON",
            ":UL",
            ":UL ON",
            "USERLIB",
            "USERLIB ON",
            ":USERLIB",
        ]
        
        for variant in ul_variants:
            self.test_command(f"UL variant: {variant}", variant, expect_response=True)
            time.sleep(0.2)
        
        # Check if we're in UL mode
        self.test_command("Query UL status", "UL?", expect_response=True)
        self.test_command("Query UL status alternative", ":UL?", expect_response=True)
        
        # Based on manual: UL command is just "UL" (no parameters)
        # Let's send it and see the response
        print("\n📋 NOTE: Manual confirms UL command is just 'UL' (no parameters)")
        print("    Sending UL command to switch to User Library mode...")
        
        # ============================================================
        # TEST GROUP 2B: Switch to UL Mode (CONFIRMED)
        # ============================================================
        print("\n\n" + "#"*60)
        print("# GROUP 2B: UL Command (Confirmed from Manual)")
        print("#"*60)
        print("# Manual states: 'UL' command switches to User Library mode")
        print("# This should be sent ONCE before executing EX commands")
        
        ul_result = self.test_command("UL (User Library mode - CONFIRMED)", "UL", expect_response=True)
        if ul_result['success']:
            print("✓ UL command sent - should now be in User Library mode")
            if ul_result['response']:
                print(f"  Response: {repr(ul_result['response'][:100])}")
        
        # ============================================================
        # TEST GROUP 3: Initialization & Setup Commands
        # ============================================================
        print("\n\n" + "#"*60)
        print("# GROUP 3: Initialization Commands")
        print("#"*60)
        print("# Testing common initialization commands")
        
        init_commands = [
            ("Reset", "*RST"),
            ("Clear Status", "*CLS"),
            ("Test Station Select", "TST SEL 1"),
            ("Test Station Select Alt", "TST? SEL 1"),
            ("Device Initialize", "DEV INT"),
            ("Device Initialize Alt", "DEV? INT"),
            ("Initialize", "INIT"),
            ("Wait", "*WAI"),
        ]
        
        for name, cmd in init_commands:
            self.test_command(f"Init: {name}", cmd, expect_response=False)
            time.sleep(0.1)
        
        # ============================================================
        # TEST GROUP 4: EX Command Format - Simple Test
        # ============================================================
        print("\n\n" + "#"*60)
        print("# GROUP 4: EX Command - Simple Function Call")
        print("#"*60)
        print("# Testing EX command format with minimal parameters")
        
        # Try to find available libraries first
        self.test_command("List libraries", "UL? LIST", expect_response=True)
        self.test_command("List libraries alt", "UL LIST", expect_response=True)
        self.test_command("Query user libraries", "USERLIB?", expect_response=True)
        
        # Try a simple EX command (this might fail, but we'll see the error)
        simple_ex_commands = [
            "EX Labview_Controlled_Programs_Kemp3 PMU_PulseTrain()",
            "EX? Labview_Controlled_Programs_Kemp3 PMU_PulseTrain",
            "UL EX Labview_Controlled_Programs_Kemp3 PMU_PulseTrain()",
        ]
        
        for cmd in simple_ex_commands:
            self.test_command(f"Simple EX: {cmd[:50]}", cmd, expect_response=True)
            time.sleep(0.2)
        
        # ============================================================
        # TEST GROUP 5: EX Command - Actual PMU_PulseTrain
        # ============================================================
        print("\n\n" + "#"*60)
        print("# GROUP 5: EX Command - PMU_PulseTrain with Parameters")
        print("#"*60)
        print("# Testing with parameters matching your observed format")
        print("# Based on PMU_PulseTrain.c signature (35 parameters)")
        
        # Minimal valid parameter set based on PMU_PulseTrain.c
        # Parameters in order (see PMU_PulseTrain.c lines 7-41):
        # riseTime, resetV, resetWidth, resetDelay,
        # measV, measWidth, measDelay,
        # setWidth, setFallTime, setDelay,
        # setStartV, setStopV, steps, IRange, max_points,
        # setR_size, resetR_size, setV_size, setI_size,
        # iteration, out1_size, out1_name, out2_size, out2_name,
        # PulseTimes_size, PulseTrainSequence, NumbPulses, ClariusDebug
        
        # Minimal test parameters (safe values)
        test_params = (
            "1.00E-7,"      # riseTime
            "2.00E+0,"      # resetV (2V)
            "1.00E-6,"      # resetWidth
            "5.00E-8,"      # resetDelay
            "3.00E-1,"      # measV (0.3V)
            "2.00E-6,"      # measWidth
            "2.00E-6,"      # measDelay
            "1.00E-6,"      # setWidth
            "1.00E-7,"      # setFallTime
            "1.00E-6,"      # setDelay
            "3.00E-1,"      # setStartV
            "3.00E-1,"      # setStopV
            "1,"            # steps
            "1.00E-4,"      # IRange
            "10000,"        # max_points
            ",12,"          # setR (output, empty), setR_size
            ",12,"          # resetR (output, empty), resetR_size
            ",12,"          # setV (output, empty), setV_size
            ",12,"          # setI (output, empty), setI_size
            "1,"            # iteration
            ",200,"         # out1 (output, empty), out1_size
            "VF,"           # out1_name
            ",200,"         # out2 (output, empty), out2_size
            "T,"            # out2_name
            ",12,"          # PulseTimes (output, empty), PulseTimes_size
            "10101,"        # PulseTrainSequence
            "4,"            # NumbPulses
            "0"             # ClariusDebug
        )
        
        ex_command = f"EX Labview_Controlled_Programs_Kemp3 PMU_PulseTrain({''.join(test_params)})"
        
        print(f"\n⚠️  WARNING: This will execute an actual measurement!")
        print(f"Command length: {len(ex_command)} characters")
        print("\n📋 IMPORTANT: Make sure UL command was sent first!")
        print("   If not, the EX command will fail. Check Group 2B results.")
        response = input("\nProceed with EX command test? (yes/no): ")
        
        if response.lower() == 'yes':
            # Ensure we're in UL mode (send UL again if needed)
            print("\n🔄 Ensuring UL mode is active...")
            self.test_command("UL (ensure mode)", "UL", expect_response=True)
            time.sleep(0.2)
            
            result = self.test_command("EX PMU_PulseTrain (minimal params)", ex_command, expect_response=True, parse_response=True)
            
            if result['response']:
                print(f"\n📊 RESPONSE ANALYSIS:")
                print(f"  Full response length: {len(result['response'])} chars")
                print(f"  First 500 chars: {result['response'][:500]}")
                print(f"  Last 500 chars: {result['response'][-500:]}")
                
                # Try to identify data format
                if result['response'].startswith('{'):
                    print(f"  ✓ Appears to be JSON")
                elif ',' in result['response']:
                    parts = result['response'].split(',')
                    print(f"  ✓ Appears to be comma-separated ({len(parts)} parts)")
                elif '\n' in result['response']:
                    lines = result['response'].split('\n')
                    print(f"  ✓ Appears to be line-separated ({len(lines)} lines)")
                
                # Now try to query parameters using GP command
                print(f"\n🔍 Attempting to query output parameters with GP command...")
                print(f"   (These commands should work after a successful EX execution)")
                
                gp_after_ex = [
                    ("GP 22 12 (setR array)", "GP 22 12"),
                    ("GP 24 12 (resetR array)", "GP 24 12"),
                    ("GP 26 12 (setV array)", "GP 26 12"),
                    ("GP 28 12 (setI array)", "GP 28 12"),
                    ("GP 37 12 (PulseTimes array)", "GP 37 12"),
                ]
                
                for name, cmd in gp_after_ex:
                    self.test_command(name, cmd, expect_response=True)
                    time.sleep(0.1)
            else:
                print(f"\n⚠️  No response from EX command")
                print(f"   This could mean:")
                print(f"   - UL mode not active (check Group 2B)")
                print(f"   - Invalid library/function name")
                print(f"   - Parameter mismatch")
                print(f"   - Command timed out")
        else:
            print("⏭️  Skipped EX command test")
        
        # ============================================================
        # TEST GROUP 6: GP Command (Query Parameter Values)
        # ============================================================
        print("\n\n" + "#"*60)
        print("# GROUP 6: GP Command (Query Parameter Values)")
        print("#"*60)
        print("# Manual states: GP <ParameterPosition> [NumValues]")
        print("# Used to retrieve output arrays after EX command execution")
        print("# For PMU_PulseTrain, output parameters are:")
        print("#   - setR (param 22, array)")
        print("#   - resetR (param 24, array)")
        print("#   - setV (param 26, array)")
        print("#   - setI (param 28, array)")
        print("#   - out1 (param 31, array)")
        print("#   - out2 (param 33, array)")
        print("#   - PulseTimes (param 37, array)")
        print("#")
        print("# NOTE: These will only work AFTER an EX command has been executed")
        
        gp_tests = [
            ("GP single param (setR)", "GP 22"),
            ("GP array param (setR, 12 values)", "GP 22 12"),
            ("GP resetR array", "GP 24 12"),
            ("GP setV array", "GP 26 12"),
            ("GP setI array", "GP 28 12"),
            ("GP out1 array", "GP 31 200"),
            ("GP out2 array", "GP 33 200"),
            ("GP PulseTimes array", "GP 37 12"),
            ("GP invalid param (test error)", "GP 999"),
        ]
        
        for name, cmd in gp_tests:
            self.test_command(name, cmd, expect_response=True)
            time.sleep(0.1)
        
        # ============================================================
        # TEST GROUP 7: GN Command (Query Parameter by Name)
        # ============================================================
        print("\n\n" + "#"*60)
        print("# GROUP 7: GN Command (Query Parameter by Name)")
        print("#"*60)
        print("# Manual states: GN <ParameterName>")
        print("# Alternative to GP command - query by name instead of position")
        
        gn_tests = [
            ("GN setR", "GN setR"),
            ("GN resetR", "GN resetR"),
            ("GN setV", "GN setV"),
            ("GN setI", "GN setI"),
            ("GN VF", "GN VF"),
            ("GN invalid name (test error)", "GN InvalidParamName"),
        ]
        
        for name, cmd in gn_tests:
            self.test_command(name, cmd, expect_response=True)
            time.sleep(0.1)
        
        # ============================================================
        # TEST GROUP 8: Return to Normal Mode
        # ============================================================
        print("\n\n" + "#"*60)
        print("# GROUP 8: Return to Normal KXCI Mode")
        print("#"*60)
        print("# Manual states: DE or US command returns to normal mode from UL mode")
        
        self.test_command("DE (return to normal mode)", "DE", expect_response=True)
        self.test_command("US (return to normal mode alt)", "US", expect_response=True)
        
        # ============================================================
        # TEST GROUP 9: Response Format Discovery
        # ============================================================
        print("\n\n" + "#"*60)
        print("# GROUP 9: Response Format Discovery")
        print("#"*60)
        
        # Query error status to see format
        self.test_command("Query errors", "*ESR?", expect_response=True)
        self.test_command("Query errors alt", "SYST:ERR?", expect_response=True)
        self.test_command("Query status", "STAT?", expect_response=True)
        
        # ============================================================
        # TEST GROUP 10: Alternative Library Names
        # ============================================================
        print("\n\n" + "#"*60)
        print("# GROUP 10: Alternative Library Names")
        print("#"*60)
        print("# Testing different library name formats")
        
        library_variants = [
            "Labview_Controlled_Programs_Kemp3",
            "Labview_Controlled_Programs_Kemp",
            "LabviewControlledProgramsKemp3",
            "LABVIEW_CONTROLLED_PROGRAMS_KEMP3",
        ]
        
        for lib_name in library_variants:
            test_cmd = f"EX {lib_name} PMU_PulseTrain()"
            self.test_command(f"Library variant: {lib_name}", test_cmd, expect_response=True)
            time.sleep(0.1)
        
        # ============================================================
        # SAVE RESULTS
        # ============================================================
        self.save_results()
        
    def save_results(self):
        """Save diagnostic results to JSON file."""
        output_dir = Path("Equipment/SMU_AND_PMU/4200A")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"kxci_diagnostics_{timestamp}.json"
        
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n\n{'='*60}")
        print(f"✓ Results saved to: {output_file}")
        print(f"{'='*60}")
        
        # Also create a human-readable summary
        summary_file = output_dir / f"kxci_diagnostics_{timestamp}.txt"
        with open(summary_file, 'w') as f:
            f.write("KXCI DIAGNOSTIC RESULTS\n")
            f.write("="*60 + "\n")
            f.write(f"Timestamp: {self.results['timestamp']}\n")
            f.write(f"GPIB Address: {self.results['gpib_address']}\n")
            f.write("\n" + "="*60 + "\n\n")
            
            for test in self.results['tests']:
                f.write(f"TEST: {test['name']}\n")
                f.write(f"Command: {test['command']}\n")
                f.write(f"Success: {test['success']}\n")
                if test['error']:
                    f.write(f"Error: {test['error']}\n")
                if test['response']:
                    f.write(f"Response (first 500 chars):\n{test['response'][:500]}\n")
                if test['parsed_response']:
                    f.write(f"Parsed: {test['parsed_response']}\n")
                f.write("\n" + "-"*60 + "\n\n")
        
        print(f"✓ Summary saved to: {summary_file}")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


def main():
    """Main entry point."""
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║   KXCI DIAGNOSTICS FOR KEITHLEY 4200A                        ║
    ║                                                               ║
    ║   This script will test various KXCI commands to discover:   ║
    ║   1. UL (User Library) command syntax                        ║
    ║   2. Required initialization sequence                       ║
    ║   3. EX command format and responses                         ║
    ║   4. GP/GN commands for querying parameters                  ║
    ║   5. Array handling in responses                             ║
    ║                                                               ║
    ║   CONFIRMED FROM MANUAL:                                     ║
    ║   - UL command: just "UL" (switches to User Library mode)    ║
    ║   - EX command: "EX <Library> <Function>(params)"            ║
    ║   - GP command: "GP <Position> [NumValues]" (query params)   ║
    ║   - GN command: "GN <ParameterName>" (query by name)          ║
    ║   - DE/US: Return to normal mode from UL mode                ║
    ║                                                               ║
    ║   Make sure the 4200A is connected via GPIB and powered on!   ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    # Get GPIB address from user
    default_address = "GPIB0::17::INSTR"
    user_input = input(f"Enter GPIB address (default: {default_address}): ").strip()
    gpib_address = user_input if user_input else default_address
    
    print(f"\n📡 Using GPIB address: {gpib_address}\n")
    
    try:
        with KXCIDiagnostics(gpib_address=gpib_address) as diag:
            diag.run_diagnostics()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()