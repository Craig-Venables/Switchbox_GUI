"""
One-off migration: Helpers refactor.
Moves core to analysis/ and plotting/, standalones to tools/, assets to resources/,
updates all imports and path references, then removes deprecated IV_Analysis and Sample_Analysis.

Run from project root: python refactor_helpers_migrate.py
"""

from pathlib import Path
import shutil
import re

PROJECT_ROOT = Path(__file__).resolve().parent

# (source relative to PROJECT_ROOT, destination relative to PROJECT_ROOT)
MOVES = [
    ("Helpers/Analysis", "analysis"),
    ("plotting", "plotting"),
    ("Helpers/Data_Analysis", "tools/device_visualizer"),
    ("Helpers/Classification_Validation", "tools/classification_validation"),
    ("Helpers/Camera_Stream_Standalone", "tools/camera_stream_standalone"),
    ("Helpers/Connection_Check_Standalone", "tools/connection_check_standalone"),
    ("tools/data_analysis_pulse_2450", "tools/data_analysis_pulse_2450"),
    ("Helpers/Equipment_Address_Location", "tools/equipment_address_location"),
    ("Helpers/HP4140B_GUI", "tools/hp4140b_gui"),
    ("Helpers/ITO_Analysis", "tools/ito_analysis"),
    ("Helpers/Maps_Create", "tools/maps_create"),
    ("Helpers/TSP_Testing_GUI_Standalone_V1", "tools/tsp_testing_gui_standalone_v1"),
    ("resources/sample_information", "resources/sample_information"),
]

# Replacements: (pattern, replacement). Order: more specific first.
# Applied to .py and .md files under PROJECT_ROOT (excluding archive, .git, __pycache__).
REPLACEMENTS = [
    # Submodule imports (specific first)
    ("tools.device_visualizer.device_visualizer_app", "tools.device_visualizer.device_visualizer_app"),
    ("analysis.aggregators.dc_endurance_analyzer", "analysis.aggregators.dc_endurance_analyzer"),
    ("analysis.core.sweep_analyzer", "analysis.core.sweep_analyzer"),
    ("analysis.api.iv_sweep_llm_analyzer", "analysis.api.iv_sweep_llm_analyzer"),
    ("analysis.api.iv_sweep_analyzer", "analysis.api.iv_sweep_analyzer"),
    ("analysis.utils.migrate_folder_structure", "analysis.utils.migrate_folder_structure"),
    ("tools.classification_validation.gui.main_window", "tools.classification_validation.gui.main_window"),
    ("tools.classification_validation.gui.file_browser", "tools.classification_validation.gui.file_browser"),
    ("tools.classification_validation.gui.review_panel", "tools.classification_validation.gui.review_panel"),
    ("tools.classification_validation.gui.tuning_panel", "tools.classification_validation.gui.tuning_panel"),
    ("tools.classification_validation.gui.metrics_panel", "tools.classification_validation.gui.metrics_panel"),
    ("tools.classification_validation.validation_tool", "tools.classification_validation.validation_tool"),
    ("plotting.unified_plotter", "plotting.unified_plotter"),
    # Package-level
    ("tools.device_visualizer", "tools.device_visualizer"),
    ("plotting", "plotting"),
    ("analysis", "analysis"),
    ("analysis", "analysis"),
    ("analysis", "analysis"),
    ("tools.classification_validation", "tools.classification_validation"),
    ("tools.camera_stream_standalone", "tools.camera_stream_standalone"),
    ("tools.connection_check_standalone", "tools.connection_check_standalone"),
    ("tools.device_visualizer_Pulse_2450", "tools.data_analysis_pulse_2450"),
    ("tools.equipment_address_location", "tools.equipment_address_location"),
    ("tools.hp4140b_gui", "tools.hp4140b_gui"),
    ("tools.ito_analysis", "tools.ito_analysis"),
    ("tools.maps_create", "tools.maps_create"),
    ("tools.tsp_testing_gui_standalone_v1", "tools.tsp_testing_gui_standalone_v1"),
    # Path strings (forward slash)
    ('"resources/sample_information"', '"resources/sample_information"'),
    ("'resources/sample_information'", "'resources/sample_information'"),
    ('"plotting"', '"plotting"'),
    ("'plotting'", "'plotting'"),
    ('"tools/data_analysis_pulse_2450"', '"tools/data_analysis_pulse_2450"'),
    ("'tools/data_analysis_pulse_2450'", "'tools/data_analysis_pulse_2450'"),
    ('"analysis/core/"', '"analysis/core/"'),
    ('"analysis/"', '"analysis/"'),
    # Path concatenation: "resources" / "sample_information" -> "resources" / "sample_information"
    ('"resources" / "sample_information"', '"resources" / "sample_information"'),
    ("'resources' / 'sample_information'", "'resources' / 'sample_information'"),
    # Path: "Helpers" / "plotting_core" -> "plotting" (plot_handlers uses parents[2] / "plotting")
    ('/ "plotting"', '/ "plotting"'),
    ('/ "tools" / "data_analysis_pulse_2450"', '/ "tools" / "data_analysis_pulse_2450"'),
]

# Special case: pulse_testing_gui uses .parent (wrong); fix to project root + tools path
PULSE_TESTING_FIX = (
    'Path(__file__).parent / "tools" / "data_analysis_pulse_2450" / "main.py"',
    'Path(__file__).resolve().parents[2] / "tools" / "data_analysis_pulse_2450" / "main.py"',
)


def should_skip_dir(d: Path) -> bool:
    return d.name in (".git", "__pycache__", "archive", "venv", ".venv", "node_modules")


def collect_files(root: Path, exts: tuple = (".py", ".md")) -> list[Path]:
    out = []
    for p in root.rglob("*"):
        if p.is_file() and p.suffix in exts:
            try:
                rel = p.relative_to(root)
                if any(part in rel.parts for part in (".git", "archive", "__pycache__")):
                    continue
            except ValueError:
                continue
            out.append(p)
    return out


def apply_replacements(file_path: Path) -> bool:
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        print(f"  Skip read {file_path}: {e}")
        return False
    original = text
    for old, new in REPLACEMENTS:
        text = text.replace(old, new)
    # Special fix for pulse_testing_gui
    if PULSE_TESTING_FIX[0] in text:
        text = text.replace(PULSE_TESTING_FIX[0], PULSE_TESTING_FIX[1])
    if text != original:
        file_path.write_text(text, encoding="utf-8")
        return True
    return False


def main():
    root = PROJECT_ROOT
    if not (root / "Helpers").exists():
        print("Helpers/ not found. Run from project root.")
        return
    if (root / "analysis").exists():
        print("analysis/ already exists. Refactor may have been run. Aborting.")
        return

    print("Creating tools/ and resources/ ...")
    (root / "tools").mkdir(exist_ok=True)
    (root / "resources").mkdir(exist_ok=True)

    print("Moving directories...")
    for src_rel, dst_rel in MOVES:
        src = (root / src_rel).resolve()
        dst = (root / dst_rel).resolve()
        try:
            src_str = src.relative_to(root)
        except ValueError:
            src_str = src
        if not src.exists():
            print(f"  Skip (missing): {src_str}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            print(f"  Skip (dst exists): {dst_rel}")
            continue
        shutil.move(str(src), str(dst))
        print(f"  {src_rel} -> {dst_rel}")

    print("Applying import/path replacements...")
    files = collect_files(root)
    updated = 0
    for f in files:
        if apply_replacements(f):
            updated += 1
            print(f"  Updated: {f.relative_to(root)}")
    print(f"Updated {updated} files.")

    print("Removing deprecated Helpers/IV_Analysis and Helpers/Sample_Analysis...")
    for name in ("IV_Analysis", "Sample_Analysis"):
        d = root / "Helpers" / name
        if d.exists():
            shutil.rmtree(d)
            print(f"  Removed Helpers/{name}")

    # Move ANALYSIS_STRUCTURE.md and README_ADD_SAMPLE_TYPE.md out of Helpers if they still exist
    for doc in ("ANALYSIS_STRUCTURE.md", "README_ADD_SAMPLE_TYPE.md"):
        src = root / "Helpers" / doc
        if src.exists():
            dst = root / "analysis" / doc if doc == "ANALYSIS_STRUCTURE.md" else root / "Documents" / doc
            if doc == "README_ADD_SAMPLE_TYPE.md" and not (root / "Documents").exists():
                dst = root / "analysis" / doc
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            print(f"  Moved Helpers/{doc} -> {dst.relative_to(root)}")

    print("Done. Check git diff and run tests.")


if __name__ == "__main__":
    main()
