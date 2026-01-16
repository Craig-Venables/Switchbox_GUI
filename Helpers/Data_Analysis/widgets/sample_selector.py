"""
Sample selector widget for browsing and selecting sample folders.

Provides a simple folder selection interface that emits signals when
a sample is selected.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFileDialog
)
from PyQt5.QtCore import pyqtSignal
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class SampleSelectorWidget(QWidget):
    """
    Widget for selecting sample directories.
    
    Signals:
        sample_selected(str): Emitted when a valid sample folder is selected
    """
    
    # Signal emitted when sample is selected
    sample_selected = pyqtSignal(str)
    
    def __init__(self, parent=None):
        """
        Initialize sample selector widget.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.current_sample_path = None
        # Default to OneDrive data folder
        self.last_directory = r"C:\Users\Craig-Desktop\OneDrive - The University of Nottingham\Documents\Data_folder"
        
        self._init_ui()
    
    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Title label
        title_label = QLabel("<b>Sample Selection</b>")
        layout.addWidget(title_label)
        
        # Browse button
        button_layout = QHBoxLayout()
        self.browse_button = QPushButton("📁 Browse Sample...")
        self.browse_button.setToolTip("Select sample folder containing device data")
        self.browse_button.clicked.connect(self._browse_sample)
        button_layout.addWidget(self.browse_button)
        layout.addLayout(button_layout)
        
        # Selected path label
        self.path_label = QLabel("<i>No sample selected</i>")
        self.path_label.setWordWrap(True)
        self.path_label.setStyleSheet("color: gray; padding: 5px;")
        layout.addWidget(self.path_label)
        
        # Add stretch to push everything to top
        layout.addStretch()
        
        self.setLayout(layout)
    
    def _browse_sample(self):
        """Open file dialog to browse for sample folder."""
        # Get starting directory (prioritize OneDrive data folder)
        default_data_folder = Path(r"C:\Users\Craig-Desktop\OneDrive - The University of Nottingham\Documents\Data_folder")
        
        if default_data_folder.exists():
            start_dir = str(default_data_folder)
        elif self.last_directory:
            start_dir = self.last_directory
        else:
            start_dir = str(Path.home())
        
        # Open folder selection dialog
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Sample Folder",
            start_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if folder_path:
            self._select_sample(folder_path)
    
    def _select_sample(self, folder_path: str):
        """
        Handle sample folder selection.
        
        Args:
            folder_path: Path to selected sample folder
        """
        sample_path = Path(folder_path)
        
        # Validate folder exists
        if not sample_path.exists():
            logger.warning(f"Selected path does not exist: {folder_path}")
            self.path_label.setText("<i>Invalid path</i>")
            self.path_label.setStyleSheet("color: red; padding: 5px;")
            return
        
        # Update current path
        self.current_sample_path = sample_path
        self.last_directory = str(sample_path.parent)
        
        # Update UI
        sample_name = sample_path.name
        self.path_label.setText(f"<b>{sample_name}</b><br><small>{folder_path}</small>")
        self.path_label.setStyleSheet("color: black; padding: 5px; background-color: #e8f5e9; border-radius: 3px;")
        
        # Emit signal
        logger.info(f"Sample selected: {sample_name}")
        self.sample_selected.emit(str(sample_path))
    
    def get_current_sample(self) -> Path:
        """
        Get currently selected sample path.
        
        Returns:
            Path to current sample, or None if no sample selected
        """
        return self.current_sample_path
    
    def set_sample(self, sample_path: str):
        """
        Programmatically set the sample path.
        
        Args:
            sample_path: Path to sample folder
        """
        self._select_sample(sample_path)
