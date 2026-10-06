"""Entry point: python -m tools.first_sweep"""

import sys
from pathlib import Path

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from tools.first_sweep import run_gui


def main():
    sys.exit(run_gui())


if __name__ == "__main__":
    main()
