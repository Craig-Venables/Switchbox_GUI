"""
Motor Control GUI - UI Builders
===============================

Modular UI construction for the Motor Control GUI.
"""

from gui.motor_control_gui.ui.header import create_header
from gui.motor_control_gui.ui.controls_panel import create_controls_panel
from gui.motor_control_gui.ui.canvas_camera import create_canvas_and_camera
from gui.motor_control_gui.ui.status_bar import create_status_bar
from gui.motor_control_gui.ui.widgets import CollapsibleFrame

__all__ = [
    "create_header",
    "create_controls_panel",
    "create_canvas_and_camera",
    "create_status_bar",
    "CollapsibleFrame",
]
