"""Standalone calibration GUI for the FC-2901V mass flow controller.

Can be launched directly:
    python calibration_gui.py

Or opened from the main dashboard via the "Calibration Tool..." button.

On startup the window auto-loads calibration.json from its own directory.
If not found the user is asked to browse for one or start fresh.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from PyQt5.QtCore import Qt, QRect, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QBrush
from PyQt5.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

try:
    from .calibration import (
        apply_correction,
        build_calibration_record,
        fit_model,
        load_calibration,
        save_calibration,
    )
except ImportError:
    from calibration import (
        apply_correction,
        build_calibration_record,
        fit_model,
        load_calibration,
        save_calibration,
    )

try:
    from .main import STYLESHEET
except ImportError:
    try:
        from main import STYLESHEET
    except ImportError:
        STYLESHEET = ""


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CALIBRATION_PATH = BASE_DIR / "calibration.json"

COMMON_GASES = ["N\u2082", "Ar", "O\u2082", "Air", "He", "CO\u2082", "H\u2082", "CH\u2084", "Other"]


# ──────────────────────────────────────────────────────────────────────────────
# Fit chart widget
# ──────────────────────────────────────────────────────────────────────────────

class CalibrationChartWidget(QWidget):
    """QPainter scatter plot with polynomial fit overlay.

    X-axis: device reading (sccm)
    Y-axis: reference reading (sccm)
    The ideal 1:1 line is shown as a dim dashed guide.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._points: List[Tuple[float, float]] = []
        self._fit_coeffs: Optional[List[float]] = None
        self._full_scale: float = 200.0
        self.setMinimumSize(180, 160)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_data(
        self,
        points: List[Tuple[float, float]],
        fit_coeffs: Optional[List[float]],
        full_scale: float,
    ) -> None:
        self._points = points
        self._fit_coeffs = fit_coeffs
        self._full_scale = max(1.0, float(full_scale))
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()

        ml, mt, mr, mb = 42, 10, 14, 32
        pw = W - ml - mr
        ph = H - mt - mb

        if pw < 10 or ph < 10:
            return

        fs = self._full_scale

        def to_screen(x: float, y: float) -> Tuple[int, int]:
            sx = ml + int(max(0.0, min(x, fs * 1.1)) / (fs * 1.1) * pw)
            sy = mt + int((1.0 - max(0.0, min(y, fs * 1.1)) / (fs * 1.1)) * ph)
            return sx, sy

        # Background
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#141626"))
        p.drawRect(ml, mt, pw, ph)

        # Grid
        grid_pen = QPen(QColor("#1e2440"), 1, Qt.DotLine)
        p.setPen(grid_pen)
        for i in range(5):
            t = i / 4
            sy = mt + int((1.0 - t) * ph)
            p.drawLine(ml, sy, ml + pw, sy)
            sx = ml + int(t * pw)
            p.drawLine(sx, mt, sx, mt + ph)

        # Ideal 1:1 line
        p.setPen(QPen(QColor("#2a3a5a"), 1, Qt.DashLine))
        sx0, sy0 = to_screen(0, 0)
        sx1, sy1 = to_screen(fs, fs)
        p.drawLine(sx0, sy0, sx1, sy1)

        # Fit curve
        if self._fit_coeffs and len(self._fit_coeffs) >= 2:
            pen = QPen(QColor("#4878d0"), 1)
            p.setPen(pen)
            prev: Optional[Tuple[int, int]] = None
            for i in range(61):
                x = i / 60.0 * fs
                y = float(np.polyval(self._fit_coeffs, x))
                sx, sy = to_screen(x, y)
                if prev:
                    p.drawLine(prev[0], prev[1], sx, sy)
                prev = (sx, sy)

        # Data points
        p.setPen(QPen(QColor("#b0c8ff"), 1))
        p.setBrush(QColor("#5890e0"))
        for dev, ref in self._points:
            sx, sy = to_screen(dev, ref)
            p.drawEllipse(sx - 4, sy - 4, 8, 8)

        # Axis tick labels
        lbl_font = QFont("Segoe UI", 7)
        p.setFont(lbl_font)
        for i in range(5):
            t = i / 4
            v = int(fs * t)
            # X
            sx = ml + int(t * pw)
            p.setPen(QColor("#404870"))
            p.drawText(QRect(sx - 14, mt + ph + 4, 28, 14), Qt.AlignCenter, str(v))
            # Y
            sy = mt + int((1.0 - t) * ph)
            p.drawText(QRect(2, sy - 7, ml - 4, 14), Qt.AlignRight | Qt.AlignVCenter, str(v))

        # Axis titles
        p.setPen(QColor("#353a60"))
        p.drawText(QRect(ml, mt + ph + 18, pw, 12), Qt.AlignCenter, "Device (sccm)")

        # Border
        p.setPen(QPen(QColor("#2a3050"), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRect(ml, mt, pw, ph)


# ──────────────────────────────────────────────────────────────────────────────
# Calibration window
# ──────────────────────────────────────────────────────────────────────────────

class CalibrationWindow(QMainWindow):
    """Multi-point calibration editor.

    Workflow:
      1. Enter device and reference readings side-by-side in the table.
      2. Click "Fit Model" to compute a polynomial correction.
      3. Click "Save Calibration" — the file is written and the main window
         reloads it automatically via the *calibration_saved* signal.
    """

    calibration_saved = pyqtSignal(object)  # emits Path when saved

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("FC-2901V \u2014 Calibration Tool")
        self.resize(900, 640)
        self._cal_path: Optional[Path] = None
        self._last_fit: Optional[Dict] = None
        self._build_ui()
        self._startup_load()

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("calroot")
        root.setStyleSheet("QWidget#calroot { background: #1a1d2e; }")
        self.setCentralWidget(root)

        main = QVBoxLayout(root)
        main.setContentsMargins(10, 10, 10, 8)
        main.setSpacing(8)

        # Top status bar
        top = QHBoxLayout()
        self._status_lbl = QLabel("No calibration loaded")
        self._status_lbl.setStyleSheet("color: #6080a8; font-style: italic;")
        load_btn = QPushButton("Load JSON\u2026")
        load_btn.clicked.connect(self._load_from_file)
        top.addWidget(self._status_lbl, 1)
        top.addWidget(load_btn)
        main.addLayout(top)

        # Splitter: left controls / right chart
        splitter = QSplitter(Qt.Horizontal)

        # ── Left panel ──────────────────────────────────────────────────────
        left = QWidget()
        left_col = QVBoxLayout(left)
        left_col.setContentsMargins(0, 0, 6, 0)
        left_col.setSpacing(8)

        # Metadata
        meta = QGroupBox("Calibration Details")
        mg = QGridLayout(meta)
        mg.setSpacing(6)

        self._gas_combo = QComboBox()
        self._gas_combo.addItems(COMMON_GASES)
        self._gas_edit = QLineEdit()
        self._gas_edit.setPlaceholderText("Custom gas name")
        self._gas_edit.setVisible(False)
        self._gas_combo.currentTextChanged.connect(self._on_gas_changed)

        self._fs_spin = QDoubleSpinBox()
        self._fs_spin.setRange(1.0, 99999.0)
        self._fs_spin.setValue(200.0)
        self._fs_spin.setSuffix(" sccm")
        self._fs_spin.setFixedWidth(120)
        self._fs_spin.valueChanged.connect(self._update_chart)

        self._notes_edit = QLineEdit()
        self._notes_edit.setPlaceholderText("Optional notes\u2026")

        mg.addWidget(QLabel("Gas:"), 0, 0)
        mg.addWidget(self._gas_combo, 0, 1)
        mg.addWidget(self._gas_edit, 0, 2)
        mg.addWidget(QLabel("Full scale:"), 1, 0)
        mg.addWidget(self._fs_spin, 1, 1)
        mg.addWidget(QLabel("Notes:"), 2, 0)
        mg.addWidget(self._notes_edit, 2, 1, 1, 2)
        left_col.addWidget(meta)

        # Points table
        pts_box = QGroupBox("Calibration Points")
        pts_col = QVBoxLayout(pts_box)
        pts_col.setSpacing(6)

        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["Device reading (sccm)", "Reference reading (sccm)"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(
            "QTableWidget { alternate-background-color: #1e2340; }"
        )
        self._table.itemChanged.connect(self._on_table_changed)
        pts_col.addWidget(self._table, 1)

        tbl_btns = QHBoxLayout()
        add_btn = QPushButton("+ Add Row")
        add_btn.clicked.connect(self._add_row)
        self._del_btn = QPushButton("Remove Selected")
        self._del_btn.clicked.connect(self._remove_selected)
        clr_btn = QPushButton("Clear All")
        clr_btn.clicked.connect(self._clear_all)
        tbl_btns.addWidget(add_btn)
        tbl_btns.addWidget(self._del_btn)
        tbl_btns.addWidget(clr_btn)
        pts_col.addLayout(tbl_btns)
        left_col.addWidget(pts_box, 1)

        # Fit panel
        fit_box = QGroupBox("Model Fitting")
        fit_col = QVBoxLayout(fit_box)
        fit_col.setSpacing(6)

        order_row = QHBoxLayout()
        order_row.addWidget(QLabel("Fit order:"))
        self._order_1 = QRadioButton("Linear (1st order)")
        self._order_1.setChecked(True)
        self._order_2 = QRadioButton("Quadratic (2nd order)")
        order_grp = QButtonGroup(self)
        order_grp.addButton(self._order_1, 1)
        order_grp.addButton(self._order_2, 2)
        order_row.addWidget(self._order_1)
        order_row.addWidget(self._order_2)
        order_row.addStretch()
        fit_col.addLayout(order_row)

        self._metrics_lbl = QLabel("")
        self._metrics_lbl.setStyleSheet("color: #7090c0; font-size: 9pt;")
        self._metrics_lbl.setWordWrap(True)
        self._metrics_lbl.setMinimumHeight(42)
        fit_col.addWidget(self._metrics_lbl)

        act_row = QHBoxLayout()
        self._fit_btn = QPushButton("Fit Model")
        self._fit_btn.clicked.connect(self._fit_model)
        self._save_btn = QPushButton("Save Calibration\u2026")
        self._save_btn.setObjectName("connect_btn")
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._save_calibration)
        act_row.addWidget(self._fit_btn)
        act_row.addWidget(self._save_btn)
        fit_col.addLayout(act_row)
        left_col.addWidget(fit_box)

        # ── Right panel (chart) ──────────────────────────────────────────────
        right = QWidget()
        right_col = QVBoxLayout(right)
        right_col.setContentsMargins(6, 0, 0, 0)

        chart_box = QGroupBox("Fit Chart  (device \u2192 reference)")
        chart_layout = QVBoxLayout(chart_box)
        self._chart = CalibrationChartWidget()
        chart_layout.addWidget(self._chart, 1)

        legend = QHBoxLayout()
        for color, txt in (("#5890e0", "data points"), ("#4878d0", "fit curve"), ("#2a3a5a", "1:1 ideal")):
            dot = QLabel("\u25cf")
            dot.setStyleSheet(f"color: {color}; font-size: 14pt;")
            lbl = QLabel(txt)
            lbl.setStyleSheet("color: #505878; font-size: 9pt;")
            legend.addWidget(dot)
            legend.addWidget(lbl)
            legend.addSpacing(12)
        legend.addStretch()
        chart_layout.addLayout(legend)
        right_col.addWidget(chart_box, 1)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([500, 380])
        main.addWidget(splitter, 1)

    # ── Startup ──────────────────────────────────────────────────────────────

    def _startup_load(self) -> None:
        if DEFAULT_CALIBRATION_PATH.exists():
            self._load_calibration(DEFAULT_CALIBRATION_PATH)
        else:
            msg = QMessageBox(self)
            msg.setWindowTitle("Calibration file not found")
            msg.setText("No calibration file was found at the default location.")
            msg.setInformativeText(
                f"{DEFAULT_CALIBRATION_PATH}\n\n"
                "Would you like to browse for an existing file, or start a new calibration?"
            )
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg.setDefaultButton(QMessageBox.No)
            msg.button(QMessageBox.Yes).setText("Browse\u2026")
            msg.button(QMessageBox.No).setText("Start fresh")
            if msg.exec_() == QMessageBox.Yes:
                self._load_from_file()

    # ── File operations ───────────────────────────────────────────────────────

    def _load_from_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Calibration JSON", str(BASE_DIR),
            "JSON files (*.json);;All files (*.*)",
        )
        if path:
            self._load_calibration(Path(path))

    def _load_calibration(self, path: Path) -> None:
        try:
            data = load_calibration(path)
        except Exception as exc:
            QMessageBox.warning(self, "Load failed", str(exc))
            return

        self._cal_path = path

        # Gas
        gas = data.get("gas", "N\u2082")
        idx = self._gas_combo.findText(gas)
        if idx >= 0:
            self._gas_combo.setCurrentIndex(idx)
        else:
            other_idx = self._gas_combo.findText("Other")
            self._gas_combo.setCurrentIndex(other_idx if other_idx >= 0 else 0)
            self._gas_edit.setText(gas)

        self._fs_spin.setValue(float(data.get("full_scale_sccm", 200.0)))
        self._notes_edit.setText(data.get("notes", ""))

        # Points table
        self._table.blockSignals(True)
        self._table.setRowCount(0)
        for pt in data.get("points", []):
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(f"{pt.get('device_sccm', 0):.4f}"))
            self._table.setItem(row, 1, QTableWidgetItem(f"{pt.get('reference_sccm', 0):.4f}"))
        self._table.blockSignals(False)

        # Fit order
        order = data.get("fit", {}).get("order", 1)
        (self._order_2 if order == 2 else self._order_1).setChecked(True)

        self._last_fit = data.get("fit") or None
        if self._last_fit:
            self._save_btn.setEnabled(True)
            self._show_metrics(self._last_fit)

        self._status_lbl.setText(f"Loaded: {path.name}")
        self._status_lbl.setStyleSheet("color: #50c880; font-style: normal;")
        self._update_chart()

    # ── Table helpers ─────────────────────────────────────────────────────────

    def _add_row(self) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QTableWidgetItem("0.0000"))
        self._table.setItem(row, 1, QTableWidgetItem("0.0000"))
        self._table.scrollToBottom()
        self._table.editItem(self._table.item(row, 0))

    def _remove_selected(self) -> None:
        rows = sorted(
            {idx.row() for idx in self._table.selectedIndexes()}, reverse=True
        )
        for row in rows:
            self._table.removeRow(row)
        self._invalidate_fit()

    def _clear_all(self) -> None:
        if self._table.rowCount() == 0:
            return
        if QMessageBox.question(
            self, "Clear all", "Remove all calibration points?",
            QMessageBox.Yes | QMessageBox.No,
        ) == QMessageBox.Yes:
            self._table.setRowCount(0)
            self._invalidate_fit()

    def _on_table_changed(self) -> None:
        self._invalidate_fit()

    def _on_gas_changed(self, text: str) -> None:
        self._gas_edit.setVisible(text == "Other")

    def _invalidate_fit(self) -> None:
        self._last_fit = None
        self._save_btn.setEnabled(False)
        self._metrics_lbl.setText("")
        self._update_chart()

    def _get_points(self) -> Optional[List[Tuple[float, float]]]:
        pts: List[Tuple[float, float]] = []
        for row in range(self._table.rowCount()):
            try:
                dev = float(self._table.item(row, 0).text())
                ref = float(self._table.item(row, 1).text())
                pts.append((dev, ref))
            except (ValueError, AttributeError):
                QMessageBox.warning(self, "Invalid data",
                                    f"Row {row + 1} has invalid data. Enter numeric values.")
                return None
        return pts

    # ── Fitting ───────────────────────────────────────────────────────────────

    def _fit_model(self) -> None:
        pts = self._get_points()
        if pts is None:
            return
        n = len(pts)
        if n < 2:
            QMessageBox.warning(self, "Not enough points",
                                "At least 2 calibration points are required.")
            return
        order = 2 if self._order_2.isChecked() else 1
        if order == 2 and n < 3:
            QMessageBox.warning(self, "Not enough points",
                                "Quadratic fit requires at least 3 points.")
            return
        try:
            dev_vals = [p[0] for p in pts]
            ref_vals = [p[1] for p in pts]
            result = fit_model(dev_vals, ref_vals, order)
            self._last_fit = result
            self._save_btn.setEnabled(True)
            self._show_metrics(result)
            self._update_chart()
        except Exception as exc:
            QMessageBox.critical(self, "Fit error", str(exc))

    def _show_metrics(self, fit: Dict) -> None:
        order = fit.get("order", 1)
        coeffs = fit.get("coefficients", [])
        rmse = fit.get("rmse_sccm", 0.0)
        max_err = fit.get("max_abs_error_sccm", 0.0)
        if order == 1 and len(coeffs) >= 2:
            eq = f"y = {coeffs[0]:.5f}\u00b7x + {coeffs[1]:.5f}"
        elif order == 2 and len(coeffs) >= 3:
            eq = (f"y = {coeffs[0]:.5f}\u00b7x\u00b2"
                  f" + {coeffs[1]:.5f}\u00b7x"
                  f" + {coeffs[2]:.5f}")
        else:
            eq = str(coeffs)
        self._metrics_lbl.setText(
            f"{eq}\n"
            f"RMSE: {rmse:.4f} sccm  \u2502  Max error: {max_err:.4f} sccm"
        )

    # ── Saving ────────────────────────────────────────────────────────────────

    def _save_calibration(self) -> None:
        if not self._last_fit:
            QMessageBox.warning(self, "No fit", "Please run 'Fit Model' first.")
            return
        pts = self._get_points()
        if pts is None:
            return

        gas = (
            self._gas_edit.text().strip()
            if self._gas_combo.currentText() == "Other"
            else self._gas_combo.currentText()
        ) or "?"
        fs = self._fs_spin.value()
        notes = self._notes_edit.text().strip()

        record = build_calibration_record(gas, fs, pts, self._last_fit, notes)

        default = str(self._cal_path or DEFAULT_CALIBRATION_PATH)
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Save Calibration JSON", default, "JSON files (*.json)"
        )
        if not path_str:
            return

        try:
            save_calibration(Path(path_str), record)
            self._cal_path = Path(path_str)
            self._status_lbl.setText(f"Saved: {self._cal_path.name}")
            self._status_lbl.setStyleSheet("color: #50c880; font-style: normal;")
            self.calibration_saved.emit(self._cal_path)
            QMessageBox.information(self, "Saved",
                                    f"Calibration saved to:\n{path_str}")
        except Exception as exc:
            QMessageBox.critical(self, "Save error", str(exc))

    # ── Chart update ──────────────────────────────────────────────────────────

    def _update_chart(self) -> None:
        pts: List[Tuple[float, float]] = []
        for row in range(self._table.rowCount()):
            try:
                dev = float(self._table.item(row, 0).text())
                ref = float(self._table.item(row, 1).text())
                pts.append((dev, ref))
            except Exception:
                pass
        coeffs = self._last_fit.get("coefficients") if self._last_fit else None
        self._chart.set_data(pts, coeffs, self._fs_spin.value())


# ──────────────────────────────────────────────────────────────────────────────
# Entry point (standalone)
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    if STYLESHEET:
        app.setStyleSheet(STYLESHEET)
    win = CalibrationWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
