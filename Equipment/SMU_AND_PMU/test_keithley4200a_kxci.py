"""
Test script for Keithley 4200A KXCI Controller

This script demonstrates how to use the Keithley4200A_KXCI class to
replace LabVIEW-based control of PMU_PulseTrain measurements.

Run this script to test the connection and execute a sample measurement.
"""

import sys
import time
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


# def test_pmu_pulse_train():
#     """Test PMU_PulseTrain execution."""
#     print("\n" + "="*60)
#     print("Testing PMU_PulseTrain")
#     print("="*60)
#     
#     gpib_address = input("Enter GPIB address (default: GPIB0::17::INSTR): ").strip()
#     if not gpib_address:
#         gpib_address = "GPIB0::17::INSTR"
#     
#     print("\n⚠️  WARNING: This will execute an actual measurement!")
#     print("Make sure the 4200A is configured correctly and connected to your DUT.")
#     response = input("\nProceed? (yes/no): ").strip().lower()
#     
#     if response != 'yes':
#         print("Test cancelled")
#         return
#     
#     try:
#         with Keithley4200A_KXCI(gpib_address=gpib_address) as keithley:
#             # Test parameters matching the working LabVIEW example:
#             # EX Labview_Controlled_Programs_Kemp3 PMU_PulseTrain(1.00E-7,1,1.00E-6,5.00E-8,3.00E-1,2.00E-6,2.00E-6,1.00E-6,1.00E-7,1.00E-6,3.00E-1,3.00E-1,1,1.00E-4,10000,,12,,12,,12,,12,1,,12,VF,,12,T,,7,11111,5,0)
#             result = keithley.pmu_pulse_train(
#                 riseTime=1e-7,          # 1.00E-7
#                 resetV=1.0,             # 1 (shown as "1" in LabVIEW)
#                 resetWidth=1e-6,        # 1.00E-6
#                 resetDelay=5e-8,         # 5.00E-8
#                 measV=0.3,              # 3.00E-1
#                 measWidth=2e-6,         # 2.00E-6
#                 measDelay=2e-6,         # 2.00E-6
#                 setWidth=1e-6,          # 1.00E-6
#                 setFallTime=1e-7,       # 1.00E-7
#                 setDelay=1e-6,           # 1.00E-6
#                 setStartV=0.3,          # 3.00E-1
#                 setStopV=0.3,           # 3.00E-1
#                 steps=1,                # 1
#                 IRange=1e-4,            # 1.00E-4
#                 max_points=10000,        # 10000
#                 setR_size=12,           # 12
#                 resetR_size=12,         # 12
#                 setV_size=12,           # 12
#                 setI_size=12,           # 12
#                 iteration=1,            # 1
#                 out1_size=12,           # 12
#                 out1_name="VF",         # VF
#                 out2_size=12,           # 12
#                 out2_name="T",          # T
#                 PulseTimes_size=7,      # 7
#                 PulseTrainSequence="11111",  # 11111
#                 NumbPulses=5,           # 5
#                 ClariusDebug=0          # 0
#             )
#             
#             if result['success']:
#                 print("\n" + "="*60)
#                 print("RESULTS")
#                 print("="*60)
#                 print(f"Return value: {result['return_value']}")
#                 print(f"Parameter 18: {result['param18']}")
#                 print(f"\nSET V values ({len(result['setV'])} points):")
#                 for i, v in enumerate(result['setV'][:10]):  # Show first 10
#                     print(f"  [{i}]: {v:.6e}")
#                 if len(result['setV']) > 10:
#                     print(f"  ... ({len(result['setV']) - 10} more)")
#                 
#                 print(f"\nSET I values ({len(result['setI'])} points):")
#                 for i, i_val in enumerate(result['setI'][:10]):  # Show first 10
#                     print(f"  [{i}]: {i_val:.6e}")
#                 if len(result['setI']) > 10:
#                     print(f"  ... ({len(result['setI']) - 10} more)")
#                 
#                 print(f"\nOUT1 values ({len(result['out1'])} points):")
#                 for i, o in enumerate(result['out1'][:10]):  # Show first 10
#                     print(f"  [{i}]: {o:.6e}")
#                 if len(result['out1']) > 10:
#                     print(f"  ... ({len(result['out1']) - 10} more)")
#             else:
#                 print(f"\n❌ Measurement failed: {result.get('error', 'Unknown error')}")
#                 
#     except KeyboardInterrupt:
#         print("\n\n⚠️  Interrupted by user")
#     except Exception as e:
#         print(f"\n\n❌ Fatal error: {e}")
#         import traceback
#         traceback.print_exc()


def test_pmu_retention():
    """Test PMU_retention execution."""
    print("\n" + "="*60)
    print("Testing PMU_retention")
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
            # EX Labview_Controlled_Programs_Kemp2 PMU_retention(1.00E-7,1.00E+0,1.00E-6,5.00E-7,3.00E-1,1.00E-6,2.00E-6,1.00E-6,1.00E-7,1.00E-6,3.00E-1,3.00E-1,0,1.00E-4,10000,,12,,12,,12,,12,1,,12,VF,,200,T,,12,0)
            result = keithley.pmu_retention()
            
            if result['success']:
                print("\n" + "="*60)
                print("RESULTS")
                print("="*60)
                print(f"Return value: {result['return_value']}")
                print(f"Parameter 18: {result.get('param18', 'N/A')}")
                
                print(f"\nSET V values (probe voltages) ({len(result['setV'])} points):")
                for i, v in enumerate(result['setV'][:15]):  # Show first 15
                    print(f"  [{i}]: {v:.6e}")
                if len(result['setV']) > 15:
                    print(f"  ... ({len(result['setV']) - 15} more)")
                
                print(f"\nSET I values (probe currents) ({len(result['setI'])} points):")
                for i, i_val in enumerate(result['setI'][:15]):  # Show first 15
                    print(f"  [{i}]: {i_val:.6e}")
                if len(result['setI']) > 15:
                    print(f"  ... ({len(result['setI']) - 15} more)")
                
                print(f"\nPulseTimes ({len(result['PulseTimes'])} points):")
                for i, t in enumerate(result['PulseTimes'][:15]):  # Show first 15
                    print(f"  [{i}]: {t:.6e}")
                if len(result['PulseTimes']) > 15:
                    print(f"  ... ({len(result['PulseTimes']) - 15} more)")
                
                print(f"\nOUT1 values ({len(result['out1'])} points):")
                for i, o in enumerate(result['out1'][:15]):  # Show first 15
                    print(f"  [{i}]: {o:.6e}")
                if len(result['out1']) > 15:
                    print(f"  ... ({len(result['out1']) - 15} more)")
            else:
                print(f"\n❌ Measurement failed: {result.get('error', 'Unknown error')}")
                
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()


def test_pmu_retention_test():
    """Test PMU_RetentionTest execution."""
    print("\n" + "="*60)
    print("Testing PMU_RetentionTest")
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
            result = keithley.pmu_retention_test(
                riseTime=1e-7,
                writeVoltage=2.5,
                writeWidth=100e-6,
                readVoltage=0.5,
                readWidth=10e-6,
                readInterval=1.0,  # 1 second between reads
                numReads=10,  # 10 measurements for testing (can be increased)
                readCount=3,  # 3 read pulses per measurement
                initialDelay=1e-6,
                IRange=1e-4,
                max_points=10000,
                resistance_size=200,
                time_size=200,
                iteration=1,
                out1_size=200,
                out1_name="VF",
                out2_size=200,
                out2_name="T",
                ClariusDebug=0
            )
            
            if result['success']:
                print("\n" + "="*60)
                print("RESULTS")
                print("="*60)
                print(f"Return value: {result['return_value']}")
                
                print(f"\nResistance values ({len(result['resistance'])} points):")
                for i, r in enumerate(result['resistance'][:15]):
                    print(f"  [{i}]: {r:.6e} Ohm")
                if len(result['resistance']) > 15:
                    print(f"  ... ({len(result['resistance']) - 15} more)")
                
                print(f"\nTime values ({len(result['time_s'])} points):")
                for i, t in enumerate(result['time_s'][:15]):
                    print(f"  [{i}]: {t:.6f} s")
                if len(result['time_s']) > 15:
                    print(f"  ... ({len(result['time_s']) - 15} more)")
                
                print(f"\nOUT1 values ({len(result['out1'])} points):")
                for i, o in enumerate(result['out1'][:10]):
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



def test_pmu_retention_simple():
    """Test PMU_RetentionSimple function - single write/read measurement."""
    print("\n" + "="*60)
    print("Testing PMU_RetentionSimple (Single Measurement)")
    print("="*60)
    
    gpib_address = input("Enter GPIB address (default: GPIB0::17::INSTR): ").strip()
    if not gpib_address:
        gpib_address = "GPIB0::17::INSTR"
    
    print("\n⚠️  WARNING: This will execute an actual measurement!")
    print("This performs a single write+read or read-only measurement.")
    response = input("\nProceed? (yes/no): ").strip().lower()
    
    if response != 'yes':
        print("Test cancelled")
        return
    
    try:
        with Keithley4200A_KXCI(gpib_address=gpib_address) as keithley:
            # First measurement: write + read
            print("\n--- Measurement 1: Write + Read ---")
            result1 = keithley.pmu_retention_simple(
                riseTime=1e-7,
                writeVoltage=2.5,
                writeWidth=100e-6,
                readVoltage=0.5,
                readWidth=10e-6,
                readCount=3,
                v_range=2.0,
                IRange=1e-4,
                doWrite=1,
                ClariusDebug=0
            )
            
            if result1['success']:
                print(f"\n✓ Write+Read completed:")
                print(f"  Resistance: {result1['resistance']} Ω")
                print(f"  Current: {result1['current']} A")
                print(f"  Voltage: {result1['voltage']} V")
            
            time.sleep(1.0)  # Brief delay between measurements
            
            # Second measurement: read only
            print("\n--- Measurement 2: Read Only ---")
            result2 = keithley.pmu_retention_simple(
                riseTime=1e-7,
                writeVoltage=2.5,
                writeWidth=100e-6,
                readVoltage=0.5,
                readWidth=10e-6,
                readCount=3,
                v_range=2.0,
                IRange=1e-4,
                doWrite=0,  # No write, just read
                ClariusDebug=0
            )
            
            if result2['success']:
                print(f"\n✓ Read-only completed:")
                print(f"  Resistance: {result2['resistance']} Ω")
                print(f"  Current: {result2['current']} A")
                print(f"  Voltage: {result2['voltage']} V")
                
                if result1['success'] and result2['success']:
                    if result1['resistance'] and result2['resistance']:
                        delta = result2['resistance'] - result1['resistance']
                        delta_pct = (delta / result1['resistance'] * 100) if result1['resistance'] != 0 else 0
                        print(f"\nResistance change: {delta:.2e} Ω ({delta_pct:+.2f}%)")
            else:
                print(f"\n❌ Measurement 2 failed: {result2.get('error', 'Unknown error')}")
                
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()


def test_long_term_retention():
    """Test the long-term retention test function."""
    gpib_address = input("Enter GPIB address (default: GPIB0::17::INSTR): ").strip()
    if not gpib_address:
        gpib_address = "GPIB0::17::INSTR"
    
    print("\nLong-Term Retention Test Configuration:")
    print("This test will run for a specified duration, taking measurements at intervals.")
    print("Similar to chris_man_retention.c from keithley-memstress repository.")
    
    time_limit = input("Enter test duration in minutes (default: 5): ").strip()
    time_limit = float(time_limit) if time_limit else 5.0
    
    interval = input("Enter measurement interval in seconds (default: 10): ").strip()
    interval = float(interval) if interval else 10.0
    
    confirm = input(f"\nRun test for {time_limit} minutes with {interval}s intervals? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Cancelled.")
        return
    
    try:
        with Keithley4200A_KXCI(gpib_address=gpib_address) as keithley:
            result = keithley.long_term_retention_test(
                riseTime=1e-7,
                writeVoltage=2.5,
                writeWidth=100e-6,
                readVoltage=0.5,
                readWidth=10e-6,
                readCount=3,
                v_range=10.0,
                IRange=1e-4,
                time_limit_minutes=time_limit,
                measurement_interval_seconds=interval,
                initial_write=True,
                ClariusDebug=0
            )
            
            if result['success']:
                print("\n" + "="*60)
                print("LONG-TERM RETENTION TEST RESULTS")
                print("="*60)
                print(f"Total measurements: {result['measurement_count']}")
                print(f"Return value: {result['return_value']}")
                
                if result['resistance_history']:
                    print(f"\nResistance values over time:")
                    for i, (r, t) in enumerate(zip(result['resistance_history'][:20], result['time_history'][:20])):
                        if r is not None:
                            print(f"  [{i+1}] t={t/60:.2f} min: R={r:.6e} Ω")
                    if len(result['resistance_history']) > 20:
                        print(f"  ... ({len(result['resistance_history']) - 20} more measurements)")
            else:
                print(f"\n❌ Test failed: {result.get('error', 'Unknown error')}")
                
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
    ║   2. Test PMU_retention (actual measurement)                  ║
    ║   3. Test PMU_RetentionTest (new - full retention test)      ║
    ║   4. Test PMU_RetentionSimple (single measurement)           ║
    ║   5. Test Long-Term Retention (time-based, like chris_man)   ║
    ║   6. Test NVM reramSweep (IV characterization)               ║
    ║   7. Test NVM pundTest (PUND 4-pulse sequence)              ║
    ║   8. Test NVM reramStress (stress pulse test)               ║
    ║   9. Exit                                                     ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    choice = input("Enter choice (1-9): ").strip()
    
    if choice == "1":
        test_connection()
    elif choice == "2":
        test_pmu_retention()
    elif choice == "3":
        test_pmu_retention_test()
    elif choice == "4":
        test_pmu_retention_simple()
    elif choice == "5":
        test_long_term_retention()
    elif choice == "6":
        test_nvm_reram_sweep()
    elif choice == "7":
        test_nvm_pund_test()
    elif choice == "8":
        test_nvm_reram_stress()
    elif choice == "9":
        print("Exiting...")
    else:
        print("Invalid choice")


def test_nvm_reram_sweep():
    """Test NVM reramSweep function - IV characterization."""
    print("\n" + "="*60)
    print("Testing NVM reramSweep (IV Characterization)")
    print("="*60)
    
    gpib_address = input("Enter GPIB address (default: GPIB0::17::INSTR): ").strip()
    if not gpib_address:
        gpib_address = "GPIB0::17::INSTR"
    
    print("\n⚠️  WARNING: This will execute an actual measurement!")
    print("This performs a double sweep (reset + set pulse) for IV characterization.")
    response = input("\nProceed? (yes/no): ").strip().lower()
    
    if response != 'yes':
        print("Test cancelled")
        return
    
    try:
        with Keithley4200A_KXCI(gpib_address=gpib_address) as keithley:
            result = keithley.nvm_reram_sweep(
                riseTime=1e-4,
                widthTime=1e-6,
                delayTime=1e-4,
                complianceCH=2,
                resetV=-2.5,
                setV=2.5,
                Irange=1e-2,
                resetIcomp=0.0,
                setIcomp=1e-3,
                resTestV=0.5,
                takeRmeas=1,
                useSmu=0,
                numIter=1.0,
                Vforce_size=1000,
                Imeas_size=1000,
                Time_size=1000
            )
            
            if result['success']:
                print("\n" + "="*60)
                print("RESULTS")
                print("="*60)
                print(f"Return value: {result['return_value']}")
                print(f"Points: {result['pts']}")
                print(f"\nInitial Resistance: {result['initResistance']} Ω")
                print(f"Reset Resistance: {result['resetResistance']} Ω")
                print(f"Set Resistance: {result['setResistance']} Ω")
                print(f"\nVforce array: {len(result['Vforce'])} points")
                print(f"Imeas array: {len(result['Imeas'])} points")
                print(f"Time array: {len(result['Time'])} points")
                if len(result['Vforce']) > 0:
                    print(f"\nFirst 5 Vforce values: {result['Vforce'][:5]}")
                    print(f"First 5 Imeas values: {result['Imeas'][:5]}")
            else:
                print(f"\n❌ Measurement failed: {result.get('error', 'Unknown error')}")
                
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()


def test_nvm_pund_test():
    """Test NVM pundTest function - PUND 4-pulse sequence."""
    print("\n" + "="*60)
    print("Testing NVM pundTest (PUND 4-Pulse Sequence)")
    print("="*60)
    
    gpib_address = input("Enter GPIB address (default: GPIB0::17::INSTR): ").strip()
    if not gpib_address:
        gpib_address = "GPIB0::17::INSTR"
    
    print("\n⚠️  WARNING: This will execute an actual measurement!")
    print("This performs a PUND test (4 pulses: P, Pa, N, Na, D, Da) for FRAM.")
    response = input("\nProceed? (yes/no): ").strip().lower()
    
    if response != 'yes':
        print("Test cancelled")
        return
    
    try:
        with Keithley4200A_KXCI(gpib_address=gpib_address) as keithley:
            result = keithley.nvm_pund_test(
                Vp=3.3,
                tp=1e-6,
                td=1e-6,
                trf=1e-6,
                Irange1=1e-2,
                Irange2=1e-2,
                V_size=10000,
                I_size=10000,
                t_size=10000
            )
            
            if result['success']:
                print("\n" + "="*60)
                print("RESULTS")
                print("="*60)
                print(f"Return value: {result['return_value']}")
                print(f"Points: {result['pts']}")
                print(f"\nPolarization Values:")
                print(f"  P = {result['P']}")
                print(f"  Pa = {result['Pa']}")
                print(f"  U = {result['U']}")
                print(f"  Ua = {result['Ua']}")
                print(f"  N = {result['N']}")
                print(f"  Na = {result['Na']}")
                print(f"  D = {result['D']}")
                print(f"  Da = {result['Da']}")
                print(f"\nSwitching:")
                print(f"  Psw = {result['Psw']}")
                print(f"  Qsw = {result['Qsw']}")
                print(f"\nWaveform arrays:")
                print(f"  V: {len(result['V'])} points")
                print(f"  I: {len(result['I'])} points")
                print(f"  t: {len(result['t'])} points")
            else:
                print(f"\n❌ Measurement failed: {result.get('error', 'Unknown error')}")
                
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()


def test_nvm_reram_stress():
    """Test NVM reramStress function - stress pulse test."""
    print("\n" + "="*60)
    print("Testing NVM reramStress (Stress Pulse Test)")
    print("="*60)
    
    gpib_address = input("Enter GPIB address (default: GPIB0::17::INSTR): ").strip()
    if not gpib_address:
        gpib_address = "GPIB0::17::INSTR"
    
    print("\n⚠️  WARNING: This will execute an actual measurement!")
    print("This performs a single long stress pulse and measures resistance before/after.")
    response = input("\nProceed? (yes/no): ").strip().lower()
    
    if response != 'yes':
        print("Test cancelled")
        return
    
    try:
        with Keithley4200A_KXCI(gpib_address=gpib_address) as keithley:
            result = keithley.nvm_reram_stress(
                riseTime=1e-4,
                widthTime=1e-4,  # Can be up to 480s for long stress tests
                compCH=2,
                biasV=-2.5,
                Irange=1e-2,
                Icomp=0.0,
                resTestV=0.5,
                useSmu=0,
                Vforce_size=3000,
                Imeas_size=3000,
                Time_size=3000
            )
            
            if result['success']:
                print("\n" + "="*60)
                print("RESULTS")
                print("="*60)
                print(f"Return value: {result['return_value']}")
                print(f"Points: {result['pts']}")
                print(f"\nResistance before stress: {result['beforeRes']} Ω")
                print(f"Resistance after stress: {result['afterRes']} Ω")
                if result['beforeRes'] and result['afterRes']:
                    delta = result['afterRes'] - result['beforeRes']
                    delta_pct = (delta / result['beforeRes'] * 100) if result['beforeRes'] != 0 else 0
                    print(f"Change: {delta:.2e} Ω ({delta_pct:+.2f}%)")
                print(f"\nWaveform arrays:")
                print(f"  Vforce: {len(result['Vforce'])} points")
                print(f"  Imeas: {len(result['Imeas'])} points")
                print(f"  Time: {len(result['Time'])} points")
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

