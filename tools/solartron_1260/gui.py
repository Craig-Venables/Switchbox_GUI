"""
PyQt5 GUI for Solartron SI 1260 capacitance / impedance sweeps.

SMaRT replacement: connect over GPIB, guided Open → Short → Device,
Origin-ready export, and in-app preview plots.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Optional

import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from engine import (
    SweepConfig,
    SweepEngine,
    SweepResult,
    n_points_from_ppd,
    parse_bias_list,
)
from export import export_bias_series_bundle, export_run_bundle
from instrument import (
    DEFAULT_GPIB_ADDRESS,
    DEFAULT_TIMEOUT_MS,
    list_visa_resources,
    prefer_solartron_address,
)
from paths import (
    DEFAULT_DATA_ROOT,
    DEVICE_NUMBERS,
    SECTION_LETTERS,
    discover_samples,
    migrate_save_root,
    sanitize_notes,
    sanitize_sample_name,
)
from workers import BiasSeriesWorker, ConnectWorker, SweepWorker

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_CONFIG_PATH = _SCRIPT_DIR / "solartron_1260_config.json"
TABLE_HEADERS = ["#", "Frequency (Hz)", "R (Ω)", "X (Ω)", "Cs (F)", "Cp (F)"]


class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, width: float = 5.0, height: float = 4.0) -> None:
        self.fig = Figure(figsize=(width, height), tight_layout=True)
        super().__init__(self.fig)
        self.setParent(parent)


class SolartronMainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Solartron SI 1260 — Capacitance Tool")
        self.resize(1280, 820)

        self.engine = SweepEngine()
        self._connect_worker: Optional[ConnectWorker] = None
        self._sweep_worker: Optional[SweepWorker] = None
        self._bias_worker: Optional[BiasSeriesWorker] = None
        self._last_result: Optional[SweepResult] = None
        self._save_dir = DEFAULT_DATA_ROOT
        self._sample_default = "untitled"
        self._section_default = "A"
        self._device_default = "1"
        self._saved_address = DEFAULT_GPIB_ADDRESS
        self._saved_timeout_ms = DEFAULT_TIMEOUT_MS
        self._saved_f_start = 100.0
        self._saved_f_stop = 1.0e6
        self._saved_ppd = 5
        self._saved_va = 0.1
        self._saved_vb = 0.0
        self._saved_settle = 0.3
        self._saved_bias_start = 0.0
        self._saved_bias_stop = 1.0
        self._saved_bias_step = 0.5
        self._notes_default = ""
        self._auto_connect_pending = False
        self._load_config()

        self._build_ui()
        self._set_connected_ui(False)
        self._refresh_resources()
        self._apply_saved_sweep_values()
        self._refresh_sample_list()
        self._update_save_preview()
        # Auto-connect to GPIB 8 after the window is shown
        QTimer.singleShot(300, self._auto_connect_on_startup)

    @staticmethod
    def _set_layout_visible(layout: QLayout, visible: bool) -> None:
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item is None:
                continue
            w = item.widget()
            if w is not None:
                w.setVisible(visible)
            elif item.layout() is not None:
                SolartronMainWindow._set_layout_visible(item.layout(), visible)

    def _make_collapsible(self, box: QGroupBox, *, start_collapsed: bool = False) -> None:
        """Checkable group box; unchecked hides contents (title stays)."""
        box.setCheckable(True)
        box.setChecked(not start_collapsed)

        def _on_toggled(checked: bool) -> None:
            layout = box.layout()
            if layout is not None:
                self._set_layout_visible(layout, checked)

        box.toggled.connect(_on_toggled)
        _on_toggled(not start_collapsed)

    @staticmethod
    def _equalize_nyquist_axes(ax, x, y, *, pad: float = 0.05) -> None:
        """Match X/Y axis span (same length) with 1:1 aspect for Nyquist."""
        xv = np.asarray(x, dtype=float).ravel()
        yv = np.asarray(y, dtype=float).ravel()
        mask = np.isfinite(xv) & np.isfinite(yv)
        xv, yv = xv[mask], yv[mask]
        if xv.size == 0:
            return
        xmin, xmax = float(np.min(xv)), float(np.max(xv))
        ymin, ymax = float(np.min(yv)), float(np.max(yv))
        xmid = 0.5 * (xmin + xmax)
        ymid = 0.5 * (ymin + ymax)
        half = 0.5 * max(xmax - xmin, ymax - ymin, 1e-30) * (1.0 + pad)
        ax.set_xlim(xmid - half, xmid + half)
        ax.set_ylim(ymid - half, ymid + half)
        ax.set_aspect("equal", adjustable="box")

    def _auto_connect_on_startup(self) -> None:
        """Connect to GPIB0::8::INSTR on launch (quiet failure if offline)."""
        self.edit_address.setText(DEFAULT_GPIB_ADDRESS)
        idx = self.combo_resources.findText(DEFAULT_GPIB_ADDRESS)
        if idx >= 0:
            self.combo_resources.setCurrentIndex(idx)
        self._auto_connect_pending = True
        self.statusBar().showMessage(f"Auto-connecting to {DEFAULT_GPIB_ADDRESS}…")
        self._on_connect()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 8, 8)
        splitter.addWidget(left)

        # Connection
        conn_box = QGroupBox("Connection")
        conn_form = QFormLayout(conn_box)
        self.combo_resources = QComboBox()
        self.combo_resources.setEditable(True)
        self.combo_resources.setMinimumWidth(260)
        self.edit_address = QLineEdit(DEFAULT_GPIB_ADDRESS)
        self.lbl_terminator = QLabel("CRLF (fixed)")
        self.btn_refresh = QPushButton("List resources")
        self.btn_refresh.clicked.connect(self._refresh_resources)
        self.btn_connect = QPushButton("Connect")
        self.btn_connect.clicked.connect(self._on_connect)
        self.btn_disconnect = QPushButton("Disconnect")
        self.btn_disconnect.clicked.connect(self._on_disconnect)
        conn_btns = QHBoxLayout()
        conn_btns.addWidget(self.btn_refresh)
        conn_btns.addWidget(self.btn_connect)
        conn_btns.addWidget(self.btn_disconnect)
        conn_form.addRow("Resources", self.combo_resources)
        conn_form.addRow("GPIB address", self.edit_address)
        conn_form.addRow("Terminator", self.lbl_terminator)
        conn_form.addRow(conn_btns)
        self.combo_resources.currentTextChanged.connect(self._on_resource_picked)
        self._make_collapsible(conn_box, start_collapsed=True)
        left_layout.addWidget(conn_box)

        # Sweep presets
        sweep_box = QGroupBox("Sweep presets")
        sweep_form = QFormLayout(sweep_box)
        self.spin_f_start = QDoubleSpinBox()
        self.spin_f_start.setRange(1e-3, 3.2e7)
        self.spin_f_start.setDecimals(3)
        self.spin_f_start.setValue(100.0)
        self.spin_f_start.setSuffix(" Hz")
        self.spin_f_stop = QDoubleSpinBox()
        self.spin_f_stop.setRange(1e-3, 3.2e7)
        self.spin_f_stop.setDecimals(3)
        self.spin_f_stop.setValue(1.0e6)
        self.spin_f_stop.setSuffix(" Hz")
        self.spin_ppd = QSpinBox()
        self.spin_ppd.setRange(1, 100)
        self.spin_ppd.setValue(5)
        self.spin_ppd.setSuffix(" /dec")
        self.lbl_total_points = QLabel("Total points: —")
        self.spin_va = QDoubleSpinBox()
        self.spin_va.setRange(0.001, 3.0)
        self.spin_va.setDecimals(3)
        self.spin_va.setValue(0.1)
        self.spin_va.setSuffix(" V")
        self.spin_vb = QDoubleSpinBox()
        self.spin_vb.setRange(-40.95, 40.95)
        self.spin_vb.setDecimals(3)
        self.spin_vb.setSingleStep(0.1)
        self.spin_vb.setValue(0.0)
        self.spin_vb.setSuffix(" V")
        self.spin_settle = QDoubleSpinBox()
        self.spin_settle.setRange(0.0, 10.0)
        self.spin_settle.setDecimals(2)
        self.spin_settle.setValue(0.3)
        self.spin_settle.setSuffix(" s")
        self.spin_timeout = QSpinBox()
        self.spin_timeout.setRange(500, 300000)
        self.spin_timeout.setSingleStep(5000)
        self.spin_timeout.setValue(DEFAULT_TIMEOUT_MS)
        self.spin_timeout.setSuffix(" ms")
        sweep_form.addRow("Start frequency", self.spin_f_start)
        sweep_form.addRow("Stop frequency", self.spin_f_stop)
        sweep_form.addRow("Points per decade", self.spin_ppd)
        sweep_form.addRow(self.lbl_total_points)
        sweep_form.addRow("AC amplitude (VA)", self.spin_va)
        sweep_form.addRow("DC bias (VB)", self.spin_vb)
        sweep_form.addRow("Settle time", self.spin_settle)
        sweep_form.addRow("VISA timeout", self.spin_timeout)
        for w in (self.spin_f_start, self.spin_f_stop, self.spin_ppd):
            w.valueChanged.connect(self._update_points_preview)
        self._make_collapsible(sweep_box, start_collapsed=False)
        left_layout.addWidget(sweep_box)
        self._update_points_preview()

        # Bias automation
        bias_box = QGroupBox("Bias automation (VB series)")
        bias_form = QFormLayout(bias_box)
        self.spin_bias_start = QDoubleSpinBox()
        self.spin_bias_start.setRange(-40.95, 40.95)
        self.spin_bias_start.setDecimals(3)
        self.spin_bias_start.setValue(0.0)
        self.spin_bias_start.setSuffix(" V")
        self.spin_bias_stop = QDoubleSpinBox()
        self.spin_bias_stop.setRange(-40.95, 40.95)
        self.spin_bias_stop.setDecimals(3)
        self.spin_bias_stop.setValue(1.0)
        self.spin_bias_stop.setSuffix(" V")
        self.spin_bias_step = QDoubleSpinBox()
        self.spin_bias_step.setRange(0.001, 40.95)
        self.spin_bias_step.setDecimals(3)
        self.spin_bias_step.setValue(0.5)
        self.spin_bias_step.setSuffix(" V")
        self.lbl_bias_preview = QLabel("Levels: —")
        self.lbl_bias_preview.setWordWrap(True)
        self.btn_bias_series = QPushButton("Run bias series (Device only)")
        self.btn_bias_series_corr = QPushButton("Run bias series (Device + correct)")
        bias_form.addRow("Bias start", self.spin_bias_start)
        bias_form.addRow("Bias stop", self.spin_bias_stop)
        bias_form.addRow("Bias step", self.spin_bias_step)
        bias_form.addRow(self.lbl_bias_preview)
        bias_form.addRow(self.btn_bias_series)
        bias_form.addRow(self.btn_bias_series_corr)
        for w in (self.spin_bias_start, self.spin_bias_stop, self.spin_bias_step):
            w.valueChanged.connect(self._update_bias_preview)
        self.btn_bias_series.clicked.connect(
            lambda: self._start_bias_series("device_only")
        )
        self.btn_bias_series_corr.clicked.connect(
            lambda: self._start_bias_series("device")
        )
        self._make_collapsible(bias_box, start_collapsed=False)
        left_layout.addWidget(bias_box)
        self._update_bias_preview()

        # Workflow
        wf_box = QGroupBox("Calibration workflow")
        wf_layout = QVBoxLayout(wf_box)
        self.lbl_cal_status = QLabel("Open: —   Short: —   Device: —")
        self.lbl_prompt = QLabel(
            "Connect, then Open → Short → Device. Cs/Cp are NaN when X ≥ 0 (inductive)."
        )
        self.lbl_prompt.setWordWrap(True)
        self.btn_open = QPushButton("1. Measure Open")
        self.btn_short = QPushButton("2. Measure Short")
        self.btn_device = QPushButton("3. Measure Device (+ correct)")
        self.btn_device_only = QPushButton("Device only (no correction)")
        self.btn_stop = QPushButton("Stop")
        self.btn_clear_cal = QPushButton("Clear calibration")
        for b in (
            self.btn_open,
            self.btn_short,
            self.btn_device,
            self.btn_device_only,
            self.btn_stop,
            self.btn_clear_cal,
        ):
            wf_layout.addWidget(b)
        wf_layout.addWidget(self.lbl_cal_status)
        wf_layout.addWidget(self.lbl_prompt)
        self.btn_open.clicked.connect(lambda: self._start_sweep("open"))
        self.btn_short.clicked.connect(lambda: self._start_sweep("short"))
        self.btn_device.clicked.connect(lambda: self._start_sweep("device"))
        self.btn_device_only.clicked.connect(lambda: self._start_sweep("device_only"))
        self.btn_stop.clicked.connect(self._on_stop)
        self.btn_clear_cal.clicked.connect(self._on_clear_cal)
        self._make_collapsible(wf_box, start_collapsed=False)
        left_layout.addWidget(wf_box)

        # Save / sample identity (same convention as PMU laser tool / Sample GUI)
        save_box = QGroupBox("Sample / save location")
        save_form = QFormLayout(save_box)
        self.combo_sample = QComboBox()
        self.combo_sample.setEditable(True)
        self.combo_sample.setMinimumWidth(160)
        self.combo_sample.setCurrentText(self._sample_default)
        btn_refresh_samples = QPushButton("↻")
        btn_refresh_samples.setFixedWidth(32)
        btn_refresh_samples.setToolTip("Rescan Data_folder for samples")
        btn_refresh_samples.clicked.connect(self._refresh_sample_list)
        sample_row = QHBoxLayout()
        sample_row.addWidget(self.combo_sample)
        sample_row.addWidget(btn_refresh_samples)
        self.combo_section = QComboBox()
        self.combo_section.addItems(SECTION_LETTERS)
        if self._section_default in SECTION_LETTERS:
            self.combo_section.setCurrentText(self._section_default)
        self.combo_device = QComboBox()
        self.combo_device.addItems(DEVICE_NUMBERS)
        if self._device_default in DEVICE_NUMBERS:
            self.combo_device.setCurrentText(self._device_default)
        self.edit_notes = QLineEdit(self._notes_default)
        self.edit_notes.setPlaceholderText("e.g. hrs_after_55, lrs_after, laser")
        self.edit_notes.setToolTip(
            "Optional note baked into folder + CSV names "
            "(hrs / lrs / laser / etc.). Leave blank for a plain run."
        )
        self.edit_save_dir = QLineEdit(str(self._save_dir))
        btn_browse = QPushButton("Browse…")
        btn_browse.clicked.connect(self._browse_save_dir)
        dir_row = QHBoxLayout()
        dir_row.addWidget(self.edit_save_dir)
        dir_row.addWidget(btn_browse)
        self.lbl_save_preview = QLabel("")
        self.lbl_save_preview.setWordWrap(True)
        self.lbl_save_preview.setStyleSheet("color: #444; font-size: 11px;")
        self.lbl_last_save = QLabel("Last export: —")
        self.lbl_last_save.setWordWrap(True)
        save_form.addRow("Sample", sample_row)
        save_form.addRow("Section", self.combo_section)
        save_form.addRow("Device #", self.combo_device)
        save_form.addRow("Run notes", self.edit_notes)
        save_form.addRow("Save root", dir_row)
        save_form.addRow("Path preview", self.lbl_save_preview)
        save_form.addRow(self.lbl_last_save)
        for w in (
            self.combo_sample,
            self.combo_section,
            self.combo_device,
            self.edit_notes,
            self.edit_save_dir,
        ):
            if hasattr(w, "currentTextChanged"):
                w.currentTextChanged.connect(self._update_save_preview)
            if hasattr(w, "editTextChanged"):
                w.editTextChanged.connect(self._update_save_preview)
            if hasattr(w, "textChanged"):
                w.textChanged.connect(self._update_save_preview)
        self._make_collapsible(save_box, start_collapsed=False)
        left_layout.addWidget(save_box)

        note = QLabel(
            "Saves to Data_folder/<Sample>/<Section>/<Device>/Solartron_1260/ "
            "(same tree as the Sample GUI / PMU tool). Settings persist between sessions. "
            "Cs/Cp = NaN when X ≥ 0."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #555; font-size: 11px;")
        left_layout.addWidget(note)
        left_layout.addStretch(1)

        # Right: table + plots
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 8, 8, 8)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        right_layout.addWidget(self.progress)

        self.table = QTableWidget(0, len(TABLE_HEADERS))
        self.table.setHorizontalHeaderLabels(TABLE_HEADERS)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        font = QFont("Consolas")
        font.setStyleHint(QFont.Monospace)
        self.table.setFont(font)
        right_layout.addWidget(self.table, stretch=1)

        self.tabs = QTabWidget()
        self.canvas_c = MplCanvas(width=5, height=3.5)
        self.canvas_bode = MplCanvas(width=5, height=4.5)
        self.canvas_nyq = MplCanvas(width=4.5, height=4.5)
        self.tabs.addTab(self.canvas_c, "C vs f")
        self.tabs.addTab(self.canvas_bode, "Bode")
        self.tabs.addTab(self.canvas_nyq, "Nyquist")
        right_layout.addWidget(self.tabs, stretch=2)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready — list VISA resources and connect.")

    # -------------------------------------------------------------- config
    def _load_config(self) -> None:
        if not _CONFIG_PATH.exists():
            return
        try:
            data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            if data.get("save_dir"):
                self._save_dir = migrate_save_root(Path(data["save_dir"]))
            self._sample_default = data.get("sample_name", self._sample_default) or "untitled"
            self._section_default = data.get("section", self._section_default) or "A"
            self._device_default = str(data.get("device_number", self._device_default) or "1")
            if data.get("gpib_address"):
                self._saved_address = data["gpib_address"]
            if data.get("timeout_ms"):
                self._saved_timeout_ms = int(data["timeout_ms"])
            if "f_start_hz" in data:
                self._saved_f_start = float(data["f_start_hz"])
            if "f_stop_hz" in data:
                self._saved_f_stop = float(data["f_stop_hz"])
            if "points_per_decade" in data:
                self._saved_ppd = int(data["points_per_decade"])
            if "ac_amplitude_v" in data:
                self._saved_va = float(data["ac_amplitude_v"])
            if "dc_bias_v" in data:
                self._saved_vb = float(data["dc_bias_v"])
            if "settle_s" in data:
                self._saved_settle = float(data["settle_s"])
            if "bias_start_v" in data:
                self._saved_bias_start = float(data["bias_start_v"])
            if "bias_stop_v" in data:
                self._saved_bias_stop = float(data["bias_stop_v"])
            if "bias_step_v" in data:
                self._saved_bias_step = float(data["bias_step_v"])
            if "run_notes" in data:
                self._notes_default = str(data.get("run_notes") or "")
        except Exception:
            pass

    def _save_config(self) -> None:
        data = {
            "save_dir": self.edit_save_dir.text().strip() or str(DEFAULT_DATA_ROOT),
            "sample_name": self.combo_sample.currentText().strip() or "untitled",
            "section": self.combo_section.currentText().strip() or "A",
            "device_number": self.combo_device.currentText().strip() or "1",
            "run_notes": self.edit_notes.text().strip(),
            "gpib_address": self.edit_address.text().strip(),
            "timeout_ms": int(self.spin_timeout.value()),
            "f_start_hz": float(self.spin_f_start.value()),
            "f_stop_hz": float(self.spin_f_stop.value()),
            "points_per_decade": int(self.spin_ppd.value()),
            "ac_amplitude_v": float(self.spin_va.value()),
            "dc_bias_v": float(self.spin_vb.value()),
            "settle_s": float(self.spin_settle.value()),
            "bias_start_v": float(self.spin_bias_start.value()),
            "bias_stop_v": float(self.spin_bias_stop.value()),
            "bias_step_v": float(self.spin_bias_step.value()),
        }
        try:
            _CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _apply_saved_sweep_values(self) -> None:
        self.spin_f_start.setValue(self._saved_f_start)
        self.spin_f_stop.setValue(self._saved_f_stop)
        self.spin_ppd.setValue(self._saved_ppd)
        self.spin_va.setValue(self._saved_va)
        self.spin_vb.setValue(self._saved_vb)
        self.spin_settle.setValue(self._saved_settle)
        self.spin_timeout.setValue(int(self._saved_timeout_ms))
        self.spin_bias_start.setValue(self._saved_bias_start)
        self.spin_bias_stop.setValue(self._saved_bias_stop)
        self.spin_bias_step.setValue(self._saved_bias_step)
        if hasattr(self, "edit_notes"):
            self.edit_notes.setText(self._notes_default)
        self._update_points_preview()
        self._update_bias_preview()

    def _refresh_sample_list(self) -> None:
        root = Path(self.edit_save_dir.text().strip() or self._save_dir)
        samples = discover_samples(root)
        current = self.combo_sample.currentText().strip()
        self.combo_sample.blockSignals(True)
        self.combo_sample.clear()
        self.combo_sample.addItems(samples)
        if current:
            self.combo_sample.setCurrentText(current)
        elif self._sample_default:
            self.combo_sample.setCurrentText(self._sample_default)
        self.combo_sample.blockSignals(False)
        self._update_save_preview()

    def _run_notes(self) -> str:
        return sanitize_notes(self.edit_notes.text())

    def _update_save_preview(self) -> None:
        sample = sanitize_sample_name(self.combo_sample.currentText())
        section = self.combo_section.currentText().strip() or "A"
        device = self.combo_device.currentText().strip() or "1"
        root = self.edit_save_dir.text().strip() or str(DEFAULT_DATA_ROOT)
        note = self._run_notes()
        kind = f"device_{note}" if note else "device"
        self.lbl_save_preview.setText(
            f"{root}\\{sample}\\{section}\\{device}\\Solartron_1260\\<N>-{kind}_…"
        )

    def _update_bias_preview(self) -> None:
        try:
            biases = parse_bias_list(
                self.spin_bias_start.value(),
                self.spin_bias_stop.value(),
                self.spin_bias_step.value(),
            )
            preview = ", ".join(f"{v:+.3g}" for v in biases[:12])
            if len(biases) > 12:
                preview += f", … ({len(biases)} total)"
            else:
                preview += f"  ({len(biases)} total)"
            self.lbl_bias_preview.setText(f"Levels: {preview}")
        except Exception as exc:
            self.lbl_bias_preview.setText(f"Levels: invalid ({exc})")

    def _update_points_preview(self) -> None:
        try:
            n = n_points_from_ppd(
                float(self.spin_f_start.value()),
                float(self.spin_f_stop.value()),
                int(self.spin_ppd.value()),
            )
            decades = abs(
                math.log10(
                    float(self.spin_f_stop.value()) / float(self.spin_f_start.value())
                )
            )
            self.lbl_total_points.setText(
                f"Total points: {n}  ({decades:.2f} decades × {self.spin_ppd.value()}/dec)"
            )
        except Exception as exc:
            self.lbl_total_points.setText(f"Total points: invalid ({exc})")

    def _identity(self) -> tuple:
        sample = self.combo_sample.currentText().strip() or "untitled"
        section = self.combo_section.currentText().strip() or "A"
        device = self.combo_device.currentText().strip() or "1"
        root = Path(self.edit_save_dir.text().strip() or DEFAULT_DATA_ROOT)
        return sample, section, device, root

    # ----------------------------------------------------------- connection
    def _refresh_resources(self) -> None:
        self.combo_resources.clear()
        try:
            resources = list(list_visa_resources())
        except Exception as exc:
            self.statusBar().showMessage(f"VISA list failed: {exc}")
            resources = []
        self.combo_resources.addItems(resources)
        saved = getattr(self, "_saved_address", DEFAULT_GPIB_ADDRESS)
        if saved in resources:
            addr = saved
        else:
            addr = prefer_solartron_address(resources)
        self.edit_address.setText(addr)
        idx = self.combo_resources.findText(addr)
        if idx >= 0:
            self.combo_resources.setCurrentIndex(idx)

    def _on_resource_picked(self, text: str) -> None:
        if text.strip():
            self.edit_address.setText(text.strip())

    def _current_config(self) -> SweepConfig:
        sample, _, _, root = self._identity()
        return SweepConfig(
            gpib_address=self.edit_address.text().strip() or DEFAULT_GPIB_ADDRESS,
            timeout_ms=int(self.spin_timeout.value()),
            terminator="crlf",
            f_start_hz=float(self.spin_f_start.value()),
            f_stop_hz=float(self.spin_f_stop.value()),
            points_per_decade=int(self.spin_ppd.value()),
            ac_amplitude_v=float(self.spin_va.value()),
            dc_bias_v=float(self.spin_vb.value()),
            settle_s=float(self.spin_settle.value()),
            sample_name=sanitize_sample_name(sample),
            save_dir=str(root),
        )

    def _on_connect(self) -> None:
        if self._connect_worker and self._connect_worker.isRunning():
            return
        cfg = self._current_config()
        self._set_busy(True)
        self.statusBar().showMessage(f"Connecting to {cfg.gpib_address}…")
        self._connect_worker = ConnectWorker(self.engine, cfg, parent=self)
        self._connect_worker.finished_ok.connect(self._on_connected)
        self._connect_worker.failed.connect(self._on_connect_failed)
        self._connect_worker.start()

    def _on_connected(self, resources: list) -> None:
        self._set_busy(False)
        self._set_connected_ui(True)
        was_auto = self._auto_connect_pending
        self._auto_connect_pending = False
        self._save_config()
        self.statusBar().showMessage(
            f"Connected to {self.edit_address.text().strip()} "
            f"({'auto' if was_auto else 'manual'}). Ready for Open/Short/Device."
        )
        self.lbl_prompt.setText(
            "Probe OPEN (leads apart), then click Measure Open."
        )

    def _on_connect_failed(self, message: str) -> None:
        self._set_busy(False)
        self._set_connected_ui(False)
        if self._auto_connect_pending:
            self._auto_connect_pending = False
            self.statusBar().showMessage(
                f"Auto-connect failed ({DEFAULT_GPIB_ADDRESS}). "
                "Expand Connection and connect manually."
            )
            return
        QMessageBox.critical(self, "Connection failed", message)
        self.statusBar().showMessage("Connection failed.")

    def _on_disconnect(self) -> None:
        self.engine.disconnect()
        self._set_connected_ui(False)
        self.statusBar().showMessage("Disconnected.")

    def _set_connected_ui(self, connected: bool) -> None:
        self.btn_connect.setEnabled(not connected)
        self.btn_disconnect.setEnabled(connected)
        measuring = self._is_sweeping()
        for b in (
            self.btn_open,
            self.btn_short,
            self.btn_device,
            self.btn_device_only,
            self.btn_bias_series,
            self.btn_bias_series_corr,
        ):
            b.setEnabled(connected and not measuring)

    def _is_sweeping(self) -> bool:
        return bool(
            (self._sweep_worker and self._sweep_worker.isRunning())
            or (self._bias_worker and self._bias_worker.isRunning())
        )

    def _set_busy(self, busy: bool) -> None:
        connected = self.engine.connected
        self.btn_connect.setEnabled(not busy and not connected)
        self.btn_disconnect.setEnabled(not busy and connected)
        self.btn_refresh.setEnabled(not busy)
        for b in (
            self.btn_open,
            self.btn_short,
            self.btn_device,
            self.btn_device_only,
            self.btn_clear_cal,
            self.btn_bias_series,
            self.btn_bias_series_corr,
        ):
            b.setEnabled(not busy and connected)
        self.btn_stop.setEnabled(busy and self._is_sweeping())

    # --------------------------------------------------------------- sweeps
    def _start_sweep(self, role: str) -> None:
        if not self.engine.connected:
            QMessageBox.warning(self, "Not connected", "Connect to the instrument first.")
            return
        if self._is_sweeping():
            return
        if role == "device" and (
            self.engine.store.open_result is None or self.engine.store.short_result is None
        ):
            reply = QMessageBox.question(
                self,
                "Missing calibration",
                "Open and/or Short not measured yet.\n"
                "Continue as Device only (no correction)?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
            role = "device_only"

        prompts = {
            "open": "Measuring OPEN — keep probes open.",
            "short": "Measuring SHORT — short the probes.",
            "device": "Measuring DEVICE — mount the sample.",
            "device_only": "Measuring DEVICE (no open/short correction).",
        }
        self.lbl_prompt.setText(prompts.get(role, "Measuring…"))
        self._clear_table()
        self.progress.setValue(0)
        cfg = self._current_config()
        self._sweep_worker = SweepWorker(self.engine, cfg, role, parent=self)
        self._sweep_worker.progress.connect(self._on_progress)
        self._sweep_worker.finished_ok.connect(self._on_sweep_done)
        self._sweep_worker.failed.connect(self._on_sweep_failed)
        self._sweep_worker.status.connect(self.statusBar().showMessage)
        self._set_busy(True)
        self.btn_stop.setEnabled(True)
        self._sweep_worker.start()

    def _on_stop(self) -> None:
        if self._sweep_worker and self._sweep_worker.isRunning():
            self._sweep_worker.request_cancel()
            self.statusBar().showMessage("Cancel requested…")
        if self._bias_worker and self._bias_worker.isRunning():
            self._bias_worker.request_cancel()
            self.statusBar().showMessage("Bias series cancel requested…")

    def _start_bias_series(self, role: str) -> None:
        if not self.engine.connected:
            QMessageBox.warning(self, "Not connected", "Connect to the instrument first.")
            return
        if self._is_sweeping():
            return
        if role == "device" and (
            self.engine.store.open_result is None or self.engine.store.short_result is None
        ):
            QMessageBox.warning(
                self,
                "Missing calibration",
                "Measure Open and Short first, or use Device-only bias series.",
            )
            return
        try:
            biases = parse_bias_list(
                self.spin_bias_start.value(),
                self.spin_bias_stop.value(),
                self.spin_bias_step.value(),
            )
        except Exception as exc:
            QMessageBox.critical(self, "Invalid bias list", str(exc))
            return
        if len(biases) > 200:
            reply = QMessageBox.question(
                self,
                "Long bias series",
                f"{len(biases)} bias levels — continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        self._clear_table()
        self.progress.setValue(0)
        cfg = self._current_config()
        self.lbl_prompt.setText(
            f"Bias series ({role}): {len(biases)} levels using current f-sweep presets."
        )
        self._bias_worker = BiasSeriesWorker(
            self.engine, cfg, biases, role=role, parent=self
        )
        self._bias_worker.progress.connect(self._on_progress)
        self._bias_worker.bias_progress.connect(self._on_bias_progress)
        self._bias_worker.finished_ok.connect(self._on_bias_series_done)
        self._bias_worker.failed.connect(self._on_sweep_failed)
        self._bias_worker.status.connect(self.statusBar().showMessage)
        self._set_busy(True)
        self.btn_stop.setEnabled(True)
        self._bias_worker.start()

    def _on_bias_progress(self, index: int, total: int, bias_v: float) -> None:
        self.spin_vb.setValue(float(bias_v))
        self._clear_table()
        self.progress.setValue(0)
        self.statusBar().showMessage(
            f"Bias {index}/{total}: VB={bias_v:+.3f} V — frequency sweep…"
        )
        self.lbl_prompt.setText(f"Measuring at VB={bias_v:+.3f} V ({index}/{total})")

    def _on_bias_series_done(self, results: object) -> None:
        assert isinstance(results, list)
        self._set_busy(False)
        if not results:
            self.statusBar().showMessage("Bias series produced no results.")
            return
        self._last_result = results[-1]
        self._update_cal_label()
        self._update_plots(results[-1])
        self.progress.setValue(100)
        try:
            sample, section, device, root = self._identity()
            run_dir = export_bias_series_bundle(
                results,
                save_root=root,
                sample=sample,
                section=section,
                device=device,
                notes=self._run_notes(),
                open_result=self.engine.store.open_result,
                short_result=self.engine.store.short_result,
            )
            self.lbl_last_save.setText(f"Last export: {run_dir}")
            self._save_config()
            self._refresh_sample_list()
            compare_dir = run_dir.parent / "origin_compare"
            self.statusBar().showMessage(
                f"Bias series done ({len(results)} levels) → {run_dir}  "
                f"| compare refreshed → {compare_dir}"
            )
            self.lbl_prompt.setText(
                f"Bias series complete: Origin CSVs + device compare plots updated."
            )
        except Exception as exc:
            QMessageBox.warning(self, "Export failed", str(exc))
            self.statusBar().showMessage(f"Series OK but export failed: {exc}")

    def _on_clear_cal(self) -> None:
        self.engine.clear_calibration()
        self._update_cal_label()
        self.lbl_prompt.setText("Calibration cleared. Measure Open next.")
        self.statusBar().showMessage("Calibration store cleared.")

    def _on_progress(self, current: int, total: int, point: dict) -> None:
        pct = int(100 * current / max(total, 1))
        self.progress.setValue(pct)
        row = self.table.rowCount()
        self.table.insertRow(row)
        values = [
            str(current),
            f"{point['frequency_hz']:.6g}",
            f"{point['r_ohm']:.6g}",
            f"{point['x_ohm']:.6g}",
            f"{point['cs_f']:.6g}",
            f"{point['cp_f']:.6g}",
        ]
        for col, text in enumerate(values):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() ^ Qt.ItemIsEditable)
            self.table.setItem(row, col, item)
        self.table.scrollToBottom()
        self.statusBar().showMessage(
            f"Point {current}/{total}: f={point['frequency_hz']:.4g} Hz"
        )

    def _on_sweep_done(self, result: object) -> None:
        assert isinstance(result, SweepResult)
        self._set_busy(False)
        self._last_result = result
        self._update_cal_label()
        self._update_plots(result)
        self.progress.setValue(100)

        if result.role in ("device", "device_only"):
            try:
                sample, section, device, root = self._identity()
                run_dir = export_run_bundle(
                    result,
                    save_root=root,
                    sample=sample,
                    section=section,
                    device=device,
                    kind=result.role,
                    notes=self._run_notes(),
                    open_result=self.engine.store.open_result,
                    short_result=self.engine.store.short_result,
                )
                self.lbl_last_save.setText(f"Last export: {run_dir}")
                self._save_config()
                self._refresh_sample_list()
                compare_dir = run_dir.parent / "origin_compare"
                self.statusBar().showMessage(
                    f"Saved → {run_dir}  | compare refreshed → {compare_dir}"
                )
                self.lbl_prompt.setText(
                    "Device sweep complete. Origin CSV saved; device compare plots updated."
                )
            except Exception as exc:
                QMessageBox.warning(self, "Export failed", str(exc))
                self.statusBar().showMessage(f"Sweep OK but export failed: {exc}")
        elif result.role == "open":
            self.lbl_prompt.setText("Open done. Short the probes, then Measure Short.")
            self.statusBar().showMessage("Open sweep complete.")
        elif result.role == "short":
            self.lbl_prompt.setText("Short done. Mount the DUT, then Measure Device.")
            self.statusBar().showMessage("Short sweep complete.")

    def _on_sweep_failed(self, message: str) -> None:
        self._set_busy(False)
        self.statusBar().showMessage(message)
        if "cancel" in message.lower():
            QMessageBox.information(self, "Cancelled", message)
        else:
            QMessageBox.critical(self, "Sweep failed", message)

    def _clear_table(self) -> None:
        self.table.setRowCount(0)

    def _update_cal_label(self) -> None:
        store = self.engine.store

        def mark(res: Optional[SweepResult]) -> str:
            return "OK" if res is not None else "—"

        self.lbl_cal_status.setText(
            f"Open: {mark(store.open_result)}   "
            f"Short: {mark(store.short_result)}   "
            f"Device: {mark(store.device_result)}"
        )

    # ---------------------------------------------------------------- plots
    def _update_plots(self, result: SweepResult) -> None:
        src = result.corrected if result.corrected is not None else result
        f = src.frequencies_hz
        c = np.abs(src.cp_f)
        mag = src.z_mag_ohm
        phase = src.phase_deg
        r = src.r_ohm
        x = src.x_ohm

        # C vs f
        self.canvas_c.fig.clear()
        ax_c = self.canvas_c.fig.add_subplot(111)
        valid = np.isfinite(c) & (c > 0)
        if np.any(valid):
            ax_c.loglog(f[valid], c[valid], ".-")
        ax_c.set_xlabel("Frequency (Hz)")
        ax_c.set_ylabel("|Cp| (F)")
        ax_c.set_title("Capacitance vs Frequency")
        ax_c.grid(True, which="both", alpha=0.3)
        self.canvas_c.draw()

        # Bode
        self.canvas_bode.fig.clear()
        ax_m = self.canvas_bode.fig.add_subplot(211)
        ax_p = self.canvas_bode.fig.add_subplot(212, sharex=ax_m)
        ax_m.loglog(f, mag, ".-")
        ax_m.set_ylabel("|Z| (Ω)")
        ax_m.grid(True, which="both", alpha=0.3)
        ax_m.set_title("Bode")
        ax_p.semilogx(f, phase, ".-")
        ax_p.set_xlabel("Frequency (Hz)")
        ax_p.set_ylabel("Phase (°)")
        ax_p.grid(True, which="both", alpha=0.3)
        self.canvas_bode.fig.tight_layout()
        self.canvas_bode.draw()

        # Nyquist (-Im vs Re) — equal X/Y axis length
        self.canvas_nyq.fig.clear()
        ax_n = self.canvas_nyq.fig.add_subplot(111)
        y_nyq = -x
        ax_n.plot(r, y_nyq, ".-")
        ax_n.set_xlabel("Re(Z) (Ω)")
        ax_n.set_ylabel("-Im(Z) (Ω)")
        ax_n.set_title("Nyquist")
        ax_n.grid(True, alpha=0.3)
        self._equalize_nyquist_axes(ax_n, r, y_nyq)
        self.canvas_nyq.draw()

    def _browse_save_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Select Data_folder root", self.edit_save_dir.text()
        )
        if path:
            self.edit_save_dir.setText(path)
            self._save_dir = Path(path)
            self._refresh_sample_list()
            self._save_config()

    def closeEvent(self, event) -> None:  # noqa: N802
        try:
            if self._is_sweeping():
                self.engine.request_cancel()
            if self._sweep_worker and self._sweep_worker.isRunning():
                self._sweep_worker.wait(2000)
            if self._bias_worker and self._bias_worker.isRunning():
                self._bias_worker.wait(2000)
            self.engine.disconnect()
            self._save_config()
        finally:
            event.accept()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Solartron SI 1260 Capacitance Tool")
    win = SolartronMainWindow()
    win.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
