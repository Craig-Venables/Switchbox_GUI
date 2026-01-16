"""
Device Analysis Visualizer - Qt5 Application

A standalone Qt5 application for visualizing device analysis data with dynamic data discovery,
comprehensive visualizations, and intuitive navigation for quick device assessment.

Features:
- Dynamic data discovery (standard locations + pattern-based fallback)
- Multi-tab visualization interface (Overview, Plots, Metrics, Classification)
- Device filtering by type and score range
- Interactive yield heatmap for device selection
- Comprehensive I-V plots, metrics charts, and classification breakdowns

Usage:
    from Helpers.Data_Analysis import launch_visualizer
    launch_visualizer(sample_path='/path/to/sample')
"""

from .device_visualizer_app import launch_visualizer

__version__ = "1.0.0"
__author__ = "Switchbox GUI Team"

__all__ = ['launch_visualizer']
