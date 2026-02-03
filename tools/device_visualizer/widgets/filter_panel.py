"""
Filter panel widget for filtering devices by type and score range.

Provides checkboxes for device types and a slider for score filtering.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QCheckBox, QSlider,
    QPushButton, QLabel, QHBoxLayout
)
from PyQt5.QtCore import pyqtSignal, Qt
from dataclasses import dataclass
from typing import List
import logging

logger = logging.getLogger(__name__)


@dataclass
class FilterCriteria:
    """
    Filter criteria for device filtering.
    
    Attributes:
        device_types: List of device types to include
        min_score: Minimum memristivity score (0-100)
        max_score: Maximum memristivity score (0-100)
    """
    device_types: List[str]
    min_score: float
    max_score: float


class FilterPanelWidget(QWidget):
    """
    Widget for filtering devices by type and score.
    
    Signals:
        filter_changed(FilterCriteria): Emitted when filter settings change
    """
    
    # Signal emitted when filters change
    filter_changed = pyqtSignal(object)  # FilterCriteria object
    
    # Available device types
    DEVICE_TYPES = [
        'Memristive',
        'Ohmic',
        'Capacitive',
        'Memcapacitive',
        'Conductive',
        'Unknown'
    ]
    
    def __init__(self, parent=None):
        """
        Initialize filter panel widget.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.type_checkboxes = {}
        self.min_score = 0.0
        self.max_score = 100.0
        
        self._init_ui()
        self._reset_filters()
    
    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Title
        title_label = QLabel("<b>Filters</b>")
        layout.addWidget(title_label)
        
        # Device Type Filter Group
        type_group = QGroupBox("Device Type")
        type_layout = QVBoxLayout()
        
        for device_type in self.DEVICE_TYPES:
            checkbox = QCheckBox(device_type)
            checkbox.setChecked(True)  # All checked by default
            checkbox.stateChanged.connect(self._on_filter_changed)
            self.type_checkboxes[device_type] = checkbox
            type_layout.addWidget(checkbox)
        
        type_group.setLayout(type_layout)
        layout.addWidget(type_group)
        
        # Score Range Filter Group
        score_group = QGroupBox("Score Range")
        score_layout = QVBoxLayout()
        
        # Minimum score slider
        min_score_label = QLabel("Minimum Score: 0")
        score_layout.addWidget(min_score_label)
        
        self.min_slider = QSlider(Qt.Horizontal)
        self.min_slider.setMinimum(0)
        self.min_slider.setMaximum(100)
        self.min_slider.setValue(0)
        self.min_slider.setTickPosition(QSlider.TicksBelow)
        self.min_slider.setTickInterval(10)
        self.min_slider.valueChanged.connect(
            lambda v: self._on_slider_changed(min_score_label, "Minimum Score", v, is_min=True)
        )
        score_layout.addWidget(self.min_slider)
        
        # Maximum score slider
        max_score_label = QLabel("Maximum Score: 100")
        score_layout.addWidget(max_score_label)
        
        self.max_slider = QSlider(Qt.Horizontal)
        self.max_slider.setMinimum(0)
        self.max_slider.setMaximum(100)
        self.max_slider.setValue(100)
        self.max_slider.setTickPosition(QSlider.TicksBelow)
        self.max_slider.setTickInterval(10)
        self.max_slider.valueChanged.connect(
            lambda v: self._on_slider_changed(max_score_label, "Maximum Score", v, is_min=False)
        )
        score_layout.addWidget(self.max_slider)
        
        # Store labels for later updates
        self.min_score_label = min_score_label
        self.max_score_label = max_score_label
        
        score_group.setLayout(score_layout)
        layout.addWidget(score_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.apply_button = QPushButton("Apply")
        self.apply_button.clicked.connect(self._apply_filters)
        button_layout.addWidget(self.apply_button)
        
        self.reset_button = QPushButton("Reset")
        self.reset_button.clicked.connect(self._reset_filters)
        button_layout.addWidget(self.reset_button)
        
        layout.addLayout(button_layout)
        
        # Add stretch
        layout.addStretch()
        
        self.setLayout(layout)
    
    def _on_slider_changed(self, label: QLabel, prefix: str, value: int, is_min: bool):
        """
        Handle slider value changes.
        
        Args:
            label: Label to update
            prefix: Label prefix text
            value: New slider value
            is_min: True if this is the minimum slider
        """
        label.setText(f"{prefix}: {value}")
        
        if is_min:
            self.min_score = float(value)
            # Ensure min doesn't exceed max
            if self.min_score > self.max_score:
                self.max_slider.setValue(int(self.min_score))
        else:
            self.max_score = float(value)
            # Ensure max doesn't go below min
            if self.max_score < self.min_score:
                self.min_slider.setValue(int(self.max_score))
        
        self._on_filter_changed()
    
    def _on_filter_changed(self):
        """Handle filter changes (called by checkboxes)."""
        # Auto-apply filters on change
        self._apply_filters()
    
    def _apply_filters(self):
        """Apply current filter settings and emit signal."""
        # Get selected device types
        selected_types = [
            device_type for device_type, checkbox in self.type_checkboxes.items()
            if checkbox.isChecked()
        ]
        
        # Create filter criteria
        criteria = FilterCriteria(
            device_types=selected_types,
            min_score=self.min_score,
            max_score=self.max_score
        )
        
        logger.debug(f"Applying filters: types={selected_types}, score={self.min_score}-{self.max_score}")
        
        # Emit signal
        self.filter_changed.emit(criteria)
    
    def _reset_filters(self):
        """Reset all filters to default (no filtering)."""
        # Check all device type checkboxes
        for checkbox in self.type_checkboxes.values():
            checkbox.setChecked(True)
        
        # Reset score sliders
        self.min_slider.setValue(0)
        self.max_slider.setValue(100)
        self.min_score = 0.0
        self.max_score = 100.0
        
        # Update labels
        self.min_score_label.setText("Minimum Score: 0")
        self.max_score_label.setText("Maximum Score: 100")
        
        # Apply filters
        self._apply_filters()
        
        logger.info("Filters reset to default")
    
    def get_current_criteria(self) -> FilterCriteria:
        """
        Get current filter criteria.
        
        Returns:
            Current FilterCriteria object
        """
        selected_types = [
            device_type for device_type, checkbox in self.type_checkboxes.items()
            if checkbox.isChecked()
        ]
        
        return FilterCriteria(
            device_types=selected_types,
            min_score=self.min_score,
            max_score=self.max_score
        )
