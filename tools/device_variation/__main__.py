"""Entry point: python -m tools.device_variation [--session file.json]"""

import argparse
import sys
from pathlib import Path

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from tools.device_variation import run_gui


def main():
    parser = argparse.ArgumentParser(
        description="Compare pre- and post-forming IV curves across devices and samples.",
    )
    parser.add_argument(
        "--session",
        "-s",
        type=str,
        default=None,
        help="Filament jump finder session JSON to open on startup",
    )
    args = parser.parse_args()
    sys.exit(run_gui(args.session))


if __name__ == "__main__":
    main()
