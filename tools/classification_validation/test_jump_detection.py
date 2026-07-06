"""
Test the new _detect_current_jump feature on:
  - D80 3.5V sweep : the actual forming event — SHOULD detect
  - D80 3.0V sweep : partial forming — may detect
  - D80 post-forming cycling : should NOT detect
  - D94 unformed   : should NOT detect
  - D81 never-formed: should NOT detect

Usage: python tools/classification_validation/test_jump_detection.py
"""
import sys
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from analysis import quick_analyze
from analysis.core.sweep_analyzer import read_data_file

DATA = Path(r"C:\Users\ppxcv1\OneDrive - The University of Nottingham\Documents\Data_folder")

TESTS = [
    ("D80-0.1mgml-ITO-PMMA(2%)-Gold-s2/A/1/0-FS-3.5v-0.05sv-0.05sd-Py-1.0.txt",
     True,  "D80 3.5V forming sweep — SHOULD detect large jump"),
    ("D80-0.1mgml-ITO-PMMA(2%)-Gold-s2/A/1/0-FS-3.0v-0.05sv-0.05sd-Py-3.0.txt",
     None,  "D80 3.0V early forming — may or may not detect"),
    ("D80-0.1mgml-ITO-PMMA(2%)-Gold-s2/A/1/6-FS-2.5v-0.05sv-0.05sd-Py-St_v2_led-3.txt",
     False, "D80 post-forming cycling at 2.5V — should NOT detect"),
    ("D80-0.1mgml-ITO-PMMA(2%)-Gold-s2/A/1/22-FS-2.8v-0.05sv-0.05sd-Py-St_v2_led-5.txt",
     False, "D80 late cycling sweep — should NOT detect"),
    ("D94-0.1mgml-ITO-PMMA(2%)-Gold-s2/A/1/7-FS-2.8v-0.05sv-0.05sd-Py-St_v2_led-5.txt",
     False, "D94 unformed device at 2.8V — should NOT detect"),
    ("D81-0.07mgml-ITO-PMMA(3%)-Gold-s3/H/4/10-FS-2.8v-0.05sv-0.05sd-Py-St_v1-5.txt",
     False, "D81 never-formed batch — should NOT detect"),
]


def run():
    SEP = "=" * 90
    print(f"\n{SEP}")
    print("  CURRENT JUMP DETECTION TEST")
    print(SEP)
    print(f"  {'File':<52} {'Jump?':>6} {'Ratio':>9} {'V_onset':>8}  {'Stage':<22} {'Expect'}")
    print(f"  {'-'*52} {'-'*6} {'-'*9} {'-'*8}  {'-'*22} {'-'*9}")

    passes = 0
    total_labelled = 0

    for rel, expected, note in TESTS:
        f = DATA / rel
        if not f.exists():
            print(f"  {f.name[:52]:<52} FILE NOT FOUND — skipping")
            continue

        r = read_data_file(str(f))
        v, i = r[0], r[1]
        a = quick_analyze(v, i, analysis_level="classification", device_name=f.stem)
        clf = a.get("classification", {}) or {}
        feats = clf.get("features") or {}

        jump    = feats.get("current_jump_detected", False)
        ratio   = feats.get("current_jump_ratio", 1.0)
        v_onset = feats.get("forming_voltage_onset")
        stage   = clf.get("forming_stage") or feats.get("forming_stage", "")
        dt      = clf.get("device_type", "?")
        conf    = round((clf.get("confidence") or 0) * 100, 1)

        v_str    = f"{v_onset:.2f}V" if v_onset is not None else "  --  "
        flag_str = "YES ***" if jump else "no     "

        if expected is not None:
            total_labelled += 1
            ok = (jump == expected)
            if ok:
                passes += 1
            match_str = "OK" if ok else "FAIL"
        else:
            match_str = "(unknown)"

        print(f"  {f.name[:52]:<52} {flag_str} {ratio:>9.0f} {v_str:>8}  {str(stage):<22} {match_str}")
        print(f"    -> {dt} conf={conf}%   | {note}")
        print()

    print(SEP)
    print(f"  Labelled checks: {passes}/{total_labelled} passed")
    print(SEP)
    print()


if __name__ == "__main__":
    run()
