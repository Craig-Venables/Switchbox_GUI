"""
Run classification across full sweep trajectories for specific devices to validate
the forming progression: non_conductive -> rectifying -> forming_memristive -> formed_memristive.

Usage:  python tools/classification_validation/run_trajectories.py
"""
import sys
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from analysis import quick_analyze
from analysis.core.sweep_analyzer import read_data_file

DATA = Path(r"C:\Users\ppxcv1\OneDrive - The University of Nottingham\Documents\Data_folder")

DEVICES = {
    "D94-A-1  (ITO-PMMA2%-Gold)": DATA / "D94-0.1mgml-ITO-PMMA(2%)-Gold-s2/A/1",
    "D80-A-1  (ITO-PMMA2%-Gold)": DATA / "D80-0.1mgml-ITO-PMMA(2%)-Gold-s2/A/1",
    "D80-A-1-extra (sweeps 15-25)": DATA / "D80-0.1mgml-ITO-PMMA(2%)-Gold-s2/A/1",  # same folder
}

EXCLUDE = {"log", "analysis", "stats", "tsp", "pulse", "endurance", "freqresp", "summary", "classification"}


def sort_key(f: Path):
    try:
        return int(f.name.split("-")[0])
    except ValueError:
        return 9999


def classify_file(path: Path):
    r = read_data_file(str(path))
    if r is None or len(r) < 2:
        return None
    v, i = r[0], r[1]
    t = r[2] if len(r) > 2 else None
    a = quick_analyze(v, i, time=t, analysis_level="classification", device_name=path.stem)
    clf = a.get("classification", {}) or {}
    bd = clf.get("breakdown") or {}
    feats = clf.get("features") or {}
    mem_score = clf.get("memristivity_score")
    p95 = float(np.percentile(np.abs(i), 95))
    imax = float(np.max(np.abs(i)))
    active = {k: round(v2, 1) for k, v2 in bd.items()
              if isinstance(v2, (int, float)) and v2 not in (0, -999)}
    return {
        "type": clf.get("device_type", "?"),
        "conf": round((clf.get("confidence") or 0) * 100, 1),
        "mem_score": round(mem_score, 1) if mem_score is not None else None,
        "forming": clf.get("forming_stage", ""),
        "scores": active,
        "hyst": feats.get("has_hysteresis"), "pinch": feats.get("pinched_hysteresis"),
        "switch": feats.get("switching_behavior"), "nonlin": feats.get("nonlinear_iv"),
        "phase": round(feats.get("phase_shift", 0), 1),
        "polarity": feats.get("polarity_dependent"),
        "comply": feats.get("compliance_limited", False),
        "p95_na": round(p95 * 1e9, 2),
        "imax_ua": round(imax * 1e6, 3),
        "warnings": [w.encode("ascii", errors="replace").decode("ascii") for w in clf.get("warnings", [])],
    }


SEP = "=" * 95
STAGE_ICON = {
    "unformed": "[ ]",
    "precursor_rectifying": "[~]",
    "forming_memristive": "[/]",
    "forming_event":       "[F]",
    "weak_memristive": "[w]",
    "formed_memristive": "[*]",
    "formed_rectifying": "[R]",
    "lrs_cycling":         "[L]",
    "": "[ ]",
}

TYPE_COLOR = {
    "non_conductive": "NC ",
    "memristive":     "MEM",
    "ohmic":          "OHM",
    "conductive":     "CON",
    "capacitive":     "CAP",
    "uncertain":      "UNC",
}


def run():
    print(f"\n{SEP}")
    print("  FULL FORMING TRAJECTORY ANALYSIS")
    print(SEP)

    all_issues = []

    for dev_name, dev_dir in {
        # ── Previously validated ──────────────────────────────────────────
        "D80-A-1  (ITO-PMMA2%-Gold, 25 sweeps incl. forming event)":
            DATA / "D80-0.1mgml-ITO-PMMA(2%)-Gold-s2/A/1",
        "D94-A-1  (ITO-PMMA2%-Gold, never formed)":
            DATA / "D94-0.1mgml-ITO-PMMA(2%)-Gold-s2/A/1",
        # ── New devices ──────────────────────────────────────────────────
        "D96-A-1  (ITO-PMMA2%-Gold, 26 sweeps up to 4.0V)":
            DATA / "D96-0.1mgml-ITO-PMMA(2%)-Gold-s4/A/1",
        "D104-A-1 (ITO-PMMA2.0%-Gold, St_form(2.2V) protocol + compliance-controlled sweeps)":
            DATA / "D104-0.1mgml-ITO-PMMA 2.0(2%)-Gold-s5/A/1",
        "D107-F-1 (Stock-Gold-PMMA, 3 sweeps 1-3V — stock concentration)":
            DATA / "D107-Stock-Gold-PMMA 2.0(2%)-Gold-s2/F/1",
        "D111-A-1 (ITO-PMMA2.0-ITO — symmetric electrodes)":
            DATA / "D111-0.1mgml-ITO-PMMA 2.0(2%)-ITO-s11/A/1",
        "ITO_D113-A-1 (ITO device, up to 10V)":
            DATA / "ITO_D113/A/1",
        "GOX_Gap-A-1 (nanogap device, up to 25V — different physics)":
            DATA / "GOX_Gap/A/1",
    }.items():
        if not dev_dir.exists():
            print(f"\n  [{dev_name}] — directory not found, skipping")
            continue

        files = sorted(
            [f for f in dev_dir.glob("*.txt")
             if not any(ex in f.name.lower() for ex in EXCLUDE)],
            key=sort_key
        )
        if not files:
            print(f"\n  [{dev_name}] — no .txt files found")
            continue

        print(f"\n  [{dev_name}]")
        print(f"  {'Sweep':<48} {'T':>3} {'Conf':>5} {'Mem':>5} {'I_p95':>9}  {'Stage':<22}  Feats")
        print(f"  {'-'*48} {'-'*3} {'-'*5} {'-'*5} {'-'*9}  {'-'*22}  -----")

        stage_seq = []
        issues = []
        prev_type = None

        for f in files:
            try:
                r = classify_file(f)
            except Exception as e:
                print(f"  {f.name[:48]:<48} ERROR: {e}")
                continue
            if r is None:
                continue

            t_short = TYPE_COLOR.get(r["type"], r["type"][:3].upper())
            stage_icon = STAGE_ICON.get(r["forming"], "[ ]")
            stage_seq.append(r["forming"])
            p95_str = f"{r['p95_na']:.1f}nA" if r['p95_na'] < 1000 else f"{r['p95_na']/1000:.1f}µA"
            mem_str = str(r["mem_score"]) if r["mem_score"] is not None else ""

            feat_str = (
                ("H" if r["hyst"] else ".") +
                ("P" if r["pinch"] else ".") +
                ("S" if r["switch"] else ".") +
                ("N" if r["nonlin"] else ".") +
                ("C" if r["comply"] else ".")
            )

            warn_flag = " W" if r["warnings"] else "  "
            print(f"  {f.name[:48]:<48} {t_short} {r['conf']:>4}% {mem_str:>5} {p95_str:>9}"
                  f"  {stage_icon} {r['forming'][:18]:<18}  {feat_str}{warn_flag}")

            # Flag regressions (formed → non_conductive)
            if prev_type in ("memristive",) and r["type"] == "non_conductive":
                msg = f"  REGRESSION: {f.name} — was memristive, now non_conductive"
                issues.append(msg)
                print(f"  !!! {msg}")

            prev_type = r["type"]

        # Trajectory summary
        unique_stages = list(dict.fromkeys(s for s in stage_seq if s))
        print(f"\n  Forming trajectory: {' -> '.join(unique_stages) if unique_stages else 'none detected'}")

        if issues:
            all_issues.extend(issues)

    # -----------------------------------------------------------------------
    # Global issues summary
    # -----------------------------------------------------------------------
    print(f"\n{SEP}")
    print("  GLOBAL ISSUES SUMMARY")
    print(SEP)
    if all_issues:
        for iss in all_issues:
            print(f"  {iss}")
    else:
        print("  No regressions or critical issues detected across all trajectories.")

    # -----------------------------------------------------------------------
    # Tuning recommendations
    # -----------------------------------------------------------------------
    print(f"\n{SEP}")
    print("  CLASSIFIER PERFORMANCE NOTES")
    print(SEP)
    print("""
  Legend: H=has_hysteresis P=pinched_hysteresis S=switching N=nonlinear C=compliance_limited
          [ ]=unformed  [~]=precursor_rect  [/]=forming_mem  [w]=weak_mem  [*]=formed_mem
          [F]=forming_event (jump detected)  [L]=lrs_cycling (formed, in LRS)  [R]=formed_rectifying

  What to look for:
    1. Forming trajectory  : [ ] -> [~] -> [/] -> [*] is the expected progression
    2. Missing transitions : devices stuck at [ ] despite high voltage = non-forming batch
    3. Regressions         : [*] -> [ ] after formed = device death or measurement issue
    4. D81 all NC          : lower concentration + thicker PMMA may need higher voltage to form
    5. Confidence at [/]   : forming_memristive at 50-65% is correct — borderline cases for review
  """)

    print(SEP)


if __name__ == "__main__":
    run()
