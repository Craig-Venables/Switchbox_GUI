"""Launch fast flash review (Y/N keyboard shortcuts)."""
import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from paths import DATASETS, DEFAULT_DATASET
from flash_review import main

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=list(DATASETS.keys()), default=DEFAULT_DATASET)
    args = parser.parse_args()
    main(dataset=args.dataset)
