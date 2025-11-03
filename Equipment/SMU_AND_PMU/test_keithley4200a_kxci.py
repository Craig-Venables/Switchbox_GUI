"""
Test script for Keithley 4200A KXCI Controller

This script demonstrates how to use the Keithley4200A_KXCI class to
replace LabVIEW-based control of PMU_PulseTrain measurements.

Run this script to test the connection and execute a sample measurement.
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Equipment.SMU_AND_PMU.Keithley4200A_KXCI import Keithley4200A_KXCI


def test_connection():
    """Test basic connection to the instrument."""
    print("="*60)
    print("Testing Connection")
    print("="*60)
    
    gpib_address = input("Enter GPIB address (default: GPIB0::17::INSTR): ").strip()
    if not gpib_address:
        gpib_address = "GPIB0::17::INSTR"
    
    try:
        keithley = Keithley4200A_KXCI(gpib_address=gpib_address)
        
        if keithley.connect():
            print("✓ Connection successful!")
            keithley.disconnect()
            return True
        else:
            print("❌ Connection failed")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_pmu_pulse_train():
    """Test PMU_PulseTrain execution."""
    print("\n" + "="*60)
    print("Testing PMU_PulseTrain")
    print("="*60)
    
    gpib_address = input("Enter GPIB address (default: GPIB0::17::INSTR): ").strip()
    if not gpib_address:
        gpib_address = "GPIB0::17::INSTR"
    
    print("\n⚠️  WARNING: This will execute an actual measurement!")
    print("Make sure the 4200A is configured correctly and connected to your DUT.")
    response = input("\nProceed? (yes/no): ").strip().lower()
    
    if response != 'yes':
        print("Test cancelled")
        return
    
    try:
        with Keithley4200A_KXCI(gpib_address=gpib_address) as keithley:
            # Test parameters matching the working LabVIEW example:
            # EX Labview_Controlled_Programs_Kemp3 PMU_PulseTrain(1.00E-7,1,1.00E-6,5.00E-8,3.00E-1,2.00E-6,2.00E-6,1.00E-6,1.00E-7,1.00E-6,3.00E-1,3.00E-1,1,1.00E-4,10000,,12,,12,,12,,12,1,,12,VF,,12,T,,7,11111,5,0)
            result = keithley.pmu_pulse_train(
                riseTime=1e-7,          # 1.00E-7
                resetV=1.0,             # 1 (shown as "1" in LabVIEW)
                resetWidth=1e-6,        # 1.00E-6
                resetDelay=5e-8,         # 5.00E-8
                measV=0.3,              # 3.00E-1
                measWidth=2e-6,         # 2.00E-6
                measDelay=2e-6,         # 2.00E-6
                setWidth=1e-6,          # 1.00E-6
                setFallTime=1e-7,       # 1.00E-7
                setDelay=1e-6,           # 1.00E-6
                setStartV=0.3,          # 3.00E-1
                setStopV=0.3,           # 3.00E-1
                steps=1,                # 1
                IRange=1e-4,            # 1.00E-4
                max_points=10000,        # 10000
                setR_size=12,           # 12
                resetR_size=12,         # 12
                setV_size=12,           # 12
                setI_size=12,           # 12
                iteration=1,            # 1
                out1_size=12,           # 12
                out1_name="VF",         # VF
                out2_size=12,           # 12
                out2_name="T",          # T
                PulseTimes_size=7,      # 7
                PulseTrainSequence="11111",  # 11111
                NumbPulses=5,           # 5
                ClariusDebug=0          # 0
            )
            
            if result['success']:
                print("\n" + "="*60)
                print("RESULTS")
                print("="*60)
                print(f"Return value: {result['return_value']}")
                print(f"Parameter 18: {result['param18']}")
                print(f"\nSET V values ({len(result['setV'])} points):")
                for i, v in enumerate(result['setV'][:10]):  # Show first 10
                    print(f"  [{i}]: {v:.6e}")
                if len(result['setV']) > 10:
                    print(f"  ... ({len(result['setV']) - 10} more)")
                
                print(f"\nSET I values ({len(result['setI'])} points):")
                for i, i_val in enumerate(result['setI'][:10]):  # Show first 10
                    print(f"  [{i}]: {i_val:.6e}")
                if len(result['setI']) > 10:
                    print(f"  ... ({len(result['setI']) - 10} more)")
                
                print(f"\nOUT1 values ({len(result['out1'])} points):")
                for i, o in enumerate(result['out1'][:10]):  # Show first 10
                    print(f"  [{i}]: {o:.6e}")
                if len(result['out1']) > 10:
                    print(f"  ... ({len(result['out1']) - 10} more)")
            else:
                print(f"\n❌ Measurement failed: {result.get('error', 'Unknown error')}")
                
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main menu."""
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║   Keithley 4200A KXCI Controller Test                        ║
    ║                                                               ║
    ║   Select test:                                               ║
    ║   1. Test connection                                         ║
    ║   2. Test PMU_PulseTrain (actual measurement)               ║
    ║   3. Exit                                                     ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    choice = input("Enter choice (1-3): ").strip()
    
    if choice == "1":
        test_connection()
    elif choice == "2":
        test_pmu_pulse_train()
    elif choice == "3":
        print("Exiting...")
    else:
        print("Invalid choice")


if __name__ == "__main__":
    main()

