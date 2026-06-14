"""
Quick visualisation for SMaRT CSV impedance exports only.

Usage:
  python visualise_csv.py [path]
  python visualise_csv.py "C:\...\Impedance Analyzer"
  python visualise_csv.py folder --open path/to/open.csv --short path/to/short.csv

Path can be a single .csv file or a folder (all .csv files are loaded and compared).
Set DATA_PATH below for a default, or pass as first argument.

Options:
  MAX_FREQ = 1e6  — data above this frequency (Hz) is greyed out on plots (noise); set to None to show all.
  SAVE_GRAPHS = True  — save figures into <path>/graphs/ and <path>/uncorrected/graphs/
  SAVE_ORIGIN = True  — export Origin-ready CSVs into <path>/origin_data/ and <path>/uncorrected/origin_data/

Open/short calibration:
  When a folder is used, --open and --short can point to calibration CSVs.
  If not given, the script may detect candidates by filename (open, short, etc.) and prompt (standalone only).
  Uncorrected data and graphs go to uncorrected/. Corrected data and graphs go to graphs/ and origin_data/.
"""

from pathlib import Path
import re
import sys
from typing import Optional
import pandas as pd

# Default: set to your CSV file or folder, or leave None and pass as argument
DATA_PATH = None  # e.g. Path(r"C:\...\Impedance Analyzer") or Path(r"...\file.csv")

# Data above this frequency (Hz) is greyed out on plots (system noise). Set None to show all as normal.
MAX_FREQ = 1e6

# Save figures and Origin CSVs under the given path
SAVE_GRAPHS = True
SAVE_ORIGIN = True

# Keywords to detect open/short calibration files (case-insensitive, match on file stem)
OPEN_KEYWORDS = re.compile(r"open|open_circuit|open_loop|oc\b", re.I)
SHORT_KEYWORDS = re.compile(r"short|short_circuit|short_loop|sc\b|closed|closed_circuit", re.I)


def detect_open_short_candidates(data_keys: list) -> tuple:
    """
    Return (open_key or None, short_key or None) from data keys (file stems).
    Picks first match for open and first for short.
    """
    open_key = None
    short_key = None
    for k in data_keys:
        if OPEN_KEYWORDS.search(k) and open_key is None:
            open_key = k
        if SHORT_KEYWORDS.search(k) and short_key is None:
            short_key = k
    return open_key, short_key


def main():
    try:
        from smart_loader import load_smart_csv, load_impedance_folder
        from impedance_plots import plot_all, plot_folder_comparison, plot_nyquist, extract_nyquist_parameters
        from origin_export import export_origin_csv, export_origin_csv_with_corrected
        from calibration import apply_open_short_correction
    except ImportError:
        from smart_loader import load_smart_csv, load_impedance_folder
        from impedance_plots import plot_all, plot_folder_comparison, plot_nyquist, extract_nyquist_parameters
        from origin_export import export_origin_csv, export_origin_csv_with_corrected
        from calibration import apply_open_short_correction

    import argparse
    import matplotlib.pyplot as plt

    p = argparse.ArgumentParser(description="Plot SMaRT impedance CSV data; optional open/short calibration")
    p.add_argument("path", type=str, nargs="?", default=None, help="Folder or single .csv file")
    p.add_argument("--open", type=str, default=None, help="Path to open-circuit calibration CSV")
    p.add_argument("--short", type=str, default=None, help="Path to short-circuit calibration CSV")
    args = p.parse_args()

    path = DATA_PATH
    if path is None and args.path:
        path = Path(args.path)
    if path is not None:
        path = Path(path)
    if path is None:
        print("Set DATA_PATH in this script or run: python visualise_csv.py <file_or_folder>")
        return

    if not path.exists():
        print("Path not found:", path)
        return

    open_path = Path(args.open) if args.open else None
    short_path = Path(args.short) if args.short else None

    output_dir = path if path.is_dir() else path.parent
    graphs_dir = output_dir / "graphs" if SAVE_GRAPHS else None
    origin_dir = output_dir / "origin_data" if SAVE_ORIGIN else None
    # Uncorrected folder is now inside graphs/
    uncorrected_graphs = graphs_dir / "uncorrected" if graphs_dir and SAVE_GRAPHS else None
    uncorrected_origin = graphs_dir / "uncorrected" / "origin_data" if graphs_dir and SAVE_ORIGIN else None
    
    # Create directories (order matters: create graphs_dir first)
    if graphs_dir:
        graphs_dir.mkdir(parents=True, exist_ok=True)
    if origin_dir:
        origin_dir.mkdir(parents=True, exist_ok=True)
    if uncorrected_graphs:
        uncorrected_graphs.mkdir(parents=True, exist_ok=True)
    if uncorrected_origin:
        uncorrected_origin.mkdir(parents=True, exist_ok=True)

    def save_fig(fig, name: str, to_dir: Optional[Path]):
        if to_dir:
            try:
                to_dir.mkdir(parents=True, exist_ok=True)
                filepath = to_dir / f"{name}.png"
                fig.savefig(filepath, dpi=150, bbox_inches="tight")
                print(f"Saved {filepath}")
            except Exception as e:
                print(f"ERROR: Failed to save {name} to {to_dir}: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"WARNING: Cannot save {name} - to_dir is None (SAVE_GRAPHS={SAVE_GRAPHS})")

    # --- Single file ---
    if path.is_file():
        if path.suffix.lower() != ".csv":
            print("Not a .csv file:", path)
            return
        try:
            df = load_smart_csv(path)
        except Exception as e:
            print("Failed to load", path.name, ":", e)
            return
        if origin_dir:
            export_origin_csv(df, origin_dir / f"{path.stem}_origin.csv")
            print("Saved", origin_dir / f"{path.stem}_origin.csv")
        if uncorrected_origin:
            export_origin_csv(df, uncorrected_origin / f"{path.stem}_origin.csv")
        fig = plot_all(df, title=path.stem, label=path.stem, show=False, max_trusted_freq=MAX_FREQ)
        if graphs_dir:
            safe = path.stem.replace(" ", "_")
            fig.savefig(graphs_dir / f"{safe}_full_2x2.png", dpi=150, bbox_inches="tight")
            print("Saved", graphs_dir / f"{safe}_full_2x2.png")
        plt.show()
        return

    # --- Folder: load all CSVs ---
    try:
        data = load_impedance_folder(path)
    except Exception as e:
        print("Failed to load folder:", e)
        return

    if not data:
        print("No CSV files in folder.")
        return

    # Resolve open/short: CLI args override; else detect and prompt (standalone)
    open_key = None
    short_key = None
    if open_path and open_path.exists():
        try:
            open_df = load_smart_csv(open_path)
            open_key = "_open_cal_"
            data[open_key] = open_df
        except Exception as e:
            print("Failed to load --open:", e)
    if short_path and short_path.exists():
        try:
            short_df = load_smart_csv(short_path)
            short_key = "_short_cal_"
            data[short_key] = short_df
        except Exception as e:
            print("Failed to load --short:", e)

    if open_key is None or short_key is None:
        cand_open, cand_short = detect_open_short_candidates(list(data.keys()))
        if cand_open or cand_short:
            if open_key is None:
                open_key = cand_open
            if short_key is None:
                short_key = cand_short
            # When run from GUI, no stdin; only prompt when no --open/--short were passed
            if not args.open and not args.short and sys.stdin.isatty():
                msg = f"Use open: {open_key!r}, short: {short_key!r} for calibration? [Y/n]: "
                if input(msg).strip().lower() == "n":
                    open_key = None
                    short_key = None

    use_calibration = open_key is not None and short_key is not None
    if use_calibration:
        open_df = data[open_key]
        short_df = data[short_key]
        device_data = {k: v for k, v in data.items() if k not in (open_key, short_key)}
    else:
        device_data = dict(data)

    # --- Uncorrected: always save to uncorrected/ ---
    for name in list(device_data.keys()):
        if uncorrected_origin:
            export_origin_csv(device_data[name], uncorrected_origin / f"{name}_origin.csv")
    if uncorrected_origin:
        print("Saved uncorrected Origin CSVs to", uncorrected_origin)
    
    # Extract and save Nyquist parameters for uncorrected data
    nyquist_params_uncorrected = []
    for name, df in device_data.items():
        if df.empty:
            continue
        try:
            params = extract_nyquist_parameters(df)
            params["Dataset"] = name
            nyquist_params_uncorrected.append(params)
        except Exception as e:
            print(f"Warning: Failed to extract Nyquist parameters for {name}: {e}")
    
    if nyquist_params_uncorrected and uncorrected_origin:
        df_params = pd.DataFrame(nyquist_params_uncorrected)
        # Reorder columns: Dataset first
        cols = ["Dataset", "series_resistance_ohms", "parallel_resistance_ohms", 
                "peak_frequency_hz", "relaxation_time_s"]
        df_params = df_params[cols]
        df_params.to_csv(uncorrected_origin / "nyquist_parameters.csv", index=False)
        print("Saved Nyquist parameters (uncorrected) to", uncorrected_origin / "nyquist_parameters.csv")

    def save_uncorrected_fig(fig, name: str):
        save_fig(fig, name, uncorrected_graphs)

    print("Loaded:", list(device_data.keys()), f"{'(data above {MAX_FREQ} Hz greyed out)' if MAX_FREQ else ''}")
    if use_calibration:
        print("Calibration: open =", open_key, ", short =", short_key)

    # Uncorrected comparison plots -> uncorrected/graphs/
    try:
        fig1 = plot_folder_comparison(device_data, plot_type="magnitude", max_trusted_freq=MAX_FREQ)
        fig1.suptitle("|Z| vs f (uncorrected) — " + path.name)
        save_uncorrected_fig(fig1, "magnitude")
        plt.show(block=False)
    except Exception as e:
        print(f"ERROR creating magnitude plot: {e}")
        import traceback
        traceback.print_exc()

    try:
        fig2 = plot_folder_comparison(device_data, plot_type="nyquist", max_trusted_freq=MAX_FREQ)
        fig2.suptitle("Nyquist (uncorrected) — " + path.name)
        save_uncorrected_fig(fig2, "nyquist_combined")
        plt.show(block=False)
    except Exception as e:
        print(f"ERROR creating nyquist plot: {e}")
        import traceback
        traceback.print_exc()
    for name, df in device_data.items():
        if df.empty:
            continue
        try:
            # Individual Nyquist plot with parameter extraction and annotation
            fig_n, ax_n = plt.subplots(figsize=(7, 7))
            ax_n, _ = plot_nyquist(df, ax=ax_n, label=name, max_trusted_freq=MAX_FREQ, extract_params=True)
            ax_n.set_title(f"Nyquist (uncorrected) — {name}")
            fig_n.suptitle(f"Nyquist (uncorrected) — {name}")
            save_uncorrected_fig(fig_n, f"nyquist_{name}")
            plt.close(fig_n)
        except (KeyError, Exception) as e:
            print(f"Warning: Failed to plot Nyquist for {name}: {e}")

    try:
        fig3 = plot_folder_comparison(device_data, plot_type="phase", max_trusted_freq=MAX_FREQ)
        fig3.suptitle("Phase vs f (uncorrected) — " + path.name)
        save_uncorrected_fig(fig3, "phase")
        plt.show(block=False)
    except Exception as e:
        print(f"ERROR creating phase plot: {e}")
        import traceback
        traceback.print_exc()

    try:
        fig4 = plot_folder_comparison(device_data, plot_type="capacitance", max_trusted_freq=MAX_FREQ)
        fig4.suptitle("Capacitance vs f (uncorrected) — " + path.name)
        save_uncorrected_fig(fig4, "capacitance")
        plt.show(block=False)
    except Exception as e:
        print(f"ERROR creating capacitance plot: {e}")
        import traceback
        traceback.print_exc()

    # Uncorrected full 2x2 per CSV -> uncorrected/graphs/
    for name, df in device_data.items():
        if df.empty:
            continue
        try:
            fig = plot_all(df, title=name + " (uncorrected)", label=name, show=False, max_trusted_freq=MAX_FREQ)
            if uncorrected_graphs:
                safe_name = name.replace(" ", "_")
                fig.savefig(uncorrected_graphs / f"{safe_name}_full_2x2.png", dpi=150, bbox_inches="tight")
                print("Saved", uncorrected_graphs / f"{safe_name}_full_2x2.png")
            plt.close(fig)
        except (KeyError, Exception):
            pass

    # --- Corrected path: apply calibration and save to graphs/ and origin_data/ ---
    # Note: device_data already excludes open/short/closed calibration files, so corrected_data
    # will also exclude them (calibration files are not useful to plot).
    if use_calibration:
        corrected_data = {}
        for name, df in device_data.items():
            if df.empty:
                continue
            try:
                corrected_data[name] = apply_open_short_correction(df, open_df, short_df)
            except Exception as e:
                print("Calibration failed for", name, ":", e)

        for name in corrected_data:
            if origin_dir:
                export_origin_csv_with_corrected(
                    device_data[name],
                    origin_dir / f"{name}_origin.csv",
                    df_corrected=corrected_data[name],
                )
        if origin_dir:
            print("Saved Origin CSVs (uncorrected + corrected columns) to", origin_dir)
        
        # Extract and save Nyquist parameters for corrected data
        nyquist_params_corrected = []
        for name, df in corrected_data.items():
            if df.empty:
                continue
            try:
                params = extract_nyquist_parameters(df)
                params["Dataset"] = name
                nyquist_params_corrected.append(params)
            except Exception as e:
                print(f"Warning: Failed to extract Nyquist parameters for {name} (corrected): {e}")
        
        if nyquist_params_corrected and origin_dir:
            df_params = pd.DataFrame(nyquist_params_corrected)
            cols = ["Dataset", "series_resistance_ohms", "parallel_resistance_ohms", 
                    "peak_frequency_hz", "relaxation_time_s"]
            df_params = df_params[cols]
            df_params.to_csv(origin_dir / "nyquist_parameters_corrected.csv", index=False)
            print("Saved Nyquist parameters (corrected) to", origin_dir / "nyquist_parameters_corrected.csv")

        fig1c = plot_folder_comparison(corrected_data, plot_type="magnitude", max_trusted_freq=MAX_FREQ)
        fig1c.suptitle("|Z| vs f (corrected) — " + path.name)
        save_fig(fig1c, "magnitude_corrected", graphs_dir)
        plt.show()

        fig2c = plot_folder_comparison(corrected_data, plot_type="nyquist", max_trusted_freq=MAX_FREQ)
        fig2c.suptitle("Nyquist (corrected) — " + path.name)
        save_fig(fig2c, "nyquist_combined_corrected", graphs_dir)
        plt.show()
        
        # Individual corrected Nyquist plots with parameter annotations
        for name, df in corrected_data.items():
            if df.empty:
                continue
            try:
                fig_n, ax_n = plt.subplots(figsize=(7, 7))
                ax_n, _ = plot_nyquist(df, ax=ax_n, label=name, max_trusted_freq=MAX_FREQ, extract_params=True)
                ax_n.set_title(f"Nyquist (corrected) — {name}")
                fig_n.suptitle(f"Nyquist (corrected) — {name}")
                if graphs_dir:
                    safe_name = name.replace(" ", "_")
                    fig_n.savefig(graphs_dir / f"nyquist_{safe_name}_corrected.png", dpi=150, bbox_inches="tight")
                    print("Saved", graphs_dir / f"nyquist_{safe_name}_corrected.png")
                plt.close(fig_n)
            except (KeyError, Exception) as e:
                print(f"Warning: Failed to plot Nyquist for {name} (corrected): {e}")

        fig3c = plot_folder_comparison(corrected_data, plot_type="phase", max_trusted_freq=MAX_FREQ)
        fig3c.suptitle("Phase vs f (corrected) — " + path.name)
        save_fig(fig3c, "phase_corrected", graphs_dir)
        plt.show()

        fig4c = plot_folder_comparison(corrected_data, plot_type="capacitance", max_trusted_freq=MAX_FREQ)
        fig4c.suptitle("Capacitance vs f (corrected) — " + path.name)
        save_fig(fig4c, "capacitance_corrected", graphs_dir)
        plt.show()

        fig_to_show = None
        for name, df in corrected_data.items():
            if df.empty:
                continue
            try:
                fig = plot_all(df, title=name + " (corrected)", label=name, show=False, max_trusted_freq=MAX_FREQ)
                if graphs_dir:
                    safe_name = name.replace(" ", "_")
                    fig.savefig(graphs_dir / f"{safe_name}_full_2x2_corrected.png", dpi=150, bbox_inches="tight")
                    print("Saved", graphs_dir / f"{safe_name}_full_2x2_corrected.png")
                if fig_to_show is not None:
                    plt.close(fig)
                else:
                    fig_to_show = fig
            except (KeyError, Exception):
                pass
        if fig_to_show is not None:
            plt.show()
    else:
        # No calibration: copy uncorrected to main graphs/ and origin_data/ for backward compatibility
        for name in list(device_data.keys()):
            if origin_dir:
                export_origin_csv(device_data[name], origin_dir / f"{name}_origin.csv")
        if origin_dir:
            print("Saved Origin CSVs (uncorrected) to", origin_dir)
        fig1b = plot_folder_comparison(device_data, plot_type="magnitude", max_trusted_freq=MAX_FREQ)
        fig1b.suptitle("|Z| vs f — " + path.name)
        save_fig(fig1b, "magnitude", graphs_dir)
        plt.show()
        fig2b = plot_folder_comparison(device_data, plot_type="nyquist", max_trusted_freq=MAX_FREQ)
        fig2b.suptitle("Nyquist — " + path.name)
        save_fig(fig2b, "nyquist_combined", graphs_dir)
        plt.show()
        fig3b = plot_folder_comparison(device_data, plot_type="phase", max_trusted_freq=MAX_FREQ)
        fig3b.suptitle("Phase vs f — " + path.name)
        save_fig(fig3b, "phase", graphs_dir)
        plt.show()
        fig4b = plot_folder_comparison(device_data, plot_type="capacitance", max_trusted_freq=MAX_FREQ)
        fig4b.suptitle("Capacitance vs f — " + path.name)
        save_fig(fig4b, "capacitance", graphs_dir)
        plt.show()
        fig_to_show = None
        for name, df in device_data.items():
            if df.empty:
                continue
            try:
                fig = plot_all(df, title=name, label=name, show=False, max_trusted_freq=MAX_FREQ)
                if graphs_dir:
                    safe_name = name.replace(" ", "_")
                    fig.savefig(graphs_dir / f"{safe_name}_full_2x2.png", dpi=150, bbox_inches="tight")
                    print("Saved", graphs_dir / f"{safe_name}_full_2x2.png")
                if fig_to_show is not None:
                    plt.close(fig)
                else:
                    fig_to_show = fig
            except (KeyError, Exception):
                pass
        if fig_to_show is not None:
            plt.show()


if __name__ == "__main__":
    try:
        main()
        print("\n" + "="*60)
        print("Plotting complete! Check the graphs/ folder for saved plots.")
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
