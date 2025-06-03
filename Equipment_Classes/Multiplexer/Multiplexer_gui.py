"""
Multiplexer Control GUI

This program provides a graphical interface for controlling a 10-channel multiplexer via a National Instruments USB-6001 DAQ.

Hardware Configuration:
- NI USB-6001 DAQ connected via USB
- Digital Output Lines:
    - Line 0 => EN  (red)    - Enable line
    - Line 1 => A0  (white)  - Address line 0
    - Line 2 => A1  (yellow) - Address line 1
    - Line 3 => A2  (green)  - Address line 2
    - Line 4 => A3  (blue)   - Address line 3
    - GND => (black)         - Ground reference

Features:
1. Channel Selection (1-10):
   - Direct channel selection via dropdown
   - Real-time channel status display

2. Channel Testing:
   - Basic Test: Enables selected channel for specified duration
   - Toggle Test: Cycles channel ON-OFF 3 times
   - Sequence Test: Runs ON-OFF-ON-OFF-ON pattern

3. Channel Cycling:
   - Automatically cycles through all channels
   - Adjustable delay between channel switches

4. Safety Features:
   - Emergency disable button
   - Automatic shutdown on program close
   - Error handling with user notifications

Usage:
1. Select channel from dropdown (1-10)
2. Choose test pattern and duration for testing
3. Use cycle control for automated channel sequencing
4. Use disable button to turn off all channels

Author: [Your Name]
Date: [Current Date]
"""

import tkinter as tk
from tkinter import ttk, messagebox
import time
from Multiplexer_Class import MultiplexerController
import nidaqmx


class MultiplexerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Multiplexer Control")

        # Check available devices and select the first one or let user choose
        try:
            system = nidaqmx.system.System.local()
            available_devices = [device.name for device in system.devices]

            if not available_devices:
                messagebox.showerror("Error", "No NI-DAQ devices found!")
                root.destroy()
                return

            if len(available_devices) > 1:
                # If multiple devices, let user choose
                self.device_name = self.select_device_dialog(available_devices)
            else:
                # If only one device, use it
                self.device_name = available_devices[0]

            print(f"Using device: {self.device_name}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to enumerate devices: {e}")
            root.destroy()
            return

        # Add help button
        self.create_help_button()

        # Initialize multiplexer
        try:
            self.mux = MultiplexerController(device_name=self.device_name)
            print("Multiplexer initialized successfully")
        except Exception as e:
            messagebox.showerror("Initialization Error", f"Failed to initialize multiplexer: {e}")
            root.destroy()
            return

        # Create main frame
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Channel Selection
        ttk.Label(self.main_frame, text="Channel Selection").grid(row=0, column=0, columnspan=2, pady=5)
        self.channel_var = tk.StringVar(value="1")
        self.channel_combo = ttk.Combobox(self.main_frame, textvariable=self.channel_var,
                                          values=[str(i) for i in range(1, 11)], width=10)
        self.channel_combo.grid(row=1, column=0, padx=5)
        ttk.Button(self.main_frame, text="Select Channel",
                   command=self.select_channel).grid(row=1, column=1, padx=5)

        # Current Channel Display
        self.current_channel_var = tk.StringVar(value="Current Channel: None")
        ttk.Label(self.main_frame, textvariable=self.current_channel_var).grid(row=2, column=0,
                                                                               columnspan=2, pady=10)

        # Channel Test Frame
        test_frame = ttk.LabelFrame(self.main_frame, text="Channel Test", padding="5")
        test_frame.grid(row=3, column=0, columnspan=2, pady=5, sticky=(tk.W, tk.E))

        # Test Pattern Selection
        ttk.Label(test_frame, text="Test Pattern:").grid(row=0, column=0, padx=5)
        self.test_pattern = tk.StringVar(value="basic")
        pattern_combo = ttk.Combobox(test_frame, textvariable=self.test_pattern,
                                     values=["basic", "toggle", "sequence"], width=10)
        pattern_combo.grid(row=0, column=1, padx=5)

        ttk.Label(test_frame, text="Duration (s):").grid(row=1, column=0, padx=5)
        self.duration_var = tk.StringVar(value="1.0")
        self.duration_entry = ttk.Entry(test_frame, textvariable=self.duration_var, width=10)
        self.duration_entry.grid(row=1, column=1, padx=5)
        ttk.Button(test_frame, text="Run Test",
                   command=self.run_test).grid(row=1, column=2, padx=5)

        # Cycle Control Frame
        cycle_frame = ttk.LabelFrame(self.main_frame, text="Cycle Control", padding="5")
        cycle_frame.grid(row=4, column=0, columnspan=2, pady=5, sticky=(tk.W, tk.E))

        ttk.Label(cycle_frame, text="Delay (s):").grid(row=0, column=0, padx=5)
        self.cycle_delay_var = tk.StringVar(value="1.0")
        self.cycle_delay_entry = ttk.Entry(cycle_frame, textvariable=self.cycle_delay_var, width=10)
        self.cycle_delay_entry.grid(row=0, column=1, padx=5)
        ttk.Button(cycle_frame, text="Start Cycle",
                   command=self.cycle_channels).grid(row=0, column=2, padx=5)

        # Control Buttons
        ttk.Button(self.main_frame, text="Disable Multiplexer",
                   command=self.disable_mux).grid(row=5, column=0, columnspan=2, pady=10)

        # Status Bar
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self.main_frame, textvariable=self.status_var,
                  relief=tk.SUNKEN).grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E))

        # Cleanup on window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_help_button(self):
        """Creates a help button that displays program information"""
        help_frame = ttk.Frame(self.root, padding="5")
        help_frame.grid(row=0, column=0, sticky=(tk.E))
        ttk.Button(help_frame, text="Help", command=self.show_help).grid(row=0, column=0)

    def show_help(self):
        """Displays help information"""
        help_text = """
Multiplexer Control System

Hardware Setup:
- NI USB-6001 DAQ
- 10-channel multiplexer
- Digital connections:
  Line 0 (RED) => Enable
  Line 1 (WHITE) => A0
  Line 2 (YELLOW) => A1
  Line 3 (GREEN) => A2
  Line 4 (BLUE) => A3
  GND (BLACK) => Ground

Features:
1. Channel Selection:
   - Choose channels 1-10
   - Direct channel activation

2. Test Patterns:
   - Basic: Simple ON for duration
   - Toggle: ON-OFF-ON cycles
   - Sequence: Complex ON-OFF pattern

3. Channel Cycling:
   - Automatic channel sequencing
   - Adjustable timing

4. Safety Controls:
   - Emergency disable
   - Auto-shutdown protection
"""
        messagebox.showinfo("Help", help_text)

    def select_channel(self):
        try:
            channel = int(self.channel_var.get())
            self.mux.select_channel(channel)
            self.current_channel_var.set(f"Current Channel: {channel}")
            self.status_var.set(f"Channel {channel} selected")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to select channel: {e}")

    def run_test(self):
        try:
            channel = int(self.channel_var.get())
            duration = float(self.duration_var.get())
            pattern = self.test_pattern.get()

            self.status_var.set(f"Testing channel {channel} with {pattern} pattern")
            self.root.update()

            if pattern == "basic":
                # Simple duration test
                self.mux.select_channel(channel)
                time.sleep(duration)

            elif pattern == "toggle":
                # Toggle test
                for i in range(3):
                    self.status_var.set(f"Toggle {i + 1}/3")
                    self.root.update()
                    self.mux.select_channel(channel)
                    time.sleep(duration / 2)
                    self.mux.disable()
                    time.sleep(duration / 2)

            elif pattern == "sequence":
                # Sequence test
                self.status_var.set("Running sequence test")
                self.root.update()

                # ON-OFF-ON-OFF-ON sequence
                sequence = [(channel, duration),
                            (None, duration / 2),
                            (channel, duration),
                            (None, duration / 2),
                            (channel, duration)]

                for ch, dur in sequence:
                    if ch is None:
                        self.mux.disable()
                    else:
                        self.mux.select_channel(ch)
                    time.sleep(dur)

            self.status_var.set("Test complete")
            messagebox.showinfo("Test Complete",
                                f"Channel {channel} {pattern} test completed\n"
                                f"Duration: {duration} seconds")

        except Exception as e:
            messagebox.showerror("Error", f"Test failed: {e}")

    def cycle_channels(self):
        try:
            delay = float(self.cycle_delay_var.get())
            self.status_var.set("Cycling through channels...")
            self.root.update()

            for channel in range(1, 11):
                self.mux.select_channel(channel)
                self.current_channel_var.set(f"Current Channel: {channel}")
                self.root.update()
                time.sleep(delay)

            self.status_var.set("Cycle complete")
        except Exception as e:
            messagebox.showerror("Error", f"Cycle failed: {e}")

    def disable_mux(self):
        try:
            self.mux.disable()
            self.current_channel_var.set("Current Channel: None")
            self.status_var.set("Multiplexer disabled")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to disable multiplexer: {e}")

    def on_closing(self):
        try:
            self.mux.disable()
        finally:
            self.root.destroy()


def main():
    root = tk.Tk()
    app = MultiplexerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()