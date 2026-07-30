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
    QVBoxLayout,
    QWidget,
)

from ..models import CATEGORY_DISPLAY
from ..plots import (
    AGE_CMAP,
    COMPOSITION_COLORS,
    COMPOSITION_ORDER,
    concentration_ticks,
)


PLOT_YIELD = "Yield vs sample ID"
PLOT_COMPOSITION = "Composition vs sample ID"
PLOT_CONCENTRATION = "Concentration vs yield"


class InteractivePlotPanel(QWidget):
    """Yield / composition / concentration plots with Matplotlib navigation toolbar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._df = pd.DataFrame()
        self._plotted = pd.DataFrame()
        self._axis_columns: Tuple[Optional[str], Optional[str]] = (None, None)
        # dpi=130 keeps small concentration clusters legible when zooming.
        self.figure = Figure(figsize=(7, 4.5), dpi=130, tight_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)

        self.plot_type = QComboBox()
        self.plot_type.addItems([PLOT_YIELD, PLOT_COMPOSITION, PLOT_CONCENTRATION])
        self.plot_type.currentIndexChanged.connect(self.redraw)

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

    # ---------------------------------------------------------------- public
    def set_dataframe(self, df: pd.DataFrame) -> None:
        self._df = df.copy() if df is not None else pd.DataFrame()
        self.redraw()

    def plotted_dataframe(self) -> pd.DataFrame:
        """Rows actually drawn, in plotted order (for Origin export)."""
        return self._plotted.copy()

    def plot_kind(self) -> str:
        return self.plot_type.currentText()

    def axis_columns(self) -> Tuple[Optional[str], Optional[str]]:
        """(x_column, y_column) for the current plot, or (None, None)."""
        return self._axis_columns

    def export_stem(self) -> str:
        kind = self.plot_kind()
        if kind == PLOT_YIELD:
            return "plot_yield_vs_sample"
        if kind == PLOT_COMPOSITION:
            return "plot_composition_vs_sample"
        stem = "plot_concentration_vs_yield"
        return f"{stem}_logx" if self.log_x_check.isChecked() else stem

    # ---------------------------------------------------------------- drawing
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
        self.gradient_check.setEnabled(kind != PLOT_COMPOSITION)
        self.labels_check.setEnabled(kind != PLOT_COMPOSITION)

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
        ax.set_title("Strict memristive yield vs sample ID")
        ax.set_ylim(-2, 105)
        ax.grid(True, alpha=0.3)
        self._hover_xy = np.column_stack([x, y])
        self._hover_ids = sub["sample_id"].astype(str).tolist()
        self._plotted = sub.reset_index(drop=True)
        self._axis_columns = ("sample_number", "strict_yield_pct")
        self._setup_annot(ax)

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
