"""Re-export for backward compatibility: from plotting.endurance_plots import ..."""
from .core.deprecation import warn_old_import

warn_old_import("plotting.endurance_plots", "plotting.endurance or from plotting.endurance.endurance_plots")

from .endurance.endurance_plots import plot_current_vs_cycle, plot_endurance_summary

__all__ = ["plot_current_vs_cycle", "plot_endurance_summary"]
