# Solartron SI 1260 Capacitance Tool

SMaRT replacement for the legacy Solartron SI 1260 Impedance Analyzer: PyQt5 GUI over GPIB (PyVISA), guided Open → Short → Device calibration, Origin-ready CSV export, and in-app preview plots.

## Run

From the repo root (with the project venv active):

```bash
python tools/solartron_1260/run_gui.py
```

or:

```bash
python tools/solartron_1260/main.py
```

Install tool extras if needed:

```bash
pip install -r tools/solartron_1260/requirements.txt
```

## Save location

Uses the same shared lab root as the Sample GUI / PMU tool
(`resolve_default_save_root()` → OneDrive `Documents\Data_folder`):

```text
<Data_folder>/<Sample>/<Section>/<Device #>/Solartron_1260/<N>-<kind>_<timestamp>/
  origin_data/
  graphs/
  raw/
  meta.json
```

- **Sample** — editable combobox of existing folders under Data_folder (↻ to rescan)
- **Section** — A–L
- **Device #** — 1–10
- **Run notes** — optional tag (e.g. `hrs_after_55`, `lrs_after`, `laser`) baked into folder + CSV names and `meta.json`

Sample / section / device / notes / sweep presets / bias series settings are remembered in
`solartron_1260_config.json` between sessions.

## Quick workflow

1. On launch: **auto-connects to `GPIB0::8::INSTR`**; Connection panel starts collapsed. Left sections are collapsible (checkbox in title).
2. Set **Sample / Section / Device #** and optional **Run notes**.
3. Set **points per decade**, `VA`, optional `VB` (CRLF terminator fixed).
4. **Device only** (or Open → Short → Device).
5. Bias series: start/stop/step → **Run bias series**.

### Why Cs / Cp are sometimes blank (NaN)

Capacitance is only defined when reactance **X < 0** (capacitive). If **X ≥ 0**, `Cs`/`Cp` are NaN on purpose.

## Output layout

```text
<Data_folder>/<Sample>/<Section>/<Device>/Solartron_1260/
  <N>-device_<timestamp>/
    origin_data/*.csv
    graphs/*.png
    raw/*_full.csv
    meta.json
  origin_compare/                 # auto-refreshed after every save
    all_datasets_long.csv         # filter by Dataset for any combo
    origin_compare_C_vs_f.csv
    origin_compare_bode.csv
    origin_compare_Zreal_vs_f.csv # Frequency vs Z'
    origin_compare_Zimag_vs_f.csv # Frequency vs -Z''
    origin_compare_nyquist.csv
  combined_plots/                 # overlay PNGs of all runs on this device
  eis_analyser/                   # EIS Spectrum Analyser (eissa1.exe) ready
    <dataset_label>.txt           # File → Open data file
```

After each device / bias-series export, `auto_compare.py` rebuilds the device-level
`origin_compare/` CSVs, `combined_plots/`, and `eis_analyser/` `.txt` files
(for [EIS Spectrum Analyser](http://www.abc.chemistry.bsu.by/vi/analyser/) /
`C:\eisanalyser\eissa1.exe`: first line = `n`, then `ReZ  -ImZ  Freq` descending).

Manual rebuild (any folder of runs):

```bash
python tools/solartron_1260/useful_scripts/combine_bias_origin_csvs.py "D:\...\Solartron_1260"
```

Origin columns match `tools/impedance_analyzer/origin_export.py`:

`Frequency_Hz, Z_Magnitude_Ohms, Phase_deg, Capacitance_F, Z_Real_Ohms, Z_Imag_Ohms`

Corrected runs also include `*_corrected` columns. Note: `Z_Imag_Ohms` is already `−Im(Z)` for Nyquist (plot vs `Z_Real_Ohms` with no extra sign flip).

## GPIB diagnose

```bash
python tools/solartron_1260/diagnose_gpib.py
```

Close the GUI first so the GPIB resource is free. Measure command is **`SI`** (not `SW`).

## GPIB commands used

| Command | Meaning |
|---------|---------|
| `OT1` / `OS0` | GPIB terminator CR LF+EOI, comma separator |
| `OP2,1` | Send all readings to GPIB |
| `CZ0` | Impedance coordinates R, X |
| `VA <v>` | AC amplitude (volts) |
| `FR <f>` | Set frequency (Hz) |
| `SI` | Single measurement; reply `F,R,X,error,limits` |

## Automation

Measurement logic lives in `engine.py` (no UI). The GUI calls it via `workers.py`. A future sequence runner can import `SweepEngine` / `SweepConfig` and call `run_sweep(...)` without opening the window.

## VISA backend note

GPIB-USB adapters (NI GPIB-USB-HS, Keysight 82357B, etc.) need a **native VISA backend** — typically **NI-VISA** or **Keysight IO Libraries**. PyVISA is only the Python front-end; **PyVISA-py** alone usually cannot drive classic GPIB-USB hardware. After installing a backend, use **List resources** to confirm the address.
