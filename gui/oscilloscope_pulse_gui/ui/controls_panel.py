"""Left controls panel (all collapsible sections) for Oscilloscope Pulse GUI."""

from __future__ import annotations

from tkinter import ttk

from .action_buttons import create_action_buttons
from .calculator import create_calculator_frame
from .connection import create_connection_frame
from .measurement import create_measurement_frame
from .pulse import create_pulse_frame
from .save_options import create_save_options_frame
from .scope import create_scope_frame
from .status_bar import create_status_bar


def create_controls_panel(gui, parent):
    """Build the left panel with all collapsible sections and action buttons."""
    create_connection_frame(gui, parent)
    create_scope_frame(gui, parent)
    create_pulse_frame(gui, parent)
    create_measurement_frame(gui, parent)
    create_calculator_frame(gui, parent)
    create_save_options_frame(gui, parent)
    create_action_buttons(gui, parent)
    create_status_bar(gui, parent)
