"""PyQt5 dashboard for Tylan FC-2901V mass flow controller.

The FC-2901V uses a purely ANALOG 15-pin D-sub interface.
Supports two hardware backends (selectable in the UI):
  - NI-DAQ  : NI USB-6001 or any NI-DAQmx device
  - Arduino : Arduino running arduino_firmware/firmware.ino
"""

from __future__ import annotations

import json
import math
import sys
from collections import deque
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import Qt, QRect, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QBrush
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

try:
    from .calibration import apply_correction, load_calibration
    from .driver import (
        AbstractMFCDriver,
        ArduinoDriver,
        DriverError,
        NIDAQDriver,
        build_driver_from_config,
        load_config,
        save_config,
    )
except ImportError:
    from calibration import apply_correction, load_calibration
    from driver import (
        AbstractMFCDriver,
        ArduinoDriver,
        DriverError,
        NIDAQDriver,
        build_driver_from_config,
        load_config,
        save_config,
    )


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
UI_SETTINGS_PATH = BASE_DIR / "ui_settings.json"
DEFAULT_CALIBRATION_PATH = BASE_DIR / "calibration.json"


# ──────────────────────────────────────────────────────────────────────────────
# Shared stylesheet
# ──────────────────────────────────────────────────────────────────────────────

STYLESHEET = """
QMainWindow { background: #1a1d2e; }
QWidget { background: transparent; color: #cdd3ea;
          font-family: "Segoe UI", Arial, sans-serif; font-size: 10pt; }
QGroupBox {
    background: #21253a; border: 1px solid #333860;
    border-radius: 8px; margin-top: 12px; padding: 10px 6px 6px 6px;
}
QGroupBox::title {
    subcontrol-origin: margin; subcontrol-position: top left;
    left: 12px; padding: 0 6px;
    color: #7eb8f7; font-weight: bold;
}
QLabel { color: #cdd3ea; background: transparent; }
QPushButton {
    background: #2a2f4a; color: #cdd3ea;
    border: 1px solid #3e4470; border-radius: 5px;
    padding: 5px 14px; min-height: 26px;
}
QPushButton:hover { background: #363d64; border-color: #6080d0; }
QPushButton:pressed { background: #1e2238; }
QPushButton:disabled { color: #505878; border-color: #2a2f45; background: #222640; }
QPushButton#on_btn {
    background: #1a3d28; border-color: #35804a; color: #55e880; font-weight: bold;
}
QPushButton#on_btn:hover { background: #1e4a30; }
QPushButton#on_btn:disabled { background: #181e18; color: #3a5040; border-color: #202e22; }
QPushButton#off_btn {
    background: #3d1a1a; border-color: #804040; color: #ff8080; font-weight: bold;
}
QPushButton#off_btn:hover { background: #4a1e1e; }
QPushButton#off_btn:disabled { background: #1e1818; color: #5a3535; border-color: #2c2020; }
QPushButton#connect_btn {
    background: #1a2e4a; border-color: #3a6090; color: #70bcff; font-weight: bold;
}
QPushButton#connect_btn:hover { background: #1e3a5a; }
QPushButton#cal_btn {
    background: #2a2040; border-color: #604a90; color: #c090ff;
}
QPushButton#cal_btn:hover { background: #362a50; }
QLineEdit, QSpinBox, QComboBox {
    background: #1e2238; color: #c8d0ea;
    border: 1px solid #333860; border-radius: 4px; padding: 4px 6px;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus { border-color: #5080c0; }
QSpinBox::up-button, QSpinBox::down-button { width: 16px; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background: #21253a; selection-background-color: #3d5080;
    border: 1px solid #333860;
}
QSlider::groove:horizontal {
    height: 6px; background: #1e2238; border-radius: 3px; border: 1px solid #333860;
}
QSlider::handle:horizontal {
    background: #5580d0; width: 16px; height: 16px;
    margin: -5px 0; border-radius: 8px; border: 1px solid #6090e0;
}
QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2a508c,stop:1 #4a80d0);
    border-radius: 3px;
}
QPlainTextEdit {
    background: #141626; color: #50c870;
    font-family: Consolas, "Courier New", monospace; font-size: 9pt;
    border: 1px solid #252a40; border-radius: 4px;
}
QCheckBox { color: #a0b0d0; spacing: 6px; }
QCheckBox::indicator {
    width: 14px; height: 14px; border: 1px solid #3a4080;
    border-radius: 3px; background: #1e2238;
}
QCheckBox::indicator:checked { background: #3a66b8; border-color: #5080c0; }
QStatusBar { background: #141626; color: #6070a0; border-top: 1px solid #252a40; }
QHeaderView::section {
    background: #21253a; color: #7eb8f7; border: 1px solid #333860;
    padding: 4px; font-weight: bold;
}
QTableWidget { background: #1a1e30; gridline-color: #2a2f48; }
QTableWidget::item { padding: 4px; }
QTableWidget::item:selected { background: #2e3a5c; color: #dce8ff; }
QRadioButton { color: #a0b0d0; spacing: 6px; }
QRadioButton::indicator { width: 14px; height: 14px; }
QDoubleSpinBox {
    background: #1e2238; color: #c8d0ea;
    border: 1px solid #333860; border-radius: 4px; padding: 4px 6px;
}
QDoubleSpinBox:focus { border-color: #5080c0; }
QSplitter::handle { background: #2a2f48; }
"""


# ──────────────────────────────────────────────────────────────────────────────
# Background polling thread
# ──────────────────────────────────────────────────────────────────────────────

class PollingWorker(QThread):
    flow_updated = pyqtSignal(float)
    error = pyqtSignal(str)

    def __init__(self, driver: AbstractMFCDriver, interval_ms: int = 300) -> None:
        super().__init__()
        self.driver = driver
        self.interval_ms = interval_ms
        self._running = True

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        while self._running:
            try:
                flow = self.driver.read_flow_sccm()
                self.flow_updated.emit(float(flow))
            except DriverError as exc:
                self.error.emit(str(exc))
            except Exception as exc:
                self.error.emit(str(exc))
            self.msleep(max(50, self.interval_ms))


# ──────────────────────────────────────────────────────────────────────────────
# Flow gauge widget
# ──────────────────────────────────────────────────────────────────────────────

class FlowGaugeWidget(QWidget):
    """Arc gauge showing live flow with setpoint marker and history sparkline.

    The arc sweeps 270° clockwise from bottom-left (225°) to bottom-right (-45°/315°).
    Qt drawArc convention: startAngle in 1/16ths counterclockwise from 3-o'clock;
    negative spanAngle = clockwise on screen.
    """

    _GAUGE_START = 225    # Qt degrees for the zero end of the arc
    _GAUGE_SPAN = -270    # negative = clockwise (low→high goes left→top→right)
    _HISTORY_LEN = 60

    def __init__(self, full_scale: float = 200.0, parent=None):
        super().__init__(parent)
        self._flow: float = 0.0
        self._setpoint: float = 0.0
        self._full_scale: float = max(1.0, float(full_scale))
        self._corrected: Optional[float] = None
        self._history: deque = deque(maxlen=self._HISTORY_LEN)
        self._connected: bool = False
        self.setMinimumSize(240, 270)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_flow(self, flow: float, corrected: Optional[float] = None) -> None:
        self._flow = max(0.0, min(float(flow), self._full_scale))
        self._corrected = corrected
        if self._connected:
            self._history.append(self._flow)
        self.update()

    def set_setpoint(self, sp: float) -> None:
        self._setpoint = max(0.0, min(float(sp), self._full_scale))
        self.update()

    def set_full_scale(self, fs: float) -> None:
        self._full_scale = max(1.0, float(fs))
        self.update()

    def set_connected(self, connected: bool) -> None:
        self._connected = connected
        if not connected:
            self._history.clear()
        self.update()

    @staticmethod
    def _flow_color(ratio: float) -> QColor:
        """Green → amber → red based on fraction of full scale."""
        r = max(0.0, min(1.0, ratio))
        if r < 0.5:
            t = r / 0.5
            return QColor(int(30 + 225 * t), 210, int(80 - 50 * t))
        elif r < 0.8:
            t = (r - 0.5) / 0.3
            return QColor(255, int(200 - 90 * t), 30)
        else:
            t = (r - 0.8) / 0.2
            return QColor(255, int(110 - 70 * t), 20)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()

        spark_h = 46
        gauge_region_h = H - spark_h - 8

        margin = 22
        size = min(W - 2 * margin, gauge_region_h - 8)
        if size < 20:
            return
        gx = (W - size) // 2
        gy = (gauge_region_h - size) // 2
        rect = QRect(gx, gy, size, size)
        arc_w = max(10, size // 11)
        cx = gx + size / 2.0
        cy = gy + size / 2.0

        ratio = max(0.0, min(1.0, self._flow / self._full_scale))

        # Background track
        pen = QPen(QColor("#1a1f32"), arc_w)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawArc(rect, self._GAUGE_START * 16, self._GAUGE_SPAN * 16)

        # Colored fill arc
        if ratio > 0.002 and self._connected:
            fill_pen = QPen(self._flow_color(ratio), arc_w)
            fill_pen.setCapStyle(Qt.RoundCap)
            painter.setPen(fill_pen)
            painter.drawArc(rect, self._GAUGE_START * 16, int(self._GAUGE_SPAN * ratio) * 16)

        # Tick marks at 0 / 25 / 50 / 75 / 100 %
        tick_font = QFont("Segoe UI", max(6, size // 32))
        for i in range(5):
            t = i / 4.0
            deg = self._GAUGE_START + self._GAUGE_SPAN * t
            rad = math.radians(deg)
            r_in = size / 2.0 - arc_w - 8
            r_out = size / 2.0 - 2
            painter.setPen(QPen(QColor("#2a3254"), 1))
            painter.drawLine(
                int(cx + r_in * math.cos(rad)), int(cy - r_in * math.sin(rad)),
                int(cx + r_out * math.cos(rad)), int(cy - r_out * math.sin(rad)),
            )
            painter.setFont(tick_font)
            painter.setPen(QColor("#3a4468"))
            lbl = str(int(self._full_scale * t))
            r_lbl = size / 2.0 + 13
            lx = int(cx + r_lbl * math.cos(rad))
            ly = int(cy - r_lbl * math.sin(rad))
            painter.drawText(QRect(lx - 14, ly - 8, 28, 16), Qt.AlignCenter, lbl)

        # Setpoint tick marker
        sp_ratio = max(0.0, min(1.0, self._setpoint / self._full_scale))
        sp_deg = self._GAUGE_START + self._GAUGE_SPAN * sp_ratio
        sp_rad = math.radians(sp_deg)
        r1 = size / 2.0 - arc_w - 2
        r2 = size / 2.0 + 3
        painter.setPen(QPen(QColor("#4898e8"), 2))
        painter.drawLine(
            int(cx + r1 * math.cos(sp_rad)), int(cy - r1 * math.sin(sp_rad)),
            int(cx + r2 * math.cos(sp_rad)), int(cy - r2 * math.sin(sp_rad)),
        )

        # Center value text
        inner_m = arc_w + 10
        tr = rect.adjusted(inner_m, inner_m, -inner_m, -inner_m)
        center_x = tr.left()
        center_w = tr.width()
        mid_y = tr.top() + tr.height() // 2

        if self._connected:
            val_str = f"{self._flow:.1f}"
            unit_str = "sccm"
        else:
            val_str = "—"
            unit_str = "not connected"

        val_font_size = max(14, size // 7)
        val_font = QFont("Segoe UI", val_font_size, QFont.Bold)
        painter.setFont(val_font)
        painter.setPen(QColor("#d8e2ff"))
        painter.drawText(
            QRect(center_x, mid_y - val_font_size - 4, center_w, val_font_size * 2),
            Qt.AlignCenter, val_str,
        )

        unit_font = QFont("Segoe UI", max(8, size // 20))
        painter.setFont(unit_font)
        painter.setPen(QColor("#505888"))
        painter.drawText(
            QRect(center_x, mid_y + val_font_size - 4, center_w, 22),
            Qt.AlignCenter, unit_str,
        )

        if self._corrected is not None and self._connected:
            corr_font = QFont("Segoe UI", max(7, size // 26))
            painter.setFont(corr_font)
            painter.setPen(QColor("#6070a8"))
            painter.drawText(
                QRect(center_x, mid_y + val_font_size + 18, center_w, 18),
                Qt.AlignCenter, f"corr: {self._corrected:.1f} sccm",
            )

        # Setpoint label near tick
        sp_lbl_font = QFont("Segoe UI", max(6, size // 34))
        painter.setFont(sp_lbl_font)
        painter.setPen(QColor("#3a70b8"))
        r_sp_lbl = size / 2.0 + 26
        slx = int(cx + r_sp_lbl * math.cos(sp_rad)) - 14
        sly = int(cy - r_sp_lbl * math.sin(sp_rad)) - 7
        painter.drawText(QRect(slx, sly, 28, 14), Qt.AlignCenter,
                         f"{int(self._setpoint)}")

        # Sparkline
        if self._connected and len(self._history) >= 2:
            self._paint_sparkline(painter, W, H, spark_h)

    def _paint_sparkline(self, p: QPainter, W: int, H: int, spark_h: int) -> None:
        vals = list(self._history)
        n = len(vals)
        if n < 2:
            return

        mx = 24
        sy = H - spark_h
        sw = W - 2 * mx
        sh = spark_h - 4

        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#13152a"))
        p.drawRoundedRect(mx, sy, sw, sh, 4, 4)

        pts = []
        for i, v in enumerate(vals):
            px = mx + 2 + int(i / (n - 1) * (sw - 4))
            r = v / self._full_scale if self._full_scale > 0 else 0.0
            py = sy + sh - 2 - int(max(0.0, min(1.0, r)) * (sh - 4))
            pts.append((px, py))

        path = QPainterPath()
        path.moveTo(pts[0][0], sy + sh - 2)
        for px, py in pts:
            path.lineTo(px, py)
        path.lineTo(pts[-1][0], sy + sh - 2)
        path.closeSubpath()
        fill = QColor("#1e4a80")
        fill.setAlpha(100)
        p.setBrush(fill)
        p.setPen(Qt.NoPen)
        p.drawPath(path)

        pen = QPen(QColor("#3d78c8"), 1)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        for i in range(1, n):
            p.drawLine(pts[i - 1][0], pts[i - 1][1], pts[i][0], pts[i][1])

        lx, ly = pts[-1]
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#60a8e8"))
        p.drawEllipse(lx - 3, ly - 3, 6, 6)

        lbl_font = QFont("Segoe UI", 7)
        p.setFont(lbl_font)
        p.setPen(QColor("#2a3460"))
        p.drawText(mx + 4, sy + sh - 3, "history")


# ──────────────────────────────────────────────────────────────────────────────
# Collapsible section widget
# ──────────────────────────────────────────────────────────────────────────────

class CollapsibleSection(QWidget):
    """Titled panel that collapses/expands when the header is clicked."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

        self._header = QPushButton(f"  \u25bc   {title}")
        self._header.setCheckable(True)
        self._header.setChecked(True)
        self._header.setCursor(Qt.PointingHandCursor)
        self._header.setStyleSheet("""
            QPushButton {
                text-align: left; padding: 7px 12px;
                background: #252a40; border: 1px solid #333860;
                border-radius: 6px; color: #7eb8f7;
                font-weight: bold; font-size: 10pt;
            }
            QPushButton:hover { background: #2d3356; }
            QPushButton:checked { border-bottom-left-radius: 0; border-bottom-right-radius: 0; }
        """)
        self._header.toggled.connect(self._on_toggled)

        self._content = QFrame()
        self._content.setStyleSheet("""
            QFrame {
                background: #21253a; border: 1px solid #333860;
                border-top: none;
                border-bottom-left-radius: 6px; border-bottom-right-radius: 6px;
            }
        """)
        self._inner = QVBoxLayout(self._content)
        self._inner.setContentsMargins(10, 8, 10, 10)
        self._inner.setSpacing(6)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._header)
        layout.addWidget(self._content)

    def _on_toggled(self, checked: bool) -> None:
        self._content.setVisible(checked)
        txt = self._header.text()
        if checked:
            self._header.setText(txt.replace("\u25b6", "\u25bc"))
        else:
            self._header.setText(txt.replace("\u25bc", "\u25b6"))

    def add_widget(self, widget: QWidget) -> None:
        self._inner.addWidget(widget)

    def add_layout(self, layout) -> None:
        self._inner.addLayout(layout)

    def set_collapsed(self, collapsed: bool) -> None:
        self._header.setChecked(not collapsed)


# ──────────────────────────────────────────────────────────────────────────────
# Main window
# ──────────────────────────────────────────────────────────────────────────────

class MassFlowWindow(QMainWindow):

    def __init__(self) -> None:
        super().__init__()
        self.driver: Optional[AbstractMFCDriver] = None
        self.calibration: Optional[dict] = None
        self.polling_worker: Optional[PollingWorker] = None
        self._last_poll_error: Optional[str] = None
        self._setpoint_guard = False
        self._config: dict = {}
        self._cal_window = None

        self.setWindowTitle("Tylan FC-2901V \u2014 Mass Flow Dashboard")
        self.resize(820, 720)

        self._load_hw_config()
        self._build_ui()
        self._apply_ui_settings()
        self._load_calibration_on_startup()

        self._status_timer = QTimer(self)
        self._status_timer.setInterval(1200)
        self._status_timer.timeout.connect(self._refresh_status_bar)
        self._status_timer.start()

    # ── Config helpers ──────────────────────────────────────────────────────

    def _load_hw_config(self) -> None:
        if CONFIG_PATH.exists():
            try:
                self._config = load_config(CONFIG_PATH)
                return
            except Exception:
                pass
        self._config = {
            "driver": "nidaq",
            "full_scale_sccm": 200.0,
            "nidaq": {
                "device_name": "Dev1",
                "ao_setpoint_channel": "ao0",
                "ai_flow_channel": "ai0",
                "do_valve_off_channel": "port0/line0",
            },
            "arduino": {"port": "COM3", "baudrate": 115200, "timeout_s": 0.5},
        }

    def _save_hw_config(self) -> None:
        try:
            save_config(CONFIG_PATH, self._config)
        except Exception:
            pass

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)
        root.setObjectName("root")
        root.setStyleSheet("QWidget#root { background: #1a1d2e; }")

        main = QVBoxLayout(root)
        main.setContentsMargins(10, 10, 10, 6)
        main.setSpacing(8)

        self._conn_section = self._build_connection_section()
        main.addWidget(self._conn_section)

        full_scale = float(self._config.get("full_scale_sccm", 200.0))
        self._gauge = FlowGaugeWidget(full_scale=full_scale)
        main.addWidget(self._gauge, stretch=3)

        main.addWidget(self._build_control_group())
        main.addWidget(self._build_calibration_bar())
        main.addWidget(self._build_log_group(), stretch=1)

        self.statusBar().showMessage("Ready \u2014 not connected")

    # ── Connection section ──────────────────────────────────────────────────

    def _build_connection_section(self) -> CollapsibleSection:
        section = CollapsibleSection("Hardware Connection")

        inner = QWidget()
        grid = QGridLayout(inner)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(6)

        self._backend_combo = QComboBox()
        self._backend_combo.addItems([
            "NI-DAQ  (NI USB-6001 or similar)",
            "Arduino (firmware.ino)",
        ])
        self._backend_combo.currentIndexChanged.connect(self._on_backend_changed)

        self._hw_stack = QStackedWidget()
        self._hw_stack.addWidget(self._build_nidaq_panel())
        self._hw_stack.addWidget(self._build_arduino_panel())

        initial_backend = str(self._config.get("driver", "nidaq")).lower()
        idx = 1 if initial_backend == "arduino" else 0
        self._backend_combo.setCurrentIndex(idx)
        self._hw_stack.setCurrentIndex(idx)

        self._connect_btn = QPushButton("Connect")
        self._connect_btn.setObjectName("connect_btn")
        self._connect_btn.setFixedWidth(120)
        self._connect_btn.clicked.connect(self.toggle_connection)

        self._conn_status = QLabel("\u25cf  Disconnected")
        self._conn_status.setStyleSheet("color: #805050;")

        grid.addWidget(QLabel("Backend:"), 0, 0)
        grid.addWidget(self._backend_combo, 0, 1, 1, 2)
        grid.addWidget(self._hw_stack, 1, 0, 1, 3)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self._connect_btn)
        btn_row.addWidget(self._conn_status)
        btn_row.addStretch(1)
        grid.addLayout(btn_row, 2, 0, 1, 3)

        section.add_widget(inner)
        return section

    def _build_nidaq_panel(self) -> QWidget:
        w = QWidget()
        g = QGridLayout(w)
        g.setContentsMargins(0, 0, 0, 0)
        g.setSpacing(6)

        self._ni_device_combo = QComboBox()
        self._ni_refresh_btn = QPushButton("Refresh")
        self._ni_refresh_btn.clicked.connect(self._refresh_ni_devices)

        self._ni_ao_edit = QLineEdit(
            self._config.get("nidaq", {}).get("ao_setpoint_channel", "ao0"))
        self._ni_ai_edit = QLineEdit(
            self._config.get("nidaq", {}).get("ai_flow_channel", "ai0"))
        self._ni_do_edit = QLineEdit(
            self._config.get("nidaq", {}).get("do_valve_off_channel", "port0/line0"))

        g.addWidget(QLabel("Device:"), 0, 0)
        g.addWidget(self._ni_device_combo, 0, 1)
        g.addWidget(self._ni_refresh_btn, 0, 2)
        g.addWidget(QLabel("AO setpoint:"), 1, 0)
        g.addWidget(self._ni_ao_edit, 1, 1)
        g.addWidget(QLabel("e.g. ao0"), 1, 2)
        g.addWidget(QLabel("AI flow:"), 2, 0)
        g.addWidget(self._ni_ai_edit, 2, 1)
        g.addWidget(QLabel("e.g. ai0"), 2, 2)
        g.addWidget(QLabel("DO valve-OFF:"), 3, 0)
        g.addWidget(self._ni_do_edit, 3, 1)
        g.addWidget(QLabel("e.g. port0/line0"), 3, 2)
        self._refresh_ni_devices()
        return w

    def _build_arduino_panel(self) -> QWidget:
        w = QWidget()
        g = QGridLayout(w)
        g.setContentsMargins(0, 0, 0, 0)
        g.setSpacing(6)

        self._ard_port_combo = QComboBox()
        self._ard_refresh_btn = QPushButton("Refresh")
        self._ard_refresh_btn.clicked.connect(self._refresh_arduino_ports)

        self._ard_baud_spin = QSpinBox()
        self._ard_baud_spin.setRange(9600, 921600)
        self._ard_baud_spin.setValue(
            int(self._config.get("arduino", {}).get("baudrate", 115200)))

        g.addWidget(QLabel("COM port:"), 0, 0)
        g.addWidget(self._ard_port_combo, 0, 1)
        g.addWidget(self._ard_refresh_btn, 0, 2)
        g.addWidget(QLabel("Baud rate:"), 1, 0)
        g.addWidget(self._ard_baud_spin, 1, 1)
        self._refresh_arduino_ports()
        return w

    # ── Flow control group ──────────────────────────────────────────────────

    def _build_control_group(self) -> QGroupBox:
        box = QGroupBox("Flow Control")
        grid = QGridLayout(box)
        grid.setSpacing(8)

        full_scale = int(self._config.get("full_scale_sccm", 200))

        self._on_btn = QPushButton("ON \u2014 open valve")
        self._on_btn.setObjectName("on_btn")
        self._off_btn = QPushButton("OFF \u2014 close valve")
        self._off_btn.setObjectName("off_btn")
        self._on_btn.clicked.connect(lambda: self._set_output(True))
        self._off_btn.clicked.connect(lambda: self._set_output(False))
        self._on_btn.setEnabled(False)
        self._off_btn.setEnabled(False)

        self._setpoint_slider = QSlider(Qt.Horizontal)
        self._setpoint_slider.setRange(0, full_scale)
        self._setpoint_slider.valueChanged.connect(self._slider_changed)

        self._setpoint_spin = QSpinBox()
        self._setpoint_spin.setRange(0, full_scale)
        self._setpoint_spin.setSuffix(" sccm")
        self._setpoint_spin.valueChanged.connect(self._spin_changed)
        self._setpoint_spin.setFixedWidth(90)

        self._apply_btn = QPushButton("Apply Setpoint")
        self._apply_btn.clicked.connect(self._apply_setpoint)
        self._apply_btn.setEnabled(False)

        self._poll_spin = QSpinBox()
        self._poll_spin.setRange(100, 5000)
        self._poll_spin.setValue(300)
        self._poll_spin.setSuffix(" ms")
        self._poll_spin.setFixedWidth(90)

        grid.addWidget(self._on_btn, 0, 0, 1, 2)
        grid.addWidget(self._off_btn, 0, 2, 1, 2)
        grid.addWidget(QLabel("Setpoint:"), 1, 0)
        grid.addWidget(self._setpoint_slider, 1, 1, 1, 2)
        grid.addWidget(self._setpoint_spin, 1, 3)
        grid.addWidget(self._apply_btn, 2, 0, 1, 2)
        grid.addWidget(QLabel("Poll interval:"), 2, 2)
        grid.addWidget(self._poll_spin, 2, 3)
        return box

    # ── Calibration bar ──────────────────────────────────────────────────────

    def _build_calibration_bar(self) -> QGroupBox:
        box = QGroupBox("Calibration")
        row = QHBoxLayout(box)
        row.setSpacing(8)

        self._cal_label = QLabel("No calibration loaded")
        self._cal_label.setStyleSheet("color: #7080a8; font-style: italic;")

        self._load_cal_btn = QPushButton("Browse\u2026")
        self._load_cal_btn.clicked.connect(self._choose_calibration_file)

        self._open_cal_tool_btn = QPushButton("Calibration Tool\u2026")
        self._open_cal_tool_btn.setObjectName("cal_btn")
        self._open_cal_tool_btn.clicked.connect(self._open_calibration_tool)

        row.addWidget(self._cal_label, 1)
        row.addWidget(self._load_cal_btn)
        row.addWidget(self._open_cal_tool_btn)
        return box

    # ── Log group ────────────────────────────────────────────────────────────

    def _build_log_group(self) -> QGroupBox:
        box = QGroupBox("Raw Log")
        col = QVBoxLayout(box)
        col.setSpacing(4)

        self._log_cb = QCheckBox("Enable logging")
        self._log_cb.toggled.connect(self._toggle_log)
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(2000)
        self._log.setMaximumHeight(130)

        col.addWidget(self._log_cb)
        col.addWidget(self._log)
        return box

    # ── UI settings persistence ──────────────────────────────────────────────

    def _apply_ui_settings(self) -> None:
        if not UI_SETTINGS_PATH.exists():
            return
        try:
            data = json.loads(UI_SETTINGS_PATH.read_text(encoding="utf-8"))
            self._poll_spin.setValue(int(data.get("poll_ms", self._poll_spin.value())))
        except Exception:
            pass

    def _save_ui_settings(self) -> None:
        payload = {"poll_ms": self._poll_spin.value()}
        try:
            UI_SETTINGS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            pass

    # ── Device list helpers ──────────────────────────────────────────────────

    def _refresh_ni_devices(self) -> None:
        current = self._ni_device_combo.currentText()
        self._ni_device_combo.clear()
        devices = NIDAQDriver.list_devices()
        self._ni_device_combo.addItems(devices if devices else ["Dev1"])
        stored = self._config.get("nidaq", {}).get("device_name", "Dev1")
        for name in (current, stored):
            idx = self._ni_device_combo.findText(name)
            if idx >= 0:
                self._ni_device_combo.setCurrentIndex(idx)
                break
        device_list = ', '.join(devices) if devices else '(none \u2013 defaulted to Dev1)'
        self._log_append(f"[INFO] NI devices: {device_list}")

    def _refresh_arduino_ports(self) -> None:
        current = self._ard_port_combo.currentText()
        self._ard_port_combo.clear()
        ports = ArduinoDriver.list_devices()
        self._ard_port_combo.addItems(ports)
        stored = self._config.get("arduino", {}).get("port", "")
        for name in (current, stored):
            idx = self._ard_port_combo.findText(name)
            if idx >= 0:
                self._ard_port_combo.setCurrentIndex(idx)
                break
        self._log_append(f"[INFO] Serial ports: {', '.join(ports) if ports else '(none)'}")

    def _on_backend_changed(self, idx: int) -> None:
        self._hw_stack.setCurrentIndex(idx)

    # ── Connection ───────────────────────────────────────────────────────────

    def _build_driver_from_ui(self) -> AbstractMFCDriver:
        full_scale = float(self._config.get("full_scale_sccm", 200.0))
        idx = self._backend_combo.currentIndex()
        if idx == 0:
            device = self._ni_device_combo.currentText().strip() or "Dev1"
            ao = self._ni_ao_edit.text().strip() or "ao0"
            ai = self._ni_ai_edit.text().strip() or "ai0"
            do_ch = self._ni_do_edit.text().strip() or "port0/line0"
            self._config["driver"] = "nidaq"
            self._config.setdefault("nidaq", {}).update({
                "device_name": device,
                "ao_setpoint_channel": ao,
                "ai_flow_channel": ai,
                "do_valve_off_channel": do_ch,
            })
            return NIDAQDriver(device, ao, ai, do_ch, full_scale)
        else:
            port = self._ard_port_combo.currentText().strip()
            baud = self._ard_baud_spin.value()
            if not port:
                raise DriverError("No COM port selected for Arduino.")
            self._config["driver"] = "arduino"
            self._config.setdefault("arduino", {}).update({"port": port, "baudrate": baud})
            return ArduinoDriver(port, baud, full_scale_sccm=full_scale)

    def toggle_connection(self) -> None:
        if self.driver and self.driver.is_connected:
            self._disconnect()
            return
        try:
            self.driver = self._build_driver_from_ui()
            self.driver.connect()
            self._connect_btn.setText("Disconnect")
            self._conn_status.setText(f"\u25cf  Connected \u2014 {self._backend_name()}")
            self._conn_status.setStyleSheet("color: #50c880; font-weight: bold;")
            self._on_btn.setEnabled(True)
            self._off_btn.setEnabled(True)
            self._apply_btn.setEnabled(True)
            self._gauge.set_connected(True)
            self._gauge.set_full_scale(float(self._config.get("full_scale_sccm", 200.0)))
            self._log_append(f"[INFO] Connected via {self._backend_name()}")
            self._save_hw_config()
            self._save_ui_settings()
            self._start_polling()
            self._conn_section.set_collapsed(True)
        except Exception as exc:
            QMessageBox.critical(self, "Connection error", str(exc))
            self._log_append(f"[ERROR] {exc}")
            self.driver = None

    def _disconnect(self) -> None:
        self._stop_polling()
        if self.driver:
            try:
                self.driver.close()
            except Exception:
                pass
        self.driver = None
        self._connect_btn.setText("Connect")
        self._conn_status.setText("\u25cf  Disconnected")
        self._conn_status.setStyleSheet("color: #805050;")
        self._on_btn.setEnabled(False)
        self._off_btn.setEnabled(False)
        self._apply_btn.setEnabled(False)
        self._gauge.set_connected(False)
        self._log_append("[INFO] Disconnected")
        self._save_ui_settings()
        self._conn_section.set_collapsed(False)

    def _backend_name(self) -> str:
        return "NI-DAQ" if self._backend_combo.currentIndex() == 0 else "Arduino"

    # ── Flow control ─────────────────────────────────────────────────────────

    def _set_output(self, enabled: bool) -> None:
        if not (self.driver and self.driver.is_connected):
            return
        try:
            self.driver.set_output_enabled(enabled)
            self._log_append(f"[TX] valve {'ON' if enabled else 'OFF'}")
        except Exception as exc:
            QMessageBox.critical(self, "Valve error", str(exc))
            self._log_append(f"[ERROR] {exc}")

    def _slider_changed(self, value: int) -> None:
        if self._setpoint_guard:
            return
        self._setpoint_guard = True
        self._setpoint_spin.setValue(value)
        self._gauge.set_setpoint(float(value))
        self._setpoint_guard = False

    def _spin_changed(self, value: int) -> None:
        if self._setpoint_guard:
            return
        self._setpoint_guard = True
        self._setpoint_slider.setValue(value)
        self._gauge.set_setpoint(float(value))
        self._setpoint_guard = False

    def _apply_setpoint(self) -> None:
        if not (self.driver and self.driver.is_connected):
            return
        value = float(self._setpoint_spin.value())
        try:
            self.driver.set_setpoint_sccm(value)
            self._log_append(f"[TX] setpoint = {value:.1f} sccm")
        except Exception as exc:
            QMessageBox.critical(self, "Setpoint error", str(exc))
            self._log_append(f"[ERROR] {exc}")

    # ── Polling ───────────────────────────────────────────────────────────────

    def _start_polling(self) -> None:
        self._stop_polling()
        if not (self.driver and self.driver.is_connected):
            return
        worker = PollingWorker(self.driver, self._poll_spin.value())
        worker.flow_updated.connect(self._on_flow_update)
        worker.error.connect(self._on_poll_error)
        self.polling_worker = worker
        self._last_poll_error = None
        worker.start()

    def _stop_polling(self) -> None:
        if not self.polling_worker:
            return
        self.polling_worker.stop()
        self.polling_worker.wait(1500)
        self.polling_worker = None

    def _on_flow_update(self, flow: float) -> None:
        self._last_poll_error = None
        corrected = apply_correction(flow, self.calibration or {})
        has_cal = bool(
            self.calibration and self.calibration.get("fit", {}).get("coefficients"))
        self._gauge.set_flow(flow, corrected if has_cal else None)
        self._log_append(f"[RX] flow = {flow:.3f} sccm")

    def _on_poll_error(self, message: str) -> None:
        self._last_poll_error = message
        self._log_append(f"[ERROR] {message}")

    # ── Calibration ───────────────────────────────────────────────────────────

    def _load_calibration_on_startup(self) -> None:
        if DEFAULT_CALIBRATION_PATH.exists():
            self._refresh_calibration_label(DEFAULT_CALIBRATION_PATH)
        else:
            msg = QMessageBox(self)
            msg.setWindowTitle("Calibration file not found")
            msg.setText("No calibration file was found at the default location.")
            msg.setInformativeText(
                f"{DEFAULT_CALIBRATION_PATH}\n\n"
                "Would you like to browse for an existing calibration file?"
            )
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg.setDefaultButton(QMessageBox.No)
            msg.button(QMessageBox.Yes).setText("Browse\u2026")
            msg.button(QMessageBox.No).setText("Continue without")
            if msg.exec_() == QMessageBox.Yes:
                self._choose_calibration_file()

    def _choose_calibration_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select calibration JSON", str(BASE_DIR),
            "JSON files (*.json);;All files (*.*)"
        )
        if path:
            self._refresh_calibration_label(Path(path))

    def _refresh_calibration_label(self, path: Path) -> None:
        if not path.exists():
            self.calibration = None
            self._cal_label.setText("No calibration loaded")
            self._cal_label.setStyleSheet("color: #7080a8; font-style: italic;")
            return
        try:
            self.calibration = load_calibration(path)
            gas = self.calibration.get("gas", "?")
            order = self.calibration.get("fit", {}).get("order", "?")
            self._cal_label.setText(
                f"Loaded: {path.name}  (gas={gas}, fit order={order})")
            self._cal_label.setStyleSheet("color: #50c880; font-style: normal;")
        except Exception as exc:
            self.calibration = None
            self._cal_label.setText("Calibration load failed")
            self._cal_label.setStyleSheet("color: #c05050; font-style: italic;")
            QMessageBox.warning(self, "Calibration error", str(exc))

    def _open_calibration_tool(self) -> None:
        try:
            from .calibration_gui import CalibrationWindow
        except ImportError:
            from calibration_gui import CalibrationWindow

        if self._cal_window is None or not self._cal_window.isVisible():
            self._cal_window = CalibrationWindow(parent=None)
            self._cal_window.calibration_saved.connect(self._on_calibration_saved)

        self._cal_window.show()
        self._cal_window.raise_()
        self._cal_window.activateWindow()

    def _on_calibration_saved(self, path: "Path") -> None:
        self._refresh_calibration_label(path)

    # ── Log helpers ───────────────────────────────────────────────────────────

    def _toggle_log(self, enabled: bool) -> None:
        self._log_enabled = enabled

    def _log_append(self, message: str) -> None:
        if getattr(self, "_log_enabled", False):
            self._log.appendPlainText(message)

    # ── Status bar ─────────────────────────────────────────────────────────

    def _refresh_status_bar(self) -> None:
        connected = bool(self.driver and self.driver.is_connected)
        if connected:
            msg = f"Connected | {self._backend_name()}"
            if self._gauge._flow > 0:
                msg += f" | {self._gauge._flow:.2f} sccm"
        else:
            msg = "Disconnected"
        if self._last_poll_error:
            msg += f" | Error: {self._last_poll_error}"
        self.statusBar().showMessage(msg)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:  # noqa: N802
        self._stop_polling()
        if self.driver:
            try:
                self.driver.close()
            except Exception:
                pass
        if self._cal_window:
            self._cal_window.close()
        self._save_ui_settings()
        super().closeEvent(event)


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    window = MassFlowWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
