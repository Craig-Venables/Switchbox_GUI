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

- DeviceVisualizer: Device analysis visualization tool
  - Access: "Device Visualizer" button
  - Purpose: Browse and analyze device data with comprehensive visualizations

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
from gui.measurement_gui.analysis_stats_window import AnalysisStatsWindow
from gui.pulse_testing_gui import TSPTestingGUI
from gui.oscilloscope_pulse_gui.main import OscilloscopePulseGUI

# Import step-based IV sweep functions for 4200A (conditional import)
# Using importlib to avoid issues with directory names starting with numbers
try:
    import importlib
    _smu_iv_sweep_module = importlib.import_module('Equipment.SMU_AND_PMU.4200A.C_Code_with_python_scripts.A_Iv_Sweep.run_smu_vi_sweep')
    KXCIClient = _smu_iv_sweep_module.KXCIClient
    build_ex_command = _smu_iv_sweep_module.build_ex_command
    format_param = _smu_iv_sweep_module.format_param
    _SMU_IV_SWEEP_AVAILABLE = True
except (ImportError, AttributeError) as e:
    # Gracefully handle if module is not available
    _SMU_IV_SWEEP_AVAILABLE = False
    KXCIClient = None
    build_ex_command = None
    format_param = None
    print(f"WARNING: Step-based IV sweep module not available: {e}")
    KXCIClient = None
    build_ex_command = None
    format_param = None

# Optional dependencies --------------------------------------------------------
try:  # PMU testing GUI is optional (requires PMU hardware stack)
    from PMU_Testing_GUI import PMUTestingGUI  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    PMUTestingGUI = None  # type: ignore

try:  # Advanced tests GUI is optional
    from Advanced_tests_GUI import AdvancedTestsGUI  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    AdvancedTestsGUI = None  # type: ignore

try:  # Automated tester GUI is optional
    from Automated_tester_GUI import AutomatedTesterGUI  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    AutomatedTesterGUI = None  # type: ignore

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

# ==================== DEBUG CONTROL ====================
# Set to True only when actively debugging. In normal use this should stay False
# so the console isn't flooded with messages.
DEBUG_ENABLED = False

def debug_print(*args, **kwargs):
    """
    Lightweight debug logger.
    
    NOTE: Kept for future troubleshooting, but disabled by default via
    DEBUG_ENABLED=False to keep runtime output clean for end users.
    """
    if DEBUG_ENABLED:
        print(*args, **kwargs)

if TYPE_CHECKING:
    # Optional-only imports for typing; avoids runtime deps if unavailable
    try:
        from Advanced_tests_GUI import AdvancedTestsGUI  # noqa: F401, type: ignore
    except ImportError:
        AdvancedTestsGUI = None  # type: ignore
    try:
        from PMU_Testing_GUI import PMUTestingGUI as _PMUTestingGUIType  # noqa: F401, type: ignore
    except ImportError:
        _PMUTestingGUIType = None  # type: ignore
    try:
        from Automated_tester_GUI import AutomatedTesterGUI as _AutomatedTesterGUIType  # noqa: F401, type: ignore
    except ImportError:
        _AutomatedTesterGUIType = None  # type: ignore
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
            # Unregister from sample_gui
            if hasattr(self.sample_gui, 'unregister_child_gui'):
                self.sample_gui.unregister_child_gui(self)
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
                "open_oscilloscope_pulse": self.open_oscilloscope_pulse,
                "run_conditional_testing": self.run_conditional_testing,
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
        # Set GUI reference for toggle logic
        self.plot_panels.gui = self
        
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
        
        # Initialize analysis stats window (floating overlay)
        if hasattr(self, 'measurements_graph_panel'):
            self.analysis_stats_window = AnalysisStatsWindow(
                parent=self.master,
                graph_frame=self.measurements_graph_panel
            )
        else:
            self.analysis_stats_window = None
        
        # Wire up analysis enabled checkbox to show/hide stats window
        if hasattr(self, 'analysis_enabled'):
            self.analysis_enabled.trace_add('write', self._on_analysis_enabled_changed)

        # self.measurement_thread = None
        # self.plotter = None
        # self.safe_plotter = None
        # self.plotter = None

        # list all GPIB Devices
        # find kiethely smu assign to correct

        # connect to kiethley's
        # Set default to System 1 and trigger the change
        self.set_default_system()

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

        # Clean up analysis stats window
        try:
            if hasattr(self, 'analysis_stats_window') and self.analysis_stats_window:
                self.analysis_stats_window.destroy()
        except Exception:
            pass
        
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
            pass

        # Disconnect laser/optical system if connected
        try:
            if hasattr(self, 'optical') and self.optical is not None:
                # Disable optical source first
                try:
                    self.optical.set_enabled(False)
                except Exception:
                    pass
                # Close connection properly (restores laser to manual control mode)
                try:
                    self.optical.close()
                    print("[OPTICAL] Laser/optical system disconnected and restored to manual control")
                except Exception as e:
                    print(f"[OPTICAL] Warning: Failed to close optical system: {e}")
        except Exception:
            print("Warning: Optical system cleanup failed")

        # Also try disconnect_laser method if it exists (for backward compatibility)
        try:
            if hasattr(self, 'disconnect_laser'):
                self.disconnect_laser()
        except Exception:
            pass

        print("safely turned everything off")
        # Reset runtime test flags
        self.tests_running = False
        self.abort_tests_flag = False

    def _on_analysis_enabled_changed(self, *args) -> None:
        """
        Callback when analysis_enabled checkbox changes.
        Shows or hides the analysis stats window accordingly.
        Note: If stats panel is visible, floating window will be hidden.
        """
        if not hasattr(self, 'analysis_stats_window') or not self.analysis_stats_window:
            return
        
        if hasattr(self, 'analysis_enabled') and self.analysis_enabled.get():
            # Check if stats panel is visible - if so, don't show floating window
            stats_panel_visible = False
            if hasattr(self, 'plot_panels') and self.plot_panels:
                stats_panel_visible = self.plot_panels.plot_visibility.get(
                    "analysis_stats",
                    tk.BooleanVar(value=False)
                ).get()
            
            if not stats_panel_visible:
                # Show the stats window
                self.analysis_stats_window.show()
            else:
                # Stats panel is visible, so hide floating window
                self.analysis_stats_window.hide()
        else:
            # Hide the stats window
            self.analysis_stats_window.hide()
    
    def update_analysis_stats(self, analysis_data: Dict[str, Any], analysis_level: Optional[str] = None) -> None:
        """
        Update the analysis stats window and panel with new analysis data.
        
        This method should be called when analysis is performed on a sweep.
        It will update both the floating window and the stats panel if they're visible.
        
        Example usage (when wiring up analysis):
        ---------------------------------------
        from Helpers.Analysis import IVSweepAnalyzer
        
        # After a sweep completes, analyze the data:
        analyzer = IVSweepAnalyzer(analysis_level=self.analysis_level_var.get())
        analysis_data = analyzer.analyze_sweep(voltage=voltage_data, current=current_data)
        
        # Update the stats window:
        self.update_analysis_stats(analysis_data)
        
        Parameters:
        -----------
        analysis_data : dict
            Analysis data from IVSweepAnalyzer.analyze_sweep()
        analysis_level : str, optional
            Analysis level ('basic', 'classification', 'full', 'research').
            If None, uses the current value from analysis_level_var.
        """
        # Get analysis level from GUI if not provided
        if analysis_level is None:
            if hasattr(self, 'analysis_level_var'):
                analysis_level = self.analysis_level_var.get()
            else:
                analysis_level = 'full'
        
        # Update the stats panel (if it exists)
        if hasattr(self, 'plot_panels') and self.plot_panels:
            self.plot_panels.update_stats_panel(analysis_data, analysis_level)
        
        # Update the floating stats window (if it exists)
        if hasattr(self, 'analysis_stats_window') and self.analysis_stats_window:
            self.analysis_stats_window.update_stats(analysis_data, analysis_level)
            
            # Show window if analysis is enabled AND stats panel is not visible
            if hasattr(self, 'analysis_enabled') and self.analysis_enabled.get():
                # Check if stats panel is visible - if so, hide floating window
                stats_panel_visible = False
                if hasattr(self, 'plot_panels') and self.plot_panels:
                    stats_panel_visible = self.plot_panels.plot_visibility.get(
                        "analysis_stats", 
                        tk.BooleanVar(value=False)
                    ).get()
                
                if not stats_panel_visible:
                    self.analysis_stats_window.show()
                else:
                    self.analysis_stats_window.hide()

    def _update_live_classification_display(
        self, 
        sweep_num: int, 
        total_sweeps: int, 
        classification_data: Dict[str, Any]
    ) -> None:
        """
        Update GUI with live classification progress during custom measurements.
        Shows: "Sweep 5/20: Memristive (Score: 75.2)"
        
        Parameters:
        -----------
        sweep_num : int
            Current sweep number (1-indexed)
        total_sweeps : int
            Total number of sweeps in sequence
        classification_data : Dict[str, Any]
            Classification data from analysis (device_type, memristivity_score, etc.)
        """
        try:
            device_type = classification_data.get('device_type', 'unknown')
            score = classification_data.get('memristivity_score', 0)
            
            # Build status message
            status_msg = f"Sweep {sweep_num}/{total_sweeps}: "
            status_msg += f"{device_type.title()} "
            status_msg += f"(Score: {score:.1f}/100)"
            
            # Update status bar or label if available
            if hasattr(self, 'status_label'):
                self.status_label.config(text=status_msg)
            
            # Force GUI update
            self.master.update_idletasks()
            
            debug_print(f"[LIVE] {status_msg}")
            
        except Exception as e:
            debug_print(f"[LIVE] Error updating display: {e}")

    def _send_classification_notification(
        self, 
        device_id: str, 
        classification_data: Dict[str, Any]
    ) -> None:
        """
        PLACEHOLDER for future notification system.
        
        TODO: Implement notifications for:
        - Device becomes memristive during forming
        - Score exceeds threshold
        - Degradation detected
        - Sequence complete
        
        Integration options:
        - Telegram bot
        - Email alerts
        - System notifications
        - Webhook POST
        
        Parameters:
        -----------
        device_id : str
            Device identifier (e.g., "sample_A_1")
        classification_data : Dict[str, Any]
            Classification data from analysis
        """
        pass

    def _run_analysis_if_enabled(
        self,
        voltage: List[float],
        current: List[float],
        timestamps: Optional[List[float]],
        save_dir: str,
        file_name: str,
        metadata: Optional[Dict[str, Any]] = None,
        is_custom_sequence: bool = False,
        sweep_number: int = 1,
        device_memristive_flag: bool = None
    ) -> Optional[Dict[str, Any]]:
        """
        Run IV analysis if enabled, display results, and save to file.
        
        This method checks if analysis is enabled, runs quick_analyze() on the
        measurement data, updates the stats window/panel, and saves results to
        the unified analysis folder at {sample}/sample_analysis/analysis/sweeps/{device_id}/.
        
        For custom sequences:
        - Sweep 1: Always analyze to determine if memristive
        - Sweeps 2+: Only analyze if device_memristive_flag == True
        a "sweep_analysis" subfolder.

        Parameters:
        -----------
        voltage : List[float]
            Voltage data array from measurement
        current : List[float]
            Current data array from measurement
        timestamps : Optional[List[float]]
            Timestamp data array (optional, for pulse/retention measurements)
        save_dir : str
            Directory where measurement data is saved
        file_name : str
            Base filename for the measurement (without extension)
        metadata : Optional[Dict[str, Any]]
            Additional metadata (LED state, temperature, etc.)
        is_custom_sequence : bool
            Whether this is part of a custom measurement sequence
        sweep_number : int
            Sweep number within the sequence (1-indexed)
        device_memristive_flag : bool, optional
            Whether device is known to be memristive (for sweeps 2+)
        
        Returns:
        --------
        Optional[Dict[str, Any]] - Analysis data dict, or None if skipped.
            For custom sequences, first sweep returns {'analysis_data': ..., 'is_memristive': bool}
        """
        # ANALYSIS IS NOW AUTOMATIC - Always runs classification, background research for memristive
        # (Checkbox is now redundant but kept for potential future use)
        
        # === CONDITIONAL LOGIC FOR CUSTOM SEQUENCES ===
        # Skip if not first sweep AND device is not memristive
        if is_custom_sequence and sweep_number > 1:
            if not device_memristive_flag:
                debug_print(f"[ANALYSIS] Skipping sweep {sweep_number} - device not memristive")
                return None
        
        # Validate input data
        if not voltage or not current or len(voltage) == 0 or len(current) == 0:
            debug_print("[ANALYSIS] Skipping analysis: empty voltage or current arrays")
            return None
        
        if len(voltage) != len(current):
            debug_print(f"[ANALYSIS] Skipping analysis: array length mismatch (V:{len(voltage)}, I:{len(current)})")
            return None
        
        try:
            # Import analysis module
            from Helpers.Analysis import quick_analyze
            
            # Get analysis level from GUI
            # Always use 'classification' for speed (memristive devices get research in background)
            analysis_level = 'classification'
            if hasattr(self, 'analysis_level_var'):
                # Allow user override if they really want different level
                user_level = self.analysis_level_var.get()
                if user_level in ['basic', 'full', 'research']:
                    analysis_level = user_level
            
            # Convert to numpy arrays if needed
            import numpy as np
            v_arr = np.array(voltage) if not isinstance(voltage, np.ndarray) else voltage
            i_arr = np.array(current) if not isinstance(current, np.ndarray) else current
            t_arr = None
            if timestamps and len(timestamps) > 0:
                t_arr = np.array(timestamps) if not isinstance(timestamps, np.ndarray) else timestamps
            
            # Build metadata if not provided
            if metadata is None:
                metadata = {}
            
            # Add device info to metadata
            if 'device_name' not in metadata:
                device_name = f"{self.sample_name_var.get()}_{self.final_device_letter}{self.final_device_number}"
                metadata['device_name'] = device_name
            
            # Add LED info if available
            if hasattr(self, 'optical') and self.optical is not None:
                try:
                    caps = getattr(self.optical, 'capabilities', {})
                    if caps.get('type', '').lower() == 'led':
                        # Check if LED was on during measurement
                        # This might need to be passed in metadata from the measurement runner
                        pass
                except Exception:
                    pass
            
            # === PHASE 2: Build device tracking info ===
            device_id = None
            cycle_number = None
            sample_save_dir = save_dir  # Will be updated to sample-level for unified analysis folder
            
            if hasattr(self, 'sample_name_var') and hasattr(self, 'final_device_letter') and hasattr(self, 'final_device_number'):
                # Create unique device ID: sample_letter_number (e.g., "MyChip_A_1")
                device_id = f"{self.sample_name_var.get()}_{self.final_device_letter}_{self.final_device_number}"
                
                # Use sample-level directory for tracking/research (not device-level)
                sample_name = self.sample_name_var.get()
                if sample_name:
                    sample_save_dir = self._get_sample_save_directory(sample_name)
            
            # Try to get cycle number from measurement count (if available)
            # This will be overridden in endurance/retention measurements with actual cycle count
            if hasattr(self, 'measurement_count'):
                cycle_number = getattr(self, 'measurement_count', None)
            
            # Run analysis in background thread to prevent crashes
            debug_print(f"[ANALYSIS] Queuing analysis (level: {analysis_level}) on {len(v_arr)} points...")

            # Ensure threading module is accessible (fix for UnboundLocalError)
            import threading as _threading

            # Create a thread-safe way to update GUI after analysis
            def run_analysis_thread():
                try:
                    debug_print(f"[ANALYSIS] Running analysis (level: {analysis_level}) on {len(v_arr)} points...")
                    analysis_data = quick_analyze(
                        voltage=v_arr,
                        current=i_arr,
                        time=t_arr,
                        metadata=metadata,
                        analysis_level=analysis_level,
                        device_id=device_id,
                        cycle_number=cycle_number,
                        save_directory=sample_save_dir  # Use sample-level for tracking/research
                    )

                    # Update GUI in main thread using after() method
                    def update_gui():
                        try:
                            # Update stats window and panel
                            self.update_analysis_stats(analysis_data, analysis_level)
                        except Exception as stats_exc:
                            debug_print(f"[ANALYSIS] Failed to update stats window: {stats_exc}")

                        try:
                            # Update top bar classification display
                            self.update_classification_display(analysis_data.get('classification', {}))
                        except Exception as display_exc:
                            debug_print(f"[ANALYSIS] Failed to update classification display: {display_exc}")

                        try:
                            # Save analysis results to file
                            self._save_analysis_results(analysis_data, save_dir, file_name, analysis_level)
                        except Exception as save_exc:
                            debug_print(f"[ANALYSIS] Failed to save analysis results: {save_exc}")

                        # Store analysis result for plotting
                        if not is_custom_sequence:
                            self._last_analysis_result = analysis_data

                        # Log analysis completion
                        if hasattr(self, 'plot_panels'):
                            self.plot_panels.log_graph_activity(f"Analysis complete: {file_name} ({analysis_level})")

                        # === AUTO-TRIGGER RESEARCH ANALYSIS FOR MEMRISTIVE DEVICES ===
                        device_type = analysis_data.get('classification', {}).get('device_type', '')
                        memristivity_score = analysis_data.get('classification', {}).get('memristivity_score', 0)

                        if device_type in ['memristive', 'memcapacitive'] or (memristivity_score and memristivity_score > 60):
                            # Spawn background thread for research-level analysis
                            def run_research_analysis():
                                try:
                                    debug_print(f"[RESEARCH] Starting background research analysis for {file_name}...")
                                    if hasattr(self, 'plot_panels'):
                                        self.plot_panels.log_graph_activity(f"Starting research analysis: {file_name}")

                                    # Run research-level analysis
                                    research_data = quick_analyze(
                                        voltage=v_arr,
                                        current=i_arr,
                                        time=t_arr,
                                        metadata=metadata,
                                        analysis_level='research',
                                        device_id=device_id,
                                        cycle_number=cycle_number,
                                        save_directory=sample_save_dir
                                    )

                                    # Save to device-specific research folder
                                    self._save_research_analysis(research_data, sample_save_dir, file_name, device_id)

                                    debug_print(f"[RESEARCH] Background research analysis complete for {file_name}")
                                    if hasattr(self, 'plot_panels'):
                                        self.plot_panels.log_graph_activity(f"Research analysis complete: {file_name}")
                                except Exception as e:
                                    debug_print(f"[RESEARCH ERROR] Background analysis failed: {e}")
                                    import traceback
                                    traceback.print_exc()

                            # Start background thread (daemon so it doesn't block exit)
                            research_thread = _threading.Thread(target=run_research_analysis, daemon=True)
                            research_thread.start()

                            debug_print(f"[RESEARCH] Background research analysis queued (memristive device detected, score={memristivity_score:.1f})")

                        # === RETURN FOR CUSTOM SEQUENCES ===
                        # For first sweep in custom sequence, store memristive flag
                        if is_custom_sequence and sweep_number == 1:
                            is_memristive = device_type in ['memristive', 'memcapacitive'] or (memristivity_score and memristivity_score > 60)
                            debug_print(f"[ANALYSIS] First sweep: score={memristivity_score:.1f}, memristive={is_memristive}")
                            # Store result for custom measurement to use
                            if not hasattr(self, '_pending_analysis_results'):
                                self._pending_analysis_results = {}
                            self._pending_analysis_results[f"{file_name}_sweep_{sweep_number}"] = {
                                'analysis_data': analysis_data,
                                'is_memristive': is_memristive
                            }

                        # For non-custom or subsequent sweeps, trigger automatic plotting
                        if not is_custom_sequence:
                            try:
                                classification = analysis_data.get('classification', {})
                                is_memristive = classification.get('memristivity_score', 0) > 60
                                device_name = f"{self.final_device_letter}{self.final_device_number}" if hasattr(self, 'final_device_letter') else "device"

                                if save_dir:
                                    self._plot_measurement_in_background(
                                        voltage=list(v_arr),
                                        current=list(i_arr),
                                        timestamps=list(t_arr) if t_arr is not None else None,
                                        save_dir=save_dir,
                                        device_name=device_name,
                                        sweep_number=1,
                                        is_memristive=is_memristive,
                                        filename=file_name
                                    )
                            except Exception as plot_exc:
                                print(f"[PLOT ERROR] Failed to queue background plotting: {plot_exc}")

                    # Schedule GUI update on main thread
                    if hasattr(self, 'master') and self.master:
                        self.master.after(0, update_gui)
                    else:
                        update_gui()

                except Exception as exc:
                    debug_print(f"[ANALYSIS ERROR] Failed to run analysis: {exc}")
                    import traceback
                    traceback.print_exc()
                    # Try to update GUI with error message
                    if hasattr(self, 'master') and self.master:
                        def show_error():
                            try:
                                if hasattr(self, 'plot_panels'):
                                    self.plot_panels.log_graph_activity(f"Analysis failed: {str(exc)[:50]}")
                            except:
                                pass
                        self.master.after(0, show_error)

            # Start analysis in background thread
            analysis_thread = _threading.Thread(target=run_analysis_thread, daemon=True, name="AnalysisThread")
            analysis_thread.start()

            # Log that analysis is starting
            if hasattr(self, 'plot_panels'):
                self.plot_panels.log_graph_activity(f"Analysis queued: {file_name} ({analysis_level})")

            # Return immediately - analysis will continue in background
            # For custom sequences, we need to check for pending results
            if is_custom_sequence and sweep_number == 1:
                # Wait a short time for analysis to complete (non-blocking check)
                # The actual result will be stored in _pending_analysis_results
                return None

            # For non-custom sequences, return None (analysis happens in background)
            return None
            
            # Run analysis
            debug_print(f"[ANALYSIS] Running analysis (level: {analysis_level}) on {len(v_arr)} points...")
            analysis_data = quick_analyze(
                voltage=v_arr,
                current=i_arr,
                time=t_arr,
                metadata=metadata,
                analysis_level=analysis_level,
                device_id=device_id,
                cycle_number=cycle_number,
                save_directory=sample_save_dir  # Use sample-level for tracking/research
            )

            # Update stats window and panel
            self.update_analysis_stats(analysis_data, analysis_level)

            # Update top bar classification display
            self.update_classification_display(analysis_data.get('classification', {}))

            # Save analysis results to file
            self._save_analysis_results(analysis_data, save_dir, file_name, analysis_level)

            # === AUTO-TRIGGER RESEARCH ANALYSIS FOR MEMRISTIVE DEVICES ===
            # If device is memristive, run full research analysis in background
            device_type = analysis_data.get('classification', {}).get('device_type', '')
            memristivity_score = analysis_data.get('classification', {}).get('memristivity_score', 0)

            if device_type in ['memristive', 'memcapacitive'] or (memristivity_score and memristivity_score > 60):
                # Spawn background thread for research-level analysis
                import threading

                def run_research_analysis():
                    try:
                        debug_print(f"[RESEARCH] Starting background research analysis for {file_name}...")

                        # Use sample-level directory for research (same as tracking)
                        research_save_dir = sample_save_dir

                        # Run research-level analysis
                        research_data = quick_analyze(
                            voltage=v_arr,
                            current=i_arr,
                            time=t_arr,
                            metadata=metadata,
                            analysis_level='research',
                            device_id=device_id,
                            cycle_number=cycle_number,
                            save_directory=research_save_dir  # Use sample-level
                        )

                        # Save to device-specific research folder (within sample-level directory)
                        self._save_research_analysis(research_data, research_save_dir, file_name, device_id)

                        debug_print(f"[RESEARCH] Background research analysis complete for {file_name}")
                    except Exception as e:
                        debug_print(f"[RESEARCH ERROR] Background analysis failed: {e}")

                # Start background thread (daemon so it doesn't block exit)
                research_thread = _threading.Thread(target=run_research_analysis, daemon=True)
                research_thread.start()

                debug_print(f"[RESEARCH] Background research analysis queued (memristive device detected, score={memristivity_score:.1f})")

            debug_print("[ANALYSIS] Analysis complete and results saved")

        except Exception as exc:
            # Log error but don't interrupt measurement flow
            debug_print(f"[ANALYSIS ERROR] Failed to run analysis: {exc}")
            import traceback
            traceback.print_exc()
            return None
    
    def _save_analysis_results(
        self,
        analysis_data: Dict[str, Any],
        save_dir: str,
        file_name: str,
        analysis_level: str
    ) -> None:
        """
        Save analysis results to a formatted text file in the unified analysis folder.
        
        Saves to: {sample}/sample_analysis/analysis/sweeps/{device_id}/{file_name}_analysis.txt
        Save analysis results to a formatted text file in the sweep_analysis subfolder.

        Parameters:
        -----------
        analysis_data : dict
            Analysis results from quick_analyze()
        save_dir : str
            Base save directory for measurements
        file_name : str
            Base filename (without extension)
        analysis_level : str
            Analysis level used ('basic', 'classification', 'full', 'research')
        """
        try:
            import os
            from datetime import datetime
            
            # Get device_id - prefer from analysis data, fallback to construction
            device_id = None
            device_info = analysis_data.get('device_info', {})
            
            # Try to get from device_info first
            if device_info.get('name'):
                device_id = device_info['name']
            else:
                # Try metadata
                metadata = device_info.get('metadata', {})
                if metadata.get('device_name'):
                    device_id = metadata['device_name']
            
            # If still no device_id, construct from GUI vars (same logic as tracking)
            if not device_id:
                if hasattr(self, 'sample_name_var') and hasattr(self, 'final_device_letter') and hasattr(self, 'final_device_number'):
                    sample_name = self.sample_name_var.get()
                    device_letter = getattr(self, 'final_device_letter', '')
                    device_number = getattr(self, 'final_device_number', '')
                    if sample_name and device_letter and device_number:
                        device_id = f"{sample_name}_{device_letter}_{device_number}"
            
            # Last resort: extract from save_dir path
            if not device_id:
                path_parts = os.path.normpath(save_dir).split(os.sep)
                if len(path_parts) >= 3:
                    # save_dir is: {sample}/{section}/{device}
                    device_id = f"{path_parts[-3]}_{path_parts[-2]}_{path_parts[-1]}"
                else:
                    device_id = "unknown_device"
            
            # Get sample-level directory (same logic as device tracking)
            sample_name = self.sample_name_var.get() if hasattr(self, 'sample_name_var') else None
            if not sample_name:
                # Extract from path if needed
                path_parts = os.path.normpath(save_dir).split(os.sep)
                if len(path_parts) >= 3:
                    sample_name = path_parts[-3]
            
            sample_save_dir = self._get_sample_save_directory(sample_name) if sample_name else save_dir
            
            # Create unified analysis/sweeps folder structure
            # {sample}/sample_analysis/analysis/sweeps/{device_id}/
            analysis_base_dir = os.path.join(sample_save_dir, "sample_analysis", "analysis", "sweeps", device_id)
            os.makedirs(analysis_base_dir, exist_ok=True)
            # Create sweep_analysis subfolder
            analysis_dir = os.path.join(save_dir, "sweep_analysis")
            os.makedirs(analysis_dir, exist_ok=True)

            # Create output filename
            analysis_file = os.path.join(analysis_base_dir, f"{file_name}_analysis.txt")
            
            # Format analysis results as readable text
            lines = []
            lines.append("=" * 80)
            lines.append("IV SWEEP ANALYSIS RESULTS")
            lines.append("=" * 80)
            lines.append(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append(f"Analysis Level: {analysis_level.upper()}")
            lines.append(f"Original File: {file_name}.txt")
            lines.append("")
            
            # Device Information
            device_info = analysis_data.get('device_info', {})
            lines.append("DEVICE INFORMATION")
            lines.append("-" * 80)
            lines.append(f"Device Name: {device_info.get('name', 'N/A')}")
            lines.append(f"Measurement Type: {device_info.get('measurement_type', 'N/A')}")
            lines.append(f"Number of Loops: {device_info.get('num_loops', 0)}")
            metadata = device_info.get('metadata', {})
            if metadata:
                if metadata.get('led_on') is not None:
                    lines.append(f"LED State: {'ON' if metadata.get('led_on') else 'OFF'}")
                if metadata.get('led_type'):
                    lines.append(f"LED Type: {metadata.get('led_type')}")
                if metadata.get('temperature') is not None:
                    lines.append(f"Temperature: {metadata.get('temperature'):.1f} °C")
            lines.append("")
            
            # Resistance Metrics
            res_metrics = analysis_data.get('resistance_metrics', {})
            lines.append("RESISTANCE METRICS")
            lines.append("-" * 80)
            lines.append(f"Ron (mean): {self._format_analysis_value(res_metrics.get('ron_mean', 0), 'Ω')}")
            lines.append(f"Ron (std): {self._format_analysis_value(res_metrics.get('ron_std', 0), 'Ω')}")
            lines.append(f"Roff (mean): {self._format_analysis_value(res_metrics.get('roff_mean', 0), 'Ω')}")
            lines.append(f"Roff (std): {self._format_analysis_value(res_metrics.get('roff_std', 0), 'Ω')}")
            lines.append(f"Switching Ratio (mean): {self._format_analysis_value(res_metrics.get('switching_ratio_mean', 0))}")
            lines.append(f"ON/OFF Ratio (mean): {self._format_analysis_value(res_metrics.get('on_off_ratio_mean', 0))}")
            lines.append("")
            
            # Voltage Metrics
            volt_metrics = analysis_data.get('voltage_metrics', {})
            lines.append("VOLTAGE METRICS")
            lines.append("-" * 80)
            lines.append(f"Von (mean): {self._format_analysis_value(volt_metrics.get('von_mean', 0), 'V')}")
            lines.append(f"Voff (mean): {self._format_analysis_value(volt_metrics.get('voff_mean', 0), 'V')}")
            lines.append(f"Max Voltage: {self._format_analysis_value(volt_metrics.get('max_voltage', 0), 'V')}")
            lines.append("")
            
            # Hysteresis Metrics
            hyst_metrics = analysis_data.get('hysteresis_metrics', {})
            lines.append("HYSTERESIS METRICS")
            lines.append("-" * 80)
            lines.append(f"Normalized Area (mean): {self._format_analysis_value(hyst_metrics.get('normalized_area_mean', 0))}")
            lines.append(f"Has Hysteresis: {'Yes' if hyst_metrics.get('has_hysteresis', False) else 'No'}")
            lines.append(f"Pinched Hysteresis: {'Yes' if hyst_metrics.get('pinched_hysteresis', False) else 'No'}")
            lines.append("")
            
            # Classification (if available)
            if analysis_level in ['classification', 'full', 'research']:
                class_data = analysis_data.get('classification', {})
                lines.append("CLASSIFICATION")
                lines.append("-" * 80)
                lines.append(f"Device Type: {class_data.get('device_type', 'N/A')}")
                lines.append(f"Confidence: {self._format_analysis_value(class_data.get('confidence', 0) * 100, '%', 1)}")
                lines.append(f"Conduction Mechanism: {class_data.get('conduction_mechanism', 'N/A')}")
                if class_data.get('model_r2', 0) > 0:
                    lines.append(f"Model R²: {self._format_analysis_value(class_data.get('model_r2', 0), '', 3)}")
                
                # === ENHANCED CLASSIFICATION (Phase 1) ===
                # Memristivity Score
                memristivity_score = class_data.get('memristivity_score')
                if memristivity_score is not None:
                    lines.append("")
                    lines.append(f"Memristivity Score: {memristivity_score:.1f}/100")
                    
                    # Breakdown of score
                    breakdown = class_data.get('memristivity_breakdown', {})
                    if breakdown:
                        lines.append("  Score Breakdown:")
                        for feature, score in breakdown.items():
                            if score > 0:
                                lines.append(f"    - {feature}: {score:.1f}/100")
                
                # Memory Window Quality
                mw_quality = class_data.get('memory_window_quality', {})
                if mw_quality.get('available', True):
                    lines.append("")
                    lines.append("Memory Window Quality:")
                    if 'overall_quality_score' in mw_quality:
                        lines.append(f"  Overall Quality: {mw_quality['overall_quality_score']:.1f}/100")
                    if 'avg_stability' in mw_quality:
                        lines.append(f"  State Stability: {mw_quality['avg_stability']:.1f}/100")
                    if 'separation_ratio' in mw_quality:
                        lines.append(f"  Separation Ratio: {mw_quality['separation_ratio']:.2f}")
                    if 'reproducibility' in mw_quality:
                        lines.append(f"  Reproducibility: {mw_quality['reproducibility']:.1f}/100")
                    if 'avg_switching_voltage' in mw_quality:
                        lines.append(f"  Avg Switching Voltage: {mw_quality['avg_switching_voltage']:.3f}V")
                
                # Hysteresis Shape
                hyst_shape = class_data.get('hysteresis_shape', {})
                if hyst_shape.get('has_hysteresis', False):
                    lines.append("")
                    lines.append("Hysteresis Shape Analysis:")
                    if 'figure_eight_quality' in hyst_shape:
                        lines.append(f"  Figure-8 Quality: {hyst_shape['figure_eight_quality']:.1f}/100")
                    if 'lobe_asymmetry' in hyst_shape:
                        lines.append(f"  Lobe Asymmetry: {hyst_shape['lobe_asymmetry']:.3f}")
                    if 'avg_hysteresis_width' in hyst_shape:
                        lines.append(f"  Avg Width: {self._format_analysis_value(hyst_shape['avg_hysteresis_width'], 'V')}")
                    if 'num_kinks_detected' in hyst_shape:
                        kinks = hyst_shape['num_kinks_detected']
                        if kinks > 0:
                            lines.append(f"  Kinks Detected: {kinks} (possible trapping)")
                
                # Warnings
                warnings = class_data.get('warnings', [])
                if warnings:
                    lines.append("")
                    lines.append("Classification Warnings:")
                    for warning in warnings:
                        lines.append(f"  ⚠ {warning}")
                
                lines.append("")
            
            # Performance Metrics (if available)
            if analysis_level in ['full', 'research']:
                perf_metrics = analysis_data.get('performance_metrics', {})
                lines.append("PERFORMANCE METRICS")
                lines.append("-" * 80)
                lines.append(f"Retention Score: {self._format_analysis_value(perf_metrics.get('retention_score', 0), '', 3)}")
                lines.append(f"Endurance Score: {self._format_analysis_value(perf_metrics.get('endurance_score', 0), '', 3)}")
                lines.append(f"Rectification Ratio: {self._format_analysis_value(perf_metrics.get('rectification_ratio_mean', 1))}")
                lines.append(f"Non-linearity: {self._format_analysis_value(perf_metrics.get('nonlinearity_mean', 0))}")
                if perf_metrics.get('power_consumption_mean', 0) > 0:
                    lines.append(f"Power Consumption: {self._format_analysis_value(perf_metrics.get('power_consumption_mean', 0), 'W')}")
                if perf_metrics.get('compliance_current') is not None:
                    lines.append(f"Compliance Current: {self._format_analysis_value(perf_metrics.get('compliance_current', 0), 'μA')}")
                lines.append("")
            
            # Research Diagnostics (if available)
            if analysis_level == 'research':
                research_data = analysis_data.get('research_diagnostics', {})
                if research_data:
                    lines.append("RESEARCH DIAGNOSTICS")
                    lines.append("-" * 80)
                    if research_data.get('switching_polarity'):
                        lines.append(f"Switching Polarity: {research_data.get('switching_polarity')}")
                    if research_data.get('ndr_index') is not None:
                        lines.append(f"NDR Index: {self._format_analysis_value(research_data.get('ndr_index', 0))}")
                    if research_data.get('hysteresis_direction'):
                        lines.append(f"Hysteresis Direction: {research_data.get('hysteresis_direction')}")
                    if research_data.get('loop_similarity_score') is not None:
                        lines.append(f"Loop Similarity Score: {self._format_analysis_value(research_data.get('loop_similarity_score', 0), '', 3)}")
                    if research_data.get('noise_floor') is not None:
                        lines.append(f"Noise Floor: {self._format_analysis_value(research_data.get('noise_floor', 0), 'A')}")
                    lines.append("")
            
            lines.append("=" * 80)
            lines.append("End of Analysis Report")
            lines.append("=" * 80)
            
            # Write to file
            with open(analysis_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            
            debug_print(f"[ANALYSIS] Results saved to: {os.path.abspath(analysis_file)}")
            
            # Update classification log if classification-level analysis was performed
            if analysis_level in ['classification', 'full', 'research']:
                try:
                    # Get device directory from save_dir (should be G/{device_num}/)
                    # If save_dir is already device-level, use it; otherwise try to extract
                    device_dir = save_dir
                    
                    # If save_dir is sample-level, try to construct device directory
                    if 'sample_analysis' in save_dir or not os.path.basename(save_dir).isdigit():
                        # Try to extract device directory from path or use a fallback
                        # For now, use save_dir as-is and let _append_classification_log handle it
                        pass
                    
                    self._append_classification_log(
                        save_dir=device_dir,
                        file_name=file_name,
                        analysis_data=analysis_data
                    )
                except Exception as log_exc:
                    debug_print(f"[ANALYSIS] Failed to update classification log: {log_exc}")
                    # Non-critical error, don't fail the whole save operation
            
        except Exception as exc:
            debug_print(f"[ANALYSIS ERROR] Failed to save analysis results: {exc}")
            import traceback
            traceback.print_exc()
    
    def _save_research_analysis(
        self,
        research_data: Dict[str, Any],
        save_dir: str,
        file_name: str,
        device_id: str
    ):
        """
        Save research-level analysis to device-specific folder.
        
        Parameters:
        -----------
        research_data : dict
            Research analysis results
        save_dir : str
            Base save directory
        file_name : str
            Measurement filename
        device_id : str
            Device identifier
        """
        try:
            import os
            import json
            from datetime import datetime
            
            # Save research data in sweep_analysis folder within device directory
            # New structure: G/{device_num}/sweep_analysis/{filename}_research.json
            research_dir = os.path.join(save_dir, "sweep_analysis")
            os.makedirs(research_dir, exist_ok=True)
            
            # Save as JSON for easy parsing
            research_file = os.path.join(research_dir, f"{file_name}_research.json")
            
            # Convert numpy types for JSON serialization
            def convert_types(obj):
                import numpy as np
                if isinstance(obj, np.bool_):
                    return bool(obj)
                elif isinstance(obj, np.integer):
                    return int(obj)
                elif isinstance(obj, np.floating):
                    return float(obj)
                elif isinstance(obj, np.ndarray):
                    return obj.tolist()
                elif isinstance(obj, dict):
                    return {key: convert_types(value) for key, value in obj.items()}
                elif isinstance(obj, list):
                    return [convert_types(item) for item in obj]
                return obj
            
            serializable_data = convert_types(research_data)
            serializable_data['saved_timestamp'] = datetime.now().isoformat()
            
            with open(research_file, 'w') as f:
                json.dump(serializable_data, f, indent=2)
            
            debug_print(f"[RESEARCH] Saved to: {research_file}")
            
            # Also append to classification log
            try:
                self._append_classification_log(save_dir, file_name, research_data)
            except Exception as log_exc:
                debug_print(f"[CLASSIFICATION LOG ERROR] Failed to append log: {log_exc}")
            
        except Exception as e:
            debug_print(f"[RESEARCH ERROR] Failed to save research analysis: {e}")

    def _append_classification_log(
        self,
        save_dir: str,
        file_name: str,
        analysis_data: Dict[str, Any]
    ) -> None:
        """
        Append classification results to device-level log file.
        
        Creates/appends to: {save_dir}/classification_log.txt
        
        Parameters:
        -----------
        save_dir : str
            Device directory (e.g., G/1/)
        file_name : str
            Measurement filename
        analysis_data : Dict[str, Any]
            Analysis results containing classification data
        """
        try:
            import os
            from datetime import datetime
            
            # Log file path
            log_file = os.path.join(save_dir, "classification_log.txt")
            summary_log_file = os.path.join(save_dir, "classification_summary.txt")
            
            # Extract classification data
            classification = analysis_data.get('classification', {})
            device_type = classification.get('device_type', 'unknown')
            confidence = classification.get('confidence', 0.0)
            memristivity_score = classification.get('memristivity_score', 0.0)
            switching_strength = classification.get('switching_strength', 0.0)
            reasoning = classification.get('reasoning', '')
            warnings = classification.get('warnings', [])
            
            # Get breakdown scores
            breakdown = classification.get('breakdown', {})
            
            # Format log entry
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            separator = "=" * 80
            
            # Check if file exists to determine if we need a header
            file_exists = os.path.exists(log_file)
            
            # === DETAILED LOG FILE ===
            with open(log_file, 'a') as f:
                # Add header if new file
                if not file_exists:
                    f.write(separator + "\n")
                    f.write("DEVICE CLASSIFICATION LOG (DETAILED)\n")
                    f.write(f"Device: {os.path.basename(save_dir)}\n")
                    f.write(f"Created: {timestamp}\n")
                    f.write(f"\n")
                    f.write("NOTE: For quick reference, see classification_summary.txt\n")
                    f.write(separator + "\n\n")
                
                # Write entry
                f.write(f"{separator}\n")
                f.write(f"Sweep: {file_name}\n")
                f.write(f"Timestamp: {timestamp}\n")
                f.write(f"\n")
                f.write(f"CLASSIFICATION: {device_type.upper()}\n")
                f.write(f"Confidence: {confidence:.1%}\n")
                f.write(f"Memristivity Score: {memristivity_score:.1f}/100\n")
                f.write(f"Switching Strength: {switching_strength:.1f}/100\n")
                f.write(f"\n")
                
                # Score breakdown
                f.write(f"Score Breakdown:\n")
                for dtype, score in sorted(breakdown.items(), key=lambda x: x[1], reverse=True):
                    if score > 0:
                        f.write(f"  - {dtype:15s}: {score:6.1f}\n")
                f.write(f"\n")
                
                # Detailed explanation/reasoning
                if reasoning:
                    f.write("DETAILED EXPLANATION:\n")
                    f.write("-" * 80 + "\n")
                    # Add proper indentation to multiline reasoning
                    for line in reasoning.split('\n'):
                        f.write(f"{line}\n")
                    f.write("\n")
                
                # Warnings (red flags)
                if warnings and len(warnings) > 0:
                    f.write("⚠ WARNINGS / RED FLAGS:\n")
                    f.write("-" * 80 + "\n")
                    for i, warning in enumerate(warnings, 1):
                        # Wrap long warnings to 75 characters
                        import textwrap
                        wrapped = textwrap.fill(warning, width=75, initial_indent=f"  {i}. ", 
                                               subsequent_indent="     ")
                        f.write(wrapped + "\n")
                    f.write("\n")
                else:
                    f.write("No warnings detected.\n\n")
            
            # === SUMMARY FILE (Quick Reference) ===
            # Read existing summary to update/append
            summary_entries = []
            summary_exists = os.path.exists(summary_log_file)
            
            if summary_exists:
                # Read existing entries
                try:
                    with open(summary_log_file, 'r') as f:
                        lines = f.readlines()
                        # Skip header lines and parse entries
                        for line in lines:
                            if ' - ' in line and not line.startswith('=') and not line.startswith('QUICK'):
                                summary_entries.append(line.strip())
                except:
                    pass
            
            # Add new entry
            confidence_emoji = "✓" if confidence >= 0.75 else "~" if confidence >= 0.5 else "?"
            score_emoji = "🟢" if memristivity_score >= 70 else "🟡" if memristivity_score >= 40 else "🔴"
            new_entry = f"{file_name:50s} - {device_type.upper():15s} {confidence_emoji} ({confidence:.0%}) {score_emoji} {memristivity_score:.0f}/100"
            summary_entries.append(new_entry)
            
            # Write updated summary
            with open(summary_log_file, 'w') as f:
                f.write(separator + "\n")
                f.write("QUICK CLASSIFICATION SUMMARY\n")
                f.write(f"Device: {os.path.basename(save_dir)}\n")
                f.write(f"Updated: {timestamp}\n")
                f.write(separator + "\n")
                f.write("Format: Sweep Name - Classification ✓/~/? (Confidence) 🟢/🟡/🔴 Score/100\n")
                f.write("Legend: ✓=High confidence, ~=Medium, ?=Low | 🟢=Strong, 🟡=Moderate, 🔴=Weak\n")
                f.write(separator + "\n\n")
                
                for entry in summary_entries:
                    f.write(entry + "\n")
            
            debug_print(f"[CLASSIFICATION LOG] Appended to: {log_file}")
            debug_print(f"[CLASSIFICATION LOG] Updated summary: {summary_log_file}")
            
        except Exception as e:
            debug_print(f"[CLASSIFICATION LOG ERROR] Failed to write log: {e}")
            import traceback
            traceback.print_exc()

    def _plot_measurement_in_background(
        self,
        voltage,
        current,
        timestamps,
        save_dir: str,
        device_name: str,
        sweep_number: int,
        is_memristive: Optional[bool] = None,
        filename: Optional[str] = None
    ) -> None:
        """
        Plot measurement graphs in background thread using UnifiedPlotter.
        
        Always plots basic IV dashboard. If memristive, also plots advanced analysis.
        Saves to {save_dir}/Graphs/{filename}_graph/, {filename}_conduction/, {filename}_sclc_fit/ folders.
        
        Args:
            voltage: Voltage array
            current: Current array
            timestamps: Optional time array
            save_dir: Directory where measurement was saved
            device_name: Device identifier (e.g., "A1", "B5")
            sweep_number: Sweep number
            is_memristive: Optional memristive flag. If None, will check from analysis.
            filename: Optional measurement filename (without .txt). If None, will try to extract from save_dir.
        """
        def run_plotting():
            try:
                import sys
                from pathlib import Path
                import matplotlib
                
                # Set non-interactive backend for background thread (prevents GUI/LaTeX issues)
                matplotlib.use('Agg')
                
                # Import UnifiedPlotter from plotting_core
                # Try direct import first, then add to path if needed
                try:
                    from Helpers.plotting_core import UnifiedPlotter
                except ImportError:
                    # Fallback: add to path and import
                    plotting_core_path = Path(__file__).resolve().parents[2] / "Helpers" / "plotting_core"
                    if str(plotting_core_path.parent) not in sys.path:
                        sys.path.insert(0, str(plotting_core_path.parent))
                    from plotting_core import UnifiedPlotter
                
                # Disable LaTeX rendering FIRST to avoid parsing errors in background thread
                import matplotlib.pyplot as plt
                import matplotlib
                # Set backend first
                matplotlib.use('Agg')
                # Disable all LaTeX/math text
                plt.rcParams['text.usetex'] = False
                plt.rcParams['mathtext.default'] = 'regular'
                plt.rcParams['axes.formatter.use_mathtext'] = False
                # Force plain text for all formatters
                plt.rcParams['axes.formatter.min_exponent'] = 0
                plt.rcParams['axes.unicode_minus'] = False
                
                # Create Graphs folder in device directory
                graphs_dir = os.path.join(save_dir, "Graphs")
                os.makedirs(graphs_dir, exist_ok=True)
                
                # Determine filename if not provided (use local variable to avoid scoping issues)
                plot_filename = filename  # Capture from outer scope
                if plot_filename is None:
                    # Try to find the most recent .txt file in save_dir
                    try:
                        txt_files = [f for f in os.listdir(save_dir) if f.endswith('.txt')]
                        if txt_files:
                            # Get the most recently modified file
                            txt_files_with_time = [(f, os.path.getmtime(os.path.join(save_dir, f))) for f in txt_files]
                            txt_files_with_time.sort(key=lambda x: x[1], reverse=True)
                            latest_file = txt_files_with_time[0][0]
                            # Remove .txt extension
                            plot_filename = os.path.splitext(latest_file)[0]
                        else:
                            # Fallback: construct from device name and sweep number
                            plot_filename = f"{device_name}_sweep_{sweep_number}"
                    except Exception:
                        plot_filename = f"{device_name}_sweep_{sweep_number}"
                
                # Create folder structure:
                # - Graphs/ for dashboard plots (directly in Graphs folder)
                # - Graphs/sclc_fit/ for all SCLC plots (shared folder)
                # - Graphs/conduction/ for all conduction plots (shared folder)
                conduction_dir = os.path.join(graphs_dir, "conduction")
                sclc_dir = os.path.join(graphs_dir, "sclc_fit")
                
                # Dashboard goes directly in Graphs folder (no subfolder)
                if is_memristive:
                    os.makedirs(conduction_dir, exist_ok=True)
                    os.makedirs(sclc_dir, exist_ok=True)
                
                # Determine if memristive (check from analysis if not provided)
                if is_memristive is None:
                    # Try to get from latest analysis result
                    try:
                        # Check if we have analysis data for this sweep
                        # This will be set by _run_analysis_if_enabled
                        memristivity_score = 0
                        if hasattr(self, '_last_analysis_result'):
                            analysis = self._last_analysis_result
                            if isinstance(analysis, dict):
                                classification = analysis.get('classification', {})
                                memristivity_score = classification.get('memristivity_score', 0)
                        
                        is_memristive_flag = memristivity_score > 60
                    except Exception:
                        is_memristive_flag = False
                else:
                    is_memristive_flag = is_memristive
                
                # Use filename for plot names instead of device_name_sweep_number
                sample_name = self.sample_name_var.get() if hasattr(self, 'sample_name_var') else ""
                title_prefix = f"{sample_name} {device_name}" if sample_name else device_name
                
                # Plot basic IV dashboard (always) - save directly in Graphs folder
                plotter_graph = UnifiedPlotter(save_dir=graphs_dir, auto_close=True)
                # Use plot_iv_dashboard directly to specify exact filename
                plotter_graph.plot_iv_dashboard(
                    voltage=voltage,
                    current=current,
                    time=timestamps,
                    device_name=plot_filename,  # Use filename instead of device_name_sweep
                    title=f"{title_prefix} {plot_filename} - IV Dashboard",
                    save_name=f"{plot_filename}_iv_dashboard.png"
                )
                
                # Plot advanced analysis if memristive - save with filename in shared folders
                if is_memristive_flag:
                    plotter_cond = UnifiedPlotter(save_dir=conduction_dir, auto_close=True)
                    plotter_cond.plot_conduction_analysis(
                        voltage=voltage,
                        current=current,
                        device_name=plot_filename,  # Use filename
                        title=f"{title_prefix} {plot_filename} - Conduction Analysis",
                        save_name=f"{plot_filename}_conduction.png"  # Explicit filename
                    )
                    
                    plotter_sclc = UnifiedPlotter(save_dir=sclc_dir, auto_close=True)
                    plotter_sclc.plot_sclc_fit(
                        voltage=voltage,
                        current=current,
                        device_name=plot_filename,  # Use filename
                        title=f"{title_prefix} {plot_filename} - SCLC Fit",
                        save_name=f"{plot_filename}_sclc_fit.png"  # Explicit filename
                    )
                
                debug_print(f"[PLOT] Generated plots for {plot_filename} (memristive={is_memristive_flag})")
                debug_print(f"[PLOT] Dashboard saved to: {graphs_dir}")
                if is_memristive_flag:
                    debug_print(f"[PLOT] Conduction plot: {os.path.join(conduction_dir, plot_filename + '_conduction.png')}")
                    debug_print(f"[PLOT] SCLC plot: {os.path.join(sclc_dir, plot_filename + '_sclc_fit.png')}")
                
            except ImportError as e:
                debug_print(f"[PLOT ERROR] Failed to import UnifiedPlotter: {e}")
                debug_print(f"[PLOT ERROR] Make sure plotting_core is available")
            except Exception as e:
                debug_print(f"[PLOT ERROR] Background plotting failed: {e}")
                import traceback
                traceback.print_exc()
        
        # Start background thread (daemon so it doesn't block exit)
        plot_thread = threading.Thread(target=run_plotting, daemon=True)
        plot_thread.start()
        debug_print(f"[PLOT] Background plotting queued for {device_name} sweep {sweep_number}")

    def _generate_sequence_summary(
        self,
        device_id: str,
        sequence_name: str,
        sequence_results: List[Dict[str, Any]],
        save_dir: str,
        total_sweeps: int
    ) -> None:
        """
        Generate comprehensive summary report for custom measurement sequence.
        
        Designed for batch overnight testing (100+ devices).
        
        Creates:
        - Text summary (sample_analysis/device_summaries/{device_id}_{sequence_name}_summary.txt)
        - JSON data (sample_analysis/device_summaries/{device_id}_{sequence_name}_summary.json)
        
        Parameters:
        -----------
        device_id : str
            Device identifier (e.g., "sample_A_1")
        sequence_name : str
            Name of the custom measurement sequence
        sequence_results : List[Dict[str, Any]]
            List of analysis results for each analyzed sweep
            Each dict should have: {'sweep_number': int, 'voltage': float, 'analysis': dict}
        save_dir : str
            Base save directory (device-level)
        total_sweeps : int
            Total number of sweeps in sequence
        """
        try:
            import os
            import json
            from datetime import datetime
            import numpy as np
            
            # Create summaries directory at sample level
            sample_name = self.sample_name_var.get() if hasattr(self, 'sample_name_var') else None
            if not sample_name:
                debug_print("[SUMMARY ERROR] No sample name available")
                return
            
            sample_save_dir = self._get_sample_save_directory(sample_name)
            # Use unified sample_analysis folder structure
            summary_dir = os.path.join(sample_save_dir, "sample_analysis", "device_summaries")
            os.makedirs(summary_dir, exist_ok=True)
            
            # Extract key metrics from all analyzed sweeps
            scores = []
            voltages = []
            best_sweep = None
            worst_sweep = None
            
            for result in sequence_results:
                classification = result['analysis'].get('classification', {})
                score = classification.get('memristivity_score', 0)
                scores.append(score)
                voltages.append(result['voltage'])
                
                # Track best/worst
                if best_sweep is None or score > best_sweep['score']:
                    best_sweep = {'sweep': result['sweep_number'], 'score': score, 'voltage': result['voltage']}
                if worst_sweep is None or score < worst_sweep['score']:
                    worst_sweep = {'sweep': result['sweep_number'], 'score': score, 'voltage': result['voltage']}
            
            # Calculate overall device score (weighted average favoring later sweeps)
            # Later sweeps more important for formed devices
            weights = np.linspace(0.5, 1.0, len(scores)) if len(scores) > 0 else np.array([1.0])
            overall_score = np.average(scores, weights=weights) if scores else 0
            
            # Determine final device status
            final_classification = sequence_results[-1]['analysis'].get('classification', {}) if sequence_results else {}
            final_device_type = final_classification.get('device_type', 'unknown')
            
            # Detect forming process
            score_improvement = scores[-1] - scores[0] if len(scores) > 1 else 0
            is_forming = score_improvement > 15  # >15 point improvement
            
            # === TEXT SUMMARY ===
            lines = []
            lines.append("=" * 80)
            lines.append(f"CUSTOM MEASUREMENT SEQUENCE SUMMARY")
            lines.append("=" * 80)
            lines.append(f"Device: {device_id}")
            lines.append(f"Sequence: {sequence_name}")
            lines.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append(f"Total Sweeps: {total_sweeps}")
            lines.append(f"Analyzed Sweeps: {len(scores)} (memristive sweeps only)")
            lines.append("")
            
            lines.append("OVERALL ASSESSMENT")
            lines.append("-" * 80)
            lines.append(f"Overall Device Score: {overall_score:.1f}/100")
            # Handle None case for final_device_type
            final_type_str = (final_device_type or 'UNKNOWN').upper() if isinstance(final_device_type, str) else 'UNKNOWN'
            lines.append(f"Final Classification: {final_type_str}")
            
            # Rating
            if overall_score >= 80:
                rating = "EXCELLENT - Ready for advanced testing"
            elif overall_score >= 60:
                rating = "GOOD - Suitable for basic memristive applications"
            elif overall_score >= 40:
                rating = "FAIR - May need additional forming"
            else:
                rating = "POOR - Not suitable for memristive applications"
            lines.append(f"Rating: {rating}")
            
            if is_forming:
                lines.append(f"Forming Detected: YES (improved {score_improvement:.1f} points)")
            lines.append("")
            
            lines.append("KEY SWEEPS")
            lines.append("-" * 80)
            if best_sweep:
                lines.append(f"Best Sweep: #{best_sweep['sweep']} @ {best_sweep['voltage']:.1f}V (Score: {best_sweep['score']:.1f})")
            if worst_sweep and worst_sweep['sweep'] != best_sweep['sweep']:
                lines.append(f"Worst Sweep: #{worst_sweep['sweep']} @ {worst_sweep['voltage']:.1f}V (Score: {worst_sweep['score']:.1f})")
            lines.append("")
            
            lines.append("SWEEP-BY-SWEEP PROGRESSION")
            lines.append("-" * 80)
            for result in sequence_results:
                classification = result['analysis'].get('classification', {})
                score = classification.get('memristivity_score', 0)
                device_type = classification.get('device_type', 'unknown')
                lines.append(f"Sweep #{result['sweep_number']:2d} @ {result['voltage']:4.1f}V: "
                            f"{device_type:12s} Score: {score:5.1f}/100")
            lines.append("")
            
            lines.append("DETAILED METRICS (Final Sweep)")
            lines.append("-" * 80)
            if sequence_results:
                final_analysis = sequence_results[-1]['analysis']
                
                # Resistance
                resistance = final_analysis.get('resistance_metrics', {})
                lines.append(f"Ron (mean):  {resistance.get('ron_mean', 0):.2e} Ω")
                lines.append(f"Roff (mean): {resistance.get('roff_mean', 0):.2e} Ω")
                lines.append(f"Switching Ratio: {resistance.get('switching_ratio_mean', 0):.1f}")
                lines.append("")
                
                # Hysteresis
                hysteresis = final_analysis.get('hysteresis_metrics', {})
                lines.append(f"Hysteresis: {('Yes' if hysteresis.get('has_hysteresis') else 'No')}")
                lines.append(f"Pinched: {('Yes' if hysteresis.get('pinched_hysteresis') else 'No')}")
                lines.append("")
                
                # Quality metrics
                if 'memory_window_quality' in final_classification:
                    quality = final_classification['memory_window_quality']
                    lines.append(f"Memory Window Quality: {quality.get('overall_quality_score', 0):.1f}/100")
                lines.append("")
            
            lines.append("=" * 80)
            lines.append("NOTES FOR BATCH PROCESSING:")
            lines.append(f"- Data Location: {save_dir}")
            lines.append(f"- Device Tracking: {sample_save_dir}/sample_analysis/analysis/device_tracking/{device_id}_history.json")
            if overall_score > 60:
                lines.append(f"- Research Data: {save_dir}/sweep_analysis/")
            lines.append(f"- Classification Summary: {save_dir}/classification_summary.txt (quick reference)")
            lines.append(f"- Classification Log: {save_dir}/classification_log.txt (detailed)")
            lines.append("")
            lines.append("FUTURE ENHANCEMENTS:")
            lines.append("- [ ] Trend plots (score vs voltage, Ron/Roff evolution)")
            lines.append("- [ ] Comparative analysis across devices")
            lines.append("- [ ] Statistical summary for entire sample (100+ devices)")
            lines.append("- [ ] Automated report generation (PDF/HTML)")
            lines.append("=" * 80)

            # Save text summary
            text_file = os.path.join(summary_dir, f"{device_id}_{sequence_name}_summary.txt")
            with open(text_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))

            # === JSON SUMMARY (for programmatic access) ===
            json_summary = {
                'device_id': device_id,
                'sequence_name': sequence_name,
                'timestamp': datetime.now().isoformat(),
                'total_sweeps': total_sweeps,
                'analyzed_sweeps': len(scores),
                'overall_score': float(overall_score),
                'final_device_type': final_device_type,
                'forming_detected': is_forming,
                'score_improvement': float(score_improvement) if score_improvement else 0,
                'best_sweep': best_sweep,
                'worst_sweep': worst_sweep,
                'sweep_progression': [
                    {
                        'sweep_number': r['sweep_number'],
                        'voltage': r['voltage'],
                        'score': r['analysis'].get('classification', {}).get('memristivity_score', 0),
                        'device_type': r['analysis'].get('classification', {}).get('device_type', 'unknown')
                    }
                    for r in sequence_results
                ],
                'final_metrics': {
                    'resistance': sequence_results[-1]['analysis'].get('resistance_metrics', {}) if sequence_results else {},
                    'hysteresis': sequence_results[-1]['analysis'].get('hysteresis_metrics', {}) if sequence_results else {},
                    'classification': final_classification
                },
                'data_locations': {
                    'raw_data': save_dir,
                    'tracking': f"{sample_save_dir}/sample_analysis/analysis/device_tracking/{device_id}_history.json",
                    'research': f"{save_dir}/sweep_analysis/" if overall_score > 60 else None,
                    'classification_summary': f"{save_dir}/classification_summary.txt",
                    'classification_log': f"{save_dir}/classification_log.txt"
                }
            }
            
            # Convert numpy types for JSON serialization
            def convert_types(obj):
                if isinstance(obj, np.bool_):
                    return bool(obj)
                elif isinstance(obj, np.integer):
                    return int(obj)
                elif isinstance(obj, np.floating):
                    return float(obj)
                elif isinstance(obj, np.ndarray):
                    return obj.tolist()
                elif isinstance(obj, dict):
                    return {key: convert_types(value) for key, value in obj.items()}
                elif isinstance(obj, list):
                    return [convert_types(item) for item in obj]
                return obj
            
            serializable_summary = convert_types(json_summary)
            
            # Save JSON summary
            json_file = os.path.join(summary_dir, f"{device_id}_{sequence_name}_summary.json")
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(serializable_summary, f, indent=2, ensure_ascii=False)
            
            debug_print(f"[SUMMARY] Sequence summary saved:")
            debug_print(f"[SUMMARY]   Text: {text_file}")
            debug_print(f"[SUMMARY]   JSON: {json_file}")
            # Handle None case for final_device_type
            final_type_str = (final_device_type or 'UNKNOWN').upper() if isinstance(final_device_type, str) else 'UNKNOWN'
            debug_print(f"[SUMMARY]   Overall Score: {overall_score:.1f}/100 ({final_type_str})")
            
        except Exception as e:
            debug_print(f"[SUMMARY ERROR] Failed to generate sequence summary: {e}")
            import traceback
            traceback.print_exc()
    
    def update_classification_display(self, classification_data: Dict[str, Any]) -> None:
        """Update top bar with classification and score"""
        try:
            device_type = classification_data.get('device_type', '')
            score = classification_data.get('memristivity_score')
            
            if not score:
                return
            
            # Color based on score
            if score >= 80:
                color = "#4CAF50"  # Green
            elif score >= 60:
                color = "#FFA500"  # Orange
            elif score >= 40:
                color = "#FF9800"  # Deep orange
            else:
                color = "#F44336"  # Red
            
            if hasattr(self, 'classification_label'):
                text = f"| {device_type.title()} ({score:.1f}/100)"
                self.classification_label.config(text=text, fg=color)
        except Exception as e:
            print(f"[CLASSIFICATION DISPLAY] Error updating: {e}")
    
    def refresh_stats_list(self):
        """Refresh list of tracked devices"""
        try:
            import os
            
            # Get save directory
            sample_name = self.sample_name_var.get() if hasattr(self, 'sample_name_var') else ""
            if not sample_name:
                # Show message in stats display
                if hasattr(self, 'stats_text_widget'):
                    self.stats_text_widget.config(state=tk.NORMAL)
                    self.stats_text_widget.delete('1.0', tk.END)
                    self.stats_text_widget.insert('1.0', 
                        "No sample selected.\n\n"
                        "Please select a sample in the Sample GUI first,\n"
                        "then run some measurements to track devices.\n\n"
                        "Device tracking data will appear here after\n"
                        "you complete measurements."
                    )
                    self.stats_text_widget.config(state=tk.DISABLED)
                print("[STATS] No sample name set - cannot load device tracking")
                return
            
            # Use sample-level directory (not device-level)
            save_root = self._get_sample_save_directory(sample_name)
            tracking_dir = os.path.join(save_root, "sample_analysis", "analysis", "device_tracking")
            legacy_tracking_dir = os.path.join(save_root, "sample_analysis", "device_tracking")
            old_legacy_tracking_dir = os.path.join(save_root, "device_tracking")
            
            # List all device history files (check new location first, then legacy)
            devices = []
            for check_dir in [tracking_dir, legacy_tracking_dir, old_legacy_tracking_dir]:
                if os.path.exists(check_dir):
                    for file in os.listdir(check_dir):
                        if file.endswith('_history.json'):
                            device_id = file.replace('_history.json', '')
                            if device_id not in devices:  # Avoid duplicates
                                devices.append(device_id)
                    if devices:  # Found devices, stop checking other locations
                        break
            
            # Update combobox
            if hasattr(self, 'stats_device_combo'):
                self.stats_device_combo['values'] = sorted(devices)
                
                if devices:
                    # Select first device if none selected
                    if not self.stats_device_var.get():
                        self.stats_device_var.set(devices[0])
                    self.update_stats_display()
                    print(f"[STATS] Found {len(devices)} tracked device(s)")
                else:
                    # No devices found - show helpful message
                    self.stats_device_var.set("")
                    if hasattr(self, 'stats_text_widget'):
                        self.stats_text_widget.config(state=tk.NORMAL)
                        self.stats_text_widget.delete('1.0', tk.END)
                        self.stats_text_widget.insert('1.0', 
                            f"No device tracking data found for sample: {sample_name}\n\n"
                            "Run some measurements to start tracking devices.\n\n"
                            "After each measurement with analysis enabled,\n"
                            "device statistics will be saved to:\n"
                            f"{tracking_dir}\n\n"
                            "Then refresh this tab to see tracked devices."
                        )
                        self.stats_text_widget.config(state=tk.DISABLED)
                    
                    # Clear plots
                    self._clear_stats_plots()
                    print(f"[STATS] No tracked devices found in {tracking_dir}")
        
        except Exception as e:
            print(f"[STATS] Error refreshing device list: {e}")
            import traceback
            traceback.print_exc()
    
    def update_stats_display(self):
        """Display device tracking stats"""
        try:
            import json
            import os
            from datetime import datetime
            
            device_id = self.stats_device_var.get()
            if not device_id:
                return
            
            # Load device history
            sample_name = self.sample_name_var.get() if hasattr(self, 'sample_name_var') else ""
            # Use sample-level directory (not device-level)
            save_root = self._get_sample_save_directory(sample_name)
            history_file = os.path.join(save_root, "sample_analysis", "analysis", "device_tracking", f"{device_id}_history.json")
            
            if not os.path.exists(history_file):
                if hasattr(self, 'stats_text_widget'):
                    self.stats_text_widget.config(state=tk.NORMAL)
                    self.stats_text_widget.delete('1.0', tk.END)
                    self.stats_text_widget.insert('1.0', f"Device tracking file not found:\n{history_file}")
                    self.stats_text_widget.config(state=tk.DISABLED)
                return
            
            with open(history_file, 'r') as f:
                history = json.load(f)
            
            # Format display
            lines = []
            lines.append(f"{'='*80}")
            lines.append(f"DEVICE STATISTICS: {device_id}")
            lines.append(f"{'='*80}")
            lines.append("")
            
            lines.append(f"Total Measurements: {history.get('total_measurements', 0)}")
            
            # === FORMING STATUS ===
            # Only show if we have enough data
            measurements = history.get('all_measurements', [])
            if len(measurements) >= 3:
                from datetime import datetime
                # Load measurements to analyze forming
                mem_scores = []
                sw_ratios = []
                rs_on = []
                rs_off = []
                vs = []
                for m in measurements:
                    c = m.get('classification', {})
                    if c.get('memristivity_score'):
                        mem_scores.append(c['memristivity_score'])
                    r = m.get('resistance', {})
                    if r.get('ron_mean'):
                        rs_on.append(r['ron_mean'])
                    if r.get('roff_mean'):
                        rs_off.append(r['roff_mean'])
                    if r.get('switching_ratio'):
                        sw_ratios.append(r['switching_ratio'])
                    v = m.get('voltage', {})
                    if v.get('max_voltage'):
                        vs.append(abs(v['max_voltage']))
                
                forming_info = self._analyze_forming_process(mem_scores, sw_ratios, rs_on, rs_off, vs)
                status = forming_info['status']
                confidence = forming_info['confidence']
                
                status_display = {
                    'forming': '🔧 FORMING',
                    'formed': '✓ FORMED',
                    'degrading': '⚠ DEGRADING',
                    'unstable': '⚠ UNSTABLE',
                    'stable': '→ STABLE'
                }
                # Handle None case for status
                if status and isinstance(status, str):
                    status_text = status_display.get(status, status.upper())
                else:
                    status_text = 'UNKNOWN'
                lines.append(f"Device Status: {status_text} ({confidence*100:.0f}% confidence)")
                
                if status == 'forming':
                    progress = forming_info['progress']
                    lines.append(f"Forming Progress: {progress}% complete")
                
                if forming_info['indicators']:
                    lines.append("Evidence:")
                    for indicator in forming_info['indicators']:
                        lines.append(f"  • {indicator}")
                
                lines.append("")
            
            # Format timestamps nicely
            created = history.get('created', 'N/A')
            if created != 'N/A':
                try:
                    dt = datetime.fromisoformat(created)
                    created = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    pass
            lines.append(f"First Measurement: {created}")
            
            last_updated = history.get('last_updated', 'N/A')
            if last_updated != 'N/A':
                try:
                    dt = datetime.fromisoformat(last_updated)
                    last_updated = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    pass
            lines.append(f"Last Updated: {last_updated}")
            lines.append("")
            
            # Get recent measurements
            measurements = history.get('measurements', [])
            if measurements:
                latest = measurements[-1]
                
                lines.append("LATEST MEASUREMENT")
                lines.append("-" * 80)
                
                timestamp = latest.get('timestamp', 'N/A')
                if timestamp != 'N/A':
                    try:
                        dt = datetime.fromisoformat(timestamp)
                        timestamp = dt.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        pass
                lines.append(f"Timestamp: {timestamp}")
                lines.append(f"Cycle: {latest.get('cycle_number', 'N/A')}")
                lines.append("")
                
                # Classification
                classification = latest.get('classification', {})
                lines.append("CLASSIFICATION")
                lines.append("-" * 40)
                # Handle None case for device_type
                device_type = classification.get('device_type') or 'N/A'
                device_type_str = device_type.upper() if isinstance(device_type, str) else 'N/A'
                lines.append(f"  Device Type: {device_type_str}")
                lines.append(f"  Confidence: {classification.get('confidence', 0)*100:.1f}%")
                
                score = classification.get('memristivity_score', 0)
                score_str = f"{score:.1f}/100"
                if score >= 80:
                    score_str += " (Excellent)"
                elif score >= 60:
                    score_str += " (Good)"
                elif score >= 40:
                    score_str += " (Fair)"
                else:
                    score_str += " (Poor)"
                lines.append(f"  Memristivity Score: {score_str}")
                lines.append(f"  Conduction: {classification.get('conduction_mechanism', 'N/A')}")
                lines.append("")
                
                # Resistance
                resistance = latest.get('resistance', {})
                lines.append("RESISTANCE METRICS")
                lines.append("-" * 40)
                ron = resistance.get('ron_mean')
                roff = resistance.get('roff_mean')
                if ron is not None:
                    lines.append(f"  Ron (mean): {ron:.2e} Ω")
                if roff is not None:
                    lines.append(f"  Roff (mean): {roff:.2e} Ω")
                if resistance.get('switching_ratio'):
                    lines.append(f"  Switching Ratio: {resistance.get('switching_ratio', 0):.2f}")
                if resistance.get('on_off_ratio'):
                    lines.append(f"  ON/OFF Ratio: {resistance.get('on_off_ratio', 0):.2f}")
                lines.append("")
                
                # Hysteresis
                hysteresis = latest.get('hysteresis', {})
                if hysteresis:
                    lines.append("HYSTERESIS")
                    lines.append("-" * 40)
                    lines.append(f"  Has Hysteresis: {'Yes' if hysteresis.get('has_hysteresis') else 'No'}")
                    lines.append(f"  Pinched: {'Yes' if hysteresis.get('pinched') else 'No'}")
                    if hysteresis.get('normalized_area'):
                        lines.append(f"  Normalized Area: {hysteresis.get('normalized_area'):.3f}")
                    lines.append("")
                
                # Quality metrics
                quality = latest.get('quality', {})
                if quality and quality.get('memory_window_quality'):
                    lines.append("QUALITY METRICS")
                    lines.append("-" * 40)
                    lines.append(f"  Memory Window: {quality.get('memory_window_quality'):.1f}/100")
                    if quality.get('stability'):
                        lines.append(f"  Stability: {quality.get('stability'):.1f}/100")
                    lines.append("")
                
                # Trends over time
                if len(measurements) > 1:
                    lines.append("TRENDS OVER TIME")
                    lines.append("-" * 40)
                    lines.append(f"  Measurements: {len(measurements)}")
                    
                    # Memristivity scores
                    scores = [m['classification'].get('memristivity_score') for m in measurements 
                             if m.get('classification', {}).get('memristivity_score') is not None]
                    if len(scores) > 1:
                        trend = "↓ declining" if scores[-1] < scores[0] * 0.9 else "→ stable"
                        if scores[-1] > scores[0] * 1.1:
                            trend = "↑ improving"
                        lines.append(f"  Memristivity: {scores[0]:.1f} → {scores[-1]:.1f} ({trend})")
                    
                    # Ron drift
                    rons = [m['resistance'].get('ron_mean') for m in measurements
                           if m.get('resistance', {}).get('ron_mean') is not None]
                    if len(rons) > 1:
                        drift_pct = (rons[-1] - rons[0]) / (rons[0] + 1e-20) * 100
                        drift_str = f"{drift_pct:+.1f}%"
                        if abs(drift_pct) > 20:
                            drift_str += " (significant)"
                        lines.append(f"  Ron Drift: {drift_str}")
                    
                    # Classification changes
                    types = [m['classification'].get('device_type') for m in measurements 
                            if m.get('classification', {}).get('device_type')]
                    if len(set(types)) > 1:
                        lines.append(f"  ⚠ Classification changed: {types[0]} → {types[-1]}")
                    
                    lines.append("")
                
                # Warnings
                warnings = latest.get('warnings', [])
                if warnings:
                    lines.append("⚠ WARNINGS")
                    lines.append("-" * 40)
                    for i, warning in enumerate(warnings[:5], 1):  # Show max 5 warnings
                        lines.append(f"  {i}. {warning}")
                    if len(warnings) > 5:
                        lines.append(f"  ... and {len(warnings)-5} more")
                    lines.append("")
                
                # Data location
                lines.append("DATA LOCATION")
                lines.append("-" * 40)
                lines.append(f"  Tracking: {history_file}")
                
                # Check for research data (now in sweep_analysis folder within device dir)
                # Device directory structure: G/{device_num}/sweep_analysis/
                device_letter, device_num = device_id.rsplit('_', 1)
                research_dir = os.path.join(save_root, device_letter, device_num, "sweep_analysis")
                if os.path.exists(research_dir):
                    research_files = [f for f in os.listdir(research_dir) if f.endswith('_research.json')]
                    lines.append(f"  Research: {len(research_files)} file(s) in {research_dir}")
                
                # Check for classification log
                classification_log = os.path.join(save_root, device_letter, device_num, "classification_log.txt")
                if os.path.exists(classification_log):
                    lines.append(f"  Classification Log: {classification_log}")
            else:
                lines.append("No measurements recorded yet.")
            
            # Update text widget
            if hasattr(self, 'stats_text_widget'):
                self.stats_text_widget.config(state=tk.NORMAL)
                self.stats_text_widget.delete('1.0', tk.END)
                self.stats_text_widget.insert('1.0', '\n'.join(lines))
                self.stats_text_widget.config(state=tk.DISABLED)
            
            # Update trend plots
            self._update_stats_plots(history, device_id)
        
        except Exception as e:
            print(f"[STATS] Error updating display: {e}")
            import traceback
            traceback.print_exc()
            
            # Show error in widget
            if hasattr(self, 'stats_text_widget'):
                self.stats_text_widget.config(state=tk.NORMAL)
                self.stats_text_widget.delete('1.0', tk.END)
                self.stats_text_widget.insert('1.0', f"Error loading device stats:\n\n{str(e)}\n\nCheck console for details.")
                self.stats_text_widget.config(state=tk.DISABLED)
    
    def _analyze_forming_process(self, memristivity_scores, switching_ratios, rons, roffs, voltages):
        """
        Analyze if device is forming, formed, or degrading.
        
        Returns dict with:
        - status: 'forming', 'formed', 'degrading', 'unstable', 'insufficient_data'
        - confidence: 0-1
        - indicators: list of evidence strings
        - progress: 0-100 (for forming)
        """
        try:
            import numpy as np
            
            result = {
                'status': 'insufficient_data',
                'confidence': 0.0,
                'indicators': [],
                'progress': 0,
                'voltage_trend': 'unknown'
            }
            
            # Need at least 3 measurements for trend analysis
            if len(memristivity_scores) < 3:
                return result
            
            # Calculate trends (recent vs initial)
            # Use first 2 and last 2 points for robustness
            initial_score = np.mean(memristivity_scores[:2]) if len(memristivity_scores) >= 2 else memristivity_scores[0]
            recent_score = np.mean(memristivity_scores[-2:]) if len(memristivity_scores) >= 2 else memristivity_scores[-1]
            score_change = recent_score - initial_score
            score_change_pct = (score_change / (initial_score + 1e-6)) * 100
            
            # Switching ratio trend
            ratio_improving = False
            if len(switching_ratios) >= 3:
                initial_ratio = np.mean(switching_ratios[:2])
                recent_ratio = np.mean(switching_ratios[-2:])
                ratio_change_pct = (recent_ratio - initial_ratio) / (initial_ratio + 1e-6) * 100
                ratio_improving = ratio_change_pct > 10  # >10% improvement
            
            # Ron stability (should stay stable or decrease slightly during forming)
            ron_stable = True
            ron_trend = 0
            if len(rons) >= 3:
                initial_ron = np.mean(rons[:2])
                recent_ron = np.mean(rons[-2:])
                ron_change_pct = (recent_ron - initial_ron) / (initial_ron + 1e-20) * 100
                ron_trend = ron_change_pct
                ron_stable = abs(ron_change_pct) < 30  # Within 30%
            
            # Roff trend (should increase during forming)
            roff_increasing = False
            if len(roffs) >= 3:
                initial_roff = np.mean(roffs[:2])
                recent_roff = np.mean(roffs[-2:])
                roff_change_pct = (recent_roff - initial_roff) / (initial_roff + 1e-20) * 100
                roff_increasing = roff_change_pct > 15  # >15% increase
            
            # Voltage trend (increasing during forming)
            voltage_increasing = False
            if len(voltages) >= 3:
                voltage_increasing = voltages[-1] > voltages[0] * 1.1  # 10% higher
                result['voltage_trend'] = 'increasing' if voltage_increasing else 'stable'
            
            # DECISION LOGIC
            evidence_count = 0
            indicators = []
            
            # FORMING indicators
            if score_change > 10:  # Score improved by >10 points
                evidence_count += 2
                indicators.append(f"Memristivity improving (+{score_change:.1f})")
            
            if ratio_improving:
                evidence_count += 2
                indicators.append(f"Switching ratio improving (+{ratio_change_pct:.0f}%)")
            
            if roff_increasing:
                evidence_count += 1
                indicators.append("Roff increasing (good)")
            
            if ron_stable:
                evidence_count += 1
                indicators.append("Ron stable")
            
            if voltage_increasing:
                evidence_count += 1
                indicators.append("Voltage ramping (forming protocol)")
            
            # Calculate forming progress (0-100)
            if recent_score < 40:
                progress = int((recent_score / 40) * 33)  # 0-33%: Poor to Fair
            elif recent_score < 60:
                progress = int(33 + ((recent_score - 40) / 20) * 33)  # 33-66%: Fair to Good
            else:
                progress = int(66 + ((recent_score - 60) / 40) * 34)  # 66-100%: Good to Excellent
            
            result['progress'] = min(100, max(0, progress))
            
            # FORMING status (improving + early stage)
            if evidence_count >= 3 and score_change > 5:
                result['status'] = 'forming'
                result['confidence'] = min(1.0, evidence_count / 5)
                result['indicators'] = indicators
                return result
            
            # FORMED status (high score + stable)
            if recent_score >= 70 and abs(score_change) < 10:
                result['status'] = 'formed'
                result['confidence'] = min(1.0, recent_score / 100)
                result['indicators'] = ['High memristivity score', 'Stable characteristics']
                if not ron_stable:
                    result['indicators'].append(f"⚠ Ron drifting ({ron_trend:+.0f}%)")
                return result
            
            # DEGRADING indicators
            degrading_evidence = 0
            degrade_indicators = []
            
            if score_change < -10:
                degrading_evidence += 2
                degrade_indicators.append(f"Memristivity declining ({score_change:.1f})")
            
            if not ratio_improving and len(switching_ratios) >= 3:
                if ratio_change_pct < -20:
                    degrading_evidence += 2
                    degrade_indicators.append(f"Switching ratio declining ({ratio_change_pct:.0f}%)")
            
            if not ron_stable and ron_trend > 30:
                degrading_evidence += 1
                degrade_indicators.append(f"Ron increasing ({ron_trend:+.0f}%)")
            
            if degrading_evidence >= 2:
                result['status'] = 'degrading'
                result['confidence'] = min(1.0, degrading_evidence / 4)
                result['indicators'] = degrade_indicators
                return result
            
            # UNSTABLE status (fluctuating)
            if len(memristivity_scores) >= 4:
                score_std = np.std(memristivity_scores[-4:])  # Last 4 measurements
                if score_std > 15:  # High variability
                    result['status'] = 'unstable'
                    result['confidence'] = 0.7
                    result['indicators'] = [f'High score variability (±{score_std:.1f})']
                    return result
            
            # DEFAULT: Stable (no clear trend)
            result['status'] = 'stable'
            result['confidence'] = 0.6
            result['indicators'] = ['No significant trends detected']
            return result
            
        except Exception as e:
            print(f"[FORMING] Error analyzing forming: {e}")
            return {
                'status': 'unknown',
                'confidence': 0.0,
                'indicators': ['Analysis error'],
                'progress': 0,
                'voltage_trend': 'unknown'
            }
    
    def _clear_stats_plots(self) -> None:
        """Clear stats plots"""
        try:
            if hasattr(self, 'stats_plot_figure') and hasattr(self, 'stats_plot_canvas'):
                fig = self.stats_plot_figure
                fig.clear()
                ax = fig.add_subplot(111)
                ax.text(0.5, 0.5, 'No device selected\n\nSelect a device to view trends',
                       ha='center', va='center', fontsize=14, color='gray')
                ax.axis('off')
                self.stats_plot_canvas.draw()
        except Exception as e:
            print(f"[STATS] Error clearing plots: {e}")
    
    def browse_sample_folder_for_analysis(self) -> None:
        """Browse for a sample folder to analyze retroactively."""
        try:
            from tkinter import filedialog
            import os
            
            # Get default directory (current sample or data folder)
            initial_dir = None
            if hasattr(self, 'sample_name_var') and self.sample_name_var.get():
                try:
                    initial_dir = self._get_sample_save_directory(self.sample_name_var.get())
                    # Go up one level to show all samples
                    initial_dir = os.path.dirname(initial_dir) if os.path.exists(initial_dir) else None
                except:
                    pass
            
            # If no initial dir, try to get data folder from settings
            if not initial_dir:
                try:
                    # Try to get from data saver or settings
                    if hasattr(self, 'data_saver') and hasattr(self.data_saver, 'base_directory'):
                        initial_dir = self.data_saver.base_directory
                except:
                    pass
            
            # Browse for folder
            folder = filedialog.askdirectory(
                title="Select Sample Folder to Analyze",
                initialdir=initial_dir
            )
            
            if folder:
                # Accept folder if it has sample_analysis/analysis/device_tracking (new) or old locations OR if it has device subfolders
                has_tracking = os.path.exists(os.path.join(folder, "sample_analysis", "analysis", "device_tracking")) or \
                               os.path.exists(os.path.join(folder, "sample_analysis", "device_tracking")) or \
                               os.path.exists(os.path.join(folder, "sample_analysis", "device_research")) or \
                               os.path.exists(os.path.join(folder, "device_tracking")) or \
                               os.path.exists(os.path.join(folder, "device_research"))  # Legacy support

                # Check for device subfolders (letter/number structure)
                has_device_folders = False
                try:
                    for item in os.listdir(folder):
                        item_path = os.path.join(folder, item)
                        if os.path.isdir(item_path):
                            # Check if it contains numbered subfolders (device structure)
                            for subitem in os.listdir(item_path):
                                subitem_path = os.path.join(item_path, subitem)
                                if os.path.isdir(subitem_path):
                                    # Check if it contains .txt files (measurement files)
                                    txt_files = [f for f in os.listdir(subitem_path) if f.endswith('.txt')]
                                    if txt_files:
                                        has_device_folders = True
                                        break
                            if has_device_folders:
                                break
                except:
                    pass

                if has_tracking or has_device_folders:
                    if hasattr(self, 'analysis_folder_var'):
                        self.analysis_folder_var.set(folder)
                        print(f"[ANALYSIS] Selected folder: {folder}")
                        if has_device_folders and not has_tracking:
                            print(f"[ANALYSIS] Note: Folder contains raw data - will run retroactive analysis first")
                else:
                    from tkinter import messagebox
                    messagebox.showwarning(
                        "Invalid Folder",
                        "Selected folder doesn't appear to be a sample folder.\n\n"
                        "Expected either:\n"
                        "- 'sample_analysis/analysis/device_tracking' or 'sample_analysis/device_research' subfolders, OR\n"
                        "- Device subfolders (letter/number) containing .txt measurement files"
                    )
        except Exception as e:
            print(f"[ANALYSIS] Error browsing folder: {e}")
            import traceback
            traceback.print_exc()

    def clear_sample_folder_selection(self) -> None:
        """Clear the selected sample folder (use current sample instead)."""
        if hasattr(self, 'analysis_folder_var'):
            self.analysis_folder_var.set("(Use current sample)")
            print("[ANALYSIS] Cleared folder selection - will use current sample")

    def plot_all_device_graphs(self) -> None:
        """
        Plot all graphs (dashboard, conduction, SCLC) for all measurement files
        in the currently selected device.

        This is separate from the automatic plotting and is useful for retroactive
        plotting of old data.
        """
        try:
            from tkinter import messagebox
            import numpy as np
            import threading

            # Get current device info
            if not hasattr(self, 'sample_name_var') or not self.sample_name_var.get():
                messagebox.showwarning(
                    "No Sample Selected",
                    "Please select a sample name first."
                )
                return

            if not hasattr(self, 'final_device_letter') or not hasattr(self, 'final_device_number'):
                messagebox.showwarning(
                    "No Device Selected",
                    "Please select a device (letter and number) first."
                )
                return

            sample_name = self.sample_name_var.get()
            device_letter = self.final_device_letter
            device_number = self.final_device_number
            device_name = f"{device_letter}{device_number}"

            # Get device directory
            device_dir = self._get_save_directory(sample_name, device_letter, device_number)

            if not os.path.exists(device_dir):
                messagebox.showerror(
                    "Directory Not Found",
                    f"Device directory not found:\n{device_dir}"
                )
                return

            # Find all .txt measurement files
            txt_files = [f for f in os.listdir(device_dir) if f.endswith('.txt')]
            txt_files = sorted(txt_files)  # Sort for consistent processing

            if not txt_files:
                messagebox.showinfo(
                    "No Files Found",
                    f"No measurement files (.txt) found in:\n{device_dir}"
                )
                return

            # Confirm with user
            response = messagebox.askyesno(
                "Plot All Device Graphs",
                f"Found {len(txt_files)} measurement file(s) for device {device_name}.\n\n"
                f"This will:\n"
                f"• Load each measurement file\n"
                f"• Run analysis to determine if memristive\n"
                f"• Plot dashboard graphs (all files)\n"
                f"• Plot conduction & SCLC graphs (memristive files only)\n\n"
                f"Continue?"
            )

            if not response:
                return

            # Update status if label exists
            if hasattr(self, 'analysis_status_label'):
                self.analysis_status_label.config(
                    text=f"Plotting graphs for {len(txt_files)} file(s)...",
                    fg="#2196F3"
                )
                self.master.update()

            # Run in background thread to avoid blocking GUI
            def run_plotting():
                try:
                    from Helpers.Analysis import quick_analyze
                    from Helpers.plotting_core import UnifiedPlotter
                    import matplotlib
                    matplotlib.use('Agg')

                    success_count = 0
                    error_count = 0

                    for idx, txt_file in enumerate(txt_files, 1):
                        try:
                            file_path = os.path.join(device_dir, txt_file)
                            filename = os.path.splitext(txt_file)[0]

                            print(f"[DEVICE PLOT] Processing {idx}/{len(txt_files)}: {txt_file}")

                            # Load data
                            try:
                                data = np.loadtxt(file_path, skiprows=1)
                                if data.shape[1] < 2:
                                    print(f"[DEVICE PLOT] Skipping {txt_file}: insufficient columns")
                                    error_count += 1
                                    continue

                                voltage = data[:, 0]
                                current = data[:, 1]
                                timestamps = data[:, 2] if data.shape[1] > 2 else None
                            except Exception as e:
                                print(f"[DEVICE PLOT] Error loading {txt_file}: {e}")
                                error_count += 1
                                continue

                            # Run analysis to determine if memristive
                            try:
                                analysis_data = quick_analyze(
                                    voltage=list(voltage),
                                    current=list(current),
                                    time=list(timestamps) if timestamps is not None else None,
                                    analysis_level='full'
                                )
                                device_type = classification.get('device_type', '')
                                memristivity_score = classification.get('memristivity_score', 0)
                                is_memristive = device_type in ['memristive', 'memcapacitive'] or memristivity_score > 60
                            except Exception as e:
                                print(f"[DEVICE PLOT] Analysis error for {txt_file}: {e}")
                                is_memristive = False  # Default to non-memristive if analysis fails

                            # Plot graphs using the same logic as background plotting
                            try:
                                self._plot_measurement_in_background(
                                    voltage=voltage,
                                    current=current,
                                    timestamps=timestamps,
                                    save_dir=device_dir,
                                    device_name=device_name,
                                    sweep_number=idx,  # Use index as sweep number
                                    is_memristive=is_memristive,
                                    filename=filename
                                )
                                success_count += 1
                                print(f"[DEVICE PLOT] ✓ Plotted {txt_file} (memristive={is_memristive})")
                            except Exception as e:
                                print(f"[DEVICE PLOT] Plotting error for {txt_file}: {e}")
                                error_count += 1

                        except Exception as e:
                            print(f"[DEVICE PLOT] Unexpected error processing {txt_file}: {e}")
                            error_count += 1
                            continue

                    # Update status
                    if hasattr(self, 'analysis_status_label'):
                        status_text = f"Completed: {success_count} plotted, {error_count} errors"
                        self.analysis_status_label.config(
                            text=status_text,
                            fg="#4CAF50" if error_count == 0 else "#FF9800"
                        )

                    # Show completion message
                    messagebox.showinfo(
                        "Plotting Complete",
                        f"Finished plotting graphs for device {device_name}.\n\n"
                        f"Success: {success_count} file(s)\n"
                        f"Errors: {error_count} file(s)\n\n"
                        f"Graphs saved to:\n{os.path.join(device_dir, 'Graphs')}"
                    )

                except Exception as e:
                    print(f"[DEVICE PLOT] Fatal error: {e}")
                    import traceback
                    traceback.print_exc()
                    if hasattr(self, 'analysis_status_label'):
                        self.analysis_status_label.config(
                            text=f"Error: {str(e)}",
                            fg="#F44336"
                        )
                    messagebox.showerror(
                        "Plotting Error",
                        f"Error during plotting:\n{str(e)}"
                    )

            # Start background thread
            plot_thread = threading.Thread(target=run_plotting, daemon=True)
            plot_thread.start()

        except Exception as e:
            print(f"[DEVICE PLOT] Error: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror(
                "Error",
                f"Failed to start plotting:\n{str(e)}"
            )

    def plot_all_sample_graphs(self) -> None:
        """
        Plot all graphs for ALL devices in the selected sample directory.
        Allows generating device-level plots for an entire sample at once.
        """
        try:
            from tkinter import messagebox
            import numpy as np
            import threading

            # Use selected folder logic from run_full_sample_analysis
            sample_dir = None
            sample_name = None

            if hasattr(self, 'analysis_folder_var'):
                selected_folder = self.analysis_folder_var.get()
                if selected_folder and selected_folder != "(Use current sample)":
                    if os.path.exists(selected_folder):
                        sample_dir = selected_folder
                        sample_name = os.path.basename(selected_folder)
                    else:
                        messagebox.showerror("Error", f"Selected folder not found: {selected_folder}")
                        return

            # If no folder selected, use current sample
            if not sample_dir:
                sample_name = self.sample_name_var.get() if hasattr(self, 'sample_name_var') else None
                if not sample_name:
                    messagebox.showwarning("No Sample", "Please select a sample first.")
                    return
                sample_dir = self._get_sample_save_directory(sample_name)

            if not os.path.exists(sample_dir):
                messagebox.showerror("Error", f"Sample directory not found: {sample_dir}")
                return

            # Find all device directories
            device_dirs = []
            for item in os.listdir(sample_dir):
                # Look for section folders (single letter)
                section_path = os.path.join(sample_dir, item)
                if os.path.isdir(section_path) and len(item) == 1 and item.isalpha():
                    # Look for device folders (digits) inside section
                    for subitem in os.listdir(section_path):
                        device_path = os.path.join(section_path, subitem)
                        if os.path.isdir(device_path) and subitem.isdigit():
                            device_dirs.append((item, subitem, device_path))

            if not device_dirs:
                messagebox.showinfo("No Devices", f"No device folders found in {sample_dir}")
                return

            # Count total files
            total_files = 0
            for _, _, d_path in device_dirs:
                total_files += len([f for f in os.listdir(d_path) if f.endswith('.txt') and f != 'log.txt'])

            response = messagebox.askyesno(
                "Plot All Sample Graphs",
                f"Found {len(device_dirs)} devices with ~{total_files} measurement files.\n\n"
                f"This will generate dashboard plots for EVERY device in sample '{sample_name}'.\n"
                f"This process may take some time.\n\nContinue?"
            )

            if not response:
                return

            if hasattr(self, 'analysis_status_label'):
                self.analysis_status_label.config(text="Starting sample-wide plotting...", fg="#2196F3")
                self.master.update()

            def run_sample_plotting():
                try:
                    from Helpers.Analysis import quick_analyze
                    from Helpers.plotting_core import UnifiedPlotter
                    import matplotlib
                    # Force headless backend
                    matplotlib.use('Agg')
                    from matplotlib.figure import Figure
                    from matplotlib.backends.backend_agg import FigureCanvasAgg

                    processed_devices = 0
                    total_success = 0

                    for section, device_num, device_dir in device_dirs:
                        processed_devices += 1

                        # Update status (periodically)
                        if processed_devices % 1 == 0 and hasattr(self, 'analysis_status_label'):
                             # Use after() to safely update GUI from thread
                            self.master.after(0, lambda t=f"Processing {section}{device_num} ({processed_devices}/{len(device_dirs)})...":
                                             self.analysis_status_label.config(text=t))

                        txt_files = [f for f in os.listdir(device_dir) if f.endswith('.txt') and f !='log.txt']

                        for txt_file in txt_files:
                            try:
                                file_path = os.path.join(device_dir, txt_file)
                                # Load and analyze (simplified version of plot_all_device_graphs logic)
                                data = np.loadtxt(file_path, skiprows=1)
                                if data.shape[1] < 2: continue

                                voltage = data[:, 0]
                                current = data[:, 1]
                                timestamps = data[:, 2] if data.shape[1] > 2 else None

                                # Analyze
                                analysis_data = quick_analyze(
                                    voltage=list(voltage),
                                    current=list(current),
                                    time=list(timestamps) if timestamps is not None else None,
                                    analysis_level='full'
                                )

                                # Plot
                                plotter = UnifiedPlotter(save_dir=device_dir, auto_close=True)
                                # Dashboard - use plot_iv_dashboard instead of plot_dashboard
                                filename_base = os.path.splitext(txt_file)[0]
                                plotter.plot_iv_dashboard(
                                    voltage=voltage,
                                    current=current,
                                    time=timestamps,
                                    device_name=filename_base,
                                    save_name=f"{filename_base}_iv_dashboard.png"
                                )
                                total_success += 1

                            except Exception as e:
                                print(f"Error processing {txt_file}: {e}")

                    # Finished
                    msg = f"Completed! Generated plots for {processed_devices} devices ({total_success} files)."
                    self.master.after(0, lambda: messagebox.showinfo("Done", msg))
                    self.master.after(0, lambda: self.analysis_status_label.config(text=msg, fg="green"))

                except Exception as e:
                    self.master.after(0, lambda: self.analysis_status_label.config(text=f"Error: {e}", fg="red"))

            threading.Thread(target=run_sample_plotting, daemon=True).start()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to start plotting: {e}")

    def run_full_sample_analysis(self) -> None:
        """Run comprehensive sample analysis with all plots."""
        #todo fix this to fully plot correctly!!
        try:
            import os
            import subprocess
            from tkinter import messagebox

            # Check if a folder was selected via browse button
            sample_dir = None
            sample_name = None

            if hasattr(self, 'analysis_folder_var'):
                selected_folder = self.analysis_folder_var.get()
                if selected_folder and selected_folder != "(Use current sample)":
                    if os.path.exists(selected_folder):
                        sample_dir = selected_folder
                        sample_name = os.path.basename(selected_folder)
                        print(f"[SAMPLE ANALYSIS] Using selected folder: {sample_dir}")
                    else:
                        messagebox.showerror("Error", f"Selected folder not found: {selected_folder}")
                        return

            # If no folder selected, use current sample
            if not sample_dir:
                sample_name = self.sample_name_var.get() if hasattr(self, 'sample_name_var') else None
                if not sample_name:
                    messagebox.showwarning(
                        "No Sample",
                        "Please either:\n"
                        "1. Select a sample in the GUI, OR\n"
                        "2. Click 'Browse...' to select a sample folder"
                    )
                    return

                # Get sample directory
                sample_dir = self._get_sample_save_directory(sample_name)

            if not os.path.exists(sample_dir):
                messagebox.showerror("Error", f"Sample directory not found: {sample_dir}")
                return

            # Update status
            if hasattr(self, 'analysis_status_label'):
                self.analysis_status_label.config(text="Checking for existing analysis data...")
                self.master.update_idletasks()

            # Set up logging callback for terminal updates (define early so it can be used)
            def log_to_terminal(message: str) -> None:
                """Log message to graph activity terminal"""
                if hasattr(self, 'plot_panels') and self.plot_panels:
                    self.plot_panels.log_graph_activity(message)
                # Also update status label
                if hasattr(self, 'analysis_status_label'):
                    self.analysis_status_label.config(text=message)
                    self.master.update_idletasks()

            print(f"[SAMPLE ANALYSIS] Starting analysis for: {sample_name or os.path.basename(sample_dir)}")
            log_to_terminal(f"Starting analysis for: {sample_name or os.path.basename(sample_dir)}")

            # Check if we need to run retroactive analysis on raw data
            # Check new structure first, then legacy
            tracking_dir = os.path.join(sample_dir, "sample_analysis", "analysis", "device_tracking")
            legacy_tracking_dir = os.path.join(sample_dir, "sample_analysis", "device_tracking")  # Old location
            old_legacy_tracking_dir = os.path.join(sample_dir, "device_tracking")  # Very old location
            has_tracking = (os.path.exists(tracking_dir) and os.listdir(tracking_dir)) or \
                          (os.path.exists(legacy_tracking_dir) and os.listdir(legacy_tracking_dir)) or \
                          (os.path.exists(old_legacy_tracking_dir) and os.listdir(old_legacy_tracking_dir))

            if not has_tracking:
                # Need to run retroactive analysis on raw measurement files
                if hasattr(self, 'analysis_status_label'):
                    self.analysis_status_label.config(text="Running retroactive analysis on raw data...")
                    self.master.update_idletasks()

                log_to_terminal("No tracking data found - analyzing raw measurement files...")
                analyzed_count = self._run_retroactive_analysis(
                    sample_dir,
                    sample_name or os.path.basename(sample_dir),
                    log_callback=log_to_terminal
                )

                if analyzed_count == 0:
                    messagebox.showwarning(
                        "No Data",
                        "No measurement files found to analyze.\n\n"
                        "Expected device subfolders (letter/number) containing .txt files."
                    )
                    if hasattr(self, 'analysis_status_label'):
                        self.analysis_status_label.config(text="✗ No data found")
                    return

                print(f"[RETROACTIVE] Analyzed {analyzed_count} measurement files")

            # Update status
            if hasattr(self, 'analysis_status_label'):
                self.analysis_status_label.config(text="Loading device data...")
                self.master.update_idletasks()

            # Use comprehensive analyzer for one-stop shop analysis
            from Helpers.Analysis import ComprehensiveAnalyzer

            if hasattr(self, 'analysis_status_label'):
                self.analysis_status_label.config(text="Running comprehensive analysis (all code_names)...")
                self.master.update_idletasks()

            comprehensive = ComprehensiveAnalyzer(sample_dir)
            comprehensive.set_log_callback(log_to_terminal)  # Pass logging callback
            comprehensive.run_comprehensive_analysis()

            # Count devices for status message
            device_count = 0
            tracking_dir = os.path.join(sample_dir, "sample_analysis", "analysis", "device_tracking")
            legacy_tracking_dir = os.path.join(sample_dir, "sample_analysis", "device_tracking")  # Old location
            old_legacy_tracking_dir = os.path.join(sample_dir, "device_tracking")  # Very old location
            if os.path.exists(tracking_dir):
                device_count = len([f for f in os.listdir(tracking_dir) if f.endswith('_history.json')])
            elif os.path.exists(legacy_tracking_dir):
                device_count = len([f for f in os.listdir(legacy_tracking_dir) if f.endswith('_history.json')])
            elif os.path.exists(old_legacy_tracking_dir):
                device_count = len([f for f in os.listdir(old_legacy_tracking_dir) if f.endswith('_history.json')])

            # Success
            output_dir = os.path.join(sample_dir, "sample_analysis")

            messagebox.showinfo(
                "Comprehensive Analysis Complete",
                f"Comprehensive analysis complete!\n\n"
                f"Devices analyzed: {device_count}\n"
                f"Code names processed: {len(comprehensive.discovered_code_names)}\n"
                f"Output: {output_dir}\n\n"
                f"Generated:\n"
                f"• Device-level combined sweep plots\n"
                f"• Sample-level analysis for each code_name\n"
                f"• Overall sample analysis\n"
                f"• Origin-ready data exports\n\n"
                f"Check the output folders for all results."
            )

            # Update status
            if hasattr(self, 'analysis_status_label'):
                self.analysis_status_label.config(text=f"✓ Complete - {device_count} devices, {len(comprehensive.discovered_code_names)} code_names")

            print(f"[COMPREHENSIVE ANALYSIS] Complete!")
            print(f"[COMPREHENSIVE ANALYSIS] Code names: {sorted(comprehensive.discovered_code_names)}")
            print(f"[COMPREHENSIVE ANALYSIS] Output: {output_dir}")

            # Optionally open output folder
            try:
                import subprocess
                subprocess.Popen(f'explorer "{output_dir}"')
            except Exception:
                pass  # Ignore if explorer fails

        except Exception as e:
            error_msg = f"Sample analysis failed: {e}"
            print(f"[SAMPLE ANALYSIS ERROR] {error_msg}")
            import traceback
            traceback.print_exc()

            from tkinter import messagebox
            messagebox.showerror("Analysis Error", error_msg)

            if hasattr(self, 'analysis_status_label'):
                self.analysis_status_label.config(text=f"✗ Error: {e}")

    # ======================================================================
    # Custom Sweeps Graphing Methods
    # ======================================================================

    def load_custom_sweep_methods(self) -> None:
        """Load available custom sweep methods from Custom_Sweeps.json"""
        try:
            custom_sweeps_path = _PROJECT_ROOT / "Json_Files" / "Custom_Sweeps.json"
            if not custom_sweeps_path.exists():
                if hasattr(self, 'custom_sweep_status_label'):
                    self.custom_sweep_status_label.config(text="✗ Custom_Sweeps.json not found", fg="#F44336")
                from tkinter import messagebox
                messagebox.showerror("File Not Found", f"Custom_Sweeps.json not found at:\n{custom_sweeps_path}")
                return

            custom_sweeps = self.load_custom_sweeps(str(custom_sweeps_path))

            # Build list of method names (identifier or code_name)
            method_list = []
            for identifier, method_data in custom_sweeps.items():
                code_name = method_data.get("code_name", "")
                # Show both identifier and code_name for clarity
                if code_name:
                    display_name = f"{identifier} ({code_name})"
                else:
                    display_name = identifier
                method_list.append(display_name)

            if not method_list:
                if hasattr(self, 'custom_sweep_status_label'):
                    self.custom_sweep_status_label.config(text="✗ No methods found in file", fg="#F44336")
                return

            # Update combobox
            if hasattr(self, 'custom_sweep_method_combo'):
                self.custom_sweep_method_combo['values'] = method_list
                if method_list:
                    self.custom_sweep_method_combo.current(0)
                    self.on_custom_sweep_method_selected()

            # Store the mapping for later use
            self.custom_sweeps_data = custom_sweeps
            self.custom_sweeps_method_map = {}
            for identifier, method_data in custom_sweeps.items():
                code_name = method_data.get("code_name", "")
                display_name = f"{identifier} ({code_name})" if code_name else identifier
                self.custom_sweeps_method_map[display_name] = {
                    'identifier': identifier,
                    'code_name': code_name,
                    'data': method_data
                }

            if hasattr(self, 'custom_sweep_status_label'):
                self.custom_sweep_status_label.config(text=f"✓ Loaded {len(method_list)} method(s)", fg="#4CAF50")

        except Exception as e:
            error_msg = f"Error loading custom sweep methods: {e}"
            print(f"[CUSTOM SWEEPS] {error_msg}")
            if hasattr(self, 'custom_sweep_status_label'):
                self.custom_sweep_status_label.config(text=f"✗ {error_msg}", fg="#F44336")
            from tkinter import messagebox
            messagebox.showerror("Error", error_msg)

    def on_custom_sweep_method_selected(self) -> None:
        """Handle custom sweep method selection"""
        try:
            if not hasattr(self, 'custom_sweep_method_var') or not self.custom_sweep_method_var.get():
                return

            # Load combinations for the selected method
            self.load_custom_sweep_combinations()

        except Exception as e:
            print(f"[CUSTOM SWEEPS] Error handling method selection: {e}")

    def load_custom_sweep_combinations(self) -> None:
        """Load sweep combinations from test_configurations.json for selected method"""
        try:
            if not hasattr(self, 'custom_sweep_method_var') or not self.custom_sweep_method_var.get():
                if hasattr(self, 'custom_sweep_combinations_listbox'):
                    self.custom_sweep_combinations_listbox.delete(0, tk.END)
                return

            # Get selected method
            selected_display = self.custom_sweep_method_var.get()
            if not hasattr(self, 'custom_sweeps_method_map') or selected_display not in self.custom_sweeps_method_map:
                return

            method_info = self.custom_sweeps_method_map[selected_display]
            code_name = method_info['code_name']

            # Load test configurations
            test_config_path = _PROJECT_ROOT / "Json_Files" / "test_configurations.json"
            if not test_config_path.exists():
                if hasattr(self, 'custom_sweep_status_label'):
                    self.custom_sweep_status_label.config(text="✗ test_configurations.json not found", fg="#F44336")
                return

            with test_config_path.open("r", encoding="utf-8") as f:
                test_configs = json.load(f)

            # Find configurations for this code_name
            if code_name not in test_configs:
                if hasattr(self, 'custom_sweep_combinations_listbox'):
                    self.custom_sweep_combinations_listbox.delete(0, tk.END)
                    self.custom_sweep_combinations_listbox.insert(0, f"No combinations found for {code_name}")
                if hasattr(self, 'custom_sweep_status_label'):
                    self.custom_sweep_status_label.config(text=f"✗ No combinations for {code_name}", fg="#F44336")
                return

            config = test_configs[code_name]
            combinations = config.get("sweep_combinations", [])

            # Store combinations (make a copy so we can modify it)
            self.custom_sweep_combinations = [combo.copy() for combo in combinations]

            # Update listbox
            if hasattr(self, 'custom_sweep_combinations_listbox'):
                self.custom_sweep_combinations_listbox.delete(0, tk.END)
                for combo in self.custom_sweep_combinations:
                    sweeps_str = ", ".join(map(str, combo.get("sweeps", [])))
                    title = combo.get("title", "Untitled")
                    display_text = f"{title} [Sweeps: {sweeps_str}]"
                    self.custom_sweep_combinations_listbox.insert(tk.END, display_text)

            if hasattr(self, 'custom_sweep_status_label'):
                self.custom_sweep_status_label.config(
                    text=f"✓ Loaded {len(combinations)} combination(s) for {code_name}",
                    fg="#4CAF50"
                )

        except Exception as e:
            error_msg = f"Error loading combinations: {e}"
            print(f"[CUSTOM SWEEPS] {error_msg}")
            if hasattr(self, 'custom_sweep_status_label'):
                self.custom_sweep_status_label.config(text=f"✗ {error_msg}", fg="#F44336")

    def add_sweep_combination(self) -> None:
        """Add a new sweep combination to the current list."""
        try:
            if not hasattr(self, 'custom_sweep_method_var') or not self.custom_sweep_method_var.get():
                messagebox.showwarning("No Method Selected", "Please select a method first")
                return

            # Get sweep numbers
            sweeps_str = self.new_combination_sweeps_var.get().strip()
            if not sweeps_str:
                messagebox.showwarning("Invalid Input", "Please enter sweep numbers (e.g., 1,2 or 1,2,3)")
                return

            # Parse sweep numbers
            try:
                sweeps = [int(x.strip()) for x in sweeps_str.split(',')]
                if not sweeps:
                    raise ValueError("No valid sweep numbers")
            except ValueError as e:
                messagebox.showerror("Invalid Format", f"Invalid sweep numbers format. Use comma-separated numbers.\nError: {e}")
                return

            # Get title
            title = self.new_combination_title_var.get().strip()
            if not title:
                title = f"Combined sweeps {sweeps_str}"

            # Create new combination
            new_combo = {
                "sweeps": sweeps,
                "title": title
            }

            # Add to current combinations
            if not hasattr(self, 'custom_sweep_combinations'):
                self.custom_sweep_combinations = []

            self.custom_sweep_combinations.append(new_combo)

            # Update listbox
            if hasattr(self, 'custom_sweep_combinations_listbox'):
                sweeps_str_display = ", ".join(map(str, sweeps))
                display_text = f"{title} [Sweeps: {sweeps_str_display}]"
                self.custom_sweep_combinations_listbox.insert(tk.END, display_text)

            # Clear input fields
            self.new_combination_sweeps_var.set("")
            self.new_combination_title_var.set("")

            if hasattr(self, 'custom_sweep_status_label'):
                self.custom_sweep_status_label.config(
                    text=f"✓ Added combination: {title}",
                    fg="#4CAF50"
                )

            print(f"[CUSTOM SWEEPS] Added combination: {title} - Sweeps: {sweeps}")

        except Exception as e:
            error_msg = f"Error adding combination: {e}"
            print(f"[CUSTOM SWEEPS] {error_msg}")
            messagebox.showerror("Error", error_msg)
            if hasattr(self, 'custom_sweep_status_label'):
                self.custom_sweep_status_label.config(text=f"✗ {error_msg}", fg="#F44336")

    def edit_sweep_combination(self) -> None:
        """Edit the selected sweep combination."""
        try:
            if not hasattr(self, 'custom_sweep_combinations_listbox'):
                return

            selection = self.custom_sweep_combinations_listbox.curselection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a combination to edit")
                return

            idx = selection[0]

            if not hasattr(self, 'custom_sweep_combinations') or idx >= len(self.custom_sweep_combinations):
                messagebox.showerror("Error", "Invalid selection")
                return

            # Get current combination
            combo = self.custom_sweep_combinations[idx]

            # Pre-fill input fields
            sweeps_str = ", ".join(map(str, combo.get("sweeps", [])))
            self.new_combination_sweeps_var.set(sweeps_str)
            self.new_combination_title_var.set(combo.get("title", ""))

            # Delete old entry
            self.delete_sweep_combination(silent=True, index=idx)

            # Focus on input fields for editing
            if hasattr(self, 'new_combination_sweeps_var'):
                # User can now modify and click "Add" to save
                messagebox.showinfo(
                    "Edit Mode",
                    "Combination removed from list.\n"
                    "Modify the values above and click 'Add Combination' to save changes."
                )

        except Exception as e:
            error_msg = f"Error editing combination: {e}"
            print(f"[CUSTOM SWEEPS] {error_msg}")
            messagebox.showerror("Error", error_msg)

    def delete_sweep_combination(self, silent: bool = False, index: int = None) -> None:
        """Delete the selected sweep combination."""
        try:
            if not hasattr(self, 'custom_sweep_combinations_listbox'):
                return

            if index is None:
                selection = self.custom_sweep_combinations_listbox.curselection()
                if not selection:
                    if not silent:
                        messagebox.showwarning("No Selection", "Please select a combination to delete")
                    return
                idx = selection[0]
            else:
                idx = index

            if not hasattr(self, 'custom_sweep_combinations') or idx >= len(self.custom_sweep_combinations):
                if not silent:
                    messagebox.showerror("Error", "Invalid selection")
                return

            # Confirm deletion
            if not silent:
                combo = self.custom_sweep_combinations[idx]
                title = combo.get("title", "Untitled")
                if not messagebox.askyesno("Confirm Delete", f"Delete combination: {title}?"):
                    return

            # Remove from list
            self.custom_sweep_combinations.pop(idx)

            # Update listbox
            self.custom_sweep_combinations_listbox.delete(idx)

            if hasattr(self, 'custom_sweep_status_label') and not silent:
                self.custom_sweep_status_label.config(
                    text="✓ Combination deleted",
                    fg="#4CAF50"
                )

            print(f"[CUSTOM SWEEPS] Deleted combination at index {idx}")

        except Exception as e:
            error_msg = f"Error deleting combination: {e}"
            print(f"[CUSTOM SWEEPS] {error_msg}")
            if not silent:
                messagebox.showerror("Error", error_msg)

    def save_sweep_combinations_to_json(self) -> None:
        """Save current sweep combinations to test_configurations.json"""
        try:
            if not hasattr(self, 'custom_sweep_method_var') or not self.custom_sweep_method_var.get():
                messagebox.showwarning("No Method Selected", "Please select a method first")
                return

            if not hasattr(self, 'custom_sweep_combinations') or not self.custom_sweep_combinations:
                messagebox.showwarning("No Combinations", "No combinations to save. Add some combinations first.")
                return

            # Get selected method
            selected_display = self.custom_sweep_method_var.get()
            if not hasattr(self, 'custom_sweeps_method_map') or selected_display not in self.custom_sweeps_method_map:
                messagebox.showerror("Error", "Invalid method selection")
                return

            method_info = self.custom_sweeps_method_map[selected_display]
            code_name = method_info['code_name']

            # Load existing config
            test_config_path = _PROJECT_ROOT / "Json_Files" / "test_configurations.json"
            if not test_config_path.exists():
                test_configs = {}
            else:
                with test_config_path.open("r", encoding="utf-8") as f:
                    test_configs = json.load(f)

            # Update or create config for this code_name
            if code_name not in test_configs:
                test_configs[code_name] = {}

            # Update combinations
            test_configs[code_name]["sweep_combinations"] = self.custom_sweep_combinations

            # Preserve main_sweep if it exists, otherwise set to None
            if "main_sweep" not in test_configs[code_name]:
                test_configs[code_name]["main_sweep"] = None

            # Save to file
            with test_config_path.open("w", encoding="utf-8") as f:
                json.dump(test_configs, f, indent=4, ensure_ascii=False)

            if hasattr(self, 'custom_sweep_status_label'):
                self.custom_sweep_status_label.config(
                    text=f"✓ Saved {len(self.custom_sweep_combinations)} combination(s) to JSON",
                    fg="#4CAF50"
                )

            messagebox.showinfo(
                "Saved",
                f"Successfully saved {len(self.custom_sweep_combinations)} combination(s)\n"
                f"to test_configurations.json for method: {code_name}"
            )

            print(f"[CUSTOM SWEEPS] Saved {len(self.custom_sweep_combinations)} combinations to {test_config_path}")

        except Exception as e:
            error_msg = f"Error saving combinations: {e}"
            print(f"[CUSTOM SWEEPS] {error_msg}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error", error_msg)
            if hasattr(self, 'custom_sweep_status_label'):
                self.custom_sweep_status_label.config(text=f"✗ {error_msg}", fg="#F44336")


    def reclassify_all_devices(self) -> None:
        """
        Reclassify all devices in the current sample using updated classification weights.
        
        Scans all measurement files, re-runs analysis with current weights from classification_weights.json,
        and updates device_tracking history files and research files accordingly.
        """
        try:
            import os
            import json
            import numpy as np
            from pathlib import Path
            from tkinter import messagebox
            from Helpers.Analysis import quick_analyze
            from datetime import datetime

            # Get sample directory (same logic as run_full_sample_analysis)
            sample_dir = None
            sample_name = None

            if hasattr(self, 'analysis_folder_var'):
                selected_folder = self.analysis_folder_var.get()
                if selected_folder and selected_folder != "(Use current sample)":
                    if os.path.exists(selected_folder):
                        sample_dir = selected_folder
                        sample_name = os.path.basename(selected_folder)
                    else:
                        messagebox.showerror("Error", f"Selected folder not found: {selected_folder}")
                        return

            # If no folder selected, use current sample
            if not sample_dir:
                sample_name = self.sample_name_var.get() if hasattr(self, 'sample_name_var') else None
                if not sample_name:
                    messagebox.showwarning(
                        "No Sample",
                        "Please either:\n"
                        "1. Select a sample in the GUI, OR\n"
                        "2. Click 'Browse...' to select a sample folder"
                    )
                    return

                sample_dir = self._get_sample_save_directory(sample_name)

            if not os.path.exists(sample_dir):
                messagebox.showerror("Error", f"Sample directory not found: {sample_dir}")
                return

            # Set up logging callback
            def log_to_terminal(message: str) -> None:
                """Log message to graph activity terminal"""
                if hasattr(self, 'plot_panels') and self.plot_panels:
                    self.plot_panels.log_graph_activity(message)
                if hasattr(self, 'analysis_status_label'):
                    self.analysis_status_label.config(text=message)
                    self.master.update_idletasks()

            # Confirm with user
            response = messagebox.askyesno(
                "Reclassify All Devices",
                f"This will reclassify all devices in:\n{sample_dir}\n\n"
                "This may take a while for large samples.\n\n"
                "Continue?"
            )
            if not response:
                return

            log_to_terminal("Starting reclassification...")
            print(f"[RECLASSIFY] Starting reclassification for: {sample_name or os.path.basename(sample_dir)}")

            # Statistics
            total_files = 0
            reclassified_count = 0
            type_changes = 0
            errors = []

            # Scan for device subfolders (letter/number structure)
            sample_path = Path(sample_dir)
            tracking_dir = os.path.join(sample_dir, "sample_analysis", "analysis", "device_tracking")
            legacy_tracking_dir = os.path.join(sample_dir, "sample_analysis", "device_tracking")  # Old location
            old_legacy_tracking_dir = os.path.join(sample_dir, "device_tracking")  # Very old location

            # Helper function to convert numpy types for JSON
            def convert_for_json(obj):
                if isinstance(obj, np.bool_):
                    return bool(obj)
                elif isinstance(obj, np.integer):
                    return int(obj)
                elif isinstance(obj, np.floating):
                    return float(obj)
                elif isinstance(obj, np.ndarray):
                    return obj.tolist()
                elif isinstance(obj, dict):
                    return {key: convert_for_json(value) for key, value in obj.items()}
                elif isinstance(obj, list):
                    return [convert_for_json(item) for item in obj]
                return obj

            # Process each device folder
            for letter_dir in sample_path.iterdir():
                if not letter_dir.is_dir() or letter_dir.name.startswith('.'):
                    continue

                letter = letter_dir.name

                # Check if this is a device letter folder (contains numbered subfolders)
                for number_dir in letter_dir.iterdir():
                    if not number_dir.is_dir():
                        continue

                    try:
                        device_number = number_dir.name
                    except:
                        continue

                    # Find .txt measurement files in this device folder
                    txt_files = list(number_dir.glob("*.txt"))

                    if not txt_files:
                        continue

                    # Construct device ID
                    device_id = f"{sample_name or os.path.basename(sample_dir)}_{letter}_{device_number}"

                    # Load or create device history
                    history_file = None
                    history = None
                    
                    # Try new structure first, then legacy (check all possible locations)
                    for tracking_path in [tracking_dir, legacy_tracking_dir, old_legacy_tracking_dir]:
                        potential_file = os.path.join(tracking_path, f"{device_id}_history.json")
                        if os.path.exists(potential_file):
                            history_file = potential_file
                            try:
                                with open(history_file, 'r') as f:
                                    history = json.load(f)
                                break
                            except Exception as e:
                                print(f"[RECLASSIFY] Error loading history file {potential_file}: {e}")
                                errors.append(f"Error loading {device_id} history: {str(e)[:50]}")

                    # If no history file exists, create new structure
                    if history is None:
                        # Create tracking directory if needed
                        os.makedirs(tracking_dir, exist_ok=True)
                        history_file = os.path.join(tracking_dir, f"{device_id}_history.json")
                        history = {
                            'device_id': device_id,
                            'created': datetime.now().isoformat(),
                            'measurements': []
                        }

                    log_to_terminal(f"Processing device {device_id}: {len(txt_files)} file(s)")

                    # Process each measurement file
                    for txt_file in txt_files:
                        total_files += 1
                        try:
                            # Load data from file
                            try:
                                data = np.loadtxt(txt_file, skiprows=1)
                            except:
                                try:
                                    data = np.loadtxt(txt_file)
                                except:
                                    # Try reading line by line
                                    with open(txt_file, 'r') as f:
                                        lines = f.readlines()
                                        if lines and ('Voltage' in lines[0] or 'voltage' in lines[0].lower()):
                                            lines = lines[1:]
                                        data_lines = []
                                        for line in lines:
                                            if line.strip() and not line.strip().startswith('#'):
                                                try:
                                                    values = [float(x) for x in line.strip().split()]
                                                    if len(values) >= 2:
                                                        data_lines.append(values)
                                                except:
                                                    continue
                                        if not data_lines:
                                            raise ValueError("No valid data found")
                                        data = np.array(data_lines)

                            if len(data.shape) < 2 or data.shape[1] < 2:
                                print(f"[RECLASSIFY] Skipping {txt_file.name}: insufficient columns")
                                continue

                            # Extract voltage, current, time
                            voltage = data[:, 0]
                            current = data[:, 1]
                            timestamps = data[:, 2] if data.shape[1] > 2 else None

                            if len(voltage) == 0 or len(current) == 0:
                                print(f"[RECLASSIFY] Skipping {txt_file.name}: empty data")
                                continue

                            # Build metadata
                            metadata = {
                                'device_name': device_id,
                                'file_name': txt_file.stem,
                                'reclassification': True
                            }

                            # Run classification-level analysis with current weights
                            log_to_terminal(f"Reclassifying {txt_file.name}...")
                            analysis_data = quick_analyze(
                                voltage=voltage,
                                current=current,
                                time=timestamps,
                                metadata=metadata,
                                analysis_level='classification',
                                device_id=device_id,
                                cycle_number=None,
                                save_directory=sample_dir
                            )

                            # Get new classification
                            classification = analysis_data.get('classification', {})
                            new_device_type = classification.get('device_type', 'unknown')
                            new_memristivity_score = classification.get('memristivity_score', 0)
                            new_confidence = classification.get('confidence', 0.0)
                            new_conduction_mechanism = classification.get('conduction_mechanism', 'N/A')

                            # Find matching measurement in history
                            file_stem = txt_file.stem
                            measurement_found = False
                            old_device_type = None

                            # Try to match by filename first (if stored in metadata)
                            for measurement in history.get('measurements', []):
                                # Check if this measurement matches the file
                                # Match by filename if stored, or by being the only measurement, or by timestamp proximity
                                measurement_file = measurement.get('file_name')
                                if measurement_file and measurement_file == file_stem:
                                    measurement_found = True
                                    old_classification = measurement.get('classification', {})
                                    old_device_type = old_classification.get('device_type', 'unknown')
                                    
                                    # Update classification fields
                                    measurement['classification'] = {
                                        'device_type': new_device_type,
                                        'confidence': float(new_confidence),
                                        'memristivity_score': float(new_memristivity_score) if new_memristivity_score else None,
                                        'conduction_mechanism': new_conduction_mechanism,
                                    }
                                    measurement['reclassified'] = True
                                    measurement['reclassified_timestamp'] = datetime.now().isoformat()
                                    
                                    # Track type changes
                                    if old_device_type != new_device_type:
                                        type_changes += 1
                                        print(f"[RECLASSIFY] {device_id}/{file_stem}: {old_device_type} → {new_device_type}")
                                    
                                    break

                            # If no exact match found, try to match by being the only measurement or update most recent
                            if not measurement_found:
                                measurements = history.get('measurements', [])
                                measurement_to_update = None
                                
                                if len(measurements) == 1:
                                    # Only one measurement - update it
                                    measurement_to_update = measurements[0]
                                elif len(measurements) > 1:
                                    # Multiple measurements - update the most recent one
                                    # Sort by timestamp (most recent last)
                                    sorted_measurements = sorted(
                                        measurements,
                                        key=lambda m: m.get('timestamp', ''),
                                        reverse=False
                                    )
                                    measurement_to_update = sorted_measurements[-1]  # Most recent
                                
                                if measurement_to_update:
                                    old_classification = measurement_to_update.get('classification', {})
                                    old_device_type = old_classification.get('device_type', 'unknown')
                                    
                                    # Update classification fields
                                    measurement_to_update['classification'] = {
                                        'device_type': new_device_type,
                                        'confidence': float(new_confidence),
                                        'memristivity_score': float(new_memristivity_score) if new_memristivity_score else None,
                                        'conduction_mechanism': new_conduction_mechanism,
                                    }
                                    measurement_to_update['file_name'] = file_stem  # Store filename for future matching
                                    measurement_to_update['reclassified'] = True
                                    measurement_to_update['reclassified_timestamp'] = datetime.now().isoformat()
                                    
                                    # Track type changes
                                    if old_device_type != new_device_type:
                                        type_changes += 1
                                        print(f"[RECLASSIFY] {device_id}/{file_stem}: {old_device_type} → {new_device_type}")
                                    
                                    measurement_found = True

                            # If still no match found, add new entry
                            if not measurement_found:
                                # Create new measurement entry (minimal, just classification)
                                new_measurement = {
                                    'timestamp': datetime.now().isoformat(),
                                    'cycle_number': None,
                                    'classification': {
                                        'device_type': new_device_type,
                                        'confidence': float(new_confidence),
                                        'memristivity_score': float(new_memristivity_score) if new_memristivity_score else None,
                                        'conduction_mechanism': new_conduction_mechanism,
                                    },
                                    'file_name': file_stem,
                                    'reclassified': True,
                                    'reclassified_timestamp': datetime.now().isoformat()
                                }
                                history['measurements'].append(new_measurement)

                            # Update history metadata
                            history['last_updated'] = datetime.now().isoformat()
                            history['total_measurements'] = len(history['measurements'])

                            # Save updated history
                            serializable_history = convert_for_json(history)
                            with open(history_file, 'w') as f:
                                json.dump(serializable_history, f, indent=2)

                            # Handle research files
                            is_memristive = new_device_type in ['memristive', 'memcapacitive'] or (new_memristivity_score and new_memristivity_score > 60)
                            
                            if is_memristive:
                                # Run research analysis and save
                                try:
                                    log_to_terminal(f"Running research analysis for {txt_file.name}...")
                                    research_data = quick_analyze(
                                        voltage=voltage,
                                        current=current,
                                        time=timestamps,
                                        metadata=metadata,
                                        analysis_level='research',
                                        device_id=device_id,
                                        cycle_number=None,
                                        save_directory=sample_dir
                                    )
                                    
                                    # Save research data
                                    self._save_research_analysis(
                                        research_data,
                                        str(number_dir),  # Device directory
                                        txt_file.stem,
                                        device_id
                                    )
                                except Exception as research_exc:
                                    print(f"[RECLASSIFY] Research analysis failed for {txt_file.name}: {research_exc}")
                                    errors.append(f"Research analysis failed for {device_id}/{txt_file.name}: {str(research_exc)[:50]}")

                            reclassified_count += 1

                            # Update classification log files
                            try:
                                self._append_classification_log(
                                    save_dir=str(number_dir),  # Device directory (e.g., G/1/)
                                    file_name=txt_file.stem,
                                    analysis_data=analysis_data
                                )
                            except Exception as log_exc:
                                print(f"[RECLASSIFY] Failed to update classification log for {txt_file.name}: {log_exc}")
                                # Don't add to errors - log failure is non-critical

                            # Update progress
                            if reclassified_count % 5 == 0:
                                log_to_terminal(f"Reclassified {reclassified_count}/{total_files} files...")

                        except Exception as file_exc:
                            error_msg = f"Error processing {txt_file.name}: {str(file_exc)[:100]}"
                            print(f"[RECLASSIFY] {error_msg}")
                            errors.append(f"{device_id}/{txt_file.name}: {str(file_exc)[:50]}")
                            continue

            # Show completion summary
            summary = (
                f"Reclassification complete!\n\n"
                f"Total files processed: {total_files}\n"
                f"Successfully reclassified: {reclassified_count}\n"
                f"Type changes: {type_changes}\n"
            )
            
            if errors:
                summary += f"\nErrors: {len(errors)}\n"
                summary += "\n".join(errors[:10])  # Show first 10 errors
                if len(errors) > 10:
                    summary += f"\n... and {len(errors) - 10} more errors"

            log_to_terminal(f"✓ Reclassification complete: {reclassified_count} files, {type_changes} type changes")
            messagebox.showinfo("Reclassification Complete", summary)
            
            print(f"[RECLASSIFY] Complete: {reclassified_count}/{total_files} files, {type_changes} type changes")

        except Exception as e:
            error_msg = f"Reclassification failed: {str(e)}"
            print(f"[RECLASSIFY ERROR] {error_msg}")
            import traceback
            traceback.print_exc()
            
            if hasattr(self, 'analysis_status_label'):
                self.analysis_status_label.config(text=f"✗ {error_msg[:50]}")
            
            from tkinter import messagebox
            messagebox.showerror("Reclassification Error", error_msg)

    def _run_retroactive_analysis(self, sample_dir: str, sample_name: str, log_callback: Optional[Callable] = None) -> int:
        """
        Run analysis on raw measurement files retroactively.

        Scans sample folder for device subfolders (letter/number) containing .txt files,
        loads the data, and runs quick_analyze() to generate device_tracking and device_research data.

        Args:
            sample_dir: Path to sample folder
            sample_name: Sample name (for device ID construction)

        Returns:
            Number of files analyzed
        """
        try:
            import numpy as np
            from Helpers.Analysis import quick_analyze
            from pathlib import Path

            analyzed_count = 0

            # Scan for device subfolders (letter/number structure)
            sample_path = Path(sample_dir)

            for letter_dir in sample_path.iterdir():
                if not letter_dir.is_dir() or letter_dir.name.startswith('.'):
                    continue

                letter = letter_dir.name

                # Check if this is a device letter folder (contains numbered subfolders)
                for number_dir in letter_dir.iterdir():
                    if not number_dir.is_dir():
                        continue

                    try:
                        device_number = number_dir.name
                    except:
                        continue

                    # Find .txt measurement files in this device folder
                    txt_files = list(number_dir.glob("*.txt"))

                    if not txt_files:
                        continue

                    # Construct device ID
                    device_id = f"{sample_name}_{letter}_{device_number}"

                    if log_callback:
                        log_callback(f"Processing device {device_id}: {len(txt_files)} file(s)")

                    # Process each measurement file
                    file_count = 0
                    for txt_file in txt_files:
                        file_count += 1
                        try:
                            # Load data from file
                            # Format: tab-delimited, header "Voltage Current Time", scientific notation
                            # Try to load with skiprows=1 first (standard format)
                            try:
                                data = np.loadtxt(txt_file, skiprows=1)
                            except:
                                # If that fails, try without skiprows (no header)
                                try:
                                    data = np.loadtxt(txt_file)
                                except:
                                    # If still fails, try reading line by line to skip header
                                    with open(txt_file, 'r') as f:
                                        lines = f.readlines()
                                        # Skip first line if it looks like a header
                                        if lines and ('Voltage' in lines[0] or 'voltage' in lines[0].lower()):
                                            lines = lines[1:]
                                        # Parse remaining lines
                                        data_lines = []
                                        for line in lines:
                                            if line.strip() and not line.strip().startswith('#'):
                                                try:
                                                    values = [float(x) for x in line.strip().split()]
                                                    if len(values) >= 2:
                                                        data_lines.append(values)
                                                except:
                                                    continue
                                        if not data_lines:
                                            raise ValueError("No valid data found")
                                        data = np.array(data_lines)

                            if len(data.shape) < 2 or data.shape[1] < 2:
                                print(f"[RETROACTIVE] Skipping {txt_file.name}: insufficient columns")
                                continue

                            # Extract voltage, current, time
                            voltage = data[:, 0]
                            current = data[:, 1]
                            timestamps = data[:, 2] if data.shape[1] > 2 else None

                            if len(voltage) == 0 or len(current) == 0:
                                print(f"[RETROACTIVE] Skipping {txt_file.name}: empty data")
                                continue

                            # Build metadata
                            metadata = {
                                'device_name': device_id,
                                'file_name': txt_file.stem,
                                'retroactive_analysis': True
                            }

                            # Run classification-level analysis
                            if log_callback:
                                remaining = len(txt_files) - file_count
                                log_callback(f"Analyzing {txt_file.name} ({file_count}/{len(txt_files)} done, {remaining} remaining)...")
                            analysis_data = quick_analyze(
                                voltage=voltage,
                                current=current,
                                time=timestamps,
                                metadata=metadata,
                                analysis_level='classification',
                                device_id=device_id,
                                cycle_number=None,
                                save_directory=sample_dir
                            )

                            # If memristive, also run research analysis
                            device_type = analysis_data.get('classification', {}).get('device_type', '')
                            memristivity_score = analysis_data.get('classification', {}).get('memristivity_score', 0)

                            if device_type in ['memristive', 'memcapacitive'] or (memristivity_score and memristivity_score > 60):
                                if log_callback:
                                    log_callback(f"Running research analysis for {txt_file.name}...")
                                try:
                                    research_data = quick_analyze(
                                        voltage=voltage,
                                        current=current,
                                        time=timestamps,
                                        metadata=metadata,
                                        analysis_level='research',
                                        device_id=device_id,
                                        cycle_number=None,
                                        save_directory=sample_dir
                                    )

                                    # Save research data
                                    self._save_research_analysis(
                                        research_data,
                                        sample_dir,
                                        txt_file.stem,
                                        device_id
                                    )
                                except Exception as research_exc:
                                    print(f"[RETROACTIVE] Research analysis failed for {txt_file.name}: {research_exc}")

                            analyzed_count += 1

                        except Exception as file_exc:
                            if log_callback:
                                log_callback(f"Error processing {txt_file.name}: {str(file_exc)[:50]}")
                            print(f"[RETROACTIVE] Error processing {txt_file.name}: {file_exc}")
                            continue

                    # Update status periodically
                    if log_callback and analyzed_count % 5 == 0:
                        log_callback(f"Analyzed {analyzed_count} file(s) so far...")
                    elif hasattr(self, 'analysis_status_label') and analyzed_count % 5 == 0:
                        self.analysis_status_label.config(text=f"Analyzed {analyzed_count} files...")
                        self.master.update_idletasks()

            if log_callback:
                log_callback(f"✓ Retroactive analysis complete: {analyzed_count} file(s) analyzed")
            return analyzed_count

        except Exception as e:
            if log_callback:
                log_callback(f"✗ Retroactive analysis failed: {str(e)[:50]}")
            print(f"[RETROACTIVE ERROR] Failed to run retroactive analysis: {e}")
            import traceback
            traceback.print_exc()
            return 0
    
    def _update_stats_plots(self, history: Dict[str, Any], device_id: str) -> None:
        """Update trend plots for device tracking"""
        try:
            if not hasattr(self, 'stats_plot_figure') or not hasattr(self, 'stats_plot_canvas'):
                return
            
            measurements = history.get('measurements', [])
            if len(measurements) < 2:
                # Not enough data for trends - show message
                fig = self.stats_plot_figure
                fig.clear()
                ax = fig.add_subplot(111)
                ax.text(0.5, 0.5, 'Not enough data\nfor trend analysis\n\n(Need 2+ measurements)',
                       ha='center', va='center', fontsize=14, color='gray')
                ax.axis('off')
                self.stats_plot_canvas.draw()
                return
            
            import numpy as np
            from datetime import datetime
            
            # Extract time series data
            timestamps = []
            memristivity_scores = []
            rons = []
            roffs = []
            switching_ratios = []
            confidences = []
            device_types = []
            voltages = []  # Track max voltage per measurement
            
            for i, m in enumerate(measurements):
                timestamps.append(i + 1)  # Cycle number
                
                # Classification metrics
                classification = m.get('classification', {})
                score = classification.get('memristivity_score')
                if score is not None:
                    memristivity_scores.append(score)
                confidence = classification.get('confidence')
                if confidence is not None:
                    confidences.append(confidence * 100)
                device_types.append(classification.get('device_type', 'unknown'))
                
                # Resistance metrics
                resistance = m.get('resistance', {})
                ron = resistance.get('ron_mean')
                if ron is not None:
                    rons.append(ron)
                roff = resistance.get('roff_mean')
                if roff is not None:
                    roffs.append(roff)
                ratio = resistance.get('switching_ratio')
                if ratio is not None:
                    switching_ratios.append(ratio)
                
                # Voltage tracking (for forming analysis)
                voltage_data = m.get('voltage', {})
                max_v = voltage_data.get('max_voltage', 0)
                voltages.append(abs(max_v) if max_v else 0)
            
            # FORMING ANALYSIS: Detect if device is forming vs degrading
            forming_status = self._analyze_forming_process(
                memristivity_scores, switching_ratios, rons, roffs, voltages
            )
            
            # Create plots
            fig = self.stats_plot_figure
            fig.clear()
            
            # Title with forming status
            status = forming_status['status']
            status_colors = {
                'forming': '#2196F3',  # Blue
                'formed': '#4CAF50',   # Green
                'degrading': '#F44336',  # Red
                'unstable': '#FF9800',  # Orange
                'stable': '#9E9E9E',   # Gray
                'insufficient_data': '#9E9E9E',
                'unknown': '#9E9E9E'
            }
            status_color = status_colors.get(status, '#000000')
            
            title_text = f'Device Evolution: {device_id}'
            if status != 'insufficient_data' and status:
                confidence_pct = int(forming_status.get('confidence', 0) * 100)
                # Handle None case for status
                status_str = status.upper() if isinstance(status, str) else 'UNKNOWN'
                title_text += f'  |  Status: {status_str} ({confidence_pct}%)'
            
            fig.suptitle(title_text, fontsize=11, fontweight='bold', color=status_color)
            
            # 4 subplots stacked vertically
            gs = fig.add_gridspec(4, 1, hspace=0.4, left=0.15, right=0.95, top=0.93, bottom=0.05)
            
            # Plot 1: Memristivity Score over time
            if memristivity_scores:
                ax1 = fig.add_subplot(gs[0])
                ax1.plot(timestamps[:len(memristivity_scores)], memristivity_scores, 
                        'o-', color='#2196F3', linewidth=2, markersize=6)
                ax1.axhline(y=80, color='green', linestyle='--', alpha=0.3, label='Excellent')
                ax1.axhline(y=60, color='orange', linestyle='--', alpha=0.3, label='Good')
                ax1.axhline(y=40, color='red', linestyle='--', alpha=0.3, label='Poor')
                ax1.set_ylabel('Memristivity\nScore', fontsize=9)
                ax1.set_ylim(0, 105)
                ax1.grid(True, alpha=0.3)
                ax1.legend(loc='upper right', fontsize=7)
                ax1.tick_params(labelsize=8)
                
                # Add forming-aware indicators
                if len(memristivity_scores) > 1:
                    trend = memristivity_scores[-1] - memristivity_scores[0]
                    if abs(trend) > 5:
                        if status == 'forming' and trend > 0:
                            # Forming - show progress
                            progress = forming_status['progress']
                            ax1.text(0.02, 0.98, f'🔧 Forming: {progress}%', 
                                    transform=ax1.transAxes, fontsize=9, color='blue',
                                    va='top', fontweight='bold')
                        elif status == 'degrading' and trend < 0:
                            # Degrading - show warning
                            arrow = '↓'
                            ax1.text(0.02, 0.98, f'⚠ {arrow} {abs(trend):.1f}', 
                                    transform=ax1.transAxes, fontsize=10, color='red',
                                    va='top', fontweight='bold')
                        else:
                            # Normal trend
                            arrow = '↑' if trend > 0 else '↓'
                            color = 'green' if trend > 0 else 'orange'
                            ax1.text(0.02, 0.98, f'{arrow} {abs(trend):.1f}', 
                                    transform=ax1.transAxes, fontsize=10, color=color,
                                    va='top', fontweight='bold')
            
            # Plot 2: Ron/Roff over time
            if rons and roffs:
                ax2 = fig.add_subplot(gs[1])
                x_ron = timestamps[:len(rons)]
                x_roff = timestamps[:len(roffs)]
                ax2.semilogy(x_ron, rons, 'o-', color='#4CAF50', linewidth=2, 
                            markersize=6, label='Ron (ON)')
                ax2.semilogy(x_roff, roffs, 's-', color='#F44336', linewidth=2, 
                            markersize=6, label='Roff (OFF)')
                ax2.set_ylabel('Resistance\n(Ω)', fontsize=9)
                ax2.grid(True, alpha=0.3, which='both')
                ax2.legend(loc='upper right', fontsize=7)
                ax2.tick_params(labelsize=8)
                
                # Add drift indicators (only warn if not forming)
                if len(rons) > 1:
                    ron_drift = (rons[-1] - rons[0]) / (rons[0] + 1e-20) * 100
                    if abs(ron_drift) > 10 and status != 'forming':
                        arrow = '↑' if ron_drift > 0 else '↓'
                        color = 'red' if abs(ron_drift) > 20 else 'orange'
                        warning = '⚠ ' if abs(ron_drift) > 20 else ''
                        ax2.text(0.02, 0.98, f'{warning}Ron {arrow} {abs(ron_drift):.0f}%', 
                                transform=ax2.transAxes, fontsize=9, color=color,
                                va='top', fontweight='bold')
                    elif status == 'forming':
                        ax2.text(0.02, 0.98, '🔧 Forming', 
                                transform=ax2.transAxes, fontsize=9, color='blue',
                                va='top', fontweight='bold')
            
            # Plot 3: Switching Ratio over time
            if switching_ratios:
                ax3 = fig.add_subplot(gs[2])
                ax3.plot(timestamps[:len(switching_ratios)], switching_ratios, 
                        'o-', color='#9C27B0', linewidth=2, markersize=6)
                ax3.set_ylabel('Switching\nRatio', fontsize=9)
                ax3.grid(True, alpha=0.3)
                ax3.tick_params(labelsize=8)
                
                # Add mean line
                mean_ratio = np.mean(switching_ratios)
                ax3.axhline(y=mean_ratio, color='gray', linestyle='--', 
                           alpha=0.5, label=f'Mean: {mean_ratio:.1f}')
                ax3.legend(loc='upper right', fontsize=7)
                
                # Add forming-aware indicators
                if len(switching_ratios) > 1:
                    ratio_change = (switching_ratios[-1] - switching_ratios[0]) / (switching_ratios[0] + 1e-20) * 100
                    
                    if status == 'forming' and ratio_change > 10:
                        # Forming and improving - positive indicator
                        ax3.text(0.02, 0.98, f'🔧 Improving (+{ratio_change:.0f}%)', 
                                transform=ax3.transAxes, fontsize=9, color='blue',
                                va='top', fontweight='bold')
                    elif status == 'degrading' and ratio_change < -20:
                        # Degrading - strong warning
                        ax3.text(0.02, 0.98, f'⚠ Degrading ({ratio_change:.0f}%)', 
                                transform=ax3.transAxes, fontsize=9, color='red',
                                va='top', fontweight='bold')
                    elif ratio_change < -20 and status != 'forming':
                        # Declining but not during forming
                        ax3.text(0.02, 0.98, f'⚠ Declining ({ratio_change:.0f}%)', 
                                transform=ax3.transAxes, fontsize=9, color='orange',
                                va='top', fontweight='bold')
            
            # Plot 4: Classification confidence & type changes
            if confidences:
                ax4 = fig.add_subplot(gs[3])
                ax4.plot(timestamps[:len(confidences)], confidences, 
                        'o-', color='#FF9800', linewidth=2, markersize=6)
                ax4.set_ylabel('Confidence\n(%)', fontsize=9)
                ax4.set_xlabel('Measurement #', fontsize=9)
                ax4.set_ylim(0, 105)
                ax4.grid(True, alpha=0.3)
                ax4.tick_params(labelsize=8)
                
                # Mark classification changes
                for i in range(1, len(device_types)):
                    if device_types[i] != device_types[i-1]:
                        ax4.axvline(x=timestamps[i], color='red', linestyle=':', alpha=0.5)
                        ax4.text(timestamps[i], 5, 'Type\nChanged', 
                                rotation=90, fontsize=7, color='red', va='bottom')
            
            # Update canvas
            self.stats_plot_canvas.draw()
            
        except Exception as e:
            print(f"[STATS] Error updating plots: {e}")
            import traceback
            traceback.print_exc()
    
    def _format_analysis_value(self, value: Any, unit: str = "", precision: int = 3) -> str:
        """
        Format a numeric value for analysis output.
        
        Parameters:
        -----------
        value : Any
            Value to format
        unit : str
            Unit to append (e.g., "V", "Ω", "%")
        precision : int
            Number of decimal places
        
        Returns:
        --------
        str : Formatted value string
        """
        if value is None:
            return "N/A"
        
        try:
            if isinstance(value, (int, float)):
                if abs(value) >= 1e6:
                    return f"{value/1e6:.{precision}f} M{unit}"
                elif abs(value) >= 1e3:
                    return f"{value/1e3:.{precision}f} k{unit}"
                elif abs(value) < 1e-3 and abs(value) > 0:
                    return f"{value*1e6:.{precision}f} μ{unit}"
                elif abs(value) < 1e-6 and abs(value) > 0:
                    return f"{value*1e9:.{precision}f} n{unit}"
                else:
                    return f"{value:.{precision}f} {unit}".strip()
            else:
                return str(value)
        except (ValueError, TypeError):
            return str(value) if value is not None else "N/A"

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

    def _load_conditional_test_config(self) -> Dict[str, Any]:
        """Load conditional testing configuration from JSON file."""
        config_path = _PROJECT_ROOT / "Json_Files" / "conditional_test_config.json"
        if not config_path.exists():
            print(f"[Conditional Testing] Config not found at {config_path}, using defaults.")
            return {
                "quick_test": {"custom_sweep_name": "", "timeout_s": 300},
                "thresholds": {"basic_memristive": 60, "high_quality": 80},
                "re_evaluate_during_test": {"enabled": True},
                "include_memcapacitive": True,
                "tests": {
                    "basic_memristive": {"custom_sweep_name": ""},
                    "high_quality": {"custom_sweep_name": ""}
                },
                "final_test": {
                    "enabled": False,
                    "selection_mode": "top_x",
                    "top_x_count": 3,
                    "min_score_threshold": 80.0,
                    "custom_sweep_name": ""
                }
            }
        try:
            with config_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data
        except Exception as exc:
            print(f"[Conditional Testing] Failed to load {config_path}: {exc}")
            return {
                "quick_test": {"custom_sweep_name": "", "timeout_s": 300},
                "thresholds": {"basic_memristive": 60, "high_quality": 80},
                "re_evaluate_during_test": {"enabled": True},
                "include_memcapacitive": True,
                "tests": {
                    "basic_memristive": {"custom_sweep_name": ""},
                    "high_quality": {"custom_sweep_name": ""}
                },
                "final_test": {
                    "enabled": False,
                    "selection_mode": "top_x",
                    "top_x_count": 3,
                    "min_score_threshold": 80.0,
                    "custom_sweep_name": ""
                }
            }

    def _save_conditional_test_config(self, config: Dict[str, Any]) -> bool:
        """Save conditional testing configuration to JSON file."""
        config_path = _PROJECT_ROOT / "Json_Files" / "conditional_test_config.json"
        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with config_path.open("w", encoding="utf-8") as handle:
                json.dump(config, handle, indent=2, ensure_ascii=False)
            return True
        except Exception as exc:
            print(f"[Conditional Testing] Failed to save {config_path}: {exc}")
            messagebox.showerror("Save Error", f"Failed to save conditional testing config:\n{exc}")
            return False

    def _run_analysis_sync(
        self,
        voltage: List[float],
        current: List[float],
        timestamps: Optional[List[float]],
        device_id: str,
        save_dir: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Run analysis synchronously (blocking until complete).
        Returns analysis dictionary or None if failed.
        """
        from Helpers.Analysis import quick_analyze
        
        try:
            # Determine analysis level
            analysis_level = getattr(self, 'analysis_level', 'full')
            if not hasattr(self, 'analysis_enabled') or not self.analysis_enabled:
                analysis_level = 'none'
            
            if analysis_level == 'none':
                return None
            
            # Run analysis
            print(f"[Conditional Testing] Running synchronous analysis on {len(voltage)} points...")
            analysis_data = quick_analyze(
                voltage=voltage,
                current=current,
                time=timestamps,
                analysis_level=analysis_level,
                device_id=device_id,
                save_directory=save_dir
            )
            
            return analysis_data
        except Exception as exc:
            print(f"[Conditional Testing] Analysis failed: {exc}")
            import traceback
            traceback.print_exc()
            return None

    def _run_quick_test(self, custom_sweep_name: str, device: str) -> Tuple[List[float], List[float], List[float]]:
        """
        Run quick screening test using a custom sweep.
        Returns (voltage_array, current_array, timestamps_array).
        """
        if not custom_sweep_name or custom_sweep_name not in self.custom_sweeps:
            raise ValueError(f"Quick test '{custom_sweep_name}' not found in custom sweeps")
        
        print(f"[Conditional Testing] Running quick test '{custom_sweep_name}' on device {device}")
        
        # Temporarily store original custom measurement selection
        original_selection = getattr(self, 'custom_measurement_var', None)
        if original_selection:
            original_value = original_selection.get()
        else:
            original_value = None
        
        # Set the quick test as the selected measurement
        if hasattr(self, 'custom_measurement_var'):
            self.custom_measurement_var.set(custom_sweep_name)
        
        # Get the first sweep from the quick test
        sweeps = self.custom_sweeps[custom_sweep_name]["sweeps"]
        if not sweeps:
            raise ValueError(f"Quick test '{custom_sweep_name}' has no sweeps defined")
        
        # Get the first sweep parameters
        first_sweep_key = sorted(sweeps.keys(), key=lambda x: int(x) if x.isdigit() else 0)[0]
        params = sweeps[first_sweep_key]
        
        # Execute the sweep
        try:
            # Use the existing custom measurement infrastructure but run just one sweep
            v_arr, c_arr, t_arr = self._execute_single_sweep_for_conditional_test(params, device)
            return v_arr, c_arr, t_arr
        finally:
            # Restore original selection
            if original_selection and original_value:
                original_selection.set(original_value)

    def _execute_single_sweep_for_conditional_test(
        self,
        params: Dict[str, Any],
        device: str
    ) -> Tuple[List[float], List[float], List[float]]:
        """Execute a single sweep for conditional testing."""
        from Measurments.source_modes import SourceMode
        
        # Read measurement type
        measurement_type = str(params.get("measurement_type", "IV"))
        if "mode" in params:
            measurement_type = params["mode"]
        elif "excitation" in params:
            excitation_map = {
                "DC Triangle IV": "IV",
                "SMU Pulsed IV": "PulsedIV",
                "SMU Fast Pulses": "FastPulses",
                "SMU Fast Hold": "Hold"
            }
            measurement_type = excitation_map.get(params["excitation"], "IV")
        
        # Read parameters
        start_v = params.get("start_v", 0)
        stop_v = params.get("stop_v", 1)
        step_v = params.get("step_v", 0.1)
        num_sweeps = params.get("sweeps", 1)
        step_delay = params.get("step_delay", 0.05)
        sweep_type = params.get("Sweep_type", "FS")
        icc_val = params.get("icc", float(self.icc.get()) if hasattr(self, 'icc') else 1e-3)
        
        # LED control
        led = bool(params.get("LED_ON", 0))
        power = params.get("power", 1)
        sequence = params.get("sequence", None)
        if sequence == 0:
            sequence = None
        
        # Execute IV sweep
        if measurement_type == "IV":
            def _on_point(v, i, t_s):
                pass  # Don't update display for quick test
            
            v_arr, c_arr, timestamps = self.measurement_service.run_iv_sweep(
                keithley=self.keithley,
                start_v=start_v,
                stop_v=stop_v,
                step_v=step_v,
                sweeps=num_sweeps,
                step_delay=step_delay,
                sweep_type=sweep_type,
                icc=icc_val,
                psu=getattr(self, 'psu', None),
                led=led,
                power=power,
                optical=getattr(self, 'optical', None),
                sequence=sequence,
                pause_s=0,
                smu_type=getattr(self, 'SMU_type', 'Keithley 2401'),
                source_mode=SourceMode.VOLTAGE,
                should_stop=lambda: getattr(self, 'stop_measurement_flag', False),
                on_point=_on_point
            )
            return v_arr, c_arr, timestamps
        else:
            raise ValueError(f"Quick test measurement type '{measurement_type}' not supported for conditional testing")

    def _run_tiered_test(self, test_config: Dict[str, Any], device: str) -> Optional[Tuple[List[float], List[float], List[float]]]:
        """
        Run a tiered test (basic or high-quality) using a custom sweep.
        Returns (v_arr, c_arr, t_arr) of the last sweep for re-evaluation, or None.
        """
        custom_sweep_name = test_config.get("custom_sweep_name", "")
        if not custom_sweep_name or custom_sweep_name not in self.custom_sweeps:
            print(f"[Conditional Testing] Warning: Test '{custom_sweep_name}' not found, skipping")
            return None
        
        print(f"[Conditional Testing] Running tiered test '{custom_sweep_name}' on device {device}")
        
        # Temporarily store original selection
        original_selection = getattr(self, 'custom_measurement_var', None)
        if original_selection:
            original_value = original_selection.get()
        else:
            original_value = None
        
        last_v_arr, last_c_arr, last_t_arr = None, None, None
        
        try:
            # Set the test as selected
            if hasattr(self, 'custom_measurement_var'):
                self.custom_measurement_var.set(custom_sweep_name)
            
            # Run the custom measurement (but only for this device)
            sweeps = self.custom_sweeps[custom_sweep_name]["sweeps"]
            
            for key, params in sweeps.items():
                if self.stop_measurement_flag:
                    break
                
                # Execute this sweep
                v_arr, c_arr, t_arr = self._execute_single_sweep_for_conditional_test(params, device)
                last_v_arr, last_c_arr, last_t_arr = v_arr, c_arr, t_arr
                
                # Save the data
                save_dir = self._get_save_directory(
                    self.sample_name_var.get(),
                    self.final_device_letter,
                    self.final_device_number
                )
                import os
                os.makedirs(save_dir, exist_ok=True)
                
                from Measurments.single_measurement_runner import find_largest_number_in_folder
                key_num = find_largest_number_in_folder(save_dir)
                save_key = 0 if key_num is None else key_num + 1
                
                # Extract parameters for filename (matching custom measurement format)
                stop_v = params.get("stop_v", 1)
                step_v = params.get("step_v", 0.1)
                step_delay = params.get("step_delay", 0.05)
                sweep_type = params.get("Sweep_type", "FS")
                code_name = self.custom_sweeps[custom_sweep_name].get("code_name", custom_sweep_name)
                
                import numpy as np
                from pathlib import Path
                name = f"{save_key}-{sweep_type}-{stop_v}v-{step_v}sv-{step_delay}sd-Py-{code_name}"
                file_path = Path(save_dir) / f"{name}.txt"
                
                try:
                    data = np.column_stack((v_arr, c_arr, t_arr))
                    np.savetxt(
                        file_path,
                        data,
                        fmt="%0.3E\t%0.3E\t%0.3E",
                        header="Voltage(V) Current(A) Time(s)",
                        comments=""
                    )
                    print(f"[Conditional Testing] Saved: {file_path}")
                except Exception as exc:
                    print(f"[Conditional Testing] Failed to save {file_path}: {exc}")
        finally:
            # Restore original selection
            if original_selection and original_value:
                original_selection.set(original_value)
        
        # Return last sweep data for re-evaluation
        if last_v_arr is not None:
            return (last_v_arr, last_c_arr, last_t_arr)
        return None

    def _get_latest_analysis_for_device(self, device: str) -> Optional[Dict[str, Any]]:
        """
        Get the latest analysis result for a device.
        This checks saved analysis files or pending results.
        """
        # Check pending analysis results first
        if hasattr(self, '_pending_analysis_results'):
            # Find the most recent analysis for this device
            for key, result in self._pending_analysis_results.items():
                if device in key:
                    return result.get('analysis_data')
        
        # Try to load from saved analysis files
        try:
            save_dir = self._get_save_directory(
                self.sample_name_var.get(),
                self.final_device_letter,
                self.final_device_number
            )
            analysis_dir = Path(save_dir) / "sample_analysis" / "analysis" / "sweeps" / device
            if analysis_dir.exists():
                # Find the most recent analysis JSON file
                json_files = list(analysis_dir.glob("*.json"))
                if json_files:
                    latest_file = max(json_files, key=lambda p: p.stat().st_mtime)
                    with latest_file.open("r", encoding="utf-8") as f:
                        return json.load(f)
        except Exception as exc:
            print(f"[Conditional Testing] Failed to load analysis for {device}: {exc}")
        
        return None

    def run_conditional_testing(self) -> None:
        """
        Main entry point for conditional memristive testing.
        Runs quick test on all devices, analyzes, and conditionally runs additional tests.
        """
        if not self.connected:
            messagebox.showwarning("Warning", "Not connected to Keithley!")
            return
        
        # Load config
        config = self._load_conditional_test_config()
        
        # Get configuration values
        quick_test_name = config.get("quick_test", {}).get("custom_sweep_name", "")
        if not quick_test_name:
            messagebox.showerror("Error", "Quick test not configured. Please select a quick test.")
            return
        
        basic_threshold = config.get("thresholds", {}).get("basic_memristive", 60)
        high_quality_threshold = config.get("thresholds", {}).get("high_quality", 80)
        re_evaluate_enabled = config.get("re_evaluate_during_test", {}).get("enabled", True)
        include_memcapacitive = config.get("include_memcapacitive", True)
        
        basic_test_name = config.get("tests", {}).get("basic_memristive", {}).get("custom_sweep_name", "")
        high_quality_test_name = config.get("tests", {}).get("high_quality", {}).get("custom_sweep_name", "")
        
        if not basic_test_name:
            messagebox.showerror("Error", "Basic memristive test not configured.")
            return
        
        # Reset stop flag
        self.stop_measurement_flag = False
        
        # Track device scores for final test selection
        device_scores = {}  # {device: score}
        
        # Iterate through devices
        device_count = len(self.device_list)
        start_index = 0
        if self.current_device in self.device_list:
            start_index = self.device_list.index(self.current_device)
        
        for i in range(device_count):
            device = self.device_list[(start_index + i) % device_count]
            
            if self.stop_measurement_flag:
                print("[Conditional Testing] Measurement interrupted!")
                break
            
            print(f"[Conditional Testing] Processing device {device}")
            self.set_status_message(f"Conditional Testing: Device {device}")
            self.master.update()
            
            try:
                # 1. Run quick test
                v_arr, c_arr, t_arr = self._run_quick_test(quick_test_name, device)
                
                # 2. Analyze synchronously
                save_dir = self._get_save_directory(
                    self.sample_name_var.get(),
                    self.final_device_letter,
                    self.final_device_number
                )
                analysis = self._run_analysis_sync(v_arr, c_arr, t_arr, device, save_dir)
                
                if not analysis:
                    print(f"[Conditional Testing] Analysis failed for device {device}, skipping")
                    continue
                
                score = analysis.get('classification', {}).get('memristivity_score', 0)
                device_type = analysis.get('classification', {}).get('device_type', '')
                
                # Store score for final test selection
                device_scores[device] = score
                
                # Check if device qualifies (memristive or memcapacitive, unless excluded)
                is_qualified = False
                if include_memcapacitive:
                    is_qualified = device_type in ['memristive', 'memcapacitive'] or score >= basic_threshold
                else:
                    is_qualified = device_type == 'memristive' or score >= basic_threshold
                
                print(f"[Conditional Testing] Device {device}: Score={score:.1f}, Type={device_type}, Qualified={is_qualified} (include_memcapacitive={include_memcapacitive})")
                
                # 3. Conditionally run tests
                if is_qualified:
                    # Run basic memristive test
                    basic_test_data = None
                    if basic_test_name:
                        basic_test_data = self._run_tiered_test(
                            {"custom_sweep_name": basic_test_name},
                            device
                        )
                    
                    # Check if already qualified for high-quality test
                    if score >= high_quality_threshold:
                        if high_quality_test_name:
                            self._run_tiered_test(
                                {"custom_sweep_name": high_quality_test_name},
                                device
                            )
                    
                    # If re-evaluation enabled, check during/after basic test
                    elif re_evaluate_enabled and basic_test_name and basic_test_data:
                        # Re-analyze the basic test results
                        basic_v, basic_c, basic_t = basic_test_data
                        basic_test_analysis = self._run_analysis_sync(basic_v, basic_c, basic_t, device, save_dir)
                        if basic_test_analysis:
                            new_score = basic_test_analysis.get('classification', {}).get('memristivity_score', 0)
                            new_device_type = basic_test_analysis.get('classification', {}).get('device_type', '')
                            
                            # Check if qualifies for high-quality test (using same logic)
                            qualifies_high_quality = False
                            if include_memcapacitive:
                                qualifies_high_quality = new_device_type in ['memristive', 'memcapacitive'] or new_score >= high_quality_threshold
                            else:
                                qualifies_high_quality = new_device_type == 'memristive' or new_score >= high_quality_threshold
                            
                            print(f"[Conditional Testing] Device {device}: Re-evaluation score={new_score:.1f}, type={new_device_type}, qualifies={qualifies_high_quality}")
                            if qualifies_high_quality:
                                # Score improved during basic test, run high-quality test
                                if high_quality_test_name:
                                    print(f"[Conditional Testing] Device {device}: Score improved to {new_score:.1f}, running high-quality test")
                                    self._run_tiered_test(
                                        {"custom_sweep_name": high_quality_test_name},
                                        device
                                    )
                else:
                    print(f"[Conditional Testing] Device {device}: Score {score:.1f} below threshold {basic_threshold}, skipping additional tests")
                
            except Exception as exc:
                print(f"[Conditional Testing] Error processing device {device}: {exc}")
                import traceback
                traceback.print_exc()
                continue
        
        # Run final test if enabled
        final_test_config = config.get("final_test", {})
        if final_test_config.get("enabled", False):
            self._run_final_test(final_test_config, device_scores)
        
        self.set_status_message("Conditional Testing Complete")
        messagebox.showinfo("Complete", "Conditional testing finished for all devices.")

    def _update_conditional_testing_button_state(self) -> None:
        """Update the conditional testing run button state based on connection status."""
        if hasattr(self, 'conditional_testing_run_button'):
            if self.connected:
                self.conditional_testing_run_button.config(state=tk.NORMAL)
            else:
                self.conditional_testing_run_button.config(state=tk.DISABLED)
        if hasattr(self, 'run_conditional_button_main'):
            if self.connected:
                self.run_conditional_button_main.config(state=tk.NORMAL)
            else:
                self.run_conditional_button_main.config(state=tk.DISABLED)

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

        # Initialize as Tk StringVar objects (required by TelegramCoordinator)
        self.token_var = tk.StringVar(value=profile.get("token", ""))
        self.chatid_var = tk.StringVar(value=profile.get("chatid", ""))
        self.get_messaged_var = tk.IntVar(value=0)
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

            if AutomatedTesterGUI is None:
                messagebox.showerror("AutoTester", "AutomatedTesterGUI module not available")
                return
            
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
            self.tsp_btn = tk.Button(
                frame,
                text="2450 TSP Pulse Testing",
                command=self.open_pulse_testing_gui,
            )
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

    def open_pulse_testing_gui(self) -> None:
        """Launch the pulse testing GUI with current sample/context info."""
        sample_name = None
        if hasattr(self, "sample_name_var"):
            try:
                sample_name = self.sample_name_var.get().strip()
            except Exception:
                sample_name = None
        if not sample_name and hasattr(self, "sample_gui") and self.sample_gui:
            for attr in ("current_device_name", "current_sample_name", "sample_name"):
                fallback = getattr(self.sample_gui, attr, None)
                if fallback:
                    sample_name = str(fallback).strip()
                    break

        device_label = getattr(self, "device_section_and_number", None)
        custom_path = None
        use_custom_var = getattr(self, "use_custom_save_var", None)
        if use_custom_var and use_custom_var.get():
            custom_loc = getattr(self, "custom_save_location", None)
            if custom_loc:
                custom_path = str(custom_loc)

        address = getattr(self, "keithley_address", None)
        if (not address) and hasattr(self, "keithley_address_var"):
            try:
                address = self.keithley_address_var.get().strip()
            except Exception:
                address = None

        try:
            TSPTestingGUI(
                self.master,
                device_address=address or "GPIB0::17::INSTR",
                provider=self,
                sample_name=sample_name,
                device_label=device_label,
                custom_save_base=custom_path,
            )
        except Exception as exc:
            messagebox.showerror("Pulse Testing", f"Could not open Pulse Testing GUI:\n{exc}")

    def open_device_visualizer(self) -> None:
        """Launch the Device Analysis Visualizer with current sample/context info."""
        # Get sample name (same logic as open_pulse_testing_gui)
        sample_name = None
        if hasattr(self, "sample_name_var"):
            try:
                sample_name = self.sample_name_var.get().strip()
            except Exception:
                sample_name = None
        
        # Fallback to sample_gui if available
        if not sample_name and hasattr(self, "sample_gui") and self.sample_gui:
            for attr in ("current_device_name", "current_sample_name", "sample_name"):
                fallback = getattr(self.sample_gui, attr, None)
                if fallback:
                    sample_name = str(fallback).strip()
                    break
        
        # Get sample save directory path
        sample_path = None
        if sample_name:
            try:
                sample_path = self._get_sample_save_directory(sample_name)
            except Exception:
                sample_path = None
        
        # Launch the visualizer
        try:
            from Helpers.Data_Analysis.device_visualizer_app import launch_visualizer
            # Note: launch_visualizer creates its own QApplication, so this will
            # run in a separate process/event loop
            launch_visualizer(sample_path=sample_path)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            messagebox.showerror(
                "Device Visualizer", 
                f"Could not open Device Visualizer:\n{exc}"
            )

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
            
            # Update orange overlay box to stay in sync with sample/device changes
            if hasattr(self, '_update_overlay_from_current_state'):
                try:
                    self._update_overlay_from_current_state()
                except Exception as e:
                    # Silently fail to avoid spamming errors
                    pass
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
                                             command=self._handle_system_selection)
        self.system_dropdown.grid(row=0, column=1, columnspan=2, sticky="ew")

        # GPIB Address - IV
        self.iv_label = tk.Label(frame, text="GPIB Address - IV:")
        self.iv_label.grid(row=1, column=0, sticky="w")
        self.keithley_address_var = tk.StringVar(value=self.keithley_address)
        self.iv_address_entry = tk.Entry(frame, textvariable=self.keithley_address_var)
        self.iv_address_entry.grid(row=1, column=1)
        self.iv_connect_button = tk.Button(frame, text="Connect", command=self.auto_connect_current_system)
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
        """Set default system to 'Please Select System' without auto-connecting"""
        systems = self.systems
        default = "Please Select System"
        # Set to "Please Select System" without triggering auto-connect
        self.system_var.set(default)
        # Don't call _handle_system_selection to avoid auto-connection

    def load_systems(self) -> List[str]:
        """Load system configurations from JSON file"""
        config_file = str(_PROJECT_ROOT / "Json_Files" / "system_configs.json")

        try:
            with open(config_file, 'r') as f:
                self.system_configs = json.load(f)
            systems_list = list(self.system_configs.keys())
            # Prepend "Please Select System" to the list
            return ["Please Select System"] + systems_list
        except (FileNotFoundError, json.JSONDecodeError):
            return ["Please Select System", "No systems available"]

    def load_system(self) -> None:
        """Load the selected system configuration and populate all fields"""
        selected_system = getattr(self, 'system_var', None)
        if not selected_system:
            return
        
        system_name = selected_system.get() if hasattr(selected_system, 'get') else str(selected_system)
        if not system_name or system_name == "No systems available" or system_name == "Please Select System":
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
        temp_type = config.get("temp_controller")
        if not temp_type or temp_type.strip() == "":
            temp_type = "None"
        temp_address = config.get("temp_address", "")
        if temp_type == "None":
            temp_address = ""
        if hasattr(self, 'temp_type_var'):
            self.temp_type_var.set(temp_type)
        if hasattr(self, 'temp_address_var'):
            self.temp_address_var.set(temp_address)
        # Ensure address is in combobox values if using combobox
        if hasattr(self, 'temp_address_combo') and temp_address:
            current_values = list(self.temp_address_combo['values'])
            if temp_address not in current_values:
                self.temp_address_combo['values'] = tuple([temp_address] + list(current_values))
        self.temp_controller_type = temp_type if temp_type != "None" else ""
        self.temp_controller_address = temp_address
        self.controller_type = temp_type
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
        if selected_system == "Please Select System" or not selected_system:
            # Don't update addresses if no system selected
            return
            
        if selected_system in self.system_configs:
            config = self.system_configs[selected_system]

            # Update IV section
            iv_address = config.get("SMU_address", "")
            self.iv_address = iv_address
            self.keithley_address = iv_address
            
            # Update the StringVar (this should sync with combobox if bound)
            if hasattr(self, 'keithley_address_var'):
                self.keithley_address_var.set(iv_address)
            
            # Also explicitly update combobox if it exists (in case it's not bound properly)
            if hasattr(self, 'iv_address_combo'):
                # Ensure address is in combobox values first
                current_values = list(self.iv_address_combo['values'])
                if iv_address and iv_address not in current_values:
                    self.iv_address_combo['values'] = tuple([iv_address] + list(current_values))
                # Then set the value
                self.iv_address_combo.set(iv_address)
            
            self.update_component_state("iv", iv_address)

            # Update PSU section
            psu_address = config.get("psu_address", "")
            if hasattr(self, 'psu_address_var'):
                self.psu_address_var.set(psu_address)
            self.psu_visa_address = psu_address
            self.update_component_state("psu", psu_address)

            # Update Temp section
            temp_type = config.get("temp_controller")
            if not temp_type or temp_type.strip() == "":
                temp_type = "None"
            temp_address = config.get("temp_address", "")
            if temp_type == "None":
                temp_address = ""
            if hasattr(self, 'temp_type_var'):
                self.temp_type_var.set(temp_type)
            if hasattr(self, 'temp_address_var'):
                self.temp_address_var.set(temp_address)
            self.temp_controller_address = temp_address
            self.update_component_state("temp", temp_address)

            # updater controller type
            self.temp_controller_type = temp_type if temp_type != "None" else ""
            self.controller_type = temp_type
            self.controller_address = temp_address

            # smu type
            self.SMU_type = config.get("SMU Type", "")
            print(self.SMU_type)

            # Optical excitation (LED/Laser) selection based on config
            try:
                self.optical = create_optical_from_system_config(config)
            except Exception:
                self.optical = None

    def _handle_system_selection(self, selected_system: str) -> None:
        """Callback for legacy system dropdown - only connects if a valid system is selected."""
        # Don't auto-connect if "Please Select System" is selected
        if selected_system == "Please Select System" or not selected_system:
            self.on_system_change(selected_system)
            return
        
        self.on_system_change(selected_system)
        # Don't auto-connect - user must click Connect button manually
        # self.auto_connect_current_system()  # Removed auto-connect


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

    def auto_connect_current_system(self) -> bool:
        """Attempt to connect to the currently selected SMU and update status label."""
        keithley_address = ""
        if hasattr(self, "keithley_address_var"):
            try:
                keithley_address = self.keithley_address_var.get().strip()
            except Exception:
                keithley_address = ""
        if not keithley_address:
            keithley_address = getattr(self, "keithley_address", "").strip()

        smu_type = getattr(self, "SMU_type", "")
        if not smu_type and hasattr(self, "smu_type_var"):
            try:
                smu_type = self.smu_type_var.get()
            except Exception:
                smu_type = ""
        smu_type = smu_type or "Keithley 2401"

        status_label = getattr(self, "connection_status_label", None)
        success_color = getattr(self.layout_builder, "COLOR_SUCCESS", "green") if hasattr(self, "layout_builder") else "green"
        error_color = getattr(self.layout_builder, "COLOR_ERROR", "red") if hasattr(self, "layout_builder") else "red"
        warning_color = getattr(self.layout_builder, "COLOR_WARNING", "orange") if hasattr(self, "layout_builder") else "orange"

        if not keithley_address:
            print("⚠️  No SMU address configured; skipping auto-connect.")
            if status_label:
                status_label.config(text="● Address Required", fg=warning_color)
            return False

        if status_label:
            status_label.config(text="● Connecting...", fg=warning_color)

        print(f"Connecting to {smu_type} @ {keithley_address}...")
        self.connect_keithley()

        connected = getattr(self, "connected", False)
        if connected:
            idn = ""
            try:
                if hasattr(self.keithley, "get_idn"):
                    idn = self.keithley.get_idn()
            except Exception as exc:
                print(f"⚠️  Warning: Unable to query IDN: {exc}")
            status_text = idn or f"{smu_type} @ {keithley_address}"
            print(f"✓ Connected: {status_text}")
            if status_label:
                status_label.config(text=f"● Connected: {status_text}", fg=success_color)
            return True

        print(f"❌ Connection failed for {smu_type} @ {keithley_address}")
        if status_label:
            status_label.config(text="● Connection Failed", fg=error_color)
        return False
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
        
        # Auto-switch graphs based on measurement type
        def on_measurement_type_change(event=None):
            """Automatically switch graph visibility based on measurement type."""
            if not hasattr(self, 'plot_panels') or self.plot_panels is None:
                return
            
            meas_type = self.excitation_var.get()
            
            # Hide all specialized plots first
            if hasattr(self.plot_panels, 'plot_visibility'):
                # Reset visibility to defaults
                self.plot_panels.plot_visibility["rt_iv"].set(True)
                self.plot_panels.plot_visibility["rt_logiv"].set(True)
                self.plot_panels.plot_visibility["all_sweeps"].set(False)
                self.plot_panels.plot_visibility["logilogv"].set(False)
                self.plot_panels.plot_visibility["current_time"].set(False)
                self.plot_panels.plot_visibility["temp_time"].set(False)
                self.plot_panels.plot_visibility["endurance"].set(False)
                self.plot_panels.plot_visibility["endurance_current"].set(False)
                self.plot_panels.plot_visibility["retention"].set(False)
                
                # Show appropriate plots based on measurement type
                if meas_type == "Endurance":
                    # For endurance, show endurance plots prominently, keep IV plots for reference
                    self.plot_panels.plot_visibility["endurance"].set(True)
                    self.plot_panels.plot_visibility["endurance_current"].set(True)
                    self.plot_panels.plot_visibility["rt_iv"].set(True)
                    self.plot_panels.plot_visibility["rt_logiv"].set(False)  # Hide log IV for cleaner view
                    # Start endurance plot updater thread
                    if hasattr(self, 'plot_updaters'):
                        self.plot_updaters.start_endurance_thread(True)
                    print("[MeasurementGUI] Switched to Endurance plot view")
                elif meas_type == "Retention":
                    # For retention, show retention plot prominently, keep IV plots for reference
                    self.plot_panels.plot_visibility["retention"].set(True)
                    self.plot_panels.plot_visibility["rt_iv"].set(True)
                    self.plot_panels.plot_visibility["rt_logiv"].set(False)  # Hide log IV for cleaner view
                    # Start retention plot updater thread
                    if hasattr(self, 'plot_updaters'):
                        self.plot_updaters.start_retention_thread(True)
                    print("[MeasurementGUI] Switched to Retention plot view")
                else:
                    # For other measurements (IV sweeps, etc.), show IV plots
                    self.plot_panels.plot_visibility["rt_iv"].set(True)
                    self.plot_panels.plot_visibility["rt_logiv"].set(True)
                    print(f"[MeasurementGUI] Switched to IV plot view for {meas_type}")
                
                # Update the layout
                if hasattr(self.plot_panels, '_update_plot_layout'):
                    self.plot_panels._update_plot_layout()
        
        # Bind the change event
        self.excitation_menu.bind("<<ComboboxSelected>>", on_measurement_type_change)
        self.excitation_var.trace_add("write", lambda *args: on_measurement_type_change())

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
                sweep_type_values = ["FS", "PS", "NS", "HS"]
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
        tk.Label(frame, text="LED Controls", font=("Arial", 9, "bold"), bg='#f0f0f0').grid(row=22, column=0, columnspan=2, sticky="w",
                                                                             pady=(10, 2))

        # LED Toggle Button
        tk.Label(frame, text="LED Status:", bg='#f0f0f0').grid(row=23, column=0, sticky="w")
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
        self.led_button.grid(row=23, column=1, sticky="w")

        tk.Label(frame, text="Led_Power (0-1):", bg='#f0f0f0').grid(row=24, column=0, sticky="w")
        self.led_power = tk.DoubleVar(value=1)
        tk.Entry(frame, textvariable=self.led_power).grid(row=24, column=1)

        tk.Label(frame, text="Sequence: (01010)", bg='#f0f0f0').grid(row=25, column=0, sticky="w")
        self.sequence = tk.StringVar()
        tk.Entry(frame, textvariable=self.sequence).grid(row=25, column=1)

        # Other Controls mini title
        tk.Label(frame, text="Other", font=("Arial", 9, "bold"), bg='#f0f0f0').grid(row=26, column=0, columnspan=2, sticky="w",
                                                                      pady=(10, 2))

        tk.Label(frame, text="Pause at end?:", bg='#f0f0f0').grid(row=27, column=0, sticky="w")
        self.pause = tk.DoubleVar(value=0.0)
        tk.Entry(frame, textvariable=self.pause).grid(row=27, column=1)

        temp_row = 29
        tk.Label(frame, text="Target Temp (°C):", bg='#f0f0f0').grid(row=temp_row, column=0, sticky="w")
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
            self.temp_controller = None
            self.update_controller_status()
            return
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
        self._reset_plots_for_new_run(self)

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
                # Store total count before loop (sweeps dict may be shadowed inside loop)
                total_sweeps_count = len(sweeps)
                # Initial merge disabled; we now apply live edits per-sweep inside the loop
                code_name = self.custom_sweeps[selected_measurement].get("code_name", "unknown")
                
                # === CUSTOM MEASUREMENT ANALYSIS TRACKING ===
                # Track device memristive status across sweeps
                device_is_memristive = None  # Unknown until first sweep analyzed
                sequence_analysis_results = []  # Collect all analysis results
                sweep_classifications = {}  # Track score per sweep

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
                    num_sweeps_in_measurement = params.get("sweeps", 1)  # Renamed to avoid shadowing outer 'sweeps' dict
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
                            
                            # Flag to track if graphs have been cleared for this measurement
                            _graphs_cleared_for_this_measurement = False
                            
                            def _on_point(v, i, t_s):
                                nonlocal _graphs_cleared_for_this_measurement
                                # Clear graphs on first data point (right before plotting new data)
                                if not _graphs_cleared_for_this_measurement:
                                    if hasattr(self, '_reset_plots_for_new_sweep'):
                                        self._reset_plots_for_new_sweep(self)
                                    _graphs_cleared_for_this_measurement = True
                                
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
                            
                            # Flag to track if graphs have been cleared for this measurement
                            _graphs_cleared_for_this_measurement = False
                            
                            def _on_point(v, i, t_s):
                                nonlocal _graphs_cleared_for_this_measurement
                                # Clear graphs on first data point (right before plotting new data)
                                if not _graphs_cleared_for_this_measurement:
                                    if hasattr(self, '_reset_plots_for_new_sweep'):
                                        self._reset_plots_for_new_sweep(self)
                                    _graphs_cleared_for_this_measurement = True
                                
                                self.v_arr_disp.append(v)
                                self.c_arr_disp.append(i)
                                self.t_arr_disp.append(t_s)
                            
                            v_arr, c_arr, timestamps = self.measurement_service.run_iv_sweep(
                                keithley=self.keithley,
                                start_v=start_v,
                                stop_v=stop_v,
                                step_v=step_v,
                                sweeps=num_sweeps_in_measurement,
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
                        # Read from JSON params first, fallback to GUI variables
                        set_v = float(params.get("set_v", self.end_set_v.get()))
                        reset_v = float(params.get("reset_v", self.end_reset_v.get()))
                        pulse_ms = float(params.get("pulse_ms", self.end_pulse_ms.get()))
                        cycles = int(params.get("cycles", self.end_cycles.get()))
                        read_v = float(params.get("read_v", self.end_read_v.get()))
                        
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
                        # Read from JSON params first, fallback to GUI variables
                        set_v = float(params.get("set_v", self.ret_set_v.get()))
                        set_ms = float(params.get("set_ms", self.ret_set_ms.get()))
                        read_v = float(params.get("read_v", self.ret_read_v.get()))
                        # Handle times_s array from JSON or single delay from GUI
                        if "times_s" in params and isinstance(params["times_s"], list):
                            times_s = [float(t) for t in params["times_s"]]
                        else:
                            delay_s = float(params.get("delay_s", self.ret_measure_delay.get()))
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

                    # Find the largest existing file number to continue from the most recent
                    from Measurments.single_measurement_runner import find_largest_number_in_folder
                    key_num = find_largest_number_in_folder(save_dir)
                    save_key = 0 if key_num is None else key_num + 1

                    if self.additional_info_var != "":
                        #extra_info = "-" + str(self.additional_info_entry.get())
                        # or
                        extra_info = "-" + self.additional_info_entry.get().strip()
                    else:
                        extra_info = ""

                    name = f"{save_key}-{sweep_type}-{stop_v}v-{step_v}sv-{step_delay}sd-Py-{code_name}{extra_info}"
                    file_path = f"{save_dir}\\{name}.txt"

                    try:
                        np.savetxt(file_path, data, fmt="%0.3E\t%0.3E\t%0.3E", header="Voltage Current Time", comments="")
                        abs_path = os.path.abspath(file_path)
                        print(f"[SAVE] File saved to: {abs_path}")
                        self.log_terminal(f"File saved: {abs_path}")
                    except Exception as e:
                        print(f"[SAVE ERROR] Failed to save file: {e}")

                    # show graphs on main display
                    self.graphs_show(v_arr, c_arr, key, stop_v)
                    
                    # === PER-SWEEP ANALYSIS FOR CUSTOM SEQUENCES ===
                    try:
                        # Build metadata for this sweep
                        sweep_metadata = {}
                        if hasattr(self, 'optical') and self.optical is not None:
                            try:
                                caps = getattr(self.optical, 'capabilities', {})
                                if caps.get('type'):
                                    sweep_metadata['led_type'] = str(caps.get('type', ''))
                            except Exception:
                                pass
                        
                        # Use sweep-specific filename (should match the actual saved file: save_key-based)
                        # Note: 'name' uses save_key (line 7067), so use that for consistency
                        sweep_file_name = name  # Use the actual filename that was saved
                        
                        # Run analysis with conditional logic
                        analysis_result = self._run_analysis_if_enabled(
                            voltage=list(v_arr),
                            current=list(c_arr),
                            timestamps=list(timestamps) if timestamps is not None else None,
                            save_dir=save_dir,
                            file_name=sweep_file_name,
                            metadata=sweep_metadata,
                            is_custom_sequence=True,
                            sweep_number=int(str(save_key)),  # Use save_key instead of key for consistency
                            device_memristive_flag=device_is_memristive
                        )
                        
                        # Update memristive flag after first sweep
                        # Since analysis now runs in background, check for pending results
                        if save_key == 0:  # First sweep (use save_key instead of key)
                            # Wait a bit for analysis to complete (with timeout)
                            max_wait = 10.0  # 10 seconds max
                            wait_start = time.time()
                            while time.time() - wait_start < max_wait:
                                if hasattr(self, '_pending_analysis_results'):
                                    result_key = f"{sweep_file_name}_sweep_{save_key}"
                                    if result_key in self._pending_analysis_results:
                                        result = self._pending_analysis_results[result_key]
                                        device_is_memristive = result.get('is_memristive', False)
                                        analysis_result = result
                                        print(f"[CUSTOM ANALYSIS] First sweep complete: memristive={device_is_memristive}")
                                        break
                                time.sleep(0.1)
                            else:
                                print(f"[CUSTOM ANALYSIS] Timeout waiting for first sweep analysis result")
                                analysis_result = None

                        # === AUTOMATIC PLOTTING FOR ALL SWEEPS ===
                        # Plot IV dashboard for EVERY sweep (memristive or not)
                        # Only include conduction/SCLC plots if device is memristive
                        try:
                            # Determine if memristive from analysis result (if available)
                            is_memristive_for_plot = False
                            if analysis_result and hasattr(analysis_result, 'get'):
                                analysis_data = analysis_result.get('analysis_data') or analysis_result
                                if analysis_data:
                                    classification = analysis_data.get('classification', {})
                                    is_memristive_for_plot = classification.get('memristivity_score', 0) > 60
                            else:
                                # No analysis result - use device flag from first sweep
                                is_memristive_for_plot = device_is_memristive if device_is_memristive is not None else False
                            
                            # ALWAYS plot (dashboard always, conduction/SCLC only if memristive)
                            self._plot_measurement_in_background(
                                voltage=v_arr,
                                current=c_arr,
                                timestamps=timestamps,
                                save_dir=save_dir,
                                device_name=f"{self.final_device_letter}{self.final_device_number}",
                                sweep_number=save_key,  # Use save_key for consistency
                                is_memristive=is_memristive_for_plot,
                                filename=name  # Use actual saved filename (includes extra_info if present)
                            )
                            debug_print(f"[PLOT] Queued plots for sweep {save_key}: {name} (memristive={is_memristive_for_plot})")
                        except Exception as plot_exc:
                            print(f"[PLOT ERROR] Failed to queue background plotting: {plot_exc}")
                        
                        # Collect analysis data (if available)
                        if analysis_result and hasattr(analysis_result, 'get'):
                            try:
                                analysis_data = analysis_result.get('analysis_data') or analysis_result
                                sequence_analysis_results.append({
                                    'sweep_number': save_key,  # Use save_key for consistency
                                    'voltage': stop_v,
                                    'analysis': analysis_data
                                })
                                
                                # Update live display (separate try-except to not block data collection)
                                try:
                                    classification = analysis_data.get('classification', {})
                                    self._update_live_classification_display(
                                        sweep_num=save_key,  # Use save_key for consistency
                                        total_sweeps=total_sweeps_count,
                                        classification_data=classification
                                    )
                                except Exception as display_exc:
                                    print(f"[LIVE DISPLAY ERROR] Failed to update display: {display_exc}")
                                
                                # Store classification for summary
                                try:
                                    sweep_classifications[int(str(key))] = {
                                        'score': classification.get('memristivity_score', 0),
                                        'device_type': classification.get('device_type', 'unknown')
                                    }
                                except Exception as class_exc:
                                    print(f"[CLASSIFICATION ERROR] Failed to store classification: {class_exc}")
                            except Exception as data_exc:
                                print(f"[DATA COLLECTION ERROR] Failed to collect analysis data: {data_exc}")
                    except Exception as exc:
                        # Don't interrupt measurement flow if analysis fails
                        print(f"[CUSTOM ANALYSIS] Failed to run per-sweep analysis: {exc}")

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
                
                # Run IV analysis on combined data from all sweeps if enabled
                try:
                    if hasattr(self, 'v_arr_disp') and hasattr(self, 'c_arr_disp'):
                        v_arr = list(self.v_arr_disp) if self.v_arr_disp else []
                        c_arr = list(self.c_arr_disp) if self.c_arr_disp else []
                        
                        if len(v_arr) > 0 and len(c_arr) > 0:
                            # Get timestamps if available
                            t_arr = None
                            if hasattr(self, 't_arr_disp') and self.t_arr_disp:
                                t_arr = list(self.t_arr_disp)
                            
                            # Build metadata
                            metadata = {}
                            if hasattr(self, 'optical') and self.optical is not None:
                                try:
                                    caps = getattr(self.optical, 'capabilities', {})
                                    if caps.get('type'):
                                        metadata['led_type'] = str(caps.get('type', ''))
                                except Exception:
                                    pass
                            
                            # Use measurement name as filename
                            file_name = f"custom_{selected_measurement}"
                            
                            # Call analysis helper
                            # NOTE: Pass is_custom_sequence=True to suppress automatic plotting
                            # (Individual sweeps already have plots, this is just for combined stats)
                            self._run_analysis_if_enabled(
                                voltage=v_arr,
                                current=c_arr,
                                timestamps=t_arr,
                                save_dir=save_dir,
                                file_name=file_name,
                                metadata=metadata,
                                is_custom_sequence=True,  # Suppress automatic plotting
                                sweep_number=9999,  # Dummy value (will be ignored for combined analysis)
                                device_memristive_flag=True  # Allow analysis to run (combined data)
                            )
                except Exception as exc:
                    # Don't interrupt measurement flow if analysis fails
                    print(f"[ANALYSIS] Failed to run analysis in custom measurement: {exc}")
                
                self.ax_all_iv.clear()
                self.ax_all_logiv.clear()
                self.keithley.enable_output(False)

                end = time.time()
                print("total time for ", selected_measurement, "=", end - start, " - ")

                self.data_saver.create_log_file(save_dir, start_time, selected_measurement)
                
                # === GENERATE SEQUENCE SUMMARY ===
                # Wrap in try-except to ensure measurement flow is never interrupted
                try:
                    if sequence_analysis_results:
                        device_id = f"{self.sample_name_var.get()}_{self.final_device_letter}_{self.final_device_number}"
                        self._generate_sequence_summary(
                            device_id=device_id,
                            sequence_name=selected_measurement,
                            sequence_results=sequence_analysis_results,
                            save_dir=save_dir,
                            total_sweeps=total_sweeps_count
                        )
                except Exception as exc:
                    # Don't interrupt measurement flow if summary generation fails
                    debug_print(f"[SUMMARY ERROR] Failed to generate sequence summary: {exc}")
                    import traceback
                    traceback.print_exc()
                
                # === AUTOMATIC COMPREHENSIVE ANALYSIS AFTER CUSTOM MEASUREMENT ===
                # DISABLED: Auto analysis should only run after the very last sample is measured
                # This will be a later feature - for now, only dashboard/general graphs are plotted
                # (Dashboard graphs are handled by the plotting system automatically)
                pass

                debug_print(self.single_device_flag,device_count)
                
                if self.single_device_flag:
                    debug_print("Measuring one device only")
                    # Stop iterating further devices by exiting the device loop
                    
                    break
                if not self.single_device_flag:
                    # Check if in manual mode - skip automatic advancement
                    if hasattr(self.sample_gui, 'multiplexer_type') and self.sample_gui.multiplexer_type == "Manual":
                        debug_print("Manual mode: Skipping automatic device advancement - user must manually advance")
                        self.log_terminal("Manual mode: Measurement complete. Please manually advance to next device using GUI buttons.")
                    else:
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
            print(f"  Debug: {'ON' if debug else 'OFF'} (value={debug}, type={type(debug).__name__})")
            # Print full command (may be long, but useful for debugging)
            if len(command) > 300:
                print(f"  Command (first 150): {command[:150]}...")
                print(f"  Command (last 150): ...{command[-150:]}")
                # Also show the debug parameter part
                if ",1)" in command or ",0)" in command:
                    debug_pos = command.rfind(",")
                    if debug_pos > 0:
                        print(f"  Debug parameter in command: ...{command[debug_pos-5:debug_pos+5]}...")
            else:
                print(f"  Full command: {command}")
            
            # Calculate wait time based on sweep parameters
            # Time per point ≈ settle_time + (integration_time × 0.01s per PLC)
            # Total time = (4 × num_cycles) × time_per_point × safety_factor
            time_per_point = settle_time + (integration_time * 0.01)  # Rough: 1 PLC ≈ 0.01s
            estimated_time = (4 * num_cycles) * time_per_point
            wait_time = max(2.0, estimated_time * 1.5)  # Minimum 2s, add 50% safety margin
            print(f"  Estimated sweep time: {estimated_time:.2f}s, waiting {wait_time:.2f}s...")
            
            return_value, error = controller._execute_ex_command(command, wait_seconds=wait_time)
            
            if error:
                raise RuntimeError(f"EX command failed: {error}")
            # smu_ivsweep returns 0 on success, negative values on error
            if return_value == 0:
                print(f"[Cyclical IV Sweep] Return value: 0 (success)")
            elif return_value is not None and return_value < 0:
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
            
            # Wait a bit more to ensure EX command is fully complete
            time.sleep(0.3)
            
            # Exit UL mode before GP commands (GP commands must be sent in normal mode)
            controller._exit_ul_mode()
            time.sleep(0.5)  # Wait longer for mode transition to complete (GP commands need normal mode)
            
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
            # Cleanup: exit UL mode (if still active) and disconnect
            try:
                if controller._ul_mode_active:
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
        self._reset_plots_for_new_run(self)
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
            self._update_conditional_testing_button_state()
            if hasattr(self.keithley, 'beep'):
                self.keithley.beep(4000, 0.2)
                time.sleep(0.2)
                self.keithley.beep(5000, 0.5)
        except RuntimeError as exc:
            self.connected = False
            self._update_conditional_testing_button_state()
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

    def open_oscilloscope_pulse(self) -> None:
        """Open the Oscilloscope Pulse Capture GUI with current context."""
        try:
            # 1. Prepare Adapter
            adapter = None
            if self.keithley:
                 adapter = SMUAdapter(self.keithley)
            
            # 2. Prepare Context
            context = {
                'device_label': self.current_device,
                'sample_name': self.sample_gui.sample_name if hasattr(self.sample_gui, 'sample_name') else "Unknown",
                'save_directory': self.default_save_root,
                'smu_ports': [self.keithley_address], # Currently connected
                'known_systems': self.systems if hasattr(self, 'systems') and isinstance(self.systems, list) else (list(self.systems.keys()) if hasattr(self, 'systems') else []),
                'system': self.controller_type 
            }
            
            # 3. Launch
            OscilloscopePulseGUI(self.master, smu_instance=adapter, context=context)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open Oscilloscope Pulse GUI:\n{e}")

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
    
    def _get_sample_save_directory(self, sample_name: str) -> str:
        """
        Get sample-level save directory (for tracking/research that should be at sample level).
        
        Args:
            sample_name: Sample name
        
        Returns:
            String path to sample-level directory (e.g., base/test/)
        """
        base_path = Path(self._get_base_save_path())
        sample_path = base_path / sample_name
        sample_path.mkdir(parents=True, exist_ok=True)
        return str(sample_path)
    
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
    
    def _update_overlay_from_current_state(self) -> None:
        """Helper method to update the orange overlay box with current state."""
        if not hasattr(self, 'plot_panels') or not hasattr(self.plot_panels, 'update_overlay'):
            return
        
        # Get sample name - prioritize in this order:
        # 1. sample_name_var (user-entered or set from device)
        # 2. current_device_name from sample_gui (saved device)
        # 3. sample_type_var from sample_gui (selected sample type, even if no saved device)
        sample_name = "—"
        
        # First try sample_name_var
        if hasattr(self, 'sample_name_var'):
            try:
                name = self.sample_name_var.get().strip()
                if name:
                    sample_name = name
            except Exception:
                pass
        
        # If still empty, try current_device_name (saved device)
        if sample_name == "—" or not sample_name:
            if hasattr(self.sample_gui, 'current_device_name') and self.sample_gui.current_device_name:
                sample_name = self.sample_gui.current_device_name
        
        # If still empty, fall back to sample_type_var (selected sample type)
        # This ensures it updates even when no saved device is selected
        if sample_name == "—" or not sample_name:
            if hasattr(self.sample_gui, 'sample_type_var'):
                try:
                    sample_type = self.sample_gui.sample_type_var.get()
                    if sample_type:
                        sample_name = sample_type
                except Exception:
                    pass
        
        # Get device label
        device_label = "—"
        try:
            # Try to get from device_section_and_number
            if hasattr(self, 'device_section_and_number') and self.device_section_and_number:
                device_label = self.device_section_and_number
            # Fallback: get from sample_gui's current device selection
            elif hasattr(self.sample_gui, 'device_var'):
                try:
                    device = self.sample_gui.device_var.get()
                    if device:
                        device_label = device
                except Exception:
                    pass
            # Another fallback: use current_index to get device label
            if device_label == "—" and hasattr(self, 'current_index') and hasattr(self.sample_gui, 'device_list'):
                if 0 <= self.current_index < len(self.sample_gui.device_list):
                    device_key = self.sample_gui.device_list[self.current_index]
                    if hasattr(self.sample_gui, 'get_device_label'):
                        device_label = self.sample_gui.get_device_label(device_key)
                    else:
                        device_label = str(device_key)
        except Exception:
            pass
        
        # Get current voltage
        current_voltage = getattr(self, 'current_voltage', '0V')
        if current_voltage == '0V' and hasattr(self, 'v_arr_disp') and self.v_arr_disp:
            try:
                v_now = float(self.v_arr_disp[-1])
                current_voltage = f"{v_now:.3f}V"
            except Exception:
                pass
        
        # Get current loop
        current_loop = getattr(self, 'current_loop', '#1')
        if current_loop == '#1':
            loop_val = None
            if getattr(self, 'sweep_num', None) is not None:
                loop_val = self.sweep_num
            elif getattr(self, 'measurment_number', None) is not None:
                loop_val = self.measurment_number
            if loop_val is not None:
                current_loop = f"#{loop_val}"
        
        # Update the overlay
        self.plot_panels.update_overlay(
            sample_name=sample_name,
            device=device_label,
            voltage=current_voltage,
            loop=current_loop
        )
    
    def on_sample_gui_change(self, change_type: str, **kwargs) -> None:
        """Handle notifications from SampleGUI about changes.
        
        Args:
            change_type: Type of change ('sample_type', 'section', 'device_name', 'device_selection')
            **kwargs: Additional data about the change
        """
        try:
            if change_type == 'device_name':
                device_name = kwargs.get('device_name')
                # Update sample_name_var if it exists
                if hasattr(self, 'sample_name_var'):
                    if device_name:
                        self.sample_name_var.set(device_name)
                    else:
                        # If device name is cleared, try to get sample type as fallback
                        if hasattr(self.sample_gui, 'sample_type_var'):
                            try:
                                sample_type = self.sample_gui.sample_type_var.get()
                                if sample_type:
                                    self.sample_name_var.set(sample_type)
                            except Exception:
                                pass
                
                # Update overlay
                self._update_overlay_from_current_state()
            
            elif change_type == 'sample_type':
                sample_type = kwargs.get('sample_type')
                # Update sample_name_var if device_name is not set
                if hasattr(self, 'sample_name_var'):
                    current_name = self.sample_name_var.get().strip()
                    # Only update if current name is empty or matches old sample type
                    if not current_name or (hasattr(self.sample_gui, 'sample_type_var') and 
                                           current_name == getattr(self.sample_gui, 'sample_type_var', None)):
                        if sample_type:
                            self.sample_name_var.set(sample_type)
                
                # Update overlay
                self._update_overlay_from_current_state()
            
            elif change_type == 'section':
                section = kwargs.get('section')
                device = kwargs.get('device')
                # Update current_index if device changed
                if device and hasattr(self.sample_gui, 'device_list'):
                    try:
                        device_key = self.sample_gui.get_device_key_from_label(device)
                        if device_key and device_key in self.sample_gui.device_list:
                            new_index = self.sample_gui.device_list.index(device_key)
                            if new_index != self.current_index:
                                self.current_index = new_index
                                # Update device-related attributes
                                if hasattr(self, 'device_list') and self.current_index < len(self.device_list):
                                    self.current_device = self.device_list[self.current_index]
                                    self.device_section_and_number = self.convert_to_name(self.current_index)
                                    self.display_index_section_number = f"{self.device_section_and_number} ({self.current_device})"
                    except Exception:
                        pass
                
                # Update overlay
                self._update_overlay_from_current_state()
            
            elif change_type == 'device_selection':
                selected_devices = kwargs.get('selected_devices', [])
                selected_indices = kwargs.get('selected_indices', [])
                # Update device_list if provided
                if selected_devices:
                    self.device_list = selected_devices.copy()
                    # Update current_index if it's out of bounds
                    if self.current_index >= len(self.device_list):
                        self.current_index = 0 if self.device_list else 0
                    # Update current_device and device_section_and_number
                    if self.device_list and self.current_index < len(self.device_list):
                        self.current_device = self.device_list[self.current_index]
                        self.device_section_and_number = self.convert_to_name(self.current_index)
                        self.display_index_section_number = f"{self.device_section_and_number} ({self.current_device})"
                
                # Update overlay
                self._update_overlay_from_current_state()
        except Exception as e:
            print(f"Error handling sample_gui change notification ({change_type}): {e}")
    
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
    def _get_sample_save_directory(self, sample_name: str) -> str:
        """
        Get sample-level save directory (for tracking/research that should be at sample level).
        
        Args:
            sample_name: Sample name
        
        Returns:
            String path to sample-level directory (e.g., base/test/)
        """
        base_path = Path(self._get_base_save_path())
        sample_path = base_path / sample_name
        sample_path.mkdir(parents=True, exist_ok=True)
        return str(sample_path)
    
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
    
    def _update_overlay_from_current_state(self) -> None:
        """Helper method to update the orange overlay box with current state."""
        if not hasattr(self, 'plot_panels') or not hasattr(self.plot_panels, 'update_overlay'):
            return
        
        # Get sample name - prioritize in this order:
        # 1. sample_name_var (user-entered or set from device)
        # 2. current_device_name from sample_gui (saved device)
        # 3. sample_type_var from sample_gui (selected sample type, even if no saved device)
        sample_name = "—"
        
        # First try sample_name_var
        if hasattr(self, 'sample_name_var'):
            try:
                name = self.sample_name_var.get().strip()
                if name:
                    sample_name = name
            except Exception:
                pass
        
        # If still empty, try current_device_name (saved device)
        if sample_name == "—" or not sample_name:
            if hasattr(self.sample_gui, 'current_device_name') and self.sample_gui.current_device_name:
                sample_name = self.sample_gui.current_device_name
        
        # If still empty, fall back to sample_type_var (selected sample type)
        # This ensures it updates even when no saved device is selected
        if sample_name == "—" or not sample_name:
            if hasattr(self.sample_gui, 'sample_type_var'):
                try:
                    sample_type = self.sample_gui.sample_type_var.get()
                    if sample_type:
                        sample_name = sample_type
                except Exception:
                    pass
        
        # Get device label
        device_label = "—"
        try:
            # Try to get from device_section_and_number
            if hasattr(self, 'device_section_and_number') and self.device_section_and_number:
                device_label = self.device_section_and_number
            # Fallback: get from sample_gui's current device selection
            elif hasattr(self.sample_gui, 'device_var'):
                try:
                    device = self.sample_gui.device_var.get()
                    if device:
                        device_label = device
                except Exception:
                    pass
            # Another fallback: use current_index to get device label
            if device_label == "—" and hasattr(self, 'current_index') and hasattr(self.sample_gui, 'device_list'):
                if 0 <= self.current_index < len(self.sample_gui.device_list):
                    device_key = self.sample_gui.device_list[self.current_index]
                    if hasattr(self.sample_gui, 'get_device_label'):
                        device_label = self.sample_gui.get_device_label(device_key)
                    else:
                        device_label = str(device_key)
        except Exception:
            pass
        
        # Get current voltage
        current_voltage = getattr(self, 'current_voltage', '0V')
        if current_voltage == '0V' and hasattr(self, 'v_arr_disp') and self.v_arr_disp:
            try:
                v_now = float(self.v_arr_disp[-1])
                current_voltage = f"{v_now:.3f}V"
            except Exception:
                pass
        
        # Get current loop
        current_loop = getattr(self, 'current_loop', '#1')
        if current_loop == '#1':
            loop_val = None
            if getattr(self, 'sweep_num', None) is not None:
                loop_val = self.sweep_num
            elif getattr(self, 'measurment_number', None) is not None:
                loop_val = self.measurment_number
            if loop_val is not None:
                current_loop = f"#{loop_val}"
        
        # Update the overlay
        self.plot_panels.update_overlay(
            sample_name=sample_name,
            device=device_label,
            voltage=current_voltage,
            loop=current_loop
        )
    
    def on_sample_gui_change(self, change_type: str, **kwargs) -> None:
        """Handle notifications from SampleGUI about changes.
        
        Args:
            change_type: Type of change ('sample_type', 'section', 'device_name', 'device_selection')
            **kwargs: Additional data about the change
        """
        try:
            if change_type == 'device_name':
                device_name = kwargs.get('device_name')
                # Update sample_name_var if it exists
                if hasattr(self, 'sample_name_var'):
                    if device_name:
                        self.sample_name_var.set(device_name)
                    else:
                        # If device name is cleared, try to get sample type as fallback
                        if hasattr(self.sample_gui, 'sample_type_var'):
                            try:
                                sample_type = self.sample_gui.sample_type_var.get()
                                if sample_type:
                                    self.sample_name_var.set(sample_type)
                            except Exception:
                                pass
                
                # Update overlay
                self._update_overlay_from_current_state()
            
            elif change_type == 'sample_type':
                sample_type = kwargs.get('sample_type')
                # Update sample_name_var if device_name is not set
                if hasattr(self, 'sample_name_var'):
                    current_name = self.sample_name_var.get().strip()
                    # Only update if current name is empty or matches old sample type
                    if not current_name or (hasattr(self.sample_gui, 'sample_type_var') and 
                                           current_name == getattr(self.sample_gui, 'sample_type_var', None)):
                        if sample_type:
                            self.sample_name_var.set(sample_type)
                
                # Update overlay
                self._update_overlay_from_current_state()
            
            elif change_type == 'section':
                section = kwargs.get('section')
                device = kwargs.get('device')
                # Update current_index if device changed
                if device and hasattr(self.sample_gui, 'device_list'):
                    try:
                        device_key = self.sample_gui.get_device_key_from_label(device)
                        if device_key and device_key in self.sample_gui.device_list:
                            new_index = self.sample_gui.device_list.index(device_key)
                            if new_index != self.current_index:
                                self.current_index = new_index
                                # Update device-related attributes
                                if hasattr(self, 'device_list') and self.current_index < len(self.device_list):
                                    self.current_device = self.device_list[self.current_index]
                                    self.device_section_and_number = self.convert_to_name(self.current_index)
                                    self.display_index_section_number = f"{self.device_section_and_number} ({self.current_device})"
                    except Exception:
                        pass
                
                # Update overlay
                self._update_overlay_from_current_state()
            
            elif change_type == 'device_selection':
                selected_devices = kwargs.get('selected_devices', [])
                selected_indices = kwargs.get('selected_indices', [])
                # Update device_list if provided
                if selected_devices:
                    self.device_list = selected_devices.copy()
                    # Update current_index if it's out of bounds
                    if self.current_index >= len(self.device_list):
                        self.current_index = 0 if self.device_list else 0
                    # Update current_device and device_section_and_number
                    if self.device_list and self.current_index < len(self.device_list):
                        self.current_device = self.device_list[self.current_index]
                        self.device_section_and_number = self.convert_to_name(self.current_index)
                        self.display_index_section_number = f"{self.device_section_and_number} ({self.current_device})"
                
                # Update overlay
                self._update_overlay_from_current_state()
        except Exception as e:
            print(f"Error handling sample_gui change notification ({change_type}): {e}")
    
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
