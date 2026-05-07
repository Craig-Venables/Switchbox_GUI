# AFM Line Profile Analyser

Analyses Gwyddion-exported AFM line profile data to characterise **holes** (pits) and **protrusions** (bumps) across multiple samples. Outputs per-profile CSVs, per-file plots, and cross-sample comparison plots — all with companion `.txt` files for direct import into **Origin**.

---

## Quick Start

```bash
py -3 main.py
```

Place your `.txt` data files in the `Data/` folder and run. Results appear in `Output/`.

---

## Dependencies

```bash
pip install numpy pandas matplotlib scipy
```

---

## Input File Format

Files must be Gwyddion profile exports with the following structure:

```
Profile 1             Profile 2             ...
x       y             x       y             ...
[m]     [m]           [m]     [m]           ...
0       2.88e-10      0       -1.94e-10     ...
1.88e-8 2.50e-10      1.83e-8 -8.50e-11    ...
...
-       -             ...                       ← missing values use '-'
```

- Multiple profiles are stored **side by side**, two columns (x, y) per profile
- x and y are both in **metres**
- Profiles can have different lengths — missing rows are marked with `-`

---

## Configuration

All tunable parameters are at the **top of `main.py`**:

| Variable | Default | Description |
|---|---|---|
| `SAVE_PLOTS` | `True` | Set `False` to skip all plotting (faster batch runs) |
| `WIDTH_THRESHOLD_FRAC` | `0.20` | Primary width measurement level as a fraction of peak amplitude. `0.20` = measure where feature is at 20% of its full depth/height. Lower values give wider (more inclusive) widths |
| `THRESHOLD_RANGE` | `[0.05, 0.10, 0.20]` | Additional threshold fractions reported alongside the primary — shown as extra lines on profile plots and in `threshold_width_bars.png` |
| `N_EDGE_PTS` | `2` | Number of points at each end of a profile used to fit the linear baseline. Increase for longer flat regions |
| `MIN_SIGNAL_FRAC` | `0.10` | A feature must exceed this fraction of the profile's total range to be counted (noise rejection) |
| `DPI` | `150` | Plot resolution |

---

## How It Works

### 1 · Linear baseline subtraction
A straight line is fitted to the first and last `N_EDGE_PTS` data points of each profile and subtracted. This removes any sample tilt or DC offset before measurement.

### 2 · Classification (hole or protrusion)
After baseline subtraction, each profile is classified as **one** feature type:
- `|min| ≥ |max|` → **hole** (dominant negative excursion)
- `|max| > |min|` → **protrusion** (dominant positive excursion)

A profile is discarded as noise if its dominant amplitude is less than `MIN_SIGNAL_FRAC × full range`.

### 3 · Width measurement
The signal is inverted for holes (so the dip becomes a positive peak). Width is measured at the level `WIDTH_THRESHOLD_FRAC × amplitude` — i.e. where the feature returns close to the surface baseline. This gives the **full physical feature width**, not FWHM.

Width is re-measured at every fraction in `THRESHOLD_RANGE` to show how sensitive the result is to threshold choice.

### 4 · Height / depth
Reported as the peak amplitude above the local baseline (in nm).

---

## Output Structure

```
Output/
├── summary.csv                          ← one row per file, all key averages
├── <filename>_profiles.csv              ← one row per profile
│
├── <filename>/
│   ├── profiles/
│   │   ├── profile_01.png               ← raw + baseline (top panel)
│   │   │                                   corrected signal + threshold lines (bottom)
│   │   ├── profile_01.txt               ← Origin-compatible tab-separated data
│   │   └── ...
│   └── stats/
│       ├── boxplot.png / .txt
│       ├── violin.png  / .txt
│       ├── scatter.png / .txt
│       └── histogram.png / .txt
│
└── comparison/                          ← cross-sample plots (all files together)
    ├── feature_count_bar.png / .txt     ← holes & protrusions per sample (grouped bar)
    ├── hole_width_box.png / .txt        ← hole width distribution per sample
    ├── hole_depth_box.png / .txt        ← hole depth distribution per sample
    ├── width_vs_depth.png / .txt        ← mean width vs depth scatter (bubble = count)
    ├── threshold_width_bars.png / .txt  ← width at each threshold per sample
    ├── protrusion_width_box.png / .txt  ← protrusion width distribution per sample
    ├── protrusion_height_box.png / .txt ← protrusion height distribution per sample
    ├── protrusion_width_vs_height.png   ← protrusion width vs height scatter
    └── ranking_table.png / .txt         ← ranked table: rank 1 = best (fewest/smallest holes)
```

---

## Reading the Profile Plots

Each profile generates a two-panel figure:

**Top panel** — Raw data (blue) with the fitted linear baseline (orange dashed). Useful for checking whether the baseline removal is sensible.

**Bottom panel** — Baseline-corrected signal (holes are inverted so the pit appears as a positive peak). Contains:
- **Red dashed line** — primary threshold (`WIDTH_THRESHOLD_FRAC × amplitude`)
- **Green dotted vertical lines** — primary width measurement boundaries
- **Green shading** — measured width region
- **Coloured dotted horizontal lines** — secondary thresholds from `THRESHOLD_RANGE`, each annotated with the width it would give

---

## Reading the Comparison / Ranking Table

Samples are ranked on three metrics (rank 1 = best):

| Metric | What "best" means |
|---|---|
| `rank_n_holes` | Fewest holes detected |
| `rank_width` | Narrowest average hole width |
| `rank_depth` | Shallowest average hole depth |
| **Composite** | Sum of the three ranks — **lowest = best overall** |

The best-ranked sample is highlighted in **green** in the table PNG.

---

## Workflow for Comparing Samples

1. Export line profiles from Gwyddion for each sample into `Data/` (one `.txt` per sample)
2. Run `py -3 main.py`
3. Check `Output/comparison/ranking_table.png` for the overall ranking
4. Use `threshold_width_bars.png` to see how width estimates change with threshold choice
5. Import any `.txt` file directly into **Origin** (tab-separated, first row = column headers)

---

## Files

| File | Purpose |
|---|---|
| `main.py` | Entry point — parsing, analysis, per-file plots, configuration |
| `comparison.py` | Cross-file comparison plots (called automatically by `main.py`) |
| `Data/` | Place input `.txt` files here |
| `Output/` | All results written here (created automatically) |
