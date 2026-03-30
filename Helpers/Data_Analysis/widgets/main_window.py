"""
Main window for Device Analysis Visualizer application.

Integrates all widgets into a cohesive Qt5 application with navigation and visualization panels.
"""

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTabWidget, QAction, QMessageBox, QStatusBar, QApplication
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon
from pathlib import Path
from typing import Optional, Dict
import logging

from ..data.device_data_model import DeviceData
from ..data.data_loader import DataLoader
from ..data.data_discovery import DataDiscovery
from .sample_selector import SampleSelectorWidget
from .filter_panel import FilterPanelWidget, FilterCriteria
from .device_list_panel import DeviceListPanelWidget
from .overview_tab import OverviewTab
from .plots_tab import PlotsTab
from .metrics_tab import MetricsTab
from .classification_tab import ClassificationTab

logger = logging.getLogger(__name__)


class DataLoadingThread(QThread):
    """Background thread for loading sample data without freezing UI."""
    
    # Signals
    loading_complete = pyqtSignal(dict)  # Dict[device_id, DeviceData]
    loading_error = pyqtSignal(str)  # Error message
    
    def __init__(self, sample_path: Path):
        super().__init__()
        self.sample_path = sample_path
    
    def run(self):
        """Load sample data in background thread."""
        try:
            logger.info(f"Loading sample in background: {self.sample_path}")
            devices = DataLoader.load_sample(self.sample_path)
            self.loading_complete.emit(devices)
        except Exception as e:
            logger.error(f"Error loading sample: {e}")
            self.loading_error.emit(str(e))


class MainWindow(QMainWindow):
    """
    Main application window for Device Analysis Visualizer.
    
    Layout:
    - Left panel: Sample selector, filter panel, device list
    - Center panel: Tabbed visualization (Overview, Plots, Metrics, Classification)
    - Right sidebar: Optional quick stats (future)
    """
    
    def __init__(self):
        """Initialize main window."""
        super().__init__()
        
        self.devices = {}  # Dict[device_id, DeviceData]
        self.filtered_devices = []  # List of filtered DeviceData
        self.current_device = None
        self.loading_thread = None
        
        self._init_ui()
        self._connect_signals()
        
        logger.info("Main window initialized")
    
    def _init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Device Analysis Visualizer")
        self.setGeometry(100, 100, 1400, 900)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create main layout
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Create horizontal splitter for left panel and center panel
        splitter = QSplitter(Qt.Horizontal)
        
        # === LEFT PANEL ===
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Sample selector
        self.sample_selector = SampleSelectorWidget()
        left_layout.addWidget(self.sample_selector)
        
        # Filter panel
        self.filter_panel = FilterPanelWidget()
        left_layout.addWidget(self.filter_panel)
        
        # Device list
        self.device_list = DeviceListPanelWidget()
        left_layout.addWidget(self.device_list, stretch=1)
        
        left_panel.setLayout(left_layout)
        splitter.addWidget(left_panel)
        
        # === CENTER PANEL ===
        center_panel = QWidget()
        center_layout = QVBoxLayout()
        center_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create tab widget for different views
        self.tab_widget = QTabWidget()
        
        # Create tabs
        self.overview_tab = OverviewTab()
        self.plots_tab = PlotsTab()
        self.metrics_tab = MetricsTab()
        self.classification_tab = ClassificationTab()
        
        # Add tabs
        self.tab_widget.addTab(self.overview_tab, "📊 Overview")
        self.tab_widget.addTab(self.plots_tab, "📈 Plots")
        self.tab_widget.addTab(self.metrics_tab, "📉 Metrics")
        self.tab_widget.addTab(self.classification_tab, "🔬 Classification")
        
        center_layout.addWidget(self.tab_widget)
        center_panel.setLayout(center_layout)
        splitter.addWidget(center_panel)
        
        # Set splitter sizes (left panel smaller than center)
        splitter.setSizes([300, 1100])
        
        main_layout.addWidget(splitter)
        central_widget.setLayout(main_layout)
        
        # Create menu bar
        self._create_menu_bar()
        
        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
    
    def _create_menu_bar(self):
        """Create application menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        open_action = QAction("&Open Sample...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.sample_selector._browse_sample)
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # View menu
        view_menu = menubar.addMenu("&View")
        
        refresh_action = QAction("&Refresh", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self._refresh_current_sample)
        view_menu.addAction(refresh_action)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
    
    def _connect_signals(self):
        """Connect all widget signals to handlers."""
        # Sample selector
        self.sample_selector.sample_selected.connect(self._on_sample_selected)
        
        # Filter panel
        self.filter_panel.filter_changed.connect(self._on_filter_changed)
        
        # Device list
        self.device_list.device_selected.connect(self._on_device_selected)
        
        # Heatmap
        self.overview_tab.heatmap_widget.device_clicked.connect(self._on_heatmap_device_clicked)
    
    def _on_sample_selected(self, sample_path: str):
        """
        Handle sample selection.
        
        Args:
            sample_path: Path to selected sample folder
        """
        logger.info(f"Sample selected: {sample_path}")
        self.status_bar.showMessage(f"Loading sample: {Path(sample_path).name}...")
        
        # Load sample in background thread
        self.loading_thread = DataLoadingThread(Path(sample_path))
        self.loading_thread.loading_complete.connect(self._on_sample_loaded)
        self.loading_thread.loading_error.connect(self._on_sample_load_error)
        self.loading_thread.start()
        
        # Disable UI while loading
        self.sample_selector.setEnabled(False)
        QApplication.setOverrideCursor(Qt.WaitCursor)
    
    def _on_sample_loaded(self, devices: Dict[str, DeviceData]):
        """
        Handle sample loading completion.
        
        Args:
            devices: Dictionary of loaded devices
        """
        logger.info(f"Sample loaded: {len(devices)} devices")
        self.devices = devices
        self.filtered_devices = list(devices.values())
        
        # Load devices into list
        self.device_list.load_devices(self.filtered_devices)
        
        # Load devices into heatmap
        self.overview_tab.load_devices(self.filtered_devices)
        
        # Auto-select best device
        if len(self.filtered_devices) > 0:
            self.device_list.auto_select_best_device()
        
        # Re-enable UI
        self.sample_selector.setEnabled(True)
        QApplication.restoreOverrideCursor()
        
        # Update status
        self.status_bar.showMessage(f"Loaded {len(devices)} devices", 3000)
    
    def _on_sample_load_error(self, error_msg: str):
        """
        Handle sample loading error.
        
        Args:
            error_msg: Error message
        """
        logger.error(f"Sample load error: {error_msg}")
        
        # Re-enable UI
        self.sample_selector.setEnabled(True)
        QApplication.restoreOverrideCursor()
        
        # Show error message
        QMessageBox.critical(self, "Loading Error", 
                           f"Failed to load sample:\n{error_msg}")
        
        self.status_bar.showMessage("Error loading sample", 5000)
    
    def _on_filter_changed(self, criteria: FilterCriteria):
        """
        Handle filter criteria change.
        
        Args:
            criteria: New filter criteria
        """
        # Apply filters to device list
        self.device_list.filter_devices(
            criteria.device_types,
            criteria.min_score,
            criteria.max_score
        )
        
        logger.debug(f"Filters applied: {len(criteria.device_types)} types, "
                    f"score {criteria.min_score}-{criteria.max_score}")
    
    def _on_device_selected(self, device: DeviceData):
        """
        Handle device selection from list.
        
        Args:
            device: Selected device
        """
        self.current_device = device
        logger.info(f"Device selected: {device.device_id}")
        
        # Update all tabs
        self.overview_tab.update_device(device)
        self.plots_tab.update_device(device)
        self.metrics_tab.update_device(device)
        self.classification_tab.update_device(device)
        
        # Update status bar
        self.status_bar.showMessage(
            f"Device: {device.device_id} | "
            f"Classification: {device.current_classification.device_type} | "
            f"Score: {device.memristivity_score:.1f}"
        )
    
    def _on_heatmap_device_clicked(self, device_id: str):
        """
        Handle device click from heatmap.
        
        Args:
            device_id: Clicked device ID
        """
        # Select device in list
        self.device_list.select_device(device_id)
    
    def _refresh_current_sample(self):
        """Refresh current sample by reloading."""
        current_sample = self.sample_selector.get_current_sample()
        if current_sample:
            self._on_sample_selected(str(current_sample))
        else:
            QMessageBox.information(self, "Refresh", "No sample loaded to refresh.")
    
    def _show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About Device Analysis Visualizer",
            "<h2>Device Analysis Visualizer</h2>"
            "<p>Version 1.0.0</p>"
            "<p>A Qt5 application for visualizing device analysis data with "
            "dynamic data discovery and comprehensive visualizations.</p>"
            "<p><b>Features:</b></p>"
            "<ul>"
            "<li>Interactive yield heatmap</li>"
            "<li>I-V curve visualization</li>"
            "<li>Metrics analysis and comparison</li>"
            "<li>Classification breakdown</li>"
            "</ul>"
            "<p>© 2026 Switchbox GUI Team</p>"
        )
    
    def closeEvent(self, event):
        """Handle window close event."""
        # Stop loading thread if running
        if self.loading_thread and self.loading_thread.isRunning():
            self.loading_thread.terminate()
            self.loading_thread.wait()
        
        event.accept()
        logger.info("Application closed")
