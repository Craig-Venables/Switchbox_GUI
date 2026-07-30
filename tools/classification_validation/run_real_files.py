"""
Run classification on a diverse selection of REAL lab data files and produce a diagnostic report.

Files span:
  - D94  ITO-PMMA(2%)-Gold: multiple devices, low-to-high voltage forming trajectory
  - D80  ITO-PMMA(2%)-Gold: 3.0V sweep
  - D81  ITO-PMMA(3%)-Gold: different recipe (lower concentration, thicker PMMA)
  - D93  ITO-PMMA(2%)-Gold: different substrate sample
  - D103 ITO-PMMA2.0(2%)-Gold: newer sample batch
  - D105 ITO-PMMA2.0(2%)-Gold: different electrode (ITO top)
  - Chris_Sample_4: external sample, different substrate

Usage:  python tools/classification_validation/run_real_files.py
"""
import sys
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from analysis import quick_analyze
from analysis.core.sweep_analyzer import read_data_file

DATA = Path(r"C:\Users\ppxcv1\OneDrive - The University of Nottingham\Documents\Data_folder")

# (path_relative_to_DATA, label, notes)
TEST_FILES = [
    # --- D94: forming trajectory sweep 1-10 on device A-1 ---
    ("D94-0.1mgml-ITO-PMMA(2%)-Gold-s2/A/1/1-FS-0.5v-0.05sv-0.05sd-Py-St_v2_led-3.txt",
     None, "D94 A-1 sweep 1 / 0.5V — expect non_conductive or memristive (pre-forming / precursor rectifying)"),
    ("D94-0.1mgml-ITO-PMMA(2%)-Gold-s2/A/1/10-FS-2.0v-0.05sv-0.05sd-Py-St_v2_led-3.txt",
     None, "D94 A-1 sweep 10 / 2.0V — expect forming or memristive"),

    # --- D94: different devices same section ---
    ("D94-0.1mgml-ITO-PMMA(2%)-Gold-s2/A/5/10-FS-2.0v-0.05sv-0.05sd-Py-St_v2_led-3.txt",
     None, "D94 A-5 sweep 10 — different device, same sample"),
    ("D94-0.1mgml-ITO-PMMA(2%)-Gold-s2/A/6/10-FS-2.0v-0.05sv-0.05sd-Py-St_v2_led-3.txt",
     None, "D94 A-6 sweep 10"),
    ("D94-0.1mgml-ITO-PMMA(2%)-Gold-s2/A/10/10-FS-2.0v-0.05sv-0.05sd-Py-St_v2_led-3.txt",
     None, "D94 A-10 sweep 10"),

    # --- D80: early 3.0V sweep ---
    ("D80-0.1mgml-ITO-PMMA(2%)-Gold-s2/A/1/0-FS-3.0v-0.05sv-0.05sd-Py-3.0.txt",
     None, "D80 A-1 / 3.0V sweep 0 — first sweep on this device"),

    # --- D81: lower concentration, thicker PMMA ---
    ("D81-0.07mgml-ITO-PMMA(3%)-Gold-s3/H/4/0-FS-3.0v-0.1sv-0.05sd-Py-1.0.txt",
     None, "D81 H-4 / 3.0V — 0.07mgml lower concentration"),
    ("D81-0.07mgml-ITO-PMMA(3%)-Gold-s3/H/4/10-FS-2.8v-0.05sv-0.05sd-Py-St_v1-5.txt",
     None, "D81 H-4 sweep 10 / 2.8V"),
    ("D81-0.07mgml-ITO-PMMA(3%)-Gold-s3/H/5/10-FS-2.8v-0.05sv-0.05sd-Py-St_v1-5.txt",
     None, "D81 H-5 sweep 10 / 2.8V — adjacent device"),
    ("D81-0.07mgml-ITO-PMMA(3%)-Gold-s3/H/5/11-FS-2.5v-0.05sv-0.05sd-Py-St_v1-3.txt",
     None, "D81 H-5 sweep 11 / 2.5V"),

    # --- D93: different substrate run ---
    ("D93-0.1mgml-ITO-PMMA(2%)-Gold-s1/A/5/0-FS-3.0v-0.1sv-0.05sd-Py-2.0.txt",
     None, "D93 A-5 / 3.0V first sweep"),
    ("D93-0.1mgml-ITO-PMMA(2%)-Gold-s1/A/6/0-FS-3.0v-0.1sv-0.05sd-Py-2.0.txt",
     None, "D93 A-6 / 3.0V first sweep"),
    ("D93-0.1mgml-ITO-PMMA(2%)-Gold-s1/A/7/0-FS-3.0v-0.1sv-0.05sd-Py-2.0.txt",
     None, "D93 A-7 / 3.0V first sweep"),
    ("D93-0.1mgml-ITO-PMMA(2%)-Gold-s1/A/8/0-FS-4.0v-0.1sv-0.05sd-Py-2.0.txt",
     None, "D93 A-8 / 4.0V first sweep — higher voltage"),

    # --- D103: newer batch ---
    ("D103-0.1mgml-ITO-PMMA 2.0(2%)-Gold-s4/G/1/1-FS-0.5v-0.05sv-0.05sd-Py-St_v2-3.txt",
     None, "D103 G-1 sweep 1 / 0.5V — expect pre-forming"),
    ("D103-0.1mgml-ITO-PMMA 2.0(2%)-Gold-s4/G/1/10-FS-2.0v-0.05sv-0.05sd-Py-St_v2-3.txt",
     None, "D103 G-1 sweep 10 / 2.0V"),

    # --- D105: ITO-PMMA2.0 different electrode ---
    ("D105-0.1mgml-ITO-PMMA 2.0(2%)-Gold-s6/C/1/0-FS-0.8v-0.05sv-0.05sd-Py-1.0.txt",
     None, "D105 C-1 sweep 0 / 0.8V"),
    ("D105-0.1mgml-ITO-PMMA 2.0(2%)-Gold-s6/C/1/1-FS-0.8v-0.05sv-0.05sd-Py-1.0.txt",
     None, "D105 C-1 sweep 1 / 0.8V"),

    # --- Chris_Sample_4: external sample ---
    ("Chris_Sample_4/F/1/1-FS-0.3v-0.05sv-0.05sd-Py-Chris_Devices-3-.txt",
     None, "Chris F-1 sweep 1 / 0.3V — expect non_conductive"),
    ("Chris_Sample_4/F/1/11-FS-3.0v-0.05sv-0.05sd-Py-Chris_Devices-3-.txt",
     None, "Chris F-1 sweep 11 / 3.0V — expect memristive or forming"),
    ("Chris_Sample_4/F/1/10-FS-3.5v-0.05sv-0.05sd-Py-Chris_Devices-3-.txt",
     None, "Chris F-1 sweep 10 / 3.5V"),
]


def run():
    SEP = "=" * 90

    results = []
    for rel_path, label, notes in TEST_FILES:
        full = DATA / rel_path
        short = full.name
        device_label = Path(rel_path).parts[0]  # e.g. D94-...

        if not full.exists():
            results.append({"path": str(full), "short": short, "device": device_label,
                            "notes": notes, "type": "FILE_NOT_FOUND", "error": "missing"})
            continue

        try:
            r = read_data_file(str(full))
            if r is None or len(r) < 2:
                raise ValueError("no IV data")
            v, i = r[0], r[1]
            t = r[2] if len(r) > 2 else None

            p95 = float(np.percentile(np.abs(i), 95))
            i_max = float(np.max(np.abs(i)))

            a = quick_analyze(v, i, time=t, analysis_level="classification", device_name=full.stem)
            clf = a.get("classification", {}) or {}
            bd = clf.get("breakdown") or {}
            feats = clf.get("features") or {}
            mem_score = clf.get("memristivity_score")

            active_scores = {k: round(val, 1) for k, val in bd.items()
                             if isinstance(val, (int, float)) and val not in (0, -999)}

            results.append({
                "path": str(full),
                "short": short,
                "device": device_label,
                "notes": notes,
                "label": label,
                "type": clf.get("device_type", "?"),
                "conf": round((clf.get("confidence") or 0) * 100, 1),
                "mem_score": round(mem_score, 1) if mem_score is not None else None,
                "forming": clf.get("forming_stage", ""),
                "scores": active_scores,
                "feats": {
                    "hyst": feats.get("has_hysteresis"),
                    "pinch": feats.get("pinched_hysteresis"),
                    "switch": feats.get("switching_behavior"),
                    "nonlin": feats.get("nonlinear_iv"),
                    "ohmic": feats.get("ohmic_behavior"),
                    "phase": round(feats.get("phase_shift", 0), 1),
                    "polarity": feats.get("polarity_dependent"),
                    "comply": feats.get("compliance_limited", False),
                },
                "p95_na": round(p95 * 1e9, 2),
                "imax_ua": round(i_max * 1e6, 3),
                "warnings": [w.encode("ascii", errors="replace").decode("ascii")
                             for w in clf.get("warnings", [])],
            })

        except Exception as e:
            import traceback
            results.append({"path": str(full), "short": short, "device": device_label,
                            "notes": notes, "type": "ERROR", "error": str(e)})

    # -----------------------------------------------------------------------
    # Summary table
    # -----------------------------------------------------------------------
    print(f"\n{SEP}")
    print("  REAL-DATA CLASSIFICATION REPORT")
    print(SEP)
    print(f"  {'File':<52} {'Device':<7} {'Type':>14} {'Conf':>6} {'Mem':>5} {'I p95':>9}")
    print(f"  {'-'*52} {'-'*7} {'-'*14} {'-'*6} {'-'*5} {'-'*9}")

    type_counts = {}
    for r in results:
        t = r.get("type", "ERROR")
        type_counts[t] = type_counts.get(t, 0) + 1

        p95_str = f"{r.get('p95_na', 0):.1f}nA" if r.get('p95_na', 0) < 1000 else f"{r.get('p95_na',0)/1000:.1f}µA"
        print(f"  {r['short'][:52]:<52} {r['device'][:7]:<7} "
              f"{r.get('type','?'):>14} {str(r.get('conf','')):>5}%"
              f" {str(r.get('mem_score','') or ''):>5} {p95_str:>9}")

    # -----------------------------------------------------------------------
    # Per-device forming trajectory
    # -----------------------------------------------------------------------
    print(f"\n{SEP}")
    print("  FORMING TRAJECTORY (grouped by device folder)")
    print(SEP)
    by_device: dict = {}
    for r in results:
        by_device.setdefault(r["device"], []).append(r)

    for dev, recs in by_device.items():
        print(f"\n  [{dev}]")
        for r in recs:
            stage = r.get("forming", "")
            warn_n = len(r.get("warnings", []))
            print(f"    {r['short'][:55]:<55} -> {r.get('type','?'):14}  "
                  f"conf={str(r.get('conf','')):>4}%  stage={stage}"
                  + (f"  WARN:{warn_n}" if warn_n else ""))

    # -----------------------------------------------------------------------
    # Issues and tuning suggestions
    # -----------------------------------------------------------------------
    print(f"\n{SEP}")
    print("  ISSUES / OBSERVATIONS")
    print(SEP)

    uncertain_list = [r for r in results if r.get("type") == "uncertain"]
    low_conf = [r for r in results if isinstance(r.get("conf"), float) and r["conf"] < 50
                and r.get("type") not in ("non_conductive", "uncertain", "ERROR", "FILE_NOT_FOUND")]
    warned = [r for r in results if r.get("warnings")]
    comply = [r for r in results if r.get("feats", {}).get("comply")]

    if uncertain_list:
        print(f"\n  Uncertain classifications ({len(uncertain_list)}):")
        for r in uncertain_list:
            print(f"    {r['short']}  scores={r.get('scores',{})}  p95={r.get('p95_na',0):.1f}nA")
            print(f"    feats={r.get('feats',{})}  notes: {r['notes']}")

    if low_conf:
        print(f"\n  Low confidence <50% (not non_conductive) ({len(low_conf)}):")
        for r in low_conf:
            print(f"    {r['short']}  -> {r['type']}  {r['conf']}%  scores={r.get('scores',{})}")

    if comply:
        print(f"\n  Compliance-limited sweeps ({len(comply)}) - review priority HIGH:")
        for r in comply:
            print(f"    {r['short']}  -> {r['type']}  p95={r.get('p95_na',0):.1f}nA  imax={r.get('imax_ua',0):.2f}µA")

    if warned:
        print(f"\n  Files with classifier warnings ({len(warned)}):")
        for r in warned:
            for w in r["warnings"]:
                print(f"    [{r['short'][:40]}] {w[:100]}")

    # -----------------------------------------------------------------------
    # Distribution
    # -----------------------------------------------------------------------
    print(f"\n{SEP}")
    print("  TYPE DISTRIBUTION")
    print(SEP)
    for t, n in sorted(type_counts.items(), key=lambda x: -x[1]):
        pct = 100 * n / len(results)
        bar = "#" * n
        print(f"  {t:<20} {n:>3}  ({pct:.0f}%)  {bar}")

    # -----------------------------------------------------------------------
    # Tuning suggestions
    # -----------------------------------------------------------------------
    print(f"\n{SEP}")
    print("  TUNING SUGGESTIONS FROM THIS RUN")
    print(SEP)

    mem_results = [r for r in results if r.get("type") == "memristive"]
    nc_results  = [r for r in results if r.get("type") == "non_conductive"]
    rect_results = [r for r in results if r.get("type") == "memristive" and r.get("features", {}).get("rectifying_character")]
    ohmic_results = [r for r in results if r.get("type") == "ohmic"]

    # Check for memristive sweeps with low mem_score (weak forming)
    weak_mem = [r for r in mem_results if r.get("mem_score") is not None and r["mem_score"] < 40]
    if weak_mem:
        print(f"\n  {len(weak_mem)} memristive sweeps have mem_score < 40 (weak_memristive forming stage):")
        for r in weak_mem:
            print(f"    {r['short'][:55]}  score={r['mem_score']}  forming={r.get('forming')}")
        print("    -> These are correctly identified but worth reviewing to check forming trajectory")

    # Check for uncertain that might be low-voltage pre-forming
    unc_low_v = [r for r in uncertain_list if "0.3v" in r["short"] or "0.5v" in r["short"] or "0.8v" in r["short"]]
    if unc_low_v:
        print(f"\n  {len(unc_low_v)} uncertain at low voltages — likely pre-forming (expected):")
        for r in unc_low_v:
            print(f"    {r['short']}")

    # Same device, compare low vs high voltage
    print(f"\n  Cross-device consistency check (same sample, different sweeps):")
    for dev, recs in by_device.items():
        types = list(dict.fromkeys(r.get("type","?") for r in recs if r.get("type")))
        if len(types) > 1:
            print(f"    {dev[:40]}: {types} — trajectory visible OK")
        elif len(types) == 1:
            print(f"    {dev[:40]}: all {types[0]} (consistent)")

    print(f"\n{SEP}\n")
    return results


if __name__ == "__main__":
    run()
