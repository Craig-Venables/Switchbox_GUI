"""
Quick visualisation for SMaRT CSV impedance exports only.

Usage:
  python visualise_csv.py [path]
  python visualise_csv.py "C:\...\Impedance Analyzer"

Path can be a single .csv file or a folder (all .csv files are loaded and compared).
Set DATA_PATH below for a default, or pass as first argument.

Options:
  MAX_FREQ = 1e6  — remove data above this frequency (noise); set to None to keep all.
  SAVE_GRAPHS = True  — save figures into <path>/graphs/
  SAVE_ORIGIN = True  — export Origin-ready CSVs into <path>/origin_data/
"""

from pathlib import Path
import sys

# Default: set to your CSV file or folder, or leave None and pass as argument
DATA_PATH = Path(
    r"C:\Users\Craig-Desktop\OneDrive - The University of Nottingham\Documents\Data_folder"
    r"\D108-0.1mgml-ITO-PMMA 2.0(2%)-Gold-s5\A\3\Impedance Analyzer"
)  # or Path(r"...\1_onstate_10pt_decade.csv")

# Remove data above this frequency (Hz); system noise above 1e6. Set None to keep all.
MAX_FREQ = 1e6

# Save figures and Origin CSVs under the given path
SAVE_GRAPHS = True
SAVE_ORIGIN = True


def main():
    try:
        from smart_loader import load_smart_csv, load_impedance_folder
        from impedance_plots import plot_all, plot_folder_comparison
        from origin_export import filter_by_max_frequency, export_origin_csv
    except ImportError:
        from smart_loader import load_smart_csv, load_impedance_folder
        from impedance_plots import plot_all, plot_folder_comparison
        from origin_export import filter_by_max_frequency, export_origin_csv

    import matplotlib.pyplot as plt

    path = DATA_PATH
    if path is None and len(sys.argv) > 1:
        path = Path(sys.argv[1])
    if path is None:
        print("Set DATA_PATH in this script or run: python visualise_csv.py <file_or_folder>")
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

    def save_fig(fig, name: str):
        if graphs_dir:
            fig.savefig(graphs_dir / f"{name}.png", dpi=150, bbox_inches="tight")
            print("Saved", graphs_dir / f"{name}.png")

    if path.is_file():
        if path.suffix.lower() != ".csv":
            print("Not a .csv file:", path)
            return
        try:
            df = load_smart_csv(path)
        except Exception as e:
            print("Failed to load", path.name, ":", e)
            return
        df = apply_filter(df)
        if origin_dir:
            export_origin_csv(df, origin_dir / f"{path.stem}_origin.csv")
            print("Saved", origin_dir / f"{path.stem}_origin.csv")
        fig = plot_all(df, title=path.stem, label=path.stem, show=False)
        if graphs_dir:
            safe = path.stem.replace(" ", "_")
            fig.savefig(graphs_dir / f"full_2x2_{safe}.png", dpi=150, bbox_inches="tight")
            print("Saved", graphs_dir / f"full_2x2_{safe}.png")
        plt.show()
        return

    # Folder: load all CSVs and overlay
    try:
        data = load_impedance_folder(path)
    except Exception as e:
        print("Failed to load folder:", e)
        return

    if not data:
        print("No CSV files in folder.")
        return

    for name in list(data.keys()):
        data[name] = apply_filter(data[name])
        if origin_dir:
            export_origin_csv(data[name], origin_dir / f"{name}_origin.csv")
    if origin_dir:
        print("Saved Origin CSVs to", origin_dir)

    print("Loaded:", list(data.keys()), f"{'(filtered to f <= {MAX_FREQ} Hz)' if MAX_FREQ else ''}")

    fig1 = plot_folder_comparison(data, plot_type="magnitude")
    fig1.suptitle("|Z| vs f — " + path.name)
    save_fig(fig1, "magnitude")
    plt.show()

    # Combined Nyquist (on screen); save one Nyquist per CSV with CSV name
    fig2 = plot_folder_comparison(data, plot_type="nyquist")
    fig2.suptitle("Nyquist — " + path.name)
    save_fig(fig2, "nyquist_combined")
    plt.show()
    for name, df in data.items():
        if df.empty:
            continue
        try:
            fig_n = plot_folder_comparison({name: df}, plot_type="nyquist")
            fig_n.suptitle(f"Nyquist — {name}")
            save_fig(fig_n, f"nyquist_{name}")
            plt.close(fig_n)
        except (KeyError, Exception):
            pass

    fig3 = plot_folder_comparison(data, plot_type="phase")
    fig3.suptitle("Phase vs f — " + path.name)
    save_fig(fig3, "phase")
    plt.show()

    fig4 = plot_folder_comparison(data, plot_type="capacitance")
    fig4.suptitle("Capacitance vs f — " + path.name)
    save_fig(fig4, "capacitance")
    plt.show()

    # Save one full 2x2 per CSV (named by CSV) so we don't overwrite
    fig_to_show = None
    for name, df in data.items():
        if df.empty:
            continue
        try:
            fig = plot_all(df, title=name, label=name, show=False)
            if graphs_dir:
                safe_name = name.replace(" ", "_")
                fig.savefig(graphs_dir / f"full_2x2_{safe_name}.png", dpi=150, bbox_inches="tight")
                print("Saved", graphs_dir / f"full_2x2_{safe_name}.png")
            if fig_to_show is not None:
                plt.close(fig)
            else:
                fig_to_show = fig
        except (KeyError, Exception):
            pass
    if fig_to_show is not None:
        plt.show()


if __name__ == "__main__":
    main()
