"""Re-export for backward compatibility: from plotting.sample_plots import SamplePlots."""
from .core.deprecation import warn_old_import

warn_old_import("plotting.sample_plots", "plotting.sample or from plotting.sample.sample_plots")

from .sample.sample_plots import SamplePlots

__all__ = ["SamplePlots"]
