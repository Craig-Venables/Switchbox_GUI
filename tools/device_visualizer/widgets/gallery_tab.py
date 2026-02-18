"""
Gallery tab for viewing plot images in a scrollable grid.

By default shows only IV dashboard images. Option "Show all plot types" includes
Conduction, SCLC, Endurance, Retention, Forming, and Other, grouped by category.
"""

import logging
from pathlib import Path
from typing import List

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QGridLayout, QPushButton, QCheckBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap

from ..data.device_data_model import DeviceData
from ..utils.plot_categories import (
    sort_plot_paths,
    group_plots_by_category,
    get_plot_category,
)

logger = logging.getLogger(__name__)


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

        # Header: info label, "Show all plot types" checkbox, refresh
        header_layout = QHBoxLayout()
        self.info_label = QLabel("No device selected")
        self.info_label.setStyleSheet("font-weight: bold; padding: 5px;")
        header_layout.addWidget(self.info_label)
        header_layout.addStretch()

        self.show_all_check = QCheckBox("Show all plot types")
        self.show_all_check.setChecked(False)
        self.show_all_check.setToolTip("Unchecked: only IV dashboards. Checked: all plot types (Conduction, SCLC, etc.).")
        self.show_all_check.stateChanged.connect(self._on_show_all_changed)
        header_layout.addWidget(self.show_all_check)

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
        
        # Update info label (count depends on filter)
        self._update_info_label()

        # Display plots (respects "Show all plot types" checkbox)
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
        
        # Sort by category (IV dashboard first) then naturally by filename
        plot_paths = sort_plot_paths(plot_paths)

        logger.debug(f"Discovered {len(plot_paths)} plot images in {device_folder}")
        return plot_paths

    def _paths_to_display(self) -> List[Path]:
        """Paths to show: IV dashboards only, or all if 'Show all plot types' is checked."""
        if not self.plot_paths:
            return []
        if self.show_all_check.isChecked():
            return self.plot_paths
        return [p for p in self.plot_paths if get_plot_category(p) == "IV Dashboard"]

    def _update_info_label(self):
        """Update header label with device and count of visible plots."""
        if not self.current_device:
            self.info_label.setText("No device selected")
            return
        visible = self._paths_to_display()
        total = len(self.plot_paths)
        if len(visible) == total:
            self.info_label.setText(
                f"Device: {self.current_device.device_id} - {len(visible)} plot images"
            )
        else:
            self.info_label.setText(
                f"Device: {self.current_device.device_id} - {len(visible)} shown (IV only; {total} total)"
            )

    def _on_show_all_changed(self, _state):
        """Re-display when 'Show all plot types' is toggled."""
        self._update_info_label()
        self._display_plots()

    def _display_plots(self):
        """Display plot images in grid: IV dashboards only by default, or all grouped by category."""
        self._clear_plots()

        paths = self._paths_to_display()
        if len(paths) == 0:
            # Show "no plots" message
            msg = (
                "No IV dashboard images found."
                if not self.show_all_check.isChecked() and self.plot_paths
                else "No plot images found in device folder"
            )
            no_plots_label = QLabel(msg)
            no_plots_label.setAlignment(Qt.AlignCenter)
            no_plots_label.setStyleSheet("font-size: 14px; color: gray; padding: 50px;")
            self.plots_layout.addWidget(no_plots_label, 0, 0)
            return

        num_columns = 3
        current_row = 0
        show_all = self.show_all_check.isChecked()

        for category_name, category_paths in group_plots_by_category(paths):
            # Section header spanning all columns
            header = QLabel(category_name)
            header.setStyleSheet(
                "font-size: 13px; font-weight: bold; color: #333; "
                "padding: 12px 5px 6px 5px; border-bottom: 2px solid #ccc;"
            )
            # Only show section headers when showing all plot types
            if show_all:
                self.plots_layout.addWidget(header, current_row, 0, 1, num_columns)
                current_row += 1

            for idx, plot_path in enumerate(category_paths):
                row = current_row + idx // num_columns
                col = idx % num_columns
                plot_widget = self._create_plot_widget(plot_path)
                self.plots_layout.addWidget(plot_widget, row, col)

            current_row += (len(category_paths) + num_columns - 1) // num_columns

        # Add stretch at the end to push plots to top
        self.plots_layout.setRowStretch(current_row, 1)
    
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
