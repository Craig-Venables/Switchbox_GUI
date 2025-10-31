# ITO Analysis - Quick Guide

## What it does
- Scans an ITO sample folder (e.g., `5-ITO`) and finds section subfolders (`A`, `B`, ...).
- Loads first three sweeps per section matching patterns in `FIRST_THREE_SWEEP_PREFIXES`.
- Computes per-section metrics:
  - Resistances: Rpos (0..0.5 V first sweep), Rneg (-0.5..0 V last sweep), small-signal R near 0 V.
  - Conductance G = 1/R, plus geometry-aware conductivity (σ), resistivity (ρ), sheet resistance (Rs).
  - Switching heuristic near 0 V.
- Produces CSVs, an Excel workbook, plots, and a combined dashboard image.

## How to run
1. Edit `Helpers/ITO_Analysis/ITO.py`:
   - Set `ONEDRIVE_ROOT` to your data root.
   - Choose one:
     - Single sample: set `SAMPLE_FOLDER_NAME = "<sample>"` and `PROCESS_ALL_SAMPLES = False`.
     - Batch: set `PROCESS_ALL_SAMPLES = True` and optionally set `EXCLUDE_SAMPLES = {"folder_to_skip", ...}`.
2. Run the script:
```
python -m Helpers.ITO_Analysis.ITO
```

## Geometry assumptions
- Thickness: 50 nm (THICKNESS_M).
- Length range: 6700–6950 µm (bounds for σ, Rs error bars).
- Width mapping: A, D, G, H → 200 µm; B, E, L, I → 100 µm.
- Update `SECTION_WIDTH_UM` if your layout differs.

## Outputs (per sample in `Helpers/ITO_Analysis/<sample>`)
- CSVs:
  - `ITO_<sample>_summary.csv`: per section & sweep metrics (R, G, σ, ρ, Rs, switching).
  - `ITO_<sample>_first_three_sweeps.csv`: long/tidy V-I-Time across sweeps.
  - `ITO_<sample>_start_end_stats.csv`: summary of start vs end R.
- Excel workbook:
  - `ITO_<sample>_summary.xlsx` with sheets: `summary`, `long`, `start_end_stats`, `summary_table` (image).
- Plots (PNG):
  - First-sweep overlay, last-neg overlay, semilogy last sweep.
  - Bars: R (first), G first vs final (final background).
  - Start vs end: R grouped bars, dumbbell, scatter.
  - Conductivity (σ) start vs end with guideline lines (low/med/high), Sheet Rs start vs end, Resistivity start vs end.
  - Summary table image and a multi-subplot `dashboard.png` that tiles all plots (table placed last).

## Interpretation notes
- Typical ITO σ: ~1e4–1e5 S/m for good films; ~1e3 S/m for lower-quality/thinner films.
- Conductivity guideline lines: 1e3, 1e4, 1e5 S/m on σ chart.
- Error bars on σ and Rs reflect length uncertainty (6.7–6.95 mm).

## Customization
- Edit `FIRST_THREE_SWEEP_PREFIXES` if your file naming differs.
- Add/adjust widths in `SECTION_WIDTH_UM`.
- Change thresholds in `CONDUCTIVITY_THRESHOLDS`.
- Toggle batch behavior via `PROCESS_ALL_SAMPLES` and `EXCLUDE_SAMPLES`.



