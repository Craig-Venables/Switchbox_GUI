"""
Camera Stream Standalone Application

Description:
    Standalone application that displays camera feed locally and streams it over IP.
    Supports HTTP/MJPEG streaming for web browser access and local OpenCV display.

Purpose:
    Provide a simple standalone tool to view camera feed locally while making it
    accessible over the network via web browser or other clients.

Features:
    - Local camera display using OpenCV
    - HTTP/MJPEG streaming over IP (accessible via web browser)
    - Configurable IP address and port
    - Simple GUI for configuration
    - Can be converted to standalone executable

Usage:
    python camera_stream_app.py
    
    Or convert to exe:
    pyinstaller --onefile --windowed camera_stream_app.py

Dependencies:
    - opencv-python (cv2)
    - flask (for HTTP streaming)
    - numpy
    - pylablib (optional; enables Thorlabs TLCamera support)
"""

import cv2
import threading
import time
import socket
from typing import Optional
import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os
import numpy as np

# Optional: Thorlabs scientific camera support via pylablib.
# In frozen (exe) builds we deliberately disable this backend to avoid
# heavy bundling issues; Thorlabs mode is intended for script use only.
try:
    import pylablib as pll
    from pylablib.devices import Thorlabs
    THORLABS_AVAILABLE = True
except ImportError:
    THORLABS_AVAILABLE = False

IS_FROZEN = getattr(sys, "frozen", False)
if IS_FROZEN:
    THORLABS_AVAILABLE = False

# Try to import Flask for HTTP streaming
try:
    from flask import Flask, Response, render_template_string
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    print("Warning: Flask not available. HTTP streaming will be disabled.")
    print("Install Flask with: pip install flask")


class CameraStreamApp:
    """Standalone camera streaming application with local display and IP streaming."""
    
    def __init__(self):
        """Initialize the application."""
        self.camera: Optional[cv2.VideoCapture] = None
        self.tl_camera = None  # pylablib camera handle when using Thorlabs backend
        self.camera_index = 0
        self.camera_backend = "OpenCV (index)"
        self.tl_serial: Optional[str] = None
        self.streaming = False
        self.displaying = False
        self.paused = False  # Pause state
        
        # Network settings
        self.stream_ip = "0.0.0.0"  # 0.0.0.0 means all interfaces
        self.stream_port = 8080
        self.http_server: Optional[Flask] = None
        self.http_thread: Optional[threading.Thread] = None
        
        # Frame capture - use raw frame for local display, encoded for streaming
        self.current_frame_raw: Optional[np.ndarray] = None  # Raw frame for local display
        self.current_frame_encoded: Optional[bytes] = None  # Encoded frame for streaming
        self.frame_lock = threading.Lock()
        self.capture_thread: Optional[threading.Thread] = None
        
        # Resolution
        self.resolution = (1280, 720)
        self.fps = 30
        
        # Camera settings - track if manual mode is enabled
        self.manual_mode = False  # True when user explicitly changes settings
        self.exposure = -6.0  # Default exposure (negative = auto)
        self.brightness = 0.0
        self.contrast = 0.0
        self.gain = 0.0
        
        # Single marker for click-to-mark feature (moves to new position on click)
        self.marker = None  # Single (x, y) tuple or None
        self.marker_lock = threading.Lock()
        
        # GUI
        self.root: Optional[tk.Tk] = None
        self._build_gui()
    
    def _build_gui(self):
        """Build the configuration GUI."""
        self.root = tk.Tk()
        self.root.title("Camera Stream Application")
        # Increase default window size so all controls are clearly visible
        self.root.geometry("900x900")
        self.root.configure(bg="#f0f0f0")
        
        # Title
        title = tk.Label(
            self.root,
            text="📹 Camera Stream Application",
            font=("Arial", 16, "bold"),
            bg="#f0f0f0",
            fg="#1565c0"
        )
        title.pack(pady=20)
        
        # Configuration frame
        config_frame = tk.LabelFrame(
            self.root,
            text="Configuration",
            bg="#f0f0f0",
            font=("Arial", 10, "bold"),
            padx=20,
            pady=15
        )
        config_frame.pack(padx=20, pady=10, fill="x")
        
        # Camera backend selection
        tk.Label(
            config_frame,
            text="Camera Type:",
            bg="#f0f0f0",
            font=("Arial", 9)
        ).grid(row=0, column=0, sticky="w", pady=5)
        # In frozen/exe builds we only expose the OpenCV backend; Thorlabs
        # support is intended for script use where pylablib is installed.
        if THORLABS_AVAILABLE:
            backend_options = ["OpenCV (index)", "Thorlabs (pylablib)"]
        else:
            backend_options = ["OpenCV (index)"]
        self.camera_backend = backend_options[0]
        self.backend_var = tk.StringVar(value=self.camera_backend)
        backend_combo = ttk.Combobox(
            config_frame,
            textvariable=self.backend_var,
            values=backend_options,
            width=18,
            state="readonly"
        )
        backend_combo.grid(row=0, column=1, sticky="w", padx=10, pady=5)
        backend_combo.bind("<<ComboboxSelected>>", lambda e: self._toggle_backend_fields())
        
        # Camera index
        tk.Label(
            config_frame,
            text="Camera Index:",
            bg="#f0f0f0",
            font=("Arial", 9)
        ).grid(row=1, column=0, sticky="w", pady=5)
        self.camera_var = tk.StringVar(value="0")
        self.camera_entry = tk.Entry(
            config_frame,
            textvariable=self.camera_var,
            width=10,
            font=("Arial", 9)
        )
        self.camera_entry.grid(row=1, column=1, sticky="w", padx=10, pady=5)
        
        # Thorlabs serial (when using pylablib) – only show when available (script mode)
        if THORLABS_AVAILABLE:
            tk.Label(
                config_frame,
                text="Thorlabs Serial:",
                bg="#f0f0f0",
                font=("Arial", 9)
            ).grid(row=2, column=0, sticky="w", pady=5)
            self.serial_var = tk.StringVar(value="")
            self.serial_entry = tk.Entry(
                config_frame,
                textvariable=self.serial_var,
                width=15,
                font=("Arial", 9),
                state=tk.NORMAL
            )
            self.serial_entry.grid(row=2, column=1, sticky="w", padx=10, pady=5)
            
            self.detect_btn = tk.Button(
                config_frame,
                text="Detect Thorlabs",
                command=self._detect_thorlabs_cameras,
                bg="#569CD6",
                fg="white",
                font=("Arial", 8, "bold"),
                padx=8,
                pady=3,
                relief=tk.FLAT,
                state=tk.NORMAL
            )
            self.detect_btn.grid(row=2, column=2, sticky="w", padx=5, pady=5)
            
            self.detect_result_var = tk.StringVar(
                value="Click Detect to list cameras"
            )
            tk.Label(
                config_frame,
                textvariable=self.detect_result_var,
                bg="#f0f0f0",
                font=("Arial", 8),
                fg="#666",
                justify=tk.LEFT,
                wraplength=200
            ).grid(row=2, column=3, sticky="w", padx=5, pady=5)
        
        # Stream IP - Make it optional/clearer
        tk.Label(
            config_frame,
            text="Stream IP Address:",
            bg="#f0f0f0",
            font=("Arial", 9)
        ).grid(row=3, column=0, sticky="w", pady=5)
        self.ip_var = tk.StringVar(value="0.0.0.0")
        ip_entry = tk.Entry(
            config_frame,
            textvariable=self.ip_var,
            width=15,
            font=("Arial", 9)
        )
        ip_entry.grid(row=3, column=1, sticky="w", padx=10, pady=5)
        
        # Help text with better explanation
        help_text = tk.Label(
            config_frame,
            text="(Leave as 0.0.0.0 to stream on all network interfaces.\n"
                 "This makes it accessible from any device on your network.)",
            bg="#f0f0f0",
            font=("Arial", 8),
            fg="#666",
            justify=tk.LEFT,
            wraplength=200
        )
        help_text.grid(row=3, column=2, sticky="w", padx=5)
        
        # Stream Port
        tk.Label(
            config_frame,
            text="Stream Port:",
            bg="#f0f0f0",
            font=("Arial", 9)
        ).grid(row=4, column=0, sticky="w", pady=5)
        self.port_var = tk.StringVar(value="8080")
        port_entry = tk.Entry(
            config_frame,
            textvariable=self.port_var,
            width=10,
            font=("Arial", 9)
        )
        port_entry.grid(row=4, column=1, sticky="w", padx=10, pady=5)
        
        # Resolution
        tk.Label(
            config_frame,
            text="Resolution:",
            bg="#f0f0f0",
            font=("Arial", 9)
        ).grid(row=5, column=0, sticky="w", pady=5)
        self.resolution_var = tk.StringVar(value="1280x720")
        resolution_combo = ttk.Combobox(
            config_frame,
            textvariable=self.resolution_var,
            values=["320x240", "640x480", "800x600", "1024x768", "1280x720"],
            width=12,
            state="readonly"
        )
        resolution_combo.grid(row=3, column=1, sticky="w", padx=10, pady=5)
        
        # Camera Controls Frame
        controls_frame = tk.LabelFrame(
            self.root,
            text="Camera Controls",
            bg="#f0f0f0",
            font=("Arial", 10, "bold"),
            padx=20,
            pady=15
        )
        controls_frame.pack(padx=20, pady=10, fill="x")
        
        # Frame Rate
        tk.Label(
            controls_frame,
            text="Frame Rate (fps):",
            bg="#f0f0f0",
            font=("Arial", 9)
        ).grid(row=0, column=0, sticky="w", pady=5)
        self.fps_var = tk.StringVar(value="30")
        fps_entry = tk.Entry(
            controls_frame,
            textvariable=self.fps_var,
            width=10,
            font=("Arial", 9)
        )
        fps_entry.grid(row=0, column=1, sticky="w", padx=10, pady=5)
        fps_entry.bind('<Return>', lambda e: self._update_camera_settings())
        
        # Exposure
        tk.Label(
            controls_frame,
            text="Exposure:",
            bg="#f0f0f0",
            font=("Arial", 9)
        ).grid(row=1, column=0, sticky="w", pady=5)
        self.exposure_var = tk.StringVar(value="-6.0")
        exposure_entry = tk.Entry(
            controls_frame,
            textvariable=self.exposure_var,
            width=10,
            font=("Arial", 9)
        )
        exposure_entry.grid(row=1, column=1, sticky="w", padx=10, pady=5)
        exposure_entry.bind('<Return>', lambda e: self._update_camera_settings())
        tk.Label(
            controls_frame,
            text="(negative = auto, only applies when 'Apply Manual Settings' is clicked)",
            bg="#f0f0f0",
            font=("Arial", 8),
            fg="#666"
        ).grid(row=3, column=2, sticky="w", padx=5)
        
        # Brightness
        tk.Label(
            controls_frame,
            text="Brightness:",
            bg="#f0f0f0",
            font=("Arial", 9)
        ).grid(row=2, column=0, sticky="w", pady=5)
        self.brightness_var = tk.StringVar(value="0.0")
        brightness_scale = tk.Scale(
            controls_frame,
            from_=-100,
            to=100,
            orient=tk.HORIZONTAL,
            variable=self.brightness_var,
            length=150,
            bg="#f0f0f0"
            # Don't auto-apply - user must click "Apply Manual Settings"
        )
        brightness_scale.grid(row=2, column=1, sticky="w", padx=10, pady=5)
        
        # Contrast
        tk.Label(
            controls_frame,
            text="Contrast:",
            bg="#f0f0f0",
            font=("Arial", 9)
        ).grid(row=3, column=0, sticky="w", pady=5)
        self.contrast_var = tk.StringVar(value="0.0")
        contrast_scale = tk.Scale(
            controls_frame,
            from_=-100,
            to=100,
            orient=tk.HORIZONTAL,
            variable=self.contrast_var,
            length=150,
            bg="#f0f0f0"
            # Don't auto-apply - user must click "Apply Manual Settings"
        )
        contrast_scale.grid(row=3, column=1, sticky="w", padx=10, pady=5)
        
        # Gain
        tk.Label(
            controls_frame,
            text="Gain:",
            bg="#f0f0f0",
            font=("Arial", 9)
        ).grid(row=4, column=0, sticky="w", pady=5)
        self.gain_var = tk.StringVar(value="0.0")
        gain_scale = tk.Scale(
            controls_frame,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            variable=self.gain_var,
            length=150,
            bg="#f0f0f0"
            # Don't auto-apply - user must click "Apply Manual Settings"
        )
        gain_scale.grid(row=4, column=1, sticky="w", padx=10, pady=5)
        
        # Buttons frame
        buttons_frame = tk.Frame(controls_frame, bg="#f0f0f0")
        buttons_frame.grid(row=5, column=0, columnspan=3, pady=10)
        
        # Apply Settings Button
        apply_btn = tk.Button(
            buttons_frame,
            text="Apply Manual Settings",
            command=self._update_camera_settings,
            bg="#569CD6",
            fg="white",
            font=("Arial", 8, "bold"),
            padx=10,
            pady=5,
            relief=tk.FLAT
        )
        apply_btn.pack(side=tk.LEFT, padx=5)
        
        # Reset to Auto Button
        auto_btn = tk.Button(
            buttons_frame,
            text="Reset to Auto",
            command=self._reset_to_auto,
            bg="#4CAF50",
            fg="white",
            font=("Arial", 8, "bold"),
            padx=10,
            pady=5,
            relief=tk.FLAT
        )
        auto_btn.pack(side=tk.LEFT, padx=5)
        
        # Auto mode indicator
        self.auto_mode_label = tk.Label(
            controls_frame,
            text="Mode: Auto (camera controls exposure, brightness, contrast, gain)",
            bg="#f0f0f0",
            font=("Arial", 8),
            fg="#4CAF50"
        )
        self.auto_mode_label.grid(row=6, column=0, columnspan=3, pady=5)
        
        # Status
        self.status_var = tk.StringVar(value="Ready")
        status_label = tk.Label(
            self.root,
            textvariable=self.status_var,
            bg="#f0f0f0",
            font=("Arial", 9),
            fg="#333"
        )
        status_label.pack(pady=10)
        
        # Buttons
        button_frame = tk.Frame(self.root, bg="#f0f0f0")
        button_frame.pack(pady=20)
        
        self.start_button = tk.Button(
            button_frame,
            text="▶ Start Camera & Stream",
            command=self._start_camera,
            bg="#4CAF50",
            fg="white",
            font=("Arial", 10, "bold"),
            padx=20,
            pady=10,
            relief=tk.FLAT
        )
        self.start_button.pack(side=tk.LEFT, padx=10)
        
        self.pause_button = tk.Button(
            button_frame,
            text="⏸ Pause",
            command=self._pause_camera,
            bg="#FFA500",
            fg="white",
            font=("Arial", 10, "bold"),
            padx=20,
            pady=10,
            relief=tk.FLAT,
            state=tk.DISABLED
        )
        self.pause_button.pack(side=tk.LEFT, padx=10)
        
        self.stop_button = tk.Button(
            button_frame,
            text="⏹ Stop",
            command=self._stop_camera,
            bg="#F44336",
            fg="white",
            font=("Arial", 10, "bold"),
            padx=20,
            pady=10,
            relief=tk.FLAT,
            state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=10)
        
        # Clear Marker Button
        self.clear_markers_button = tk.Button(
            button_frame,
            text="🗑️ Clear Marker",
            command=self._clear_markers,
            bg="#FFA500",
            fg="white",
            font=("Arial", 9, "bold"),
            padx=15,
            pady=10,
            relief=tk.FLAT,
            state=tk.DISABLED
        )
        self.clear_markers_button.pack(side=tk.LEFT, padx=10)
        
        # Info text
        info_text = tk.Text(
            self.root,
            height=6,
            width=60,
            bg="#ffffff",
            fg="#333",
            font=("Consolas", 8),
            wrap=tk.WORD
        )
        info_text.pack(padx=20, pady=10, fill="both", expand=True)
        info_text.insert("1.0", 
            "Quick Start Instructions:\n\n"
            "1. Select camera index (usually 0 for default camera)\n"
            "2. Stream IP: Leave as 0.0.0.0 (recommended) - this makes the stream\n"
            "   accessible from any device on your network\n"
            "3. Set port (default: 8080 is fine)\n"
            "4. Adjust camera controls if needed (exposure, brightness, etc.)\n"
            "5. Click 'Start Camera & Stream'\n"
            "6. Click on the camera window to place markers\n\n"
            "Accessing the Stream:\n"
            "• On this computer: http://localhost:8080/stream\n"
            "• From other devices: http://<this-computer-ip>:8080/stream\n"
            "  (The IP address will be shown in the status message)\n\n"
            "Note: You don't need to change the IP address unless you have\n"
            "specific network requirements. 0.0.0.0 works for most cases."
        )
        info_text.config(state=tk.DISABLED)
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _toggle_backend_fields(self):
        """Enable/disable fields depending on selected backend."""
        self.camera_backend = self.backend_var.get()
        use_thorlabs = self.camera_backend == "Thorlabs (pylablib)"
        if THORLABS_AVAILABLE and use_thorlabs:
            self.camera_entry.config(state=tk.DISABLED)
            if hasattr(self, "serial_entry"):
                self.serial_entry.config(state=tk.NORMAL)
            if hasattr(self, "detect_btn"):
                self.detect_btn.config(state=tk.NORMAL)
            if hasattr(self, "detect_result_var"):
                self.detect_result_var.set("Click Detect to list cameras")
        else:
            # Default OpenCV path or exe builds where Thorlabs is disabled
            self.camera_entry.config(state=tk.NORMAL)
            if hasattr(self, "serial_entry"):
                self.serial_entry.config(state=tk.DISABLED)
            if hasattr(self, "detect_btn"):
                self.detect_btn.config(state=tk.DISABLED)
            if hasattr(self, "detect_result_var"):
                self.detect_result_var.set("")

    def _detect_thorlabs_cameras(self):
        """List connected Thorlabs cameras using pylablib."""
        if not THORLABS_AVAILABLE:
            # In exe builds Thorlabs mode is disabled entirely; in script
            # mode user should only reach here if pylablib imported OK.
            messagebox.showerror("Thorlabs", "Thorlabs backend is not available in this build.")
            return
        try:
            serials = Thorlabs.list_cameras_tlcam()
            if serials:
                self.detect_result_var.set(f"Found: {', '.join(serials)}")
                if not self.serial_var.get():
                    self.serial_var.set(serials[0])
            else:
                self.detect_result_var.set("No Thorlabs cameras detected")
        except Exception as exc:
            self.detect_result_var.set(f"Error detecting cameras: {exc}")
            messagebox.showerror("Thorlabs detection error", str(exc))
    
    def _get_local_ip(self) -> str:
        """Get local IP address."""
        try:
            # Connect to a remote address to determine local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
    
    def _start_camera(self):
        """Start camera capture and streaming."""
        try:
            # Get configuration
            self.camera_backend = self.backend_var.get()
            self.camera_index = int(self.camera_var.get()) if self.camera_var.get() else 0
            self.tl_serial = self.serial_var.get().strip() or None
            self.stream_ip = self.ip_var.get().strip()
            self.stream_port = int(self.port_var.get())
            
            # Parse resolution
            res_str = self.resolution_var.get()
            width, height = map(int, res_str.split('x'))
            self.resolution = (width, height)
            
            # Validate IP
            if not self.stream_ip:
                self.stream_ip = "0.0.0.0"
            
            self.status_var.set("Initializing camera...")
            self.root.update()

            # Initialize selected backend
            if self.camera_backend == "Thorlabs (pylablib)":
                self._open_thorlabs_camera()
            else:
                self._open_opencv_camera()
            
            # Start frame capture thread
            self.streaming = True
            self.capture_thread = threading.Thread(target=self._capture_frames, daemon=True)
            self.capture_thread.start()
            
            # Start local display thread
            self.displaying = True
            display_thread = threading.Thread(target=self._display_frames, daemon=True)
            display_thread.start()
            
            # Start HTTP streaming if Flask is available
            if FLASK_AVAILABLE:
                self._start_http_stream()
            
            # Update UI
            self.start_button.config(state=tk.DISABLED)
            self.pause_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.NORMAL)
            self.clear_markers_button.config(state=tk.NORMAL)
            
            local_ip = self._get_local_ip()
            if self.stream_ip == "0.0.0.0" or self.stream_ip == "":
                # Show both localhost and network IP
                self.status_var.set(
                    f"Streaming! Local: http://localhost:{self.stream_port}/stream | "
                    f"Network: http://{local_ip}:{self.stream_port}/stream"
                )
            else:
                stream_url = f"http://{self.stream_ip}:{self.stream_port}/stream"
                self.status_var.set(f"Streaming! Access at: {stream_url}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start camera:\n{e}")
            self.status_var.set("Error: " + str(e))
            self._stop_camera()

    def _open_opencv_camera(self):
        """Open a camera using OpenCV backends."""
        if sys.platform == 'win32':
            self.camera = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            if not self.camera.isOpened():
                self.camera = cv2.VideoCapture(self.camera_index)
        else:
            self.camera = cv2.VideoCapture(self.camera_index)

        if not self.camera.isOpened():
            raise RuntimeError(f"Failed to open camera {self.camera_index}. Try a different camera index (0, 1, 2, etc.)")

        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
        self.camera.set(cv2.CAP_PROP_FPS, self.fps)
        self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        print("Camera started with auto exposure/brightness/contrast/gain")

    def _open_thorlabs_camera(self):
        """Open a Thorlabs TLCamera using pylablib."""
        if not THORLABS_AVAILABLE:
            raise RuntimeError("pylablib not installed. Run `pip install pylablib` to enable Thorlabs support.")

        # If a previous camera exists, close it first
        self.camera = None  # ensure OpenCV handle is unused
        if self.tl_camera:
            try:
                self.tl_camera.stop_acquisition()
            except Exception:
                pass
            try:
                self.tl_camera.close()
            except Exception:
                pass
            self.tl_camera = None

        # Optionally allow overriding DLL path via environment variable
        dll_override = os.environ.get("THORLABS_TLCAM_DLL_DIR")
        if dll_override:
            pll.par["devices/dlls/thorlabs_tlcam"] = dll_override

        # Connect
        self.tl_camera = Thorlabs.ThorlabsTLCamera(serial=self.tl_serial or None)
        # Start acquisition immediately so capture loop can read frames
        self.tl_camera.start_acquisition()
        print(f"Thorlabs camera started (serial={self.tl_serial or 'first available'})")
    
    def _pause_camera(self):
        """Pause or resume camera capture."""
        if not self.streaming:
            return
        
        self.paused = not self.paused
        
        if self.paused:
            self.pause_button.config(text="▶ Resume")
            self.status_var.set("Camera Paused - Click Resume to continue")
            print("Camera paused")
        else:
            self.pause_button.config(text="⏸ Pause")
            local_ip = self._get_local_ip()
            if self.stream_ip == "0.0.0.0" or self.stream_ip == "":
                self.status_var.set(
                    f"Streaming! Local: http://localhost:{self.stream_port}/stream | "
                    f"Network: http://{local_ip}:{self.stream_port}/stream"
                )
            else:
                stream_url = f"http://{self.stream_ip}:{self.stream_port}/stream"
                self.status_var.set(f"Streaming! Access at: {stream_url}")
            print("Camera resumed")
    
    def _stop_camera(self):
        """Stop camera capture and streaming."""
        self.streaming = False
        self.displaying = False
        self.paused = False
        
        # Stop HTTP server
        if self.http_server:
            # Flask doesn't have a clean shutdown, so we'll just stop accepting connections
            pass
        
        # Stop camera
        if self.camera_backend == "Thorlabs (pylablib)":
            if self.tl_camera:
                try:
                    self.tl_camera.stop_acquisition()
                except Exception:
                    pass
                try:
                    self.tl_camera.close()
                except Exception:
                    pass
                self.tl_camera = None
        else:
            if self.camera:
                self.camera.release()
                self.camera = None
        
        # Close OpenCV windows
        cv2.destroyAllWindows()
        
        # Update UI
        self.start_button.config(state=tk.NORMAL)
        self.pause_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.DISABLED)
        self.clear_markers_button.config(state=tk.DISABLED)
        self.status_var.set("Stopped")
        self.paused = False
        
        # Clear marker
        with self.marker_lock:
            self.marker = None
    
    def _capture_frames(self):
        """Capture frames from camera in background thread - optimized for speed."""
        # Calculate target frame time
        target_fps = max(1, min(60, self.fps))  # Clamp between 1 and 60 fps
        frame_time = 1.0 / target_fps
        
        # Use high-precision timing
        last_time = time.perf_counter()
        
        while self.streaming and (self.camera or self.tl_camera):
            try:
                # Skip frame capture if paused
                if self.paused:
                    time.sleep(0.1)
                    continue
                
                # Read frame depending on backend
                if self.camera_backend == "Thorlabs (pylablib)":
                    frame = self._get_thorlabs_frame()
                    if frame is None:
                        time.sleep(0.01)
                        continue
                else:
                    ret, frame = self.camera.read()
                    if not ret:
                        time.sleep(0.01)  # Short sleep on read failure
                        continue
                
                # Resize if needed (only if necessary)
                if frame.shape[1] != self.resolution[0] or frame.shape[0] != self.resolution[1]:
                    frame = cv2.resize(frame, self.resolution, interpolation=cv2.INTER_LINEAR)
                
                # Draw markers on frame
                frame = self._draw_markers(frame)
                
                # Store raw frame for local display (no encoding overhead)
                with self.frame_lock:
                    self.current_frame_raw = frame.copy()
                
                # Encode frame for streaming (only if Flask is available)
                if FLASK_AVAILABLE:
                    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    with self.frame_lock:
                        self.current_frame_encoded = buffer.tobytes()
                
                # Frame rate limiting using high-precision timing
                current_time = time.perf_counter()
                elapsed = current_time - last_time
                sleep_time = max(0, frame_time - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                last_time = time.perf_counter()
                
            except Exception as e:
                print(f"Error capturing frame: {e}")
                time.sleep(0.01)

    def _get_thorlabs_frame(self):
        """Grab a frame from Thorlabs TLCamera."""
        if not self.tl_camera:
            return None
        try:
            frame = self.tl_camera.get_frame(timeout=1.0)
            # pylablib returns (frame, meta) for most cameras
            if isinstance(frame, tuple) and len(frame) >= 1:
                frame = frame[0]
            return np.array(frame)
        except Exception as exc:
            print(f"Thorlabs frame error: {exc}")
            return None
    
    def _display_frames(self):
        """Display frames locally using OpenCV - optimized for speed."""
        window_name = 'Camera Stream - Local Display (Click to mark)'
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(window_name, self._on_mouse_click)
        
        target_fps = max(1, min(60, self.fps))
        frame_time = 1.0 / target_fps
        last_time = time.perf_counter()
        
        while self.displaying:
            try:
                # Get raw frame directly (no decoding needed)
                with self.frame_lock:
                    frame = self.current_frame_raw
                    if frame is None:
                        time.sleep(0.01)
                        continue
                    # Make a copy to avoid lock contention
                    display_frame = frame.copy()
                
                # Draw stream address and close instructions on frame (only if streaming)
                if self.streaming:
                    local_url = f"http://localhost:{self.stream_port}/stream"
                    try:
                        local_ip = self._get_local_ip()
                        network_url = f"http://{local_ip}:{self.stream_port}/stream"
                    except:
                        network_url = None
                    display_frame = self._draw_overlay_info(display_frame, local_url, network_url)
                else:
                    # Just show close instructions if not streaming
                    display_frame = self._draw_overlay_info(display_frame, None, None)
                
                # Display frame
                cv2.imshow(window_name, display_frame)
                
                # Handle keyboard input
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    self._stop_camera()
                    break
                elif key == ord('c'):
                    # Clear marker with 'c' key
                    self._clear_markers()
                
                # Frame rate limiting
                current_time = time.perf_counter()
                elapsed = current_time - last_time
                sleep_time = max(0, frame_time - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                last_time = time.perf_counter()
                
            except Exception as e:
                print(f"Error displaying frame: {e}")
                time.sleep(0.01)
    
    def _start_http_stream(self):
        """Start HTTP streaming server using Flask."""
        if not FLASK_AVAILABLE:
            return
        
        app = Flask(__name__)
        self.http_server = app
        
        @app.route('/')
        def index():
            """Main page with stream viewer."""
            html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Camera Stream</title>
                <style>
                    body {
                        font-family: Arial, sans-serif;
                        text-align: center;
                        background: #f0f0f0;
                        margin: 0;
                        padding: 20px;
                    }
                    h1 {
                        color: #1565c0;
                    }
                    img {
                        border: 2px solid #333;
                        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
                    }
                </style>
            </head>
            <body>
                <h1>📹 Camera Stream</h1>
                <img src="/stream" alt="Camera Stream">
            </body>
            </html>
            """
            return render_template_string(html)
        
        @app.route('/stream')
        def stream():
            """MJPEG stream endpoint."""
            def generate():
                target_fps = max(1, min(30, self.fps))  # Limit stream to 30fps max
                frame_time = 1.0 / target_fps
                last_time = time.perf_counter()
                
                while self.streaming:
                    with self.frame_lock:
                        frame_data = self.current_frame_encoded
                        if frame_data:
                            yield (b'--frame\r\n'
                                   b'Content-Type: image/jpeg\r\n\r\n' + 
                                   frame_data + b'\r\n')
                    
                    # Frame rate limiting for stream
                    current_time = time.perf_counter()
                    elapsed = current_time - last_time
                    sleep_time = max(0, frame_time - elapsed)
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                    last_time = time.perf_counter()
            
            return Response(
                generate(),
                mimetype='multipart/x-mixed-replace; boundary=frame'
            )
        
        # Run Flask in a separate thread
        def run_flask():
            app.run(host=self.stream_ip, port=self.stream_port, threaded=True, debug=False)
        
        self.http_thread = threading.Thread(target=run_flask, daemon=True)
        self.http_thread.start()
    
    def _on_mouse_click(self, event, x, y, flags, param):
        """Handle mouse clicks on the OpenCV window to move marker."""
        if event == cv2.EVENT_LBUTTONDOWN:
            with self.marker_lock:
                self.marker = (x, y)
            print(f"Marker moved to ({x}, {y})")
    
    def _draw_markers(self, frame):
        """Draw single marker on the frame."""
        with self.marker_lock:
            if self.marker is not None:
                x, y = self.marker
                # Draw a red circle with crosshair
                cv2.circle(frame, (x, y), 10, (0, 0, 255), 2)  # Red circle
                cv2.circle(frame, (x, y), 2, (0, 0, 255), -1)  # Red center dot
                # Crosshair
                cv2.line(frame, (x - 15, y), (x + 15, y), (0, 0, 255), 1)
                cv2.line(frame, (x, y - 15), (x, y + 15), (0, 0, 255), 1)
        return frame
    
    def _draw_overlay_info(self, frame, local_url, network_url=None):
        """Draw stream address and close instructions in a small corner box."""
        if frame is None:
            return frame
        
        height, width = frame.shape[:2]
        
        # Use high-quality font for better readability
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.4  # Smaller font
        thickness = 1
        line_height = 18
        padding = 8
        margin = 10  # Distance from corner
        
        # Calculate box dimensions
        lines = []
        if local_url:
            lines.append("Stream:")
            lines.append(f"Local: {local_url}")
            if network_url:
                lines.append(f"Net: {network_url}")
        lines.append("Press 'Q' to close")
        
        # Calculate text sizes to determine box width
        max_width = 0
        for line in lines:
            (text_width, text_height), _ = cv2.getTextSize(line, font, font_scale, thickness)
            max_width = max(max_width, text_width)
        
        box_width = max_width + (padding * 2)
        box_height = len(lines) * line_height + (padding * 2)
        
        # Position in top-right corner
        box_x = width - box_width - margin
        box_y = margin
        
        # Draw semi-transparent background box
        overlay = frame.copy()
        cv2.rectangle(overlay, (box_x, box_y), (box_x + box_width, box_y + box_height), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        
        # Draw border around box
        cv2.rectangle(frame, (box_x, box_y), (box_x + box_width, box_y + box_height), (0, 255, 0), 1)
        
        # Draw text lines
        y_pos = box_y + padding + line_height
        for i, line in enumerate(lines):
            if i == 0 and local_url:
                # Header in green
                cv2.putText(frame, line, (box_x + padding, y_pos), font, font_scale, (0, 255, 0), thickness)
            elif i < len(lines) - 1 and local_url:
                # URLs in white
                cv2.putText(frame, line, (box_x + padding, y_pos), font, font_scale, (255, 255, 255), thickness)
            else:
                # Instructions in cyan
                cv2.putText(frame, line, (box_x + padding, y_pos), font, font_scale, (0, 255, 255), thickness)
            y_pos += line_height
        
        return frame
    
    def _clear_markers(self):
        """Clear the marker."""
        with self.marker_lock:
            self.marker = None
        print("Marker cleared")
    
    def _update_camera_settings(self):
        """Update camera settings from GUI values (only when user explicitly changes them)."""
        if self.camera_backend == "Thorlabs (pylablib)":
            # For Thorlabs we only adjust FPS limiter; hardware settings should be set in vendor tools or via pylablib directly.
            try:
                self.fps = float(self.fps_var.get())
                self.status_var.set("Thorlabs FPS limiter updated; exposure/brightness unchanged")
            except ValueError as e:
                print(f"Invalid FPS value: {e}")
            return

        if not self.camera or not self.camera.isOpened():
            return
        
        # Mark that manual mode is now enabled
        self.manual_mode = True
        
        try:
            # Update FPS (always apply FPS)
            self.fps = float(self.fps_var.get())
            self.camera.set(cv2.CAP_PROP_FPS, self.fps)
            
            # Update exposure
            self.exposure = float(self.exposure_var.get())
            self.camera.set(cv2.CAP_PROP_EXPOSURE, self.exposure)
            
            # Update brightness
            self.brightness = float(self.brightness_var.get())
            self.camera.set(cv2.CAP_PROP_BRIGHTNESS, self.brightness)
            
            # Update contrast
            self.contrast = float(self.contrast_var.get())
            self.camera.set(cv2.CAP_PROP_CONTRAST, self.contrast)
            
            # Update gain
            self.gain = float(self.gain_var.get())
            self.camera.set(cv2.CAP_PROP_GAIN, self.gain)
            
            print(f"Manual camera settings applied: FPS={self.fps}, Exposure={self.exposure}, "
                  f"Brightness={self.brightness}, Contrast={self.contrast}, Gain={self.gain}")
            
            # Update mode indicator
            if hasattr(self, 'auto_mode_label'):
                self.auto_mode_label.config(
                    text="Mode: Manual (user controls exposure, brightness, contrast, gain)",
                    fg="#FFA500"
                )
            
        except ValueError as e:
            print(f"Invalid camera setting value: {e}")
    
    def _reset_to_auto(self):
        """Reset camera to auto mode (let camera control exposure, brightness, contrast, gain)."""
        if self.camera_backend == "Thorlabs (pylablib)":
            self.status_var.set("Auto reset not required for Thorlabs; camera manages exposure internally.")
            return
        if not self.camera or not self.camera.isOpened():
            return
        
        # Reset manual mode flag
        self.manual_mode = False
        
        # Set exposure to auto (negative value)
        try:
            self.camera.set(cv2.CAP_PROP_EXPOSURE, -6.0)  # Auto exposure
            # Don't set brightness, contrast, or gain - let camera use defaults
            print("Camera reset to auto mode (auto exposure, brightness, contrast, gain)")
            
            # Update mode indicator
            if hasattr(self, 'auto_mode_label'):
                self.auto_mode_label.config(
                    text="Mode: Auto (camera controls exposure, brightness, contrast, gain)",
                    fg="#4CAF50"
                )
        except Exception as e:
            print(f"Error resetting to auto mode: {e}")
    
    def _on_closing(self):
        """Handle window closing."""
        self._stop_camera()
        self.root.destroy()
    
    def run(self):
        """Run the application."""
        self.root.mainloop()


def main():
    """Main entry point."""
    app = CameraStreamApp()
    app.run()


if __name__ == "__main__":
    main()

