# SMaRT Impedance Analyzer tools

Load and plot data from SMaRT impedance analyzer CSV and binary `.dat` exports (e.g. Solartron ModuLab).

If this folder is still named `Impedence Analyzer`, you can rename it to `Impedance Analyzer` when nothing is using it (e.g. close the IDE), then use the import path `tools.Impedance Analyzer` below.

## Open/Short Calibration and Corrected Data

### Overview

Impedance measurements include parasitic contributions from the measurement system (probe capacitance, lead resistance/inductance, etc.). This tool implements a **5-step correction procedure** to remove these system parasitics and extract the true device impedance and capacitance.

### Correction Procedure (with Equations)

The correction process operates on **complex impedance** and **admittance**, not directly on capacitance values. This ensures physically correct compensation.

#### Step 1: Construct Complex Impedance

From magnitude and phase measurements, build the complex impedance for Open, Short, and Device:

\[
Z = Z_{real} + j \cdot Z_{imag}
\]

where:
- \( Z_{real} = |Z| \cos(\phi) \)
- \( Z_{imag} = |Z| \sin(\phi) \)
- \( \phi \) is the phase angle in radians

#### Step 2: Remove Short (Series) Contribution First

The short measurement mostly tells you the series lead impedance. Remove the series lead effect first:

\[
Z_s(f) = Z_{short}(f)
\]

Subtract it from the measured device:

\[
Z'(f) = Z_{device}(f) - Z_s(f)
\]

This removes lead resistance, inductance, and other series parasitics. The short-circuit data is interpolated to match the device measurement frequencies.

#### Step 3: Remove Open (Parallel) Contribution

But first remove the same series effect from the open too:

\[
Z_{open,shunt}(f) = Z_{open}(f) - Z_s(f)
\]

Convert that to the setup's parallel admittance:

\[
Y_p(f) = \frac{1}{Z_{open,shunt}(f)}
\]

Convert your device-after-series-removal to admittance and subtract:

\[
Y'(f) = \frac{1}{Z'(f)}
\]

\[
Y_{DUT}(f) = Y'(f) - Y_p(f)
\]

Convert back to get the corrected device impedance:

\[
Z_{DUT}(f) = \frac{1}{Y_{DUT}(f)}
\]

This removes stray capacitance between probes and other parallel parasitics. The open-circuit data is interpolated to match the device measurement frequencies.

**Note:** It is critical to remove the series (short) effect from both the device AND the open measurement before using the open to remove parallel effects. This ensures physically correct compensation.

#### Step 4: Extract True Capacitance

The corrected capacitance is derived from the imaginary part of admittance:

\[
C = \frac{B}{\omega}
\]

where \( B = \text{Im}(Y_{DUT}) \) is the susceptance (imaginary part of \( Y_{DUT} \)) and \( \omega = 2\pi f \) is the angular frequency.

### Auto-Detection of Calibration Files

When processing a **folder** of CSV files, the tool automatically searches for calibration files by scanning filenames for keywords:

- **Open-circuit files**: Detects filenames containing `open`, `open_circuit`, `open_loop`, or `oc` (case-insensitive)
- **Short-circuit files**: Detects filenames containing `short`, `short_circuit`, `short_loop`, `sc`, `closed`, or `closed_circuit` (case-insensitive)

**Detection behavior:**
- Standalone script: Prompts "*Use these for calibration? [Y/n]*" if files are found
- GUI: Shows a dialog with options to "Use detected", "Skip calibration", or "Pick files manually"
- CLI: Use `--open` and `--short` flags to explicitly specify calibration files

The first matching file for each type is used. If multiple matches exist, you can manually select via the GUI dialog or CLI flags.

### Frequency Interpolation

Calibration data (open/short) may be measured at different frequencies than device data. The tool uses **linear interpolation** to align calibration data to device frequencies:

- Interpolation is performed on the complex impedance components (real and imaginary parts)
- Data outside the calibration frequency range is set to `NaN` (not extrapolated)
- This ensures corrections are only applied where calibration data is valid

### Output Structure

When calibration is applied:

- **Uncorrected data**: Always saved to `graphs/uncorrected/` and `graphs/uncorrected/origin_data/` for reference
- **Corrected data**: Saved to `graphs/` (plots) and `origin_data/` (CSV files)
- **Origin CSV format**: Includes both uncorrected and corrected columns:
  - Uncorrected: `Z_Magnitude_Ohms`, `Phase_deg`, `Capacitance_F`, `Z_Real_Ohms`, `Z_Imag_Ohms`
  - Corrected: `Z_Magnitude_Ohms_corrected`, `Phase_deg_corrected`, `Capacitance_F_corrected`, `Z_Real_Ohms_corrected`, `Z_Imag_Ohms_corrected`

This allows easy comparison and plotting of both datasets in Origin.

### Nyquist Plot Analysis

For Nyquist plots (imaginary vs. real impedance), the tool automatically extracts:

- **High-frequency intercept**: Series resistance \( R_s \) (where curve meets real axis at high frequency)
- **Low-frequency intercept**: Parallel resistance \( R_p \) (where curve meets real axis at low frequency)
- **Peak frequency**: Frequency at maximum \( -\text{Im}(Z) \) (peak of semicircle)
- **Relaxation time**: \( \tau = \frac{1}{2\pi f_{peak}} \)

These parameters are annotated on plots and saved to `nyquist_parameters.csv` (and `nyquist_parameters_corrected.csv` if calibration is used).

## Quick run

From this folder:

```bash
python visualise_csv.py [path]   # CSV file or folder of CSVs
python visualise_csv.py folder --open path/to/open.csv --short path/to/short.csv   # with calibration
python visualise_dat.py [path]   # .dat file or folder of .dat files
```

Or set `DATA_PATH` at the top of each script and run without arguments.

## Using Calibration

When using a **folder** of CSVs, you can remove system capacitance (open-circuit) and series parasitics (short-circuit) by providing calibration files:

- **CLI**: `--open` and `--short` paths to the open- and short-circuit CSV files.
- **Standalone (no CLI)**: The script auto-detects files whose names contain "open" / "short" (or "oc" / "sc" / "closed") and prompts: *Use these for calibration? [Y/n]*.
- **GUI**: The measurement GUI shows a dialog to "Use detected", "Skip calibration", or "Pick files...", then passes the chosen paths to the script.

See the [Open/Short Calibration](#openshort-calibration-and-corrected-data) section above for detailed explanation of the correction procedure and equations.

## Options (in script)

At the top of `visualise_csv.py` and `visualise_dat.py`:

| Option | Default | Meaning |
|--------|---------|---------|
| `MAX_FREQ` | `1e6` | Data above this frequency (Hz) is greyed out on plots. Set to `None` to show all. |
| `SAVE_GRAPHS` | `True` | Save figures into `<path>/graphs/` and `<path>/uncorrected/graphs/`. |
| `SAVE_ORIGIN` | `True` | Export Origin CSVs into `<path>/origin_data/` and `<path>/uncorrected/origin_data/`. |

## Outputs

- **uncorrected/** — Uncorrected data and graphs (always written when using a folder):
  - **uncorrected/graphs/** — Magnitude, Nyquist, phase, capacitance, full_2x2 per CSV (uncorrected).
  - **uncorrected/origin_data/** — One CSV per dataset with uncorrected columns only.

- **graphs/** — When **calibration is used**: corrected comparison plots and per-CSV full 2x2. When **no calibration**: same as before (uncorrected comparison plots and full 2x2).

- **origin_data/** — One CSV per dataset:
  - **With calibration**: columns include uncorrected and corrected (`Z_Magnitude_Ohms_corrected`, `Phase_deg_corrected`, `Capacitance_F_corrected`, `Z_Real_Ohms_corrected`, `Z_Imag_Ohms_corrected`) for plotting in Origin.
  - **Without calibration**: same as before (`Frequency_Hz`, `Z_Magnitude_Ohms`, `Phase_deg`, `Capacitance_F`, `Z_Real_Ohms`, `Z_Imag_Ohms`).

Combination plots use a larger figure size and a smaller/outside legend when there are more than 10 series.

## Comparing Combinations of Files

The **Compare Combinations** feature allows you to compare multiple sets of CSV files side-by-side. This is useful for comparing different measurement conditions, time points, or device states.

### How It Works

1. **Select Combinations**: Create named combinations (e.g., "Before_Forming", "After_Forming") and add CSV files to each combination
2. **Auto-naming**: If you don't provide a name, combinations are auto-named as `Combination_1`, `Combination_2`, etc.
3. **Data Loading**: 
   - Supports both SMaRT CSV format and Origin CSV format
   - Automatically detects and uses **corrected data** from Origin CSVs if available (when `use_corrected=True`)
   - Falls back to uncorrected data if corrected columns are not found
4. **Output**: Generates comparison plots and Origin CSV files

### Output Files

For each comparison run:

- **Plots** (saved to `graphs/combinations/`):
  - `magnitude_comparison_{names}.png` — Impedance magnitude vs. frequency
  - `phase_comparison_{names}.png` — Phase vs. frequency
  - `capacitance_comparison_{names}.png` — Capacitance vs. frequency
  - `nyquist_comparison_{names}.png` — Nyquist plot (imaginary vs. real impedance)

- **Origin CSV files** (saved to `graphs/combinations/`):
  - One CSV per combination: `{combination_name}_origin.csv`
  - Contains all datasets from that combination in a single file
  - Columns: `Frequency_Hz`, `Dataset`, `Z_Magnitude_Ohms`, `Phase_deg`, `Capacitance_F`, `Z_Real_Ohms`, `Z_Imag_Ohms`
  - The `Dataset` column identifies which file each row came from
  - Ready to import directly into Origin Graph for plotting

### Usage

- **GUI**: Use the "Compare Combinations" button in the Impedance Analyzer section of the Graphing tab
- **CLI**: 
  ```bash
  python compare_combinations.py <output_dir> <combo1_name:file1,file2,...> [combo2_name:file1,file2,...] ...
  ```

### Data Format Handling

The combination comparison tool intelligently handles different CSV formats:

1. **SMaRT CSV**: Uses the standard SMaRT loader (handles 3-line headers)
2. **Origin CSV (uncorrected)**: Detects Origin format and converts to standard internal format
3. **Origin CSV (corrected)**: If corrected columns exist (`*_corrected`), prioritizes those when `use_corrected=True`

This allows you to mix different file formats in the same comparison.

## Package use

From repo root:

```python
from tools.Impedence Analyzer import (
    load_smart_csv,
    load_impedance_folder,
    load_smart_dat,
    filter_by_max_frequency,
    export_origin_csv,
    export_origin_csv_with_corrected,
    apply_open_short_correction,
    detect_open_short_paths,
    plot_all,
    plot_folder_comparison,
)
```
