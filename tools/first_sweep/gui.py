"""Compare first sweeps and forming metrics across sample folders."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from tools.filament_jump_finder.core import origin_export_root
from tools.filament_jump_finder.origin_export import origin_data_dir, sanitize_export_name

from .core import (
    METRIC_FIELDS,
    discover_sample,
    ensure_sweeps,
    evolution_rows,
    export_origin,
    limited_sweeps,
    load_session,
    metrics_for,
    opening_segment,
    path_key,
    save_session,
)

_LINESTYLES = ("-", "--", ":", "-.")
_HIGHLIGHT = "#c2185b"

_PALETTE = ["#1565c0", "#ef6c00", "#2e7d32", "#6a1b9a", "#c62828", "#00838f", "#4e342e", "#37474f"]

_PLOT_METRICS = (
    ("pre_current_A", "Pre-forming current (A)"),
    ("pre_resistance_ohm", "Pre-forming resistance (ohm)"),
    ("first_jump_voltage_V", "First-sweep jump voltage (V)"),
    ("forming_voltage_V", "Forming voltage (V)"),
    ("forming_polarity", "Forming polarity"),
    ("forming_current", "Current before and after forming (A)"),
    ("first_loglog_slope", "First log-log slope"),
    ("conduction_regions", "Conduction regions"),
    ("switching_voltage_V", "Switching voltage (V)"),
    ("on_off_ratio", "ON/OFF ratio"),
    ("permanently_ohmic", "Permanently ohmic"),
)
_COUNT_KEYS = {"forming_polarity", "permanently_ohmic"}
_NEEDS_FULL = {
    "forming_voltage_V",
    "forming_polarity",
    "forming_current",
    "switching_voltage_V",
    "on_off_ratio",
    "permanently_ohmic",
}


def _sample_colors(n: int):
    if n <= len(_PALETTE):
        return _PALETTE[:n]
    from matplotlib import colormaps
    cmap = colormaps["tab20"]
    return [cmap(i / max(n - 1, 1)) for i in range(n)]


def _finite(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(number):
        return None
    return number


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("First sweep comparison")
        self.resize(1280, 820)
        self.folders: List[Path] = []
        self.labels: Dict[str, str] = {}
        self.devices: List[Dict[str, Any]] = []
        self.hidden: set = set()
        self.hidden_files: set = set()
        self._highlight_path: Optional[str] = None
        self._filling = False
        self._build_ui()

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        bar = QHBoxLayout()
        self.btn_add = QPushButton("Add folders…")
        self.btn_remove = QPushButton("Remove selected")
        self.btn_save = QPushButton("Save session…")
        self.btn_load = QPushButton("Load session…")
        self.btn_origin = QPushButton("Save for Origin…")
        for button in (self.btn_add, self.btn_remove, self.btn_save, self.btn_load, self.btn_origin):
            bar.addWidget(button)
        bar.addStretch(1)
        layout.addLayout(bar)

        params = QHBoxLayout()
        params.addWidget(QLabel("Opening cutoff (V)"))
        self.cutoff = QDoubleSpinBox()
        self.cutoff.setRange(0.01, 20.0)
        self.cutoff.setDecimals(2)
        self.cutoff.setSingleStep(0.1)
        self.cutoff.setValue(0.5)
        self.cutoff.setToolTip("First part of each sweep, from the start until the voltage reaches this value.")
        params.addWidget(self.cutoff)
        params.addWidget(QLabel("Files"))
        self.file_count = QSpinBox()
        self.file_count.setRange(1, 50)
        self.file_count.setValue(3)
        self.file_count.setToolTip("How many measurement files to take from the start of each device.")
        params.addWidget(self.file_count)
        params.addWidget(QLabel("Jump ratio"))
        self.ratio = QDoubleSpinBox()
        self.ratio.setRange(1.5, 100000.0)
        self.ratio.setDecimals(1)
        self.ratio.setSingleStep(1.0)
        self.ratio.setValue(10.0)
        self.ratio.setToolTip(
            "A current step counts as a jump when the larger |I| is at least this many times the smaller. "
            "Steps below 0.1 pA are ignored."
        )
        params.addWidget(self.ratio)
        params.addWidget(QLabel("Normalization"))
        self.norm = QComboBox()
        self.norm.addItem("Raw current", "raw")
        self.norm.addItem("Divide by max |I|", "max")
        params.addWidget(self.norm)
        self.log_check = QCheckBox("Log |current|")
        params.addWidget(self.log_check)
        params.addWidget(QLabel("Figure"))
        self.figure = QComboBox()
        self.figure.addItem("Opening window", "window")
        self.figure.addItem("Full first sweep", "full")
        self.figure.addItem("Metric", "metric")
        self.figure.addItem("Sweep evolution", "evolution")
        params.addWidget(self.figure)
        self.metric = QComboBox()
        for key, label in _PLOT_METRICS:
            self.metric.addItem(label, key)
        self.metric.setEnabled(False)
        params.addWidget(self.metric)
        params.addStretch(1)
        layout.addLayout(params)

        self.status = QLabel(
            "Add sample folders. Opening window plots the first files of each device, from the start until the cutoff. "
            "Uncheck a file to drop it. Click a file to highlight that curve."
        )
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("Samples"))
        self.folder_list = QListWidget()
        self.folder_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        left_layout.addWidget(self.folder_list, 1)
        label_row = QHBoxLayout()
        label_row.addWidget(QLabel("Label"))
        self.sample_label = QLineEdit()
        self.sample_label.setPlaceholderText("Select a sample, then type a short name such as 2%")
        label_row.addWidget(self.sample_label, 1)
        left_layout.addLayout(label_row)
        device_row = QHBoxLayout()
        device_row.addWidget(QLabel("Devices"))
        self.btn_all = QPushButton("All")
        self.btn_none = QPushButton("None")
        device_row.addWidget(self.btn_all)
        device_row.addWidget(self.btn_none)
        device_row.addStretch(1)
        left_layout.addLayout(device_row)
        self.device_list = QListWidget()
        left_layout.addWidget(self.device_list, 2)
        file_row = QHBoxLayout()
        file_row.addWidget(QLabel("Files"))
        self.btn_files_all = QPushButton("All")
        self.btn_files_none = QPushButton("None")
        file_row.addWidget(self.btn_files_all)
        file_row.addWidget(self.btn_files_none)
        file_row.addStretch(1)
        left_layout.addLayout(file_row)
        self.file_list = QListWidget()
        self.file_list.setToolTip("Check a file to keep it. Click a row to highlight that curve.")
        left_layout.addWidget(self.file_list, 2)

        self.fig = Figure(figsize=(8, 5))
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.toolbar = NavigationToolbar2QT(self.canvas, root)
        self.table = QTableWidget(0, 3 + len(METRIC_FIELDS))
        self.table.setHorizontalHeaderLabels(
            ["Sample", "Section", "Device", *[title for _key, title in METRIC_FIELDS]]
        )
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        plot_wrap = QWidget()
        plot_layout = QVBoxLayout(plot_wrap)
        plot_layout.setContentsMargins(0, 0, 0, 0)
        plot_layout.addWidget(self.toolbar)
        plot_layout.addWidget(self.canvas, 2)
        plot_layout.addWidget(self.table, 1)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(plot_wrap)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

        self.btn_add.clicked.connect(self._add_folders)
        self.btn_remove.clicked.connect(self._remove_folders)
        self.btn_save.clicked.connect(self._save_session)
        self.btn_load.clicked.connect(self._load_session)
        self.btn_origin.clicked.connect(self._save_origin)
        self.btn_all.clicked.connect(lambda: self._set_all_checks(True))
        self.btn_none.clicked.connect(lambda: self._set_all_checks(False))
        self.btn_files_all.clicked.connect(lambda: self._set_all_files(True))
        self.btn_files_none.clicked.connect(lambda: self._set_all_files(False))
        self.folder_list.currentRowChanged.connect(self._show_label)
        self.sample_label.editingFinished.connect(self._apply_label)
        self.device_list.itemChanged.connect(self._device_toggled)
        self.file_list.itemChanged.connect(self._on_file_toggled)
        self.file_list.itemClicked.connect(self._on_file_clicked)
        self.file_count.valueChanged.connect(self._file_count_changed)
        self.cutoff.valueChanged.connect(self._refresh)
        self.ratio.valueChanged.connect(self._refresh)
        self.norm.currentIndexChanged.connect(self._refresh)
        self.log_check.toggled.connect(self._refresh)
        self.figure.currentIndexChanged.connect(self._figure_changed)
        self.metric.currentIndexChanged.connect(self._refresh)

    def _figure_changed(self):
        self.metric.setEnabled(self.figure.currentData() == "metric")
        self._refresh()

    def _key(self, device: Dict[str, Any]) -> Tuple[str, str, int]:
        return (device["sample_path"], device["section"], int(device["device_num"]))

    def _label_for(self, device: Dict[str, Any]) -> str:
        return self.labels.get(device["sample_path"]) or device["sample_folder"]

    def _checked_devices(self) -> List[Dict[str, Any]]:
        return [device for device in self.devices if self._key(device) not in self.hidden]

    def _add_folders(self):
        dialog = QFileDialog(self, "Add sample folders")
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setOption(QFileDialog.ShowDirsOnly, True)
        dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        for view in dialog.findChildren(QListView) + dialog.findChildren(QTreeView):
            view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        if not dialog.exec_():
            return
        added = 0
        for raw in dialog.selectedFiles():
            path = Path(raw).resolve()
            if path in self.folders:
                continue
            self.folders.append(path)
            self.labels.setdefault(str(path), path.name)
            added += 1
        if added:
            self._reload_devices()

    def _remove_folders(self):
        selected = {Path(item.data(Qt.UserRole)) for item in self.folder_list.selectedItems()}
        if not selected:
            return
        self.folders = [path for path in self.folders if path not in selected]
        for path in selected:
            self.labels.pop(str(path), None)
        self.hidden = {key for key in self.hidden if Path(key[0]) not in selected}
        self._reload_devices()

    def _reload_devices(self):
        self.status.setText("Reading device folders…")
        self.repaint()
        devices: List[Dict[str, Any]] = []
        for folder in self.folders:
            self.labels.setdefault(str(folder), folder.name)
            try:
                devices.extend(discover_sample(folder))
            except Exception as exc:
                QMessageBox.warning(self, "Could not read folder", f"{folder}\n{exc}")
        self.devices = devices
        self._fill_folders()
        self._fill_devices()
        self._fill_files()
        self._refresh()

    def _fill_folders(self):
        self._filling = True
        self.folder_list.clear()
        for folder in self.folders:
            label = self.labels.get(str(folder)) or folder.name
            item = QListWidgetItem(f"{folder.name}  —  {label}")
            item.setData(Qt.UserRole, str(folder))
            self.folder_list.addItem(item)
        self._filling = False
        if self.folder_list.count():
            self.folder_list.setCurrentRow(0)
        else:
            self.sample_label.clear()

    def _fill_devices(self):
        self._filling = True
        self.device_list.clear()
        for device in self.devices:
            text = f"{self._label_for(device)}   {device['section']} {device['device_num']}"
            item = QListWidgetItem(text)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked if self._key(device) in self.hidden else Qt.Checked)
            item.setData(Qt.UserRole, self._key(device))
            self.device_list.addItem(item)
        self._filling = False

    def _show_label(self, row: int):
        if self._filling or row < 0:
            return
        item = self.folder_list.item(row)
        path = item.data(Qt.UserRole)
        self.sample_label.setText(self.labels.get(path) or "")

    def _apply_label(self):
        if self._filling:
            return
        item = self.folder_list.currentItem()
        if item is None:
            return
        path = item.data(Qt.UserRole)
        text = self.sample_label.text().strip() or Path(path).name
        self.labels[path] = text
        item.setText(f"{Path(path).name}  —  {text}")
        self._fill_devices()
        self._fill_files()
        self._refresh()

    def _device_toggled(self, item: QListWidgetItem):
        if self._filling:
            return
        key = item.data(Qt.UserRole)
        if item.checkState() == Qt.Checked:
            self.hidden.discard(key)
        else:
            self.hidden.add(key)
        self._refresh()

    def _set_all_checks(self, checked: bool):
        self._filling = True
        state = Qt.Checked if checked else Qt.Unchecked
        for index in range(self.device_list.count()):
            item = self.device_list.item(index)
            item.setCheckState(state)
            key = item.data(Qt.UserRole)
            if checked:
                self.hidden.discard(key)
            else:
                self.hidden.add(key)
        self._filling = False
        self._refresh()

    def _fill_files(self):
        scroll = self.file_list.verticalScrollBar().value()
        self.file_list.blockSignals(True)
        self._filling = True
        try:
            self.file_list.clear()
            limit = int(self.file_count.value())
            for device in self.devices:
                files = list(device.get("files") or [])[:limit]
                for path in files:
                    key = path_key(path)
                    text = (
                        f"{self._label_for(device)}   {device['section']} {device['device_num']}"
                        f"   {Path(path).name}"
                    )
                    item = QListWidgetItem(text)
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                    item.setCheckState(Qt.Unchecked if key in self.hidden_files else Qt.Checked)
                    item.setData(Qt.UserRole, key)
                    self._style_file_item(item, key)
                    self.file_list.addItem(item)
        finally:
            self._filling = False
            self.file_list.blockSignals(False)
            self.file_list.verticalScrollBar().setValue(scroll)

    def _style_file_item(self, item: QListWidgetItem, key: str):
        font = item.font()
        font.setBold(key == self._highlight_path)
        item.setFont(font)

    def _mark_highlighted_file(self):
        self.file_list.blockSignals(True)
        try:
            for row in range(self.file_list.count()):
                item = self.file_list.item(row)
                self._style_file_item(item, item.data(Qt.UserRole))
        finally:
            self.file_list.blockSignals(False)

    def _on_file_clicked(self, item: QListWidgetItem):
        if self._filling or item is None:
            return
        self._highlight_path = item.data(Qt.UserRole)
        self._mark_highlighted_file()
        self._refresh()

    def _on_file_toggled(self, item: QListWidgetItem):
        if self._filling:
            return
        key = item.data(Qt.UserRole)
        if not key:
            return
        if item.checkState() == Qt.Checked:
            self.hidden_files.discard(key)
        else:
            self.hidden_files.add(key)
        self._highlight_path = key
        self._mark_highlighted_file()
        self._refresh()

    def _set_all_files(self, checked: bool):
        self.file_list.blockSignals(True)
        self._filling = True
        try:
            state = Qt.Checked if checked else Qt.Unchecked
            for index in range(self.file_list.count()):
                item = self.file_list.item(index)
                item.setCheckState(state)
                key = item.data(Qt.UserRole)
                if checked:
                    self.hidden_files.discard(key)
                else:
                    self.hidden_files.add(key)
        finally:
            self._filling = False
            self.file_list.blockSignals(False)
        self._refresh()

    def _file_count_changed(self):
        if self._filling:
            return
        self._fill_files()
        self._refresh()

    def _needs_full(self) -> bool:
        figure = self.figure.currentData()
        if figure == "evolution":
            return True
        if figure == "metric" and self.metric.currentData() in _NEEDS_FULL:
            return True
        return False

    def _refresh(self):
        if self._filling:
            return
        devices = self._checked_devices()
        full = self._needs_full()
        if full and devices:
            self.status.setText(f"Reading later sweeps for {len(devices)} devices…")
            self.repaint()
        cutoff = float(self.cutoff.value())
        ratio = float(self.ratio.value())
        if self.figure.currentData() == "window":
            limit = int(self.file_count.value())
            for device in devices:
                limited_sweeps(device, limit)
        for device in devices:
            metrics_for(device, cutoff, ratio, full=full)
        self._fill_table(devices)
        self.fig.clear()
        figure = self.figure.currentData()
        if figure == "metric":
            self._draw_metric(devices)
        elif figure == "evolution":
            self._draw_evolution(devices)
        else:
            self._draw_curves(devices, window=figure == "window")
        self.canvas.draw_idle()

    def _groups(self, devices: Sequence[Dict[str, Any]]):
        order = []
        for device in devices:
            if device["sample_path"] not in order:
                order.append(device["sample_path"])
        colors = _sample_colors(len(order))
        return order, {path: color for path, color in zip(order, colors)}

    def _scaled_current(self, current: np.ndarray, normalise: bool, use_log: bool) -> np.ndarray:
        values = np.asarray(current, dtype=float)
        if normalise:
            scale = float(np.nanmax(np.abs(values))) if values.size else float("nan")
            values = values / scale if np.isfinite(scale) and scale > 0 else values
        if use_log:
            values = np.abs(values)
        return values

    def _draw_curves(self, devices: Sequence[Dict[str, Any]], window: bool):
        ax = self.fig.add_subplot(111)
        order, colors = self._groups(devices)
        seen = set()
        handles = []
        drawn = 0
        skipped = 0
        cutoff = float(self.cutoff.value())
        file_limit = int(self.file_count.value())
        normalise = self.norm.currentData() == "max"
        use_log = self.log_check.isChecked()
        highlighted = None
        styles_used = set()
        for device in devices:
            if window:
                series = limited_sweeps(device, file_limit)
            else:
                series = [(1, sweep) for sweep in ensure_sweeps(device, full=False)[:1]]
            if not series and not window:
                skipped += 1
                continue
            color = colors[device["sample_path"]]
            for file_number, sweep in series:
                key = path_key(sweep["path"])
                if window and key in self.hidden_files:
                    continue
                voltage = sweep["voltage"]
                current = sweep["current"]
                if window:
                    voltage, current = opening_segment(voltage, current, cutoff)
                    if voltage.size < 2:
                        skipped += 1
                        continue
                values = self._scaled_current(current, normalise, use_log)
                style = _LINESTYLES[(file_number - 1) % len(_LINESTYLES)]
                if device["sample_path"] not in seen:
                    seen.add(device["sample_path"])
                    handles.append(Line2D([0], [0], color=color, label=self._label_for(device)))
                if window and key == self._highlight_path:
                    highlighted = (voltage, values, sweep["filename"], style)
                    styles_used.add((file_number - 1) % len(_LINESTYLES))
                    continue
                ax.plot(voltage, values, color=color, alpha=0.75, linewidth=1.0, linestyle=style)
                drawn += 1
                if window:
                    styles_used.add((file_number - 1) % len(_LINESTYLES))
        if highlighted is not None:
            voltage, values, filename, style = highlighted
            ax.plot(
                voltage, values,
                color=_HIGHLIGHT, linestyle=style, linewidth=2.8, alpha=1.0, zorder=5,
            )
            handles.append(Line2D([0], [0], color=_HIGHLIGHT, linestyle=style, linewidth=2.8, label=filename))
            drawn += 1
        if window:
            for index in sorted(styles_used):
                number = index + 1
                label = f"File {number}" if file_limit <= len(_LINESTYLES) else f"File {number}, {number + len(_LINESTYLES)}, ..."
                handles.append(Line2D([0], [0], color="0.25", linestyle=_LINESTYLES[index], label=label))
        if use_log:
            ax.set_yscale("log")
            ylabel = "Absolute current (normalised)" if normalise else "Absolute current (A)"
        else:
            ylabel = "Current (normalised)" if normalise else "Current (A)"
        ax.set_xlabel("Voltage (V)")
        ax.set_ylabel(ylabel)
        if window:
            title = f"Opening window, first {cutoff:g} V, first {file_limit} files"
        else:
            title = "Full first sweep"
        ax.set_title(title)
        ax.grid(True, alpha=0.3)
        if handles:
            ax.legend(handles=handles, loc="best", fontsize=8)
        self.fig.tight_layout()
        if window:
            extra = f" {skipped} files had no points in this window." if skipped else ""
            self.status.setText(
                f"{drawn} openings across {len(order)} samples. "
                f"Solid, dashed, and dotted are files 1, 2, and 3. Click a file to highlight it.{extra}"
            )
        else:
            self.status.setText(f"{drawn} first sweeps across {len(order)} samples.")

    def _draw_metric(self, devices: Sequence[Dict[str, Any]]):
        key = self.metric.currentData()
        ax = self.fig.add_subplot(111)
        order, colors = self._groups(devices)
        if key in _COUNT_KEYS:
            self._draw_counts(ax, devices, order, colors, key)
        elif key == "forming_current":
            self._draw_before_after(ax, devices, order, colors)
        else:
            self._draw_boxes(ax, devices, order, colors, key, self.metric.currentText())
        self.fig.tight_layout()

    def _values_for(self, device: Dict[str, Any], key: str) -> Optional[float]:
        metrics = device.get("metrics") or {}
        return _finite(metrics.get(key))

    def _draw_boxes(self, ax, devices, order, colors, key: str, title: str):
        data = []
        labels = []
        used = []
        for path in order:
            values = [
                self._values_for(device, key)
                for device in devices
                if device["sample_path"] == path
            ]
            values = [value for value in values if value is not None]
            if not values:
                continue
            data.append(values)
            labels.append(self.labels.get(path) or Path(path).name)
            used.append(path)
        if not data:
            ax.text(0.5, 0.5, "No values for the checked devices.", ha="center", va="center", transform=ax.transAxes)
            ax.set_axis_off()
            self.status.setText("No values for this metric. A blank means the sweep did not contain that event.")
            return
        ax.boxplot(data, showfliers=False)
        for index, (path, values) in enumerate(zip(used, data), start=1):
            xs = index + np.linspace(-0.12, 0.12, len(values))
            ax.scatter(xs, values, color=colors[path], s=22, zorder=3)
        ax.set_xticks(range(1, len(labels) + 1))
        ax.set_xticklabels(labels, rotation=15, ha="right")
        ax.set_title(title)
        ax.grid(True, axis="y", alpha=0.3)
        missing = sum(1 for device in devices if self._values_for(device, key) is None)
        self.status.setText(f"{sum(len(values) for values in data)} devices plotted. {missing} checked devices have no value.")

    def _draw_before_after(self, ax, devices, order, colors):
        data = []
        labels = []
        point_colors = []
        for path in order:
            sample_devices = [device for device in devices if device["sample_path"] == path]
            before = [self._values_for(device, "current_before_forming_A") for device in sample_devices]
            after = [self._values_for(device, "current_after_forming_A") for device in sample_devices]
            before = [value for value in before if value is not None]
            after = [value for value in after if value is not None]
            name = self.labels.get(path) or Path(path).name
            if before:
                data.append(before)
                labels.append(f"{name} before")
                point_colors.append(colors[path])
            if after:
                data.append(after)
                labels.append(f"{name} after")
                point_colors.append(colors[path])
        if not data:
            ax.text(0.5, 0.5, "No forming jump on the checked devices.", ha="center", va="center", transform=ax.transAxes)
            ax.set_axis_off()
            self.status.setText("No forming jump yet. Forming is the earliest current jump in sweep order.")
            return
        use_log = self.log_check.isChecked()
        if use_log:
            data = [[abs(value) for value in series] for series in data]
        ax.boxplot(data, showfliers=False)
        for index, (values, color) in enumerate(zip(data, point_colors), start=1):
            xs = index + np.linspace(-0.12, 0.12, len(values))
            ax.scatter(xs, values, color=color, s=22, zorder=3)
        ax.set_xticks(range(1, len(labels) + 1))
        ax.set_xticklabels(labels, rotation=15, ha="right")
        ax.set_ylabel("Absolute current (A)" if use_log else "Current (A)")
        ax.set_title("Current immediately before and after forming")
        if use_log and all(value > 0 for series in data for value in series):
            ax.set_yscale("log")
        ax.grid(True, axis="y", alpha=0.3)
        self.status.setText("Before is the current on the low side of the forming jump. After is the current on the high side.")

    def _draw_counts(self, ax, devices, order, colors, key: str):
        if key == "forming_polarity":
            categories = ["positive", "negative"]
            title = "Polarity of forming"
        else:
            categories = ["yes", "no"]
            title = "Permanently ohmic"
        x = np.arange(len(categories))
        width = 0.8 / max(len(order), 1)
        plotted = False
        for index, path in enumerate(order):
            counts = []
            for category in categories:
                counts.append(sum(
                    1
                    for device in devices
                    if device["sample_path"] == path and (device.get("metrics") or {}).get(key) == category
                ))
            offset = (index - (len(order) - 1) / 2) * width
            name = self.labels.get(path) or Path(path).name
            ax.bar(x + offset, counts, width=width * 0.9, color=colors[path], label=name)
            plotted = True
        ax.set_xticks(x)
        ax.set_xticklabels(["Positive", "Negative"] if key == "forming_polarity" else ["Ohmic", "Not ohmic"])
        ax.set_ylabel("Devices")
        ax.set_title(title)
        ax.grid(True, axis="y", alpha=0.3)
        if plotted:
            ax.legend(loc="best", fontsize=8)
        self.fig.tight_layout()
        if key == "permanently_ohmic":
            self.status.setText(
                "Ohmic means every sweep after forming has no jump, one log-log slope near 1, and an ON/OFF ratio below 2."
            )
        else:
            self.status.setText("Polarity is the sign of the earliest forming jump. Devices with no jump are not counted.")

    def _draw_evolution(self, devices: Sequence[Dict[str, Any]]):
        ax_i, ax_r = self.fig.subplots(2, 1, sharex=True)
        order, colors = self._groups(devices)
        seen = set()
        handles = []
        cutoff = float(self.cutoff.value())
        for device in devices:
            rows = evolution_rows(device, cutoff)
            xs = [row[0] for row in rows]
            current = [row[1] if row[1] not in (None, 0) else np.nan for row in rows]
            resistance = [row[2] if row[2] is not None else np.nan for row in rows]
            color = colors[device["sample_path"]]
            ax_i.plot(xs, current, color=color, alpha=0.75, linewidth=1.0)
            ax_r.plot(xs, resistance, color=color, alpha=0.75, linewidth=1.0)
            if device["sample_path"] not in seen:
                seen.add(device["sample_path"])
                handles.append(Line2D([0], [0], color=color, label=self._label_for(device)))
        ax_i.set_ylabel(f"|I| at {cutoff:g} V (A)")
        ax_r.set_ylabel(f"Resistance at {cutoff:g} V (ohm)")
        ax_r.set_xlabel("Sweep number")
        ax_i.set_title("Sweep-to-sweep evolution")
        if self.log_check.isChecked():
            ax_i.set_yscale("log")
        ax_i.grid(True, alpha=0.3)
        ax_r.grid(True, alpha=0.3)
        if handles:
            ax_i.legend(handles=handles, loc="best", fontsize=8)
        self.fig.tight_layout()
        self.status.setText(f"Each line is one device. Sweep 1 is the first measurement file. Values are taken at {cutoff:g} V.")

    def _fill_table(self, devices: Sequence[Dict[str, Any]]):
        self.table.setRowCount(len(devices))
        for row_index, device in enumerate(devices):
            metrics = device.get("metrics") or {}
            values = [
                self._label_for(device),
                device["section"],
                str(device["device_num"]),
                *[metrics.get(key) for key, _title in METRIC_FIELDS],
            ]
            for column, value in enumerate(values):
                if value is None:
                    text = ""
                elif isinstance(value, float):
                    text = f"{value:.6g}"
                else:
                    text = str(value)
                self.table.setItem(row_index, column, QTableWidgetItem(text))

    def _save_session(self):
        path, _selected = QFileDialog.getSaveFileName(self, "Save session", "", "JSON (*.json)")
        if not path:
            return
        payload = {
            "folders": [str(folder) for folder in self.folders],
            "sample_labels": dict(self.labels),
            "cutoff": float(self.cutoff.value()),
            "jump_ratio": float(self.ratio.value()),
            "normalisation": self.norm.currentData(),
            "log_y": self.log_check.isChecked(),
            "hidden_devices": [list(key) for key in sorted(self.hidden, key=lambda item: (item[0], item[1], item[2]))],
            "hidden_files": sorted(self.hidden_files),
            "file_count": int(self.file_count.value()),
            "figure": self.figure.currentData(),
            "metric": self.metric.currentData(),
        }
        try:
            save_session(Path(path), payload)
        except Exception as exc:
            QMessageBox.warning(self, "Could not save session", str(exc))
            return
        self.status.setText(f"Saved session to {path}")

    def _load_session(self):
        path, _selected = QFileDialog.getOpenFileName(self, "Load session", "", "JSON (*.json)")
        if not path:
            return
        try:
            payload = load_session(Path(path))
        except Exception as exc:
            QMessageBox.warning(self, "Could not load session", str(exc))
            return
        self.folders = [Path(folder).resolve() for folder in payload.get("folders") or []]
        self.labels = {str(Path(key).resolve()): str(value) for key, value in (payload.get("sample_labels") or {}).items()}
        self.hidden = set()
        for row in payload.get("hidden_devices") or []:
            if isinstance(row, (list, tuple)) and len(row) >= 3:
                self.hidden.add((str(Path(row[0]).resolve()), str(row[1]), int(row[2])))
        self.hidden_files = {path_key(raw) for raw in (payload.get("hidden_files") or [])}
        self._highlight_path = None
        self._filling = True
        self.file_count.setValue(int(payload.get("file_count") or 3))
        self.cutoff.setValue(float(payload.get("cutoff") or 0.5))
        self.ratio.setValue(float(payload.get("jump_ratio") or 10))
        norm = payload.get("normalisation") or "raw"
        index = self.norm.findData(norm)
        if index >= 0:
            self.norm.setCurrentIndex(index)
        self.log_check.setChecked(bool(payload.get("log_y")))
        figure = payload.get("figure") or "window"
        figure_index = self.figure.findData(figure)
        if figure_index >= 0:
            self.figure.setCurrentIndex(figure_index)
        metric = payload.get("metric") or _PLOT_METRICS[0][0]
        metric_index = self.metric.findData(metric)
        if metric_index >= 0:
            self.metric.setCurrentIndex(metric_index)
        self.metric.setEnabled(self.figure.currentData() == "metric")
        self._filling = False
        self._reload_devices()
        self.status.setText(f"Loaded session {path}")

    def _save_origin(self):
        devices = self._checked_devices()
        if not devices:
            QMessageBox.information(self, "Nothing to save", "Add sample folders and leave at least one device checked.")
            return
        name, ok = QInputDialog.getText(self, "Save for Origin", "Name for this export:")
        if not ok:
            return
        clean = sanitize_export_name(name.strip())
        if not clean:
            QMessageBox.warning(self, "Name required", "Enter a name so this export does not overwrite another.")
            return
        self.status.setText("Writing Origin tables…")
        self.repaint()
        try:
            out_dir = origin_data_dir(origin_export_root(self.folders), clean)
            export_origin(
                out_dir,
                devices,
                self.labels,
                float(self.cutoff.value()),
                float(self.ratio.value()),
                file_limit=int(self.file_count.value()),
                hidden_files=self.hidden_files,
            )
        except Exception as exc:
            QMessageBox.warning(self, "Origin export failed", str(exc))
            return
        self._fill_table(devices)
        self.status.setText(f"Origin tables written to {out_dir}")
