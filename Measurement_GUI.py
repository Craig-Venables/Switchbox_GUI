import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import numpy as np
import json
import time
import sys
import string
import os
import re
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import logging
from datetime import datetime
import threading
import atexit

from Equipment_Classes.Keithley2400 import Keithley2400Controller  # Import the Keithley class
from Equipment_Classes.Keithley2220 import Keithley2220_Powersupply  # import power supply controll
from AdaptiveMeasurement import AdaptiveMeasurement
from Check_Connection import CheckConnection
from TelegramBot import TelegramBot
from Equipment_Classes.OxfordITC4 import OxfordITC4

# Set logging level to WARNING (hides INFO messages)
logging.getLogger("pymeasure").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)


class MeasurementGUI:
    def __init__(self, master, sample_type, section, device_list, sample_gui):
        self.measurment_number = None
        self.sweep_num = None
        self.master = tk.Toplevel(master)
        self.master.title("Measurement Setup")
        self.master.geometry("1800x1000")
        #200+100
        self.sample_gui = sample_gui
        self.current_index = self.sample_gui.current_index
        self.load_messaging_data()
        self.psu_visa_address = "USB0::0x05E6::0x2220::9210734::INSTR"
        self.temp_controller_address= 'ASRL12::INSTR'
        self.keithley_address = "GPIB0::24::INSTR"
        self.axis_font_size = 8
        self.title_font_size = 10

        # Device name's
        self.sample_type = sample_type
        self.section = section  # redudntant i think
        self.device_list = device_list
        self.current_device = self.device_list[self.current_index]
        self.device_section_and_number = self.convert_to_name(self.current_index)
        self.display_index_section_number = self.current_device + "/" + self.device_section_and_number

        # Flags
        self.connected = False
        self.keithley = None  # Keithley instance
        self.psu_connected = False
        self.adaptive_measurement = None
        self.single_device_flag = True
        self.stop_measurement_flag = False
        self.get_messaged_var = False
        self.measuring = False
        self.not_at_tempriture = False
        self.itc_connected = False

        # Data storage
        self.measurement_data = {}  # Store measurement results
        self.v_arr_disp = []
        self.v_arr_disp_abs = []
        self.v_arr_disp_abs_log = []
        self.c_arr_disp = []
        self.c_arr_disp_log = []
        self.t_arr_disp = []
        self.c_arr_disp_abs = []
        self.c_arr_disp_abs_log = []
        self.r_arr_disp = []
        self.temp_time_disp = []


        # Load custom sweeps from JSON
        self.custom_sweeps = self.load_custom_sweeps("Json_Files/Custom_Sweeps.json")
        self.test_names = list(self.custom_sweeps.keys())
        self.code_names = {name: self.custom_sweeps[name].get("code_name") for name in self.test_names}

        # Container frames
        self.left_frame = tk.Frame(self.master)
        self.left_frame.grid(row=1, column=0, sticky="nsew",padx=0, pady=0)

        self.right_frame = tk.Frame(self.master)
        self.right_frame.grid(row=1, column=1, sticky="nsew", padx=0, pady=0)

        self.top_frame = tk.Frame(self.master)
        self.top_frame.grid(row=0, column=0, columnspan=2, sticky="nsew",padx=0, pady=0)

        # Make the columns expand
        # self.master.columnconfigure(0, weight=1)
        # self.master.columnconfigure(1, weight=2)
        # self.master.rowconfigure(0, weight=1)

        # layout
        # left frame
        self.create_connection_section(self.left_frame)
        self.create_mode_selection(self.left_frame)
        self.create_sweep_parameters(self.left_frame)
        self.create_status_box(self.left_frame)
        self.create_custom_measurement_section(self.left_frame)
        self.signal_messaging(self.left_frame)
        self.temp_measurments(self.left_frame)

        # right frame

        self.graphs_main_iv(self.right_frame) # main
        self.graphs_all(self.right_frame)
        self.graphs_current_time_rt(self.right_frame)
        self.graphs_resistance_time_rt(self.right_frame)
        self.graphs_temp_time_rt(self.right_frame)
        self.graphs_endurance_retention(self.right_frame)
        self.graphs_vi_logiv(self.right_frame)

        self.top_banner(self.top_frame)

        # # ohno
        # self.adaptive_button = tk.Button(self.master, text="oh no", command=self.ohno)
        # self.adaptive_button.grid(row=9, column=2, columnspan=2, pady=10)
        #
        # # Adaptive melody
        # self.adaptive_button = tk.Button(self.master, text="Song", command=self.play_melody)
        # self.adaptive_button.grid(row=10, column=3, columnspan=2, pady=10)

        # list all GPIB Devices
        # find kiethely smu assign to correct

        # connect to kiethley's
        self.connect_keithley()
        self.connect_keithley_psu()

        atexit.register(self.cleanup)



    def cleanup(self):
        self.keithley.shutdown()
        # todo send comand to temp if connected to cool down to 0
        if self.itc_connected:
            self.itc.set_temperature(0) # set temp controller tp 0 deg
        if self.psu_connected:
            self.psu.disable_channel(1)
            self.psu.disable_channel(2)
            self.psu.close()
        print("safely turned everything off")
    ###################################################################
    # Frames
    ###################################################################
    def top_banner(self, parent):
        top_frame = tk.LabelFrame(parent, text="", padx=10, pady=10)
        top_frame.grid(row=0, column=0, columnspan=2, sticky="nsew", pady=(10, 5))
        top_frame.columnconfigure(0, weight=1)
        top_frame.columnconfigure(1, weight=1)

        # Big bold title
        title_label = tk.Label(
            top_frame,
            text="CRAIG'S CRAZY FUN IV CONTROL PANEL",
            font=("Helvetica", 12, "bold"),
            fg="black"
        )
        title_label.grid(row=0, column=0, columnspan=2, pady=5, sticky="w")

        # Info display
        info_frame = tk.Frame(top_frame)
        info_frame.grid(row=0, column=2, columnspan=4, sticky="ew")
        info_frame.columnconfigure([0, 1, 2], weight=1)

        # Device
        self.device_label = tk.Label(info_frame, text="Device: XYZ", font=("Helvetica", 12))
        self.device_label.grid(row=0, column=0, padx=10, sticky="w")

        # Voltage
        self.voltage_label = tk.Label(info_frame, text="Voltage: 1.23 V", font=("Helvetica", 12))
        self.voltage_label.grid(row=0, column=1, padx=10, sticky="w")

        # Loop
        self.loop_label = tk.Label(info_frame, text="Loop: 5", font=("Helvetica", 12))
        self.loop_label.grid(row=0, column=2, padx=10, sticky="w")

        # Show last sweeps button
        self.show_results_button = tk.Button(info_frame, text="Show Last Sweeps", command=self.show_last_sweeps)
        self.show_results_button.grid(row=0, column=6, columnspan=1, pady=5)

        # Show last sweeps button
        self.show_results_button = tk.Button(info_frame, text="check_connection", command=self.check_connection)
        self.show_results_button.grid(row=0, column=7, columnspan=1, pady=5)

    ###################################################################
    # Graph empty shells setting up for plotting
    ###################################################################
    def graphs_main_iv(self, parent):
        """Single Iv Plot"""
        frame = tk.LabelFrame(parent, text="Current Measurement", padx=5, pady=5)
        frame.grid(row=0, column=1, rowspan=2, padx=10, pady=5, sticky="nsew")

        self.figure_rt_iv, self.ax_rt_iv = plt.subplots(figsize=(3, 3))
        self.ax_rt_iv.set_title("IV", fontsize=self.title_font_size)
        self.ax_rt_iv.set_xlabel("Voltage (V)", fontsize=self.axis_font_size)
        self.ax_rt_iv.set_ylabel("Current", fontsize=self.axis_font_size)

        self.canvas_rt_iv = FigureCanvasTkAgg(self.figure_rt_iv, master=frame)
        self.canvas_rt_iv.get_tk_widget().grid(row=0, column=0, columnspan=5, sticky="nsew")

        self.figure_rt_logiv, self.ax_rt_logiv = plt.subplots(figsize=(3, 3))
        self.ax_rt_logiv.set_title("Log IV", fontsize=self.title_font_size)
        self.ax_rt_logiv.set_xlabel("Voltage (V)", fontsize=self.axis_font_size)
        self.ax_rt_logiv.set_ylabel("Current", fontsize=self.axis_font_size)
        self.ax_rt_logiv.set_yscale('log')

        self.canvas_rt_logiv = FigureCanvasTkAgg(self.figure_rt_logiv, master=frame)
        self.canvas_rt_logiv.get_tk_widget().grid(row=0, column=5, columnspan=5, sticky="nsew")

        # Configure the frame layout
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self.line_rt_iv, = self.ax_rt_iv.plot([], [], marker='.')  # if different from vi_logilogv
        self.line_rt_logiv, = self.ax_rt_logiv.plot([], [], marker='.')

        # Start the plotting thread
        self.measurement_iv_thread = threading.Thread(target=self.plot_voltage_current)
        self.measurement_iv_thread.daemon = True
        self.measurement_iv_thread.start()

    def graphs_all(self, parent):
        """Matplotlib figure for plotting"""
        frame = tk.LabelFrame(parent, text="Last Measurement Plot", padx=5, pady=5)
        frame.grid(row=0, column=2, rowspan=2, padx=10, pady=5, sticky="nsew")

        self.figure_all_iv, self.ax_all_iv = plt.subplots(figsize=(3, 3))
        self.ax_all_iv.set_title("Iv - All", fontsize=self.title_font_size)
        self.ax_all_iv.set_xlabel("Voltage (V)", fontsize=self.axis_font_size)
        self.ax_all_iv.set_ylabel("Current", fontsize=self.axis_font_size)
        self.figure_all_iv.tight_layout()  # Adjust layout

        self.canvas_all_iv = FigureCanvasTkAgg(self.figure_all_iv, master=frame)
        self.canvas_all_iv.get_tk_widget().grid(row=0, column=0, pady=5, sticky="nsew")

        self.figure_all_logiv, self.ax_all_logiv = plt.subplots(figsize=(3, 3))
        self.ax_all_logiv.set_title("Log Plot - All", fontsize=self.title_font_size)
        self.ax_all_logiv.set_xlabel("Voltage (V)", fontsize=self.axis_font_size)
        self.ax_all_logiv.set_ylabel("abs(Current)", fontsize=self.axis_font_size)
        self.ax_all_logiv.set_yscale('log')
        self.figure_all_logiv.tight_layout()  # Adjust layout

        self.canvas_all_logiv = FigureCanvasTkAgg(self.figure_all_logiv, master=frame)
        self.canvas_all_logiv.get_tk_widget().grid(row=0, column=1, pady=5, sticky="nsew")

        # Configure the frame layout
        # frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)  # Ensure equal space for both plots
        frame.rowconfigure(0, weight=1)

        # Show last sweeps button
        self.show_results_button = tk.Button(frame, text="Ax1 Clear", command=lambda: self.clear_axis(2))
        self.show_results_button.grid(row=1, column=0, columnspan=1, pady=5)

        # Show last sweeps button
        self.show_results_button = tk.Button(frame, text="Ax2 Clear", command=lambda: self.clear_axis(3))
        self.show_results_button.grid(row=1, column=1, columnspan=1, pady=5)

    def graphs_vi_logiv(self, parent):
        """Single Iv Plot"""
        frame = tk.LabelFrame(parent, text="Current Measurement", padx=5, pady=5)
        frame.grid(row=2, column=1, rowspan=3, padx=10, pady=5, sticky="nsew")

        # V/I
        self.figure_rt_vi, self.ax_rt_vi = plt.subplots(figsize=(3, 3))
        self.ax_rt_vi.set_title("V/I",fontsize=self.title_font_size)
        self.ax_rt_vi.set_xlabel("Current(A)",fontsize=self.axis_font_size)
        self.ax_rt_vi.set_ylabel("Voltage (V)",fontsize=self.axis_font_size)

        self.canvas_rt_vi = FigureCanvasTkAgg(self.figure_rt_vi, master=frame)
        self.canvas_rt_vi.get_tk_widget().grid(row=0, column=0, rowspan =3,columnspan=1, sticky="nsew")

        # LOGI/LOGV X2
        self.figure_rt_logilogv, self.ax_rt_logilogv = plt.subplots(figsize=(3, 3))
        self.ax_rt_logilogv.set_title("LogI/LogV",fontsize=self.title_font_size)
        self.ax_rt_logilogv.set_xlabel("Voltage (V)",fontsize=self.axis_font_size)
        self.ax_rt_logilogv.set_ylabel("Current",fontsize=self.axis_font_size)
        self.ax_rt_logilogv.set_yscale('log')
        self.ax_rt_logilogv.set_xscale('log')

        # set up plot lines
        self.line_rt_vi, = self.ax_rt_vi.plot([], [], marker='.')
        self.line_rt_logilogv, = self.ax_rt_logilogv.plot([], [], marker='.', color='r')

        self.canvas_rt_logilogv = FigureCanvasTkAgg(self.figure_rt_logilogv, master=frame)
        self.canvas_rt_logilogv.get_tk_widget().grid(row=0, column=1, rowspan =3,columnspan=1, sticky="nsew")

        # Configure the frame layout
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        # Start the plotting thread
        self.measurement_vi_logilogv_thread = threading.Thread(target=self.plot_vi_logilogv)
        self.measurement_vi_logilogv_thread.daemon = True
        self.measurement_vi_logilogv_thread.start()

    def graphs_endurance_retention(self, parent):
        frame = tk.LabelFrame(parent, text="Endurance & Retention", padx=5, pady=5)
        frame.grid(row=3, column=2, padx=10, pady=5, columnspan=1, rowspan=1, sticky="ew")

        self.figure_rt_er, self.ax_rt_er = plt.subplots(figsize=(4, 2))
        self.ax_rt_er.set_title("Endurance")
        self.ax_rt_er.set_xlabel("Time (s)",fontsize=self.axis_font_size)
        self.ax_rt_er.set_ylabel("Currnet (ohm)",fontsize=self.axis_font_size)

        self.canvas_rt_er = FigureCanvasTkAgg(self.figure_rt_er, master=frame)
        self.canvas_rt_er.get_tk_widget().grid(row=0, column=0, columnspan=1, sticky="nsew")

        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        # # Start the plotting thread
        # self.measurement_ER_thread = threading.Thread(target=self.plot_resistance_time)
        # self.measurement_ER_thread.daemon = True
        # self.measurement_ER_thread.start()

    def graphs_current_time_rt(self, parent):
        frame = tk.LabelFrame(parent, text="Current time", padx=5, pady=5)
        frame.grid(row=5, column=1, padx=10, pady=5, columnspan=1, rowspan=1, sticky="ew")

        self.figure_ct_rt, self.ax_ct_rt = plt.subplots(figsize=(3, 2))
        self.ax_ct_rt.set_title("Current_time",fontsize=self.title_font_size)
        self.ax_ct_rt.set_xlabel("Time (s)",fontsize=self.axis_font_size)
        self.ax_ct_rt.set_ylabel("Current (A)",fontsize=self.axis_font_size)

        self.canvas_ct_rt = FigureCanvasTkAgg(self.figure_ct_rt, master=frame)
        self.canvas_ct_rt.get_tk_widget().grid(row=0, column=0, columnspan=2, sticky="nsew")

        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)


        self.line_ct_rt, = self.ax_ct_rt.plot([], [], marker='.')

        # Start the plotting thread
        self.measurement_ct_thread = threading.Thread(target=self.plot_current_time)
        self.measurement_ct_thread.daemon = True
        self.measurement_ct_thread.start()

    def graphs_resistance_time_rt(self, parent):
        frame = tk.LabelFrame(parent, text="Resistance time", padx=5, pady=5)
        frame.grid(row=5, column=2, padx=10, pady=5, columnspan=2, rowspan=1, sticky="ew")

        self.figure_rt_rt, self.ax_rt_rt = plt.subplots(figsize=(3, 2))
        self.ax_rt_rt.set_title("Resistance time Plot",fontsize=self.title_font_size)
        self.ax_rt_rt.set_xlabel("Time (s)",fontsize=self.axis_font_size)
        self.ax_rt_rt.set_ylabel("Resistance (ohm)",fontsize=self.axis_font_size)

        self.canvas_rt_rt = FigureCanvasTkAgg(self.figure_rt_rt, master=frame)
        self.canvas_rt_rt.get_tk_widget().grid(row=0, column=0, columnspan=1, sticky="nsew")

        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self.line_rt_rt, = self.ax_rt_rt.plot([], [], marker='.')

        # Start the plotting thread
        self.measurement_rt_thread = threading.Thread(target=self.plot_resistance_time)
        self.measurement_rt_thread.daemon = True
        self.measurement_rt_thread.start()

    def graphs_temp_time_rt(self, parent):

        frame = tk.LabelFrame(parent, text="temperature time", padx=0, pady=0)
        frame.grid(row=4, column=2, padx=10, pady=5, columnspan=1, rowspan=1, sticky="ew")

        if self.itc_connected:
            self.figure_tt_rt, self.ax_tt_rt = plt.subplots(figsize=(2, 1))
            self.ax_tt_rt.set_title("Temp time Plot",fontsize=self.title_font_size)
            self.ax_tt_rt.set_xlabel("Time (s)",fontsize=self.axis_font_size)
            self.ax_tt_rt.set_ylabel("Temp (T)",fontsize=self.axis_font_size)

            self.canvas_tt_rt = FigureCanvasTkAgg(self.figure_rt_rt, master=frame)
            self.canvas_tt_rt.get_tk_widget().grid(row=0, column=0, columnspan=1, sticky="nsew")

            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(0, weight=1)

            self.line_tt_rt, = self.ax_tt_rt.plot([], [], marker='x')

            # Start the plotting thread
            self.measurement_tt_thread = threading.Thread(target=self.plot_Temp_time)
            self.measurement_tt_thread.daemon = True
            self.measurement_tt_thread.start()
        else:
            # Greyed out placeholder (e.g., label or empty canvas)
            label = tk.Label(frame, text="Temp plot disabled", fg="grey")
            label.grid(row=0, column=0, sticky="nsew")
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(0, weight=1)

    ###################################################################
    #   Real time plotting
    ###################################################################

    def plot_current_time(self):
        while True:
            if self.measuring:
                self.line_ct_rt.set_data(self.t_arr_disp, self.c_arr_disp)
                self.ax_ct_rt.relim()
                self.ax_ct_rt.autoscale_view()
                self.canvas_ct_rt.draw()
            time.sleep(0.1)

    def plot_vi_logilogv(self):
        while True:
            if self.measuring:
                self.line_rt_vi.set_data(self.c_arr_disp, self.v_arr_disp)
                self.ax_rt_vi.relim()
                self.ax_rt_vi.autoscale_view()
                self.canvas_rt_vi.draw()

                if np.any(np.array(self.v_arr_disp_abs) > 0) and np.any(np.isfinite(self.c_arr_disp)):
                    # it never makes it into here!
                    self.line_rt_logilogv.set_data(self.v_arr_disp, self.c_arr_disp)
                    self.ax_rt_logilogv.relim()
                    self.ax_rt_logilogv.autoscale_view()
                    self.canvas_rt_logilogv.draw()

            time.sleep(0.1)

    def plot_voltage_current(self):
        while True:
            if self.measuring:
                self.line_rt_iv.set_data(self.v_arr_disp, self.c_arr_disp)
                self.ax_rt_iv.relim()
                self.ax_rt_iv.autoscale_view()
                self.canvas_rt_iv.draw()

                self.line_rt_logiv.set_data(self.v_arr_disp, self.c_arr_disp_abs)
                self.ax_rt_logiv.relim()
                self.ax_rt_logiv.autoscale_view()
                self.canvas_rt_logiv.draw()

            time.sleep(0.1)

    def plot_resistance_time(self):
        while True:
            if self.measuring:
                self.line_rt_rt.set_data(self.t_arr_disp, self.r_arr_disp)
                self.ax_rt_rt.relim()
                self.ax_rt_rt.autoscale_view()
                self.canvas_rt_rt.draw()
            time.sleep(0.1)

    def plot_Temp_time(self):
        while True:
            if self.measuring:
                self.line_tt_rt.set_data(self.t_arr_disp, self.c_arr_disp)
                self.ax_tt_rt.relim()
                self.ax_tt_rt.autoscale_view()
                self.canvas_tt_rt.draw()
            time.sleep(0.1)

    ###################################################################

    ###################################################################
    def create_connection_section(self,parent):
        """Keithley connection section"""
        frame = tk.LabelFrame(parent, text="Keithley Connection", padx=5, pady=5)
        frame.grid(row=0, column=0, padx=10, pady=5, sticky="ew")

        # add dropdowns to connect too each

        tk.Label(frame, text="GPIB Address - Iv:").grid(row=0, column=0, sticky="w")
        self.keithley_address_var = tk.StringVar(value=self.keithley_address)
        self.address_entry = tk.Entry(frame, textvariable=self.keithley_address_var)
        self.address_entry.grid(row=0, column=1)

        self.connect_button = tk.Button(frame, text="Connect", command=self.connect_keithley)
        self.connect_button.grid(row=0, column=2)

        tk.Label(frame, text="GPIB Address - PSU:").grid(row=1, column=0, sticky="w")
        self.address_var = tk.StringVar(value=self.psu_visa_address)
        self.address_entry = tk.Entry(frame, textvariable=self.address_var)
        self.address_entry.grid(row=1, column=1)

        self.connect_button = tk.Button(frame, text="Connect", command=self.connect_keithley_psu)
        self.connect_button.grid(row=1, column=2)

        tk.Label(frame, text="GPIB Address - Temp:").grid(row=2, column=0, sticky="w")
        self.address_var = tk.StringVar(value=self.temp_controller_address)
        self.address_entry = tk.Entry(frame, textvariable=self.address_var)
        self.address_entry.grid(row=2, column=1)

        self.connect_button = tk.Button(frame, text="Connect", command=self.connect_temp_controller)
        self.connect_button.grid(row=2, column=2)

    def create_mode_selection(self,parent):
        """Mode selection section"""
        # Create a frame for mode selection
        mode_frame = tk.LabelFrame(parent, text="Mode Selection", padx=5, pady=5)
        mode_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        # Toggle switch: Measure one device
        self.measure_one_device_label = tk.Label(mode_frame, text="Measure One Device?")
        self.measure_one_device_label.grid(row=0, column=0, sticky="w")

        # when this is changed to meausure all at once (value = 0) set self.measure_one_device to false
        self.adaptive_var = tk.IntVar(value=1)
        self.adaptive_switch = ttk.Checkbutton(
            mode_frame, variable=self.adaptive_var, command=self.measure_one_device
        )
        self.adaptive_switch.grid(row=0, column=1, columnspan=1)

        # Current Device Label
        self.current_device_label = tk.Label(mode_frame, text="Current Device:")
        self.current_device_label.grid(row=1, column=0, sticky="w")

        self.device_var = tk.Label(
            mode_frame, text=self.display_index_section_number, relief=tk.SUNKEN, anchor="w", width=20
        )
        self.device_var.grid(row=1, column=1, columnspan=1, sticky="ew")

        # Sample Name Entry
        self.sample_name_label = tk.Label(mode_frame, text="Sample Name (for saving):")
        self.sample_name_label.grid(row=2, column=0, sticky="w")

        self.sample_name_var = tk.StringVar()  # Use a StringVar
        self.sample_name_entry = ttk.Entry(mode_frame, textvariable=self.sample_name_var)
        self.sample_name_entry.grid(row=2, column=1, columnspan=1, sticky="ew")

    def create_sweep_parameters(self,parent):
        """Sweep parameter section"""
        frame = tk.LabelFrame(parent, text="Sweep Parameters", padx=5, pady=5)
        frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")

        tk.Label(frame, text="Start Voltage (V):").grid(row=0, column=0, sticky="w")
        self.start_voltage = tk.DoubleVar(value=0)
        tk.Entry(frame, textvariable=self.start_voltage).grid(row=0, column=1)

        tk.Label(frame, text="Voltage High (V):").grid(row=1, column=0, sticky="w")
        self.voltage_high = tk.DoubleVar(value=1)
        tk.Entry(frame, textvariable=self.voltage_high).grid(row=1, column=1)

        tk.Label(frame, text="Step Size (V):").grid(row=2, column=0, sticky="w")
        self.step_size = tk.DoubleVar(value=0.1)
        tk.Entry(frame, textvariable=self.step_size).grid(row=2, column=1)

        tk.Label(frame, text="Step Delay (S):").grid(row=3, column=0, sticky="w")
        self.step_delay = tk.DoubleVar(value=0.05)
        tk.Entry(frame, textvariable=self.step_delay).grid(row=3, column=1)

        tk.Label(frame, text="# Sweeps:").grid(row=4, column=0, sticky="w")
        self.sweeps = tk.DoubleVar(value=1)
        tk.Entry(frame, textvariable=self.sweeps).grid(row=4, column=1)


        tk.Label(frame, text="Icc:").grid(row=5, column=0, sticky="w")
        self.icc = tk.DoubleVar(value=0.1)
        tk.Entry(frame, textvariable=self.icc).grid(row=5, column=1)

        tk.Label(frame, text="Pause at end?:").grid(row=6, column=0, sticky="w")
        self.pause = tk.DoubleVar(value=0.0)
        tk.Entry(frame, textvariable=self.pause).grid(row=6, column=1)

        # self.led = tk.IntVar(value=0)
        # self.led = ttk.Checkbutton(frame, variable=self.led_toggle)
        # self.led.grid(row=6, column=1, columnspan=1)

        tk.Label(frame, text="Led (0=OFF,1=ON) :").grid(row=7, column=0, sticky="w")
        self.led = tk.DoubleVar(value=0)
        tk.Entry(frame, textvariable=self.led).grid(row=7, column=1)

        tk.Label(frame, text="Led_Power (0-1):").grid(row=8, column=0, sticky="w")
        self.led_power = tk.DoubleVar(value=1)
        tk.Entry(frame, textvariable=self.led_power).grid(row=8, column=1)

        tk.Label(frame, text="Sequence: (01010)").grid(row=9, column=0, sticky="w")
        self.sequence  = tk.StringVar()
        tk.Entry(frame, textvariable=self.sequence).grid(row=9, column=1)

        def start_thread():
            self.measurement_thread = threading.Thread(target=self.start_measurement)
            self.measurement_thread.daemon = True
            self.measurement_thread.start()

        self.measure_button = tk.Button(frame, text="Start Measurement", command=start_thread)
        self.measure_button.grid(row=10, column=0, columnspan=1, pady=5)

        # stop button
        self.adaptive_button = tk.Button(frame, text="Stop Measurement!", command=self.set_measurment_flag_true)
        self.adaptive_button.grid(row=10, column=1, columnspan=1, pady=10)

    def set_measurment_flag_true(self):
        self.stop_measurement_flag = True
    def create_custom_measurement_section(self,parent):
        """Custom measurements section"""
        frame = tk.LabelFrame(parent, text="Custom Measurements", padx=5, pady=5)
        frame.grid(row=3, column=0, padx=10, pady=5, sticky="ew")

        # Drop_down menu
        tk.Label(frame, text="Custom Measurement:").grid(row=0, column=0, sticky="w")
        self.custom_measurement_var = tk.StringVar(value=self.test_names[0] if self.test_names else "Test")
        self.custom_measurement_menu = ttk.Combobox(frame, textvariable=self.custom_measurement_var,
                                                    values=self.test_names)
        self.custom_measurement_menu.grid(row=0, column=1, padx=5)

        # compliance current Data entry
        tk.Label(frame, text="Icc (A):").grid(row=1, column=0, sticky="w")
        self.icc = tk.DoubleVar(value=0.1)
        tk.Entry(frame, textvariable=self.icc).grid(row=1, column=1)

        def start_thread():
            self.measurement_thread = threading.Thread(target=self.run_custom_measurement)
            self.measurement_thread.daemon = True
            self.measurement_thread.start()

        # Run button
        self.run_custom_button = tk.Button(frame, text="Run Custom", command=start_thread)
        self.run_custom_button.grid(row=2, column=0, columnspan=2, pady=5)

    def signal_messaging(self,parent):
        frame = tk.LabelFrame(parent, text="Signal_Messaging", padx=5, pady=5)
        frame.grid(row=5, column=0, rowspan=2, padx=10, pady=5, sticky="nsew")

        # Toggle switch: Measure one device
        tk.Label(frame, text="Do you want to use the bot?").grid(row=0, column=0, sticky="w")
        self.get_messaged_var = tk.IntVar(value=0)
        self.get_messaged_switch = ttk.Checkbutton(frame, variable=self.get_messaged_var)
        self.get_messaged_switch.grid(row=0, column=1)

        # Dropdown menu for user selection
        tk.Label(frame, text="Who's Using this?").grid(row=2, column=0, sticky="w")
        self.selected_user = tk.StringVar(value="Choose name" if self.names else "No_Name")
        self.custom_measurement_menu = ttk.Combobox(frame, textvariable=self.selected_user,
                                                    values=self.names, state="readonly")
        self.custom_measurement_menu.grid(row=2, column=1, padx=5)
        self.custom_measurement_menu.bind("<<ComboboxSelected>>", self.update_messaging_info)

        # # Compliance current Data entry
        # tk.Label(frame, text="empty:").grid(row=3, column=0, sticky="w")
        # self.icc = tk.DoubleVar(value=0.01)
        # tk.Entry(frame, textvariable=self.icc).grid(row=3, column=1)

        # # Labels to display token and chat ID
        # tk.Label(frame, text="Token:").grid(row=4, column=0, sticky="w")
        self.token_var = tk.StringVar(value="")
        # tk.Label(frame, textvariable=self.token_var).grid(row=4, column=1, sticky="w")

        # tk.Label(frame, text="Chat ID:").grid(row=4, column=0, sticky="w")
        self.chatid_var = tk.StringVar(value="")
        # tk.Label(frame, textvariable=self.chatid_var).grid(row=4, column=1, sticky="w")

    def create_status_box(self,parent):
        """Status box section"""
        frame = tk.LabelFrame(parent, text="Status", padx=5, pady=5)
        frame.grid(row=4, column=0, padx=10, pady=5, sticky="ew")

        self.status_box = tk.Label(frame, text="Status: Not Connected", relief=tk.SUNKEN, anchor="w", width=40)
        self.status_box.pack(fill=tk.X)

    def connect_temp_sensor(self):
        print("connecting to temp controller")
        self.connect_temp_controller()

    def temp_measurments(self, parent):
        # Temperature section
        frame = tk.LabelFrame(parent, text="temp_measurments", padx=5, pady=5)
        frame.grid(row=9, column=0, padx=10, pady=5, sticky="ew")

        # temp entry
        self.temp_label = tk.Label(frame, text="Set_temp:")
        self.temp_label.grid(row=1, column=0, sticky="w")

        self.temp_var = tk.StringVar()  # Use a StringVar
        self.temp_var_entry = ttk.Entry(frame, textvariable=self.temp_var)
        self.temp_var_entry.grid(row=1, column=1, columnspan=1, sticky="ew")

        # button
        self.temp_go_button = tk.Button(frame, text="Apply", command=self.send_temp)
        self.temp_go_button.grid(row=1, column=2)

    ###################################################################
    # All Measurment acquisition code
    ###################################################################

    def measure(self, voltage_range, sweeps, step_delay, led=0, power=1, sequence=None, pause=0):
        """Start measurement for device.

        Parameters:
            voltage_range : iterable of voltages to apply.
            sweeps        : number of sweeps to perform.
            step_delay    : delay between each voltage step.
            led           : if 1, LED will be controlled (default: 0 = off).
            power         : LED power level between 0-1.
            sequence      : optional string like '0101' determining LED status per sweep.
        """
        self.stop_measurement_flag = False

        if sequence is not None:
            sequence = str(sequence)

        start_time = time.time()
        v_arr = []
        c_arr = []
        c_arr_abs = []

        self.v_arr_disp = []
        self.v_arr_disp_abs = []
        self.v_arr_disp_abs_log = []
        self.c_arr_disp = []
        self.c_arr_disp_log = []
        self.t_arr_disp = []
        self.c_arr_disp_abs = []
        self.c_arr_disp_abs_log = []
        self.r_arr_disp = []
        self.temp_time_disp = []

        time_stamps = []
        icc = self.icc.get()
        v_max = np.max(voltage_range)
        v_min = np.min(voltage_range)

        previous_v = 0

        for sweep_num in range(int(sweeps)):
            self.sweep_num = sweep_num

            # Determine LED state for this sweep
            led_state = '1' if led == 1 else '0'  # default if no sequence is given
            if sequence and sweep_num < len(sequence):
                led_state = sequence[sweep_num]

            if led_state == '1':
                self.psu.led_on_380(power)
            else:
                self.psu.led_off_380()

            if self.stop_measurement_flag:  # Check if stop was pressed
                print("Measurement interrupted!")
                break  # Exit measurement loop immediately

            for v in voltage_range:
                self.keithley.set_voltage(v, icc)
                time.sleep(0.1)  # Allow measurement to settle

                current = self.keithley.measure_current()
                measure_time = time.time() - start_time

                # append information
                v_arr.append(v)
                c_arr.append(current[1])
                time_stamps.append(measure_time)




                # appending info for real time graphs.
                self.v_arr_disp.append(v)
                self.v_arr_disp_abs.append(abs(v))
                #self.v_arr_disp_abs_log.append(np.log(abs(v)))
                self.c_arr_disp.append(current[1])
                #self.c_arr_disp_log.append(np.log(current[1]))
                self.c_arr_disp_abs.append(abs(current[1]))
                self.c_arr_disp_abs_log.append(np.log(abs(current[1])))
                self.t_arr_disp.append(measure_time)
                self.r_arr_disp.append(zero_devision_check(v,current[1]))


                time.sleep(step_delay)

                # pause feature at v_max
                if v == v_max or v == v_min:
                    if v != previous_v:
                        if pause != 0:
                            self.keithley.set_voltage(0, icc)
                            print('pausing for',pause," seconds")
                            time.sleep(pause)
                previous_v = v
        self.psu.led_off_380()  # ensure LED is off at the end
        return v_arr, c_arr, time_stamps

    def run_custom_measurement(self):
        """ when custom measurements has been ran"""


        if not self.connected:
            messagebox.showwarning("Warning", "Not connected to Keithley!")
            return

        if self.single_device_flag:
            response = messagebox.askquestion(
                "Did you choose the correct device?",
                "Please make sure the correct device is selected.\nClick 'Yes' if you are sure.\nIf not you will be "
                "saving over old data")
            if response != 'yes':
                return
        self.measuring = True

        self.stop_measurement_flag = False

        # make sure it is on the top
        self.bring_to_top()

        # checks for sample name if not prompts user
        self.check_for_sample_name()

        selected_measurement = self.custom_measurement_var.get()
        print(f"Running custom measurement: {selected_measurement}")

        print(self.get_messaged_var)
        # use the bot to send a message
        a = self.get_messaged_var.get()
        #b = self.get_messaged_switch.get()
        print(a)
        if self.get_messaged_var.get() == 1:
            bot = TelegramBot(self.token_var.get(), self.chatid_var.get())
            var = self.custom_measurement_var.get()
            samle_name = self.sample_name_var.get()
            section = self.device_section_and_number
            text = f"Starting Measurements on {samle_name} device {section} "
            bot.send_message(text)  # Runs the coroutine properly

        if selected_measurement in self.custom_sweeps:
            if self.current_device in self.device_list:
                start_index = self.device_list.index(self.current_device)
            else:
                start_index = 0  # Default to the first device if current one is not found

            device_count = len(self.device_list)

            # looping through each device.
            for i in range(device_count):  # Ensure we process each device exactly once
                device = self.device_list[(start_index + i) % device_count]  # Wrap around when reaching the end

                self.status_box.config(text=f"Measuring {device}...")
                self.master.update()
                time.sleep(1)

                # Ensure Kiethley set correctly
                self.keithley.set_voltage(0, self.icc.get())  # Start at 0V
                self.keithley.enable_output(True)  # Enable output

                start = time.time()
                start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                sweeps = self.custom_sweeps[selected_measurement]["sweeps"]
                code_name = self.custom_sweeps[selected_measurement].get("code_name", "unknown")

                # checks psu connection if led required for measurement
                LED = False
                for key, params in sweeps.items():
                    LED = params.get("LED_ON", "OFF")
                    if LED:
                        if not self.psu_connected:
                            print("led used needs to be connected to psu")
                            messagebox.showwarning("Warning", "Not connected to PSU!")
                            time.sleep(1)
                            self.connect_keithley_psu()
                            break

                for key, params in sweeps.items():
                    if self.stop_measurement_flag:  # Check if stop was pressed
                        print("Measurement interrupted!")
                        break  # Exit measurement loop immediately

                    self.measurment_number = key
                    print("Working on device -", device, ": Measurement -", key)

                    # default values
                    start_v = params.get("start_v", 0)
                    stop_v = params.get("stop_v", 1)
                    sweeps = params.get("sweeps", 1)
                    step_v = params.get("step_v", 0.1)
                    step_delay = params.get("step_delay", 0.05)
                    sweep_type = params.get("Sweep_type", "FS")
                    pause = params.get('pause', 0)

                    # LED control
                    led = params.get("LED_ON", 0)
                    power = params.get("power", 1)  # Power Refers to voltage
                    sequence = params.get("sequence", 0)


                    # retention
                    set_voltage = params.get("set_voltage", 10)
                    reset_voltage = params.get("reset_voltage", 10)
                    repeat_delay = params.get("repeat_delay", 500) #ms
                    number = params.get("number", 100)
                    set_time = params.get("set_time",100)
                    read_voltage = params.get("read_voltage",0.15)
                    #led = params.get("LED_ON", 0)
                    # sequence
                    led_time = params.get("led_time", "100") # in seconds


                    if sequence == 0:
                        sequence = None

                    if led:
                        if not self.psu_connected:
                            messagebox.showwarning("Warning", "Not connected to PSU!")
                            self.connect_keithley_psu()

                    # add checker step where it checks if the devices current state and if ts ohmic or capacaive it stops

                    if sweep_type == "NS":
                        voltage_range = get_voltage_range(start_v, stop_v, step_v, sweep_type)
                        # print(sweep_type,voltage_range)
                        v_arr, c_arr, timestamps = self.measure(voltage_range, sweeps, step_delay, led, power, sequence,pause)
                    elif sweep_type == "PS":
                        voltage_range = get_voltage_range(start_v, stop_v, step_v, sweep_type)
                        # print(sweep_type,voltage_range)
                        v_arr, c_arr, timestamps = self.measure(voltage_range, sweeps, step_delay, led, power, sequence,pause)
                    elif sweep_type == "Endurance":
                        print("endurance")
                        #self.endurance_measure()
                    elif sweep_type == "Retention":
                        self.retention_measure(set_voltage,set_time,read_voltage,repeat_delay,number,sequence,led,led_time,pause)
                        print("retention")
                    # elif sweep_type == "FS_pause":
                    #     v_arr, c_arr, timestamps = self.measure(voltage_range, sweeps, step_delay, led, power, sequence)
                    else:  # sweep_type == "FS":
                        voltage_range = get_voltage_range(start_v, stop_v, step_v, sweep_type)
                        # print(sweep_type,voltage_range)
                        v_arr, c_arr, timestamps = self.measure(voltage_range, sweeps, step_delay, led, power, sequence,pause)

                    # this isnt being used yet i dont think
                    if device not in self.measurement_data:
                        self.measurement_data[device] = {}

                    self.measurement_data[device][key] = (v_arr, c_arr, timestamps)

                    # todo wrap this into a function for use on other method!!!

                    #self.keithley.beep(600, 1)

                    # data arry to save
                    data = np.column_stack((v_arr, c_arr, timestamps))

                    # creates save directory with the selected measurement device name letter and number
                    save_dir = f"Data_save_loc\\{self.sample_name_var.get()}\\{self.final_device_letter}" \
                               f"\\{self.final_device_number}"

                    # make directory if dost exist.
                    if not os.path.exists(save_dir):
                        os.makedirs(save_dir)

                    name = f"{key}-{sweep_type}-{stop_v}v-{step_v}sv-{step_delay}sd-Py-{code_name}-{sweeps}"
                    file_path = f"{save_dir}\\{name}.txt"

                    if os.path.exists(file_path):
                        print("filepath already exisits")
                        messagebox.showerror("ERROR", "file already exists, you should check before continueing as "
                                                      "this will overwrite")

                    np.savetxt(file_path, data, fmt="%0.3E\t%0.3E\t%0.3E", header="Voltage Current Time", comments="")

                    # show graphs on main display
                    self.graphs_show(v_arr, c_arr, key, stop_v)

                    # give time to sleep between measurements!
                    time.sleep(2)

                plot_filename_iv = f"{save_dir}\\All_graphs_IV.png"
                plot_filename_log = f"{save_dir}\\All_graphs_LOG.png"
                self.ax_all_iv.figure.savefig(plot_filename_iv, dpi=400)
                self.ax_all_logiv.figure.savefig(plot_filename_log, dpi=400)
                self.ax_all_iv.clear()
                self.ax_all_logiv.clear()
                self.keithley.enable_output(False)

                end = time.time()
                print("total time for ", selected_measurement, "=", end - start, " - ")

                self.create_log_file(save_dir, start_time, selected_measurement)

                if self.single_device_flag:
                    print("Measuring one device only")
                    break  # Exit measurement loop immediately

                self.sample_gui.next_device()

            if self.get_messaged_var.get() == 1:
                bot.send_message("Measurments Finished")

            try:
                bot.send_image(plot_filename_log,"Final_graphs_LOG")
            except:
                print("failed to send image")
            self.measuring = False
            self.status_box.config(text="Measurement Complete")
            messagebox.showinfo("Complete", "Measurements finished.")


        else:
            print("Selected measurement not found in JSON file.")

    def start_measurement(self):
        """Start single measurementt on the device! """

        if not self.connected:
            messagebox.showwarning("Warning", "Not connected to Keithley!")
            return
        self.measuring = True


        start_v = self.start_voltage.get()
        stop_v = self.voltage_high.get()
        sweeps = self.sweeps.get()
        step_v = self.step_size.get()
        sweep_type = "FS"
        step_delay = self.step_delay.get()
        icc = self.icc.get()
        device_count = len(self.device_list)
        pause = self.pause.get()

        led = self.led.get()
        led_power = self.led_power.get()
        sequence = self.sequence.get().strip()
        # if led != 1:
        #     led_power = 1
        # if led == 0:
        #     sequence = None

        voltage_range = get_voltage_range(start_v, stop_v, step_v, sweep_type)
        self.stop_measurement_flag = False  # Reset the stop flag

        # make sure it is on the top
        self.bring_to_top()

        # checks for sample name if not prompts user
        self.check_for_sample_name()

        # checks for the current device and the index for start
        if self.current_device in self.device_list:
            start_index = self.device_list.index(self.current_device)
        else:
            # Default to the first device if current one is not found
            start_index = 0

        for i in range(device_count):
            # loop through all the device, looping to start
            device = self.device_list[(start_index + i) % device_count]  # Wrap around when reaching the end

            if self.stop_measurement_flag:  # Check if stop was pressed
                print("Measurement interrupted!")
                break  # Exit measurement loop immediately

            self.keithley.set_voltage(0, self.icc.get())  # Start at 0V
            self.keithley.enable_output(True)  # Enable output

            print("working on device - ", device)
            self.status_box.config(text=f"Measuring {device}...")
            self.master.update()

            time.sleep(1)

            #def measure(self, voltage_range, sweeps, step_delay, led=0, power=1, sequence=None, pause=0):

            # measure device
            v_arr, c_arr, timestamps = self.measure(voltage_range, sweeps, step_delay, led, led_power, sequence,pause)

            # save data to file
            data = np.column_stack((v_arr, c_arr, timestamps))

            # creates save directory with the selected measurement device name letter and number
            save_dir = f"Data_save_loc\\{self.sample_name_var.get()}\\{self.final_device_letter}" \
                       f"\\{self.final_device_number}"

            # make directory if dost exist.
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)
            # find a way top extract key from previous device
            if sequence != "":
                additional = "-"+sequence
            else:
                additional =""

            key = find_largest_number_in_folder(save_dir)
            save_key = 0 if key is None else key + 1
            name = f"{save_key}-{sweep_type}-{stop_v}v-{step_v}sv-{step_delay}sd-Py-{sweeps}{additional}"
            file_path = f"{save_dir}\\{name}.txt"

            np.savetxt(file_path, data, fmt="%0.3E\t%0.3E\t%0.3E", header="Voltage Current Time", comments="")

            self.graphs_show(v_arr, c_arr, "1", stop_v)

            # Turn off output
            self.keithley.enable_output(False)

            if self.single_device_flag:  # Check if stop was pressed
                print("measuring one device only")
                break  # Exit measurement loop immediately

            # change device
            self.sample_gui.next_device()

        self.measuring = False
        self.status_box.config(text="Measurement Complete")
        messagebox.showinfo("Complete", "Measurements finished.")

    def retention_measure(self,set_voltage,set_time,read_voltage,repeat_delay,number,sequence,led,led_time):
        icc = 0.0001
        time_data = []
        current_data = []
        start_time = time.time()
        self.keithley.enable_output(True)

        #apply pulse
        self.keithley.set_voltage(set_voltage, icc)
        time.sleep(set_time)
        # apply read
        self.keithley.set_voltage(read_voltage, icc)

        for i in range(number):
            current_value = self.keithley.measure_current()
            elapsed_time = time.time() - start_time

            time_data.append(elapsed_time)
            current_data.append(current_value[1])
            time.sleep(repeat_delay)

            #add in an iteration for led

        self.keithley.shutdown()
        return current_data,time_data

    def send_temp(self):
        self.itc.set_temperature(int(self.temp_var.get()))
        self.graphs_temp_time_rt(self.right_frame)
        print("temperature set too", self.temp_var.get())

    def update_variables(self):
        # update current device
        self.current_device = self.device_list[self.current_index]
        # Update number (ie device_11)
        self.device_section_and_number = self.convert_to_name(self.current_index)
        # Update section and number
        self.display_index_section_number = self.current_device + "/" + self.device_section_and_number
        self.device_var.config(text=self.display_index_section_number)
        # print(self.convert_to_name(self.current_index))

    def measure_one_device(self):
        if self.adaptive_var.get():
            print("Measuring only one device")
            self.single_device_flag = True
        else:
            print("Measuring all devices")
            self.single_device_flag = False

    ###################################################################
    # Connect
    ###################################################################
    def connect_keithley(self):
        """Connect to the Keithley SMU via GPIB"""
        address = self.keithley_address_var.get()
        try:
            self.keithley = Keithley2400Controller(address)
            self.connected = True
            self.status_box.config(text="Status: Connected")
            # messagebox.showinfo("Connection", f"Connected to: {address}")
            self.keithley.beep(4000, 0.2)
            time.sleep(0.2)
            self.keithley.beep(5000, 0.5)


        except Exception as e:
            self.connected = False
            print("unable to connect to SMU please check")
            messagebox.showerror("Error", f"Could not connect to device: {str(e)}")

    def connect_keithley_psu(self):
        try:
            self.psu = Keithley2220_Powersupply(self.psu_visa_address)
            self.psu_connected = True
            self.keithley.beep(5000, 0.2)
            time.sleep(0.2)
            self.keithley.beep(6000, 0.2)

            self.psu.reset()  # reset psu
        except Exception as e:
            print("unable to connect to psu please check")
            messagebox.showerror("Error", f"Could not connect to device: {str(e)}")

    def connect_temp_controller(self):
        """Connect to the Keithley SMU via GPIB"""
        #address = self.address_var.get()
        address = self.temp_controller_address
        try:
            self.itc = OxfordITC4(port=address)
            self.itc_connected = True
            print("connected too Temp controller")
            #self.status_box.config(text="Status: Connected")
            # messagebox.showinfo("Connection", f"Connected to: {address}")
            self.keithley.beep(7000, 0.2)
            time.sleep(0.2)
            self.keithley.beep(8000, 0.2)

        except Exception as e:
            self.itc_connected = False
            print("unable to connect to Temp please check")
            messagebox.showerror("Error", f"Could not connect to temp device: {str(e)}")

    ###################################################################
    # Other Functions
    ###################################################################
    def update_last_sweeps(self):
        """Automatically updates the plot every 1000ms"""
        # Re-draw the latest data on the axes
        for i, (device, measurements) in enumerate(self.measurement_data.items()):
            if i >= 100:
                break  # Limit to 100 devices

            row, col = divmod(i, 10)  # Convert index to 10x10 grid position
            ax = self.axes[row, col]
            last_key = list(measurements.keys())[-1]  # Get the last sweep key
            v_arr, c_arr = measurements[last_key]
            ax.clear()  # Clear the old plot
            ax.plot(v_arr, c_arr, marker="o", markersize=1)

            # # Add labels to axes (you can adjust the label text and font size)
            # ax.set_xlabel('Voltage (V)', fontsize=6)  # X-axis label
            # ax.set_ylabel('Current (Across Ito)', fontsize=6)  # Y-axis label

            # Make tick labels visible and set font size
            ax.tick_params(axis='x', labelsize=6)  # X-axis tick labels font size
            ax.tick_params(axis='y', labelsize=6)  # Y-axis tick labels font size

            # Optionally, set limits or show minor ticks if needed
            ax.set_xticks(np.linspace(min(v_arr), max(v_arr), 3))  # Adjust the number of ticks
            ax.set_yticks(np.linspace(min(c_arr), max(c_arr), 3))  # Adjust the number of ticks

            ax.ticklabel_format(style='sci', axis='y', scilimits=(0, 0))
            ax.set_title(f"Device {device}", fontsize=6)

        self.canvas.draw()  # Redraw the canvas with the new data

        # Set the next update ( or 10 seconds)
        self.master.after(10000, self.update_last_sweeps)
    def check_for_sample_name(self):

        sample_name = self.sample_name_var.get().strip()

        if not sample_name:
            # Open a dialog box to get new sample name
            new_name = simpledialog.askstring("Update Sample Name", "Enter new sample name:", parent=self.master)

            # If the user entered a name and didn't cancel the dialog, update the Entry widget
            if new_name:
                self.sample_name_var.set(new_name)
            else:
                self.sample_name_var.set("undefined")

    def check_connection(self):
        self.connect_keithley()
        time.sleep(0.1)
        self.Check_connection_gui = CheckConnection(self.master, self.keithley)

    def open_adaptive_settings(self):
        if self.adaptive_measurement is None or not self.adaptive_measurement.master.winfo_exists():
            self.adaptive_measurement = AdaptiveMeasurement(self.master)

    def show_last_sweeps(self):
        """Creates a new window showing the last measurement for each device"""
        results_window = tk.Toplevel(self.master)
        results_window.title("Last Measurement for Each Device")
        results_window.geometry("800x600")

        figure, axes = plt.subplots(10, 10, figsize=(10, 10))  # 10x10 grid
        figure.tight_layout()
        figure.subplots_adjust(wspace=0.1, hspace=0.1)

        # Store the figure and axes for future updates
        self.figure = figure
        self.axes = axes
        self.results_window = results_window

        for i, (device, measurements) in enumerate(self.measurement_data.items()):
            if i >= 100:
                break  # Limit to 100 devices

            row, col = divmod(i, 10)  # Convert index to 10x10 grid position
            ax = self.axes[row, col]
            last_key = list(measurements.keys())[-1]  # Get the last sweep key
            v_arr, c_arr = measurements[last_key]

            ax.plot(v_arr, c_arr, marker="o", markersize=1)
            # ax.set_title(f"Device {device}", fontsize=5)

            # Add labels to axes (you can adjust the label text and font size)
            # ax.set_xlabel('Voltage (V)', fontsize=6)  # X-axis label
            # ax.set_ylabel('Current (Across Ito)', fontsize=6)  # Y-axis label

            # Make tick labels visible and set font size
            ax.tick_params(axis='x', labelsize=2)  # X-axis tick labels font size
            ax.tick_params(axis='y', labelsize=2)  # Y-axis tick labels font size

            # Optionally, set limits or show minor ticks if needed
            ax.set_xticks(np.linspace(min(v_arr), max(v_arr), 2))  # Adjust the number of ticks
            ax.set_yticks(np.linspace(min(c_arr), max(c_arr), 2))  # Adjust the number of ticks

            ax.ticklabel_format(style='sci', axis='y', scilimits=(0, 0))
            ax.set_title(f"Device {device}", fontsize=6)

        self.canvas = FigureCanvasTkAgg(self.figure, master=self.results_window)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.canvas.draw()

        # Start automatic update
        self.update_last_sweeps()

    def clear_axis(self, axis):
        # todo make the clear work correctly
        if axis == 2:
            self.ax_all_iv.clear()
            self.canvas.draw()  # Redraw the canvas
            self.master.update_idletasks()
            self.master.update()
        if axis == 3:
            self.ax_all_logiv.clear()
            self.ax_all_logiv.set_yscale('log')
            self.canvas.draw()  # Redraw the canvas
            self.master.update_idletasks()
            self.master.update()

    def spare_button(self):
        print("spare")

    def convert_to_name(self, device_number):
        if not (0 <= device_number <= 99):  # Adjusted range to start from 0
            print(device_number)
            raise ValueError("Device number must be between 0 and 99")

        # Define valid letters, excluding 'C' and 'J'
        valid_letters = [ch for ch in string.ascii_uppercase[:12] if ch not in {'C', 'J'}]

        index = device_number // 10  # Determine the letter group
        sub_number = (device_number % 10) + 1  # Determine the numeric suffix (1-10)

        # better name needed for these
        self.final_device_letter = valid_letters[index]
        self.final_device_number = sub_number

        return f"{valid_letters[index]}{sub_number}"

    def create_log_file(self, save_dir, start_time, measurement_type):
        # Get the current date and time
        end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        measurement_type = measurement_type

        # Open the log file in append mode
        with open(save_dir + '\\log.txt', 'a') as log_file:
            log_file.write(f"Measurement started at: {start_time}\n")
            log_file.write(f"Measurement ended at: {end_time}\n")
            log_file.write(f"Time Taken: {end_time}\n")

            log_file.write(f"Measurement Type: {measurement_type}\n")
            # log_file.write(f"Measurement Value: {measurement_value}\n")
            # log_file.write(f"Additional Info: {additional_info}\n")
            log_file.write("-" * 40 + "\n")  # Separator for readability

    def graphs_show(self, v_arr, c_arr, key, stop_v):

        # # plot on main screen! on #1
        # self.ax_rt_iv.clear()
        # self.ax_rt_iv.plot(v_arr, c_arr, marker='o', markersize=2, color='k')
        # self.canvas_rt_iv.draw()

        self.ax_all_iv.plot(v_arr, c_arr, marker='o', markersize=2, label=key + "_" + str(stop_v) + "v", alpha=0.8)
        self.ax_all_iv.legend(loc="best", fontsize="5")
        self.ax_all_logiv.plot(v_arr, np.abs(c_arr), marker='o', markersize=2, label=key + "_" + str(stop_v) + "v",
                               alpha=0.8)
        self.ax_all_logiv.legend(loc="best", fontsize="5")
        self.canvas_all_iv.draw()
        self.canvas_all_logiv.draw()
        self.master.update_idletasks()
        self.master.update()

    def load_custom_sweeps(self, filename):
        try:
            with open(filename, "r") as file:
                return json.load(file)
        except FileNotFoundError:
            print("Custom sweeps file not found.")
            return {}
        except json.JSONDecodeError:
            print("Error decoding JSON file.")
            return {}


    def bring_to_top(self):
        # If the window is already open, bring it to the front
        self.master.lift()  # Bring the GUI window to the front
        self.master.focus()  # Focus the window (optional, makes it active)

    def load_messaging_data(self):
        """Load user data (names, tokens, chat IDs) from a JSON file."""
        try:
            with open("Json_Files\\messaging_data.json", "r") as file:
                self.messaging_data = json.load(file)
                self.names = list(self.messaging_data.keys())  # Extract names
        except (FileNotFoundError, json.JSONDecodeError):
            self.messaging_data = {}
            self.names = []

    def update_messaging_info(self, event=None):
        """Update token and chat ID based on selected user."""
        user = self.selected_user.get()
        if user in self.messaging_data:
            print("Telegram Bot On")
            self.token_var.set(self.messaging_data[user]["token"])
            self.chatid_var.set(self.messaging_data[user]["chatid"])
        else:
            print("Telegram Bot off")
            self.token_var.set("N/A")
            self.chatid_var.set("N/A")
    def play_melody(self):
        """Plays a short melody using Keithley beep."""
        if not self.keithley:
            print("Keithley not connected, can't play melody!")
            return
        # star wars
        melody = [
            # Iconic opening (G-G-G-Eb)
            (392.00, 0.4), (392.00, 0.4), (392.00, 0.4), (311.13, 0.8),  # G4, G4, G4, Eb4
            # Response phrase (Bb-Across Ito-G-Eb)
            (466.16, 0.3), (440.00, 0.3), (392.00, 0.3), (311.13, 0.8),  # Bb4, A4, G4, Eb4
            # Repeat opening
            (392.00, 0.4), (392.00, 0.4), (392.00, 0.4), (311.13, 0.8),  # G4, G4, G4, Eb4
            # Descending line (Bb-Across Ito-G-F#-G)
            (466.16, 0.3), (440.00, 0.3), (392.00, 0.3), (369.99, 0.3), (392.00, 0.8),  # Bb4, A4, G4, F#4, G4
            # Final cadence (C5-Bb-Across Ito-G)
            (523.25, 0.4), (466.16, 0.4), (440.00, 0.4), (392.00, 1.0)  # C5, Bb4, A4, G4
        ]

        # Ode to Joy (Beethoven's 9th)
        melody = [
            (329.63, 0.4), (329.63, 0.4), (349.23, 0.4), (392.00, 0.4),
            (392.00, 0.4), (349.23, 0.4), (329.63, 0.4), (293.66, 0.4),
            (261.63, 0.4), (261.63, 0.4), (293.66, 0.4), (329.63, 0.8)]

        for freq, duration in melody:
            self.keithley.beep(freq, duration)
            time.sleep(duration * 0.8)  # Small gap between notes
        print("Melody finished!")

    def ohno(self):
        self.keithley.beep(150, 0.2)
        time.sleep(0.2)
        self.keithley.beep(100, 0.2)

    def close(self):
        if self.keithley:

            self.stop_measurement_flag = True  # Set stop flag to break loops
            self.keithley.beep(5000, 0.1)
            time.sleep(0.2)
            self.keithley.beep(4000, 0.1)

            self.keithley.shutdown()
            self.psu.disable_channel(1)
            self.psu.disable_channel(2)

            self.psu.close()
            print("closed")
            self.master.destroy()  # Closes the GUI window
            sys.exit()
        else:
            print("closed")
            sys.exit()


def get_voltage_range(start_v, stop_v, step_v, sweep_type):
    def frange(start, stop, step):
        while start <= stop if step > 0 else start >= stop:
            yield round(start, 3)
            start += step

    # this method takes the readings twice at all ends of the ranges.
    if sweep_type == "NS":
        voltage_range = (list(frange(start_v, -stop_v, -step_v)) +
                         list(frange(-stop_v, start_v, step_v)))

        return voltage_range
    if sweep_type == "PS":
        voltage_range = (list(frange(start_v, stop_v, step_v)) +
                         list(frange(stop_v, start_v, -step_v)))

        return voltage_range
    else:
        voltage_range = (list(frange(start_v, stop_v, step_v)) +
                         list(frange(stop_v, -stop_v, -step_v)) +
                         list(frange(-stop_v, start_v, step_v)))

        return voltage_range


def extract_number_from_filename(filename):
    # Use regex to find the number at the start of the filename before the first '-'
    match = re.match(r'^(\d+)-', filename)
    if match:
        return int(match.group(1))
    return None


def find_largest_number_in_folder(folder_path):
    largest_number = None

    # Iterate over all files in the folder
    for filename in os.listdir(folder_path):
        number = extract_number_from_filename(filename)
        if number is not None:
            if largest_number is None or number > largest_number:
                largest_number = number
    print(largest_number)
    return largest_number


def zero_devision_check(x, y):
    try:
        return x / y
    except:
        return 0