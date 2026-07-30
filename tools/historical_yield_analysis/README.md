# Historical Device Yield Analysis

Self-contained desktop tool that indexes manual classification Excel sheets across
your (possibly split) data folders, caches a normalized device catalogue locally,
and regenerates thesis-ready yield / composition plots **without modifying or
moving raw data**.

Designed to live under `tools/` now and become its own repository later.

## Goals

- See how devices evolved over time (ordered by sample ID `D#`)
- Track **strict memristive yield** rising and ohmic / capacitive / other falling
- Re-run analysis cheaply from a local SQLite cache
- Leave a clean plug-in point for a future automatic classifier

## Yield definition (v1)

\[
\text{strict yield} = \frac{\#\ \mathrm{Memristive}}{\#\ \mathrm{recognised\ non\text{-}blank\ classifications}}
\]

- Blank / empty classification rows are **excluded** from the denominator
- Only **Memristive** counts as success (Mem-Capacitance and Intermittent are tracked separately, not as success)
- Label aliases are normalized (`Capacative` → capacitive, `Non Conductive` → non_conductive, `Intermittant` → intermittent, …)

## Data roots (read-only)

Configure in `config.json` (created automatically from `config.example.json` on first run):

1. Newer: `...\Documents\Data_folder` (priority **1**, wins duplicates)
2. Older: `...\Phd\2) Data\1) Devices\1) Memristors` (priority **2**)

When the same sample ID exists in both trees, the newer root is kept and the older
copy is logged as `duplicate_rejected` in the quality report.

Source Excel files are **never** written to.

## Install

From this folder:

```powershell
cd tools\historical_yield_analysis
pip install -r requirements.txt
```

## Run (GUI)

```powershell
python launch_gui.py
```

Or:

```powershell
python -m historical_yield gui
```

### GUI actions

| Button | Behaviour |
|--------|-----------|
| **Scan / update cache** | Discover workbooks; parse only new/changed fingerprints |
| **Rebuild cache** | Clear local SQLite and re-import everything |
| **Generate report from selection** | Build CSVs + plots + Origin TXT for currently selected samples |
| **Export Origin TXT** | Write tab-delimited Origin files for the current selection |
| **Open output folder** | Opens `output/` |
| **Reload config** | Re-read `config.json` |

### Filters & interactive plot (Phase 2)

The **Filters & plot** tab lets you:

- Select / deselect samples individually (All / None / Invert + search box)
- Filter by **polymer**, **B-electrode**, **T-electrode**, **polymer %**, and **Np type** (from fabrication workbook)
- Zoom / pan the embedded Matplotlib plot (toolbar) — useful for dense Stock=0 / edge concentration points
- Switch plot type: yield timeline, composition stack, concentration vs yield (hover shows sample ID)

Plot toggles:

| Toggle | Effect |
|--------|--------|
| **Log x (concentration)** | Log-scales the concentration axis so low values (0.001–0.07 mg/ml) spread out instead of bunching at the origin. Stock (0 mg/ml) cannot appear on a log axis, so those points are hidden and counted in the title. |
| **Colour by sample age** | Shades points by sample number with a `viridis` gradient plus colourbar, so early devices and later devices are visually separable — the evolution-over-time view. |
| **Show labels** | Annotates every point with its sample ID. |

Plot buttons:

| Button | Behaviour |
|--------|-----------|
| **Export plotted data (TXT)** | Writes exactly the points currently drawn (after filters and the log-axis drop) to `output/origin_export/<plot>.txt`, with the plotted axes first as `X_…` / `Y_…`, then sample IDs, sample names, and fabrication metadata |
| **Save figure (PNG)** | Saves the on-screen figure at 300 dpi to `output/figures/` |

### Missing Excel tab

Lists `Dxx…` sample folders under the data roots that do **not** contain a matching classification `.xlsx`, so you can fill them in manually. Non-`Dxx` folders are ignored. Also notes whether each sample has a row in `solutions and devices.xlsx`.

## Fabrication metadata

Configure in `config.json`:

```json
"fabrication_workbook": "C:\\Users\\...\\Phd\\solutions and devices.xlsx",
"fabrication_sheet": "Memristor Devices"
```

Lookups use device number `#` → `D{#}` and/or `Device Full Name`. Fields used for filtering: Polymer, Np Concentraion, B-Material, T-Material, Layer 1 (polymer %), Np Type. Read-only.

## Run (CLI)

```powershell
python -m historical_yield scan
python -m historical_yield scan --rebuild
python -m historical_yield report
python -m historical_yield stats
```

## Outputs

Each report lands in `output/report_YYYYMMDD_HHMMSS/`:

| File | Contents |
|------|----------|
| `sample_summary.csv` | One row per sample: strict yield, counts, composition fractions, fabrication fields |
| `device_detail.csv` | One row per device classification |
| `quality_report.csv` | Duplicates, malformed files, warnings |
| `missing_classification_excel.csv` | Dxx folders lacking a classification workbook |
| `config_snapshot.json` | Config used for the report |
| `manifest.json` | Reproducibility metadata |
| `plots/` | PNG / SVG / PDF |
| `origin/` | Tab-delimited Origin-ready TXT |

### Origin TXT

Tab-separated UTF-8 files (no index column):

- `origin_yield_vs_sample.txt`
- `origin_concentration_vs_yield.txt`
- `origin_composition_vs_sample.txt`

Also available via **Export Origin TXT** without a full report (`output/origin_export/`).

### Static plots

Saved at 300 dpi in each requested format:

1. Strict memristive yield vs sample ID
2. Stacked classification composition vs sample ID
3. Concentration vs strict yield (Stock = 0), sample labels, age gradient
4. Concentration vs strict yield on a log x axis (`concentration_vs_yield_logx`), Stock points excluded
5. Concentration vs yield faceted by polymer

### Deferred (documented for later)

- Broader polymer / electrode / material thesis facet packs beyond current filters
- Automatic classifier as the primary label source

## Cache

- Location: `cache/historical_yield.sqlite`
- Fingerprint = resolved path + size + mtime (fast)
- Unchanged workbooks are skipped on incremental scans
- Safe to delete the cache folder; rebuild from raw data anytime

## Classifier plug-in

Version 1 uses `manual_excel`.

To add an automatic classifier later:

1. Implement `ClassifierProvider` in `historical_yield/classifiers/` with:
   - `classifier_id`, `classifier_version`
   - `classify(source_path, sample, *, success_categories) -> ClassificationResult`
2. Call `register_classifier(YourProvider())`
3. Set `"classifier": "your_id"` in `config.json`

Analysis and plotting stay unchanged because they consume the normalized
`DeviceClassification` records only.

## Tests

```powershell
cd tools\historical_yield_analysis
pytest tests -q
```

## Layout

```
historical_yield_analysis/
  launch_gui.py
  config.example.json
  requirements.txt
  historical_yield/
    config.py
    discovery.py
    workbook.py
    normalize.py
    parse_sample.py
    cache.py
    import_pipeline.py
    analysis.py
    fabrication.py   # solutions and devices.xlsx join
    missing_excel.py # Dxx folders without classification xlsx
    origin_export.py # Origin-ready TSV
    plots.py
    report.py
    classifiers/     # pluggable providers
    gui/             # PyQt5 desktop UI (+ interactive plot panel)
  tests/
  cache/             # local, gitignored
  output/            # local, gitignored
```
