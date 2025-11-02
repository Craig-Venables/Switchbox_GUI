"""
Batch Processing Tab

Tab version of batch processing dialog - embedded in main window.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QGroupBox
from PyQt6.QtCore import Qt
from .batch_processing_dialog import BatchProcessingDialog


class BatchProcessingTab(QWidget):
    """Tab version of batch processing - opens dialog"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Instructions section
        instructions_group = QGroupBox("📖 Batch Processing")
        instructions_layout = QVBoxLayout()
        
        info_label = QLabel(
            "<h3>Process Multiple Files at Once</h3>"
            "<p>Batch processing allows you to:</p>"
            "<ul>"
            "<li>Process all .txt files in a folder (optionally recursively)</li>"
            "<li>Generate plots for all files automatically</li>"
            "<li>Calculate and export statistics to CSV</li>"
            "<li>Filter by test type if needed</li>"
            "</ul>"
            "<p><b>Output Structure:</b></p>"
            "<ul>"
            "<li>Plots → <i>output_folder/plots/</i></li>"
            "<li>Statistics → <i>output_folder/statistics/batch_summary_*.csv</i></li>"
            "</ul>"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("""
            QLabel {
                color: #e0e0e0;
                padding: 20px;
                background-color: #2b2b2b;
                border: 1px solid #555;
                border-radius: 5px;
                font-size: 11pt;
            }
        """)
        instructions_layout.addWidget(info_label)
        
        instructions_group.setLayout(instructions_layout)
        layout.addWidget(instructions_group)
        
        # Button to open batch processing dialog
        button_group = QGroupBox("")
        button_layout = QVBoxLayout()
        button_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        open_dialog_btn = QPushButton("🚀 Open Batch Processing Dialog")
        open_dialog_btn.setMinimumHeight(50)
        open_dialog_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: #ffffff;
                font-size: 14pt;
                font-weight: bold;
                padding: 15px 30px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #0D47A1;
            }
        """)
        open_dialog_btn.clicked.connect(self.open_batch_dialog)
        button_layout.addWidget(open_dialog_btn)
        
        # Shortcut hint
        shortcut_label = QLabel("(Or press <b>Ctrl+B</b> from anywhere)")
        shortcut_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        shortcut_label.setStyleSheet("color: #888; padding: 10px;")
        button_layout.addWidget(shortcut_label)
        
        button_group.setLayout(button_layout)
        layout.addWidget(button_group)
        
        layout.addStretch()
    
    def open_batch_dialog(self):
        """Open the batch processing dialog"""
        dialog = BatchProcessingDialog(self)
        dialog.exec()

