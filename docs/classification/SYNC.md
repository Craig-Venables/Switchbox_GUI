# Sync Switchbox_GUI → memristive-iv-classifier

**GitHub:** https://github.com/Craig-Venables/memristive-iv-classifier  
**Local path:** `..\memristive-iv-classifier` (sibling of Switchbox_GUI)

Switchbox_GUI is the **source of truth** for classification code. The external repo is a **snapshot + documentation** you update when you want a Git record or shareable copy.

---

## Quick sync (recommended)

From **Switchbox_GUI** root:

```powershell
.\tools\sync_to_classifier_repo.ps1
cd ..\memristive-iv-classifier
git add -A
git commit -m "Sync from Switchbox_GUI"
git push
```

---

## What gets copied

| Source (Switchbox_GUI) | Destination (memristive-iv-classifier) |
|------------------------|----------------------------------------|
| `analysis/` | `analysis/` |
| `tools/data_consolidation/` | `tools/data_consolidation/` |
| `tools/classification_validation/` | `tools/classification_validation/` |

**Not copied:** GUI code, `plotting/`, hardware, `Json_Files/`, root `requirements.txt`.

**Not overwritten in target:** `docs/`, `examples/`, root `README.md`, `SYNC.md` in the classifier repo (update those manually when behaviour changes).

---

## Post-sync patch

After robocopy, the sync script runs `memristive-iv-classifier/tools/apply_standalone_patch.ps1`. This makes `from analysis import quick_analyze` work in the external repo without the full Switchbox_GUI `plotting` package.

If you sync manually with robocopy, run the patch yourself:

```powershell
cd ..\memristive-iv-classifier
.\tools\apply_standalone_patch.ps1
```

---

## Manual robocopy (alternative)

From Switchbox_GUI root:

```powershell
$dest = "..\memristive-iv-classifier"
robocopy analysis\ "$dest\analysis" /MIR /XD __pycache__ /XF *.pyc
robocopy tools\data_consolidation\ "$dest\tools\data_consolidation" /MIR /XD __pycache__ /XF *.pyc *.log
robocopy tools\classification_validation\ "$dest\tools\classification_validation" /MIR /XD __pycache__ /XF *.pyc
cd $dest
.\tools\apply_standalone_patch.ps1
```

---

## First-time GitHub setup (already done)

Repo was created with:

```powershell
cd memristive-iv-classifier
gh auth login
gh repo create memristive-iv-classifier --public --source=. --remote=origin --push
```

To clone elsewhere:

```powershell
git clone https://github.com/Craig-Venables/memristive-iv-classifier.git
```

---

## After syncing — checklist

1. Run example classify script in classifier repo (sanity check):
   ```powershell
   python examples/classify_single_sweep.py tools/classification_validation/files_for_testing/3-FS-2.0v-0.05sv-0.05sd-Py-St_v2-.txt
   ```
2. Update classifier repo `docs/` if rules or schemas changed
3. `git commit` with a note of what changed (or Switchbox_GUI commit hash)
4. `git push`

---

## When to sync

- Before sharing with a collaborator
- Before a paper / thesis milestone
- After significant classifier changes
- **Not** required on every Switchbox_GUI commit
