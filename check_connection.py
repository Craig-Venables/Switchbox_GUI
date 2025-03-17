import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from Keithley2400 import Keithley2400Controller
import time
import threading

class CheckConnection:
    def __init__(self, master,keithley):
        self.master = master
        self.top = tk.Toplevel(master)
        self.top.title("Checking Connection...")
        self.top.geometry("500x500")
        self.keithley = keithley
        self.check_connection_window = True



        self.frame1()
        self.start_measurement_loop()

    def frame1(self):
        frame = tk.LabelFrame(self.top, text="Last Measurement Plot", padx=5, pady=5)
        frame.grid(row=0, column=0, rowspan=5, padx=10, pady=5, sticky="nsew")

        self.figure, self.ax = plt.subplots(figsize=(4, 3))
        self.ax.set_title("Measurement Plot")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Current (A)")

        self.canvas = FigureCanvasTkAgg(self.figure, master=frame)
        self.canvas.get_tk_widget().grid(row=0, column=0, columnspan=5, sticky="nsew")

        # Configure the frame layout
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        # Close button
        self.close_button = tk.Button(frame, text="Close", command=self.close_window)
        self.close_button.grid(row=1, column=0, columnspan=1, pady=5)

    def start_measurement_loop(self):
        self.measurement_thread = threading.Thread(target=self.measurement_loop)
        self.measurement_thread.daemon = True
        self.measurement_thread.start()

    def measurement_loop(self):
        time_data = []
        current_data = []
        start_time = time.time()
        self.keithley.set_voltage(0.2,0.0001)
        self.keithley.enable_output(True)
        time.sleep(0.5)
        self.previous_current = None
        while self.check_connection_window:

            current_value = self.keithley.measure_current()
            elapsed_time = time.time() - start_time

            time_data.append(elapsed_time)
            current_data.append(current_value[1])
            current = current_value[1]
            print(current)

            # if self.previous_current is not None and current > 1000 * self.previous_current:
            #     self.on_spike_detected()

            self.previous_current = current_value[1]
            self.update_plot(time_data, current_data)
            time.sleep(0.2)

        self.keithley.shutdown()

    def on_spike_detected(self):
        self.keithley.beep(400,1)

    # This function is called when a spike is detected

    def get_current_from_keithley(self):
        # Replace this with actual code to get current from Keithley
        # For simulation, return a random value
        import random
        return random.uniform(0.1, 1.0)

    def update_plot(self, time_data, current_data):
        self.ax.clear()
        self.ax.plot(time_data, current_data, marker='o')
        self.ax.set_title("Measurement Plot")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Current (A)")

        # Set y-axis limit to not go above 1e-9
        self.ax.set_ylim(bottom=-5e-10, top=5e-10)
        self.canvas.draw()
    def close_window(self):
        self.check_connection_window = False
        self.top.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = CheckConnection(root)
    root.mainloop()