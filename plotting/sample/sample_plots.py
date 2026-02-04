"""
Sample-level analysis plots. All plot implementations for "Run Full Sample Analysis".
Used by analysis.aggregators.sample_analyzer.SampleAnalysisOrchestrator.
Style: use plotting.style for dpi and figsize.
"""

import os
import json
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from typing import Dict, List, Optional, Any, Callable, Tuple

from ..core import style

try:
    import seaborn as sns
    SEABORN_AVAILABLE = True
except ImportError:
    SEABORN_AVAILABLE = False

DEVICE_SIZE_MAPPING = {
    'a': {'size': '200x200um', 'area_um2': 40000},
    'd': {'size': '200x200um', 'area_um2': 40000},
    'h': {'size': '200x200um', 'area_um2': 40000},
    'k': {'size': '200x200um', 'area_um2': 40000},
    'b': {'size': '100x100um', 'area_um2': 10000},
    'e': {'size': '100x100um', 'area_um2': 10000},
    'i': {'size': '100x100um', 'area_um2': 10000},
    'l': {'size': '100x100um', 'area_um2': 10000},
    'c': {'size': '400x400um', 'area_um2': 160000},
    'j': {'size': '400x400um', 'area_um2': 160000},
}


class SamplePlots:
    """Holds data and paths; each method draws one plot and saves to plots_dir. No Origin export here."""
    
    def __init__(
        self,
        devices_data: List[Dict],
        plots_dir: str,
        sample_name: str,
        research_data: Optional[Dict] = None,
        memristive_devices: Optional[List] = None,
        data_origin_formatted_dir: Optional[str] = None,
        size_comparison_dir: Optional[str] = None,
        load_iv_callback: Optional[Callable[[str], Tuple[Optional[np.ndarray], Optional[np.ndarray]]]] = None,
        tracking_dir: Optional[str] = None,
        code_name_filter: Optional[str] = None,
    ):
        self.devices_data = devices_data or []
        self.plots_dir = plots_dir
        self.sample_name = sample_name
        self.research_data = research_data or {}
        self.memristive_devices = memristive_devices or []
        self.data_origin_formatted_dir = data_origin_formatted_dir or ""
        self.size_comparison_dir = size_comparison_dir or ""
        self._load_iv = load_iv_callback
        self._tracking_dir = tracking_dir or ""
        self._code_name_filter = code_name_filter
        self._dpi = style.get_dpi()
    
    def plot_memristivity_heatmap(self) -> None:
        try:
            positions = {}
            for dev in self.devices_data:
                device_id = dev['device_id']
                parts = device_id.split('_')
                if len(parts) >= 3:
                    try:
                        row = parts[-2]
                        col = int(parts[-1])
                        score = dev['classification'].get('memristivity_score', 0)
                        positions[(row, col)] = score
                    except (ValueError, IndexError):
                        continue
            if not positions:
                print("[PLOT] No position data for heatmap")
                return
            rows = sorted(set(r for r, c in positions.keys()))
            cols = sorted(set(c for r, c in positions.keys()))
            grid = np.zeros((len(rows), len(cols)))
            for i, row in enumerate(rows):
                for j, col in enumerate(cols):
                    grid[i, j] = positions.get((row, col), 0)
            w, h = style.get_figsize("heatmap")
            fig, ax = plt.subplots(figsize=(max(w, len(cols) * 0.8), max(h, len(rows) * 0.6)))
            colors = ['#d62728', '#ff7f0e', '#ffd700', '#2ca02c']
            cmap = LinearSegmentedColormap.from_list('memristivity', colors, N=100)
            im = ax.imshow(grid, cmap=cmap, vmin=0, vmax=100, aspect='auto')
            ax.set_xticks(range(len(cols)))
            ax.set_xticklabels(cols)
            ax.set_yticks(range(len(rows)))
            ax.set_yticklabels(rows)
            ax.set_xlabel('Device Number', fontsize=12, fontweight='bold')
            ax.set_ylabel('Section', fontsize=12, fontweight='bold')
            ax.set_title(f'Memristivity Score Heatmap - {self.sample_name}', fontsize=14, fontweight='bold')
            cbar = plt.colorbar(im, ax=ax)
            cbar.set_label('Memristivity Score (0-100)', fontsize=12)
            for i in range(len(rows)):
                for j in range(len(cols)):
                    score = grid[i, j]
                    if score > 0:
                        text_color = 'white' if score < 50 else 'black'
                        ax.text(j, i, f'{score:.0f}', ha='center', va='center',
                                color=text_color, fontsize=8, fontweight='bold')
            plt.tight_layout()
            output_file = os.path.join(self.plots_dir, '01_memristivity_heatmap.png')
            plt.savefig(output_file, dpi=self._dpi, bbox_inches='tight')
            plt.close()
            print(f"[PLOT] Saved: 01_memristivity_heatmap.png")
        except Exception as e:
            print(f"[PLOT ERROR] Heatmap failed: {e}")
            import traceback
            traceback.print_exc()
    
    def plot_conduction_mechanisms(self) -> None:
        try:
            mechanisms = {}
            for dev in self.devices_data:
                mechanism = dev['classification'].get('conduction_mechanism', 'unknown')
                if mechanism is None:
                    mechanism = 'unknown'
                mechanisms[mechanism] = mechanisms.get(mechanism, 0) + 1
            if not mechanisms:
                print("[PLOT] No conduction mechanism data")
                return
            sorted_mechs = sorted(mechanisms.items(), key=lambda x: x[1], reverse=True)
            labels = [str(m[0]).replace('_', ' ').title() for m, _ in sorted_mechs]
            counts = [c for _, c in sorted_mechs]
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=style.get_figsize("double"))
            colors = plt.cm.Set3(np.linspace(0, 1, len(labels)))
            ax1.pie(counts, labels=labels, autopct='%1.1f%%', startangle=90, colors=colors)
            ax1.set_title('Conduction Mechanism Distribution\n(Pie Chart)', fontsize=12, fontweight='bold')
            bars = ax2.barh(labels, counts, color=colors)
            ax2.set_xlabel('Device Count', fontsize=11, fontweight='bold')
            ax2.set_title('Conduction Mechanism Distribution\n(Bar Chart)', fontsize=12, fontweight='bold')
            ax2.grid(axis='x', alpha=0.3)
            for i, (bar, count) in enumerate(zip(bars, counts)):
                ax2.text(count + 0.5, i, str(count), va='center', fontweight='bold')
            plt.tight_layout()
            output_file = os.path.join(self.plots_dir, '02_conduction_mechanisms.png')
            plt.savefig(output_file, dpi=self._dpi, bbox_inches='tight')
            plt.close()
            print(f"[PLOT] Saved: 02_conduction_mechanisms.png")
        except Exception as e:
            print(f"[PLOT ERROR] Conduction mechanisms failed: {e}")
            import traceback
            traceback.print_exc()
    
    def plot_memory_window_quality(self) -> None:
        try:
            ron_stability, roff_stability, overall_quality, separation_ratio = [], [], [], []
            for dev in self.devices_data:
                quality = dev.get('quality', {})
                if not isinstance(quality, dict):
                    continue
                mw_quality = quality.get('memory_window_quality', {})
                if mw_quality and isinstance(mw_quality, dict):
                    ron_stability.append(mw_quality.get('ron_stability', np.nan))
                    roff_stability.append(mw_quality.get('roff_stability', np.nan))
                    overall_quality.append(mw_quality.get('overall_quality_score', np.nan))
                    separation_ratio.append(mw_quality.get('separation_ratio', np.nan))
            if not overall_quality:
                print("[PLOT] No memory window quality data")
                return
            fig, axes = plt.subplots(2, 2, figsize=style.get_figsize("grid_2x2"))
            axes[0, 0].boxplot([x for x in ron_stability if not np.isnan(x)], vert=True)
            axes[0, 0].set_ylabel('Ron Stability (0-100)', fontsize=11, fontweight='bold')
            axes[0, 0].set_title('Ron Stability Distribution', fontsize=12, fontweight='bold')
            axes[0, 0].grid(axis='y', alpha=0.3)
            axes[0, 1].boxplot([x for x in roff_stability if not np.isnan(x)], vert=True)
            axes[0, 1].set_ylabel('Roff Stability (0-100)', fontsize=11, fontweight='bold')
            axes[0, 1].set_title('Roff Stability Distribution', fontsize=12, fontweight='bold')
            axes[0, 1].grid(axis='y', alpha=0.3)
            axes[1, 0].boxplot([x for x in overall_quality if not np.isnan(x)], vert=True)
            axes[1, 0].set_ylabel('Overall Quality Score (0-100)', fontsize=11, fontweight='bold')
            axes[1, 0].set_title('Memory Window Quality Score', fontsize=12, fontweight='bold')
            axes[1, 0].grid(axis='y', alpha=0.3)
            valid_ratios = [x for x in separation_ratio if not np.isnan(x) and x > 0]
            if valid_ratios:
                axes[1, 1].boxplot(valid_ratios, vert=True)
                axes[1, 1].set_yscale('log')
                axes[1, 1].set_ylabel('Separation Ratio (log scale)', fontsize=11, fontweight='bold')
                axes[1, 1].set_title('Separation Ratio Distribution', fontsize=12, fontweight='bold')
                axes[1, 1].grid(axis='y', alpha=0.3)
            plt.suptitle(f'Memory Window Quality Distribution - {self.sample_name}', fontsize=14, fontweight='bold', y=0.995)
            plt.tight_layout()
            output_file = os.path.join(self.plots_dir, '03_memory_window_quality.png')
            plt.savefig(output_file, dpi=self._dpi, bbox_inches='tight')
            plt.close()
            print(f"[PLOT] Saved: 03_memory_window_quality.png")
        except Exception as e:
            print(f"[PLOT ERROR] Memory window quality failed: {e}")
            import traceback
            traceback.print_exc()
    
    def plot_hysteresis_radar(self) -> None:
        try:
            if not self.research_data:
                print("[PLOT] No research data for radar chart")
                return
            features_list = []
            for device_id, research in self.research_data.items():
                hyst_shape = research.get('classification', {}).get('hysteresis_shape', {})
                if hyst_shape:
                    features_list.append({
                        'figure_eight_quality': hyst_shape.get('figure_eight_quality', 0),
                        'smoothness': min(100, np.log10(hyst_shape.get('smoothness_metric', 1)) * 10) if hyst_shape.get('smoothness_metric', 0) > 0 else 0,
                        'lobe_asymmetry': hyst_shape.get('lobe_asymmetry', 0) * 100,
                        'width_variation': (1 - hyst_shape.get('width_variation', 1)) * 100 if hyst_shape.get('width_variation', 1) > 0 else 0
                    })
            if not features_list:
                print("[PLOT] No hysteresis shape data")
                return
            avg_features = {
                'figure_eight_quality': np.mean([f['figure_eight_quality'] for f in features_list]),
                'smoothness': np.mean([f['smoothness'] for f in features_list]),
                'lobe_asymmetry': np.mean([f['lobe_asymmetry'] for f in features_list]),
                'width_variation': np.mean([f['width_variation'] for f in features_list])
            }
            categories = ['Figure-8\nQuality', 'Smoothness', 'Lobe\nAsymmetry', 'Width\nVariation']
            values = [avg_features['figure_eight_quality'], avg_features['smoothness'],
                      avg_features['lobe_asymmetry'], avg_features['width_variation']]
            angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
            values += values[:1]
            angles += angles[:1]
            fig, ax = plt.subplots(figsize=style.get_figsize("polar"), subplot_kw=dict(projection='polar'))
            ax.plot(angles, values, 'o-', linewidth=2, label='Average')
            ax.fill(angles, values, alpha=0.25)
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(categories)
            ax.set_ylim(0, 100)
            ax.set_title(f'Hysteresis Shape Quality (Average)\n{self.sample_name}', fontsize=12, fontweight='bold', pad=20)
            ax.grid(True)
            ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
            plt.tight_layout()
            output_file = os.path.join(self.plots_dir, '04_hysteresis_radar.png')
            plt.savefig(output_file, dpi=self._dpi, bbox_inches='tight')
            plt.close()
            print(f"[PLOT] Saved: 04_hysteresis_radar.png")
        except Exception as e:
            print(f"[PLOT ERROR] Hysteresis radar failed: {e}")
            import traceback
            traceback.print_exc()
    
    def plot_classification_scatter(self) -> None:
        try:
            ron_values, roff_values, scores, device_types, pinched, switching_ratios = [], [], [], [], [], []
            for dev in self.devices_data:
                ron = dev['resistance'].get('ron_mean', None)
                roff = dev['resistance'].get('roff_mean', None)
                score = dev['classification'].get('memristivity_score', 0)
                dtype = dev['classification'].get('device_type', 'unknown')
                is_pinched = dev['hysteresis'].get('pinched', False)
                ratio = dev['resistance'].get('switching_ratio', None)
                if ron is not None and roff is not None:
                    try:
                        ron_val = float(ron) if not (isinstance(ron, float) and np.isnan(ron)) else None
                        roff_val = float(roff) if not (isinstance(roff, float) and np.isnan(roff)) else None
                        if ron_val is not None and roff_val is not None and not np.isnan(ron_val) and not np.isnan(roff_val) and ron_val > 0 and roff_val > 0:
                            ron_values.append(ron_val)
                            roff_values.append(roff_val)
                            scores.append(score)
                            device_types.append(dtype if dtype is not None else 'unknown')
                            pinched.append(is_pinched)
                            safe_ratio = 1
                            if ratio is not None:
                                try:
                                    ratio_float = float(ratio)
                                    if not np.isnan(ratio_float) and ratio_float > 0:
                                        safe_ratio = ratio_float
                                except (ValueError, TypeError):
                                    pass
                            switching_ratios.append(safe_ratio)
                    except (ValueError, TypeError):
                        continue
            if not ron_values:
                print("[PLOT] No resistance data for scatter")
                return
            fig, ax = plt.subplots(figsize=style.get_figsize("scatter"))
            type_shapes = {'memristive': 'o', 'ohmic': 's', 'capacitive': '^', 'unknown': 'x'}
            for dtype in set(device_types):
                mask = [dt == dtype for dt in device_types]
                ron_subset = [r for r, m in zip(ron_values, mask) if m]
                roff_subset = [r for r, m in zip(roff_values, mask) if m]
                score_subset = [s for s, m in zip(scores, mask) if m]
                ratio_subset = [r for r, m in zip(switching_ratios, mask) if m]
                sizes = [min(200, max(20, np.log10(r) * 20)) if r > 1 else 20 for r in ratio_subset]
                ax.scatter(ron_subset, roff_subset, c=score_subset, s=sizes,
                          marker=type_shapes.get(dtype, 'o'), cmap='RdYlGn', vmin=0, vmax=100,
                          alpha=0.6, edgecolors='black', linewidths=0.5, label=dtype.title())
            ax.set_xscale('log')
            ax.set_yscale('log')
            ax.set_xlabel('Ron (Ω)', fontsize=12, fontweight='bold')
            ax.set_ylabel('Roff (Ω)', fontsize=12, fontweight='bold')
            ax.set_title(f'Enhanced Classification: Ron vs Roff\n{self.sample_name}', fontsize=14, fontweight='bold')
            ax.legend(title='Device Type', fontsize=10)
            ax.grid(True, alpha=0.3)
            cbar = plt.colorbar(ax.collections[0], ax=ax)
            cbar.set_label('Memristivity Score', fontsize=11)
            plt.tight_layout()
            output_file = os.path.join(self.plots_dir, '05_classification_scatter.png')
            plt.savefig(output_file, dpi=self._dpi, bbox_inches='tight')
            plt.close()
            print(f"[PLOT] Saved: 05_classification_scatter.png")
        except Exception as e:
            print(f"[PLOT ERROR] Classification scatter failed: {e}")
            import traceback
            traceback.print_exc()
    
    def plot_forming_progress(self) -> None:
        try:
            fig, ax = plt.subplots(figsize=style.get_figsize("single"))
            devices_plotted = 0
            for dev in self.devices_data:
                measurements = dev.get('all_measurements', [])
                if len(measurements) < 2:
                    continue
                scores = []
                for m in measurements:
                    score = m.get('classification', {}).get('memristivity_score', None)
                    if score is not None:
                        try:
                            scores.append(float(score))
                        except (ValueError, TypeError):
                            continue
                if len(scores) < 2:
                    continue
                measurement_nums = list(range(1, len(scores) + 1))
                if len(scores) > 1 and scores[-1] is not None and scores[0] is not None:
                    improvement = scores[-1] - scores[0]
                    if improvement > 15:
                        color, label_suffix = 'green', ' (Forming)'
                    elif improvement < -10:
                        color, label_suffix = 'red', ' (Degrading)'
                    else:
                        color, label_suffix = 'blue', ' (Stable)'
                else:
                    color, label_suffix = 'gray', ''
                ax.plot(measurement_nums, scores, 'o-', color=color, alpha=0.6, linewidth=1.5, markersize=4, label=f"{dev['device_id']}{label_suffix}")
                devices_plotted += 1
            if devices_plotted == 0:
                print("[PLOT] No multi-measurement data for forming progress")
                return
            ax.set_xlabel('Measurement Number', fontsize=12, fontweight='bold')
            ax.set_ylabel('Memristivity Score', fontsize=12, fontweight='bold')
            ax.set_title(f'Forming Progress Tracking - {self.sample_name}', fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3)
            ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8, ncol=2)
            plt.tight_layout()
            output_file = os.path.join(self.plots_dir, '06_forming_progress.png')
            plt.savefig(output_file, dpi=self._dpi, bbox_inches='tight')
            plt.close()
            print(f"[PLOT] Saved: 06_forming_progress.png")
        except Exception as e:
            print(f"[PLOT ERROR] Forming progress failed: {e}")
            import traceback
            traceback.print_exc()
    
    def plot_warning_summary(self) -> None:
        try:
            warning_counts = {}
            for dev in self.devices_data:
                for warning in dev.get('warnings', []):
                    warning_type = warning.split(':')[0].split('.')[0].strip()
                    if not warning_type:
                        warning_type = warning[:50]
                    warning_counts[warning_type] = warning_counts.get(warning_type, 0) + 1
            if not warning_counts:
                print("[PLOT] No warnings to plot")
                return
            sorted_warnings = sorted(warning_counts.items(), key=lambda x: x[1], reverse=True)
            labels = [w[0] for w in sorted_warnings]
            counts = [w[1] for w in sorted_warnings]
            fig, ax = plt.subplots(figsize=(12, max(6, len(labels) * 0.4)))
            bars = ax.barh(labels, counts, color='#ff6b6b')
            ax.set_xlabel('Count', fontsize=12, fontweight='bold')
            ax.set_title(f'Warning Flag Summary - {self.sample_name}', fontsize=14, fontweight='bold')
            ax.grid(axis='x', alpha=0.3)
            for i, (bar, count) in enumerate(zip(bars, counts)):
                ax.text(count + 0.5, i, str(count), va='center', fontweight='bold')
            plt.tight_layout()
            output_file = os.path.join(self.plots_dir, '07_warning_summary.png')
            plt.savefig(output_file, dpi=self._dpi, bbox_inches='tight')
            plt.close()
            print(f"[PLOT] Saved: 07_warning_summary.png")
        except Exception as e:
            print(f"[PLOT ERROR] Warning summary failed: {e}")
            import traceback
            traceback.print_exc()
    
    def plot_research_diagnostics(self) -> None:
        try:
            if not SEABORN_AVAILABLE:
                print("[PLOT] Skipping research diagnostics - seaborn not available")
                return
            if not self.research_data:
                print("[PLOT] No research data for diagnostics")
                return
            data_rows = []
            for device_id, research in self.research_data.items():
                diag = research.get('research_diagnostics', {})
                if diag:
                    data_rows.append({
                        'NDR_Index': diag.get('ndr_index', np.nan),
                        'Kink_Voltage': diag.get('kink_voltage', np.nan),
                        'Pinch_Offset': diag.get('pinch_offset', np.nan) if diag.get('pinch_offset') else np.nan,
                        'Noise_Floor': diag.get('noise_floor', np.nan) if diag.get('noise_floor') else np.nan,
                        'Device_ID': device_id
                    })
            if not data_rows:
                print("[PLOT] No diagnostic data")
                return
            df = pd.DataFrame(data_rows)
            numeric_cols = ['NDR_Index', 'Kink_Voltage', 'Pinch_Offset', 'Noise_Floor']
            df_numeric = df[numeric_cols].dropna()
            if len(df_numeric) < 2:
                print("[PLOT] Insufficient data for pairplot")
                return
            g = sns.pairplot(df_numeric, diag_kind='kde', plot_kws={'alpha': 0.6, 's': 50})
            g.fig.suptitle(f'Research Diagnostics Scatter Matrix - {self.sample_name}', fontsize=14, fontweight='bold', y=1.02)
            output_file = os.path.join(self.plots_dir, '08_research_diagnostics.png')
            plt.savefig(output_file, dpi=self._dpi, bbox_inches='tight')
            plt.close()
            print(f"[PLOT] Saved: 08_research_diagnostics.png")
        except Exception as e:
            print(f"[PLOT ERROR] Research diagnostics failed: {e}")
            import traceback
            traceback.print_exc()
    
    @staticmethod
    def _safe_get_quality_score(dev: Dict) -> float:
        """Safely extract memory window quality score from device data."""
        try:
            quality = dev.get('quality', {})
            if not isinstance(quality, dict):
                return np.nan
            mw_quality = quality.get('memory_window_quality', {})
            if not isinstance(mw_quality, dict):
                return np.nan
            return float(mw_quality.get('overall_quality_score', np.nan))
        except Exception:
            return np.nan
    
    def plot_power_efficiency(self) -> None:
        try:
            if not self.research_data:
                print("[PLOT] No research data for power efficiency")
                return
            scores, power_consumption, energy_per_switch = [], [], []
            for device_id, research in self.research_data.items():
                perf = research.get('performance_metrics', {})
                classification = research.get('classification', {})
                score = classification.get('memristivity_score', 0)
                power = perf.get('power_consumption_mean', np.nan)
                energy = perf.get('energy_per_switch_mean', np.nan)
                if not np.isnan(power) and not np.isnan(energy):
                    scores.append(score)
                    power_consumption.append(power)
                    energy_per_switch.append(energy)
            if not scores:
                print("[PLOT] No power/energy data")
                return
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=style.get_figsize("double"))
            scatter1 = ax1.scatter(scores, power_consumption, c=scores, cmap='RdYlGn', vmin=0, vmax=100, s=100, alpha=0.6, edgecolors='black')
            ax1.set_xlabel('Memristivity Score', fontsize=11, fontweight='bold')
            ax1.set_ylabel('Power Consumption (W)', fontsize=11, fontweight='bold')
            ax1.set_title('Power Consumption vs Performance', fontsize=12, fontweight='bold')
            ax1.grid(True, alpha=0.3)
            plt.colorbar(scatter1, ax=ax1, label='Score')
            ax2.boxplot(energy_per_switch, vert=True)
            ax2.set_ylabel('Energy per Switch (J)', fontsize=11, fontweight='bold')
            ax2.set_title('Energy per Switch Distribution', fontsize=12, fontweight='bold')
            ax2.grid(axis='y', alpha=0.3)
            plt.suptitle(f'Power & Energy Efficiency - {self.sample_name}', fontsize=14, fontweight='bold')
            plt.tight_layout()
            plt.savefig(os.path.join(self.plots_dir, '09_power_efficiency.png'), dpi=self._dpi, bbox_inches='tight')
            plt.close()
            print(f"[PLOT] Saved: 09_power_efficiency.png")
        except Exception as e:
            print(f"[PLOT ERROR] Power efficiency failed: {e}")
            import traceback
            traceback.print_exc()
    
    def plot_device_leaderboard(self) -> None:
        try:
            device_scores = []
            for dev in self.devices_data:
                memristivity = dev.get('classification', {}).get('memristivity_score', None)
                if memristivity is None:
                    memristivity = 0
                else:
                    try:
                        memristivity = float(memristivity)
                        if np.isnan(memristivity):
                            memristivity = 0
                    except (ValueError, TypeError):
                        memristivity = 0
                quality_dict = dev.get('quality', {})
                if isinstance(quality_dict, dict):
                    mw_quality = quality_dict.get('memory_window_quality', {})
                    quality = mw_quality.get('overall_quality_score', 0) if isinstance(mw_quality, dict) else 0
                    stability = mw_quality.get('avg_stability', 0) if isinstance(mw_quality, dict) else 0
                else:
                    quality = stability = 0
                if quality is None:
                    quality = 0
                else:
                    try:
                        quality = float(quality)
                        if np.isnan(quality):
                            quality = 0
                    except (ValueError, TypeError):
                        quality = 0
                if stability is None:
                    stability = 0
                else:
                    try:
                        stability = float(stability)
                        if np.isnan(stability):
                            stability = 0
                    except (ValueError, TypeError):
                        stability = 0
                ratio_val = 1
                sr = dev['resistance'].get('switching_ratio', None)
                if sr is not None:
                    try:
                        ratio_val = float(sr)
                        if np.isnan(ratio_val) or ratio_val <= 0:
                            ratio_val = 1
                    except (ValueError, TypeError):
                        ratio_val = 1
                ratio_score = min(100, np.log10(ratio_val) * 10) if ratio_val > 1 else 0
                composite = (memristivity * 0.4 + quality * 0.3 + ratio_score * 0.2 + stability * 0.1)
                device_scores.append({'device_id': dev['device_id'], 'composite_score': composite, 'memristivity': memristivity, 'quality': quality, 'switching_ratio': sr})
            device_scores.sort(key=lambda x: x['composite_score'], reverse=True)
            top_devices = device_scores[:20]
            if not top_devices:
                print("[PLOT] No devices for leaderboard")
                return
            fig, ax = plt.subplots(figsize=(12, max(8, len(top_devices) * 0.4)))
            device_ids = [d['device_id'] for d in top_devices]
            scores = [d['composite_score'] for d in top_devices]
            colors = ['#4CAF50' if s >= 80 else '#FFA500' if s >= 60 else '#FF9800' if s >= 40 else '#F44336' for s in scores]
            bars = ax.barh(device_ids, scores, color=colors)
            ax.set_xlabel('Composite Score', fontsize=12, fontweight='bold')
            ax.set_title(f'Device Leaderboard (Top 20) - {self.sample_name}', fontsize=14, fontweight='bold')
            ax.grid(axis='x', alpha=0.3)
            for i, (bar, score) in enumerate(zip(bars, scores)):
                ax.text(score + 1, i, f'{score:.1f}', va='center', fontweight='bold')
            plt.tight_layout()
            plt.savefig(os.path.join(self.plots_dir, '10_device_leaderboard.png'), dpi=self._dpi, bbox_inches='tight')
            plt.close()
            print(f"[PLOT] Saved: 10_device_leaderboard.png")
        except Exception as e:
            print(f"[PLOT ERROR] Leaderboard failed: {e}")
            import traceback
            traceback.print_exc()
    
    def plot_spatial_distributions(self) -> None:
        try:
            memristivity_map, quality_map, switching_map = {}, {}, {}
            for dev in self.devices_data:
                device_id = dev['device_id']
                parts = device_id.split('_')
                if len(parts) >= 3:
                    try:
                        row, col = parts[-2], int(parts[-1])
                        memristivity_map[(row, col)] = dev['classification'].get('memristivity_score', 0)
                        quality_dict = dev.get('quality', {})
                        quality_map[(row, col)] = (quality_dict.get('memory_window_quality', {}) or {}).get('overall_quality_score', 0) if isinstance(quality_dict, dict) else 0
                        switching_map[(row, col)] = dev['resistance'].get('switching_ratio', 1)
                    except (ValueError, IndexError):
                        continue
            if not memristivity_map:
                print("[PLOT] No spatial data")
                return
            rows = sorted(set(r for r, c in memristivity_map.keys()))
            cols = sorted(set(c for r, c in memristivity_map.keys()))
            grid_mem = np.zeros((len(rows), len(cols)))
            grid_qual = np.zeros((len(rows), len(cols)))
            grid_switch = np.zeros((len(rows), len(cols)))
            for i, row in enumerate(rows):
                for j, col in enumerate(cols):
                    grid_mem[i, j] = memristivity_map.get((row, col), 0)
                    grid_qual[i, j] = quality_map.get((row, col), 0)
                    grid_switch[i, j] = switching_map.get((row, col), 0)
            fig, axes = plt.subplots(1, 3, figsize=style.get_figsize("grid_1x3"))
            im1 = axes[0].imshow(grid_mem, cmap='RdYlGn', vmin=0, vmax=100, aspect='auto')
            axes[0].set_title('Memristivity Score', fontsize=12, fontweight='bold')
            axes[0].set_xticks(range(len(cols)))
            axes[0].set_xticklabels(cols)
            axes[0].set_yticks(range(len(rows)))
            axes[0].set_yticklabels(rows)
            plt.colorbar(im1, ax=axes[0])
            im2 = axes[1].imshow(grid_qual, cmap='RdYlGn', vmin=0, vmax=100, aspect='auto')
            axes[1].set_title('Memory Window Quality', fontsize=12, fontweight='bold')
            axes[1].set_xticks(range(len(cols)))
            axes[1].set_xticklabels(cols)
            axes[1].set_yticks(range(len(rows)))
            axes[1].set_yticklabels(rows)
            plt.colorbar(im2, ax=axes[1])
            grid_switch_log = np.log10(grid_switch + 1)
            im3 = axes[2].imshow(grid_switch_log, cmap='viridis', aspect='auto')
            axes[2].set_title('Switching Ratio (log)', fontsize=12, fontweight='bold')
            axes[2].set_xticks(range(len(cols)))
            axes[2].set_xticklabels(cols)
            axes[2].set_yticks(range(len(rows)))
            axes[2].set_yticklabels(rows)
            plt.colorbar(im3, ax=axes[2])
            plt.suptitle(f'Spatial Distribution Maps - {self.sample_name}', fontsize=14, fontweight='bold')
            plt.tight_layout()
            plt.savefig(os.path.join(self.plots_dir, '11_spatial_distributions.png'), dpi=self._dpi, bbox_inches='tight')
            plt.close()
            print(f"[PLOT] Saved: 11_spatial_distributions.png")
        except Exception as e:
            print(f"[PLOT ERROR] Spatial distributions failed: {e}")
            import traceback
            traceback.print_exc()
    
    def plot_forming_status(self) -> None:
        try:
            forming = formed = degrading = unstable = 0
            for dev in self.devices_data:
                measurements = dev.get('all_measurements', [])
                if len(measurements) < 2:
                    continue
                scores = [m.get('classification', {}).get('memristivity_score', 0) for m in measurements]
                scores = [s for s in scores if s is not None]
                if len(scores) > 1:
                    improvement = scores[-1] - scores[0]
                    variation = np.std(scores) if len(scores) > 1 else 0
                    if improvement > 15:
                        forming += 1
                    elif improvement < -10:
                        degrading += 1
                    elif variation > 20:
                        unstable += 1
                    else:
                        formed += 1
            if forming + formed + degrading + unstable == 0:
                print("[PLOT] No multi-measurement data for forming status")
                return
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=style.get_figsize("double"))
            sizes = [forming, formed, degrading, unstable]
            labels = ['Forming', 'Formed', 'Degrading', 'Unstable']
            colors = ['#2196F3', '#4CAF50', '#F44336', '#FF9800']
            explode = (0.1, 0, 0.1, 0.1)
            ax1.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.1f%%', shadow=True, startangle=90)
            ax1.set_title('Forming Status Distribution', fontsize=12, fontweight='bold')
            ax2.bar(labels, sizes, color=colors)
            ax2.set_ylabel('Device Count', fontsize=11, fontweight='bold')
            ax2.set_title('Forming Status Count', fontsize=12, fontweight='bold')
            ax2.grid(axis='y', alpha=0.3)
            for i, (label, size) in enumerate(zip(labels, sizes)):
                ax2.text(i, size + 0.5, str(size), ha='center', fontweight='bold')
            plt.suptitle(f'Forming Status Distribution - {self.sample_name}', fontsize=14, fontweight='bold')
            plt.tight_layout()
            plt.savefig(os.path.join(self.plots_dir, '12_forming_status.png'), dpi=self._dpi, bbox_inches='tight')
            plt.close()
            print(f"[PLOT] Saved: 12_forming_status.png")
        except Exception as e:
            print(f"[PLOT ERROR] Forming status failed: {e}")
            import traceback
            traceback.print_exc()
    
    def plot_device_size_comparison(self) -> None:
        try:
            plt.rcParams['text.usetex'] = False
            plt.rcParams['mathtext.default'] = 'regular'
            plt.rcParams['axes.formatter.use_mathtext'] = False
            devices_by_size = {
                '100x100um': [d for d in self.devices_data if d.get('device_size') == '100x100um'],
                '200x200um': [d for d in self.devices_data if d.get('device_size') == '200x200um'],
                '400x400um': [d for d in self.devices_data if d.get('device_size') == '400x400um']
            }
            devices_by_size = {k: v for k, v in devices_by_size.items() if v}
            if not devices_by_size:
                print("[PLOT] No devices with size metadata for size comparison")
                return
            sizes_present = list(devices_by_size.keys())
            fig, axes = plt.subplots(2, 2, figsize=style.get_figsize("grid_2x2_large"))
            fig.suptitle(f'Device Size Comparison - {self.sample_name}', fontsize=16, fontweight='bold')
            size_labels = []
            memristivity_scores = []
            switching_ratios = []
            device_types_by_size = {}
            mean_metrics = {'memristivity': [], 'quality': [], 'switching_ratio': []}
            colors = ['#4CAF50', '#2196F3', '#FF9800']
            for size in sizes_present:
                devices = devices_by_size[size]
                size_labels.append(size)
                scores = [d['classification'].get('memristivity_score', 0) or 0 for d in devices]
                memristivity_scores.append(scores)
                ratios = [d['resistance'].get('switching_ratio', 1) or 1 for d in devices]
                switching_ratios.append(ratios)
                type_counts = {}
                for d in devices:
                    t = d['classification'].get('device_type', 'unknown')
                    type_counts[t] = type_counts.get(t, 0) + 1
                device_types_by_size[size] = type_counts
                mean_metrics['memristivity'].append(np.mean(scores) if scores else 0)
                mean_metrics['quality'].append(np.mean([self._safe_get_quality_score(d) for d in devices]))
                mean_metrics['switching_ratio'].append(np.mean(ratios) if ratios else 1)
            if memristivity_scores:
                bp1 = axes[0, 0].boxplot(memristivity_scores, labels=size_labels, patch_artist=True)
                for patch, color in zip(bp1['boxes'], colors[:len(bp1['boxes'])]):
                    patch.set_facecolor(color)
                    patch.set_alpha(0.7)
                axes[0, 0].set_ylabel('Memristivity Score', fontweight='bold')
                axes[0, 0].set_title('Memristivity Score Distribution', fontweight='bold')
                axes[0, 0].grid(True, alpha=0.3, axis='y')
            if switching_ratios:
                bp2 = axes[0, 1].boxplot(switching_ratios, labels=size_labels, patch_artist=True)
                for patch, color in zip(bp2['boxes'], colors[:len(bp2['boxes'])]):
                    patch.set_facecolor(color)
                    patch.set_alpha(0.7)
                axes[0, 1].set_ylabel('Switching Ratio (Roff/Ron)', fontweight='bold')
                axes[0, 1].set_title('Switching Ratio Distribution', fontweight='bold')
                axes[0, 1].set_yscale('log')
                axes[0, 1].grid(True, alpha=0.3, axis='y')
            type_names = sorted(set(t for counts in device_types_by_size.values() for t in (counts or {}).keys() if t))
            colors_dict = {'memristive': '#4CAF50', 'ohmic': '#9E9E9E', 'capacitive': '#2196F3', 'conductive': '#FF9800', 'memcapacitive': '#9C27B0', 'uncertain': '#F44336'}
            if type_names and device_types_by_size:
                x = np.arange(len(size_labels))
                width = 0.6
                bottom = np.zeros(len(size_labels))
                for tname in type_names:
                    counts = [device_types_by_size[size].get(tname, 0) for size in size_labels]
                    totals = [len(devices_by_size[size]) for size in size_labels]
                    percentages = [100 * c / t if t > 0 else 0 for c, t in zip(counts, totals)]
                    axes[1, 0].bar(x, percentages, width, label=tname.replace('_', ' ').title(), bottom=bottom, color=colors_dict.get(tname, '#757575'))
                    bottom += percentages
                axes[1, 0].set_xlabel('Device Size', fontweight='bold')
                axes[1, 0].set_ylabel('Percentage (%)', fontweight='bold')
                axes[1, 0].set_title('Device Type Distribution by Size', fontweight='bold')
                axes[1, 0].set_xticks(x)
                axes[1, 0].set_xticklabels(size_labels)
                axes[1, 0].legend(bbox_to_anchor=(1.05, 1), loc='upper left')
                axes[1, 0].grid(True, alpha=0.3, axis='y')
            if mean_metrics['memristivity']:
                x = np.arange(len(size_labels))
                width = 0.25
                metrics = ['Memristivity', 'Quality', 'Switching Ratio']
                y_data = [mean_metrics['memristivity'], mean_metrics['quality'], [r if r > 0 else 1 for r in mean_metrics['switching_ratio']]]
                for i, (metric, y_vals) in enumerate(zip(metrics, y_data)):
                    if metric == 'Switching Ratio':
                        y_vals = [v / 10.0 for v in y_vals]
                    offset = (i - 1) * width
                    axes[1, 1].bar(x + offset, y_vals, width, label=metric, alpha=0.8)
                axes[1, 1].set_xlabel('Device Size', fontweight='bold')
                axes[1, 1].set_ylabel('Normalized Score', fontweight='bold')
                axes[1, 1].set_title('Mean Metrics Comparison', fontweight='bold')
                axes[1, 1].set_xticks(x)
                axes[1, 1].set_xticklabels(size_labels)
                axes[1, 1].legend()
                axes[1, 1].grid(True, alpha=0.3, axis='y')
            plt.tight_layout()
            plt.savefig(os.path.join(self.plots_dir, '13_device_size_comparison.png'), dpi=self._dpi, bbox_inches='tight')
            plt.close()
            print(f"[PLOT] Saved: 13_device_size_comparison.png")
        except Exception as e:
            print(f"[PLOT ERROR] Device size comparison failed: {e}")
            import traceback
            traceback.print_exc()
    
    def plot_metric_correlation_heatmap(self) -> None:
        try:
            metrics_data = []
            for dev in self.devices_data:
                row = {
                    'Memristivity_Score': dev['classification'].get('memristivity_score', np.nan),
                    'Confidence': dev['classification'].get('confidence', np.nan),
                    'Ron_Mean': dev['resistance'].get('ron_mean', np.nan),
                    'Roff_Mean': dev['resistance'].get('roff_mean', np.nan),
                    'Switching_Ratio': dev['resistance'].get('switching_ratio', np.nan),
                    'On_Off_Ratio': dev['resistance'].get('on_off_ratio', np.nan),
                    'Memory_Window_Quality': self._safe_get_quality_score(dev),
                    'Total_Measurements': dev.get('total_measurements', 0),
                    'Warning_Count': len(dev.get('warnings', []))
                }
                metrics_data.append(row)
            df = pd.DataFrame(metrics_data).dropna(how='all')
            if len(df) < 3:
                print("[PLOT] Insufficient data for correlation heatmap")
                return
            corr_matrix = df.corr()
            fig, ax = plt.subplots(figsize=style.get_figsize("heatmap"))
            im = ax.imshow(corr_matrix, cmap='RdBu_r', vmin=-1, vmax=1, aspect='auto')
            ax.set_xticks(range(len(corr_matrix.columns)))
            ax.set_yticks(range(len(corr_matrix.columns)))
            ax.set_xticklabels(corr_matrix.columns, rotation=45, ha='right')
            ax.set_yticklabels(corr_matrix.columns)
            for i in range(len(corr_matrix.columns)):
                for j in range(len(corr_matrix.columns)):
                    value = corr_matrix.iloc[i, j]
                    if not np.isnan(value):
                        text_color = 'white' if abs(value) > 0.5 else 'black'
                        ax.text(j, i, f'{value:.2f}', ha='center', va='center', color=text_color, fontsize=9, fontweight='bold')
            ax.set_title(f'Metric Correlation Heatmap - {self.sample_name}', fontsize=14, fontweight='bold', pad=20)
            plt.colorbar(im, ax=ax)
            plt.tight_layout()
            plt.savefig(os.path.join(self.plots_dir, '14_metric_correlation_heatmap.png'), dpi=self._dpi, bbox_inches='tight')
            plt.close()
            print(f"[PLOT] Saved: 14_metric_correlation_heatmap.png")
        except Exception as e:
            print(f"[PLOT ERROR] Correlation heatmap failed: {e}")
            import traceback
            traceback.print_exc()
    
    def plot_section_performance_comparison(self) -> None:
        try:
            sections_data = {}
            for dev in self.devices_data:
                section = dev.get('section')
                if not section:
                    continue
                if section not in sections_data:
                    sections_data[section] = []
                sections_data[section].append(dev)
            if not sections_data:
                print("[PLOT] No section data for comparison")
                return
            sections = sorted(sections_data.keys())
            metrics = {'Memristivity_Score': [], 'Memory_Window_Quality': [], 'Switching_Ratio': [], 'Memristive_Percentage': []}
            section_std = {'Memristivity_Score': [], 'Memory_Window_Quality': [], 'Switching_Ratio': []}
            for section in sections:
                devices = sections_data[section]
                scores = [d['classification'].get('memristivity_score', 0) or 0 for d in devices]
                qualities = [q for q in [self._safe_get_quality_score(d) for d in devices] if not np.isnan(q)]
                ratios = [r for r in [d['resistance'].get('switching_ratio', 1) or 1 for d in devices] if r > 0]
                memristive_count = sum(1 for d in devices if d['classification'].get('device_type') == 'memristive')
                metrics['Memristivity_Score'].append(np.mean(scores) if scores else 0)
                metrics['Memory_Window_Quality'].append(np.mean(qualities) if qualities else 0)
                metrics['Switching_Ratio'].append(np.mean(ratios) if ratios else 1)
                metrics['Memristive_Percentage'].append(100 * memristive_count / len(devices) if devices else 0)
                section_std['Memristivity_Score'].append(np.std(scores) if len(scores) > 1 else 0)
                section_std['Memory_Window_Quality'].append(np.std(qualities) if len(qualities) > 1 else 0)
                section_std['Switching_Ratio'].append(np.std(ratios) if len(ratios) > 1 else 0)
            fig, axes = plt.subplots(2, 2, figsize=style.get_figsize("grid_2x2_large"))
            fig.suptitle(f'Section Performance Comparison - {self.sample_name}', fontsize=16, fontweight='bold')
            x = np.arange(len(sections))
            width = 0.6
            axes[0, 0].bar(x, metrics['Memristivity_Score'], width, yerr=section_std['Memristivity_Score'], capsize=5, color='#4CAF50', alpha=0.7, edgecolor='black')
            axes[0, 0].set_xlabel('Section'); axes[0, 0].set_ylabel('Mean Memristivity Score'); axes[0, 0].set_title('Memristivity Score by Section')
            axes[0, 0].set_xticks(x); axes[0, 0].set_xticklabels(sections); axes[0, 0].grid(axis='y', alpha=0.3); axes[0, 0].set_ylim(0, 100)
            axes[0, 1].bar(x, metrics['Memory_Window_Quality'], width, yerr=section_std['Memory_Window_Quality'], capsize=5, color='#2196F3', alpha=0.7, edgecolor='black')
            axes[0, 1].set_xlabel('Section'); axes[0, 1].set_ylabel('Mean Quality Score'); axes[0, 1].set_title('Memory Window Quality by Section')
            axes[0, 1].set_xticks(x); axes[0, 1].set_xticklabels(sections); axes[0, 1].grid(axis='y', alpha=0.3); axes[0, 1].set_ylim(0, 100)
            axes[1, 0].bar(x, metrics['Memristive_Percentage'], width, color='#FF9800', alpha=0.7, edgecolor='black')
            axes[1, 0].set_xlabel('Section'); axes[1, 0].set_ylabel('Memristive Devices (%)'); axes[1, 0].set_title('Memristive Yield by Section')
            axes[1, 0].set_xticks(x); axes[1, 0].set_xticklabels(sections); axes[1, 0].grid(axis='y', alpha=0.3); axes[1, 0].set_ylim(0, 100)
            axes[1, 1].bar(x, metrics['Switching_Ratio'], width, yerr=section_std['Switching_Ratio'], capsize=5, color='#9C27B0', alpha=0.7, edgecolor='black')
            axes[1, 1].set_xlabel('Section'); axes[1, 1].set_ylabel('Mean Switching Ratio'); axes[1, 1].set_title('Switching Ratio by Section')
            axes[1, 1].set_xticks(x); axes[1, 1].set_xticklabels(sections); axes[1, 1].set_yscale('log'); axes[1, 1].grid(axis='y', alpha=0.3)
            plt.tight_layout()
            plt.savefig(os.path.join(self.plots_dir, '15_section_performance_comparison.png'), dpi=self._dpi, bbox_inches='tight')
            plt.close()
            print(f"[PLOT] Saved: 15_section_performance_comparison.png")
        except Exception as e:
            print(f"[PLOT ERROR] Section comparison failed: {e}")
            import traceback
            traceback.print_exc()
    
    def plot_resistance_distribution_comparison(self) -> None:
        try:
            ron_memristive, roff_memristive, ron_ohmic, roff_ohmic, ron_all, roff_all = [], [], [], [], [], []
            for dev in self.devices_data:
                ron = dev['resistance'].get('ron_mean', None)
                roff = dev['resistance'].get('roff_mean', None)
                dtype = dev['classification'].get('device_type', 'unknown')
                if ron is not None and roff is not None:
                    try:
                        ron_val, roff_val = float(ron), float(roff)
                        if not np.isnan(ron_val) and not np.isnan(roff_val) and ron_val > 0 and roff_val > 0:
                            ron_all.append(ron_val); roff_all.append(roff_val)
                            if dtype == 'memristive':
                                ron_memristive.append(ron_val); roff_memristive.append(roff_val)
                            elif dtype == 'ohmic':
                                ron_ohmic.append(ron_val); roff_ohmic.append(roff_val)
                    except (ValueError, TypeError):
                        continue
            if not ron_all:
                print("[PLOT] No resistance data for distribution comparison")
                return
            fig, axes = plt.subplots(2, 2, figsize=style.get_figsize("grid_2x2_large"))
            fig.suptitle(f'Resistance Distribution Comparison - {self.sample_name}', fontsize=16, fontweight='bold')
            axes[0, 0].hist(np.log10(ron_all), bins=30, alpha=0.7, color='#2196F3', edgecolor='black')
            axes[0, 0].set_xlabel('log10(Ron)'); axes[0, 0].set_ylabel('Device Count'); axes[0, 0].set_title('Ron Distribution (All)')
            axes[0, 0].axvline(np.log10(np.mean(ron_all)), color='red', linestyle='--', linewidth=2); axes[0, 0].grid(alpha=0.3)
            axes[0, 1].hist(np.log10(roff_all), bins=30, alpha=0.7, color='#FF9800', edgecolor='black')
            axes[0, 1].set_xlabel('log10(Roff)'); axes[0, 1].set_ylabel('Device Count'); axes[0, 1].set_title('Roff Distribution (All)')
            axes[0, 1].axvline(np.log10(np.mean(roff_all)), color='red', linestyle='--', linewidth=2); axes[0, 1].grid(alpha=0.3)
            if ron_memristive:
                axes[1, 0].hist(np.log10(ron_memristive), bins=20, alpha=0.6, color='green', label='Memristive', edgecolor='black')
            if ron_ohmic:
                axes[1, 0].hist(np.log10(ron_ohmic), bins=20, alpha=0.6, color='red', label='Ohmic', edgecolor='black')
            axes[1, 0].set_xlabel('log10(Ron)'); axes[1, 0].set_ylabel('Device Count'); axes[1, 0].set_title('Ron by Type'); axes[1, 0].legend(); axes[1, 0].grid(alpha=0.3)
            if roff_memristive:
                axes[1, 1].hist(np.log10(roff_memristive), bins=20, alpha=0.6, color='green', label='Memristive', edgecolor='black')
            if roff_ohmic:
                axes[1, 1].hist(np.log10(roff_ohmic), bins=20, alpha=0.6, color='red', label='Ohmic', edgecolor='black')
            axes[1, 1].set_xlabel('log10(Roff)'); axes[1, 1].set_ylabel('Device Count'); axes[1, 1].set_title('Roff by Type'); axes[1, 1].legend(); axes[1, 1].grid(alpha=0.3)
            plt.tight_layout()
            plt.savefig(os.path.join(self.plots_dir, '16_resistance_distribution_comparison.png'), dpi=self._dpi, bbox_inches='tight')
            plt.close()
            print(f"[PLOT] Saved: 16_resistance_distribution_comparison.png")
        except Exception as e:
            print(f"[PLOT ERROR] Resistance distribution failed: {e}")
            import traceback
            traceback.print_exc()
    
    def plot_yield_dashboard(self) -> None:
        try:
            total_devices = len(self.devices_data)
            memristive_count = len(self.memristive_devices)
            yield_pct = 100 * memristive_count / total_devices if total_devices > 0 else 0
            scores = [d['classification'].get('memristivity_score', 0) or 0 for d in self.devices_data]
            avg_score = np.mean(scores) if scores else 0
            sections_data = {}
            for dev in self.devices_data:
                section = dev.get('section')
                if section:
                    if section not in sections_data:
                        sections_data[section] = {'total': 0, 'memristive': 0}
                    sections_data[section]['total'] += 1
                    if dev['classification'].get('device_type') == 'memristive':
                        sections_data[section]['memristive'] += 1
            sections = sorted(sections_data.keys())
            section_yields = [100 * sections_data[s]['memristive'] / sections_data[s]['total'] if sections_data[s]['total'] > 0 else 0 for s in sections]
            size_data = {}
            for dev in self.devices_data:
                size = dev.get('device_size')
                if size:
                    if size not in size_data:
                        size_data[size] = {'total': 0, 'memristive': 0}
                    size_data[size]['total'] += 1
                    if dev['classification'].get('device_type') == 'memristive':
                        size_data[size]['memristive'] += 1
            sizes = sorted(size_data.keys())
            size_yields = [100 * size_data[s]['memristive'] / size_data[s]['total'] if size_data[s]['total'] > 0 else 0 for s in sizes]
            type_counts = {}
            for dev in self.devices_data:
                t = dev['classification'].get('device_type', 'unknown')
                type_counts[t] = type_counts.get(t, 0) + 1
            fig = plt.figure(figsize=style.get_figsize("dashboard"))
            gs = fig.add_gridspec(3, 4, hspace=0.3, wspace=0.3)
            fig.suptitle(f'Yield and Performance Dashboard - {self.sample_name}', fontsize=18, fontweight='bold', y=0.98)
            ax1 = fig.add_subplot(gs[0, 0])
            ax1.axis('off')
            ax1.text(0.1, 0.5, f"Total Devices: {total_devices}\nMemristive: {memristive_count}\nOverall Yield: {yield_pct:.1f}%\nAvg Score: {avg_score:.1f}/100", fontsize=14, fontweight='bold', verticalalignment='center', family='monospace')
            ax2 = fig.add_subplot(gs[0, 1:3])
            if sections:
                bars = ax2.bar(sections, section_yields, color='#4CAF50', alpha=0.7, edgecolor='black')
                ax2.set_ylabel('Yield (%)'); ax2.set_title('Yield by Section'); ax2.set_ylim(0, 100); ax2.grid(axis='y', alpha=0.3)
                for bar, yld in zip(bars, section_yields):
                    ax2.text(bar.get_x() + bar.get_width()/2, yld + 2, f'{yld:.1f}%', ha='center', fontweight='bold')
            ax3 = fig.add_subplot(gs[0, 3])
            if type_counts:
                labels = list(type_counts.keys())
                sizes_pie = list(type_counts.values())
                colors = plt.cm.Set3(np.linspace(0, 1, len(labels)))
                ax3.pie(sizes_pie, labels=labels, autopct='%1.1f%%', colors=colors, startangle=90)
                ax3.set_title('Device Type Distribution', fontweight='bold')
            ax4 = fig.add_subplot(gs[1, :2])
            if scores:
                ax4.hist(scores, bins=30, color='#2196F3', alpha=0.7, edgecolor='black')
                ax4.axvline(avg_score, color='red', linestyle='--', linewidth=2, label=f'Mean: {avg_score:.1f}')
                ax4.set_xlabel('Memristivity Score'); ax4.set_ylabel('Device Count'); ax4.set_title('Score Distribution'); ax4.legend(); ax4.grid(alpha=0.3)
            ax5 = fig.add_subplot(gs[1, 2:])
            if sizes:
                bars = ax5.bar(sizes, size_yields, color='#FF9800', alpha=0.7, edgecolor='black')
                ax5.set_ylabel('Yield (%)'); ax5.set_title('Yield by Size'); ax5.set_ylim(0, 100); ax5.grid(axis='y', alpha=0.3)
                for bar, yld in zip(bars, size_yields):
                    ax5.text(bar.get_x() + bar.get_width()/2, yld + 2, f'{yld:.1f}%', ha='center', fontweight='bold')
            ax6 = fig.add_subplot(gs[2, :2])
            if sections_data:
                section_avg_scores = {s: np.mean([d['classification'].get('memristivity_score', 0) or 0 for d in self.devices_data if d.get('section') == s]) for s in sections}
                sorted_sections = sorted(section_avg_scores.items(), key=lambda x: x[1], reverse=True)[:5]
                if sorted_sections:
                    secs, scr = zip(*sorted_sections)
                    ax6.barh(secs, scr, color='#9C27B0', alpha=0.7, edgecolor='black')
                    ax6.set_xlabel('Average Score'); ax6.set_title('Top 5 Sections'); ax6.set_xlim(0, 100); ax6.grid(axis='x', alpha=0.3)
            ax7 = fig.add_subplot(gs[2, 2:])
            scores_s = []; quals_s = []
            for dev in self.devices_data:
                sc = dev['classification'].get('memristivity_score', 0) or 0
                q = self._safe_get_quality_score(dev)
                if not np.isnan(q):
                    scores_s.append(sc); quals_s.append(q)
            if scores_s:
                ax7.scatter(scores_s, quals_s, alpha=0.6, s=50, edgecolors='black', linewidth=0.5)
                ax7.set_xlabel('Memristivity Score'); ax7.set_ylabel('Quality Score'); ax7.set_title('Score vs Quality'); ax7.grid(alpha=0.3); ax7.set_xlim(0, 100); ax7.set_ylim(0, 100)
            plt.tight_layout()
            plt.savefig(os.path.join(self.plots_dir, '17_yield_dashboard.png'), dpi=self._dpi, bbox_inches='tight')
            plt.close()
            print(f"[PLOT] Saved: 17_yield_dashboard.png")
        except Exception as e:
            print(f"[PLOT ERROR] Yield dashboard failed: {e}")
            import traceback
            traceback.print_exc()
    
    def plot_device_type_size_matrix(self) -> None:
        try:
            size_type_data = {}
            for dev in self.devices_data:
                size = dev.get('device_size')
                dtype = dev['classification'].get('device_type', 'unknown')
                if size:
                    if size not in size_type_data:
                        size_type_data[size] = {}
                    size_type_data[size][dtype] = size_type_data[size].get(dtype, 0) + 1
            if not size_type_data:
                print("[PLOT] No device size data for type vs size matrix")
                return
            sizes = sorted(size_type_data.keys())
            all_types = sorted(set(t for sizes_dict in size_type_data.values() for t in sizes_dict.keys() if t is not None))
            matrix = np.zeros((len(sizes), len(all_types)))
            for i, size in enumerate(sizes):
                total = sum(size_type_data[size].values())
                for j, dtype in enumerate(all_types):
                    count = size_type_data[size].get(dtype, 0)
                    matrix[i, j] = 100 * count / total if total > 0 else 0
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=style.get_figsize("double"))
            fig.suptitle(f'Device Type vs Size Matrix - {self.sample_name}', fontsize=16, fontweight='bold')
            im = ax1.imshow(matrix, cmap='YlOrRd', aspect='auto', vmin=0, vmax=100)
            ax1.set_xticks(range(len(all_types)))
            ax1.set_yticks(range(len(sizes)))
            ax1.set_xticklabels([t.replace('_', ' ').title() for t in all_types], rotation=45, ha='right')
            ax1.set_yticklabels(sizes)
            ax1.set_xlabel('Device Type', fontweight='bold')
            ax1.set_ylabel('Device Size', fontweight='bold')
            ax1.set_title('Device Type Distribution (%)', fontweight='bold')
            for i in range(len(sizes)):
                for j in range(len(all_types)):
                    value = matrix[i, j]
                    if value > 0:
                        text_color = 'white' if value > 50 else 'black'
                        ax1.text(j, i, f'{value:.0f}%', ha='center', va='center', color=text_color, fontsize=10, fontweight='bold')
            plt.colorbar(im, ax=ax1)
            x = np.arange(len(sizes))
            width = 0.6
            bottom = np.zeros(len(sizes))
            colors_dict = {'memristive': '#4CAF50', 'ohmic': '#9E9E9E', 'capacitive': '#2196F3', 'conductive': '#FF9800', 'memcapacitive': '#9C27B0', 'unknown': '#F44336'}
            colors_list = [colors_dict.get(t, '#757575') for t in all_types]
            for j, dtype in enumerate(all_types):
                values = [100 * size_type_data[size].get(dtype, 0) / sum(size_type_data[size].values()) if sum(size_type_data[size].values()) > 0 else 0 for size in sizes]
                dtype_label = dtype.replace('_', ' ').title() if dtype is not None else 'Unknown'
                ax2.bar(x, values, width, label=dtype_label, bottom=bottom, color=colors_list[j], alpha=0.8, edgecolor='black')
                bottom += values
            ax2.set_xlabel('Device Size', fontweight='bold')
            ax2.set_ylabel('Percentage (%)', fontweight='bold')
            ax2.set_title('Device Type Distribution (Stacked)', fontweight='bold')
            ax2.set_xticks(x)
            ax2.set_xticklabels(sizes)
            ax2.set_ylim(0, 100)
            ax2.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
            ax2.grid(axis='y', alpha=0.3)
            plt.tight_layout()
            plt.savefig(os.path.join(self.plots_dir, '18_device_type_size_matrix.png'), dpi=self._dpi, bbox_inches='tight')
            plt.close()
            print(f"[PLOT] Saved: 18_device_type_size_matrix.png")
        except Exception as e:
            print(f"[PLOT ERROR] Device type vs size matrix failed: {e}")
            import traceback
            traceback.print_exc()
    
    def plot_quality_score_breakdown(self) -> None:
        try:
            ron_stability, roff_stability, separation_ratio, overall_quality, device_ids, sections = [], [], [], [], [], []
            for dev in self.devices_data:
                quality = dev.get('quality', {})
                if not isinstance(quality, dict):
                    continue
                mw_quality = quality.get('memory_window_quality', {})
                if isinstance(mw_quality, dict):
                    ron_stab = mw_quality.get('ron_stability', np.nan)
                    roff_stab = mw_quality.get('roff_stability', np.nan)
                    sep_ratio = mw_quality.get('separation_ratio', np.nan)
                    overall = mw_quality.get('overall_quality_score', np.nan)
                    if not np.isnan(overall):
                        ron_stability.append(ron_stab if not np.isnan(ron_stab) else 0)
                        roff_stability.append(roff_stab if not np.isnan(roff_stab) else 0)
                        separation_ratio.append(sep_ratio if not np.isnan(sep_ratio) else 1)
                        overall_quality.append(overall)
                        device_ids.append(dev['device_id'])
                        sections.append(dev.get('section', 'Unknown'))
            if not overall_quality:
                print("[PLOT] No quality data for breakdown")
                return
            sections_data = {}
            if any(s != 'Unknown' for s in sections):
                for i, section in enumerate(sections):
                    if section not in sections_data:
                        sections_data[section] = {'ron': [], 'roff': [], 'sep': [], 'overall': []}
                    sections_data[section]['ron'].append(ron_stability[i])
                    sections_data[section]['roff'].append(roff_stability[i])
                    sections_data[section]['sep'].append(separation_ratio[i])
                    sections_data[section]['overall'].append(overall_quality[i])
            fig, axes = plt.subplots(2, 2, figsize=style.get_figsize("grid_2x2_large"))
            fig.suptitle(f'Quality Score Breakdown - {self.sample_name}', fontsize=16, fontweight='bold')
            ax1 = axes[0, 0]
            components = ['Ron\nStability', 'Roff\nStability', 'Overall\nQuality']
            means = [np.mean(ron_stability), np.mean(roff_stability), np.mean(overall_quality)]
            stds = [np.std(ron_stability), np.std(roff_stability), np.std(overall_quality)]
            bars = ax1.bar(components, means, yerr=stds, capsize=5, color=['#FF6B6B', '#4ECDC4', '#95E1D3'], alpha=0.7, edgecolor='black')
            ax1.set_ylabel('Score', fontweight='bold')
            ax1.set_title('Average Quality Components', fontweight='bold')
            ax1.set_ylim(0, 100)
            ax1.grid(axis='y', alpha=0.3)
            for bar, mean, std in zip(bars, means, stds):
                ax1.text(bar.get_x() + bar.get_width()/2, mean + std + 2, f'{mean:.1f}', ha='center', fontweight='bold')
            ax2 = axes[0, 1]
            valid_ratios = [r for r in separation_ratio if r > 0]
            if valid_ratios:
                ax2.hist(np.log10(valid_ratios), bins=30, color='#FFA07A', alpha=0.7, edgecolor='black')
                ax2.axvline(np.log10(np.mean(valid_ratios)), color='red', linestyle='--', linewidth=2, label=f'Mean: {np.mean(valid_ratios):.2e}')
                ax2.set_xlabel('log₁₀(Separation Ratio)', fontweight='bold')
                ax2.set_ylabel('Device Count', fontweight='bold')
                ax2.set_title('Separation Ratio Distribution', fontweight='bold')
                ax2.legend()
                ax2.grid(alpha=0.3)
            ax3 = axes[1, 0]
            if sections_data:
                section_names = sorted(sections_data.keys())
                section_means = [np.mean(sections_data[s]['overall']) for s in section_names]
                section_stds = [np.std(sections_data[s]['overall']) for s in section_names]
                x = np.arange(len(section_names))
                ax3.bar(x, section_means, yerr=section_stds, capsize=5, color='#9C27B0', alpha=0.7, edgecolor='black')
                ax3.set_xlabel('Section', fontweight='bold')
                ax3.set_ylabel('Mean Overall Quality Score', fontweight='bold')
                ax3.set_title('Quality Score by Section', fontweight='bold')
                ax3.set_xticks(x)
                ax3.set_xticklabels(section_names)
                ax3.set_ylim(0, 100)
                ax3.grid(axis='y', alpha=0.3)
            else:
                ax3.text(0.5, 0.5, 'No section data available', ha='center', va='center', transform=ax3.transAxes)
                ax3.set_title('Quality Score by Section', fontweight='bold')
            ax4 = axes[1, 1]
            scatter = ax4.scatter(ron_stability, roff_stability, c=overall_quality, cmap='RdYlGn', vmin=0, vmax=100, s=100, alpha=0.6, edgecolors='black', linewidth=0.5)
            ax4.set_xlabel('Ron Stability', fontweight='bold')
            ax4.set_ylabel('Roff Stability', fontweight='bold')
            ax4.set_title('Ron vs Roff Stability', fontweight='bold')
            ax4.set_xlim(0, 100)
            ax4.set_ylim(0, 100)
            ax4.grid(alpha=0.3)
            plt.colorbar(scatter, ax=ax4)
            plt.tight_layout()
            plt.savefig(os.path.join(self.plots_dir, '19_quality_score_breakdown.png'), dpi=self._dpi, bbox_inches='tight')
            plt.close()
            print(f"[PLOT] Saved: 19_quality_score_breakdown.png")
        except Exception as e:
            print(f"[PLOT ERROR] Quality breakdown failed: {e}")
            import traceback
            traceback.print_exc()
    
    def plot_confidence_performance_scatter(self) -> None:
        try:
            confidences, scores, device_types, switching_ratios = [], [], [], []
            for dev in self.devices_data:
                confidence = dev['classification'].get('confidence', np.nan)
                score = dev['classification'].get('memristivity_score', 0) or 0
                dtype = dev['classification'].get('device_type', 'unknown')
                ratio = dev['resistance'].get('switching_ratio', 1) or 1
                if not np.isnan(confidence):
                    confidences.append(confidence * 100)
                    scores.append(score)
                    device_types.append(dtype)
                    switching_ratios.append(ratio)
            if not confidences:
                print("[PLOT] No confidence data for scatter plot")
                return
            fig, axes = plt.subplots(1, 2, figsize=style.get_figsize("double"))
            fig.suptitle(f'Confidence vs Performance - {self.sample_name}', fontsize=16, fontweight='bold')
            ax1 = axes[0]
            type_colors = {'memristive': 'green', 'ohmic': 'red', 'capacitive': 'blue', 'unknown': 'gray', 'conductive': 'orange'}
            for dtype in set(device_types):
                mask = [dt == dtype for dt in device_types]
                conf_subset = [c for c, m in zip(confidences, mask) if m]
                score_subset = [s for s, m in zip(scores, mask) if m]
                ratio_subset = [r for r, m in zip(switching_ratios, mask) if m]
                sizes = [min(200, max(20, np.log10(r) * 20)) if r > 1 else 20 for r in ratio_subset]
                dtype_label = dtype.replace('_', ' ').title() if dtype is not None else 'Unknown'
                ax1.scatter(conf_subset, score_subset, c=type_colors.get(dtype, 'gray'), s=sizes, alpha=0.6, edgecolors='black', linewidth=0.5, label=dtype_label)
            if len(confidences) > 1 and np.std(confidences) > 1e-10:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    warnings.simplefilter("ignore", UserWarning)
                    try:
                        z = np.polyfit(confidences, scores, 1)
                        p = np.poly1d(z)
                        x_line = np.linspace(min(confidences), max(confidences), 100)
                        ax1.plot(x_line, p(x_line), "r--", alpha=0.5, linewidth=2, label='Linear Fit')
                    except (np.linalg.LinAlgError, ValueError):
                        pass
            ax1.axhspan(70, 100, alpha=0.1, color='green')
            ax1.axvspan(70, 100, alpha=0.1, color='green')
            ax1.set_xlabel('Classification Confidence (%)', fontweight='bold')
            ax1.set_ylabel('Memristivity Score', fontweight='bold')
            ax1.set_title('Confidence vs Performance (All Devices)', fontweight='bold')
            ax1.set_xlim(0, 100)
            ax1.set_ylim(0, 100)
            ax1.grid(alpha=0.3)
            ax1.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
            ax2 = axes[1]
            memristive_conf = [c for c, dt in zip(confidences, device_types) if dt == 'memristive']
            memristive_scores = [s for s, dt in zip(scores, device_types) if dt == 'memristive']
            memristive_ratios = [r for r, dt in zip(switching_ratios, device_types) if dt == 'memristive']
            if memristive_conf:
                sizes = [min(200, max(20, np.log10(r) * 20)) if r > 1 else 20 for r in memristive_ratios]
                scatter = ax2.scatter(memristive_conf, memristive_scores, c=memristive_scores, cmap='RdYlGn', vmin=0, vmax=100, s=sizes, alpha=0.7, edgecolors='black', linewidth=0.5)
                if len(memristive_conf) > 1 and np.std(memristive_conf) > 1e-10:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", RuntimeWarning)
                        warnings.simplefilter("ignore", UserWarning)
                        try:
                            z = np.polyfit(memristive_conf, memristive_scores, 1)
                            p = np.poly1d(z)
                            x_line = np.linspace(min(memristive_conf), max(memristive_conf), 100)
                            ax2.plot(x_line, p(x_line), "b--", alpha=0.7, linewidth=2, label='Linear Fit')
                        except (np.linalg.LinAlgError, ValueError):
                            pass
                ax2.set_xlabel('Classification Confidence (%)', fontweight='bold')
                ax2.set_ylabel('Memristivity Score', fontweight='bold')
                ax2.set_title(f'Confidence vs Performance (Memristive, n={len(memristive_conf)})', fontweight='bold')
                ax2.set_xlim(0, 100)
                ax2.set_ylim(0, 100)
                ax2.grid(alpha=0.3)
                ax2.legend()
                plt.colorbar(scatter, ax=ax2)
            else:
                ax2.text(0.5, 0.5, 'No memristive devices', ha='center', va='center', transform=ax2.transAxes, fontsize=14)
                ax2.set_title('Confidence vs Performance (Memristive)', fontweight='bold')
            plt.tight_layout()
            plt.savefig(os.path.join(self.plots_dir, '20_confidence_performance_scatter.png'), dpi=self._dpi, bbox_inches='tight')
            plt.close()
            print(f"[PLOT] Saved: 20_confidence_performance_scatter.png")
        except Exception as e:
            print(f"[PLOT ERROR] Confidence vs performance scatter failed: {e}")
            import traceback
            traceback.print_exc()
    
    def plot_voltage_range_analysis(self) -> None:
        try:
            max_voltages, scores, device_types, sections = [], [], [], []
            for dev in self.devices_data:
                voltage_data = dev.get('voltage', {})
                max_v = voltage_data.get('max_voltage', np.nan)
                if not np.isnan(max_v) and max_v > 0:
                    max_voltages.append(abs(max_v))
                    scores.append(dev['classification'].get('memristivity_score', 0) or 0)
                    device_types.append(dev['classification'].get('device_type', 'unknown'))
                    sections.append(dev.get('section', 'Unknown'))
            if not max_voltages:
                print("[PLOT] No voltage data for voltage range analysis")
                return
            fig, axes = plt.subplots(2, 2, figsize=style.get_figsize("grid_2x2_large"))
            fig.suptitle(f'Voltage Range Analysis - {self.sample_name}', fontsize=16, fontweight='bold')
            ax1 = axes[0, 0]
            ax1.hist(max_voltages, bins=30, color='#2196F3', alpha=0.7, edgecolor='black')
            ax1.axvline(np.mean(max_voltages), color='red', linestyle='--', linewidth=2, label=f'Mean: {np.mean(max_voltages):.2f} V')
            ax1.set_xlabel('Max Voltage (V)', fontweight='bold')
            ax1.set_ylabel('Device Count', fontweight='bold')
            ax1.set_title('Voltage Distribution', fontweight='bold')
            ax1.legend()
            ax1.grid(alpha=0.3)
            ax2 = axes[0, 1]
            type_colors = {'memristive': 'green', 'ohmic': 'red', 'capacitive': 'blue', 'unknown': 'gray'}
            for dtype in set(device_types):
                mask = [dt == dtype for dt in device_types]
                v_subset = [v for v, m in zip(max_voltages, mask) if m]
                s_subset = [s for s, m in zip(scores, mask) if m]
                dtype_label = dtype.replace('_', ' ').title() if dtype is not None else 'Unknown'
                ax2.scatter(v_subset, s_subset, c=type_colors.get(dtype, 'gray'), alpha=0.6, s=50, edgecolors='black', linewidth=0.5, label=dtype_label)
            ax2.set_xlabel('Max Voltage (V)', fontweight='bold')
            ax2.set_ylabel('Memristivity Score', fontweight='bold')
            ax2.set_title('Voltage vs Performance', fontweight='bold')
            ax2.grid(alpha=0.3)
            ax2.legend()
            ax3 = axes[1, 0]
            if any(s != 'Unknown' for s in sections):
                section_voltages = {}
                for v, s in zip(max_voltages, sections):
                    if s != 'Unknown':
                        if s not in section_voltages:
                            section_voltages[s] = []
                        section_voltages[s].append(v)
                if section_voltages:
                    section_names = sorted(section_voltages.keys())
                    voltage_lists = [section_voltages[s] for s in section_names]
                    bp = ax3.boxplot(voltage_lists, labels=section_names, patch_artist=True)
                    for patch in bp['boxes']:
                        patch.set_facecolor('#FF9800')
                        patch.set_alpha(0.7)
                    ax3.set_xlabel('Section', fontweight='bold')
                    ax3.set_ylabel('Max Voltage (V)', fontweight='bold')
                    ax3.set_title('Voltage Range by Section', fontweight='bold')
                    ax3.grid(axis='y', alpha=0.3)
            else:
                ax3.text(0.5, 0.5, 'No section data available', ha='center', va='center', transform=ax3.transAxes)
                ax3.set_title('Voltage Range by Section', fontweight='bold')
            ax4 = axes[1, 1]
            voltage_bins = [0, 0.5, 1.0, 1.5, 2.0, 5.0, 10.0]
            bin_labels = [f'{voltage_bins[i]:.1f}-{voltage_bins[i+1]:.1f}V' for i in range(len(voltage_bins)-1)]
            bin_means, bin_counts = [], []
            for i in range(len(voltage_bins)-1):
                mask = [(v >= voltage_bins[i]) & (v < voltage_bins[i+1]) for v in max_voltages]
                bin_scores = [s for s, m in zip(scores, mask) if m]
                if bin_scores:
                    bin_means.append(np.mean(bin_scores))
                    bin_counts.append(len(bin_scores))
                else:
                    bin_means.append(0)
                    bin_counts.append(0)
            bars = ax4.bar(range(len(bin_labels)), bin_means, color='#4CAF50', alpha=0.7, edgecolor='black')
            ax4.set_xlabel('Voltage Range', fontweight='bold')
            ax4.set_ylabel('Mean Memristivity Score', fontweight='bold')
            ax4.set_title('Performance by Voltage Range', fontweight='bold')
            ax4.set_xticks(range(len(bin_labels)))
            ax4.set_xticklabels(bin_labels, rotation=45, ha='right')
            ax4.set_ylim(0, 100)
            ax4.grid(axis='y', alpha=0.3)
            for i, (bar, count) in enumerate(zip(bars, bin_counts)):
                if count > 0:
                    ax4.text(bar.get_x() + bar.get_width()/2, bin_means[i] + 2, f'n={count}', ha='center', fontsize=9)
            plt.tight_layout()
            plt.savefig(os.path.join(self.plots_dir, '21_voltage_range_analysis.png'), dpi=self._dpi, bbox_inches='tight')
            plt.close()
            print(f"[PLOT] Saved: 21_voltage_range_analysis.png")
        except Exception as e:
            print(f"[PLOT ERROR] Voltage range analysis failed: {e}")
            import traceback
            traceback.print_exc()
    
    def plot_performance_stability_analysis(self) -> None:
        try:
            def is_valid_positive(value):
                try:
                    if value is None:
                        return False
                    val = float(value)
                    return not np.isnan(val) and val > 0
                except (ValueError, TypeError):
                    return False
            devices_with_multiple = []
            for dev in self.devices_data:
                measurements = dev.get('all_measurements', [])
                if len(measurements) >= 3:
                    scores = [m.get('classification', {}).get('memristivity_score', 0) or 0 for m in measurements]
                    rons = [m.get('resistance', {}).get('ron_mean', np.nan) for m in measurements]
                    roffs = [m.get('resistance', {}).get('roff_mean', np.nan) for m in measurements]
                    rons = [r for r in rons if is_valid_positive(r)]
                    roffs = [r for r in roffs if is_valid_positive(r)]
                    if len(scores) >= 3 and len(rons) >= 2 and len(roffs) >= 2:
                        score_cv = np.std(scores) / np.mean(scores) if np.mean(scores) > 0 else 0
                        ron_cv = np.std(rons) / np.mean(rons) if np.mean(rons) > 0 else 0
                        roff_cv = np.std(roffs) / np.mean(roffs) if np.mean(roffs) > 0 else 0
                        devices_with_multiple.append({
                            'device_id': dev['device_id'], 'avg_score': np.mean(scores), 'score_cv': score_cv,
                            'ron_cv': ron_cv, 'roff_cv': roff_cv, 'num_measurements': len(measurements),
                            'device_type': dev['classification'].get('device_type', 'unknown')
                        })
            if not devices_with_multiple:
                print("[PLOT] No devices with multiple measurements for stability analysis")
                return
            fig, axes = plt.subplots(2, 2, figsize=style.get_figsize("grid_2x2_large"))
            fig.suptitle(f'Performance Stability Analysis - {self.sample_name}', fontsize=16, fontweight='bold')
            score_cvs = [d['score_cv'] for d in devices_with_multiple]
            avg_scores = [d['avg_score'] for d in devices_with_multiple]
            ax1 = axes[0, 0]
            ax1.hist(score_cvs, bins=30, color='#2196F3', alpha=0.7, edgecolor='black')
            ax1.axvline(np.mean(score_cvs), color='red', linestyle='--', linewidth=2, label=f'Mean CV: {np.mean(score_cvs):.3f}')
            ax1.set_xlabel('Coefficient of Variation (Score)', fontweight='bold')
            ax1.set_ylabel('Device Count', fontweight='bold')
            ax1.set_title('Score Stability Distribution', fontweight='bold')
            ax1.legend()
            ax1.grid(alpha=0.3)
            ax2 = axes[0, 1]
            scatter = ax2.scatter(score_cvs, avg_scores, c=avg_scores, cmap='RdYlGn', vmin=0, vmax=100, s=100, alpha=0.6, edgecolors='black', linewidth=0.5)
            ax2.set_xlabel('Coefficient of Variation (Stability)', fontweight='bold')
            ax2.set_ylabel('Average Memristivity Score', fontweight='bold')
            ax2.set_title('Stability vs Performance', fontweight='bold')
            ax2.grid(alpha=0.3)
            plt.colorbar(scatter, ax=ax2)
            ax3 = axes[1, 0]
            ron_cvs = [d['ron_cv'] for d in devices_with_multiple if d['ron_cv'] > 0]
            if ron_cvs:
                ax3.hist(ron_cvs, bins=30, color='#FF9800', alpha=0.7, edgecolor='black')
                ax3.axvline(np.mean(ron_cvs), color='red', linestyle='--', linewidth=2, label=f'Mean CV: {np.mean(ron_cvs):.3f}')
                ax3.set_xlabel('Coefficient of Variation (Ron)', fontweight='bold')
                ax3.set_ylabel('Device Count', fontweight='bold')
                ax3.set_title('Ron Stability Distribution', fontweight='bold')
                ax3.legend()
                ax3.grid(alpha=0.3)
            else:
                ax3.text(0.5, 0.5, 'No Ron stability data', ha='center', va='center', transform=ax3.transAxes)
            ax4 = axes[1, 1]
            roff_cvs = [d['roff_cv'] for d in devices_with_multiple if d['roff_cv'] > 0]
            if roff_cvs:
                ax4.hist(roff_cvs, bins=30, color='#9C27B0', alpha=0.7, edgecolor='black')
                ax4.axvline(np.mean(roff_cvs), color='red', linestyle='--', linewidth=2, label=f'Mean CV: {np.mean(roff_cvs):.3f}')
                ax4.set_xlabel('Coefficient of Variation (Roff)', fontweight='bold')
                ax4.set_ylabel('Device Count', fontweight='bold')
                ax4.set_title('Roff Stability Distribution', fontweight='bold')
                ax4.legend()
                ax4.grid(alpha=0.3)
            else:
                ax4.text(0.5, 0.5, 'No Roff stability data', ha='center', va='center', transform=ax4.transAxes)
            plt.tight_layout()
            plt.savefig(os.path.join(self.plots_dir, '22_performance_stability_analysis.png'), dpi=self._dpi, bbox_inches='tight')
            plt.close()
            print(f"[PLOT] Saved: 22_performance_stability_analysis.png")
        except Exception as e:
            print(f"[PLOT ERROR] Performance stability analysis failed: {e}")
            import traceback
            traceback.print_exc()
    
    def plot_warning_analysis_dashboard(self) -> None:
        try:
            warning_types, warning_devices = {}, {}
            devices_with_warnings, devices_without_warnings = [], []
            for dev in self.devices_data:
                warnings_list = dev.get('warnings', [])
                score = dev['classification'].get('memristivity_score', 0) or 0
                dtype = dev['classification'].get('device_type', 'unknown')
                if warnings_list:
                    devices_with_warnings.append({'score': score, 'type': dtype})
                    for warning in warnings_list:
                        warning_type = warning.split(':')[0].split('.')[0].strip()[:50]
                        if warning_type:
                            warning_types[warning_type] = warning_types.get(warning_type, 0) + 1
                            if warning_type not in warning_devices:
                                warning_devices[warning_type] = []
                            warning_devices[warning_type].append(score)
                else:
                    devices_without_warnings.append({'score': score, 'type': dtype})
            if not warning_types:
                print("[PLOT] No warnings found for analysis")
                return
            fig, axes = plt.subplots(2, 2, figsize=style.get_figsize("grid_2x2_large"))
            fig.suptitle(f'Warning Analysis Dashboard - {self.sample_name}', fontsize=16, fontweight='bold')
            ax1 = axes[0, 0]
            sorted_warnings = sorted(warning_types.items(), key=lambda x: x[1], reverse=True)[:10]
            labels = [w[0] for w in sorted_warnings]
            counts = [w[1] for w in sorted_warnings]
            bars = ax1.barh(range(len(labels)), counts, color='#F44336', alpha=0.7, edgecolor='black')
            ax1.set_yticks(range(len(labels)))
            ax1.set_yticklabels(labels)
            ax1.set_xlabel('Warning Count', fontweight='bold')
            ax1.set_title('Most Common Warnings', fontweight='bold')
            ax1.grid(axis='x', alpha=0.3)
            for i, (bar, count) in enumerate(zip(bars, counts)):
                ax1.text(count + 0.5, i, str(count), va='center', fontweight='bold')
            ax2 = axes[0, 1]
            scores_with = [d['score'] for d in devices_with_warnings]
            scores_without = [d['score'] for d in devices_without_warnings]
            if scores_with and scores_without:
                ax2.hist(scores_with, bins=20, alpha=0.6, label=f'With Warnings (n={len(scores_with)})', color='#F44336', edgecolor='black')
                ax2.hist(scores_without, bins=20, alpha=0.6, label=f'No Warnings (n={len(scores_without)})', color='#4CAF50', edgecolor='black')
                ax2.axvline(np.mean(scores_with), color='red', linestyle='--', linewidth=2)
                ax2.axvline(np.mean(scores_without), color='green', linestyle='--', linewidth=2)
                ax2.set_xlabel('Memristivity Score', fontweight='bold')
                ax2.set_ylabel('Device Count', fontweight='bold')
                ax2.set_title('Score Distribution: With vs Without Warnings', fontweight='bold')
                ax2.legend()
                ax2.grid(alpha=0.3)
            ax3 = axes[1, 0]
            warning_avg_scores = {wt: np.mean(scores) for wt, scores in warning_devices.items() if scores}
            sorted_avg = sorted(warning_avg_scores.items(), key=lambda x: x[1])[:10]
            if sorted_avg:
                labels_avg = [w[0] for w in sorted_avg]
                avg_scores = [w[1] for w in sorted_avg]
                bars = ax3.barh(range(len(labels_avg)), avg_scores, color='#FF9800', alpha=0.7, edgecolor='black')
                ax3.set_yticks(range(len(labels_avg)))
                ax3.set_yticklabels(labels_avg, fontsize=8)
                ax3.set_xlabel('Average Memristivity Score', fontweight='bold')
                ax3.set_title('Average Score by Warning Type', fontweight='bold')
                ax3.set_xlim(0, 100)
                ax3.grid(axis='x', alpha=0.3)
            ax4 = axes[1, 1]
            warning_counts_list = [len(dev.get('warnings', [])) for dev in self.devices_data]
            scores_list = [dev['classification'].get('memristivity_score', 0) or 0 for dev in self.devices_data]
            scatter = ax4.scatter(warning_counts_list, scores_list, alpha=0.6, s=50, c=scores_list, cmap='RdYlGn', vmin=0, vmax=100, edgecolors='black', linewidth=0.5)
            ax4.set_xlabel('Number of Warnings', fontweight='bold')
            ax4.set_ylabel('Memristivity Score', fontweight='bold')
            ax4.set_title('Warning Count vs Performance', fontweight='bold')
            ax4.grid(alpha=0.3)
            plt.colorbar(scatter, ax=ax4)
            plt.tight_layout()
            plt.savefig(os.path.join(self.plots_dir, '23_warning_analysis_dashboard.png'), dpi=self._dpi, bbox_inches='tight')
            plt.close()
            print(f"[PLOT] Saved: 23_warning_analysis_dashboard.png")
        except Exception as e:
            print(f"[PLOT ERROR] Warning analysis dashboard failed: {e}")
            import traceback
            traceback.print_exc()
    
    def plot_ratio_comparison(self) -> None:
        try:
            switching_ratios, on_off_ratios, scores, device_types = [], [], [], []
            for dev in self.devices_data:
                switching = dev['resistance'].get('switching_ratio', None)
                on_off = dev['resistance'].get('on_off_ratio', None)
                score = dev['classification'].get('memristivity_score', 0) or 0
                dtype = dev['classification'].get('device_type', 'unknown')
                if switching is not None and on_off is not None:
                    try:
                        switching_val, on_off_val = float(switching), float(on_off)
                        if not np.isnan(switching_val) and not np.isnan(on_off_val) and switching_val > 0 and on_off_val > 0:
                            switching_ratios.append(switching_val)
                            on_off_ratios.append(on_off_val)
                            scores.append(score)
                            device_types.append(dtype if dtype is not None else 'unknown')
                    except (ValueError, TypeError):
                        continue
            if not switching_ratios:
                print("[PLOT] No ratio data for comparison")
                return
            fig, axes = plt.subplots(1, 2, figsize=style.get_figsize("double"))
            fig.suptitle(f'On/Off Ratio vs Switching Ratio - {self.sample_name}', fontsize=16, fontweight='bold')
            ax1 = axes[0]
            type_colors = {'memristive': 'green', 'ohmic': 'red', 'capacitive': 'blue', 'unknown': 'gray'}
            for dtype in set(device_types):
                mask = [dt == dtype for dt in device_types]
                switch_subset = [s for s, m in zip(switching_ratios, mask) if m]
                onoff_subset = [o for o, m in zip(on_off_ratios, mask) if m]
                dtype_label = dtype.replace('_', ' ').title() if dtype is not None else 'Unknown'
                ax1.scatter(switch_subset, onoff_subset, c=type_colors.get(dtype, 'gray'), alpha=0.6, s=50, edgecolors='black', linewidth=0.5, label=dtype_label)
            max_val = max(max(switching_ratios), max(on_off_ratios))
            ax1.plot([1, max_val], [1, max_val], 'k--', alpha=0.5, label='1:1 Line')
            ax1.set_xscale('log')
            ax1.set_yscale('log')
            ax1.set_xlabel('Switching Ratio (Roff/Ron)', fontweight='bold')
            ax1.set_ylabel('On/Off Ratio', fontweight='bold')
            ax1.set_title('Ratio Comparison', fontweight='bold')
            ax1.grid(alpha=0.3)
            ax1.legend()
            ax2 = axes[1]
            ax2.hist(np.log10(switching_ratios), bins=30, alpha=0.6, label='Switching Ratio', color='#2196F3', edgecolor='black')
            ax2.hist(np.log10(on_off_ratios), bins=30, alpha=0.6, label='On/Off Ratio', color='#FF9800', edgecolor='black')
            ax2.set_xlabel('log₁₀(Ratio)', fontweight='bold')
            ax2.set_ylabel('Device Count', fontweight='bold')
            ax2.set_title('Ratio Distribution Comparison', fontweight='bold')
            ax2.legend()
            ax2.grid(alpha=0.3)
            plt.tight_layout()
            plt.savefig(os.path.join(self.plots_dir, '24_ratio_comparison.png'), dpi=self._dpi, bbox_inches='tight')
            plt.close()
            print(f"[PLOT] Saved: 24_ratio_comparison.png")
        except Exception as e:
            print(f"[PLOT ERROR] Ratio comparison failed: {e}")
            import traceback
            traceback.print_exc()
    
    def plot_section_spatial_gradient(self) -> None:
        try:
            section_positions = {}
            for dev in self.devices_data:
                section = dev.get('section')
                if section:
                    if section not in section_positions:
                        section_positions[section] = {'scores': [], 'qualities': [], 'yield': 0, 'total': 0}
                    section_positions[section]['scores'].append(dev['classification'].get('memristivity_score', 0) or 0)
                    quality = self._safe_get_quality_score(dev)
                    if not np.isnan(quality):
                        section_positions[section]['qualities'].append(quality)
                    section_positions[section]['total'] += 1
                    if dev['classification'].get('device_type') == 'memristive':
                        section_positions[section]['yield'] += 1
            if not section_positions:
                print("[PLOT] No section data for spatial gradient")
                return
            sections = sorted(section_positions.keys())
            section_metrics = {
                'avg_score': [np.mean(section_positions[s]['scores']) if section_positions[s]['scores'] else 0 for s in sections],
                'avg_quality': [np.mean(section_positions[s]['qualities']) if section_positions[s]['qualities'] else 0 for s in sections],
                'yield_pct': [100 * section_positions[s]['yield'] / section_positions[s]['total'] if section_positions[s]['total'] > 0 else 0 for s in sections]
            }
            fig, axes = plt.subplots(2, 2, figsize=style.get_figsize("grid_2x2_large"))
            fig.suptitle(f'Section Spatial Gradient - {self.sample_name}', fontsize=16, fontweight='bold')
            x = np.arange(len(sections))
            ax1 = axes[0, 0]
            ax1.bar(x, section_metrics['avg_score'], color='#4CAF50', alpha=0.7, edgecolor='black')
            ax1.plot(x, section_metrics['avg_score'], 'ro-', linewidth=2, markersize=8, label='Trend')
            ax1.set_xlabel('Section', fontweight='bold')
            ax1.set_ylabel('Average Memristivity Score', fontweight='bold')
            ax1.set_title('Score Gradient Across Sections', fontweight='bold')
            ax1.set_xticks(x)
            ax1.set_xticklabels(sections)
            ax1.set_ylim(0, 100)
            ax1.grid(axis='y', alpha=0.3)
            ax1.legend()
            ax2 = axes[0, 1]
            ax2.bar(x, section_metrics['yield_pct'], color='#FF9800', alpha=0.7, edgecolor='black')
            ax2.plot(x, section_metrics['yield_pct'], 'bo-', linewidth=2, markersize=8, label='Trend')
            ax2.set_xlabel('Section', fontweight='bold')
            ax2.set_ylabel('Memristive Yield (%)', fontweight='bold')
            ax2.set_title('Yield Gradient Across Sections', fontweight='bold')
            ax2.set_xticks(x)
            ax2.set_xticklabels(sections)
            ax2.set_ylim(0, 100)
            ax2.grid(axis='y', alpha=0.3)
            ax2.legend()
            ax3 = axes[1, 0]
            ax3.bar(x, section_metrics['avg_quality'], color='#2196F3', alpha=0.7, edgecolor='black')
            ax3.plot(x, section_metrics['avg_quality'], 'go-', linewidth=2, markersize=8, label='Trend')
            ax3.set_xlabel('Section', fontweight='bold')
            ax3.set_ylabel('Average Quality Score', fontweight='bold')
            ax3.set_title('Quality Gradient Across Sections', fontweight='bold')
            ax3.set_xticks(x)
            ax3.set_xticklabels(sections)
            ax3.set_ylim(0, 100)
            ax3.grid(axis='y', alpha=0.3)
            ax3.legend()
            ax4 = axes[1, 1]
            normalized_score = [s / 100.0 for s in section_metrics['avg_score']]
            normalized_yield = [y / 100.0 for y in section_metrics['yield_pct']]
            normalized_quality = [q / 100.0 for q in section_metrics['avg_quality']]
            ax4.plot(x, normalized_score, 'o-', linewidth=2, markersize=8, label='Score (normalized)', color='#4CAF50')
            ax4.plot(x, normalized_yield, 's-', linewidth=2, markersize=8, label='Yield (normalized)', color='#FF9800')
            ax4.plot(x, normalized_quality, '^-', linewidth=2, markersize=8, label='Quality (normalized)', color='#2196F3')
            ax4.set_xlabel('Section', fontweight='bold')
            ax4.set_ylabel('Normalized Value (0-1)', fontweight='bold')
            ax4.set_title('Combined Gradient (Normalized)', fontweight='bold')
            ax4.set_xticks(x)
            ax4.set_xticklabels(sections)
            ax4.set_ylim(0, 1)
            ax4.grid(alpha=0.3)
            ax4.legend()
            plt.tight_layout()
            plt.savefig(os.path.join(self.plots_dir, '25_section_spatial_gradient.png'), dpi=self._dpi, bbox_inches='tight')
            plt.close()
            print(f"[PLOT] Saved: 25_section_spatial_gradient.png")
        except Exception as e:
            print(f"[PLOT ERROR] Section spatial gradient failed: {e}")
            import traceback
            traceback.print_exc()
    
    def plot_onoff_ratio_evolution(self) -> None:
        try:
            if not self._tracking_dir or not os.path.exists(self._tracking_dir):
                print("[PLOT] No tracking directory found for on/off ratio evolution")
                return
            device_evolution_data = []
            tracking_files = [f for f in os.listdir(self._tracking_dir) if f.endswith('_history.json')]
            for file in tracking_files:
                try:
                    file_path = os.path.join(self._tracking_dir, file)
                    with open(file_path, 'r') as f:
                        history_data = json.load(f)
                    device_id = history_data.get('device_id', file.replace('_history.json', ''))
                    measurements = history_data.get('measurements', [])
                    if self._code_name_filter:
                        matching_measurements = [m for m in measurements]
                        if not matching_measurements:
                            continue
                        measurements = matching_measurements
                    if len(measurements) < 2:
                        continue
                    ratios, cycle_nums, timestamps = [], [], []
                    for idx, m in enumerate(measurements, 1):
                        resistance = m.get('resistance', {})
                        on_off_ratio = resistance.get('on_off_ratio')
                        if on_off_ratio is not None and on_off_ratio > 0:
                            ratios.append(float(on_off_ratio))
                            cycle_nums.append(idx)
                            timestamps.append(m.get('timestamp', ''))
                    if len(ratios) >= 2:
                        device_evolution_data.append({'device_id': device_id, 'ratios': ratios, 'cycle_nums': cycle_nums, 'timestamps': timestamps})
                except Exception:
                    continue
            if not device_evolution_data:
                print("[PLOT] No multi-measurement data for on/off ratio evolution")
                return
            fig, ax = plt.subplots(figsize=style.get_figsize("single"))
            devices_plotted = 0
            for dev_data in device_evolution_data:
                ratios = dev_data['ratios']
                cycle_nums = dev_data['cycle_nums']
                device_id = dev_data['device_id']
                if len(ratios) > 1:
                    improvement = ratios[-1] - ratios[0]
                    relative_change = improvement / ratios[0] if ratios[0] > 0 else 0
                    if relative_change > 0.2:
                        color, label_suffix = 'green', ' (Improving)'
                    elif relative_change < -0.2:
                        color, label_suffix = 'red', ' (Degrading)'
                    else:
                        color, label_suffix = 'blue', ' (Stable)'
                else:
                    color, label_suffix = 'gray', ''
                ax.plot(cycle_nums, ratios, 'o-', color=color, alpha=0.6, linewidth=1.5, markersize=4, label=f"{device_id}{label_suffix}")
                devices_plotted += 1
            if devices_plotted == 0:
                print("[PLOT] No valid data for on/off ratio evolution")
                return
            ax.set_xlabel('Measurement Number', fontsize=12, fontweight='bold')
            ax.set_ylabel('On/Off Ratio', fontsize=12, fontweight='bold')
            ax.set_title(f'On/Off Ratio Evolution Over Time - {self.sample_name}', fontsize=14, fontweight='bold')
            ax.set_yscale('log')
            ax.grid(True, alpha=0.3, which='both')
            ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8, ncol=2)
            plt.tight_layout()
            plt.savefig(os.path.join(self.plots_dir, '26_onoff_ratio_evolution.png'), dpi=self._dpi, bbox_inches='tight')
            plt.close()
            print(f"[PLOT] Saved: 26_onoff_ratio_evolution.png")
        except Exception as e:
            print(f"[PLOT ERROR] On/off ratio evolution failed: {e}")
            import traceback
            traceback.print_exc()
    
    def plot_size_memristive_overlays(self) -> None:
        """I-V overlays for memristive devices by size. Requires load_iv_callback."""
        if not self._load_iv:
            print("[PLOT] No I-V loader for size comparison; skipping memristive overlays")
            return
        try:
            plt.rcParams['text.usetex'] = False
            plt.rcParams['mathtext.default'] = 'regular'
            plt.rcParams['axes.formatter.use_mathtext'] = False
            memristive_devices = [d for d in self.devices_data if d.get('classification', {}).get('device_type') == 'memristive']
            if not memristive_devices:
                print("[PLOT] No memristive devices for I-V overlay")
                return
            devices_by_size = {
                '100x100um': [d for d in memristive_devices if d.get('device_size') == '100x100um'],
                '200x200um': [d for d in memristive_devices if d.get('device_size') == '200x200um'],
                '400x400um': [d for d in memristive_devices if d.get('device_size') == '400x400um']
            }
            devices_by_size = {size: devices for size, devices in devices_by_size.items() if devices}
            if not devices_by_size:
                print("[PLOT] No memristive devices with size metadata")
                return
            sizes_present = sorted(devices_by_size.keys())
            num_sizes = len(sizes_present)
            fig, axes = plt.subplots(1, num_sizes, figsize=(6*num_sizes, 6))
            if num_sizes == 1:
                axes = [axes]
            fig.suptitle(f'All Memristive I-V Curves by Size - {self.sample_name}', fontsize=14, fontweight='bold')
            all_voltages, all_currents = [], []
            for devices in devices_by_size.values():
                for dev in devices:
                    v, i = self._load_iv(dev['device_id'])
                    if v is not None and i is not None:
                        all_voltages.extend(v)
                        all_currents.extend(i)
            if not all_voltages or not all_currents:
                print("[PLOT] No I-V data available for memristive devices")
                return
            v_min, v_max = min(all_voltages), max(all_voltages)
            i_max = max(abs(min(all_currents)), abs(max(all_currents)))
            for idx, size in enumerate(sizes_present):
                ax = axes[idx]
                devices = devices_by_size[size]
                plotted_count = 0
                for dev in devices:
                    v, i = self._load_iv(dev['device_id'])
                    if v is not None and i is not None:
                        ax.plot(v, i * 1e6, alpha=0.4, linewidth=0.8)
                        plotted_count += 1
                ax.set_xlabel('Voltage (V)', fontweight='bold')
                ax.set_ylabel('Current (μA)', fontweight='bold')
                ax.set_title(f'{size} (n={plotted_count})', fontweight='bold')
                ax.grid(True, alpha=0.3)
                ax.set_xlim(v_min, v_max)
                ax.set_ylim(-i_max * 1e6 * 1.1, i_max * 1e6 * 1.1)
            plt.tight_layout()
            plt.savefig(os.path.join(self.size_comparison_dir, 'memristive_iv_overlays_by_size.png'), dpi=self._dpi, bbox_inches='tight')
            plt.close()
            print(f"[PLOT] Saved: size_comparison/memristive_iv_overlays_by_size.png")
        except Exception as e:
            print(f"[PLOT ERROR] Memristive I-V overlays failed: {e}")
            import traceback
            traceback.print_exc()
    
    def plot_size_top_per_section(self) -> None:
        if not self._load_iv:
            print("[PLOT] No I-V loader; skipping top per section")
            return
        try:
            plt.rcParams['text.usetex'] = False
            plt.rcParams['mathtext.default'] = 'regular'
            plt.rcParams['axes.formatter.use_mathtext'] = False
            devices_by_section_size = {}
            for dev in self.devices_data:
                section, size = dev.get('section'), dev.get('device_size')
                if section and size:
                    key = (section, size)
                    if key not in devices_by_section_size:
                        devices_by_section_size[key] = []
                    devices_by_section_size[key].append(dev)
            if not devices_by_section_size:
                print("[PLOT] No devices with section and size metadata")
                return
            devices_by_size = {}
            for (section, size), devices in devices_by_section_size.items():
                if size not in devices_by_size:
                    devices_by_size[size] = {}
                devices_sorted = sorted(devices, key=lambda d: d.get('classification', {}).get('memristivity_score', 0) or 0, reverse=True)
                devices_by_size[size][section] = devices_sorted[0] if devices_sorted else None
            devices_by_size = {size: sections for size, sections in devices_by_size.items() if sections and any(d is not None for d in sections.values())}
            if not devices_by_size:
                print("[PLOT] No devices for top per section plot")
                return
            sizes_present = sorted(devices_by_size.keys())
            num_sizes = len(sizes_present)
            fig, axes = plt.subplots(1, num_sizes, figsize=(6*num_sizes, 6))
            if num_sizes == 1:
                axes = [axes]
            fig.suptitle(f'Top Device per Section by Size - {self.sample_name}', fontsize=14, fontweight='bold')
            all_voltages, all_currents = [], []
            for sections in devices_by_size.values():
                for dev in sections.values():
                    if dev:
                        v, i = self._load_iv(dev['device_id'])
                        if v is not None and i is not None:
                            all_voltages.extend(v)
                            all_currents.extend(i)
            if not all_voltages or not all_currents:
                print("[PLOT] No I-V data available")
                return
            v_min, v_max = min(all_voltages), max(all_voltages)
            i_max = max(abs(min(all_currents)), abs(max(all_currents)))
            for idx, size in enumerate(sizes_present):
                ax = axes[idx]
                sections = devices_by_size[size]
                plotted_count = 0
                for section in sorted(sections.keys()):
                    dev = sections[section]
                    if dev:
                        v, i = self._load_iv(dev['device_id'])
                        if v is not None and i is not None:
                            ax.plot(v, i * 1e6, label=f'{section}', alpha=0.7, linewidth=1.5)
                            plotted_count += 1
                ax.set_xlabel('Voltage (V)', fontweight='bold')
                ax.set_ylabel('Current (μA)', fontweight='bold')
                ax.set_title(f'{size} (n={plotted_count})', fontweight='bold')
                ax.grid(True, alpha=0.3)
                ax.legend()
                ax.set_xlim(v_min, v_max)
                ax.set_ylim(-i_max * 1e6 * 1.1, i_max * 1e6 * 1.1)
            plt.tight_layout()
            plt.savefig(os.path.join(self.size_comparison_dir, 'top_device_per_section_by_size.png'), dpi=self._dpi, bbox_inches='tight')
            plt.close()
            print(f"[PLOT] Saved: size_comparison/top_device_per_section_by_size.png")
        except Exception as e:
            print(f"[PLOT ERROR] Top per section plot failed: {e}")
            import traceback
            traceback.print_exc()
    
    def plot_size_top_across_sample(self) -> None:
        if not self._load_iv:
            print("[PLOT] No I-V loader; skipping top across sample")
            return
        try:
            plt.rcParams['text.usetex'] = False
            plt.rcParams['mathtext.default'] = 'regular'
            plt.rcParams['axes.formatter.use_mathtext'] = False
            devices_with_scores = []
            for dev in self.devices_data:
                score = dev.get('classification', {}).get('memristivity_score', 0) or 0
                quality = self._safe_get_quality_score(dev)
                composite = (score * 0.7 + quality * 0.3) if not np.isnan(quality) else score
                devices_with_scores.append((dev, composite))
            devices_with_scores.sort(key=lambda x: x[1], reverse=True)
            devices_by_size = {}
            for dev, score in devices_with_scores:
                size = dev.get('device_size')
                if size:
                    if size not in devices_by_size:
                        devices_by_size[size] = []
                    if len(devices_by_size[size]) < 5:
                        devices_by_size[size].append(dev)
            devices_by_size = {size: devices for size, devices in devices_by_size.items() if devices}
            if not devices_by_size:
                print("[PLOT] No devices with size metadata for top 5 plot")
                return
            sizes_present = sorted(devices_by_size.keys())
            num_sizes = len(sizes_present)
            fig, axes = plt.subplots(1, num_sizes, figsize=(6*num_sizes, 6))
            if num_sizes == 1:
                axes = [axes]
            fig.suptitle(f'Top 5 Devices by Size - {self.sample_name}', fontsize=14, fontweight='bold')
            all_voltages, all_currents = [], []
            for devices in devices_by_size.values():
                for dev in devices:
                    v, i = self._load_iv(dev['device_id'])
                    if v is not None and i is not None:
                        all_voltages.extend(v)
                        all_currents.extend(i)
            if not all_voltages or not all_currents:
                print("[PLOT] No I-V data available")
                return
            v_min, v_max = min(all_voltages), max(all_voltages)
            i_max = max(abs(min(all_currents)), abs(max(all_currents)))
            for idx, size in enumerate(sizes_present):
                ax = axes[idx]
                devices = devices_by_size[size]
                plotted_count = 0
                for i, dev in enumerate(devices):
                    v, i_data = self._load_iv(dev['device_id'])
                    if v is not None and i_data is not None:
                        score = dev.get('classification', {}).get('memristivity_score', 0) or 0
                        ax.plot(v, i_data * 1e6, label=f'#{i+1} ({score:.0f})', alpha=0.7, linewidth=1.5)
                        plotted_count += 1
                ax.set_xlabel('Voltage (V)', fontweight='bold')
                ax.set_ylabel('Current (μA)', fontweight='bold')
                ax.set_title(f'{size} (n={plotted_count})', fontweight='bold')
                ax.grid(True, alpha=0.3)
                ax.legend()
                ax.set_xlim(v_min, v_max)
                ax.set_ylim(-i_max * 1e6 * 1.1, i_max * 1e6 * 1.1)
            plt.tight_layout()
            plt.savefig(os.path.join(self.size_comparison_dir, 'top5_devices_by_size.png'), dpi=self._dpi, bbox_inches='tight')
            plt.close()
            print(f"[PLOT] Saved: size_comparison/top5_devices_by_size.png")
        except Exception as e:
            print(f"[PLOT ERROR] Top 5 devices plot failed: {e}")
            import traceback
            traceback.print_exc()
