# SMaRT Impedance Analyzer tools

Load and plot data from SMaRT impedance analyzer CSV and binary `.dat` exports (e.g. Solartron ModuLab).

If this folder is still named `Impedence Analyzer`, you can rename it to `Impedance Analyzer` when nothing is using it (e.g. close the IDE), then use the import path `tools.Impedance Analyzer` below.

## Quick run

From this folder:

```bash
python visualise_csv.py [path]   # CSV file or folder of CSVs
python visualise_dat.py [path]   # .dat file or folder of .dat files
```

Or set `DATA_PATH` at the top of each script and run without arguments.

## Options (in script)

At the top of `visualise_csv.py` and `visualise_dat.py`:

| Option | Default | Meaning |
|--------|---------|---------|
| `MAX_FREQ` | `1e6` | Remove data above this frequency (Hz). Set to `None` to keep all. |
| `SAVE_GRAPHS` | `True` | Save figures into `<path>/graphs/`. |
| `SAVE_ORIGIN` | `True` | Export Origin-ready CSVs into `<path>/origin_data/`. |

## Outputs

- **graphs/** — PNGs: magnitude, nyquist (combined + per-CSV), phase, capacitance, full_2x2 per CSV.
- **origin_data/** — One CSV per dataset (`<name>_origin.csv`) with columns: `Frequency_Hz`, `Z_Magnitude_Ohms`, `Phase_deg`, `Capacitance_F`, `Z_Real_Ohms`, `Z_Imag_Ohms` for use in Origin (Bode, C vs f, Nyquist).

## Package use

From repo root:

```python
from tools.Impedance Analyzer import (
    load_smart_csv,
    load_impedance_folder,
    load_smart_dat,
    filter_by_max_frequency,
    export_origin_csv,
    plot_all,
    plot_folder_comparison,
)
```
