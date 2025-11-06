"""
Combined Plot Tab

A read-only plotting tab that shows multiple source tabs in a multi-panel layout.
Each source tab becomes one panel. Panels can be reordered but data is locked.
"""

from PyQt6.QtWidgets import (QLabel, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                              QComboBox, QCheckBox, QSpinBox, QDoubleSpinBox, QListWidget, QListWidgetItem)
from PyQt6.QtCore import Qt
from typing import List, Optional
from .plotting_tab import PlottingTab, DatasetListItem
from .plot_annotations import AnnotationManager, AnnotationToolbar
import numpy as np


class CombinedPlotTab(PlottingTab):
    """A read-only plotting tab that shows source tabs in multi-panel layout"""
    
    def __init__(self, parent=None, source_tabs: Optional[List[PlottingTab]] = None):
        """
        Args:
            parent: Parent widget (MainWindow)
            source_tabs: List of PlottingTab objects to combine (each becomes a panel)
        """
        self.is_combined = True
        self.source_tabs: List[PlottingTab] = source_tabs or []
        self.panel_order: List[int] = []  # Order of panels (indices into source_tabs)
        self.current_layout_rows = 0  # Current layout configuration
        self.current_layout_cols = 0
        self.annotation_manager = None  # Will be initialized per panel
        
        # Initialize empty datasets list (we'll use source tabs directly)
        self.datasets = []
        self.dataset_colors = []
        self.custom_labels = []
        self.custom_samples = []
        
        # Call parent init
        super().__init__(parent)
        
        # Initialize panel order
        if self.source_tabs:
            self.panel_order = list(range(len(self.source_tabs)))
        
        # Make it read-only (after UI is set up)
        self.make_read_only()
        
        # Add panel reordering controls and layout selector
        self.add_panel_controls()
        
        # Add info banner
        self.add_info_banner()
        
        # Enable annotations (they work on combined plots)
        self.enable_annotations()
        
        # Set initial multi-panel layout (after controls are created)
        # Use a small delay to ensure everything is initialized
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, self.setup_multi_panel_layout)
    
    def make_read_only(self):
        """Disable editing controls to make this tab read-only"""
        # Disable dataset list editing
        if hasattr(self, 'dataset_list'):
            self.dataset_list.setEnabled(False)
        
        # Disable all editing controls except panel reordering and refresh
        widgets_to_disable = []
        
        for widget in self.findChildren(QWidget):
            widget_name = widget.objectName()
            # Skip panel controls, layout selector, annotation toolbar, and navigation toolbar
            if widget_name in ['panel_order_list', 'reorder_up_btn', 'reorder_down_btn', 'refresh_btn', 'layout_combo']:
                continue
            if isinstance(widget, QComboBox) and widget.objectName() == 'layout_combo':
                continue
            if 'nav' in widget_name.lower() or 'toolbar' in widget_name.lower() or 'annotation' in widget_name.lower():
                continue
                
            # Disable specific control types
            if isinstance(widget, (QComboBox, QCheckBox, QSpinBox, QDoubleSpinBox)):
                widgets_to_disable.append(widget)
            elif isinstance(widget, QPushButton):
                btn_text = widget.text() if hasattr(widget, 'text') else ''
                if 'refresh' not in btn_text.lower() and '🔄' not in btn_text and 'reorder' not in btn_text.lower() and 'annotation' not in btn_text.lower():
                    widgets_to_disable.append(widget)
        
        # Disable all found widgets
        for widget in widgets_to_disable:
            widget.setEnabled(False)
    
    def add_info_banner(self):
        """Add an info banner at the top indicating this is a combined plot"""
        # Find the control panel
        control_panel = None
        for child in self.children():
            if hasattr(child, 'layout') and child.layout():
                if hasattr(child, 'findChild'):
                    dataset_list = child.findChild(QWidget)
                    if dataset_list and hasattr(dataset_list, 'count'):  # It's a list widget
                        control_panel = child
                        break
        
        if control_panel:
            layout = control_panel.layout()
            if layout:
                banner = QLabel("🔗 Combined Multi-Panel View")
                banner.setStyleSheet("""
                    QLabel {
                        background-color: #2196F3;
                        color: white;
                        padding: 6px;
                        font-weight: bold;
                        border-radius: 3px;
                        margin: 3px;
                    }
                """)
                banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
                banner.setWordWrap(True)
                banner.setToolTip("Each source tab is shown as a panel. Data is locked but panels can be reordered.")
                # Insert at the top
                layout.insertWidget(0, banner)
    
    def enable_annotations(self):
        """Enable annotation toolbar for combined plots"""
        # The annotation toolbar is already created by parent class
        # We just need to make sure it's enabled and connected
        if hasattr(self, 'annotation_toolbar'):
            # Connect click handler if not already connected
            if not hasattr(self, '_annotation_click_connected'):
                self.canvas.mpl_connect('button_press_event', self.on_plot_click)
                self._annotation_click_connected = True
    
    def on_plot_click(self, event):
        """Handle clicks on the plot canvas for annotations"""
        if event.inaxes is None or event.button != 1:  # Left click only
            return
        
        # Find which panel was clicked
        clicked_panel = None
        for ax in self.figure.axes:
            if ax == event.inaxes:
                clicked_panel = ax
                break
        
        if clicked_panel and hasattr(self, 'annotation_toolbar'):
            # Update annotation manager for the clicked panel
            self.annotation_manager = AnnotationManager(clicked_panel)
            
            # Update position in annotation toolbar
            self.annotation_toolbar.set_position(event.xdata, event.ydata)
            
            # If adding arrow and already have start point, set end point
            if self.annotation_toolbar.current_type == 'arrow':
                if self.annotation_toolbar.x2_spin.value() == 0:
                    self.annotation_toolbar.set_arrow_end_position(event.xdata, event.ydata)
    
    def add_panel_controls(self):
        """Add controls for reordering panels"""
        # Find the control panel
        control_panel = None
        for child in self.children():
            if hasattr(child, 'layout') and child.layout():
                if hasattr(child, 'findChild'):
                    dataset_list = child.findChild(QWidget)
                    if dataset_list and hasattr(dataset_list, 'count'):
                        control_panel = child
                        break
        
        if control_panel:
            layout = control_panel.layout()
            if layout:
                # Panel order group
                panel_group = QWidget()
                panel_layout = QVBoxLayout(panel_group)
                panel_layout.setContentsMargins(5, 5, 5, 5)
                
                panel_label = QLabel("📐 Panel Order:")
                panel_layout.addWidget(panel_label)
                
                # List widget for panel order
                self.panel_order_list = QListWidget()
                self.panel_order_list.setObjectName("panel_order_list")
                self.panel_order_list.setMaximumHeight(150)
                self.panel_order_list.setToolTip("Drag to reorder panels or use Up/Down buttons")
                panel_layout.addWidget(self.panel_order_list)
                
                # Reorder buttons
                reorder_btn_layout = QHBoxLayout()
                
                self.reorder_up_btn = QPushButton("⬆ Up")
                self.reorder_up_btn.setObjectName("reorder_up_btn")
                self.reorder_up_btn.clicked.connect(self.move_panel_up)
                reorder_btn_layout.addWidget(self.reorder_up_btn)
                
                self.reorder_down_btn = QPushButton("⬇ Down")
                self.reorder_down_btn.setObjectName("reorder_down_btn")
                self.reorder_down_btn.clicked.connect(self.move_panel_down)
                reorder_btn_layout.addWidget(self.reorder_down_btn)
                
                panel_layout.addLayout(reorder_btn_layout)
                
                # Layout selection
                layout_select_layout = QHBoxLayout()
                layout_select_layout.addWidget(QLabel("Layout:"))
                self.layout_combo = QComboBox()
                self.layout_combo.setObjectName("layout_combo")
                self.layout_combo.addItems([
                    "Auto",
                    "1×1",
                    "1×2",
                    "2×1",
                    "2×2",
                    "2×3",
                    "3×2",
                    "3×3"
                ])
                self.layout_combo.setCurrentText("Auto")
                self.layout_combo.setToolTip("Select panel layout grid")
                self.layout_combo.currentTextChanged.connect(self.on_layout_changed)
                layout_select_layout.addWidget(self.layout_combo)
                panel_layout.addLayout(layout_select_layout)
                
                # Insert after banner (position 1)
                layout.insertWidget(1, panel_group)
                
                # Update panel order list
                self.update_panel_order_list()
    
    def update_panel_order_list(self):
        """Update the panel order list widget"""
        if not hasattr(self, 'panel_order_list'):
            return
        
        self.panel_order_list.clear()
        
        # Get tab names from parent
        parent_window = self.parent()
        tab_names = {}
        if hasattr(parent_window, 'tabs'):
            for i in range(parent_window.tabs.count()):
                widget = parent_window.tabs.widget(i)
                if isinstance(widget, PlottingTab) and widget in self.source_tabs:
                    tab_name = parent_window.tabs.tabText(i)
                    tab_names[widget] = tab_name
        
        # Add panels in current order
        for idx in self.panel_order:
            if idx < len(self.source_tabs):
                source_tab = self.source_tabs[idx]
                tab_name = tab_names.get(source_tab, f"Panel {idx + 1}")
                
                item = QListWidgetItem(f"📊 {tab_name}")
                item.setData(Qt.ItemDataRole.UserRole, idx)
                self.panel_order_list.addItem(item)
    
    def move_panel_up(self):
        """Move selected panel up in order"""
        current_row = self.panel_order_list.currentRow()
        if current_row > 0:
            # Swap items
            item_above = self.panel_order_list.item(current_row - 1)
            item_current = self.panel_order_list.item(current_row)
            
            # Swap in list
            self.panel_order_list.takeItem(current_row)
            self.panel_order_list.insertItem(current_row - 1, item_current)
            
            # Swap in panel_order
            self.panel_order[current_row], self.panel_order[current_row - 1] = \
                self.panel_order[current_row - 1], self.panel_order[current_row]
            
            # Update selection
            self.panel_order_list.setCurrentRow(current_row - 1)
            
            # Refresh plot
            self.setup_multi_panel_layout()
    
    def move_panel_down(self):
        """Move selected panel down in order"""
        current_row = self.panel_order_list.currentRow()
        if current_row >= 0 and current_row < self.panel_order_list.count() - 1:
            # Swap items
            item_current = self.panel_order_list.item(current_row)
            item_below = self.panel_order_list.item(current_row + 1)
            
            # Swap in list
            self.panel_order_list.takeItem(current_row)
            self.panel_order_list.insertItem(current_row + 1, item_current)
            
            # Swap in panel_order
            self.panel_order[current_row], self.panel_order[current_row + 1] = \
                self.panel_order[current_row + 1], self.panel_order[current_row]
            
            # Update selection
            self.panel_order_list.setCurrentRow(current_row + 1)
            
            # Refresh plot
            self.setup_multi_panel_layout()
    
    def on_layout_changed(self):
        """Handle layout selection change"""
        self.setup_multi_panel_layout()
    
    def setup_multi_panel_layout(self):
        """Setup multi-panel layout showing each source tab as a panel"""
        if not self.source_tabs:
            return
        
        num_panels = len(self.source_tabs)
        
        # Determine grid layout based on selection or auto
        layout_text = "Auto"
        # Check if layout_combo exists and is the one we created (not from parent class)
        # We need to find it by objectName to avoid conflicts with parent class
        layout_combo_widget = None
        for widget in self.findChildren(QComboBox):
            if widget.objectName() == 'layout_combo':
                layout_combo_widget = widget
                break
        
        if layout_combo_widget:
            layout_text = layout_combo_widget.currentText()
        
        if layout_text == "Auto":
            # Auto-determine layout
            if num_panels == 1:
                rows, cols = 1, 1
            elif num_panels == 2:
                rows, cols = 1, 2
            elif num_panels <= 4:
                rows, cols = 2, 2
            elif num_panels <= 6:
                rows, cols = 2, 3
            elif num_panels <= 9:
                rows, cols = 3, 3
            else:
                cols = 4
                rows = (num_panels + cols - 1) // cols
        else:
            # Parse selected layout - handle different formats
            # Could be "1×1", "1×2", "2×2", etc. or "Single Panel (1×1) - All Overlaid"
            layout_clean = layout_text.strip()
            
            # Extract just the numbers if it's in "rows×cols" format
            if "×" in layout_clean:
                # Find the pattern like "1×1" or "2×2" in the text
                import re
                match = re.search(r'(\d+)\s*×\s*(\d+)', layout_clean)
                if match:
                    rows = int(match.group(1))
                    cols = int(match.group(2))
                else:
                    # Fallback: try direct split
                    parts = layout_clean.split("×")
                    if len(parts) == 2:
                        try:
                            rows = int(parts[0].strip())
                            cols = int(parts[1].strip())
                        except ValueError:
                            # Fallback to auto
                            rows, cols = 2, 2
                    else:
                        rows, cols = 2, 2
            else:
                # Fallback to auto
                rows, cols = 2, 2
        
        # Store current layout
        self.current_layout_rows = rows
        self.current_layout_cols = cols
        
        # Clear figure
        self.figure.clear()
        
        # Create subplots
        axes_array = self.figure.subplots(rows, cols, sharex=False, sharey=False)
        
        # Flatten axes array
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
        
        # Get parent window for tab names
        parent_window = self.parent()
        tab_names = {}
        if hasattr(parent_window, 'tabs'):
            for i in range(parent_window.tabs.count()):
                widget = parent_window.tabs.widget(i)
                if isinstance(widget, PlottingTab) and widget in self.source_tabs:
                    tab_name = parent_window.tabs.tabText(i)
                    tab_names[widget] = tab_name
        
        # Plot each source tab in its panel (in order specified by panel_order)
        for panel_idx, source_idx in enumerate(self.panel_order):
            if panel_idx >= len(axes_list) or source_idx >= len(self.source_tabs):
                continue
            
            ax = axes_list[panel_idx]
            source_tab = self.source_tabs[source_idx]
            
            # Apply style
            self.plot_generator.style.apply_to_axes(ax)
            
            # Initialize annotation manager for this panel (first panel only for simplicity)
            if panel_idx == 0:
                self.annotation_manager = AnnotationManager(ax)
            
            # Get tab name
            tab_name = tab_names.get(source_tab, f"Panel {source_idx + 1}")
            ax.set_title(tab_name, fontsize=10)
            
            # Copy the plot from source tab
            # We need to get the plot data from source tab and plot it
            if source_tab.datasets:
                # Get current plot settings from source tab
                # For now, just plot the datasets with their current settings
                for i, dataset in enumerate(source_tab.datasets):
                    if i >= source_tab.dataset_list.count():
                        continue
                    
                    item = source_tab.dataset_list.item(i)
                    if not isinstance(item, DatasetListItem):
                        continue
                    
                    if not item.visible:
                        continue
                    
                    # Get color
                    color = source_tab.dataset_colors[i] if i < len(source_tab.dataset_colors) else \
                        self.plot_generator.style.COLORS[i % len(self.plot_generator.style.COLORS)]
                    
                    # Get label
                    if i < len(source_tab.custom_labels) and source_tab.custom_labels[i]:
                        label = source_tab.custom_labels[i]
                    else:
                        label = dataset.get_display_name()
                        key_params = dataset.get_key_parameters()
                        if key_params:
                            label += f" ({key_params})"
                    
                    # Get axis configuration from source tab
                    x_axis = source_tab.x_axis_combo.currentText() if hasattr(source_tab, 'x_axis_combo') else "Time (s)"
                    y_axis = source_tab.y_left_combo.currentText() if hasattr(source_tab, 'y_left_combo') else "Resistance (Ω)"
                    
                    # Get processed data (with current settings from source tab)
                    crop_start = source_tab.crop_start_spin.value() if hasattr(source_tab, 'crop_start_spin') else 0
                    crop_end = source_tab.crop_end_spin.value() if hasattr(source_tab, 'crop_end_spin') else 999999
                    normalize = source_tab.normalize_check.isChecked() if hasattr(source_tab, 'normalize_check') else False
                    y_offset = source_tab.y_offset_spin.value() if hasattr(source_tab, 'y_offset_spin') else 0
                    
                    # Process data
                    processed_data = source_tab.process_data(dataset, crop_start, crop_end, normalize, y_offset)
                    
                    # Get X and Y data
                    x_data, x_label = source_tab.get_axis_data(processed_data, x_axis)
                    y_data, y_label = source_tab.get_axis_data(processed_data, y_axis)
                    
                    # Filter valid data
                    valid_mask = np.isfinite(x_data) & np.isfinite(y_data)
                    if not np.any(valid_mask):
                        continue
                    
                    x_plot = x_data[valid_mask]
                    y_plot = y_data[valid_mask]
                    
                    # Plot
                    ax.plot(x_plot, y_plot,
                           color=color,
                           linewidth=self.plot_generator.style.line_width,
                           marker='o',
                           markersize=self.plot_generator.style.marker_size,
                           label=label,
                           markevery=max(1, len(x_plot)//50))
                    
                    # Set labels
                    ax.set_xlabel(x_label)
                    ax.set_ylabel(y_label)
                    
                    # Apply log scale if source tab has it
                    if hasattr(source_tab, 'log_scale_check') and source_tab.log_scale_check.isChecked():
                        ax.set_yscale('log')
            
            # Add legend
            if hasattr(source_tab, 'legend_check') and source_tab.legend_check.isChecked():
                lines, labels = ax.get_legend_handles_labels()
                if lines:
                    ax.legend(lines, labels, loc='best', fontsize=8)
            
            # Apply grid
            if self.plot_generator.style.grid:
                ax.grid(True, alpha=0.3)
        
        # Hide unused panels
        for idx in range(num_panels, len(axes_list)):
            axes_list[idx].set_visible(False)
        
        self.figure.tight_layout()
        self.canvas.draw()
        
        if hasattr(self, 'status_label'):
            self.status_label.setText(f"Showing {num_panels} panel(s) in {rows}×{cols} layout")
    
    def refresh_from_sources(self):
        """Refresh the combined plot from source tabs"""
        self.setup_multi_panel_layout()
    
    def load_datasets(self, datasets, append=False):
        """Override to prevent direct loading - combined plots get data from source tabs"""
        pass
    
    def update_plot(self):
        """Override to use multi-panel layout"""
        self.setup_multi_panel_layout()
