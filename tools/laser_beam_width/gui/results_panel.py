"""Numeric results display."""

from __future__ import annotations

from typing import Optional

from PyQt5.QtWidgets import QGridLayout, QGroupBox, QLabel, QVBoxLayout, QWidget

from analysis.gaussian_fit import BeamFitResult


def _fmt_px(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"{value:.2f} px"


def _fmt_um(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"{value:.1f} µm"


class ResultsPanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        box = QGroupBox("Beam width")
        grid = QGridLayout(box)
        grid.setHorizontalSpacing(16)
        self.status = QLabel("Waiting…")
        self.fwhm_x = QLabel("—")
        self.fwhm_y = QLabel("—")
        self.e2_x = QLabel("—")
        self.e2_y = QLabel("—")
        self.major = QLabel("—")
        self.minor = QLabel("—")
        self.r2 = QLabel("—")
        self.snr = QLabel("—")
        self.saturation = QLabel("—")

        def add_pair(row: int, col: int, label: str, widget: QLabel) -> None:
            grid.addWidget(QLabel(label), row, col * 2)
            grid.addWidget(widget, row, col * 2 + 1)

        grid.addWidget(QLabel("Status"), 0, 0)
        grid.addWidget(self.status, 0, 1, 1, 3)
        add_pair(1, 0, "FWHM X", self.fwhm_x)
        add_pair(1, 1, "FWHM Y", self.fwhm_y)
        add_pair(2, 0, "1/e² X", self.e2_x)
        add_pair(2, 1, "1/e² Y", self.e2_y)
        add_pair(3, 0, "Major", self.major)
        add_pair(3, 1, "Minor", self.minor)
        add_pair(4, 0, "Fit R²", self.r2)
        add_pair(4, 1, "SNR", self.snr)
        add_pair(5, 0, "Saturation", self.saturation)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(box)

    def update_result(self, fit: Optional[BeamFitResult], um_per_pixel: Optional[float]) -> None:
        if fit is None:
            self.status.setText("No measurement")
            return
        self.status.setText(fit.message)
        self.fwhm_x.setText(self._dual(fit.fwhm_x_px, fit.width_um("fwhm_x_px", um_per_pixel)))
        self.fwhm_y.setText(self._dual(fit.fwhm_y_px, fit.width_um("fwhm_y_px", um_per_pixel)))
        self.e2_x.setText(self._dual(fit.e2_x_px, fit.width_um("e2_x_px", um_per_pixel)))
        self.e2_y.setText(self._dual(fit.e2_y_px, fit.width_um("e2_y_px", um_per_pixel)))
        self.major.setText(self._dual(fit.major_fwhm_px, fit.width_um("major_fwhm_px", um_per_pixel)))
        self.minor.setText(self._dual(fit.minor_fwhm_px, fit.width_um("minor_fwhm_px", um_per_pixel)))
        self.r2.setText(f"{min(fit.r2_x, fit.r2_y):.3f} (2D {fit.r2_2d:.3f})")
        self.snr.setText(f"{fit.snr:.1f}")
        self.saturation.setText(f"{fit.saturation_pct:.2f} %")

    @staticmethod
    def _dual(px: float, um: Optional[float]) -> str:
        if um is None:
            return _fmt_px(px)
        return f"{_fmt_px(px)}  /  {_fmt_um(um)}"
