"""PyQt5 dashboard for Tylan FC-2901V mass flow controller.

The FC-2901V uses a purely ANALOG 15-pin D-sub interface.
This dashboard supports two hardware backends (selectable in the UI):
  - NI-DAQ  : NI USB-6001 or any NI-DAQmx device
  - Arduino : Arduino running arduino_firmware/firmware.ino
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
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

_FLOW_FONT = QFont()
_FLOW_FONT.setPointSize(24)
_FLOW_FONT.setBold(True)


# ---------------------------------------------------------------------------
# Background polling thread
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MassFlowWindow(QMainWindow):

    def __init__(self) -> None:
        super().__init__()
        self.driver: Optional[AbstractMFCDriver] = None
        self.calibration: Optional[dict] = None
        self.polling_worker: Optional[PollingWorker] = None
        self._last_poll_error: Optional[str] = None
        self._setpoint_guard = False
        self._config: dict = {}

        self.setWindowTitle("Tylan FC-2901V — Mass Flow Dashboard")
        self.resize(1000, 780)

        self._load_hw_config()
        self._build_ui()
        self._apply_ui_settings()
        self._refresh_calibration_label(DEFAULT_CALIBRATION_PATH)

        self._status_timer = QTimer(self)
        self._status_timer.setInterval(1200)
        self._status_timer.timeout.connect(self._refresh_status_bar)
        self._status_timer.start()

    # ------------------------------------------------------------------
    # Config helpers
    # ------------------------------------------------------------------

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
            "nidaq": {"device_name": "Dev1", "ao_setpoint_channel": "ao0",
                      "ai_flow_channel": "ai0", "do_valve_off_channel": "port0/line0"},
            "arduino": {"port": "COM3", "baudrate": 115200, "timeout_s": 0.5},
        }

    def _save_hw_config(self) -> None:
        try:
            save_config(CONFIG_PATH, self._config)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)
        main = QVBoxLayout(root)

        main.addWidget(self._build_connection_group())
        main.addWidget(self._build_control_group())
        main.addWidget(self._build_calibration_bar())
        main.addWidget(self._build_log_group(), stretch=1)

        self.statusBar().showMessage("Ready — not connected")

    # --- Connection group ------------------------------------------------

    def _build_connection_group(self) -> QGroupBox:
        box = QGroupBox("Hardware connection")
        grid = QGridLayout(box)

        # Backend selector
        self._backend_combo = QComboBox()
        self._backend_combo.addItems(["NI-DAQ  (NI USB-6001 or similar)",
                                      "Arduino (firmware.ino)"])
        self._backend_combo.currentIndexChanged.connect(self._on_backend_changed)

        self._hw_stack = QStackedWidget()
        self._hw_stack.addWidget(self._build_nidaq_panel())
        self._hw_stack.addWidget(self._build_arduino_panel())

        initial_backend = str(self._config.get("driver", "nidaq")).lower()
        idx = 1 if initial_backend == "arduino" else 0
        self._backend_combo.setCurrentIndex(idx)
        self._hw_stack.setCurrentIndex(idx)

        self._connect_btn = QPushButton("Connect")
        self._connect_btn.setFixedWidth(110)
        self._connect_btn.clicked.connect(self.toggle_connection)

        self._conn_status = QLabel("Disconnected")

        grid.addWidget(QLabel("Backend:"), 0, 0)
        grid.addWidget(self._backend_combo, 0, 1, 1, 2)
        grid.addWidget(self._hw_stack, 1, 0, 1, 3)
        btn_row = QHBoxLayout()
        btn_row.addWidget(self._connect_btn)
        btn_row.addWidget(self._conn_status)
        btn_row.addStretch(1)
        grid.addLayout(btn_row, 2, 0, 1, 3)
        return box

    def _build_nidaq_panel(self) -> QWidget:
        w = QWidget()
        g = QGridLayout(w)

        self._ni_device_combo = QComboBox()
        self._ni_refresh_btn = QPushButton("Refresh")
        self._ni_refresh_btn.clicked.connect(self._refresh_ni_devices)

        self._ni_ao_edit = QLineEdit(
            self._config.get("nidaq", {}).get("ao_setpoint_channel", "ao0")
        )
        self._ni_ai_edit = QLineEdit(
            self._config.get("nidaq", {}).get("ai_flow_channel", "ai0")
        )
        self._ni_do_edit = QLineEdit(
            self._config.get("nidaq", {}).get("do_valve_off_channel", "port0/line0")
        )

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

        self._ard_port_combo = QComboBox()
        self._ard_refresh_btn = QPushButton("Refresh")
        self._ard_refresh_btn.clicked.connect(self._refresh_arduino_ports)

        self._ard_baud_spin = QSpinBox()
        self._ard_baud_spin.setRange(9600, 921600)
        self._ard_baud_spin.setValue(
            int(self._config.get("arduino", {}).get("baudrate", 115200))
        )

        g.addWidget(QLabel("COM port:"), 0, 0)
        g.addWidget(self._ard_port_combo, 0, 1)
        g.addWidget(self._ard_refresh_btn, 0, 2)
        g.addWidget(QLabel("Baud rate:"), 1, 0)
        g.addWidget(self._ard_baud_spin, 1, 1)
        self._refresh_arduino_ports()
        return w

    # --- Flow control group ----------------------------------------------

    def _build_control_group(self) -> QGroupBox:
        box = QGroupBox("Flow control")
        grid = QGridLayout(box)

        full_scale = int(self._config.get("full_scale_sccm", 200))

        # On / Off buttons
        self._on_btn = QPushButton("ON  (open valve)")
        self._off_btn = QPushButton("OFF  (close valve)")
        self._on_btn.clicked.connect(lambda: self._set_output(True))
        self._off_btn.clicked.connect(lambda: self._set_output(False))
        self._on_btn.setEnabled(False)
        self._off_btn.setEnabled(False)

        # Setpoint
        self._setpoint_slider = QSlider(Qt.Horizontal)
        self._setpoint_slider.setRange(0, full_scale)
        self._setpoint_slider.valueChanged.connect(self._slider_changed)

        self._setpoint_spin = QSpinBox()
        self._setpoint_spin.setRange(0, full_scale)
        self._setpoint_spin.setSuffix(" sccm")
        self._setpoint_spin.valueChanged.connect(self._spin_changed)

        self._apply_btn = QPushButton("Apply setpoint")
        self._apply_btn.clicked.connect(self._apply_setpoint)
        self._apply_btn.setEnabled(False)

        self._poll_spin = QSpinBox()
        self._poll_spin.setRange(100, 5000)
        self._poll_spin.setValue(300)
        self._poll_spin.setSuffix(" ms")

        # Large flow readout
        self._flow_label = QLabel("---")
        self._flow_label.setFont(_FLOW_FONT)
        self._flow_label.setAlignment(Qt.AlignCenter)

        self._corrected_label = QLabel("Corrected: ---")
        self._corrected_label.setAlignment(Qt.AlignCenter)

        self._full_scale_label = QLabel(f"Full scale: 0 – {full_scale} sccm  (N₂ equivalent)")
        self._full_scale_label.setAlignment(Qt.AlignCenter)

        grid.addWidget(self._on_btn, 0, 0, 1, 2)
        grid.addWidget(self._off_btn, 0, 2, 1, 2)
        grid.addWidget(QLabel("Setpoint:"), 1, 0)
        grid.addWidget(self._setpoint_slider, 1, 1, 1, 2)
        grid.addWidget(self._setpoint_spin, 1, 3)
        grid.addWidget(self._apply_btn, 2, 0, 1, 2)
        grid.addWidget(QLabel("Polling interval:"), 2, 2)
        grid.addWidget(self._poll_spin, 2, 3)
        grid.addWidget(self._flow_label, 3, 0, 1, 4)
        grid.addWidget(self._corrected_label, 4, 0, 1, 4)
        grid.addWidget(self._full_scale_label, 5, 0, 1, 4)
        return box

    # --- Calibration bar -------------------------------------------------

    def _build_calibration_bar(self) -> QGroupBox:
        box = QGroupBox("Calibration")
        row = QHBoxLayout(box)
        self._cal_label = QLabel("No calibration loaded")
        self._load_cal_btn = QPushButton("Load calibration JSON")
        self._load_cal_btn.clicked.connect(self._choose_calibration_file)
        row.addWidget(self._cal_label)
        row.addStretch(1)
        row.addWidget(self._load_cal_btn)
        return box

    # --- Log group -------------------------------------------------------

    def _build_log_group(self) -> QGroupBox:
        box = QGroupBox("Raw log")
        col = QVBoxLayout(box)
        self._log_cb = QCheckBox("Enable logging")
        self._log_cb.toggled.connect(self._toggle_log)
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(2000)
        col.addWidget(self._log_cb)
        col.addWidget(self._log)
        return box

    # ------------------------------------------------------------------
    # Saved UI settings (last-used values, not hardware config)
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Device list helpers
    # ------------------------------------------------------------------

    def _refresh_ni_devices(self) -> None:
        current = self._ni_device_combo.currentText()
        self._ni_device_combo.clear()
        devices = NIDAQDriver.list_devices()
        if devices:
            self._ni_device_combo.addItems(devices)
        else:
            self._ni_device_combo.addItem("Dev1")
        stored = self._config.get("nidaq", {}).get("device_name", "Dev1")
        for name in (current, stored):
            idx = self._ni_device_combo.findText(name)
            if idx >= 0:
                self._ni_device_combo.setCurrentIndex(idx)
                break
        self._log_append(f"[INFO] NI devices: {', '.join(devices) if devices else '(none found – defaulted to Dev1)'}")

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

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def _build_driver_from_ui(self) -> AbstractMFCDriver:
        full_scale = float(self._config.get("full_scale_sccm", 200.0))
        idx = self._backend_combo.currentIndex()
        if idx == 0:  # NI-DAQ
            device = self._ni_device_combo.currentText().strip() or "Dev1"
            ao = self._ni_ao_edit.text().strip() or "ao0"
            ai = self._ni_ai_edit.text().strip() or "ai0"
            do_ch = self._ni_do_edit.text().strip() or "port0/line0"
            self._config["driver"] = "nidaq"
            self._config.setdefault("nidaq", {})
            self._config["nidaq"].update({
                "device_name": device,
                "ao_setpoint_channel": ao,
                "ai_flow_channel": ai,
                "do_valve_off_channel": do_ch,
            })
            return NIDAQDriver(device, ao, ai, do_ch, full_scale)
        else:  # Arduino
            port = self._ard_port_combo.currentText().strip()
            baud = self._ard_baud_spin.value()
            if not port:
                raise DriverError("No COM port selected for Arduino.")
            self._config["driver"] = "arduino"
            self._config.setdefault("arduino", {})
            self._config["arduino"].update({"port": port, "baudrate": baud})
            return ArduinoDriver(port, baud, full_scale_sccm=full_scale)

    def toggle_connection(self) -> None:
        if self.driver and self.driver.is_connected:
            self._disconnect()
            return
        try:
            self.driver = self._build_driver_from_ui()
            self.driver.connect()
            self._connect_btn.setText("Disconnect")
            self._conn_status.setText(f"Connected — {self._backend_name()}")
            self._on_btn.setEnabled(True)
            self._off_btn.setEnabled(True)
            self._apply_btn.setEnabled(True)
            self._log_append(f"[INFO] Connected via {self._backend_name()}")
            self._save_hw_config()
            self._save_ui_settings()
            self._start_polling()
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
        self._conn_status.setText("Disconnected")
        self._on_btn.setEnabled(False)
        self._off_btn.setEnabled(False)
        self._apply_btn.setEnabled(False)
        self._flow_label.setText("---")
        self._corrected_label.setText("Corrected: ---")
        self._log_append("[INFO] Disconnected")
        self._save_ui_settings()

    def _backend_name(self) -> str:
        return "NI-DAQ" if self._backend_combo.currentIndex() == 0 else "Arduino"

    # ------------------------------------------------------------------
    # Flow control
    # ------------------------------------------------------------------

    def _set_output(self, enabled: bool) -> None:
        if not (self.driver and self.driver.is_connected):
            return
        try:
            self.driver.set_output_enabled(enabled)
            state = "ON" if enabled else "OFF"
            self._log_append(f"[TX] valve {state}")
        except Exception as exc:
            QMessageBox.critical(self, "Valve error", str(exc))
            self._log_append(f"[ERROR] {exc}")

    def _slider_changed(self, value: int) -> None:
        if self._setpoint_guard:
            return
        self._setpoint_guard = True
        self._setpoint_spin.setValue(value)
        self._setpoint_guard = False

    def _spin_changed(self, value: int) -> None:
        if self._setpoint_guard:
            return
        self._setpoint_guard = True
        self._setpoint_slider.setValue(value)
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

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

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
        self._flow_label.setText(f"{flow:.2f} sccm")
        corrected = apply_correction(flow, self.calibration or {})
        self._corrected_label.setText(f"Corrected: {corrected:.2f} sccm")
        self._log_append(f"[RX] flow = {flow:.3f} sccm")

    def _on_poll_error(self, message: str) -> None:
        self._last_poll_error = message
        self._log_append(f"[ERROR] {message}")

    # ------------------------------------------------------------------
    # Calibration
    # ------------------------------------------------------------------

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
            return
        try:
            self.calibration = load_calibration(path)
            gas = self.calibration.get("gas", "?")
            order = self.calibration.get("fit", {}).get("order", "?")
            self._cal_label.setText(
                f"Loaded: {path.name}  (gas={gas}, fit order={order})"
            )
        except Exception as exc:
            self.calibration = None
            self._cal_label.setText("Calibration load failed")
            QMessageBox.warning(self, "Calibration error", str(exc))

    # ------------------------------------------------------------------
    # Log helpers
    # ------------------------------------------------------------------

    def _toggle_log(self, enabled: bool) -> None:
        self._log_enabled = enabled

    def _log_append(self, message: str) -> None:
        if getattr(self, "_log_enabled", False):
            self._log.appendPlainText(message)

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------

    def _refresh_status_bar(self) -> None:
        connected = bool(self.driver and self.driver.is_connected)
        msg = "Connected" if connected else "Disconnected"
        if connected:
            msg += f" | {self._backend_name()}"
        if self._last_poll_error:
            msg += f" | Last error: {self._last_poll_error}"
        self.statusBar().showMessage(msg)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: N802
        self._stop_polling()
        if self.driver:
            try:
                self.driver.close()
            except Exception:
                pass
        self._save_ui_settings()
        super().closeEvent(event)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    app = QApplication(sys.argv)
    window = MassFlowWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
