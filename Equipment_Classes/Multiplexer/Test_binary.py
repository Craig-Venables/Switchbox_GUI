import nidaqmx
import time
from nidaqmx.constants import LineGrouping

""" Simple test scrip to test connection too the multiplexer"""

# Simple test script for NI USB-6001 multiplexer control
try:
    print("Testing DAQ connection...")

    # First, let's check if we can see the device
    system = nidaqmx.system.System.local()
    devices = [device.name for device in system.devices]
    print(f"Found devices: {devices}")

    # Simple test sequence
    with nidaqmx.Task() as task:
        # Configure digital output lines
        task.do_channels.add_do_chan("Multiplexer/port0/line0:7",line_grouping=LineGrouping.CHAN_PER_LINE)

        # Start the task
        task.start()

        print("\nRunning basic test sequence...")

        # reset
        task.write([False, False, False, False, False, False,False,False], auto_start=True)
        time.sleep(1)

        # set ch 2
        task.write([True, True, False, False, False,False,False,False], auto_start=True)
        time.sleep(5)


    print("\nBasic test completed successfully!")

except nidaqmx.DaqError as e:
    print(f"DAQ Error: {e}")
except Exception as e:
    print(f"Error: {e}")