"""Live video display widget."""

from __future__ import annotations

from typing import Optional

import cv2
import numpy as np
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget


class VideoPanel(QWidget):
    clicked = pyqtSignal(float, float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._label = QLabel("Camera not connected")
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setMinimumSize(640, 480)
        self._label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._label.setStyleSheet("background-color: #1e1e1e; color: #cccccc;")
        self._label.mousePressEvent = self._on_mouse_press  # type: ignore[method-assign]
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)
        self._frame_shape: Optional[tuple[int, int]] = None
        self._pixmap_size = (0, 0)

    def set_frame(self, frame: np.ndarray) -> None:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        self._frame_shape = (w, h)
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg)
        scaled = pix.scaled(self._label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._pixmap_size = (scaled.width(), scaled.height())
        self._label.setPixmap(scaled)

    def _on_mouse_press(self, event) -> None:
        if self._frame_shape is None:
            return
        fw, fh = self._frame_shape
        lw, lh = self._label.width(), self._label.height()
        pw, ph = self._pixmap_size
        if pw <= 0 or ph <= 0:
            return
        ox = (lw - pw) / 2.0
        oy = (lh - ph) / 2.0
        x = event.x() - ox
        y = event.y() - oy
        if x < 0 or y < 0 or x > pw or y > ph:
            return
        img_x = x / pw * fw
        img_y = y / ph * fh
        self.clicked.emit(float(img_x), float(img_y))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        pix = self._label.pixmap()
        if pix is not None and not pix.isNull():
            scaled = pix.scaled(self._label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._pixmap_size = (scaled.width(), scaled.height())
            self._label.setPixmap(scaled)
