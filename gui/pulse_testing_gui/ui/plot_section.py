"""
Plot section – matplotlib figure and toolbar for result plotting.
Builds the Live Plot LabelFrame; sets gui.fig, gui.ax, gui.canvas, gui.toolbar.
"""

import tkinter as tk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk


def build_plot_section(parent, gui):
    """Build Live Plot (fig, ax, canvas, toolbar)."""
    frame = tk.LabelFrame(parent, text="Live Plot", padx=5, pady=5)
    frame.pack(fill=tk.BOTH, expand=True)

    gui.fig = Figure(figsize=(8, 6), dpi=100)  # Taller plot for better visibility
    gui.ax = gui.fig.add_subplot(111)
    gui.ax.set_title("No data yet")
    gui.ax.set_xlabel("Time (s)")
    gui.ax.set_ylabel("Resistance (Ω)")
    gui.ax.grid(True, alpha=0.3)

    gui.canvas = FigureCanvasTkAgg(gui.fig, master=frame)
    gui.canvas.draw()
    gui.canvas.get_tk_widget().pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

    gui.toolbar = NavigationToolbar2Tk(gui.canvas, frame)
    gui.toolbar.update()
    gui.toolbar.pack(side=tk.TOP, fill=tk.X)
