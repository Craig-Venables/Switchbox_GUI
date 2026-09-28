"""
Filament Jump Finder GUI.

Multi-folder load → live ratio / voltage window → mark Jump / Not a jump →
Compare yield (all + memristive) → Save Session / Save for Origin.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional

import numpy as np
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QFileDialog,
    QDoubleSpinBox, QCheckBox, QMessageBox, QDialog, QSlider,
    QGroupBox, QScrollArea, QDialogButtonBox, QAbstractItemView, QHeaderView,
    QSplitter, QTabWidget, QListWidget, QListWidgetItem, QListView, QTreeView,
    QShortcut, QApplication, QScrollArea, QComboBox, QInputDialog,
)
from PyQt5.QtCore import pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QKeySequence, QBrush, QColor
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter, MaxNLocator

try:
    from tools.device_visualizer.data.data_loader import DataLoader
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.device_visualizer.data.data_loader import DataLoader

from .core import (
    load_folders,
    filter_jumps,
    find_jumps_in_curve,
    jump_decision_key,
    histogram_bins,
    compute_yield_summary,
    resolve_device_iv_curve,
    memristive_devices_by_jump,
    origin_export_root,
    DETECTION_FLOOR_RATIO,
    NDR_SOFT_THRESHOLD,
    NDR_STRONG_THRESHOLD,
)
from .origin_export import (
    export_origin_files,
    load_review_json,
    load_session,
    save_session,
    apply_review_to_decisions,
    apply_review_excluded_files,
    session_folder_paths,
    sanitize_export_name,
    ORIGIN_DIR_NAME,
)


class InspectJumpsDialog(QDialog):
    """Dialog showing IV curve for a device+file with include checkboxes."""

    inclusion_changed = pyqtSignal()
    jumps_to_add = pyqtSignal(list)
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
        curve_cache: Optional[Dict] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.file_path = Path(file_path)
        self.jumps_for_file = jumps_for_file
        self.section = section
        self.device_num = device_num
        self.main_threshold = main_threshold
        self.min_current = min_current
        self.upward_only = upward_only
        self._exclude_from_first = exclude_from_first
        self._curve_cache = curve_cache or {}
        self.setWindowTitle(f"Inspect jumps — {self.file_path.name}")
        self.setMinimumSize(800, 600)
        self._build_ui()

    def _load_curve(self):
        cached = self._curve_cache.get(self.file_path)
        if cached is not None:
            return (
                np.asarray(cached['voltage']),
                np.asarray(cached['current']),
                cached.get('time'),
            )
        voltage, current, time_arr = DataLoader.load_raw_measurement(self.file_path)
        return np.asarray(voltage), np.asarray(current), time_arr

    def _build_ui(self):
        layout = QVBoxLayout(self)
        voltage, current, time_arr = self._load_curve()

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

        for j in self.jumps_for_file:
            v = j.get('voltage_mid', j.get('voltage'))
            if v is not None:
                color = 'green' if j.get('included', True) else 'grey'
                if axes.flat[0] is not None:
                    axes.flat[0].axvline(v, color=color, alpha=0.7, linestyle='--')
                if len(axes.flat) > 1 and axes.flat[1] is not None:
                    axes.flat[1].axvline(v, color=color, alpha=0.7, linestyle='--')

        fig.tight_layout()
        canvas = FigureCanvasQTAgg(fig)
        toolbar = NavigationToolbar2QT(canvas, self)
        layout.addWidget(toolbar)
        layout.addWidget(canvas)

        excl_row = QHBoxLayout()
        self.exclude_from_first_cb = QCheckBox(
            "Exclude this file from first occurrence (use next file instead)"
        )
        self.exclude_from_first_cb.setChecked(self._exclude_from_first)
        self.exclude_from_first_cb.toggled.connect(self._on_exclude_from_first_toggled)
        excl_row.addWidget(self.exclude_from_first_cb)
        excl_row.addStretch()
        layout.addLayout(excl_row)

        find_row = QHBoxLayout()
        find_row.addWidget(QLabel("Show jumps with ratio ≥"))
        self.inspect_threshold_spin = QDoubleSpinBox()
        self.inspect_threshold_spin.setRange(DETECTION_FLOOR_RATIO, 100.0)
        self.inspect_threshold_spin.setValue(2.0)
        self.inspect_threshold_spin.setDecimals(1)
        self.inspect_threshold_spin.setSingleStep(0.5)
        find_row.addWidget(self.inspect_threshold_spin)
        find_row.addWidget(QLabel(f"(main threshold is {self.main_threshold:.1f})"))
        find_more_btn = QPushButton("Find more jumps")
        find_more_btn.clicked.connect(self._find_more_jumps)
        find_row.addWidget(find_more_btn)
        find_row.addStretch()
        layout.addLayout(find_row)

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
        voltage, current, _ = self._load_curve()
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

    def _build_jump_list(self):
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
    """Live filament jump review with multi-folder sessions and Compare tab."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Filament Jump Finder")
        self.setMinimumSize(1280, 820)

        self._folder_paths: List[Path] = []
        self._all_jumps: List[Dict[str, Any]] = []
        self._filtered: List[Dict[str, Any]] = []
        self._curve_cache: Dict[Path, Dict[str, Any]] = {}
        self._device_registry: List[Dict[str, Any]] = []
        self._decisions: Dict[str, bool] = {}
        self._excluded_files_from_first: set = set()
        self._selected_index: int = -1
        self._marker_artists = []
        self._updating_controls = False
        self._yield_summary: Optional[Dict[str, Any]] = None
        self._jump_by_key: Dict[str, Dict[str, Any]] = {}
        self._compare_dirty = False
        self._compare_refresh_timer = QTimer(self)
        self._compare_refresh_timer.setSingleShot(True)
        self._compare_refresh_timer.setInterval(400)
        self._compare_refresh_timer.timeout.connect(self._flush_compare_refresh)
        self._hist_refresh_timer = QTimer(self)
        self._hist_refresh_timer.setSingleShot(True)
        self._hist_refresh_timer.setInterval(200)
        self._hist_refresh_timer.timeout.connect(self._flush_hist_refresh)

        self._init_ui()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # --- Folders list + session / origin ---
        folder_row = QHBoxLayout()
        folder_col = QVBoxLayout()
        folder_col.addWidget(QLabel("Loaded folders"))
        self.folder_list = QListWidget()
        self.folder_list.setMaximumHeight(90)
        self.folder_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        folder_col.addWidget(self.folder_list)
        folder_row.addLayout(folder_col, stretch=1)

        folder_btns = QVBoxLayout()
        add_btn = QPushButton("Add folders…")
        add_btn.clicked.connect(self._add_folders)
        folder_btns.addWidget(add_btn)
        remove_btn = QPushButton("Remove selected")
        remove_btn.clicked.connect(self._remove_selected_folders)
        folder_btns.addWidget(remove_btn)
        reload_btn = QPushButton("Reload")
        reload_btn.clicked.connect(self._reload_folders)
        folder_btns.addWidget(reload_btn)
        folder_btns.addStretch()
        folder_row.addLayout(folder_btns)

        session_btns = QVBoxLayout()
        save_sess = QPushButton("Save Session…")
        save_sess.clicked.connect(self._save_session)
        session_btns.addWidget(save_sess)
        load_sess = QPushButton("Load Session…")
        load_sess.clicked.connect(self._load_session)
        session_btns.addWidget(load_sess)
        save_origin = QPushButton("Save for Origin")
        save_origin.clicked.connect(self._save_origin)
        session_btns.addWidget(save_origin)
        session_btns.addStretch()
        folder_row.addLayout(session_btns)
        root.addLayout(folder_row)

        # Back-compat hidden field for --sample / run_gui
        self.folder_edit = QLineEdit()
        self.folder_edit.hide()

        # --- Live filter controls ---
        opts = QHBoxLayout()
        opts.addWidget(QLabel("Jump ratio ≥"))
        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(DETECTION_FLOOR_RATIO, 1000.0)
        self.threshold_spin.setValue(10.0)
        self.threshold_spin.setDecimals(1)
        self.threshold_spin.setSingleStep(0.5)
        self.threshold_spin.valueChanged.connect(self._on_threshold_spin)
        opts.addWidget(self.threshold_spin)

        self.threshold_slider = QSlider(Qt.Horizontal)
        self.threshold_slider.setRange(int(DETECTION_FLOOR_RATIO * 10), 200)
        self.threshold_slider.setValue(100)
        self.threshold_slider.setMinimumWidth(120)
        self.threshold_slider.valueChanged.connect(self._on_threshold_slider)
        opts.addWidget(self.threshold_slider)

        opts.addWidget(QLabel("V from"))
        self.v_min_spin = QDoubleSpinBox()
        self.v_min_spin.setRange(-100.0, 100.0)
        self.v_min_spin.setDecimals(2)
        self.v_min_spin.setSingleStep(0.1)
        self.v_min_spin.setValue(2.0)
        self.v_min_spin.valueChanged.connect(self._on_filters_changed)
        opts.addWidget(self.v_min_spin)

        opts.addWidget(QLabel("to"))
        self.v_max_spin = QDoubleSpinBox()
        self.v_max_spin.setRange(-100.0, 100.0)
        self.v_max_spin.setDecimals(2)
        self.v_max_spin.setSingleStep(0.1)
        self.v_max_spin.setValue(3.0)
        self.v_max_spin.valueChanged.connect(self._on_filters_changed)
        opts.addWidget(self.v_max_spin)

        self.v_window_cb = QCheckBox("Voltage window")
        self.v_window_cb.setChecked(True)
        self.v_window_cb.toggled.connect(self._on_filters_changed)
        opts.addWidget(self.v_window_cb)

        self.abs_v_cb = QCheckBox("Use |V|")
        self.abs_v_cb.setChecked(True)
        self.abs_v_cb.setToolTip("Apply voltage window to absolute voltage (both sweep directions)")
        self.abs_v_cb.toggled.connect(self._on_filters_changed)
        opts.addWidget(self.abs_v_cb)

        opts.addWidget(QLabel("Min current (A):"))
        self.min_current_edit = QLineEdit()
        self.min_current_edit.setPlaceholderText("optional")
        self.min_current_edit.setMaximumWidth(100)
        self.min_current_edit.textChanged.connect(self._on_filters_changed)
        opts.addWidget(self.min_current_edit)

        self.upward_only_cb = QCheckBox("Only upward")
        self.upward_only_cb.setChecked(False)
        self.upward_only_cb.toggled.connect(self._on_filters_changed)
        opts.addWidget(self.upward_only_cb)

        opts.addStretch()
        self.count_label = QLabel("Add device folders to begin.")
        self.count_label.setStyleSheet("font-weight: bold;")
        opts.addWidget(self.count_label)
        root.addLayout(opts)

        # --- Tabs: Review | Compare ---
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_review_tab(), "Review")
        self.tabs.addTab(self._build_compare_tab(), "Compare")
        root.addWidget(self.tabs, stretch=1)

        self.status = QLabel("Add one or more device folders (e.g. D110, D112), then review jumps.")
        root.addWidget(self.status)

        self._draw_empty_iv()
        self._plot_histogram([])
        self._plot_compare_empty()

    def _build_review_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        splitter = QSplitter(Qt.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("Jumps (current filters)"))
        self.jump_table = QTableWidget()
        self.jump_table.setColumnCount(7)
        self.jump_table.setHorizontalHeaderLabels([
            "Status", "Folder", "Section", "Device", "Filename", "Voltage (V)", "Ratio",
        ])
        self.jump_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.jump_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.jump_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.jump_table.setToolTip("Ctrl/Shift-click to multi-select, then A=accept or R=reject all selected")
        self.jump_table.itemSelectionChanged.connect(self._on_table_selection)
        self.jump_table.doubleClicked.connect(self._inspect_selected)
        left_layout.addWidget(self.jump_table)
        bulk_row = QHBoxLayout()
        reject_sel = QPushButton("Reject selected")
        reject_sel.setToolTip("Reject all highlighted rows (R / Delete)")
        reject_sel.clicked.connect(lambda: self._set_selected_included(False, advance=True))
        bulk_row.addWidget(reject_sel)
        accept_sel = QPushButton("Accept selected")
        accept_sel.setToolTip("Accept all highlighted rows (A / Enter)")
        accept_sel.clicked.connect(lambda: self._set_selected_included(True, advance=True))
        bulk_row.addWidget(accept_sel)
        bulk_row.addStretch()
        left_layout.addLayout(bulk_row)
        inspect_btn = QPushButton("Inspect file (exclude from first…)")
        inspect_btn.clicked.connect(self._inspect_selected)
        left_layout.addWidget(inspect_btn)
        splitter.addWidget(left)

        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        self.iv_fig = Figure(figsize=(6, 5), dpi=100)
        self.iv_canvas = FigureCanvasQTAgg(self.iv_fig)
        self.iv_toolbar = NavigationToolbar2QT(self.iv_canvas, self)
        center_layout.addWidget(self.iv_toolbar)
        center_layout.addWidget(self.iv_canvas, stretch=1)
        self.iv_canvas.mpl_connect('button_press_event', self._on_iv_click)

        actions = QHBoxLayout()
        prev_btn = QPushButton("◀ Previous")
        prev_btn.setToolTip("Previous jump (Left / Up)")
        prev_btn.clicked.connect(self._prev_jump)
        actions.addWidget(prev_btn)
        jump_btn = QPushButton("Jump (A)")
        jump_btn.setStyleSheet("background-color: #4caf50; color: white; font-weight: bold;")
        jump_btn.setToolTip("Accept selected row(s) as jump (A or Enter) — advances to next")
        jump_btn.clicked.connect(lambda: self._set_selected_included(True, advance=True))
        actions.addWidget(jump_btn)
        not_btn = QPushButton("Not a jump (R)")
        not_btn.setStyleSheet("background-color: #9e9e9e; color: white; font-weight: bold;")
        not_btn.setToolTip("Reject selected row(s) (R / X / Delete) — advances past selection")
        not_btn.clicked.connect(lambda: self._set_selected_included(False, advance=True))
        actions.addWidget(not_btn)
        next_btn = QPushButton("Next ▶")
        next_btn.setToolTip("Next jump (Right / Down)")
        next_btn.clicked.connect(self._next_jump)
        actions.addWidget(next_btn)
        center_layout.addLayout(actions)
        self.selection_label = QLabel("No jump selected.  Shortcuts: A=Jump, R=Reject, ←/→=Prev/Next")
        center_layout.addWidget(self.selection_label)
        splitter.addWidget(center)
        self._install_shortcuts()

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(QLabel("Accepted jump voltages"))
        self.hist_fig = Figure(figsize=(5, 5), dpi=100)
        self.hist_canvas = FigureCanvasQTAgg(self.hist_fig)
        self.hist_toolbar = NavigationToolbar2QT(self.hist_canvas, self)
        right_layout.addWidget(self.hist_toolbar)
        right_layout.addWidget(self.hist_canvas, stretch=1)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 2)
        layout.addWidget(splitter)
        return tab

    def _build_compare_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.compare_status = QLabel(
            "Load folders to see yield, NDR, and memristive IV overlays."
        )
        self.compare_status.setWordWrap(True)
        layout.addWidget(self.compare_status)

        self.compare_tabs = QTabWidget()
        self.compare_tabs.currentChanged.connect(self._on_compare_tab_changed)

        # --- Yield ---
        yield_w = QWidget()
        yield_l = QVBoxLayout(yield_w)
        self.yield_fig = Figure(figsize=(10, 6), dpi=100)
        self.yield_canvas = FigureCanvasQTAgg(self.yield_fig)
        yield_l.addWidget(NavigationToolbar2QT(self.yield_canvas, self))
        yield_l.addWidget(self.yield_canvas, stretch=1)
        self.compare_tabs.addTab(yield_w, "Yield")

        # --- NDR ---
        ndr_w = QWidget()
        ndr_l = QVBoxLayout(ndr_w)
        self.ndr_fig = Figure(figsize=(10, 7), dpi=100)
        self.ndr_canvas = FigureCanvasQTAgg(self.ndr_fig)
        ndr_l.addWidget(NavigationToolbar2QT(self.ndr_canvas, self))
        ndr_l.addWidget(self.ndr_canvas, stretch=1)
        self.compare_tabs.addTab(ndr_w, "NDR")

        # --- Memristive IVs (all devices) ---
        mem_w = QWidget()
        mem_l = QVBoxLayout(mem_w)
        filt_row = QHBoxLayout()
        filt_row.addWidget(QLabel("Sample:"))
        self.mem_iv_folder_combo = QComboBox()
        self.mem_iv_folder_combo.currentIndexChanged.connect(self._on_mem_iv_folder_changed)
        filt_row.addWidget(self.mem_iv_folder_combo, stretch=1)
        self.mem_iv_count_label = QLabel("")
        filt_row.addWidget(self.mem_iv_count_label)
        mem_l.addLayout(filt_row)
        self.mem_iv_fig = Figure(figsize=(11, 8), dpi=100)
        self.mem_iv_canvas = FigureCanvasQTAgg(self.mem_iv_fig)
        mem_l.addWidget(NavigationToolbar2QT(self.mem_iv_canvas, self))
        mem_l.addWidget(self.mem_iv_canvas, stretch=1)
        self.compare_tabs.addTab(mem_w, "Memristive IVs")

        # --- Best pair showcase ---
        best_w = QWidget()
        best_l = QVBoxLayout(best_w)
        best_filt = QHBoxLayout()
        best_filt.addWidget(QLabel("Sample:"))
        self.best_pair_folder_combo = QComboBox()
        self.best_pair_folder_combo.currentIndexChanged.connect(self._on_best_pair_folder_changed)
        best_filt.addWidget(self.best_pair_folder_combo, stretch=1)
        best_l.addLayout(best_filt)
        self.best_pair_fig = Figure(figsize=(11, 5), dpi=100)
        self.best_pair_canvas = FigureCanvasQTAgg(self.best_pair_fig)
        best_l.addWidget(NavigationToolbar2QT(self.best_pair_canvas, self))
        best_l.addWidget(self.best_pair_canvas, stretch=1)
        self.compare_tabs.addTab(best_w, "Best pair")

        layout.addWidget(self.compare_tabs, stretch=1)
        # Back-compat aliases so empty plot helpers still work during transition
        self.compare_fig = self.yield_fig
        self.compare_canvas = self.yield_canvas
        return tab

    # ------------------------------------------------------------------ folders
    def _refresh_folder_list(self):
        self.folder_list.clear()
        for p in self._folder_paths:
            item = QListWidgetItem(f"{p.name}  —  {p}")
            item.setData(Qt.UserRole, str(p))
            self.folder_list.addItem(item)
        if self._folder_paths:
            self.folder_edit.setText(str(self._folder_paths[0]))

    def _add_folders(self):
        dialog = QFileDialog(self, "Select device folders")
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setOption(QFileDialog.ShowDirsOnly, True)
        dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        for view in dialog.findChildren(QListView) + dialog.findChildren(QTreeView):
            if isinstance(view, (QListView, QTreeView)):
                view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        if not dialog.exec_():
            return
        added = 0
        existing = {p.resolve() for p in self._folder_paths}
        for path_str in dialog.selectedFiles():
            path = Path(path_str)
            if path.resolve() in existing:
                continue
            if path.is_dir():
                self._folder_paths.append(path)
                existing.add(path.resolve())
                added += 1
        if added:
            self._refresh_folder_list()
            self._reload_folders()

    def _remove_selected_folders(self):
        selected = self.folder_list.selectedItems()
        if not selected:
            return
        remove_paths = {Path(item.data(Qt.UserRole)).resolve() for item in selected}
        self._folder_paths = [p for p in self._folder_paths if p.resolve() not in remove_paths]
        self._refresh_folder_list()
        if self._folder_paths:
            self._reload_folders()
        else:
            self._clear_data()
            self.status.setText("All folders removed.")

    def _clear_data(self):
        self._all_jumps = []
        self._filtered = []
        self._curve_cache = {}
        self._device_registry = []
        self._yield_summary = None
        self.count_label.setText("Add device folders to begin.")
        self._fill_table()
        self._draw_empty_iv()
        self._plot_histogram([])
        self._plot_compare_empty()

    def _reload_folders(self):
        # Honour pending --sample path in folder_edit if list empty
        text = self.folder_edit.text().strip()
        if not self._folder_paths and text:
            p = Path(text)
            if p.is_dir():
                self._folder_paths = [p]
                self._refresh_folder_list()

        if not self._folder_paths:
            QMessageBox.information(self, "No folders", "Add one or more device folders first.")
            return

        self.status.setText(f"Loading {len(self._folder_paths)} folder(s)…")
        self.repaint()
        loaded = load_folders(self._folder_paths)
        self._all_jumps = loaded['jumps']
        self._curve_cache = loaded['curve_cache']
        self._device_registry = loaded.get('device_registry', [])
        self._jump_by_key = {jump_decision_key(j): j for j in self._all_jumps}

        # Prefer review JSON from first folder if decisions empty
        if not self._decisions and self._folder_paths:
            review = load_review_json(self._folder_paths[0])
            if review:
                self._decisions = apply_review_to_decisions(review)
                self._excluded_files_from_first = apply_review_excluded_files(review)
                if review.get('filter_state'):
                    self._apply_filter_state(review['filter_state'])

        n_dev = len(self._device_registry)
        n_class = sum(1 for d in self._device_registry if d.get('has_classification'))
        n_mem = sum(1 for d in self._device_registry if d.get('is_memristive'))
        self.status.setText(
            f"Loaded {len(self._all_jumps)} candidates from {n_dev} device(s) "
            f"in {len(self._folder_paths)} folder(s). "
            f"Classification: {n_class}/{n_dev} from thesis_llm_exports "
            f"({n_mem} worked memristive). "
            f"Save for Origin → {ORIGIN_DIR_NAME}/"
        )
        self._on_filters_changed()

    # ------------------------------------------------------------------ controls
    def _parse_min_current(self) -> Optional[float]:
        text = self.min_current_edit.text().strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    def _on_threshold_spin(self, value: float):
        if self._updating_controls:
            return
        self._updating_controls = True
        slider_val = int(round(value * 10))
        slider_val = max(self.threshold_slider.minimum(), min(self.threshold_slider.maximum(), slider_val))
        self.threshold_slider.setValue(slider_val)
        self._updating_controls = False
        self._on_filters_changed()

    def _on_threshold_slider(self, value: int):
        if self._updating_controls:
            return
        self._updating_controls = True
        self.threshold_spin.setValue(value / 10.0)
        self._updating_controls = False
        self._on_filters_changed()

    def _filter_kwargs(self) -> Dict[str, Any]:
        v_min = self.v_min_spin.value() if self.v_window_cb.isChecked() else None
        v_max = self.v_max_spin.value() if self.v_window_cb.isChecked() else None
        return dict(
            min_ratio=self.threshold_spin.value(),
            v_min=v_min,
            v_max=v_max,
            use_abs_v=self.abs_v_cb.isChecked(),
            min_current=self._parse_min_current(),
            upward_only=self.upward_only_cb.isChecked(),
            decisions=self._decisions,
        )

    def _on_filters_changed(self, *_args):
        if not self._folder_paths and not self._all_jumps:
            return
        prev_key = None
        if 0 <= self._selected_index < len(self._filtered):
            prev_key = jump_decision_key(self._filtered[self._selected_index])
        self._filtered = filter_jumps(self._all_jumps, **self._filter_kwargs()) if self._all_jumps else []
        accepted = sum(1 for j in self._filtered if j.get('included', True))
        rejected = len(self._filtered) - accepted
        self.count_label.setText(f"{accepted} jumps, {rejected} rejected")
        self._fill_table()
        self._plot_histogram([j for j in self._filtered if j.get('included', True)])
        self._update_compare()
        new_idx = 0 if self._filtered else -1
        if prev_key is not None:
            for i, j in enumerate(self._filtered):
                if jump_decision_key(j) == prev_key:
                    new_idx = i
                    break
        self._select_index(new_idx)

    def _apply_filter_state(self, state: Dict[str, Any]):
        self._updating_controls = True
        try:
            if 'min_ratio' in state:
                self.threshold_spin.setValue(float(state['min_ratio']))
                self.threshold_slider.setValue(int(round(float(state['min_ratio']) * 10)))
            if 'v_min' in state and state['v_min'] is not None:
                self.v_min_spin.setValue(float(state['v_min']))
            if 'v_max' in state and state['v_max'] is not None:
                self.v_max_spin.setValue(float(state['v_max']))
            if 'voltage_window' in state:
                self.v_window_cb.setChecked(bool(state['voltage_window']))
            if 'use_abs_v' in state:
                self.abs_v_cb.setChecked(bool(state['use_abs_v']))
            if 'upward_only' in state:
                self.upward_only_cb.setChecked(bool(state['upward_only']))
            if state.get('min_current') is not None:
                self.min_current_edit.setText(str(state['min_current']))
            else:
                self.min_current_edit.clear()
        finally:
            self._updating_controls = False

    def _current_filter_state(self) -> Dict[str, Any]:
        return {
            'min_ratio': self.threshold_spin.value(),
            'v_min': self.v_min_spin.value() if self.v_window_cb.isChecked() else None,
            'v_max': self.v_max_spin.value() if self.v_window_cb.isChecked() else None,
            'voltage_window': self.v_window_cb.isChecked(),
            'use_abs_v': self.abs_v_cb.isChecked(),
            'min_current': self._parse_min_current(),
            'upward_only': self.upward_only_cb.isChecked(),
        }

    # ------------------------------------------------------------------ session / origin
    def _prompt_save_name(self, title: str, default: str = "") -> Optional[str]:
        """Ask for a save name. Returns None if cancelled; empty string if left blank."""
        if not default:
            folders = [p.name for p in self._folder_paths[:3]]
            default = "_".join(folders) if folders else "filament_export"
        name, ok = QInputDialog.getText(
            self,
            title,
            "Name for this save:",
            text=default,
        )
        if not ok:
            return None
        return name.strip()

    def _save_session(self):
        if not self._folder_paths:
            QMessageBox.information(self, "No data", "Add folders first.")
            return
        name = self._prompt_save_name("Save Session — name", default="")
        if name is None:
            return
        clean = sanitize_export_name(name) or "filament_jump_session"
        default_path = f"{clean}.json"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Session", default_path, "JSON (*.json)"
        )
        if not path:
            return
        save_session(
            Path(path),
            self._folder_paths,
            decisions=self._decisions,
            filter_state=self._current_filter_state(),
            excluded_files_from_first=self._excluded_files_from_first,
            session_name=clean,
        )
        self.status.setText(f"Session \"{clean}\" saved to {path}")

    def _load_session(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Session", "", "JSON (*.json)"
        )
        if not path:
            return
        session = load_session(Path(path))
        if not session:
            QMessageBox.warning(self, "Invalid session", "Could not read that session file.")
            return
        folders = session_folder_paths(session)
        missing = [p for p in folders if not p.exists()]
        if missing:
            QMessageBox.warning(
                self,
                "Missing folders",
                "These folders no longer exist:\n" + "\n".join(str(p) for p in missing[:10]),
            )
        folders = [p for p in folders if p.exists()]
        if not folders:
            QMessageBox.warning(self, "No folders", "Session has no usable folder paths.")
            return
        self._folder_paths = folders
        self._decisions = apply_review_to_decisions(session)
        self._excluded_files_from_first = apply_review_excluded_files(session)
        if session.get('filter_state'):
            self._apply_filter_state(session['filter_state'])
        self._refresh_folder_list()
        self._reload_folders()
        label = session.get('session_name') or Path(path).stem
        self.status.setText(f"Session \"{label}\" loaded from {path}")

    def _save_origin(self):
        if not self._folder_paths:
            QMessageBox.information(self, "No data", "Add folders first.")
            return
        name = self._prompt_save_name("Save for Origin — name", default="")
        if name is None:
            return
        clean = sanitize_export_name(name)
        if not clean:
            QMessageBox.warning(self, "Name required", "Please enter a name for this Origin export.")
            return
        self._filtered = filter_jumps(self._all_jumps, **self._filter_kwargs()) if self._all_jumps else []
        out_root = origin_export_root(self._folder_paths)
        paths = export_origin_files(
            out_root,
            self._filtered,
            decisions=self._decisions,
            filter_state=self._current_filter_state(),
            excluded_files_from_first=self._excluded_files_from_first,
            folder_paths=self._folder_paths,
            device_registry=self._device_registry,
            export_name=clean,
        )
        out_dir = out_root / ORIGIN_DIR_NAME / clean
        self.status.setText(f"Saved \"{clean}\" ({len(paths)} files) to {out_dir}")
        QMessageBox.information(
            self,
            "Saved for Origin",
            f"Export name: {clean}\n\nWrote Origin-ready files to:\n{out_dir}",
        )

    # ------------------------------------------------------------------ table / selection
    def _fill_table(self):
        self.jump_table.blockSignals(True)
        self.jump_table.setRowCount(len(self._filtered))
        gray = QBrush(QColor(140, 140, 140))
        black = QBrush(QColor(0, 0, 0))
        for r, j in enumerate(self._filtered):
            included = j.get('included', True)
            status = "Jump" if included else "Rejected"
            vals = [
                status,
                str(j.get('source_folder', '')),
                str(j.get('section', '')),
                str(j.get('device_num', '')),
                str(j.get('filename', '')),
                f"{j.get('voltage', j.get('voltage_mid')):.6g}"
                if j.get('voltage', j.get('voltage_mid')) is not None else "—",
                f"{j.get('ratio', 0):.2f}",
            ]
            fg = black if included else gray
            for c, text in enumerate(vals):
                item = QTableWidgetItem(text)
                item.setForeground(fg)
                self.jump_table.setItem(r, c, item)
        self.jump_table.blockSignals(False)

    def _update_row_status(self, row: int):
        """Patch one table row's status/colour without rebuilding the whole table."""
        if not (0 <= row < len(self._filtered)):
            return
        j = self._filtered[row]
        included = j.get('included', True)
        status = "Jump" if included else "Rejected"
        fg = QBrush(QColor(0, 0, 0) if included else QColor(140, 140, 140))
        for c in range(7):
            item = self.jump_table.item(row, c)
            if item is None:
                item = QTableWidgetItem("")
                self.jump_table.setItem(row, c, item)
            if c == 0:
                item.setText(status)
            item.setForeground(fg)

    def _selected_row_indices(self) -> List[int]:
        rows = sorted({idx.row() for idx in self.jump_table.selectedIndexes() if idx.row() >= 0})
        rows = [r for r in rows if r < len(self._filtered)]
        if rows:
            return rows
        if 0 <= self._selected_index < len(self._filtered):
            return [self._selected_index]
        return []

    def _on_table_selection(self):
        rows = self._selected_row_indices()
        if not rows:
            return
        # IV preview follows the current (last-focused) row
        current = self.jump_table.currentRow()
        idx = current if current in rows else rows[-1]
        self._selected_index = idx
        j = self._filtered[idx]
        n_sel = len(rows)
        status = "Jump" if j.get('included', True) else "Rejected"
        extra = f"  ({n_sel} selected)" if n_sel > 1 else ""
        self.selection_label.setText(
            f"{status}: {j.get('source_folder')}/{j.get('section')}_{j.get('device_num')} / "
            f"{j.get('filename')} @ {j.get('voltage', 0):.4f} V (ratio {j.get('ratio', 0):.2f})"
            f"{extra}   [A=Jump  R=Reject  multi-select OK]"
        )
        self._draw_iv_for_jump(j)

    def _select_index(self, index: int, sync_table: bool = True):
        if not self._filtered:
            self._selected_index = -1
            self._draw_empty_iv()
            self.selection_label.setText("No jump selected.")
            return
        index = max(0, min(index, len(self._filtered) - 1))
        self._selected_index = index
        if sync_table:
            self.jump_table.blockSignals(True)
            self.jump_table.clearSelection()
            self.jump_table.selectRow(index)
            self.jump_table.blockSignals(False)
        j = self._filtered[index]
        status = "Jump" if j.get('included', True) else "Rejected"
        self.selection_label.setText(
            f"{status}: {j.get('source_folder')}/{j.get('section')}_{j.get('device_num')} / "
            f"{j.get('filename')} @ {j.get('voltage', 0):.4f} V (ratio {j.get('ratio', 0):.2f})"
            f"   [A=Jump  R=Reject  ←/→=Nav]"
        )
        self._draw_iv_for_jump(j)

    def _schedule_heavy_refresh(self):
        """Defer histogram + Compare redraws so rapid rejects stay responsive."""
        self._compare_dirty = True
        self._hist_refresh_timer.start()
        self._compare_refresh_timer.start()

    def _flush_hist_refresh(self):
        accepted = [x for x in self._filtered if x.get('included', True)]
        self._plot_histogram(accepted)

    def _flush_compare_refresh(self):
        if not self._compare_dirty:
            return
        self._compare_dirty = False
        self._update_compare()

    def _install_shortcuts(self):
        """A/Enter = accept, R/X/Delete = reject (all selected), arrows = prev/next."""
        pairs = [
            ("A", self._accept_jump),
            ("Return", self._accept_jump),
            ("Enter", self._accept_jump),
            ("R", self._reject_jump),
            ("X", self._reject_jump),
            ("Delete", self._reject_jump),
            ("Left", self._prev_jump),
            ("Up", self._prev_jump),
            ("Right", self._next_jump),
            ("Down", self._next_jump),
        ]
        for key, slot in pairs:
            sc = QShortcut(QKeySequence(key), self)
            sc.setContext(Qt.WindowShortcut)
            sc.activated.connect(slot)

    def _typing_in_field(self) -> bool:
        """Ignore shortcuts while editing text/spin boxes."""
        w = QApplication.focusWidget()
        return isinstance(w, (QLineEdit, QDoubleSpinBox))

    def _prev_jump(self):
        if self._typing_in_field() or not self._filtered:
            return
        idx = self._selected_index - 1 if self._selected_index > 0 else len(self._filtered) - 1
        self._select_index(idx)

    def _next_jump(self):
        if self._typing_in_field() or not self._filtered:
            return
        idx = self._selected_index + 1 if self._selected_index < len(self._filtered) - 1 else 0
        self._select_index(idx)

    def _accept_jump(self):
        if self._typing_in_field():
            return
        self._set_selected_included(True, advance=True)

    def _reject_jump(self):
        if self._typing_in_field():
            return
        self._set_selected_included(False, advance=True)

    def _set_selected_included(self, included: bool, advance: bool = False):
        rows = self._selected_row_indices()
        if not rows:
            return
        self.jump_table.blockSignals(True)
        last_j = None
        for row in rows:
            j = self._filtered[row]
            key = jump_decision_key(j)
            self._decisions[key] = included
            j['included'] = included
            master = self._jump_by_key.get(key)
            if master is not None:
                master['included'] = included
            else:
                # Fallback if key map stale (e.g. inspect-added jumps)
                for m in self._all_jumps:
                    if jump_decision_key(m) == key:
                        m['included'] = included
                        self._jump_by_key[key] = m
                        break
            self._update_row_status(row)
            last_j = j
        self.jump_table.blockSignals(False)

        accepted = sum(1 for x in self._filtered if x.get('included', True))
        rejected = len(self._filtered) - accepted
        self.count_label.setText(f"{accepted} jumps, {rejected} rejected")
        n = len(rows)
        status = "Jump" if included else "Rejected"
        if last_j is not None:
            self.selection_label.setText(
                f"{status} ×{n}: last {last_j.get('source_folder')}/"
                f"{last_j.get('section')}_{last_j.get('device_num')} / {last_j.get('filename')}"
                f"   [A=Jump  R=Reject]"
            )
            self._draw_iv_for_jump(last_j)

        self._schedule_heavy_refresh()

        if advance and self._filtered:
            next_idx = rows[-1] + 1
            if next_idx >= len(self._filtered):
                next_idx = 0
            # Skip still-selected block if we wrapped into it
            self._select_index(next_idx)

    # ------------------------------------------------------------------ IV plot
    def _draw_empty_iv(self):
        self.iv_fig.clear()
        ax = self.iv_fig.add_subplot(111)
        ax.text(0.5, 0.5, "Select a jump", ha='center', va='center')
        ax.set_xticks([])
        ax.set_yticks([])
        self.iv_fig.tight_layout()
        self.iv_canvas.draw_idle()
        self._marker_artists = []

    def _draw_iv_for_jump(self, selected: Dict[str, Any]):
        file_path = selected.get('file_path')
        if file_path is None:
            self._draw_empty_iv()
            return
        file_path = Path(file_path)
        cached = self._curve_cache.get(file_path)
        if cached is None:
            try:
                voltage, current, _ = DataLoader.load_raw_measurement(file_path)
            except Exception:
                self._draw_empty_iv()
                return
            voltage = np.asarray(voltage, dtype=float)
            current = np.asarray(current, dtype=float)
        else:
            voltage = np.asarray(cached['voltage'], dtype=float)
            current = np.asarray(cached['current'], dtype=float)

        self.iv_fig.clear()
        ax_lin = self.iv_fig.add_subplot(121)
        ax_log = self.iv_fig.add_subplot(122)
        ax_lin.plot(voltage, current, "o-", markersize=2, color='#1f77b4', alpha=0.8)
        ax_lin.set_xlabel("Voltage (V)")
        ax_lin.set_ylabel("Current (A)")
        ax_lin.set_title(file_path.name)
        ax_lin.grid(True, alpha=0.3)

        ax_log.plot(voltage, np.abs(current), "o-", markersize=2, color='#1f77b4', alpha=0.8)
        ax_log.set_yscale("log")
        ax_log.set_xlabel("Voltage (V)")
        ax_log.set_ylabel("|Current| (A)")
        ax_log.grid(True, which="both", alpha=0.3)

        self._marker_artists = []
        selected_key = jump_decision_key(selected)
        for idx, j in enumerate(self._filtered):
            if Path(j.get('file_path', '')) != file_path:
                continue
            v = j.get('voltage_mid', j.get('voltage'))
            if v is None:
                continue
            is_sel = jump_decision_key(j) == selected_key
            included = j.get('included', True)
            if is_sel:
                color, lw = '#ff9800', 2.5
            elif included:
                color, lw = '#4caf50', 1.5
            else:
                color, lw = '#9e9e9e', 1.0
            for ax in (ax_lin, ax_log):
                line = ax.axvline(v, color=color, alpha=0.85, linestyle='--', linewidth=lw)
                self._marker_artists.append((line, idx, float(v)))

        self.iv_fig.tight_layout()
        self.iv_canvas.draw_idle()

    def _on_iv_click(self, event):
        if event.inaxes is None or event.xdata is None or not self._marker_artists:
            return
        best_idx = None
        best_dist = None
        for _line, jump_idx, v in self._marker_artists:
            dist = abs(event.xdata - v)
            if best_dist is None or dist < best_dist:
                best_dist = dist
                best_idx = jump_idx
        if best_idx is None:
            return
        ax = event.inaxes
        xlim = ax.get_xlim()
        tol = 0.03 * abs(xlim[1] - xlim[0])
        if best_dist is not None and best_dist <= tol:
            if best_idx == self._selected_index:
                j = self._filtered[best_idx]
                self._set_selected_included(not j.get('included', True))
            else:
                self._select_index(best_idx)

    # ------------------------------------------------------------------ histogram
    def _plot_histogram(self, accepted: List[Dict]):
        self.hist_fig.clear()
        voltages = []
        for j in accepted:
            v = j.get('voltage', j.get('voltage_mid'))
            if v is not None:
                voltages.append(float(v))
        if not voltages:
            ax = self.hist_fig.add_subplot(111)
            ax.text(0.5, 0.5, "No accepted jumps", ha='center', va='center')
            self.hist_fig.tight_layout()
            self.hist_canvas.draw_idle()
            return

        centers_s, counts_s = histogram_bins(voltages, absolute=False)
        centers_a, counts_a = histogram_bins(voltages, absolute=True)
        bin_width = 0.2

        ax1 = self.hist_fig.add_subplot(211)
        if len(centers_s):
            ax1.bar(centers_s, counts_s, width=bin_width * 0.9, edgecolor='black', alpha=0.7)
        ax1.set_xlabel("Jump voltage (V)")
        ax1.set_ylabel("Count")
        ax1.set_title("Signed")
        ax1.grid(True, alpha=0.3)
        ax1.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.1f}"))

        ax2 = self.hist_fig.add_subplot(212)
        if len(centers_a):
            ax2.bar(centers_a, counts_a, width=bin_width * 0.9, edgecolor='black', alpha=0.7)
        ax2.set_xlabel("|Jump voltage| (V)")
        ax2.set_ylabel("Count")
        ax2.set_title("Absolute")
        ax2.grid(True, alpha=0.3)
        ax2.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.1f}"))
        self.hist_fig.tight_layout()
        self.hist_canvas.draw_idle()

    # ------------------------------------------------------------------ compare
    def _on_compare_tab_changed(self, *_args):
        """Ensure deferred Compare plots catch up when you open the tab."""
        if self._compare_dirty:
            self._compare_refresh_timer.stop()
            self._flush_compare_refresh()

    def _plot_compare_empty(self):
        for fig, canvas in (
            (self.yield_fig, self.yield_canvas),
            (self.ndr_fig, self.ndr_canvas),
            (self.mem_iv_fig, self.mem_iv_canvas),
            (self.best_pair_fig, self.best_pair_canvas),
        ):
            fig.clear()
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, "No devices loaded", ha='center', va='center')
            ax.set_xticks([])
            ax.set_yticks([])
            fig.tight_layout()
            canvas.draw_idle()
        self.compare_status.setText(
            "Load folders to see yield, NDR, and memristive IV overlays."
        )
        self.mem_iv_count_label.setText("")
        self._sync_compare_folder_combos([])

    def _sync_compare_folder_combos(self, folders: List[str]):
        """Refresh sample filter dropdowns without re-triggering full redraw loops."""
        for combo in (self.mem_iv_folder_combo, self.best_pair_folder_combo):
            combo.blockSignals(True)
            prev = combo.currentData()
            combo.clear()
            combo.addItem("All folders", None)
            for sf in folders:
                combo.addItem(sf, sf)
            # Default: first folder if multiple, else All / sole folder
            if len(folders) == 1:
                combo.setCurrentIndex(1)
            elif prev is not None:
                idx = combo.findData(prev)
                combo.setCurrentIndex(idx if idx >= 0 else (1 if folders else 0))
            elif folders:
                combo.setCurrentIndex(1)
            else:
                combo.setCurrentIndex(0)
            combo.blockSignals(False)

    def _on_mem_iv_folder_changed(self, *_args):
        if self._yield_summary:
            self._update_memristive_iv_tab(self._yield_summary)

    def _on_best_pair_folder_changed(self, *_args):
        if self._yield_summary:
            self._update_best_pair_tab(self._yield_summary)

    def _update_compare(self):
        if not self._device_registry:
            self._plot_compare_empty()
            return
        summary = compute_yield_summary(self._device_registry, self._filtered)
        self._yield_summary = summary
        combined = summary['combined']
        ndr = summary.get('ndr_stats') or {}
        unknown = combined.get('UnknownClass', 0)

        mem_ndr = ndr.get('memristive', {})
        mw = mem_ndr.get('with_jump', {})
        mn = mem_ndr.get('no_jump', {})

        def _fmt_mean(g):
            m = g.get('mean_ndr')
            return f"{m:.3f}" if m is not None else "—"

        self.compare_status.setText(
            f"All: {combined['WithJump']} with jump, {combined['NoJump']} without.  "
            f"Memristive (worked): {combined['MemWithJump']} with jump, "
            f"{combined['MemNoJump']} without.  "
            f"Mean NDR (mem): jump={_fmt_mean(mw)} vs no-jump={_fmt_mean(mn)} "
            f"(soft≥{NDR_SOFT_THRESHOLD}, strong≥{NDR_STRONG_THRESHOLD})"
            + (f"  ({unknown} missing classification)." if unknown else ".")
        )

        folders = sorted(summary['counts_by_folder'].keys())
        self._sync_compare_folder_combos(folders)
        self._update_yield_tab(summary)
        self._update_ndr_tab(summary)
        self._update_memristive_iv_tab(summary)
        self._update_best_pair_tab(summary)

    def _update_yield_tab(self, summary: Dict[str, Any]):
        folders = sorted(summary['counts_by_folder'].keys())
        labels = list(folders) + ['Combined']
        with_vals, without_vals, mem_with, mem_without = [], [], [], []
        for lab in labels:
            c = summary['combined'] if lab == 'Combined' else summary['counts_by_folder'][lab]
            with_vals.append(c.get('WithJump', 0))
            without_vals.append(c.get('NoJump', 0))
            mem_with.append(c.get('MemWithJump', 0))
            mem_without.append(c.get('MemNoJump', 0))

        self.yield_fig.clear()
        x = np.arange(len(labels))
        width = 0.35
        ax1 = self.yield_fig.add_subplot(211)
        ax1.bar(x - width / 2, with_vals, width, label='With jump', color='#4caf50', edgecolor='black')
        ax1.bar(x + width / 2, without_vals, width, label='No jump', color='#90a4ae', edgecolor='black')
        ax1.set_xticks(x)
        ax1.set_xticklabels(labels, rotation=15, ha='right')
        ax1.set_ylabel('Devices')
        ax1.set_title('All devices — With jump vs No jump')
        ax1.legend(loc='upper right')
        ax1.yaxis.set_major_locator(MaxNLocator(integer=True))
        ax1.grid(True, axis='y', alpha=0.3)

        ax2 = self.yield_fig.add_subplot(212)
        ax2.bar(x - width / 2, mem_with, width, label='Memristive + jump', color='#2e7d32', edgecolor='black')
        ax2.bar(x + width / 2, mem_without, width, label='Memristive + no jump', color='#b0bec5', edgecolor='black')
        ax2.set_xticks(x)
        ax2.set_xticklabels(labels, rotation=15, ha='right')
        ax2.set_ylabel('Devices')
        ax2.set_title('Worked memristive — With jump vs No jump')
        ax2.legend(loc='upper right')
        ax2.yaxis.set_major_locator(MaxNLocator(integer=True))
        ax2.grid(True, axis='y', alpha=0.3)
        self.yield_fig.tight_layout()
        self.yield_canvas.draw_idle()

    def _update_ndr_tab(self, summary: Dict[str, Any]):
        ndr = summary.get('ndr_stats') or {}
        folders = sorted(summary['counts_by_folder'].keys())
        labels = list(folders) + ['Combined']
        self.ndr_fig.clear()
        gs = self.ndr_fig.add_gridspec(2, 2, hspace=0.4, wspace=0.3)
        self._plot_ndr_means(
            self.ndr_fig, gs[0, 0], ndr.get('all', {}), labels, summary,
            title='Mean NDR — all devices', mem_only=False,
        )
        self._plot_ndr_means(
            self.ndr_fig, gs[0, 1], ndr.get('memristive', {}), labels, summary,
            title='Mean NDR — memristive', mem_only=True,
        )
        self._plot_ndr_soft_strong(self.ndr_fig, gs[1, :], labels, ndr)
        self.ndr_fig.tight_layout()
        self.ndr_canvas.draw_idle()

    def _update_memristive_iv_tab(self, summary: Dict[str, Any]):
        folder = self.mem_iv_folder_combo.currentData()
        rows = summary.get('device_rows') or []
        with_j, no_j = memristive_devices_by_jump(rows, source_folder=folder)
        scope = folder or "All folders"
        self.mem_iv_count_label.setText(
            f"{scope}: {len(with_j)} with jump, {len(no_j)} without"
        )

        self.mem_iv_fig.clear()
        ax_lin_w = self.mem_iv_fig.add_subplot(221)
        ax_log_w = self.mem_iv_fig.add_subplot(222)
        ax_lin_n = self.mem_iv_fig.add_subplot(223)
        ax_log_n = self.mem_iv_fig.add_subplot(224)

        self._plot_memristive_group_overlay(
            ax_lin_w, ax_log_w, with_j,
            title_lin=f"Memristive WITH jump — IV (n={len(with_j)})",
            title_log=f"Memristive WITH jump — log |I| (n={len(with_j)})",
            color='#2e7d32',
        )
        self._plot_memristive_group_overlay(
            ax_lin_n, ax_log_n, no_j,
            title_lin=f"Memristive NO jump — IV (n={len(no_j)})",
            title_log=f"Memristive NO jump — log |I| (n={len(no_j)})",
            color='#c62828',
        )
        self.mem_iv_fig.tight_layout()
        self.mem_iv_canvas.draw_idle()

    def _plot_memristive_group_overlay(
        self, ax_lin, ax_log, device_rows: List[Dict], *,
        title_lin: str, title_log: str, color: str,
    ):
        ax_lin.set_title(title_lin, fontsize=10)
        ax_log.set_title(title_log, fontsize=10)
        plotted = 0
        max_legend = 12
        n = max(len(device_rows), 1)
        alpha = max(0.35, min(0.75, 1.2 / np.sqrt(n)))
        for row in device_rows:
            resolved = resolve_device_iv_curve(row, self._curve_cache)
            if resolved is None:
                continue
            v, i, _label = resolved
            name = f"{row.get('section')}_{row.get('device_num')}"
            show_label = plotted < max_legend
            ax_lin.plot(
                v, i, '-', color=color, alpha=alpha, linewidth=1.0,
                label=name if show_label else None,
            )
            ax_log.plot(
                v, np.abs(i), '-', color=color, alpha=alpha, linewidth=1.0,
                label=name if show_label else None,
            )
            plotted += 1
        if plotted > max_legend:
            extra = f"+{plotted - max_legend} more"
            ax_lin.plot([], [], ' ', label=extra)
            ax_log.plot([], [], ' ', label=extra)
        ax_lin.set_xlabel('Voltage (V)')
        ax_lin.set_ylabel('Current (A)')
        ax_lin.grid(True, alpha=0.3)
        ax_log.set_xlabel('Voltage (V)')
        ax_log.set_ylabel('|Current| (A)')
        ax_log.set_yscale('log')
        ax_log.grid(True, which='both', alpha=0.3)
        if plotted:
            ax_lin.legend(loc='best', fontsize=6, ncol=2)
            ax_log.legend(loc='best', fontsize=6, ncol=2)
        else:
            ax_lin.text(0.5, 0.5, 'No devices / IV not found', ha='center', va='center',
                        transform=ax_lin.transAxes)
            ax_log.text(0.5, 0.5, '—', ha='center', va='center', transform=ax_log.transAxes)

    def _update_best_pair_tab(self, summary: Dict[str, Any]):
        folder = self.best_pair_folder_combo.currentData()
        pairs = summary.get('best_memristive_pairs') or {}
        folders = sorted(pairs.keys()) if folder is None else [folder]

        self.best_pair_fig.clear()
        n = max(len(folders), 1)
        for i, sf in enumerate(folders):
            ax_lin = self.best_pair_fig.add_subplot(n, 2, 2 * i + 1)
            ax_log = self.best_pair_fig.add_subplot(n, 2, 2 * i + 2)
            pair = pairs.get(sf) or {}
            self._plot_best_iv_overlay(ax_lin, ax_log, sf, pair)
        if not folders:
            ax = self.best_pair_fig.add_subplot(111)
            ax.text(0.5, 0.5, "No folder selected", ha='center', va='center')
        self.best_pair_fig.tight_layout()
        self.best_pair_canvas.draw_idle()

    def _plot_ndr_means(self, fig, subplot_spec, group, labels, summary, title, mem_only=False):
        ax = fig.add_subplot(subplot_spec)
        means_w, means_n = [], []
        for lab in labels:
            if lab == 'Combined':
                g = group
            else:
                folder_ndr = (summary.get('ndr_stats') or {}).get('by_folder', {}).get(lab, {})
                g = folder_ndr.get('memristive' if mem_only else 'all', {})
            mw = (g.get('with_jump') or {}).get('mean_ndr')
            mn = (g.get('no_jump') or {}).get('mean_ndr')
            means_w.append(mw if mw is not None else 0.0)
            means_n.append(mn if mn is not None else 0.0)
        x = np.arange(len(labels))
        width = 0.35
        ax.bar(x - width / 2, means_w, width, label='With jump', color='#ef6c00', edgecolor='black')
        ax.bar(x + width / 2, means_n, width, label='No jump', color='#ffcc80', edgecolor='black')
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=15, ha='right')
        ax.set_ylabel('Mean ndr_index_max')
        ax.set_title(title)
        ax.legend(loc='upper right', fontsize=8)
        ax.grid(True, axis='y', alpha=0.3)

    def _plot_ndr_soft_strong(self, fig, subplot_spec, labels, ndr):
        ax = fig.add_subplot(subplot_spec)
        soft_w, soft_n, strong_w, strong_n = [], [], [], []
        for lab in labels:
            if lab == 'Combined':
                g = ndr.get('memristive', {})
            else:
                g = (ndr.get('by_folder') or {}).get(lab, {}).get('memristive', {})
            w = g.get('with_jump') or {}
            n = g.get('no_jump') or {}
            soft_w.append(w.get('n_soft_ndr', 0))
            soft_n.append(n.get('n_soft_ndr', 0))
            strong_w.append(w.get('n_strong_ndr', 0))
            strong_n.append(n.get('n_strong_ndr', 0))
        x = np.arange(len(labels))
        w = 0.2
        ax.bar(x - 1.5 * w, soft_w, w, label=f'Soft NDR + jump (≥{NDR_SOFT_THRESHOLD})', color='#6a1b9a', edgecolor='black')
        ax.bar(x - 0.5 * w, soft_n, w, label='Soft NDR + no jump', color='#ce93d8', edgecolor='black')
        ax.bar(x + 0.5 * w, strong_w, w, label=f'Strong NDR + jump (≥{NDR_STRONG_THRESHOLD})', color='#ad1457', edgecolor='black')
        ax.bar(x + 1.5 * w, strong_n, w, label='Strong NDR + no jump', color='#f48fb1', edgecolor='black')
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=15, ha='right')
        ax.set_ylabel('Devices')
        ax.set_title('Memristive devices — soft / strong NDR counts vs jump')
        ax.legend(loc='upper right', fontsize=7, ncol=2)
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        ax.grid(True, axis='y', alpha=0.3)

    def _plot_best_iv_overlay(self, ax_lin, ax_log, source_folder: str, pair: Dict):
        ax_lin.set_title(f"{source_folder}: best memristive IV (with vs without jump)")
        ax_log.set_title(f"{source_folder}: |I| log")
        plotted = False
        styles = [
            ('with_jump', '#2e7d32', 'With jump'),
            ('no_jump', '#c62828', 'No jump'),
        ]
        for key, color, legend in styles:
            row = pair.get(key)
            if not row:
                continue
            resolved = resolve_device_iv_curve(row, self._curve_cache)
            if resolved is None:
                continue
            v, i, _label = resolved
            ndr = row.get('ndr_index_max')
            ndr_s = f", NDR={ndr:.3f}" if ndr is not None else ""
            full = f"{legend}: {row.get('section')}_{row.get('device_num')}{ndr_s}"
            ax_lin.plot(v, i, '-', color=color, alpha=0.85, linewidth=1.2, label=full)
            ax_log.plot(v, np.abs(i), '-', color=color, alpha=0.85, linewidth=1.2, label=full)
            plotted = True
        ax_lin.set_xlabel('Voltage (V)')
        ax_lin.set_ylabel('Current (A)')
        ax_lin.grid(True, alpha=0.3)
        ax_log.set_xlabel('Voltage (V)')
        ax_log.set_ylabel('|Current| (A)')
        ax_log.set_yscale('log')
        ax_log.grid(True, which='both', alpha=0.3)
        if plotted:
            ax_lin.legend(loc='best', fontsize=7)
            ax_log.legend(loc='best', fontsize=7)
        else:
            ax_lin.text(0.5, 0.5, 'No memristive pair / IV not found', ha='center', va='center',
                        transform=ax_lin.transAxes)
            ax_log.text(0.5, 0.5, '—', ha='center', va='center', transform=ax_log.transAxes)

    # ------------------------------------------------------------------ inspect
    def _inspect_selected(self):
        if not (0 <= self._selected_index < len(self._filtered)):
            QMessageBox.information(self, "Select jump", "Select a jump in the table first.")
            return
        j = self._filtered[self._selected_index]
        file_path = j.get('file_path')
        if not file_path:
            QMessageBox.warning(self, "No file", "This row has no file path.")
            return
        file_path = Path(file_path)
        jumps_for_file = [x for x in self._all_jumps if Path(x.get('file_path', '')) == file_path]
        display = []
        for x in jumps_for_file:
            row = dict(x)
            key = jump_decision_key(x)
            if key in self._decisions:
                row['included'] = self._decisions[key]
            display.append(row)
        section = j.get('section', '')
        device_num = j.get('device_num', 0)
        sf = j.get('source_folder', '')
        file_key_4 = (sf, section, device_num, file_path.name)
        file_key_3 = (section, device_num, file_path.name)
        exclude_from_first = (
            file_key_4 in self._excluded_files_from_first
            or file_key_3 in self._excluded_files_from_first
        )
        dlg = InspectJumpsDialog(
            file_path,
            display,
            section=section,
            device_num=device_num,
            main_threshold=self.threshold_spin.value(),
            min_current=self._parse_min_current(),
            upward_only=self.upward_only_cb.isChecked(),
            exclude_from_first=exclude_from_first,
            curve_cache=self._curve_cache,
            parent=self,
        )
        dlg.inclusion_changed.connect(self._on_inspect_inclusion)
        dlg.jumps_to_add.connect(self._on_jumps_to_add)
        dlg.file_excluded_from_first_changed.connect(
            lambda s, d, f, excl, source=sf: self._on_file_excluded_from_first(source, s, d, f, excl)
        )
        self._inspect_display = display
        dlg.exec_()

    def _on_inspect_inclusion(self):
        display = getattr(self, '_inspect_display', [])
        for j in display:
            key = jump_decision_key(j)
            self._decisions[key] = bool(j.get('included', True))
            for master in self._all_jumps:
                if jump_decision_key(master) == key:
                    master['included'] = self._decisions[key]
                    break
        self._on_filters_changed()

    def _on_jumps_to_add(self, new_jumps: list):
        for j in new_jumps:
            if 'source_folder' not in j and self._folder_paths:
                j['source_folder'] = self._folder_paths[0].name
            self._all_jumps.append(j)
            key = jump_decision_key(j)
            self._decisions[key] = True
            self._jump_by_key[key] = j
        self._on_filters_changed()

    def _on_file_excluded_from_first(
        self, source_folder: str, section: str, device_num: int, filename: str, excluded: bool
    ):
        key = (source_folder, section, device_num, filename)
        if excluded:
            self._excluded_files_from_first.add(key)
        else:
            self._excluded_files_from_first.discard(key)
