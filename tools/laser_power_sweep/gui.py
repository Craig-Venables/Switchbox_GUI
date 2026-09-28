"""PyQt5 GUI for laser power sweep with PM100D."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from Equipment.Laser_Controller.oxxius import OxxiusLaser
from Equipment.Laser_Power_Meter.pm100d import PM100D, find_pm100d_resource

from config import AppConfig, load_config, save_config
from focus_scan import FocusScanPoint, load_focus_scan
from sweep import (
    ControlMode,
    SweepPoint,
    SweepResult,
    filter_setpoints,
    generate_ramp,
    parse_setpoint_list,
    run_power_sweep,
    save_sweep_results,
)

try:
    from gui.sample_gui.config import resolve_default_save_root
except Exception:

    def resolve_default_save_root() -> Path:
        root = Path.home() / "OneDrive - The University of Nottingham" / "Documents" / "Data_folder"
        root.mkdir(parents=True, exist_ok=True)
        return root


class SweepWorker(QObject):
    point_done = pyqtSignal(object, int, int)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(
        self,
        laser: OxxiusLaser,
        pm: PM100D,
        setpoints: List[float],
        kwargs: dict,
    ) -> None:
        super().__init__()
        self._laser = laser
        self._pm = pm
        self._setpoints = setpoints
        self._kwargs = kwargs
        self._stop = False

    def request_stop(self) -> None:
        self._stop = True

    @pyqtSlot()
    def run(self) -> None:
        try:
            result = run_power_sweep(
                self._laser,
                self._pm,
                self._setpoints,
                should_stop=lambda: self._stop,
                on_progress=lambda pt, i, n: self.point_done.emit(pt, i, n),
                **self._kwargs,
            )
            if self._stop and not result.aborted:
                result.aborted = True
                result.abort_reason = "Stopped by user"
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Laser Power Sweep (Oxxius + PM100D)")
        self.resize(1000, 780)

        self.config = load_config()
        self._laser: Optional[OxxiusLaser] = None
        self._pm: Optional[PM100D] = None
        self._laser_idn = ""
        self._pm_idn = ""
        self._meter_zeroed = self.config.meter_zeroed
        self._worker_thread: Optional[QThread] = None
        self._worker: Optional[SweepWorker] = None
        self._last_result: Optional[SweepResult] = None
        self._focus_scan_points: List[FocusScanPoint] = []

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        layout.addWidget(self._build_control_mode_group())
        layout.addWidget(self._build_connection_group())
        layout.addWidget(self._build_sweep_group())
        layout.addWidget(self._build_beam_group())
        layout.addWidget(self._build_run_group())

        splitter = QSplitter()
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(QFont("Consolas", 9))
        self.table = QTableWidget(0, 7)
        splitter.addWidget(self.log)
        splitter.addWidget(self.table)
        splitter.setSizes([240, 360])
        layout.addWidget(splitter, stretch=1)

        self.setStatusBar(QStatusBar())
        self._apply_config_to_ui()
        self._update_connection_state()
        self._update_table_headers()

    def _control_mode(self) -> ControlMode:
        return "ttl_current_pct" if self.control_mode_combo.currentIndex() == 1 else "digital_mw"

    def _build_control_mode_group(self) -> QGroupBox:
        box = QGroupBox("Laser control mode")
        row = QHBoxLayout(box)
        row.addWidget(QLabel("Mode:"))
        self.control_mode_combo = QComboBox()
        self.control_mode_combo.addItems(
            [
                "Digital power (mW) — direct Oxxius setpoint",
                "TTL + current % — you hold 5 V on TTL manually",
            ]
        )
        self.control_mode_combo.currentIndexChanged.connect(self._on_control_mode_changed)
        row.addWidget(self.control_mode_combo, stretch=1)
        return box

    def _build_connection_group(self) -> QGroupBox:
        box = QGroupBox("Connection")
        form = QFormLayout(box)

        self.laser_port_edit = QLineEdit()
        self.laser_baud_spin = QSpinBox()
        self.laser_baud_spin.setRange(9600, 115200)
        self.laser_baud_spin.setSingleStep(9600)

        self.pm_serial_edit = QLineEdit()
        self.pm_serial_edit.setPlaceholderText("Auto-detect if blank")

        self.ttl_hint = QLabel(
            "TTL mode: apply ~5 V to the laser TTL input yourself (FG or bench supply). "
            "Keep TTL LOW for zeroing; hold TTL HIGH during each measurement."
        )
        self.ttl_hint.setWordWrap(True)

        self.wavelength_spin = QDoubleSpinBox()
        self.wavelength_spin.setRange(0, 2000)
        self.wavelength_spin.setSuffix(" nm")
        self.wavelength_spin.setSpecialValueText("(none)")
        self.wavelength_spin.setValue(0)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self._connect_instruments)
        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.clicked.connect(self._disconnect_instruments)
        self.zero_btn = QPushButton("Zero meter (laser OFF)")
        self.zero_btn.clicked.connect(self._zero_meter)

        row = QHBoxLayout()
        row.addWidget(self.connect_btn)
        row.addWidget(self.disconnect_btn)
        row.addWidget(self.zero_btn)

        self.conn_status = QLabel("Not connected")
        self.zero_status = QLabel("Meter not zeroed")

        form.addRow("Laser port", self.laser_port_edit)
        form.addRow("Laser baud", self.laser_baud_spin)
        form.addRow("PM100D serial", self.pm_serial_edit)
        form.addRow(self.ttl_hint)
        form.addRow("Wavelength", self.wavelength_spin)
        form.addRow(row)
        form.addRow(self.conn_status)
        form.addRow(self.zero_status)
        return box

    def _build_sweep_group(self) -> QGroupBox:
        box = QGroupBox("Power sweep")
        layout = QVBoxLayout(box)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Setpoint list mode:"))
        self.setpoint_mode = QComboBox()
        self.setpoint_mode.addItems(["Comma list", "Start / step / max"])
        self.setpoint_mode.currentIndexChanged.connect(self._on_setpoint_list_mode_changed)
        mode_row.addWidget(self.setpoint_mode)
        mode_row.addStretch()
        layout.addLayout(mode_row)

        self.list_widget = QWidget()
        list_form = QFormLayout(self.list_widget)
        self.setpoint_list_edit = QLineEdit()
        self.list_label = QLabel("Setpoints (mW)")
        list_form.addRow(self.list_label, self.setpoint_list_edit)
        layout.addWidget(self.list_widget)

        self.ramp_widget = QWidget()
        ramp_form = QFormLayout(self.ramp_widget)
        self.ramp_start = QDoubleSpinBox()
        self.ramp_start.setRange(0.01, 200.0)
        self.ramp_start.setDecimals(2)
        self.ramp_step = QDoubleSpinBox()
        self.ramp_step.setRange(0.01, 200.0)
        self.ramp_step.setDecimals(2)
        self.ramp_max = QDoubleSpinBox()
        self.ramp_max.setRange(0.01, 200.0)
        self.ramp_max.setDecimals(2)
        self.ramp_start_label = QLabel("Start (mW)")
        self.ramp_step_label = QLabel("Step (mW)")
        self.ramp_max_label = QLabel("Max (mW)")
        ramp_form.addRow(self.ramp_start_label, self.ramp_start)
        ramp_form.addRow(self.ramp_step_label, self.ramp_step)
        ramp_form.addRow(self.ramp_max_label, self.ramp_max)
        self.ramp_widget.setVisible(False)
        layout.addWidget(self.ramp_widget)

        adv = QFormLayout()
        self.abort_spin = QDoubleSpinBox()
        self.abort_spin.setRange(0.1, 50.0)
        self.abort_spin.setDecimals(1)
        self.abort_spin.setSuffix(" mW")
        self.max_setpoint_spin = QDoubleSpinBox()
        self.max_setpoint_spin.setRange(0.1, 50.0)
        self.max_setpoint_spin.setDecimals(1)
        self.max_setpoint_spin.setSuffix(" mW")
        self.max_current_spin = QDoubleSpinBox()
        self.max_current_spin.setRange(1.0, 125.0)
        self.max_current_spin.setDecimals(1)
        self.max_current_spin.setSuffix(" %")
        self.settle_spin = QDoubleSpinBox()
        self.settle_spin.setRange(0.1, 30.0)
        self.settle_spin.setDecimals(1)
        self.settle_spin.setSuffix(" s")
        self.samples_spin = QSpinBox()
        self.samples_spin.setRange(1, 100)
        self.sample_interval_spin = QDoubleSpinBox()
        self.sample_interval_spin.setRange(0.01, 5.0)
        self.sample_interval_spin.setDecimals(2)
        self.sample_interval_spin.setSuffix(" s")
        self.max_limit_label = QLabel("Max setpoint allowed")
        adv.addRow("Safety abort if measured ≥", self.abort_spin)
        adv.addRow(self.max_limit_label, self.max_setpoint_spin)
        adv.addRow("Max current % allowed", self.max_current_spin)
        adv.addRow("Settle time", self.settle_spin)
        adv.addRow("Samples per point", self.samples_spin)
        adv.addRow("Sample interval", self.sample_interval_spin)
        layout.addLayout(adv)
        return box

    def _build_beam_group(self) -> QGroupBox:
        box = QGroupBox("Optional — spot size for power density")
        form = QFormLayout(box)

        self.spot_source_combo = QComboBox()
        self.spot_source_combo.addItems(["Manual FWHM / 1/e²", "From focus scan (Z height)"])
        self.spot_source_combo.currentIndexChanged.connect(self._on_spot_source_changed)

        self.focus_scan_dir_edit = QLineEdit()
        focus_browse = QPushButton("Browse…")
        focus_browse.clicked.connect(self._browse_focus_scan_dir)
        focus_load = QPushButton("Load Z list")
        focus_load.clicked.connect(self._load_focus_scan)
        dir_row = QHBoxLayout()
        dir_row.addWidget(self.focus_scan_dir_edit, stretch=1)
        dir_row.addWidget(focus_browse)
        dir_row.addWidget(focus_load)

        self.focus_z_combo = QComboBox()
        self.focus_z_combo.currentIndexChanged.connect(self._on_focus_z_changed)

        self.spot_detail_label = QLabel("")
        self.spot_detail_label.setWordWrap(True)

        self.manual_spot_widget = QWidget()
        manual_form = QFormLayout(self.manual_spot_widget)
        self.fwhm_spin = QDoubleSpinBox()
        self.fwhm_spin.setRange(0, 5000)
        self.fwhm_spin.setDecimals(2)
        self.fwhm_spin.setSuffix(" µm")
        self.fwhm_spin.setSpecialValueText("(not used)")
        self.e2_spin = QDoubleSpinBox()
        self.e2_spin.setRange(0, 5000)
        self.e2_spin.setDecimals(2)
        self.e2_spin.setSuffix(" µm")
        self.e2_spin.setSpecialValueText("(not used)")
        manual_form.addRow("FWHM (mean diameter)", self.fwhm_spin)
        manual_form.addRow("1/e² (mean diameter)", self.e2_spin)

        self.focus_scan_widget = QWidget()
        focus_form = QFormLayout(self.focus_scan_widget)
        focus_form.addRow("Focus scan folder", dir_row)
        focus_form.addRow("Z position", self.focus_z_combo)

        form.addRow("Source", self.spot_source_combo)
        form.addRow(self.manual_spot_widget)
        form.addRow(self.focus_scan_widget)
        form.addRow(self.spot_detail_label)
        return box

    def _build_run_group(self) -> QGroupBox:
        box = QGroupBox("Run")
        layout = QHBoxLayout(box)

        self.save_dir_edit = QLineEdit()
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_save_dir)

        self.start_btn = QPushButton("Start sweep")
        self.start_btn.clicked.connect(self._start_sweep)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self._stop_sweep)
        self.stop_btn.setEnabled(False)

        dir_row = QVBoxLayout()
        dir_row.addWidget(QLabel("Save folder"))
        dir_row.addWidget(self.save_dir_edit)
        dir_row.addWidget(browse)

        layout.addLayout(dir_row, stretch=1)
        layout.addWidget(self.start_btn)
        layout.addWidget(self.stop_btn)
        return box

    def _apply_config_to_ui(self) -> None:
        c = self.config
        idx = 1 if c.control_mode == "ttl_current_pct" else 0
        self.control_mode_combo.setCurrentIndex(idx)
        self.laser_port_edit.setText(c.laser_port)
        self.laser_baud_spin.setValue(c.laser_baud)
        self.pm_serial_edit.setText(c.pm_serial)
        if c.wavelength_nm > 0:
            self.wavelength_spin.setValue(c.wavelength_nm)
        default_save = c.save_dir or str(resolve_default_save_root() / "laser_power_sweep")
        self.save_dir_edit.setText(default_save)
        self.setpoint_mode.setCurrentIndex(0 if c.setpoint_mode == "list" else 1)
        self.setpoint_list_edit.setText(c.setpoint_list if c.control_mode == "digital_mw" else c.current_list)
        self.ramp_start.setValue(c.ramp_start_mw)
        self.ramp_step.setValue(c.ramp_step_mw)
        self.ramp_max.setValue(c.ramp_max_mw)
        self.abort_spin.setValue(c.abort_threshold_mw)
        self.max_setpoint_spin.setValue(c.max_setpoint_mw)
        self.max_current_spin.setValue(c.max_current_pct)
        self.settle_spin.setValue(c.settle_s)
        self.samples_spin.setValue(c.num_samples)
        self.sample_interval_spin.setValue(c.sample_interval_s)
        self.fwhm_spin.setValue(c.fwhm_um)
        self.e2_spin.setValue(c.e2_um)
        self.focus_scan_dir_edit.setText(c.focus_scan_dir)
        self.spot_source_combo.setCurrentIndex(1 if c.spot_source == "focus_scan" else 0)
        if c.spot_source == "focus_scan" and c.focus_scan_dir:
            try:
                self._load_focus_scan(select_z=c.focus_scan_z_mm or None, quiet=True)
            except Exception:
                pass
        self._on_spot_source_changed()
        self._on_control_mode_changed()
        self._on_setpoint_list_mode_changed()
        self._update_zero_status()

    def _sync_config_from_ui(self) -> None:
        c = self.config
        c.control_mode = self._control_mode()
        c.laser_port = self.laser_port_edit.text().strip()
        c.laser_baud = self.laser_baud_spin.value()
        c.pm_serial = self.pm_serial_edit.text().strip()
        wl = self.wavelength_spin.value()
        c.wavelength_nm = wl if wl > 0 else 0.0
        c.save_dir = self.save_dir_edit.text().strip()
        c.setpoint_mode = "list" if self.setpoint_mode.currentIndex() == 0 else "ramp"
        c.setpoint_list = self.setpoint_list_edit.text() if c.control_mode == "digital_mw" else c.setpoint_list
        c.current_list = self.setpoint_list_edit.text() if c.control_mode == "ttl_current_pct" else c.current_list
        if c.control_mode == "digital_mw":
            c.ramp_start_mw = self.ramp_start.value()
            c.ramp_step_mw = self.ramp_step.value()
            c.ramp_max_mw = self.ramp_max.value()
        else:
            c.ramp_start_pct = self.ramp_start.value()
            c.ramp_step_pct = self.ramp_step.value()
            c.ramp_max_pct = self.ramp_max.value()
        c.abort_threshold_mw = self.abort_spin.value()
        c.max_setpoint_mw = self.max_setpoint_spin.value()
        c.max_current_pct = self.max_current_spin.value()
        c.settle_s = self.settle_spin.value()
        c.num_samples = self.samples_spin.value()
        c.sample_interval_s = self.sample_interval_spin.value()
        c.fwhm_um = self.fwhm_spin.value()
        c.e2_um = self.e2_spin.value()
        c.focus_scan_dir = self.focus_scan_dir_edit.text().strip()
        c.spot_source = "focus_scan" if self.spot_source_combo.currentIndex() == 1 else "manual"
        if self._focus_scan_points and self.focus_z_combo.currentIndex() >= 0:
            c.focus_scan_z_mm = self._focus_scan_points[self.focus_z_combo.currentIndex()].z_mm
        c.meter_zeroed = self._meter_zeroed
        save_config(c)

    def _spot_from_focus_scan(self) -> bool:
        return self.spot_source_combo.currentIndex() == 1

    def _on_spot_source_changed(self) -> None:
        use_scan = self._spot_from_focus_scan()
        self.manual_spot_widget.setVisible(not use_scan)
        self.focus_scan_widget.setVisible(use_scan)
        if use_scan and not self._focus_scan_points and self.focus_scan_dir_edit.text().strip():
            try:
                self._load_focus_scan(quiet=True)
            except Exception:
                pass
        elif use_scan and self._focus_scan_points:
            self._on_focus_z_changed()

    def _browse_focus_scan_dir(self) -> None:
        start = self.focus_scan_dir_edit.text().strip() or str(Path.home() / "Desktop")
        path = QFileDialog.getExistingDirectory(self, "Focus scan folder", start)
        if path:
            self.focus_scan_dir_edit.setText(path)

    def _load_focus_scan(self, select_z: Optional[float] = None, quiet: bool = False) -> None:
        folder = self.focus_scan_dir_edit.text().strip()
        if not folder:
            if not quiet:
                QMessageBox.warning(self, "Focus scan", "Choose a focus scan folder first.")
            return
        try:
            self._focus_scan_points = load_focus_scan(Path(folder))
        except Exception as exc:
            self._focus_scan_points = []
            self.focus_z_combo.clear()
            if not quiet:
                QMessageBox.critical(self, "Focus scan", str(exc))
            return

        self.focus_z_combo.blockSignals(True)
        self.focus_z_combo.clear()
        select_idx = 0
        for i, pt in enumerate(self._focus_scan_points):
            self.focus_z_combo.addItem(pt.label, pt.z_mm)
            if select_z is not None and abs(pt.z_mm - select_z) < 0.01:
                select_idx = i
        self.focus_z_combo.setCurrentIndex(select_idx)
        self.focus_z_combo.blockSignals(False)
        self._on_focus_z_changed()
        if not quiet:
            self._append_log(f"Loaded {len(self._focus_scan_points)} Z positions from focus scan.")
            self.statusBar().showMessage(f"Focus scan: {len(self._focus_scan_points)} Z positions", 4000)

    def _on_focus_z_changed(self) -> None:
        if not self._focus_scan_points or self.focus_z_combo.currentIndex() < 0:
            return
        pt = self._focus_scan_points[self.focus_z_combo.currentIndex()]
        self.fwhm_spin.setValue(pt.mean_fwhm_um)
        self.e2_spin.setValue(pt.e2_mean_um)
        self.spot_detail_label.setText(
            f"Z = {pt.z_mm:.2f} mm ({pt.folder}) — "
            f"FWHM {pt.fwhm_x_um:.1f} × {pt.fwhm_y_um:.1f} µm (mean {pt.mean_fwhm_um:.1f}), "
            f"1/e² {pt.e2_x_um:.1f} × {pt.e2_y_um:.1f} µm (mean {pt.e2_mean_um:.1f}) — [{pt.rating}]"
        )

    def _spot_sizes_for_sweep(self) -> tuple[Optional[float], Optional[float], Optional[float], str]:
        """Return (fwhm_um, e2_um, focus_z_mm, focus_scan_dir)."""
        fwhm = self.fwhm_spin.value() or None
        e2 = self.e2_spin.value() or None
        z_mm: Optional[float] = None
        scan_dir = ""
        if self._spot_from_focus_scan() and self._focus_scan_points:
            idx = self.focus_z_combo.currentIndex()
            if idx >= 0:
                pt = self._focus_scan_points[idx]
                fwhm = pt.mean_fwhm_um
                e2 = pt.e2_mean_um
                z_mm = pt.z_mm
            scan_dir = self.focus_scan_dir_edit.text().strip()
        return fwhm, e2, z_mm, scan_dir

    def _on_control_mode_changed(self) -> None:
        ttl = self._control_mode() == "ttl_current_pct"
        self.ttl_hint.setVisible(ttl)
        self.max_setpoint_spin.setVisible(not ttl)
        self.max_limit_label.setVisible(not ttl)
        self.max_current_spin.setVisible(ttl)

        if ttl:
            self.config.setpoint_list = self.setpoint_list_edit.text()
            self.list_label.setText("Current levels (%)")
            self.setpoint_list_edit.setText(self.config.current_list)
            self.setpoint_list_edit.setPlaceholderText("e.g. 10, 20, 30, 50, 70, 100")
            self.ramp_start.setValue(self.config.ramp_start_pct)
            self.ramp_step.setValue(self.config.ramp_step_pct)
            self.ramp_max.setValue(self.config.ramp_max_pct)
            self.ramp_start_label.setText("Start (%)")
            self.ramp_step_label.setText("Step (%)")
            self.ramp_max_label.setText("Max (%)")
            self.ramp_start.setRange(0.1, 125.0)
            self.ramp_step.setRange(0.1, 125.0)
            self.ramp_max.setRange(0.1, 125.0)
        else:
            self.config.current_list = self.setpoint_list_edit.text()
            self.list_label.setText("Setpoints (mW)")
            self.setpoint_list_edit.setText(self.config.setpoint_list)
            self.setpoint_list_edit.setPlaceholderText("e.g. 0.5, 1, 2, 5, 10, 20, 40")
            self.ramp_start.setValue(self.config.ramp_start_mw)
            self.ramp_step.setValue(self.config.ramp_step_mw)
            self.ramp_max.setValue(self.config.ramp_max_mw)
            self.ramp_start_label.setText("Start (mW)")
            self.ramp_step_label.setText("Step (mW)")
            self.ramp_max_label.setText("Max (mW)")
            self.ramp_start.setRange(0.01, 50.0)
            self.ramp_step.setRange(0.01, 50.0)
            self.ramp_max.setRange(0.01, 50.0)

        self._update_table_headers()
        if self._laser or self._pm:
            self.statusBar().showMessage("Control mode changed — disconnect and reconnect", 6000)

    def _on_setpoint_list_mode_changed(self) -> None:
        is_list = self.setpoint_mode.currentIndex() == 0
        self.list_widget.setVisible(is_list)
        self.ramp_widget.setVisible(not is_list)

    def _update_table_headers(self) -> None:
        if self._control_mode() == "ttl_current_pct":
            self.table.setHorizontalHeaderLabels(
                ["Set (%)", "Measured (mW)", "—", "—", "Peak I (1/e²)", "Avg I (FWHM)", "Status"]
            )
        else:
            self.table.setHorizontalHeaderLabels(
                [
                    "Set (mW)",
                    "Measured (mW)",
                    "Error (mW)",
                    "Error %",
                    "Peak I (1/e²)",
                    "Avg I (FWHM)",
                    "Status",
                ]
            )

    def _is_connected(self) -> bool:
        return self._laser is not None and self._pm is not None

    def _update_connection_state(self) -> None:
        connected = self._is_connected()
        self.connect_btn.setEnabled(not connected)
        self.disconnect_btn.setEnabled(connected or self._laser is not None or self._pm is not None)
        self.zero_btn.setEnabled(self._pm is not None)
        self.start_btn.setEnabled(connected)
        if connected:
            lid = self._laser_idn[:40] + ("…" if len(self._laser_idn) > 40 else "")
            pid = self._pm_idn[:40] + ("…" if len(self._pm_idn) > 40 else "")
            extra = ""
            self.conn_status.setText(f"Connected — Laser: {lid} | PM: {pid}{extra}")
        else:
            self.conn_status.setText("Not connected")

    def _update_zero_status(self) -> None:
        if self._meter_zeroed:
            self.zero_status.setText("Meter zeroed ✓")
        else:
            self.zero_status.setText("Meter not zeroed — zero before sweep")

    def _append_log(self, msg: str) -> None:
        self.log.append(msg)

    def _connect_instruments(self) -> None:
        self._sync_config_from_ui()
        mode = self._control_mode()
        pm_serial = self.config.pm_serial or None

        try:
            resource = find_pm100d_resource(serial=pm_serial)
            if resource is None:
                QMessageBox.warning(self, "PM100D", "Power meter not found. Check USB connection.")
                return
            pm = PM100D(resource=resource)
            pm.connect()
            self._pm_idn = pm.idn()
            if self.config.wavelength_nm > 0:
                pm.set_wavelength_nm(self.config.wavelength_nm)
            pm.configure_power()
            self._pm = pm
            self._append_log(f"PM100D: {self._pm_idn}")
        except Exception as exc:
            QMessageBox.critical(self, "PM100D", str(exc))
            return

        try:
            laser = OxxiusLaser(
                port=self.config.laser_port,
                baud=self.config.laser_baud,
                safe_power_mw=1.0 if mode == "digital_mw" else None,
                verbose=False,
            )
            self._laser_idn = laser.idn()
            if mode == "ttl_current_pct":
                laser.prepare_for_ttl_modulation()
                laser.ensure_ttl_modulation()
                self._append_log("Laser: TTL modulation armed (ACC + emission ON)")
            self._laser = laser
            self._append_log(f"Laser: {self._laser_idn}")
        except Exception as exc:
            if self._pm:
                self._pm.close()
                self._pm = None
            QMessageBox.critical(self, "Laser", str(exc))
            return

        self._meter_zeroed = False
        self._update_connection_state()
        self._update_zero_status()
        self.statusBar().showMessage("Connected — zero meter with laser OFF before sweep", 8000)

    def _disconnect_instruments(self) -> None:
        if self._worker_thread and self._worker_thread.isRunning():
            QMessageBox.warning(self, "Busy", "Stop the sweep before disconnecting.")
            return
        if self._laser:
            try:
                self._laser.emission_off()
                restore = self._control_mode() == "digital_mw"
                self._laser.close(restore_to_manual_control=restore)
            except Exception:
                pass
            self._laser = None
        if self._pm:
            try:
                self._pm.close()
            except Exception:
                pass
            self._pm = None
        self._laser_idn = ""
        self._pm_idn = ""
        self._update_connection_state()
        self._append_log("Disconnected.")

    def _zero_meter(self) -> None:
        if not self._pm:
            return
        if self._laser and self._control_mode() == "digital_mw":
            try:
                self._laser.emission_off()
            except Exception:
                pass
        try:
            self._append_log("Zeroing PM100D (laser/TTL must be OFF)…")
            self._pm.zero()
            self._meter_zeroed = True
            self._update_zero_status()
            self.statusBar().showMessage("Meter zeroed", 4000)
        except Exception as exc:
            QMessageBox.critical(self, "Zero", str(exc))

    def _browse_save_dir(self) -> None:
        start = self.save_dir_edit.text().strip() or str(resolve_default_save_root())
        path = QFileDialog.getExistingDirectory(self, "Save folder", start)
        if path:
            self.save_dir_edit.setText(path)

    def _resolve_setpoints(self) -> List[float]:
        if self.setpoint_mode.currentIndex() == 0:
            return parse_setpoint_list(self.setpoint_list_edit.text())
        return generate_ramp(
            self.ramp_start.value(),
            self.ramp_step.value(),
            self.ramp_max.value(),
        )

    def _start_sweep(self) -> None:
        if not self._is_connected():
            QMessageBox.warning(self, "Not connected", "Connect all instruments for the selected mode.")
            return
        if not self._meter_zeroed:
            reply = QMessageBox.question(
                self,
                "Meter not zeroed",
                "Power meter has not been zeroed this session. Continue anyway?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        self._sync_config_from_ui()
        mode = self._control_mode()
        try:
            requested = self._resolve_setpoints()
        except ValueError as exc:
            QMessageBox.warning(self, "Setpoints", str(exc))
            return

        if mode == "digital_mw":
            maximum = self.max_setpoint_spin.value()
            accepted, rejected = filter_setpoints(requested, maximum=maximum)
            unit = "mW"
        else:
            maximum = self.max_current_spin.value()
            accepted, rejected = filter_setpoints(requested, maximum=maximum)
            unit = "%"

        if rejected:
            QMessageBox.warning(
                self,
                "Setpoints capped",
                f"Removed {len(rejected)} value(s) above {maximum:g} {unit}: "
                + ", ".join(f"{v:g}" for v in rejected),
            )
        if not accepted:
            QMessageBox.warning(self, "Setpoints", f"No setpoints in (0, {maximum:g}] {unit}.")
            return

        fwhm_um, e2_um, focus_z, focus_dir = self._spot_sizes_for_sweep()

        self.table.setRowCount(0)
        self._append_log(
            f"Starting {mode} sweep: {', '.join(f'{s:g}' for s in accepted)} {unit}"
        )

        if focus_z is not None:
            self._append_log(f"Spot size from focus scan: Z={focus_z:.2f} mm, FWHM={fwhm_um:.1f} µm, 1/e²={e2_um:.1f} µm")

        kwargs = dict(
            control_mode=mode,
            abort_threshold_mw=self.abort_spin.value(),
            settle_s=self.settle_spin.value(),
            num_samples=self.samples_spin.value(),
            sample_interval_s=self.sample_interval_spin.value(),
            fwhm_um=fwhm_um,
            e2_um=e2_um,
        )
        if mode == "digital_mw":
            kwargs["max_setpoint_mw"] = self.max_setpoint_spin.value()
        else:
            kwargs["max_current_pct"] = self.max_current_spin.value()
            self._append_log("TTL mode: hold ~5 V on TTL before/during each point (settle time).")

        if self._worker_thread is not None and self._worker_thread.isRunning():
            QMessageBox.warning(self, "Busy", "Wait for the current sweep to finish.")
            return

        self._worker = SweepWorker(self._laser, self._pm, accepted, kwargs)
        self._worker_thread = QThread()
        self._worker.moveToThread(self._worker_thread)
        self._worker_thread.started.connect(self._worker.run)
        self._worker.point_done.connect(self._on_point_done, Qt.QueuedConnection)
        self._worker.finished.connect(self._on_sweep_finished, Qt.QueuedConnection)
        self._worker.error.connect(self._on_sweep_error, Qt.QueuedConnection)
        self._worker.finished.connect(self._worker_thread.quit)
        self._worker.error.connect(self._worker_thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.error.connect(self._worker.deleteLater)
        self._worker_thread.finished.connect(self._on_worker_thread_finished)

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._worker_thread.start()

    def _on_worker_thread_finished(self) -> None:
        """Clear thread refs only after QThread has fully stopped."""
        self._worker = None
        if self._worker_thread is not None:
            self._worker_thread.deleteLater()
            self._worker_thread = None

    def _stop_sweep(self) -> None:
        if self._worker:
            self._worker.request_stop()
            self._append_log("Stop requested…")

    def _on_point_done(self, pt: SweepPoint, index: int, total: int) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        ttl = pt.setpoint_unit == "current_pct"
        vals = [
            f"{pt.setpoint:.3g}",
            f"{pt.measured_mw:.4f}" if pt.status != "SKIPPED" else "—",
            "—" if ttl else (f"{pt.error_value:+.4f}" if pt.status != "SKIPPED" else "—"),
            "—" if ttl else (f"{pt.error_pct:+.1f}" if pt.status != "SKIPPED" else "—"),
            f"{pt.intensity_from_e2_mw_per_um2:.4f}" if pt.intensity_from_e2_mw_per_um2 is not None else "—",
            f"{pt.intensity_from_fwhm_mw_per_um2:.4f}" if pt.intensity_from_fwhm_mw_per_um2 is not None else "—",
            pt.status,
        ]
        for col, text in enumerate(vals):
            self.table.setItem(row, col, QTableWidgetItem(text))
        unit = "%" if ttl else "mW"
        self._append_log(
            f"[{index}/{total}] set={pt.setpoint:.3g} {unit}  "
            f"measured={pt.measured_mw:.4f} mW  [{pt.status}]"
        )

    def _on_sweep_finished(self, result: SweepResult) -> None:
        self._last_result = result
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

        if self._laser and self._control_mode() == "digital_mw":
            try:
                self._laser.emission_off()
            except Exception:
                pass

        save_dir = Path(self.save_dir_edit.text().strip() or resolve_default_save_root())
        fwhm_um, e2_um, focus_z, focus_dir = self._spot_sizes_for_sweep()
        try:
            requested = self._resolve_setpoints()
        except ValueError:
            requested = []

        try:
            csv_path, json_path, png_path = save_sweep_results(
                result,
                save_dir,
                laser_port=self.config.laser_port,
                laser_idn=self._laser_idn,
                pm_idn=self._pm_idn,
                wavelength_nm=self.config.wavelength_nm or None,
                abort_threshold_mw=self.abort_spin.value(),
                max_setpoint_mw=self.max_setpoint_spin.value(),
                max_current_pct=self.max_current_spin.value(),
                fwhm_um=fwhm_um,
                e2_um=e2_um,
                focus_scan_dir=focus_dir,
                focus_scan_z_mm=focus_z,
                setpoints_requested=requested,
            )
        except Exception as exc:
            self._append_log(f"ERROR saving results: {exc}")
            QMessageBox.critical(self, "Save failed", str(exc))
            return

        self._append_log(f"Saved CSV:  {csv_path}")
        self._append_log(f"Saved JSON: {json_path}")
        self._append_log(f"Saved plot: {png_path}")

        if result.aborted:
            QMessageBox.warning(self, "Sweep aborted", result.abort_reason or "Sweep was aborted.")
            self.statusBar().showMessage("Sweep aborted — partial results saved", 8000)
        else:
            self.statusBar().showMessage("Sweep complete", 5000)

    def _on_sweep_error(self, message: str) -> None:
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        if self._laser and self._control_mode() == "digital_mw":
            try:
                self._laser.emission_off()
            except Exception:
                pass
        self._append_log(f"ERROR: {message}")
        QMessageBox.critical(self, "Sweep error", message)

    def closeEvent(self, event) -> None:
        if self._worker_thread is not None and self._worker_thread.isRunning():
            if self._worker:
                self._worker.request_stop()
            self._worker_thread.quit()
            if not self._worker_thread.wait(10000):
                self._append_log("Warning: sweep thread did not stop cleanly on exit.")
        self._worker = None
        self._worker_thread = None
        self._sync_config_from_ui()
        if self._laser:
            try:
                self._laser.emission_off()
                self._laser.close(restore_to_manual_control=self._control_mode() == "digital_mw")
            except Exception:
                pass
        if self._pm:
            try:
                self._pm.close()
            except Exception:
                pass
        event.accept()


def main() -> int:
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
