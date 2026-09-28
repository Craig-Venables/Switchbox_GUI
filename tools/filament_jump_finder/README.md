# Filament Jump Finder

Interactive PyQt tool for finding **large current jumps** in IV sweep data (e.g. filament formation / soft-breakdown events), reviewing candidates by eye, and exporting **Origin-ready** tables for thesis and publication figures.

Jump detection and live review work on ordinary IV measurement folders.  
**Memristive vs non-memristive Compare panels, NDR stats, and “best memristive IV” overlays only work if your samples follow a specific analysis layout** (described below). Without that layout, those tabs stay empty or show “Unknown” classification.

---

## What it does

| Capability | Needs special analysis exports? |
|------------|----------------------------------|
| Load one or many sample folders | No |
| Detect current steps by ratio threshold | No |
| Live voltage window / min current / upward-only filters | No |
| Mark Jump / Not a jump (single or multi-select) | No |
| Histograms of accepted jump voltages | No |
| Save / load review session (JSON) | No |
| Export jump lists + histograms for Origin | No |
| Yield bars: devices with jump vs without | No |
| Split by **worked memristive** | **Yes** — thesis LLM device summary |
| NDR mean / soft / strong vs jump | **Yes** — `ndr_index_max` in that summary |
| Overlay all memristive IVs with vs without jump | **Yes** — summary + IV classifications |
| Best memristive pair showcase | **Yes** — same |

---

## Requirements

- Python 3.9+ (tested on Windows)
- **PyQt5**, **matplotlib**, **numpy**

### As part of Switchbox_GUI (current packaging)

From the **Switchbox_GUI** repository root:

```powershell
pip install PyQt5 matplotlib numpy
python -m tools.filament_jump_finder
python -m tools.filament_jump_finder --sample "D:\Data\D110-..."
```

The tool also uses helpers from `tools/device_visualizer/` (folder discovery and raw IV loaders). Keep that package on the Python path (running as `python -m tools.filament_jump_finder` from the repo root does this).

### Standalone GitHub repo

If you extract this folder into its own repo, you must either:

1. Vendor or copy the small `device_visualizer` data helpers it imports, **or**
2. Document that Switchbox_GUI remains a dependency and install/path accordingly.

Raw IV loading expects the same text formats your Switchbox / measurement pipeline already writes (voltage/current columns via `DataLoader.load_raw_measurement`).

---

## Expected data layouts

### A. Jump finding only (works generally)

**Sample folder** with nested devices:

```text
MySample/
  A/
    1/
      0-FS-....txt
      1-FS-....txt
      ...
    2/
      ...
  F/
    1/
      ...
```

Or a **single device folder** that itself contains measurement `.txt` files (no section nesting).

Add the sample folder(s) with **Add folders…** (multi-select). The tool tags every jump with the folder basename (e.g. `D110-0.1mgml-...`).

### B. Memristive / NDR / IV overlay features (specific pipeline)

These features look under each loaded sample for:

```text
{sample}/sample_analysis/thesis_llm_exports/
  {sid}_device_summary.csv      ← required for memristive + NDR
  {sid}_iv_classifications.csv  ← used to pick each device’s “best” IV sweep
  {sid}_sample_summary.csv      ← not required by the GUI (context only)
  devices/                      ← optional per-device copies
```

Example (author’s layout):

```text
D110-0.1mgml-ITO-PMMA 2.0(2%)-Gold-s9/
  A/1/*.txt
  F/1/*.txt
  ...
  sample_analysis/
    thesis_llm_exports/
      D110_device_summary.csv
      D110_iv_classifications.csv
      D110_sample_summary.csv
```

Those CSVs are produced by the **thesis LLM / classification export** pipeline (`thesis_llm.classification_export` in the companion analysis project), kept in sync with device tracking / reclassify. They are **not** the old per-device `classification_log.txt` files.

#### Fields used from `{sid}_device_summary.csv`

| Column | Role in this tool |
|--------|-------------------|
| `section`, `device_number` | Match to on-disk devices (`A/1`, `F/10`, …) |
| `endpoint_type` (fallback `majority_type`) | Display classification string |
| `worked_memristive` | **Primary** “is memristive” flag for Compare (same idea as sample yield) |
| `ndr_index_max` | NDR Compare tab |
| `memristive_sweep_count` | Ranking “best” memristive devices |
| `R_at_0p5V_fold_change` | Secondary ranking for best-pair |

#### Fields used from `{sid}_iv_classifications.csv`

| Column | Role |
|--------|------|
| `section`, `device_number` | Device key |
| `filename` / `file_path` | Which IV file to plot for overlays |
| `memristivity_score`, `predicted_type` | Prefer the strongest memristive sweep per device |

If these files are missing, jump review and Origin jump exports still work; memristive/NDR/IV-overlay Compare tabs will not.

---

## How to use (step by step)

### 1. Launch

```powershell
cd path\to\Switchbox_GUI
python -m tools.filament_jump_finder
# or
py -m tools.filament_jump_finder --sample "C:\path\to\sample_folder"
```

### 2. Add samples

1. Click **Add folders…**
2. Multi-select sample directories (Ctrl/Shift in the non-native dialog)
3. Use **Remove selected** / **Reload** as needed

Folders appear in the list as `name — full path`.

### 3. Tune detection (live)

Controls at the top (no second “Run”):

| Control | Meaning |
|---------|---------|
| **Jump ratio ≥** | Min \|I\| step ratio between consecutive points (slider + spin) |
| **V from / to** + **Voltage window** | Keep jumps whose mid-voltage lies in the window |
| **Use \|V\|** | Apply the window to absolute voltage (both sweep directions) |
| **Min current (A)** | Optional floor on the smaller \|I\| of the step |
| **Only upward** | Require signed current increase |

Candidates are scanned once at a low floor ratio (~1.5); the UI filters that cache live. The count label shows `N jumps, M rejected`.

### 4. Review tab — accept / reject

- Table lists jumps under the current filters (including rejected rows so you can restore them).
- Select a row → IV (linear + log) with markers: green = accepted, grey = rejected, orange = selected.
- Click a marker to toggle; or use buttons / shortcuts.

**Keyboard**

| Key | Action |
|-----|--------|
| **A** or **Enter** | Accept selected row(s) as jump → advance |
| **R**, **X**, or **Delete** | Reject selected → advance |
| **← / →** or **↑ / ↓** | Previous / next |

**Multi-select:** Ctrl/Shift-click rows, then Accept/Reject (or **A** / **R**).  
Histogram and Compare redraws are deferred so bulk rejects stay responsive.

**Inspect file…** (or double-click): full IV dashboard, include toggles, and “exclude this file from first occurrence”.

### 5. Compare tab (subtabs)

Shared status line summarises with-jump / without-jump and memristive NDR means when data exist.

| Subtab | Content | Needs thesis exports? |
|--------|---------|------------------------|
| **Yield** | Device counts: with vs without jump (all devices + worked-memristive split) | Memristive split: yes |
| **NDR** | Mean `ndr_index_max`; soft (≥0.05) / strong (≥0.15) counts vs jump | Yes |
| **Memristive IVs** | 2×2 overlays of **every** worked-memristive device’s best sweep: linear & log **with jump**, linear & log **without jump**. Sample dropdown: one folder or All | Yes |
| **Best pair** | One best with-jump vs one best without-jump IV per sample (showcase) | Yes |

Without exports, use **Yield** for raw with/without jump counts only; treat other subtabs as unavailable.

### 6. Save Session

1. **Save Session…**
2. Enter a **name**
3. Choose where to write the `.json`

Stores: folder paths, filter settings, Jump/Not-a-jump decisions, exclude-from-first flags.  
**Load Session…** reloads folders and decisions (paths must still exist).

### 7. Save for Origin

1. **Save for Origin**
2. Enter a **name** (required) so exports do not overwrite each other

Writes under:

```text
{common parent of loaded folders}/origin data/{your name}/
```

If only one sample is loaded, that sample folder is the root.

#### Files written

| File | Description |
|------|-------------|
| `filament_jumps_all.txt` | All accepted jumps |
| `filament_jumps_first.txt` | First accepted jump per device |
| `filament_jump_histogram_signed.txt` | Histogram bins (signed V) |
| `filament_jump_histogram_absolute.txt` | Histogram bins (\|V\|) |
| `filament_device_yield.txt` | Per device: HasJump, classification, memristive flags, NDR, … |
| `filament_yield_counts.txt` | Count categories per folder + Combined |
| `filament_ndr_compare.txt` | NDR stats with vs without jump |
| `filament_best_memristive_pairs.txt` | Which devices were chosen as “best” |
| `filament_jumps_review.json` | Snapshot of decisions/filters for that export |

Jump TSV columns typically include:  
`SourceFolder`, `Section`, `Device`, `Filename`, `Voltage_V`, `AbsVoltage_V`, `Ratio`, `I_before_A`, `I_after_A`.

Import into Origin as tab-delimited text; use signed or absolute histogram files for publication plots.

---

## Detection definition (technical)

Between consecutive points \(i\) and \(i+1\):

\[
\text{ratio} = \frac{\max(|I_i|,|I_{i+1}|)}{\max(\min(|I_i|,|I_{i+1}|),\,10^{-15})}
\]

A candidate is kept if `ratio ≥` threshold (and optional current / upward / voltage filters).  
Jump voltage is the midpoint of the two voltages. Manual rejects are keyed by `file_path + step index` so changing the threshold does not resurrect a rejected step.

---

## Limitations and caveats

1. **Memristive Compare is pipeline-specific.** It does **not** re-run classification. It only reads `thesis_llm_exports/*_device_summary.csv`. Other lab layouts (logs only, different CSV names, different column names) will not populate memristive/NDR/IV-overlay views unless you adapt the loader or generate matching exports.

2. **“Memristive” means `worked_memristive`.** That matches the author’s sample-summary yield definition. Devices with `endpoint_type` containing “mem” but `worked_memristive=False` are **not** counted as memristive here.

3. **Jump detection ≠ thesis `current_jump_detected`.** The GUI finds jumps from raw IV ratios. Thesis CSVs may also list jump flags; Compare “has jump” follows **your accepted GUI decisions**, not the CSV jump column.

4. **Best IV file paths** in `*_iv_classifications.csv` sometimes point at sample-root stems; the tool falls back to the device folder and filename. Odd path quirks in exports can leave a device without an overlay curve.

5. **Large sessions:** defer Compare redraw while rejecting; opening Compare refreshes. Extremely large multi-sample overlays can still be heavy.

6. **First occurrence** can skip a whole file via Inspect; that only affects `filament_jumps_first.txt`, not the all-jumps list.

7. **Packaging:** designed as `tools.filament_jump_finder` inside Switchbox_GUI. A standalone repo needs the data-loader dependency story resolved.

---

## Project layout (this package)

```text
filament_jump_finder/
  __init__.py       # run_gui, public API
  __main__.py       # python -m entry
  core.py           # detection, multi-folder load, yield/NDR, thesis CSV readers
  gui.py            # Review + Compare UI
  origin_export.py  # Origin TSV + session JSON
  README.md         # this file
```

---

## Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| No jumps | Raise sensitivity: lower ratio, widen/disable voltage window |
| Memristive counts all zero / Unknown | Missing `sample_analysis/thesis_llm_exports/*_device_summary.csv`, or section/device numbers do not match folders |
| Memristive IVs empty | No worked-memristive devices, or no usable `*_iv_classifications.csv` / IV files |
| Session load fails | Sample paths moved; edit JSON or re-add folders |
| Slow rejects | Use multi-select; Compare updates are deferred — open Compare after bulk edits |

---

## Licence / citation

Use and redistribute according to the parent repository’s licence.  
For papers, prefer exporting Origin tables from a **named** Save for Origin run and archive the session JSON with the figure source data.

---

## Related tools

- **device_visualizer** — browse devices / classifications in Switchbox_GUI  
- **thesis LLM classification export** — writes `thesis_llm_exports` CSVs this tool optionally consumes  
- **Origin** — import the tab-delimited files under `origin data/<name>/`
