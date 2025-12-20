"""
File Browser Panel - Select directory and process IV files.
"""

import tkinter as tk
from tkinter import ttk, filedialog
from pathlib import Path
import threading


class FileBrowserPanel:
    """Panel for selecting and processing IV files."""
    
    def __init__(self, parent, validator, on_loaded_callback=None):
        """
        Initialize file browser panel.
        
        Args:
            parent: Parent widget (notebook)
            validator: ClassificationValidator instance
            on_loaded_callback: Callback when data is loaded
        """
        self.validator = validator
        self.on_loaded_callback = on_loaded_callback
        
        self.frame = ttk.Frame(parent)
        self._build_ui()
    
    def _build_ui(self):
        """Build the UI."""
        # Title
        title = tk.Label(
            self.frame,
            text="Load IV Data Files",
            font=('Arial', 14, 'bold')
        )
        title.pack(pady=10)
        
        # Directory selection
        dir_frame = ttk.Frame(self.frame)
        dir_frame.pack(pady=10, padx=20, fill=tk.X)
        
        tk.Label(dir_frame, text="Directory:").pack(side=tk.LEFT, padx=5)
        
        self.dir_var = tk.StringVar()
        dir_entry = ttk.Entry(dir_frame, textvariable=self.dir_var, width=50)
        dir_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        browse_btn = ttk.Button(
            dir_frame,
            text="Browse...",
            command=self._browse_directory
        )
        browse_btn.pack(side=tk.LEFT, padx=5)
        
        # Options
        options_frame = ttk.LabelFrame(self.frame, text="Options")
        options_frame.pack(pady=10, padx=20, fill=tk.X)
        
        self.recursive_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options_frame,
            text="Scan subdirectories",
            variable=self.recursive_var
        ).pack(anchor=tk.W, padx=10, pady=5)
        
        pattern_frame = ttk.Frame(options_frame)
        pattern_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(pattern_frame, text="File pattern:").pack(side=tk.LEFT)
        self.pattern_var = tk.StringVar(value="*.txt")
        ttk.Entry(pattern_frame, textvariable=self.pattern_var, width=15).pack(side=tk.LEFT, padx=5)
        
        # Process button
        self.process_btn = ttk.Button(
            self.frame,
            text="Process Files",
            command=self._process_files,
            state=tk.DISABLED
        )
        self.process_btn.pack(pady=20)
        
        # Progress
        self.progress_var = tk.StringVar(value="")
        progress_label = tk.Label(
            self.frame,
            textvariable=self.progress_var,
            font=('Arial', 9),
            fg='#666666'
        )
        progress_label.pack(pady=5)
        
        self.progress_bar = ttk.Progressbar(
            self.frame,
            mode='determinate'
        )
        self.progress_bar.pack(pady=5, padx=20, fill=tk.X)
        
        # Results
        results_frame = ttk.LabelFrame(self.frame, text="Results")
        results_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        
        self.results_text = tk.Text(results_frame, height=10, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.results_text.yview)
        self.results_text.configure(yscrollcommand=scrollbar.set)
        
        self.results_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Update process button state based on directory
        self.dir_var.trace('w', lambda *args: self._update_process_button())
    
    def _browse_directory(self):
        """Browse for directory."""
        directory = filedialog.askdirectory(title="Select directory with IV files")
        if directory:
            self.dir_var.set(directory)
    
    def _update_process_button(self):
        """Update process button state."""
        if self.dir_var.get() and Path(self.dir_var.get()).exists():
            self.process_btn.config(state=tk.NORMAL)
        else:
            self.process_btn.config(state=tk.DISABLED)
    
    def _process_files(self):
        """Process files in selected directory."""
        directory = self.dir_var.get()
        if not directory or not Path(directory).exists():
            messagebox.showerror("Error", "Please select a valid directory")
            return
        
        # Disable button during processing
        self.process_btn.config(state=tk.DISABLED)
        self.progress_var.set("Processing files...")
        self.progress_bar['maximum'] = 100
        self.progress_bar['value'] = 0
        self.results_text.delete('1.0', tk.END)
        
        # Process in background thread
        def process_thread():
            try:
                def progress_callback(processed, total, current_file):
                    percent = (processed / total) * 100 if total > 0 else 0
                    self.progress_bar['value'] = percent
                    self.progress_var.set(f"Processing {processed}/{total}: {Path(current_file).name}")
                    self.frame.update_idletasks()
                
                results = self.validator.load_data(
                    directory=directory,
                    recursive=self.recursive_var.get(),
                    pattern=self.pattern_var.get(),
                    progress_callback=progress_callback
                )
                
                # Update UI in main thread
                self.frame.after(0, lambda: self._on_processing_complete(results))
                
            except Exception as e:
                self.frame.after(0, lambda: self._on_processing_error(str(e)))
        
        thread = threading.Thread(target=process_thread, daemon=True)
        thread.start()
    
    def _on_processing_complete(self, results):
        """Handle processing completion."""
        self.progress_bar['value'] = 100
        self.progress_var.set(f"Complete! Processed {len(results)} files")
        self.process_btn.config(state=tk.NORMAL)
        
        # Show results
        successful = [r for r in results if r.get('analysis')]
        errors = [r for r in results if r.get('error')]
        
        self.results_text.insert('1.0', f"Processing Complete\n")
        self.results_text.insert(tk.END, f"Total files: {len(results)}\n")
        self.results_text.insert(tk.END, f"Successful: {len(successful)}\n")
        self.results_text.insert(tk.END, f"Errors: {len(errors)}\n\n")
        
        if errors:
            self.results_text.insert(tk.END, "Errors:\n")
            for err in errors[:10]:  # Show first 10 errors
                self.results_text.insert(tk.END, f"  {Path(err['file_path']).name}: {err['error']}\n")
            if len(errors) > 10:
                self.results_text.insert(tk.END, f"  ... and {len(errors) - 10} more errors\n")
        
        # Callback
        if self.on_loaded_callback:
            self.on_loaded_callback()
