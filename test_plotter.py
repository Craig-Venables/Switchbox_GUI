# test_plotter.py - Simple test script
import tkinter as tk
import numpy as np
import time
import threading
from measurement_plotter import MeasurementPlotter, ThreadSafePlotter


def test_iv_sweep():
    """Test the plotter with simulated IV sweep data."""
    root = tk.Tk()
    root.title("Test Plotter")

    # Create plotter
    plotter = MeasurementPlotter(root, measurement_type="IV Sweep")
    safe_plotter = ThreadSafePlotter(plotter)

    def generate_data():
        """Generate simulated data in a thread."""
        devices = ["Device_1", "Device_2", "Device_3"]

        for cycle in range(5):
            for device in devices:
                # Generate IV curve
                voltages = np.linspace(0, 5, 50)
                # Add some noise and device-specific behavior
                noise = np.random.normal(0, 0.1e-6, len(voltages))
                if device == "Device_1":
                    currents = 1e-6 * voltages ** 2 + noise
                elif device == "Device_2":
                    currents = 2e-6 * voltages ** 1.5 + noise
                else:
                    currents = 0.5e-6 * voltages ** 2.5 + noise

                # Add data to plotter
                safe_plotter.add_batch(device, voltages, currents)

                time.sleep(0.5)  # Simulate measurement time

        print("Data generation complete!")

    # Start data generation in thread
    data_thread = threading.Thread(target=generate_data, daemon=True)
    data_thread.start()

    # Control frame
    control_frame = tk.Frame(root)
    control_frame.pack(pady=10)

    tk.Label(control_frame, text="Test controls for the plotter").pack()

    tk.Button(
        control_frame,
        text="Close Plotter",
        command=lambda: plotter.on_close() if plotter else None
    ).pack(pady=5)

    root.mainloop()


def test_avg_measure():
    """Test the plotter with simulated average measurement data."""
    root = tk.Tk()
    root.title("Test Average Measurement Plotter")

    # Create plotter
    plotter = MeasurementPlotter(root, measurement_type="Single Avg Measure")
    safe_plotter = ThreadSafePlotter(plotter)

    def generate_data():
        """Generate simulated average measurement data."""
        devices = ["Device_A", "Device_B", "Device_C", "Device_D"]
        start_time = time.time()

        for measurement in range(20):
            for i, device in enumerate(devices):
                # Simulate current measurement with drift
                base_current = (i + 1) * 1e-6
                drift = 0.1e-6 * np.sin(measurement * 0.1)
                noise = np.random.normal(0, 0.05e-6)
                current = base_current + drift + noise

                # Add data point
                elapsed_time = time.time() - start_time
                safe_plotter.add_data(device, elapsed_time, current)

                time.sleep(0.2)  # Simulate measurement time

        print("Data generation complete!")

    # Start data generation in thread
    data_thread = threading.Thread(target=generate_data, daemon=True)
    data_thread.start()

    root.mainloop()


if __name__ == "__main__":
    # Test IV sweep plotter
    print("Testing IV Sweep plotter...")
    test_iv_sweep()

    # Test average measurement plotter
    # print("Testing Average Measurement plotter...")
    # test_avg_measure()