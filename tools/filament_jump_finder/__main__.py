"""Entry point: python -m tools.filament_jump_finder [--sample /path]"""

import argparse
import sys
from pathlib import Path

# Ensure project root is on path when run as __main__
if __name__ == '__main__':
    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from tools.filament_jump_finder import run_gui


def main():
    parser = argparse.ArgumentParser(description="Filament Jump Finder — detect large current jumps in IV data.")
    parser.add_argument('--sample', '-s', type=str, default=None, help="Sample folder to load on startup")
    args = parser.parse_args()
    sys.exit(run_gui(args.sample))


if __name__ == '__main__':
    main()
