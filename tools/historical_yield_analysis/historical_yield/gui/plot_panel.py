"""Embedded Matplotlib plot panel with zoom/pan toolbar."""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
import pandas as pd
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from ..auto_yield import load_auto_yield_dataframe, parse_gates
from ..models import CATEGORY_DISPLAY
from ..plots import (
    AGE_CMAP,
    COMPOSITION_COLORS,
    COMPOSITION_ORDER,
    concentration_ticks,
)


PLOT_YIELD = "Yield vs sample ID (Excel)"
PLOT_AUTO_YIELD = "Auto yield ≥N loops vs sample ID"
PLOT_COMPOSITION = "Composition vs sample ID"
PLOT_CONCENTRATION = "Concentration vs yield"

_GATE_COLORS = {
    4: "#2ca02c",
    10: "#1f77b4",
    20: "#ff7f0e",
    50: "#d62728",
    100: "#9467bd",
}


class InteractivePlotPanel(QWidget):
    """Yield / composition / concentration plots with Matplotlib navigation toolbar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._df = pd.DataFrame()
        self._auto_df = pd.DataFrame()
        self._facts_dir = None
        self._plotted = pd.DataFrame()
        self._axis_columns: Tuple[Optional[str], Optional[str]] = (None, None)
        # dpi=130 keeps small concentration clusters legible when zooming.
        self.figure = Figure(figsize=(7, 4.5), dpi=130, tight_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)

        self.plot_type = QComboBox()
        self.plot_type.addItems(
            [PLOT_YIELD, PLOT_AUTO_YIELD, PLOT_COMPOSITION, PLOT_CONCENTRATION]
        )
        self.plot_type.currentIndexChanged.connect(self._on_plot_type_changed)

        self.gates_edit = QLineEdit("4,10,20,50,100")
        self.gates_edit.setToolTip(
            "Comma-separated min memristive_loop_count gates "
            "(cumulative cycles across IV files; not file count). Example: 4,10,50,100"
        )
        self.gates_edit.setMaximumWidth(160)
        self.gates_edit.editingFinished.connect(self._on_gates_changed)

        self.overlay_excel_check = QCheckBox("Overlay Excel strict yield")
        self.overlay_excel_check.setToolTip(
            "On the auto ≥N plot, also draw Excel strict memristive yield for comparison."
        )
        self.overlay_excel_check.toggled.connect(self.redraw)

        self.log_x_check = QCheckBox("Log x (concentration)")
        self.log_x_check.setToolTip(
            "Log-scale the concentration axis to separate low values such as "
            "0.001–0.07 mg/ml. Stock (0) cannot be shown on a log axis."
        )
        self.log_x_check.toggled.connect(self.redraw)

        self.gradient_check = QCheckBox("Colour by sample age")
        self.gradient_check.setToolTip(
            "Colour points by sample number so early devices and later devices "
            "are visually distinct."
        )
        self.gradient_check.toggled.connect(self.redraw)

        self.labels_check = QCheckBox("Show labels")
        self.labels_check.setToolTip("Annotate each point with its sample ID.")
        self.labels_check.toggled.connect(self.redraw)

        self._annot = None
        self._hover_ids: list[str] = []
        self._hover_xy: Optional[np.ndarray] = None

        top = QHBoxLayout()
        top.addWidget(QLabel("Plot:"))
        top.addWidget(self.plot_type)
        top.addWidget(QLabel("Gates ≥"))
        top.addWidget(self.gates_edit)
        top.addWidget(self.overlay_excel_check)
        top.addWidget(self.log_x_check)
        top.addWidget(self.gradient_check)
        top.addWidget(self.labels_check)
        top.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(top)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)
        self.canvas.mpl_connect("motion_notify_event", self._on_motion)
        self._on_plot_type_changed()

    # ---------------------------------------------------------------- public
    def set_dataframe(self, df: pd.DataFrame) -> None:
        self._df = df.copy() if df is not None else pd.DataFrame()
        self.redraw()

    def set_auto_dataframe(self, df: pd.DataFrame) -> None:
        self._auto_df = df.copy() if df is not None else pd.DataFrame()
        self.redraw()

    def set_facts_dir(self, facts_dir) -> None:
        self._facts_dir = facts_dir

    def set_default_gates(self, gates: str) -> None:
        if gates:
            self.gates_edit.setText(str(gates))

    def _on_gates_changed(self) -> None:
        if self._facts_dir is not None:
            self._auto_df = load_auto_yield_dataframe(
                self._facts_dir, gates=self.current_gates()
            )
        self.redraw()

    def plotted_dataframe(self) -> pd.DataFrame:
        """Rows actually drawn, in plotted order (for Origin export)."""
        return self._plotted.copy()

    def plot_kind(self) -> str:
        return self.plot_type.currentText()

    def axis_columns(self) -> Tuple[Optional[str], Optional[str]]:
        """(x_column, y_column) for the current plot, or (None, None)."""
        return self._axis_columns

    def current_gates(self) -> list:
        return parse_gates(self.gates_edit.text())

    def export_stem(self) -> str:
        kind = self.plot_kind()
        if kind == PLOT_YIELD:
            return "plot_yield_vs_sample"
        if kind == PLOT_AUTO_YIELD:
            gates = "-".join(str(g) for g in self.current_gates())
            return f"plot_auto_loop_yield_vs_sample_g{gates}"
        if kind == PLOT_COMPOSITION:
            return "plot_composition_vs_sample"
        stem = "plot_concentration_vs_yield"
        return f"{stem}_logx" if self.log_x_check.isChecked() else stem

    # ---------------------------------------------------------------- drawing
    def _on_plot_type_changed(self, *_args) -> None:
        auto = self.plot_kind() == PLOT_AUTO_YIELD
        self.gates_edit.setEnabled(True)
        self.overlay_excel_check.setEnabled(auto)
        self.redraw()

    def redraw(self) -> None:
        self.figure.clear()
        self._annot = None
        self._hover_ids = []
        self._hover_xy = None
        self._plotted = pd.DataFrame()
        self._axis_columns = (None, None)

        ax = self.figure.add_subplot(111)
        df = self._df
        kind = self.plot_kind()
        self.log_x_check.setEnabled(kind == PLOT_CONCENTRATION)
        self.gradient_check.setEnabled(kind not in (PLOT_COMPOSITION, PLOT_AUTO_YIELD))
        self.labels_check.setEnabled(kind != PLOT_COMPOSITION)

        if kind == PLOT_AUTO_YIELD:
            self._draw_auto_yield(ax)
            self.canvas.draw_idle()
            return

        if df is None or df.empty:
            ax.text(0.5, 0.5, "No samples selected", ha="center", va="center")
            ax.set_axis_off()
            self.canvas.draw_idle()
            return

        if kind == PLOT_YIELD:
            self._draw_yield(ax, df)
        elif kind == PLOT_COMPOSITION:
            self._draw_composition(ax, df)
        else:
            self._draw_concentration(ax, df)
        self.canvas.draw_idle()

    def _scatter_points(self, ax, x, y, sample_numbers) -> None:
        if self.gradient_check.isChecked() and len(x):
            scatter = ax.scatter(
                x,
                y,
                c=sample_numbers,
                cmap=AGE_CMAP,
                s=75,
                edgecolors="k",
                linewidths=0.4,
                alpha=0.9,
                zorder=3,
            )
            bar = self.figure.colorbar(scatter, ax=ax)
            bar.set_label("Sample number (early → late)")
        else:
            ax.scatter(
                x,
                y,
                s=75,
                c="#1f77b4",
                edgecolors="k",
                linewidths=0.4,
                alpha=0.9,
                zorder=3,
            )

    def _annotate_points(self, ax, x, y, labels) -> None:
        if not self.labels_check.isChecked():
            return
        for xi, yi, label in zip(x, y, labels):
            ax.annotate(
                str(label),
                (xi, yi),
                textcoords="offset points",
                xytext=(4, 4),
                fontsize=6,
            )

    def _draw_yield(self, ax, df: pd.DataFrame) -> None:
        sub = df.sort_values("sample_number")
        x = sub["sample_number"].to_numpy(dtype=float)
        y = sub["strict_yield_pct"].to_numpy(dtype=float)
        ax.plot(x, y, linestyle="-", color="#9e9e9e", linewidth=1.0, zorder=2)
        self._scatter_points(ax, x, y, sub["sample_number"].to_numpy())
        self._annotate_points(ax, x, y, sub["sample_id"].tolist())
        ax.set_xlabel("Sample number (D#)")
        ax.set_ylabel("Strict memristive yield (%)")
        ax.set_title("Excel strict memristive yield vs sample ID")
        ax.set_ylim(-2, 105)
        ax.grid(True, alpha=0.3)
        self._hover_xy = np.column_stack([x, y])
        self._hover_ids = sub["sample_id"].astype(str).tolist()
        self._plotted = sub.reset_index(drop=True)
        self._axis_columns = ("sample_number", "strict_yield_pct")
        self._setup_annot(ax)

    def _draw_auto_yield(self, ax) -> None:
        gates = self.current_gates()
        auto = self._auto_df
        if auto is None or auto.empty:
            ax.text(
                0.5,
                0.5,
                "No thesis_llm fact packs found.\n"
                "Set thesis_facts_dir in config.json\n"
                "(e.g. …/llm model/output/facts) and rebuild facts.",
                ha="center",
                va="center",
            )
            ax.set_axis_off()
            return

        excel = self._df
        if excel is not None and not excel.empty and "sample_id" in excel.columns:
            keep = set(excel["sample_id"].astype(str).str.upper())
            auto = auto[auto["sample_id"].astype(str).str.upper().isin(keep)].copy()

        sub = auto.dropna(subset=["sample_number"]).sort_values("sample_number")
        if sub.empty:
            ax.text(
                0.5,
                0.5,
                "No overlapping samples with fact packs",
                ha="center",
                va="center",
            )
            ax.set_axis_off()
            return

        x = sub["sample_number"].to_numpy(dtype=float)
        plotted_cols = ["sample_id", "sample_number"]
        palette = ["#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"]
        any_line = False
        hover_col = None
        for i, g in enumerate(gates):
            col = f"worked_pct_at_{g}"
            if col not in sub.columns:
                continue
            y = pd.to_numeric(sub[col], errors="coerce").to_numpy(dtype=float)
            if np.all(np.isnan(y)):
                continue
            color = _GATE_COLORS.get(int(g), palette[i % len(palette)])
            ax.plot(
                x,
                y,
                marker="o",
                markersize=4.5,
                linewidth=1.6,
                color=color,
                label=f"≥{g} memristive loops",
                zorder=3,
            )
            plotted_cols.append(col)
            if hover_col is None:
                hover_col = col
            any_line = True

        if self.overlay_excel_check.isChecked() and excel is not None and not excel.empty:
            ex = excel.dropna(subset=["sample_number", "strict_yield_pct"]).sort_values(
                "sample_number"
            )
            if not ex.empty:
                ax.plot(
                    ex["sample_number"].to_numpy(dtype=float),
                    ex["strict_yield_pct"].to_numpy(dtype=float),
                    linestyle="--",
                    color="#9e9e9e",
                    linewidth=1.4,
                    marker="x",
                    markersize=4,
                    label="Excel strict yield",
                    zorder=2,
                )

        if not any_line:
            ax.text(
                0.5,
                0.5,
                "Fact packs lack worked_by_loop_threshold for these gates.\n"
                "Run scan-loops + build-facts in thesis_llm.",
                ha="center",
                va="center",
            )
            ax.set_axis_off()
            return

        if hover_col:
            self._annotate_points(
                ax,
                x,
                pd.to_numeric(sub[hover_col], errors="coerce").to_numpy(dtype=float),
                sub["sample_id"].tolist(),
            )

        ax.set_xlabel("Sample number (D#)")
        ax.set_ylabel("Worked memristive-loop yield (%)")
        ax.set_title(
            "Auto worked_memristive_loops yield vs sample ID "
            f"(gates ≥{', ≥'.join(str(g) for g in gates)} loops)"
        )
        ax.set_ylim(-2, 105)
        ax.grid(True, alpha=0.3)
        ax.legend(loc="best", fontsize=7, framealpha=0.92)

        if hover_col:
            hy = pd.to_numeric(sub[hover_col], errors="coerce").to_numpy(dtype=float)
            self._hover_xy = np.column_stack([x, hy])
            self._hover_ids = sub["sample_id"].astype(str).tolist()
            self._setup_annot(ax)
        self._plotted = sub[[c for c in plotted_cols if c in sub.columns]].reset_index(
            drop=True
        )
        self._axis_columns = ("sample_number", hover_col)

    def _draw_composition(self, ax, df: pd.DataFrame) -> None:
        sub = df.sort_values("sample_number")
        x = np.arange(len(sub))
        bottoms = np.zeros(len(sub))
        for cat in COMPOSITION_ORDER:
            col = f"pct_{cat}"
            if col not in sub.columns:
                continue
            vals = sub[col].fillna(0).to_numpy()
            if np.allclose(vals, 0):
                continue
            ax.bar(
                x,
                vals,
                bottom=bottoms,
                width=0.9,
                color=COMPOSITION_COLORS.get(cat, "#333333"),
                label=CATEGORY_DISPLAY.get(cat, cat),
            )
            bottoms = bottoms + vals
        ax.set_ylabel("Share of classified devices (%)")
        ax.set_xlabel("Sample ID")
        ax.set_title("Classification composition vs sample ID")
        ax.set_ylim(0, 105)
        labels = sub["sample_id"].tolist()
        if len(labels) <= 40:
            ax.set_xticks(x)
            ax.set_xticklabels(labels, rotation=90, fontsize=7)
        else:
            step = max(len(labels) // 25, 1)
            ax.set_xticks(x[::step])
            ax.set_xticklabels(labels[::step], rotation=90, fontsize=7)
        ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=7)
        self._plotted = sub.reset_index(drop=True)
        self._axis_columns = ("sample_id", "pct_memristive")

    def _draw_concentration(self, ax, df: pd.DataFrame) -> None:
        sub = df.dropna(subset=["concentration_mgml"]).copy()
        if sub.empty:
            ax.text(0.5, 0.5, "No concentration values", ha="center", va="center")
            ax.set_axis_off()
            return

        log_x = self.log_x_check.isChecked()
        dropped = 0
        if log_x:
            positive = sub["concentration_mgml"].astype(float) > 0
            dropped = int((~positive).sum())
            sub = sub[positive]
            if sub.empty:
                ax.text(
                    0.5,
                    0.5,
                    "All selected samples are Stock (0 mg/ml)\nLog axis needs positive values",
                    ha="center",
                    va="center",
                )
                ax.set_axis_off()
                return

        sub = sub.sort_values("concentration_mgml")
        x = sub["concentration_mgml"].to_numpy(dtype=float)
        y = sub["strict_yield_pct"].to_numpy(dtype=float)
        self._scatter_points(ax, x, y, sub["sample_number"].to_numpy())
        self._annotate_points(ax, x, y, sub["sample_id"].tolist())

        ticks = concentration_ticks(x, log_x=log_x)
        if log_x:
            ax.set_xscale("log")
            if ticks:
                ax.set_xticks(ticks)
                ax.set_xticklabels([f"{t:g}" for t in ticks], rotation=45, ha="right", fontsize=7)
            ax.set_xlabel("Np concentration (mg/ml, log scale)")
        else:
            if ticks:
                ax.set_xticks(ticks)
            ax.set_xlabel("Np concentration (mg/ml); Stock = 0")

        title = "Concentration vs strict memristive yield"
        if dropped:
            title += f"  (Stock/0 hidden: {dropped})"
        ax.set_title(title)
        ax.set_ylabel("Strict memristive yield (%)")
        ax.set_ylim(-2, 105)
        ax.grid(True, which="both", alpha=0.3)

        self._hover_xy = np.column_stack([x, y])
        self._hover_ids = sub["sample_id"].astype(str).tolist()
        self._plotted = sub.reset_index(drop=True)
        self._axis_columns = ("concentration_mgml", "strict_yield_pct")
        self._setup_annot(ax)

    def _setup_annot(self, ax) -> None:
        self._annot = ax.annotate(
            "",
            xy=(0, 0),
            xytext=(12, 12),
            textcoords="offset points",
            bbox=dict(boxstyle="round", fc="w", alpha=0.9),
            arrowprops=dict(arrowstyle="->"),
            zorder=5,
        )
        self._annot.set_visible(False)

    def _on_motion(self, event) -> None:
        if self._annot is None or self._hover_xy is None or event.inaxes is None:
            return
        if event.x is None or event.y is None:
            return
        # Compare in pixel space so hovering behaves the same on log and linear axes.
        pixels = event.inaxes.transData.transform(self._hover_xy)
        distances = np.hypot(pixels[:, 0] - event.x, pixels[:, 1] - event.y)
        nearest = int(np.argmin(distances))
        if distances[nearest] > 20:
            if self._annot.get_visible():
                self._annot.set_visible(False)
                self.canvas.draw_idle()
            return
        x, y = self._hover_xy[nearest]
        self._annot.xy = (x, y)
        if self.plot_kind() == PLOT_CONCENTRATION:
            text = f"{self._hover_ids[nearest]}\n{x:g} mg/ml\nyield={y:.1f}%"
        else:
            text = f"{self._hover_ids[nearest]}\nyield={y:.1f}%"
        self._annot.set_text(text)
        self._annot.set_visible(True)
        self.canvas.draw_idle()
