"""
Simple Tkinter Motor Control GUI (single-file)

Description:
- A minimal, single-file Tkinter GUI to control Thorlabs Kinesis XY motors via
  your existing `motor_control.MotorController`. Provides jog buttons and a
  clickable canvas. Clicking within the canvas issues a move-to command to the
  clicked position.
- Optional function generator (FG) controls are included. If you pass in an FG
  instance, the GUI can toggle its output ON/OFF and set amplitude (default 0.4 V).

Dependencies:
- Python 3.8+
- Tkinter (included with most Python distributions; on Windows it is typically
  available by default). If missing, install OS-level Tk support.
- Your project modules: `motor_control.py` (uses pylablib Thorlabs Kinesis) and `config.py`.

Usage (import into another project):
    from simple_motor_tk import MotorControlWindow

    # Optionally pass a function generator instance; motors are controlled by
    # your existing motor_control.MotorController upon pressing Connect.
    window = MotorControlWindow(
        function_generator=my_function_generator,  # optional
        default_amplitude_volts=0.4
    )
    window.run()

Quick run:
    python simple_motor_tk.py

Function generator interface expected:
    - set_output(enabled: bool) -> None
    - set_amplitude(volts: float) -> None
    - get_amplitude() -> float
"""

from __future__ import annotations

from typing import Optional, Protocol, Tuple

import tkinter as tk
from tkinter import ttk


# ---------- Optional FG Protocol (for type hints) ----------

class FunctionGenerator(Protocol):
    def set_output(self, enabled: bool) -> None: ...  # noqa: E701
    def set_amplitude(self, volts: float) -> None: ...  # noqa: E701
    def get_amplitude(self) -> float: ...  # noqa: E701

# Use existing project motor control
from Equipment.Motor_Controll.Kenisis_motor_control import MotorController as KinesisController


# ---------- GUI Window ----------

class MotorControlWindow:
    """Simple Tkinter window for motor jogging and canvas-click moves.

    Parameters
    ----------
    function_generator : Optional[FunctionGenerator]
        Provide your own FG. If None, FG controls are hidden.
    default_amplitude_volts : float
        Initial amplitude value for FG controls.
    canvas_size_pixels : int
        Width and height of the square canvas in pixels.
    world_range_units : float
        The movement range mapped to the canvas in user units. Clicking at the
        edges maps to +/- world_range_units.
    """

    def __init__(
        self,
        function_generator: Optional[FunctionGenerator] = None,
        default_amplitude_volts: float = 0.4,
        canvas_size_pixels: int = 420,
        world_range_units: float = 25.0,
    ) -> None:
        # Will be initialized on Connect
        self.motor: Optional[KinesisController] = None
        # FG optional
        self.fg: Optional[FunctionGenerator] = function_generator

        self.canvas_size = int(canvas_size_pixels)
        self.world_range = float(world_range_units)

        self.root = tk.Tk()
        self.root.title("Simple Motor Control")
        self.root.geometry("820x560")

        # State variables
        self.var_status = tk.StringVar(value="Disconnected")
        self.var_position = tk.StringVar(value="X: 0.00, Y: 0.00")
        self.var_step = tk.StringVar(value="1.0")  # jog step in user units
        self.var_status_x = tk.StringVar(value="")
        self.var_status_y = tk.StringVar(value="")
        # FG state only if FG provided
        self.var_fg_enabled = tk.BooleanVar(value=False) if self.fg is not None else None
        self.var_fg_amplitude = (
            tk.StringVar(value=f"{default_amplitude_volts:.3f}") if self.fg is not None else None
        )

        self._build_ui()
        self._update_canvas_grid()

    # ---------- UI Construction ----------
    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=0)
        self.root.rowconfigure(1, weight=1)

        # Header frame: connection + position
        header = ttk.Frame(self.root, padding=(10, 10))
        header.grid(row=0, column=0, columnspan=2, sticky="nsew")
        header.columnconfigure(3, weight=1)

        ttk.Label(header, text="Status:").grid(row=0, column=0, sticky="w")
        self.lbl_status = ttk.Label(header, textvariable=self.var_status)
        self.lbl_status.grid(row=0, column=1, sticky="w", padx=(4, 12))

        self.btn_connect = ttk.Button(header, text="Connect", command=self._on_connect)
        self.btn_connect.grid(row=0, column=2, sticky="w")
        self.btn_disconnect = ttk.Button(header, text="Disconnect", command=self._on_disconnect)
        self.btn_disconnect.grid(row=0, column=3, sticky="w", padx=(6, 0))

        ttk.Label(header, text="Position:").grid(row=0, column=4, sticky="e", padx=(16, 4))
        self.lbl_position = ttk.Label(header, textvariable=self.var_position)
        self.lbl_position.grid(row=0, column=5, sticky="w")

        # Canvas frame
        canvas_frame = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        canvas_frame.grid(row=1, column=0, sticky="nsew")
        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            canvas_frame,
            width=self.canvas_size,
            height=self.canvas_size,
            background="#fafafa",
            highlightthickness=1,
            highlightbackground="#cccccc",
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Button-1>", self._on_canvas_click)

        # Controls frame
        controls = ttk.Frame(self.root, padding=(0, 0, 10, 10))
        controls.grid(row=1, column=1, sticky="nsew")
        controls.columnconfigure(0, weight=1)

        # Jog controls
        jog_group = ttk.Labelframe(controls, text="Jog Controls", padding=10)
        jog_group.grid(row=0, column=0, sticky="new", pady=(0, 10))
        jog_group.columnconfigure(1, weight=1)

        ttk.Label(jog_group, text="Step (units)").grid(row=0, column=0, columnspan=3, sticky="w")
        step_entry = ttk.Entry(jog_group, textvariable=self.var_step, width=10)
        step_entry.grid(row=1, column=0, columnspan=3, sticky="we", pady=(0, 6))

        btn_x_neg = ttk.Button(jog_group, text="X-", command=lambda: self._on_jog("x", -1))
        btn_x_pos = ttk.Button(jog_group, text="X+", command=lambda: self._on_jog("x", +1))
        btn_y_neg = ttk.Button(jog_group, text="Y-", command=lambda: self._on_jog("y", -1))
        btn_y_pos = ttk.Button(jog_group, text="Y+", command=lambda: self._on_jog("y", +1))

        # Arrange jog buttons like arrows
        btn_y_pos.grid(row=2, column=1, pady=2)
        btn_x_neg.grid(row=3, column=0, padx=2)
        btn_x_pos.grid(row=3, column=2, padx=2)
        btn_y_neg.grid(row=4, column=1, pady=2)

        btn_home = ttk.Button(jog_group, text="Home (0,0)", command=self._on_home)
        btn_home.grid(row=5, column=0, columnspan=3, sticky="we", pady=(6, 0))

        # Per-axis brief status lines
        axis_group = ttk.Labelframe(controls, text="Axis Status", padding=10)
        axis_group.grid(row=1, column=0, sticky="new", pady=(0, 10))
        ttk.Label(axis_group, text="X:").grid(row=0, column=0, sticky="w")
        ttk.Label(axis_group, textvariable=self.var_status_x).grid(row=0, column=1, sticky="w")
        ttk.Label(axis_group, text="Y:").grid(row=1, column=0, sticky="w")
        ttk.Label(axis_group, textvariable=self.var_status_y).grid(row=1, column=1, sticky="w")

        # FG controls (optional)
        if self.fg is not None:
            fg_group = ttk.Labelframe(controls, text="Function Generator", padding=10)
            fg_group.grid(row=2, column=0, sticky="new")
            fg_group.columnconfigure(1, weight=1)

            fg_toggle = ttk.Checkbutton(
                fg_group, text="Output Enabled", variable=self.var_fg_enabled, command=self._on_fg_toggle
            )
            fg_toggle.grid(row=0, column=0, columnspan=2, sticky="w")

            ttk.Label(fg_group, text="Amplitude (V)").grid(row=1, column=0, sticky="w", pady=(6, 0))
            fg_entry = ttk.Entry(fg_group, textvariable=self.var_fg_amplitude, width=10)
            fg_entry.grid(row=2, column=0, sticky="we")
            ttk.Button(fg_group, text="Apply", command=self._on_apply_amplitude).grid(row=2, column=1, sticky="we", padx=(6, 0))

    # ---------- Canvas helpers ----------
    def _update_canvas_grid(self) -> None:
        c = self.canvas
        c.delete("grid")
        size = self.canvas_size
        mid = size // 2
        # Grid lines every 20 px
        spacing = 20
        for x in range(0, size + 1, spacing):
            c.create_line(x, 0, x, size, fill="#e6e6e6", tags="grid")
        for y in range(0, size + 1, spacing):
            c.create_line(0, y, size, y, fill="#e6e6e6", tags="grid")
        # Axes
        c.create_line(mid, 0, mid, size, fill="#cccccc", width=2, tags="grid")
        c.create_line(0, mid, size, mid, fill="#cccccc", width=2, tags="grid")

    def _canvas_to_world(self, px: int, py: int) -> Tuple[float, float]:
        size = self.canvas_size
        # Map canvas [0..size] to world [0..range]
        wx = (px / float(size)) * self.world_range
        wy = ((size - py) / float(size)) * self.world_range  # invert Y so top is max
        return (wx, wy)

    # ---------- Event Handlers ----------
    def _on_connect(self) -> None:
        try:
            self.motor = KinesisController()
            # Report any initialization errors captured by motor_control
            err_parts = []
            try:
                if getattr(self.motor, "error_x", None):
                    err_parts.append(f"X: {self.motor.error_x}")
                if getattr(self.motor, "error_y", None):
                    err_parts.append(f"Y: {self.motor.error_y}")
            except Exception:
                pass
            if err_parts:
                self.var_status.set("Connected with errors: " + "; ".join(err_parts))
            else:
                self.var_status.set("Connected")
            self._refresh_position()
        except Exception as exc:  # pragma: no cover - UI feedback only
            self.var_status.set(f"Error: {exc}")

    def _on_disconnect(self) -> None:
        try:
            if self.motor is not None:
                try:
                    self.motor.stop_motors()
                except Exception:
                    pass
            self.motor = None
            self.var_status.set("Disconnected")
        except Exception as exc:  # pragma: no cover - UI feedback only
            self.var_status.set(f"Error: {exc}")

    def _on_home(self) -> None:
        if not self._is_connected():
            return
        try:
            # Home using provided API
            self.motor.home_motors(self.var_status_x, self.var_status_y)  # type: ignore[union-attr]
            self._refresh_position()
        except Exception as exc:  # pragma: no cover
            self.var_status.set(f"Error: {exc}")

    def _on_jog(self, axis: str, sign: int) -> None:
        if not self._is_connected():
            return
        try:
            step = float(self.var_step.get()) * float(sign)
        except ValueError:
            step = 1.0 * float(sign)
            self.var_step.set("1.0")
        try:
            if axis.lower() == "x":
                self.motor.move_motor_x(step, self.var_status_x)  # type: ignore[union-attr]
            else:
                self.motor.move_motor_y(step, self.var_status_y)  # type: ignore[union-attr]
            self._refresh_position()
        except Exception as exc:  # pragma: no cover
            self.var_status.set(f"Error: {exc}")

    def _on_canvas_click(self, event: tk.Event) -> None:  # type: ignore[name-defined]
        if not self._is_connected():
            return
        xw, yw = self._canvas_to_world(event.x, event.y)
        try:
            # Clamp to [0, world_range]
            xw = max(0.0, min(self.world_range, xw))
            yw = max(0.0, min(self.world_range, yw))
            self.motor.move_to_target(xw, yw, self.var_status_x, self.var_status_y)  # type: ignore[union-attr]
            self._refresh_position()
        except Exception as exc:  # pragma: no cover
            self.var_status.set(f"Error: {exc}")

    def _on_fg_toggle(self) -> None:
        if self.fg is None or self.var_fg_enabled is None:
            return
        try:
            self.fg.set_output(bool(self.var_fg_enabled.get()))
        except Exception as exc:  # pragma: no cover
            self.var_status.set(f"FG Error: {exc}")

    def _on_apply_amplitude(self) -> None:
        if self.fg is None or self.var_fg_amplitude is None:
            return
        try:
            volts = float(self.var_fg_amplitude.get())
        except ValueError:
            volts = 0.4
            self.var_fg_amplitude.set("0.400")
        try:
            self.fg.set_amplitude(volts)
        except Exception as exc:  # pragma: no cover
            self.var_status.set(f"FG Error: {exc}")

    # ---------- Helpers ----------
    def _refresh_position(self) -> None:
        try:
            if not self._is_connected():
                self.var_position.set("X: --, Y: --")
                return
            x = self.motor.get_position_x()  # type: ignore[union-attr]
            y = self.motor.get_position_y()  # type: ignore[union-attr]
            if x is None or y is None:
                self.var_position.set("X: --, Y: --")
            else:
                self.var_position.set(f"X: {float(x):.2f}, Y: {float(y):.2f}")
        except Exception as exc:  # pragma: no cover
            self.var_status.set(f"Error: {exc}")

    def _is_connected(self) -> bool:
        try:
            return self.motor is not None and (getattr(self.motor, "motor_x", None) or getattr(self.motor, "motor_y", None))
        except Exception:
            return False

    # ---------- Public API ----------
    def run(self) -> None:
        """Start the Tkinter main loop."""
        self.root.mainloop()


if __name__ == "__main__":
    # Open the layout; connect via the Connect button.
    window = MotorControlWindow()
    window.run()


