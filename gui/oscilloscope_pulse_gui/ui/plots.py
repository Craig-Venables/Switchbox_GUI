"""Plots and alignment panel for Oscilloscope Pulse GUI."""

from __future__ import annotations


def create_plots(gui, parent):
    """Build matplotlib plots and alignment controls. Delegates to gui._build_plots."""
    gui._build_plots(parent)
