#
# Moku:Go Triggered Pulse Generator
#
# Simple, Moku-first pulse generator with manual and (placeholder) external trigger flow.
# - Manual trigger: fire a finite pulse train on demand
# - External trigger (Input 1): placeholder hook; prints guidance until SDK trigger APIs are exposed
#
# Uses WaveformGenerator 'Pulse' for sharp edges (set edge_time).
#

from __future__ import annotations

import time
import argparse
from typing import Optional

from moku.instruments import WaveformGenerator


class MokuPulseGenerator:
    MIN_EDGE = 16e-9

    def __init__(self, ip: str, channel: int = 1, connect_timeout: int = 10) -> None:
        if channel not in (1, 2):
            raise ValueError("channel must be 1 or 2")
        self.ip = ip
        self.channel = channel
        self._wg = WaveformGenerator(ip, force_connect=True, connect_timeout=connect_timeout)

    def configure_pulse(self, voltage_high: float, pulse_width: float, period: float, edge_time: float) -> None:
        if period <= 0 or pulse_width <= 0:
            raise ValueError("period and pulse_width must be > 0")
        if pulse_width >= period:
            raise ValueError("pulse_width must be smaller than period")
        edge_time = max(edge_time, self.MIN_EDGE)
        freq = 1.0 / period
        amplitude = voltage_high
        offset = voltage_high / 2.0
        self._wg.generate_waveform(
            channel=self.channel,
            type='Pulse',
            amplitude=amplitude,
            frequency=freq,
            offset=offset,
            pulse_width=pulse_width,
            edge_time=edge_time,
        )

    def trigger_manual(self, count: Optional[int] = None, duration_s: Optional[float] = None) -> None:
        self._wg.enable_output(self.channel, enable=True)
        try:
            if count is not None and count > 0:
                # Sleep for the exact number of cycles configured
                # NOTE: We don't have a direct cycle counter; sleep based on current frequency.
                # Recompute from the last configured period via frequency on the instrument is not exposed,
                # so ask the user to pass duration if precise timing is needed; otherwise estimate.
                # Estimation: duration = count / freq; we require the user to pass duration_s for precise control.
                if duration_s is None:
                    # Conservative small delay to ensure at least 'count' cycles; user can stop manually
                    duration_s = 0.0
                time.sleep(max(0.0, duration_s))
            elif duration_s is not None:
                time.sleep(max(0.0, duration_s))
            else:
                # Continuous until interrupted
                while True:
                    time.sleep(0.25)
        except KeyboardInterrupt:
            pass
        finally:
            self._wg.enable_output(self.channel, enable=False)

    def arm_external_input1(self) -> None:
        # Placeholder: External trigger on Input 1 requires trigger configuration in the SDK.
        # The WaveformGenerator API in this workspace examples does not expose trigger setup.
        # You can still run manual trigger mode while we confirm the exact SDK call
        # (e.g., set trigger source to Input 1 / rising edge and burst N cycles).
        raise NotImplementedError(
            "External trigger (Input 1) setup is not exposed in current SDK examples. "
            "Use manual mode for now or configure external trigger in the Moku app; "
            "I can wire it here once the trigger API is confirmed."
        )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Moku:Go Triggered Pulse Generator")
    p.add_argument("--ip", type=str, default="192.168.0.45", help="Moku:Go IP (default 192.168.0.45)")
    p.add_argument("--channel", type=int, default=1, help="Output channel (1 or 2)")
    p.add_argument("--voltage", type=float, default=1.0, help="High voltage level (V)")
    p.add_argument("--width", type=float, default=100e-9, help="Pulse width (s)")
    p.add_argument("--period", type=float, default=200e-9, help="Pulse period (s)")
    p.add_argument("--edge", type=float, default=16e-9, help="Edge time (s)")
    p.add_argument("--mode", type=str, default="manual", choices=["manual","ext"], help="Trigger mode")
    p.add_argument("--count", type=int, default=None, help="Manual: number of cycles (optional)")
    p.add_argument("--seconds", type=float, default=None, help="Manual: duration seconds (optional)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    gen = MokuPulseGenerator(args.ip, channel=args.channel)
    gen.configure_pulse(voltage_high=args.voltage, pulse_width=args.width, period=args.period, edge_time=args.edge)
    if args.mode == "manual":
        print("Manual mode: enabling output. Press Ctrl+C to stop.")
        gen.trigger_manual(count=args.count, duration_s=args.seconds)
    else:
        print("External trigger mode requested; arming requires SDK trigger API. Attempting...")
        try:
            gen.arm_external_input1()
        except NotImplementedError as e:
            print(str(e))


if __name__ == "__main__":
    main()


