"""
Compare combinations of impedance CSV files.

Allows selecting multiple CSV files to form combinations, then compares
all combinations with each other. Saves plots to graphs/combinations/.

Supports both SMaRT CSV format and Origin CSV format (with corrected columns).
If Origin CSV has corrected columns, those are used automatically.
"""

from pathlib import Path
from typing import Dict, List, Optional
import sys

try:
    from smart_loader import load_smart_csv
    from impedance_plots import plot_folder_comparison, FREQ, MAG, PHASE, CAP
    from origin_export import _build_origin_columns
except ImportError:
    from smart_loader import load_smart_csv
    from impedance_plots import plot_folder_comparison, FREQ, MAG, PHASE, CAP
    from origin_export import _build_origin_columns

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Data above this frequency (Hz) is greyed out on plots
MAX_FREQ = 1e6


def _load_csv_with_corrected(csv_path: Path, use_corrected: bool = True) -> Optional[pd.DataFrame]:
    """
    Load CSV file, detecting if it's Origin format with corrected columns.
    
    If Origin CSV has corrected columns and use_corrected=True, converts to standard
    format using corrected data. Otherwise uses uncorrected data.
    
    Returns DataFrame in standard format: Frequency (Hz), Impedance Magnitude (Ohms), etc.
    """
    if not csv_path.exists():
        return None
    
    # First, try loading as SMaRT CSV (handles special header format)
    try:
        df_smart = load_smart_csv(csv_path)
        # If it loaded successfully and has standard columns, it's SMaRT format
        if FREQ in df_smart.columns or "Frequency (Hz)" in df_smart.columns:
            return df_smart
    except Exception:
        # Not SMaRT format, continue to check Origin format
        pass
    
    # Try reading as regular CSV to check if it's Origin format
    try:
        df_raw = pd.read_csv(csv_path)
    except Exception as e:
        # If regular CSV read fails, try SMaRT loader one more time with error details
        try:
            return load_smart_csv(csv_path)
        except Exception:
            print(f"Warning: Failed to read CSV {csv_path.name}: {e}")
            return None
    
    # Check if this is an Origin CSV (has Frequency_Hz column)
    if "Frequency_Hz" in df_raw.columns:
        # Origin CSV format - convert to standard format
        out = pd.DataFrame()
        out[FREQ] = pd.to_numeric(df_raw["Frequency_Hz"], errors="coerce")
        
        # Check if corrected columns exist
        has_corrected = use_corrected and "Z_Magnitude_Ohms_corrected" in df_raw.columns
        
        if has_corrected:
            # Use corrected columns
            out[MAG] = pd.to_numeric(df_raw["Z_Magnitude_Ohms_corrected"], errors="coerce")
            out[PHASE] = pd.to_numeric(df_raw["Phase_deg_corrected"], errors="coerce")
            out[CAP] = pd.to_numeric(df_raw["Capacitance_F_corrected"], errors="coerce")
        else:
            # Use uncorrected columns
            out[MAG] = pd.to_numeric(df_raw["Z_Magnitude_Ohms"], errors="coerce")
            out[PHASE] = pd.to_numeric(df_raw["Phase_deg"], errors="coerce")
            out[CAP] = pd.to_numeric(df_raw["Capacitance_F"], errors="coerce")
        
        return out
    else:
        # Not Origin format, try SMaRT loader as last resort
        try:
            return load_smart_csv(csv_path)
        except Exception as e:
            print(f"Warning: Failed to load {csv_path.name} as SMaRT CSV: {e}")
            return None


def export_combined_origin_csv(
    all_data: Dict[str, pd.DataFrame],
    output_dir: Path,
    combinations: Dict[str, List[Path]],
) -> None:
    """
    Export combination data to Origin CSV files (one per combination).
    
    Creates columns: Frequency_Hz, Dataset, Z_Magnitude_Ohms, Phase_deg, 
    Capacitance_F, Z_Real_Ohms, Z_Imag_Ohms for easy plotting in Origin.
    Each dataset is identified by the Dataset column.
    Each combination gets its own CSV file named after the combination.
    """
    # Group datasets by combination name
    combo_datasets = {}
    for dataset_name, df in all_data.items():
        # Extract combination name from dataset name (format: "combo_name_filename")
        # Find which combination this dataset belongs to
        combo_name = None
        for cname in combinations.keys():
            # Dataset name format is "combo_name_filename", so check if it starts with combo_name
            if dataset_name.startswith(f"{cname}_"):
                combo_name = cname
                break
        
        if combo_name is None:
            # Fallback: try partial match
            for cname in combinations.keys():
                if cname in dataset_name:
                    combo_name = cname
                    break
        
        if combo_name is None:
            combo_name = "Unknown"
        
        if combo_name not in combo_datasets:
            combo_datasets[combo_name] = []
        combo_datasets[combo_name].append((dataset_name, df))
    
    # Export one CSV per combination
    for combo_name, datasets in combo_datasets.items():
        combined_rows = []
        
        for dataset_name, df in datasets:
            # Build Origin columns for this dataset
            try:
                origin_df = _build_origin_columns(df, FREQ, MAG, PHASE, CAP)
                # Add dataset name column (just the filename part, not combo name)
                # Dataset name format is "combo_name_filename", so remove combo_name prefix
                if dataset_name.startswith(f"{combo_name}_"):
                    display_name = dataset_name[len(combo_name)+1:]  # Remove "combo_name_"
                else:
                    display_name = dataset_name
                origin_df["Dataset"] = display_name
                # Reorder: Frequency, Dataset, then measurements
                cols = ["Frequency_Hz", "Dataset", "Z_Magnitude_Ohms", "Phase_deg", 
                       "Capacitance_F", "Z_Real_Ohms", "Z_Imag_Ohms"]
                origin_df = origin_df[cols]
                combined_rows.append(origin_df)
            except Exception as e:
                print(f"  Warning: Failed to export {dataset_name} to Origin CSV: {e}")
                continue
        
        if not combined_rows:
            print(f"  No data to export for combination '{combo_name}'.")
            continue
        
        # Concatenate all datasets for this combination
        combined = pd.concat(combined_rows, ignore_index=True)
        
        # Sort by frequency and dataset name for easier viewing
        combined = combined.sort_values(["Frequency_Hz", "Dataset"]).reset_index(drop=True)
        
        # Save to CSV (sanitize combo_name for filename)
        safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in combo_name)
        safe_name = safe_name.replace(' ', '_')
        output_file = output_dir / f"{safe_name}_origin.csv"
        combined.to_csv(output_file, index=False, na_rep="")
        print(f"  Saved Origin CSV for '{combo_name}': {output_file.name}")
        print(f"    Contains {len(combined)} rows from {len(combined_rows)} dataset(s)")


def compare_combinations(
    combinations: Dict[str, List[Path]],
    output_dir: Path,
    max_trusted_freq: Optional[float] = MAX_FREQ,
    use_corrected: bool = True,
) -> None:
    """
    Compare multiple combinations of CSV files.
    
    Parameters
    ----------
    combinations : dict mapping combination_name -> list of CSV paths
    output_dir : directory to save plots (will create graphs/combinations/ subfolder)
    max_trusted_freq : frequency threshold for greyed-out data
    use_corrected : if True, use corrected columns from Origin CSVs when available
    """
    # Load all CSV files
    all_data = {}
    corrected_count = 0
    print(f"Loading {sum(len(files) for files in combinations.values())} CSV file(s) from {len(combinations)} combination(s)...")
    
    for combo_name, csv_paths in combinations.items():
        print(f"\nProcessing combination '{combo_name}' ({len(csv_paths)} files)...")
        for csv_path in csv_paths:
            csv_path = Path(csv_path)
            if not csv_path.exists():
                print(f"  ERROR: File not found: {csv_path}")
                continue
            
            try:
                df = _load_csv_with_corrected(csv_path, use_corrected=use_corrected)
                if df is None or df.empty:
                    print(f"  WARNING: Failed to load or empty: {csv_path.name}")
                    continue
                
                # Check if we used corrected data
                try:
                    orig_df = pd.read_csv(csv_path)
                    if "Frequency_Hz" in orig_df.columns and "Z_Magnitude_Ohms_corrected" in orig_df.columns:
                        if use_corrected:
                            corrected_count += 1
                            print(f"  ✓ Loaded {csv_path.name} (using corrected data)")
                        else:
                            print(f"  ✓ Loaded {csv_path.name} (using uncorrected data)")
                    else:
                        print(f"  ✓ Loaded {csv_path.name}")
                except Exception as e:
                    print(f"  ✓ Loaded {csv_path.name} (could not check for corrected columns: {e})")
                
                # Validate that DataFrame has required columns and data
                required_cols = [FREQ, MAG, PHASE]
                missing = [col for col in required_cols if col not in df.columns]
                if missing:
                    print(f"  ERROR: {csv_path.name} missing required columns: {missing}")
                    print(f"  Available columns: {list(df.columns)}")
                    continue
                
                if len(df) == 0:
                    print(f"  WARNING: {csv_path.name} has no data rows")
                    continue
                
                # Use combination name + file stem as key
                key = f"{combo_name}_{csv_path.stem}"
                all_data[key] = df
                print(f"    Added to dataset: {key}")
            except Exception as e:
                print(f"  ERROR loading {csv_path.name}: {e}")
                import traceback
                traceback.print_exc()
                continue
    
    if corrected_count > 0:
        print(f"Using corrected data from {corrected_count} Origin CSV file(s).")
    elif use_corrected:
        print("Note: No Origin CSVs with corrected columns found. Using uncorrected data.")
    
    if not all_data:
        print("\nERROR: No data loaded. Check file paths and formats.")
        return
    
    print(f"\nSuccessfully loaded {len(all_data)} dataset(s).")
    
    # Create output directory
    combinations_dir = output_dir / "graphs" / "combinations"
    try:
        combinations_dir.mkdir(parents=True, exist_ok=True)
        print(f"Output directory: {combinations_dir}")
    except Exception as e:
        print(f"ERROR: Failed to create output directory {combinations_dir}: {e}")
        return
    
    def save_fig(fig, name: str):
        try:
            filepath = combinations_dir / f"{name}.png"
            fig.savefig(filepath, dpi=150, bbox_inches="tight")
            print(f"  Saved {filepath.name}")
        except Exception as e:
            print(f"  ERROR saving {name}: {e}")
            import traceback
            traceback.print_exc()
    
    # Export Origin CSV files (one per combination)
    try:
        print(f"\nExporting Origin CSV files...")
        export_combined_origin_csv(all_data, combinations_dir, combinations)
    except Exception as e:
        print(f"  ERROR exporting Origin CSV: {e}")
        import traceback
        traceback.print_exc()
    
    # Plot comparisons for each plot type
    plot_types = ["magnitude", "phase", "capacitance", "nyquist"]
    combo_names_str = "_vs_".join(combinations.keys())
    
    print(f"\nGenerating comparison plots...")
    for plot_type in plot_types:
        try:
            print(f"  Creating {plot_type} plot...")
            fig = plot_folder_comparison(all_data, plot_type=plot_type, max_trusted_freq=max_trusted_freq)
            fig.suptitle(f"{plot_type.title()} comparison: {combo_names_str}")
            save_fig(fig, f"{plot_type}_comparison_{combo_names_str}")
            plt.show(block=False)
            plt.close(fig)  # Close to free memory
        except Exception as e:
            print(f"  ERROR creating {plot_type} plot: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    print(f"\nCombination plots saved to {combinations_dir}")


def main():
    """CLI entry point - expects combinations as arguments."""
    if len(sys.argv) < 3:
        print("Usage: python compare_combinations.py <output_dir> <combo1_name:file1,file2,...> [combo2_name:file1,file2,...] ...")
        print("Example: python compare_combinations.py ./output combo1:file1.csv,file2.csv combo2:file3.csv,file4.csv")
        return
    
    output_dir = Path(sys.argv[1])
    combinations = {}
    
    for arg in sys.argv[2:]:
        if ":" not in arg:
            print(f"Warning: Invalid format '{arg}', expected 'name:file1,file2,...'")
            continue
        name, files_str = arg.split(":", 1)
        files = [Path(f.strip()) for f in files_str.split(",")]
        combinations[name] = files
    
    if not combinations:
        print("No valid combinations provided.")
        return
    
    compare_combinations(combinations, output_dir)


if __name__ == "__main__":
    try:
        main()
        print("\n" + "="*60)
        print("Combination comparison complete! Check graphs/combinations/ folder.")
        print("="*60)
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Keep console open so user can see output
        try:
            input("\nPress Enter to close this window...")
        except:
            pass  # If running non-interactively, just exit
