"""
GUI package
============

This package contains Tkinter-front-end building blocks extracted from
`Measurement_GUI.py`. Each module focuses on a single responsibility:
- `layout_builder`: widget and layout creation
- `plot_panels`: matplotlib figure construction
- `plot_updaters`: background update loops

Having a dedicated package keeps GUI concerns isolated from measurement
logic so we can eventually target alternative toolkits such as Qt.
"""

__all__ = [
    "layout_builder",
    "plot_panels",
    "plot_updaters",
]

