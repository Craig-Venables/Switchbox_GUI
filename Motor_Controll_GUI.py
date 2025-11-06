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
    from Motor_Controll_GUI import MotorControlWindow
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

# ---------- Optional FG Protocol (for type hints) ----------

class FunctionGenerator(Protocol):
    def set_output(self, enabled: bool) -> None: ...  # noqa: E701
    def set_amplitude(self, volts: float) -> None: ...  # noqa: E701
    def get_amplitude(self) -> float: ...  # noqa: E701

# Use existing project motor control
from Equipment.Motor_Controll.Kenisis_motor_control import MotorController as KinesisController
from Equipment.function_generator_manager import FunctionGeneratorManager
import Equipment.Motor_Controll.config as config


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

    # Color scheme for modern UI
    COLORS = {
        'bg_dark': '#2b2b2b',
        'bg_medium': '#3c3c3c',
        'bg_light': '#4a4a4a',
        'fg_primary': '#ffffff',
        'fg_secondary': '#b0b0b0',
        'accent_blue': '#4a9eff',
        'accent_green': '#4ade80',
        'accent_red': '#ef4444',
        'accent_yellow': '#fbbf24',
        'grid_light': '#555555',
        'grid_dark': '#444444',
    }

    def __init__(
        self,
        function_generator: Optional[FunctionGenerator] = None,
        default_amplitude_volts: float = 0.4,
        canvas_size_pixels: int = 500,
        world_range_units: float = 50.0,
    ) -> None:
        # Motor controller (initialized on Connect)
        self.motor: Optional[KinesisController] = None
        
        # FG optional (legacy injection) and manager-based control
        self.fg: Optional[FunctionGenerator] = function_generator
        self.fg_mgr: Optional[FunctionGeneratorManager] = None

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

        # Create root window
        self.root = tk.Tk()
        self.root.title("Advanced Motor Control & Laser Positioning")
        self.root.geometry("1200x750")
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
        
        # Scanning state
        self.var_scan_x = tk.StringVar(value="5.0")
        self.var_scan_y = tk.StringVar(value="5.0")
        self.var_scan_count = tk.StringVar(value="3")
        self.var_scan_direction = tk.StringVar(value="Horizontal")

        self._build_ui()
        self._update_canvas_display()
        self._setup_keyboard_shortcuts()

    # ---------- UI Construction ----------
    def _build_ui(self) -> None:
        """Build the complete user interface."""
        # Configure root grid
        self.root.columnconfigure(0, weight=0)  # Controls
        self.root.columnconfigure(1, weight=1)  # Canvas + Camera
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
        controls_container = tk.Frame(self.root, bg=self.COLORS['bg_dark'], width=320)
        controls_container.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        controls_container.grid_propagate(False)

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

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Add control sections
        self._build_jog_controls(scrollable_frame)
        self._build_goto_controls(scrollable_frame)
        self._build_motor_settings(scrollable_frame)
        self._build_presets(scrollable_frame)
        self._build_scan_controls(scrollable_frame)
        self._build_fg_controls(scrollable_frame)

    def _build_jog_controls(self, parent: tk.Frame) -> None:
        """Build jog controls section."""
        jog_frame = self._create_section_frame(parent, "🎮 Jog Controls")
        jog_frame.pack(fill=tk.X, pady=5)

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

        btn_home = tk.Button(
            jog_frame, 
            text="🏠\nHOME", 
            command=self._on_home,
            bg=self.COLORS['accent_yellow'],
            fg='black',
            font=("Arial", 9, "bold"),
            width=6,
            height=2
        )
        btn_home.grid(row=3, column=1, padx=2, pady=2)

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
        goto_frame = self._create_section_frame(parent, "📍 Go To Position")
        goto_frame.pack(fill=tk.X, pady=5)

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
        settings_frame = self._create_section_frame(parent, "⚙️ Motor Settings")
        settings_frame.pack(fill=tk.X, pady=5)

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
        presets_frame = self._create_section_frame(parent, "⭐ Position Presets")
        presets_frame.pack(fill=tk.X, pady=5)

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
        scan_frame = self._create_section_frame(parent, "🔍 Raster Scan")
        scan_frame.pack(fill=tk.X, pady=5)

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
        fg_frame = self._create_section_frame(parent, "⚡ Laser / Function Generator")
        fg_frame.pack(fill=tk.X, pady=5)

        # VISA address with auto-detect button
        tk.Label(
            fg_frame, 
            text="VISA Address:", 
            fg=self.COLORS['fg_primary'],
            bg=self.COLORS['bg_medium']
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=2)
        
        addr_frame = tk.Frame(fg_frame, bg=self.COLORS['bg_medium'])
        addr_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 5))
        addr_frame.columnconfigure(0, weight=1)
        
        tk.Entry(
            addr_frame, 
            textvariable=self.var_fg_addr,
            bg=self.COLORS['bg_light'],
            fg=self.COLORS['fg_primary'],
            insertbackground=self.COLORS['fg_primary']
        ).grid(row=0, column=0, sticky="ew", padx=(0, 5))
        
        tk.Button(
            addr_frame,
            text="🔍",
            command=self._auto_detect_fg,
            bg=self.COLORS['accent_blue'],
            fg='white',
            width=3
        ).grid(row=0, column=1)

        # Connection buttons
        btn_frame = tk.Frame(fg_frame, bg=self.COLORS['bg_medium'])
        btn_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 5))
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)
        
        tk.Button(
            btn_frame, 
            text="Connect", 
            command=self._on_fg_connect,
            bg=self.COLORS['accent_green'],
            fg='black',
            font=("Arial", 8)
        ).grid(row=0, column=0, sticky="ew", padx=(0, 2))
        
        tk.Button(
            btn_frame, 
            text="Disconnect", 
            command=self._on_fg_disconnect,
            bg=self.COLORS['accent_red'],
            fg='white',
            font=("Arial", 8)
        ).grid(row=0, column=1, sticky="ew", padx=(2, 0))

        # Status
        status_label = tk.Label(
            fg_frame,
            textvariable=self.var_fg_status,
            fg=self.COLORS['accent_yellow'],
            bg=self.COLORS['bg_medium'],
            font=("Arial", 9)
        )
        status_label.grid(row=3, column=0, columnspan=2, sticky="w", pady=2)

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
        output_check.grid(row=4, column=0, columnspan=2, sticky="w", pady=2)

        # DC Voltage
        tk.Label(
            fg_frame, 
            text="DC Voltage (V):", 
            fg=self.COLORS['fg_primary'],
            bg=self.COLORS['bg_medium']
        ).grid(row=5, column=0, sticky="w", pady=2)
        tk.Entry(
            fg_frame, 
            textvariable=self.var_fg_amplitude,
            bg=self.COLORS['bg_light'],
            fg=self.COLORS['fg_primary'],
            insertbackground=self.COLORS['fg_primary']
        ).grid(row=5, column=1, sticky="ew", pady=2)

        # Apply button
        tk.Button(
            fg_frame, 
            text="Apply Voltage", 
            command=self._on_apply_amplitude,
            bg=self.COLORS['accent_blue'],
            fg='white',
            font=("Arial", 9)
        ).grid(row=6, column=0, columnspan=2, sticky="ew", pady=(5, 0))

        fg_frame.columnconfigure(1, weight=1)

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
            background='#1a1a1a',
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
            fill=self.COLORS['accent_yellow'],
            font=("Consolas", 9)
        )

    def _build_camera_placeholder(self, parent: tk.Frame) -> None:
        """Build camera feed placeholder."""
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

        # Placeholder content
        placeholder = tk.Frame(camera_frame, bg='#1a1a1a')
        placeholder.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        tk.Label(
            placeholder,
            text="📹",
            font=("Arial", 48),
            fg=self.COLORS['grid_light'],
            bg='#1a1a1a'
        ).pack(expand=True)

        tk.Label(
            placeholder,
            text="CAMERA FEED\nCOMING SOON",
            font=("Arial", 16, "bold"),
            fg=self.COLORS['fg_secondary'],
            bg='#1a1a1a'
        ).pack()

        tk.Label(
            placeholder,
            text="Real-time camera monitoring will be available in a future update",
            font=("Arial", 9),
            fg=self.COLORS['grid_light'],
            bg='#1a1a1a'
        ).pack(pady=(10, 0))

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
            fill=self.COLORS['accent_yellow'],
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
        """Home both motors to (0,0)."""
        if not self._is_connected():
            messagebox.showwarning("Not Connected", "Please connect to motors first.")
            return
        try:
            self.var_status.set("Motors: Homing...")
            self.root.update()
            self.motor.home_motors(self.var_status_x, self.var_status_y)  # type: ignore
            self._refresh_position()
            self.var_status.set("Motors: Homed ✓")
        except Exception as exc:
            self.var_status.set("Motors: Homing Failed")
            messagebox.showerror("Homing Error", f"Failed to home motors:\n{exc}")

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
    def _auto_detect_fg(self) -> None:
        """Auto-detect function generator VISA address."""
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

    # ---------- Public API ----------
    def run(self) -> None:
        """Start the Tkinter main loop."""
        self.root.mainloop()


if __name__ == "__main__":
    # Open the GUI
    window = MotorControlWindow()
    window.run()
