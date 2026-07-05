# IV classification — documentation snapshot

The rule-based IV classifier and offline batch/review tools are documented and snapshotted in a **separate local repo**:

**[../memristive-iv-classifier](../memristive-iv-classifier)** (sibling folder)

That repo contains:

- `analysis/` — `SweepAnalyzer`, `quick_analyze`, device tracking JSON
- `tools/data_consolidation/` — batch classify and review
- `tools/classification_validation/` — weight tuning
- Detailed docs under `docs/`

## Daily workflow (unchanged)

Develop classification in **this repo** (`Switchbox_GUI/analysis/`). The app uses it directly — no pip install or submodule.

## Refresh the snapshot

When you want a Git record or shareable copy:

```powershell
.\tools\sync_to_classifier_repo.ps1
```

Then commit in `memristive-iv-classifier`. See that repo's `SYNC.md`.

## Integration in this app

| Component | Path |
|-----------|------|
| Live classification | `gui/measurement_gui/main.py` → `_run_analysis_if_enabled` |
| Sample map overlay | `gui/sample_gui/classification_overlay.py` |
| Yield from tracking | `gui/measurement_gui/yield_concentration/yield_source.py` |

Push `memristive-iv-classifier` to GitHub when ready (`gh auth login` then see its README).
