"""Re-export for backward compatibility: from plotting.section_plots import ..."""
from .core.deprecation import warn_old_import

warn_old_import("plotting.section_plots", "plotting.section or from plotting.section.section_plots")

from .section.section_plots import (
    plot_customization,
    plot_sweeps_by_type,
    plot_sweeps_by_voltage,
    plot_statistical_comparisons,
    create_subplot,
    plot_data,
)

__all__ = [
    "plot_customization",
    "plot_sweeps_by_type",
    "plot_sweeps_by_voltage",
    "plot_statistical_comparisons",
    "create_subplot",
    "plot_data",
]
