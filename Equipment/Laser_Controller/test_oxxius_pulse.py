"""
Test script for Oxxius laser ms-scale pulsing.
Run this to verify pulse_on_ms and pulse_train (e.g. before using Optical tab in Pulse Testing GUI).
Uses software power control (mW) for the pulses, then restores manual control on exit.

Usage:
  python test_oxxius_pulse.py [COM_PORT] [BAUD] [POWER_MW]
  python test_oxxius_pulse.py --timing [COM_PORT] [BAUD] [POWER_MW]   # find shortest pulse

Defaults: COM4, 19200, power 10 mW
"""

import sys
import time
from pathlib import Path

# Allow importing oxxius from same package
_here = Path(__file__).resolve().parent
if str(_here.parent.parent) not in sys.path:
    sys.path.insert(0, str(_here.parent.parent))

from Equipment.Laser_Controller.oxxius import OxxiusLaser


def run_timing_test(laser, power_mw, n_samples=3):
    """
    Measure serial overhead and try progressively shorter pulses to find
    the shortest usable pulse. All times in ms.
    """
    print("=" * 60)
    print("Minimum pulse timing test (serial-limited)")
    print("=" * 60)

    # 1) Overhead: time for emission_on() + emission_off() with zero delay (no sleep)
    print("\n1. Serial overhead (on + off with 0 ms delay)...")
    times = []
    for _ in range(n_samples):
        t0 = time.perf_counter()
        laser.emission_on()
        laser.emission_off()
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000)
    overhead_ms = sum(times) / len(times)
    print(f"   Mean: {overhead_ms:.1f} ms  (samples: {[f'{t:.1f}' for t in times]})")
    print(f"   -> Shortest cycle (on+off) is ~{overhead_ms:.0f} ms; use on-times >> this for accurate pulses.")
    time.sleep(0.3)

    # 2) Requested vs actual total time for various on-durations
    print("\n2. Requested on-time vs total elapsed (requested + overhead):")
    print("   {:>10} {:>12} {:>10}".format("Requested", "Total", "Overhead"))
    print("   {:>10} {:>12} {:>10}".format("(ms)", "(ms)", "(ms)"))
    print("   " + "-" * 34)

    test_durations_ms = [50, 20, 10, 5, 2, 1]
    for req_ms in test_durations_ms:
        t0 = time.perf_counter()
        laser.pulse_on_ms(req_ms)
        t1 = time.perf_counter()
        total_ms = (t1 - t0) * 1000
        extra = total_ms - req_ms
        print("   {:>10.1f} {:>12.1f} {:>10.1f}".format(req_ms, total_ms, extra))
        time.sleep(0.2)

    print()
    print("Summary:")
    print(f"  - Serial overhead ~{overhead_ms:.0f} ms per on/off cycle.")
    print(f"  - For reliable pulse length, use on-time >= ~{max(20, overhead_ms * 2):.0f} ms.")
    print("  - For shorter pulses, use the laser TTL input (hardware modulation).")
    print("=" * 60)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    do_timing = "--timing" in sys.argv

    port = args[0] if len(args) > 0 else "COM4"
    baud = int(args[1]) if len(args) > 1 else 19200
    power_mw = float(args[2]) if len(args) > 2 else 10.0

    print("=" * 50)
    print("Oxxius laser pulse test")
    print("=" * 50)
    print(f"Port: {port}, Baud: {baud}, Power: {power_mw} mW")
    if do_timing:
        print("Mode: timing test (find shortest pulse)")
    print()

    laser = OxxiusLaser(port=port, baud=baud)
    try:
        idn = laser.idn()
        print(f"Laser: {idn}")
        print()

        # Switch to software/digital power control so set_power() is used
        print(f"Setting to software power control at {power_mw} mW...")
        laser.set_to_digital_power_control(power_mw)
        print(f"   Power: {laser.get_power()}")
        print()

        if do_timing:
            run_timing_test(laser, power_mw)
            return

        # Single pulse: 100 ms on at power_mw
        print(f"1. Single pulse: 100 ms on @ {power_mw} mW...")
        t0 = time.perf_counter()
        laser.pulse_on_ms(100)
        t1 = time.perf_counter()
        print(f"   Done in {(t1 - t0) * 1000:.0f} ms")
        print()

        # Short pause
        time.sleep(0.5)

        # Pulse train: 5 pulses, 100 ms on, 200 ms off at power_mw
        n_pulses = 5
        on_ms = 100
        off_ms = 200
        print(f"2. Pulse train: {n_pulses} pulses, {on_ms} ms on, {off_ms} ms off @ {power_mw} mW...")
        t0 = time.perf_counter()
        laser.pulse_train(n_pulses, on_ms, off_ms, power_mw=power_mw)
        t1 = time.perf_counter()
        print(f"   Done in {(t1 - t0) * 1000:.0f} ms (expected ~{n_pulses * (on_ms + off_ms) - off_ms} ms)")
        print()

        print("=" * 50)
        print("Pulse test finished successfully.")
        print("=" * 50)
    finally:
        laser.close(restore_to_manual_control=True)
        print("Laser connection closed, restored to manual control.")


if __name__ == "__main__":
    main()
