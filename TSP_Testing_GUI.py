"""
TSP Testing GUI - Multi-System Pulse Testing Interface
========================================================

Purpose:
--------
Fast, buffer-based pulse testing GUI with real-time visualization for Keithley
instruments. Supports both Keithley 2450 (TSP-based) and Keithley 4200A-SCS
(KXCI-based) systems. Automatically routes tests to the appropriate measurement
system based on device address.

Key Features:
-------------
- Pulse-read-repeat tests
- Width sweeps (pulse width characterization)
- Potentiation/depression cycles
- Endurance testing
- Real-time plotting and visualization
- Automatic system detection (2450 vs 4200A)
- Test parameter configuration
- Data saving with customizable locations

Entry Points:
-------------
1. Standalone mode:
   ```python
   root = tk.Tk()
   gui = TSPTestingGUI(root, device_address="USB0::0x05E6::0x2450::04496615::INSTR")
   root.mainloop()
   ```

2. Launched from MeasurementGUI:
   - User clicks "Pulse Testing" button in MeasurementGUI
   - Passes device address and context (sample name, device label)

Dependencies:
-------------
- Pulse_Testing.system_wrapper: System detection and routing
- Pulse_Testing.test_capabilities: Test availability checking
- Equipment.SMU_AND_PMU.Keithley2450_TSP: 2450 TSP interface
- Equipment.SMU_AND_PMU.keithley2450_tsp_scripts: 2450 test scripts
- Equipment.SMU_AND_PMU.keithley4200_kxci_scripts: 4200A KXCI scripts
- Measurments.data_formats: Data formatting and saving

Relationships:
-------------
TSP_Testing_GUI (this file)
    ├─> Can be launched from MeasurementGUI
    ├─> Can be standalone
    └─> Uses SystemWrapper to route to:
            ├─> Keithley 2450 system
            └─> Keithley 4200A system

Test Functions:
---------------
Defined in TEST_FUNCTIONS dictionary:
- Pulse-Read-Repeat
- Multi-Pulse-Then-Read
- Width Sweep
- Potentiation/Depression Cycle
- Endurance Test
- And more...

File Structure:
---------------
- ~3289 lines
- Main class: TSPTestingGUI
- Key components: Test definitions, test runner, plot manager, connection handler
- TODO: Consider breaking into smaller modules (see GUI_REFACTORING_PLAN.md)
"""

import threading
import time
import os
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional, List, Union
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import numpy as np

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

# Legacy imports kept for compatibility
from Equipment.SMU_AND_PMU.Keithley2450_TSP import Keithley2450_TSP
from Equipment.SMU_AND_PMU.keithley2450_tsp_scripts import Keithley2450_TSP_Scripts

# New modular pulse testing system
from Pulse_Testing.system_wrapper import SystemWrapper, detect_system_from_address, get_default_address_for_system
from Pulse_Testing.test_capabilities import is_test_supported, get_test_explanation

from Measurments.data_formats import TSPDataFormatter, FileNamer, save_tsp_measurement


# Standalone utility function for independent operation
def find_largest_number_in_folder(folder: Union[str, Path]) -> Optional[int]:
    """
    Return the largest numeric prefix found in folder filenames.
    
    Scans existing files in the folder to find the largest numeric prefix
    (e.g., "5-test.txt" -> 5). Used for sequential file numbering.
    
    Args:
        folder: Path to folder to scan
        
    Returns:
        Largest number found, or None if no numeric prefixes found
    """
    try:
        entries = os.listdir(folder)
    except (FileNotFoundError, OSError):
        return None
    
    max_idx: Optional[int] = None
    for name in entries:
        try:
            # Extract prefix before first hyphen
            prefix = name.split("-", 1)[0]
            value = int(prefix)
            if max_idx is None or value > max_idx:
                max_idx = value
        except (ValueError, IndexError):
            continue
    
    return max_idx


# Test function definitions with parameters
TEST_FUNCTIONS = {
    "Pulse-Read-Repeat": {
        "function": "pulse_read_repeat",
        "description": "Pattern: Initial Read → (Pulse → Read → Delay) × N\nBasic pulse response with immediate read after each pulse",
        "params": {
            "pulse_voltage": {"default": 1.5, "label": "Pulse Voltage (V)", "type": "float"},
            "pulse_width": {"default": 1.0, "label": "Pulse Width (ms)", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "delay_between": {"default": 10.0, "label": "Delay Between (ms)", "type": "float"},
            "num_cycles": {"default": 100, "label": "Number of Cycles", "type": "int"},
            "clim": {"default": 100e-6, "label": "Current Limit (A)", "type": "float"},
        },
        "plot_type": "time_series",
    },
    
    
    "Multi-Pulse-Then-Read": {
        "function": "multi_pulse_then_read",
        "description": "Pattern: Initial Read → (Pulse×N → Read×M) × Cycles\nMultiple pulses then multiple reads per cycle",
        "params": {
            "pulse_voltage": {"default": 1.5, "label": "Pulse Voltage (V)", "type": "float"},
            "num_pulses_per_read": {"default": 10, "label": "Pulses Per Cycle", "type": "int"},
            "pulse_width": {"default": 1.0, "label": "Pulse Width (ms)", "type": "float"},
            "delay_between_pulses": {"default": 1.0, "label": "Delay Between Pulses (ms)", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "num_reads": {"default": 1, "label": "Reads Per Cycle", "type": "int"},
            "delay_between_reads": {"default": 10.0, "label": "Delay Between Reads (ms)", "type": "float"},
            "num_cycles": {"default": 20, "label": "Number of Cycles", "type": "int"},
            "delay_between_cycles": {"default": 10.0, "label": "Delay Between Cycles (ms)", "type": "float"},
            "clim": {"default": 100e-6, "label": "Current Limit (A)", "type": "float"},
        },
        "plot_type": "time_series",
    },
    
    "Width Sweep": {
        "function": "width_sweep_with_reads",
        "description": "Pattern: Initial Read, (Pulse→Read)×N, Reset (per width)\nFind optimal pulse timing, measure speed dependence",
        "params": {
            "pulse_voltage": {"default": 1.5, "label": "Pulse Voltage (V)", "type": "float"},
            "pulse_widths": {"default": "1e-3,5e-3,10e-3,50e-3", "label": "Pulse Widths (comma-separated, s)", "type": "list"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "num_pulses_per_width": {"default": 5, "label": "Pulses Per Width", "type": "int"},
            "reset_voltage": {"default": -1.0, "label": "Reset Voltage (V)", "type": "float"},
            "reset_width": {"default": 1e-3, "label": "Reset Width (s)", "type": "float"},
            "delay_between_widths": {"default": 5.0, "label": "Relaxation Delay Between Width Blocks (s)", "type": "float"},
            "clim": {"default": 100e-6, "label": "Current Limit (A)", "type": "float"},
        },
        "plot_type": "width_vs_resistance",
    },
    
    "Width Sweep (Full)": {
        "function": "width_sweep_with_all_measurements",
        "description": "Pattern: Initial Read, (Pulse(measured)→Read)×N, Reset (per width)\nFull characterization including pulse peak currents",
        "params": {
            "pulse_voltage": {"default": 1.5, "label": "Pulse Voltage (V)", "type": "float"},
            "pulse_widths": {"default": "1e-3,5e-3,10e-3", "label": "Pulse Widths (comma-separated, s)", "type": "list"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "num_pulses_per_width": {"default": 5, "label": "Pulses Per Width", "type": "int"},
            "reset_voltage": {"default": -1.0, "label": "Reset Voltage (V)", "type": "float"},
            "reset_width": {"default": 1e-3, "label": "Reset Width (s)", "type": "float"},
            "delay_between_widths": {"default": 5.0, "label": "Relaxation Delay Between Width Blocks (s)", "type": "float"},
            "clim": {"default": 100e-6, "label": "Current Limit (A)", "type": "float"},
        },
        "plot_type": "width_vs_resistance",
    },
    
    "Potentiation-Depression Cycle": {
        "function": "potentiation_depression_cycle",
        "description": "Pattern: Initial Read → (Gradual SET → Gradual RESET) × N cycles\nSynaptic weight update, neuromorphic applications",
        "params": {
            "set_voltage": {"default": 2.0, "label": "SET Voltage (V)", "type": "float"},
            "reset_voltage": {"default": -2.0, "label": "RESET Voltage (V)", "type": "float"},
            "pulse_width": {"default": 1.0, "label": "Pulse Width (ms)", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "steps": {"default": 20, "label": "Steps (each direction)", "type": "int"},
            "num_cycles": {"default": 1, "label": "Number of Cycles", "type": "int"},
            "delay_between": {"default": 10.0, "label": "Delay Between (ms)", "type": "float"},
            "clim": {"default": 100e-6, "label": "Current Limit (A)", "type": "float"},
        },
        "plot_type": "pot_dep_cycle",
    },
    
    "Potentiation Only": {
        "function": "potentiation_only",
        "description": "Pattern: Initial Read → Repeated SET pulses with reads\nOptional post-pulse reads to observe relaxation",
        "params": {
            "set_voltage": {"default": 2.0, "label": "SET Voltage (V)", "type": "float"},
            "pulse_width": {"default": 1.0, "label": "Pulse Width (ms)", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "num_pulses": {"default": 30, "label": "Number of Pulses", "type": "int"},
            "delay_between": {"default": 10.0, "label": "Delay Between (ms)", "type": "float"},
            "num_post_reads": {"default": 0, "label": "Post-Pulse Reads (0=disabled)", "type": "int"},
            "post_read_interval": {"default": 1.0, "label": "Post-Read Interval (ms)", "type": "float"},
            "clim": {"default": 100e-6, "label": "Current Limit (A)", "type": "float"},
        },
        "plot_type": "time_series",
    },
    
    "Depression Only": {
        "function": "depression_only",
        "description": "Pattern: Initial Read → Repeated RESET pulses with reads\nOptional post-pulse reads to observe relaxation",
        "params": {
            "reset_voltage": {"default": -2.0, "label": "RESET Voltage (V)", "type": "float"},
            "pulse_width": {"default": 1.0, "label": "Pulse Width (ms)", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "num_pulses": {"default": 30, "label": "Number of Pulses", "type": "int"},
            "delay_between": {"default": 10.0, "label": "Delay Between (ms)", "type": "float"},
            "num_post_reads": {"default": 0, "label": "Post-Pulse Reads (0=disabled)", "type": "int"},
            "post_read_interval": {"default": 1.0, "label": "Post-Read Interval (ms)", "type": "float"},
            "clim": {"default": 100e-6, "label": "Current Limit (A)", "type": "float"},
        },
        "plot_type": "time_series",
    },
    
    "Endurance Test": {
        "function": "endurance_test",
        "description": "Pattern: Initial Read → (SET → Read → RESET → Read) × N\nDevice lifetime, cycling endurance monitoring",
        "params": {
            "set_voltage": {"default": 2.0, "label": "SET Voltage (V)", "type": "float"},
            "reset_voltage": {"default": -2.0, "label": "RESET Voltage (V)", "type": "float"},
            "pulse_width": {"default": 1.0, "label": "Pulse Width (ms)", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "num_cycles": {"default": 100, "label": "Number of Cycles", "type": "int"},
            "delay_between": {"default": 10.0, "label": "Delay Between (ms)", "type": "float"},
            "clim": {"default": 100e-6, "label": "Current Limit (A)", "type": "float"},
        },
        "plot_type": "endurance",
    },
    
    "Pulse-Multi-Read": {
        "function": "pulse_multi_read",
        "description": "Pattern: Initial Read → (Pulse × M) → Read × N\nMonitor state relaxation/drift after pulses",
        "params": {
            "pulse_voltage": {"default": 1.5, "label": "Pulse Voltage (V)", "type": "float"},
            "pulse_width": {"default": 1.0, "label": "Pulse Width (ms)", "type": "float"},
            "num_pulses": {"default": 1, "label": "Number of Pulses", "type": "int"},
            "delay_between_pulses": {"default": 1.0, "label": "Delay Between Pulses (ms)", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "num_reads": {"default": 50, "label": "Number of Reads", "type": "int"},
            "delay_between_reads": {"default": 100.0, "label": "Delay Between Reads (ms)", "type": "float"},
            "clim": {"default": 100e-6, "label": "Current Limit (A)", "type": "float"},
        },
        "plot_type": "time_series",
    },
    
    "Multi-Read Only": {
        "function": "multi_read_only",
        "description": "Pattern: Just reads, no pulses\nBaseline noise, read disturb characterization",
        "params": {
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "num_reads": {"default": 100, "label": "Number of Reads", "type": "int"},
            "delay_between": {"default": 100.0, "label": "Delay Between (ms)", "type": "float"},
            "clim": {"default": 100e-6, "label": "Current Limit (A)", "type": "float"},
        },
        "plot_type": "time_series",
    },
    
    "Current Range Finder": {
        "function": "current_range_finder",
        "description": "Find optimal current measurement range\nTests multiple ranges and recommends best for your device",
        "params": {
            "test_voltage": {"default": 0.2, "label": "Test Voltage (V)", "type": "float"},
            "num_reads_per_range": {"default": 10, "label": "Reads Per Range", "type": "int"},
            "delay_between_reads": {"default": 10.0, "label": "Delay Between Reads (ms)", "type": "float"},
            "current_ranges": {"default": "0.001,0.0001,0.00001,0.000001", "label": "Ranges to Test (comma-separated, A)", "type": "list"},
        },
        "plot_type": "range_finder",
    },
    
    "Relaxation After Multi-Pulse": {
        "function": "relaxation_after_multi_pulse",
        "description": "Pattern: 1×Read → N×Pulse → N×Read\nFind how device relaxes after cumulative pulsing",
        "params": {
            "pulse_voltage": {"default": 1.5, "label": "Pulse Voltage (V)", "type": "float"},
            "num_pulses": {"default": 10, "label": "Number of Pulses", "type": "int"},
            "pulse_width": {"default": 1.0, "label": "Pulse Width (ms)", "type": "float"},
            "delay_between_pulses": {"default": 1.0, "label": "Delay Between Pulses (ms)", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "num_reads": {"default": 10, "label": "Number of Reads", "type": "int"},
            "delay_between_reads": {"default": 0.1, "label": "Delay Between Reads (ms)", "type": "float"},
            "clim": {"default": 100e-6, "label": "Current Limit (A)", "type": "float"},
        },
        "plot_type": "relaxation_reads",
    },
    
    "Relaxation After Multi-Pulse With Pulse Measurement": {
        "function": "relaxation_after_multi_pulse_with_pulse_measurement",
        "description": "Pattern: 1×Read → N×Pulse(measured) → N×Read\nFull relaxation with pulse peak currents",
        "params": {
            "pulse_voltage": {"default": 1.5, "label": "Pulse Voltage (V)", "type": "float"},
            "num_pulses": {"default": 10, "label": "Number of Pulses", "type": "int"},
            "pulse_width": {"default": 1.0, "label": "Pulse Width (ms)", "type": "float"},
            "delay_between_pulses": {"default": 1.0, "label": "Delay Between Pulses (ms)", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "num_reads": {"default": 10, "label": "Number of Reads", "type": "int"},
            "delay_between_reads": {"default": 0.1, "label": "Delay Between Reads (ms)", "type": "float"},
            "clim": {"default": 100e-6, "label": "Current Limit (A)", "type": "float"},
        },
        "plot_type": "relaxation_all",
    },
    
    "Voltage Amplitude Sweep": {
        "function": "voltage_amplitude_sweep",
        "description": "Pattern: For each voltage: Initial Read → (Pulse → Read) × N → Reset\nTest different pulse voltages at fixed width (complementary to width sweep)",
        "params": {
            "pulse_voltage_start": {"default": 0.5, "label": "Start Voltage (V)", "type": "float"},
            "pulse_voltage_stop": {"default": 2.5, "label": "Stop Voltage (V)", "type": "float"},
            "pulse_voltage_step": {"default": 0.1, "label": "Voltage Step (V)", "type": "float"},
            "pulse_width": {"default": 1.0, "label": "Pulse Width (ms)", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "num_pulses_per_voltage": {"default": 5, "label": "Pulses Per Voltage", "type": "int"},
            "delay_between": {"default": 10.0, "label": "Delay Between (ms)", "type": "float"},
            "reset_voltage": {"default": -1.0, "label": "Reset Voltage (V)", "type": "float"},
            "reset_width": {"default": 1.0, "label": "Reset Width (ms)", "type": "float"},
            "delay_between_voltages": {"default": 1000.0, "label": "Delay Between Voltages (ms)", "type": "float"},
            "clim": {"default": 100e-6, "label": "Current Limit (A)", "type": "float"},
        },
        "plot_type": "voltage_sweep",
    },
    
    "ISPP (Incremental Step Pulse Programming)": {
        "function": "ispp_test",
        "description": "Pattern: Start at low voltage, increase by step each pulse\nGradually increase voltage until switching occurs",
        "params": {
            "start_voltage": {"default": 0.5, "label": "Start Voltage (V)", "type": "float"},
            "voltage_step": {"default": 0.05, "label": "Voltage Step (V)", "type": "float"},
            "max_voltage": {"default": 3.0, "label": "Max Voltage (V)", "type": "float"},
            "pulse_width": {"default": 1.0, "label": "Pulse Width (ms)", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "max_pulses": {"default": 100, "label": "Max Pulses", "type": "int"},
            "delay_between": {"default": 10.0, "label": "Delay Between (ms)", "type": "float"},
            "clim": {"default": 100e-6, "label": "Current Limit (A)", "type": "float"},
        },
        "plot_type": "ispp",
    },
    
    "Switching Threshold Finder": {
        "function": "switching_threshold_test",
        "description": "Pattern: Try increasing voltages, find minimum that causes switching\nFind minimum SET or RESET voltage",
        "params": {
            "direction": {"default": "set", "label": "Direction (set/reset)", "type": "str"},
            "start_voltage": {"default": 0.5, "label": "Start Voltage (V)", "type": "float"},
            "voltage_step": {"default": 0.05, "label": "Voltage Step (V)", "type": "float"},
            "max_voltage": {"default": 3.0, "label": "Max Voltage (V)", "type": "float"},
            "pulse_width": {"default": 1.0, "label": "Pulse Width (ms)", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "num_pulses_per_voltage": {"default": 3, "label": "Pulses Per Voltage", "type": "int"},
            "delay_between": {"default": 10.0, "label": "Delay Between (ms)", "type": "float"},
            "clim": {"default": 100e-6, "label": "Current Limit (A)", "type": "float"},
        },
        "plot_type": "threshold",
    },
    
    "Multilevel Programming": {
        "function": "multilevel_programming",
        "description": "Pattern: For each level: Reset → Program with pulses → Read\nTarget specific resistance states for multilevel memory",
        "params": {
            "target_levels": {"default": "1,2,3,4,5", "label": "Target Levels (comma-separated)", "type": "list"},
            "pulse_voltage": {"default": 1.5, "label": "Pulse Voltage (V)", "type": "float"},
            "pulse_width": {"default": 1.0, "label": "Pulse Width (ms)", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "num_pulses_per_level": {"default": 5, "label": "Pulses Per Level", "type": "int"},
            "delay_between": {"default": 10.0, "label": "Delay Between (ms)", "type": "float"},
            "reset_voltage": {"default": -1.0, "label": "Reset Voltage (V)", "type": "float"},
            "reset_width": {"default": 1.0, "label": "Reset Width (ms)", "type": "float"},
            "delay_between_levels": {"default": 1000.0, "label": "Delay Between Levels (ms)", "type": "float"},
            "clim": {"default": 100e-6, "label": "Current Limit (A)", "type": "float"},
        },
        "plot_type": "multilevel",
    },
    
    "Pulse Train with Varying Amplitudes": {
        "function": "pulse_train_varying_amplitudes",
        "description": "Pattern: Initial Read → (Pulse1 → Read → Pulse2 → Read → ...) × N\nAlternating or varying amplitude pulses",
        "params": {
            "pulse_voltages": {"default": "1.0,1.5,2.0,-1.0,-1.5,-2.0", "label": "Pulse Voltages (comma-separated, V)", "type": "list"},
            "pulse_width": {"default": 1.0, "label": "Pulse Width (ms)", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "num_repeats": {"default": 1, "label": "Number of Repeats", "type": "int"},
            "delay_between": {"default": 10.0, "label": "Delay Between (ms)", "type": "float"},
            "clim": {"default": 100e-6, "label": "Current Limit (A)", "type": "float"},
        },
        "plot_type": "pulse_train",
    },
}


class TSPTestingGUI(tk.Toplevel):
    """Multi-System Pulse Testing GUI
    
    Supports Keithley 2450 (TSP) and Keithley 4200A-SCS (KXCI).
    Automatically routes tests to appropriate system based on device address.
    """
    
    def __init__(self, master, device_address: str = "USB0::0x05E6::0x2450::04496615::INSTR", provider=None):
        super().__init__(master)
        self.title("Multi-System Pulse Testing")
        self.geometry("1400x900")
        self.resizable(True, True)
        
        # State
        self.tsp = None
        self.test_scripts = None  # Legacy - kept for backward compatibility
        self.provider = provider
        self.device_address = device_address
        self.current_test = None
        self.test_running = False
        self.test_thread = None
        self.last_results = None
        
        # New modular system wrapper
        self.system_wrapper = SystemWrapper()
        self.current_system_name = None  # Track which system is connected
        
        # Context from provider
        self.sample_name = "UnknownSample"
        self.device_label = "A"
        
        # Save location - load from config
        self.custom_base_path = self._load_custom_save_location()
        
        # Simple save location (for TSP GUI independent mode)
        self.use_simple_save_var = tk.BooleanVar()
        self.simple_save_path_var = tk.StringVar()
        self.simple_save_path = None
        self._load_simple_save_config()
        
        # Create UI
        self.create_ui()
        
        # Attempt auto-connect
        self.after(500, self.auto_connect)
    
    def create_ui(self):
        """Create the main UI layout"""
        # Main container
        main_frame = tk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left panel: Controls with scrollbar
        left_container = tk.Frame(main_frame, width=450)
        left_container.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 5))
        left_container.pack_propagate(False)
        
        # Create scrollable canvas for left panel
        left_canvas = tk.Canvas(left_container, highlightthickness=0)
        left_scrollbar = ttk.Scrollbar(left_container, orient="vertical", command=left_canvas.yview)
        left_panel = tk.Frame(left_canvas)
        
        # Create window in canvas for the frame
        left_canvas_window = left_canvas.create_window((0, 0), window=left_panel, anchor="nw")
        left_canvas.configure(yscrollcommand=left_scrollbar.set)
        
        # Configure scrollable region and update canvas window width
        def update_scroll_region(event=None):
            left_canvas.configure(scrollregion=left_canvas.bbox("all"))
            # Update canvas window width to match canvas width
            canvas_width = left_canvas.winfo_width()
            if canvas_width > 1:  # Only update if canvas has been rendered
                left_canvas.itemconfig(left_canvas_window, width=canvas_width)
        
        left_panel.bind("<Configure>", update_scroll_region)
        left_canvas.bind("<Configure>", lambda e: left_canvas.itemconfig(left_canvas_window, width=e.width))
        
        # Pack scrollbar and canvas
        left_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        left_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Bind mousewheel to canvas (for Windows)
        def _on_mousewheel(event):
            left_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        left_canvas.bind("<MouseWheel>", _on_mousewheel)
        # Also bind to the frame for better responsiveness
        left_panel.bind("<MouseWheel>", lambda e: left_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        
        # Right panel: Visualizations
        right_panel = tk.Frame(main_frame)
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Create sections (order matters - params_frame must exist before on_test_selected is called)
        self.create_connection_section(left_panel)
        self.create_pulse_diagram_section(right_panel)  # NEW: Visual diagram
        self.create_parameters_section(left_panel)  # Must be before test_selection!
        self.create_test_selection_section(left_panel)  # This calls on_test_selected
        self.create_control_buttons_section(left_panel)
        self.create_status_section(left_panel)
        self.create_plot_section(right_panel)
    
    def create_connection_section(self, parent):
        """Connection controls"""
        frame = tk.LabelFrame(parent, text="Connection", padx=5, pady=5)
        frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Context display
        self.context_var = tk.StringVar(value=f"Sample: {self.sample_name}  |  Device: {self.device_label}")
        tk.Label(frame, textvariable=self.context_var, font=("TkDefaultFont", 9, "bold")).pack(anchor="w", pady=(0, 5))
        
        # System selection (FIRST - above device)
        system_frame = tk.Frame(frame)
        system_frame.pack(fill=tk.X, pady=2)
        tk.Label(system_frame, text="System:").pack(side=tk.LEFT)
        
        self.system_var = tk.StringVar()
        # Auto-detect system from address
        detected_system = detect_system_from_address(self.device_address)
        if detected_system:
            self.system_var.set(detected_system)
        else:
            self.system_var.set("keithley2450")  # Default
        
        system_combo = ttk.Combobox(system_frame, textvariable=self.system_var,
                                   values=["keithley2450", "keithley2450_sim", "keithley4200a"],
                                   state="readonly", width=20)
        system_combo.pack(side=tk.LEFT, padx=5)
        
        # Auto-detect button
        tk.Button(system_frame, text="🔍 Auto", command=self._auto_detect_system,
                 width=6, font=("TkDefaultFont", 8)).pack(side=tk.LEFT, padx=2)
        
        # When system changes, update device address to default
        self.system_var.trace_add("write", lambda *args: self._on_system_changed())
        
        # Device address with dropdown (SECOND - below system)
        addr_frame = tk.Frame(frame)
        addr_frame.pack(fill=tk.X, pady=(5, 2))
        tk.Label(addr_frame, text="Device:").pack(side=tk.LEFT)
        
        self.addr_var = tk.StringVar()
        # Set initial address based on detected system
        if detected_system:
            default_addr = get_default_address_for_system(detected_system)
            if default_addr:
                self.addr_var.set(default_addr)
            else:
                self.addr_var.set(self.device_address)
        else:
            self.addr_var.set(self.device_address)
        
        # Get available devices
        available_devices = self._get_available_devices()
        current_addr = self.addr_var.get()
        if current_addr not in available_devices and available_devices:
            # Add current address if not in list
            available_devices.insert(0, current_addr)
        
        self.addr_combo = ttk.Combobox(addr_frame, textvariable=self.addr_var,
                                       values=available_devices,
                                       width=37, state="readonly")
        self.addr_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Refresh button to re-scan devices
        tk.Button(addr_frame, text="🔄", command=self._refresh_devices, 
                 width=3, font=("TkDefaultFont", 8)).pack(side=tk.LEFT, padx=2)
        
        # Update system detection when address changes (optional auto-detect)
        self.addr_var.trace_add("write", lambda *args: self._update_system_detection())
        
        # Terminal selection
        term_frame = tk.Frame(frame)
        term_frame.pack(fill=tk.X, pady=(5, 2))
        tk.Label(term_frame, text="Terminals:").pack(side=tk.LEFT)
        self.terminals_var = tk.StringVar()
        # Load default from config
        default_terminals = self.load_default_terminals()
        self.terminals_var.set(default_terminals)
        tk.Radiobutton(term_frame, text="Front", variable=self.terminals_var, 
                      value="front", command=self.save_terminal_default).pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(term_frame, text="Rear", variable=self.terminals_var, 
                      value="rear", command=self.save_terminal_default).pack(side=tk.LEFT, padx=5)
        
        # Connect button
        btn_frame = tk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=5)
        tk.Button(btn_frame, text="Connect", command=self.connect_device, bg="green", fg="white").pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="Disconnect", command=self.disconnect_device).pack(side=tk.LEFT, padx=2)
        
        # Status
        self.conn_status_var = tk.StringVar(value="Disconnected")
        tk.Label(frame, textvariable=self.conn_status_var, fg="red").pack(anchor="w")
        
        # Save location toggle (small, inside connection box)
        save_frame = tk.Frame(frame)
        save_frame.pack(fill=tk.X, pady=(8, 0))
        
        tk.Checkbutton(save_frame, text="Simple Save:", variable=self.use_simple_save_var,
                      command=self._on_simple_save_toggle, font=("TkDefaultFont", 8)).pack(side=tk.LEFT)
        
        self.simple_save_entry = tk.Entry(save_frame, textvariable=self.simple_save_path_var, 
                                          width=25, state="disabled", font=("TkDefaultFont", 8))
        self.simple_save_entry.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        tk.Button(save_frame, text="📁", command=self._browse_simple_save, 
                 state="disabled", width=2, font=("TkDefaultFont", 8)).pack(side=tk.LEFT, padx=1)
    
    def create_test_selection_section(self, parent):
        """Test type selection"""
        frame = tk.LabelFrame(parent, text="Test Selection", padx=5, pady=5)
        frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Dropdown
        tk.Label(frame, text="Test Type:", font=("TkDefaultFont", 9, "bold")).pack(anchor="w")
        self.test_var = tk.StringVar()
        self.test_combo = ttk.Combobox(frame, textvariable=self.test_var, 
                                       values=list(TEST_FUNCTIONS.keys()), 
                                       state="readonly", width=35)
        self.test_combo.pack(fill=tk.X, pady=5)
        self.test_combo.bind("<<ComboboxSelected>>", self.on_test_selected)
        self.test_combo.current(0)  # Select first test
        
        # Description
        tk.Label(frame, text="Description:", font=("TkDefaultFont", 9, "bold")).pack(anchor="w", pady=(5,0))
        self.desc_text = tk.Text(frame, height=4, wrap=tk.WORD, bg="#f0f0f0", relief=tk.FLAT, 
                                font=("TkDefaultFont", 9))
        self.desc_text.pack(fill=tk.X, pady=2)
        self.desc_text.config(state=tk.DISABLED)
        
        # Update description and diagram
        self.on_test_selected(None)
    
    def create_pulse_diagram_section(self, parent):
        """Visual pulse pattern diagram"""
        frame = tk.LabelFrame(parent, text="📊 Pulse Pattern Preview", padx=5, pady=5)
        frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Create matplotlib figure for pulse diagram
        self.diagram_fig = Figure(figsize=(6, 2.5), dpi=100)
        self.diagram_ax = self.diagram_fig.add_subplot(111)
        self.diagram_fig.tight_layout(pad=2.0)
        
        self.diagram_canvas = FigureCanvasTkAgg(self.diagram_fig, master=frame)
        self.diagram_canvas.draw()
        self.diagram_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Initialize with first test pattern
        self.update_pulse_diagram()
    
    def create_parameters_section(self, parent):
        """Parameter inputs"""
        frame = tk.LabelFrame(parent, text="Test Parameters", padx=5, pady=5)
        frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Preset controls at top
        preset_frame = tk.Frame(frame)
        preset_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        
        tk.Label(preset_frame, text="Presets:", font=("TkDefaultFont", 9, "bold")).pack(side=tk.LEFT, padx=(0, 5))
        
        self.preset_var = tk.StringVar()
        self.preset_dropdown = ttk.Combobox(preset_frame, textvariable=self.preset_var, 
                                            state="readonly", width=20)
        self.preset_dropdown.pack(side=tk.LEFT, padx=2)
        self.preset_dropdown.bind("<<ComboboxSelected>>", lambda e: self.load_preset())
        
        tk.Button(preset_frame, text="💾 Save", command=self.save_preset, 
                 font=("TkDefaultFont", 8), width=6).pack(side=tk.LEFT, padx=2)
        tk.Button(preset_frame, text="🗑️ Del", command=self.delete_preset, 
                 font=("TkDefaultFont", 8), width=6).pack(side=tk.LEFT, padx=2)
        
        # Scrollable frame
        canvas = tk.Canvas(frame, height=300)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        self.params_frame = tk.Frame(canvas)
        
        self.params_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.params_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.param_vars = {}
        self.presets = self.load_presets_from_file()
        self.populate_parameters()
    
    def create_control_buttons_section(self, parent):
        """Run/Stop/Save buttons"""
        frame = tk.LabelFrame(parent, text="Control", padx=5, pady=5)
        frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Run button - large and prominent
        self.run_btn = tk.Button(frame, text="▶  RUN TEST", command=self.run_test, 
                                 bg="#28a745", fg="white", font=("TkDefaultFont", 12, "bold"),
                                 height=2, relief=tk.RAISED, bd=3, cursor="hand2")
        self.run_btn.pack(fill=tk.X, pady=(0, 5))
        
        # Secondary buttons
        btn_frame = tk.Frame(frame)
        btn_frame.pack(fill=tk.X)
        
        self.stop_btn = tk.Button(btn_frame, text="⏹ Stop", command=self.stop_test, 
                                  bg="#dc3545", fg="white", state=tk.DISABLED, font=("TkDefaultFont", 9))
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 2), fill=tk.X, expand=True)
        
        self.save_btn = tk.Button(btn_frame, text="💾 Manual Save", command=self.manual_save_with_notes, 
                                  state=tk.DISABLED, font=("TkDefaultFont", 9))
        self.save_btn.pack(side=tk.LEFT, padx=(2, 2), fill=tk.X, expand=True)
        
        # Data Analysis button
        analysis_btn = tk.Button(btn_frame, text="📊 Analysis", command=self.open_data_analysis, 
                                bg="#FF9800", fg="white", font=("TkDefaultFont", 9))
        analysis_btn.pack(side=tk.LEFT, padx=(2, 0), fill=tk.X, expand=True)
        
        # Auto-save toggle
        auto_save_frame = tk.Frame(frame)
        auto_save_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.auto_save_var = tk.BooleanVar(value=True)  # Default: auto-save enabled
        auto_save_check = tk.Checkbutton(auto_save_frame, text="🔄 Auto-save data after test completion",
                                        variable=self.auto_save_var, font=("TkDefaultFont", 9))
        auto_save_check.pack(anchor="w")
        
        # Filename suffix section
        suffix_frame = tk.LabelFrame(frame, text="📝 Filename Suffix (optional - added to filename)", padx=5, pady=5)
        suffix_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.filename_suffix_var = tk.StringVar()
        suffix_entry = tk.Entry(suffix_frame, textvariable=self.filename_suffix_var, 
                               font=("TkDefaultFont", 9), width=30)
        suffix_entry.pack(fill=tk.X, padx=2, pady=2)
        tk.Label(suffix_frame, text="Example: 'test1', 'batchA', 'highTemp'", 
                font=("TkDefaultFont", 7), fg="gray").pack(anchor="w", padx=2)
        
        # Notes section
        notes_frame = tk.LabelFrame(frame, text="📝 Test Notes (optional - saved with data)", padx=5, pady=5)
        notes_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.notes_text = tk.Text(notes_frame, height=3, wrap=tk.WORD, font=("TkDefaultFont", 9))
        self.notes_text.pack(fill=tk.X)
        self.notes_text.insert(1.0, "Add notes about this test here...")
    
    def create_status_section(self, parent):
        """Status/log display"""
        frame = tk.LabelFrame(parent, text="Status", padx=5, pady=5)
        frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.status_text = tk.Text(frame, height=6, wrap=tk.WORD, bg="black", fg="lime", 
                                   font=("Courier", 8))
        self.status_text.pack(fill=tk.X)
        self.log("TSP Testing GUI initialized")
    
    def create_plot_section(self, parent):
        """Matplotlib plot area"""
        frame = tk.LabelFrame(parent, text="Live Plot", padx=5, pady=5)
        frame.pack(fill=tk.BOTH, expand=True)
        
        self.fig = Figure(figsize=(8, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_title("No data yet")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Resistance (Ω)")
        self.ax.grid(True, alpha=0.3)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)
        
        # Add navigation toolbar for zoom/pan/save
        self.toolbar = NavigationToolbar2Tk(self.canvas, frame)
        self.toolbar.update()
        self.toolbar.pack(side=tk.TOP, fill=tk.X)
    
    def auto_connect(self):
        """Auto-connect on startup"""
        # Update context from provider (like PMU GUI does)
        self._poll_context()
        
        # Try to get device address from provider (if Measurement GUI has one)
        if self.provider:
            try:
                # Check if provider has keithley_address_var (from Measurement GUI)
                addr_var = getattr(self.provider, 'keithley_address_var', None)
                if addr_var is not None:
                    addr = addr_var.get()
                    if addr and addr.strip():
                        self.addr_var.set(addr)
                        self.log(f"Using device address from provider: {addr}")
            except Exception as e:
                self.log(f"Could not get address from provider: {e}")
        
        # Try to connect
        self.connect_device()
    
    def _poll_context(self):
        """Poll provider for updated sample name and device (like PMU GUI)"""
        try:
            if self.provider is not None:
                # Measurement_GUI has sample_name_var and final_device_letter/number
                sn = getattr(self.provider, 'sample_name_var', None)
                name = sn.get().strip() if sn is not None else None
                letter = getattr(self.provider, 'final_device_letter', None)
                number = getattr(self.provider, 'final_device_number', None)
                if name:
                    self.sample_name = name
                if letter and number:
                    self.device_label = f"{letter}{number}"
                
                # Check if provider has custom save location enabled
                use_custom = getattr(self.provider, 'use_custom_save_var', None)
                if use_custom and use_custom.get():
                    custom_path = getattr(self.provider, 'custom_save_location', None)
                    if custom_path:
                        # Use Measurement GUI's custom save location
                        self.custom_base_path = Path(custom_path)
                        # Extract sample name from the last part of the custom path
                        # e.g., "C:\...\D80-0.1mgml-ITO-PMMA(2%)-Gold-s2" -> "D80-0.1mgml-ITO-PMMA(2%)-Gold-s2"
                        sample_from_path = Path(custom_path).name
                        if sample_from_path:
                            self.sample_name = sample_from_path
                        # Disable simple save mode when using Measurement GUI's custom location
                        self.use_simple_save_var.set(False)
            self.context_var.set(f"Sample: {self.sample_name}  |  Device: {self.device_label}")
        except Exception:
            pass
        # Poll every 500ms like PMU GUI
        self.after(500, self._poll_context)
    
    def _load_custom_save_location(self) -> Optional[Path]:
        """Load custom save location from config file"""
        config_file = Path("Json_Files/save_location_config.json")
        try:
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    use_custom = config.get('use_custom_save', False)
                    custom_path = config.get('custom_save_path', '')
                    if use_custom and custom_path:
                        return Path(custom_path)
        except Exception as e:
            print(f"Could not load save location config: {e}")
        return None  # None means use default
    
    def load_default_terminals(self) -> str:
        """Load default terminal setting from config file"""
        config_file = Path("Json_Files/tsp_gui_config.json")
        try:
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    terminals = config.get('default_terminals', 'front')
                    if terminals.lower() in ['front', 'rear']:
                        return terminals.lower()
        except Exception as e:
            print(f"Could not load terminal config: {e}")
        return 'front'  # Default to front
    
    def save_terminal_default(self):
        """Save current terminal selection as default"""
        config_file = Path("Json_Files/tsp_gui_config.json")
        try:
            config = {}
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = json.load(f)
            
            config['default_terminals'] = self.terminals_var.get()
            
            config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            self.log(f"💾 Default terminals saved: {self.terminals_var.get().upper()}")
        except Exception as e:
            self.log(f"⚠️ Could not save terminal config: {e}")
    
    def _on_simple_save_toggle(self):
        """Handle simple save checkbox toggle"""
        if self.use_simple_save_var.get():
            self.simple_save_entry.config(state="normal")
            # Enable browse button
            for widget in self.simple_save_entry.master.winfo_children():
                if isinstance(widget, tk.Button):
                    widget.config(state="normal")
            # If no path set, prompt for one
            if not self.simple_save_path_var.get():
                self._browse_simple_save()
        else:
            self.simple_save_entry.config(state="disabled")
            # Disable browse button
            for widget in self.simple_save_entry.master.winfo_children():
                if isinstance(widget, tk.Button):
                    widget.config(state="disabled")
            self.simple_save_path = None
            self.simple_save_path_var.set("")
        
        # Save preference
        self._save_simple_save_config()
    
    def _browse_simple_save(self):
        """Open folder picker for simple save location"""
        from tkinter import filedialog
        folder = filedialog.askdirectory(
            title="Choose Simple Save Location",
            mustexist=False
        )
        if folder:
            self.simple_save_path = Path(folder)
            self.simple_save_path_var.set(str(self.simple_save_path))
            # Save preference
            self._save_simple_save_config()
    
    def _load_simple_save_config(self):
        """Load simple save location preference from config file"""
        config_file = Path("Json_Files/tsp_gui_save_config.json")
        try:
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    use_simple = config.get('use_simple_save', False)
                    simple_path = config.get('simple_save_path', '')
                    
                    self.use_simple_save_var.set(use_simple)
                    if use_simple and simple_path:
                        self.simple_save_path = Path(simple_path)
                        self.simple_save_path_var.set(simple_path)
        except Exception as e:
            print(f"Could not load simple save config: {e}")
    
    def _save_simple_save_config(self):
        """Save simple save location preference to config file"""
        config_file = Path("Json_Files/tsp_gui_save_config.json")
        try:
            config = {}
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = json.load(f)
            
            config['use_simple_save'] = self.use_simple_save_var.get()
            config['simple_save_path'] = str(self.simple_save_path) if self.simple_save_path else ""
            
            config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Could not save simple save config: {e}")
    
    def _get_available_devices(self) -> List[str]:
        """Scan and return list of available USB and GPIB devices"""
        devices = []
        try:
            import pyvisa
            rm = pyvisa.ResourceManager()
            resources = rm.list_resources()
            
            # Filter for USB and GPIB devices (Keithley 2450 typically uses USB)
            for res in resources:
                if res.startswith('USB') or res.startswith('GPIB'):
                    devices.append(res)
            
            # If no devices found, at least return the current one
            if not devices:
                devices = [self.device_address]
            
        except Exception as e:
            print(f"Could not scan devices: {e}")
            devices = [self.device_address]
        
        return devices
    
    def _refresh_devices(self):
        """Refresh the device dropdown list"""
        available_devices = self._get_available_devices()
        current_selection = self.addr_var.get()
        
        # Update combobox values
        if current_selection not in available_devices:
            available_devices.insert(0, current_selection)
        self.addr_combo['values'] = available_devices
        
        self.log(f"🔄 Refreshed device list: {len(available_devices)} device(s) found")
    
    def _auto_detect_system(self):
        """Auto-detect system from current address"""
        address = self.addr_var.get()
        detected = detect_system_from_address(address)
        if detected:
            self.system_var.set(detected)
            self.log(f"🔍 Auto-detected system: {detected}")
        else:
            self.log(f"⚠️ Could not auto-detect system from address: {address}")
            messagebox.showinfo("Auto-Detect", 
                              f"Could not detect system from address.\n"
                              f"Please select manually or use a recognized format.")
    
    def _on_system_changed(self):
        """When system changes, update device address to system default"""
        system_name = self.system_var.get()
        default_addr = get_default_address_for_system(system_name)
        if default_addr:
            self.addr_var.set(default_addr)
            # Update available devices list
            available_devices = self._get_available_devices()
            if default_addr not in available_devices:
                available_devices.insert(0, default_addr)
            self.addr_combo['values'] = available_devices
            self.log(f"🔧 Auto-populated device address for {system_name}: {default_addr}")
        
        # Update current_system_name for parameter unit conversion
        # (even if not connected, this affects default display units)
        if not self.system_wrapper.is_connected():
            self.current_system_name = system_name
        
        # Refresh parameters to show correct units (ms for 2450, µs for 4200A)
        if hasattr(self, 'test_var') and self.test_var.get():
            self.populate_parameters()
    
    def _update_system_detection(self):
        """Update system selection when address changes (optional - user can override)"""
        # Only auto-detect if user hasn't manually changed system
        # For now, we'll allow address to suggest system but not force it
        # User can use the "🔍 Auto" button if they want auto-detection
        pass
    
    def connect_device(self):
        """Connect to measurement system (supports multiple systems)"""
        try:
            address = self.addr_var.get()
            system_name = self.system_var.get()
            
            # Auto-detect system if not explicitly set or if address changed
            detected = detect_system_from_address(address)
            if detected and detected != system_name:
                # Update system selection if auto-detection differs
                self.system_var.set(detected)
                system_name = detected
                self.log(f"Auto-detected system: {system_name}")
            
            self.log(f"Connecting to {address}...")
            self.log(f"System: {system_name}")
            
            # Connect using system wrapper
            connected_system = self.system_wrapper.connect(
                address=address,
                system_name=system_name,
                terminals=self.terminals_var.get()
                if system_name in ('keithley2450', 'keithley2450_sim') else None,
            )
            
            self.current_system_name = connected_system
            idn = self.system_wrapper.get_idn()
            
            # Legacy compatibility: maintain old tsp/test_scripts if 2450
            if connected_system in ('keithley2450', 'keithley2450_sim'):
                system = self.system_wrapper.current_system
                self.tsp = getattr(system, 'tsp_controller', None)
                self.test_scripts = getattr(system, 'test_scripts', None)
            else:
                self.tsp = None
                self.test_scripts = None
            
            terminals_text = (
                f" ({self.terminals_var.get().upper()})"
                if connected_system in ('keithley2450', 'keithley2450_sim')
                else ""
            )
            self.conn_status_var.set(f"Connected: {system_name.upper()} - {idn}{terminals_text}")
            self.log(f"✓ Connected: {idn}")
            if connected_system in ('keithley2450', 'keithley2450_sim'):
                self.log(f"✓ Terminals: {self.terminals_var.get().upper()}")
            
            # Update test list based on capabilities - this greys out unsupported tests
            self._update_test_list_capabilities()
            
            # Check current test and update button state (this will refresh parameters with correct units)
            self.on_test_selected(None)
            
            self.run_btn.config(state=tk.NORMAL)
            
        except Exception as e:
            self.conn_status_var.set("Connection Failed")
            self.log(f"❌ Connection error: {e}")
            messagebox.showerror("Connection Error", str(e))
    
    def disconnect_device(self):
        """Disconnect from device"""
        # Disconnect using system wrapper
        if self.system_wrapper.is_connected():
            try:
                self.system_wrapper.disconnect()
                self.log("✓ Disconnected")
            except:
                pass
        
        # Legacy cleanup
        if self.tsp:
            try:
                self.tsp.close()
            except:
                pass
            self.tsp = None
            self.test_scripts = None
        
        self.current_system_name = None
        self.conn_status_var.set("Disconnected")
        self.run_btn.config(state=tk.DISABLED)
        
        # Reset test list (enable all tests when disconnected)
        self._update_test_list_capabilities()
    
    def _update_test_list_capabilities(self):
        """Update test list to gray out unsupported tests based on current system"""
        if not hasattr(self, 'test_combo'):
            return  # GUI not fully initialized yet
        
        system_name = self.current_system_name if self.current_system_name else None
        test_values = list(TEST_FUNCTIONS.keys())
        
        # Store current selection
        current_selection = self.test_var.get()
        
        # Update combobox values (this will trigger capability checking)
        self.test_combo['values'] = test_values
        
        # Restore selection if it exists
        if current_selection in test_values:
            self.test_var.set(current_selection)
        elif test_values:
            self.test_var.set(test_values[0])
        
        # Update enabled state and appearance based on capabilities
        # Note: Tkinter combobox doesn't support individual item styling easily,
        # so we'll handle capability checking in on_test_selected instead
    
    def on_test_selected(self, event):
        """Update UI when test is selected"""
        test_name = self.test_var.get()
        if test_name not in TEST_FUNCTIONS:
            return
        
        test_info = TEST_FUNCTIONS[test_name]
        test_function = test_info["function"]
        
        # Check if test is supported by current system
        system_name = self.current_system_name
        is_supported = True
        unsupported_msg = None
        
        if system_name:
            is_supported = is_test_supported(system_name, test_function)
            if not is_supported:
                unsupported_msg = get_test_explanation(system_name, test_function)
        
        # Update description (add warning if unsupported)
        self.desc_text.config(state=tk.NORMAL)
        self.desc_text.delete(1.0, tk.END)
        description = test_info["description"]
        if not is_supported and unsupported_msg:
            description = f"⚠️ NOT SUPPORTED: {unsupported_msg}\n\n{description}"
        self.desc_text.insert(1.0, description)
        if not is_supported:
            # Make text grayed out
            self.desc_text.tag_add("unsupported", "1.0", tk.END)
            self.desc_text.tag_config("unsupported", foreground="gray")
        self.desc_text.config(state=tk.DISABLED)
        
        # Disable/enable run button based on support
        if not is_supported:
            self.run_btn.config(state=tk.DISABLED, bg="gray", cursor="arrow")
            self.log(f"⚠️ Test '{test_name}' not supported by {system_name}")
        elif self.system_wrapper.is_connected():
            self.run_btn.config(state=tk.NORMAL, bg="#28a745", cursor="hand2")
        
        # Update parameters
        self.populate_parameters()
        
        # Update pulse diagram
        self.update_pulse_diagram()
    
    def populate_parameters(self):
        """Populate parameter inputs based on selected test"""
        # Check if test_var exists yet (might not during initial UI creation)
        if not hasattr(self, 'test_var'):
            return
        
        # Clear existing
        for widget in self.params_frame.winfo_children():
            widget.destroy()
        self.param_vars.clear()
        
        test_name = self.test_var.get()
        if test_name not in TEST_FUNCTIONS:
            return
        
        params = TEST_FUNCTIONS[test_name]["params"]
        row = 0
        
        # Add warning disclaimer for Current Range Finder
        if test_name == "Current Range Finder":
            warning_frame = tk.Frame(self.params_frame, bg="red", relief=tk.RAISED, bd=2)
            warning_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
            
            warning_text = (
                "⚠️ WARNING: This test has known issues and needs fixing!\n"
                "• Graph displays incorrect data\n"
                "• Warning: 'range_stats' column length mismatch (e.g., 2 vs 20)\n"
                "• SMU does not set the measurement range correctly\n"
                "• Source limit errors (5076/5077) may occur\n"
                "Do not rely on results from this test until fixed."
            )
            
            warning_label = tk.Label(warning_frame, text=warning_text, 
                                    bg="red", fg="white", font=("TkDefaultFont", 9, "bold"),
                                    justify=tk.LEFT, wraplength=400)
            warning_label.pack(padx=5, pady=5)
            
            row += 1
        
        # Check if current system is 4200A (use µs instead of ms)
        is_4200a = self.current_system_name in ('keithley4200a',)
        # Time parameters that should be in µs for 4200A
        time_params = ['pulse_width', 'delay_between', 'delay_between_pulses', 
                      'delay_between_reads', 'delay_between_cycles', 'post_read_interval',
                      'reset_width', 'delay_between_voltages', 'delay_between_levels']
        
        # Default values for 4200A (in µs) - different from 2450 defaults
        # For 4200A, we want 1 µs for pulse_width and delays, not 1000 µs (1 ms)
        defaults_4200a = {
            'pulse_width': 1.0,  # 1 µs
            'delay_between': 10.0,  # 10 µs
            'delay_between_pulses': 1.0,  # 1 µs
            'delay_between_reads': 10.0,  # 10 µs
            'delay_between_cycles': 10.0,  # 10 µs
            'post_read_interval': 1.0,  # 1 µs
            'reset_width': 1.0,  # 1 µs
            'delay_between_voltages': 1000.0,  # 1000 µs = 1 ms
            'delay_between_levels': 1000.0,  # 1000 µs = 1 ms
        }
        
        for param_name, param_info in params.items():
            # Adjust label and default for 4200A time parameters
            label = param_info["label"]
            default_value = param_info["default"]
            
            if is_4200a and param_name in time_params:
                # Convert label from (ms) to (µs)
                if "(ms)" in label:
                    label = label.replace("(ms)", "(µs)")
                # Use 4200A-specific defaults (in µs) if available, otherwise convert from ms
                if param_name in defaults_4200a:
                    default_value = defaults_4200a[param_name]
                elif isinstance(default_value, (int, float)):
                    # Fallback: convert from ms to µs (multiply by 1000)
                    default_value = default_value * 1000.0
            
            # Label
            tk.Label(self.params_frame, text=label, anchor="w").grid(
                row=row, column=0, sticky="w", padx=5, pady=2)
            
            # Entry
            var = tk.StringVar(value=str(default_value))
            entry = tk.Entry(self.params_frame, textvariable=var, width=20)
            entry.grid(row=row, column=1, sticky="ew", padx=5, pady=2)
            
            # Bind entry to update diagram when changed
            var.trace_add("write", lambda *args: self.update_pulse_diagram())
            
            # Store original label and whether this is a time param for 4200A
            self.param_vars[param_name] = {
                "var": var, 
                "type": param_info["type"],
                "is_time_param": param_name in time_params,
                "original_label": param_info["label"]
            }
            row += 1
        
        self.params_frame.columnconfigure(1, weight=1)
        
        # Update preset dropdown for new test type
        if hasattr(self, 'preset_dropdown'):
            self.update_preset_dropdown()
    
    def get_test_parameters(self):
        """Extract and validate parameters"""
        params = {}
        # Time parameters that need conversion
        time_params = ['pulse_width', 'delay_between', 'delay_between_pulses', 
                      'delay_between_reads', 'delay_between_cycles', 'post_read_interval',
                      'reset_width', 'delay_between_voltages', 'delay_between_levels']
        
        # Check if current system is 4200A (values are in µs, need to convert to seconds)
        is_4200a = self.current_system_name in ('keithley4200a',)
        
        for param_name, param_info in self.param_vars.items():
            var = param_info["var"]
            param_type = param_info["type"]
            is_time_param = param_info.get("is_time_param", False)
            
            try:
                value_str = var.get()
                if param_type == "int":
                    params[param_name] = int(value_str)
                elif param_type == "float":
                    value = float(value_str)
                    # Convert time parameters to seconds
                    if is_time_param:
                        if is_4200a:
                            # 4200A: values are in µs, convert to seconds
                            value = value / 1e6  # µs → s
                        else:
                            # 2450: values are in ms, convert to seconds
                            value = value / 1000.0  # ms → s
                    params[param_name] = value
                elif param_type == "list":
                    # Parse comma-separated list
                    params[param_name] = [float(x.strip()) for x in value_str.split(",")]
                else:
                    params[param_name] = value_str
            except Exception as e:
                raise ValueError(f"Invalid value for {param_name}: {e}")
        
        return params
    
    def run_test(self):
        """Start test in background thread"""
        if not self.system_wrapper.is_connected():
            messagebox.showerror("Error", "Not connected to device")
            return
        
        if self.test_running:
            messagebox.showwarning("Warning", "Test already running")
            return
        
        # Check if test is supported
        test_name = self.test_var.get()
        test_info = TEST_FUNCTIONS[test_name]
        test_function = test_info["function"]
        
        if self.current_system_name and not is_test_supported(self.current_system_name, test_function):
            explanation = get_test_explanation(self.current_system_name, test_function)
            messagebox.showwarning(
                "Test Not Supported",
                f"Test '{test_name}' is not supported by {self.current_system_name}.\n\n{explanation}"
            )
            return
        
        # Get parameters
        try:
            params = self.get_test_parameters()
        except Exception as e:
            messagebox.showerror("Parameter Error", str(e))
            return
        
        # UI state
        self.test_running = True
        self.run_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.save_btn.config(state=tk.DISABLED)
        self.log(f"▶ Starting: {test_name}")
        
        # Run in thread
        self.test_thread = threading.Thread(target=self._run_test_thread, 
                                             args=(test_info, params), daemon=True)
        self.test_thread.start()
    
    def _run_test_thread(self, test_info, params):
        """Execute test in background using system wrapper"""
        try:
            # Get function name
            func_name = test_info["function"]
            
            # Execute using system wrapper (routes to appropriate system)
            self.log(f"Executing {func_name} on {self.current_system_name}...")
            start_time = time.time()
            
            results = self.system_wrapper.run_test(test_function=func_name, params=params)
            
            elapsed = time.time() - start_time
            self.log(f"✓ Test complete in {elapsed:.2f}s")
            self.log(f"  {len(results['timestamps'])} measurements")
            
            # Store results
            self.last_results = results
            self.last_results['test_name'] = self.test_var.get()
            self.last_results['params'] = params
            self.last_results['plot_type'] = test_info['plot_type']
            
            # Show popup for range finder results (with small delay to ensure GUI is ready)
            if func_name == 'current_range_finder':
                def show_popup():
                    try:
                        self._show_range_finder_popup(results)
                    except Exception as e:
                        self.log(f"⚠️ Could not show range finder popup: {e}")
                        import traceback
                        traceback.print_exc()
                self.after(100, show_popup)  # Small delay to ensure GUI thread is ready
            
            # Plot first, then finish (ensure plot is rendered before saving)
            def plot_and_finish():
                try:
                    self.plot_results()
                    # Small delay to ensure plot is fully rendered
                    self.after(100, self._test_finished)
                except Exception as e:
                    self.log(f"❌ Plot error: {e}")
                    self._test_finished()
            
            self.after(0, plot_and_finish)
            
        except Exception as e:
            self.log(f"❌ Test error: {e}")
            import traceback
            traceback.print_exc()
            self.after(0, self._test_finished)
    
    def stop_test(self):
        """Stop running test"""
        # TSP tests run entirely on instrument, so can't easily stop
        self.log("⚠ Test runs on instrument - wait for completion")
    
    def _test_finished(self):
        """Clean up after test and auto-save (if enabled)"""
        self.test_running = False
        self.run_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.save_btn.config(state=tk.NORMAL if self.last_results else tk.DISABLED)
        
        # Auto-save data after successful test (if enabled)
        if self.last_results and self.auto_save_var.get():
            try:
                self.log("💾 Auto-saving data...")
                success = self.save_data(show_dialog=False)
                if success:
                    self.log("✓ Data automatically saved")
                else:
                    self.log("⚠ Auto-save failed - use Manual Save button")
            except Exception as e:
                self.log(f"❌ Auto-save error: {e}")
                import traceback
                traceback.print_exc()
        elif self.last_results and not self.auto_save_var.get():
            self.log("ℹ Auto-save disabled - use Manual Save to save data")
        else:
            self.log("⚠ No data to save")
    
    def plot_results(self):
        """Plot test results"""
        if not self.last_results:
            return
        
        self.ax.clear()
        
        plot_type = self.last_results.get('plot_type', 'time_series')
        
        try:
            if plot_type == 'time_series':
                self._plot_time_series()
            elif plot_type == 'range_finder':
                self._plot_range_finder()
            elif plot_type == 'width_vs_resistance':
                self._plot_width_sweep()
            elif plot_type == 'pot_dep_cycle':
                self._plot_pot_dep_cycle()
            elif plot_type == 'endurance':
                self._plot_endurance()
            elif plot_type == 'relaxation_reads':
                self._plot_relaxation_reads()
            elif plot_type == 'relaxation_all':
                self._plot_relaxation_all()
            elif plot_type == 'relaxation':
                self._plot_relaxation()
            elif plot_type == 'voltage_sweep':
                self._plot_voltage_sweep()
            elif plot_type == 'ispp':
                self._plot_ispp()
            elif plot_type == 'threshold':
                self._plot_threshold()
            elif plot_type == 'multilevel':
                self._plot_multilevel()
            elif plot_type == 'pulse_train':
                self._plot_pulse_train()
            else:
                self._plot_time_series()  # Default
            
            self.canvas.draw()
        except Exception as e:
            self.log(f"Plot error: {e}")
    
    def _plot_time_series(self):
        """Plot resistance vs time"""
        test_name = self.last_results['test_name']
        params = self.last_results.get('params', {})
        
        self.ax.plot(self.last_results['timestamps'], 
                     self.last_results['resistances'], 'o-', markersize=3)
        
        # Add red dotted line for potentiation/depression tests with post-reads
        if test_name in ["Potentiation Only", "Depression Only"]:
            num_post_reads = params.get('num_post_reads', 0)
            if num_post_reads > 0:
                num_pulses = params.get('num_pulses', 30)
                # Pattern: initial read (idx 0) + num_pulses pulse+read pairs (idx 1 to num_pulses)
                # Post-reads start at idx num_pulses + 1
                # Find the timestamp where pulses end (right after the last pulse read)
                pulse_end_idx = num_pulses  # Index of last pulse read (idx 0 is initial, 1-N are pulse reads)
                if pulse_end_idx < len(self.last_results['timestamps']):
                    pulse_end_time = self.last_results['timestamps'][pulse_end_idx]
                    self.ax.axvline(x=pulse_end_time, color='red', linestyle='--', 
                                   linewidth=2, alpha=0.7, label='Pulses End → Post-reads Start')
                    self.ax.legend()
        
        self.ax.set_xlabel('Time (s)')
        self.ax.set_ylabel('Resistance (Ω)')
        self.ax.set_title(self.last_results['test_name'])
        self.ax.grid(True, alpha=0.3)
        self.ax.set_yscale('log')
    
    def _plot_range_finder(self):
        """Plot resistance vs current range"""
        range_values = self.last_results.get('range_values', [])
        resistances = self.last_results['resistances']
        range_stats = self.last_results.get('range_stats', [])
        recommended_range = self.last_results.get('recommended_range', None)
        
        if not range_values or len(range_values) != len(resistances):
            # Fallback to time series if no range data
            self._plot_time_series()
            return
        
        # Group data by range
        unique_ranges = []
        for r in range_values:
            if r not in unique_ranges:
                unique_ranges.append(r)
        
        # Sort ranges for proper x-axis ordering
        unique_ranges = sorted(unique_ranges, reverse=True)  # Largest to smallest
        
        # Create color map
        colors = plt.cm.viridis(np.linspace(0, 1, len(unique_ranges)))
        
        # Plot each range group
        for idx, range_val in enumerate(unique_ranges):
            # Find all measurements for this range
            range_indices = [i for i, r in enumerate(range_values) if r == range_val]
            range_resistances = [resistances[i] for i in range_indices]
            
            # Use range index for x-axis position
            x_pos = len(unique_ranges) - idx  # Reverse order for display
            x_positions = [x_pos] * len(range_resistances)
            
            # Plot with some jitter for visibility
            x_jittered = [x + np.random.uniform(-0.1, 0.1) for x in x_positions]
            
            label = f"{range_val*1e6:.1f} µA"
            if range_val == recommended_range:
                label += " (★ Recommended)"
            
            self.ax.scatter(x_jittered, range_resistances, 
                          color=colors[idx], alpha=0.6, s=30,
                          label=label)
        
        # Set x-axis with range labels
        self.ax.set_xticks(range(1, len(unique_ranges) + 1))
        self.ax.set_xticklabels([f"{r*1e6:.1f} µA" for r in unique_ranges], 
                                rotation=45, ha='right')
        self.ax.set_xlabel('Current Measurement Range (µA)', fontsize=11)
        self.ax.set_ylabel('Resistance (Ω)', fontsize=11)
        self.ax.set_title(f"{self.last_results['test_name']}\nResistance vs Measurement Range", 
                         fontsize=12, fontweight='bold')
        self.ax.set_yscale('log')
        self.ax.grid(True, alpha=0.3)
        self.ax.legend(loc='best', fontsize=9)
        
        # Highlight recommended range
        if recommended_range:
            rec_idx = unique_ranges.index(recommended_range)
            rec_x = len(unique_ranges) - rec_idx
            self.ax.axvline(x=rec_x, color='red', linestyle='--', 
                           alpha=0.5, linewidth=2, label='Recommended')
    
    def _plot_width_sweep(self):
        """Plot resistance vs pulse number for each width"""
        widths = self.last_results.get('pulse_widths', [])
        resistances = self.last_results['resistances']
        
        if not widths or len(widths) != len(resistances):
            # Fallback to basic plot if data structure is unexpected
            self.ax.plot(resistances, 'o-', markersize=4)
            self.ax.set_xlabel('Measurement Number')
            self.ax.set_ylabel('Resistance (Ω)')
            self.ax.set_title(self.last_results['test_name'])
            self.ax.set_yscale('log')
            self.ax.grid(True, alpha=0.3)
            return
        
        # Group data by width
        unique_widths = []
        for w in widths:
            if w not in unique_widths:
                unique_widths.append(w)
        
        colors = plt.cm.viridis(np.linspace(0, 1, len(unique_widths)))
        
        for idx, width in enumerate(unique_widths):
            # Find all measurements for this width
            width_indices = [i for i, w in enumerate(widths) if w == width]
            width_resistances = [resistances[i] for i in width_indices]
            pulse_numbers = list(range(1, len(width_resistances) + 1))
            
            # Plot this width
            self.ax.plot(pulse_numbers, width_resistances, 
                        'o-', color=colors[idx], 
                        label=f'{width*1e6:.1f} µs',
                        markersize=6, linewidth=2, alpha=0.8)
        
        self.ax.set_xlabel('Pulse Number', fontsize=11)
        self.ax.set_ylabel('Resistance (Ω)', fontsize=11)
        self.ax.set_title(f'{self.last_results["test_name"]}\nResistance Evolution per Width', 
                         fontsize=12, fontweight='bold')
        self.ax.set_yscale('log')
        self.ax.legend(title='Pulse Width', loc='best', fontsize=9)
        self.ax.grid(True, alpha=0.3, linestyle='--')
        
        # Add subtle background for initial read if visible
        if len(unique_widths) > 0:
            self.ax.axvline(x=0.5, color='gray', linestyle=':', alpha=0.3, label='Initial Read')
    
    def _plot_pot_dep_cycle(self):
        """Plot potentiation-depression cycle showing all cycles separately"""
        phases = self.last_results.get('phase', [])
        timestamps = self.last_results.get('timestamps', [])
        resistances = self.last_results.get('resistances', [])
        params = self.last_results.get('params', {})
        num_cycles = params.get('num_cycles', 1)
        steps = params.get('steps', 20)
        
        if not phases or not timestamps or not resistances:
            self.ax.text(0.5, 0.5, "No data to plot", ha='center', va='center')
            return
        
        # Calculate steps per cycle (potentiation + depression)
        steps_per_cycle = steps * 2
        
        # Plot each cycle separately with distinct colors
        colors = plt.cm.tab10(np.linspace(0, 1, max(num_cycles, 1)))
        
        # Skip initial read (idx 0)
        for cycle in range(num_cycles):
            cycle_start_idx = 1 + (cycle * steps_per_cycle)
            cycle_end_idx = 1 + ((cycle + 1) * steps_per_cycle)
            
            if cycle_start_idx >= len(phases):
                break
            
            # Get indices for this cycle
            cycle_indices = list(range(cycle_start_idx, min(cycle_end_idx, len(phases))))
            
            # Separate potentiation and depression for this cycle
            pot_indices_cycle = [i for i in cycle_indices if i < len(phases) and phases[i] == 'potentiation']
            dep_indices_cycle = [i for i in cycle_indices if i < len(phases) and phases[i] == 'depression']
            
            # Plot potentiation for this cycle
            if pot_indices_cycle:
                pot_times = [timestamps[i] for i in pot_indices_cycle]
                pot_res = [resistances[i] for i in pot_indices_cycle]
                label = f'Cycle {cycle+1}: Potentiation' if num_cycles > 1 else 'Potentiation (SET)'
                self.ax.plot(pot_times, pot_res, 'o-', color=colors[cycle % len(colors)], 
                           markersize=4, linewidth=2, alpha=0.8, label=label)
            
            # Plot depression for this cycle
            if dep_indices_cycle:
                dep_times = [timestamps[i] for i in dep_indices_cycle]
                dep_res = [resistances[i] for i in dep_indices_cycle]
                label = f'Cycle {cycle+1}: Depression' if num_cycles > 1 else 'Depression (RESET)'
                # Use darker shade of same color for depression
                dep_color = plt.cm.Reds(0.6 + (cycle % len(colors)) * 0.3)
                self.ax.plot(dep_times, dep_res, 's-', color=dep_color, 
                           markersize=4, linewidth=2, alpha=0.8, label=label)
        
        # Plot initial read if present
        if len(phases) > 0 and phases[0] == 'initial':
            self.ax.plot(timestamps[0], resistances[0], 'o', color='blue', 
                        markersize=8, label='Initial Read', zorder=5)
        
        self.ax.set_xlabel('Time (s)', fontsize=11)
        self.ax.set_ylabel('Resistance (Ω)', fontsize=11)
        title = f'{self.last_results["test_name"]}'
        if num_cycles > 1:
            title += f' - {num_cycles} Cycles'
        self.ax.set_title(title, fontsize=12, fontweight='bold')
        self.ax.legend(loc='best', fontsize=9, ncol=2 if num_cycles > 1 else 1)
        self.ax.grid(True, alpha=0.3)
        self.ax.set_yscale('log')
    
    def _plot_endurance(self):
        """Plot endurance test (SET/RESET cycles)"""
        operations = self.last_results.get('operation', [])
        cycle_numbers = self.last_results.get('cycle_number', list(range(len(self.last_results['resistances']))))
        
        set_idx = [i for i, op in enumerate(operations) if op == 'SET']
        reset_idx = [i for i, op in enumerate(operations) if op == 'RESET']
        
        if set_idx:
            self.ax.plot([cycle_numbers[i] for i in set_idx],
                        [self.last_results['resistances'][i] for i in set_idx],
                        'o', label='SET (LRS)', color='green', markersize=3)
        if reset_idx:
            self.ax.plot([cycle_numbers[i] for i in reset_idx],
                        [self.last_results['resistances'][i] for i in reset_idx],
                        'o', label='RESET (HRS)', color='red', markersize=3)
        
        self.ax.set_xlabel('Cycle Number')
        self.ax.set_ylabel('Resistance (Ω)')
        self.ax.set_title(f'{self.last_results["test_name"]} - Endurance')
        self.ax.legend()
        self.ax.grid(True, alpha=0.3)
        self.ax.set_yscale('log')
    
    def _plot_relaxation(self):
        """Plot relaxation measurements (old plot type for backward compatibility)"""
        self.ax.plot(self.last_results['timestamps'], 
                     self.last_results['resistances'], 'o-', markersize=4)
        self.ax.set_xlabel('Time (s)')
        self.ax.set_ylabel('Resistance (Ω)')
        self.ax.set_title(f'{self.last_results["test_name"]} - Relaxation')
        self.ax.grid(True, alpha=0.3)
        self.ax.set_yscale('log')
        
        # Mark initial read and pulse/read transitions if possible
        self.ax.axvline(x=self.last_results['timestamps'][0], color='blue', 
                        linestyle='--', alpha=0.3, label='Initial Read')
    
    def _plot_relaxation_reads(self):
        """Plot read number vs resistance for relaxation_after_multi_pulse"""
        resistances = self.last_results['resistances']
        params = self.last_results.get('params', {})
        num_pulses = params.get('num_pulses', 10)
        
        # First measurement is initial read (pulse 0), then num_reads after pulses
        pulse_numbers = list(range(len(resistances)))
        
        self.ax.plot(pulse_numbers, resistances, 'o-', markersize=6, linewidth=2)
        self.ax.set_xlabel('Read Number (0 = before pulses)')
        self.ax.set_ylabel('Resistance (Ω)')
        self.ax.set_title(f'{self.last_results["test_name"]}\nAfter {num_pulses} pulses')
        self.ax.grid(True, alpha=0.3)
        self.ax.set_yscale('log')
        
        # Mark the transition from initial read to post-pulse reads
        self.ax.axvline(x=0.5, color='red', linestyle='--', alpha=0.5, label=f'{num_pulses} pulses here')
        self.ax.legend()
    
    def _plot_relaxation_all(self):
        """Plot measurement number vs resistance for relaxation_after_multi_pulse_with_pulse_measurement"""
        resistances = self.last_results['resistances']
        voltages = self.last_results['voltages']
        params = self.last_results.get('params', {})
        num_pulses = params.get('num_pulses', 10)
        read_voltage = params.get('read_voltage', 0.2)
        pulse_voltage = params.get('pulse_voltage', 1.5)
        
        # Separate into reads vs pulse measurements
        # Pattern: measurement 0 = initial read, 1 to num_pulses = pulse peaks, rest = reads
        measurement_nums = []
        read_resistances = []
        pulse_resistances = []
        
        for i, (r, v) in enumerate(zip(resistances, voltages)):
            measurement_nums.append(i)
            
            # Use position-based logic (more robust than voltage comparison)
            if i == 0:
                # Initial read
                read_resistances.append(r)
                pulse_resistances.append(None)
            elif i <= num_pulses:
                # Pulse peak measurement
                read_resistances.append(None)
                pulse_resistances.append(r)
            else:
                # Post-pulse read
                read_resistances.append(r)
                pulse_resistances.append(None)
        
        # Separate data into separate lists for plotting (filter out None values)
        read_meas_nums = [i for i, r in zip(measurement_nums, read_resistances) if r is not None]
        read_vals = [r for r in read_resistances if r is not None]
        
        pulse_meas_nums = [i for i, p in zip(measurement_nums, pulse_resistances) if p is not None]
        pulse_vals = [p for p in pulse_resistances if p is not None]
        
        # Debug output
        print(f"Plotting: {len(read_vals)} reads at indices {read_meas_nums[:5]}...")
        print(f"Plotting: {len(pulse_vals)} pulse peaks at indices {pulse_meas_nums[:5]}...")
        
        # Plot both with different styles (no lines, just markers for clarity)
        if read_vals:
            self.ax.plot(read_meas_nums, read_vals, 'o', markersize=6, 
                        label=f'Reads ({len(read_vals)})', color='blue')
        if pulse_vals:
            self.ax.plot(pulse_meas_nums, pulse_vals, 's', markersize=7, 
                        label=f'Pulse Peaks ({len(pulse_vals)})', color='red', alpha=0.8)
        
        self.ax.set_xlabel('Measurement Number (0 = initial read)')
        self.ax.set_ylabel('Resistance (Ω)')
        self.ax.set_title(f'{self.last_results["test_name"]}\n{num_pulses} pulses @ {pulse_voltage}V with peak measurements')
        self.ax.grid(True, alpha=0.3)
        self.ax.set_yscale('log')
        self.ax.legend()
        
        # Mark the transition points
        self.ax.axvline(x=0.5, color='green', linestyle='--', alpha=0.3, label='Start')
        self.ax.axvline(x=num_pulses + 0.5, color='orange', linestyle='--', alpha=0.3, label='Post-pulse reads')
    
    def _plot_voltage_sweep(self):
        """Plot resistance vs pulse number for each voltage"""
        pulse_voltages = self.last_results.get('pulse_voltages', [])
        resistances = self.last_results['resistances']
        
        if not pulse_voltages or len(pulse_voltages) != len(resistances):
            # Fallback to basic plot
            self._plot_time_series()
            return
        
        # Group data by pulse voltage
        unique_voltages = []
        for v in pulse_voltages:
            if v not in unique_voltages:
                unique_voltages.append(v)
        
        colors = plt.cm.plasma(np.linspace(0, 1, len(unique_voltages)))
        params = self.last_results.get('params', {})
        num_pulses_per_voltage = params.get('num_pulses_per_voltage', 5)
        
        for idx, voltage in enumerate(unique_voltages):
            # Find all measurements for this voltage
            voltage_indices = [i for i, v in enumerate(pulse_voltages) if v == voltage]
            voltage_resistances = [resistances[i] for i in voltage_indices]
            pulse_numbers = list(range(1, len(voltage_resistances) + 1))
            
            # Plot this voltage
            self.ax.plot(pulse_numbers, voltage_resistances, 
                        'o-', color=colors[idx], 
                        label=f'{voltage:.2f}V',
                        markersize=6, linewidth=2, alpha=0.8)
        
        self.ax.set_xlabel('Pulse Number', fontsize=11)
        self.ax.set_ylabel('Resistance (Ω)', fontsize=11)
        self.ax.set_title(f'{self.last_results["test_name"]}\nResistance Evolution per Voltage', 
                         fontsize=12, fontweight='bold')
        self.ax.set_yscale('log')
        self.ax.legend(title='Pulse Voltage', loc='best', fontsize=9)
        self.ax.grid(True, alpha=0.3, linestyle='--')
    
    def _plot_ispp(self):
        """Plot ISPP: Resistance vs Pulse Number with voltage annotation"""
        pulse_voltages = self.last_results.get('pulse_voltages', [])
        resistances = self.last_results['resistances']
        timestamps = self.last_results.get('timestamps', [])
        
        if not pulse_voltages or len(pulse_voltages) != len(resistances):
            # Fallback to basic plot
            self._plot_time_series()
            return
        
        # Plot resistance vs pulse number
        pulse_numbers = list(range(len(resistances)))
        
        # Color by voltage (gradual increase)
        if len(pulse_voltages) > 1:
            scatter = self.ax.scatter(pulse_numbers, resistances, 
                                     c=pulse_voltages, cmap='viridis',
                                     s=50, alpha=0.7, edgecolors='black', linewidth=0.5)
            cbar = plt.colorbar(scatter, ax=self.ax)
            cbar.set_label('Pulse Voltage (V)', fontsize=10)
        else:
            self.ax.plot(pulse_numbers, resistances, 'o-', markersize=6, linewidth=2)
        
        self.ax.set_xlabel('Pulse Number', fontsize=11)
        self.ax.set_ylabel('Resistance (Ω)', fontsize=11)
        self.ax.set_title(f'{self.last_results["test_name"]}\nIncremental Step Pulse Programming', 
                         fontsize=12, fontweight='bold')
        self.ax.set_yscale('log')
        self.ax.grid(True, alpha=0.3, linestyle='--')
    
    def _plot_threshold(self):
        """Plot switching threshold: Resistance vs Pulse Voltage"""
        pulse_voltages = self.last_results.get('pulse_voltages', [])
        resistances = self.last_results['resistances']
        direction = self.last_results.get('direction', 'set')
        
        if not pulse_voltages or len(pulse_voltages) != len(resistances):
            # Fallback to basic plot
            self._plot_time_series()
            return
        
        # Group by voltage and average resistance for each voltage
        voltage_groups = {}
        for v, r in zip(pulse_voltages, resistances):
            if v != 0.0:  # Skip initial read (voltage = 0)
                if v not in voltage_groups:
                    voltage_groups[v] = []
                voltage_groups[v].append(r)
        
        # Calculate mean resistance for each voltage
        unique_voltages = sorted(voltage_groups.keys())
        mean_resistances = [np.mean(voltage_groups[v]) for v in unique_voltages]
        std_resistances = [np.std(voltage_groups[v]) for v in unique_voltages]
        
        # Plot with error bars
        self.ax.errorbar(unique_voltages, mean_resistances, yerr=std_resistances,
                        fmt='o-', markersize=8, linewidth=2, capsize=5,
                        label=f'{direction.upper()} Threshold Test')
        
        self.ax.set_xlabel('Pulse Voltage (V)', fontsize=11)
        self.ax.set_ylabel('Resistance (Ω)', fontsize=11)
        self.ax.set_title(f'{self.last_results["test_name"]}\nSwitching Threshold ({direction.upper()})', 
                         fontsize=12, fontweight='bold')
        self.ax.set_yscale('log')
        self.ax.grid(True, alpha=0.3, linestyle='--')
        self.ax.legend()
    
    def _plot_multilevel(self):
        """Plot multilevel programming: Resistance vs Pulse Number for each level"""
        target_levels = self.last_results.get('target_levels', [])
        resistances = self.last_results['resistances']
        
        if not target_levels or len(target_levels) != len(resistances):
            # Fallback to basic plot
            self._plot_time_series()
            return
        
        # Group data by target level
        unique_levels = []
        for l in target_levels:
            if l not in unique_levels:
                unique_levels.append(l)
        
        colors = plt.cm.tab10(np.linspace(0, 1, len(unique_levels)))
        params = self.last_results.get('params', {})
        num_pulses_per_level = params.get('num_pulses_per_level', 5)
        
        for idx, level in enumerate(unique_levels):
            # Find all measurements for this level
            level_indices = [i for i, l in enumerate(target_levels) if l == level]
            level_resistances = [resistances[i] for i in level_indices]
            pulse_numbers = list(range(1, len(level_resistances) + 1))
            
            # Plot this level
            self.ax.plot(pulse_numbers, level_resistances, 
                        'o-', color=colors[idx], 
                        label=f'Level {level}',
                        markersize=6, linewidth=2, alpha=0.8)
        
        self.ax.set_xlabel('Pulse Number', fontsize=11)
        self.ax.set_ylabel('Resistance (Ω)', fontsize=11)
        self.ax.set_title(f'{self.last_results["test_name"]}\nMultilevel Programming', 
                         fontsize=12, fontweight='bold')
        self.ax.set_yscale('log')
        self.ax.legend(title='Target Level', loc='best', fontsize=9)
        self.ax.grid(True, alpha=0.3, linestyle='--')
    
    def _plot_pulse_train(self):
        """Plot pulse train with varying amplitudes: Resistance vs Pulse Number"""
        pulse_voltages = self.last_results.get('pulse_voltages', [])
        resistances = self.last_results['resistances']
        timestamps = self.last_results.get('timestamps', [])
        
        if not pulse_voltages or len(pulse_voltages) != len(resistances):
            # Fallback to basic plot
            self._plot_time_series()
            return
        
        # Plot resistance vs pulse number
        pulse_numbers = list(range(len(resistances)))
        
        # Color by voltage (showing the pattern)
        if len(pulse_voltages) > 1:
            # Use a diverging colormap for positive/negative voltages
            scatter = self.ax.scatter(pulse_numbers, resistances, 
                                     c=pulse_voltages, cmap='RdBu_r',
                                     s=50, alpha=0.7, edgecolors='black', linewidth=0.5)
            cbar = plt.colorbar(scatter, ax=self.ax)
            cbar.set_label('Pulse Voltage (V)', fontsize=10)
        else:
            self.ax.plot(pulse_numbers, resistances, 'o-', markersize=6, linewidth=2)
        
        self.ax.set_xlabel('Pulse Number', fontsize=11)
        self.ax.set_ylabel('Resistance (Ω)', fontsize=11)
        self.ax.set_title(f'{self.last_results["test_name"]}\nPulse Train with Varying Amplitudes', 
                         fontsize=12, fontweight='bold')
        self.ax.set_yscale('log')
        self.ax.grid(True, alpha=0.3, linestyle='--')
    
    def save_data(self, show_dialog=False, extra_notes=None):
        """Save test results automatically using standardized format
        
        Args:
            show_dialog: If True, show success dialog (for manual saves)
            extra_notes: Additional notes to include in metadata
        """
        if not self.last_results:
            if show_dialog:
                messagebox.showwarning("No Data", "No test results to save")
            return False
        
        try:
            formatter = TSPDataFormatter()
            
            # Check if using provider custom location - if so, skip sample name requirement
            use_provider_custom = False
            if self.provider is not None:
                use_custom = getattr(self.provider, 'use_custom_save_var', None)
                if use_custom and use_custom.get():
                    custom_path = getattr(self.provider, 'custom_save_location', None)
                    if custom_path:
                        use_provider_custom = True
            
            # Check if simple save mode is enabled
            if self.use_simple_save_var.get() and self.simple_save_path:
                # Simple save: everything in one folder
                save_dir = Path(self.simple_save_path)
                save_dir.mkdir(parents=True, exist_ok=True)
                
                # Get next index for sequential numbering (simple mode)
                # Find largest number prefix from existing files
                max_num = find_largest_number_in_folder(str(save_dir))
                index = 0 if max_num is None else max_num + 1
            else:
                # Structured save: use FileNamer with custom base if configured
                # Check if provider (Measurement GUI) has custom save location enabled
                # (use_provider_custom already set above)
                custom_path = None
                device_section = None
                
                if use_provider_custom and self.provider is not None:
                    custom_path = getattr(self.provider, 'custom_save_location', None)
                    if custom_path:
                        device_section = getattr(self.provider, 'device_section_and_number', None)
                
                if use_provider_custom and custom_path and device_section:
                    # Use Measurement GUI's custom save location
                    # Extract section (letter) and device number from device_section (e.g., "A1" -> "A" and "1")
                    section = device_section[0] if len(device_section) > 0 else "A"
                    device_num = device_section[1:] if len(device_section) > 1 else "1"
                    
                    # Build path: custom_location / section / device_number / Pulse_measurements
                    save_dir = Path(custom_path) / section / device_num / "Pulse_measurements"
                    save_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Get next index for sequential numbering
                    max_num = find_largest_number_in_folder(str(save_dir))
                    index = 0 if max_num is None else max_num + 1
                    
                    # Update device_label for display
                    self.device_label = device_section
                else:
                    # Use default structure (FileNamer)
                    # Only require sample_name if not using provider custom location
                    if not use_provider_custom:
                        # If sample name is still unknown, try to get from provider or use default
                        if self.sample_name == "UnknownSample" and self.provider is not None:
                            sn = getattr(self.provider, 'sample_name_var', None)
                            if sn is not None:
                                provider_sample_name = sn.get().strip()
                                if provider_sample_name:
                                    self.sample_name = provider_sample_name
                    
                    # When using custom base, sample_name is not used in path, but we still need to pass something
                    namer = FileNamer(base_dir=self.custom_base_path)
                    save_dir = namer.get_device_folder(
                        sample_name=self.sample_name if not use_provider_custom else "UnknownSample",
                        device=self.device_label if self.device_label != "UnknownDevice" else "A1",
                        subfolder="Pulse_measurements"
                    )
                    save_dir.mkdir(parents=True, exist_ok=True)
                    index = namer.get_next_index(save_dir)
            
            # Create test details string with key parameters (max 3)
            test_name = self.last_results['test_name']
            params = self.last_results.get('params', {})
            test_details = self._generate_test_details(params)
            
            # Get filename suffix if provided
            filename_suffix = self.filename_suffix_var.get().strip()
            # Sanitize suffix: remove invalid filename characters
            if filename_suffix:
                import re
                filename_suffix = re.sub(r'[<>:"/\\|?*]', '_', filename_suffix)
                filename_suffix = filename_suffix.replace(' ', '_')
                suffix_str = f"-{filename_suffix}" if filename_suffix else ""
            else:
                suffix_str = ""
            
            # Create filename
            if self.use_simple_save_var.get() and self.simple_save_path:
                # Simple mode: number at start, then test name + details + suffix + timestamp
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                test_clean = test_name.replace(" ", "_").replace("-", "_")
                details_str = f"-{test_details}" if test_details else ""
                filename = f"{index}-{test_clean}{details_str}{suffix_str}-{timestamp}.txt"
            else:
                # Structured mode: use FileNamer, then add suffix before extension
                namer = FileNamer(base_dir=self.custom_base_path)
                filename = namer.create_tsp_filename(test_name, index, extension="txt", test_details=test_details)
                # Add suffix before file extension
                if suffix_str:
                    filename = filename.rsplit('.', 1)[0] + suffix_str + '.' + filename.rsplit('.', 1)[1]
            
            filepath = save_dir / filename
            
            # Get notes from text widget
            notes = self.notes_text.get(1.0, tk.END).strip()
            if notes == "Add notes about this test here...":
                notes = ""
            if extra_notes:
                notes = f"{notes}\n{extra_notes}" if notes else extra_notes
            
            # Extract sample name for metadata
            # Priority: 1) From custom path (if using custom location), 2) From provider's sample_name_var, 3) Current sample_name
            sample_name_for_metadata = self.sample_name
            
            # Check if using provider custom location - extract sample name from path
            if self.provider is not None:
                use_custom = getattr(self.provider, 'use_custom_save_var', None)
                if use_custom and use_custom.get():
                    custom_path = getattr(self.provider, 'custom_save_location', None)
                    if custom_path:
                        # Extract sample name from the last part of the custom path
                        sample_from_path = Path(custom_path).name
                        if sample_from_path:
                            sample_name_for_metadata = sample_from_path
            
            # If not using custom location, try to get from provider's sample_name_var
            if sample_name_for_metadata == "UnknownSample" and self.provider is not None:
                sn = getattr(self.provider, 'sample_name_var', None)
                if sn is not None:
                    provider_sample_name = sn.get().strip()
                    if provider_sample_name:
                        sample_name_for_metadata = provider_sample_name
            
            # Prepare metadata
            metadata = {
                'sample': sample_name_for_metadata,
                'device': self.device_label,
                'instrument': 'Keithley 2450',  # Default, will be updated below
                'address': self.addr_var.get() if hasattr(self, 'addr_var') else 'N/A',
                'test_index': index,
                'notes': notes,
            }
            
            # Add hardware limits from system wrapper if available
            if self.system_wrapper.is_connected():
                try:
                    limits = self.system_wrapper.get_hardware_limits()
                    if limits:
                        # Format limits for metadata
                        metadata['hardware_limits'] = {
                            'min_pulse_width': f"{limits.get('min_pulse_width', 0)*1e3:.3f} ms",
                            'max_voltage': f"{limits.get('max_voltage', 0)} V",
                            'max_current_limit': f"{limits.get('max_current_limit', 0)} A",
                        }
                        metadata['instrument'] = f"{self.current_system_name.upper()}" if self.current_system_name else "Unknown"
                except:
                    pass
            # Legacy fallback for compatibility
            elif hasattr(self, 'test_scripts') and self.test_scripts:
                try:
                    metadata['hardware_limits'] = {
                        'min_pulse_width': f"{self.test_scripts.MIN_PULSE_WIDTH*1e3:.3f} ms",
                        'max_voltage': f"{self.test_scripts.MAX_VOLTAGE} V",
                        'max_current_limit': f"{self.test_scripts.MAX_CURRENT_LIMIT} A",
                    }
                    metadata['instrument'] = 'Keithley 2450'
                except:
                    pass
            
            # Format data using standardized formatter
            data, header, fmt, full_metadata = formatter.format_tsp_data(
                data_dict=self.last_results,
                test_name=test_name,
                params=self.last_results.get('params', {}),
                metadata=metadata
            )
            
            # Ensure plot is updated before saving
            if hasattr(self, 'fig') and self.fig is not None:
                self.canvas.draw_idle()
                self.master.update_idletasks()
            
            # Save using standardized function (saves .txt, .png, and log)
            success = save_tsp_measurement(
                filepath=filepath,
                data=data,
                header=header,
                fmt=fmt,
                metadata=full_metadata,
                save_plot=self.fig if hasattr(self, 'fig') else None
            )
            
            if success:
                # Display full filepath for easy finding
                self.log(f"✓ Saved to: {filepath}")
                if show_dialog:
                    messagebox.showinfo("Success", 
                        f"Test #{index} saved successfully!\n\n"
                        f"Location:\n{filepath.parent}\n\n"
                        f"Files:\n"
                        f"  • {filepath.name}\n"
                        f"  • {filepath.with_suffix('.png').name}")
                return True
            else:
                raise Exception("Save function returned False")
                
        except Exception as e:
            self.log(f"❌ Save error: {e}")
            if show_dialog:
                messagebox.showerror("Save Error", str(e))
            import traceback
            traceback.print_exc()
            return False
    
    def manual_save_with_notes(self):
        """Manually save data with current notes"""
        self.save_data(show_dialog=True)
    
    def open_data_analysis(self):
        """Open the TSP Data Analysis Tool"""
        try:
            # Get the path to the analysis tool
            # TSP_Testing_GUI.py is in the root, so parent is the root directory
            analysis_script = Path(__file__).parent / "Helpers" / "Data_Analysis_Pulse_2450" / "main.py"
            
            if not analysis_script.exists():
                messagebox.showerror("Analysis Tool Not Found", 
                    f"Could not find analysis tool at:\n{analysis_script}\n\n"
                    "Please ensure the Data_Analysis_Pulse_2450 folder exists.")
                return
            
            # Launch the analysis tool in a separate process
            # Use pythonw on Windows to avoid showing console window
            if sys.platform == "win32":
                # Try pythonw first, fallback to python if pythonw doesn't exist
                python_exe = sys.executable.replace("python.exe", "pythonw.exe")
                if not Path(python_exe).exists():
                    python_exe = sys.executable
                # CREATE_NO_WINDOW flag to hide console window on Windows
                try:
                    subprocess.Popen([python_exe, str(analysis_script)],
                                   creationflags=subprocess.CREATE_NO_WINDOW)
                except AttributeError:
                    # Fallback if CREATE_NO_WINDOW is not available
                    subprocess.Popen([python_exe, str(analysis_script)])
            else:
                subprocess.Popen([sys.executable, str(analysis_script)])
            
            self.log("📊 Opening TSP Data Analysis Tool...")
            
        except Exception as e:
            self.log(f"❌ Error opening analysis tool: {e}")
            messagebox.showerror("Error", f"Could not open analysis tool:\n{e}")
    
    def _show_range_finder_popup(self, results: dict):
        """Show popup window with range finder results and recommendations"""
        try:
            popup = tk.Toplevel(self.master)
            popup.title("Current Range Finder Results")
            popup.geometry("700x600")
            popup.transient(self.master)
            popup.grab_set()
        except Exception as e:
            self.log(f"⚠️ Error creating popup window: {e}")
            import traceback
            traceback.print_exc()
            return
        
        # Main frame with padding
        main_frame = ttk.Frame(popup, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Current Range Finder Results", 
                                font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 10))
        
        # Get range stats
        range_stats = results.get('range_stats', [])
        recommended_range = results.get('recommended_range', None)
        
        if not range_stats:
            ttk.Label(main_frame, text="No range statistics available", 
                     foreground="red").pack()
            ttk.Button(main_frame, text="Close", command=popup.destroy).pack(pady=10)
            return
        
        # Recommendation section
        rec_frame = ttk.LabelFrame(main_frame, text="Recommendation", padding="10")
        rec_frame.pack(fill=tk.X, pady=(0, 10))
        
        if recommended_range:
            rec_text = f"✓ RECOMMENDED RANGE: {recommended_range*1e6:.1f} µA"
            # Find the stats for recommended range
            rec_stats = next((s for s in range_stats if s['range_limit'] == recommended_range), None)
            if rec_stats:
                rec_text += f"\n\n• Mean Current: {rec_stats['mean_current']*1e6:.3f} µA"
                rec_text += f"\n• Stability (CV): {rec_stats['cv_percent']:.2f}%"
                rec_text += f"\n• Mean Resistance: {rec_stats['mean_resistance']:.2e} Ω"
                rec_text += f"\n• No negative readings"
                if rec_stats['has_negative']:
                    rec_text += " ⚠️ (Actually has negatives - check data)"
        else:
            rec_text = "⚠ No ideal range found - check your device/connections"
        
        rec_label = ttk.Label(rec_frame, text=rec_text, font=("Arial", 10))
        rec_label.pack(anchor=tk.W)
        
        # Results table
        table_frame = ttk.LabelFrame(main_frame, text="All Ranges Tested", padding="10")
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Create treeview for table
        columns = ("Range", "Mean Current", "Std Dev", "CV %", "Min", "Max", "Resistance", "Status")
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=len(range_stats))
        
        # Configure columns
        tree.heading("Range", text="Range Limit (µA)")
        tree.heading("Mean Current", text="Mean (µA)")
        tree.heading("Std Dev", text="Std Dev (µA)")
        tree.heading("CV %", text="CV %")
        tree.heading("Min", text="Min (µA)")
        tree.heading("Max", text="Max (µA)")
        tree.heading("Resistance", text="Resistance (Ω)")
        tree.heading("Status", text="Status")
        
        tree.column("Range", width=100, anchor=tk.CENTER)
        tree.column("Mean Current", width=100, anchor=tk.CENTER)
        tree.column("Std Dev", width=90, anchor=tk.CENTER)
        tree.column("CV %", width=70, anchor=tk.CENTER)
        tree.column("Min", width=90, anchor=tk.CENTER)
        tree.column("Max", width=90, anchor=tk.CENTER)
        tree.column("Resistance", width=120, anchor=tk.CENTER)
        tree.column("Status", width=80, anchor=tk.CENTER)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        # Populate table
        try:
            for stats in range_stats:
                status = "✓ OK" if not stats['has_negative'] else "✗ Neg"
                if recommended_range and stats['range_limit'] == recommended_range:
                    status = "★ REC"
                
                # Format resistance
                if stats['mean_resistance'] >= 1e12:
                    res_str = ">1e12"
                elif stats['mean_resistance'] >= 1e6:
                    res_str = f"{stats['mean_resistance']:.2e}"
                else:
                    res_str = f"{stats['mean_resistance']:.2f}"
                
                values = (
                    f"{stats['range_limit']*1e6:.1f}",
                    f"{stats['mean_current']*1e6:.3f}",
                    f"{stats['std_current']*1e6:.3f}",
                    f"{stats['cv_percent']:.2f}",
                    f"{stats['min_current']*1e6:.3f}",
                    f"{stats['max_current']*1e6:.3f}",
                    res_str,
                    status
                )
                
                item = tree.insert("", tk.END, values=values)
                
                # Highlight recommended range
                if recommended_range and stats['range_limit'] == recommended_range:
                    tree.set(item, "Status", "★ RECOMMENDED")
        except Exception as e:
            self.log(f"⚠️ Error populating range finder table: {e}")
            import traceback
            traceback.print_exc()
            ttk.Label(table_frame, text=f"Error displaying table: {e}", 
                     foreground="red").pack()
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Close button
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        ttk.Button(button_frame, text="Close", command=popup.destroy).pack()
    
    def _generate_test_details(self, params: dict) -> str:
        """
        Generate test details string for filename (max 3 most important parameters).
        
        Args:
            params: Test parameters dictionary
        
        Returns:
            str: Formatted test details (e.g., "1.5V_100us_10cyc")
        """
        details = []
        
        # Voltage (if present)
        if 'pulse_voltage' in params:
            v = params['pulse_voltage']
            details.append(f"{abs(v):.1f}V")
        
        # Pulse width (if present)
        if 'pulse_width' in params:
            pw = params['pulse_width']
            if pw >= 1e-3:
                details.append(f"{pw*1e3:.0f}ms")
            else:
                details.append(f"{pw*1e6:.0f}us")
        
        # Number of pulses/cycles/reads (pick one that exists)
        for key in ['num_pulses', 'num_cycles', 'num_reads']:
            if key in params:
                val = params[key]
                short_name = key.split('_')[1][:3]  # "pul", "cyc", "rea"
                details.append(f"{val}{short_name}")
                break  # Only include one count parameter
        
        return "_".join(details[:3])  # Max 3 parameters
    
    def update_pulse_diagram(self):
        """Update the pulse pattern diagram based on selected test and parameters"""
        if not hasattr(self, 'diagram_ax'):
            return
        
        # Check if test_var exists (might not exist during initial UI creation)
        if not hasattr(self, 'test_var'):
            return
        
        self.diagram_ax.clear()
        test_name = self.test_var.get()
        
        if test_name not in TEST_FUNCTIONS:
            self.diagram_ax.text(0.5, 0.5, "Select a test", ha='center', va='center')
            self.diagram_canvas.draw()
            return
        
        try:
            # Get current parameters (with fallbacks)
            # Check if current system is 4200A (values are in µs)
            is_4200a = self.current_system_name in ('keithley4200a',)
            time_params = ['pulse_width', 'delay_between', 'delay_between_pulses', 
                          'delay_between_reads', 'delay_between_cycles', 'post_read_interval',
                          'reset_width', 'delay_between_voltages', 'delay_between_levels']
            
            params = {}
            for key, info in self.param_vars.items():
                try:
                    val = info["var"].get()
                    if info["type"] == "float":
                        value = float(val)
                        # Convert µs to seconds for diagram (diagram expects seconds)
                        if is_4200a and info.get("is_time_param", False):
                            value = value / 1e6  # µs → s
                        params[key] = value
                    elif info["type"] == "int":
                        params[key] = int(val)
                    elif info["type"] == "list":
                        params[key] = [float(x.strip()) for x in val.split(",")]
                    else:
                        params[key] = val
                except:
                    params[key] = 1.0  # Fallback value
            
            # Draw pattern based on test type
            if "Pulse-Read-Repeat" in test_name:
                self._draw_pulse_read_repeat(params)
            elif "Multi-Pulse-Then-Read" in test_name:
                self._draw_multi_pulse_then_read(params)
            elif "Width Sweep" in test_name:
                self._draw_width_sweep(params, "Full" in test_name)
            elif "Potentiation-Depression" in test_name:
                self._draw_pot_dep_cycle(params)
            elif "Potentiation Only" in test_name:
                self._draw_potentiation_only(params)
            elif "Depression Only" in test_name:
                self._draw_depression_only(params)
            elif "Endurance" in test_name:
                self._draw_endurance(params)
            elif "Pulse-Multi-Read" in test_name:
                self._draw_pulse_multi_read(params)
            elif "Multi-Read Only" in test_name:
                self._draw_multi_read_only(params)
            elif "Relaxation" in test_name:
                self._draw_relaxation(params, "Pulse Measurement" in test_name)
            elif "Voltage Amplitude Sweep" in test_name:
                self._draw_voltage_sweep(params)
            elif "ISPP" in test_name:
                self._draw_ispp(params)
            elif "Switching Threshold" in test_name:
                self._draw_threshold(params)
            elif "Multilevel Programming" in test_name:
                self._draw_multilevel(params)
            elif "Pulse Train" in test_name:
                self._draw_pulse_train(params)
            else:
                self._draw_generic_pattern()
            
            # Add limit warnings
            self._add_limit_warnings(params)
            
            self.diagram_canvas.draw()
            
        except Exception as e:
            self.diagram_ax.text(0.5, 0.5, f"Diagram error:\n{str(e)}", ha='center', va='center', fontsize=8)
            self.diagram_canvas.draw()
    
    def _draw_pulse_read_repeat(self, params):
        """Draw: Initial Read → (Pulse → Read → Delay) × N"""
        t = 0
        times, voltages = [], []
        read_times = []  # Track read measurement times
        p_v = params.get('pulse_voltage', 1.5)
        r_v = params.get('read_voltage', 0.2)
        p_w = params.get('pulse_width', 1e-3)
        cycles = min(params.get('num_cycles', 100), 5)  # Show max 5 cycles
        
        # Initial read before any pulses
        read_t = t + p_w*0.15
        read_times.append(read_t)
        times.extend([t, t, t+p_w*0.3, t+p_w*0.3])
        voltages.extend([0, r_v, r_v, 0])
        t += p_w*0.3 + 0.0001
        
        for i in range(cycles):
            # Pulse
            times.extend([t, t, t+p_w, t+p_w])
            voltages.extend([0, p_v, p_v, 0])
            t += p_w + 0.0001
            # Read
            read_t = t + p_w*0.25  # Mark center of read pulse
            read_times.append(read_t)
            times.extend([t, t, t+p_w*0.5, t+p_w*0.5])
            voltages.extend([0, r_v, r_v, 0])
            t += p_w*0.5 + params.get('delay_between', 10e-3)
        
        self.diagram_ax.plot(np.array(times)*1e3, voltages, 'b-', linewidth=2)
        self.diagram_ax.fill_between(np.array(times)*1e3, 0, voltages, alpha=0.3)
        # Mark read points
        for rt in read_times:
            self.diagram_ax.plot(rt*1e3, r_v, 'rx', markersize=10, markeredgewidth=2)
        self.diagram_ax.set_xlabel('Time (ms)')
        self.diagram_ax.set_ylabel('Voltage (V)')
        self.diagram_ax.set_title(f'Pattern: Initial Read → (Pulse→Read)×{cycles}', fontsize=9)
        self.diagram_ax.grid(True, alpha=0.3)
        self.diagram_ax.set_ylim(-0.2, max(p_v, r_v)*1.2)
    
    def _draw_multi_pulse_then_read(self, params):
        """Draw: Initial Read → (Pulse×N → Read×M) × Cycles"""
        t = 0
        times, voltages = [], []
        read_times = []
        p_v = params.get('pulse_voltage', 1.5)
        r_v = params.get('read_voltage', 0.2)
        p_w = params.get('pulse_width', 1e-3)
        n_pulses = min(params.get('num_pulses_per_read', 10), 5)
        n_reads = min(params.get('num_reads', 1), 5)
        cycles = min(params.get('num_cycles', 20), 2)
        
        # Initial read before any pulses
        read_t = t + p_w*0.15
        read_times.append(read_t)
        times.extend([t, t, t+p_w*0.3, t+p_w*0.3])
        voltages.extend([0, r_v, r_v, 0])
        t += p_w*0.3 + 0.0001
        
        for cycle in range(cycles):
            # Multiple pulses
            for i in range(n_pulses):
                times.extend([t, t, t+p_w, t+p_w])
                voltages.extend([0, p_v, p_v, 0])
                t += p_w + params.get('delay_between_pulses', 1e-3)
            # Multiple reads
            for i in range(n_reads):
                read_t = t + p_w*0.25
                read_times.append(read_t)
                times.extend([t, t, t+p_w*0.5, t+p_w*0.5])
                voltages.extend([0, r_v, r_v, 0])
                t += p_w*0.5 + (params.get('delay_between_reads', 10e-3) if i < n_reads-1 else params.get('delay_between_cycles', 10e-3))
        
        self.diagram_ax.plot(np.array(times)*1e3, voltages, 'purple', linewidth=2)
        self.diagram_ax.fill_between(np.array(times)*1e3, 0, voltages, alpha=0.3, color='purple')
        for rt in read_times:
            self.diagram_ax.plot(rt*1e3, r_v, 'rx', markersize=10, markeredgewidth=2)
        self.diagram_ax.set_xlabel('Time (ms)')
        self.diagram_ax.set_ylabel('Voltage (V)')
        self.diagram_ax.set_title(f'Pattern: Initial Read → {n_pulses}×Pulse→{n_reads}×Read ×{cycles}', fontsize=9)
        self.diagram_ax.grid(True, alpha=0.3)
        self.diagram_ax.set_ylim(-0.2, max(p_v, r_v)*1.2)
    
    def _draw_width_sweep(self, params, with_pulse_measurement=False):
        """Draw width sweep pattern"""
        t = 0
        times, voltages = [], []
        read_times = []
        pulse_read_times = []  # Read at pulse peak
        p_v = params.get('pulse_voltage', 1.5)
        r_v = params.get('read_voltage', 0.2)
        widths = params.get('pulse_widths', [1e-3, 5e-3, 10e-3])[:3]
        
        for width in widths:
            # Read before
            read_t = t + width*0.15
            read_times.append(read_t)
            times.extend([t, t, t+width*0.3, t+width*0.3])
            voltages.extend([0, r_v, r_v, 0])
            t += width*0.3 + 0.0001
            # Pulse at this width
            pulse_start_t = t
            times.extend([t, t, t+width, t+width])
            voltages.extend([0, p_v, p_v, 0])
            if with_pulse_measurement:
                pulse_read_times.append(pulse_start_t + width*0.5)  # Peak read
            t += width + 0.0001
            # Read after
            read_t = t + width*0.15
            read_times.append(read_t)
            times.extend([t, t, t+width*0.3, t+width*0.3])
            voltages.extend([0, r_v, r_v, 0])
            t += width*0.3 + width*2
        
        self.diagram_ax.plot(np.array(times)*1e3, voltages, 'orange', linewidth=2)
        self.diagram_ax.fill_between(np.array(times)*1e3, 0, voltages, alpha=0.3, color='orange')
        # Regular reads
        for rt in read_times:
            self.diagram_ax.plot(rt*1e3, r_v, 'rx', markersize=10, markeredgewidth=2)
        # Pulse-peak reads (if Full version)
        for pt in pulse_read_times:
            self.diagram_ax.plot(pt*1e3, p_v, 'rx', markersize=10, markeredgewidth=2)
        self.diagram_ax.set_xlabel('Time (ms)')
        self.diagram_ax.set_ylabel('Voltage (V)')
        title = f'Width Sweep (Full): {len(widths)} widths' if with_pulse_measurement else f'Width Sweep: {len(widths)} widths'
        self.diagram_ax.set_title(title, fontsize=10)
        self.diagram_ax.grid(True, alpha=0.3)
        self.diagram_ax.set_ylim(-0.2, max(p_v, r_v)*1.2)
    
    def _draw_pot_dep_cycle(self, params):
        """Draw potentiation-depression cycle with initial read, repeated for multiple cycles"""
        t = 0
        times, voltages, colors = [], [], []
        read_times = []
        set_v = params.get('set_voltage', 2.0)
        reset_v = params.get('reset_voltage', -2.0)
        r_v = params.get('read_voltage', 0.2)
        p_w = params.get('pulse_width', 1e-3)
        steps = min(params.get('steps', 20), 5)
        num_cycles = min(params.get('num_cycles', 1), 3)  # Show max 3 cycles in diagram
        
        # Initial read before any pulses
        read_t = t + p_w*0.15
        read_times.append(read_t)
        times.extend([t, t, t+p_w*0.3, t+p_w*0.3])
        voltages.extend([0, r_v, r_v, 0])
        t += p_w*0.3 + 0.0001
        
        # Loop through cycles
        for cycle in range(num_cycles):
            # Potentiation (SET)
            for i in range(steps):
                times.extend([t, t, t+p_w, t+p_w])
                voltages.extend([0, set_v, set_v, 0])
                t += p_w + 0.0001
                read_t = t + p_w*0.15
                read_times.append(read_t)
                times.extend([t, t, t+p_w*0.3, t+p_w*0.3])
                voltages.extend([0, r_v, r_v, 0])
                t += p_w*0.3 + params.get('delay_between', 10e-3)
            
            # Depression (RESET)
            for i in range(steps):
                times.extend([t, t, t+p_w, t+p_w])
                voltages.extend([0, reset_v, reset_v, 0])
                t += p_w + 0.0001
                read_t = t + p_w*0.15
                read_times.append(read_t)
                times.extend([t, t, t+p_w*0.3, t+p_w*0.3])
                voltages.extend([0, r_v, r_v, 0])
                t += p_w*0.3 + params.get('delay_between', 10e-3)
        
        self.diagram_ax.plot(np.array(times)*1e3, voltages, 'red', linewidth=2)
        self.diagram_ax.fill_between(np.array(times)*1e3, 0, voltages, alpha=0.3, 
                                     where=np.array(voltages)>=0, color='green', label='SET')
        self.diagram_ax.fill_between(np.array(times)*1e3, 0, voltages, alpha=0.3,
                                     where=np.array(voltages)<0, color='red', label='RESET')
        for rt in read_times:
            self.diagram_ax.plot(rt*1e3, r_v, 'rx', markersize=10, markeredgewidth=2)
        self.diagram_ax.set_xlabel('Time (ms)')
        self.diagram_ax.set_ylabel('Voltage (V)')
        title = f'Pot-Dep Cycle: Initial Read → {num_cycles}×({steps} SET → {steps} RESET)'
        self.diagram_ax.set_title(title, fontsize=9)
        self.diagram_ax.legend(fontsize=8)
        self.diagram_ax.grid(True, alpha=0.3)
    
    def _draw_potentiation_only(self, params):
        """Draw potentiation only with initial read"""
        t = 0
        times, voltages = [], []
        read_times = []
        set_v = params.get('set_voltage', 2.0)
        r_v = params.get('read_voltage', 0.2)
        p_w = params.get('pulse_width', 1e-3)
        n = min(params.get('num_pulses', 30), 5)
        
        # Initial read before any pulses
        read_t = t + p_w*0.15
        read_times.append(read_t)
        times.extend([t, t, t+p_w*0.3, t+p_w*0.3])
        voltages.extend([0, r_v, r_v, 0])
        t += p_w*0.3 + 0.0001
        
        for i in range(n):
            times.extend([t, t, t+p_w, t+p_w])
            voltages.extend([0, set_v, set_v, 0])
            t += p_w + 0.0001
            read_t = t + p_w*0.15
            read_times.append(read_t)
            times.extend([t, t, t+p_w*0.3, t+p_w*0.3])
            voltages.extend([0, r_v, r_v, 0])
            t += p_w*0.3 + params.get('delay_between', 10e-3)
        
        # Post-pulse reads (if enabled)
        num_post_reads = params.get('num_post_reads', 0)
        post_interval = params.get('post_read_interval', 1e-3)
        if num_post_reads > 0:
            t += 0.0001  # Small delay after last pulse
            post_n = min(num_post_reads, 3)  # Show max 3 for diagram
            for i in range(post_n):
                t += post_interval
                read_t = t + 0.001*0.5  # Read at middle of 1ms pulse
                read_times.append(read_t)
                times.extend([t, t, t+0.001, t+0.001])
                voltages.extend([0, r_v, r_v, 0])
                t += 0.001
        
        self.diagram_ax.plot(np.array(times)*1e3, voltages, 'green', linewidth=2)
        self.diagram_ax.fill_between(np.array(times)*1e3, 0, voltages, alpha=0.3, color='green')
        for rt in read_times:
            self.diagram_ax.plot(rt*1e3, r_v, 'rx', markersize=10, markeredgewidth=2)
        title = f'Potentiation: Initial Read → {n} SET pulses'
        if num_post_reads > 0:
            title += f' → {num_post_reads} post-reads'
        self.diagram_ax.set_xlabel('Time (ms)')
        self.diagram_ax.set_ylabel('Voltage (V)')
        self.diagram_ax.set_title(title, fontsize=9)
        self.diagram_ax.grid(True, alpha=0.3)
        self.diagram_ax.set_ylim(-0.2, set_v*1.2)
    
    def _draw_depression_only(self, params):
        """Draw depression only with initial read"""
        t = 0
        times, voltages = [], []
        read_times = []
        reset_v = params.get('reset_voltage', -2.0)
        r_v = params.get('read_voltage', 0.2)
        p_w = params.get('pulse_width', 1e-3)
        n = min(params.get('num_pulses', 30), 5)
        
        # Initial read before any pulses
        read_t = t + p_w*0.15
        read_times.append(read_t)
        times.extend([t, t, t+p_w*0.3, t+p_w*0.3])
        voltages.extend([0, r_v, r_v, 0])
        t += p_w*0.3 + 0.0001
        
        for i in range(n):
            times.extend([t, t, t+p_w, t+p_w])
            voltages.extend([0, reset_v, reset_v, 0])
            t += p_w + 0.0001
            read_t = t + p_w*0.15
            read_times.append(read_t)
            times.extend([t, t, t+p_w*0.3, t+p_w*0.3])
            voltages.extend([0, r_v, r_v, 0])
            t += p_w*0.3 + params.get('delay_between', 10e-3)
        
        # Post-pulse reads (if enabled)
        num_post_reads = params.get('num_post_reads', 0)
        post_interval = params.get('post_read_interval', 1e-3)
        if num_post_reads > 0:
            t += 0.0001  # Small delay after last pulse
            post_n = min(num_post_reads, 3)  # Show max 3 for diagram
            for i in range(post_n):
                t += post_interval
                read_t = t + 0.001*0.5  # Read at middle of 1ms pulse
                read_times.append(read_t)
                times.extend([t, t, t+0.001, t+0.001])
                voltages.extend([0, r_v, r_v, 0])
                t += 0.001
        
        self.diagram_ax.plot(np.array(times)*1e3, voltages, 'red', linewidth=2)
        self.diagram_ax.fill_between(np.array(times)*1e3, 0, voltages, alpha=0.3, color='red')
        for rt in read_times:
            self.diagram_ax.plot(rt*1e3, r_v, 'rx', markersize=10, markeredgewidth=2)
        title = f'Depression: Initial Read → {n} RESET pulses'
        if num_post_reads > 0:
            title += f' → {num_post_reads} post-reads'
        self.diagram_ax.set_xlabel('Time (ms)')
        self.diagram_ax.set_ylabel('Voltage (V)')
        self.diagram_ax.set_title(title, fontsize=9)
        self.diagram_ax.grid(True, alpha=0.3)
        self.diagram_ax.set_ylim(reset_v*1.2, 0.5)
    
    def _draw_endurance(self, params):
        """Draw endurance test with initial read"""
        t = 0
        times, voltages = [], []
        read_times = []
        set_v = params.get('set_voltage', 2.0)
        reset_v = params.get('reset_voltage', -2.0)
        r_v = params.get('read_voltage', 0.2)
        p_w = params.get('pulse_width', 1e-3)
        cycles = min(params.get('num_cycles', 100), 3)
        
        # Initial read before any cycles
        read_t = t + p_w*0.15
        read_times.append(read_t)
        times.extend([t, t, t+p_w*0.3, t+p_w*0.3])
        voltages.extend([0, r_v, r_v, 0])
        t += p_w*0.3 + 0.0001
        
        for i in range(cycles):
            # SET + read
            times.extend([t, t, t+p_w, t+p_w])
            voltages.extend([0, set_v, set_v, 0])
            t += p_w + 0.0001
            read_t = t + p_w*0.15
            read_times.append(read_t)
            times.extend([t, t, t+p_w*0.3, t+p_w*0.3])
            voltages.extend([0, r_v, r_v, 0])
            t += p_w*0.3 + params.get('delay_between', 10e-3)
            # RESET + read
            times.extend([t, t, t+p_w, t+p_w])
            voltages.extend([0, reset_v, reset_v, 0])
            t += p_w + 0.0001
            read_t = t + p_w*0.15
            read_times.append(read_t)
            times.extend([t, t, t+p_w*0.3, t+p_w*0.3])
            voltages.extend([0, r_v, r_v, 0])
            t += p_w*0.3 + params.get('delay_between', 10e-3)
        
        self.diagram_ax.plot(np.array(times)*1e3, voltages, 'brown', linewidth=2)
        self.diagram_ax.fill_between(np.array(times)*1e3, 0, voltages, alpha=0.3, color='brown')
        for rt in read_times:
            self.diagram_ax.plot(rt*1e3, r_v, 'rx', markersize=10, markeredgewidth=2)
        self.diagram_ax.set_xlabel('Time (ms)')
        self.diagram_ax.set_ylabel('Voltage (V)')
        self.diagram_ax.set_title(f'Endurance: Initial Read → {cycles} SET/RESET cycles', fontsize=9)
        self.diagram_ax.grid(True, alpha=0.3)
    
    def _draw_pulse_multi_read(self, params):
        """Draw initial read → pulse followed by multiple reads"""
        t = 0
        times, voltages = [], []
        read_times = []
        p_v = params.get('pulse_voltage', 1.5)
        r_v = params.get('read_voltage', 0.2)
        p_w = params.get('pulse_width', 1e-3)
        n_pulses = params.get('num_pulses', 1)
        n_reads = min(params.get('num_reads', 50), 8)
        
        # Initial read before any pulses
        read_t = t + p_w*0.15
        read_times.append(read_t)
        times.extend([t, t, t+p_w*0.3, t+p_w*0.3])
        voltages.extend([0, r_v, r_v, 0])
        t += p_w*0.3 + 0.0001
        
        # N pulses
        for i in range(min(n_pulses, 3)):
            times.extend([t, t, t+p_w, t+p_w])
            voltages.extend([0, p_v, p_v, 0])
            t += p_w + params.get('delay_between_pulses', 1e-3)
        
        # Many reads
        for i in range(n_reads):
            read_t = t + p_w*0.15
            read_times.append(read_t)
            times.extend([t, t, t+p_w*0.3, t+p_w*0.3])
            voltages.extend([0, r_v, r_v, 0])
            t += p_w*0.3 + params.get('delay_between_reads', 100e-3)
        
        self.diagram_ax.plot(np.array(times)*1e3, voltages, 'cyan', linewidth=2)
        self.diagram_ax.fill_between(np.array(times)*1e3, 0, voltages, alpha=0.3, color='cyan')
        for rt in read_times:
            self.diagram_ax.plot(rt*1e3, r_v, 'rx', markersize=10, markeredgewidth=2)
        self.diagram_ax.set_xlabel('Time (ms)')
        self.diagram_ax.set_ylabel('Voltage (V)')
        self.diagram_ax.set_title(f'Initial Read → {n_pulses}×Pulse → {n_reads} Reads', fontsize=9)
        self.diagram_ax.grid(True, alpha=0.3)
        self.diagram_ax.set_ylim(-0.2, p_v*1.2)
    
    def _draw_multi_read_only(self, params):
        """Draw multiple reads only"""
        t = 0
        times, voltages = [], []
        read_times = []
        r_v = params.get('read_voltage', 0.2)
        n_reads = min(params.get('num_reads', 100), 8)
        
        for i in range(n_reads):
            read_t = t + 0.0005
            read_times.append(read_t)
            times.extend([t, t, t+0.001, t+0.001])
            voltages.extend([0, r_v, r_v, 0])
            t += 0.001 + params.get('delay_between', 100e-3)
        
        self.diagram_ax.plot(np.array(times)*1e3, voltages, 'gray', linewidth=2)
        self.diagram_ax.fill_between(np.array(times)*1e3, 0, voltages, alpha=0.3, color='gray')
        for rt in read_times:
            self.diagram_ax.plot(rt*1e3, r_v, 'rx', markersize=10, markeredgewidth=2)
        self.diagram_ax.set_xlabel('Time (ms)')
        self.diagram_ax.set_ylabel('Voltage (V)')
        self.diagram_ax.set_title(f'Only Reads: {n_reads} measurements', fontsize=10)
        self.diagram_ax.grid(True, alpha=0.3)
        self.diagram_ax.set_ylim(-0.1, r_v*1.3)
    
    def _draw_relaxation(self, params, with_pulse_measurement=False):
        """Draw relaxation pattern"""
        t = 0
        times, voltages = [], []
        read_times = []
        pulse_read_times = []  # Read at pulse peak
        p_v = params.get('pulse_voltage', 1.5)
        r_v = params.get('read_voltage', 0.2)
        p_w = params.get('pulse_width', 1e-3)
        n_pulses = min(params.get('num_pulses', 10), 5)
        n_reads = min(params.get('num_reads', 10), 5)
        
        # Initial read
        read_t = t + p_w*0.15
        read_times.append(read_t)
        times.extend([t, t, t+p_w*0.3, t+p_w*0.3])
        voltages.extend([0, r_v, r_v, 0])
        t += p_w*0.3 + 0.0001
        
        # Multiple pulses
        for i in range(n_pulses):
            pulse_start_t = t
            times.extend([t, t, t+p_w, t+p_w])
            voltages.extend([0, p_v, p_v, 0])
            if with_pulse_measurement:
                pulse_read_times.append(pulse_start_t + p_w*0.5)  # Peak read
            t += p_w + params.get('delay_between_pulses', 1e-3)
        
        # Multiple reads (relaxation)
        for i in range(n_reads):
            read_t = t + p_w*0.15
            read_times.append(read_t)
            times.extend([t, t, t+p_w*0.3, t+p_w*0.3])
            voltages.extend([0, r_v, r_v, 0])
            t += p_w*0.3 + params.get('delay_between_reads', 100e-6)
        
        self.diagram_ax.plot(np.array(times)*1e3, voltages, 'magenta', linewidth=2)
        self.diagram_ax.fill_between(np.array(times)*1e3, 0, voltages, alpha=0.3, color='magenta')
        # Regular reads
        for rt in read_times:
            self.diagram_ax.plot(rt*1e3, r_v, 'rx', markersize=10, markeredgewidth=2)
        # Pulse-peak reads (if with pulse measurement)
        for pt in pulse_read_times:
            self.diagram_ax.plot(pt*1e3, p_v, 'rx', markersize=10, markeredgewidth=2)
        self.diagram_ax.set_xlabel('Time (ms)')
        self.diagram_ax.set_ylabel('Voltage (V)')
        title = f'Relaxation (Pulse Meas): 1Read→{n_pulses}Pulse→{n_reads}Read' if with_pulse_measurement else f'Relaxation: 1Read→{n_pulses}Pulse→{n_reads}Read'
        self.diagram_ax.set_title(title, fontsize=9)
        self.diagram_ax.grid(True, alpha=0.3)
        self.diagram_ax.set_ylim(-0.2, p_v*1.2)
    
    def _draw_voltage_sweep(self, params):
        """Draw: For each voltage: Initial Read → (Pulse → Read) × N → Reset"""
        t = 0
        times, voltages = [], []
        read_times = []
        start_v = params.get('pulse_voltage_start', 0.5)
        stop_v = params.get('pulse_voltage_stop', 2.5)
        step_v = params.get('pulse_voltage_step', 0.1)
        r_v = params.get('read_voltage', 0.2)
        p_w = params.get('pulse_width', 1e-3)
        delay = params.get('delay_between', 10e-3)
        reset_v = params.get('reset_voltage', -1.0)
        reset_w = params.get('reset_width', 1e-3)
        pulses_per_v = min(params.get('num_pulses_per_voltage', 5), 3)  # Show max 3
        
        # Show 2-3 voltage levels for diagram
        num_voltages = min(int((stop_v - start_v) / step_v) + 1, 3)
        pulse_voltages = [start_v + i * step_v for i in range(num_voltages)]
        
        for v_idx, pulse_v in enumerate(pulse_voltages):
            # Initial read before pulses at this voltage
            read_times.append(t)
            t += 0.001
            
            # Pulses at this voltage
            for p in range(pulses_per_v):
                times.append(t)
                voltages.append(pulse_v)
                t += p_w
                times.append(t)
                voltages.append(0)
                t += 0.00001
                read_times.append(t)
                t += 0.001
                if p < pulses_per_v - 1:
                    t += delay
            
            # Reset between voltages (except last)
            if v_idx < len(pulse_voltages) - 1:
                times.append(t)
                voltages.append(reset_v)
                t += reset_w
                times.append(t)
                voltages.append(0)
                t += 0.00001
        
        self.diagram_ax.fill_between(np.array(times)*1e3, 0, voltages, alpha=0.3, color='blue')
        for rt in read_times:
            self.diagram_ax.plot(rt*1e3, r_v, 'rx', markersize=8, markeredgewidth=2)
        self.diagram_ax.set_xlabel('Time (ms)')
        self.diagram_ax.set_ylabel('Voltage (V)')
        self.diagram_ax.set_title(f'Voltage Sweep: {start_v}V to {stop_v}V, {pulses_per_v} pulses/voltage', fontsize=9)
        self.diagram_ax.grid(True, alpha=0.3)
        self.diagram_ax.set_ylim(min(min(voltages), reset_v)*1.2, max(max(voltages), start_v)*1.2)
    
    def _draw_ispp(self, params):
        """Draw: Initial Read → (Pulse with increasing voltage → Read) × N"""
        t = 0
        times, voltages = [], []
        read_times = []
        start_v = params.get('start_voltage', 0.5)
        step_v = params.get('voltage_step', 0.05)
        max_v = params.get('max_voltage', 3.0)
        r_v = params.get('read_voltage', 0.2)
        p_w = params.get('pulse_width', 1e-3)
        delay = params.get('delay_between', 10e-3)
        max_pulses = min(params.get('max_pulses', 100), 10)  # Show max 10
        
        # Initial read
        read_times.append(t)
        t += 0.001
        
        # ISPP pulses with increasing voltage
        current_v = start_v
        for p in range(max_pulses):
            if current_v > max_v:
                break
            times.append(t)
            voltages.append(current_v)
            t += p_w
            times.append(t)
            voltages.append(0)
            t += 0.00001
            read_times.append(t)
            t += 0.001
            current_v += step_v
            if p < max_pulses - 1:
                t += delay
        
        self.diagram_ax.fill_between(np.array(times)*1e3, 0, voltages, alpha=0.3, color='green')
        for rt in read_times:
            self.diagram_ax.plot(rt*1e3, r_v, 'rx', markersize=8, markeredgewidth=2)
        self.diagram_ax.set_xlabel('Time (ms)')
        self.diagram_ax.set_ylabel('Voltage (V)')
        self.diagram_ax.set_title(f'ISPP: {start_v}V → {max_v}V, step {step_v}V', fontsize=9)
        self.diagram_ax.grid(True, alpha=0.3)
        self.diagram_ax.set_ylim(-0.2, max_v*1.2)
    
    def _draw_threshold(self, params):
        """Draw: For each voltage: Initial Read → (Pulse → Read) × N"""
        t = 0
        times, voltages = [], []
        read_times = []
        start_v = params.get('start_voltage', 0.5)
        step_v = params.get('voltage_step', 0.05)
        max_v = params.get('max_voltage', 3.0)
        r_v = params.get('read_voltage', 0.2)
        p_w = params.get('pulse_width', 1e-3)
        delay = params.get('delay_between', 10e-3)
        pulses_per_v = min(params.get('num_pulses_per_voltage', 3), 2)  # Show max 2
        direction = params.get('direction', 'set')
        
        # Show 3 voltage levels for diagram
        num_voltages = min(int((max_v - start_v) / step_v) + 1, 3)
        pulse_voltages = [start_v + i * step_v for i in range(num_voltages)]
        if direction.lower() == 'reset':
            pulse_voltages = [-v for v in pulse_voltages]
        
        for pulse_v in pulse_voltages:
            # Initial read before pulses at this voltage
            read_times.append(t)
            t += 0.001
            
            # Pulses at this voltage
            for p in range(pulses_per_v):
                times.append(t)
                voltages.append(pulse_v)
                t += p_w
                times.append(t)
                voltages.append(0)
                t += 0.00001
                read_times.append(t)
                t += 0.001
                if p < pulses_per_v - 1:
                    t += delay
        
        self.diagram_ax.fill_between(np.array(times)*1e3, 0, voltages, alpha=0.3, color='orange')
        for rt in read_times:
            self.diagram_ax.plot(rt*1e3, r_v, 'rx', markersize=8, markeredgewidth=2)
        self.diagram_ax.set_xlabel('Time (ms)')
        self.diagram_ax.set_ylabel('Voltage (V)')
        self.diagram_ax.set_title(f'Threshold Test ({direction.upper()}): {start_v}V → {max_v}V', fontsize=9)
        self.diagram_ax.grid(True, alpha=0.3)
        min_v = min(min(voltages) if voltages else 0, -max_v)
        max_v_plot = max(max(voltages) if voltages else 0, max_v)
        self.diagram_ax.set_ylim(min_v*1.2, max_v_plot*1.2)
    
    def _draw_multilevel(self, params):
        """Draw: For each level: Reset → Program with pulses → Read"""
        t = 0
        times, voltages = [], []
        read_times = []
        pulse_v = params.get('pulse_voltage', 1.5)
        r_v = params.get('read_voltage', 0.2)
        p_w = params.get('pulse_width', 1e-3)
        delay = params.get('delay_between', 10e-3)
        reset_v = params.get('reset_voltage', -1.0)
        reset_w = params.get('reset_width', 1e-3)
        pulses_per_level = min(params.get('num_pulses_per_level', 5), 3)  # Show max 3
        target_levels = params.get('target_levels', [1, 2, 3])
        if isinstance(target_levels, str):
            target_levels = [float(x.strip()) for x in target_levels.split(",")]
        levels_to_show = min(len(target_levels), 3)  # Show max 3 levels
        
        for level_idx in range(levels_to_show):
            # Reset before programming each level
            times.append(t)
            voltages.append(reset_v)
            t += reset_w
            times.append(t)
            voltages.append(0)
            t += 0.00001
            
            # Initial read after reset
            read_times.append(t)
            t += 0.001
            
            # Program with pulses
            for p in range(pulses_per_level):
                times.append(t)
                voltages.append(pulse_v)
                t += p_w
                times.append(t)
                voltages.append(0)
                t += 0.00001
                read_times.append(t)
                t += 0.001
                if p < pulses_per_level - 1:
                    t += delay
        
        self.diagram_ax.fill_between(np.array(times)*1e3, 0, voltages, alpha=0.3, color='purple')
        for rt in read_times:
            self.diagram_ax.plot(rt*1e3, r_v, 'rx', markersize=8, markeredgewidth=2)
        self.diagram_ax.set_xlabel('Time (ms)')
        self.diagram_ax.set_ylabel('Voltage (V)')
        self.diagram_ax.set_title(f'Multilevel: {levels_to_show} levels, {pulses_per_level} pulses/level', fontsize=9)
        self.diagram_ax.grid(True, alpha=0.3)
        self.diagram_ax.set_ylim(reset_v*1.2, pulse_v*1.2)
    
    def _draw_pulse_train(self, params):
        """Draw: Initial Read → (Pulse1 → Read → Pulse2 → Read → ...) × N"""
        t = 0
        times, voltages = [], []
        read_times = []
        pulse_voltages = params.get('pulse_voltages', [1.0, 1.5, 2.0, -1.0, -1.5, -2.0])
        if isinstance(pulse_voltages, str):
            pulse_voltages = [float(x.strip()) for x in pulse_voltages.split(",")]
        r_v = params.get('read_voltage', 0.2)
        p_w = params.get('pulse_width', 1e-3)
        delay = params.get('delay_between', 10e-3)
        num_repeats = min(params.get('num_repeats', 1), 2)  # Show max 2 repeats
        
        # Initial read
        read_times.append(t)
        t += 0.001
        
        # Pulse train pattern
        for repeat in range(num_repeats):
            for pulse_v in pulse_voltages:
                times.append(t)
                voltages.append(pulse_v)
                t += p_w
                times.append(t)
                voltages.append(0)
                t += 0.00001
                read_times.append(t)
                t += 0.001
                t += delay
        
        self.diagram_ax.fill_between(np.array(times)*1e3, 0, voltages, alpha=0.3, color='cyan')
        for rt in read_times:
            self.diagram_ax.plot(rt*1e3, r_v, 'rx', markersize=8, markeredgewidth=2)
        self.diagram_ax.set_xlabel('Time (ms)')
        self.diagram_ax.set_ylabel('Voltage (V)')
        self.diagram_ax.set_title(f'Pulse Train: {len(pulse_voltages)} voltages × {num_repeats} repeats', fontsize=9)
        self.diagram_ax.grid(True, alpha=0.3)
        min_v = min(min(voltages) if voltages else 0, min(pulse_voltages) if pulse_voltages else 0)
        max_v_plot = max(max(voltages) if voltages else 0, max(pulse_voltages) if pulse_voltages else 0)
        self.diagram_ax.set_ylim(min_v*1.2, max_v_plot*1.2)
    
    def _draw_generic_pattern(self):
        """Generic pattern for unknown tests"""
        self.diagram_ax.text(0.5, 0.5, "Pulse Pattern\n(Generic)", ha='center', va='center', fontsize=12)
        self.diagram_ax.set_xlim(0, 1)
        self.diagram_ax.set_ylim(0, 1)
    
    def _add_limit_warnings(self, params):
        """Add visual warnings for parameters near hardware limits"""
        warnings = []
        
        # Check pulse width (min 1ms = 0.001s)
        if 'pulse_width' in params:
            pw = params['pulse_width']
            if pw < 1e-3:
                warnings.append(f"⚠ Pulse width {pw*1e3:.2f}ms < 1ms min")
        
        # Check delay between pulses (min 1ms)
        if 'delay_between' in params:
            delay = params['delay_between']
            if delay < 1e-3:
                warnings.append(f"⚠ Delay {delay*1e3:.2f}ms < 1ms min")
        
        if 'delay_between_pulses' in params:
            delay = params['delay_between_pulses']
            if delay < 1e-3:
                warnings.append(f"⚠ Pulse delay {delay*1e3:.2f}ms < 1ms min")
        
        # Check pulse widths list
        if 'pulse_widths' in params:
            widths = params['pulse_widths']
            if isinstance(widths, list):
                for w in widths:
                    if w < 1e-3:
                        warnings.append(f"⚠ Width {w*1e3:.2f}ms < 1ms min")
                        break
        
        # Display warnings on diagram
        if warnings:
            warning_text = "\n".join(warnings)
            self.diagram_ax.text(0.02, 0.98, warning_text, 
                               transform=self.diagram_ax.transAxes,
                               fontsize=8, color='red', weight='bold',
                               va='top', ha='left',
                               bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.8))
    
    def log(self, message):
        """Add message to status log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.status_text.see(tk.END)
        self.status_text.update_idletasks()
    
    # ===== PRESET MANAGEMENT =====
    
    def load_presets_from_file(self):
        """Load presets from JSON file"""
        preset_file = Path("Json_Files/tsp_test_presets.json")
        if preset_file.exists():
            try:
                import json
                with open(preset_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading presets: {e}")
                return {}
        return {}
    
    def save_presets_to_file(self):
        """Save presets to JSON file"""
        preset_file = Path("Json_Files/tsp_test_presets.json")
        preset_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            import json
            with open(preset_file, 'w') as f:
                json.dump(self.presets, f, indent=2)
        except Exception as e:
            print(f"Error saving presets: {e}")
            messagebox.showerror("Save Error", f"Could not save presets: {e}")
    
    def update_preset_dropdown(self):
        """Update preset dropdown for current test type"""
        test_name = self.test_var.get()
        presets_for_test = self.presets.get(test_name, {})
        preset_names = list(presets_for_test.keys())
        
        self.preset_dropdown['values'] = preset_names
        if preset_names:
            self.preset_var.set("")  # Clear selection
        else:
            self.preset_var.set("")
    
    def save_preset(self):
        """Save current parameters as a preset"""
        test_name = self.test_var.get()
        
        # Ask for preset name
        preset_name = tk.simpledialog.askstring(
            "Save Preset",
            f"Enter preset name for '{test_name}':",
            parent=self
        )
        
        if not preset_name:
            return
        
        # Get current parameters
        try:
            params = self.get_test_parameters()
        except Exception as e:
            messagebox.showerror("Error", f"Invalid parameters: {e}")
            return
        
        # Store preset
        if test_name not in self.presets:
            self.presets[test_name] = {}
        
        self.presets[test_name][preset_name] = params
        
        # Save to file
        self.save_presets_to_file()
        
        # Update dropdown
        self.update_preset_dropdown()
        self.preset_var.set(preset_name)
        
        self.log(f"✓ Saved preset: '{preset_name}'")
        messagebox.showinfo("Saved", f"Preset '{preset_name}' saved successfully!")
    
    def load_preset(self):
        """Load selected preset"""
        test_name = self.test_var.get()
        preset_name = self.preset_var.get()
        
        if not preset_name:
            return
        
        # Get preset parameters
        presets_for_test = self.presets.get(test_name, {})
        params = presets_for_test.get(preset_name)
        
        if not params:
            messagebox.showwarning("Not Found", f"Preset '{preset_name}' not found")
            return
        
        # Load parameters into GUI
        # Check if current system is 4200A (need to convert to µs)
        is_4200a = self.current_system_name in ('keithley4200a',)
        time_params = ['pulse_width', 'delay_between', 'delay_between_pulses', 
                      'delay_between_reads', 'delay_between_cycles', 'post_read_interval',
                      'reset_width', 'delay_between_voltages', 'delay_between_levels']
        
        for param_name, value in params.items():
            if param_name in self.param_vars:
                var = self.param_vars[param_name]["var"]
                param_type = self.param_vars[param_name]["type"]
                is_time_param = self.param_vars[param_name].get("is_time_param", False)
                
                # Convert back from seconds to display units for time parameters
                if is_time_param and param_type == "float":
                    if is_4200a:
                        value = value * 1e6  # s → µs
                    else:
                        value = value * 1000.0  # s → ms
                
                # Format value appropriately
                if param_type == "int":
                    var.set(str(int(value)))
                elif param_type == "float":
                    var.set(str(value))
                elif param_type == "list":
                    var.set(",".join(str(v) for v in value))
                else:
                    var.set(str(value))
        
        self.log(f"✓ Loaded preset: '{preset_name}'")
        self.update_pulse_diagram()
    
    def delete_preset(self):
        """Delete selected preset"""
        test_name = self.test_var.get()
        preset_name = self.preset_var.get()
        
        if not preset_name:
            messagebox.showwarning("No Selection", "Please select a preset to delete")
            return
        
        # Confirm deletion
        if not messagebox.askyesno("Confirm Delete", 
                                   f"Delete preset '{preset_name}'?"):
            return
        
        # Delete preset
        if test_name in self.presets and preset_name in self.presets[test_name]:
            del self.presets[test_name][preset_name]
            
            # Remove test entry if no presets left
            if not self.presets[test_name]:
                del self.presets[test_name]
            
            # Save to file
            self.save_presets_to_file()
            
            # Update dropdown
            self.update_preset_dropdown()
            
            self.log(f"✓ Deleted preset: '{preset_name}'")
            messagebox.showinfo("Deleted", f"Preset '{preset_name}' deleted")
        else:
            messagebox.showerror("Error", "Preset not found")


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # Hide root window
    app = TSPTestingGUI(root)
    root.mainloop()

