"""
CLI wrapper: rebuild Origin compare CSVs + overlay plots for a folder of
Solartron runs (any folder containing origin_data/*.csv trees).

The Solartron GUI also does this automatically after every save under
  .../<Sample>/<Section>/<Device>/Solartron_1260/

Usage:
  python combine_bias_origin_csvs.py
  python combine_bias_origin_csvs.py "D:\\path\\to\\Solartron_1260"
  python combine_bias_origin_csvs.py "D:\\path\\to\\solertron"
"""

from __future__ import annotations

import sys
from pathlib import Path

_TOOL_DIR = Path(__file__).resolve().parents[1]
if str(_TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOL_DIR))

from auto_compare import refresh_device_compare  # noqa: E402

DEFAULT_DATA_DIR = Path(
    r"C:\Users\ppxcv1\OneDrive - The University of Nottingham"
    r"\Documents\Data_folder\D114\B\1\solertron"
)


def main() -> None:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DATA_DIR
    out = refresh_device_compare(root, quiet=False)
    if out is None:
        raise SystemExit(f"No origin_data CSVs found under:\n  {root}")
    print(
        "\nOrigin tips:\n"
        "  Easiest any-combo: open all_datasets_long.csv, filter/group by Dataset\n"
        "  C vs f / Bode / Z' vs f / -Z'' vs f: Y columns vs Frequency_Hz\n"
        "  Nyquist: -Z_Imag_<name> vs Z_Real_<name> (matching pair; already -Im(Z))\n"
        "\nEIS Spectrum Analyser (eissa1.exe):\n"
        f"  Open any .txt in: {root / 'eis_analyser'}\n"
        "  File → Open data file"
    )


if __name__ == "__main__":
    main()
