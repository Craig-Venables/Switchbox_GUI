"""
Run classification on all files_for_testing and print a detailed diagnostic report.
Usage:  python tools/classification_validation/run_test_files.py
"""
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from analysis import quick_analyze
from analysis.core.sweep_analyzer import read_data_file

TEST_DIR = ROOT / "tools" / "classification_validation" / "files_for_testing"

# Ground-truth labels based on filename context (hand-assigned for regression testing).
# These are your best guesses from the filename - you can update them after reviewing plots.
KNOWN_LABELS = {
    # Chris_Devices-3 files
    "17-FS-0.3v-0.05sv-0.05sd-Py-Chris_Devices-3-.txt":   "non_conductive",
    # Sub-nA at 3.0V: p95=14 nA, switches between linear resistance states — forming memristive
    "19-FS-3.0v-0.05sv-0.05sd-Py-Chris_Devices-3-.txt":   "memristive",
    "19-FS-3.0v-0.05sv-0.05sd-Py-Chris_Devices-3-1.txt":  "memristive",
    # p95=0.905 nA (barely sub-1nA) — device unformed at this stage, NOT a formed memristor
    "8-FS-3.5v-0.05sv-0.05sd-Py-Chris_Devices-3-.txt":    "non_conductive",
    # St_v2 files — confirmed from IV statistics
    # p95=577 µA, flat linear, no features → ohmic
    "10-FS-1.5v-0.05sv-0.05sd-Py-St_v2-.txt":  "ohmic",
    # p95=1.47 µA, polarity asymmetry 2000x (p5 vs p95) → memristive (rectifying character)
    "4-FS-2.2v-0.05sv-0.05sd-Py-St_v2-.txt":   "memristive",
    # Strong memristive features (hyst+pinch+switch+nonlin)
    "5-FS-2.5v-0.05sv-0.05sd-Py-St_v2-.txt":   "memristive",
    "20-FS-2.8v-0.05sv-0.05sd-Py-St_v2-.txt":  "memristive",
    # Forming memristive (switching without full hysteresis loop)
    "3-FS-2.0v-0.05sv-0.05sd-Py-St_v2-.txt":   "memristive",
    # St_v1 files
    "11-FS-2.5v-0.05sv-0.05sd-Py-St_v1-3.txt": "memristive",
    "31-FS-2.5v-0.05sv-0.05sd-Py-St_v1-5.txt": "memristive",
    "31-FS-2.5v-0.05sv-0.05sd-Py-St_v1-5-2.txt": "memristive",
    # High-current (p95=333 µA), switches without hysteresis → conductive (LRS with switching)
    "37-FS-3.0v-0.05sv-0.05sd-Py-St_v1-10.02.txt": "conductive",
}


def run_all():
    files = sorted(TEST_DIR.glob("*.txt"))
    if not files:
        print(f"No .txt files found in {TEST_DIR}")
        return

    results = []
    for f in files:
        try:
            r = read_data_file(str(f))
            if r is None or len(r) < 2:
                results.append({"file": f.name, "type": "ERROR", "error": "no IV data"})
                continue
            v, i = r[0], r[1]
            t = r[2] if len(r) > 2 else None
            a = quick_analyze(v, i, time=t, analysis_level="classification", device_name=f.stem)
            clf = a.get("classification", {}) or {}
            bd = clf.get("breakdown", {}) or {}
            feats = clf.get("features", {}) or {}
            mem_score = clf.get("memristivity_score")
            results.append({
                "file": f.name,
                "type": clf.get("device_type", "?"),
                "conf": round((clf.get("confidence") or 0) * 100, 1),
                "mem_score": round(mem_score, 1) if mem_score is not None else None,
                "forming": clf.get("forming_stage", ""),
                "scores": {k: round(val, 1) for k, val in bd.items()
                           if isinstance(val, (int, float)) and val not in (0, -999)},
                "hysteresis": feats.get("has_hysteresis"),
                "pinched": feats.get("pinched_hysteresis"),
                "switching": feats.get("switching_behavior"),
                "nonlinear": feats.get("nonlinear_iv"),
                "ohmic": feats.get("ohmic_behavior"),
                "phase": round(feats.get("phase_shift", 0), 1),
                "polarity": feats.get("polarity_dependent"),
                "compliance_limited": feats.get("compliance_limited", False),
                "warnings": clf.get("warnings", []),
                "known": KNOWN_LABELS.get(f.name),
            })
        except Exception as e:
            import traceback
            results.append({"file": f.name, "type": "ERROR", "error": str(e), "trace": traceback.format_exc()})

    SEP = "=" * 80
    print(f"\n{SEP}")
    print("  TEST FILE CLASSIFICATION REPORT")
    print(SEP)
    print(f"  {'File':<52} {'Predicted':>14} {'Conf':>6} {'Mem':>5} {'Known':>14} {'Match':>6}")
    print(f"  {'-'*52} {'-'*14} {'-'*6} {'-'*5} {'-'*14} {'-'*6}")

    correct = wrong = unknown = 0
    for r in results:
        known = r.get("known") or "?"
        predicted = r.get("type", "ERROR")
        match_str = ""
        if known != "?":
            if predicted == known:
                match_str = "  OK"
                correct += 1
            else:
                match_str = "FAIL"
                wrong += 1
        else:
            unknown += 1

        print(f"  {r['file'][:52]:<52} {predicted:>14} {str(r.get('conf','')):>5}% "
              f"{str(r.get('mem_score','') or ''):>5} {known:>14} {match_str:>6}")

    print(f"\n  Labelled: {correct+wrong}  Correct: {correct}  Wrong: {wrong}  Unlabelled: {unknown}")
    if correct + wrong > 0:
        print(f"  Accuracy on labelled subset: {100*correct/(correct+wrong):.0f}%")

    print(f"\n{SEP}")
    print("  DETAILED PER-FILE BREAKDOWN")
    print(SEP)
    for r in results:
        if r.get("type") == "ERROR":
            print(f"\n[ERROR] {r['file']}: {r.get('error')}")
            continue
        known = r.get("known") or "?"
        match = ""
        if known != "?":
            match = " OK" if r["type"] == known else f" FAIL (expected {known})"
        print(f"\n{r['file']}")
        print(f"  -> {r['type']} | conf={r['conf']}% | mem_score={r['mem_score']} | forming={r['forming']}{match}")
        print(f"  scores: {r['scores']}")
        print(f"  feats:  hyst={r['hysteresis']} pinch={r['pinched']} switch={r['switching']} "
              f"nonlin={r['nonlinear']} ohmic={r['ohmic']} phase={r['phase']}deg "
              f"polarity={r['polarity']} comply_lim={r['compliance_limited']}")
        if r["warnings"]:
            for w in r["warnings"]:
                # Strip non-ASCII to avoid Windows cp1252 encoding errors
                safe_w = w.encode("ascii", errors="replace").decode("ascii")
                print(f"  WARN:   {safe_w[:120]}")

    print(f"\n{SEP}")
    print("  SCORE DISTRIBUTION SUMMARY")
    print(SEP)
    type_counts = {}
    for r in results:
        t = r.get("type", "ERROR")
        type_counts[t] = type_counts.get(t, 0) + 1
    for t, n in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {t:<20} {n:>3} sweep(s)")

    print()
    return results


if __name__ == "__main__":
    run_all()
