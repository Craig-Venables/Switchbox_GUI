"""
Batch Processing Dialog

Dialog for processing multiple TSP files at once, generating plots and statistics.
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                              QLabel, QGroupBox, QCheckBox, QComboBox, QLineEdit,
                              QFileDialog, QProgressBar, QTextEdit, QMessageBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from pathlib import Path
from typing import List, Optional, Dict
import sys
import csv
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.data_parser import parse_tsp_file, TSPData
from core.plot_generator import PlotGenerator
from core.statistics import DataStatistics, format_stat_value
from core.test_type_registry import get_registry


class BatchProcessorThread(QThread):
    """Thread for batch processing to avoid blocking UI"""
    
    progress = pyqtSignal(int, int)  # current, total
    file_processed = pyqtSignal(str, bool, str)  # filename, success, message
    finished = pyqtSignal(bool, str)  # success, summary message
    
    def __init__(self, input_folder: Path, output_folder: Path, 
                 options: Dict, parent=None):
        super().__init__(parent)
        self.input_folder = input_folder
        self.output_folder = output_folder
        self.options = options
        self.cancel_requested = False
    
    def cancel(self):
        """Request cancellation"""
        self.cancel_requested = True
    
    def run(self):
        """Run batch processing"""
        try:
            # Find all .txt files (recursively or not)
            if self.options.get('recursive', True):
                txt_files = list(self.input_folder.rglob("*.txt"))
            else:
                txt_files = list(self.input_folder.glob("*.txt"))
            txt_files = [f for f in txt_files if not f.name.startswith("tsp_test_log")]
            
            if not txt_files:
                self.finished.emit(False, "No .txt files found in selected folder")
                return
            
            # Filter by test type if specified
            if self.options.get('filter_test_type') and self.options['filter_test_type'] != "All Test Types":
                filtered_files = []
                for filepath in txt_files:
                    data = parse_tsp_file(filepath)
                    if data and data.test_name == self.options['filter_test_type']:
                        filtered_files.append(filepath)
                txt_files = filtered_files
            
            total_files = len(txt_files)
            successful = 0
            failed = 0
            all_stats = []
            
            # Create output folders
            plots_folder = self.output_folder / "plots" if self.options.get('export_plots') else None
            stats_folder = self.output_folder / "statistics" if self.options.get('export_stats') else None
            
            if plots_folder:
                plots_folder.mkdir(parents=True, exist_ok=True)
            if stats_folder:
                stats_folder.mkdir(parents=True, exist_ok=True)
            
            plot_generator = PlotGenerator()
            
            # Process each file
            for i, filepath in enumerate(txt_files):
                if self.cancel_requested:
                    self.finished.emit(False, "Batch processing cancelled by user")
                    return
                
                self.progress.emit(i + 1, total_files)
                
                try:
                    # Parse file
                    data = parse_tsp_file(filepath)
                    if data is None:
                        self.file_processed.emit(filepath.name, False, "Failed to parse file")
                        failed += 1
                        continue
                    
                    # Generate plot if requested
                    if self.options.get('export_plots') and plots_folder:
                        try:
                            fig, ax = plot_generator.plot_single(data)
                            
                            # Save plot
                            plot_filename = filepath.stem + ".png"
                            if self.options.get('format') == 'pdf':
                                plot_filename = filepath.stem + ".pdf"
                            
                            plot_path = plots_folder / plot_filename
                            dpi = 300 if self.options.get('format') == 'png' else 150
                            fig.savefig(plot_path, dpi=dpi, 
                                      bbox_inches='tight', 
                                      facecolor=fig.get_facecolor(),
                                      edgecolor='none')
                            
                            import matplotlib.pyplot as plt
                            plt.close(fig)
                            self.file_processed.emit(filepath.name, True, f"Plot saved: {plot_filename}")
                        except Exception as e:
                            self.file_processed.emit(filepath.name, False, f"Plot error: {str(e)}")
                    
                    # Calculate statistics if requested
                    if self.options.get('export_stats') and stats_folder:
                        try:
                            # Get appropriate data based on test type
                            if 'relaxation' in data.test_name.lower():
                                include_relaxation = True
                                include_hrs_lrs = False
                            elif 'endurance' in data.test_name.lower() or 'switching' in data.test_name.lower():
                                include_relaxation = False
                                include_hrs_lrs = True
                            else:
                                include_relaxation = False
                                include_hrs_lrs = False
                            
                            # Calculate stats
                            stats_calc = DataStatistics(
                                data.timestamps,
                                data.resistances,
                                data.get_display_name(),
                                data.test_name
                            )
                            
                            stats = stats_calc.all_stats(
                                include_relaxation=include_relaxation,
                                include_hrs_lrs=include_hrs_lrs
                            )
                            
                            # Add file metadata to stats
                            stats['Filename'] = filepath.name
                            stats['Test Type'] = data.test_name
                            stats['Sample'] = data.sample or "Unknown"
                            stats['Device'] = data.device or "Unknown"
                            
                            all_stats.append(stats)
                            
                        except Exception as e:
                            self.file_processed.emit(filepath.name, False, f"Stats error: {str(e)}")
                    
                    successful += 1
                    
                except Exception as e:
                    self.file_processed.emit(filepath.name, False, f"Error: {str(e)}")
                    failed += 1
            
            # Save summary CSV if statistics were calculated
            if all_stats and stats_folder:
                csv_path = stats_folder / f"batch_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                
                if all_stats:
                    fieldnames = list(all_stats[0].keys())
                    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        for stats_row in all_stats:
                            writer.writerow(stats_row)
            
            # Final summary
            summary = f"Processing complete!\n\nSuccessful: {successful}\nFailed: {failed}\nTotal: {total_files}"
            if all_stats:
                summary += f"\n\nStatistics saved: {csv_path.name}"
            
            self.finished.emit(True, summary)
            
        except Exception as e:
            self.finished.emit(False, f"Batch processing error: {str(e)}")


class BatchProcessingDialog(QDialog):
    """Dialog for batch processing multiple files"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Batch Processing")
        self.setMinimumSize(600, 600)
        
        self.processor_thread = None
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Instructions section at top
        instructions_group = QGroupBox("📖 Instructions")
        instructions_layout = QVBoxLayout()
        
        instructions_text = QLabel(
            "<b>How to use Batch Processing:</b><br><br>"
            "1. <b>Select Input Folder:</b> Choose the folder containing your .txt data files<br>"
            "2. <b>Select Output Folder:</b> Choose where to save plots and statistics<br>"
            "3. <b>Configure Options:</b><br>"
            "   • Enable 'Process subfolders recursively' to scan nested folders<br>"
            "   • Filter by test type (optional) to process only specific tests<br>"
            "   • Choose export formats (PNG/PDF for plots, CSV for statistics)<br>"
            "4. <b>Start Processing:</b> Click '▶ Start Processing' to begin<br>"
            "5. <b>Monitor Progress:</b> Watch the progress bar and log for results<br><br>"
            "<b>Output Structure:</b><br>"
            "• Plots saved to: <i>output_folder/plots/</i><br>"
            "• Statistics saved to: <i>output_folder/statistics/batch_summary_*.csv</i>"
        )
        instructions_text.setWordWrap(True)
        instructions_text.setStyleSheet("""
            QLabel {
                color: #e0e0e0;
                padding: 10px;
                background-color: #2b2b2b;
                border: 1px solid #555;
                border-radius: 5px;
            }
        """)
        instructions_layout.addWidget(instructions_text)
        
        instructions_group.setLayout(instructions_layout)
        layout.addWidget(instructions_group)
        
        # Input folder selection
        input_group = QGroupBox("Input Folder")
        input_layout = QVBoxLayout()
        
        input_folder_layout = QHBoxLayout()
        input_folder_layout.addWidget(QLabel("Folder:"))
        self.input_folder_edit = QLineEdit()
        self.input_folder_edit.setReadOnly(True)
        self.input_folder_edit.setPlaceholderText("Select folder containing .txt files...")
        input_folder_layout.addWidget(self.input_folder_edit, 1)
        
        browse_input_btn = QPushButton("📁 Browse...")
        browse_input_btn.clicked.connect(self.browse_input_folder)
        input_folder_layout.addWidget(browse_input_btn)
        input_layout.addLayout(input_folder_layout)
        
        self.recursive_check = QCheckBox("Process subfolders recursively")
        self.recursive_check.setChecked(True)
        input_layout.addWidget(self.recursive_check)
        
        # Filter by test type
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter by test type:"))
        self.test_type_combo = QComboBox()
        self.test_type_combo.addItem("All Test Types")
        # Populate from registry
        registry = get_registry()
        for test_type in registry.get_all_test_types():
            self.test_type_combo.addItem(test_type)
        filter_layout.addWidget(self.test_type_combo, 1)
        input_layout.addLayout(filter_layout)
        
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)
        
        # Output folder selection
        output_group = QGroupBox("Output Folder")
        output_layout = QVBoxLayout()
        
        output_folder_layout = QHBoxLayout()
        output_folder_layout.addWidget(QLabel("Folder:"))
        self.output_folder_edit = QLineEdit()
        self.output_folder_edit.setReadOnly(True)
        self.output_folder_edit.setPlaceholderText("Select output folder...")
        output_folder_layout.addWidget(self.output_folder_edit, 1)
        
        browse_output_btn = QPushButton("📁 Browse...")
        browse_output_btn.clicked.connect(self.browse_output_folder)
        output_folder_layout.addWidget(browse_output_btn)
        output_layout.addLayout(output_folder_layout)
        
        output_group.setLayout(output_layout)
        layout.addWidget(output_group)
        
        # Options
        options_group = QGroupBox("Export Options")
        options_layout = QVBoxLayout()
        
        self.export_plots_check = QCheckBox("Export plots")
        self.export_plots_check.setChecked(True)
        options_layout.addWidget(self.export_plots_check)
        
        plot_format_layout = QHBoxLayout()
        plot_format_layout.addWidget(QLabel("Plot format:"))
        self.plot_format_combo = QComboBox()
        self.plot_format_combo.addItems(["PNG", "PDF"])
        plot_format_layout.addWidget(self.plot_format_combo)
        plot_format_layout.addStretch()
        options_layout.addLayout(plot_format_layout)
        
        self.export_stats_check = QCheckBox("Export statistics (CSV)")
        self.export_stats_check.setChecked(True)
        options_layout.addWidget(self.export_stats_check)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # Progress
        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        progress_layout.addWidget(self.progress_bar)
        
        self.progress_label = QLabel("Ready to start")
        self.progress_label.setStyleSheet("color: #888;")
        progress_layout.addWidget(self.progress_label)
        
        # Log output
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #2b2b2b;
                color: #e0e0e0;
                border: 1px solid #555;
                font-family: 'Courier New';
                font-size: 9pt;
            }
        """)
        progress_layout.addWidget(self.log_text)
        
        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.start_btn = QPushButton("▶ Start Processing")
        self.start_btn.clicked.connect(self.start_processing)
        button_layout.addWidget(self.start_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.cancel_btn.setEnabled(False)
        button_layout.addWidget(self.cancel_btn)
        
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
    
    def browse_input_folder(self):
        """Browse for input folder"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Input Folder",
            str(Path.home())
        )
        if folder:
            self.input_folder_edit.setText(folder)
    
    def browse_output_folder(self):
        """Browse for output folder"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Output Folder",
            str(Path.home())
        )
        if folder:
            self.output_folder_edit.setText(folder)
    
    def start_processing(self):
        """Start batch processing"""
        # Validate inputs
        input_folder = Path(self.input_folder_edit.text())
        output_folder = Path(self.output_folder_edit.text())
        
        if not input_folder.exists():
            QMessageBox.warning(self, "Invalid Input", "Please select a valid input folder")
            return
        
        if not output_folder.exists():
            try:
                output_folder.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                QMessageBox.warning(self, "Invalid Output", f"Cannot create output folder: {e}")
                return
        
        if not self.export_plots_check.isChecked() and not self.export_stats_check.isChecked():
            QMessageBox.warning(self, "No Options", "Please select at least one export option")
            return
        
        # Prepare options
        options = {
            'filter_test_type': self.test_type_combo.currentText(),
            'export_plots': self.export_plots_check.isChecked(),
            'export_stats': self.export_stats_check.isChecked(),
            'format': self.plot_format_combo.currentText().lower(),
            'recursive': self.recursive_check.isChecked()
        }
        
        # Clear log
        self.log_text.clear()
        self.log_text.append(f"Starting batch processing...")
        self.log_text.append(f"Input: {input_folder}")
        self.log_text.append(f"Output: {output_folder}")
        self.log_text.append("")
        
        # Create and start thread
        self.processor_thread = BatchProcessorThread(input_folder, output_folder, options, self)
        self.processor_thread.progress.connect(self.on_progress)
        self.processor_thread.file_processed.connect(self.on_file_processed)
        self.processor_thread.finished.connect(self.on_finished)
        
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.cancel_btn.setText("Cancel Processing")
        
        self.processor_thread.start()
    
    def on_progress(self, current: int, total: int):
        """Update progress bar"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.progress_label.setText(f"Processing: {current} / {total}")
    
    def on_file_processed(self, filename: str, success: bool, message: str):
        """Log file processing result"""
        status = "✓" if success else "✗"
        self.log_text.append(f"{status} {filename}: {message}")
        # Auto-scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def on_finished(self, success: bool, summary: str):
        """Handle processing completion"""
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setText("Cancel")
        
        if success:
            self.progress_label.setText("Processing complete!")
            self.log_text.append("")
            self.log_text.append("=" * 60)
            self.log_text.append(summary)
        else:
            self.progress_label.setText("Processing failed")
            self.log_text.append("")
            self.log_text.append("ERROR: " + summary)
        
        if success:
            QMessageBox.information(self, "Batch Processing Complete", summary)
    
    def reject(self):
        """Cancel processing if in progress"""
        if self.processor_thread and self.processor_thread.isRunning():
            reply = QMessageBox.question(
                self,
                "Cancel Processing",
                "Stop batch processing?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.processor_thread.cancel()
                self.processor_thread.wait()
        super().reject()

