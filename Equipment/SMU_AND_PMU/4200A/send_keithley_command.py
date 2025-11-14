"""
Simple script to send a preprogrammed command to Keithley 4200A via KXCI.

Usage:
    1. Edit the COMMAND and GPIB_ADDRESS variables below
    2. Run: python send_keithley_command.py

This script will:
    - Connect to the Keithley
    - Enter UL mode (if needed)
    - Send your command
    - Print the response
    - Disconnect
"""

import pyvisa
import time

# ============================================================================
# CONFIGURATION - Edit these values
# ============================================================================

# GPIB address of your Keithley 4200A
GPIB_ADDRESS = "GPIB0::17::INSTR"

# Command to send (EX command only - UL is sent automatically first)
# Examples:
#   "EX Python_Controlled_PMU_Craig TwoTonesTwice"
#   "EX Python_Controlled_PMU_Craig PMU_retention(...)"
COMMAND = "EX Python_Controlled_PMU_Craig TwoTonesTwice(1000,400)"

# ============================================================================
# Script execution
# ============================================================================

def main():
    print("="*60)
    print("Keithley 4200A Command Sender")
    print("="*60)
    print(f"GPIB Address: {GPIB_ADDRESS}")
    print(f"Command: {COMMAND}")
    print("="*60)
    
    rm = None
    inst = None
    
    try:
        # Connect
        print("\n[1/4] Connecting to instrument...")
        rm = pyvisa.ResourceManager()
        inst = rm.open_resource(GPIB_ADDRESS)
        inst.timeout = 30000  # 30 second timeout
        inst.write_termination = '\n'
        inst.read_termination = '\n'
        
        # Test connection
        idn = inst.query("*IDN?")
        print(f"✓ Connected: {idn.strip()}")
        
        # Enter UL mode first
        print(f"\n[2/5] Entering UL mode...")
        inst.write("UL")
        time.sleep(0.03)  # Wait 30ms as per KXCI protocol
        print(f"      UL sent")
        
        # Send command
        print(f"\n[3/5] Sending command...")
        print(f"      {COMMAND}")
        inst.write(COMMAND)
        time.sleep(2.0)  # Wait for measurement to complete (2000ms as per protocol)
        
        # Read response
        print(f"\n[4/5] Reading response...")
        try:
            response = inst.read()
            print(f"\n✓ Response received:")
            print("-" * 60)
            print(response)
            print("-" * 60)
        except pyvisa.errors.VisaIOError as e:
            if "timeout" in str(e).lower():
                print("⚠️  No response received (timeout) - command may have executed without response")
            else:
                print(f"⚠️  Read error: {e}")
        
        print(f"\n[5/5] Done!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Disconnect
        if inst:
            try:
                inst.close()
            except:
                pass
        if rm:
            try:
                rm.close()
            except:
                pass
        print("\n✓ Disconnected")

if __name__ == "__main__":
    main()

