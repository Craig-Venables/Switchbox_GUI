"""
Device variation viewer.

Device tab: every included sweep of one device, split at the first accepted jump.
Sample tab: the real sweeps you pick, one curve per sweep.
Compare tab: median and interquartile band for each loaded sample.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from matplotlib import colormaps
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QTextEdit,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
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
    QTabWidget,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from .core import (
    NORM_LABELS,
    NORM_LOG,
    NORM_MAX,
    NORM_RAW,
    NORM_READ,
    add_folders_to_model,
    classify_device,
    iter_devices,
    load_folder_paths,
    load_jump_session,
    load_view_state,
    normalize_current,
    negative_side,
    positive_side,
    read_current,
    split_loops,
    export_measurement_loops,
    remove_folders_from_model,
    save_view_state,
    split_lookup_key,
    summarize_compare,
    summarize_sample,
    export_origin_bundle,
    y_axis_label,
)

DeviceKey = Tuple[str, str, int]


_HELP_TEXT = """\
Forming, pre, post, and unformed

The split comes from the jump-finder session you load. This tool does not invent a new jump threshold.

The forming file is the earliest sweep that still has a jump you left accepted. Sweeps before that file are pre. That file and every later sweep are post. A device with no accepted jump is unformed, so it has no post curve. A jump you marked Rejected does not set the forming file. A candidate you never marked still counts, which is the same rule as the jump finder.

Sample tab, with All devices

Pre draws only formed devices, using the Pre sweep menu. The default is the last sweep before the forming file.
Post draws those same formed devices, using the Post sweep menu. The default is the forming sweep. First after forming skips that file. Last sweep is the end of the run.
Unformed is its own panel. Those devices have no forming file, so the Post sweep menu does not apply to them. The Pre sweep menu picks which of their sweeps to show. They stay off the pre and post panels.

Each line is one real IV loop for one device. Uncheck a device to leave it off the plot. Pick one device in the Device menu to see its checked sweeps, and click a file to highlight that curve.

Positive trend and Negative trend, on the Sample tab, use one measurement file. Min loops (default 20) is how many repeated cycles that file must contain, not how many files are in the folder. Each line is one voltage side of one loop, scaled by that side's own maximum current. Early loops are blue and later loops are red. Click the file first. Save loops writes twelve Origin files for that measurement: the full loop, the positive side only, and the negative side only, each as voltage against absolute current and voltage against current, raw and normalised. Sweep numbers start at 1.

Normalisation and raw current

The Normalization menu applies to every tab. Divide by max |I| compares shape, so a high-current device does not hide the rest. Raw current keeps the amperes, so you can see how large the currents are.

Also show raw current on the Sample tab keeps the shape plot and adds a second row of the same sweeps in amperes. Use the top row when the claim is about loop shape, and the bottom row when the claim is about how much current the devices pass.

Using the figures

The formed / unformed count is the forming yield of the sample under the jumps you already accepted.
All devices, with the same Pre and Post choice, is device-to-device variation at one matched point in the run.
The Device tab Lifetime plot is one device from its early sweeps through forming and later sweeps.
Memristive only keeps devices already marked worked-memristive. Leave it off when the figure is the whole film, including devices that never formed.
Compare is for two samples, such as 2% and 3%. The Figure menu chooses Medians (sample bands plus one device), Yield (formed, unformed, and memristive counts for every device), Read current (|I| at the read voltage on the sweep chosen in the Sample tab), or Sweep overlay (those real sweeps, one colour per sample). Unchecked devices stay off the read-current and overlay figures. Yield still counts them.
Save for Origin writes one voltage and current pair per sweep, plus an index that names the files. Save session keeps the unchecked files, unchecked devices, and the Pre/Post choice so the same figure can be redrawn.
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Device variation viewer")
        self.resize(1280, 860)

        self.model: Optional[Dict[str, Any]] = None
        self.excluded_keys: set = set()
        self.hidden_device_keys: set = set()
        self.split_before: Dict[str, str] = {}
        self.sample_labels: Dict[str, str] = {}
        self.compare_device_keys: Dict[str, DeviceKey] = {}
        self._selected_device: Optional[DeviceKey] = None
        self._highlight_path: Optional[str] = None
        self._loop_sweep: Optional[Dict[str, Any]] = None
        self._filling = False
        self._heavy_timer = QTimer(self)
        self._heavy_timer.setSingleShot(True)
        self._heavy_timer.timeout.connect(self._refresh_heavy_tabs)

        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        bar = QHBoxLayout()
        self.btn_session = QPushButton("Load jump session…")
        self.btn_add = QPushButton("Add folders…")
        self.btn_remove = QPushButton("Remove selected")
        self.btn_save_view = QPushButton("Save session…")
        self.btn_load_view = QPushButton("Load session…")
        self.btn_origin = QPushButton("Save for Origin…")
        self.btn_save_loops = QPushButton("Save loops…")
        self.btn_save_loops.setToolTip(
            "Twelve Origin files for the clicked measurement: full loop, positive side, and negative side, "
            "each as voltage against current and absolute current, raw and normalised. Sweep numbers start at 1."
        )
        self.btn_help = QPushButton("?")
        self.btn_help.setFixedWidth(32)
        self.btn_help.setToolTip("How pre, post, unformed, and normalisation work")
        for button in (
            self.btn_session, self.btn_add, self.btn_remove,
            self.btn_save_view, self.btn_load_view, self.btn_origin, self.btn_save_loops, self.btn_help,
        ):
            bar.addWidget(button)
        bar.addStretch(1)
        layout.addLayout(bar)

        norm_row = QHBoxLayout()
        norm_row.addWidget(QLabel("Normalization"))
        self.norm_combo = QComboBox()
        for key, label in NORM_LABELS.items():
            self.norm_combo.addItem(label, key)
        self.norm_combo.setCurrentIndex(0)  # max |I|
        norm_row.addWidget(self.norm_combo)
        norm_row.addWidget(QLabel("Read voltage (V)"))
        self.read_v_spin = QDoubleSpinBox()
        self.read_v_spin.setRange(-20.0, 20.0)
        self.read_v_spin.setDecimals(2)
        self.read_v_spin.setSingleStep(0.1)
        self.read_v_spin.setValue(0.5)
        self.read_v_spin.setEnabled(False)
        norm_row.addWidget(self.read_v_spin)
        self.log_check = QCheckBox("Log |y| on device plots")
        norm_row.addWidget(self.log_check)
        self.memristive_only = QCheckBox("Memristive only")
        self.memristive_only.setToolTip(
            "Only devices marked worked-memristive in the thesis classification. "
            "Device lists stay sorted by memristivity score either way."
        )
        norm_row.addWidget(self.memristive_only)
        norm_row.addStretch(1)
        layout.addLayout(norm_row)

        self.status = QLabel("Load a filament jump finder session to mark pre and post.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        splitter = QSplitter(Qt.Horizontal)
        self.folder_list = QListWidget()
        self.folder_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.folder_list.setMinimumWidth(220)
        splitter.addWidget(self.folder_list)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_device_tab(), "Device")
        self.tabs.addTab(self._build_sample_tab(), "Sample")
        self.tabs.addTab(self._build_compare_tab(), "Compare")
        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

        self.btn_session.clicked.connect(self._load_session)
        self.btn_add.clicked.connect(self._add_folders)
        self.btn_remove.clicked.connect(self._remove_folders)
        self.btn_save_view.clicked.connect(self._save_view)
        self.btn_load_view.clicked.connect(self._load_view)
        self.btn_origin.clicked.connect(self._save_origin)
        self.btn_help.clicked.connect(self._show_help)
        self.norm_combo.currentIndexChanged.connect(self._on_norm_changed)
        self.read_v_spin.valueChanged.connect(lambda *_: self._refresh_views())
        self.log_check.toggled.connect(lambda *_: self._refresh_device_tab())
        self.memristive_only.toggled.connect(self._on_memristive_filter)

    def _build_device_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        side = QVBoxLayout()
        side.addWidget(QLabel("Sample"))
        self.device_sample_combo = QComboBox()
        side.addWidget(self.device_sample_combo)
        side.addWidget(QLabel("Device"))
        self.device_combo = QComboBox()
        side.addWidget(self.device_combo)
        side.addWidget(QLabel("Plot"))
        self.device_view_combo = QComboBox()
        self.device_view_combo.addItem("Lifetime (all sweeps)", "lifetime")
        self.device_view_combo.addItem("Pre / post", "split")
        side.addWidget(self.device_view_combo)
        side.addWidget(QLabel("Split before file"))
        self.split_combo = QComboBox()
        side.addWidget(self.split_combo)
        side.addWidget(QLabel("Files (click to highlight, uncheck to drop)"))
        self.file_list = QListWidget()
        side.addWidget(self.file_list, 1)
        file_btns = QHBoxLayout()
        self.btn_check_all = QPushButton("All")
        self.btn_uncheck_all = QPushButton("None")
        file_btns.addWidget(self.btn_check_all)
        file_btns.addWidget(self.btn_uncheck_all)
        side.addLayout(file_btns)
        self.device_info = QLabel("No device selected.")
        self.device_info.setWordWrap(True)
        side.addWidget(self.device_info)
        side_wrap = QWidget()
        side_wrap.setLayout(side)
        side_wrap.setMinimumWidth(280)
        layout.addWidget(side_wrap)

        plot_col = QVBoxLayout()
        self.device_fig = Figure(figsize=(8, 6))
        self.device_canvas = FigureCanvasQTAgg(self.device_fig)
        self.device_toolbar = NavigationToolbar2QT(self.device_canvas, page)
        plot_col.addWidget(self.device_toolbar)
        plot_col.addWidget(self.device_canvas, 1)
        plot_wrap = QWidget()
        plot_wrap.setLayout(plot_col)
        layout.addWidget(plot_wrap, 1)

        self.device_sample_combo.currentIndexChanged.connect(self._on_device_sample_changed)
        self.device_combo.currentIndexChanged.connect(self._on_device_changed)
        self.device_view_combo.currentIndexChanged.connect(lambda *_: self._refresh_device_tab())
        self.split_combo.currentIndexChanged.connect(self._on_split_changed)
        self.file_list.itemChanged.connect(self._on_file_toggled)
        self.file_list.itemClicked.connect(self._on_file_clicked)
        self.btn_check_all.clicked.connect(lambda: self._set_all_files(True))
        self.btn_uncheck_all.clicked.connect(lambda: self._set_all_files(False))
        return page

    def _build_sample_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        row = QHBoxLayout()
        row.addWidget(QLabel("Sample"))
        self.sample_combo = QComboBox()
        row.addWidget(self.sample_combo, 1)
        row.addWidget(QLabel("Device"))
        self.sample_device_combo = QComboBox()
        self.sample_device_combo.addItem("All devices", None)
        row.addWidget(self.sample_device_combo, 1)
        row.addWidget(QLabel("Pre sweep"))
        self.sample_pre_combo = QComboBox()
        self.sample_pre_combo.addItem("Last before forming", "last")
        self.sample_pre_combo.addItem("First sweep", "first")
        self.sample_pre_combo.addItem("All pre sweeps", "all")
        self.sample_pre_combo.addItem("Hide pre", "none")
        row.addWidget(self.sample_pre_combo)
        row.addWidget(QLabel("Post sweep"))
        self.sample_post_combo = QComboBox()
        self.sample_post_combo.addItem("Forming sweep", "forming")
        self.sample_post_combo.addItem("First after forming", "after_forming")
        self.sample_post_combo.addItem("Last sweep", "last")
        self.sample_post_combo.addItem("All post sweeps", "all")
        self.sample_post_combo.addItem("Hide post", "none")
        row.addWidget(self.sample_post_combo)
        row.addWidget(QLabel("Plot"))
        self.sample_plot_combo = QComboBox()
        self.sample_plot_combo.addItem("Pre / post", "split")
        self.sample_plot_combo.addItem("Positive trend", "positive")
        self.sample_plot_combo.addItem("Negative trend", "negative")
        row.addWidget(self.sample_plot_combo)
        row.addWidget(QLabel("Min loops"))
        self.min_sweeps_spin = QSpinBox()
        self.min_sweeps_spin.setRange(1, 5000)
        self.min_sweeps_spin.setValue(20)
        self.min_sweeps_spin.setToolTip(
            "Positive trend and Negative trend draw a measurement only when that file contains at least this many loops."
        )
        row.addWidget(self.min_sweeps_spin)
        self.sample_raw_check = QCheckBox("Also show raw current")
        self.sample_raw_check.setToolTip(
            "Adds a second row of the same sweeps in amperes, so devices can differ in size as well as shape."
        )
        row.addWidget(self.sample_raw_check)
        self.sample_info = QLabel("")
        self.sample_info.setWordWrap(True)
        row.addWidget(self.sample_info, 2)
        layout.addLayout(row)

        self.sample_fig = Figure(figsize=(10, 7))
        self.sample_canvas = FigureCanvasQTAgg(self.sample_fig)
        self.sample_toolbar = NavigationToolbar2QT(self.sample_canvas, page)
        plot_col = QVBoxLayout()
        plot_col.addWidget(self.sample_toolbar)
        plot_col.addWidget(self.sample_canvas, 1)
        plot_wrap = QWidget()
        plot_wrap.setLayout(plot_col)

        device_col = QVBoxLayout()
        device_head = QHBoxLayout()
        device_head.addWidget(QLabel("Devices"))
        self.btn_devices_all = QPushButton("All")
        self.btn_devices_none = QPushButton("None")
        device_head.addWidget(self.btn_devices_all)
        device_head.addWidget(self.btn_devices_none)
        device_col.addLayout(device_head)
        self.sample_device_list = QListWidget()
        device_col.addWidget(self.sample_device_list, 1)
        device_wrap = QWidget()
        device_wrap.setLayout(device_col)

        file_col = QVBoxLayout()
        file_col.addWidget(QLabel("Sweeps (selected device)"))
        self.sample_file_list = QListWidget()
        file_col.addWidget(self.sample_file_list, 1)
        file_wrap = QWidget()
        file_wrap.setLayout(file_col)

        side = QSplitter(Qt.Vertical)
        side.addWidget(device_wrap)
        side.addWidget(file_wrap)
        side.setMinimumWidth(280)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(side)
        splitter.addWidget(plot_wrap)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 3)

        self.distance_table = QTableWidget(0, 4)
        self.distance_table.setHorizontalHeaderLabels([
            "Device", "Status", "Pre sweep", "Post sweep",
        ])
        self.distance_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.distance_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.distance_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.distance_table.setMinimumHeight(160)
        layout.addWidget(self.distance_table, 1)

        self.sample_combo.currentIndexChanged.connect(lambda *_: self._refresh_sample_tab())
        self.sample_device_combo.currentIndexChanged.connect(self._on_sample_device_changed)
        self.sample_pre_combo.currentIndexChanged.connect(lambda *_: self._refresh_sample_and_compare())
        self.sample_post_combo.currentIndexChanged.connect(lambda *_: self._refresh_sample_and_compare())
        self.sample_plot_combo.currentIndexChanged.connect(lambda *_: self._refresh_sample_tab())
        self.min_sweeps_spin.valueChanged.connect(lambda *_: self._refresh_sample_tab())
        self.btn_save_loops.clicked.connect(self._save_loops)
        self.sample_raw_check.toggled.connect(lambda *_: self._refresh_sample_tab())
        self.sample_device_list.itemChanged.connect(self._on_sample_device_toggled)
        self.btn_devices_all.clicked.connect(lambda: self._set_sample_devices(True))
        self.btn_devices_none.clicked.connect(lambda: self._set_sample_devices(False))
        self.sample_file_list.itemClicked.connect(self._on_file_clicked)
        self.sample_file_list.itemChanged.connect(self._on_file_toggled)
        self.distance_table.itemSelectionChanged.connect(self._on_distance_selected)
        self.distance_table.itemDoubleClicked.connect(self._on_distance_double_clicked)
        return page

    def _build_compare_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        figure_row = QHBoxLayout()
        figure_row.addWidget(QLabel("Figure"))
        self.compare_figure_combo = QComboBox()
        self.compare_figure_combo.addItem("Medians", "medians")
        self.compare_figure_combo.addItem("Yield", "yield")
        self.compare_figure_combo.addItem("Read current", "read_current")
        self.compare_figure_combo.addItem("Sweep overlay", "overlay")
        figure_row.addWidget(self.compare_figure_combo)
        figure_row.addStretch(1)
        layout.addLayout(figure_row)
        layout.addWidget(QLabel(
            "Medians keeps one device lifetime under the sample bands. "
            "Yield counts every device. Read current and Sweep overlay use the Sample tab's "
            "Pre and Post menus, and leave unchecked devices off the figure. "
            "Edit the label (the folder name is the default, so you can type 2% and 3%)."
        ))
        self.label_table = QTableWidget(0, 3)
        self.label_table.setHorizontalHeaderLabels(["Folder", "Label", "Device"])
        self.label_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.label_table.setMaximumHeight(180)
        layout.addWidget(self.label_table)
        self.compare_info = QLabel("")
        self.compare_info.setWordWrap(True)
        layout.addWidget(self.compare_info)
        self.compare_fig = Figure(figsize=(10, 8))
        self.compare_canvas = FigureCanvasQTAgg(self.compare_fig)
        self.compare_toolbar = NavigationToolbar2QT(self.compare_canvas, page)
        layout.addWidget(self.compare_toolbar)
        layout.addWidget(self.compare_canvas, 1)
        self.label_table.itemChanged.connect(self._on_label_edited)
        self.compare_figure_combo.currentIndexChanged.connect(lambda *_: self._refresh_compare_tab())
        return page

    # ------------------------------------------------------------------ loading
    def load_session_path(self, path: str):
        self._open_session(Path(path))

    def _load_session(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load jump session", "", "JSON (*.json)")
        if path:
            self._open_session(Path(path))

    def _open_session(self, path: Path):
        self.status.setText(f"Loading session {path.name}…")
        self.repaint()
        try:
            model = load_jump_session(path)
        except Exception as exc:
            QMessageBox.warning(self, "Could not load session", str(exc))
            self.status.setText("Session load failed.")
            return
        self.model = model
        missing = model.get("missing_folders") or []
        if missing:
            QMessageBox.warning(
                self,
                "Missing folders",
                "These folders no longer exist:\n" + "\n".join(str(p) for p in missing[:12]),
            )
        self._selected_device = None
        self._fill_folder_list()
        self._fill_sample_combos()
        self._refresh_views()
        name = model.get("session_name") or path.stem
        self.status.setText(
            f"Session \"{name}\": {model.get('n_accepted', 0)} accepted jumps, "
            f"{model.get('n_rejected', 0)} rejected, "
            f"{len(model.get('folders') or [])} folder(s)."
        )

    def _add_folders(self):
        dialog = QFileDialog(self, "Add sample folders")
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setOption(QFileDialog.ShowDirsOnly, True)
        dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        for view in dialog.findChildren(QListView) + dialog.findChildren(QTreeView):
            if isinstance(view, (QListView, QTreeView)):
                view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        if not dialog.exec_():
            return
        paths = [Path(p) for p in dialog.selectedFiles()]
        if not paths:
            return
        self.status.setText("Loading folders…")
        self.repaint()
        try:
            if self.model is None:
                self.model = load_folder_paths(paths)
            else:
                add_folders_to_model(self.model, paths)
        except Exception as exc:
            QMessageBox.warning(self, "Could not load folders", str(exc))
            return
        self._fill_folder_list()
        self._fill_sample_combos()
        self._refresh_views()
        if self.model.get("has_session"):
            self.status.setText(
                "Folders added. New folders stay unsplit until they are part of a jump session. "
                f"{self.model.get('n_accepted', 0)} accepted jumps from the loaded session."
            )
        else:
            self.status.setText(
                "Curves loaded. Load a jump session to mark pre and post. "
                "Nothing is labelled from an automatic threshold."
            )

    def _remove_folders(self):
        if not self.model:
            return
        selected = self.folder_list.selectedItems()
        if not selected:
            return
        paths = [Path(item.data(Qt.UserRole)) for item in selected]
        remove_folders_from_model(self.model, paths)
        self._selected_device = None
        self._fill_folder_list()
        self._fill_sample_combos()
        if not self.model.get("folders"):
            self.model = None
            self._refresh_views()
            self.status.setText("All folders removed.")
            return
        self._refresh_views()
        self.status.setText(f"{len(self.model['folders'])} folder(s) still loaded.")

    def _save_view(self):
        if not self.model:
            QMessageBox.information(self, "No data", "Load a jump session or some folders first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save session", "device_variation_session.json", "JSON (*.json)",
        )
        if not path:
            return
        save_view_state(
            Path(path),
            self.excluded_keys,
            self.split_before,
            self.sample_labels,
            session_meta=self._session_meta(),
        )
        self.status.setText(f"Session saved to {path}")

    def _load_view(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load session", "", "JSON (*.json)")
        if not path:
            return
        try:
            state = load_view_state(Path(path))
        except ValueError as exc:
            QMessageBox.warning(self, "Could not load session", str(exc))
            return
        self._apply_session_state(state)
        jump = state.get("jump_session_path")
        folders = [Path(p) for p in (state.get("folder_paths") or [])]
        try:
            if jump and Path(jump).is_file():
                self._open_session(Path(jump))
            elif any(p.exists() for p in folders):
                self.model = load_folder_paths(folders)
                self._fill_folder_list()
                self._fill_sample_combos()
                self._refresh_views()
            elif self.model:
                self._fill_label_table()
                self._on_device_changed()
                self._refresh_views()
            else:
                QMessageBox.warning(
                    self, "No data",
                    "That session has no jump-session file or sample folders that still exist.",
                )
                return
        except Exception as exc:
            QMessageBox.warning(self, "Could not load session", str(exc))
            return
        self.status.setText(
            f"Session loaded: {len(self.excluded_keys)} excluded file(s), "
            f"{len(self.split_before)} split override(s)."
        )

    def _session_meta(self) -> Dict[str, Any]:
        folders = []
        jump = None
        if self.model:
            jump_path = self.model.get("session_path")
            jump = str(jump_path) if jump_path else None
            folders = [str(row["path"]) for row in self.model.get("folders") or []]
        compare_rows = []
        for folder, key in self.compare_device_keys.items():
            parsed = _as_device_key(key)
            if parsed is None:
                continue
            compare_rows.append({
                "source_folder": parsed[0],
                "section": parsed[1],
                "device_num": parsed[2],
            })
        return {
            "jump_session_path": jump,
            "folder_paths": folders,
            "compare_devices": compare_rows,
            "normalization": self._mode(),
            "read_voltage": self._read_v(),
            "memristive_only": self.memristive_only.isChecked(),
            "log_y": self.log_check.isChecked(),
            "device_view": self.device_view_combo.currentData(),
            "sample_pre_rule": self.sample_pre_combo.currentData(),
            "sample_post_rule": self.sample_post_combo.currentData(),
            "sample_show_raw": self.sample_raw_check.isChecked(),
            "compare_figure": self.compare_figure_combo.currentData(),
            "sample_plot": self.sample_plot_combo.currentData(),
            "min_sweeps": int(self.min_sweeps_spin.value()),
            "hidden_devices": [
                {"source_folder": key[0], "section": key[1], "device_num": key[2]}
                for key in sorted(self.hidden_device_keys)
            ],
        }

    def _apply_session_state(self, state: Dict[str, Any]):
        self.excluded_keys = set(state.get("excluded_keys") or [])
        self.hidden_device_keys = set()
        for row in state.get("hidden_devices") or []:
            try:
                self.hidden_device_keys.add(
                    (str(row["source_folder"]), str(row["section"]), int(row["device_num"]))
                )
            except (KeyError, TypeError, ValueError):
                continue
        self.split_before = dict(state.get("split_before") or {})
        self.sample_labels = dict(state.get("sample_labels") or {})
        self.compare_device_keys = {}
        for row in state.get("compare_devices") or []:
            try:
                key = (str(row["source_folder"]), str(row["section"]), int(row["device_num"]))
            except (KeyError, TypeError, ValueError):
                continue
            self.compare_device_keys[key[0]] = key
        self._filling = True
        try:
            mode = state.get("normalization")
            if mode:
                self._select_combo(self.norm_combo, mode)
            if state.get("read_voltage") is not None:
                self.read_v_spin.setValue(float(state["read_voltage"]))
            if state.get("memristive_only") is not None:
                self.memristive_only.setChecked(bool(state["memristive_only"]))
            if state.get("log_y") is not None:
                self.log_check.setChecked(bool(state["log_y"]))
            if state.get("device_view"):
                self._select_combo(self.device_view_combo, state["device_view"])
            if state.get("sample_pre_rule"):
                self._select_combo(self.sample_pre_combo, state["sample_pre_rule"])
            if state.get("sample_post_rule"):
                self._select_combo(self.sample_post_combo, state["sample_post_rule"])
            if state.get("sample_show_raw") is not None:
                self.sample_raw_check.setChecked(bool(state["sample_show_raw"]))
            if state.get("compare_figure"):
                self._select_combo(self.compare_figure_combo, state["compare_figure"])
            if state.get("sample_plot"):
                self._select_combo(self.sample_plot_combo, state["sample_plot"])
            if state.get("min_sweeps") is not None:
                self.min_sweeps_spin.setValue(int(state["min_sweeps"]))
        finally:
            self._filling = False

    def _save_origin(self):
        if not self.model:
            QMessageBox.information(self, "No data", "Load a jump session or some folders first.")
            return
        name, ok = QInputDialog.getText(self, "Save for Origin", "Name for this export:")
        if not ok:
            return
        name = name.strip()
        if not name:
            QMessageBox.warning(self, "Name required", "Enter a name so this export does not overwrite another.")
            return
        try:
            out_dir = export_origin_bundle(
                self.model,
                name,
                excluded_keys=self.excluded_keys,
                split_before=self.split_before,
                sample_labels=self.sample_labels,
                mode=self._mode(),
                read_voltage=self._read_v(),
                include_keys=self._include_keys(),
                compare_device_keys=self.compare_device_keys,
                current_device=self._current_device(),
            )
        except Exception as exc:
            QMessageBox.warning(self, "Origin export failed", str(exc))
            return
        self.status.setText(f"Origin tables written to {out_dir}")

    # ------------------------------------------------------------------ shared state
    def _show_help(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("How this viewer works")
        dialog.resize(680, 560)
        layout = QVBoxLayout(dialog)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText(_HELP_TEXT)
        layout.addWidget(text)
        close = QPushButton("Close")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec_()

    def _mode(self) -> str:
        return self.norm_combo.currentData() or NORM_MAX

    def _read_v(self) -> float:
        return float(self.read_v_spin.value())

    def _listed_devices(self, folder: str) -> List[Dict[str, Any]]:
        """Devices in one sample, highest memristive score first."""
        if not self.model or not folder:
            return []
        devices = list(iter_devices(self.model, folder))
        devices.sort(key=_device_rank, reverse=True)
        if self.memristive_only.isChecked():
            memristive = [device for device in devices if _is_memristive_device(device)]
            if memristive:
                return memristive
        return devices

    def _include_keys(self):
        """None means every device. A set limits sample stats to the memristive list."""
        if not self.memristive_only.isChecked() or not self.model:
            return None
        keys = set()
        for folder in self._folder_names():
            for device in self._listed_devices(folder):
                keys.add(device["key"])
        return keys or None

    def _device_in_folder(self, folder: str, key) -> Optional[Dict[str, Any]]:
        wanted = _as_device_key(key)
        if wanted is None or not self.model:
            return None
        for device in iter_devices(self.model, folder):
            if _as_device_key(device["key"]) == wanted:
                return device
        return None

    def _on_memristive_filter(self, *_args):
        self._fill_device_combo()
        self._fill_label_table()
        self._refresh_views()

    def _on_compare_device_changed(self, folder: str, box: QComboBox):
        if self._filling:
            return
        key = _as_device_key(box.currentData())
        if key is None:
            self.compare_device_keys.pop(folder, None)
        else:
            self.compare_device_keys[folder] = key
        self._refresh_compare_tab()

    def _on_norm_changed(self, *_args):
        self.read_v_spin.setEnabled(self._mode() == NORM_READ)
        self.log_check.setEnabled(self._mode() != NORM_LOG)
        self._refresh_views()

    def _folder_names(self) -> List[str]:
        if not self.model:
            return []
        return [row["source_folder"] for row in self.model.get("folders") or []]

    def _fill_folder_list(self):
        self.folder_list.clear()
        if not self.model:
            return
        for row in self.model.get("folders") or []:
            tag = "session" if row.get("in_session") else "no review"
            item = QListWidgetItem(f"{row['source_folder']}  ({tag})")
            item.setData(Qt.UserRole, str(row["path"]))
            item.setToolTip(str(row["path"]))
            self.folder_list.addItem(item)

    def _fill_sample_combos(self):
        names = self._folder_names()
        current_device = self.device_sample_combo.currentData()
        current_sample = self.sample_combo.currentData()
        self._filling = True
        try:
            self.device_sample_combo.clear()
            self.sample_combo.clear()
            for name in names:
                self.device_sample_combo.addItem(name, name)
                self.sample_combo.addItem(name, name)
            self._select_combo(self.device_sample_combo, current_device)
            self._select_combo(self.sample_combo, current_sample)
        finally:
            self._filling = False
        self._fill_label_table()
        self._fill_device_combo()

    def _fill_label_table(self):
        self.label_table.blockSignals(True)
        try:
            self.label_table.setRowCount(0)
            for name in self._folder_names():
                label = self.sample_labels.get(name) or name
                self.sample_labels[name] = label
                row = self.label_table.rowCount()
                self.label_table.insertRow(row)
                folder_item = QTableWidgetItem(name)
                folder_item.setFlags(folder_item.flags() & ~Qt.ItemIsEditable)
                self.label_table.setItem(row, 0, folder_item)
                self.label_table.setItem(row, 1, QTableWidgetItem(label))
                combo = QComboBox()
                devices = self._listed_devices(name)
                for device in devices:
                    combo.addItem(_device_menu_label(device), device["key"])
                chosen = _as_device_key(self.compare_device_keys.get(name))
                picked = 0
                if chosen is not None:
                    for i in range(combo.count()):
                        if _as_device_key(combo.itemData(i)) == chosen:
                            picked = i
                            break
                if combo.count():
                    combo.setCurrentIndex(picked)
                    key = _as_device_key(combo.itemData(picked))
                    if key is not None:
                        self.compare_device_keys[name] = key
                combo.currentIndexChanged.connect(
                    lambda _i, folder=name, box=combo: self._on_compare_device_changed(folder, box)
                )
                self.label_table.setCellWidget(row, 2, combo)
        finally:
            self.label_table.blockSignals(False)

    def _select_combo(self, combo: QComboBox, data):
        if data is None:
            return
        for i in range(combo.count()):
            if combo.itemData(i) == data:
                combo.setCurrentIndex(i)
                return

    def _on_label_edited(self, item: QTableWidgetItem):
        if item.column() != 1 or self._filling:
            return
        folder_item = self.label_table.item(item.row(), 0)
        if folder_item is None:
            return
        self.sample_labels[folder_item.text()] = item.text().strip() or folder_item.text()
        self._refresh_compare_tab()

    def _refresh_views(self):
        self._refresh_device_tab()
        self._refresh_heavy_tabs()

    def _schedule_heavy_refresh(self):
        """Sample and compare plots wait until a burst of file clicks finishes."""
        self._heavy_timer.start(400)

    def _refresh_heavy_tabs(self):
        self._refresh_sample_tab()
        self._refresh_compare_tab()

    def _refresh_sample_and_compare(self):
        self._refresh_sample_tab()
        self._refresh_compare_tab()

    # ------------------------------------------------------------------ device tab
    def _on_device_sample_changed(self, *_args):
        if self._filling:
            return
        self._fill_device_combo()

    def _fill_device_combo(self):
        folder = self.device_sample_combo.currentData()
        previous = self.device_combo.currentData()
        self._filling = True
        try:
            self.device_combo.clear()
            if not self.model or not folder:
                return
            for device in self._listed_devices(folder):
                self.device_combo.addItem(_device_menu_label(device), device["key"])
            self._select_combo(self.device_combo, previous)
        finally:
            self._filling = False
        self._on_device_changed()

    def _current_device(self) -> Optional[Dict[str, Any]]:
        if not self.model:
            return None
        key = self.device_combo.currentData()
        folder = self.device_sample_combo.currentData()
        if key is None or folder is None:
            return None
        wanted = _as_device_key(key)
        for device in iter_devices(self.model, folder):
            if _as_device_key(device["key"]) == wanted:
                return device
        return None

    def _on_device_changed(self, *_args):
        if self._filling:
            return
        self._fill_split_and_files()
        self._refresh_device_tab()

    def _fill_split_and_files(self):
        device = self._current_device()
        self.split_combo.blockSignals(True)
        self.file_list.blockSignals(True)
        try:
            self.split_combo.clear()
            self.file_list.clear()
            if device is None or not self.model:
                return
            classified = classify_device(device, self.model, self.excluded_keys, self.split_before)
            self.split_combo.addItem("Automatic (first accepted jump)", None)
            for sweep in classified["sweeps"]:
                self.split_combo.addItem(sweep["filename"], sweep["filename"])
            override = self.split_before.get(split_lookup_key(*device["key"]))
            if override:
                self._select_combo(self.split_combo, override)
            for sweep in classified["sweeps"]:
                phase = sweep.get("phase") or ""
                item = QListWidgetItem(f"{sweep['filename']}    {phase}")
                item.setData(Qt.UserRole, sweep["path_key"])
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Unchecked if sweep.get("excluded") else Qt.Checked)
                self._style_file_item(item, sweep)
                self.file_list.addItem(item)
        finally:
            self.split_combo.blockSignals(False)
            self.file_list.blockSignals(False)

    def _on_split_changed(self, *_args):
        if self._filling:
            return
        device = self._current_device()
        if device is None:
            return
        key = split_lookup_key(*device["key"])
        chosen = self.split_combo.currentData()
        if chosen:
            self.split_before[key] = chosen
        else:
            self.split_before.pop(key, None)
        self._fill_split_and_files()
        self._refresh_device_tab()
        self._schedule_heavy_refresh()

    def _on_file_clicked(self, item: QListWidgetItem):
        if self._filling or item is None:
            return
        self._highlight_path = item.data(Qt.UserRole)
        self._mark_highlighted_file()
        self._refresh_device_tab()
        self._refresh_sample_tab()

    def _on_file_toggled(self, item: QListWidgetItem):
        if self._filling:
            return
        key = item.data(Qt.UserRole)
        if not key:
            return
        if item.checkState() == Qt.Checked:
            self.excluded_keys.discard(key)
        else:
            self.excluded_keys.add(key)
        self._highlight_path = key
        self._refresh_file_labels()
        self._refresh_device_tab()
        self._refresh_sample_tab()
        self._schedule_heavy_refresh()

    def _set_all_files(self, checked: bool):
        device = self._current_device()
        if device is None or not self.model:
            return
        classified = classify_device(device, self.model, set(), self.split_before)
        wanted = {sweep["path_key"] for sweep in classified["sweeps"]}
        if checked:
            self.excluded_keys.difference_update(wanted)
        else:
            self.excluded_keys.update(wanted)
        self.file_list.blockSignals(True)
        try:
            state = Qt.Checked if checked else Qt.Unchecked
            for row in range(self.file_list.count()):
                item = self.file_list.item(row)
                if item.data(Qt.UserRole) in wanted:
                    item.setCheckState(state)
        finally:
            self.file_list.blockSignals(False)
        self._refresh_file_labels()
        self._refresh_device_tab()
        self._refresh_sample_tab()
        self._schedule_heavy_refresh()

    def _refresh_file_labels(self):
        """Rewrite phase text without a heavy redraw, so uncheck stays responsive."""
        self._apply_file_list(self.file_list, self._current_device())
        self._apply_file_list(self.sample_file_list, self._sample_focus_device())

    def _sample_focus_device(self) -> Optional[Dict[str, Any]]:
        folder = self.sample_combo.currentData() if self.model else None
        if not folder or self._selected_device is None:
            return None
        return self._device_in_folder(folder, self._selected_device)

    def _apply_file_list(self, widget: QListWidget, device: Optional[Dict[str, Any]]):
        if widget is None:
            return
        scroll = widget.verticalScrollBar().value()
        widget.blockSignals(True)
        try:
            widget.clear()
            if device is None or not self.model:
                return
            classified = classify_device(device, self.model, self.excluded_keys, self.split_before)
            for sweep in classified["sweeps"]:
                item = QListWidgetItem()
                item.setData(Qt.UserRole, sweep["path_key"])
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Unchecked if sweep.get("excluded") else Qt.Checked)
                self._style_file_item(item, sweep)
                widget.addItem(item)
        finally:
            widget.blockSignals(False)
            widget.verticalScrollBar().setValue(scroll)

    def _mark_highlighted_file(self):
        for widget in (self.file_list, self.sample_file_list):
            widget.blockSignals(True)
            try:
                for row in range(widget.count()):
                    item = widget.item(row)
                    font = item.font()
                    font.setBold(item.data(Qt.UserRole) == self._highlight_path)
                    item.setFont(font)
            finally:
                widget.blockSignals(False)

    def _style_file_item(self, item: QListWidgetItem, sweep: Dict[str, Any]):
        phase = sweep.get("phase") or ""
        item.setText(f"{sweep['filename']}    {phase}")
        font = item.font()
        font.setBold(sweep.get("path_key") == self._highlight_path)
        item.setFont(font)

    def _refresh_device_tab(self):
        self.device_fig.clear()
        device = self._current_device()
        if device is None or not self.model:
            ax = self.device_fig.add_subplot(111)
            ax.text(0.5, 0.5, "Load a sample to plot a device.", ha="center", va="center")
            ax.set_axis_off()
            self.device_canvas.draw_idle()
            self.device_info.setText("No device selected.")
            return
        classified = classify_device(device, self.model, self.excluded_keys, self.split_before)
        status = classified["status"]
        forming = classified["forming_file"]
        mode = self._mode()
        log_y = bool(self.log_check.isChecked()) and mode != NORM_LOG
        if self.device_view_combo.currentData() == "lifetime":
            sweeps = list(classified["included"])
            title = f"Lifetime (n={len(sweeps)})"
            if forming:
                title += f" — black trace is the forming file {forming}"
            ax_lin = self.device_fig.add_subplot(2 if log_y else 1, 1, 1)
            self._plot_sweeps(ax_lin, sweeps, forming, mode, log_y=False)
            ax_lin.set_title(title, fontsize=10)
            if log_y:
                ax_log = self.device_fig.add_subplot(2, 1, 2)
                self._plot_sweeps(ax_log, sweeps, forming, mode, log_y=True)
                ax_log.set_title("Lifetime — log |y|", fontsize=10)
        else:
            if status == "formed":
                phases = [("pre", "Pre-forming"), ("post", "Post-forming")]
            elif status == "no_session":
                phases = [("all", "All sweeps (no jump session)")]
            else:
                phases = [("unformed", "Unformed (no accepted jump)")]
            n_rows = 2 if log_y else 1
            n_cols = len(phases)
            for col, (phase, title) in enumerate(phases):
                sweeps = [s for s in classified["included"] if s.get("phase") == phase]
                ax_lin = self.device_fig.add_subplot(n_rows, n_cols, col + 1)
                self._plot_sweeps(ax_lin, sweeps, forming, mode, log_y=False)
                suffix = f" — forming {forming}" if phase == "post" and forming else ""
                ax_lin.set_title(f"{title} (n={len(sweeps)}){suffix}", fontsize=10)
                if log_y:
                    ax_log = self.device_fig.add_subplot(n_rows, n_cols, n_cols + col + 1)
                    self._plot_sweeps(ax_log, sweeps, forming, mode, log_y=True)
                    ax_log.set_title(f"{title} — log |y|", fontsize=10)
        self.device_fig.tight_layout()
        self.device_canvas.draw_idle()
        n_pre = sum(1 for s in classified["included"] if s.get("phase") == "pre")
        n_post = sum(1 for s in classified["included"] if s.get("phase") == "post")
        self.device_info.setText(
            f"{_device_menu_label(device)}  ·  {status}"
            + (f"  ·  forming file {forming}" if forming else "")
            + f"\n{n_pre} pre, {n_post} post, "
            f"{sum(1 for s in classified['sweeps'] if s.get('excluded'))} excluded."
            + "\nEarly sweeps are blue, later sweeps are red. Rejected jumps are not used."
        )

    def _plot_sweeps(self, ax, sweeps: List[Dict[str, Any]], forming: Optional[str], mode: str, log_y: bool):
        if not sweeps:
            ax.text(0.5, 0.5, "No sweeps", ha="center", va="center", transform=ax.transAxes)
            ax.set_xlabel("Voltage (V)")
            return
        n = len(sweeps)
        highlighted = None
        for i, sweep in enumerate(sweeps):
            y = normalize_current(sweep["voltage"], sweep["current"], mode, self._read_v())
            if log_y:
                y = np.abs(y)
            if sweep.get("path_key") == self._highlight_path:
                highlighted = (sweep["voltage"], y, sweep.get("filename") or "")
                continue
            color = colormaps["turbo"](0.0 if n == 1 else i / (n - 1))
            is_forming = sweep["filename"] == forming
            ax.plot(
                sweep["voltage"], y,
                color="black" if is_forming else color,
                linewidth=2.0 if is_forming else 1.1,
                alpha=0.95 if is_forming else 0.55,
            )
        if highlighted is not None:
            voltage, y, filename = highlighted
            ax.plot(
                voltage, y,
                color="#c2185b", linewidth=2.8, alpha=1.0, zorder=5, label=filename,
            )
            ax.legend(loc="best", fontsize=8)
        ax.set_xlabel("Voltage (V)")
        ax.set_ylabel(("| " + y_axis_label(mode) + " |") if log_y else y_axis_label(mode))
        if log_y:
            ax.set_yscale("log")
        ax.grid(True, alpha=0.3)

    # ------------------------------------------------------------------ sample tab
    def _refresh_sample_tab(self):
        if self._filling:
            return
        try:
            self._refresh_sample_tab_body()
        except Exception as exc:
            self.sample_fig.clear()
            ax = self.sample_fig.add_subplot(111)
            ax.text(0.5, 0.5, "Could not draw this sample.", ha="center", va="center")
            ax.set_axis_off()
            self.sample_canvas.draw_idle()
            self.status.setText(f"Sample plot failed: {exc}")

    def _refresh_sample_tab_body(self):
        self.sample_fig.clear()
        self._filling = True
        try:
            self.distance_table.setRowCount(0)
        finally:
            self._filling = False
        folder = self.sample_combo.currentData() if self.model else None
        if not self.model or not folder:
            self._fill_sample_device_checks([])
            ax = self.sample_fig.add_subplot(111)
            ax.text(0.5, 0.5, "Choose a sample.", ha="center", va="center")
            ax.set_axis_off()
            self.sample_canvas.draw_idle()
            self.sample_info.setText("")
            return
        rows = self._sample_rows(folder)
        self._fill_sample_device_checks(self._listed_devices(folder))
        self._sync_sample_device_combo(rows)
        self._apply_file_list(self.sample_file_list, self._sample_focus_device())
        if self.sample_plot_combo.currentData() in ("positive", "negative"):
            trend_note = self._draw_loop_trend(folder)
        else:
            self._draw_sample(rows)
            trend_note = ""
        self._fill_distance_table(rows)
        shown = [row for row in rows if not self._device_is_hidden(row["key"])]
        hidden = len(rows) - len(shown)
        self.sample_info.setText(
            f"{sum(1 for row in shown if row['status'] == 'formed')} formed, "
            f"{sum(1 for row in shown if row['status'] == 'unformed')} unformed, "
            f"{sum(1 for row in shown if row['status'] == 'no_session')} without a jump session."
            + (f"  {hidden} device(s) unchecked." if hidden else "")
            + trend_note
        )

    def _sample_rows(self, folder: str) -> List[Dict[str, Any]]:
        rows = []
        pre_rule = self.sample_pre_combo.currentData() or "last"
        post_rule = self.sample_post_combo.currentData() or "forming"
        for device in self._listed_devices(folder):
            classified = classify_device(device, self.model, self.excluded_keys, self.split_before)
            forming = classified["forming_file"]
            included = classified["included"]
            status = classified["status"]
            if status == "formed":
                pre = _sweeps_for_rule(included, "pre", pre_rule, forming)
                post = _sweeps_for_rule(included, "post", post_rule, forming)
            elif status == "unformed":
                pre = _sweeps_for_rule(included, "unformed", pre_rule if pre_rule != "none" else "last", forming)
                post = []
            else:
                pre = _sweeps_for_rule(included, "all", pre_rule if pre_rule != "none" else "last", forming)
                post = []
            rows.append({
                "key": device["key"],
                "label": device.get("label") or "",
                "status": status,
                "forming_file": forming,
                "included": included,
                "pre_sweeps": pre,
                "post_sweeps": post,
                "pre_name": ", ".join(sweep["filename"] for sweep in pre),
                "post_name": ", ".join(sweep["filename"] for sweep in post),
            })
        return rows

    def _focused_sweeps(self, folder: str) -> List[Dict[str, Any]]:
        device = self._sample_focus_device()
        if device is None:
            return []
        classified = classify_device(device, self.model, self.excluded_keys, self.split_before)
        return [sweep for sweep in classified["included"]]

    def _measurement_for_loops(self, folder: str) -> Optional[Dict[str, Any]]:
        """The clicked file, or else the included file with the most loops."""
        sweeps = self._focused_sweeps(folder)
        if not sweeps:
            return None
        for sweep in sweeps:
            if sweep.get("path_key") == self._highlight_path:
                return sweep
        ranked = sorted(sweeps, key=lambda sweep: len(split_loops(sweep["voltage"], sweep["current"])), reverse=True)
        return ranked[0]

    def _draw_loop_trend(self, folder: str) -> str:
        self._loop_sweep = None
        negative = self.sample_plot_combo.currentData() == "negative"
        minimum = int(self.min_sweeps_spin.value())
        if self._selected_device is None:
            ax = self.sample_fig.add_subplot(111)
            ax.text(0.5, 0.5, "Pick one device, then click the measurement file.", ha="center", va="center")
            ax.set_axis_off()
            self.sample_canvas.draw_idle()
            return ""
        sweep = self._measurement_for_loops(folder)
        if sweep is None:
            ax = self.sample_fig.add_subplot(111)
            ax.text(0.5, 0.5, "This device has no sweeps to split into loops.", ha="center", va="center")
            ax.set_axis_off()
            self.sample_canvas.draw_idle()
            return ""
        loops = split_loops(sweep["voltage"], sweep["current"])
        self._loop_sweep = sweep
        name = sweep.get("filename") or "measurement"
        if len(loops) < minimum:
            ax = self.sample_fig.add_subplot(111)
            ax.text(
                0.5, 0.5,
                f"{name} has {len(loops)} loop(s). The minimum is {minimum}.",
                ha="center", va="center",
            )
            ax.set_axis_off()
            self.sample_canvas.draw_idle()
            return f"  {name}: {len(loops)} loops."
        ax = self.sample_fig.add_subplot(111)
        self._plot_loop_sides(ax, loops, negative=negative)
        side = "negative" if negative else "positive"
        ax.set_title(f"{name}  ({len(loops)} loops, {side})", fontsize=10)
        self.sample_fig.tight_layout()
        self.sample_canvas.draw_idle()
        return f"  {name}: {len(loops)} {side} loops."

    def _plot_loop_sides(self, ax, loops: List[Tuple[np.ndarray, np.ndarray]], negative: bool):
        n = len(loops)
        drawn = 0
        for i, (voltage, current) in enumerate(loops):
            segments = negative_side(voltage, current) if negative else positive_side(voltage, current)
            if not segments:
                continue
            color = colormaps["turbo"](0.0 if n == 1 else i / (n - 1))
            alpha = 0.45 if n == 1 else 0.25 + 0.7 * (i / (n - 1))
            for loop_v, loop_i in segments:
                ax.plot(loop_v, loop_i, color=color, linewidth=1.05, alpha=alpha)
                drawn += 1
        if drawn == 0:
            which = "negative" if negative else "positive"
            ax.text(0.5, 0.5, f"No {which} voltage", ha="center", va="center", transform=ax.transAxes)
        ax.set_xlabel("Voltage (V)")
        ax.set_ylabel("I / max|I| on V≤0" if negative else "I / max|I| on V≥0")
        ax.grid(True, alpha=0.3)

    def _save_loops(self):
        sweep = self._loop_sweep
        if self.sample_plot_combo.currentData() not in ("positive", "negative") or sweep is None or not self.model:
            QMessageBox.information(
                self, "No measurement",
                "On the Sample tab choose Positive trend or Negative trend, pick a device, and click the measurement file. Then use Save loops.",
            )
            return
        name, ok = QInputDialog.getText(self, "Save loops for Origin", "Name for this export:")
        if not ok:
            return
        name = name.strip()
        if not name:
            QMessageBox.warning(self, "Name required", "Enter a name so this export does not overwrite another.")
            return
        try:
            from tools.filament_jump_finder.core import origin_export_root
            from tools.filament_jump_finder.origin_export import origin_data_dir, sanitize_export_name
            folder_paths = [Path(row["path"]) for row in self.model.get("folders") or []]
            clean = sanitize_export_name(name)
            if not clean:
                raise ValueError("Enter a name for this Origin export.")
            out_dir = origin_data_dir(origin_export_root(folder_paths), clean)
            filename = sweep.get("filename") or "measurement"
            out_path, n_loops = export_measurement_loops(
                out_dir, filename, sweep["voltage"], sweep["current"],
            )
        except Exception as exc:
            QMessageBox.warning(self, "Origin export failed", str(exc))
            return
        self.status.setText(f"{n_loops} sweeps written as 12 Origin files in {out_path}")

    def _draw_sample(self, rows: List[Dict[str, Any]]):
        focus = self._selected_device
        focused = None
        if focus is not None:
            for row in rows:
                if _as_device_key(row["key"]) == focus:
                    focused = row
                    break
        panels = []
        if any(row["status"] == "formed" for row in rows):
            if (self.sample_pre_combo.currentData() or "last") != "none":
                panels.append(("pre_sweeps", "Pre"))
            if (self.sample_post_combo.currentData() or "forming") != "none":
                panels.append(("post_sweeps", "Post"))
        if any(row["status"] == "unformed" for row in rows):
            panels.append(("pre_sweeps", "Unformed"))
        if any(row["status"] == "no_session" for row in rows):
            panels.append(("pre_sweeps", "All sweeps"))
        if focused is not None:
            panels = [("included", "Sweeps")]
        if not panels:
            ax = self.sample_fig.add_subplot(111)
            ax.text(0.5, 0.5, "No sweeps for this choice.", ha="center", va="center")
            ax.set_axis_off()
            self.sample_canvas.draw_idle()
            return
        colors = _device_colors(len(rows))
        modes = [self._mode()]
        if self.sample_raw_check.isChecked() and modes[0] != NORM_RAW:
            modes.append(NORM_RAW)
        n_cols = len(panels)
        for row_i, mode in enumerate(modes):
            for col, (field, title) in enumerate(panels):
                ax = self.sample_fig.add_subplot(len(modes), n_cols, row_i * n_cols + col + 1)
                drawn = 0
                labeled = set()
                for row, color in zip(rows, colors):
                    key = _as_device_key(row["key"])
                    if self._device_is_hidden(key) and key != focus:
                        continue
                    if focus is not None and key != focus:
                        continue
                    if title == "Unformed" and row["status"] != "unformed":
                        continue
                    if title == "All sweeps" and row["status"] != "no_session":
                        continue
                    if title in ("Pre", "Post") and row["status"] != "formed":
                        continue
                    sweeps = row.get(field) or []
                    if focus is not None:
                        self._plot_sweeps(ax, sweeps, row.get("forming_file"), mode, log_y=False)
                        drawn += len(sweeps)
                        continue
                    for sweep in sweeps:
                        y = normalize_current(sweep["voltage"], sweep["current"], mode, self._read_v())
                        highlighted = sweep.get("path_key") == self._highlight_path
                        name = row["label"]
                        show_label = name not in labeled and not highlighted
                        ax.plot(
                            sweep["voltage"], y,
                            color="#c2185b" if highlighted else color,
                            linewidth=2.6 if highlighted else 1.05,
                            alpha=1.0 if highlighted else 0.75,
                            zorder=5 if highlighted else 1,
                            label=name if show_label else None,
                        )
                        labeled.add(name)
                        drawn += 1
                if title == "Post":
                    rule = self.sample_post_combo.currentText()
                elif title == "Sweeps":
                    rule = "checked sweeps"
                else:
                    rule = self.sample_pre_combo.currentText()
                who = focused["label"] if focused else f"{drawn} curves"
                heading = f"{title}: {rule} — {who}"
                if mode == NORM_RAW and len(modes) > 1:
                    heading = f"Raw current · {heading}"
                ax.set_title(heading, fontsize=10)
                ax.set_xlabel("Voltage (V)")
                ax.set_ylabel(y_axis_label(mode))
                ax.grid(True, alpha=0.3)
                if focus is not None or drawn <= 12:
                    handles, labels = ax.get_legend_handles_labels()
                    if labels:
                        ax.legend(handles, labels, loc="best", fontsize=7)
        self.sample_fig.tight_layout()
        self.sample_canvas.draw_idle()

    def _fill_distance_table(self, rows: List[Dict[str, Any]]):
        self._filling = True
        self.distance_table.blockSignals(True)
        try:
            self.distance_table.setRowCount(len(rows))
            row_i = 0
            for device in rows:
                if self._device_is_hidden(device["key"]):
                    continue
                values = [
                    device["label"],
                    device["status"],
                    device["pre_name"],
                    device["post_name"],
                ]
                for col, text in enumerate(values):
                    item = QTableWidgetItem(text)
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    item.setData(Qt.UserRole, device["key"])
                    self.distance_table.setItem(row_i, col, item)
                if self._selected_device == _as_device_key(device["key"]):
                    self.distance_table.selectRow(row_i)
                row_i += 1
            self.distance_table.setRowCount(row_i)
        finally:
            self.distance_table.blockSignals(False)
            self._filling = False

    def _device_is_hidden(self, key) -> bool:
        parsed = _as_device_key(key)
        return parsed is not None and parsed in self.hidden_device_keys

    def _fill_sample_device_checks(self, devices: List[Dict[str, Any]]):
        scroll = self.sample_device_list.verticalScrollBar().value()
        self.sample_device_list.blockSignals(True)
        try:
            self.sample_device_list.clear()
            for device in devices:
                item = QListWidgetItem(_device_menu_label(device))
                item.setData(Qt.UserRole, device["key"])
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                hidden = self._device_is_hidden(device["key"])
                item.setCheckState(Qt.Unchecked if hidden else Qt.Checked)
                self.sample_device_list.addItem(item)
        finally:
            self.sample_device_list.blockSignals(False)
            self.sample_device_list.verticalScrollBar().setValue(scroll)

    def _on_sample_device_toggled(self, item: QListWidgetItem):
        if self._filling or item is None:
            return
        key = _as_device_key(item.data(Qt.UserRole))
        if key is None:
            return
        if item.checkState() == Qt.Checked:
            self.hidden_device_keys.discard(key)
        else:
            self.hidden_device_keys.add(key)
        self._refresh_sample_and_compare()

    def _set_sample_devices(self, checked: bool):
        folder = self.sample_combo.currentData() if self.model else None
        if not folder:
            return
        for device in self._listed_devices(folder):
            key = _as_device_key(device["key"])
            if key is None:
                continue
            if checked:
                self.hidden_device_keys.discard(key)
            else:
                self.hidden_device_keys.add(key)
        self._refresh_sample_and_compare()

    def _on_sample_device_changed(self, *_args):
        if self._filling:
            return
        self._selected_device = _as_device_key(self.sample_device_combo.currentData())
        self._refresh_sample_tab()

    def _sync_sample_device_combo(self, devices: List[Dict[str, Any]]):
        folder = self.sample_combo.currentData()
        listed = self._listed_devices(folder) if self.model and folder else []
        status_by_key = {
            _as_device_key(device["key"]): device.get("status") for device in devices
        }
        keys = [_as_device_key(device["key"]) for device in listed]
        if self._selected_device not in keys:
            self._selected_device = None
        self._filling = True
        self.sample_device_combo.blockSignals(True)
        try:
            self.sample_device_combo.clear()
            self.sample_device_combo.addItem("All devices", None)
            for device in listed:
                status = status_by_key.get(_as_device_key(device["key"])) or ""
                label = _device_menu_label(device)
                if status:
                    label = f"{label}  ({status})"
                if self._device_is_hidden(device["key"]):
                    label = f"{label}  (off)"
                self.sample_device_combo.addItem(label, device["key"])
            if self._selected_device is None:
                self.sample_device_combo.setCurrentIndex(0)
            else:
                for i in range(self.sample_device_combo.count()):
                    if _as_device_key(self.sample_device_combo.itemData(i)) == self._selected_device:
                        self.sample_device_combo.setCurrentIndex(i)
                        break
        finally:
            self.sample_device_combo.blockSignals(False)
            self._filling = False

    def _on_distance_selected(self):
        if self._filling:
            return
        items = self.distance_table.selectedItems()
        if not items:
            return
        key = _as_device_key(items[0].data(Qt.UserRole))
        if key is None or key == self._selected_device:
            return
        self._selected_device = key
        self._refresh_sample_tab()

    def _on_distance_double_clicked(self, item: QTableWidgetItem):
        key = _as_device_key(item.data(Qt.UserRole))
        if key is None:
            return
        source_folder, section, device_num = key
        self._selected_device = key
        self.tabs.setCurrentIndex(0)
        self._filling = True
        try:
            self._select_combo(self.device_sample_combo, source_folder)
        finally:
            self._filling = False
        self._fill_device_combo()
        self._filling = True
        try:
            self._select_combo(self.device_combo, (source_folder, section, int(device_num)))
        finally:
            self._filling = False
        self._on_device_changed()

    # ------------------------------------------------------------------ compare tab
    def _refresh_compare_tab(self):
        if self._filling:
            return
        self.compare_fig.clear()
        names = self._folder_names()
        if not self.model or not names:
            ax = self.compare_fig.add_subplot(111)
            ax.text(0.5, 0.5, "Load two samples to compare them.", ha="center", va="center")
            ax.set_axis_off()
            self.compare_canvas.draw_idle()
            self.compare_info.setText("")
            return
        figure = self.compare_figure_combo.currentData() or "medians"
        if figure == "yield":
            self._draw_compare_yield(names)
        elif figure == "read_current":
            self._draw_compare_read(names)
        elif figure == "overlay":
            self._draw_compare_overlay(names)
        else:
            self._draw_compare_medians(names)

    def _draw_compare_medians(self, names: List[str]):
        compared = summarize_compare(
            self.model, names, self.sample_labels, self.excluded_keys,
            self.split_before, self._mode(), self._read_v(),
            include_keys=self._include_keys(),
        )
        samples = compared["samples"]
        any_formed = any(s["summary"]["n_formed"] for s in samples)
        any_unsplit = any(s["summary"]["n_no_session"] or s["summary"]["n_unformed"] for s in samples)
        if any_formed:
            panels = [("pre_band", "pre", "Pre-forming"), ("post_band", "post", "Post-forming")]
        else:
            panels = [("all_band", "all", "All sweeps (no jump session)")]
        colors = _sample_colors(len(samples))
        ncols = max(len(panels), len(samples), 1)
        gs = self.compare_fig.add_gridspec(2, ncols, height_ratios=[1.0, 1.25])
        for col, (band_name, field, title) in enumerate(panels):
            ax = self.compare_fig.add_subplot(gs[0, col])
            for sample, color in zip(samples, colors):
                summary = sample["summary"]
                _plot_band(ax, summary["grid"], summary.get(band_name), color=color, label=sample["label"])
                for device in summary["devices"]:
                    profile = device.get(field)
                    if profile is None:
                        continue
                    ax.plot(summary["grid"], profile, color=color, alpha=0.15, linewidth=0.8)
            ax.set_title(title)
            ax.set_xlabel("Voltage (V)")
            ax.set_ylabel(y_axis_label(compared["mode"]))
            ax.grid(True, alpha=0.3)
            handles, labels = ax.get_legend_handles_labels()
            if labels:
                ax.legend(handles, labels, loc="best", fontsize=8)
        for col, sample in enumerate(samples):
            ax = self.compare_fig.add_subplot(gs[1, col])
            device = self._device_in_folder(sample["source_folder"], self.compare_device_keys.get(sample["source_folder"]))
            if device is None:
                ax.text(0.5, 0.5, "No device", ha="center", va="center", transform=ax.transAxes)
                ax.set_axis_off()
                continue
            classified = classify_device(device, self.model, self.excluded_keys, self.split_before)
            self._plot_sweeps(
                ax, list(classified["included"]), classified["forming_file"],
                self._mode(), log_y=False,
            )
            ax.set_title(f"{sample['label']}\n{_device_menu_label(device)}", fontsize=9)
        self.compare_fig.tight_layout()
        self.compare_canvas.draw_idle()
        bits = [f"{s['label']}: {s['summary']['n_formed']} formed" for s in samples]
        extra = ""
        if any_unsplit and any_formed:
            extra = " Samples without an accepted jump are left off the pre/post bands."
        self.compare_info.setText("  ·  ".join(bits) + extra)

    def _yield_counts(self, folder: str) -> Tuple[int, int, int]:
        """Formed, unformed, and memristive counts for every device in the folder."""
        formed = unformed = memristive = 0
        for device in iter_devices(self.model, folder):
            status = classify_device(device, self.model, self.excluded_keys, self.split_before)["status"]
            if status == "formed":
                formed += 1
            elif status == "unformed":
                unformed += 1
            if _is_memristive_device(device):
                memristive += 1
        return formed, unformed, memristive

    def _draw_compare_yield(self, names: List[str]):
        colors = _sample_colors(len(names))
        categories = ["Formed", "Unformed", "Memristive"]
        x = np.arange(len(categories))
        width = 0.8 / max(len(names), 1)
        ax = self.compare_fig.add_subplot(111)
        bits = []
        for i, (folder, color) in enumerate(zip(names, colors)):
            formed, unformed, memristive = self._yield_counts(folder)
            label = self.sample_labels.get(folder) or folder
            offset = (i - (len(names) - 1) / 2) * width
            ax.bar(x + offset, [formed, unformed, memristive], width=width * 0.9, color=color, label=label)
            bits.append(f"{label}: {formed} formed, {unformed} unformed, {memristive} memristive")
        ax.set_xticks(x)
        ax.set_xticklabels(categories)
        ax.set_ylabel("Devices")
        ax.set_title("Yield")
        ax.grid(True, axis="y", alpha=0.3)
        ax.legend(loc="best", fontsize=8)
        self.compare_fig.tight_layout()
        self.compare_canvas.draw_idle()
        self.compare_info.setText(
            "  ·  ".join(bits) + "  Memristive devices are also counted as formed or unformed."
        )

    def _checked_sample_rows(self, folder: str) -> List[Dict[str, Any]]:
        return [
            row for row in self._sample_rows(folder)
            if not self._device_is_hidden(row["key"])
        ]

    def _device_read(self, sweeps: List[Dict[str, Any]]) -> Optional[float]:
        values = []
        for sweep in sweeps:
            value = read_current(sweep["voltage"], sweep["current"], self._read_v())
            if value is not None:
                values.append(value)
        if not values:
            return None
        return float(np.median(values))

    def _draw_compare_read(self, names: List[str]):
        colors = _sample_colors(len(names))
        labels = [self.sample_labels.get(folder) or folder for folder in names]
        panels = (("pre_sweeps", "Pre"), ("post_sweeps", "Post"))
        for col, (field, title) in enumerate(panels):
            ax = self.compare_fig.add_subplot(1, 2, col + 1)
            groups = []
            for folder in names:
                values = []
                for row in self._checked_sample_rows(folder):
                    value = self._device_read(row.get(field) or [])
                    if value is not None:
                        values.append(value)
                groups.append(values)
            self._plot_read_boxes(ax, groups, labels, colors)
            rule = self.sample_pre_combo.currentText() if title == "Pre" else self.sample_post_combo.currentText()
            ax.set_title(f"{title}: {rule}")
            ax.set_ylabel(f"|I| at {self._read_v():g} V (A)")
        self.compare_fig.tight_layout()
        self.compare_canvas.draw_idle()
        self.compare_info.setText(
            "One point per checked device. Unformed devices are on the pre plot only."
        )

    def _plot_read_boxes(self, ax, groups: List[List[float]], labels: List[str], colors: List):
        data = []
        positions = []
        box_colors = []
        for i, (values, color) in enumerate(zip(groups, colors)):
            if not values:
                continue
            data.append(values)
            positions.append(i)
            box_colors.append(color)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, fontsize=8)
        ax.grid(True, axis="y", alpha=0.3)
        if not data:
            ax.text(0.5, 0.5, "No sweeps", ha="center", va="center", transform=ax.transAxes)
            return
        drawn = ax.boxplot(data, positions=positions, widths=0.55, patch_artist=True, manage_ticks=False)
        for patch, color in zip(drawn["boxes"], box_colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.35)
        for i, (values, color) in enumerate(zip(groups, colors)):
            if not values:
                continue
            if len(values) == 1:
                xs = [i]
            else:
                xs = np.linspace(i - 0.12, i + 0.12, len(values))
            ax.scatter(xs, values, color=color, s=18, zorder=3)

    def _draw_compare_overlay(self, names: List[str]):
        colors = _sample_colors(len(names))
        panels = (("pre_sweeps", "Pre"), ("post_sweeps", "Post"))
        for col, (field, title) in enumerate(panels):
            ax = self.compare_fig.add_subplot(1, 2, col + 1)
            drawn = 0
            for folder, color in zip(names, colors):
                label = self.sample_labels.get(folder) or folder
                first = True
                for row in self._checked_sample_rows(folder):
                    for sweep in row.get(field) or []:
                        y = normalize_current(sweep["voltage"], sweep["current"], self._mode(), self._read_v())
                        ax.plot(
                            sweep["voltage"], y,
                            color=color, linewidth=1.05, alpha=0.75,
                            label=label if first else None,
                        )
                        first = False
                        drawn += 1
            rule = self.sample_pre_combo.currentText() if title == "Pre" else self.sample_post_combo.currentText()
            ax.set_title(f"{title}: {rule} — {drawn} curves")
            ax.set_xlabel("Voltage (V)")
            ax.set_ylabel(y_axis_label(self._mode()))
            ax.grid(True, alpha=0.3)
            handles, legend_labels = ax.get_legend_handles_labels()
            if legend_labels:
                ax.legend(handles, legend_labels, loc="best", fontsize=8)
            elif drawn == 0:
                ax.text(0.5, 0.5, "No sweeps", ha="center", va="center", transform=ax.transAxes)
        self.compare_fig.tight_layout()
        self.compare_canvas.draw_idle()
        self.compare_info.setText(
            "Each line is one real sweep. Colour is the sample, using the Sample tab's Pre and Post menus."
        )


def _device_rank(device: Dict[str, Any]):
    """Higher tuple sorts first: worked memristive, then memristivity score, then sweep count."""
    best = device.get("best_sweep") or {}
    try:
        mem_score = float(best.get("memristivity_score") or 0)
    except (TypeError, ValueError):
        mem_score = 0.0
    try:
        sweeps = float(device.get("memristive_sweep_count") or device.get("score") or 0)
    except (TypeError, ValueError):
        sweeps = 0.0
    worked = 1.0 if device.get("worked_memristive") or device.get("is_memristive") else 0.0
    return (worked, mem_score, sweeps)


def _is_memristive_device(device: Dict[str, Any]) -> bool:
    return bool(device.get("worked_memristive") or device.get("is_memristive"))


def _device_menu_label(device: Dict[str, Any]) -> str:
    worked, mem_score, sweeps = _device_rank(device)
    parts = [str(device.get("label") or "")]
    if mem_score > 0:
        parts.append(f"score {mem_score:g}")
    elif sweeps > 0:
        parts.append(f"{int(sweeps)} mem sweeps")
    if worked > 0:
        parts.append("memristive")
    return "  ·  ".join(parts)


def _plot_band(ax, grid, band, color, label):
    if not band:
        return
    median, q25, q75 = band
    grid = np.asarray(grid, dtype=float)
    ok = np.isfinite(q25) & np.isfinite(q75)
    ax.fill_between(grid, q25, q75, where=ok, color=color, alpha=0.18, linewidth=0)
    ok_m = np.isfinite(median)
    ax.plot(grid[ok_m], median[ok_m], color=color, linewidth=2.2, label=label)


def _as_device_key(data):
    """Qt may hand back a list instead of the tuple that was stored."""
    if not isinstance(data, (list, tuple)) or len(data) != 3:
        return None
    try:
        return (str(data[0]), str(data[1]), int(data[2]))
    except (TypeError, ValueError):
        return None


def _device_colors(n: int):
    cmap = colormaps["turbo"]
    if n <= 0:
        return []
    if n == 1:
        return [cmap(0.4)]
    return [cmap(i / (n - 1)) for i in range(n)]


def _sample_colors(n: int):
    palette = ["#1565c0", "#ef6c00", "#2e7d32", "#6a1b9a", "#c62828", "#00838f", "#4e342e", "#37474f"]
    if n <= len(palette):
        return palette[:n]
    return _device_colors(n)


def _sweeps_for_rule(included, phase: str, rule: str, forming_filename: Optional[str]):
    """Pick real sweeps. ``none`` hides the phase; ``all`` keeps every sweep in it."""
    group = [sweep for sweep in included if sweep.get("phase") == phase]
    if rule == "none" or not group:
        return []
    if rule == "all":
        return list(group)
    if rule == "first":
        return [group[0]]
    if rule == "forming":
        for sweep in group:
            if sweep.get("filename") == forming_filename:
                return [sweep]
        return [group[0]]
    if rule == "after_forming":
        for sweep in group:
            if sweep.get("filename") != forming_filename:
                return [sweep]
        return []
    return [group[-1]]
