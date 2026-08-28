"""
CLI for auxiliary pulse + Solartron analysis.

Usage:
  python -m analysis.aux.cli --sample "C:\\path\\to\\D114"
  python -m analysis.aux.cli --sample "C:\\path\\to\\D114" --kinds pulse
  python -m analysis.aux.cli --pulse-folder "C:\\path\\to\\...\\Pulse_measurements"
  python -m analysis.aux.cli --solartron-folder "C:\\path\\to\\...\\Solartron_1260"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze Pulse_measurements and Solartron_1260 data")
    parser.add_argument("--sample", type=str, help="Sample root directory")
    parser.add_argument(
        "--kinds",
        type=str,
        default="pulse,solartron",
        help="Comma-separated: pulse,solartron",
    )
    parser.add_argument("--pulse-folder", type=str, help="Single Pulse_measurements folder")
    parser.add_argument("--solartron-folder", type=str, help="Single Solartron_1260 folder")
    parser.add_argument("--no-save", action="store_true", help="Do not write analysis files")
    parser.add_argument("--json-out", type=str, help="Optional path to write full JSON result")
    args = parser.parse_args(argv)

    save = not args.no_save

    def _log(msg: str) -> None:
        print(msg)

    if args.pulse_folder:
        from .api import analyze_pulse_folder

        result = analyze_pulse_folder(args.pulse_folder, save=save)
        print(result.get("brief") or json.dumps(result, indent=2, default=str)[:2000])
        if args.json_out:
            Path(args.json_out).write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        return 0

    if args.solartron_folder:
        from .solartron.analyzer import SolartronDeviceAnalyzer

        result = SolartronDeviceAnalyzer(args.solartron_folder).analyze(save=save)
        print(result.get("brief") or "")
        if args.json_out:
            Path(args.json_out).write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        return 0

    if not args.sample:
        parser.error("Provide --sample, --pulse-folder, or --solartron-folder")

    from .api import analyze_sample_aux

    kinds = [k.strip() for k in args.kinds.split(",") if k.strip()]
    result = analyze_sample_aux(args.sample, kinds=kinds, save=save, log=_log)
    print(result.get("brief") or "")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
