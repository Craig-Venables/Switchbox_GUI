"""
Overlay tab for viewing plot images stacked on top of one another.

Displays all plot images overlaid in a single view with transparency controls.
"""

import logging
import re
from pathlib import Path
from typing import List, Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QSlider, QPushButton, QComboBox, QCheckBox, QSpinBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QImage, QPainter

from ..data.device_data_model import DeviceData

logger = logging.getLogger(__name__)


def natural_sort_key(path: Path) -> List:
    """
    Generate a natural sorting key for filenames with numbers.
    
    Converts '1', '2', '10', '11' to sort as [1, 2, 10, 11] instead of [1, 10, 11, 2].
    
    Args:
        path: Path object
        
    Returns:
        List of strings and integers for natural sorting
    """
    def atoi(text):
        return int(text) if text.isdigit() else text.lower()
    
    return [atoi(c) for c in re.split(r'(\d+)', str(path.name))]


class OverlayTab(QWidget):
    """
    Overlay tab showing all plot images stacked on top of one another.
    
    Features:
    - Displays multiple plots overlaid with adjustable transparency
    - Controls for toggling individual plots
    - Zoom and pan capabilities
    - Export combined image
    """
    
    def __init__(self, parent=None):
        """
        Initialize overlay tab.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.current_device = None
        self.plot_paths = []
        self.plot_pixmaps = []
        self.plot_enabled = []  # Track which plots are enabled
        self.opacity = 0.7  # Default opacity for overlaid plots
        
        self._init_ui()
    
    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        
        # === HEADER with controls ===
        header_layout = QVBoxLayout()
        
        # Top row: Info and refresh
        top_row = QHBoxLayout()
        self.info_label = QLabel("No device selected")
        self.info_label.setStyleSheet("font-weight: bold; padding: 5px;")
        top_row.addWidget(self.info_label)
        top_row.addStretch()
        
        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.setMaximumWidth(100)
        self.refresh_btn.clicked.connect(self._refresh_plots)
        self.refresh_btn.setEnabled(False)
        top_row.addWidget(self.refresh_btn)
        
        header_layout.addLayout(top_row)
        
        # Second row: Opacity control
        opacity_row = QHBoxLayout()
        opacity_label = QLabel("Opacity per layer:")
        opacity_label.setMaximumWidth(120)
        opacity_row.addWidget(opacity_label)
        
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setMinimum(10)
        self.opacity_slider.setMaximum(100)
        self.opacity_slider.setValue(70)
        self.opacity_slider.setTickPosition(QSlider.TicksBelow)
        self.opacity_slider.setTickInterval(10)
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        opacity_row.addWidget(self.opacity_slider)
        
        self.opacity_value_label = QLabel("70%")
        self.opacity_value_label.setMinimumWidth(40)
        opacity_row.addWidget(self.opacity_value_label)
        
        opacity_row.addStretch()
        header_layout.addLayout(opacity_row)
        
        # Third row: Layer selection
        layer_row = QHBoxLayout()
        layer_label = QLabel("Visible layers:")
        layer_label.setMaximumWidth(120)
        layer_row.addWidget(layer_label)
        
        self.layer_combo = QComboBox()
        self.layer_combo.setMinimumWidth(300)
        self.layer_combo.currentIndexChanged.connect(self._on_layer_selection_changed)
        layer_row.addWidget(self.layer_combo)
        
        self.show_all_btn = QPushButton("Show All")
        self.show_all_btn.setMaximumWidth(100)
        self.show_all_btn.clicked.connect(self._show_all_layers)
        layer_row.addWidget(self.show_all_btn)
        
        self.hide_all_btn = QPushButton("Hide All")
        self.hide_all_btn.setMaximumWidth(100)
        self.hide_all_btn.clicked.connect(self._hide_all_layers)
        layer_row.addWidget(self.hide_all_btn)
        
        layer_row.addStretch()
        header_layout.addLayout(layer_row)
        
        layout.addLayout(header_layout)
        
        # === DISPLAY AREA ===
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet("background-color: #f5f5f5;")
        
        # Image display label
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: white; padding: 10px;")
        
        self.scroll_area.setWidget(self.image_label)
        layout.addWidget(self.scroll_area)
        
        self.setLayout(layout)
        
        # Show placeholder
        self._show_placeholder()
    
    def _show_placeholder(self):
        """Show placeholder text when no device is selected."""
        self.info_label.setText("No device selected")
        self.refresh_btn.setEnabled(False)
        self.layer_combo.clear()
        
        placeholder = QLabel("Select a device to view overlaid plot images")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet("font-size: 14px; color: gray; padding: 50px;")
        self.image_label = placeholder
        self.scroll_area.setWidget(placeholder)
    
    def update_device(self, device: DeviceData):
        """
        Update overlay with new device data.
        
        Args:
            device: DeviceData object
        """
        self.current_device = device
        self.refresh_btn.setEnabled(True)
        
        # Discover plot images
        self.plot_paths = self._discover_plot_images(device)
        
        # Load pixmaps
        self._load_pixmaps()
        
        # Update info label
        self.info_label.setText(
            f"Device: {device.device_id} - Overlaying {len(self.plot_paths)} plot images"
        )
        
        # Populate layer combo
        self._populate_layer_combo()
        
        # Display overlaid plots
        self._render_overlay()
        
        logger.info(f"Overlay updated for device {device.device_id}: {len(self.plot_paths)} plots")
    
    def _discover_plot_images(self, device: DeviceData) -> List[Path]:
        """
        Discover all plot images in device folder and subfolders.
        
        Args:
            device: DeviceData object
            
        Returns:
            List of paths to plot images
        """
        plot_paths = []
        
        # Get device folder path from measurements or raw data files
        if device.measurements and len(device.measurements) > 0:
            device_folder = device.measurements[0].file_path.parent
        elif device.raw_data_files and len(device.raw_data_files) > 0:
            device_folder = device.raw_data_files[0].parent
        else:
            logger.warning(f"Cannot determine device folder for {device.device_id}")
            return plot_paths
        
        # Search for image files (PNG, JPG, JPEG)
        image_extensions = ['*.png', '*.PNG', '*.jpg', '*.JPG', '*.jpeg', '*.JPEG']
        
        for ext in image_extensions:
            # Search in device folder and subfolders
            found_images = list(device_folder.rglob(ext))
            plot_paths.extend(found_images)
        
        # Sort naturally by filename (1, 2, 10, 11 instead of 1, 10, 11, 2)
        plot_paths.sort(key=natural_sort_key)
        
        logger.debug(f"Discovered {len(plot_paths)} plot images in {device_folder}")
        return plot_paths
    
    def _load_pixmaps(self):
        """Load all plot images as pixmaps."""
        self.plot_pixmaps = []
        self.plot_enabled = []
        
        for plot_path in self.plot_paths:
            pixmap = QPixmap(str(plot_path))
            if not pixmap.isNull():
                self.plot_pixmaps.append(pixmap)
                self.plot_enabled.append(True)  # All enabled by default
            else:
                logger.warning(f"Failed to load image: {plot_path}")
                self.plot_pixmaps.append(None)
                self.plot_enabled.append(False)
    
    def _populate_layer_combo(self):
        """Populate layer combo box with plot names."""
        self.layer_combo.clear()
        self.layer_combo.addItem("All layers (combined)", -1)
        
        for idx, plot_path in enumerate(self.plot_paths):
            status = "✓" if self.plot_enabled[idx] else "✗"
            self.layer_combo.addItem(f"{status} Layer {idx+1}: {plot_path.name}", idx)
    
    def _render_overlay(self):
        """Render all enabled plots overlaid on top of one another."""
        if len(self.plot_pixmaps) == 0:
            self._show_no_plots()
            return
        
        # Get enabled pixmaps
        enabled_pixmaps = [
            pm for pm, enabled in zip(self.plot_pixmaps, self.plot_enabled)
            if pm is not None and enabled
        ]
        
        if len(enabled_pixmaps) == 0:
            self._show_no_plots()
            return
        
        # Find maximum dimensions
        max_width = max(pm.width() for pm in enabled_pixmaps)
        max_height = max(pm.height() for pm in enabled_pixmaps)
        
        # Create composite image
        composite = QImage(max_width, max_height, QImage.Format_ARGB32)
        composite.fill(Qt.white)
        
        # Paint each enabled pixmap with opacity
        painter = QPainter(composite)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        
        for pixmap in enabled_pixmaps:
            # Calculate centered position
            x = (max_width - pixmap.width()) // 2
            y = (max_height - pixmap.height()) // 2
            
            # Set opacity and draw
            painter.setOpacity(self.opacity)
            painter.drawPixmap(x, y, pixmap)
        
        painter.end()
        
        # Convert to pixmap and display
        result_pixmap = QPixmap.fromImage(composite)
        
        # Scale if too large (max 1200x900)
        if result_pixmap.width() > 1200 or result_pixmap.height() > 900:
            result_pixmap = result_pixmap.scaled(
                1200, 900,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
        
        # Update image label
        if not isinstance(self.image_label, QLabel):
            # Replace placeholder with proper label
            self.image_label = QLabel()
            self.image_label.setAlignment(Qt.AlignCenter)
            self.image_label.setStyleSheet("background-color: white; padding: 10px;")
            self.scroll_area.setWidget(self.image_label)
        
        self.image_label.setPixmap(result_pixmap)
        
        logger.debug(f"Rendered overlay with {len(enabled_pixmaps)} layers at {self.opacity:.1%} opacity")
    
    def _show_no_plots(self):
        """Show message when no plots are available or enabled."""
        placeholder = QLabel("No plot images available or all layers are hidden")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet("font-size: 14px; color: gray; padding: 50px;")
        
        self.image_label = placeholder
        self.scroll_area.setWidget(placeholder)
    
    def _on_opacity_changed(self, value):
        """Handle opacity slider change."""
        self.opacity = value / 100.0
        self.opacity_value_label.setText(f"{value}%")
        self._render_overlay()
    
    def _on_layer_selection_changed(self, index):
        """Handle layer selection change in combo box."""
        # Get the layer index from combo data
        layer_idx = self.layer_combo.currentData()
        
        # Handle None or invalid data
        if layer_idx is None or layer_idx == -1:
            # "All layers" selected or invalid - no specific action needed
            return
        
        # Toggle the selected layer
        if 0 <= layer_idx < len(self.plot_enabled):
            self.plot_enabled[layer_idx] = not self.plot_enabled[layer_idx]
            
            # Update combo box display
            self._populate_layer_combo()
            
            # Set combo back to "All layers"
            self.layer_combo.setCurrentIndex(0)
            
            # Re-render
            self._render_overlay()
    
    def _show_all_layers(self):
        """Show all layers."""
        self.plot_enabled = [True] * len(self.plot_enabled)
        self._populate_layer_combo()
        self._render_overlay()
    
    def _hide_all_layers(self):
        """Hide all layers."""
        self.plot_enabled = [False] * len(self.plot_enabled)
        self._populate_layer_combo()
        self._render_overlay()
    
    def _refresh_plots(self):
        """Refresh plots for current device."""
        if self.current_device:
            self.update_device(self.current_device)
    
    def clear(self):
        """Clear the overlay tab."""
        self.current_device = None
        self.plot_paths = []
        self.plot_pixmaps = []
        self.plot_enabled = []
        self._show_placeholder()
