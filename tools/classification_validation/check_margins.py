"""Check forming-memristive margin over conductive after the new conductive_has_switching bonus."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from analysis import quick_analyze
from analysis.core.sweep_analyzer import read_data_file

borderline = [
    "tools/classification_validation/files_for_testing/19-FS-3.0v-0.05sv-0.05sd-Py-Chris_Devices-3-.txt",
    "tools/classification_validation/files_for_testing/19-FS-3.0v-0.05sv-0.05sd-Py-Chris_Devices-3-1.txt",
    "tools/classification_validation/files_for_testing/3-FS-2.0v-0.05sv-0.05sd-Py-St_v2-.txt",
    "tools/classification_validation/files_for_testing/37-FS-3.0v-0.05sv-0.05sd-Py-St_v1-10.02.txt",
]
for path in borderline:
    r = read_data_file(str(ROOT / path))
    a = quick_analyze(r[0], r[1], analysis_level="classification", device_name=Path(path).stem)
    clf = a["classification"]
    bd = clf.get("breakdown") or {}
    active = {k: round(v, 1) for k, v in bd.items() if isinstance(v, (int, float)) and v not in (0, -999)}
    mem = active.get("memristive", 0)
    cond = active.get("conductive", 0)
    print(f"{Path(path).name}")
    print(f"  -> {clf['device_type']}  conf={clf['confidence']:.0%}  forming={clf.get('forming_stage','')}")
    print(f"  scores: {active}")
    print(f"  margin (mem-cond): {mem-cond:+.1f}  memristive wins: {clf['device_type']=='memristive'}")
    print()
