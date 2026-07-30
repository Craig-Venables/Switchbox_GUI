"""PyQt5 main window for historical device yield analysis."""

from __future__ import annotations

import os
import sys
from typing import List, Optional, Set

import pandas as pd
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QGroupBox,
    QFormLayout,
    QFileDialog,
)

from ..analysis import quality_report, sample_dataframe
from ..cache import YieldCache
from ..config import AppConfig, load_config
from ..fabrication import get_fabrication_index
from ..missing_excel import find_missing_excel, missing_excel_dataframe
from ..origin_export import export_origin_txt, export_plotted_txt
from .plot_panel import InteractivePlotPanel
from .workers import ReportWorker, ScanWorker


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self.scan_worker: Optional[ScanWorker] = None
        self.report_worker: Optional[ReportWorker] = None
        self._samples = pd.DataFrame()
        self._updating_filters = False
        self.setWindowTitle("Historical Device Yield Analysis")
        self.resize(1400, 900)
        self._build_ui()
        self.refresh_all()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        status_box = QGroupBox("Sources & cache")
        status_form = QFormLayout(status_box)
        self.roots_label = QLabel()
        self.roots_label.setWordWrap(True)
        self.cache_label = QLabel()
        self.stats_label = QLabel()
        self.fab_label = QLabel()
        self.fab_label.setWordWrap(True)
        status_form.addRow("Data roots:", self.roots_label)
        status_form.addRow("Fabrication:", self.fab_label)
        status_form.addRow("Cache:", self.cache_label)
        status_form.addRow("Stats:", self.stats_label)
        layout.addWidget(status_box)

        btn_row = QHBoxLayout()
        self.btn_scan = QPushButton("Scan / update cache")
        self.btn_rebuild = QPushButton("Rebuild cache")
        self.btn_report = QPushButton("Generate report from selection")
        self.btn_origin = QPushButton("Export Origin TXT")
        self.btn_open_output = QPushButton("Open output folder")
        self.btn_reload_config = QPushButton("Reload config")
        for b in (
            self.btn_scan,
            self.btn_rebuild,
            self.btn_report,
            self.btn_origin,
            self.btn_open_output,
            self.btn_reload_config,
        ):
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

        self.btn_scan.clicked.connect(lambda: self.start_scan(rebuild=False))
        self.btn_rebuild.clicked.connect(self._confirm_rebuild)
        self.btn_report.clicked.connect(self.start_report)
        self.btn_origin.clicked.connect(self.export_origin)
        self.btn_open_output.clicked.connect(self.open_output)
        self.btn_reload_config.clicked.connect(self.reload_config)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        layout.addWidget(self.progress)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(100)
        layout.addWidget(self.log)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, stretch=1)

        self.tabs.addTab(self._build_explore_tab(), "Filters & plot")
        self.tabs.addTab(self._build_tables_tab(), "Tables")
        self.tabs.addTab(self._build_missing_tab(), "Missing Excel")

    def _build_explore_tab(self) -> QWidget:
        page = QWidget()
        split = QSplitter(Qt.Horizontal)
        layout = QVBoxLayout(page)
        layout.addWidget(split)

        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)

        # Category filters
        self.polymer_list = self._make_checklist("Polymer")
        self.b_elec_list = self._make_checklist("B-electrode")
        self.t_elec_list = self._make_checklist("T-electrode")
        self.poly_pct_list = self._make_checklist("Polymer %")
        self.np_type_list = self._make_checklist("Np type")
        for w in (
            self.polymer_list,
            self.b_elec_list,
            self.t_elec_list,
            self.poly_pct_list,
            self.np_type_list,
        ):
            left_lay.addWidget(w)

        # Sample checklist
        sample_box = QGroupBox("Samples")
        sample_lay = QVBoxLayout(sample_box)
        search_row = QHBoxLayout()
        self.sample_search = QLineEdit()
        self.sample_search.setPlaceholderText("Filter sample list…")
        self.sample_search.textChanged.connect(self._filter_sample_list_view)
        search_row.addWidget(self.sample_search)
        sample_lay.addLayout(search_row)
        btn_row = QHBoxLayout()
        self.btn_sel_all = QPushButton("All")
        self.btn_sel_none = QPushButton("None")
        self.btn_sel_invert = QPushButton("Invert")
        self.btn_sel_all.clicked.connect(lambda: self._set_all_samples(True))
        self.btn_sel_none.clicked.connect(lambda: self._set_all_samples(False))
        self.btn_sel_invert.clicked.connect(self._invert_samples)
        btn_row.addWidget(self.btn_sel_all)
        btn_row.addWidget(self.btn_sel_none)
        btn_row.addWidget(self.btn_sel_invert)
        sample_lay.addLayout(btn_row)
        self.sample_list = QListWidget()
        self.sample_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.sample_list.itemChanged.connect(self._on_filter_changed)
        sample_lay.addWidget(self.sample_list)
        self.selection_label = QLabel("Selected: 0")
        sample_lay.addWidget(self.selection_label)
        left_lay.addWidget(sample_box, stretch=1)

        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        self.plot_panel = InteractivePlotPanel()
        right_lay.addWidget(self.plot_panel, stretch=1)
        plot_btn_row = QHBoxLayout()
        self.btn_export_plot = QPushButton("Export plotted data (TXT)")
        self.btn_export_plot.setToolTip(
            "Write the points currently drawn, with sample names, to a "
            "tab-delimited file for Origin."
        )
        self.btn_export_plot.clicked.connect(self.export_plotted)
        self.btn_save_figure = QPushButton("Save figure (PNG)")
        self.btn_save_figure.clicked.connect(self.save_figure)
        plot_btn_row.addWidget(self.btn_export_plot)
        plot_btn_row.addWidget(self.btn_save_figure)
        plot_btn_row.addStretch(1)
        right_lay.addLayout(plot_btn_row)

        split.addWidget(left)
        split.addWidget(right)
        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 5)
        return page

    def _make_checklist(self, title: str) -> QGroupBox:
        box = QGroupBox(title)
        lay = QVBoxLayout(box)
        lst = QListWidget()
        lst.setMaximumHeight(110)
        lst.setSelectionMode(QAbstractItemView.NoSelection)
        lst.itemChanged.connect(self._on_filter_changed)
        lay.addWidget(lst)
        box.list_widget = lst  # type: ignore[attr-defined]
        return box

    def _build_tables_tab(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        splitter = QSplitter(Qt.Vertical)
        self.sample_table = QTableWidget()
        self.quality_table = QTableWidget()
        splitter.addWidget(self._wrap("Accepted samples (current selection)", self.sample_table))
        splitter.addWidget(self._wrap("Quality / duplicates", self.quality_table))
        lay.addWidget(splitter)
        return page

    def _build_missing_tab(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        row = QHBoxLayout()
        self.btn_refresh_missing = QPushButton("Refresh missing list")
        self.btn_export_missing = QPushButton("Export missing CSV…")
        self.btn_refresh_missing.clicked.connect(self.refresh_missing)
        self.btn_export_missing.clicked.connect(self.export_missing_csv)
        row.addWidget(self.btn_refresh_missing)
        row.addWidget(self.btn_export_missing)
        row.addStretch(1)
        lay.addLayout(row)
        self.missing_label = QLabel("")
        lay.addWidget(self.missing_label)
        self.missing_table = QTableWidget()
        lay.addWidget(self.missing_table)
        return page

    def _wrap(self, title: str, widget: QWidget) -> QWidget:
        box = QGroupBox(title)
        lay = QVBoxLayout(box)
        lay.addWidget(widget)
        return box

    # ------------------------------------------------------------------ data
    def append_log(self, message: str) -> None:
        self.log.append(message)

    def set_busy(self, busy: bool) -> None:
        for btn in (
            self.btn_scan,
            self.btn_rebuild,
            self.btn_report,
            self.btn_origin,
            self.btn_reload_config,
            self.btn_refresh_missing,
        ):
            btn.setEnabled(not busy)

    def _fab_index(self):
        return get_fabrication_index(
            self.config.fabrication_workbook, self.config.fabrication_sheet
        )

    def refresh_all(self) -> None:
        self.refresh_status()
        self.reload_sample_data()
        # The missing-Excel scan is user-triggered. It walks external OneDrive
        # roots and must not delay or prevent the main window from opening.
        self.missing_label.setText(
            "Click “Refresh missing list” to scan Dxx sample folders."
        )

    def refresh_status(self) -> None:
        roots = []
        for r in self.config.data_roots:
            mark = "ON" if r.enabled else "off"
            exists = "exists" if r.path.exists() else "MISSING"
            roots.append(f"[{mark}/{exists}] p{r.priority} {r.name}: {r.path}")
        self.roots_label.setText("\n".join(roots) if roots else "(no roots configured)")
        fab = self.config.fabrication_workbook
        if fab:
            fab_idx = self._fab_index()
            if not fab.exists():
                state = "MISSING"
            elif fab_idx.load_error:
                state = "LOCKED/UNREADABLE"
            else:
                state = "ok"
            msg = f"[{state}] {fab}  (rows={fab_idx.n_rows})"
            if fab_idx.load_error:
                msg += f"\n{fab_idx.load_error}"
            self.fab_label.setText(msg)
        else:
            self.fab_label.setText("(not configured)")
        self.cache_label.setText(str(self.config.sqlite_path))
        if self.config.sqlite_path.exists():
            stats = YieldCache(self.config.sqlite_path).stats()
            self.stats_label.setText(
                f"accepted={stats['workbooks_accepted']}  devices={stats['devices']}  "
                f"classified={stats['classified_devices']}  "
                f"duplicates={stats['duplicates']}  malformed={stats['malformed']}"
            )
        else:
            self.stats_label.setText("cache not created yet — run Scan / update cache")

    def reload_sample_data(self) -> None:
        if not self.config.sqlite_path.exists():
            self._samples = pd.DataFrame()
            self._populate_filter_lists()
            self._populate_sample_list()
            self._apply_selection_to_plot()
            self.sample_table.setRowCount(0)
            self.quality_table.setRowCount(0)
            return
        cache = YieldCache(self.config.sqlite_path)
        self._samples = sample_dataframe(cache, fab_index=self._fab_index())
        prev_selected = self._selected_sample_ids()
        self._populate_filter_lists()
        self._populate_sample_list(prefer_selected=prev_selected or None)
        self._apply_selection_to_plot()
        quality = quality_report(cache)
        self._fill_table(
            self.quality_table,
            quality,
            columns=[
                "sample_id",
                "status",
                "accepted",
                "root_name",
                "duplicate_of",
                "warnings",
            ],
        )

    def _populate_filter_lists(self) -> None:
        self._updating_filters = True
        df = self._samples
        self._fill_check_list(
            self.polymer_list.list_widget,
            sorted(df["polymer"].dropna().unique()) if not df.empty and "polymer" in df else [],
        )
        self._fill_check_list(
            self.b_elec_list.list_widget,
            sorted(df["bottom_electrode"].dropna().unique())
            if not df.empty and "bottom_electrode" in df
            else [],
        )
        self._fill_check_list(
            self.t_elec_list.list_widget,
            sorted(df["top_electrode"].dropna().unique())
            if not df.empty and "top_electrode" in df
            else [],
        )
        pcts = []
        if not df.empty and "polymer_percent" in df.columns:
            pcts = sorted({float(x) for x in df["polymer_percent"].dropna().unique()})
        self._fill_check_list(self.poly_pct_list.list_widget, [str(p) for p in pcts])
        self._fill_check_list(
            self.np_type_list.list_widget,
            sorted(df["np_type"].dropna().unique()) if not df.empty and "np_type" in df else [],
        )
        self._updating_filters = False

    def _fill_check_list(self, lst: QListWidget, values) -> None:
        previous = {
            lst.item(i).text(): lst.item(i).checkState() == Qt.Checked
            for i in range(lst.count())
        }
        lst.blockSignals(True)
        lst.clear()
        for val in values:
            text = str(val)
            item = QListWidgetItem(text)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            # default checked; keep prior state when possible
            checked = previous.get(text, True)
            item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
            lst.addItem(item)
        lst.blockSignals(False)

    def _populate_sample_list(self, prefer_selected: Optional[Set[str]] = None) -> None:
        self._updating_filters = True
        self.sample_list.blockSignals(True)
        self.sample_list.clear()
        if self._samples.empty:
            self.sample_list.blockSignals(False)
            self._updating_filters = False
            return
        for _, row in self._samples.iterrows():
            sid = str(row["sample_id"])
            poly = row.get("polymer") or "?"
            label = f"{sid}  |  {poly}  |  yield={float(row.get('strict_yield_pct') or 0):.1f}%"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, sid)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            if prefer_selected is None:
                checked = True
            else:
                checked = sid in prefer_selected
            item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
            self.sample_list.addItem(item)
        self.sample_list.blockSignals(False)
        self._updating_filters = False
        self._filter_sample_list_view(self.sample_search.text())

    def _filter_sample_list_view(self, text: str) -> None:
        needle = (text or "").strip().lower()
        for i in range(self.sample_list.count()):
            item = self.sample_list.item(i)
            visible = needle in item.text().lower() if needle else True
            item.setHidden(not visible)

    def _checked_values(self, lst: QListWidget) -> Optional[List[str]]:
        if lst.count() == 0:
            return None
        checked = [
            lst.item(i).text()
            for i in range(lst.count())
            if lst.item(i).checkState() == Qt.Checked
        ]
        # If nothing checked, treat as empty selection (no rows)
        if len(checked) == lst.count():
            return None  # no restriction
        return checked

    def _selected_sample_ids(self) -> Set[str]:
        ids: Set[str] = set()
        for i in range(self.sample_list.count()):
            item = self.sample_list.item(i)
            if item.checkState() == Qt.Checked:
                ids.add(str(item.data(Qt.UserRole)))
        return ids

    def _set_all_samples(self, checked: bool) -> None:
        self._updating_filters = True
        state = Qt.Checked if checked else Qt.Unchecked
        self.sample_list.blockSignals(True)
        for i in range(self.sample_list.count()):
            item = self.sample_list.item(i)
            if item.isHidden():
                continue
            item.setCheckState(state)
        self.sample_list.blockSignals(False)
        self._updating_filters = False
        self._on_filter_changed()

    def _invert_samples(self) -> None:
        self._updating_filters = True
        self.sample_list.blockSignals(True)
        for i in range(self.sample_list.count()):
            item = self.sample_list.item(i)
            if item.isHidden():
                continue
            item.setCheckState(
                Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked
            )
        self.sample_list.blockSignals(False)
        self._updating_filters = False
        self._on_filter_changed()

    def _on_filter_changed(self, *_args) -> None:
        if self._updating_filters:
            return
        # When category filters change, auto-check matching samples
        sender = self.sender()
        category_lists = {
            self.polymer_list.list_widget,
            self.b_elec_list.list_widget,
            self.t_elec_list.list_widget,
            self.poly_pct_list.list_widget,
            self.np_type_list.list_widget,
        }
        if sender in category_lists:
            self._sync_samples_from_categories()
        self._apply_selection_to_plot()

    def _sync_samples_from_categories(self) -> None:
        """Check samples that match currently checked category filters."""
        if self._samples.empty:
            return
        df = self._apply_category_filters(self._samples)
        allowed = set(df["sample_id"].astype(str)) if not df.empty else set()
        self._updating_filters = True
        self.sample_list.blockSignals(True)
        for i in range(self.sample_list.count()):
            item = self.sample_list.item(i)
            sid = str(item.data(Qt.UserRole))
            item.setCheckState(Qt.Checked if sid in allowed else Qt.Unchecked)
        self.sample_list.blockSignals(False)
        self._updating_filters = False

    def _apply_category_filters(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df
        polymers = self._checked_values(self.polymer_list.list_widget)
        if polymers is not None:
            # empty list => none
            out = out[out["polymer"].isin(polymers)] if polymers else out.iloc[0:0]
        b_elec = self._checked_values(self.b_elec_list.list_widget)
        if b_elec is not None:
            out = out[out["bottom_electrode"].isin(b_elec)] if b_elec else out.iloc[0:0]
        t_elec = self._checked_values(self.t_elec_list.list_widget)
        if t_elec is not None:
            out = out[out["top_electrode"].isin(t_elec)] if t_elec else out.iloc[0:0]
        pcts = self._checked_values(self.poly_pct_list.list_widget)
        if pcts is not None:
            if not pcts:
                out = out.iloc[0:0]
            else:
                allowed = {float(x) for x in pcts}
                out = out[
                    out["polymer_percent"].apply(
                        lambda v: v is not None and not pd.isna(v) and float(v) in allowed
                    )
                ]
        nps = self._checked_values(self.np_type_list.list_widget)
        if nps is not None:
            out = out[out["np_type"].isin(nps)] if nps else out.iloc[0:0]
        return out

    def current_selection_df(self) -> pd.DataFrame:
        if self._samples.empty:
            return self._samples
        ids = self._selected_sample_ids()
        return self._samples[self._samples["sample_id"].isin(ids)].reset_index(drop=True)

    def _apply_selection_to_plot(self) -> None:
        df = self.current_selection_df()
        self.selection_label.setText(f"Selected: {len(df)}")
        self.plot_panel.set_dataframe(df)
        self._fill_table(
            self.sample_table,
            df,
            columns=[
                "sample_id",
                "sample_number",
                "strict_yield_pct",
                "n_classified",
                "n_memristive",
                "concentration_mgml",
                "polymer",
                "polymer_percent",
                "bottom_electrode",
                "top_electrode",
                "np_type",
                "has_fab_row",
                "root_name",
            ],
        )

    def _fill_table(self, table: QTableWidget, df, columns: List[str]) -> None:
        cols = [c for c in columns if c in getattr(df, "columns", [])]
        table.clear()
        table.setColumnCount(len(cols))
        table.setHorizontalHeaderLabels(cols)
        table.setRowCount(0 if df is None or df.empty else len(df))
        if df is None or df.empty or not cols:
            return
        for r_i, (_, row) in enumerate(df.iterrows()):
            for c_i, col in enumerate(cols):
                val = row[col]
                if col == "strict_yield_pct" and val is not None and not pd.isna(val):
                    text = f"{float(val):.1f}"
                else:
                    text = "" if val is None or (isinstance(val, float) and pd.isna(val)) else str(val)
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                table.setItem(r_i, c_i, item)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

    # ------------------------------------------------------------------ missing
    def refresh_missing(self) -> None:
        fab = self._fab_index()
        entries = find_missing_excel(self.config, fab_index=fab)
        preferred = [e for e in entries if e.preferred]
        df = missing_excel_dataframe(entries)
        self.missing_label.setText(
            f"Missing classification Excel: {len(preferred)} preferred sample folders "
            f"({len(entries)} including duplicate-root copies)"
        )
        self._fill_table(
            self.missing_table,
            df,
            columns=[
                "sample_id",
                "sample_number",
                "folder_name",
                "root_name",
                "has_fab_row",
                "preferred",
                "folder_path",
            ],
        )

    def export_missing_csv(self) -> None:
        fab = self._fab_index()
        df = missing_excel_dataframe(find_missing_excel(self.config, fab_index=fab))
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export missing Excel list",
            str(self.config.output_dir / "missing_classification_excel.csv"),
            "CSV (*.csv)",
        )
        if not path:
            return
        df.to_csv(path, index=False)
        self.append_log(f"Missing list exported: {path}")

    # ------------------------------------------------------------------ actions
    def _confirm_rebuild(self) -> None:
        reply = QMessageBox.question(
            self,
            "Rebuild cache",
            "This clears the local SQLite cache and re-parses all workbooks.\n"
            "Source Excel files are never modified.\n\nContinue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.start_scan(rebuild=True)

    def start_scan(self, rebuild: bool = False) -> None:
        if self.scan_worker and self.scan_worker.isRunning():
            return
        self.set_busy(True)
        self.progress.setValue(0)
        self.append_log("Rebuild cache…" if rebuild else "Scanning / updating cache…")
        self.scan_worker = ScanWorker(self.config, rebuild=rebuild)
        self.scan_worker.progress.connect(self._on_scan_progress)
        self.scan_worker.finished_ok.connect(self._on_scan_ok)
        self.scan_worker.failed.connect(self._on_worker_fail)
        self.scan_worker.start()

    def _on_scan_progress(self, message: str, frac: float) -> None:
        self.progress.setValue(int(max(0, min(100, frac * 100))))
        self.append_log(message)

    def _on_scan_ok(self, summary) -> None:
        self.set_busy(False)
        self.progress.setValue(100)
        d = summary.as_dict()
        self.append_log(
            f"Scan done: discovered={d['discovered']} unchanged={d['unchanged']} "
            f"imported={d['imported']} duplicates={d['duplicates_rejected']} "
            f"malformed={d['malformed']} accepted={d['accepted']}"
        )
        self.refresh_all()

    def start_report(self) -> None:
        if not self.config.sqlite_path.exists():
            QMessageBox.warning(self, "No cache", "Run Scan / update cache first.")
            return
        if self.report_worker and self.report_worker.isRunning():
            return
        ids = sorted(self._selected_sample_ids())
        if not ids:
            QMessageBox.warning(self, "No selection", "Select at least one sample.")
            return
        self.set_busy(True)
        self.append_log(f"Generating report for {len(ids)} selected samples…")
        self.report_worker = ReportWorker(self.config, sample_ids=ids)
        self.report_worker.progress.connect(self.append_log)
        self.report_worker.finished_ok.connect(self._on_report_ok)
        self.report_worker.failed.connect(self._on_worker_fail)
        self.report_worker.start()

    def _on_report_ok(self, result) -> None:
        self.set_busy(False)
        self.progress.setValue(100)
        self.append_log(f"Report written: {result.output_dir}")
        QMessageBox.information(
            self,
            "Report ready",
            f"Report saved to:\n{result.output_dir}\n\n"
            f"CSV + plots + Origin TXT + missing-Excel list",
        )

    def export_origin(self) -> None:
        df = self.current_selection_df()
        if df.empty:
            QMessageBox.warning(self, "No selection", "Select at least one sample.")
            return
        out_dir = self.config.output_dir / "origin_export"
        paths = export_origin_txt(df, out_dir)
        self.append_log(f"Origin TXT written to {out_dir} ({len(paths)} files)")
        QMessageBox.information(
            self,
            "Origin export",
            f"Wrote {len(paths)} files to:\n{out_dir}",
        )

    def export_plotted(self) -> None:
        df = self.plot_panel.plotted_dataframe()
        if df.empty:
            QMessageBox.warning(self, "Nothing plotted", "Draw a plot with at least one sample first.")
            return
        x_col, y_col = self.plot_panel.axis_columns()
        out_dir = self.config.output_dir / "origin_export"
        path = export_plotted_txt(df, out_dir, self.plot_panel.export_stem(), x_col, y_col)
        self.append_log(f"Plotted data written: {path} ({len(df)} rows)")
        QMessageBox.information(
            self,
            "Plot export",
            f"Wrote {len(df)} plotted rows to:\n{path}",
        )

    def save_figure(self) -> None:
        out_dir = self.config.output_dir / "figures"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{self.plot_panel.export_stem()}.png"
        self.plot_panel.figure.savefig(path, dpi=300, bbox_inches="tight")
        self.append_log(f"Figure saved: {path}")

    def _on_worker_fail(self, message: str) -> None:
        self.set_busy(False)
        self.append_log(f"ERROR: {message}")
        QMessageBox.critical(self, "Error", message)

    def open_output(self) -> None:
        path = self.config.output_dir
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(str(path))  # type: ignore[attr-defined]

    def reload_config(self) -> None:
        from ..fabrication import clear_fabrication_cache

        clear_fabrication_cache()
        self.config = load_config(self.config.config_path)
        self.append_log(f"Reloaded config: {self.config.config_path}")
        self.refresh_all()


def run_app(config: Optional[AppConfig] = None) -> int:
    config = config or load_config()
    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow(config)
    win.show()
    return app.exec_()
