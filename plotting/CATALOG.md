# Plot catalog – where each graph lives

Use this to find the code for any graph so you can change style or behavior. **Global style:** [style.py](style.py). **Single entry point:** `from plotting import UnifiedPlotter, SamplePlots, style, endurance_plots`.

| Plot name | Module / function | Used by |
|-----------|------------------|---------|
| IV dashboard (device) | [unified_plotter.py](unified_plotter.py) `plot_iv_dashboard` | Plot Current Device Graphs, Plot All Sample Graphs, background after measurement |
| Conduction analysis | [unified_plotter.py](unified_plotter.py) `plot_conduction_analysis` | Same as above (memristive) |
| SCLC fit | [unified_plotter.py](unified_plotter.py) `plot_sclc_fit` | Same (memristive) |
| Endurance analysis | [unified_plotter.py](unified_plotter.py) `plot_endurance_analysis` | Background plot (endurance tests) |
| Retention analysis | [unified_plotter.py](unified_plotter.py) `plot_retention_analysis` | Background plot (retention tests) |
| Pulse forming analysis | [unified_plotter.py](unified_plotter.py) `plot_pulse_forming_analysis` | Background plot (forming tests) |
| Memristivity heatmap | [sample_plots.py](sample_plots.py) `SamplePlots.plot_memristivity_heatmap` | Sample Analysis > Run Full Sample Analysis |
| Conduction mechanisms | [sample_plots.py](sample_plots.py) `SamplePlots.plot_conduction_mechanisms` | Same |
| Memory window quality | [sample_plots.py](sample_plots.py) `SamplePlots.plot_memory_window_quality` | Same |
| Hysteresis radar | [sample_plots.py](sample_plots.py) `SamplePlots.plot_hysteresis_radar` | Same |
| Classification scatter | [sample_plots.py](sample_plots.py) `SamplePlots.plot_classification_scatter` | Same |
| Forming progress | [sample_plots.py](sample_plots.py) `SamplePlots.plot_forming_progress` | Same |
| Warning summary | [sample_plots.py](sample_plots.py) `SamplePlots.plot_warning_summary` | Same |
| Research diagnostics | [sample_plots.py](sample_plots.py) `SamplePlots.plot_research_diagnostics` | Same |
| Sample plots 9–26 (power efficiency, leaderboard, spatial, forming status, size comparison, metric correlation, section comparison, resistance distribution, yield dashboard, type/size matrix, quality breakdown, confidence scatter, voltage range, stability, warning dashboard, ratio comparison, section gradient, on/off evolution) | [sample_plots.py](sample_plots.py) `SamplePlots` | Sample Analysis > Run Full Sample Analysis |
| Size comparison I-V overlays (memristive by size, top per section, top 5 by size) | [sample_plots.py](sample_plots.py) `SamplePlots.plot_size_*` | Same (plots in `plots/size_comparison/`) |
| Section stacked sweeps by type/voltage, statistical comparisons | [section_plots.py](section_plots.py) `plot_sweeps_by_type`, `plot_sweeps_by_voltage`, `plot_statistical_comparisons` | Run Full Sample Analysis (section-level) |
| Device combined sweeps (IV / endurance / retention per device) | [device_combined_plots.py](device_combined_plots.py) `plot_device_combined_sweeps` | Run Full Sample Analysis (per-device images) |
| DC endurance (per voltage + summary) | [endurance_plots.py](endurance_plots.py) `plot_current_vs_cycle`, `plot_endurance_summary` | DC endurance analysis |
