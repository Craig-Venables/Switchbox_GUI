"""
Second broad classification test — 10 new devices, fresh random sample,
covering new D-numbers and more diverse ZnS/GeO/QD/organic conditions.

Usage:  python tools/classification_validation/run_broad_test2.py
"""
import re
import sys
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from analysis import quick_analyze
from analysis.core.sweep_analyzer import read_data_file

DATA   = Path(r"C:\Users\ppxcv1\OneDrive - The University of Nottingham\Documents\Data_folder")
ALLDATA = Path(r"C:\Users\ppxcv1\OneDrive - The University of Nottingham\Documents\Phd\2) Data\All_data_collated")
DANS   = ALLDATA / "dans data"
QD     = ALLDATA / "Quantum Dots"
STOCK  = ALLDATA / "Stock"

EXCLUDE = {"log", "analysis", "stats", "tsp", "pulse", "endurance",
           "freqresp", "summary", "classification"}

DEVICES = [
    # ── New PMMA memristors ───────────────────────────────────────────────────
    (
        "D93-A-4  (0.1mgml ITO-PMMA2%-Gold, 10 sweeps — diff device same sample)",
        DATA / "D93-0.1mgml-ITO-PMMA(2%)-Gold-s1/A/4",
    ),
    (
        "D110-F-3  (0.1mgml ITO-PMMA2%-Gold-s9, 46 sweeps — deeply cycled)",
        DATA / "D110-0.1mgml-ITO-PMMA 2.0(2%)-Gold-s9/F/3",
    ),
    (
        "D112-G-2  (Stock-ITO-PMMA2%-ITO-s10 — stock conc. + ITO-ITO symmetric)",
        DATA / "D112-Stock-ITO-PMMA 2.0(2%)-ITO-s10/G/2",
    ),
    (
        "D93-A-2  (0.1mgml ITO-PMMA2%-Gold, 12 sweeps — same sample diff number)",
        DATA / "D93-0.1mgml-ITO-PMMA(2%)-Gold-s1/A/2",
    ),
    # ── ZnS thin films — different thickness and sputtering power ────────────
    (
        "ZnS_25nm_120W_Apr2026-A-1  (thinner 25nm ZnS film, 15 sweeps)",
        (DANS, "120W_ZnS_25nm_TF_17_04_2026-A-1-"),
    ),
    (
        "ZnS_50nm_80W_Feb2026-A-2   (ZnS 50nm at 80W sputtering power)",
        (DANS, "80W_ZnS_50nm_TF_02_02_2026-A-2-"),
    ),
    (
        "ZnS_Dec2025_Device1-G-1   (earliest ZnS device, section G)",
        (DANS, "ZnS_16_12_2025_Device1-G-1-"),
    ),
    # ── GeO — different oxygen partial pressure (1.5% vs 0.79%) ─────────────
    (
        "1P5_Oxygen_GeO-C-2  (GeO with 1.5% O2 partial pressure, 11 sweeps)",
        (DANS, "1P5_Oxygen_GeO-C-2-"),
    ),
    # ── WS2 quantum dots — different device section ───────────────────────────
    (
        "WS2-D16-G-3  (WS2 QD device D16 section G device 3, 9 sweeps)",
        (QD, "WS2-D16-G-3-"),
    ),
    # ── Organic semiconductor — second F8TBT device ───────────────────────────
    (
        "F8TBT-D29-G-2  (organic F8TBT device 2, 16 sweeps)",
        (STOCK, "F8TBT-D29-G-2-"),
    ),
]


def make_sort_key(prefix: str = ""):
    def key(f: Path):
        name = f.name
        if prefix and name.startswith(prefix):
            name = name[len(prefix):]
        m = re.match(r'^(\d+)', name)
        return int(m.group(1)) if m else 9999
    return key


def get_files(source):
    if isinstance(source, tuple):
        flat_dir, prefix = source
        files = sorted(
            [f for f in flat_dir.glob("*.txt")
             if f.name.startswith(prefix)
             and not any(ex in f.name.lower() for ex in EXCLUDE)],
            key=make_sort_key(prefix),
        )
    else:
        files = sorted(
            [f for f in source.glob("*.txt")
             if not any(ex in f.name.lower() for ex in EXCLUDE)],
            key=make_sort_key(),
        )
    return files


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
    return {
        "type":      clf.get("device_type", "?"),
        "conf":      round((clf.get("confidence") or 0) * 100, 1),
        "mem_score": round(mem_score, 1) if mem_score is not None else None,
        "forming":   clf.get("forming_stage", ""),
        "scores":    active,
        "hyst":      feats.get("has_hysteresis"),
        "pinch":     feats.get("pinched_hysteresis"),
        "switch":    feats.get("switching_behavior"),
        "nonlin":    feats.get("nonlinear_iv"),
        "comply":    feats.get("compliance_limited", False),
        "rect_char": feats.get("rectifying_character", False),
        "p95_na":    round(p95 * 1e9, 2),
        "warnings":  [w.encode("ascii", errors="replace").decode("ascii")
                      for w in clf.get("warnings", [])],
    }


SEP = "=" * 95
STAGE_ICON = {
    "unformed":            "[ ]",
    "precursor_rectifying":"[~]",
    "forming_memristive":  "[/]",
    "forming_event":       "[F]",
    "weak_memristive":     "[w]",
    "formed_memristive":   "[*]",
    "formed_rectifying":   "[R]",
    "lrs_cycling":         "[L]",
    "":                    "[ ]",
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
    print("  BROAD TEST — BATCH 2")
    print(SEP)

    type_totals: dict[str, int] = {}
    all_issues = []
    total_sweeps = 0
    devices_run = 0
    device_results = []

    for label, source in DEVICES:
        files = get_files(source)
        if not files:
            src_str = str(source[0])+"/"+source[1] if isinstance(source, tuple) else str(source)
            print(f"\n  [{label}] — no files at {src_str}, skipping")
            continue

        print(f"\n  [{label}]  ({len(files)} sweeps)")
        print(f"  {'Sweep':<48} {'T':>3} {'Conf':>5} {'Mem':>5} {'I_p95':>9}  {'Stage':<22}  Feats")
        print(f"  {'-'*48} {'-'*3} {'-'*5} {'-'*5} {'-'*9}  {'-'*22}  -----")

        stage_seq, issues, per_sweep = [], [], []
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
            per_sweep.append(r)

            t_short    = TYPE_SHORT.get(dt, dt[:3].upper())
            rect_tag   = "*" if r["rect_char"] else " "
            stage_icon = STAGE_ICON.get(r["forming"], "[ ]")
            stage_seq.append(r["forming"])
            p95_str    = f"{r['p95_na']:.1f}nA" if r["p95_na"] < 1000 else f"{r['p95_na']/1000:.1f}µA"
            mem_str    = str(r["mem_score"]) if r["mem_score"] is not None else ""
            feat_str   = (("H" if r["hyst"] else ".") + ("P" if r["pinch"] else ".") +
                          ("S" if r["switch"] else ".") + ("N" if r["nonlin"] else ".") +
                          ("C" if r["comply"] else "."))
            warn_flag  = " W" if r["warnings"] else "  "

            print(f"  {f.name[:48]:<48} {t_short}{rect_tag} {r['conf']:>4}% {mem_str:>5} {p95_str:>9}"
                  f"  {stage_icon} {r['forming'][:18]:<18}  {feat_str}{warn_flag}")

            if prev_type in ("memristive",) and dt == "non_conductive":
                msg = f"REGRESSION: {f.name} — was memristive, now non_conductive"
                issues.append(msg)
                print(f"  !!! {msg}")
            prev_type = dt

        unique_stages = list(dict.fromkeys(s for s in stage_seq if s))
        traj_str = ' -> '.join(unique_stages) if unique_stages else 'none detected'
        print(f"\n  Forming trajectory: {traj_str}")

        device_results.append({"label": label, "traj": traj_str,
                                "sweeps": per_sweep, "issues": issues})
        all_issues.extend(issues)

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
  T: MEM=memristive  NC=non_conductive  OHM=ohmic  CON=conductive  CAP=capacitive  UNC=uncertain
  * : rectifying character (memristive sub-type, polarity-dependent I-V)
  Feats: H=hysteresis  P=pinched  S=switching  N=nonlinear  C=compliance_limited  W=warning
  Stage: [ ]=unformed  [~]=precursor_rect  [/]=forming_mem  [w]=weak_mem  [*]=formed_mem
         [R]=formed_rect  [F]=forming_event  [L]=lrs_cycling
  """)
    print(SEP)


if __name__ == "__main__":
    run()
