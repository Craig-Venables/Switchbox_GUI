"""
Filament Jump Finder GUI.

Main window: sample folder, threshold and options, Run; two result tabs
(First occurrence, All occurrences) with table + plot; CSV export; Inspect jumps dialog.
"""

import csv
from pathlib import Path
from typing import List, Dict, Any, Optional

import numpy as np
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTabWidget, QTableWidget, QTableWidgetItem, QFileDialog,
    QDoubleSpinBox, QCheckBox, QMessageBox, QDialog,
    QGroupBox, QScrollArea, QDialogButtonBox, QAbstractItemView, QHeaderView,
)
from PyQt5.QtCore import pyqtSignal
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter

try:
    from tools.device_visualizer.data.data_loader import DataLoader
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.device_visualizer.data.data_loader import DataLoader

from .core import (
    analyse_sample,
    get_first_and_all,
    find_jumps_in_curve,
)


class InspectJumpsDialog(QDialog):
    """Dialog showing IV curve for a device+file with all detected jumps and Include checkboxes."""

    # Emitted when any include state changes so main window can refresh
    inclusion_changed = pyqtSignal()
    # Emitted with list of new jump dicts to add to main _jumps
    jumps_to_add = pyqtSignal(list)
    # Emitted (section, device_num, filename, excluded: bool) when exclude-from-first toggled
    file_excluded_from_first_changed = pyqtSignal(str, int, str, bool)

    def __init__(
        self,
        file_path: Path,
        jumps_for_file: List[Dict[str, Any]],
        section: str,
        device_num: int,
        main_threshold: float,
        min_current: Optional[float],
        upward_only: bool,
        exclude_from_first: bool,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.file_path = Path(file_path)
        self.jumps_for_file = jumps_for_file  # list of refs into main jumps list, we may append
        self.section = section
        self.device_num = device_num
        self.main_threshold = main_threshold
        self.min_current = min_current
        self.upward_only = upward_only
        self._exclude_from_first = exclude_from_first
        self.setWindowTitle(f"Inspect jumps — {self.file_path.name}")
        self.setMinimumSize(800, 600)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        voltage, current, time_arr = DataLoader.load_raw_measurement(self.file_path)
        voltage = np.asarray(voltage)
        current = np.asarray(current)

        # IV dashboard 2x2 grid (linear IV, log IV, arrows, current vs time) like plotting module
        try:
            import sys
            root = Path(__file__).resolve().parents[2]
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            from plotting.device.iv_grid import IVGridPlotter
            grid = IVGridPlotter(figsize=(10, 8))
            fig, axes = grid.plot_grid(
                voltage, current, time=time_arr,
                title=self.file_path.name, device_label="",
                save_name=None,
            )
        except Exception:
            # Fallback: simple 2-panel (linear + log)
            fig = Figure(figsize=(10, 6), dpi=100)
            ax1 = fig.add_subplot(121)
            ax1.plot(voltage, current, "o-", markersize=2)
            ax1.set_xlabel("Voltage (V)")
            ax1.set_ylabel("Current (A)")
            ax1.grid(True, alpha=0.3)
            ax2 = fig.add_subplot(122)
            ax2.plot(voltage, np.abs(current), "o-", markersize=2)
            ax2.set_yscale("log")
            ax2.set_xlabel("Voltage (V)")
            ax2.set_ylabel("|Current| (A)")
            ax2.grid(True, which="both", alpha=0.3)
            axes = np.array([[ax1, ax2], [None, None]])

        # Add jump markers to linear and log panels
        for j in self.jumps_for_file:
            v = j.get('voltage_mid', j.get('voltage'))
            if v is not None:
                if axes.flat[0] is not None:
                    axes.flat[0].axvline(v, color='red', alpha=0.7, linestyle='--')
                if len(axes.flat) > 1 and axes.flat[1] is not None:
                    axes.flat[1].axvline(v, color='red', alpha=0.7, linestyle='--')

        fig.tight_layout()
        canvas = FigureCanvasQTAgg(fig)
        toolbar = NavigationToolbar2QT(canvas, self)
        layout.addWidget(toolbar)
        layout.addWidget(canvas)

        # Exclude this file from first occurrence
        excl_row = QHBoxLayout()
        self.exclude_from_first_cb = QCheckBox("Exclude this file from first occurrence (use next file instead)")
        self.exclude_from_first_cb.setChecked(self._exclude_from_first)
        self.exclude_from_first_cb.toggled.connect(self._on_exclude_from_first_toggled)
        excl_row.addWidget(self.exclude_from_first_cb)
        excl_row.addStretch()
        layout.addLayout(excl_row)

        # Find more (sub-threshold) jumps
        find_row = QHBoxLayout()
        find_row.addWidget(QLabel("Show jumps with ratio ≥"))
        self.inspect_threshold_spin = QDoubleSpinBox()
        self.inspect_threshold_spin.setRange(1.5, 100.0)
        self.inspect_threshold_spin.setValue(2.0)
        self.inspect_threshold_spin.setDecimals(1)
        self.inspect_threshold_spin.setSingleStep(0.5)
        find_row.addWidget(self.inspect_threshold_spin)
        find_row.addWidget(QLabel("(main threshold is {:.1f})".format(self.main_threshold)))
        find_more_btn = QPushButton("Find more jumps")
        find_more_btn.clicked.connect(self._find_more_jumps)
        find_row.addWidget(find_more_btn)
        find_row.addStretch()
        layout.addLayout(find_row)

        # Jump list with Include checkboxes
        self.jump_group = QGroupBox("Detected jumps (toggle Include to add/remove from results)")
        self.jump_group_layout = QVBoxLayout(self.jump_group)
        self.jump_scroll = QScrollArea()
        self.jump_scroll.setWidgetResizable(True)
        self.jump_inner = QWidget()
        self.jump_inner_layout = QVBoxLayout(self.jump_inner)
        self.jump_group_layout.addWidget(self.jump_scroll)
        self.jump_scroll.setWidget(self.jump_inner)
        layout.addWidget(self.jump_group)
        self._build_jump_list()

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.accept)
        layout.addWidget(buttons)

    def _on_exclude_from_first_toggled(self, checked: bool):
        self._exclude_from_first = checked
        self.file_excluded_from_first_changed.emit(
            self.section, self.device_num, self.file_path.name, checked
        )
        self.inclusion_changed.emit()

    def _find_more_jumps(self):
        voltage, current, _ = DataLoader.load_raw_measurement(self.file_path)
        voltage = np.asarray(voltage)
        current = np.asarray(current)
        if len(voltage) < 2 or len(current) < 2:
            return
        thresh = self.inspect_threshold_spin.value()
        extra = find_jumps_in_curve(
            voltage, current,
            min_ratio=thresh,
            min_current=self.min_current,
            upward_only=self.upward_only,
        )
        existing = {(j.get('voltage_mid'), j.get('index')) for j in self.jumps_for_file}
        added = []
        for j in extra:
            key = (j.get('voltage_mid'), j.get('index'))
            if key not in existing:
                j = dict(j)
                j['included'] = True
                j['section'] = self.section
                j['device_num'] = self.device_num
                j['device_id'] = f"{self.section}_{self.device_num}"
                j['filename'] = self.file_path.name
                j['file_path'] = self.file_path
                j['voltage'] = j['voltage_mid']
                self.jumps_for_file.append(j)
                added.append(j)
                existing.add(key)
        if added:
            self.jumps_to_add.emit(added)
            self._build_jump_list()
            # Add new jump markers to IV plots and redraw
            for w in self.findChildren(FigureCanvasQTAgg):
                fig = w.figure
                if fig.axes:
                    for j in added:
                        v = j.get('voltage_mid', j.get('voltage'))
                        if v is not None:
                            for ax in fig.axes[:2]:  # linear and log panels
                                ax.axvline(v, color='red', alpha=0.7, linestyle='--')
                w.draw_idle()
                break

    def _build_jump_list(self):
        # Clear existing content
        while self.jump_inner_layout.count():
            item = self.jump_inner_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for j in self.jumps_for_file:
            row = QHBoxLayout()
            cb = QCheckBox("Include")
            cb.setChecked(j.get('included', True))

            def make_toggled(jump_ref):
                def on_toggled(checked):
                    jump_ref['included'] = checked
                    self.inclusion_changed.emit()
                return on_toggled

            cb.toggled.connect(make_toggled(j))
            row.addWidget(cb)
            v = j.get('voltage_mid', j.get('voltage'))
            ratio = j.get('ratio', 0)
            row.addWidget(QLabel(f"V = {v:.4f} V, ratio = {ratio:.2f}"))
            row.addStretch()
            self.jump_inner_layout.addLayout(row)
        self.jump_inner_layout.addStretch()


class MainWindow(QMainWindow):
    """Main window: folder, threshold, Run; two tabs (First / All) with table + plot; CSV export; Inspect."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Filament Jump Finder")
        self.setMinimumSize(1000, 700)
        self._analysis = None  # result of analyse_sample
        self._jumps: List[Dict[str, Any]] = []
        self._section_device_nums = {}
        self._excluded_files_from_first: set = set()  # (section, device_num, filename)
        self._main_threshold = 10.0
        self._min_current: Optional[float] = None
        self._upward_only = False
        self._init_ui()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Top: folder + options + Run
        top = QHBoxLayout()
        top.addWidget(QLabel("Sample folder:"))
        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText("Path to sample directory")
        top.addWidget(self.folder_edit)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse)
        top.addWidget(browse_btn)
        layout.addLayout(top)

        opts = QHBoxLayout()
        opts.addWidget(QLabel("Jump ratio threshold (≥):"))
        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(2.0, 1000.0)
        self.threshold_spin.setValue(10.0)
        self.threshold_spin.setDecimals(1)
        self.threshold_spin.setSingleStep(5.0)
        opts.addWidget(self.threshold_spin)
        opts.addWidget(QLabel("Min current (A, optional):"))
        self.min_current_edit = QLineEdit()
        self.min_current_edit.setPlaceholderText("e.g. 1e-12 or leave empty")
        self.min_current_edit.setMaximumWidth(120)
        opts.addWidget(self.min_current_edit)
        self.upward_only_cb = QCheckBox("Only upward jumps")
        self.upward_only_cb.setChecked(False)
        opts.addWidget(self.upward_only_cb)
        opts.addStretch()
        run_btn = QPushButton("Run")
        run_btn.clicked.connect(self._run)
        opts.addWidget(run_btn)
        layout.addLayout(opts)

        # Tabs: First occurrence, All occurrences
        self.tabs = QTabWidget()
        self.first_table = QTableWidget()
        self.first_table.setColumnCount(5)
        self.first_table.setHorizontalHeaderLabels(["Include", "Section", "Device #", "Filename", "Voltage (V)"])
        self.first_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.first_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.first_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.first_table.doubleClicked.connect(self._on_first_double_click)
        self.first_fig = Figure(figsize=(8, 6), dpi=100)
        self.first_canvas = FigureCanvasQTAgg(self.first_fig)
        self.first_toolbar = NavigationToolbar2QT(self.first_canvas, self)
        first_layout = QVBoxLayout()
        first_layout.addWidget(self.first_toolbar)
        first_layout.addWidget(self.first_canvas)
        first_layout.addWidget(QLabel("First occurrence table:"))
        first_layout.addWidget(self.first_table)
        first_export = QPushButton("Export CSV (first)")
        first_export.clicked.connect(lambda: self._export_csv('first'))
        first_layout.addWidget(first_export)
        first_w = QWidget()
        first_w.setLayout(first_layout)
        self.tabs.addTab(first_w, "First occurrence")

        self.all_table = QTableWidget()
        self.all_table.setColumnCount(5)
        self.all_table.setHorizontalHeaderLabels(["Include", "Section", "Device #", "Filename", "Voltage (V)"])
        self.all_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.all_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.all_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.all_table.doubleClicked.connect(self._on_all_double_click)
        self.all_fig = Figure(figsize=(8, 6), dpi=100)
        self.all_canvas = FigureCanvasQTAgg(self.all_fig)
        self.all_toolbar = NavigationToolbar2QT(self.all_canvas, self)
        all_layout = QVBoxLayout()
        all_layout.addWidget(self.all_toolbar)
        all_layout.addWidget(self.all_canvas)
        all_layout.addWidget(QLabel("All occurrences table:"))
        all_layout.addWidget(self.all_table)
        all_export = QPushButton("Export CSV (all)")
        all_export.clicked.connect(lambda: self._export_csv('all'))
        all_layout.addWidget(all_export)
        all_w = QWidget()
        all_w.setLayout(all_layout)
        self.tabs.addTab(all_w, "All occurrences")

        layout.addWidget(self.tabs)
        self.inspect_btn = QPushButton("Inspect jumps for selected row")
        self.inspect_btn.clicked.connect(self._inspect_selected)
        layout.addWidget(self.inspect_btn)
        self.status = QLabel("Select a sample folder and click Run.")
        layout.addWidget(self.status)

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, "Select sample folder")
        if path:
            self.folder_edit.setText(path)

    def _parse_min_current(self) -> Optional[float]:
        text = self.min_current_edit.text().strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    def _run(self):
        folder = self.folder_edit.text().strip()
        if not folder:
            QMessageBox.warning(self, "No folder", "Please select a sample folder.")
            return
        path = Path(folder)
        if not path.exists():
            QMessageBox.warning(self, "Invalid folder", f"Folder does not exist: {path}")
            return
        min_ratio = self.threshold_spin.value()
        min_current = self._parse_min_current()
        upward_only = self.upward_only_cb.isChecked()
        self._main_threshold = min_ratio
        self._min_current = min_current
        self._upward_only = upward_only
        self._excluded_files_from_first.clear()  # Reset when running new analysis
        self._analysis = analyse_sample(path, min_ratio=min_ratio, min_current=min_current, upward_only=upward_only)
        self._jumps = self._analysis.get('jumps', [])
        self._section_device_nums = self._analysis.get('section_device_nums', {})
        if not self._jumps:
            self.status.setText("No jumps detected. Try lowering the ratio threshold or check the folder.")
        else:
            self.status.setText(f"Found {len(self._jumps)} jump(s). Toggle Include in Inspect to refine.")
        self._refresh_results()

    def _refresh_results(self):
        if not self._jumps:
            self.first_table.setRowCount(0)
            self.all_table.setRowCount(0)
            self._plot_first([])
            self._plot_all([])
            return
        first_list, all_list = get_first_and_all(
            self._jumps,
            excluded_files_from_first=self._excluded_files_from_first,
        )
        self._fill_table(self.first_table, first_list)
        self._fill_table(self.all_table, all_list)
        self._plot_first(first_list)
        self._plot_all(all_list)

    def _fill_table(self, table: QTableWidget, rows: List[Dict]):
        table.setRowCount(len(rows))
        for r, j in enumerate(rows):
            cb = QCheckBox("Include")
            cb.setChecked(j.get('included', True))

            def make_toggled(jump_ref):
                def on_toggled(checked):
                    jump_ref['included'] = checked
                    self._refresh_results()
                return on_toggled

            cb.toggled.connect(make_toggled(j))
            table.setCellWidget(r, 0, cb)
            table.setItem(r, 1, QTableWidgetItem(str(j.get('section', ''))))
            table.setItem(r, 2, QTableWidgetItem(str(j.get('device_num', ''))))
            table.setItem(r, 3, QTableWidgetItem(str(j.get('filename', ''))))
            v = j.get('voltage', j.get('voltage_mid'))
            table.setItem(r, 4, QTableWidgetItem(f"{v:.6g}" if v is not None else "—"))
        for c in range(5):
            table.setColumnWidth(c, 100 if c == 0 else 120)

    def _plot_first(self, first_list: List[Dict]):
        self._plot_voltage_vs_device(first_list, self.first_fig, "First occurrence")

    def _plot_all(self, all_list: List[Dict]):
        self._plot_voltage_vs_device(all_list, self.all_fig, "All occurrences")

    def _plot_voltage_vs_device(self, rows: List[Dict], fig: Figure, title: str):
        fig.clear()
        if not rows:
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, "No data", ha='center', va='center')
            fig.tight_layout()
            fig.canvas.draw_idle()
            return
        voltages = []
        for j in rows:
            v = j.get('voltage', j.get('voltage_mid'))
            if v is not None:
                voltages.append(float(v))
        if not voltages:
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, "No data", ha='center', va='center')
            fig.tight_layout()
            fig.canvas.draw_idle()
            return
        bin_width = 0.2
        v_min, v_max = min(voltages), max(voltages)
        start_s = np.floor(v_min / bin_width) * bin_width
        stop_s = np.ceil(v_max / bin_width) * bin_width + 0.01
        bins_signed = np.arange(start_s, stop_s, bin_width)
        if len(bins_signed) < 2:
            bins_signed = np.array([start_s, start_s + bin_width])
        ax1 = fig.add_subplot(211)
        ax1.hist(voltages, bins=bins_signed, edgecolor='black', alpha=0.7)
        ax1.set_xlabel("Jump voltage (V)")
        ax1.set_ylabel("Count")
        ax1.set_title(title + " — signed")
        ax1.grid(True, alpha=0.3)
        ax1.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.1f}"))
        ax2 = fig.add_subplot(212)
        abs_v = [abs(v) for v in voltages]
        bins_abs = np.arange(0, np.ceil(max(abs_v) / bin_width) * bin_width + 0.01, bin_width)
        if len(bins_abs) < 2:
            bins_abs = np.array([0.0, bin_width])
        ax2.hist(abs_v, bins=bins_abs, edgecolor='black', alpha=0.7)
        ax2.set_xlabel("|Jump voltage| (V)")
        ax2.set_ylabel("Count")
        ax2.set_title(title + " — absolute")
        ax2.grid(True, alpha=0.3)
        ax2.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.1f}"))
        fig.tight_layout()
        fig.canvas.draw_idle()

    def _export_csv(self, mode: str):
        if not self._jumps:
            QMessageBox.information(self, "No data", "Run analysis first.")
            return
        first_list, all_list = get_first_and_all(
            self._jumps,
            excluded_files_from_first=self._excluded_files_from_first,
        )
        rows = first_list if mode == 'first' else all_list
        path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "", "CSV (*.csv)")
        if not path:
            return
        with open(path, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(["section", "device_num", "filename", "voltage"])
            for j in rows:
                w.writerow([
                    j.get('section', ''),
                    j.get('device_num', ''),
                    j.get('filename', ''),
                    j.get('voltage', j.get('voltage_mid', '')),
                ])
        self.status.setText(f"Exported to {path}")

    def _get_selected_jump(self, table: QTableWidget) -> Optional[Dict]:
        row = table.currentRow()
        if row < 0 or row >= table.rowCount():
            return None
        section = table.item(row, 1)
        device_num = table.item(row, 2)
        filename = table.item(row, 3)
        if not all([section, device_num, filename]):
            return None
        section = section.text()
        try:
            device_num = int(device_num.text())
        except (ValueError, TypeError):
            return None
        filename = filename.text()
        for j in self._jumps:
            if j.get('section') == section and j.get('device_num') == device_num and j.get('filename') == filename:
                return j
        return None

    def _on_first_double_click(self, _index):
        self._open_inspect_from_table(self.first_table)

    def _on_all_double_click(self, _index):
        self._open_inspect_from_table(self.all_table)

    def _open_inspect_from_table(self, table: QTableWidget):
        j = self._get_selected_jump(table)
        if j is None:
            QMessageBox.information(self, "Select row", "Select a row first (or double-click a row).")
            return
        file_path = j.get('file_path')
        if not file_path:
            QMessageBox.warning(self, "No file", "This row has no file path.")
            return
        jumps_for_file = [x for x in self._jumps if x.get('file_path') == file_path]
        section = j.get('section', '')
        device_num = j.get('device_num', 0)
        file_key = (section, device_num, Path(file_path).name)
        exclude_from_first = file_key in self._excluded_files_from_first
        dlg = InspectJumpsDialog(
            Path(file_path),
            jumps_for_file,
            section=section,
            device_num=device_num,
            main_threshold=self._main_threshold,
            min_current=self._min_current,
            upward_only=self._upward_only,
            exclude_from_first=exclude_from_first,
            parent=self,
        )
        dlg.inclusion_changed.connect(self._refresh_results)
        dlg.jumps_to_add.connect(self._on_jumps_to_add)
        dlg.file_excluded_from_first_changed.connect(self._on_file_excluded_from_first)
        dlg.exec_()

    def _on_jumps_to_add(self, new_jumps: list):
        self._jumps.extend(new_jumps)
        self._refresh_results()

    def _on_file_excluded_from_first(self, section: str, device_num: int, filename: str, excluded: bool):
        key = (section, device_num, filename)
        if excluded:
            self._excluded_files_from_first.add(key)
        else:
            self._excluded_files_from_first.discard(key)
        self._refresh_results()

    def _inspect_selected(self):
        tab = self.tabs.currentWidget()
        table = self.first_table if self.tabs.currentIndex() == 0 else self.all_table
        self._open_inspect_from_table(table)
