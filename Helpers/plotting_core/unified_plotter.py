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
        analysis_data: Optional[dict] = None,
    ) -> dict:
        """
        Generate basic IV dashboard only (fast, always recommended).
        
        Args:
            voltage: Voltage array
            current: Current array
            time: Optional time array
            device_name: Name for file naming and labels
            title_prefix: Optional prefix for plot titles
            analysis_data: Optional analysis results dict to add resistance annotations
            
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
        
        # Add resistance annotations if analysis data is available
        if analysis_data:
            self._add_resistance_annotations(axes_iv[0, 0], voltage, current, analysis_data)  # Linear IV
            self._add_resistance_annotations(axes_iv[0, 1], voltage, current, analysis_data)  # Log IV
        
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
        analysis_data: Optional[dict] = None,
    ):
        """
        Generate IV dashboard (2x2 grid).
        
        Args:
            voltage: Voltage array
            current: Current array
            time: Optional time array
            device_name: Name for file naming and labels
            title: Optional plot title
            save_name: Optional filename for saving
            analysis_data: Optional analysis results dict to add resistance annotations
        """
        if title is None:
            title = f"{device_name} - IV Dashboard"
        if save_name is None and self.save_dir:
            save_name = f"{device_name}_iv_dashboard.png"
        
        fig, axes = self.iv_plotter.plot_grid(
            voltage=voltage,
            current=current,
            time=time,
            title=title,
            device_label=device_name,
            arrows_points=self.iv_arrows_points,
            save_name=save_name,
        )
        
        # Add resistance annotations if analysis data is available
        if analysis_data:
            self._add_resistance_annotations(axes[0, 0], voltage, current, analysis_data)  # Linear IV
            self._add_resistance_annotations(axes[0, 1], voltage, current, analysis_data)  # Log IV
        
        return fig, axes

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
        analysis_data: Optional[dict] = None,
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
            analysis_data: Optional analysis results dict to add resistance annotations
            
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
            analysis_data=analysis_data,
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
    
    @staticmethod
    def _add_resistance_annotations(
        ax,
        voltage: np.ndarray,
        current: np.ndarray,
        analysis_data: dict,
    ) -> None:
        """
        Add resistance annotations (Ron, Roff, switching ratio) to IV plots.
        
        Args:
            ax: Matplotlib axes to annotate
            voltage: Voltage array
            current: Current array
            analysis_data: Analysis results dict containing resistance metrics
        """
        try:
            # Extract resistance metrics from analysis data
            resistance_metrics = analysis_data.get('resistance_metrics', {})
            ron_mean = resistance_metrics.get('ron_mean', None)
            roff_mean = resistance_metrics.get('roff_mean', None)
            switching_ratio = resistance_metrics.get('switching_ratio_mean', None)
            memristivity_score = analysis_data.get('classification', {}).get('memristivity_score', None)
            
            # Helper function to format resistance values
            def format_resistance(r_val):
                """Format resistance with appropriate units."""
                if r_val is None or r_val <= 0:
                    return None
                if r_val >= 1e6:
                    return f"{r_val/1e6:.2f} MΩ"
                elif r_val >= 1e3:
                    return f"{r_val/1e3:.2f} kΩ"
                else:
                    return f"{r_val:.2e} Ω"
            
            # Find positions for annotations
            v_pos = voltage[voltage > 0]
            v_neg = voltage[voltage < 0]
            
            # Add Ron annotation at positive voltage region
            if ron_mean and ron_mean > 0 and len(v_pos) > 0:
                # Find a point in positive voltage region to place annotation
                v_pos_mid = np.median(v_pos) if len(v_pos) > 0 else np.max(voltage) * 0.5
                # Find corresponding current value (approximate)
                v_idx = np.argmin(np.abs(voltage - v_pos_mid))
                if v_idx < len(current):
                    i_pos = current[v_idx]
                    ron_str = format_resistance(ron_mean)
                    if ron_str:
                        ax.annotate(
                            f"Ron: {ron_str}",
                            xy=(v_pos_mid, i_pos),
                            xytext=(10, 10),
                            textcoords='offset points',
                            bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgreen', alpha=0.7),
                            fontsize=9,
                            ha='left',
                            va='bottom'
                        )
            
            # Add Roff annotation at negative voltage region
            if roff_mean and roff_mean > 0 and len(v_neg) > 0:
                # Find a point in negative voltage region to place annotation
                v_neg_mid = np.median(v_neg) if len(v_neg) > 0 else np.min(voltage) * 0.5
                # Find corresponding current value (approximate)
                v_idx = np.argmin(np.abs(voltage - v_neg_mid))
                if v_idx < len(current):
                    i_neg = current[v_idx]
                    roff_str = format_resistance(roff_mean)
                    if roff_str:
                        ax.annotate(
                            f"Roff: {roff_str}",
                            xy=(v_neg_mid, i_neg),
                            xytext=(-10, -20),
                            textcoords='offset points',
                            bbox=dict(boxstyle='round,pad=0.5', facecolor='lightcoral', alpha=0.7),
                            fontsize=9,
                            ha='right',
                            va='top'
                        )
            
            # Add switching ratio and memristivity score in corner
            info_lines = []
            if switching_ratio and switching_ratio > 0:
                info_lines.append(f"Ratio: {switching_ratio:.1f}")
            if memristivity_score is not None:
                info_lines.append(f"Score: {memristivity_score:.0f}")
            
            if info_lines:
                info_text = "\n".join(info_lines)
                ax.text(
                    0.98, 0.02,
                    info_text,
                    transform=ax.transAxes,
                    fontsize=8,
                    verticalalignment='bottom',
                    horizontalalignment='right',
                    bbox=dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.8, edgecolor='gray'),
                )
        except Exception as e:
            # Silently fail if annotation fails (don't break plotting)
            pass

    def plot_endurance_analysis(
        self,
        voltage: Sequence[float],
        current: Sequence[float],
        timestamps: Optional[Sequence[float]] = None,
        device_name: str = "device",
        title_prefix: str = "",
        read_voltage: float = 0.2,
        save_name_cycle_resistance: Optional[str] = None,
        save_name_onoff_ratio: Optional[str] = None,
    ) -> dict:
        """
        Generate endurance analysis plots.
        
        Creates two plots:
        1. Cycle vs Resistance (SET and RESET separately)
        2. Cycle vs ON/OFF Ratio
        
        Args:
            voltage: Voltage array
            current: Current array
            timestamps: Optional time array
            device_name: Name for file naming and labels
            title_prefix: Optional prefix for plot titles
            read_voltage: Voltage at which reads occur (default 0.2V)
            save_name_cycle_resistance: Filename for cycle vs resistance plot
            save_name_onoff_ratio: Filename for ON/OFF ratio plot
            
        Returns:
            Dictionary with figure objects
        """
        results = {}
        v = np.asarray(voltage, dtype=float)
        i = np.asarray(current, dtype=float)
        t = np.asarray(timestamps, dtype=float) if timestamps is not None else np.arange(len(v))
        
        # Detect read measurements (voltage ≈ read_voltage)
        read_tolerance = 0.05  # 50mV tolerance
        read_indices = np.where(np.abs(v - read_voltage) < read_tolerance)[0]
        
        if len(read_indices) < 2:
            # Not enough read measurements, fall back to IV dashboard
            print(f"[ENDURANCE PLOT] Warning: Not enough read measurements detected. Plotting IV dashboard instead.")
            return self.plot_basic(voltage, current, timestamps, device_name, title_prefix)
        
        # Separate SET reads (even indices) and RESET reads (odd indices)
        # Pattern: SET_read, RESET_read, SET_read, RESET_read, ...
        set_read_indices = read_indices[::2]  # Even indices (0, 2, 4, ...)
        reset_read_indices = read_indices[1::2]  # Odd indices (1, 3, 5, ...)
        
        # Calculate resistances
        set_resistances = np.abs(v[set_read_indices] / (i[set_read_indices] + 1e-12))
        reset_resistances = np.abs(v[reset_read_indices] / (i[reset_read_indices] + 1e-12))
        
        # Calculate cycle numbers (1-indexed)
        set_cycles = np.arange(1, len(set_read_indices) + 1)
        reset_cycles = np.arange(1, len(reset_read_indices) + 1)
        
        # Calculate ON/OFF ratios (I_ON / I_OFF)
        # Match cycles: use minimum length to ensure pairs
        min_cycles = min(len(set_read_indices), len(reset_read_indices))
        if min_cycles > 0:
            set_currents = np.abs(i[set_read_indices[:min_cycles]])
            reset_currents = np.abs(i[reset_read_indices[:min_cycles]])
            onoff_ratios = set_currents / (reset_currents + 1e-12)
            ratio_cycles = np.arange(1, min_cycles + 1)
        else:
            onoff_ratios = np.array([])
            ratio_cycles = np.array([])
        
        title_base = f"{title_prefix} {device_name}".strip() if title_prefix else device_name
        
        # Plot 1: Cycle vs Resistance (SET and RESET)
        fig1, ax1 = plt.subplots(figsize=(10, 6))
        if len(set_cycles) > 0:
            ax1.plot(set_cycles, set_resistances, 'o-', color='green', markersize=4, 
                    label='SET (LRS)', linewidth=1.5)
        if len(reset_cycles) > 0:
            ax1.plot(reset_cycles, reset_resistances, 's-', color='red', markersize=4,
                    label='RESET (HRS)', linewidth=1.5)
        ax1.set_xlabel('Cycle Number', fontsize=11)
        ax1.set_ylabel('Resistance (Ω)', fontsize=11)
        ax1.set_title(f"{title_base} - Endurance: Cycle vs Resistance", fontsize=12, fontweight='bold')
        ax1.set_yscale('log')
        ax1.grid(True, alpha=0.3)
        ax1.legend(loc='best')
        fig1.tight_layout()
        
        if save_name_cycle_resistance is None and self.save_dir:
            save_name_cycle_resistance = f"{device_name}_endurance_cycle_resistance.png"
        if save_name_cycle_resistance:
            self.manager.save(fig1, save_name_cycle_resistance)
        results["endurance_cycle_resistance"] = {"fig": fig1, "axes": ax1}
        
        # Plot 2: Cycle vs ON/OFF Ratio
        if len(ratio_cycles) > 0:
            fig2, ax2 = plt.subplots(figsize=(10, 6))
            ax2.plot(ratio_cycles, onoff_ratios, 'o-', color='blue', markersize=4, linewidth=1.5)
            ax2.set_xlabel('Cycle Number', fontsize=11)
            ax2.set_ylabel('ON/OFF Ratio (I_ON / I_OFF)', fontsize=11)
            ax2.set_title(f"{title_base} - Endurance: Cycle vs ON/OFF Ratio", fontsize=12, fontweight='bold')
            ax2.set_yscale('log')
            ax2.grid(True, alpha=0.3)
            fig2.tight_layout()
            
            if save_name_onoff_ratio is None and self.save_dir:
                save_name_onoff_ratio = f"{device_name}_endurance_onoff_ratio.png"
            if save_name_onoff_ratio:
                self.manager.save(fig2, save_name_onoff_ratio)
            results["endurance_onoff_ratio"] = {"fig": fig2, "axes": ax2}
        
        return results
    
    def plot_retention_analysis(
        self,
        voltage: Sequence[float],
        current: Sequence[float],
        timestamps: Optional[Sequence[float]] = None,
        device_name: str = "device",
        title_prefix: str = "",
        read_voltage: float = 0.2,
        save_name_loglog: Optional[str] = None,
        save_name_linear: Optional[str] = None,
        save_name_resistance: Optional[str] = None,
    ) -> dict:
        """
        Generate retention analysis plots.
        
        Creates three plots:
        1. Log-Log: Time vs Current
        2. Linear: Time vs Current
        3. Time vs Resistance
        
        Args:
            voltage: Voltage array
            current: Current array
            timestamps: Optional time array
            device_name: Name for file naming and labels
            title_prefix: Optional prefix for plot titles
            read_voltage: Voltage at which reads occur (default 0.2V)
            save_name_loglog: Filename for log-log plot
            save_name_linear: Filename for linear plot
            save_name_resistance: Filename for resistance plot
            
        Returns:
            Dictionary with figure objects
        """
        results = {}
        v = np.asarray(voltage, dtype=float)
        i = np.asarray(current, dtype=float)
        t = np.asarray(timestamps, dtype=float) if timestamps is not None else np.arange(len(v))
        
        # For retention, all measurements after SET pulse are reads
        # Filter to only read measurements (voltage ≈ read_voltage)
        read_tolerance = 0.05  # 50mV tolerance
        read_indices = np.where(np.abs(v - read_voltage) < read_tolerance)[0]
        
        if len(read_indices) < 2:
            # Not enough read measurements, use all data
            read_indices = np.arange(len(v))
        
        read_times = t[read_indices]
        read_currents = np.abs(i[read_indices])
        read_voltages = v[read_indices]
        
        # Calculate relative time (start from first read)
        if len(read_times) > 0:
            relative_times = read_times - read_times[0]
            # Ensure positive times for log scale
            relative_times = np.maximum(relative_times, 1e-6)
        else:
            relative_times = np.array([])
        
        # Calculate resistances
        resistances = np.abs(read_voltages / (read_currents + 1e-12))
        
        title_base = f"{title_prefix} {device_name}".strip() if title_prefix else device_name
        
        # Plot 1: Log-Log Time vs Current
        if len(relative_times) > 0 and len(read_currents) > 0:
            fig1, ax1 = plt.subplots(figsize=(10, 6))
            ax1.loglog(relative_times, read_currents, 'o-', color='blue', markersize=4, linewidth=1.5)
            ax1.set_xlabel('Time (s)', fontsize=11)
            ax1.set_ylabel('Current (A)', fontsize=11)
            ax1.set_title(f"{title_base} - Retention: Time vs Current (Log-Log)", fontsize=12, fontweight='bold')
            ax1.grid(True, alpha=0.3, which='both')
            fig1.tight_layout()
            
            if save_name_loglog is None and self.save_dir:
                save_name_loglog = f"{device_name}_retention_loglog.png"
            if save_name_loglog:
                self.manager.save(fig1, save_name_loglog)
            results["retention_loglog"] = {"fig": fig1, "axes": ax1}
        
        # Plot 2: Linear Time vs Current
        if len(relative_times) > 0 and len(read_currents) > 0:
            fig2, ax2 = plt.subplots(figsize=(10, 6))
            ax2.plot(relative_times, read_currents, 'o-', color='blue', markersize=4, linewidth=1.5)
            ax2.set_xlabel('Time (s)', fontsize=11)
            ax2.set_ylabel('Current (A)', fontsize=11)
            ax2.set_title(f"{title_base} - Retention: Time vs Current (Linear)", fontsize=12, fontweight='bold')
            ax2.set_yscale('log')  # Keep log scale for current (typical for retention)
            ax2.grid(True, alpha=0.3)
            fig2.tight_layout()
            
            if save_name_linear is None and self.save_dir:
                save_name_linear = f"{device_name}_retention_linear.png"
            if save_name_linear:
                self.manager.save(fig2, save_name_linear)
            results["retention_linear"] = {"fig": fig2, "axes": ax2}
        
        # Plot 3: Time vs Resistance
        if len(relative_times) > 0 and len(resistances) > 0:
            fig3, ax3 = plt.subplots(figsize=(10, 6))
            ax3.plot(relative_times, resistances, 'o-', color='red', markersize=4, linewidth=1.5)
            ax3.set_xlabel('Time (s)', fontsize=11)
            ax3.set_ylabel('Resistance (Ω)', fontsize=11)
            ax3.set_title(f"{title_base} - Retention: Time vs Resistance", fontsize=12, fontweight='bold')
            ax3.set_yscale('log')  # Log scale for resistance
            ax3.grid(True, alpha=0.3)
            fig3.tight_layout()
            
            if save_name_resistance is None and self.save_dir:
                save_name_resistance = f"{device_name}_retention_resistance.png"
            if save_name_resistance:
                self.manager.save(fig3, save_name_resistance)
            results["retention_resistance"] = {"fig": fig3, "axes": ax3}
        
        return results

    def plot_pulse_forming_analysis(
        self,
        voltage: Sequence[float],
        current: Sequence[float],
        timestamps: Optional[Sequence[float]] = None,
        device_name: str = "device",
        title_prefix: str = "",
        forming_metadata: Optional[dict] = None,
        read_voltage: float = 0.1,
        save_name_time_current: Optional[str] = None,
        save_name_pulse_current: Optional[str] = None,
        save_name_voltage_current: Optional[str] = None,
    ) -> dict:
        """
        Generate plots for pulse/forming measurements.
        
        Creates three plots:
        1. Time vs Current (during pulses and at read voltage, separate traces)
        2. Pulse Number vs Current (showing progression)
        3. Voltage vs Current (if voltage was varied during forming)
        
        Args:
            voltage: Voltage array
            current: Current array  
            timestamps: Time array
            device_name: Device identifier
            title_prefix: Optional prefix
            forming_metadata: Dict with forming parameters and results
            read_voltage: Voltage at which reads occur (default 0.1V)
            save_name_time_current: Filename for time vs current plot
            save_name_pulse_current: Filename for pulse number vs current plot
            save_name_voltage_current: Filename for voltage vs current plot
            
        Returns:
            Dictionary with figure objects
        """
        results = {}
        v = np.asarray(voltage, dtype=float)
        i = np.asarray(current, dtype=float)
        t = np.asarray(timestamps, dtype=float) if timestamps is not None else np.arange(len(v))
        
        # Separate pulse measurements (at pulse voltage) from read measurements (at read_voltage)
        read_tolerance = 0.05  # 50mV tolerance
        pulse_indices = np.where(np.abs(v - read_voltage) >= read_tolerance)[0]
        read_indices = np.where(np.abs(v - read_voltage) < read_tolerance)[0]
        
        title_base = f"{title_prefix} {device_name}".strip() if title_prefix else device_name
        
        # Plot 1: Time vs Current (separate traces for pulse and read)
        fig1, ax1 = plt.subplots(figsize=(10, 6))
        if len(pulse_indices) > 0:
            ax1.plot(t[pulse_indices], i[pulse_indices], 'o-', color='red', markersize=3,
                    label='During Pulse', linewidth=1.5, alpha=0.7)
        if len(read_indices) > 0:
            ax1.plot(t[read_indices], i[read_indices], 's-', color='blue', markersize=3,
                    label=f'At Read Voltage ({read_voltage}V)', linewidth=1.5, alpha=0.7)
        
        # Highlight forming success point if metadata available
        if forming_metadata and forming_metadata.get("forming_successful", False):
            if len(t) > 0:
                ax1.axvline(x=t[-1], color='green', linestyle='--', linewidth=2, 
                           label='Forming Complete', alpha=0.7)
        
        ax1.set_xlabel('Time (s)', fontsize=11)
        ax1.set_ylabel('Current (A)', fontsize=11)
        ax1.set_title(f"{title_base} - Forming: Time vs Current", fontsize=12, fontweight='bold')
        ax1.set_yscale('log')
        ax1.grid(True, alpha=0.3)
        ax1.legend(loc='best')
        
        # Add metadata text if available
        if forming_metadata:
            metadata_text = f"Success: {forming_metadata.get('forming_successful', False)}\n"
            metadata_text += f"Final V: {forming_metadata.get('final_voltage', 'N/A')}V\n"
            metadata_text += f"Final t: {forming_metadata.get('final_time', 'N/A')}s\n"
            metadata_text += f"Total Pulses: {forming_metadata.get('total_pulses', 'N/A')}"
            ax1.text(0.02, 0.98, metadata_text, transform=ax1.transAxes,
                    fontsize=9, verticalalignment='top', bbox=dict(boxstyle='round', 
                    facecolor='wheat', alpha=0.5))
        
        fig1.tight_layout()
        
        if save_name_time_current is None and self.save_dir:
            save_name_time_current = f"{device_name}_forming_time_current.png"
        if save_name_time_current:
            self.manager.save(fig1, save_name_time_current)
        results["forming_time_current"] = {"fig": fig1, "axes": ax1}
        
        # Plot 2: Pulse Number vs Current (progression)
        if len(pulse_indices) > 0:
            # Count pulses (each pulse has a corresponding read, so divide by 2)
            pulse_numbers = np.arange(1, len(pulse_indices) + 1)
            pulse_currents = i[pulse_indices]
            
            fig2, ax2 = plt.subplots(figsize=(10, 6))
            ax2.plot(pulse_numbers, pulse_currents, 'o-', color='red', markersize=4, linewidth=1.5)
            
            # Highlight target current if metadata available
            if forming_metadata and 'target_current' in forming_metadata:
                target = forming_metadata.get('target_current', 0)
                ax2.axhline(y=target, color='green', linestyle='--', linewidth=2,
                           label=f'Target Current ({target:.2e}A)', alpha=0.7)
            
            # Highlight forming success point
            if forming_metadata and forming_metadata.get("forming_successful", False):
                if len(pulse_numbers) > 0:
                    ax2.axvline(x=pulse_numbers[-1], color='green', linestyle='--', 
                               linewidth=2, label='Forming Complete', alpha=0.7)
            
            ax2.set_xlabel('Pulse Number', fontsize=11)
            ax2.set_ylabel('Current During Pulse (A)', fontsize=11)
            ax2.set_title(f"{title_base} - Forming: Pulse Number vs Current", fontsize=12, fontweight='bold')
            ax2.set_yscale('log')
            ax2.grid(True, alpha=0.3)
            if forming_metadata and 'target_current' in forming_metadata:
                ax2.legend(loc='best')
            fig2.tight_layout()
            
            if save_name_pulse_current is None and self.save_dir:
                save_name_pulse_current = f"{device_name}_forming_pulse_current.png"
            if save_name_pulse_current:
                self.manager.save(fig2, save_name_pulse_current)
            results["forming_pulse_current"] = {"fig": fig2, "axes": ax2}
        
        # Plot 3: Voltage vs Current (if voltage varied)
        if len(v) > 0:
            unique_voltages = np.unique(v)
            if len(unique_voltages) > 1:  # Only plot if voltage varied
                fig3, ax3 = plt.subplots(figsize=(10, 6))
                # Plot pulse measurements
                if len(pulse_indices) > 0:
                    ax3.scatter(v[pulse_indices], i[pulse_indices], c='red', s=20,
                              label='During Pulse', alpha=0.6)
                # Plot read measurements
                if len(read_indices) > 0:
                    ax3.scatter(v[read_indices], i[read_indices], c='blue', s=20,
                              label=f'At Read Voltage', alpha=0.6)
                
                ax3.set_xlabel('Voltage (V)', fontsize=11)
                ax3.set_ylabel('Current (A)', fontsize=11)
                ax3.set_title(f"{title_base} - Forming: Voltage vs Current", fontsize=12, fontweight='bold')
                ax3.set_yscale('log')
                ax3.grid(True, alpha=0.3)
                ax3.legend(loc='best')
                fig3.tight_layout()
                
                if save_name_voltage_current is None and self.save_dir:
                    save_name_voltage_current = f"{device_name}_forming_voltage_current.png"
                if save_name_voltage_current:
                    self.manager.save(fig3, save_name_voltage_current)
                results["forming_voltage_current"] = {"fig": fig3, "axes": ax3}
        
        return results

    def show_all(self):
        """Display all open figures (useful for interactive use)."""
        plt.show()

