"""
Yield heatmap widget for visualizing devices in a grid colored by score.

Displays devices as a color-coded grid for quick visual assessment of sample yield.
"""

import numpy as np
import matplotlib.pyplot as plt
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtCore import pyqtSignal
from typing import List, Dict, Optional
import logging

from ..data.device_data_model import DeviceData
from ..utils.plot_utils import create_mpl_canvas
from ..utils.color_themes import get_heatmap_colormap

logger = logging.getLogger(__name__)


class YieldHeatmapWidget(QWidget):
    """
    Interactive heatmap showing devices colored by memristivity score.
    
    Displays devices in a grid layout with colors representing scores.
    Clicking a cell selects that device.
    
    Signals:
        device_clicked(str): Emitted when a device is clicked (device_id)
    """
    
    #Signal
    device_clicked = pyqtSignal(str)
    
    def __init__(self, parent=None):
        """
        Initialize yield heatmap widget.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.devices = []
        self.device_grid = {}  # Map (row, col) to device_id
        self.selected_device = None
        
        self._init_ui()
    
    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create matplotlib canvas
        self.figure = plt.Figure(figsize=(6, 6), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.canvas = create_mpl_canvas(self, self.figure)
        
        # Connect click event
        self.canvas.mpl_connect('button_press_event', self._on_click)
        
        layout.addWidget(self.canvas)
        self.setLayout(layout)
        
        # Show placeholder
        self._show_placeholder()
    
    def _show_placeholder(self):
        """Show placeholder text when no data is loaded."""
        self.ax.clear()
        self.ax.text(0.5, 0.5, 'No devices loaded\nSelect a sample to view heatmap',
                    ha='center', va='center', fontsize=12, color='gray',
                    transform=self.ax.transAxes)
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.canvas.draw()
    
    def load_devices(self, devices: List[DeviceData]):
        """
        Load devices and generate heatmap.
        
        Args:
            devices: List of DeviceData objects
        """
        self.devices = devices
        
        if len(devices) == 0:
            self._show_placeholder()
            return
        
        # Generate heatmap
        self._generate_heatmap()
    
    def _generate_heatmap(self):
        """Generate and display the yield heatmap with Section vs Device Number axes."""
        # Extract device sections and numbers
        device_data = []
        for device in self.devices:
            section = device.section
            device_num = device.device_number
            score = device.memristivity_score
            device_data.append((section, device_num, score, device.device_id))
        
        if not device_data:
            self._show_placeholder()
            return
        
        # Group by section
        sections = {}
        for section, device_num, score, device_id in device_data:
            if section not in sections:
                sections[section] = {}
            sections[section][device_num] = (score, device_id)
        
        # Get list of unique sections and max device number
        section_names = sorted(sections.keys())
        all_device_nums = set()
        for section_devices in sections.values():
            all_device_nums.update(section_devices.keys())
        max_device_num = max(all_device_nums) if all_device_nums else 0
        device_nums = list(range(1, max_device_num + 1))
        
        # Create score grid: rows = sections, columns = device numbers
        num_sections = len(section_names)
        num_devices = len(device_nums)
        score_grid = np.full((num_sections, num_devices), np.nan)
        self.device_grid = {}
        
        for row_idx, section in enumerate(section_names):
            for col_idx, device_num in enumerate(device_nums):
                if device_num in sections[section]:
                    score, device_id = sections[section][device_num]
                    score_grid[row_idx, col_idx] = score
                    self.device_grid[(row_idx, col_idx)] = device_id
        
        # Plot heatmap
        self.ax.clear()
        
        # Use RdYlGn colormap (red-yellow-green)
        from ..utils.color_themes import get_heatmap_colormap
        cmap = get_heatmap_colormap('RdYlGn')
        
        im = self.ax.imshow(score_grid, cmap=cmap, vmin=0, vmax=100, 
                           aspect='auto', interpolation='nearest')
        
        # Add colorbar
        if not hasattr(self, 'colorbar') or self.colorbar is None:
            self.colorbar = self.figure.colorbar(im, ax=self.ax, fraction=0.046, pad=0.04)
            self.colorbar.set_label('Memristivity Score', rotation=270, labelpad=15, 
                                   fontweight='bold')
        else:
            self.colorbar.update_normal(im)
        
        # Add grid lines
        self.ax.set_xticks(np.arange(-0.5, num_devices, 1), minor=True)
        self.ax.set_yticks(np.arange(-0.5, num_sections, 1), minor=True)
        self.ax.grid(which='minor', color='white', linestyle='-', linewidth=2)
        
        # Set labels and title
        self.ax.set_title('Device Yield Heatmap', fontweight='bold', fontsize=13, pad=10)
        self.ax.set_xlabel('Device Number', fontsize=11, fontweight='bold')
        self.ax.set_ylabel('Section', fontsize=11, fontweight='bold')
        
        # Set tick labels
        self.ax.set_xticks(range(num_devices))
        self.ax.set_xticklabels([str(num) for num in device_nums], fontsize=9)
        self.ax.set_yticks(range(num_sections))
        self.ax.set_yticklabels(section_names, fontsize=10, fontweight='bold')
        
        # Annotate cells with scores
        for row in range(num_sections):
            for col in range(num_devices):
                if (row, col) in self.device_grid:
                    score = score_grid[row, col]
                    if not np.isnan(score):
                        # Choose text color based on score for readability
                        text_color = 'white' if score < 50 else 'black'
                        self.ax.text(col, row, f'{score:.0f}', 
                                   ha='center', va='center',
                                   color=text_color, fontsize=8, fontweight='bold')
        
        # Highlight selected device if any
        if self.selected_device:
            self._highlight_device(self.selected_device)
        
        self.figure.tight_layout()
        self.canvas.draw()
        logger.info(f"Generated heatmap: {num_sections} sections × {num_devices} devices")
    
    def _on_click(self, event):
        """
        Handle click event on heatmap.
        
        Args:
            event: Matplotlib mouse event
        """
        if event.inaxes != self.ax:
            return
        
        # Get clicked cell coordinates
        col = int(np.round(event.xdata))
        row = int(np.round(event.ydata))
        
        # Check if device exists at this position
        if (row, col) in self.device_grid:
            device_id = self.device_grid[(row, col)]
            logger.debug(f"Heatmap cell clicked: ({row}, {col}) -> {device_id}")
            self.device_clicked.emit(device_id)
    
    def highlight_device(self, device_id: str):
        """
        Highlight a specific device on the heatmap.
        
        Args:
            device_id: Device ID to highlight
        """
        self.selected_device = device_id
        self._highlight_device(device_id)
        self.canvas.draw()
    
    def _highlight_device(self, device_id: str):
        """
        Draw highlight border around selected device.
        
        Args:
            device_id: Device ID to highlight
        """
        # Find device position in grid
        for (row, col), dev_id in self.device_grid.items():
            if dev_id == device_id:
                # Draw rectangle around cell
                from matplotlib.patches import Rectangle
                rect = Rectangle((col - 0.5, row - 0.5), 1, 1, 
                               linewidth=3, edgecolor='blue', facecolor='none')
                self.ax.add_patch(rect)
                break
