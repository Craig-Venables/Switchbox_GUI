import nidaqmx
from nidaqmx.constants import Level, Edge, AcquisitionType, FrequencyUnits
import time

class NIUSB6211:
    """
    Control class for NI USB-6211 DAQ card using nidaqmx.
    Supports:
        - Analog Input
        - Analog Output
        - Digital IO
        - Counter
    """

    def __init__(self, device_name="Dev1"):
        self.device_name = device_name

    # ---------- ANALOG INPUT ----------
    def read_analog(self, channel="ai0", samples=1, rate=1000):
        """
        Read analog voltage from input channel(s).
        """
        values = []
        with nidaqmx.Task() as task:
            task.ai_channels.add_ai_voltage_chan(f"{self.device_name}/{channel}")
            if samples > 1:
                task.timing.cfg_samp_clk_timing(rate, sample_mode=AcquisitionType.FINITE, samps_per_chan=samples)
                values = task.read(number_of_samples_per_channel=samples)
            else:
                values = task.read()
        return values

    # ---------- ANALOG OUTPUT ----------
    def write_analog(self, channel="ao0", value=0.0):
        """
        Write an analog voltage to output channel.
        """
        with nidaqmx.Task() as task:
            task.ao_channels.add_ao_voltage_chan(f"{self.device_name}/{channel}")
            task.write(value)

    # ---------- DIGITAL OUTPUT ----------
    def write_digital(self, channel="port0/line0", value=True):
        """
        Write a digital signal (True/False).
        """
        with nidaqmx.Task() as task:
            task.do_channels.add_do_chan(f"{self.device_name}/{channel}")
            task.write(value)

    # ---------- DIGITAL INPUT ----------
    def read_digital(self, channel="port0/line0"):
        """
        Read a digital signal (True/False).
        """
        with nidaqmx.Task() as task:
            task.di_channels.add_di_chan(f"{self.device_name}/{channel}")
            return task.read()

    # ---------- COUNTER (example: edge counting) ----------
    def count_edges(self, counter="ctr0", source="PFI0", samples=100, rate=1000):
        """
        Count edges on a given counter input.
        """
        with nidaqmx.Task() as task:
            task.ci_channels.add_ci_count_edges_chan(f"{self.device_name}/{counter}")
            task.channels.all.ci_count_edges_term = f"/{self.device_name}/{source}"
            task.timing.cfg_samp_clk_timing(rate, sample_mode=AcquisitionType.FINITE, samps_per_chan=samples)
            return task.read(number_of_samples_per_channel=samples)

    # ---------- PULSE GENERATION ----------
    
    def send_pulse(self, counter="ctr0", pulse_time=0.001, idle_state=Level.LOW):
        """
        Send a single digital pulse on counter output (appears on fixed hardware pin).
        For USB-6211: ctr0 → PFI12, ctr1 → PFI13
        """
        min_time = 2 / 80e6  # 25 ns minimum
        high_time = max(pulse_time, min_time)
        low_time = max(min_time, pulse_time * 0.1)

        with nidaqmx.Task() as task:
            chan = f"{self.device_name}/{counter}"
            task.co_channels.add_co_pulse_chan_time(
                chan,
                low_time=low_time,
                high_time=high_time,
                idle_state=idle_state
            )

            task.timing.cfg_implicit_timing(
                sample_mode=AcquisitionType.FINITE,
                samps_per_chan=1
            )

            task.start()
            task.wait_until_done(timeout=5.0)
            task.stop()

    
    def send_repeated_pulses(self, counter="ctr0", output_terminal="/Dev1/PFI12",
                             high_time=0.001, low_time=0.001, num_pulses=10):
        """
        Generate a finite train of pulses.
        """
        with nidaqmx.Task() as task:
            chan = f"{self.device_name}/{counter}"
            task.co_channels.add_co_pulse_chan_time(
                chan,
                low_time=low_time,
                high_time=high_time,
                idle_state=Level.LOW
            )
            task.co_channels.all.co_pulse_term = output_terminal

            task.timing.cfg_implicit_timing(
                sample_mode=AcquisitionType.FINITE,
                samps_per_chan=num_pulses
            )

            task.start()
            task.wait_until_done(timeout=10.0)
            task.stop()

if __name__ == "__main__":
    daq = NIUSB6211("Dev1")
    # Sends one pulse 1 ms wide on ctr0 → appears on PFI12 pin
    daq.send_pulse(counter="ctr0", pulse_time=1e-3)

    # Example: send 10 pulses, 1 ms high / 1 ms low
    daq.send_repeated_pulses(counter="ctr0", output_terminal="/Dev1/PFI12",
                             high_time=0.001, low_time=0.001, num_pulses=10)