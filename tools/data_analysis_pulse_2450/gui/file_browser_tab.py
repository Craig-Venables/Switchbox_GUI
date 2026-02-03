"""
File Browser Tab

Tab for browsing folders, previewing files, and selecting datasets for analysis.
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                              QLabel, QListWidget, QListWidgetItem, QFileDialog,
                              QGroupBox, QTextEdit, QSplitter, QComboBox,
                              QLineEdit, QScrollArea, QGridLayout, QCheckBox)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont
from pathlib import Path
from typing import List, Optional
import sys
import re

# Matplotlib for thumbnail preview
import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.data_parser import parse_tsp_file, TSPData
from core.test_type_registry import get_registry
from utils.settings import get_settings


def natural_sort_key(text: str) -> tuple:
    """
    Generate a sort key for natural/numeric sorting.
    
    Converts strings like "file10.txt" to (('file',), (10,), ('.txt',))
    so that numeric parts are sorted numerically rather than alphabetically.
    
    Example:
        "file1.txt" -> (('file',), (1,), ('.txt',))
        "file10.txt" -> (('file',), (10,), ('.txt',))
        "file2.txt" -> (('file',), (2,), ('.txt',))
    
    This ensures: file1.txt < file2.txt < file10.txt (not file1.txt < file10.txt < file2.txt)
    """
    def convert(text_part):
        return int(text_part) if text_part.isdigit() else text_part.lower()
    
    return tuple(convert(c) for c in re.split(r'(\d+)', text))


class FileListItem(QListWidgetItem):
    """Custom list item that stores TSPData"""
    
    def __init__(self, tsp_data: TSPData):
        super().__init__()
        self.tsp_data = tsp_data
        
        # Display text
        display_name = tsp_data.filename
        if tsp_data.sample and tsp_data.sample != "Unknown":
            display_name = f"{tsp_data.sample} - {display_name}"
        
        self.setText(display_name)
        
        # Store for sorting/filtering
        self.test_type = tsp_data.test_name


class FileBrowserTab(QWidget):
    """File browser and selection tab"""
    
    # Signals
    files_selected = pyqtSignal(list)  # Emits list of TSPData objects
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.current_folder: Optional[Path] = None
        self.all_files: List[TSPData] = []
        self.selected_data: List[TSPData] = []
        
        # Auto-refresh state
        self.auto_refresh_enabled = False
        self.file_timestamps = {}  # Track file modification times
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.check_for_changes)
        self.refresh_interval_ms = 2000  # Check every 2 seconds
        
        self.setup_ui()
        self.load_recent_folders()
    
    def setup_ui(self):
        """Setup the UI"""
        layout = QVBoxLayout(self)
        
        # Top section: Folder selection
        folder_group = QGroupBox("Folder Selection")
        folder_layout = QVBoxLayout()
        
        # Current folder display
        folder_path_layout = QHBoxLayout()
        folder_path_layout.addWidget(QLabel("Current Folder:"))
        self.folder_path_label = QLineEdit()
        self.folder_path_label.setReadOnly(True)
        self.folder_path_label.setPlaceholderText("No folder selected")
        folder_path_layout.addWidget(self.folder_path_label, 1)
        
        browse_btn = QPushButton("📁 Browse...")
        browse_btn.clicked.connect(self.browse_folder)
        folder_path_layout.addWidget(browse_btn)
        
        folder_layout.addLayout(folder_path_layout)
        
        # Recent folders dropdown
        recent_layout = QHBoxLayout()
        recent_layout.addWidget(QLabel("Recent Folders:"))
        self.recent_folders_combo = QComboBox()
        self.recent_folders_combo.currentTextChanged.connect(self.load_recent_folder)
        recent_layout.addWidget(self.recent_folders_combo, 1)
        folder_layout.addLayout(recent_layout)
        
        # Auto-refresh toggle
        refresh_layout = QHBoxLayout()
        self.auto_refresh_checkbox = QCheckBox("🔄 Auto-refresh folder (every 2s)")
        self.auto_refresh_checkbox.setChecked(False)
        self.auto_refresh_checkbox.toggled.connect(self.toggle_auto_refresh)
        refresh_layout.addWidget(self.auto_refresh_checkbox)
        refresh_layout.addStretch()
        self.refresh_status_label = QLabel("")
        self.refresh_status_label.setStyleSheet("color: #4CAF50; font-size: 10px;")
        refresh_layout.addWidget(self.refresh_status_label)
        folder_layout.addLayout(refresh_layout)
        
        folder_group.setLayout(folder_layout)
        layout.addWidget(folder_group)
        
        # Middle section: File list and preview (splitter)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left: File list with filter
        file_list_widget = QWidget()
        file_list_layout = QVBoxLayout(file_list_widget)
        
        # Filter controls
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter by test type:"))
        self.test_type_filter = QComboBox()
        self.test_type_filter.addItem("All Test Types")
        self.test_type_filter.currentTextChanged.connect(self.apply_filter)
        filter_layout.addWidget(self.test_type_filter, 1)
        file_list_layout.addLayout(filter_layout)
        
        # File list
        file_list_layout.addWidget(QLabel(f"Files (click to select):"))
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.file_list.itemSelectionChanged.connect(self.on_selection_changed)
        self.file_list.currentItemChanged.connect(self.on_current_item_changed)
        file_list_layout.addWidget(self.file_list, 1)
        
        # Stats
        self.stats_label = QLabel("No files loaded")
        self.stats_label.setStyleSheet("color: #888; font-size: 10pt;")
        file_list_layout.addWidget(self.stats_label)
        
        splitter.addWidget(file_list_widget)
        
        # Right: Preview panel
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.addWidget(QLabel("File Preview:"))
        
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setFont(QFont("Courier New", 9))
        self.preview_text.setStyleSheet("""
            QTextEdit {
                background-color: #2b2b2b;
                color: #e0e0e0;
                border: 1px solid #555;
                padding: 8px;
            }
        """)
        preview_layout.addWidget(self.preview_text, 1)
        
        # Thumbnail plot preview
        self.thumbnail_figure = Figure(figsize=(4, 2.5), dpi=80)
        self.thumbnail_canvas = FigureCanvas(self.thumbnail_figure)
        self.thumbnail_canvas.setMinimumHeight(200)
        self.thumbnail_canvas.setMaximumHeight(200)
        self.thumbnail_canvas.setStyleSheet("border: 1px solid #555; background: #2b2b2b;")
        
        # Initialize with empty plot
        self.thumbnail_ax = self.thumbnail_figure.add_subplot(111)
        self.thumbnail_ax.set_facecolor('#2b2b2b')
        self.thumbnail_figure.patch.set_facecolor('#2b2b2b')
        self.thumbnail_ax.text(0.5, 0.5, 'Select a file to preview', 
                              ha='center', va='center', color='#888',
                              transform=self.thumbnail_ax.transAxes)
        self.thumbnail_ax.set_xticks([])
        self.thumbnail_ax.set_yticks([])
        for spine in self.thumbnail_ax.spines.values():
            spine.set_color('#555')
        self.thumbnail_figure.tight_layout()
        
        preview_layout.addWidget(self.thumbnail_canvas)
        
        splitter.addWidget(preview_widget)
        
        # Set initial splitter sizes (60/40 split)
        splitter.setSizes([600, 400])
        
        layout.addWidget(splitter, 1)
        
        # Bottom section: Selected files
        selected_group = QGroupBox("Selected Files for Plotting")
        selected_layout = QVBoxLayout()
        
        self.selected_list = QListWidget()
        self.selected_list.setMaximumHeight(120)
        selected_layout.addWidget(self.selected_list)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        clear_btn = QPushButton("Clear Selection")
        clear_btn.clicked.connect(self.clear_selection)
        button_layout.addWidget(clear_btn)
        
        button_layout.addStretch()
        
        # Append checkbox
        self.append_check = QCheckBox("Append to existing plot")
        self.append_check.setToolTip("Add datasets to current plot instead of replacing")
        button_layout.addWidget(self.append_check)
        
        self.plot_btn = QPushButton("📊 Plot Selected Files")
        self.plot_btn.setEnabled(False)
        self.plot_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 8px 16px;
                font-weight: bold;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #4a4a4a;
                color: #777;
            }
        """)
        self.plot_btn.clicked.connect(self.plot_selected)
        button_layout.addWidget(self.plot_btn)
        
        selected_layout.addLayout(button_layout)
        selected_group.setLayout(selected_layout)
        layout.addWidget(selected_group)
    
    def browse_folder(self):
        """Open folder browser dialog"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Folder with TSP Data Files",
            str(Path.home()),
            QFileDialog.Option.ShowDirsOnly
        )
        
        if folder:
            self.load_folder(Path(folder))
    
    def load_folder(self, folder_path: Path, force_reload: bool = False):
        """Load all TSP files from folder
        
        Args:
            folder_path: Path to folder containing TSP files
            force_reload: If True, reload even if folder is the same (for auto-refresh)
        """
        # Prevent loading same folder twice (unless force_reload)
        if not force_reload and self.current_folder == folder_path:
            return
            
        self.current_folder = folder_path
        self.folder_path_label.setText(str(folder_path))
        
        # Block signals to prevent recursion
        self.recent_folders_combo.blockSignals(True)
        
        # Add to recent folders
        settings = get_settings()
        settings.add_recent_folder(str(folder_path))
        self.load_recent_folders()
        
        # Unblock signals
        self.recent_folders_combo.blockSignals(False)
        
        # Find all .txt files
        txt_files = list(folder_path.glob("*.txt"))
        
        # Filter out log files
        txt_files = [f for f in txt_files if not f.name.startswith("tsp_test_log")]
        
        # Store file timestamps for change detection
        self.file_timestamps = {}
        for txt_file in txt_files:
            try:
                self.file_timestamps[txt_file] = txt_file.stat().st_mtime
            except (OSError, FileNotFoundError):
                pass
        
        # Parse files
        self.all_files = []
        for txt_file in txt_files:
            data = parse_tsp_file(txt_file)
            if data:
                self.all_files.append(data)
        
        # Update UI
        self.update_file_list()
        self.update_test_type_filter()
        self.update_stats()
        
        # Start auto-refresh if enabled
        if self.auto_refresh_enabled:
            self.refresh_timer.start(self.refresh_interval_ms)
    
    def update_file_list(self):
        """Update the file list widget"""
        self.file_list.clear()
        
        # Get current filter
        current_filter = self.test_type_filter.currentText()
        
        # Filter files
        filtered_files = []
        for data in self.all_files:
            # Apply filter
            if current_filter != "All Test Types" and data.test_name != current_filter:
                continue
            filtered_files.append(data)
        
        # Sort files using natural/numeric sorting
        filtered_files.sort(key=lambda data: natural_sort_key(data.filename))
        
        # Add items in sorted order
        for data in filtered_files:
            item = FileListItem(data)
            self.file_list.addItem(item)
    
    def update_test_type_filter(self):
        """Update test type filter dropdown"""
        # Get unique test types
        test_types = set(data.test_name for data in self.all_files)
        
        # Update combo box
        current_text = self.test_type_filter.currentText()
        self.test_type_filter.clear()
        self.test_type_filter.addItem("All Test Types")
        for test_type in sorted(test_types):
            self.test_type_filter.addItem(test_type)
        
        # Restore selection if possible
        index = self.test_type_filter.findText(current_text)
        if index >= 0:
            self.test_type_filter.setCurrentIndex(index)
    
    def update_stats(self):
        """Update statistics label"""
        total = len(self.all_files)
        visible = self.file_list.count()
        selected = len(self.selected_data)
        
        self.stats_label.setText(
            f"Total: {total} files | Showing: {visible} | Selected: {selected}"
        )
    
    def apply_filter(self):
        """Apply test type filter"""
        self.update_file_list()
        self.update_stats()
    
    def on_selection_changed(self):
        """Handle selection change in file list"""
        # Get selected items
        selected_items = self.file_list.selectedItems()
        self.selected_data = [item.tsp_data for item in selected_items if isinstance(item, FileListItem)]
        
        # Update selected list display
        self.selected_list.clear()
        for data in self.selected_data:
            display_text = f"{data.get_display_name()}"
            key_params = data.get_key_parameters()
            if key_params:
                display_text += f" - {key_params}"
            self.selected_list.addItem(display_text)
        
        # Enable/disable plot button
        self.plot_btn.setEnabled(len(self.selected_data) > 0)
        
        # Update stats
        self.update_stats()
    
    def on_current_item_changed(self, current, previous):
        """Handle current item change (for preview)"""
        if current and isinstance(current, FileListItem):
            self.show_preview(current.tsp_data)
    
    def show_preview(self, data: TSPData):
        """Show file preview"""
        preview_text = f"""
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
        <b>Timestamp:</b> {data.timestamp}<br>
        <b>Data Points:</b> {len(data.timestamps)}<br>
        <b>Duration:</b> {data.duration:.2f} s<br>
        <hr>
        <b>Test Parameters:</b><br>
        """
        for key, value in data.parameters.items():
            preview_text += f"&nbsp;&nbsp;<span style='color: #888'>{key}:</span> {value}<br>"
        
        if data.notes:
            preview_text += f"<hr><b>Notes:</b><br><span style='color: #d0d0d0'>{data.notes}</span>"
        
        self.preview_text.setHtml(preview_text)
        
        # Update thumbnail plot
        self.update_thumbnail_plot(data)
    
    def update_thumbnail_plot(self, data: TSPData):
        """Update thumbnail with mini-plot of data"""
        try:
            # Clear previous plot
            self.thumbnail_ax.clear()
            
            # Style
            self.thumbnail_ax.set_facecolor('#2b2b2b')
            self.thumbnail_figure.patch.set_facecolor('#2b2b2b')
            
            # Check if this is an IV sweep (should plot V vs I)
            if 'IV Sweep' in data.test_name or 'Hysteresis' in data.test_name:
                # Plot Voltage vs Current
                if hasattr(data, 'voltages') and hasattr(data, 'currents') and len(data.voltages) > 0:
                    # Downsample if too many points
                    max_points = 200
                    if len(data.voltages) > max_points:
                        step = len(data.voltages) // max_points
                        voltages = data.voltages[::step]
                        currents = data.currents[::step]
                    else:
                        voltages = data.voltages
                        currents = data.currents
                    
                    # Plot IV curve
                    self.thumbnail_ax.plot(voltages, currents,
                                          color='#2196F3', linewidth=1.5,
                                          marker='o', markersize=2, markevery=max(1, len(voltages)//20))
                    
                    # Labels
                    self.thumbnail_ax.set_xlabel('Voltage (V)', color='#b0b0b0', fontsize=8)
                    self.thumbnail_ax.set_ylabel('Current (A)', color='#b0b0b0', fontsize=8)
                    self.thumbnail_ax.tick_params(colors='#b0b0b0', labelsize=7)
                    
                    # Grid and zero lines
                    self.thumbnail_ax.grid(True, alpha=0.2, color='#555')
                    self.thumbnail_ax.axhline(y=0, color='#666', linestyle='--', linewidth=0.5, alpha=0.5)
                    self.thumbnail_ax.axvline(x=0, color='#666', linestyle='--', linewidth=0.5, alpha=0.5)
                    
                    # Spines
                    for spine in self.thumbnail_ax.spines.values():
                        spine.set_color('#555')
                    
                    # Title
                    title = f"{data.test_name} ({len(data.voltages)} pts)"
                    self.thumbnail_ax.set_title(title, color='#e0e0e0', fontsize=9, pad=5)
                else:
                    raise ValueError("No voltage/current data for IV sweep")
            
            # Standard plot: Time vs Resistance
            elif hasattr(data, 'resistances') and len(data.resistances) > 0:
                # Downsample if too many points (for speed)
                max_points = 200
                if len(data.resistances) > max_points:
                    step = len(data.resistances) // max_points
                    times = data.timestamps[::step]
                    resistances = data.resistances[::step]
                else:
                    times = data.timestamps
                    resistances = data.resistances
                
                # Plot
                self.thumbnail_ax.plot(times, resistances, 
                                      color='#2196F3', linewidth=1.5, 
                                      marker='o', markersize=2, markevery=max(1, len(times)//20))
                
                # Labels with dark theme colors
                self.thumbnail_ax.set_xlabel('Time (s)', color='#b0b0b0', fontsize=8)
                self.thumbnail_ax.set_ylabel('Resistance (Ω)', color='#b0b0b0', fontsize=8)
                self.thumbnail_ax.tick_params(colors='#b0b0b0', labelsize=7)
                
                # Grid
                self.thumbnail_ax.grid(True, alpha=0.2, color='#555')
                
                # Spines
                for spine in self.thumbnail_ax.spines.values():
                    spine.set_color('#555')
                
                # Title
                title = f"{data.test_name} ({len(data.resistances)} pts)"
                self.thumbnail_ax.set_title(title, color='#e0e0e0', fontsize=9, pad=5)
                
                # Auto log scale if wide range
                r_min, r_max = min(resistances), max(resistances)
                if r_max > 0 and r_min > 0 and r_max / r_min > 100:
                    self.thumbnail_ax.set_yscale('log')
                
            else:
                # No data to plot
                self.thumbnail_ax.text(0.5, 0.5, 'No data available', 
                                      ha='center', va='center', color='#888',
                                      transform=self.thumbnail_ax.transAxes, fontsize=10)
                self.thumbnail_ax.set_xticks([])
                self.thumbnail_ax.set_yticks([])
                for spine in self.thumbnail_ax.spines.values():
                    spine.set_color('#555')
            
            self.thumbnail_figure.tight_layout(pad=0.5)
            self.thumbnail_canvas.draw()
            
        except Exception as e:
            print(f"Error updating thumbnail: {e}")
            # Show error message
            self.thumbnail_ax.clear()
            self.thumbnail_ax.text(0.5, 0.5, f'Error: {str(e)[:30]}...', 
                                  ha='center', va='center', color='#ff5555',
                                  transform=self.thumbnail_ax.transAxes, fontsize=9)
            self.thumbnail_ax.set_xticks([])
            self.thumbnail_ax.set_yticks([])
            self.thumbnail_canvas.draw()
    
    def clear_selection(self):
        """Clear all selected files"""
        self.file_list.clearSelection()
    
    def plot_selected(self):
        """Emit signal to plot selected files"""
        if self.selected_data:
            self.files_selected.emit(self.selected_data)
            # TODO: Switch to plotting tab
    
    def toggle_auto_refresh(self, enabled: bool):
        """Enable/disable auto-refresh"""
        self.auto_refresh_enabled = enabled
        if enabled and self.current_folder:
            self.refresh_timer.start(self.refresh_interval_ms)
            self.refresh_status_label.setText("🔄 Auto-refresh active")
        else:
            self.refresh_timer.stop()
            self.refresh_status_label.setText("")
    
    def check_for_changes(self):
        """Periodically check if files have changed and update if needed"""
        if not self.current_folder or not self.auto_refresh_enabled:
            return
        
        try:
            # Find all .txt files
            txt_files = list(self.current_folder.glob("*.txt"))
            txt_files = [f for f in txt_files if not f.name.startswith("tsp_test_log")]
            
            # Check for new or modified files
            files_changed = False
            current_timestamps = {}
            
            for txt_file in txt_files:
                try:
                    mtime = txt_file.stat().st_mtime
                    current_timestamps[txt_file] = mtime
                    
                    # Check if file is new or modified
                    if txt_file not in self.file_timestamps or self.file_timestamps[txt_file] != mtime:
                        files_changed = True
                        break
                except (OSError, FileNotFoundError):
                    continue
            
            # Check for deleted files
            if not files_changed:
                for old_file in self.file_timestamps:
                    if old_file not in current_timestamps:
                        files_changed = True
                        break
            
            # If changes detected, reload folder
            if files_changed:
                # Reload folder (force reload even if same folder)
                folder = self.current_folder
                self.load_folder(folder, force_reload=True)
                self.refresh_status_label.setText("✓ Files updated")
                # Clear status after 1 second
                QTimer.singleShot(1000, lambda: self.refresh_status_label.setText("🔄 Auto-refresh active"))
                
        except Exception as e:
            # Silently handle errors (folder might have been deleted, etc.)
            pass
    
    def load_recent_folders(self):
        """Load recent folders into combo box"""
        settings = get_settings()
        recent = settings.get_recent_folders()
        
        self.recent_folders_combo.clear()
        if recent:
            self.recent_folders_combo.addItems(recent)
        else:
            self.recent_folders_combo.addItem("No recent folders")
    
    def load_recent_folder(self, folder_path: str):
        """Load a folder from recent list"""
        if folder_path and folder_path != "No recent folders" and folder_path != "":
            try:
                path = Path(folder_path)
                if path.exists() and path != self.current_folder:
                    self.load_folder(path)
            except Exception as e:
                print(f"Error loading recent folder: {e}")

