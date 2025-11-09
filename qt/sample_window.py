"""PyQt6 sample selection window."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from PyQt6 import QtCore, QtGui, QtWidgets

from sample.sample_controller import SampleController

from .measurement_window import QtMeasurementGUI


class QtSampleWindow(QtWidgets.QMainWindow):
    """Qt front-end for selecting samples/devices before launching measurements."""

    def __init__(self, controller: Optional[SampleController] = None) -> None:
        super().__init__()
        self.controller = controller or SampleController()
        self.controller.set_logger(self._log)

        self._pixmap_item: Optional[QtWidgets.QGraphicsPixmapItem] = None
        self._orig_image_size = QtCore.QSize()
        self._device_items: Dict[str, QtWidgets.QGraphicsRectItem] = {}
        self._zoom_factor = 1.0

        self.measurement_window: Optional[QtMeasurementGUI] = None

        self.setWindowTitle("Sample Selector (Qt)")
        self.resize(900, 600)

        self._build_ui()
        self._populate_initial_state()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        form_grid = QtWidgets.QGridLayout()
        form_grid.setHorizontalSpacing(10)
        form_grid.setVerticalSpacing(8)

        # Multiplexer type
        form_grid.addWidget(QtWidgets.QLabel("Multiplexer:"), 0, 0)
        self.mux_combo = QtWidgets.QComboBox()
        self.mux_combo.addItems(["Pyswitchbox", "Electronic_Mpx"])
        self.mux_combo.currentTextChanged.connect(self._on_multiplexer_changed)
        form_grid.addWidget(self.mux_combo, 0, 1)

        # Sample type
        form_grid.addWidget(QtWidgets.QLabel("Sample Type:"), 1, 0)
        self.sample_combo = QtWidgets.QComboBox()
        self.sample_combo.addItems(self.controller.get_sample_types())
        self.sample_combo.currentTextChanged.connect(self._on_sample_changed)
        form_grid.addWidget(self.sample_combo, 1, 1)

        # Section
        form_grid.addWidget(QtWidgets.QLabel("Section:"), 2, 0)
        self.section_combo = QtWidgets.QComboBox()
        self.section_combo.currentTextChanged.connect(self._on_section_changed)
        form_grid.addWidget(self.section_combo, 2, 1)

        # Sample name entry
        form_grid.addWidget(QtWidgets.QLabel("Sample Name:"), 3, 0)
        self.sample_name_edit = QtWidgets.QLineEdit()
        self.sample_name_edit.setPlaceholderText("Optional sample identifier")
        form_grid.addWidget(self.sample_name_edit, 3, 1)

        layout.addLayout(form_grid)

        # Device list
        device_layout = QtWidgets.QHBoxLayout()
        left_panel = QtWidgets.QVBoxLayout()
        self.canvas = QtWidgets.QGraphicsView()
        self.canvas.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        self.canvas.setScene(QtWidgets.QGraphicsScene(self))
        self.canvas.setMinimumSize(400, 400)
        self.canvas.setDragMode(QtWidgets.QGraphicsView.DragMode.ScrollHandDrag)
        self.canvas.viewport().setCursor(QtCore.Qt.CursorShape.CrossCursor)
        self.canvas.setMouseTracking(True)
        self.canvas.viewport().installEventFilter(self)
        left_panel.addWidget(self.canvas, 1)

        # Buttons for image view
        zoom_row = QtWidgets.QHBoxLayout()
        self.zoom_in_btn = QtWidgets.QPushButton("Zoom In")
        self.zoom_in_btn.clicked.connect(lambda: self._adjust_zoom(1.2))
        zoom_row.addWidget(self.zoom_in_btn)
        self.zoom_out_btn = QtWidgets.QPushButton("Zoom Out")
        self.zoom_out_btn.clicked.connect(lambda: self._adjust_zoom(1 / 1.2))
        zoom_row.addWidget(self.zoom_out_btn)
        zoom_row.addStretch(1)
        left_panel.addLayout(zoom_row)

        device_layout.addLayout(left_panel, 3)

        list_panel = QtWidgets.QVBoxLayout()
        self.device_list = QtWidgets.QListWidget()
        self.device_list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.MultiSelection)
        self.device_list.itemSelectionChanged.connect(self._on_device_selection_changed)
        list_panel.addWidget(self.device_list, 1)

        button_column = QtWidgets.QVBoxLayout()
        self.select_all_btn = QtWidgets.QPushButton("Select All")
        self.select_all_btn.clicked.connect(self._select_all_devices)
        button_column.addWidget(self.select_all_btn)

        self.clear_btn = QtWidgets.QPushButton("Clear Selection")
        self.clear_btn.clicked.connect(self._clear_selection)
        button_column.addWidget(self.clear_btn)

        self.route_btn = QtWidgets.QPushButton("Route to Current Device")
        self.route_btn.clicked.connect(self._route_current_device)
        button_column.addWidget(self.route_btn)

        nav_row = QtWidgets.QHBoxLayout()
        self.prev_btn = QtWidgets.QPushButton("Previous")
        self.prev_btn.clicked.connect(self._goto_previous_device)
        nav_row.addWidget(self.prev_btn)
        self.next_btn = QtWidgets.QPushButton("Next")
        self.next_btn.clicked.connect(self._goto_next_device)
        nav_row.addWidget(self.next_btn)
        button_column.addLayout(nav_row)

        button_column.addStretch(1)
        list_panel.addLayout(button_column)
        device_layout.addLayout(list_panel, 2)
        layout.addLayout(device_layout, 4)

        # Status/log area
        self.log_view = QtWidgets.QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(2000)
        layout.addWidget(self.log_view, 2)

        # Action buttons
        action_row = QtWidgets.QHBoxLayout()
        action_row.addStretch(1)
        self.launch_btn = QtWidgets.QPushButton("Open Measurement")
        self.launch_btn.clicked.connect(self._launch_measurement)
        action_row.addWidget(self.launch_btn)
        layout.addLayout(action_row)

    # ------------------------------------------------------------------
    # Initial data population
    # ------------------------------------------------------------------
    def _populate_initial_state(self) -> None:
        # Multiplexer
        self.mux_combo.setCurrentText(self.controller.multiplexer_type)
        self.controller.configure_multiplexer(self.controller.multiplexer_type)

        # Sample type and sections
        self.sample_combo.setCurrentText(self.controller.sample_type)
        self._refresh_sections(self.controller.get_sections())
        self._refresh_devices()
        self._refresh_canvas()
        self._refresh_selection_view()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _on_multiplexer_changed(self, text: str) -> None:
        self.controller.configure_multiplexer(text)

    def _on_sample_changed(self, sample: str) -> None:
        sections = self.controller.set_sample_type(sample)
        self._refresh_sections(sections)
        self._refresh_devices()
        self._refresh_canvas()
        self._refresh_selection_view()

    def _on_section_changed(self, section: str) -> None:
        if section:
            self.controller.set_section(section)

    def _on_device_selection_changed(self) -> None:
        selected = [item.text() for item in self.device_list.selectedItems()]
        self.controller.replace_selection(selected)
        if selected:
            self.controller.set_current_device(selected[0])
        self._synch_canvas_selection()
        self._log(f"[SampleSelector] Selected devices: {', '.join(selected) or 'None'}")

    def _select_all_devices(self) -> None:
        self.controller.select_all()
        self._refresh_selection_view()

    def _clear_selection(self) -> None:
        self.controller.clear_selection()
        self._refresh_selection_view()

    def _route_current_device(self) -> None:
        device = self.controller.current_device_name
        if not device:
            QtWidgets.QMessageBox.warning(self, "No Device", "No current device available to route.")
            return
        success = self.controller.change_relays()
        if not success:
            QtWidgets.QMessageBox.warning(self, "Routing Failed", f"Failed to route to {device}.")

    def _goto_previous_device(self) -> None:
        device = self.controller.previous_device()
        if not device:
            return
        self._ensure_device_selected(device)
        self._refresh_selection_view()
        self._log(f"[SampleSelector] Previous device: {device}")

    def _goto_next_device(self) -> None:
        device = self.controller.next_device()
        if not device:
            return
        self._ensure_device_selected(device)
        self._refresh_selection_view()
        self._log(f"[SampleSelector] Next device: {device}")

    def _launch_measurement(self) -> None:
        devices = self.controller.ensure_selection()
        if not devices:
            QtWidgets.QMessageBox.warning(self, "No Devices", "Select at least one device.")
            return

        sample_name = self.sample_name_edit.text().strip()
        if sample_name:
            self.controller.set_sample_name(sample_name)

        self.controller.apply_measurement_selection(devices)
        window = QtMeasurementGUI(
            sample_type=self.controller.sample_type,
            section=self.controller.section,
            device_list=list(devices),
            sample_gui=self.controller,
        )
        window.show()
        window.bring_to_top()
        self.measurement_window = window

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _refresh_sections(self, sections: List[str]) -> None:
        self.section_combo.blockSignals(True)
        self.section_combo.clear()
        self.section_combo.addItems(sections)
        if sections:
            self.section_combo.setCurrentText(sections[0])
        self.section_combo.blockSignals(False)

    def _ensure_device_selected(self, device: str) -> None:
        if device not in self.controller.selected_devices:
            self.controller.select_device(device)
        self.controller.set_current_device(device)
        self._update_device_colors()

    def _update_device_colors(self) -> None:
        if not hasattr(self, "_device_items"):
            return
        selected = self.controller.selected_devices
        current = self.controller.current_device_name
        for device, item in self._device_items.items():
            if device == current:
                pen = QtGui.QPen(QtGui.QColor(220, 30, 30), 2)
                brush = QtGui.QBrush(QtGui.QColor(220, 30, 30, 70))
            elif device in selected:
                pen = QtGui.QPen(QtGui.QColor(40, 180, 80), 1.5)
                brush = QtGui.QBrush(QtGui.QColor(40, 180, 80, 60))
            else:
                pen = QtGui.QPen(QtGui.QColor(120, 120, 120, 80), 1)
                brush = QtGui.QBrush(QtGui.QColor(0, 0, 0, 0))
            item.setPen(pen)
            item.setBrush(brush)

    def _refresh_devices(self) -> None:
        self.device_list.blockSignals(True)
        self.device_list.clear()
        for name in self.controller.device_list:
            item = QtWidgets.QListWidgetItem(name)
            self.device_list.addItem(item)
        self.device_list.blockSignals(False)
        self._refresh_selection_view()

    def _refresh_canvas(self) -> None:
        scene = self.canvas.scene()
        block = scene.signalsBlocked()
        scene.blockSignals(True)
        scene.clear()
        pixmap, orig_size = self._load_sample_pixmap(self.controller.sample_type)
        if pixmap:
            self._pixmap_item = scene.addPixmap(pixmap)
            self._pixmap_item.setZValue(0)
            self.canvas.resetTransform()
            self.canvas.fitInView(self._pixmap_item, QtCore.Qt.AspectRatioMode.KeepAspectRatio)
            self._zoom_factor = 1.0
        else:
            self._pixmap_item = None
        self._orig_image_size = orig_size
        self._device_items: Dict[str, QtWidgets.QGraphicsRectItem] = {}
        mapping = self.controller.device_mapping
        if not mapping:
            scene.blockSignals(block)
            return
        scale_x, scale_y = self._bounds_scale_factors()
        for device, bounds in mapping.items():
            rect = QtCore.QRectF(
                bounds["x_min"] / scale_x,
                bounds["y_min"] / scale_y,
                (bounds["x_max"] - bounds["x_min"]) / scale_x,
                (bounds["y_max"] - bounds["y_min"]) / scale_y,
            )
            item = scene.addRect(rect)
            item.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            item.setData(0, device)
            item.setZValue(1)
            self._device_items[device] = item

        self._synch_canvas_selection()
        scene.blockSignals(block)

    def _adjust_zoom(self, factor: float) -> None:
        if not self._pixmap_item:
            return
        self._zoom_factor *= factor
        self.canvas.resetTransform()
        self.canvas.scale(self._zoom_factor, self._zoom_factor)
        self.canvas.centerOn(self._pixmap_item)

    def _synch_canvas_selection(self) -> None:
        if not hasattr(self, "_device_items"):
            return
        for name, item in self._device_items.items():
            block = item.scene().signalsBlocked()
            item.scene().blockSignals(True)
            item.setSelected(name in self.controller.selected_devices)
            item.scene().blockSignals(block)
        self._update_device_colors()

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:  # type: ignore[override]
        if watched is self.canvas.viewport() and event.type() == QtCore.QEvent.Type.MouseButtonPress:
            pos = self.canvas.mapToScene(event.pos())
            items = self.canvas.scene().items(pos)
            for item in items:
                device = item.data(0)
                if device:
                    self.controller.toggle_device(device)
                    self._refresh_selection_view()
                    return True
        return super().eventFilter(watched, event)

    def _bounds_scale_factors(self) -> tuple[float, float]:
        if getattr(self, "_orig_image_size", None) and self._pixmap_item:
            orig_width = max(float(self._orig_image_size.width()), 1.0)
            orig_height = max(float(self._orig_image_size.height()), 1.0)
            pix = self._pixmap_item.pixmap()
            scaled_width = max(float(pix.width()), 1.0)
            scaled_height = max(float(pix.height()), 1.0)
            return orig_width / scaled_width, orig_height / scaled_height
        return 1.0, 1.0

    def _load_sample_pixmap(self, sample: str) -> tuple[Optional[QtGui.QPixmap], QtCore.QSize]:
        helpers_dir = Path(__file__).resolve().parents[1] / "Helpers" / "Sample_Infomation"
        image_map = {
            "Cross_bar": helpers_dir / "memristor.png",
            "Device_Array_10": helpers_dir / "Multiplexer_10_OUT.jpg",
        }
        path = image_map.get(sample)
        if not path or not path.exists():
            return None, QtCore.QSize()
        pixmap = QtGui.QPixmap(str(path))
        if pixmap.isNull():
            return None, QtCore.QSize()
        orig_size = pixmap.size()
        scaled = pixmap.scaled(
            400,
            400,
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
        return scaled, orig_size

    def _refresh_selection_view(self) -> None:
        self.device_list.blockSignals(True)
        self.device_list.clearSelection()
        for idx in self.controller.selected_indices:
            if 0 <= idx < self.device_list.count():
                item = self.device_list.item(idx)
                item.setSelected(True)
        current_idx = getattr(self.controller, "current_index", -1)
        if (
            current_idx not in self.controller.selected_indices
            and self.controller.selected_indices
        ):
            first_idx = self.controller.selected_indices[0]
            if 0 <= first_idx < len(self.controller.device_list):
                self.controller.set_current_device(self.controller.device_list[first_idx])
                current_idx = first_idx
        if 0 <= current_idx < self.device_list.count():
            item = self.device_list.item(current_idx)
            self.device_list.scrollToItem(item, QtWidgets.QAbstractItemView.ScrollHint.PositionAtCenter)
        self.device_list.blockSignals(False)
        self._synch_canvas_selection()

    def _log(self, message: str) -> None:
        self.log_view.appendPlainText(message)
        cursor = self.log_view.textCursor()
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
        self.log_view.setTextCursor(cursor)


def launch_sample_window() -> None:
    app = QtWidgets.QApplication([])
    window = QtSampleWindow()
    window.show()
    app.exec()


if __name__ == "__main__":  # pragma: no cover
    launch_sample_window()


