# Gordon–Taylor blend temperature

Small standalone script to plot PMMA / solvent blend glass-transition temperature using a Gordon–Taylor-style equation.

## Run

```powershell
python tools/gordon_temperature/gordon_temp.py
```

Opens a matplotlib plot of blend Tg vs solvent weight fraction.

## Parameters

Edit constants at the top of `gordon_temp.py`:

- `PMMA_TG_K` — PMMA glass transition (K)
- `TOL_TG_K` — solvent glass transition (K)
- `K_FACTOR` — Gordon–Taylor interaction constant
