"""Launch classification review GUI for consolidated data."""
import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from paths import DATASETS, DEFAULT_DATASET
from review_classifications import main as review_main
from flash_review import main as flash_main

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=list(DATASETS.keys()), default=DEFAULT_DATASET)
    parser.add_argument(
        "--flash",
        action="store_true",
        help="Fast Y/N flash review mode (keyboard: Y/N/S)",
    )
    args = parser.parse_args()
    if args.flash:
        flash_main(dataset=args.dataset)
    else:
        review_main(dataset=args.dataset)