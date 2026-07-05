# Data Consolidation

Collects IV measurement `.txt` files from `Data_folder` sample directories into one flat folder for batch classification and labeling.

## Which folders are included

Top-level folders under the source path whose names **start with `D` + digits**, for example:

- `D80`
- `D94-0.1mgml-ITO-PMMA(2%)-Gold-s2`

Only the **`Dxx`** prefix is used in output names (e.g. `D94`), not the full folder name.

## Output naming

```
D94-A-1-1-FS-0.5v-0.05sv-0.05sd-Py-St_v2_led-3.txt
│   │ │  └── original sweep filename
│   │ └───── device number (folder under section)
│   └─────── section letter (e.g. A, B)
└─────────── sample id (D94)
```

Files in subfolders under a device (e.g. `A/1/Pulse_measurements/...`) keep the subfolder in the name:

```
D80-A-1-Pulse_measurements-0-Pulse_Multi_Read-....txt
```

## Excluded files

- `log.txt`, `classification_log.txt`, `classification_summary.txt`
- `*_analysis.txt`

## Usage

From project root:

```bash
# Preview without copying
python tools/data_consolidation/consolidate.py --dry-run

# Copy all files (default source = OneDrive Data_folder)
python tools/data_consolidation/consolidate.py

# Custom paths
python tools/data_consolidation/consolidate.py --source "C:\path\to\Data_folder" --output tools/data_consolidation/data
```

Writes `manifest.csv` next to the script mapping each output file back to its original path.

If two source files map to the same output name (e.g. duplicate `D80` and `D80-...` folders), the second file gets a `-2`, `-3`, ... suffix before `.txt`.

## Next step

### 1. Batch classify (run once)

```bash
python tools/data_consolidation/batch_classify.py
```

Writes:
- `classification_results.csv` — open in Excel; sort by `review_priority` or `confidence`
- `classification_results.json` — full results for review GUI
- `classification_summary.txt` — what the classifier is strong/weak at (distribution, low-confidence counts)

### 2. Review GUI (manual checking)

```bash
python tools/data_consolidation/launch_review.py
```

### 2b. Flash review (fast Y/N — recommended first pass)

```bash
python tools/data_consolidation/launch_flash_review.py
python tools/data_consolidation/launch_review.py --flash
```

- Big predicted type on screen (e.g. **MEMRISTIVE**)
- **Y** = correct, **N** = wrong (saved for manual labelling later), **S** = skip
- Dropdown to pick which predicted type to review (default: memristive)
- Single I–V plot only — built for speed
- Same `review_corrections.json` as full review

Then use full review with filter **"Needs manual label (flash N)"** or **"I disagreed"** to pick the correct type.

### 2c. Full review GUI

- IV plot + predicted type + class scores
- **Agree** / **Disagree** (pick correct label) / **Skip**
- Filters: not reviewed, low confidence, uncertain, borderline memristivity, etc.
- Saves your corrections to **`review_corrections.json`** (per dataset, on OneDrive)
- Also writes **`review_corrections.csv`** as a spreadsheet backup
- **Re-running `batch_classify.py` does not erase your corrections** — they are stored separately from `classification_results.json`
- Bottom panel shows accuracy, save location, and misclassification patterns as you review

### Alternative: original validation tool

```bash
python tools/classification_validation/launch_gui.py
```

Load Data → select the consolidated `data` folder (re-runs analysis; slower than batch + review GUI).
