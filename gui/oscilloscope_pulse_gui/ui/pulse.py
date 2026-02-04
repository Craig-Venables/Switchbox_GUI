"""Pulse parameters section for Oscilloscope Pulse GUI."""

from __future__ import annotations

from .widgets import create_collapsible_frame


def build_pulse_content(gui, frame):
    """Build pulse parameters content."""
    gui._add_param(frame, "Pulse Voltage (V):", "pulse_voltage", "1.0", ToolTipText="Amplitude of the pulse")
    gui._add_param(frame, "Pulse Duration (s):", "pulse_duration", "0.001", ToolTipText="Width of the pulse")
    gui._add_param(frame, "Bias Voltage (V):", "bias_voltage", "0.2", ToolTipText="Bias level applied before and after the pulse")
    gui._add_param(frame, "Pre-Bias Time (s):", "pre_bias_time", "0.1", ToolTipText="Time at bias voltage before the pulse")
    gui._add_param(frame, "Post-Bias Time (s):", "post_bias_time", "1.0", ToolTipText="Time at bias voltage after the pulse")


def create_pulse_frame(gui, parent):
    """Build collapsible pulse parameters frame."""
    create_collapsible_frame(gui, parent, "Pulse Parameters", lambda f: build_pulse_content(gui, f), default_expanded=True)
