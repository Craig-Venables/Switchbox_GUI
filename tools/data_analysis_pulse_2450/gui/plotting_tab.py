"""
Plotting Tab

Interactive plotting tab with matplotlib canvas and controls.
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                              QLabel, QGroupBox, QComboBox, QCheckBox,
                              QSpinBox, QDoubleSpinBox, QColorDialog, QFileDialog,
                              QScrollArea, QFrame, QSplitter, QListWidget,
                              QListWidgetItem, QMessageBox, QTextEdit, QMenu)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from pathlib import Path
from typing import List, Optional
import sys

# Matplotlib imports
import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.axes import Axes

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
        self.dataset_list.itemSelectionChanged.connect(self.on_dataset_selection_changed)
        dataset_layout.addWidget(QLabel("Double-click to show/hide | Right-click for menu:"))
        dataset_layout.addWidget(self.dataset_list, 1)
        
        # Enable context menu
        self.dataset_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.dataset_list.customContextMenuRequested.connect(self.show_dataset_context_menu)
        
        # Dataset controls
        ds_buttons = QHBoxLayout()
        
        self.view_details_btn = QPushButton("ℹ️ View Details")
        self.view_details_btn.clicked.connect(self.view_dataset_details)
        self.view_details_btn.setToolTip("View detailed information about selected dataset")
        self.view_details_btn.setEnabled(False)  # Disabled until a dataset is selected
        ds_buttons.addWidget(self.view_details_btn)
        
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
        
        # Multi-Panel Layout
        layout_group = QGroupBox("📐 Multi-Panel Layout")
        layout_group_layout = QVBoxLayout()
        
        # Layout selection
        layout_select_layout = QHBoxLayout()
        layout_select_layout.addWidget(QLabel("Layout:"))
        self.layout_combo = QComboBox()
        self.layout_combo.addItems([
            "Single Panel (1×1) - All Overlaid",
            "2 Panels (2×1)", 
            "2 Panels (1×2)",
            "4 Panels (2×2)",
            "6 Panels (3×2)",
            "9 Panels (3×3)"
        ])
        self.layout_combo.setCurrentIndex(0)
        self.layout_combo.currentIndexChanged.connect(self.on_layout_changed)
        self.layout_combo.setToolTip("Single Panel: All datasets on same graph. Multi-Panel: Split into separate panels")
        layout_select_layout.addWidget(self.layout_combo)
        layout_group_layout.addLayout(layout_select_layout)
        
        # Panel assignment button (only enabled for multi-panel)
        self.assign_panels_btn = QPushButton("📋 Assign Datasets to Panels")
        self.assign_panels_btn.setEnabled(False)
        self.assign_panels_btn.setToolTip("Manually assign which dataset goes to which panel")
        self.assign_panels_btn.clicked.connect(self.show_panel_assignment_dialog)
        layout_group_layout.addWidget(self.assign_panels_btn)
        
        # Shared axes option
        self.shared_axes_check = QCheckBox("Share Axes Between Panels")
        self.shared_axes_check.setChecked(False)
        self.shared_axes_check.setToolTip("Use same axis ranges for all panels")
        self.shared_axes_check.setEnabled(False)
        self.shared_axes_check.stateChanged.connect(self.update_plot)
        layout_group_layout.addWidget(self.shared_axes_check)
        
        # Panel assignment info
        self.layout_info_label = QLabel("💡 All datasets shown together on same graph")
        self.layout_info_label.setStyleSheet("color: #888; font-size: 9pt; padding: 3px;")
        self.layout_info_label.setWordWrap(True)
        layout_group_layout.addWidget(self.layout_info_label)
        
        # Store panel assignments: {dataset_index: panel_index}
        self.panel_assignments = {}
        
        layout_group.setLayout(layout_group_layout)
        control_layout.addWidget(layout_group)
        
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
        
        # Show difference for endurance tests
        self.show_difference_check = QCheckBox("Show R_off - R_on (Endurance)")
        self.show_difference_check.setToolTip("Plot the difference between RESET and SET resistances for endurance tests")
        self.show_difference_check.stateChanged.connect(self.update_plot)
        settings_layout.addWidget(self.show_difference_check)
        
        # Endurance: which state uses one fixed colour (the other varies per dataset)
        endurance_color_layout = QHBoxLayout()
        endurance_color_layout.addWidget(QLabel("Same colour for:"))
        self.endurance_fixed_combo = QComboBox()
        self.endurance_fixed_combo.addItems(["HRS (RESET)", "LRS (SET)"])
        self.endurance_fixed_combo.setToolTip(
            "HRS (RESET): all high-resistance lines same colour; LRS varies per dataset.\n"
            "LRS (SET): all low-resistance lines same colour; HRS varies per dataset.")
        self.endurance_fixed_combo.currentTextChanged.connect(self.update_plot)
        endurance_color_layout.addWidget(self.endurance_fixed_combo)
        settings_layout.addLayout(endurance_color_layout)
        
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
        
        # Data Smoothing
        smoothing_label = QLabel("Data Smoothing:")
        smoothing_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        processing_layout.addWidget(smoothing_label)
        
        # Smoothing method
        smooth_method_layout = QHBoxLayout()
        smooth_method_layout.addWidget(QLabel("Method:"))
        self.smoothing_method_combo = QComboBox()
        self.smoothing_method_combo.addItems([
            "None",
            "Moving Average",
            "Savitzky-Golay",
            "Gaussian Filter"
        ])
        self.smoothing_method_combo.setCurrentIndex(0)
        self.smoothing_method_combo.currentTextChanged.connect(self.update_smoothing_controls)
        self.smoothing_method_combo.currentTextChanged.connect(self.update_plot)
        smooth_method_layout.addWidget(self.smoothing_method_combo)
        processing_layout.addLayout(smooth_method_layout)
        
        # Window size (for Moving Average and Savitzky-Golay)
        smooth_window_layout = QHBoxLayout()
        smooth_window_layout.addWidget(QLabel("Window Size:"))
        self.smoothing_window_spin = QSpinBox()
        self.smoothing_window_spin.setRange(3, 101)
        self.smoothing_window_spin.setValue(5)
        self.smoothing_window_spin.setSingleStep(2)
        self.smoothing_window_spin.setToolTip("Number of points to average (must be odd for Savitzky-Golay)")
        self.smoothing_window_spin.valueChanged.connect(self.ensure_odd_window_size)
        self.smoothing_window_spin.valueChanged.connect(self.update_plot)
        smooth_window_layout.addWidget(self.smoothing_window_spin)
        processing_layout.addLayout(smooth_window_layout)
        
        # Polynomial order (for Savitzky-Golay)
        smooth_poly_layout = QHBoxLayout()
        smooth_poly_layout.addWidget(QLabel("Polynomial Order:"))
        self.smoothing_poly_spin = QSpinBox()
        self.smoothing_poly_spin.setRange(1, 5)
        self.smoothing_poly_spin.setValue(2)
        self.smoothing_poly_spin.setToolTip("Polynomial order for Savitzky-Golay filter (typically 2-3)")
        self.smoothing_poly_spin.valueChanged.connect(self.update_plot)
        smooth_poly_layout.addWidget(self.smoothing_poly_spin)
        processing_layout.addLayout(smooth_poly_layout)
        
        # Sigma (for Gaussian filter)
        smooth_sigma_layout = QHBoxLayout()
        smooth_sigma_layout.addWidget(QLabel("Sigma (σ):"))
        self.smoothing_sigma_spin = QDoubleSpinBox()
        self.smoothing_sigma_spin.setRange(0.1, 10.0)
        self.smoothing_sigma_spin.setValue(1.0)
        self.smoothing_sigma_spin.setDecimals(2)
        self.smoothing_sigma_spin.setSingleStep(0.1)
        self.smoothing_sigma_spin.setToolTip("Standard deviation for Gaussian filter (higher = more smoothing)")
        self.smoothing_sigma_spin.valueChanged.connect(self.update_plot)
        smooth_sigma_layout.addWidget(self.smoothing_sigma_spin)
        processing_layout.addLayout(smooth_sigma_layout)
        
        # Initially hide smoothing controls
        self.smoothing_window_spin.setEnabled(False)
        self.smoothing_poly_spin.setEnabled(False)
        self.smoothing_sigma_spin.setEnabled(False)
        
        # Smoothing info label
        smoothing_info_label = QLabel("💡 Smoothing reduces noise in noisy datasets")
        smoothing_info_label.setStyleSheet("color: #888; font-size: 9pt; padding: 3px;")
        smoothing_info_label.setWordWrap(True)
        processing_layout.addWidget(smoothing_info_label)
        
        processing_group.setLayout(processing_layout)
        control_layout.addWidget(processing_group)
        
        # Axis Configuration (what to plot on each axis)
        axis_config_group = QGroupBox("Axis Configuration")
        axis_config_layout = QVBoxLayout()
        
        # X-axis selection
        x_axis_layout = QHBoxLayout()
        x_axis_layout.addWidget(QLabel("X-axis:"))
        self.x_axis_combo = QComboBox()
        self.x_axis_combo.addItems(["Time (s)", "Voltage (V)", "Current (A)", "Resistance (Ω)", 
                                    "Measurement Number", "Cycle Number"])
        self.x_axis_combo.currentTextChanged.connect(self.update_plot)
        x_axis_layout.addWidget(self.x_axis_combo)
        axis_config_layout.addLayout(x_axis_layout)
        
        # Left Y-axis selection
        y_left_layout = QHBoxLayout()
        y_left_layout.addWidget(QLabel("Y-axis (Left):"))
        self.y_left_combo = QComboBox()
        self.y_left_combo.addItems(["Resistance (Ω)", "Current (A)", "Voltage (V)", "Time (s)"])
        self.y_left_combo.currentTextChanged.connect(self.update_plot)
        y_left_layout.addWidget(self.y_left_combo)
        axis_config_layout.addLayout(y_left_layout)
        
        # Enable right Y-axis checkbox
        self.enable_right_y_check = QCheckBox("Enable Right Y-axis")
        self.enable_right_y_check.stateChanged.connect(self.toggle_right_y_axis)
        self.enable_right_y_check.stateChanged.connect(self.update_plot)
        axis_config_layout.addWidget(self.enable_right_y_check)
        
        # Right Y-axis selection
        y_right_layout = QHBoxLayout()
        y_right_layout.addWidget(QLabel("Y-axis (Right):"))
        self.y_right_combo = QComboBox()
        self.y_right_combo.addItems(["Current (A)", "Resistance (Ω)", "Voltage (V)", "Time (s)"])
        self.y_right_combo.setEnabled(False)
        self.y_right_combo.currentTextChanged.connect(self.update_plot)
        y_right_layout.addWidget(self.y_right_combo)
        axis_config_layout.addLayout(y_right_layout)
        
        # Reset to defaults button
        reset_axes_btn = QPushButton("Reset to Defaults")
        reset_axes_btn.clicked.connect(self.reset_axis_config)
        axis_config_layout.addWidget(reset_axes_btn)
        
        axis_config_group.setLayout(axis_config_layout)
        control_layout.addWidget(axis_config_group)
        
        # Axis Controls (ranges)
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
        
        # Add stretch to push export buttons to bottom
        control_layout.addStretch()
        
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
        
        # Export buttons in a horizontal line at the bottom
        export_layout = QHBoxLayout()
        export_layout.setContentsMargins(5, 5, 5, 5)
        
        export_label = QLabel("Export:")
        export_label.setStyleSheet("font-weight: bold; padding-right: 5px;")
        export_layout.addWidget(export_label)
        
        # PNG buttons
        save_png_btn = QPushButton("💾 PNG")
        save_png_btn.clicked.connect(lambda: self.export_plot('png', False))
        export_layout.addWidget(save_png_btn)
        
        save_png_trans_btn = QPushButton("PNG (Trans)")
        save_png_trans_btn.setToolTip("Save with transparent background")
        save_png_trans_btn.clicked.connect(lambda: self.export_plot('png', True))
        export_layout.addWidget(save_png_trans_btn)
        
        # PDF buttons
        save_pdf_btn = QPushButton("📄 PDF")
        save_pdf_btn.clicked.connect(lambda: self.export_plot('pdf', False))
        export_layout.addWidget(save_pdf_btn)
        
        save_pdf_trans_btn = QPushButton("PDF (Trans)")
        save_pdf_trans_btn.setToolTip("Save with transparent background")
        save_pdf_trans_btn.clicked.connect(lambda: self.export_plot('pdf', True))
        export_layout.addWidget(save_pdf_trans_btn)
        
        # SVG export
        save_svg_btn = QPushButton("🖼️ SVG")
        save_svg_btn.setToolTip("Vector format for publications")
        save_svg_btn.clicked.connect(lambda: self.export_plot('svg', False))
        export_layout.addWidget(save_svg_btn)
        
        # Data export
        save_data_btn = QPushButton("📊 Export Data (TXT)")
        save_data_btn.clicked.connect(self.export_data)
        export_layout.addWidget(save_data_btn)
        
        # Origin export (future)
        save_origin_btn = QPushButton("🔬 Export to Origin")
        save_origin_btn.setEnabled(False)
        save_origin_btn.setToolTip("Coming soon!")
        export_layout.addWidget(save_origin_btn)
        
        export_layout.addStretch()
        
        plot_layout.addLayout(export_layout)
        
        # Add plot panel to splitter
        splitter.addWidget(plot_panel)
        
        # Set initial splitter sizes (25% controls, 75% plot)
        splitter.setSizes([300, 1200])
        
        # Add splitter to main layout
        layout.addWidget(splitter)
    
    def load_datasets(self, datasets: List[TSPData], append: bool = False):
        """Load datasets for plotting
        
        Args:
            datasets: List of TSPData objects to load
            append: If True, append to existing datasets instead of replacing
        """
        if append and hasattr(self, 'datasets') and self.datasets:
            # Append to existing datasets
            start_idx = len(self.datasets)
            self.datasets.extend(datasets)
            
            # Assign colors for new datasets
            for i, data in enumerate(datasets):
                color_idx = (start_idx + i) % len(self.plot_generator.style.COLORS)
                color = self.plot_generator.style.COLORS[color_idx]
                self.dataset_colors.append(color)
            
            # Extend custom labels and samples
            self.custom_labels.extend([None] * len(datasets))
            self.custom_samples.extend([None] * len(datasets))
            
            # Add to dataset list
            for i, data in enumerate(datasets):
                item = DatasetListItem(data, self.dataset_colors[start_idx + i])
                self.dataset_list.addItem(item)
        else:
            # Replace existing datasets
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
            
            # Clear panel assignments when replacing
            self.panel_assignments = {}
        
        # Auto-detect and set default axis configuration (don't update plot yet)
        has_iv_sweep = any('IV Sweep' in data.test_name or 
                          'iv_sweep' in data.test_name.lower() 
                          for data in datasets)
        
        if has_iv_sweep:
            self.x_axis_combo.setCurrentText("Voltage (V)")
            self.y_left_combo.setCurrentText("Current (A)")
            self.enable_right_y_check.setChecked(False)
        else:
            self.x_axis_combo.setCurrentText("Time (s)")
            self.y_left_combo.setCurrentText("Resistance (Ω)")
            self.enable_right_y_check.setChecked(False)
        
        self.toggle_right_y_axis()
        
        # Update plot with new axis configuration
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
        
        # Apply style settings
        self.plot_generator.style.line_width = self.line_width_spin.value()
        self.plot_generator.style.marker_size = self.marker_size_spin.value()
        self.plot_generator.style.grid = self.grid_check.isChecked()
        self.plot_generator.style.legend = self.legend_check.isChecked()
        
        self.plot_generator.style.apply_to_figure(self.figure)
        
        # Get layout configuration
        layout_text = self.layout_combo.currentText()
        shared_axes = self.shared_axes_check.isChecked()
        is_single_panel = "Single Panel" in layout_text
        
        # Collect visible datasets
        visible_datasets = []
        for i in range(self.dataset_list.count()):
            item = self.dataset_list.item(i)
            if isinstance(item, DatasetListItem) and item.visible:
                visible_datasets.append((i, item))
        
        visible_count = len(visible_datasets)
        
        if visible_count == 0:
            self.status_label.setText("No visible datasets to plot")
            return
        
        # Get crop range and processing settings
        crop_start = self.crop_start_spin.value()
        crop_end = self.crop_end_spin.value()
        normalize = self.normalize_check.isChecked()
        y_offset = self.y_offset_spin.value()
        
        # Get axis configuration
        x_axis = self.x_axis_combo.currentText()
        y_left_axis = self.y_left_combo.currentText()
        enable_right_y = self.enable_right_y_check.isChecked()
        y_right_axis = self.y_right_combo.currentText() if enable_right_y else None
        
        # Create subplots
        if is_single_panel:
            # Single panel - ALL datasets on same graph (overlaid)
            ax = self.figure.add_subplot(111)
            axes_list = [ax]
            self.plot_generator.style.apply_to_axes(ax)
            
            # Initialize annotation manager
            self.annotation_manager = AnnotationManager(ax)
            
            # Create right axis if needed
            ax_right = None
            if enable_right_y:
                ax_right = ax.twinx()
                self.plot_generator.style.apply_to_axes(ax_right)
            
            # Plot ALL visible datasets on the same axis
            for dataset_idx, item in visible_datasets:
                data = item.tsp_data
                color = item.color
                
                # Use custom label if available
                if self.custom_labels[dataset_idx]:
                    label = self.custom_labels[dataset_idx]
                else:
                    if self.custom_samples[dataset_idx]:
                        label = f"{self.custom_samples[dataset_idx]} - {data.filename}"
                    else:
                        label = data.get_display_name()
                    
                    key_params = data.get_key_parameters()
                    if key_params and not self.custom_labels[dataset_idx]:
                        label += f" ({key_params})"
                
                # Apply data processing
                processed_data = self.process_data(data, crop_start, crop_end, normalize, y_offset)
                
                # Plot on the same axis
                self.plot_with_axes(processed_data, self.figure, ax, color, label, 
                                  x_axis, y_left_axis, y_right_axis, ax_right)
            
            # Apply log scale if checked
            if self.log_scale_check.isChecked():
                ax.set_yscale('log')
            
            # Update legend
            if self.legend_check.isChecked():
                lines_left, labels_left = ax.get_legend_handles_labels()
                if enable_right_y and ax_right is not None:
                    lines_right, labels_right = ax_right.get_legend_handles_labels()
                    all_lines = lines_left + lines_right
                    all_labels = labels_left + labels_right
                else:
                    all_lines = lines_left
                    all_labels = labels_left
                
                if all_lines:
                    legend = ax.legend(all_lines, all_labels,
                                     facecolor=self.plot_generator.style.bg_color,
                                     edgecolor=self.plot_generator.style.text_color,
                                     labelcolor=self.plot_generator.style.text_color,
                                     loc='best')
                    legend.get_frame().set_alpha(0.9)
            
            # Add statistics box if enabled
            if self.show_stats_box.isChecked() and self.calculated_stats:
                self.draw_statistics_box(ax)
            
            # Apply manual axis ranges if not auto-scaling
            if not self.autoscale_check.isChecked():
                self.apply_axis_ranges()
            
        else:
            # Multi-panel layout
            # Parse layout
            if "2×1" in layout_text:
                rows, cols = 2, 1
            elif "1×2" in layout_text:
                rows, cols = 1, 2
            elif "2×2" in layout_text:
                rows, cols = 2, 2
            elif "3×2" in layout_text:
                rows, cols = 3, 2
            elif "3×3" in layout_text:
                rows, cols = 3, 3
            else:
                rows, cols = 1, 1
            
            total_panels = rows * cols
            
            # Create subplots
            axes_array = self.figure.subplots(rows, cols, sharex=shared_axes, sharey=shared_axes)
            # Flatten axes array to list
            if isinstance(axes_array, np.ndarray):
                axes_list = axes_array.flatten().tolist()
            elif hasattr(axes_array, 'flatten'):
                axes_list = list(axes_array.flatten())
            elif isinstance(axes_array, list):
                axes_list = []
                for item in axes_array:
                    if isinstance(item, list):
                        axes_list.extend(item)
                    else:
                        axes_list.append(item)
            else:
                axes_list = [axes_array]
            
            # Track axis ranges for shared axes
            x_min_vals, x_max_vals = [], []
            y_min_vals, y_max_vals = [], []
            
            # Create mapping: panel_idx -> list of dataset indices
            panel_to_datasets = {i: [] for i in range(total_panels)}
            
            # Assign datasets to panels based on assignments or auto-assign
            for dataset_idx, item in visible_datasets:
                if dataset_idx in self.panel_assignments:
                    # Use manual assignments (can be list for multiple panels)
                    assigned = self.panel_assignments[dataset_idx]
                    if isinstance(assigned, list):
                        for panel_idx in assigned:
                            if panel_idx < total_panels:
                                panel_to_datasets[panel_idx].append((dataset_idx, item))
                    elif assigned < total_panels:
                        panel_to_datasets[assigned].append((dataset_idx, item))
                else:
                    # Auto-assign: first dataset to panel 0, second to panel 1, etc.
                    panel_idx = len([d for ds in panel_to_datasets.values() for d in ds]) % total_panels
                    panel_to_datasets[panel_idx].append((dataset_idx, item))
            
            # Plot datasets on their assigned panels
            for panel_idx in range(total_panels):
                ax = axes_list[panel_idx]
                self.plot_generator.style.apply_to_axes(ax)
                
                # Initialize annotation manager on first panel only
                if panel_idx == 0:
                    self.annotation_manager = AnnotationManager(ax)
                
                # Get datasets for this panel
                panel_datasets = panel_to_datasets[panel_idx]
                
                if not panel_datasets:
                    # No datasets for this panel - hide it
                    ax.set_visible(False)
                    continue
                
                # Create right axis if needed (only for first panel)
                ax_right = None
                if enable_right_y and panel_idx == 0:
                    ax_right = ax.twinx()
                    self.plot_generator.style.apply_to_axes(ax_right)
                
                # Plot all datasets assigned to this panel
                for dataset_idx, item in panel_datasets:
                    data = item.tsp_data
                    color = item.color
                    
                    # Use custom label if available
                    if self.custom_labels[dataset_idx]:
                        label = self.custom_labels[dataset_idx]
                    else:
                        if self.custom_samples[dataset_idx]:
                            label = f"{self.custom_samples[dataset_idx]} - {data.filename}"
                        else:
                            label = data.get_display_name()
                        
                        key_params = data.get_key_parameters()
                        if key_params and not self.custom_labels[dataset_idx]:
                            label += f" ({key_params})"
                    
                    # Apply data processing
                    processed_data = self.process_data(data, crop_start, crop_end, normalize, y_offset)
                    
                    # Plot on this panel
                    self.plot_with_axes(processed_data, self.figure, ax, color, label, 
                                      x_axis, y_left_axis, y_right_axis, ax_right)
                
                # Apply log scale if checked
                if self.log_scale_check.isChecked():
                    ax.set_yscale('log')
                
                # Collect axis ranges for shared axes
                if not self.autoscale_check.isChecked():
                    x_min_vals.append(self.x_min_spin.value())
                    x_max_vals.append(self.x_max_spin.value())
                    y_min_vals.append(self.y_min_spin.value())
                    y_max_vals.append(self.y_max_spin.value())
                else:
                    xlim = ax.get_xlim()
                    ylim = ax.get_ylim()
                    x_min_vals.append(xlim[0])
                    x_max_vals.append(xlim[1])
                    y_min_vals.append(ylim[0])
                    y_max_vals.append(ylim[1])
                
                # Update legend for this panel
                if self.legend_check.isChecked():
                    lines, labels = ax.get_legend_handles_labels()
                    if lines:
                        legend = ax.legend(lines, labels,
                                         facecolor=self.plot_generator.style.bg_color,
                                         edgecolor=self.plot_generator.style.text_color,
                                         labelcolor=self.plot_generator.style.text_color,
                                         loc='best', fontsize=8)
                        legend.get_frame().set_alpha(0.9)
            
            # Add statistics box if enabled (only on first panel with data)
            if self.show_stats_box.isChecked() and self.calculated_stats:
                first_panel_with_data = next((i for i, ax in enumerate(axes_list) if ax.get_visible()), 0)
                self.draw_statistics_box(axes_list[first_panel_with_data])
            
            # Apply shared axes ranges if enabled
            if shared_axes:
                if x_min_vals and x_max_vals:
                    x_min_global = min(x_min_vals)
                    x_max_global = max(x_max_vals)
                    for ax in axes_list:
                        if ax.get_visible():
                            ax.set_xlim(x_min_global, x_max_global)
                
                if y_min_vals and y_max_vals:
                    y_min_global = min(y_min_vals)
                    y_max_global = max(y_max_vals)
                    for ax in axes_list:
                        if ax.get_visible():
                            ax.set_ylim(y_min_global, y_max_global)
        
        self.figure.tight_layout()
        self.canvas.draw()
        
        if is_single_panel:
            self.status_label.setText(f"Showing {visible_count} dataset(s) overlaid on same graph")
        else:
            panel_info = f" ({total_panels} panel{'s' if total_panels > 1 else ''})"
            self.status_label.setText(f"Showing {visible_count} dataset(s) across{panel_info}")
    
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
            # Also remove custom labels/samples if they exist
            if current_row < len(self.custom_labels):
                del self.custom_labels[current_row]
            if current_row < len(self.custom_samples):
                del self.custom_samples[current_row]
            self.update_plot()
            # Update button state
            if len(self.datasets) == 0:
                self.view_details_btn.setEnabled(False)
    
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
    
    def on_dataset_selection_changed(self):
        """Handle dataset selection change - enable/disable view details button"""
        current_row = self.dataset_list.currentRow()
        has_selection = current_row >= 0 and current_row < len(self.datasets)
        self.view_details_btn.setEnabled(has_selection)
    
    def show_dataset_context_menu(self, position):
        """Show context menu for dataset list"""
        item = self.dataset_list.itemAt(position)
        if item is None:
            return
        
        menu = QMenu(self)
        
        view_action = menu.addAction("ℹ️ View Details")
        view_action.triggered.connect(self.view_dataset_details)
        
        menu.addSeparator()
        
        toggle_action = menu.addAction("👁️ Toggle Visibility")
        toggle_action.triggered.connect(lambda: self.toggle_dataset_visibility(item))
        
        remove_action = menu.addAction("🗑️ Remove")
        remove_action.triggered.connect(self.remove_selected_dataset)
        
        menu.exec(self.dataset_list.mapToGlobal(position))
    
    def view_dataset_details(self):
        """Show detailed information about selected dataset"""
        current_row = self.dataset_list.currentRow()
        if current_row < 0 or current_row >= len(self.datasets):
            QMessageBox.information(self, "No Selection", "Please select a dataset to view details.")
            return
        
        data = self.datasets[current_row]
        
        # Create dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Dataset Details: {data.filename}")
        dialog.setMinimumWidth(500)
        dialog.setMinimumHeight(400)
        
        layout = QVBoxLayout(dialog)
        
        # Create text area with formatted information
        details_text = QTextEdit()
        details_text.setReadOnly(True)
        details_text.setFont(QFont("Courier New", 9))
        details_text.setStyleSheet("""
            QTextEdit {
                background-color: #2b2b2b;
                color: #e0e0e0;
                border: 1px solid #555;
                padding: 8px;
            }
        """)
        
        # Format information similar to file browser preview
        info_html = f"""
        <style>
            body {{ background-color: #2b2b2b; color: #e0e0e0; }}
            h3 {{ color: #2196F3; }}
            hr {{ border: 1px solid #555; }}
            b {{ color: #b0b0b0; }}
        </style>
        <h3>{data.filename}</h3>
        <hr>
        <b>Test Type:</b> <span style="color: #4CAF50;">{data.test_name}</span><br>
        <b>Sample:</b> {data.sample}<br>
        <b>Device:</b> {data.device}<br>
        <b>Instrument:</b> {data.instrument}<br>
        <b>Address:</b> {data.address}<br>
        <b>Timestamp:</b> {data.timestamp}<br>
        <b>Data Points:</b> {len(data.timestamps)}<br>
        <b>Duration:</b> {data.duration:.2f} s<br>
        <b>File Path:</b> <span style="color: #888; font-size: 9pt;">{data.filepath}</span><br>
        <hr>
        <b>Test Parameters:</b><br>
        """
        for key, value in data.parameters.items():
            info_html += f"&nbsp;&nbsp;<span style='color: #888'>{key}:</span> {value}<br>"
        
        if data.hardware_limits:
            info_html += f"<hr><b>Hardware Limits:</b><br>"
            for key, value in data.hardware_limits.items():
                info_html += f"&nbsp;&nbsp;<span style='color: #888'>{key}:</span> {value}<br>"
        
        if data.notes:
            info_html += f"<hr><b>Notes:</b><br><span style='color: #d0d0d0'>{data.notes}</span>"
        
        details_text.setHtml(info_html)
        layout.addWidget(details_text)
        
        # Close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)
        
        dialog.exec()
    
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
            # Update button state
            self.view_details_btn.setEnabled(False)
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
    
    def on_layout_changed(self):
        """Handle layout change - enable/disable multi-panel controls"""
        layout_text = self.layout_combo.currentText()
        is_multi_panel = "Single Panel" not in layout_text
        
        self.assign_panels_btn.setEnabled(is_multi_panel)
        self.shared_axes_check.setEnabled(is_multi_panel)
        
        if is_multi_panel:
            self.layout_info_label.setText("💡 Click 'Assign Datasets' to choose which datasets go to which panels")
        else:
            self.layout_info_label.setText("💡 All datasets shown together on same graph")
        
        self.update_plot()
    
    def show_panel_assignment_dialog(self):
        """Show dialog to assign datasets to panels"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QDialogButtonBox
        
        # Get current layout
        layout_text = self.layout_combo.currentText()
        if "2×1" in layout_text:
            rows, cols = 2, 1
        elif "1×2" in layout_text:
            rows, cols = 1, 2
        elif "2×2" in layout_text:
            rows, cols = 2, 2
        elif "3×2" in layout_text:
            rows, cols = 3, 2
        elif "3×3" in layout_text:
            rows, cols = 3, 3
        else:
            QMessageBox.information(self, "Info", "Select a multi-panel layout first")
            return
        
        total_panels = rows * cols
        
        # Get visible datasets
        visible_datasets = []
        for i in range(self.dataset_list.count()):
            item = self.dataset_list.item(i)
            if isinstance(item, DatasetListItem) and item.visible:
                visible_datasets.append((i, item))
        
        if not visible_datasets:
            QMessageBox.warning(self, "No Data", "No visible datasets to assign")
            return
        
        # Create dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Assign Datasets to Panels ({rows}×{cols})")
        dialog.setMinimumWidth(600)
        dialog.setMinimumHeight(400)
        
        layout = QVBoxLayout(dialog)
        
        # Instructions
        info_label = QLabel(f"Assign {len(visible_datasets)} dataset(s) to {total_panels} panel(s). Each panel can have multiple datasets.")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("padding: 10px; background-color: #3c3c3c; border-radius: 5px;")
        layout.addWidget(info_label)
        
        # Table: rows = datasets, columns = panels
        table = QTableWidget(len(visible_datasets), total_panels)
        table.setHorizontalHeaderLabels([f"Panel {i+1}" for i in range(total_panels)])
        
        # Set dataset names as row headers
        dataset_names = []
        for idx, item in visible_datasets:
            name = self.custom_labels[idx] if self.custom_labels[idx] else item.tsp_data.get_display_name()
            dataset_names.append(name)
        table.setVerticalHeaderLabels(dataset_names)
        
        # Populate table with checkboxes
        for row, (dataset_idx, item) in enumerate(visible_datasets):
            # Check if already assigned
            assigned_panels = self.panel_assignments.get(dataset_idx, [])
            if not isinstance(assigned_panels, list):
                assigned_panels = [assigned_panels] if assigned_panels is not None else []
            
            for col in range(total_panels):
                checkbox_item = QTableWidgetItem()
                checkbox_item.setFlags(checkbox_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                
                # Check if this dataset was previously assigned to this panel
                if col in assigned_panels:
                    checkbox_item.setCheckState(Qt.CheckState.Checked)
                else:
                    checkbox_item.setCheckState(Qt.CheckState.Unchecked)
                
                table.setItem(row, col, checkbox_item)
        
        # Auto-assign button
        auto_assign_layout = QHBoxLayout()
        auto_assign_btn = QPushButton("Auto-Assign (Sequential)")
        auto_assign_btn.clicked.connect(lambda: self.auto_assign_datasets(table, visible_datasets, total_panels))
        auto_assign_layout.addWidget(auto_assign_btn)
        auto_assign_layout.addStretch()
        layout.addLayout(auto_assign_layout)
        
        layout.addWidget(table)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(lambda: self.apply_panel_assignments(dialog, table, visible_datasets, total_panels))
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        dialog.exec()
    
    def auto_assign_datasets(self, table, visible_datasets, total_panels):
        """Auto-assign datasets to panels sequentially"""
        for row, (dataset_idx, item) in enumerate(visible_datasets):
            panel_idx = row % total_panels
            checkbox_item = table.item(row, panel_idx)
            if checkbox_item:
                checkbox_item.setCheckState(Qt.CheckState.Checked)
                # Uncheck all other panels for this dataset
                for col in range(total_panels):
                    if col != panel_idx:
                        other_item = table.item(row, col)
                        if other_item:
                            other_item.setCheckState(Qt.CheckState.Unchecked)
    
    def apply_panel_assignments(self, dialog, table, visible_datasets, total_panels):
        """Apply panel assignments from dialog"""
        # Clear existing assignments
        self.panel_assignments.clear()
        
        # Read assignments from table
        for row, (dataset_idx, item) in enumerate(visible_datasets):
            for col in range(total_panels):
                checkbox_item = table.item(row, col)
                if checkbox_item and checkbox_item.checkState() == Qt.CheckState.Checked:
                    # This dataset should be on this panel
                    if dataset_idx not in self.panel_assignments:
                        self.panel_assignments[dataset_idx] = []
                    if isinstance(self.panel_assignments[dataset_idx], list):
                        self.panel_assignments[dataset_idx].append(col)
                    else:
                        self.panel_assignments[dataset_idx] = [col]
        
        dialog.accept()
        self.update_plot()
    
    def ensure_odd_window_size(self):
        """Ensure window size is odd when Savitzky-Golay is selected"""
        method = self.smoothing_method_combo.currentText()
        if method == "Savitzky-Golay":
            current_val = self.smoothing_window_spin.value()
            if current_val % 2 == 0:
                # Block signals to avoid recursion
                self.smoothing_window_spin.blockSignals(True)
                self.smoothing_window_spin.setValue(current_val + 1)
                self.smoothing_window_spin.blockSignals(False)
    
    def update_smoothing_controls(self):
        """Enable/disable smoothing controls based on selected method"""
        method = self.smoothing_method_combo.currentText()
        
        if method == "None":
            self.smoothing_window_spin.setEnabled(False)
            self.smoothing_poly_spin.setEnabled(False)
            self.smoothing_sigma_spin.setEnabled(False)
        elif method == "Moving Average":
            self.smoothing_window_spin.setEnabled(True)
            self.smoothing_poly_spin.setEnabled(False)
            self.smoothing_sigma_spin.setEnabled(False)
        elif method == "Savitzky-Golay":
            self.smoothing_window_spin.setEnabled(True)
            self.smoothing_poly_spin.setEnabled(True)
            self.smoothing_sigma_spin.setEnabled(False)
            # Ensure window size is odd for Savitzky-Golay
            self.ensure_odd_window_size()
        elif method == "Gaussian Filter":
            self.smoothing_window_spin.setEnabled(False)
            self.smoothing_poly_spin.setEnabled(False)
            self.smoothing_sigma_spin.setEnabled(True)
    
    def toggle_right_y_axis(self):
        """Enable/disable right Y-axis controls"""
        enabled = self.enable_right_y_check.isChecked()
        self.y_right_combo.setEnabled(enabled)
    
    def reset_axis_config(self):
        """Reset axis configuration to defaults based on data type"""
        if not self.datasets:
            # Default: Time vs Resistance
            self.x_axis_combo.setCurrentText("Time (s)")
            self.y_left_combo.setCurrentText("Resistance (Ω)")
            self.enable_right_y_check.setChecked(False)
            return
        
        # Check if any dataset is IV sweep
        has_iv_sweep = any('IV Sweep' in data.test_name or 
                          'iv_sweep' in data.test_name.lower() 
                          for data in self.datasets)
        
        if has_iv_sweep:
            # Default for IV sweeps: Voltage vs Current
            self.x_axis_combo.setCurrentText("Voltage (V)")
            self.y_left_combo.setCurrentText("Current (A)")
            self.enable_right_y_check.setChecked(False)
        else:
            # Default for other data: Time vs Resistance
            self.x_axis_combo.setCurrentText("Time (s)")
            self.y_left_combo.setCurrentText("Resistance (Ω)")
            self.enable_right_y_check.setChecked(False)
        
        self.toggle_right_y_axis()
        self.update_plot()
    
    def get_axis_data(self, data: TSPData, axis_name: str) -> tuple:
        """
        Get data array and label for a given axis name.
        Returns (data_array, label_string)
        """
        axis_name_lower = axis_name.lower()
        
        if 'time' in axis_name_lower:
            return data.timestamps, "Time (s)"
        elif 'voltage' in axis_name_lower:
            return data.voltages, "Voltage (V)"
        elif 'current' in axis_name_lower:
            return data.currents, "Current (A)"
        elif 'resistance' in axis_name_lower or 'Ω' in axis_name or 'ohm' in axis_name_lower:
            return data.resistances, "Resistance (Ω)"
        elif 'measurement' in axis_name_lower and 'number' in axis_name_lower:
            return data.measurement_numbers, "Measurement Number"
        elif 'cycle' in axis_name_lower and 'number' in axis_name_lower:
            if 'Cycle Number' in data.additional_data:
                return data.additional_data['Cycle Number'], "Cycle Number"
            if 'Cycle Numbers' in data.additional_data:
                return np.asarray(data.additional_data['Cycle Numbers'], dtype=float), "Cycle Number"
            return data.measurement_numbers, "Measurement Number"
        else:
            # Try to find in additional_data
            for key, value in data.additional_data.items():
                if axis_name_lower in key.lower():
                    return value, key
        
        # Fallback to timestamps
        return data.timestamps, "Time (s)"
    
    def plot_with_axes(self, data: TSPData, fig: Figure, ax: Axes, color: str, label: str,
                       x_axis: str, y_left_axis: str, y_right_axis: Optional[str] = None,
                       ax_right: Optional[Axes] = None):
        """
        Plot data with custom axis configuration.
        
        Args:
            data: TSPData object
            fig: Matplotlib figure
            ax: Matplotlib axes (left Y-axis)
            color: Line color
            label: Legend label
            x_axis: X-axis selection (e.g., "Time (s)")
            y_left_axis: Left Y-axis selection
            y_right_axis: Right Y-axis selection (optional)
            ax_right: Right Y-axis (optional, created externally for multi-dataset)
        """
        import numpy as np
        
        # Special handling for endurance tests: use plot_single to get SET/RESET separation
        if ('endurance' in data.test_name.lower() and
                'Resistance (Reset)' in data.additional_data and
                'Resistance (Set)' in data.additional_data):
            show_difference = self.show_difference_check.isChecked()
            fixed_state = 'lrs' if self.endurance_fixed_combo.currentText() == "LRS (SET)" else 'hrs'
            self.plot_generator.plot_single(data, fig, ax, color, label, show_difference=show_difference,
                                           endurance_fixed_state=fixed_state)
            return
        
        # Get X-axis data
        x_data, x_label = self.get_axis_data(data, x_axis)
        
        # Get left Y-axis data
        y_left_data, y_left_label = self.get_axis_data(data, y_left_axis)
        
        # Filter out NaN and inf values
        valid_mask = np.isfinite(x_data) & np.isfinite(y_left_data)
        if not np.any(valid_mask):
            return
        
        x_plot = x_data[valid_mask]
        y_left_plot = y_left_data[valid_mask]
        
        # Plot on left Y-axis
        line = ax.plot(x_plot, y_left_plot,
                      color=color,
                      linewidth=self.plot_generator.style.line_width,
                      marker='o',
                      markersize=self.plot_generator.style.marker_size,
                      label=label,
                      markevery=max(1, len(x_plot)//50))
        
        # Set labels
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_left_label)
        
        # Handle right Y-axis if enabled
        if y_right_axis and ax_right is not None:
            # Get right Y-axis data
            y_right_data, y_right_label = self.get_axis_data(data, y_right_axis)
            
            # Filter out NaN and inf
            valid_mask_right = np.isfinite(x_data) & np.isfinite(y_right_data)
            if np.any(valid_mask_right):
                x_right_plot = x_data[valid_mask_right]
                y_right_plot = y_right_data[valid_mask_right]
                
                # Use different color for right axis
                # Shift color in palette or use complementary
                color_index = self.plot_generator.style.COLORS.index(color) if color in self.plot_generator.style.COLORS else 0
                right_color = self.plot_generator.style.COLORS[(color_index + 1) % len(self.plot_generator.style.COLORS)]
                
                # Use dashed line style to distinguish
                ax_right.plot(x_right_plot, y_right_plot,
                            color=right_color,
                            linewidth=self.plot_generator.style.line_width,
                            marker='s',
                            markersize=self.plot_generator.style.marker_size * 0.8,
                            label=f"{label} ({y_right_label})",
                            linestyle='--',
                            markevery=max(1, len(x_right_plot)//50))
                
                ax_right.set_ylabel(y_right_label, color=right_color)
                ax_right.tick_params(axis='y', labelcolor=right_color)
    
    def process_data(self, data: TSPData, crop_start: int, crop_end: int, 
                    normalize: bool, y_offset: float) -> TSPData:
        """
        Process data with cropping, normalization, offset, and smoothing.
        Returns a modified copy of the data.
        """
        import copy
        import numpy as np
        from scipy import signal
        from scipy.ndimage import gaussian_filter1d
        
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
        
        # Apply smoothing (to resistance, current, and voltage)
        smoothing_method = self.smoothing_method_combo.currentText()
        if smoothing_method != "None" and len(processed.resistances) > 0:
            window_size = self.smoothing_window_spin.value()
            poly_order = self.smoothing_poly_spin.value()
            sigma = self.smoothing_sigma_spin.value()
            
            # Ensure we have enough points for smoothing
            min_points = max(3, window_size if window_size > 3 else 3)
            if len(processed.resistances) >= min_points:
                try:
                    if smoothing_method == "Moving Average":
                        # Moving average with proper edge handling
                        # Use scipy's uniform_filter1d which handles edges better
                        from scipy.ndimage import uniform_filter1d
                        processed.resistances = uniform_filter1d(processed.resistances, size=window_size, mode='reflect')
                        if len(processed.currents) == len(processed.resistances):
                            processed.currents = uniform_filter1d(processed.currents, size=window_size, mode='reflect')
                    
                    elif smoothing_method == "Savitzky-Golay":
                        # Ensure window size is odd
                        if window_size % 2 == 0:
                            window_size += 1
                        if window_size > len(processed.resistances):
                            window_size = len(processed.resistances) if len(processed.resistances) % 2 == 1 else len(processed.resistances) - 1
                        
                        if window_size >= 3 and poly_order < window_size:
                            processed.resistances = signal.savgol_filter(processed.resistances, window_size, poly_order)
                            if len(processed.currents) == len(processed.resistances):
                                processed.currents = signal.savgol_filter(processed.currents, window_size, poly_order)
                    
                    elif smoothing_method == "Gaussian Filter":
                        processed.resistances = gaussian_filter1d(processed.resistances, sigma=sigma)
                        if len(processed.currents) == len(processed.resistances):
                            processed.currents = gaussian_filter1d(processed.currents, sigma=sigma)
                except Exception as e:
                    # If smoothing fails, continue without smoothing
                    print(f"Warning: Smoothing failed: {e}")
        
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
        
        # Get default save location from first dataset's filepath
        default_dir = None
        default_name = f"tsp_plot.{format}"
        
        if self.datasets:
            # Use directory of first dataset
            first_filepath = self.datasets[0].filepath
            if first_filepath and first_filepath.parent.exists():
                default_dir = str(first_filepath.parent)
                # Generate better default name from first dataset
                base_name = first_filepath.stem
                trans_suffix = "_transparent" if transparent else ""
                default_name = f"{base_name}_plot{trans_suffix}.{format}"
        
        # Get save location
        if default_dir:
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                f"Save Plot as {format.upper()}" + (" (Transparent)" if transparent else ""),
                str(Path(default_dir) / default_name),
                f"{format.upper()} Files (*.{format});;All Files (*.*)"
            )
        else:
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                f"Save Plot as {format.upper()}" + (" (Transparent)" if transparent else ""),
                default_name,
                f"{format.upper()} Files (*.{format});;All Files (*.*)"
            )
        
        if file_path:
            try:
                # Set DPI based on format
                if format == 'png':
                    dpi = 300
                elif format == 'pdf':
                    dpi = 150
                elif format == 'svg':
                    dpi = None  # SVG is vector, no DPI
                else:
                    dpi = 150
                
                if transparent:
                    # Save with transparent background
                    original_bg = self.figure.get_facecolor()
                    original_ax_bgs = []
                    for ax in self.figure.axes:
                        original_ax_bgs.append(ax.get_facecolor())
                    
                    # Set transparent
                    self.figure.patch.set_facecolor('none')
                    for ax in self.figure.axes:
                        ax.patch.set_facecolor('none')
                    
                    # Save
                    save_kwargs = {'transparent': True, 'bbox_inches': 'tight'}
                    if dpi is not None:
                        save_kwargs['dpi'] = dpi
                    self.figure.savefig(file_path, **save_kwargs)
                    
                    # Restore original colors
                    self.figure.patch.set_facecolor(original_bg)
                    for ax, original_bg in zip(self.figure.axes, original_ax_bgs):
                        ax.patch.set_facecolor(original_bg)
                else:
                    # Save with current background
                    if format == 'svg':
                        self.figure.savefig(file_path, format='svg', bbox_inches='tight')
                    else:
                        self.plot_generator.save_figure(self.figure, Path(file_path), dpi=dpi)
                
                QMessageBox.information(self, "Success", f"Plot saved to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save plot:\n{e}")
                import traceback
                traceback.print_exc()
    
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
        
        # Get default save location from first dataset's filepath
        default_dir = None
        default_name = "tsp_data_export.txt"
        
        if visible_datasets:
            first_filepath = visible_datasets[0].filepath
            if first_filepath and first_filepath.parent.exists():
                default_dir = str(first_filepath.parent)
                base_name = first_filepath.stem
                default_name = f"{base_name}_export.txt"
        
        # Get save location
        if default_dir:
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Data as TXT",
                str(Path(default_dir) / default_name),
                "Text Files (*.txt);;All Files (*.*)"
            )
        else:
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Data as TXT",
                default_name,
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

