"""Main application window."""

from __future__ import annotations

import csv
import json
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QGridLayout,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

_SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from analysis.calibration import AppConfig, CalibrationState, load_config, save_config
from analysis.gaussian_fit import BeamFitResult, analyze_beam
from analysis.intensity_hist import draw_intensity_histogram, gray_from_frame
from analysis.preprocessing import preprocess_frame
from analysis.view_zoom import crop_zoom, map_display_to_full
from camera import (
    THORLABS_AVAILABLE,
    UC480_AVAILABLE,
    OpenCVCamera,
    ThorlabsCamera,
    UC480Camera,
    list_opencv_devices,
    list_thorlabs_serials,
    list_uc480_cameras,
    recommend_backend,
)
from gui.overlays import draw_overlays
from gui.results_panel import ResultsPanel
from gui.video_panel import VideoPanel
from stage import KINESIS_AVAILABLE, ZMotorController, list_stage_motors


class MainWindow(QMainWindow):
    _z_connect_result = pyqtSignal(object, str)
    _z_async_result = pyqtSignal(str, str)
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Laser Beam Width")
        self.resize(1400, 820)

        self.config = load_config()
        self._camera = None
        self._background: Optional[np.ndarray] = None
        self._last_fit: Optional[BeamFitResult] = None
        self._last_roi_offset = (0, 0)
        self._frozen = False
        self._frozen_frame: Optional[np.ndarray] = None
        self._cal_click_step = 0
        self._cal_temp_a: Optional[Tuple[float, float]] = None
        self._calibrating = False
        self._pick_spot_center = False
        self._crop_offset = (0, 0)
        self._zoom_center_x: Optional[float] = None
        self._zoom_center_y: Optional[float] = None
        self._frame_fail_count = 0
        self._camera_lost_notified = False
        self._z_motor: Optional[ZMotorController] = None
        self._z_busy = False

        self.video = VideoPanel()
        self.video.clicked.connect(self._on_video_click)
        self.results = ResultsPanel()

        sidebar = self._build_sidebar()

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.video)
        splitter.addWidget(sidebar)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([880, 520])
        self.setCentralWidget(splitter)
        self.setStatusBar(QStatusBar())

        self._display_timer = QTimer(self)
        self._display_timer.timeout.connect(self._on_display_tick)
        self._analysis_timer = QTimer(self)
        self._analysis_timer.timeout.connect(self._on_analysis_tick)
        self._z_position_timer = QTimer(self)
        self._z_position_timer.timeout.connect(self._refresh_z_position)
        self._z_connect_result.connect(self._finish_z_connect)
        self._z_async_result.connect(self._on_z_async_result)

        self._apply_config_to_ui()
        self._refresh_backend_availability()

    def _build_sidebar(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(500)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        grid = QGridLayout(content)
        grid.setSpacing(10)
        grid.setContentsMargins(6, 6, 6, 6)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        camera = self._build_camera_group()
        zoom = self._build_zoom_group()
        measure = self._build_measure_group()
        cal = self._build_cal_group()
        z_focus = self._build_z_focus_group()
        save = self._build_save_group()

        grid.addWidget(camera, 0, 0)
        grid.addWidget(zoom, 0, 1)
        grid.addWidget(measure, 1, 0)
        grid.addWidget(cal, 1, 1)
        grid.addWidget(z_focus, 2, 0, 1, 2)
        grid.addWidget(self.results, 3, 0, 1, 2)
        grid.addWidget(save, 4, 0, 1, 2)

        bottom_spacer = QWidget()
        bottom_spacer.setMinimumHeight(8)
        grid.addWidget(bottom_spacer, 5, 0, 1, 2)
        grid.setRowStretch(5, 1)

        scroll.setWidget(content)
        return scroll

    def _refresh_backend_availability(self) -> None:
        """Pick sensible defaults and populate device lists."""
        self._scan_devices(show_message=False)
        recommended = recommend_backend()
        if self.config.camera_backend not in {"uc480", "opencv", "thorlabs"}:
            self.config.camera_backend = recommended
        backend_index = {"uc480": 0, "opencv": 1, "thorlabs": 2}.get(self.config.camera_backend, 0)
        self.backend_combo.setCurrentIndex(backend_index)
        if not UC480_AVAILABLE:
            self.backend_combo.model().item(0).setEnabled(False)
        if not THORLABS_AVAILABLE or not list_thorlabs_serials():
            self.backend_combo.model().item(2).setEnabled(False)
        self._on_backend_changed(self.backend_combo.currentIndex())

    def _backend_name(self) -> str:
        return ("uc480", "opencv", "thorlabs")[self.backend_combo.currentIndex()]

    def _scan_devices(self, show_message: bool = True) -> None:
        backend = self._backend_name()
        self.device_combo.clear()
        if backend == "uc480":
            cameras = list_uc480_cameras()
            if not cameras:
                self.device_combo.addItem("No uc480 camera detected")
            for cam in cameras:
                label = f"{cam['model']} ({cam['serial']})"
                if cam["in_use"]:
                    label += " [in use]"
                self.device_combo.addItem(label, cam)
            if show_message:
                if cameras:
                    self.statusBar().showMessage(f"Found {len(cameras)} Thorlabs uc480 camera(s)", 4000)
                else:
                    QMessageBox.information(
                        self,
                        "Scan cameras",
                        "No Thorlabs uc480 camera found.\nInstall ThorCam and check USB.",
                    )
        elif backend == "opencv":
            devices = list_opencv_devices()
            if not devices:
                self.device_combo.addItem("No USB webcam found")
            for dev in devices:
                self.device_combo.addItem(f"{dev['index']}: {dev['name']}", dev)
            if show_message:
                msg = "\n".join(f"{d['index']}: {d['name']}" for d in devices) or "No USB webcams found."
                QMessageBox.information(self, "OpenCV cameras", msg)
        else:
            serials = list_thorlabs_serials()
            if not serials:
                self.device_combo.addItem("No TLCamera detected")
            else:
                self.device_combo.addItems(serials)
            if show_message and not serials:
                QMessageBox.information(self, "Thorlabs TLCamera", "No TLCamera devices detected.")
        self._select_saved_device()

    def _select_saved_device(self) -> None:
        backend = self.config.camera_backend
        for i in range(self.device_combo.count()):
            data = self.device_combo.itemData(i)
            if backend == "uc480" and isinstance(data, dict):
                if data.get("serial") == self.config.camera_serial:
                    self.device_combo.setCurrentIndex(i)
                    return
            elif backend == "opencv" and isinstance(data, dict):
                if data.get("index") == self.config.camera_index:
                    self.device_combo.setCurrentIndex(i)
                    return
            elif backend == "thorlabs":
                if self.device_combo.itemText(i) == self.config.camera_serial:
                    self.device_combo.setCurrentIndex(i)
                    return

    def _on_backend_changed(self, index: int) -> None:
        use_uc480 = index == 0
        use_opencv = index == 1
        self.res_w.setEnabled(use_opencv)
        self.res_h.setEnabled(use_opencv)
        self.exposure_spin.setEnabled(use_opencv or use_uc480)
        self.exposure_stack.setCurrentIndex(0 if use_uc480 else 1)
        self.gain_spin.setEnabled(use_uc480 or use_opencv)
        self.gain_boost_check.setEnabled(use_uc480)
        self.gain_boost_check.setVisible(use_uc480)
        self.dark_preset_btn.setEnabled(use_uc480 or use_opencv)
        self.apply_camera_btn.setEnabled(use_uc480 or use_opencv)
        if use_uc480:
            self.gain_spin.setRange(1.0, 100.0)
            self.gain_spin.setSuffix("×")
            self.backend_hint.setText(
                "Use Thorlabs UC480 for your C1284R13C camera (ThorCam SDK). "
                "OpenCV only sees standard webcams such as the Logitech C920."
            )
        elif use_opencv:
            self.exposure_spin.setRange(-13.0, 0.0)
            if self.exposure_spin.value() > 0:
                self.exposure_spin.setValue(-6.0)
            self.exposure_spin.setSuffix("")
            self.gain_spin.setRange(0.0, 255.0)
            self.gain_spin.setSuffix("")
            self.backend_hint.setText(
                "OpenCV lists USB webcams only. Your Thorlabs camera will not appear here."
            )
        else:
            self.gain_spin.setEnabled(False)
            self.dark_preset_btn.setEnabled(False)
            self.apply_camera_btn.setEnabled(False)
            self.backend_hint.setText("TLCamera is for Kiralux/Zelux models with ThorCam TLCamera SDK.")
        self._scan_devices(show_message=False)

    def _build_camera_group(self) -> QGroupBox:
        box = QGroupBox("Camera")
        form = QFormLayout(box)
        self.backend_combo = QComboBox()
        self.backend_combo.addItems(
            [
                "Thorlabs UC480 (ThorCam)",
                "OpenCV (USB webcam)",
                "Thorlabs TLCamera",
            ]
        )
        if not UC480_AVAILABLE:
            self.backend_combo.model().item(0).setEnabled(False)
        if not THORLABS_AVAILABLE:
            self.backend_combo.model().item(2).setEnabled(False)
        self.device_combo = QComboBox()
        self.scan_btn = QPushButton("Scan cameras")
        self.scan_btn.clicked.connect(lambda: self._scan_devices(show_message=True))
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self._toggle_camera)
        self.exposure_spin = QDoubleSpinBox()
        self.exposure_spin.setRange(0.001, 1.0)
        self.exposure_spin.setDecimals(4)
        self.exposure_spin.setSingleStep(0.01)
        self.exposure_spin.setValue(self.config.exposure)

        self.exposure_ms_spin = QDoubleSpinBox()
        self.exposure_ms_spin.setRange(0.001, 1000.0)
        self.exposure_ms_spin.setDecimals(3)
        self.exposure_ms_spin.setSingleStep(0.1)
        self.exposure_ms_spin.setSuffix(" ms")
        self.exposure_ms_spin.setToolTip("Shutter / exposure time (lower = darker, faster)")
        self.exposure_ms_spin.setValue(max(0.001, self.config.exposure * 1000.0))

        self.gain_spin = QDoubleSpinBox()
        self.gain_spin.setRange(1.0, 100.0)
        self.gain_spin.setDecimals(1)
        self.gain_spin.setSingleStep(1.0)
        self.gain_spin.setValue(max(1.0, self.config.camera_gain))
        self.gain_spin.setToolTip("Master gain (1.0 = minimum / no amplification)")

        self.gain_boost_check = QCheckBox("Gain boost (brighter, noisier)")
        self.gain_boost_check.setChecked(self.config.gain_boost)

        self.apply_camera_btn = QPushButton("Apply camera settings")
        self.apply_camera_btn.clicked.connect(self._apply_camera_settings)

        self.dark_preset_btn = QPushButton("Min intensity preset")
        self.dark_preset_btn.setToolTip("Shortest exposure, minimum gain, gain boost off")
        self.dark_preset_btn.clicked.connect(self._apply_dark_preset)

        self.exposure_ms_spin.valueChanged.connect(lambda _: self._schedule_camera_apply())
        self.exposure_spin.valueChanged.connect(lambda _: self._schedule_camera_apply())
        self.gain_spin.valueChanged.connect(lambda _: self._schedule_camera_apply())
        self.gain_boost_check.toggled.connect(lambda _: self._schedule_camera_apply())
        self._camera_apply_timer = QTimer(self)
        self._camera_apply_timer.setSingleShot(True)
        self._camera_apply_timer.timeout.connect(self._apply_camera_settings)

        self.exposure_stack = QStackedWidget()
        self.exposure_stack.addWidget(self.exposure_ms_spin)
        self.exposure_stack.addWidget(self.exposure_spin)
        self.res_w = QSpinBox()
        self.res_w.setRange(320, 4096)
        self.res_w.setValue(self.config.resolution[0])
        self.res_h = QSpinBox()
        self.res_h.setRange(240, 4096)
        self.res_h.setValue(self.config.resolution[1])
        form.addRow("Backend", self.backend_combo)
        device_row = QHBoxLayout()
        device_row.addWidget(self.device_combo)
        device_row.addWidget(self.scan_btn)
        form.addRow("Device", device_row)
        form.addRow("Exposure", self.exposure_stack)
        form.addRow("Master gain", self.gain_spin)
        form.addRow(self.gain_boost_check)
        dark_row = QHBoxLayout()
        dark_row.addWidget(self.dark_preset_btn)
        dark_row.addWidget(self.apply_camera_btn)
        form.addRow(dark_row)
        res_row = QHBoxLayout()
        res_row.addWidget(self.res_w)
        res_row.addWidget(QLabel("×"))
        res_row.addWidget(self.res_h)
        form.addRow("Resolution", res_row)
        self.backend_hint = QLabel("")
        self.backend_hint.setWordWrap(True)
        self.backend_hint.setStyleSheet("color: #555; font-size: 11px;")
        form.addRow(self.backend_hint)
        form.addRow(self.connect_btn)
        self.backend_combo.currentIndexChanged.connect(self._on_backend_changed)
        return box

    def _build_measure_group(self) -> QGroupBox:
        box = QGroupBox("Measurement")
        layout = QVBoxLayout(box)
        self.bg_check = QCheckBox("Subtract background")
        self.bg_check.setChecked(self.config.background_subtract)
        self.bg_btn = QPushButton("Capture background (laser OFF)")
        self.bg_btn.clicked.connect(self._capture_background)
        self.clear_bg_btn = QPushButton("Clear background")
        self.clear_bg_btn.clicked.connect(self._clear_background)
        self.freeze_btn = QPushButton("Freeze frame")
        self.freeze_btn.setCheckable(True)
        self.freeze_btn.toggled.connect(self._on_freeze_toggled)
        self.roi_spin = QSpinBox()
        self.roi_spin.setRange(5, 800)
        self.roi_spin.setValue(self.config.roi_half_size_px)
        self.roi_spin.setToolTip("Half-width of analysis box around spot (use 10–30 for few-pixel spots)")
        form = QFormLayout()
        form.addRow(self.bg_check)
        form.addRow("ROI half-size (px)", self.roi_spin)
        layout.addLayout(form)
        layout.addWidget(self.bg_btn)
        layout.addWidget(self.clear_bg_btn)
        layout.addWidget(self.freeze_btn)
        return box

    def _build_zoom_group(self) -> QGroupBox:
        box = QGroupBox("Zoom & spot")
        layout = QVBoxLayout(box)
        form = QFormLayout()

        self.zoom_spin = QSpinBox()
        self.zoom_spin.setRange(1, 64)
        self.zoom_spin.setValue(1)
        self.zoom_spin.setSuffix("×")
        self.zoom_spin.setToolTip("Current view magnification (1× = full frame)")

        self.click_zoom_spin = QSpinBox()
        self.click_zoom_spin.setRange(2, 64)
        self.click_zoom_spin.setValue(max(2, int(round(self.config.click_magnification))))
        self.click_zoom_spin.setSuffix("×")
        self.click_zoom_spin.setToolTip("Magnification applied when you click the image")

        self.full_view_btn = QPushButton("Full view (zoom out)")
        self.full_view_btn.clicked.connect(self._zoom_out_full)

        self.manual_center_check = QCheckBox("Manual spot center (for small spots)")
        self.manual_center_check.setChecked(self.config.manual_spot_center)
        self.set_center_btn = QPushButton("Set spot center only (no zoom)")
        self.set_center_btn.clicked.connect(self._start_pick_spot_center)
        self.clear_center_btn = QPushButton("Use auto center")
        self.clear_center_btn.clicked.connect(self._clear_manual_center)

        self.center_x_spin = QSpinBox()
        self.center_x_spin.setRange(0, 10000)
        self.center_y_spin = QSpinBox()
        self.center_y_spin.setRange(0, 10000)
        if self.config.spot_center_x is not None:
            self.center_x_spin.setValue(int(round(self.config.spot_center_x)))
        if self.config.spot_center_y is not None:
            self.center_y_spin.setValue(int(round(self.config.spot_center_y)))

        form.addRow("Zoom on click", self.click_zoom_spin)
        form.addRow("Current zoom", self.zoom_spin)
        layout.addLayout(form)
        layout.addWidget(self.full_view_btn)
        form2 = QFormLayout()
        form2.addRow("Center X (px)", self.center_x_spin)
        form2.addRow("Center Y (px)", self.center_y_spin)
        layout.addLayout(form2)
        layout.addWidget(self.manual_center_check)
        layout.addWidget(self.set_center_btn)
        layout.addWidget(self.clear_center_btn)

        self.sensor_roi_group = QGroupBox("Sensor ROI (uc480 hardware crop)")
        roi_form = QFormLayout(self.sensor_roi_group)
        self.sensor_roi_w = QSpinBox()
        self.sensor_roi_w.setRange(64, 1280)
        self.sensor_roi_w.setValue(self.config.sensor_roi_width)
        self.sensor_roi_h = QSpinBox()
        self.sensor_roi_h.setRange(64, 1024)
        self.sensor_roi_h.setValue(self.config.sensor_roi_height)
        self.apply_sensor_roi_btn = QPushButton("Apply sensor ROI")
        self.apply_sensor_roi_btn.clicked.connect(self._apply_sensor_roi)
        self.reset_sensor_roi_btn = QPushButton("Reset full sensor")
        self.reset_sensor_roi_btn.clicked.connect(self._reset_sensor_roi)
        roi_form.addRow("ROI width (px)", self.sensor_roi_w)
        roi_form.addRow("ROI height (px)", self.sensor_roi_h)
        roi_form.addRow(self.apply_sensor_roi_btn)
        roi_form.addRow(self.reset_sensor_roi_btn)
        layout.addWidget(self.sensor_roi_group)
        return box

    def _build_cal_group(self) -> QGroupBox:
        box = QGroupBox("Calibration")
        layout = QVBoxLayout(box)
        self.pixel_only_check = QCheckBox("Pixels only (no physical scale)")
        self.pixel_only_check.toggled.connect(self._on_pixel_only_toggled)
        self.ref_distance = QDoubleSpinBox()
        self.ref_distance.setRange(0.1, 1e6)
        self.ref_distance.setDecimals(2)
        self.ref_distance.setSuffix(" µm")
        self.ref_distance.setValue(self.config.calibration.reference_distance_um)
        self.cal_btn = QPushButton("Calibrate: click two points")
        self.cal_btn.clicked.connect(self._start_calibration)
        self.cal_status = QLabel("Uncalibrated")
        form = QFormLayout()
        form.addRow(self.pixel_only_check)
        form.addRow("Known distance", self.ref_distance)
        form.addRow(self.cal_status)
        layout.addLayout(form)
        layout.addWidget(self.cal_btn)
        return box

    def _build_z_focus_group(self) -> QGroupBox:
        box = QGroupBox("Z focus (Kinesis)")
        layout = QVBoxLayout(box)
        hint = QLabel("Connect after camera is live. Uses Kinesis only — not Kenisis / TLCamera.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #555; font-size: 11px;")
        layout.addWidget(hint)

        form = QFormLayout()
        self.z_motor_combo = QComboBox()
        self.z_motor_combo.setEditable(True)
        self.z_scan_btn = QPushButton("Scan")
        self.z_scan_btn.clicked.connect(self._scan_z_motors)
        serial_row = QHBoxLayout()
        serial_row.addWidget(self.z_motor_combo, stretch=1)
        serial_row.addWidget(self.z_scan_btn)
        self.z_position_label = QLabel("Z: not connected")
        self.z_jog_step_spin = QDoubleSpinBox()
        self.z_jog_step_spin.setRange(0.001, 5.0)
        self.z_jog_step_spin.setDecimals(3)
        self.z_jog_step_spin.setSuffix(" mm")
        self.z_jog_step_spin.setValue(self.config.z_jog_step_mm)
        self.z_speed_spin = QDoubleSpinBox()
        self.z_speed_spin.setRange(0.05, 2.4)
        self.z_speed_spin.setDecimals(2)
        self.z_speed_spin.setSuffix(" mm/s")
        self.z_speed_spin.setValue(self.config.z_speed_mm_s)
        form.addRow("Motor", serial_row)
        form.addRow("Position", self.z_position_label)
        form.addRow("Jog step", self.z_jog_step_spin)
        form.addRow("Speed", self.z_speed_spin)
        layout.addLayout(form)

        row1 = QHBoxLayout()
        self.z_connect_btn = QPushButton("Connect Z")
        self.z_connect_btn.clicked.connect(self._toggle_z_motor)
        self.z_stop_btn = QPushButton("Stop Z")
        self.z_stop_btn.clicked.connect(self._stop_z_motor)
        row1.addWidget(self.z_connect_btn)
        row1.addWidget(self.z_stop_btn)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.z_down_btn = QPushButton("Z − (down)")
        self.z_up_btn = QPushButton("Z + (up)")
        self.z_home_btn = QPushButton("Home Z")
        self.z_down_btn.clicked.connect(lambda: self._jog_z(-1))
        self.z_up_btn.clicked.connect(lambda: self._jog_z(1))
        self.z_home_btn.clicked.connect(self._home_z_motor)
        row2.addWidget(self.z_down_btn)
        row2.addWidget(self.z_up_btn)
        row2.addWidget(self.z_home_btn)
        layout.addLayout(row2)

        enabled = KINESIS_AVAILABLE
        box.setEnabled(enabled)
        if not KINESIS_AVAILABLE:
            self.z_position_label.setText("Install pylablib + Kinesis for Z control")
        else:
            self._scan_z_motors(select_saved=True)
        self._set_z_motion_enabled(False)
        return box

    def _z_motor_serial(self) -> str:
        text = self.z_motor_combo.currentText().strip()
        if " (" in text:
            return text.split(" (", 1)[0].strip()
        return text

    def _scan_z_motors(self, select_saved: bool = False) -> None:
        self.z_motor_combo.clear()
        devices = list_stage_motors()
        if not devices:
            self.z_motor_combo.addItem(self.config.z_motor_serial)
            self.z_position_label.setText("No Kinesis motors detected — check USB/power")
            return
        saved = self.config.z_motor_serial
        select_idx = 0
        for idx, (serial, desc) in enumerate(devices):
            self.z_motor_combo.addItem(f"{serial} ({desc})", serial)
            if select_saved and serial == saved:
                select_idx = idx
        if select_saved:
            self.z_motor_combo.setCurrentIndex(select_idx)
        elif self.z_motor_combo.findData(saved) >= 0:
            self.z_motor_combo.setCurrentIndex(self.z_motor_combo.findData(saved))
        self.statusBar().showMessage(f"Found {len(devices)} Kinesis motor(s)", 3000)

    def _set_z_motion_enabled(self, enabled: bool) -> None:
        for w in (self.z_down_btn, self.z_up_btn, self.z_home_btn, self.z_stop_btn, self.z_jog_step_spin, self.z_speed_spin):
            w.setEnabled(enabled)
        motors_connected = self._z_motor is not None and self._z_motor.is_connected()
        self.z_motor_combo.setEnabled(not motors_connected)
        self.z_scan_btn.setEnabled(not motors_connected)

    def _toggle_z_motor(self) -> None:
        if self._z_motor is not None and self._z_motor.is_connected():
            self._disconnect_z_motor()
            return
        if self._z_busy:
            return
        self._z_busy = True
        self._set_z_motion_enabled(False)
        serial = self._z_motor_serial()

        def task() -> None:
            try:
                motor = ZMotorController(
                    serial=serial,
                    scale=self.config.z_motor_scale,
                    z_min_mm=self.config.z_min_mm,
                    z_max_mm=self.config.z_max_mm,
                    speed_mm_s=self.z_speed_spin.value(),
                    accel_mm_s2=self.config.z_accel_mm_s2,
                )
                motor.connect()
                self._z_connect_result.emit(motor, "")
            except Exception as exc:
                self._z_connect_result.emit(None, str(exc))

        threading.Thread(target=task, daemon=True).start()

    def _finish_z_connect(self, motor: Optional[ZMotorController], error: str) -> None:
        self._z_busy = False
        if error or motor is None:
            self.z_position_label.setText("Z: connect failed")
            self.statusBar().showMessage(f"Connect Z failed", 5000)
            QMessageBox.warning(self, "Connect Z", error or "Unknown error")
            self._set_z_motion_enabled(False)
            self._scan_z_motors(select_saved=False)
            return
        self._z_motor = motor
        self._on_z_connected()
        self.statusBar().showMessage("Z motor connected", 3000)

    def _on_z_connected(self) -> None:
        self.z_connect_btn.setText("Disconnect Z")
        self._set_z_motion_enabled(True)
        self._z_position_timer.start(400)
        self._refresh_z_position()

    def _disconnect_z_motor(self) -> None:
        self._z_position_timer.stop()
        if self._z_motor is not None:
            try:
                self._z_motor.stop()
                self._z_motor.disconnect()
            except Exception:
                pass
            self._z_motor = None
        self.z_connect_btn.setText("Connect Z")
        self.z_position_label.setText("Z: not connected")
        self._set_z_motion_enabled(False)

    def _stop_z_motor(self) -> None:
        if self._z_motor is not None:
            self._z_motor.stop()

    def _jog_z(self, direction: int) -> None:
        if self._z_motor is None or not self._z_motor.is_connected() or self._z_busy:
            return
        step = self.z_jog_step_spin.value() * direction
        self._run_z_async(
            lambda: self._z_motor.move_relative_mm(step),
            f"Z jog {step:+.3f} mm",
            "Z jog failed",
        )

    def _home_z_motor(self) -> None:
        if self._z_motor is None or not self._z_motor.is_connected() or self._z_busy:
            return
        self._run_z_async(lambda: self._z_motor.home(), "Z homed", "Home Z failed")

    def _refresh_z_position(self) -> None:
        if self._z_motor is None or not self._z_motor.is_connected():
            return
        pos = self._z_motor.get_position_mm()
        if pos is None:
            _, msg = self._z_motor.state()
            self.z_position_label.setText(f"Z: error ({msg})")
        else:
            self.z_position_label.setText(f"Z: {pos:.3f} mm")

    def _run_z_async(self, fn, ok_message: str, err_prefix: str) -> None:
        if self._z_busy:
            return
        self._z_busy = True
        self._set_z_motion_enabled(False)

        def task() -> None:
            try:
                fn()
                if self._z_motor is not None and self._z_motor.is_connected():
                    self._z_motor.apply_motion(self.z_speed_spin.value(), self.config.z_accel_mm_s2)
                self._z_async_result.emit(ok_message, "")
            except Exception as exc:
                self._z_async_result.emit("", f"{err_prefix}: {exc}")

        threading.Thread(target=task, daemon=True).start()

    def _on_z_async_result(self, ok_message: str, error: str) -> None:
        self._z_busy = False
        if error:
            self.statusBar().showMessage(error, 5000)
            QMessageBox.warning(self, "Z motor", error)
        elif ok_message:
            self.statusBar().showMessage(ok_message, 3000)
        connected = self._z_motor is not None and self._z_motor.is_connected()
        self._set_z_motion_enabled(connected)
        self._refresh_z_position()

    def _build_save_group(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        self.save_btn = QPushButton("Save snapshot + results")
        self.save_btn.clicked.connect(self._save_snapshot)
        self.save_btn.setEnabled(False)
        layout.addWidget(self.save_btn)
        return w

    def _apply_config_to_ui(self) -> None:
        backend_index = {"uc480": 0, "opencv": 1, "thorlabs": 2}.get(self.config.camera_backend, 0)
        self.backend_combo.setCurrentIndex(backend_index)
        self.exposure_spin.setValue(self.config.exposure)
        self.exposure_ms_spin.setValue(max(0.001, self.config.exposure * 1000.0))
        self.gain_spin.setValue(max(1.0, self.config.camera_gain))
        self.gain_boost_check.setChecked(self.config.gain_boost)
        self.pixel_only_check.setChecked(self.config.calibration.mode == "pixel_only")
        self.manual_center_check.setChecked(self.config.manual_spot_center)
        self._scan_z_motors(select_saved=True)
        self.z_jog_step_spin.setValue(self.config.z_jog_step_mm)
        self.z_speed_spin.setValue(self.config.z_speed_mm_s)
        self._update_cal_status()

    def _update_cal_status(self) -> None:
        cal = self.config.calibration
        if cal.mode == "pixel_only" or not cal.is_calibrated():
            self.cal_status.setText("Uncalibrated (px only)")
        else:
            self.cal_status.setText(f"{cal.um_per_pixel:.4f} µm/px")

    def _on_pixel_only_toggled(self, checked: bool) -> None:
        if checked:
            self.config.calibration.mode = "pixel_only"
        elif self.config.calibration.um_per_pixel:
            self.config.calibration.mode = "two_point"
        save_config(self.config)

    def _display_zoom(self) -> float:
        return float(self.zoom_spin.value())

    def _spot_center_full(self, frame: np.ndarray) -> Optional[Tuple[float, float]]:
        if self.manual_center_check.isChecked():
            return float(self.center_x_spin.value()), float(self.center_y_spin.value())
        return None

    def _zoom_view_center(self, frame: np.ndarray) -> Tuple[float, float]:
        if self._display_zoom() > 1.0 and self._zoom_center_x is not None and self._zoom_center_y is not None:
            return self._zoom_center_x, self._zoom_center_y
        manual = self._spot_center_full(frame)
        if manual is not None:
            return manual
        if self._last_fit is not None:
            x0, y0 = self._last_roi_offset
            return x0 + self._last_fit.centroid_x, y0 + self._last_fit.centroid_y
        h, w = frame.shape[:2]
        return w / 2.0, h / 2.0

    def _set_spot_center(self, full_x: float, full_y: float) -> None:
        self.center_x_spin.setValue(int(round(full_x)))
        self.center_y_spin.setValue(int(round(full_y)))
        self.manual_center_check.setChecked(True)
        self.config.spot_center_x = full_x
        self.config.spot_center_y = full_y
        self.config.manual_spot_center = True

    def _apply_click_zoom(self, full_x: float, full_y: float) -> None:
        self._zoom_center_x = full_x
        self._zoom_center_y = full_y
        self._set_spot_center(full_x, full_y)
        if self._display_zoom() <= 1.0:
            self.zoom_spin.setValue(self.click_zoom_spin.value())
        save_config(self.config)
        mag = self.zoom_spin.value()
        self.statusBar().showMessage(f"Zoomed {mag}× on ({full_x:.0f}, {full_y:.0f}) — Full view to zoom out", 5000)

    def _zoom_out_full(self) -> None:
        self.zoom_spin.setValue(1)
        self.statusBar().showMessage("Full view — click the laser spot to zoom in", 5000)

    def _map_click_to_full(self, x: float, y: float, frame_shape: tuple) -> Tuple[float, float]:
        return map_display_to_full(x, y, self._display_zoom(), self._crop_offset, frame_shape[:2])

    def _start_pick_spot_center(self) -> None:
        if self._camera is None:
            QMessageBox.warning(self, "Spot center", "Connect the camera first.")
            return
        self._pick_spot_center = True
        self._calibrating = False
        self.manual_center_check.setChecked(True)
        self.statusBar().showMessage("Click the laser spot on the image")

    def _clear_manual_center(self) -> None:
        self.manual_center_check.setChecked(False)
        self._pick_spot_center = False
        self.config.spot_center_x = None
        self.config.spot_center_y = None
        save_config(self.config)
        self.statusBar().showMessage("Using auto-detected spot center", 3000)

    def _apply_sensor_roi(self) -> None:
        if not isinstance(self._camera, UC480Camera):
            QMessageBox.information(self, "Sensor ROI", "Sensor ROI is only available for Thorlabs UC480.")
            return
        frame = self._read_frame()
        if frame is None:
            return
        cx, cy = self._zoom_view_center(frame)
        try:
            aw, ah = self._camera.set_sensor_roi(
                cx, cy, self.sensor_roi_w.value(), self.sensor_roi_h.value()
            )
            self.statusBar().showMessage(f"Sensor ROI applied — now {aw}×{ah}", 5000)
        except Exception as exc:
            QMessageBox.critical(self, "Sensor ROI", str(exc))

    def _reset_sensor_roi(self) -> None:
        if not isinstance(self._camera, UC480Camera):
            return
        try:
            aw, ah = self._camera.reset_sensor_roi()
            self.statusBar().showMessage(f"Full sensor restored — {aw}×{ah}", 5000)
        except Exception as exc:
            QMessageBox.critical(self, "Sensor ROI", str(exc))

    def _detect_thorlabs(self) -> None:
        self._scan_devices(show_message=True)

    def _toggle_camera(self) -> None:
        if self._camera is not None:
            self._stop_camera()
            return
        try:
            self._start_camera()
        except Exception as exc:
            msg = str(exc)
            if "1004" in msg or "Serial number not found" in msg:
                msg = (
                    "Thorlabs TLCamera could not open this camera.\n\n"
                    "Your C1284R13C uc480 camera needs:\n"
                    "  • Backend: Thorlabs UC480 (ThorCam)\n\n"
                    f"Technical detail: {exc}"
                )
                self.backend_combo.setCurrentIndex(0)
            elif "IS_CANT_OPEN_DEVICE" in msg or "in use" in msg.lower():
                msg = (
                    f"{msg}\n\nClose ThorCam, close other instances of this app, "
                    "then click Scan cameras and Connect again."
                )
            QMessageBox.critical(self, "Camera error", msg)

    def _start_camera(self) -> None:
        backend = self._backend_name()
        data = self.device_combo.currentData()
        if backend == "uc480":
            serial = ""
            cam_id = None
            if isinstance(data, dict):
                if data.get("in_use"):
                    raise RuntimeError(
                        f"Camera {data.get('model')} is in use by another application."
                    )
                serial = str(data.get("serial", ""))
                cam_id = data.get("cam_id")
            elif self.config.camera_serial:
                serial = self.config.camera_serial
            self._camera = UC480Camera(cam_id=cam_id, serial=serial)
        elif backend == "opencv":
            index = 0
            if isinstance(data, dict):
                index = int(data.get("index", 0))
            else:
                index = self.config.camera_index
            res = (self.res_w.value(), self.res_h.value())
            self._camera = OpenCVCamera(index=index, resolution=res)
        else:
            serials = list_thorlabs_serials()
            if not serials:
                raise RuntimeError("No Thorlabs TLCamera detected.")
            serial = self.device_combo.currentText().strip() or serials[0]
            self._camera = ThorlabsCamera(serial=serial)

        self._camera.open()
        self._apply_camera_settings()
        if isinstance(self._camera, UC480Camera):
            max_gain = self._camera.get_max_gain()
            if max_gain is not None and max_gain > 1.0:
                self.gain_spin.setRange(1.0, max_gain)
            self._sync_camera_settings_from_device()
            if not self._camera.verify_frames(timeout_s=4.0):
                self._camera.close()
                self._camera = None
                raise RuntimeError(
                    "Thorlabs camera opened but sent no frames.\n\n"
                    "Try:\n"
                    "  • Close ThorCam and this app, then replug the camera USB\n"
                    "  • Open the camera once in ThorCam to confirm it live-previews\n"
                    "  • Remove lens cap / check illumination"
                )
        self.connect_btn.setText("Disconnect")
        self.save_btn.setEnabled(True)
        self._frame_fail_count = 0
        self._camera_lost_notified = False
        interval = max(20, int(1000 / max(1, self.config.analysis_fps)))
        self._display_timer.start(33)
        self._analysis_timer.start(interval)
        if isinstance(self._camera, UC480Camera):
            aw, ah = self._camera.actual_resolution()
            self.statusBar().showMessage(
                f"Connected — {self._camera.device_label()} {aw}×{ah} — click the spot to zoom in"
            )
        elif isinstance(self._camera, OpenCVCamera):
            aw, ah = self._camera.actual_resolution()
            self.statusBar().showMessage(
                f"Connected — OpenCV index {self._camera.index} {aw}×{ah} — click the spot to zoom in"
            )
        else:
            self.statusBar().showMessage("Connected — Thorlabs TLCamera — click the spot to zoom in")

    def _schedule_camera_apply(self) -> None:
        if self._camera is None:
            return
        self._camera_apply_timer.start(150)

    def _exposure_seconds(self) -> float:
        if isinstance(self._camera, UC480Camera) or self._backend_name() == "uc480":
            return max(1e-6, self.exposure_ms_spin.value() / 1000.0)
        return self.exposure_spin.value()

    def _apply_camera_settings(self) -> None:
        if self._camera is None:
            return
        if isinstance(self._camera, UC480Camera):
            actual = self._camera.set_exposure(self._exposure_seconds())
            if actual is not None:
                self.exposure_ms_spin.blockSignals(True)
                self.exposure_ms_spin.setValue(max(0.001, actual * 1000.0))
                self.exposure_ms_spin.blockSignals(False)
            self._camera.set_master_gain(self.gain_spin.value())
            self._camera.set_gain_boost(self.gain_boost_check.isChecked())
            self.config.exposure = self._exposure_seconds()
            self.config.camera_gain = self.gain_spin.value()
            self.config.gain_boost = self.gain_boost_check.isChecked()
        elif isinstance(self._camera, OpenCVCamera):
            self._camera.set_exposure(self.exposure_spin.value())
            self._camera.set_gain(self.gain_spin.value())
            self.config.exposure = self.exposure_spin.value()
            self.config.camera_gain = self.gain_spin.value()
        else:
            self._camera.set_exposure(self._exposure_seconds())

    def _sync_camera_settings_from_device(self) -> None:
        if not isinstance(self._camera, UC480Camera):
            return
        exp = self._camera.get_exposure()
        if exp is not None:
            self.exposure_ms_spin.blockSignals(True)
            self.exposure_ms_spin.setValue(max(0.001, exp * 1000.0))
            self.exposure_ms_spin.blockSignals(False)
        gains = self._camera.get_gains()
        if gains is not None:
            self.gain_spin.blockSignals(True)
            self.gain_spin.setValue(max(1.0, gains[0]))
            self.gain_spin.blockSignals(False)
        boost = self._camera.get_gain_boost()
        if boost is not None:
            self.gain_boost_check.blockSignals(True)
            self.gain_boost_check.setChecked(boost)
            self.gain_boost_check.blockSignals(False)

    def _apply_dark_preset(self) -> None:
        if isinstance(self._camera, UC480Camera) or self._backend_name() == "uc480":
            self.exposure_ms_spin.setValue(0.001)
            self.gain_spin.setValue(1.0)
            self.gain_boost_check.setChecked(False)
        elif isinstance(self._camera, OpenCVCamera) or self._backend_name() == "opencv":
            self.exposure_spin.setValue(-13.0)
            self.gain_spin.setValue(0.0)
        self._apply_camera_settings()
        self.statusBar().showMessage("Min intensity preset applied — check histogram for clipping", 5000)

    def _stop_camera(self) -> None:
        self._display_timer.stop()
        self._analysis_timer.stop()
        if self._camera is not None:
            self._camera.close()
            self._camera = None
        self.connect_btn.setText("Connect")
        self.statusBar().showMessage("Disconnected")

    def _read_frame(self) -> Optional[np.ndarray]:
        if self._frozen and self._frozen_frame is not None:
            return self._frozen_frame.copy()
        if self._camera is None:
            return None
        return self._camera.read()

    def _handle_camera_lost(self) -> None:
        if self._camera_lost_notified:
            return
        self._camera_lost_notified = True
        self._display_timer.stop()
        self._analysis_timer.stop()
        if self._camera is not None:
            try:
                self._camera.close()
            except Exception:
                pass
            self._camera = None
        self.connect_btn.setText("Connect")
        self.save_btn.setEnabled(False)
        self.statusBar().showMessage(
            "Camera stream lost — close Kenisis/ThorCam if open, then click Connect again",
            0,
        )

    def _on_display_tick(self) -> None:
        frame = self._read_frame()
        if frame is None:
            if self._camera is not None and not self._frozen:
                self._frame_fail_count += 1
                if self._frame_fail_count >= 20:
                    self._handle_camera_lost()
            return
        self._frame_fail_count = 0
        view_cx, view_cy = self._zoom_view_center(frame)
        zoom = self._display_zoom()
        spot = self._spot_center_full(frame)
        full_shape = frame.shape[:2]
        display, self._crop_offset = crop_zoom(frame, view_cx, view_cy, zoom)
        display = draw_overlays(
            display,
            self._last_fit,
            self._last_roi_offset,
            self.roi_spin.value(),
            cal_point_a=self.config.calibration.point_a if self.config.calibration.is_calibrated() else None,
            cal_point_b=self.config.calibration.point_b if self.config.calibration.is_calibrated() else None,
            cal_pending=self._cal_temp_a if self._cal_click_step == 1 else None,
            spot_center=spot,
            zoom=zoom,
            crop_offset=self._crop_offset,
            full_shape=full_shape,
        )
        display = draw_intensity_histogram(display, gray_from_frame(frame))
        self.video.set_frame(display)

    def _on_analysis_tick(self) -> None:
        if self._frozen:
            return
        frame = self._read_frame()
        if frame is None:
            return
        self._run_analysis(frame)

    def _run_analysis(self, frame: np.ndarray) -> None:
        bg = self._background if self.bg_check.isChecked() else None
        center = self._spot_center_full(frame)
        prep = preprocess_frame(
            frame,
            background=bg,
            roi_half_size_px=self.roi_spin.value(),
            center_x=center[0] if center else None,
            center_y=center[1] if center else None,
        )
        fit = analyze_beam(prep.roi, prep.centroid_x, prep.centroid_y, prep.saturation_pct, prep.snr)
        self._last_fit = fit
        self._last_roi_offset = prep.roi_offset
        um = None if self.config.calibration.mode == "pixel_only" else self.config.calibration.um_per_pixel
        self.results.update_result(fit, um)

    def _capture_background(self) -> None:
        frame = self._read_frame()
        if frame is None:
            QMessageBox.warning(self, "Background", "No frame available.")
            return
        from analysis.preprocessing import to_grayscale

        self._background = to_grayscale(frame)
        self.statusBar().showMessage("Background captured", 3000)

    def _clear_background(self) -> None:
        self._background = None
        self.statusBar().showMessage("Background cleared", 3000)

    def _on_freeze_toggled(self, checked: bool) -> None:
        self._frozen = checked
        if checked:
            self._frozen_frame = self._read_frame()
            if self._frozen_frame is not None:
                self._run_analysis(self._frozen_frame)
            self.freeze_btn.setText("Unfreeze")
        else:
            self._frozen_frame = None
            self.freeze_btn.setText("Freeze frame")

    def _start_calibration(self) -> None:
        if self._camera is None:
            QMessageBox.warning(self, "Calibration", "Connect the camera first.")
            return
        self._calibrating = True
        self._pick_spot_center = False
        self._cal_click_step = 0
        self._cal_temp_a = None
        self.pixel_only_check.setChecked(False)
        self.statusBar().showMessage("Calibration: click first point")

    def _on_video_click(self, x: float, y: float) -> None:
        frame = self._read_frame()
        if frame is None:
            return
        full_x, full_y = self._map_click_to_full(x, y, frame.shape)

        if self._pick_spot_center:
            self._set_spot_center(full_x, full_y)
            save_config(self.config)
            self._pick_spot_center = False
            self.statusBar().showMessage(f"Spot center set to ({full_x:.0f}, {full_y:.0f})", 4000)
            return

        if self._calibrating:
            x, y = full_x, full_y
            if self._cal_click_step == 0:
                self._cal_temp_a = (x, y)
                self._cal_click_step = 1
                self.statusBar().showMessage("Calibration: click second point")
                return
            if self._cal_click_step == 1 and self._cal_temp_a is not None:
                cal = self.config.calibration
                cal.point_a = self._cal_temp_a
                cal.point_b = (x, y)
                cal.reference_distance_um = self.ref_distance.value()
                if cal.apply_two_point():
                    self.pixel_only_check.setChecked(False)
                    save_config(self.config)
                    self._update_cal_status()
                    self.statusBar().showMessage(f"Calibrated: {cal.um_per_pixel:.4f} µm/px", 5000)
                else:
                    QMessageBox.warning(self, "Calibration", "Could not compute scale from those points.")
                self._cal_click_step = 0
                self._cal_temp_a = None
                self._calibrating = False
            return

        self._apply_click_zoom(full_x, full_y)

    def _save_snapshot(self) -> None:
        frame = self._read_frame()
        if frame is None:
            return
        folder = QFileDialog.getExistingDirectory(self, "Save snapshot folder")
        if not folder:
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = Path(folder) / f"beam_width_{stamp}"
        view_cx, view_cy = self._zoom_view_center(frame)
        zoom = self._display_zoom()
        display, crop_off = crop_zoom(frame, view_cx, view_cy, zoom)
        display = draw_overlays(
            display,
            self._last_fit,
            self._last_roi_offset,
            self.roi_spin.value(),
            cal_point_a=self.config.calibration.point_a,
            cal_point_b=self.config.calibration.point_b,
            spot_center=self._spot_center_full(frame),
            zoom=zoom,
            crop_offset=crop_off,
            full_shape=frame.shape[:2],
        )
        display = draw_intensity_histogram(display, gray_from_frame(frame))
        cv2.imwrite(str(base.with_suffix(".png")), display)
        meta = {
            "timestamp": stamp,
            "fit": None if self._last_fit is None else self._last_fit.__dict__,
            "calibration": self.config.calibration.to_dict(),
            "camera_backend": self.backend_combo.currentText(),
        }
        with open(base.with_suffix(".json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
        if self._last_fit is not None:
            um = self.config.calibration.um_per_pixel
            with open(base.with_suffix(".csv"), "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["metric", "px", "um"])
                for name in ("fwhm_x_px", "fwhm_y_px", "e2_x_px", "e2_y_px", "major_fwhm_px", "minor_fwhm_px"):
                    px = getattr(self._last_fit, name)
                    writer.writerow([name, f"{px:.4f}", "" if um is None else f"{px * um:.2f}"])
        self.statusBar().showMessage(f"Saved {base.name}.*", 5000)

    def closeEvent(self, event) -> None:
        self.config.camera_backend = self._backend_name()
        data = self.device_combo.currentData()
        if isinstance(self._camera, OpenCVCamera):
            self.config.camera_index = self._camera.index
        elif isinstance(self._camera, UC480Camera):
            self.config.camera_serial = self._camera.serial
        elif isinstance(data, dict) and data.get("serial"):
            self.config.camera_serial = str(data["serial"])
        elif self.device_combo.currentText() and self.device_combo.currentText() != "No TLCamera detected":
            self.config.camera_serial = self.device_combo.currentText()
        self.config.resolution = [self.res_w.value(), self.res_h.value()]
        if self._backend_name() == "uc480":
            self.config.exposure = max(1e-6, self.exposure_ms_spin.value() / 1000.0)
        else:
            self.config.exposure = self.exposure_spin.value()
        self.config.camera_gain = self.gain_spin.value()
        self.config.gain_boost = self.gain_boost_check.isChecked()
        self.config.roi_half_size_px = self.roi_spin.value()
        self.config.background_subtract = self.bg_check.isChecked()
        self.config.display_zoom = float(self.zoom_spin.value())
        self.config.click_magnification = float(self.click_zoom_spin.value())
        self.config.manual_spot_center = self.manual_center_check.isChecked()
        if self.manual_center_check.isChecked():
            self.config.spot_center_x = float(self.center_x_spin.value())
            self.config.spot_center_y = float(self.center_y_spin.value())
        self.config.sensor_roi_width = self.sensor_roi_w.value()
        self.config.sensor_roi_height = self.sensor_roi_h.value()
        self.config.z_motor_serial = self._z_motor_serial()
        self.config.z_jog_step_mm = self.z_jog_step_spin.value()
        self.config.z_speed_mm_s = self.z_speed_spin.value()
        save_config(self.config)
        self._disconnect_z_motor()
        self._stop_camera()
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
