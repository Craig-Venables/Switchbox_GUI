import nidaqmx
import time
from nidaqmx.constants import LineGrouping

""" Multiplexer class for controlling the multiplexer, Truth table is required to be boolean it cannot be 1,0!"""

class MultiplexerController:
    def __init__(self, device_name=None):
        """
        Initialize the Multiplexer Controller
        Args:
            device_name (str): Name of the NI DAQ device. If None, will attempt to find first available device
        """
        # Find and set device name
        self.device_name = self._get_device_name(device_name)
        self.current_channel = None

        # Truth table mapping for channels (A3, A2, A1, A0, EN)
        self.truth_table = {
            'None': (False, False, False, False, False),  # All off including EN
            1: (False, False, False, False, True),
            2: (False, False, False, True, True),
            3: (False, False, True, False, True),
            4: (False, False, True, True, True),
            5: (False, True, False, False, True),
            6: (False, True, False, True, True),
            7: (False, True, True, False, True),
            8: (False, True, True, True, True),
            9: (True, False, False, False, True),
            10: (True, False, False, True, True)
        }

    def _get_device_name(self, device_name):
        """
        Get device name, either from parameter or by finding first available device
        """
        try:
            system = nidaqmx.system.System.local()
            available_devices = [device.name for device in system.devices]

            if not available_devices:
                raise RuntimeError("No NI-DAQ devices found")

            # If no device name specified, use first available
            if device_name is None:
                selected_device = available_devices[0]
            else:
                # If device name specified, verify it exists
                if device_name not in available_devices:
                    raise ValueError(f"Device {device_name} not found. Available devices: {available_devices}")
                selected_device = device_name

            print(f"Using DAQ device: {selected_device}")
            return selected_device

        except Exception as e:
            raise RuntimeError(f"Failed to initialize DAQ device: {str(e)}")

    def select_channel(self, channel):
        """
        Select a specific channel on the multiplexer
        Args:
            channel (int or str): Channel number (1-10) or 'None' to disable
        """
        if channel not in self.truth_table:
            raise ValueError(f"Invalid channel. Must be one of {list(self.truth_table.keys())}")

        try:
            # Skip if trying to set the same channel
            if channel == self.current_channel:
                return

            # Get the binary values for the selected channel
            a3, a2, a1, a0, en = self.truth_table[channel]

            values = [en,a0,a1, a2, a3]  #reorder


            with nidaqmx.Task() as task:
                # Configure digital output lines
                task.do_channels.add_do_chan(f"{self.device_name}/port0/line0:4" ,line_grouping=LineGrouping.CHAN_PER_LINE)

                # Then write new values
                task.write(values, auto_start=True)
                time.sleep(0.01)  # Small delay to ensure latching

            self.current_channel = channel
            print(f"Set channel {channel} with values: {values}")  # Debug output

        except nidaqmx.DaqError as e:
            raise ConnectionError(f"Failed to set channel: {e}")

    def disable(self):
        """Disable the multiplexer by setting all lines to 0"""
        self.select_channel('None')

    def get_current_channel(self):
        """Return the currently selected channel"""
        return self.current_channel

    def cycle_all_channels(self, delay=1.0):
        """
        Cycle through all channels
        Args:
            delay (float): Delay between channel switches in seconds
        """
        try:
            for channel in range(1, 11):
                print(f"Switching to channel {channel}")
                self.select_channel(channel)
                time.sleep(delay)
        finally:
            self.disable()


# Simple test function to verify the controller is working
def test_controller():
    try:
        print("Initializing Multiplexer Controller...")
        mux = MultiplexerController()
        print("Controller initialized successfully")

        # Test basic functionality
        print("\nTesting basic channel selection...")
        mux.select_channel(1)
        time.sleep(1)

        print("Testing channel disable...")
        mux.disable()
        time.sleep(1)

        print("Testing quick channel cycle...")
        mux.cycle_all_channels(delay=0.5)

        print("\nTest completed successfully!")

    except Exception as e:
        print(f"Test failed: {e}")
    finally:
        try:
            mux.disable()
        except:
            pass


if __name__ == "__main__":
    test_controller()