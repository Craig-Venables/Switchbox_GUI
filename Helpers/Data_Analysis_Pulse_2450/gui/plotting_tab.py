"""
Plotting Tab

Interactive plotting tab with matplotlib canvas and controls.
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                              QLabel, QGroupBox, QComboBox, QCheckBox,
                              QSpinBox, QDoubleSpinBox, QColorDialog, QFileDialog,
                              QScrollArea, QFrame, QSplitter, QListWidget,
                              QListWidgetItem, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from pathlib import Path
from typing import List, Optional
import sys

# Matplotlib imports
import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.data_parser import TSPData
from core.plot_generator import PlotGenerator, PlotStyle
from core.statistics import DataStatistics, format_stat_value
from .label_editor_dialog import LabelEditorDialog
from .plot_annotations import AnnotationManager, AnnotationToolbar
from PyQt6.QtWidgets import QDialog
import numpy as np


class DatasetListItem(QListWidgetItem):
    """List item representing a dataset"""
    
    def __init__(self, tsp_data: TSPData, color: str):
        super().__init__()
        self.tsp_data = tsp_data
        self.color = color
        self.visible = True
        
        # Display text with color indicator
        display_name = tsp_data.get_display_name()
        key_params = tsp_data.get_key_parameters()
        if key_params:
            display_name += f" - {key_params}"
        
        self.setText(f"● {display_name}")
        self.update_display()
    
    def update_display(self):
        """Update display based on visibility"""
        if not self.visible:
            self.setForeground(QColor("#666"))
            text = self.text()
            if not text.startswith("○"):
                self.setText(text.replace("●", "○"))
        else:
            self.setForeground(QColor(self.color))


class PlottingTab(QWidget):
    """Interactive plotting tab"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.datasets: List[TSPData] = []
        self.dataset_colors: List[str] = []
        self.custom_labels: List[Optional[str]] = []  # Custom legend labels
        self.custom_samples: List[Optional[str]] = []  # Custom sample names
        self.plot_generator = PlotGenerator()
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel: Plot controls (with scroll area for smaller screens)
        control_scroll = QScrollArea()
        control_scroll.setWidgetResizable(True)
        control_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        control_scroll.setMinimumWidth(250)
        control_scroll.setMaximumWidth(500)
        
        control_panel = QWidget()
        control_layout = QVBoxLayout(control_panel)
        
        # Annotation manager (will be initialized when plot is created)
        self.annotation_manager = None
        
        # Dataset list
        dataset_group = QGroupBox("Datasets")
        dataset_layout = QVBoxLayout()
        
        self.dataset_list = QListWidget()
        self.dataset_list.itemDoubleClicked.connect(self.toggle_dataset_visibility)
        dataset_layout.addWidget(QLabel("Double-click to show/hide:"))
        dataset_layout.addWidget(self.dataset_list, 1)
        
        # Dataset controls
        ds_buttons = QHBoxLayout()
        
        edit_labels_btn = QPushButton("✏️ Edit Labels")
        edit_labels_btn.clicked.connect(self.edit_labels)
        edit_labels_btn.setToolTip("Edit legend labels and sample names")
        ds_buttons.addWidget(edit_labels_btn)
        
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self.remove_selected_dataset)
        ds_buttons.addWidget(remove_btn)
        
        dataset_layout.addLayout(ds_buttons)
        
        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self.clear_all_datasets)
        dataset_layout.addWidget(clear_btn)
        
        dataset_group.setLayout(dataset_layout)
        control_layout.addWidget(dataset_group)
        
        # Plot settings
        settings_group = QGroupBox("Plot Settings")
        settings_layout = QVBoxLayout()
        
        # Line width
        lw_layout = QHBoxLayout()
        lw_layout.addWidget(QLabel("Line Width:"))
        self.line_width_spin = QDoubleSpinBox()
        self.line_width_spin.setRange(0.5, 5.0)
        self.line_width_spin.setValue(2.0)
        self.line_width_spin.setSingleStep(0.5)
        self.line_width_spin.valueChanged.connect(self.update_plot)
        lw_layout.addWidget(self.line_width_spin)
        settings_layout.addLayout(lw_layout)
        
        # Marker size
        ms_layout = QHBoxLayout()
        ms_layout.addWidget(QLabel("Marker Size:"))
        self.marker_size_spin = QSpinBox()
        self.marker_size_spin.setRange(0, 12)
        self.marker_size_spin.setValue(6)
        self.marker_size_spin.valueChanged.connect(self.update_plot)
        ms_layout.addWidget(self.marker_size_spin)
        settings_layout.addLayout(ms_layout)
        
        # Background color
        bg_layout = QHBoxLayout()
        bg_layout.addWidget(QLabel("Background:"))
        self.bg_color_btn = QPushButton("Dark")
        self.bg_color_btn.clicked.connect(self.change_background_color)
        self.bg_color_btn.setMaximumWidth(80)
        bg_layout.addWidget(self.bg_color_btn)
        settings_layout.addLayout(bg_layout)
        
        # Grid
        self.grid_check = QCheckBox("Show Grid")
        self.grid_check.setChecked(True)
        self.grid_check.stateChanged.connect(self.update_plot)
        settings_layout.addWidget(self.grid_check)
        
        # Legend
        self.legend_check = QCheckBox("Show Legend")
        self.legend_check.setChecked(True)
        self.legend_check.stateChanged.connect(self.update_plot)
        settings_layout.addWidget(self.legend_check)
        
        # Log scale
        self.log_scale_check = QCheckBox("Log Scale (Y)")
        self.log_scale_check.stateChanged.connect(self.update_plot)
        settings_layout.addWidget(self.log_scale_check)
        
        settings_group.setLayout(settings_layout)
        control_layout.addWidget(settings_group)
        
        # Data Processing
        processing_group = QGroupBox("Data Processing")
        processing_layout = QVBoxLayout()
        
        # Crop data
        crop_label = QLabel("Crop Data:")
        crop_label.setStyleSheet("font-weight: bold;")
        processing_layout.addWidget(crop_label)
        
        # Start point
        start_layout = QHBoxLayout()
        start_layout.addWidget(QLabel("Start:"))
        self.crop_start_spin = QSpinBox()
        self.crop_start_spin.setRange(0, 999999)
        self.crop_start_spin.setValue(0)
        self.crop_start_spin.valueChanged.connect(self.update_plot)
        start_layout.addWidget(self.crop_start_spin)
        processing_layout.addLayout(start_layout)
        
        # End point
        end_layout = QHBoxLayout()
        end_layout.addWidget(QLabel("End:"))
        self.crop_end_spin = QSpinBox()
        self.crop_end_spin.setRange(0, 999999)
        self.crop_end_spin.setValue(999999)
        self.crop_end_spin.valueChanged.connect(self.update_plot)
        end_layout.addWidget(self.crop_end_spin)
        processing_layout.addLayout(end_layout)
        
        reset_crop_btn = QPushButton("Reset Crop")
        reset_crop_btn.clicked.connect(self.reset_crop)
        processing_layout.addWidget(reset_crop_btn)
        
        # Normalization
        self.normalize_check = QCheckBox("Normalize to 0-1")
        self.normalize_check.stateChanged.connect(self.update_plot)
        processing_layout.addWidget(self.normalize_check)
        
        # Y-axis offset
        offset_layout = QHBoxLayout()
        offset_layout.addWidget(QLabel("Y Offset:"))
        self.y_offset_spin = QDoubleSpinBox()
        self.y_offset_spin.setRange(-1e12, 1e12)
        self.y_offset_spin.setValue(0)
        self.y_offset_spin.setDecimals(2)
        self.y_offset_spin.setSingleStep(1.0)
        self.y_offset_spin.valueChanged.connect(self.update_plot)
        offset_layout.addWidget(self.y_offset_spin)
        processing_layout.addLayout(offset_layout)
        
        processing_group.setLayout(processing_layout)
        control_layout.addWidget(processing_group)
        
        # Axis Controls
        axis_group = QGroupBox("Axis Ranges")
        axis_layout = QVBoxLayout()
        
        # Auto-scale checkbox
        self.autoscale_check = QCheckBox("Auto Scale")
        self.autoscale_check.setChecked(True)
        self.autoscale_check.stateChanged.connect(self.toggle_axis_controls)
        axis_layout.addWidget(self.autoscale_check)
        
        # X-axis range
        x_label = QLabel("X-axis (Time):")
        x_label.setStyleSheet("font-weight: bold;")
        axis_layout.addWidget(x_label)
        
        x_min_layout = QHBoxLayout()
        x_min_layout.addWidget(QLabel("Min:"))
        self.x_min_spin = QDoubleSpinBox()
        self.x_min_spin.setRange(-1e12, 1e12)
        self.x_min_spin.setDecimals(3)
        self.x_min_spin.setValue(0)
        self.x_min_spin.setEnabled(False)
        self.x_min_spin.valueChanged.connect(self.apply_axis_ranges)
        x_min_layout.addWidget(self.x_min_spin)
        axis_layout.addLayout(x_min_layout)
        
        x_max_layout = QHBoxLayout()
        x_max_layout.addWidget(QLabel("Max:"))
        self.x_max_spin = QDoubleSpinBox()
        self.x_max_spin.setRange(-1e12, 1e12)
        self.x_max_spin.setDecimals(3)
        self.x_max_spin.setValue(100)
        self.x_max_spin.setEnabled(False)
        self.x_max_spin.valueChanged.connect(self.apply_axis_ranges)
        x_max_layout.addWidget(self.x_max_spin)
        axis_layout.addLayout(x_max_layout)
        
        # Y-axis range
        y_label = QLabel("Y-axis (Resistance):")
        y_label.setStyleSheet("font-weight: bold;")
        axis_layout.addWidget(y_label)
        
        y_min_layout = QHBoxLayout()
        y_min_layout.addWidget(QLabel("Min:"))
        self.y_min_spin = QDoubleSpinBox()
        self.y_min_spin.setRange(-1e12, 1e12)
        self.y_min_spin.setDecimals(2)
        self.y_min_spin.setValue(0)
        self.y_min_spin.setEnabled(False)
        self.y_min_spin.valueChanged.connect(self.apply_axis_ranges)
        y_min_layout.addWidget(self.y_min_spin)
        axis_layout.addLayout(y_min_layout)
        
        y_max_layout = QHBoxLayout()
        y_max_layout.addWidget(QLabel("Max:"))
        self.y_max_spin = QDoubleSpinBox()
        self.y_max_spin.setRange(-1e12, 1e12)
        self.y_max_spin.setDecimals(2)
        self.y_max_spin.setValue(1000)
        self.y_max_spin.setEnabled(False)
        self.y_max_spin.valueChanged.connect(self.apply_axis_ranges)
        y_max_layout.addWidget(self.y_max_spin)
        axis_layout.addLayout(y_max_layout)
        
        axis_group.setLayout(axis_layout)
        control_layout.addWidget(axis_group)
        
        # Export buttons
        export_group = QGroupBox("Export")
        export_layout = QVBoxLayout()
        
        # PNG with options
        png_layout = QHBoxLayout()
        save_png_btn = QPushButton("💾 PNG")
        save_png_btn.clicked.connect(lambda: self.export_plot('png', False))
        png_layout.addWidget(save_png_btn)
        
        save_png_trans_btn = QPushButton("PNG (Trans)")
        save_png_trans_btn.setToolTip("Save with transparent background")
        save_png_trans_btn.clicked.connect(lambda: self.export_plot('png', True))
        png_layout.addWidget(save_png_trans_btn)
        export_layout.addLayout(png_layout)
        
        # PDF with options
        pdf_layout = QHBoxLayout()
        save_pdf_btn = QPushButton("📄 PDF")
        save_pdf_btn.clicked.connect(lambda: self.export_plot('pdf', False))
        pdf_layout.addWidget(save_pdf_btn)
        
        save_pdf_trans_btn = QPushButton("PDF (Trans)")
        save_pdf_trans_btn.setToolTip("Save with transparent background")
        save_pdf_trans_btn.clicked.connect(lambda: self.export_plot('pdf', True))
        pdf_layout.addWidget(save_pdf_trans_btn)
        export_layout.addLayout(pdf_layout)
        
        # Data export
        save_data_btn = QPushButton("📊 Export Data (TXT)")
        save_data_btn.clicked.connect(self.export_data)
        export_layout.addWidget(save_data_btn)
        
        # Origin export (future)
        save_origin_btn = QPushButton("🔬 Export to Origin")
        save_origin_btn.setEnabled(False)
        save_origin_btn.setToolTip("Coming soon!")
        export_layout.addWidget(save_origin_btn)
        
        export_group.setLayout(export_layout)
        control_layout.addWidget(export_group)
        
        # Annotations section
        annotations_group = QGroupBox("Annotations")
        annotations_layout = QVBoxLayout()
        
        # Header with help button
        header_layout = QHBoxLayout()
        header_label = QLabel("Annotations")
        header_label.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(header_label)
        header_layout.addStretch()
        
        help_btn = QPushButton("?")
        help_btn.setMaximumWidth(25)
        help_btn.setMaximumHeight(25)
        help_btn.setToolTip("Annotation help")
        help_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a4a4a;
                color: #e0e0e0;
                border: 1px solid #666;
                border-radius: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #555;
            }
        """)
        help_btn.clicked.connect(self.show_annotation_help)
        header_layout.addWidget(help_btn)
        
        annotations_layout.addLayout(header_layout)
        
        self.annotation_toolbar = AnnotationToolbar()
        self.annotation_toolbar.annotation_added.connect(self.add_annotation)
        self.annotation_toolbar.remove_last_btn.clicked.connect(self.remove_last_annotation)
        self.annotation_toolbar.clear_btn.clicked.connect(self.clear_all_annotations)
        annotations_layout.addWidget(self.annotation_toolbar)
        
        # Click-to-add instructions
        click_label = QLabel("💡 Tip: Click on plot to set position")
        click_label.setStyleSheet("color: #888; font-size: 9pt; padding: 5px;")
        click_label.setWordWrap(True)
        annotations_layout.addWidget(click_label)
        
        annotations_group.setLayout(annotations_layout)
        control_layout.addWidget(annotations_group)
        
        # Statistics section
        stats_group = QGroupBox("Statistics")
        stats_layout = QVBoxLayout()
        
        # Header with help button
        stats_header_layout = QHBoxLayout()
        stats_header_label = QLabel("Statistics")
        stats_header_label.setStyleSheet("font-weight: bold;")
        stats_header_layout.addWidget(stats_header_label)
        stats_header_layout.addStretch()
        
        stats_help_btn = QPushButton("?")
        stats_help_btn.setMaximumWidth(25)
        stats_help_btn.setMaximumHeight(25)
        stats_help_btn.setToolTip("Statistics help")
        stats_help_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a4a4a;
                color: #e0e0e0;
                border: 1px solid #666;
                border-radius: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #555;
            }
        """)
        stats_help_btn.clicked.connect(self.show_statistics_help)
        stats_header_layout.addWidget(stats_help_btn)
        
        stats_layout.addLayout(stats_header_layout)
        
        # Show/Hide stats box on graph
        self.show_stats_box = QCheckBox("Show Stats on Graph")
        self.show_stats_box.setChecked(False)
        self.show_stats_box.stateChanged.connect(self.update_plot)
        stats_layout.addWidget(self.show_stats_box)
        
        # Stats box position
        stats_pos_layout = QHBoxLayout()
        stats_pos_layout.addWidget(QLabel("Position:"))
        self.stats_position_combo = QComboBox()
        self.stats_position_combo.addItems([
            "Upper Right", "Upper Left", "Lower Right", "Lower Left",
            "Center Right", "Center Left", "Upper Center", "Lower Center"
        ])
        self.stats_position_combo.setCurrentText("Upper Right")
        self.stats_position_combo.currentTextChanged.connect(self.update_plot)
        stats_pos_layout.addWidget(self.stats_position_combo)
        stats_layout.addLayout(stats_pos_layout)
        
        # Calculate stats button
        calc_stats_btn = QPushButton("📊 Calculate Statistics")
        calc_stats_btn.clicked.connect(self.calculate_statistics)
        stats_layout.addWidget(calc_stats_btn)
        
        # Checkboxes for which stats to show
        stats_layout.addWidget(QLabel("Display on Graph:"))
        
        self.stat_checkboxes = {}
        stat_options = [
            "Mean", "Median", "Std Dev", "Min", "Max", "Range",
            "Initial Value", "Final Value", "Total Change (ΔY)", "Percent Change (%)",
            "Tau (Relaxation Time)", "Tau R²", "Relaxation Type",
            "HRS Mean", "LRS Mean", "Switching Window", "On/Off Ratio"
        ]
        
        for stat_name in stat_options:
            cb = QCheckBox(stat_name)
            # Default checked: basic stats and relaxation time (if available)
            cb.setChecked(stat_name in ["Mean", "Std Dev", "Min", "Max", "Tau (Relaxation Time)", "Tau R²"])
            cb.stateChanged.connect(self.update_plot)
            self.stat_checkboxes[stat_name] = cb
            stats_layout.addWidget(cb)
        
        # Export stats button
        export_stats_btn = QPushButton("💾 Export Stats to CSV")
        export_stats_btn.clicked.connect(self.export_statistics)
        stats_layout.addWidget(export_stats_btn)
        
        stats_group.setLayout(stats_layout)
        control_layout.addWidget(stats_group)
        
        # Store calculated statistics
        self.calculated_stats = {}
        
        control_layout.addStretch()
        
        # Refresh button at bottom
        refresh_btn = QPushButton("🔄 Refresh Plot")
        refresh_btn.clicked.connect(self.update_plot)
        control_layout.addWidget(refresh_btn)
        
        # Set control panel into scroll area
        control_scroll.setWidget(control_panel)
        
        # Add to splitter
        splitter.addWidget(control_scroll)
        
        # Right panel: Plot canvas
        plot_panel = QWidget()
        plot_layout = QVBoxLayout(plot_panel)
        
        # Matplotlib figure
        self.figure = Figure(figsize=(10, 6))
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setStyleSheet("background-color: #2b2b2b;")
        
        # Connect canvas click events
        self.canvas.mpl_connect('button_press_event', self.on_plot_click)
        
        # Toolbar
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.toolbar.setStyleSheet("""
            QToolBar {
                background-color: #3c3c3c;
                border: 1px solid #555;
                spacing: 3px;
            }
            QToolButton {
                background-color: #4a4a4a;
                color: #e0e0e0;
                border: 1px solid #666;
                padding: 4px;
                border-radius: 3px;
            }
            QToolButton:hover {
                background-color: #555555;
            }
        """)
        
        plot_layout.addWidget(self.toolbar)
        plot_layout.addWidget(self.canvas, 1)
        
        # Status label
        self.status_label = QLabel("No data loaded")
        self.status_label.setStyleSheet("color: #888; padding: 5px;")
        plot_layout.addWidget(self.status_label)
        
        # Add plot panel to splitter
        splitter.addWidget(plot_panel)
        
        # Set initial splitter sizes (25% controls, 75% plot)
        splitter.setSizes([300, 1200])
        
        # Add splitter to main layout
        layout.addWidget(splitter)
    
    def load_datasets(self, datasets: List[TSPData]):
        """Load datasets for plotting"""
        self.datasets = datasets
        self.dataset_colors = []
        self.custom_labels = [None] * len(datasets)
        self.custom_samples = [None] * len(datasets)
        
        # Assign colors
        for i, data in enumerate(datasets):
            color = self.plot_generator.style.COLORS[i % len(self.plot_generator.style.COLORS)]
            self.dataset_colors.append(color)
        
        # Update dataset list
        self.dataset_list.clear()
        for i, data in enumerate(datasets):
            item = DatasetListItem(data, self.dataset_colors[i])
            self.dataset_list.addItem(item)
        
        # Update plot
        self.update_plot()
        
        # Update status
        self.status_label.setText(f"Loaded {len(datasets)} dataset(s)")
    
    def update_plot(self):
        """Redraw the plot with current settings"""
        if not self.datasets:
            self.status_label.setText("No data to plot")
            return
        
        # Clear figure
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        
        # Apply style settings
        self.plot_generator.style.line_width = self.line_width_spin.value()
        self.plot_generator.style.marker_size = self.marker_size_spin.value()
        self.plot_generator.style.grid = self.grid_check.isChecked()
        self.plot_generator.style.legend = self.legend_check.isChecked()
        
        self.plot_generator.style.apply_to_figure(self.figure)
        self.plot_generator.style.apply_to_axes(ax)
        
        # Initialize annotation manager (after axes exist)
        self.annotation_manager = AnnotationManager(ax)
        
        # Get crop range
        crop_start = self.crop_start_spin.value()
        crop_end = self.crop_end_spin.value()
        
        # Get normalization and offset settings
        normalize = self.normalize_check.isChecked()
        y_offset = self.y_offset_spin.value()
        
        # Plot each visible dataset
        visible_count = 0
        for i in range(self.dataset_list.count()):
            item = self.dataset_list.item(i)
            if isinstance(item, DatasetListItem) and item.visible:
                data = item.tsp_data
                color = item.color
                
                # Use custom label if available, otherwise generate default
                if self.custom_labels[i]:
                    label = self.custom_labels[i]
                else:
                    # Use custom sample if available
                    if self.custom_samples[i]:
                        label = f"{self.custom_samples[i]} - {data.filename}"
                    else:
                        label = data.get_display_name()
                    
                    # Add key parameters to label (only if not custom)
                    key_params = data.get_key_parameters()
                    if key_params and not self.custom_labels[i]:
                        label += f" ({key_params})"
                
                # Apply data processing
                processed_data = self.process_data(data, crop_start, crop_end, normalize, y_offset)
                
                self.plot_generator.plot_single(processed_data, self.figure, ax, color, label)
                visible_count += 1
        
        # Apply log scale if checked
        if self.log_scale_check.isChecked():
            ax.set_yscale('log')
        
        # Update legend
        if self.legend_check.isChecked() and visible_count > 0:
            legend = ax.legend(facecolor=self.plot_generator.style.bg_color,
                             edgecolor=self.plot_generator.style.text_color,
                             labelcolor=self.plot_generator.style.text_color)
            legend.get_frame().set_alpha(0.9)
        
        # Add statistics box if enabled
        if self.show_stats_box.isChecked() and self.calculated_stats:
            self.draw_statistics_box(ax)
        
        self.figure.tight_layout()
        
        # Apply manual axis ranges if not auto-scaling
        if not self.autoscale_check.isChecked():
            self.apply_axis_ranges()
        
        self.canvas.draw()
        
        self.status_label.setText(f"Showing {visible_count} of {len(self.datasets)} dataset(s)")
    
    def toggle_dataset_visibility(self, item: QListWidgetItem):
        """Toggle visibility of a dataset"""
        if isinstance(item, DatasetListItem):
            item.visible = not item.visible
            item.update_display()
            self.update_plot()
    
    def remove_selected_dataset(self):
        """Remove selected dataset"""
        current_row = self.dataset_list.currentRow()
        if current_row >= 0:
            self.dataset_list.takeItem(current_row)
            del self.datasets[current_row]
            del self.dataset_colors[current_row]
            self.update_plot()
    
    def edit_labels(self):
        """Open label editor dialog"""
        if not self.datasets:
            QMessageBox.information(self, "No Data", "Load datasets first to edit labels.")
            return
        
        # Create and show dialog
        dialog = LabelEditorDialog(self.datasets, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Get custom data
            self.custom_labels, self.custom_samples = dialog.get_custom_data()
            
            # Update plot with new labels
            self.update_plot()
            
            QMessageBox.information(self, "Success", "Labels updated!")
    
    def clear_all_datasets(self):
        """Clear all datasets"""
        reply = QMessageBox.question(
            self,
            "Clear All",
            "Remove all datasets from plot?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.datasets.clear()
            self.dataset_colors.clear()
            self.custom_labels.clear()
            self.custom_samples.clear()
            self.dataset_list.clear()
            self.figure.clear()
            self.canvas.draw()
            self.status_label.setText("No data loaded")
    
    def change_background_color(self):
        """Change plot background color"""
        # Get current color
        current_color = QColor(self.plot_generator.style.bg_color)
        
        # Show color picker
        color = QColorDialog.getColor(current_color, self, "Select Background Color")
        
        if color.isValid():
            hex_color = color.name()
            
            # Update style
            self.plot_generator.style.bg_color = hex_color
            
            # Adjust text color based on background brightness
            brightness = (color.red() * 299 + color.green() * 587 + color.blue() * 114) / 1000
            if brightness > 128:
                # Light background, use dark text
                self.plot_generator.style.text_color = '#2b2b2b'
                self.plot_generator.style.grid_color = '#cccccc'
                self.bg_color_btn.setText("Light")
            else:
                # Dark background, use light text
                self.plot_generator.style.text_color = '#e0e0e0'
                self.plot_generator.style.grid_color = '#555555'
                self.bg_color_btn.setText("Dark")
            
            # Update plot
            self.update_plot()
    
    def toggle_axis_controls(self):
        """Enable/disable manual axis range controls"""
        enabled = not self.autoscale_check.isChecked()
        self.x_min_spin.setEnabled(enabled)
        self.x_max_spin.setEnabled(enabled)
        self.y_min_spin.setEnabled(enabled)
        self.y_max_spin.setEnabled(enabled)
        self.update_plot()
    
    def apply_axis_ranges(self):
        """Apply manual axis ranges to plot"""
        if self.figure.axes and not self.autoscale_check.isChecked():
            ax = self.figure.axes[0]
            try:
                ax.set_xlim(self.x_min_spin.value(), self.x_max_spin.value())
                ax.set_ylim(self.y_min_spin.value(), self.y_max_spin.value())
                self.canvas.draw()
            except Exception as e:
                print(f"Error setting axis ranges: {e}")
    
    def reset_crop(self):
        """Reset crop range to full data"""
        self.crop_start_spin.setValue(0)
        self.crop_end_spin.setValue(999999)
        self.update_plot()
    
    def process_data(self, data: TSPData, crop_start: int, crop_end: int, 
                    normalize: bool, y_offset: float) -> TSPData:
        """
        Process data with cropping, normalization, and offset.
        Returns a modified copy of the data.
        """
        import copy
        import numpy as np
        
        # Create a copy
        processed = copy.deepcopy(data)
        
        # Apply cropping
        if crop_start > 0 or crop_end < len(data.timestamps):
            end_idx = min(crop_end, len(data.timestamps))
            start_idx = min(crop_start, end_idx)
            
            processed.timestamps = data.timestamps[start_idx:end_idx]
            processed.voltages = data.voltages[start_idx:end_idx]
            processed.currents = data.currents[start_idx:end_idx]
            processed.resistances = data.resistances[start_idx:end_idx]
            processed.measurement_numbers = data.measurement_numbers[start_idx:end_idx]
            
            # Process additional data columns
            for key in data.additional_data:
                if len(data.additional_data[key]) == len(data.timestamps):
                    processed.additional_data[key] = data.additional_data[key][start_idx:end_idx]
        
        # Apply normalization (to resistance only)
        if normalize and len(processed.resistances) > 0:
            r_min = np.nanmin(processed.resistances)
            r_max = np.nanmax(processed.resistances)
            if r_max > r_min:
                processed.resistances = (processed.resistances - r_min) / (r_max - r_min)
        
        # Apply offset (to resistance only)
        if y_offset != 0:
            processed.resistances = processed.resistances + y_offset
        
        return processed
    
    def export_plot(self, format: str, transparent: bool = False):
        """Export plot to file"""
        if not self.datasets:
            QMessageBox.warning(self, "No Data", "No data to export!")
            return
        
        # Get save location
        trans_suffix = "_transparent" if transparent else ""
        default_name = f"tsp_plot{trans_suffix}.{format}"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Save Plot as {format.upper()}" + (" (Transparent)" if transparent else ""),
            default_name,
            f"{format.upper()} Files (*.{format});;All Files (*.*)"
        )
        
        if file_path:
            try:
                dpi = 300 if format == 'png' else 150
                
                if transparent:
                    # Save with transparent background
                    original_bg = self.figure.get_facecolor()
                    original_ax_bg = self.figure.axes[0].get_facecolor() if self.figure.axes else None
                    
                    # Set transparent
                    self.figure.patch.set_facecolor('none')
                    if self.figure.axes:
                        self.figure.axes[0].patch.set_facecolor('none')
                    
                    # Save
                    self.figure.savefig(file_path, dpi=dpi, transparent=True, bbox_inches='tight')
                    
                    # Restore original colors
                    self.figure.patch.set_facecolor(original_bg)
                    if self.figure.axes and original_ax_bg:
                        self.figure.axes[0].patch.set_facecolor(original_ax_bg)
                else:
                    # Save with current background
                    self.plot_generator.save_figure(self.figure, Path(file_path), dpi=dpi)
                
                QMessageBox.information(self, "Success", f"Plot saved to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save plot:\n{e}")
    
    def export_data(self):
        """Export data to text file with proper column format"""
        if not self.datasets:
            QMessageBox.warning(self, "No Data", "No data to export!")
            return
        
        # Get visible datasets only
        visible_datasets = []
        for i in range(self.dataset_list.count()):
            item = self.dataset_list.item(i)
            if isinstance(item, DatasetListItem) and item.visible:
                visible_datasets.append(item.tsp_data)
        
        if not visible_datasets:
            QMessageBox.warning(self, "No Visible Data", "No visible datasets to export!")
            return
        
        # Get save location
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Data as TXT",
            "tsp_data_export.txt",
            "Text Files (*.txt);;All Files (*.*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    # Prepare column headers, units, and comments
                    headers = []
                    units = []
                    comments = []
                    
                    # Build column info for each visible dataset
                    for tsp_data in visible_datasets:
                        # Determine X and Y column names
                        if 'Time (s)' in tsp_data.data:
                            x_col = 'Time (s)'
                            x_unit = 's'
                        elif 'Voltage (V)' in tsp_data.data:
                            x_col = 'Voltage (V)'
                            x_unit = 'V'
                        else:
                            x_col = list(tsp_data.data.keys())[0] if tsp_data.data else 'X'
                            x_unit = ''
                        
                        if 'Resistance (Ohms)' in tsp_data.data:
                            y_col = 'Resistance (Ohms)'
                            y_unit = 'Ω'
                        elif 'Current (A)' in tsp_data.data:
                            y_col = 'Current (A)'
                            y_unit = 'A'
                        else:
                            # Find the Y column (usually second column)
                            cols = list(tsp_data.data.keys())
                            y_col = cols[1] if len(cols) > 1 else 'Y'
                            y_unit = ''
                        
                        # Get custom label or generate default
                        dataset_idx = self.datasets.index(tsp_data)
                        if self.custom_labels[dataset_idx]:
                            label = self.custom_labels[dataset_idx]
                        else:
                            if self.custom_samples[dataset_idx]:
                                label = self.custom_samples[dataset_idx]
                            else:
                                label = f"{tsp_data.sample}_{tsp_data.device}"
                        
                        # Add columns for this dataset
                        headers.append(f"{x_col} ({label})")
                        headers.append(f"{y_col} ({label})")
                        
                        units.append(x_unit)
                        units.append(y_unit)
                        
                        # Build comment with useful metadata
                        comment_parts = [f"{label}"]
                        
                        # Add test type
                        test_type = tsp_data.metadata.get('Test Type', 'Unknown')
                        comment_parts.append(f"Test: {test_type}")
                        
                        # Add key parameters from metadata
                        if 'Pulse Width (s)' in tsp_data.metadata:
                            pw = tsp_data.metadata['Pulse Width (s)']
                            # Convert to microseconds if small
                            if pw < 1e-3:
                                comment_parts.append(f"PW: {pw*1e6:.1f}µs")
                            else:
                                comment_parts.append(f"PW: {pw:.6f}s")
                        
                        if 'Pulse Voltage (V)' in tsp_data.metadata:
                            pv = tsp_data.metadata['Pulse Voltage (V)']
                            comment_parts.append(f"PV: {pv}V")
                        
                        if 'Read Voltage (V)' in tsp_data.metadata:
                            rv = tsp_data.metadata['Read Voltage (V)']
                            comment_parts.append(f"RV: {rv}V")
                        
                        if 'Number of Pulses' in tsp_data.metadata:
                            np_val = tsp_data.metadata['Number of Pulses']
                            comment_parts.append(f"N: {np_val}")
                        
                        if 'Delay (s)' in tsp_data.metadata:
                            delay = tsp_data.metadata['Delay (s)']
                            if delay < 1e-3:
                                comment_parts.append(f"Delay: {delay*1e6:.1f}µs")
                            else:
                                comment_parts.append(f"Delay: {delay:.6f}s")
                        
                        # Create comment (2 columns wide)
                        full_comment = ", ".join(comment_parts)
                        comments.append(full_comment)
                        comments.append("")  # Empty for second column
                    
                    # Write header row
                    f.write("\t".join(headers) + "\n")
                    
                    # Write units row
                    f.write("\t".join(units) + "\n")
                    
                    # Write comments row
                    f.write("\t".join(comments) + "\n")
                    
                    # Prepare data columns
                    data_columns = []
                    max_rows = 0
                    
                    for tsp_data in visible_datasets:
                        # Get X and Y data
                        if 'Time (s)' in tsp_data.data:
                            x_data = tsp_data.data['Time (s)']
                        elif 'Voltage (V)' in tsp_data.data:
                            x_data = tsp_data.data['Voltage (V)']
                        else:
                            x_data = list(tsp_data.data.values())[0] if tsp_data.data else []
                        
                        if 'Resistance (Ohms)' in tsp_data.data:
                            y_data = tsp_data.data['Resistance (Ohms)']
                        elif 'Current (A)' in tsp_data.data:
                            y_data = tsp_data.data['Current (A)']
                        else:
                            cols = list(tsp_data.data.values())
                            y_data = cols[1] if len(cols) > 1 else []
                        
                        # Convert to numpy arrays for processing
                        x_data = np.array(x_data, dtype=float)
                        y_data = np.array(y_data, dtype=float)
                        
                        # Apply data processing
                        x_data, y_data = self.process_data(x_data, y_data)
                        
                        data_columns.append(x_data)
                        data_columns.append(y_data)
                        
                        max_rows = max(max_rows, len(x_data))
                    
                    # Write data rows
                    for row_idx in range(max_rows):
                        row_values = []
                        for col in data_columns:
                            if row_idx < len(col):
                                # Format with appropriate precision
                                value = col[row_idx]
                                if abs(value) < 1e-10 and value != 0:
                                    row_values.append(f"{value:.6e}")
                                elif abs(value) > 1e6:
                                    row_values.append(f"{value:.6e}")
                                else:
                                    row_values.append(f"{value:.8f}")
                            else:
                                row_values.append("")  # Empty if this dataset is shorter
                        
                        f.write("\t".join(row_values) + "\n")
                
                QMessageBox.information(self, "Success", f"Data exported to:\n{file_path}\n\n"
                                      f"Exported {len(visible_datasets)} visible dataset(s)")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export data:\n{e}")
    
    def on_plot_click(self, event):
        """Handle clicks on the plot canvas"""
        if event.inaxes is None or event.button != 1:  # Left click only
            return
        
        # Update position in annotation toolbar
        self.annotation_toolbar.set_position(event.xdata, event.ydata)
        
        # If adding arrow and already have start point, set end point
        if self.annotation_toolbar.current_type == 'arrow':
            # Toggle between start and end
            if self.annotation_toolbar.x2_spin.value() == 0:
                self.annotation_toolbar.set_arrow_end_position(event.xdata, event.ydata)
    
    def add_annotation(self, ann_type: str, params: dict):
        """Add annotation to plot"""
        if not self.annotation_manager or not self.figure.axes:
            QMessageBox.warning(self, "No Plot", "Create a plot first!")
            return
        
        try:
            x = params['x']
            y = params['y']
            color = params['color']
            
            if ann_type == 'text_box':
                text = params.get('text', 'Annotation')
                fontsize = params.get('fontsize', 12)
                bbox = params.get('bbox', True)
                self.annotation_manager.add_text(x, y, text, color, fontsize, bbox)
                
            elif ann_type == 'arrow':
                x2 = params.get('x2', x + 0.1)
                y2 = params.get('y2', y + 0.1)
                style = params.get('style', '->')
                lw = params.get('linewidth', 2.0)
                self.annotation_manager.add_arrow(x, y, x2, y2, color, style, lw)
                
            elif ann_type == 'circle':
                radius = params.get('radius', 0.1)
                fill = params.get('fill', False)
                lw = params.get('linewidth', 2.0)
                self.annotation_manager.add_circle(x, y, radius, color, fill, lw)
                
            elif ann_type == 'rectangle':
                width = params.get('width', 0.2)
                height = params.get('height', 0.1)
                fill = params.get('fill', False)
                lw = params.get('linewidth', 2.0)
                self.annotation_manager.add_rectangle(x, y, width, height, color, fill, lw)
            
            self.canvas.draw()
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to add annotation:\n{e}")
    
    def remove_last_annotation(self):
        """Remove last added annotation"""
        if self.annotation_manager:
            if self.annotation_manager.remove_last():
                self.canvas.draw()
            else:
                QMessageBox.information(self, "No Annotations", "No annotations to remove.")
    
    def clear_all_annotations(self):
        """Clear all annotations"""
        if self.annotation_manager:
            reply = QMessageBox.question(
                self,
                "Clear All Annotations",
                "Remove all annotations from plot?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.annotation_manager.clear_all()
                self.canvas.draw()
    
    def show_annotation_help(self):
        """Show help dialog for annotations"""
        help_text = """
<h3>How to Add Annotations</h3>

<p><b>1. Choose Annotation Type:</b></p>
<ul>
  <li><b>Text Box:</b> Add text labels (optional background box)</li>
  <li><b>Arrow:</b> Point to specific features</li>
  <li><b>Circle:</b> Highlight regions of interest</li>
  <li><b>Rectangle:</b> Mark areas of interest</li>
</ul>

<p><b>2. Set Position:</b></p>
<ul>
  <li><b>Method 1:</b> Click directly on the plot where you want the annotation</li>
  <li><b>Method 2:</b> Type X and Y coordinates in the position fields</li>
  <li>For arrows: Click start point, then click end point (or enter X2/Y2)</li>
</ul>

<p><b>3. Customize:</b></p>
<ul>
  <li>Choose annotation color (click "Color" button)</li>
  <li>Adjust size/radius/width/height for shapes</li>
  <li>Toggle fill options for circles/rectangles</li>
  <li>Adjust font size and box for text</li>
</ul>

<p><b>4. Add:</b></p>
<ul>
  <li>Click <b>"➕ Add Annotation"</b> button</li>
  <li>Annotation appears on plot immediately</li>
</ul>

<p><b>Tips:</b></p>
<ul>
  <li>💡 <b>Click on plot</b> to auto-fill position coordinates</li>
  <li>🔄 Use <b>"Remove Last"</b> to undo mistakes</li>
  <li>🗑️ Use <b>"Clear All"</b> to remove all annotations</li>
  <li>📊 Annotations are saved when you export the plot</li>
  <li>⚙️ Adjust position values to fine-tune placement</li>
</ul>

<p><b>Example Workflow:</b></p>
<ol>
  <li>Click on plot where you want an arrow to point</li>
  <li>Select "Arrow" type</li>
  <li>Adjust X2/Y2 for end position (or click plot again)</li>
  <li>Choose arrow style and color</li>
  <li>Click "Add Annotation"</li>
</ol>
        """
        
        QMessageBox.information(
            self,
            "Annotation Help",
            help_text
        )
    
    def show_statistics_help(self):
        """Show help dialog for statistics"""
        help_text = """
<h3>How to Use Statistics</h3>

<p><b>1. Calculate Statistics:</b></p>
<ul>
  <li>Click <b>"📊 Calculate Statistics"</b> button</li>
  <li>Stats are calculated for all visible datasets</li>
  <li>Relaxation time fitting is automatic for relaxation tests</li>
</ul>

<p><b>2. Display on Graph:</b></p>
<ul>
  <li>Check <b>"Show Stats on Graph"</b> to display stats box</li>
  <li>Select which statistics to display using checkboxes</li>
  <li>Choose position (Upper Right, Lower Left, etc.)</li>
  <li>Stats box updates automatically when you change selections</li>
</ul>

<p><b>Available Statistics:</b></p>
<ul>
  <li><b>Basic:</b> Mean, Median, Std Dev, Min, Max, Range</li>
  <li><b>Change:</b> Initial Value, Final Value, Total Change, Percent Change</li>
  <li><b>Relaxation:</b> Tau (time constant), R² (fit quality)</li>
  <li><b>Switching:</b> HRS/LRS Mean, Switching Window, On/Off Ratio</li>
</ul>

<p><b>Export Statistics:</b></p>
<ul>
  <li>Click <b>"💾 Export Stats to CSV"</b> to save all statistics</li>
  <li>Exports stats for all visible datasets</li>
  <li>Opens in Excel or any spreadsheet software</li>
</ul>

<p><b>Tips:</b></p>
<ul>
  <li>📊 Recalculate stats after changing axis ranges or processing data</li>
  <li>🎯 Use relaxation time for exponential decay/growth analysis</li>
  <li>📈 HRS/LRS stats are useful for endurance and switching tests</li>
  <li>💡 Stats box can be repositioned to avoid overlapping with data</li>
</ul>
        """
        
        QMessageBox.information(
            self,
            "Statistics Help",
            help_text
        )
    
    def calculate_statistics(self):
        """Calculate statistics for all visible datasets"""
        if not hasattr(self, 'datasets') or not self.datasets:
            QMessageBox.warning(
                self,
                "No Data",
                "No datasets loaded. Please select files first."
            )
            return
        
        # Clear previous stats
        self.calculated_stats = {}
        
        # Get visible datasets
        visible_datasets = []
        for i in range(self.dataset_list.count()):
            item = self.dataset_list.item(i)
            if isinstance(item, DatasetListItem) and item.visible:
                visible_datasets.append(item.tsp_data)
        
        if not visible_datasets:
            QMessageBox.warning(
                self,
                "No Visible Data",
                "No visible datasets. Please make datasets visible first."
            )
            return
        
        # Calculate stats for each dataset
        for tsp_data in visible_datasets:
            # Apply data processing first (gets processed TSPData object)
            crop_start = self.crop_start_spin.value()
            crop_end = self.crop_end_spin.value()
            normalize = self.normalize_check.isChecked()
            y_offset = self.y_offset_spin.value()
            
            processed_data = self.process_data(tsp_data, crop_start, crop_end, normalize, y_offset)
            
            # Get X and Y data from processed TSPData object
            # Determine X axis (time or voltage)
            if len(processed_data.timestamps) > 0:
                x_data = processed_data.timestamps
            elif len(processed_data.voltages) > 0:
                x_data = processed_data.voltages
            else:
                continue  # Skip if no X data
            
            # Determine Y axis (resistance or current)
            # Check test type to determine what to plot
            test_type = processed_data.test_name.lower()
            if 'iv' in test_type or 'sweep' in test_type:
                # IV sweep uses current
                y_data = processed_data.currents if len(processed_data.currents) > 0 else []
            else:
                # Most tests use resistance
                y_data = processed_data.resistances if len(processed_data.resistances) > 0 else []
            
            if len(x_data) == 0 or len(y_data) == 0:
                continue
            
            # Convert to numpy arrays (in case they're not already)
            x_data = np.array(x_data, dtype=float)
            y_data = np.array(y_data, dtype=float)
            
            # Remove NaN values
            valid_mask = ~(np.isnan(x_data) | np.isnan(y_data))
            x_data = x_data[valid_mask]
            y_data = y_data[valid_mask]
            
            if len(x_data) == 0 or len(y_data) == 0:
                continue
            
            # Create statistics calculator
            label = processed_data.get_display_name()
            test_type = processed_data.test_name
            
            stats_calc = DataStatistics(x_data, y_data, label, test_type)
            
            # Determine which stats to calculate
            # Check for relaxation tests - look for 'relaxation' in test type or check data trend
            test_type_lower = test_type.lower()
            include_relaxation = 'relaxation' in test_type_lower
            
            # Also check if data shows exponential decay/growth pattern (for manual relaxation calculations)
            # If user wants to calculate relaxation time for any dataset, we'll try it
            # The fit will fail gracefully if it's not exponential
            include_hrs_lrs = any(keyword in test_type_lower 
                                  for keyword in ['endurance', 'potentiation', 'depression', 'switching'])
            
            # Calculate all stats
            stats = stats_calc.all_stats(
                include_relaxation=include_relaxation,
                include_hrs_lrs=include_hrs_lrs
            )
            
            self.calculated_stats[label] = stats
        
        # Update plot to show stats box if enabled
        self.update_plot()
        
        # Show success message
        QMessageBox.information(
            self,
            "Statistics Calculated",
            f"Statistics calculated for {len(self.calculated_stats)} dataset(s).\n\n"
            f"Enable 'Show Stats on Graph' to display them on the plot."
        )
    
    def export_statistics(self):
        """Export statistics to CSV file"""
        if not self.calculated_stats:
            QMessageBox.warning(
                self,
                "No Statistics",
                "No statistics calculated. Click 'Calculate Statistics' first."
            )
            return
        
        # Open file dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Statistics",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if not file_path:
            return
        
        # Ensure .csv extension
        if not file_path.endswith('.csv'):
            file_path += '.csv'
        
        try:
            # Write CSV
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                # Get all unique stat names
                all_stat_names = set()
                for stats in self.calculated_stats.values():
                    all_stat_names.update(stats.keys())
                all_stat_names = sorted(all_stat_names)
                
                # Write header
                f.write("Dataset," + ",".join(all_stat_names) + "\n")
                
                # Write data
                for label, stats in self.calculated_stats.items():
                    f.write(f'"{label}"')
                    for stat_name in all_stat_names:
                        value = stats.get(stat_name, np.nan)
                        if isinstance(value, (int, float)):
                            f.write(f",{value}")
                        else:
                            f.write(f',"{value}"')
                    f.write("\n")
            
            QMessageBox.information(
                self,
                "Export Successful",
                f"Statistics exported to:\n{file_path}"
            )
        
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Failed",
                f"Failed to export statistics:\n{str(e)}"
            )
    
    def draw_statistics_box(self, ax):
        """Draw statistics text box on the plot"""
        if not self.calculated_stats:
            return
        
        # Build statistics text
        stats_text = ""
        
        # For each visible dataset
        for i in range(self.dataset_list.count()):
            item = self.dataset_list.item(i)
            if isinstance(item, DatasetListItem) and item.visible:
                label = item.tsp_data.get_display_name()
                
                # Check if we have stats for this dataset
                if label not in self.calculated_stats:
                    continue
                
                stats = self.calculated_stats[label]
                
                # Add dataset label
                if stats_text:
                    stats_text += "\n"  # Separator between datasets
                stats_text += f"{label}:\n"
                
                # Add selected statistics
                for stat_name, checkbox in self.stat_checkboxes.items():
                    if checkbox.isChecked() and stat_name in stats:
                        value = stats[stat_name]
                        formatted = format_stat_value(stat_name, value, precision=3)
                        stats_text += f"  {formatted}\n"
        
        if not stats_text:
            return
        
        # Map position names to matplotlib location codes
        position_map = {
            "Upper Right": "upper right",
            "Upper Left": "upper left",
            "Lower Right": "lower right",
            "Lower Left": "lower left",
            "Center Right": "center right",
            "Center Left": "center left",
            "Upper Center": "upper center",
            "Lower Center": "lower center"
        }
        
        position = self.stats_position_combo.currentText()
        loc = position_map.get(position, "upper right")
        
        # Create text box
        from matplotlib.patches import FancyBboxPatch
        
        # Add text with box
        text_props = dict(
            boxstyle='round,pad=0.5',
            facecolor=self.plot_generator.style.bg_color,
            edgecolor=self.plot_generator.style.text_color,
            alpha=0.9,
            linewidth=1.5
        )
        
        # Add text to plot
        ax.text(
            0.02 if 'left' in loc.lower() else 0.98,
            0.98 if 'upper' in loc.lower() else 0.02,
            stats_text.strip(),
            transform=ax.transAxes,
            fontsize=8,
            verticalalignment='top' if 'upper' in loc.lower() else 'bottom',
            horizontalalignment='left' if 'left' in loc.lower() else 'right',
            bbox=text_props,
            color=self.plot_generator.style.text_color,
            family='monospace'
        )

