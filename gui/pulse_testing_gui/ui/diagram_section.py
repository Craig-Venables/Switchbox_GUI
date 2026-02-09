"""
Pulse diagram section – matplotlib figure showing pulse pattern preview.
Builds the Pulse Pattern Preview LabelFrame; gui must have update_pulse_diagram.
"""

import tkinter as tk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from .pulse_diagram import PulseDiagramHelper


def build_pulse_diagram_section(parent, gui):
    """Build pulse pattern diagram (fig, ax, canvas, helper). Sets gui.diagram_fig, gui.diagram_ax, gui.diagram_canvas, gui.pulse_diagram_helper."""
    frame = tk.LabelFrame(parent, text="📊 Pulse Pattern Preview", padx=5, pady=5)
    frame.pack(fill=tk.X, padx=5, pady=5)

    gui.diagram_fig = Figure(figsize=(7, 1.5), dpi=100)  # Wider, shorter for compact display
    gui.diagram_ax = gui.diagram_fig.add_subplot(111)
    gui.diagram_fig.tight_layout(pad=1.5)  # Reduced padding

    gui.diagram_canvas = FigureCanvasTkAgg(gui.diagram_fig, master=frame)
    gui.diagram_canvas.draw()
    gui.diagram_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    gui.pulse_diagram_helper = PulseDiagramHelper(gui.diagram_ax, gui.diagram_fig)

    gui.update_pulse_diagram()
