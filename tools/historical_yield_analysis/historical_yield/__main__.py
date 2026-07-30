"""python -m historical_yield"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _ensure_path() -> None:
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def main(argv: list[str] | None = None) -> int:
    _ensure_path()
    from historical_yield.config import load_config
    from historical_yield.import_pipeline import scan_and_update_cache
    from historical_yield.report import generate_report

    parser = argparse.ArgumentParser(description="Historical Device Yield Analysis")
    parser.add_argument("--config", type=str, default=None, help="Path to config.json")
    sub = parser.add_subparsers(dest="command")

    p_scan = sub.add_parser("scan", help="Discover workbooks and update cache")
    p_scan.add_argument("--rebuild", action="store_true", help="Clear cache and re-import all")

    p_report = sub.add_parser("report", help="Generate thesis report from cache")
    p_report.add_argument("--min-sample", type=int, default=None)
    p_report.add_argument("--max-sample", type=int, default=None)
    p_report.add_argument("--polymer", type=str, default=None)

    sub.add_parser("gui", help="Launch desktop GUI")
    sub.add_parser("stats", help="Print cache statistics")

    args = parser.parse_args(argv)
    config = load_config(args.config)

    if args.command in (None, "gui"):
        from historical_yield.gui import run_app

        return run_app(config)

    if args.command == "scan":
        summary = scan_and_update_cache(config, rebuild=args.rebuild, progress=lambda m, f: print(f"[{f:.0%}] {m}"))
        print(json.dumps(summary.as_dict(), indent=2))
        return 0

    if args.command == "report":
        polymers = [args.polymer] if args.polymer else None
        result = generate_report(
            config,
            polymers=polymers,
            min_sample_number=args.min_sample,
            max_sample_number=args.max_sample,
        )
        print(f"Report: {result.output_dir}")
        return 0

    if args.command == "stats":
        from historical_yield.cache import YieldCache

        if not config.sqlite_path.exists():
            print("No cache yet.")
            return 1
        print(json.dumps(YieldCache(config.sqlite_path).stats(), indent=2))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
