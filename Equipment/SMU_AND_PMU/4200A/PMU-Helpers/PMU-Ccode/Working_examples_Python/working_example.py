# This script is a minimum working example for generating a segmented arbitrary waveform with Keithley 4200-SCS device
# and fetching the results from the device. The problem arises when trying to read out the buffer after a measurement.

import time
import sys
from pathlib import Path
# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from ProxyClass import Proxy


# The pylptlib package is a python wrapper for the lptlib.dll.
#from pylptlib import lpt, param


def minimum_working_example():
    lpt = Proxy('192.168.0.10', 8888, "lpt")
    param = Proxy('192.168.0.10', 8888, "param")
    
    # Initialization
    lpt.initialize()
    lpt.tstsel(1)
    lpt.devint()
    card_id = lpt.getinstid("PMU1")

    gate = 1
    drain = 2
    sample_rate = 200e6

    lpt.pg2_init(card_id, param.PULSE_MODE_SARB)

    for channel in [gate, drain]:
        lpt.pulse_load(card_id, channel, 50)
        lpt.pulse_ranges(
            card_id,
            channel,
            10,
            param.PULSE_MEAS_FIXED,
            10,
            param.PULSE_MEAS_FIXED,
            0.2,
        )
        lpt.pulse_burst_count(card_id, channel, 1)
        lpt.pulse_output(card_id, channel, 1)

    lpt.pulse_sample_rate(card_id, sample_rate)

    # Define a simple 'rectangle' sequence for both channels and create a waveform
    for channel in [gate, drain]:
        lpt.seg_arb_sequence(
            instr_id=card_id,
            chan=channel,
            seq_num=1,
            num_segments=3,
            start_v=[0, 1, 1],
            stop_v=[1, 1, 0],
            time=[1e-7, 1e-6, 1e-7],
            trig=[1, 1, 1],
            ssr=[1, 1, 1],
            meas_type=[0, 1, 0],
            meas_start=[0, 0, 0],
            meas_stop=[0, 1e-6, 0],
        )

        lpt.seg_arb_waveform(
            instr_id=card_id,
            chan=channel,
            num_seq=3,
            seq=[1, 1, 1],
            seq_loop_count=[1, 1, 1],
        )

    # Start pulse generation
    # Working pulse generation has been confirmed by an external oscilloscope
    lpt.pulse_exec(0)

    # Wait for test to finish - as described in the manual
    # This works as expected
    while True:
        time.sleep(1)
        status, elapsed_time = lpt.pulse_exec_status()

        if status != param.PMU_TEST_STATUS_RUNNING:
            break
        if elapsed_time > 60:
            lpt.dev_abort()

    results = []
    for channel in [1, 2]:
        # The problem arises here: buffer_size is always empty
        buffer_size = lpt.pulse_chan_status(card_id, channel)
        print(f"Buffer size for channel {channel}: {buffer_size}")

        # Hence the following line will always return an empty list
        result = lpt.pulse_fetch(card_id, channel, 0, 9)
        results.append(result)
        print(f"Results for channel {channel}: {result}")


if __name__ == "__main__":
    minimum_working_example()