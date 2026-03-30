"""
Label Editor Dialog

Dialog for editing dataset labels, sample names, and legend text.
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                              QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
                              QDialogButtonBox, QGroupBox)
from PyQt6.QtCore import Qt
from typing import List
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.data_parser import TSPData


class LabelEditorDialog(QDialog):
    """Dialog for editing dataset labels"""
    
    def __init__(self, datasets: List[TSPData], parent=None):
        super().__init__(parent)
        
        self.datasets = datasets
        self.custom_labels = [None] * len(datasets)  # Store custom labels
        self.custom_samples = [None] * len(datasets)  # Store custom sample names
        
        self.setWindowTitle("Edit Dataset Labels")
        self.setMinimumWidth(700)
        self.setMinimumHeight(500)
        
        self.setup_ui()
        self.populate_table()
    
    def setup_ui(self):
        """Setup the UI"""
        layout = QVBoxLayout(self)
        
        # Instructions
        instructions = QLabel(
            "Edit labels and sample names for each dataset.\n"
            "Leave blank to use default values."
        )
        instructions.setStyleSheet("color: #888; padding: 10px;")
        layout.addWidget(instructions)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([
            "Filename", "Original Sample", "Custom Sample", "Custom Legend Label"
        ])
        
        # Set column widths
        self.table.setColumnWidth(0, 200)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(2, 150)
        self.table.setColumnWidth(3, 200)
        
        layout.addWidget(self.table, 1)
        
        # Quick actions
        actions_group = QGroupBox("Quick Actions")
        actions_layout = QHBoxLayout()
        
        apply_sample_btn = QPushButton("Apply Sample to All")
        apply_sample_btn.clicked.connect(self.apply_sample_to_all)
        apply_sample_btn.setToolTip("Copy first dataset's sample name to all")
        actions_layout.addWidget(apply_sample_btn)
        
        clear_custom_btn = QPushButton("Clear All Custom")
        clear_custom_btn.clicked.connect(self.clear_all_custom)
        clear_custom_btn.setToolTip("Remove all custom labels and samples")
        actions_layout.addWidget(clear_custom_btn)
        
        actions_layout.addStretch()
        actions_group.setLayout(actions_layout)
        layout.addWidget(actions_group)
        
        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def populate_table(self):
        """Populate table with dataset information"""
        self.table.setRowCount(len(self.datasets))
        
        for i, data in enumerate(self.datasets):
            # Filename (read-only)
            filename_item = QTableWidgetItem(data.filename)
            filename_item.setFlags(filename_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            filename_item.setBackground(Qt.GlobalColor.darkGray)
            self.table.setItem(i, 0, filename_item)
            
            # Original sample (read-only)
            sample_item = QTableWidgetItem(data.sample)
            sample_item.setFlags(sample_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            sample_item.setBackground(Qt.GlobalColor.darkGray)
            self.table.setItem(i, 1, sample_item)
            
            # Custom sample (editable)
            custom_sample_item = QTableWidgetItem("")
            custom_sample_item.setForeground(Qt.GlobalColor.gray)
            self.table.setItem(i, 2, custom_sample_item)
            
            # Custom label (editable)
            custom_label_item = QTableWidgetItem("")
            custom_label_item.setForeground(Qt.GlobalColor.gray)
            self.table.setItem(i, 3, custom_label_item)
    
    def apply_sample_to_all(self):
        """Apply first dataset's custom sample (or original) to all"""
        if not self.datasets:
            return
        
        # Get first row's custom sample, or fall back to original
        first_custom = self.table.item(0, 2).text()
        sample_to_apply = first_custom if first_custom else self.datasets[0].sample
        
        # Apply to all rows
        for i in range(self.table.rowCount()):
            self.table.item(i, 2).setText(sample_to_apply)
    
    def clear_all_custom(self):
        """Clear all custom labels and samples"""
        for i in range(self.table.rowCount()):
            self.table.item(i, 2).setText("")
            self.table.item(i, 3).setText("")
    
    def get_custom_data(self):
        """Get the custom labels and samples"""
        custom_labels = []
        custom_samples = []
        
        for i in range(self.table.rowCount()):
            # Custom sample
            custom_sample = self.table.item(i, 2).text()
            custom_samples.append(custom_sample if custom_sample else None)
            
            # Custom label
            custom_label = self.table.item(i, 3).text()
            custom_labels.append(custom_label if custom_label else None)
        
        return custom_labels, custom_samples

