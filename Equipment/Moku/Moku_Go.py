from moku import Moku
from moku.instruments import ArbitraryWaveformGenerator
import numpy as np
import time

class MokuGoPulse:
    def __init__(self, usb_identifier: str):
        """
        Connect to a Moku:Go via USB.
        usb_identifier example: 'usb://MokuGo-000010'
        """
        self.moku = Moku(usb_identifier)
        self.awg = self.moku.attach_instrument(ArbitraryWaveformGenerator)

    def send_pulse(self, width: float, height: float, rise: float = 0, fall: float = 0):
        """
        Send a single pulse.
        width, rise, fall in seconds
        height in volts
        """
        total_time = rise + width + fall
        # Time vector
        dt = 1e-7  # 100 ns resolution, adjust if needed
        t = np.arange(0, total_time, dt)
        
        waveform = np.zeros_like(t)
        # Rising edge
        if rise > 0:
            rise_idx = (t < rise)
            waveform[rise_idx] = height * (t[rise_idx] / rise)
        # Pulse top
        top_idx = (t >= rise) & (t < rise + width)
        waveform[top_idx] = height
        # Falling edge
        if fall > 0:
            fall_idx = (t >= rise + width)
            waveform[fall_idx] = height * (1 - (t[fall_idx] - (rise + width)) / fall)

        self.awg.set_waveform(t, waveform)
        self.awg.output = True
        time.sleep(total_time)
        self.awg.output = False

    def send_pulse_train(self, pulse_train: list, width: float, height: float, rise: float = 0, fall: float = 0, dt_between: float = 0):
        """
        Send a sequence of pulses defined by a list of 0s and 1s.
        dt_between: time between pulses in seconds
        """
        pulses = []
        for bit in pulse_train:
            if bit:
                total_time = rise + width + fall
                t = np.arange(0, total_time, 1e-7)
                waveform = np.zeros_like(t)
                # Rising
                if rise > 0:
                    rise_idx = (t < rise)
                    waveform[rise_idx] = height * (t[rise_idx] / rise)
                # Top
                top_idx = (t >= rise) & (t < rise + width)
                waveform[top_idx] = height
                # Falling
                if fall > 0:
                    fall_idx = (t >= rise + width)
                    waveform[fall_idx] = height * (1 - (t[fall_idx] - (rise + width)) / fall)
                pulses.append(waveform)
            else:
                pulses.append(np.zeros(int((rise + width + fall) / 1e-7)))
            
            # Add spacing between pulses
            if dt_between > 0:
                pulses.append(np.zeros(int(dt_between / 1e-7)))

        full_waveform = np.concatenate(pulses)
        t_total = np.arange(0, len(full_waveform) * 1e-7, 1e-7)
        self.awg.set_waveform(t_total, full_waveform)
        self.awg.output = True
        time.sleep(t_total[-1])
        self.awg.output = False

# Example usage
if __name__ == "__main__":
    moku_pulse = MokuGoPulse("usb://MokuGo-000010")
    # Single pulse: 100 ns width, 1 V height, 10 ns rise/fall
    moku_pulse.send_pulse(width=100e-9, height=1, rise=10e-9, fall=10e-9)
    # Pulse train: 1-0-1, width 100 ns, 1 V height, 10 ns rise/fall, 50 ns spacing
    moku_pulse.send_pulse_train([1,0,1], width=100e-9, height=1, rise=10e-9, fall=10e-9, dt_between=50e-9)
