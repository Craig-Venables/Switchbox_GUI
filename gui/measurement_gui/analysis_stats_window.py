"""
Analysis Stats Window - Floating Stats Display
==============================================

Purpose:
--------
Creates a floating window that displays IV sweep analysis statistics as an overlay
on top of the measurement graphs. The window adapts its content based on the
selected analysis level (basic, classification, full, research).

Key Features:
-------------
- Floating Toplevel window that overlays on graphs
- Adapts content based on analysis level
- Auto-positioning relative to graph area
- Show/hide based on analysis_enabled checkbox
- Updates when new analysis data is available

Usage:
------
    from gui.measurement_gui.analysis_stats_window import AnalysisStatsWindow
    
    # Create window (initially hidden)
    stats_window = AnalysisStatsWindow(parent_window, graph_frame)
    
    # Show window when analysis is enabled
    stats_window.show()
    
    # Update with analysis data
    stats_window.update_stats(analysis_data, analysis_level='full')
    
    # Hide window
    stats_window.hide()
"""

from __future__ import annotations

# Standard library imports
from typing import Any, Dict, Optional

# Third-party imports
import tkinter as tk
from tkinter import ttk


class AnalysisStatsWindow:
    """
    Floating window that displays IV sweep analysis statistics.
    
    The window shows different levels of detail based on the analysis_level:
    - basic: Core metrics only (Ron, Roff, areas)
    - classification: Adds device classification
    - full: Adds conduction models and advanced metrics
    - research: Maximum detail with extra diagnostics
    """
    
    # Color scheme - orange theme matching overlay
    COLOR_BG = "#ffe0b2"  # Light orange background (same as overlay)
    COLOR_HEADER = "#e65100"  # Dark orange header
    COLOR_TEXT = "#e65100"  # Dark orange text
    COLOR_SUBTEXT = "#bf360c"  # Darker orange for subtext
    COLOR_BORDER = "#ff9800"  # Orange border
    
    # Fonts
    FONT_HEADER = ("Segoe UI", 9, "bold")
    FONT_SECTION = ("Segoe UI", 8, "bold")
    FONT_TEXT = ("Segoe UI", 8)
    FONT_VALUE = ("Segoe UI", 8)
    
    def __init__(self, parent: tk.Toplevel, graph_frame: tk.Frame):
        """
        Initialize the analysis stats window.
        
        Parameters:
        -----------
        parent : tk.Toplevel
            Parent window (the main measurement GUI window)
        graph_frame : tk.Frame
            Frame containing the graphs (used for positioning)
        """
        self.parent = parent
        self.graph_frame = graph_frame
        self.window: Optional[tk.Toplevel] = None
        self.content_frame: Optional[tk.Frame] = None
        self.current_data: Optional[Dict[str, Any]] = None
        self.current_level: str = "full"
        
        # Create window (initially hidden)
        self._create_window()
    
    def _create_window(self) -> None:
        """Create the floating stats window (initially hidden)"""
        # Create Toplevel window
        self.window = tk.Toplevel(self.parent)
        self.window.title("Analysis Statistics")
        self.window.configure(bg=self.COLOR_BG)
        
        # Make it floating and always on top
        self.window.attributes('-topmost', True)
        self.window.overrideredirect(True)  # Remove window decorations
        
        # Make it translucent (alpha transparency)
        try:
            self.window.attributes('-alpha', 0.92)  # Slightly translucent
        except:
            pass  # Some systems don't support alpha
        
        # Set smaller size for corner box
        self.window.geometry("280x400")
        
        # Create main content frame with scrollbar
        main_frame = tk.Frame(self.window, bg=self.COLOR_BG, relief='solid', borderwidth=1)
        main_frame.pack(fill='both', expand=True, padx=1, pady=1)
        
        # Canvas for scrolling
        canvas = tk.Canvas(main_frame, bg=self.COLOR_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        self.content_frame = tk.Frame(canvas, bg=self.COLOR_BG)
        
        # Configure scrolling
        self.content_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.content_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Add compact header with close button
        header_frame = tk.Frame(self.content_frame, bg=self.COLOR_HEADER, height=24)
        header_frame.pack(fill='x', padx=0, pady=0)
        header_frame.pack_propagate(False)
        
        title_label = tk.Label(
            header_frame,
            text="Analysis Stats",
            font=self.FONT_HEADER,
            bg=self.COLOR_HEADER,
            fg='white'
        )
        title_label.pack(side='left', padx=8, pady=2)
        
        close_btn = tk.Label(
            header_frame,
            text="×",
            font=("Segoe UI", 12, "bold"),
            bg=self.COLOR_HEADER,
            fg='white',
            cursor='hand2'
        )
        close_btn.pack(side='right', padx=5, pady=2)
        close_btn.bind("<Button-1>", lambda e: self.hide())
        
        # Initially hide the window
        self.window.withdraw()
    
    def _format_value(self, value: Any, unit: str = "", precision: int = 3) -> str:
        """
        Format a numeric value for display.
        
        Parameters:
        -----------
        value : Any
            Value to format
        unit : str
            Unit to append (e.g., "V", "Ω", "%")
        precision : int
            Number of decimal places
        """
        if value is None:
            return "N/A"
        
        try:
            if isinstance(value, (int, float)):
                if abs(value) >= 1e6:
                    return f"{value/1e6:.{precision}f} M{unit}"
                elif abs(value) >= 1e3:
                    return f"{value/1e3:.{precision}f} k{unit}"
                elif abs(value) < 1e-3 and abs(value) > 0:
                    return f"{value*1e6:.{precision}f} μ{unit}"
                elif abs(value) < 1e-6 and abs(value) > 0:
                    return f"{value*1e9:.{precision}f} n{unit}"
                else:
                    return f"{value:.{precision}f} {unit}".strip()
            else:
                return str(value)
        except (ValueError, TypeError):
            return str(value) if value is not None else "N/A"
    
    def _add_section(self, parent: tk.Frame, title: str) -> tk.Frame:
        """Add a section header and return a frame for content"""
        section_frame = tk.Frame(parent, bg=self.COLOR_BG)
        section_frame.pack(fill='x', padx=6, pady=(6, 3))
        
        # Section title
        title_label = tk.Label(
            section_frame,
            text=title,
            font=self.FONT_SECTION,
            bg=self.COLOR_BG,
            fg=self.COLOR_HEADER,
            anchor='w'
        )
        title_label.pack(fill='x', pady=(0, 2))
        
        # Separator line
        separator = tk.Frame(section_frame, height=1, bg=self.COLOR_BORDER)
        separator.pack(fill='x')
        
        # Content frame
        content_frame = tk.Frame(section_frame, bg=self.COLOR_BG)
        content_frame.pack(fill='x', padx=(6, 0), pady=3)
        
        return content_frame
    
    def _add_stat_row(self, parent: tk.Frame, label: str, value: str) -> None:
        """Add a stat row (label: value)"""
        row = tk.Frame(parent, bg=self.COLOR_BG)
        row.pack(fill='x', pady=1)
        
        label_widget = tk.Label(
            row,
            text=f"{label}:",
            font=self.FONT_TEXT,
            bg=self.COLOR_BG,
            fg=self.COLOR_SUBTEXT,
            anchor='w',
            width=14
        )
        label_widget.pack(side='left')
        
        value_widget = tk.Label(
            row,
            text=value,
            font=self.FONT_VALUE,
            bg=self.COLOR_BG,
            fg=self.COLOR_TEXT,
            anchor='w'
        )
        value_widget.pack(side='left', fill='x', expand=True)
    
    def _update_content(self, data: Dict[str, Any], level: str) -> None:
        """
        Update the window content based on analysis data and level.
        
        Parameters:
        -----------
        data : dict
            Analysis data from IVSweepAnalyzer
        level : str
            Analysis level: 'basic', 'classification', 'full', or 'research'
        """
        if not self.content_frame:
            return
        
        # Clear existing content (except header)
        for widget in self.content_frame.winfo_children():
            if isinstance(widget, tk.Frame) and widget.winfo_children():
                # Check if it's the header frame (has close button)
                if any(isinstance(child, tk.Button) for child in widget.winfo_children()):
                    continue
                widget.destroy()
        
        # Device Info Section (always shown)
        device_info = data.get('device_info', {})
        info_section = self._add_section(self.content_frame, "Device Information")
        self._add_stat_row(info_section, "Device", device_info.get('name', 'N/A'))
        self._add_stat_row(info_section, "Type", device_info.get('measurement_type', 'N/A'))
        self._add_stat_row(info_section, "Loops", str(device_info.get('num_loops', 0)))
        self._add_stat_row(info_section, "Analysis Level", level.upper())
        
        # Basic Metrics (always shown)
        res_metrics = data.get('resistance_metrics', {})
        basic_section = self._add_section(self.content_frame, "Resistance Metrics")
        self._add_stat_row(basic_section, "Ron (mean)", self._format_value(res_metrics.get('ron_mean', 0), "Ω"))
        self._add_stat_row(basic_section, "Ron (std)", self._format_value(res_metrics.get('ron_std', 0), "Ω"))
        self._add_stat_row(basic_section, "Roff (mean)", self._format_value(res_metrics.get('roff_mean', 0), "Ω"))
        self._add_stat_row(basic_section, "Roff (std)", self._format_value(res_metrics.get('roff_std', 0), "Ω"))
        self._add_stat_row(basic_section, "Switching Ratio", self._format_value(res_metrics.get('switching_ratio_mean', 0), ""))
        self._add_stat_row(basic_section, "ON/OFF Ratio", self._format_value(res_metrics.get('on_off_ratio_mean', 0), ""))
        
        # Voltage Metrics (always shown)
        volt_metrics = data.get('voltage_metrics', {})
        volt_section = self._add_section(self.content_frame, "Voltage Metrics")
        self._add_stat_row(volt_section, "Von (mean)", self._format_value(volt_metrics.get('von_mean', 0), "V"))
        self._add_stat_row(volt_section, "Voff (mean)", self._format_value(volt_metrics.get('voff_mean', 0), "V"))
        self._add_stat_row(volt_section, "Max Voltage", self._format_value(volt_metrics.get('max_voltage', 0), "V"))
        
        # Hysteresis Metrics (always shown)
        hyst_metrics = data.get('hysteresis_metrics', {})
        hyst_section = self._add_section(self.content_frame, "Hysteresis")
        self._add_stat_row(hyst_section, "Normalized Area", self._format_value(hyst_metrics.get('normalized_area_mean', 0), ""))
        self._add_stat_row(hyst_section, "Has Hysteresis", "Yes" if hyst_metrics.get('has_hysteresis', False) else "No")
        self._add_stat_row(hyst_section, "Pinched", "Yes" if hyst_metrics.get('pinched_hysteresis', False) else "No")
        
        # Classification (shown for classification, full, research)
        if level in ['classification', 'full', 'research']:
            class_data = data.get('classification', {})
            class_section = self._add_section(self.content_frame, "Classification")
            self._add_stat_row(class_section, "Device Type", class_data.get('device_type', 'N/A'))
            self._add_stat_row(class_section, "Confidence", self._format_value(class_data.get('confidence', 0) * 100, "%", 1))
            self._add_stat_row(class_section, "Conduction", class_data.get('conduction_mechanism', 'N/A'))
            if class_data.get('model_r2', 0) > 0:
                self._add_stat_row(class_section, "Model R²", self._format_value(class_data.get('model_r2', 0), "", 3))
        
        # Performance Metrics (shown for full, research)
        if level in ['full', 'research']:
            perf_metrics = data.get('performance_metrics', {})
            perf_section = self._add_section(self.content_frame, "Performance")
            self._add_stat_row(perf_section, "Retention Score", self._format_value(perf_metrics.get('retention_score', 0), "", 3))
            self._add_stat_row(perf_section, "Endurance Score", self._format_value(perf_metrics.get('endurance_score', 0), "", 3))
            self._add_stat_row(perf_section, "Rectification", self._format_value(perf_metrics.get('rectification_ratio_mean', 1), ""))
            self._add_stat_row(perf_section, "Non-linearity", self._format_value(perf_metrics.get('nonlinearity_mean', 0), ""))
            if perf_metrics.get('power_consumption_mean', 0) > 0:
                self._add_stat_row(perf_section, "Power", self._format_value(perf_metrics.get('power_consumption_mean', 0), "W"))
            if perf_metrics.get('compliance_current') is not None:
                self._add_stat_row(perf_section, "Compliance", self._format_value(perf_metrics.get('compliance_current', 0), "μA"))
        
        # Research Diagnostics (shown only for research)
        if level == 'research':
            research_data = data.get('research_diagnostics', {})
            if research_data:
                research_section = self._add_section(self.content_frame, "Research Diagnostics")
                if research_data.get('switching_polarity'):
                    self._add_stat_row(research_section, "Polarity", research_data.get('switching_polarity', 'N/A'))
                if research_data.get('ndr_index') is not None:
                    self._add_stat_row(research_section, "NDR Index", self._format_value(research_data.get('ndr_index', 0), ""))
                if research_data.get('hysteresis_direction'):
                    self._add_stat_row(research_section, "Hyst. Direction", research_data.get('hysteresis_direction', 'N/A'))
                if research_data.get('loop_similarity_score') is not None:
                    self._add_stat_row(research_section, "Loop Similarity", self._format_value(research_data.get('loop_similarity_score', 0), "", 3))
                if research_data.get('noise_floor') is not None:
                    self._add_stat_row(research_section, "Noise Floor", self._format_value(research_data.get('noise_floor', 0), "A"))
        
        # Metadata (if available)
        metadata = device_info.get('metadata', {})
        if metadata:
            meta_section = self._add_section(self.content_frame, "Metadata")
            if metadata.get('led_on') is not None:
                self._add_stat_row(meta_section, "LED", "ON" if metadata.get('led_on') else "OFF")
            if metadata.get('led_type'):
                self._add_stat_row(meta_section, "LED Type", metadata.get('led_type', 'N/A'))
            if metadata.get('temperature') is not None:
                self._add_stat_row(meta_section, "Temperature", self._format_value(metadata.get('temperature', 0), "°C", 1))
            if metadata.get('humidity') is not None:
                self._add_stat_row(meta_section, "Humidity", self._format_value(metadata.get('humidity', 0), "%", 1))
    
    def update_stats(self, data: Dict[str, Any], analysis_level: str = "full") -> None:
        """
        Update the stats window with new analysis data.
        
        Parameters:
        -----------
        data : dict
            Analysis data from IVSweepAnalyzer.analyze_sweep()
        analysis_level : str
            Analysis level: 'basic', 'classification', 'full', or 'research'
        """
        self.current_data = data
        self.current_level = analysis_level
        
        if self.window and self.window.winfo_viewable():
            self._update_content(data, analysis_level)
    
    def show(self) -> None:
        """Show the stats window and position it over the graphs"""
        if not self.window:
            return
        
        # Update content if we have data
        if self.current_data:
            self._update_content(self.current_data, self.current_level)
        
        # Position window relative to graph frame
        try:
            # Wait for geometry to be calculated if needed
            self.parent.update_idletasks()
            self.graph_frame.update_idletasks()
            
            # Get graph frame position relative to parent
            graph_x = self.graph_frame.winfo_x()
            graph_y = self.graph_frame.winfo_y()
            graph_width = self.graph_frame.winfo_width()
            graph_height = self.graph_frame.winfo_height()
            
            # Only position if we have valid geometry
            if graph_width > 0 and graph_height > 0:
                # Position in top-right corner of graph area
                # Offset from edges
                offset_x = 20
                offset_y = 60  # Below the control bar
                
                # Calculate position
                parent_x = self.parent.winfo_x()
                parent_y = self.parent.winfo_y()
                
                window_x = parent_x + graph_x + graph_width - 290 - offset_x  # 290 = window width + padding
                window_y = parent_y + graph_y + offset_y
                
                # Ensure window stays within parent bounds
                if window_x < parent_x:
                    window_x = parent_x + 10
                if window_y < parent_y:
                    window_y = parent_y + 10
                
                self.window.geometry(f"280x400+{int(window_x)}+{int(window_y)}")
            else:
                # Fallback: position relative to parent center-right
                parent_x = self.parent.winfo_x()
                parent_y = self.parent.winfo_y()
                parent_width = self.parent.winfo_width()
                window_x = parent_x + parent_width - 290 - 20
                window_y = parent_y + 100
                self.window.geometry(f"280x400+{int(window_x)}+{int(window_y)}")
        except Exception:
            # Fallback: position at default location
            self.window.geometry("280x400+100+100")
        
        # Show window
        self.window.deiconify()
        self.window.lift()
        self.window.attributes('-topmost', True)
    
    def hide(self) -> None:
        """Hide the stats window"""
        if self.window:
            self.window.withdraw()
    
    def is_visible(self) -> bool:
        """Check if the window is currently visible"""
        if not self.window:
            return False
        try:
            return self.window.winfo_viewable()
        except:
            return False
    
    def destroy(self) -> None:
        """Destroy the stats window"""
        if self.window:
            self.window.destroy()
            self.window = None

