"""
Unified Plotter - Single entry point for all plotting functionality.

This class provides a simple interface to generate all plot types
with minimal configuration.
"""

from pathlib import Path
from typing import Optional, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np

from .base import PlotManager
from .iv_grid import IVGridPlotter
from .conduction import ConductionPlotter
from .sclc_fit import SCLCFitPlotter
from .hdf5_style import HDF5StylePlotter


class UnifiedPlotter:
    """
    Unified interface for all plotting functionality.
    
    Usage:
        plotter = UnifiedPlotter(save_dir="output/plots")
        plotter.plot_all(voltage, current, device_name="Device_1")
    """

    def __init__(
        self,
        save_dir: Optional[Path] = None,
        auto_close: bool = True,
        # IV Grid settings
        iv_figsize: Tuple[int, int] = (12, 9),
        iv_arrows_points: int = 12,
        # Conduction settings
        conduction_figsize: Tuple[int, int] = (12, 9),
        target_slopes: Tuple[float, ...] = (1.0, 2.0, 3.0),
        high_slope_min: Optional[float] = 4.0,
        min_points: int = 8,
        enable_loglog_overlays: bool = True,
        enable_schottky_overlays: bool = True,
        enable_pf_overlays: bool = True,
        target_slopes_schottky: Tuple[float, ...] = (1.0,),
        target_slopes_pf: Tuple[float, ...] = (1.0,),
        schottky_slope_bounds: Optional[Tuple[float, float]] = None,
        pf_slope_bounds: Optional[Tuple[float, float]] = None,
        # SCLC Fit settings
        sclc_figsize: Tuple[int, int] = (7, 6),
        sclc_ref_slope: float = 2.0,
    ):
        """
        Initialize unified plotter with all settings.
        
        Args:
            save_dir: Directory to save plots (creates if doesn't exist)
            auto_close: Automatically close figures after saving
            iv_figsize: Figure size for IV dashboard
            iv_arrows_points: Number of points for averaged IV arrows
            conduction_figsize: Figure size for conduction grid
            target_slopes: Target slopes for log-log fitting (e.g., 1, 2, 3)
            high_slope_min: Minimum slope to search for high-slope regions
            min_points: Minimum points per fitting window
            enable_loglog_overlays: Show slope overlays on log-log plot
            enable_schottky_overlays: Show fits on Schottky plot
            enable_pf_overlays: Show fits on Poole-Frenkel plot
            target_slopes_schottky: Target slopes for Schottky fitting
            target_slopes_pf: Target slopes for Poole-Frenkel fitting
            schottky_slope_bounds: Optional bounds for best-fit Schottky search
            pf_slope_bounds: Optional bounds for best-fit Poole-Frenkel search
            sclc_figsize: Figure size for SCLC fit plot
            sclc_ref_slope: Reference slope line for SCLC plot
        """
        self.save_dir = Path(save_dir) if save_dir else None
        if self.save_dir:
            self.save_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize individual plotters
        self.iv_plotter = IVGridPlotter(save_dir=save_dir)
        self.iv_plotter.figsize = iv_figsize
        
        self.conduction_plotter = ConductionPlotter(
            save_dir=save_dir,
            figsize=conduction_figsize,
            target_slopes=target_slopes,
            high_slope_min=high_slope_min,
            min_points=min_points,
            enable_loglog_overlays=enable_loglog_overlays,
            enable_schottky_overlays=enable_schottky_overlays,
            enable_pf_overlays=enable_pf_overlays,
            target_slopes_schottky=target_slopes_schottky,
            target_slopes_pf=target_slopes_pf,
            schottky_slope_bounds=schottky_slope_bounds,
            pf_slope_bounds=pf_slope_bounds,
        )
        
        self.sclc_plotter = SCLCFitPlotter(save_dir=save_dir, figsize=sclc_figsize)
        
        self.hdf5_plotter = HDF5StylePlotter(save_dir=save_dir, auto_close=auto_close)
        
        # Store settings
        self.iv_arrows_points = iv_arrows_points
        self.sclc_ref_slope = sclc_ref_slope
        self.auto_close = auto_close

    def plot_basic(
        self,
        voltage: Sequence[float],
        current: Sequence[float],
        time: Optional[Sequence[float]] = None,
        device_name: str = "device",
        title_prefix: str = "",
    ) -> dict:
        """
        Generate basic IV dashboard only (fast, always recommended).
        
        Args:
            voltage: Voltage array
            current: Current array
            time: Optional time array
            device_name: Name for file naming and labels
            title_prefix: Optional prefix for plot titles
            
        Returns:
            Dictionary with figure objects
        """
        results = {}
        title_base = f"{title_prefix} {device_name}".strip() if title_prefix else device_name
        
        fig_iv, axes_iv = self.iv_plotter.plot_grid(
            voltage=voltage,
            current=current,
            time=time,
            title=f"{title_base} - IV Dashboard",
            device_label=device_name,
            arrows_points=self.iv_arrows_points,
            save_name=f"{device_name}_iv_dashboard.png" if self.save_dir else None,
        )
        results["iv"] = {"fig": fig_iv, "axes": axes_iv}
        
        return results

    def plot_memristive_analysis(
        self,
        voltage: Sequence[float],
        current: Sequence[float],
        device_name: str = "device",
        title_prefix: str = "",
        include_conduction: bool = True,
        include_sclc: bool = True,
    ) -> dict:
        """
        Generate advanced analysis plots for memristive devices.
        
        This includes conduction mechanism analysis and SCLC fitting.
        Use this when a device has been identified as memristive.
        
        Args:
            voltage: Voltage array
            current: Current array
            device_name: Name for file naming and labels
            title_prefix: Optional prefix for plot titles
            include_conduction: Whether to generate conduction analysis
            include_sclc: Whether to generate SCLC fit plot
            
        Returns:
            Dictionary with figure objects
        """
        results = {}
        title_base = f"{title_prefix} {device_name}".strip() if title_prefix else device_name
        
        # Conduction Grid
        if include_conduction:
            fig_cond, axes_cond = self.conduction_plotter.plot_conduction_grid(
                voltage=voltage,
                current=current,
                title=f"{title_base} - Conduction Analysis",
                device_label=device_name,
                save_name=f"{device_name}_conduction.png" if self.save_dir else None,
            )
            results["conduction"] = {"fig": fig_cond, "axes": axes_cond}
        
        # SCLC Fit
        if include_sclc:
            fig_sclc, ax_sclc = self.sclc_plotter.plot_sclc_fit(
                voltage=voltage,
                current=current,
                title=f"{title_base} - SCLC Fit",
                device_label=device_name,
                ref_slope=self.sclc_ref_slope,
                save_name=f"{device_name}_sclc_fit.png" if self.save_dir else None,
            )
            results["sclc"] = {"fig": fig_sclc, "axes": ax_sclc}
        
        return results

    def plot_all(
        self,
        voltage: Sequence[float],
        current: Sequence[float],
        time: Optional[Sequence[float]] = None,
        device_name: str = "device",
        title_prefix: str = "",
        save_iv: bool = True,
        save_conduction: bool = True,
        save_sclc: bool = True,
    ) -> dict:
        """
        Generate all standard plots for IV data.
        
        Convenience method that calls both plot_basic() and plot_memristive_analysis().
        For conditional plotting, use plot_basic() and plot_memristive_analysis() separately.
        
        Args:
            voltage: Voltage array
            current: Current array
            time: Optional time array
            device_name: Name for file naming and labels
            title_prefix: Optional prefix for plot titles
            save_iv: Whether to save IV dashboard
            save_conduction: Whether to save conduction grid
            save_sclc: Whether to save SCLC fit plot
            
        Returns:
            Dictionary with figure objects and saved paths
        """
        results = {}
        
        # Always plot basic IV dashboard
        if save_iv:
            basic_results = self.plot_basic(voltage, current, time, device_name, title_prefix)
            results.update(basic_results)
        
        # Advanced analysis (if requested)
        if save_conduction or save_sclc:
            memristive_results = self.plot_memristive_analysis(
                voltage, current, device_name, title_prefix,
                include_conduction=save_conduction,
                include_sclc=save_sclc,
            )
            results.update(memristive_results)
        
        return results

    def plot_iv_dashboard(
        self,
        voltage: Sequence[float],
        current: Sequence[float],
        time: Optional[Sequence[float]] = None,
        device_name: str = "device",
        title: Optional[str] = None,
        save_name: Optional[str] = None,
    ):
        """Generate IV dashboard (2x2 grid)."""
        if title is None:
            title = f"{device_name} - IV Dashboard"
        if save_name is None and self.save_dir:
            save_name = f"{device_name}_iv_dashboard.png"
        
        return self.iv_plotter.plot_grid(
            voltage=voltage,
            current=current,
            time=time,
            title=title,
            device_label=device_name,
            arrows_points=self.iv_arrows_points,
            save_name=save_name,
        )

    def plot_conduction_analysis(
        self,
        voltage: Sequence[float],
        current: Sequence[float],
        device_name: str = "device",
        title: Optional[str] = None,
        save_name: Optional[str] = None,
    ):
        """Generate conduction mechanism analysis (2x2 grid)."""
        if title is None:
            title = f"{device_name} - Conduction Analysis"
        if save_name is None and self.save_dir:
            save_name = f"{device_name}_conduction.png"
        
        return self.conduction_plotter.plot_conduction_grid(
            voltage=voltage,
            current=current,
            title=title,
            device_label=device_name,
            save_name=save_name,
        )

    def plot_sclc_fit(
        self,
        voltage: Sequence[float],
        current: Sequence[float],
        device_name: str = "device",
        title: Optional[str] = None,
        save_name: Optional[str] = None,
    ):
        """Generate SCLC fit plot."""
        if title is None:
            title = f"{device_name} - SCLC Fit"
        if save_name is None and self.save_dir:
            save_name = f"{device_name}_sclc_fit.png"
        
        return self.sclc_plotter.plot_sclc_fit(
            voltage=voltage,
            current=current,
            title=title,
            device_label=device_name,
            ref_slope=self.sclc_ref_slope,
            save_name=save_name,
        )

    def plot_conditional(
        self,
        voltage: Sequence[float],
        current: Sequence[float],
        time: Optional[Sequence[float]] = None,
        device_name: str = "device",
        title_prefix: str = "",
        is_memristive: bool = False,
    ) -> dict:
        """
        Conditional plotting: always plot basic IV, optionally plot advanced analysis.
        
        This is a convenience method that combines plot_basic() and plot_memristive_analysis()
        based on the is_memristive flag. Perfect for batch processing.
        
        Args:
            voltage: Voltage array
            current: Current array
            time: Optional time array
            device_name: Name for file naming and labels
            title_prefix: Optional prefix for plot titles
            is_memristive: If True, also generates advanced analysis plots
            
        Returns:
            Dictionary with figure objects
        """
        results = {}
        
        # Always plot basic IV dashboard
        basic_results = self.plot_basic(
            voltage=voltage,
            current=current,
            time=time,
            device_name=device_name,
            title_prefix=title_prefix,
        )
        results.update(basic_results)
        
        # Only plot advanced analysis if memristive
        if is_memristive:
            memristive_results = self.plot_memristive_analysis(
                voltage=voltage,
                current=current,
                device_name=device_name,
                title_prefix=title_prefix,
            )
            results.update(memristive_results)
        
        return results

    def show_all(self):
        """Display all open figures (useful for interactive use)."""
        plt.show()

