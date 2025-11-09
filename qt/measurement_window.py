"""PyQt6 implementation of the main measurement GUI.

This module provides `QtMeasurementGUI`, a feature-parity successor to the
legacy Tkinter `MeasurementGUI`. It focuses on replicating the existing layout
and behaviour using Qt widgets while reusing the established measurement
services, runners and data persistence utilities.

Key design goals:
    * Preserve the orchestration logic that coordinates instrument connections,
      measurement runners and data saving.
    * Keep the left/middle/right column layout that users are familiar with.
    * Provide Qt-friendly adapters for status updates, messaging and plotting.
    * Allow side-by-side execution with the Tk variant during migration.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from itertools import cycle
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple
import statistics

from PyQt6 import QtCore, QtGui, QtWidgets

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib import rcParams

from Equipment.SMU_AND_PMU.Keithley2400 import Keithley2400Controller  # noqa: F401
from Equipment.iv_controller_manager import IVControllerManager
from Equipment.PowerSupplies.Keithley2220 import Keithley2220_Powersupply
from Equipment.TempControllers.OxfordITC4 import OxfordITC4

from Measurments.measurement_services_smu import MeasurementService, VoltageRangeMode
from Measurments.data_saver import MeasurementDataSaver, SummaryPlotData
from Measurments.optical_controller import OpticalController
from Equipment.optical_excitation import create_optical_from_system_config
from Measurments.sequential_runner import SequentialMeasurementRunner
from Measurments.sequential_persistence import SequentialDataSaver


class VarWrapper:
    """Minimal stand-in for Tkinter Variable classes."""

    def __init__(self, value: Any) -> None:
        self._value = value

    def get(self) -> Any:
        return self._value

    def set(self, value: Any) -> None:
        self._value = value


class IVSweepWorker(QtCore.QObject):
    """Background worker that runs a MeasurementService IV sweep."""

    point = QtCore.pyqtSignal(float, float, float)
    message = QtCore.pyqtSignal(str)
    finished = QtCore.pyqtSignal(list, list, list, str)

    def __init__(
        self,
        service: MeasurementService,
        keithley: Any,
        smu_type: str,
        voltage_range: List[float],
        icc: float,
        sweeps: int,
        step_delay: float,
    ) -> None:
        super().__init__()
        self._service = service
        self._keithley = keithley
        self._smu_type = smu_type
        self._voltage_range = voltage_range
        self._icc = icc
        self._sweeps = sweeps
        self._step_delay = step_delay
        self._stop_requested = False

    @QtCore.pyqtSlot()
    def run(self) -> None:
        def _on_point(v: float, c: float, t: float) -> None:
            self.point.emit(v, c, t)

        try:
            v_arr, c_arr, t_arr = self._service.run_iv_sweep(
                keithley=self._keithley,
                icc=self._icc,
                sweeps=self._sweeps,
                step_delay=self._step_delay,
                voltage_range=self._voltage_range,
                smu_type=self._smu_type,
                should_stop=self._should_stop,
                on_point=_on_point,
            )
            self.finished.emit(v_arr, c_arr, t_arr, "")
        except Exception as exc:
            self.finished.emit([], [], [], str(exc))

    def request_stop(self) -> None:
        self._stop_requested = True

    def _should_stop(self) -> bool:
        return self._stop_requested


class GenericMeasurementWorker(QtCore.QObject):
    """Background worker that executes an arbitrary measurement callable."""

    finished = QtCore.pyqtSignal(list, list, list, str)

    def __init__(
        self,
        task: Callable[[Callable[[], bool]], Tuple[Iterable[float], Iterable[float], Iterable[float]]],
    ) -> None:
        super().__init__()
        self._task = task
        self._stop_requested = False

    @QtCore.pyqtSlot()
    def run(self) -> None:
        try:
            voltage, current, timestamps = self._task(self._should_stop)
            self.finished.emit(list(voltage), list(current), list(timestamps), "")
        except Exception as exc:
            self.finished.emit([], [], [], str(exc))

    def request_stop(self) -> None:
        self._stop_requested = True

    def _should_stop(self) -> bool:
        return self._stop_requested


class ManualEnduranceWorker(QtCore.QObject):
    progress = QtCore.pyqtSignal(list)
    error = QtCore.pyqtSignal(str)
    finished = QtCore.pyqtSignal(list)
    status = QtCore.pyqtSignal(str)

    def __init__(
        self,
        keithley: Any,
        set_voltage: float,
        reset_voltage: float,
        read_voltage: float,
        pulse_width_s: float,
        cycles: int,
        should_stop: Callable[[], bool],
    ) -> None:
        super().__init__()
        self._keithley = keithley
        self._set_voltage = set_voltage
        self._reset_voltage = reset_voltage
        self._read_voltage = read_voltage
        self._pulse_width_s = max(0.0001, pulse_width_s)
        self._cycles = max(1, cycles)
        self._ratios: List[float] = []
        self._should_stop_cb = should_stop

    @QtCore.pyqtSlot()
    def run(self) -> None:
        try:
            self.status.emit("Manual endurance: enabling SMU output.")
            if hasattr(self._keithley, "enable_output"):
                self._keithley.enable_output(True)
            for idx in range(self._cycles):
                if self._should_stop():
                    break
                self._set_voltage_and_wait(self._set_voltage, self._pulse_width_s)
                i_on = self._measure_current()
                self._set_voltage_and_wait(self._read_voltage, 0.01)
                self._set_voltage_and_wait(self._reset_voltage, self._pulse_width_s)
                i_off = self._measure_current()
                ratio = (abs(i_on) + 1e-12) / (abs(i_off) + 1e-12)
                self._ratios.append(ratio)
                self.progress.emit(self._ratios.copy())
                self.status.emit(f"Manual endurance cycle {idx + 1}/{self._cycles}")
                if self._should_stop():
                    break
            self.finished.emit(self._ratios.copy())
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            try:
                if hasattr(self._keithley, "enable_output"):
                    self._keithley.enable_output(False)
            except Exception:
                pass

    def _set_voltage_and_wait(self, voltage: float, delay_s: float) -> None:
        try:
            self._keithley.set_voltage(voltage)
        except Exception:
            pass
        time.sleep(max(0.0, delay_s))

    def _measure_current(self) -> float:
        try:
            current = self._keithley.measure_current()
            if isinstance(current, (list, tuple)):
                current = current[-1]
            return float(current)
        except Exception:
            return 0.0

    def _should_stop(self) -> bool:
        try:
            return self._should_stop_cb()
        except Exception:
            return False


class ManualRetentionWorker(QtCore.QObject):
    progress = QtCore.pyqtSignal(list, list)
    error = QtCore.pyqtSignal(str)
    finished = QtCore.pyqtSignal(list, list)
    status = QtCore.pyqtSignal(str)

    def __init__(
        self,
        keithley: Any,
        set_voltage: float,
        set_time_s: float,
        read_voltage: float,
        interval_s: float,
        points: int,
        should_stop: Callable[[], bool],
    ) -> None:
        super().__init__()
        self._keithley = keithley
        self._set_voltage = set_voltage
        self._set_time_s = max(0.0001, set_time_s)
        self._read_voltage = read_voltage
        self._interval_s = max(0.0001, interval_s)
        self._points = max(1, points)
        self._should_stop_cb = should_stop

    @QtCore.pyqtSlot()
    def run(self) -> None:
        times: List[float] = []
        currents: List[float] = []
        try:
            if hasattr(self._keithley, "enable_output"):
                self._keithley.enable_output(True)
            self._set_voltage_and_wait(self._set_voltage, self._set_time_s)
            start = time.time()
            for idx in range(self._points):
                target_time = (idx + 1) * self._interval_s
                while True:
                    if self._should_stop():
                        break
                    elapsed = time.time() - start
                    if elapsed >= target_time:
                        break
                    time.sleep(0.01)
                if self._should_stop():
                    break
                self._set_voltage_and_wait(self._read_voltage, 0.01)
                current = self._measure_current()
                times.append(time.time() - start)
                currents.append(abs(current))
                self.progress.emit(times.copy(), currents.copy())
                self.status.emit(f"Manual retention sample {idx + 1}/{self._points}")
                if self._should_stop():
                    break
            self.finished.emit(times.copy(), currents.copy())
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            try:
                if hasattr(self._keithley, "enable_output"):
                    self._keithley.enable_output(False)
            except Exception:
                pass

    def _set_voltage_and_wait(self, voltage: float, delay_s: float) -> None:
        try:
            self._keithley.set_voltage(voltage)
        except Exception:
            pass
        time.sleep(max(0.0, delay_s))

    def _measure_current(self) -> float:
        try:
            current = self._keithley.measure_current()
            if isinstance(current, (list, tuple)):
                current = current[-1]
            return float(current)
        except Exception:
            return 0.0

    def _should_stop(self) -> bool:
        try:
            return self._should_stop_cb()
        except Exception:
            return False



@dataclass
class WidgetGroup:
    """Convenience container for frequently accessed widget groups."""

    connections: Optional[QtWidgets.QGroupBox] = None
    status: Optional[QtWidgets.QGroupBox] = None
    controls: Optional[QtWidgets.QGroupBox] = None
    sequential: Optional[QtWidgets.QGroupBox] = None
    plots: Dict[str, QtWidgets.QWidget] = None

    def __post_init__(self) -> None:  # pragma: no cover - trivial
        if self.plots is None:
            self.plots = {}


class QtMeasurementGUI(QtWidgets.QMainWindow):
    """Qt-based control panel for running and monitoring measurements."""

    def __init__(
        self,
        sample_type: str,
        section: str,
        device_list: list[str],
        sample_gui: Any,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self.sample_type = sample_type
        self.section = section
        self.device_list = device_list
        self.sample_gui = sample_gui

        self.measurement_service = MeasurementService()
        self.optical_controller: Optional[OpticalController] = None
        self.data_saver = MeasurementDataSaver()
        self.sequential_data_saver = SequentialDataSaver()
        self._measurement_active = False
        self._current_thread: Optional[QtCore.QThread] = None
        self._current_worker: Optional[QtCore.QObject] = None
        self._active_measurement_label: Optional[str] = None
        self._pre_measurement_led_state = False
        self._led_restore_required = False
        self._active_result_metadata: Optional[Dict[str, Any]] = None
        self._pulsed_modes = {
            "SMU_AND_PMU Pulsed IV <1.5v",
            "SMU_AND_PMU Pulsed IV >1.5v",
            "SMU_AND_PMU Fast Pulses",
            "SMU_AND_PMU Fast Hold",
        }
        self._advanced_modes = {
            "ISPP",
            "Pulse Width Sweep",
            "Threshold Search",
            "Transient Decay",
        }
        self._point_counter = 0
        self._icc_default = 1e-3
        self._step_delay_default = 0.05
        self._pending_voltage_range: List[float] = []
        self._plot_voltage: List[float] = []
        self._plot_current: List[float] = []
        self._plot_time: List[float] = []
        self._plot_line = None
        self._plot_line_log = None
        self._plot_vi_line = None
        self._plot_loglog_line = None
        self._plot_current_time_line = None
        self._plot_resistance_time_line = None
        self._all_sweeps_history: List[Dict[str, List[float]]] = []
        self._max_history_traces = 12
        self.iv_canvas: Optional[FigureCanvasQTAgg] = None
        self.log_canvas: Optional[FigureCanvasQTAgg] = None
        self.vi_canvas: Optional[FigureCanvasQTAgg] = None
        self.loglog_canvas: Optional[FigureCanvasQTAgg] = None
        self.current_time_canvas: Optional[FigureCanvasQTAgg] = None
        self.resistance_time_canvas: Optional[FigureCanvasQTAgg] = None
        self.iv_ax = None
        self.log_ax = None
        self.vi_ax = None
        self.loglog_ax = None
        self.current_time_ax = None
        self.resistance_time_ax = None
        self._motor_process: Optional[QtCore.QProcess] = None
        self.sequential_runner: Optional[SequentialMeasurementRunner] = None
        # Sequential/shared state mirrors Tk variables for compatibility
        self.use_custom_save_var = VarWrapper(False)
        self.custom_save_location: Optional[Path] = None
        self.additional_info_var = VarWrapper("")
        self._saved_custom_path: Optional[str] = None
        self._saved_use_custom: bool = False
        self.stop_measurement_flag = False
        self.single_device_flag = True
        self.sample_name_var = VarWrapper(getattr(sample_gui, "sample_name", "Qt_Sample"))
        self.current_device = self.device_list[0] if self.device_list else ""
        self.Sequential_measurement_var = VarWrapper("Iv Sweep")
        self.sequential_number_of_sweeps = VarWrapper(100)
        self.sq_voltage = VarWrapper(0.1)
        self.sq_time_delay = VarWrapper(10.0)
        self.measurement_duration_var = VarWrapper(5.0)
        self.record_temp_var = VarWrapper(True)
        self.led_enabled = False
        self.led_power_var = VarWrapper(1.0)
        self.led_sequence_var = VarWrapper("")
        self.source_mode_var = VarWrapper("voltage")
        self.dc_sweep_mode_var = VarWrapper(VoltageRangeMode.FIXED_STEP)
        self.dc_sweep_type_var = VarWrapper("FS")
        self.dc_sweep_rate_var = VarWrapper(1.0)
        self.dc_total_time_var = VarWrapper(5.0)
        self.dc_num_steps_var = VarWrapper(0)
        self.dc_neg_stop_var = VarWrapper(None)
        self.v_arr_disp: List[float] = []
        self.c_arr_disp: List[float] = []
        self.t_arr_disp: List[float] = []
        self.endurance_ratios: List[float] = []
        self.retention_times: List[float] = []
        self.retention_currents: List[float] = []
        self.manual_endurance_thread: Optional[QtCore.QThread] = None
        self.manual_endurance_worker: Optional[ManualEnduranceWorker] = None
        self.manual_retention_thread: Optional[QtCore.QThread] = None
        self.manual_retention_worker: Optional[ManualRetentionWorker] = None
        self.manual_stop_requested = False
        self.measurement_data: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self.last_measurement_config: Optional[Dict[str, Any]] = None

        # Instrument placeholders / defaults
        self.keithley: Optional[IVControllerManager] = None
        self.psu: Optional[Keithley2220_Powersupply] = None
        self.itc: Optional[OxfordITC4] = None
        self.connected = False
        self.psu_connected = False
        self.itc_connected = False
        self.psu_visa_address = "USB0::0x05E6::0x2220::9210734::INSTR"
        self.temp_controller_address = "ASRL12::INSTR"
        self.keithley_address = "GPIB0::24::INSTR"
        self.smu_type = "Keithley 2401"
        self.temp_controller_type: Optional[str] = None

        self.final_device_letter, self.final_device_number = self._split_device_label(self.current_device)
        self.keithley_address_var = VarWrapper(self.keithley_address)
        self._external_processes: Dict[str, QtCore.QProcess] = {}
        self._load_save_location_config()

        # System presets (JSON-backed)
        self.system_configs: Dict[str, Dict[str, Any]] = self._load_system_configs()
        self._system_names: List[str] = list(self.system_configs.keys())
        self._default_system_name: Optional[str] = self._choose_default_system_name()
        self._current_system_name: Optional[str] = None

        # Messaging/custom sweep data
        self.messaging_data: Dict[str, Dict[str, str]] = {}
        self.names: list[str] = []
        self.custom_sweeps: Dict[str, Dict[str, Any]] = {}
        self.code_names: Dict[str, Optional[str]] = {}

        self._load_messaging_data()
        self._load_custom_sweeps("Json_Files/Custom_Sweeps.json")

        self.widgets = WidgetGroup()
        self._build_device_cache()
        self._setup_window()
        self._create_layout()

    # ------------------------------------------------------------------
    # Window scaffold
    # ------------------------------------------------------------------
    def _setup_window(self) -> None:
        self.setWindowTitle("Measurement Setup (Qt)")
        self.resize(1800, 1200)
        self._status_bar = self.statusBar()
        self._status_bar.showMessage("Ready")

    def _create_layout(self) -> None:
        central = QtWidgets.QWidget(self)
        outer_layout = QtWidgets.QVBoxLayout(central)
        outer_layout.setContentsMargins(6, 6, 6, 6)
        outer_layout.setSpacing(6)

        header = QtWidgets.QLabel(
            f"{self.sample_type} – Section {self.section} • {len(self.device_list)} devices"
        )
        header_font = QtGui.QFont()
        header_font.setPointSize(12)
        header_font.setBold(True)
        header.setFont(header_font)
        header.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        outer_layout.addWidget(header)

        main_layout = QtWidgets.QHBoxLayout()
        main_layout.setSpacing(10)

        # Left column (connections/status/temperature)
        left_widget = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_widget)
        left_layout.setSpacing(8)
        left_layout.addWidget(self._create_connection_panel())
        left_layout.addWidget(self._create_status_panel())
        left_layout.addWidget(self._create_temperature_panel())
        left_layout.addWidget(self._create_messaging_panel())
        left_layout.addWidget(self._create_optical_panel())
        left_layout.addStretch(1)

        # Middle column (sweep parameters, custom configs, sequential controls)
        middle_widget = QtWidgets.QWidget()
        middle_layout = QtWidgets.QVBoxLayout(middle_widget)
        middle_layout.setSpacing(8)
        middle_layout.addWidget(self._create_mode_panel())
        middle_layout.addWidget(self._create_sweep_panel())
        middle_layout.addWidget(self._create_custom_panel())
        middle_layout.addWidget(self._create_sequential_panel())
        middle_layout.addWidget(self._create_automation_panel())
        middle_layout.addWidget(self._create_manual_tests_panel())
        middle_layout.addStretch(1)

        # Right column (plots)
        right_widget = self._create_plot_panel()

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(middle_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 2)

        main_layout.addWidget(splitter)
        outer_layout.addLayout(main_layout)

        self.setCentralWidget(central)
        self._status_bar.showMessage("Ready – Qt migration prototype")
        if self.device_list:
            self.set_current_device(self.device_list[0])

    # ------------------------------------------------------------------
    # Panel builders
    # ------------------------------------------------------------------
    def _create_group(self, title: str) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox(title)
        box_layout = QtWidgets.QGridLayout(box)
        box_layout.setContentsMargins(10, 8, 10, 8)
        box_layout.setHorizontalSpacing(6)
        box_layout.setVerticalSpacing(4)
        return box

    def _create_connection_panel(self) -> QtWidgets.QGroupBox:
        group = self._create_group("Instrument Connections")
        self.widgets.connections = group

        row = 0
        group.layout().addWidget(QtWidgets.QLabel("System Preset:"), row, 0)
        self.system_combo = QtWidgets.QComboBox()
        if self._system_names:
            self.system_combo.addItems(self._system_names)
            default_name = self._default_system_name or self._system_names[0]
            index = self.system_combo.findText(default_name, QtCore.Qt.MatchFlag.MatchExactly)
            if index >= 0:
                self.system_combo.setCurrentIndex(index)
        else:
            self.system_combo.addItem("No systems available")
            self.system_combo.setEnabled(False)
        self.system_combo.currentTextChanged.connect(self._on_system_combo_changed)
        group.layout().addWidget(self.system_combo, row, 1)

        row += 1
        group.layout().addWidget(QtWidgets.QLabel("SMU Type:"), row, 0)
        self.smu_type_combo = QtWidgets.QComboBox()
        self.smu_type_combo.addItems(
            [
                "Keithley 2401",
                "Keithley 2400",
                "Keithley 4200A_smu",
                "HP4140B",
            ]
        )
        self.smu_type_combo.setCurrentText(self.smu_type)
        self.smu_type_combo.currentTextChanged.connect(self._update_smu_type)
        group.layout().addWidget(self.smu_type_combo, row, 1)

        row += 1
        group.layout().addWidget(QtWidgets.QLabel("SMU Address:"), row, 0)
        self.keithley_address_edit = QtWidgets.QLineEdit(self.keithley_address)
        group.layout().addWidget(self.keithley_address_edit, row, 1)

        row += 1
        connect_btn = QtWidgets.QPushButton("Connect SMU")
        connect_btn.clicked.connect(self._handle_connect_smu)
        group.layout().addWidget(connect_btn, row, 0, 1, 2)

        row += 1
        group.layout().addWidget(QtWidgets.QLabel("PSU Address:"), row, 0)
        self.psu_address_edit = QtWidgets.QLineEdit(self.psu_visa_address)
        group.layout().addWidget(self.psu_address_edit, row, 1)

        row += 1
        psu_btn = QtWidgets.QPushButton("Connect PSU")
        psu_btn.clicked.connect(self._handle_connect_psu)
        group.layout().addWidget(psu_btn, row, 0, 1, 2)

        row += 1
        group.layout().addWidget(QtWidgets.QLabel("Temp Controller:"), row, 0)
        self.temp_address_edit = QtWidgets.QLineEdit(self.temp_controller_address)
        group.layout().addWidget(self.temp_address_edit, row, 1)

        row += 1
        temp_btn = QtWidgets.QPushButton("Connect Temp Controller")
        temp_btn.clicked.connect(self._handle_connect_temp)
        group.layout().addWidget(temp_btn, row, 0, 1, 2)

        row += 1
        self.connection_status = QtWidgets.QLabel("Status: Disconnected")
        group.layout().addWidget(self.connection_status, row, 0, 1, 2)

        if self._system_names:
            QtCore.QTimer.singleShot(
                0,
                lambda: self._apply_system_config(
                    self.system_combo.currentText(), announce=False
                ),
            )

        return group

    def _create_status_panel(self) -> QtWidgets.QGroupBox:
        group = self._create_group("Status & Logs")
        self.widgets.status = group

        self.status_log = QtWidgets.QPlainTextEdit(group)
        self.status_log.setReadOnly(True)
        self.status_log.setMaximumBlockCount(2000)
        group.layout().addWidget(self.status_log, 0, 0, 1, 2)

        clear_btn = QtWidgets.QPushButton("Clear Log")
        clear_btn.clicked.connect(self.status_log.clear)
        group.layout().addWidget(clear_btn, 1, 1, alignment=QtCore.Qt.AlignmentFlag.AlignRight)

        return group

    def _create_temperature_panel(self) -> QtWidgets.QGroupBox:
        group = self._create_group("Temperature Control")

        self.temp_enable = QtWidgets.QCheckBox("Enable Temperature Control")
        self.temp_enable.stateChanged.connect(self._handle_temp_toggle)
        group.layout().addWidget(self.temp_enable, 0, 0, 1, 2)

        group.layout().addWidget(QtWidgets.QLabel("Setpoint (°C):"), 1, 0)
        self.temp_spin = QtWidgets.QDoubleSpinBox()
        self.temp_spin.setRange(-200.0, 500.0)
        self.temp_spin.setDecimals(2)
        self.temp_spin.setValue(25.0)
        group.layout().addWidget(self.temp_spin, 1, 1)

        apply_btn = QtWidgets.QPushButton("Apply")
        apply_btn.clicked.connect(self._handle_temp_apply)
        group.layout().addWidget(apply_btn, 2, 1, alignment=QtCore.Qt.AlignmentFlag.AlignRight)

        return group

    def _create_messaging_panel(self) -> QtWidgets.QGroupBox:
        group = self._create_group("Telegram Messaging")

        self.messaging_toggle = QtWidgets.QCheckBox("Enable Bot")
        self.messaging_toggle.stateChanged.connect(self._handle_messaging_toggle)

        self.messaging_operator = QtWidgets.QComboBox()
        if self.names:
            self.messaging_operator.addItem("Choose name")
            self.messaging_operator.addItems(self.names)
            self.messaging_operator.setCurrentIndex(0)
        else:
            self.messaging_operator.addItem("No operators configured")
            self.messaging_operator.setEnabled(False)
        self.messaging_operator.currentTextChanged.connect(self._handle_operator_change)

        group.layout().addWidget(self.messaging_toggle, 0, 0, 1, 2)
        group.layout().addWidget(QtWidgets.QLabel("Operator:"), 1, 0)
        group.layout().addWidget(self.messaging_operator, 1, 1)

        return group

    def _create_optical_panel(self) -> QtWidgets.QGroupBox:
        group = self._create_group("Optical / LED Control")

        self.led_toggle = QtWidgets.QCheckBox("Enable LED / Optical Source")
        self.led_toggle.stateChanged.connect(self._handle_led_toggle)

        self.led_power_spin = QtWidgets.QDoubleSpinBox()
        self.led_power_spin.setRange(0.0, 100.0)
        self.led_power_spin.setDecimals(3)
        self.led_power_spin.setValue(self.led_power_var.get())
        self.led_power_spin.setSingleStep(0.1)
        self.led_power_spin.valueChanged.connect(self.led_power_var.set)

        self.led_sequence_edit = QtWidgets.QLineEdit()
        self.led_sequence_edit.setPlaceholderText("Sequence (optional, e.g. ON,OFF,...)")
        self.led_sequence_edit.textChanged.connect(self.led_sequence_var.set)

        apply_btn = QtWidgets.QPushButton("Apply Power")
        apply_btn.clicked.connect(self._apply_led_power)
        self.led_refresh_button = apply_btn

        self.led_status_label = QtWidgets.QLabel("Status: Off")
        self.led_status_label.setWordWrap(True)

        layout = group.layout()
        layout.addWidget(self.led_toggle, 0, 0, 1, 2)
        layout.addWidget(QtWidgets.QLabel("Power / Level"), 1, 0)
        layout.addWidget(self.led_power_spin, 1, 1)
        layout.addWidget(QtWidgets.QLabel("Sequence"), 2, 0)
        layout.addWidget(self.led_sequence_edit, 2, 1)
        layout.addWidget(apply_btn, 3, 0, 1, 2)
        layout.addWidget(self.led_status_label, 4, 0, 1, 2)

        self._update_led_controls_state(enabled=False)

        return group

    def _create_mode_panel(self) -> QtWidgets.QGroupBox:
        group = self._create_group("Mode Selection")
        layout = group.layout()
        layout.setColumnStretch(1, 1)

        row = 0
        self.measure_one_checkbox = QtWidgets.QCheckBox("Measure one device only")
        self.measure_one_checkbox.setChecked(self.single_device_flag)
        self.measure_one_checkbox.stateChanged.connect(self._handle_measure_one_toggle)
        layout.addWidget(self.measure_one_checkbox, row, 0, 1, 2)

        row += 1
        layout.addWidget(QtWidgets.QLabel("Current Device:"), row, 0)
        self.device_indicator = QtWidgets.QLabel(self.current_device or "N/A")
        layout.addWidget(self.device_indicator, row, 1)

        row += 1
        layout.addWidget(QtWidgets.QLabel("Sample Name:"), row, 0)
        self.sample_name_edit = QtWidgets.QLineEdit(self.sample_name_var.get())
        self.sample_name_edit.setPlaceholderText("Required for saving data")
        self.sample_name_edit.textChanged.connect(lambda txt: self.sample_name_var.set(txt.strip()))
        layout.addWidget(self.sample_name_edit, row, 1)

        row += 1
        layout.addWidget(QtWidgets.QLabel("Additional Info:"), row, 0)
        self.additional_info_edit = QtWidgets.QLineEdit(self.additional_info_var.get())
        self.additional_info_edit.setPlaceholderText("Optional notes (included in metadata)")
        self.additional_info_edit.textChanged.connect(self.additional_info_var.set)
        layout.addWidget(self.additional_info_edit, row, 1)

        row += 1
        self.custom_save_checkbox = QtWidgets.QCheckBox("Use custom save location")
        self.custom_save_checkbox.setChecked(False)
        self.custom_save_checkbox.toggled.connect(self._toggle_custom_save)
        layout.addWidget(self.custom_save_checkbox, row, 0, 1, 2)

        row += 1
        self.custom_save_entry = QtWidgets.QLineEdit()
        self.custom_save_entry.setReadOnly(True)
        self.custom_save_entry.setPlaceholderText("Browse for folder...")
        layout.addWidget(self.custom_save_entry, row, 0)

        self.custom_save_button = QtWidgets.QPushButton("Browse…")
        self.custom_save_button.clicked.connect(self._browse_custom_save_location)
        layout.addWidget(self.custom_save_button, row, 1)

        self._apply_saved_save_location()

        return group

    def _create_sweep_panel(self) -> QtWidgets.QGroupBox:
        group = self._create_group("Sweep Parameters")
        layout = group.layout()
        layout.setColumnStretch(1, 1)

        measurement_types = [
            "DC Triangle IV",
            "SMU_AND_PMU Pulsed IV <1.5v",
            "SMU_AND_PMU Pulsed IV >1.5v",
            "SMU_AND_PMU Fast Pulses",
            "SMU_AND_PMU Fast Hold",
            "ISPP",
            "Pulse Width Sweep",
            "Threshold Search",
            "Transient Decay",
        ]

        row = 0
        layout.addWidget(QtWidgets.QLabel("Measurement Type:"), row, 0)
        self.measurement_type_combo = QtWidgets.QComboBox()
        self.measurement_type_combo.addItems(measurement_types)
        layout.addWidget(self.measurement_type_combo, row, 1)

        row += 1
        layout.addWidget(QtWidgets.QLabel("Source Mode:"), row, 0)
        self.source_mode_combo = QtWidgets.QComboBox()
        self.source_mode_combo.addItems(["voltage", "current"])
        self.source_mode_combo.setCurrentText(self.source_mode_var.get())
        self.source_mode_combo.currentTextChanged.connect(self.source_mode_var.set)
        layout.addWidget(self.source_mode_combo, row, 1)

        row += 1
        self.measurement_stack = QtWidgets.QStackedWidget()
        layout.addWidget(self.measurement_stack, row, 0, 1, 2)

        self._measurement_forms: Dict[str, QtWidgets.QWidget] = {}
        self._measurement_indices: Dict[str, int] = {}

        self._add_measurement_form("DC Triangle IV", self._build_dc_form())
        self._add_measurement_form(
            "SMU_AND_PMU Pulsed IV <1.5v", self._build_pulsed_form(low_voltage=True)
        )
        self._add_measurement_form(
            "SMU_AND_PMU Pulsed IV >1.5v", self._build_pulsed_form(low_voltage=False)
        )
        self._add_measurement_form("SMU_AND_PMU Fast Pulses", self._build_fast_pulses_form())
        self._add_measurement_form("SMU_AND_PMU Fast Hold", self._build_fast_hold_form())
        self._add_measurement_form("ISPP", self._build_ispp_form())
        self._add_measurement_form("Pulse Width Sweep", self._build_pulse_width_form())
        self._add_measurement_form("Threshold Search", self._build_threshold_form())
        self._add_measurement_form("Transient Decay", self._build_transient_form())

        row += 1
        layout.addWidget(QtWidgets.QLabel("Compliance (A)"), row, 0)
        self.icc_spin = QtWidgets.QDoubleSpinBox()
        self.icc_spin.setDecimals(6)
        self.icc_spin.setRange(1e-9, 1.0)
        self.icc_spin.setValue(self._icc_default)
        self.icc_spin.setSingleStep(1e-4)
        self.icc = VarWrapper(self._icc_default)
        self.icc_spin.valueChanged.connect(self.icc.set)
        layout.addWidget(self.icc_spin, row, 1)

        row += 1
        layout.addWidget(QtWidgets.QLabel("Sweeps"), row, 0)
        self.sweep_count_spin = QtWidgets.QSpinBox()
        self.sweep_count_spin.setRange(1, 1000)
        self.sweep_count_spin.setValue(1)
        layout.addWidget(self.sweep_count_spin, row, 1)

        row += 1
        layout.addWidget(QtWidgets.QLabel("Step Delay (s)"), row, 0)
        self.step_delay_spin = QtWidgets.QDoubleSpinBox()
        self.step_delay_spin.setDecimals(3)
        self.step_delay_spin.setRange(0.0, 10.0)
        self.step_delay_spin.setSingleStep(0.01)
        self.step_delay_spin.setValue(self._step_delay_default)
        layout.addWidget(self.step_delay_spin, row, 1)

        row += 1
        button_row = QtWidgets.QHBoxLayout()
        run_btn = QtWidgets.QPushButton("Start")
        run_btn.clicked.connect(self._start_measurement)
        self.run_button = run_btn

        stop_btn = QtWidgets.QPushButton("Stop")
        stop_btn.clicked.connect(self._stop_measurement)
        stop_btn.setEnabled(False)
        self.stop_button = stop_btn

        button_row.addWidget(run_btn)
        button_row.addWidget(stop_btn)
        layout.addLayout(button_row, row, 0, 1, 2)

        self.measurement_type_combo.currentTextChanged.connect(self._on_measurement_type_changed)
        self._on_measurement_type_changed(self.measurement_type_combo.currentText())

        return group

    def _add_measurement_form(self, name: str, widget: QtWidgets.QWidget) -> None:
        index = self.measurement_stack.addWidget(widget)
        self._measurement_forms[name] = widget
        self._measurement_indices[name] = index

    def _build_dc_form(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QGridLayout(widget)
        layout.setColumnStretch(1, 1)

        row = 0
        layout.addWidget(QtWidgets.QLabel("Start Voltage (V)"), row, 0)
        self.start_voltage = QtWidgets.QDoubleSpinBox()
        self.start_voltage.setRange(-1000.0, 1000.0)
        self.start_voltage.setDecimals(4)
        self.start_voltage.setValue(0.0)
        layout.addWidget(self.start_voltage, row, 1)

        row += 1
        layout.addWidget(QtWidgets.QLabel("Stop Voltage (V)"), row, 0)
        self.stop_voltage = QtWidgets.QDoubleSpinBox()
        self.stop_voltage.setRange(-1000.0, 1000.0)
        self.stop_voltage.setDecimals(4)
        self.stop_voltage.setValue(5.0)
        layout.addWidget(self.stop_voltage, row, 1)

        row += 1
        layout.addWidget(QtWidgets.QLabel("Step Voltage (V)"), row, 0)
        self.step_voltage = QtWidgets.QDoubleSpinBox()
        self.step_voltage.setRange(0.0001, 100.0)
        self.step_voltage.setDecimals(4)
        self.step_voltage.setSingleStep(0.0005)
        self.step_voltage.setValue(0.1)
        layout.addWidget(self.step_voltage, row, 1)

        row += 1
        layout.addWidget(QtWidgets.QLabel("Negative Stop (V, optional)"), row, 0)
        self.dc_neg_stop_edit = QtWidgets.QLineEdit()
        self.dc_neg_stop_edit.setPlaceholderText("Leave blank to mirror positive stop")
        self.dc_neg_stop_edit.textChanged.connect(self._handle_dc_neg_stop_text)
        layout.addWidget(self.dc_neg_stop_edit, row, 1)

        row += 1
        layout.addWidget(QtWidgets.QLabel("Sweep Mode"), row, 0)
        self.dc_sweep_mode_combo = QtWidgets.QComboBox()
        self.dc_sweep_mode_combo.addItem("Fixed Step", VoltageRangeMode.FIXED_STEP)
        self.dc_sweep_mode_combo.addItem("Fixed Sweep Rate", VoltageRangeMode.FIXED_SWEEP_RATE)
        self.dc_sweep_mode_combo.addItem("Fixed Voltage Time", VoltageRangeMode.FIXED_VOLTAGE_TIME)
        layout.addWidget(self.dc_sweep_mode_combo, row, 1)

        row += 1
        layout.addWidget(QtWidgets.QLabel("Sweep Type"), row, 0)
        self.dc_sweep_type_combo = QtWidgets.QComboBox()
        self.dc_sweep_type_combo.addItem("Full Sweep (FS)", "FS")
        self.dc_sweep_type_combo.addItem("Positive Only (PS)", "PS")
        self.dc_sweep_type_combo.addItem("Negative Only (NS)", "NS")
        layout.addWidget(self.dc_sweep_type_combo, row, 1)

        row += 1
        rate_label = QtWidgets.QLabel("Sweep Rate (V/s)")
        self.dc_rate_spin = QtWidgets.QDoubleSpinBox()
        self.dc_rate_spin.setRange(0.0001, 10000.0)
        self.dc_rate_spin.setDecimals(4)
        self.dc_rate_spin.setValue(self.dc_sweep_rate_var.get())
        layout.addWidget(rate_label, row, 0)
        layout.addWidget(self.dc_rate_spin, row, 1)

        row += 1
        time_label = QtWidgets.QLabel("Total Sweep Time (s)")
        self.dc_total_time_spin = QtWidgets.QDoubleSpinBox()
        self.dc_total_time_spin.setRange(0.001, 100000.0)
        self.dc_total_time_spin.setDecimals(3)
        self.dc_total_time_spin.setValue(self.dc_total_time_var.get())
        layout.addWidget(time_label, row, 0)
        layout.addWidget(self.dc_total_time_spin, row, 1)

        row += 1
        steps_label = QtWidgets.QLabel("# Steps (optional)")
        self.dc_num_steps_spin = QtWidgets.QSpinBox()
        self.dc_num_steps_spin.setRange(0, 100000)
        self.dc_num_steps_spin.setValue(self.dc_num_steps_var.get())
        layout.addWidget(steps_label, row, 0)
        layout.addWidget(self.dc_num_steps_spin, row, 1)

        self._dc_rate_widgets = [rate_label, self.dc_rate_spin]
        self._dc_time_widgets = [time_label, self.dc_total_time_spin]
        self._dc_steps_widgets = [steps_label, self.dc_num_steps_spin]

        self.dc_sweep_mode_combo.currentIndexChanged.connect(self._update_dc_mode_fields)
        self.dc_sweep_type_combo.currentIndexChanged.connect(
            lambda _: self.dc_sweep_type_var.set(self.dc_sweep_type_combo.currentData())
        )
        self.dc_rate_spin.valueChanged.connect(lambda value: self.dc_sweep_rate_var.set(value))
        self.dc_total_time_spin.valueChanged.connect(lambda value: self.dc_total_time_var.set(value))
        self.dc_num_steps_spin.valueChanged.connect(lambda value: self.dc_num_steps_var.set(value))

        self._update_dc_mode_fields()

        return widget

    def _build_pulsed_form(self, *, low_voltage: bool) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(widget)

        prefix = "lt" if low_voltage else "gt"
        setattr(self, f"pulsed_{prefix}_start_spin", QtWidgets.QDoubleSpinBox())
        start_spin: QtWidgets.QDoubleSpinBox = getattr(self, f"pulsed_{prefix}_start_spin")
        start_spin.setRange(-20.0, 20.0)
        start_spin.setDecimals(3)
        start_spin.setValue(0.0)
        form.addRow("Start V", start_spin)

        setattr(self, f"pulsed_{prefix}_stop_spin", QtWidgets.QDoubleSpinBox())
        stop_spin: QtWidgets.QDoubleSpinBox = getattr(self, f"pulsed_{prefix}_stop_spin")
        stop_spin.setRange(-20.0, 20.0)
        stop_spin.setDecimals(3)
        stop_spin.setValue(1.0 if low_voltage else 5.0)
        form.addRow("Stop V", stop_spin)

        setattr(self, f"pulsed_{prefix}_step_spin", QtWidgets.QDoubleSpinBox())
        step_spin: QtWidgets.QDoubleSpinBox = getattr(self, f"pulsed_{prefix}_step_spin")
        step_spin.setRange(0.0001, 20.0)
        step_spin.setDecimals(4)
        step_spin.setValue(0.1)
        form.addRow("Step V", step_spin)

        setattr(self, f"pulsed_{prefix}_nsteps_spin", QtWidgets.QSpinBox())
        nsteps_spin: QtWidgets.QSpinBox = getattr(self, f"pulsed_{prefix}_nsteps_spin")
        nsteps_spin.setRange(0, 10000)
        nsteps_spin.setValue(0)
        form.addRow("# Steps (optional)", nsteps_spin)

        setattr(self, f"pulsed_{prefix}_width_spin", QtWidgets.QDoubleSpinBox())
        width_spin: QtWidgets.QDoubleSpinBox = getattr(self, f"pulsed_{prefix}_width_spin")
        width_spin.setRange(0.0001, 1000.0)
        width_spin.setDecimals(3)
        width_spin.setSuffix(" ms")
        width_spin.setValue(1.0)
        form.addRow("Pulse width", width_spin)

        setattr(self, f"pulsed_{prefix}_vbase_spin", QtWidgets.QDoubleSpinBox())
        vbase_spin: QtWidgets.QDoubleSpinBox = getattr(self, f"pulsed_{prefix}_vbase_spin")
        vbase_spin.setRange(-20.0, 20.0)
        vbase_spin.setDecimals(3)
        vbase_spin.setValue(0.2)
        form.addRow("Base Voltage", vbase_spin)

        setattr(self, f"pulsed_{prefix}_delay_spin", QtWidgets.QDoubleSpinBox())
        delay_spin: QtWidgets.QDoubleSpinBox = getattr(self, f"pulsed_{prefix}_delay_spin")
        delay_spin.setRange(0.0, 3600.0)
        delay_spin.setDecimals(3)
        delay_spin.setValue(0.0)
        form.addRow("Inter-step delay (s)", delay_spin)

        return widget

    def _build_fast_pulses_form(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(widget)

        self.fast_pulse_voltage_spin = QtWidgets.QDoubleSpinBox()
        self.fast_pulse_voltage_spin.setRange(-10.0, 10.0)
        self.fast_pulse_voltage_spin.setDecimals(3)
        self.fast_pulse_voltage_spin.setValue(0.2)
        form.addRow("Pulse Voltage (V)", self.fast_pulse_voltage_spin)

        self.fast_pulse_width_spin = QtWidgets.QDoubleSpinBox()
        self.fast_pulse_width_spin.setRange(0.0001, 1000.0)
        self.fast_pulse_width_spin.setDecimals(3)
        self.fast_pulse_width_spin.setSuffix(" ms")
        self.fast_pulse_width_spin.setValue(1.0)
        form.addRow("Pulse Width", self.fast_pulse_width_spin)

        self.fast_pulse_count_spin = QtWidgets.QSpinBox()
        self.fast_pulse_count_spin.setRange(1, 100000)
        self.fast_pulse_count_spin.setValue(10)
        form.addRow("Pulse Count", self.fast_pulse_count_spin)

        self.fast_pulse_delay_spin = QtWidgets.QDoubleSpinBox()
        self.fast_pulse_delay_spin.setRange(0.0, 3600.0)
        self.fast_pulse_delay_spin.setDecimals(3)
        self.fast_pulse_delay_spin.setValue(0.0)
        form.addRow("Inter-pulse delay (s)", self.fast_pulse_delay_spin)

        self.fast_pulse_vbase_spin = QtWidgets.QDoubleSpinBox()
        self.fast_pulse_vbase_spin.setRange(-10.0, 10.0)
        self.fast_pulse_vbase_spin.setDecimals(3)
        self.fast_pulse_vbase_spin.setValue(0.2)
        form.addRow("Base Voltage (V)", self.fast_pulse_vbase_spin)

        self.fast_pulse_max_speed_check = QtWidgets.QCheckBox("Use maximum speed")
        form.addRow(self.fast_pulse_max_speed_check)

        return widget

    def _build_fast_hold_form(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(widget)

        self.fast_hold_voltage_spin = QtWidgets.QDoubleSpinBox()
        self.fast_hold_voltage_spin.setRange(-10.0, 10.0)
        self.fast_hold_voltage_spin.setDecimals(3)
        self.fast_hold_voltage_spin.setValue(0.2)
        form.addRow("Hold Voltage (V)", self.fast_hold_voltage_spin)

        self.fast_hold_duration_spin = QtWidgets.QDoubleSpinBox()
        self.fast_hold_duration_spin.setRange(0.001, 100000.0)
        self.fast_hold_duration_spin.setDecimals(3)
        self.fast_hold_duration_spin.setValue(5.0)
        form.addRow("Hold Duration (s)", self.fast_hold_duration_spin)

        self.fast_hold_dt_spin = QtWidgets.QDoubleSpinBox()
        self.fast_hold_dt_spin.setRange(0.0001, 10.0)
        self.fast_hold_dt_spin.setDecimals(4)
        self.fast_hold_dt_spin.setValue(0.01)
        form.addRow("Sample Interval (s)", self.fast_hold_dt_spin)

        return widget

    def _build_ispp_form(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(widget)

        self.ispp_start_spin = QtWidgets.QDoubleSpinBox()
        self.ispp_start_spin.setRange(0.0, 20.0)
        self.ispp_start_spin.setDecimals(3)
        self.ispp_start_spin.setValue(0.1)
        form.addRow("Start Voltage (V)", self.ispp_start_spin)

        self.ispp_stop_spin = QtWidgets.QDoubleSpinBox()
        self.ispp_stop_spin.setRange(0.0, 20.0)
        self.ispp_stop_spin.setDecimals(3)
        self.ispp_stop_spin.setValue(1.0)
        form.addRow("Stop Voltage (V)", self.ispp_stop_spin)

        self.ispp_step_spin = QtWidgets.QDoubleSpinBox()
        self.ispp_step_spin.setRange(0.0001, 20.0)
        self.ispp_step_spin.setDecimals(4)
        self.ispp_step_spin.setValue(0.1)
        form.addRow("Step Voltage (V)", self.ispp_step_spin)

        self.ispp_pulse_spin = QtWidgets.QDoubleSpinBox()
        self.ispp_pulse_spin.setRange(0.0001, 1000.0)
        self.ispp_pulse_spin.setDecimals(3)
        self.ispp_pulse_spin.setSuffix(" ms")
        self.ispp_pulse_spin.setValue(1.0)
        form.addRow("Pulse Width", self.ispp_pulse_spin)

        self.ispp_vbase_spin = QtWidgets.QDoubleSpinBox()
        self.ispp_vbase_spin.setRange(-10.0, 10.0)
        self.ispp_vbase_spin.setDecimals(3)
        self.ispp_vbase_spin.setValue(0.2)
        form.addRow("Base Voltage (V)", self.ispp_vbase_spin)

        self.ispp_target_spin = QtWidgets.QDoubleSpinBox()
        self.ispp_target_spin.setRange(1e-12, 1.0)
        self.ispp_target_spin.setDecimals(12)
        self.ispp_target_spin.setValue(1e-5)
        form.addRow("Target |I| (A)", self.ispp_target_spin)

        self.ispp_delay_spin = QtWidgets.QDoubleSpinBox()
        self.ispp_delay_spin.setRange(0.0, 3600.0)
        self.ispp_delay_spin.setDecimals(3)
        self.ispp_delay_spin.setValue(0.0)
        form.addRow("Inter-step delay (s)", self.ispp_delay_spin)

        return widget

    def _build_pulse_width_form(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(widget)

        self.pws_amplitude_spin = QtWidgets.QDoubleSpinBox()
        self.pws_amplitude_spin.setRange(0.0, 20.0)
        self.pws_amplitude_spin.setDecimals(3)
        self.pws_amplitude_spin.setValue(0.5)
        form.addRow("Amplitude (V)", self.pws_amplitude_spin)

        self.pws_widths_edit = QtWidgets.QLineEdit("1,2,5,10")
        self.pws_widths_edit.setToolTip("Comma separated pulse widths in ms")
        form.addRow("Pulse Widths (ms)", self.pws_widths_edit)

        self.pws_vbase_spin = QtWidgets.QDoubleSpinBox()
        self.pws_vbase_spin.setRange(-10.0, 10.0)
        self.pws_vbase_spin.setDecimals(3)
        self.pws_vbase_spin.setValue(0.2)
        form.addRow("Base Voltage (V)", self.pws_vbase_spin)

        self.pws_delay_spin = QtWidgets.QDoubleSpinBox()
        self.pws_delay_spin.setRange(0.0, 3600.0)
        self.pws_delay_spin.setDecimals(3)
        self.pws_delay_spin.setValue(0.0)
        form.addRow("Inter-step delay (s)", self.pws_delay_spin)

        return widget

    def _build_threshold_form(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(widget)

        self.threshold_low_spin = QtWidgets.QDoubleSpinBox()
        self.threshold_low_spin.setRange(-20.0, 20.0)
        self.threshold_low_spin.setDecimals(3)
        self.threshold_low_spin.setValue(0.0)
        form.addRow("Low Voltage (V)", self.threshold_low_spin)

        self.threshold_high_spin = QtWidgets.QDoubleSpinBox()
        self.threshold_high_spin.setRange(-20.0, 20.0)
        self.threshold_high_spin.setDecimals(3)
        self.threshold_high_spin.setValue(1.0)
        form.addRow("High Voltage (V)", self.threshold_high_spin)

        self.threshold_pulse_spin = QtWidgets.QDoubleSpinBox()
        self.threshold_pulse_spin.setRange(0.0001, 1000.0)
        self.threshold_pulse_spin.setDecimals(3)
        self.threshold_pulse_spin.setSuffix(" ms")
        self.threshold_pulse_spin.setValue(1.0)
        form.addRow("Pulse Width", self.threshold_pulse_spin)

        self.threshold_vbase_spin = QtWidgets.QDoubleSpinBox()
        self.threshold_vbase_spin.setRange(-10.0, 10.0)
        self.threshold_vbase_spin.setDecimals(3)
        self.threshold_vbase_spin.setValue(0.2)
        form.addRow("Base Voltage (V)", self.threshold_vbase_spin)

        self.threshold_target_spin = QtWidgets.QDoubleSpinBox()
        self.threshold_target_spin.setRange(1e-12, 1.0)
        self.threshold_target_spin.setDecimals(12)
        self.threshold_target_spin.setValue(1e-5)
        form.addRow("Target |I| (A)", self.threshold_target_spin)

        self.threshold_iterations_spin = QtWidgets.QSpinBox()
        self.threshold_iterations_spin.setRange(1, 1000)
        self.threshold_iterations_spin.setValue(12)
        form.addRow("Max Iterations", self.threshold_iterations_spin)

        return widget

    def _build_transient_form(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(widget)

        self.transient_pulse_voltage_spin = QtWidgets.QDoubleSpinBox()
        self.transient_pulse_voltage_spin.setRange(-20.0, 20.0)
        self.transient_pulse_voltage_spin.setDecimals(3)
        self.transient_pulse_voltage_spin.setValue(0.8)
        form.addRow("Pulse Voltage (V)", self.transient_pulse_voltage_spin)

        self.transient_pulse_width_spin = QtWidgets.QDoubleSpinBox()
        self.transient_pulse_width_spin.setRange(0.0001, 1000.0)
        self.transient_pulse_width_spin.setDecimals(3)
        self.transient_pulse_width_spin.setSuffix(" ms")
        self.transient_pulse_width_spin.setValue(1.0)
        form.addRow("Pulse Width", self.transient_pulse_width_spin)

        self.transient_read_voltage_spin = QtWidgets.QDoubleSpinBox()
        self.transient_read_voltage_spin.setRange(-20.0, 20.0)
        self.transient_read_voltage_spin.setDecimals(3)
        self.transient_read_voltage_spin.setValue(0.2)
        form.addRow("Read Voltage (V)", self.transient_read_voltage_spin)

        self.transient_capture_time_spin = QtWidgets.QDoubleSpinBox()
        self.transient_capture_time_spin.setRange(0.001, 100000.0)
        self.transient_capture_time_spin.setDecimals(3)
        self.transient_capture_time_spin.setValue(1.0)
        form.addRow("Capture Time (s)", self.transient_capture_time_spin)

        self.transient_dt_spin = QtWidgets.QDoubleSpinBox()
        self.transient_dt_spin.setRange(0.0001, 10.0)
        self.transient_dt_spin.setDecimals(4)
        self.transient_dt_spin.setValue(0.001)
        form.addRow("Sample Interval (s)", self.transient_dt_spin)

        return widget

    def _on_measurement_type_changed(self, name: str) -> None:
        index = self._measurement_indices.get(name)
        if index is not None:
            self.measurement_stack.setCurrentIndex(index)
        if name == "DC Triangle IV":
            self._update_dc_mode_fields()

    def _handle_dc_neg_stop_text(self, text: str) -> None:
        stripped = text.strip()
        if not stripped:
            self.dc_neg_stop_var.set(None)
            return
        try:
            value = float(stripped)
        except ValueError:
            self.dc_neg_stop_var.set(None)
        else:
            self.dc_neg_stop_var.set(value)

    def _update_dc_mode_fields(self) -> None:
        if not hasattr(self, "dc_sweep_mode_combo"):
            return
        mode = self.dc_sweep_mode_combo.currentData()
        self.dc_sweep_mode_var.set(mode)
        self.dc_sweep_type_var.set(self.dc_sweep_type_combo.currentData())

        show_rate = mode == VoltageRangeMode.FIXED_SWEEP_RATE
        for widget in self._dc_rate_widgets:
            widget.setVisible(show_rate)

        show_time = mode == VoltageRangeMode.FIXED_VOLTAGE_TIME
        for widget in self._dc_time_widgets:
            widget.setVisible(show_time)

        show_steps = mode in (VoltageRangeMode.FIXED_SWEEP_RATE, VoltageRangeMode.FIXED_VOLTAGE_TIME)
        for widget in self._dc_steps_widgets:
            widget.setVisible(show_steps)

    def _collect_measurement_config(self) -> Dict[str, Any]:
        measurement_type = self.measurement_type_combo.currentText()
        config: Dict[str, Any] = {
            "type": measurement_type,
            "source_mode": self.source_mode_combo.currentText(),
            "compliance": float(self.icc_spin.value()),
            "sweeps": int(self.sweep_count_spin.value()),
            "step_delay": float(self.step_delay_spin.value()),
        }

        if measurement_type == "DC Triangle IV":
            mode = self.dc_sweep_mode_combo.currentData()
            sweep_rate = float(self.dc_rate_spin.value()) if mode == VoltageRangeMode.FIXED_SWEEP_RATE else None
            total_time = float(self.dc_total_time_spin.value()) if mode == VoltageRangeMode.FIXED_VOLTAGE_TIME else None
            num_steps = int(self.dc_num_steps_spin.value()) if mode in (
                VoltageRangeMode.FIXED_SWEEP_RATE,
                VoltageRangeMode.FIXED_VOLTAGE_TIME,
            ) else None
            neg_stop_text = self.dc_neg_stop_edit.text().strip()
            neg_stop_val = None
            if neg_stop_text:
                try:
                    neg_stop_val = float(neg_stop_text)
                except ValueError:
                    neg_stop_val = None
            config["dc"] = {
                "start_voltage": float(self.start_voltage.value()),
                "stop_voltage": float(self.stop_voltage.value()),
                "step_voltage": float(self.step_voltage.value()),
                "neg_stop_voltage": neg_stop_val,
                "sweep_mode": mode,
                "sweep_type": self.dc_sweep_type_combo.currentData(),
                "sweep_rate": sweep_rate,
                "total_time": total_time,
                "num_steps": num_steps,
            }
        elif measurement_type in (
            "SMU_AND_PMU Pulsed IV <1.5v",
            "SMU_AND_PMU Pulsed IV >1.5v",
        ):
            prefix = "lt" if measurement_type.endswith("<1.5v") else "gt"
            config["pulsed"] = {
                "high_voltage_mode": prefix == "gt",
                "start_voltage": float(getattr(self, f"pulsed_{prefix}_start_spin").value()),
                "stop_voltage": float(getattr(self, f"pulsed_{prefix}_stop_spin").value()),
                "step_voltage": float(getattr(self, f"pulsed_{prefix}_step_spin").value()),
                "num_steps": int(getattr(self, f"pulsed_{prefix}_nsteps_spin").value()),
                "pulse_width_ms": float(getattr(self, f"pulsed_{prefix}_width_spin").value()),
                "base_voltage": float(getattr(self, f"pulsed_{prefix}_vbase_spin").value()),
                "inter_delay_s": float(getattr(self, f"pulsed_{prefix}_delay_spin").value()),
            }
        elif measurement_type == "SMU_AND_PMU Fast Pulses":
            config["fast_pulses"] = {
                "pulse_voltage": float(self.fast_pulse_voltage_spin.value()),
                "pulse_width_ms": float(self.fast_pulse_width_spin.value()),
                "pulse_count": int(self.fast_pulse_count_spin.value()),
                "inter_delay_s": float(self.fast_pulse_delay_spin.value()),
                "base_voltage": float(self.fast_pulse_vbase_spin.value()),
                "max_speed": self.fast_pulse_max_speed_check.isChecked(),
            }
        elif measurement_type == "SMU_AND_PMU Fast Hold":
            config["fast_hold"] = {
                "hold_voltage": float(self.fast_hold_voltage_spin.value()),
                "hold_duration_s": float(self.fast_hold_duration_spin.value()),
                "sample_interval_s": float(self.fast_hold_dt_spin.value()),
            }
        elif measurement_type == "ISPP":
            config["ispp"] = {
                "start_voltage": float(self.ispp_start_spin.value()),
                "stop_voltage": float(self.ispp_stop_spin.value()),
                "step_voltage": float(self.ispp_step_spin.value()),
                "pulse_width_ms": float(self.ispp_pulse_spin.value()),
                "base_voltage": float(self.ispp_vbase_spin.value()),
                "target_current": float(self.ispp_target_spin.value()),
                "inter_delay_s": float(self.ispp_delay_spin.value()),
            }
        elif measurement_type == "Pulse Width Sweep":
            widths_text = self.pws_widths_edit.text()
            try:
                widths_list = [
                    float(token.strip())
                    for token in widths_text.split(",")
                    if token.strip()
                ]
            except ValueError:
                widths_list = []
            config["pulse_width_sweep"] = {
                "amplitude": float(self.pws_amplitude_spin.value()),
                "widths_ms": widths_list,
                "widths_raw": widths_text,
                "base_voltage": float(self.pws_vbase_spin.value()),
                "inter_delay_s": float(self.pws_delay_spin.value()),
            }
        elif measurement_type == "Threshold Search":
            config["threshold"] = {
                "voltage_low": float(self.threshold_low_spin.value()),
                "voltage_high": float(self.threshold_high_spin.value()),
                "pulse_width_ms": float(self.threshold_pulse_spin.value()),
                "base_voltage": float(self.threshold_vbase_spin.value()),
                "target_current": float(self.threshold_target_spin.value()),
                "max_iterations": int(self.threshold_iterations_spin.value()),
            }
        elif measurement_type == "Transient Decay":
            config["transient"] = {
                "pulse_voltage": float(self.transient_pulse_voltage_spin.value()),
                "pulse_width_ms": float(self.transient_pulse_width_spin.value()),
                "read_voltage": float(self.transient_read_voltage_spin.value()),
                "capture_time_s": float(self.transient_capture_time_spin.value()),
                "sample_interval_s": float(self.transient_dt_spin.value()),
            }

        config["led"] = {
            "enabled": bool(self.led_enabled),
            "power": float(self.led_power_spin.value()),
            "sequence": self.led_sequence_var.get(),
            "using_optical_controller": self.optical_controller is not None,
            "psu_connected": bool(self.psu_connected),
        }

        return config

    def _collect_sample_metadata(self) -> Dict[str, Any]:
        return {
            "sample_name": self.sample_name_var.get(),
            "additional_info": self.additional_info_var.get(),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "custom_save_enabled": bool(self.use_custom_save_var.get()),
            "custom_save_path": str(self.custom_save_location) if self.custom_save_location else None,
            "measurement_type": self.measurement_type_combo.currentText(),
            "source_mode": self.source_mode_combo.currentText(),
        }

    def _store_measurement_result(
        self,
        voltage: Iterable[float],
        current: Iterable[float],
        time_arr: Iterable[float],
        result_metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        device = self.current_device or (self.device_list[0] if self.device_list else "Device-1")
        metadata = self._collect_sample_metadata()
        if result_metadata:
            metadata.update({k: v for k, v in result_metadata.items() if k != "extra_series"})
        timestamp_key = metadata["timestamp"]
        device_store = self.measurement_data.setdefault(device, {})
        device_store[timestamp_key] = {
            "voltage": list(voltage),
            "current": list(current),
            "time": list(time_arr),
            "metadata": metadata,
        }
        if result_metadata and "extra_series" in result_metadata:
            device_store[timestamp_key]["extra_series"] = result_metadata["extra_series"]
        self.last_measurement_entry = {
            "device": device,
            "key": timestamp_key,
            "data": device_store[timestamp_key],
        }
        self.append_status(
            f"Stored measurement for {device} at {timestamp_key} "
            f"(sample: {metadata['sample_name'] or 'undefined'})."
        )
        self._persist_measurement(device, metadata, voltage, current, time_arr)

    def _resolve_device_label(self, device_key: str) -> str:
        if hasattr(self.sample_gui, "get_device_label"):
            try:
                return str(self.sample_gui.get_device_label(device_key))
            except Exception:
                pass
        return device_key

    def _resolve_sample_name(self, metadata: Dict[str, Any]) -> str:
        name = metadata.get("sample_name") or ""
        return name.strip() or "undefined"

    def _split_device_label(self, device: Optional[str]) -> Tuple[str, str]:
        if not device:
            return "", ""
        device = str(device).strip()
        if not device:
            return "", ""
        first_char = device[0]
        if first_char.isalpha():
            letter = first_char.upper()
            number = device[1:] or "1"
        else:
            parts = device.replace("-", "_").split("_", 1)
            letter = parts[0]
            number = parts[1] if len(parts) > 1 else ""
        return letter, number

    def _make_json_safe(self, value: Any) -> Any:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, (list, tuple, set)):
            return [self._make_json_safe(v) for v in value]
        if isinstance(value, dict):
            return {str(k): self._make_json_safe(v) for k, v in value.items()}
        try:
            return float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return str(value)

    def _build_save_metadata(
        self,
        base_metadata: Dict[str, Any],
        result_metadata: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        combined: Dict[str, Any] = {}
        keys = [
            "sample_name",
            "additional_info",
            "timestamp",
            "measurement_type",
            "source_mode",
            "custom_save_enabled",
            "custom_save_path",
        ]
        for key in keys:
            if key in base_metadata and base_metadata[key] is not None:
                combined[key] = base_metadata[key]
        if result_metadata:
            for key in [
                "measurement_type",
                "x_axis_label",
                "y_axis_label",
                "parameters",
                "led",
            ]:
                if key in result_metadata and result_metadata[key] is not None:
                    combined[key] = result_metadata[key]
        return self._make_json_safe(combined)

    def _get_optical_suffix(self, led_cfg: Dict[str, Any]) -> str:
        try:
            if led_cfg.get("enabled"):
                if self.optical_controller is not None:
                    caps = getattr(self.optical_controller, "capabilities", {}) or {}
                    unit = str(caps.get("units", "mW"))
                    lvl = float(led_cfg.get("power", 0.0))
                    typ = str(caps.get("type", "LED")).upper()
                    return f"-{typ}{lvl}{unit}"
                if led_cfg.get("psu_connected"):
                    lvl = float(led_cfg.get("power", 0.0))
                    return f"-LED{lvl}"
        except Exception:
            pass
        return ""

    def _persist_measurement(
        self,
        device_key: str,
        metadata: Dict[str, Any],
        voltage: Iterable[float],
        current: Iterable[float],
        time_arr: Iterable[float],
        result_metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        result_meta = result_metadata or self._active_result_metadata or {}
        measurement_type = (
            result_meta.get("measurement_type") or metadata.get("measurement_type") or "Unknown"
        )
        try:
            last_config = getattr(self, "last_measurement_config", {}) or {}
            sample_name = self._resolve_sample_name(metadata)
            metadata["sample_name"] = sample_name
            device_label = self._resolve_device_label(device_key)
            base_override: Optional[Path] = None
            if metadata.get("custom_save_enabled") and self.custom_save_location:
                base_override = self.custom_save_location
            save_metadata = self._build_save_metadata(metadata, result_meta)

            if measurement_type == "DC Triangle IV":
                sweep_info = last_config.get("dc", {})
                if not sweep_info:
                    return
                led_suffix = self._get_optical_suffix(last_config.get("led", {}))
                saved_path = self.data_saver.save_iv_sweep(
                    voltages=list(voltage),
                    currents=list(current),
                    timestamps=list(time_arr),
                    device_label=device_label,
                    sample_name=sample_name,
                    sweep_type=str(sweep_info.get("sweep_type", "FS")),
                    stop_voltage=float(sweep_info.get("stop_voltage", 0.0)),
                    sweeps=int(last_config.get("sweeps", 1)),
                    step_voltage=float(sweep_info.get("step_voltage", 0.1)),
                    delay_s=float(last_config.get("step_delay", self._step_delay_default)),
                    optical_suffix=led_suffix,
                    metadata={"additional_info": str(metadata.get("additional_info", ""))},
                    base_override=base_override,
                )
                self.append_status(f"[SAVE] Saved IV sweep to {saved_path}")
                summary_data = SummaryPlotData(
                    all_iv=[(hist["voltage"], hist["current"]) for hist in self._all_sweeps_history],
                    all_log=[
                        (hist["voltage"], [abs(i) for i in hist["current"]]) for hist in self._all_sweeps_history
                    ],
                    final_iv=(list(voltage), list(current)),
                )
                summary_dir = saved_path.parent
                try:
                    self.data_saver.save_summary_plots(summary_dir, summary_data)
                except Exception as exc:
                    self.append_status(f"[SAVE] Failed to save summary plots: {exc}")
                return

            saved_path = self.data_saver.save_measurement_trace(
                sample_name=sample_name,
                device_label=device_label,
                measurement_label=measurement_type.replace(" ", "_"),
                x_values=list(voltage),
                y_values=list(current),
                x_label=str(result_meta.get("x_axis_label") or "X"),
                y_label=str(result_meta.get("y_axis_label") or "Current (A)"),
                timestamps=list(time_arr),
                extra_series=result_meta.get("extra_series"),
                metadata=save_metadata,
                base_override=base_override,
            )
            if saved_path:
                self.append_status(f"[SAVE] Saved {measurement_type} data to {saved_path}")
        except Exception as exc:
            self.append_status(f"[SAVE] Error while persisting sweep: {exc}")

    def _clear_sweep_history(self) -> None:
        if not self._all_sweeps_history:
            self.append_status("Sweep history already empty.")
            return
        self._all_sweeps_history.clear()
        self._update_all_sweeps_plots()
        self.append_status("Cleared sweep history.")

    # ------------------------------------------------------------------
    # Manual endurance / retention
    # ------------------------------------------------------------------
    def _manual_should_stop(self) -> bool:
        return bool(self.manual_stop_requested)

    def _set_manual_controls_enabled(self, enabled: bool) -> None:
        self.manual_endurance_start_btn.setEnabled(enabled)
        self.manual_retention_start_btn.setEnabled(enabled)

    def _start_manual_endurance(self) -> None:
        if not self.keithley:
            QtWidgets.QMessageBox.warning(
                self,
                "SMU Not Connected",
                "Connect the SMU before starting manual endurance.",
            )
            return
        if self.manual_endurance_thread is not None or self.manual_retention_thread is not None:
            QtWidgets.QMessageBox.information(
                self,
                "Manual Tests Running",
                "Stop the current manual test before starting a new one.",
            )
            return

        self.manual_stop_requested = False
        self._set_manual_controls_enabled(False)
        set_v = float(self.end_set_spin.value())
        reset_v = float(self.end_reset_spin.value())
        read_v = float(self.end_read_spin.value())
        pulse_width_s = float(self.end_pulse_spin.value()) / 1000.0
        cycles = int(self.end_cycles_spin.value())

        worker = ManualEnduranceWorker(
            keithley=self.keithley,
            set_voltage=set_v,
            reset_voltage=reset_v,
            read_voltage=read_v,
            pulse_width_s=pulse_width_s,
            cycles=cycles,
            should_stop=self._manual_should_stop,
        )
        thread = QtCore.QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._manual_endurance_progress)
        worker.finished.connect(self._manual_endurance_finished)
        worker.status.connect(self.append_status)
        worker.error.connect(self._manual_worker_error)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._manual_endurance_cleanup)

        self.manual_endurance_thread = thread
        self.manual_endurance_worker = worker
        self.manual_status_label.setText("Status: Endurance running…")
        self.append_status("Manual endurance started.")
        thread.start()

    def _manual_endurance_progress(self, ratios: List[float]) -> None:
        self.endurance_ratios = ratios
        self._update_endurance_plot()

    def _manual_endurance_finished(self, ratios: List[float]) -> None:
        self.endurance_ratios = ratios
        self._update_endurance_plot()
        self.append_status("Manual endurance complete.")
        self.manual_status_label.setText("Status: Idle")
        self.manual_stop_requested = False
        self._set_manual_controls_enabled(True)
        self._persist_manual_endurance(ratios)

    def _manual_endurance_cleanup(self) -> None:
        self.manual_endurance_thread = None
        self.manual_endurance_worker = None

    def _start_manual_retention(self) -> None:
        if not self.keithley:
            QtWidgets.QMessageBox.warning(
                self,
                "SMU Not Connected",
                "Connect the SMU before starting manual retention.",
            )
            return
        if self.manual_endurance_thread is not None or self.manual_retention_thread is not None:
            QtWidgets.QMessageBox.information(
                self,
                "Manual Tests Running",
                "Stop the current manual test before starting a new one.",
            )
            return

        self.manual_stop_requested = False
        self._set_manual_controls_enabled(False)
        set_v = float(self.ret_set_spin.value())
        set_time_s = float(self.ret_set_time_spin.value()) / 1000.0
        read_v = float(self.ret_read_spin.value())
        interval_s = float(self.ret_interval_spin.value())
        points = int(self.ret_points_spin.value())
        total_estimate = interval_s * points
        self.ret_estimate_label.setText(f"Total ~{int(total_estimate)} s")

        worker = ManualRetentionWorker(
            keithley=self.keithley,
            set_voltage=set_v,
            set_time_s=set_time_s,
            read_voltage=read_v,
            interval_s=interval_s,
            points=points,
            should_stop=self._manual_should_stop,
        )
        thread = QtCore.QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._manual_retention_progress)
        worker.finished.connect(self._manual_retention_finished)
        worker.status.connect(self.append_status)
        worker.error.connect(self._manual_worker_error)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._manual_retention_cleanup)

        self.manual_retention_thread = thread
        self.manual_retention_worker = worker
        self.manual_status_label.setText("Status: Retention running…")
        self.append_status("Manual retention started.")
        thread.start()

    def _manual_retention_progress(self, times: List[float], currents: List[float]) -> None:
        self.retention_times = times
        self.retention_currents = currents
        self._update_retention_plot()

    def _manual_retention_finished(self, times: List[float], currents: List[float]) -> None:
        self.retention_times = times
        self.retention_currents = currents
        self._update_retention_plot()
        self.append_status("Manual retention complete.")
        self.manual_status_label.setText("Status: Idle")
        self.manual_stop_requested = False
        self._set_manual_controls_enabled(True)
        self._persist_manual_retention(times, currents)

    def _manual_retention_cleanup(self) -> None:
        self.manual_retention_thread = None
        self.manual_retention_worker = None

    def _stop_manual_tests(self) -> None:
        if not (self.manual_endurance_thread or self.manual_retention_thread):
            self.append_status("No manual tests are currently running.")
            return
        self.manual_stop_requested = True
        self.manual_status_label.setText("Status: Stopping…")
        self.append_status("Manual tests stop requested.")

    def _manual_worker_error(self, message: str) -> None:
        self.append_status(f"[Manual tests] Error: {message}")
        QtWidgets.QMessageBox.warning(self, "Manual Tests", message)
        self.manual_status_label.setText("Status: Error")
        self.manual_stop_requested = False
        self._set_manual_controls_enabled(True)

    def _update_endurance_plot(self) -> None:
        if not hasattr(self, "endurance_ax") or self.endurance_ax is None:
            return
        self.endurance_ax.clear()
        self.endurance_ax.set_title("Manual Endurance (ON/OFF)")
        self.endurance_ax.set_xlabel("Cycle")
        self.endurance_ax.set_ylabel("ON/OFF Ratio")
        self.endurance_ax.grid(True, alpha=0.2)
        if self.endurance_ratios:
            cycles = list(range(1, len(self.endurance_ratios) + 1))
            self.endurance_ax.plot(cycles, self.endurance_ratios, marker="o", color="#2ca02c")
        if hasattr(self, "endurance_canvas") and self.endurance_canvas:
            self.endurance_canvas.draw_idle()

    def _update_retention_plot(self) -> None:
        if not hasattr(self, "retention_ax") or self.retention_ax is None:
            return
        self.retention_ax.clear()
        self.retention_ax.set_title("Manual Retention")
        self.retention_ax.set_xlabel("Time (s)")
        self.retention_ax.set_ylabel("|Current| (A)")
        self.retention_ax.set_xscale("log")
        self.retention_ax.set_yscale("log")
        self.retention_ax.grid(True, alpha=0.2)
        if self.retention_times and self.retention_currents:
            self.retention_ax.plot(self.retention_times, self.retention_currents, marker="x", color="#d62728")
        if hasattr(self, "retention_canvas") and self.retention_canvas:
            self.retention_canvas.draw_idle()

    def _persist_manual_endurance(self, ratios: List[float]) -> None:
        if not ratios:
            return
        metadata = self._collect_sample_metadata()
        sample_name = self._resolve_sample_name(metadata)
        metadata["sample_name"] = sample_name
        device_key = self.current_device or (self.device_list[0] if self.device_list else "Device-1")
        device_label = self._resolve_device_label(device_key)
        params = {
            "set_voltage": float(self.end_set_spin.value()),
            "reset_voltage": float(self.end_reset_spin.value()),
            "read_voltage": float(self.end_read_spin.value()),
            "pulse_width_s": float(self.end_pulse_spin.value()) / 1000.0,
            "cycles": int(self.end_cycles_spin.value()),
        }
        result_meta = {
            "measurement_type": "Manual Endurance",
            "x_axis_label": "Cycle",
            "y_axis_label": "ON/OFF Ratio",
            "parameters": self._make_json_safe(params),
        }
        base_override: Optional[Path] = None
        if metadata.get("custom_save_enabled") and self.custom_save_location:
            base_override = self.custom_save_location
        save_metadata = self._build_save_metadata(metadata, result_meta)
        cycles = list(range(1, len(ratios) + 1))
        saved_path = self.data_saver.save_measurement_trace(
            sample_name=sample_name,
            device_label=device_label,
            measurement_label="Manual_Endurance",
            x_values=cycles,
            y_values=ratios,
            x_label="Cycle",
            y_label="ON/OFF Ratio",
            metadata=save_metadata,
            base_override=base_override,
        )
        if saved_path:
            self.append_status(f"[SAVE] Manual endurance saved to {saved_path}")

    def _persist_manual_retention(self, times: List[float], currents: List[float]) -> None:
        if not times or not currents:
            return
        metadata = self._collect_sample_metadata()
        sample_name = self._resolve_sample_name(metadata)
        metadata["sample_name"] = sample_name
        device_key = self.current_device or (self.device_list[0] if self.device_list else "Device-1")
        device_label = self._resolve_device_label(device_key)
        params = {
            "set_voltage": float(self.ret_set_spin.value()),
            "set_time_s": float(self.ret_set_time_spin.value()) / 1000.0,
            "read_voltage": float(self.ret_read_spin.value()),
            "interval_s": float(self.ret_interval_spin.value()),
            "points": int(self.ret_points_spin.value()),
        }
        result_meta = {
            "measurement_type": "Manual Retention",
            "x_axis_label": "Time (s)",
            "y_axis_label": "|Current| (A)",
            "parameters": self._make_json_safe(params),
        }
        base_override: Optional[Path] = None
        if metadata.get("custom_save_enabled") and self.custom_save_location:
            base_override = self.custom_save_location
        save_metadata = self._build_save_metadata(metadata, result_meta)
        saved_path = self.data_saver.save_measurement_trace(
            sample_name=sample_name,
            device_label=device_label,
            measurement_label="Manual_Retention",
            x_values=times,
            y_values=currents,
            x_label="Time (s)",
            y_label="|Current| (A)",
            metadata=save_metadata,
            base_override=base_override,
        )
        if saved_path:
            self.append_status(f"[SAVE] Manual retention saved to {saved_path}")

    def _record_sweep_history(self, voltage: Iterable[float], current: Iterable[float]) -> None:
        history_entry = {
            "voltage": list(voltage),
            "current": list(current),
        }
        self._all_sweeps_history.append(history_entry)
        if len(self._all_sweeps_history) > self._max_history_traces:
            self._all_sweeps_history.pop(0)
        self._update_all_sweeps_plots()

    def _update_all_sweeps_plots(self) -> None:
        if not hasattr(self, "all_sweeps_ax"):
            return

        def _render(ax: Any, *, log_scale: bool) -> None:
            ax.clear()
            ax.set_title("All Sweeps (Log |I|)" if log_scale else "All Sweeps (Linear)")
            ax.set_xlabel("Voltage (V)")
            ax.set_ylabel("|Current| (A)" if log_scale else "Current (A)")
            if log_scale:
                ax.set_yscale("log")
                grid_kw = {"which": "both"}
            else:
                ax.set_yscale("linear")
                grid_kw = {}
            ax.grid(True, alpha=0.2, **grid_kw)
            prop_cycle = rcParams.get("axes.prop_cycle")
            colors = []
            if prop_cycle is not None:
                try:
                    colors = list(prop_cycle.by_key().get("color", []))
                except Exception:
                    colors = []
            color_cycle = cycle(colors or ["#1f77b4"])
            for idx, entry in enumerate(self._all_sweeps_history, start=1):
                color = next(color_cycle)
                voltage = entry["voltage"]
                current = entry["current"]
                y_values = [max(abs(i), 1e-12) for i in current] if log_scale else current
                label = f"Sweep {idx}"
                ax.plot(voltage, y_values, color=color, alpha=0.85, label=label)
            if self._all_sweeps_history:
                ax.legend(loc="best", fontsize="x-small")

        if self.all_sweeps_ax is not None:
            _render(self.all_sweeps_ax, log_scale=False)
            if getattr(self, "all_sweeps_canvas", None):
                self.all_sweeps_canvas.draw_idle()
        if self.all_sweeps_log_ax is not None:
            _render(self.all_sweeps_log_ax, log_scale=True)
            if getattr(self, "all_sweeps_log_canvas", None):
                self.all_sweeps_log_canvas.draw_idle()

    def _create_custom_panel(self) -> QtWidgets.QGroupBox:
        group = self._create_group("Custom Measurement")
        group.layout().addWidget(QtWidgets.QLabel("Preset:"), 0, 0)
        self.custom_combo = QtWidgets.QComboBox()
        presets = ["None"] + sorted(self.custom_sweeps.keys())
        self.custom_combo.addItems(presets)
        group.layout().addWidget(self.custom_combo, 0, 1)

        edit_btn = QtWidgets.QPushButton("Edit Presets")
        edit_btn.clicked.connect(self._open_custom_editor)
        group.layout().addWidget(edit_btn, 1, 1, alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        return group

    def _create_sequential_panel(self) -> QtWidgets.QGroupBox:
        group = self._create_group("Sequential Measurements")
        self.widgets.sequential = group

        self.seq_mode_combo = QtWidgets.QComboBox()
        self.seq_mode_combo.addItems(["Iv Sweep", "Single Avg Measure"])
        self.seq_mode_combo.currentTextChanged.connect(self.Sequential_measurement_var.set)
        group.layout().addWidget(QtWidgets.QLabel("Mode"), 0, 0)
        group.layout().addWidget(self.seq_mode_combo, 0, 1)

        self.seq_voltage_spin = QtWidgets.QDoubleSpinBox()
        self.seq_voltage_spin.setDecimals(3)
        self.seq_voltage_spin.setRange(-1000.0, 1000.0)
        self.seq_voltage_spin.setValue(self.sq_voltage.get())
        group.layout().addWidget(QtWidgets.QLabel("Voltage (V)"), 1, 0)
        group.layout().addWidget(self.seq_voltage_spin, 1, 1)

        self.seq_count_spin = QtWidgets.QSpinBox()
        self.seq_count_spin.setRange(1, 1000)
        self.seq_count_spin.setValue(self.sequential_number_of_sweeps.get())
        group.layout().addWidget(QtWidgets.QLabel("Iterations"), 2, 0)
        group.layout().addWidget(self.seq_count_spin, 2, 1)

        self.seq_delay_spin = QtWidgets.QDoubleSpinBox()
        self.seq_delay_spin.setDecimals(2)
        self.seq_delay_spin.setRange(0.0, 3600.0)
        self.seq_delay_spin.setValue(self.sq_time_delay.get())
        group.layout().addWidget(QtWidgets.QLabel("Delay (s)"), 3, 0)
        group.layout().addWidget(self.seq_delay_spin, 3, 1)

        self.seq_duration_spin = QtWidgets.QDoubleSpinBox()
        self.seq_duration_spin.setDecimals(2)
        self.seq_duration_spin.setRange(0.1, 3600.0)
        self.seq_duration_spin.setValue(self.measurement_duration_var.get())
        group.layout().addWidget(QtWidgets.QLabel("Avg Duration (s)"), 4, 0)
        group.layout().addWidget(self.seq_duration_spin, 4, 1)

        self.seq_record_temp = QtWidgets.QCheckBox("Record Temperature")
        self.seq_record_temp.setChecked(self.record_temp_var.get())
        self.seq_record_temp.toggled.connect(self.record_temp_var.set)
        group.layout().addWidget(self.seq_record_temp, 5, 0, 1, 2)

        self.seq_single_device = QtWidgets.QCheckBox("Single device only")
        self.seq_single_device.setChecked(True)
        self.seq_single_device.toggled.connect(self._handle_single_device_toggle)
        group.layout().addWidget(self.seq_single_device, 6, 0, 1, 2)

        self.seq_device_combo = QtWidgets.QComboBox()
        self.seq_device_combo.addItems(self.device_list)
        self.seq_device_combo.currentTextChanged.connect(self._on_sequential_device_selected)
        group.layout().addWidget(QtWidgets.QLabel("Start Device"), 7, 0)
        group.layout().addWidget(self.seq_device_combo, 7, 1)

        button_row = QtWidgets.QHBoxLayout()
        self.seq_run_button = QtWidgets.QPushButton("Run Sequential")
        self.seq_run_button.clicked.connect(self._start_sequential)
        self.seq_stop_button = QtWidgets.QPushButton("Stop")
        self.seq_stop_button.setEnabled(False)
        self.seq_stop_button.clicked.connect(self._stop_sequential)
        button_row.addWidget(self.seq_run_button)
        button_row.addWidget(self.seq_stop_button)
        group.layout().addLayout(button_row, 8, 0, 1, 2)

        self.set_sequential_state("idle")
        return group

    def _create_automation_panel(self) -> QtWidgets.QGroupBox:
        group = self._create_group("Utilities")
        layout = group.layout()

        motor_btn = QtWidgets.QPushButton("Motor Control")
        motor_btn.clicked.connect(self._open_motor_control)
        layout.addWidget(motor_btn, 0, 0, 1, 2)

        pmu_btn = QtWidgets.QPushButton("PMU Testing")
        pmu_btn.clicked.connect(self._open_pmu_testing)
        layout.addWidget(pmu_btn, 1, 0, 1, 2)

        tsp_btn = QtWidgets.QPushButton("2450 TSP Pulse Testing")
        tsp_btn.clicked.connect(self._open_tsp_testing)
        layout.addWidget(tsp_btn, 2, 0, 1, 2)

        advanced_btn = QtWidgets.QPushButton("Advanced Tests")
        advanced_btn.clicked.connect(self._open_advanced_tests)
        layout.addWidget(advanced_btn, 3, 0, 1, 2)

        return group

    def _create_manual_tests_panel(self) -> QtWidgets.QGroupBox:
        group = self._create_group("Manual Endurance / Retention")
        layout = group.layout()
        layout.setHorizontalSpacing(10)

        endurance_box = QtWidgets.QGroupBox("Endurance")
        endurance_layout = QtWidgets.QFormLayout(endurance_box)
        endurance_layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.end_set_spin = QtWidgets.QDoubleSpinBox()
        self.end_set_spin.setRange(-10.0, 10.0)
        self.end_set_spin.setDecimals(3)
        self.end_set_spin.setValue(1.5)
        endurance_layout.addRow("SET Voltage (V)", self.end_set_spin)

        self.end_reset_spin = QtWidgets.QDoubleSpinBox()
        self.end_reset_spin.setRange(-10.0, 10.0)
        self.end_reset_spin.setDecimals(3)
        self.end_reset_spin.setValue(-1.5)
        endurance_layout.addRow("RESET Voltage (V)", self.end_reset_spin)

        self.end_pulse_spin = QtWidgets.QDoubleSpinBox()
        self.end_pulse_spin.setRange(0.01, 10000.0)
        self.end_pulse_spin.setDecimals(2)
        self.end_pulse_spin.setSuffix(" ms")
        self.end_pulse_spin.setValue(10.0)
        endurance_layout.addRow("Pulse Width", self.end_pulse_spin)

        self.end_cycles_spin = QtWidgets.QSpinBox()
        self.end_cycles_spin.setRange(1, 1000000)
        self.end_cycles_spin.setValue(100)
        endurance_layout.addRow("Cycles", self.end_cycles_spin)

        self.end_read_spin = QtWidgets.QDoubleSpinBox()
        self.end_read_spin.setRange(-10.0, 10.0)
        self.end_read_spin.setDecimals(3)
        self.end_read_spin.setValue(0.2)
        endurance_layout.addRow("Read Voltage (V)", self.end_read_spin)

        endurance_button_row = QtWidgets.QHBoxLayout()
        self.manual_endurance_start_btn = QtWidgets.QPushButton("Start Endurance")
        self.manual_endurance_start_btn.clicked.connect(self._start_manual_endurance)
        endurance_button_row.addWidget(self.manual_endurance_start_btn)
        endurance_layout.addRow(endurance_button_row)

        retention_box = QtWidgets.QGroupBox("Retention")
        retention_layout = QtWidgets.QFormLayout(retention_box)
        retention_layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.ret_set_spin = QtWidgets.QDoubleSpinBox()
        self.ret_set_spin.setRange(-10.0, 10.0)
        self.ret_set_spin.setDecimals(3)
        self.ret_set_spin.setValue(1.5)
        retention_layout.addRow("SET Voltage (V)", self.ret_set_spin)

        self.ret_set_time_spin = QtWidgets.QDoubleSpinBox()
        self.ret_set_time_spin.setRange(0.01, 100000.0)
        self.ret_set_time_spin.setDecimals(2)
        self.ret_set_time_spin.setSuffix(" ms")
        self.ret_set_time_spin.setValue(10.0)
        retention_layout.addRow("SET Time", self.ret_set_time_spin)

        self.ret_read_spin = QtWidgets.QDoubleSpinBox()
        self.ret_read_spin.setRange(-10.0, 10.0)
        self.ret_read_spin.setDecimals(3)
        self.ret_read_spin.setValue(0.2)
        retention_layout.addRow("Read Voltage (V)", self.ret_read_spin)

        self.ret_interval_spin = QtWidgets.QDoubleSpinBox()
        self.ret_interval_spin.setRange(0.01, 100000.0)
        self.ret_interval_spin.setDecimals(3)
        self.ret_interval_spin.setValue(10.0)
        self.ret_interval_spin.setSuffix(" s")
        retention_layout.addRow("Sample Every", self.ret_interval_spin)

        self.ret_points_spin = QtWidgets.QSpinBox()
        self.ret_points_spin.setRange(1, 100000)
        self.ret_points_spin.setValue(30)
        retention_layout.addRow("# Points", self.ret_points_spin)

        self.ret_estimate_label = QtWidgets.QLabel("Total ~300 s")
        retention_layout.addRow("Estimate", self.ret_estimate_label)

        self.manual_retention_start_btn = QtWidgets.QPushButton("Start Retention")
        self.manual_retention_start_btn.clicked.connect(self._start_manual_retention)
        retention_layout.addRow(self.manual_retention_start_btn)

        layout.addWidget(endurance_box, 0, 0, 1, 1)
        layout.addWidget(retention_box, 0, 1, 1, 1)

        control_row = QtWidgets.QHBoxLayout()
        self.manual_stop_btn = QtWidgets.QPushButton("Stop Manual Tests")
        self.manual_stop_btn.clicked.connect(self._stop_manual_tests)
        control_row.addWidget(self.manual_stop_btn)

        self.manual_status_label = QtWidgets.QLabel("Status: Idle")
        control_row.addWidget(self.manual_status_label, 1)
        layout.addLayout(control_row, 1, 0, 1, 2)

        return group

    def _create_plot_panel(self) -> QtWidgets.QWidget:
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setSpacing(8)

        self.plot_tabs = QtWidgets.QTabWidget()
        self.plot_tabs.setDocumentMode(True)
        layout.addWidget(self.plot_tabs, 1)

        self._init_plot_canvases()
        controls = QtWidgets.QHBoxLayout()
        controls.addStretch(1)
        clear_btn = QtWidgets.QPushButton("Clear Sweep History")
        clear_btn.clicked.connect(self._clear_sweep_history)
        controls.addWidget(clear_btn)
        layout.addLayout(controls)
        return container

    def _init_plot_canvases(self) -> None:
        # IV curve (linear scale)
        iv_figure = Figure(figsize=(5, 4))
        iv_figure.set_tight_layout(True)
        self.iv_canvas = FigureCanvasQTAgg(iv_figure)
        self.iv_canvas.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        self.iv_ax = iv_figure.add_subplot(111)
        self.iv_ax.set_title("IV Sweep")
        self.iv_ax.set_xlabel("Voltage (V)")
        self.iv_ax.set_ylabel("Current (A)")
        self.iv_ax.grid(True, alpha=0.2)
        (self._plot_line,) = self.iv_ax.plot([], [], color="#1f77b4")
        self.plot_tabs.addTab(self.iv_canvas, "IV")

        # Log plot (absolute current)
        log_figure = Figure(figsize=(5, 4))
        log_figure.set_tight_layout(True)
        self.log_canvas = FigureCanvasQTAgg(log_figure)
        self.log_canvas.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        self.log_ax = log_figure.add_subplot(111)
        self.log_ax.set_title("Log |Current|")
        self.log_ax.set_xlabel("Voltage (V)")
        self.log_ax.set_ylabel("|Current| (A)")
        self.log_ax.set_yscale("log")
        self.log_ax.grid(True, alpha=0.2, which="both")
        (self._plot_line_log,) = self.log_ax.plot([], [], color="#ff7f0e")
        self.plot_tabs.addTab(self.log_canvas, "Log IV")

        # V/I plot
        vi_figure = Figure(figsize=(5, 4))
        vi_figure.set_tight_layout(True)
        self.vi_canvas = FigureCanvasQTAgg(vi_figure)
        self.vi_canvas.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        self.vi_ax = vi_figure.add_subplot(111)
        self.vi_ax.set_title("Voltage vs Current")
        self.vi_ax.set_xlabel("Current (A)")
        self.vi_ax.set_ylabel("Voltage (V)")
        self.vi_ax.grid(True, alpha=0.2)
        (self._plot_vi_line,) = self.vi_ax.plot([], [], color="#9467bd")
        self.plot_tabs.addTab(self.vi_canvas, "V/I")

        # Log-Log plot
        loglog_figure = Figure(figsize=(5, 4))
        loglog_figure.set_tight_layout(True)
        self.loglog_canvas = FigureCanvasQTAgg(loglog_figure)
        self.loglog_canvas.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        self.loglog_ax = loglog_figure.add_subplot(111)
        self.loglog_ax.set_title("Log I / Log V")
        self.loglog_ax.set_xlabel("Voltage (V)")
        self.loglog_ax.set_ylabel("|Current| (A)")
        self.loglog_ax.set_xscale("log")
        self.loglog_ax.set_yscale("log")
        self.loglog_ax.grid(True, alpha=0.2)
        (self._plot_loglog_line,) = self.loglog_ax.plot([], [], color="#8c564b")
        self.plot_tabs.addTab(self.loglog_canvas, "Log-Log")

        # Current vs Time
        current_time_figure = Figure(figsize=(5, 4))
        current_time_figure.set_tight_layout(True)
        self.current_time_canvas = FigureCanvasQTAgg(current_time_figure)
        self.current_time_canvas.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        self.current_time_ax = current_time_figure.add_subplot(111)
        self.current_time_ax.set_title("Current vs Time")
        self.current_time_ax.set_xlabel("Time (s)")
        self.current_time_ax.set_ylabel("|Current| (A)")
        self.current_time_ax.grid(True, alpha=0.2)
        (self._plot_current_time_line,) = self.current_time_ax.plot([], [], color="#17becf")
        self.plot_tabs.addTab(self.current_time_canvas, "I(t)")

        # Resistance vs Time
        resistance_time_figure = Figure(figsize=(5, 4))
        resistance_time_figure.set_tight_layout(True)
        self.resistance_time_canvas = FigureCanvasQTAgg(resistance_time_figure)
        self.resistance_time_canvas.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        self.resistance_time_ax = resistance_time_figure.add_subplot(111)
        self.resistance_time_ax.set_title("Resistance vs Time")
        self.resistance_time_ax.set_xlabel("Time (s)")
        self.resistance_time_ax.set_ylabel("Resistance (Ω)")
        self.resistance_time_ax.grid(True, alpha=0.2)
        (self._plot_resistance_time_line,) = self.resistance_time_ax.plot([], [], color="#bcbd22")
        self.plot_tabs.addTab(self.resistance_time_canvas, "R(t)")

        # All sweeps (linear)
        self.all_sweeps_canvas = FigureCanvasQTAgg(Figure(figsize=(5, 4)))
        self.all_sweeps_canvas.figure.set_tight_layout(True)
        self.all_sweeps_canvas.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        self.all_sweeps_ax = self.all_sweeps_canvas.figure.add_subplot(111)
        self.all_sweeps_ax.set_title("All Sweeps (Linear)")
        self.all_sweeps_ax.set_xlabel("Voltage (V)")
        self.all_sweeps_ax.set_ylabel("Current (A)")
        self.all_sweeps_ax.grid(True, alpha=0.2)
        self.plot_tabs.addTab(self.all_sweeps_canvas, "All Sweeps")

        # All sweeps (log)
        self.all_sweeps_log_canvas = FigureCanvasQTAgg(Figure(figsize=(5, 4)))
        self.all_sweeps_log_canvas.figure.set_tight_layout(True)
        self.all_sweeps_log_canvas.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        self.all_sweeps_log_ax = self.all_sweeps_log_canvas.figure.add_subplot(111)
        self.all_sweeps_log_ax.set_title("All Sweeps (Log |I|)")
        self.all_sweeps_log_ax.set_xlabel("Voltage (V)")
        self.all_sweeps_log_ax.set_ylabel("|Current| (A)")
        self.all_sweeps_log_ax.set_yscale("log")
        self.all_sweeps_log_ax.grid(True, alpha=0.2, which="both")
        self.plot_tabs.addTab(self.all_sweeps_log_canvas, "All Sweeps Log")

        # Endurance plot
        endurance_figure = Figure(figsize=(5, 4))
        endurance_figure.set_tight_layout(True)
        self.endurance_canvas = FigureCanvasQTAgg(endurance_figure)
        self.endurance_canvas.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        self.endurance_ax = endurance_figure.add_subplot(111)
        self.endurance_ax.set_title("Manual Endurance (ON/OFF)")
        self.endurance_ax.set_xlabel("Cycle")
        self.endurance_ax.set_ylabel("ON/OFF Ratio")
        self.endurance_ax.grid(True, alpha=0.2)
        self.plot_tabs.addTab(self.endurance_canvas, "Endurance")

        # Retention plot
        retention_figure = Figure(figsize=(5, 4))
        retention_figure.set_tight_layout(True)
        self.retention_canvas = FigureCanvasQTAgg(retention_figure)
        self.retention_canvas.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        self.retention_ax = retention_figure.add_subplot(111)
        self.retention_ax.set_title("Manual Retention")
        self.retention_ax.set_xlabel("Time (s)")
        self.retention_ax.set_ylabel("|Current| (A)")
        self.retention_ax.set_xscale("log")
        self.retention_ax.set_yscale("log")
        self.retention_ax.grid(True, alpha=0.2)
        self.plot_tabs.addTab(self.retention_canvas, "Retention")

    def _reset_plots(self) -> None:
        self._plot_voltage.clear()
        self._plot_current.clear()
        self._plot_time.clear()
        if self._plot_line is not None:
            self._plot_line.set_data([], [])
        if self._plot_line_log is not None:
            self._plot_line_log.set_data([], [])
        if self._plot_vi_line is not None:
            self._plot_vi_line.set_data([], [])
        if self._plot_loglog_line is not None:
            self._plot_loglog_line.set_data([], [])
        if self._plot_current_time_line is not None:
            self._plot_current_time_line.set_data([], [])
        if self._plot_resistance_time_line is not None:
            self._plot_resistance_time_line.set_data([], [])
        if self.iv_ax is not None:
            self.iv_ax.relim()
            self.iv_ax.autoscale_view()
        if self.log_ax is not None:
            self.log_ax.relim()
            self.log_ax.autoscale_view()
        if self.vi_ax is not None:
            self.vi_ax.relim()
            self.vi_ax.autoscale_view()
        if self.loglog_ax is not None:
            self.loglog_ax.relim()
            self.loglog_ax.autoscale_view()
        if self.current_time_ax is not None:
            self.current_time_ax.relim()
            self.current_time_ax.autoscale_view()
        if self.resistance_time_ax is not None:
            self.resistance_time_ax.relim()
            self.resistance_time_ax.autoscale_view()
        if self.iv_canvas is not None:
            self.iv_canvas.draw_idle()
        if self.log_canvas is not None:
            self.log_canvas.draw_idle()
        if self.vi_canvas is not None:
            self.vi_canvas.draw_idle()
        if self.loglog_canvas is not None:
            self.loglog_canvas.draw_idle()
        if self.current_time_canvas is not None:
            self.current_time_canvas.draw_idle()
        if self.resistance_time_canvas is not None:
            self.resistance_time_canvas.draw_idle()
        self._update_all_sweeps_plots()

    def _refresh_plots(self, force: bool = False) -> None:
        if not self._plot_voltage:
            return
        if not force and (self._point_counter % 5):
            return

        if self._plot_line is not None:
            self._plot_line.set_data(self._plot_voltage, self._plot_current)
        if self.iv_ax is not None:
            self.iv_ax.relim()
            self.iv_ax.autoscale_view()

        if self._plot_line_log is not None:
            abs_current = [max(abs(i), 1e-12) for i in self._plot_current]
            self._plot_line_log.set_data(self._plot_voltage, abs_current)
        if self.log_ax is not None:
            self.log_ax.relim()
            self.log_ax.autoscale_view()

        if self.iv_canvas is not None:
            self.iv_canvas.draw_idle()
        if self.log_canvas is not None:
            self.log_canvas.draw_idle()
        if self._plot_vi_line is not None:
            currents = self._plot_current
            voltages = self._plot_voltage
            self._plot_vi_line.set_data(currents, voltages)
        if self.vi_ax is not None:
            self.vi_ax.relim()
            self.vi_ax.autoscale_view()
        if self.vi_canvas is not None:
            self.vi_canvas.draw_idle()
        if self._plot_loglog_line is not None:
            abs_current = [max(abs(i), 1e-12) for i in self._plot_current]
            abs_voltage = [max(abs(v), 1e-12) for v in self._plot_voltage]
            self._plot_loglog_line.set_data(abs_voltage, abs_current)
        if self.loglog_ax is not None:
            self.loglog_ax.relim()
            self.loglog_ax.autoscale_view()
        if self.loglog_canvas is not None:
            self.loglog_canvas.draw_idle()
        if self._plot_current_time_line is not None and self._plot_time:
            abs_current = [max(abs(i), 1e-12) for i in self._plot_current]
            self._plot_current_time_line.set_data(self._plot_time, abs_current)
        if self.current_time_ax is not None:
            self.current_time_ax.relim()
            self.current_time_ax.autoscale_view()
        if self.current_time_canvas is not None:
            self.current_time_canvas.draw_idle()
        if self._plot_resistance_time_line is not None and self._plot_time:
            resistances = []
            for v, i in zip(self._plot_voltage, self._plot_current):
                if abs(i) < 1e-12:
                    resistances.append(float("nan"))
                else:
                    resistances.append(v / i)
            self._plot_resistance_time_line.set_data(self._plot_time, resistances)
        if self.resistance_time_ax is not None:
            self.resistance_time_ax.relim()
            self.resistance_time_ax.autoscale_view()
        if self.resistance_time_canvas is not None:
            self.resistance_time_canvas.draw_idle()
        self._update_all_sweeps_plots()

    # ------------------------------------------------------------------
    # Event handlers / adapters (stubs for now)
    # ------------------------------------------------------------------
    def append_status(self, message: str) -> None:
        """Append a line to the status log and mirror to the status bar."""
        self.status_log.appendPlainText(message)
        self._status_bar.showMessage(message, 5000)

    # ---- Measurement actions -------------------------------------------------
    def _start_measurement(self) -> None:
        if not self.keithley:
            QtWidgets.QMessageBox.warning(
                self,
                "SMU Not Connected",
                "Connect the SMU before starting a measurement.",
            )
            return

        if self._measurement_active:
            QtWidgets.QMessageBox.information(
                self,
                "Measurement Running",
                "A measurement is already running. Please wait for it to finish.",
            )
            return

        config = self._collect_measurement_config()
        measurement_type = config["type"]
        self.last_measurement_config = config
        self.stop_measurement_flag = False
        icc = float(config.get("compliance", self._icc_default))
        self._active_result_metadata = {
            "measurement_type": measurement_type,
            "parameters": self._make_json_safe(config),
        }

        if measurement_type == "DC Triangle IV":
            dc_cfg = config.get("dc", {})
            start_v = dc_cfg.get("start_voltage", 0.0)
            stop_v = dc_cfg.get("stop_voltage", 0.0)
            step_v = max(dc_cfg.get("step_voltage", 0.1), 1e-9)
            neg_stop_v = dc_cfg.get("neg_stop_voltage")
            sweep_mode = dc_cfg.get("sweep_mode", VoltageRangeMode.FIXED_STEP)
            sweep_type = dc_cfg.get("sweep_type", "FS")
            sweep_rate = dc_cfg.get("sweep_rate")
            total_time = dc_cfg.get("total_time")
            num_steps = dc_cfg.get("num_steps")
            if num_steps is not None and num_steps <= 0:
                num_steps = None
            step_delay = max(config.get("step_delay", self._step_delay_default), 0.0)

            voltage_range = self.measurement_service.compute_voltage_range(
                start_v=start_v,
                stop_v=stop_v,
                step_v=step_v,
                sweep_type=sweep_type,
                mode=sweep_mode,
                neg_stop_v=neg_stop_v,
                sweep_rate_v_per_s=sweep_rate,
                voltage_time_s=total_time,
                step_delay_s=step_delay,
                num_steps=num_steps,
            )
            if not voltage_range:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Invalid Sweep",
                    "The computed voltage range is empty. Check the sweep parameters.",
                )
                return

            self.append_status(
                f"Computed sweep with {len(voltage_range)} points "
                f"from {start_v:.3f} V to {stop_v:.3f} V (step {step_v:.3f} V) "
                f"({sweep_type} / {sweep_mode})."
            )
            sweeps = int(config.get("sweeps", 1))
            self._active_result_metadata["x_axis_label"] = "Voltage (V)"
            self._active_result_metadata.setdefault("y_axis_label", "Current (A)")
            self._begin_measurement(voltage_range, icc, sweeps, step_delay)
            return

        if measurement_type in self._pulsed_modes:
            self._start_pulsed_measurement(measurement_type, config, icc)
            return

        if measurement_type in self._advanced_modes:
            self._start_advanced_measurement(measurement_type, config, icc)
            return

        self._active_result_metadata = None
        message = (
            f"'{measurement_type}' is not yet wired into the Qt measurement runner. "
            "The configuration panel is available for review, but execution remains pending."
        )
        QtWidgets.QMessageBox.information(self, "Mode Not Implemented", message)
        self.append_status(message)

    def _start_pulsed_measurement(self, measurement_type: str, config: Dict[str, Any], icc: float) -> None:
        if not self.keithley:
            QtWidgets.QMessageBox.warning(
                self,
                "SMU Not Connected",
                "Connect the SMU before starting a pulsed measurement.",
            )
            return

        led_cfg = config.get("led", {})
        self._led_restore_required = self._prepare_led_for_measurement(led_cfg)
        metadata = {
            "measurement_type": measurement_type,
            "x_axis_label": "Pulse Voltage (V)",
            "y_axis_label": "Current (A)",
            "led": self._make_json_safe(led_cfg),
        }
        self._active_result_metadata = metadata

        def task(should_stop: Callable[[], bool]) -> Tuple[Iterable[float], Iterable[float], Iterable[float]]:
            if measurement_type in ("SMU_AND_PMU Pulsed IV <1.5v", "SMU_AND_PMU Pulsed IV >1.5v"):
                params = dict(config.get("pulsed", {}) or {})
                metadata["parameters"] = self._make_json_safe(params)
                return self._compute_pulsed_iv(params, icc, should_stop)
            if measurement_type == "SMU_AND_PMU Fast Pulses":
                metadata["x_axis_label"] = "Pulse Voltage (V)"
                params = dict(config.get("fast_pulses", {}) or {})
                metadata["parameters"] = self._make_json_safe(params)
                return self._compute_fast_pulses(params, icc, should_stop, led_cfg)
            if measurement_type == "SMU_AND_PMU Fast Hold":
                metadata["x_axis_label"] = "Time (s)"
                params = dict(config.get("fast_hold", {}) or {})
                metadata["parameters"] = self._make_json_safe(params)
                return self._compute_fast_hold(params, icc, should_stop)
            raise ValueError(f"Unsupported pulsed measurement type: {measurement_type}")

        worker = GenericMeasurementWorker(task)
        self._run_generic_worker(worker, measurement_type, f"Starting {measurement_type}...")

    def _start_advanced_measurement(self, measurement_type: str, config: Dict[str, Any], icc: float) -> None:
        if not self.keithley:
            QtWidgets.QMessageBox.warning(
                self,
                "SMU Not Connected",
                "Connect the SMU before starting this measurement.",
            )
            return

        led_cfg = config.get("led", {})
        self._led_restore_required = self._prepare_led_for_measurement(led_cfg)
        metadata = {
            "measurement_type": measurement_type,
            "y_axis_label": "Current (A)",
            "led": self._make_json_safe(led_cfg),
        }

        def task(should_stop: Callable[[], bool]) -> Tuple[Iterable[float], Iterable[float], Iterable[float]]:
            if measurement_type == "ISPP":
                metadata["x_axis_label"] = "Pulse Voltage (V)"
                params = dict(config.get("ispp", {}) or {})
                metadata["parameters"] = self._make_json_safe(params)
                return self._compute_ispp(params, icc, should_stop)
            if measurement_type == "Pulse Width Sweep":
                metadata["x_axis_label"] = "Pulse Width (ms)"
                params = dict(config.get("pulse_width_sweep", {}) or {})
                metadata["parameters"] = self._make_json_safe(params)
                return self._compute_pulse_width_sweep(params, icc, should_stop)
            if measurement_type == "Threshold Search":
                metadata["x_axis_label"] = "Pulse Voltage (V)"
                params = dict(config.get("threshold", {}) or {})
                metadata["parameters"] = self._make_json_safe(params)
                return self._compute_threshold_search(params, icc, should_stop)
            if measurement_type == "Transient Decay":
                metadata["x_axis_label"] = "Time (s)"
                params = dict(config.get("transient", {}) or {})
                metadata["parameters"] = self._make_json_safe(params)
                return self._compute_transient_decay(params, icc, should_stop)
            raise ValueError(f"Unsupported measurement type: {measurement_type}")

        worker = GenericMeasurementWorker(task)
        self._active_result_metadata = metadata
        self._run_generic_worker(worker, measurement_type, f"Starting {measurement_type}...")

    def _run_generic_worker(
        self,
        worker: GenericMeasurementWorker,
        measurement_label: str,
        start_message: str,
    ) -> None:
        if not (self.use_custom_save_var.get() and self.custom_save_location):
            self.check_for_sample_name()
        self._reset_plots_for_new_run()
        self._point_counter = 0

        thread = QtCore.QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._handle_generic_measurement_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        self._current_worker = worker
        self._current_thread = thread
        self._active_measurement_label = measurement_label
        self._set_measurement_active(True)
        self.append_status(start_message)
        thread.start()

    def _handle_generic_measurement_finished(
        self,
        voltage: List[float],
        current: List[float],
        timestamps: List[float],
        error: str,
    ) -> None:
        label = self._active_measurement_label or "Measurement"
        result_meta = self._active_result_metadata or {}
        measurement_type = result_meta.get("measurement_type")
        if error:
            QtWidgets.QMessageBox.critical(
                self,
                "Measurement Error",
                f"{label} failed:\n{error}",
            )
            self.append_status(f"{label} failed: {error}")
        else:
            self.append_status(f"{label} complete with {len(voltage)} samples collected.")
            self._plot_voltage = list(voltage)
            self._plot_current = list(current)
            self._plot_time = list(timestamps)
            self.v_arr_disp = list(voltage)
            self.c_arr_disp = list(current)
            self.t_arr_disp = list(timestamps)
            self._refresh_plots(force=True)
            if measurement_type == "DC Triangle IV":
                self._record_sweep_history(voltage, current)
            self._store_measurement_result(
                voltage,
                current,
                timestamps,
                result_meta,
            )

        if self._led_restore_required and not self._pre_measurement_led_state:
            try:
                self._set_led_state(False)
            except Exception:
                pass

        self._set_measurement_active(False)
        self._current_worker = None
        self._current_thread = None
        self._active_measurement_label = None
        self._led_restore_required = False
        self._active_result_metadata = None
        self.stop_measurement_flag = False

    def _compute_pulsed_iv(
        self,
        params: Dict[str, Any],
        icc: float,
        should_stop: Callable[[], bool],
    ) -> Tuple[List[float], List[float], List[float]]:
        if not params:
            raise ValueError("Missing pulsed IV parameters.")

        start_v = float(params.get("start_voltage", 0.0))
        stop_v = float(params.get("stop_voltage", 0.0))
        step_v = params.get("step_voltage")
        if step_v is None or abs(float(step_v)) < 1e-9:
            step_v = None
        else:
            step_v = float(step_v)
        num_steps = params.get("num_steps")
        if num_steps is not None and int(num_steps) <= 0:
            num_steps = None
        else:
            num_steps = int(num_steps) if num_steps is not None else None
        pulse_ms = max(self._min_pulse_width_ms(), float(params.get("pulse_width_ms", 1.0)))
        base_v = float(params.get("base_voltage", 0.2))
        inter_delay = float(params.get("inter_delay_s", 0.0))

        self._prepare_for_pulses(icc)
        try:
            v_arr, i_arr, t_arr = self.measurement_service.run_pulsed_iv_sweep(
                keithley=self.keithley,
                start_v=start_v,
                stop_v=stop_v,
                step_v=step_v,
                num_steps=num_steps,
                pulse_width_ms=pulse_ms,
                vbase=base_v,
                inter_step_delay_s=inter_delay,
                icc=icc,
                smu_type=self.smu_type,
                should_stop=lambda: self.stop_measurement_flag or should_stop(),
                on_point=None,
                validate_timing=True,
                manage_session=False,
            )
        finally:
            self._finish_pulses(icc)
        return v_arr, i_arr, t_arr

    def _compute_fast_pulses(
        self,
        params: Dict[str, Any],
        icc: float,
        should_stop: Callable[[], bool],
        led_cfg: Dict[str, Any],
    ) -> Tuple[List[float], List[float], List[float]]:
        if not params:
            raise ValueError("Missing fast pulse parameters.")

        pulse_v = float(params.get("pulse_voltage", 0.2))
        pulse_ms = max(self._min_pulse_width_ms(), float(params.get("pulse_width_ms", 1.0)))
        pulse_count = max(1, int(params.get("pulse_count", 1)))
        inter_delay = 0.0 if params.get("max_speed") else float(params.get("inter_delay_s", 0.0))
        base_v = float(params.get("base_voltage", 0.2))

        led_enabled = bool(led_cfg.get("enabled"))
        led_power = float(led_cfg.get("power", 0.0))
        sequence = led_cfg.get("sequence") or None

        return self.measurement_service.run_pulse_measurement(
            keithley=self.keithley,
            pulse_voltage=pulse_v,
            pulse_width_ms=pulse_ms,
            num_pulses=pulse_count,
            read_voltage=base_v,
            inter_pulse_delay_s=inter_delay,
            icc=icc,
            smu_type=self.smu_type,
            psu=self.psu,
            led=led_enabled,
            power=led_power,
            optical=self.optical_controller,
            sequence=sequence,
            should_stop=lambda: self.stop_measurement_flag or should_stop(),
            on_point=None,
            validate_timing=True,
        )

    def _compute_fast_hold(
        self,
        params: Dict[str, Any],
        icc: float,
        should_stop: Callable[[], bool],
    ) -> Tuple[List[float], List[float], List[float]]:
        if not params:
            raise ValueError("Missing fast hold parameters.")

        hold_v = float(params.get("hold_voltage", 0.2))
        duration = float(params.get("hold_duration_s", 5.0))
        sample_dt = max(0.0001, float(params.get("sample_interval_s", 0.01)))

        return self.measurement_service.run_dc_capture(
            keithley=self.keithley,
            voltage_v=hold_v,
            capture_time_s=duration,
            sample_dt_s=sample_dt,
            icc=icc,
            on_point=None,
            should_stop=lambda: self.stop_measurement_flag or should_stop(),
        )

    def _compute_ispp(
        self,
        params: Dict[str, Any],
        icc: float,
        should_stop: Callable[[], bool],
    ) -> Tuple[List[float], List[float], List[float]]:
        if not params:
            raise ValueError("Missing ISPP parameters.")

        start_v = float(params.get("start_voltage", 0.0))
        stop_v = float(params.get("stop_voltage", 0.0))
        step_v = float(params.get("step_voltage", 0.1))
        if step_v == 0.0:
            step_v = 0.1 if stop_v >= start_v else -0.1
        pulse_ms = params.get("pulse_width_ms")
        vbase = float(params.get("base_voltage", 0.2))
        target = float(params.get("target_current", 1e-5))
        inter_delay = float(params.get("inter_delay_s", 0.0))

        amps, currents, times = self.measurement_service.run_ispp(
            keithley=self.keithley,
            start_v=start_v,
            stop_v=stop_v,
            step_v=step_v,
            vbase=vbase,
            pulse_width_ms=pulse_ms,
            target_current_a=target,
            inter_step_delay_s=inter_delay,
            icc=icc,
            smu_type=self.smu_type,
            should_stop=lambda: self.stop_measurement_flag or should_stop(),
            on_point=None,
            validate_timing=True,
        )
        return amps, currents, times

    def _compute_pulse_width_sweep(
        self,
        params: Dict[str, Any],
        icc: float,
        should_stop: Callable[[], bool],
    ) -> Tuple[List[float], List[float], List[float]]:
        if not params:
            raise ValueError("Missing pulse-width sweep parameters.")

        amplitude = float(params.get("amplitude", 0.2))
        widths = params.get("widths_ms") or []
        if isinstance(widths, str):
            widths = [float(token.strip()) for token in widths.split(",") if token.strip()]
        widths = [float(w) for w in widths]
        if not widths:
            raise ValueError("Pulse width sweep requires at least one width entry.")
        base_v = float(params.get("base_voltage", 0.2))
        inter_delay = float(params.get("inter_delay_s", 0.0))

        widths_out, currents, times = self.measurement_service.run_pulse_width_sweep(
            keithley=self.keithley,
            amplitude_v=amplitude,
            widths_ms=widths,
            vbase=base_v,
            icc=icc,
            smu_type=self.smu_type,
            inter_step_delay_s=inter_delay,
            should_stop=lambda: self.stop_measurement_flag or should_stop(),
            on_point=None,
            validate_timing=True,
        )
        return widths_out, currents, times

    def _compute_threshold_search(
        self,
        params: Dict[str, Any],
        icc: float,
        should_stop: Callable[[], bool],
    ) -> Tuple[List[float], List[float], List[float]]:
        if not params:
            raise ValueError("Missing threshold search parameters.")

        v_low = float(params.get("voltage_low", 0.0))
        v_high = float(params.get("voltage_high", 1.0))
        pulse_ms = params.get("pulse_width_ms")
        vbase = float(params.get("base_voltage", 0.2))
        target = float(params.get("target_current", 1e-5))
        max_iters = int(params.get("max_iterations", 12))

        voltages, currents, times = self.measurement_service.run_threshold_search(
            keithley=self.keithley,
            v_low=v_low,
            v_high=v_high,
            vbase=vbase,
            pulse_width_ms=pulse_ms,
            target_current_a=target,
            max_iters=max_iters,
            icc=icc,
            smu_type=self.smu_type,
            should_stop=lambda: self.stop_measurement_flag or should_stop(),
            on_point=None,
            validate_timing=True,
        )
        return voltages, currents, times

    def _compute_transient_decay(
        self,
        params: Dict[str, Any],
        icc: float,
        should_stop: Callable[[], bool],
    ) -> Tuple[List[float], List[float], List[float]]:
        if not params:
            raise ValueError("Missing transient decay parameters.")

        pulse_voltage = float(params.get("pulse_voltage", 0.2))
        pulse_width_ms = float(params.get("pulse_width_ms", 1.0))
        read_voltage = float(params.get("read_voltage", 0.2))
        capture_time = float(params.get("capture_time_s", 1.0))
        sample_dt = float(params.get("sample_interval_s", 0.001))

        t_arr, i_arr, v_arr = self.measurement_service.run_transient_decay(
            keithley=self.keithley,
            pulse_voltage=pulse_voltage,
            pulse_width_ms=pulse_width_ms,
            read_voltage=read_voltage,
            capture_time_s=capture_time,
            sample_dt_s=sample_dt,
            icc=icc,
            smu_type=self.smu_type,
            should_stop=lambda: self.stop_measurement_flag or should_stop(),
            on_point=None,
        )
        # For plotting, use time on the x-axis and keep the V trace in metadata.
        self._active_result_metadata = (self._active_result_metadata or {}).copy()
        extra = self._active_result_metadata.setdefault("extra_series", {})
        extra["read_voltage_trace"] = list(v_arr)
        return t_arr, i_arr, t_arr

    def _prepare_for_pulses(self, icc: float) -> None:
        try:
            if hasattr(self.keithley, "prepare_for_pulses"):
                self.keithley.prepare_for_pulses(
                    Icc=icc,
                    v_range=20.0,
                    ovp=22.0,
                    use_remote_sense=False,
                    autozero_off=True,
                )
        except Exception:
            pass

    def _finish_pulses(self, icc: float) -> None:
        try:
            if hasattr(self.keithley, "finish_pulses"):
                self.keithley.finish_pulses(Icc=icc, restore_autozero=True)
        except Exception:
            pass

    def _min_pulse_width_ms(self) -> float:
        try:
            limits = self.measurement_service.get_smu_limits(self.smu_type)
            return float(limits.get("min_pulse_width_ms", 1.0))
        except Exception:
            return 1.0

    def _start_sequential(self) -> None:
        if not self.keithley:
            QtWidgets.QMessageBox.warning(
                self,
                "SMU Not Connected",
                "Connect the SMU before starting a sequential run.",
            )
            return

        # Sync UI values into compatibility wrappers expected by the runner
        self.Sequential_measurement_var.set(self.seq_mode_combo.currentText())
        self.sequential_number_of_sweeps.set(self.seq_count_spin.value())
        self.sq_voltage.set(self.seq_voltage_spin.value())
        self.sq_time_delay.set(self.seq_delay_spin.value())
        self.measurement_duration_var.set(self.seq_duration_spin.value())
        self.record_temp_var.set(self.seq_record_temp.isChecked())
        self.single_device_flag = self.seq_single_device.isChecked()
        self.stop_measurement_flag = False

        current_device = self.seq_device_combo.currentText()
        if current_device:
            self.current_device = current_device

        self.sequential_runner = SequentialMeasurementRunner(self)
        self.set_sequential_state("running")
        self.append_status("Sequential measurement starting...")
        self.sequential_runner.start()

    def _stop_sequential(self) -> None:
        self.stop_measurement_flag = True
        if self.sequential_runner:
            self.append_status("Stop requested for sequential run.")
            try:
                self.sequential_runner.request_stop()
            except Exception:
                pass
        else:
            self.append_status("No sequential run is active.")

    # ---- Connection handlers -------------------------------------------------
    def _handle_connect_smu(self) -> None:
        address = self.keithley_address_edit.text().strip() or self.keithley_address
        self.keithley_address = address
        self.keithley_address_var.set(address)
        self.append_status(f"Connecting to SMU at {address} ({self.smu_type}) ...")
        try:
            self.keithley = IVControllerManager(self.smu_type, address)
            try:
                self.connected = bool(self.keithley.is_connected())
            except Exception:
                self.connected = True
            if self.connected:
                self.connection_status.setText("Status: Connected to SMU")
                if hasattr(self.keithley, "beep"):
                    self.keithley.beep(4000, 0.2)
                    time.sleep(0.1)
                    self.keithley.beep(5000, 0.2)
            self.append_status("SMU connection successful.")
        except Exception as exc:
            self.keithley = None
            self.connected = False
            self.connection_status.setText("Status: SMU connection failed")
            QtWidgets.QMessageBox.critical(
                self,
                "Connection Error",
                f"Could not connect to SMU:\n{exc}",
            )

    def _handle_connect_psu(self) -> None:
        address = self.psu_address_edit.text().strip() or self.psu_visa_address
        self.psu_visa_address = address
        self.append_status(f"Connecting to PSU at {address} ...")
        try:
            self.psu = Keithley2220_Powersupply(address)
            self.psu_connected = True
            if self.keithley and hasattr(self.keithley, "beep"):
                self.keithley.beep(5000, 0.2)
            self.append_status("PSU connection successful.")
        except Exception as exc:
            self.psu = None
            self.psu_connected = False
            QtWidgets.QMessageBox.critical(
                self,
                "Connection Error",
                f"Could not connect to PSU:\n{exc}",
            )

    def _handle_connect_temp(self) -> None:
        address = self.temp_address_edit.text().strip() or self.temp_controller_address
        self.temp_controller_address = address
        self.append_status(f"Connecting to temperature controller at {address} ...")
        try:
            self.itc = OxfordITC4(port=address)
            self.itc_connected = True
            if self.keithley and hasattr(self.keithley, "beep"):
                self.keithley.beep(7000, 0.2)
            self.append_status("Temperature controller connection successful.")
        except Exception as exc:
            self.itc = None
            self.itc_connected = False
            QtWidgets.QMessageBox.critical(
                self,
                "Connection Error",
                f"Could not connect to temperature controller:\n{exc}",
            )

    # ---- System preset handling ----------------------------------------------
    def _on_system_combo_changed(self, name: str) -> None:
        if not name or name == "No systems available":
            return
        self._apply_system_config(name)

    def _apply_system_config(self, name: str, announce: bool = True) -> None:
        config = self.system_configs.get(name)
        if not config:
            return

        self._current_system_name = name

        # Update SMU type
        smu_type = config.get("SMU Type") or config.get("SMU_type") or config.get("smu_type")
        if smu_type:
            if (
                hasattr(self, "smu_type_combo")
                and self.smu_type_combo.findText(smu_type, QtCore.Qt.MatchFlag.MatchExactly) == -1
            ):
                self.smu_type_combo.addItem(smu_type)
            if hasattr(self, "smu_type_combo"):
                self.smu_type_combo.blockSignals(True)
                self.smu_type_combo.setCurrentText(smu_type)
                self.smu_type_combo.blockSignals(False)
            self._update_smu_type(smu_type)

        # Update instrument addresses
        iv_address = config.get("SMU_address") or config.get("smu_address")
        if iv_address:
            self.keithley_address = iv_address
            if hasattr(self, "keithley_address_edit"):
                self.keithley_address_edit.setText(iv_address)
            self.keithley_address_var.set(iv_address)

        psu_address = config.get("psu_address")
        if psu_address is not None:
            self.psu_visa_address = psu_address
            if hasattr(self, "psu_address_edit"):
                self.psu_address_edit.setText(psu_address)

        temp_address = config.get("temp_address")
        if temp_address is not None:
            self.temp_controller_address = temp_address
            if hasattr(self, "temp_address_edit"):
                self.temp_address_edit.setText(temp_address)

        self.temp_controller_type = config.get("temp_controller")

        # Prepare optical controller (if defined)
        try:
            self.optical_controller = create_optical_from_system_config(config)
        except Exception:
            self.optical_controller = None

        self._update_led_controls_state(self.led_enabled)
        if announce:
            if self.optical_controller:
                self.append_status("Optical controller configured from preset.")
            else:
                self.append_status("No optical controller defined for this preset.")

        if announce:
            self.append_status(f"Loaded system preset '{name}'.")

    def _handle_measure_one_toggle(self, state: int) -> None:
        enabled = state == QtCore.Qt.CheckState.Checked.value
        self.single_device_flag = enabled
        if enabled:
            self.append_status("Single-device mode enabled.")
        else:
            self.append_status("Sequential device mode enabled (measure all selected devices).")

    def _handle_led_toggle(self, state: int) -> None:
        enabled = state == QtCore.Qt.CheckState.Checked.value
        if enabled == self.led_enabled and self.led_enabled:
            self.append_status("LED already enabled.")
            return
        self._set_led_state(enabled)

    def _apply_led_power(self) -> None:
        self.led_power_var.set(float(self.led_power_spin.value()))
        if self.led_enabled:
            self._set_led_state(True)
        else:
            self.append_status("LED power updated; enable the LED to apply.")

    def _set_led_state(self, enabled: bool) -> None:
        if enabled:
            power = float(self.led_power_spin.value())
            power = max(power, 0.0)
            self.led_power_var.set(power)

            if self.optical_controller is not None:
                try:
                    capabilities = getattr(self.optical_controller, "capabilities", {}) or {}
                    units = capabilities.get("units", "mW")
                    if hasattr(self.optical_controller, "set_level"):
                        self.optical_controller.set_level(power, units)
                    if hasattr(self.optical_controller, "set_enabled"):
                        self.optical_controller.set_enabled(True)
                    self.led_enabled = True
                    self.append_status(f"Optical source enabled at {power:.3f} {units}.")
                except Exception as exc:
                    self.append_status(f"[LED] Failed to enable optical controller: {exc}")
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Optical Control",
                        f"Failed to enable optical controller:\n{exc}",
                    )
                    self.led_toggle.blockSignals(True)
                    self.led_toggle.setChecked(False)
                    self.led_toggle.blockSignals(False)
                    self.led_enabled = False
            else:
                # Fallback to PSU-based LED control
                if self.psu is None or not self.psu_connected:
                    self._handle_connect_psu()
                if self.psu is None or not self.psu_connected:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "LED Control",
                        "No PSU available for LED control. Connect the PSU or configure an optical controller.",
                    )
                    self.led_toggle.blockSignals(True)
                    self.led_toggle.setChecked(False)
                    self.led_toggle.blockSignals(False)
                    self.led_enabled = False
                    self._update_led_controls_state(False)
                    return
                try:
                    if hasattr(self.psu, "led_on_380"):
                        self.psu.led_on_380(power)
                    elif hasattr(self.psu, "set_led_output"):
                        self.psu.set_led_output(True, power)
                    else:
                        raise RuntimeError("PSU does not support LED control.")
                    self.led_enabled = True
                    self.append_status(f"PSU LED output enabled at {power:.3f}.")
                except Exception as exc:
                    self.append_status(f"[LED] Failed to enable PSU LED output: {exc}")
                    QtWidgets.QMessageBox.warning(
                        self,
                        "LED Control",
                        f"Failed to enable LED output:\n{exc}",
                    )
                    self.led_toggle.blockSignals(True)
                    self.led_toggle.setChecked(False)
                    self.led_toggle.blockSignals(False)
                    self.led_enabled = False
        else:
            # Disable the LED/optical source
            if self.optical_controller is not None:
                try:
                    if hasattr(self.optical_controller, "set_enabled"):
                        self.optical_controller.set_enabled(False)
                    self.led_enabled = False
                    self.append_status("Optical source disabled.")
                except Exception as exc:
                    self.append_status(f"[LED] Failed to disable optical controller: {exc}")
            elif self.psu is not None and self.psu_connected:
                try:
                    if hasattr(self.psu, "led_off_380"):
                        self.psu.led_off_380()
                    elif hasattr(self.psu, "set_led_output"):
                        self.psu.set_led_output(False, 0.0)
                    self.led_enabled = False
                    self.append_status("PSU LED output disabled.")
                except Exception as exc:
                    self.append_status(f"[LED] Failed to disable PSU LED output: {exc}")
            else:
                self.led_enabled = False
                self.append_status("LED disabled.")

        self.led_toggle.blockSignals(True)
        self.led_toggle.setChecked(self.led_enabled)
        self.led_toggle.blockSignals(False)
        self._update_led_controls_state(self.led_enabled)

    def _prepare_led_for_measurement(self, led_cfg: Dict[str, Any]) -> bool:
        """Ensure LED state matches requested configuration before starting a run."""
        self._pre_measurement_led_state = self.led_enabled
        restore_needed = False
        if led_cfg.get("enabled") and not self.led_enabled:
            prev_state = self.led_enabled
            self._set_led_state(True)
            if self.led_enabled and not prev_state:
                restore_needed = True
        return restore_needed

    def _prepare_external_env(self) -> QtCore.QProcessEnvironment:
        env = QtCore.QProcessEnvironment.systemEnvironment()
        sample_name = self.sample_name_var.get() or ""
        device_label = f"{self.final_device_letter}{self.final_device_number}".strip()
        env.insert("SWITCHBOX_SAMPLE_NAME", sample_name)
        env.insert("SWITCHBOX_DEVICE_LABEL", device_label)
        env.insert("SWITCHBOX_SECTION", self.section or "")
        env.insert("SWITCHBOX_DEVICE_LIST", ",".join(self.device_list))
        if self.use_custom_save_var.get() and self.custom_save_location:
            env.insert("SWITCHBOX_CUSTOM_SAVE_PATH", str(self.custom_save_location))
        address = ""
        try:
            address = str(self.keithley_address_var.get() or "")
        except Exception:
            address = self.keithley_address
        if address:
            env.insert("SWITCHBOX_KEITHLEY_ADDRESS", address)
        return env

    def _launch_external_gui(self, name: str, script_path: Path) -> None:
        key = name.lower()
        existing = self._external_processes.get(key)
        if existing and existing.state() == QtCore.QProcess.ProcessState.Running:
            QtWidgets.QMessageBox.information(
                self,
                name,
                f"{name} window is already running.",
            )
            self.append_status(f"{name} launch skipped (already running).")
            return

        if not script_path.exists():
            QtWidgets.QMessageBox.critical(
                self,
                name,
                f"Could not find launcher script at:\n{script_path}",
            )
            self.append_status(f"{name} launch failed: missing script.")
            return

        process = QtCore.QProcess(self)
        process.setProcessEnvironment(self._prepare_external_env())
        process.setProgram(sys.executable)
        process.setArguments([str(script_path)])
        process.setProcessChannelMode(QtCore.QProcess.ProcessChannelMode.MergedChannels)
        process.finished.connect(
            lambda code, status, k=key, n=name: self._on_external_gui_finished(k, n, code, status)
        )
        process.start()

        if not process.waitForStarted(3000):
            msg = process.errorString()
            QtWidgets.QMessageBox.critical(
                self,
                name,
                f"Failed to start {name} window:\n{msg}",
            )
            self.append_status(f"{name} launch failed: {msg}")
            process.deleteLater()
            return

        self._external_processes[key] = process
        self.append_status(f"{name} window launched.")

    def _on_external_gui_finished(
        self,
        key: str,
        name: str,
        exit_code: int,
        status: QtCore.QProcess.ExitStatus,
    ) -> None:
        state = "normal exit" if status == QtCore.QProcess.ExitStatus.NormalExit else "crash"
        self.append_status(f"{name} window closed ({state}, code {exit_code}).")
        process = self._external_processes.pop(key, None)
        if process:
            process.deleteLater()

    def _update_led_controls_state(self, enabled: bool) -> None:
        if not hasattr(self, "led_power_spin"):
            return
        self.led_power_spin.setEnabled(True)
        self.led_refresh_button.setEnabled(True)
        self.led_sequence_edit.setEnabled(True)
        status = "On" if enabled else "Off"
        source = "optical" if self.optical_controller else ("PSU" if self.psu_connected else "none")
        self.led_status_label.setText(f"Status: {status} (source: {source})")

    def _toggle_custom_save(self, checked: bool) -> None:
        enabled = bool(checked)
        self.use_custom_save_var.set(enabled)
        self.custom_save_entry.setEnabled(enabled)
        self.custom_save_button.setEnabled(enabled)

        if enabled:
            if not self.custom_save_location and self._saved_custom_path:
                try:
                    self.custom_save_location = Path(self._saved_custom_path)
                except Exception:
                    self.custom_save_location = None

            if not self.custom_save_location:
                if not self._prompt_custom_save_location():
                    self.custom_save_checkbox.blockSignals(True)
                    self.custom_save_checkbox.setChecked(False)
                    self.custom_save_checkbox.blockSignals(False)
                    self.use_custom_save_var.set(False)
                    self.custom_save_entry.setEnabled(False)
                    self.custom_save_button.setEnabled(False)
                    return

            if self.custom_save_location:
                location_text = str(self.custom_save_location)
                self.custom_save_entry.setText(location_text)
                self.custom_save_entry.setToolTip(location_text)
        else:
            self.custom_save_entry.setEnabled(False)
            self.custom_save_button.setEnabled(False)

        self._save_save_location_config()

    def _prompt_custom_save_location(self) -> bool:
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Choose Custom Data Save Location",
        )
        if folder:
            path = Path(folder)
            self.custom_save_location = path
            self._saved_custom_path = folder
            self.custom_save_entry.setText(folder)
            self.custom_save_entry.setToolTip(folder)
            self.custom_save_entry.setEnabled(True)
            self.custom_save_button.setEnabled(True)
            self._save_save_location_config()
            return True
        return False

    def _browse_custom_save_location(self) -> None:
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Choose Data Save Location",
        )
        if folder:
            path = Path(folder)
            self.custom_save_location = path
            self._saved_custom_path = folder
            self.custom_save_entry.setText(folder)
            self.custom_save_entry.setToolTip(folder)
            self._save_save_location_config()

    def _apply_saved_save_location(self) -> None:
        if self._saved_custom_path:
            self.custom_save_entry.setText(self._saved_custom_path)
            self.custom_save_entry.setToolTip(self._saved_custom_path)
            try:
                self.custom_save_location = Path(self._saved_custom_path)
            except Exception:
                self.custom_save_location = None
        else:
            self.custom_save_entry.clear()
            self.custom_save_entry.setToolTip("")

        self.custom_save_entry.setEnabled(False)
        self.custom_save_button.setEnabled(False)
        self.custom_save_checkbox.blockSignals(True)
        self.custom_save_checkbox.setChecked(False)
        self.custom_save_checkbox.blockSignals(False)
        self.use_custom_save_var.set(False)

    def _load_system_configs(self) -> Dict[str, Dict[str, Any]]:
        config_path = Path(__file__).resolve().parents[1] / "Json_Files" / "system_configs.json"
        try:
            with config_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                return data
        except FileNotFoundError:
            print(f"[QtMeasurementGUI] system config file missing: {config_path}")
        except json.JSONDecodeError as exc:
            print(f"[QtMeasurementGUI] system config JSON error: {exc}")
        return {}

    def _choose_default_system_name(self) -> Optional[str]:
        if "Lab Small" in self.system_configs:
            return "Lab Small"
        if self.system_configs:
            return next(iter(self.system_configs.keys()))
        return None

    def _load_save_location_config(self) -> None:
        config_path = Path(__file__).resolve().parents[1] / "Json_Files" / "save_location_config.json"
        self._saved_custom_path = None
        self._saved_use_custom = False
        try:
            if config_path.exists():
                with config_path.open("r", encoding="utf-8") as handle:
                    data = json.load(handle)
                if isinstance(data, dict):
                    custom_path = data.get("custom_save_path")
                    if custom_path:
                        self._saved_custom_path = custom_path
                        try:
                            self.custom_save_location = Path(custom_path)
                        except Exception:
                            self.custom_save_location = None
                    self._saved_use_custom = bool(data.get("use_custom_save", False))
        except Exception as exc:
            print(f"[QtMeasurementGUI] Could not load save location config: {exc}")

    def _save_save_location_config(self) -> None:
        config_path = Path(__file__).resolve().parents[1] / "Json_Files" / "save_location_config.json"
        try:
            payload = {
                "use_custom_save": bool(self.use_custom_save_var.get()),
                "custom_save_path": str(self.custom_save_location) if self.custom_save_location else self._saved_custom_path or "",
            }
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with config_path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
        except Exception as exc:
            print(f"[QtMeasurementGUI] Could not save save location config: {exc}")

    # ---- Auxiliary handlers --------------------------------------------------
    def _handle_temp_toggle(self, state: int) -> None:
        flag = state == QtCore.Qt.CheckState.Checked.value
        self.append_status(f"Temperature control {'enabled' if flag else 'disabled'}.")

    def _handle_temp_apply(self) -> None:
        setpoint = self.temp_spin.value()
        self.append_status(f"Temperature setpoint requested: {setpoint:.2f} °C")

    def _handle_messaging_toggle(self, state: int) -> None:
        enabled = state == QtCore.Qt.CheckState.Checked.value
        self.append_status(f"Telegram messaging {'enabled' if enabled else 'disabled'}.")

    def _handle_operator_change(self, name: str) -> None:
        if name in ("", "Choose name"):
            return
        if name and name in self.messaging_data:
            self.append_status(f"Selected Telegram operator: {name}")
        else:
            self.append_status("Telegram operator set to default.")

    def _open_custom_editor(self) -> None:
        QtWidgets.QMessageBox.information(
            self,
            "Custom Presets",
            "Preset editor is not yet available in the Qt port.",
        )

    def _open_motor_control(self) -> None:
        if self._motor_process and self._motor_process.state() == QtCore.QProcess.ProcessState.Running:
            QtWidgets.QMessageBox.information(
                self,
                "Motor Control",
                "The motor control window is already running.",
            )
            self.append_status("Motor control window already active.")
            return

        script_path = Path(__file__).resolve().parent.parent / "Motor_Controll_GUI.py"
        if not script_path.exists():
            QtWidgets.QMessageBox.critical(
                self,
                "Motor Control",
                f"Could not find motor control script at\n{script_path}",
            )
            self.append_status("Motor control script missing; launch aborted.")
            return

        process = QtCore.QProcess(self)
        process.setProgram(sys.executable)
        process.setArguments([str(script_path)])
        process.setProcessChannelMode(QtCore.QProcess.ProcessChannelMode.MergedChannels)
        process.finished.connect(self._on_motor_process_finished)
        process.start()

        if not process.waitForStarted(3000):
            msg = process.errorString()
            QtWidgets.QMessageBox.critical(
                self,
                "Motor Control",
                f"Failed to start motor control window:\n{msg}",
            )
            self.append_status(f"Motor control launch failed: {msg}")
            process.deleteLater()
            return

        self._motor_process = process
        self.append_status("Motor control window launched as external Tk application.")

    def _on_motor_process_finished(
        self,
        exit_code: int,
        status: QtCore.QProcess.ExitStatus,
    ) -> None:
        reason = "normal exit" if status == QtCore.QProcess.ExitStatus.NormalExit else "crash"
        self.append_status(f"Motor control window closed ({reason}, code {exit_code}).")
        if self._motor_process:
            self._motor_process.deleteLater()
            self._motor_process = None

    def _open_advanced_tests(self) -> None:
        self.append_status("Advanced tests (Qt) launch requested.")
        QtWidgets.QMessageBox.information(
            self,
            "Advanced Tests",
            "Advanced test dialogs are not yet ported to the Qt interface.",
        )

    def _open_pmu_testing(self) -> None:
        script_path = Path(__file__).resolve().parents[1] / "Other" / "old_code" / "4200_old" / "PMU_Testing_GUI.py"
        self._launch_external_gui("PMU Testing", script_path)

    def _open_tsp_testing(self) -> None:
        script_path = Path(__file__).resolve().parents[1] / "TSP_Testing_GUI.py"
        self._launch_external_gui("TSP Pulse Testing", script_path)

    # ------------------------------------------------------------------
    # Helpers / initialization data
    # ------------------------------------------------------------------
    def _update_smu_type(self, smu: str) -> None:
        self.smu_type = smu
        self.append_status(f"SMU type set to {smu}.")

    def _build_device_cache(self) -> None:
        if not self.device_list:
            self.device_list = ["1"]

    def set_current_device(self, device_name: str) -> None:
        """Update UI to reflect the active device selection."""
        if not device_name:
            return
        self.current_device = device_name
        self.final_device_letter, self.final_device_number = self._split_device_label(device_name)
        self.device_indicator.setText(f"Current device: {device_name}")
        combo = getattr(self, "seq_device_combo", None)
        if combo is not None:
            idx = combo.findText(device_name)
            if idx >= 0:
                combo.setCurrentIndex(idx)

    # ------------------------------------------------------------------
    # Measurement orchestration helpers
    # ------------------------------------------------------------------
    def _begin_measurement(
        self,
        voltage_range: List[float],
        icc: float,
        sweeps: int,
        step_delay: float,
    ) -> None:
        if not (self.use_custom_save_var.get() and self.custom_save_location):
            self.check_for_sample_name()
        self._pending_voltage_range = list(voltage_range)
        self._point_counter = 0
        self._set_measurement_active(True)
        self._reset_plots()
        self._plot_time.clear()

        worker = IVSweepWorker(
            service=self.measurement_service,
            keithley=self.keithley,
            smu_type=self.smu_type,
            voltage_range=self._pending_voltage_range,
            icc=icc,
            sweeps=sweeps,
            step_delay=step_delay,
        )
        thread = QtCore.QThread(self)

        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.point.connect(self._handle_worker_point)
        worker.finished.connect(self._handle_worker_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        self._current_worker = worker
        self._current_thread = thread

        self.append_status("Starting IV sweep...")
        thread.start()

    def _stop_measurement(self) -> None:
        if not self._measurement_active or not self._current_worker:
            self.append_status("No active measurement to stop.")
            return
        self.stop_measurement_flag = True
        self.append_status("Stop requested; waiting for worker to finish current point.")
        self._current_worker.request_stop()
        if hasattr(self, "stop_button"):
            self.stop_button.setEnabled(False)

    def _handle_worker_point(self, source: float, measurement: float, t_s: float) -> None:
        self._point_counter += 1
        self._plot_voltage.append(source)
        self._plot_current.append(measurement)
        self._plot_time.append(t_s)
        self._refresh_plots()
        if self._point_counter % 25 == 0:
            self.append_status(
                f"Point {self._point_counter}: source={source:.4f}, meas={measurement:.4e}, t={t_s:.2f}s"
            )

    def _handle_worker_finished(
        self,
        v_arr: List[float],
        c_arr: List[float],
        t_arr: List[float],
        error: str,
    ) -> None:
        if error:
            QtWidgets.QMessageBox.critical(
                self,
                "Measurement Error",
                f"The measurement failed:\n{error}",
            )
            self.append_status(f"Measurement failed: {error}")
        else:
            self.append_status(
                f"Measurement complete with {len(v_arr)} samples collected."
            )
            self._plot_voltage = list(v_arr)
            self._plot_current = list(c_arr)
            self._plot_time = list(t_arr)
            self._refresh_plots(force=True)
            self._record_sweep_history(v_arr, c_arr)
            self._store_measurement_result(v_arr, c_arr, t_arr)
        self._set_measurement_active(False)
        self._current_worker = None
        self._current_thread = None

    def _set_measurement_active(self, active: bool) -> None:
        self._measurement_active = active
        if hasattr(self, "run_button"):
            self.run_button.setEnabled(not active)
        if hasattr(self, "stop_button"):
            self.stop_button.setEnabled(active)

        controls: List[Optional[QtWidgets.QWidget]] = [
            getattr(self, "start_voltage", None),
            getattr(self, "stop_voltage", None),
            getattr(self, "step_voltage", None),
            getattr(self, "icc_spin", None),
            getattr(self, "sweep_count_spin", None),
            getattr(self, "step_delay_spin", None),
            getattr(self, "custom_combo", None),
        ]
        for widget in controls:
            if widget is not None:
                widget.setEnabled(not active)

    def set_sequential_state(self, state: str) -> None:
        running = state == "running"
        if hasattr(self, "seq_run_button"):
            self.seq_run_button.setEnabled(not running)
        if hasattr(self, "seq_stop_button"):
            self.seq_stop_button.setEnabled(running)
        for widget in [
            getattr(self, "seq_mode_combo", None),
            getattr(self, "seq_voltage_spin", None),
            getattr(self, "seq_count_spin", None),
            getattr(self, "seq_delay_spin", None),
            getattr(self, "seq_duration_spin", None),
            getattr(self, "seq_record_temp", None),
            getattr(self, "seq_single_device", None),
            getattr(self, "seq_device_combo", None),
        ]:
            if widget is not None:
                widget.setEnabled(not running)

    def _handle_single_device_toggle(self, checked: bool) -> None:
        self.single_device_flag = checked

    def _on_sequential_device_selected(self, device: str) -> None:
        if device:
            self.current_device = device
            self.set_current_device(device)

    def _reset_plots_for_new_run(self) -> None:
        self.v_arr_disp.clear()
        self.c_arr_disp.clear()
        self.t_arr_disp.clear()
        self._reset_plots()

    def get_var_value(self, name: str) -> Any:
        mapping = {
            "Sequential_measurement_var": self.Sequential_measurement_var,
            "sequential_number_of_sweeps": self.sequential_number_of_sweeps,
            "sq_voltage": self.sq_voltage,
            "sq_time_delay": self.sq_time_delay,
            "measurement_duration_var": self.measurement_duration_var,
            "record_temp_var": self.record_temp_var,
            "use_custom_save_var": self.use_custom_save_var,
            "custom_save_location": self.custom_save_location,
        }
        var = mapping.get(name)
        if hasattr(var, "get"):
            return var.get()
        return var

    def log_terminal(self, message: str) -> None:
        self.append_status(message)

    def bring_to_top(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def check_for_sample_name(self) -> None:
        if not self.sample_name_var.get():
            self.sample_name_var.set("Qt_Sample")

    def _get_base_save_path(self) -> Optional[str]:
        if self.use_custom_save_var.get() and self.custom_save_location:
            return str(self.custom_save_location)
        return None

    def save_averaged_data(
        self,
        device_data: Dict[str, Dict[str, List[float]]],
        sample_name: str,
        start_index: int,
        interrupted: bool = False,
    ) -> None:
        status = "interrupted" if interrupted else "complete"
        custom_base = self._get_base_save_path()
        custom_path = Path(custom_base) if custom_base else None
        self.sequential_data_saver.save_averaged_data(
            device_data=device_data,
            sample_name=sample_name,
            measurement_duration=float(self.measurement_duration_var.get()),
            record_temperature=self.record_temp_var.get(),
            status=status,
            custom_base=custom_path,
            logger=self.append_status,
        )

    def save_all_measurements_file(
        self,
        device_data: Dict[str, Dict[str, List[float]]],
        sample_name: str,
        start_index: int,
    ) -> None:
        custom_base = self._get_base_save_path()
        custom_path = Path(custom_base) if custom_base else None
        self.sequential_data_saver.save_all_measurements_file(
            device_data=device_data,
            sample_name=sample_name,
            record_temperature=self.record_temp_var.get(),
            custom_base=custom_path,
            logger=self.append_status,
        )

    def measure_average_current(self, voltage: float, duration: float) -> Tuple[float, float, float]:
        if not self.keithley:
            return 0.0, 0.0, float("nan")

        try:
            self.keithley.set_voltage(voltage)
        except Exception:
            return 0.0, 0.0, float("nan")

        readings: List[float] = []
        start = time.time()
        sample_interval = 0.1
        while (time.time() - start) < duration and not self.stop_measurement_flag:
            try:
                current = self.keithley.measure_current()
                if isinstance(current, (list, tuple)):
                    current = current[-1]
                readings.append(float(current))
            except Exception:
                break
            time.sleep(sample_interval)

        avg = statistics.mean(readings) if readings else 0.0
        std = statistics.pstdev(readings) if len(readings) > 1 else 0.0
        return avg, std, float("nan")

    def sequential_run_finished(self) -> None:
        self.set_sequential_state("idle")
        self.stop_measurement_flag = False
        self.sequential_runner = None
        self.append_status("Sequential measurement complete.")

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # type: ignore[override]
        if self._measurement_active and self._current_worker:
            self._current_worker.request_stop()
            if self._current_thread:
                self._current_thread.quit()
                self._current_thread.wait(1000)
        if self._motor_process and self._motor_process.state() == QtCore.QProcess.ProcessState.Running:
            self._motor_process.terminate()
            self._motor_process.waitForFinished(2000)
            self._motor_process.deleteLater()
            self._motor_process = None
        super().closeEvent(event)

    def _load_custom_sweeps(self, filename: str) -> None:
        try:
            with open(filename, "r", encoding="utf-8") as handle:
                self.custom_sweeps = json.load(handle)
        except FileNotFoundError:
            self.custom_sweeps = {}
            self._log_startup("Custom sweeps file not found; continuing without presets.")
        except json.JSONDecodeError as exc:
            self.custom_sweeps = {}
            self._log_startup(f"Error decoding custom sweeps JSON: {exc}")
        self.code_names = {
            name: sweep.get("code_name") for name, sweep in self.custom_sweeps.items()
        }

    def _load_messaging_data(self) -> None:
        try:
            with open("Json_Files/messaging_data.json", "r", encoding="utf-8") as file:
                self.messaging_data = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            self.messaging_data = {}
        self.names = list(self.messaging_data.keys())

    def _log_startup(self, message: str) -> None:
        """Fallback logger for early initialization before UI widgets exist."""
        if hasattr(self, "status_log"):
            self.append_status(message)
        else:
            print(f"[QtMeasurementGUI] {message}")


def launch_qt_gui(
    sample_type: str,
    section: str,
    device_list: list[str],
    sample_gui: Any,
) -> QtMeasurementGUI:
    """Convenience factory to instantiate the Qt GUI window."""

    window = QtMeasurementGUI(
        sample_type=sample_type,
        section=section,
        device_list=device_list,
        sample_gui=sample_gui,
    )
    window.show()
    return window

