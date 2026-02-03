"""
GUI Package – User Interface Components
========================================

Top-level package for all graphical user interfaces in the Switchbox measurement system.
Each submodule provides a self-contained GUI application or component.

Submodules:
-----------
- sample_gui:      Device selection, sample management, and multiplexer routing.
                  Entry point when launching from main.py.

- measurement_gui: Main IV/PMU/SMU measurement interface. Launched from sample_gui
                  when the user starts a measurement. Handles instrument connections,
                  sweep configuration, real-time plotting, and data saving.

- pulse_testing_gui: Pulse testing interface for TSP-based pulse measurements.

- motor_control_gui: XY stage motor control for laser positioning.

- connection_check_gui: Electrical connection verification tool.

- oscilloscope_pulse_gui: Oscilloscope pulse capture and waveform display.
"""

__all__ = [
    "measurement_gui",
    "pulse_testing_gui",
    "sample_gui",
    "motor_control_gui",
    "connection_check_gui",
]

