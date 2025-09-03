#
# Moku:Go Fast Pulse Generator (Built-in Pulse Waveform)
#
# Purpose:
# - Drive sharp pulses using the hardware Pulse generator for fastest edges
# - Simple controls: voltage (high level), pulse width, period, edge time
# - Optional time-limited run for short bursts; otherwise runs until Ctrl+C
#
# Notes:
# - Baseline is 0 V and high level is VOLTAGE_HIGH (using amplitude/offset mapping)
# - EDGE_TIME is clamped to device minimums where relevant (e.g., ~16 ns)
# - Frequency = 1 / PULSE_PERIOD; duty = PULSE_WIDTH / PULSE_PERIOD
#
# (c) 2024
#

from __future__ import annotations

import time
import argparse
from typing import Optional

from moku.instruments import WaveformGenerator


def clamp(value: float, minimum: Optional[float] = None, maximum: Optional[float] = None) -> float:
    if minimum is not None and value < minimum:
        return minimum
    if maximum is not None and value > maximum:
        return maximum
    return value


def run_fast_pulse(
    moku_ip: str,
    voltage_high: float,
    pulse_width: float,
    pulse_period: float,
    edge_time: float,
    channel: int = 1,
    run_seconds: Optional[float] = None,
) -> None:
    """
    Configure and run the built-in Pulse generator for fastest possible edges.
    Baseline is 0 V, high level is voltage_high.
    """

    if pulse_period <= 0:
        raise ValueError("pulse_period must be > 0")
    if pulse_width <= 0:
        raise ValueError("pulse_width must be > 0")
    if pulse_width >= pulse_period:
        raise ValueError("pulse_width must be smaller than pulse_period")
    if channel not in (1, 2):
        raise ValueError("channel must be 1 or 2")

    # Moku:Go typical minimum edge time ~16 ns; allow user override but clamp
    min_edge_time = 16e-9
    edge_time = clamp(edge_time, minimum=min_edge_time)

    frequency_hz = 1.0 / pulse_period
    duty = pulse_width / pulse_period

    amplitude = voltage_high
    offset = voltage_high / 2.0

    print("🔧 Moku:Go Fast Pulse Generator")
    print("=" * 48)
    print(f"Target IP: {moku_ip}")
    print(f"Channel: {channel}")
    print(f"High Voltage: {voltage_high:.3f} V")
    print(f"Pulse Width: {pulse_width*1e9:.1f} ns")
    print(f"Pulse Period: {pulse_period*1e9:.1f} ns")
    print(f"Frequency: {frequency_hz/1e6:.3f} MHz")
    print(f"Duty: {duty*100:.2f} %")
    print(f"Edge Time: {edge_time*1e9:.1f} ns (clamped to min)")
    if run_seconds is not None:
        print(f"Run Duration: {run_seconds:.3f} s")
    print()

    # Connect and configure
    try:
        wg = WaveformGenerator(moku_ip, force_connect=True, connect_timeout=10)
        print("✅ Connected to WaveformGenerator")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return

    try:
        wg.generate_waveform(
            channel=channel,
            type='Pulse',
            amplitude=amplitude,
            frequency=frequency_hz,
            offset=offset,
            pulse_width=pulse_width,
            edge_time=edge_time,
        )
        wg.enable_output(channel, enable=True)
        print("✅ Pulse output enabled")
        print("   Press Ctrl+C to stop" if run_seconds is None else "   Running for set duration...")

        if run_seconds is None:
            # Continuous until interrupted
            try:
                while True:
                    time.sleep(0.25)
            except KeyboardInterrupt:
                print("\n🛑 Stopping pulse output...")
        else:
            time.sleep(max(0.0, run_seconds))
            print("🛑 Time elapsed; stopping pulse output...")

    except Exception as e:
        print(f"❌ Configuration or runtime error: {e}")
    finally:
        try:
            wg.enable_output(channel, enable=False)
            print("✅ Output disabled. Safe to disconnect.")
        except Exception:
            pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Moku:Go Fast Pulse Generator")
    parser.add_argument("--ip", dest="ip", type=str, required=False, default="192.168.0.45", help="Moku:Go IP address (default: 192.168.0.45)")
    parser.add_argument("--voltage", dest="voltage", type=float, default=1.0, help="High voltage level (V)")
    parser.add_argument("--width", dest="width", type=float, default=100e-9, help="Pulse width (s)")
    parser.add_argument("--period", dest="period", type=float, default=200e-9, help="Pulse period (s)")
    parser.add_argument("--edge", dest="edge", type=float, default=16e-9, help="Edge time (s)")
    parser.add_argument("--channel", dest="channel", type=int, default=1, help="Output channel (1 or 2)")
    parser.add_argument("--seconds", dest="seconds", type=float, default=None, help="Run duration in seconds; omit for continuous")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_fast_pulse(
        moku_ip=args.ip,
        voltage_high=args.voltage,
        pulse_width=args.width,
        pulse_period=args.period,
        edge_time=args.edge,
        channel=args.channel,
        run_seconds=args.seconds,
    )


if __name__ == "__main__":
    main()


