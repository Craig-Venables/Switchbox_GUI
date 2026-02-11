"""
Analyze a saved optical pulse-test result to home in on timing and pulse width.

Loads a Pulse Testing .txt file (or CSV with timestamps/resistances), detects
resistance drops (photodiode response), and reports:
  - First pulse time (s)
  - Suggested laser_sync_offset_s for a desired first-pulse time
  - Observed pulse width(s) from each drop

Usage:
  python analyze_optical_result.py path/to/result.txt
  python analyze_optical_result.py path/to/result.txt --desired 1.0
  python analyze_optical_result.py path/to/result.txt --desired 1.0 --baseline-fraction 0.15

Run from repo root or from this directory (script adds repo root to path).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Repo root (parent of tools/)
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def load_tsp_txt(filepath: Path) -> tuple[list[float], list[float]]:
    """Load timestamps and resistances from a TSP pulse-test .txt (tab-delimited, # header)."""
    timestamps: list[float] = []
    resistances: list[float] = []
    header_line = None
    ts_col = None
    r_col = None

    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip()
            if not line or line.startswith("#"):
                continue
            # First non-comment line is usually the column header
            if header_line is None:
                header_line = line
                parts = [p.strip() for p in line.split("\t")]
                for i, p in enumerate(parts):
                    if "timestamp" in p.lower() or p.lower() == "timestamp(s)":
                        ts_col = i
                    if "resistance" in p.lower() or "ohm" in p.lower():
                        r_col = i
                if ts_col is None or r_col is None:
                    # Try comma
                    parts = [p.strip() for p in line.split(",")]
                    for i, p in enumerate(parts):
                        if "timestamp" in p.lower():
                            ts_col = i
                        if "resistance" in p.lower() or "ohm" in p.lower():
                            r_col = i
                continue
            parts = line.split("\t") if "\t" in line else line.split(",")
            if ts_col is not None and r_col is not None and len(parts) > max(ts_col, r_col):
                try:
                    t = float(parts[ts_col])
                    r = float(parts[r_col])
                    timestamps.append(t)
                    resistances.append(r)
                except (ValueError, IndexError):
                    continue
    return timestamps, resistances


def suggest_sync_offset(
    timestamps: list[float],
    resistances: list[float],
    desired_first_pulse_s: float,
    baseline_fraction: float = 0.1,
    min_samples_baseline: int = 10,
) -> float | None:
    """Suggest laser_sync_offset_s so first pulse appears at desired_first_pulse_s."""
    if not timestamps or not resistances or len(timestamps) != len(resistances):
        return None
    if len(resistances) < min_samples_baseline:
        return None
    valid_baseline = [r for r in resistances[:min_samples_baseline] if r and abs(r) < 1e15]
    if not valid_baseline:
        return None
    baseline = sorted(valid_baseline)[len(valid_baseline) // 2]
    threshold = baseline * baseline_fraction
    for t, r in zip(timestamps, resistances):
        if not r or abs(r) >= 1e15:
            continue
        if (baseline - r) > threshold:  # resistance drop (photodiode response)
            return desired_first_pulse_s - t
    return None


def estimate_pulse_widths(
    timestamps: list[float],
    resistances: list[float],
    baseline_fraction: float = 0.1,
    min_baseline_samples: int = 10,
) -> list[tuple[float, float, float]]:
    """Return list of (t_start, t_end, width_s) for each resistance drop."""
    if len(timestamps) < min_baseline_samples or len(timestamps) != len(resistances):
        return []
    valid = [r for r in resistances[:min_baseline_samples] if r and abs(r) < 1e15]
    if not valid:
        return []
    baseline = sorted(valid)[len(valid) // 2]
    threshold = baseline * baseline_fraction
    in_drop = False
    t_start = 0.0
    out = []
    for t, r in zip(timestamps, resistances):
        if not r or abs(r) >= 1e15:
            continue
        below = (baseline - r) > threshold
        if below and not in_drop:
            in_drop = True
            t_start = t
        elif not below and in_drop:
            in_drop = False
            out.append((t_start, t, t - t_start))
    if in_drop and timestamps:
        out.append((t_start, timestamps[-1], timestamps[-1] - t_start))
    return out


def find_first_pulse_time(
    timestamps: list[float],
    resistances: list[float],
    baseline_fraction: float = 0.1,
    min_samples_baseline: int = 10,
) -> float | None:
    """Time (s) of first significant resistance drop."""
    if len(resistances) < min_samples_baseline:
        return None
    valid = [r for r in resistances[:min_samples_baseline] if r and abs(r) < 1e15]
    if not valid:
        return None
    baseline = sorted(valid)[len(valid) // 2]
    threshold = baseline * baseline_fraction
    for t, r in zip(timestamps, resistances):
        if not r or abs(r) >= 1e15:
            continue
        if (baseline - r) > threshold:  # resistance drop
            return t
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze optical pulse-test result for timing and pulse width."
    )
    parser.add_argument(
        "file",
        type=Path,
        help="Path to saved .txt (or CSV) with Timestamp(s) and Resistance(Ohm) columns",
    )
    parser.add_argument(
        "--desired",
        type=float,
        default=1.0,
        help="Desired time (s) for first pulse on plot (default 1.0)",
    )
    parser.add_argument(
        "--baseline-fraction",
        type=float,
        default=0.1,
        help="Fraction of baseline for drop detection (default 0.1)",
    )
    parser.add_argument(
        "--min-baseline",
        type=int,
        default=10,
        help="Min samples for baseline (default 10)",
    )
    args = parser.parse_args()

    path = args.file
    if not path.exists():
        print(f"Error: file not found: {path}")
        return 1

    ts, R = load_tsp_txt(path)
    if not ts or not R:
        print("Error: could not load timestamps/resistances from file.")
        return 1

    print(f"Loaded {len(ts)} points from {path.name}")
    print(f"  Time range: {ts[0]:.3f} s to {ts[-1]:.3f} s")
    print()

    first_t = find_first_pulse_time(
        ts, R,
        baseline_fraction=args.baseline_fraction,
        min_samples_baseline=args.min_baseline,
    )
    if first_t is None:
        print("No resistance drop detected. Check baseline_fraction or data.")
        return 0
    print(f"First pulse (from resistance drop): {first_t:.3f} s")
    print()

    suggested = suggest_sync_offset(
        ts, R, args.desired,
        baseline_fraction=args.baseline_fraction,
        min_samples_baseline=args.min_baseline,
    )
    if suggested is not None:
        print(f"To have the first pulse at {args.desired} s on the plot:")
        print(f"  Suggested 'Laser sync offset (s)' = {suggested:.3f}")
        print()
    else:
        print("Could not suggest sync offset (no drop detected).")
        print()

    pulses = estimate_pulse_widths(
        ts, R,
        baseline_fraction=args.baseline_fraction,
        min_baseline_samples=args.min_baseline,
    )
    if pulses:
        print("Observed pulse width(s) from resistance drops:")
        for i, (t_start, t_end, w) in enumerate(pulses):
            print(f"  Pulse {i+1}: start={t_start:.3f} s, end={t_end:.3f} s, width={w*1000:.1f} ms")
    else:
        print("No pulse widths estimated.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
