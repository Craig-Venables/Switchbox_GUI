"""Thesis-style session comparison graphs and Origin text export."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

PADS = (100, 200, 400)
DEVICE = "#8d8d8d"
JUMP = "#1f4e79"
LATER = "#b9b9b9"
SERIES = ("#1f4e79", "#6e6e6e", "#c47b4a", "#2f6f4e", "#7b4ea3", "#8d5a3c", "#3d6b8c", "#555555")
THESIS_RC = {
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
    "font.size": 10,
    "axes.labelsize": 11,
    "axes.titlesize": 12,
    "axes.linewidth": 0.8,
    "axes.spines.top": False,
    "axes.spines.right": False,
}

PAGES: Tuple[Tuple[str, str], ...] = (
    ("share", "Device vs jump share"),
    ("forming", "Forming yield"),
    ("voltage", "First vs later voltage"),
    ("median", "Median voltage"),
    ("counts", "Jump counts"),
)


def _write_tsv(path: Path, headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> None:
    lines = ["\t".join(headers)]
    for row in rows:
        lines.append("\t".join("" if value is None else str(value) for value in row))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _pad(row: Dict[str, Any], um: int) -> Dict[str, Any]:
    return next((item for item in row.get("pads") or [] if item.get("pad_um") == um), {})


def _usable(results: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [row for row in results if row.get("pads")]


def _pads(pad_um: Optional[int]) -> Tuple[int, ...]:
    if pad_um is None:
        return PADS
    return (int(pad_um),)


def _pct(value: float) -> str:
    if abs(value - round(value)) < 0.05:
        return f"{value:.0f}%"
    return f"{value:.1f}%"


def _fmt(value: Any, spec: str = ".6g") -> str:
    if value is None:
        return ""
    return format(float(value), spec)


def _style(ax) -> None:
    ax.yaxis.grid(True, linestyle=":", linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)


def origin_tables(results: Sequence[Dict[str, Any]]) -> Dict[str, Tuple[str, Sequence[str], List[Tuple]]]:
    """Tab-separated tables for every comparison graph. Both jump sets are included."""
    usable = _usable(results)
    share_rows: List[Tuple] = []
    forming_rows: List[Tuple] = []
    voltage_rows: List[Tuple] = []
    median_rows: List[Tuple] = []
    count_rows: List[Tuple] = []
    for row in usable:
        name = row.get("name") or ""
        for um in PADS:
            pad = _pad(row, um)
            n_devices = int(pad.get("n_devices") or 0)
            n_formed = int(pad.get("n_with_jump") or 0)
            n_jumps = int(pad.get("n_jumps") or 0)
            n_first = int(pad.get("n_first") or 0)
            n_later = int(pad.get("n_later") or 0)
            share_rows.append((
                name, um, n_devices,
                _fmt(pad.get("pct_devices"), ".6f"),
                n_jumps, _fmt(pad.get("pct_jumps"), ".6f"),
                n_first, _fmt(pad.get("pct_first_jumps"), ".6f"),
            ))
            forming_rows.append((
                name, um, n_devices, n_formed,
                "" if n_devices == 0 else _fmt(100.0 * n_formed / n_devices, ".6f"),
            ))
            median_rows.append((
                name, um, n_jumps, _fmt(pad.get("median_abs_v")),
                n_first, _fmt(pad.get("median_first_v")),
                n_later, _fmt(pad.get("median_later_v")),
            ))
            count_rows.append((name, um, n_devices, n_formed, n_jumps, n_first, n_later))
            for kind, key in (("first", "first_abs_v"), ("later", "later_abs_v")):
                for value in pad.get(key) or []:
                    voltage_rows.append((name, um, kind, _fmt(value)))
    return {
        "share": (
            "session_device_vs_jump_share.txt",
            [
                "Session", "Pad_um", "N_devices", "Device_share_pct",
                "N_jumps_all", "Jump_share_all_pct", "N_first", "First_jump_share_pct",
            ],
            share_rows,
        ),
        "forming": (
            "session_forming_yield.txt",
            ["Session", "Pad_um", "N_devices", "N_formed", "Yield_pct"],
            forming_rows,
        ),
        "voltage": (
            "session_jump_voltages.txt",
            ["Session", "Pad_um", "JumpKind", "AbsVoltage_V"],
            voltage_rows,
        ),
        "median": (
            "session_median_voltage.txt",
            [
                "Session", "Pad_um", "N_jumps_all", "Median_all_AbsV",
                "N_first", "Median_first_AbsV", "N_later", "Median_later_AbsV",
            ],
            median_rows,
        ),
        "counts": (
            "session_jump_counts.txt",
            ["Session", "Pad_um", "N_devices", "N_formed", "N_jumps_all", "N_first", "N_later"],
            count_rows,
        ),
    }


def write_origin_files(folder: Path, results: Sequence[Dict[str, Any]], keys: Optional[Sequence[str]] = None) -> List[Path]:
    tables = origin_tables(results)
    chosen = list(tables) if keys is None else [key for key in keys if key in tables]
    written = []
    folder.mkdir(parents=True, exist_ok=True)
    for key in chosen:
        filename, headers, rows = tables[key]
        path = folder / filename
        _write_tsv(path, headers, rows)
        written.append(path)
    return written


class SessionGraphsDialog(QDialog):
    """All session comparison figures, with one Origin file per figure."""

    def __init__(self, results: Sequence[Dict[str, Any]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Session graphs")
        self.resize(1180, 780)
        self.setModal(False)
        self._results = _usable(results)
        self._pages: Dict[str, Dict[str, Any]] = {}

        root = QVBoxLayout(self)
        note = QLabel(
            "Each tab is one comparison. First jumps only applies to every tab. "
            "The pad choice applies to the voltage and median tabs. "
            "Save writes a text file and a PNG for each graph. Import the text into Origin as tab-delimited text."
        )
        note.setWordWrap(True)
        root.addWidget(note)

        controls = QHBoxLayout()
        self.first_only = QPushButton("First jumps only")
        self.first_only.setCheckable(True)
        self.first_only.setToolTip("Use the first accepted jump on each device in every graph.")
        controls.addWidget(self.first_only)
        controls.addWidget(QLabel("Pad"))
        self.pad_combo = QComboBox()
        self.pad_combo.addItem("All pads", None)
        for um in PADS:
            self.pad_combo.addItem(f"{um} µm", um)
        self.pad_combo.setCurrentIndex(2)
        controls.addWidget(self.pad_combo)
        controls.addStretch()
        save_txt = QPushButton("Save txt and png…")
        save_txt.setToolTip(
            "Write a text file and a PNG for each graph into the folder you choose."
        )
        save_txt.clicked.connect(self._save_all)
        controls.addWidget(save_txt)
        root.addLayout(controls)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        self.tabs = QTabWidget()
        for key, title in PAGES:
            self.tabs.addTab(self._make_page(key), title)
        root.addWidget(self.tabs, stretch=1)

        self.first_only.toggled.connect(self.redraw)
        self.pad_combo.currentIndexChanged.connect(self.redraw)
        self.redraw()

    def set_results(self, results: Sequence[Dict[str, Any]]) -> None:
        self._results = _usable(results)
        self.redraw()

    def _make_page(self, key: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        caption = QLabel("")
        caption.setWordWrap(True)
        layout.addWidget(caption)
        fig = Figure(figsize=(10.6, 5.4), dpi=100)
        canvas = FigureCanvasQTAgg(fig)
        layout.addWidget(NavigationToolbar2QT(canvas, self))
        layout.addWidget(canvas, stretch=1)
        self._pages[key] = {"fig": fig, "canvas": canvas, "caption": caption}
        return page

    def redraw(self, *_args) -> None:
        first_only = self.first_only.isChecked()
        pad_um = self.pad_combo.currentData()
        drawers = {
            "share": self._draw_share,
            "forming": self._draw_forming,
            "voltage": self._draw_voltage,
            "median": self._draw_median,
            "counts": self._draw_counts,
        }
        with plt.rc_context(THESIS_RC):
            for key, page in self._pages.items():
                fig = page["fig"]
                fig.clear()
                if not self._results:
                    ax = fig.add_subplot(111)
                    ax.text(0.5, 0.5, "No session data", ha="center", va="center")
                    ax.set_xticks([])
                    ax.set_yticks([])
                else:
                    use_pad = pad_um if key in ("voltage", "median") else None
                    page["caption"].setText(drawers[key](fig, first_only, use_pad))
                fig.tight_layout()
                page["canvas"].draw_idle()

    def _draw_share(self, fig: Figure, first_only: bool, pad_um: Optional[int]) -> str:
        pads = _pads(pad_um)
        rows_n, cols = _grid(len(self._results))
        x = np.arange(len(pads))
        width = 0.36
        jump_key = "pct_first_jumps" if first_only else "pct_jumps"
        count_key = "n_first" if first_only else "n_jumps"
        jump_label = "First jumps" if first_only else "Accepted jumps"
        for i, row in enumerate(self._results):
            ax = fig.add_subplot(rows_n, cols, i + 1)
            dev_pct, jump_pct, dev_n, jump_n = [], [], [], []
            for um in pads:
                pad = _pad(row, um)
                dev_pct.append(float(pad.get("pct_devices") or 0.0))
                jump_pct.append(float(pad.get(jump_key) or 0.0))
                dev_n.append(int(pad.get("n_devices") or 0))
                jump_n.append(int(pad.get(count_key) or 0))
            bars_d = ax.bar(x - width / 2, dev_pct, width, color=DEVICE, edgecolor="black", linewidth=0.6, label="Devices", zorder=2)
            bars_j = ax.bar(x + width / 2, jump_pct, width, color=JUMP, edgecolor="black", linewidth=0.6, label=jump_label, zorder=2)
            for bar, pct, n in zip(bars_d, dev_pct, dev_n):
                if n:
                    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.5, _pct(pct), ha="center", va="bottom", fontsize=8, color="#333333")
            for bar, pct, n in zip(bars_j, jump_pct, jump_n):
                if n:
                    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.5, _pct(pct), ha="center", va="bottom", fontsize=8, color=JUMP)
            ax.set_xticks(x)
            ax.set_xticklabels([f"{um} µm" for um in pads])
            ax.set_ylim(0, 118)
            ax.set_title(row.get("name") or "")
            if i % cols == 0:
                ax.set_ylabel("Share of the sample (%)")
            _style(ax)
            if i == 0:
                ax.legend(frameon=False, fontsize=8, loc="upper right")
        which = "first jumps" if first_only else "every accepted jump"
        return f"Grey is the share of devices. Blue is the share of {which}."

    def _draw_forming(self, fig: Figure, _first_only: bool, pad_um: Optional[int]) -> str:
        pads = _pads(pad_um)
        ax = fig.add_subplot(111)
        x = np.arange(len(pads))
        n = max(len(self._results), 1)
        width = min(0.8 / n, 0.28)
        for i, row in enumerate(self._results):
            heights, labels = [], []
            for um in pads:
                pad = _pad(row, um)
                devices = int(pad.get("n_devices") or 0)
                formed = int(pad.get("n_with_jump") or 0)
                heights.append(0.0 if devices == 0 else 100.0 * formed / devices)
                labels.append("" if devices == 0 else f"{formed}/{devices}")
            offset = (i - (n - 1) / 2.0) * width
            bars = ax.bar(
                x + offset, heights, width * 0.92,
                color=SERIES[i % len(SERIES)], edgecolor="black", linewidth=0.5,
                label=row.get("name") or "", zorder=2,
            )
            for bar, text in zip(bars, labels):
                if text:
                    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.4, text, ha="center", va="bottom", fontsize=7)
        ax.set_xticks(x)
        ax.set_xticklabels([f"{um} µm" for um in pads])
        ax.set_ylim(0, 118)
        ax.set_ylabel("Devices that form (%)")
        ax.set_title("Forming yield")
        _style(ax)
        ax.legend(frameon=False, fontsize=8, loc="upper right")
        return "A device forms when it has a first accepted jump. The label is formed / devices."

    def _draw_voltage(self, fig: Figure, first_only: bool, pad_um: Optional[int]) -> str:
        ax = fig.add_subplot(111)
        pads = _pads(pad_um)
        series = []
        for row in self._results:
            name = row.get("name") or ""
            for um in pads:
                pad = _pad(row, um)
                pad_bit = f"\n{um} µm" if len(pads) > 1 else ""
                series.append((f"{name}{pad_bit}\nfirst", list(pad.get("first_abs_v") or []), JUMP))
                if not first_only:
                    series.append((f"{name}{pad_bit}\nlater", list(pad.get("later_abs_v") or []), LATER))
        drawn = [(label, vals, color) for label, vals, color in series if vals]
        if not drawn:
            ax.text(0.5, 0.5, "No jumps for this pad", ha="center", va="center")
            ax.set_xticks([])
            ax.set_yticks([])
            return "No voltages to plot."
        rng = np.random.default_rng(7)
        ymax = 0.0
        for i, (label, vals, color) in enumerate(drawn):
            arr = np.asarray(vals, dtype=float)
            jitter = rng.uniform(-0.12, 0.12, size=arr.size)
            edge = "black" if color == JUMP else "#666666"
            ax.scatter(np.full(arr.size, i) + jitter, arr, s=28, c=color, edgecolors=edge, linewidths=0.4, zorder=3)
            med = float(np.median(arr))
            ax.plot([i - 0.28, i + 0.28], [med, med], color="black", lw=1.4, zorder=4)
            ax.annotate(
                f"{med:.2f} V",
                xy=(i, med),
                xytext=(0, 7),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=8,
                bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.9),
                zorder=5,
            )
            ymax = max(ymax, float(arr.max()), med)
        ax.set_xticks(range(len(drawn)))
        ax.set_xticklabels([label for label, _vals, _color in drawn], fontsize=8)
        ax.set_ylabel("|Voltage| (V)")
        ax.set_title("First jump" if first_only else "First jump and later jumps")
        ax.set_ylim(0.0, ymax + 0.8)
        _style(ax)
        which = "the forming jump" if first_only else "the forming jump in blue and later jumps in grey"
        return f"Each point is one jump. The black line is the median of {which}."

    def _draw_median(self, fig: Figure, first_only: bool, pad_um: Optional[int]) -> str:
        pads = _pads(pad_um)
        ax = fig.add_subplot(111)
        x = np.arange(len(self._results))
        kinds = [("median_first_v", "First jump", JUMP)]
        if not first_only:
            kinds.append(("median_later_v", "Later jumps", LATER))
            kinds.append(("median_abs_v", "All jumps", "#6e6e6e"))
        n = len(kinds)
        width = min(0.8 / max(len(pads) * n, 1), 0.18)
        for p_i, um in enumerate(pads):
            for k_i, (key, label, color) in enumerate(kinds):
                offset = (k_i - (n - 1) / 2.0) * width + (p_i - (len(pads) - 1) / 2.0) * (n * width + 0.08)
                heights = []
                for row in self._results:
                    med = _pad(row, um).get(key)
                    heights.append(0.0 if med is None else float(med))
                show = label if p_i == 0 else None
                bars = ax.bar(x + offset, heights, width * 0.92, color=color, edgecolor="black", linewidth=0.4, label=show, zorder=2)
                for bar, height in zip(bars, heights):
                    if height:
                        ax.text(bar.get_x() + bar.get_width() / 2, height + 0.05, f"{height:.2f}", ha="center", va="bottom", fontsize=6, rotation=90)
        ax.set_xticks(x)
        ax.set_xticklabels([row.get("name") or "" for row in self._results], rotation=15, ha="right")
        ax.set_ylabel("Median |voltage| (V)")
        ax.set_title("Median |V|")
        _style(ax)
        ax.legend(frameon=False, fontsize=8)
        if len(pads) > 1:
            return "Bars are grouped within each sample. Blue is the first jump, light grey the later jumps, dark grey every jump."
        return "Median |V| at the selected pad. Blue is the first jump."

    def _draw_counts(self, fig: Figure, first_only: bool, pad_um: Optional[int]) -> str:
        pads = _pads(pad_um)
        rows_n, cols = _grid(len(self._results))
        x = np.arange(len(pads))
        width = 0.26
        jump_key = "n_first" if first_only else "n_jumps"
        jump_label = "First jumps" if first_only else "All jumps"
        for i, row in enumerate(self._results):
            ax = fig.add_subplot(rows_n, cols, i + 1)
            devices = [int(_pad(row, um).get("n_devices") or 0) for um in pads]
            formed = [int(_pad(row, um).get("n_with_jump") or 0) for um in pads]
            jumps = [int(_pad(row, um).get(jump_key) or 0) for um in pads]
            ax.bar(x - width, devices, width, color=DEVICE, edgecolor="black", linewidth=0.5, label="Devices", zorder=2)
            ax.bar(x, formed, width, color="#6e6e6e", edgecolor="black", linewidth=0.5, label="Formed", zorder=2)
            ax.bar(x + width, jumps, width, color=JUMP, edgecolor="black", linewidth=0.5, label=jump_label, zorder=2)
            ax.set_xticks(x)
            ax.set_xticklabels([f"{um} µm" for um in pads])
            ax.set_title(row.get("name") or "")
            if i % cols == 0:
                ax.set_ylabel("Count")
            _style(ax)
            if i == 0:
                ax.legend(frameon=False, fontsize=8)
        which = "first jumps" if first_only else "every accepted jump"
        return f"Devices, devices that formed, and {which}."

    def _save_all(self) -> None:
        self._save_keys(None, "Save graphs as text for Origin")

    def _save_keys(self, keys: Optional[Sequence[str]], title: str) -> None:
        if not self._results:
            self.status.setText("Compare sessions before saving.")
            return
        start = str(Path(__file__).resolve().parents[1])
        folder = QFileDialog.getExistingDirectory(self, title, start)
        if not folder:
            return
        written = write_origin_files(Path(folder), self._results, keys)
        pngs = self._save_pngs(Path(folder), keys)
        names = ", ".join(path.name for path in written + pngs)
        self.status.setText(f"Wrote {names}.")

    def _save_pngs(self, folder: Path, keys: Optional[Sequence[str]]) -> List[Path]:
        tables = origin_tables(self._results)
        chosen = list(self._pages) if keys is None else [key for key in keys if key in self._pages]
        written = []
        for key in chosen:
            filename = tables[key][0]
            path = folder / Path(filename).with_suffix(".png")
            fig = self._pages[key]["fig"]
            fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
            written.append(path)
        return written


def _grid(n: int) -> Tuple[int, int]:
    if n <= 1:
        return 1, 1
    if n <= 4:
        return int(np.ceil(n / 2)), 2
    return int(np.ceil(n / 3)), 3
