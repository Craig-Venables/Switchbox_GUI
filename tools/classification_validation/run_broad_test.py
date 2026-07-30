"""
Broad classification test across 10 new diverse devices from different material systems:
  - PMMA memristors (new samples D93, D106 Gold-bottom, D108, D109)
  - ZnS thin films (Daniel Whitt group - 120W and 60W sputtered)
  - GeO material (dans data - 0P79_Oxygen_GeO)
  - WS2 quantum dots (Quantum Dots folder)
  - Organic semiconductors (Stock folder - F8TBT, pure PMMA control)

Usage:  python tools/classification_validation/run_broad_test.py
"""
import re
import sys
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from analysis import quick_analyze
from analysis.core.sweep_analyzer import read_data_file

# ── Data paths ──────────────────────────────────────────────────────────────
DATA   = Path(r"C:\Users\ppxcv1\OneDrive - The University of Nottingham\Documents\Data_folder")
ALLDATA = Path(r"C:\Users\ppxcv1\OneDrive - The University of Nottingham\Documents\Phd\2) Data\All_data_collated")
DANS   = ALLDATA / "dans data"
QD     = ALLDATA / "Quantum Dots"
STOCK  = ALLDATA / "Stock"

EXCLUDE = {"log", "analysis", "stats", "tsp", "pulse", "endurance",
           "freqresp", "summary", "classification"}

# ── Devices to test ─────────────────────────────────────────────────────────
# Each entry: (label, source, extra_info)
#   source = Path to folder  OR  (flat_dir: Path, prefix: str)
DEVICES = [
    # ── New PMMA-based devices from Data_folder ──────────────────────────────
    (
        "D93-A-1  (0.1mgml ITO-PMMA2%-Gold, 20 sweeps — new sample)",
        DATA / "D93-0.1mgml-ITO-PMMA(2%)-Gold-s1/A/1",
    ),
    (
        "D106-A-5  (0.1mgml GOLD-PMMA2%-Gold — GOLD bottom electrode!)",
        DATA / "D106-0.1mgml-Gold-PMMA 2.0(2%)-Gold-s1/A/5",
    ),
    (
        "D106-B-3  (0.1mgml Gold-PMMA2%-Gold, section B — different area)",
        DATA / "D106-0.1mgml-Gold-PMMA 2.0(2%)-Gold-s1/B/3",
    ),
    (
        "D108-A-3  (0.1mgml ITO-PMMA2%-Gold-s5, 47 sweeps — heavily swept)",
        DATA / "D108-0.1mgml-ITO-PMMA 2.0(2%)-Gold-s5/A/3",
    ),
    (
        "D109-A-4  (0.1mgml ITO-PMMA2%-Gold-s6 — new chip)",
        DATA / "D109-0.1mgml-ITO-PMMA 2.0(2%)-Gold-s6/A/4",
    ),
    # ── ZnS thin films (Daniel Whitt / dans data — different material) ───────
    (
        "ZnS_50nm_120W_Feb2026-A-1  (ITO-ZnS-Gold thin film, 120W sputter)",
        (DANS, "120W_ZnS_50nm_TF_02_02_2026-A-1-"),
    ),
    (
        "ZnS_50nm_60W_Feb2026-A-1   (ITO-ZnS-Gold thin film, 60W sputter)",
        (DANS, "60W_ZnS_50nm_TF_02_02_2026-A-1-"),
    ),
    # ── GeO material (dans data) ─────────────────────────────────────────────
    (
        "0P79_Oxygen_GeO-B-8  (GeO device, 10 sweeps 0.3->5.0V)",
        (DANS, "0P79_Oxygen_GeO-B-8-"),
    ),
    # ── WS2 quantum dots ─────────────────────────────────────────────────────
    (
        "WS2-D15-G-1  (WS2 quantum dot PMMA device, 11 sweeps)",
        (QD, "WS2-D15-G-1-"),
    ),
    # ── Organic semiconductors / controls ────────────────────────────────────
    (
        "F8TBT-D29-G-1  (organic semiconductor F8TBT, 14 sweeps)",
        (STOCK, "F8TBT-D29-G-1-"),
    ),
    (
        "PMMA-D17-G-1   (pure PMMA control device — expect non-conductive)",
        (STOCK, "PMMA-D17-G-1-"),
    ),
]


# ── Helpers ──────────────────────────────────────────────────────────────────
def make_sort_key(prefix: str = ""):
    """Return a sort function that extracts the integer sweep index.
    For flat-folder files with a long device prefix, strip the prefix first."""
    def key(f: Path):
        name = f.name
        if prefix and name.startswith(prefix):
            name = name[len(prefix):]
        m = re.match(r'^(\d+)', name)
        return int(m.group(1)) if m else 9999
    return key


def classify_file(path: Path):
    r = read_data_file(str(path))
    if r is None or len(r) < 2:
        return None
    v, i = r[0], r[1]
    t = r[2] if len(r) > 2 else None
    a = quick_analyze(v, i, time=t, analysis_level="classification", device_name=path.stem)
    clf = a.get("classification", {}) or {}
    bd  = clf.get("breakdown") or {}
    feats = clf.get("features") or {}
    mem_score = clf.get("memristivity_score")
    p95 = float(np.percentile(np.abs(i), 95))
    active = {k: round(v2, 1) for k, v2 in bd.items()
              if isinstance(v2, (int, float)) and v2 not in (0, -999)}
    rect_char = feats.get("rectifying_character", False)
    return {
        "type":       clf.get("device_type", "?"),
        "conf":       round((clf.get("confidence") or 0) * 100, 1),
        "mem_score":  round(mem_score, 1) if mem_score is not None else None,
        "forming":    clf.get("forming_stage", ""),
        "scores":     active,
        "hyst":       feats.get("has_hysteresis"),
        "pinch":      feats.get("pinched_hysteresis"),
        "switch":     feats.get("switching_behavior"),
        "nonlin":     feats.get("nonlinear_iv"),
        "phase":      round(feats.get("phase_shift", 0), 1),
        "polarity":   feats.get("polarity_dependent"),
        "comply":     feats.get("compliance_limited", False),
        "rect_char":  rect_char,
        "p95_na":     round(p95 * 1e9, 2),
        "warnings":   [w.encode("ascii", errors="replace").decode("ascii")
                       for w in clf.get("warnings", [])],
    }


def get_files(source):
    """Return sorted list of sweep .txt files from either a folder or (flat_dir, prefix)."""
    if isinstance(source, tuple):
        flat_dir, prefix = source
        files = sorted(
            [f for f in flat_dir.glob("*.txt")
             if f.name.startswith(prefix)
             and not any(ex in f.name.lower() for ex in EXCLUDE)],
            key=make_sort_key(prefix),
        )
    else:
        # device folder
        files = sorted(
            [f for f in source.glob("*.txt")
             if not any(ex in f.name.lower() for ex in EXCLUDE)],
            key=make_sort_key(),
        )
    return files


SEP = "=" * 95
STAGE_ICON = {
    "unformed":           "[ ]",
    "precursor_rectifying":"[~]",
    "forming_memristive": "[/]",
    "forming_event":      "[F]",
    "weak_memristive":    "[w]",
    "formed_memristive":  "[*]",
    "formed_rectifying":  "[R]",
    "lrs_cycling":        "[L]",
    "":                   "[ ]",
}
TYPE_SHORT = {
    "non_conductive": "NC ",
    "memristive":     "MEM",
    "ohmic":          "OHM",
    "conductive":     "CON",
    "capacitive":     "CAP",
    "uncertain":      "UNC",
}


def run():
    print(f"\n{SEP}")
    print("  BROAD MULTI-MATERIAL TRAJECTORY TEST")
    print(SEP)

    type_totals: dict[str, int] = {}
    all_issues = []
    total_sweeps = 0
    devices_run = 0

    for label, source in DEVICES:
        # Resolve files
        files = get_files(source)
        if not files:
            src_str = str(source[0]) + "/" + source[1] if isinstance(source, tuple) else str(source)
            print(f"\n  [{label}] — no files found at {src_str}, skipping")
            continue

        print(f"\n  [{label}]  ({len(files)} sweeps)")
        print(f"  {'Sweep':<48} {'T':>3} {'Conf':>5} {'Mem':>5} {'I_p95':>9}  {'Stage':<22}  Feats")
        print(f"  {'-'*48} {'-'*3} {'-'*5} {'-'*5} {'-'*9}  {'-'*22}  -----")

        stage_seq = []
        issues = []
        prev_type = None
        devices_run += 1

        for f in files:
            try:
                r = classify_file(f)
            except Exception as e:
                print(f"  {f.name[:48]:<48} ERROR: {e}")
                continue
            if r is None:
                continue

            total_sweeps += 1
            dt = r["type"]
            type_totals[dt] = type_totals.get(dt, 0) + 1

            t_short   = TYPE_SHORT.get(dt, dt[:3].upper())
            rect_tag  = "*" if r["rect_char"] else " "  # flag rectifying-character sweeps
            stage_icon = STAGE_ICON.get(r["forming"], "[ ]")
            stage_seq.append(r["forming"])

            p95_str   = f"{r['p95_na']:.1f}nA" if r["p95_na"] < 1000 else f"{r['p95_na']/1000:.1f}µA"
            mem_str   = str(r["mem_score"]) if r["mem_score"] is not None else ""

            feat_str = (
                ("H" if r["hyst"]    else ".") +
                ("P" if r["pinch"]   else ".") +
                ("S" if r["switch"]  else ".") +
                ("N" if r["nonlin"]  else ".") +
                ("C" if r["comply"]  else ".")
            )
            warn_flag = " W" if r["warnings"] else "  "

            print(f"  {f.name[:48]:<48} {t_short}{rect_tag} {r['conf']:>4}% {mem_str:>5} {p95_str:>9}"
                  f"  {stage_icon} {r['forming'][:18]:<18}  {feat_str}{warn_flag}")

            if prev_type in ("memristive",) and dt == "non_conductive":
                msg = f"REGRESSION: {f.name} — was memristive, now non_conductive"
                issues.append(msg)
                print(f"  !!! {msg}")

            prev_type = dt

        unique_stages = list(dict.fromkeys(s for s in stage_seq if s))
        print(f"\n  Forming trajectory: {' -> '.join(unique_stages) if unique_stages else 'none detected'}")

        if issues:
            all_issues.extend(issues)

    # ─── Global summary ────────────────────────────────────────────────────
    print(f"\n{SEP}")
    print("  GLOBAL SUMMARY")
    print(SEP)
    print(f"  Devices tested : {devices_run}")
    print(f"  Total sweeps   : {total_sweeps}")
    print()
    print("  Classification distribution:")
    for t, n in sorted(type_totals.items(), key=lambda x: -x[1]):
        bar = "#" * (n // 2)
        print(f"    {t:<18} {n:>4}  {bar}")
    print()
    if all_issues:
        print("  Issues:")
        for iss in all_issues:
            print(f"    {iss}")
    else:
        print("  No regressions or critical issues.")

    print(f"\n{SEP}")
    print("  LEGEND")
    print(SEP)
    print("""
  T column: MEM=memristive  NC=non_conductive  OHM=ohmic  CON=conductive
            CAP=capacitive  UNC=uncertain
  * after T: rectifying character detected (memristive sub-type, polarity-dependent)
  Feats:  H=has_hysteresis  P=pinched_hysteresis  S=switching  N=nonlinear  C=compliance_limited
  Stage:  [ ]=unformed  [~]=precursor_rectifying  [/]=forming_memristive  [w]=weak_memristive
          [*]=formed_memristive  [R]=formed_rectifying  [F]=forming_event  [L]=lrs_cycling
  W  = classifier emitted a warning or info note
  """)
    print(SEP)


if __name__ == "__main__":
    run()
