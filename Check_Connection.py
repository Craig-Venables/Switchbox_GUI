import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import time
import threading

class CheckConnection:
    def __init__(self, master,keithley):
        self.master = master
        self.top = tk.Toplevel(master)
        self.top.title("Checking Connection...")
        self.top.geometry("700x700")
        self.keithley = keithley
        self.check_connection_window = True
        self.noise_already = False
        # Beep when absolute current reaches or exceeds this threshold (A)
        self.current_threshold_a = 10e-9

        self.frame1()
        self.start_measurement_loop()

    def frame1(self):
        frame = tk.LabelFrame(self.top, text="Last Measurement Plot", padx=5, pady=5)
        frame.grid(row=0, column=0, columnspan=5, padx=10, pady=5, sticky="nsew")

        self.figure, self.ax = plt.subplots(figsize=(5, 5))
        self.ax.set_title("Measurement Plot")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Current (Across Ito)")

        self.canvas = FigureCanvasTkAgg(self.figure, master=frame)
        self.canvas.get_tk_widget().grid(row=0, column=0, columnspan=3, sticky="nsew")

        # Configure the frame layout
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        # Close button
        self.close_button = tk.Button(frame, text="Close", command=self.close_window)
        self.close_button.grid(row=1, column=2, columnspan=1, pady=5)

        # Toggle switch: make sound
        self.make_sound_label = tk.Label(frame, text="make sound upon connection?")
        self.make_sound_label.grid(row=1, column=0, sticky="w")
        self.make_sound_var = tk.IntVar(value=1)
        self.make_sound_switch = ttk.Checkbutton(frame, variable=self.make_sound_var, command=self.make_sound)
        self.make_sound_switch.grid(row=1, column=1, columnspan=1)

        # # Toggle switch: Measure one device
        # self.make_sound_label = tk.Label(frame, text="other?")
        # self.make_sound_label.grid(row=1, column=1, sticky="w")
        # self.make_sound_var = tk.IntVar(value=1)
        # self.make_sound_switch = ttk.Checkbutton(frame, variable=self.make_sound_var, command=self.make_sound)
        # self.make_sound_switch.grid(row=1, column=2, columnspan=1)

    def make_sound(self):
        if self.make_sound_var.get():
            print("sound on")
        else:
            print("sound off")

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
            #print(current)

            if self.make_sound_var.get():
                # Beep once when absolute current crosses or exceeds threshold
                if not self.noise_already and abs(current) >= self.current_threshold_a:
                    print("sound made (threshold reached)")
                    self.on_spike_detected()

            self.previous_current = current_value[1]
            self.update_plot(time_data, current_data)
            time.sleep(0.2)

        self.keithley.shutdown()

    def on_spike_detected(self):
        self.keithley.beep(400,1)
        self.noise_already = True

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
        self.ax.set_ylabel("Current")
        self.ax.set_yscale("log")
        #self.ax.autoscale(axis="y")
        self.canvas.draw()

    def close_window(self):
        self.check_connection_window = False
        self.keithley.enable_output(False)
        self.top.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = CheckConnection(root)
    root.mainloop()


    def endurance(self):
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

            time.sleep(0.2)

        self.keithley.shutdown()
