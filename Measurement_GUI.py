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
from Equipment_Classes.temperature_controller_manager import TemperatureControllerManager
from measurement_plotter import MeasurementPlotter, ThreadSafePlotter

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
        self.master.geometry("1800x1200")
        #200+100
        self.sample_gui = sample_gui
        self.current_index = self.sample_gui.current_index
        self.load_messaging_data()
        self.psu_visa_address = "USB0::0x05E6::0x2220::9210734::INSTR"
        self.temp_controller_address= 'ASRL12::INSTR'
        self.keithley_address = "GPIB0::24::INSTR"
        self.axis_font_size = 8
        self.title_font_size = 10
        self.sequential_number_of_sweeps = 100


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
        self.lakeshore = None
        self.psu_needed = False

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

        self.middle_frame = tk.Frame(self.master)
        self.middle_frame.grid(row=1, column=1, sticky="nsew", padx=0, pady=0)

        self.Graph_frame = tk.Frame(self.master)
        self.Graph_frame.grid(row=0, column=2, sticky="nsew", padx=0,rowspan=10 ,pady=0)

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
        self.create_status_box(self.left_frame)
        self.create_controller_selection(self.left_frame)

        self.temp_measurments_itc4(self.left_frame)
        self.signal_messaging(self.left_frame)

        # middle
        self.create_sweep_parameters(self.middle_frame)
        self.create_custom_measurement_section(self.middle_frame)
        self.sequential_measurments(self.middle_frame)




        # right frame

        self.graphs_main_iv(self.Graph_frame) # main
        self.graphs_all(self.Graph_frame)
        self.graphs_current_time_rt(self.Graph_frame)
        self.graphs_resistance_time_rt(self.Graph_frame)
        self.graphs_temp_time_rt(self.Graph_frame)
        self.graphs_endurance_retention(self.Graph_frame)
        self.graphs_vi_logiv(self.Graph_frame)

        self.top_banner(self.top_frame)

        # self.measurement_thread = None
        # self.plotter = None
        # self.safe_plotter = None
        # self.plotter = None

        # list all GPIB Devices
        # find kiethely smu assign to correct

        # connect to kiethley's
        # Set default to System 1 and trigger the change
        self.set_default_system()
        self.connect_keithley()
        #self.connect_keithley_psu()

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
        info_frame.grid(row=1, column=0, columnspan=4, sticky="ew")
        info_frame.columnconfigure([0, 1, 2], weight=1)

        # Device
        self.device_label = tk.Label(info_frame, text="Device: XYZ", font=("Helvetica", 12))
        self.device_label.grid(row=1, column=0, padx=10, sticky="w")

        # Voltage
        self.voltage_label = tk.Label(info_frame, text="Voltage: 1.23 V", font=("Helvetica", 12))
        self.voltage_label.grid(row=1, column=1, padx=10, sticky="w")

        # Loop
        self.loop_label = tk.Label(info_frame, text="Loop: 5", font=("Helvetica", 12))
        self.loop_label.grid(row=1, column=2, padx=10, sticky="w")

        # Show last sweeps button
        self.show_results_button = tk.Button(info_frame, text="Show Last Sweeps", command=self.show_last_sweeps)
        self.show_results_button.grid(row=1, column=3, columnspan=1, pady=5)

        # Show last sweeps button
        self.show_results_button = tk.Button(info_frame, text="check_connection", command=self.check_connection)
        self.show_results_button.grid(row=1, column=4, columnspan=1, pady=5)

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
    # seequencial plotting
    ###################################################################

    # Add to your GUI initialization
    def create_plot_menu(self):
        """Create menu options for plotting."""
        # Add to your menu bar
        plot_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Plot", menu=plot_menu)

        plot_menu.add_command(label="Open Live Plotter", command=self.open_live_plotter)
        plot_menu.add_separator()
        plot_menu.add_command(label="Export All Plots", command=self.export_all_plots)
        plot_menu.add_command(label="Save Current Plot", command=self.save_current_plot)

    def open_live_plotter(self):
        """Open a standalone live plotter window."""
        if not hasattr(self, 'standalone_plotter') or not self.standalone_plotter.window.winfo_exists():
            measurement_type = self.Sequential_measurement_var.get()
            if measurement_type == "Iv Sweep":
                plot_type = "IV Sweep"
            elif measurement_type == "Single Avg Measure":
                plot_type = "Single Avg Measure"
            else:
                plot_type = "Unknown"

            self.standalone_plotter = MeasurementPlotter(self.root, measurement_type=plot_type)

    def export_all_plots(self):
        """Export plots from the current plotter."""
        if hasattr(self, 'plotter') and self.plotter and self.plotter.window.winfo_exists():
            self.plotter.export_data()
        else:
            tk.messagebox.showinfo("No Active Plotter", "No active measurement plotter found.")

    def save_current_plot(self):
        """Save the current plot as an image."""
        if hasattr(self, 'plotter') and self.plotter and self.plotter.window.winfo_exists():
            self.plotter.save_current_plot()
        else:
            tk.messagebox.showinfo("No Active Plotter", "No active measurement plotter found.")

    ###################################################################
    # GUI mETHODS
    ###################################################################


    def create_connection_section(self, parent):
        """Keithley connection section"""
        frame = tk.LabelFrame(parent, text="Keithley Connection", padx=5, pady=5)
        frame.grid(row=0, column=0, padx=10, pady=5, sticky="ew")

        # System selection dropdown
        tk.Label(frame, text="Choose System:").grid(row=0, column=0, sticky="w")
        self.system_var = tk.StringVar()
        self.systems = self.load_systems()
        self.system_dropdown = tk.OptionMenu(frame, self.system_var,*self.systems,
                                             command=self.on_system_change)
        self.system_dropdown.grid(row=0, column=1, columnspan=2, sticky="ew")

        # GPIB Address - IV
        self.iv_label = tk.Label(frame, text="GPIB Address - IV:")
        self.iv_label.grid(row=1, column=0, sticky="w")
        self.keithley_address_var = tk.StringVar(value=self.keithley_address)
        self.iv_address_entry = tk.Entry(frame, textvariable=self.keithley_address_var)
        self.iv_address_entry.grid(row=1, column=1)
        self.iv_connect_button = tk.Button(frame, text="Connect", command=self.connect_keithley)
        self.iv_connect_button.grid(row=1, column=2)

        # GPIB Address - PSU
        self.psu_label = tk.Label(frame, text="GPIB Address - PSU:")
        self.psu_label.grid(row=2, column=0, sticky="w")
        self.psu_address_var = tk.StringVar(value=self.psu_visa_address)
        self.psu_address_entry = tk.Entry(frame, textvariable=self.psu_address_var)
        self.psu_address_entry.grid(row=2, column=1)
        self.psu_connect_button = tk.Button(frame, text="Connect", command=self.connect_keithley_psu)
        self.psu_connect_button.grid(row=2, column=2)

        # GPIB Address - Temp
        self.temp_label = tk.Label(frame, text="GPIB Address - Temp:")
        self.temp_label.grid(row=3, column=0, sticky="w")
        self.temp_address_var = tk.StringVar(value=self.temp_controller_address)
        self.temp_address_entry = tk.Entry(frame, textvariable=self.temp_address_var)
        self.temp_address_entry.grid(row=3, column=1)
        self.temp_connect_button = tk.Button(frame, text="Connect", command=self.reconnect_temperature_controller)
        #self.temp_connect_button = tk.Button(frame, text="Connect", command=self.connect_temp_controller)
        self.temp_connect_button.grid(row=3, column=2)

    def set_default_system(self):
        systems = self.systems
        default = "Lab Small"
        if default in systems:
            self.system_var.set(default)
            self.on_system_change(default)  # Trigger the address updates
        elif systems and systems[0] != "No systems available":
            self.system_var.set(systems[0])
            self.on_system_change(systems[0])

    def load_systems(self):
        """Load system configurations from JSON file"""
        config_file = "system_configs.json"

        try:
            with open(config_file, 'r') as f:
                self.system_configs = json.load(f)
            return list(self.system_configs.keys())
        except (FileNotFoundError, json.JSONDecodeError):
            return ["No systems available"]

    def on_system_change(self, selected_system):
        """Update addresses when system selection changes"""
        if selected_system in self.system_configs:
            config = self.system_configs[selected_system]

            # Update IV section
            iv_address = config.get("SMU_address", "")
            self.keithley_address_var.set(iv_address)
            self.keithley_address = iv_address
            self.update_component_state("iv", iv_address)

            # Update PSU section
            psu_address = config.get("psu_address", "")
            self.psu_address_var.set(psu_address)
            self.psu_visa_address = psu_address
            self.update_component_state("psu", psu_address)

            # Update Temp section
            temp_address = config.get("temp_address", "")
            self.temp_address_var.set(temp_address)
            self.temp_controller_address = temp_address
            self.update_component_state("temp", temp_address)

            # updater controller type
            self.temp_controller_type = config.get("temp_controller", "")
            self.controller_type_var.set(self.temp_controller_type)
            self.controller_address_var.set(temp_address)

            # smu type
            self.SMU_type = config.get("SMU Type", "")


    def update_component_state(self, component_type, address):
        """Enable/disable and style components based on address availability"""
        has_address = bool(address and address.strip())

        if component_type == "iv":
            components = [self.iv_label, self.iv_address_entry, self.iv_connect_button]
        elif component_type == "psu":
            components = [self.psu_label, self.psu_address_entry, self.psu_connect_button]
        elif component_type == "temp":
            components = [self.temp_label, self.temp_address_entry, self.temp_connect_button]
        else:
            return

        if has_address:
            # Enable components - normal state
            for component in components:
                component.configure(state="normal")

            # Reset colors to default
            components[0].configure(fg="black")  # label
            components[1].configure(state="normal", bg="white", fg="black")  # entry
            components[2].configure(state="normal")  # button
        else:
            # Disable and grey out components
            components[0].configure(fg="grey")  # label
            components[1].configure(state="disabled", bg="lightgrey", fg="grey")  # entry
            components[2].configure(state="disabled")  # button

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

        # Sample Name Entry
        self.additional_info_label = tk.Label(mode_frame, text="Additional Info:")
        self.additional_info_label.grid(row=3, column=0, sticky="w")

        self.additional_info_var = tk.StringVar()  # Use a StringVar
        self.additional_info_entry = ttk.Entry(mode_frame, textvariable=self.additional_info_var)
        self.additional_info_entry.grid(row=3, column=1, columnspan=1, sticky="ew")



    def create_sweep_parameters(self, parent):
        """Sweep parameter section"""
        frame = tk.LabelFrame(parent, text="Sweep Parameters", padx=5, pady=5)
        frame.grid(row=2, column=0,columnspan = 2 ,padx=10, pady=5, sticky="ew")

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

        # LED Controls mini title
        tk.Label(frame, text="LED Controls", font=("Arial", 9, "bold")).grid(row=6, column=0, columnspan=2, sticky="w",
                                                                             pady=(10, 2))

        # LED Toggle Button
        tk.Label(frame, text="LED Status:").grid(row=7, column=0, sticky="w")
        self.led = tk.IntVar(value=0)  # Changed to IntVar for toggle

        def toggle_led():
            current_state = self.led.get()
            new_state = 1 - current_state
            self.led.set(new_state)
            update_led_button()

        def update_led_button():
            if self.led.get() == 1:
                self.led_button.config(text="ON", bg="green", fg="white")
            else:
                self.led_button.config(text="OFF", bg="red", fg="white")

        self.led_button = tk.Button(frame, text="OFF", bg="red", fg="white",
                                    width=8, command=toggle_led)
        self.led_button.grid(row=7, column=1, sticky="w")

        tk.Label(frame, text="Led_Power (0-1):").grid(row=8, column=0, sticky="w")
        self.led_power = tk.DoubleVar(value=1)
        tk.Entry(frame, textvariable=self.led_power).grid(row=8, column=1)

        tk.Label(frame, text="Sequence: (01010)").grid(row=9, column=0, sticky="w")
        self.sequence = tk.StringVar()
        tk.Entry(frame, textvariable=self.sequence).grid(row=9, column=1)

        # Other Controls mini title
        tk.Label(frame, text="Other", font=("Arial", 9, "bold")).grid(row=10, column=0, columnspan=2, sticky="w",
                                                                      pady=(10, 2))

        tk.Label(frame, text="Pause at end?:").grid(row=11, column=0, sticky="w")
        self.pause = tk.DoubleVar(value=0.0)
        tk.Entry(frame, textvariable=self.pause).grid(row=11, column=1)

        def start_thread():
            self.measurement_thread = threading.Thread(target=self.start_measurement)
            self.measurement_thread.daemon = True
            self.measurement_thread.start()

        self.measure_button = tk.Button(frame, text="Start Measurement", command=start_thread)
        self.measure_button.grid(row=12, column=0, columnspan=1, pady=5)

        # stop button
        self.adaptive_button = tk.Button(frame, text="Stop Measurement!", command=self.set_measurment_flag_true)
        self.adaptive_button.grid(row=12, column=1, columnspan=1, pady=10)

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

        def start_thread():
            self.measurement_thread = threading.Thread(target=self.run_custom_measurement)
            self.measurement_thread.daemon = True
            self.measurement_thread.start()

        # Run button
        self.run_custom_button = tk.Button(frame, text="Run Custom", command=start_thread)
        self.run_custom_button.grid(row=1, column=0, columnspan=2, pady=5)

    def signal_messaging(self,parent):
        frame = tk.LabelFrame(parent, text="Signal_Messaging", padx=5, pady=5)
        frame.grid(row=6, column=0, rowspan=2, padx=10, pady=5, sticky="nsew")

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
        frame.grid(row=3, column=0, padx=10, pady=5, sticky="ew")

        self.status_box = tk.Label(frame, text="Status: Not Connected", relief=tk.SUNKEN, anchor="w", width=20)
        self.status_box.pack(fill=tk.X)


    def temp_measurments_itc4(self, parent):
        # Temperature section
        frame = tk.LabelFrame(parent, text="Itc4 Temp Set", padx=5, pady=5)
        frame.grid(row=5, column=0, padx=10, pady=5, sticky="ew")

        # temp entry
        self.temp_label = tk.Label(frame, text="Set_temp:")
        self.temp_label.grid(row=1, column=0, sticky="w")

        self.temp_var = tk.StringVar()  # Use a StringVar
        self.temp_var_entry = ttk.Entry(frame, textvariable=self.temp_var)
        self.temp_var_entry.grid(row=1, column=1, columnspan=1, sticky="ew")

        # button
        self.temp_go_button = tk.Button(frame, text="Apply", command=self.send_temp)
        self.temp_go_button.grid(row=1, column=2)

    def create_controller_selection(self,parent):
        """Create manual controller selection widgets."""
        control_frame = tk.LabelFrame(parent, text="Temperature Controller", padx=5, pady=5)
        control_frame.grid(row=4, column=0, columnspan=2, sticky='ew', padx=5)

        # Controller type dropdown
        tk.Label(control_frame, text="Type:").grid(row=0, column=0, sticky='w')
        self.controller_type_var = tk.StringVar(value="Auto-Detect")
        self.controller_dropdown = ttk.Combobox(
            control_frame,
            textvariable=self.controller_type_var,
            values=["Auto-Detect", "Lakeshore 335", "Oxford ITC4", "None"],
            width=15
        )
        self.controller_dropdown.grid(row=0, column=1, padx=5)

        # Address entry
        tk.Label(control_frame, text="Address:").grid(row=1, column=0, sticky='w')
        self.controller_address_var = tk.StringVar(value="Auto")
        self.controller_address_entry = tk.Entry(
            control_frame,
            textvariable=self.controller_address_var,
            width=15
        )
        self.controller_address_entry.grid(row=1, column=1, padx=5)

        # Connect button
        self.connect_button = tk.Button(
            control_frame,
            text="Connect",
            command=self.reconnect_temperature_controller
        )
        self.connect_button.grid(row=2, column=0, padx=5)

        # Status indicator
        self.controller_status_label = tk.Label(
            control_frame,
            text="● Disconnected",
            fg="red"
        )
        self.controller_status_label.grid(row=2, column=1, padx=5)

    def reconnect_temperature_controller(self):
        """Reconnect temperature controller based on GUI selection."""
        controller_type = self.controller_type_var.get()
        address = self.controller_address_var.get()

        # Close existing connection
        try:
            if hasattr(self, 'temp_controller'):
                self.temp_controller.close()
        except:
            pass

        # Connect based on selection
        if controller_type == "Auto-Detect":
            self.temp_controller = TemperatureControllerManager(auto_detect=True)
        elif controller_type == "None":
            self.temp_controller = TemperatureControllerManager(auto_detect=False)
        else:
            # Manual connection
            if address == "Auto":
                # Use default addresses
                default_addresses = {
                    "Lakeshore 335": "12",
                    "Oxford ITC4": "ASRL12::INSTR"
                }
                address = default_addresses.get(controller_type, "12")

            self.temp_controller = TemperatureControllerManager(
                auto_detect=False,
                controller_type=controller_type,
                address=address
            )

        # Update status
        self.update_controller_status()

    def reconnect_Kieithley_controller(self):
        """Reconnect temperature controller based on GUI selection."""
        controller_type = self.controller_type_var.get()
        address = self.controller_address_var.get()

        # Close existing connection
        if hasattr(self, 'temp_controller'):
            self.temp_controller.close()

        # Connect based on selection
        if controller_type == "Auto-Detect":
            self.temp_controller = TemperatureControllerManager(auto_detect=True)
        elif controller_type == "None":
            self.temp_controller = TemperatureControllerManager(auto_detect=False)
        else:
            # Manual connection
            if address == "Auto":
                # Use default addresses
                default_addresses = {
                    "Lakeshore 335": "12",
                    "Oxford ITC4": "ASRL12::INSTR"
                }
                address = default_addresses.get(controller_type, "12")

            self.temp_controller = TemperatureControllerManager(
                auto_detect=False,
                controller_type=controller_type,
                address=address
            )

        # Update status
        self.update_controller_status()
    def update_controller_status(self):
        """Update controller status indicator."""
        if self.temp_controller.is_connected():
            info = self.temp_controller.get_controller_info()
            self.controller_status_label.config(
                text=f"● Connected: {info['type']}",
                fg="green"
            )
            #self.log_terminal(f"Connected to {info['type']} at {info['address']}")
        else:
            self.controller_status_label.config(
                text="● Disconnected",
                fg="red"
            )

    def sequential_measurments(self,parent):

        frame = tk.LabelFrame(parent, text="Sequential_measurement", padx=5, pady=5)
        frame.grid(row=10, column=0, padx=10, pady=5, sticky="ew")

        # Drop_down menu
        tk.Label(frame, text="Sequential_measurement:").grid(row=0, column=0, sticky="w")
        self.Sequential_measurement_var = tk.StringVar(value ="choose")
        self.Sequential_measurement = ttk.Combobox(frame, textvariable=self.Sequential_measurement_var,
                                                    values=["Iv Sweep","Single Avg Measure"])
        self.Sequential_measurement.grid(row=0, column=1, padx=5)

        # voltage Data entry
        tk.Label(frame, text="Voltage").grid(row=1, column=0, sticky="w")
        self.sq_voltage = tk.DoubleVar(value=0.1)
        tk.Entry(frame, textvariable=self.sq_voltage).grid(row=1, column=1)

        # voltage Data entry
        tk.Label(frame, text="Num of itterations").grid(row=2, column=0, sticky="w")
        self.sequential_number_of_sweeps = tk.DoubleVar(value=100)
        tk.Entry(frame, textvariable=self.sequential_number_of_sweeps).grid(row=2, column=1)

        # voltage Data entry
        tk.Label(frame, text="Time delay (S)").grid(row=3, column=0, sticky="w")
        self.sq_time_delay = tk.DoubleVar(value=10)
        tk.Entry(frame, textvariable=self.sq_time_delay).grid(row=3, column=1)

        # Add this to your GUI initialization section where other sequential measurement controls are:

        # Temperature recording checkbox
        self.record_temp_var = tk.BooleanVar(value=True)
        self.record_temp_checkbox = tk.Checkbutton(frame,text="Record Temperature",variable=self.record_temp_var)
        self.record_temp_checkbox.grid(row=5, column=0, sticky='w')  # Adjust row/column as needed

        # Add measurement duration entry for averaging
        tk.Label(frame, text="Measurement Duration (s):").grid(row=4, column=0, sticky='w')
        self.measurement_duration_var = tk.DoubleVar(value=5.0)  # Default 5 seconds
        self.measurement_duration_entry = tk.Entry(frame,textvariable=self.measurement_duration_var,width=10)
        self.measurement_duration_entry.grid(row=4, column=1)


        def start_thread():
            self.measurement_thread = threading.Thread(target=self.sequential_measure)
            self.measurement_thread.daemon = True
            self.measurement_thread.start()

        # Run button
        self.run_custom_button = tk.Button(frame, text="Run Sequence", command=start_thread)
        self.run_custom_button.grid(row=5, column=1, columnspan=2, pady=5)

    ###################################################################
    # All Measurement acquisition code
    ###################################################################

    def sequential_measure(self):

        self.measuring = True
        self.stop_measurement_flag = False
        self.bring_to_top() # make sure it is on the top
        self.check_for_sample_name() # checks for sample name if not prompts user

        print(f"Running sequential measurement:")

        if self.Sequential_measurement_var.get() == "Iv Sweep":
            count_pass = 1

            for i in range(int(self.sequential_number_of_sweeps.get())):
                print("Starting pass #",i + 1)
                voltage = int(self.sq_voltage.get())
                voltage_arr = get_voltage_range(0, voltage, 0.05, "FS")

                self.stop_measurement_flag = False  # Reset the stop flag

                if self.current_device in self.device_list:
                    start_index = self.device_list.index(self.current_device)
                else:
                    start_index = 0  # Default to the first device if current one is not found

                device_count = len(self.device_list)

                # looping through each device.
                for j in range(device_count):  # Ensure we process each device exactly once
                    device = self.device_list[(start_index + j) % device_count]  # Wrap around when reaching the end

                    self.status_box.config(text=f"Measuring {device}...")
                    self.master.update()
                    self.keithley.set_voltage(0, self.icc.get())  # Start at 0V
                    self.keithley.enable_output(True)  # Enable output

                    if self.stop_measurement_flag:  # Check if stop was pressed
                        print("Measurement interrupted!")
                        break  # Exit measurement loop immediately
                    time.sleep(0.5)
                    v_arr, c_arr, timestamps = self.measure(voltage_arr)
                    data = np.column_stack((v_arr, c_arr, timestamps))

                    # save the current data in a folder called multiplexer and the name of the sample

                    # creates save directory with the selected measurement device name letter and number
                    save_dir = f"Data_save_loc\\Multiplexer_IV_sweep\\{self.sample_name_var.get()}" \
                               f"\\{j+1}"
                    # make directory if dost exist.
                    if not os.path.exists(save_dir):
                        os.makedirs(save_dir)
                    sweeps=1
                    name = f"{count_pass}-FS-{voltage}v-{0.05}sv-{0.05}sd-Py-Sq-{sweeps}"
                    file_path = f"{save_dir}\\{name}.txt"


                    np.savetxt(file_path, data, fmt="%0.3E\t%0.3E\t%0.3E", header="Voltage Current Time", comments="")

                    #change device
                    self.sample_gui.next_device()
                    time.sleep(0.1)
                    self.sample_gui.change_relays()

                count_pass += 1
                time.sleep(self.sq_time_delay.get()) # delay for the time between measurements

        elif self.Sequential_measurement_var.get() == "Single Avg Measure":

            count_pass = 1
            # Initialize data arrays for each device
            device_data = {}  # Dictionary to store data for each device
            start_time = time.time()  # Record overall start time

            if self.current_device in self.device_list:
                start_index = self.device_list.index(self.current_device)
            else:
                start_index = 0  # Default to the first device if current one is not found

            device_count = len(self.device_list)
            # Initialize empty arrays for each device

            for j in range(device_count):
                device_idx = (start_index + j) % device_count
                device = self.device_list[device_idx]
                device_data[device] = {
                    'voltages': [],
                    'currents': [],
                    'std_errors': [],
                    'timestamps': [],
                    'temperatures': []
                }

            voltage = float(self.sq_voltage.get())
            measurement_duration = self.measurement_duration_var.get()
            self.keithley.set_voltage(0)
            self.keithley.enable_output(True)
            # Main measurement loop

            for i in range(int(self.sequential_number_of_sweeps.get())):

                print(f"Starting pass #{i + 1}")

                self.stop_measurement_flag = False  # Reset the stop flag

                # Loop through each device

                for j in range(device_count):

                    device_idx = (start_index + j) % device_count
                    device = self.device_list[device_idx]

                    # Extract actual device number from device name
                    device_number = int(device.split('_')[1]) if '_' in device else j + 1

                    self.status_box.config(text=f"Pass {i + 1}: Measuring {device}...")
                    self.master.update()
                    device_display_name = f"Device_{device_number}_{device}"  # Use actual device number

                    # Calculate timestamp (middle of measurement period)
                    measurement_timestamp = time.time() - start_time + (measurement_duration / 2)
                    # Perform averaged measurement
                    avg_current, std_error, temperature = self.measure_average_current(voltage, measurement_duration)

                    # Store data in arrays
                    device_data[device]['voltages'].append(voltage)
                    device_data[device]['currents'].append(avg_current)
                    device_data[device]['std_errors'].append(std_error)
                    device_data[device]['timestamps'].append(measurement_timestamp)

                    if self.record_temp_var.get():
                        temperature = self.temp_controller.get_temperature_celsius()  # B
                        device_data[device]['temperatures'].append(temperature)

                    # Log current measurement
                    self.log_terminal(f"Pass {i + 1}, Device {device}: V={voltage}V, "
                                      f"I_avg={avg_current:.3E}A, σ={std_error:.3E}A, "
                                      f"t={measurement_timestamp:.1f}s")

                    if self.stop_measurement_flag:  # Check if stop was pressed
                        print("Measurement interrupted! Saving current data...")
                        self.save_averaged_data(device_data, self.sample_name_var.get(),
                                                start_index, interrupted=True)  # Removed device_count parameter
                        return  # Exit the function

                    #when changing device ensure voltage is 0
                    self.keithley.set_voltage(0,self.icc.get())
                    # let current drop/voltage to decrease
                    time.sleep(0.1)

                    # Change to next device
                    self.sample_gui.next_device()
                    time.sleep(0.1)
                    self.sample_gui.change_relays()
                    print("Switching Device")
                    time.sleep(0.1)

                # Auto-save every 5 cycles
                if (i + 1) % 5 == 0:
                    self.log_terminal(f"Auto-saving data after {i + 1} cycles...")
                    self.save_averaged_data(device_data, self.sample_name_var.get(), start_index, interrupted=False)
                count_pass += 1

                # Delay between measurement passes (if not the last pass)
                if i < int(self.sequential_number_of_sweeps.get()) - 1:
                    time.sleep(self.sq_time_delay.get())

            # Save all data at the end
            self.save_averaged_data(device_data, self.sample_name_var.get(), start_index, interrupted=False)

            # Save comprehensive file with all measurements
            self.save_all_measurements_file(device_data, self.sample_name_var.get(), start_index)

            self.measuring = False
            self.status_box.config(text="Measurement Complete")
            self.keithley.set_voltage(0)
            time.sleep(0.1)
            self.keithley.enable_output(False)  # Disable output when done

        # elif self.Sequential_measurement_var.get() == "Single Avg Measure":
        #
        #     count_pass = 1
        #     # Initialize data arrays for each device
        #     device_data = {}  # Dictionary to store data for each device
        #     start_time = time.time()  # Record overall start time
        #
        #     if self.current_device in self.device_list:
        #         start_index = self.device_list.index(self.current_device)
        #     else:
        #         start_index = 0  # Default to the first device if current one is not found
        #
        #     device_count = len(self.device_list)
        #     # Initialize empty arrays for each device
        #
        #     for j in range(device_count):
        #         device_idx = (start_index + j) % device_count
        #         device = self.device_list[device_idx]
        #         device_data[device] = {
        #             'voltages': [],
        #             'currents': [],
        #             'std_errors': [],
        #             'timestamps': [],
        #             'temperatures': []
        #         }
        #
        #     voltage = float(self.sq_voltage.get())
        #     measurement_duration = self.measurement_duration_var.get()
        #     # Main measurement loop
        #
        #     for i in range(int(self.sequential_number_of_sweeps.get())):
        #
        #         print(f"Starting pass #{i + 1}")
        #
        #         self.stop_measurement_flag = False  # Reset the stop flag
        #
        #         # Loop through each device
        #
        #         for j in range(device_count):
        #
        #             device_idx = (start_index + j) % device_count
        #             device = self.device_list[device_idx]
        #             self.status_box.config(text=f"Pass {i + 1}: Measuring {device}...")
        #             self.master.update()
        #             device_display_name = f"Device_{j + 1}_{device}"
        #
        #             # Calculate timestamp (middle of measurement period)
        #             measurement_timestamp = time.time() - start_time + (measurement_duration / 2)
        #             # Perform averaged measurement
        #             avg_current, std_error, temperature = self.measure_average_current(voltage, measurement_duration)
        #
        #
        #
        #             # Store data in arrays
        #             device_data[device]['voltages'].append(voltage)
        #             device_data[device]['currents'].append(avg_current)
        #             device_data[device]['std_errors'].append(std_error)
        #             device_data[device]['timestamps'].append(measurement_timestamp)
        #
        #             if self.record_temp_var.get():
        #                 temperature = self.temp_controller.get_temperature_celsius() #B
        #                 device_data[device]['temperatures'].append(temperature)
        #
        #
        #             # Log current measurement
        #             self.log_terminal(f"Pass {i + 1}, Device {device}: V={voltage}V, "
        #                               f"I_avg={avg_current:.3E}A, σ={std_error:.3E}A, "
        #                               f"t={measurement_timestamp:.1f}s")
        #
        #             if self.stop_measurement_flag:  # Check if stop was pressed
        #
        #                 print("Measurement interrupted! Saving current data...")
        #
        #                 self.save_averaged_data(device_data, self.sample_name_var.get(),
        #
        #                                         start_index, device_count, interrupted=True)
        #
        #                 return  # Exit the function
        #
        #             # Change to next device
        #             self.sample_gui.next_device()
        #             time.sleep(0.1)
        #             self.sample_gui.change_relays()
        #             print("switching device")
        #             time.sleep(0.1)
        #
        #         # Auto-save every 5 cycles
        #         if (i + 1) % 5 == 0:
        #             self.log_terminal(f"Auto-saving data after {i + 1} cycles...")
        #             self.save_averaged_data(device_data, self.sample_name_var.get(),start_index, device_count, interrupted=False)
        #         count_pass += 1
        #
        #         # Delay between measurement passes (if not the last pass)
        #         if i < int(self.sequential_number_of_sweeps.get()) - 1:
        #             time.sleep(self.sq_time_delay.get())
        #
        #
        #     # Save all data at the end
        #     self.save_averaged_data(device_data, self.sample_name_var.get(), start_index, device_count,interrupted=False)
        #
        #     # Save comprehensive file with all measurements
        #     self.save_all_measurements_file(device_data, self.sample_name_var.get(), start_index, device_count)
        #
        #     # Save all data at the end
        #     self.save_averaged_data(device_data, self.sample_name_var.get(),start_index, device_count, interrupted=False)
        #     self.measuring = False
        #     self.status_box.config(text="Measurement Complete")
        #     self.keithley.enable_output(False)  # Disable output when done


    def measure_average_current(self, voltage, duration):
        """
        Apply voltage and measure current for specified duration, then return average.

        Args:
            voltage: Voltage to apply (V)
            duration: Time to measure for (seconds)

        Returns:
            tuple: (average_current, standard_error, temperature)
        """
        # todo add retention on graph

        # Set voltage and enable output
        self.keithley.set_voltage(voltage, self.icc.get())


        # Allow settling time
        time.sleep(0.2)

        # Collect current measurements
        current_readings = []
        timestamps = []
        start_time = time.time()

        # Sample rate (adjust as needed)
        sample_interval = 0.1  # 10 Hz sampling

        while (time.time() - start_time) < duration:
            if self.stop_measurement_flag:
                break

            current = self.keithley.measure_current()
            current_readings.append(current[1])
            timestamps.append(time.time() - start_time)

            # Update status
            elapsed = time.time() - start_time
            self.status_box.config(
                text=f"Measuring... {elapsed:.1f}/{duration}s"
            )
            self.master.update()

            # Wait for next sample
            time.sleep(sample_interval)

        # Calculate statistics
        if current_readings:
            current_array = np.array(current_readings)
            avg_current = np.mean(current_array)
            std_dev = np.std(current_array)
            std_error = std_dev / np.sqrt(len(current_array))
        else:
            avg_current = 0
            std_error = 0

        # Record temperature if enabled
        temperature = 0  # Default value
        if self.record_temp_var.get():
            temperature = self.record_temperature()

        # Disable output after measurement
        #self.keithley.enable_output(False)
        self.keithley.set_voltage(0,self.icc.get())

        return avg_current, std_error, temperature

    def record_temperature(self):
        """
        Placeholder function for temperature recording.
        To be implemented when temperature measurement hardware is available.

        Returns:
            float: Temperature in Celsius (currently returns 25.0 as placeholder)
        """
        # TODO: Implement actual temperature measurement
        # This might involve:
        # - Reading from a thermocouple
        # - Querying a temperature controller
        # - Reading from an environmental chamber

        # For now, return a placeholder value
        return 25.0  # Room temperature placeholder

    def log_terminal(self, message):
        """Log message to terminal output (if you don't already have this)"""
        if hasattr(self, 'terminal_output'):
            self.terminal_output.config(state=tk.NORMAL)
            self.terminal_output.insert(tk.END, message + "\n")
            self.terminal_output.config(state=tk.DISABLED)
            self.terminal_output.see(tk.END)
        else:
            print(message)

    def measure(self, voltage_range, sweeps= 1, step_delay=0.05, led=0, power=1, sequence=None, pause=0):
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
                if self.psu_needed:
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
        if self.psu_needed:
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
                            self.psu_needed = True
                        else:
                            self.psu_needed = False

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
                try:
                    self.psu.led_off_380()
                except:
                    continue

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

            if self.additional_info_var != "":

                #extra_info = "-" + str(self.additional_info_entry.get())
                # or
                extra_info = "-" + self.additional_info_entry.get().strip()
            else:
                extra_info = ""

            key = find_largest_number_in_folder(save_dir)
            save_key = 0 if key is None else key + 1
            name = f"{save_key}-{sweep_type}-{stop_v}v-{step_v}sv-{step_delay}sd-Py-{sweeps}{additional}{extra_info}"
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

    def init_temperature_controller(self):
        """Initialize temperature controller with auto-detection."""
        self.temp_controller = TemperatureControllerManager(auto_detect=True)

        # Log the result
        if self.temp_controller.is_connected():
            info = self.temp_controller.get_controller_info()
            self.log_terminal(f"Temperature Controller: {info['type']} at {info['address']}")
            self.log_terminal(f"Current temperature: {info['temperature']:.1f}°C")
        else:
            self.log_terminal("No temperature controller detected - using 25°C default")

    ###################################################################
    # Temp logging
    ###################################################################

    def create_temperature_log(self):
        """Create a temperature log that records during measurements."""
        self.temperature_log = []
        self.is_logging_temperature = False

    def start_temperature_logging(self):
        """Start logging temperature data."""
        self.temperature_log = []
        self.is_logging_temperature = True
        self.log_temperature_data()

    def log_temperature_data(self):
        """Log temperature data periodically during measurements."""
        if self.is_logging_temperature and self.measuring:
            timestamp = time.time()
            temp = self.temp_controller.get_temperature_celsius()
            self.temperature_log.append((timestamp, temp))

            # Continue logging every second
            self.root.after(1000, self.log_temperature_data)

    def stop_temperature_logging(self):
        """Stop temperature logging and save data."""
        self.is_logging_temperature = False

        if self.temperature_log:
            # Save temperature log with measurement data
            save_path = f"Data_save_loc\\Temperature_Log_{time.strftime('%Y%m%d_%H%M%S')}.txt"
            with open(save_path, 'w') as f:
                f.write("Time(s)\tTemperature(C)\n")
                start_time = self.temperature_log[0][0]
                for timestamp, temp in self.temperature_log:
                    f.write(f"{timestamp - start_time:.1f}\t{temp:.2f}\n")



    ###################################################################
    # Other Functions
    ###################################################################

    # def save_averaged_data(self, device_data, sample_name, start_index, interrupted=False):
    #     """
    #     Save the averaged measurement data for all devices.
    #
    #     Args:
    #         device_data: Dictionary containing arrays for each device
    #         sample_name: Name of the sample
    #         start_index: Starting device index
    #         interrupted: Boolean indicating if measurement was interrupted
    #     """
    #     # Create main save directory
    #     base_dir = f"Data_save_loc\\Multiplexer_Avg_Measure\\{sample_name}"
    #     if not os.path.exists(base_dir):
    #         os.makedirs(base_dir)
    #
    #     # Save data for each device
    #     for device in device_data.keys():  # Iterate through actual devices instead of using range
    #
    #         if len(device_data[device]['currents']) == 0:
    #             continue  # Skip if no data for this device
    #
    #         # Extract actual device number from device name
    #         device_number = int(device.split('_')[1]) if '_' in device else 1
    #
    #         # Create device-specific directory using actual device number
    #         device_dir = f"{base_dir}\\{device_number}"
    #         if not os.path.exists(device_dir):
    #             os.makedirs(device_dir)
    #
    #         # Prepare data array
    #         voltages = np.array(device_data[device]['voltages'])
    #         currents = np.array(device_data[device]['currents'])
    #         std_errors = np.array(device_data[device]['std_errors'])
    #         timestamps = np.array(device_data[device]['timestamps'])
    #
    #         if self.record_temp_var.get() and device_data[device]['temperatures']:
    #             temperatures = np.array(device_data[device]['temperatures'])
    #             data = np.column_stack((timestamps,temperatures, voltages, currents, std_errors))
    #             header = "Time(s)\tTemperature(C)\tVoltage(V)\tCurrent(A)\tStd_Error(A)"
    #             fmt = "%0.3E\t%0.3E\t%0.3E\t%0.3E\t%0.3E"
    #         else:
    #             data = np.column_stack((timestamps, voltages, currents, std_errors))
    #             header = "Time(s)\tVoltage(V)\tCurrent(A)\tStd_Error(A)"
    #             fmt = "%0.3E\t%0.3E\t%0.3E\t%0.3E"
    #
    #         # Create filename
    #         timestamp_str = time.strftime("%Y%m%d_%H%M%S")
    #         status_str = "interrupted" if interrupted else "complete"
    #         num_measurements = len(currents)
    #
    #         voltage = voltages[0] if len(voltages) > 0 else 0
    #         measurement_duration = self.measurement_duration_var.get()
    #
    #         # Use actual device number in filename
    #         filename = f"Device_{device_number}_{device}_{voltage}V_{measurement_duration}s_" \
    #                    f"{num_measurements}measurements_{status_str}_{timestamp_str}.txt"
    #
    #         file_path = os.path.join(device_dir, filename)
    #
    #         # Save data
    #         np.savetxt(file_path, data, fmt=fmt, header=header, comments="# ")
    #
    #         self.log_terminal(f"Saved data for device {device}: {num_measurements} measurements")

    def save_averaged_data(self, device_data, sample_name, start_index, interrupted=False):
        """
        Save the averaged measurement data for all devices.

        Args:
            device_data: Dictionary containing arrays for each device
            sample_name: Name of the sample
            start_index: Starting device index
            interrupted: Boolean indicating if measurement was interrupted
        """
        # Create main save directory
        base_dir = f"Data_save_loc\\Multiplexer_Avg_Measure\\{sample_name}"
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)

        # Save data for each device
        for device in device_data.keys():

            if len(device_data[device]['currents']) == 0:
                continue  # Skip if no data for this device

            # Extract actual device number from device name
            device_number = int(device.split('_')[1]) if '_' in device else 1

            # Create device-specific directory using actual device number
            device_dir = f"{base_dir}\\{device_number}"
            if not os.path.exists(device_dir):
                os.makedirs(device_dir)

            # Prepare data arrays
            timestamps = np.array(device_data[device]['timestamps'])
            voltages = np.array(device_data[device]['voltages'])
            currents = np.array(device_data[device]['currents'])
            std_errors = np.array(device_data[device]['std_errors'])

            # Calculate additional parameters
            resistance = voltages / currents  # R = V/I
            conductance = currents / voltages  # G = I/V = 1/R

            # Calculate normalized conductance (G/G0 where G0 is first measurement)
            conductance_normalized = conductance / np.max(conductance) if len(conductance) > 0 else conductance

            if self.record_temp_var.get() and device_data[device]['temperatures']:
                temperatures = np.array(device_data[device]['temperatures'])
                data = np.column_stack((timestamps, temperatures, voltages, currents, std_errors,
                                        resistance, conductance, conductance_normalized))
                header = "Time(s)\tTemperature(C)\tVoltage(V)\tCurrent(A)\tStd_Error(A)\tResistance(Ohm)\tConductance(S)\tConductance_Normalized"
                fmt = "%0.3E\t%0.3E\t%0.3E\t%0.3E\t%0.3E\t%0.3E\t%0.3E\t%0.3E"
            else:
                # If no temperature, fill with NaN or zeros
                temperatures = np.full_like(timestamps, np.nan)
                data = np.column_stack((timestamps, temperatures, voltages, currents, std_errors,
                                        resistance, conductance, conductance_normalized))
                header = "Time(s)\tTemperature(C)\tVoltage(V)\tCurrent(A)\tStd_Error(A)\tResistance(Ohm)\tConductance(S)\tConductance_Normalized"
                fmt = "%0.3E\t%0.3E\t%0.3E\t%0.3E\t%0.3E\t%0.3E\t%0.3E\t%0.3E"

            # Create filename
            timestamp_str = time.strftime("%Y%m%d_%H%M%S")
            status_str = "interrupted" if interrupted else "complete"
            num_measurements = len(currents)

            voltage = voltages[0] if len(voltages) > 0 else 0
            measurement_duration = self.measurement_duration_var.get()

            filename = f"Device_{device_number}_{device}_{voltage}V_{measurement_duration}s_" \
                       f"{num_measurements}measurements_{status_str}_{timestamp_str}.txt"

            file_path = os.path.join(device_dir, filename)

            # Save data
            np.savetxt(file_path, data, fmt=fmt, header=header, comments="# ")

            self.log_terminal(f"Saved data for device {device}: {num_measurements} measurements")

    def send_temp(self):
        self.itc.set_temperature(int(self.temp_var.get()))
        self.graphs_temp_time_rt(self.Graph_frame)
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

    def save_all_measurements_file(self, device_data, sample_name, start_index):
        """Save all measurements with each device in its own columns using pandas and create graphs"""

        import pandas as pd
        import matplotlib.pyplot as plt
        import numpy as np

        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{sample_name}_{timestamp}_all.csv"

        # Create a dictionary to hold all columns and processed data for graphing
        all_columns = {}
        graph_data = {}  # Store processed data for graphing

        # Build columns for each device - iterate through actual devices
        for device in device_data.keys():
            # Extract actual device number from device name
            device_number = int(device.split('_')[1]) if '_' in device else 1
            device_display_name = f"D{device_number}_{device}"

            if device in device_data:
                data = device_data[device]

                # Calculate additional parameters
                timestamps = np.array(data['timestamps'])
                voltages = np.array(data['voltages'])
                currents = np.array(data['currents'])
                std_errors = np.array(data['std_errors'])

                resistance = voltages / currents
                conductance = currents / voltages
                conductance_normalized = conductance / np.max(conductance) if len(conductance) > 0 else conductance

                temperatures = np.array(
                    data['temperatures']) if self.record_temp_var.get() and 'temperatures' in data else np.full_like(
                    timestamps, np.nan)

                # Add columns in the specified order
                all_columns[f'Time({device_display_name})'] = timestamps
                all_columns[f'Temperature({device_display_name})'] = temperatures
                all_columns[f'Voltage({device_display_name})'] = voltages
                all_columns[f'Current({device_display_name})'] = currents
                all_columns[f'StdError({device_display_name})'] = std_errors
                all_columns[f'Resistance({device_display_name})'] = resistance
                all_columns[f'Conductance({device_display_name})'] = conductance
                all_columns[f'Conductance_Normalized({device_display_name})'] = conductance_normalized

                # Store data for graphing
                graph_data[device] = {
                    'device_number': device_number,
                    'device_name': device,
                    'timestamps': timestamps,
                    'temperatures': temperatures,
                    'currents': currents,
                    'conductance': conductance,
                    'conductance_normalized': conductance_normalized
                }

        # Create DataFrame
        df = pd.DataFrame(dict([(k, pd.Series(v)) for k, v in all_columns.items()]))

        # Create main save directory
        base_dir = f"Data_save_loc\\Multiplexer_Avg_Measure\\{sample_name}"
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)


        # Save to CSV
        filepath = os.path.join(base_dir, filename)
        df.to_csv(filepath, index=False)

        # Create graphs directory
        graphs_dir = os.path.join(base_dir, "graphs")
        if not os.path.exists(graphs_dir):
            os.makedirs(graphs_dir)

        # Create individual device graphs
        self._create_individual_device_graphs(graph_data, graphs_dir, sample_name, timestamp)

        # Create comparison graph
        self._create_comparison_graph(graph_data, graphs_dir, sample_name, timestamp)

        self.log_terminal(f"Saved all measurements to: {filename}")
        self.log_terminal(f"Saved graphs to: graphs directory")

        return filename

    def _create_individual_device_graphs(self, graph_data, graphs_dir, sample_name, timestamp):
        """Create individual graphs for each device"""
        # stops error message by using back end
        import matplotlib
        matplotlib.use('Agg')  # Use non-interactive backend
        import matplotlib.pyplot as plt
        import matplotlib.cm as cm

        for device, data in graph_data.items():
            device_number = data['device_number']
            device_name = data['device_name']

            # Skip if no valid temperature data
            if np.all(np.isnan(data['temperatures'])):
                continue

            fig, axes = plt.subplots(2, 3, figsize=(18, 12))
            fig.suptitle(f'Device {device_number} ({device_name}) - {sample_name}', fontsize=16)

            # Time vs Current
            axes[0, 0].plot(data['timestamps'], data['currents'], 'b.-')
            axes[0, 0].set_xlabel('Time (s)')
            axes[0, 0].set_ylabel('Current (A)')
            axes[0, 0].set_title('Time vs Current')
            axes[0, 0].grid(True)

            # Temperature vs Current
            axes[0, 1].plot(data['temperatures'], data['currents'], 'r.-')
            axes[0, 1].set_xlabel('Temperature (°C)')
            axes[0, 1].set_ylabel('Current (A)')
            axes[0, 1].set_title('Temperature vs Current')
            axes[0, 1].grid(True)

            # Temperature vs Conductance
            axes[0, 2].plot(data['temperatures'], data['conductance'], 'g.-')
            axes[0, 2].set_xlabel('Temperature (°C)')
            axes[0, 2].set_ylabel('Conductance (S)')
            axes[0, 2].set_title('Temperature vs Conductance')
            axes[0, 2].grid(True)

            # Temperature vs Normalized Conductance
            axes[1, 0].plot(data['temperatures'], data['conductance_normalized'], 'm.-')
            axes[1, 0].set_xlabel('Temperature (°C)')
            axes[1, 0].set_ylabel('Normalized Conductance')
            axes[1, 0].set_title('Temperature vs Normalized Conductance')
            axes[1, 0].grid(True)

            # Temperature power law plots (log-log)
            temp_kelvin = data['temperatures'] + 273.15  # Convert to Kelvin

            # Filter out any invalid temperatures
            valid_temp = temp_kelvin > 0
            temp_filtered = temp_kelvin[valid_temp]
            cond_norm_filtered = data['conductance_normalized'][valid_temp]

            if len(temp_filtered) > 0:
                axes[1, 1].loglog(temp_filtered ** (-1 / 4), cond_norm_filtered, 'c.-', label='T^(-1/4)')
                axes[1, 1].loglog(temp_filtered ** (-1 / 3), cond_norm_filtered, 'y.-', label='T^(-1/3)')
                axes[1, 1].loglog(temp_filtered ** (-1 / 2), cond_norm_filtered, 'k.-', label='T^(-1/2)')
                axes[1, 1].set_xlabel('Temperature^(-n) (K^(-n))')
                axes[1, 1].set_ylabel('Normalized Conductance')
                axes[1, 1].set_title('Power Law: T^(-n) vs Normalized Conductance')
                axes[1, 1].legend()
                axes[1, 1].grid(True)

            # Remove empty subplot
            axes[1, 2].remove()

            plt.tight_layout()

            # Save individual device graph
            graph_filename = f"Device_{device_number}_{device_name}_{sample_name}_{timestamp}.png"
            graph_filepath = os.path.join(graphs_dir, graph_filename)
            plt.savefig(graph_filepath, dpi=300, bbox_inches='tight')
            plt.close()

    def _create_comparison_graph(self, graph_data, graphs_dir, sample_name, timestamp):
        """Create comparison graph with all devices"""
        import matplotlib
        matplotlib.use('Agg')  # Use non-interactive backend
        import matplotlib.pyplot as plt
        import matplotlib.cm as cm

        fig, ax = plt.subplots(1, 1, figsize=(12, 8))

        colors = cm.tab10(np.linspace(0, 1, len(graph_data)))

        for i, (device, data) in enumerate(graph_data.items()):
            device_number = data['device_number']
            device_name = data['device_name']

            # Skip if no valid temperature data
            if np.all(np.isnan(data['temperatures'])):
                continue

            ax.plot(data['temperatures'], data['conductance_normalized'],
                    '.-', color=colors[i], label=f'Device {device_number}', linewidth=2, markersize=6)

        ax.set_xlabel('Temperature (°C)', fontsize=12)
        ax.set_ylabel('Normalized Conductance', fontsize=12)
        ax.set_title(f'All Devices - Temperature vs Normalized Conductance\n{sample_name}', fontsize=14)
        ax.grid(True, alpha=0.3)
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')

        plt.tight_layout()

        # Save comparison graph
        comparison_filename = f"All_Devices_Comparison_{sample_name}_{timestamp}.png"
        comparison_filepath = os.path.join(graphs_dir, comparison_filename)
        plt.savefig(comparison_filepath, dpi=300, bbox_inches='tight')
        plt.close()

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

if __name__ == "__main__":
    print("you cannot do this")