#!/usr/bin/env python3
"""
Quick test script for Keithley4200A_PMUController
"""

import time
import sys
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Equipment_Classes.SMU.Keithley4200A import Keithley4200A_PMUController


def test_pmu_controller():
    """Test basic PMU functionality."""
    # Use a dummy address for testing - replace with actual IP
    address = "192.168.0.10:8888|PMU1-CH1"

    print(f"Testing Keithley4200A_PMUController at {address}")
    print("=" * 50)

    try:
        # Initialize PMU controller
        print("1. Initializing PMU controller...")
        pmu = Keithley4200A_PMUController(address)
        print("   ✓ Connected successfully")

        # Configure a pulse sequence (similar to example)
        print("2. Configuring pulse sequence...")
        pmu.configure_pulse(
            v_src_range=10.0,      # Voltage source range
            v_meas_range_type=0,   # Auto range
            v_meas_range=10.0,     # Voltage measurement range
            i_meas_range_type=0,   # Auto range
            i_meas_range=0.2,      # Current measurement range
            v_limit=5.0,           # Voltage compliance
            i_limit=1.0,           # Current compliance
            power_limit=10.0,      # Power limit
            start_pct=0.2,         # Measurement start percentage
            stop_pct=0.8,          # Measurement stop percentage
            num_pulses=4,          # Multiple pulses for better test
            period=20e-6,          # Pulse period (20μs)
            delay=1e-7,            # Delay (100ns)
            width=10e-6,           # Pulse width (10μs)
            rise=1e-7,             # Rise time (100ns)
            fall=1e-7,             # Fall time (100ns)
            load_ohm=1e6           # Load impedance (1MΩ)
        )
        print("   ✓ Pulse sequence configured")

        # Test pulse sweep execution
        print("3. Testing pulse sweep execution...")
        start_voltage = 1.0  # Start at 1V
        stop_voltage = 2.0   # End at 2V
        step_voltage = 0.25  # 0.25V steps

        print(f"   Setting up voltage sweep: {start_voltage}V to {stop_voltage}V")

        # Configure linear sweep instead of single pulse
        pmu.lpt.pulse_sweep_linear(
            pmu._card_id,
            pmu._chan,
            pmu.param.PULSE_AMPLITUDE_SP,
            start_voltage,
            stop_voltage,
            step_voltage
        )

        # Enable output
        pmu.output(True)
        print("   ✓ Output enabled")

        # Execute and fetch results
        print("   Executing pulse sweep...")
        voltages, currents, timestamps, statuses = pmu.exec_and_fetch()

        print("   ✓ Pulse sweep executed successfully")
        print("   Results:")
        print(f"     - Data points: {len(voltages)}")

        if voltages and currents:
            # Decode status codes
            decoded_statuses = [pmu.lpt.decode_pulse_status(status) for status in statuses]

            print(f"     - Voltage measurements: {len([v for v in voltages if v is not None])} valid")
            print(f"     - Current measurements: {len([i for i in currents if i is not None])} valid")
            print(f"     - Timestamps: {len([t for t in timestamps if t is not None])} valid")
            print(f"     - Status codes: {set(statuses)}")

            # Show first few data points
            print("     - First few data points:")
            for i in range(min(5, len(voltages))):
                if voltages[i] is not None and currents[i] is not None:
                    print(".6f")

            # Check for any status issues
            status_issues = [s for s in decoded_statuses if s != 'N']  # 'N' = Normal
            if status_issues:
                print(f"     ⚠ Status issues detected: {status_issues}")
            else:
                print("     ✓ All measurements completed normally")

        # Test output control
        print("4. Testing output control...")
        pmu.output(False)
        print("   ✓ Output disabled")

        # Close connection
        print("5. Closing connection...")
        pmu.close()
        print("   ✓ Connection closed")

        print("\n" + "=" * 50)
        print("✓ All tests completed successfully!")

    except Exception as e:
        print(f"✗ Test failed with error: {e}")
        print("Make sure:")
        print("  - The 4200A is connected and powered on")
        print("  - The IP address is correct")
        print("  - The LPT server is running on the 4200A")
        print("  - PMU1-CH1 is available and properly configured")
        return False

    return True


if __name__ == "__main__":
    success = test_pmu_controller()
    sys.exit(0 if success else 1)
