"""Entry point: python -m tools.loop_trend"""

import sys
from pathlib import Path

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from tools.loop_trend import run_gui


def main():
    sys.exit(run_gui())


if __name__ == "__main__":
    main()
