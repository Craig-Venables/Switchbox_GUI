# motor_control.py

from pylablib.devices import Thorlabs
import Equipment.Motor_Controll.config as config
import threading
from typing import Optional, Tuple, Callable

class MotorController:
    """High-level controller for two Thorlabs Kinesis linear stages.

    Provides safe movement with software travel limits, thread-safe stop control,
    and utility helpers to reduce duplication between X and Y axes.
    """

    def __init__(self):
        self.motor_x, self.error_x = self.initialize_motor(config.MOTOR_X_SERIAL)
        self.motor_y, self.error_y = self.initialize_motor(config.MOTOR_Y_SERIAL)
        self.moving = False
        self._stop_event = threading.Event()

    def stop(self) -> None:
        """Request a stop and send immediate stop to both axes."""
        self._stop_event.set()
        if self.motor_x:
            self.motor_x.stop()
        if self.motor_y:
            self.motor_y.stop()
        self.moving = False

    def initialize_motor(self, serial_number: str) -> Tuple[Optional[object], Optional[str]]:
        try:
            motor = Thorlabs.KinesisMotor(serial_number, scale=config.MOTOR_SCALE)
            return motor, None
        except Exception as e:
            return None, str(e)

    def set_velocity_and_acceleration(self, velocity: float, acceleration: float) -> None:
        if self.motor_x:
            self.motor_x.setup_velocity(max_velocity=velocity, acceleration=acceleration)
        if self.motor_y:
            self.motor_y.setup_velocity(max_velocity=velocity, acceleration=acceleration)

    # ------------------------- Helpers -------------------------
    def _within_limits(self, current_pos: float, delta: float) -> bool:
        target = current_pos + delta
        return config.TRAVEL_MIN_MM <= target <= config.TRAVEL_MAX_MM

    def _wait_until_stopped(self, is_moving: Callable[[], bool], stop_callable: Callable[[], None]) -> None:
        while is_moving():
            if self._stop_event.is_set():
                stop_callable()
                return

    def _move_motor(self, axis: str, motor: Optional[object], distance: float, status_var) -> None:
        if not motor:
            status_var.set(f"{axis} Motor not initialized")
            return
        try:
            current_pos = motor.get_position()
            if self._within_limits(current_pos, distance):
                motor.move_by(distance)
                self._wait_until_stopped(motor.is_moving, motor.stop)
                if not self._stop_event.is_set():
                    status_var.set(f"Moved {axis} axis")
            else:
                status_var.set("Error: Movement exceeds limit")
        except Exception as e:
            status_var.set(f"Error: {str(e)}")

    def move_motor_x(self, distance: float, status_var_x) -> None:
        self._move_motor("X", self.motor_x, distance, status_var_x)

    def move_motor_y(self, distance: float, status_var_y) -> None:
        self._move_motor("Y", self.motor_y, distance, status_var_y)

    def move_to_target(self, x_target: float, y_target: float, status_var_x, status_var_y) -> None:
        if not (self.motor_x and self.motor_y):
            status_var_x.set("Motors not initialized")
            status_var_y.set("Motors not initialized")
            return
        try:
            current_x = self.motor_x.get_position()
            current_y = self.motor_y.get_position()
            delta_x = x_target - current_x
            delta_y = y_target - current_y
            self.move_motor_x(delta_x, status_var_x)
            if not self._stop_event.is_set():
                self.move_motor_y(delta_y, status_var_y)
        except Exception as e:
            status_var_x.set(f"Error: {str(e)}")
            status_var_y.set(f"Error: {str(e)}")

    def stop_motors(self) -> None:
        """Immediate stop for both axes without toggling state flags."""
        if self.motor_x:
            self.motor_x.stop()
        if self.motor_y:
            self.motor_y.stop()
        self.moving = False

    def home_motors(self, status_var_x, status_var_y) -> None:
        if self.motor_x:
            try:
                self.motor_x.home()
                self.motor_x.wait_move()
                status_var_x.set("Homed X axis")
            except Exception as e:
                status_var_x.set(f"Error: {str(e)}")
        if self.motor_y:
            try:
                self.motor_y.home()
                self.motor_y.wait_move()
                status_var_y.set("Homed Y axis")
            except Exception as e:
                status_var_y.set(f"Error: {str(e)}")

    def get_position_x(self) -> Optional[float]:
        if self.motor_x:
            return self.motor_x.get_position()
        return None

    def get_position_y(self) -> Optional[float]:
        if self.motor_y:
            return self.motor_y.get_position()
        return None

    def raster_scan(self, distance_x: float, distance_y: float, num_rasters: int, direction: str, status_var_x, status_var_y) -> None:
        self._stop_event.clear()
        try:
            for _ in range(num_rasters):
                if self._stop_event.is_set():
                    break
                if direction == "Horizontal":
                    self.move_motor_x(distance_x, status_var_x)
                    if self._stop_event.is_set():
                        break
                    self.move_motor_y(distance_y, status_var_y)
                    if self._stop_event.is_set():
                        break
                    self.move_motor_x(-distance_x, status_var_x)
                    if self._stop_event.is_set():
                        break
                    self.move_motor_y(distance_y, status_var_y)
                elif direction == "Vertical":
                    self.move_motor_y(distance_y, status_var_y)
                    if self._stop_event.is_set():
                        break
                    self.move_motor_x(distance_x, status_var_x)
                    if self._stop_event.is_set():
                        break
                    self.move_motor_y(-distance_y, status_var_y)
                    if self._stop_event.is_set():
                        break
                    self.move_motor_x(distance_x, status_var_x)
        except Exception as e:
            status_var_x.set(f"Error: {str(e)}")
            status_var_y.set(f"Error: {str(e)}")




