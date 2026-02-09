"""
Gallery tab for viewing all plot images in a scrollable grid.

Displays all plot images (PNG, JPG) from the device folder in a scrollable grid view.
"""

import logging
import re
from pathlib import Path
from typing import List, Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QGridLayout, QPushButton, QSizePolicy
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap

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


class GalleryTab(QWidget):
    """
    Gallery tab showing all plot images from device folder in scrollable grid.
    
    Features:
    - Automatically discovers plot images (PNG, JPG, JPEG)
    - Displays in responsive grid layout
    - Scrollable for many plots
    - Click to enlarge (future enhancement)
    """
    
    def __init__(self, parent=None):
        """
        Initialize gallery tab.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.current_device = None
        self.plot_paths = []
        
        self._init_ui()
    
    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Header with info label
        header_layout = QHBoxLayout()
        self.info_label = QLabel("No device selected")
        self.info_label.setStyleSheet("font-weight: bold; padding: 5px;")
        header_layout.addWidget(self.info_label)
        header_layout.addStretch()
        
        # Refresh button
        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.setMaximumWidth(100)
        self.refresh_btn.clicked.connect(self._refresh_plots)
        self.refresh_btn.setEnabled(False)
        header_layout.addWidget(self.refresh_btn)
        
        layout.addLayout(header_layout)
        
        # Create scroll area for plots
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Container widget for plots
        self.plots_container = QWidget()
        self.plots_layout = QGridLayout()
        self.plots_layout.setSpacing(10)
        self.plots_container.setLayout(self.plots_layout)
        
        self.scroll_area.setWidget(self.plots_container)
        layout.addWidget(self.scroll_area)
        
        self.setLayout(layout)
        
        # Show placeholder
        self._show_placeholder()
    
    def _show_placeholder(self):
        """Show placeholder text when no device is selected."""
        self.info_label.setText("No device selected")
        self.refresh_btn.setEnabled(False)
        
        # Clear existing plots
        self._clear_plots()
        
        # Add placeholder label
        placeholder = QLabel("Select a device to view plot images")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet("font-size: 14px; color: gray; padding: 50px;")
        self.plots_layout.addWidget(placeholder, 0, 0)
    
    def _clear_plots(self):
        """Clear all plots from the grid."""
        while self.plots_layout.count():
            item = self.plots_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
    
    def update_device(self, device: DeviceData):
        """
        Update gallery with new device data.
        
        Args:
            device: DeviceData object
        """
        self.current_device = device
        self.refresh_btn.setEnabled(True)
        
        # Discover plot images
        self.plot_paths = self._discover_plot_images(device)
        
        # Update info label
        self.info_label.setText(
            f"Device: {device.device_id} - Found {len(self.plot_paths)} plot images"
        )
        
        # Display plots
        self._display_plots()
        
        logger.info(f"Gallery updated for device {device.device_id}: {len(self.plot_paths)} plots")
    
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
    
    def _display_plots(self):
        """Display all plot images in grid layout."""
        self._clear_plots()
        
        if len(self.plot_paths) == 0:
            # Show "no plots" message
            no_plots_label = QLabel("No plot images found in device folder")
            no_plots_label.setAlignment(Qt.AlignCenter)
            no_plots_label.setStyleSheet("font-size: 14px; color: gray; padding: 50px;")
            self.plots_layout.addWidget(no_plots_label, 0, 0)
            return
        
        # Display plots in grid (3 columns)
        num_columns = 3
        
        for idx, plot_path in enumerate(self.plot_paths):
            row = idx // num_columns
            col = idx % num_columns
            
            # Create plot widget
            plot_widget = self._create_plot_widget(plot_path)
            self.plots_layout.addWidget(plot_widget, row, col)
        
        # Add stretch at the end to push plots to top
        self.plots_layout.setRowStretch(len(self.plot_paths) // num_columns + 1, 1)
    
    def _create_plot_widget(self, plot_path: Path) -> QWidget:
        """
        Create widget for displaying a single plot image.
        
        Args:
            plot_path: Path to plot image
            
        Returns:
            QWidget containing the plot
        """
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Load and scale image
        pixmap = QPixmap(str(plot_path))
        if pixmap.isNull():
            logger.warning(f"Failed to load image: {plot_path}")
            error_label = QLabel("Failed to load image")
            error_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(error_label)
        else:
            # Scale image to fit (max 400x300)
            scaled_pixmap = pixmap.scaled(
                400, 300,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            
            # Create image label
            image_label = QLabel()
            image_label.setPixmap(scaled_pixmap)
            image_label.setAlignment(Qt.AlignCenter)
            image_label.setStyleSheet("border: 1px solid #cccccc; background-color: white;")
            layout.addWidget(image_label)
        
        # Create filename label
        filename_label = QLabel(plot_path.name)
        filename_label.setAlignment(Qt.AlignCenter)
        filename_label.setStyleSheet("font-size: 10px; color: #666666;")
        filename_label.setWordWrap(True)
        filename_label.setMaximumWidth(400)
        layout.addWidget(filename_label)
        
        # Create path label (truncated)
        relative_path = self._get_relative_path(plot_path)
        path_label = QLabel(relative_path)
        path_label.setAlignment(Qt.AlignCenter)
        path_label.setStyleSheet("font-size: 9px; color: #999999;")
        path_label.setWordWrap(True)
        path_label.setMaximumWidth(400)
        layout.addWidget(path_label)
        
        widget.setLayout(layout)
        return widget
    
    def _get_relative_path(self, plot_path: Path) -> str:
        """
        Get relative path from device folder for display.
        
        Args:
            plot_path: Absolute path to plot
            
        Returns:
            Relative path string
        """
        try:
            if self.current_device and self.current_device.measurements:
                device_folder = self.current_device.measurements[0].file_path.parent
                relative = plot_path.relative_to(device_folder)
                return str(relative)
        except (ValueError, AttributeError):
            pass
        
        # Fallback: show parent folder + filename
        return f"{plot_path.parent.name}/{plot_path.name}"
    
    def _refresh_plots(self):
        """Refresh plots for current device."""
        if self.current_device:
            self.update_device(self.current_device)
    
    def clear(self):
        """Clear the gallery tab."""
        self.current_device = None
        self.plot_paths = []
        self._show_placeholder()
