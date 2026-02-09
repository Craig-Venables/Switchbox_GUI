"""
Pulse Testing GUI – UI components
=================================

UI builders for connection, test selection, parameters, plot, pulse diagram, tabs.
Used by TSPTestingGUI (main.py) to build the layout.
"""

from .connection import build_connection_section, toggle_connection_section
from .test_selection import build_test_selection_section
from .diagram_section import build_pulse_diagram_section
from .parameters import build_parameters_section
from .status_section import build_status_section
from .plot_section import build_plot_section
from .tabs_optical import build_optical_tab
from .laser_section import build_laser_section
from .pulse_diagram import PulseDiagramHelper

__all__ = [
    "build_connection_section",
    "toggle_connection_section",
    "build_test_selection_section",
    "build_pulse_diagram_section",
    "build_parameters_section",
    "build_status_section",
    "build_plot_section",
    "build_optical_tab",
    "build_laser_section",
    "PulseDiagramHelper",
]
