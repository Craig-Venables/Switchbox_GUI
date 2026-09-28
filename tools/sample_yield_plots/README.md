# Sample yield plots

Small standalone script that plots device yield against polymer percentage and internal phase separation. The labelled sample table lives in `main.py`.

This tool is separate from the main Switchbox application. It could live in its own repository; it stays here so it is easy to run next to the lab software.

## Run

From the repository root:

```powershell
python tools/sample_yield_plots/main.py
```

Figures are written to `tools/sample_yield_plots/output/` (gitignored):

- `yield_by_polymer_labeled.png`
- `yield_vs_separation.png`

## Dependencies

`pandas`, `matplotlib`, and `seaborn`, already listed in the repository `requirements.txt`.
