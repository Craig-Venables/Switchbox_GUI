"""Re-export for backward compatibility: from plotting.device_combined_plots import plot_device_combined_sweeps."""
from .core.deprecation import warn_old_import

warn_old_import("plotting.device_combined_plots", "plotting.device or from plotting.device.device_combined_plots")

from .device.device_combined_plots import plot_device_combined_sweeps

__all__ = ["plot_device_combined_sweeps"]
