import time
from ProxyClass import Proxy


class SimpleKeithley4200A_PMU:
    """Minimal wrapper for Keithley 4200A PMU via LPT (stripped down)."""

    def __init__(self, ip: str, port: int = 8888, card: str = "PMU1", channel: int = 1):
        """Connect to PMU card/channel.

        Args:
            ip: IP of the 4200A LPT server, e.g. "192.168.0.10"
            port: LPT server port (default 8888)
            card: Instrument name, usually "PMU1"
            channel: Channel index (1 or 2)
        """
        self.lpt = Proxy(ip, port, "lpt")
        self.param = Proxy(ip, port, "param")

        # Init session
        self.lpt.initialize()
        self.lpt.tstsel(1)     # select station 1
        self.lpt.devint()
        self.lpt.dev_abort()

        # Resolve card ID
        self.card_id = self.lpt.getinstid(card)
        self.channel = channel   # NOTE: 1- or 2-based

        print(f"Connected to {card} channel {channel}, id={self.card_id}")

    def configure_basic_pulse(self):
        """Configure a simple pulse sweep (values from working example)."""

        self.lpt.rpm_config(self.card_id, self.channel,
                            modifier=self.param.KI_RPM_PATHWAY,
                            value=self.param.KI_RPM_PULSE)

        self.lpt.pulse_meas_sm(self.card_id, self.channel,
                               acquire_type=0,
                               acquire_meas_v_ampl=1,
                               acquire_meas_v_base=0,
                               acquire_meas_i_ampl=1,
                               acquire_meas_i_base=0,
                               acquire_time_stamp=1,
                               llecomp=0)

        self.lpt.pulse_ranges(self.card_id, self.channel,
                              v_src_range=10.0,
                              v_range_type=0, v_range=10.0,
                              i_range_type=0, i_range=0.2)

        self.lpt.pulse_limits(self.card_id, self.channel,
                              v_limit=5.0, i_limit=1.0, power_limit=10.0)

        self.lpt.pulse_meas_timing(self.card_id, self.channel,
                                   start_percent=0.2,
                                   stop_percent=0.8,
                                   num_pulses=4)

        self.lpt.pulse_source_timing(self.card_id, self.channel,
                                     period=20e-6,
                                     delay=1e-7,
                                     width=10e-6,
                                     rise=1e-7,
                                     fall=1e-7)

        self.lpt.pulse_load(self.card_id, self.channel, load=1e6)

        self.lpt.pulse_sweep_linear(self.card_id, self.channel,
                                    sweep_type=self.param.PULSE_AMPLITUDE_SP,
                                    start=0.5,
                                    stop=1.0,
                                    step=0.1)

    def run(self, timeout: float = 5.0):
        """Execute configured sequence and fetch results."""

        self.lpt.pulse_output(self.card_id, self.channel, out_state=1)
        self.lpt.pulse_exec(mode=1)

        t0 = time.time()
        while True:
            status, elapsed = self.lpt.pulse_exec_status()
            if status != self.param.PMU_TEST_STATUS_RUNNING:
                break
            if time.time() - t0 > timeout:
                self.lpt.dev_abort()
                raise TimeoutError("Pulse execution timeout")
            time.sleep(0.05)

        buf_size = self.lpt.pulse_chan_status(self.card_id, self.channel)
        v, i, ts, statuses = self.lpt.pulse_fetch(self.card_id, self.channel,
                                                  start_index=0,
                                                  stop_index=buf_size - 1)

        decoded_status = [self.lpt.decode_pulse_status(s) for s in statuses]

        print(f"Buffer size: {buf_size}")
        print("Voltages:", v)
        print("Currents:", i)
        print("Timestamps:", ts)
        print("Statuses:", decoded_status)

        self.lpt.pulse_output(self.card_id, self.channel, out_state=0)

    def close(self):
        try:
            self.lpt.devint()
            self.lpt.tstdsl()
        except Exception:
            pass


if __name__ == "__main__":
    # Adjust IP as needed
    pmu = SimpleKeithley4200A_PMU("192.168.0.10", 8888, card="PMU1", channel=1)
    pmu.configure_basic_pulse()
    pmu.run(timeout=10.0)
    pmu.close()