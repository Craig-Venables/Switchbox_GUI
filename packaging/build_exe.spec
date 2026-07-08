# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Switchbox_GUI v6.1 (windowed, onedir).

Build from repository root::

    python packaging/build_exe.py
or as part of the full v6 release::

    python packaging/build_release_v6.py --build

Module / data inventory: Documents/build/BUILD_MODULES.md
Release checklist: packaging/BUILD_RELEASE_V6.md
"""
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# Spec lives in packaging/; application root is one level up.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(SPEC)))


def _safe_collect_submodules(package: str) -> list:
    try:
        return collect_submodules(package)
    except Exception:
        return []


# Root-level plotting shims (plotting.sample_plots, etc.) log deprecation on import;
# skip them as hiddenimports — real code uses plotting.sample, plotting.device, etc.
_SKIP_PLOTTING_ROOT_SHIMS = frozenset(
    {"sample_plots", "endurance_plots", "section_plots", "device_combined_plots"}
)


def _modules_from_pkg_path(pkg_name: str, relative_folder: str) -> list:
    """
    List import paths (e.g. analysis.core.sweep_analyzer) by walking .py files.
    Avoids ``import analysis`` at spec time (that package pulls scipy immediately).
    PyInstaller still follows imports inside those files to bundle scipy, etc.
    """
    root = Path(REPO_ROOT) / relative_folder
    if not root.is_dir():
        return []
    out: list = []
    for p in root.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        rel = p.relative_to(root)
        parts = list(rel.with_suffix("").parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        if pkg_name == "plotting" and len(parts) == 1 and parts[0] in _SKIP_PLOTTING_ROOT_SHIMS:
            continue
        if not parts:
            out.append(pkg_name)
        else:
            out.append(pkg_name + "." + ".".join(parts))
    return sorted(set(out))


def _optional_moku_binaries() -> list:
    """Bundle Moku CLI when present locally (not in git — see SETUP.md)."""
    moku_dir = Path(REPO_ROOT) / "Equipment" / "Moku" / "Moku CLI"
    if not moku_dir.is_dir():
        return []
    out: list = []
    for pattern in ("*.exe", "*.dll"):
        for src in moku_dir.rglob(pattern):
            rel_parent = src.parent.relative_to(moku_dir)
            dest = str(Path("Equipment") / "Moku" / "Moku CLI" / rel_parent)
            out.append((str(src), dest))
    return out


def _static_runtime_datas() -> list:
    """Repo trees read by path at runtime (images, calibration files, scope presets, etc.)."""
    out: list = []

    resources = os.path.join(REPO_ROOT, "resources")
    if os.path.isdir(resources):
        out.append((resources, "resources"))

    equipment_root = Path(REPO_ROOT) / "Equipment"
    if equipment_root.is_dir():
        skip_dirs = {"__pycache__", ".git"}
        skip_ext = {".py", ".pyc", ".pyo"}
        for path in equipment_root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in skip_dirs for part in path.parts):
                continue
            if path.suffix.lower() in skip_ext:
                continue
            rel_parent = path.parent.relative_to(equipment_root)
            dest = str(Path("Equipment") / rel_parent)
            out.append((str(path), dest))

    videos = os.path.join(REPO_ROOT, "Videos")
    if os.path.isdir(videos):
        out.append((videos, "Videos"))
    return out


def _tool_script_datas() -> list:
    """Python tool trees launched via Switchbox_ScriptRunner in frozen builds."""
    folders = (
        "tools/impedance_analyzer",
        "tools/Display",
        "tools/LED_testing",
        "tools/data_analysis_pulse_2450",
        "tools/device_visualizer",
        "Equipment/Laser_Power_Meter",
    )
    out: list = []
    for folder in folders:
        src = os.path.join(REPO_ROOT, folder.replace("/", os.sep))
        if os.path.isdir(src):
            out.append((src, folder.replace("/", os.sep)))
    return out


# Prefer import tracing from ``main.py`` for large trees (``Equipment``, ``Pulse_Testing``,
# ``Notifications``) to avoid PyInstaller spending minutes on optional / broken subpackages.
_pkg_roots = (
    "gui",
    "Measurements",
)

hiddenimports: list = []
# ``collect_submodules`` for gui/measurements can pull in thousands of modules and, on some
# PyInstaller 6.x + Python 3.10 environments, trigger modulegraph ``IndexError`` during bytecode
# scan. Rely on static analysis from ``main.py`` first; re-enable if the frozen app misses code.
# for _pkg in _pkg_roots:
#     hiddenimports.extend(_safe_collect_submodules(_pkg))

# Lazy-imported analysis / plotting (measurement GUI classification & plots)
hiddenimports.extend(_modules_from_pkg_path("analysis", "analysis"))
hiddenimports.extend(_modules_from_pkg_path("plotting", "plotting"))
hiddenimports.extend(_modules_from_pkg_path("Pulse_Testing", "Pulse_Testing"))

# Measurement GUI top-bar child windows (lazy-imported from child_gui_launchers)
_CHILD_GUI_PACKAGES = (
    ("gui.oscilloscope_pulse_gui", "gui/oscilloscope_pulse_gui"),
    ("gui.motor_control_gui", "gui/motor_control_gui"),
    ("gui.connection_check_gui", "gui/connection_check_gui"),
    ("gui.pulse_testing_gui", "gui/pulse_testing_gui"),
    ("gui.laser_fg_scope_gui", "gui/laser_fg_scope_gui"),
    ("tools.device_visualizer", "tools/device_visualizer"),
)
for _pkg, _folder in _CHILD_GUI_PACKAGES:
    hiddenimports.extend(_modules_from_pkg_path(_pkg, _folder))

# Lazy importlib / backends / hardware (see Documents/build/BUILD_MODULES.md)
hiddenimports += [
    "Equipment.SMU_AND_PMU.4200A.C_Code_with_python_scripts.A_Iv_Sweep.run_smu_vi_sweep",
    "Equipment.SMU_AND_PMU.keithley4200.kxci_scripts",
    "Equipment.SMU_AND_PMU.Keithley2450_TSP",
    "Equipment.SMU_AND_PMU.keithley2450_tsp_scripts",
    "Equipment.Oscilloscopes.TektronixTBS1000C",
    "matplotlib.backends.backend_tkagg",
    "matplotlib.backends.backend_qtagg",
    "PIL._tkinter_finder",
    "cv2",
    "seaborn",
    "pyvisa",
    "pyvisa_py",
    "serial.tools.list_ports",
    "serial.tools.list_ports_common",
    "telegram",
    "telegram.ext",
    "nidaqmx",
    "pint",
    "pyqtgraph",
    "gui.frozen_launch",
    "gui.measurement_gui.child_gui_launchers",
    "gui.measurement_gui.child_gui_registry",
    "PyQt5",
    "PyQt5.QtCore",
    "PyQt5.QtGui",
    "PyQt5.QtWidgets",
]

datas = [
    (os.path.join(REPO_ROOT, "Json_Files"), "Json_Files"),
    (os.path.join(REPO_ROOT, "Documents"), "Documents"),
    *_static_runtime_datas(),
    *_tool_script_datas(),
]

a = Analysis(
    [os.path.join(REPO_ROOT, "main.py")],
    pathex=[REPO_ROOT],
    binaries=_optional_moku_binaries(),
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Switchbox_GUI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Switchbox_GUI",
)
