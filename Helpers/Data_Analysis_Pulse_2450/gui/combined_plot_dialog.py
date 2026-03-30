"""
Combined Plot Dialog

Dialog for selecting datasets from multiple plotting tabs to combine into one plot.
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                              QLabel, QListWidget, QListWidgetItem, QDialogButtonBox,
                              QGroupBox, QMessageBox)
from PyQt6.QtCore import Qt
from typing import List
from .plotting_tab import PlottingTab


class CombinedPlotDialog(QDialog):
    """Dialog for selecting plotting tabs to combine into multi-panel layout"""
    
    def __init__(self, parent, plotting_tabs: List[PlottingTab]):
        super().__init__(parent)
        self.plotting_tabs = plotting_tabs
        self.selected_tabs: List[PlottingTab] = []
        self.parent_window = parent
        
        self.setWindowTitle("Create Combined Plot - Select Tabs")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        self.setup_ui()
        self.populate_list()
    
    def setup_ui(self):
        """Setup the dialog UI"""
        layout = QVBoxLayout(self)
        
        # Instructions
        info_label = QLabel(
            "Select plotting tabs to combine. Each selected tab will become a panel in a multi-panel layout.\n"
            "You can rearrange the panel order later, but the data in each panel is locked."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("padding: 10px; background-color: #3c3c3c; border-radius: 5px; margin-bottom: 10px;")
        layout.addWidget(info_label)
        
        # List widget for tabs
        list_group = QGroupBox("Available Plotting Tabs")
        list_layout = QVBoxLayout()
        
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.list_widget.setAlternatingRowColors(True)
        
        # Style the list
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #2b2b2b;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 3px;
            }
            QListWidget::item {
                padding: 8px;
            }
            QListWidget::item:selected {
                background-color: #2196F3;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #454545;
            }
        """)
        
        list_layout.addWidget(self.list_widget)
        list_group.setLayout(list_layout)
        layout.addWidget(list_group, 1)
        
        # Selection buttons
        button_layout = QHBoxLayout()
        
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self.select_all)
        button_layout.addWidget(select_all_btn)
        
        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(self.deselect_all)
        button_layout.addWidget(deselect_all_btn)
        
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        # Status label
        self.status_label = QLabel("No tabs selected")
        self.status_label.setStyleSheet("color: #888; padding: 5px;")
        layout.addWidget(self.status_label)
        
        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept_selection)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        # Connect list selection changed signal
        self.list_widget.itemSelectionChanged.connect(self.update_status)
    
    def populate_list(self):
        """Populate list with plotting tabs"""
        self.list_widget.clear()
        
        # Get tab names from parent (main window)
        tab_names = {}
        if hasattr(self.parent_window, 'tabs'):
            for i in range(self.parent_window.tabs.count()):
                widget = self.parent_window.tabs.widget(i)
                if isinstance(widget, PlottingTab) and widget in self.plotting_tabs:
                    tab_name = self.parent_window.tabs.tabText(i)
                    tab_names[widget] = tab_name
        
        # Add tabs to list
        for tab in self.plotting_tabs:
            if not tab.datasets:
                continue  # Skip tabs with no data
            
            # Get tab name
            if tab in tab_names:
                tab_name = tab_names[tab]
            else:
                # Fallback: try to find index in plotting_tabs
                try:
                    idx = self.plotting_tabs.index(tab)
                    tab_name = f"Plotting Tab {idx + 1}"
                except ValueError:
                    tab_name = "Plotting Tab"
            
            # Count datasets
            num_datasets = len(tab.datasets)
            
            # Create list item
            item = QListWidgetItem(f"📊 {tab_name} ({num_datasets} dataset{'s' if num_datasets != 1 else ''})")
            item.setData(Qt.ItemDataRole.UserRole, tab)
            self.list_widget.addItem(item)
    
    def select_all(self):
        """Select all tabs"""
        self.list_widget.selectAll()
        self.update_status()
    
    def deselect_all(self):
        """Deselect all tabs"""
        self.list_widget.clearSelection()
        self.update_status()
    
    def update_status(self):
        """Update status label with selection count"""
        count = len(self.list_widget.selectedItems())
        
        if count == 0:
            self.status_label.setText("No tabs selected")
        elif count == 1:
            self.status_label.setText("1 tab selected")
        else:
            self.status_label.setText(f"{count} tabs selected")
    
    def accept_selection(self):
        """Accept selection and collect selected tabs"""
        selected_items = self.list_widget.selectedItems()
        
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select at least one plotting tab to combine.")
            return
        
        self.selected_tabs = []
        for item in selected_items:
            tab = item.data(Qt.ItemDataRole.UserRole)
            if tab:
                self.selected_tabs.append(tab)
        
        self.accept()
    
    def get_selected_tabs(self) -> List[PlottingTab]:
        """Get list of selected PlottingTab objects"""
        return self.selected_tabs

