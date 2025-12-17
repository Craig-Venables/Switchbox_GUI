""" 
Advanced Motor Control GUI with Laser Positioning

Description:
- Professional Tkinter GUI for controlling Thorlabs Kinesis XY motors with laser positioning
- Features interactive canvas with real-time position tracking and visual feedback
- Integrated function generator controls for laser power management
- Position presets, scanning capabilities, and keyboard shortcuts
- Camera feed integration (placeholder for future implementation)

Purpose:
This GUI provides comprehensive control over XY stage motors for laser positioning applications.
It combines motor control, laser power management, and visual feedback in a modern interface.

Dependencies:
- Python 3.8+
- Tkinter (standard library)
- pylablib (Thorlabs motor control)
- Equipment modules: Kenisis_motor_control, function_generator_manager, config

Features:
- Interactive canvas with click-to-move functionality
- Real-time position display with visual laser marker
- Jog controls with adjustable step size
- Velocity and acceleration settings
- Position presets/bookmarks
- Go-to-position with coordinate input
- Scanning/raster scan capabilities
- Function generator integration
- Keyboard shortcuts for common operations
- Camera feed placeholder for future integration

Usage:
    from gui.motor_control_gui import MotorControlWindow
    window = MotorControlWindow()
    # window.run() is not needed when called from another GUI

Tests:
- Manual testing required for hardware integration
- Verify motor movements match canvas clicks
- Test position tracking and visual feedback
- Validate preset save/load functionality
"""

from __future__ import annotations

from typing import Optional, Protocol, Tuple, Dict, List
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import json
import os
from pathlib import Path
import re
import sys
import threading
import time

# Camera imports
try:
    import cv2
    import numpy as np
    from PIL import Image, ImageTk
    CAMERA_AVAILABLE = True
except ImportError:
    CAMERA_AVAILABLE = False
    cv2 = None
    np = None
    Image = None
    ImageTk = None

# ---------- Collapsible Frame Widget ----------

class CollapsibleFrame(tk.Frame):
    """A frame that can be collapsed and expanded with a toggle button."""
    
    def __init__(self, parent, title: str, bg_color: str = '#e8e8e8', 
                 fg_color: str = '#000000', **kwargs):
        super().__init__(parent, bg=bg_color, **kwargs)
        
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.is_expanded = True
        
        # Header frame with toggle button
        self.header = tk.Frame(self, bg=bg_color)
        self.header.pack(fill=tk.X, padx=2, pady=2)
        
        # Toggle button (arrow icon)
        self.toggle_btn = tk.Button(
            self.header,
            text="▼",
            command=self.toggle,
            bg=bg_color,
            fg=fg_color,
            font=("Arial", 10, "bold"),
            relief=tk.FLAT,
            width=2,
            cursor="hand2"
        )
        self.toggle_btn.pack(side=tk.LEFT, padx=(2, 5))
        
        # Title label
        self.title_label = tk.Label(
            self.header,
            text=title,
            bg=bg_color,
            fg=fg_color,
            font=("Arial", 10, "bold"),
            anchor="w"
        )
        self.title_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Make header clickable too
        self.header.bind("<Button-1>", lambda e: self.toggle())
        self.title_label.bind("<Button-1>", lambda e: self.toggle())
        
        # Content frame - use light border color
        self.content_frame = tk.Frame(self, bg='#d0d0d0', relief=tk.FLAT, borderwidth=1)
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=(0, 2))
        
        # Inner padding frame for content - light background matching GUI theme
        self.inner_frame = tk.Frame(self.content_frame, bg='#f0f0f0')
        self.inner_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
    def toggle(self):
        """Toggle the collapsed/expanded state."""
        if self.is_expanded:
            self.content_frame.pack_forget()
            self.toggle_btn.config(text="▶")
            self.is_expanded = False
        else:
            self.content_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=(0, 2))
            self.toggle_btn.config(text="▼")
            self.is_expanded = True
    
    def collapse(self):
        """Collapse the frame."""
        if self.is_expanded:
            self.toggle()
    
    def expand(self):
        """Expand the frame."""
        if not self.is_expanded:
            self.toggle()
    
    def get_content_frame(self) -> tk.Frame:
        """Return the frame where content should be added."""
        return self.inner_frame

# ---------- Optional FG Protocol (for type hints) ----------

class FunctionGenerator(Protocol):
    def set_output(self, enabled: bool) -> None: ...  # noqa: E701
    def set_amplitude(self, volts: float) -> None: ...  # noqa: E701
    def get_amplitude(self) -> float: ...  # noqa: E701

# Use existing project motor control
try:
    from Equipment.managers.function_generator import FunctionGeneratorManager
except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
    FunctionGeneratorManager = None  # type: ignore[assignment]
    _FG_IMPORT_ERROR = exc
else:
    _FG_IMPORT_ERROR = None

try:
    from Equipment.managers.laser import LaserManager
except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
    LaserManager = None  # type: ignore[assignment]
    _LASER_IMPORT_ERROR = exc
else:
    _LASER_IMPORT_ERROR = None

import Equipment.Motor_Controll.config as config

try:
    from Equipment.Motor_Controll.Kenisis_motor_control import MotorController as KinesisController
except ModuleNotFoundError as exc:  # pragma: no cover - import guard
    KinesisController = None  # type: ignore[assignment]
    _KINESIS_IMPORT_ERROR = exc
    MOTOR_DRIVER_AVAILABLE = False
else:
    _KINESIS_IMPORT_ERROR = None
    MOTOR_DRIVER_AVAILABLE = True


# ---------- GUI Window ----------

class MotorControlWindow:
    """Advanced motor control GUI with laser positioning and visual feedback.

    Parameters
    ----------
    function_generator : Optional[FunctionGenerator]
        Provide your own FG. If None, FG controls use manager-based connection.
    default_amplitude_volts : float
        Initial amplitude value for FG controls.
    canvas_size_pixels : int
        Width and height of the square canvas in pixels.
    world_range_units : float
        The movement range mapped to the canvas in user units (mm).
    """

    # Color scheme matching other GUIs (light theme)
    COLORS = {
        'bg_dark': '#f0f0f0',  # Light grey background
        'bg_medium': '#f0f0f0',  # Light grey for frames
        'bg_light': '#ffffff',  # White for entries/listboxes
        'fg_primary': '#000000',  # Black text
        'fg_secondary': '#888888',  # Grey secondary text
        'accent_blue': '#569CD6',  # Blue for info/accents
        'accent_green': '#4CAF50',  # Green for buttons/success
        'accent_red': '#F44336',  # Red for errors/stop
        'accent_yellow': '#FFA500',  # Orange for warnings
        'grid_light': '#cccccc',  # Light grey grid lines
        'grid_dark': '#999999',  # Darker grey grid lines
    }

    def __init__(
        self,
        function_generator: Optional[FunctionGenerator] = None,
        default_amplitude_volts: float = 0.4,
        canvas_size_pixels: int = 500,
        world_range_units: float = 25.0,
    ) -> None:
        # Motor controller (initialized on Connect)
        self.motor: Optional[KinesisController] = None
        
        # FG optional (legacy injection) and manager-based control
        self.fg: Optional[FunctionGenerator] = function_generator
        self.fg_mgr: Optional[FunctionGeneratorManager] = None
        
        # Laser controller
        self.laser_mgr: Optional[LaserManager] = None

        # Canvas and world coordinate settings
        self.canvas_size = int(canvas_size_pixels)
        self.world_range = float(world_range_units)
        
        # Position tracking
        self.current_x: float = 0.0
        self.current_y: float = 0.0
        self.laser_marker: Optional[int] = None
        
        # Position presets
        self.presets: Dict[str, Tuple[float, float]] = {}
        self.presets_file = Path("motor_presets.json")
        self._load_presets()
        
        # Camera feed - supports both direct USB and IP stream
        self.camera: Optional[cv2.VideoCapture] = None
        self.camera_index = 0
        self.camera_running = False
        self.camera_thread: Optional[threading.Thread] = None
        self.current_camera_frame: Optional[np.ndarray] = None
        self.camera_frame_lock = threading.Lock()
        self.camera_label: Optional[tk.Label] = None
        self.camera_index_var: Optional[tk.StringVar] = None
        self.camera_ip_var: Optional[tk.StringVar] = None
        self.camera_port_var: Optional[tk.StringVar] = None
        self.camera_mode_var: Optional[tk.StringVar] = None
        self.camera_start_button: Optional[tk.Button] = None
        self.camera_stop_button: Optional[tk.Button] = None
        self.camera_stream_url: Optional[str] = None
        self.camera_photo: Optional[ImageTk.PhotoImage] = None  # Keep reference to prevent garbage collection
        self._updating_display = False  # Flag to prevent overlapping updates

        # Create root window
        self.root = tk.Tk()
        self.root.title("Advanced Motor Control & Laser Positioning")
        self.root.geometry("1400x900")
        self.root.configure(bg=self.COLORS['bg_dark'])

        # State variables
        self.var_status = tk.StringVar(value="Motors: Disconnected")
        self.var_position = tk.StringVar(value="X: 0.00 mm, Y: 0.00 mm")
        self.var_step = tk.StringVar(value="1.0")
        self.var_velocity = tk.StringVar(value=str(config.MAX_VELOCITY))
        self.var_acceleration = tk.StringVar(value=str(config.MAX_ACCELERATION))
        self.var_goto_x = tk.StringVar(value="0.0")
        self.var_goto_y = tk.StringVar(value="0.0")
        self.var_status_x = tk.StringVar(value="Ready")
        self.var_status_y = tk.StringVar(value="Ready")
        
        # FG state
        self.var_fg_status = tk.StringVar(value="FG: Disconnected")
        self.var_fg_addr = tk.StringVar(value=config.LASER_USB)  # Pre-populate from config
        self.var_fg_enabled = tk.BooleanVar(value=False)
        self.var_fg_amplitude = tk.StringVar(value=f"{default_amplitude_volts:.3f}")
        # Predefined FG addresses from test scripts
        self.fg_addresses = [
            "USB0::0xF4EC::0x1103::SDG1XCAQ3R3184::INSTR",  # From test script
            config.LASER_USB,  # From config
            "USB0::0xF4EC::0x1103::INSTR",  # Generic Siglent USB
            "TCPIP0::192.168.1.100::INSTR",  # Generic TCP/IP
        ]
        
        # Laser state
        self.var_laser_status = tk.StringVar(value="Laser: Disconnected")
        self.var_laser_port = tk.StringVar(value="COM4")  # From oxxius.py line 115
        self.var_laser_baud = tk.StringVar(value="19200")  # From oxxius.py line 115
        self.var_laser_enabled = tk.BooleanVar(value=False)
        self.var_laser_power = tk.StringVar(value="10.0")
        # Track previous emission state to detect toggle direction
        self._laser_emission_previous_state = False
        # Predefined laser ports and baud rates from test scripts
        self.laser_configs = [
            {"port": "COM4", "baud": "19200"},  # From oxxius.py line 115 (primary)
            {"port": "COM4", "baud": "38400"},  # From test.py
            {"port": "COM3", "baud": "38400"},  # Default from oxxius.py
            {"port": "COM3", "baud": "19200"},
            {"port": "COM5", "baud": "38400"},
            {"port": "COM5", "baud": "19200"},
        ]
        
        # Scanning state
        self.var_scan_x = tk.StringVar(value="5.0")
        self.var_scan_y = tk.StringVar(value="5.0")
        self.var_scan_count = tk.StringVar(value="3")
        self.var_scan_direction = tk.StringVar(value="Horizontal")

        self._build_ui()
        self._update_canvas_display()
        self._setup_keyboard_shortcuts()

        if not MOTOR_DRIVER_AVAILABLE or KinesisController is None:
            self.var_status.set("Motors: Driver unavailable (install pylablib)")
            try:
                self.btn_connect.configure(state=tk.DISABLED)
            except Exception:
                pass

    # ---------- UI Construction ----------
    def _build_ui(self) -> None:
        """Build the complete user interface."""
        # Configure root grid
        self.root.columnconfigure(0, weight=0)  # Controls (fixed width)
        self.root.columnconfigure(1, weight=1)  # Canvas + Camera (takes remaining space)
        self.root.rowconfigure(0, weight=0)  # Header
        self.root.rowconfigure(1, weight=1)  # Main content
        self.root.rowconfigure(2, weight=0)  # Status bar

        # Build sections
        self._build_header()
        self._build_controls()
        self._build_canvas_and_camera()
        self._build_status_bar()

    def _build_header(self) -> None:
        """Build header with title and connection controls."""
        header = tk.Frame(self.root, bg=self.COLORS['bg_dark'], pady=10, padx=10)
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.columnconfigure(1, weight=1)

        # Title
        title_label = tk.Label(
            header, 
            text="⚡ Motor Control & Laser Positioning", 
            font=("Arial", 16, "bold"),
            fg=self.COLORS['accent_blue'],
            bg=self.COLORS['bg_dark']
        )
        title_label.grid(row=0, column=0, sticky="w", padx=(0, 20))

        # Connection buttons
        btn_frame = tk.Frame(header, bg=self.COLORS['bg_dark'])
        btn_frame.grid(row=0, column=1, sticky="e")
        
        self.btn_connect = tk.Button(
            btn_frame, 
            text="🔌 Connect Motors", 
            command=self._on_connect,
            bg=self.COLORS['accent_green'],
            fg='black',
            font=("Arial", 10, "bold"),
            padx=15,
            pady=5,
            relief=tk.FLAT
        )
        self.btn_connect.pack(side=tk.LEFT, padx=5)
        
        self.btn_disconnect = tk.Button(
            btn_frame, 
            text="⏹ Disconnect", 
            command=self._on_disconnect,
            bg=self.COLORS['accent_red'],
            fg='white',
            font=("Arial", 10, "bold"),
            padx=15,
            pady=5,
            relief=tk.FLAT
        )
        self.btn_disconnect.pack(side=tk.LEFT, padx=5)
        
        # Help button
        help_btn = tk.Button(
            btn_frame,
            text="Help / Guide",
            command=self._show_help,
            bg=self.COLORS['accent_blue'],
            fg="white",
            font=("Arial", 10, "bold"),
            padx=15,
            pady=5,
            relief=tk.FLAT
        )
        help_btn.pack(side=tk.LEFT, padx=5)
        
        # Position display
        pos_label = tk.Label(
            header,
            textvariable=self.var_position,
            font=("Consolas", 11),
            fg=self.COLORS['accent_yellow'],
            bg=self.COLORS['bg_dark']
        )
        pos_label.grid(row=0, column=2, sticky="e", padx=(20, 0))

    def _build_controls(self) -> None:
        """Build left control panel."""
        controls_container = tk.Frame(self.root, bg=self.COLORS['bg_dark'], width=380)
        controls_container.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        controls_container.grid_propagate(False)
        controls_container.rowconfigure(1, weight=1)
        controls_container.columnconfigure(0, weight=1)

        # Expand/Collapse all buttons
        expand_collapse_frame = tk.Frame(controls_container, bg=self.COLORS['bg_dark'])
        expand_collapse_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(0, 5))
        
        tk.Button(
            expand_collapse_frame,
            text="▼ Expand All",
            command=self._expand_all_sections,
            bg=self.COLORS['accent_blue'],
            fg='white',
            font=("Arial", 9),
            relief=tk.FLAT,
            padx=10,
            pady=3
        ).pack(side=tk.LEFT, padx=2)
        
        tk.Button(
            expand_collapse_frame,
            text="▶ Collapse All",
            command=self._collapse_all_sections,
            bg=self.COLORS['accent_blue'],
            fg='white',
            font=("Arial", 9),
            relief=tk.FLAT,
            padx=10,
            pady=3
        ).pack(side=tk.LEFT, padx=2)

        # Create canvas for scrolling
        canvas = tk.Canvas(
            controls_container, 
            bg=self.COLORS['bg_dark'], 
            highlightthickness=0
        )
        scrollbar = ttk.Scrollbar(controls_container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=self.COLORS['bg_dark'])

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.grid(row=1, column=0, sticky="nsew")
        scrollbar.grid(row=1, column=1, sticky="ns")
        
        # Store collapsible sections for expand/collapse all
        self.collapsible_sections = []

        # Add control sections
        self._build_jog_controls(scrollable_frame)
        self._build_goto_controls(scrollable_frame)
        self._build_motor_settings(scrollable_frame)
        self._build_presets(scrollable_frame)
        self._build_scan_controls(scrollable_frame)
        self._build_fg_controls(scrollable_frame)
        self._build_laser_controls(scrollable_frame)

    def _expand_all_sections(self) -> None:
        """Expand all collapsible sections."""
        for section in self.collapsible_sections:
            section.expand()
    
    def _collapse_all_sections(self) -> None:
        """Collapse all collapsible sections."""
        for section in self.collapsible_sections:
            section.collapse()

    def _build_jog_controls(self, parent: tk.Frame) -> None:
        """Build jog controls section."""
        collapsible = CollapsibleFrame(parent, "🎮 Jog Controls", bg_color=self.COLORS['bg_dark'], fg_color=self.COLORS['fg_primary'])
        collapsible.pack(fill=tk.X, pady=3)
        self.collapsible_sections.append(collapsible)
        
        jog_frame = collapsible.get_content_frame()
        jog_frame.configure(bg=self.COLORS['bg_medium'])

        # Step size
        tk.Label(
            jog_frame, 
            text="Step Size (mm):", 
            font=("Arial", 9),
            fg=self.COLORS['fg_primary'],
            bg=self.COLORS['bg_medium']
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 5))
        
        step_entry = tk.Entry(
            jog_frame, 
            textvariable=self.var_step, 
            font=("Arial", 10),
            bg=self.COLORS['bg_light'],
            fg=self.COLORS['fg_primary'],
            insertbackground=self.COLORS['fg_primary']
        )
        step_entry.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        # Bind validation to update on focus out or Enter key
        step_entry.bind('<FocusOut>', self._validate_step)
        step_entry.bind('<Return>', self._validate_step)

        # Jog buttons - styled
        btn_y_pos = tk.Button(
            jog_frame, 
            text="▲\nY+", 
            command=lambda: self._on_jog("y", +1),
            bg=self.COLORS['accent_blue'],
            fg='white',
            font=("Arial", 10, "bold"),
            width=6,
            height=2
        )
        btn_y_pos.grid(row=2, column=1, padx=2, pady=2)

        btn_x_neg = tk.Button(
            jog_frame, 
            text="◀\nX-", 
            command=lambda: self._on_jog("x", -1),
            bg=self.COLORS['accent_blue'],
            fg='white',
            font=("Arial", 10, "bold"),
            width=6,
            height=2
        )
        btn_x_neg.grid(row=3, column=0, padx=2, pady=2)

        self.btn_home = tk.Button(
            jog_frame, 
            text="🏠\nHOME", 
            command=self._on_home,
            bg=self.COLORS['accent_yellow'],
            fg='black',
            font=("Arial", 9, "bold"),
            width=6,
            height=2
        )
        self.btn_home.grid(row=3, column=1, padx=2, pady=2)

        btn_x_pos = tk.Button(
            jog_frame, 
            text="▶\nX+", 
            command=lambda: self._on_jog("x", +1),
            bg=self.COLORS['accent_blue'],
            fg='white',
            font=("Arial", 10, "bold"),
            width=6,
            height=2
        )
        btn_x_pos.grid(row=3, column=2, padx=2, pady=2)

        btn_y_neg = tk.Button(
            jog_frame, 
            text="▼\nY-", 
            command=lambda: self._on_jog("y", -1),
            bg=self.COLORS['accent_blue'],
            fg='white',
            font=("Arial", 10, "bold"),
            width=6,
            height=2
        )
        btn_y_neg.grid(row=4, column=1, padx=2, pady=2)

        # Configure grid weights
        for i in range(3):
            jog_frame.columnconfigure(i, weight=1)

    def _build_goto_controls(self, parent: tk.Frame) -> None:
        """Build go-to-position controls."""
        collapsible = CollapsibleFrame(parent, "📍 Go To Position", bg_color=self.COLORS['bg_dark'], fg_color=self.COLORS['fg_primary'])
        collapsible.pack(fill=tk.X, pady=3)
        self.collapsible_sections.append(collapsible)
        
        goto_frame = collapsible.get_content_frame()
        goto_frame.configure(bg=self.COLORS['bg_medium'])

        # X coordinate
        tk.Label(
            goto_frame, 
            text="X (mm):", 
            fg=self.COLORS['fg_primary'],
            bg=self.COLORS['bg_medium']
        ).grid(row=0, column=0, sticky="w", pady=2)
        tk.Entry(
            goto_frame, 
            textvariable=self.var_goto_x,
            bg=self.COLORS['bg_light'],
            fg=self.COLORS['fg_primary'],
            insertbackground=self.COLORS['fg_primary']
        ).grid(row=0, column=1, sticky="ew", pady=2)

        # Y coordinate
        tk.Label(
            goto_frame, 
            text="Y (mm):", 
            fg=self.COLORS['fg_primary'],
            bg=self.COLORS['bg_medium']
        ).grid(row=1, column=0, sticky="w", pady=2)
        tk.Entry(
            goto_frame, 
            textvariable=self.var_goto_y,
            bg=self.COLORS['bg_light'],
            fg=self.COLORS['fg_primary'],
            insertbackground=self.COLORS['fg_primary']
        ).grid(row=1, column=1, sticky="ew", pady=2)

        # Go button
        tk.Button(
            goto_frame, 
            text="➜ Move To Position", 
            command=self._on_goto,
            bg=self.COLORS['accent_green'],
            fg='black',
            font=("Arial", 9, "bold")
        ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(5, 0))

        goto_frame.columnconfigure(1, weight=1)

    def _build_motor_settings(self, parent: tk.Frame) -> None:
        """Build motor velocity/acceleration settings."""
        collapsible = CollapsibleFrame(parent, "⚙️ Motor Settings", bg_color=self.COLORS['bg_dark'], fg_color=self.COLORS['fg_primary'])
        collapsible.pack(fill=tk.X, pady=3)
        self.collapsible_sections.append(collapsible)
        
        settings_frame = collapsible.get_content_frame()
        settings_frame.configure(bg=self.COLORS['bg_medium'])

        # Velocity
        tk.Label(
            settings_frame, 
            text="Max Velocity (mm/s):", 
            fg=self.COLORS['fg_primary'],
            bg=self.COLORS['bg_medium']
        ).grid(row=0, column=0, sticky="w", pady=2)
        tk.Entry(
            settings_frame, 
            textvariable=self.var_velocity,
            bg=self.COLORS['bg_light'],
            fg=self.COLORS['fg_primary'],
            insertbackground=self.COLORS['fg_primary']
        ).grid(row=0, column=1, sticky="ew", pady=2)

        # Acceleration
        tk.Label(
            settings_frame, 
            text="Acceleration (mm/s²):", 
            fg=self.COLORS['fg_primary'],
            bg=self.COLORS['bg_medium']
        ).grid(row=1, column=0, sticky="w", pady=2)
        tk.Entry(
            settings_frame, 
            textvariable=self.var_acceleration,
            bg=self.COLORS['bg_light'],
            fg=self.COLORS['fg_primary'],
            insertbackground=self.COLORS['fg_primary']
        ).grid(row=1, column=1, sticky="ew", pady=2)

        # Apply button
        tk.Button(
            settings_frame, 
            text="Apply Settings", 
            command=self._apply_motor_settings,
            bg=self.COLORS['accent_blue'],
            fg='white',
            font=("Arial", 9)
        ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(5, 0))

        settings_frame.columnconfigure(1, weight=1)

    def _build_presets(self, parent: tk.Frame) -> None:
        """Build position presets section."""
        collapsible = CollapsibleFrame(parent, "⭐ Position Presets", bg_color=self.COLORS['bg_dark'], fg_color=self.COLORS['fg_primary'])
        collapsible.pack(fill=tk.X, pady=3)
        self.collapsible_sections.append(collapsible)
        
        presets_frame = collapsible.get_content_frame()
        presets_frame.configure(bg=self.COLORS['bg_medium'])

        # Presets listbox
        self.presets_listbox = tk.Listbox(
            presets_frame,
            height=4,
            bg=self.COLORS['bg_light'],
            fg=self.COLORS['fg_primary'],
            selectbackground=self.COLORS['accent_blue'],
            font=("Consolas", 9)
        )
        self.presets_listbox.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 5))
        self._update_presets_list()

        # Buttons
        tk.Button(
            presets_frame, 
            text="💾 Save Current", 
            command=self._save_preset,
            bg=self.COLORS['accent_green'],
            fg='black',
            font=("Arial", 8)
        ).grid(row=1, column=0, sticky="ew", padx=(0, 2))

        tk.Button(
            presets_frame, 
            text="📌 Go To Selected", 
            command=self._goto_preset,
            bg=self.COLORS['accent_blue'],
            fg='white',
            font=("Arial", 8)
        ).grid(row=1, column=1, sticky="ew", padx=(2, 0))

        tk.Button(
            presets_frame, 
            text="🗑️ Delete Selected", 
            command=self._delete_preset,
            bg=self.COLORS['accent_red'],
            fg='white',
            font=("Arial", 8)
        ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(2, 0))

        presets_frame.columnconfigure(0, weight=1)
        presets_frame.columnconfigure(1, weight=1)

    def _build_scan_controls(self, parent: tk.Frame) -> None:
        """Build scanning/raster controls."""
        collapsible = CollapsibleFrame(parent, "🔍 Raster Scan", bg_color=self.COLORS['bg_dark'], fg_color=self.COLORS['fg_primary'])
        collapsible.pack(fill=tk.X, pady=3)
        self.collapsible_sections.append(collapsible)
        
        scan_frame = collapsible.get_content_frame()
        scan_frame.configure(bg=self.COLORS['bg_medium'])

        # X distance
        tk.Label(
            scan_frame, 
            text="X Distance (mm):", 
            fg=self.COLORS['fg_primary'],
            bg=self.COLORS['bg_medium']
        ).grid(row=0, column=0, sticky="w", pady=2)
        tk.Entry(
            scan_frame, 
            textvariable=self.var_scan_x,
            bg=self.COLORS['bg_light'],
            fg=self.COLORS['fg_primary'],
            insertbackground=self.COLORS['fg_primary']
        ).grid(row=0, column=1, sticky="ew", pady=2)

        # Y distance
        tk.Label(
            scan_frame, 
            text="Y Distance (mm):", 
            fg=self.COLORS['fg_primary'],
            bg=self.COLORS['bg_medium']
        ).grid(row=1, column=0, sticky="w", pady=2)
        tk.Entry(
            scan_frame, 
            textvariable=self.var_scan_y,
            bg=self.COLORS['bg_light'],
            fg=self.COLORS['fg_primary'],
            insertbackground=self.COLORS['fg_primary']
        ).grid(row=1, column=1, sticky="ew", pady=2)

        # Number of rasters
        tk.Label(
            scan_frame, 
            text="Raster Count:", 
            fg=self.COLORS['fg_primary'],
            bg=self.COLORS['bg_medium']
        ).grid(row=2, column=0, sticky="w", pady=2)
        tk.Entry(
            scan_frame, 
            textvariable=self.var_scan_count,
            bg=self.COLORS['bg_light'],
            fg=self.COLORS['fg_primary'],
            insertbackground=self.COLORS['fg_primary']
        ).grid(row=2, column=1, sticky="ew", pady=2)

        # Direction
        tk.Label(
            scan_frame, 
            text="Direction:", 
            fg=self.COLORS['fg_primary'],
            bg=self.COLORS['bg_medium']
        ).grid(row=3, column=0, sticky="w", pady=2)
        direction_combo = ttk.Combobox(
            scan_frame,
            textvariable=self.var_scan_direction,
            values=["Horizontal", "Vertical"],
            state="readonly"
        )
        direction_combo.grid(row=3, column=1, sticky="ew", pady=2)

        # Start scan button
        tk.Button(
            scan_frame, 
            text="▶️ Start Scan", 
            command=self._start_scan,
            bg=self.COLORS['accent_green'],
            fg='black',
            font=("Arial", 9, "bold")
        ).grid(row=4, column=0, columnspan=2, sticky="ew", pady=(5, 0))

        scan_frame.columnconfigure(1, weight=1)

    def _build_fg_controls(self, parent: tk.Frame) -> None:
        """Build function generator controls."""
        collapsible = CollapsibleFrame(parent, "⚡ Function Generator", bg_color=self.COLORS['bg_dark'], fg_color=self.COLORS['fg_primary'])
        collapsible.pack(fill=tk.X, pady=3)
        # Start collapsed by default to save space
        collapsible.collapse()
        self.collapsible_sections.append(collapsible)
        
        fg_frame = collapsible.get_content_frame()
        fg_frame.configure(bg=self.COLORS['bg_medium'])

        # VISA address with dropdown and auto-detect button
        tk.Label(
            fg_frame, 
            text="VISA Address:", 
            fg=self.COLORS['fg_primary'],
            bg=self.COLORS['bg_medium']
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=2)
        
        # Dropdown for predefined addresses
        addr_dropdown_frame = tk.Frame(fg_frame, bg=self.COLORS['bg_medium'])
        addr_dropdown_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 5))
        addr_dropdown_frame.columnconfigure(0, weight=1)
        
        self.fg_addr_combo = ttk.Combobox(
            addr_dropdown_frame,
            values=["Custom..."] + self.fg_addresses,
            state="readonly",
            width=50
        )
        self.fg_addr_combo.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        # Set initial value if current address matches a predefined one
        current_addr = self.var_fg_addr.get()
        if current_addr in self.fg_addresses:
            self.fg_addr_combo.set(current_addr)
        else:
            self.fg_addr_combo.set("Custom...")
        self.fg_addr_combo.bind("<<ComboboxSelected>>", self._on_fg_addr_selected)
        
        auto_btn = tk.Button(
            addr_dropdown_frame,
            text="🔍",
            command=self._auto_detect_fg,
            bg=self.COLORS['accent_blue'],
            fg='white',
            width=3
        )
        auto_btn.grid(row=0, column=1, padx=(0, 5))
        
        # Entry field for custom/manual address
        addr_frame = tk.Frame(fg_frame, bg=self.COLORS['bg_medium'])
        addr_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 5))
        addr_frame.columnconfigure(0, weight=1)
        
        addr_entry = tk.Entry(
            addr_frame, 
            textvariable=self.var_fg_addr,
            bg=self.COLORS['bg_light'],
            fg=self.COLORS['fg_primary'],
            insertbackground=self.COLORS['fg_primary']
        )
        addr_entry.grid(row=0, column=0, sticky="ew")

        # Connection buttons
        btn_frame = tk.Frame(fg_frame, bg=self.COLORS['bg_medium'])
        btn_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 5))
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)
        
        connect_btn = tk.Button(
            btn_frame, 
            text="Connect", 
            command=self._on_fg_connect,
            bg=self.COLORS['accent_green'],
            fg='black',
            font=("Arial", 8)
        )
        connect_btn.grid(row=0, column=0, sticky="ew", padx=(0, 2))
        
        disconnect_btn = tk.Button(
            btn_frame, 
            text="Disconnect", 
            command=self._on_fg_disconnect,
            bg=self.COLORS['accent_red'],
            fg='white',
            font=("Arial", 8)
        )
        disconnect_btn.grid(row=0, column=1, sticky="ew", padx=(2, 0))

        # Status
        status_label = tk.Label(
            fg_frame,
            textvariable=self.var_fg_status,
            fg=self.COLORS['accent_yellow'],
            bg=self.COLORS['bg_medium'],
            font=("Arial", 9)
        )
        status_label.grid(row=4, column=0, columnspan=2, sticky="w", pady=2)

        # Output toggle
        output_check = tk.Checkbutton(
            fg_frame, 
            text="Output Enabled", 
            variable=self.var_fg_enabled, 
            command=self._on_fg_toggle,
            fg=self.COLORS['fg_primary'],
            bg=self.COLORS['bg_medium'],
            selectcolor=self.COLORS['bg_light'],
            activebackground=self.COLORS['bg_medium'],
            activeforeground=self.COLORS['fg_primary']
        )
        output_check.grid(row=5, column=0, columnspan=2, sticky="w", pady=2)

        # DC Voltage
        tk.Label(
            fg_frame, 
            text="DC Voltage (V):", 
            fg=self.COLORS['fg_primary'],
            bg=self.COLORS['bg_medium']
        ).grid(row=6, column=0, sticky="w", pady=2)
        amplitude_entry = tk.Entry(
            fg_frame, 
            textvariable=self.var_fg_amplitude,
            bg=self.COLORS['bg_light'],
            fg=self.COLORS['fg_primary'],
            insertbackground=self.COLORS['fg_primary']
        )
        amplitude_entry.grid(row=6, column=1, sticky="ew", pady=2)

        # Apply button
        apply_btn = tk.Button(
            fg_frame, 
            text="Apply Voltage", 
            command=self._on_apply_amplitude,
            bg=self.COLORS['accent_blue'],
            fg='white',
            font=("Arial", 9)
        )
        apply_btn.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(5, 0))

        fg_frame.columnconfigure(1, weight=1)

        if FunctionGeneratorManager is None:
            self.var_fg_status.set("FG: Driver unavailable (install pyvisa)")
            for widget in (
                self.fg_addr_combo,
                addr_entry,
                auto_btn,
                connect_btn,
                disconnect_btn,
                output_check,
                amplitude_entry,
                apply_btn,
            ):
                widget.configure(state=tk.DISABLED)

    def _build_laser_controls(self, parent: tk.Frame) -> None:
        """Build laser controller controls."""
        collapsible = CollapsibleFrame(parent, "🔴 Laser Control", bg_color=self.COLORS['bg_dark'], fg_color=self.COLORS['fg_primary'])
        collapsible.pack(fill=tk.X, pady=3)
        # Start collapsed by default to save space
        collapsible.collapse()
        self.collapsible_sections.append(collapsible)
        
        laser_frame = collapsible.get_content_frame()
        laser_frame.configure(bg=self.COLORS['bg_medium'])

        # COM Port with dropdown
        tk.Label(
            laser_frame, 
            text="Configuration:", 
            fg=self.COLORS['fg_primary'],
            bg=self.COLORS['bg_medium']
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=2)
        
        # Create dropdown options from configs
        laser_config_options = ["Custom..."] + [
            f"{cfg['port']} @ {cfg['baud']} baud" for cfg in self.laser_configs
        ]
        
        self.laser_config_combo = ttk.Combobox(
            laser_frame,
            values=laser_config_options,
            state="readonly",
            width=30
        )
        self.laser_config_combo.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 5))
        # Set initial value if current config matches a predefined one
        current_port = self.var_laser_port.get()
        current_baud = self.var_laser_baud.get()
        matching_config = f"{current_port} @ {current_baud} baud"
        if matching_config in laser_config_options:
            self.laser_config_combo.set(matching_config)
        else:
            self.laser_config_combo.set("Custom...")
        self.laser_config_combo.bind("<<ComboboxSelected>>", self._on_laser_config_selected)

        # COM Port
        tk.Label(
            laser_frame, 
            text="COM Port:", 
            fg=self.COLORS['fg_primary'],
            bg=self.COLORS['bg_medium']
        ).grid(row=2, column=0, sticky="w", pady=2)
        port_entry = tk.Entry(
            laser_frame, 
            textvariable=self.var_laser_port,
            bg=self.COLORS['bg_light'],
            fg=self.COLORS['fg_primary'],
            insertbackground=self.COLORS['fg_primary']
        )
        port_entry.grid(row=2, column=1, sticky="ew", pady=2)

        # Baud Rate
        tk.Label(
            laser_frame, 
            text="Baud Rate:", 
            fg=self.COLORS['fg_primary'],
            bg=self.COLORS['bg_medium']
        ).grid(row=3, column=0, sticky="w", pady=2)
        baud_entry = tk.Entry(
            laser_frame, 
            textvariable=self.var_laser_baud,
            bg=self.COLORS['bg_light'],
            fg=self.COLORS['fg_primary'],
            insertbackground=self.COLORS['fg_primary']
        )
        baud_entry.grid(row=3, column=1, sticky="ew", pady=2)

        # Connection buttons
        btn_frame = tk.Frame(laser_frame, bg=self.COLORS['bg_medium'])
        btn_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(5, 5))
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)
        
        connect_btn = tk.Button(
            btn_frame, 
            text="Connect", 
            command=self._on_laser_connect,
            bg=self.COLORS['accent_green'],
            fg='black',
            font=("Arial", 8)
        )
        connect_btn.grid(row=0, column=0, sticky="ew", padx=(0, 2))
        
        disconnect_btn = tk.Button(
            btn_frame, 
            text="Disconnect", 
            command=self._on_laser_disconnect,
            bg=self.COLORS['accent_red'],
            fg='white',
            font=("Arial", 8)
        )
        disconnect_btn.grid(row=0, column=1, sticky="ew", padx=(2, 0))

        # Status
        status_label = tk.Label(
            laser_frame,
            textvariable=self.var_laser_status,
            fg=self.COLORS['accent_yellow'],
            bg=self.COLORS['bg_medium'],
            font=("Arial", 9)
        )
        status_label.grid(row=5, column=0, columnspan=2, sticky="w", pady=2)

        # Emission toggle
        emission_check = tk.Checkbutton(
            laser_frame, 
            text="Emission Enabled", 
            variable=self.var_laser_enabled, 
            command=self._on_laser_toggle,
            fg=self.COLORS['fg_primary'],
            bg=self.COLORS['bg_medium'],
            selectcolor=self.COLORS['bg_light'],
            activebackground=self.COLORS['bg_medium'],
            activeforeground=self.COLORS['fg_primary']
        )
        emission_check.grid(row=6, column=0, columnspan=2, sticky="w", pady=2)

        # Power setting
        tk.Label(
            laser_frame, 
            text="Power (mW):", 
            fg=self.COLORS['fg_primary'],
            bg=self.COLORS['bg_medium']
        ).grid(row=7, column=0, sticky="w", pady=2)
        
        # Power control frame with entry and adjustment buttons
        power_frame = tk.Frame(laser_frame, bg=self.COLORS['bg_medium'])
        power_frame.grid(row=7, column=1, sticky="ew", pady=2)
        power_frame.columnconfigure(1, weight=1)
        
        # Decrease button
        decrease_btn = tk.Button(
            power_frame,
            text="−",
            command=self._decrease_laser_power,
            bg=self.COLORS['accent_blue'],
            fg='white',
            font=("Arial", 10, "bold"),
            width=3
        )
        decrease_btn.grid(row=0, column=0, padx=(0, 2))
        
        # Power entry
        power_entry = tk.Entry(
            power_frame, 
            textvariable=self.var_laser_power,
            bg=self.COLORS['bg_light'],
            fg=self.COLORS['fg_primary'],
            insertbackground=self.COLORS['fg_primary']
        )
        power_entry.grid(row=0, column=1, sticky="ew", padx=2)
        
        # Increase button
        increase_btn = tk.Button(
            power_frame,
            text="+",
            command=self._increase_laser_power,
            bg=self.COLORS['accent_blue'],
            fg='white',
            font=("Arial", 10, "bold"),
            width=3
        )
        increase_btn.grid(row=0, column=2, padx=(2, 0))

        # Apply button
        apply_btn = tk.Button(
            laser_frame, 
            text="Apply Power", 
            command=self._on_apply_laser_power,
            bg=self.COLORS['accent_blue'],
            fg='white',
            font=("Arial", 9)
        )
        apply_btn.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(5, 0))

        laser_frame.columnconfigure(1, weight=1)

        if LaserManager is None:
            self.var_laser_status.set("Laser: Driver unavailable (install pyserial)")
            for widget in (
                self.laser_config_combo,
                port_entry,
                baud_entry,
                connect_btn,
                disconnect_btn,
                emission_check,
                power_entry,
                decrease_btn,
                increase_btn,
                apply_btn,
            ):
                widget.configure(state=tk.DISABLED)

    def _build_canvas_and_camera(self) -> None:
        """Build canvas and camera feed area."""
        right_container = tk.Frame(self.root, bg=self.COLORS['bg_dark'])
        right_container.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
        right_container.rowconfigure(0, weight=1)
        right_container.rowconfigure(1, weight=1)
        right_container.columnconfigure(0, weight=1)

        # Canvas section
        self._build_canvas(right_container)
        
        # Camera section (placeholder)
        self._build_camera_placeholder(right_container)

    def _build_canvas(self, parent: tk.Frame) -> None:
        """Build interactive canvas with grid and position marker."""
        canvas_frame = tk.LabelFrame(
            parent, 
            text="🎯 Position Map (Click to Move)",
            bg=self.COLORS['bg_medium'],
            fg=self.COLORS['fg_primary'],
            font=("Arial", 11, "bold"),
            relief=tk.FLAT,
            borderwidth=2
        )
        canvas_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # Canvas
        self.canvas = tk.Canvas(
            canvas_frame,
            width=self.canvas_size,
            height=self.canvas_size,
            background='#ffffff',
            highlightthickness=0
        )
        self.canvas.pack(padx=10, pady=10)
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<Motion>", self._on_canvas_hover)

        # Coordinate display on canvas
        self.canvas_coord_text = self.canvas.create_text(
            10, 10,
            text="",
            anchor="nw",
            fill=self.COLORS['accent_blue'],
            font=("Consolas", 9)
        )

    def _build_camera_placeholder(self, parent: tk.Frame) -> None:
        """Build camera feed display with controls."""
        camera_frame = tk.LabelFrame(
            parent,
            text="📷 Camera Feed",
            bg=self.COLORS['bg_medium'],
            fg=self.COLORS['fg_primary'],
            font=("Arial", 11, "bold"),
            relief=tk.FLAT,
            borderwidth=2
        )
        camera_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        camera_frame.columnconfigure(0, weight=1)
        camera_frame.rowconfigure(0, weight=1)
        camera_frame.rowconfigure(1, weight=0)

        # Camera display area
        display_frame = tk.Frame(camera_frame, bg='#ffffff')
        display_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        display_frame.columnconfigure(0, weight=1)
        display_frame.rowconfigure(0, weight=1)

        # Camera display - use Label with persistent PhotoImage
        if CAMERA_AVAILABLE:
            # Label for displaying video
            self.camera_label = tk.Label(
                display_frame,
                text="Camera not started",
                bg='#000000',
                fg=self.COLORS['fg_secondary'],
                font=("Arial", 12),
                anchor='center'
            )
            self.camera_label.grid(row=0, column=0, sticky="nsew")
            
            # CRITICAL: Keep a list of PhotoImage objects to prevent garbage collection
            # Tkinter PhotoImage objects must be kept alive by maintaining references
            self._camera_photo_list = []  # List to keep PhotoImage objects alive
            self._camera_photo = None  # Current PhotoImage
        else:
            tk.Label(
                display_frame,
                text="📹\nCamera support not available\n(Install opencv-python and pillow)",
                bg='#ffffff',
                fg=self.COLORS['fg_secondary'],
                font=("Arial", 12)
            ).grid(row=0, column=0, sticky="nsew")

        # Camera controls
        controls_frame = tk.Frame(camera_frame, bg=self.COLORS['bg_medium'])
        controls_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        
        if CAMERA_AVAILABLE:
            # Camera mode selection
            mode_frame = tk.Frame(controls_frame, bg=self.COLORS['bg_medium'])
            mode_frame.pack(side=tk.TOP, fill=tk.X, pady=5)
            
            tk.Label(
                mode_frame,
                text="Mode:",
                bg=self.COLORS['bg_medium'],
                fg=self.COLORS['fg_primary'],
                font=("Arial", 9)
            ).pack(side=tk.LEFT, padx=5)
            
            self.camera_mode_var = tk.StringVar(value="IP Stream")
            mode_combo = ttk.Combobox(
                mode_frame,
                textvariable=self.camera_mode_var,
                values=["IP Stream", "USB Camera"],
                width=12,
                state="readonly"
            )
            mode_combo.pack(side=tk.LEFT, padx=5)
            mode_combo.bind("<<ComboboxSelected>>", lambda e: self._update_camera_mode_ui())
            
            # IP Stream settings
            self.ip_frame = tk.Frame(controls_frame, bg=self.COLORS['bg_medium'])
            self.ip_frame.pack(side=tk.TOP, fill=tk.X, pady=5)
            
            tk.Label(
                self.ip_frame,
                text="Stream IP:",
                bg=self.COLORS['bg_medium'],
                fg=self.COLORS['fg_primary'],
                font=("Arial", 9)
            ).pack(side=tk.LEFT, padx=5)
            
            self.camera_ip_var = tk.StringVar(value="localhost")
            ip_entry = tk.Entry(
                self.ip_frame,
                textvariable=self.camera_ip_var,
                width=15,
                font=("Arial", 9)
            )
            ip_entry.pack(side=tk.LEFT, padx=5)
            
            tk.Label(
                self.ip_frame,
                text="Port:",
                bg=self.COLORS['bg_medium'],
                fg=self.COLORS['fg_primary'],
                font=("Arial", 9)
            ).pack(side=tk.LEFT, padx=5)
            
            self.camera_port_var = tk.StringVar(value="8080")
            port_entry = tk.Entry(
                self.ip_frame,
                textvariable=self.camera_port_var,
                width=6,
                font=("Arial", 9)
            )
            port_entry.pack(side=tk.LEFT, padx=5)
            
            # USB Camera settings (hidden by default)
            self.usb_frame = tk.Frame(controls_frame, bg=self.COLORS['bg_medium'])
            
            tk.Label(
                self.usb_frame,
                text="Camera Index:",
                bg=self.COLORS['bg_medium'],
                fg=self.COLORS['fg_primary'],
                font=("Arial", 9)
            ).pack(side=tk.LEFT, padx=5)
            
            self.camera_index_var = tk.StringVar(value="0")
            camera_entry = tk.Entry(
                self.usb_frame,
                textvariable=self.camera_index_var,
                width=5,
                font=("Arial", 9)
            )
            camera_entry.pack(side=tk.LEFT, padx=5)
            
            # Start/Stop button
            button_frame = tk.Frame(controls_frame, bg=self.COLORS['bg_medium'])
            button_frame.pack(side=tk.TOP, fill=tk.X, pady=5)
            
            self.camera_start_button = tk.Button(
                button_frame,
                text="▶ Start Camera",
                command=self._start_camera_feed,
                bg=self.COLORS['accent_green'],
                fg='white',
                font=("Arial", 9, "bold"),
                padx=10,
                pady=5,
                relief=tk.FLAT
            )
            self.camera_start_button.pack(side=tk.LEFT, padx=5)
            
            self.camera_stop_button = tk.Button(
                button_frame,
                text="⏹ Stop Camera",
                command=self._stop_camera_feed,
                bg=self.COLORS['accent_red'],
                fg='white',
                font=("Arial", 9, "bold"),
                padx=10,
                pady=5,
                relief=tk.FLAT,
                state=tk.DISABLED
            )
            self.camera_stop_button.pack(side=tk.LEFT, padx=5)
            
            # Initialize UI based on default mode
            self._update_camera_mode_ui()

    def _build_status_bar(self) -> None:
        """Build bottom status bar."""
        status_bar = tk.Frame(self.root, bg=self.COLORS['bg_light'], height=30)
        status_bar.grid(row=2, column=0, columnspan=2, sticky="ew")
        status_bar.grid_propagate(False)

        # Motor status
        tk.Label(
            status_bar,
            textvariable=self.var_status,
            fg=self.COLORS['fg_primary'],
            bg=self.COLORS['bg_light'],
            font=("Arial", 9),
            anchor="w"
        ).pack(side=tk.LEFT, padx=10)

        # Axis status
        tk.Label(
            status_bar,
            text="X:",
            fg=self.COLORS['accent_blue'],
            bg=self.COLORS['bg_light'],
            font=("Arial", 9, "bold")
        ).pack(side=tk.LEFT)
        
        tk.Label(
            status_bar,
            textvariable=self.var_status_x,
            fg=self.COLORS['fg_secondary'],
            bg=self.COLORS['bg_light'],
            font=("Arial", 9)
        ).pack(side=tk.LEFT, padx=(2, 15))

        tk.Label(
            status_bar,
            text="Y:",
            fg=self.COLORS['accent_green'],
            bg=self.COLORS['bg_light'],
            font=("Arial", 9, "bold")
        ).pack(side=tk.LEFT)
        
        tk.Label(
            status_bar,
            textvariable=self.var_status_y,
            fg=self.COLORS['fg_secondary'],
            bg=self.COLORS['bg_light'],
            font=("Arial", 9)
        ).pack(side=tk.LEFT, padx=(2, 0))

        # Keyboard shortcuts hint
        tk.Label(
            status_bar,
            text="⌨️ Shortcuts: Arrow keys=Jog | H=Home | G=Go-to | S=Save Preset | Ctrl+Q=Quit",
            fg=self.COLORS['grid_light'],
            bg=self.COLORS['bg_light'],
            font=("Arial", 8)
        ).pack(side=tk.RIGHT, padx=10)

    def _create_section_frame(self, parent: tk.Frame, title: str) -> tk.Frame:
        """Create a styled section frame for controls."""
        frame = tk.LabelFrame(
            parent,
            text=title,
            bg=self.COLORS['bg_medium'],
            fg=self.COLORS['fg_primary'],
            font=("Arial", 10, "bold"),
            relief=tk.FLAT,
            borderwidth=1,
            padx=10,
            pady=10
        )
        return frame

    # ---------- Canvas Management ----------
    def _update_canvas_display(self) -> None:
        """Update canvas with grid, labels, and position marker."""
        c = self.canvas
        c.delete("all")
        size = self.canvas_size
        
        # Background grid
        spacing = 50  # pixels between grid lines
        num_lines = size // spacing
        
        # Draw grid lines
        for i in range(num_lines + 1):
            pos = i * spacing
            # Vertical lines
            c.create_line(
                pos, 0, pos, size,
                fill=self.COLORS['grid_dark'],
                width=1,
                tags="grid"
            )
            # Horizontal lines
            c.create_line(
                0, pos, size, pos,
                fill=self.COLORS['grid_dark'],
                width=1,
                tags="grid"
            )
            
            # Add coordinate labels
            if i > 0:
                world_x = (i * spacing / size) * self.world_range
                world_y = self.world_range - (i * spacing / size) * self.world_range
                
                # X-axis labels (bottom)
                c.create_text(
                    pos, size - 5,
                    text=f"{world_x:.0f}",
                    fill=self.COLORS['grid_light'],
                    font=("Arial", 7),
                    anchor="s",
                    tags="grid"
                )
                
                # Y-axis labels (left)
                c.create_text(
                    5, pos,
                    text=f"{world_y:.0f}",
                    fill=self.COLORS['grid_light'],
                    font=("Arial", 7),
                    anchor="w",
                    tags="grid"
                )

        # Draw axes (heavier lines at origin)
        origin_y = size  # Y=0 is at bottom
        c.create_line(0, origin_y, size, origin_y, fill=self.COLORS['accent_blue'], width=2, tags="axes")
        c.create_line(0, 0, 0, size, fill=self.COLORS['accent_green'], width=2, tags="axes")

        # Origin label
        c.create_text(
            15, size - 15,
            text="(0,0)",
            fill=self.COLORS['accent_yellow'],
            font=("Arial", 9, "bold"),
            tags="origin"
        )

        # Draw laser position marker
        self._update_laser_marker()

        # Recreate coordinate display
        self.canvas_coord_text = c.create_text(
            10, 10,
            text="",
            anchor="nw",
            fill=self.COLORS['accent_blue'],
            font=("Consolas", 9),
            tags="coord_display"
        )

    def _update_laser_marker(self) -> None:
        """Update laser position marker on canvas."""
        if self.laser_marker:
            self.canvas.delete(self.laser_marker)
        
        # Convert world coordinates to canvas coordinates
        cx, cy = self._world_to_canvas(self.current_x, self.current_y)
        
        # Draw laser marker (red circle with crosshairs)
        radius = 8
        self.canvas.create_oval(
            cx - radius, cy - radius, cx + radius, cy + radius,
            outline=self.COLORS['accent_red'],
            width=2,
            tags="laser"
        )
        self.canvas.create_oval(
            cx - 2, cy - 2, cx + 2, cy + 2,
            fill=self.COLORS['accent_red'],
            outline=self.COLORS['accent_red'],
            tags="laser"
        )
        # Crosshairs
        self.canvas.create_line(
            cx - radius - 3, cy, cx + radius + 3, cy,
            fill=self.COLORS['accent_red'],
            width=1,
            tags="laser"
        )
        self.canvas.create_line(
            cx, cy - radius - 3, cx, cy + radius + 3,
            fill=self.COLORS['accent_red'],
            width=1,
            tags="laser"
        )

    def _world_to_canvas(self, wx: float, wy: float) -> Tuple[int, int]:
        """Convert world coordinates to canvas pixel coordinates."""
        size = self.canvas_size
        cx = int((wx / self.world_range) * size)
        cy = int(size - (wy / self.world_range) * size)  # Flip Y (canvas Y=0 is top)
        return (cx, cy)

    def _canvas_to_world(self, px: int, py: int) -> Tuple[float, float]:
        """Convert canvas pixel coordinates to world coordinates."""
        size = self.canvas_size
        wx = (px / float(size)) * self.world_range
        wy = self.world_range - (py / float(size)) * self.world_range  # Flip Y back
        return (wx, wy)

    # ---------- Event Handlers ----------
    def _on_connect(self) -> None:
        """Connect to motors."""
        if not MOTOR_DRIVER_AVAILABLE or KinesisController is None:
            details = (
                "pylablib is not installed, so the Thorlabs Kinesis motor driver "
                "cannot be loaded."
            )
            if _KINESIS_IMPORT_ERROR:
                details += f"\nOriginal import error: {_KINESIS_IMPORT_ERROR}"
            messagebox.showerror("Motor Driver Unavailable", details)
            return

        try:
            self.var_status.set("Motors: Connecting...")
            self.root.update()

            self.motor = KinesisController()

            # Check for initialization errors
            err_parts = []
            if getattr(self.motor, "error_x", None):
                err_parts.append(f"X: {self.motor.error_x}")
            if getattr(self.motor, "error_y", None):
                err_parts.append(f"Y: {self.motor.error_y}")

            if err_parts:
                self.var_status.set("Motors: Connected (with errors)")
                messagebox.showwarning("Connection Warning", "; ".join(err_parts))
            else:
                self.var_status.set("Motors: Connected ✓")

            # Apply motor settings
            self._apply_motor_settings()

            # Read initial position
            self._refresh_position()

        except Exception as exc:
            self.var_status.set("Motors: Connection Failed")
            messagebox.showerror("Connection Error", f"Failed to connect to motors:\n{exc}")

    def _on_disconnect(self) -> None:
        """Disconnect from motors."""
        try:
            if self.motor is not None:
                try:
                    self.motor.stop_motors()
                except Exception:
                    pass
            self.motor = None
            self.var_status.set("Motors: Disconnected")
            self.var_status_x.set("Ready")
            self.var_status_y.set("Ready")
        except Exception as exc:
            messagebox.showerror("Disconnect Error", f"Error during disconnect:\n{exc}")

    def _on_home(self) -> None:
        """Home both motors to (0,0) in parallel threads."""
        if not self._is_connected():
            messagebox.showwarning("Not Connected", "Please connect to motors first.")
            return
        
        # Disable home button during homing
        if hasattr(self, 'btn_home'):
            self.btn_home.config(state=tk.DISABLED)
        
        self.var_status.set("Motors: Homing...")
        self.var_status_x.set("Homing X...")
        self.var_status_y.set("Homing Y...")
        self.root.update()
        
        # Run homing in a background thread to prevent GUI freezing
        def home_thread():
            """Thread function to home motors in parallel."""
            try:
                # Create threads for X and Y homing to run simultaneously
                def home_x():
                    """Home X axis."""
                    if self.motor and self.motor.motor_x:  # type: ignore
                        try:
                            self.motor.motor_x.home()  # type: ignore
                            self.motor.motor_x.wait_move()  # type: ignore
                            self.root.after(0, lambda: self.var_status_x.set("Homed X ✓"))
                        except Exception as e:
                            self.root.after(0, lambda: self.var_status_x.set(f"Error: {str(e)}"))
                
                def home_y():
                    """Home Y axis."""
                    if self.motor and self.motor.motor_y:  # type: ignore
                        try:
                            self.motor.motor_y.home()  # type: ignore
                            self.motor.motor_y.wait_move()  # type: ignore
                            self.root.after(0, lambda: self.var_status_y.set("Homed Y ✓"))
                        except Exception as e:
                            self.root.after(0, lambda: self.var_status_y.set(f"Error: {str(e)}"))
                
                # Start both homing operations in parallel
                thread_x = threading.Thread(target=home_x, daemon=True)
                thread_y = threading.Thread(target=home_y, daemon=True)
                
                thread_x.start()
                thread_y.start()
                
                # Wait for both threads to complete
                thread_x.join()
                thread_y.join()
                
                # Update UI on main thread
                self.root.after(0, lambda: self._refresh_position())
                self.root.after(0, lambda: self.var_status.set("Motors: Homed ✓"))
                
            except Exception as exc:
                self.root.after(0, lambda: self.var_status.set("Motors: Homing Failed"))
                self.root.after(0, lambda: messagebox.showerror("Homing Error", f"Failed to home motors:\n{exc}"))
            finally:
                # Re-enable home button
                if hasattr(self, 'btn_home'):
                    self.root.after(0, lambda: self.btn_home.config(state=tk.NORMAL))
        
        # Start the homing thread
        threading.Thread(target=home_thread, daemon=True).start()

    def _validate_step(self, event=None) -> None:
        """Validate and correct step size entry."""
        try:
            value = float(self.var_step.get())
            if value <= 0:
                raise ValueError("Step must be positive")
            # Value is valid, format it nicely
            self.var_step.set(f"{value:.3f}")
        except ValueError:
            # Invalid value, reset to default
            self.var_step.set("1.0")
            messagebox.showwarning("Invalid Step", "Step size must be a positive number. Reset to 1.0 mm.")

    def _on_jog(self, axis: str, sign: int) -> None:
        """Jog motor by step amount."""
        if not self._is_connected():
            messagebox.showwarning("Not Connected", "Please connect to motors first.")
            return
        
        try:
            step = float(self.var_step.get()) * float(sign)
        except ValueError:
            step = 1.0 * float(sign)
            self.var_step.set("1.0")
        
        try:
            if axis.lower() == "x":
                self.motor.move_motor_x(step, self.var_status_x)  # type: ignore
            else:
                # Y direction reversed: invert the sign
                self.motor.move_motor_y(-step, self.var_status_y)  # type: ignore
            self._refresh_position()
        except Exception as exc:
            messagebox.showerror("Jog Error", f"Failed to jog {axis.upper()} axis:\n{exc}")

    def _on_goto(self) -> None:
        """Move to specified coordinates."""
        if not self._is_connected():
            messagebox.showwarning("Not Connected", "Please connect to motors first.")
            return
        
        try:
            x = float(self.var_goto_x.get())
            y = float(self.var_goto_y.get())
            
            # Validate range
            if not (0 <= x <= self.world_range and 0 <= y <= self.world_range):
                messagebox.showwarning(
                    "Out of Range",
                    f"Coordinates must be between 0 and {self.world_range} mm."
                )
                return
            
            self.var_status.set(f"Motors: Moving to ({x:.2f}, {y:.2f})...")
            self.root.update()
            self.motor.move_to_target(x, y, self.var_status_x, self.var_status_y)  # type: ignore
            self._refresh_position()
            self.var_status.set("Motors: Move Complete ✓")
            
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid numeric coordinates.")
        except Exception as exc:
            self.var_status.set("Motors: Move Failed")
            messagebox.showerror("Movement Error", f"Failed to move to position:\n{exc}")

    def _on_canvas_click(self, event: tk.Event) -> None:  # type: ignore
        """Handle canvas click to move to position."""
        if not self._is_connected():
            messagebox.showwarning("Not Connected", "Please connect to motors first.")
            return
        
        xw, yw = self._canvas_to_world(event.x, event.y)
        
        # Clamp to valid range
        xw = max(0.0, min(self.world_range, xw))
        yw = max(0.0, min(self.world_range, yw))
        
        try:
            self.var_status.set(f"Motors: Moving to ({xw:.2f}, {yw:.2f})...")
            self.root.update()
            self.motor.move_to_target(xw, yw, self.var_status_x, self.var_status_y)  # type: ignore
            self._refresh_position()
            self.var_status.set("Motors: Move Complete ✓")
        except Exception as exc:
            self.var_status.set("Motors: Move Failed")
            messagebox.showerror("Movement Error", f"Failed to move to clicked position:\n{exc}")

    def _on_canvas_hover(self, event: tk.Event) -> None:  # type: ignore
        """Update coordinate display on canvas hover."""
        xw, yw = self._canvas_to_world(event.x, event.y)
        self.canvas.itemconfig(
            self.canvas_coord_text,
            text=f"Cursor: X={xw:.2f} mm, Y={yw:.2f} mm"
        )

    def _apply_motor_settings(self) -> None:
        """Apply velocity and acceleration settings to motors."""
        if not self._is_connected():
            return
        
        try:
            velocity = float(self.var_velocity.get())
            acceleration = float(self.var_acceleration.get())
            
            if velocity <= 0 or acceleration <= 0:
                raise ValueError("Values must be positive")
            
            self.motor.set_velocity_and_acceleration(velocity, acceleration)  # type: ignore
            messagebox.showinfo("Settings Applied", f"Velocity: {velocity} mm/s\nAcceleration: {acceleration} mm/s²")
            
        except ValueError as e:
            messagebox.showerror("Invalid Settings", f"Please enter valid positive numbers.\n{e}")
            # Reset to defaults
            self.var_velocity.set(str(config.MAX_VELOCITY))
            self.var_acceleration.set(str(config.MAX_ACCELERATION))

    def _refresh_position(self) -> None:
        """Refresh current position display."""
        try:
            if not self._is_connected():
                self.var_position.set("X: --, Y: --")
                return
            
            x = self.motor.get_position_x()  # type: ignore
            y = self.motor.get_position_y()  # type: ignore
            
            if x is not None and y is not None:
                self.current_x = float(x)
                self.current_y = float(y)
                self.var_position.set(f"X: {self.current_x:.2f} mm, Y: {self.current_y:.2f} mm")
                self.var_goto_x.set(f"{self.current_x:.2f}")
                self.var_goto_y.set(f"{self.current_y:.2f}")
                self._update_laser_marker()
            else:
                self.var_position.set("X: --, Y: --")
                
        except Exception as exc:
            print(f"Error refreshing position: {exc}")

    def _is_connected(self) -> bool:
        """Check if motors are connected."""
        try:
            return (self.motor is not None and 
                   (getattr(self.motor, "motor_x", None) is not None or 
                    getattr(self.motor, "motor_y", None) is not None))
        except Exception:
            return False

    # ---------- Position Presets ----------
    def _load_presets(self) -> None:
        """Load position presets from file."""
        try:
            if self.presets_file.exists():
                with open(self.presets_file, 'r') as f:
                    data = json.load(f)
                    self.presets = {k: tuple(v) for k, v in data.items()}  # type: ignore
        except Exception as e:
            print(f"Error loading presets: {e}")
            self.presets = {}

    def _save_presets(self) -> None:
        """Save position presets to file."""
        try:
            with open(self.presets_file, 'w') as f:
                json.dump(self.presets, f, indent=2)
        except Exception as e:
            print(f"Error saving presets: {e}")

    def _update_presets_list(self) -> None:
        """Update the presets listbox display."""
        if hasattr(self, 'presets_listbox'):
            self.presets_listbox.delete(0, tk.END)
            for name, (x, y) in sorted(self.presets.items()):
                self.presets_listbox.insert(tk.END, f"{name}: ({x:.2f}, {y:.2f})")

    def _save_preset(self) -> None:
        """Save current position as a preset."""
        if not self._is_connected():
            messagebox.showwarning("Not Connected", "Please connect to motors first.")
            return
        
        name = simpledialog.askstring("Save Preset", "Enter preset name:")
        if name:
            self.presets[name] = (self.current_x, self.current_y)
            self._save_presets()
            self._update_presets_list()
            messagebox.showinfo("Preset Saved", f"Position saved as '{name}'")

    def _goto_preset(self) -> None:
        """Move to selected preset position."""
        if not self._is_connected():
            messagebox.showwarning("Not Connected", "Please connect to motors first.")
            return
        
        selection = self.presets_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a preset first.")
            return
        
        selected_text = self.presets_listbox.get(selection[0])
        name = selected_text.split(":")[0]
        
        if name in self.presets:
            x, y = self.presets[name]
            try:
                self.var_status.set(f"Motors: Moving to preset '{name}'...")
                self.root.update()
                self.motor.move_to_target(x, y, self.var_status_x, self.var_status_y)  # type: ignore
                self._refresh_position()
                self.var_status.set(f"Motors: At preset '{name}' ✓")
            except Exception as exc:
                self.var_status.set("Motors: Move Failed")
                messagebox.showerror("Movement Error", f"Failed to move to preset:\n{exc}")

    def _delete_preset(self) -> None:
        """Delete selected preset."""
        selection = self.presets_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a preset to delete.")
            return
        
        selected_text = self.presets_listbox.get(selection[0])
        name = selected_text.split(":")[0]
        
        if name in self.presets:
            if messagebox.askyesno("Confirm Delete", f"Delete preset '{name}'?"):
                del self.presets[name]
                self._save_presets()
                self._update_presets_list()

    # ---------- Scanning ----------
    def _start_scan(self) -> None:
        """Start raster scan."""
        if not self._is_connected():
            messagebox.showwarning("Not Connected", "Please connect to motors first.")
            return
        
        try:
            dx = float(self.var_scan_x.get())
            dy = float(self.var_scan_y.get())
            count = int(self.var_scan_count.get())
            direction = self.var_scan_direction.get()
            
            if count <= 0:
                raise ValueError("Raster count must be positive")
            
            result = messagebox.askyesno(
                "Start Scan",
                f"Start {direction} raster scan?\n"
                f"X distance: {dx} mm\n"
                f"Y distance: {dy} mm\n"
                f"Raster count: {count}"
            )
            
            if result:
                self.var_status.set("Motors: Scanning...")
                self.root.update()
                self.motor.raster_scan(dx, dy, count, direction, self.var_status_x, self.var_status_y)  # type: ignore
                self._refresh_position()
                self.var_status.set("Motors: Scan Complete ✓")
                
        except ValueError as e:
            messagebox.showerror("Invalid Input", f"Please enter valid scan parameters.\n{e}")
        except Exception as exc:
            self.var_status.set("Motors: Scan Failed")
            messagebox.showerror("Scan Error", f"Failed to complete scan:\n{exc}")

    # ---------- Function Generator Controls ----------
    def _on_fg_addr_selected(self, event=None) -> None:
        """Handle function generator address selection from dropdown."""
        selected = self.fg_addr_combo.get()
        if selected and selected != "Custom...":
            self.var_fg_addr.set(selected)
    
    def _on_laser_config_selected(self, event=None) -> None:
        """Handle laser configuration selection from dropdown."""
        selected = self.laser_config_combo.get()
        if selected and selected != "Custom...":
            # Parse the selection (format: "COM4 @ 38400 baud")
            try:
                parts = selected.split(" @ ")
                port = parts[0]
                baud = parts[1].replace(" baud", "")
                self.var_laser_port.set(port)
                self.var_laser_baud.set(baud)
            except Exception:
                pass  # If parsing fails, leave as custom
    
    def _auto_detect_fg(self) -> None:
        """Auto-detect function generator VISA address."""
        if FunctionGeneratorManager is None:
            messagebox.showerror(
                "Function Generator",
                "pyvisa is not installed, so auto-detect is unavailable.",
            )
            return
        try:
            import pyvisa
            rm = pyvisa.ResourceManager()
            resources = rm.list_resources()
            
            # Filter for likely function generators
            fg_resources = [r for r in resources if 'USB' in r or 'TCPIP' in r]
            
            if fg_resources:
                if len(fg_resources) == 1:
                    self.var_fg_addr.set(fg_resources[0])
                    messagebox.showinfo("Device Found", f"Found device:\n{fg_resources[0]}")
                else:
                    # Show selection dialog
                    selection = simpledialog.askstring(
                        "Multiple Devices",
                        f"Found {len(fg_resources)} devices.\nEnter number (0-{len(fg_resources)-1}):\n" +
                        "\n".join(f"{i}: {r}" for i, r in enumerate(fg_resources))
                    )
                    if selection is not None:
                        try:
                            idx = int(selection)
                            if 0 <= idx < len(fg_resources):
                                self.var_fg_addr.set(fg_resources[idx])
                        except ValueError:
                            pass
            else:
                messagebox.showinfo("No Devices", "No VISA devices found.")
                
        except Exception as e:
            messagebox.showerror("Auto-detect Error", f"Failed to detect devices:\n{e}")

    def _on_fg_connect(self) -> None:
        """Connect to function generator."""
        if FunctionGeneratorManager is None:
            detail = "pyvisa is not installed, so function generator control is disabled."
            if _FG_IMPORT_ERROR:
                detail += f"\nOriginal import error: {_FG_IMPORT_ERROR}"
            messagebox.showerror("Function Generator", detail)
            return
        try:
            addr = self.var_fg_addr.get().strip()
            if not addr:
                messagebox.showwarning("No Address", "Please enter a VISA address.")
                return
            
            self.var_fg_status.set("FG: Connecting...")
            self.root.update()
            
            self.fg_mgr = FunctionGeneratorManager(
                fg_type="Siglent SDG1032X",
                address=addr,
                auto_connect=True
            )
            
            if self.fg_mgr.is_connected():
                self.var_fg_status.set("FG: Connected ✓")
                # Read current output status
                try:
                    out_on = bool(self.fg_mgr.get_output_status(1))
                    self.var_fg_enabled.set(out_on)
                except Exception:
                    pass
                # Apply current voltage setting
                self._on_apply_amplitude()
            else:
                self.var_fg_status.set("FG: Connection Failed")
                messagebox.showerror("Connection Failed", "Could not connect to function generator.")
                
        except Exception as exc:
            self.var_fg_status.set("FG: Error")
            messagebox.showerror("Connection Error", f"Failed to connect:\n{exc}")

    def _on_fg_disconnect(self) -> None:
        """Disconnect from function generator."""
        try:
            if self.fg_mgr is not None:
                try:
                    self.fg_mgr.close()
                except Exception:
                    pass
                self.fg_mgr = None
            self.var_fg_enabled.set(False)
            self.var_fg_status.set("FG: Disconnected")
        except Exception as exc:
            messagebox.showerror("Disconnect Error", f"Error during disconnect:\n{exc}")

    def _on_fg_toggle(self) -> None:
        """Toggle function generator output."""
        try:
            desired = bool(self.var_fg_enabled.get())
            
            if self.fg_mgr is not None and self.fg_mgr.is_connected():
                self.fg_mgr.output(1, desired)
                status = "ON" if desired else "OFF"
                self.var_fg_status.set(f"FG: Output {status}")
            elif self.fg is not None:
                self.fg.set_output(desired)
                status = "ON" if desired else "OFF"
                self.var_fg_status.set(f"FG: Output {status}")
            else:
                self.var_fg_enabled.set(not desired)
                messagebox.showwarning("Not Connected", "Please connect to function generator first.")
                
        except Exception as exc:
            messagebox.showerror("FG Error", f"Failed to toggle output:\n{exc}")

    def _on_apply_amplitude(self) -> None:
        """Apply DC voltage setting."""
        try:
            volts = float(self.var_fg_amplitude.get())
            
            if self.fg_mgr is not None and self.fg_mgr.is_connected():
                self.fg_mgr.set_dc_level(1, volts)
                self.var_fg_status.set(f"FG: DC {volts:.3f} V applied")
            elif self.fg is not None and hasattr(self.fg, "set_amplitude"):
                self.fg.set_amplitude(volts)
                self.var_fg_status.set(f"FG: {volts:.3f} V applied")
            else:
                messagebox.showwarning("Not Connected", "Please connect to function generator first.")
                
        except ValueError:
            messagebox.showerror("Invalid Value", "Please enter a valid voltage value.")
        except Exception as exc:
            messagebox.showerror("FG Error", f"Failed to apply voltage:\n{exc}")

    # ---------- Laser Controller Controls ----------
    def _set_laser_analog_modulation_mode(self, power_mw: float = 100.0) -> None:
        """Set laser to analog modulation mode for manual control via front panel.
        
        This is the standard state the laser should be left in:
        - AM 1: Analog modulation ON (allows front panel wheel control)
        - DM 0: Digital modulation OFF
        - APC 1: Automatic power control ON (constant power mode)
        - Power: Set to specified value (default 100 mW)
        - Emission: Should remain ON
        
        The analog modulation controls a percentage of the set power value.
        Setting power to 100 mW means the front panel wheel can control
        0-100% of 100 mW (0-100 mW range).
        
        This is the default state that allows manual control via the control box.
        
        Args:
            power_mw: Power level in mW (default: 100 mW)
        """
        print(f"[LASER] _set_laser_analog_modulation_mode called with power_mw={power_mw}")
        if not self.laser_mgr:
            print("[LASER] ERROR: laser_mgr is None")
            return
        
        try:
            if not self.laser_mgr:
                print("[LASER] ERROR: laser_mgr is None in _set_laser_analog_modulation_mode")
                return
            
            laser = self.laser_mgr.instrument
            print(f"[LASER] Got instrument: {laser}")
            print(f"[LASER] Instrument type: {type(laser)}")
            
            # Check if serial connection is open
            if hasattr(laser, 'ser'):
                print(f"[LASER] Serial port object: {laser.ser}")
                if laser.ser:
                    print(f"[LASER] Serial port name: {laser.ser.port}")
                    print(f"[LASER] Serial is_open: {laser.ser.is_open}")
                    if not laser.ser.is_open:
                        print("[LASER] WARNING: Serial port is not open!")
                else:
                    print("[LASER] WARNING: Serial port object is None!")
            
            # Use the new method if available, otherwise fall back to manual commands
            if hasattr(laser, 'set_to_analog_modulation_mode'):
                print("[LASER] Using set_to_analog_modulation_mode method")
                try:
                    result = laser.set_to_analog_modulation_mode(power_mw=power_mw)
                    print(f"[LASER] set_to_analog_modulation_mode result: {result}")
                except Exception as e:
                    print(f"[LASER] ERROR calling set_to_analog_modulation_mode: {e}")
                    import traceback
                    traceback.print_exc()
                    raise
            else:
                print("[LASER] Using manual commands (fallback)")
                # Fallback: manual commands
                print("[LASER] Sending APC 1...")
                try:
                    result = laser.send_command("APC 1")
                    print(f"[LASER] APC 1 response: {result}")
                except Exception as e:
                    print(f"[LASER] ERROR sending APC 1: {e}")
                    raise
                time.sleep(0.1)
                print("[LASER] Sending AM 1...")
                try:
                    result = laser.send_command("AM 1")
                    print(f"[LASER] AM 1 response: {result}")
                except Exception as e:
                    print(f"[LASER] ERROR sending AM 1: {e}")
                    raise
                time.sleep(0.1)
                print("[LASER] Sending DM 0...")
                try:
                    result = laser.send_command("DM 0")
                    print(f"[LASER] DM 0 response: {result}")
                except Exception as e:
                    print(f"[LASER] ERROR sending DM 0: {e}")
                    raise
                time.sleep(0.1)
                print(f"[LASER] Setting power to {power_mw} mW...")
                try:
                    result = laser.set_power(power_mw)
                    print(f"[LASER] set_power response: {result}")
                except Exception as e:
                    print(f"[LASER] ERROR setting power: {e}")
                    raise
                time.sleep(0.1)
            print("[LASER] Analog modulation mode set successfully")
        except Exception as e:
            print(f"[LASER] ERROR: Could not set laser to analog modulation mode: {e}")
            import traceback
            traceback.print_exc()
    
    def _on_laser_connect(self) -> None:
        """Connect to laser controller."""
        print("[LASER] Connect button clicked")
        if LaserManager is None:
            detail = "pyserial is not installed, so laser control is disabled."
            if _LASER_IMPORT_ERROR:
                detail += f"\nOriginal import error: {_LASER_IMPORT_ERROR}"
            print(f"[LASER] ERROR: {detail}")
            messagebox.showerror("Laser Controller", detail)
            return
        try:
            port = self.var_laser_port.get().strip()
            baud_str = self.var_laser_baud.get().strip()
            print(f"[LASER] Attempting connection: port={port}, baud={baud_str}")
            
            if not port:
                print("[LASER] ERROR: No port specified")
                messagebox.showwarning("No Port", "Please enter a COM port.")
                return
            
            try:
                baud = int(baud_str)
            except ValueError:
                print(f"[LASER] ERROR: Invalid baud rate: {baud_str}")
                messagebox.showwarning("Invalid Baud", "Please enter a valid baud rate.")
                return
            
            self.var_laser_status.set("Laser: Connecting...")
            self.root.update()
            
            # Create laser manager with config
            cfg = {
                "driver": "Oxxius",
                "address": port,
                "baud": baud
            }
            print(f"[LASER] Creating LaserManager with config: {cfg}")
            print(f"[LASER] LaserManager class: {LaserManager}")
            print(f"[LASER] LaserManager.from_config method: {LaserManager.from_config}")
            
            try:
                self.laser_mgr = LaserManager.from_config(cfg)
                print(f"[LASER] LaserManager created successfully: {self.laser_mgr}")
                print(f"[LASER] LaserManager type: {type(self.laser_mgr)}")
                print(f"[LASER] LaserManager has instrument attribute: {hasattr(self.laser_mgr, 'instrument')}")
            except Exception as e:
                print(f"[LASER] ERROR creating LaserManager: {e}")
                import traceback
                traceback.print_exc()
                raise
            
            # Test connection by querying ID
            try:
                laser = self.laser_mgr.instrument
                print(f"[LASER] Got instrument: {laser}")
                print(f"[LASER] Instrument type: {type(laser)}")
                print(f"[LASER] Instrument has idn method: {hasattr(laser, 'idn')}")
                print(f"[LASER] Instrument has send_command method: {hasattr(laser, 'send_command')}")
                print(f"[LASER] Instrument has ser attribute: {hasattr(laser, 'ser')}")
                if hasattr(laser, 'ser'):
                    print(f"[LASER] Serial port: {laser.ser.port if laser.ser else 'None'}")
                    print(f"[LASER] Serial is_open: {laser.ser.is_open if laser.ser else 'N/A'}")
                
                print("[LASER] Querying laser ID...")
                idn = laser.idn()
                print(f"[LASER] Laser ID response: {idn}")
                print(f"[LASER] Laser ID type: {type(idn)}")
                self.var_laser_status.set(f"Laser: Connected ✓ ({idn[:30]})")
                print("[LASER] Connection successful - laser ready (not setting analog modulation until emission is on)")
                
                # Read current power if available
                try:
                    print("[LASER] Reading current power...")
                    power_str = laser.get_power()
                    print(f"[LASER] Power response: {power_str}")
                    # Try to extract numeric value from response
                    import re
                    power_match = re.search(r'[\d.]+', power_str)
                    if power_match:
                        power_val = float(power_match.group())
                        print(f"[LASER] Extracted power: {power_val}")
                        # Only update entry field if laser has a valid non-zero power
                        # Don't overwrite user's desired power with 0.0
                        if power_val > 0:
                            self.var_laser_power.set(str(power_val))
                        else:
                            print("[LASER] Laser power is 0.0 - keeping entry field value")
                except Exception as e:
                    print(f"[LASER] Warning: Could not read power: {e}")
                    pass
                print("[LASER] Connection successful!")
            except Exception as e:
                print(f"[LASER] ERROR: Connection test failed: {e}")
                import traceback
                traceback.print_exc()
                self.var_laser_status.set("Laser: Connection Failed")
                messagebox.showerror("Connection Failed", f"Could not communicate with laser:\n{e}")
                self.laser_mgr = None
                
        except Exception as exc:
            print(f"[LASER] ERROR: Exception during connect: {exc}")
            import traceback
            traceback.print_exc()
            self.var_laser_status.set("Laser: Error")
            messagebox.showerror("Connection Error", f"Failed to connect:\n{exc}")
            self.laser_mgr = None

    def _on_laser_disconnect(self) -> None:
        """Disconnect from laser controller and restore to analog modulation mode.
        
        This is called when user clicks Disconnect or when GUI closes.
        Standard final state:
        - Emission: ON
        - Analog modulation: ON (AM 1)
        - Power: 100 mW
        - This allows manual control via front panel wheel
        """
        print("[LASER] ===== DISCONNECT - Restoring to manual control mode =====")
        try:
            if self.laser_mgr is not None:
                laser = self.laser_mgr.instrument
                print(f"[LASER] Got instrument: {laser}")
                try:
                    # Ensure emission is ON (required for proper operation)
                    print("[LASER] Ensuring emission is ON...")
                    result = laser.emission_on()
                    print(f"[LASER] emission_on response: {result}")
                    time.sleep(0.1)
                except Exception as e:
                    print(f"[LASER] Warning: Could not set emission ON: {e}")
                    pass
                try:
                    # Restore to analog modulation mode with 100 mW for manual control
                    # This ensures the laser can be controlled via front panel after disconnect
                    print("[LASER] Restoring to analog modulation mode with 100 mW...")
                    self._set_laser_analog_modulation_mode(power_mw=100.0)
                    print("[LASER] Analog modulation mode restored")
                except Exception as e:
                    print(f"[LASER] Warning: Could not restore analog modulation mode: {e}")
                    pass
                try:
                    # Use the close method which automatically restores to manual control
                    # restore_to_manual_control=True ensures proper final state
                    print("[LASER] Closing connection...")
                    laser.close(restore_to_manual_control=True)
                    print("[LASER] Connection closed")
                except Exception as e:
                    print(f"[LASER] Warning: Error during close: {e}")
                    pass
                self.laser_mgr = None
                print("[LASER] laser_mgr set to None")
            else:
                print("[LASER] laser_mgr is None - nothing to disconnect")
            self.var_laser_enabled.set(False)
            self.var_laser_status.set("Laser: Disconnected (restored to manual control)")
            print("[LASER] Disconnect complete - laser ready for manual control")
        except Exception as exc:
            print(f"[LASER] ERROR: Exception during disconnect: {exc}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("Disconnect Error", f"Error during disconnect:\n{exc}")

    def _on_laser_toggle(self) -> None:
        """Toggle laser emission following proper sequence.
        
        When turning ON:
        1. Set to power control mode (APC 1)
        2. Set to digital control (AM 0, DM 0)
        3. Set power to current value
        4. Turn emission ON
        5. Wait 2 seconds
        6. Enable analog modulation (AM 1)
        
        When turning OFF (proper shutdown):
        1. Set to analog modulation mode (AM 1)
        2. Set power to 100 mW
        3. Keep emission ON (do NOT disable - causes issues)
        """
        print("[LASER] ========== Emission toggle clicked ==========")
        try:
            # Simple approach: toggle based on previous state
            # If it was OFF, turn it ON. If it was ON, turn it OFF.
            previous_state = self._laser_emission_previous_state
            want_on = not previous_state  # Toggle: if was OFF, want ON; if was ON, want OFF
            
            print(f"[LASER] Previous state: {previous_state}")
            print(f"[LASER] User wants: {'ON' if want_on else 'OFF'}")
            
            if self.laser_mgr is not None:
                laser = self.laser_mgr.instrument
                print(f"[LASER] Got instrument: {laser}")
                
                if want_on:
                    # Checkbox is CHECKED - user wants to turn laser ON
                    print("[LASER] ===== TURNING LASER ON =====")
                    # Turning ON - follow proper sequence
                    print("[LASER] Turning ON - starting sequence...")
                    self.var_laser_status.set("Laser: Initializing...")
                    self.root.update()
                    
                    # Step 1: Set to power control mode
                    print("[LASER] Step 1: Setting to power control mode (APC 1)...")
                    result = laser.send_command("APC 1")
                    print(f"[LASER] APC 1 response: {result}")
                    time.sleep(0.1)
                    
                    # Step 2: Set to digital control (AM 0, DM 0)
                    print("[LASER] Step 2: Setting to digital control (AM 0, DM 0)...")
                    result = laser.send_command("AM 0")
                    print(f"[LASER] AM 0 response: {result}")
                    time.sleep(0.1)
                    result = laser.send_command("DM 0")
                    print(f"[LASER] DM 0 response: {result}")
                    time.sleep(0.1)
                    
                    # Step 3: Set power to current value (or default to 10.0 if 0.0 or invalid)
                    try:
                        power_str = self.var_laser_power.get().strip()
                        if not power_str or power_str == "0" or power_str == "0.0":
                            print("[LASER] Power entry is 0.0 or empty - using default 10.0 mW")
                            power = 10.0
                            self.var_laser_power.set("10.0")
                        else:
                            power = float(power_str)
                        print(f"[LASER] Step 3: Setting power to {power} mW...")
                        result = laser.set_power(power)
                        print(f"[LASER] set_power response: {result}")
                        time.sleep(0.1)
                    except ValueError as e:
                        print(f"[LASER] ERROR: Invalid power value: {e}, using default 10.0 mW")
                        power = 10.0
                        self.var_laser_power.set("10.0")
                        result = laser.set_power(power)
                        print(f"[LASER] set_power response: {result}")
                        time.sleep(0.1)
                    
                    # Step 4: Turn emission ON
                    print("[LASER] Step 4: Turning emission ON...")
                    result = laser.emission_on()
                    print(f"[LASER] emission_on response: {result}")
                    self.var_laser_status.set("Laser: Emission ON...")
                    self.root.update()
                    
                    # NOTE: Do NOT enable analog modulation while emission is ON
                    # Analog modulation will be enabled when emission is turned OFF
                    
                    # Query actual power reading
                    try:
                        print("[LASER] Querying actual power reading...")
                        power_str = laser.get_power()
                        print(f"[LASER] Power query response: {power_str}")
                        import re
                        power_match = re.search(r'[\d.]+', power_str)
                        if power_match:
                            actual_power = power_match.group()
                            print(f"[LASER] Actual power reading: {actual_power} mW")
                            set_power = self.var_laser_power.get()
                            self.var_laser_status.set(f"Laser: Emission ON (set: {set_power} mW, actual: {actual_power} mW)")
                        else:
                            set_power = self.var_laser_power.get()
                            self.var_laser_status.set(f"Laser: Emission ON (set: {set_power} mW)")
                    except Exception as e:
                        print(f"[LASER] Warning: Could not query actual power: {e}")
                        set_power = self.var_laser_power.get()
                        self.var_laser_status.set(f"Laser: Emission ON (set: {set_power} mW)")
                    
                    print("[LASER] Turn ON sequence complete!")
                    # Update state tracking
                    self._laser_emission_previous_state = True
                    # Ensure checkbox reflects the state
                    self.var_laser_enabled.set(True)
                    
                else:
                    # User wants emission OFF (previous was True, new is False)
                    print("[LASER] ===== TURNING EMISSION OFF =====")
                    
                    try:
                        # Turn emission OFF first
                        print("[LASER] Step 1: Turning emission OFF...")
                        result = laser.emission_off()
                        print(f"[LASER] emission_off response: {result}")
                        time.sleep(0.1)
                        
                        # Now enable analog modulation (only when emission is OFF)
                        print("[LASER] Step 2: Enabling analog modulation (AM 1)...")
                        result = laser.send_command("AM 1")
                        print(f"[LASER] AM 1 response: {result}")
                        time.sleep(0.1)
                        
                        # Set power to 100 mW for manual control
                        print("[LASER] Step 3: Setting power to 100 mW for manual control...")
                        result = laser.set_power(100.0)
                        print(f"[LASER] set_power response: {result}")
                        time.sleep(0.1)
                        
                        self.var_laser_status.set("Laser: Emission OFF (ready for manual control)")
                        # Update state tracking
                        self._laser_emission_previous_state = False
                        # Ensure checkbox reflects the state
                        self.var_laser_enabled.set(False)
                        print("[LASER] Emission turned OFF and analog modulation enabled successfully")
                    except Exception as e:
                        print(f"[LASER] ERROR: Could not turn emission off: {e}")
                        import traceback
                        traceback.print_exc()
                        # Revert checkbox if error
                        self.var_laser_enabled.set(True)
                        self._laser_emission_previous_state = True
                        messagebox.showerror("Laser Error", f"Failed to turn emission off:\n{e}")
                    
            else:
                print("[LASER] ERROR: laser_mgr is None - not connected")
                # Revert checkbox state since we can't connect
                self.var_laser_enabled.set(False)
                self._laser_emission_previous_state = False
                messagebox.showwarning("Not Connected", "Please connect to laser first.")
                
        except Exception as exc:
            print(f"[LASER] ERROR: Exception during toggle: {exc}")
            import traceback
            traceback.print_exc()
            # Revert checkbox state on error - go back to previous state
            self.var_laser_enabled.set(self._laser_emission_previous_state)
            messagebox.showerror("Laser Error", f"Failed to toggle emission:\n{exc}")

    def _increase_laser_power(self) -> None:
        """Increase laser power by 5 mW and apply immediately if laser is on."""
        print("[LASER] Increase power button clicked")
        try:
            current_power = float(self.var_laser_power.get())
            new_power = current_power + 5.0
            print(f"[LASER] Increasing power: {current_power} -> {new_power} mW")
            self.var_laser_power.set(f"{new_power:.1f}")
            # Auto-apply if laser is on
            if self.laser_mgr is not None and self.var_laser_enabled.get():
                print("[LASER] Laser is on - auto-applying power change")
                self._on_apply_laser_power()
            else:
                print("[LASER] Laser is off - power value updated but not applied")
        except ValueError as e:
            print(f"[LASER] ERROR: Invalid power value: {e}")
            self.var_laser_power.set("5.0")
    
    def _decrease_laser_power(self) -> None:
        """Decrease laser power by 5 mW and apply immediately if laser is on."""
        print("[LASER] Decrease power button clicked")
        try:
            current_power = float(self.var_laser_power.get())
            new_power = max(0.0, current_power - 5.0)  # Don't go below 0
            print(f"[LASER] Decreasing power: {current_power} -> {new_power} mW")
            self.var_laser_power.set(f"{new_power:.1f}")
            # Auto-apply if laser is on
            if self.laser_mgr is not None and self.var_laser_enabled.get():
                print("[LASER] Laser is on - auto-applying power change")
                self._on_apply_laser_power()
            else:
                print("[LASER] Laser is off - power value updated but not applied")
        except ValueError as e:
            print(f"[LASER] ERROR: Invalid power value: {e}")
            self.var_laser_power.set("0.0")
    
    def _on_apply_laser_power(self) -> None:
        """Apply laser power setting.
        
        This method allows adjusting power while the laser is on.
        The power can be increased or decreased as needed.
        
        When analog modulation is enabled (AM 1):
        - The set power becomes the MAXIMUM
        - Front panel wheel controls 0-100% of this maximum
        - Example: 100 mW with AM 1 = wheel controls 0-100 mW
        
        When analog modulation is disabled (AM 0):
        - The set power is absolute
        - Example: 50 mW with AM 0 = exactly 50 mW
        """
        print("[LASER] Apply power button clicked")
        try:
            power_str = self.var_laser_power.get().strip()
            if not power_str or power_str == "0" or power_str == "0.0":
                print("[LASER] WARNING: Power is 0.0 or empty - using default 10.0 mW")
                power = 10.0
                self.var_laser_power.set("10.0")
            else:
                power = float(power_str)
            print(f"[LASER] Requested power: {power} mW")
            
            if power < 0:
                print("[LASER] ERROR: Power must be non-negative")
                raise ValueError("Power must be non-negative")
            
            if self.laser_mgr is not None:
                laser = self.laser_mgr.instrument
                print(f"[LASER] Got instrument: {laser}")
                
                # Check if emission is currently on
                emission_on = self.var_laser_enabled.get()
                print(f"[LASER] Emission currently: {'ON' if emission_on else 'OFF'}")
                
                if emission_on:
                    # Laser is on - can adjust power directly
                    print("[LASER] Laser is ON - applying power directly...")
                    # Ensure we're in power control mode
                    try:
                        print("[LASER] Ensuring power control mode (APC 1)...")
                        result = laser.send_command("APC 1")
                        print(f"[LASER] APC 1 response: {result}")
                        time.sleep(0.05)
                    except Exception as e:
                        print(f"[LASER] Warning: Could not set APC 1: {e}")
                        pass
                    
                    # Set power (works with both AM 0 and AM 1)
                    print(f"[LASER] Setting power to {power} mW...")
                    result = laser.set_power(power)
                    print(f"[LASER] set_power response: {result}")
                    time.sleep(0.1)  # Small delay before querying
                    
                    # Query actual power reading
                    try:
                        print("[LASER] Querying actual power reading...")
                        power_str = laser.get_power()
                        print(f"[LASER] Power query response: {power_str}")
                        import re
                        power_match = re.search(r'[\d.]+', power_str)
                        if power_match:
                            actual_power = power_match.group()
                            print(f"[LASER] Actual power reading: {actual_power} mW")
                            self.var_laser_status.set(f"Laser: Power set to {power:.2f} mW (actual: {actual_power} mW)")
                        else:
                            print("[LASER] Could not extract power from response")
                            self.var_laser_status.set(f"Laser: Power set to {power:.2f} mW")
                    except Exception as e:
                        print(f"[LASER] Warning: Could not query actual power: {e}")
                        self.var_laser_status.set(f"Laser: Power set to {power:.2f} mW")
                    print("[LASER] Power applied successfully!")
                else:
                    # Laser is off - just set the power value for when it's turned on
                    print("[LASER] Laser is OFF - storing power value for next turn-on")
                    # Don't actually send command to laser yet
                    self.var_laser_status.set(f"Laser: Power will be set to {power:.2f} mW when turned on")
                    
            else:
                print("[LASER] ERROR: laser_mgr is None - not connected")
                messagebox.showwarning("Not Connected", "Please connect to laser first.")
                
        except ValueError as e:
            print(f"[LASER] ERROR: Invalid power value: {e}")
            messagebox.showerror("Invalid Value", "Please enter a valid power value (mW).")
        except Exception as exc:
            print(f"[LASER] ERROR: Exception during apply power: {exc}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("Laser Error", f"Failed to set power:\n{exc}")

    def _show_help(self) -> None:
        """Display a help window with usage instructions."""
        help_win = tk.Toplevel(self.root)
        help_win.title("Motor Control Guide")
        help_win.geometry("800x700")
        help_win.configure(bg=self.COLORS['bg_dark'])
        
        # Scrollable Content
        canvas = tk.Canvas(help_win, bg="#f0f0f0")
        scrollbar = ttk.Scrollbar(help_win, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Content
        pad = {'padx': 20, 'pady': 10, 'anchor': 'w'}
        
        tk.Label(scrollable_frame, text="Motor Control & Laser Positioning Guide", 
                font=("Segoe UI", 16, "bold"), bg="#f0f0f0", fg="#1565c0").pack(**pad)
        
        tk.Label(scrollable_frame, text="1. Overview", font=("Segoe UI", 12, "bold"), 
                bg="#f0f0f0").pack(**pad)
        tk.Label(scrollable_frame, 
                text="This GUI provides comprehensive control over XY stage motors for laser positioning.\n"
                      "It combines motor control, laser power management, and visual feedback.",
                justify="left", bg="#f0f0f0").pack(**pad)
        
        tk.Label(scrollable_frame, text="2. Getting Started", font=("Segoe UI", 12, "bold"), 
                bg="#f0f0f0").pack(**pad)
        tk.Label(scrollable_frame,
                text="• Click 'Connect Motors' to establish connection\n"
                      "• Use the interactive canvas to click-to-move\n"
                      "• Use jog controls for precise positioning\n"
                      "• Set velocity and acceleration in Motor Settings\n"
                      "• Save positions as presets for quick access",
                justify="left", bg="#f0f0f0").pack(**pad)
        
        tk.Label(scrollable_frame, text="3. Features", font=("Segoe UI", 12, "bold"), 
                bg="#f0f0f0").pack(**pad)
        tk.Label(scrollable_frame,
                text="• Interactive Canvas: Click anywhere to move laser\n"
                      "• Jog Controls: Arrow buttons for fine positioning\n"
                      "• Go-To Position: Enter exact coordinates\n"
                      "• Presets: Save and recall favorite positions\n"
                      "• Scanning: Automated raster scan patterns\n"
                      "• Function Generator: Control laser power/amplitude",
                justify="left", bg="#f0f0f0").pack(**pad)
        
        tk.Label(scrollable_frame, text="4. Keyboard Shortcuts", font=("Segoe UI", 12, "bold"), 
                bg="#f0f0f0").pack(**pad)
        tk.Label(scrollable_frame,
                text="• Arrow Keys: Jog motors\n"
                      "• H: Home position\n"
                      "• G: Go to position dialog\n"
                      "• S: Save current position as preset\n"
                      "• Ctrl+Q: Quit application",
                justify="left", bg="#f0f0f0").pack(**pad)
        
        tk.Label(scrollable_frame, text="Video Tutorial", font=("Segoe UI", 12, "bold"), 
                bg="#f0f0f0", fg="#d32f2f").pack(**pad)
        tk.Label(scrollable_frame,
                text="Video tutorials and additional resources will be added here.",
                justify="left", bg="#f0f0f0", fg="#666").pack(**pad)
    
    # ---------- Keyboard Shortcuts ----------
    def _setup_keyboard_shortcuts(self) -> None:
        """Setup keyboard shortcuts for common operations."""
        self.root.bind('<Up>', lambda e: self._on_jog('y', +1) if self._is_connected() else None)
        self.root.bind('<Down>', lambda e: self._on_jog('y', -1) if self._is_connected() else None)
        self.root.bind('<Left>', lambda e: self._on_jog('x', -1) if self._is_connected() else None)
        self.root.bind('<Right>', lambda e: self._on_jog('x', +1) if self._is_connected() else None)
        self.root.bind('h', lambda e: self._on_home())
        self.root.bind('H', lambda e: self._on_home())
        self.root.bind('g', lambda e: self._on_goto())
        self.root.bind('G', lambda e: self._on_goto())
        self.root.bind('s', lambda e: self._save_preset())
        self.root.bind('S', lambda e: self._save_preset())
        self.root.bind('<Control-q>', lambda e: self.root.quit())

    # ---------- Camera Feed Methods ----------
    def _update_camera_mode_ui(self) -> None:
        """Update UI based on selected camera mode."""
        if not hasattr(self, 'camera_mode_var'):
            return
        
        mode = self.camera_mode_var.get()
        if mode == "IP Stream":
            self.ip_frame.pack(side=tk.TOP, fill=tk.X, pady=5)
            self.usb_frame.pack_forget()
        else:  # USB Camera
            self.usb_frame.pack(side=tk.TOP, fill=tk.X, pady=5)
            self.ip_frame.pack_forget()
    
    def _start_camera_feed(self) -> None:
        """Start camera feed (IP stream or USB camera)."""
        if not CAMERA_AVAILABLE:
            messagebox.showerror("Camera Unavailable", "Camera support not available. Install opencv-python and pillow.")
            return
        
        mode = self.camera_mode_var.get()
        
        try:
            if mode == "IP Stream":
                self._start_ip_stream()
            else:  # USB Camera
                self._start_usb_camera()
        except Exception as e:
            messagebox.showerror("Camera Error", f"Failed to start camera:\n{e}")
            self._stop_camera_feed()
    
    def _start_ip_stream(self) -> None:
        """Start camera feed from IP stream."""
        stream_ip = self.camera_ip_var.get().strip()
        stream_port = int(self.camera_port_var.get())
        
        # Build stream URL - OpenCV needs the full MJPEG stream URL
        self.camera_stream_url = f"http://{stream_ip}:{stream_port}/stream"
        
        print(f"Attempting to connect to: {self.camera_stream_url}")
        
        # OpenCV can open MJPEG streams via URL
        # Use CAP_FFMPEG backend for better HTTP stream support
        self.camera = cv2.VideoCapture(self.camera_stream_url, cv2.CAP_FFMPEG)
        
        if not self.camera.isOpened():
            # Fallback to default backend
            print("FFMPEG backend failed, trying default...")
            self.camera = cv2.VideoCapture(self.camera_stream_url)
        
        if not self.camera.isOpened():
            raise RuntimeError(
                f"Failed to connect to camera stream at {self.camera_stream_url}.\n"
                f"Make sure the Camera Stream Standalone app is running and streaming.\n"
                f"Test the URL in your browser: {self.camera_stream_url}"
            )
        
        print(f"Camera opened, testing frame read...")
        
        # Test if we can read a frame (try a few times)
        ret = False
        test_frame = None
        for attempt in range(5):
            ret, test_frame = self.camera.read()
            if ret and test_frame is not None:
                print(f"Successfully read test frame: {test_frame.shape[1]}x{test_frame.shape[0]}")
                break
            time.sleep(0.2)
        
        if not ret or test_frame is None:
            raise RuntimeError(
                f"Connected to stream but cannot read frames after 5 attempts.\n"
                f"Check that the stream is active at {self.camera_stream_url}\n"
                f"Try opening the URL in your browser to verify the stream works."
            )
        
        # Set buffer size to 1 for low latency
        self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        # Initialize display update counter
        self._display_update_count = 0
        
        # Start camera thread
        self.camera_running = True
        self.camera_thread = threading.Thread(target=self._camera_capture_loop, daemon=True)
        self.camera_thread.start()
        
        # Start display update loop
        self._update_camera_display()
        
        # Update UI
        self.camera_start_button.config(state=tk.DISABLED)
        self.camera_stop_button.config(state=tk.NORMAL)
        
        print(f"✓ Connected to camera stream: {self.camera_stream_url}")
    
    def _start_usb_camera(self) -> None:
        """Start camera feed from USB camera."""
        self.camera_index = int(self.camera_index_var.get())
        
        # Suppress OpenCV warnings temporarily
        import os
        os.environ['OPENCV_LOG_LEVEL'] = 'ERROR'
        
        # Initialize camera - use default backend to avoid DirectShow issues
        self.camera = cv2.VideoCapture(self.camera_index)
        
        if not self.camera.isOpened():
            raise RuntimeError(f"Failed to open camera {self.camera_index}. Try a different camera index (0, 1, 2, etc.)")
        
        # Set buffer size to 1 for low latency
        self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        # Test if we can actually read a frame
        ret, test_frame = self.camera.read()
        if not ret:
            raise RuntimeError(f"Camera {self.camera_index} opened but cannot read frames. Camera may be in use by another application.")
        
        # Start camera thread
        self.camera_running = True
        self.camera_thread = threading.Thread(target=self._camera_capture_loop, daemon=True)
        self.camera_thread.start()
        
        # Start display update loop
        self._update_camera_display()
        
        # Update UI
        self.camera_start_button.config(state=tk.DISABLED)
        self.camera_stop_button.config(state=tk.NORMAL)
        
        print(f"Camera {self.camera_index} started successfully")
    
    def _stop_camera_feed(self) -> None:
        """Stop camera feed."""
        self.camera_running = False
        
        if self.camera:
            self.camera.release()
            self.camera = None
        
        # Update UI
        self.camera_start_button.config(state=tk.NORMAL)
        self.camera_stop_button.config(state=tk.DISABLED)
        
        if self.camera_label:
            self.camera_label.config(image='', text="Camera stopped")
            # Clear photo reference
            if hasattr(self.camera_label, '_photo'):
                self.camera_label._photo = None
        
        # Clear photo reference
        self.camera_photo = None
        if hasattr(self, '_camera_photo'):
            self._camera_photo = None
        if hasattr(self, 'camera_label') and self.camera_label:
            self.camera_label.config(image='', text="Camera stopped")
    
    def _camera_capture_loop(self) -> None:
        """Camera capture loop running in background thread."""
        frame_count = 0
        while self.camera_running and self.camera:
            try:
                ret, frame = self.camera.read()
                if ret and frame is not None:
                    # Resize frame to fit display (max 640x480 for performance)
                    height, width = frame.shape[:2]
                    max_width, max_height = 640, 480
                    
                    if width > max_width or height > max_height:
                        scale = min(max_width / width, max_height / height)
                        new_width = int(width * scale)
                        new_height = int(height * scale)
                        frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
                    
                    with self.camera_frame_lock:
                        self.current_camera_frame = frame.copy()
                    
                    frame_count += 1
                    if frame_count % 30 == 0:
                        print(f"Camera: Captured {frame_count} frames (latest: {width}x{height})")
                else:
                    if frame_count == 0:
                        print("Camera: Warning - No frames being captured from stream")
                
                time.sleep(1.0 / 30)  # Target 30 fps
                
            except Exception as e:
                print(f"Camera capture error: {e}")
                time.sleep(0.1)
    
    def _update_camera_display(self) -> None:
        """Update camera display in GUI (called periodically)."""
        if not self.camera_running or not hasattr(self, 'camera_label') or not self.camera_label or self._updating_display:
            # Schedule next update even if skipping this one
            if self.camera_running and hasattr(self, 'root') and self.root:
                try:
                    self.root.after(50, self._update_camera_display)
                except tk.TclError:
                    # Widget destroyed, stop updating
                    self.camera_running = False
            return
        
        self._updating_display = True
        update_count = getattr(self, '_display_update_count', 0)
        self._display_update_count = update_count + 1
        
        # Debug first few updates
        if update_count < 5:
            print(f"Display update #{update_count} starting...")
        
        try:
            # Get frame from capture thread
            frame = None
            with self.camera_frame_lock:
                if self.current_camera_frame is not None:
                    # Make a copy to avoid holding the lock during processing
                    frame = self.current_camera_frame.copy()
                    if update_count < 5:
                        print(f"Display update #{update_count}: Got frame, shape: {frame.shape if frame is not None else 'None'}")
                else:
                    if update_count < 5:
                        print(f"Display update #{update_count}: current_camera_frame is None")
            
            if frame is not None:
                # Check if it's a valid numpy array
                if not isinstance(frame, np.ndarray):
                    if update_count < 5 or update_count % 30 == 0:
                        print(f"Display: Frame is not a numpy array: {type(frame)}")
                    frame = None
                elif frame.size == 0:
                    if update_count < 5 or update_count % 30 == 0:
                        print(f"Display: Frame has size 0")
                    frame = None
                elif len(frame.shape) < 2:
                    if update_count < 5 or update_count % 30 == 0:
                        print(f"Display: Invalid frame shape: {frame.shape}")
                    frame = None
            
            if frame is not None and frame.size > 0:
                try:
                    if update_count < 5:
                        print(f"Display update #{update_count}: Processing frame, shape: {frame.shape}")
                    
                    # Convert BGR to RGB
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    
                    if update_count < 5:
                        print(f"Display update #{update_count}: Converted to RGB, shape: {frame_rgb.shape}")
                    
                    # Get label size to resize image if needed (but don't force resize if label not ready)
                    try:
                        label_width = self.camera_label.winfo_width()
                        label_height = self.camera_label.winfo_height()
                        if update_count < 5:
                            print(f"Display update #{update_count}: Label size: {label_width}x{label_height}")
                        # Only resize if label has been rendered and has valid size
                        if label_width > 1 and label_height > 1:
                            # Resize frame to fit label (maintain aspect ratio)
                            scale = min(label_width / frame_rgb.shape[1], label_height / frame_rgb.shape[0])
                            if scale < 1.0:  # Only downscale, not upscale
                                new_width = int(frame_rgb.shape[1] * scale)
                                new_height = int(frame_rgb.shape[0] * scale)
                                frame_rgb = cv2.resize(frame_rgb, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
                                if update_count < 5:
                                    print(f"Display update #{update_count}: Resized to {new_width}x{new_height}")
                    except Exception as size_err:
                        # Label not yet sized, use frame as-is
                        if update_count < 5:
                            print(f"Display update #{update_count}: Could not get label size: {size_err}")
                    
                    # Convert to PIL Image
                    pil_image = Image.fromarray(frame_rgb)
                    
                    if update_count < 5:
                        print(f"Display update #{update_count}: Created PIL image, size: {pil_image.size}")
                    
                    # CRITICAL: Create PhotoImage using a workaround to prevent GC
                    # Store PIL image temporarily and create PhotoImage in a way that prevents GC
                    import gc
                    gc.disable()  # Temporarily disable GC
                    
                    try:
                        photo = ImageTk.PhotoImage(image=pil_image)
                        
                        if update_count < 5:
                            print(f"Display update #{update_count}: Created PhotoImage, size: {photo.width()}x{photo.height()}, id: {id(photo)}")
                        
                        # CRITICAL: Store in list FIRST to keep it alive
                        if not hasattr(self, '_camera_photo_list'):
                            self._camera_photo_list = []
                        self._camera_photo_list.append(photo)
                        # Keep only last 3 to prevent memory buildup
                        if len(self._camera_photo_list) > 3:
                            old_photo = self._camera_photo_list.pop(0)
                            del old_photo
                        
                        # Store in instance variables - multiple references
                        self._camera_photo = photo
                        self.camera_photo = photo
                        
                        # CRITICAL: Store on label widget - this MUST happen before config()
                        self.camera_label.image = photo
                        
                        # Also store as an attribute on the root to keep it alive
                        if not hasattr(self.root, '_camera_photos'):
                            self.root._camera_photos = []
                        self.root._camera_photos.append(photo)
                        if len(self.root._camera_photos) > 3:
                            self.root._camera_photos.pop(0)
                        
                        # Update the label with the PhotoImage
                        if update_count < 5:
                            print(f"Display update #{update_count}: Updating label, photo_id: {id(photo)}")
                        
                        # Update the label - use the photo directly
                        self.camera_label.config(image=photo, text='')
                        
                        if update_count < 5:
                            print(f"Display update #{update_count}: Label updated successfully, photo size: {photo.width()}x{photo.height()}")
                        
                        if update_count < 5 or update_count % 30 == 0:
                            try:
                                label_width = self.camera_label.winfo_width()
                                label_height = self.camera_label.winfo_height()
                            except:
                                label_width = label_height = 0
                            print(f"Display: Updated #{update_count}, frame: {frame.shape[1]}x{frame.shape[0]}, photo: {photo.width()}x{photo.height()}, label: {label_width}x{label_height}, visible: {self.camera_label.winfo_viewable()}")
                    except tk.TclError as tcl_err:
                        error_str = str(tcl_err)
                        # Don't suppress errors for first few updates - we need to see them
                        if update_count < 5 or "doesn't exist" not in error_str:
                            print(f"Display TclError at update #{update_count}: {error_str}")
                        # Don't raise - continue trying
                    except Exception as update_err:
                        if update_count < 5:
                            print(f"Display update error at update #{update_count}: {update_err}")
                            import traceback
                            traceback.print_exc()
                    finally:
                        gc.enable()  # Re-enable GC
                    
                except Exception as img_error:
                    # Don't suppress errors - we need to see what's wrong
                    error_str = str(img_error)
                    print(f"Image conversion error at update #{update_count}: {img_error}")
                    import traceback
                    traceback.print_exc()
            else:
                # Show status if no frame available
                if self.camera_running:
                    if update_count % 30 == 0:
                        with self.camera_frame_lock:
                            frame_status = "None" if self.current_camera_frame is None else f"exists (type: {type(self.current_camera_frame)})"
                        print(f"Display: Waiting for frame (update #{update_count}), current_frame: {frame_status}")
                    # Show label with status, hide canvas
                    self.camera_canvas.grid_remove()
                    self.camera_label.grid()
                    self.camera_label.config(text="Waiting for camera frame...")
        
        except Exception as e:
            error_msg = str(e)
            # Suppress the "doesn't exist" error - it's a Tkinter GC warning
            if "doesn't exist" not in error_msg:
                print(f"Camera display update error: {e}")
        finally:
            self._updating_display = False
        
        # Schedule next update (20 fps to reduce load and prevent GC issues)
        if self.camera_running and hasattr(self, 'root') and self.root:
            try:
                self.root.after(50, self._update_camera_display)  # ~20 fps
            except tk.TclError as e:
                # Widget might be destroyed, stop updating
                print(f"Error scheduling display update: {e}")
                self.camera_running = False
    
    # ---------- Public API ----------
    def run(self) -> None:
        """Start the Tkinter main loop."""
        self.root.mainloop()
    
    def close(self) -> None:
        """Clean up resources and restore laser to analog modulation mode.
        
        Ensures laser is left in standard final state:
        - Emission: ON
        - Analog modulation: ON (AM 1)
        - Power: 100 mW
        - Allows manual control via front panel wheel
        """
        self._stop_camera_feed()
        # Disconnect laser if connected (this will restore analog modulation mode)
        try:
            if self.laser_mgr is not None:
                # Ensure emission is ON and restore to analog modulation mode with 100 mW
                # This ensures the laser can be controlled manually after closing
                laser = self.laser_mgr.instrument
                try:
                    laser.emission_on()
                    time.sleep(0.1)
                except Exception:
                    pass
                # Restore to analog modulation mode with 100 mW before disconnecting
                self._set_laser_analog_modulation_mode(power_mw=100.0)
                self._on_laser_disconnect()
        except Exception:
            pass
        if hasattr(self, 'root'):
            self.root.destroy()


def _self_test() -> None:
    """Lightweight check that the import guard behaves as expected."""
    if MOTOR_DRIVER_AVAILABLE:
        print("Motor driver available.")
    else:
        print("Motor driver unavailable (expected if pylablib missing).")
        assert KinesisController is None


if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
    else:
        window = MotorControlWindow()
        window.run()
