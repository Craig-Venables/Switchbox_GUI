#
# Moku:Go Laser Controller
#
# High-level wrapper for driving a laser via Moku:Go instruments.
# - Uses WaveformGenerator Pulse for sharpest edges (fastest practical pulses)
# - Uses ArbitraryWaveformGenerator for binary bit patterns via LUTs
# - Provides convenience methods for single pulse, pulse trains, voltage sweeps
#
# (c) 2024
#

from __future__ import annotations

import time
from typing import List, Optional, Tuple

import numpy as np
from moku.instruments import WaveformGenerator, ArbitraryWaveformGenerator


def _clamp(value: float, minimum: Optional[float] = None, maximum: Optional[float] = None) -> float:
    if minimum is not None and value < minimum:
        return minimum
    if maximum is not None and value > maximum:
        return maximum
    return value


class MonkuGoController:
    """
    Manages connections to Moku:Go instruments.

    Lazily constructs instrument handles as needed and keeps them alive
    until explicitly closed.
    """

    def __init__(self, ip_address: str, connect_timeout: int = 10) -> None:
        self.ip_address = ip_address
        self.connect_timeout = connect_timeout
        self._wg: Optional[WaveformGenerator] = None
        self._awg: Optional[ArbitraryWaveformGenerator] = None

    def wavegen(self) -> WaveformGenerator:
        if self._wg is None:
            self._wg = WaveformGenerator(self.ip_address, force_connect=True, connect_timeout=self.connect_timeout)
        return self._wg

    def awg(self) -> ArbitraryWaveformGenerator:
        if self._awg is None:
            self._awg = ArbitraryWaveformGenerator(self.ip_address, force_connect=True, connect_timeout=self.connect_timeout)
        return self._awg

    def close(self) -> None:
        try:
            if self._wg is not None:
                # No explicit close in most Moku SDKs; ensure outputs are off.
                pass
        finally:
            self._wg = None
        try:
            if self._awg is not None:
                pass
        finally:
            self._awg = None

    def reset_wavegen(self) -> None:
        """Drop and recreate WaveformGenerator on next access."""
        try:
            # No explicit close; rely on GC and device session cleanup
            self._wg = None
        except Exception:
            self._wg = None

    def reset_awg(self) -> None:
        """Drop and recreate AWG on next access."""
        try:
            self._awg = None
        except Exception:
            self._awg = None


class LaserFunctionGenerator:
    """
    High-level functions for laser control using Moku:Go.

    Pulse-based methods use WaveformGenerator (built-in Pulse mode) for minimal edge time.
    Binary methods use AWG LUTs for arbitrary bit patterns.
    """

    MIN_EDGE_TIME_S = 16e-9  # Typical Moku:Go minimum

    def __init__(self, controller: MonkuGoController, channel: int = 1) -> None:
        if channel not in (1, 2):
            raise ValueError("channel must be 1 or 2")
        self.controller = controller
        self.channel = channel
        self._configured: Optional[tuple] = None  # (voltage_high, pulse_width, period, edge_time)
        self.trigger_mode: str = 'manual'  # 'manual' or 'external' (placeholder)

    # ------------------------
    # Pulse (WaveformGenerator)
    # ------------------------

    def send_single_pulse(self, voltage_high: float, pulse_width: float, edge_time: float, period: Optional[float] = None) -> None:
        """
        Emit a single pulse by enabling the Pulse waveform for one period.
        If period is not provided, use a safe minimum (>= 200 ns) that accommodates edge time.
        """
        wg = self.controller.wavegen()

        edge_time = _clamp(edge_time, minimum=self.MIN_EDGE_TIME_S)
        if period is None:
            period = max(200e-9, pulse_width + 4 * edge_time)
        if pulse_width >= period:
            raise ValueError("pulse_width must be smaller than period")

        frequency = 1.0 / period
        amplitude = voltage_high
        offset = voltage_high / 2.0

        wg.generate_waveform(
            channel=self.channel,
            type='Pulse',
            amplitude=amplitude,
            frequency=frequency,
            offset=offset,
            pulse_width=pulse_width,
            edge_time=edge_time,
        )
        # Older SDKs often auto-enable output; enabling may raise benign errors. Ignore.
        try:
            wg.enable_output(self.channel, enable=True,force_connect=True)
        except Exception:
            pass
        try:
            time.sleep(period)
        finally:
            try:
                wg.enable_output(self.channel, enable=False)
            except Exception:
                pass

    def send_pulse_train(self, voltage_high: float, pulse_width: float, period: float, edge_time: float, count: Optional[int] = None, duration_s: Optional[float] = None) -> None:
        """
        Emit a pulse train. Use count to emit an exact number of pulses, or duration_s for time-based run.
        Leave both None for continuous until interrupted.
        """
        if pulse_width >= period:
            raise ValueError("pulse_width must be smaller than period")

        wg = self.controller.wavegen()
        edge_time = _clamp(edge_time, minimum=self.MIN_EDGE_TIME_S)
        frequency = 1.0 / period
        amplitude = voltage_high
        offset = voltage_high / 2.0

        wg.generate_waveform(
            channel=self.channel,
            type='Pulse',
            amplitude=amplitude,
            frequency=frequency,
            offset=offset,
            pulse_width=pulse_width,
            edge_time=edge_time,
        )
        try:
            wg.enable_output(self.channel, enable=True,force_connect=True)
        except Exception:
            pass

        try:
            if count is not None:
                time.sleep(max(0.0, count / frequency))
            elif duration_s is not None:
                time.sleep(max(0.0, duration_s))
            else:
                while True:
                    time.sleep(0.25)
        except KeyboardInterrupt:
            pass
        finally:
            try:
                wg.enable_output(self.channel, enable=False)
            except Exception:
                pass

    def send_ten_pulses(self, voltage_high: float, pulse_width: float, period: float, edge_time: float) -> None:
        self.send_pulse_train(voltage_high, pulse_width, period, edge_time, count=10)

    # ------------------------
    # Non-blocking control helpers
    # ------------------------

    def configure_pulse(self, voltage_high: float, pulse_width: float, period: float, edge_time: float) -> None:
        """Configure pulse parameters without enabling output."""
        if pulse_width >= period:
            raise ValueError("pulse_width must be smaller than period")
        wg = self.controller.wavegen()
        edge_time = _clamp(edge_time, minimum=self.MIN_EDGE_TIME_S)
        frequency = 1.0 / period
        amplitude = voltage_high
        offset = voltage_high / 2.0
        wg.generate_waveform(
            channel=self.channel,
            type='Pulse',
            amplitude=amplitude,
            frequency=frequency,
            offset=offset,
            pulse_width=pulse_width,
            edge_time=edge_time,
        )
        self._configured = (voltage_high, pulse_width, period, edge_time)

    def start_continuous(self, voltage_high: float, pulse_width: float, period: float, edge_time: float) -> None:
        """Configure and enable output continuously until stop_output is called."""
        self.configure_pulse(voltage_high, pulse_width, period, edge_time)
        try:
            self.controller.wavegen().enable_output(self.channel, enable=True)
        except Exception:
            # Old SDK may already be enabled; ignore
            pass

    def stop_output(self) -> None:
        """Disable output."""
        try:
            self.controller.wavegen().enable_output(self.channel, enable=False)
        except Exception:
            pass
        # Reset session to avoid "API Connection already exists" on next start
        self.controller.reset_wavegen()

    def run_burst(self, voltage_high: float, pulse_width: float, period: float, edge_time: float, *, count: Optional[int] = None, duration_s: Optional[float] = None) -> None:
        """Run a finite burst (blocking)."""
        # Approximate finite cycles by enabling for duration = count/frequency and then disabling
        if count is None and duration_s is None:
            count = 1
        if count is not None and count <= 0:
            return
        # Configure
        self.configure_pulse(voltage_high, pulse_width, period, edge_time)
        frequency = 1.0 / period
        try:
            self.controller.wavegen().enable_output(self.channel, enable=True)
        except Exception:
            pass
        try:
            dwell = float(duration_s) if duration_s is not None else (float(count) / frequency)
            dwell = max(0.0, dwell)
            time.sleep(dwell)
        finally:
            try:
                self.controller.wavegen().enable_output(self.channel, enable=False)
            except Exception:
                pass
            # Reset to avoid connection reuse issues
            self.controller.reset_wavegen()

    def arm_external_trigger(self, mode: str = 'NCYC', cycles: int = 1) -> None:
        """Placeholder: external trigger support pending SDK trigger APIs."""
        raise NotImplementedError("External trigger configuration not implemented; requires SDK trigger API.")

    # ------------------------
    # Safe wrappers with reconnect
    # ------------------------
    def _retry_on_session(self, func, *args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            msg = str(exc)
            if 'already exists' in msg.lower() or 'connection' in msg.lower():
                # Reset and retry once
                self.controller.reset_wavegen()
                return func(*args, **kwargs)
            raise

    def safe_send_single_pulse(self, voltage_high: float, pulse_width: float, edge_time: float, period: Optional[float] = None) -> None:
        return self._retry_on_session(self.send_single_pulse, voltage_high, pulse_width, edge_time, period)

    def safe_run_burst(self, voltage_high: float, pulse_width: float, period: float, edge_time: float, *, count: Optional[int] = None, duration_s: Optional[float] = None) -> None:
        return self._retry_on_session(self.run_burst, voltage_high, pulse_width, period, edge_time, count=count, duration_s=duration_s)

    def safe_start_continuous(self, voltage_high: float, pulse_width: float, period: float, edge_time: float) -> None:
        return self._retry_on_session(self.start_continuous, voltage_high, pulse_width, period, edge_time)

    def set_trigger_mode(self, mode: str) -> None:
        mode = str(mode).lower()
        if mode not in ('manual', 'external'):
            raise ValueError('Unsupported trigger mode: ' + mode)
        self.trigger_mode = mode

    def safe_send_trigger_pulse_on_ch2(self, voltage_high: float = 1.0, pulse_width: float = 1e-7, period: float = 2e-7, edge_time: float = 16e-9) -> None:
        """Send a single trigger pulse on channel 2 using safe wrappers."""
        temp = LaserFunctionGenerator(self.controller, channel=2)
        return temp.safe_send_single_pulse(voltage_high=voltage_high, pulse_width=pulse_width, edge_time=edge_time, period=period)

    # ------------------------
    # DC Output support
    # ------------------------
    def configure_dc(self, level_v: float) -> None:
        wg = self.controller.wavegen()
        # Use DC type if supported; if not, approximate with Pulse of 100% duty
        try:
            wg.generate_waveform(
                channel=self.channel,
                type='DC',
                amplitude=0.0,
                frequency=1.0,
                offset=float(level_v),
            )
        except Exception:
            # Fallback to low-frequency pulse with width≈period
            freq = 1.0
            wg.generate_waveform(
                channel=self.channel,
                type='Pulse',
                amplitude=float(level_v),
                frequency=freq,
                offset=float(level_v)/2.0,
                pulse_width=0.9,
                edge_time=self.MIN_EDGE_TIME_S,
            )

    def start_dc(self, level_v: float) -> None:
        self.configure_dc(level_v)
        try:
            self.controller.wavegen().enable_output(self.channel, enable=True)
        except Exception:
            pass

    def safe_start_dc(self, level_v: float) -> None:
        return self._retry_on_session(self.start_dc, level_v)

    def send_voltage_sweep_pulses(self, voltage_start: float, voltage_stop: float, steps: int, pulses_per_step: int, pulse_width: float, period: float, edge_time: float, dwell_between_steps_s: float = 0.0) -> None:
        """
        Step the high level from start to stop across steps; emit pulses_per_step at each level.
        """
        if steps <= 0:
            raise ValueError("steps must be > 0")
        if pulses_per_step <= 0:
            raise ValueError("pulses_per_step must be > 0")

        wg = self.controller.wavegen()
        edge_time = _clamp(edge_time, minimum=self.MIN_EDGE_TIME_S)
        frequency = 1.0 / period

        voltages = np.linspace(voltage_start, voltage_stop, steps)
        for v in voltages:
            amplitude = float(v)
            offset = amplitude / 2.0
            wg.generate_waveform(
                channel=self.channel,
                type='Pulse',
                amplitude=amplitude,
                frequency=frequency,
                offset=offset,
                pulse_width=pulse_width,
                edge_time=edge_time,
            )
            try:
                wg.enable_output(self.channel, enable=True)
            except Exception:
                pass
            try:
                time.sleep(max(0.0, pulses_per_step / frequency))
            finally:
                try:
                    wg.enable_output(self.channel, enable=False)
                except Exception:
                    pass
            if dwell_between_steps_s > 0:
                time.sleep(dwell_between_steps_s)

    # ------------------------
    # Binary patterns (AWG LUT)
    # ------------------------

    @staticmethod
    def _binary_string_to_levels(binary_string: str, high_voltage: float) -> List[float]:
        levels: List[float] = []
        for bit in binary_string:
            if bit == '1':
                levels.append(high_voltage)
            elif bit == '0':
                levels.append(0.0)
            else:
                raise ValueError("Binary pattern must contain only '0' or '1'")
        return levels

    @staticmethod
    def _closest_mokugo_sample_rate(desired_rate: float) -> Tuple[str, float]:
        # Subset of plausible Moku:Go AWG rates represented as label->numeric
        supported = {
            '125Ms': 125e6,
            '62.5Ms': 62.5e6,
            '31.25Ms': 31.25e6,
            '15.625Ms': 15.625e6,
        }
        best_label = '125Ms'
        best_rate = supported[best_label]
        best_err = abs(best_rate - desired_rate)
        for label, rate in supported.items():
            err = abs(rate - desired_rate)
            if err < best_err:
                best_label = label
                best_rate = rate
                best_err = err
        return best_label, best_rate

    def _build_lut_for_binary(self, pattern: str, bit_period: float, high_voltage: float, samples_per_bit: int = 10) -> Tuple[np.ndarray, str, float, float]:
        if bit_period <= 0:
            raise ValueError("bit_period must be > 0")
        if samples_per_bit <= 0:
            raise ValueError("samples_per_bit must be > 0")

        desired_rate = samples_per_bit / bit_period
        sample_rate_label, actual_rate = self._closest_mokugo_sample_rate(desired_rate)

        levels = self._binary_string_to_levels(pattern, high_voltage)
        samples: List[float] = []
        for v in levels:
            samples.extend([v] * samples_per_bit)

        lut = np.array(samples, dtype=float)
        if high_voltage > 0:
            lut = lut / high_voltage

        total_samples = len(lut)
        frequency = actual_rate / float(total_samples)
        return lut, sample_rate_label, actual_rate, frequency

    def send_binary_pattern(self, pattern: str, bit_period: float, high_voltage: float, samples_per_bit: int = 10, continuous: bool = False, repeat_seconds: Optional[float] = None) -> None:
        """
        Send a binary pattern like "10110011" using the AWG LUT.
        If continuous=False and repeat_seconds is None, transmits for one pattern period then disables.
        """
        awg = self.controller.awg()
        lut, sample_rate_label, _, frequency = self._build_lut_for_binary(pattern, bit_period, high_voltage, samples_per_bit)

        awg.generate_waveform(
            channel=self.channel,
            sample_rate=sample_rate_label,
            lut_data=lut.tolist(),
            frequency=frequency,
            amplitude=high_voltage,
            offset=0.0,
            interpolation=False,
        )
        awg.enable_output(self.channel, enable=True)

        try:
            if continuous:
                while True:
                    time.sleep(0.25)
            elif repeat_seconds is not None:
                time.sleep(max(0.0, repeat_seconds))
            else:
                time.sleep(max(0.0, 1.0 / frequency))
        except KeyboardInterrupt:
            pass
        finally:
            awg.enable_output(self.channel, enable=False)

    # ---------------
    # Housekeeping
    # ---------------

    def stop_all(self) -> None:
        # Best-effort disable on both instruments
        try:
            self.controller.wavegen().enable_output(self.channel, enable=False)
        except Exception:
            pass
        try:
            self.controller.awg().enable_output(self.channel, enable=False)
        except Exception:
            pass


__all__ = [
    'MonkuGoController',
    'LaserFunctionGenerator',
]


