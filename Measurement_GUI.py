"""Measurement GUI

Module summary:
This module implements a Tkinter-based GUI used to control IV/PMU/SMU
measurements for arrays of devices. It provides:
- Connection helpers for instrument managers (SMU, PSU, temperature controllers)
- A centralized `MeasurementService` integration for performing IV sweeps,
  pulsed measurements, endurance/retention tests, and transient captures
- Real-time plotting using matplotlib embedded in Tkinter windows
- Utilities for saving measurement data, creating summary plots and
  sending results via Telegram.

Key components:
- `SMUAdapter`: small adapter layer that exposes a common minimal interface
  (set_voltage, measure_current, enable_output, ...) wrapping an IV controller
  manager instance. Used by the automated tester and other consumers that
  expect a simple instrument API.
- `MeasurementGUI`: the main window/class that constructs the Tkinter layout,
  handles user inputs, routes measurements to `MeasurementService`, updates
  live plots, and saves results.

Notes:
- The file intentionally routes most measurement work to `MeasurementService`
  to keep GUI logic separate from instrument/measurement details.
- Docstrings and inline comments focus on clarifying the intent of complex
  functions and public APIs rather than literal line-by-line explanation.
"""
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
from pathlib import Path
import queue
from PMU_Testing_GUI import PMUTestingGUI
from TSP_Testing_GUI import TSPTestingGUI

from telegram import PassportData

from Equipment.SMU_AND_PMU.Keithley2400 import Keithley2400Controller  # Import the Keithley class
from Equipment.iv_controller_manager import IVControllerManager
from Equipment.PowerSupplies.Keithley2220 import Keithley2220_Powersupply  # import power supply controll
from Equipment.temperature_controller_manager import TemperatureControllerManager
#from measurement_plotter import MeasurementPlotter, ThreadSafePlotter
from Measurments.measurement_services_smu import MeasurementService, VoltageRangeMode
from Equipment.optical_excitation import create_optical_from_system_config, OpticalExcitation
from typing import Optional, Any, Callable, Dict, List, Tuple, Union

# Import new utility modules
from Measurments.data_utils import safe_measure_current, safe_measure_voltage
from Measurments.optical_controller import OpticalController

from Check_Connection_GUI import CheckConnection
from TelegramBot import TelegramBot
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Optional-only imports for typing; avoids runtime deps if unavailable
    from Advanced_tests_GUI import AdvancedTestsGUI  # noqa: F401
    from PMU_Testing_GUI import PMUTestingGUI as _PMUTestingGUIType  # noqa: F401
    from Automated_tester_GUI import AutomatedTesterGUI as _AutomatedTesterGUIType  # noqa: F401
    # Test framework types
    from typing import Protocol
    class _Thresholds(Protocol):
        probe_voltage_v: float
        probe_duration_s: float
        probe_sample_hz: float
        working_current_a: float
        forming_voltages_v: List[float]
        forming_compliance_a: float
        forming_cooldown_s: float
        hyst_budget: float
        hyst_profiles: List[Any]
        endurance_cycles: int
        pulse_width_s: float
        retention_times_s: List[float]
        max_voltage_v: float
        max_compliance_a: float
from Equipment.TempControllers.OxfordITC4 import OxfordITC4
from Automated_tester_GUI import AutomatedTesterGUI

# Set logging level to WARNING (hides INFO messages)
logging.getLogger("pymeasure").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)

class SMUAdapter:
	"""Light adapter wrapping an IV controller manager to a minimal SMU-like API.

	This adapter provides a small, stable surface for consumers that expect a
	simple instrument object with methods such as `set_voltage`, `set_current`,
	`measure_current`, `measure_voltage`, `enable_output` and `close`.

	Attributes:
		_iv: underlying IV controller/manager instance (typed object)
		device: optional device identifier exposed by some instrument drivers

	Notes:
		The adapter performs small normalization steps (e.g. tuple -> float)
		so callers can assume simple return types. A NotImplementedError is raised
		when a fast-path API (like `run_tsp_sweep`) is not implemented by the
		underlying instrument.
	"""

	def __init__(self, iv_manager: Any) -> None:
		self._iv = iv_manager
		# For ad-hoc TSP fallback, expose an attribute named 'device' if available
		self.device = None
		try:
			inst = getattr(self._iv, 'instrument', None)
			if inst is not None and hasattr(inst, 'device'):
				self.device = inst.device
		except Exception:
			self.device = None

	def safe_init(self) -> None:
		return None

	def set_voltage(self, voltage: float, Icc: Optional[float] = None) -> None:
		if Icc is None:
			# Use a reasonable default if not specified
			Icc = 1e-3
		return self._iv.set_voltage(voltage, Icc)

	def set_current(self, current: float, Vcc: Optional[float] = None) -> None:
		if Vcc is None:
			Vcc = 10.0
		return self._iv.set_current(current, Vcc)

	def measure_voltage(self) -> float:
		val = self._iv.measure_voltage()
		try:
			# Some controllers return tuples; normalize to float
			if isinstance(val, (list, tuple)):
				return float(val[0] if len(val) > 0 else 0.0)
			return float(val)
		except Exception:
			return 0.0

	def measure_current(self) -> float:
		val = self._iv.measure_current()
		try:
			# Manager may return tuple (None, current)
			if isinstance(val, (list, tuple)):
				return float(val[-1])
			return float(val)
		except Exception:
			return 0.0

	def enable_output(self, enable: bool) -> None:
		return self._iv.enable_output(bool(enable))

	def close(self) -> None:
		try:
			return self._iv.close()
		except Exception:
			return None

	# Optional fast-path: if underlying controller implements run_tsp_sweep, expose it
	def run_tsp_sweep(self, start_v: float, stop_v: float, step_v: float,
					 icc_start: float, icc_factor: float = 10.0,
					 icc_max: Optional[float] = None, delay_s: float = 0.005,
					 burn_abort_A: Optional[float] = None) -> Any:
		inst = getattr(self._iv, 'instrument', None)
		if inst is not None and hasattr(inst, 'run_tsp_sweep'):
			return inst.run_tsp_sweep(start_v=start_v, stop_v=stop_v, step_v=step_v,
									  icc_start=icc_start, icc_factor=icc_factor,
									  icc_max=icc_max, delay_s=delay_s,
									  burn_abort_A=burn_abort_A)
		raise NotImplementedError("Underlying instrument does not support run_tsp_sweep")


class MeasurementGUI:
    """Graphical control panel for running and monitoring measurements.

    This class builds a Tkinter window that allows the user to configure and
    run a broad range of measurements (IV sweeps, pulsed IV, endurance,
    retention, transient captures, etc.) using an underlying
    `MeasurementService` and instrument managers (SMU/PSU/Temp).


    Main responsibilities:
    - Construct the GUI layout (connection, sweep parameters, plots, logs)
    - Translate GUI parameters into calls to `MeasurementService`
    - Manage instrument connections via `IVControllerManager`, PSU and
      temperature controller managers
    - Provide lightweight helpers for saving, plotting and messaging

    Attributes (selected):
        master (tk.Toplevel): The GUI top-level window container.
        sample_gui: reference to the sample-selection GUI (provides device list/index).
        device_list (list[str]): list of device ids managed by the GUI.
        measurement_service (MeasurementService): central engine performing measurements.
        keithley: underlying SMU/IV controller manager instance (or None).
        psu, temp_controller: optional external device managers.

    Note: many instance attributes are created at runtime and are documented
    inline where they are defined to avoid a huge upfront attribute block.
    """
    def __init__(self, master: tk.Misc, sample_type: str, section: str,
                 device_list: List[str], sample_gui: Any) -> None:
        # Commonly accessed attributes with explicit types for clarity
        self.keithley: Optional[Any] = None
        self.psu: Optional[Any] = None
        self.temp_controller: Optional[Any] = None
        self.itc: Optional[Any] = None
        self.lakeshore: Optional[Any] = None
        self.device_list: List[str] = device_list
        self.sample_gui: Any = sample_gui
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
        self.tests_running = False
        self.abort_tests_flag = False
        self.test_log_queue = queue.Queue()
        self.live_plot_enabled = tk.BooleanVar(value=True)


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
        self._telegram_bot = None
        # Runtime controls for custom sweeps
        self.pause_requested = False
        self.sweep_runtime_overrides = {}

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

        # Central measurement engine
        self.measurement_service = MeasurementService()


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
        self.create_manual_endurance_retention(self.left_frame)

        # middle
        self.create_sweep_parameters(self.middle_frame)
        self.create_custom_measurement_section(self.middle_frame)
        self.sequential_measurments(self.middle_frame)
        self.create_automated_tests_section(self.middle_frame)




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

        # Removed automated tests log frame

        atexit.register(self.cleanup)



    def cleanup(self) -> None:
        """Attempt to gracefully shutdown connected instruments and clear flags.

        This method is registered with `atexit` to ensure the SMU/PSU/temp
        controllers are left in a safe state when the GUI exits. It performs
        best-effort cleanup and swallows exceptions so shutdown proceeds.
        """

        #  self.keithley.shutdown()
        # # todo send comand to temp if connected to cool down to 0
        # if self.itc_connected:
        #     self.itc.set_temperature(0) # set temp controller tp 0 deg
        # if self.psu_connected:
        #     self.psu.disable_channel(1)
        #     self.psu.disable_channel(2)
        #     self.psu.close()
        try:
            if getattr(self, 'keithley', None):
                self.keithley.shutdown()
        except Exception:
            # Don't raise during process exit; just log to stdout where possible
            print("Warning: keithley.shutdown() failed during cleanup")

        # If a temperature controller is connected, try to set it to 0°C
        try:
            if getattr(self, 'itc_connected', False) and getattr(self, 'itc', None):
                self.itc.set_temperature(0)
        except Exception:
            print("Warning: could not reset temperature controller during cleanup")

        # Disable and close PSU channels if a PSU was connected
        try:
            if getattr(self, 'psu_connected', False) and getattr(self, 'psu', None):
                self.psu.disable_channel(1)
                self.psu.disable_channel(2)
                self.psu.close()
        except Exception:
            print("Warning: PSU cleanup failed")

        print("safely turned everything off")
        # Reset runtime test flags
        self.tests_running = False
        self.abort_tests_flag = False

    ###################################################################
    # Frames
    ###################################################################
    def top_banner(self, parent: tk.Misc) -> None:
        """Build the top banner: title and live status labels.

        Displays the app title and periodically-updated labels showing the
        currently selected device, most recent voltage sample, and loop/sweep
        number. Also includes quick-access buttons.
        """
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

        # Start periodic status updates for device/voltage/loop
        self._status_updates_active = True
        self.master.after(250, self._status_update_tick)

    def log_test(self, msg: str) -> None:
        """Append a line to the tests log widget or stdout if unavailable."""
        try:
            if hasattr(self, 'tests_log') and self.tests_log:
                self.tests_log.config(state=tk.NORMAL)
                self.tests_log.insert(tk.END, msg + "\n")
                self.tests_log.config(state=tk.DISABLED)
                self.tests_log.see(tk.END)
            else:
                print(msg)
        except Exception:
            print(msg)
    
    def open_autotest(self) -> None:
        """Open the Automated Tester window bound to this GUI.

        This prepares a simple `SMUAdapter` for the automated tester and
        provides a callback that advances the currently-selected device in the
        parent GUI. Any connection errors are reported to the user.
        """
        try:
            if not self.keithley:
                self.connect_keithley()
            if not self.keithley:
                messagebox.showerror("Instrument", "Keithley not connected.")
                return

            adapter = SMUAdapter(self.keithley)

            # Provide section and device helpers to the automated tester
            current_section_name = self.section

            def get_next_device():
                """Advance to the next device and update display labels.

                Returns the new device id string or None on error.
                """
                try:
                    # Advance internal index, wrap safely
                    self.current_index = (self.current_index + 1) % max(1, len(self.device_list))
                    self.current_device = self.device_list[self.current_index]
                    # Update any GUI labels that display the device name
                    self.device_section_and_number = self.convert_to_name(self.current_index)
                    self.display_index_section_number = self.current_device + "/" + self.device_section_and_number
                    try:
                        self.device_label.config(text=f"Device: {self.display_index_section_number}")
                    except Exception:
                        pass
                    try:
                        # Notify any listeners
                        self.master.event_generate('<<DeviceChanged>>', when='tail')
                    except Exception:
                        pass
                    return self.current_device
                except Exception:
                    return None

            AutomatedTesterGUI(
                self.master,
                instrument=adapter,
                current_section=current_section_name,
                device_list=self.device_list,
                get_next_device_cb=get_next_device,
                current_device_id=self.current_device,
                host_gui=self,
            )
        except Exception as e:
            messagebox.showerror("AutoTester", str(e))


    # ---------------- Telegram helpers -----------------
    def _bot_enabled(self) -> bool:
        """Return True if Telegram messaging is configured and enabled.

        Checks that the GUI toggle is set and that token/chat-id strings are
        present.
        """
        try:
            return bool(
                getattr(self, 'get_messaged_var', None)
                and self.get_messaged_var.get() == 1
                and getattr(self, 'token_var', None)
                and getattr(self, 'chatid_var', None)
                and self.token_var.get().strip()
                and self.chatid_var.get().strip()
            )
        except Exception:
            return False

    def _get_bot(self) -> Optional[Any]:
        """Return a cached `TelegramBot` instance or None.

        The bot is created lazily on first use. Errors creating the bot result
        in None being returned so callers can continue without messaging.
        """
        if not self._bot_enabled():
            return None
        if self._telegram_bot is None:
            try:
                self._telegram_bot = TelegramBot(self.token_var.get().strip(), self.chatid_var.get().strip())
            except Exception:
                self._telegram_bot = None
        return self._telegram_bot

    def _send_bot_message(self, text: str) -> None:
        """Send a simple text message via the configured Telegram bot.

        This is a safe wrapper that ignores messaging errors to avoid
        disrupting the GUI flow.
        """
        bot = self._get_bot()
        if bot:
            try:
                bot.send_message(text)
            except Exception:
                pass

    def _send_bot_image(self, image_path: str, caption: str = "") -> None:
        """Send an image (path) with optional caption via Telegram.

        Errors are swallowed so missing/invalid image paths do not crash the GUI.
        """
        bot = self._get_bot()
        if bot:
            try:
                bot.send_image(image_path, caption)
            except Exception:
                pass

    def _pump_test_logs(self) -> None:
        """Drain the in-memory test log queue and update the tests log widget.

        This method schedules itself via `after` while tests are running so the
        GUI receives incremental updates from background test threads.
        """
        drained = False
        try:
            while True:
                m = self.test_log_queue.get_nowait()
                drained = True
                self.log_test(m)
        except queue.Empty:
            pass

        # Continue polling while tests are running. If we drained logs just now
        # keep polling a little longer to avoid UI starvation.
        if self.tests_running:
            self.master.after(100, self._pump_test_logs)
        elif drained:
            self.master.after(100, self._pump_test_logs)

    def show_test_preferences(self) -> None:
        """Display current test preference thresholds in a read-only popup.

        The helper `load_thresholds` (from the test framework) provides a
        named structure containing probe settings, thresholds and safety limits.
        """
        t = load_thresholds()
        info = (
            f"Probe: {t.probe_voltage_v} V for {t.probe_duration_s}s @ {t.probe_sample_hz} Hz\n"
            f"Working I threshold: {t.working_current_a} A\n"
            f"Forming steps: {t.forming_voltages_v}, comp={t.forming_compliance_a} A, cooldown={t.forming_cooldown_s}s\n"
            f"Hyst budget: {t.hyst_budget}, profiles: {len(t.hyst_profiles)}\n"
            f"Endurance cycles: {t.endurance_cycles}, pulse width: {t.pulse_width_s}s\n"
            f"Retention times: {t.retention_times_s}\n"
            f"Safety: Vmax={t.max_voltage_v} V, Imax={t.max_compliance_a} A\n"
        )
        messagebox.showinfo("Test Preferences (read-only)", info)

    def create_automated_tests_section(self, parent: tk.Misc) -> None:
        """Create the section with buttons for automated and PMU tests."""
        frame = tk.LabelFrame(parent, text="More Tests", padx=5, pady=5)
        frame.grid(row=4, column=0, columnspan=2, padx=10, pady=5, sticky="ew")

        # # Only one button: open AutoTester GUI on demand
        # self.autopress_btn = tk.Button(frame, text="AutoPress", command=self.open_autotest)
        # self.autopress_btn.grid(row=0, column=0, padx=(5, 5), pady=(2, 2), sticky='w')

        # # Volatile/Non-volatile popup
        # def open_advanced():
        #     try:
        #         from Advanced_tests_GUI import AdvancedTestsGUI
        #         AdvancedTestsGUI(self.master, provider=self)
        #     except Exception as e:
        #         try:
        #             import traceback
        #             traceback.print_exc()
        #         except Exception:
        #             pass
        #         tk.messagebox.showerror("Advanced Tests", str(e))
        # self.adv_btn = tk.Button(frame, text="Volatile/Non-volatile Testing", command=open_advanced)
        # self.adv_btn.grid(row=0, column=2, padx=(5, 5), pady=(2, 2), sticky='w')

        # PMU testing button: opens a lightweight PMU Testing GUI
        
        try:
            self.pmu_btn = tk.Button(frame, text="PMU Testing", command=lambda: PMUTestingGUI(self.master, provider=self))
            
            self.pmu_btn.grid(row=0, column=1, padx=(5, 5), pady=(2, 2), sticky='w')
            print("importing PMU_Testing_GUI completed")
        except Exception:
            print("promblem with pmu testing gui")
            # If import fails, keep UI functional without PMU
            pass
        
        # TSP Testing button: opens Keithley 2450 TSP pulse testing GUI
        try:
            self.tsp_btn = tk.Button(frame, text="2450 TSP Pulse Testing", 
                                     command=lambda: TSPTestingGUI(self.master, provider=self))
            self.tsp_btn.grid(row=0, column=1, padx=(5, 5), pady=(2, 2), sticky='w')
            print("TSP_Testing_GUI loaded successfully")
        except Exception as e:
            print(f"Problem loading TSP Testing GUI: {e}")
            pass

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        frame.columnconfigure(3, weight=1)

    

    ###################################################################
    # Graph empty shells setting up for plotting
    ###################################################################
    def graphs_main_iv(self, parent: tk.Misc) -> None:
        """Create live IV and log-IV plots (single-sweep real-time)."""
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

    def graphs_all(self, parent: tk.Misc) -> None:
        """Create the two 'All sweeps' axes: linear and log(|I|)."""
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

    def graphs_vi_logiv(self, parent: tk.Misc) -> None:
        """Create V/I and log-log plots updated during measurements."""
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

    def graphs_endurance_retention(self, parent: tk.Misc) -> None:
        """Create small plots for Endurance (ON/OFF) and Retention (I vs t)."""
        frame = tk.LabelFrame(parent, text="Endurance & Retention", padx=5, pady=5)
        frame.grid(row=3, column=2, padx=10, pady=5, columnspan=1, rowspan=1, sticky="nsew")

        # Endurance (ON/OFF ratio over cycles)
        self.figure_endurance, self.ax_endurance = plt.subplots(figsize=(3, 2))
        self.ax_endurance.set_title("Endurance (ON/OFF)")
        self.ax_endurance.set_xlabel("Cycle")
        self.ax_endurance.set_ylabel("ON/OFF Ratio")
        self.canvas_endurance = FigureCanvasTkAgg(self.figure_endurance, master=frame)
        self.canvas_endurance.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        # Retention (Current vs time)
        self.figure_retention, self.ax_retention = plt.subplots(figsize=(3, 2))
        self.ax_retention.set_title("Retention")
        self.ax_retention.set_xlabel("Time (s)")
        self.ax_retention.set_ylabel("Current (A)")
        self.ax_retention.set_xscale('log')
        self.ax_retention.set_yscale('log')
        self.canvas_retention = FigureCanvasTkAgg(self.figure_retention, master=frame)
        self.canvas_retention.get_tk_widget().grid(row=0, column=1, sticky="nsew")

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(0, weight=1)

        # Data holders for plotting
        self.endurance_ratios = []
        self.retention_times = []
        self.retention_currents = []

    def create_manual_endurance_retention(self, parent: tk.Misc) -> None:
        """Build control panel for manual Endurance and Retention tasks."""
        frame = tk.LabelFrame(parent, text="Manual Endurance / Retention", padx=5, pady=5)
        frame.grid(row=6, column=0, padx=10, pady=5, sticky="ew")

        # Two-panel vertical layout (narrower, taller)
        end_frame = tk.Frame(frame)
        end_frame.grid(row=0, column=0, sticky='nw', padx=(0, 10))
        ret_frame = tk.Frame(frame)
        ret_frame.grid(row=0, column=1, sticky='ne')

        # Endurance controls (stacked)
        tk.Label(end_frame, text="Endurance").grid(row=0, column=0, columnspan=2, sticky='w')
        tk.Label(end_frame, text="SET V").grid(row=1, column=0, sticky='w')
        self.end_set_v = tk.DoubleVar(value=1.5)
        tk.Entry(end_frame, textvariable=self.end_set_v, width=8).grid(row=1, column=1, sticky='w')

        tk.Label(end_frame, text="RESET V").grid(row=2, column=0, sticky='w')
        self.end_reset_v = tk.DoubleVar(value=-1.5)
        tk.Entry(end_frame, textvariable=self.end_reset_v, width=8).grid(row=2, column=1, sticky='w')

        tk.Label(end_frame, text="Pulse (ms)").grid(row=3, column=0, sticky='w')
        self.end_pulse_ms = tk.DoubleVar(value=10)
        tk.Entry(end_frame, textvariable=self.end_pulse_ms, width=8).grid(row=3, column=1, sticky='w')

        tk.Label(end_frame, text="Cycles").grid(row=4, column=0, sticky='w')
        self.end_cycles = tk.IntVar(value=100)
        tk.Entry(end_frame, textvariable=self.end_cycles, width=8).grid(row=4, column=1, sticky='w')

        tk.Label(end_frame, text="Read V").grid(row=5, column=0, sticky='w')
        self.end_read_v = tk.DoubleVar(value=0.2)
        tk.Entry(end_frame, textvariable=self.end_read_v, width=8).grid(row=5, column=1, sticky='w')

        tk.Button(end_frame, text="Start Endurance", command=self.start_manual_endurance).grid(row=6, column=0, columnspan=2, pady=(4,0), sticky='w')

        # Retention controls (stacked)
        tk.Label(ret_frame, text="Retention").grid(row=0, column=0, columnspan=2, sticky='w')
        tk.Label(ret_frame, text="SET V").grid(row=1, column=0, sticky='w')
        self.ret_set_v = tk.DoubleVar(value=1.5)
        tk.Entry(ret_frame, textvariable=self.ret_set_v, width=8).grid(row=1, column=1, sticky='w')

        tk.Label(ret_frame, text="SET Time (ms)").grid(row=2, column=0, sticky='w')
        self.ret_set_ms = tk.DoubleVar(value=10)
        tk.Entry(ret_frame, textvariable=self.ret_set_ms, width=8).grid(row=2, column=1, sticky='w')

        tk.Label(ret_frame, text="Read V").grid(row=3, column=0, sticky='w')
        self.ret_read_v = tk.DoubleVar(value=0.2)
        tk.Entry(ret_frame, textvariable=self.ret_read_v, width=8).grid(row=3, column=1, sticky='w')

        tk.Label(ret_frame, text="Every (s)").grid(row=4, column=0, sticky='w')
        self.ret_every_s = tk.DoubleVar(value=10.0)
        tk.Entry(ret_frame, textvariable=self.ret_every_s, width=8).grid(row=4, column=1, sticky='w')

        tk.Label(ret_frame, text="# Points").grid(row=5, column=0, sticky='w')
        self.ret_points = tk.IntVar(value=30)
        tk.Entry(ret_frame, textvariable=self.ret_points, width=8).grid(row=5, column=1, sticky='w')

        self.ret_estimate_var = tk.StringVar(value="Total: ~300 s")
        tk.Label(ret_frame, textvariable=self.ret_estimate_var, fg="grey").grid(row=6, column=0, columnspan=2, sticky='w')

        tk.Button(ret_frame, text="Start Retention", command=self.start_manual_retention).grid(row=7, column=0, columnspan=2, pady=(4,0), sticky='w')

        # LED row spanning under both panels
        led_frame = tk.Frame(frame)
        led_frame.grid(row=1, column=0, columnspan=2, sticky='w', pady=(6,0))
        tk.Label(led_frame, text="LED:").pack(side='left')
        self.manual_led_power = tk.DoubleVar(value=1.0)
        tk.Entry(led_frame, textvariable=self.manual_led_power, width=8).pack(side='left', padx=(4,4))
        self.manual_led_on = False
        self.manual_led_btn = tk.Button(led_frame, text="LED OFF", command=self.toggle_manual_led)
        self.manual_led_btn.pack(side='left')

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

    def toggle_manual_led(self) -> None:
        """Toggle the optical source (LED/Laser) using configured abstraction."""
        try:
            # Prefer new optical abstraction if available
            if hasattr(self, 'optical') and self.optical is not None:
                if not self.manual_led_on:
                    lvl = float(self.manual_led_power.get())
                    unit = getattr(self.optical, 'capabilities', {}).get('units', 'mW')
                    self.optical.set_level(lvl, unit)
                    self.optical.set_enabled(True)
                    self.manual_led_on = True
                    self.manual_led_btn.config(text="LIGHT ON")
                else:
                    self.optical.set_enabled(False)
                    self.manual_led_on = False
                    self.manual_led_btn.config(text="LIGHT OFF")
                return
            # Legacy PSU path fallback
            if not getattr(self, 'psu_connected', False):
                self.connect_keithley_psu()
            if not self.manual_led_on:
                self.psu.led_on_380(self.manual_led_power.get())
                self.manual_led_on = True
                self.manual_led_btn.config(text="LED ON")
            else:
                self.psu.led_off_380()
                self.manual_led_on = False
                self.manual_led_btn.config(text="LED OFF")
        except Exception:
            pass

    def start_manual_endurance(self) -> None:
        """Kick off manual endurance in a background worker thread."""
        if not self.connected:
            messagebox.showwarning("Warning", "Not connected to Keithley!")
            return
        threading.Thread(target=self._manual_endurance_worker, daemon=True).start()

    def _manual_endurance_worker(self) -> None:
        """Worker: alternates SET/RESET pulses and plots ON/OFF ratio."""
        try:
            set_v = self.end_set_v.get()
            reset_v = self.end_reset_v.get()
            width_s = max(0.001, self.end_pulse_ms.get() / 1000.0)
            cycles = max(1, self.end_cycles.get())
            read_v = self.end_read_v.get()
            icc = self.icc.get()

            self.endurance_ratios = []
            self.keithley.enable_output(True)
            for idx in range(cycles):
                if self.stop_measurement_flag:
                    break
                # SET
                self.keithley.set_voltage(set_v, icc)
                time.sleep(width_s)
                # Read ON
                self.keithley.set_voltage(read_v, icc)
                time.sleep(0.01)
                i_on = safe_measure_current(self.keithley)
                # RESET
                self.keithley.set_voltage(reset_v, icc)
                time.sleep(width_s)
                # Read OFF
                self.keithley.set_voltage(read_v, icc)
                time.sleep(0.01)
                i_off = safe_measure_current(self.keithley)
                ratio = (abs(i_on) + 1e-12) / (abs(i_off) + 1e-12)
                self.endurance_ratios.append(ratio)
                # Update plot
                self.ax_endurance.clear()
                self.ax_endurance.set_title("Endurance (ON/OFF)")
                self.ax_endurance.set_xlabel("Cycle")
                self.ax_endurance.set_ylabel("ON/OFF Ratio")
                self.ax_endurance.plot(range(1, len(self.endurance_ratios)+1), self.endurance_ratios, marker='o')
                self.canvas_endurance.draw()
            self.keithley.enable_output(False)
        except Exception as e:
            print("Manual endurance error:", e)

    def start_manual_retention(self) -> None:
        """Kick off manual retention capture in a background worker thread."""
        if not self.connected:
            messagebox.showwarning("Warning", "Not connected to Keithley!")
            return
        # Update estimate
        try:
            total = max(1, self.ret_points.get()) * max(0.001, self.ret_every_s.get())
            self.ret_estimate_var.set(f"Total: ~{int(total)} s")
        except Exception:
            pass
        threading.Thread(target=self._manual_retention_worker, daemon=True).start()

    def _manual_retention_worker(self) -> None:
        """Worker: applies SET then samples current at READ V over time (log-log plot)."""
        try:
            set_v = self.ret_set_v.get()
            set_ms = max(0.001, self.ret_set_ms.get() / 1000.0)
            read_v = self.ret_read_v.get()
            # Build uniform schedule using every and points
            try:
                every = max(0.001, self.ret_every_s.get())
                points = max(1, self.ret_points.get())
                times = [every * i for i in range(1, points + 1)]
            except Exception:
                times = [10 * i for i in range(1, 31)]
            icc = self.icc.get()

            self.retention_times = []
            self.retention_currents = []
            self.keithley.enable_output(True)
            # Apply SET
            self.keithley.set_voltage(set_v, icc)
            time.sleep(set_ms)
            # Retention reads
            t0 = time.time()
            for t in times:
                while (time.time() - t0) < t:
                    time.sleep(0.01)
                self.keithley.set_voltage(read_v, icc)
                time.sleep(0.01)
                i = safe_measure_current(self.keithley)
                self.retention_times.append(t)
                self.retention_currents.append(abs(i))
                # Update plot
                self.ax_retention.clear()
                self.ax_retention.set_title("Retention")
                self.ax_retention.set_xlabel("Time (s)")
                self.ax_retention.set_ylabel("Current (A)")
                self.ax_retention.set_xscale('log')
                self.ax_retention.set_yscale('log')
                self.ax_retention.plot(self.retention_times, self.retention_currents, marker='x')
                self.canvas_retention.draw()
            self.keithley.enable_output(False)
        except Exception as e:
            print("Manual retention error:", e)

    def graphs_current_time_rt(self, parent: tk.Misc) -> None:
        """Create Current vs Time live plot and start its update thread."""
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

    def graphs_resistance_time_rt(self, parent: tk.Misc) -> None:
        """Create Resistance vs Time live plot and start its update thread."""
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

    def graphs_temp_time_rt(self, parent: tk.Misc) -> None:
        """Create Temperature vs Time plot if a temp controller is connected."""

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

    def _status_update_tick(self):
        try:
            # Device name
            try:
                current_device = self.sample_gui.device_var.get()
            except Exception:
                current_device = self.display_index_section_number
            if current_device:
                self.device_label.config(text=f"Device: {current_device}")

            # Current voltage (latest sample if available)
            if self.v_arr_disp:
                try:
                    v_now = float(self.v_arr_disp[-1])
                    self.voltage_label.config(text=f"Voltage: {v_now:.3f} V")
                except Exception:
                    pass

            # Loop number (if known)
            loop_val = None
            if getattr(self, 'sweep_num', None) is not None:
                loop_val = self.sweep_num
            elif getattr(self, 'measurment_number', None) is not None:
                loop_val = self.measurment_number
            if loop_val is not None:
                self.loop_label.config(text=f"Loop: {loop_val}")
        finally:
            if self._status_updates_active and self.master.winfo_exists():
                self.master.after(250, self._status_update_tick)

    def plot_current_time(self) -> None:
        """Background plotter thread: update Current vs Time plot.

        This method runs in a dedicated thread and periodically checks the
        `self.measuring` flag. When measurements are active it copies the
        plotting buffers and updates the matplotlib line objects safely.
        """
        while True:
            if self.measuring:
                try:
                    x = list(self.t_arr_disp)
                    y = list(self.c_arr_disp)
                    n = min(len(x), len(y))
                    if n > 0:
                        self.line_ct_rt.set_data(x[:n], y[:n])
                        self.ax_ct_rt.relim()
                        self.ax_ct_rt.autoscale_view()
                        self.canvas_ct_rt.draw()
                except Exception:
                    pass
            time.sleep(0.1)

    def plot_vi_logilogv(self) -> None:
        """Background plotter thread: update V/I and log-log axes.

        Keeps the V/I and log-log plots in sync with the shared buffers.
        """
        while True:
            if self.measuring:
                try:
                    x = list(self.c_arr_disp)
                    y = list(self.v_arr_disp)
                    n = min(len(x), len(y))
                    if n > 0:
                        self.line_rt_vi.set_data(x[:n], y[:n])
                        self.ax_rt_vi.relim()
                        self.ax_rt_vi.autoscale_view()
                        self.canvas_rt_vi.draw()
                except Exception:
                    pass

                try:
                    vx = list(self.v_arr_disp)
                    vy = list(self.c_arr_disp)
                    n2 = min(len(vx), len(vy))
                    if n2 > 0 and np.any(np.array(vx[:n2]) > 0):
                        self.line_rt_logilogv.set_data(vx[:n2], vy[:n2])
                        self.ax_rt_logilogv.relim()
                        self.ax_rt_logilogv.autoscale_view()
                        self.canvas_rt_logilogv.draw()
                except Exception:
                    pass

            time.sleep(0.1)

    def plot_voltage_current(self) -> None:
        """Background plotter thread: update IV and |I| (log) plots.

        Regularly copies shared buffers into the live line objects so the GUI
        displays the most recent measurement points.
        """
        while True:
            if self.measuring:
                try:
                    x = list(self.v_arr_disp)
                    y = list(self.c_arr_disp)
                    n = min(len(x), len(y))
                    if n > 0:
                        self.line_rt_iv.set_data(x[:n], y[:n])
                        self.ax_rt_iv.relim()
                        self.ax_rt_iv.autoscale_view()
                        self.canvas_rt_iv.draw()
                except Exception:
                    pass

                try:
                    x2 = list(self.v_arr_disp)
                    y2 = list(self.c_arr_disp_abs)
                    n2 = min(len(x2), len(y2))
                    if n2 > 0:
                        self.line_rt_logiv.set_data(x2[:n2], y2[:n2])
                        self.ax_rt_logiv.relim()
                        self.ax_rt_logiv.autoscale_view()
                        self.canvas_rt_logiv.draw()
                except Exception:
                    pass

            time.sleep(0.1)

    def plot_resistance_time(self) -> None:
        """Background plotter thread: update Resistance vs Time plot."""
        while True:
            if self.measuring:
                try:
                    x = list(self.t_arr_disp)
                    y = list(self.r_arr_disp)
                    n = min(len(x), len(y))
                    if n > 0:
                        self.line_rt_rt.set_data(x[:n], y[:n])
                        self.ax_rt_rt.relim()
                        self.ax_rt_rt.autoscale_view()
                        self.canvas_rt_rt.draw()
                except Exception:
                    pass
            time.sleep(0.1)

    def plot_Temp_time(self) -> None:
        """Background plotter thread: update temperature-time plot (if enabled)."""
        while True:
            if self.measuring:
                try:
                    x = list(self.t_arr_disp)
                    y = list(self.c_arr_disp)
                    n = min(len(x), len(y))
                    if n > 0:
                        self.line_tt_rt.set_data(x[:n], y[:n])
                        self.ax_tt_rt.relim()
                        self.ax_tt_rt.autoscale_view()
                        self.canvas_tt_rt.draw()
                except Exception:
                    pass
            time.sleep(0.1)

    ###################################################################
    # seequencial plotting
    ###################################################################

    # Add to your GUI initialization
    def create_plot_menu(self) -> None:
        """Create menu options for plotting."""
        # Add to your menu bar
        plot_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Plot", menu=plot_menu)

        plot_menu.add_command(label="Open Live Plotter", command=self.open_live_plotter)
        plot_menu.add_separator()
        plot_menu.add_command(label="Export All Plots", command=self.export_all_plots)
        plot_menu.add_command(label="Save Current Plot", command=self.save_current_plot)

    def open_live_plotter(self) -> None:
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

    def export_all_plots(self) -> None:
        """Export plots from the current plotter."""
        if hasattr(self, 'plotter') and self.plotter and self.plotter.window.winfo_exists():
            self.plotter.export_data()
        else:
            tk.messagebox.showinfo("No Active Plotter", "No active measurement plotter found.")

    def save_current_plot(self) -> None:
        """Save the current plot as an image."""
        if hasattr(self, 'plotter') and self.plotter and self.plotter.window.winfo_exists():
            self.plotter.save_current_plot()
        else:
            tk.messagebox.showinfo("No Active Plotter", "No active measurement plotter found.")

    ###################################################################
    # GUI mETHODS
    ###################################################################


    def create_connection_section(self, parent: tk.Misc) -> None:
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

    def set_default_system(self) -> None:
        systems = self.systems
        default = "Lab Small"
        if default in systems:
            self.system_var.set(default)
            self.on_system_change(default)  # Trigger the address updates
        elif systems and systems[0] != "No systems available":
            self.system_var.set(systems[0])
            self.on_system_change(systems[0])

    def load_systems(self) -> List[str]:
        """Load system configurations from JSON file"""
        config_file = "Json_Files/system_configs.json"

        try:
            with open(config_file, 'r') as f:
                self.system_configs = json.load(f)
            return list(self.system_configs.keys())
        except (FileNotFoundError, json.JSONDecodeError):
            return ["No systems available"]

    def on_system_change(self, selected_system: str) -> None:
        """Update addresses when system selection changes"""
        if selected_system in self.system_configs:
            config = self.system_configs[selected_system]

            # Update IV section
            iv_address = config.get("SMU_address", "")
            self.iv_address = iv_address
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
            print(self.SMU_type)

            # Optical excitation (LED/Laser) selection based on config
            try:
                self.optical = create_optical_from_system_config(config)
            except Exception:
                self.optical = None


    def update_component_state(self, component_type: str, address: str) -> None:
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

    def create_mode_selection(self,parent: tk.Misc) -> None:
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

        # Additional Info Entry
        self.additional_info_label = tk.Label(mode_frame, text="Additional Info:")
        self.additional_info_label.grid(row=3, column=0, sticky="w")

        self.additional_info_var = tk.StringVar()  # Use a StringVar
        self.additional_info_entry = ttk.Entry(mode_frame, textvariable=self.additional_info_var)
        self.additional_info_entry.grid(row=3, column=1, columnspan=1, sticky="ew")
        
        # Save Location Controls
        save_location_frame = tk.Frame(mode_frame)
        save_location_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(5, 0))
        mode_frame.columnconfigure(1, weight=1)
        
        self.use_custom_save_var = tk.BooleanVar(value=False)
        self.custom_save_location_var = tk.StringVar(value="")
        self.custom_save_location = None  # Will store Path object
        
        tk.Checkbutton(save_location_frame, text="Use custom save location", 
                      variable=self.use_custom_save_var,
                      command=self._on_custom_save_toggle).grid(row=0, column=0, sticky="w")
        
        save_path_frame = tk.Frame(save_location_frame)
        save_path_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(2, 0))
        save_path_frame.columnconfigure(0, weight=1)
        
        self.save_path_entry = tk.Entry(save_path_frame, textvariable=self.custom_save_location_var, 
                                        state="disabled", width=40)
        self.save_path_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        
        tk.Button(save_path_frame, text="Browse...", 
                 command=self._browse_save_location,
                 state="disabled").grid(row=0, column=1)
        
        # Load saved preference
        self._load_save_location_config()



    def create_sweep_parameters(self, parent: tk.Misc) -> None:
        """Sweep parameter section"""
        frame = tk.LabelFrame(parent, text="Sweep Parameters", padx=5, pady=5)
        frame.grid(row=2, column=0,columnspan = 2 ,padx=10, pady=5, sticky="ew")

        # Measurement Type selector (DC Triangle IV, SMU_AND_PMU pulse modes, etc.)
        tk.Label(frame, text="Measurement Type:").grid(row=0, column=0, sticky="w")
        self.excitation_var = tk.StringVar(value="DC Triangle IV")
        self.excitation_menu = ttk.Combobox(frame, textvariable=self.excitation_var,
                                            values=["DC Triangle IV",
                                                    "SMU_AND_PMU Pulsed IV <1.5v",
                                                    "SMU_AND_PMU Pulsed IV >1.5v",
                                                    "SMU_AND_PMU Fast Pulses",
                                                    "SMU_AND_PMU Fast Hold",
                                                    "ISPP",
                                                    "Pulse Width Sweep",
                                                    "Threshold Search",
                                                    "Transient Decay"], state="readonly")
        self.excitation_menu.grid(row=0, column=1, sticky="ew")

        # Source Mode Selection (placed right after measurement type)
        tk.Label(frame, text="Source Mode:", font=("Arial", 9, "bold")).grid(row=1, column=0, sticky="w")
        self.source_mode_var = tk.StringVar(value="voltage")  # Default: voltage source
        source_mode_dropdown = ttk.Combobox(
            frame, 
            textvariable=self.source_mode_var,
            values=["voltage", "current"],
            state="readonly",
            width=18
        )
        source_mode_dropdown.grid(row=1, column=1, sticky="w")
        
        # Info label for source mode
        #info_label = tk.Label(frame, text="ℹ️ Current mode works best with Keithley 4200A", 
        #                     fg="gray", font=("Arial", 7))
        #info_label.grid(row=1, column=2, sticky="w", padx=(5, 0))

        # Dynamic params container for excitation-specific options
        exc_dyn = tk.Frame(frame)
        exc_dyn.grid(row=2, column=0, columnspan=2, sticky="ew")
        exc_dyn.columnconfigure(1, weight=1)
        self._excitation_params_frame = exc_dyn

        # Tk variables for pulse modes
        # Pulsed IV
        self.ex_piv_start = tk.DoubleVar(value=0.0)
        self.ex_piv_stop = tk.DoubleVar(value=1.0)
        self.ex_piv_step = tk.DoubleVar(value=0.1)
        self.ex_piv_nsteps = tk.IntVar(value=0)  # 0 -> ignored
        self.ex_piv_width_ms = tk.DoubleVar(value=1.0)
        self.ex_piv_vbase = tk.DoubleVar(value=0.2)
        self.ex_piv_inter_delay = tk.DoubleVar(value=0.0)
        # Fast pulses
        self.ex_fp_voltage = tk.DoubleVar(value=0.2)
        self.ex_fp_width_ms = tk.DoubleVar(value=1.0)
        self.ex_fp_num = tk.IntVar(value=10)
        self.ex_fp_inter_delay = tk.DoubleVar(value=0.0)
        self.ex_fp_vbase = tk.DoubleVar(value=0.2)
        self.ex_fp_max_speed = tk.BooleanVar(value=False)
        # Fast hold
        self.ex_fh_voltage = tk.DoubleVar(value=0.2)
        self.ex_fh_duration = tk.DoubleVar(value=5.0)
        self.ex_fh_sample_dt = tk.DoubleVar(value=0.01)

        # DC Triangle configuration variables used by dynamic UI below
        # Sweep Mode and Sweep Type
        self.sweep_mode_var = tk.StringVar(value=VoltageRangeMode.FIXED_STEP)
        self.sweep_type_var = tk.StringVar(value="FS")
        # Dynamic params variables (used when mode is rate/time based)
        self.var_sweep_rate = tk.DoubleVar(value=1.0)     # V/s
        self.var_total_time = tk.DoubleVar(value=5.0)     # s
        self.var_num_steps = tk.IntVar(value=101)

        def _min_pulse_width_ms_default() -> float:
            try:
                smu_type = getattr(self, 'SMU_type', 'Keithley 2401')
                limits = self.measurement_service.get_smu_limits(smu_type)
                return float(limits.get("min_pulse_width_ms", 1.0))
            except Exception:
                return 1.0

        def render_excitation_params(*_):
            for w in list(self._excitation_params_frame.children.values()):
                try: w.destroy()
                except Exception: pass
            sel = self.excitation_var.get()
            r = 0
            if sel == "DC Triangle IV":
                tk.Label(self._excitation_params_frame, text="Triangle IV sweep (FS/PS/NS).", fg="grey").grid(row=r, column=0, columnspan=2, sticky="w"); r+=1
                # Sweep Mode
                tk.Label(self._excitation_params_frame, text="Sweep Mode:").grid(row=r, column=0, sticky="w")
                sweep_mode_menu = ttk.Combobox(self._excitation_params_frame, textvariable=self.sweep_mode_var,
                                               values=[VoltageRangeMode.FIXED_STEP,
                                                       VoltageRangeMode.FIXED_SWEEP_RATE,
                                                       VoltageRangeMode.FIXED_VOLTAGE_TIME], state="readonly")
                sweep_mode_menu.grid(row=r, column=1, sticky="ew"); r+=1
                # Sweep Type directly below
                tk.Label(self._excitation_params_frame, text="Sweep Type:").grid(row=r, column=0, sticky="w")
                sweep_type_menu = ttk.Combobox(self._excitation_params_frame, textvariable=self.sweep_type_var,
                                               values=["FS", "PS", "NS"], state="readonly")
                sweep_type_menu.grid(row=r, column=1, sticky="ew"); r+=1

                # Dynamic params for mode (rendered in place of Step/Delay at rows 5 and 6 below)
                # Prepare alternating widgets (created lazily when needed)
                if not hasattr(self, '_dc_alt_lbl1'):
                    self._dc_alt_lbl1 = None; self._dc_alt_ent1 = None
                    self._dc_alt_lbl2 = None; self._dc_alt_ent2 = None

                def _toggle_dc_step_fields(show: bool):
                    try:
                        if show:
                            self._dc_lbl_step.grid()
                            self._dc_ent_step.grid()
                            self._dc_lbl_dwell.grid()
                            self._dc_ent_dwell.grid()
                        else:
                            self._dc_lbl_step.grid_remove()
                            self._dc_ent_step.grid_remove()
                            self._dc_lbl_dwell.grid_remove()
                            self._dc_ent_dwell.grid_remove()
                    except Exception:
                        pass

                def render_dynamic_params(*_):
                    # Clear any alternate widgets
                    try:
                        if self._dc_alt_lbl1: self._dc_alt_lbl1.grid_remove()
                        if self._dc_alt_ent1: self._dc_alt_ent1.grid_remove()
                        if self._dc_alt_lbl2: self._dc_alt_lbl2.grid_remove()
                        if self._dc_alt_ent2: self._dc_alt_ent2.grid_remove()
                    except Exception:
                        pass
                    mode = self.sweep_mode_var.get()
                    if mode == VoltageRangeMode.FIXED_STEP:
                        # Show step size and step delay; nothing extra here
                        _toggle_dc_step_fields(True)
                    elif mode == VoltageRangeMode.FIXED_SWEEP_RATE:
                        _toggle_dc_step_fields(False)
                        # Row 6: Sweep rate (V/s)
                        self._dc_alt_lbl1 = tk.Label(frame, text="Sweep rate (V/s):")
                        self._dc_alt_lbl1.grid(row=6, column=0, sticky="w")
                        self._dc_alt_ent1 = tk.Entry(frame, textvariable=self.var_sweep_rate)
                        self._dc_alt_ent1.grid(row=6, column=1, sticky="ew")
                        # Row 7: # Steps (optional)
                        self._dc_alt_lbl2 = tk.Label(frame, text="# Steps (optional):")
                        self._dc_alt_lbl2.grid(row=7, column=0, sticky="w")
                        self._dc_alt_ent2 = tk.Entry(frame, textvariable=self.var_num_steps)
                        self._dc_alt_ent2.grid(row=7, column=1, sticky="ew")
                    elif mode == VoltageRangeMode.FIXED_VOLTAGE_TIME:
                        _toggle_dc_step_fields(False)
                        # Row 6: Total sweep time (s)
                        self._dc_alt_lbl1 = tk.Label(frame, text="Total sweep time (s):")
                        self._dc_alt_lbl1.grid(row=6, column=0, sticky="w")
                        self._dc_alt_ent1 = tk.Entry(frame, textvariable=self.var_total_time)
                        self._dc_alt_ent1.grid(row=6, column=1, sticky="ew")
                        # Row 7: # Steps (optional)
                        self._dc_alt_lbl2 = tk.Label(frame, text="# Steps (optional):")
                        self._dc_alt_lbl2.grid(row=7, column=0, sticky="w")
                        self._dc_alt_ent2 = tk.Entry(frame, textvariable=self.var_num_steps)
                        self._dc_alt_ent2.grid(row=7, column=1, sticky="ew")
                sweep_mode_menu.bind("<<ComboboxSelected>>", render_dynamic_params)
                render_dynamic_params()
                # Show DC widgets
                try:
                    for w in self._dc_widgets:
                        try: w.grid()  # restore
                        except Exception: pass
                except Exception:
                    pass
                return
            if sel == "SMU_AND_PMU Pulsed IV <1.5v":
                # Defaults tied to SMU_AND_PMU min pulse width and base 0.2 V
                try:
                    self.ex_piv_width_ms.set(_min_pulse_width_ms_default())
                except Exception:
                    pass
                tk.Label(self._excitation_params_frame, text="One pulse per amplitude, read at Vbase; plots A vs I.", fg="grey").grid(row=r, column=0, columnspan=2, sticky="w"); r+=1
                # For pulse modes, hide DC sweep-mode/type, so nothing to render here
                tk.Label(self._excitation_params_frame, text="Vstart").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self.ex_piv_start, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Vstop").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self.ex_piv_stop, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Step (use or set #steps)").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self.ex_piv_step, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="#Steps (optional)").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self.ex_piv_nsteps, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Pulse width (ms)").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self.ex_piv_width_ms, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Vbase").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self.ex_piv_vbase, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Inter-step delay (s)").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self.ex_piv_inter_delay, width=10).grid(row=r, column=1, sticky="w"); r+=1
                # Hide DC widgets
                try:
                    for w in self._dc_widgets:
                        try: w.grid_remove()
                        except Exception: pass
                except Exception:
                    pass
                # Notes for <1.5 V mode
                tk.Label(self._excitation_params_frame, text="Note: Output is typically limited ~1.5 V depending on pulse width.", fg="grey", wraplength=380, justify='left').grid(row=r, column=0, columnspan=2, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Tip: Verify pulse width on an oscilloscope; effective width is often slower than the set value.", fg="grey", wraplength=380, justify='left').grid(row=r, column=0, columnspan=2, sticky="w"); r+=1
                return
            if sel == "SMU_AND_PMU Pulsed IV >1.5v":
                try:
                    self.ex_piv_width_ms.set(_min_pulse_width_ms_default())
                except Exception:
                    pass
                tk.Label(self._excitation_params_frame, text="Fixed 20 V range + OVP.", fg="grey").grid(row=r, column=0, columnspan=2, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Vstart").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self.ex_piv_start, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Vstop").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self.ex_piv_stop, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Step (use or set #steps)").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self.ex_piv_step, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="#Steps (optional)").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self.ex_piv_nsteps, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Pulse width (ms)").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self.ex_piv_width_ms, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Vbase").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self.ex_piv_vbase, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Inter-step delay (s)").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self.ex_piv_inter_delay, width=10).grid(row=r, column=1, sticky="w"); r+=1
                try:
                    for w in self._dc_widgets:
                        try: w.grid_remove()
                        except Exception: pass
                except Exception:
                    pass
                # Notes for >1.5 V mode (20 V range)
                tk.Label(self._excitation_params_frame, text="Note: 20 V range is slower; use ≥100 ms pulse width for reliable amplitude.", fg="grey", wraplength=380, justify='left').grid(row=r, column=0, columnspan=2, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Tip: Verify pulses on an oscilloscope; rise/fall can reduce effective width.", fg="grey", wraplength=380, justify='left').grid(row=r, column=0, columnspan=2, sticky="w"); r+=1
                return
            if sel == "SMU_AND_PMU Fast Pulses":
                try:
                    self.ex_fp_width_ms.set(_min_pulse_width_ms_default())
                except Exception:
                    pass
                tk.Label(self._excitation_params_frame, text="Pulse train; read after each at Vbase.", fg="grey").grid(row=r, column=0, columnspan=2, sticky="w"); r+=1
                # For pulse modes, hide DC sweep-mode/type
                tk.Label(self._excitation_params_frame, text="Pulse V").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self.ex_fp_voltage, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Pulse width (ms)").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self.ex_fp_width_ms, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="# Pulses").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self.ex_fp_num, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Inter-pulse delay (s)").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self.ex_fp_inter_delay, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Vbase").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self.ex_fp_vbase, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Checkbutton(self._excitation_params_frame, text="Max speed (min width, 0 delay)", variable=self.ex_fp_max_speed).grid(row=r, column=0, columnspan=2, sticky="w"); r+=1
                try:
                    for w in self._dc_widgets:
                        try: w.grid_remove()
                        except Exception: pass
                except Exception:
                    pass
                return
            if sel == "SMU_AND_PMU Fast Hold":
                tk.Label(self._excitation_params_frame, text="Hold DC and sample I(t).", fg="grey").grid(row=r, column=0, columnspan=2, sticky="w"); r+=1
                # For pulse modes, hide DC sweep-mode/type
                tk.Label(self._excitation_params_frame, text="Hold V").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self.ex_fh_voltage, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Duration (s)").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self.ex_fh_duration, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Sample dt (s)").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self.ex_fh_sample_dt, width=10).grid(row=r, column=1, sticky="w"); r+=1
                try:
                    for w in self._dc_widgets:
                        try: w.grid_remove()
                        except Exception: pass
                except Exception:
                    pass
                return
            if sel == "ISPP":
                tk.Label(self._excitation_params_frame, text="Increase pulse amplitude until target |I|.", fg="grey").grid(row=r, column=0, columnspan=2, sticky="w"); r+=1
                # Params: start, stop, step, pulse_ms, vbase, target I, inter-step
                self._ispp_start = tk.DoubleVar(value=0.0)
                self._ispp_stop = tk.DoubleVar(value=1.0)
                self._ispp_step = tk.DoubleVar(value=0.1)
                self._ispp_pulse_ms = tk.DoubleVar(value=1.0)
                self._ispp_vbase = tk.DoubleVar(value=0.2)
                self._ispp_target = tk.DoubleVar(value=1e-5)
                self._ispp_inter = tk.DoubleVar(value=0.0)
                tk.Label(self._excitation_params_frame, text="Start V").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self._ispp_start, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Stop V").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self._ispp_stop, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Step V").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self._ispp_step, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Pulse (ms)").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self._ispp_pulse_ms, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Vbase").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self._ispp_vbase, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Target |I| (A)").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self._ispp_target, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Inter-step (s)").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self._ispp_inter, width=10).grid(row=r, column=1, sticky="w"); r+=1
                try:
                    for w in self._dc_widgets:
                        try: w.grid_remove()
                        except Exception: pass
                except Exception:
                    pass
                return
            if sel == "Pulse Width Sweep":
                tk.Label(self._excitation_params_frame, text="Sweep pulse width at fixed amplitude.", fg="grey").grid(row=r, column=0, columnspan=2, sticky="w"); r+=1
                self._pws_amp = tk.DoubleVar(value=0.5)
                self._pws_widths = tk.StringVar(value="1,2,5,10")
                self._pws_vbase = tk.DoubleVar(value=0.2)
                self._pws_inter = tk.DoubleVar(value=0.0)
                tk.Label(self._excitation_params_frame, text="Amplitude V").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self._pws_amp, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Widths (ms, csv)").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self._pws_widths, width=14).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Vbase").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self._pws_vbase, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Inter-step (s)").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self._pws_inter, width=10).grid(row=r, column=1, sticky="w"); r+=1
                try:
                    for w in self._dc_widgets:
                        try: w.grid_remove()
                        except Exception: pass
                except Exception:
                    pass
                return
            if sel == "Threshold Search":
                tk.Label(self._excitation_params_frame, text="Binary search V within range to reach target |I|.", fg="grey").grid(row=r, column=0, columnspan=2, sticky="w"); r+=1
                self._th_lo = tk.DoubleVar(value=0.0)
                self._th_hi = tk.DoubleVar(value=1.0)
                self._th_pulse_ms = tk.DoubleVar(value=1.0)
                self._th_vbase = tk.DoubleVar(value=0.2)
                self._th_target = tk.DoubleVar(value=1e-5)
                self._th_iters = tk.IntVar(value=12)
                tk.Label(self._excitation_params_frame, text="V low").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self._th_lo, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="V high").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self._th_hi, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Pulse (ms)").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self._th_pulse_ms, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Vbase").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self._th_vbase, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Target |I| (A)").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self._th_target, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Max iters").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self._th_iters, width=10).grid(row=r, column=1, sticky="w"); r+=1
                try:
                    for w in self._dc_widgets:
                        try: w.grid_remove()
                        except Exception: pass
                except Exception:
                    pass
                return
            if sel == "Transient Decay":
                tk.Label(self._excitation_params_frame, text="Pulse once, then sample I(t) at Vread.", fg="grey").grid(row=r, column=0, columnspan=2, sticky="w"); r+=1
                self._tr_pulse_v = tk.DoubleVar(value=0.8)
                self._tr_pulse_ms = tk.DoubleVar(value=1.0)
                self._tr_read_v = tk.DoubleVar(value=0.2)
                self._tr_cap_s = tk.DoubleVar(value=1.0)
                self._tr_dt_s = tk.DoubleVar(value=0.001)
                tk.Label(self._excitation_params_frame, text="Pulse V").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self._tr_pulse_v, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Pulse (ms)").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self._tr_pulse_ms, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Read V").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self._tr_read_v, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Capture (s)").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self._tr_cap_s, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="dt (s)").grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self._tr_dt_s, width=10).grid(row=r, column=1, sticky="w"); r+=1
                try:
                    for w in self._dc_widgets:
                        try: w.grid_remove()
                        except Exception: pass
                except Exception:
                    pass
                return

        self.excitation_menu.bind("<<ComboboxSelected>>", render_excitation_params)
        render_excitation_params()

        self._dc_widgets = []

        # Callback to update labels when source mode changes
        def on_source_mode_change(*args):
            mode = self.source_mode_var.get()
            if mode == "voltage":
                # Voltage source mode: Source V, Measure I
                self._dc_lbl_start.config(text="Start Voltage (V):")
                self._dc_lbl_vhigh.config(text="Voltage High (V):")
                self._dc_lbl_vlow.config(text="Voltage Low (V, optional):")
                self._dc_lbl_step.config(text="Step Size (V):")
                self._dc_lbl_icc.config(text="Icc (A):")
            elif mode == "current":
                # Current source mode: Source I, Measure V
                self._dc_lbl_start.config(text="Start Current (A):")
                self._dc_lbl_vhigh.config(text="Current High (A):")
                self._dc_lbl_vlow.config(text="Current Low (A, optional):")
                self._dc_lbl_step.config(text="Step Size (A):")
                self._dc_lbl_icc.config(text="Vcc (V):")
        
        self.source_mode_var.trace_add("write", on_source_mode_change)

        self._dc_lbl_start = tk.Label(frame, text="Start Voltage (V):")
        self._dc_lbl_start.grid(row=3, column=0, sticky="w")
        self.start_voltage = tk.DoubleVar(value=0)
        self._dc_ent_start = tk.Entry(frame, textvariable=self.start_voltage)
        self._dc_ent_start.grid(row=3, column=1)
        self._dc_widgets.extend([self._dc_lbl_start, self._dc_ent_start])

        self._dc_lbl_vhigh = tk.Label(frame, text="Voltage High (V):")
        self._dc_lbl_vhigh.grid(row=4, column=0, sticky="w")
        self.voltage_high = tk.DoubleVar(value=1)
        self._dc_ent_vhigh = tk.Entry(frame, textvariable=self.voltage_high)
        self._dc_ent_vhigh.grid(row=4, column=1)
        self._dc_widgets.extend([self._dc_lbl_vhigh, self._dc_ent_vhigh])

        # Optional asymmetric negative voltage limit
        self._dc_lbl_vlow = tk.Label(frame, text="Voltage Low (V, optional):")
        self._dc_lbl_vlow.grid(row=5, column=0, sticky="w")
        self.voltage_low_str = tk.StringVar(value="")
        self._dc_ent_vlow = tk.Entry(frame, textvariable=self.voltage_low_str)
        self._dc_ent_vlow.grid(row=5, column=1)
        self._dc_widgets.extend([self._dc_lbl_vlow, self._dc_ent_vlow])

        self._dc_lbl_step = tk.Label(frame, text="Step Size (V):")
        self._dc_lbl_step.grid(row=6, column=0, sticky="w")
        self.step_size = tk.DoubleVar(value=0.1)
        self._dc_ent_step = tk.Entry(frame, textvariable=self.step_size)
        self._dc_ent_step.grid(row=6, column=1)
        self._dc_widgets.extend([self._dc_lbl_step, self._dc_ent_step])

        self._dc_lbl_dwell = tk.Label(frame, text="Step Delay (S):")
        self._dc_lbl_dwell.grid(row=7, column=0, sticky="w")
        self.step_delay = tk.DoubleVar(value=0.05)
        self._dc_ent_dwell = tk.Entry(frame, textvariable=self.step_delay)
        self._dc_ent_dwell.grid(row=7, column=1)
        self._dc_widgets.extend([self._dc_lbl_dwell, self._dc_ent_dwell])

        self._dc_lbl_sweeps = tk.Label(frame, text="# Sweeps:")
        self._dc_lbl_sweeps.grid(row=8, column=0, sticky="w")
        self.sweeps = tk.DoubleVar(value=1)
        self._dc_ent_sweeps = tk.Entry(frame, textvariable=self.sweeps)
        self._dc_ent_sweeps.grid(row=8, column=1)
        self._dc_widgets.extend([self._dc_lbl_sweeps, self._dc_ent_sweeps])

        self._dc_lbl_icc = tk.Label(frame, text="Icc:")
        self._dc_lbl_icc.grid(row=9, column=0, sticky="w")
        self.icc = tk.DoubleVar(value=0.1)
        self._dc_ent_icc = tk.Entry(frame, textvariable=self.icc)
        self._dc_ent_icc.grid(row=9, column=1)
        self._dc_widgets.extend([self._dc_lbl_icc, self._dc_ent_icc])

        # Sweep Type variable already declared above; controls will be shown in DC Triangle UI

        # LED Controls mini title
        tk.Label(frame, text="LED Controls", font=("Arial", 9, "bold")).grid(row=23, column=0, columnspan=2, sticky="w",
                                                                             pady=(10, 2))

        # LED Toggle Button
        tk.Label(frame, text="LED Status:").grid(row=24, column=0, sticky="w")
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
        self.led_button.grid(row=24, column=1, sticky="w")

        tk.Label(frame, text="Led_Power (0-1):").grid(row=25, column=0, sticky="w")
        self.led_power = tk.DoubleVar(value=1)
        tk.Entry(frame, textvariable=self.led_power).grid(row=25, column=1)

        tk.Label(frame, text="Sequence: (01010)").grid(row=26, column=0, sticky="w")
        self.sequence = tk.StringVar()
        tk.Entry(frame, textvariable=self.sequence).grid(row=26, column=1)

        # Other Controls mini title
        tk.Label(frame, text="Other", font=("Arial", 9, "bold")).grid(row=27, column=0, columnspan=2, sticky="w",
                                                                      pady=(10, 2))

        tk.Label(frame, text="Pause at end?:").grid(row=28, column=0, sticky="w")
        self.pause = tk.DoubleVar(value=0.0)
        tk.Entry(frame, textvariable=self.pause).grid(row=28, column=1)

        def start_thread():
            self.measurement_thread = threading.Thread(target=self.start_measurement)
            self.measurement_thread.daemon = True
            self.measurement_thread.start()

        self.measure_button = tk.Button(frame, text="Start Measurement", command=start_thread)
        self.measure_button.grid(row=29, column=0, columnspan=1, pady=5)

        # stop button
        self.adaptive_button = tk.Button(frame, text="Stop Measurement!", command=self.set_measurment_flag_true)
        self.adaptive_button.grid(row=29, column=1, columnspan=1, pady=10)

        # Note: Detailed sweep controls moved to popup editor; only Pause remains in main panel

    def start_automated_tests(self) -> None:
        if self.tests_running:
            messagebox.showinfo("Tests", "Automated tests already running.")
            return
        # Connected flag is set when using IVControllerManager; don't require a raw Keithley2401 instance
        if not self.connected or self.keithley is None:
            messagebox.showerror("Instrument", "Keithley not connected.")
            return
        self.tests_running = True
        self.abort_tests_flag = False
        self.test_log_queue.put("Starting automated tests...")
        self._send_bot_message("Automated tests started")
        self._pump_test_logs()
        threading.Thread(target=self._tests_worker, daemon=True).start()

    def stop_automated_tests(self) -> None:
        if self.tests_running:
            self.abort_tests_flag = True
            self.test_log_queue.put("Abort requested.")

    def _route_current_device(self) -> None:
        # use Sample GUI to route relays if available
        try:
            self.sample_gui.change_relays()
        except Exception:
            pass

    def _tests_worker(self) -> None:
        try:
            inst = self.keithley
            driver = MeasurementDriver(inst, abort_flag=lambda: self.abort_tests_flag)
            runner = TestRunner(driver, load_thresholds())

            results_dir = Path(__file__).resolve().parent / "results"
            results_dir.mkdir(exist_ok=True)

            # Current device only or all devices from Sample GUI
            devices = [self.sample_gui.device_list[self.current_index]] if self.single_device_flag else list(self.sample_gui.get_selected_devices())
            for device in devices:
                if self.abort_tests_flag:
                    break
                self.test_log_queue.put(f"Routing to device {device}...")
                self.master.after(0, self._route_current_device)
                if self.abort_tests_flag:
                    break
                self.test_log_queue.put(f"Testing {device}...")
                self._send_bot_message(f"Testing {device}...")

                # Live plotting callback if enabled
                on_sample = None
                if self.live_plot_enabled.get():
                    try:
                        on_sample = getattr(self, 'plotter', None)
                        if on_sample and hasattr(self, 'thread_safe'):
                            on_sample = self.thread_safe.callback_sink(device)
                        else:
                            on_sample = None
                    except Exception:
                        on_sample = None

                if on_sample is not None:
                    orig_dc = driver.dc_hold
                    orig_sw = driver.triangle_sweep
                    def dc_cb(v, d, hz, comp):
                        return orig_dc(v, d, hz, comp, on_sample=on_sample)
                    def sw_cb(vmin, vmax, step, dwell, cycles, comp):
                        return orig_sw(vmin, vmax, step, dwell, cycles, comp, on_sample=on_sample)
                    driver.dc_hold = dc_cb  # type: ignore
                    driver.triangle_sweep = sw_cb  # type: ignore

                outcome, artifacts = runner.run_device(device)

                # Save summary, best IV, and per-run log
                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                try:
                    with (results_dir / f"{device}_summary_{ts}.json").open('w', encoding='utf-8') as f:
                        import json as _json
                        _json.dump(outcome.__dict__, f, indent=2)
                except Exception as e:
                    self.test_log_queue.put(f"Failed summary save for {device}: {e}")
                try:
                    best = artifacts.get("best_iv")
                    if best:
                        with (results_dir / f"{device}_best_iv_{ts}-automated.csv").open('w', encoding='utf-8') as f:
                            f.write("V,I,t\n")
                            for v, i, t in zip(best.voltage, best.current, best.timestamps):
                                f.write(f"{v},{i},{t}\n")
                except Exception as e:
                    self.test_log_queue.put(f"Failed IV save for {device}: {e}")

                # Persist per-run log in a subfolder per device
                try:
                    device_dir = results_dir / f"{device}_logs"
                    device_dir.mkdir(exist_ok=True)
                    log_path = device_dir / f"log_{ts}.txt"
                    lines = artifacts.get("log_lines") or []
                    with log_path.open('w', encoding='utf-8') as f:
                        f.write("\n".join(lines))
                except Exception as e:
                    self.test_log_queue.put(f"Failed log save for {device}: {e}")

                # Append to summary CSV
                try:
                    import csv
                    sp = results_dir / "summary.csv"
                    write_header = not sp.exists()
                    with sp.open('a', newline='', encoding='utf-8') as f:
                        w = csv.writer(f)
                        if write_header:
                            w.writerow(["device_id","status","formed","probe_current_a","hyst_area",
                                        "endurance_on_off","retention_alpha","timestamp"])
                        w.writerow([
                            device,
                            "WORKING" if outcome.is_working else "NON-WORKING",
                            outcome.formed,
                            f"{outcome.probe_current_a:.3e}",
                            f"{(outcome.hyst_area or 0):.3e}",
                            f"{(outcome.endurance_on_off or 0):.3f}",
                            f"{(outcome.retention_alpha or 0):.3f}",
                            datetime.now().isoformat(timespec='seconds')
                        ])
                except Exception as e:
                    self.test_log_queue.put(f"Failed to update summary: {e}")

                status = "WORKING" if outcome.is_working else "NON-WORKING"
                formed = " (formed)" if outcome.formed else ""
                extras = []
                if outcome.hyst_area is not None:
                    extras.append(f"hyst={outcome.hyst_area:.2e}")
                if outcome.endurance_on_off is not None:
                    extras.append(f"on/off~{outcome.endurance_on_off:.2f}")
                if outcome.retention_alpha is not None:
                    extras.append(f"ret~{outcome.retention_alpha:.2f}")
                summary_line = f"{device}: {status}{formed}, I_probe={outcome.probe_current_a:.2e} A" \
                               + (", " + ", ".join(extras) if extras else "")
                self.test_log_queue.put(summary_line)
                self._send_bot_message(summary_line)
        except Exception as e:
            self.test_log_queue.put(f"Automated tests error: {e}")
        finally:
            self.tests_running = False
            self._send_bot_message("Automated tests finished")

    def set_measurment_flag_true(self) -> None:
        self.stop_measurement_flag = True
    
    def create_custom_measurement_section(self,parent: tk.Misc) -> None:
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

        # Pause button (kept in main UI, positioned under Run Custom)
        def toggle_pause():
            self.pause_requested = not self.pause_requested
            self.pause_button_custom.config(text=("Resume" if self.pause_requested else "Pause"))
        self.pause_button_custom = tk.Button(frame, text="Pause", width=10, command=toggle_pause)
        self.pause_button_custom.grid(row=2, column=0, padx=5, pady=2, sticky="w")

        # Open sweep editor popup (under Run Custom)
        tk.Button(frame, text="Edit Sweeps", command=self.open_sweep_editor_popup).grid(row=2, column=1, padx=5, pady=2, sticky="w")

    def open_sweep_editor_popup(self) -> None:
        try:
            selected = self.custom_measurement_var.get()
            plan = self.custom_sweeps.get(selected, {}).get('sweeps', {})
        except Exception:
            plan = {}

        win = tk.Toplevel(self.master)
        win.title("Edit Sweeps")
        win.geometry("500x500")
        try:
            win.grid_rowconfigure(1, weight=1)
            win.grid_columnconfigure(0, weight=1)
        except Exception:
            pass

        # Header
        header = tk.Frame(win)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=6, pady=4)
        tk.Label(header, text="Sweep", width=8).grid(row=0, column=0)
        tk.Label(header, text="stop_v", width=10).grid(row=0, column=1)
        tk.Label(header, text="Skip", width=6).grid(row=0, column=2)

        # Body with rows (grid-based layout)
        rows = tk.Frame(win)
        rows.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=6, pady=4)
        try:
            rows.grid_rowconfigure(0, weight=1)
            rows.grid_columnconfigure(0, weight=1)
        except Exception:
            pass

        # Scrollable area if many sweeps
        canvas = tk.Canvas(rows)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(rows, orient="vertical", command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        inner = tk.Frame(canvas)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        self._sweep_editor_vars = {}
        for idx, (key, params) in enumerate(sorted(plan.items(), key=lambda kv: int(kv[0]))):
            key_str = str(key)
            stopv_val = params.get('stop_v', '')
            tk.Label(inner, text=key_str, width=8).grid(row=idx, column=0, padx=2, pady=2)
            v = tk.StringVar(value=str(stopv_val))
            e = ttk.Entry(inner, textvariable=v, width=10)
            e.grid(row=idx, column=1, padx=2, pady=2)
            skip_var = tk.IntVar(value=1 if params.get('__skip__') else 0)
            cb = ttk.Checkbutton(inner, variable=skip_var)
            cb.grid(row=idx, column=2, padx=2, pady=2)
            self._sweep_editor_vars[key_str] = {'stop_v': v, 'skip': skip_var}

        # Footer with actions
        footer = tk.Frame(win)
        footer.grid(row=2, column=0, columnspan=2, sticky="ew", padx=6, pady=6)

        def apply_changes():
            edits = {}
            for key_str, vars_dict in self._sweep_editor_vars.items():
                entry_val = vars_dict['stop_v'].get().strip()
                skip_flag = bool(vars_dict['skip'].get())
                entry_num = None
                if entry_val != "":
                    try:
                        entry_num = float(entry_val)
                    except Exception:
                        entry_num = None
                edits[key_str] = {}
                if entry_num is not None:
                    edits[key_str]['stop_v'] = entry_num
                if skip_flag:
                    edits[key_str]['skip'] = True
            self.sweep_runtime_overrides = edits
            win.destroy()

        ttk.Button(footer, text="Apply", command=apply_changes).grid(row=0, column=1, sticky="e")

    def signal_messaging(self,parent: tk.Misc) -> None:
        """Build Telegram messaging controls (toggle, user dropdown, tokens)."""
        # Keep a handle to the frame so we can manage stacking/visibility
        self.signal_frame = tk.LabelFrame(parent, text="Signal_Messaging", padx=5, pady=5)
        frame = self.signal_frame
        frame.grid(row=7, column=0, rowspan=2, padx=10, pady=5, sticky="nsew")

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
        # Ensure the bot section isn't hidden behind other widgets
        try:
            frame.lift()
        except Exception:
            pass

    def create_status_box(self,parent: tk.Misc) -> None:
        """Create a single-line status label for connection/measurements."""
        frame = tk.LabelFrame(parent, text="Status", padx=5, pady=5)
        frame.grid(row=3, column=0, padx=10, pady=5, sticky="ew")

        self.status_box = tk.Label(frame, text="Status: Not Connected", relief=tk.SUNKEN, anchor="w", width=20)
        self.status_box.pack(fill=tk.X)


    def temp_measurments_itc4(self, parent: tk.Misc) -> None:
        """Create a simple panel to send a setpoint to the ITC4 controller."""
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

    def create_controller_selection(self,parent: tk.Misc) -> None:
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

    def reconnect_temperature_controller(self) -> None:
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

    def reconnect_Kieithley_controller(self) -> None:
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
    def update_controller_status(self) -> None:
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

    def sequential_measurments(self,parent: tk.Misc) -> None:
        """Build the UI for sequential measurement routines (Iv/Avg measure)."""

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

    def sequential_measure(self) -> None:
        """Run a sequence of measurements across devices.

        This method supports two sequence modes selectable from the GUI:
        - "Iv Sweep": runs repeated IV sweeps for each device
        - "Single Avg Measure": measures an averaged current at a fixed voltage

        The method runs in a background thread (started by the UI) and updates
        GUI widgets and plots via thread-safe callbacks. It honors
        `self.stop_measurement_flag` for cooperative cancellation and
        `self.single_device_flag` to limit operation to the selected device.
        """

        # Enter measurement mode and ensure GUI focus
        self._reset_plots_for_new_run()
        self.measuring = True
        self.stop_measurement_flag = False
        self.bring_to_top()  # make sure the window is visible
        self.check_for_sample_name()  # ensure sample name is set (or prompt)

        print("Running sequential measurement:")

        # Branch by sequence type selected in the GUI
        if self.Sequential_measurement_var.get() == "Iv Sweep":
            count_pass = 1

            for i in range(int(self.sequential_number_of_sweeps.get())):
                print("Starting pass #",i + 1)
                voltage = int(self.sq_voltage.get())
                voltage_arr = get_voltage_range(0, voltage, 0.05, "FS", neg_stop_v=None)

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
                    # Use centralized service for a default FS sweep
                    icc_val = float(self.icc.get())
                    def _on_point(v, i, t_s):
                        self.v_arr_disp.append(v)
                        self.c_arr_disp.append(i)
                        self.t_arr_disp.append(t_s)
                    v_arr, c_arr, timestamps = self.measurement_service.run_iv_sweep(
                        keithley=self.keithley,
                        icc=icc_val,
                        sweeps=1,
                        step_delay=0.05,
                        voltage_range=voltage_arr,
                        psu=getattr(self, 'psu', None),
                        led=False,
                        power=1.0,
                        sequence=None,
                        pause_s=0.0,
                        smu_type=getattr(self, 'SMU_type', 'Keithley 2401'),
                        should_stop=lambda: getattr(self, 'stop_measurement_flag', False),
                        on_point=_on_point,
                    )
                    data = np.column_stack((v_arr, c_arr, timestamps))

                    # save the current data in a folder called multiplexer and the name of the sample

                    # creates save directory with the selected measurement device name letter and number
                    # For multiplexer sweeps, use special subfolder
                    base_path = self._get_base_save_path()
                    if base_path:
                        # Custom path: {custom_base}/Multiplexer_IV_sweep/{sample}/{device_number}
                        save_dir = os.path.join(str(base_path), "Multiplexer_IV_sweep", 
                                               self.sample_name_var.get(), str(j+1))
                    else:
                        # Default path: Data_save_loc/Multiplexer_IV_sweep/{sample}/{device_number}
                        save_dir = f"Data_save_loc\\Multiplexer_IV_sweep\\{self.sample_name_var.get()}" \
                                   f"\\{j+1}"
                    # make directory if dost exist.
                    if not os.path.exists(save_dir):
                        os.makedirs(save_dir)
                    sweeps=1
                    name = f"{count_pass}-FS-{voltage}v-{0.05}sv-{0.05}sd-Py-Sq-{sweeps}"
                    file_path = f"{save_dir}\\{name}.txt"


                    np.savetxt(file_path, data, fmt="%0.3E\t%0.3E\t%0.3E", header="Voltage Current Time", comments="")

                    # change device only if measuring all devices
                    if not self.single_device_flag:
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

            device_count = 1 if self.single_device_flag else len(self.device_list)
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

                    # when changing device, only do so if measuring all devices
                    if not self.single_device_flag:
                        # ensure voltage is 0 before switching
                        self.keithley.set_voltage(0,self.icc.get())
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


    def measure_average_current(self, voltage: float, duration: float) -> Tuple[float, float, float]:
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

    def record_temperature(self) -> float:
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

    def log_terminal(self, message: str) -> None:
        """Log message to terminal output (if you don't already have this)"""
        if hasattr(self, 'terminal_output'):
            self.terminal_output.config(state=tk.NORMAL)
            self.terminal_output.insert(tk.END, message + "\n")
            self.terminal_output.config(state=tk.DISABLED)
            self.terminal_output.see(tk.END)
        else:
            print(message)

    def _finalize_output(self) -> None:
        """Set SMU_AND_PMU to 0 V and disable output (best-effort)."""
        try:
            self.keithley.set_voltage(0, self.icc.get())
        except Exception:
            pass
        try:
            self.keithley.enable_output(False)
        except Exception:
            pass

    # Old measure method removed; logic centralized in MeasurementService

    def run_custom_measurement(self) -> None:
        """Execute a custom measurement plan from the loaded JSON file.

        The JSON (loaded into `self.custom_sweeps`) contains an ordered set of
        named sweeps. For each sweep the method configures instrument options
        (LED, PSU, pulse parameters, etc.) and delegates the actual work to
        `MeasurementService`. Per-sweep overrides made at runtime via the
        sweep editor popup are applied on-the-fly.

        The GUI's `stop_measurement_flag` is checked frequently to allow
        cooperative abort. Results are saved per-sweep in `Data_save_loc` and
        basic summary plots are produced.
        """


        if not self.connected:
            messagebox.showwarning("Warning", "Not connected to Keithley!")
            return

        # Reset graphs/buffers between runs
        self._reset_plots_for_new_run()

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
        # Reset any prior sweep edits from the popup for a fresh run
        try:
            self.sweep_runtime_overrides = {}
        except Exception:
            pass
        print(f"Running custom measurement: {selected_measurement}")

        print(self.get_messaged_var)
        # use the bot to send a message
        a = self.get_messaged_var.get()
        #b = self.get_messaged_switch.get()
        #print(a)
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
                # Initial merge disabled; we now apply live edits per-sweep inside the loop
                code_name = self.custom_sweeps[selected_measurement].get("code_name", "unknown")

                # checks psu connection only if any sweep explicitly requires LED
                def _is_truthy(val) -> bool:
                    try:
                        # numeric truthiness: non-zero => True
                        if isinstance(val, (int, float)):
                            return float(val) != 0.0
                    except Exception:
                        pass
                    if isinstance(val, str):
                        return val.strip().lower() in {"1", "true", "on", "yes", "y"}
                    return bool(val)

                any_led_required = any(_is_truthy(params.get("LED_ON", 0)) for _k, params in sweeps.items())
                if any_led_required and not self.psu_connected:
                    print("LED required by at least one sweep; connecting PSU")
                    messagebox.showwarning("Warning", "Not connected to PSU! Connecting now for LED use...")
                    time.sleep(1)
                    self.connect_keithley_psu()

                for key, params in sweeps.items():
                    # Apply live edits for this sweep (skip/stop_v) so mid-run changes take effect
                    try:
                        live_edits = getattr(self, 'sweep_runtime_overrides', {}) or {}
                        per = live_edits.get(str(key), {})
                        if per.get('skip'):
                            continue
                        if 'stop_v' in per:
                            try:
                                params['stop_v'] = float(per['stop_v'])
                            except Exception:
                                pass
                    except Exception:
                        pass
                    if self.stop_measurement_flag:  # Check if stop was pressed
                        print("Measurement interrupted!")
                        break  # Exit measurement loop immediately

                    self.measurment_number = key
                    print("Working on device -", device, ": Measurement -", key)

                    # Runtime: pause between sweeps if requested
                    while getattr(self, 'pause_requested', False) and not self.stop_measurement_flag:
                        time.sleep(0.1)

                    # Runtime: skip forward to a specific sweep number, if set
                    skip_to = getattr(self, 'skip_to_sweep_target', None)
                    if skip_to is not None:
                        try:
                            current_idx = int(str(key))
                            if current_idx < int(skip_to):
                                continue
                            else:
                                # Clear the target once reached
                                self.skip_to_sweep_target = None
                        except Exception:
                            pass

                    # default values
                    start_v = params.get("start_v", 0)
                    stop_v = params.get("stop_v", 1)
                    # Runtime: override stop_v for a configured sweep range
                    override = getattr(self, 'override_range', None)
                    if override is not None:
                        try:
                            cur_idx = int(str(key))
                            if override["start"] <= cur_idx <= override["end"]:
                                stop_v = float(override["stop_v"])
                        except Exception:
                            pass
                    sweeps = params.get("sweeps", 1)
                    step_v = params.get("step_v", 0.1)
                    step_delay = params.get("step_delay", 0.05)
                    sweep_type = params.get("Sweep_type", "FS")
                    pause = params.get('pause', 0)

                    # LED control
                    led = _is_truthy(params.get("LED_ON", 0))
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

                    # Read measurement_type (new unified field)
                    measurement_type = str(params.get("measurement_type", "IV"))
                    
                    # Backward compatibility: check old "mode" and "excitation" fields
                    if "mode" in params:
                        measurement_type = params["mode"]  # Endurance, Retention
                    elif "excitation" in params:
                        # Map old excitation names to measurement_type
                        excitation_map = {
                            "DC Triangle IV": "IV",
                            "SMU Pulsed IV": "PulsedIV",
                            "SMU Fast Pulses": "FastPulses",
                            "SMU Fast Hold": "Hold"
                        }
                        measurement_type = excitation_map.get(params["excitation"], "IV")
                    
                    # Read source mode (NEW)
                    source_mode_str = params.get("source_mode", "voltage")
                    from Measurments.source_modes import SourceMode
                    source_mode = SourceMode.CURRENT if source_mode_str == "current" else SourceMode.VOLTAGE
                    
                    # Read compliance per sweep (NEW - optional, defaults to GUI value)
                    icc_val = params.get("icc", None)
                    if icc_val is None:
                        icc_val = float(self.icc.get())  # Use GUI value
                    else:
                        icc_val = float(icc_val)  # Use JSON value
                    
                    # Read metadata/notes (NEW - optional)
                    sweep_notes = params.get("notes", None)
                    if sweep_notes:
                        print(f"Sweep {key} notes: {sweep_notes}")
                    
                    # Read temperature (NEW - OPTIONAL, defaults to OFF)
                    # Temperature control is ONLY activated if temperature_C is explicitly set in JSON
                    if "temperature_C" in params:
                        target_temp = params["temperature_C"]
                        if hasattr(self, 'temp_controller') and self.temp_controller is not None:
                            try:
                                print(f"Setting temperature to {target_temp}°C")
                                self.temp_controller.set_temperature(float(target_temp))
                                
                                # Optional: wait for stabilization (only if specified)
                                stabilization_time = params.get("temp_stabilization_s", 0)
                                if stabilization_time > 0:
                                    print(f"Waiting {stabilization_time}s for temperature stabilization...")
                                    time.sleep(float(stabilization_time))
                            except Exception as e:
                                print(f"Temperature setting failed: {e}")
                                # Continue with measurement even if temp control fails
                        else:
                            print("Warning: temperature_C specified but no temp controller connected")
                    # If "temperature_C" not in params, temperature control is completely skipped

                    # Helpers for SMU_AND_PMU timing defaults
                    def _min_pw_ms() -> float:
                        try:
                            smu_type_loc = getattr(self, 'SMU_type', 'Keithley 2401')
                            return float(self.measurement_service.get_smu_limits(smu_type_loc).get("min_pulse_width_ms", 1.0))
                        except Exception:
                            return 1.0

                    # Route to appropriate measurement based on measurement_type
                    if measurement_type == "IV":
                        # Optional per-sweep negative stop voltage: params override UI field
                        neg_stop_v_param = None
                        try:
                            if 'neg_stop_v' in params:
                                neg_stop_v_param = float(params.get('neg_stop_v'))
                            elif 'Vneg' in params:
                                neg_stop_v_param = float(params.get('Vneg'))
                            else:
                                raw_neg = self.voltage_low_str.get().strip() if hasattr(self, 'voltage_low_str') else ""
                                if raw_neg != "":
                                    neg_stop_v_param = float(raw_neg)
                        except Exception:
                            neg_stop_v_param = None
                        voltage_range = get_voltage_range(start_v, stop_v, step_v, sweep_type, neg_stop_v=neg_stop_v_param)
                        
                        def _on_point(v, i, t_s):
                            self.v_arr_disp.append(v)
                            self.c_arr_disp.append(i)
                            self.t_arr_disp.append(t_s)
                        
                        v_arr, c_arr, timestamps = self.measurement_service.run_iv_sweep(
                            keithley=self.keithley,
                            start_v=start_v,
                            stop_v=stop_v,
                            step_v=step_v,
                            sweeps=sweeps,
                            step_delay=step_delay,
                            sweep_type=sweep_type,
                            icc=icc_val,
                            psu=getattr(self, 'psu', None),
                            led=led,
                            power=power,
                            optical=getattr(self, 'optical', None),
                            sequence=sequence,
                            pause_s=pause,
                            smu_type=getattr(self, 'SMU_type', 'Keithley 2401'),
                            source_mode=source_mode,
                            should_stop=lambda: getattr(self, 'stop_measurement_flag', False),
                            on_point=_on_point
                        )

                    elif measurement_type == "Endurance":
                        set_v = params.get("set_v", 1.5)
                        reset_v = params.get("reset_v", -1.5)
                        pulse_ms = params.get("pulse_ms", 10)
                        cycles = params.get("cycles", 100)
                        read_v = params.get("read_v", 0.2)
                        
                        def _on_point(v, i, t_s):
                            self.v_arr_disp.append(v)
                            self.c_arr_disp.append(i)
                            self.t_arr_disp.append(t_s)
                        
                        v_arr, c_arr, timestamps = self.measurement_service.run_endurance(
                            keithley=self.keithley,
                            set_voltage=set_v,
                            reset_voltage=reset_v,
                            pulse_width_s=pulse_ms/1000,
                            num_cycles=cycles,
                            read_voltage=read_v,
                            icc=icc_val,
                            psu=getattr(self, 'psu', None),
                            led=led,
                            power=power,
                            optical=getattr(self, 'optical', None),
                            smu_type=getattr(self, 'SMU_type', 'Keithley 2401'),
                            should_stop=lambda: getattr(self, 'stop_measurement_flag', False),
                            on_point=_on_point
                        )
                        print("endurance")

                    elif measurement_type == "Retention":
                        set_v = params.get("set_v", 1.5)
                        set_ms = params.get("set_ms", 10)
                        read_v = params.get("read_v", 0.2)
                        times_s = params.get("times_s", [1, 10, 100, 1000])
                        
                        def _on_point(v, i, t_s):
                            self.v_arr_disp.append(v)
                            self.c_arr_disp.append(i)
                            self.t_arr_disp.append(t_s)
                        
                        v_arr, c_arr, timestamps = self.measurement_service.run_retention(
                            keithley=self.keithley,
                            set_voltage=set_v,
                            set_time_s=set_ms/1000,
                            read_voltage=read_v,
                            repeat_delay_s=0.1,
                            number=len(times_s),
                            icc=icc_val,
                            psu=getattr(self, 'psu', None),
                            led=led,
                            optical=getattr(self, 'optical', None),
                            smu_type=getattr(self, 'SMU_type', 'Keithley 2401'),
                            should_stop=lambda: getattr(self, 'stop_measurement_flag', False),
                            on_point=_on_point
                        )
                        print("retention")

                    elif measurement_type == "PulsedIV":
                        # Parameters
                        start_amp = float(params.get("start_v", 0.0))
                        stop_amp = float(params.get("stop_v", 0.2))
                        step_amp = float(params.get("step_v", 0.0)) if params.get("step_v") is not None else None
                        num_steps = int(params.get("num_steps", 0)) or None
                        pulse_ms = float(params.get("pulse_ms", _min_pw_ms()))
                        vbase = float(params.get("vbase", 0.2))
                        inter_step = float(params.get("inter_delay", 0.0))

                        v_arr, c_arr, timestamps = self.measurement_service.run_pulsed_iv_sweep(
                            keithley=self.keithley,
                            start_v=start_amp,
                            stop_v=stop_amp,
                            step_v=step_amp,
                            num_steps=num_steps,
                            pulse_width_ms=max(_min_pw_ms(), pulse_ms),
                            vbase=vbase,
                            inter_step_delay_s=inter_step,
                            icc=icc_val,
                            smu_type=getattr(self, 'SMU_type', 'Keithley 2401'),
                            should_stop=lambda: getattr(self, 'stop_measurement_flag', False),
                            on_point=None,
                            validate_timing=True,
                        )
                        
                    elif measurement_type == "FastPulses":
                        pulse_v = float(params.get("pulse_v", 0.2))
                        pulse_ms = float(params.get("pulse_ms", _min_pw_ms()))
                        num_pulses = int(params.get("num", 10))
                        inter_delay = float(params.get("inter_delay", 0.0))
                        vbase = float(params.get("vbase", 0.2))
                        
                        v_arr, c_arr, timestamps = self.measurement_service.run_pulse_measurement(
                            keithley=self.keithley,
                            pulse_voltage=pulse_v,
                            pulse_width_ms=max(_min_pw_ms(), pulse_ms),
                            num_pulses=max(1, num_pulses),
                            read_voltage=vbase,
                            inter_pulse_delay_s=max(0.0, inter_delay),
                            icc=icc_val,
                            smu_type=getattr(self, 'SMU_type', 'Keithley 2401'),
                            psu=getattr(self, 'psu', None),
                            led=False,
                            power=1.0,
                            optical=getattr(self, 'optical', None),
                            sequence=None,
                            should_stop=lambda: getattr(self, 'stop_measurement_flag', False),
                            on_point=None,
                            validate_timing=True,
                        )
                        
                    elif measurement_type == "Hold":
                        hold_v = float(params.get("hold_v", 0.2))
                        duration = float(params.get("duration_s", 5.0))
                        sample_dt = float(params.get("sample_dt_s", 0.01))
                        
                        v_arr, c_arr, timestamps = self.measurement_service.run_dc_capture(
                            keithley=self.keithley,
                            voltage_v=hold_v,
                            capture_time_s=duration,
                            sample_dt_s=sample_dt,
                            icc=icc_val,
                            on_point=None,
                            should_stop=lambda: getattr(self, 'stop_measurement_flag', False),
                        )
                        
                    else:
                        print(f"Unknown measurement_type: {measurement_type}")
                        continue

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

                    if self.additional_info_var != "":
                        #extra_info = "-" + str(self.additional_info_entry.get())
                        # or
                        extra_info = "-" + self.additional_info_entry.get().strip()
                    else:
                        extra_info = ""

                    name = f"{key}-{sweep_type}-{stop_v}v-{step_v}sv-{step_delay}sd-Py-{code_name}-{sweeps}{extra_info}"
                    file_path = f"{save_dir}\\{name}.txt"

                    if os.path.exists(file_path):
                        print("filepath already exisits")
                        messagebox.showerror("ERROR", "file already exists, you should check before continueing as "
                                                      "this will overwrite")

                    np.savetxt(file_path, data, fmt="%0.3E\t%0.3E\t%0.3E", header="Voltage Current Time", comments="")

                    # show graphs on main display
                    self.graphs_show(v_arr, c_arr, key, stop_v)

                    # Handle inter-sweep delay (NEW - optional)
                    delay_after_sweep = params.get("delay_after_sweep_s", None)
                    if delay_after_sweep is not None:
                        try:
                            delay_time = float(delay_after_sweep)
                            if delay_time > 0:
                                print(f"Waiting {delay_time}s after sweep {key}...")
                                time.sleep(delay_time)
                        except (ValueError, TypeError):
                            print(f"Invalid delay_after_sweep_s value: {delay_after_sweep}")
                    
                    # Default sleep between measurements (if no specific delay set)
                    if delay_after_sweep is None:
                        time.sleep(2)
                try:
                    if hasattr(self, 'optical') and self.optical is not None and bool(led):
                        self.optical.set_enabled(False)
                    elif getattr(self, 'psu_needed', False) and hasattr(self, 'psu'):
                        self.psu.led_off_380()
                except Exception:
                    # Do not skip the rest of the per-device finalization
                    pass

                plot_filename_iv = f"{save_dir}\\All_graphs_IV.png"
                plot_filename_log = f"{save_dir}\\All_graphs_LOG.png"
                self.ax_all_iv.figure.savefig(plot_filename_iv, dpi=400)
                self.ax_all_logiv.figure.savefig(plot_filename_log, dpi=400)
                # Save final sweep plot(s)
                final_iv_path, final_log_path = self._save_final_sweep_plot(save_dir)
                # Create combined BEFORE clearing axes so "All" plots retain data
                try:
                    combined_now = self._save_combined_summary_plot(save_dir)
                    self._last_combined_summary_path = combined_now
                except Exception:
                    self._last_combined_summary_path = None
                self.ax_all_iv.clear()
                self.ax_all_logiv.clear()
                self.keithley.enable_output(False)

                end = time.time()
                print("total time for ", selected_measurement, "=", end - start, " - ")

                self.create_log_file(save_dir, start_time, selected_measurement)

                print(self.single_device_flag,device_count)
                
                if self.single_device_flag:
                    print("Measuring one device only")
                    # Stop iterating further devices by exiting the device loop
                    
                    break
                if not self.single_device_flag:
                    self.sample_gui.next_device()
                    time.sleep(0.1)
                    self.sample_gui.change_relays()
                    print("Switching Device")


            # Always mark measurement complete in GUI
            self.measuring = False
            self.status_box.config(text="Measurement Complete")
            if self._bot_enabled():
                # Offload interactive flow to background thread so GUI is not blocked
                try:
                    import threading
                    combined = getattr(self, '_last_combined_summary_path', None)
                    threading.Thread(target=self._post_measurement_options_worker,
                                     args=(save_dir, combined),
                                     daemon=True).start()
                except Exception:
                    # Fallback to simple message
                    self._send_bot_message("Measurements finished")
            else:
                # Only show blocking popup when bot is disabled
                messagebox.showinfo("Complete", "Measurements finished.")
        else:
            print("Selected measurement not found in JSON file.")

    def _show_message_async(self, kind: str, *args: Any, **kwargs: Any) -> None:
        try:
            self.master.after(0, lambda: getattr(messagebox, kind)(*args, **kwargs))
        except Exception:
            pass

    def _safe_get_float(self, var: Any, name: str, default: Optional[float] = None) -> Optional[float]:
        try:
            return float(var.get())
        except Exception:
            if default is not None:
                try:
                    return float(default)
                except Exception:
                    return None
            self._show_message_async("showerror", "Invalid input", f"{name} is empty or invalid.")
            return None

    def start_measurement(self) -> None:
        """Start single measurementt on the device! """

        if not self.connected:
            self._show_message_async("showwarning", "Warning", "Not connected to Keithley!")
            return
        # Reset graphs/buffers between runs
        self._reset_plots_for_new_run()
        self.measuring = True

        # Branch by excitation mode if available
        try:
            excitation = self.excitation_var.get()
        except Exception:
            excitation = "DC Triangle IV"

        # Helper: build save directory per-device
        def _ensure_save_dir() -> str:
            save_dir = self._get_save_directory(self.sample_name_var.get(), 
                                               self.final_device_letter, 
                                               self.final_device_number)
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)
            return save_dir

        # Helper: SMU_AND_PMU timing defaults
        def _min_pulse_width_ms() -> float:
            try:
                smu_type = getattr(self, 'SMU_type', 'Keithley 2401')
                limits = self.measurement_service.get_smu_limits(smu_type)
                return float(limits.get("min_pulse_width_ms", 1.0))
            except Exception:
                return 1.0
        
        self.stop_measurement_flag = False
        # Device routing context
        if self.current_device in self.device_list:
            start_index = self.device_list.index(self.current_device)
        else:
            start_index = 0
        device_count = 1 if self.single_device_flag else len(self.device_list)

        if excitation == "SMU_AND_PMU Pulsed IV <1.5v":
            # One device (or iterate) amplitude-sweep pulsed IV
            for i in range(device_count):
                device = self.device_list[(start_index + i) % device_count]
                if self.stop_measurement_flag:
                    break
                self.status_box.config(text=f"Measuring {device} (SMU_AND_PMU Pulsed IV <1.5v)...")
                self.master.update()

                # Pull parameters
                start_v = float(self.ex_piv_start.get())
                stop_v = float(self.ex_piv_stop.get())
                step_v = float(self.ex_piv_step.get()) if self.ex_piv_step.get() != 0 else None
                nsteps = int(self.ex_piv_nsteps.get()) if int(self.ex_piv_nsteps.get() or 0) > 0 else None
                width_ms = float(self.ex_piv_width_ms.get())
                width_ms = max(_min_pulse_width_ms(), width_ms)
                vbase = float(self.ex_piv_vbase.get())
                inter_step = float(self.ex_piv_inter_delay.get())
                icc_val = float(self.icc.get())
                smu_type = getattr(self, 'SMU_type', 'Keithley 2401')

                # Prepare fixed 20 V range for higher voltage measurements
                try:
                    self.keithley.prepare_for_pulses(Icc=icc_val, v_range=20.0, ovp=22.0, use_remote_sense=False, autozero_off=True)
                except Exception:
                    pass
                try:
                    v_out, i_out, t_out = self.measurement_service.run_pulsed_iv_sweep(
                        keithley=self.keithley,
                        start_v=start_v,
                        stop_v=stop_v,
                        step_v=step_v,
                        num_steps=nsteps,
                        pulse_width_ms=width_ms,
                        vbase=vbase,
                        inter_step_delay_s=inter_step,
                        icc=icc_val,
                        smu_type=smu_type,
                        should_stop=lambda: getattr(self, 'stop_measurement_flag', False),
                        on_point=None,
                        validate_timing=True,
                        manage_session=False,
                    )
                finally:
                    try:
                        self.keithley.finish_pulses(Icc=icc_val, restore_autozero=True)
                    except Exception:
                        pass

                # Plot as IV (amplitude vs read current)
                try:
                    self.graphs_show(v_out, i_out, "PULSED_IV", stop_v)
                except Exception:
                    pass

                # Save
                save_dir = _ensure_save_dir()
                key = find_largest_number_in_folder(save_dir)
                save_key = 0 if key is None else key + 1
                name = f"{save_key}-PULSED_IV_LT1p5-{stop_v}v-{width_ms}ms-Py"
                file_path = f"{save_dir}\\{name}.txt"
                try:
                    data = np.column_stack((v_out, i_out, t_out))
                    np.savetxt(file_path, data, fmt="%0.3E\t%0.3E\t%0.3E", header="Amplitude(V) Current(A) Time(s)", comments="")
                except Exception:
                    pass

                if not self.single_device_flag:
                    self.sample_gui.next_device(); time.sleep(0.1); self.sample_gui.change_relays(); time.sleep(0.1)
            self._finalize_output()
            self.measuring = False
            self.status_box.config(text="Measurement Complete")
            show_popup = not self._bot_enabled()
            if show_popup:
                messagebox.showinfo("Complete", "Measurements finished.")
            return

        if excitation == "SMU_AND_PMU Pulsed IV >1.5v":
            for i in range(device_count):
                device = self.device_list[(start_index + i) % device_count]
                if self.stop_measurement_flag:
                    break
                self.status_box.config(text=f"Measuring {device} (SMU_AND_PMU Pulsed IV >1.5v)...")
                self.master.update()

                start_v = float(self.ex_piv_start.get())
                stop_v = float(self.ex_piv_stop.get())
                step_v = float(self.ex_piv_step.get()) if self.ex_piv_step.get() != 0 else None
                nsteps = int(self.ex_piv_nsteps.get()) if int(self.ex_piv_nsteps.get() or 0) > 0 else None
                width_ms = max(_min_pulse_width_ms(), float(self.ex_piv_width_ms.get()))
                vbase = float(self.ex_piv_vbase.get())
                inter_step = float(self.ex_piv_inter_delay.get())
                icc_val = float(self.icc.get())
                smu_type = getattr(self, 'SMU_type', 'Keithley 2401')

                # Prepare fixed 20 V range for >1.5 V
                try:
                    self.keithley.prepare_for_pulses(Icc=icc_val, v_range=20.0, ovp=22.0, use_remote_sense=False, autozero_off=True)
                except Exception:
                    pass
                try:
                    v_out, i_out, t_out = self.measurement_service.run_pulsed_iv_sweep(
                        keithley=self.keithley,
                        start_v=start_v,
                        stop_v=stop_v,
                        step_v=step_v,
                        num_steps=nsteps,
                        pulse_width_ms=width_ms,
                        vbase=vbase,
                        inter_step_delay_s=inter_step,
                        icc=icc_val,
                        smu_type=smu_type,
                        should_stop=lambda: getattr(self, 'stop_measurement_flag', False),
                        on_point=None,
                        validate_timing=True,
                        manage_session=False,
                )
                finally:
                    try:
                        self.keithley.finish_pulses(Icc=icc_val, restore_autozero=True)
                    except Exception:
                        pass

                try:
                    self.graphs_show(v_out, i_out, "PULSED_IV_GT1p5", stop_v)
                except Exception:
                    pass

                if not self.single_device_flag:
                    self.sample_gui.next_device(); time.sleep(0.1); self.sample_gui.change_relays(); time.sleep(0.1)
            self._finalize_output()
            self.measuring = False
            self.status_box.config(text="Measurement Complete")
            if not self._bot_enabled():
                messagebox.showinfo("Complete", "Measurements finished.")
            return

        if excitation == "SMU_AND_PMU Pulsed IV (fixed 20V)":
            for i in range(device_count):
                device = self.device_list[(start_index + i) % device_count]
                if self.stop_measurement_flag:
                    break
                self.status_box.config(text=f"Measuring {device} (SMU_AND_PMU Pulsed IV - fixed 20V)...")
                self.master.update()

                start_v = float(self.ex_piv_start.get())
                stop_v = float(self.ex_piv_stop.get())
                step_v = float(self.ex_piv_step.get()) if self.ex_piv_step.get() != 0 else None
                nsteps = int(self.ex_piv_nsteps.get()) if int(self.ex_piv_nsteps.get() or 0) > 0 else None
                width_ms = max(_min_pulse_width_ms(), float(self.ex_piv_width_ms.get()))
                vbase = float(self.ex_piv_vbase.get())
                inter_step = float(self.ex_piv_inter_delay.get())
                icc_val = float(self.icc.get())
                smu_type = getattr(self, 'SMU_type', 'Keithley 2401')

                # One-shot prep (fixed range, OVP, sense, autozero)
                try:
                    self.keithley.prepare_for_pulses(Icc=icc_val, v_range=20.0, ovp=21.0,
                                                     use_remote_sense=False, autozero_off=True)
                except Exception:
                    pass

                v_out, i_out, t_out, dbg = self.measurement_service.run_pulsed_iv_sweep_debug(
                    keithley=self.keithley,
                    start_v=start_v,
                    stop_v=stop_v,
                    step_v=step_v,
                    num_steps=nsteps,
                    pulse_width_ms=width_ms,
                    vbase=vbase,
                    inter_step_delay_s=inter_step,
                    icc=icc_val,
                    smu_type=smu_type,
                    should_stop=lambda: getattr(self, 'stop_measurement_flag', False),
                    on_point=None,
                    validate_timing=True,
                )

                try:
                    self.keithley.finish_pulses(Icc=icc_val, restore_autozero=True)
                except Exception:
                    pass

                try:
                    self.graphs_show(v_out, i_out, "PULSED_IV_FIXED", stop_v)
                except Exception:
                    pass

                save_dir = _ensure_save_dir()
                key = find_largest_number_in_folder(save_dir)
                save_key = 0 if key is None else key + 1
                name = f"{save_key}-PULSED_IV_FIXED20-{stop_v}v-{width_ms}ms-Py"
                file_path = f"{save_dir}\\{name}.txt"
                dbg_path = f"{save_dir}\\{name}_debug.json"
                try:
                    data = np.column_stack((v_out, i_out, t_out))
                    np.savetxt(file_path, data, fmt="%0.3E\t%0.3E\t%0.3E", header="Amplitude(V) Current(A) Time(s)", comments="")
                except Exception:
                    pass
                try:
                    import json as _json
                    with open(dbg_path, 'w', encoding='utf-8') as f:
                        _json.dump(dbg, f, indent=2)
                except Exception:
                    pass

                if not self.single_device_flag:
                    self.sample_gui.next_device(); time.sleep(0.1); self.sample_gui.change_relays(); time.sleep(0.1)
            self._finalize_output()
            self.measuring = False
            self.status_box.config(text="Measurement Complete")
            if not self._bot_enabled():
                messagebox.showinfo("Complete", "Measurements finished.")
            return

        if excitation == "SMU_AND_PMU Fast Pulses":
            for i in range(device_count):
                device = self.device_list[(start_index + i) % device_count]
                if self.stop_measurement_flag:
                    break
                self.status_box.config(text=f"Measuring {device} (SMU_AND_PMU Fast Pulses)...")
                self.master.update()

                pulse_v = float(self.ex_fp_voltage.get())
                width_ms = max(_min_pulse_width_ms(), float(self.ex_fp_width_ms.get()))
                num = max(1, int(self.ex_fp_num.get()))
                inter = 0.0 if bool(self.ex_fp_max_speed.get()) else float(self.ex_fp_inter_delay.get())
                vbase = float(self.ex_fp_vbase.get())
                icc_val = float(self.icc.get())
                smu_type = getattr(self, 'SMU_type', 'Keithley 2401')

                v_arr, c_arr, t_arr = self.measurement_service.run_pulse_measurement(
                    keithley=self.keithley,
                    pulse_voltage=pulse_v,
                    pulse_width_ms=width_ms,
                    num_pulses=num,
                    read_voltage=vbase,
                    inter_pulse_delay_s=inter,
                    icc=icc_val,
                    smu_type=smu_type,
                    psu=getattr(self, 'psu', None),
                    led=False,
                    power=1.0,
                    sequence=None,
                    should_stop=lambda: getattr(self, 'stop_measurement_flag', False),
                    on_point=None,
                    validate_timing=True,
                )

                # Update time plot buffers
                try:
                    self.v_arr_disp.extend(list(v_arr))
                    self.c_arr_disp.extend(list(c_arr))
                    self.t_arr_disp.extend(list(t_arr))
                except Exception:
                    pass

                # Save
                save_dir = _ensure_save_dir()
                key = find_largest_number_in_folder(save_dir)
                save_key = 0 if key is None else key + 1
                name = f"{save_key}-FAST_PULSES-{pulse_v}v-{width_ms}ms-N{num}-Py"
                file_path = f"{save_dir}\\{name}.txt"
                try:
                    # Save as Time (elapsed), Current, Voltage with higher precision
                    data = np.column_stack((t_arr, c_arr, v_arr))
                    np.savetxt(file_path, data, fmt="%0.9E\t%0.9E\t%0.6E", header="Time(s) Current(A) Voltage(V)", comments="")
                except Exception:
                    pass

                if not self.single_device_flag:
                    self.sample_gui.next_device(); time.sleep(0.1); self.sample_gui.change_relays(); time.sleep(0.1)
            self._finalize_output()
            self.measuring = False
            self.status_box.config(text="Measurement Complete")
            show_popup = not self._bot_enabled()
            if show_popup:
                messagebox.showinfo("Complete", "Measurements finished.")
            return

        if excitation == "SMU_AND_PMU Fast Hold":
            for i in range(device_count):
                device = self.device_list[(start_index + i) % device_count]
                if self.stop_measurement_flag:
                    break
                self.status_box.config(text=f"Measuring {device} (SMU_AND_PMU Fast Hold)...")
                self.master.update()

                hold_v = float(self.ex_fh_voltage.get())
                duration = float(self.ex_fh_duration.get())
                dt = float(self.ex_fh_sample_dt.get())
                icc_val = float(self.icc.get())

                v_arr, c_arr, t_arr = self.measurement_service.run_dc_capture(
                    keithley=self.keithley,
                    voltage_v=hold_v,
                    capture_time_s=duration,
                    sample_dt_s=dt,
                    icc=icc_val,
                    on_point=None,
                    should_stop=lambda: getattr(self, 'stop_measurement_flag', False),
                )

                try:
                    self.v_arr_disp.extend(list(v_arr))
                    self.c_arr_disp.extend(list(c_arr))
                    self.t_arr_disp.extend(list(t_arr))
                except Exception:
                    pass

                # Save
                save_dir = _ensure_save_dir()
                key = find_largest_number_in_folder(save_dir)
                save_key = 0 if key is None else key + 1
                name = f"{save_key}-FAST_HOLD-{hold_v}v-{duration}s-Py"
                file_path = f"{save_dir}\\{name}.txt"
                try:
                    data = np.column_stack((v_arr, c_arr, t_arr))
                    np.savetxt(file_path, data, fmt="%0.3E\t%0.3E\t%0.3E", header="Voltage(V) Current(A) Time(s)", comments="")
                except Exception:
                    pass

                if not self.single_device_flag:
                    self.sample_gui.next_device(); time.sleep(0.1); self.sample_gui.change_relays(); time.sleep(0.1)
            self._finalize_output()
            self.measuring = False
            self.status_box.config(text="Measurement Complete")
            show_popup = not self._bot_enabled()
            if show_popup:
                messagebox.showinfo("Complete", "Measurements finished.")
            return

        if excitation == "ISPP":
            for i in range(device_count):
                device = self.device_list[(start_index + i) % device_count]
                if self.stop_measurement_flag:
                    break
                self.status_box.config(text=f"Measuring {device} (ISPP)..."); self.master.update()
                start_v = float(getattr(self, '_ispp_start', tk.DoubleVar(value=0.0)).get())
                stop_v = float(getattr(self, '_ispp_stop', tk.DoubleVar(value=1.0)).get())
                step_v = float(getattr(self, '_ispp_step', tk.DoubleVar(value=0.1)).get())
                pulse_ms = float(getattr(self, '_ispp_pulse_ms', tk.DoubleVar(value=1.0)).get())
                vbase = float(getattr(self, '_ispp_vbase', tk.DoubleVar(value=0.2)).get())
                target = float(getattr(self, '_ispp_target', tk.DoubleVar(value=1e-5)).get())
                inter = float(getattr(self, '_ispp_inter', tk.DoubleVar(value=0.0)).get())
                icc_val = float(self.icc.get())
                v_arr, c_arr, t_arr = self.measurement_service.run_ispp(
                    keithley=self.keithley,
                    start_v=start_v,
                    stop_v=stop_v,
                    step_v=step_v,
                    vbase=vbase,
                    pulse_width_ms=pulse_ms,
                    target_current_a=target,
                    inter_step_delay_s=inter,
                    icc=icc_val,
                    smu_type=getattr(self, 'SMU_type', 'Keithley 2401'),
                    should_stop=lambda: getattr(self, 'stop_measurement_flag', False),
                    on_point=None,
                    validate_timing=True,
                )
                try:
                    self.graphs_show(v_arr, c_arr, "ISPP", stop_v)
                except Exception:
                    pass
                save_dir = f"Data_save_loc\\{self.sample_name_var.get()}\\{self.final_device_letter}\\{self.final_device_number}"
                if not os.path.exists(save_dir): os.makedirs(save_dir)
                key = find_largest_number_in_folder(save_dir); save_key = 0 if key is None else key + 1
                name = f"{save_key}-ISPP-{stop_v}v-{pulse_ms}ms-Py"
                file_path = f"{save_dir}\\{name}.txt"
                try:
                    data = np.column_stack((v_arr, c_arr, t_arr)); np.savetxt(file_path, data, fmt="%0.3E\t%0.3E\t%0.3E", header="Amplitude(V) Current(A) Time(s)", comments="")
                except Exception:
                    pass
                if not self.single_device_flag:
                    self.sample_gui.next_device(); time.sleep(0.1); self.sample_gui.change_relays(); time.sleep(0.1)
            self._finalize_output()
            self.measuring = False; self.status_box.config(text="Measurement Complete")
            if not self._bot_enabled(): messagebox.showinfo("Complete", "Measurements finished.")
            return

        if excitation == "Pulse Width Sweep":
            for i in range(device_count):
                device = self.device_list[(start_index + i) % device_count]
                if self.stop_measurement_flag: break
                self.status_box.config(text=f"Measuring {device} (Pulse Width Sweep)..."); self.master.update()
                amp = float(getattr(self, '_pws_amp', tk.DoubleVar(value=0.5)).get())
                widths_csv = str(getattr(self, '_pws_widths', tk.StringVar(value="1,2,5,10")).get())
                try:
                    widths_ms = [float(x.strip()) for x in widths_csv.split(',') if x.strip()]
                except Exception:
                    widths_ms = [1.0, 2.0, 5.0, 10.0]
                vbase = float(getattr(self, '_pws_vbase', tk.DoubleVar(value=0.2)).get())
                inter = float(getattr(self, '_pws_inter', tk.DoubleVar(value=0.0)).get())
                icc_val = float(self.icc.get())
                w_arr, i_arr, t_arr = self.measurement_service.run_pulse_width_sweep(
                    keithley=self.keithley,
                    amplitude_v=amp,
                    widths_ms=widths_ms,
                    vbase=vbase,
                    icc=icc_val,
                    smu_type=getattr(self, 'SMU_type', 'Keithley 2401'),
                    inter_step_delay_s=inter,
                    should_stop=lambda: getattr(self, 'stop_measurement_flag', False),
                    on_point=None,
                    validate_timing=True,
                )
                try:
                    # Plot width(ms) vs I
                    self.graphs_show(w_arr, i_arr, "PWidth", amp)
                except Exception:
                    pass
                save_dir = f"Data_save_loc\\{self.sample_name_var.get()}\\{self.final_device_letter}\\{self.final_device_number}"
                if not os.path.exists(save_dir): os.makedirs(save_dir)
                key = find_largest_number_in_folder(save_dir); save_key = 0 if key is None else key + 1
                name = f"{save_key}-PWIDTH-{amp}v-Py"
                file_path = f"{save_dir}\\{name}.txt"
                try:
                    data = np.column_stack((w_arr, i_arr, t_arr)); np.savetxt(file_path, data, fmt="%0.3E\t%0.3E\t%0.3E", header="Width(ms) Current(A) Time(s)", comments="")
                except Exception:
                    pass
                if not self.single_device_flag:
                    self.sample_gui.next_device(); time.sleep(0.1); self.sample_gui.change_relays(); time.sleep(0.1)
            self._finalize_output()
            self.measuring = False; self.status_box.config(text="Measurement Complete")
            if not self._bot_enabled(): messagebox.showinfo("Complete", "Measurements finished.")
            return

        if excitation == "Threshold Search":
            for i in range(device_count):
                device = self.device_list[(start_index + i) % device_count]
                if self.stop_measurement_flag: break
                self.status_box.config(text=f"Measuring {device} (Threshold Search)..."); self.master.update()
                v_lo = float(getattr(self, '_th_lo', tk.DoubleVar(value=0.0)).get())
                v_hi = float(getattr(self, '_th_hi', tk.DoubleVar(value=1.0)).get())
                pulse_ms = float(getattr(self, '_th_pulse_ms', tk.DoubleVar(value=1.0)).get())
                vbase = float(getattr(self, '_th_vbase', tk.DoubleVar(value=0.2)).get())
                target = float(getattr(self, '_th_target', tk.DoubleVar(value=1e-5)).get())
                iters = int(getattr(self, '_th_iters', tk.IntVar(value=12)).get())
                icc_val = float(self.icc.get())
                v_arr, c_arr, t_arr = self.measurement_service.run_threshold_search(
                    keithley=self.keithley,
                    v_low=v_lo,
                    v_high=v_hi,
                    vbase=vbase,
                    pulse_width_ms=pulse_ms,
                    target_current_a=target,
                    max_iters=iters,
                    icc=icc_val,
                    smu_type=getattr(self, 'SMU_type', 'Keithley 2401'),
                    should_stop=lambda: getattr(self, 'stop_measurement_flag', False),
                    on_point=None,
                    validate_timing=True,
                )
                try:
                    self.graphs_show(v_arr, c_arr, "THRESH", v_hi)
                except Exception:
                    pass
                save_dir = f"Data_save_loc\\{self.sample_name_var.get()}\\{self.final_device_letter}\\{self.final_device_number}"
                if not os.path.exists(save_dir): os.makedirs(save_dir)
                key = find_largest_number_in_folder(save_dir); save_key = 0 if key is None else key + 1
                name = f"{save_key}-THRESH-{v_lo}-{v_hi}v-{pulse_ms}ms-Py"
                file_path = f"{save_dir}\\{name}.txt"
                try:
                    data = np.column_stack((v_arr, c_arr, t_arr)); np.savetxt(file_path, data, fmt="%0.3E\t%0.3E\t%0.3E", header="TestV(V) Current(A) Time(s)", comments="")
                except Exception:
                    pass
                if not self.single_device_flag:
                    self.sample_gui.next_device(); time.sleep(0.1); self.sample_gui.change_relays(); time.sleep(0.1)
            self.measuring = False; self.status_box.config(text="Measurement Complete")
            if not self._bot_enabled(): messagebox.showinfo("Complete", "Measurements finished.")
            return

        if excitation == "Transient Decay":
            for i in range(device_count):
                device = self.device_list[(start_index + i) % device_count]
                if self.stop_measurement_flag: break
                self.status_box.config(text=f"Measuring {device} (Transient Decay)..."); self.master.update()
                p_v = float(getattr(self, '_tr_pulse_v', tk.DoubleVar(value=0.8)).get())
                p_ms = float(getattr(self, '_tr_pulse_ms', tk.DoubleVar(value=1.0)).get())
                r_v = float(getattr(self, '_tr_read_v', tk.DoubleVar(value=0.2)).get())
                cap_s = float(getattr(self, '_tr_cap_s', tk.DoubleVar(value=1.0)).get())
                dt_s = float(getattr(self, '_tr_dt_s', tk.DoubleVar(value=0.001)).get())
                icc_val = float(self.icc.get())
                t_arr, i_arr, v_arr = self.measurement_service.run_transient_decay(
                    keithley=self.keithley,
                    pulse_voltage=p_v,
                    pulse_width_ms=p_ms,
                    read_voltage=r_v,
                    capture_time_s=cap_s,
                    sample_dt_s=dt_s,
                    icc=icc_val,
                    smu_type=getattr(self, 'SMU_type', 'Keithley 2401'),
                    should_stop=lambda: getattr(self, 'stop_measurement_flag', False),
                    on_point=None,
                )
                # Save time series
                save_dir = f"Data_save_loc\\{self.sample_name_var.get()}\\{self.final_device_letter}\\{self.final_device_number}"
                if not os.path.exists(save_dir): os.makedirs(save_dir)
                key = find_largest_number_in_folder(save_dir); save_key = 0 if key is None else key + 1
                name = f"{save_key}-TRANSIENT-{p_v}v-{p_ms}ms-Read{r_v}v-{cap_s}s@{dt_s}s-Py"
                file_path = f"{save_dir}\\{name}.txt"
                try:
                    data = np.column_stack((v_arr, i_arr, t_arr)); np.savetxt(file_path, data, fmt="%0.6E\t%0.6E\t%0.6E", header="Voltage(V) Current(A) Time(s)", comments="")
                except Exception:
                    pass
                if not self.single_device_flag:
                    self.sample_gui.next_device(); time.sleep(0.1); self.sample_gui.change_relays(); time.sleep(0.1)
            self.measuring = False; self.status_box.config(text="Measurement Complete")
            if not self._bot_enabled(): messagebox.showinfo("Complete", "Measurements finished.")
            return


        start_v = self._safe_get_float(self.start_voltage, "Start Voltage")
        if start_v is None:
            self.measuring = False
            return
        stop_v = self._safe_get_float(self.voltage_high, "Stop Voltage")
        if stop_v is None:
            self.measuring = False
            return
        # Optional asymmetric negative stop voltage support; fallback to |stop_v|
        neg_stop_v = None
        try:
            raw_neg = self.voltage_low_str.get().strip() if hasattr(self, 'voltage_low_str') else ""
            if raw_neg != "":
                neg_stop_v = float(raw_neg)
        except Exception:
            neg_stop_v = None
        sweeps_val = self._safe_get_float(self.sweeps, "Sweeps", default=1)
        if sweeps_val is None:
            self.measuring = False
            return
        sweeps = int(sweeps_val)
        step_v = self._safe_get_float(self.step_size, "Step Size", default=0.1)
        if step_v is None:
            self.measuring = False
            return
        sweep_type = "FS"
        step_delay = self._safe_get_float(self.step_delay, "Step Delay", default=0.05)
        if step_delay is None:
            self.measuring = False
            return
        icc = self._safe_get_float(self.icc, "Compliance (Icc)", default=1e-3)
        if icc is None:
            self.measuring = False
            return
        device_count = 1 if self.single_device_flag else len(self.device_list)
        pause = self._safe_get_float(self.pause, "Pause", default=0.0)
        if pause is None:
            self.measuring = False
            return

        led = self.led.get()
        led_power = self._safe_get_float(self.led_power, "LED Power", default=1.0)
        if led_power is None:
            self.measuring = False
            return
        sequence = self.sequence.get().strip()
        # if led != 1:
        #     led_power = 1
        # if led == 0:
        #     sequence = None

        # Build voltage range according to selected mode
        mode = self.sweep_mode_var.get() if hasattr(self, 'sweep_mode_var') else VoltageRangeMode.FIXED_STEP
        sweep_rate = float(self.var_sweep_rate.get()) if mode == VoltageRangeMode.FIXED_SWEEP_RATE else None
        total_time = float(self.var_total_time.get()) if mode == VoltageRangeMode.FIXED_VOLTAGE_TIME else None
        nsteps = int(self.var_num_steps.get()) if mode in (VoltageRangeMode.FIXED_SWEEP_RATE, VoltageRangeMode.FIXED_VOLTAGE_TIME) else None
        # Choose sweep type from dropdown if available
        try:
            sweep_type = self.sweep_type_var.get().strip().upper() or sweep_type
        except Exception:
            pass
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

            # measure device using centralized service with hardware acceleration!
            icc_val = float(self.icc.get())
            smu_type_str = getattr(self, 'SMU_type', 'Keithley 2401')
            
            # Check if hardware sweep will be used
            num_points_estimate = int(abs(stop_v - start_v) / step_v) + 1 if step_v else 100
            using_hardware_sweep = (
                smu_type_str == 'Keithley 4200A' and 
                num_points_estimate > 20 and 
                step_delay < 0.05
            )
            
            if using_hardware_sweep:
                # Status message for hardware sweep
                self.status_box.config(text="Hardware sweep in progress (fast mode)...")
                self.master.update()
                
                # Create sweep config
                from Measurments.sweep_config import SweepConfig
                from Measurments.source_modes import SourceMode
                
                # Get source mode from GUI
                source_mode_str = getattr(self, 'source_mode_var', None)
                if source_mode_str:
                    source_mode = SourceMode.CURRENT if source_mode_str.get() == "current" else SourceMode.VOLTAGE
                else:
                    source_mode = SourceMode.VOLTAGE  # Default
                
                config = SweepConfig(
                    start_v=start_v,
                    stop_v=stop_v,
                    step_v=step_v,
                    neg_stop_v=neg_stop_v,
                    step_delay=step_delay,
                    sweep_type=sweep_type,
                    sweeps=sweeps,
                    pause_s=pause,
                    icc=icc_val,
                    led=bool(led),
                    power=led_power,
                    sequence=sequence,
                    source_mode=source_mode
                )
                
                # Use new hardware-accelerated method
                v_arr, c_arr, timestamps = self.measurement_service.run_iv_sweep_v2(
                    keithley=self.keithley,
                    config=config,
                    smu_type=smu_type_str,
                    psu=getattr(self, 'psu', None),
                    optical=getattr(self, 'optical', None),
                    should_stop=lambda: getattr(self, 'stop_measurement_flag', False),
                    on_point=None  # Hardware sweep doesn't support live plotting
                )
                
                # Update status with completion time
                if timestamps:
                    self.status_box.config(
                        text=f"Sweep complete: {len(v_arr)} points in {timestamps[-1]:.2f}s"
                    )
            else:
                # Point-by-point with live plotting
                def _on_point(v, i, t_s):
                    self.v_arr_disp.append(v)
                    self.c_arr_disp.append(i)
                    self.t_arr_disp.append(t_s)
                
                # Get source mode for point-by-point (now supported!)
                from Measurments.source_modes import SourceMode
                source_mode_str = getattr(self, 'source_mode_var', None)
                if source_mode_str:
                    source_mode = SourceMode.CURRENT if source_mode_str.get() == "current" else SourceMode.VOLTAGE
                else:
                    source_mode = SourceMode.VOLTAGE  # Default
                
                v_arr, c_arr, timestamps = self.measurement_service.run_iv_sweep(
                    keithley=self.keithley,
                    icc=icc_val,
                    sweeps=sweeps,
                    step_delay=step_delay,
                    start_v=start_v,
                    stop_v=stop_v,
                    neg_stop_v=neg_stop_v,
                    step_v=step_v,
                    sweep_type=sweep_type,
                    mode=mode,
                    sweep_rate_v_per_s=sweep_rate,
                    total_time_s=total_time,
                    num_steps=nsteps,
                    psu=getattr(self, 'psu', None),
                    led=bool(led),
                    power=led_power,
                    optical=getattr(self, 'optical', None),
                    sequence=sequence,
                    pause_s=pause,
                    smu_type=smu_type_str,
                    should_stop=lambda: getattr(self, 'stop_measurement_flag', False),
                    on_point=_on_point,
                    source_mode=source_mode,
                )
            
            # If endurance selected as a custom mode via UI in future, we could branch here
            # For now, update endurance/retention plots if arrays exist from tests
            if hasattr(self, 'endurance_ratios') and self.endurance_ratios:
                self.ax_endurance.clear()
                self.ax_endurance.set_title("Endurance (ON/OFF)")
                self.ax_endurance.set_xlabel("Cycle")
                self.ax_endurance.set_ylabel("ON/OFF Ratio")
                self.ax_endurance.plot(range(1, len(self.endurance_ratios)+1), self.endurance_ratios, marker='o')
                self.canvas_endurance.draw()

            if hasattr(self, 'retention_times') and self.retention_times and hasattr(self, 'retention_currents'):
                self.ax_retention.clear()
                self.ax_retention.set_title("Retention")
                self.ax_retention.set_xlabel("Time (s)")
                self.ax_retention.set_ylabel("Current (A)")
                self.ax_retention.set_xscale('log')
                self.ax_retention.set_yscale('log')
                self.ax_retention.plot(self.retention_times, self.retention_currents, marker='x')
                self.canvas_retention.draw()

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
            # Optional optical suffix when using Laser
            opt_suffix = ""
            try:
                if hasattr(self, 'optical') and self.optical is not None:
                    caps = getattr(self.optical, 'capabilities', {})
                    if str(caps.get('type', '')).lower() == 'laser' and bool(led):
                        unit = str(caps.get('units', 'mW'))
                        lvl = float(led_power)
                        opt_suffix = f"-LASER{lvl}{unit}"
            except Exception:
                opt_suffix = ""
            name = f"{save_key}-{sweep_type}-{stop_v}v-{step_v}sv-{step_delay}sd-Py-{sweeps}{additional}{opt_suffix}{extra_info}"
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

        self._finalize_output()
        self.measuring = False
        self.status_box.config(text="Measurement Complete")
        # Only show popup if bot is disabled; otherwise let bot drive the follow-up
        show_popup = not self._bot_enabled()
        if show_popup:
            messagebox.showinfo("Complete", "Measurements finished.")
        try:
            # Also send post-measurement flow for single/normal measurement path
            if self._bot_enabled():
                save_dir = f"Data_save_loc\\{self.sample_name_var.get()}\\{self.final_device_letter}\\{self.final_device_number}"
                try:
                    # Save all plots to ensure combined has the latest
                    self.ax_all_iv.figure.savefig(f"{save_dir}\\All_graphs_IV.png", dpi=400)
                    self.ax_all_logiv.figure.savefig(f"{save_dir}\\All_graphs_LOG.png", dpi=400)
                except Exception:
                    pass
                combined = self._save_combined_summary_plot(save_dir)
                # Store last combined for consistency with custom flow
                self._last_combined_summary_path = combined
                import threading
                threading.Thread(target=self._post_measurement_options_worker,
                                 args=(save_dir, combined),
                                 daemon=True).start()
        except Exception:
            pass

    def retention_measure(self,
                          set_voltage: float,
                          set_time: float,
                          read_voltage: float,
                          repeat_delay: float,
                          number: int,
                          sequence: Optional[Union[str,int]] ,
                          led: bool,
                          led_time: Union[str, float],
                          pause: Optional[float] = None) -> Tuple[List[float], List[float], List[float]]:
        """Run retention via MeasurementService and return (v_arr, c_arr, timestamps)."""
        icc = 0.0001

        def _on_point(v: float, i: float, t_s: float) -> None:
            # Update plotting arrays minimally so existing plots keep working
            try:
                self.v_arr_disp.append(v)
                self.c_arr_disp.append(i)
                self.t_arr_disp.append(t_s)
            except Exception:
                pass

        v_arr, c_arr, t_arr = self.measurement_service.run_retention(
            keithley=self.keithley,
            set_voltage=set_voltage,
            set_time_s=set_time,
            read_voltage=read_voltage,
            repeat_delay_s=repeat_delay,
            number=number,
            icc=icc,
            psu=getattr(self, 'psu', None),
            led=bool(led),
            optical=getattr(self, 'optical', None),
            led_time_s=led_time,
            sequence=sequence,
            should_stop=lambda: getattr(self, 'stop_measurement_flag', False),
            on_point=_on_point,
        )

        return v_arr, c_arr, t_arr


    ###################################################################
    # Connect
    ###################################################################
    def connect_keithley(self) -> None:
        """Connect to the selected IV controller via GPIB using system config SMU_AND_PMU Type"""
        address = self.keithley_address_var.get()
        smu_type = getattr(self, 'SMU type', 'Keithley 2401')
        #print("3")
        try:
            #print("a")
            #print(smu_type)
            #print(address)
            self.keithley = IVControllerManager(self.SMU_type, address)
            # Verify the connection using controller's handle
            #print("b")
            try:
                self.connected = bool(self.keithley.is_connected())
            except Exception:
                self.connected = True
            self.status_box.config(text="Status: Connected")
            # Optional beep if supported
            if hasattr(self.keithley, 'beep'):
                self.keithley.beep(4000, 0.2)
                time.sleep(0.2)
                self.keithley.beep(5000, 0.5)
        except Exception as e:
            self.connected = False
            print("unable to connect to SMU please check")
            messagebox.showerror("Error", f"Could not connect to device: {str(e)}")

    def connect_keithley_psu(self) -> None:
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

    def connect_temp_controller(self) -> None:
        """Connect to the Keithley SMU_AND_PMU via GPIB"""
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

    def init_temperature_controller(self) -> None:
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

    def create_temperature_log(self) -> None:
        """Create a temperature log that records during measurements."""
        self.temperature_log = []
        self.is_logging_temperature = False

    def start_temperature_logging(self) -> None:
        """Start logging temperature data."""
        self.temperature_log = []
        self.is_logging_temperature = True
        self.log_temperature_data()

    def log_temperature_data(self) -> None:
        """Log temperature data periodically during measurements."""
        if self.is_logging_temperature and self.measuring:
            timestamp = time.time()
            temp = self.temp_controller.get_temperature_celsius()
            self.temperature_log.append((timestamp, temp))

            # Continue logging every second
            self.root.after(1000, self.log_temperature_data)

    def stop_temperature_logging(self) -> None:
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

    def send_temp(self) -> None:
        self.itc.set_temperature(int(self.temp_var.get()))
        self.graphs_temp_time_rt(self.Graph_frame)
        print("temperature set too", self.temp_var.get())

    def update_variables(self) -> None:
        # update current device
        self.current_device = self.device_list[self.current_index]
        # Update number (ie device_11)
        self.device_section_and_number = self.convert_to_name(self.current_index)
        # Update section and number
        self.display_index_section_number = self.current_device + "/" + self.device_section_and_number
        self.device_var.config(text=self.display_index_section_number)
        # print(self.convert_to_name(self.current_index))

    def measure_one_device(self) -> None:
        if self.adaptive_var.get():
            print("Measuring only one device")
            self.single_device_flag = True
        else:
            print("Measuring all devices")
            self.single_device_flag = False

    def update_last_sweeps(self) -> None:
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
    
    def _on_custom_save_toggle(self):
        """Handle checkbox toggle for custom save location"""
        if self.use_custom_save_var.get():
            # Always prompt for location when enabling (don't use saved default)
            self._prompt_save_location()
        else:
            self.save_path_entry.config(state="disabled")
            # Disable browse button
            for widget in self.save_path_entry.master.winfo_children():
                if isinstance(widget, tk.Button):
                    widget.config(state="disabled")
            self.custom_save_location = None
            self.custom_save_location_var.set("")
        
        # Save preference (but don't auto-load saved path on next enable)
        self._save_save_location_config()
    
    def _prompt_save_location(self):
        """Prompt user to choose a save location (folder) or cancel"""
        from tkinter import filedialog
        folder = filedialog.askdirectory(
            title="Choose Custom Data Save Location",
            mustexist=False  # Allow creating new folder
        )
        if folder:
            self.custom_save_location = Path(folder)
            self.custom_save_location_var.set(str(self.custom_save_location))
            self.save_path_entry.config(state="normal")
            # Enable browse button
            for widget in self.save_path_entry.master.winfo_children():
                if isinstance(widget, tk.Button):
                    widget.config(state="normal")
        else:
            # User cancelled - uncheck the box
            self.use_custom_save_var.set(False)
            self.save_path_entry.config(state="disabled")
            for widget in self.save_path_entry.master.winfo_children():
                if isinstance(widget, tk.Button):
                    widget.config(state="disabled")
    
    def _browse_save_location(self):
        """Open folder picker to change custom save location"""
        from tkinter import filedialog
        folder = filedialog.askdirectory(
            title="Choose Data Save Location",
            mustexist=False  # Allow creating new folder
        )
        if folder:
            self.custom_save_location = Path(folder)
            self.custom_save_location_var.set(str(self.custom_save_location))
            # Save preference (as reference, but won't auto-enable)
            self._save_save_location_config()
    
    def _load_save_location_config(self):
        """Load save location preference from config file (but don't auto-enable)"""
        config_file = Path("Json_Files") / "save_location_config.json"
        try:
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    # Don't auto-load the saved path - user must choose each time
                    # Just keep the checkbox unchecked by default
                    self.use_custom_save_var.set(False)
                    # Store the last path for reference, but don't use it automatically
                    custom_path = config.get('custom_save_path', '')
                    if custom_path:
                        # Store in entry but leave disabled (just shows last used path)
                        self.custom_save_location_var.set(custom_path)
                    else:
                        self.custom_save_location_var.set("")
        except Exception as e:
            print(f"Could not load save location config: {e}")
    
    def _save_save_location_config(self):
        """Save save location preference to config file"""
        config_file = Path("Json_Files") / "save_location_config.json"
        try:
            config = {}
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = json.load(f)
            
            config['use_custom_save'] = self.use_custom_save_var.get()
            config['custom_save_path'] = str(self.custom_save_location) if self.custom_save_location else ""
            
            config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Could not save save location config: {e}")
    
    def _get_base_save_path(self) -> Optional[str]:
        """Get base save path (custom if enabled, None for default)"""
        if self.use_custom_save_var.get() and self.custom_save_location:
            return str(self.custom_save_location)
        return None  # None means use default (Data_save_loc)
    
    def _get_save_directory(self, sample_name: str, device_letter: str, device_number: str) -> str:
        """
        Get save directory path, using custom base if configured.
        
        Args:
            sample_name: Sample name (only used with default base)
            device_letter: Device letter (e.g., "A")
            device_number: Device number (e.g., "1")
        
        Returns:
            String path to save directory
        """
        base_path = self._get_base_save_path()
        if base_path:
            # Custom path: {custom_base}/{letter}/{number}
            return os.path.join(base_path, device_letter, device_number)
        else:
            # Default path: Data_save_loc/{sample_name}/{letter}/{number}
            return f"Data_save_loc\\{sample_name}\\{device_letter}\\{device_number}"
    
    def check_for_sample_name(self) -> None:
        """Check if sample name is set, prompt if not (thread-safe)."""
        sample_name = self.sample_name_var.get().strip()

        if not sample_name:
            # Must run dialog on main thread - schedule it
            result_holder = [None]  # Mutable container to store result across thread boundary
            
            def ask_on_main_thread():
                """Run the dialog on the main GUI thread."""
                new_name = simpledialog.askstring(
                    "Sample Name Required", 
                    "Enter sample name (or cancel for 'undefined'):", 
                    parent=self.master
                )
                
                # Clean and validate the entered name
                if new_name:
                    cleaned_name = new_name.strip()
                    # Remove/replace invalid file path characters
                    invalid_chars = '<>:"|?*\\/[]'
                    for char in invalid_chars:
                        cleaned_name = cleaned_name.replace(char, '_')
                    
                    if cleaned_name:
                        self.sample_name_var.set(cleaned_name)
                    else:
                        self.sample_name_var.set("undefined")
                else:
                    self.sample_name_var.set("undefined")
                
                result_holder[0] = True  # Signal completion
            
            # If we're on the main thread, just call it directly
            try:
                if threading.current_thread() == threading.main_thread():
                    ask_on_main_thread()
                else:
                    # Schedule on main thread and wait
                    self.master.after(0, ask_on_main_thread)
                    # Wait for dialog to complete (with timeout)
                    timeout = 60  # 60 seconds
                    elapsed = 0
                    while result_holder[0] is None and elapsed < timeout:
                        time.sleep(0.1)
                        elapsed += 0.1
                    
                    if result_holder[0] is None:
                        # Timeout - just set undefined
                        self.sample_name_var.set("undefined")
            except Exception as e:
                print(f"Error in sample name dialog: {e}")
                self.sample_name_var.set("undefined")

    def check_connection(self) -> None:
        self.connect_keithley()
        time.sleep(0.1)
        self.Check_connection_gui = CheckConnection(self.master, self.keithley)

    def open_adaptive_settings(self) -> None:
        if self.adaptive_measurement is None or not self.adaptive_measurement.master.winfo_exists():
            self.adaptive_measurement = AdaptiveMeasurement(self.master)

    def show_last_sweeps(self) -> None:
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

    def clear_axis(self, axis: int) -> None:
        """Clear one of the 'All sweeps' axes by index.

        axis=2 clears the linear IV panel; axis=3 clears the log(|I|) panel.
        """
        if axis == 2:
            self.ax_all_iv.clear()
            try:
                self.canvas_all_iv.draw()
            except Exception:
                pass
            self.master.update_idletasks()
            self.master.update()
        if axis == 3:
            self.ax_all_logiv.clear()
            self.ax_all_logiv.set_yscale('log')
            try:
                self.canvas_all_logiv.draw()
            except Exception:
                pass
            self.master.update_idletasks()
            self.master.update()

    def save_all_measurements_file(self, device_data: Dict[str, Dict[str, List[float]]],
                                   sample_name: str,
                                   start_index: int) -> str:
        """Create a consolidated CSV and graphs for every device in `device_data`.

        The CSV organizes each device as a group of columns (time, temperature,
        voltage, current, std error, resistance, conductance, normalized).
        Individual and comparison graphs are saved to a `graphs` subdirectory.

        Args:
            device_data (dict): mapping device_id -> dict of arrays (timestamps, voltages, currents, ...)
            sample_name (str): sample folder/name used for saving
            start_index (int): index of the first device (used for filenames/labels)

        Returns:
            filename (str): CSV filename created under `Data_save_loc`.
        """

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

    def _create_individual_device_graphs(self, graph_data: Dict[str, Dict[str, Any]],
                                         graphs_dir: str,
                                         sample_name: str,
                                         timestamp: str) -> None:
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

    def _create_comparison_graph(self, graph_data: Dict[str, Dict[str, Any]],
                                 graphs_dir: str,
                                 sample_name: str,
                                 timestamp: str) -> None:
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

    def spare_button(self) -> None:
        print("spare")

    def convert_to_name(self, device_number: int) -> str:
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

    def create_log_file(self, save_dir: str, start_time: str, measurement_type: str) -> None:
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

    def graphs_show(self, v_arr: List[float], c_arr: List[float], key: Union[str,int], stop_v: float) -> None:

        # # plot on main screen! on #1
        # self.ax_rt_iv.clear()
        # self.ax_rt_iv.plot(v_arr, c_arr, marker='o', markersize=2, color='k')
        # self.canvas_rt_iv.draw()

        # Remember last sweep for summary/final plot sharing
        try:
            self._last_sweep_data = (list(v_arr), list(c_arr))
        except Exception:
            self._last_sweep_data = (v_arr, c_arr)

        self.ax_all_iv.plot(v_arr, c_arr, marker='o', markersize=2, label=key + "_" + str(stop_v) + "v", alpha=0.8)
        self.ax_all_iv.legend(loc="best", fontsize="5")
        self.ax_all_logiv.plot(v_arr, np.abs(c_arr), marker='o', markersize=2, label=key + "_" + str(stop_v) + "v",
                               alpha=0.8)
        self.ax_all_logiv.legend(loc="best", fontsize="5")
        self.canvas_all_iv.draw()
        self.canvas_all_logiv.draw()
        self.master.update_idletasks()
        self.master.update()

    def _reset_plots_for_new_run(self) -> None:
        """Clear live buffers and 'All sweeps' axes so a new run starts clean."""
        try:
            # Reset in-memory buffers used by background plotters
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
        except Exception:
            pass

        # Clear the summary axes that accumulate lines across runs
        try:
            self.ax_all_iv.clear()
            self.ax_all_logiv.clear()
            self.ax_all_logiv.set_yscale('log')
            self.canvas_all_iv.draw()
            self.canvas_all_logiv.draw()
        except Exception:
            pass

        # Clear the real-time line objects if available
        try:
            if hasattr(self, 'line_rt_iv'):
                self.line_rt_iv.set_data([], [])
                self.canvas_rt_iv.draw()
        except Exception:
            pass
        try:
            if hasattr(self, 'line_rt_logiv'):
                self.line_rt_logiv.set_data([], [])
                self.canvas_rt_logiv.draw()
        except Exception:
            pass
        try:
            if hasattr(self, 'line_rt_vi'):
                self.line_rt_vi.set_data([], [])
                self.canvas_rt_vi.draw()
        except Exception:
            pass
        try:
            if hasattr(self, 'line_rt_logilogv'):
                self.line_rt_logilogv.set_data([], [])
                self.canvas_rt_logilogv.draw()
        except Exception:
            pass
        try:
            if hasattr(self, 'line_ct_rt'):
                self.line_ct_rt.set_data([], [])
                self.canvas_ct_rt.draw()
        except Exception:
            pass
        try:
            if hasattr(self, 'line_rt_rt'):
                self.line_rt_rt.set_data([], [])
                self.canvas_rt_rt.draw()
        except Exception:
            pass

    def _save_final_sweep_plot(self, save_dir: str) -> Tuple[Optional[str], Optional[str]]:
        """Save final sweep plots (linear and log) using Agg backend. Returns (iv_path, log_path)."""
        try:
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
            v_arr, c_arr = getattr(self, '_last_sweep_data', (None, None))
            if v_arr is None or c_arr is None:
                return (None, None)
            iv_path = f"{save_dir}\\Final_graph_IV.png"
            log_path = f"{save_dir}\\Final_graph_LOG.png"
            try:
                fig_iv = Figure(figsize=(4, 3))
                _ = FigureCanvas(fig_iv)
                ax_iv = fig_iv.add_subplot(111)
                ax_iv.set_title("Final Sweep (IV)")
                ax_iv.set_xlabel("Voltage (V)")
                ax_iv.set_ylabel("Current (A)")
                ax_iv.plot(v_arr, c_arr, marker='o', markersize=2, color='k')
                fig_iv.savefig(iv_path, dpi=300)
            except Exception:
                iv_path = None
            try:
                fig_log = Figure(figsize=(4, 3))
                _ = FigureCanvas(fig_log)
                ax_log = fig_log.add_subplot(111)
                ax_log.set_title("Final Sweep (|I|)")
                ax_log.set_xlabel("Voltage (V)")
                ax_log.set_ylabel("|Current| (A)")
                ax_log.semilogy(v_arr, np.abs(c_arr), marker='o', markersize=2, color='k')
                fig_log.savefig(log_path, dpi=300)
            except Exception:
                log_path = None
            return (iv_path, log_path)
        except Exception:
            return (None, None)

    def _save_combined_summary_plot(self, save_dir: str) -> Optional[str]:
        """Create a 2x2 summary figure using Agg: (All IV, All log, Final IV, Final log). Returns image path or None."""
        try:
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
            combined_path = f"{save_dir}\\Combined_summary.png"
            fig = Figure(figsize=(8, 6))
            _ = FigureCanvas(fig)
            ax_all_iv = fig.add_subplot(221)
            ax_all_log = fig.add_subplot(222)
            ax_final_iv = fig.add_subplot(223)
            ax_final_log = fig.add_subplot(224)

            # Re-plot from existing lines in the GUI axes
            try:
                for line in self.ax_all_iv.get_lines():
                    x = line.get_xdata()
                    y = line.get_ydata()
                    ax_all_iv.plot(x, y, marker='o', markersize=2, alpha=0.8)
                ax_all_iv.set_title("All sweeps (IV)")
                ax_all_iv.set_xlabel("V (V)")
                ax_all_iv.set_ylabel("I (A)")
            except Exception:
                pass

            try:
                for line in self.ax_all_logiv.get_lines():
                    x = line.get_xdata()
                    y = np.abs(line.get_ydata())
                    ax_all_log.semilogy(x, y, marker='o', markersize=2, alpha=0.8)
                ax_all_log.set_title("All sweeps (|I|)")
                ax_all_log.set_xlabel("V (V)")
                ax_all_log.set_ylabel("|I| (A)")
            except Exception:
                pass

            # Final sweep from last remembered data
            try:
                v_arr, c_arr = getattr(self, '_last_sweep_data', (None, None))
                if v_arr is not None and c_arr is not None:
                    ax_final_iv.plot(v_arr, c_arr, marker='o', markersize=2, color='k')
                    ax_final_iv.set_title("Final sweep (IV)")
                    ax_final_iv.set_xlabel("V (V)")
                    ax_final_iv.set_ylabel("I (A)")

                    ax_final_log.semilogy(v_arr, np.abs(c_arr), marker='o', markersize=2, color='k')
                    ax_final_log.set_title("Final sweep (|I|)")
                    ax_final_log.set_xlabel("V (V)")
                    ax_final_log.set_ylabel("|I| (A)")
            except Exception:
                pass

            fig.tight_layout()
            fig.savefig(combined_path, dpi=300)
            return combined_path
        except Exception:
            return None

    def _post_measurement_options_worker(self, save_dir: str, combined_path: Optional[str] = None) -> None:
        """Runs in background: sends summary and asks what to do next via Telegram."""
        try:
            bot = self._get_bot()
            if not bot:
                return
            # Send completion message and images
            try:
                bot.send_message("Measurement finished")
            except Exception:
                pass
            try:
                if combined_path:
                    bot.send_image(combined_path, caption="Summary (All + Final)")
            except Exception:
                pass

            # Ask for next steps
            choices = {
                "1": "Finish",
                "2": "Pick another custom sweep",
                "3": "Do a normal measurement",
                "4": "Endurance or retention",
            }
            reply = None
            try:
                reply = bot.ask_and_wait("Would you like to continue measuring?", choices, timeout_s=900)
            except Exception:
                reply = None
            if not reply:
                return
            r = reply.strip().lower()
            # Normalize number selections
            if r.startswith("1") or "finish" in r:
                try:
                    bot.send_message("Okay, finishing.")
                except Exception:
                    pass
                # Send final image again at end as confirmation
                try:
                    v_path, l_path = self._save_final_sweep_plot(save_dir)
                    for p in (v_path, l_path):
                        if p:
                            bot.send_image(p, caption="Final measurement")
                except Exception:
                    pass
                return
            if r.startswith("2") or r == "2" or "custom" in r:
                # Offer list of custom sweeps
                names = list(self.custom_sweeps.keys()) if hasattr(self, 'custom_sweeps') else []
                listing = "\n".join([f"{i+1}. {n}" for i, n in enumerate(names)]) or "No custom sweeps available"
                try:
                    bot.send_message("Available custom sweeps:\n" + listing + "\n\nReply with number or name.")
                except Exception:
                    pass
                selected = bot.wait_for_text_reply(timeout_s=900)
                if not selected:
                    return
                sel = selected.strip()
                chosen = None
                try:
                    idx = int(sel) - 1
                    if 0 <= idx < len(names):
                        chosen = names[idx]
                except Exception:
                    pass
                if chosen is None:
                    # match by name
                    for n in names:
                        if n.lower() == sel.lower():
                            chosen = n
                            break
                if chosen is None:
                    try:
                        bot.send_message("Could not recognise that sweep. Aborting.")
                    except Exception:
                        pass
                    return
                # Confirm start
                try:
                    bot.send_message(f"Starting custom sweep: {chosen}")
                except Exception:
                    pass
                def start_custom():
                    try:
                        self.custom_measurement_var.set(chosen)
                    except Exception:
                        pass
                    try:
                        self.run_custom_measurement()
                    except Exception:
                        pass
                self.master.after(0, start_custom)
                return
            if r.startswith("3") or r == "3" or "normal" in r or "manual" in r:
                # Ask for optional overrides
                try:
                    # Summarise current parameters for convenience
                    cur = {
                        'start_v': getattr(self, 'start_voltage').get() if hasattr(self, 'start_voltage') else None,
                        'stop_v': getattr(self, 'voltage_high').get() if hasattr(self, 'voltage_high') else None,
                        'step_v': getattr(self, 'step_size').get() if hasattr(self, 'step_size') else None,
                        'sweeps': getattr(self, 'sweeps').get() if hasattr(self, 'sweeps') else None,
                        'step_delay': getattr(self, 'step_delay').get() if hasattr(self, 'step_delay') else None,
                        'icc': getattr(self, 'icc').get() if hasattr(self, 'icc') else None,
                        'pause': getattr(self, 'pause').get() if hasattr(self, 'pause') else None,
                        'led': getattr(self, 'led').get() if hasattr(self, 'led') else None,
                        'led_power': getattr(self, 'led_power').get() if hasattr(self, 'led_power') else None,
                        'sequence': getattr(self, 'sequence').get() if hasattr(self, 'sequence') else None,
                    }
                    msg = (
                        "Okay, please specify options as key=value pairs (comma separated).\n"
                        "Supported: start_v, stop_v (alias: V), step_v (alias: Sv), sweeps, step_delay, icc, pause, led, led_power, sequence.\n"
                        "Example: start_v=0, V=1, Sv=0.1, sweeps=1, step_delay=0.05, icc=1e-3\n"
                        "Send 'default' to keep current settings.\n\n"
                        f"Current: start_v={cur['start_v']}, stop_v={cur['stop_v']}, step_v={cur['step_v']}, sweeps={cur['sweeps']}, step_delay={cur['step_delay']}, icc={cur['icc']}, pause={cur['pause']}, led={cur['led']}, led_power={cur['led_power']}, sequence={cur['sequence']}"
                    )
                    bot.send_message(msg)
                except Exception:
                    pass
                opts = bot.wait_for_text_reply(timeout_s=900)
                if opts:
                    o = opts.strip()
                    if o.lower() != "default":
                        # Parse key=value
                        try:
                            pairs = [p.strip() for p in o.replace("\n", ",").split(",") if p.strip()]
                            kv = {}
                            for p in pairs:
                                if "=" in p:
                                    k, v = p.split("=", 1)
                                    key_norm = k.strip()
                                    key_low = key_norm.lower()
                                    # Aliases for brevity in chat: V -> stop_v, Sv -> step_v
                                    if key_low in ("v",):
                                        key_low = "stop_v"
                                    if key_low in ("sv",):
                                        key_low = "step_v"
                                    kv[key_low] = v.strip()
                            def set_var(name, conv=float):
                                if name in kv:
                                    try:
                                        getattr(self, name_map[name]).set(conv(kv[name]))
                                    except Exception:
                                        pass
                            # Map keys to Tk vars
                            name_map = {
                                'start_v': 'start_voltage',
                                'stop_v': 'voltage_high',
                                'step_v': 'step_size',
                                'sweeps': 'sweeps',
                                'step_delay': 'step_delay',
                                'icc': 'icc',
                                'pause': 'pause',
                                'led': 'led',
                                'led_power': 'led_power',
                                'sequence': 'sequence',
                            }
                            set_var('start_v', float)
                            set_var('stop_v', float)
                            set_var('step_v', float)
                            set_var('sweeps', float)
                            set_var('step_delay', float)
                            set_var('icc', float)
                            set_var('pause', float)
                            # led, led_power, sequence: handle separately
                            if 'led' in kv:
                                try:
                                    getattr(self, 'led').set(int(kv['led']))
                                except Exception:
                                    pass
                            if 'led_power' in kv:
                                try:
                                    getattr(self, 'led_power').set(float(kv['led_power']))
                                except Exception:
                                    pass
                            if 'sequence' in kv:
                                try:
                                    getattr(self, 'sequence').set(kv['sequence'])
                                except Exception:
                                    pass
                        except Exception:
                            pass
                # Summarise final parameters that will be used
                try:
                    cur = {
                        'start_v': getattr(self, 'start_voltage').get() if hasattr(self, 'start_voltage') else None,
                        'stop_v': getattr(self, 'voltage_high').get() if hasattr(self, 'voltage_high') else None,
                        'step_v': getattr(self, 'step_size').get() if hasattr(self, 'step_size') else None,
                        'sweeps': getattr(self, 'sweeps').get() if hasattr(self, 'sweeps') else None,
                        'step_delay': getattr(self, 'step_delay').get() if hasattr(self, 'step_delay') else None,
                        'icc': getattr(self, 'icc').get() if hasattr(self, 'icc') else None,
                        'pause': getattr(self, 'pause').get() if hasattr(self, 'pause') else None,
                        'led': getattr(self, 'led').get() if hasattr(self, 'led') else None,
                        'led_power': getattr(self, 'led_power').get() if hasattr(self, 'led_power') else None,
                        'sequence': getattr(self, 'sequence').get() if hasattr(self, 'sequence') else None,
                    }
                    bot.send_message(
                        f"Using: start_v={cur['start_v']}, stop_v={cur['stop_v']} (V), step_v={cur['step_v']} (Sv), sweeps={cur['sweeps']}, step_delay={cur['step_delay']}, icc={cur['icc']}, pause={cur['pause']}, led={cur['led']}, led_power={cur['led_power']}, sequence={cur['sequence']}"
                    )
                except Exception:
                    pass
                try:
                    bot.send_message("Type 'Start' to begin now, or anything else to cancel.")
                except Exception:
                    pass
                conf = bot.wait_for_text_reply(timeout_s=900)
                if conf and conf.strip().lower() in ("start", "yes", "y"):
                    def start_norm():
                        try:
                            self.start_measurement()
                        except Exception:
                            pass
                    self.master.after(0, start_norm)
                return
            if r.startswith("4") or r == "4" or "endurance" in r or "retention" in r:
                try:
                    bot.send_message("Reply with 'endurance' or 'retention'. Defaults from GUI will be used.")
                except Exception:
                    pass
                m = bot.wait_for_text_reply(timeout_s=900)
                if not m:
                    return
                ml = m.strip().lower()
                if "endurance" in ml:
                    def start_end():
                        try:
                            self.start_manual_endurance()
                        except Exception:
                            pass
                    try:
                        bot.send_message("Starting endurance...")
                    except Exception:
                        pass
                    self.master.after(0, start_end)
                    return
                if "retention" in ml:
                    def start_ret():
                        try:
                            self.start_manual_retention()
                        except Exception:
                            pass
                    try:
                        bot.send_message("Starting retention...")
                    except Exception:
                        pass
                    self.master.after(0, start_ret)
                    return
        except Exception:
            pass

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





def get_voltage_range(start_v: float,
                      stop_v: float,
                      step_v: float,
                      sweep_type: str,
                      neg_stop_v: Optional[float] = None) -> List[float]:
    """Compatibility wrapper routing to MeasurementService to compute voltage ranges.

    Existing code calls this function from several places; keep the signature and
    delegate to the centralized service to avoid divergence.
    """
    try:
        svc = MeasurementService()
        return svc.compute_voltage_range(start_v, stop_v, step_v, sweep_type, mode=VoltageRangeMode.FIXED_STEP, neg_stop_v=neg_stop_v)
    except Exception:
        # Fallback to legacy behavior if service import/usage fails for any reason
        def frange(start, stop, step):
            """Simple floating-range generator used when MeasurementService is unavailable.

            Rounds to 3 decimals to avoid long floating point tails.
            """
            while start <= stop if step > 0 else start >= stop:
                yield round(start, 3)
                start += step
        if sweep_type == "NS":
            neg_target = -abs(neg_stop_v if neg_stop_v is not None else stop_v)
            return list(frange(start_v, neg_target, -abs(step_v))) + list(frange(neg_target, start_v, abs(step_v)))
        if sweep_type == "PS":
            return list(frange(start_v, stop_v, abs(step_v))) + list(frange(stop_v, start_v, -abs(step_v)))
        neg_target = -abs(neg_stop_v if neg_stop_v is not None else stop_v)
        return (
            list(frange(start_v, stop_v, abs(step_v)))
            + list(frange(stop_v, neg_target, -abs(step_v)))
            + list(frange(neg_target, start_v, abs(step_v)))
        )


def extract_number_from_filename(filename: str) -> Optional[int]:
    """Extract a leading integer prefix from a filename of the form '<N>-rest...'.

    Returns the integer or None if no leading numeric prefix is present.
    """
    match = re.match(r'^(\d+)-', filename)
    if match:
        return int(match.group(1))
    return None


def find_largest_number_in_folder(folder_path: str) -> Optional[int]:
    """Return the largest leading numeric prefix for files in `folder_path`.

    Used to choose a monotonically-increasing save key when writing new
    measurement files of the form '<N>-...'. Returns None if none found.
    """
    largest_number = None

    # Iterate over all files in the folder
    try:
        for filename in os.listdir(folder_path):
            number = extract_number_from_filename(filename)
            if number is not None:
                if largest_number is None or number > largest_number:
                    largest_number = number
    except FileNotFoundError:
        return None

    return largest_number


def zero_devision_check(x: float, y: float) -> float:
    """Safe division helper returning 0 on any error (e.g., division by zero).

    Prefer explicit error handling where possible; this function is a small
    convenience in places where 0 is an acceptable fallback.
    """
    try:
        return x / y
    except Exception:
        return 0

if __name__ == "__main__":
    print("you cannot do this")