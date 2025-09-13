# PMUDualChannelSweeps.py
# Minimal helper class for configuring common PMU sweeps on a dual-channel PMU (4225-PMU)
# Style follows your Keithley4200A_PMUDualChannel (Proxy lpt/param objects).
#
# Notes:
#  - This assumes the Proxy API you already use (self.lpt, self.param) exposes the LPT calls
#    named the same as the LPT library: pulse_sweep_linear, pulse_period, pulse_width, pulse_vlow,
#    pulse_vhigh, pulse_rise, pulse_fall, pulse_trig, pulse_burst_count, pulse_meas_sm, pulse_meas_timing,
#    pulse_sample_rate, pulse_ranges, pulse_load, pulse_exec / pulse_fetch, etc.
#  - Defaults chosen for memristor work (fast pulses, small duty cycle). Tune to your device.
#  - This class configures CH1 as the pulser (source) and CH2 as the measurement channel (typical wiring).
#    You can swap channels by setting pulse_channel and measure_channel at init.
#


"""
https://chatgpt.com/s/t_68c5ec9a7ff88191948bdf4480c5f1a2
"""

import time
from typing import Tuple, List

class PMUDualChannelSweeps:
    def __init__(self, lpt_proxy, param_proxy, card_name="PMU1", pulse_channel: int = 1, measure_channel: int = 2):
        """
        lpt_proxy: your Proxy(..., "lpt") instance
        param_proxy: your Proxy(..., "param") instance (contains constants)
        card_name: "PMU1" (or "PMU2")
        pulse_channel: channel number that will be swept (1 or 2)
        measure_channel: read-back channel (1 or 2)
        """
        self.lpt = lpt_proxy
        self.param = param_proxy
        self.card = card_name
        self.pulse_channel = pulse_channel
        self.measure_channel = measure_channel

        # get instrument id (int) used by LPT calls
        self.card_id = self.lpt.getinstid(self.card)

        # sensible default measurement settings
        self.default_width = 10e-6     # 10 µs
        self.default_period = 100e-6   # 100 µs (duty ~10%)
        self.default_rise = 1e-7       # 100 ns
        self.default_fall = 1e-7       # 100 ns
        self.default_base = 0.0        # base (Vlow)
        self.default_v_range = 10.0    # pulse source range (V)
        self.default_i_meas_range = 1e-3  # 1 mA meas range (tweak to device)

    # -------------------------
    # Low-level helpers
    # -------------------------
    def _set_common_timing(self, width=None, period=None, rise=None, fall=None, delay=0.0):
        """Set timing: width, period, rise, fall, delay (keeps defaults if None)"""
        w = width if width is not None else self.default_width
        p = period if period is not None else self.default_period
        r = rise if rise is not None else self.default_rise
        f = fall if fall is not None else self.default_fall

        # order follows LPT naming from Keithley docs
        # set period (instr, chan, value)
        self.lpt.pulse_period(self.card_id, self.pulse_channel, float(p))
        # set width, rise, fall
        self.lpt.pulse_width(self.card_id, self.pulse_channel, float(w))
        self.lpt.pulse_rise(self.card_id, self.pulse_channel, float(r))
        self.lpt.pulse_fall(self.card_id, self.pulse_channel, float(f))
        # optional delay before pulses begin
        self.lpt.pulse_delay(self.card_id, self.pulse_channel, float(delay))

    def _set_output_levels(self, base: float, amplitude: float):
        """Set base (vlow) and a nominal vhigh (amplitude argument is a placeholder for some calls)."""
        # pulse_vlow(instr, chan, vlow)
        self.lpt.pulse_vlow(self.card_id, self.pulse_channel, float(base))
        # pulse_vhigh(instr, chan, vhigh)  -- set a nominal high value (sweeps will override amplitude)
        self.lpt.pulse_vhigh(self.card_id, self.pulse_channel, float(amplitude))

    def _set_measurement_defaults(self, meas_range_i=None, meas_sample_rate: float | None = None):
        """Set default measurement parameters so PMU knows how to capture current/voltage on measure channel."""
        if meas_range_i is None:
            meas_range_i = self.default_i_meas_range

        # Configure measurement ranges (instr, chan, v_range, i_range) — signature depends on your proxy impl
        # For safety set a measurement range on the measure channel and ensure PMU uses spot-mean measurement
        self.lpt.pulse_ranges(self.card_id, self.measure_channel, float(self.default_v_range), float(meas_range_i))
        # spot-mean config: pulse_meas_sm(instr, chan, KI_SPOT_MEAN_TYPE, ???) - keep example generic
        self.lpt.pulse_meas_sm(self.card_id, self.measure_channel, 0)  # 0==default spot-mean mode (proxy-specific)
        if meas_sample_rate:
            self.lpt.pulse_sample_rate(self.card_id, self.measure_channel, float(meas_sample_rate))

    def _arm_and_fetch(self, num_pulses:int=1, burst_mode: int = 0) -> dict:
        """
        Arm (trigger) the PMU and fetch results.
          - num_pulses: number of pulses per sweep point (pulse_burst_count)
          - burst_mode: 0 = Burst, 1 = Continuous, 2 = Trigger Burst
        Returns raw result buffer from pulse_fetch or pulse_exec / pulse_fetch sequence.
        """
        # set burst count
        self.lpt.pulse_burst_count(self.card_id, self.pulse_channel, int(num_pulses))
        # arm/start the pulse train (0 = burst)
        self.lpt.pulse_trig(self.card_id, int(burst_mode))
        # Wait a little for the test to complete; longer if many points / pulses used
        time.sleep(0.02 + num_pulses * 0.0001)
        # fetch results into buffer (proxy-specific return format)
        results = self.lpt.pulse_fetch(self.card_id)  # returns buffer/object depending on proxy impl
        return results

    # -------------------------
    # Sweep methods (one per sweep type)
    # -------------------------
    def sweep_amplitude(self, start: float, stop: float, step: float,
                        base: float = None, width=None, period=None, rise=None, fall=None,
                        pulses_per_point:int = 1) -> dict:
        """
        Sweep the pulse amplitude (Vhigh values): classic memristor switching search.
        - start/stop/step: amplitude sweep values (V)
        - base: Vlow (kept fixed while amplitude sweeps)
        - width/period/rise/fall: timing (defaults chosen above)
        - pulses_per_point: how many pulses to apply at each amplitude
        Returns the LPT result buffer from the PMU.
        """
        base = self.default_base if base is None else base
        # set timing and base/high placeholders
        self._set_common_timing(width, period, rise, fall)
        # set the fixed base level
        self._set_output_levels(base, start)   # vhigh set as 'start' placeholder
        # configure measurement defaults
        self._set_measurement_defaults()
        # configure the sweep on the pulser channel: (instr_id, chan, SweepType, start, stop, step)
        self.lpt.pulse_sweep_linear(self.card_id, self.pulse_channel, self.param.PULSE_AMPLITUDE_SP,
                                    float(start), float(stop), float(step))
        # execute/trigger and fetch data
        return self._arm_and_fetch(num_pulses=pulses_per_point)

    def sweep_base(self, start: float, stop: float, step: float,
                   amplitude: float = 0.0, width=None, period=None, rise=None, fall=None,
                   pulses_per_point:int = 1) -> dict:
        """
        Sweep the base (Vlow) while amplitude (Vhigh) is fixed.
        Useful for applying different offsets / asymmetric pulsing.
        """
        self._set_common_timing(width, period, rise, fall)
        # amplitude fixed at Vhigh
        self._set_output_levels(start, float(amplitude))  # placeholder for vlow/amp
        self._set_measurement_defaults()
        self.lpt.pulse_sweep_linear(self.card_id, self.pulse_channel, self.param.PULSE_BASE_SP,
                                    float(start), float(stop), float(step))
        return self._arm_and_fetch(num_pulses=pulses_per_point)

    def sweep_dc(self, start: float, stop: float, step: float, width=None, period=None, pulses_per_point:int = 1) -> dict:
        """
        Sweep the DC offset (DC bias) applied by the PMU. This moves the whole waveform up/down.
        """
        self._set_common_timing(width, period)
        # set a nominal vhigh/vlow so the device sees the DC variation (the sweep will adjust)
        self._set_output_levels(0.0, start)
        self._set_measurement_defaults()
        self.lpt.pulse_sweep_linear(self.card_id, self.pulse_channel, self.param.PULSE_DC_SP,
                                    float(start), float(stop), float(step))
        return self._arm_and_fetch(num_pulses=pulses_per_point)

    def sweep_period(self, start: float, stop: float, step: float,
                      amplitude: float = 1.0, base: float = 0.0, pulses_per_point:int = 1) -> dict:
        """
        Sweep pulse period (i.e., change duty cycle when width fixed).
        Use to probe thermal/self-heating or time-dependent switching.
        """
        # width keep default or user-supplied, period is being swept
        self._set_common_timing(width=self.default_width, period=None)  # we'll let sweep set period
        # set base and amplitude
        self._set_output_levels(base, amplitude)
        self._set_measurement_defaults()
        self.lpt.pulse_sweep_linear(self.card_id, self.pulse_channel, self.param.PULSE_PERIOD_SP,
                                    float(start), float(stop), float(step))
        return self._arm_and_fetch(num_pulses=pulses_per_point)

    def sweep_rise(self, start: float, stop: float, step: float, amplitude: float = 1.0, base: float = 0.0,
                   pulses_per_point:int = 1) -> dict:
        """Sweep rise time (edge speed). Useful when capacitive/edge effects matter."""
        self._set_common_timing(width=self.default_width, period=self.default_period)
        self._set_output_levels(base, amplitude)
        self._set_measurement_defaults()
        self.lpt.pulse_sweep_linear(self.card_id, self.pulse_channel, self.param.PULSE_RISE_SP,
                                    float(start), float(stop), float(step))
        return self._arm_and_fetch(num_pulses=pulses_per_point)

    def sweep_fall(self, start: float, stop: float, step: float, amplitude: float = 1.0, base: float = 0.0,
                   pulses_per_point:int = 1) -> dict:
        """Sweep fall time (edge speed)."""
        self._set_common_timing(width=self.default_width, period=self.default_period)
        self._set_output_levels(base, amplitude)
        self._set_measurement_defaults()
        self.lpt.pulse_sweep_linear(self.card_id, self.pulse_channel, self.param.PULSE_FALL_SP,
                                    float(start), float(stop), float(step))
        return self._arm_and_fetch(num_pulses=pulses_per_point)

    def sweep_width(self, start: float, stop: float, step: float, amplitude: float = 1.0, base: float = 0.0,
                    pulses_per_point:int = 1) -> dict:
        """Sweep pulse width (FWHM). Good for probing switching speed and energy per pulse."""
        self._set_common_timing(width=None, period=None)  # sweep will control width
        self._set_output_levels(base, amplitude)
        self._set_measurement_defaults()
        self.lpt.pulse_sweep_linear(self.card_id, self.pulse_channel, self.param.PULSE_WIDTH_SP,
                                    float(start), float(stop), float(step))
        return self._arm_and_fetch(num_pulses=pulses_per_point)

    def sweep_dual_amplitude(self, start: float, stop: float, step: float,
                             base: float = 0.0, width=None, period=None, pulses_per_point:int = 1) -> dict:
        """
        Dual sweep amplitude: sweeps from start->stop then stop->start (forward + reverse)
        Useful if you want an up-and-down hysteresis sweep in a single test pass.
        """
        self._set_common_timing(width, period)
        self._set_output_levels(base, start)
        self._set_measurement_defaults()
        self.lpt.pulse_sweep_linear(self.card_id, self.pulse_channel, self.param.PULSE_DUAL_AMPLITUDE_SP,
                                    float(start), float(stop), float(step))
        return self._arm_and_fetch(num_pulses=pulses_per_point)

    def sweep_dual_base(self, start: float, stop: float, step: float, amplitude: float = 1.0, pulses_per_point:int = 1) -> dict:
        """Dual sweep base (Vlow) - up and down in one test."""
        self._set_common_timing()
        self._set_output_levels(start, amplitude)
        self._set_measurement_defaults()
        self.lpt.pulse_sweep_linear(self.card_id, self.pulse_channel, self.param.PULSE_DUAL_BASE_SP,
                                    float(start), float(stop), float(step))
        return self._arm_and_fetch(num_pulses=pulses_per_point)

    def sweep_dual_dc(self, start: float, stop: float, step: float, pulses_per_point:int = 1) -> dict:
        """Dual sweep DC offset up and down in one pass."""
        self._set_common_timing()
        self._set_output_levels(0.0, start)
        self._set_measurement_defaults()
        self.lpt.pulse_sweep_linear(self.card_id, self.pulse_channel, self.param.PULSE_DUAL_DC_SP,
                                    float(start), float(stop), float(step))
        return self._arm_and_fetch(num_pulses=pulses_per_point)

    # -------------------------
    # Utility
    # -------------------------
    def close(self):
        try:
            self.lpt.devint()
            self.lpt.tstdsl()
        except Exception:
            pass



from ProxyClass import Proxy
import sys

def connect_to_pmu(ip: str, port: int = 8888, card: str = "PMU1"):
    """
    Connect to a 4200A PMU card via the LPT server.
    Returns (lpt_proxy, param_proxy, card_id).

    ip   : IP address of the 4200A
    port : LPT server port (default 8888)
    card : PMU card name, e.g. "PMU1" or "PMU2"
    """
    try:
        # Proxies for LPT commands and constants
        lpt_proxy = Proxy(ip, port, "lpt")
        param_proxy = Proxy(ip, port, "param")

        # Initialize tester
        lpt_proxy.initialize()

        # Select test station (station 1 usually default)
        lpt_proxy.tstsel(1)

        # Reset any existing operations
        lpt_proxy.devint()
        lpt_proxy.dev_abort()

        # Get instrument ID for the chosen card
        card_id = lpt_proxy.getinstid(card)

        print(f"✅ Connected to {card} at {ip}:{port} (card_id={card_id})")
        return lpt_proxy, param_proxy, card_id

    except Exception as e:
        print(f"❌ Failed to connect to {card} at {ip}:{port}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    ip = "192.168.0.10"
    port = 8888
    card = "PMU1"

    lpt, param, card_id = connect_to_pmu(ip, port, card)

    # Now you can pass these into your sweep/test class
    pmu = PMUDualChannelSweeps(lpt, param, card_name=card, pulse_channel=1, measure_channel=2)
    res = pmu.sweep_amplitude(0, 5, 0.1)

    pmu = PMUDualChannelSweeps(lpt_proxy, param_proxy, card_name="PMU1", pulse_channel=1, measure_channel=2)
    res = pmu.sweep_amplitude(start=0.0, stop=5.0, step=0.1, base=0.0,
                            width=10e-6, period=200e-6, pulses_per_point=1)
    # res: whatever your Proxy returns from pulse_fetch (convert/parse to array)
    pmu.close()


    res = pmu.sweep_dual_amplitude(start=0.0, stop=4.0, step=0.1, base=0.0,
                               width=10e-6, period=200e-6)

    res = pmu.sweep_width(start=10e-9, stop=1e-3, step=10e-9, amplitude=2.5, base=0.0, pulses_per_point=5)
    # you may want multiple pulses per point and average to reduce noise

    res = pmu.sweep_period(start=20e-6, stop=500e-6, step=20e-6, amplitude=2.5, base=0.0)

    # run small-amplitude sweeps with e.g. 10 pulses per point; look for sharp current jump
res = pmu.sweep_amplitude(start=0.5, stop=6.0, step=0.05, base=0.0, width=100e-6, period=1e-3, pulses_per_point=10)