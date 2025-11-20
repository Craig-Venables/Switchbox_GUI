"""
Measurement GUI - Main Measurement Interface
=============================================

Purpose:
--------
Main measurement interface for IV/PMU/SMU measurements on device arrays.
Provides comprehensive control over instrument connections, measurement
configuration, real-time plotting, and data saving. Acts as the central hub
for launching specialized measurement tools.

Key Features:
-------------
- Instrument connection management (SMU, PSU, temperature controllers)
- IV sweep configuration and execution
- Custom measurement sweeps (loadable from JSON)
- Real-time plotting (voltage, current, resistance)
- Sequential measurement support
- Manual endurance/retention test controls
- Data saving with automatic file naming
- Telegram integration for notifications
- Optical excitation control (LED, laser)

Entry Points:
-------------
Launched from Sample_GUI:
  ```python
  # In Sample_GUI, when user clicks "Start Measurement"
  measurement_gui = MeasurementGUI(
      master=parent_window,
      sample_type="Cross_bar",
      section="A",
      device_list=["1", "2", "3"],
      sample_gui=self
  )
  ```

Launches:
---------
- TSPTestingGUI: Pulse testing interface
  - Access: "Pulse Testing" button/tab
  - Passes: device address, sample context

- CheckConnection: Connection verification tool
  - Access: "Check Connection" button
  - Purpose: Verify electrical connections

- MotorControlWindow: Motor control for laser positioning
  - Access: "Motor Control" button
  - Purpose: XY stage control

- AdvancedTestsGUI: Advanced/volatile memristor tests
  - Access: "Advanced Tests" button/tab
  - Tests: PPF, STDP, SRDP, transient decay

- AutomatedTesterGUI: Automated testing workflows
  - Access: "Automated Tester" button
  - Purpose: Batch device testing

Dependencies:
-------------
- Measurments.measurement_services_smu: SMU measurement service
- Measurments.measurement_services_pmu: PMU measurement service
- Measurments.connection_manager: Instrument connection management
- gui.layout_builder: Modern tabbed layout builder
- gui.plot_panels: Plotting components
- gui.plot_updaters: Plot update logic
- Equipment.iv_controller_manager: IV controller management
- Equipment.power_supply_manager: Power supply management
- Equipment.temperature_controller_manager: Temperature control

Relationships:
-------------
MeasurementGUI (this file)
    ├─> Launched from: Sample_GUI
    ├─> Launches: TSPTestingGUI
    ├─> Launches: CheckConnection
    ├─> Launches: MotorControlWindow
    ├─> Launches: AdvancedTestsGUI
    └─> Launches: AutomatedTesterGUI

Key Components:
---------------
- SMUAdapter: Adapter layer for simple instrument API
- MeasurementGUI: Main window class
- InstrumentConnectionManager: Manages instrument lifecycles
- MeasurementGUILayoutBuilder: Builds modern tabbed interface

File Structure:
---------------
- ~2000+ lines
- Main class: MeasurementGUI
- Uses layout_builder.py for UI construction (good separation!)
- Routes measurement work to MeasurementService (good separation!)
"""
# Standard library imports
import atexit
import json
import logging
import os
import queue
import re
import string
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple, Union

# Get project root (go up from gui/measurement_gui/ to project root)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]  # gui/measurement_gui/main.py -> gui -> root

# Third-party imports
import numpy as np
import tkinter as tk
from telegram import PassportData
from tkinter import messagebox, simpledialog, ttk

# Local application imports
from gui.connection_check_gui import CheckConnection
from Equipment.optical_excitation import OpticalExcitation, create_optical_from_system_config
from gui.motor_control_gui import MotorControlWindow
from Measurments.background_workers import (
    start_manual_endurance as bw_start_manual_endurance,
    start_manual_retention as bw_start_manual_retention,
)
from Measurments.connection_manager import InstrumentConnectionManager
from Measurments.data_saver import MeasurementDataSaver, SummaryPlotData
from Measurments.data_utils import safe_measure_current, safe_measure_voltage
from Measurments.measurement_services_smu import MeasurementService, VoltageRangeMode
from Measurments.optical_controller import OpticalController
from Measurments.pulsed_measurement_runner import PulsedMeasurementRunner
from Measurments.sequential_runner import run_sequential_measurement
from Measurments.single_measurement_runner import SingleMeasurementRunner
from Measurments.special_measurement_runner import SpecialMeasurementRunner
from Measurments.telegram_coordinator import TelegramCoordinator
from gui.measurement_gui.layout_builder import MeasurementGUILayoutBuilder
from gui.measurement_gui.plot_panels import MeasurementPlotPanels
from gui.measurement_gui.plot_updaters import PlotUpdaters
from gui.pulse_testing_gui import TSPTestingGUI

# Import cyclical IV sweep functions for 4200A (conditional import)
# Using importlib to avoid issues with directory names starting with numbers
try:
    import importlib
    _smu_iv_sweep_module = importlib.import_module('Equipment.SMU_AND_PMU.4200A.C_Code_with_python_scripts.A_Iv_Sweep.run_smu_vi_sweep')
    KXCIClient = _smu_iv_sweep_module.KXCIClient
    build_ex_command = _smu_iv_sweep_module.build_ex_command
    format_param = _smu_iv_sweep_module.format_param
except (ImportError, AttributeError):
    # Gracefully handle if module is not available
    KXCIClient = None
    build_ex_command = None
    format_param = None

# Optional dependencies --------------------------------------------------------
try:  # PMU testing GUI is optional (requires PMU hardware stack)
    from PMU_Testing_GUI import PMUTestingGUI  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    PMUTestingGUI = None  # type: ignore

try:  # Legacy live plotter utility (not always present)
    from Measurement_Plotter import MeasurementPlotter  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    try:
        from measurement_plotter import MeasurementPlotter  # type: ignore
    except Exception:  # pragma: no cover
        MeasurementPlotter = None  # type: ignore

try:  # Automated test framework (external package)
    from automated_tests.framework import MeasurementDriver, TestRunner, load_thresholds  # type: ignore
    _HAS_TEST_FRAMEWORK = True
except Exception:  # pragma: no cover - optional dependency
    MeasurementDriver = None  # type: ignore
    TestRunner = None  # type: ignore
    load_thresholds = None  # type: ignore
    _HAS_TEST_FRAMEWORK = False

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
#from Automated_tester_GUI import AutomatedTesterGUI

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
        self._base_title = "IV Measurement System"
        self._status_message = ""
        self.master.title(self._base_title)
        self.master.geometry("1920x1080")
        #200+100
        self.sample_gui = sample_gui
        self.current_index = self.sample_gui.current_index
        self.load_messaging_data()
        
        # Set up window close protocol to notify sample_gui
        def on_closing():
            """Handle window close - notify sample_gui and cleanup"""
            # Notify sample_gui that measurement window is closing
            if hasattr(self.sample_gui, '_on_measurement_window_closed'):
                self.sample_gui._on_measurement_window_closed()
            # Clean up resources
            self.cleanup()
            # Destroy the window
            self.master.destroy()
        
        self.master.protocol("WM_DELETE_WINDOW", on_closing)
        
        self.psu_visa_address = "USB0::0x05E6::0x2220::9210734::INSTR"
        self.temp_controller_address= 'ASRL12::INSTR'
        self.keithley_address = "GPIB0::24::INSTR"
        self.controller_type: str = "Auto-Detect"
        self.controller_address: str = self.temp_controller_address
        self.temp_setpoint: Optional[str] = None
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
        self.display_index_section_number = f"{self.device_section_and_number} ({self.current_device})"
        self._update_device_identifiers(self.device_section_and_number)

        # Flags
        self.connected = False
        self.keithley = None  # Keithley instance
        self.psu_connected = False
        self.adaptive_measurement = None
        self.single_device_flag = True
        self.stop_measurement_flag = False
        self.measuring = False
        self.not_at_tempriture = False
        self.itc_connected = False
        self.lakeshore = None
        self.psu_needed = False
        self.telegram = TelegramCoordinator(self)
        self.single_runner = SingleMeasurementRunner(self)
        self.pulsed_runner = PulsedMeasurementRunner(self)
        self.special_runner = SpecialMeasurementRunner(self)
        self._last_combined_summary_path: Optional[str] = None
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
        # Shared persistence helper with updated default storage root
        self.default_save_root = self._resolve_default_save_root()
        self.data_saver = MeasurementDataSaver(default_base=self.default_save_root)
        # Instrument connection manager (handles SMU/PSU/temp lifecycles)
        self.connections = InstrumentConnectionManager(status_logger=self.log_terminal)


        # Load custom sweeps from JSON
        self.custom_sweeps = self.load_custom_sweeps(str(_PROJECT_ROOT / "Json_Files" / "Custom_Sweeps.json"))
        self.test_names = list(self.custom_sweeps.keys())
        self.code_names = {name: self.custom_sweeps[name].get("code_name") for name in self.test_names}

        # Initialize system configurations
        self.system_configs = {}
        self.systems = self.load_systems()

        # === NEW MODERN LAYOUT INITIALIZATION ===
        # Create layout builder with callbacks
        self.layout_builder = MeasurementGUILayoutBuilder(
            gui=self,
            callbacks={
                "connect_keithley": self.connect_keithley,
                "connect_psu": self.connect_keithley_psu,
                "connect_temp": self.reconnect_temperature_controller,
                "measure_one_device": self.measure_one_device,
                "on_system_change": self.on_system_change,
                "load_system": self.load_system,
                "save_system": self.save_system,
                "on_custom_save_toggle": self._on_custom_save_toggle,
                "browse_save": self._browse_save_location,
                "open_motor_control": self.open_motor_control,
                "check_connection": self.check_connection,
                "start_manual_endurance": self.start_manual_endurance,
                "start_manual_retention": self.start_manual_retention,
                "toggle_manual_led": self.toggle_manual_led,
                "start_custom_measurement_thread": self._start_custom_measurement_thread,
                "toggle_custom_pause": self._toggle_custom_pause,
                "open_sweep_editor": self.open_sweep_editor_popup,
                "start_sequential_measurement": self._start_sequential_measurement_thread,
                "stop_sequential_measurement": self.set_measurment_flag_true,
                "update_messaging_info": getattr(self, "update_messaging_info", None),
            },
        )
        
        # Build the modern tabbed layout
        self.layout_builder.build_modern_layout(self.master)
        
        # Set default system
        self.set_default_system()
        
        # Create sweep parameters section (will populate the collapsible frame)
        if hasattr(self, 'sweep_parameters_frame'):
            self.create_sweep_parameters(self.sweep_parameters_frame)
        
        # Create automated tests section (for advanced tests tab)
        # This will be called later when needed
        
        # Initialize plot panels with modern layout
        self.plot_panels = MeasurementPlotPanels(
            font_config={"axis": self.axis_font_size, "title": self.title_font_size}
        )
        
        # Create plots in the measurements tab graph panel
        if hasattr(self, 'measurements_graph_panel'):
            self.plot_panels.create_all_plots_modern(
                self.measurements_graph_panel, 
                temp_enabled=self.itc_connected
            )
        
        # Attach plot attributes to self for backwards compatibility
        self.plot_panels.attach_to(self)
        
        # Set up context menus for quick notes on all plot canvases
        if hasattr(self, 'layout_builder'):
            self.layout_builder._setup_plot_context_menus(self)
        
        # Start plot updaters
        self.plot_updaters = PlotUpdaters(gui=self, plot_panels=self.plot_panels)
        self.plot_updaters.start_all_threads()
        self.plot_updaters.start_temperature_thread(self.itc_connected)
        
        # Update overlay with initial device info
        if hasattr(self.plot_panels, 'update_overlay'):
            self.plot_panels.update_overlay(
                sample_name=self.sample_name_var.get() if hasattr(self, 'sample_name_var') else "—",
                device=self.device_section_and_number,
                voltage="0V",
                loop="#1"
            )

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

        try:
            if hasattr(self, "plot_updaters"):
                self.plot_updaters.stop_all_threads()
        except Exception:
            pass

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

    def load_custom_sweeps(self, path: str) -> Dict[str, Dict[str, Any]]:
        """Load custom measurement definitions from JSON (backward compatible)."""
        file_path = Path(path)
        if not file_path.exists():
            print(f"[Custom Sweeps] Config not found at {file_path}, using defaults.")
            return {}
        try:
            with file_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception as exc:
            print(f"[Custom Sweeps] Failed to load {file_path}: {exc}")
            return {}
        if not isinstance(data, dict):
            print(f"[Custom Sweeps] Invalid format in {file_path}; expected object at top level.")
            return {}
        return data

    def load_messaging_data(self) -> None:
        """Populate Telegram messaging metadata (names, token/chat IDs)."""
        config_path = _PROJECT_ROOT / "Json_Files" / "messaging_data.json"
        self.messaging_profiles: Dict[str, Dict[str, str]] = {}
        self.names: List[str] = []
        try:
            with config_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except FileNotFoundError:
            data = {}
        except Exception as exc:
            print(f"[Messaging] Failed to load config: {exc}")
            data = {}

        if isinstance(data, dict):
            for raw_name, raw_info in data.items():
                if not isinstance(raw_info, dict):
                    continue
                name = str(raw_name)
                token = str(raw_info.get("token", "") or "")
                chatid = str(raw_info.get("chatid", raw_info.get("chat_id", "")) or "")
                self.messaging_profiles[name] = {"token": token, "chatid": chatid}

        self.names = sorted(self.messaging_profiles.keys())
        default_name = self.names[0] if self.names else ""
        profile = self.messaging_profiles.get(default_name, {})

        self.token_var = profile.get("token", "")
        self.chatid_var = profile.get("chatid", "")
        self.get_messaged_var = 0
        self._selected_messaging_user = default_name

    def update_messaging_info(self, _event: Optional[Any] = None) -> None:
        """Update token/chat ID when the operator selects a different profile."""
        selection = ""
        try:
            selected = getattr(self, "selected_user", None)
            if isinstance(selected, tk.StringVar):
                selection = selected.get()
            elif isinstance(selected, str):
                selection = selected
        except Exception:
            selection = ""

        if not selection:
            selection = getattr(self, "_selected_messaging_user", "") or ""

        profile = self.messaging_profiles.get(selection)
        if not profile:
            return

        self._selected_messaging_user = selection
        token = profile.get("token", "")
        chatid = profile.get("chatid", "")

        if hasattr(self, "token_var") and hasattr(self.token_var, "set"):
            self.token_var.set(token)
        else:
            self.token_var = token

        if hasattr(self, "chatid_var") and hasattr(self.chatid_var, "set"):
            self.chatid_var.set(chatid)
        else:
            self.chatid_var = chatid

        if hasattr(self, "telegram"):
            self.telegram.reset_credentials()

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
        info_frame.columnconfigure([0, 1, 2, 3, 4], weight=1)

        # Device
        self.device_label = tk.Label(info_frame, text="Device: XYZ", font=("Helvetica", 12))
        self.device_label.grid(row=1, column=0, padx=10, sticky="w")

        # Voltage
        self.voltage_label = tk.Label(info_frame, text="Voltage: 1.23 V", font=("Helvetica", 12))
        self.voltage_label.grid(row=1, column=1, padx=10, sticky="w")

        # Loop
        self.loop_label = tk.Label(info_frame, text="Loop: 5", font=("Helvetica", 12))
        self.loop_label.grid(row=1, column=2, padx=10, sticky="w")

        # Motor Control button
        self.motor_control_button = tk.Button(info_frame, text="Motor Control", command=self.open_motor_control)
        self.motor_control_button.grid(row=1, column=3, columnspan=1, pady=5)

        # Check connection button
        self.check_connection_button = tk.Button(info_frame, text="check_connection", command=self.check_connection)
        self.check_connection_button.grid(row=1, column=4, columnspan=1, pady=5)

        # Start periodic status updates for device/voltage/loop
        self._status_updates_active = True
        self.master.after(250, self._status_update_tick)

    def set_status_message(self, message: str) -> None:
        """Update the window title and terminal log with the latest status."""
        previous = getattr(self, "_status_message", "")
        if message == previous:
            return
        self._status_message = message
        try:
            base = getattr(self, "_base_title", "Measurement Setup")
            title = base if not message else f"{base} - {message}"
            self.master.title(title)
        except Exception:
            pass
        if message and message != previous:
            try:
                self.log_terminal(message)
            except Exception:
                print(message)

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
                    self.display_index_section_number = f"{self.device_section_and_number} ({self.current_device})"
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
        if not _HAS_TEST_FRAMEWORK or not callable(load_thresholds):
            messagebox.showinfo(
                "Test Preferences",
                "Automated test framework is not installed; thresholds unavailable.",
            )
            return
        try:
            t = load_thresholds()
        except Exception as exc:  # pragma: no cover - optional dependency
            messagebox.showerror(
                "Test Preferences",
                f"Unable to load thresholds: {exc}",
            )
            return
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
            if PMUTestingGUI is not None:
                self.pmu_btn = tk.Button(
                    frame,
                    text="PMU Testing",
                    command=lambda: PMUTestingGUI(self.master, provider=self),
                )
            else:
                raise RuntimeError("PMU_Testing_GUI module not available")

            self.pmu_btn.grid(row=0, column=1, padx=(5, 5), pady=(2, 2), sticky='w')
            print("importing PMU_Testing_GUI completed")
        except Exception:
            print("promblem with pmu testing gui")
            # If import fails, keep UI functional without PMU
            self.pmu_btn = tk.Button(
                frame,
                text="PMU Testing (unavailable)",
                state=tk.DISABLED,
            )
            self.pmu_btn.grid(row=0, column=1, padx=(5, 5), pady=(2, 2), sticky='w')
        
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

    def graphs_all(self, parent: tk.Misc) -> None:
        """Legacy wrapper retained for backward compatibility."""
        self.plot_panels.create_all_sweeps_plots(parent)
        self.plot_panels.attach_to(self)

    def graphs_vi_logiv(self, parent: tk.Misc) -> None:
        """Legacy wrapper retained for backward compatibility (no-op)."""
        self.plot_panels.attach_to(self)
        self._start_plot_threads()

    def graphs_endurance_retention(self, parent: tk.Misc) -> None:
        """Legacy wrapper retained for backward compatibility."""
        self.plot_panels.create_endurance_retention_plots(parent)
        self.plot_panels.attach_to(self)

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

    def _start_custom_measurement_thread(self) -> None:
        """Start the custom measurement workflow in a background thread."""
        try:
            if getattr(self, "measurement_thread", None) and self.measurement_thread.is_alive():
                return
        except Exception:
            pass

        self.measurement_thread = threading.Thread(target=self.run_custom_measurement, daemon=True)
        self.measurement_thread.start()

    def _toggle_custom_pause(self) -> bool:
        """Toggle pause state for custom measurement; returns new pause flag."""
        self.pause_requested = not getattr(self, "pause_requested", False)
        return self.pause_requested

    def _start_sequential_measurement_thread(self) -> None:
        """Start the sequential measurement workflow in a background thread."""
        try:
            if getattr(self, "measurement_thread", None) and self.measurement_thread.is_alive():
                messagebox.showwarning("Measurement", "A measurement is already running.")
                return
        except Exception:
            pass

        self.measurement_thread = threading.Thread(target=self.sequential_measure, daemon=True)
        self.measurement_thread.start()

    def start_manual_endurance(self) -> None:
        bw_start_manual_endurance(self)

    def start_manual_retention(self) -> None:
        bw_start_manual_retention(self)

    def graphs_current_time_rt(self, parent: tk.Misc) -> None:
        """Legacy wrapper retained for backward compatibility."""
        self.plot_panels.create_current_time_plot(parent)
        self.plot_panels.attach_to(self)
        self._start_plot_threads()

    def graphs_resistance_time_rt(self, parent: tk.Misc) -> None:
        """Legacy wrapper retained for backward compatibility (no-op)."""
        self.plot_panels.attach_to(self)
        self._start_plot_threads()

    def graphs_temp_time_rt(self, parent: tk.Misc) -> None:
        """Legacy wrapper retained for backward compatibility."""
        self.plot_panels.create_temp_time_plot(parent, temp_enabled=self.itc_connected)
        self.plot_panels.attach_to(self)
        self._start_temperature_thread()

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
        if MeasurementPlotter is None:
            messagebox.showinfo(
                "Plotter",
                "MeasurementPlotter module is not available on this installation.",
            )
            return
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
        config_file = str(_PROJECT_ROOT / "Json_Files" / "system_configs.json")

        try:
            with open(config_file, 'r') as f:
                self.system_configs = json.load(f)
            return list(self.system_configs.keys())
        except (FileNotFoundError, json.JSONDecodeError):
            return ["No systems available"]

    def load_system(self) -> None:
        """Load the selected system configuration and populate all fields"""
        selected_system = getattr(self, 'system_var', None)
        if not selected_system:
            return
        
        system_name = selected_system.get() if hasattr(selected_system, 'get') else str(selected_system)
        if not system_name or system_name == "No systems available":
            return
        
        if not hasattr(self, 'system_configs') or system_name not in self.system_configs:
            # Reload systems
            self.load_systems()
            if system_name not in self.system_configs:
                messagebox.showwarning("System Not Found", f"System '{system_name}' not found in configuration file.")
                return
        
        config = self.system_configs[system_name]
        
        # Update SMU section
        smu_type = config.get("SMU Type", "")
        smu_address = config.get("SMU_address", "")
        if hasattr(self, 'smu_type_var'):
            self.smu_type_var.set(smu_type)
        if hasattr(self, 'keithley_address_var'):
            self.keithley_address_var.set(smu_address)
        # Ensure address is in combobox values if using combobox
        if hasattr(self, 'iv_address_combo') and smu_address:
            current_values = list(self.iv_address_combo['values'])
            if smu_address not in current_values:
                self.iv_address_combo['values'] = tuple([smu_address] + list(current_values))
        self.SMU_type = smu_type
        self.keithley_address = smu_address
        self.iv_address = smu_address
        
        # Update PSU section
        psu_type = config.get("psu_type", "None")
        psu_address = config.get("psu_address", "")
        if hasattr(self, 'psu_type_var'):
            self.psu_type_var.set(psu_type if psu_type else "None")
        if hasattr(self, 'psu_address_var'):
            self.psu_address_var.set(psu_address)
        # Ensure address is in combobox values if using combobox
        if hasattr(self, 'psu_address_combo') and psu_address:
            current_values = list(self.psu_address_combo['values'])
            if psu_address not in current_values:
                self.psu_address_combo['values'] = tuple([psu_address] + list(current_values))
        self.psu_visa_address = psu_address
        
        # Update Temp section
        temp_type = config.get("temp_controller", "Auto-Detect")
        temp_address = config.get("temp_address", "")
        if hasattr(self, 'temp_type_var'):
            self.temp_type_var.set(temp_type if temp_type else "Auto-Detect")
        if hasattr(self, 'temp_address_var'):
            self.temp_address_var.set(temp_address)
        # Ensure address is in combobox values if using combobox
        if hasattr(self, 'temp_address_combo') and temp_address:
            current_values = list(self.temp_address_combo['values'])
            if temp_address not in current_values:
                self.temp_address_combo['values'] = tuple([temp_address] + list(current_values))
        self.temp_controller_type = temp_type
        self.temp_controller_address = temp_address
        self.controller_type = temp_type or "Auto-Detect"
        self.controller_address = temp_address
        
        # Update optical section
        optical_config = config.get("optical")
        if optical_config and hasattr(self, 'optical_type_var'):
            opt_type = optical_config.get("type", "None")
            self.optical_type_var.set(opt_type)
            
            # Expand optical section if configured
            if opt_type != "None" and hasattr(self, 'optical_config_frame'):
                if hasattr(self, 'optical_expanded_var') and not self.optical_expanded_var.get():
                    if hasattr(self, 'optical_toggle_button'):
                        self.layout_builder._toggle_optical_section(self, self.optical_config_frame, self.optical_toggle_button)
            
            if opt_type == "LED":
                if hasattr(self, 'optical_led_units_var'):
                    self.optical_led_units_var.set(optical_config.get("units", "mA"))
                if hasattr(self, 'optical_led_channels_var'):
                    channels = optical_config.get("channels", {})
                    channels_str = ",".join([f"{k}:{v}" for k, v in channels.items()])
                    self.optical_led_channels_var.set(channels_str)
                limits = optical_config.get("limits", {})
                if hasattr(self, 'optical_led_min_var'):
                    self.optical_led_min_var.set(str(limits.get("min", "0.0")))
                if hasattr(self, 'optical_led_max_var'):
                    self.optical_led_max_var.set(str(limits.get("max", "30.0")))
                defaults = optical_config.get("defaults", {})
                if hasattr(self, 'optical_led_default_channel_var'):
                    self.optical_led_default_channel_var.set(defaults.get("channel", "380nm"))
                # Update UI
                if hasattr(self, 'optical_config_frame'):
                    self.layout_builder._update_optical_ui(self, self.optical_config_frame)
                    
            elif opt_type == "Laser":
                if hasattr(self, 'optical_laser_driver_var'):
                    self.optical_laser_driver_var.set(optical_config.get("driver", "Oxxius"))
                if hasattr(self, 'optical_laser_address_var'):
                    self.optical_laser_address_var.set(optical_config.get("address", "COM4"))
                if hasattr(self, 'optical_laser_baud_var'):
                    self.optical_laser_baud_var.set(str(optical_config.get("baud", "19200")))
                if hasattr(self, 'optical_laser_units_var'):
                    self.optical_laser_units_var.set(optical_config.get("units", "mW"))
                if hasattr(self, 'optical_laser_wavelength_var'):
                    self.optical_laser_wavelength_var.set(str(optical_config.get("wavelength_nm", "405")))
                limits = optical_config.get("limits", {})
                if hasattr(self, 'optical_laser_min_var'):
                    self.optical_laser_min_var.set(str(limits.get("min", "0.0")))
                if hasattr(self, 'optical_laser_max_var'):
                    self.optical_laser_max_var.set(str(limits.get("max", "10.0")))
                # Update UI
                if hasattr(self, 'optical_config_frame'):
                    self.layout_builder._update_optical_ui(self, self.optical_config_frame)
        elif hasattr(self, 'optical_type_var'):
            self.optical_type_var.set("None")
        
        # Try to create optical object
        try:
            self.optical = create_optical_from_system_config(config)
        except Exception:
            self.optical = None
        
        # Removed "System Loaded Successfully" popup - it's misleading since connection hasn't been tested
    
    def save_system(self) -> None:
        """Save current configuration as a new system"""
        # Get system name from user
        system_name = simpledialog.askstring("Save System", "Enter system name:")
        if not system_name:
            return
        
        # Build configuration dictionary
        config = {}
        
        # SMU configuration
        if hasattr(self, 'smu_type_var'):
            config["SMU Type"] = self.smu_type_var.get()
        elif hasattr(self, 'SMU_type'):
            config["SMU Type"] = self.SMU_type
        else:
            config["SMU Type"] = "Keithley 2401"
        
        if hasattr(self, 'keithley_address_var'):
            config["SMU_address"] = self.keithley_address_var.get()
        elif hasattr(self, 'keithley_address'):
            config["SMU_address"] = self.keithley_address
        else:
            config["SMU_address"] = ""
        
        # PSU configuration
        if hasattr(self, 'psu_type_var'):
            psu_type = self.psu_type_var.get()
            if psu_type and psu_type != "None":
                config["psu_type"] = psu_type
                if hasattr(self, 'psu_address_var'):
                    config["psu_address"] = self.psu_address_var.get()
                elif hasattr(self, 'psu_visa_address'):
                    config["psu_address"] = self.psu_visa_address
                else:
                    config["psu_address"] = ""
        
        # Temperature controller configuration
        if hasattr(self, 'temp_type_var'):
            temp_type = self.temp_type_var.get()
            if temp_type and temp_type != "None" and temp_type != "Auto-Detect":
                config["temp_controller"] = temp_type
                if hasattr(self, 'temp_address_var'):
                    config["temp_address"] = self.temp_address_var.get()
                elif hasattr(self, 'temp_controller_address'):
                    config["temp_address"] = self.temp_controller_address
                else:
                    config["temp_address"] = ""
        
        # Optical configuration
        if hasattr(self, 'optical_type_var'):
            opt_type = self.optical_type_var.get()
            if opt_type and opt_type != "None":
                optical_config = {"type": opt_type}
                
                if opt_type == "LED":
                    if hasattr(self, 'optical_led_units_var'):
                        optical_config["units"] = self.optical_led_units_var.get()
                    else:
                        optical_config["units"] = "mA"
                    
                    # Parse channels string
                    if hasattr(self, 'optical_led_channels_var'):
                        channels_str = self.optical_led_channels_var.get()
                        channels = {}
                        for pair in channels_str.split(','):
                            if ':' in pair:
                                key, val = pair.strip().split(':', 1)
                                try:
                                    channels[key] = int(val)
                                except ValueError:
                                    pass
                        optical_config["channels"] = channels
                    
                    # Limits
                    limits = {}
                    if hasattr(self, 'optical_led_min_var'):
                        try:
                            limits["min"] = float(self.optical_led_min_var.get())
                        except ValueError:
                            limits["min"] = 0.0
                    if hasattr(self, 'optical_led_max_var'):
                        try:
                            limits["max"] = float(self.optical_led_max_var.get())
                        except ValueError:
                            limits["max"] = 30.0
                    optical_config["limits"] = limits
                    
                    # Defaults
                    defaults = {}
                    if hasattr(self, 'optical_led_default_channel_var'):
                        defaults["channel"] = self.optical_led_default_channel_var.get()
                    optical_config["defaults"] = defaults
                    
                elif opt_type == "Laser":
                    if hasattr(self, 'optical_laser_driver_var'):
                        optical_config["driver"] = self.optical_laser_driver_var.get()
                    else:
                        optical_config["driver"] = "Oxxius"
                    
                    if hasattr(self, 'optical_laser_address_var'):
                        optical_config["address"] = self.optical_laser_address_var.get()
                    else:
                        optical_config["address"] = "COM4"
                    
                    if hasattr(self, 'optical_laser_baud_var'):
                        try:
                            optical_config["baud"] = int(self.optical_laser_baud_var.get())
                        except ValueError:
                            optical_config["baud"] = 19200
                    else:
                        optical_config["baud"] = 19200
                    
                    if hasattr(self, 'optical_laser_units_var'):
                        optical_config["units"] = self.optical_laser_units_var.get()
                    else:
                        optical_config["units"] = "mW"
                    
                    if hasattr(self, 'optical_laser_wavelength_var'):
                        try:
                            optical_config["wavelength_nm"] = int(self.optical_laser_wavelength_var.get())
                        except ValueError:
                            optical_config["wavelength_nm"] = 405
                    else:
                        optical_config["wavelength_nm"] = 405
                    
                    # Limits
                    limits = {}
                    if hasattr(self, 'optical_laser_min_var'):
                        try:
                            limits["min"] = float(self.optical_laser_min_var.get())
                        except ValueError:
                            limits["min"] = 0.0
                    if hasattr(self, 'optical_laser_max_var'):
                        try:
                            limits["max"] = float(self.optical_laser_max_var.get())
                        except ValueError:
                            limits["max"] = 10.0
                    optical_config["limits"] = limits
                    
                    # Defaults
                    defaults = {}
                    if hasattr(self, 'optical_laser_min_var'):
                        try:
                            defaults["level"] = float(self.optical_laser_min_var.get())
                        except ValueError:
                            defaults["level"] = 0.6
                    optical_config["defaults"] = defaults
                
                config["optical"] = optical_config
        
        # Load existing configs
        config_file = str(_PROJECT_ROOT / "Json_Files" / "system_configs.json")
        try:
            with open(config_file, 'r') as f:
                all_configs = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            all_configs = {}
        
        # Add/update system
        all_configs[system_name] = config
        
        # Save to file
        try:
            with open(config_file, 'w') as f:
                json.dump(all_configs, f, indent=4)
            
            # Update local configs
            self.system_configs = all_configs
            
            # Update system combo
            if hasattr(self, 'system_combo'):
                systems = list(all_configs.keys())
                self.system_combo['values'] = systems
                self.system_var.set(system_name)
            
            messagebox.showinfo("System Saved", f"System '{system_name}' saved successfully.")
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save system: {e}")
    
    def on_system_change(self, selected_system: str) -> None:
        """Update addresses when system selection changes (legacy method)"""
        if selected_system in self.system_configs:
            config = self.system_configs[selected_system]

            # Update IV section
            iv_address = config.get("SMU_address", "")
            self.iv_address = iv_address
            if hasattr(self, 'keithley_address_var'):
                self.keithley_address_var.set(iv_address)
            self.keithley_address = iv_address
            self.update_component_state("iv", iv_address)

            # Update PSU section
            psu_address = config.get("psu_address", "")
            if hasattr(self, 'psu_address_var'):
                self.psu_address_var.set(psu_address)
            self.psu_visa_address = psu_address
            self.update_component_state("psu", psu_address)

            # Update Temp section
            temp_address = config.get("temp_address", "")
            if hasattr(self, 'temp_address_var'):
                self.temp_address_var.set(temp_address)
            self.temp_controller_address = temp_address
            self.update_component_state("temp", temp_address)

            # updater controller type
            self.temp_controller_type = config.get("temp_controller", "")
            self.controller_type = self.temp_controller_type or "Auto-Detect"
            self.controller_address = temp_address or self.temp_controller_address

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

        # Build components list - labels may not exist in modern layout
        if component_type == "iv":
            label = getattr(self, "iv_label", None)
            entry = getattr(self, "iv_address_entry", None)
            button = getattr(self, "iv_connect_button", None)
        elif component_type == "psu":
            label = getattr(self, "psu_label", None)
            entry = getattr(self, "psu_address_entry", None)
            button = getattr(self, "psu_connect_button", None)
        elif component_type == "temp":
            label = getattr(self, "temp_label", None)
            entry = getattr(self, "temp_address_entry", None)
            button = getattr(self, "temp_connect_button", None)
        else:
            return

        # Skip if required components don't exist
        if entry is None or button is None:
            return

        # Update label color if it exists
        if label is not None:
            if has_address:
                label.configure(fg="black")
            else:
                label.configure(fg="grey")

        # Update entry state
        # Check if it's a ttk widget (ttk widgets don't support bg/fg options)
        # Ttk widgets have class names starting with "T" (e.g., "TEntry", "TCombobox")
        # Regular tk widgets have class names without "T" prefix (e.g., "Entry", "Button")
        widget_class = entry.winfo_class()
        is_ttk_widget = widget_class.startswith("T")
        
        try:
            if has_address:
                if is_ttk_widget:
                    entry.configure(state="normal")
                else:
                    entry.configure(state="normal", bg="white", fg="black")
            else:
                if is_ttk_widget:
                    entry.configure(state="disabled")
                else:
                    entry.configure(state="disabled", bg="lightgrey", fg="grey")
        except Exception:
            # Fallback: if bg/fg options aren't supported, just update state
            entry.configure(state="normal" if has_address else "disabled")

        # Update button state
        if has_address:
            button.configure(state="normal")
        else:
            button.configure(state="disabled")
    def create_mode_selection(self,parent: tk.Misc) -> None:
        """Legacy wrapper retained for backward compatibility."""
        pass

    def create_sweep_parameters(self, parent: tk.Misc) -> None:
        """Sweep parameter section - no frame wrapper, uses parent directly"""
        # Use parent directly - it's already the content frame from collapsible section
        frame = parent

        # Measurement Type selector (DC Triangle IV, SMU_AND_PMU pulse modes, etc.)
        tk.Label(frame, text="Measurement Type:", bg='#f0f0f0').grid(row=0, column=0, sticky="w", pady=2)
        self.excitation_var = tk.StringVar(value="DC Triangle IV")
        self.excitation_menu = ttk.Combobox(frame, textvariable=self.excitation_var,
                                            values=["DC Triangle IV",
                                                    "Endurance",
                                                    "Retention",
                                                    "Pulsed IV <1.5V",
                                                    "Pulsed IV >1.5V",
                                                    "Fast Pulses",
                                                    "Fast Hold",
                                                    "ISPP",
                                                    "Pulse Width Sweep",
                                                    "Threshold Search",
                                                    "Transient Decay"], state="readonly")
        self.excitation_menu.grid(row=0, column=1, sticky="ew")

        # Source Mode Selection (placed right after measurement type)
        tk.Label(frame, text="Source Mode:", font=("Arial", 9, "bold"), bg='#f0f0f0').grid(row=1, column=0, sticky="w")
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
        exc_dyn = tk.Frame(frame, bg='#f0f0f0')
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
        # Cyclical IV Sweep (4200A-specific)
        self.cyclical_vpos = tk.DoubleVar(value=2.0)      # Positive voltage (V)
        self.cyclical_vneg = tk.DoubleVar(value=0.0)      # Negative voltage (V), 0 = auto-symmetric
        self.cyclical_num_cycles = tk.IntVar(value=1)     # Number of cycles (1-1000)
        self.cyclical_settle_time = tk.DoubleVar(value=0.001)  # Settling time (s), default 1ms
        self.cyclical_ilimit = tk.DoubleVar(value=0.1)    # Current limit (A), default 0.1A
        self.cyclical_integration_time = tk.DoubleVar(value=0.01)  # Integration time (PLC), default 0.01
        self.cyclical_debug = tk.BooleanVar(value=True)   # Debug output (default ON)

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
                tk.Label(self._excitation_params_frame, text="Triangle IV sweep (FS/PS/NS).", fg="grey", bg='#f0f0f0').grid(row=r, column=0, columnspan=2, sticky="w"); r+=1
                # Sweep Mode
                tk.Label(self._excitation_params_frame, text="Sweep Mode:", bg='#f0f0f0').grid(row=r, column=0, sticky="w")
                sweep_mode_menu = ttk.Combobox(self._excitation_params_frame, textvariable=self.sweep_mode_var,
                                               values=[VoltageRangeMode.FIXED_STEP,
                                                       VoltageRangeMode.FIXED_SWEEP_RATE,
                                                       VoltageRangeMode.FIXED_VOLTAGE_TIME], state="readonly")
                sweep_mode_menu.grid(row=r, column=1, sticky="ew"); r+=1
                # Sweep Type directly below
                tk.Label(self._excitation_params_frame, text="Sweep Type:", bg='#f0f0f0').grid(row=r, column=0, sticky="w")
                # Get current SMU type to conditionally show CYCLICAL option
                smu_type = getattr(self, 'SMU_type', 'Keithley 2401')
                sweep_type_values = ["FS", "PS", "NS"]
                if smu_type == 'Keithley 4200A':
                    sweep_type_values.append("CYCLICAL")  # Add cyclical option for 4200A only
                sweep_type_menu = ttk.Combobox(self._excitation_params_frame, textvariable=self.sweep_type_var,
                                               values=sweep_type_values, state="readonly")
                sweep_type_menu.grid(row=r, column=1, sticky="ew"); r+=1
                
                # Cyclical-specific parameters (shown when sweep_type is CYCLICAL)
                self._cyclical_params_frame = tk.Frame(self._excitation_params_frame, bg='#f0f0f0')
                def update_cyclical_params_visibility(*_):
                    sweep_type = self.sweep_type_var.get()
                    if sweep_type == "CYCLICAL":
                        # Show cyclical parameters
                        self._cyclical_params_frame.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(5,0))
                        render_cyclical_params()
                    else:
                        # Hide cyclical parameters
                        self._cyclical_params_frame.grid_remove()
                
                def render_cyclical_params():
                    # Clear existing widgets
                    for w in list(self._cyclical_params_frame.children.values()):
                        try: w.destroy()
                        except Exception: pass
                    
                    cr = 0
                    tk.Label(self._cyclical_params_frame, text="Cyclical Sweep Parameters (4200A):", font=("Arial", 8, "bold"), bg='#f0f0f0', fg='blue').grid(row=cr, column=0, columnspan=2, sticky="w"); cr+=1
                    tk.Label(self._cyclical_params_frame, text="Pattern: (0V → +Vpos → Vneg → 0V) × NumCycles", fg="grey", bg='#f0f0f0', font=("Arial", 7)).grid(row=cr, column=0, columnspan=2, sticky="w"); cr+=1
                    tk.Label(self._cyclical_params_frame, text="Vpos (V):", bg='#f0f0f0').grid(row=cr, column=0, sticky="w")
                    tk.Entry(self._cyclical_params_frame, textvariable=self.cyclical_vpos, width=10).grid(row=cr, column=1, sticky="w"); cr+=1
                    tk.Label(self._cyclical_params_frame, text="Vneg (V, 0=auto-symmetric):", bg='#f0f0f0').grid(row=cr, column=0, sticky="w")
                    tk.Entry(self._cyclical_params_frame, textvariable=self.cyclical_vneg, width=10).grid(row=cr, column=1, sticky="w"); cr+=1
                    tk.Label(self._cyclical_params_frame, text="Num Cycles:", bg='#f0f0f0').grid(row=cr, column=0, sticky="w")
                    tk.Entry(self._cyclical_params_frame, textvariable=self.cyclical_num_cycles, width=10).grid(row=cr, column=1, sticky="w"); cr+=1
                    tk.Label(self._cyclical_params_frame, text="Settle Time (s):", bg='#f0f0f0').grid(row=cr, column=0, sticky="w")
                    tk.Entry(self._cyclical_params_frame, textvariable=self.cyclical_settle_time, width=10).grid(row=cr, column=1, sticky="w"); cr+=1
                    tk.Label(self._cyclical_params_frame, text="I Limit (A):", bg='#f0f0f0').grid(row=cr, column=0, sticky="w")
                    tk.Entry(self._cyclical_params_frame, textvariable=self.cyclical_ilimit, width=10).grid(row=cr, column=1, sticky="w"); cr+=1
                    tk.Label(self._cyclical_params_frame, text="Integration Time (PLC):", bg='#f0f0f0').grid(row=cr, column=0, sticky="w")
                    tk.Entry(self._cyclical_params_frame, textvariable=self.cyclical_integration_time, width=10).grid(row=cr, column=1, sticky="w"); cr+=1
                    tk.Label(self._cyclical_params_frame, text="Debug Output:", bg='#f0f0f0').grid(row=cr, column=0, sticky="w")
                    tk.Checkbutton(self._cyclical_params_frame, variable=self.cyclical_debug, bg='#f0f0f0').grid(row=cr, column=1, sticky="w"); cr+=1
                    
                    # Total points label (updates when cycles change)
                    def update_total_points(*_):
                        try:
                            cycles = self.cyclical_num_cycles.get()
                            total = cycles * 4
                            for widget in reversed(list(self._cyclical_params_frame.children.values())):
                                if isinstance(widget, tk.Label) and "Total points:" in widget.cget("text"):
                                    widget.config(text=f"Total points: {total} (4 × {cycles} cycles)")
                                    break
                        except Exception:
                            pass
                    
                    total_points_label = tk.Label(self._cyclical_params_frame, text=f"Total points: {self.cyclical_num_cycles.get() * 4} (4 × {self.cyclical_num_cycles.get()} cycles)", fg="grey", bg='#f0f0f0', font=("Arial", 7))
                    total_points_label.grid(row=cr, column=0, columnspan=2, sticky="w"); cr+=1
                    self.cyclical_num_cycles.trace_add("write", update_total_points)
                
                sweep_type_menu.bind("<<ComboboxSelected>>", update_cyclical_params_visibility)
                self.sweep_type_var.trace_add("write", update_cyclical_params_visibility)
                # Initial render
                update_cyclical_params_visibility()

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
                        self._dc_alt_lbl1 = tk.Label(frame, text="Sweep rate (V/s):", bg='#f0f0f0')
                        self._dc_alt_lbl1.grid(row=6, column=0, sticky="w")
                        self._dc_alt_ent1 = tk.Entry(frame, textvariable=self.var_sweep_rate)
                        self._dc_alt_ent1.grid(row=6, column=1, sticky="ew")
                        # Row 7: # Steps (optional)
                        self._dc_alt_lbl2 = tk.Label(frame, text="# Steps (optional):", bg='#f0f0f0')
                        self._dc_alt_lbl2.grid(row=7, column=0, sticky="w")
                        self._dc_alt_ent2 = tk.Entry(frame, textvariable=self.var_num_steps)
                        self._dc_alt_ent2.grid(row=7, column=1, sticky="ew")
                    elif mode == VoltageRangeMode.FIXED_VOLTAGE_TIME:
                        _toggle_dc_step_fields(False)
                        # Row 6: Total sweep time (s)
                        self._dc_alt_lbl1 = tk.Label(frame, text="Total sweep time (s):", bg='#f0f0f0')
                        self._dc_alt_lbl1.grid(row=6, column=0, sticky="w")
                        self._dc_alt_ent1 = tk.Entry(frame, textvariable=self.var_total_time)
                        self._dc_alt_ent1.grid(row=6, column=1, sticky="ew")
                        # Row 7: # Steps (optional)
                        self._dc_alt_lbl2 = tk.Label(frame, text="# Steps (optional):", bg='#f0f0f0')
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
            if sel == "Endurance":
                tk.Label(self._excitation_params_frame, text="Repeated SET/RESET pulses with readback.", fg="grey", bg='#f0f0f0').grid(row=r, column=0, columnspan=2, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="SET Voltage (V)", bg='#f0f0f0').grid(row=r, column=0, sticky="w")
                tk.Entry(self._excitation_params_frame, textvariable=self.end_set_v, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="RESET Voltage (V)", bg='#f0f0f0').grid(row=r, column=0, sticky="w")
                tk.Entry(self._excitation_params_frame, textvariable=self.end_reset_v, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Pulse Width (ms)", bg='#f0f0f0').grid(row=r, column=0, sticky="w")
                tk.Entry(self._excitation_params_frame, textvariable=self.end_pulse_ms, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Cycles", bg='#f0f0f0').grid(row=r, column=0, sticky="w")
                tk.Entry(self._excitation_params_frame, textvariable=self.end_cycles, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Read Voltage (V)", bg='#f0f0f0').grid(row=r, column=0, sticky="w")
                tk.Entry(self._excitation_params_frame, textvariable=self.end_read_v, width=10).grid(row=r, column=1, sticky="w"); r+=1
                try:
                    for w in self._dc_widgets:
                        try: w.grid_remove()
                        except Exception: pass
                except Exception:
                    pass
                return
            if sel == "Retention":
                tk.Label(self._excitation_params_frame, text="Measure state retention over time.", fg="grey", bg='#f0f0f0').grid(row=r, column=0, columnspan=2, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="SET Voltage (V)", bg='#f0f0f0').grid(row=r, column=0, sticky="w")
                tk.Entry(self._excitation_params_frame, textvariable=self.ret_set_v, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="SET Time (ms)", bg='#f0f0f0').grid(row=r, column=0, sticky="w")
                tk.Entry(self._excitation_params_frame, textvariable=self.ret_set_ms, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Read Voltage (V)", bg='#f0f0f0').grid(row=r, column=0, sticky="w")
                tk.Entry(self._excitation_params_frame, textvariable=self.ret_read_v, width=10).grid(row=r, column=1, sticky="w"); r+=1
                if not hasattr(self, "ret_measure_delay"):
                    self.ret_measure_delay = tk.DoubleVar(value=10.0)
                tk.Label(self._excitation_params_frame, text="Measure after (s)", bg='#f0f0f0').grid(row=r, column=0, sticky="w")
                tk.Entry(self._excitation_params_frame, textvariable=self.ret_measure_delay, width=14).grid(row=r, column=1, sticky="w"); r+=1
                try:
                    for w in self._dc_widgets:
                        try: w.grid_remove()
                        except Exception: pass
                except Exception:
                    pass
                return
            if sel == "Pulsed IV <1.5V":
                # Defaults tied to SMU_AND_PMU min pulse width and base 0.2 V
                try:
                    self.ex_piv_width_ms.set(_min_pulse_width_ms_default())
                except Exception:
                    pass
                tk.Label(self._excitation_params_frame, text="One pulse per amplitude, read at Vbase; plots A vs I.", fg="grey", bg='#f0f0f0').grid(row=r, column=0, columnspan=2, sticky="w"); r+=1
                # For pulse modes, hide DC sweep-mode/type, so nothing to render here
                tk.Label(self._excitation_params_frame, text="Vstart", bg='#f0f0f0').grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self.ex_piv_start, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Vstop", bg='#f0f0f0').grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self.ex_piv_stop, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Step (use or set #steps)", bg='#f0f0f0').grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self.ex_piv_step, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="#Steps (optional)", bg='#f0f0f0').grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self.ex_piv_nsteps, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Pulse width (ms)", bg='#f0f0f0').grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self.ex_piv_width_ms, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Vbase", bg='#f0f0f0').grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self.ex_piv_vbase, width=10).grid(row=r, column=1, sticky="w"); r+=1
                tk.Label(self._excitation_params_frame, text="Inter-step delay (s)", bg='#f0f0f0').grid(row=r, column=0, sticky="w"); tk.Entry(self._excitation_params_frame, textvariable=self.ex_piv_inter_delay, width=10).grid(row=r, column=1, sticky="w"); r+=1
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
            if sel == "Pulsed IV >1.5V":
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
            if sel == "Fast Pulses":
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
            if sel == "Fast Hold":
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

        temp_row = 29
        tk.Label(frame, text="Target Temp (°C):").grid(row=temp_row, column=0, sticky="w")
        self.target_temp_var = tk.DoubleVar(value=25.0)
        self.target_temp_entry = tk.Entry(frame, textvariable=self.target_temp_var, state="disabled")
        self.target_temp_entry.grid(row=temp_row, column=1, sticky="w")
        self.target_temp_button = tk.Button(frame, text="Set Temp", command=self.send_temp, state="disabled")
        self.target_temp_button.grid(row=temp_row, column=2, padx=(5, 0), sticky="w")

        def start_thread():
            self.measurement_thread = threading.Thread(target=self.start_measurement)
            self.measurement_thread.daemon = True
            self.measurement_thread.start()

        self.measure_button = tk.Button(frame, text="Start Measurement", command=start_thread)
        self.measure_button.grid(row=30, column=0, columnspan=1, pady=5)

        # stop button
        self.adaptive_button = tk.Button(frame, text="Stop Measurement!", command=self.set_measurment_flag_true)
        self.adaptive_button.grid(row=30, column=1, columnspan=1, pady=10)

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
        self.telegram.send_message("Automated tests started")
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
            if (
                MeasurementDriver is None
                or TestRunner is None
                or not callable(load_thresholds)
            ):
                self.test_log_queue.put(
                    "Automated test framework not available; skipping run."
                )
                return
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
                self.telegram.send_message(f"Testing {device}...")

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
                self.telegram.send_message(summary_line)
        except Exception as e:
            self.test_log_queue.put(f"Automated tests error: {e}")
        finally:
            self.tests_running = False
            self.telegram.send_message("Automated tests finished")

    def set_measurment_flag_true(self) -> None:
        self.stop_measurement_flag = True
    
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

    def reconnect_temperature_controller(self) -> None:
        """Reconnect temperature controller based on GUI selection."""
        controller_type = getattr(self, "controller_type", "Auto-Detect")
        if hasattr(self, "controller_type_var"):
            try:
                controller_type = self.controller_type_var.get()
            except Exception:
                controller_type = getattr(self, "controller_type", "Auto-Detect")
        address = getattr(self, "controller_address", self.temp_controller_address)
        if hasattr(self, "controller_address_var"):
            try:
                address = self.controller_address_var.get()
            except Exception:
                address = getattr(self, "controller_address", self.temp_controller_address)
        self.controller_type = controller_type or "Auto-Detect"
        self.controller_address = address

        # Close existing connection
        try:
            if self.temp_controller:
                self.temp_controller.close()
        except Exception:
            pass

        if controller_type == "Auto-Detect":
            self.temp_controller = self.connections.create_temperature_controller(auto_detect=True)
        elif controller_type == "None":
            self.temp_controller = self.connections.create_temperature_controller(auto_detect=False)
        else:
            if address == "Auto":
                default_addresses = {
                    "Lakeshore 335": "12",
                    "Oxford ITC4": "ASRL12::INSTR",
                }
                address = default_addresses.get(controller_type, "12")
            self.temp_controller = self.connections.create_temperature_controller(
                auto_detect=False,
                controller_type=controller_type,
                address=address,
            )

        self.update_controller_status()

    def reconnect_Kieithley_controller(self) -> None:
        """Reconnect temperature controller based on GUI selection."""
        self.reconnect_temperature_controller()

    def update_controller_status(self) -> None:
        """Update controller status indicator."""
        info = self.connections.get_temperature_info()
        label = getattr(self, "controller_status_label", None)
        entry = getattr(self, "target_temp_entry", None)
        btn = getattr(self, "target_temp_button", None)
        if label:
            if info:
                label.config(
                    text=f"● Connected: {info['type']}",
                    fg="green"
                )
            else:
                label.config(
                    text="● Disconnected",
                    fg="red"
                )
        state = "normal" if info else "disabled"
        if entry:
            entry.configure(state=state)
        if btn:
            btn.configure(state=state)

    def sequential_measure(self) -> None:
        """Delegate sequential measurement logic to the runner module."""
        run_sequential_measurement(self)

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
        cooperative abort. Results are saved per-sweep in the default `Data_folder`
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
        # Skip sample name check if custom save location is enabled (custom path takes priority)
        if not (self.use_custom_save_var.get() and self.custom_save_location):
            self.check_for_sample_name()

        selected_measurement = self.custom_measurement_var.get()
        # Reset any prior sweep edits from the popup for a fresh run
        try:
            self.sweep_runtime_overrides = {}
        except Exception:
            pass
        print(f"Running custom measurement: {selected_measurement}")

        if self.telegram.is_enabled():
            var = self.custom_measurement_var.get()
            sample_name = self.sample_name_var.get()
            section = self.device_section_and_number
            text = f"Starting Measurements on {sample_name} device {section} ({var})"
            self.telegram.send_message(text)

        if selected_measurement in self.custom_sweeps:
            if self.current_device in self.device_list:
                start_index = self.device_list.index(self.current_device)
            else:
                start_index = 0  # Default to the first device if current one is not found

            device_count = len(self.device_list)

            # looping through each device.
            for i in range(device_count):  # Ensure we process each device exactly once
                device = self.device_list[(start_index + i) % device_count]  # Wrap around when reaching the end

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
                        # Check if this is a cyclical sweep (4200A only)
                        if sweep_type == "CYCLICAL":
                            if KXCIClient is None or build_ex_command is None:
                                print("ERROR: Cyclical sweep requires KXCI client, but module is not available")
                                messagebox.showerror("Module Not Available", 
                                                    "Cyclical sweep requires the KXCI module.\n"
                                                    "Please ensure the 4200A C module is properly installed.")
                                continue
                            
                            smu_type = getattr(self, 'SMU_type', 'Keithley 2401')
                            if smu_type != 'Keithley 4200A':
                                print(f"ERROR: Cyclical sweep (CYCLICAL) is only available for Keithley 4200A, not {smu_type}")
                                messagebox.showerror("Invalid SMU Type", 
                                                    f"Cyclical sweep is only available for Keithley 4200A.\n"
                                                    f"Current SMU: {smu_type}\n"
                                                    f"Please change SMU type or select a different sweep type.")
                                continue
                            
                            # Get cyclical parameters from GUI variables or params
                            if hasattr(self, 'cyclical_vpos'):
                                vpos = self.cyclical_vpos.get()
                                vneg = self.cyclical_vneg.get()
                                num_cycles = self.cyclical_num_cycles.get()
                                settle_time = self.cyclical_settle_time.get()
                                ilimit = self.cyclical_ilimit.get()
                                integration_time = self.cyclical_integration_time.get()
                                debug = 1 if self.cyclical_debug.get() else 0
                            else:
                                # Fallback to params if GUI vars don't exist
                                vpos = float(params.get("vpos", stop_v if stop_v > 0 else 2.0))
                                vneg = float(params.get("vneg", 0.0))
                                num_cycles = int(params.get("num_cycles", 1))
                                settle_time = float(params.get("settle_time", step_delay if step_delay > 0 else 0.001))
                                ilimit = float(params.get("ilimit", icc_val if icc_val > 0 else 0.1))
                                integration_time = float(params.get("integration_time", 0.01))
                                debug = 1 if _is_truthy(params.get("debug", True)) else 0
                            
                            def _on_point(v, i, t_s):
                                self.v_arr_disp.append(v)
                                self.c_arr_disp.append(i)
                                self.t_arr_disp.append(t_s)
                            
                            # Execute cyclical sweep via 4200A system wrapper (manager pattern)
                            v_arr, c_arr, timestamps = self._run_cyclical_iv_sweep_via_manager(
                                vpos=vpos,
                                vneg=vneg,
                                num_cycles=num_cycles,
                                settle_time=settle_time,
                                ilimit=ilimit,
                                integration_time=integration_time,
                                debug=debug,
                                on_point=_on_point
                            )
                        else:
                            # Standard triangle IV sweep (FS/PS/NS)
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
                            voltage_range = self.measurement_service.compute_voltage_range(
                                start_v=start_v,
                                stop_v=stop_v,
                                step_v=step_v,
                                sweep_type=sweep_type,
                                mode=VoltageRangeMode.FIXED_STEP,
                                neg_stop_v=neg_stop_v_param,
                            )
                            
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
                        set_v = float(self.end_set_v.get())
                        reset_v = float(self.end_reset_v.get())
                        pulse_ms = float(self.end_pulse_ms.get())
                        cycles = int(self.end_cycles.get())
                        read_v = float(self.end_read_v.get())
                        
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
                        set_v = float(self.ret_set_v.get())
                        set_ms = float(self.ret_set_ms.get())
                        read_v = float(self.ret_read_v.get())
                        delay_s = float(self.ret_measure_delay.get())
                        times_s = [delay_s]
                        
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
                    save_dir = self._get_save_directory(self.sample_name_var.get(), 
                                                       self.final_device_letter, 
                                                       self.final_device_number)
                    
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

                    try:
                        np.savetxt(file_path, data, fmt="%0.3E\t%0.3E\t%0.3E", header="Voltage Current Time", comments="")
                        abs_path = os.path.abspath(file_path)
                        print(f"[SAVE] File saved to: {abs_path}")
                        self.log_terminal(f"File saved: {abs_path}")
                    except Exception as e:
                        print(f"[SAVE ERROR] Failed to save file: {e}")

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
                try:
                    self._save_summary_artifacts(save_dir)
                except Exception as exc:
                    print(f"[SAVE ERROR] Failed to save summary plots: {exc}")
                    self._last_combined_summary_path = None
                self.ax_all_iv.clear()
                self.ax_all_logiv.clear()
                self.keithley.enable_output(False)

                end = time.time()
                print("total time for ", selected_measurement, "=", end - start, " - ")

                self.data_saver.create_log_file(save_dir, start_time, selected_measurement)

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
            if self.telegram.is_enabled():
                combined = getattr(self, '_last_combined_summary_path', None)
                self.telegram.start_post_measurement_worker(save_dir, combined)
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

    def _get_4200a_system_wrapper(self):
        """Get or create a 4200A system wrapper instance for cyclical sweep.
        
        Returns:
            Keithley4200ASystem instance or None if not available
        
        Note:
            This method creates a temporary system wrapper instance that connects
            to the instrument. The caller is responsible for cleanup (disconnection).
        """
        try:
            from Pulse_Testing.systems.keithley4200a import Keithley4200ASystem
            
            # Get GPIB address from GUI
            gpib_address = getattr(self, 'keithley_address', None) or getattr(self, 'keithley_address_var', None)
            if gpib_address:
                if hasattr(gpib_address, 'get'):
                    gpib_address = gpib_address.get()
            else:
                gpib_address = "GPIB0::17::INSTR"  # Default
            
            # Create system wrapper instance
            system = Keithley4200ASystem()
            
            # Connect to instrument
            if system.connect(gpib_address, timeout=30.0):
                return system
            else:
                print(f"WARNING: Failed to connect 4200A system wrapper at {gpib_address}")
                return None
        except ImportError:
            print("WARNING: 4200A system wrapper not available (Pulse_Testing.systems.keithley4200a)")
            return None
        except Exception as e:
            print(f"WARNING: Failed to create 4200A system wrapper: {e}")
            return None
    
    def _run_cyclical_iv_sweep_via_manager(
        self,
        vpos: float,
        vneg: float,
        num_cycles: int,
        settle_time: float,
        ilimit: float,
        integration_time: float,
        debug: int,
        on_point: Optional[Callable[[float, float, float], None]] = None,
    ) -> Tuple[List[float], List[float], List[float]]:
        """Run cyclical IV sweep via 4200A system wrapper (manager pattern).
        
        This method uses the 4200A system wrapper which encapsulates the KXCI
        communication and provides a clean interface for the cyclical sweep.
        The wrapper uses SMU1 for measurements (correct channel).
        
        Args:
            vpos: Positive voltage (V)
            vneg: Negative voltage (V), 0 = auto-symmetric
            num_cycles: Number of cycles (1-1000)
            settle_time: Settling time at each voltage point (s)
            ilimit: Current compliance limit (A)
            integration_time: Measurement integration time (PLC)
            debug: Debug output flag (0 or 1)
            on_point: Optional callback for each data point (v, i, t)
        
        Returns:
            Tuple of (voltage_list, current_list, timestamp_list)
        """
        system = None
        try:
            # Get 4200A system wrapper
            system = self._get_4200a_system_wrapper()
            if system is None:
                raise RuntimeError("Failed to get 4200A system wrapper - ensure 4200A is selected and connected")
            
            # Execute cyclical sweep via system wrapper
            result = system.cyclical_iv_sweep(
                vpos=vpos,
                vneg=vneg,
                num_cycles=num_cycles,
                settle_time=settle_time,
                ilimit=ilimit,
                integration_time=integration_time,
                debug=debug,
            )
            
            # Extract data from result
            voltage = result.get('voltage', [])
            current = result.get('current', [])
            timestamps = result.get('timestamp', [])
            
            # Call on_point callback if provided
            if on_point is not None:
                for v, i, t in zip(voltage, current, timestamps):
                    if hasattr(self, 'stop_measurement_flag') and self.stop_measurement_flag:
                        break
                    try:
                        on_point(v, i, t)
                    except Exception as e:
                        print(f"Warning: on_point callback failed: {e}")
            
            return (voltage, current, timestamps)
            
        except Exception as e:
            error_msg = f"Cyclical IV sweep failed: {e}"
            print(f"ERROR: {error_msg}")
            messagebox.showerror("Cyclical IV Sweep Error", error_msg)
            return ([], [], [])
        finally:
            # Cleanup: disconnect system wrapper
            if system is not None:
                try:
                    system.disconnect()
                except Exception:
                    pass
    
    def _run_cyclical_iv_sweep_kxci(
        self,
        vpos: float,
        vneg: float,
        num_cycles: int,
        settle_time: float,
        ilimit: float,
        integration_time: float,
        debug: int,
        on_point: Optional[Callable[[float, float, float], None]] = None,
    ) -> Tuple[List[float], List[float], List[float]]:
        """
        Execute cyclical IV sweep using KXCI (Keithley 4200A only).
        
        Pattern: (0V → +Vpos → Vneg → 0V) × NumCycles
        Total points = 4 × NumCycles
        
        Args:
            vpos: Positive voltage (V)
            vneg: Negative voltage (V), 0 = auto-symmetric with -vpos
            num_cycles: Number of cycles to repeat
            settle_time: Settling time at each voltage point (s)
            ilimit: Current compliance limit (A)
            integration_time: Measurement integration time (PLC)
            debug: Debug output flag (0 or 1)
            on_point: Optional callback for each measurement point (v, i, t)
            
        Returns:
            Tuple of (voltage_array, current_array, timestamps)
        """
        # Get GPIB address from GUI
        gpib_address = getattr(self, 'keithley_address_var', None)
        if gpib_address is None or not hasattr(gpib_address, 'get'):
            gpib_address_str = getattr(self, 'keithley_address', 'GPIB0::17::INSTR')
        else:
            gpib_address_str = gpib_address.get()
        
        # Validate parameters
        if vpos < 0:
            raise ValueError(f"Vpos ({vpos}) must be >= 0")
        if vneg > 0:
            raise ValueError(f"Vneg ({vneg}) must be <= 0 (use 0 for auto-symmetric)")
        if not (1 <= num_cycles <= 1000):
            raise ValueError(f"NumCycles ({num_cycles}) must be between 1 and 1000")
        
        # Calculate total points
        num_points = 4 * num_cycles
        
        # Create KXCI client
        controller = KXCIClient(gpib_address=gpib_address_str, timeout=30.0)
        
        try:
            # Connect to instrument
            if not controller.connect():
                raise RuntimeError(f"Failed to connect to Keithley 4200A at {gpib_address_str}")
            
            # Enter UL mode
            if not controller._enter_ul_mode():
                raise RuntimeError("Failed to enter UL mode")
            
            # Build and execute EX command
            command = build_ex_command(
                vpos=vpos,
                vneg=vneg,
                num_cycles=num_cycles,
                num_points=num_points,
                settle_time=settle_time,
                ilimit=ilimit,
                integration_time=integration_time,
                clarius_debug=debug,
            )
            
            print(f"\n[Cyclical IV Sweep] Executing KXCI command:")
            vneg_display = vneg if vneg != 0 else -vpos
            print(f"  Pattern: (0V → +{vpos}V → {vneg_display}V → 0V) × {num_cycles} cycles")
            print(f"  Total points: {num_points}")
            print(f"  Settle time: {settle_time*1000:.1f} ms")
            print(f"  Current limit: {ilimit:.2e} A")
            print(f"  Integration time: {integration_time:.6f} PLC")
            print(f"  Debug: {'ON' if debug else 'OFF'}")
            
            return_value, error = controller._execute_ex_command(command)
            
            if error:
                raise RuntimeError(f"EX command failed: {error}")
            if return_value is not None and return_value < 0:
                error_messages = {
                    -1: "Invalid Vpos (must be >= 0) or Vneg (must be <= 0)",
                    -2: "NumIPoints != NumVPoints (array size mismatch)",
                    -3: "NumIPoints != 4 × NumCycles (array size must equal 4 × number of cycles)",
                    -4: "Invalid array sizes (NumIPoints or NumVPoints < 4)",
                    -5: "Invalid NumCycles (must be >= 1 and <= 1000)",
                    -6: "forcev() failed (check SMU connection and voltage range)",
                    -7: "measi() failed (check SMU connection)",
                    -8: "limiti() failed (check current limit value)",
                    -9: "setmode() failed (check SMU connection)",
                }
                msg = error_messages.get(return_value, f"Unknown error code: {return_value}")
                raise RuntimeError(f"EX command returned error code: {return_value} - {msg}")
            
            # Wait a bit for measurement to complete
            time.sleep(0.5)
            
            # Query data from GP parameters
            # GP parameter 6 = Vforce (6th parameter in function signature)
            # GP parameter 4 = Imeas (4th parameter in function signature)
            print(f"[Cyclical IV Sweep] Retrieving {num_points} data points...")
            voltage = controller._query_gp(6, num_points)  # Vforce
            current = controller._query_gp(4, num_points)  # Imeas
            
            print(f"[Cyclical IV Sweep] Received: {len(voltage)} voltage, {len(current)} current samples")
            
            # Ensure arrays are same length and filter out any trailing zeros
            min_len = min(len(voltage), len(current))
            voltage = voltage[:min_len]
            current = current[:min_len]
            
            # Filter trailing zeros (C module may allocate more space than filled)
            while min_len > 0 and voltage[min_len-1] == 0.0 and current[min_len-1] == 0.0:
                min_len -= 1
            if min_len < len(voltage):
                voltage = voltage[:min_len]
                current = current[:min_len]
                print(f"[Cyclical IV Sweep] Filtered to {min_len} valid points (removed trailing zeros)")
            
            # Generate timestamps (estimate based on settle_time and number of points)
            # Each point takes approximately settle_time + integration_time
            time_per_point = settle_time + (integration_time * 0.01)  # Rough estimate: 1 PLC ≈ 0.01s
            timestamps = [i * time_per_point for i in range(len(voltage))]
            
            # Call on_point callback if provided
            if on_point is not None:
                for v, i, t in zip(voltage, current, timestamps):
                    if hasattr(self, 'stop_measurement_flag') and self.stop_measurement_flag:
                        break
                    try:
                        on_point(v, i, t)
                    except Exception as e:
                        print(f"Warning: on_point callback failed: {e}")
            
            return (voltage, current, timestamps)
            
        finally:
            # Cleanup: exit UL mode and disconnect
            try:
                controller._exit_ul_mode()
                controller.disconnect()
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

        self.stop_measurement_flag = False
        # Device routing context
        if self.current_device in self.device_list:
            start_index = self.device_list.index(self.current_device)
        else:
            start_index = 0
        device_count = 1 if self.single_device_flag else len(self.device_list)

        if self.pulsed_runner.run(excitation, device_count, start_index):
            return
        if self.special_runner.run(excitation, device_count, start_index):
            return
        return self.single_runner.run_standard_iv()
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
        """Connect to the selected IV controller via the connection manager."""
        address = self.keithley_address_var.get()
        smu_type = getattr(self, 'SMU_type', 'Keithley 2401')
        try:
            instrument = self.connections.connect_keithley(smu_type, address)
            self.keithley = instrument
            self.connected = self.connections.is_connected("keithley")
            if hasattr(self.keithley, 'beep'):
                self.keithley.beep(4000, 0.2)
                time.sleep(0.2)
                self.keithley.beep(5000, 0.5)
        except RuntimeError as exc:
            self.connected = False
            error_str = str(exc)
            print(f"❌ ERROR: Unable to connect to SMU ({smu_type} @ {address})")
            print(f"   {error_str}")
            # Show a more user-friendly error message
            if "IVControllerManager dependency not available" in error_str:
                detailed_msg = (
                    f"Could not connect to IV Controller Manager.\n\n"
                    f"The required dependencies are not available.\n\n"
                    f"Please check:\n"
                    f"• That Equipment/managers/iv_controller.py exists\n"
                    f"• That all required dependencies are installed\n"
                    f"• Try restarting Python/your IDE\n\n"
                    f"Original error:\n{exc}"
                )
            else:
                detailed_msg = f"Could not connect to device ({smu_type} @ {address}):\n\n{exc}"
            messagebox.showerror("Connection Error", detailed_msg)
        except Exception as exc:
            self.connected = False
            print(f"❌ ERROR: Unable to connect to SMU ({smu_type} @ {address}): {exc}")
            messagebox.showerror("Connection Error", f"Could not connect to device ({smu_type} @ {address}):\n\n{exc}")

    def connect_keithley_psu(self) -> None:
        try:
            self.psu = self.connections.connect_psu(self.psu_visa_address)
            self.psu_connected = self.connections.is_connected("psu")
            if self.keithley and hasattr(self.keithley, 'beep'):
                self.keithley.beep(5000, 0.2)
                time.sleep(0.2)
                self.keithley.beep(6000, 0.2)
            if self.psu:
                self.psu.reset()
        except Exception as exc:
            self.psu_connected = False
            print("unable to connect to psu please check")
            messagebox.showerror("Error", f"Could not connect to device: {exc}")

    def connect_temp_controller(self) -> None:
        """Connect to the Oxford ITC4 temperature controller."""
        address = self.temp_controller_address
        try:
            self.itc = self.connections.connect_oxford_itc4(address)
            self.itc_connected = self.connections.is_connected("itc")
            print("connected too Temp controller")
            if self.keithley and hasattr(self.keithley, 'beep'):
                self.keithley.beep(7000, 0.2)
                time.sleep(0.2)
                self.keithley.beep(8000, 0.2)
        except Exception as exc:
            self.itc_connected = False
            print("unable to connect to Temp please check")
            messagebox.showerror("Error", f"Could not connect to temp device: {exc}")

    def init_temperature_controller(self) -> None:
        """Initialize temperature controller with auto-detection."""
        self.temp_controller = self.connections.create_temperature_controller(auto_detect=True)
        info = self.connections.get_temperature_info()
        if info:
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
            try:
                sample_name = self.sample_name_var.get().strip() or "temperature_log"
            except Exception:
                sample_name = "temperature_log"
            try:
                path = self.data_saver.save_temperature_log(
                    entries=self.temperature_log,
                    sample_name=sample_name,
                    base_override=self._get_base_save_path(),
                )
                if path:
                    self.log_terminal(f"Temperature log saved: {os.path.abspath(path)}")
            except Exception as exc:
                print(f"[DATA_SAVER] Failed to save temperature log: {exc}")
                self.log_terminal(f"Error saving temperature log: {exc}")



    ###################################################################
    # Other Functions
    ###################################################################

    def save_averaged_data(self, device_data, sample_name, start_index, interrupted=False):
        """
        Delegate averaged-data persistence to :class:`MeasurementDataSaver`.

        The new saver expects primitive values instead of reaching back into
        Tkinter variables, so we extract everything up-front and pass it
        explicitly.  This makes the method easier to unit-test and keeps the
        saver reusable for future front-ends (e.g. Qt).
        """
        try:
            duration_value = self.measurement_duration_var.get()
            try:
                measurement_duration = float(duration_value)
            except (TypeError, ValueError):
                measurement_duration = float(str(duration_value).strip() or 0)
        except Exception:
            measurement_duration = 0.0

        record_temperature = bool(getattr(self.record_temp_var, "get", lambda: False)())
        base_override = self._get_base_save_path()

        try:
            saved_paths = self.data_saver.save_averaged_data(
                device_data=device_data,
                sample_name=sample_name,
                measurement_duration_s=measurement_duration,
                record_temperature=record_temperature,
                interrupted=interrupted,
                base_override=base_override,
            )
        except Exception as exc:
            print(f"[DATA_SAVER] Failed to save averaged data: {exc}")
            self.log_terminal(f"Error saving averaged data: {exc}")
            return

        for path in saved_paths:
            abs_path = os.path.abspath(path)
            print(f"[SAVE] File saved to: {abs_path}")
            self.log_terminal(f"Saved data to: {abs_path}")

    def send_temp(self) -> None:
        """Apply a new temperature setpoint if hardware is connected."""
        target = getattr(self, "target_temp_var", None)
        if hasattr(target, "get"):
            try:
                value = target.get()
            except Exception:
                value = None
        else:
            value = target

        if value in ("", None):
            print("No temperature setpoint specified.")
            return

        try:
            setpoint = float(value)
        except (TypeError, ValueError):
            print(f"Invalid temperature setpoint: {value}")
            return

        if not getattr(self, "itc", None):
            print("Temperature controller not connected.")
            return

        self.itc.set_temperature(setpoint)
        self.temp_setpoint = str(value)
        self.graphs_temp_time_rt(self.Graph_frame)
        print(f"temperature set to {value}")

    def update_variables(self) -> None:
        # update current device
        self.current_device = self.device_list[self.current_index]
        # Update number (ie device_11)
        self.device_section_and_number = self.convert_to_name(self.current_index)
        # Update section and number
        self.display_index_section_number = f"{self.device_section_and_number} ({self.current_device})"
        self.device_var.config(text=self.display_index_section_number)
        self._update_device_identifiers(self.device_section_and_number)
        # print(self.convert_to_name(self.current_index))

    def measure_one_device(self) -> None:
        if self.adaptive_var.get():
            print("Measuring only one device")
            self.single_device_flag = True
        else:
            print("Measuring all devices")
            self.single_device_flag = False

    def bring_to_top(self) -> None:
        """Raise the main window and ensure it gains focus."""
        try:
            master = getattr(self, "master", None)
            if master and master.winfo_exists():
                master.deiconify()
                master.lift()
                master.focus_force()
                master.attributes("-topmost", True)
                master.after(100, lambda: master.attributes("-topmost", False))
            else:
                # Window doesn't exist anymore, return False to indicate failure
                raise Exception("Window no longer exists")
        except Exception as exc:
            print(f"[GUI] Failed to bring window to top: {exc}")
            raise  # Re-raise to let caller know it failed

    def convert_to_name(self, index: int) -> str:
        """Translate a device index into the legacy section/number label."""
        try:
            device = self.device_list[index]
        except Exception:
            return f"device_{index + 1}"

        # Prefer Sample GUI friendly labels if available
        try:
            if hasattr(self.sample_gui, "get_device_label"):
                label = self.sample_gui.get_device_label(device)
                if label:
                    return str(label)
        except Exception:
            pass

        # Backwards compatibility with older Sample GUI helper
        try:
            if hasattr(self.sample_gui, "convert_to_name"):
                return str(self.sample_gui.convert_to_name(device))
        except Exception:
            pass

        try:
            if hasattr(self.sample_gui, "convert_to_name"):
                return str(self.sample_gui.convert_to_name(index))
        except Exception:
            pass

        section = getattr(self, "section", "")
        if section:
            return f"{section}_{device}"
        return str(device)

    def _update_device_identifiers(self, label: str) -> None:
        """Derive the legacy letter/number components for save paths."""
        letter = "".join(ch for ch in str(label) if ch.isalpha()) or "A"
        number = "".join(ch for ch in str(label) if ch.isdigit()) or "1"
        self.final_device_letter = letter
        try:
            self.final_device_number = int(number)
        except ValueError:
            self.final_device_number = number

    def open_motor_control(self) -> None:
        """Launch or raise the motor control GUI."""
        try:
            existing = getattr(self, "motor_control_window", None)
            if existing is not None and existing.winfo_exists():
                existing.lift()
                return
        except Exception:
            pass

        try:
            window = MotorControlWindow()
            self.motor_control_window = window
        except Exception as exc:
            messagebox.showerror("Motor Control", f"Unable to open motor control GUI:\n{exc}")

    def _collect_summary_plot_data(self) -> SummaryPlotData:
        """Gather plot data for summary image generation."""
        def _extract_lines(axis: Any) -> list[tuple[list[float], list[float]]]:
            lines_data: list[tuple[list[float], list[float]]] = []
            if not axis:
                return lines_data
            for line in getattr(axis, "lines", []):
                try:
                    x = list(line.get_xdata())
                    y = list(line.get_ydata())
                    if x and y:
                        lines_data.append((x, y))
                except Exception:
                    continue
            return lines_data

        final_iv = getattr(getattr(self, "plot_panels", None), "last_sweep", ([], []))
        return SummaryPlotData(
            all_iv=_extract_lines(getattr(self, "ax_all_iv", None)),
            all_log=_extract_lines(getattr(self, "ax_all_logiv", None)),
            final_iv=(list(final_iv[0]), list(final_iv[1])),
        )

    def _save_summary_artifacts(self, save_dir: str) -> None:
        """Save legacy summary figures and data-saver combined plots."""
        Path(save_dir).mkdir(parents=True, exist_ok=True)
        try:
            iv_path = os.path.join(save_dir, "All_graphs_IV.png")
            log_path = os.path.join(save_dir, "All_graphs_LOG.png")
            self.ax_all_iv.figure.savefig(iv_path, dpi=400)
            self.ax_all_logiv.figure.savefig(log_path, dpi=400)
            print(f"[SAVE] Graph saved to: {os.path.abspath(iv_path)}")
            print(f"[SAVE] Graph saved to: {os.path.abspath(log_path)}")
        except Exception as exc:
            print(f"[SAVE ERROR] Failed to save graphs: {exc}")

        plot_data = self._collect_summary_plot_data()
        _, _, combined = self.data_saver.save_summary_plots(save_dir, plot_data)
        self._last_combined_summary_path = combined

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
        config_file = _PROJECT_ROOT / "Json_Files" / "save_location_config.json"
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
        config_file = _PROJECT_ROOT / "Json_Files" / "save_location_config.json"
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
    
    def _resolve_default_save_root(self) -> Path:
        """
        Determine the default base directory for measurement data.

        Preference order:
        1. OneDrive commercial root (environment-provided) ➜ Documents ➜ Data_folder
        2. Explicit `%USERPROFILE%/OneDrive - The University of Nottingham/Documents/Data_folder`
        3. Local `%USERPROFILE%/Documents/Data_folder`

        The folder is created on demand. If none of the OneDrive locations
        exist, the method falls back to the local Documents directory.
        """
        home = Path.home()
        candidates: List[Path] = []

        for env_key in ("OneDriveCommercial", "OneDrive"):
            env_path = os.environ.get(env_key)
            if env_path:
                root = Path(env_path)
                candidates.append(root / "Documents")

        candidates.append(home / "OneDrive - The University of Nottingham" / "Documents")
        candidates.append(home / "Documents")

        for documents_path in candidates:
            try:
                root_exists = documents_path.parent.exists()
                if not root_exists:
                    continue
                documents_path.mkdir(parents=True, exist_ok=True)
                target = documents_path / "Data_folder"
                target.mkdir(parents=True, exist_ok=True)
                return target
            except Exception:
                continue

        fallback = home / "Documents" / "Data_folder"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback

    def _get_base_save_path(self) -> str:
        """Get base save path (custom if enabled, default root otherwise)."""
        if self.use_custom_save_var.get() and self.custom_save_location:
            return str(self.custom_save_location)
        return str(self.default_save_root)
    
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
        base_path = Path(self._get_base_save_path())
        device_path = base_path / sample_name / device_letter / str(device_number)
        device_path.mkdir(parents=True, exist_ok=True)
        return str(device_path)
    
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

    def _start_plot_threads(self) -> None:
        """Compatibility shim: delegate to PlotUpdaters."""
        if hasattr(self, "plot_updaters"):
            self.plot_updaters.start_all_threads()

    def _start_temperature_thread(self) -> None:
        """Compatibility shim for legacy callers."""
        if hasattr(self, "plot_updaters"):
            self.plot_updaters.start_temperature_thread(self.itc_connected)
