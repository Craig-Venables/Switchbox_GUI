# IV classification

Rule-based IV sweep classification for memristive and related device types. This page describes how classification fits into **Switchbox_GUI** and where the **separate documentation repo** lives.

## GitHub repo (canonical record)

**https://github.com/Craig-Venables/memristive-iv-classifier**

That repo holds:

| Content | Description |
|---------|-------------|
| `analysis/` | `SweepAnalyzer`, `quick_analyze`, device tracking JSON |
| `tools/data_consolidation/` | Flatten datasets, batch classify, review GUIs |
| `tools/classification_validation/` | Weight tuning and validation |
| `docs/` | Architecture, rules, data formats, API, batch workflow |
| `examples/` | Standalone scripts (no GUI) |

**Local clone (sibling folder):**

```
C:\Users\Craig-Desktop\Documents\GitHub\pythonProject\memristive-iv-classifier
```

Start reading there at **`docs/README.md`** for the full technical write-up.

---

## Daily workflow (this repo)

Develop classification **here**, in Switchbox_GUI:

```
Switchbox_GUI/
  analysis/                          ← edit classifier here
  gui/measurement_gui/main.py        ← live post-sweep pipeline
  gui/sample_gui/classification_overlay.py   ← map colors
  tools/data_consolidation/          ← batch tools (also mirrored externally)
```

The app imports `analysis/` directly. **No pip install, no submodule, no second codebase to edit day-to-day.**

---

## What runs when you measure

After each sweep (Measurement GUI):

1. `quick_analyze(..., analysis_level='classification')`
2. Device tracking JSON → `{sample}/sample_analysis/analysis/device_tracking/{device_id}_history.json`
3. `classification_log.txt` in the device folder
4. IV dashboard PNG (always)
5. Sample GUI map overlay refresh

**Extended** checkbox adds analysis report `.txt` and stats panel only — not core classification.

See also: [SYNC.md](SYNC.md) for refreshing the external repo.

---

## Integration map

| Feature | Switchbox_GUI path |
|---------|-------------------|
| Live classification | `gui/measurement_gui/main.py` → `_run_analysis_if_enabled` |
| Classification log | `gui/measurement_gui/main.py` → `_append_classification_log` |
| Sample map overlay | `gui/sample_gui/classification_overlay.py` |
| Overlay rules (≥2 sweeps, score ≥60) | `gui/measurement_gui/yield_concentration/yield_source.py` → `summarize_device_from_history` |
| Chip yield manifest | `gui/measurement_gui/yield_concentration/yield_source.py` → `resolve_yield` |
| Batch classify | `tools/data_consolidation/batch_classify.py` |
| Weight tuning | `tools/classification_validation/launch_gui.py` |

---

## Refresh & push the GitHub snapshot

When you want a Git record (milestone, paper, handoff):

```powershell
# 1. From Switchbox_GUI root — copy code to sibling repo
.\tools\sync_to_classifier_repo.ps1

# 2. Commit and push
cd ..\memristive-iv-classifier
git add -A
git status
git commit -m "Sync from Switchbox_GUI"
git push
```

Custom target path:

```powershell
.\tools\sync_to_classifier_repo.ps1 -TargetRepo "D:\path\to\memristive-iv-classifier"
```

The sync script copies `analysis/`, `tools/data_consolidation/`, and `tools/classification_validation/`, then applies a small patch so the external repo imports without the full `plotting` package.

**Frequency:** whenever you choose — not on every commit.

Full details: [SYNC.md](SYNC.md) and the external repo’s [SYNC.md](https://github.com/Craig-Venables/memristive-iv-classifier/blob/master/SYNC.md).

---

## Clone on another machine

```powershell
git clone https://github.com/Craig-Venables/memristive-iv-classifier.git
cd memristive-iv-classifier
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python examples/classify_single_sweep.py tools/classification_validation/files_for_testing/3-FS-2.0v-0.05sv-0.05sd-Py-St_v2-.txt
```

---

## Related docs in this repo

| Doc | Location |
|-----|----------|
| Analysis module overview | `analysis/README.md` |
| Sample analysis structure | `analysis/ANALYSIS_STRUCTURE.md` |
| Data consolidation workflow | `tools/data_consolidation/README.md` |
| Validation / tuning tool | `tools/classification_validation/README.md` |

External (mirrored) deep docs: [memristive-iv-classifier/docs/](https://github.com/Craig-Venables/memristive-iv-classifier/tree/master/docs)
