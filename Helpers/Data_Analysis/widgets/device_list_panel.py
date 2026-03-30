"""
Device list panel widget for displaying and selecting devices.

Shows a scrollable list of devices with classification, score, and status indicators.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QLabel
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QFont
from typing import List, Optional
import logging

from ..data.device_data_model import DeviceData
from ..utils.color_themes import score_to_color, classification_to_color

logger = logging.getLogger(__name__)


class DeviceListPanelWidget(QWidget):
    """
    Scrollable list panel displaying devices with selection support.
    
    Each list item shows:
    - Device ID
    - Classification badge with color and score
    - Status icon (✓/⚠/✗)
    
    Signals:
        device_selected(DeviceData): Emitted when device is selected
        device_double_clicked(DeviceData): Emitted on double-click
    """
    
    # Signals
    device_selected = pyqtSignal(object)  # DeviceData object
    device_double_clicked = pyqtSignal(object)  # DeviceData object
    
    def __init__(self, parent=None):
        """
        Initialize device list panel.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.devices = []  # List of DeviceData objects
        self.device_items = {}  # Map device_id to QListWidgetItem
        
        self._init_ui()
    
    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Title
        self.title_label = QLabel("<b>Devices</b> (0)")
        layout.addWidget(self.title_label)
        
        # List widget
        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid #ccc;
                border-radius: 3px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
                color: black;
            }
            QListWidget::item:hover {
                background-color: #f5f5f5;
            }
        """)
        layout.addWidget(self.list_widget)
        
        self.setLayout(layout)
    
    def load_devices(self, devices: List[DeviceData]):
        """
        Load devices into the list.
        
        Args:
            devices: List of DeviceData objects
        """
        # Clear existing items
        self.list_widget.clear()
        self.device_items.clear()
        self.devices = devices
        
        # Add devices to list
        for device in devices:
            self._add_device_item(device)
        
        # Update title
        self.title_label.setText(f"<b>Devices</b> ({len(devices)})")
        
        logger.info(f"Loaded {len(devices)} devices into list")
    
    def _add_device_item(self, device: DeviceData):
        """
        Add a device to the list widget.
        
        Args:
            device: DeviceData object
        """
        # Create list item
        item = QListWidgetItem()
        
        # Format the display text
        # Line 1: Device ID
        # Line 2: Classification | Score
        #Line 3: Status icon
        
        classification = device.current_classification.device_type
        score_str = device.get_score_for_display()
        status_icon = device.get_status_icon()
        
        # Get classification color
        class_color = classification_to_color(classification)
        
        # Create HTML formatted text
        text = f"""
        <div style='line-height: 1.3;'>
            <span style='font-size: 11pt; font-weight: bold;'>{device.device_id}</span><br>
            <span style='color: {class_color}; font-weight: bold;'>● {classification}</span> 
            <span style='color: gray;'>|</span> 
            <span style='font-weight: bold;'>{score_str}</span><br>
            <span style='font-size: 14pt;'>{status_icon}</span>
        </div>
        """
        
        # Since QListWidgetItem doesn't support HTML rendering directly,
        # we'll use a simpler text format
        simple_text = f"{device.device_id}\n{classification} | {score_str}  {status_icon}"
        
        item.setText(simple_text)
        item.setData(Qt.UserRole, device)  # Store device data
        
        # Set font
        font = QFont()
        font.setPointSize(9)
        item.setFont(font)
        
        # Add to list
        self.list_widget.addItem(item)
        self.device_items[device.device_id] = item
    
    def _on_item_clicked(self, item: QListWidgetItem):
        """
        Handle item click event.
        
        Args:
            item: Clicked list item
        """
        device = item.data(Qt.UserRole)
        if device:
            logger.debug(f"Device selected: {device.device_id}")
            self.device_selected.emit(device)
    
    def _on_item_double_clicked(self, item: QListWidgetItem):
        """
        Handle item double-click event.
        
        Args:
            item: Double-clicked list item
        """
        device = item.data(Qt.UserRole)
        if device:
            logger.debug(f"Device double-clicked: {device.device_id}")
            self.device_double_clicked.emit(device)
    
    def select_device(self, device_id: str):
        """
        Programmatically select a device by ID.
        
        Args:
            device_id: Device ID to select
        """
        if device_id in self.device_items:
            item = self.device_items[device_id]
            self.list_widget.setCurrentItem(item)
            self.list_widget.scrollToItem(item)
    
    def get_selected_device(self) -> Optional[DeviceData]:
        """
        Get currently selected device.
        
        Returns:
            Selected DeviceData object, or None if no selection
        """
        current_item = self.list_widget.currentItem()
        if current_item:
            return current_item.data(Qt.UserRole)
        return None
    
    def filter_devices(self, device_types: List[str], min_score: float, max_score: float):
        """
        Filter displayed devices by type and score.
        
        Args:
            device_types: List of device types to include
            min_score: Minimum score threshold
            max_score: Maximum score threshold
        """
        visible_count = 0
        
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            device = item.data(Qt.UserRole)
            
            # Check if device matches filter criteria
            type_match = device.current_classification.device_type in device_types
            score_match = min_score <= device.memristivity_score <= max_score
            
            # Show/hide item
            item.setHidden(not (type_match and score_match))
            
            if type_match and score_match:
                visible_count += 1
        
        # Update title
        total_count = len(self.devices)
        if visible_count < total_count:
            self.title_label.setText(f"<b>Devices</b> ({visible_count}/{total_count})")
        else:
            self.title_label.setText(f"<b>Devices</b> ({total_count})")
        
        logger.debug(f"Filtered devices: {visible_count}/{total_count} visible")
    
    def auto_select_best_device(self):
        """
        Automatically select the device with the highest score.
        """
        if len(self.devices) == 0:
            return
        
        # Find device with highest score
        best_device = max(self.devices, key=lambda d: d.memristivity_score)
        
        # Select it
        self.select_device(best_device.device_id)
        
        logger.info(f"Auto-selected best device: {best_device.device_id} (score: {best_device.memristivity_score:.1f})")
