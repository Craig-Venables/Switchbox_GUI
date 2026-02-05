"""
Test script for Oxxius laser ms-scale pulsing.
Run this to verify pulse_on_ms and pulse_train (e.g. before using Optical tab in Pulse Testing GUI).

Usage:
  python test_oxxius_pulse.py [COM_PORT] [BAUD]
  e.g. python test_oxxius_pulse.py COM4 19200

Defaults: COM4, 19200
"""

import sys
import time
from pathlib import Path

# Allow importing oxxius from same package
_here = Path(__file__).resolve().parent
if str(_here.parent.parent) not in sys.path:
    sys.path.insert(0, str(_here.parent.parent))

from Equipment.Laser_Controller.oxxius import OxxiusLaser


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else "COM4"
    baud = int(sys.argv[2]) if len(sys.argv) > 2 else 19200

    print("=" * 50)
    print("Oxxius laser pulse test")
    print("=" * 50)
    print(f"Port: {port}, Baud: {baud}")
    print()

    laser = OxxiusLaser(port=port, baud=baud)
    try:
        idn = laser.idn()
        print(f"Laser: {idn}")
        print()

        # Single pulse: 100 ms on
        print("1. Single pulse: 100 ms on...")
        t0 = time.perf_counter()
        laser.pulse_on_ms(100)
        t1 = time.perf_counter()
        print(f"   Done in {(t1 - t0) * 1000:.0f} ms")
        print()

        # Short pause
        time.sleep(0.5)

        # Pulse train: 5 pulses, 100 ms on, 200 ms off
        n_pulses = 5
        on_ms = 100
        off_ms = 200
        print(f"2. Pulse train: {n_pulses} pulses, {on_ms} ms on, {off_ms} ms off...")
        t0 = time.perf_counter()
        laser.pulse_train(n_pulses, on_ms, off_ms)
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
