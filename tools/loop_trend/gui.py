"""Browse multi-loop IV files and save each voltage side for Origin."""

from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
from matplotlib import colormaps
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QListView,
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

from tools.device_variation.core import negative_side, positive_side, split_loops
from tools.filament_jump_finder.core import origin_export_root
from tools.filament_jump_finder.origin_export import origin_data_dir, sanitize_export_name

from .core import load_iv, save_all_loops, scan_folders


class _ScanThread(QThread):
    progress = pyqtSignal(str)
    done = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, folders: List[Path], min_loops: int):
        super().__init__()
        self.folders = folders
        self.min_loops = min_loops

    def run(self):
        try:
            hits = scan_folders(
                self.folders,
                self.min_loops,
                on_progress=lambda name: self.progress.emit(name),
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.done.emit(hits)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Loop trend")
        self.resize(1200, 780)
        self.folders: List[Path] = []
        self.hits: List[Dict] = []
        self._thread: Optional[_ScanThread] = None
        self._build_ui()

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        bar = QHBoxLayout()
        self.btn_add = QPushButton("Add folders…")
        self.btn_scan = QPushButton("Scan")
        self.btn_save = QPushButton("Save all loops…")
        bar.addWidget(self.btn_add)
        bar.addWidget(QLabel("Min loops"))
        self.min_loops = QSpinBox()
        self.min_loops.setRange(2, 5000)
        self.min_loops.setValue(20)
        self.min_loops.setToolTip("Keep a measurement only when the file itself contains at least this many loops.")
        bar.addWidget(self.min_loops)
        bar.addWidget(self.btn_scan)
        bar.addWidget(self.btn_save)
        bar.addStretch(1)
        layout.addLayout(bar)

        self.status = QLabel("Add the sample folders, then scan. Files are sorted by how much the last loop differs from the first.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Change", "Loops", "File", "Folder"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)

        self.fig = Figure(figsize=(10, 6))
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.toolbar = NavigationToolbar2QT(self.canvas, root)
        plot_col = QVBoxLayout()
        plot_col.addWidget(self.toolbar)
        plot_col.addWidget(self.canvas, 1)
        plot_wrap = QWidget()
        plot_wrap.setLayout(plot_col)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.table)
        splitter.addWidget(plot_wrap)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

        self.btn_add.clicked.connect(self._add_folders)
        self.btn_scan.clicked.connect(self._scan)
        self.btn_save.clicked.connect(self._save_all)
        self.table.itemSelectionChanged.connect(self._draw_selected)

    def _add_folders(self):
        dialog = QFileDialog(self, "Sample folders")
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setOption(QFileDialog.ShowDirsOnly, True)
        dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        for view in dialog.findChildren(QListView) + dialog.findChildren(QTreeView):
            if isinstance(view, (QListView, QTreeView)):
                view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        if not dialog.exec_():
            return
        for raw in dialog.selectedFiles():
            path = Path(raw)
            if path not in self.folders:
                self.folders.append(path)
        self.status.setText(f"{len(self.folders)} folder(s) selected. Press Scan.")

    def _scan(self):
        if not self.folders:
            QMessageBox.information(self, "No folders", "Add the sample folders first.")
            return
        if self._thread is not None and self._thread.isRunning():
            return
        self.btn_scan.setEnabled(False)
        self.hits = []
        self.table.setRowCount(0)
        self.status.setText("Scanning…")
        self._thread = _ScanThread(list(self.folders), int(self.min_loops.value()))
        self._thread.progress.connect(lambda name: self.status.setText(f"Scanning {name}"))
        self._thread.done.connect(self._scan_done)
        self._thread.failed.connect(self._scan_failed)
        self._thread.start()

    def _scan_done(self, hits):
        self.btn_scan.setEnabled(True)
        self.hits = list(hits)
        self.table.setRowCount(len(self.hits))
        for row, hit in enumerate(self.hits):
            values = [
                f"{hit['change']:.3g}",
                str(hit["n_loops"]),
                hit["path"].name,
                str(hit["path"].parent),
            ]
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                item.setData(Qt.UserRole, row)
                self.table.setItem(row, col, item)
        self.status.setText(
            f"{len(self.hits)} measurement(s) with at least {int(self.min_loops.value())} loops. "
            "The largest first-to-last change is at the top. Early loops are blue, later loops are red."
        )
        if self.hits:
            self.table.selectRow(0)

    def _scan_failed(self, message: str):
        self.btn_scan.setEnabled(True)
        QMessageBox.warning(self, "Scan failed", message)

    def _selected_hit(self) -> Optional[Dict]:
        items = self.table.selectedItems()
        if not items:
            return None
        index = items[0].data(Qt.UserRole)
        if index is None or index >= len(self.hits):
            return None
        return self.hits[index]

    def _draw_selected(self):
        self.fig.clear()
        hit = self._selected_hit()
        if hit is None:
            self.canvas.draw_idle()
            return
        loaded = load_iv(hit["path"])
        if loaded is None:
            ax = self.fig.add_subplot(111)
            ax.text(0.5, 0.5, "Could not read this file.", ha="center", va="center")
            ax.set_axis_off()
            self.canvas.draw_idle()
            return
        voltage, current = loaded
        loops = split_loops(voltage, current)
        for col, (negative, title, ylabel) in enumerate((
            (False, "Positive", "I / max|I| on V≥0"),
            (True, "Negative", "I / max|I| on V≤0"),
        )):
            ax = self.fig.add_subplot(1, 2, col + 1)
            _plot_side(ax, loops, negative=negative)
            ax.set_title(f"{title} — {hit['path'].name} ({len(loops)} loops)", fontsize=10)
            ax.set_ylabel(ylabel)
        self.fig.tight_layout()
        self.canvas.draw_idle()

    def _save_all(self):
        if not self.hits:
            QMessageBox.information(self, "Nothing to save", "Scan first. Only files over the loop minimum are saved.")
            return
        name, ok = QInputDialog.getText(self, "Save all loops", "Name for this export:")
        if not ok:
            return
        name = name.strip()
        clean = sanitize_export_name(name)
        if not clean:
            QMessageBox.warning(self, "Name required", "Enter a name so this export does not overwrite another.")
            return
        out_dir = origin_data_dir(origin_export_root(self.folders), clean)
        self.status.setText(f"Writing {len(self.hits)} measurements…")
        self.repaint()
        try:
            written = save_all_loops(self.hits, out_dir)
        except Exception as exc:
            QMessageBox.warning(self, "Save failed", str(exc))
            return
        self.status.setText(f"Saved {written} measurement(s), 12 Origin files each, in {out_dir}")


def _plot_side(ax, loops, negative: bool):
    n = len(loops)
    drawn = 0
    for i, (voltage, current) in enumerate(loops):
        segments = negative_side(voltage, current) if negative else positive_side(voltage, current)
        color = colormaps["turbo"](0.0 if n <= 1 else i / (n - 1))
        alpha = 0.45 if n <= 1 else 0.25 + 0.7 * (i / (n - 1))
        for loop_v, loop_i in segments:
            ax.plot(loop_v, loop_i, color=color, linewidth=1.0, alpha=alpha)
            drawn += 1
    if drawn == 0:
        which = "negative" if negative else "positive"
        ax.text(0.5, 0.5, f"No {which} voltage", ha="center", va="center", transform=ax.transAxes)
    ax.set_xlabel("Voltage (V)")
    ax.grid(True, alpha=0.3)
