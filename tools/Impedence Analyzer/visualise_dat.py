"""
Quick visualisation for SMaRT .dat (binary) impedance files.

Usage:
  python visualise_dat.py [path]
  python visualise_dat.py "C:\...\Impedance Analyzer"

Path can be a single .dat file or a folder (all .dat files inside are plotted).
Set DATA_PATH below for a default, or pass as first argument.

Options:
  MAX_FREQ = 1e6  — remove data above this frequency (noise); set to None to keep all.
  SAVE_GRAPHS = True  — save figures into <path>/graphs/
  SAVE_ORIGIN = True  — export Origin-ready CSVs into <path>/origin_data/
"""

from pathlib import Path
import sys

# Default: set to your .dat file or folder, or leave None and pass as argument
DATA_PATH = None  # e.g. Path(r"C:\...\1_onstate_10pt_decade.dat") or Path(r"C:\...\Impedance Analyzer")

# Remove data above this frequency (Hz); system noise above 1e6. Set None to keep all.
MAX_FREQ = 1e6

# Save figures and Origin CSVs under the given path
SAVE_GRAPHS = True
SAVE_ORIGIN = True


def main():
    try:
        from dat_loader import load_smart_dat
        from impedance_plots import plot_magnitude_vs_frequency
        from origin_export import filter_by_max_frequency, export_origin_csv
    except ImportError:
        from dat_loader import load_smart_dat
        from impedance_plots import plot_magnitude_vs_frequency
        from origin_export import filter_by_max_frequency, export_origin_csv

    import matplotlib.pyplot as plt

    path = DATA_PATH
    if path is None and len(sys.argv) > 1:
        path = Path(sys.argv[1])
    if path is None:
        print("Set DATA_PATH in this script or run: python visualise_dat.py <file_or_folder>")
        return

    path = Path(path)
    if not path.exists():
        print("Path not found:", path)
        return

    output_dir = path if path.is_dir() else path.parent
    graphs_dir = output_dir / "graphs" if SAVE_GRAPHS else None
    origin_dir = output_dir / "origin_data" if SAVE_ORIGIN else None
    if graphs_dir:
        graphs_dir.mkdir(parents=True, exist_ok=True)
    if origin_dir:
        origin_dir.mkdir(parents=True, exist_ok=True)

    def apply_filter(df):
        if MAX_FREQ is not None:
            return filter_by_max_frequency(df, max_freq=MAX_FREQ)
        return df

    data = {}
    if path.is_file():
        if path.suffix.lower() != ".dat":
            print("Not a .dat file:", path)
            return
        try:
            df = load_smart_dat(path)
        except Exception as e:
            print("Failed to load", path.name, ":", e)
            return
        data[path.stem] = apply_filter(df)
    else:
        for f in sorted(path.glob("*.dat")):
            try:
                df = load_smart_dat(f)
                data[f.stem] = apply_filter(df)
            except Exception as e:
                print("Skip", f.name, ":", e)

    if not data:
        print("No .dat data to plot.")
        return

    for name in list(data.keys()):
        if origin_dir:
            export_origin_csv(data[name], origin_dir / f"{name}_origin.csv")
    if origin_dir:
        print("Saved Origin CSVs to", origin_dir)

    print("Plotting:", list(data.keys()), f"{'(filtered to f <= {MAX_FREQ} Hz)' if MAX_FREQ else ''}")

    fig, ax = plt.subplots(figsize=(8, 5))
    for name, df in data.items():
        if df.empty:
            continue
        plot_magnitude_vs_frequency(df, ax=ax, label=name)
    ax.legend()
    fig.suptitle("Impedance magnitude (from .dat)" + (f" — {path.name}" if path.is_dir() else ""))
    plt.tight_layout()
    if graphs_dir:
        fig.savefig(graphs_dir / "magnitude.png", dpi=150, bbox_inches="tight")
        print("Saved", graphs_dir / "magnitude.png")
    plt.show()


if __name__ == "__main__":
    main()
