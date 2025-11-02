"""
Main Application Window

PyQt6-based main window with tabs for file browsing and plotting.
"""

from PyQt6.QtWidgets import (QMainWindow, QTabWidget, QWidget, QVBoxLayout, 
                              QStatusBar, QMenuBar, QMenu, QFileDialog, QMessageBox)
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QAction, QKeySequence
from pathlib import Path
import sys

# Import custom tabs
from .file_browser_tab import FileBrowserTab
from .plotting_tab import PlottingTab
from .batch_processing_dialog import BatchProcessingDialog

class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        
        # Window setup
        self.setWindowTitle("TSP Data Analysis Tool")
        self.setGeometry(100, 100, 1600, 900)
        
        # State
        self.current_folder = None
        self.selected_files = []
        
        # Setup UI
        self.setup_ui()
        self.setup_menu_bar()
        self.setup_status_bar()
        
        # Load window state
        self.load_window_state()
    
    def setup_ui(self):
        """Setup the main UI with tabs"""
        # Central widget with tabs
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # Tab 1: File Browser & Selection
        self.file_browser_tab = FileBrowserTab(self)
        self.tabs.addTab(self.file_browser_tab, "📁 File Browser")
        
        # Tab 2: Plotting
        self.plotting_tab = PlottingTab(self)
        self.tabs.addTab(self.plotting_tab, "📊 Plotting")
        
        # Tab 3: Batch Processing
        from .batch_processing_tab import BatchProcessingTab
        self.batch_processing_tab = BatchProcessingTab(self)
        self.tabs.addTab(self.batch_processing_tab, "⚙️ Batch Processing")
        
        # Connect signals
        self.file_browser_tab.files_selected.connect(self.on_files_selected)
        
        # Set modern dark style
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
                color: #e0e0e0;
            }
            QTabWidget::pane {
                border: 1px solid #555;
                background: #3c3c3c;
            }
            QTabBar::tab {
                background: #2b2b2b;
                color: #b0b0b0;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                border: 1px solid #555;
            }
            QTabBar::tab:selected {
                background: #3c3c3c;
                color: #ffffff;
                border-bottom: 2px solid #2196F3;
            }
            QTabBar::tab:hover {
                background: #454545;
                color: #ffffff;
            }
            QWidget {
                background-color: #3c3c3c;
                color: #e0e0e0;
            }
            QLabel {
                color: #e0e0e0;
            }
            QPushButton {
                background-color: #4a4a4a;
                color: #e0e0e0;
                border: 1px solid #666;
                padding: 6px 12px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #555555;
                border: 1px solid #777;
            }
            QPushButton:pressed {
                background-color: #3a3a3a;
            }
            QLineEdit, QTextEdit {
                background-color: #2b2b2b;
                color: #e0e0e0;
                border: 1px solid #555;
                padding: 4px;
                border-radius: 3px;
            }
            QLineEdit:read-only {
                background-color: #353535;
                color: #b0b0b0;
            }
            QComboBox {
                background-color: #2b2b2b;
                color: #e0e0e0;
                border: 1px solid #555;
                padding: 4px;
                border-radius: 3px;
            }
            QComboBox:drop-down {
                border: none;
            }
            QComboBox:down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid #e0e0e0;
                margin-right: 6px;
            }
            QListWidget {
                background-color: #2b2b2b;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 3px;
            }
            QListWidget::item:selected {
                background-color: #2196F3;
                color: #ffffff;
            }
            QListWidget::item:hover {
                background-color: #454545;
            }
            QGroupBox {
                border: 1px solid #555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
                color: #b0b0b0;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                color: #b0b0b0;
            }
            QStatusBar {
                background-color: #2b2b2b;
                color: #b0b0b0;
            }
            QMenuBar {
                background-color: #2b2b2b;
                color: #e0e0e0;
            }
            QMenuBar::item:selected {
                background-color: #454545;
            }
            QMenu {
                background-color: #3c3c3c;
                color: #e0e0e0;
                border: 1px solid #555;
            }
            QMenu::item:selected {
                background-color: #2196F3;
            }
            QScrollBar:vertical {
                background: #2b2b2b;
                width: 12px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background: #555;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #666;
            }
            QScrollBar:horizontal {
                background: #2b2b2b;
                height: 12px;
                border: none;
            }
            QScrollBar::handle:horizontal {
                background: #555;
                border-radius: 6px;
                min-width: 20px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #666;
            }
        """)
    
    def setup_menu_bar(self):
        """Setup the menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        # Open folder action
        open_folder_action = QAction("Open Folder...", self)
        open_folder_action.setShortcut(QKeySequence("Ctrl+O"))
        open_folder_action.triggered.connect(self.open_folder)
        file_menu.addAction(open_folder_action)
        
        # Batch processing action
        batch_action = QAction("Batch Processing...", self)
        batch_action.setShortcut(QKeySequence("Ctrl+B"))
        batch_action.triggered.connect(self.open_batch_processing)
        file_menu.addAction(batch_action)
        
        file_menu.addSeparator()
        
        # Exit action
        exit_action = QAction("Exit", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # View menu
        view_menu = menubar.addMenu("&View")
        
        # Refresh action
        refresh_action = QAction("Refresh", self)
        refresh_action.setShortcut(QKeySequence("F5"))
        refresh_action.triggered.connect(self.refresh_files)
        view_menu.addAction(refresh_action)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        # About action
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def setup_status_bar(self):
        """Setup the status bar"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
    
    def open_folder(self):
        """Open folder dialog and load files"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Folder with TSP Data Files",
            str(Path.home()),
            QFileDialog.Option.ShowDirsOnly
        )
        
        if folder:
            self.current_folder = Path(folder)
            self.file_browser_tab.load_folder(self.current_folder)
            self.status_bar.showMessage(f"Loaded folder: {folder}")
    
    def refresh_files(self):
        """Refresh the file list"""
        if self.current_folder:
            self.file_browser_tab.load_folder(self.current_folder)
            self.status_bar.showMessage("Files refreshed")
    
    def open_batch_processing(self):
        """Open batch processing dialog"""
        dialog = BatchProcessingDialog(self)
        dialog.exec()
    
    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            "About TSP Data Analysis Tool",
            "<h3>TSP Data Analysis Tool</h3>"
            "<p>Version 1.0</p>"
            "<p>A tool for analyzing and plotting Keithley 2450 TSP pulse test data.</p>"
            "<p>Features:</p>"
            "<ul>"
            "<li>Browse and preview TSP data files</li>"
            "<li>Compare multiple measurements</li>"
            "<li>Advanced plotting and analysis</li>"
            "<li>Export to various formats</li>"
            "<li>Batch processing</li>"
            "</ul>"
        )
    
    def load_window_state(self):
        """Load saved window state"""
        settings = QSettings("TSP_Analysis", "MainWindow")
        
        # Window geometry
        geometry = settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        
        # Window state (maximized, etc.)
        state = settings.value("windowState")
        if state:
            self.restoreState(state)
    
    def save_window_state(self):
        """Save window state"""
        settings = QSettings("TSP_Analysis", "MainWindow")
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())
    
    def on_files_selected(self, tsp_datasets):
        """Handle files selected from file browser"""
        # Load datasets into plotting tab
        self.plotting_tab.load_datasets(tsp_datasets)
        
        # Switch to plotting tab
        self.tabs.setCurrentWidget(self.plotting_tab)
        
        # Update status
        self.status_bar.showMessage(f"Loaded {len(tsp_datasets)} dataset(s) for plotting")
    
    def closeEvent(self, event):
        """Handle window close event"""
        self.save_window_state()
        event.accept()

